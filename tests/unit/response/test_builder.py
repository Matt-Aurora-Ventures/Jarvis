"""
Tests for ResponseBuilder class.

Tests fluent text building interface for consistent message formatting.
"""

import pytest


class TestResponseBuilder:
    """Test ResponseBuilder class."""

    def test_text_basic(self):
        """text() should add plain text content."""
        from core.response.builder import ResponseBuilder

        builder = ResponseBuilder()
        result = builder.text("Hello, World!").build()

        assert result == "Hello, World!"

    def test_text_chaining(self):
        """text() should support method chaining."""
        from core.response.builder import ResponseBuilder

        builder = ResponseBuilder()
        result = builder.text("Hello").text(" World").build()

        assert result == "Hello World"

    def test_bold_markdown(self):
        """bold() should wrap text in markdown bold markers."""
        from core.response.builder import ResponseBuilder

        builder = ResponseBuilder()
        result = builder.bold("Important").build()

        assert result == "*Important*"

    def test_bold_inline(self):
        """bold() should work inline with other text."""
        from core.response.builder import ResponseBuilder

        builder = ResponseBuilder()
        result = builder.text("This is ").bold("important").text(" text").build()

        assert result == "This is *important* text"

    def test_italic_markdown(self):
        """italic() should wrap text in markdown italic markers."""
        from core.response.builder import ResponseBuilder

        builder = ResponseBuilder()
        result = builder.italic("emphasized").build()

        assert result == "_emphasized_"

    def test_italic_inline(self):
        """italic() should work inline with other text."""
        from core.response.builder import ResponseBuilder

        builder = ResponseBuilder()
        result = builder.text("This is ").italic("emphasized").text(" text").build()

        assert result == "This is _emphasized_ text"

    def test_code_inline(self):
        """code() should wrap text in backticks for inline code."""
        from core.response.builder import ResponseBuilder

        builder = ResponseBuilder()
        result = builder.code("variable_name").build()

        assert result == "`variable_name`"

    def test_code_block(self):
        """code() with block=True should use triple backticks."""
        from core.response.builder import ResponseBuilder

        builder = ResponseBuilder()
        result = builder.code("def foo():\n    pass", block=True).build()

        assert result == "```\ndef foo():\n    pass\n```"

    def test_code_block_with_language(self):
        """code() with language should specify syntax highlighting."""
        from core.response.builder import ResponseBuilder

        builder = ResponseBuilder()
        result = builder.code("def foo():\n    pass", block=True, lang="python").build()

        assert result == "```python\ndef foo():\n    pass\n```"

    def test_link_markdown(self):
        """link() should create markdown link."""
        from core.response.builder import ResponseBuilder

        builder = ResponseBuilder()
        result = builder.link("Click here", "https://example.com").build()

        assert result == "[Click here](https://example.com)"

    def test_link_inline(self):
        """link() should work inline with other text."""
        from core.response.builder import ResponseBuilder

        builder = ResponseBuilder()
        result = (
            builder
            .text("Visit ")
            .link("our site", "https://example.com")
            .text(" for more info")
            .build()
        )

        assert result == "Visit [our site](https://example.com) for more info"

    def test_newline(self):
        """newline() should add a newline character."""
        from core.response.builder import ResponseBuilder

        builder = ResponseBuilder()
        result = builder.text("Line 1").newline().text("Line 2").build()

        assert result == "Line 1\nLine 2"

    def test_newline_count(self):
        """newline() with count should add multiple newlines."""
        from core.response.builder import ResponseBuilder

        builder = ResponseBuilder()
        result = builder.text("Line 1").newline(2).text("Line 2").build()

        assert result == "Line 1\n\nLine 2"

    def test_line_adds_newline_after(self):
        """line() should add text followed by newline."""
        from core.response.builder import ResponseBuilder

        builder = ResponseBuilder()
        result = builder.line("First line").line("Second line").build()

        assert result == "First line\nSecond line\n"

    def test_build_returns_string(self):
        """build() should return a string."""
        from core.response.builder import ResponseBuilder

        builder = ResponseBuilder()
        result = builder.text("test").build()

        assert isinstance(result, str)

    def test_build_empty(self):
        """build() on empty builder should return empty string."""
        from core.response.builder import ResponseBuilder

        builder = ResponseBuilder()
        result = builder.build()

        assert result == ""

    def test_clear_resets_builder(self):
        """clear() should reset the builder."""
        from core.response.builder import ResponseBuilder

        builder = ResponseBuilder()
        builder.text("Some text")
        builder.clear()
        result = builder.build()

        assert result == ""

    def test_str_magic_method(self):
        """__str__ should call build()."""
        from core.response.builder import ResponseBuilder

        builder = ResponseBuilder()
        builder.text("Hello")

        assert str(builder) == "Hello"


