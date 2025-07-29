import tkinter as tk
from tkinter import messagebox
import webbrowser, sqlite3, time
from datetime import datetime, timedelta
import pytz, os
import winsound  # For Windows sound notification
import subprocess  # For MP3 playback
from playsound import playsound
import threading


db_folder = r"C:\YAMiN\database"
os.makedirs(db_folder, exist_ok=True)  # Makes sure the folder exists

DB_NAME = os.path.join(db_folder, "sweethart.db")
os.makedirs(os.path.dirname(DB_NAME), exist_ok=True)

# Global set to track overdue tasks that have already played sound
overdue_sound_played = set()

# Global variables for blinking effect
blinking_tasks = set()  # Track which tasks are currently blinking
blink_state = True  # Toggle for blinking effect

# Global icon path
ICON_PATH = os.path.join(os.getcwd(), "icon.ico")

def set_window_icon(window):
    """Set icon for a window if icon file exists"""
    try:
        if os.path.exists(ICON_PATH):
            window.iconbitmap(ICON_PATH)
    except Exception as e:
        print(f"Error setting window icon: {e}")

def create_scrolled_listbox(parent, **kwargs):
    frame = tk.Frame(parent, bg="white")
    frame.pack(fill="both", expand=True, padx=kwargs.pop('padx', 0), pady=kwargs.pop('pady', 0))
    
    scrollbar = tk.Scrollbar(frame)
    scrollbar.pack(side="right", fill="y")
    
    listbox = tk.Listbox(frame, **kwargs)
    listbox.pack(side="left", fill="both", expand=True)
    
    scrollbar.config(command=listbox.yview)
    listbox.config(yscrollcommand=scrollbar.set)
    
    return listbox

def add_placeholder(entry, placeholder):
    placeholder_color = '#aaa'
    default_color = entry['fg']

    def on_focus_in(event):
        if entry.get() == placeholder:
            entry.delete(0, tk.END)
            entry.config(fg=default_color)

    def on_focus_out(event):
        if not entry.get():
            entry.insert(0, placeholder)
            entry.config(fg=placeholder_color)

    entry.insert(0, placeholder)
    entry.config(fg=placeholder_color)
    entry.bind('<FocusIn>', on_focus_in)
    entry.bind('<FocusOut>', on_focus_out)

# ----------- DATABASE SETUP -----------
def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    
    # Create todos table with new schema
    c.execute('''CREATE TABLE IF NOT EXISTS todos 
                 (id INTEGER PRIMARY KEY, 
                  task TEXT, 
                  done INTEGER,
                  deadline TEXT,
                  created_at TEXT)''')
    
    # Check if deadline column exists, if not add it
    c.execute("PRAGMA table_info(todos)")
    columns = [column[1] for column in c.fetchall()]
    
    if 'deadline' not in columns:
        c.execute("ALTER TABLE todos ADD COLUMN deadline TEXT")
    
    if 'created_at' not in columns:
        c.execute("ALTER TABLE todos ADD COLUMN created_at TEXT")
        # Update existing rows with current timestamp
        c.execute("UPDATE todos SET created_at = datetime('now') WHERE created_at IS NULL")
    
    # Create notes table with new schema
    c.execute('''CREATE TABLE IF NOT EXISTS notes 
                 (id INTEGER PRIMARY KEY,
                  title TEXT NOT NULL,
                  content TEXT NOT NULL,
                  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                  order_index INTEGER DEFAULT 0)''')
    
    # Check if order_index column exists, if not add it
    c.execute("PRAGMA table_info(notes)")
    note_columns = [column[1] for column in c.fetchall()]
    
    if 'order_index' not in note_columns:
        c.execute("ALTER TABLE notes ADD COLUMN order_index INTEGER DEFAULT 0")
    
    # Create links table with new schema
    c.execute('''CREATE TABLE IF NOT EXISTS links 
                 (id INTEGER PRIMARY KEY, 
                  name TEXT, 
                  url TEXT,
                  order_index INTEGER DEFAULT 0)''')
    
    # Check if order_index column exists, if not add it
    c.execute("PRAGMA table_info(links)")
    link_columns = [column[1] for column in c.fetchall()]
    
    if 'order_index' not in link_columns:
        c.execute("ALTER TABLE links ADD COLUMN order_index INTEGER DEFAULT 0")
    
    conn.commit()
    conn.close()

def load_todos():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT task, done, deadline, created_at FROM todos ORDER BY created_at ASC")
    todos = c.fetchall()
    conn.close()
    return todos

def save_todos(todo_listbox):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("DELETE FROM todos")
    for i in range(todo_listbox.size()):
        task = todo_listbox.get(i)
        done = 1 if task.startswith("✅") else 0
        # Extract task text and deadline
        if "⏰" in task:
            parts = task.split("⏰")
            clean_task = parts[0][2:].strip()  # Remove checkbox
            # Extract the deadline part
            deadline_part = parts[1].strip() if len(parts) > 1 else ""
            
            # Remove any time display formatting like "(2 hours left)" or "(OVERDUE!)"
            if "(" in deadline_part:
                deadline_part = deadline_part.split("(")[0].strip()
            
            # Try to parse the formatted deadline back to raw format
            try:
                deadline_obj = datetime.strptime(deadline_part, "%d %B %y, %I:%M %p")
                deadline = deadline_obj.strftime("%Y-%m-%d %H:%M")
            except ValueError:
                # If parsing fails, check if it's already in raw format
                if len(deadline_part) == 16 and "-" in deadline_part and ":" in deadline_part:
                    deadline = deadline_part
                else:
                    deadline = deadline_part  # Keep as is if parsing fails
        else:
            clean_task = task[2:].strip()
            deadline = ""
        c.execute("INSERT INTO todos (task, done, deadline) VALUES (?, ?, ?)", (clean_task, done, deadline))
    conn.commit()
    conn.close()

def load_links():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT id, name, url, order_index FROM links ORDER BY order_index ASC")
    links = c.fetchall()
    conn.close()
    return links

def save_link(name, url):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT MAX(order_index) FROM links")
    max_order = c.fetchone()[0] or 0
    c.execute("INSERT INTO links (name, url, order_index) VALUES (?, ?, ?)", (name, url, max_order + 1))
    conn.commit()
    conn.close()

def delete_link(link_id):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("DELETE FROM links WHERE id = ?", (link_id,))
    conn.commit()
    conn.close()

