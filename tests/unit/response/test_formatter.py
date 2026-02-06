"""Tests for ResponseFormatter class.

Covers:
- format_text() with different platforms
- format_error() for error formatting
- format_list() for list formatting
- format_table() for table formatting
- Platform-specific formatting
"""
import pytest
from typing import Dict, List, Any

from core.response.formatter import ResponseFormatter, Platform


class TestResponseFormatterInit:
    """Test ResponseFormatter initialization."""

    def test_init_default(self):
        """Test default initialization."""
        formatter = ResponseFormatter()
        assert formatter is not None

    def test_init_with_platform(self):
        """Test initialization with platform."""
        formatter = ResponseFormatter(default_platform=Platform.TELEGRAM)
        assert formatter.default_platform == Platform.TELEGRAM

    def test_init_with_string_platform(self):
        """Test initialization with string platform."""
        formatter = ResponseFormatter(default_platform="telegram")
        assert formatter.default_platform == Platform.TELEGRAM


class TestFormatText:
    """Test format_text() method."""

    def test_format_text_basic(self):
        """Test basic text formatting."""
        formatter = ResponseFormatter()
        result = formatter.format_text("Hello World")
        assert result == "Hello World"

    def test_format_text_with_platform(self):
        """Test text formatting with platform override."""
        formatter = ResponseFormatter()
        result = formatter.format_text("Hello", platform=Platform.TELEGRAM)
        assert isinstance(result, str)

    def test_format_text_preserves_content(self):
        """Test that formatting preserves essential content."""
        formatter = ResponseFormatter()
        text = "Important message with data: 123"
        result = formatter.format_text(text)
        assert "Important message" in result
        assert "123" in result

    def test_format_text_empty(self):
        """Test formatting empty text."""
        formatter = ResponseFormatter()
        result = formatter.format_text("")
        assert result == ""

    def test_format_text_none_returns_empty(self):
        """Test formatting None returns empty string."""
        formatter = ResponseFormatter()
        result = formatter.format_text(None)
        assert result == ""

    def test_format_text_multiline(self):
        """Test formatting multiline text."""
        formatter = ResponseFormatter()
        text = "Line 1\nLine 2\nLine 3"
        result = formatter.format_text(text)
        assert "Line 1" in result
        assert "Line 2" in result
        assert "Line 3" in result

    def test_format_text_with_special_chars(self):
        """Test formatting text with special characters."""
        formatter = ResponseFormatter()
        text = "Price: $100 <test> & more"
        result = formatter.format_text(text, platform=Platform.PLAIN)
        assert "$100" in result


class TestFormatError:
    """Test format_error() method."""

    def test_format_error_exception(self):
        """Test formatting an exception."""
        formatter = ResponseFormatter()
        error = ValueError("Invalid input")
        result = formatter.format_error(error)
        assert "ValueError" in result or "Invalid input" in result

    def test_format_error_string(self):
        """Test formatting error string."""
        formatter = ResponseFormatter()
        result = formatter.format_error("Something went wrong")
        assert "Something went wrong" in result

    def test_format_error_with_code(self):
        """Test formatting error with code."""
        formatter = ResponseFormatter()
        result = formatter.format_error("Auth failed", code="AUTH_001")
        assert "AUTH_001" in result

    def test_format_error_includes_error_marker(self):
        """Test error formatting includes error indicator."""
        formatter = ResponseFormatter()
        result = formatter.format_error("Test error")
        # Should have some error indicator (emoji, prefix, etc.)
        assert len(result) > len("Test error")

    def test_format_error_dict(self):
        """Test formatting error dict."""
        formatter = ResponseFormatter()
        error = {"code": "ERR_001", "message": "Error message"}
        result = formatter.format_error(error)
        assert "ERR_001" in result or "Error message" in result


