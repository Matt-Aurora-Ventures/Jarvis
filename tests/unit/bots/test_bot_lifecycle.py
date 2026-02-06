"""Tests for BotLifecycle - unified heartbeat + self-healing manager."""

import threading
import time
from unittest.mock import MagicMock, patch, AsyncMock

import pytest


class TestBotLifecycleInit:
    """Test BotLifecycle initialization."""

    def test_import(self):
        """BotLifecycle can be imported."""
        from bots.shared.bot_lifecycle import BotLifecycle
        assert BotLifecycle is not None

    def test_init_basic(self):
        """BotLifecycle initializes with bot_name and bot_token."""
        from bots.shared.bot_lifecycle import BotLifecycle
        lc = BotLifecycle(bot_name="TestBot", bot_token="fake-token")
        assert lc.bot_name == "TestBot"
        assert lc.bot_token == "fake-token"

    def test_init_creates_heartbeat(self):
        """BotLifecycle creates a TelegramHeartbeat instance."""
        from bots.shared.bot_lifecycle import BotLifecycle
        lc = BotLifecycle(bot_name="TestBot", bot_token="fake-token")
        assert lc.heartbeat is not None
        assert lc.heartbeat.bot_name == "TestBot"

    def test_init_creates_watchdog(self):
        """BotLifecycle creates a ProcessWatchdog instance."""
        from bots.shared.bot_lifecycle import BotLifecycle
        lc = BotLifecycle(bot_name="TestBot", bot_token="fake-token")
        assert lc.watchdog is not None
        assert lc.watchdog.bot_name == "testbot"  # lowercase per SelfHealingConfig

    def test_init_custom_heartbeat_interval(self):
        """BotLifecycle accepts custom heartbeat interval in hours."""
        from bots.shared.bot_lifecycle import BotLifecycle
        lc = BotLifecycle(bot_name="TestBot", bot_token="fake-token", heartbeat_interval_hours=0.5)
        assert lc.heartbeat.interval_seconds == 1800  # 0.5 hours = 1800s

    def test_init_custom_memory_threshold(self):
        """BotLifecycle accepts custom memory threshold."""
        from bots.shared.bot_lifecycle import BotLifecycle
        lc = BotLifecycle(bot_name="TestBot", bot_token="fake-token", memory_threshold_mb=128)
        assert lc.watchdog.config.memory_threshold_mb == 128

    def test_default_memory_threshold_256(self):
        """Default memory threshold is 256MB."""
        from bots.shared.bot_lifecycle import BotLifecycle
        lc = BotLifecycle(bot_name="TestBot", bot_token="fake-token")
        assert lc.watchdog.config.memory_threshold_mb == 256


class TestBotLifecycleProxies:
    """Test proxy methods."""

    def test_record_message(self):
        """record_message proxies to heartbeat."""
        from bots.shared.bot_lifecycle import BotLifecycle
        lc = BotLifecycle(bot_name="TestBot", bot_token="fake-token")
        lc.heartbeat.record_message = MagicMock()
        lc.record_message()
        lc.heartbeat.record_message.assert_called_once()

    def test_record_api_cost(self):
        """record_api_cost proxies to heartbeat."""
        from bots.shared.bot_lifecycle import BotLifecycle
        lc = BotLifecycle(bot_name="TestBot", bot_token="fake-token")
        lc.heartbeat.record_api_cost = MagicMock()
        lc.record_api_cost(0.05)
        lc.heartbeat.record_api_cost.assert_called_once_with(0.05)


class TestBotLifecycleStartStop:
    """Test start and shutdown."""

    def test_start_sets_running(self):
        """start() sets running flag."""
        from bots.shared.bot_lifecycle import BotLifecycle
        lc = BotLifecycle(bot_name="TestBot", bot_token="fake-token")
        # Mock the underlying start methods to avoid actual threads
        lc.heartbeat._run_loop = MagicMock()
        lc.watchdog.start = MagicMock()
        with patch("bots.shared.bot_lifecycle.start_heartbeat_thread") as mock_hb_start:
            lc.start()
        assert lc.running is True

    def test_shutdown_stops_both(self):
        """shutdown() stops heartbeat and watchdog."""
        from bots.shared.bot_lifecycle import BotLifecycle
        lc = BotLifecycle(bot_name="TestBot", bot_token="fake-token")
        lc.running = True
        lc.heartbeat.stop = MagicMock()
        lc.watchdog.stop = MagicMock()
        lc.shutdown()
        lc.heartbeat.stop.assert_called_once()
        lc.watchdog.stop.assert_called_once()
        assert lc.running is False

    def test_shutdown_idempotent(self):
        """shutdown() is safe to call when not running."""
        from bots.shared.bot_lifecycle import BotLifecycle
        lc = BotLifecycle(bot_name="TestBot", bot_token="fake-token")
        lc.shutdown()  # Should not raise


class TestBotLifecycleAlertWiring:
    """Test that watchdog alerts wire to heartbeat emergency alerts."""

    def test_alert_callback_registered(self):
        """Watchdog gets an alert callback on init."""
        from bots.shared.bot_lifecycle import BotLifecycle
        lc = BotLifecycle(bot_name="TestBot", bot_token="fake-token")
        assert len(lc.watchdog._alert_callbacks) >= 1
