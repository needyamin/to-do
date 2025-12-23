#!/usr/bin/env python3
"""
FTP/FTPS/SFTP Client GUI with file management features.

Features:
  - FTP, FTPS (TLS), and SFTP support
  - Save/load connection profiles
  - File browser for remote and local directories
  - Upload/download files and directories
  - Connection history tracking
  - All credentials saved in shared settings.db
"""

import os
import platform
import sqlite3
import stat
import threading
import tkinter as tk
import base64
import json
import socket
import time
import hashlib
from datetime import datetime
from tkinter import filedialog, messagebox, simpledialog
from tkinter import ttk
from pathlib import Path
from collections import deque
import ftplib
from ftplib import FTP, FTP_TLS

# Add project root to path for icon_utils
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from icon_utils import set_window_icon
from settings_db import get_settings_db_path

# Optional SFTP support
try:
    import paramiko
    SFTP_AVAILABLE = True
    # Store paramiko module for later use
    _paramiko_module = paramiko
except ImportError:
    SFTP_AVAILABLE = False
    _paramiko_module = None

# Color scheme
COLOR_PRIMARY = "#2563eb"
COLOR_PRIMARY_HOVER = "#1d4ed8"
COLOR_SECONDARY = "#10b981"
COLOR_SECONDARY_HOVER = "#059669"
COLOR_DANGER = "#ef4444"
COLOR_WARNING = "#f59e0b"
COLOR_BG = "#f8fafc"
COLOR_CARD = "#ffffff"
COLOR_BORDER = "#e2e8f0"
COLOR_TEXT = "#1e293b"
COLOR_TEXT_LIGHT = "#64748b"
COLOR_SUCCESS = "#22c55e"

