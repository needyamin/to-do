# Daily Dashboard - Task Management Application

A comprehensive daily dashboard application built with Python and Tkinter for managing tasks, notes, and useful links with timer functionality and deadline tracking.

## 🚀 Features

### 📋 Task Management
- **To-Do List**: Create, edit, and manage tasks with checkboxes
- **Deadline Tracking**: Set deadlines with 12-hour format (AM/PM)
- **Timer Display**: Real-time countdown showing time remaining
- **Visual Alerts**: Color-coded tasks based on urgency
  - 🔴 Red: Overdue or <2 hours left
  - 🟠 Orange: <6 hours left
  - 🔵 Blue: Same day
  - ⚫ Black: Future days
- **Blinking Effect**: Overdue tasks blink to draw attention
- **Sound Notifications**: MP3 sound plays when tasks become overdue

### 🔗 Useful Links
- **Link Management**: Add, edit, and organize frequently used URLs
- **Quick Access**: Right-click to open links directly
- **Reordering**: Move links up/down to organize by priority

### 📝 Notes
- **Note Taking**: Create and manage detailed notes
- **Rich Content**: Support for multi-line text
- **Organization**: Reorder notes by importance
- **Quick View**: Double-click to view full note content

### 🎨 User Interface
- **Modern Design**: Clean and responsive interface
- **Icon Support**: Application icon on all windows
- **Keyboard Shortcuts**: 
  - Enter: Add new task/link/note
  - Space: Toggle task completion
  - Delete: Remove selected item
  - Up/Down arrows: Navigate items

## 📦 Installation

### Prerequisites
- Python 3.12 or higher
- Windows 10/11 (for sound notifications)

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

To create a standalone executable:

```bash
python build.py
```

The executable will be created in the `build/` directory with all required assets included.

### Build Requirements
- Python 3.12+
- Internet connection (for downloading MinGW64 compiler)
- 2-5 GB free disk space

## 📁 Project Structure

```
task/
├── task.py              # Main application
├── build.py             # Build script for executable
├── requirements.txt     # Python dependencies
├── README.md           # This file
├── icon.ico            # Application icon
├── assets/             # Sound files and assets
│   └── overdue.mp3     # Overdue notification sound
└── database/           # SQLite database
    └── sweethart.db    # Application data
```

## 🎯 Usage Guide

### Adding Tasks
1. Type task description in the input field
2. Press Enter or click "Add Task"
3. **Set Deadline**: Click "Set Task Deadline" button
4. Choose time using the clock interface or quick time buttons
5. Task will appear with countdown timer

### Managing Links
1. Click "Add Link" button
2. Enter name and URL
3. Links appear in the Useful Links section
4. Right-click to open or delete

### Creating Notes
1. Click "Add Note" button
2. Enter title and content
3. Notes are saved automatically
4. Double-click to view full note

### Timer Features
- **12-Hour Format**: AM/PM time selection
- **Clock Interface**: Visual time picker
- **Quick Times**: Predefined time buttons
- **Real-time Updates**: Timer updates every second
- **Sound Alerts**: MP3 plays when task becomes overdue

## 🔧 Configuration

### Database
- SQLite database automatically created in `database/sweethart.db`
- Data persists between application sessions
- No manual configuration required

### Sound Notifications
- Place MP3 files in `assets/` directory
- Default sound: `assets/overdue.mp3`
- Test sound button available in application

### Timezone
- Application uses Asia/Dhaka timezone
- Current time displayed in main window

## 🐛 Troubleshooting

### Common Issues

**Build Fails with MSVC Error**
- Solution: Use `--mingw64` flag (already configured in build.py)
- Nuitka will automatically download MinGW64

**Sound Not Playing**
- Check if `assets/overdue.mp3` exists
- Try the "🔊 Test Sound" button
- Ensure system volume is not muted

**Python Version Error**
- Ensure Python 3.12+ is installed
- Check with: `python --version`

**Database Issues**
- Delete `database/sweethart.db` to reset
- Application will recreate database automatically

## 📋 Dependencies

### Runtime Dependencies
- `pytz>=2023.3` - Timezone handling
- `playsound==1.2.2` - Sound playback

### Build Dependencies
- `nuitka>=2.0` - Python to executable compiler
- `zstandard>=0.21.0` - Compression
- `ordered-set>=4.1.0` - Optimization
- `clang>=16.0.0` - C compilation

### Standard Library
- `tkinter` - GUI framework
- `sqlite3` - Database
- `datetime` - Date/time handling
- `threading` - Background tasks
- `subprocess` - System commands
- `webbrowser` - URL opening
- `winsound` - Windows sound (Windows only)

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## 📄 License

This project is open source and available under the MIT License.

## 🆘 Support

For issues or questions:
1. Check the troubleshooting section
2. Review the error messages
3. Ensure all dependencies are installed
4. Try running with Python 3.12+

---

**Made with ❤️ for productive daily management**
