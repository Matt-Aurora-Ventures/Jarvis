"""
Window Interaction CLI for Jarvis

Provides a command-line interface for interacting with browser windows and elements.
"""

import argparse
import json
import sys
from typing import Dict, Any, List, Optional

from core.browser_automation import get_browser_automation
from core.window_interaction_task import WindowInteractionTaskHandler, TaskStatus

class WindowCLI:
    """Command-line interface for window interaction."""
    
    def __init__(self):
        self.browser = get_browser_automation()
        self.task_handler = WindowInteractionTaskHandler(self.browser)
        self.parser = self._create_parser()
    
    def _create_parser(self) -> argparse.ArgumentParser:
        """Create the argument parser."""
        parser = argparse.ArgumentParser(description="Jarvis Window Interaction CLI")
        subparsers = parser.add_subparsers(dest="command", help="Command to execute")
        
        # List windows command
        list_parser = subparsers.add_parser("list-windows", help="List all browser windows")
        
        # Activate window command
        activate_parser = subparsers.add_parser("activate-window", help="Activate a browser window")
        activate_parser.add_argument("title", help="Title or part of the window title to activate")
        
        # Click command
        click_parser = subparsers.add_parser("click", help="Click at specific coordinates")
        click_parser.add_argument("x", type=int, help="X coordinate")
        click_parser.add_argument("y", type=int, help="Y coordinate")
        click_parser.add_argument("--button", default="left", help="Mouse button (left, right, middle)")
        click_parser.add_argument("--clicks", type=int, default=1, help="Number of clicks")
        
        # Type command
        type_parser = subparsers.add_parser("type", help="Type text at the current cursor position")
        type_parser.add_argument("text", help="Text to type")
        
        # Press key command
        press_parser = subparsers.add_parser("press", help="Press a key")
        press_parser.add_argument("key", help="Key to press (e.g., 'enter', 'tab', 'esc')")
        
        # Scroll command
        scroll_parser = subparsers.add_parser("scroll", help="Scroll the mouse wheel")
        scroll_parser.add_argument("clicks", type=int, help="Number of scroll clicks (positive for up, negative for down)")
        
        # Move mouse command
        move_parser = subparsers.add_parser("move", help="Move the mouse to specific coordinates")
        move_parser.add_argument("x", type=int, help="X coordinate")
        move_parser.add_argument("y", type=int, help="Y coordinate")
        move_parser.add_argument("--duration", type=float, default=0.5, help="Duration of the movement in seconds")
        
        # Get screen size command
        size_parser = subparsers.add_parser("screen-size", help="Get the screen size")
        
        # Get mouse position command
        pos_parser = subparsers.add_parser("mouse-pos", help="Get the current mouse position")
        
        # Extract text command
        extract_parser = subparsers.add_parser("extract-text", help="Extract text from the screen")
        extract_parser.add_argument("--region", nargs=4, type=int, metavar=("left", "top", "width", "height"), 
                                  help="Region to extract text from (left, top, width, height)")
        
        # Navigate to URL command
        nav_parser = subparsers.add_parser("navigate", help="Navigate to a URL")
        nav_parser.add_argument("url", help="URL to navigate to")
        
        # Create task command
        task_parser = subparsers.add_parser("create-task", help="Create a window interaction task")
        task_parser.add_argument("task_type", help="Type of task (find_and_click, extract_text, navigate_to_url, fill_form)")
        task_parser.add_argument("--params", type=json.loads, default={}, help="Task parameters as a JSON string")
        
        # Execute task command
        execute_parser = subparsers.add_parser("execute-task", help="Execute a window interaction task")
        execute_parser.add_argument("task_id", help="ID of the task to execute")
        
        # Task status command
        status_parser = subparsers.add_parser("task-status", help="Get the status of a task")
        status_parser.add_argument("task_id", help="ID of the task")
        
        # List tasks command
        list_tasks_parser = subparsers.add_parser("list-tasks", help="List all tasks")
        list_tasks_parser.add_argument("--status", help="Filter tasks by status")
        
        return parser
    
    def run(self, args: Optional[List[str]] = None) -> int:
        """Run the CLI with the given arguments."""
        if not args:
            args = sys.argv[1:]
        
        if not args:
            self.parser.print_help()
            return 0
        
        parsed_args = self.parser.parse_args(args)
        
        try:
            if parsed_args.command == "list-windows":
                self._handle_list_windows()
            elif parsed_args.command == "activate-window":
                self._handle_activate_window(parsed_args.title)
            elif parsed_args.command == "click":
                self._handle_click(parsed_args.x, parsed_args.y, parsed_args.button, parsed_args.clicks)
            elif parsed_args.command == "type":
                self._handle_type(parsed_args.text)
            elif parsed_args.command == "press":
                self._handle_press(parsed_args.key)
            elif parsed_args.command == "scroll":
                self._handle_scroll(parsed_args.clicks)
            elif parsed_args.command == "move":
                self._handle_move(parsed_args.x, parsed_args.y, parsed_args.duration)
            elif parsed_args.command == "screen-size":
                self._handle_screen_size()
            elif parsed_args.command == "mouse-pos":
                self._handle_mouse_pos()
            elif parsed_args.command == "extract-text":
                self._handle_extract_text(parsed_args.region)
            elif parsed_args.command == "navigate":
                self._handle_navigate(parsed_args.url)
            elif parsed_args.command == "create-task":
                self._handle_create_task(parsed_args.task_type, parsed_args.params)
            elif parsed_args.command == "execute-task":
                self._handle_execute_task(parsed_args.task_id)
            elif parsed_args.command == "task-status":
                self._handle_task_status(parsed_args.task_id)
            elif parsed_args.command == "list-tasks":
                self._handle_list_tasks(parsed_args.status)
            else:
                self.parser.print_help()
                return 1
                
            return 0
            
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1
    
    def _print_json(self, data: Any):
        """Print data as formatted JSON."""
        print(json.dumps(data, indent=2))
    
    def _handle_list_windows(self):
        """Handle list-windows command."""
        result = self.browser.interact_with_browser("list_windows")
        self._print_json(result)
    
    def _handle_activate_window(self, title: str):
        """Handle activate-window command."""
        result = self.browser.interact_with_browser("activate_window", title=title)
        self._print_json(result)
    
    def _handle_click(self, x: int, y: int, button: str, clicks: int):
        """Handle click command."""
        result = self.browser.interact_with_browser("click", x=x, y=y, button=button, clicks=clicks)
        self._print_json(result)
    
    def _handle_type(self, text: str):
        """Handle type command."""
        result = self.browser.interact_with_browser("type", text=text)
        self._print_json(result)
    
    def _handle_press(self, key: str):
        """Handle press command."""
        result = self.browser.interact_with_browser("press", key=key)
        self._print_json(result)
    
    def _handle_scroll(self, clicks: int):
        """Handle scroll command."""
        result = self.browser.interact_with_browser("scroll", clicks=clicks)
        self._print_json(result)
    
    def _handle_move(self, x: int, y: int, duration: float):
        """Handle move command."""
        result = self.browser.interact_with_browser("move_mouse", x=x, y=y, duration=duration)
        self._print_json(result)
    
    def _handle_screen_size(self):
        """Handle screen-size command."""
        result = self.browser.interact_with_browser("get_screen_size")
        self._print_json(result)
    
    def _handle_mouse_pos(self):
        """Handle mouse-pos command."""
        result = self.browser.interact_with_browser("get_mouse_position")
        self._print_json(result)
    
    def _handle_extract_text(self, region: Optional[List[int]]):
        """Handle extract-text command."""
        if region and len(region) == 4:
            region = tuple(region)  # Convert to tuple for compatibility
        result = self.browser.extract_visible_text(region)
        self._print_json(result)
    
    def _handle_navigate(self, url: str):
        """Handle navigate command."""
        task = self.task_handler.create_task("navigate_to_url", {"url": url})
        result = self.task_handler.execute_task(task)
        self._print_json({"task_id": task.task_id, "result": result})
    
    def _handle_create_task(self, task_type: str, params: Dict[str, Any]):
        """Handle create-task command."""
        task = self.task_handler.create_task(task_type, params)
        self._print_json({"task_id": task.task_id, "status": task.status.name})
    
    def _handle_execute_task(self, task_id: str):
        """Handle execute-task command."""
        task = self.task_handler.tasks.get(task_id)
        if not task:
            print(f"Error: Task {task_id} not found", file=sys.stderr)
            return
            
        result = self.task_handler.execute_task(task)
        self._print_json({"task_id": task_id, "result": result})
    
    def _handle_task_status(self, task_id: str):
        """Handle task-status command."""
        status = self.task_handler.get_task_status(task_id)
        if status:
            self._print_json(status)
        else:
            print(f"Error: Task {task_id} not found", file=sys.stderr)
    
    def _handle_list_tasks(self, status: Optional[str]):
        """Handle list-tasks command."""
        status_enum = None
        if status:
            try:
                status_enum = TaskStatus[status.upper()]
            except KeyError:
                print(f"Error: Invalid status '{status}'", file=sys.stderr)
                return
                
        tasks = self.task_handler.list_tasks(status_enum)
        self._print_json(tasks)


def main():
    """Main entry point for the CLI."""
    cli = WindowCLI()
    sys.exit(cli.run())


if __name__ == "__main__":
    main()
