"""
Passive observation module for LifeOS.
Tracks keyboard activity, app switches, idle time, and screen context.
Designed to be lightweight and privacy-respecting (no keylogging, just activity levels).
"""

import json
import subprocess
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from core import config, state

ROOT = Path(__file__).resolve().parents[1]
ACTIVITY_LOG_PATH = ROOT / "data" / "activity_logs"


@dataclass
class KeyboardSummary:
    keystrokes: int = 0
    words_typed: int = 0
    backspaces: int = 0
    enters: int = 0
    last_activity: float = 0.0


@dataclass
class AppSwitch:
    timestamp: float
    from_app: str
    to_app: str
    to_window: str


@dataclass
class FocusSession:
    app: str
    window: str
    start_time: float
    end_time: float = 0.0
    keystrokes: int = 0
    mouse_moves: int = 0

    def duration_seconds(self) -> float:
        end = self.end_time or time.time()
        return end - self.start_time


@dataclass
class ActivitySnapshot:
    timestamp: float
    frontmost_app: str
    frontmost_window: str
    visible_apps: List[str]
    keyboard: KeyboardSummary
    idle_seconds: float
    focus_sessions: List[FocusSession]


class KeyboardTracker:
    """Tracks keyboard activity without logging actual keys (privacy-first)."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._keystrokes = 0
        self._words = 0
        self._backspaces = 0
        self._enters = 0
        self._last_activity = 0.0
        self._listener = None
        self._word_buffer = 0

    def start(self) -> bool:
        try:
            from pynput import keyboard
        except Exception:
            return False

        def _on_press(key) -> None:
            now = time.time()
            with self._lock:
                self._keystrokes += 1
                self._last_activity = now

                try:
                    if hasattr(key, 'char') and key.char:
                        if key.char == ' ':
                            if self._word_buffer > 0:
                                self._words += 1
                                self._word_buffer = 0
                        else:
                            self._word_buffer += 1
                    elif hasattr(key, 'name'):
                        if key.name == 'backspace':
                            self._backspaces += 1
                        elif key.name in ('enter', 'return'):
                            self._enters += 1
                            if self._word_buffer > 0:
                                self._words += 1
                                self._word_buffer = 0
                except Exception:
                    pass

        try:
            self._listener = keyboard.Listener(on_press=_on_press)
            self._listener.start()
            return True
        except Exception:
            return False

    def stop(self) -> None:
        if self._listener:
            try:
                self._listener.stop()
            except Exception:
                pass

    def summary(self) -> KeyboardSummary:
        with self._lock:
            return KeyboardSummary(
                keystrokes=self._keystrokes,
                words_typed=self._words,
                backspaces=self._backspaces,
                enters=self._enters,
                last_activity=self._last_activity,
            )

    def reset(self) -> KeyboardSummary:
        with self._lock:
            summary = KeyboardSummary(
                keystrokes=self._keystrokes,
                words_typed=self._words,
                backspaces=self._backspaces,
                enters=self._enters,
                last_activity=self._last_activity,
            )
            self._keystrokes = 0
            self._words = 0
            self._backspaces = 0
            self._enters = 0
            self._word_buffer = 0
            return summary


class IdleDetector:
    """Detects user idle time based on keyboard and mouse activity."""

    def __init__(self) -> None:
        self._last_keyboard = 0.0
        self._last_mouse = 0.0

    def update_keyboard(self, timestamp: float) -> None:
        self._last_keyboard = max(self._last_keyboard, timestamp)

    def update_mouse(self, timestamp: float) -> None:
        self._last_mouse = max(self._last_mouse, timestamp)

    def idle_seconds(self) -> float:
        last_activity = max(self._last_keyboard, self._last_mouse)
        if last_activity == 0:
            return 0.0
        return time.time() - last_activity


class AppSwitchTracker:
    """Tracks app switches and focus sessions."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._current_app = ""
        self._current_window = ""
        self._switches: List[AppSwitch] = []
        self._sessions: List[FocusSession] = []
        self._current_session: Optional[FocusSession] = None

    def update(self, app: str, window: str, keystrokes: int = 0, mouse_moves: int = 0) -> Optional[AppSwitch]:
        now = time.time()
        switch = None

        with self._lock:
            if app != self._current_app or window != self._current_window:
                if self._current_app:
                    switch = AppSwitch(
                        timestamp=now,
                        from_app=self._current_app,
                        to_app=app,
                        to_window=window,
                    )
                    self._switches.append(switch)

                if self._current_session:
                    self._current_session.end_time = now
                    self._sessions.append(self._current_session)

                self._current_session = FocusSession(
                    app=app,
                    window=window,
                    start_time=now,
                )
                self._current_app = app
                self._current_window = window

            if self._current_session:
                self._current_session.keystrokes += keystrokes
                self._current_session.mouse_moves += mouse_moves

        return switch

    def get_switches(self, since: float = 0) -> List[AppSwitch]:
        with self._lock:
            return [s for s in self._switches if s.timestamp > since]

    def get_sessions(self, since: float = 0) -> List[FocusSession]:
        with self._lock:
            sessions = [s for s in self._sessions if s.start_time > since]
            if self._current_session and self._current_session.start_time > since:
                current_copy = FocusSession(
                    app=self._current_session.app,
                    window=self._current_session.window,
                    start_time=self._current_session.start_time,
                    end_time=time.time(),
                    keystrokes=self._current_session.keystrokes,
                    mouse_moves=self._current_session.mouse_moves,
                )
                sessions.append(current_copy)
            return sessions

    def clear_old(self, before: float) -> None:
        with self._lock:
            self._switches = [s for s in self._switches if s.timestamp >= before]
            self._sessions = [s for s in self._sessions if s.start_time >= before]


