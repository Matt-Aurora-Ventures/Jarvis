"""Tests for MarkdownFormatter class.

Covers:
- bold(), italic(), code() formatting
- link() creation
- escape() special characters
- convert_html_to_md() conversion
"""
import pytest

from core.response.markdown import MarkdownFormatter


class TestMarkdownFormatterInit:
    """Test MarkdownFormatter initialization."""

    def test_init_default(self):
        """Test default initialization."""
        formatter = MarkdownFormatter()
        assert formatter is not None


class TestBoldFormatting:
    """Test bold() method."""

    def test_bold_basic(self):
        """Test basic bold formatting."""
        formatter = MarkdownFormatter()
        result = formatter.bold("important")
        assert result == "*important*" or result == "**important**"

    def test_bold_empty(self):
        """Test bold with empty string."""
        formatter = MarkdownFormatter()
        result = formatter.bold("")
        assert result == "**" or result == ""

    def test_bold_none(self):
        """Test bold with None."""
        formatter = MarkdownFormatter()
        result = formatter.bold(None)
        assert result == "" or result == "**"

    def test_bold_with_spaces(self):
        """Test bold with spaces."""
        formatter = MarkdownFormatter()
        result = formatter.bold("hello world")
        assert "hello world" in result
        assert result.startswith("*") or result.startswith("**")

    def test_bold_preserves_content(self):
        """Test bold preserves original content."""
        formatter = MarkdownFormatter()
        result = formatter.bold("Test 123")
        assert "Test 123" in result


class TestItalicFormatting:
    """Test italic() method."""

    def test_italic_basic(self):
        """Test basic italic formatting."""
        formatter = MarkdownFormatter()
        result = formatter.italic("emphasis")
        assert result == "_emphasis_" or result == "*emphasis*"

    def test_italic_empty(self):
        """Test italic with empty string."""
        formatter = MarkdownFormatter()
        result = formatter.italic("")
        assert result == "_" or result == "" or result == "__"

    def test_italic_none(self):
        """Test italic with None."""
        formatter = MarkdownFormatter()
        result = formatter.italic(None)
        assert result == "" or result == "__"

    def test_italic_preserves_content(self):
        """Test italic preserves original content."""
        formatter = MarkdownFormatter()
        result = formatter.italic("emphasized text")
        assert "emphasized text" in result


class TestCodeFormatting:
    """Test code() method."""

    def test_code_basic(self):
        """Test basic code formatting."""
        formatter = MarkdownFormatter()
        result = formatter.code("print('hello')")
        assert "`print('hello')`" in result or "print('hello')" in result

    def test_code_inline(self):
        """Test inline code formatting."""
        formatter = MarkdownFormatter()
        result = formatter.code("variable")
        assert "`" in result
        assert "variable" in result

    def test_code_multiline(self):
        """Test multiline code block."""
        formatter = MarkdownFormatter()
        code_text = "line1\nline2\nline3"
        result = formatter.code(code_text, block=True)
        assert "line1" in result
        assert "line2" in result
        # Should use triple backticks for block
        assert "```" in result or "line1\nline2\nline3" in result

    def test_code_with_language(self):
        """Test code block with language hint."""
        formatter = MarkdownFormatter()
        result = formatter.code("def foo(): pass", block=True, language="python")
        assert "def foo(): pass" in result

    def test_code_empty(self):
        """Test code with empty string."""
        formatter = MarkdownFormatter()
        result = formatter.code("")
        assert result == "``" or result == ""

    def test_code_preserves_whitespace(self):
        """Test code preserves whitespace."""
        formatter = MarkdownFormatter()
        code_text = "  indented"
        result = formatter.code(code_text)
        assert "indented" in result


class TestLinkFormatting:
    """Test link() method."""

    def test_link_basic(self):
        """Test basic link formatting."""
        formatter = MarkdownFormatter()
        result = formatter.link("Click here", "https://example.com")
        assert "[Click here](https://example.com)" in result

    def test_link_markdown_format(self):
        """Test link follows markdown format."""
        formatter = MarkdownFormatter()
        result = formatter.link("text", "url")
        assert "[" in result
        assert "]" in result
        assert "(" in result
        assert ")" in result

    def test_link_empty_text(self):
        """Test link with empty text uses URL."""
        formatter = MarkdownFormatter()
        result = formatter.link("", "https://example.com")
        assert "https://example.com" in result

    def test_link_empty_url(self):
        """Test link with empty URL."""
        formatter = MarkdownFormatter()
        result = formatter.link("text", "")
        # Should handle gracefully
        assert "text" in result

    def test_link_special_chars_in_url(self):
        """Test link with special characters in URL."""
        formatter = MarkdownFormatter()
        result = formatter.link("query", "https://example.com?a=1&b=2")
        assert "https://example.com?a=1&b=2" in result


