"""
Computer Control module for LifeOS.
Allows Jarvis to control the computer safely with guardian protection.
"""

import subprocess
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from core import guardian


@dataclass
class ControlAction:
    action_type: str
    params: Dict[str, Any]
    safe: bool
    reason: str = ""


def _run_applescript(script: str, timeout: int = 10) -> Tuple[bool, str]:
    """Run AppleScript and return success status and output."""
    try:
        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return result.returncode == 0, result.stdout.strip() or result.stderr.strip()
    except Exception as e:
        return False, str(e)


def type_text(text: str) -> Tuple[bool, str]:
    """Type text using keyboard simulation."""
    # Safety check
    is_safe, reason = guardian.is_command_dangerous(f"type: {text}")
    if not is_safe:
        return False, f"Blocked: {reason}"
    
    script = f'''
    tell application "System Events"
        keystroke "{text.replace('"', '\\"')}"
    end tell
    '''
    return _run_applescript(script)


def press_key(key: str, modifiers: List[str] = None) -> Tuple[bool, str]:
    """Press a key with optional modifiers (command, control, option, shift)."""
    modifiers = modifiers or []
    
    # Map common key names
    key_map = {
        "enter": "return",
        "esc": "escape",
        "del": "delete",
        "up": "up arrow",
        "down": "down arrow",
        "left": "left arrow",
        "right": "right arrow",
    }
    key = key_map.get(key.lower(), key.lower())
    
    mod_str = ""
    if modifiers:
        mod_str = " using {" + ", ".join(f"{m} down" for m in modifiers) + "}"
    
    script = f'''
    tell application "System Events"
        key code (key code of "{key}"){mod_str}
    end tell
    '''
    
    # For special keys, use keystroke
    if key in ["return", "escape", "delete", "tab", "space"]:
        script = f'''
        tell application "System Events"
            keystroke {key}{mod_str}
        end tell
        '''
    
    return _run_applescript(script)


def click_at(x: int, y: int, button: str = "left") -> Tuple[bool, str]:
    """Click at screen coordinates."""
    try:
        from pynput.mouse import Button, Controller
        mouse = Controller()
        mouse.position = (x, y)
        time.sleep(0.1)
        
        btn = Button.left if button == "left" else Button.right
        mouse.click(btn)
        return True, f"Clicked at ({x}, {y})"
    except Exception as e:
        return False, str(e)


def move_mouse(x: int, y: int) -> Tuple[bool, str]:
    """Move mouse to coordinates."""
    try:
        from pynput.mouse import Controller
        mouse = Controller()
        mouse.position = (x, y)
        return True, f"Moved to ({x}, {y})"
    except Exception as e:
        return False, str(e)


def scroll(dx: int = 0, dy: int = 0) -> Tuple[bool, str]:
    """Scroll by delta amounts."""
    try:
        from pynput.mouse import Controller
        mouse = Controller()
        mouse.scroll(dx, dy)
        return True, f"Scrolled ({dx}, {dy})"
    except Exception as e:
        return False, str(e)


def open_app(app_name: str) -> Tuple[bool, str]:
    """Open an application."""
    script = f'tell application "{app_name}" to activate'
    return _run_applescript(script)


def close_app(app_name: str) -> Tuple[bool, str]:
    """Close an application (quit)."""
    # Safety: don't close critical apps
    protected = ["Finder", "System Preferences", "Terminal"]
    if app_name in protected:
        return False, f"Cannot close protected app: {app_name}"
    
    script = f'tell application "{app_name}" to quit'
    return _run_applescript(script)


def open_url(url: str) -> Tuple[bool, str]:
    """Open a URL in default browser."""
    try:
        subprocess.run(["open", url], check=True, timeout=5)
        return True, f"Opened {url}"
    except Exception as e:
        return False, str(e)


def open_file(path: str) -> Tuple[bool, str]:
    """Open a file with default application."""
    # Safety check
    is_protected, reason = guardian.is_path_protected(path)
    if is_protected:
        return False, f"Cannot open protected path: {reason}"
    
    try:
        subprocess.run(["open", path], check=True, timeout=5)
        return True, f"Opened {path}"
    except Exception as e:
        return False, str(e)


def run_shell(command: str, cwd: str = None, timeout: int = 30) -> Tuple[bool, str]:
    """Run a shell command (with safety checks)."""
    # Safety check
    is_dangerous, reason = guardian.is_command_dangerous(command)
    if is_dangerous:
        return False, f"Blocked dangerous command: {reason}"
    
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            cwd=cwd,
            timeout=timeout,
        )
        output = result.stdout or result.stderr
        return result.returncode == 0, output[:1000]
    except Exception as e:
        return False, str(e)


