"""
Tests for KeyboardBuilder class.

Tests fluent keyboard building interface for Telegram inline keyboards.
"""

import pytest
from unittest.mock import MagicMock, patch


class TestKeyboardBuilder:
    """Test KeyboardBuilder class."""

    def test_empty_build(self):
        """build() on empty builder should return empty keyboard."""
        from core.response.keyboard import KeyboardBuilder

        builder = KeyboardBuilder()
        keyboard = builder.build()

        assert keyboard is not None
        assert len(keyboard.inline_keyboard) == 0

    def test_add_button_single(self):
        """add_button() should add a callback button."""
        from core.response.keyboard import KeyboardBuilder

        builder = KeyboardBuilder()
        keyboard = builder.add_button("Click Me", "action:data").build()

        assert len(keyboard.inline_keyboard) == 1
        assert len(keyboard.inline_keyboard[0]) == 1
        assert keyboard.inline_keyboard[0][0].text == "Click Me"
        assert keyboard.inline_keyboard[0][0].callback_data == "action:data"

    def test_add_button_chaining(self):
        """add_button() should support chaining, buttons stay on same row."""
        from core.response.keyboard import KeyboardBuilder

        builder = KeyboardBuilder()
        keyboard = (
            builder
            .add_button("Button 1", "action1")
            .add_button("Button 2", "action2")
            .build()
        )

        # Buttons stay on same row until add_row() is called
        assert len(keyboard.inline_keyboard) == 1
        assert len(keyboard.inline_keyboard[0]) == 2

    def test_add_button_same_row(self):
        """Multiple buttons before add_row() should be on same row."""
        from core.response.keyboard import KeyboardBuilder

        builder = KeyboardBuilder()
        keyboard = (
            builder
            .add_button("A", "a")
            .add_button("B", "b")
            .add_row()
            .add_button("C", "c")
            .build()
        )

        # First row: A, B; Second row: C
        assert len(keyboard.inline_keyboard) == 2
        assert len(keyboard.inline_keyboard[0]) == 2
        assert len(keyboard.inline_keyboard[1]) == 1

    def test_add_row_creates_new_row(self):
        """add_row() should start a new row for subsequent buttons."""
        from core.response.keyboard import KeyboardBuilder

        builder = KeyboardBuilder()
        keyboard = (
            builder
            .add_button("Row 1", "r1")
            .add_row()
            .add_button("Row 2", "r2")
            .build()
        )

        assert len(keyboard.inline_keyboard) == 2
        assert keyboard.inline_keyboard[0][0].text == "Row 1"
        assert keyboard.inline_keyboard[1][0].text == "Row 2"

    def test_add_url_button(self):
        """add_url_button() should add a URL button."""
        from core.response.keyboard import KeyboardBuilder

        builder = KeyboardBuilder()
        keyboard = builder.add_url_button("Visit", "https://example.com").build()

        assert len(keyboard.inline_keyboard) == 1
        btn = keyboard.inline_keyboard[0][0]
        assert btn.text == "Visit"
        assert btn.url == "https://example.com"
        assert btn.callback_data is None

    def test_add_url_button_mixed(self):
        """URL and callback buttons should work together on same row."""
        from core.response.keyboard import KeyboardBuilder

        builder = KeyboardBuilder()
        keyboard = (
            builder
            .add_button("Action", "action:1")
            .add_url_button("Link", "https://example.com")
            .build()
        )

        # Both buttons on same row
        assert len(keyboard.inline_keyboard) == 1
        assert keyboard.inline_keyboard[0][0].callback_data == "action:1"
        assert keyboard.inline_keyboard[0][1].url == "https://example.com"

    def test_build_returns_inline_keyboard_markup(self):
        """build() should return InlineKeyboardMarkup."""
        from core.response.keyboard import KeyboardBuilder
        from telegram import InlineKeyboardMarkup

        builder = KeyboardBuilder()
        keyboard = builder.add_button("Test", "test").build()

        assert isinstance(keyboard, InlineKeyboardMarkup)

    def test_callback_data_truncation(self):
        """Long callback data should be truncated to 64 bytes."""
        from core.response.keyboard import KeyboardBuilder

        builder = KeyboardBuilder()
        long_data = "a" * 100  # Exceeds 64 byte limit
        keyboard = builder.add_button("Test", long_data).build()

        callback = keyboard.inline_keyboard[0][0].callback_data
        assert len(callback.encode('utf-8')) <= 64

    def test_add_buttons_row(self):
        """add_buttons_row() should add multiple buttons in one row."""
        from core.response.keyboard import KeyboardBuilder

        builder = KeyboardBuilder()
        keyboard = (
            builder
            .add_buttons_row([
                ("A", "a"),
                ("B", "b"),
                ("C", "c"),
            ])
            .build()
        )

        assert len(keyboard.inline_keyboard) == 1
        assert len(keyboard.inline_keyboard[0]) == 3

    def test_clear_resets_builder(self):
        """clear() should reset the builder."""
        from core.response.keyboard import KeyboardBuilder

        builder = KeyboardBuilder()
        builder.add_button("Test", "test")
        builder.clear()
        keyboard = builder.build()

        assert len(keyboard.inline_keyboard) == 0


