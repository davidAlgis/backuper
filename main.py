import os
import shutil
import threading
import time
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path
import json
import sys
from datetime import datetime
from pystray import Icon, MenuItem, Menu
from PIL import Image, ImageDraw, ImageFont

def get_base_directory():
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    else:
        # Running normally as a script
        current_directory = os.path.abspath(os.path.dirname(__file__))
        return current_directory  # Use the current directory instead of the parent one


CONFIG_FILE = os.path.join(get_base_directory(), "config.json")

def is_backup_due(last_backup_date):
    if last_backup_date:
        last_backup = datetime.strptime(last_backup_date, "%Y-%m-%d %H:%M:%S")
        delta = datetime.now() - last_backup
        return delta.days > 3
    return False

def show_backup_prompt(root, tree, last_backup_date, progress_text, progress_bar, progress_label):  # Add progress_text as an argument
    if is_backup_due(last_backup_date):
        response = messagebox.askyesno("Backup Reminder", "It's been more than 3 days since your last backup. Would you like to perform a backup now?")
        if response:  # If user clicks "Yes"
            # Start the backup process
            start_backup(
                [(tree.item(item)["values"][0], tree.item(item)["values"][1]) for item in tree.get_children()],
                progress_text,
                progress_bar,
                progress_label
            )

            root.deiconify()  # Make sure the GUI window is visible
        else:  # If user clicks "No"
            # Save the response to the config file to check the next day
            save_config([(tree.item(item)["values"][0], tree.item(item)["values"][1]) for item in tree.get_children()], last_backup_date)



def should_copy(src_file, dest_file):
    if not dest_file.exists():
        return True
    return src_file.stat().st_mtime > dest_file.stat().st_mtime

def calculate_total_files(pairs):
    total_files = 0
    for input_folder, _ in pairs:
        for _, _, files in os.walk(input_folder):
            total_files += len(files)
    return total_files

def backup_files(pairs, progress_callback, update_progress):
    total_files = calculate_total_files(pairs)
    processed_files = 0
    start_time = time.time()

    for input_folder, backup_folder in pairs:
        input_folder = Path(input_folder).resolve()
        backup_folder = Path(backup_folder).resolve()

        for root, _, files in os.walk(input_folder):
            for file in files:
                src_file = Path(root) / file
                relative_path = src_file.relative_to(input_folder)
                dest_file = backup_folder / relative_path

                dest_file.parent.mkdir(parents=True, exist_ok=True)
                if should_copy(src_file, dest_file):
                    shutil.copy2(src_file, dest_file)
                    progress_callback(f"Copied: {src_file} -> {dest_file}")

                processed_files += 1
                elapsed_time = time.time() - start_time
                time_per_file = elapsed_time / processed_files
                estimated_time = (total_files - processed_files) * time_per_file
                update_progress(processed_files, total_files, estimated_time)

    # After backup is finished, update the last backup date
    last_backup_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    save_config(pairs, last_backup_date)

def start_backup(pairs, progress_text, progress_bar, progress_label):
    def update_progress(processed, total, estimated_time):
        progress_bar["value"] = (processed / total) * 100
        progress_label.config(text=f"Progress: {processed}/{total} files | Estimated time left: {estimated_time:.1f}s")

    def run_backup():
        progress_text.set("Starting backup...")
        try:
            backup_files(pairs, lambda msg: progress_text.set(msg), update_progress)
            progress_text.set("Backup completed successfully!")
        except Exception as e:
            progress_text.set(f"Error: {str(e)}")

    threading.Thread(target=run_backup, daemon=True).start()

def add_folder_pair(tree, input_var, backup_var):
    input_folder = input_var.get()
    backup_folder = backup_var.get()

    if not input_folder or not backup_folder:
        messagebox.showerror("Error", "Both input and backup folders must be specified.")
        return

    tree.insert("", "end", values=(input_folder, backup_folder))
    input_var.set("")
    backup_var.set("")

def remove_selected_pair(tree):
    selected_item = tree.selection()
    if not selected_item:
        messagebox.showwarning("Warning", "No item selected to remove.")
        return

    for item in selected_item:
        tree.delete(item)

def browse_folder(entry_var):
    folder = filedialog.askdirectory()
    if folder:
        entry_var.set(folder)

def save_config(pairs, last_backup_date):
    """
    Save the current input and backup folder pairs to a JSON file, along with the last backup date.
    """
    config_data = {
        "pairs": [(input_folder, backup_folder) for input_folder, backup_folder in pairs],
        "last_backup_date": last_backup_date
    }
    with open(CONFIG_FILE, "w") as f:
        json.dump(config_data, f, indent=4)

def load_config(tree, backup_date_only = False):
    if not os.path.exists(CONFIG_FILE):
        return None
    with open(CONFIG_FILE, "r") as f:
        try:
            config_data = json.load(f)
            pairs = config_data.get("pairs", [])
            last_backup_date = config_data.get("last_backup_date", None)
            if backup_date_only == False:
                # Insert pairs into the tree view
                for input_folder, backup_folder in pairs:
                    tree.insert("", "end", values=(input_folder, backup_folder))

            if last_backup_date:
                # Optionally display last backup date
                print(f"Last backup was on: {last_backup_date}")

            return last_backup_date
        except json.JSONDecodeError:
            messagebox.showwarning("Warning", "Could not load configuration file. The format may be incorrect.")
            return None

