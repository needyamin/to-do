import os
import sys
import shutil
from subprocess import run

def build_project():
    print("Starting build process...")
    
    # Ensure Nuitka is installed
    try:
        import nuitka
    except ImportError:
        print("Installing Nuitka...")
        run([sys.executable, "-m", "pip", "install", "nuitka"])
    
    # Project paths
    current_dir = os.path.dirname(os.path.abspath(__file__))
    task_py = os.path.join(current_dir, "task.py")
    db_file = os.path.join(current_dir, "dashboard_data.db")
    
    # Nuitka build command
    build_command = [
        sys.executable, 
        "-m", 
        "nuitka",
        "--follow-imports",
        "--windows-disable-console",
        "--include-data-files=%s=dashboard_data.db" % db_file,
        "--windows-icon-from-ico=icon.ico",  # Optional: Add this line if you have an icon file
        "--standalone",
        "--enable-plugin=tk-inter",
        "--output-dir=build",
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
