"""
Safe stdio initialization for daemonized processes.

Some environments (systemd, supervisors) can detach stdio streams.
When that happens, libraries that call .fileno() on stdin/stdout/stderr
can crash with: 'NoneType' object has no attribute 'fileno'.
"""

from __future__ import annotations

import os
import sys


def _replace_stream(name: str, mode: str) -> None:
    stream = getattr(sys, name, None)
    try:
        if stream is None or getattr(stream, "closed", False):
            raise RuntimeError("stream missing")
        # Ensure fileno exists and works
        stream.fileno()
        return
    except Exception:
        pass

    # Replace with a devnull-backed stream to satisfy .fileno()
    replacement = open(
        os.devnull,
        mode,
        buffering=1,
        encoding="utf-8",
        errors="replace",
    )
    setattr(sys, name, replacement)


def ensure_stdio() -> None:
    """Ensure sys.stdin/stdout/stderr are valid file-like objects with fileno()."""
    _replace_stream("stdin", "r")
    _replace_stream("stdout", "w")
    _replace_stream("stderr", "w")