def _run_osascript(script: str) -> str:
    try:
        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            text=True,
            check=False,
            timeout=2,
        )
        return (result.stdout or "").strip()
    except Exception:
        return ""


def get_frontmost_app() -> tuple[str, str]:
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


def get_visible_apps(limit: int = 8) -> List[str]:
    script = 'tell application "System Events" to get name of every process whose visible is true'
    raw = _run_osascript(script)
    if not raw:
        return []
    parts = [p.strip() for p in raw.split(",") if p.strip()]
    return parts[:limit]


def capture_screen_thumbnail(output_path: Path, max_size: int = 200) -> bool:
    """Capture a tiny thumbnail of the screen for context (very lightweight)."""
    try:
        temp_path = output_path.with_suffix(".tmp.png")
        result = subprocess.run(
            ["screencapture", "-x", "-t", "png", str(temp_path)],
            capture_output=True,
            check=False,
            timeout=5,
        )
        if result.returncode != 0 or not temp_path.exists():
            return False

        try:
            from PIL import Image
            img = Image.open(temp_path)
            img.thumbnail((max_size, max_size))
            img.save(output_path, "PNG", optimize=True)
            temp_path.unlink()
            return True
        except Exception:
            temp_path.rename(output_path)
            return True
    except Exception:
        return False


