import tkinter as tk
from tkinter import ttk, messagebox, BooleanVar
import os
import yt_dlp
import threading
import webbrowser
import pyperclip
import pystray
from pystray import MenuItem as item
from PIL import Image, ImageTk, ImageSequence, ImageDraw
import sys
import platform
import re
from pathlib import Path
from urllib.parse import urlparse
import validators
import yt_dlp.postprocessor.ffmpeg
import queue
import shutil
import requests
import json
import zipfile
import tempfile
import subprocess
import time
import ssl
import certifi
import io
import traceback

# Platform detection
IS_WINDOWS = platform.system() == "Windows"
IS_LINUX = platform.system() == "Linux"
IS_MAC = platform.system() == "Darwin"

# Windows-specific imports (optional)
if IS_WINDOWS:
    try:
        import win32com.client
        WIN32COM_AVAILABLE = True
    except ImportError:
        WIN32COM_AVAILABLE = False
    try:
        import winreg
        WINREG_AVAILABLE = True
    except ImportError:
        WINREG_AVAILABLE = False
    try:
        import ctypes
        CTYPES_AVAILABLE = True
    except ImportError:
        CTYPES_AVAILABLE = False
else:
    WIN32COM_AVAILABLE = False
    WINREG_AVAILABLE = False
    CTYPES_AVAILABLE = False

# Debug mode - set to True to enable detailed console output
DEBUG_MODE = True

# Set up debugging and error handling
def setup_debugging():
    """Configure debugging and error handling"""
    # Print system information
    print("\n=== SYSTEM INFORMATION ===")
    print(f"Python version: {sys.version}")
    print(f"Operating system: {sys.platform}")
    print(f"Current directory: {os.getcwd()}")
    
    try:
        print(f"yt-dlp version: {yt_dlp.version.__version__}")
    except Exception as e:
        print(f"Error getting yt-dlp version: {e}")
    
    # Check for required modules (platform-specific)
    required_modules = [
        "tkinter", "PIL", "yt_dlp", "pyperclip", "pystray", 
        "validators", "requests"
    ]
    if IS_WINDOWS:
        required_modules.append("win32com")
    
    print("\n=== MODULE CHECKS ===")
    for module_name in required_modules:
        try:
            module = __import__(module_name)
            if hasattr(module, "__version__"):
                print(f"{module_name}: OK (version {module.__version__})")
            else:
                print(f"{module_name}: OK")
        except ImportError as e:
            print(f"{module_name}: MISSING - {e}")
        except Exception as e:
            print(f"{module_name}: ERROR - {e}")
    
    # Set up global exception handler
    def global_exception_handler(exc_type, exc_value, exc_traceback):
        """Handle uncaught exceptions"""
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return
            
        error_msg = "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))
        print(f"\n[CRITICAL ERROR]:\n{error_msg}")
        
        # If message box is available, show error
        try:
            if 'messagebox' in globals():
                messagebox.showerror("Critical Error", 
                    f"An unexpected error occurred: {exc_value}\n\nSee console for details.")
        except:
            pass
    
    # Install the exception handler
    sys.excepthook = global_exception_handler
    print("\n=== DEBUG SETUP COMPLETE ===\n")

# Run debugging setup
setup_debugging()

# GUI Theme and Styles
THEME = {
    'bg': '#ffffff',
    'fg': '#333333',
    'primary': '#2196F3',
    'secondary': '#1976D2',
    'success': '#4CAF50',
    'error': '#F44336',
    'warning': '#FFC107',
    'gray': '#757575',
    'light_gray': '#f5f5f5',
    'border': '#e0e0e0'
}

# Path configuration
APP_DIR = os.path.dirname(os.path.abspath(__file__))
ICON_PATH = Path(APP_DIR) / "needyamin.ico"

# Set app ID for Windows taskbar (Windows only)
if IS_WINDOWS and CTYPES_AVAILABLE:
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID('needyamin.video_downloader')
    except:
        pass

# Cross-platform installation directory
if IS_WINDOWS:
    INSTALL_DIR = Path(os.environ.get("LOCALAPPDATA", Path.home() / ".local" / "share")) / "Media Downloader"
elif IS_LINUX:
    INSTALL_DIR = Path.home() / ".local" / "share" / "Media Downloader"
else:  # macOS
    INSTALL_DIR = Path.home() / "Library" / "Application Support" / "Media Downloader"
INSTALL_DIR.mkdir(parents=True, exist_ok=True)

# Cross-platform output directories
if IS_WINDOWS:
    downloads_base = Path(os.environ.get("USERPROFILE", Path.home())) / "Downloads"
else:
    downloads_base = Path.home() / "Downloads"

downloads_path = downloads_base / "Yamin Downloader"
video_output_dir = downloads_path / "video"
audio_output_dir = downloads_path / "audio"
playlist_output_dir = downloads_path / "playlists"
video_output_dir.mkdir(parents=True, exist_ok=True)
audio_output_dir.mkdir(parents=True, exist_ok=True)
playlist_output_dir.mkdir(parents=True, exist_ok=True)

# Auto-update configuration
REPO_OWNER = "needyamin"
REPO_NAME = "media-downloader"
CURRENT_VERSION = "1.0.15"
GITHUB_API_URL = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/releases/latest"
UPDATE_CHECK_FILE = INSTALL_DIR / "last_update_check.txt"

# Add a force check flag to check for updates regardless of the time since last check
FORCE_UPDATE_CHECK = False

# Global variables
ffmpeg_path = None
early_log_queue = queue.Queue()
loading_gif = None
loading_label = None
quality_settings = {
    'video_quality': 'best',  # best, 1080p, 720p, 480p, 360p
    'audio_quality': '320',   # 320, 256, 192, 128, 96
    'format': 'mp4'          # mp4, webm, mkv
}

def verify_ffmpeg(ffmpeg_path, ffprobe_path):
    """Verify that FFmpeg and FFprobe are working."""
    try:
        print(f"\n=== FFMPEG VERIFICATION ===")
        print(f"FFmpeg path: {ffmpeg_path}")
        print(f"FFprobe path: {ffprobe_path}")
        
        if not ffmpeg_path or not ffprobe_path:
            log("FFmpeg path or FFprobe path is empty")
            print("FFmpeg or FFprobe path is empty")
            return False
            
        if not os.path.exists(ffmpeg_path) or not os.path.exists(ffprobe_path):
            log(f"FFmpeg or FFprobe executable not found at: {ffmpeg_path} or {ffprobe_path}")
            print(f"FFmpeg file exists: {os.path.exists(ffmpeg_path)}")
            print(f"FFprobe file exists: {os.path.exists(ffprobe_path)}")
            return False
            
        # Cross-platform subprocess flags
        subprocess_kwargs = {}
        if IS_WINDOWS:
            subprocess_kwargs['creationflags'] = subprocess.CREATE_NO_WINDOW
        else:
            subprocess_kwargs['stdout'] = subprocess.DEVNULL
            subprocess_kwargs['stderr'] = subprocess.DEVNULL
        
        # Check FFmpeg
        log(f"Testing FFmpeg at: {ffmpeg_path}")
        print(f"Testing FFmpeg execution...")
        result = subprocess.run([ffmpeg_path, '-version'], 
                              capture_output=True, 
                              text=True,
                              **subprocess_kwargs)
        if result.returncode != 0:
            log(f"FFmpeg test failed with return code: {result.returncode}")
            log(f"Error: {result.stderr}")
            print(f"FFmpeg test failed with return code: {result.returncode}")
            print(f"Error: {result.stderr}")
            return False
        else:
            log("FFmpeg test successful")
            print(f"FFmpeg version: {result.stdout.splitlines()[0] if result.stdout else 'Unknown'}")
            
        # Check FFprobe
        log(f"Testing FFprobe at: {ffprobe_path}")
        print(f"Testing FFprobe execution...")
        result = subprocess.run([ffprobe_path, '-version'], 
                              capture_output=True, 
                              text=True,
                              **subprocess_kwargs)
        if result.returncode != 0:
            log(f"FFprobe test failed with return code: {result.returncode}")
            log(f"Error: {result.stderr}")
            print(f"FFprobe test failed with return code: {result.returncode}")
            print(f"Error: {result.stderr}")
            return False
        else:
            log("FFprobe test successful")
            print(f"FFprobe version: {result.stdout.splitlines()[0] if result.stdout else 'Unknown'}")
            
        print("FFmpeg verification passed successfully")
        return True
    except Exception as e:
        log(f"Error verifying FFmpeg: {str(e)}")
        print(f"Exception during FFmpeg verification: {str(e)}")
        print(traceback.format_exc())
        return False

