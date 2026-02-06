"""
ResponseBuilder - Fluent text builder for message composition.

Provides a chainable interface for building formatted messages with
Markdown support for Telegram and other platforms.

Example:
    builder = ResponseBuilder()
    message = (
        builder
        .bold("Trade Alert")
        .newline()
        .text("Token: ").code("BONK")
        .newline()
        .text("Action: ").bold("BUY")
        .build()
    )
"""

from __future__ import annotations

import re
from typing import List, Optional, Union


# Characters that need escaping in Telegram Markdown
MARKDOWN_SPECIAL_CHARS = ['*', '_', '`', '[', ']', '(', ')', '~', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']


def _escape_markdown(text: str) -> str:
    """Escape markdown special characters."""
    for char in MARKDOWN_SPECIAL_CHARS:
        text = text.replace(char, f'\\{char}')
    return text


class ResponseBuilder:
    """
    Fluent text builder for composing formatted messages.

    Supports method chaining for intuitive message construction:
        builder.text("Hello ").bold("World").newline().text("!")

    All methods return self to enable chaining except build() which
    returns the final string.
    """

    def __init__(self) -> None:
        """Initialize empty builder."""
        self._parts: List[str] = []
        self._template: Optional[str] = None
        self._template_vars: dict = {}

    def text(self, content: str, escape: bool = True) -> ResponseBuilder:
        """
        Add plain text content.

        Args:
            content: Text to add
            escape: Whether to escape markdown characters (default True)

        Returns:
            self for chaining
        """
        if escape:
            # Only escape potential markdown conflicts
            content = content.replace('*', '\\*')
        self._parts.append(content)
        return self

    def bold(self, content: str) -> ResponseBuilder:
        """
        Add bold text.

        Args:
            content: Text to make bold

        Returns:
            self for chaining
        """
        self._parts.append(f"*{content}*")
        return self

    def italic(self, content: str) -> ResponseBuilder:
        """
        Add italic text.

        Args:
            content: Text to make italic

        Returns:
            self for chaining
        """
        self._parts.append(f"_{content}_")
        return self

    def code(
        self,
        content: str,
        block: bool = False,
        lang: Optional[str] = None
    ) -> ResponseBuilder:
        """
        Add code (inline or block).

        Args:
            content: Code content
            block: If True, use code block (triple backticks)
            lang: Language for syntax highlighting (only for blocks)

        Returns:
            self for chaining
        """
        if block:
            lang_spec = lang if lang else ""
            self._parts.append(f"```{lang_spec}\n{content}\n```")
        else:
            self._parts.append(f"`{content}`")
        return self

    def link(self, text: str, url: str) -> ResponseBuilder:
        """
        Add a markdown link.

        Args:
            text: Link display text
            url: URL to link to

        Returns:
            self for chaining
        """
        self._parts.append(f"[{text}]({url})")
        return self

    def newline(self, count: int = 1) -> ResponseBuilder:
        """
        Add newline character(s).

        Args:
            count: Number of newlines to add

        Returns:
            self for chaining
        """
        self._parts.append("\n" * count)
        return self

    def line(self, content: str) -> ResponseBuilder:
        """
        Add text followed by a newline.

        Args:
            content: Text to add as a line

        Returns:
            self for chaining
        """
        self._parts.append(content)
        self._parts.append("\n")
        return self

    def build(self) -> str:
        """
        Build and return the final string.

        Returns:
            Composed message string
        """
        result = "".join(self._parts)

        # Apply template formatting if set
        if self._template:
            result = self._template.format(**self._template_vars)

        return result

    def clear(self) -> ResponseBuilder:
        """
        Clear all content and reset builder.

        Returns:
            self for chaining
        """
        self._parts = []
        self._template = None
        self._template_vars = {}
        return self

    def __str__(self) -> str:
        """Return built string when converted to str."""
        return self.build()

    def format(self, **kwargs) -> ResponseBuilder:
        """
        Set template variables for formatting.

        Used with from_template() for variable substitution.

        Args:
            **kwargs: Variable name-value pairs

        Returns:
            self for chaining
        """
        self._template_vars.update(kwargs)
        return self

    @classmethod
    def from_template(cls, template: str) -> ResponseBuilder:
        """
        Create builder from a template string.

        Args:
            template: Template with {variable} placeholders

        Returns:
            New ResponseBuilder with template set
        """
        builder = cls()
        builder._template = template
        return builder

    @classmethod
    def join(
        cls,
        builders: List[ResponseBuilder],
        separator: str = ""
    ) -> ResponseBuilder:
        """
        Join multiple builders into one.

        Args:
            builders: List of ResponseBuilder instances
            separator: String to place between each builder's content

        Returns:
            New ResponseBuilder with combined content
        """
        result = cls()
        parts = [b.build() for b in builders]
        result._parts = [separator.join(parts)]
        return result


# Convenience function for quick responses
def response() -> ResponseBuilder:
    """
    Create a new ResponseBuilder.

    Convenience function for quick builder creation.

    Returns:
        New ResponseBuilder instance
    """
    return ResponseBuilder()