def update_link_order(link_id, new_order):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("UPDATE links SET order_index = ? WHERE id = ?", (new_order, link_id))
    conn.commit()
    conn.close()

def save_note(title, content):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT MAX(order_index) FROM notes")
    max_order = c.fetchone()[0] or 0
    c.execute("INSERT INTO notes (title, content, order_index) VALUES (?, ?, ?)", (title, content, max_order + 1))
    conn.commit()
    conn.close()

def delete_note(note_id):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("DELETE FROM notes WHERE id = ?", (note_id,))
    conn.commit()
    conn.close()

def update_note_order(note_id, new_order):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("UPDATE notes SET order_index = ? WHERE id = ?", (new_order, note_id))
    conn.commit()
    conn.close()

def get_all_notes():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT id, title, content, created_at, order_index FROM notes ORDER BY order_index ASC")
    notes = c.fetchall()
    conn.close()
    return notes

# ----------- REORDERING FUNCTIONS -----------
def move_up(listbox, save_func, update_order_func, items_data):
    selection = listbox.curselection()
    if selection and selection[0] > 0:
        index = selection[0]
        text = listbox.get(index)
        listbox.delete(index)
        listbox.insert(index - 1, text)
        listbox.selection_set(index - 1)
        
        # Update order in database
        if items_data:
            item_id = items_data[index][0]  # Assuming first element is ID
            update_order_func(item_id, index)
        save_func(listbox)

def move_down(listbox, save_func, update_order_func, items_data):
    selection = listbox.curselection()
    if selection and selection[0] < listbox.size() - 1:
        index = selection[0]
        text = listbox.get(index)
        listbox.delete(index)
        listbox.insert(index + 1, text)
        listbox.selection_set(index + 1)
        
        # Update order in database
        if items_data:
            item_id = items_data[index][0]  # Assuming first element is ID
            update_order_func(item_id, index + 2)
        save_func(listbox)