def download_ffmpeg():
    """Download and install FFmpeg."""
    message_label = None
    try:
        # Create FFmpeg directory (cross-platform)
        ffmpeg_dir = INSTALL_DIR / "ffmpeg"
        ffmpeg_dir.mkdir(parents=True, exist_ok=True)
        
        # Platform-specific executable names
        if IS_WINDOWS:
            ffmpeg_exe = "ffmpeg.exe"
            ffprobe_exe = "ffprobe.exe"
        else:
            ffmpeg_exe = "ffmpeg"
            ffprobe_exe = "ffprobe"
        
        # Check if FFmpeg is already installed and working
        ffmpeg_path = ffmpeg_dir / ffmpeg_exe
        ffprobe_path = ffmpeg_dir / ffprobe_exe
        
        if ffmpeg_path.exists() and ffprobe_path.exists():
            if verify_ffmpeg(str(ffmpeg_path), str(ffprobe_path)):
                log("FFmpeg is already installed and working")
                return str(ffmpeg_path)
        
        # Show loading animation
        message_label = show_loading("Downloading FFmpeg...")
        
        # Platform-specific download URLs
        if IS_WINDOWS:
            download_urls = [
                "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip",
                "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip",
                "https://github.com/GyanD/codexffmpeg/releases/download/2023-10-08-git-10a3e7e0f8/ffmpeg-2023-10-08-git-10a3e7e0f8-essentials_build.zip"
            ]
        elif IS_LINUX:
            # For Linux, provide instructions to install via package manager
            messagebox.showinfo("FFmpeg Installation", 
                "FFmpeg is not installed.\n\n"
                "Please install FFmpeg using your package manager:\n\n"
                "Ubuntu/Debian: sudo apt-get install ffmpeg\n"
                "Fedora: sudo dnf install ffmpeg\n"
                "Arch: sudo pacman -S ffmpeg\n\n"
                "Or download from: https://ffmpeg.org/download.html")
            return None
        else:  # macOS
            messagebox.showinfo("FFmpeg Installation",
                "FFmpeg is not installed.\n\n"
                "Please install FFmpeg using Homebrew:\n\n"
                "brew install ffmpeg\n\n"
                "Or download from: https://ffmpeg.org/download.html")
            return None
        
        download_urls = download_urls if IS_WINDOWS else []
        
        # Try each download URL until one succeeds
        for download_url in download_urls:
            try:
                log(f"Attempting to download FFmpeg from: {download_url}")
                
                # Download FFmpeg from GitHub
                response = requests.get(download_url, stream=True, timeout=30)
                response.raise_for_status()
                
                # Get total file size
                total_size = int(response.headers.get('content-length', 0))
                block_size = 1024  # 1 Kibibyte
                downloaded = 0
                
                # Save the zip file with progress
                zip_path = ffmpeg_dir / "ffmpeg.zip"
                with open(zip_path, 'wb') as f:
                    for data in response.iter_content(block_size):
                        downloaded += len(data)
                        f.write(data)
                        # Update progress
                        if total_size:
                            percent = int(100 * downloaded / total_size)
                            message = f"Downloading FFmpeg... {percent}% ({downloaded}/{total_size} bytes)"
                            log(message)
                            if message_label:
                                message_label.config(text=message)
                
                log("FFmpeg download completed. Extracting files...")
                if message_label:
                    message_label.config(text="Extracting FFmpeg files...")
                
                # Extract the zip file
                with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                    zip_ref.extractall(ffmpeg_dir)
                
                # Find the bin directory with ffmpeg and ffprobe executables
                ffmpeg_exe_paths = list(ffmpeg_dir.glob(f"**/{ffmpeg_exe}"))
                ffprobe_exe_paths = list(ffmpeg_dir.glob(f"**/{ffprobe_exe}"))
                
                if not ffmpeg_exe_paths or not ffprobe_exe_paths:
                    log("FFmpeg executables not found in zip file")
                    continue  # Try next URL
                
                # Get the first found executables
                source_ffmpeg = ffmpeg_exe_paths[0]
                source_ffprobe = ffprobe_exe_paths[0]
                
                log(f"Moving FFmpeg from {source_ffmpeg} to {ffmpeg_path}")
                log(f"Moving FFprobe from {source_ffprobe} to {ffprobe_path}")
                
                # Move FFmpeg and FFprobe to the main directory
                if ffmpeg_path.exists():
                    ffmpeg_path.unlink()
                if ffprobe_path.exists():
                    ffprobe_path.unlink()
                    
                shutil.copy2(str(source_ffmpeg), str(ffmpeg_path))
                shutil.copy2(str(source_ffprobe), str(ffprobe_path))
                
                # Clean up
                try:
                    zip_path.unlink()
                    for item in ffmpeg_dir.glob("*"):
                        if item.is_dir() and item.name != "bin" and item != ffmpeg_path.parent and item != ffprobe_path.parent:
                            shutil.rmtree(item)
                except:
                    pass  # Ignore cleanup errors
                
                # Verify installation
                if verify_ffmpeg(str(ffmpeg_path), str(ffprobe_path)):
                    log("FFmpeg installation successful")
                    return str(ffmpeg_path)
                else:
                    log("FFmpeg verification failed after installation, trying next URL")
            except Exception as e:
                log(f"Error downloading FFmpeg from {download_url}: {str(e)}")
                # Continue to next URL
        
        # If we got here, all URLs failed
        log("All FFmpeg download attempts failed")
        messagebox.showerror("Error", 
            "Failed to download FFmpeg. You may need to install it manually.\n"
            "Please visit: https://ffmpeg.org/download.html")
        return None
            
    except Exception as e:
        log(f"Error downloading FFmpeg: {str(e)}")
        return None
    finally:
        if message_label:
            hide_loading(message_label)

def show_loading(message="Loading..."):
    """Show a loading animation with a message."""
    global loading_gif, loading_label
    try:
        if loading_gif is None:
            loading_gif = create_loading_icon()
        
        if loading_label is None:
            loading_label = tk.Label(root, bg=THEME['bg'])
            loading_label.place(relx=0.5, rely=0.5, anchor='center')
        
        loading_label.config(text=message)
        update_loading_animation()
        return loading_label
    except:
        return None

def hide_loading(label=None):
    """Hide the loading animation."""
    global loading_label
    try:
        if label:
            label.place_forget()
        elif loading_label:
            loading_label.place_forget()
        loading_label = None
    except:
        pass

def create_progress_hook():
    """Create a progress hook for yt-dlp."""
    def progress_hook(d):
        if download_cancelled:
            # Raise an exception to stop the download
            raise yt_dlp.utils.DownloadError("Download cancelled by user")
            
        if d['status'] == 'downloading':
            try:
                # Calculate download progress
                total = d.get('total_bytes', 0) or d.get('total_bytes_estimate', 0)
                downloaded = d.get('downloaded_bytes', 0)
                
                if total > 0:
                    percent = (downloaded / total) * 100
                    speed = d.get('speed', 0)
                    if speed:
                        eta = d.get('eta', 0)
                        speed_str = f"{speed/1024/1024:.1f} MB/s"
                        eta_str = f"ETA: {eta//60}m {eta%60}s"
                        message = f"Downloading: {percent:.1f}% | Speed: {speed_str} | {eta_str}"
                    else:
                        message = f"Downloading: {percent:.1f}%"
                    
                    # Update progress bar and label through the UI queue
                    ui_queue.put(lambda: update_progress(percent, message))
                    log(message)
            except Exception as e:
                log(f"Progress error: {str(e)}")
        
        elif d['status'] == 'finished':
            if not download_cancelled:
                ui_queue.put(lambda: update_progress(100, "Download complete! Processing..."))
                log("Download complete! Processing video...")
        
        elif d['status'] == 'error':
            if not download_cancelled:
                error_msg = d.get('error', 'Unknown error')
                ui_queue.put(lambda: update_progress(0, f"Error occurred: {error_msg}"))
                log(f"Download error: {error_msg}")
    
    return progress_hook

def is_auto_start_enabled():
    """Check if the application is set to start automatically"""
    if IS_WINDOWS and WINREG_AVAILABLE:
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run", 0, winreg.KEY_READ)
            try:
                winreg.QueryValueEx(key, "Video Downloader")
                return True
            except (WindowsError, FileNotFoundError):
                return False
            finally:
                key.Close()
        except Exception as e:
            print(f"Error checking auto-start: {e}")
            return False
    elif IS_LINUX:
        # Check for .desktop file in autostart directory
        autostart_dir = Path.home() / ".config" / "autostart"
        desktop_file = autostart_dir / "media-downloader.desktop"
        return desktop_file.exists()
    else:
        return False

def toggle_auto_start():
    """Toggle auto-start (Windows: registry, Linux: .desktop file)"""
    if IS_WINDOWS and WINREG_AVAILABLE:
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run", 0, winreg.KEY_SET_VALUE)
            if auto_start_var.get():
                # Get the path to the Python executable and the script
                python_path = sys.executable
                script_path = os.path.abspath(__file__)
                # Create the command to run the script
                command = f'"{python_path}" "{script_path}"'
                winreg.SetValueEx(key, "Video Downloader", 0, winreg.REG_SZ, command)
                print("Auto-start enabled")
            else:
                try:
                    winreg.DeleteValue(key, "Video Downloader")
                    print("Auto-start disabled")
                except (WindowsError, FileNotFoundError):
                    pass
            key.Close()
        except Exception as e:
            print(f"Error toggling auto-start: {e}")
    elif IS_LINUX:
        autostart_dir = Path.home() / ".config" / "autostart"
        autostart_dir.mkdir(parents=True, exist_ok=True)
        desktop_file = autostart_dir / "media-downloader.desktop"
        
        if auto_start_var.get():
            # Create .desktop file
            python_path = sys.executable
            script_path = os.path.abspath(__file__)
            icon_path = str(ICON_PATH) if ICON_PATH.exists() else ""
            
            desktop_content = f"""[Desktop Entry]
Type=Application
Name=Media Downloader
Exec={python_path} {script_path}
Icon={icon_path}
Terminal=false
Categories=Utility;
"""
            try:
                with open(desktop_file, 'w') as f:
                    f.write(desktop_content)
                # Make executable
                os.chmod(desktop_file, 0o755)
                print("Auto-start enabled (Linux)")
            except Exception as e:
                print(f"Error creating .desktop file: {e}")
        else:
            # Remove .desktop file
            try:
                if desktop_file.exists():
                    desktop_file.unlink()
                print("Auto-start disabled (Linux)")
            except Exception as e:
                print(f"Error removing .desktop file: {e}")
    else:
        messagebox.showinfo("Auto-start", "Auto-start is not supported on this platform.")