class TestKeyboardBuilderGrid:
    """Test grid layout functionality."""

    def test_add_button_grid(self):
        """add_button_grid() should create grid layout."""
        from core.response.keyboard import KeyboardBuilder

        buttons = [
            ("1", "1"), ("2", "2"), ("3", "3"),
            ("4", "4"), ("5", "5"), ("6", "6"),
        ]

        builder = KeyboardBuilder()
        keyboard = builder.add_button_grid(buttons, columns=3).build()

        assert len(keyboard.inline_keyboard) == 2  # 6 buttons / 3 columns = 2 rows
        assert len(keyboard.inline_keyboard[0]) == 3
        assert len(keyboard.inline_keyboard[1]) == 3

    def test_add_button_grid_uneven(self):
        """Grid with uneven button count should work."""
        from core.response.keyboard import KeyboardBuilder

        buttons = [
            ("1", "1"), ("2", "2"), ("3", "3"),
            ("4", "4"), ("5", "5"),
        ]

        builder = KeyboardBuilder()
        keyboard = builder.add_button_grid(buttons, columns=3).build()

        assert len(keyboard.inline_keyboard) == 2
        assert len(keyboard.inline_keyboard[0]) == 3
        assert len(keyboard.inline_keyboard[1]) == 2  # Remaining buttons


class TestKeyboardBuilderNavigation:
    """Test navigation button helpers."""

    def test_add_back_button(self):
        """add_back_button() should add a back navigation button."""
        from core.response.keyboard import KeyboardBuilder

        builder = KeyboardBuilder()
        keyboard = builder.add_back_button().build()

        btn = keyboard.inline_keyboard[0][0]
        assert "Back" in btn.text or "back" in btn.callback_data

    def test_add_close_button(self):
        """add_close_button() should add a close button."""
        from core.response.keyboard import KeyboardBuilder

        builder = KeyboardBuilder()
        keyboard = builder.add_close_button().build()

        btn = keyboard.inline_keyboard[0][0]
        assert "Close" in btn.text or "close" in btn.callback_data

    def test_add_navigation_row(self):
        """add_navigation_row() should add back and close buttons."""
        from core.response.keyboard import KeyboardBuilder

        builder = KeyboardBuilder()
        keyboard = builder.add_navigation_row().build()

        row = keyboard.inline_keyboard[0]
        assert len(row) == 2
        texts = [btn.text for btn in row]
        assert any("Back" in t for t in texts)
        assert any("Close" in t for t in texts)

    def test_add_pagination(self):
        """add_pagination() should add previous/next buttons."""
        from core.response.keyboard import KeyboardBuilder

        builder = KeyboardBuilder()
        keyboard = builder.add_pagination(
            current_page=2,
            total_pages=5,
            callback_prefix="page"
        ).build()

        row = keyboard.inline_keyboard[0]
        assert len(row) >= 2  # At least prev and next

        # Should have prev button (not on first page)
        assert any("<" in btn.text or "Prev" in btn.text for btn in row)
        # Should have next button (not on last page)
        assert any(">" in btn.text or "Next" in btn.text for btn in row)

    def test_add_pagination_first_page(self):
        """First page should not have previous button."""
        from core.response.keyboard import KeyboardBuilder

        builder = KeyboardBuilder()
        keyboard = builder.add_pagination(
            current_page=1,
            total_pages=5,
            callback_prefix="page"
        ).build()

        row = keyboard.inline_keyboard[0]
        # Previous should be disabled or absent
        prev_btn = next((b for b in row if "<" in b.text or "Prev" in b.text), None)
        if prev_btn:
            assert prev_btn.callback_data in ("noop", None) or "disabled" in prev_btn.callback_data

    def test_add_pagination_last_page(self):
        """Last page should not have next button."""
        from core.response.keyboard import KeyboardBuilder

        builder = KeyboardBuilder()
        keyboard = builder.add_pagination(
            current_page=5,
            total_pages=5,
            callback_prefix="page"
        ).build()

        row = keyboard.inline_keyboard[0]
        # Next should be disabled or absent
        next_btn = next((b for b in row if ">" in b.text or "Next" in b.text), None)
        if next_btn:
            assert next_btn.callback_data in ("noop", None) or "disabled" in next_btn.callback_data


class TestKeyboardBuilderConfirmation:
    """Test confirmation dialog helpers."""

    def test_add_confirm_cancel(self):
        """add_confirm_cancel() should add confirm and cancel buttons."""
        from core.response.keyboard import KeyboardBuilder

        builder = KeyboardBuilder()
        keyboard = builder.add_confirm_cancel(
            confirm_callback="confirm:action",
            cancel_callback="cancel:action"
        ).build()

        row = keyboard.inline_keyboard[0]
        assert len(row) == 2

        texts = [btn.text for btn in row]
        assert any("Confirm" in t or "Yes" in t for t in texts)
        assert any("Cancel" in t or "No" in t for t in texts)

    def test_add_confirm_cancel_custom_text(self):
        """add_confirm_cancel() should accept custom text."""
        from core.response.keyboard import KeyboardBuilder

        builder = KeyboardBuilder()
        keyboard = builder.add_confirm_cancel(
            confirm_callback="yes",
            cancel_callback="no",
            confirm_text="Accept",
            cancel_text="Decline"
        ).build()

        row = keyboard.inline_keyboard[0]
        texts = [btn.text for btn in row]
        assert "Accept" in texts
        assert "Decline" in texts
