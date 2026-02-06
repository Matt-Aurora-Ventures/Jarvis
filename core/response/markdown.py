"""
MarkdownFormatter - Markdown text formatting utilities.

Provides functions for creating formatted Markdown text including
bold, italic, code, links, and HTML-to-Markdown conversion.

Example:
    formatter = MarkdownFormatter()
    text = formatter.bold("Important") + " " + formatter.italic("note")
"""

from __future__ import annotations

import re
from typing import Optional


class MarkdownFormatter:
    """
    Markdown text formatting utilities.

    Supports standard Markdown formatting:
    - Bold: *text* or **text**
    - Italic: _text_
    - Code: `code` or ```code```
    - Links: [text](url)
    """

    def __init__(self, style: str = "single") -> None:
        """
        Initialize formatter.

        Args:
            style: Bold style - 'single' (*) or 'double' (**)
        """
        self.style = style

    def bold(self, text: Optional[str]) -> str:
        """
        Format text as bold.

        Args:
            text: Text to make bold

        Returns:
            Bold formatted text
        """
        if text is None:
            return ""
        if not text:
            return "**" if self.style == "double" else ""

        if self.style == "double":
            return f"**{text}**"
        return f"*{text}*"

    def italic(self, text: Optional[str]) -> str:
        """
        Format text as italic.

        Args:
            text: Text to make italic

        Returns:
            Italic formatted text
        """
        if text is None:
            return ""
        return f"_{text}_"

    def code(self, text: Optional[str], block: bool = False, lang: str = "") -> str:
        """
        Format text as code.

        Args:
            text: Code text
            block: Use code block (triple backticks)
            lang: Language for syntax highlighting

        Returns:
            Code formatted text
        """
        if text is None:
            return ""

        if block:
            return f"```{lang}\n{text}\n```"
        return f"`{text}`"

    def link(self, text: str, url: str) -> str:
        """
        Create a markdown link.

        Args:
            text: Link text
            url: Link URL

        Returns:
            Markdown link
        """
        return f"[{text}]({url})"

    def escape(self, text: str) -> str:
        """
        Escape markdown special characters.

        Args:
            text: Text to escape

        Returns:
            Escaped text
        """
        special_chars = ['*', '_', '`', '[', ']', '(', ')']
        for char in special_chars:
            text = text.replace(char, f'\\{char}')
        return text

    def unescape(self, text: str) -> str:
        """
        Remove markdown escape characters.

        Args:
            text: Text to unescape

        Returns:
            Unescaped text
        """
        return text.replace('\\', '')

    def strikethrough(self, text: Optional[str]) -> str:
        """
        Format text with strikethrough.

        Args:
            text: Text to strike through

        Returns:
            Strikethrough formatted text
        """
        if text is None:
            return ""
        return f"~{text}~"

    def convert_html_to_md(self, html: str) -> str:
        """
        Convert basic HTML to Markdown.

        Args:
            html: HTML text

        Returns:
            Markdown text
        """
        # Bold
        html = re.sub(r'<b>(.*?)</b>', r'*\1*', html)
        html = re.sub(r'<strong>(.*?)</strong>', r'*\1*', html)

        # Italic
        html = re.sub(r'<i>(.*?)</i>', r'_\1_', html)
        html = re.sub(r'<em>(.*?)</em>', r'_\1_', html)

        # Code
        html = re.sub(r'<code>(.*?)</code>', r'`\1`', html)

        # Links
        html = re.sub(r'<a href="(.*?)">(.*?)</a>', r'[\2](\1)', html)

        # Line breaks
        html = html.replace('<br>', '\n')
        html = html.replace('<br/>', '\n')
        html = html.replace('<br />', '\n')

        # Paragraphs
        html = re.sub(r'<p>(.*?)</p>', r'\1\n\n', html)

        return html.strip()

    def convert_md_to_html(self, md: str) -> str:
        """
        Convert basic Markdown to HTML.

        Args:
            md: Markdown text

        Returns:
            HTML text
        """
        # Bold
        md = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', md)
        md = re.sub(r'\*(.*?)\*', r'<b>\1</b>', md)

        # Italic
        md = re.sub(r'_(.*?)_', r'<i>\1</i>', md)

        # Code
        md = re.sub(r'`(.*?)`', r'<code>\1</code>', md)

        # Links
        md = re.sub(r'\[(.*?)\]\((.*?)\)', r'<a href="\2">\1</a>', md)

        return md
