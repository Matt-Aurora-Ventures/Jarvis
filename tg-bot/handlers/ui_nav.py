"""
Small UI navigation helpers for Telegram inline-keyboard flows.

Design goal: every "page" (message with buttons) should offer a clear way back.
We map "Previous Menu" to the existing `menu_back` callback handler.
"""

from __future__ import annotations

from telegram import InlineKeyboardButton, InlineKeyboardMarkup


PREV_MENU_CALLBACK = "menu_back"


def prev_menu_button(label: str = "↩️ Previous Menu") -> InlineKeyboardButton:
    return InlineKeyboardButton(label, callback_data=PREV_MENU_CALLBACK)


def ensure_prev_menu(
    markup: InlineKeyboardMarkup | None,
    label: str = "↩️ Previous Menu",
) -> InlineKeyboardMarkup:
    """Append a single-row "Previous Menu" button unless already present."""
    if markup is None:
        return InlineKeyboardMarkup([[prev_menu_button(label)]])

    try:
        for row in (markup.inline_keyboard or []):
            for btn in (row or []):
                if getattr(btn, "callback_data", None) == PREV_MENU_CALLBACK:
                    return markup
    except Exception:
        # If the markup is unexpected, fall back to rebuilding below.
        pass

    rows = list(getattr(markup, "inline_keyboard", None) or [])
    rows.append([prev_menu_button(label)])
    return InlineKeyboardMarkup(rows)

