"""
Window Interaction Task for Autonomous Improver

Handles tasks related to interacting with browser windows and elements.
"""

from typing import Dict, Any, List, Optional
import logging
import time
from dataclasses import dataclass
from enum import Enum, auto

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TaskStatus(Enum):
    PENDING = auto()
    IN_PROGRESS = auto()
    COMPLETED = auto()
    FAILED = auto()
    RETRYING = auto()

@dataclass
class WindowInteractionTask:
    """Represents a window interaction task."""
    task_id: str
    task_type: str
    parameters: Dict[str, Any]
    status: TaskStatus = TaskStatus.PENDING
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 3
    created_at: float = None
    updated_at: float = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = time.time()
        if self.updated_at is None:
            self.updated_at = self.created_at
    
    def update_status(self, status: TaskStatus, result: Dict[str, Any] = None, error: str = None):
        """Update the task status and related information."""
        self.status = status
        self.updated_at = time.time()
        
        if result is not None:
            self.result = result
        if error is not None:
            self.error = error
            logger.error(f"Task {self.task_id} failed: {error}")
        
        logger.info(f"Task {self.task_id} status updated to {status.name}")
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert the task to a dictionary."""
        return {
            "task_id": self.task_id,
            "task_type": self.task_type,
            "parameters": self.parameters,
            "status": self.status.name,
            "result": self.result,
            "error": self.error,
            "retry_count": self.retry_count,
            "max_retries": self.max_retries,
            "created_at": self.created_at,
            "updated_at": self.updated_at
        }

class WindowInteractionTaskHandler:
    """Handles window interaction tasks for the autonomous improver."""
    
    def __init__(self, browser_automation):
        self.browser_automation = browser_automation
        self.tasks: Dict[str, WindowInteractionTask] = {}
    
    def create_task(self, task_type: str, parameters: Dict[str, Any]) -> WindowInteractionTask:
        """Create a new window interaction task."""
        task_id = f"win_task_{int(time.time() * 1000)}"
        task = WindowInteractionTask(
            task_id=task_id,
            task_type=task_type,
            parameters=parameters
        )
        self.tasks[task_id] = task
        return task
    
    def execute_task(self, task: WindowInteractionTask) -> Dict[str, Any]:
        """Execute a window interaction task."""
        task.update_status(TaskStatus.IN_PROGRESS)
        
        try:
            if task.task_type == "find_and_click":
                result = self._handle_find_and_click(task.parameters)
            elif task.task_type == "extract_text":
                result = self._handle_extract_text(task.parameters)
            elif task.task_type == "navigate_to_url":
                result = self._handle_navigate_to_url(task.parameters)
            elif task.task_type == "fill_form":
                result = self._handle_fill_form(task.parameters)
            else:
                raise ValueError(f"Unknown task type: {task.task_type}")
            
            task.update_status(TaskStatus.COMPLETED, result=result)
            return result
            
        except Exception as e:
            task.retry_count += 1
            
            if task.retry_count <= task.max_retries:
                task.update_status(
                    TaskStatus.RETRYING,
                    error=f"Attempt {task.retry_count}/{task.max_retries}: {str(e)}"
                )
                # Add a small delay before retrying
                time.sleep(1)
                return self.execute_task(task)
            else:
                task.update_status(
                    TaskStatus.FAILED,
                    error=f"Failed after {task.retry_count} attempts: {str(e)}"
                )
                return {"success": False, "error": str(e)}
    
    def _handle_find_and_click(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Handle find and click task."""
        element_info = parameters.get("element_info", {})
        return self.browser_automation.find_and_click_element(element_info)
    
    def _handle_extract_text(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Handle extract text task."""
        region = parameters.get("region")
        return self.browser_automation.extract_visible_text(region)
    
    def _handle_navigate_to_url(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Handle navigate to URL task."""
        url = parameters.get("url")
        if not url:
            raise ValueError("URL is required for navigate_to_url task")
        
        # First, try to find and activate a browser window
        self.browser_automation.interact_with_browser("activate_window", title="Chrome")
        
        # Use keyboard shortcut to focus the address bar (Cmd+L on Mac, Ctrl+L on Windows/Linux)
        self.browser_automation.interact_with_browser("press", key="command+l")
        
        # Type the URL and press Enter
        self.browser_automation.interact_with_browser("type", text=url)
        self.browser_automation.interact_with_browser("press", key="enter")
        
        # Wait for the page to load
        time.sleep(3)
        
        return {"success": True, "url": url}
    
    def _handle_fill_form(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Handle form filling task."""
        form_data = parameters.get("form_data", {})
        url = parameters.get("url", "")
        
        if not form_data:
            raise ValueError("form_data is required for fill_form task")
        
        # First navigate to the URL if provided
        if url:
            self._handle_navigate_to_url({"url": url})
        
        # Fill each form field
        for field, value in form_data.items():
            # This is a simplified example - in practice, you'd need to locate each field
            # and interact with it appropriately
            self.browser_automation.interact_with_browser("type", text=value)
            self.browser_automation.interact_with_browser("press", key="tab")
            time.sleep(0.5)
        
        # Submit the form if requested
        if parameters.get("submit", False):
            self.browser_automation.interact_with_browser("press", key="enter")
        
        return {"success": True, "fields_filled": len(form_data)}
    
    def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Get the status of a task."""
        task = self.tasks.get(task_id)
        if task:
            return task.to_dict()
        return None
    
    def list_tasks(self, status: Optional[TaskStatus] = None) -> List[Dict[str, Any]]:
        """List all tasks, optionally filtered by status."""
        if status is not None:
            return [t.to_dict() for t in self.tasks.values() if t.status == status]
        return [t.to_dict() for t in self.tasks.values()]
