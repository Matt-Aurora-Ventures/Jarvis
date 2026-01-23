"""Identity helpers for stable IDs and hashing."""

from __future__ import annotations

import hashlib
import json
from typing import Any
import uuid


def new_id(prefix: str = "") -> str:
    value = uuid.uuid4().hex
    return f"{prefix}{value}" if prefix else value


def canonicalize(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str)


def content_hash(obj: Any) -> str:
    payload = canonicalize(obj).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()
