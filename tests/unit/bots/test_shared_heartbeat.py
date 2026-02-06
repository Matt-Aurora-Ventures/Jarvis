"""
Tests for bots/shared/heartbeat.py - Telegram Heartbeat System.

The heartbeat system sends periodic status messages to a Telegram chat,
keeping Daryl informed about bot health without being intrusive.

Features tested:
1. Periodic heartbeat messages (configurable, default 6 hours)
2. Status reporting (uptime, messages processed, API costs, memory usage)
3. Emergency alerts for critical issues
4. Manual trigger via send_heartbeat_now()
5. Thread-safe background operation
6. State persistence at /root/clawdbots/heartbeat_state.json
"""

import pytest
import asyncio
import json
import os
import sys
import threading
import time
from pathlib import Path
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, patch, MagicMock

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


class TestHeartbeatModuleExists:
    """Tests for heartbeat module existence and basic structure."""

    def test_heartbeat_module_exists(self):
        """The heartbeat module should exist at bots/shared/heartbeat.py."""
        heartbeat_path = PROJECT_ROOT / "bots" / "shared" / "heartbeat.py"
        assert heartbeat_path.exists(), "Heartbeat module should exist at bots/shared/heartbeat.py"

    def test_heartbeat_exports_required_functions(self):
        """The heartbeat module should export required functions."""
        from bots.shared.heartbeat import (
            start_heartbeat_thread,
            send_heartbeat_now,
            get_heartbeat_status,
            format_heartbeat_message,
        )
        # All imports should succeed
        assert callable(start_heartbeat_thread)
        assert callable(send_heartbeat_now)
        assert callable(get_heartbeat_status)
        assert callable(format_heartbeat_message)


class TestHeartbeatConfiguration:
    """Tests for heartbeat configuration."""

    def test_default_interval_is_six_hours(self):
        """Default heartbeat interval should be 6 hours (21600 seconds)."""
        from bots.shared.heartbeat import TelegramHeartbeat

        hb = TelegramHeartbeat(bot_token="test", chat_id=-123)
        assert hb.interval_seconds == 21600, "Default interval should be 6 hours"

    def test_interval_is_configurable(self):
        """Heartbeat interval should be configurable."""
        from bots.shared.heartbeat import TelegramHeartbeat

        # 1 hour interval
        hb = TelegramHeartbeat(bot_token="test", chat_id=-123, interval_hours=1)
        assert hb.interval_seconds == 3600

    def test_state_path_default(self):
        """State should be stored at /root/clawdbots/heartbeat_state.json by default."""
        from bots.shared.heartbeat import TelegramHeartbeat

        hb = TelegramHeartbeat(bot_token="test", chat_id=-123)
        # Normalize path separators for cross-platform comparison
        expected_parts = ["root", "clawdbots", "heartbeat_state.json"]
        actual_parts = hb.state_path.parts[-3:]
        assert list(actual_parts) == expected_parts, f"Expected path ending in {expected_parts}, got {actual_parts}"

    def test_state_path_is_configurable(self):
        """State path should be configurable."""
        from bots.shared.heartbeat import TelegramHeartbeat

        custom_path = "/tmp/test_heartbeat_state.json"
        hb = TelegramHeartbeat(bot_token="test", chat_id=-123, state_path=custom_path)
        # Check that the path ends with expected components
        assert hb.state_path.name == "test_heartbeat_state.json"


