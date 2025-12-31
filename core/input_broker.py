"""Shared input broker to avoid multiple pynput listeners on macOS."""

from __future__ import annotations

import threading
from typing import Any, Callable, Dict, Optional

KeyboardCallback = Callable[[str, Any], None]
MouseCallback = Callable[..., None]


_SPECIAL_KEYS = {
    "ctrl": "<ctrl>",
    "ctrl_l": "<ctrl>",
    "ctrl_r": "<ctrl>",
    "shift": "<shift>",
    "shift_l": "<shift>",
    "shift_r": "<shift>",
    "alt": "<alt>",
    "alt_l": "<alt>",
    "alt_r": "<alt>",
    "option": "<alt>",
    "cmd": "<cmd>",
    "cmd_l": "<cmd>",
    "cmd_r": "<cmd>",
    "command": "<cmd>",
    "super": "<cmd>",
    "enter": "<enter>",
    "return": "<enter>",
    "space": "<space>",
    "tab": "<tab>",
    "esc": "<esc>",
    "escape": "<esc>",
    "backspace": "<backspace>",
    "up": "<up>",
    "down": "<down>",
    "left": "<left>",
    "right": "<right>",
}


def normalize_key(key: Any) -> str:
    """Normalize pynput key into a comparable token."""
    try:
        if hasattr(key, "char") and key.char:
            return str(key.char).lower()
        name = getattr(key, "name", "") or ""
    except Exception:
        name = ""
    name = name.lower()
    if name in _SPECIAL_KEYS:
        return _SPECIAL_KEYS[name]
    if name:
        return f"<{name}>"
    return ""


class InputBroker:
    """Singleton-style broker to multiplex keyboard/mouse events."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._keyboard_listener = None
        self._mouse_listener = None
        self._keyboard_subs: Dict[int, KeyboardCallback] = {}
        self._mouse_subs: Dict[int, MouseCallback] = {}
        self._next_id = 1

    def subscribe_keyboard(self, callback: KeyboardCallback) -> int:
        with self._lock:
            sub_id = self._next_id
            self._next_id += 1
            self._keyboard_subs[sub_id] = callback
        return sub_id

    def unsubscribe_keyboard(self, sub_id: int) -> None:
        with self._lock:
            self._keyboard_subs.pop(sub_id, None)

    def subscribe_mouse(self, callback: MouseCallback) -> int:
        with self._lock:
            sub_id = self._next_id
            self._next_id += 1
            self._mouse_subs[sub_id] = callback
        return sub_id

    def unsubscribe_mouse(self, sub_id: int) -> None:
        with self._lock:
            self._mouse_subs.pop(sub_id, None)

    def ensure_keyboard(self) -> bool:
        if self._keyboard_listener is not None:
            return True
        try:
            from pynput import keyboard
        except Exception:
            return False

        def _on_press(key):
            self._emit_keyboard("press", key)

        def _on_release(key):
            self._emit_keyboard("release", key)

        try:
            self._keyboard_listener = keyboard.Listener(
                on_press=_on_press,
                on_release=_on_release,
            )
            self._keyboard_listener.start()
            return True
        except Exception:
            self._keyboard_listener = None
            return False

    def ensure_mouse(self) -> bool:
        if self._mouse_listener is not None:
            return True
        try:
            from pynput import mouse
        except Exception:
            return False

        def _on_move(x, y):
            self._emit_mouse("move", x, y)

        def _on_click(x, y, button, pressed):
            self._emit_mouse("click", x, y, button, pressed)

        def _on_scroll(x, y, dx, dy):
            self._emit_mouse("scroll", x, y, dx, dy)

        try:
            self._mouse_listener = mouse.Listener(
                on_move=_on_move,
                on_click=_on_click,
                on_scroll=_on_scroll,
            )
            self._mouse_listener.start()
            return True
        except Exception:
            self._mouse_listener = None
            return False

    def stop(self) -> None:
        if self._keyboard_listener:
            try:
                self._keyboard_listener.stop()
            except Exception:
                pass
            self._keyboard_listener = None
        if self._mouse_listener:
            try:
                self._mouse_listener.stop()
            except Exception:
                pass
            self._mouse_listener = None

    def _emit_keyboard(self, event_type: str, key: Any) -> None:
        with self._lock:
            callbacks = list(self._keyboard_subs.values())
        for callback in callbacks:
            try:
                callback(event_type, key)
            except Exception:
                continue

    def _emit_mouse(self, event_type: str, *args: Any) -> None:
        with self._lock:
            callbacks = list(self._mouse_subs.values())
        for callback in callbacks:
            try:
                callback(event_type, *args)
            except Exception:
                continue


_INPUT_BROKER: Optional[InputBroker] = None


def get_input_broker() -> InputBroker:
    global _INPUT_BROKER
    if _INPUT_BROKER is None:
        _INPUT_BROKER = InputBroker()
    return _INPUT_BROKER
