"""
Demo Bot - UI Components Package

Contains modular UI builders for the demo trading bot.

This is a transitional module that re-exports from demo_legacy.py
while providing proper module structure for future extraction.

Modules being built:
- theme: JarvisTheme emoji constants and indicators
- base: Base utilities (escape, keyboard builders)
"""

from tg_bot.handlers.demo.ui.theme import JarvisTheme
from tg_bot.handlers.demo.ui.base import (
    escape_md,
    safe_symbol,
    build_keyboard,
    back_button,
    close_button,
    refresh_button,
    format_usd,
    format_sol,
    format_pnl_pct,
    format_address,
    chunks,
)

# For backward compatibility, import DemoMenuBuilder from legacy
from tg_bot.handlers.demo_legacy import DemoMenuBuilder


__all__ = [
    "JarvisTheme",
    "DemoMenuBuilder",
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