# --- Database Manager ---
class DatabaseManager:
    """Manages SQLite database for storing FTP connections and history."""
    
    def __init__(self, db_path=None):
        if db_path is None:
            db_path = get_settings_db_path()
        
        self.db_path = db_path
        self.init_database()
        
        # Set secure file permissions on database file (Linux/Unix only)
        if platform.system() != "Windows":
            try:
                os.chmod(self.db_path, stat.S_IRUSR | stat.S_IWUSR)
            except OSError:
                pass
    
    def get_connection(self):
        """Get database connection."""
        if platform.system() != "Windows" and os.path.exists(self.db_path):
            try:
                os.chmod(self.db_path, stat.S_IRUSR | stat.S_IWUSR)
            except OSError:
                pass
        return sqlite3.connect(self.db_path)
    
    def init_database(self):
        """Initialize database tables."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Saved FTP connections table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ftp_connections (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                protocol TEXT NOT NULL,
                host TEXT,
                port TEXT,
                username TEXT,
                password TEXT,
                use_tls INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_used TIMESTAMP,
                is_favorite INTEGER DEFAULT 0
            )
        """)
        
        # FTP operation history
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ftp_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                connection_name TEXT,
                operation TEXT,
                local_path TEXT,
                remote_path TEXT,
                file_size INTEGER,
                status TEXT,
                error_message TEXT,
                started_at TIMESTAMP,
                completed_at TIMESTAMP,
                duration_seconds REAL
            )
        """)
        
        # Directory bookmarks
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ftp_bookmarks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                connection_name TEXT,
                path TEXT,
                name TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Transfer logs for advanced logging
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ftp_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                level TEXT,
                message TEXT,
                connection_name TEXT
            )
        """)
        
        conn.commit()
        conn.close()
    
    def save_connection(self, name, protocol, host, port, username, password, use_tls=False, is_favorite=False):
        """Save a connection profile."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        encoded_password = base64.b64encode(password.encode()).decode() if password else ""
        
        try:
            cursor.execute("""
                INSERT OR REPLACE INTO ftp_connections 
                (name, protocol, host, port, username, password, use_tls, is_favorite, last_used)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """, (name, protocol, host, port, username, encoded_password, 1 if use_tls else 0, 1 if is_favorite else 0))
            conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False
        finally:
            conn.close()
    
    def get_connections(self, favorites_only=False):
        """Get all saved connections."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        if favorites_only:
            cursor.execute("SELECT * FROM ftp_connections WHERE is_favorite = 1 ORDER BY last_used DESC")
        else:
            cursor.execute("SELECT * FROM ftp_connections ORDER BY is_favorite DESC, last_used DESC")
        
        rows = cursor.fetchall()
        conn.close()
        
        connections = []
        for row in rows:
            password = base64.b64decode(row[6]).decode() if row[6] else ""
            connections.append({
                'id': row[0],
                'name': row[1],
                'protocol': row[2],
                'host': row[3] or "",
                'port': row[4] or "",
                'username': row[5] or "",
                'password': password,
                'use_tls': bool(row[7]),
                'created_at': row[8],
                'last_used': row[9],
                'is_favorite': bool(row[10])
            })
        
        return connections
    
    def load_connection(self, name):
        """Load a connection by name."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM ftp_connections WHERE name = ?", (name,))
        row = cursor.fetchone()
        
        if row:
            password = base64.b64decode(row[6]).decode() if row[6] else ""
            cursor.execute("UPDATE ftp_connections SET last_used = CURRENT_TIMESTAMP WHERE name = ?", (name,))
            conn.commit()
            conn.close()
            
            return {
                'name': row[1],
                'protocol': row[2],
                'host': row[3] or "",
                'port': row[4] or "",
                'username': row[5] or "",
                'password': password,
                'use_tls': bool(row[7])
            }
        conn.close()
        return None
    
    def delete_connection(self, name):
        """Delete a saved connection. Returns True if deleted, False otherwise."""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute("DELETE FROM ftp_connections WHERE name = ?", (name,))
            rows_deleted = cursor.rowcount
            conn.commit()
            conn.close()
            return rows_deleted > 0
        except Exception as e:
            print(f"Error deleting connection: {e}")
            return False
    
    def add_history(self, connection_name, operation, local_path, remote_path, status, error_message=None, file_size=0, duration=0):
        """Add an operation to history."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        start_datetime = datetime.fromtimestamp(datetime.now().timestamp() - duration)
        start_time_str = start_datetime.strftime("%Y-%m-%d %H:%M:%S")
        
        cursor.execute("""
            INSERT INTO ftp_history 
            (connection_name, operation, local_path, remote_path, file_size, status, error_message, started_at, completed_at, duration_seconds)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), ?)
        """, (connection_name, operation, local_path, remote_path, file_size, status, error_message, start_time_str, duration))
        
        conn.commit()
        conn.close()
    
    def get_history(self, limit=100, connection_name=None):
        """Get operation history."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        if connection_name:
            cursor.execute("""
                SELECT * FROM ftp_history 
                WHERE connection_name = ?
                ORDER BY started_at DESC 
                LIMIT ?
            """, (connection_name, limit))
        else:
            cursor.execute("""
                SELECT * FROM ftp_history 
                ORDER BY started_at DESC 
                LIMIT ?
            """, (limit,))
        
        rows = cursor.fetchall()
        conn.close()
        
        history = []
        for row in rows:
            history.append({
                'id': row[0],
                'connection_name': row[1],
                'operation': row[2],
                'local_path': row[3],
                'remote_path': row[4],
                'file_size': row[5],
                'status': row[6],
                'error_message': row[7],
                'started_at': row[8],
                'completed_at': row[9],
                'duration_seconds': row[10]
            })
        return history
    
    def add_bookmark(self, connection_name, path, name):
        """Add a directory bookmark."""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                INSERT INTO ftp_bookmarks (connection_name, path, name)
                VALUES (?, ?, ?)
            """, (connection_name, path, name))
            conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False
        finally:
            conn.close()
    
    def get_bookmarks(self, connection_name=None):
        """Get directory bookmarks."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        if connection_name:
            cursor.execute("""
                SELECT id, path, name, created_at FROM ftp_bookmarks
                WHERE connection_name = ?
                ORDER BY created_at DESC
            """, (connection_name,))
        else:
            cursor.execute("""
                SELECT id, connection_name, path, name, created_at FROM ftp_bookmarks
                ORDER BY created_at DESC
            """)
        
        results = cursor.fetchall()
        conn.close()
        
        bookmarks = []
        for row in results:
            if connection_name:
                bookmarks.append({
                    'id': row[0],
                    'path': row[1],
                    'name': row[2],
                    'created_at': row[3]
                })
            else:
                bookmarks.append({
                    'id': row[0],
                    'connection_name': row[1],
                    'path': row[2],
                    'name': row[3],
                    'created_at': row[4]
                })
        
        return bookmarks
    
    def delete_bookmark(self, bookmark_id):
        """Delete a bookmark."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM ftp_bookmarks WHERE id = ?", (bookmark_id,))
        conn.commit()
        conn.close()
    
    def add_log(self, level, message, connection_name=None):
        """Add a log entry."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO ftp_logs (level, message, connection_name)
            VALUES (?, ?, ?)
        """, (level, message, connection_name))
        conn.commit()
        conn.close()
    
    def get_logs(self, level=None, connection_name=None, limit=1000):
        """Get log entries."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        query = "SELECT timestamp, level, message, connection_name FROM ftp_logs WHERE 1=1"
        params = []
        
        if level:
            query += " AND level = ?"
            params.append(level)
        
        if connection_name:
            query += " AND connection_name = ?"
            params.append(connection_name)
        
        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)
        
        cursor.execute(query, params)
        results = cursor.fetchall()
        conn.close()
        
        logs = []
        for row in results:
            logs.append({
                'timestamp': row[0],
                'level': row[1],
                'message': row[2],
                'connection_name': row[3]
            })
        
        return logs

# Initialize database manager
db_manager = DatabaseManager()

# --- FTP Client Classes ---
class FTPClient:
    """FTP/FTPS client wrapper."""
    
    def __init__(self, host, port, username, password, use_tls=False):
        self.host = host
        self.port = int(port) if port else (990 if use_tls else 21)
        self.username = username
        self.password = password
        self.use_tls = use_tls
        self.connection = None
    
    def connect(self):
        """Connect to FTP server."""
        try:
            # Validate host
            if not self.host or not self.host.strip():
                return False, "Host cannot be empty"
            
            # Add timeout for connection
            timeout = 10
            
            if self.use_tls:
                self.connection = FTP_TLS()
                self.connection.connect(self.host, self.port, timeout=timeout)
                self.connection.login(self.username, self.password)
                self.connection.prot_p()  # Switch to secure data connection
            else:
                self.connection = FTP()
                self.connection.connect(self.host, self.port, timeout=timeout)
                self.connection.login(self.username, self.password)
            return True, "Connected successfully"
        except socket.gaierror as e:
            # DNS resolution error
            error_code = getattr(e, 'errno', None)
            if error_code == 11001 or 'getaddrinfo failed' in str(e).lower():
                return False, f"Cannot resolve hostname '{self.host}'. Please check:\n- Hostname is correct\n- Internet connection is active\n- DNS settings are correct"
            return False, f"DNS resolution error: {e}"
        except socket.timeout:
            return False, f"Connection timeout. Server '{self.host}:{self.port}' did not respond."
        except ConnectionRefusedError:
            return False, f"Connection refused. Server '{self.host}:{self.port}' is not accepting connections."
        except ftplib.error_perm as e:
            return False, f"Authentication failed: {e}"
        except ftplib.error_temp as e:
            return False, f"Temporary error: {e}"
        except Exception as e:
            error_msg = str(e)
            # Make Windows error codes more user-friendly
            if '11001' in error_msg or 'getaddrinfo failed' in error_msg.lower():
                return False, f"Cannot resolve hostname '{self.host}'. Please check the hostname and your network connection."
            return False, f"Connection error: {error_msg}"
    
    def disconnect(self):
        """Disconnect from FTP server."""
        if self.connection:
            try:
                self.connection.quit()
            except:
                try:
                    self.connection.close()
                except:
                    pass
            self.connection = None
    
    def list_files(self, path="/"):
        """List files in remote directory."""
        if not self.connection:
            return []
        try:
            self.connection.cwd(path)
            files = []
            self.connection.retrlines('LIST', files.append)
            return files
        except Exception as e:
            return []
    
    def get_current_dir(self):
        """Get current working directory."""
        if not self.connection:
            return "/"
        try:
            return self.connection.pwd()
        except:
            return "/"
    
    def change_dir(self, path):
        """Change remote directory."""
        if not self.connection:
            return False
        try:
            self.connection.cwd(path)
            return True
        except:
            return False
    
    def upload_file(self, local_path, remote_path, callback=None):
        """Upload a file."""
        if not self.connection:
            return False, "Not connected"
        try:
            with open(local_path, 'rb') as f:
                if self.use_tls:
                    self.connection.storbinary(f'STOR {remote_path}', f, callback=callback)
                else:
                    self.connection.storbinary(f'STOR {remote_path}', f, callback=callback)
            return True, "Upload successful"
        except Exception as e:
            return False, str(e)
    
    def download_file(self, remote_path, local_path, callback=None):
        """Download a file."""
        if not self.connection:
            return False, "Not connected"
        try:
            with open(local_path, 'wb') as f:
                # Use callback if provided, otherwise use f.write
                if callback:
                    def write_with_callback(data):
                        f.write(data)
                        callback(data)
                    self.connection.retrbinary(f'RETR {remote_path}', write_with_callback)
                else:
                    self.connection.retrbinary(f'RETR {remote_path}', f.write)
            return True, "Download successful"
        except Exception as e:
            return False, str(e)
    
    def delete_file(self, remote_path):
        """Delete a remote file."""
        if not self.connection:
            return False, "Not connected"
        try:
            self.connection.delete(remote_path)
            return True, "Delete successful"
        except Exception as e:
            return False, str(e)
    
    def create_dir(self, remote_path):
        """Create a remote directory."""
        if not self.connection:
            return False, "Not connected"
        try:
            self.connection.mkd(remote_path)
            return True, "Directory created"
        except Exception as e:
            return False, str(e)
    
    def rename_file(self, old_path, new_path):
        """Rename a remote file or directory."""
        if not self.connection:
            return False, "Not connected"
        try:
            self.connection.rename(old_path, new_path)
            return True, "Rename successful"
        except Exception as e:
            return False, str(e)
    
    def delete_dir(self, remote_path):
        """Delete a remote directory (recursively if not empty)."""
        if not self.connection:
            return False, "Not connected"
        
        # Normalize path - ensure it doesn't end with /
        remote_path = remote_path.rstrip('/') or '/'
        
        try:
            # First, try to delete as empty directory
            try:
                self.connection.rmd(remote_path)
                return True, "Directory deleted"
            except (ftplib.error_perm, ftplib.error_temp, Exception) as rmd_error:
                # Check if this is a "directory not empty" error
                error_str = str(rmd_error).lower()
                error_code = None
                
                # Extract error code if it's an ftplib error
                if isinstance(rmd_error, (ftplib.error_perm, ftplib.error_temp)):
                    error_code = getattr(rmd_error, 'args', [None])[0] if rmd_error.args else None
                    if error_code:
                        error_str = str(error_code).lower() + " " + error_str
                
                # Check for various "not empty" error indicators
                is_not_empty_error = (
                    "550" in error_str or 
                    "not empty" in error_str or 
                    "directory not empty" in error_str or 
                    "could not delete" in error_str or
                    "directory not empty" in error_str or
                    (isinstance(rmd_error, ftplib.error_perm) and "550" in str(rmd_error))
                )
                
                if is_not_empty_error:
                    # Directory is not empty, need to delete contents first
                    try:
                        # Save current directory
                        try:
                            original_dir = self.connection.pwd()
                        except:
                            original_dir = "/"
                        
                        # Change to the directory we want to delete
                        try:
                            self.connection.cwd(remote_path)
                        except Exception as cwd_err:
                            return False, f"Cannot access directory: {str(cwd_err)}"
                        
                        # List all files and directories
                        files = []
                        try:
                            self.connection.retrlines('LIST', files.append)
                        except Exception as list_err:
                            # Try to go back before returning error
                            try:
                                self.connection.cwd(original_dir)
                            except:
                                pass
                            return False, f"Cannot list directory contents: {str(list_err)}"
                        
                        # Process each item
                        items_to_delete = []
                        for line in files:
                            if not line.strip():
                                continue
                            
                            # Parse LIST output: drwxr-xr-x 2 user group 4096 date time name
                            parts = line.split()
                            if len(parts) < 9:
                                # Try alternative parsing for different LIST formats
                                if len(parts) >= 4:
                                    # Might be: drwxr-xr-x size date time name
                                    parts = parts[:1] + [''] + [''] + parts[1:]
                            
                            if len(parts) < 9:
                                continue
                            
                            # Check if it's a directory (starts with 'd')
                            is_dir = line.startswith('d')
                            item_name = parts[-1]
                            
                            # Skip . and ..
                            if item_name in ['.', '..']:
                                continue
                            
                            # Build absolute path from root
                            if remote_path == "/":
                                item_path = f"/{item_name}"
                            else:
                                item_path = f"{remote_path}/{item_name}"
                            
                            items_to_delete.append((item_path, item_name, is_dir))
                        
                        # Go back to original directory before deleting
                        try:
                            self.connection.cwd(original_dir)
                        except:
                            # If we can't go back, try parent
                            try:
                                if remote_path != "/":
                                    parent = '/'.join(remote_path.split('/')[:-1]) or '/'
                                    self.connection.cwd(parent)
                            except:
                                pass  # Continue anyway
                        
                        # Delete all items (files first, then directories)
                        # Sort: files first, then directories
                        items_to_delete.sort(key=lambda x: (x[2], x[1]))  # is_dir=False (files) come first
                        
                        for item_path, item_name, is_dir in items_to_delete:
                            if is_dir:
                                # Recursively delete subdirectory
                                success, msg = self.delete_dir(item_path)
                                if not success:
                                    return False, f"Failed to delete subdirectory '{item_name}': {msg}"
                            else:
                                # Delete file using absolute path
                                try:
                                    self.connection.delete(item_path)
                                except Exception as del_err:
                                    # Try relative path if absolute fails
                                    try:
                                        # Change to parent directory and use relative path
                                        parent_path = '/'.join(item_path.split('/')[:-1]) or '/'
                                        if parent_path != "/":
                                            self.connection.cwd(parent_path)
                                        self.connection.delete(item_name)
                                        # Go back
                                        try:
                                            self.connection.cwd(original_dir)
                                        except:
                                            pass
                                    except:
                                        return False, f"Failed to delete file '{item_name}': {str(del_err)}"
                        
                        # Now try to delete the empty directory (use absolute path)
                        try:
                            self.connection.rmd(remote_path)
                            return True, "Directory deleted recursively"
                        except Exception as final_err:
                            return False, f"Deleted contents but failed to remove directory: {str(final_err)}"
                            
                    except Exception as rec_error:
                        import traceback
                        error_details = traceback.format_exc()
                        return False, f"Recursive delete failed: {str(rec_error)}\nDetails: {error_details}"
                else:
                    # Some other error (permission denied, etc.)
                    return False, f"Cannot delete directory: {str(rmd_error)}"
        except Exception as e:
            import traceback
            error_details = traceback.format_exc()
            return False, f"Unexpected error: {str(e)}\nDetails: {error_details}"
    
    def get_file_size(self, remote_path):
        """Get file size."""
        if not self.connection:
            return None
        try:
            size = self.connection.size(remote_path)
            return size if size is not None else 0
        except:
            return None
    
    def get_file_info(self, remote_path):
        """Get detailed file information."""
        if not self.connection:
            return None
        try:
            # Try to get file size
            size = self.get_file_size(remote_path)
            
            # Try to get modification time
            mtime = None
            try:
                mdtm = self.connection.voidcmd(f"MDTM {remote_path}")
                if mdtm.startswith("213"):
                    mtime_str = mdtm.split()[1]
                    mtime = datetime.strptime(mtime_str, "%Y%m%d%H%M%S")
            except:
                pass
            
            # Try to get permissions and other info from LIST
            permissions = None
            owner = None
            group = None
            ctime = None
            try:
                # Get detailed listing
                lines = []
                self.connection.retrlines(f'LIST {remote_path}', lines.append)
                if lines:
                    # Parse LIST output (format: -rw-r--r-- 1 owner group size date time name)
                    line = lines[0] if lines else ""
                    parts = line.split()
                    if len(parts) >= 9:
                        permissions = parts[0]  # e.g., "-rw-r--r--"
                        owner = parts[2] if len(parts) > 2 else None
                        group = parts[3] if len(parts) > 3 else None
            except:
                pass
            
            return {
                'size': size,
                'mtime': mtime,
                'permissions': permissions,
                'owner': owner,
                'group': group,
                'ctime': ctime  # Created time - FTP doesn't always support this
            }
        except:
            return None
    
    def set_permissions(self, remote_path, mode):
        """Set file permissions (chmod). Returns (success, message)."""
        if not self.connection:
            return False, "Not connected"
        try:
            # Try SITE CHMOD command (not all FTP servers support this)
            mode_str = oct(mode)[2:] if isinstance(mode, int) else str(mode)
            response = self.connection.sendcmd(f'SITE CHMOD {mode_str} {remote_path}')
            if '200' in response or '250' in response:
                return True, "Permissions updated"
            else:
                return False, f"Server response: {response}"
        except Exception as e:
            return False, f"Failed to set permissions: {e}"

class SFTPClient:
    """SFTP client wrapper using paramiko."""
    
    def __init__(self, host, port, username, password):
        self.host = host
        self.port = int(port) if port else 22
        self.username = username
        self.password = password
        self.client = None
        self.sftp = None
    
    def connect(self):
        """Connect to SFTP server."""
        if not SFTP_AVAILABLE:
            return False, "paramiko not installed. Install with: pip install paramiko"
        try:
            # Validate host
            if not self.host or not self.host.strip():
                return False, "Host cannot be empty"
            
            if not _paramiko_module:
                return False, "paramiko module not available"
            self.client = _paramiko_module.SSHClient()
            self.client.set_missing_host_key_policy(_paramiko_module.AutoAddPolicy())
            self.client.connect(self.host, self.port, self.username, self.password, timeout=10)
            self.sftp = self.client.open_sftp()
            return True, "Connected successfully"
        except socket.gaierror as e:
            error_code = getattr(e, 'errno', None)
            if error_code == 11001 or 'getaddrinfo failed' in str(e).lower():
                return False, f"Cannot resolve hostname '{self.host}'. Please check:\n- Hostname is correct\n- Internet connection is active\n- DNS settings are correct"
            return False, f"DNS resolution error: {e}"
        except socket.timeout:
            return False, f"Connection timeout. Server '{self.host}:{self.port}' did not respond."
        except ConnectionRefusedError:
            return False, f"Connection refused. Server '{self.host}:{self.port}' is not accepting connections."
        except Exception as e:
            error_type = type(e).__name__
            if 'Authentication' in error_type or 'auth' in str(e).lower():
                return False, "Authentication failed. Please check username and password."
            elif 'SSH' in error_type or 'ssh' in str(e).lower():
                return False, f"SSH error: {e}"
            else:
                error_msg = str(e)
                if '11001' in error_msg or 'getaddrinfo failed' in error_msg.lower():
                    return False, f"Cannot resolve hostname '{self.host}'. Please check the hostname and your network connection."
                return False, f"Connection error: {error_msg}"
        except Exception as e:
            error_msg = str(e)
            if '11001' in error_msg or 'getaddrinfo failed' in error_msg.lower():
                return False, f"Cannot resolve hostname '{self.host}'. Please check the hostname and your network connection."
            return False, f"Connection error: {error_msg}"
    
    def disconnect(self):
        """Disconnect from SFTP server."""
        if self.sftp:
            self.sftp.close()
        if self.client:
            self.client.close()
        self.sftp = None
        self.client = None
    
    def list_files(self, path="/"):
        """List files in remote directory."""
        if not self.sftp:
            return []
        try:
            files = []
            for item in self.sftp.listdir_attr(path):
                files.append(f"{'d' if stat.S_ISDIR(item.st_mode) else '-'} {item.st_mode:04o} {item.st_size:10d} {datetime.fromtimestamp(item.st_mtime).strftime('%b %d %H:%M')} {item.filename}")
            return files
        except Exception as e:
            return []
    
    def get_current_dir(self):
        """Get current working directory."""
        if not self.sftp:
            return "/"
        try:
            return self.sftp.getcwd()
        except:
            return "/"
    
    def change_dir(self, path):
        """Change remote directory."""
        if not self.sftp:
            return False
        try:
            self.sftp.chdir(path)
            return True
        except:
            return False
    
    def upload_file(self, local_path, remote_path, callback=None):
        """Upload a file."""
        if not self.sftp:
            return False, "Not connected"
        try:
            self.sftp.put(local_path, remote_path, callback=callback)
            return True, "Upload successful"
        except Exception as e:
            return False, str(e)
    
    def download_file(self, remote_path, local_path, callback=None):
        """Download a file."""
        if not self.sftp:
            return False, "Not connected"
        try:
            self.sftp.get(remote_path, local_path, callback=callback)
            return True, "Download successful"
        except Exception as e:
            return False, str(e)
    
    def delete_file(self, remote_path):
        """Delete a remote file."""
        if not self.sftp:
            return False, "Not connected"
        try:
            self.sftp.remove(remote_path)
            return True, "Delete successful"
        except Exception as e:
            return False, str(e)
    
    def create_dir(self, remote_path):
        """Create a remote directory."""
        if not self.sftp:
            return False, "Not connected"
        try:
            self.sftp.mkdir(remote_path)
            return True, "Directory created"
        except Exception as e:
            return False, str(e)
    
    def rename_file(self, old_path, new_path):
        """Rename a remote file or directory."""
        if not self.sftp:
            return False, "Not connected"
        try:
            self.sftp.rename(old_path, new_path)
            return True, "Rename successful"
        except Exception as e:
            return False, str(e)
    
    def delete_dir(self, remote_path):
        """Delete a remote directory (recursively if not empty)."""
        if not self.sftp:
            return False, "Not connected"
        try:
            import stat
            # Check if it's a directory
            try:
                attrs = self.sftp.stat(remote_path)
                if not stat.S_ISDIR(attrs.st_mode):
                    # It's a file, use remove
                    self.sftp.remove(remote_path)
                    return True, "File deleted"
            except:
                pass
            
            # It's a directory, try to delete recursively
            try:
                # List all items in directory
                items = self.sftp.listdir_attr(remote_path)
                
                for item in items:
                    item_name = item.filename
                    if item_name in ['.', '..']:
                        continue
                    
                    item_path = f"{remote_path.rstrip('/')}/{item_name}" if remote_path != "/" else f"/{item_name}"
                    
                    # Recursively delete subdirectories or files
                    if stat.S_ISDIR(item.st_mode):
                        success, msg = self.delete_dir(item_path)
                        if not success:
                            return False, f"Failed to delete subdirectory {item_name}: {msg}"
                    else:
                        try:
                            self.sftp.remove(item_path)
                        except Exception as del_err:
                            return False, f"Failed to delete file {item_name}: {str(del_err)}"
                
                # Now delete the empty directory
                self.sftp.rmdir(remote_path)
                return True, "Directory deleted recursively"
            except Exception as rmd_error:
                # Try simple rmdir first (in case directory is already empty)
                try:
                    self.sftp.rmdir(remote_path)
                    return True, "Directory deleted"
                except:
                    return False, f"Failed to delete directory: {str(rmd_error)}"
        except Exception as e:
            return False, str(e)
    
    def get_file_size(self, remote_path):
        """Get file size."""
        if not self.sftp:
            return None
        try:
            return self.sftp.stat(remote_path).st_size
        except:
            return None
    
    def get_file_info(self, remote_path):
        """Get detailed file information."""
        if not self.sftp:
            return None
        try:
            stat_info = self.sftp.stat(remote_path)
            return {
                'size': stat_info.st_size,
                'mtime': datetime.fromtimestamp(stat_info.st_mtime),
                'permissions': stat_info.st_mode
            }
        except:
            return None

# Global client instance
current_client = None
current_connection_name = None

# --- Transfer Queue System ---
class TransferItem:
    """Represents a single transfer item in the queue."""
    def __init__(self, operation, local_path, remote_path, size=0):
        self.id = int(time.time() * 1000000)  # Unique ID
        self.operation = operation  # 'upload' or 'download'
        self.local_path = local_path
        self.remote_path = remote_path
        self.size = size
        self.status = 'pending'  # pending, running, paused, completed, failed, cancelled
        self.progress = 0  # 0-100
        self.speed = 0  # bytes per second
        self.eta = 0  # seconds remaining
        self.error = None
        self.start_time = None
        self.bytes_transferred = 0
        self.thread = None
        self.stop_event = threading.Event()

class TransferQueue:
    """Manages the transfer queue with pause/resume/cancel capabilities."""
    def __init__(self, max_concurrent=3):
        self.queue = deque()
        self.active_transfers = []
        self.max_concurrent = max_concurrent
        self.lock = threading.Lock()
        self.speed_limit = 0  # 0 = unlimited, bytes per second
    
    def add(self, transfer_item):
        """Add a transfer to the queue."""
        with self.lock:
            self.queue.append(transfer_item)
        self._process_queue()
    
    def _process_queue(self):
        """Process the queue and start transfers if slots available."""
        with self.lock:
            # Remove completed/failed/cancelled transfers
            self.active_transfers = [t for t in self.active_transfers if t.status in ('running', 'paused')]
            
            # Start new transfers if we have capacity
            while len(self.active_transfers) < self.max_concurrent and self.queue:
                transfer = self.queue.popleft()
                if transfer.status == 'pending':
                    transfer.status = 'running'
                    self.active_transfers.append(transfer)
    
    def pause(self, transfer_id):
        """Pause a transfer."""
        with self.lock:
            for transfer in self.active_transfers:
                if transfer.id == transfer_id:
                    transfer.status = 'paused'
                    transfer.stop_event.set()
                    return True
        return False
    
    def resume(self, transfer_id):
        """Resume a paused transfer."""
        with self.lock:
            for transfer in self.active_transfers + list(self.queue):
                if transfer.id == transfer_id and transfer.status == 'paused':
                    transfer.status = 'pending'
                    transfer.stop_event.clear()
                    if transfer not in self.queue:
                        self.queue.append(transfer)
                    self._process_queue()
                    return True
        return False
    
    def cancel(self, transfer_id):
        """Cancel a transfer."""
        with self.lock:
            # Check active transfers
            for transfer in self.active_transfers:
                if transfer.id == transfer_id:
                    transfer.status = 'cancelled'
                    transfer.stop_event.set()
                    self.active_transfers.remove(transfer)
                    self._process_queue()
                    return True
            # Check queue
            for transfer in list(self.queue):
                if transfer.id == transfer_id:
                    transfer.status = 'cancelled'
                    self.queue.remove(transfer)
                    return True
        return False
    
    def get_all(self):
        """Get all transfers (active + queued)."""
        with self.lock:
            return list(self.active_transfers) + list(self.queue)
    
    def clear_completed(self):
        """Clear completed transfers."""
        with self.lock:
            self.queue = deque([t for t in self.queue if t.status not in ('completed', 'failed', 'cancelled')])
            self.active_transfers = [t for t in self.active_transfers if t.status not in ('completed', 'failed', 'cancelled')]
    
    def set_speed_limit(self, limit_bytes_per_sec):
        """Set speed limit for transfers (0 = unlimited)."""
        with self.lock:
            self.speed_limit = limit_bytes_per_sec

# Global transfer queue
transfer_queue = TransferQueue(max_concurrent=3)

# --- GUI Functions ---
def set_busy(is_busy: bool, text: str = ""):
    """Enable/disable UI and show/hide the loading spinner."""
    if is_busy:
        status_var.set(text)
        progress_bar.start(10)
        progress_frame.pack(fill="x", side="bottom", padx=0, pady=0)
        root.config(cursor="watch")
        try:
            connect_btn.config(state="disabled")
            upload_btn.config(state="disabled")
            download_btn.config(state="disabled")
        except:
            pass
    else:
        status_var.set("")
        progress_bar.stop()
        progress_frame.pack_forget()
        root.config(cursor="")
        try:
            connect_btn.config(state="normal")
            upload_btn.config(state="normal")
            download_btn.config(state="normal")
        except:
            pass

def connect_worker():
    """Background worker for connecting to FTP/SFTP server."""
    global current_client, current_connection_name
    
    protocol = protocol_var.get()
    host = host_var.get().strip()
    port = port_var.get().strip()
    username = username_var.get().strip()
    password = password_var.get().strip()
    use_tls = use_tls_var.get()
    
    # Validate inputs
    if not host:
        root.after(0, lambda: messagebox.showerror("Error", "Please enter a hostname or IP address"))
        set_busy(False)
        return
    
    if not username:
        root.after(0, lambda: messagebox.showerror("Error", "Please enter a username"))
        set_busy(False)
        return
    
    # Validate port
    if port:
        try:
            port_int = int(port)
            if port_int < 1 or port_int > 65535:
                root.after(0, lambda: messagebox.showerror("Error", "Port must be between 1 and 65535"))
                set_busy(False)
                return
        except ValueError:
            root.after(0, lambda: messagebox.showerror("Error", "Port must be a valid number"))
            set_busy(False)
            return
    
    def _connect():
        global current_client, current_connection_name
        
        try:
            if protocol == "sftp":
                if not SFTP_AVAILABLE:
                    root.after(0, lambda: messagebox.showerror("Error", "paramiko not installed.\n\nInstall with: pip install paramiko"))
                    set_busy(False)
                    return
                client = SFTPClient(host, port, username, password)
            else:
                client = FTPClient(host, port, username, password, use_tls)
            
            success, message = client.connect()
            
            if success:
                current_client = client
                current_connection_name = f"{username}@{host}:{port}"
                
                # Save connection
                conn_name = f"{username}@{host}"
                db_manager.save_connection(conn_name, protocol, host, port, username, password, use_tls)
                
                # Update UI
                root.after(0, lambda: update_connection_status(True, message))
                root.after(0, lambda: refresh_remote_files_wrapper())
            else:
                root.after(0, lambda: messagebox.showerror("Connection Failed", message))
                set_busy(False)
        except Exception as e:
            root.after(0, lambda: messagebox.showerror("Error", f"Connection error: {e}"))
            set_busy(False)
    
    threading.Thread(target=_connect, daemon=True).start()

# Global variable to track connection settings visibility
connection_settings_visible = True

def toggle_connection_settings():
    """Toggle connection settings form visibility."""
    global connection_settings_visible
    connection_settings_visible = not connection_settings_visible
    
    if connection_settings_visible:
        form_frame.pack(fill="x", padx=10, pady=5)
        expand_collapse_btn.config(text="⚙️ Settings")
    else:
        form_frame.pack_forget()
        expand_collapse_btn.config(text="⚙️ Show Settings")

def update_connection_status(connected, message):
    """Update connection status display."""
    global connection_settings_visible
    
    if connected:
        connection_label.config(text=f"✓ {message}", fg=COLOR_SUCCESS, font=("TkDefaultFont", 9, "bold"))
        # Hide connection settings form after successful connection
        if connection_settings_visible:
            form_frame.pack_forget()
            connection_settings_visible = False
            expand_collapse_btn.config(text="⚙️ Show Settings")
        
        # Disable connect button, enable disconnect
        connect_btn.config(text="🔌 Disconnect", command=disconnect_worker, bg=COLOR_DANGER)
        
        # Show remote frame
        if not remote_frame.winfo_ismapped():
            remote_frame.pack(side="left", fill="both", expand=True, padx=(0, 5), pady=10)
        # Adjust local frame to take less space (re-pack it)
        local_frame.pack_forget()
        local_frame.pack(side="right", fill="both", expand=True, padx=(5, 0), pady=10)
        update_status_info()
    else:
        connection_label.config(text="Not connected", fg=COLOR_TEXT_LIGHT, font=("TkDefaultFont", 9))
        # Re-enable connect button
        connect_btn.config(text="🔌 Connect", command=lambda: (set_busy(True, "Connecting..."), connect_worker()), bg=COLOR_PRIMARY)
        
        # Hide remote frame
        remote_frame.pack_forget()
        # Local frame takes full width (re-pack it)
        local_frame.pack_forget()
        local_frame.pack(side="left", fill="both", expand=True, padx=0, pady=10)
        status_info_var.set("Not connected")
    set_busy(False)

def disconnect_worker():
    """Disconnect from FTP/SFTP server."""
    global current_client, current_connection_name
    
    def _disconnect():
        try:
            if current_client:
                current_client.disconnect()
                current_client = None
                current_connection_name = None
                db_manager.add_log("INFO", "Disconnected from server", None)
                root.after(0, lambda: update_connection_status(False, "Disconnected"))
                root.after(0, lambda: refresh_local_files_wrapper())
        except Exception as e:
            root.after(0, lambda: messagebox.showerror("Error", f"Disconnect error: {e}"))
        finally:
            set_busy(False)
    
    set_busy(True, "Disconnecting...")
    threading.Thread(target=_disconnect, daemon=True).start()

# Global lock to prevent concurrent refresh operations
refresh_lock = threading.Lock()
refresh_in_progress = False
pending_refresh = False

def refresh_remote_files():
    """Refresh remote file list with thread-safe protection."""
    global refresh_in_progress, pending_refresh
    
    if not current_client:
        messagebox.showwarning("Not Connected", "Please connect to a server first")
        return
    
    # Check if refresh is already in progress
    if refresh_in_progress:
        pending_refresh = True
        print("Refresh already in progress, queuing another refresh...")
        return
    
    def _refresh():
        global refresh_in_progress, pending_refresh
        
        # Acquire lock to prevent concurrent refreshes
        if not refresh_lock.acquire(blocking=False):
            print("Refresh lock already held, skipping...")
            return
        
        try:
            refresh_in_progress = True
            pending_refresh = False
            
            # Get current path before listing (in case it changes)
            current_path = current_client.get_current_dir()
            if not current_path:
                current_path = "/"
            
            print(f"Refresh: Starting refresh for {current_path}")
            
            # List files
            files = current_client.list_files(current_path)
            
            # Ensure we have a valid files list (even if empty)
            if files is None:
                files = []
            
            # Debug output
            print(f"Refresh: Got {len(files)} files from {current_path}")
            
            # Update UI on main thread - capture files and path to avoid closure issues
            files_to_update = files.copy() if isinstance(files, list) else list(files) if files else []
            path_to_update = current_path
            
            def update_ui():
                try:
                    # Double-check client is still connected before updating
                    if not current_client:
                        print("Refresh: Client disconnected, skipping UI update")
                        return
                    
                    # Verify we have valid data
                    if not files_to_update and path_to_update == "/":
                        print("Refresh: Empty root directory, showing empty list")
                    elif not files_to_update:
                        print(f"Refresh: No files in {path_to_update}, showing parent directory only")
                    
                    update_remote_list(files_to_update, path_to_update)
                    print(f"Refresh: UI update scheduled with {len(files_to_update)} files")
                except Exception as e:
                    import traceback
                    error_trace = traceback.format_exc()
                    print(f"Error in update_ui: {error_trace}")
                    # Don't clear on error - preserve existing list
                    try:
                        if current_client:
                            print(f"Refresh: Error occurred, preserving existing list")
                    except:
                        pass
            
            root.after(0, update_ui)
            
            # If another refresh was requested while we were working, do it now
            if pending_refresh:
                print("Refresh: Pending refresh detected, scheduling another refresh...")
                root.after(500, refresh_remote_files)  # Wait 500ms before next refresh
            
        except Exception as e:
            import traceback
            error_msg = traceback.format_exc()
            print(f"Error refreshing remote files: {error_msg}")
            root.after(0, lambda: messagebox.showerror("Error", f"Failed to list files: {e}"))
            # Try to restore previous state or show empty list
            try:
                if current_client:
                    current_path = current_client.get_current_dir() or "/"
                    root.after(0, lambda: update_remote_list([], current_path))
            except:
                pass
        finally:
            refresh_in_progress = False
            refresh_lock.release()
            print("Refresh: Lock released")
    
    threading.Thread(target=_refresh, daemon=True).start()

def refresh_local_files():
    """Refresh local file list with metadata."""
    try:
        # Check if local_listbox exists
        if 'local_listbox' not in globals():
            return
        
        local_path = local_path_var.get()
        if not local_path or not os.path.exists(local_path):
            local_path = os.getcwd()
            local_path_var.set(local_path)
        
        # Clear tree/listbox
        if hasattr(local_listbox, 'delete'):  # Treeview
            for item in local_listbox.get_children():
                local_listbox.delete(item)
        else:  # Listbox
            local_listbox.delete(0, tk.END)
        
        # Add parent directory if not at root
        parent_path = os.path.dirname(local_path)
        if parent_path != local_path and os.path.exists(parent_path):
            if hasattr(local_listbox, 'insert'):  # Treeview
                local_listbox.insert("", "end", text="📁", values=("..", "", "", "", ""))
            else:  # Listbox
                local_listbox.insert(0, "📁 ..")
        
        try:
            items = sorted(os.listdir(local_path))
            for item_name in items:
                item_path = os.path.join(local_path, item_name)
                try:
                    stat_info = os.stat(item_path)
                    is_dir = os.path.isdir(item_path)
                    
                    # Format size
                    size = stat_info.st_size if not is_dir else 0
                    size_str = format_file_size(size) if not is_dir else "<DIR>"
                    
                    # Format dates
                    mtime = datetime.fromtimestamp(stat_info.st_mtime)
                    mtime_str = mtime.strftime("%Y-%m-%d %H:%M:%S")
                    
                    ctime = datetime.fromtimestamp(stat_info.st_ctime)
                    ctime_str = ctime.strftime("%Y-%m-%d %H:%M:%S")
                    
                    # Format permissions
                    perm_str = format_permissions(stat_info.st_mode)
                    
                    # Icon
                    icon = "📁" if is_dir else "📄"
                    
                    if hasattr(local_listbox, 'insert'):  # Treeview
                        local_listbox.insert("", "end", text=icon, 
                                            values=(item_name, size_str, mtime_str, ctime_str, perm_str),
                                            tags=("dir" if is_dir else "file",))
                    else:  # Listbox
                        local_listbox.insert(tk.END, f"{icon} {item_name}")
                except Exception as e:
                    # If we can't get metadata, just show the name
                    icon = "📁" if os.path.isdir(item_path) else "📄"
                    if hasattr(local_listbox, 'insert'):  # Treeview
                        local_listbox.insert("", "end", text=icon, 
                                            values=(item_name, "N/A", "N/A", "N/A", "N/A"))
                    else:  # Listbox
                        local_listbox.insert(tk.END, f"{icon} {item_name}")
            
            # Update status if status_info_var exists
            try:
                root.after(100, update_status_info)
            except:
                pass
        except PermissionError:
            messagebox.showerror("Error", f"Permission denied: {local_path}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to list local files: {e}")
    except Exception as e:
        print(f"Error in refresh_local_files: {e}")

# Wrapper functions - defined early so they can be used in UI setup
# Note: update_status_info will be defined later, but we'll handle that with try/except
def refresh_remote_files_wrapper():
    """Wrapper to refresh remote files and update status."""
    refresh_remote_files()
    try:
        root.after(100, update_status_info)
    except:
        pass  # update_status_info not defined yet

def refresh_local_files_wrapper():
    """Wrapper to refresh local files and update status."""
    refresh_local_files()
    try:
        root.after(100, update_status_info)
    except:
        pass  # update_status_info not defined yet

def get_selected_remote_item():
    """Get selected item from remote tree/listbox."""
    try:
        if hasattr(remote_listbox, 'selection'):
            # Treeview
            selection = remote_listbox.selection()
            if not selection:
                return None
            item_id = selection[0]
            values = remote_listbox.item(item_id, "values")
            # Get filename from values[0] (first column) - this is the actual filename without icon
            if values and len(values) > 0 and values[0]:
                name = str(values[0]).strip()
                if name:  # Make sure it's not empty
                    return name
            # Fallback: try to get from text (icon + name format)
            text = remote_listbox.item(item_id, "text")
            if text:
                # Text might be just the icon, so check values again
                if values and len(values) > 0:
                    return str(values[0]).strip() if values[0] else None
                # If no values, extract from text (handles "📁 name" format)
                text_str = str(text).strip()
                if text_str.startswith("📁") or text_str.startswith("📄"):
                    return text_str[2:].strip() if len(text_str) > 2 else None
                return text_str
            return None
        else:
            # Listbox (backward compatibility)
            try:
                selection = remote_listbox.curselection()
                if not selection:
                    return None
                return remote_listbox.get(selection[0])
            except:
                return None
    except Exception as e:
        print(f"Error in get_selected_remote_item: {e}")
        return None

def get_selected_local_item():
    """Get selected item from local tree/listbox."""
    try:
        if hasattr(local_listbox, 'selection'):
            # Treeview
            selection = local_listbox.selection()
            if not selection:
                return None
            item_id = selection[0]
            values = local_listbox.item(item_id, "values")
            # Get filename from values[0] (first column)
            if values and len(values) > 0 and values[0]:
                name = str(values[0]).strip()
                return name if name else None
            # Fallback to text if values are empty
            text = local_listbox.item(item_id, "text")
            return str(text).strip() if text else None
        else:
            # Listbox (backward compatibility)
            try:
                selection = local_listbox.curselection()
                if not selection:
                    return None
                return local_listbox.get(selection[0])
            except:
                return None
    except Exception as e:
        print(f"Error in get_selected_local_item: {e}")
        return None

def extract_filename(item):
    """Extract filename from item string. Handles both '📁 name' and 'name' formats."""
    if not item:
        return ""
    if isinstance(item, str):
        if item.startswith("📁"):
            return item[2:].strip()
        else:
            return item.strip()
    return str(item) if item else ""

def on_remote_double_click(event):
    """Handle double-click on remote file list."""
    item = get_selected_remote_item()
    if not item:
        return
    
    # Extract filename from item string
    if item.startswith("📁"):
        name = item[2:].strip()
    else:
        name = item.strip()
    
    if name == "..":
        current_path = current_client.get_current_dir()
        parent = os.path.dirname(current_path) if current_path != "/" else "/"
        current_client.change_dir(parent)
    else:
        current_client.change_dir(name)
    refresh_remote_files()
    try:
        root.after(100, update_status_info)
    except:
        pass

def on_local_double_click(event):
    """Handle double-click on local file list."""
    item = get_selected_local_item()
    if not item:
        return
    
    # Extract filename from item
    filename = extract_filename(item)
    
    current_path = local_path_var.get()
    if filename == "..":
        new_path = os.path.dirname(current_path) if current_path != os.path.dirname(current_path) else current_path
    else:
        new_path = os.path.join(current_path, filename)
    if os.path.exists(new_path):
        local_path_var.set(new_path)
        refresh_local_files()

def upload_file():
    """Upload selected file(s) to remote server."""
    if not current_client:
        messagebox.showerror("Error", "Not connected to server")
        return
    
    item = get_selected_local_item()
    if not item:
        messagebox.showwarning("No Selection", "Please select a file to upload")
        return
    
    # Extract filename from item
    filename = extract_filename(item)
    if filename.startswith("📁") or not filename:
        messagebox.showwarning("Error", "Please select a file, not a directory")
        return
    local_file = os.path.join(local_path_var.get(), filename)
    
    if not os.path.exists(local_file):
        messagebox.showerror("Error", "File not found")
        return
    
    current_dir = current_client.get_current_dir()
    remote_path = f"{current_dir.rstrip('/')}/{filename}" if current_dir != "/" else f"/{filename}"
    
    def _upload():
        import time
        start_time = time.time()
        file_size = os.path.getsize(local_file)
        
        try:
            success, message = current_client.upload_file(local_file, remote_path)
            duration = time.time() - start_time
            
            if success:
                db_manager.add_history(current_connection_name, "upload", local_file, remote_path, "success", None, file_size, duration)
                root.after(0, lambda: messagebox.showinfo("Success", f"Uploaded: {filename}"))
                root.after(0, lambda: refresh_remote_files_wrapper())
            else:
                db_manager.add_history(current_connection_name, "upload", local_file, remote_path, "failed", message, file_size, duration)
                root.after(0, lambda: messagebox.showerror("Upload Failed", message))
        except Exception as e:
            duration = time.time() - start_time
            db_manager.add_history(current_connection_name, "upload", local_file, remote_path, "failed", str(e), file_size, duration)
            root.after(0, lambda: messagebox.showerror("Error", f"Upload error: {e}"))
        finally:
            set_busy(False)
    
    set_busy(True, f"Uploading {filename}...")
    threading.Thread(target=_upload, daemon=True).start()

def download_file():
    """Download selected file from remote server."""
    if not current_client:
        messagebox.showerror("Error", "Not connected to server")
        return
    
    item = get_selected_remote_item()
    if not item:
        messagebox.showwarning("No Selection", "Please select a file to download")
        return
    
    # Extract filename from item
    filename = extract_filename(item)
    if filename.startswith("📁") or not filename:
        messagebox.showwarning("Error", "Please select a file, not a directory")
        return
    current_dir = current_client.get_current_dir()
    remote_path = f"{current_dir.rstrip('/')}/{filename}" if current_dir != "/" else f"/{filename}"
    local_file = os.path.join(local_path_var.get(), filename)
    
    def _download():
        import time
        start_time = time.time()
        
        try:
            success, message = current_client.download_file(remote_path, local_file)
            duration = time.time() - start_time
            file_size = os.path.getsize(local_file) if os.path.exists(local_file) else 0
            
            if success:
                db_manager.add_history(current_connection_name, "download", local_file, remote_path, "success", None, file_size, duration)
                root.after(0, lambda: messagebox.showinfo("Success", f"Downloaded: {filename}"))
                root.after(0, lambda: refresh_local_files_wrapper())
            else:
                db_manager.add_history(current_connection_name, "download", local_file, remote_path, "failed", message, 0, duration)
                root.after(0, lambda: messagebox.showerror("Download Failed", message))
        except Exception as e:
            duration = time.time() - start_time
            db_manager.add_history(current_connection_name, "download", local_file, remote_path, "failed", str(e), 0, duration)
            root.after(0, lambda: messagebox.showerror("Error", f"Download error: {e}"))
        finally:
            set_busy(False)
    
    set_busy(True, f"Downloading {filename}...")
    threading.Thread(target=_download, daemon=True).start()

def browse_local_folder():
    """Browse for local folder."""
    folder = filedialog.askdirectory(initialdir=local_path_var.get())
    if folder:
        local_path_var.set(folder)
        refresh_local_files()

def format_file_size(size_bytes):
    """Format bytes to human readable."""
    if size_bytes is None:
        return "N/A"
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.2f} PB"

def delete_remote_file():
    """Delete selected remote file."""
    if not current_client:
        messagebox.showerror("Error", "Not connected to server")
        return
    
    item = get_selected_remote_item()
    if not item:
        messagebox.showwarning("No Selection", "Please select a file or directory to delete")
        return
    
    # Extract filename from item
    filename = extract_filename(item)
    
    if filename == "..":
        messagebox.showwarning("Error", "Cannot delete parent directory")
        return
    current_dir = current_client.get_current_dir()
    remote_path = f"{current_dir.rstrip('/')}/{filename}" if current_dir != "/" else f"/{filename}"
    
    is_dir = item.startswith("📁")
    confirm_msg = f"Are you sure you want to delete {'directory' if is_dir else 'file'} '{filename}'?"
    
    if not messagebox.askyesno("Confirm Delete", confirm_msg):
        return
    
    def _delete():
        try:
            if is_dir:
                success, message = current_client.delete_dir(remote_path)
            else:
                success, message = current_client.delete_file(remote_path)
            
            if success:
                root.after(0, lambda: messagebox.showinfo("Success", f"Deleted: {filename}"))
                root.after(0, lambda: refresh_remote_files_wrapper())
            else:
                root.after(0, lambda: messagebox.showerror("Delete Failed", message))
        except Exception as e:
            root.after(0, lambda: messagebox.showerror("Error", f"Delete error: {e}"))
        finally:
            set_busy(False)
    
    set_busy(True, f"Deleting {filename}...")
    threading.Thread(target=_delete, daemon=True).start()

def rename_remote_file():
    """Rename selected remote file or directory."""
    if not current_client:
        messagebox.showerror("Error", "Not connected to server")
        return
    
    item = get_selected_remote_item()
    if not item:
        messagebox.showwarning("No Selection", "Please select a file or directory to rename")
        return
    
    # Extract filename from item
    old_name = extract_filename(item)
    
    if old_name == "..":
        messagebox.showwarning("Error", "Cannot rename parent directory")
        return
    new_name = simpledialog.askstring("Rename", f"Enter new name for '{old_name}':", initialvalue=old_name)
    
    if not new_name or new_name == old_name:
        return
    
    current_dir = current_client.get_current_dir()
    old_path = f"{current_dir.rstrip('/')}/{old_name}" if current_dir != "/" else f"/{old_name}"
    new_path = f"{current_dir.rstrip('/')}/{new_name}" if current_dir != "/" else f"/{new_name}"
    
    def _rename():
        try:
            success, message = current_client.rename_file(old_path, new_path)
            
            if success:
                root.after(0, lambda: messagebox.showinfo("Success", f"Renamed: {old_name} → {new_name}"))
                root.after(0, lambda: refresh_remote_files_wrapper())
            else:
                root.after(0, lambda: messagebox.showerror("Rename Failed", message))
        except Exception as e:
            root.after(0, lambda: messagebox.showerror("Error", f"Rename error: {e}"))
        finally:
            set_busy(False)
    
    set_busy(True, f"Renaming {old_name}...")
    threading.Thread(target=_rename, daemon=True).start()

def create_remote_directory():
    """Create a new remote directory."""
    if not current_client:
        messagebox.showerror("Error", "Not connected to server")
        return
    
    dir_name = simpledialog.askstring("Create Directory", "Enter directory name:")
    if not dir_name:
        return
    
    current_dir = current_client.get_current_dir()
    remote_path = f"{current_dir.rstrip('/')}/{dir_name}" if current_dir != "/" else f"/{dir_name}"
    
    def _create():
        try:
            success, message = current_client.create_dir(remote_path)
            
            if success:
                root.after(0, lambda: messagebox.showinfo("Success", f"Created directory: {dir_name}"))
                root.after(0, lambda: refresh_remote_files_wrapper())
            else:
                root.after(0, lambda: messagebox.showerror("Create Failed", message))
        except Exception as e:
            root.after(0, lambda: messagebox.showerror("Error", f"Create error: {e}"))
        finally:
            set_busy(False)
    
    set_busy(True, f"Creating directory {dir_name}...")
    threading.Thread(target=_create, daemon=True).start()

def view_edit_remote_file():
    """View or edit a remote text file."""
    if not current_client:
        messagebox.showerror("Error", "Not connected to server")
        return
    
    item = get_selected_remote_item()
    if not item:
        messagebox.showwarning("No Selection", "Please select a file to view/edit")
        return
    
    # Extract filename from item
    filename = extract_filename(item)
    if filename.startswith("📁") or not filename:
        messagebox.showwarning("Error", "Please select a file, not a directory")
        return
    current_dir = current_client.get_current_dir()
    remote_path = f"{current_dir.rstrip('/')}/{filename}" if current_dir != "/" else f"/{filename}"
    
    # Check if it's likely a text file
    text_extensions = {'.txt', '.py', '.js', '.html', '.css', '.json', '.xml', '.md', '.log', '.ini', '.conf', '.sh', '.bat', '.yml', '.yaml'}
    is_text_file = any(filename.lower().endswith(ext) for ext in text_extensions) or '.' not in filename
    
    if not is_text_file:
        if not messagebox.askyesno("Binary File", "This may be a binary file. Attempt to view as text anyway?"):
            return
    
    # Create temp file for editing
    import tempfile
    temp_file = os.path.join(tempfile.gettempdir(), f"ftp_edit_{filename}")
    
    def _download_and_edit():
        try:
            # Download file
            success, message = current_client.download_file(remote_path, temp_file)
            
            if not success:
                root.after(0, lambda: messagebox.showerror("Download Failed", message))
                set_busy(False)
                return
            
            # Open editor window
            root.after(0, lambda: open_file_editor(temp_file, remote_path, filename))
        except Exception as e:
            root.after(0, lambda: messagebox.showerror("Error", f"Error: {e}"))
            set_busy(False)
    
    set_busy(True, f"Downloading {filename} for editing...")
    threading.Thread(target=_download_and_edit, daemon=True).start()

def open_file_editor(temp_file, remote_path, filename):
    """Open file editor window."""
    set_busy(False)
    
    editor = tk.Toplevel(root)
    editor.title(f"Edit: {filename}")
    editor.geometry("800x600")
    editor.configure(bg=COLOR_BG)
    set_window_icon(editor)
    
    # Read file content
    try:
        with open(temp_file, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
    except:
        with open(temp_file, 'r', encoding='latin-1', errors='ignore') as f:
            content = f.read()
    
    # Text area with scrollbar
    text_frame = tk.Frame(editor, bg=COLOR_BG)
    text_frame.pack(fill="both", expand=True, padx=10, pady=10)
    
    text_area = tk.Text(text_frame, font=("Consolas", 11), wrap="none", bg="white", fg="black")
    text_area.pack(side="left", fill="both", expand=True)
    
    scrollbar = tk.Scrollbar(text_frame, command=text_area.yview)
    scrollbar.pack(side="right", fill="y")
    text_area.config(yscrollcommand=scrollbar.set)
    
    text_area.insert("1.0", content)
    
    # Button frame
    btn_frame = tk.Frame(editor, bg=COLOR_BG)
    btn_frame.pack(fill="x", padx=10, pady=10)
    
    def save_and_upload():
        """Save changes and upload back to server."""
        try:
            # Save to temp file
            content = text_area.get("1.0", tk.END)
            with open(temp_file, 'w', encoding='utf-8') as f:
                f.write(content)
            
            # Upload back
            def _upload():
                try:
                    success, message = current_client.upload_file(temp_file, remote_path)
                    if success:
                        root.after(0, lambda: messagebox.showinfo("Success", f"Saved: {filename}"))
                        root.after(0, lambda: editor.destroy())
                        root.after(0, lambda: refresh_remote_files_wrapper())
                    else:
                        root.after(0, lambda: messagebox.showerror("Upload Failed", message))
                except Exception as e:
                    root.after(0, lambda: messagebox.showerror("Error", f"Upload error: {e}"))
                finally:
                    set_busy(False)
                    try:
                        os.remove(temp_file)
                    except:
                        pass
            
            set_busy(True, f"Uploading {filename}...")
            threading.Thread(target=_upload, daemon=True).start()
        except Exception as e:
            messagebox.showerror("Error", f"Save error: {e}")
    
    tk.Button(btn_frame, text="💾 Save & Upload", command=save_and_upload, bg=COLOR_SECONDARY, fg="white", font=("TkDefaultFont", 10, "bold"), padx=15, pady=8).pack(side="left", padx=5)
    tk.Button(btn_frame, text="❌ Cancel", command=editor.destroy, bg=COLOR_DANGER, fg="white", font=("TkDefaultFont", 10, "bold"), padx=15, pady=8).pack(side="left", padx=5)
    
    # Cleanup on close
    def on_close():
        try:
            os.remove(temp_file)
        except:
            pass
        editor.destroy()
    
    editor.protocol("WM_DELETE_WINDOW", on_close)

def change_remote_permissions():
    """Change permissions of selected remote file/folder."""
    try:
        if not current_client:
            messagebox.showerror("Error", "Not connected to server")
            return
        
        item = get_selected_remote_item()
        if not item:
            messagebox.showwarning("No Selection", "Please select a file or directory")
            return
        
        # Extract filename from item (Treeview returns filename directly, Listbox might have icon prefix)
        filename = extract_filename(item) if item else ""
        
        if not filename:
            messagebox.showerror("Error", f"Could not extract filename from selection. Item: '{item}'. Please try selecting the file again.")
            return
        
        if filename == "..":
            messagebox.showwarning("Error", "Cannot change permissions for parent directory")
            return
        
        current_dir = current_client.get_current_dir()
        remote_path = f"{current_dir.rstrip('/')}/{filename}" if current_dir != "/" else f"/{filename}"
        
        # Get current permissions
        info = None
        try:
            info = current_client.get_file_info(remote_path)
        except Exception as e:
            print(f"Error getting file info: {e}")
            pass
        
        current_perm = info.get('permissions', '644') if info else '644'
        
        # Convert to octal string
        if isinstance(current_perm, int):
            perm_str = oct(current_perm)[-3:]
        elif isinstance(current_perm, str) and len(current_perm) >= 10:
            # Parse string like "-rw-r--r--" to octal
            try:
                perm_str_clean = current_perm[1:]  # Remove file type char
                octal = 0
                for i, char in enumerate(perm_str_clean[:9]):
                    if char != '-':
                        octal |= (1 << (8 - i))
                perm_str = oct(octal)[-3:]
            except:
                perm_str = "644"
        else:
            perm_str = "644"
        
        # Ask for new permissions
        new_perm_str = simpledialog.askstring("Change Permissions", 
                                             f"Enter new permissions (octal) for '{filename}':\nCurrent: {perm_str}",
                                             initialvalue=perm_str)
        if not new_perm_str:
            return
        
        try:
            perm_int = int(new_perm_str, 8)
            
            def _set_perm():
                try:
                    if not hasattr(current_client, 'set_permissions'):
                        root.after(0, lambda: messagebox.showerror("Error", "Permission editing not supported for this connection type"))
                        return
                    
                    success, message = current_client.set_permissions(remote_path, perm_int)
                    root.after(0, lambda: messagebox.showinfo("Success", message) if success else messagebox.showerror("Error", message))
                    if success:
                        root.after(0, lambda: refresh_remote_files_wrapper())
                except Exception as e:
                    import traceback
                    error_msg = traceback.format_exc()
                    print(f"Error setting permissions: {error_msg}")
                    root.after(0, lambda: messagebox.showerror("Error", f"Failed: {e}"))
            
            threading.Thread(target=_set_perm, daemon=True).start()
        except ValueError:
            messagebox.showerror("Error", "Invalid permissions format. Use octal (e.g., 755, 644)")
    except Exception as e:
        import traceback
        error_msg = traceback.format_exc()
        print(f"Error in change_remote_permissions: {error_msg}")
        messagebox.showerror("Error", f"An error occurred: {e}")

def change_local_permissions():
    """Change permissions of selected local file/folder."""
    try:
        item = get_selected_local_item()
        if not item:
            messagebox.showwarning("No Selection", "Please select a file or directory")
            return
        
        # Extract filename from item (Treeview returns filename directly, Listbox might have icon prefix)
        filename = extract_filename(item) if item else ""
        
        if not filename:
            messagebox.showerror("Error", f"Could not extract filename from selection. Item: '{item}'")
            return
        
        if filename == "..":
            messagebox.showwarning("Error", "Cannot change permissions for parent directory")
            return
        
        file_path = os.path.join(local_path_var.get(), filename)
        if not os.path.exists(file_path):
            messagebox.showerror("Error", "File not found")
            return
        
        # Get current permissions
        try:
            stat_info = os.stat(file_path)
            current_perm = oct(stat_info.st_mode)[-3:]
        except Exception as e:
            print(f"Error getting file stats: {e}")
            current_perm = "644"
        
        # Ask for new permissions
        new_perm_str = simpledialog.askstring("Change Permissions", 
                                             f"Enter new permissions (octal) for '{filename}':\nCurrent: {current_perm}",
                                             initialvalue=current_perm)
        if not new_perm_str:
            return
        
        try:
            perm_int = int(new_perm_str, 8)
            os.chmod(file_path, perm_int)
            messagebox.showinfo("Success", f"Permissions changed to {new_perm_str}")
            refresh_local_files()
        except ValueError:
            messagebox.showerror("Error", "Invalid permissions format. Use octal (e.g., 755, 644)")
        except Exception as e:
            import traceback
            error_msg = traceback.format_exc()
            print(f"Error changing permissions: {error_msg}")
            messagebox.showerror("Error", f"Failed to change permissions: {e}")
    except Exception as e:
        import traceback
        error_msg = traceback.format_exc()
        print(f"Error in change_local_permissions: {error_msg}")
        messagebox.showerror("Error", f"An error occurred: {e}")

def show_file_properties():
    """Show properties of selected remote file."""
    if not current_client:
        messagebox.showerror("Error", "Not connected to server")
        return
    
    item = get_selected_remote_item()
    if not item:
        messagebox.showwarning("No Selection", "Please select a file or directory")
        return
    
    # Extract filename from item (item is now always a string from get_selected_*_item)
    if not item:
        filename = ""
    elif item.startswith("📁"):
        filename = item[2:].strip()
    else:
        filename = item.strip()
    
    if filename == "..":
        return
    
    current_dir = current_client.get_current_dir()
    remote_path = f"{current_dir.rstrip('/')}/{filename}" if current_dir != "/" else f"/{filename}"
    
    # Check if it's a directory from treeview
    is_dir = False
    if hasattr(remote_listbox, 'selection'):
        selection = remote_listbox.selection()
        if selection:
            tags = remote_listbox.item(selection[0], "tags")
            is_dir = "dir" in tags if tags else False
    elif isinstance(item, str) and item.startswith("📁"):
        is_dir = True
    
    def _get_properties():
        try:
            if is_dir:
                info = {'size': 0, 'mtime': None, 'permissions': None, 'owner': None, 'group': None, 'ctime': None, 'atime': None}
            else:
                info = current_client.get_file_info(remote_path) or {}
            
            root.after(0, lambda: show_properties_dialog(filename, remote_path, is_dir, info))
        except Exception as e:
            root.after(0, lambda: messagebox.showerror("Error", f"Error getting properties: {e}"))
        finally:
            set_busy(False)
    
    set_busy(True, "Getting file properties...")
    threading.Thread(target=_get_properties, daemon=True).start()

def format_permissions(mode):
    """Format file permissions to readable string."""
    if mode is None:
        return "N/A"
    if isinstance(mode, str):
        return mode  # Already formatted like "-rw-r--r--"
    # Convert numeric mode to string
    try:
        mode_oct = oct(mode)[-3:]  # Get last 3 digits
        perms = ""
        for digit in mode_oct:
            val = int(digit)
            perms += "r" if val & 4 else "-"
            perms += "w" if val & 2 else "-"
            perms += "x" if val & 1 else "-"
        return perms
    except:
        return str(mode)

def show_properties_dialog(filename, path, is_dir, info):
    """Show enhanced file properties dialog with permissions editor."""
    set_busy(False)
    
    dialog = tk.Toplevel(root)
    dialog.title(f"Properties: {filename}")
    dialog.geometry("550x650")
    dialog.configure(bg=COLOR_BG)
    set_window_icon(dialog)
    
    # Create scrollable frame
    canvas = tk.Canvas(dialog, bg=COLOR_BG, highlightthickness=0)
    scrollbar = tk.Scrollbar(dialog, orient="vertical", command=canvas.yview)
    scrollable_frame = tk.Frame(canvas, bg=COLOR_BG)
    
    scrollable_frame.bind(
        "<Configure>",
        lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
    )
    
    canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
    canvas.configure(yscrollcommand=scrollbar.set)
    
    canvas.pack(side="left", fill="both", expand=True)
    scrollbar.pack(side="right", fill="y")
    
    props_frame = tk.Frame(scrollable_frame, bg=COLOR_CARD, relief="flat", borderwidth=1, highlightbackground=COLOR_BORDER, highlightthickness=1)
    props_frame.pack(fill="both", expand=True, padx=15, pady=15)
    
    tk.Label(props_frame, text="📋 File Properties", font=("TkDefaultFont", 14, "bold"), bg=COLOR_CARD, fg=COLOR_TEXT).pack(pady=15)
    
    # Properties display
    info_frame = tk.Frame(props_frame, bg=COLOR_CARD)
    info_frame.pack(fill="x", padx=20, pady=10)
    
    def add_property(label, value, row):
        tk.Label(info_frame, text=f"{label}:", font=("TkDefaultFont", 10, "bold"), bg=COLOR_CARD, fg=COLOR_TEXT, anchor="w").grid(row=row, column=0, sticky="w", pady=5)
        tk.Label(info_frame, text=str(value), font=("TkDefaultFont", 10), bg=COLOR_CARD, fg=COLOR_TEXT_LIGHT, anchor="w").grid(row=row, column=1, sticky="w", padx=(10, 0), pady=5)
    
    row = 0
    add_property("Name", filename, row); row += 1
    add_property("Type", "Directory" if is_dir else "File", row); row += 1
    add_property("Path", path, row); row += 1
    
    size = format_file_size(info.get('size', 0)) if not is_dir else "N/A (Directory)"
    add_property("Size", size, row); row += 1
    
    # Dates
    mtime_obj = info.get('mtime')
    mtime_str = mtime_obj.strftime("%Y-%m-%d %H:%M:%S") if mtime_obj else "N/A"
    add_property("Modified", mtime_str, row); row += 1
    
    ctime_obj = info.get('ctime')
    ctime_str = ctime_obj.strftime("%Y-%m-%d %H:%M:%S") if ctime_obj else "N/A"
    add_property("Created", ctime_str, row); row += 1
    
    atime_obj = info.get('atime')
    atime_str = atime_obj.strftime("%Y-%m-%d %H:%M:%S") if atime_obj else "N/A"
    add_property("Accessed", atime_str, row); row += 1
    
    # Permissions
    permissions = format_permissions(info.get('permissions'))
    add_property("Permissions", permissions, row); row += 1
    
    # Owner/Group
    owner = info.get('owner', 'N/A')
    add_property("Owner", owner, row); row += 1
    
    group = info.get('group', 'N/A')
    add_property("Group", group, row); row += 1
    
    # Permission editor section
    if hasattr(current_client, 'set_permissions'):
        perm_frame = tk.LabelFrame(props_frame, text="Edit Permissions", font=("TkDefaultFont", 11, "bold"), 
                                   bg=COLOR_CARD, fg=COLOR_TEXT, padx=15, pady=15)
        perm_frame.pack(fill="x", padx=20, pady=15)
        
        perm_input_frame = tk.Frame(perm_frame, bg=COLOR_CARD)
        perm_input_frame.pack(fill="x", pady=5)
        
        tk.Label(perm_input_frame, text="Octal (e.g., 755):", bg=COLOR_CARD, font=("TkDefaultFont", 10)).pack(side="left", padx=5)
        perm_var = tk.StringVar()
        
        # Extract current permissions if available
        current_perm = info.get('permissions')
        if current_perm:
            if isinstance(current_perm, int):
                perm_var.set(oct(current_perm)[-3:])
            elif isinstance(current_perm, str) and len(current_perm) >= 10:
                # Parse string like "-rw-r--r--" to octal
                try:
                    perm_str = current_perm[1:]  # Remove file type char
                    octal = 0
                    for i, char in enumerate(perm_str[:9]):
                        if char != '-':
                            octal |= (1 << (8 - i))
                    perm_var.set(oct(octal)[-3:])
                except:
                    perm_var.set("644")
            else:
                perm_var.set("644")
        else:
            perm_var.set("644")
        
        perm_entry = tk.Entry(perm_input_frame, textvariable=perm_var, width=10, font=("TkDefaultFont", 10))
        perm_entry.pack(side="left", padx=5)
        
        def apply_permissions():
            try:
                perm_str = perm_var.get().strip()
                if not perm_str:
                    messagebox.showerror("Error", "Please enter permissions")
                    return
                
                # Convert to integer
                perm_int = int(perm_str, 8)
                
                def _set_perm():
                    try:
                        success, message = current_client.set_permissions(path, perm_int)
                        root.after(0, lambda: messagebox.showinfo("Success", message) if success else messagebox.showerror("Error", message))
                        if success:
                            root.after(0, lambda: dialog.destroy())
                            root.after(0, lambda: show_file_properties())  # Refresh
                    except Exception as e:
                        root.after(0, lambda: messagebox.showerror("Error", f"Failed: {e}"))
                
                threading.Thread(target=_set_perm, daemon=True).start()
            except ValueError:
                messagebox.showerror("Error", "Invalid permissions format. Use octal (e.g., 755, 644)")
        
        tk.Button(perm_input_frame, text="Apply", command=apply_permissions, bg=COLOR_SECONDARY, fg="white", 
                 font=("TkDefaultFont", 9, "bold"), padx=15, pady=5).pack(side="left", padx=10)
        
        # Quick permission buttons
        quick_frame = tk.Frame(perm_frame, bg=COLOR_CARD)
        quick_frame.pack(fill="x", pady=5)
        
        tk.Label(quick_frame, text="Quick:", bg=COLOR_CARD, font=("TkDefaultFont", 9)).pack(side="left", padx=5)
        
        quick_perms = [("755", "rwxr-xr-x"), ("644", "rw-r--r--"), ("777", "rwxrwxrwx"), ("600", "rw-------")]
        for perm_val, perm_desc in quick_perms:
            btn = tk.Button(quick_frame, text=f"{perm_val} ({perm_desc})", 
                          command=lambda p=perm_val: perm_var.set(p),
                          bg=COLOR_BG, fg=COLOR_TEXT, font=("TkDefaultFont", 8),
                          padx=8, pady=3, relief="flat")
            btn.pack(side="left", padx=2)
    
    # Modification time editor (for SFTP)
    if hasattr(current_client, 'set_mtime') and mtime_obj:
        mtime_frame = tk.LabelFrame(props_frame, text="Edit Modification Time", font=("TkDefaultFont", 11, "bold"),
                                   bg=COLOR_CARD, fg=COLOR_TEXT, padx=15, pady=15)
        mtime_frame.pack(fill="x", padx=20, pady=15)
        
        mtime_input_frame = tk.Frame(mtime_frame, bg=COLOR_CARD)
        mtime_input_frame.pack(fill="x", pady=5)
        
        tk.Label(mtime_input_frame, text="Date & Time:", bg=COLOR_CARD, font=("TkDefaultFont", 10)).pack(side="left", padx=5)
        mtime_var = tk.StringVar(value=mtime_str)
        mtime_entry = tk.Entry(mtime_input_frame, textvariable=mtime_var, width=20, font=("TkDefaultFont", 10))
        mtime_entry.pack(side="left", padx=5)
        
        def apply_mtime():
            try:
                mtime_str_new = mtime_var.get().strip()
                mtime_new = datetime.strptime(mtime_str_new, "%Y-%m-%d %H:%M:%S")
                
                def _set_mtime():
                    try:
                        success, message = current_client.set_mtime(path, mtime_new)
                        root.after(0, lambda: messagebox.showinfo("Success", message) if success else messagebox.showerror("Error", message))
                        if success:
                            root.after(0, lambda: dialog.destroy())
                            root.after(0, lambda: show_file_properties())  # Refresh
                    except Exception as e:
                        root.after(0, lambda: messagebox.showerror("Error", f"Failed: {e}"))
                
                threading.Thread(target=_set_mtime, daemon=True).start()
            except ValueError:
                messagebox.showerror("Error", "Invalid date format. Use: YYYY-MM-DD HH:MM:SS")
        
        tk.Button(mtime_input_frame, text="Apply", command=apply_mtime, bg=COLOR_SECONDARY, fg="white",
                 font=("TkDefaultFont", 9, "bold"), padx=15, pady=5).pack(side="left", padx=10)
    
    # Buttons
    btn_frame = tk.Frame(props_frame, bg=COLOR_CARD)
    btn_frame.pack(pady=15)
    
    tk.Button(btn_frame, text="Refresh", command=lambda: (dialog.destroy(), show_file_properties()), 
             bg=COLOR_PRIMARY, fg="white", font=("TkDefaultFont", 10, "bold"), padx=15, pady=8).pack(side="left", padx=5)
    tk.Button(btn_frame, text="Close", command=dialog.destroy, bg=COLOR_TEXT_LIGHT, fg="white", 
             font=("TkDefaultFont", 10, "bold"), padx=15, pady=8).pack(side="left", padx=5)

def delete_local_file():
    """Delete selected local file or directory."""
    item = get_selected_local_item()
    if not item:
        messagebox.showwarning("No Selection", "Please select a file or directory to delete")
        return
    
    # Extract filename from item
    filename = extract_filename(item)
    
    if filename == "..":
        messagebox.showwarning("Error", "Cannot delete parent directory")
        return
    file_path = os.path.join(local_path_var.get(), filename)
    
    if not os.path.exists(file_path):
        messagebox.showerror("Error", "File not found")
        return
    
    is_dir = item.startswith("📁")
    confirm_msg = f"Are you sure you want to delete {'directory' if is_dir else 'file'} '{filename}'?"
    
    if not messagebox.askyesno("Confirm Delete", confirm_msg):
        return
    
    try:
        if is_dir:
            import shutil
            shutil.rmtree(file_path)
        else:
            os.remove(file_path)
        messagebox.showinfo("Success", f"Deleted: {filename}")
        refresh_local_files()
    except Exception as e:
        messagebox.showerror("Error", f"Delete error: {e}")

def rename_local_file():
    """Rename selected local file or directory."""
    item = get_selected_local_item()
    if not item:
        messagebox.showwarning("No Selection", "Please select a file or directory to rename")
        return
    
    # Extract filename from item
    old_name = extract_filename(item)
    
    if old_name == "..":
        messagebox.showwarning("Error", "Cannot rename parent directory")
        return
    old_path = os.path.join(local_path_var.get(), old_name)
    
    if not os.path.exists(old_path):
        messagebox.showerror("Error", "File not found")
        return
    
    new_name = simpledialog.askstring("Rename", f"Enter new name for '{old_name}':", initialvalue=old_name)
    
    if not new_name or new_name == old_name:
        return
    
    new_path = os.path.join(local_path_var.get(), new_name)
    
    if os.path.exists(new_path):
        messagebox.showerror("Error", f"'{new_name}' already exists")
        return
    
    try:
        os.rename(old_path, new_path)
        messagebox.showinfo("Success", f"Renamed: {old_name} → {new_name}")
        refresh_local_files()
    except Exception as e:
        messagebox.showerror("Error", f"Rename error: {e}")

def create_local_directory():
    """Create a new local directory."""
    dir_name = simpledialog.askstring("Create Directory", "Enter directory name:")
    if not dir_name:
        return
    
    dir_path = os.path.join(local_path_var.get(), dir_name)
    
    if os.path.exists(dir_path):
        messagebox.showerror("Error", f"Directory '{dir_name}' already exists")
        return
    
    try:
        os.makedirs(dir_path)
        messagebox.showinfo("Success", f"Created directory: {dir_name}")
        refresh_local_files()
    except Exception as e:
        messagebox.showerror("Error", f"Create error: {e}")

def save_connection():
    """Save current connection as a profile."""
    protocol = protocol_var.get()
    host = host_var.get().strip()
    port = port_var.get().strip()
    username = username_var.get().strip()
    password = password_var.get().strip()
    use_tls = use_tls_var.get()
    
    if not host or not username:
        messagebox.showerror("Error", "Please fill Host and Username")
        return
    
    name = simpledialog.askstring("Save Connection", "Enter a name for this connection:", initialvalue=f"{username}@{host}")
    if not name:
        return
    
    if db_manager.save_connection(name, protocol, host, port, username, password, use_tls):
        messagebox.showinfo("Success", f"Connection '{name}' saved successfully!")
    else:
        messagebox.showerror("Error", f"Connection '{name}' already exists!")

def load_connection():
    """Load a saved connection."""
    connections = db_manager.get_connections()
    
    if not connections:
        messagebox.showinfo("No Saved Connections", "No saved connections found. Save a connection first.")
        return
    
    dialog = tk.Toplevel(root)
    dialog.title("Load/Delete Saved Connection")
    dialog.geometry("650x450")
    dialog.configure(bg=COLOR_BG)
    dialog.transient(root)
    dialog.grab_set()
    
    tk.Label(dialog, text="📋 Saved Connections", font=("TkDefaultFont", 14, "bold"), bg=COLOR_BG, fg=COLOR_TEXT, pady=10).pack()
    
    # Use Treeview for better display
    list_frame = tk.Frame(dialog, bg=COLOR_BG)
    list_frame.pack(fill="both", expand=True, padx=15, pady=10)
    
    tree = ttk.Treeview(list_frame, columns=("name", "protocol", "host", "port"), show="tree headings", height=15)
    tree.heading("#0", text="")
    tree.heading("name", text="Name")
    tree.heading("protocol", text="Protocol")
    tree.heading("host", text="Host")
    tree.heading("port", text="Port")
    
    tree.column("#0", width=30, stretch=False)
    tree.column("name", width=150, anchor="w")
    tree.column("protocol", width=80, anchor="w")
    tree.column("host", width=200, anchor="w")
    tree.column("port", width=80, anchor="w")
    
    tree.pack(side="left", fill="both", expand=True)
    
    scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=tree.yview)
    scrollbar.pack(side="right", fill="y")
    tree.config(yscrollcommand=scrollbar.set)
    
    # Store connection names with tree items
    conn_map = {}
    for conn in connections:
        item_id = tree.insert("", "end", text="🔌", 
                             values=(conn['name'], conn['protocol'].upper(), conn['host'], conn['port']))
        conn_map[item_id] = conn['name']
    
    def load_selected():
        selection = tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a connection to load")
            return
        
        conn_name = conn_map.get(selection[0])
        if not conn_name:
            messagebox.showerror("Error", "Could not find connection details")
            return
        
        conn = db_manager.load_connection(conn_name)
        if conn:
            protocol_var.set(conn['protocol'])
            host_var.set(conn['host'])
            port_var.set(conn['port'])
            username_var.set(conn['username'])
            password_var.set(conn['password'])
            use_tls_var.set(conn['use_tls'])
            dialog.destroy()
            messagebox.showinfo("Success", f"Connection '{conn_name}' loaded successfully!")
        else:
            messagebox.showerror("Error", f"Failed to load connection '{conn_name}'")
    
    def delete_selected():
        selection = tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a connection to delete")
            return
        
        conn_name = conn_map.get(selection[0])
        if not conn_name:
            messagebox.showerror("Error", "Could not find connection details")
            return
        
        if messagebox.askyesno("Confirm Delete", f"Are you sure you want to delete connection '{conn_name}'?"):
            if db_manager.delete_connection(conn_name):
                tree.delete(selection[0])
                del conn_map[selection[0]]
                messagebox.showinfo("Success", f"Connection '{conn_name}' deleted successfully!")
                
                # If no more connections, close dialog
                if not tree.get_children():
                    dialog.destroy()
            else:
                messagebox.showerror("Error", f"Failed to delete connection '{conn_name}'")
    
    # Button frame
    btn_frame = tk.Frame(dialog, bg=COLOR_BG)
    btn_frame.pack(fill="x", padx=15, pady=10)
    
    tk.Button(btn_frame, text="📥 Load", command=load_selected, bg=COLOR_PRIMARY, fg="white", 
              font=("TkDefaultFont", 10, "bold"), padx=20, pady=8).pack(side="left", padx=5)
    
    tk.Button(btn_frame, text="🗑️ Delete", command=delete_selected, bg=COLOR_DANGER, fg="white", 
              font=("TkDefaultFont", 10, "bold"), padx=20, pady=8).pack(side="left", padx=5)
    
    tk.Button(btn_frame, text="❌ Cancel", command=dialog.destroy, bg=COLOR_TEXT_LIGHT, fg="white", 
              font=("TkDefaultFont", 10, "bold"), padx=20, pady=8).pack(side="right", padx=5)

def show_history():
    """Show operation history."""
    history = db_manager.get_history(limit=100)
    
    dialog = tk.Toplevel(root)
    dialog.title("Operation History")
    dialog.geometry("900x600")
    dialog.configure(bg=COLOR_BG)
    
    tk.Label(dialog, text="📊 Operation History", font=("TkDefaultFont", 14, "bold"), bg=COLOR_BG, fg=COLOR_TEXT, pady=10).pack()
    
    tree = ttk.Treeview(dialog, columns=("Date", "Operation", "Local", "Remote", "Status", "Size"), show="headings", height=20)
    tree.heading("Date", text="Date")
    tree.heading("Operation", text="Operation")
    tree.heading("Local", text="Local Path")
    tree.heading("Remote", text="Remote Path")
    tree.heading("Status", text="Status")
    tree.heading("Size", text="Size")
    
    tree.column("Date", width=150)
    tree.column("Operation", width=100)
    tree.column("Local", width=200)
    tree.column("Remote", width=200)
    tree.column("Status", width=100)
    tree.column("Size", width=100)
    
    for record in history:
        status_display = "✅ Success" if record['status'] == "success" else "❌ Failed"
        size_display = f"{record['file_size'] / 1024:.1f} KB" if record['file_size'] else "N/A"
        tree.insert("", "end", values=(
            record['started_at'],
            record['operation'],
            record['local_path'],
            record['remote_path'],
            status_display,
            size_display
        ))
    
    tree.pack(fill="both", expand=True, padx=15, pady=10)
    tk.Button(dialog, text="Close", command=dialog.destroy, bg=COLOR_TEXT_LIGHT, fg="white", font=("TkDefaultFont", 10, "bold"), padx=20, pady=8).pack(pady=10)

def show_transfer_queue():
    """Show transfer queue window with pause/resume/cancel."""
    queue_window = tk.Toplevel(root)
    set_window_icon(queue_window)
    queue_window.title("Transfer Queue")
    queue_window.geometry("800x500")
    queue_window.configure(bg=COLOR_BG)
    
    # Header
    header = tk.Frame(queue_window, bg=COLOR_PRIMARY, height=50)
    header.pack(fill="x")
    header.pack_propagate(False)
    tk.Label(header, text="📋 Transfer Queue", font=("TkDefaultFont", 14, "bold"), bg=COLOR_PRIMARY, fg="white", pady=15).pack()
    
    # Queue controls
    controls = tk.Frame(queue_window, bg=COLOR_BG, pady=10)
    controls.pack(fill="x", padx=10)
    
    tk.Button(controls, text="Clear Completed", command=lambda: (transfer_queue.clear_completed(), update_queue_display()), 
              bg=COLOR_TEXT_LIGHT, fg="white", font=("TkDefaultFont", 9), padx=10, pady=5).pack(side="left", padx=5)
    
    speed_frame = tk.Frame(controls, bg=COLOR_BG)
    speed_frame.pack(side="right", padx=5)
    tk.Label(speed_frame, text="Speed Limit (KB/s):", bg=COLOR_BG, font=("TkDefaultFont", 9)).pack(side="left", padx=5)
    speed_var = tk.StringVar(value="0")
    speed_entry = tk.Entry(speed_frame, textvariable=speed_var, width=10, font=("TkDefaultFont", 9))
    speed_entry.pack(side="left", padx=5)
    
    def set_speed_limit():
        try:
            limit = int(speed_var.get()) * 1024  # Convert KB/s to bytes/s
            transfer_queue.set_speed_limit(limit if limit > 0 else 0)
            db_manager.add_log("INFO", f"Speed limit set to {speed_var.get()} KB/s", current_connection_name)
        except ValueError:
            messagebox.showerror("Error", "Invalid speed limit")
    
    tk.Button(speed_frame, text="Set", command=set_speed_limit, bg=COLOR_SECONDARY, fg="white", 
              font=("TkDefaultFont", 9), padx=8, pady=3).pack(side="left", padx=5)
    
    # Queue list
    queue_frame = tk.Frame(queue_window, bg=COLOR_BG)
    queue_frame.pack(fill="both", expand=True, padx=10, pady=10)
    
    tree = ttk.Treeview(queue_frame, columns=("Operation", "File", "Status", "Progress", "Speed", "ETA"), show="headings", height=15)
    tree.heading("Operation", text="Operation")
    tree.heading("File", text="File")
    tree.heading("Status", text="Status")
    tree.heading("Progress", text="Progress")
    tree.heading("Speed", text="Speed")
    tree.heading("ETA", text="ETA")
    
    tree.column("Operation", width=80)
    tree.column("File", width=300)
    tree.column("Status", width=80)
    tree.column("Progress", width=100)
    tree.column("Speed", width=100)
    tree.column("ETA", width=100)
    
    scrollbar = ttk.Scrollbar(queue_frame, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=scrollbar.set)
    
    tree.pack(side="left", fill="both", expand=True)
    scrollbar.pack(side="right", fill="y")
    
    # Context menu
    queue_menu = tk.Menu(queue_window, tearoff=0)
    
    def pause_selected():
        selection = tree.selection()
        if selection:
            transfer_id = int(tree.item(selection[0], "tags")[0])
            transfer_queue.pause(transfer_id)
            update_queue_display()
    
    def resume_selected():
        selection = tree.selection()
        if selection:
            transfer_id = int(tree.item(selection[0], "tags")[0])
            transfer_queue.resume(transfer_id)
            update_queue_display()
    
    def cancel_selected():
        selection = tree.selection()
        if selection:
            transfer_id = int(tree.item(selection[0], "tags")[0])
            transfer_queue.cancel(transfer_id)
            update_queue_display()
    
    queue_menu.add_command(label="⏸️ Pause", command=pause_selected)
    queue_menu.add_command(label="▶️ Resume", command=resume_selected)
    queue_menu.add_separator()
    queue_menu.add_command(label="❌ Cancel", command=cancel_selected)
    
    def show_queue_menu(event):
        try:
            queue_menu.tk_popup(event.x_root, event.y_root)
        finally:
            queue_menu.grab_release()
    
    tree.bind("<Button-3>", show_queue_menu)
    
    def update_queue_display():
        """Update the queue display."""
        for item in tree.get_children():
            tree.delete(item)
        
        transfers = transfer_queue.get_all()
        for transfer in transfers:
            file_name = os.path.basename(transfer.local_path) if transfer.operation == 'upload' else os.path.basename(transfer.remote_path)
            status_icon = {
                'pending': '⏳',
                'running': '▶️',
                'paused': '⏸️',
                'completed': '✅',
                'failed': '❌',
                'cancelled': '🚫'
            }.get(transfer.status, '❓')
            
            speed_str = f"{transfer.speed / 1024:.1f} KB/s" if transfer.speed > 0 else "-"
            eta_str = f"{int(transfer.eta)}s" if transfer.eta > 0 else "-"
            progress_str = f"{transfer.progress:.1f}%" if transfer.progress > 0 else "0%"
            
            tree.insert("", "end", tags=(transfer.id,), values=(
                transfer.operation.upper(),
                file_name,
                f"{status_icon} {transfer.status}",
                progress_str,
                speed_str,
                eta_str
            ))
        
        # Schedule next update
        queue_window.after(1000, update_queue_display)
    
    update_queue_display()
    
    tk.Button(queue_window, text="Close", command=queue_window.destroy, 
              bg=COLOR_TEXT_LIGHT, fg="white", font=("TkDefaultFont", 10, "bold"), padx=20, pady=8).pack(pady=10)

def show_advanced_logs():
    """Show advanced log viewer with filters."""
    log_window = tk.Toplevel(root)
    set_window_icon(log_window)
    log_window.title("Advanced Log Viewer")
    log_window.geometry("900x600")
    log_window.configure(bg=COLOR_BG)
    
    # Header with filters
    header = tk.Frame(log_window, bg=COLOR_PRIMARY, height=80)
    header.pack(fill="x")
    header.pack_propagate(False)
    
    tk.Label(header, text="📝 Advanced Log Viewer", font=("TkDefaultFont", 14, "bold"), bg=COLOR_PRIMARY, fg="white", pady=10).pack()
    
    filter_frame = tk.Frame(header, bg=COLOR_PRIMARY)
    filter_frame.pack(pady=5)
    
    tk.Label(filter_frame, text="Level:", bg=COLOR_PRIMARY, fg="white", font=("TkDefaultFont", 9)).pack(side="left", padx=5)
    level_var = tk.StringVar(value="ALL")
    level_menu = ttk.Combobox(filter_frame, textvariable=level_var, values=["ALL", "INFO", "WARNING", "ERROR"], 
                              state="readonly", width=10, font=("TkDefaultFont", 9))
    level_menu.pack(side="left", padx=5)
    
    def refresh_logs():
        level = level_var.get() if level_var.get() != "ALL" else None
        logs = db_manager.get_logs(level=level, connection_name=current_connection_name, limit=500)
        
        for item in log_tree.get_children():
            log_tree.delete(item)
        
        for log in logs:
            level_icon = {
                'INFO': 'ℹ️',
                'WARNING': '⚠️',
                'ERROR': '❌'
            }.get(log['level'], '📝')
            
            log_tree.insert("", "end", values=(
                log['timestamp'],
                f"{level_icon} {log['level']}",
                log['message']
            ))
    
    tk.Button(filter_frame, text="Refresh", command=refresh_logs, bg=COLOR_SECONDARY, fg="white", 
              font=("TkDefaultFont", 9), padx=10, pady=3).pack(side="left", padx=10)
    
    # Log display
    log_frame = tk.Frame(log_window, bg=COLOR_BG)
    log_frame.pack(fill="both", expand=True, padx=10, pady=10)
    
    log_tree = ttk.Treeview(log_frame, columns=("Timestamp", "Level", "Message"), show="headings", height=20)
    log_tree.heading("Timestamp", text="Timestamp")
    log_tree.heading("Level", text="Level")
    log_tree.heading("Message", text="Message")
    
    log_tree.column("Timestamp", width=180)
    log_tree.column("Level", width=100)
    log_tree.column("Message", width=600)
    
    scrollbar = ttk.Scrollbar(log_frame, orient="vertical", command=log_tree.yview)
    log_tree.configure(yscrollcommand=scrollbar.set)
    
    log_tree.pack(side="left", fill="both", expand=True)
    scrollbar.pack(side="right", fill="y")
    
    refresh_logs()
    
    tk.Button(log_window, text="Close", command=log_window.destroy, 
              bg=COLOR_TEXT_LIGHT, fg="white", font=("TkDefaultFont", 10, "bold"), padx=20, pady=8).pack(pady=10)

def show_bookmarks():
    """Show directory bookmarks manager."""
    bookmark_window = tk.Toplevel(root)
    set_window_icon(bookmark_window)
    bookmark_window.title("Directory Bookmarks")
    bookmark_window.geometry("700x500")
    bookmark_window.configure(bg=COLOR_BG)
    
    tk.Label(bookmark_window, text="🔖 Directory Bookmarks", font=("TkDefaultFont", 14, "bold"), 
             bg=COLOR_BG, fg=COLOR_TEXT, pady=10).pack()
    
    # Bookmarks list
    bookmark_frame = tk.Frame(bookmark_window, bg=COLOR_BG)
    bookmark_frame.pack(fill="both", expand=True, padx=10, pady=10)
    
    bookmark_tree = ttk.Treeview(bookmark_frame, columns=("Name", "Path"), show="headings", height=15)
    bookmark_tree.heading("Name", text="Name")
    bookmark_tree.heading("Path", text="Path")
    
    bookmark_tree.column("Name", width=200)
    bookmark_tree.column("Path", width=450)
    
    scrollbar = ttk.Scrollbar(bookmark_frame, orient="vertical", command=bookmark_tree.yview)
    bookmark_tree.configure(yscrollcommand=scrollbar.set)
    
    bookmark_tree.pack(side="left", fill="both", expand=True)
    scrollbar.pack(side="right", fill="y")
    
    def refresh_bookmarks():
        for item in bookmark_tree.get_children():
            bookmark_tree.delete(item)
        
        bookmarks = db_manager.get_bookmarks(connection_name=current_connection_name)
        for bm in bookmarks:
            bookmark_tree.insert("", "end", tags=(bm['id'],), values=(bm['name'], bm['path']))
    
    def add_bookmark():
        if not current_client:
            messagebox.showwarning("Not Connected", "Please connect to a server first")
            return
        
        current_path = current_client.get_current_dir()
        name = simpledialog.askstring("Add Bookmark", f"Enter bookmark name for:\n{current_path}", 
                                     initialvalue=os.path.basename(current_path) or "Bookmark")
        if name:
            if db_manager.add_bookmark(current_connection_name, current_path, name):
                messagebox.showinfo("Success", "Bookmark added")
                refresh_bookmarks()
            else:
                messagebox.showerror("Error", "Failed to add bookmark")
    
    def delete_bookmark():
        selection = bookmark_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a bookmark to delete")
            return
        
        bookmark_id = int(bookmark_tree.item(selection[0], "tags")[0])
        if messagebox.askyesno("Confirm", "Delete this bookmark?"):
            db_manager.delete_bookmark(bookmark_id)
            refresh_bookmarks()
    
    def goto_bookmark():
        selection = bookmark_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a bookmark")
            return
        
        path = bookmark_tree.item(selection[0], "values")[1]
        if current_client:
            try:
                current_client.change_dir(path)
                refresh_remote_files_wrapper()
                bookmark_window.destroy()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to navigate: {e}")
    
    bookmark_tree.bind("<Double-Button-1>", lambda e: goto_bookmark())
    
    # Buttons
    btn_frame = tk.Frame(bookmark_window, bg=COLOR_BG)
    btn_frame.pack(pady=10)
    
    tk.Button(btn_frame, text="➕ Add Current", command=add_bookmark, bg=COLOR_SECONDARY, fg="white", 
              font=("TkDefaultFont", 9), padx=15, pady=5).pack(side="left", padx=5)
    tk.Button(btn_frame, text="➡️ Go To", command=goto_bookmark, bg=COLOR_PRIMARY, fg="white", 
              font=("TkDefaultFont", 9), padx=15, pady=5).pack(side="left", padx=5)
    tk.Button(btn_frame, text="🗑️ Delete", command=delete_bookmark, bg=COLOR_DANGER, fg="white", 
              font=("TkDefaultFont", 9), padx=15, pady=5).pack(side="left", padx=5)
    tk.Button(btn_frame, text="Close", command=bookmark_window.destroy, bg=COLOR_TEXT_LIGHT, fg="white", 
              font=("TkDefaultFont", 9), padx=15, pady=5).pack(side="left", padx=5)
    
    refresh_bookmarks()

# --- Tkinter UI setup ---
root = tk.Tk()
set_window_icon(root)
root.title("FTP/FTPS/SFTP Client")
root.geometry("1000x700")
root.configure(bg=COLOR_BG)
root.minsize(800, 600)

# Variables
protocol_var = tk.StringVar(value="ftp")
host_var = tk.StringVar(value="")
port_var = tk.StringVar(value="21")
username_var = tk.StringVar(value="")
password_var = tk.StringVar(value="")
use_tls_var = tk.BooleanVar(value=False)
local_path_var = tk.StringVar(value=os.getcwd())
remote_path_var = tk.StringVar(value="/")
status_var = tk.StringVar(value="")

# Header
header_frame = tk.Frame(root, bg=COLOR_PRIMARY, height=60)
header_frame.pack(fill="x")
header_frame.pack_propagate(False)

tk.Label(header_frame, text="🔌 FTP/FTPS/SFTP Client", font=("TkDefaultFont", 16, "bold"), bg=COLOR_PRIMARY, fg="white", pady=15).pack()

# Main container for connection and file manager
main_container = tk.Frame(root, bg=COLOR_BG)
main_container.pack(fill="both", expand=True, padx=10, pady=10)

# Connection frame - compact at top
connect_frame = tk.Frame(main_container, bg=COLOR_CARD, relief="flat", borderwidth=1, highlightbackground=COLOR_BORDER, highlightthickness=1)
connect_frame.pack(fill="x", pady=(0, 10))

# Compact connection header with expand/collapse
conn_header = tk.Frame(connect_frame, bg=COLOR_CARD)
conn_header.pack(fill="x", padx=10, pady=8)

# Connection status and expand/collapse button
conn_status_frame = tk.Frame(conn_header, bg=COLOR_CARD)
conn_status_frame.pack(side="left", fill="x", expand=True)

connection_label = tk.Label(conn_status_frame, text="Not connected", fg=COLOR_TEXT_LIGHT, bg=COLOR_CARD, font=("TkDefaultFont", 9))
connection_label.pack(side="left", padx=(0, 10))

# Expand/collapse button for connection settings
expand_collapse_btn = tk.Button(conn_status_frame, text="⚙️ Settings", command=lambda: toggle_connection_settings(), 
                                bg=COLOR_TEXT_LIGHT, fg="white", font=("TkDefaultFont", 8), padx=8, pady=3, cursor="hand2")
expand_collapse_btn.pack(side="left")

# Menu buttons on the right
menu_buttons_frame = tk.Frame(conn_header, bg=COLOR_CARD)
menu_buttons_frame.pack(side="right")

connect_btn = tk.Button(menu_buttons_frame, text="🔌 Connect", command=lambda: (set_busy(True, "Connecting..."), connect_worker()), 
                       bg=COLOR_PRIMARY, fg="white", font=("TkDefaultFont", 9, "bold"), padx=12, pady=5, cursor="hand2")
connect_btn.pack(side="left", padx=2)

tk.Button(menu_buttons_frame, text="💾 Save", command=save_connection, bg=COLOR_SECONDARY, fg="white", 
          font=("TkDefaultFont", 9), padx=10, pady=5, cursor="hand2").pack(side="left", padx=2)
tk.Button(menu_buttons_frame, text="📂 Load", command=load_connection, bg=COLOR_PRIMARY, fg="white", 
          font=("TkDefaultFont", 9), padx=10, pady=5, cursor="hand2").pack(side="left", padx=2)

# Separator
tk.Frame(menu_buttons_frame, bg=COLOR_BORDER, width=1).pack(side="left", fill="y", padx=5, pady=2)

tk.Button(menu_buttons_frame, text="📊 History", command=show_history, bg=COLOR_TEXT_LIGHT, fg="white", 
          font=("TkDefaultFont", 9), padx=10, pady=5, cursor="hand2").pack(side="left", padx=2)
tk.Button(menu_buttons_frame, text="📋 Queue", command=show_transfer_queue, bg=COLOR_PRIMARY, fg="white", 
          font=("TkDefaultFont", 9), padx=10, pady=5, cursor="hand2").pack(side="left", padx=2)
tk.Button(menu_buttons_frame, text="📝 Logs", command=show_advanced_logs, bg=COLOR_SECONDARY, fg="white", 
          font=("TkDefaultFont", 9), padx=10, pady=5, cursor="hand2").pack(side="left", padx=2)
tk.Button(menu_buttons_frame, text="🔖 Bookmarks", command=show_bookmarks, bg=COLOR_WARNING, fg="white", 
          font=("TkDefaultFont", 9), padx=10, pady=5, cursor="hand2").pack(side="left", padx=2)

# Connection settings form (can be collapsed)
form_frame = tk.Frame(connect_frame, bg=COLOR_CARD)
form_frame.pack(fill="x", padx=10, pady=5)

tk.Label(form_frame, text="Protocol:", font=("TkDefaultFont", 10, "bold"), bg=COLOR_CARD, fg=COLOR_TEXT, anchor="w").grid(row=0, column=0, sticky="w", padx=5, pady=8)
protocol_frame = tk.Frame(form_frame, bg=COLOR_CARD)
protocol_frame.grid(row=0, column=1, sticky="w", padx=5, pady=8)
tk.Radiobutton(protocol_frame, text="FTP", value="ftp", variable=protocol_var, bg=COLOR_CARD, command=lambda: use_tls_frame.grid() if protocol_var.get() == "ftp" else use_tls_frame.grid_remove()).pack(side="left", padx=5)
tk.Radiobutton(protocol_frame, text="FTPS", value="ftps", variable=protocol_var, bg=COLOR_CARD, command=lambda: use_tls_frame.grid()).pack(side="left", padx=5)
tk.Radiobutton(protocol_frame, text="SFTP", value="sftp", variable=protocol_var, bg=COLOR_CARD, command=lambda: use_tls_frame.grid_remove()).pack(side="left", padx=5)

tk.Label(form_frame, text="Host:", font=("TkDefaultFont", 10, "bold"), bg=COLOR_CARD, fg=COLOR_TEXT, anchor="w").grid(row=1, column=0, sticky="w", padx=5, pady=8)
tk.Entry(form_frame, textvariable=host_var, font=("TkDefaultFont", 10), width=30).grid(row=1, column=1, sticky="w", padx=5, pady=8)

tk.Label(form_frame, text="Port:", font=("TkDefaultFont", 10, "bold"), bg=COLOR_CARD, fg=COLOR_TEXT, anchor="w").grid(row=2, column=0, sticky="w", padx=5, pady=8)
tk.Entry(form_frame, textvariable=port_var, font=("TkDefaultFont", 10), width=15).grid(row=2, column=1, sticky="w", padx=5, pady=8)

tk.Label(form_frame, text="Username:", font=("TkDefaultFont", 10, "bold"), bg=COLOR_CARD, fg=COLOR_TEXT, anchor="w").grid(row=3, column=0, sticky="w", padx=5, pady=8)
tk.Entry(form_frame, textvariable=username_var, font=("TkDefaultFont", 10), width=30).grid(row=3, column=1, sticky="w", padx=5, pady=8)

tk.Label(form_frame, text="Password:", font=("TkDefaultFont", 10, "bold"), bg=COLOR_CARD, fg=COLOR_TEXT, anchor="w").grid(row=4, column=0, sticky="w", padx=5, pady=8)
tk.Entry(form_frame, textvariable=password_var, show="*", font=("TkDefaultFont", 10), width=30).grid(row=4, column=1, sticky="w", padx=5, pady=8)

use_tls_frame = tk.Frame(form_frame, bg=COLOR_CARD)
use_tls_frame.grid(row=5, column=1, sticky="w", padx=5, pady=8)
tk.Checkbutton(use_tls_frame, text="Use TLS/SSL", variable=use_tls_var, bg=COLOR_CARD).pack(side="left")

# Connection settings are now in form_frame, buttons are in menu_buttons_frame in header

# File manager frame - always visible, but remote side hidden until connected
file_manager_frame = tk.Frame(main_container, bg=COLOR_BG)
file_manager_frame.pack(fill="both", expand=True)

# Remote files - initially hidden
remote_frame = tk.Frame(file_manager_frame, bg=COLOR_CARD, relief="flat", borderwidth=1, highlightbackground=COLOR_BORDER, highlightthickness=1)
# Will be packed when connected

tk.Label(remote_frame, text="📁 Remote Files", font=("TkDefaultFont", 12, "bold"), bg=COLOR_CARD, fg=COLOR_TEXT).pack(pady=10)
tk.Label(remote_frame, textvariable=remote_path_var, font=("TkDefaultFont", 9), bg=COLOR_CARD, fg=COLOR_TEXT_LIGHT).pack()

# Remote file list with Treeview (supports columns for metadata)
remote_list_frame = tk.Frame(remote_frame, bg=COLOR_CARD)
remote_list_frame.pack(fill="both", expand=True, padx=10, pady=10)

# Use Treeview instead of Listbox for better metadata display
remote_tree = ttk.Treeview(remote_list_frame, columns=("name", "size", "modified", "created", "permissions"), 
                          show="tree headings", height=15)
remote_tree.heading("#0", text="")
remote_tree.heading("name", text="Name")
remote_tree.heading("size", text="Size")
remote_tree.heading("modified", text="Modified")
remote_tree.heading("created", text="Created")
remote_tree.heading("permissions", text="Permissions")

remote_tree.column("#0", width=30, stretch=False)
remote_tree.column("name", width=200, anchor="w")
remote_tree.column("size", width=100, anchor="e")
remote_tree.column("modified", width=150, anchor="w")
remote_tree.column("created", width=150, anchor="w")
remote_tree.column("permissions", width=100, anchor="w")

remote_tree.pack(side="left", fill="both", expand=True)

remote_scrollbar = ttk.Scrollbar(remote_list_frame, orient="vertical", command=remote_tree.yview)
remote_scrollbar.pack(side="right", fill="y")
remote_tree.config(yscrollcommand=remote_scrollbar.set)

# Keep remote_listbox reference for backward compatibility (will use tree instead)
remote_listbox = remote_tree

remote_tree.bind("<Double-Button-1>", on_remote_double_click)

# Remote context menu
remote_menu = tk.Menu(remote_listbox, tearoff=0)
remote_menu.add_command(label="⬇️ Download", command=download_file)
remote_menu.add_command(label="✏️ Rename", command=rename_remote_file)
remote_menu.add_command(label="🗑️ Delete", command=delete_remote_file)
remote_menu.add_separator()
remote_menu.add_command(label="📝 View/Edit", command=view_edit_remote_file)
remote_menu.add_command(label="ℹ️ Properties", command=show_file_properties)
remote_menu.add_separator()
remote_menu.add_command(label="🔐 Change Permissions", command=lambda: change_remote_permissions())
remote_menu.add_separator()
remote_menu.add_command(label="📁 Create Directory", command=create_remote_directory)
remote_menu.add_command(label="🔄 Refresh", command=refresh_remote_files_wrapper)

def show_remote_menu(event):
    """Show context menu for remote files."""
    try:
        remote_menu.tk_popup(event.x_root, event.y_root)
    finally:
        remote_menu.grab_release()

remote_listbox.bind("<Button-3>", show_remote_menu)

# Remote buttons frame
remote_btn_frame = tk.Frame(remote_frame, bg=COLOR_CARD)
remote_btn_frame.pack(fill="x", padx=10, pady=5)

download_btn = tk.Button(remote_btn_frame, text="⬇️ Download", command=download_file, bg=COLOR_SECONDARY, fg="white", font=("TkDefaultFont", 9, "bold"), padx=10, pady=6, cursor="hand2")
download_btn.pack(side="left", padx=2)

tk.Button(remote_btn_frame, text="📝 Edit", command=view_edit_remote_file, bg=COLOR_PRIMARY, fg="white", font=("TkDefaultFont", 9, "bold"), padx=10, pady=6, cursor="hand2").pack(side="left", padx=2)

tk.Button(remote_btn_frame, text="✏️ Rename", command=rename_remote_file, bg=COLOR_TEXT_LIGHT, fg="white", font=("TkDefaultFont", 9, "bold"), padx=10, pady=6, cursor="hand2").pack(side="left", padx=2)

tk.Button(remote_btn_frame, text="🗑️ Delete", command=delete_remote_file, bg=COLOR_DANGER, fg="white", font=("TkDefaultFont", 9, "bold"), padx=10, pady=6, cursor="hand2").pack(side="left", padx=2)

tk.Button(remote_btn_frame, text="📁 New Dir", command=create_remote_directory, bg=COLOR_SECONDARY, fg="white", font=("TkDefaultFont", 9, "bold"), padx=10, pady=6, cursor="hand2").pack(side="left", padx=2)

tk.Button(remote_btn_frame, text="🔄 Refresh", command=refresh_remote_files_wrapper, bg=COLOR_TEXT_LIGHT, fg="white", font=("TkDefaultFont", 9, "bold"), padx=10, pady=6, cursor="hand2").pack(side="left", padx=2)

# Local files - always visible
local_frame = tk.Frame(file_manager_frame, bg=COLOR_CARD, relief="flat", borderwidth=1, highlightbackground=COLOR_BORDER, highlightthickness=1)
local_frame.pack(side="right", fill="both", expand=True, padx=(5, 0), pady=10)

tk.Label(local_frame, text="📁 Local Files", font=("TkDefaultFont", 12, "bold"), bg=COLOR_CARD, fg=COLOR_TEXT).pack(pady=10)

local_path_frame = tk.Frame(local_frame, bg=COLOR_CARD)
local_path_frame.pack(fill="x", padx=10, pady=5)
tk.Entry(local_path_frame, textvariable=local_path_var, font=("TkDefaultFont", 9), width=40).pack(side="left", fill="x", expand=True, padx=(0, 5))
tk.Button(local_path_frame, text="Browse", command=browse_local_folder, bg=COLOR_TEXT_LIGHT, fg="white", font=("TkDefaultFont", 9), padx=10, pady=4, cursor="hand2").pack(side="left")

# Local file list with Treeview (supports columns for metadata)
local_list_frame = tk.Frame(local_frame, bg=COLOR_CARD)
local_list_frame.pack(fill="both", expand=True, padx=10, pady=10)

# Use Treeview instead of Listbox for better metadata display
local_tree = ttk.Treeview(local_list_frame, columns=("name", "size", "modified", "created", "permissions"), 
                         show="tree headings", height=15)
local_tree.heading("#0", text="")
local_tree.heading("name", text="Name")
local_tree.heading("size", text="Size")
local_tree.heading("modified", text="Modified")
local_tree.heading("created", text="Created")
local_tree.heading("permissions", text="Permissions")

local_tree.column("#0", width=30, stretch=False)
local_tree.column("name", width=200, anchor="w")
local_tree.column("size", width=100, anchor="e")
local_tree.column("modified", width=150, anchor="w")
local_tree.column("created", width=150, anchor="w")
local_tree.column("permissions", width=100, anchor="w")

local_tree.pack(side="left", fill="both", expand=True)

local_scrollbar = ttk.Scrollbar(local_list_frame, orient="vertical", command=local_tree.yview)
local_scrollbar.pack(side="right", fill="y")
local_tree.config(yscrollcommand=local_scrollbar.set)

# Keep local_listbox reference for backward compatibility (will use tree instead)
local_listbox = local_tree

local_tree.bind("<Double-Button-1>", on_local_double_click)

# Local context menu
local_menu = tk.Menu(local_listbox, tearoff=0)
local_menu.add_command(label="⬆️ Upload", command=upload_file)
local_menu.add_command(label="✏️ Rename", command=rename_local_file)
local_menu.add_command(label="🗑️ Delete", command=delete_local_file)
local_menu.add_separator()
local_menu.add_command(label="🔐 Change Permissions", command=lambda: change_local_permissions())
local_menu.add_separator()
local_menu.add_command(label="📁 Create Directory", command=create_local_directory)
local_menu.add_command(label="🔄 Refresh", command=refresh_local_files_wrapper)

def show_local_menu(event):
    """Show context menu for local files."""
    try:
        local_menu.tk_popup(event.x_root, event.y_root)
    finally:
        local_menu.grab_release()

local_listbox.bind("<Button-3>", show_local_menu)

# Local buttons frame
local_btn_frame = tk.Frame(local_frame, bg=COLOR_CARD)
local_btn_frame.pack(fill="x", padx=10, pady=5)

upload_btn = tk.Button(local_btn_frame, text="⬆️ Upload", command=upload_file, bg=COLOR_SECONDARY, fg="white", font=("TkDefaultFont", 9, "bold"), padx=10, pady=6, cursor="hand2")
upload_btn.pack(side="left", padx=2)

tk.Button(local_btn_frame, text="✏️ Rename", command=rename_local_file, bg=COLOR_TEXT_LIGHT, fg="white", font=("TkDefaultFont", 9, "bold"), padx=10, pady=6, cursor="hand2").pack(side="left", padx=2)

tk.Button(local_btn_frame, text="🗑️ Delete", command=delete_local_file, bg=COLOR_DANGER, fg="white", font=("TkDefaultFont", 9, "bold"), padx=10, pady=6, cursor="hand2").pack(side="left", padx=2)

tk.Button(local_btn_frame, text="📁 New Dir", command=create_local_directory, bg=COLOR_SECONDARY, fg="white", font=("TkDefaultFont", 9, "bold"), padx=10, pady=6, cursor="hand2").pack(side="left", padx=2)

tk.Button(local_btn_frame, text="🔄 Refresh", command=refresh_local_files_wrapper, bg=COLOR_TEXT_LIGHT, fg="white", font=("TkDefaultFont", 9, "bold"), padx=10, pady=6, cursor="hand2").pack(side="left", padx=2)

# Initialize local file list after a short delay to ensure UI is ready
def init_local_files():
    try:
        refresh_local_files()
    except Exception as e:
        print(f"Error initializing local files: {e}")

root.after(100, init_local_files)

# Keyboard shortcuts
def on_key_press(event):
    """Handle keyboard shortcuts."""
    if not current_client:
        return
    
    # F5 - Refresh
    if event.keysym == 'F5':
        if root.focus_get() == remote_listbox:
            refresh_remote_files_wrapper()
        elif root.focus_get() == local_listbox:
            refresh_local_files_wrapper()
    
    # Delete key - Delete selected
    elif event.keysym == 'Delete':
        if root.focus_get() == remote_listbox:
            delete_remote_file()
        elif root.focus_get() == local_listbox:
            delete_local_file()
    
    # F2 - Rename
    elif event.keysym == 'F2':
        if root.focus_get() == remote_listbox:
            rename_remote_file()
        elif root.focus_get() == local_listbox:
            rename_local_file()
    
    # Enter - Open/Download/Upload
    elif event.keysym == 'Return':
        if root.focus_get() == remote_listbox:
            item = get_selected_remote_item()
            if item:
                name = extract_filename(item)
                
                if name == ".." or (isinstance(item, str) and item.startswith("📁")):
                    on_remote_double_click(None)
                else:
                    download_file()
        elif root.focus_get() == local_listbox:
            item = get_selected_local_item()
            if item:
                name = extract_filename(item)
                
                if name == ".." or (isinstance(item, str) and item.startswith("📁")):
                    on_local_double_click(None)
                elif current_client:
                    upload_file()

root.bind("<KeyPress>", on_key_press)

# Search/filter functionality
def add_search_filter():
    """Add search filter to file lists."""
    # Remote search
    remote_search_frame = tk.Frame(remote_frame, bg=COLOR_CARD)
    remote_search_frame.pack(fill="x", padx=10, pady=(5, 0))
    
    remote_search_var = tk.StringVar()
    remote_search_var.trace("w", lambda *args: filter_remote_files())
    
    tk.Label(remote_search_frame, text="🔍", bg=COLOR_CARD, fg=COLOR_TEXT_LIGHT).pack(side="left", padx=(0, 5))
    remote_search_entry = tk.Entry(remote_search_frame, textvariable=remote_search_var, font=("TkDefaultFont", 9), width=20)
    remote_search_entry.pack(side="left", fill="x", expand=True)
    remote_search_entry.insert(0, "Search files...")
    remote_search_entry.config(fg=COLOR_TEXT_LIGHT)
    
    def on_remote_search_focus_in(event):
        if remote_search_entry.get() == "Search files...":
            remote_search_entry.delete(0, tk.END)
            remote_search_entry.config(fg=COLOR_TEXT)
    
    def on_remote_search_focus_out(event):
        if not remote_search_entry.get():
            remote_search_entry.insert(0, "Search files...")
            remote_search_entry.config(fg=COLOR_TEXT_LIGHT)
    
    remote_search_entry.bind("<FocusIn>", on_remote_search_focus_in)
    remote_search_entry.bind("<FocusOut>", on_remote_search_focus_out)
    
    # Local search
    local_search_frame = tk.Frame(local_frame, bg=COLOR_CARD)
    local_search_frame.pack(fill="x", padx=10, pady=(5, 0))
    
    local_search_var = tk.StringVar()
    local_search_var.trace("w", lambda *args: filter_local_files())
    
    tk.Label(local_search_frame, text="🔍", bg=COLOR_CARD, fg=COLOR_TEXT_LIGHT).pack(side="left", padx=(0, 5))
    local_search_entry = tk.Entry(local_search_frame, textvariable=local_search_var, font=("TkDefaultFont", 9), width=20)
    local_search_entry.pack(side="left", fill="x", expand=True)
    local_search_entry.insert(0, "Search files...")
    local_search_entry.config(fg=COLOR_TEXT_LIGHT)
    
    def on_local_search_focus_in(event):
        if local_search_entry.get() == "Search files...":
            local_search_entry.delete(0, tk.END)
            local_search_entry.config(fg=COLOR_TEXT)
    
    def on_local_search_focus_out(event):
        if not local_search_entry.get():
            local_search_entry.insert(0, "Search files...")
            local_search_entry.config(fg=COLOR_TEXT_LIGHT)
    
    local_search_entry.bind("<FocusIn>", on_local_search_focus_in)
    local_search_entry.bind("<FocusOut>", on_local_search_focus_out)

# Store original file lists for filtering
remote_files_backup = []
local_files_backup = []

def filter_remote_files():
    """Filter remote file list based on search."""
    # This is a placeholder - full implementation would filter the listbox
    pass

def filter_local_files():
    """Filter local file list based on search."""
    # This is a placeholder - full implementation would filter the listbox
    pass

# Add search after UI is created
root.after(100, add_search_filter)

# Progress frame
progress_frame = tk.Frame(root, bg=COLOR_BG, relief="flat", borderwidth=1)
progress_inner = tk.Frame(progress_frame, bg=COLOR_BG)
progress_inner.pack(fill="x", padx=15, pady=10)

progress_bar = ttk.Progressbar(progress_inner, mode="indeterminate", length=200)
progress_bar.pack(side="left", padx=(0, 10))

status_label = tk.Label(progress_inner, textvariable=status_var, font=("TkDefaultFont", 10), bg=COLOR_BG, fg=COLOR_TEXT, anchor="w")
status_label.pack(side="left", fill="x", expand=True)

# Status bar at bottom
status_bar = tk.Frame(root, bg=COLOR_BORDER, height=25)
status_bar.pack(fill="x", side="bottom")
status_bar.pack_propagate(False)

status_info_var = tk.StringVar(value="Ready")
status_info_label = tk.Label(status_bar, textvariable=status_info_var, font=("TkDefaultFont", 9), bg=COLOR_BORDER, fg=COLOR_TEXT, anchor="w", padx=10)
status_info_label.pack(side="left", fill="x", expand=True)

def update_status_info():
    """Update status bar with file counts and connection info."""
    try:
        if current_client:
            try:
                # Get counts from treeview or listbox
                if hasattr(remote_listbox, 'get_children'):
                    remote_count = len(remote_listbox.get_children())
                else:
                    remote_count = remote_listbox.size()
                
                if hasattr(local_listbox, 'get_children'):
                    local_count = len(local_listbox.get_children())
                else:
                    local_count = local_listbox.size()
                
                status_info_var.set(f"Connected: {current_connection_name} | Remote: {remote_count} items | Local: {local_count} items")
            except:
                status_info_var.set(f"Connected: {current_connection_name}")
        else:
            status_info_var.set("Not connected")
    except:
        pass  # UI elements might not be created yet

# Wrapper functions are already defined above (line ~792) and will work correctly
# They use try/except to handle update_status_info not being defined yet

# Update the original update_remote_list to also update status
def update_remote_list(files, current_path):
    """Update remote file list with metadata. Thread-safe version."""
    try:
        # Validate inputs
        if not files:
            files = []  # Ensure files is a list, not None
        
        if not current_path:
            current_path = "/"
        
        # Verify client is still connected before updating
        if not current_client:
            print("update_remote_list: Client not connected, aborting update")
            return
        
        print(f"update_remote_list: Updating with {len(files)} files in {current_path}")
        
        remote_path_var.set(current_path)
        
        # Store current items count before clearing (for debugging)
        try:
            if hasattr(remote_listbox, 'get_children'):
                old_count = len(remote_listbox.get_children())
            else:
                old_count = remote_listbox.size()
        except:
            old_count = 0
        
        # Clear tree/listbox - do this atomically and safely
        try:
            if hasattr(remote_listbox, 'get_children'):  # Treeview
                # Get all children first, then delete them one by one
                children = list(remote_listbox.get_children())
                for item in children:
                    try:
                        remote_listbox.delete(item)
                    except:
                        pass  # Item might already be deleted
            elif hasattr(remote_listbox, 'delete'):  # Listbox
                try:
                    remote_listbox.delete(0, tk.END)
                except:
                    pass  # List might be empty
        except Exception as e:
            print(f"Error clearing remote list: {e}")
            # Continue anyway - try to populate
        
        # Add parent directory first
        if current_path != "/":
            try:
                if hasattr(remote_listbox, 'insert'):  # Treeview
                    remote_listbox.insert("", "end", text="📁", values=("..", "", "", "", ""))
                else:  # Listbox
                    remote_listbox.insert(0, "📁 ..")
            except Exception as e:
                print(f"Error adding parent directory: {e}")
        
        # Process files - ensure we have files to process
        if not files:
            # If no files, just show parent directory if available
            print(f"update_remote_list: No files to display (was {old_count} items)")
            root.after(100, update_status_info)
            return
        
        file_count = 0
        for file_line in files:
            if file_line and file_line.strip():
                try:
                    parts = file_line.split()
                    if len(parts) < 9:
                        continue
                    
                    is_dir = file_line.startswith('d')
                    filename = parts[-1]
                    permissions = parts[0] if len(parts) > 0 else ""
                    size = int(parts[4]) if len(parts) > 4 and parts[4].isdigit() else 0
                    
                    # Parse date/time
                    date_str = " ".join(parts[5:8]) if len(parts) > 7 else ""
                    mtime_str = date_str if date_str else "N/A"
                    
                    # Get detailed info
                    remote_path_full = f"{current_path.rstrip('/')}/{filename}" if current_path != "/" else f"/{filename}"
                    info = None
                    try:
                        if not is_dir:
                            info = current_client.get_file_info(remote_path_full)
                    except:
                        pass
                    
                    if info:
                        mtime = info.get('mtime')
                        mtime_str = mtime.strftime("%Y-%m-%d %H:%M:%S") if mtime else mtime_str
                        ctime = info.get('ctime')
                        ctime_str = ctime.strftime("%Y-%m-%d %H:%M:%S") if ctime else "N/A"
                        perm_str = format_permissions(info.get('permissions', permissions))
                    else:
                        ctime_str = "N/A"
                        perm_str = format_permissions(permissions) if permissions else "N/A"
                    
                    size_str = format_file_size(size) if not is_dir else "<DIR>"
                    icon = "📁" if is_dir else "📄"
                    
                    if hasattr(remote_listbox, 'insert'):  # Treeview
                        remote_listbox.insert("", "end", text=icon,
                                            values=(filename, size_str, mtime_str, ctime_str, perm_str),
                                            tags=("dir" if is_dir else "file",))
                    else:  # Listbox
                        remote_listbox.insert(tk.END, f"{icon} {filename}")
                    file_count += 1
                except Exception as e:
                    # Fallback to simple display
                    try:
                        parts = file_line.split()
                        if parts:
                            filename = parts[-1]
                            is_dir = file_line.startswith('d')
                            icon = "📁" if is_dir else "📄"
                            if hasattr(remote_listbox, 'insert'):  # Treeview
                                remote_listbox.insert("", "end", text=icon,
                                                    values=(filename, "N/A", "N/A", "N/A", "N/A"))
                            else:  # Listbox
                                remote_listbox.insert(tk.END, f"{icon} {filename}")
                            file_count += 1
                    except:
                        pass  # Skip this file if we can't parse it
        
        # Update status after populating list
        print(f"update_remote_list: Successfully updated with {file_count} files in {current_path} (was {old_count} items)")
        
        # Verify we actually added items
        try:
            if hasattr(remote_listbox, 'get_children'):
                new_count = len(remote_listbox.get_children())
            else:
                new_count = remote_listbox.size()
            if new_count == 0 and file_count > 0:
                print(f"WARNING: Expected {file_count} items but list is empty!")
        except:
            pass
        
        root.after(100, update_status_info)
    except Exception as e:
        import traceback
        error_msg = traceback.format_exc()
        print(f"Error in update_remote_list: {error_msg}")
        # Try to restore with at least parent directory
        try:
            if current_client:  # Only if still connected
                if current_path != "/":
                    try:
                        if hasattr(remote_listbox, 'insert'):  # Treeview
                            remote_listbox.insert("", "end", text="📁", values=("..", "", "", "", ""))
                        else:  # Listbox
                            remote_listbox.insert(0, "📁 ..")
                    except:
                        pass
        except Exception as restore_error:
            print(f"Error in error recovery: {restore_error}")

root.mainloop()

