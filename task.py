import tkinter as tk
from tkinter import messagebox
import webbrowser, sqlite3, time
from datetime import datetime
import pytz

DB_NAME = "dashboard_data.db"

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
    c.execute('''CREATE TABLE IF NOT EXISTS todos (id INTEGER PRIMARY KEY, task TEXT, done INTEGER)''')
    c.execute('''CREATE TABLE IF NOT EXISTS notes 
                 (id INTEGER PRIMARY KEY,
                  title TEXT NOT NULL,
                  content TEXT NOT NULL,
                  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    c.execute('''CREATE TABLE IF NOT EXISTS links (id INTEGER PRIMARY KEY, name TEXT, url TEXT)''')
    conn.commit()
    conn.close()

def load_todos():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT task, done FROM todos")
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
        clean_task = task[2:].strip()
        c.execute("INSERT INTO todos (task, done) VALUES (?, ?)", (clean_task, done))
    conn.commit()
    conn.close()

def load_links():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT id, name, url FROM links")
    links = c.fetchall()
    conn.close()
    return links

def save_link(name, url):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("INSERT INTO links (name, url) VALUES (?, ?)", (name, url))
    conn.commit()
    conn.close()

def delete_link(link_id):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("DELETE FROM links WHERE id = ?", (link_id,))
    conn.commit()
    conn.close()

def save_note(title, content):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("INSERT INTO notes (title, content) VALUES (?, ?)", (title, content))
    conn.commit()
    conn.close()

def delete_note(note_id):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("DELETE FROM notes WHERE id = ?", (note_id,))
    conn.commit()
    conn.close()

def get_all_notes():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT id, title, content, created_at FROM notes ORDER BY created_at DESC")
    notes = c.fetchall()
    conn.close()
    return notes

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

def toggle_task(event=None):
    i = todo_listbox.curselection()
    if i:
        i = i[0]
        task = todo_listbox.get(i)
        if task.startswith("☐"):
            todo_listbox.delete(i)
            todo_listbox.insert(i, task.replace("☐", "✅", 1))
        else:
            todo_listbox.delete(i)
            todo_listbox.insert(i, task.replace("✅", "☐", 1))
        save_todos(todo_listbox)

def delete_task():
    selected = todo_listbox.curselection()
    if selected:
        todo_listbox.delete(selected[0])
        save_todos(todo_listbox)
    else:
        messagebox.showinfo("No Selection", "Please select a task to delete.")

def add_link_window():
    link_window = tk.Toplevel(root)
    link_window.title("Add New Link")
    link_window.geometry("500x250")
    
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
    for widget in links_frame.winfo_children():
        widget.destroy()
    
    links = load_links()
    for link_id, name, url in links:
        link_frame = tk.Frame(links_frame, bg="white")
        link_frame.pack(fill="x", padx=5, pady=2)
        
        link = tk.Label(link_frame, text="🌐 " + name, fg="#333", bg="white", font=("Segoe UI", 10))
        link.pack(side="left")
        link.bind("<Button-1>", lambda e, url=url: open_website(url))
        link.bind("<Enter>", on_enter)
        link.bind("<Leave>", on_leave)
        
        delete_btn = tk.Button(link_frame, text="🗑️", command=lambda lid=link_id: delete_and_refresh_link(lid))
        delete_btn.pack(side="right")

def delete_and_refresh_link(link_id):
    if messagebox.askyesno("Confirm Delete", "Are you sure you want to delete this link?"):
        delete_link(link_id)
        refresh_links()

def add_note_window():
    note_window = tk.Toplevel(root)
    note_window.title("Add New Note")
    note_window.geometry("600x500")  # Bigger window
    
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
links_frame = tk.Frame(left_frame, bg="white")
links_frame.pack(fill="both", expand=True, padx=15, pady=(0, 10))

# To-Do List
todo_title_frame = tk.Frame(right_frame, bg="white", padx=15, pady=10)
todo_title_frame.pack(fill="x")
tk.Label(todo_title_frame, text="✅ To-Do List", bg="white", fg="#111", 
         font=("Segoe UI", 14, "bold")).pack(side="left")
todo_listbox = create_scrolled_listbox(right_frame, 
                         font=("Segoe UI", 11), 
                         height=12, selectbackground="#007bff",
                         selectforeground="white", relief="flat",
                         bg="#f8f9fa",
                         padx=10, pady=5)
todo_listbox.bind("<Double-Button-1>", toggle_task)

# Entry & Buttons
todo_entry = tk.Entry(right_frame, font=("Segoe UI", 12), 
                     relief="flat", bg="#f8f9fa")
todo_entry.pack(padx=10, pady=(10, 10), fill="x", ipady=8)
add_placeholder(todo_entry, "Add a new task...")

button_frame = tk.Frame(right_frame, bg="white")
button_frame.pack(pady=(0, 10))

tk.Button(button_frame, text="➕ Add Task", command=add_todo,
          font=("Segoe UI", 10, "bold"), bg="#28a745", fg="white",
          padx=15, pady=5).pack(side="left", padx=5)
tk.Button(button_frame, text="🗑️ Delete Task", command=delete_task,
          font=("Segoe UI", 10), bg="#dc3545", fg="white",
          padx=15, pady=5).pack(side="left", padx=5)

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

# Load saved todos
for task, done in load_todos():
    checkbox = "✅" if done else "☐"
    todo_listbox.insert(tk.END, f"{checkbox} {task}")

refresh_links()
refresh_notes()

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

# Start the datetime update
update_datetime()

# Start GUI loop
root.mainloop()
