# Daily Dashboard - Advanced Task Management Application

A comprehensive daily dashboard application built with Python and Tkinter for managing tasks, notes, and useful links with timer functionality, deadline tracking, and cloud sync capabilities.

<img width="1297" height="1010" alt="Image" src="https://github.com/user-attachments/assets/d3a1e4e2-50d3-4c81-ab4a-4b7486c149af" />

## 🚀 Features

### 📋 Task Management
- **To-Do List**: Create, edit, and manage tasks with checkboxes
- **Detailed Task Editor**: Comprehensive editing window with:
  - Multi-line task description editor
  - Task completion status toggle
  - Created date editing
  - Deadline management with date/time picker
  - Completion timestamp display
- **Deadline Tracking**: Set deadlines with 12-hour format (AM/PM)
- **Timer Display**: Real-time countdown showing time remaining
- **Search Functionality**: Quick search to find tasks by name, deadline, or created date
- **Visual Alerts**: Color-coded tasks based on urgency
  - 🔴 Red: Overdue or <2 hours left
  - 🟠 Orange: <6 hours left
  - 🔵 Blue: Same day
  - ⚫ Black: Future days
- **Blinking Effect**: Overdue tasks blink to draw attention
- **Sound Notifications**: MP3 sound plays when tasks become overdue
- **Table View**: Organized display with columns for Status, Task, Created Date, Deadline, and Time Left

### 🔗 Useful Links
- **Link Management**: Add, edit, and organize frequently used URLs
- **Quick Access**: Right-click to open links directly
- **Reordering**: Move links up/down to organize by priority
- **Modern GUI**: Clean interface with improved input validation

### 📝 Notes
- **Note Taking**: Create and manage detailed notes
- **Edit Notes**: Full-featured note editor with:
  - Title editing
  - Multi-line content editor with scrollbar
  - Proper height adjustment to prevent content cutoff
- **Rich Content**: Support for multi-line text
- **Organization**: Reorder notes by importance
- **Quick View**: Double-click to view full note content
- **Context Menu**: Right-click to edit or delete notes

### ☁️ Cloud Sync (Optional)
- **Multiple Sync Methods**:
  - **HTTP Sync**: Sync with custom server (original method)
  - **FTP Sync**: Sync via FTP server
  - **S3 Sync**: Sync with Amazon S3 or S3-compatible storage
- **Auto-Sync**: Automatic synchronization at configurable intervals
- **Manual Sync**: Trigger sync on demand
- **Conflict Resolution**: Choose how to handle sync conflicts (prefer local, prefer server, or prefer newer)

### 🎨 User Interface
- **Modern Design**: Clean and responsive interface
- **Improved Font Sizes**: Larger, more readable fonts (13px) for all content sections
- **Responsive Layout**: Adapts to different screen sizes
- **Icon Support**: Application icon on all windows
- **Centered Windows**: All popup windows open centered relative to main window
- **Scrollable Content**: Proper scrolling for long content
- **Keyboard Shortcuts**: 
  - Enter: Add new task/link/note
  - Space: Toggle task completion
  - Delete: Remove selected item
  - Up/Down arrows: Navigate items
  - Ctrl+Enter: Save in edit windows
  - Escape: Cancel/close windows

## 📦 Installation

### Prerequisites
- Python 3.12 or higher
- Windows 10/11 or Linux (for sound notifications on Windows)

