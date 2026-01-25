"""
Tests for Status Dashboard - Comprehensive system status like Clawdbot.

Tests the status dashboard module which provides:
- System version, uptime, git commit
- Model and provider information
- Token usage (session in/out)
- Context usage and limits
- Quota tracking (hourly/daily remaining)
- Session information
- Settings (reasoning level, verbose mode)
- Queue/subagent status
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timezone, timedelta


class TestStatusDashboard:
    """Test the StatusDashboard class."""

    def test_dashboard_creation(self):
        """Test that StatusDashboard can be instantiated."""
        from core.status.dashboard import StatusDashboard

        dashboard = StatusDashboard()
        assert dashboard is not None

    def test_get_version_info(self):
        """Test version info returns expected fields."""
        from core.status.dashboard import StatusDashboard

        dashboard = StatusDashboard()
        info = dashboard.get_version_info()

        assert "version" in info
        assert "git_commit" in info
        # Version should be a string like "2026.1.25-0"
        assert isinstance(info["version"], str)

    def test_get_uptime(self):
        """Test uptime calculation."""
        from core.status.dashboard import StatusDashboard

        dashboard = StatusDashboard()
        uptime = dashboard.get_uptime()

        assert "uptime_str" in uptime
        assert "started_at" in uptime
        assert "uptime_seconds" in uptime
        assert uptime["uptime_seconds"] >= 0

    def test_get_model_info(self):
        """Test model info returns expected fields."""
        from core.status.dashboard import StatusDashboard

        dashboard = StatusDashboard()
        model_info = dashboard.get_model_info()

        assert "model" in model_info
        assert "provider" in model_info
        assert "auth_type" in model_info

    def test_get_token_usage(self):
        """Test token usage tracking."""
        from core.status.dashboard import StatusDashboard

        dashboard = StatusDashboard()
        tokens = dashboard.get_token_usage()

        assert "tokens_in" in tokens
        assert "tokens_out" in tokens
        assert isinstance(tokens["tokens_in"], int)
        assert isinstance(tokens["tokens_out"], int)

    def test_get_context_info(self):
        """Test context usage info."""
        from core.status.dashboard import StatusDashboard

        dashboard = StatusDashboard()
        context = dashboard.get_context_info()

        assert "used" in context
        assert "limit" in context
        assert "percent" in context
        assert "compactions" in context
        # Percent should be between 0 and 100
        assert 0 <= context["percent"] <= 100

    def test_get_quota_info(self):
        """Test quota/usage tracking."""
        from core.status.dashboard import StatusDashboard

        dashboard = StatusDashboard()
        quota = dashboard.get_quota_info()

        assert "hourly_remaining" in quota
        assert "daily_remaining" in quota
        assert "hourly_percent" in quota
        assert "daily_percent" in quota

    def test_get_session_info(self):
        """Test session information."""
        from core.status.dashboard import StatusDashboard

        dashboard = StatusDashboard()
        session = dashboard.get_session_info()

        assert "session_id" in session
        assert "last_activity" in session
        assert "last_activity_str" in session

    def test_get_settings(self):
        """Test settings retrieval."""
        from core.status.dashboard import StatusDashboard

        dashboard = StatusDashboard()
        settings = dashboard.get_settings()

        assert "runtime" in settings
        assert "think_level" in settings
        assert "verbose" in settings

    def test_get_queue_status(self):
        """Test queue/subagent status."""
        from core.status.dashboard import StatusDashboard

        dashboard = StatusDashboard()
        queue = dashboard.get_queue_status()

        assert "state" in queue
        assert "depth" in queue
        assert isinstance(queue["depth"], int)

    def test_get_full_status(self):
        """Test full status aggregation."""
        from core.status.dashboard import StatusDashboard

        dashboard = StatusDashboard()
        status = dashboard.get_full_status()

        # Should contain all sections
        assert "version" in status
        assert "uptime" in status
        assert "model" in status
        assert "tokens" in status
        assert "context" in status
        assert "quota" in status
        assert "session" in status
        assert "settings" in status
        assert "queue" in status

    def test_format_status_telegram(self):
        """Test Telegram-formatted status output."""
        from core.status.dashboard import StatusDashboard

        dashboard = StatusDashboard()
        formatted = dashboard.format_telegram()

        # Should be a string with emojis
        assert isinstance(formatted, str)
        assert len(formatted) > 0
        # Should contain key indicators
        assert "JARVIS" in formatted or "Jarvis" in formatted


class TestStatusDashboardSingleton:
    """Test singleton pattern for StatusDashboard."""

    def test_get_status_dashboard_singleton(self):
        """Test singleton accessor returns same instance."""
        from core.status.dashboard import get_status_dashboard

        d1 = get_status_dashboard()
        d2 = get_status_dashboard()

        assert d1 is d2


class TestStatusDashboardIntegration:
    """Integration tests for status dashboard with real components."""

    @pytest.mark.asyncio
    async def test_status_with_mocked_health(self):
        """Test status integrates with health monitor."""
        from core.status.dashboard import StatusDashboard

        with patch('core.status.dashboard.get_health_monitor') as mock_hm:
            mock_monitor = Mock()
            mock_monitor.get_overall_status.return_value = Mock(value="healthy")
            mock_hm.return_value = mock_monitor

            dashboard = StatusDashboard()
            status = dashboard.get_full_status()

            assert status is not None

    @pytest.mark.asyncio
    async def test_status_with_mocked_cost_tracker(self):
        """Test status integrates with cost tracker."""
        from core.status.dashboard import StatusDashboard

        with patch('core.status.dashboard.get_tracker') as mock_tracker:
            mock_t = Mock()
            mock_t.get_today_stats.return_value = Mock(
                total_cost_usd=1.50,
                total_calls=100,
                sentiment_checks=5
            )
            mock_tracker.return_value = mock_t

            dashboard = StatusDashboard()
            quota = dashboard.get_quota_info()

            assert quota is not None


class TestStatusCommandHandler:
    """Test the /status command handler for Telegram."""

    @pytest.mark.asyncio
    async def test_status_handler_exists(self):
        """Test status handler can be imported."""
        from tg_bot.handlers.status import status_dashboard_handler

        assert status_dashboard_handler is not None
        assert callable(status_dashboard_handler)

    @pytest.mark.asyncio
    async def test_status_handler_sends_message(self):
        """Test status handler sends formatted message."""
        from tg_bot.handlers.status import status_dashboard_handler

        # Mock update and context
        mock_update = MagicMock()
        mock_update.message.reply_text = MagicMock()
        mock_context = MagicMock()

        # Make reply_text a coroutine
        async def mock_reply(*args, **kwargs):
            pass
        mock_update.message.reply_text = mock_reply

        # Call handler
        await status_dashboard_handler(mock_update, mock_context)

        # Handler should complete without error

    @pytest.mark.asyncio
    async def test_status_handler_uses_html_parse_mode(self):
        """Test status handler uses HTML parse mode for formatting."""
        from tg_bot.handlers.status import status_dashboard_handler
        from telegram.constants import ParseMode

        mock_update = MagicMock()
        mock_context = MagicMock()

        captured_kwargs = {}
        async def capture_reply(*args, **kwargs):
            captured_kwargs.update(kwargs)
        mock_update.message.reply_text = capture_reply

        await status_dashboard_handler(mock_update, mock_context)

        # Should use HTML for rich formatting
        assert captured_kwargs.get("parse_mode") == ParseMode.HTML


class TestTokenTracking:
    """Test token tracking functionality."""

    def test_track_tokens_in(self):
        """Test tracking input tokens."""
        from core.status.dashboard import StatusDashboard

        dashboard = StatusDashboard()
        initial = dashboard.get_token_usage()["tokens_in"]

        dashboard.track_tokens(tokens_in=100)

        after = dashboard.get_token_usage()["tokens_in"]
        assert after == initial + 100

    def test_track_tokens_out(self):
        """Test tracking output tokens."""
        from core.status.dashboard import StatusDashboard

        dashboard = StatusDashboard()
        initial = dashboard.get_token_usage()["tokens_out"]

        dashboard.track_tokens(tokens_out=50)

        after = dashboard.get_token_usage()["tokens_out"]
        assert after == initial + 50

    def test_reset_session_tokens(self):
        """Test resetting session token counts."""
        from core.status.dashboard import StatusDashboard

        dashboard = StatusDashboard()
        dashboard.track_tokens(tokens_in=100, tokens_out=50)

        dashboard.reset_session()

        tokens = dashboard.get_token_usage()
        assert tokens["tokens_in"] == 0
        assert tokens["tokens_out"] == 0


class TestContextTracking:
    """Test context usage tracking."""

    def test_update_context_usage(self):
        """Test updating context usage."""
        from core.status.dashboard import StatusDashboard

        dashboard = StatusDashboard()
        dashboard.update_context(used=20000, limit=400000)

        context = dashboard.get_context_info()
        assert context["used"] == 20000
        assert context["limit"] == 400000
        assert context["percent"] == 5  # 20000/400000 = 5%

    def test_increment_compactions(self):
        """Test incrementing compaction count."""
        from core.status.dashboard import StatusDashboard

        dashboard = StatusDashboard()
        initial = dashboard.get_context_info()["compactions"]

        dashboard.increment_compactions()

        after = dashboard.get_context_info()["compactions"]
        assert after == initial + 1
