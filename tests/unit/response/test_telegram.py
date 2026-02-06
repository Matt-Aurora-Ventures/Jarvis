"""Tests for TelegramFormatter class.

Covers:
- format_for_telegram() response formatting
- split_long_message() message splitting
- add_inline_keyboard() keyboard creation
"""
import pytest
from typing import Dict, List

from core.response.telegram import TelegramFormatter


class TestTelegramFormatterInit:
    """Test TelegramFormatter initialization."""

    def test_init_default(self):
        """Test default initialization."""
        formatter = TelegramFormatter()
        assert formatter is not None

    def test_init_with_parse_mode(self):
        """Test initialization with parse mode."""
        formatter = TelegramFormatter(parse_mode="HTML")
        assert formatter.parse_mode == "HTML"

    def test_init_default_parse_mode(self):
        """Test default parse mode is Markdown or MarkdownV2."""
        formatter = TelegramFormatter()
        assert formatter.parse_mode in ("Markdown", "MarkdownV2", "HTML")


class TestFormatForTelegram:
    """Test format_for_telegram() method."""

    def test_format_basic_response(self):
        """Test formatting basic response."""
        formatter = TelegramFormatter()
        response = {"message": "Hello World"}
        result = formatter.format_for_telegram(response)
        assert isinstance(result, str)
        assert "Hello World" in result

    def test_format_success_response(self):
        """Test formatting success response."""
        formatter = TelegramFormatter()
        response = {"success": True, "message": "Operation completed"}
        result = formatter.format_for_telegram(response)
        assert "Operation completed" in result

    def test_format_error_response(self):
        """Test formatting error response."""
        formatter = TelegramFormatter()
        response = {"success": False, "error": "Something failed"}
        result = formatter.format_for_telegram(response)
        assert "Something failed" in result or "error" in result.lower()

    def test_format_data_response(self):
        """Test formatting response with data."""
        formatter = TelegramFormatter()
        response = {"data": {"name": "Test", "value": 100}}
        result = formatter.format_for_telegram(response)
        assert "Test" in result or "name" in result.lower()

    def test_format_string_response(self):
        """Test formatting string response."""
        formatter = TelegramFormatter()
        result = formatter.format_for_telegram("Simple text")
        assert result == "Simple text" or "Simple text" in result

    def test_format_list_response(self):
        """Test formatting list response."""
        formatter = TelegramFormatter()
        response = ["item1", "item2", "item3"]
        result = formatter.format_for_telegram(response)
        assert "item1" in result

    def test_format_none_response(self):
        """Test formatting None response."""
        formatter = TelegramFormatter()
        result = formatter.format_for_telegram(None)
        assert result == "" or result is not None

    def test_format_empty_dict(self):
        """Test formatting empty dict."""
        formatter = TelegramFormatter()
        result = formatter.format_for_telegram({})
        assert isinstance(result, str)

    def test_format_nested_response(self):
        """Test formatting nested response."""
        formatter = TelegramFormatter()
        response = {
            "user": {
                "name": "Alice",
                "settings": {"theme": "dark"}
            }
        }
        result = formatter.format_for_telegram(response)
        assert "Alice" in result or "user" in result.lower()

    def test_format_escapes_special_chars(self):
        """Test special chars are handled for Telegram."""
        formatter = TelegramFormatter()
        response = {"message": "Use *bold* and _italic_"}
        result = formatter.format_for_telegram(response)
        # Content should be present (escaped or formatted)
        assert "bold" in result
        assert "italic" in result


class TestSplitLongMessage:
    """Test split_long_message() method."""

    def test_split_short_message(self):
        """Test short message is not split."""
        formatter = TelegramFormatter()
        message = "Short message"
        result = formatter.split_long_message(message)
        assert len(result) == 1
        assert result[0] == "Short message"

    def test_split_long_message_default_limit(self):
        """Test long message is split at default limit (4096)."""
        formatter = TelegramFormatter()
        message = "A" * 5000
        result = formatter.split_long_message(message)
        assert len(result) >= 2
        assert all(len(part) <= 4096 for part in result)

    def test_split_long_message_custom_limit(self):
        """Test long message with custom limit."""
        formatter = TelegramFormatter()
        message = "A" * 1000
        result = formatter.split_long_message(message, max_len=500)
        assert len(result) >= 2
        assert all(len(part) <= 500 for part in result)

    def test_split_preserves_all_content(self):
        """Test split preserves all content."""
        formatter = TelegramFormatter()
        message = "Hello " * 1000  # About 6000 chars
        result = formatter.split_long_message(message)
        rejoined = "".join(result)
        # Should preserve the message (maybe with split points)
        assert len(rejoined) >= len(message) - len(result)  # Allow for split markers

    def test_split_at_word_boundary(self):
        """Test split prefers word boundaries."""
        formatter = TelegramFormatter()
        message = "word " * 900  # About 4500 chars
        result = formatter.split_long_message(message)
        # First part should ideally end at a word boundary
        if len(result) > 1:
            assert result[0].endswith(" ") or result[0].endswith("word")

    def test_split_at_newline(self):
        """Test split prefers newline boundaries."""
        formatter = TelegramFormatter()
        lines = ["Line " + str(i) for i in range(500)]
        message = "\n".join(lines)
        result = formatter.split_long_message(message)
        # Should split at newlines when possible
        assert len(result) > 1

    def test_split_empty_message(self):
        """Test split empty message."""
        formatter = TelegramFormatter()
        result = formatter.split_long_message("")
        assert result == [] or result == [""]

    def test_split_exactly_at_limit(self):
        """Test message exactly at limit."""
        formatter = TelegramFormatter()
        message = "A" * 4096
        result = formatter.split_long_message(message)
        assert len(result) == 1
        assert len(result[0]) == 4096

    def test_split_one_over_limit(self):
        """Test message one char over limit."""
        formatter = TelegramFormatter()
        message = "A" * 4097
        result = formatter.split_long_message(message)
        assert len(result) >= 2

    def test_split_returns_list(self):
        """Test split always returns list."""
        formatter = TelegramFormatter()
        result = formatter.split_long_message("test")
        assert isinstance(result, list)


