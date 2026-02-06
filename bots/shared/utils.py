"""
Shared Utilities for ClawdBots.

Common helper functions used across all bots.
"""

import hashlib
import logging
import os
import re
import time
from datetime import datetime, timedelta
from typing import Any, Optional

logger = logging.getLogger(__name__)


def truncate(text: str, max_len: int = 4000, suffix: str = "...") -> str:
    """Truncate text to max length (Telegram limit is 4096)."""
    if len(text) <= max_len:
        return text
    return text[: max_len - len(suffix)] + suffix


def escape_markdown(text: str) -> str:
    """Escape Telegram MarkdownV2 special characters."""
    special = r"_*[]()~`>#+-=|{}.!"
    return re.sub(f"([{re.escape(special)}])", r"\\\1", text)


def format_sol(amount: float, decimals: int = 4) -> str:
    """Format SOL amount for display."""
    return f"{amount:.{decimals}f} SOL"


def format_usd(amount: float) -> str:
    """Format USD amount."""
    if abs(amount) >= 1000:
        return f"${amount:,.2f}"
    return f"${amount:.2f}"


def format_pct(value: float) -> str:
    """Format percentage with sign."""
    sign = "+" if value > 0 else ""
    return f"{sign}{value:.1f}%"


def format_duration(seconds: float) -> str:
    """Human-readable duration."""
    if seconds < 60:
        return f"{seconds:.0f}s"
    elif seconds < 3600:
        return f"{seconds / 60:.0f}m"
    elif seconds < 86400:
        return f"{seconds / 3600:.1f}h"
    else:
        return f"{seconds / 86400:.1f}d"


def time_ago(dt: datetime) -> str:
    """Human-readable time ago string."""
    diff = datetime.utcnow() - dt
    seconds = diff.total_seconds()
    if seconds < 60:
        return "just now"
    elif seconds < 3600:
        return f"{int(seconds / 60)}m ago"
    elif seconds < 86400:
        return f"{int(seconds / 3600)}h ago"
    else:
        return f"{int(seconds / 86400)}d ago"


def short_hash(text: str, length: int = 8) -> str:
    """Generate a short hash for deduplication."""
    return hashlib.sha256(text.encode()).hexdigest()[:length]


def safe_int(value: Any, default: int = 0) -> int:
    """Safely convert to int."""
    try:
        return int(value)
    except (ValueError, TypeError):
        return default


def safe_float(value: Any, default: float = 0.0) -> float:
    """Safely convert to float."""
    try:
        return float(value)
    except (ValueError, TypeError):
        return default


def get_bot_name() -> str:
    """Get current bot name from environment."""
    return os.environ.get("CLAWDBOT_NAME", "unknown")


def is_founder(user_id: int) -> bool:
    """Check if user is the founder."""
    return user_id == 8527130908


def retry(func, retries: int = 3, delay: float = 1.0, backoff: float = 2.0):
    """Simple sync retry wrapper."""
    last_exc = None
    for i in range(retries):
        try:
            return func()
        except Exception as e:
            last_exc = e
            if i < retries - 1:
                time.sleep(delay * (backoff ** i))
    raise last_exc


def chunk_list(lst: list, size: int) -> list:
    """Split a list into chunks of given size."""
    return [lst[i : i + size] for i in range(0, len(lst), size)]


def sanitize_input(text: str, max_len: int = 1000) -> str:
    """Basic input sanitization - strip control chars and limit length."""
    # Remove control characters except newline/tab
    cleaned = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)
    return cleaned[:max_len].strip()
