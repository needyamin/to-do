# Advanced Shell Terminal GUI

A powerful cross-platform GUI shell terminal with superadmin/root support for Windows, Linux, and macOS.

## Features

- **Cross-Platform Support**: Works on Windows, Linux, and macOS
- **Admin/Root Privileges**: 
  - Windows: Uses UAC elevation with `runas`
  - Linux: Uses `sudo` or `pkexec` for privilege elevation
  - macOS: Uses `osascript` with administrator privileges
- **Built-in Commands**:
  - `help` - Show help message
  - `exit` / `quit` - Exit the shell
  - `clear` / `cls` - Clear the terminal
  - `cd [directory]` - Change directory
  - `pwd` - Print working directory
  - `sudo [command]` - Execute command with elevated privileges
  - `history` - Show command history
  - `env` - Show environment variables
  - `whoami` - Show current user
- **Modern Dark Theme**: Terminal-style dark theme with syntax highlighting
- **Command History**: Navigate previous commands with Up/Down arrows
- **Real-time Output**: Live output from commands with color-coded messages
- **Error Handling**: Proper error handling and display

## Usage

### From Task.py
1. Open `task.py`
2. Go to `Tools` menu
3. Click `🔧 Advanced Shell...`

### Direct Execution
```bash
python shell_yamin/shell_gui.py
```

## Privilege Elevation

### Windows
- Click the "🔐 Elevate" button to restart with administrator privileges
- Or use `sudo` prefix before commands to elevate specific commands

### Linux
- Use `sudo` prefix before commands
- Or click "🔐 Elevate" to restart with root privileges
- Uses `pkexec` (GUI) or `sudo` (terminal) for elevation

### macOS
- Uses `osascript` with administrator privileges
- Click "🔐 Elevate" or use `sudo` prefix

## Requirements

- Python 3.7+
- tkinter (usually included with Python)
- Standard library only (no external dependencies)

## Security Notes

- The shell runs with the privileges of the user who launched it
- Elevation requires user confirmation (UAC on Windows, password prompt on Linux/Mac)
- Use with caution when running with elevated privileges

## Examples

```bash
# Change directory
cd /home/user/documents

# List files
ls -la

# Run with admin privileges
sudo apt update

# Check current user
whoami

# View environment variables
env
```

