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

def build_windows_exe():
    """Build Windows .exe using Nuitka"""
    print("Building Windows executable (.exe)...")
    
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
    
    # Check for icon
    icon_path = os.path.join(current_dir, "icon.ico")
    icon_command = []
    if os.path.exists(icon_path):
        icon_command = [f"--windows-icon-from-ico={icon_path}"]
        print(f"Including icon: {icon_path}")
    
    # Nuitka build command for Windows
    build_command = [
        python_path,
        "-m", "nuitka",
        "--mingw64",
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
