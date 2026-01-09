"""
Platform abstraction layer for Jarvis.

This package provides cross-platform abstractions for OS-specific operations.
Automatically detects the current platform and loads the appropriate adapter.

Supported platforms:
- macOS (darwin)
- Windows (win32)
- Linux (linux)
"""

import platform
import sys
from typing import Optional, List, Dict, Any
from abc import ABC, abstractmethod


class PlatformAdapter(ABC):
    """Abstract base class for platform-specific operations."""

    @abstractmethod
    def send_notification(self, title: str, message: str) -> bool:
        """Send a system notification."""
        pass

    @abstractmethod
    def get_active_window_info(self) -> Dict[str, Any]:
        """Get information about the currently active window."""
        pass

    @abstractmethod
    def open_application(self, app_name: str) -> bool:
        """Open an application by name."""
        pass

    @abstractmethod
    def execute_keyboard_shortcut(self, keys: List[str]) -> bool:
        """Execute a keyboard shortcut."""
        pass

    @abstractmethod
    def get_clipboard_content(self) -> str:
        """Get the current clipboard content."""
        pass

    @abstractmethod
    def set_clipboard_content(self, content: str) -> bool:
        """Set the clipboard content."""
        pass

    @abstractmethod
    def speak_text(self, text: str, voice: Optional[str] = None) -> bool:
        """Speak text using system TTS."""
        pass

    @abstractmethod
    def get_screen_capture(self) -> Optional[bytes]:
        """Capture the current screen."""
        pass


class MacOSAdapter(PlatformAdapter):
    """macOS-specific implementation using osascript and pyobjc."""

    def send_notification(self, title: str, message: str) -> bool:
        try:
            import subprocess
            # Sanitize inputs
            safe_title = title.replace('\\', '\\\\').replace('"', '\\"')
            safe_message = message.replace('\\', '\\\\').replace('"', '\\"')
            script = f'display notification "{safe_message}" with title "{safe_title}"'
            subprocess.run(["osascript", "-e", script], timeout=5, check=False)
            return True
        except Exception:
            return False

    def get_active_window_info(self) -> Dict[str, Any]:
        try:
            import subprocess
            script = '''
            tell application "System Events"
                set frontApp to name of first application process whose frontmost is true
            end tell
            return frontApp
            '''
            result = subprocess.run(
                ["osascript", "-e", script],
                capture_output=True,
                text=True,
                timeout=5
            )
            return {"app_name": result.stdout.strip(), "platform": "macos"}
        except Exception:
            return {"app_name": "Unknown", "platform": "macos"}

    def open_application(self, app_name: str) -> bool:
        try:
            import subprocess
            subprocess.run(["open", "-a", app_name], timeout=10, check=True)
            return True
        except Exception:
            return False

    def execute_keyboard_shortcut(self, keys: List[str]) -> bool:
        try:
            import subprocess
            key_str = " + ".join(keys)
            # Convert to osascript format
            script = f'''
            tell application "System Events"
                keystroke "{keys[-1]}" using {{{", ".join(f"{k} down" for k in keys[:-1])}}}
            end tell
            '''
            subprocess.run(["osascript", "-e", script], timeout=5, check=False)
            return True
        except Exception:
            return False

    def get_clipboard_content(self) -> str:
        try:
            import subprocess
            result = subprocess.run(["pbpaste"], capture_output=True, text=True, timeout=5)
            return result.stdout
        except Exception:
            return ""

    def set_clipboard_content(self, content: str) -> bool:
        try:
            import subprocess
            process = subprocess.Popen(["pbcopy"], stdin=subprocess.PIPE)
            process.communicate(content.encode("utf-8"))
            return True
        except Exception:
            return False

    def speak_text(self, text: str, voice: Optional[str] = None) -> bool:
        try:
            import subprocess
            cmd = ["say"]
            if voice:
                cmd.extend(["-v", voice])
            cmd.append(text)
            subprocess.run(cmd, timeout=60, check=False)
            return True
        except Exception:
            return False

    def get_screen_capture(self) -> Optional[bytes]:
        try:
            import subprocess
            import tempfile
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
                subprocess.run(["screencapture", "-x", f.name], timeout=10, check=True)
                return open(f.name, "rb").read()
        except Exception:
            return None


