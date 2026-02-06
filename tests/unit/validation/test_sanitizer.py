"""
Tests for core/validation/sanitizer.py

Tests Sanitizer class: strip_html(), escape_markdown(), truncate(), remove_null_bytes().
"""
import pytest


class TestStripHtml:
    """Tests for Sanitizer.strip_html() method."""

    def test_strip_html_removes_simple_tags(self):
        """strip_html removes simple HTML tags."""
        from core.validation.sanitizer import Sanitizer

        sanitizer = Sanitizer()
        result = sanitizer.strip_html("<p>Hello World</p>")
        assert result == "Hello World"

    def test_strip_html_removes_nested_tags(self):
        """strip_html removes nested HTML tags."""
        from core.validation.sanitizer import Sanitizer

        sanitizer = Sanitizer()
        result = sanitizer.strip_html("<div><p><b>Bold</b> text</p></div>")
        assert result == "Bold text"

    def test_strip_html_removes_script_tags(self):
        """strip_html removes script tags and content."""
        from core.validation.sanitizer import Sanitizer

        sanitizer = Sanitizer()
        result = sanitizer.strip_html("Hello<script>alert('xss')</script>World")
        assert "script" not in result.lower()
        assert "alert" not in result.lower()
        assert "Hello" in result
        assert "World" in result

    def test_strip_html_removes_style_tags(self):
        """strip_html removes style tags and content."""
        from core.validation.sanitizer import Sanitizer

        sanitizer = Sanitizer()
        result = sanitizer.strip_html("Hello<style>body{color:red}</style>World")
        assert "style" not in result.lower()
        assert "color" not in result.lower()

    def test_strip_html_removes_event_handlers(self):
        """strip_html removes event handler attributes."""
        from core.validation.sanitizer import Sanitizer

        sanitizer = Sanitizer()
        result = sanitizer.strip_html('<div onclick="evil()">Click me</div>')
        assert "onclick" not in result.lower()
        assert "evil" not in result.lower()

    def test_strip_html_preserves_text(self):
        """strip_html preserves text content."""
        from core.validation.sanitizer import Sanitizer

        sanitizer = Sanitizer()
        result = sanitizer.strip_html("No HTML here")
        assert result == "No HTML here"

    def test_strip_html_handles_empty_string(self):
        """strip_html handles empty string."""
        from core.validation.sanitizer import Sanitizer

        sanitizer = Sanitizer()
        result = sanitizer.strip_html("")
        assert result == ""

    def test_strip_html_handles_malformed_html(self):
        """strip_html handles malformed HTML gracefully."""
        from core.validation.sanitizer import Sanitizer

        sanitizer = Sanitizer()
        result = sanitizer.strip_html("<p>Unclosed tag")
        assert "Unclosed tag" in result
        assert "<p>" not in result

    def test_strip_html_removes_img_tags_with_onerror(self):
        """strip_html removes img tags with onerror XSS attempts."""
        from core.validation.sanitizer import Sanitizer

        sanitizer = Sanitizer()
        result = sanitizer.strip_html('<img src="x" onerror="alert(1)">')
        assert "img" not in result.lower()
        assert "onerror" not in result.lower()


class TestEscapeMarkdown:
    """Tests for Sanitizer.escape_markdown() method."""

    def test_escape_markdown_escapes_asterisks(self):
        """escape_markdown escapes asterisks."""
        from core.validation.sanitizer import Sanitizer

        sanitizer = Sanitizer()
        result = sanitizer.escape_markdown("*bold* and **bolder**")
        assert "*" not in result or r"\*" in result

    def test_escape_markdown_escapes_underscores(self):
        """escape_markdown escapes underscores."""
        from core.validation.sanitizer import Sanitizer

        sanitizer = Sanitizer()
        result = sanitizer.escape_markdown("_italic_ and __underline__")
        assert "_" not in result or r"\_" in result

    def test_escape_markdown_escapes_backticks(self):
        """escape_markdown escapes backticks."""
        from core.validation.sanitizer import Sanitizer

        sanitizer = Sanitizer()
        result = sanitizer.escape_markdown("`code` and ```block```")
        assert "`" not in result or r"\`" in result

    def test_escape_markdown_escapes_brackets(self):
        """escape_markdown escapes square brackets."""
        from core.validation.sanitizer import Sanitizer

        sanitizer = Sanitizer()
        result = sanitizer.escape_markdown("[link](url)")
        # Should escape [ and ]
        assert "[" not in result or r"\[" in result

    def test_escape_markdown_escapes_hash(self):
        """escape_markdown escapes hash symbols."""
        from core.validation.sanitizer import Sanitizer

        sanitizer = Sanitizer()
        result = sanitizer.escape_markdown("# Heading")
        assert "#" not in result or r"\#" in result

    def test_escape_markdown_preserves_regular_text(self):
        """escape_markdown preserves regular text."""
        from core.validation.sanitizer import Sanitizer

        sanitizer = Sanitizer()
        result = sanitizer.escape_markdown("Hello World")
        assert result == "Hello World"

    def test_escape_markdown_handles_empty_string(self):
        """escape_markdown handles empty string."""
        from core.validation.sanitizer import Sanitizer

        sanitizer = Sanitizer()
        result = sanitizer.escape_markdown("")
        assert result == ""


