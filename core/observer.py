"""
Deep Observer module for LifeOS.
Silently logs ALL keyboard input, mouse actions, and screen activity.
Lightweight, compressed logging with privacy controls.
"""

import gzip
import json
import threading
import time
from collections import deque
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Deque, Dict, List, Optional

from core import config, guardian

ROOT = Path(__file__).resolve().parents[1]
OBSERVER_LOG_PATH = ROOT / "data" / "observer"


@dataclass
class KeyEvent:
    ts: float
    key: str  # Actual key or [SPECIAL]
    app: str
    window: str


@dataclass
class MouseEvent:
    ts: float
    action: str  # click, scroll, move
    x: int
    y: int
    button: str = ""


@dataclass
class ActionLog:
    ts: float
    action_type: str  # key, mouse, app_switch, clipboard
    data: Dict[str, Any]


class DeepObserver(threading.Thread):
    """
    Silent observer that logs every action for context and learning.
    Uses compressed rolling logs to stay lightweight.
    """

    def __init__(self, buffer_size: int = 1000, flush_interval: int = 30):
        super().__init__(daemon=True)
        self._stop_event = threading.Event()
        self._lock = threading.Lock()
        
        # Rolling buffer for recent actions
        self._buffer: Deque[ActionLog] = deque(maxlen=buffer_size)
        self._flush_interval = flush_interval
        
        # Listeners
        self._keyboard_listener = None
        self._mouse_listener = None
        
        # Current context
        self._current_app = ""
        self._current_window = ""
        
        # Stats
        self._total_keys = 0
        self._total_clicks = 0
        self._session_start = time.time()

    def _get_frontmost_app(self) -> tuple:
        """Get current app and window."""
        try:
            import subprocess
            script = '''
            tell application "System Events"
                set frontApp to name of first application process whose frontmost is true
                set frontWindow to ""
                try
                    tell process frontApp
                        set frontWindow to name of front window
                    end tell
                end try
                return frontApp & "||" & frontWindow
            end tell
            '''
            result = subprocess.run(
                ["osascript", "-e", script],
                capture_output=True, text=True, timeout=2
            )
            if result.stdout and "||" in result.stdout:
                parts = result.stdout.strip().split("||", 1)
                return parts[0], parts[1] if len(parts) > 1 else ""
        except Exception:
            pass
        return self._current_app, self._current_window

    def _log_action(self, action_type: str, data: Dict[str, Any]) -> None:
        """Add action to buffer."""
        with self._lock:
            self._buffer.append(ActionLog(
                ts=time.time(),
                action_type=action_type,
                data=data,
            ))

    def _start_keyboard_listener(self) -> bool:
        """Start capturing all keyboard input."""
        try:
            from pynput import keyboard
        except ImportError:
            return False

        def on_press(key):
            self._current_app, self._current_window = self._get_frontmost_app()
            
            # Get key representation
            try:
                if hasattr(key, 'char') and key.char:
                    key_str = key.char
                else:
                    key_str = f"[{key.name}]" if hasattr(key, 'name') else "[?]"
            except Exception:
                key_str = "[?]"
            
            self._log_action("key", {
                "key": key_str,
                "app": self._current_app,
                "window": self._current_window[:80] if self._current_window else "",
            })
            self._total_keys += 1

        try:
            self._keyboard_listener = keyboard.Listener(on_press=on_press)
            self._keyboard_listener.start()
            return True
        except Exception:
            return False

    def _start_mouse_listener(self) -> bool:
        """Start capturing mouse actions."""
        try:
            from pynput import mouse
        except ImportError:
            return False

        last_move_log = [0.0]  # Track last move log time

        def on_click(x, y, button, pressed):
            if pressed:
                self._log_action("click", {
                    "x": x, "y": y,
                    "button": str(button).split(".")[-1],
                    "app": self._current_app,
                })
                self._total_clicks += 1

        def on_scroll(x, y, dx, dy):
            self._log_action("scroll", {
                "x": x, "y": y,
                "dx": dx, "dy": dy,
            })

        def on_move(x, y):
            # Only log moves every 2 seconds to stay lightweight
            now = time.time()
            if now - last_move_log[0] > 2:
                self._log_action("move", {"x": x, "y": y})
                last_move_log[0] = now

        try:
            self._mouse_listener = mouse.Listener(
                on_click=on_click,
                on_scroll=on_scroll,
                on_move=on_move,
            )
            self._mouse_listener.start()
            return True
        except Exception:
            return False

    def _flush_to_disk(self) -> None:
        """Write buffer to compressed log file."""
        with self._lock:
            if not self._buffer:
                return
            
            entries = list(self._buffer)
            self._buffer.clear()

        OBSERVER_LOG_PATH.mkdir(parents=True, exist_ok=True)
        date_str = datetime.now().strftime("%Y-%m-%d")
        log_file = OBSERVER_LOG_PATH / f"{date_str}.jsonl.gz"

        try:
            mode = "ab" if log_file.exists() else "wb"
            with gzip.open(log_file, mode) as f:
                for entry in entries:
                    line = json.dumps(asdict(entry), ensure_ascii=True) + "\n"
                    f.write(line.encode("utf-8"))
        except Exception:
            pass

    def get_recent_actions(self, seconds: int = 60) -> List[ActionLog]:
        """Get recent actions from buffer."""
        cutoff = time.time() - seconds
        with self._lock:
            return [a for a in self._buffer if a.ts > cutoff]

    def get_recent_text(self, seconds: int = 30) -> str:
        """Reconstruct recently typed text."""
        actions = self.get_recent_actions(seconds)
        chars = []
        for a in actions:
            if a.action_type == "key":
                key = a.data.get("key", "")
                if key.startswith("["):
                    if key == "[space]":
                        chars.append(" ")
                    elif key == "[enter]" or key == "[return]":
                        chars.append("\n")
                    elif key == "[backspace]" and chars:
                        chars.pop()
                else:
                    chars.append(key)
        return "".join(chars)

    def get_stats(self) -> Dict[str, Any]:
        """Get observation stats."""
        return {
            "session_duration": time.time() - self._session_start,
            "total_keystrokes": self._total_keys,
            "total_clicks": self._total_clicks,
            "buffer_size": len(self._buffer),
            "current_app": self._current_app,
        }

    def run(self) -> None:
        """Main observer loop."""
        cfg = config.load_config()
        if not cfg.get("observer", {}).get("enabled", True):
            return

        kb_ok = self._start_keyboard_listener()
        mouse_ok = self._start_mouse_listener()

        last_flush = time.time()

        while not self._stop_event.is_set():
            try:
                # Update current app periodically
                self._current_app, self._current_window = self._get_frontmost_app()

                # Flush to disk periodically
                now = time.time()
                if now - last_flush > self._flush_interval:
                    self._flush_to_disk()
                    last_flush = now

                time.sleep(1)
            except Exception:
                time.sleep(5)

        # Final flush
        self._flush_to_disk()

        if self._keyboard_listener:
            self._keyboard_listener.stop()
        if self._mouse_listener:
            self._mouse_listener.stop()

    def stop(self) -> None:
        """Stop the observer."""
        self._stop_event.set()


# Global observer instance
_observer: Optional[DeepObserver] = None


def start_observer() -> DeepObserver:
    """Start the global observer."""
    global _observer
    if _observer is None or not _observer.is_alive():
        _observer = DeepObserver()
        _observer.start()
    return _observer


def get_observer() -> Optional[DeepObserver]:
    """Get the global observer instance."""
    return _observer


def stop_observer() -> None:
    """Stop the global observer."""
    global _observer
    if _observer:
        _observer.stop()
        _observer = None
