"""
JARVIS Input Sanitizer Module

Provides the Sanitizer class for cleaning and sanitizing input data.

Methods:
- strip_html: Remove HTML tags and content
- escape_markdown: Escape Markdown special characters
- truncate: Truncate text to maximum length
- remove_null_bytes: Remove null bytes from text
- sanitize: Apply multiple sanitization methods

Usage:
    from core.validation.sanitizer import Sanitizer

    sanitizer = Sanitizer()

    # Strip HTML tags
    clean = sanitizer.strip_html("<script>alert('xss')</script>Hello")

    # Escape Markdown
    safe = sanitizer.escape_markdown("*bold* text")

    # Truncate with ellipsis
    short = sanitizer.truncate("Long text here", max_len=10)

    # Remove null bytes
    clean = sanitizer.remove_null_bytes("text\\x00with\\x00nulls")

    # Combined sanitization
    result = sanitizer.sanitize(
        text,
        strip_html=True,
        remove_nulls=True,
        escape_markdown=True,
        max_len=100
    )
"""

import html
import re
from typing import Optional


class Sanitizer:
    """
    Sanitizes input text to prevent injection attacks and ensure data integrity.

    All methods can be called both as instance methods and as static/class methods.

    Example:
        # Instance method
        sanitizer = Sanitizer()
        result = sanitizer.strip_html("<b>Bold</b>")

        # Static method
        result = Sanitizer.strip_html("<b>Bold</b>")
    """

    # Regex patterns for HTML stripping
    SCRIPT_PATTERN = re.compile(
        r'<script[^>]*>.*?</script>',
        re.IGNORECASE | re.DOTALL
    )
    STYLE_PATTERN = re.compile(
        r'<style[^>]*>.*?</style>',
        re.IGNORECASE | re.DOTALL
    )
    HTML_TAG_PATTERN = re.compile(r'<[^>]+>')
    EVENT_HANDLER_PATTERN = re.compile(
        r'\s*on\w+\s*=\s*["\'][^"\']*["\']',
        re.IGNORECASE
    )
    DATA_URI_PATTERN = re.compile(
        r'data:[^,]+,',
        re.IGNORECASE
    )
    SVG_PATTERN = re.compile(
        r'<svg[^>]*>.*?</svg>',
        re.IGNORECASE | re.DOTALL
    )

    # Markdown special characters to escape
    MARKDOWN_SPECIAL_CHARS = ['*', '_', '`', '[', ']', '#', '~', '>', '|', '-', '+', '.', '!']

    @staticmethod
    def strip_html(text: str) -> str:
        """
        Remove HTML tags and potentially dangerous content from text.

        This method removes:
        - Script tags and their content
        - Style tags and their content
        - SVG tags and their content
        - All other HTML tags
        - Event handler attributes
        - Data URIs

        Args:
            text: Text potentially containing HTML

        Returns:
            Text with HTML removed

        Example:
            >>> Sanitizer.strip_html("<p>Hello <b>World</b></p>")
            'Hello World'
            >>> Sanitizer.strip_html("<script>alert('xss')</script>Hello")
            'Hello'
        """
        if not text:
            return ""

        # Remove script tags and content
        result = Sanitizer.SCRIPT_PATTERN.sub('', text)

        # Remove style tags and content
        result = Sanitizer.STYLE_PATTERN.sub('', result)

        # Remove SVG tags and content
        result = Sanitizer.SVG_PATTERN.sub('', result)

        # Remove event handlers (before removing tags)
        result = Sanitizer.EVENT_HANDLER_PATTERN.sub('', result)

        # Remove data URIs
        result = Sanitizer.DATA_URI_PATTERN.sub('', result)

        # Remove remaining HTML tags
        result = Sanitizer.HTML_TAG_PATTERN.sub('', result)

        # Decode HTML entities
        result = html.unescape(result)

        # Clean up extra whitespace
        result = ' '.join(result.split())

        return result

    @staticmethod
    def escape_markdown(text: str) -> str:
        """
        Escape Markdown special characters to prevent formatting.

        Escapes: * _ ` [ ] # ~ > | - + . !

        Args:
            text: Text potentially containing Markdown

        Returns:
            Text with Markdown characters escaped

        Example:
            >>> Sanitizer.escape_markdown("*bold* text")
            '\\*bold\\* text'
        """
        if not text:
            return ""

        result = text
        for char in Sanitizer.MARKDOWN_SPECIAL_CHARS:
            result = result.replace(char, f'\\{char}')

        return result

    @staticmethod
    def truncate(
        text: str,
        max_len: int,
        suffix: str = "...",
        word_boundary: bool = False
    ) -> str:
        """
        Truncate text to a maximum length.

        Args:
            text: Text to truncate
            max_len: Maximum length including suffix
            suffix: String to append when truncating (default "...")
            word_boundary: If True, try to truncate at word boundary

        Returns:
            Truncated text

        Example:
            >>> Sanitizer.truncate("Hello World", 8)
            'Hello...'
            >>> Sanitizer.truncate("Hello World", 8, word_boundary=True)
            'Hello...'
        """
        if not text:
            return ""

        if len(text) <= max_len:
            return text

        # Calculate space available for actual text
        suffix_len = len(suffix)
        available_len = max_len - suffix_len

        if available_len <= 0:
            return suffix[:max_len]

        truncated = text[:available_len]

        if word_boundary:
            # Try to find the last space before the cutoff
            last_space = truncated.rfind(' ')
            if last_space > 0:
                truncated = truncated[:last_space]

        return truncated + suffix

    @staticmethod
    def remove_null_bytes(text: str) -> str:
        """
        Remove null bytes from text.

        Null bytes can cause issues in C-based systems and can be used
        in injection attacks.

        Args:
            text: Text potentially containing null bytes

        Returns:
            Text with null bytes removed

        Example:
            >>> Sanitizer.remove_null_bytes("Hello\\x00World")
            'HelloWorld'
        """
        if not text:
            return ""

        return text.replace('\x00', '')

    def sanitize(
        self,
        text: str,
        strip_html: bool = False,
        remove_nulls: bool = False,
        escape_markdown: bool = False,
        max_len: Optional[int] = None,
        truncate_suffix: str = "...",
        word_boundary: bool = False
    ) -> str:
        """
        Apply multiple sanitization methods to text.

        Args:
            text: Text to sanitize
            strip_html: Remove HTML tags and dangerous content
            remove_nulls: Remove null bytes
            escape_markdown: Escape Markdown special characters
            max_len: Maximum length (truncate if exceeded)
            truncate_suffix: Suffix for truncation (default "...")
            word_boundary: Truncate at word boundary if possible

        Returns:
            Sanitized text

        Example:
            sanitizer = Sanitizer()
            result = sanitizer.sanitize(
                "<p>Hello\\x00 **World**</p>",
                strip_html=True,
                remove_nulls=True,
                escape_markdown=True
            )
        """
        if not text:
            return ""

        result = text

        # Apply sanitization in order
        if remove_nulls:
            result = self.remove_null_bytes(result)

        if strip_html:
            result = self.strip_html(result)

        if escape_markdown:
            result = self.escape_markdown(result)

        if max_len is not None:
            result = self.truncate(result, max_len, truncate_suffix, word_boundary)

        return result

    @staticmethod
    def strip_control_chars(text: str) -> str:
        """
        Remove control characters (except newlines and tabs).

        Args:
            text: Text potentially containing control characters

        Returns:
            Text with control characters removed
        """
        if not text:
            return ""

        # Remove control characters (0x00-0x1F and 0x7F-0x9F) except:
        # - Tab (0x09)
        # - Newline (0x0A)
        # - Carriage return (0x0D)
        allowed = {'\t', '\n', '\r'}
        return ''.join(
            char for char in text
            if char in allowed or (ord(char) >= 32 and ord(char) < 127) or ord(char) >= 160
        )

    @staticmethod
    def normalize_whitespace(text: str) -> str:
        """
        Normalize whitespace: collapse multiple spaces, trim ends.

        Args:
            text: Text with potentially irregular whitespace

        Returns:
            Text with normalized whitespace
        """
        if not text:
            return ""

        return ' '.join(text.split())


# Re-export for convenient importing
__all__ = [
    "Sanitizer",
]