class TestHeartbeatMessage:
    """Tests for heartbeat message formatting."""

    def test_format_heartbeat_message_includes_uptime(self):
        """Heartbeat message should include uptime."""
        from bots.shared.heartbeat import format_heartbeat_message

        stats = {
            "uptime_seconds": 3600,
            "messages_processed": 10,
            "api_cost_usd": 0.05,
            "memory_mb": 128.5,
        }
        message = format_heartbeat_message("TestBot", stats)

        assert "uptime" in message.lower() or "1h" in message or "hour" in message.lower()

    def test_format_heartbeat_message_includes_messages_processed(self):
        """Heartbeat message should include messages processed count."""
        from bots.shared.heartbeat import format_heartbeat_message

        stats = {
            "uptime_seconds": 3600,
            "messages_processed": 42,
            "api_cost_usd": 0.05,
            "memory_mb": 128.5,
        }
        message = format_heartbeat_message("TestBot", stats)

        assert "42" in message or "messages" in message.lower()

    def test_format_heartbeat_message_includes_api_cost(self):
        """Heartbeat message should include API cost."""
        from bots.shared.heartbeat import format_heartbeat_message

        stats = {
            "uptime_seconds": 3600,
            "messages_processed": 10,
            "api_cost_usd": 1.25,
            "memory_mb": 128.5,
        }
        message = format_heartbeat_message("TestBot", stats)

        assert "1.25" in message or "cost" in message.lower() or "$" in message

    def test_format_heartbeat_message_includes_memory_usage(self):
        """Heartbeat message should include memory usage."""
        from bots.shared.heartbeat import format_heartbeat_message

        stats = {
            "uptime_seconds": 3600,
            "messages_processed": 10,
            "api_cost_usd": 0.05,
            "memory_mb": 256.0,
        }
        message = format_heartbeat_message("TestBot", stats)

        assert "256" in message or "memory" in message.lower() or "MB" in message

    def test_format_heartbeat_message_includes_bot_name(self):
        """Heartbeat message should include the bot name."""
        from bots.shared.heartbeat import format_heartbeat_message

        stats = {
            "uptime_seconds": 3600,
            "messages_processed": 10,
            "api_cost_usd": 0.05,
            "memory_mb": 128.5,
        }
        message = format_heartbeat_message("ClawdJarvis", stats)

        assert "ClawdJarvis" in message


class TestHeartbeatStatus:
    """Tests for heartbeat status retrieval."""

    def test_get_heartbeat_status_returns_dict(self):
        """get_heartbeat_status should return a dictionary."""
        from bots.shared.heartbeat import TelegramHeartbeat, get_heartbeat_status

        hb = TelegramHeartbeat(bot_token="test", chat_id=-123)
        status = get_heartbeat_status(hb)

        assert isinstance(status, dict)

    def test_get_heartbeat_status_includes_running_state(self):
        """Status should include whether heartbeat is running."""
        from bots.shared.heartbeat import TelegramHeartbeat, get_heartbeat_status

        hb = TelegramHeartbeat(bot_token="test", chat_id=-123)
        status = get_heartbeat_status(hb)

        assert "running" in status

    def test_get_heartbeat_status_includes_last_heartbeat_time(self):
        """Status should include last heartbeat time."""
        from bots.shared.heartbeat import TelegramHeartbeat, get_heartbeat_status

        hb = TelegramHeartbeat(bot_token="test", chat_id=-123)
        status = get_heartbeat_status(hb)

        assert "last_heartbeat" in status

    def test_get_heartbeat_status_includes_heartbeat_count(self):
        """Status should include total heartbeat count."""
        from bots.shared.heartbeat import TelegramHeartbeat, get_heartbeat_status

        hb = TelegramHeartbeat(bot_token="test", chat_id=-123)
        status = get_heartbeat_status(hb)

        assert "heartbeat_count" in status


