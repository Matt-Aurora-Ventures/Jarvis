"""
Unit tests for the HealthReporter class.

Tests cover:
- Status formatting
- Alert sending
- Recovery notifications
- Telegram integration
"""

import asyncio
import os
import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def mock_bot_status():
    """Create mock bot status."""
    from core.health.monitor import BotStatus
    from core.health.status import HealthStatus

    return BotStatus(
        name="test_bot",
        status=HealthStatus.UNHEALTHY,
        message="Connection failed",
        latency_ms=0,
    )


@pytest.fixture
def mock_healthy_status():
    """Create mock healthy bot status."""
    from core.health.monitor import BotStatus
    from core.health.status import HealthStatus

    return BotStatus(
        name="test_bot",
        status=HealthStatus.HEALTHY,
        message="OK",
        latency_ms=10.5,
    )




# =============================================================================
# HEALTH REPORTER IMPORT TESTS
# =============================================================================

class TestHealthReporterImport:
    """Tests for module imports."""

    def test_import_health_reporter(self):
        """Test that HealthReporter can be imported."""
        from core.health.reporter import HealthReporter
        assert HealthReporter is not None


# =============================================================================
# HEALTH REPORTER INIT TESTS
# =============================================================================

class TestHealthReporterInit:
    """Tests for HealthReporter initialization."""

    def test_init_default(self):
        """Test default initialization."""
        from core.health.reporter import HealthReporter

        reporter = HealthReporter()
        assert reporter is not None
        assert reporter._alert_cooldown == 300  # 5 minutes default

    def test_init_with_telegram_config(self):
        """Test initialization with Telegram config."""
        from core.health.reporter import HealthReporter

        with patch.dict(os.environ, {
            "TELEGRAM_BOT_TOKEN": "test_token",
            "TELEGRAM_ADMIN_IDS": "123456,789012",
        }):
            reporter = HealthReporter()
            assert reporter._telegram_token == "test_token"
            assert reporter._telegram_chat_ids == ["123456", "789012"]

    def test_init_with_custom_cooldown(self):
        """Test initialization with custom cooldown."""
        from core.health.reporter import HealthReporter

        reporter = HealthReporter(alert_cooldown=60)
        assert reporter._alert_cooldown == 60


# =============================================================================
# FORMAT STATUS TESTS
# =============================================================================

class TestFormatStatus:
    """Tests for status formatting."""

    def test_format_status_unhealthy(self, mock_bot_status):
        """Test formatting unhealthy status."""
        from core.health.reporter import HealthReporter

        reporter = HealthReporter()
        formatted = reporter.format_status(mock_bot_status)

        assert "test_bot" in formatted
        assert "UNHEALTHY" in formatted.upper() or "unhealthy" in formatted.lower()
        assert "Connection failed" in formatted

    def test_format_status_healthy(self, mock_healthy_status):
        """Test formatting healthy status."""
        from core.health.reporter import HealthReporter

        reporter = HealthReporter()
        formatted = reporter.format_status(mock_healthy_status)

        assert "test_bot" in formatted
        assert "HEALTHY" in formatted.upper() or "healthy" in formatted.lower()

    def test_format_status_with_latency(self, mock_healthy_status):
        """Test that formatted status includes latency."""
        from core.health.reporter import HealthReporter

        reporter = HealthReporter()
        formatted = reporter.format_status(mock_healthy_status)

        # Should include latency info
        assert "10" in formatted or "ms" in formatted.lower()

    def test_format_status_telegram_mode(self, mock_bot_status):
        """Test formatting for Telegram (markdown)."""
        from core.health.reporter import HealthReporter

        reporter = HealthReporter()
        formatted = reporter.format_status(mock_bot_status, format="telegram")

        # Telegram format should have markdown
        assert "*" in formatted or "_" in formatted or "`" in formatted

    def test_format_status_json_mode(self, mock_bot_status):
        """Test formatting as JSON."""
        from core.health.reporter import HealthReporter
        import json

        reporter = HealthReporter()
        formatted = reporter.format_status(mock_bot_status, format="json")

        # Should be valid JSON
        parsed = json.loads(formatted)
        assert parsed["name"] == "test_bot"