# ----------- TIMER FUNCTIONS -----------
def add_timer_window():
    # Check if any task is selected first
    selection = todo_listbox.curselection()
    if not selection:
        messagebox.showwarning("No Task Selected", "Please select a task first before adding a timer.")
        return
    
    # Store the selected task index
    selected_index = selection[0]
    
    timer_window = tk.Toplevel(root)
    timer_window.title("Add Timer to Task")
    timer_window.geometry("500x700")
    timer_window.config(bg="white")
    timer_window.resizable(False, False)
    
    # Set icon for timer window
    set_window_icon(timer_window)
    
    # Center the window
    timer_window.transient(root)
    timer_window.grab_set()
    
    container = tk.Frame(timer_window, bg="white", padx=25, pady=25)
    container.pack(fill="both", expand=True)
    
    # Title
    title_label = tk.Label(container, text="⏰ Set Task Deadline", 
                          font=("Segoe UI", 16, "bold"), bg="white", fg="#333")
    title_label.pack(pady=(0, 20))
    
    # Show selected task
    selected_task = todo_listbox.get(selected_index)
    task_text = selected_task.split("⏰")[0] if "⏰" in selected_task else selected_task
    task_text = task_text[2:].strip() if task_text.startswith(("☐", "✅")) else task_text
    
    task_label = tk.Label(container, text=f"Selected Task: {task_text}", 
                          font=("Segoe UI", 11), bg="white", fg="#666",
                          wraplength=450)
    task_label.pack(pady=(0, 20))
    
    # Date entry with better styling
    date_frame = tk.Frame(container, bg="white")
    date_frame.pack(fill="x", pady=8)
    tk.Label(date_frame, text="📅 Date:", bg="white", font=("Segoe UI", 11, "bold")).pack(side="left")
    date_entry = tk.Entry(date_frame, font=("Segoe UI", 11), 
                         relief="solid", bd=1, bg="#f8f9fa")
    date_entry.pack(side="left", padx=(10, 0), fill="x", expand=True)
    date_entry.insert(0, datetime.now().strftime("%Y-%m-%d"))
    
    # 12-hour time selection frame
    time_frame = tk.Frame(container, bg="white")
    time_frame.pack(fill="x", pady=8)
    tk.Label(time_frame, text="🕐 Time:", bg="white", font=("Segoe UI", 11, "bold")).pack(side="left")
    
    # Time selection sub-frame
    time_select_frame = tk.Frame(time_frame, bg="white")
    time_select_frame.pack(side="left", padx=(10, 0), fill="x", expand=True)
    
    # Hour selection (12-hour format)
    hour_frame = tk.Frame(time_select_frame, bg="white")
    hour_frame.pack(side="left", padx=(0, 10))
    tk.Label(hour_frame, text="Hour:", bg="white", font=("Segoe UI", 9)).pack()
    hour_var = tk.StringVar(value="12")
    hour_spinbox = tk.Spinbox(hour_frame, from_=1, to=12, width=3, 
                              textvariable=hour_var, font=("Segoe UI", 11),
                              relief="solid", bd=1, bg="#f8f9fa")
    hour_spinbox.pack()
    
    # Minute selection
    minute_frame = tk.Frame(time_select_frame, bg="white")
    minute_frame.pack(side="left", padx=(0, 10))
    tk.Label(minute_frame, text="Minute:", bg="white", font=("Segoe UI", 9)).pack()
    minute_var = tk.StringVar(value="00")
    minute_spinbox = tk.Spinbox(minute_frame, from_=0, to=59, width=3,
                                textvariable=minute_var, font=("Segoe UI", 11),
                                relief="solid", bd=1, bg="#f8f9fa")
    minute_spinbox.pack()
    
    # AM/PM selection
    ampm_frame = tk.Frame(time_select_frame, bg="white")
    ampm_frame.pack(side="left")
    tk.Label(ampm_frame, text="AM/PM:", bg="white", font=("Segoe UI", 9)).pack()
    ampm_var = tk.StringVar(value="PM")
    ampm_menu = tk.OptionMenu(ampm_frame, ampm_var, "AM", "PM")
    ampm_menu.config(font=("Segoe UI", 11), relief="solid", bd=1, bg="#f8f9fa")
    ampm_menu.pack()
    
    # Clock-style time selector
    clock_frame = tk.Frame(container, bg="white")
    clock_frame.pack(fill="x", pady=15)
    tk.Label(clock_frame, text="🕰️ Clock Style Selector:", bg="white", font=("Segoe UI", 11, "bold")).pack(anchor="w", pady=(0, 10))
    
    # Create clock grid (4x6 grid for common times)
    clock_grid = tk.Frame(clock_frame, bg="white")
    clock_grid.pack(fill="x")
    
    # Common times in 12-hour format
    common_times = [
        ("6:00 AM", 6, 0, "AM"), ("7:00 AM", 7, 0, "AM"), ("8:00 AM", 8, 0, "AM"), ("9:00 AM", 9, 0, "AM"),
        ("10:00 AM", 10, 0, "AM"), ("11:00 AM", 11, 0, "AM"), ("12:00 PM", 12, 0, "PM"), ("1:00 PM", 1, 0, "PM"),
        ("2:00 PM", 2, 0, "PM"), ("3:00 PM", 3, 0, "PM"), ("4:00 PM", 4, 0, "PM"), ("5:00 PM", 5, 0, "PM"),
        ("6:00 PM", 6, 0, "PM"), ("7:00 PM", 7, 0, "PM"), ("8:00 PM", 8, 0, "PM"), ("9:00 PM", 9, 0, "PM"),
        ("10:00 PM", 10, 0, "PM"), ("11:00 PM", 11, 0, "PM"), ("12:00 AM", 12, 0, "AM"), ("1:00 AM", 1, 0, "AM"),
        ("2:00 AM", 2, 0, "AM"), ("3:00 AM", 3, 0, "AM"), ("4:00 AM", 4, 0, "AM"), ("5:00 AM", 5, 0, "AM")
    ]
    
    def set_clock_time(hour, minute, ampm):
        hour_var.set(str(hour))
        minute_var.set(f"{minute:02d}")
        ampm_var.set(ampm)
    
    # Create clock buttons in a grid
    for i, (time_str, hour, minute, ampm) in enumerate(common_times):
        row = i // 6
        col = i % 6
        
        btn = tk.Button(clock_grid, text=time_str, 
                       command=lambda h=hour, m=minute, a=ampm: set_clock_time(h, m, a),
                       bg="#e9ecef", fg="#495057", font=("Segoe UI", 9),
                       padx=8, pady=4, relief="solid", bd=1)
        btn.grid(row=row, column=col, padx=2, pady=2, sticky="ew")
    
    # Configure grid weights
    for i in range(6):
        clock_grid.columnconfigure(i, weight=1)
    
    # Quick time buttons (updated for 12-hour format)
    quick_time_frame = tk.Frame(container, bg="white")
    quick_time_frame.pack(fill="x", pady=15)
    tk.Label(quick_time_frame, text="Quick Times:", bg="white", font=("Segoe UI", 10)).pack(anchor="w")
    
    quick_buttons_frame = tk.Frame(quick_time_frame, bg="white")
    quick_buttons_frame.pack(fill="x", pady=(5, 0))
    
    def set_quick_time_12(hour, ampm):
        hour_var.set(str(hour))
        minute_var.set("00")
        ampm_var.set(ampm)
    
    tk.Button(quick_buttons_frame, text="9:00 AM", command=lambda: set_quick_time_12(9, "AM"),
              bg="#e9ecef", fg="#495057", font=("Segoe UI", 9),
              padx=8, pady=3).pack(side="left", padx=(0, 5))
    tk.Button(quick_buttons_frame, text="12:00 PM", command=lambda: set_quick_time_12(12, "PM"),
              bg="#e9ecef", fg="#495057", font=("Segoe UI", 9),
              padx=8, pady=3).pack(side="left", padx=(0, 5))
    tk.Button(quick_buttons_frame, text="3:00 PM", command=lambda: set_quick_time_12(3, "PM"),
              bg="#e9ecef", fg="#495057", font=("Segoe UI", 9),
              padx=8, pady=3).pack(side="left", padx=(0, 5))
    tk.Button(quick_buttons_frame, text="6:00 PM", command=lambda: set_quick_time_12(6, "PM"),
              bg="#e9ecef", fg="#495057", font=("Segoe UI", 9),
              padx=8, pady=3).pack(side="left", padx=(0, 5))
    
    # Status label
    status_label = tk.Label(container, text="", bg="white", font=("Segoe UI", 10))
    status_label.pack(pady=10)
    
    def apply_timer():
        try:
            date_str = date_entry.get().strip()
            hour = int(hour_var.get())
            minute = int(minute_var.get())
            ampm = ampm_var.get()
            
            # Validate inputs
            if not date_str or hour < 1 or hour > 12 or minute < 0 or minute > 59:
                status_label.config(text="❌ Please fill in valid date and time", fg="red")
                return
            
            # Convert 12-hour format to 24-hour format
            if ampm == "PM" and hour != 12:
                hour += 12
            elif ampm == "AM" and hour == 12:
                hour = 0
            
            # Format time string for datetime parsing
            time_str = f"{hour:02d}:{minute:02d}"
            deadline = f"{date_str} {time_str}"
            deadline_obj = datetime.strptime(deadline, "%Y-%m-%d %H:%M")  # Validate format
            
            # Check if the task still exists at the stored index
            if selected_index < todo_listbox.size():
                task = todo_listbox.get(selected_index)
                
                # Remove existing timer if any
                if "⏰" in task:
                    task = task.split("⏰")[0].strip()
                
                # Format the deadline for immediate display
                deadline_display = deadline_obj.strftime("%d %B %y, %I:%M %p")
                
                # Calculate time left for immediate display
                now = datetime.now()
                time_left = deadline_obj - now
                
                if time_left.total_seconds() <= 0:
                    # Already overdue
                    new_task = f"{task} ⏰ {deadline_display} (OVERDUE!)"
                    todo_listbox.delete(selected_index)
                    todo_listbox.insert(selected_index, new_task)
                    todo_listbox.itemconfig(selected_index, fg="red")
                else:
                    # Still time left
                    days = time_left.days
                    hours = time_left.seconds // 3600
                    minutes = (time_left.seconds % 3600) // 60
                    
                    if days > 0:
                        time_display = f"⏰ {deadline_display} ({days} days left)"
                    elif hours > 0:
                        time_display = f"⏰ {deadline_display} ({hours} hours left)"
                    else:
                        time_display = f"⏰ {deadline_display} ({minutes} min left)"
                    
                    new_task = f"{task} {time_display}"
                    todo_listbox.delete(selected_index)
                    todo_listbox.insert(selected_index, new_task)
                    
                    # Color coding based on urgency
                    if days == 0 and hours < 2:
                        todo_listbox.itemconfig(selected_index, fg="red")
                    elif days == 0 and hours < 6:
                        todo_listbox.itemconfig(selected_index, fg="orange")
                    elif days == 0:
                        todo_listbox.itemconfig(selected_index, fg="blue")
                    else:
                        todo_listbox.itemconfig(selected_index, fg="black")
                
                save_todos(todo_listbox)
                
                # Restore selection
                todo_listbox.selection_clear(0, tk.END)
                todo_listbox.selection_set(selected_index)
                on_todo_select(None)
                
                timer_window.destroy()
                status_label.config(text="✅ Timer added successfully!", fg="green")
            else:
                status_label.config(text="❌ Task no longer exists. Please select a task again.", fg="red")
        except ValueError:
            status_label.config(text="❌ Invalid format. Use: YYYY-MM-DD HH:MM", fg="red")
    
    def on_timer_window_close():
        # Restore selection when window is closed
        if selected_index < todo_listbox.size():
            todo_listbox.selection_clear(0, tk.END)
            todo_listbox.selection_set(selected_index)
            on_todo_select(None)
        timer_window.destroy()
    
    # Button frame
    button_frame = tk.Frame(container, bg="white")
    button_frame.pack(fill="x", pady=(20, 0))
    
    tk.Button(button_frame, text="Cancel", command=on_timer_window_close,
              bg="#6c757d", fg="white", font=("Segoe UI", 10),
              padx=20, pady=8).pack(side="left")
    
    tk.Button(button_frame, text="Apply Timer", command=apply_timer,
              bg="#28a745", fg="white", font=("Segoe UI", 10, "bold"),
              padx=20, pady=8).pack(side="right")
    
    # Bind Enter key to apply timer
    timer_window.bind('<Return>', lambda e: apply_timer())
    
    # Bind window close event
    timer_window.protocol("WM_DELETE_WINDOW", on_timer_window_close)
    
    # Focus on date entry
    date_entry.focus_set()

