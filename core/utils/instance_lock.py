"""
Simple cross-platform file lock for single-instance polling.

Enhanced with stale PID detection to handle:
- Crashed processes that left lock files behind
- Zombie processes that shouldn't hold locks
- Supervisor-level lock acquisition for subprocess coordination
"""

from __future__ import annotations

import hashlib
import logging
import os
import time
from pathlib import Path
from typing import Optional, TextIO

import psutil

logger = logging.getLogger(__name__)


def is_pid_alive(pid: int) -> bool:
    """
    Check if a process with given PID exists and is not a zombie.

    Args:
        pid: Process ID to check

    Returns:
        True if process exists and is running (not zombie), False otherwise
    """
    if not psutil.pid_exists(pid):
        return False
    try:
        proc = psutil.Process(pid)
        return proc.status() != psutil.STATUS_ZOMBIE
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        return False


def cleanup_stale_lock(token: str, name: str) -> bool:
    """
    Check if lock file exists with a dead/zombie process and clean it up.

    Args:
        token: The token used for lock identification
        name: Lock name (e.g., "telegram_polling")

    Returns:
        True if stale lock was cleaned up, False if lock is valid or doesn't exist
    """
    lock_path = _lock_path(token, name)

    if not lock_path.exists():
        return False

    try:
        # Read PID from lock file
        with open(lock_path, "r") as f:
            content = f.read().strip()
            if not content:
                # Empty lock file - clean it up
                logger.info(f"Cleaning up empty lock file: {lock_path}")
                lock_path.unlink()
                return True

            pid = int(content)
    except (OSError, ValueError) as exc:
        # Can't read/parse lock file - try to clean it up
        logger.warning(f"Invalid lock file {lock_path}, cleaning up: {exc}")
        try:
            lock_path.unlink()
            return True
        except OSError:
            return False

    # Check if the PID is still alive
    if is_pid_alive(pid):
        logger.debug(f"Lock holder PID {pid} is still alive")
        return False

    # PID is dead or zombie - clean up the stale lock
    logger.info(f"Cleaning up stale lock file (PID {pid} is dead): {lock_path}")
    try:
        lock_path.unlink()
        return True
    except OSError as exc:
        logger.warning(f"Failed to clean up stale lock: {exc}")
        return False


def _default_lock_dir() -> Path:
    override = os.environ.get("JARVIS_LOCK_DIR")
    if override:
        return Path(override).expanduser()

    # Use a per-user global lock directory to prevent multi-clone conflicts
    if os.name == "nt":
        base = Path(os.environ.get("LOCALAPPDATA") or (Path.home() / "AppData" / "Local"))
        return base / "Jarvis" / "locks"

    base = Path(os.environ.get("XDG_STATE_HOME") or (Path.home() / ".local" / "state"))
    return base / "jarvis" / "locks"


def _token_digest(token: str) -> str:
    if not token:
        return "no-token"
    return hashlib.sha256(token.encode("utf-8")).hexdigest()[:12]


def _lock_path(token: str, name: str) -> Path:
    return _default_lock_dir() / f"{name}_{_token_digest(token)}.lock"


def _lock_file(handle: TextIO) -> None:
    if os.name == "nt":
        import msvcrt

        handle.seek(0)
        handle.write("0")
        handle.flush()
        handle.seek(0)
        msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
    else:
        import fcntl

        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)


def acquire_instance_lock(
    token: str,
    name: str,
    max_wait_seconds: int = 30,
    validate_pid: bool = True,
) -> Optional[TextIO]:
    """
    Acquire an exclusive lock file for a given token/name.

    Keep the returned file handle open for the lifetime of the process.
    Returns None if the lock cannot be acquired within max_wait_seconds.

    Args:
        token: Unique token for lock identification (e.g., bot token)
        name: Lock name (e.g., "telegram_polling")
        max_wait_seconds: Maximum time to wait for lock acquisition
        validate_pid: If True, validates that any existing lock holder is still alive
                      and cleans up stale locks from crashed processes (default: True)
    """
    lock_dir = _default_lock_dir()
    lock_dir.mkdir(parents=True, exist_ok=True)
    lock_path = _lock_path(token, name)

    # Clean up stale locks before attempting acquisition
    if validate_pid:
        if cleanup_stale_lock(token, name):
            logger.info(f"Cleaned up stale lock, proceeding with acquisition")

    try:
        handle = open(lock_path, "a+")
    except OSError as exc:
        logger.warning("Failed to open lock file %s: %s", lock_path, exc)
        return None

    start = time.time()
    while True:
        try:
            _lock_file(handle)
            handle.seek(0)
            handle.truncate()
            handle.write(str(os.getpid()))
            handle.flush()
            return handle
        except Exception as exc:
            waited = int(time.time() - start)

            # On each retry, check if the lock holder died (if validate_pid enabled)
            if validate_pid and waited > 0 and waited % 3 == 0:
                if cleanup_stale_lock(token, name):
                    logger.info(f"Lock holder died during wait, retrying acquisition")
                    continue

            if waited >= max_wait_seconds:
                logger.warning(
                    "Could not acquire lock %s after %ss: %s",
                    lock_path,
                    max_wait_seconds,
                    exc,
                )
                try:
                    handle.close()
                except Exception:
                    pass
                return None

            if waited == 0 or waited % 5 == 0:
                logger.info(
                    "Waiting for lock %s (%ss/%ss)",
                    lock_path,
                    waited,
                    max_wait_seconds,
                )
            time.sleep(1)
