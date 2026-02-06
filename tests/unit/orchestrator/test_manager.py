"""
Tests for BotOrchestrator manager.

Tests:
- Bot registration
- Start/stop all bots
- Restart individual bots
- Status reporting
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime


class TestBotOrchestrator:
    """Tests for BotOrchestrator class."""

    @pytest.fixture
    def orchestrator(self):
        """Create a fresh orchestrator for each test."""
        from core.orchestrator.manager import BotOrchestrator
        return BotOrchestrator()

    @pytest.fixture
    def mock_bot(self):
        """Create a mock bot instance."""
        bot = MagicMock()
        bot.start = AsyncMock()
        bot.stop = AsyncMock()
        bot.is_running = MagicMock(return_value=False)
        bot.name = "test_bot"
        return bot

    def test_register_bot(self, orchestrator, mock_bot):
        """Test registering a bot with the orchestrator."""
        orchestrator.register_bot("test_bot", mock_bot)

        assert "test_bot" in orchestrator.bots
        assert orchestrator.bots["test_bot"] == mock_bot

    def test_register_bot_duplicate_raises(self, orchestrator, mock_bot):
        """Test that registering a duplicate bot name raises an error."""
        orchestrator.register_bot("test_bot", mock_bot)

        with pytest.raises(ValueError, match="already registered"):
            orchestrator.register_bot("test_bot", mock_bot)

    def test_register_multiple_bots(self, orchestrator):
        """Test registering multiple bots."""
        bot1 = MagicMock()
        bot2 = MagicMock()
        bot3 = MagicMock()

        orchestrator.register_bot("bot1", bot1)
        orchestrator.register_bot("bot2", bot2)
        orchestrator.register_bot("bot3", bot3)

        assert len(orchestrator.bots) == 3
        assert "bot1" in orchestrator.bots
        assert "bot2" in orchestrator.bots
        assert "bot3" in orchestrator.bots

    @pytest.mark.asyncio
    async def test_start_all(self, orchestrator, mock_bot):
        """Test starting all registered bots."""
        bot2 = MagicMock()
        bot2.start = AsyncMock()
        bot2.is_running = MagicMock(return_value=False)

        orchestrator.register_bot("test_bot", mock_bot)
        orchestrator.register_bot("bot2", bot2)

        await orchestrator.start_all()

        mock_bot.start.assert_called_once()
        bot2.start.assert_called_once()

    @pytest.mark.asyncio
    async def test_stop_all(self, orchestrator, mock_bot):
        """Test stopping all running bots."""
        bot2 = MagicMock()
        bot2.stop = AsyncMock()
        bot2.is_running = MagicMock(return_value=True)
        mock_bot.is_running = MagicMock(return_value=True)

        orchestrator.register_bot("test_bot", mock_bot)
        orchestrator.register_bot("bot2", bot2)

        await orchestrator.stop_all()

        mock_bot.stop.assert_called_once()
        bot2.stop.assert_called_once()

    @pytest.mark.asyncio
    async def test_restart_bot(self, orchestrator, mock_bot):
        """Test restarting a specific bot."""
        mock_bot.is_running = MagicMock(return_value=True)
        orchestrator.register_bot("test_bot", mock_bot)

        await orchestrator.restart_bot("test_bot")

        mock_bot.stop.assert_called_once()
        mock_bot.start.assert_called_once()

    @pytest.mark.asyncio
    async def test_restart_nonexistent_bot_raises(self, orchestrator):
        """Test that restarting a nonexistent bot raises an error."""
        with pytest.raises(KeyError, match="not found"):
            await orchestrator.restart_bot("nonexistent")

    def test_get_status(self, orchestrator, mock_bot):
        """Test getting status of all bots."""
        mock_bot.is_running = MagicMock(return_value=True)
        mock_bot.get_status = MagicMock(return_value={"healthy": True})

        orchestrator.register_bot("test_bot", mock_bot)

        status = orchestrator.get_status()

        assert "test_bot" in status
        assert status["test_bot"]["running"] is True

    def test_get_status_empty(self, orchestrator):
        """Test getting status with no registered bots."""
        status = orchestrator.get_status()
        assert status == {}

    @pytest.mark.asyncio
    async def test_start_all_handles_failures(self, orchestrator, mock_bot):
        """Test that start_all continues even if one bot fails."""
        mock_bot.start = AsyncMock(side_effect=Exception("Start failed"))

        bot2 = MagicMock()
        bot2.start = AsyncMock()
        bot2.is_running = MagicMock(return_value=False)

        orchestrator.register_bot("test_bot", mock_bot)
        orchestrator.register_bot("bot2", bot2)

        # Should not raise, should continue to bot2
        await orchestrator.start_all()

        bot2.start.assert_called_once()

    def test_unregister_bot(self, orchestrator, mock_bot):
        """Test unregistering a bot."""
        orchestrator.register_bot("test_bot", mock_bot)
        orchestrator.unregister_bot("test_bot")

        assert "test_bot" not in orchestrator.bots

    def test_unregister_nonexistent_bot_raises(self, orchestrator):
        """Test that unregistering a nonexistent bot raises an error."""
        with pytest.raises(KeyError, match="not found"):
            orchestrator.unregister_bot("nonexistent")


class TestBotOrchestratorSingleton:
    """Test singleton pattern for orchestrator."""

    def test_get_orchestrator_returns_singleton(self):
        """Test that get_orchestrator returns the same instance."""
        from core.orchestrator.manager import get_orchestrator

        orch1 = get_orchestrator()
        orch2 = get_orchestrator()

        assert orch1 is orch2


class TestBotStatus:
    """Tests for BotStatus enum."""

    def test_bot_status_values(self):
        """Test BotStatus enum has expected values."""
        from core.orchestrator.manager import BotStatus

        assert BotStatus.STOPPED.value == "stopped"
        assert BotStatus.STARTING.value == "starting"
        assert BotStatus.RUNNING.value == "running"
        assert BotStatus.STOPPING.value == "stopping"
        assert BotStatus.FAILED.value == "failed"
