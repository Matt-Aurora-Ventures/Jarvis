"""Shared utility helpers used across bots and tests."""

from __future__ import annotations

import json
import os
import re
import socket
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict
from urllib.parse import urlparse


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def format_duration(seconds: float) -> str:
    if seconds is None or seconds < 0:
        return "0s"
    total = int(seconds)
    days, rem = divmod(total, 86400)
    hours, rem = divmod(rem, 3600)
    minutes, secs = divmod(rem, 60)

    parts = []
    if days:
        parts.append(f"{days}d")
    if hours:
        parts.append(f"{hours}h")
    if minutes:
        parts.append(f"{minutes}m")
    if secs and days == 0:
        parts.append(f"{secs}s")
    if not parts:
        parts.append("0s")
    return " ".join(parts[:3])


def parse_time(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if not isinstance(value, str):
        return None

    text = value.strip()
    if not text:
        return None

    rel = re.fullmatch(r"(\d+)\s*([mhd])", text.lower())
    if rel:
        amount = int(rel.group(1))
        unit = rel.group(2)
        if unit == "m":
            return now_utc() + timedelta(minutes=amount)
        if unit == "h":
            return now_utc() + timedelta(hours=amount)
        return now_utc() + timedelta(days=amount)

    iso = text.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(iso)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed
    except ValueError:
        pass

    try:
        parsed_date = datetime.strptime(text, "%Y-%m-%d")
        return parsed_date.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def truncate(text: str | None, max_len: int = 4000) -> str:
    if text is None:
        return ""
    if len(text) <= max_len:
        return text
    return text[:max_len] + "..."


def escape_markdown(text: str | None) -> str:
    if text is None:
        return ""
    special = r"_*[]()~`>#+-=|{}.!"
    return re.sub(f"([{re.escape(special)}])", r"\\\1", text)


def extract_urls(text: str | None) -> list[str]:
    if not text:
        return []
    return re.findall(r"https?://[^\s]+", text)


def sanitize_filename(name: str | None, max_len: int = 255) -> str:
    if name is None:
        return ""
    cleaned = name.replace(" ", "_")
    cleaned = re.sub(r'[<>:"/\\|?*]', "", cleaned)
    return cleaned[:max_len]


def safe_json_loads(raw: str | None, default: Any = None) -> Any:
    if raw is None or raw == "":
        return default
    try:
        return json.loads(raw)
    except Exception:
        return default


def deep_merge(left: Dict[str, Any], right: Dict[str, Any]) -> Dict[str, Any]:
    merged: Dict[str, Any] = dict(left)
    for key, value in right.items():
        if (
            key in merged
            and isinstance(merged[key], dict)
            and isinstance(value, dict)
        ):
            merged[key] = deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def flatten_dict(payload: Dict[str, Any], parent_key: str = "", sep: str = ".") -> Dict[str, Any]:
    flat: Dict[str, Any] = {}
    for key, value in payload.items():
        composed = f"{parent_key}{sep}{key}" if parent_key else key
        if isinstance(value, dict):
            flat.update(flatten_dict(value, composed, sep=sep))
        else:
            flat[composed] = value
    return flat


def is_url_valid(url: str | None) -> bool:
    if not url:
        return False
    parsed = urlparse(url)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def get_ip_address() -> str:
    try:
        return socket.gethostbyname(socket.gethostname())
    except Exception:
        return "127.0.0.1"


def ensure_dir(path: str | os.PathLike[str]) -> str:
    Path(path).mkdir(parents=True, exist_ok=True)
    return str(path)


def atomic_write(path: str | os.PathLike[str], content: Any) -> None:
    path_obj = Path(path)
    path_obj.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=str(path_obj.parent),
        delete=False,
    ) as tmp:
        if isinstance(content, (dict, list)):
            json.dump(content, tmp, indent=2)
        else:
            tmp.write(str(content))
        temp_name = tmp.name
    os.replace(temp_name, path_obj)


def read_json_file(path: str | os.PathLike[str], default: Any = None) -> Any:
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return json.load(handle)
    except Exception:
        return default


# Backwards-compatible helpers retained for callers in this repo.
def format_sol(amount: float, decimals: int = 4) -> str:
    return f"{amount:.{decimals}f} SOL"


def format_usd(amount: float) -> str:
    if abs(amount) >= 1000:
        return f"${amount:,.2f}"
    return f"${amount:.2f}"


def format_pct(value: float) -> str:
    sign = "+" if value > 0 else ""
    return f"{sign}{value:.1f}%"


def short_hash(text: str, length: int = 8) -> str:
    import hashlib

    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:length]


def safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return default


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def get_bot_name() -> str:
    return os.environ.get("CLAWDBOT_NAME", "unknown")


def is_founder(user_id: int) -> bool:
    ids_str = (os.environ.get("TELEGRAM_ADMIN_IDS", "") or "").strip()
    if ids_str:
        for part in ids_str.split(","):
            part = part.strip()
            if part.isdigit() and int(part) == int(user_id):
                return True
        return False
    legacy = (os.environ.get("JARVIS_ADMIN_USER_ID", "") or "").strip()
    if legacy.isdigit():
        return int(legacy) == int(user_id)
    return int(user_id) in (8527368699, 8527130908)

