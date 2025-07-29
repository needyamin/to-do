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
        "clang" , # Required for clang compilation
        "playsound==1.2.2"
    ]
    for req in requirements:
        try:
            __import__(req)
        except ImportError:
            print(f"Installing {req}...")
            run([sys.executable, "-m", "pip", "install", "--upgrade", req])

def build_project():
    print("Starting build process...")
    
    # Use current Python installation
    python312_path = sys.executable
    print(f"Using current Python installation: {python312_path}")
    
    # Check Python version
    import subprocess
    try:
        result = subprocess.run([python312_path, "--version"], capture_output=True, text=True)
        version = result.stdout.strip()
        print(f"Python version: {version}")
        
        # Check if it's Python 3.12 or higher
        if "3.12" not in version and "3.13" not in version and "3.14" not in version:
            print("Warning: This script was designed for Python 3.12+, but you're using a different version.")
            print("The build may still work, but compatibility is not guaranteed.")
    except Exception as e:
        print(f"Warning: Could not verify Python version: {e}")
    
    # Install required packages using current Python
    print("Installing requirements with current Python...")
    for req in ["nuitka", "pytz", "zstandard", "ordered-set", "playsound==1.2.2"]:
        os.system(f'"{python312_path}" -m pip install --upgrade {req}')
    
    # Project paths
    current_dir = os.path.dirname(os.path.abspath(__file__))
    task_py = os.path.join(current_dir, "task.py")
    assets_dir = os.path.join(current_dir, "assets")
    database_dir = os.path.join(current_dir, "database")
    db_file = os.path.join(database_dir, "sweethart.db")
    
    # Check if required directories and files exist
    if not os.path.exists(assets_dir):
        print(f"Warning: assets directory not found at {assets_dir}")
        print("Creating assets directory...")
        os.makedirs(assets_dir, exist_ok=True)
    
    if not os.path.exists(database_dir):
        print(f"Warning: database directory not found at {database_dir}")
        print("Creating database directory...")
        os.makedirs(database_dir, exist_ok=True)
    
    # Ensure clean build
    build_dir = os.path.join(current_dir, "build")
    if os.path.exists(build_dir):
        print("Cleaning previous build...")
        shutil.rmtree(build_dir)
    
    print(f"Using Python from: {python312_path}")
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
    
    # Build include data commands
    include_commands = []
    
    # Include assets directory
    if os.path.exists(assets_dir):
        include_commands.append(f"--include-data-dir={assets_dir}=assets")
        print(f"Including assets directory: {assets_dir}")
    
    # Include database directory
    if os.path.exists(database_dir):
        include_commands.append(f"--include-data-dir={database_dir}=database")
        print(f"Including database directory: {database_dir}")
    
    # Include specific database file as backup
    if os.path.exists(db_file):
        include_commands.append(f"--include-data-files={db_file}=database/sweethart.db")
        print(f"Including database file: {db_file}")
    
    # Nuitka build command - single file executable
    build_command = [
        python312_path,
        "-m", 
        "nuitka",
        "--mingw64",  # Use MinGW64 instead of MSVC
        "--follow-imports",
        "--windows-disable-console",  # Disable console for GUI app
        "--onefile",  # Create single executable file
        "--enable-plugin=tk-inter",
        "--output-dir=build",
        "--show-progress",
        "--assume-yes-for-downloads",
        "--windows-icon-from-ico=icon.ico",  # Add icon to single file
    ] + include_commands + [task_py]
    
    print("Building executable...")
    print("Build command:", " ".join(build_command))
    result = run(build_command)
    
    if result.returncode == 0:
        print("\nBuild completed successfully!")
        print("\nExecutable can be found in the 'build' directory")
        
        # Copy directories to build folder as backup
        build_dir = os.path.join(current_dir, "build")
        if os.path.exists(assets_dir):
            build_assets_dir = os.path.join(build_dir, "assets")
            if os.path.exists(build_assets_dir):
                shutil.rmtree(build_assets_dir)
            shutil.copytree(assets_dir, build_assets_dir)
            print("Assets directory copied to build directory")
        
        if os.path.exists(database_dir):
            build_database_dir = os.path.join(build_dir, "database")
            if os.path.exists(build_database_dir):
                shutil.rmtree(build_database_dir)
            shutil.copytree(database_dir, build_database_dir)
            print("Database directory copied to build directory")
        
        print("\nBuild summary:")
        print("- Assets folder included and copied to build directory")
        print("- Database folder included and copied to build directory")
        print("- Executable created with all required resources")
    else:
        print("\nBuild failed!")

if __name__ == "__main__":
    build_project()
