"""
ResponseFormatter - Text formatting utilities.

Provides functions for formatting lists, tables, code blocks, and other
common text structures for Telegram and other platforms.

Example:
    from core.response.formatter import format_list, format_table, truncate_safely

    list_text = format_list(["Item 1", "Item 2", "Item 3"])
    table_text = format_table([{"name": "Alice", "age": 30}])
    truncated = truncate_safely("Very long text...", max_len=20)
"""

from __future__ import annotations

from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union


class Platform(Enum):
    """Supported output platforms."""
    PLAIN = "plain"
    TELEGRAM = "telegram"
    MARKDOWN = "markdown"
    HTML = "html"

    def __new__(cls, value: str) -> Platform:
        obj = object.__new__(cls)
        obj._value_ = value
        return obj


class ResponseFormatter:
    """
    Multi-platform response formatter.

    Handles text formatting for different output platforms (Telegram, plain text, etc.)
    with appropriate escaping and styling.
    """

    def __init__(self, default_platform: Union[Platform, str] = Platform.PLAIN) -> None:
        """
        Initialize formatter.

        Args:
            default_platform: Default output platform
        """
        if isinstance(default_platform, str):
            default_platform = Platform(default_platform.lower())
        self.default_platform = default_platform

    def format_text(
        self,
        text: Optional[str],
        platform: Optional[Platform] = None
    ) -> str:
        """
        Format text for the specified platform.

        Args:
            text: Text to format
            platform: Target platform (uses default if None)

        Returns:
            Formatted text string
        """
        if text is None:
            return ""

        platform = platform or self.default_platform
        return str(text)

    def format_error(
        self,
        error: Union[str, Exception, Dict[str, Any]],
        code: Optional[str] = None
    ) -> str:
        """
        Format an error for display.

        Args:
            error: Error message, exception, or error dict
            code: Optional error code

        Returns:
            Formatted error string
        """
        if isinstance(error, Exception):
            error_type = type(error).__name__
            message = str(error)
            return f"[X] {error_type}: {message}"
        elif isinstance(error, dict):
            code = error.get("code", code)
            message = error.get("message", str(error))
            if code:
                return f"[X] Error ({code}): {message}"
            return f"[X] Error: {message}"
        else:
            if code:
                return f"[X] Error ({code}): {error}"
            return f"[X] Error: {error}"

    def format_list(
        self,
        items: Sequence[str],
        numbered: bool = False,
        title: Optional[str] = None,
        platform: Optional[Platform] = None
    ) -> str:
        """
        Format a list of items.

        Args:
            items: Items to format
            numbered: Use numbered list instead of bullets
            title: Optional list title
            platform: Target platform

        Returns:
            Formatted list string
        """
        if not items:
            return ""

        lines = []
        if title:
            lines.append(f"*{title}*")

        for i, item in enumerate(items, 1):
            if numbered:
                lines.append(f"{i}. {item}")
            else:
                lines.append(f"- {item}")

        return "\n".join(lines)

    def format_table(
        self,
        data: List[Dict[str, Any]],
        headers: Optional[List[str]] = None,
        platform: Optional[Platform] = None
    ) -> str:
        """
        Format data as a table.

        Args:
            data: List of dictionaries with row data
            headers: Optional column headers
            platform: Target platform

        Returns:
            Formatted table string
        """
        if not data:
            return ""

        # Get headers from first row if not provided
        if headers is None:
            headers = list(data[0].keys())

        # Build rows
        lines = []

        # Header line
        lines.append(" | ".join(headers))
        lines.append("-" * len(lines[0]))

        # Data rows
        for row in data:
            values = [str(row.get(h, "")) for h in headers]
            lines.append(" | ".join(values))

        return "\n".join(lines)


# =============================================================================
# Standalone Functions
# =============================================================================

def format_list(
    items: Sequence[str],
    numbered: bool = False,
    bullet: str = "-",
    indent: int = 0
) -> str:
    """
    Format a list of items.

    Args:
        items: Items to format
        numbered: Use numbered list
        bullet: Bullet character for non-numbered lists
        indent: Number of leading spaces

    Returns:
        Formatted list string
    """
    if not items:
        return ""

    prefix = " " * indent
    lines = []

    for i, item in enumerate(items, 1):
        if numbered:
            lines.append(f"{prefix}{i}. {item}")
        else:
            lines.append(f"{prefix}{bullet} {item}")

    return "\n".join(lines)


