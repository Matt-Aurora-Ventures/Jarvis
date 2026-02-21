"""
Computer Control module for LifeOS.
Allows Jarvis to control the computer safely with guardian protection.
Cross-platform support for Windows, macOS, and Linux.
"""

import os
import platform
import subprocess
import tempfile
import time
import webbrowser
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from core import guardian, safe_subprocess
from core.command_dsl.executor import execute_typed_command, parse_typed_command

# Detect platform
PLATFORM = platform.system().lower()
IS_WINDOWS = PLATFORM == "windows"
IS_MACOS = PLATFORM == "darwin"
IS_LINUX = PLATFORM == "linux"


@dataclass
class ControlAction:
    action_type: str
    params: Dict[str, Any]
    safe: bool
    reason: str = ""


def _run_applescript(script: str, timeout: int = 10) -> Tuple[bool, str]:
    """Run AppleScript and return success status and output. macOS only."""
    if not IS_MACOS:
        return False, "AppleScript only available on macOS"
    try:
        result = safe_subprocess.run_command_safe(
            ["osascript", "-e", script],
            timeout=timeout,
        )
        return (
            result.get("returncode") == 0,
            (result.get("stdout", "").strip() or result.get("stderr", "").strip()),
        )
    except Exception as e:
        return False, str(e)


