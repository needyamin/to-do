# Daily Dashboard - Advanced Task Management Suite

A comprehensive cross-platform Python application for daily task management with integrated tools for MySQL backups, FTP/SFTP file management, media downloading, and advanced shell access.

<img width="1629" height="941" alt="Image" src="https://github.com/user-attachments/assets/9d335d79-622c-42c7-b972-e74a825e9943" />
<img width="992" height="858" alt="Image" src="https://github.com/user-attachments/assets/125d0182-2c7f-4902-baed-1603ad36ef9a" />
<img width="746" height="728" alt="Image" src="https://github.com/user-attachments/assets/ae1e4df3-ed10-4c13-a9f3-feb215589f8f" />
<img width="577" height="783" alt="Image" src="https://github.com/user-attachments/assets/812520ee-c0a3-4545-a844-6c8b3420d545" />

## 🚀 Features

### 📋 Core Dashboard Features
- **Task Management**: Create, edit, delete, and manage tasks with deadlines and timers
- **Task Archive**: Automatic archiving of completed tasks after configurable time threshold
- **Notes**: Create and manage detailed notes with rich text editing
- **Useful Links**: Quick access to frequently used URLs
- **Deadline Tracking**: Real-time countdown with visual alerts and sound notifications
- **Search**: Quick search functionality for tasks
- **Cloud Sync**: Optional HTTP, FTP, or S3 synchronization for task database
- **Analog Clocks**: Display up to 6 timezone clocks (US, UK, Japan, Bangladesh, India, Singapore)
- **Date/Time Display**: Main date and time display with timezone label (configurable visibility)
- **Settings**: Comprehensive settings for theme, sync, clock visibility, and archive threshold

### 🛠️ Integrated Tools

#### MySQL Backup Tool
- GUI-based MySQL database backup management
- Save and manage multiple connection presets
- Backup history tracking
- Secure credential storage with SQLite (`settings.db`)
- **Remote Backup Options**: HTTP, FTP, S3, or Google Drive (OAuth2)
- Automatic credential persistence and auto-load on startup
- Cross-platform support (Linux/Windows/Mac)

#### FTP/FTPS/SFTP Client
- Full-featured file transfer client similar to FileZilla
- Support for FTP, FTPS (TLS), and SFTP protocols
- **Advanced Features**:
  - File upload, download, delete, rename
  - Directory creation and navigation
  - File/folder permissions editing (chmod)
  - File properties viewer (size, dates, permissions)
  - Multi-select operations
  - Transfer queue with progress tracking
  - Connection profiles with saved credentials
  - Local and remote file browsing
  - Recursive directory deletion
- Cross-platform support (Linux/Windows/Mac)

#### Media Downloader
- Download videos and audio from various platforms
- Support for playlists and single media files
- Quality settings (video: best, 1080p, 720p, 480p, 360p)
- Audio quality options (320, 256, 192, 128, 96 kbps)
- Format selection (MP4, WebM, MKV)
- Auto-detection of clipboard URLs
- System tray integration
- Auto-start with Windows/Linux
- Cross-platform support (Linux/Windows/Mac)

#### Advanced Shell (Shell Yamin)
- Powerful GUI shell with admin/root capabilities
- Cross-platform command execution (Linux/Windows/Mac)
- Privilege elevation support (sudo/pkexec on Linux, UAC on Windows, osascript on Mac)
- Command history
- Current directory management
- Built-in commands
- Dark theme interface

## 📦 Installation

### Prerequisites
- Python 3.12 or higher
- Linux, Windows, or macOS

### Quick Start
```bash
# Install dependencies
pip install -r requirements.txt

# Run the application
python task.py
```

### Platform-Specific Notes

#### Windows
- All GUIs run without console windows
- Taskbar icons properly configured
- Auto-start support via Windows Registry

#### Linux
- Auto-start via `.desktop` file in `~/.config/autostart/`
- FFmpeg installation via package manager (Ubuntu: `sudo apt-get install ffmpeg`)
- Proper icon support via Pillow fallback