def format_table(
    data: Union[List[Dict[str, Any]], List[Tuple]],
    headers: Optional[List[str]] = None,
    max_width: Optional[int] = None
) -> str:
    """
    Format data as a text table.

    Args:
        data: List of dicts or tuples
        headers: Column headers (required for tuple data)
        max_width: Maximum table width

    Returns:
        Formatted table string
    """
    if not data:
        return ""

    # Convert tuples to dicts if needed
    if isinstance(data[0], tuple):
        if headers is None:
            headers = [f"Col{i}" for i in range(len(data[0]))]
        data = [dict(zip(headers, row)) for row in data]

    # Get headers from data if not provided
    if headers is None:
        headers = list(data[0].keys())

    # Calculate column widths
    col_widths = {h: len(str(h)) for h in headers}
    for row in data:
        for h in headers:
            val_len = len(str(row.get(h, "")))
            col_widths[h] = max(col_widths[h], val_len)

    # Build table
    lines = []

    # Header
    header_line = " | ".join(str(h).ljust(col_widths[h]) for h in headers)
    lines.append(header_line)

    # Separator
    sep_line = "-+-".join("-" * col_widths[h] for h in headers)
    lines.append(sep_line)

    # Rows
    for row in data:
        row_line = " | ".join(str(row.get(h, "")).ljust(col_widths[h]) for h in headers)
        lines.append(row_line)

    return "\n".join(lines)


def format_code(
    code: str,
    block: bool = False,
    lang: Optional[str] = None
) -> str:
    """
    Format code with markdown.

    Args:
        code: Code content
        block: Use code block (triple backticks)
        lang: Language for syntax highlighting

    Returns:
        Formatted code string
    """
    if block:
        lang_spec = lang if lang else ""
        return f"```{lang_spec}\n{code}\n```"
    return f"`{code}`"


def truncate_safely(
    text: str,
    max_len: int,
    suffix: str = "..."
) -> str:
    """
    Truncate text to max length, respecting word boundaries.

    Args:
        text: Text to truncate
        max_len: Maximum length
        suffix: Suffix to append when truncated

    Returns:
        Truncated text
    """
    if len(text) <= max_len:
        return text

    # Account for suffix length
    target_len = max_len - len(suffix)
    if target_len <= 0:
        return text[:max_len]

    # Try to break at word boundary
    truncated = text[:target_len]
    last_space = truncated.rfind(" ")

    if last_space > target_len // 2:
        truncated = truncated[:last_space]

    return truncated + suffix


def format_number(
    value: Union[int, float],
    decimals: int = 2,
    thousands_sep: bool = True
) -> str:
    """
    Format a number with optional thousand separators.

    Args:
        value: Number to format
        decimals: Decimal places
        thousands_sep: Include thousand separators

    Returns:
        Formatted number string
    """
    if thousands_sep:
        if isinstance(value, int) or value == int(value):
            return f"{int(value):,}"
        return f"{value:,.{decimals}f}"
    else:
        if isinstance(value, int) or value == int(value):
            return str(int(value))
        return f"{value:.{decimals}f}"


def format_currency(
    value: float,
    currency: str = "USD",
    decimals: int = 2
) -> str:
    """
    Format a currency value.

    Args:
        value: Amount
        currency: Currency code (USD, SOL, etc.)
        decimals: Decimal places

    Returns:
        Formatted currency string
    """
    if currency.upper() == "USD":
        return f"${value:,.{decimals}f}"
    elif currency.upper() == "SOL":
        return f"{value:.{decimals}f} SOL"
    else:
        return f"{value:,.{decimals}f} {currency}"


def escape_markdown(text: str) -> str:
    """
    Escape markdown special characters.

    Args:
        text: Text to escape

    Returns:
        Escaped text
    """
    special_chars = ['*', '_', '`', '[', ']', '(', ')']
    for char in special_chars:
        text = text.replace(char, f'\\{char}')
    return text


def format_duration(seconds: Union[int, float]) -> str:
    """
    Format a duration in human-readable form.

    Args:
        seconds: Duration in seconds

    Returns:
        Formatted duration string
    """
    seconds = int(seconds)

    if seconds < 60:
        return f"{seconds}s"
    elif seconds < 3600:
        minutes = seconds // 60
        return f"{minutes}m"
    elif seconds < 86400:
        hours = seconds // 3600
        return f"{hours}h"
    else:
        days = seconds // 86400
        return f"{days}d"


def format_timestamp(
    dt: datetime,
    relative: bool = False,
    format_str: Optional[str] = None
) -> str:
    """
    Format a datetime.

    Args:
        dt: Datetime to format
        relative: Use relative time (e.g., "5 minutes ago")
        format_str: Custom strftime format

    Returns:
        Formatted timestamp string
    """
    if relative:
        now = datetime.now()
        diff = now - dt

        if diff.total_seconds() < 60:
            return f"{int(diff.total_seconds())}s ago"
        elif diff.total_seconds() < 3600:
            minutes = int(diff.total_seconds() / 60)
            return f"{minutes}m ago"
        elif diff.total_seconds() < 86400:
            hours = int(diff.total_seconds() / 3600)
            return f"{hours}h ago"
        else:
            days = int(diff.total_seconds() / 86400)
            return f"{days}d ago"

    if format_str:
        return dt.strftime(format_str)

    return dt.strftime("%Y-%m-%d %H:%M:%S")
