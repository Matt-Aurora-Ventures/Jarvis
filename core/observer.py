"""
Deep Observer module for LifeOS.
Observes keyboard input, mouse actions, and screen activity with privacy controls.
Lightweight, compressed logging. REDACTS sensitive input (passwords, credit cards).
"""

import gzip
import json
import random
import re
import threading
import time
from collections import deque
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Deque, Dict, List, Optional

from core import config, guardian, input_broker

ROOT = Path(__file__).resolve().parents[1]
OBSERVER_LOG_PATH = ROOT / "data" / "observer"


# Privacy: Apps where ALL keystrokes are ALWAYS sensitive (password managers, terminals)
ALWAYS_SENSITIVE_APPS = [
    "1Password", "LastPass", "Bitwarden", "KeePass", "Dashlane",
    "Terminal", "iTerm", "cmd.exe", "powershell.exe",  # Shell commands
    "Banking", "PayPal", "Venmo", "CashApp",  # Finance apps
    "Signal", "Telegram", "WhatsApp",  # Private messaging
]

# Privacy: Apps where sensitivity depends on window title (browsers)
CONTEXT_SENSITIVE_APPS = [
    "Chrome", "Firefox", "Safari", "Edge", "Brave", "Opera",
]

# Privacy: Window titles indicating sensitive input
SENSITIVE_WINDOW_PATTERNS = [
    r"password", r"login", r"sign in", r"authenticate",
    r"credit card", r"payment", r"billing",
    r"ssn", r"social security",
    r"private", r"confidential", r"secure",
]