# =============================================================================
# SEND ALERT TESTS
# =============================================================================

class TestSendAlert:
    """Tests for alert sending."""

    @pytest.mark.asyncio
    async def test_send_alert_to_telegram(self, mock_bot_status):
        """Test sending alert to Telegram."""
        from core.health.reporter import HealthReporter

        with patch.dict(os.environ, {
            "TELEGRAM_BOT_TOKEN": "test_token",
            "TELEGRAM_ADMIN_IDS": "123456",
        }):
            with patch("core.health.reporter.aiohttp") as mock_aiohttp:
                mock_response = MagicMock()
                mock_response.status = 200

                mock_post_cm = MagicMock()
                mock_post_cm.__aenter__ = AsyncMock(return_value=mock_response)
                mock_post_cm.__aexit__ = AsyncMock(return_value=None)

                mock_session = MagicMock()
                mock_session.post.return_value = mock_post_cm

                mock_session_cm = MagicMock()
                mock_session_cm.__aenter__ = AsyncMock(return_value=mock_session)
                mock_session_cm.__aexit__ = AsyncMock(return_value=None)

                mock_aiohttp.ClientSession.return_value = mock_session_cm

                reporter = HealthReporter()
                result = await reporter.send_alert(mock_bot_status)

                assert result.sent is True

    @pytest.mark.asyncio
    async def test_send_alert_respects_cooldown(self, mock_bot_status):
        """Test that alerts respect cooldown period."""
        from core.health.reporter import HealthReporter

        with patch.dict(os.environ, {
            "TELEGRAM_BOT_TOKEN": "test_token",
            "TELEGRAM_ADMIN_IDS": "123456",
        }):
            with patch("core.health.reporter.aiohttp") as mock_aiohttp:
                mock_response = MagicMock()
                mock_response.status = 200

                mock_post_cm = MagicMock()
                mock_post_cm.__aenter__ = AsyncMock(return_value=mock_response)
                mock_post_cm.__aexit__ = AsyncMock(return_value=None)

                mock_session = MagicMock()
                mock_session.post.return_value = mock_post_cm

                mock_session_cm = MagicMock()
                mock_session_cm.__aenter__ = AsyncMock(return_value=mock_session)
                mock_session_cm.__aexit__ = AsyncMock(return_value=None)

                mock_aiohttp.ClientSession.return_value = mock_session_cm

                reporter = HealthReporter(alert_cooldown=300)

                # First alert should send
                result1 = await reporter.send_alert(mock_bot_status)
                assert result1.sent is True

                # Second alert should be suppressed (cooldown)
                result2 = await reporter.send_alert(mock_bot_status)
                assert result2.sent is False
                assert result2.reason == "cooldown"

    @pytest.mark.asyncio
    async def test_send_alert_no_telegram_config(self, mock_bot_status):
        """Test alert when Telegram not configured."""
        from core.health.reporter import HealthReporter

        with patch.dict(os.environ, {}, clear=True):
            reporter = HealthReporter()
            result = await reporter.send_alert(mock_bot_status)

            assert result.sent is False
            assert "not configured" in result.reason.lower()

    @pytest.mark.asyncio
    async def test_send_alert_telegram_error(self, mock_bot_status):
        """Test handling Telegram API error."""
        from core.health.reporter import HealthReporter

        with patch.dict(os.environ, {
            "TELEGRAM_BOT_TOKEN": "test_token",
            "TELEGRAM_ADMIN_IDS": "123456",
        }):
            with patch("core.health.reporter.aiohttp") as mock_aiohttp:
                mock_session = MagicMock()
                mock_session.post.side_effect = Exception("Connection failed")

                mock_session_cm = MagicMock()
                mock_session_cm.__aenter__ = AsyncMock(return_value=mock_session)
                mock_session_cm.__aexit__ = AsyncMock(return_value=None)

                mock_aiohttp.ClientSession.return_value = mock_session_cm

                reporter = HealthReporter()
                result = await reporter.send_alert(mock_bot_status)

                assert result.sent is False
                assert "error" in result.reason.lower()

    @pytest.mark.asyncio
    async def test_send_alert_multiple_chat_ids(self, mock_bot_status):
        """Test sending to multiple Telegram chat IDs."""
        from core.health.reporter import HealthReporter

        with patch.dict(os.environ, {
            "TELEGRAM_BOT_TOKEN": "test_token",
            "TELEGRAM_ADMIN_IDS": "123456,789012,345678",
        }):
            with patch("core.health.reporter.aiohttp") as mock_aiohttp:
                mock_response = MagicMock()
                mock_response.status = 200

                mock_post_cm = MagicMock()
                mock_post_cm.__aenter__ = AsyncMock(return_value=mock_response)
                mock_post_cm.__aexit__ = AsyncMock(return_value=None)

                mock_session = MagicMock()
                mock_session.post.return_value = mock_post_cm

                mock_session_cm = MagicMock()
                mock_session_cm.__aenter__ = AsyncMock(return_value=mock_session)
                mock_session_cm.__aexit__ = AsyncMock(return_value=None)

                mock_aiohttp.ClientSession.return_value = mock_session_cm

                reporter = HealthReporter()
                await reporter.send_alert(mock_bot_status)

                # Should have sent to 3 chat IDs
                assert mock_session.post.call_count == 3