def update_timers():
    """Update timer displays and check for overdue tasks"""
    global blink_state
    
    for i in range(todo_listbox.size()):
        task = todo_listbox.get(i)
        if "⏰" in task:
            parts = task.split("⏰")
            task_text = parts[0]
            deadline_str = parts[1].strip()
            
            # Remove any existing time display
            if "(" in deadline_str:
                deadline_str = deadline_str.split("(")[0].strip()
            
            try:
                # Parse the raw deadline format
                deadline = datetime.strptime(deadline_str, "%Y-%m-%d %H:%M")
                now = datetime.now()
                time_left = deadline - now
                
                # Format deadline for display
                deadline_display = deadline.strftime("%d %B %y, %I:%M %p")
                
                if time_left.total_seconds() <= 0:
                    # Overdue
                    new_task = f"{task_text} ⏰ {deadline_display} (OVERDUE!)"
                    todo_listbox.delete(i)
                    todo_listbox.insert(i, new_task)
                    
                    # Add to blinking tasks set
                    task_id = f"{task_text}_{deadline_str}"
                    blinking_tasks.add(task_id)
                    
                    # Blinking effect for overdue tasks
                    if blink_state:
                        todo_listbox.itemconfig(i, fg="red", bg="#ffe6e6")  # Red text with light red background
                    else:
                        todo_listbox.itemconfig(i, fg="white", bg="red")  # White text with red background
                    
                    # Play sound for overdue tasks (only once per task)
                    if task_id not in overdue_sound_played:
                        try:
                            # Try to find assets in the executable's directory or embedded location
                            if getattr(sys, 'frozen', False):
                                # Running as compiled executable
                                base_path = sys._MEIPASS
                            else:
                                # Running as script
                                base_path = os.getcwd()
                            
                            assets_folder = os.path.join(base_path, "assets")
                            sound_file = os.path.join(assets_folder, "overdue.mp3")
                            if os.path.exists(sound_file):
                                print(f"Playing overdue sound: {sound_file}")  # Debug print
                                
                                # Use threading to play sound in background
                                def play_sound_thread():
                                    try:
                                        # Method 1: Try using playsound in background
                                        playsound(sound_file, block=False)
                                        print("Sound played using playsound in background")
                                    except Exception as e:
                                        print(f"Playsound failed: {e}")
                                        try:
                                            # Method 2: Try using subprocess with start command
                                            full_path = os.path.abspath(sound_file)
                                            subprocess.Popen(['start', full_path], shell=True, 
                                                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                                            print("Sound played using 'start' command")
                                        except Exception as e:
                                            print(f"Start command failed: {e}")
                                            try:
                                                # Method 3: Fallback to system sound
                                                winsound.PlaySound("SystemExclamation", winsound.SND_ALIAS)
                                                print("Sound played using winsound")
                                            except Exception as e:
                                                print(f"Winsound failed: {e}")
                                                pass
                                
                                # Start sound in background thread
                                threading.Thread(target=play_sound_thread, daemon=True).start()
                            else:
                                print(f"Sound file not found: {sound_file}")
                                winsound.PlaySound("SystemExclamation", winsound.SND_ALIAS)
                        except Exception as e:
                            print(f"Sound playback error: {e}")
                            # Final fallback to system sound
                            try:
                                winsound.PlaySound("SystemExclamation", winsound.SND_ALIAS)
                            except:
                                pass  # Continue if sound fails
                        
                        # Mark this task as having played sound
                        overdue_sound_played.add(task_id)
                else:
                    # Still time left - remove from blinking if it was overdue before
                    task_id = f"{task_text}_{deadline_str}"
                    if task_id in blinking_tasks:
                        blinking_tasks.remove(task_id)
                    
                    days = time_left.days
                    hours = time_left.seconds // 3600
                    minutes = (time_left.seconds % 3600) // 60
                    
                    # Color coding based on urgency
                    if days == 0 and hours < 2:
                        color = "red"
                    elif days == 0 and hours < 6:
                        color = "orange"
                    elif days == 0:
                        color = "blue"
                    else:
                        color = "black"
                    
                    if days > 0:
                        time_display = f"⏰ {deadline_display} ({days} days left)"
                    elif hours > 0:
                        time_display = f"⏰ {deadline_display} ({hours} hours left)"
                    else:
                        time_display = f"⏰ {deadline_display} ({minutes} min left)"
                    
                    new_task = f"{task_text} {time_display}"
                    todo_listbox.delete(i)
                    todo_listbox.insert(i, new_task)
                    todo_listbox.itemconfig(i, fg=color, bg="#f8f9fa")  # Reset background
            except ValueError:
                pass  # Invalid date format, skip
    
    # Toggle blink state for next update
    blink_state = not blink_state
    
    # Schedule next update in 1 second for blinking effect and 30 seconds for timer updates
    root.after(1000, update_timers)

# ----------- MAIN FUNCTIONS -----------
def open_website(url):
    webbrowser.open_new_tab(url)

def on_enter(event):
    event.widget.config(fg="#007acc", font=("Segoe UI", 10, "bold"), cursor="hand2")
def on_leave(event):
    event.widget.config(fg="#333", font=("Segoe UI", 10), cursor="arrow")

def add_todo():
    task = todo_entry.get().strip()
    if task:
        todo_listbox.insert(tk.END, f"☐ {task}")
        todo_entry.delete(0, tk.END)
        save_todos(todo_listbox)
        # Auto-select the newly added task
        todo_listbox.selection_clear(0, tk.END)
        todo_listbox.selection_set(todo_listbox.size() - 1)
        todo_listbox.see(todo_listbox.size() - 1)
        # Highlight the new task
        todo_listbox.itemconfig(todo_listbox.size() - 1, bg="#e3f2fd")

def toggle_task(event=None):
    i = todo_listbox.curselection()
    if i:
        i = i[0]
        task = todo_listbox.get(i)
        
        # Extract the task text and timer if present
        if "⏰" in task:
            parts = task.split("⏰")
            task_text = parts[0]
            timer_part = "⏰" + parts[1] if len(parts) > 1 else ""
        else:
            task_text = task
            timer_part = ""
        
        # Toggle checkbox
        if task_text.startswith("☐"):
            new_task = f"✅ {task_text[2:].strip()}{timer_part}"
            todo_listbox.delete(i)
            todo_listbox.insert(i, new_task)
            todo_listbox.itemconfig(i, fg="green", bg="#e8f5e8")
        else:
            new_task = f"☐ {task_text[2:].strip()}{timer_part}"
            todo_listbox.delete(i)
            todo_listbox.insert(i, new_task)
            todo_listbox.itemconfig(i, fg="black", bg="white")
        
        save_todos(todo_listbox)

def delete_task():
    selected = todo_listbox.curselection()
    if selected:
        todo_listbox.delete(selected[0])
        save_todos(todo_listbox)
    else:
        messagebox.showinfo("No Selection", "Please select a task to delete.")

def on_todo_select(event):
    """Handle task selection with visual feedback"""
    selection = todo_listbox.curselection()
    if selection:
        # Reset all items to default background
        for i in range(todo_listbox.size()):
            todo_listbox.itemconfig(i, bg="white")
        
        # Highlight selected item
        selected_index = selection[0]
        todo_listbox.itemconfig(selected_index, bg="#e3f2fd")

def on_todo_key(event):
    """Handle keyboard shortcuts for todo list"""
    if event.keysym == 'Return':
        add_todo()
    elif event.keysym == 'Delete':
        delete_task()
    elif event.keysym == 'space':
        toggle_task()
    elif event.keysym == 'Up':
        current = todo_listbox.curselection()
        if current and current[0] > 0:
            todo_listbox.selection_clear(0, tk.END)
            todo_listbox.selection_set(current[0] - 1)
            todo_listbox.see(current[0] - 1)
            on_todo_select(None)  # Trigger selection highlight
    elif event.keysym == 'Down':
        current = todo_listbox.curselection()
        if current and current[0] < todo_listbox.size() - 1:
            todo_listbox.selection_clear(0, tk.END)
            todo_listbox.selection_set(current[0] + 1)
            todo_listbox.see(current[0] + 1)
            on_todo_select(None)  # Trigger selection highlight

def add_link_window():
    link_window = tk.Toplevel(root)
    link_window.title("Add New Link")
    link_window.geometry("500x250")
    
    # Set icon for link window
    set_window_icon(link_window)
    
    name_entry = tk.Entry(link_window, font=("Segoe UI", 13))
    name_entry.pack(pady=5)
    add_placeholder(name_entry, "Enter link name...")
    
    url_entry = tk.Entry(link_window, font=("Segoe UI", 13))
    url_entry.pack(pady=5)
    add_placeholder(url_entry, "Enter URL...")
    
    def save():
        name = name_entry.get().strip()
        url = url_entry.get().strip()
        if name and url and name != "Enter link name..." and url != "Enter URL...":
            save_link(name, url)
            refresh_links()
            link_window.destroy()
    
    tk.Button(link_window, text="Save", command=save,
             bg="#28a745", fg="white",
             font=("Segoe UI", 10, "bold")).pack(pady=10)

def refresh_links():
    links_listbox.delete(0, tk.END)
    links = load_links()
    for link_id, name, url, order_index in links:
        links_listbox.insert(tk.END, f"🌐 {name}")
        
        # Bind click event to open URL
        def open_link(event, url=url):
            open_website(url)
        
        # Bind double-click to open link
        links_listbox.bind("<Double-Button-1>", lambda e, url=url: open_website(url))
        
        # Add right-click menu for delete
        def create_popup(link_id):
            popup = tk.Menu(links_listbox, tearoff=0)
            popup.add_command(label="Delete", command=lambda: delete_and_refresh_link(link_id))
            return popup
        
        popup = create_popup(link_id)
        links_listbox.bind("<Button-3>", lambda e, p=popup: p.tk_popup(e.x_root, e.y_root))

def delete_and_refresh_link(link_id):
    if messagebox.askyesno("Confirm Delete", "Are you sure you want to delete this link?"):
        delete_link(link_id)
        refresh_links()

def add_note_window():
    note_window = tk.Toplevel(root)
    note_window.title("Add New Note")
    note_window.geometry("600x500")  # Bigger window
    
    # Set icon for note window
    set_window_icon(note_window)
    
    container = tk.Frame(note_window, bg="white", padx=20, pady=15)
    container.pack(fill="both", expand=True)
    
    # Title entry with placeholder
    title_entry = tk.Entry(container, font=("Segoe UI", 11), 
                          relief="flat", bg="#f8f9fa")
    title_entry.pack(fill="x", ipady=8, pady=(0,15))
    add_placeholder(title_entry, "Enter note title...")
    
    # Content text area with placeholder
    content_text = tk.Text(container, height=15, font=("Segoe UI", 11),
                          wrap=tk.WORD, relief="flat", bg="#f8f9fa")
    content_text.pack(fill="both", expand=True, pady=(0,15))
    content_text.insert("1.0", "Enter your note content...")
    content_text.bind("<FocusIn>", lambda e: content_text.delete("1.0", tk.END) 
                     if content_text.get("1.0", tk.END).strip() == "Enter your note content..." else None)
    
    # Button frame
    btn_frame = tk.Frame(container, bg="white")
    btn_frame.pack(fill="x", pady=(0,10))
    
    def save():
        title = title_entry.get().strip()
        content = content_text.get("1.0", tk.END).strip()
        if title and content:
            save_note(title, content)
            refresh_notes()
            note_window.destroy()
    
    save_btn = tk.Button(btn_frame, text="Save Note",
                        command=save, bg="#28a745", fg="white",
                        font=("Segoe UI", 10, "bold"),
                        padx=20, pady=8)
    save_btn.pack(side="right")

def refresh_notes():
    notes_listbox.delete(0, tk.END)
    notes = get_all_notes()
    for note in notes:
        note_frame = tk.Frame(notes_listbox, bg="#f8f9fa")
        notes_listbox.insert(tk.END, f"{note[0]} - {note[1]}")
        
        # Add right-click menu for delete
        def create_popup(note_id):
            popup = tk.Menu(notes_listbox, tearoff=0)
            popup.add_command(label="Delete", command=lambda: delete_and_refresh_note(note_id))
            return popup
        
        popup = create_popup(note[0])
        notes_listbox.bind("<Button-3>", lambda e, p=popup: p.tk_popup(e.x_root, e.y_root))

def delete_and_refresh_note(note_id):
    if messagebox.askyesno("Confirm Delete", "Are you sure you want to delete this note?"):
        delete_note(note_id)
        refresh_notes()

def view_note(event):
    selection = notes_listbox.curselection()
    if selection:
        note_id = int(notes_listbox.get(selection[0]).split(" - ")[0])
        notes = get_all_notes()
        for note in notes:
            if note[0] == note_id:
                view_window = tk.Toplevel(root)
                view_window.title(note[1])
                view_window.geometry("600x400")  # Bigger window
                
                # Set icon for view window
                set_window_icon(view_window)
                
                # Add a container frame
                container = tk.Frame(view_window, bg="white", padx=20, pady=10)
                container.pack(fill="both", expand=True)
                
                # Title display
                title_label = tk.Label(container, text=note[1], 
                                     font=("Segoe UI", 16, "bold"),
                                     bg="white", fg="#333")
                title_label.pack(anchor="w", pady=(0, 10))
                
                # Content display
                text_frame = tk.Frame(container, bg="white")
                text_frame.pack(fill="both", expand=True)
                
                text = tk.Text(text_frame, wrap=tk.WORD, font=("Segoe UI", 11),
                              padx=10, pady=10, relief="flat", bg="#f8f9fa")
                text.pack(fill="both", expand=True)
                text.insert("1.0", note[2])
                text.config(state="disabled")
                
                # Button frame
                btn_frame = tk.Frame(container, bg="white")
                btn_frame.pack(fill="x", pady=(10, 0))
                
                def delete_current_note():
                    if messagebox.askyesno("Confirm Delete", 
                                         "Are you sure you want to delete this note?"):
                        delete_note(note_id)
                        refresh_notes()
                        view_window.destroy()
                
                delete_btn = tk.Button(btn_frame, text="Delete Note", 
                                     command=delete_current_note,
                                     bg="#dc3545", fg="white",
                                     font=("Segoe UI", 10),
                                     padx=15, pady=5)
                delete_btn.pack(side="right")
                break

# ----------- GUI SETUP -----------
init_db()
root = tk.Tk()
root.title("🧠 Advanced Daily Dashboard")
root.geometry("1024x768")  # Bigger initial size
root.minsize(1300, 980)    # Minimum window size
root.config(bg="#eaf4fc")

# Set application icon
try:
    icon_path = os.path.join(os.getcwd(), "icon.ico")
    if os.path.exists(icon_path):
        root.iconbitmap(icon_path)
        print(f"Application icon loaded: {icon_path}")
    else:
        print(f"Icon file not found: {icon_path}")
except Exception as e:
    print(f"Error loading icon: {e}")

# Create outer container
outer_frame = tk.Frame(root, bg="#eaf4fc")
outer_frame.pack(fill="both", expand=True)

# Create scrollable canvas
main_canvas = tk.Canvas(outer_frame, bg="#eaf4fc")
scrollbar = tk.Scrollbar(outer_frame, orient="vertical", command=main_canvas.yview)
scrollable_frame = tk.Frame(main_canvas, bg="#eaf4fc")

# Configure scrolling
scrollable_frame.bind(
    "<Configure>",
    lambda e: main_canvas.configure(scrollregion=main_canvas.bbox("all"))
)
main_canvas.create_window((0, 0), window=scrollable_frame, anchor="nw", width=main_canvas.winfo_width())

# Make canvas expand with window
def on_canvas_configure(e):
    main_canvas.itemconfig(canvas_window, width=e.width)
main_canvas.bind('<Configure>', on_canvas_configure)
canvas_window = main_canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")

# Pack scrollbar and canvas
scrollbar.pack(side="right", fill="y")
main_canvas.pack(side="left", fill="both", expand=True)

# Title
title_frame = tk.Frame(scrollable_frame, bg="#eaf4fc")
title_frame.pack(fill="x", padx=20, pady=15)

# Main title
tk.Label(title_frame, text="🌅 My Daily Dashboard", 
         font=("Segoe UI", 25, "bold"), bg="#eaf4fc", fg="#222").pack()

# Date and Time frame
datetime_frame = tk.Frame(title_frame, bg="#eaf4fc")
datetime_frame.pack(pady=(2, 0))

# Date label with larger font
date_label = tk.Label(datetime_frame, text="", font=("Segoe UI", 16), 
                      bg="#eaf4fc", fg="#555")
date_label.pack()

# Time label with larger font and special styling
time_label = tk.Label(datetime_frame, text="", font=("Segoe UI", 20, "bold"), 
                      bg="#eaf4fc", fg="#007bff")
time_label.pack()

# AM/PM label
ampm_label = tk.Label(datetime_frame, text="", font=("Segoe UI", 14, "bold"), 
                      bg="#eaf4fc", fg="#28a745")
ampm_label.pack(pady=(0, 5))

def update_datetime():
    # Get Bangladesh time
    bd_timezone = pytz.timezone('Asia/Dhaka')
    bd_time = datetime.now(bd_timezone)
    
    # Update date in format: "Tuesday, July 29, 2025"
    date_label.config(text=bd_time.strftime("%A, %B %d, %Y"))
    
    # Update time in 12-hour format: "11:30:45"
    time_label.config(text=bd_time.strftime("%I:%M:%S %p"))
    
    
    # Schedule the next update in 1000ms (1 second)
    root.after(1000, update_datetime)

# Main content frame
main_frame = tk.Frame(scrollable_frame, bg="#eaf4fc")
main_frame.pack(fill="both", expand=True, padx=20)

left_frame = tk.Frame(main_frame, bg="#ffffff", bd=1, relief="groove")
left_frame.pack(side="left", fill="both", expand=True, padx=10, pady=10)

right_frame = tk.Frame(main_frame, bg="#ffffff", bd=1, relief="groove")
right_frame.pack(side="right", fill="both", expand=True, padx=10, pady=10)

# Website Links
links_title_frame = tk.Frame(left_frame, bg="white", padx=15, pady=10)
links_title_frame.pack(fill="x")
tk.Label(links_title_frame, text="🔗 Useful Links", bg="white", fg="#111", 
         font=("Segoe UI", 14, "bold")).pack(side="left")
tk.Button(links_title_frame, text="➕ Add New Link", command=add_link_window,
          bg="#007bff", fg="white", font=("Segoe UI", 10),
          padx=15, pady=5).pack(side="right")

# Create links listbox for reordering
links_listbox = create_scrolled_listbox(left_frame, 
                          font=("Segoe UI", 11),
                          height=8, selectbackground="#007bff",
                          selectforeground="white", relief="flat",
                          bg="#f8f9fa",
                          padx=15, pady=(0,15))

# Add reorder buttons for links
links_button_frame = tk.Frame(left_frame, bg="white")
links_button_frame.pack(pady=(0, 10))

tk.Button(links_button_frame, text="⬆️ Move Up", 
          command=lambda: move_up(links_listbox, lambda x: None, update_link_order, []),
          font=("Segoe UI", 10), bg="#6c757d", fg="white",
          padx=10, pady=5).pack(side="left", padx=5)
tk.Button(links_button_frame, text="⬇️ Move Down", 
          command=lambda: move_down(links_listbox, lambda x: None, update_link_order, []),
          font=("Segoe UI", 10), bg="#6c757d", fg="white",
          padx=10, pady=5).pack(side="left", padx=5)

links_frame = tk.Frame(left_frame, bg="white")
links_frame.pack(fill="both", expand=True, padx=15, pady=(0, 10))

# To-Do List
todo_title_frame = tk.Frame(right_frame, bg="white", padx=15, pady=10)
todo_title_frame.pack(fill="x")
tk.Label(todo_title_frame, text="✅ To-Do List", bg="white", fg="#111", 
         font=("Segoe UI", 14, "bold")).pack(side="left")

# Add timer button with better feedback
def add_timer_with_check():
    selection = todo_listbox.curselection()
    if not selection:
        messagebox.showwarning("No Task Selected", 
                             "Please select a task first before adding a timer.\n\n"
                             "Click on any task in the list to select it.")
        return
    
    # Highlight the selected task to make it clear
    selected_index = selection[0]
    todo_listbox.selection_clear(0, tk.END)
    todo_listbox.selection_set(selected_index)
    on_todo_select(None)
    todo_listbox.see(selected_index)
    
    add_timer_window()

# Add timer button
tk.Button(todo_title_frame, text="⏰ Add Timer", command=add_timer_with_check,
          bg="#ffc107", fg="black", font=("Segoe UI", 10),
          padx=15, pady=5).pack(side="right")

todo_listbox = create_scrolled_listbox(right_frame, 
                         font=("Segoe UI", 11), 
                         height=12, selectbackground="#007bff",
                         selectforeground="white", relief="flat",
                         bg="#f8f9fa",
                         padx=10, pady=5)
todo_listbox.bind("<Double-Button-1>", toggle_task)
todo_listbox.bind("<KeyPress-Return>", on_todo_key)
todo_listbox.bind("<KeyPress-Delete>", on_todo_key)
todo_listbox.bind("<KeyPress-space>", on_todo_key)
todo_listbox.bind("<KeyPress-Up>", on_todo_key)
todo_listbox.bind("<KeyPress-Down>", on_todo_key)
todo_listbox.bind("<Button-1>", on_todo_select) # Bind selection highlight

# Entry & Buttons
todo_entry = tk.Entry(right_frame, font=("Segoe UI", 12), 
                     relief="flat", bg="#f8f9fa")
todo_entry.pack(padx=10, pady=(10, 10), fill="x", ipady=8)
add_placeholder(todo_entry, "Add a new task...")

# Bind Enter key to add task
todo_entry.bind("<Return>", lambda e: add_todo())

button_frame = tk.Frame(right_frame, bg="white")
button_frame.pack(pady=(0, 10))

tk.Button(button_frame, text="➕ Add Task", command=add_todo,
          font=("Segoe UI", 10, "bold"), bg="#28a745", fg="white",
          padx=15, pady=5).pack(side="left", padx=5)
tk.Button(button_frame, text="🗑️ Delete Task", command=delete_task,
          font=("Segoe UI", 10), bg="#dc3545", fg="white",
          padx=15, pady=5).pack(side="left", padx=5)

# Add reorder buttons for todo list
tk.Button(button_frame, text="⬆️ Move Up", 
          command=lambda: move_up(todo_listbox, save_todos, lambda x, y: None, []),
          font=("Segoe UI", 10), bg="#6c757d", fg="white",
          padx=10, pady=5).pack(side="left", padx=5)
tk.Button(button_frame, text="⬇️ Move Down", 
          command=lambda: move_down(todo_listbox, save_todos, lambda x, y: None, []),
          font=("Segoe UI", 10), bg="#6c757d", fg="white",
          padx=10, pady=5).pack(side="left", padx=5)

# Add keyboard shortcuts info
shortcuts_frame = tk.Frame(right_frame, bg="white")
shortcuts_frame.pack(fill="x", padx=10, pady=(0, 5))
tk.Label(shortcuts_frame, text="💡 Shortcuts: Enter=Add, Space=Toggle, Delete=Remove, ↑↓=Navigate", 
         font=("Segoe UI", 8), bg="white", fg="#666").pack(anchor="w")

# Notes Frame
notes_frame = tk.Frame(scrollable_frame, bg="#ffffff", bd=1, relief="groove")
notes_frame.pack(fill="both", expand=True, padx=20, pady=(20, 20))

title_frame = tk.Frame(notes_frame, bg="white", padx=15, pady=10)
title_frame.pack(fill="x")

tk.Label(title_frame, text="📝 Notes", bg="white", fg="#111", 
         font=("Segoe UI", 14, "bold")).pack(side="left")
tk.Button(title_frame, text="➕ Add New Note", command=add_note_window,
          bg="#007bff", fg="white", font=("Segoe UI", 10),
          padx=15, pady=5).pack(side="right")

notes_listbox = create_scrolled_listbox(notes_frame, 
                          font=("Segoe UI", 11),
                          height=8, selectbackground="#007bff",
                          selectforeground="white", relief="flat",
                          bg="#f8f9fa",
                          padx=15, pady=(0,15))
notes_listbox.bind("<Double-Button-1>", view_note)

# Add reorder buttons for notes
notes_button_frame = tk.Frame(notes_frame, bg="white")
notes_button_frame.pack(pady=(0, 10))

tk.Button(notes_button_frame, text="⬆️ Move Up", 
          command=lambda: move_up(notes_listbox, lambda x: None, update_note_order, []),
          font=("Segoe UI", 10), bg="#6c757d", fg="white",
          padx=10, pady=5).pack(side="left", padx=5)
tk.Button(notes_button_frame, text="⬇️ Move Down", 
          command=lambda: move_down(notes_listbox, lambda x: None, update_note_order, []),
          font=("Segoe UI", 10), bg="#6c757d", fg="white",
          padx=10, pady=5).pack(side="left", padx=5)

# Start timer updates immediately and then every 30 seconds
def start_timer_updates():
    update_timers()  # Run immediately
    # The update_timers function now schedules itself every 1 second for blinking

# Load saved todos
for task, done, deadline, created_at in load_todos():
    checkbox = "✅" if done else "☐"
    if deadline:
        todo_listbox.insert(tk.END, f"{checkbox} {task} ⏰ {deadline}")
    else:
        todo_listbox.insert(tk.END, f"{checkbox} {task}")
    
    # Set visual feedback for completed tasks
    if done:
        todo_listbox.itemconfig(todo_listbox.size() - 1, fg="green", bg="#e8f5e8")

# Run initial timer update to format existing deadlines
root.after(1000, update_timers)

# Auto-select first task if available
if todo_listbox.size() > 0:
    todo_listbox.selection_set(0)
    on_todo_select(None)

refresh_links()
refresh_notes()

# Start timer updates
start_timer_updates()

# Developer credit in footer
footer_frame = tk.Frame(scrollable_frame, bg="#eaf4fc")
footer_frame.pack(fill="x", pady=(0, 10))

credit_frame = tk.Frame(footer_frame, bg="#eaf4fc")
credit_frame.pack(expand=True)

credit_text = tk.Label(credit_frame, text="Develop by ", 
                      font=("Segoe UI", 10), bg="#eaf4fc", fg="#666")
credit_text.pack(side="left")

def open_profile(event):
    webbrowser.open_new_tab("https://github.com/needyamin")  # Replace with your actual profile URL

credit_link = tk.Label(credit_frame, text="Md. Yamin Hossain", 
                      font=("Segoe UI", 10, "bold"), bg="#eaf4fc", 
                      fg="#007bff", cursor="hand2")
credit_link.pack(side="left")
credit_link.bind("<Button-1>", open_profile)
credit_link.bind("<Enter>", lambda e: credit_link.config(fg="#0056b3"))
credit_link.bind("<Leave>", lambda e: credit_link.config(fg="#007bff"))

# Test sound function for debugging
def play_sound_background():
    """Test function to debug sound playback"""
    try:
        # Try to find assets in the executable's directory or embedded location
        if getattr(sys, 'frozen', False):
            # Running as compiled executable
            base_path = sys._MEIPASS
        else:
            # Running as script
            base_path = os.getcwd()
        
        assets_folder = os.path.join(base_path, "assets")
        sound_file = os.path.join(assets_folder, "overdue.mp3")
        if os.path.exists(sound_file):
            print(f"Testing sound playback: {sound_file}")  # Debug print
            full_path = os.path.abspath(sound_file)
            print(f"Full path: {full_path}")
            
            # Use threading to play sound in background
            def play_sound_thread():
                try:
                    # Method 1: Try using playsound in background
                    playsound(sound_file, block=False)
                    print("Test: Sound should have played using playsound in background")
                except Exception as e:
                    print(f"Test: Playsound failed: {e}")
                    try:
                        # Method 2: Try using subprocess with start command
                        subprocess.Popen(['start', full_path], shell=True, 
                                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                        print("Test: Sound should have played using 'start' command")
                    except Exception as e:
                        print(f"Test: Start command failed: {e}")
                        try:
                            # Method 3: Fallback to system sound
                            winsound.PlaySound("SystemExclamation", winsound.SND_ALIAS)
                            print("Test: Sound should have played using winsound")
                        except Exception as e:
                            print(f"Test: Winsound failed: {e}")
                            pass
            
            # Start sound in background thread
            threading.Thread(target=play_sound_thread, daemon=True).start()
        else:
            print(f"Test: Sound file not found: {sound_file}")
    except Exception as e:
        print(f"Test: Sound test error: {e}")

# Add a test button for sound (temporary, for debugging)
test_frame = tk.Frame(scrollable_frame, bg="#eaf4fc")
test_frame.pack(fill="x", pady=(0, 10))
tk.Button(test_frame, text="🔊 Test Sound", command=play_sound_background,
          bg="#ffc107", fg="black", font=("Segoe UI", 10),
          padx=15, pady=5).pack()

# Start the datetime update
update_datetime()

# Start GUI loop
root.mainloop()
