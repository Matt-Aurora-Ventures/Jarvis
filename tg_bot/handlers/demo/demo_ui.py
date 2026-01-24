"""
Demo Bot - UI Components Module

Contains:
- JarvisTheme: Beautiful emoji theme constants
- DemoMenuBuilder: Static methods for building Telegram menus
- safe_symbol: Token symbol sanitization

NOTE: This module re-exports from the main demo.py file.
The full UI implementation remains in demo.py for now due to its size (~4000 lines).
This module provides the modular interface for future refactoring.
"""

# Re-export UI components from the main demo module
# This allows gradual migration to the modular structure
from tg_bot.handlers.demo_legacy import (
    JarvisTheme,
    DemoMenuBuilder,
    safe_symbol,
    generate_price_chart,
    MATPLOTLIB_AVAILABLE,
)

__all__ = [
    "JarvisTheme",
    "DemoMenuBuilder",
    "safe_symbol",
    "generate_price_chart",
    "MATPLOTLIB_AVAILABLE",
]
