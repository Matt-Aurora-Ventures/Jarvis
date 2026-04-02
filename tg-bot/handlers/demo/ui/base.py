"""
Demo Bot - Base UI Utilities

Contains shared utilities for all menu builders:
- Text escaping for Telegram Markdown
- Symbol sanitization
- Keyboard building helpers
"""

from typing import List, Tuple, Optional
from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def escape_md(text: str) -> str:
    """
    Escape special characters for Telegram MarkdownV1.

    Characters escaped: _ * [ ] ( ) ~ ` > # + - = | { } . !
    """
    if not text:
        return ""
    # For MarkdownV1, we mainly need to escape: _ * ` [
    special_chars = ['_', '*', '`', '[']
    result = str(text)
    for char in special_chars:
        result = result.replace(char, f'\\{char}')
    return result


def safe_symbol(symbol: str) -> str:
    """
    Sanitize token symbol for safe display in Telegram messages.

    Removes special characters that could break Telegram Markdown formatting
    or cause display issues. Only allows alphanumeric, hyphen, and underscore.

    Args:
        symbol: Raw token symbol (may contain special chars)

    Returns:
        Sanitized symbol, uppercase, max 10 chars. Returns "UNKNOWN" if empty.
    """
    if not symbol:
        return "UNKNOWN"
    # Keep only alphanumeric, hyphen, and underscore
    sanitized = ''.join(c for c in str(symbol) if c.isalnum() or c in ['_', '-'])
    # Truncate to 10 chars and uppercase
    return sanitized[:10].upper() if sanitized else "UNKNOWN"


def build_keyboard(
    rows: List[List[Tuple[str, str]]],
) -> InlineKeyboardMarkup:
    """
    Build an InlineKeyboardMarkup from a list of button rows.

    Args:
        rows: List of rows, where each row is a list of (text, callback_data) tuples

    Returns:
        InlineKeyboardMarkup ready for use in Telegram messages
    """
    keyboard = []
    for row in rows:
        keyboard.append([
            InlineKeyboardButton(text=text, callback_data=callback)
            for text, callback in row
        ])
    return InlineKeyboardMarkup(keyboard)


def back_button(callback: str = "demo:main") -> InlineKeyboardButton:
    """Create a standard back button."""
    return InlineKeyboardButton("◀️ Back", callback_data=callback)


def close_button() -> InlineKeyboardButton:
    """Create a standard close button."""
    return InlineKeyboardButton("✖️ Close", callback_data="demo:close")


def refresh_button(callback: str = "demo:refresh") -> InlineKeyboardButton:
    """Create a standard refresh button."""
    return InlineKeyboardButton("🔄 Refresh", callback_data=callback)


def format_usd(value: float, include_sign: bool = False) -> str:
    """Format a USD value with proper formatting."""
    if include_sign:
        sign = "+" if value >= 0 else ""
        return f"{sign}${abs(value):,.2f}"
    return f"${value:,.2f}"


def format_sol(value: float, decimals: int = 4) -> str:
    """Format a SOL value with proper formatting."""
    return f"◎{value:,.{decimals}f}"


def format_pnl_pct(pnl: float) -> str:
    """Format a PnL percentage with sign and emoji."""
    sign = "+" if pnl >= 0 else ""
    emoji = "📈" if pnl >= 0 else "📉"
    return f"{emoji} {sign}{pnl:.1f}%"


def format_address(address: str, chars: int = 4) -> str:
    """Format a wallet/token address for display."""
    if not address or len(address) < chars * 2 + 3:
        return address or "N/A"
    return f"{address[:chars]}...{address[-chars:]}"


def chunks(lst: List, n: int) -> List[List]:
    """Split a list into chunks of size n."""
    return [lst[i:i + n] for i in range(0, len(lst), n)]


__all__ = [
    "escape_md",
    "safe_symbol",
    "build_keyboard",
    "back_button",
    "close_button",
    "refresh_button",
    "format_usd",
    "format_sol",
    "format_pnl_pct",
    "format_address",
    "chunks",
]
