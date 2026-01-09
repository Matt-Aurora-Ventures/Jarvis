"""
Tests for Telegram plugin.

Tests cover:
- Plugin lifecycle
- PAE component registration
- Action functionality
- Provider functionality
- Event handling
"""

import asyncio
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# Import plugin components directly for testing
from plugins.telegram.main import (
    TelegramPlugin,
    SendMessageAction,
    BroadcastReportAction,
    ManageChatAction,
    BotStatusProvider,
)


# =============================================================================
# Test Actions
# =============================================================================

class TestSendMessageAction:
    """Test send message action."""

    @pytest.mark.asyncio
    async def test_requires_message(self):
        """Should require message parameter."""
        action = SendMessageAction("test", {})

        with pytest.raises(ValueError):
            await action.execute({})

    @pytest.mark.asyncio
    async def test_returns_error_without_bot(self):
        """Should return error when bot not initialized."""
        action = SendMessageAction("test", {})

        result = await action.execute({"message": "Hello"})

        assert result["success"] is False
        assert "error" in result

    @pytest.mark.asyncio
    async def test_sends_to_specific_chat(self):
        """Should send message to specific chat."""
        action = SendMessageAction("test", {})

        mock_bot = MagicMock()
        mock_bot.send_message = AsyncMock(return_value=True)
        action.set_bot(mock_bot)

        result = await action.execute({
            "chat_id": 12345,
            "message": "Hello",
        })

        assert result["success"] is True
        assert result["chat_id"] == 12345
        mock_bot.send_message.assert_called_once_with(12345, "Hello")

    @pytest.mark.asyncio
    async def test_broadcasts_without_chat_id(self):
        """Should broadcast to all chats when no chat_id."""
        action = SendMessageAction("test", {})

        mock_bot = MagicMock()
        mock_bot.config = {"chat_ids": [111, 222, 333]}
        mock_bot.send_message = AsyncMock(return_value=True)
        action.set_bot(mock_bot)

        result = await action.execute({"message": "Broadcast"})

        assert result["success"] is True
        assert result["sent_count"] == 3
        assert result["total_chats"] == 3


class TestBroadcastReportAction:
    """Test broadcast report action."""

    @pytest.mark.asyncio
    async def test_returns_error_without_bot(self):
        """Should return error when bot not initialized."""
        action = BroadcastReportAction("test", {})

        result = await action.execute({})

        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_broadcasts_report(self):
        """Should broadcast sentiment report."""
        action = BroadcastReportAction("test", {})

        mock_bot = MagicMock()
        mock_bot.broadcast_report = AsyncMock(return_value=3)
        action.set_bot(mock_bot)

        result = await action.execute({})

        assert result["success"] is True
        assert result["sent_count"] == 3
        mock_bot.broadcast_report.assert_called_once()

    @pytest.mark.asyncio
    async def test_handles_broadcast_error(self):
        """Should handle broadcast errors."""
        action = BroadcastReportAction("test", {})

        mock_bot = MagicMock()
        mock_bot.broadcast_report = AsyncMock(side_effect=Exception("Network error"))
        action.set_bot(mock_bot)

        result = await action.execute({})

        assert result["success"] is False
        assert "Network error" in result["error"]


class TestManageChatAction:
    """Test manage chat action."""

    @pytest.mark.asyncio
    async def test_requires_action_and_chat_id(self):
        """Should require action and chat_id."""
        action = ManageChatAction("test", {})

        with pytest.raises(ValueError):
            await action.execute({})

        with pytest.raises(ValueError):
            await action.execute({"action": "add"})

    @pytest.mark.asyncio
    async def test_adds_chat_id(self):
        """Should add chat ID."""
        action = ManageChatAction("test", {})

        mock_bot = MagicMock()
        action.set_bot(mock_bot)

        result = await action.execute({
            "action": "add",
            "chat_id": 12345,
        })

        assert result["success"] is True
        assert result["action"] == "added"
        mock_bot.add_chat_id.assert_called_once_with(12345)

    @pytest.mark.asyncio
    async def test_removes_chat_id(self):
        """Should remove chat ID."""
        action = ManageChatAction("test", {})

        mock_bot = MagicMock()
        action.set_bot(mock_bot)

        result = await action.execute({
            "action": "remove",
            "chat_id": 12345,
        })

        assert result["success"] is True
        assert result["action"] == "removed"
        mock_bot.remove_chat_id.assert_called_once_with(12345)

    @pytest.mark.asyncio
    async def test_rejects_unknown_action(self):
        """Should reject unknown actions."""
        action = ManageChatAction("test", {})

        mock_bot = MagicMock()
        action.set_bot(mock_bot)

        with pytest.raises(ValueError):
            await action.execute({
                "action": "invalid",
                "chat_id": 12345,
            })

    def test_requires_confirmation(self):
        """Should require confirmation for chat management."""
        action = ManageChatAction("test", {})

        assert action.requires_confirmation is True


# =============================================================================
# Test Providers
# =============================================================================

class TestBotStatusProvider:
    """Test bot status provider."""

    @pytest.mark.asyncio
    async def test_returns_uninitialized_without_bot(self):
        """Should return uninitialized status without bot."""
        provider = BotStatusProvider("test", {})

        result = await provider.provide({})

        assert result["initialized"] is False

    @pytest.mark.asyncio
    async def test_returns_bot_status(self):
        """Should return full bot status."""
        provider = BotStatusProvider("test", {})

        mock_bot = MagicMock()
        mock_bot.token = "test_token"
        mock_bot._running = True
        mock_bot.config = {
            "chat_ids": [111, 222],
            "schedule": {"enabled": True, "times": ["09:00", "12:00"]},
            "tokens": ["SOL", "BTC"],
        }
        provider.set_bot(mock_bot)

        result = await provider.provide({})

        assert result["initialized"] is True
        assert result["has_token"] is True
        assert result["chat_count"] == 2
        assert result["scheduler_running"] is True
        assert result["schedule_enabled"] is True
        assert result["schedule_times"] == ["09:00", "12:00"]
        assert result["tokens"] == ["SOL", "BTC"]