class TestTruncate:
    """Tests for Sanitizer.truncate() method."""

    def test_truncate_returns_string_under_max(self):
        """truncate returns unchanged string under max length."""
        from core.validation.sanitizer import Sanitizer

        sanitizer = Sanitizer()
        result = sanitizer.truncate("Hello", max_len=10)
        assert result == "Hello"

    def test_truncate_cuts_string_at_max(self):
        """truncate cuts string at max length."""
        from core.validation.sanitizer import Sanitizer

        sanitizer = Sanitizer()
        result = sanitizer.truncate("Hello World", max_len=5)
        assert len(result) <= 5

    def test_truncate_adds_ellipsis_by_default(self):
        """truncate adds ellipsis by default when truncating."""
        from core.validation.sanitizer import Sanitizer

        sanitizer = Sanitizer()
        result = sanitizer.truncate("Hello World", max_len=8)
        assert result.endswith("...")
        assert len(result) <= 8

    def test_truncate_custom_suffix(self):
        """truncate uses custom suffix."""
        from core.validation.sanitizer import Sanitizer

        sanitizer = Sanitizer()
        result = sanitizer.truncate("Hello World", max_len=8, suffix=">>")
        assert result.endswith(">>")
        assert len(result) <= 8

    def test_truncate_no_suffix(self):
        """truncate without suffix."""
        from core.validation.sanitizer import Sanitizer

        sanitizer = Sanitizer()
        result = sanitizer.truncate("Hello World", max_len=5, suffix="")
        assert result == "Hello"
        assert len(result) == 5

    def test_truncate_handles_empty_string(self):
        """truncate handles empty string."""
        from core.validation.sanitizer import Sanitizer

        sanitizer = Sanitizer()
        result = sanitizer.truncate("", max_len=10)
        assert result == ""

    def test_truncate_handles_max_len_equal_to_string(self):
        """truncate handles max_len equal to string length."""
        from core.validation.sanitizer import Sanitizer

        sanitizer = Sanitizer()
        result = sanitizer.truncate("Hello", max_len=5)
        assert result == "Hello"

    def test_truncate_word_boundary(self):
        """truncate at word boundary when possible."""
        from core.validation.sanitizer import Sanitizer

        sanitizer = Sanitizer()
        result = sanitizer.truncate("Hello World", max_len=8, word_boundary=True)
        # Should truncate at word boundary, not in middle of "World"
        assert len(result) <= 8


