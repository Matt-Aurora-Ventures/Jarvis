"""
Tests for NotificationDispatcher - Multi-channel alert dispatch system.

TDD Phase 1: Write failing tests first.
"""
import asyncio
import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
from typing import List, Dict, Any


class TestNotificationDispatcher:
    """Test suite for NotificationDispatcher class."""

    @pytest.fixture
    def dispatcher(self):
        """Create a NotificationDispatcher instance."""
        from core.notifications.dispatcher import NotificationDispatcher
        return NotificationDispatcher()

    @pytest.fixture
    def sample_notification(self):
        """Create a sample notification dict for testing."""
        return {
            "id": "notif-123",
            "title": "Test Alert",
            "message": "This is a test notification",
            "priority": "high",
            "type": "alert",
            "data": {"key": "value"},
            "created_at": datetime.now().isoformat(),
        }

    def test_dispatcher_instantiation(self, dispatcher):
        """Test that dispatcher can be instantiated."""
        assert dispatcher is not None
        assert hasattr(dispatcher, "send")
        assert hasattr(dispatcher, "send_urgent")
        assert hasattr(dispatcher, "get_delivery_status")
        assert hasattr(dispatcher, "retry_failed")

    @pytest.mark.asyncio
    async def test_send_to_single_channel(self, dispatcher, sample_notification):
        """Test sending notification to a single channel."""
        # Register a mock channel
        mock_channel = AsyncMock()
        mock_channel.send.return_value = {"success": True, "message_id": "msg-1"}
        dispatcher.register_channel("telegram", mock_channel)

        result = await dispatcher.send(sample_notification, ["telegram"])

        assert result["success"] is True
        assert "telegram" in result["channels"]
        mock_channel.send.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_to_multiple_channels(self, dispatcher, sample_notification):
        """Test sending notification to multiple channels."""
        mock_telegram = AsyncMock()
        mock_telegram.send.return_value = {"success": True}
        mock_discord = AsyncMock()
        mock_discord.send.return_value = {"success": True}

        dispatcher.register_channel("telegram", mock_telegram)
        dispatcher.register_channel("discord", mock_discord)

        result = await dispatcher.send(sample_notification, ["telegram", "discord"])

        assert result["success"] is True
        assert len(result["channels"]) == 2
        mock_telegram.send.assert_called_once()
        mock_discord.send.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_urgent_to_all_channels(self, dispatcher, sample_notification):
        """Test that send_urgent sends to all registered channels."""
        mock_telegram = AsyncMock()
        mock_telegram.send.return_value = {"success": True}
        mock_discord = AsyncMock()
        mock_discord.send.return_value = {"success": True}
        mock_email = AsyncMock()
        mock_email.send.return_value = {"success": True}

        dispatcher.register_channel("telegram", mock_telegram)
        dispatcher.register_channel("discord", mock_discord)
        dispatcher.register_channel("email", mock_email)

        result = await dispatcher.send_urgent(sample_notification)

        assert result["success"] is True
        assert len(result["channels"]) == 3
        mock_telegram.send.assert_called_once()
        mock_discord.send.assert_called_once()
        mock_email.send.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_delivery_status(self, dispatcher, sample_notification):
        """Test getting delivery status for a notification."""
        mock_channel = AsyncMock()
        mock_channel.send.return_value = {"success": True, "message_id": "msg-123"}
        dispatcher.register_channel("telegram", mock_channel)

        await dispatcher.send(sample_notification, ["telegram"])

        status = dispatcher.get_delivery_status(sample_notification["id"])

        assert status is not None
        assert "telegram" in status["channels"]
        assert status["channels"]["telegram"]["success"] is True

    @pytest.mark.asyncio
    async def test_get_delivery_status_not_found(self, dispatcher):
        """Test getting status for non-existent notification."""
        status = dispatcher.get_delivery_status("nonexistent-id")
        assert status is None

    @pytest.mark.asyncio
    async def test_retry_failed_notification(self, dispatcher, sample_notification):
        """Test retrying a failed notification."""
        call_count = 0

        async def flaky_send(notification):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return {"success": False, "error": "Temporary failure"}
            return {"success": True}

        mock_channel = AsyncMock(side_effect=flaky_send)
        mock_channel.send = flaky_send
        dispatcher.register_channel("telegram", mock_channel)

        # First send fails
        result1 = await dispatcher.send(sample_notification, ["telegram"])
        assert result1["channels"]["telegram"]["success"] is False

        # Retry succeeds
        result2 = await dispatcher.retry_failed(sample_notification["id"])
        assert result2["success"] is True

    @pytest.mark.asyncio
    async def test_partial_channel_failure(self, dispatcher, sample_notification):
        """Test handling when some channels succeed and others fail."""
        mock_telegram = AsyncMock()
        mock_telegram.send.return_value = {"success": True}
        mock_discord = AsyncMock()
        mock_discord.send.return_value = {"success": False, "error": "Connection failed"}

        dispatcher.register_channel("telegram", mock_telegram)
        dispatcher.register_channel("discord", mock_discord)

        result = await dispatcher.send(sample_notification, ["telegram", "discord"])

        # Overall success is partial
        assert result["partial"] is True
        assert result["channels"]["telegram"]["success"] is True
        assert result["channels"]["discord"]["success"] is False

    @pytest.mark.asyncio
    async def test_send_with_formatting(self, dispatcher, sample_notification):
        """Test that notifications are formatted before sending."""
        from core.notifications.formatters import NotificationFormatter

        mock_channel = AsyncMock()
        mock_channel.send.return_value = {"success": True}
        mock_channel.channel_type = "telegram"
        dispatcher.register_channel("telegram", mock_channel)

        with patch.object(NotificationFormatter, "format_for_telegram") as mock_format:
            mock_format.return_value = "Formatted message"
            await dispatcher.send(sample_notification, ["telegram"])
            mock_format.assert_called_once()

    def test_register_channel(self, dispatcher):
        """Test registering a channel."""
        mock_channel = MagicMock()
        dispatcher.register_channel("test_channel", mock_channel)

        assert dispatcher.get_channel("test_channel") is mock_channel

    def test_unregister_channel(self, dispatcher):
        """Test unregistering a channel."""
        mock_channel = MagicMock()
        dispatcher.register_channel("test_channel", mock_channel)
        dispatcher.unregister_channel("test_channel")

        assert dispatcher.get_channel("test_channel") is None

    def test_list_channels(self, dispatcher):
        """Test listing all registered channels."""
        mock_channel1 = MagicMock()
        mock_channel2 = MagicMock()
        dispatcher.register_channel("channel1", mock_channel1)
        dispatcher.register_channel("channel2", mock_channel2)

        channels = dispatcher.list_channels()

        assert "channel1" in channels
        assert "channel2" in channels
