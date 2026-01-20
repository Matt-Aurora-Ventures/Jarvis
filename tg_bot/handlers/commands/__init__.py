"""Command handlers for Telegram bot.

This module re-exports original commands from commands_base.py and adds new
enhanced commands.
"""

# Re-export original commands (from tg_bot/handlers/commands_base.py)
# These are imported by tg_bot/bot.py
try:
    from tg_bot.handlers.commands_base import (
        start,
        help_command,
        status,
        subscribe,
        unsubscribe,
    )
except ImportError:
    # Fallback if commands_base doesn't exist yet
    start = None
    help_command = None
    status = None
    subscribe = None
    unsubscribe = None

# New enhanced commands
from tg_bot.handlers.commands.analyze_command import (
    analyze_command,
    handle_analyze_callback,
)
from tg_bot.handlers.commands.watchlist_command import (
    watchlist_command,
    handle_watchlist_callback,
)
from tg_bot.handlers.commands.quick_command import (
    quick_command,
    handle_quick_callback,
)

__all__ = [
    # Original commands
    "start",
    "help_command",
    "status",
    "subscribe",
    "unsubscribe",
    # New commands
    "analyze_command",
    "handle_analyze_callback",
    "watchlist_command",
    "handle_watchlist_callback",
    "quick_command",
    "handle_quick_callback",
]