class WindowsAdapter(PlatformAdapter):
    """Windows-specific implementation using win32 APIs."""

    def send_notification(self, title: str, message: str) -> bool:
        try:
            from win10toast import ToastNotifier
            toaster = ToastNotifier()
            toaster.show_toast(title, message, duration=5, threaded=True)
            return True
        except ImportError:
            # Fallback to PowerShell
            try:
                import subprocess
                ps_script = f'''
                [Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
                $template = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent([Windows.UI.Notifications.ToastTemplateType]::ToastText02)
                $textNodes = $template.GetElementsByTagName("text")
                $textNodes[0].AppendChild($template.CreateTextNode("{title}")) | Out-Null
                $textNodes[1].AppendChild($template.CreateTextNode("{message}")) | Out-Null
                $notifier = [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier("Jarvis")
                $notifier.Show([Windows.UI.Notifications.ToastNotification]::new($template))
                '''
                subprocess.run(["powershell", "-Command", ps_script], timeout=10, check=False)
                return True
            except Exception:
                return False
        except Exception:
            return False

    def get_active_window_info(self) -> Dict[str, Any]:
        try:
            import win32gui
            window = win32gui.GetForegroundWindow()
            title = win32gui.GetWindowText(window)
            return {"app_name": title, "platform": "windows", "hwnd": window}
        except Exception:
            return {"app_name": "Unknown", "platform": "windows"}

    def open_application(self, app_name: str) -> bool:
        try:
            import subprocess
            subprocess.Popen(["start", "", app_name], shell=True)
            return True
        except Exception:
            return False

    def execute_keyboard_shortcut(self, keys: List[str]) -> bool:
        try:
            import pyautogui
            pyautogui.hotkey(*keys)
            return True
        except Exception:
            return False

    def get_clipboard_content(self) -> str:
        try:
            import win32clipboard
            win32clipboard.OpenClipboard()
            try:
                data = win32clipboard.GetClipboardData(win32clipboard.CF_UNICODETEXT)
                return data
            finally:
                win32clipboard.CloseClipboard()
        except Exception:
            return ""

    def set_clipboard_content(self, content: str) -> bool:
        try:
            import win32clipboard
            win32clipboard.OpenClipboard()
            try:
                win32clipboard.EmptyClipboard()
                win32clipboard.SetClipboardText(content, win32clipboard.CF_UNICODETEXT)
                return True
            finally:
                win32clipboard.CloseClipboard()
        except Exception:
            return False

    def speak_text(self, text: str, voice: Optional[str] = None) -> bool:
        try:
            import pyttsx3
            engine = pyttsx3.init()
            if voice:
                voices = engine.getProperty('voices')
                for v in voices:
                    if voice.lower() in v.name.lower():
                        engine.setProperty('voice', v.id)
                        break
            engine.say(text)
            engine.runAndWait()
            return True
        except Exception:
            return False

    def get_screen_capture(self) -> Optional[bytes]:
        try:
            import pyautogui
            from io import BytesIO
            screenshot = pyautogui.screenshot()
            buffer = BytesIO()
            screenshot.save(buffer, format='PNG')
            return buffer.getvalue()
        except Exception:
            return None