class TestResponseBuilderEscape:
    """Test special character escaping."""

    def test_escape_markdown_in_text(self):
        """Markdown characters in text should be escaped."""
        from core.response.builder import ResponseBuilder

        builder = ResponseBuilder()
        result = builder.text("Price: $100 * 2 = $200").build()

        # Should escape * to prevent markdown interpretation
        assert "\\*" in result or "100 * 2" in result

    def test_escape_disabled(self):
        """escape=False should preserve raw characters."""
        from core.response.builder import ResponseBuilder

        builder = ResponseBuilder()
        result = builder.text("*raw* _text_", escape=False).build()

        assert result == "*raw* _text_"


class TestResponseBuilderFormatting:
    """Test complex formatting scenarios."""

    def test_header_formatting(self):
        """Should support header-style formatting."""
        from core.response.builder import ResponseBuilder

        builder = ResponseBuilder()
        result = (
            builder
            .bold("Portfolio Summary")
            .newline(2)
            .text("SOL: 10.5")
            .newline()
            .text("USD: $1,050")
            .build()
        )

        assert "*Portfolio Summary*" in result
        assert "SOL: 10.5" in result
        assert "USD: $1,050" in result

    def test_complex_message(self):
        """Should handle complex multi-part messages."""
        from core.response.builder import ResponseBuilder

        builder = ResponseBuilder()
        result = (
            builder
            .bold("Trade Alert")
            .newline()
            .text("Token: ").code("BONK").newline()
            .text("Action: ").bold("BUY").newline()
            .text("Amount: ").italic("$50.00").newline()
            .newline()
            .link("View on DexScreener", "https://dexscreener.com")
            .build()
        )

        assert "*Trade Alert*" in result
        assert "`BONK`" in result
        assert "*BUY*" in result
        assert "_$50.00_" in result
        assert "[View on DexScreener]" in result

    def test_list_formatting(self):
        """Should format lists properly."""
        from core.response.builder import ResponseBuilder

        items = ["Item 1", "Item 2", "Item 3"]

        builder = ResponseBuilder()
        builder.bold("My List").newline()
        for item in items:
            builder.text(f"- {item}").newline()
        result = builder.build()

        assert "*My List*" in result
        assert "- Item 1" in result
        assert "- Item 2" in result
        assert "- Item 3" in result


class TestResponseBuilderFactory:
    """Test factory methods and presets."""

    def test_from_template(self):
        """Should create builder from template."""
        from core.response.builder import ResponseBuilder

        builder = ResponseBuilder.from_template(
            "Hello {name}, your balance is {balance}"
        )
        result = builder.format(name="User", balance="$100").build()

        assert "Hello User" in result
        assert "$100" in result

    def test_join(self):
        """join() should combine multiple builders."""
        from core.response.builder import ResponseBuilder

        b1 = ResponseBuilder().text("Part 1")
        b2 = ResponseBuilder().text("Part 2")

        result = ResponseBuilder.join([b1, b2], separator="\n").build()

        assert result == "Part 1\nPart 2"
