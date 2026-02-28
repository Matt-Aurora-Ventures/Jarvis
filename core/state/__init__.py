"""
State Machine Framework + Legacy Runtime State Helpers.

This package intentionally exposes both:
- conversation state machine primitives (`StateMachine`, `ConversationContext`, etc.)
- legacy runtime state helpers (`read_state`, `write_pid`, `LOGS_DIR`, etc.)

`core.state` previously pointed to a flat module with runtime helpers. A package
was later introduced for conversation state machine code. To keep backwards
compatibility for existing imports (`from core import state`), this module
re-exports both APIs.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, Optional

from core.state.context import ConversationContext
from core.state.handlers import HandlerRegistry, Response, StateHandler
from core.state.machine import StateError, StateMachine
from core.state.storage import InMemoryStorage, JSONFileStorage, RedisStorage, StateStorage

ROOT = Path(__file__).resolve().parents[2]
LOGS_DIR = ROOT / "lifeos" / "logs"
PID_PATH = LOGS_DIR / "lifeos.pid"
STATE_PATH = LOGS_DIR / "state.json"


def _ensure_logs_dir() -> None:
    LOGS_DIR.mkdir(parents=True, exist_ok=True)


def write_pid(pid: int) -> None:
    _ensure_logs_dir()
    PID_PATH.write_text(str(pid), encoding="utf-8")


def read_pid() -> Optional[int]:
    try:
        raw = PID_PATH.read_text(encoding="utf-8").strip()
        return int(raw)
    except (FileNotFoundError, ValueError):
        return None


def clear_pid() -> None:
    try:
        PID_PATH.unlink()
    except FileNotFoundError:
        pass


def _is_process_alive(pid: int) -> bool:
    """Check if a process with given PID is alive. Cross-platform."""
    import sys

    if sys.platform == "win32":
        try:
            import psutil

            return psutil.pid_exists(pid)
        except ImportError:
            pass

        try:
            import ctypes

            kernel32 = ctypes.windll.kernel32
            process_query_limited_information = 0x1000
            handle = kernel32.OpenProcess(process_query_limited_information, False, pid)
            if handle:
                kernel32.CloseHandle(handle)
                return True
            return False
        except Exception:
            return False

    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False


def is_running() -> bool:
    pid = read_pid()
    if not pid:
        return False
    if _is_process_alive(pid):
        return True
    clear_pid()
    return False


def read_state() -> Dict[str, Any]:
    try:
        with open(STATE_PATH, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        if isinstance(data, dict):
            return data
        return {}
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def write_state(state: Dict[str, Any]) -> None:
    _ensure_logs_dir()
    with open(STATE_PATH, "w", encoding="utf-8") as handle:
        json.dump(state, handle, indent=2, sort_keys=True)


def update_state(**updates: Any) -> Dict[str, Any]:
    current = read_state()
    current.update(updates)
    write_state(current)
    return current


__all__ = [
    # State machine exports
    "StateMachine",
    "StateError",
    "ConversationContext",
    "StateStorage",
    "InMemoryStorage",
    "JSONFileStorage",
    "RedisStorage",
    "StateHandler",
    "Response",
    "HandlerRegistry",
    # Legacy runtime state exports
    "ROOT",
    "LOGS_DIR",
    "PID_PATH",
    "STATE_PATH",
    "write_pid",
    "read_pid",
    "clear_pid",
    "is_running",
    "read_state",
    "write_state",
    "update_state",
]