### Quick Start
1. **Clone or download** the project files
2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```
3. **Run the application**:
   ```bash
   python task.py
   ```

## 🛠️ Building Executable

The build script automatically detects your operating system and creates the appropriate build:

### Windows
```bash
python build.py
```
**Output**: `build/task.exe` (or similar executable name)

### Linux
```bash
python build.py
```
**Output**: `build/DailyDashboard.AppImage`

### Build Requirements
- Python 3.12+ (recommended: Python 3.12 for Windows builds)
- Internet connection (for downloading compilers and dependencies)
- 2-5 GB free disk space
- For Linux: `patchelf` (automatically installed if needed)

**Note for Python 3.13+ on Windows:**
- Python 3.13+ requires MSVC compiler (MinGW64 is not supported)
- The build script automatically uses `--msvc=latest` for Python 3.13+
- MSVC will be downloaded automatically by Nuitka if not available
- For best compatibility, Python 3.12 is recommended for Windows builds

All builds are created in the `build/` directory in the project root.

## 📁 Project Structure

```
to-do-main/
├── task.py              # Main application
├── build.py             # Build script for Windows/Linux executables
├── sync_server.py       # Optional HTTP sync server
├── requirements.txt     # Python dependencies
├── README.md           # This file
├── LICENSE             # License file
├── icon.ico            # Application icon
├── assets/             # Sound files and assets
│   └── overdue.mp3     # Overdue notification sound
├── database/           # SQLite database (portable mode)
└── build/              # Build output directory
    ├── task.exe        # Windows executable (after build)
    └── DailyDashboard.AppImage  # Linux AppImage (after build)
```

## 🎯 Usage Guide

### Adding Tasks
1. Type task description in the input field
2. Press Enter or click "Add Task"
3. **Set Deadline**: Right-click task → "Set Timer..." or click "⏰ Add Timer" button
4. Choose date and time using the time picker or quick time buttons
5. Task will appear with countdown timer

### Editing Tasks
1. Right-click on a task → "Edit Task..."
2. Use the comprehensive editor to:
   - Edit task description (multi-line supported)
   - Toggle completion status
   - Modify created date
   - Update deadline with date/time picker
   - Clear deadline if needed
3. Click "Save Changes" or press Ctrl+Enter

### Managing Links
1. Click "➕ Add New Link" button
2. Enter name and URL (https:// is added automatically if missing)
3. Links appear in the Useful Links section
4. Right-click to open or delete

### Creating and Editing Notes
1. **Create**: Click "➕ Add New Note" button
2. **Edit**: Right-click on note → "Edit" or click "Edit Note" in view window
3. Enter/edit title and content
4. Notes are saved automatically
5. Double-click to view full note

### Searching Tasks
1. Type in the search box in the To-Do List section
2. Press Enter to find next matching task
3. Search matches task name, deadline, and created date

### Timer Features
- **12-Hour Format**: AM/PM time selection
- **Time Picker**: Visual time picker with hour/minute spinboxes
- **Quick Times**: Predefined time buttons (9 AM, 12 PM, 3 PM, 6 PM)
- **Real-time Updates**: Timer updates every second
- **Sound Alerts**: MP3 plays when task becomes overdue

## 🔧 Configuration

### Database
- SQLite database is stored in **%APPDATA%\\DailyDashboard\\database\\sweethart.db** by default (Windows)
- For **portable mode**, create an empty file named `portable.txt` next to `task.py` to store DB in `./database/sweethart.db`
- Data persists between application sessions
- No manual configuration required

### Server Sync (Optional)

#### HTTP Sync
1. Run the sync server:
   ```bash
   python sync_server.py --port 8765 --token "YOUR_TOKEN"
   ```
2. In the app: `Tools → Settings…` then:
   - Select "HTTP" as sync type
   - Enable **Server Sync**
   - Set Server URL: `http://<server-ip>:8765`
   - Set User: any name (e.g. `yamin`)
   - Set Token: must match the server `--token`
   - Set Interval: auto-sync frequency (seconds)

#### FTP Sync
1. In the app: `Tools → Settings…` then:
   - Select "FTP" as sync type
   - Enable **Server Sync**
   - Enter FTP Host, Port (default: 21), Username, Password
   - Set Remote Path (default: `/`)
   - Set Interval: auto-sync frequency (seconds)