class TestEmergencyAlerts:
    """Tests for emergency alert functionality."""

    @pytest.mark.asyncio
    async def test_send_emergency_alert(self):
        """Emergency alerts should be sendable."""
        from bots.shared.heartbeat import TelegramHeartbeat
        import aiohttp

        # Create a proper mock for the async context manager chain
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={"ok": True})

        mock_post_ctx = MagicMock()
        mock_post_ctx.__aenter__ = AsyncMock(return_value=mock_response)
        mock_post_ctx.__aexit__ = AsyncMock(return_value=None)

        mock_session = MagicMock()
        mock_session.post = MagicMock(return_value=mock_post_ctx)

        mock_session_ctx = MagicMock()
        mock_session_ctx.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_ctx.__aexit__ = AsyncMock(return_value=None)

        with patch.object(aiohttp, 'ClientSession', return_value=mock_session_ctx):
            hb = TelegramHeartbeat(bot_token="test:token", chat_id=-123)
            result = await hb.send_emergency_alert("Critical error occurred!")

            # Should return True for successful send
            assert result is True

    @pytest.mark.asyncio
    async def test_emergency_alert_includes_urgency_marker(self):
        """Emergency alerts should be clearly marked as urgent."""
        from bots.shared.heartbeat import TelegramHeartbeat
        import aiohttp

        captured_text = None

        def capture_post(url, **kwargs):
            nonlocal captured_text
            if 'json' in kwargs:
                captured_text = kwargs['json'].get('text', '')

            mock_response = MagicMock()
            mock_response.status = 200
            mock_response.json = AsyncMock(return_value={"ok": True})

            mock_ctx = MagicMock()
            mock_ctx.__aenter__ = AsyncMock(return_value=mock_response)
            mock_ctx.__aexit__ = AsyncMock(return_value=None)
            return mock_ctx

        mock_session = MagicMock()
        mock_session.post = capture_post

        mock_session_ctx = MagicMock()
        mock_session_ctx.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_ctx.__aexit__ = AsyncMock(return_value=None)

        with patch.object(aiohttp, 'ClientSession', return_value=mock_session_ctx):
            hb = TelegramHeartbeat(bot_token="test:token", chat_id=-123)
            await hb.send_emergency_alert("Test emergency")

            # Should contain emergency marker (e.g., ALERT, WARNING, EMERGENCY)
            assert captured_text is not None
            assert any(marker in captured_text.upper() for marker in ["ALERT", "WARNING", "EMERGENCY", "CRITICAL"])


class TestHeartbeatThread:
    """Tests for background heartbeat thread."""

    def test_start_heartbeat_thread_returns_thread(self):
        """start_heartbeat_thread should return a thread object."""
        from bots.shared.heartbeat import TelegramHeartbeat, start_heartbeat_thread

        with patch('bots.shared.heartbeat.aiohttp.ClientSession'):
            hb = TelegramHeartbeat(bot_token="test", chat_id=-123)
            thread = start_heartbeat_thread(hb)

            assert isinstance(thread, threading.Thread)

            # Clean up
            hb.stop()
            if thread.is_alive():
                thread.join(timeout=1)

    def test_heartbeat_thread_is_daemon(self):
        """Heartbeat thread should be a daemon thread."""
        from bots.shared.heartbeat import TelegramHeartbeat, start_heartbeat_thread

        with patch('bots.shared.heartbeat.aiohttp.ClientSession'):
            hb = TelegramHeartbeat(bot_token="test", chat_id=-123)
            thread = start_heartbeat_thread(hb)

            assert thread.daemon is True

            # Clean up
            hb.stop()
            if thread.is_alive():
                thread.join(timeout=1)


class TestStatePersistence:
    """Tests for heartbeat state persistence."""

    def test_save_state_creates_file(self, tmp_path):
        """save_state should create a state file."""
        from bots.shared.heartbeat import TelegramHeartbeat

        state_file = tmp_path / "heartbeat_state.json"
        hb = TelegramHeartbeat(bot_token="test", chat_id=-123, state_path=str(state_file))
        hb.save_state()

        assert state_file.exists()

    def test_save_state_is_valid_json(self, tmp_path):
        """Saved state should be valid JSON."""
        from bots.shared.heartbeat import TelegramHeartbeat

        state_file = tmp_path / "heartbeat_state.json"
        hb = TelegramHeartbeat(bot_token="test", chat_id=-123, state_path=str(state_file))
        hb.save_state()

        # Should be parseable JSON
        data = json.loads(state_file.read_text())
        assert isinstance(data, dict)

    def test_load_state_restores_heartbeat_count(self, tmp_path):
        """load_state should restore heartbeat count."""
        from bots.shared.heartbeat import TelegramHeartbeat

        state_file = tmp_path / "heartbeat_state.json"

        # Create initial heartbeat and save state
        hb1 = TelegramHeartbeat(bot_token="test", chat_id=-123, state_path=str(state_file))
        hb1.heartbeat_count = 42
        hb1.save_state()

        # Create new heartbeat and load state
        hb2 = TelegramHeartbeat(bot_token="test", chat_id=-123, state_path=str(state_file))
        hb2.load_state()

        assert hb2.heartbeat_count == 42


