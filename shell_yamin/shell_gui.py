#!/usr/bin/env python3
"""
Powerful GUI Shell with Superadmin/Root Support
Works on Windows, Linux, and macOS
"""

import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, font
import subprocess
import sys
import os
import platform
import threading
import queue
import shlex
from pathlib import Path
import ctypes
from datetime import datetime

# Color scheme
COLOR_BG = "#1e1e1e"
COLOR_FG = "#d4d4d4"
COLOR_SELECTION = "#264f78"
COLOR_ERROR = "#f48771"
COLOR_SUCCESS = "#89d185"
COLOR_WARNING = "#dcdcaa"
COLOR_INFO = "#569cd6"
COLOR_PROMPT = "#4ec9b0"

class ShellGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("🔧 Advanced Shell Terminal")
        self.root.geometry("1000x700")
        self.root.minsize(600, 400)
        self.root.configure(bg=COLOR_BG)
        
        # Set window icon if available
        try:
            from icon_utils import set_window_icon
            set_window_icon(root)
        except:
            pass
        
        # Detect platform
        self.platform = platform.system().lower()
        self.is_windows = self.platform == "windows"
        self.is_linux = self.platform == "linux"
        self.is_mac = self.platform == "darwin"
        
        # Current directory
        self.current_dir = os.getcwd()
        
        # Admin/root status
        self.is_admin = self.check_admin_privileges()
        
        # Command history
        self.history = []
        self.history_index = -1
        
        # Process management
        self.current_process = None
        self.process_queue = queue.Queue()
        
        # Setup UI
        self.setup_ui()
        
        # Start queue processor
        self.root.after(100, self.process_queue_messages)
        
        # Welcome message
        self.print_welcome()
    
    def check_admin_privileges(self):
        """Check if running with admin/root privileges."""
        if self.is_windows:
            try:
                return ctypes.windll.shell32.IsUserAnAdmin() != 0
            except:
                return False
        else:
            # Linux/Mac - check if UID is 0 (root)
            return os.geteuid() == 0
    
    def setup_ui(self):
        """Setup the GUI interface."""
        # Main container
        main_frame = tk.Frame(self.root, bg=COLOR_BG)
        main_frame.pack(fill="both", expand=True, padx=5, pady=5)
        
        # Status bar at top
        status_frame = tk.Frame(main_frame, bg=COLOR_BG, relief="flat", bd=1)
        status_frame.pack(fill="x", pady=(0, 5))
        
        # Platform indicator
        platform_text = f"Platform: {platform.system()} {platform.release()}"
        if self.is_admin:
            platform_text += " | 🔐 ADMIN/ROOT MODE"
        else:
            platform_text += " | ⚠️ Standard User"
        
        status_label = tk.Label(
            status_frame,
            text=platform_text,
            bg=COLOR_BG,
            fg=COLOR_INFO if self.is_admin else COLOR_WARNING,
            font=("Consolas", 9, "bold"),
            anchor="w",
            padx=10,
            pady=5
        )
        status_label.pack(side="left", fill="x", expand=True)
        
        # Current directory display
        self.dir_label = tk.Label(
            status_frame,
            text=f"📁 {self.current_dir}",
            bg=COLOR_BG,
            fg=COLOR_FG,
            font=("Consolas", 9),
            anchor="e",
            padx=10,
            pady=5
        )
        self.dir_label.pack(side="right")
        
        # Terminal output area
        output_frame = tk.Frame(main_frame, bg=COLOR_BG)
        output_frame.pack(fill="both", expand=True)
        
        # Text widget with custom styling
        self.output_text = scrolledtext.ScrolledText(
            output_frame,
            bg=COLOR_BG,
            fg=COLOR_FG,
            insertbackground=COLOR_FG,
            font=("Consolas", 11),
            wrap=tk.WORD,
            relief="flat",
            borderwidth=0,
            selectbackground=COLOR_SELECTION,
            selectforeground="white"
        )
        self.output_text.pack(fill="both", expand=True)
        
        # Configure tags for colored output
        self.output_text.tag_config("error", foreground=COLOR_ERROR)
        self.output_text.tag_config("success", foreground=COLOR_SUCCESS)
        self.output_text.tag_config("warning", foreground=COLOR_WARNING)
        self.output_text.tag_config("info", foreground=COLOR_INFO)
        self.output_text.tag_config("prompt", foreground=COLOR_PROMPT)
        
        # Input frame
        input_frame = tk.Frame(main_frame, bg=COLOR_BG)
        input_frame.pack(fill="x", pady=(5, 0))
        
        # Prompt label
        prompt_symbol = "#" if self.is_admin else "$"
        self.prompt_label = tk.Label(
            input_frame,
            text=f"{prompt_symbol} ",
            bg=COLOR_BG,
            fg=COLOR_PROMPT,
            font=("Consolas", 11, "bold"),
            anchor="w"
        )
        self.prompt_label.pack(side="left", padx=(0, 5))
        
        # Command input
        self.command_entry = tk.Entry(
            input_frame,
            bg="#2d2d2d",
            fg=COLOR_FG,
            insertbackground=COLOR_FG,
            font=("Consolas", 11),
            relief="flat",
            borderwidth=1,
            highlightthickness=1,
            highlightbackground="#3d3d3d",
            highlightcolor=COLOR_INFO
        )
        self.command_entry.pack(side="left", fill="x", expand=True, padx=(0, 5))
        self.command_entry.bind("<Return>", self.execute_command)
        self.command_entry.bind("<Up>", self.history_up)
        self.command_entry.bind("<Down>", self.history_down)
        self.command_entry.bind("<Tab>", self.auto_complete)
        
        # Execute button
        execute_btn = tk.Button(
            input_frame,
            text="▶ Execute",
            command=self.execute_command,
            bg=COLOR_INFO,
            fg="white",
            font=("Consolas", 9, "bold"),
            relief="flat",
            padx=15,
            pady=5,
            cursor="hand2"
        )
        execute_btn.pack(side="left", padx=(0, 5))
        
        # Clear button
        clear_btn = tk.Button(
            input_frame,
            text="🗑️ Clear",
            command=self.clear_output,
            bg="#5a5a5a",
            fg="white",
            font=("Consolas", 9),
            relief="flat",
            padx=10,
            pady=5,
            cursor="hand2"
        )
        clear_btn.pack(side="left", padx=(0, 5))
        
        # Admin button (if not already admin)
        if not self.is_admin:
            admin_btn = tk.Button(
                input_frame,
                text="🔐 Elevate",
                command=self.elevate_privileges,
                bg=COLOR_WARNING,
                fg="black",
                font=("Consolas", 9, "bold"),
                relief="flat",
                padx=10,
                pady=5,
                cursor="hand2"
            )
            admin_btn.pack(side="left")
        
        # Focus on command entry
        self.command_entry.focus_set()
    
    def print_welcome(self):
        """Print welcome message."""
        welcome = f"""
╔══════════════════════════════════════════════════════════════╗
║          🔧 Advanced Shell Terminal - {platform.system()}          ║
╚══════════════════════════════════════════════════════════════╝

Platform: {platform.system()} {platform.release()}
Python: {sys.version.split()[0]}
Current Directory: {self.current_dir}
Privileges: {'🔐 ADMIN/ROOT' if self.is_admin else '⚠️ Standard User'}

Type 'help' for available commands or 'exit' to close.

"""
        self.append_output(welcome, "info")
        self.update_prompt()
    
    def update_prompt(self):
        """Update the prompt display."""
        prompt_symbol = "#" if self.is_admin else "$"
        self.prompt_label.config(text=f"{prompt_symbol} ")
        self.dir_label.config(text=f"📁 {self.current_dir}")
    
    def append_output(self, text, tag=None):
        """Append text to output area."""
        self.output_text.insert(tk.END, text, tag)
        self.output_text.see(tk.END)
        self.root.update_idletasks()
    
    def clear_output(self):
        """Clear the output area."""
        self.output_text.delete(1.0, tk.END)
        self.print_welcome()
    
    def execute_command(self, event=None):
        """Execute the entered command."""
        command = self.command_entry.get().strip()
        if not command:
            return
        
        # Add to history
        if not self.history or self.history[-1] != command:
            self.history.append(command)
        self.history_index = len(self.history)
        
        # Clear input
        self.command_entry.delete(0, tk.END)
        
        # Display command
        prompt_symbol = "#" if self.is_admin else "$"
        self.append_output(f"{prompt_symbol} {command}\n", "prompt")
        
        # Handle built-in commands
        if self.handle_builtin_commands(command):
            return
        
        # Execute system command
        self.run_command(command)
    
    def handle_builtin_commands(self, command):
        """Handle built-in shell commands."""
        parts = command.split()
        cmd = parts[0].lower()
        
        if cmd == "exit" or cmd == "quit":
            self.root.destroy()
            return True
        
        elif cmd == "clear" or cmd == "cls":
            self.clear_output()
            return True
        
        elif cmd == "cd":
            try:
                if len(parts) > 1:
                    new_dir = parts[1]
                    # Handle ~ for home directory
                    if new_dir == "~" or new_dir.startswith("~/"):
                        new_dir = os.path.expanduser(new_dir)
                    # Handle relative paths
                    if not os.path.isabs(new_dir):
                        new_dir = os.path.join(self.current_dir, new_dir)
                    new_dir = os.path.normpath(new_dir)
                    if os.path.isdir(new_dir):
                        self.current_dir = new_dir
                        os.chdir(new_dir)
                        self.append_output(f"Changed directory to: {self.current_dir}\n", "success")
                        self.update_prompt()
                    else:
                        self.append_output(f"Error: Directory not found: {new_dir}\n", "error")
                else:
                    # Show current directory
                    self.append_output(f"{self.current_dir}\n", "info")
            except Exception as e:
                self.append_output(f"Error: {str(e)}\n", "error")
            return True
        
        elif cmd == "pwd":
            self.append_output(f"{self.current_dir}\n", "info")
            return True
        
        elif cmd == "help":
            help_text = """
Built-in Commands:
  help              - Show this help message
  exit / quit       - Exit the shell
  clear / cls       - Clear the terminal
  cd [directory]    - Change directory
  pwd               - Print working directory
  sudo [command]    - Execute command with elevated privileges
  history           - Show command history
  env               - Show environment variables
  whoami            - Show current user

System Commands:
  All other commands are executed as system commands.
  Use 'sudo' prefix for commands requiring admin privileges.
"""
            self.append_output(help_text, "info")
            return True
        
        elif cmd == "history":
            for i, hist_cmd in enumerate(self.history[-20:], 1):
                self.append_output(f"{i:4d}  {hist_cmd}\n", "info")
            return True
        
        elif cmd == "env":
            for key, value in os.environ.items():
                self.append_output(f"{key}={value}\n", "info")
            return True
        
        elif cmd == "whoami":
            username = os.getenv("USER") or os.getenv("USERNAME") or "unknown"
            self.append_output(f"{username}\n", "info")
            return True
        
        elif cmd == "sudo":
            # Handle sudo command
            if len(parts) > 1:
                sudo_command = " ".join(parts[1:])
                self.run_command_with_elevation(sudo_command)
            else:
                self.append_output("Usage: sudo <command>\n", "error")
            return True
        
        return False
    
    def run_command(self, command):
        """Run a system command."""
        try:
            # Parse command
            if self.is_windows:
                # Windows - use cmd.exe
                shell_cmd = ["cmd.exe", "/c", command]
                use_shell = False
            else:
                # Linux/Mac - use sh
                shell_cmd = shlex.split(command)
                use_shell = True
            
            # Start process
            process = subprocess.Popen(
                shell_cmd if not self.is_windows else command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                stdin=subprocess.PIPE,
                cwd=self.current_dir,
                shell=use_shell if not self.is_windows else True,
                text=True,
                bufsize=1
            )
            
            self.current_process = process
            
            # Read output in thread
            def read_output():
                try:
                    # Read stdout
                    for line in iter(process.stdout.readline, ''):
                        if line:
                            self.process_queue.put(("stdout", line))
                    
                    # Read stderr
                    for line in iter(process.stderr.readline, ''):
                        if line:
                            self.process_queue.put(("stderr", line))
                    
                    # Wait for process to complete
                    process.wait()
                    self.process_queue.put(("exit", process.returncode))
                except Exception as e:
                    self.process_queue.put(("error", str(e)))
            
            threading.Thread(target=read_output, daemon=True).start()
            
        except Exception as e:
            self.append_output(f"Error executing command: {str(e)}\n", "error")
    
    def run_command_with_elevation(self, command):
        """Run a command with elevated privileges."""
        if self.is_admin:
            # Already admin, just run the command
            self.run_command(command)
            return
        
        if self.is_windows:
            # Windows - use runas
            self.append_output("Requesting administrator privileges...\n", "warning")
            try:
                # Use PowerShell to elevate
                ps_command = f'Start-Process cmd -ArgumentList "/c {command}" -Verb RunAs'
                subprocess.Popen(
                    ["powershell", "-Command", ps_command],
                    creationflags=subprocess.CREATE_NEW_CONSOLE
                )
                self.append_output("Elevated command window opened.\n", "info")
            except Exception as e:
                self.append_output(f"Error elevating privileges: {str(e)}\n", "error")
        else:
            # Linux/Mac - use sudo
            self.append_output("Requesting root privileges...\n", "warning")
            try:
                # Use pkexec (Linux) or osascript (Mac) for GUI elevation
                if self.is_linux:
                    # Try pkexec first, fallback to sudo
                    try:
                        subprocess.Popen(
                            ["pkexec", "sh", "-c", command],
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE
                        )
                    except:
                        # Fallback to sudo (will prompt in terminal)
                        self.append_output("Please enter your password in the terminal.\n", "warning")
                        subprocess.Popen(
                            ["sudo", "sh", "-c", command],
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE
                        )
                else:
                    # macOS - use osascript for GUI elevation
                    osascript_cmd = f'''
                        do shell script "{command}" with administrator privileges
                    '''
                    subprocess.Popen(
                        ["osascript", "-e", osascript_cmd],
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE
                    )
                self.append_output("Elevated command executed.\n", "info")
            except Exception as e:
                self.append_output(f"Error elevating privileges: {str(e)}\n", "error")
    
    def process_queue_messages(self):
        """Process messages from the command execution queue."""
        try:
            while True:
                msg_type, content = self.process_queue.get_nowait()
                
                if msg_type == "stdout":
                    self.append_output(content, "success")
                elif msg_type == "stderr":
                    self.append_output(content, "error")
                elif msg_type == "exit":
                    if content != 0:
                        self.append_output(f"\n[Process exited with code {content}]\n", "warning")
                    else:
                        self.append_output("\n[Process completed successfully]\n", "success")
                    self.current_process = None
                elif msg_type == "error":
                    self.append_output(f"Error: {content}\n", "error")
        except queue.Empty:
            pass
        
        # Schedule next check
        self.root.after(100, self.process_queue_messages)
    
    def history_up(self, event):
        """Navigate command history up."""
        if self.history and self.history_index > 0:
            self.history_index -= 1
            self.command_entry.delete(0, tk.END)
            self.command_entry.insert(0, self.history[self.history_index])
        return "break"
    
    def history_down(self, event):
        """Navigate command history down."""
        if self.history:
            if self.history_index < len(self.history) - 1:
                self.history_index += 1
                self.command_entry.delete(0, tk.END)
                self.command_entry.insert(0, self.history[self.history_index])
            else:
                self.history_index = len(self.history)
                self.command_entry.delete(0, tk.END)
        return "break"
    
    def auto_complete(self, event):
        """Basic tab completion for file/directory names."""
        # Simple implementation - can be enhanced
        return "break"
    
    def elevate_privileges(self):
        """Attempt to restart with elevated privileges."""
        if self.is_admin:
            messagebox.showinfo("Already Admin", "You are already running with administrator privileges.")
            return
        
        if self.is_windows:
            # Windows - restart with runas
            try:
                # Get script path
                script_path = os.path.abspath(__file__)
                # Use PowerShell to elevate
                subprocess.Popen(
                    ["powershell", "-Command", f'Start-Process python -ArgumentList "{script_path}" -Verb RunAs'],
                    creationflags=subprocess.CREATE_NEW_CONSOLE
                )
                self.root.after(1000, self.root.destroy)
            except Exception as e:
                messagebox.showerror("Error", f"Failed to elevate privileges: {str(e)}")
        else:
            # Linux/Mac - use sudo to restart
            try:
                script_path = os.path.abspath(__file__)
                subprocess.Popen(
                    ["sudo", sys.executable, script_path],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE
                )
                self.root.after(1000, self.root.destroy)
            except Exception as e:
                messagebox.showerror("Error", f"Failed to elevate privileges: {str(e)}")

def main():
    root = tk.Tk()
    app = ShellGUI(root)
    root.mainloop()

if __name__ == "__main__":
    main()

