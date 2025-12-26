"""Task Management System for Jarvis."""

import json
import time
import uuid
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parents[1]
TASKS_PATH = ROOT / "data" / "tasks.json"


class TaskStatus(Enum):
    """Task status enum."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class TaskPriority(Enum):
    """Task priority enum."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


class Task:
    """Task data class."""
    
    def __init__(
        self,
        title: str,
        priority: TaskPriority = TaskPriority.MEDIUM,
        status: TaskStatus = TaskStatus.PENDING,
        task_id: str = None,
        created_at: float = None,
        completed_at: float = None,
        metadata: Dict[str, Any] = None
    ):
        self.id = task_id or str(uuid.uuid4())
        self.title = title
        self.priority = priority
        self.status = status
        self.created_at = created_at or time.time()
        self.completed_at = completed_at
        self.metadata = metadata or {}
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert task to dictionary."""
        return {
            "id": self.id,
            "title": self.title,
            "priority": self.priority.value,
            "status": self.status.value,
            "created_at": self.created_at,
            "completed_at": self.completed_at,
            "metadata": self.metadata
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Task":
        """Create task from dictionary."""
        return cls(
            title=data["title"],
            priority=TaskPriority(data["priority"]),
            status=TaskStatus(data["status"]),
            task_id=data["id"],
            created_at=data["created_at"],
            completed_at=data["completed_at"],
            metadata=data.get("metadata", {})
        )
    
    def complete(self):
        """Mark task as completed."""
        self.status = TaskStatus.COMPLETED
        self.completed_at = time.time()
    
    def start(self):
        """Mark task as in progress."""
        self.status = TaskStatus.IN_PROGRESS


class TaskManager:
    """Manages tasks for Jarvis."""
    
    def __init__(self):
        self.tasks: List[Task] = []
        self._load_tasks()
    
    def _load_tasks(self):
        """Load tasks from file."""
        if TASKS_PATH.exists():
            try:
                with open(TASKS_PATH, "r") as f:
                    data = json.load(f)
                    self.tasks = [Task.from_dict(task_data) for task_data in data]
            except Exception as e:
                print(f"Error loading tasks: {e}")
                self.tasks = []
        else:
            self.tasks = []
    
    def _save_tasks(self):
        """Save tasks to file."""
        TASKS_PATH.parent.mkdir(parents=True, exist_ok=True)
        try:
            with open(TASKS_PATH, "w") as f:
                json.dump([task.to_dict() for task in self.tasks], f, indent=2)
        except Exception as e:
            print(f"Error saving tasks: {e}")
    
    def add_task(
        self,
        title: str,
        priority: TaskPriority = TaskPriority.MEDIUM,
        metadata: Dict[str, Any] = None
    ) -> Task:
        """Add a new task."""
        task = Task(title=title, priority=priority, metadata=metadata or {})
        self.tasks.append(task)
        self._save_tasks()
        return task
    
    def get_next_task(self, status_filter: TaskStatus = TaskStatus.PENDING) -> Optional[Task]:
        """Get the next highest priority task."""
        # Filter tasks by status
        available_tasks = [t for t in self.tasks if t.status == status_filter]
        
        if not available_tasks:
            return None
        
        # Sort by priority (urgent > high > medium > low) and then by creation time
        priority_order = {
            TaskPriority.URGENT: 0,
            TaskPriority.HIGH: 1,
            TaskPriority.MEDIUM: 2,
            TaskPriority.LOW: 3
        }
        
        available_tasks.sort(key=lambda t: (priority_order[t.priority], t.created_at))
        return available_tasks[0]
    
    def complete_task(self, task_id: str) -> bool:
        """Complete a task by ID."""
        for task in self.tasks:
            if task.id == task_id:
                task.complete()
                self._save_tasks()
                return True
        return False
    
    def start_task(self, task_id: str) -> bool:
        """Start a task by ID."""
        for task in self.tasks:
            if task.id == task_id:
                task.start()
                self._save_tasks()
                return True
        return False
    
    def get_task(self, task_id: str) -> Optional[Task]:
        """Get task by ID."""
        for task in self.tasks:
            if task.id == task_id:
                return task
        return None
    
    def list_tasks(
        self,
        status: Optional[TaskStatus] = None,
        priority: Optional[TaskPriority] = None,
        limit: int = 50
    ) -> List[Task]:
        """List tasks with optional filters."""
        filtered_tasks = self.tasks
        
        if status:
            filtered_tasks = [t for t in filtered_tasks if t.status == status]
        
        if priority:
            filtered_tasks = [t for t in filtered_tasks if t.priority == priority]
        
        # Sort by creation time (newest first)
        filtered_tasks.sort(key=lambda t: t.created_at, reverse=True)
        
        return filtered_tasks[:limit]
    
    def get_stats(self) -> Dict[str, Any]:
        """Get task statistics."""
        stats = {
            "total": len(self.tasks),
            "pending": len([t for t in self.tasks if t.status == TaskStatus.PENDING]),
            "in_progress": len([t for t in self.tasks if t.status == TaskStatus.IN_PROGRESS]),
            "completed": len([t for t in self.tasks if t.status == TaskStatus.COMPLETED]),
            "cancelled": len([t for t in self.tasks if t.status == TaskStatus.CANCELLED]),
            "by_priority": {
                "urgent": len([t for t in self.tasks if t.priority == TaskPriority.URGENT]),
                "high": len([t for t in self.tasks if t.priority == TaskPriority.HIGH]),
                "medium": len([t for t in self.tasks if t.priority == TaskPriority.MEDIUM]),
                "low": len([t for t in self.tasks if t.priority == TaskPriority.LOW])
            }
        }
        return stats


# Global task manager instance
_task_manager: Optional[TaskManager] = None


def get_task_manager() -> TaskManager:
    """Get the global task manager instance."""
    global _task_manager
    if not _task_manager:
        _task_manager = TaskManager()
    return _task_manager