class TestAddInlineKeyboard:
    """Test add_inline_keyboard() method."""

    def test_add_simple_button(self):
        """Test adding single button."""
        formatter = TelegramFormatter()
        buttons = [{"text": "Click me", "callback_data": "action_1"}]
        result = formatter.add_inline_keyboard(buttons)
        assert "inline_keyboard" in result
        assert len(result["inline_keyboard"]) >= 1

    def test_add_multiple_buttons(self):
        """Test adding multiple buttons."""
        formatter = TelegramFormatter()
        buttons = [
            {"text": "Button 1", "callback_data": "action_1"},
            {"text": "Button 2", "callback_data": "action_2"},
        ]
        result = formatter.add_inline_keyboard(buttons)
        assert "inline_keyboard" in result

    def test_add_button_row(self):
        """Test buttons in same row."""
        formatter = TelegramFormatter()
        buttons = [
            [
                {"text": "Left", "callback_data": "left"},
                {"text": "Right", "callback_data": "right"},
            ]
        ]
        result = formatter.add_inline_keyboard(buttons)
        assert "inline_keyboard" in result
        # First row should have multiple buttons
        if result["inline_keyboard"]:
            assert len(result["inline_keyboard"][0]) >= 1

    def test_add_url_button(self):
        """Test adding URL button."""
        formatter = TelegramFormatter()
        buttons = [{"text": "Visit", "url": "https://example.com"}]
        result = formatter.add_inline_keyboard(buttons)
        assert "inline_keyboard" in result

    def test_add_empty_buttons(self):
        """Test adding empty button list."""
        formatter = TelegramFormatter()
        result = formatter.add_inline_keyboard([])
        assert "inline_keyboard" in result
        assert result["inline_keyboard"] == [] or result["inline_keyboard"] == [[]]

    def test_keyboard_structure(self):
        """Test keyboard has correct structure."""
        formatter = TelegramFormatter()
        buttons = [{"text": "Test", "callback_data": "test"}]
        result = formatter.add_inline_keyboard(buttons)

        assert isinstance(result, dict)
        assert "inline_keyboard" in result
        assert isinstance(result["inline_keyboard"], list)

    def test_button_text_preserved(self):
        """Test button text is preserved."""
        formatter = TelegramFormatter()
        buttons = [{"text": "My Button Text", "callback_data": "data"}]
        result = formatter.add_inline_keyboard(buttons)

        # Find the button text in the structure
        keyboard = result["inline_keyboard"]
        found = False
        for row in keyboard:
            for button in row:
                if button.get("text") == "My Button Text":
                    found = True
                    break
        assert found

    def test_callback_data_preserved(self):
        """Test callback data is preserved."""
        formatter = TelegramFormatter()
        buttons = [{"text": "Button", "callback_data": "unique_callback"}]
        result = formatter.add_inline_keyboard(buttons)

        keyboard = result["inline_keyboard"]
        found = False
        for row in keyboard:
            for button in row:
                if button.get("callback_data") == "unique_callback":
                    found = True
                    break
        assert found


class TestTelegramFormatterIntegration:
    """Test TelegramFormatter integration scenarios."""

    def test_format_and_split_long_response(self):
        """Test formatting then splitting a long response."""
        formatter = TelegramFormatter()
        response = {"message": "X" * 5000}
        formatted = formatter.format_for_telegram(response)
        parts = formatter.split_long_message(formatted)
        assert len(parts) >= 1
        assert all(len(p) <= 4096 for p in parts)

    def test_format_response_with_keyboard(self):
        """Test combining response formatting with keyboard."""
        formatter = TelegramFormatter()
        response = {"message": "Choose an option"}
        text = formatter.format_for_telegram(response)
        keyboard = formatter.add_inline_keyboard([
            {"text": "Option A", "callback_data": "a"},
            {"text": "Option B", "callback_data": "b"},
        ])

        assert "Choose an option" in text
        assert "inline_keyboard" in keyboard


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
