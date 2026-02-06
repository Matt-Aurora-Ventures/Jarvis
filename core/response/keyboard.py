"""
KeyboardBuilder - Fluent keyboard builder for Telegram inline keyboards.

Provides a chainable interface for building inline keyboards with
buttons, rows, and navigation elements.

Example:
    builder = KeyboardBuilder()
    keyboard = (
        builder
        .add_button("Option 1", "action:1")
        .add_button("Option 2", "action:2")
        .add_row()
        .add_button("Cancel", "cancel")
        .build()
    )
"""

from __future__ import annotations

from typing import List, Optional, Tuple, Union

from telegram import InlineKeyboardButton, InlineKeyboardMarkup


# Telegram callback data limit
MAX_CALLBACK_DATA_LENGTH = 64


def _truncate_callback_data(data: str) -> str:
    """Truncate callback data to fit Telegram's 64-byte limit."""
    if len(data.encode('utf-8')) <= MAX_CALLBACK_DATA_LENGTH:
        return data

    # Truncate to fit, leaving room for "..."
    while len(data.encode('utf-8')) > MAX_CALLBACK_DATA_LENGTH - 3:
        data = data[:-1]
    return data + "..."


class KeyboardBuilder:
    """
    Fluent builder for Telegram inline keyboards.

    Supports method chaining for intuitive keyboard construction:
        builder.add_button("A", "a").add_button("B", "b").add_row().add_button("C", "c")

    All methods return self to enable chaining except build() which
    returns the InlineKeyboardMarkup.
    """

    def __init__(self) -> None:
        """Initialize empty builder."""
        self._rows: List[List[InlineKeyboardButton]] = []
        self._current_row: List[InlineKeyboardButton] = []

    def add_button(
        self,
        text: str,
        callback_data: str
    ) -> KeyboardBuilder:
        """
        Add a callback button to the current row.

        Args:
            text: Button display text
            callback_data: Callback data string (max 64 bytes)

        Returns:
            self for chaining
        """
        truncated_data = _truncate_callback_data(callback_data)
        button = InlineKeyboardButton(text=text, callback_data=truncated_data)
        self._current_row.append(button)
        return self

    def add_url_button(self, text: str, url: str) -> KeyboardBuilder:
        """
        Add a URL button to the current row.

        Args:
            text: Button display text
            url: URL to open when clicked

        Returns:
            self for chaining
        """
        button = InlineKeyboardButton(text=text, url=url)
        self._current_row.append(button)
        return self

    def add_row(self) -> KeyboardBuilder:
        """
        Finish current row and start a new one.

        Returns:
            self for chaining
        """
        if self._current_row:
            self._rows.append(self._current_row)
            self._current_row = []
        return self

    def add_buttons_row(
        self,
        buttons: List[Tuple[str, str]]
    ) -> KeyboardBuilder:
        """
        Add multiple buttons as a single row.

        Args:
            buttons: List of (text, callback_data) tuples

        Returns:
            self for chaining
        """
        self.add_row()  # Finish any pending row
        row = []
        for text, data in buttons:
            truncated_data = _truncate_callback_data(data)
            row.append(InlineKeyboardButton(text=text, callback_data=truncated_data))
        self._rows.append(row)
        return self

    def add_button_grid(
        self,
        buttons: List[Tuple[str, str]],
        columns: int = 3
    ) -> KeyboardBuilder:
        """
        Add buttons in a grid layout.

        Args:
            buttons: List of (text, callback_data) tuples
            columns: Number of columns per row

        Returns:
            self for chaining
        """
        self.add_row()  # Finish any pending row

        for i in range(0, len(buttons), columns):
            row_buttons = buttons[i:i + columns]
            row = []
            for text, data in row_buttons:
                truncated_data = _truncate_callback_data(data)
                row.append(InlineKeyboardButton(text=text, callback_data=truncated_data))
            self._rows.append(row)
        return self

    def add_back_button(
        self,
        callback_data: str = "nav:back"
    ) -> KeyboardBuilder:
        """
        Add a back navigation button.

        Args:
            callback_data: Callback data for back action

        Returns:
            self for chaining
        """
        self.add_row()
        self._current_row.append(
            InlineKeyboardButton(text="< Back", callback_data=callback_data)
        )
        return self

    def add_close_button(
        self,
        callback_data: str = "ui:close"
    ) -> KeyboardBuilder:
        """
        Add a close button.

        Args:
            callback_data: Callback data for close action

        Returns:
            self for chaining
        """
        self.add_row()
        self._current_row.append(
            InlineKeyboardButton(text="X Close", callback_data=callback_data)
        )
        return self

    def add_navigation_row(
        self,
        back_callback: str = "nav:back",
        close_callback: str = "ui:close"
    ) -> KeyboardBuilder:
        """
        Add a row with back and close buttons.

        Args:
            back_callback: Callback data for back button
            close_callback: Callback data for close button

        Returns:
            self for chaining
        """
        self.add_row()
        self._rows.append([
            InlineKeyboardButton(text="< Back", callback_data=back_callback),
            InlineKeyboardButton(text="X Close", callback_data=close_callback),
        ])
        return self

    def add_pagination(
        self,
        current_page: int,
        total_pages: int,
        callback_prefix: str = "page"
    ) -> KeyboardBuilder:
        """
        Add pagination buttons.

        Args:
            current_page: Current page number (1-indexed)
            total_pages: Total number of pages
            callback_prefix: Prefix for page callbacks

        Returns:
            self for chaining
        """
        self.add_row()
        row = []

        # Previous button
        if current_page > 1:
            row.append(InlineKeyboardButton(
                text="< Prev",
                callback_data=f"{callback_prefix}:{current_page - 1}"
            ))
        else:
            row.append(InlineKeyboardButton(
                text=" ",
                callback_data="noop"
            ))

        # Page indicator
        row.append(InlineKeyboardButton(
            text=f"{current_page}/{total_pages}",
            callback_data="noop"
        ))

        # Next button
        if current_page < total_pages:
            row.append(InlineKeyboardButton(
                text="Next >",
                callback_data=f"{callback_prefix}:{current_page + 1}"
            ))
        else:
            row.append(InlineKeyboardButton(
                text=" ",
                callback_data="noop"
            ))

        self._rows.append(row)
        return self

    def add_confirm_cancel(
        self,
        confirm_callback: str,
        cancel_callback: str,
        confirm_text: str = "Confirm",
        cancel_text: str = "Cancel"
    ) -> KeyboardBuilder:
        """
        Add confirm and cancel buttons.

        Args:
            confirm_callback: Callback data for confirm
            cancel_callback: Callback data for cancel
            confirm_text: Text for confirm button
            cancel_text: Text for cancel button

        Returns:
            self for chaining
        """
        self.add_row()
        self._rows.append([
            InlineKeyboardButton(text=confirm_text, callback_data=confirm_callback),
            InlineKeyboardButton(text=cancel_text, callback_data=cancel_callback),
        ])
        return self

    def clear(self) -> KeyboardBuilder:
        """
        Clear all buttons and reset builder.

        Returns:
            self for chaining
        """
        self._rows = []
        self._current_row = []
        return self

    def build(self) -> InlineKeyboardMarkup:
        """
        Build and return the InlineKeyboardMarkup.

        Returns:
            Telegram InlineKeyboardMarkup object
        """
        # Add any pending row
        if self._current_row:
            self._rows.append(self._current_row)
            self._current_row = []

        return InlineKeyboardMarkup(self._rows)


# Convenience function for quick keyboard creation
def keyboard() -> KeyboardBuilder:
    """
    Create a new KeyboardBuilder.

    Returns:
        New KeyboardBuilder instance
    """
    return KeyboardBuilder()