class TestSendHeartbeatNow:
    """Tests for manual heartbeat trigger."""

    @pytest.mark.asyncio
    async def test_send_heartbeat_now_sends_message(self):
        """send_heartbeat_now should send a message immediately."""
        from bots.shared.heartbeat import TelegramHeartbeat
        import aiohttp

        send_called = False

        def capture_post(url, **kwargs):
            nonlocal send_called
            send_called = True

            mock_response = MagicMock()
            mock_response.status = 200
            mock_response.json = AsyncMock(return_value={"ok": True})

            mock_ctx = MagicMock()
            mock_ctx.__aenter__ = AsyncMock(return_value=mock_response)
            mock_ctx.__aexit__ = AsyncMock(return_value=None)
            return mock_ctx

        mock_session = MagicMock()
        mock_session.post = capture_post

        mock_session_ctx = MagicMock()
        mock_session_ctx.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_ctx.__aexit__ = AsyncMock(return_value=None)

        with patch.object(aiohttp, 'ClientSession', return_value=mock_session_ctx):
            hb = TelegramHeartbeat(bot_token="test:token", chat_id=-123)
            await hb.send_heartbeat_now()

            assert send_called is True

    @pytest.mark.asyncio
    async def test_send_heartbeat_now_increments_count(self):
        """send_heartbeat_now should increment heartbeat count."""
        from bots.shared.heartbeat import TelegramHeartbeat
        import aiohttp

        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={"ok": True})

        mock_post_ctx = MagicMock()
        mock_post_ctx.__aenter__ = AsyncMock(return_value=mock_response)
        mock_post_ctx.__aexit__ = AsyncMock(return_value=None)

        mock_session = MagicMock()
        mock_session.post = MagicMock(return_value=mock_post_ctx)

        mock_session_ctx = MagicMock()
        mock_session_ctx.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_ctx.__aexit__ = AsyncMock(return_value=None)

        with patch.object(aiohttp, 'ClientSession', return_value=mock_session_ctx):
            hb = TelegramHeartbeat(bot_token="test:token", chat_id=-123)
            initial_count = hb.heartbeat_count

            await hb.send_heartbeat_now()

            assert hb.heartbeat_count == initial_count + 1


class TestMetricsTracking:
    """Tests for metrics tracking functionality."""

    def test_record_message_increments_count(self):
        """record_message should increment messages_processed."""
        from bots.shared.heartbeat import TelegramHeartbeat

        hb = TelegramHeartbeat(bot_token="test", chat_id=-123)
        initial = hb.stats["messages_processed"]

        hb.record_message()

        assert hb.stats["messages_processed"] == initial + 1

    def test_record_api_cost_accumulates(self):
        """record_api_cost should accumulate costs."""
        from bots.shared.heartbeat import TelegramHeartbeat

        hb = TelegramHeartbeat(bot_token="test", chat_id=-123)
        hb.stats["api_cost_usd"] = 0.0

        hb.record_api_cost(0.50)
        hb.record_api_cost(0.25)

        assert abs(hb.stats["api_cost_usd"] - 0.75) < 0.001


class TestEnvironmentIntegration:
    """Tests for environment variable integration."""

    def test_uses_telegram_bot_token_from_env(self):
        """Should use TELEGRAM_BOT_TOKEN from environment if not provided."""
        from bots.shared.heartbeat import TelegramHeartbeat

        with patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": "env_token_123"}, clear=False):
            hb = TelegramHeartbeat(chat_id=-123)
            assert hb.bot_token == "env_token_123"

    def test_uses_heartbeat_chat_id_from_env(self):
        """Should use HEARTBEAT_CHAT_ID from environment if not provided."""
        from bots.shared.heartbeat import TelegramHeartbeat

        with patch.dict(os.environ, {
            "TELEGRAM_BOT_TOKEN": "test_token",
            "HEARTBEAT_CHAT_ID": "-1001234567890"
        }, clear=False):
            hb = TelegramHeartbeat()
            assert hb.chat_id == -1001234567890