# =============================================================================
# Test Plugin Integration
# =============================================================================

class TestTelegramPluginIntegration:
    """Integration tests for Telegram plugin."""

    @pytest.fixture
    def mock_context(self):
        """Create mock plugin context."""
        context = MagicMock()
        context.config = {
            "enabled": True,
        }

        # Mock jarvis with PAE registry
        mock_jarvis = MagicMock()
        mock_jarvis.pae = MagicMock()
        mock_jarvis.pae.register_provider = MagicMock()
        mock_jarvis.pae.register_action = MagicMock()

        # Mock event bus
        mock_event_bus = MagicMock()
        mock_event_bus.emit = AsyncMock()
        mock_event_bus.on = MagicMock(return_value=lambda f: f)

        context.services = {
            "jarvis": mock_jarvis,
            "event_bus": mock_event_bus,
        }

        return context

    @pytest.fixture
    def mock_manifest(self):
        """Create mock plugin manifest."""
        manifest = MagicMock()
        manifest.name = "telegram"
        manifest.version = "1.0.0"
        return manifest

    @pytest.mark.asyncio
    async def test_plugin_loads(self, mock_context, mock_manifest):
        """Should load without errors."""
        # Mock the import to avoid needing the actual module
        with patch.dict('sys.modules', {'core.integrations.telegram_sentiment_bot': MagicMock()}):
            plugin = TelegramPlugin(mock_context, mock_manifest)
            await plugin.on_load()

            # Should register actions and providers
            assert mock_context.services["jarvis"].pae.register_action.called
            assert mock_context.services["jarvis"].pae.register_provider.called

    @pytest.mark.asyncio
    async def test_plugin_loads_without_bot_module(self, mock_context, mock_manifest):
        """Should handle missing telegram_sentiment_bot module."""
        # Don't mock the module - let it fail to import
        plugin = TelegramPlugin(mock_context, mock_manifest)
        await plugin.on_load()

        # Should still register components
        assert mock_context.services["jarvis"].pae.register_action.called

    @pytest.mark.asyncio
    async def test_plugin_enable_disable(self, mock_context, mock_manifest):
        """Should enable and disable cleanly."""
        plugin = TelegramPlugin(mock_context, mock_manifest)

        await plugin.on_load()

        # Set mock bot after load (load tries to import real bot)
        mock_bot = MagicMock()
        mock_bot.config = {"schedule": {"enabled": False}}
        mock_bot._running = False
        mock_bot.token = "test"
        plugin._bot = mock_bot

        await plugin.on_enable()

        # Should emit enabled event
        event_bus = mock_context.services["event_bus"]
        event_bus.emit.assert_called()

        await plugin.on_disable()

        # Should stop scheduler
        mock_bot.stop_scheduler.assert_called()

    @pytest.mark.asyncio
    async def test_plugin_starts_scheduler_when_enabled(self, mock_context, mock_manifest):
        """Should start scheduler when schedule is enabled."""
        plugin = TelegramPlugin(mock_context, mock_manifest)

        await plugin.on_load()

        # Set mock bot after load
        mock_bot = MagicMock()
        mock_bot.config = {"schedule": {"enabled": True}}
        mock_bot.token = "test"
        plugin._bot = mock_bot

        await plugin.on_enable()

        mock_bot.start_scheduler.assert_called_once()

    @pytest.mark.asyncio
    async def test_plugin_api_methods(self, mock_context, mock_manifest):
        """Should expose API methods."""
        plugin = TelegramPlugin(mock_context, mock_manifest)

        mock_bot = MagicMock()
        mock_bot.send_message = AsyncMock(return_value=True)
        mock_bot.broadcast_report = AsyncMock(return_value=2)
        mock_bot.config = {"chat_ids": [111, 222]}
        mock_bot.token = "test"
        mock_bot._running = False
        plugin._bot = mock_bot

        # Test send_message
        result = await plugin.send_message(12345, "Hello")
        assert result is True

        # Test broadcast
        count = await plugin.broadcast("Hello all")
        assert count == 2

        # Test send_report
        count = await plugin.send_report()
        assert count == 2

        # Test get_status
        status = plugin.get_status()
        assert status["initialized"] is True
        assert status["has_token"] is True

    @pytest.mark.asyncio
    async def test_plugin_without_bot(self, mock_context, mock_manifest):
        """Should handle missing bot gracefully."""
        plugin = TelegramPlugin(mock_context, mock_manifest)
        plugin._bot = None

        result = await plugin.send_message(123, "Hello")
        assert result is False

        count = await plugin.broadcast("Hello")
        assert count == 0

        status = plugin.get_status()
        assert status["initialized"] is False

    @pytest.mark.asyncio
    async def test_plugin_unload(self, mock_context, mock_manifest):
        """Should clean up on unload."""
        plugin = TelegramPlugin(mock_context, mock_manifest)

        mock_bot = MagicMock()
        mock_bot._running = True
        plugin._bot = mock_bot

        await plugin.on_unload()

        mock_bot.stop_scheduler.assert_called_once()
        assert plugin._bot is None