class PrivacyFilter:
    """Detects sensitive input contexts and redacts accordingly."""

    def __init__(self, sensitive_apps: Optional[List[str]] = None):
        # Apps that are always sensitive
        self.always_sensitive = set(sensitive_apps or ALWAYS_SENSITIVE_APPS)
        # Apps that are context-sensitive (browsers)
        self.context_sensitive = set(CONTEXT_SENSITIVE_APPS)
        self.sensitive_patterns = [re.compile(p, re.IGNORECASE) for p in SENSITIVE_WINDOW_PATTERNS]

    def is_sensitive_context(self, app: str, window: str) -> bool:
        """Check if current context is sensitive (password field, banking app, etc.)."""
        # Check always-sensitive app blocklist (password managers, terminals, etc.)
        if any(sensitive in app for sensitive in self.always_sensitive):
            return True

        # For browsers: only sensitive if window title matches a pattern
        is_browser = any(browser in app for browser in self.context_sensitive)
        if is_browser:
            # Browsers are only sensitive in specific contexts (login, payment, etc.)
            if window:
                for pattern in self.sensitive_patterns:
                    if pattern.search(window):
                        return True
            return False  # Browser with non-sensitive window

        # Check window title patterns for other apps
        if window:
            for pattern in self.sensitive_patterns:
                if pattern.search(window):
                    return True

        return False

    def redact_key(self, key: str, is_sensitive: bool) -> str:
        """Redact key if in sensitive context."""
        if not is_sensitive:
            return key

        # In sensitive contexts, only log key type, not actual value
        if key.startswith("["):
            return key  # Keep special keys like [enter], [tab]
        return "[REDACTED]"


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
        cfg = config.load_config()
        obs_cfg = cfg.get("observer", {})
        mode = str(obs_cfg.get("mode", "full")).lower()
        if mode == "lite":
            buffer_size = int(obs_cfg.get("buffer_size", 400))
            flush_interval = int(obs_cfg.get("flush_interval", 45))
        else:
            buffer_size = int(obs_cfg.get("buffer_size", buffer_size))
            flush_interval = int(obs_cfg.get("flush_interval", flush_interval))
        self._stop_event = threading.Event()
        self._lock = threading.Lock()

        # Rolling buffer for recent actions
        self._buffer: Deque[ActionLog] = deque(maxlen=buffer_size)
        self._flush_interval = flush_interval
        self._log_keys = bool(obs_cfg.get("log_keys", True))
        self._log_mouse = bool(obs_cfg.get("log_mouse", True))
        self._mouse_move_interval = float(obs_cfg.get("mouse_move_interval", 2))
        self._key_sample_rate = float(obs_cfg.get("key_sample_rate", 1.0))

        # Privacy controls
        sensitive_apps = obs_cfg.get("sensitive_apps", None)
        self._privacy_filter = PrivacyFilter(sensitive_apps)
        self._privacy_mode = str(obs_cfg.get("privacy_mode", "redact")).lower()  # redact, metadata, disabled

        # Input broker subscriptions
        self._broker = input_broker.get_input_broker()
        self._keyboard_subscription = None
        self._mouse_subscription = None

        # Current context
        self._current_app = ""
        self._current_window = ""

        # Stats
        self._total_keys = 0
        self._total_clicks = 0
        self._total_redacted = 0
        self._session_start = time.time()

    def _get_frontmost_app(self) -> tuple:
        """Get current app and window (cross-platform)."""
        try:
            from core.platform import get_active_window_info
            info = get_active_window_info()
            app_name = info.get("app_name", "")
            window = info.get("window", "")
            if app_name:
                return app_name, window
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
        """Start capturing keyboard input with privacy controls."""
        if not self._log_keys:
            return False

        def on_press(event_type, key):
            if event_type != "press":
                return
            if self._key_sample_rate < 1.0 and random.random() > self._key_sample_rate:
                return
            self._current_app, self._current_window = self._get_frontmost_app()

            # Privacy check
            is_sensitive = self._privacy_filter.is_sensitive_context(
                self._current_app, self._current_window
            )

            # Privacy mode: metadata - skip keystroke logging in sensitive contexts
            if self._privacy_mode == "metadata" and is_sensitive:
                return

            # Get key representation
            try:
                if hasattr(key, 'char') and key.char:
                    key_str = key.char
                else:
                    key_str = f"[{key.name}]" if hasattr(key, 'name') else "[?]"
            except Exception as e:
                key_str = "[?]"

            # Privacy mode: redact - replace actual characters with [REDACTED]
            if self._privacy_mode == "redact":
                original_key = key_str
                key_str = self._privacy_filter.redact_key(key_str, is_sensitive)
                if is_sensitive and original_key != key_str:
                    self._total_redacted += 1

            self._log_action("key", {
                "key": key_str,
                "app": self._current_app,
                "window": self._current_window[:80] if self._current_window else "",
                "sensitive": is_sensitive,  # Mark sensitive contexts
            })
            self._total_keys += 1

        self._keyboard_subscription = self._broker.subscribe_keyboard(on_press)
        return self._broker.ensure_keyboard()

    def _start_mouse_listener(self) -> bool:
        """Start capturing mouse actions."""
        if not self._log_mouse:
            return False

        last_move_log = [0.0]  # Track last move log time

        def on_mouse(event_type, *args):
            if event_type == "click":
                x, y, button, pressed = args
                if pressed:
                    self._log_action("click", {
                        "x": x, "y": y,
                        "button": str(button).split(".")[-1],
                        "app": self._current_app,
                    })
                    self._total_clicks += 1
                return

            if event_type == "scroll":
                x, y, dx, dy = args
                self._log_action("scroll", {
                    "x": x, "y": y,
                    "dx": dx, "dy": dy,
                })
                return

            if event_type != "move":
                return

            x, y = args
            # Only log moves every 2 seconds to stay lightweight
            now = time.time()
            if now - last_move_log[0] > self._mouse_move_interval:
                self._log_action("move", {"x": x, "y": y})
                last_move_log[0] = now

        self._mouse_subscription = self._broker.subscribe_mouse(on_mouse)
        return self._broker.ensure_mouse()

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
        except Exception as e:
            pass

    def get_recent_actions(self, seconds: int = 60) -> List[ActionLog]:
        """Get recent actions from buffer."""
        cutoff = time.time() - seconds
        with self._lock:
            return [a for a in self._buffer if a.ts > cutoff]

    def get_recent_text(self, seconds: int = 30, include_redacted: bool = False) -> str:
        """Reconstruct recently typed text (skips [REDACTED] by default)."""
        actions = self.get_recent_actions(seconds)
        chars = []
        for a in actions:
            if a.action_type == "key":
                key = a.data.get("key", "")

                # Skip redacted keys unless explicitly requested
                if key == "[REDACTED]" and not include_redacted:
                    chars.append("█")  # Visual indicator of redacted content
                    continue

                if key.startswith("["):
                    if key == "[space]":
                        chars.append(" ")
                    elif key == "[enter]" or key == "[return]":
                        chars.append("\n")
                    elif key == "[backspace]" and chars:
                        chars.pop()
                    # Skip other special keys
                else:
                    chars.append(key)
        return "".join(chars)

    def get_stats(self) -> Dict[str, Any]:
        """Get observation stats."""
        return {
            "session_duration": time.time() - self._session_start,
            "total_keystrokes": self._total_keys,
            "total_clicks": self._total_clicks,
            "total_redacted": self._total_redacted,
            "redaction_rate": self._total_redacted / max(self._total_keys, 1),
            "buffer_size": len(self._buffer),
            "current_app": self._current_app,
            "privacy_mode": self._privacy_mode,
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
            except Exception as e:
                time.sleep(5)

        # Final flush
        self._flush_to_disk()

        if self._keyboard_subscription is not None:
            self._broker.unsubscribe_keyboard(self._keyboard_subscription)
        if self._mouse_subscription is not None:
            self._broker.unsubscribe_mouse(self._mouse_subscription)

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
