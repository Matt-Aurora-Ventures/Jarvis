"""Secret loading helpers.

Priority order:
1. `<NAME>_FILE` path (preferred)
2. `JARVIS_SECRETS_DIR/<NAME>` file
3. `<NAME>` environment variable
"""

from __future__ import annotations

import os
from pathlib import Path


def _read_secret_file(path: Path) -> str:
    if not path.exists() or not path.is_file():
        return ""
    try:
        return path.read_text(encoding="utf-8").strip()
    except Exception:
        return ""


def get_secret(name: str, default: str = "") -> str:
    file_env = os.environ.get(f"{name}_FILE", "").strip()
    if file_env:
        value = _read_secret_file(Path(file_env))
        if value:
            return value

    secrets_dir = os.environ.get("JARVIS_SECRETS_DIR", "").strip()
    if secrets_dir:
        value = _read_secret_file(Path(secrets_dir) / name)
        if value:
            return value

    value = os.environ.get(name, "").strip()
    if value:
        return value
    return default

