"""Markdown layer synchronization for dual-layer memory architecture."""
import re
from datetime import datetime
from pathlib import Path
from typing import Optional, List

from .config import get_config


def get_daily_log_path(date: Optional[datetime] = None) -> Path:
    """
    Get path to daily log file.

    Args:
        date: Date for log. Defaults to UTC now.

    Returns:
        Path to daily log Markdown file.
    """
    if date is None:
        date = datetime.utcnow()

    config = get_config()
    filename = date.strftime("%Y-%m-%d.md")
    return config.daily_logs_dir / filename


def ensure_daily_log_exists(date: Optional[datetime] = None) -> Path:
    """
    Ensure daily log file exists, creating with header if needed.

    Args:
        date: Date for log. Defaults to UTC now.

    Returns:
        Path to daily log file.
    """
    if date is None:
        date = datetime.utcnow()

    log_path = get_daily_log_path(date)

    # Ensure directory exists
    log_path.parent.mkdir(parents=True, exist_ok=True)

    if not log_path.exists():
        header = f"""# Daily Log: {date.strftime("%Y-%m-%d")}

*Memory entries for {date.strftime("%A, %B %d, %Y")}*

---

"""
        log_path.write_text(header, encoding="utf-8")

    return log_path


def format_fact_entry(
    content: str,
    context: Optional[str] = None,
    source: Optional[str] = None,
    entities: Optional[List[str]] = None,
    confidence: float = 1.0,
    timestamp: Optional[datetime] = None,
) -> str:
    """
    Format a fact as a Markdown entry.

    Args:
        content: The fact content.
        context: Optional context/situation.
        source: Source system (telegram, treasury, etc.).
        entities: List of entity mentions.
        confidence: Confidence score (0.0-1.0).
        timestamp: Entry timestamp. Defaults to now.

    Returns:
        Formatted Markdown string.
    """
    if timestamp is None:
        timestamp = datetime.utcnow()

    lines = []

    # Header with timestamp
    lines.append(f"## {timestamp.strftime('%H:%M:%S UTC')}")
    lines.append("")

    # Content
    lines.append(content)
    lines.append("")

    # Metadata
    metadata_parts = []

    if source:
        metadata_parts.append(f"**Source:** {source}")

    if context:
        metadata_parts.append(f"**Context:** {context}")

    if entities:
        entity_str = ", ".join(f"`{e}`" for e in entities)
        metadata_parts.append(f"**Entities:** {entity_str}")

    if confidence < 1.0:
        metadata_parts.append(f"**Confidence:** {confidence:.2f}")

    if metadata_parts:
        lines.append(" | ".join(metadata_parts))
        lines.append("")

    lines.append("---")
    lines.append("")

    return "\n".join(lines)


def append_to_daily_log(
    content: str,
    context: Optional[str] = None,
    source: Optional[str] = None,
    entities: Optional[List[str]] = None,
    confidence: float = 1.0,
    date: Optional[datetime] = None,
) -> Path:
    """
    Append a fact to the daily log file.

    Creates the log file with header if it doesn't exist.

    Args:
        content: The fact content.
        context: Optional context.
        source: Source system.
        entities: Entity mentions.
        confidence: Confidence score.
        date: Date for log. Defaults to today.

    Returns:
        Path to the log file.
    """
    log_path = ensure_daily_log_exists(date)

    entry = format_fact_entry(
        content=content,
        context=context,
        source=source,
        entities=entities,
        confidence=confidence,
        timestamp=date or datetime.utcnow(),
    )

    # Append to file
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(entry)

    return log_path


def sync_fact_to_markdown(
    fact_id: int,
    content: str,
    context: Optional[str] = None,
    source: Optional[str] = None,
    entities: Optional[List[str]] = None,
    confidence: float = 1.0,
    timestamp: Optional[datetime] = None,
) -> Path:
    """
    Sync a stored fact to Markdown (for use after SQLite insert).

    This is the primary function called by retain_fact().

    Args:
        fact_id: SQLite fact ID (for reference).
        content: Fact content.
        context: Optional context.
        source: Source system.
        entities: Entity mentions.
        confidence: Confidence score.
        timestamp: Fact timestamp.

    Returns:
        Path to the log file where fact was written.
    """
    return append_to_daily_log(
        content=content,
        context=context,
        source=source,
        entities=entities,
        confidence=confidence,
        date=timestamp,
    )


def extract_entities_from_text(text: str) -> List[str]:
    """
    Extract entity mentions from text.

    Patterns:
    - @mentions (Twitter-style)
    - Token symbols (uppercase 3-6 chars)
    - Known platforms (bags.fm, Jupiter, etc.)

    Args:
        text: Text to extract entities from.

    Returns:
        List of entity names.
    """
    entities = set()

    # 1. @mentions
    mentions = re.findall(r"@(\w+)", text)
    entities.update(f"@{m}" for m in mentions)

    # 2. Token symbols (uppercase, 3-6 chars, not common words)
    common_words = {"THE", "AND", "FOR", "NOT", "BUT", "USD", "SOL", "ETH", "BTC"}
    tokens = re.findall(r"\b([A-Z]{3,6})\b", text)
    for token in tokens:
        if token not in common_words:
            entities.add(token)

    # 3. Known platforms
    platforms = ["bags.fm", "Jupiter", "Raydium", "Orca", "Telegram", "Twitter", "X"]
    text_lower = text.lower()
    for platform in platforms:
        if platform.lower() in text_lower:
            entities.add(platform)

    return list(entities)
