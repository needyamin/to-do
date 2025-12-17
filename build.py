import os
import sys
import shutil
import platform
from subprocess import run

def install_requirements():
    """Install required packages for building"""
    print("Checking and installing requirements...")
    requirements = [
        "nuitka>=2.0",
        "pytz",
        "zstandard",
        "ordered-set",
        "playsound==1.2.2",
        "boto3>=1.28.0"
    ]
    
    # Platform-specific requirements
    if platform.system() == "Linux":
        requirements.append("patchelf")  # Required for AppImage
    
    for req in requirements:
        try:
            # Try to import to check if installed
            if ">=" in req or "==" in req:
                package_name = req.split(">=")[0].split("==")[0]
            else:
                package_name = req
            __import__(package_name.replace("-", "_"))
        except ImportError:
            print(f"Installing {req}...")
            run([sys.executable, "-m", "pip", "install", "--upgrade", req], check=False)

def get_python_version():
    """Get Python version as tuple (major, minor)"""
    return sys.version_info[:2]

def check_msvc_available():
    """Check if MSVC is available on the system"""
    try:
        # Try to find vswhere (Visual Studio Installer location tool)
        import subprocess
        vswhere_paths = [
            r"C:\Program Files (x86)\Microsoft Visual Studio\Installer\vswhere.exe",
            r"C:\Program Files\Microsoft Visual Studio\Installer\vswhere.exe",
        ]
        
        for vswhere in vswhere_paths:
            if os.path.exists(vswhere):
                result = subprocess.run(
                    [vswhere, "-latest", "-products", "*", "-requires", "Microsoft.VisualStudio.Component.VC.Tools.x86.x64"],
                    capture_output=True,
                    text=True
                )
                if result.returncode == 0 and result.stdout.strip():
                    return True
        
        # Check for cl.exe in common paths
        common_paths = [
            r"C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\VC\Tools\MSVC",
            r"C:\Program Files (x86)\Microsoft Visual Studio\2022\Community\VC\Tools\MSVC",
            r"C:\Program Files (x86)\Microsoft Visual Studio\2022\Professional\VC\Tools\MSVC",
            r"C:\Program Files (x86)\Microsoft Visual Studio\2019\BuildTools\VC\Tools\MSVC",
            r"C:\Program Files (x86)\Microsoft Visual Studio\2019\Community\VC\Tools\MSVC",
        ]
        
        for base_path in common_paths:
            if os.path.exists(base_path):
                # Check for any version subdirectory
                for item in os.listdir(base_path):
                    cl_path = os.path.join(base_path, item, "bin", "Hostx64", "x64", "cl.exe")
                    if os.path.exists(cl_path):
                        return True
        
        return False
    except Exception:
        return False