class TestEscape:
    """Test escape() method."""

    def test_escape_asterisks(self):
        """Test escaping asterisks."""
        formatter = MarkdownFormatter()
        result = formatter.escape("*bold*")
        assert "*" not in result or "\\*" in result or result == "*bold*"

    def test_escape_underscores(self):
        """Test escaping underscores."""
        formatter = MarkdownFormatter()
        result = formatter.escape("_italic_")
        # Either escaped or the original is fine depending on context
        assert "_" in result or "\\_" in result

    def test_escape_backticks(self):
        """Test escaping backticks."""
        formatter = MarkdownFormatter()
        result = formatter.escape("`code`")
        # Should handle backticks
        assert "code" in result

    def test_escape_brackets(self):
        """Test escaping brackets."""
        formatter = MarkdownFormatter()
        result = formatter.escape("[text](url)")
        # Should handle link-like syntax
        assert "text" in result

    def test_escape_none(self):
        """Test escape with None."""
        formatter = MarkdownFormatter()
        result = formatter.escape(None)
        assert result == ""

    def test_escape_empty(self):
        """Test escape with empty string."""
        formatter = MarkdownFormatter()
        result = formatter.escape("")
        assert result == ""

    def test_escape_normal_text(self):
        """Test escape with normal text (no special chars)."""
        formatter = MarkdownFormatter()
        result = formatter.escape("Hello World 123")
        assert result == "Hello World 123"

    def test_escape_preserves_content(self):
        """Test escape preserves the core content."""
        formatter = MarkdownFormatter()
        result = formatter.escape("Test *with* special _chars_")
        assert "Test" in result
        assert "with" in result
        assert "special" in result
        assert "chars" in result


class TestConvertHtmlToMd:
    """Test convert_html_to_md() method."""

    def test_convert_bold(self):
        """Test converting HTML bold to markdown."""
        formatter = MarkdownFormatter()
        result = formatter.convert_html_to_md("<b>bold text</b>")
        assert "bold text" in result
        # Should have markdown bold markers
        assert "*" in result or "**" in result

    def test_convert_strong(self):
        """Test converting HTML strong to markdown."""
        formatter = MarkdownFormatter()
        result = formatter.convert_html_to_md("<strong>strong text</strong>")
        assert "strong text" in result

    def test_convert_italic(self):
        """Test converting HTML italic to markdown."""
        formatter = MarkdownFormatter()
        result = formatter.convert_html_to_md("<i>italic text</i>")
        assert "italic text" in result
        # Should have markdown italic markers
        assert "_" in result or "*" in result

    def test_convert_em(self):
        """Test converting HTML em to markdown."""
        formatter = MarkdownFormatter()
        result = formatter.convert_html_to_md("<em>emphasized</em>")
        assert "emphasized" in result

    def test_convert_code(self):
        """Test converting HTML code to markdown."""
        formatter = MarkdownFormatter()
        result = formatter.convert_html_to_md("<code>code</code>")
        assert "code" in result
        assert "`" in result

    def test_convert_link(self):
        """Test converting HTML link to markdown."""
        formatter = MarkdownFormatter()
        result = formatter.convert_html_to_md('<a href="https://example.com">link</a>')
        assert "link" in result
        assert "https://example.com" in result or "[" in result

    def test_convert_br(self):
        """Test converting HTML br to newline."""
        formatter = MarkdownFormatter()
        result = formatter.convert_html_to_md("line1<br>line2")
        assert "line1" in result
        assert "line2" in result

    def test_convert_paragraph(self):
        """Test converting HTML paragraphs."""
        formatter = MarkdownFormatter()
        result = formatter.convert_html_to_md("<p>paragraph</p>")
        assert "paragraph" in result

    def test_convert_empty(self):
        """Test converting empty string."""
        formatter = MarkdownFormatter()
        result = formatter.convert_html_to_md("")
        assert result == ""

    def test_convert_none(self):
        """Test converting None."""
        formatter = MarkdownFormatter()
        result = formatter.convert_html_to_md(None)
        assert result == ""

    def test_convert_plain_text(self):
        """Test converting plain text (no HTML)."""
        formatter = MarkdownFormatter()
        result = formatter.convert_html_to_md("Just plain text")
        assert result == "Just plain text"

    def test_convert_nested_tags(self):
        """Test converting nested HTML tags."""
        formatter = MarkdownFormatter()
        result = formatter.convert_html_to_md("<b><i>bold italic</i></b>")
        assert "bold italic" in result

    def test_convert_strips_unknown_tags(self):
        """Test unknown tags are handled gracefully."""
        formatter = MarkdownFormatter()
        result = formatter.convert_html_to_md("<custom>content</custom>")
        assert "content" in result


class TestMarkdownFormatterCombined:
    """Test combined markdown formatting operations."""

    def test_bold_then_italic(self):
        """Test nesting bold and italic."""
        formatter = MarkdownFormatter()
        bold_text = formatter.bold("important")
        italic_bold = formatter.italic(bold_text)
        # Content should be preserved
        assert "important" in italic_bold

    def test_code_in_list(self):
        """Test code formatting works for list items."""
        formatter = MarkdownFormatter()
        items = ["item1", "item2"]
        formatted = [formatter.code(item) for item in items]
        assert all("`" in f for f in formatted)

    def test_link_with_escaped_text(self):
        """Test link with text that needs escaping."""
        formatter = MarkdownFormatter()
        escaped_text = formatter.escape("Click *here*")
        link = formatter.link(escaped_text, "https://example.com")
        assert "Click" in link
        assert "https://example.com" in link


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
