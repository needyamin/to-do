#!/usr/bin/env python3
"""
Enhanced FTP/FTPS/SFTP Client GUI with FileZilla-like features.

Advanced Features:
  - Transfer Queue System (pause/resume/cancel)
  - Drag and Drop support
  - File Comparison and Directory Sync
  - Advanced Log Viewer with filters
  - Transfer Speed Limits and Statistics
  - Multiple Concurrent Transfers
  - File Permissions Editor (chmod)
  - Directory Bookmarks
  - Advanced Search/Filter
  - Per-file Progress Indicators
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
import queue as queue_module
from datetime import datetime
from tkinter import filedialog, messagebox, simpledialog
from tkinter import ttk
from pathlib import Path
import ftplib
from ftplib import FTP, FTP_TLS
from collections import deque
import hashlib

# Add project root to path for icon_utils
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from icon_utils import set_window_icon
from settings_db import get_settings_db_path

# Optional SFTP support
try:
    import paramiko
    SFTP_AVAILABLE = True
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
        self.callbacks = {
            'progress': [],
            'complete': [],
            'error': []
        }
    
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
                    # Start transfer in background thread
                    transfer.thread = threading.Thread(target=self._execute_transfer, args=(transfer,), daemon=True)
                    transfer.thread.start()
    
    def _execute_transfer(self, transfer):
        """Execute a single transfer."""
        transfer.start_time = time.time()
        # This will be implemented by the GUI to use current_client
        pass
    
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

# Global transfer queue
transfer_queue = TransferQueue(max_concurrent=3)

# --- Database Manager (same as before) ---
class DatabaseManager:
    """Manages SQLite database for storing FTP connections and history."""
    
    def __init__(self, db_path=None):
        if db_path is None:
            db_path = get_settings_db_path()
        
        self.db_path = db_path
        self.init_database()
        
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
        
        # Saved FTP connections
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
        
        # Transfer logs
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
            cursor.execute("SELECT name, protocol, host, port, username, password, use_tls FROM ftp_connections WHERE is_favorite = 1 ORDER BY last_used DESC")
        else:
            cursor.execute("SELECT name, protocol, host, port, username, password, use_tls FROM ftp_connections ORDER BY last_used DESC")
        
        results = cursor.fetchall()
        conn.close()
        
        connections = []
        for row in results:
            name, protocol, host, port, username, encoded_password, use_tls = row
            password = base64.b64decode(encoded_password.encode()).decode() if encoded_password else ""
            connections.append({
                'name': name,
                'protocol': protocol,
                'host': host,
                'port': port,
                'username': username,
                'password': password,
                'use_tls': bool(use_tls)
            })
        
        return connections
    
    def delete_connection(self, name):
        """Delete a connection profile."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM ftp_connections WHERE name = ?", (name,))
        conn.commit()
        conn.close()
    
    def add_history(self, connection_name, operation, local_path, remote_path, status, error_message=None, file_size=0, duration=0):
        """Add an operation to history."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO ftp_history 
            (connection_name, operation, local_path, remote_path, status, error_message, file_size, started_at, completed_at, duration_seconds)
            VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, ?)
        """, (connection_name, operation, local_path, remote_path, status, error_message, file_size, duration))
        conn.commit()
        conn.close()
    
    def get_history(self, connection_name=None, limit=100):
        """Get operation history."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        if connection_name:
            cursor.execute("""
                SELECT started_at, operation, local_path, remote_path, status, error_message, file_size, duration_seconds
                FROM ftp_history 
                WHERE connection_name = ?
                ORDER BY started_at DESC
                LIMIT ?
            """, (connection_name, limit))
        else:
            cursor.execute("""
                SELECT started_at, operation, local_path, remote_path, status, error_message, file_size, duration_seconds
                FROM ftp_history 
                ORDER BY started_at DESC
                LIMIT ?
            """, (limit,))
        
        results = cursor.fetchall()
        conn.close()
        
        history = []
        for row in results:
            history.append({
                'started_at': row[0],
                'operation': row[1],
                'local_path': row[2],
                'remote_path': row[3],
                'status': row[4],
                'error_message': row[5],
                'file_size': row[6] or 0,
                'duration_seconds': row[7] or 0
            })
        
        return history
    
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

# Initialize database
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
            if not self.host or not self.host.strip():
                return False, "Host cannot be empty"
            
            timeout = 10
            
            if self.use_tls:
                self.connection = FTP_TLS()
                self.connection.connect(self.host, self.port, timeout=timeout)
                self.connection.login(self.username, self.password)
                self.connection.prot_p()
            else:
                self.connection = FTP()
                self.connection.connect(self.host, self.port, timeout=timeout)
                self.connection.login(self.username, self.password)
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
        except ftplib.error_perm as e:
            return False, f"Authentication failed: {e}"
        except ftplib.error_temp as e:
            return False, f"Temporary error: {e}"
        except Exception as e:
            error_msg = str(e)
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
            size = self.get_file_size(remote_path)
            mtime = None
            try:
                mdtm = self.connection.voidcmd(f"MDTM {remote_path}")
                if mdtm.startswith("213"):
                    mtime_str = mdtm.split()[1]
                    mtime = datetime.strptime(mtime_str, "%Y%m%d%H%M%S")
            except:
                pass
            
            permissions = None
            owner = None
            group = None
            try:
                lines = []
                self.connection.retrlines(f'LIST {remote_path}', lines.append)
                if lines:
                    line = lines[0] if lines else ""
                    parts = line.split()
                    if len(parts) >= 9:
                        permissions = parts[0]
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
                'ctime': None
            }
        except:
            return None
    
    def set_permissions(self, remote_path, mode):
        """Set file permissions (chmod). Returns (success, message)."""
        if not self.connection:
            return False, "Not connected"
        try:
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
                'permissions': stat_info.st_mode,
                'ctime': datetime.fromtimestamp(stat_info.st_ctime) if hasattr(stat_info, 'st_ctime') else None,
                'atime': datetime.fromtimestamp(stat_info.st_atime) if hasattr(stat_info, 'st_atime') else None
            }
        except:
            return None
    
    def set_permissions(self, remote_path, mode):
        """Set file permissions (chmod). Returns (success, message)."""
        if not self.sftp:
            return False, "Not connected"
        try:
            self.sftp.chmod(remote_path, mode)
            return True, "Permissions updated"
        except Exception as e:
            return False, f"Failed to set permissions: {e}"
    
    def set_mtime(self, remote_path, mtime):
        """Set modification time. Returns (success, message)."""
        if not self.sftp:
            return False, "Not connected"
        try:
            import time
            mtime_ts = time.mktime(mtime.timetuple())
            self.sftp.utime(remote_path, (mtime_ts, mtime_ts))
            return True, "Modification time updated"
        except Exception as e:
            return False, f"Failed to set modification time: {e}"

# Global client instance
current_client = None
current_connection_name = None