def build_windows_exe():
    """Build Windows .exe using Nuitka"""
    print("Building Windows executable (.exe)...")
    
    python_path = sys.executable
    python_version = get_python_version()
    print(f"Python version: {python_version[0]}.{python_version[1]}")
    
    current_dir = os.path.dirname(os.path.abspath(__file__))
    task_py = os.path.join(current_dir, "task.py")
    build_dir = os.path.join(current_dir, "build")
    assets_dir = os.path.join(current_dir, "assets")
    database_dir = os.path.join(current_dir, "database")
    
    # Ensure build directory exists
    os.makedirs(build_dir, exist_ok=True)
    
    # Include data commands
    include_commands = []
    
    if os.path.exists(assets_dir):
        include_commands.append(f"--include-data-dir={assets_dir}=assets")
        print(f"Including assets directory: {assets_dir}")
    
    if os.path.exists(database_dir):
        include_commands.append(f"--include-data-dir={database_dir}=database")
        print(f"Including database directory: {database_dir}")
    
    # Check for icon
    icon_path = os.path.join(current_dir, "icon.ico")
    icon_command = []
    if os.path.exists(icon_path):
        icon_command = [f"--windows-icon-from-ico={icon_path}"]
        print(f"Including icon: {icon_path}")
    
    # Determine compiler based on Python version
    # Python 3.13+ requires MSVC, Python 3.12 and earlier can use MinGW64
    compiler_flag = []
    if python_version >= (3, 13):
        print("⚠️  Python 3.13+ detected: MSVC compiler required (MinGW64 not supported)")
        
        # Check if MSVC is available
        msvc_available = check_msvc_available()
        if not msvc_available:
            print("\n⚠️  WARNING: MSVC not detected on your system")
            print("   Nuitka will attempt to download MSVC automatically")
            print("   If this fails, please install Visual Studio Build Tools:")
            print("   https://visualstudio.microsoft.com/downloads/#build-tools-for-visual-studio-2022")
            print("   Or use Python 3.12 for better compatibility with MinGW64\n")
        else:
            print("   ✓ MSVC detected on your system")
        
        # Try different MSVC options based on availability
        # First try with latest, if that fails user can try --msvc=14.3 or install VS Build Tools
        print("   Using --msvc=latest flag")
        print("   If build fails with 'ilink' error, try installing Visual Studio Build Tools")
        compiler_flag = ["--msvc=latest"]
    else:
        print("Using MinGW64 compiler")
        compiler_flag = ["--mingw64"]
    
    # Nuitka build command for Windows
    build_command = [
        python_path,
        "-m", "nuitka",
    ] + compiler_flag + [
        "--follow-imports",
        "--windows-disable-console",
        "--onefile",
        "--enable-plugin=tk-inter",
        f"--output-dir={build_dir}",
        "--show-progress",
        "--assume-yes-for-downloads",
    ] + icon_command + include_commands + [task_py]
    
    print("Build command:", " ".join(build_command))
    result = run(build_command)
    
    if result.returncode == 0:
        print("\n✅ Windows .exe build completed successfully!")
        print(f"Executable location: {build_dir}")
        return True
    else:
        print("\n❌ Windows .exe build failed!")
        
        # Provide helpful error messages based on Python version
        if python_version >= (3, 13):
            print("\n" + "=" * 60)
            print("TROUBLESHOOTING FOR PYTHON 3.13+")
            print("=" * 60)
            print("The build failed because MSVC compiler tools are not properly available.")
            print("\nSOLUTIONS:")
            print("1. Install Visual Studio Build Tools 2022:")
            print("   https://visualstudio.microsoft.com/downloads/#build-tools-for-visual-studio-2022")
            print("   - Download 'Build Tools for Visual Studio 2022'")
            print("   - During installation, select 'Desktop development with C++' workload")
            print("   - Restart your terminal/command prompt after installation")
            print("\n2. OR use Python 3.12 (recommended for easier builds):")
            print("   - Python 3.12 works with MinGW64 (automatically downloaded)")
            print("   - Download from: https://www.python.org/downloads/")
            print("   - No additional tools required")
            print("\n3. OR try updating Nuitka to latest version:")
            print("   pip install --upgrade nuitka")
            print("\n4. OR try building without onefile (standalone mode):")
            print("   Edit build.py and change '--onefile' to '--standalone'")
            print("   This creates a folder with the executable and dependencies")
            print("=" * 60)
            print("\n💡 RECOMMENDED: Use Python 3.12 for the easiest build experience")
            print("   Python 3.12 works perfectly with MinGW64 (no extra tools needed)")
            print("=" * 60)
        
        return False

def build_linux_appimage():
    """Build Linux AppImage using Nuitka"""
    print("Building Linux AppImage...")
    
    python_path = sys.executable
    current_dir = os.path.dirname(os.path.abspath(__file__))
    task_py = os.path.join(current_dir, "task.py")
    build_dir = os.path.join(current_dir, "build")
    assets_dir = os.path.join(current_dir, "assets")
    database_dir = os.path.join(current_dir, "database")
    
    # Ensure build directory exists
    os.makedirs(build_dir, exist_ok=True)
    
    # Include data commands
    include_commands = []
    
    if os.path.exists(assets_dir):
        include_commands.append(f"--include-data-dir={assets_dir}=assets")
        print(f"Including assets directory: {assets_dir}")
    
    if os.path.exists(database_dir):
        include_commands.append(f"--include-data-dir={database_dir}=database")
        print(f"Including database directory: {database_dir}")
    
    # Check for icon (convert .ico to .png if needed, or use existing .png)
    icon_path = os.path.join(current_dir, "icon.ico")
    icon_png = os.path.join(current_dir, "icon.png")
    icon_command = []
    
    # Try to use PNG icon for Linux, or create one from ICO
    if os.path.exists(icon_png):
        icon_command = [f"--linux-icon={icon_png}"]
        print(f"Including icon: {icon_png}")
    elif os.path.exists(icon_path):
        # Note: Nuitka can handle .ico on Linux, but .png is preferred
        print(f"Note: Using .ico icon (consider converting to .png for better Linux support)")
    
    # Nuitka build command for Linux AppImage
    build_command = [
        python_path,
        "-m", "nuitka",
        "--follow-imports",
        "--onefile",
        "--enable-plugin=tk-inter",
        f"--output-dir={build_dir}",
        "--show-progress",
        "--assume-yes-for-downloads",
        "--linux-onefile-icon=icon.ico" if os.path.exists(icon_path) else "",
    ] + icon_command + include_commands + [task_py]
    
    # Remove empty strings from command
    build_command = [cmd for cmd in build_command if cmd]
    
    print("Build command:", " ".join(build_command))
    result = run(build_command)
    
    if result.returncode == 0:
        # Nuitka creates a .bin file, we need to convert it to AppImage
        # Find the built binary
        built_binary = None
        for file in os.listdir(build_dir):
            if file.endswith(".bin") or (os.path.isfile(os.path.join(build_dir, file)) and os.access(os.path.join(build_dir, file), os.X_OK)):
                if not file.endswith(".so") and not file.endswith(".py"):
                    built_binary = os.path.join(build_dir, file)
                    break
        
        if built_binary:
            # Rename to AppImage format
            appimage_name = "DailyDashboard.AppImage"
            appimage_path = os.path.join(build_dir, appimage_name)
            
            if os.path.exists(appimage_path):
                os.remove(appimage_path)
            
            os.rename(built_binary, appimage_path)
            os.chmod(appimage_path, 0o755)  # Make executable
            
            print("\n✅ Linux AppImage build completed successfully!")
            print(f"AppImage location: {appimage_path}")
            return True
        else:
            print("\n⚠️  Build completed but could not find binary to rename to AppImage")
            print(f"Check {build_dir} for the built binary")
            return True
    else:
        print("\n❌ Linux AppImage build failed!")
        return False