def debug_update_check():
    """Debug function to check update system status"""
    try:
        log("\n=== DEBUG: Update System Status ===")
        
        # Check repository configuration
        log(f"\nRepository Configuration:")
        log(f"Owner: {REPO_OWNER}")
        log(f"Name: {REPO_NAME}")
        log(f"API URL: {GITHUB_API_URL}")
        log(f"Current Version: {CURRENT_VERSION}")
        
        # Check update check file
        log(f"\nUpdate Check File Status:")
        if UPDATE_CHECK_FILE.exists():
            with open(UPDATE_CHECK_FILE, 'r') as f:
                last_check = float(f.read().strip())
                time_since_last_check = time.time() - last_check
                log(f"Last check: {time.ctime(last_check)}")
                log(f"Time since last check: {time_since_last_check/3600:.2f} hours")
        else:
            log("Update check file not found")
        
        # Test GitHub API connection
        log(f"\nTesting GitHub API Connection:")
        try:
            headers = {
                'Accept': 'application/vnd.github.v3+json',
                'User-Agent': 'Yamin-media-downloader'
            }
            response = requests.get(GITHUB_API_URL, headers=headers)
            log(f"API Response Status: {response.status_code}")
            
            if response.status_code == 200:
                latest_release = response.json()
                latest_version = latest_release.get('tag_name', '').lstrip('v')
                log(f"Latest Release: {latest_version}")
                log(f"Release Details: {json.dumps(latest_release, indent=2)}")
            else:
                log(f"API Error: {response.text}")
        except Exception as e:
            log(f"API Connection Error: {str(e)}")
        
        # Test version comparison
        log(f"\nTesting Version Comparison:")
        test_versions = [
            ("1.0.15", "1.0.14")
        ]
        for v1, v2 in test_versions:
            result = compare_versions(v1, v2)
            log(f"Compare {v1} > {v2}: {result}")
        
        log("\n=== DEBUG COMPLETED ===\n")
        
    except Exception as e:
        log(f"Debug Error: {str(e)}")

# Create main window
root = tk.Tk()
root.title("Media Downloader")
root.geometry("800x700")
root.minsize(600, 500)  # Set minimum window size
root.configure(bg=THEME['bg'])

# Ensure window is visible immediately
root.deiconify()
root.lift()
root.focus_force()
root.update()  # Force window to appear

# Quality settings variables
video_quality_var = tk.StringVar(value='best')
audio_quality_var = tk.StringVar(value='320')
format_var = tk.StringVar(value='mp4')

# Create auto-start variable
auto_start_var = tk.BooleanVar(value=is_auto_start_enabled())

def update_quality_settings(quality_type, value):
    """Update quality settings and log the change."""
    global quality_settings
    if quality_type in quality_settings:
        quality_settings[quality_type] = value
        log(f"Updated {quality_type} to: {value}")
        # Update status label to show current settings
        if 'status_label' in globals():
            status_label.config(text=f"Quality settings updated: {quality_type}={value}")

def on_video_quality_change(*args):
    value = video_quality_var.get()
    quality_settings['video_quality'] = value
    log(f"Video quality changed to: {value}")
    update_quality_settings('video_quality', value)

def on_audio_quality_change(*args):
    value = audio_quality_var.get()
    quality_settings['audio_quality'] = value
    log(f"Audio quality changed to: {value}")
    update_quality_settings('audio_quality', value)

def on_format_change(*args):
    value = format_var.get()
    quality_settings['format'] = value
    log(f"Format changed to: {value}")
    update_quality_settings('format', value)

def threaded_download(is_audio):
    """Start download in a separate thread."""
    global current_download_thread
    def download_thread():
        try:
            disable_buttons()
            download_media(is_audio)
        finally:
            enable_buttons()
            current_download_thread = None
    
    # Start the download in a new thread
    current_download_thread = threading.Thread(target=download_thread, daemon=True)
    current_download_thread.start()

def enable_buttons():
    """Enable the download buttons."""
    try:
        if 'video_btn' in globals():
            video_btn.config(state='normal')
            video_btn.grid()  # Ensure button is visible
        if 'audio_btn' in globals():
            audio_btn.config(state='normal')
            audio_btn.grid()  # Ensure button is visible
        if 'cancel_btn' in globals():
            cancel_btn.grid_remove()  # Hide cancel button
    except:
        pass

def disable_buttons():
    """Disable the download buttons."""
    try:
        if 'video_btn' in globals():
            video_btn.config(state='disabled')
            video_btn.grid()  # Keep button visible but disabled
        if 'audio_btn' in globals():
            audio_btn.config(state='disabled')
            audio_btn.grid()  # Keep button visible but disabled
        if 'cancel_btn' in globals():
            cancel_btn.grid()  # Show cancel button
    except:
        pass

def should_check_for_updates():
    """Determine if we should check for updates (once per day)."""
    global FORCE_UPDATE_CHECK
    try:
        log("Checking if update check is needed...")
        
        # If force check is enabled, always check
        if FORCE_UPDATE_CHECK:
            log("Force update check enabled, will check for updates")
            return True
            
        if not UPDATE_CHECK_FILE.exists():
            log("Update check file not found, will check for updates")
            return True
        
        # Read last check time
        with open(UPDATE_CHECK_FILE, 'r') as f:
            last_check = float(f.read().strip())
        
        time_since_last_check = time.time() - last_check
        log(f"Time since last check: {time_since_last_check/3600:.2f} hours")
        
        # Check if 24 hours have passed
        should_check = time_since_last_check >= 86400  # 24 hours in seconds
        log(f"Should check for updates: {should_check}")
        return should_check
    except Exception as e:
        log(f"Error checking update timestamp: {e}")
        return True

def update_check_timestamp():
    """Update the timestamp of last update check."""
    try:
        UPDATE_CHECK_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(UPDATE_CHECK_FILE, 'w') as f:
            f.write(str(time.time()))
    except:
        pass

def compare_versions(v1, v2):
    """Compare two version strings and return True if v1 > v2."""
    try:
        print(f"Comparing versions: '{v1}' > '{v2}'")
        # Ensure we have strings
        v1 = str(v1).strip()
        v2 = str(v2).strip()
        
        # Edge cases
        if v1 == v2:
            return False
        if not v1:
            return False
        if not v2:
            return True
        
        def parse_version(v):
            # Remove prefix like 'v'
            if v.lower().startswith('v'):
                v = v[1:]
                
            # Remove any non-numeric and non-dot characters
            v = ''.join(c for c in v if c.isdigit() or c == '.')
            
            # Handle empty string case
            if not v:
                return [0]
                
            # Split into parts and convert to integers
            parts = []
            for part in v.split('.'):
                try:
                    parts.append(int(part))
                except ValueError:
                    parts.append(0)
            return parts
        
        v1_parts = parse_version(v1)
        v2_parts = parse_version(v2)
        
        # Pad with zeros to make lengths equal
        max_len = max(len(v1_parts), len(v2_parts))
        v1_parts.extend([0] * (max_len - len(v1_parts)))
        v2_parts.extend([0] * (max_len - len(v2_parts)))
        
        print(f"Parsed versions: {v1_parts} > {v2_parts}")
        
        # Do the comparison
        for i in range(max_len):
            if v1_parts[i] > v2_parts[i]:
                print(f"Result: {v1} is newer than {v2}")
                return True
            elif v1_parts[i] < v2_parts[i]:
                print(f"Result: {v1} is older than {v2}")
                return False
                
        # They're equal
        print(f"Result: {v1} is the same as {v2}")
        return False
    except Exception as e:
        print(f"Error comparing versions: {e}")
        # If there's an error, assume the versions are the same
        return False

def check_updates_on_startup():
    """Check for updates when the application starts"""
    global FORCE_UPDATE_CHECK
    try:
        # Ensure window is visible before showing any dialogs
        try:
            root.deiconify()
            root.lift()
            root.focus_force()
        except:
            pass
        
        log("\n=== Update Check Process Started ===")
        print("\n=== UPDATE CHECK PROCESS STARTED ===")
        
        # Always check for application updates when manually initiated
        log("Starting application update check...")
        latest_release = check_for_updates()
        
        if latest_release:
            latest_version = latest_release.get('tag_name', '').lstrip('v')
            log(f"New version {latest_version} available!")
            
            # Ensure window is visible before showing dialog
            try:
                root.deiconify()
                root.lift()
                root.focus_force()
            except:
                pass
            
            if messagebox.askyesno("Update Available", 
                                 f"Version {latest_version} is available. Would you like to update now?"):
                log("User chose to update")
                download_and_install_update(latest_release)
            else:
                log("User chose not to update")
        else:
            if FORCE_UPDATE_CHECK:
                # Only show the "no updates" message if the user manually checked
                # Ensure window is visible
                try:
                    root.deiconify()
                    root.lift()
                    root.focus_force()
                except:
                    pass
                messagebox.showinfo("No Updates", "You have the latest version.")
            log("No updates available")
        
        # Always update the timestamp
        update_check_timestamp()
            
        # Check for FFmpeg updates (non-blocking)
        def check_ffmpeg_async():
            try:
                log("Starting FFmpeg update check...")
                check_ffmpeg_update()
            except Exception as e:
                log(f"Error checking FFmpeg updates: {e}")
        
        # Run FFmpeg check in background thread to avoid blocking
        threading.Thread(target=check_ffmpeg_async, daemon=True).start()
        
        log("=== Update Check Process Completed ===\n")
        print("=== UPDATE CHECK PROCESS COMPLETED ===\n")
        
    except Exception as e:
        log(f"Error in update check process: {str(e)}")
        print(f"Error in update check process: {str(e)}")
        print(traceback.format_exc())
        
        if FORCE_UPDATE_CHECK:
            # Show error message if user manually checked
            try:
                root.deiconify()
                root.lift()
                root.focus_force()
            except:
                pass
            messagebox.showerror("Update Check Failed", 
                               f"Failed to check for updates: {str(e)}\n\n"
                               "Please check your internet connection.")
    
    # Reset force flag after check
    FORCE_UPDATE_CHECK = False