def get_clipboard() -> str:
    """Get clipboard contents."""
    try:
        result = subprocess.run(
            ["pbpaste"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return result.stdout
    except Exception as e:
        return ""


def set_clipboard(text: str) -> Tuple[bool, str]:
    """Set clipboard contents."""
    try:
        process = subprocess.Popen(
            ["pbcopy"],
            stdin=subprocess.PIPE,
        )
        process.communicate(text.encode("utf-8"))
        return True, "Clipboard set"
    except Exception as e:
        return False, str(e)


def take_screenshot(output_path: str = None) -> Tuple[bool, str]:
    """Take a screenshot."""
    if output_path is None:
        output_path = f"/tmp/jarvis_screenshot_{int(time.time())}.png"
    
    try:
        subprocess.run(
            ["screencapture", "-x", output_path],
            check=True,
            timeout=10,
        )
        return True, output_path
    except Exception as e:
        return False, str(e)


def get_screen_size() -> Tuple[int, int]:
    """Get screen dimensions."""
    script = '''
    tell application "Finder"
        get bounds of window of desktop
    end tell
    '''
    success, output = _run_applescript(script)
    if success and output:
        try:
            parts = output.split(", ")
            return int(parts[2]), int(parts[3])
        except Exception as e:
            pass
    return 1920, 1080  # Default


def get_window_list() -> List[Dict[str, Any]]:
    """Get list of open windows."""
    script = '''
    tell application "System Events"
        set windowList to {}
        repeat with proc in (every process whose visible is true)
            set procName to name of proc
            try
                repeat with win in (every window of proc)
                    set winName to name of win
                    set end of windowList to procName & "||" & winName
                end repeat
            end try
        end repeat
        return windowList
    end tell
    '''
    success, output = _run_applescript(script)
    windows = []
    if success and output:
        for item in output.split(", "):
            if "||" in item:
                app, win = item.split("||", 1)
                windows.append({"app": app.strip(), "window": win.strip()})
    return windows


def focus_window(app_name: str, window_title: str = None) -> Tuple[bool, str]:
    """Focus a specific window."""
    if window_title:
        script = f'''
        tell application "System Events"
            tell process "{app_name}"
                set frontmost to true
                try
                    set focused of (first window whose name contains "{window_title}") to true
                end try
            end tell
        end tell
        '''
    else:
        script = f'tell application "{app_name}" to activate'
    
    return _run_applescript(script)


class ComputerController:
    """High-level computer control interface for Jarvis."""
    
    def __init__(self):
        self._guard = guardian.guard()
    
    def execute(self, action: str, **kwargs) -> Tuple[bool, str]:
        """Execute a computer control action."""
        actions = {
            "type": lambda: type_text(kwargs.get("text", "")),
            "press": lambda: press_key(kwargs.get("key", ""), kwargs.get("modifiers", [])),
            "click": lambda: click_at(kwargs.get("x", 0), kwargs.get("y", 0), kwargs.get("button", "left")),
            "move": lambda: move_mouse(kwargs.get("x", 0), kwargs.get("y", 0)),
            "scroll": lambda: scroll(kwargs.get("dx", 0), kwargs.get("dy", 0)),
            "open_app": lambda: open_app(kwargs.get("app", "")),
            "close_app": lambda: close_app(kwargs.get("app", "")),
            "open_url": lambda: open_url(kwargs.get("url", "")),
            "open_file": lambda: open_file(kwargs.get("path", "")),
            "shell": lambda: run_shell(kwargs.get("command", ""), kwargs.get("cwd")),
            "clipboard_get": lambda: (True, get_clipboard()),
            "clipboard_set": lambda: set_clipboard(kwargs.get("text", "")),
            "screenshot": lambda: take_screenshot(kwargs.get("path")),
            "focus": lambda: focus_window(kwargs.get("app", ""), kwargs.get("window")),
        }
        
        if action not in actions:
            return False, f"Unknown action: {action}"
        
        return actions[action]()
    
    def describe_screen(self) -> Dict[str, Any]:
        """Get current screen state."""
        return {
            "windows": get_window_list(),
            "screen_size": get_screen_size(),
            "clipboard": get_clipboard()[:200],
        }


# Global controller
_controller: Optional[ComputerController] = None


def get_controller() -> ComputerController:
    """Get the global computer controller."""
    global _controller
    if _controller is None:
        _controller = ComputerController()
    return _controller