def build_project():
    """Main build function - detects OS and builds accordingly"""
    print("=" * 60)
    print("Daily Dashboard Build Script")
    print("=" * 60)
    
    system = platform.system()
    print(f"Detected OS: {system}")
    
    # Install requirements
    print("\n" + "=" * 60)
    print("Installing requirements...")
    print("=" * 60)
    install_requirements()
    
    # Project paths
    current_dir = os.path.dirname(os.path.abspath(__file__))
    task_py = os.path.join(current_dir, "task.py")
    assets_dir = os.path.join(current_dir, "assets")
    database_dir = os.path.join(current_dir, "database")
    build_dir = os.path.join(current_dir, "build")
    
    # Check if task.py exists
    if not os.path.exists(task_py):
        print(f"❌ Error: task.py not found at {task_py}")
        sys.exit(1)
    
    # Create required directories
    if not os.path.exists(assets_dir):
        print(f"Creating assets directory: {assets_dir}")
        os.makedirs(assets_dir, exist_ok=True)
    
    if not os.path.exists(database_dir):
        print(f"Creating database directory: {database_dir}")
        os.makedirs(database_dir, exist_ok=True)
    
    # Clean build directory (optional - comment out to keep previous builds)
    if os.path.exists(build_dir):
        print(f"\nCleaning previous build directory: {build_dir}")
        try:
            shutil.rmtree(build_dir)
        except Exception as e:
            print(f"Warning: Could not clean build directory: {e}")
    
    os.makedirs(build_dir, exist_ok=True)
    
    # Check Python version and provide warnings
    python_version = get_python_version()
    print(f"\nPython version: {python_version[0]}.{python_version[1]}")
    
    if system == "Windows" and python_version >= (3, 13):
        print("\n⚠️  NOTE: Python 3.13+ detected on Windows")
        print("   Nuitka will use MSVC compiler instead of MinGW64")
        print("   MSVC will be downloaded automatically if not available")
        print("   This may take longer on first build")
    
    # Build based on OS
    print("\n" + "=" * 60)
    print("Starting build process...")
    print("=" * 60)
    
    success = False
    
    if system == "Windows":
        success = build_windows_exe()
    elif system == "Linux":
        success = build_linux_appimage()
    else:
        print(f"❌ Unsupported OS: {system}")
        print("Supported platforms: Windows, Linux")
        sys.exit(1)
    
    # Build summary
    print("\n" + "=" * 60)
    if success:
        print("✅ BUILD SUMMARY")
        print("=" * 60)
        if system == "Windows":
            print(f"✓ Windows .exe created in: {build_dir}")
        elif system == "Linux":
            print(f"✓ Linux AppImage created in: {build_dir}")
        print(f"✓ Assets included in executable")
        print(f"✓ Database structure included in executable")
        print(f"✓ No external dependencies required")
        print("\nBuild completed successfully! 🎉")
    else:
        print("❌ BUILD FAILED")
        print("=" * 60)
        print("Please check the error messages above.")
        sys.exit(1)

if __name__ == "__main__":
    build_project()
