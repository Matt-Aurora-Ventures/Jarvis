"""
TelegramFormatter - Telegram-specific response formatting.

Handles formatting responses for Telegram, including message splitting
for long messages and inline keyboard attachment.

Example:
    formatter = TelegramFormatter()
    response = {"message": "Hello", "success": True}
    text = formatter.format_for_telegram(response)
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Union

from telegram import InlineKeyboardButton, InlineKeyboardMarkup


# Telegram message length limit
MAX_MESSAGE_LENGTH = 4096


class TelegramFormatter:
    """
    Telegram-specific response formatter.

    Handles:
    - Message formatting for Telegram parse modes
    - Long message splitting
    - Inline keyboard creation
    """

    def __init__(self, parse_mode: str = "Markdown") -> None:
        """
        Initialize formatter.

        Args:
            parse_mode: Telegram parse mode (Markdown, MarkdownV2, HTML)
        """
        self.parse_mode = parse_mode

    def format_for_telegram(
        self,
        response: Union[Dict[str, Any], str]
    ) -> str:
        """
        Format a response for Telegram.

        Args:
            response: Response dict or string

        Returns:
            Formatted string for Telegram
        """
        if isinstance(response, str):
            return response

        # Extract message from response dict
        message = response.get("message", "")

        # Add success/error indicators
        if response.get("success"):
            return f"[OK] {message}"
        elif response.get("error"):
            error = response.get("error", "")
            return f"[X] Error: {error}\n{message}"

        return message

    def format_error(self, error: Union[str, Exception]) -> str:
        """
        Format an error message.

        Args:
            error: Error string or exception

        Returns:
            Formatted error string
        """
        if isinstance(error, Exception):
            return f"[X] {type(error).__name__}: {str(error)}"
        return f"[X] Error: {error}"

    def format_success(self, message: str) -> str:
        """
        Format a success message.

        Args:
            message: Success message

        Returns:
            Formatted success string
        """
        return f"[OK] {message}"

    def split_long_message(
        self,
        text: str,
        max_length: int = MAX_MESSAGE_LENGTH
    ) -> List[str]:
        """
        Split a long message into parts that fit Telegram limits.

        Args:
            text: Text to split
            max_length: Maximum length per message

        Returns:
            List of message parts
        """
        if len(text) <= max_length:
            return [text]

        parts = []
        current = ""

        for line in text.split("\n"):
            if len(current) + len(line) + 1 <= max_length:
                current += line + "\n"
            else:
                if current:
                    parts.append(current.rstrip())
                current = line + "\n"

        if current:
            parts.append(current.rstrip())

        return parts

    def add_inline_keyboard(
        self,
        buttons: List[Dict[str, str]]
    ) -> InlineKeyboardMarkup:
        """
        Create an inline keyboard from button definitions.

        Args:
            buttons: List of button dicts with 'text' and 'callback_data' or 'url'

        Returns:
            InlineKeyboardMarkup
        """
        keyboard = []
        row = []

        for btn in buttons:
            text = btn.get("text", "")

            if "url" in btn:
                button = InlineKeyboardButton(text=text, url=btn["url"])
            else:
                callback = btn.get("callback_data", btn.get("callback", ""))
                button = InlineKeyboardButton(text=text, callback_data=callback)

            if btn.get("new_row", False) and row:
                keyboard.append(row)
                row = [button]
            else:
                row.append(button)

        if row:
            keyboard.append(row)

        return InlineKeyboardMarkup(keyboard)

    def escape_markdown(self, text: str) -> str:
        """
        Escape Markdown special characters.

        Args:
            text: Text to escape

        Returns:
            Escaped text
        """
        special_chars = ['*', '_', '`', '[', ']']
        for char in special_chars:
            text = text.replace(char, f'\\{char}')
        return text

    def escape_markdown_v2(self, text: str) -> str:
        """
        Escape MarkdownV2 special characters.

        Args:
            text: Text to escape

        Returns:
            Escaped text
        """
        special_chars = [
            '_', '*', '[', ']', '(', ')', '~', '`', '>', '#',
            '+', '-', '=', '|', '{', '}', '.', '!'
        ]
        for char in special_chars:
            text = text.replace(char, f'\\{char}')
        return text
