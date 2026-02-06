"""
Notification Formatters - Format notifications for different channels.

Provides channel-specific formatting for:
- Telegram: Markdown/HTML formatting
- Discord: Rich embeds with colors
- Email: HTML and plain text bodies
"""
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional
import html
import re


class NotificationFormatter:
    """
    Format notifications for different delivery channels.

    Supports:
    - Telegram: Markdown or HTML formatted messages
    - Discord: Rich embed format with colors
    - Email: Subject line, plain text, and HTML body
    """

    # Priority colors for Discord embeds (decimal format)
    PRIORITY_COLORS = {
        "critical": 15158332,  # Red (#E74C3C)
        "high": 15105570,      # Orange (#E67E22)
        "medium": 16776960,    # Yellow (#FFFF00)
        "low": 3066993,        # Green (#2ECC71)
    }

    # Priority indicators for text messages
    PRIORITY_INDICATORS = {
        "critical": "[CRITICAL]",
        "high": "[HIGH PRIORITY]",
        "medium": "[ALERT]",
        "low": "[INFO]",
    }

    def __init__(self):
        """Initialize the formatter with custom formatter registry."""
        self._custom_formatters: Dict[str, Callable] = {}

    def register_formatter(self, channel: str, formatter_func: Callable) -> None:
        """
        Register a custom formatter for a channel.

        Args:
            channel: Channel name
            formatter_func: Function that takes a notification dict and returns formatted output
        """
        self._custom_formatters[channel] = formatter_func

    def format_for_channel(self, channel: str, notification: Dict[str, Any]) -> Any:
        """
        Format a notification for a specific channel.

        Uses custom formatter if registered, otherwise falls back to default.

        Args:
            channel: Channel name
            notification: Notification dict

        Returns:
            Formatted notification (type depends on channel)
        """
        if channel in self._custom_formatters:
            return self._custom_formatters[channel](notification)

        # Fallback formatters
        if channel == "telegram":
            return self.format_for_telegram(notification)
        elif channel == "discord":
            return self.format_for_discord(notification)
        elif channel == "email":
            return self.format_for_email(notification)
        else:
            # Default: simple string formatting
            return self._format_default(notification)

    def format_for_telegram(
        self,
        notification: Dict[str, Any],
        use_markdown: bool = False,
        use_html: bool = False
    ) -> str:
        """
        Format a notification for Telegram.

        Args:
            notification: Notification dict with title, message, priority, etc.
            use_markdown: Use Telegram MarkdownV2 formatting
            use_html: Use HTML formatting (takes precedence over markdown)

        Returns:
            Formatted string for Telegram API
        """
        title = notification.get("title", "Notification")
        message = notification.get("message", "")
        priority = notification.get("priority", "medium")
        data = notification.get("data", {})

        # Get priority indicator
        indicator = self.PRIORITY_INDICATORS.get(priority, "")

        if use_html:
            return self._format_telegram_html(title, message, indicator, data, notification)
        elif use_markdown:
            return self._format_telegram_markdown(title, message, indicator, data, notification)
        else:
            return self._format_telegram_plain(title, message, indicator, data, notification)

    def _format_telegram_plain(
        self,
        title: str,
        message: str,
        indicator: str,
        data: Dict[str, Any],
        notification: Dict[str, Any]
    ) -> str:
        """Format plain text for Telegram."""
        lines = []

        if indicator:
            lines.append(indicator)

        lines.append(title)
        lines.append("")
        lines.append(message)

        # Add data fields if present
        if data and isinstance(data, dict):
            symbol = data.get("symbol")
            if symbol:
                lines.append(f"\nSymbol: {symbol}")

        # Add timestamp if present
        timestamp = notification.get("created_at") or notification.get("timestamp")
        if timestamp:
            formatted_time = self._format_timestamp(timestamp)
            lines.append(f"\nTime: {formatted_time}")

        return "\n".join(lines)

    def _format_telegram_markdown(
        self,
        title: str,
        message: str,
        indicator: str,
        data: Dict[str, Any],
        notification: Dict[str, Any]
    ) -> str:
        """Format Markdown for Telegram (MarkdownV2)."""
        lines = []

        # Escape special characters for MarkdownV2
        def escape_md(text: str) -> str:
            special_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
            for char in special_chars:
                text = text.replace(char, f'\\{char}')
            return text

        if indicator:
            lines.append(f"*{escape_md(indicator)}*")

        lines.append(f"*{escape_md(title)}*")
        lines.append("")
        lines.append(escape_md(message))

        # Add data fields
        if data and isinstance(data, dict):
            symbol = data.get("symbol")
            if symbol:
                lines.append(f"\n_Symbol:_ `{escape_md(str(symbol))}`")

        return "\n".join(lines)

    def _format_telegram_html(
        self,
        title: str,
        message: str,
        indicator: str,
        data: Dict[str, Any],
        notification: Dict[str, Any]
    ) -> str:
        """Format HTML for Telegram."""
        lines = []

        # Escape HTML
        title = html.escape(title)
        message = html.escape(message)

        if indicator:
            lines.append(f"<b>{html.escape(indicator)}</b>")

        lines.append(f"<b>{title}</b>")
        lines.append("")
        lines.append(message)

        # Add data fields
        if data and isinstance(data, dict):
            symbol = data.get("symbol")
            if symbol:
                lines.append(f"\n<i>Symbol:</i> <code>{html.escape(str(symbol))}</code>")

        return "\n".join(lines)

    def format_for_discord(
        self,
        notification: Dict[str, Any],
        use_embed: bool = True
    ) -> Dict[str, Any]:
        """
        Format a notification for Discord webhook.

        Args:
            notification: Notification dict
            use_embed: Use Discord rich embed (default True)

        Returns:
            Dict suitable for Discord webhook payload
        """
        title = notification.get("title", "Notification")
        message = notification.get("message", "")
        priority = notification.get("priority", "medium")
        data = notification.get("data", {})

        if not use_embed:
            # Simple content message
            indicator = self.PRIORITY_INDICATORS.get(priority, "")
            content = f"{indicator} **{title}**\n{message}"
            return {"content": content}

        # Rich embed format
        color = self.PRIORITY_COLORS.get(priority, self.PRIORITY_COLORS["medium"])

        embed = {
            "title": title,
            "description": message,
            "color": color,
            "timestamp": datetime.now().isoformat(),
        }

        # Add fields from data
        fields = []
        if data and isinstance(data, dict):
            for key, value in list(data.items())[:10]:  # Limit to 10 fields
                if isinstance(value, (str, int, float)):
                    fields.append({
                        "name": key.replace("_", " ").title(),
                        "value": str(value),
                        "inline": True,
                    })

        if fields:
            embed["fields"] = fields

        # Add footer with priority
        embed["footer"] = {
            "text": f"Priority: {priority.upper()}"
        }

        return {"embeds": [embed]}

    def format_for_email(self, notification: Dict[str, Any]) -> Dict[str, Any]:
        """
        Format a notification for email.

        Args:
            notification: Notification dict

        Returns:
            Dict with subject, body (plain text), and html_body
        """
        title = notification.get("title", "Notification")
        message = notification.get("message", "")
        priority = notification.get("priority", "medium")
        data = notification.get("data", {})

        # Subject line
        indicator = self.PRIORITY_INDICATORS.get(priority, "")
        subject = f"{indicator} {title}".strip()

        # Plain text body
        body_lines = [
            title,
            "=" * len(title),
            "",
            message,
        ]

        if data and isinstance(data, dict):
            body_lines.append("")
            body_lines.append("Details:")
            for key, value in data.items():
                body_lines.append(f"  - {key.replace('_', ' ').title()}: {value}")

        timestamp = notification.get("created_at") or notification.get("timestamp")
        if timestamp:
            formatted_time = self._format_timestamp(timestamp)
            body_lines.append("")
            body_lines.append(f"Time: {formatted_time}")

        body = "\n".join(body_lines)

        # HTML body
        html_body = self._generate_email_html(title, message, priority, data, notification)

        return {
            "subject": subject,
            "body": body,
            "html_body": html_body,
        }

    def _generate_email_html(
        self,
        title: str,
        message: str,
        priority: str,
        data: Dict[str, Any],
        notification: Dict[str, Any]
    ) -> str:
        """Generate HTML body for email."""
        # Priority colors (CSS hex)
        priority_css_colors = {
            "critical": "#E74C3C",
            "high": "#E67E22",
            "medium": "#F39C12",
            "low": "#2ECC71",
        }

        color = priority_css_colors.get(priority, "#3498DB")

        # Escape HTML
        title_html = html.escape(title)
        message_html = html.escape(message).replace("\n", "<br>")

        html_parts = [
            "<!DOCTYPE html>",
            "<html>",
            "<head>",
            "<style>",
            "body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; }",
            ".container { max-width: 600px; margin: 0 auto; padding: 20px; }",
            f".header {{ background-color: {color}; color: white; padding: 20px; border-radius: 5px 5px 0 0; }}",
            ".content { background-color: #f9f9f9; padding: 20px; border: 1px solid #ddd; }",
            ".details { margin-top: 20px; }",
            ".details dt { font-weight: bold; }",
            ".footer { margin-top: 20px; font-size: 12px; color: #666; }",
            "</style>",
            "</head>",
            "<body>",
            "<div class='container'>",
            f"<div class='header'><h2>{title_html}</h2></div>",
            "<div class='content'>",
            f"<p>{message_html}</p>",
        ]

        # Add data details
        if data and isinstance(data, dict):
            html_parts.append("<div class='details'>")
            html_parts.append("<dl>")
            for key, value in data.items():
                key_html = html.escape(key.replace("_", " ").title())
                value_html = html.escape(str(value))
                html_parts.append(f"<dt>{key_html}</dt><dd>{value_html}</dd>")
            html_parts.append("</dl>")
            html_parts.append("</div>")

        html_parts.extend([
            "</div>",
            "<div class='footer'>",
            f"<p>Priority: {priority.upper()}</p>",
            "</div>",
            "</div>",
            "</body>",
            "</html>",
        ])

        return "\n".join(html_parts)

    def _format_default(self, notification: Dict[str, Any]) -> str:
        """Default formatting for unknown channels."""
        title = notification.get("title", "Notification")
        message = notification.get("message", "")
        priority = notification.get("priority", "medium")

        return f"[{priority.upper()}] {title}\n\n{message}"

    def _format_timestamp(self, timestamp: str) -> str:
        """Format ISO timestamp to human-readable string."""
        try:
            if isinstance(timestamp, str):
                # Parse ISO format
                dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
            else:
                dt = timestamp

            return dt.strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            return str(timestamp)