#### S3 Sync
1. In the app: `Tools → Settings…` then:
   - Select "S3" as sync type
   - Enable **Server Sync**
   - Enter S3 Bucket name
   - Set S3 Key (filename, default: `sweethart.db`)
   - Set S3 Region (default: `us-east-1`)
   - Enter Access Key ID and Secret Access Key
   - Set Interval: auto-sync frequency (seconds)

**Note**: You can also trigger manual sync: `Tools → Sync Now`

### Sound Notifications
- Place MP3 files in `assets/` directory
- Default sound: `assets/overdue.mp3`
- Test sound button available in application

### Timezone
- Application uses Asia/Dhaka timezone
- Current time displayed in main window

## 🐛 Troubleshooting

### Common Issues

**Build Fails with Compiler Error (Windows)**
- **Python 3.13+**: Build script automatically uses `--msvc=latest`
  - MSVC will be downloaded automatically by Nuitka
  - First build may take longer while MSVC downloads
- **Python 3.12 and earlier**: Build script uses `--mingw64` flag automatically
  - Nuitka will automatically download MinGW64
- If build still fails, try using Python 3.12 for best compatibility

**Build Fails on Linux**
- Ensure `patchelf` is installed: `sudo apt-get install patchelf` (Debian/Ubuntu)
- Or: `sudo yum install patchelf` (RHEL/CentOS)
- The build script will attempt to install it automatically

**Sound Not Playing**
- Check if `assets/overdue.mp3` exists
- Try the "🔊 Test Sound" button
- Ensure system volume is not muted
- On Linux, ensure audio system is properly configured

**Python Version Error**
- Ensure Python 3.12+ is installed
- Check with: `python --version` or `python3 --version`

**Database Issues**
- Delete database file to reset
- Windows: `%APPDATA%\DailyDashboard\database\sweethart.db`
- Portable mode: `./database/sweethart.db`
- Application will recreate database automatically

**Sync Issues**
- Check network connectivity
- Verify server credentials (FTP/S3)
- Ensure server is running (HTTP sync)
- Check firewall settings
- Review sync error messages in status bar

**S3 Sync Requires boto3**
- Install: `pip install boto3`
- Or run: `pip install -r requirements.txt`

## 📋 Dependencies

### Runtime Dependencies
- `pytz>=2024.1` - Timezone handling
- `playsound==1.2.2` - Sound playback
- `boto3>=1.28.0` - AWS S3 sync support (optional, for S3 sync)

### Build Dependencies (Optional)
- `nuitka>=2.0` - Python to executable compiler
- `zstandard>=0.21.0` - Compression
- `ordered-set>=4.1.0` - Optimization
- `clang>=16.0.0` - C compilation (Linux)
- `patchelf` - ELF patching (Linux, for AppImage)

### Standard Library
- `tkinter` - GUI framework
- `sqlite3` - Database
- `datetime` - Date/time handling
- `threading` - Background tasks
- `subprocess` - System commands
- `webbrowser` - URL opening
- `winsound` - Windows sound (Windows only)
- `ftplib` - FTP client (built-in)
- `urllib` - HTTP client (built-in)
- `hashlib` - File hashing (built-in)

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly on both Windows and Linux
5. Submit a pull request

## 📄 License

This project is open source and available under the MIT License.

## 🆘 Support

For issues or questions:
1. Check the troubleshooting section
2. Review the error messages
3. Ensure all dependencies are installed
4. Try running with Python 3.12+
5. Check the build output for detailed error messages

## 🎉 Recent Updates

- ✨ Added FTP and S3 sync support
- ✨ Enhanced task editing with comprehensive GUI
- ✨ Added note editing functionality
- ✨ Improved font sizes for better readability
- ✨ Added search functionality for tasks
- ✨ Better column widths for To-Do list
- ✨ Cross-platform build support (Windows .exe and Linux AppImage)
- ✨ Improved UI responsiveness and layout
- ✨ Better window centering and scrollability

---

**Made with ❤️ for productive daily management**
