#!/usr/bin/env python3
"""
Shared utility for setting window icons across all GUI applications.
Ensures all windows use the same icon.ico from the project root.
Cross-platform compatible (Windows, Linux, macOS).
"""

import os
import sys
import platform
import tkinter as tk

# Windows-specific icon handling
if platform.system() == "Windows":
    try:
        import ctypes
        from ctypes import wintypes
        WINDOWS_AVAILABLE = True
        
        # Try to load shell32 for AppUserModelID functions
        try:
            shell32 = ctypes.windll.shell32
            WINDOWS_SHELL32_AVAILABLE = True
        except:
            WINDOWS_SHELL32_AVAILABLE = False
    except ImportError:
        WINDOWS_AVAILABLE = False
        WINDOWS_SHELL32_AVAILABLE = False
else:
    WINDOWS_AVAILABLE = False
    WINDOWS_SHELL32_AVAILABLE = False


def get_project_root():
    """Find the project root directory by looking for icon.ico"""
    # Get the directory of the current file
    current_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Check if icon.ico exists in current directory
    icon_path = os.path.join(current_dir, "icon.ico")
    if os.path.exists(icon_path):
        return current_dir
    
    # If not, go up directories until we find it
    parent = os.path.dirname(current_dir)
    while parent != current_dir:
        icon_path = os.path.join(parent, "icon.ico")
        if os.path.exists(icon_path):
            return parent
        current_dir = parent
        parent = os.path.dirname(current_dir)
    
    # Fallback: return the directory of this file (project root should be here)
    return os.path.dirname(os.path.abspath(__file__))


def get_icon_path():
    """Get the path to icon.ico in the project root"""
    project_root = get_project_root()
    return os.path.join(project_root, "icon.ico")