def create_tray_icon(root, tree, progress_text, progress_bar, progress_label):
    """
    Create a system tray icon and menu with options to minimize, restore, and quit.
    """
    def restore_window(icon, item):
        icon.stop()  # Stop the tray icon
        root.deiconify()  # Restore the window

    # Load the icon image from the file
    icon_image_path = os.path.join(get_base_directory(), "backuper-icon.ico")  # Assuming the icon is in the same directory
    icon_image = Image.open(icon_image_path)

    # Define the menu for the tray icon
    tray_menu = Menu(
        MenuItem('Open', restore_window),
        MenuItem('Quit', lambda icon, item: icon.stop())  # Added Quit option to stop the tray icon
    )

    icon = Icon("BackupApp", icon_image, menu=tray_menu)

    def check_backup(progress_text, progress_bar, progress_label):
        print("check_backup")
        last_backup_date = load_config(tree, True)
        if last_backup_date:
            show_backup_prompt(root, tree, last_backup_date, progress_text, progress_bar, progress_label)

        # Check every hour
        root.after(3600000, check_backup, progress_text, progress_bar, progress_label)  # Pass the arguments explicitly

    def start_tray_icon():
        icon.run()  # Run the tray icon in the tray

    # Start the tray icon in a separate thread
    tray_thread = threading.Thread(target=start_tray_icon, daemon=True)
    tray_thread.start()

    check_backup(progress_text, progress_bar, progress_label)  # Start checking backups immediately

    return icon

def on_close(root, tray_icon, tree):
    """
    This function is called when the user tries to close the window.
    It will ask if they want to minimize the application instead of quitting it.
    """
    response = messagebox.askyesnocancel("Close Application", "Do you want to minimize the application instead of closing it?")
    if response is None:
        return  # If they pressed Cancel, do nothing
    elif response:  # Yes (Minimize the application)
        root.withdraw()  # Hide the window
        tray_icon.visible = True  # Show tray icon
    else:  # No (Completely close the application)
        root.quit()  # Close the application

def create_gui():
    root = tk.Tk()
    root.title("Backuper")
    root.geometry("800x500")

    icon_image_path = os.path.join(get_base_directory(), "backuper-icon.ico")  # Path to your icon file
    root.iconbitmap(icon_image_path)  # Set the window icon

    # Input folder entry
    input_var = tk.StringVar()
    tk.Label(root, text="Input Folder:").grid(row=0, column=0, sticky="w", padx=5, pady=5)
    input_entry = ttk.Entry(root, textvariable=input_var, width=50)
    input_entry.grid(row=0, column=1, padx=5, pady=5)
    ttk.Button(root, text="Browse", command=lambda: browse_folder(input_var)).grid(row=0, column=2, padx=5, pady=5)

    # Backup folder entry
    backup_var = tk.StringVar()
    tk.Label(root, text="Backup Folder:").grid(row=1, column=0, sticky="w", padx=5, pady=5)
    backup_entry = ttk.Entry(root, textvariable=backup_var, width=50)
    backup_entry.grid(row=1, column=1, padx=5, pady=5)
    ttk.Button(root, text="Browse", command=lambda: browse_folder(backup_var)).grid(row=1, column=2, padx=5, pady=5)

    # Add folder pair button
    tree = ttk.Treeview(root, columns=("Input Folder", "Backup Folder"), show="headings", height=8)
    tree.heading("Input Folder", text="Input Folder")
    tree.heading("Backup Folder", text="Backup Folder")
    tree.grid(row=2, column=0, columnspan=3, padx=5, pady=5, sticky="nsew")

    # Buttons for Add and Remove
    ttk.Button(root, text="Add Pair", command=lambda: add_folder_pair(tree, input_var, backup_var)).grid(row=3, column=0, padx=5, pady=5)
    ttk.Button(root, text="Remove Selected", command=lambda: remove_selected_pair(tree)).grid(row=3, column=1, padx=5, pady=5)

    # Backup button and progress text
    progress_text = tk.StringVar()
    ttk.Label(root, textvariable=progress_text, foreground="blue").grid(row=4, column=0, columnspan=3, pady=10)
    ttk.Button(root, text="Start Backup", command=lambda: start_backup(
        [(tree.item(item)["values"][0], tree.item(item)["values"][1]) for item in tree.get_children()],
        progress_text,
        progress_bar,
        progress_label
    )).grid(row=5, column=0, columnspan=3, pady=10)

    # Progress bar and progress label
    progress_bar = ttk.Progressbar(root, orient="horizontal", length=400, mode="determinate")
    progress_bar.grid(row=6, column=0, columnspan=3, pady=10)
    progress_label = ttk.Label(root, text="Progress: 0/0 files")
    progress_label.grid(row=7, column=0, columnspan=3)

    # Configure grid weights
    root.grid_rowconfigure(2, weight=1)
    root.grid_columnconfigure(1, weight=1)

    # Load configuration on startup
    load_config(tree)

    # Create the tray icon and hide it initially
    tray_icon = create_tray_icon(root, tree, progress_text, progress_bar, progress_label)

    # Handle window close
    root.protocol("WM_DELETE_WINDOW", lambda: on_close(root, tray_icon, tree))

    root.mainloop()


if __name__ == "__main__":
    create_gui()