#### macOS
- Auto-start not yet implemented (can be added)
- FFmpeg installation via Homebrew (`brew install ffmpeg`)

## 📁 Project Structure

```
to-do/
├── task.py                    # Main dashboard application
├── icon.ico                   # Application icon
├── icon_utils.py             # Centralized icon management
├── settings_db.py            # Shared settings database utilities
├── sync_server.py            # Optional sync server
├── requirements.txt          # Python dependencies
├── settings.db               # Shared credentials/settings database
├── ftp_client/               # FTP/FTPS/SFTP client
│   ├── ftp_client_gui.py    # Main FTP client GUI
│   └── ftp_client_gui_enhanced.py  # Enhanced version
├── media_downloader/         # Media downloader
│   ├── media-download.py    # Main media downloader GUI
│   └── requirements.txt     # Media downloader dependencies
├── mysql_client/             # MySQL backup tool
│   └── mysql_backup_gui.py  # MySQL backup GUI
└── shell_yamin/              # Advanced shell
    ├── shell_gui.py         # Shell GUI
    └── README.md            # Shell documentation
```

## 🎯 Usage

### Main Dashboard

#### Task Management
- **Add Task**: Type in the input field and press Enter
- **Set Deadline**: Right-click task → "Set Timer..." or click "⏰ Add Timer"
- **Edit Task**: Right-click → "Edit Task..." for comprehensive editing
- **Toggle Done**: Double-click task or press Space
- **Delete Task**: Select task and press Delete or right-click → "Delete Task"
- **Search**: Type in search box and press Enter to find tasks
- **Archive**: View archived tasks via **Archive → View Archive...**

#### Notes & Links
- **Add Note**: Click "➕ Add New Note" button
- **Edit Note**: Right-click note → "Edit"
- **Add Link**: Click "➕ Add New Link" button
- **Open Link**: Double-click link in list

#### Settings
- **Access**: Tools → Settings
- **Theme**: Light/Dark mode
- **Analog Clocks**: Show/hide individual timezone clocks
- **Date/Time Display**: Show/hide main date and time
- **Cloud Sync**: Configure HTTP, FTP, or S3 synchronization
- **Archive Threshold**: Set hours before completed tasks are auto-archived

### Integrated Tools

Access via **Tools** menu:
- **MySQL Backup Tool**: Database backup management
- **FTP/FTPS/SFTP Client**: File transfer and management
- **Media Downloader**: Download videos and audio
- **Advanced Shell**: GUI shell with admin access

## 🔧 Configuration

### Database
- **Main dashboard DB file**: **`taskmask.db`** (used by all dashboard features)
  - Default location (Windows): `%APPDATA%\DailyDashboard\database\taskmask.db`
  - Default location (Linux/Mac): `~/.config/DailyDashboard/database/taskmask.db`
  - Portable mode: Create `portable.txt` next to `task.py` to use `./database/taskmask.db`
- **Shared credentials/settings DB file**: **`settings.db`** (stored in project root)
  - Contains: saved MySQL connections, FTP connection profiles, backup locations, backup history, OAuth2 tokens, archive settings, clock visibility settings, and other shared credential/history settings

### Cloud Sync (Optional)
Configure in **Tools → Settings**:
- **HTTP Sync**: Custom server synchronization
- **FTP Sync**: FTP server synchronization
- **S3 Sync**: Amazon S3 or S3-compatible storage

### MySQL Backup Remote Storage
Configure in **MySQL Backup Tool → Step 3 — Remote Backup**:
- **HTTP**: Upload backup archives to custom HTTP endpoint
- **FTP**: Upload to FTP server
- **S3**: Upload to Amazon S3 or S3-compatible storage
- **Google Drive**: Upload to your personal Google Drive using OAuth2

#### Google Drive Setup (OAuth2)
1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create or select a project
3. Enable **Google Drive API**
4. Go to **Credentials** → **Create Credentials** → **OAuth client ID**
5. Choose **Desktop app** as application type
6. Download the JSON file and save it as `client_secrets.json` in the `mysql_client/` folder
7. In the MySQL Backup Tool, click **"🔐 Authorize Google Drive"** to complete OAuth2 flow

