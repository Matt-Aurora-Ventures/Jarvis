"""Desktop Task GUI for Jarvis using tkinter."""

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import sys
from pathlib import Path

# Add the project root to Python path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core import task_manager


class TaskGUI:
    """Simple desktop GUI for task management."""
    
    def __init__(self, root):
        self.root = root
        self.root.title("Jarvis Task Manager")
        self.root.geometry("800x600")
        
        self.tm = task_manager.get_task_manager()
        
        # Create main frames
        self.create_frames()
        self.create_widgets()
        self.refresh_task_list()
        
        # Auto-refresh every 5 seconds
        self.root.after(5000, self.auto_refresh)
    
    def create_frames(self):
        """Create the main frames."""
        # Top frame for controls
        self.control_frame = ttk.Frame(self.root, padding="10")
        self.control_frame.pack(fill=tk.X)
        
        # Task list frame
        self.list_frame = ttk.Frame(self.root, padding="10")
        self.list_frame.pack(fill=tk.BOTH, expand=True)
        
        # Bottom frame for status
        self.status_frame = ttk.Frame(self.root, padding="10")
        self.status_frame.pack(fill=tk.X)
    
    def create_widgets(self):
        """Create the GUI widgets."""
        # Control buttons
        ttk.Button(self.control_frame, text="Add Task", command=self.add_task_dialog).pack(side=tk.LEFT, padx=5)
        ttk.Button(self.control_frame, text="Start Task", command=self.start_selected_task).pack(side=tk.LEFT, padx=5)
        ttk.Button(self.control_frame, text="Complete Task", command=self.complete_selected_task).pack(side=tk.LEFT, padx=5)
        ttk.Button(self.control_frame, text="Refresh", command=self.refresh_task_list).pack(side=tk.LEFT, padx=5)
        ttk.Button(self.control_frame, text="Show Stats", command=self.show_stats).pack(side=tk.LEFT, padx=5)
        
        # Filter controls
        ttk.Label(self.control_frame, text="Filter:").pack(side=tk.LEFT, padx=(20, 5))
        
        self.status_filter = ttk.Combobox(self.control_frame, values=["All", "Pending", "In Progress", "Completed", "Cancelled"], width=12)
        self.status_filter.set("All")
        self.status_filter.pack(side=tk.LEFT, padx=5)
        self.status_filter.bind("<<ComboboxSelected>>", lambda e: self.refresh_task_list())
        
        self.priority_filter = ttk.Combobox(self.control_frame, values=["All", "Urgent", "High", "Medium", "Low"], width=12)
        self.priority_filter.set("All")
        self.priority_filter.pack(side=tk.LEFT, padx=5)
        self.priority_filter.bind("<<ComboboxSelected>>", lambda e: self.refresh_task_list())
        
        # Task list
        columns = ("ID", "Priority", "Status", "Title", "Created")
        self.task_tree = ttk.Treeview(self.list_frame, columns=columns, show="headings", height=20)
        
        # Configure columns
        self.task_tree.heading("ID", text="ID")
        self.task_tree.heading("Priority", text="Priority")
        self.task_tree.heading("Status", text="Status")
        self.task_tree.heading("Title", text="Title")
        self.task_tree.heading("Created", text="Created")
        
        self.task_tree.column("ID", width=80)
        self.task_tree.column("Priority", width=80)
        self.task_tree.column("Status", width=100)
        self.task_tree.column("Title", width=400)
        self.task_tree.column("Created", width=120)
        
        # Scrollbar
        scrollbar = ttk.Scrollbar(self.list_frame, orient=tk.VERTICAL, command=self.task_tree.yview)
        self.task_tree.configure(yscrollcommand=scrollbar.set)
        
        self.task_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Status bar
        self.status_label = ttk.Label(self.status_frame, text="Ready")
        self.status_label.pack(side=tk.LEFT)
    
    def add_task_dialog(self):
        """Show dialog to add a new task."""
        dialog = tk.Toplevel(self.root)
        dialog.title("Add Task")
        dialog.geometry("400x200")
        
        # Title
        ttk.Label(dialog, text="Task Title:").pack(pady=5)
        title_entry = ttk.Entry(dialog, width=50)
        title_entry.pack(pady=5)
        
        # Priority
        ttk.Label(dialog, text="Priority:").pack(pady=5)
        priority_var = tk.StringVar(value="medium")
        priority_combo = ttk.Combobox(dialog, textvariable=priority_var, values=["low", "medium", "high", "urgent"])
        priority_combo.pack(pady=5)
        
        def save_task():
            title = title_entry.get().strip()
            if not title:
                messagebox.showerror("Error", "Please enter a task title")
                return
            
            priority = task_manager.TaskPriority(priority_var.get())
            task = self.tm.add_task(title, priority)
            self.status_label.config(text=f"Added task: {task.title}")
            self.refresh_task_list()
            dialog.destroy()
        
        ttk.Button(dialog, text="Add Task", command=save_task).pack(pady=20)
        
        # Focus on title entry
        title_entry.focus()
        dialog.grab_set()
    
    def get_selected_task_id(self):
        """Get the selected task ID."""
        selection = self.task_tree.selection()
        if not selection:
            return None
        item = self.task_tree.item(selection[0])
        return item['values'][0]
    
    def start_selected_task(self):
        """Start the selected task."""
        task_id = self.get_selected_task_id()
        if not task_id:
            messagebox.showwarning("Warning", "Please select a task to start")
            return
        
        if self.tm.start_task(task_id):
            self.status_label.config(text=f"Started task: {task_id}")
            self.refresh_task_list()
        else:
            messagebox.showerror("Error", f"Task {task_id} not found")
    
    def complete_selected_task(self):
        """Complete the selected task."""
        task_id = self.get_selected_task_id()
        if not task_id:
            messagebox.showwarning("Warning", "Please select a task to complete")
            return
        
        if messagebox.askyesno("Confirm", f"Complete task {task_id}?"):
            if self.tm.complete_task(task_id):
                self.status_label.config(text=f"Completed task: {task_id}")
                self.refresh_task_list()
            else:
                messagebox.showerror("Error", f"Task {task_id} not found")
    
    def refresh_task_list(self):
        """Refresh the task list."""
        # Clear current items
        for item in self.task_tree.get_children():
            self.task_tree.delete(item)
        
        # Get filters
        status_filter = None
        priority_filter = None
        
        status_text = self.status_filter.get()
        if status_text != "All":
            status_filter = task_manager.TaskStatus(status_text.lower().replace(" ", "_"))
        
        priority_text = self.priority_filter.get()
        if priority_text != "All":
            priority_filter = task_manager.TaskPriority(priority_text.lower())
        
        # Get tasks
        tasks = self.tm.list_tasks(status=status_filter, priority=priority_filter, limit=100)
        
        # Add tasks to tree
        for task in tasks:
            created_str = task_manager.datetime.fromtimestamp(task.created_at).strftime("%Y-%m-%d %H:%M")
            self.task_tree.insert("", tk.END, values=(
                task.id[:8],
                task.priority.value.title(),
                task.status.value.replace("_", " ").title(),
                task.title,
                created_str
            ))
        
        self.status_label.config(text=f"Showing {len(tasks)} tasks")
    
    def show_stats(self):
        """Show task statistics."""
        stats = self.tm.get_stats()
        
        stats_text = f"""Task Statistics

Total Tasks: {stats['total']}
Pending: {stats['pending']}
In Progress: {stats['in_progress']}
Completed: {stats['completed']}
Cancelled: {stats['cancelled']}

By Priority:
Urgent: {stats['by_priority']['urgent']}
High: {stats['by_priority']['high']}
Medium: {stats['by_priority']['medium']}
Low: {stats['by_priority']['low']}
"""
        
        messagebox.showinfo("Task Statistics", stats_text)
    
    def auto_refresh(self):
        """Auto-refresh the task list."""
        self.refresh_task_list()
        self.root.after(5000, self.auto_refresh)


def main():
    """Main entry point for the GUI."""
    root = tk.Tk()
    app = TaskGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
