"""
Cross-platform observation utilities for LifeOS.
"""

import threading
import time
from dataclasses import dataclass
from typing import Optional

from core import input_broker


def frontmost_app_window() -> tuple[str, str]:
    """Get the frontmost app and window title (cross-platform)."""
    try:
        from core.platform import get_active_window_info
        info = get_active_window_info()
        app_name = info.get("app_name", "")
        window = info.get("window", "")
        return app_name, window
    except Exception:
        return "", ""


def visible_apps(limit: int = 8) -> list[str]:
    """Get list of visible apps (cross-platform)."""
    try:
        from core.computer import get_window_list
        windows = get_window_list()
        apps = list(set(w.get("app", "") for w in windows if w.get("app")))
        return apps[:limit]
    except Exception:
        return []


def mouse_position() -> Optional[tuple[int, int]]:
    try:
        from pynput import mouse
    except Exception:
        return None
    try:
        controller = mouse.Controller()
        position = controller.position
        return int(position[0]), int(position[1])
    except Exception:
        return None


@dataclass
class MouseSummary:
    moves: int
    start: Optional[tuple[int, int]]
    end: Optional[tuple[int, int]]
    min_pos: Optional[tuple[int, int]]
    max_pos: Optional[tuple[int, int]]


class MouseTracker:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._moves = 0
        self._start: Optional[tuple[int, int]] = None
        self._end: Optional[tuple[int, int]] = None
        self._min_pos: Optional[tuple[int, int]] = None
        self._max_pos: Optional[tuple[int, int]] = None
        self._broker = input_broker.get_input_broker()
        self._subscription_id = None
        self._last_sample = 0.0

    def start(self) -> bool:
        if self._subscription_id is not None:
            return True

        def _on_move(event_type: str, *args) -> None:
            if event_type != "move":
                return
            x, y = args
            now = time.time()
            if now - self._last_sample < 0.05:
                return
            self._last_sample = now
            with self._lock:
                pos = (int(x), int(y))
                self._moves += 1
                if self._start is None:
                    self._start = pos
                self._end = pos
                if self._min_pos is None:
                    self._min_pos = pos
                else:
                    self._min_pos = (min(self._min_pos[0], pos[0]), min(self._min_pos[1], pos[1]))
                if self._max_pos is None:
                    self._max_pos = pos
                else:
                    self._max_pos = (max(self._max_pos[0], pos[0]), max(self._max_pos[1], pos[1]))

        self._subscription_id = self._broker.subscribe_mouse(_on_move)
        return self._broker.ensure_mouse()

    def stop(self) -> None:
        if self._subscription_id is not None:
            self._broker.unsubscribe_mouse(self._subscription_id)
            self._subscription_id = None

    def summary(self) -> MouseSummary:
        with self._lock:
            return MouseSummary(
                moves=self._moves,
                start=self._start,
                end=self._end,
                min_pos=self._min_pos,
                max_pos=self._max_pos,
            )


def format_snapshot(tracker: Optional[MouseTracker]) -> str:
    app, window = frontmost_app_window()
    apps = visible_apps()
    mouse_pos = mouse_position()
    parts = []
    if app:
        parts.append(f"Frontmost app: {app}")
    if window:
        parts.append(f"Frontmost window: {window}")
    if apps:
        parts.append(f"Visible apps: {', '.join(apps)}")
    if mouse_pos:
        parts.append(f"Mouse position: {mouse_pos[0]}, {mouse_pos[1]}")
    if tracker:
        summary = tracker.summary()
        if summary.moves:
            parts.append(
                "Mouse movement: "
                f"{summary.moves} moves, start={summary.start}, end={summary.end}, "
                f"box={summary.min_pos}..{summary.max_pos}"
            )
    if not parts:
        return "No screen context available."
    return " | ".join(parts)