def check_for_updates():
    """Check for updates on GitHub and return the latest version if available."""
    try:
        log("=== Starting Update Check ===")
        print("\n=== CHECKING FOR UPDATES ===")
        print(f"Current version: {CURRENT_VERSION}")
        print(f"GitHub API URL: {GITHUB_API_URL}")
        print(f"Repository: {REPO_OWNER}/{REPO_NAME}")
        
        # Make the request with headers to avoid rate limiting
        headers = {
            'Accept': 'application/vnd.github.v3+json',
            'User-Agent': f'Yamin-media-downloader/{CURRENT_VERSION}'
        }
        
        print("Sending request to GitHub API...")
        response = requests.get(GITHUB_API_URL, headers=headers, timeout=10)
        log(f"GitHub API Response Status: {response.status_code}")
        print(f"GitHub API Response Status: {response.status_code}")
        
        if response.status_code != 200:
            log(f"GitHub API Error: {response.text}")
            print(f"GitHub API Error: {response.text}")
            return None
            
        latest_release = response.json()
        
        # Check if there's a valid release
        if 'tag_name' not in latest_release:
            log("No tag_name found in release")
            print("No tag_name found in GitHub response")
            return None
            
        # Get the latest version number (strip v prefix if present)
        latest_version = latest_release.get('tag_name', '').lstrip('v')
        log(f"Latest version on GitHub: {latest_version}")
        print(f"Latest version on GitHub: {latest_version}")
        
        if not latest_version:
            log("Empty version tag found in release")
            print("Empty version tag found in release")
            return None
            
        # Compare versions with detailed logging
        print(f"\n=== VERSION COMPARISON DETAILS ===")
        print(f"Current version: {CURRENT_VERSION}")
        print(f"Latest version: {latest_version}")
        print(f"Comparison result: {compare_versions(latest_version, CURRENT_VERSION)}")
        
        if compare_versions(latest_version, CURRENT_VERSION):
            log(f"New version {latest_version} is available!")
            print(f"✅ New version {latest_version} is available!")
            # Return the entire release data for use in download_and_install_update
            return latest_release
        else:
            log("You have the latest version")
            print("✓ You have the latest version")
            return None
    except requests.exceptions.RequestException as e:
        log(f"Network error checking for updates: {e}")
        print(f"Network error checking for updates: {e}")
        return None
    except Exception as e:
        log(f"Unexpected error checking for updates: {e}")
        print(f"Unexpected error checking for updates: {e}")
        print(traceback.format_exc())
        return None

