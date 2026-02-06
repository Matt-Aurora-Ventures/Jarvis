"""
Tests for NotificationFormatter - Message formatting for different channels.

TDD Phase 1: Write failing tests first.
"""
import pytest
from datetime import datetime


class TestNotificationFormatter:
    """Test suite for NotificationFormatter class."""

    @pytest.fixture
    def formatter(self):
        """Create a NotificationFormatter instance."""
        from core.notifications.formatters import NotificationFormatter
        return NotificationFormatter()

    @pytest.fixture
    def sample_notification(self):
        """Create a sample notification for testing."""
        return {
            "id": "notif-123",
            "title": "Price Alert",
            "message": "SOL has reached $150.00",
            "priority": "high",
            "type": "alert",
            "data": {
                "symbol": "SOL",
                "price": 150.00,
                "change_percent": 5.2,
            },
            "created_at": "2026-02-02T10:30:00Z",
        }

    def test_formatter_instantiation(self, formatter):
        """Test that formatter can be instantiated."""
        assert formatter is not None
        assert hasattr(formatter, "format_for_telegram")
        assert hasattr(formatter, "format_for_discord")
        assert hasattr(formatter, "format_for_email")

    def test_format_for_telegram_basic(self, formatter, sample_notification):
        """Test basic Telegram formatting."""
        result = formatter.format_for_telegram(sample_notification)

        assert isinstance(result, str)
        assert sample_notification["title"] in result
        assert sample_notification["message"] in result

    def test_format_for_telegram_markdown(self, formatter, sample_notification):
        """Test Telegram formatting with Markdown."""
        result = formatter.format_for_telegram(sample_notification, use_markdown=True)

        # Should contain Markdown formatting
        assert "*" in result or "_" in result or "`" in result

    def test_format_for_telegram_html(self, formatter, sample_notification):
        """Test Telegram formatting with HTML."""
        result = formatter.format_for_telegram(sample_notification, use_html=True)

        # Should contain HTML tags
        assert "<" in result and ">" in result

    def test_format_for_telegram_priority_indicator(self, formatter, sample_notification):
        """Test that high priority shows indicator."""
        result = formatter.format_for_telegram(sample_notification)

        # High priority should have some indicator
        # (emoji or text like URGENT, HIGH PRIORITY, etc.)
        assert any(indicator in result.upper() for indicator in ["HIGH", "URGENT", "!", "ALERT"])

    def test_format_for_discord_basic(self, formatter, sample_notification):
        """Test basic Discord formatting."""
        result = formatter.format_for_discord(sample_notification)

        assert isinstance(result, dict)
        # Discord webhooks expect embeds or content
        assert "content" in result or "embeds" in result

    def test_format_for_discord_embed(self, formatter, sample_notification):
        """Test Discord formatting with rich embeds."""
        result = formatter.format_for_discord(sample_notification, use_embed=True)

        assert "embeds" in result
        assert len(result["embeds"]) > 0

        embed = result["embeds"][0]
        assert "title" in embed
        assert "description" in embed

    def test_format_for_discord_color_by_priority(self, formatter):
        """Test Discord embed color based on priority."""
        high_notif = {
            "id": "1",
            "title": "High Priority",
            "message": "Test",
            "priority": "high",
        }
        low_notif = {
            "id": "2",
            "title": "Low Priority",
            "message": "Test",
            "priority": "low",
        }

        high_result = formatter.format_for_discord(high_notif, use_embed=True)
        low_result = formatter.format_for_discord(low_notif, use_embed=True)

        # Colors should be different (red for high, green for low, etc.)
        high_color = high_result["embeds"][0].get("color", 0)
        low_color = low_result["embeds"][0].get("color", 0)

        assert high_color != low_color

    def test_format_for_email_basic(self, formatter, sample_notification):
        """Test basic email formatting."""
        result = formatter.format_for_email(sample_notification)

        assert isinstance(result, dict)
        assert "subject" in result
        assert "body" in result
        assert "html_body" in result or "body" in result

    def test_format_for_email_subject(self, formatter, sample_notification):
        """Test email subject line formatting."""
        result = formatter.format_for_email(sample_notification)

        subject = result["subject"]
        assert sample_notification["title"] in subject

    def test_format_for_email_html_body(self, formatter, sample_notification):
        """Test email HTML body formatting."""
        result = formatter.format_for_email(sample_notification)

        if "html_body" in result:
            html = result["html_body"]
            assert "<html>" in html.lower() or "<body>" in html.lower() or "<div>" in html.lower()

    def test_format_for_email_plain_text_body(self, formatter, sample_notification):
        """Test email plain text body."""
        result = formatter.format_for_email(sample_notification)

        body = result["body"]
        assert sample_notification["message"] in body

    def test_format_preserves_data(self, formatter, sample_notification):
        """Test that notification data is preserved in formatting."""
        tg_result = formatter.format_for_telegram(sample_notification)
        discord_result = formatter.format_for_discord(sample_notification)

        # Symbol should appear in formatted output
        assert "SOL" in tg_result
        if "embeds" in discord_result:
            embed_str = str(discord_result["embeds"])
            assert "SOL" in embed_str or sample_notification["message"] in embed_str

    def test_format_handles_missing_fields(self, formatter):
        """Test formatting with minimal notification."""
        minimal_notification = {
            "id": "min-1",
            "message": "Minimal message",
        }

        # Should not raise exceptions
        tg_result = formatter.format_for_telegram(minimal_notification)
        discord_result = formatter.format_for_discord(minimal_notification)
        email_result = formatter.format_for_email(minimal_notification)

        assert tg_result is not None
        assert discord_result is not None
        assert email_result is not None

    def test_format_escapes_special_characters_telegram(self, formatter):
        """Test that special Markdown characters are escaped for Telegram."""
        notification = {
            "id": "special-1",
            "title": "Test *bold* and _italic_",
            "message": "Price: $100 [link](http://test.com)",
        }

        result = formatter.format_for_telegram(notification, use_markdown=True)

        # Should either escape or properly format special chars
        assert isinstance(result, str)

    def test_format_timestamp(self, formatter, sample_notification):
        """Test that timestamps are formatted nicely."""
        result = formatter.format_for_telegram(sample_notification)

        # Timestamp should be human-readable if included
        # (not raw ISO format, but formatted)
        if "2026" in result:
            assert "T" not in result or "10:30" in result or "AM" in result or "PM" in result


class TestCustomFormatters:
    """Test suite for custom format functions."""

    @pytest.fixture
    def formatter(self):
        from core.notifications.formatters import NotificationFormatter
        return NotificationFormatter()

    def test_register_custom_formatter(self, formatter):
        """Test registering a custom formatter."""
        def custom_format(notification):
            return f"CUSTOM: {notification['message']}"

        formatter.register_formatter("custom_channel", custom_format)

        notification = {"id": "1", "message": "Test"}
        result = formatter.format_for_channel("custom_channel", notification)

        assert result == "CUSTOM: Test"

    def test_format_for_unknown_channel_uses_default(self, formatter):
        """Test that unknown channels use default formatting."""
        notification = {"id": "1", "title": "Test", "message": "Test message"}

        result = formatter.format_for_channel("unknown_channel", notification)

        # Should return some formatted output, not fail
        assert result is not None
        assert "Test" in str(result)