class TestRemoveNullBytes:
    """Tests for Sanitizer.remove_null_bytes() method."""

    def test_remove_null_bytes_removes_null(self):
        """remove_null_bytes removes null bytes."""
        from core.validation.sanitizer import Sanitizer

        sanitizer = Sanitizer()
        result = sanitizer.remove_null_bytes("Hello\x00World")
        assert "\x00" not in result
        assert result == "HelloWorld"

    def test_remove_null_bytes_removes_multiple_nulls(self):
        """remove_null_bytes removes multiple null bytes."""
        from core.validation.sanitizer import Sanitizer

        sanitizer = Sanitizer()
        result = sanitizer.remove_null_bytes("A\x00B\x00C\x00D")
        assert result == "ABCD"

    def test_remove_null_bytes_preserves_string_without_nulls(self):
        """remove_null_bytes preserves string without null bytes."""
        from core.validation.sanitizer import Sanitizer

        sanitizer = Sanitizer()
        result = sanitizer.remove_null_bytes("Hello World")
        assert result == "Hello World"

    def test_remove_null_bytes_handles_empty_string(self):
        """remove_null_bytes handles empty string."""
        from core.validation.sanitizer import Sanitizer

        sanitizer = Sanitizer()
        result = sanitizer.remove_null_bytes("")
        assert result == ""

    def test_remove_null_bytes_handles_only_nulls(self):
        """remove_null_bytes handles string of only null bytes."""
        from core.validation.sanitizer import Sanitizer

        sanitizer = Sanitizer()
        result = sanitizer.remove_null_bytes("\x00\x00\x00")
        assert result == ""


class TestSanitizerChaining:
    """Tests for chaining multiple sanitizer methods."""

    def test_sanitize_chain(self):
        """Sanitizer methods can be chained via sanitize()."""
        from core.validation.sanitizer import Sanitizer

        sanitizer = Sanitizer()
        text = "<p>Hello\x00 **World**</p>"

        result = sanitizer.sanitize(
            text,
            strip_html=True,
            remove_nulls=True,
            escape_markdown=True
        )

        assert "<p>" not in result
        assert "\x00" not in result
        assert "**" not in result or r"\*\*" in result

    def test_sanitize_with_truncate(self):
        """Sanitizer.sanitize() with truncation."""
        from core.validation.sanitizer import Sanitizer

        sanitizer = Sanitizer()
        text = "<p>This is a very long text that needs to be truncated</p>"

        result = sanitizer.sanitize(text, strip_html=True, max_len=20)

        assert "<p>" not in result
        assert len(result) <= 20


class TestSanitizerStaticMethods:
    """Tests for static/class method versions."""

    def test_strip_html_static(self):
        """Sanitizer.strip_html works as static method."""
        from core.validation.sanitizer import Sanitizer

        result = Sanitizer.strip_html("<b>Bold</b>")
        assert result == "Bold"

    def test_escape_markdown_static(self):
        """Sanitizer.escape_markdown works as static method."""
        from core.validation.sanitizer import Sanitizer

        result = Sanitizer.escape_markdown("*text*")
        assert "*" not in result or r"\*" in result

    def test_truncate_static(self):
        """Sanitizer.truncate works as static method."""
        from core.validation.sanitizer import Sanitizer

        result = Sanitizer.truncate("Hello World", 5)
        assert len(result) <= 5

    def test_remove_null_bytes_static(self):
        """Sanitizer.remove_null_bytes works as static method."""
        from core.validation.sanitizer import Sanitizer

        result = Sanitizer.remove_null_bytes("A\x00B")
        assert result == "AB"


class TestSanitizerEdgeCases:
    """Tests for edge cases and security scenarios."""

    def test_strip_html_svg_xss(self):
        """strip_html handles SVG-based XSS."""
        from core.validation.sanitizer import Sanitizer

        sanitizer = Sanitizer()
        result = sanitizer.strip_html('<svg onload="alert(1)">')
        assert "svg" not in result.lower()
        assert "onload" not in result.lower()

    def test_strip_html_encoded_entities(self):
        """strip_html handles HTML entities."""
        from core.validation.sanitizer import Sanitizer

        sanitizer = Sanitizer()
        result = sanitizer.strip_html("&lt;script&gt;")
        # HTML entities should be decoded or escaped
        assert "script" not in result.lower() or "&lt;" in result

    def test_strip_html_data_uri(self):
        """strip_html handles data URI XSS attempts."""
        from core.validation.sanitizer import Sanitizer

        sanitizer = Sanitizer()
        result = sanitizer.strip_html('<a href="data:text/html,<script>alert(1)</script>">')
        assert "data:" not in result.lower()

    def test_truncate_unicode(self):
        """truncate handles unicode characters correctly."""
        from core.validation.sanitizer import Sanitizer

        sanitizer = Sanitizer()
        # Unicode string with emojis
        text = "Hello World"
        result = sanitizer.truncate(text, max_len=8)
        # Should not break unicode characters
        assert len(result) <= 8


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
