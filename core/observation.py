import subprocess
import threading
import time
from dataclasses import dataclass
from typing import Optional


def _run_osascript(script: str) -> str:
    try:
        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            text=True,
            check=False,
        )
        return (result.stdout or "").strip()
    except Exception:
        return ""


def frontmost_app_window() -> tuple[str, str]:
    script = (
        'tell application "System Events"\n'
        "set frontApp to name of first application process whose frontmost is true\n"
        "set frontWindow to \"\"\n"
        "tell process frontApp\n"
        "try\n"
        "set frontWindow to name of front window\n"
        "end try\n"
        "end tell\n"
        "end tell\n"
        "return frontApp & \"||\" & frontWindow\n"
    )
    raw = _run_osascript(script)
    if "||" in raw:
        app, window = raw.split("||", 1)
        return app.strip(), window.strip()
    return raw.strip(), ""


def visible_apps(limit: int = 8) -> list[str]:
    script = (
        'tell application "System Events" to get name of every process whose visible is true'
    )
    raw = _run_osascript(script)
    if not raw:
        return []
    parts = [part.strip() for part in raw.split(",") if part.strip()]
    return parts[:limit]


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
        self._listener = None
        self._last_sample = 0.0

    def start(self) -> bool:
        try:
            from pynput import mouse
        except Exception:
            return False

        def _on_move(x: int, y: int) -> None:
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

        try:
            self._listener = mouse.Listener(on_move=_on_move)
            self._listener.start()
        except Exception:
            return False
        return True

    def stop(self) -> None:
        if self._listener:
            try:
                self._listener.stop()
            except Exception:
                pass

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
