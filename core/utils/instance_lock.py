"""
Simple cross-platform file lock for single-instance polling.
"""

from __future__ import annotations

import hashlib
import logging
import os
import time
from pathlib import Path
from typing import Optional, TextIO

logger = logging.getLogger(__name__)


def _default_lock_dir() -> Path:
    root = Path(__file__).resolve().parents[2]
    return root / "data" / "locks"


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
) -> Optional[TextIO]:
    """
    Acquire an exclusive lock file for a given token/name.

    Keep the returned file handle open for the lifetime of the process.
    Returns None if the lock cannot be acquired within max_wait_seconds.
    """
    lock_dir = _default_lock_dir()
    lock_dir.mkdir(parents=True, exist_ok=True)
    lock_path = _lock_path(token, name)

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
