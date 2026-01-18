"""
Quick Buttons UI Component.

Provides emoji-based quick action buttons that appear below messages.
"""

import logging
from typing import List, Optional

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

logger = logging.getLogger(__name__)


# Emoji to command mappings
QUICK_ACTIONS = {
    "stats": {"emoji": "\U0001f4ca", "command": "/stats", "label": "Stats"},
    "analyze": {"emoji": "\U0001f3af", "command": "/analyze", "label": "Analyze"},
    "positions": {"emoji": "\U0001f4b0", "command": "/positions", "label": "Positions"},
    "leaderboard": {"emoji": "\U0001f3c6", "command": "/leaderboard", "label": "Leaders"},
    "help": {"emoji": "\U0001f4f1", "command": "/help", "label": "Help"},
    "watchlist": {"emoji": "\u2b50", "command": "/watchlist", "label": "Watchlist"},
    "trending": {"emoji": "\U0001f525", "command": "/trending", "label": "Trending"},
    "dashboard": {"emoji": "\U0001f4c8", "command": "/dashboard", "label": "Dashboard"},
}


class QuickButtons:
    """
    Build emoji-based quick action buttons.

    These buttons provide fast access to common commands.
    """

    def __init__(self, buttons_per_row: int = 4):
        """
        Initialize QuickButtons.

        Args:
            buttons_per_row: Number of buttons per row (default 4)
        """
        self.buttons_per_row = buttons_per_row

    def build_quick_actions(
        self,
        actions: Optional[List[str]] = None,
        compact: bool = False,
    ) -> InlineKeyboardMarkup:
        """
        Build a quick actions keyboard.

        Args:
            actions: List of action keys to include (default: all)
            compact: If True, show only emoji (no labels)

        Returns:
            InlineKeyboardMarkup with quick action buttons
        """
        if actions is None:
            actions = ["stats", "analyze", "positions", "watchlist"]

        buttons = []
        for action_key in actions:
            action = QUICK_ACTIONS.get(action_key)
            if not action:
                continue

            label = action["emoji"] if compact else f"{action['emoji']} {action['label']}"
            callback_data = f"quick_{action_key}"

            buttons.append(
                InlineKeyboardButton(label, callback_data=callback_data)
            )

        # Arrange into rows
        keyboard = []
        for i in range(0, len(buttons), self.buttons_per_row):
            keyboard.append(buttons[i:i + self.buttons_per_row])

        return InlineKeyboardMarkup(keyboard)

    def build_default_footer(self, compact: bool = True) -> InlineKeyboardMarkup:
        """
        Build the default footer with most common actions.

        Args:
            compact: If True, show only emoji

        Returns:
            InlineKeyboardMarkup with footer buttons
        """
        return self.build_quick_actions(
            actions=["stats", "analyze", "positions", "help"],
            compact=compact,
        )

    def build_analysis_footer(
        self,
        token_address: str,
        compact: bool = True,
    ) -> InlineKeyboardMarkup:
        """
        Build footer for analysis views with token-specific actions.

        Args:
            token_address: Token address for contextual actions
            compact: If True, show only emoji

        Returns:
            InlineKeyboardMarkup with analysis footer buttons
        """
        buttons = [
            InlineKeyboardButton(
                "\U0001f4ca" if compact else "\U0001f4ca Chart",
                callback_data=f"analyze_chart:{token_address}"
            ),
            InlineKeyboardButton(
                "\U0001f6e1\ufe0f" if compact else "\U0001f6e1\ufe0f Risk",
                callback_data=f"analyze_risk:{token_address}"
            ),
            InlineKeyboardButton(
                "\u2b50" if compact else "\u2b50 Watch",
                callback_data=f"watch_add:{token_address}"
            ),
            InlineKeyboardButton(
                "\u2716\ufe0f" if compact else "\u2716\ufe0f Close",
                callback_data=f"ui_close:{token_address}"
            ),
        ]

        return InlineKeyboardMarkup([buttons])

    def build_trading_footer(
        self,
        token_address: str,
        compact: bool = True,
    ) -> InlineKeyboardMarkup:
        """
        Build footer for trading views.

        Args:
            token_address: Token address for trading actions
            compact: If True, show only emoji

        Returns:
            InlineKeyboardMarkup with trading footer buttons
        """
        buttons = [
            InlineKeyboardButton(
                "\U0001f4b0" if compact else "\U0001f4b0 Buy",
                callback_data=f"trade_buy:{token_address}"
            ),
            InlineKeyboardButton(
                "\U0001f4b8" if compact else "\U0001f4b8 Sell",
                callback_data=f"trade_sell:{token_address}"
            ),
            InlineKeyboardButton(
                "\U0001f4ca" if compact else "\U0001f4ca Analyze",
                callback_data=f"analyze_{token_address}"
            ),
            InlineKeyboardButton(
                "\u2716\ufe0f" if compact else "\u2716\ufe0f Close",
                callback_data="ui_close"
            ),
        ]

        return InlineKeyboardMarkup([buttons])


async def handle_quick_callback(query, context):
    """
    Handle quick action button callbacks.

    Callback format: quick_<action>
    """
    try:
        await query.answer()
    except Exception:
        pass

    data = query.data
    action = data.replace("quick_", "")

    action_info = QUICK_ACTIONS.get(action)
    if not action_info:
        return

    # Simulate command execution by sending the command
    command = action_info["command"]
    user = query.from_user
    chat = query.message.chat

    # Build command message text
    message_text = f"_Executing {command}..._"

    await query.message.reply_text(
        message_text,
        parse_mode="Markdown"
    )

    # The actual command will be handled by the existing command handlers
    # This callback just provides a UI indication


# Singleton instance
_quick_buttons: Optional[QuickButtons] = None


def get_quick_buttons() -> QuickButtons:
    """Get the global QuickButtons instance."""
    global _quick_buttons
    if _quick_buttons is None:
        _quick_buttons = QuickButtons()
    return _quick_buttons


__all__ = [
    "QuickButtons",
    "get_quick_buttons",
    "handle_quick_callback",
    "QUICK_ACTIONS",
]
