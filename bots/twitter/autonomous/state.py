"""State/config helpers for the autonomous twitter engine."""

from __future__ import annotations

import os
from pathlib import Path


def load_env_file(env_path: Path) -> None:
    """Load dotenv-like key/value pairs from a local file."""
    if not env_path.exists():
        return

    for line in env_path.read_text(encoding="utf-8").splitlines():
        if line.strip() and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"'))


def get_duplicate_detection_hours(default: int = 48) -> int:
    """Read duplicate detection window with bounded fallback."""
    raw = os.getenv("X_DUPLICATE_DETECTION_HOURS", str(default)).strip()
    try:
        value = int(raw)
    except ValueError:
        value = default
    return max(1, min(value, 168))


def get_duplicate_similarity_threshold(default: float = 0.4) -> float:
    """Read duplicate similarity threshold with bounded fallback."""
    raw = os.getenv("X_DUPLICATE_SIMILARITY", str(default)).strip()
    try:
        value = float(raw)
    except ValueError:
        value = default
    return max(0.1, min(value, 0.95))