def _run_powershell(script: str, timeout: int = 10) -> Tuple[bool, str]:
    """Run PowerShell command on Windows."""
    if not IS_WINDOWS:
        return False, "PowerShell only available on Windows"
    try:
        result = subprocess.run(
            ["powershell", "-Command", script],
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

    try:
        import pyautogui
        pyautogui.typewrite(text, interval=0.02)
        return True, f"Typed text"
    except ImportError:
        pass

    if IS_MACOS:
        # Properly escape for AppleScript string literals: backslash first, then quote
        escaped_text = text.replace("\\", "\\\\").replace('"', '\\"')
        script = f'''
        tell application "System Events"
            keystroke "{escaped_text}"
        end tell
        '''
        return _run_applescript(script)

    return False, "pyautogui not available for typing"


def press_key(key: str, modifiers: List[str] = None) -> Tuple[bool, str]:
    """Press a key with optional modifiers (command, control, option, shift)."""
    modifiers = modifiers or []

    try:
        import pyautogui

        # Map modifier names
        mod_map = {
            "command": "command" if IS_MACOS else "win",
            "cmd": "command" if IS_MACOS else "win",
            "control": "ctrl",
            "ctrl": "ctrl",
            "option": "alt",
            "alt": "alt",
            "shift": "shift",
        }

        # Map key names
        key_map = {
            "enter": "return",
            "esc": "escape",
            "del": "delete",
        }
        mapped_key = key_map.get(key.lower(), key.lower())
        mapped_mods = [mod_map.get(m.lower(), m.lower()) for m in modifiers]

        if mapped_mods:
            pyautogui.hotkey(*mapped_mods, mapped_key)
        else:
            pyautogui.press(mapped_key)

        return True, f"Pressed {key}"
    except ImportError:
        pass

    if IS_MACOS:
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
            keystroke "{key}"{mod_str}
        end tell
        '''
        return _run_applescript(script)

    return False, "pyautogui not available for key press"


def click_at(x: int, y: int, button: str = "left") -> Tuple[bool, str]:
    """Click at screen coordinates."""
    try:
        import pyautogui
        pyautogui.click(x, y, button=button)
        return True, f"Clicked at ({x}, {y})"
    except ImportError:
        pass

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
        import pyautogui
        pyautogui.moveTo(x, y)
        return True, f"Moved to ({x}, {y})"
    except ImportError:
        pass

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
        import pyautogui
        if dy != 0:
            pyautogui.scroll(dy)
        if dx != 0:
            pyautogui.hscroll(dx)
        return True, f"Scrolled ({dx}, {dy})"
    except ImportError:
        pass

    try:
        from pynput.mouse import Controller
        mouse = Controller()
        mouse.scroll(dx, dy)
        return True, f"Scrolled ({dx}, {dy})"
    except Exception as e:
        return False, str(e)


def open_app(app_name: str) -> Tuple[bool, str]:
    """Open an application."""
    if IS_WINDOWS:
        try:
            # Use ShellExecuteW via os.startfile to avoid shell=True injection risk
            import os
            os.startfile(app_name)
            return True, f"Opening {app_name}"
        except Exception as e:
            return False, str(e)
    elif IS_MACOS:
        script = f'tell application "{app_name}" to activate'
        return _run_applescript(script)
    else:  # Linux
        try:
            subprocess.Popen([app_name], start_new_session=True)
            return True, f"Opening {app_name}"
        except Exception as e:
            return False, str(e)


def close_app(app_name: str) -> Tuple[bool, str]:
    """Close an application (quit)."""
    # Safety: don't close critical apps
    protected_windows = ["explorer", "cmd", "powershell", "taskmgr"]
    protected_macos = ["Finder", "System Preferences", "Terminal"]
    protected_linux = ["nautilus", "gnome-shell"]

    app_lower = app_name.lower()
    if IS_WINDOWS and app_lower in protected_windows:
        return False, f"Cannot close protected app: {app_name}"
    elif IS_MACOS and app_name in protected_macos:
        return False, f"Cannot close protected app: {app_name}"
    elif IS_LINUX and app_lower in protected_linux:
        return False, f"Cannot close protected app: {app_name}"

    if IS_WINDOWS:
        try:
            subprocess.run(["taskkill", "/IM", f"{app_name}.exe", "/F"],
                         capture_output=True, timeout=10)
            return True, f"Closed {app_name}"
        except Exception as e:
            return False, str(e)
    elif IS_MACOS:
        script = f'tell application "{app_name}" to quit'
        return _run_applescript(script)
    else:  # Linux
        try:
            subprocess.run(["pkill", "-f", app_name], capture_output=True, timeout=10)
            return True, f"Closed {app_name}"
        except Exception as e:
            return False, str(e)


def open_url(url: str) -> Tuple[bool, str]:
    """Open a URL in default browser."""
    try:
        webbrowser.open(url)
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
        if IS_WINDOWS:
            os.startfile(path)
        elif IS_MACOS:
            subprocess.run(["open", path], check=True, timeout=5)
        else:  # Linux
            subprocess.run(["xdg-open", path], check=True, timeout=5)
        return True, f"Opened file {path}"
    except Exception as e:
        return False, str(e)


def run_shell(command: str, cwd: str = None, timeout: int = None) -> Tuple[bool, str]:
    """Run a shell command (with safety checks and aggressive timeout protection)."""
    # Safety check
    is_dangerous, reason = guardian.is_command_dangerous(command)
    if is_dangerous:
        return False, f"Blocked dangerous command: {reason}"

    try:
        typed = parse_typed_command(
            command=command,
            timeout=timeout,
            cwd=cwd,
        )
        result = execute_typed_command(typed, capture_output=True)

        if result.get("blocked"):
            return False, result.get("stderr", "Command blocked by typed DSL")

        if result.get("timed_out"):
            return False, f"Command timed out after {result.get('timeout')}s"

        output = result.get("stdout") or result.get("stderr") or ""
        return result.get("returncode") == 0, output[:1000]
    except Exception as e:
        return False, str(e)


def get_clipboard() -> str:
    """Get clipboard contents."""
    try:
        import pyperclip
        return pyperclip.paste()
    except ImportError:
        pass

    try:
        if IS_WINDOWS:
            result = subprocess.run(
                ["powershell", "-Command", "Get-Clipboard"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            return result.stdout.strip()
        elif IS_MACOS:
            result = subprocess.run(
                ["pbpaste"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            return result.stdout
        else:  # Linux
            result = subprocess.run(
                ["xclip", "-selection", "clipboard", "-o"],
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
        import pyperclip
        pyperclip.copy(text)
        return True, "Clipboard set"
    except ImportError:
        pass

    try:
        if IS_WINDOWS:
            subprocess.run(
                ["powershell", "-Command", f"Set-Clipboard -Value '{text}'"],
                timeout=5,
            )
            return True, "Clipboard set"
        elif IS_MACOS:
            process = subprocess.Popen(
                ["pbcopy"],
                stdin=subprocess.PIPE,
            )
            process.communicate(text.encode("utf-8"))
            return True, "Clipboard set"
        else:  # Linux
            process = subprocess.Popen(
                ["xclip", "-selection", "clipboard"],
                stdin=subprocess.PIPE,
            )
            process.communicate(text.encode("utf-8"))
            return True, "Clipboard set"
    except Exception as e:
        return False, str(e)


def take_screenshot(output_path: str = None) -> Tuple[bool, str]:
    """Take a screenshot."""
    if output_path is None:
        temp_dir = tempfile.gettempdir()
        output_path = os.path.join(temp_dir, f"jarvis_screenshot_{int(time.time())}.png")

    try:
        import pyautogui
        screenshot = pyautogui.screenshot()
        screenshot.save(output_path)
        return True, output_path
    except ImportError:
        pass

    try:
        if IS_WINDOWS:
            # Use PowerShell for screenshot
            ps_script = f'''
            Add-Type -AssemblyName System.Windows.Forms
            $screen = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds
            $bitmap = New-Object System.Drawing.Bitmap($screen.Width, $screen.Height)
            $graphics = [System.Drawing.Graphics]::FromImage($bitmap)
            $graphics.CopyFromScreen($screen.Location, [System.Drawing.Point]::Empty, $screen.Size)
            $bitmap.Save("{output_path}")
            '''
            subprocess.run(["powershell", "-Command", ps_script], timeout=10)
            return True, output_path
        elif IS_MACOS:
            subprocess.run(
                ["screencapture", "-x", output_path],
                check=True,
                timeout=10,
            )
            return True, output_path
        else:  # Linux
            subprocess.run(
                ["gnome-screenshot", "-f", output_path],
                check=True,
                timeout=10,
            )
            return True, output_path
    except Exception as e:
        return False, str(e)


def get_screen_size() -> Tuple[int, int]:
    """Get screen dimensions."""
    try:
        import pyautogui
        size = pyautogui.size()
        return size.width, size.height
    except ImportError:
        pass

    if IS_WINDOWS:
        try:
            import ctypes
            user32 = ctypes.windll.user32
            return user32.GetSystemMetrics(0), user32.GetSystemMetrics(1)
        except Exception:
            pass
    elif IS_MACOS:
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
            except Exception:
                pass

    return 1920, 1080  # Default


def get_window_list() -> List[Dict[str, Any]]:
    """Get list of open windows."""
    windows = []

    if IS_WINDOWS:
        try:
            ps_script = '''
            Get-Process | Where-Object {$_.MainWindowTitle} |
            Select-Object ProcessName, MainWindowTitle |
            ForEach-Object { "$($_.ProcessName)||$($_.MainWindowTitle)" }
            '''
            result = subprocess.run(
                ["powershell", "-Command", ps_script],
                capture_output=True,
                text=True,
                timeout=10,
            )
            for line in result.stdout.strip().split("\n"):
                if "||" in line:
                    app, win = line.split("||", 1)
                    windows.append({"app": app.strip(), "window": win.strip()})
        except Exception:
            pass
    elif IS_MACOS:
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
        if success and output:
            for item in output.split(", "):
                if "||" in item:
                    app, win = item.split("||", 1)
                    windows.append({"app": app.strip(), "window": win.strip()})

    return windows


def focus_window(app_name: str, window_title: str = None) -> Tuple[bool, str]:
    """Focus a specific window."""
    if IS_WINDOWS:
        try:
            if window_title:
                ps_script = f'''
                $wshell = New-Object -ComObject wscript.shell
                $windows = Get-Process | Where-Object {{$_.MainWindowTitle -like "*{window_title}*"}}
                if ($windows) {{
                    $wshell.AppActivate($windows[0].MainWindowTitle)
                }}
                '''
            else:
                ps_script = f'''
                $wshell = New-Object -ComObject wscript.shell
                $wshell.AppActivate("{app_name}")
                '''
            subprocess.run(["powershell", "-Command", ps_script], timeout=5)
            return True, f"Focused {app_name}"
        except Exception as e:
            return False, str(e)
    elif IS_MACOS:
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

    return False, "Window focus not supported on this platform"


class ComputerController:
    """High-level computer control interface for Jarvis."""

    def __init__(self):
        self._guard = guardian.guard()
        self._platform = PLATFORM

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
            "platform": self._platform,
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