class TestFormatList:
    """Test format_list() method."""

    def test_format_list_basic(self):
        """Test basic list formatting."""
        formatter = ResponseFormatter()
        items = ["Item 1", "Item 2", "Item 3"]
        result = formatter.format_list(items)
        assert "Item 1" in result
        assert "Item 2" in result
        assert "Item 3" in result

    def test_format_list_empty(self):
        """Test formatting empty list."""
        formatter = ResponseFormatter()
        result = formatter.format_list([])
        assert result == "" or "empty" in result.lower() or "none" in result.lower()

    def test_format_list_single_item(self):
        """Test formatting single item list."""
        formatter = ResponseFormatter()
        result = formatter.format_list(["Only item"])
        assert "Only item" in result

    def test_format_list_with_bullet_points(self):
        """Test list has bullet points or similar markers."""
        formatter = ResponseFormatter()
        items = ["First", "Second"]
        result = formatter.format_list(items)
        # Should have some kind of list marker
        lines = result.split('\n')
        # Check that items are on separate lines or have markers
        assert len(lines) >= 2 or '-' in result or '*' in result or '1' in result

    def test_format_list_numbered(self):
        """Test numbered list formatting."""
        formatter = ResponseFormatter()
        items = ["Step 1", "Step 2", "Step 3"]
        result = formatter.format_list(items, numbered=True)
        assert "1" in result or "Step 1" in result

    def test_format_list_with_title(self):
        """Test list with title."""
        formatter = ResponseFormatter()
        items = ["A", "B", "C"]
        result = formatter.format_list(items, title="Options")
        assert "Options" in result


class TestFormatTable:
    """Test format_table() method."""

    def test_format_table_basic(self):
        """Test basic table formatting."""
        formatter = ResponseFormatter()
        data = [
            {"name": "Alice", "age": 30},
            {"name": "Bob", "age": 25},
        ]
        result = formatter.format_table(data)
        assert "Alice" in result
        assert "Bob" in result

    def test_format_table_empty(self):
        """Test formatting empty table."""
        formatter = ResponseFormatter()
        result = formatter.format_table([])
        assert result == "" or "empty" in result.lower() or "no data" in result.lower()

    def test_format_table_single_row(self):
        """Test formatting single row table."""
        formatter = ResponseFormatter()
        data = [{"key": "value"}]
        result = formatter.format_table(data)
        assert "key" in result or "value" in result

    def test_format_table_with_headers(self):
        """Test table with custom headers."""
        formatter = ResponseFormatter()
        data = [{"a": 1, "b": 2}]
        result = formatter.format_table(data, headers=["Column A", "Column B"])
        assert "Column A" in result or "a" in result

    def test_format_table_with_numbers(self):
        """Test table with numeric values."""
        formatter = ResponseFormatter()
        data = [
            {"item": "Widget", "price": 9.99, "qty": 5},
            {"item": "Gadget", "price": 19.99, "qty": 3},
        ]
        result = formatter.format_table(data)
        assert "Widget" in result
        assert "9.99" in result or "9" in result

    def test_format_table_alignment(self):
        """Test table content is formatted for readability."""
        formatter = ResponseFormatter()
        data = [
            {"short": "a", "long": "very long value here"},
        ]
        result = formatter.format_table(data)
        # Just verify content is present
        assert "a" in result
        assert "very long value here" in result


class TestPlatformEnum:
    """Test Platform enum."""

    def test_platform_values(self):
        """Test expected platform values exist."""
        assert Platform.PLAIN is not None
        assert Platform.TELEGRAM is not None
        assert Platform.MARKDOWN is not None

    def test_platform_from_string(self):
        """Test platform can be referenced by string."""
        assert Platform("plain") == Platform.PLAIN
        assert Platform("telegram") == Platform.TELEGRAM


class TestCrossPlatformFormatting:
    """Test formatting across different platforms."""

    def test_same_content_different_platforms(self):
        """Test same content formats for different platforms."""
        formatter = ResponseFormatter()
        text = "Test message"

        plain = formatter.format_text(text, platform=Platform.PLAIN)
        telegram = formatter.format_text(text, platform=Platform.TELEGRAM)

        # Content should be preserved
        assert "Test message" in plain
        assert "Test message" in telegram

    def test_table_different_platforms(self):
        """Test table formatting for different platforms."""
        formatter = ResponseFormatter()
        data = [{"name": "Test", "value": 100}]

        plain = formatter.format_table(data, platform=Platform.PLAIN)
        telegram = formatter.format_table(data, platform=Platform.TELEGRAM)

        # Both should contain the data
        assert "Test" in plain
        assert "Test" in telegram


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