### FTP Client
- **Connection Profiles**: Save FTP/FTPS/SFTP connection credentials
- **Auto-connect**: Load saved connections on startup
- **Credentials Storage**: All credentials stored securely in `settings.db`

### Media Downloader
- **Output Directories**: 
  - Windows: `%USERPROFILE%\Downloads\Yamin Downloader\`
  - Linux/Mac: `~/Downloads/Yamin Downloader/`
- **FFmpeg**: Auto-downloads on Windows, manual installation required on Linux/Mac
- **Auto-start**: Enable in File menu

## 📋 Dependencies

See `requirements.txt` for complete list. Key dependencies:

### Core
- `pytz>=2024.1` - Timezone handling
- `playsound==1.2.2` - Sound playback

### Cloud Sync
- `boto3>=1.28.0` - S3 sync support (dashboard sync + MySQL backup)

### MySQL Backup
- `google-api-python-client>=2.100.0` - Google Drive API
- `google-auth>=2.23.0` - Google authentication (OAuth2)
- `google-auth-httplib2>=0.1.1` - OAuth2 HTTP support
- `google-auth-oauthlib>=1.1.0` - OAuth2 flow support

### FTP Client
- `paramiko>=3.0.0` - SFTP support (optional, required for SFTP protocol)

### Media Downloader
- `yt-dlp>=2025.3.31` - Media download engine
- `pyperclip>=1.8.2` - Clipboard operations
- `pystray>=0.19.4` - System tray icon
- `validators>=0.22.0` - URL validation
- `requests>=2.31.0` - HTTP requests
- `certifi>=2023.7.22` - SSL certificates

### Cross-Platform Support
- `Pillow>=10.0.0` - Image processing and icon support
- `pywin32>=306` - Windows API integration (Windows only, optional)

## 🆕 Recent Updates

- ✨ **Task Archive System**: Automatic archiving of completed tasks with configurable threshold
- ✨ **Analog Clocks**: 6 timezone clocks with individual show/hide settings
- ✨ **Date/Time Display**: Main date and time display with timezone label and visibility control
- ✨ **FTP/FTPS/SFTP Client**: Full-featured file transfer client with advanced features
- ✨ **Media Downloader**: Cross-platform media downloader with quality settings
- ✨ **Advanced Shell**: GUI shell with admin/root capabilities
- ✨ **Cross-Platform Support**: Full compatibility with Linux, Windows, and macOS
- ✨ **Console Window Hiding**: All GUIs run without console windows
- ✨ **Shared Settings Database**: Centralized credential and settings storage
- ✨ **MySQL Backup Remote Storage**: HTTP, FTP, S3, and Google Drive (OAuth2) support
- ✨ **Auto-Save Credentials**: All tools automatically remember connection settings
- ✨ **Improved Error Handling**: Better error messages and fallback mechanisms

## 🐛 Troubleshooting

**Import Errors**: Ensure all dependencies are installed: `pip install -r requirements.txt`

**Icon Not Loading**: Icon file should be in project root as `icon.ico`

**Console Windows Appearing**: On Windows, ensure `pywin32` is installed. Console windows are automatically hidden.

**FFmpeg Not Found (Media Downloader)**:
- Windows: Auto-downloads on first use
- Linux: Install via package manager (`sudo apt-get install ffmpeg`)
- macOS: Install via Homebrew (`brew install ffmpeg`)

**Database Issues**: Delete database file to reset (location shown in status bar)

**FTP Connection Issues**: Check firewall settings and ensure correct port numbers

**Media Downloader Not Opening**: Check that all dependencies are installed, especially `yt-dlp`

## 📄 License

MIT License - See LICENSE file for details

---

**Made with ❤️ for productive daily management and automation**

**Developer**: Md. Yamin Hossain  
**GitHub**: [https://github.com/needyamin](https://github.com/needyamin)