def set_window_icon(window, debug=False):
    """
    Set icon for a window if icon file exists - cross-platform compatible.
    Ensures icon appears in taskbar on Windows, Linux, and macOS.
    
    Args:
        window: Tkinter window object
        debug: If True, print debug information
    """
    try:
        icon_path = get_icon_path()
        
        # Convert to absolute path for better reliability
        icon_path = os.path.abspath(icon_path)
        
        if debug:
            print(f"[Icon Debug] Looking for icon at: {icon_path}")
        
        if not os.path.exists(icon_path):
            if debug:
                print(f"[Icon Debug] Warning: Icon file not found at {icon_path}")
            return
        
        if debug:
            print(f"[Icon Debug] Icon file found: {icon_path}")
        
        system = platform.system()
        icon_set = False
        
        # Windows: Use Windows API to set application icon (for taskbar)
        if system == "Windows":
            if debug:
                print("[Icon Debug] Windows detected, using Windows API + iconphoto")
            
            # CRITICAL: Use Windows API to set the application icon
            # This overrides the Python icon in the taskbar
            if WINDOWS_AVAILABLE:
                try:
                    # Get the window handle from Tkinter
                    hwnd = window.winfo_id()
                    
                    if hwnd:
                        # Load icon from file using LoadImage
                        # IMAGE_ICON = 1, LR_LOADFROMFILE = 0x0010, LR_DEFAULTSIZE = 0x0040
                        icon_handle = ctypes.windll.user32.LoadImageW(
                            None,  # hInst
                            icon_path,  # name
                            1,  # IMAGE_ICON
                            0,  # cx (0 = default size)
                            0,  # cy (0 = default size)
                            0x0010 | 0x0040  # LR_LOADFROMFILE | LR_DEFAULTSIZE
                        )
                        
                        if icon_handle and icon_handle != 0:
                            # Method 1: Set window icons directly
                            # WM_SETICON = 0x0080
                            # ICON_SMALL = 0, ICON_BIG = 1
                            ctypes.windll.user32.SendMessageW(hwnd, 0x0080, 0, icon_handle)  # ICON_SMALL
                            ctypes.windll.user32.SendMessageW(hwnd, 0x0080, 1, icon_handle)  # ICON_BIG
                            
                            # Method 2: Change window class icon (more aggressive)
                            # This changes the icon for the entire window class
                            try:
                                # Get window class name
                                class_name = ctypes.create_unicode_buffer(256)
                                ctypes.windll.user32.GetClassNameW(hwnd, class_name, 256)
                                
                                # Get class info and change icon
                                # GCL_HICON = -14, GCL_HICONSM = -34
                                # Use SetClassLongPtrW (64-bit) or SetClassLongW (32-bit)
                                try:
                                    ctypes.windll.user32.SetClassLongPtrW(hwnd, -14, icon_handle)  # GCL_HICON
                                    ctypes.windll.user32.SetClassLongPtrW(hwnd, -34, icon_handle)  # GCL_HICONSM
                                except:
                                    # Fallback for 32-bit
                                    ctypes.windll.user32.SetClassLongW(hwnd, -14, icon_handle)
                                    ctypes.windll.user32.SetClassLongW(hwnd, -34, icon_handle)
                                
                                if debug:
                                    print(f"[Icon Debug] Window class icon changed (class={class_name.value})")
                            except Exception as e:
                                if debug:
                                    print(f"[Icon Debug] SetClassLongPtr failed: {e}")
                            
                            # Method 3: Set AppUserModelID to separate from Python
                            # This helps Windows treat it as a separate app
                            if WINDOWS_SHELL32_AVAILABLE:
                                try:
                                    app_id = "DailyDashboard.TaskApp.1.0"
                                    shell32.SetCurrentProcessExplicitAppUserModelID(app_id)
                                    if debug:
                                        print(f"[Icon Debug] AppUserModelID set: {app_id}")
                                except:
                                    pass
                            
                            # Method 3: Force redraw
                            ctypes.windll.user32.InvalidateRect(hwnd, None, True)
                            ctypes.windll.user32.UpdateWindow(hwnd)
                            
                            if debug:
                                print(f"[Icon Debug] Windows API icon set successfully (hwnd={hwnd})")
                            icon_set = True
                        else:
                            if debug:
                                error_code = ctypes.windll.kernel32.GetLastError()
                                print(f"[Icon Debug] LoadImage failed, error: {error_code}")
                except Exception as e:
                    if debug:
                        print(f"[Icon Debug] Windows API failed: {e}")
                    import traceback
                    if debug:
                        traceback.print_exc()
            
            # Also set iconphoto (for window title bar and additional compatibility)
            try:
                from PIL import Image, ImageTk
                img = Image.open(icon_path)
                
                # Use 48x48 for best taskbar compatibility
                target_size = (48, 48)
                if img.size != target_size:
                    img = img.resize(target_size, Image.Resampling.LANCZOS)
                
                # Convert to RGB if necessary
                if img.mode in ('RGBA', 'LA', 'P'):
                    background = Image.new('RGB', img.size, (255, 255, 255))
                    if img.mode == 'P':
                        img = img.convert('RGBA')
                    if img.mode in ('RGBA', 'LA'):
                        alpha = img.split()[-1] if img.mode == 'RGBA' else None
                        background.paste(img, mask=alpha)
                    img = background
                elif img.mode != 'RGB':
                    img = img.convert('RGB')
                
                photo = ImageTk.PhotoImage(img)
                window.iconphoto(True, photo)
                window._icon_photo = photo
                if debug:
                    print("[Icon Debug] iconphoto set successfully")
                icon_set = True
            except ImportError:
                if debug:
                    print("[Icon Debug] PIL not available")
            except Exception as e:
                if debug:
                    print(f"[Icon Debug] iconphoto failed: {e}")
            
            # Also set iconbitmap for window title bar
            try:
                window.iconbitmap(icon_path)
                if debug:
                    print("[Icon Debug] iconbitmap set successfully")
            except Exception as e:
                if debug:
                    print(f"[Icon Debug] iconbitmap failed: {e}")
        
        # Linux/macOS: Use iconphoto with PIL (best cross-platform support)
        else:
            try:
                from PIL import Image, ImageTk
                img = Image.open(icon_path)
                
                # Resize to appropriate size
                sizes = [(32, 32), (48, 48), (64, 64)]
                best_size = None
                for size in sizes:
                    if img.size[0] >= size[0] and img.size[1] >= size[1]:
                        best_size = size
                
                if best_size:
                    img = img.resize(best_size, Image.Resampling.LANCZOS)
                
                # Convert to RGB if necessary
                if img.mode in ('RGBA', 'LA', 'P'):
                    background = Image.new('RGB', img.size, (255, 255, 255))
                    if img.mode == 'P':
                        img = img.convert('RGBA')
                    if img.mode in ('RGBA', 'LA'):
                        alpha = img.split()[-1] if img.mode == 'RGBA' else None
                        background.paste(img, mask=alpha)
                    img = background
                elif img.mode != 'RGB':
                    img = img.convert('RGB')
                
                photo = ImageTk.PhotoImage(img)
                
                # Set as default icon (True = use as default for all windows)
                window.iconphoto(True, photo)
                
                # Also try wm_iconphoto for Linux
                if system == "Linux":
                    try:
                        window.wm_iconphoto(True, photo)
                    except:
                        pass
                
                # Keep a reference to prevent garbage collection
                window._icon_photo = photo
                icon_set = True
                
            except ImportError:
                # PIL not available, try native methods
                try:
                    window.iconbitmap(icon_path)
                    icon_set = True
                except:
                    pass
            except Exception:
                # PIL failed, try fallback
                try:
                    window.iconbitmap(icon_path)
                    icon_set = True
                except:
                    pass
        
        # Final fallback: Try alternative icon formats
        if not icon_set:
            base_path = os.path.splitext(icon_path)[0]
            for ext in ['.png', '.xpm', '.xbm']:
                alt_path = base_path + ext
                if os.path.exists(alt_path):
                    try:
                        window.iconbitmap(alt_path)
                        icon_set = True
                        break
                    except:
                        continue
        
        # Force window update to ensure icon is applied
        if icon_set:
            try:
                window.update_idletasks()
                if debug:
                    print("[Icon Debug] Icon set successfully, window updated")
            except:
                pass
        elif debug:
            print("[Icon Debug] Warning: Icon was not set successfully")
        
    except Exception as e:
        if debug:
            print(f"[Icon Debug] Error setting icon: {e}")
        pass