# =============================================================================
# SEND RECOVERY TESTS
# =============================================================================

class TestSendRecovery:
    """Tests for recovery notifications."""

    @pytest.mark.asyncio
    async def test_send_recovery(self, mock_healthy_status):
        """Test sending recovery notification."""
        from core.health.reporter import HealthReporter

        with patch.dict(os.environ, {
            "TELEGRAM_BOT_TOKEN": "test_token",
            "TELEGRAM_ADMIN_IDS": "123456",
        }):
            with patch("core.health.reporter.aiohttp") as mock_aiohttp:
                mock_response = MagicMock()
                mock_response.status = 200

                mock_post_cm = MagicMock()
                mock_post_cm.__aenter__ = AsyncMock(return_value=mock_response)
                mock_post_cm.__aexit__ = AsyncMock(return_value=None)

                mock_session = MagicMock()
                mock_session.post.return_value = mock_post_cm

                mock_session_cm = MagicMock()
                mock_session_cm.__aenter__ = AsyncMock(return_value=mock_session)
                mock_session_cm.__aexit__ = AsyncMock(return_value=None)

                mock_aiohttp.ClientSession.return_value = mock_session_cm

                reporter = HealthReporter()
                result = await reporter.send_recovery(mock_healthy_status)

                assert result.sent is True

    @pytest.mark.asyncio
    async def test_send_recovery_message_content(self, mock_healthy_status):
        """Test recovery message contains correct content."""
        from core.health.reporter import HealthReporter

        with patch.dict(os.environ, {
            "TELEGRAM_BOT_TOKEN": "test_token",
            "TELEGRAM_ADMIN_IDS": "123456",
        }):
            with patch("core.health.reporter.aiohttp") as mock_aiohttp:
                mock_response = MagicMock()
                mock_response.status = 200

                mock_post_cm = MagicMock()
                mock_post_cm.__aenter__ = AsyncMock(return_value=mock_response)
                mock_post_cm.__aexit__ = AsyncMock(return_value=None)

                mock_session = MagicMock()
                mock_session.post.return_value = mock_post_cm

                mock_session_cm = MagicMock()
                mock_session_cm.__aenter__ = AsyncMock(return_value=mock_session)
                mock_session_cm.__aexit__ = AsyncMock(return_value=None)

                mock_aiohttp.ClientSession.return_value = mock_session_cm

                reporter = HealthReporter()
                await reporter.send_recovery(mock_healthy_status)

                # Check that the message mentions recovery
                call_args = mock_session.post.call_args
                message = str(call_args)
                assert "recover" in message.lower() or "healthy" in message.lower()

    @pytest.mark.asyncio
    async def test_send_recovery_no_prior_alert(self, mock_healthy_status):
        """Test that recovery is still sent."""
        from core.health.reporter import HealthReporter

        with patch.dict(os.environ, {
            "TELEGRAM_BOT_TOKEN": "test_token",
            "TELEGRAM_ADMIN_IDS": "123456",
        }):
            with patch("core.health.reporter.aiohttp") as mock_aiohttp:
                mock_response = MagicMock()
                mock_response.status = 200

                mock_post_cm = MagicMock()
                mock_post_cm.__aenter__ = AsyncMock(return_value=mock_response)
                mock_post_cm.__aexit__ = AsyncMock(return_value=None)

                mock_session = MagicMock()
                mock_session.post.return_value = mock_post_cm

                mock_session_cm = MagicMock()
                mock_session_cm.__aenter__ = AsyncMock(return_value=mock_session)
                mock_session_cm.__aexit__ = AsyncMock(return_value=None)

                mock_aiohttp.ClientSession.return_value = mock_session_cm

                reporter = HealthReporter()

                # No prior alert for this bot
                result = await reporter.send_recovery(mock_healthy_status)

                # Should still send recovery notification
                assert result is not None