class LinuxAdapter(PlatformAdapter):
    """Linux-specific implementation using standard tools."""

    def send_notification(self, title: str, message: str) -> bool:
        try:
            import subprocess
            subprocess.run(["notify-send", title, message], timeout=5, check=False)
            return True
        except Exception:
            return False

    def get_active_window_info(self) -> Dict[str, Any]:
        try:
            import subprocess
            result = subprocess.run(
                ["xdotool", "getactivewindow", "getwindowname"],
                capture_output=True,
                text=True,
                timeout=5
            )
            return {"app_name": result.stdout.strip(), "platform": "linux"}
        except Exception:
            return {"app_name": "Unknown", "platform": "linux"}

    def open_application(self, app_name: str) -> bool:
        try:
            import subprocess
            subprocess.Popen(["xdg-open", app_name])
            return True
        except Exception:
            return False

    def execute_keyboard_shortcut(self, keys: List[str]) -> bool:
        try:
            import subprocess
            key_combo = "+".join(keys)
            subprocess.run(["xdotool", "key", key_combo], timeout=5, check=False)
            return True
        except Exception:
            return False

    def get_clipboard_content(self) -> str:
        try:
            import subprocess
            result = subprocess.run(
                ["xclip", "-selection", "clipboard", "-o"],
                capture_output=True,
                text=True,
                timeout=5
            )
            return result.stdout
        except Exception:
            return ""

    def set_clipboard_content(self, content: str) -> bool:
        try:
            import subprocess
            process = subprocess.Popen(
                ["xclip", "-selection", "clipboard"],
                stdin=subprocess.PIPE
            )
            process.communicate(content.encode("utf-8"))
            return True
        except Exception:
            return False

    def speak_text(self, text: str, voice: Optional[str] = None) -> bool:
        try:
            import subprocess
            cmd = ["espeak"]
            if voice:
                cmd.extend(["-v", voice])
            cmd.append(text)
            subprocess.run(cmd, timeout=60, check=False)
            return True
        except Exception:
            return False

    def get_screen_capture(self) -> Optional[bytes]:
        try:
            import subprocess
            import tempfile
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
                subprocess.run(["scrot", f.name], timeout=10, check=True)
                return open(f.name, "rb").read()
        except Exception:
            return None


def get_platform_adapter() -> PlatformAdapter:
    """Get the appropriate platform adapter for the current OS."""
    system = platform.system().lower()

    if system == "darwin":
        return MacOSAdapter()
    elif system == "windows":
        return WindowsAdapter()
    elif system == "linux":
        return LinuxAdapter()
    else:
        # Default to Linux-like behavior
        return LinuxAdapter()


# Create singleton instance
_adapter: Optional[PlatformAdapter] = None


def get_adapter() -> PlatformAdapter:
    """Get the singleton platform adapter instance."""
    global _adapter
    if _adapter is None:
        _adapter = get_platform_adapter()
    return _adapter


# Convenience functions that use the singleton adapter
def send_notification(title: str, message: str) -> bool:
    """Send a system notification."""
    return get_adapter().send_notification(title, message)


def get_active_window_info() -> Dict[str, Any]:
    """Get information about the currently active window."""
    return get_adapter().get_active_window_info()


def open_application(app_name: str) -> bool:
    """Open an application by name."""
    return get_adapter().open_application(app_name)


def execute_keyboard_shortcut(keys: List[str]) -> bool:
    """Execute a keyboard shortcut."""
    return get_adapter().execute_keyboard_shortcut(keys)


def get_clipboard_content() -> str:
    """Get the current clipboard content."""
    return get_adapter().get_clipboard_content()


def set_clipboard_content(content: str) -> bool:
    """Set the clipboard content."""
    return get_adapter().set_clipboard_content(content)


def speak_text(text: str, voice: Optional[str] = None) -> bool:
    """Speak text using system TTS."""
    return get_adapter().speak_text(text, voice)


def get_screen_capture() -> Optional[bytes]:
    """Capture the current screen."""
    return get_adapter().get_screen_capture()


__all__ = [
    # Classes
    "PlatformAdapter",
    "MacOSAdapter",
    "WindowsAdapter",
    "LinuxAdapter",
    # Factory
    "get_platform_adapter",
    "get_adapter",
    # Convenience functions
    "send_notification",
    "get_active_window_info",
    "open_application",
    "execute_keyboard_shortcut",
    "get_clipboard_content",
    "set_clipboard_content",
    "speak_text",
    "get_screen_capture",
]