def download_and_install_update(release):
    """Download and install the latest release."""
    try:
        print("\n=== DOWNLOADING UPDATE ===")
        
        # If release is a string (legacy calls), convert to new format
        if isinstance(release, str):
            print(f"Converting legacy version string: {release}")
            latest_version = release
            # We need to fetch the release data
            headers = {
                'Accept': 'application/vnd.github.v3+json',
                'User-Agent': f'Yamin-media-downloader/{CURRENT_VERSION}'
            }
            response = requests.get(GITHUB_API_URL, headers=headers, timeout=10)
            if response.status_code != 200:
                raise Exception(f"Could not fetch release data: {response.status_code}")
            release = response.json()
        else:
            latest_version = release.get('tag_name', '').lstrip('v')
        
        print(f"Preparing to download version {latest_version}")
        
        # Find the asset with appropriate extension (Windows: .exe, Linux: .AppImage or .deb, Mac: .dmg)
        assets = release.get('assets', [])
        print(f"Release has {len(assets)} assets")
        
        exe_asset = None
        if IS_WINDOWS:
            # Windows: look for .exe
            for asset in assets:
                print(f"Asset: {asset.get('name')} ({asset.get('content_type')})")
                if asset.get('name', '').lower().endswith('.exe'):
                    exe_asset = asset
                    break
        elif IS_LINUX:
            # Linux: look for .AppImage or .deb
            for asset in assets:
                print(f"Asset: {asset.get('name')} ({asset.get('content_type')})")
                name_lower = asset.get('name', '').lower()
                if name_lower.endswith('.appimage') or name_lower.endswith('.deb'):
                    exe_asset = asset
                    break
        else:  # macOS
            # macOS: look for .dmg or .app
            for asset in assets:
                print(f"Asset: {asset.get('name')} ({asset.get('content_type')})")
                name_lower = asset.get('name', '').lower()
                if name_lower.endswith('.dmg') or name_lower.endswith('.app'):
                    exe_asset = asset
                    break
                
        if not exe_asset:
            raise Exception(f"No suitable executable found in release assets for {platform.system()}")
        
        # Create temporary directory for download
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            exe_path = temp_path / exe_asset['name']
            
            # Download the new version
            download_url = exe_asset['browser_download_url']
            print(f"Downloading from: {download_url}")
            log("Downloading update...")
            
            # Show a message to inform the user that download is in progress
            messagebox.showinfo("Downloading Update", 
                               f"Downloading version {latest_version}...\n\n"
                               "The application will restart automatically when the update is complete.")
            
            # Download with progress tracking
            response = requests.get(download_url, stream=True)
            response.raise_for_status()
            
            total_size = int(response.headers.get('content-length', 0))
            downloaded = 0
            
            with open(exe_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    downloaded += len(chunk)
                    f.write(chunk)
                    # Calculate and print progress
                    if total_size > 0:
                        percent = (downloaded / total_size) * 100
                        if percent % 10 < 1:  # Print every ~10%
                            print(f"Download progress: {percent:.1f}% ({downloaded}/{total_size} bytes)")
            
            print(f"Download complete: {exe_path}")
            
            # Create update script that will:
            # 1. Wait for this process to exit
            # 2. Delete the current executable
            # 3. Move the new executable in place
            # 4. Start the new version
            update_script = temp_path / "update.bat"
            current_exe = sys.executable
            
            print(f"Creating update script at: {update_script}")
            print(f"Current executable: {current_exe}")
            
            with open(update_script, 'w') as f:
                f.write(f"""@echo off
echo Waiting for application to close...
timeout /t 2 /nobreak
echo Updating Media Downloader...
del "{current_exe}"
if exist "{current_exe}" (
    echo Retrying with force delete...
    taskkill /f /im "{os.path.basename(current_exe)}" 2>nul
    timeout /t 1 /nobreak
    del /f "{current_exe}"
)
echo Copying new version...
copy "{exe_path}" "{current_exe}"
if exist "{current_exe}" (
    echo Starting new version...
    start "" "{current_exe}"
) else (
    echo ERROR: Failed to copy new version.
    pause
)
""")
            
            print("Running update script...")
            # Run update script and exit
            subprocess.Popen([str(update_script)], shell=True)
            time.sleep(1)  # Give it a moment to start
            print("Exiting for update...")
            sys.exit(0)
            
    except Exception as e:
        error_msg = str(e)
        log(f"Error installing update: {error_msg}")
        print(f"Error installing update: {error_msg}")
        print(traceback.format_exc())
        messagebox.showerror("Update Error", f"Failed to install update: {error_msg}")
        return False

def check_ffmpeg_update():
    """Check for FFmpeg updates."""
    try:
        # Get the current FFmpeg version (Windows only for auto-update)
        if not IS_WINDOWS:
            return  # Auto-update only on Windows, Linux/Mac use package managers
        
        ffmpeg_dir = INSTALL_DIR / "ffmpeg"
        ffmpeg_exe = "ffmpeg.exe" if IS_WINDOWS else "ffmpeg"
        ffmpeg_path = ffmpeg_dir / ffmpeg_exe
        
        if not ffmpeg_path.exists():
            return
            
        subprocess_kwargs = {}
        if IS_WINDOWS:
            subprocess_kwargs['creationflags'] = subprocess.CREATE_NO_WINDOW
        else:
            subprocess_kwargs['stdout'] = subprocess.DEVNULL
            subprocess_kwargs['stderr'] = subprocess.DEVNULL
        
        result = subprocess.run([str(ffmpeg_path), '-version'], 
                              capture_output=True, 
                              text=True,
                              **subprocess_kwargs)
        if result.returncode != 0:
            return
            
        # Check GitHub for latest FFmpeg version
        log("Checking for FFmpeg updates...")
        response = requests.get("https://api.github.com/repos/BtbN/FFmpeg-Builds/releases/latest")
        response.raise_for_status()
        latest_release = response.json()
        
        # If there's a new version, download it
        if latest_release.get('tag_name'):
            log("New FFmpeg version available. Starting download...")
            # The download_ffmpeg function will handle its own loading animation
            download_ffmpeg()
            
    except Exception as e:
        log(f"Error checking FFmpeg updates: {str(e)}")

# Create menubar
menubar = tk.Menu(root)
root.config(menu=menubar)

# File Menu
file_menu = tk.Menu(menubar, tearoff=0)
menubar.add_cascade(label="File", menu=file_menu)
def open_download_folder():
    """Open download folder (cross-platform)"""
    try:
        folder_path = str(downloads_path.resolve())
        if IS_WINDOWS:
            os.startfile(folder_path)
        elif IS_LINUX:
            subprocess.Popen(['xdg-open', folder_path])
        elif IS_MAC:
            subprocess.Popen(['open', folder_path])
        else:
            webbrowser.open(f"file://{folder_path}")
    except Exception as e:
        log(f"Error opening folder: {str(e)}")
        messagebox.showerror("Error", f"Could not open folder: {str(e)}")

file_menu.add_command(label="Open Download Folder", command=open_download_folder)
file_menu.add_checkbutton(label="Auto-start", variable=auto_start_var, command=toggle_auto_start)
file_menu.add_separator()
file_menu.add_command(label="Exit", command=root.quit)

# Settings Menu
settings_menu = tk.Menu(menubar, tearoff=0)
menubar.add_cascade(label="Settings", menu=settings_menu)

# Video Quality Submenu
video_quality_menu = tk.Menu(settings_menu, tearoff=0)
settings_menu.add_cascade(label="Video Quality", menu=video_quality_menu)
video_quality_menu.add_radiobutton(label="Best Quality", variable=video_quality_var, value='best', command=lambda: on_video_quality_change())
video_quality_menu.add_radiobutton(label="1080p", variable=video_quality_var, value='1080', command=lambda: on_video_quality_change())
video_quality_menu.add_radiobutton(label="720p", variable=video_quality_var, value='720', command=lambda: on_video_quality_change())
video_quality_menu.add_radiobutton(label="480p", variable=video_quality_var, value='480', command=lambda: on_video_quality_change())
video_quality_menu.add_radiobutton(label="360p", variable=video_quality_var, value='360', command=lambda: on_video_quality_change())

# Audio Quality Submenu
audio_quality_menu = tk.Menu(settings_menu, tearoff=0)
settings_menu.add_cascade(label="Audio Quality", menu=audio_quality_menu)
audio_quality_menu.add_radiobutton(label="320 kbps", variable=audio_quality_var, value='320', command=lambda: on_audio_quality_change())
audio_quality_menu.add_radiobutton(label="256 kbps", variable=audio_quality_var, value='256', command=lambda: on_audio_quality_change())
audio_quality_menu.add_radiobutton(label="192 kbps", variable=audio_quality_var, value='192', command=lambda: on_audio_quality_change())
audio_quality_menu.add_radiobutton(label="128 kbps", variable=audio_quality_var, value='128', command=lambda: on_audio_quality_change())
audio_quality_menu.add_radiobutton(label="96 kbps", variable=audio_quality_var, value='96', command=lambda: on_audio_quality_change())

# Format Submenu
format_menu = tk.Menu(settings_menu, tearoff=0)
settings_menu.add_cascade(label="Format", menu=format_menu)
format_menu.add_radiobutton(label="MP4", variable=format_var, value='mp4', command=lambda: on_format_change())
format_menu.add_radiobutton(label="WebM", variable=format_var, value='webm', command=lambda: on_format_change())
format_menu.add_radiobutton(label="MKV", variable=format_var, value='mkv', command=lambda: on_format_change())

# Help Menu
help_menu = tk.Menu(menubar, tearoff=0)
menubar.add_cascade(label="Help", menu=help_menu)
help_menu.add_command(label="About", command=lambda: messagebox.showinfo("About", 
    "Media Downloader v" + CURRENT_VERSION + "\n\n" +
    "Created by Md Yamin Hossain\n" +
    "GitHub: https://github.com/needyamin\n\n" +
    "A powerful media downloader supporting multiple platforms."))
help_menu.add_command(label="Check for Updates", command=lambda: force_check_updates())
help_menu.add_separator()
help_menu.add_command(label="Report Issue", 
    command=lambda: webbrowser.open("https://github.com/needyamin/media-downloader/issues"))

# Add debug command to Help menu
help_menu.add_separator()
help_menu.add_command(label="Debug Update System", command=debug_update_check)

# Add function to force update check
def force_check_updates():
    """Force check for updates when user clicks menu item"""
    global FORCE_UPDATE_CHECK
    FORCE_UPDATE_CHECK = True
    log("Forcing update check...")
    print("\n=== FORCING UPDATE CHECK ===")
    check_updates_on_startup()

# Custom Widget Classes
class ModernButton(ttk.Button):
    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        self.configure(style='Modern.TButton')

class ModernEntry(tk.Entry):
    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        self.configure(
            relief='flat',
            font=('Segoe UI', 10),
            bg=THEME['light_gray'],
            fg=THEME['fg'],
            insertbackground=THEME['primary']
        )
        self.bind('<FocusIn>', self.on_focus_in)
        self.bind('<FocusOut>', self.on_focus_out)
        
    def on_focus_in(self, e):
        self.configure(bg='white')
        
    def on_focus_out(self, e):
        self.configure(bg=THEME['light_gray'])

class ModernCheckbutton(tk.Checkbutton):
    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        self.configure(
            bg=THEME['bg'],
            fg=THEME['fg'],
            activebackground=THEME['bg'],
            activeforeground=THEME['primary'],
            selectcolor=THEME['light_gray'],
            font=('Segoe UI', 10)
        )

# Create a queue for thread-safe UI updates
ui_queue = queue.Queue()

def log(message, show_console=True):
    """Log a message to the output box and status label if available, or queue it for later."""
    try:
        if show_console:
            print(f"[Yamin Downloader] {message}")  # Always show in console
        if 'output_box' in globals() and 'status_label' in globals():
            output_box.config(state='normal')
            # Insert at the beginning (index 1.0) instead of the end
            output_box.insert('1.0', message + '\n')
            # Auto-scroll to the top
            output_box.see('1.0')
            output_box.config(state='disabled')
            status_label.config(text=message)
        else:
            early_log_queue.put(message)
    except:
        print(f"[Yamin Downloader] {message}")  # Fallback to console output

def process_early_logs():
    """Process any queued log messages once the GUI is ready."""
    while not early_log_queue.empty():
        try:
            message = early_log_queue.get_nowait()
            if 'output_box' in globals() and 'status_label' in globals():
                output_box.config(state='normal')
                # Insert at the beginning (index 1.0) instead of the end
                output_box.insert('1.0', message + '\n')
                # Auto-scroll to the top
                output_box.see('1.0')
                output_box.config(state='disabled')
                status_label.config(text=message)
        except queue.Empty:
            break

# Set window icon
if ICON_PATH.exists():
    try:
        root.iconbitmap(str(ICON_PATH))
    except Exception as e:
        messagebox.showwarning("Icon Error", f"Could not load window icon: {e}")

# Make window resizable
root.resizable(True, True)

# Configure grid weights for responsive layout
root.grid_rowconfigure(0, weight=1)
root.grid_columnconfigure(0, weight=1)

# Create main container
main_container = tk.Frame(root, bg=THEME['bg'])
main_container.grid(row=0, column=0, sticky="nsew", padx=20, pady=20)
main_container.grid_rowconfigure(1, weight=1)
main_container.grid_columnconfigure(0, weight=1)

# Header Frame
header_frame = tk.Frame(main_container, bg=THEME['bg'])
header_frame.grid(row=0, column=0, sticky="ew", pady=(0, 20))

# Logo and Title
try:
    logo = Image.open(ICON_PATH)
    logo = logo.resize((48, 48), Image.Resampling.LANCZOS)
    logo_photo = ImageTk.PhotoImage(logo)
    logo_label = tk.Label(header_frame, image=logo_photo, bg=THEME['bg'])
    logo_label.image = logo_photo
    logo_label.pack(side='left', padx=(0, 10))
except:
    pass

title_label = tk.Label(
    header_frame,
    text="Media Downloader",
    font=('Segoe UI', 24, 'bold'),
    bg=THEME['bg'],
    fg=THEME['primary']
)
title_label.pack(side='left')

version_label = tk.Label(
    header_frame,
    text=f"v{CURRENT_VERSION}",
    font=('Segoe UI', 10),
    bg=THEME['bg'],
    fg=THEME['gray']
)
version_label.pack(side='left', padx=(10, 0), pady=(10, 0))

# Main Content Frame
main_frame = tk.Frame(main_container, bg=THEME['bg'])
main_frame.grid(row=1, column=0, sticky="nsew")
main_frame.grid_rowconfigure(3, weight=1)
main_frame.grid_columnconfigure(0, weight=1)

# URL Input Section
url_frame = tk.Frame(main_frame, bg=THEME['bg'])
url_frame.grid(row=0, column=0, sticky="ew", pady=(0, 20))
url_frame.grid_columnconfigure(0, weight=1)  # Make the URL entry expand

url_label = tk.Label(
    url_frame,
    text="Enter Media URL:",
    font=('Segoe UI', 12, 'bold'),
    bg=THEME['bg'],
    fg=THEME['fg']
)
url_label.grid(row=0, column=0, sticky="w", pady=(0, 5))

url_entry = ModernEntry(url_frame)
url_entry.grid(row=1, column=0, sticky="ew", ipady=8)

# Status Label
status_label = tk.Label(
    main_frame,
    text="Initializing...",
    font=('Segoe UI', 9),
    bg=THEME['border'],
    fg=THEME['fg']
)
status_label.grid(row=1, column=0, sticky="w", padx=10, pady=(0, 10))

# Process any early logs
process_early_logs()

# Initialize FFmpeg in a separate thread
def initialize_ffmpeg():
    """Initialize FFmpeg and FFprobe."""
    global ffmpeg_path, ffprobe_path
    try:
        # Debug the FFmpeg initialization
        print("\n=== INITIALIZING FFMPEG ===")
        print(f"Current ffmpeg_path: {ffmpeg_path}")
        
        # Try to find FFmpeg in expected locations first
        if not ffmpeg_path or not os.path.exists(ffmpeg_path):
            # Look in common FFmpeg locations (platform-specific)
            if IS_WINDOWS:
                potential_paths = [
                    INSTALL_DIR / "ffmpeg" / "ffmpeg.exe",
                    Path(os.environ.get("PROGRAMFILES", "")) / "ffmpeg" / "bin" / "ffmpeg.exe",
                    Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "ffmpeg" / "bin" / "ffmpeg.exe",
                    Path(APP_DIR) / "ffmpeg" / "ffmpeg.exe"
                ]
            elif IS_LINUX:
                potential_paths = [
                    INSTALL_DIR / "ffmpeg" / "ffmpeg",
                    Path("/usr/bin/ffmpeg"),
                    Path("/usr/local/bin/ffmpeg"),
                    Path.home() / ".local" / "bin" / "ffmpeg",
                    Path(APP_DIR) / "ffmpeg" / "ffmpeg"
                ]
            else:  # macOS
                potential_paths = [
                    INSTALL_DIR / "ffmpeg" / "ffmpeg",
                    Path("/usr/local/bin/ffmpeg"),
                    Path("/opt/homebrew/bin/ffmpeg"),
                    Path(APP_DIR) / "ffmpeg" / "ffmpeg"
                ]
            
            print("Searching for existing FFmpeg installation...")
            for path in potential_paths:
                print(f"Checking: {path}")
                if path.exists():
                    print(f"Found existing FFmpeg at: {path}")
                    ffmpeg_path = str(path)
                    # Find ffprobe in same directory
                    if IS_WINDOWS:
                        ffprobe_path = str(path.parent / "ffprobe.exe")
                    else:
                        ffprobe_path = str(path.parent / "ffprobe")
                    break
        
        # Try to download FFmpeg if not already installed
        if not ffmpeg_path or not os.path.exists(ffmpeg_path):
            # Verify existing installation if found
            if ffmpeg_path and os.path.exists(ffmpeg_path):
                if IS_WINDOWS:
                    test_ffprobe = str(Path(ffmpeg_path).parent / "ffprobe.exe")
                else:
                    test_ffprobe = str(Path(ffmpeg_path).parent / "ffprobe")
                if not verify_ffmpeg(ffmpeg_path, test_ffprobe):
                    ffmpeg_path = None
            
            if not ffmpeg_path:
                print("No working FFmpeg found, attempting to download...")
                ffmpeg_path = download_ffmpeg()
                if not ffmpeg_path or not os.path.exists(ffmpeg_path):
                    raise Exception("Failed to download FFmpeg")
        
        # Find ffprobe in same directory as ffmpeg
        if IS_WINDOWS:
            ffprobe_path = str(Path(ffmpeg_path).parent / "ffprobe.exe")
        else:
            ffprobe_path = str(Path(ffmpeg_path).parent / "ffprobe")
        print(f"Final ffmpeg_path: {ffmpeg_path}")
        print(f"Final ffprobe_path: {ffprobe_path}")
        
        # Configure yt-dlp to use both FFmpeg and FFprobe
        yt_dlp.postprocessor.ffmpeg.FFmpegPostProcessor.EXES = {
            'ffmpeg': ffmpeg_path,
            'ffprobe': ffprobe_path,
        }
        
        # Print the actual FFmpeg path that yt-dlp will use
        print(f"yt-dlp FFmpeg path: {yt_dlp.postprocessor.ffmpeg.FFmpegPostProcessor.EXES.get('ffmpeg')}")
        
        # Verify installation
        if not verify_ffmpeg(ffmpeg_path, ffprobe_path):
            raise Exception("FFmpeg verification failed after initialization")
        
        # Verify output directories
        verify_output_directories()
        
        # Update status
        log("Initialization complete. Ready to download!")
        status_label.config(text="Ready to download")
    except Exception as e:
        log(f"Error initializing FFmpeg: {str(e)}")
        print(f"Error initializing FFmpeg: {str(e)}")
        print(traceback.format_exc())
        status_label.config(text="Error: FFmpeg initialization failed")

def verify_output_directories():
    """Verify that output directories exist and create them if they don't."""
    try:
        log("Verifying output directories...")
        print("\n=== VERIFYING OUTPUT DIRECTORIES ===")
        
        # Check for invalid characters in paths (Windows restrictions)
        invalid_chars = ['<', '>', ':', '"', '/', '\\', '|', '?', '*']
        for path in [downloads_path, video_output_dir, audio_output_dir, playlist_output_dir]:
            path_str = str(path)
            print(f"Checking path: {path_str}")
            
            # Check for invalid characters in path
            has_invalid = any(char in path_str for char in invalid_chars)
            if has_invalid:
                print(f"WARNING: Path contains invalid characters: {path_str}")
            
            # Check for long path issues (Windows MAX_PATH is 260 chars)
            if len(path_str) > 240:  # Leave some room for filenames
                print(f"WARNING: Path is very long ({len(path_str)} chars): {path_str}")
        
        # Ensure the main download directory exists
        if not downloads_path.exists():
            log(f"Creating main download directory: {downloads_path}")
            print(f"Creating main download directory: {downloads_path}")
            downloads_path.mkdir(parents=True, exist_ok=True)
        
        # Ensure the video directory exists
        if not video_output_dir.exists():
            log(f"Creating video output directory: {video_output_dir}")
            print(f"Creating video output directory: {video_output_dir}")
            video_output_dir.mkdir(parents=True, exist_ok=True)
        
        # Ensure the audio directory exists
        if not audio_output_dir.exists():
            log(f"Creating audio output directory: {audio_output_dir}")
            print(f"Creating audio output directory: {audio_output_dir}")
            audio_output_dir.mkdir(parents=True, exist_ok=True)
        
        # Ensure the playlist directory exists
        if not playlist_output_dir.exists():
            log(f"Creating playlist output directory: {playlist_output_dir}")
            print(f"Creating playlist output directory: {playlist_output_dir}")
            playlist_output_dir.mkdir(parents=True, exist_ok=True)
        
        # Test write permissions
        try:
            print("Testing write permissions...")
            test_files = []
            for dir_path in [video_output_dir, audio_output_dir, playlist_output_dir]:
                test_file = dir_path / "write_test.tmp"
                test_files.append(test_file)
                with open(test_file, 'w') as f:
                    f.write("write test")
            
            # Cleanup test files
            for test_file in test_files:
                if test_file.exists():
                    test_file.unlink()
            print("All directories are writable")
        except Exception as e:
            print(f"WARNING: Write permission test failed: {e}")
            print(traceback.format_exc())
            # Continue anyway, might still work
        
        log("Output directories verified and created if needed")
        print("Output directory verification complete")
        return True
    except Exception as e:
        log(f"Error verifying output directories: {str(e)}")
        print(f"Error verifying output directories: {str(e)}")
        print(traceback.format_exc())
        return False

# Start FFmpeg initialization in a separate thread
threading.Thread(target=initialize_ffmpeg, daemon=True).start()

last_copied_url = ""
tray_icon = None
tray_thread = None

# Options Frame
options_frame = tk.Frame(main_frame, bg=THEME['bg'])
options_frame.grid(row=1, column=0, sticky="ew", pady=(0, 20))
options_frame.grid_columnconfigure(0, weight=1)

# Left Options
left_options = tk.Frame(options_frame, bg=THEME['bg'])
left_options.grid(row=0, column=0, sticky="w")

download_playlist = BooleanVar()
playlist_check = ModernCheckbutton(
    left_options,
    text="Download Entire Playlist",
    variable=download_playlist,
    command=lambda: max_files_entry.configure(state='normal' if download_playlist.get() else 'disabled')
)
playlist_check.grid(row=0, column=0, padx=(0, 20))

# Right Options
right_options = tk.Frame(options_frame, bg=THEME['bg'])
right_options.grid(row=0, column=1, sticky="e")

tk.Label(
    right_options,
    text="Max Files:",
    font=('Segoe UI', 10),
    bg=THEME['bg'],
    fg=THEME['fg']
).grid(row=0, column=0, padx=(0, 5))

max_files_entry = ModernEntry(right_options, width=5)
max_files_entry.insert(0, "100")
max_files_entry.configure(state='disabled')
max_files_entry.grid(row=0, column=1)

# Buttons Frame
buttons_frame = tk.Frame(main_frame, bg=THEME['bg'])
buttons_frame.grid(row=2, column=0, sticky="ew", pady=(0, 20))
buttons_frame.grid_columnconfigure(0, weight=1)
buttons_frame.grid_columnconfigure(1, weight=1)
buttons_frame.grid_columnconfigure(2, weight=1)

video_btn = tk.Button(
    buttons_frame,
    text="Download Video",
    bg='#2196F3',
    fg='white',
    activebackground='#424242',
    activeforeground='white',
    font=('Segoe UI', 10, 'bold'),
    relief='flat',
    cursor='hand2',
    padx=20,
    pady=8,
    command=lambda: threaded_download(False)
)
video_btn.grid(row=0, column=0, padx=(0, 10), sticky="ew")

audio_btn = tk.Button(
    buttons_frame,
    text="Download Audio",
    bg='#2196F3',
    fg='white',
    activebackground='#424242',
    activeforeground='white',
    font=('Segoe UI', 10, 'bold'),
    relief='flat',
    cursor='hand2',
    padx=20,
    pady=8,
    command=lambda: threaded_download(True)
)
audio_btn.grid(row=0, column=1, sticky="ew")

# Add cancel button to buttons frame
cancel_btn = tk.Button(
    buttons_frame,
    text="Cancel Download",
    bg='#F44336',
    fg='white',
    activebackground='#424242',
    activeforeground='white',
    font=('Segoe UI', 10, 'bold'),
    relief='flat',
    cursor='hand2',
    padx=20,
    pady=8,
    command=lambda: cancel_download()
)
cancel_btn.grid(row=0, column=2, padx=(10, 0), sticky="ew")
cancel_btn.grid_remove()  # Initially hidden

# Progress Section
progress_frame = tk.Frame(main_frame, bg=THEME['bg'])
progress_frame.grid(row=3, column=0, sticky="ew", pady=(0, 20))
progress_frame.grid_columnconfigure(0, weight=1)

progress_label = tk.Label(
    progress_frame,
    text="Ready to download",
    font=('Segoe UI', 10),
    bg=THEME['bg'],
    fg=THEME['fg']
)
progress_label.grid(row=0, column=0, sticky="w", pady=(0, 5))

progress = ttk.Progressbar(
    progress_frame,
    style="Modern.Horizontal.TProgressbar",
    orient="horizontal",
    length=500,
    mode="determinate"
)
progress.grid(row=1, column=0, sticky="ew")

# Output Display
output_frame = tk.Frame(main_frame, bg=THEME['bg'])
output_frame.grid(row=4, column=0, sticky="nsew", pady=(0, 20))
output_frame.grid_rowconfigure(1, weight=1)
output_frame.grid_columnconfigure(0, weight=1)

output_label = tk.Label(
    output_frame,
    text="Download History:",
    font=('Segoe UI', 12, 'bold'),
    bg=THEME['bg'],
    fg=THEME['fg']
)
output_label.grid(row=0, column=0, sticky="w", pady=(0, 5))

output_box = tk.Text(
    output_frame,
    height=10,
    font=('Consolas', 10),
    bg=THEME['light_gray'],
    fg=THEME['fg'],
    relief='flat',
    padx=10,
    pady=10
)
output_box.grid(row=1, column=0, sticky="nsew")

# Status Bar
status_frame = tk.Frame(root, bg=THEME['border'], height=30)
status_frame.grid(row=1, column=0, sticky="ew")
status_frame.grid_columnconfigure(0, weight=1)

status_label = tk.Label(
    status_frame,
    text="Ready",
    font=('Segoe UI', 9),
    bg=THEME['border'],
    fg=THEME['fg']
)
status_label.grid(row=0, column=0, sticky="w", padx=10)

# System Tray Icon
def create_tray_icon():
    global tray_icon, tray_thread
    try:
        if ICON_PATH.exists():
            icon_image = Image.open(ICON_PATH)
        else:
            # Create a simple icon if the file doesn't exist
            icon_image = Image.new('RGB', (64, 64), THEME['primary'])
        
        menu = (
            item('Show', lambda: show_window()),
            item('Exit', lambda: root.quit())
        )
        
        tray_icon = pystray.Icon(
            "media_downloader",
            icon_image,
            "Media Downloader",
            menu
        )
        
        # Run the tray icon in a separate thread
        tray_thread = threading.Thread(target=tray_icon.run, daemon=True)
        tray_thread.start()
    except Exception as e:
        log(f"Error creating tray icon: {e}")

def show_window():
    """Show the main window."""
    root.deiconify()
    root.lift()
    root.focus_force()

def hide_window():
    """Hide the window to system tray."""
    root.withdraw()
    if tray_icon is None:
        create_tray_icon()

def on_minimize(event):
    """Handle window minimize event."""
    if event.widget == root:  # Only minimize to tray if it's the main window
        hide_window()

def on_close():
    """Handle window close event."""
    messagebox.showinfo("Minimizing to Tray", "This application will minimize to system tray and continue running in background.")
    hide_window()

# Bind minimize and close events
root.protocol('WM_DELETE_WINDOW', on_close)
root.bind('<Unmap>', on_minimize)  # Handle minimize button click

# Start tray icon
create_tray_icon()

# Update progress function to show percentage in status
def update_progress(percent, message=None):
    """Update the progress bar and label."""
    try:
        progress['value'] = percent
        if message:
            progress_label.config(text=message)
            status_label.config(text=message)
    except Exception as e:
        log(f"Error updating progress: {str(e)}")

def finish_progress():
    progress['value'] = 100
    progress_label.config(text="Download Complete!")
    status_label.config(text="Download Complete!")

def process_queue():
    """Process the UI update queue."""
    while not ui_queue.empty():
        try:
            task = ui_queue.get_nowait()
            task()
        except queue.Empty:
            break
    root.after(100, process_queue)

def create_loading_icon():
    """Create a loading GIF animation."""
    global loading_gif, loading_label
    try:
        # Create a simple loading animation
        frames = []
        for i in range(8):
            img = Image.new('RGBA', (16, 16), (0, 0, 0, 0))
            draw = ImageDraw.Draw(img)
            angle = i * 45
            draw.pieslice([0, 0, 16, 16], angle, angle + 180, fill=THEME['primary'])
            frames.append(img)
        
        # Save frames to memory
        output = io.BytesIO()
        frames[0].save(output, format='GIF', save_all=True, append_images=frames[1:], 
                      duration=100, loop=0, transparency=0)
        loading_gif = Image.open(output)
        return loading_gif
    except:
        return None

def update_loading_animation():
    """Update the loading animation."""
    if loading_gif and loading_label:
        try:
            frame = next(loading_gif.iter_frames())
            photo = ImageTk.PhotoImage(frame)
            loading_label.configure(image=photo)
            loading_label.image = photo
            root.after(100, update_loading_animation)
        except:
            pass

# Add global variable for download cancellation and yt-dlp instance
download_cancelled = False
ydl_instance = None
current_download_thread = None

def cancel_download():
    """Cancel the current download."""
    global download_cancelled, ydl_instance, current_download_thread
    download_cancelled = True
    
    try:
        # Cancel the yt-dlp instance by setting the download_cancelled flag
        # The progress hook will check this flag and stop the download
        if ydl_instance:
            # Set the download_cancelled flag which is checked in the progress hook
            ydl_instance = None
        
        # Force stop the download thread
        if current_download_thread and current_download_thread.is_alive():
            # Use a more aggressive approach to stop the thread
            import ctypes
            thread_id = ctypes.c_long(current_download_thread.ident)
            ctypes.pythonapi.PyThreadState_SetAsyncExc(thread_id, ctypes.py_object(SystemExit))
            current_download_thread.join(timeout=1)
        
        # Reset progress and UI
        ui_queue.put(lambda: update_progress(0, "Download cancelled"))
        ui_queue.put(lambda: enable_buttons())
        log("Download cancelled by user")
        
        # Ensure window stays visible after cancellation
        root.deiconify()
        root.lift()
        root.focus_force()
    except Exception as e:
        log(f"Error during cancellation: {str(e)}")

def download_media(is_audio):
    """Download media from the provided URL."""
    global ffmpeg_path, ffprobe_path, download_cancelled, ydl_instance
    download_cancelled = False  # Reset cancellation flag
    ydl_instance = None  # Reset yt-dlp instance
    
    try:
        show_loading()  # Show loading animation
        update_progress(0, "Starting download...")  # Initialize progress bar
        
        # Verify output directories exist
        if not verify_output_directories():
            messagebox.showerror("Error", "Failed to create output directories. Check permissions and disk space.")
            hide_loading()
            update_progress(0, "Ready to download")
            return
            
        # Verify FFmpeg is available
        if not ffmpeg_path or not os.path.exists(ffmpeg_path):
            log("FFmpeg not found. Attempting to download...")
            ffmpeg_path = download_ffmpeg()
            if not ffmpeg_path or not os.path.exists(ffmpeg_path):
                messagebox.showerror("Error", "FFmpeg is required but could not be installed automatically.")
                hide_loading()
                update_progress(0, "Ready to download")
                return
        
        # Get current quality settings
        current_video_quality = video_quality_var.get()
        current_audio_quality = audio_quality_var.get()
        current_format = format_var.get()
        
        # Update quality settings dictionary
        quality_settings['video_quality'] = current_video_quality
        quality_settings['audio_quality'] = current_audio_quality
        quality_settings['format'] = current_format
        
        url = url_entry.get().strip()
        if not url:
            messagebox.showerror("Error", "Please enter a video URL")
            hide_loading()
            update_progress(0, "Ready to download")
            return

        # Check if URL is a playlist
        is_playlist = ('playlist' in url.lower() or 
                       'list=' in url.lower() or 
                       '/sets/' in url.lower())  # Handle SoundCloud sets
                       
        if is_playlist and not download_playlist.get():
            if not messagebox.askyesno("Playlist Detected", 
                "This appears to be a playlist URL. Would you like to download the entire playlist?\n\n"
                "If not, only the first video will be downloaded."):
                is_playlist = False

        max_files = max_files_entry.get() or '100'
        try:
            max_files = int(max_files)
        except ValueError:
            max_files = 100

        # Set the appropriate output directory
        if is_playlist:
            output_path = playlist_output_dir
            output_template = str(playlist_output_dir / '%(playlist_index)s_%(title)s.%(ext)s')
        elif is_audio:
            output_path = audio_output_dir
            output_template = str(audio_output_dir / '%(title)s.%(ext)s')
        else:
            output_path = video_output_dir
            output_template = str(video_output_dir / '%(title)s.%(ext)s')

        log(f"Output directory set to: {output_path}")

        # Validate URL
        if not url.startswith(('http://', 'https://')):
            log(f"URL validation failed: {url}")
            messagebox.showerror("Error", "Please enter a valid URL starting with http:// or https://")
            hide_loading()
            update_progress(0, "Ready to download")
            return

        # Configure format and quality settings for highest quality
        if is_audio:
            format_code = 'bestaudio/best'
            log(f"Downloading audio with settings:")
            log(f"- Format: {format_code}")
            log(f"- Quality: {current_audio_quality}kbps")
        else:
            # Updated format selection for highest quality
            if current_video_quality == 'best':
                format_code = 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/bestvideo+bestaudio/best'
            else:
                format_code = f'bestvideo[height<={current_video_quality}][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<={current_video_quality}]+bestaudio/best[height<={current_video_quality}]'
            
            log(f"Downloading video with settings:")
            log(f"- Format: {format_code}")
            log(f"- Quality: {current_video_quality}")
            log(f"- Output Format: {current_format}")

        ydl_opts = {
            'format': format_code,
            'progress_hooks': [create_progress_hook()],
            'restrictfilenames': True,
            'windowsfilenames': True,
            'quiet': False,
            'no_warnings': False,
            'nocheckcertificate': True,  # Avoid certificate issues
            'nooverwrites': True,
            'ignoreerrors': True,  # Don't stop on errors
            'continuedl': True,
            'ffmpeg_location': ffmpeg_path,
            'merge_output_format': current_format,
            'verbose': True,
            'outtmpl': output_template,
            'playlist_items': f'1-{max_files}' if is_playlist else None,
            'noplaylist': not is_playlist,
            'ssl_verify': False,  # Disable SSL verification to avoid certificate issues
            'source_address': None,
            'socket_timeout': 30,
            'retries': 10,
            'extractor_retries': 10,
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
        }
        
        # Configure postprocessor based on download type and quality settings
        if is_audio:
            ydl_opts['postprocessors'] = [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': current_audio_quality,
            }]
        else:
            # For video downloads, add postprocessor to ensure best quality
            ydl_opts['postprocessors'] = [{
                'key': 'FFmpegVideoConvertor',
                'preferedformat': current_format,
            }]

        ydl_instance = yt_dlp.YoutubeDL(ydl_opts)
        try:
            log("Extracting video information...")
            try:
                info = ydl_instance.extract_info(url, download=False)
                if not info:
                    raise Exception("Failed to extract video information")
            except Exception as extract_error:
                log(f"Error extracting info: {str(extract_error)}")
                messagebox.showerror("Error", f"Failed to extract video information: {str(extract_error)}")
                hide_loading()
                update_progress(0, "Ready to download")
                return
            
            log(f"Download options: {ydl_opts}")
            
            if is_playlist and 'entries' in info:
                log(f"? Downloading playlist: {info.get('title', 'Untitled')}")
                entries_count = len(list(info.get('entries', [])))
                log(f"?? Number of items: {entries_count}")
                log(f"?? Downloading first {max_files} items")
            else:
                log(f"? Downloading single video: {info.get('title', 'Untitled')}")
                
            log(f"? Download will be saved to: {output_path}")
            log(f"? Starting download: {url}")
            log(f"? Using quality settings: Video={current_video_quality}, Audio={current_audio_quality}kbps, Format={current_format}")
            
            if download_cancelled:
                return
                
            # Start the actual download
            log("Starting download process...")
            try:
                print("\n=== DOWNLOAD PROCESS STARTING ===")
                print(f"URL: {url}")
                print(f"Output path: {output_path}")
                print(f"Format: {format_code}")
                print(f"Is audio only: {is_audio}")
                print(f"Is playlist: {is_playlist}")
                print(f"FFmpeg path: {ffmpeg_path}")
                print(f"Output template: {output_template}")
                
                # Check that output directory exists and is writable
                print(f"Checking output directory...")
                if not output_path.exists():
                    print(f"Creating output directory: {output_path}")
                    output_path.mkdir(parents=True, exist_ok=True)
                
                # Test write access to output directory
                try:
                    test_file = output_path / "test_write.tmp"
                    with open(test_file, 'w') as f:
                        f.write("test")
                    test_file.unlink()
                    print("Output directory is writable")
                except Exception as e:
                    print(f"Warning: Output directory may not be writable: {e}")
                
                print("Starting yt-dlp download...")
                try:
                    # First attempt - use the configured options
                    ydl_instance.download([url])
                    print("yt-dlp download function completed")
                except Exception as primary_error:
                    # If the primary method failed, try a fallback with simpler options
                    print(f"\n=== PRIMARY DOWNLOAD FAILED, TRYING FALLBACK ===")
                    print(f"Primary error: {str(primary_error)}")
                    
                    # Create simpler fallback options
                    fallback_opts = {
                        'format': 'best' if not is_audio else 'bestaudio',
                        'outtmpl': output_template,
                        'nocheckcertificate': True,
                        'ignoreerrors': True,
                        'no_warnings': True,
                        'quiet': False,
                        'verbose': True,
                        'progress_hooks': [create_progress_hook()]
                    }
                    
                    if is_audio:
                        fallback_opts['postprocessors'] = [{
                            'key': 'FFmpegExtractAudio',
                            'preferredcodec': 'mp3',
                            'preferredquality': current_audio_quality,
                        }]
                        
                    print(f"Trying fallback with simplified options: {fallback_opts}")
                    fallback_ydl = yt_dlp.YoutubeDL(fallback_opts)
                    fallback_ydl.download([url])
                    print("Fallback download completed")
                
            except yt_dlp.utils.DownloadError as download_error:
                error_str = str(download_error)
                print(f"\n=== DOWNLOAD ERROR DETAILS ===")
                print(f"Error: {error_str}")
                print(f"Error type: {type(download_error).__name__}")
                
                # Detailed error diagnosis
                if "ffmpeg" in error_str.lower():
                    print("This appears to be an FFmpeg error")
                    log(f"FFmpeg error: {error_str}")
                    messagebox.showerror("FFmpeg Error", 
                        f"Error with FFmpeg: {error_str}\n\n"
                        "Please check that FFmpeg is installed correctly.")
                elif "HTTP Error 429" in error_str:
                    print("This appears to be a rate limit error")
                    log(f"Rate limit error: {error_str}")
                    messagebox.showerror("Rate Limit Error", 
                        "You are being rate limited by the server. Please try again later.")
                elif "postprocessor" in error_str.lower():
                    print("This appears to be a postprocessor error")
                    log(f"Postprocessor error: {error_str}")
                    messagebox.showerror("Processing Error", 
                        f"Error processing the video: {error_str}\n\n"
                        "Try downloading without conversion or in a different format.")
                elif "copyright" in error_str.lower() or "not available" in error_str.lower():
                    print("This appears to be a content availability error")
                    log(f"Content availability error: {error_str}")
                    messagebox.showerror("Content Error", 
                        f"This content may not be available: {error_str}")
                elif "network" in error_str.lower() or "connection" in error_str.lower():
                    print("This appears to be a network error")
                    log(f"Network error: {error_str}")
                    messagebox.showerror("Network Error", 
                        f"Network connection issue: {error_str}\n\n"
                        "Check your internet connection and try again.")
                else:
                    print("This is an unclassified error")
                    log(f"Download error: {error_str}")
                    messagebox.showerror("Download Error", error_str)
                
                hide_loading()
                update_progress(0, "Ready to download")
                return
            except Exception as e:
                log(f"Unexpected download error: {str(e)}")
                messagebox.showerror("Error", f"An unexpected error occurred: {str(e)}")
            finally:
                ydl_instance = None

            if download_cancelled:
                log("Download cancelled")
                return

            # Success! Open the appropriate folder
            if is_playlist:
                log(f"? Playlist download completed!")
                log(f"?? Saved to: {playlist_output_dir}")
                
                # Ensure the folder exists and open it
                if playlist_output_dir.exists():
                    try:
                        folder_path = str(playlist_output_dir.resolve())
                        log(f"Opening folder: {folder_path}")
                        if IS_WINDOWS:
                            os.startfile(folder_path)
                        elif IS_LINUX:
                            subprocess.Popen(['xdg-open', folder_path])
                        elif IS_MAC:
                            subprocess.Popen(['open', folder_path])
                        else:
                            webbrowser.open(f"file://{folder_path}")
                    except Exception as e:
                        log(f"Error opening folder: {str(e)}")
            else:
                log("? Download completed!")
                log(f"?? Saved to: {output_path}")
                # Open the output folder
                try:
                    folder_path = str(output_path.resolve())
                    if IS_WINDOWS:
                        os.startfile(folder_path)
                    elif IS_LINUX:
                        subprocess.Popen(['xdg-open', folder_path])
                    elif IS_MAC:
                        subprocess.Popen(['open', folder_path])
                    else:
                        webbrowser.open(f"file://{folder_path}")
                except Exception as e:
                    log(f"Error opening folder: {str(e)}")

        except yt_dlp.utils.DownloadError as e:
            # This block will only be reached for errors not caught in the inner try block
            if not download_cancelled:  # Only show error if not cancelled
                log(f"Uncaught download error: {str(e)}")
                messagebox.showerror("Download Error", f"Download failed: {str(e)}")
        except Exception as e:
            if not download_cancelled:  # Only show error if not cancelled
                log(f"Unexpected error: {str(e)}")
                messagebox.showerror("Error", f"An unexpected error occurred: {str(e)}")
        finally:
            ydl_instance = None

    except Exception as e:
        if not download_cancelled:  # Only show error if not cancelled
            messagebox.showerror("Error", f"Error occurred:\n{e}")
    finally:
        hide_loading()  # Hide loading animation
        if not download_cancelled:
            ui_queue.put(lambda: enable_buttons())
            ui_queue.put(lambda: update_progress(0, "Ready to download"))
        # Ensure window stays visible after download
        root.deiconify()
        root.lift()
        root.focus_force()

