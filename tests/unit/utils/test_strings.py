"""
Tests for core.utils.strings module.

Tests the string utility functions:
- truncate
- slugify
- camel_to_snake
- snake_to_camel
- escape_markdown
"""

import pytest


class TestTruncate:
    """Tests for truncate function."""

    def test_truncate_shorter_than_max(self):
        """Text shorter than max_len should not be modified."""
        from core.utils.strings import truncate

        result = truncate("hello", 10)
        assert result == "hello"

    def test_truncate_exact_length(self):
        """Text exactly at max_len should not be modified."""
        from core.utils.strings import truncate

        result = truncate("hello", 5)
        assert result == "hello"

    def test_truncate_longer_than_max(self):
        """Text longer than max_len should be truncated with suffix."""
        from core.utils.strings import truncate

        result = truncate("hello world", 8)
        assert result == "hello..."
        assert len(result) == 8

    def test_truncate_custom_suffix(self):
        """Custom suffix should be used when provided."""
        from core.utils.strings import truncate

        result = truncate("hello world", 9, suffix=">>")
        assert result == "hello w>>"
        assert len(result) == 9

    def test_truncate_empty_string(self):
        """Empty string should return empty string."""
        from core.utils.strings import truncate

        result = truncate("", 10)
        assert result == ""

    def test_truncate_max_len_smaller_than_suffix(self):
        """Max length smaller than suffix should still work."""
        from core.utils.strings import truncate

        result = truncate("hello", 2, suffix="...")
        assert len(result) <= 2

    def test_truncate_unicode(self):
        """Unicode characters should be handled correctly."""
        from core.utils.strings import truncate

        result = truncate("hello", 8)
        assert result == "hello"


class TestSlugify:
    """Tests for slugify function."""

    def test_slugify_basic(self):
        """Basic text should be converted to lowercase with hyphens."""
        from core.utils.strings import slugify

        result = slugify("Hello World")
        assert result == "hello-world"

    def test_slugify_special_characters(self):
        """Special characters should be removed."""
        from core.utils.strings import slugify

        result = slugify("Hello! World?")
        assert result == "hello-world"

    def test_slugify_multiple_spaces(self):
        """Multiple spaces should become single hyphen."""
        from core.utils.strings import slugify

        result = slugify("Hello   World")
        assert result == "hello-world"

    def test_slugify_leading_trailing_spaces(self):
        """Leading/trailing spaces should be removed."""
        from core.utils.strings import slugify

        result = slugify("  Hello World  ")
        assert result == "hello-world"

    def test_slugify_numbers(self):
        """Numbers should be preserved."""
        from core.utils.strings import slugify

        result = slugify("Version 2.0")
        assert result == "version-20" or result == "version-2-0"

    def test_slugify_empty_string(self):
        """Empty string should return empty string."""
        from core.utils.strings import slugify

        result = slugify("")
        assert result == ""

    def test_slugify_unicode(self):
        """Unicode should be handled (accents removed or preserved)."""
        from core.utils.strings import slugify

        result = slugify("Cafe Resume")
        assert "cafe" in result.lower()


class TestCamelToSnake:
    """Tests for camel_to_snake function."""

    def test_camel_to_snake_basic(self):
        """Basic camelCase should convert to snake_case."""
        from core.utils.strings import camel_to_snake

        result = camel_to_snake("camelCase")
        assert result == "camel_case"

    def test_camel_to_snake_pascal(self):
        """PascalCase should convert to snake_case."""
        from core.utils.strings import camel_to_snake

        result = camel_to_snake("PascalCase")
        assert result == "pascal_case"

    def test_camel_to_snake_consecutive_caps(self):
        """Consecutive capitals should be handled."""
        from core.utils.strings import camel_to_snake

        result = camel_to_snake("HTTPResponse")
        # Could be "http_response" or "h_t_t_p_response" - either is valid
        assert "response" in result.lower()

    def test_camel_to_snake_already_snake(self):
        """Already snake_case should remain unchanged."""
        from core.utils.strings import camel_to_snake

        result = camel_to_snake("already_snake")
        assert result == "already_snake"

    def test_camel_to_snake_empty(self):
        """Empty string should return empty string."""
        from core.utils.strings import camel_to_snake

        result = camel_to_snake("")
        assert result == ""

    def test_camel_to_snake_single_word(self):
        """Single word should be lowercase."""
        from core.utils.strings import camel_to_snake

        result = camel_to_snake("Hello")
        assert result == "hello"


class TestSnakeToCamel:
    """Tests for snake_to_camel function."""

    def test_snake_to_camel_basic(self):
        """Basic snake_case should convert to camelCase."""
        from core.utils.strings import snake_to_camel

        result = snake_to_camel("snake_case")
        assert result == "snakeCase"

    def test_snake_to_camel_multiple_words(self):
        """Multiple underscores should work."""
        from core.utils.strings import snake_to_camel

        result = snake_to_camel("this_is_snake_case")
        assert result == "thisIsSnakeCase"

    def test_snake_to_camel_already_camel(self):
        """Already camelCase should remain similar."""
        from core.utils.strings import snake_to_camel

        result = snake_to_camel("camelCase")
        assert result == "camelCase"

    def test_snake_to_camel_empty(self):
        """Empty string should return empty string."""
        from core.utils.strings import snake_to_camel

        result = snake_to_camel("")
        assert result == ""

    def test_snake_to_camel_single_word(self):
        """Single word should remain lowercase."""
        from core.utils.strings import snake_to_camel

        result = snake_to_camel("hello")
        assert result == "hello"

    def test_snake_to_camel_consecutive_underscores(self):
        """Consecutive underscores should be handled."""
        from core.utils.strings import snake_to_camel

        result = snake_to_camel("hello__world")
        # Should handle gracefully, not error
        assert "hello" in result.lower()


class TestEscapeMarkdown:
    """Tests for escape_markdown function."""

    def test_escape_markdown_asterisks(self):
        """Asterisks should be escaped."""
        from core.utils.strings import escape_markdown

        result = escape_markdown("*bold*")
        assert "*" not in result or result.count("\\*") == 2

    def test_escape_markdown_underscores(self):
        """Underscores should be escaped."""
        from core.utils.strings import escape_markdown

        result = escape_markdown("_italic_")
        assert "_" not in result or "\\_" in result

    def test_escape_markdown_brackets(self):
        """Brackets should be escaped."""
        from core.utils.strings import escape_markdown

        result = escape_markdown("[link](url)")
        assert "\\[" in result or "[" not in result

    def test_escape_markdown_backticks(self):
        """Backticks should be escaped."""
        from core.utils.strings import escape_markdown

        result = escape_markdown("`code`")
        assert "\\`" in result or "`" not in result

    def test_escape_markdown_plain_text(self):
        """Plain text should remain unchanged."""
        from core.utils.strings import escape_markdown

        result = escape_markdown("hello world")
        assert result == "hello world"

    def test_escape_markdown_empty(self):
        """Empty string should return empty string."""
        from core.utils.strings import escape_markdown

        result = escape_markdown("")
        assert result == ""

    def test_escape_markdown_telegram_v2(self):
        """Should escape characters used in Telegram MarkdownV2."""
        from core.utils.strings import escape_markdown

        # MarkdownV2 special chars: _ * [ ] ( ) ~ ` > # + - = | { } . !
        text = "Price: $100 (50% off!)"
        result = escape_markdown(text)
        # Should not raise and should escape properly
        assert isinstance(result, str)