class PassiveObserver(threading.Thread):
    """
    Background thread that continuously observes user activity.
    Logs summaries periodically without being resource-intensive.
    """

    def __init__(
        self,
        log_interval_seconds: int = 60,
        on_context_update: Optional[Callable[[Dict[str, Any]], None]] = None,
    ) -> None:
        super().__init__(daemon=True)
        self._stop_event = threading.Event()
        self._log_interval = log_interval_seconds
        self._on_context_update = on_context_update

        self._keyboard_tracker = KeyboardTracker()
        self._idle_detector = IdleDetector()
        self._app_tracker = AppSwitchTracker()
        self._mouse_moves = 0
        self._mouse_listener = None

    def stop(self) -> None:
        self._stop_event.set()

    def _start_mouse_tracking(self) -> bool:
        try:
            from pynput import mouse
        except Exception:
            return False

        def _on_move(x, y) -> None:
            self._mouse_moves += 1
            self._idle_detector.update_mouse(time.time())

        try:
            self._mouse_listener = mouse.Listener(on_move=_on_move)
            self._mouse_listener.start()
            return True
        except Exception:
            return False

    def _stop_mouse_tracking(self) -> None:
        if self._mouse_listener:
            try:
                self._mouse_listener.stop()
            except Exception:
                pass

    def _save_activity_log(self, snapshot: ActivitySnapshot) -> None:
        ACTIVITY_LOG_PATH.mkdir(parents=True, exist_ok=True)
        date_str = datetime.fromtimestamp(snapshot.timestamp).strftime("%Y-%m-%d")
        log_file = ACTIVITY_LOG_PATH / f"{date_str}.jsonl"

        entry = {
            "ts": snapshot.timestamp,
            "app": snapshot.frontmost_app,
            "window": snapshot.frontmost_window[:100] if snapshot.frontmost_window else "",
            "visible": snapshot.visible_apps[:5],
            "keys": snapshot.keyboard.keystrokes,
            "words": snapshot.keyboard.words_typed,
            "idle_s": round(snapshot.idle_seconds, 1),
            "sessions": [
                {
                    "app": s.app,
                    "dur_s": round(s.duration_seconds(), 1),
                    "keys": s.keystrokes,
                }
                for s in snapshot.focus_sessions[-5:]
            ],
        }

        try:
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=True) + "\n")
        except Exception:
            pass

    def _build_context_summary(self, snapshot: ActivitySnapshot) -> str:
        """Build a text summary for context injection."""
        lines = []
        lines.append(f"Current: {snapshot.frontmost_app}")
        if snapshot.frontmost_window:
            lines.append(f"Window: {snapshot.frontmost_window[:60]}")
        if snapshot.keyboard.keystrokes > 0:
            lines.append(f"Activity: {snapshot.keyboard.keystrokes} keys, {snapshot.keyboard.words_typed} words")
        if snapshot.idle_seconds > 60:
            lines.append(f"Idle: {int(snapshot.idle_seconds)}s")

        recent_sessions = snapshot.focus_sessions[-3:]
        if recent_sessions:
            apps = [s.app for s in recent_sessions]
            lines.append(f"Recent apps: {', '.join(apps)}")

        return " | ".join(lines)

    def run(self) -> None:
        cfg = config.load_config()
        passive_cfg = cfg.get("passive", {})
        if not passive_cfg.get("enabled", True):
            state.update_state(passive_enabled=False)
            return

        keyboard_ok = self._keyboard_tracker.start()
        mouse_ok = self._start_mouse_tracking()

        state.update_state(
            passive_enabled=True,
            passive_keyboard=keyboard_ok,
            passive_mouse=mouse_ok,
        )

        last_log_time = time.time()
        session_start = time.time()

        while not self._stop_event.is_set():
            try:
                app, window = get_frontmost_app()
                kb_summary = self._keyboard_tracker.summary()

                if kb_summary.last_activity > 0:
                    self._idle_detector.update_keyboard(kb_summary.last_activity)

                mouse_delta = self._mouse_moves
                self._mouse_moves = 0

                self._app_tracker.update(app, window, kb_summary.keystrokes, mouse_delta)

                now = time.time()
                if now - last_log_time >= self._log_interval:
                    kb_reset = self._keyboard_tracker.reset()
                    sessions = self._app_tracker.get_sessions(since=last_log_time)
                    visible = get_visible_apps()

                    snapshot = ActivitySnapshot(
                        timestamp=now,
                        frontmost_app=app,
                        frontmost_window=window,
                        visible_apps=visible,
                        keyboard=kb_reset,
                        idle_seconds=self._idle_detector.idle_seconds(),
                        focus_sessions=sessions,
                    )

                    self._save_activity_log(snapshot)

                    context_summary = self._build_context_summary(snapshot)
                    state.update_state(
                        passive_last_update=now,
                        passive_context=context_summary,
                        passive_idle_seconds=round(snapshot.idle_seconds, 1),
                    )

                    if self._on_context_update:
                        self._on_context_update({
                            "snapshot": snapshot,
                            "summary": context_summary,
                        })

                    one_hour_ago = now - 3600
                    self._app_tracker.clear_old(one_hour_ago)
                    last_log_time = now

                time.sleep(1)

            except Exception:
                time.sleep(5)

        self._keyboard_tracker.stop()
        self._stop_mouse_tracking()
        state.update_state(passive_enabled=False)


def load_recent_activity(hours: int = 24) -> List[Dict[str, Any]]:
    """Load recent activity logs for context building."""
    entries = []
    cutoff = time.time() - (hours * 3600)

    if not ACTIVITY_LOG_PATH.exists():
        return entries

    for log_file in sorted(ACTIVITY_LOG_PATH.glob("*.jsonl"), reverse=True):
        try:
            with open(log_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entry = json.loads(line)
                        if entry.get("ts", 0) >= cutoff:
                            entries.append(entry)
                    except json.JSONDecodeError:
                        continue
        except Exception:
            continue

        if entries and entries[-1].get("ts", 0) < cutoff:
            break

    return sorted(entries, key=lambda x: x.get("ts", 0), reverse=True)


def summarize_activity(hours: int = 4) -> str:
    """Generate a text summary of recent activity for LLM context."""
    entries = load_recent_activity(hours=hours)
    if not entries:
        return "No recent activity recorded."

    app_time: Dict[str, float] = {}
    total_keys = 0
    total_words = 0

    for entry in entries:
        app = entry.get("app", "Unknown")
        sessions = entry.get("sessions", [])
        for s in sessions:
            app_name = s.get("app", app)
            dur = s.get("dur_s", 0)
            app_time[app_name] = app_time.get(app_name, 0) + dur
        total_keys += entry.get("keys", 0)
        total_words += entry.get("words", 0)

    sorted_apps = sorted(app_time.items(), key=lambda x: x[1], reverse=True)[:5]

    lines = [f"Activity Summary (last {hours}h):"]
    if sorted_apps:
        lines.append("Top apps by time:")
        for app, seconds in sorted_apps:
            minutes = int(seconds / 60)
            if minutes > 0:
                lines.append(f"  - {app}: {minutes}m")
    lines.append(f"Total: {total_keys} keystrokes, ~{total_words} words typed")

    return "\n".join(lines)