# Clipboard Monitoring Functions
def is_supported_url(url):
    try:
        return validators.url(url)
    except:
        return False

def check_clipboard():
    global last_copied_url
    try:
        clipboard_content = pyperclip.paste().strip()
        if validators.url(clipboard_content):
            if clipboard_content != last_copied_url and is_supported_url(clipboard_content):
                url_entry.delete(0, tk.END)
                url_entry.insert(0, clipboard_content)
                last_copied_url = clipboard_content
                log(f"Auto-detected URL: {clipboard_content}")
    except Exception as e:
        print("Clipboard error:", e)
    root.after(1000, check_clipboard)

# Start clipboard monitoring
check_clipboard()

# Start queue processing
root.after(100, process_queue)

# Main loop
if __name__ == "__main__":
    try:
        # Ensure window is visible before doing anything else
        root.deiconify()
        root.lift()
        root.focus_force()
        root.update_idletasks()  # Process pending window updates
        root.update()  # Force window to appear immediately
        
        # Create tray icon but don't start minimized
        if tray_icon is None:
            create_tray_icon()
        
        # Check for updates on startup (non-blocking, after window is shown)
        def check_updates_async():
            try:
                # Small delay to ensure window is fully visible first
                root.after(500, check_updates_on_startup)
            except Exception as e:
                log(f"Error scheduling update check: {e}")
        
        check_updates_async()
        
        # Show the window again to ensure it's on top
        root.deiconify()
        root.lift()
        root.focus_force()
        
        root.mainloop()
    except KeyboardInterrupt:
        sys.exit(0)
    except Exception as e:
        # Show error in a messagebox if window creation fails
        try:
            import traceback
            error_msg = f"Failed to start Media Downloader:\n{str(e)}\n\n{traceback.format_exc()}"
            messagebox.showerror("Startup Error", error_msg)
        except:
            print(f"Critical error: {e}")
            import traceback
            traceback.print_exc()
        sys.exit(1)
    finally:
        # Clean up tray icon when exiting
        if tray_icon is not None:
            tray_icon.stop()

def resource_path(relative_path):
    """Get absolute path to resource, works for dev and for PyInstaller."""
    try:
        base_path = sys._MEIPASS
    except AttributeError:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)
