import os
import sys
import shutil
from subprocess import run

def install_requirements():
    print("Checking and installing requirements...")
    requirements = [
        "nuitka>=2.0",  # Ensure latest version
        "pytz",
        "zstandard",  # Required for Nuitka compression
        "ordered-set",  # Required for Nuitka optimization
        "clang"  # Required for clang compilation
    ]
    for req in requirements:
        try:
            __import__(req)
        except ImportError:
            print(f"Installing {req}...")
            run([sys.executable, "-m", "pip", "install", "--upgrade", req])

def build_project():
    print("Starting build process...")
    
    # Try to find Python 3.12 installation
    possible_paths = [
        os.path.expandvars(r"%LOCALAPPDATA%\Programs\Python\Python312\python.exe"),
        os.path.expandvars(r"%PROGRAMFILES%\Python312\python.exe"),
        os.path.expandvars(r"%PROGRAMFILES(X86)%\Python312\python.exe"),
        "C:\\Python312\\python.exe"
    ]
    
    python312_path = None
    for path in possible_paths:
        if os.path.exists(path):
            python312_path = path
            break
    
    if not python312_path:
        print("Error: Python 3.12 not found!")
        print("Please install Python 3.12 from https://www.python.org/downloads/release/python-3126/")
        print("Make sure to check 'Add Python to PATH' during installation")
        sys.exit(1)
    
    # Install required packages using Python 3.12
    print("Installing requirements with Python 3.12...")
    for req in ["nuitka", "pytz", "zstandard", "ordered-set"]:
        os.system(f'"{python312_path}" -m pip install --upgrade {req}')
    
    # Project paths
    current_dir = os.path.dirname(os.path.abspath(__file__))
    task_py = os.path.join(current_dir, "task.py")
    db_file = os.path.join(current_dir, "dashboard_data.db")
    
    # Ensure clean build
    build_dir = os.path.join(current_dir, "build")
    if os.path.exists(build_dir):
        print("Cleaning previous build...")
        shutil.rmtree(build_dir)
    
    print(f"Using Python 3.12 from: {python312_path}")
    print("Installing required packages...")
    
    # Install requirements
    try:
        run([python312_path, "-m", "pip", "install", "--upgrade", "pip"], check=True)
        for package in ["nuitka>=2.0", "pytz", "zstandard", "ordered-set"]:
            print(f"Installing {package}...")
            run([python312_path, "-m", "pip", "install", "--upgrade", package], check=True)
    except Exception as e:
        print(f"Error installing packages: {e}")
        sys.exit(1)
    
    # Nuitka build command
    build_command = [
        python312_path,
        "-m", 
        "nuitka",
        "--msvc=latest",  # Try MSVC first
        "--follow-imports",
        "--windows-disable-console",
        "--assume-yes-for-downloads",  # Auto-download required components
        "--show-modules",  # Show module compilation progress
        "--show-scons",    # Show detailed compilation output
        "--include-data-files=%s=dashboard_data.db" % db_file,
        "--windows-icon-from-ico=icon.ico",  # Optional: Add this line if you have an icon file
        "--standalone",
        "--enable-plugin=tk-inter",
        "--output-dir=build",
        "--show-progress",
        "--show-memory",
        "--assume-yes-for-downloads",
        "--nofollow-import-to=tkinter",  # Optimize Tkinter imports
        "--python-flag=no_site",  # Optimize startup
        task_py
    ]
    
    print("Building executable...")
    result = run(build_command)
    
    if result.returncode == 0:
        print("\nBuild completed successfully!")
        print("\nExecutable can be found in the 'build' directory")
        
        # Copy database if it exists
        build_dir = os.path.join(current_dir, "build")
        if os.path.exists(db_file):
            shutil.copy2(db_file, os.path.join(build_dir, "dashboard_data.db"))
            print("Database file copied to build directory")
    else:
        print("\nBuild failed!")

if __name__ == "__main__":
    build_project()