# =============================================================================
# ALERT RESULT TESTS
# =============================================================================

class TestAlertResult:
    """Tests for AlertResult dataclass."""

    def test_alert_result_import(self):
        """Test that AlertResult can be imported."""
        from core.health.reporter import AlertResult
        assert AlertResult is not None

    def test_alert_result_creation(self):
        """Test creating an AlertResult."""
        from core.health.reporter import AlertResult

        result = AlertResult(
            sent=True,
            channels=["telegram"],
            message="Alert sent successfully",
        )

        assert result.sent is True
        assert "telegram" in result.channels

    def test_alert_result_with_reason(self):
        """Test AlertResult with reason for not sending."""
        from core.health.reporter import AlertResult

        result = AlertResult(
            sent=False,
            channels=[],
            reason="cooldown",
        )

        assert result.sent is False
        assert result.reason == "cooldown"


# =============================================================================
# FORMATTING TESTS
# =============================================================================

class TestFormatMultipleStatuses:
    """Tests for formatting multiple statuses."""

    def test_format_summary(self, mock_bot_status, mock_healthy_status):
        """Test formatting a summary of multiple statuses."""
        from core.health.reporter import HealthReporter

        reporter = HealthReporter()

        statuses = {
            "test_bot": mock_bot_status,
            "healthy_bot": mock_healthy_status,
        }

        formatted = reporter.format_summary(statuses)

        assert "test_bot" in formatted
        assert "healthy_bot" in formatted

    def test_format_summary_counts(self, mock_bot_status, mock_healthy_status):
        """Test that summary includes counts."""
        from core.health.reporter import HealthReporter

        reporter = HealthReporter()

        statuses = {
            "bot1": mock_bot_status,
            "bot2": mock_bot_status,
            "bot3": mock_healthy_status,
        }

        formatted = reporter.format_summary(statuses)

        # Should mention counts
        assert "1" in formatted or "2" in formatted or "3" in formatted

    def test_format_summary_overall_status(self, mock_bot_status, mock_healthy_status):
        """Test that summary includes overall status."""
        from core.health.reporter import HealthReporter

        reporter = HealthReporter()

        statuses = {
            "test_bot": mock_bot_status,
            "healthy_bot": mock_healthy_status,
        }

        formatted = reporter.format_summary(statuses)

        # Should indicate overall status
        assert ("overall" in formatted.lower() or
                "degraded" in formatted.lower() or
                "unhealthy" in formatted.lower())
