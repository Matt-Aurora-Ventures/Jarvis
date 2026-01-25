"""
Tests for demo_orders module.

Tests TP/SL monitoring, trailing stops, auto-exit execution, alert formatting.
"""

import pytest
import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch, Mock
from types import SimpleNamespace
from datetime import datetime, timezone

from tg_bot.handlers.demo import demo_orders


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_context():
    """Mock Telegram context."""
    context = MagicMock()
    context.user_data = {}
    context.bot = AsyncMock()
    context.bot.send_message = AsyncMock()
    return context


@pytest.fixture
def mock_update():
    """Mock Telegram update."""
    update = MagicMock()
    update.effective_chat = MagicMock()
    update.effective_chat.id = 12345
    return update


@pytest.fixture
def sample_position():
    """Sample position dictionary."""
    return {
        "id": "pos_123",
        "symbol": "TEST",
        "address": "TokenMint123",
        "amount": 1000.0,
        "entry_price": 0.50,
        "current_price": 0.50,
        "tp_percent": 50.0,
        "sl_percent": 20.0,
    }


@pytest.fixture
def mock_jupiter():
    """Mock Jupiter client."""
    client = AsyncMock()
    client.get_token_price = AsyncMock(return_value=0.60)
    return client


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    """Clean environment variables between tests."""
    for key in [
        "DEMO_EXIT_CHECKS",
        "DEMO_TPSL_AUTO_EXECUTE",
        "DEMO_EXIT_CHECK_INTERVAL_SECONDS",
    ]:
        monkeypatch.delenv(key, raising=False)


# =============================================================================
# Configuration Tests
# =============================================================================


class TestConfiguration:
    """Test configuration helper functions."""

    def test_exit_checks_enabled_default(self, monkeypatch):
        """Test exit checks are enabled by default."""
        monkeypatch.delenv("DEMO_EXIT_CHECKS", raising=False)

        result = demo_orders._exit_checks_enabled()

        assert result is True

    def test_exit_checks_disabled_via_env(self, monkeypatch):
        """Test exit checks can be disabled via env."""
        monkeypatch.setenv("DEMO_EXIT_CHECKS", "0")

        result = demo_orders._exit_checks_enabled()

        assert result is False

    def test_auto_exit_enabled_requires_env_and_user_data(self, mock_context, monkeypatch):
        """Test auto-exit requires both env flag and user_data setting."""
        monkeypatch.setenv("DEMO_TPSL_AUTO_EXECUTE", "1")
        mock_context.user_data["ai_auto_trade"] = True

        result = demo_orders._auto_exit_enabled(mock_context)

        assert result is True

    def test_auto_exit_disabled_when_env_off(self, mock_context, monkeypatch):
        """Test auto-exit disabled when env var is off."""
        monkeypatch.setenv("DEMO_TPSL_AUTO_EXECUTE", "0")
        mock_context.user_data["ai_auto_trade"] = True

        result = demo_orders._auto_exit_enabled(mock_context)

        assert result is False

    def test_auto_exit_disabled_when_user_data_false(self, mock_context, monkeypatch):
        """Test auto-exit disabled when user hasn't enabled it."""
        monkeypatch.setenv("DEMO_TPSL_AUTO_EXECUTE", "1")
        mock_context.user_data["ai_auto_trade"] = False

        result = demo_orders._auto_exit_enabled(mock_context)

        assert result is False

    def test_get_exit_check_interval_default(self, monkeypatch):
        """Test default exit check interval is 30 seconds."""
        monkeypatch.delenv("DEMO_EXIT_CHECK_INTERVAL_SECONDS", raising=False)

        result = demo_orders._get_exit_check_interval_seconds()

        assert result == 30

    def test_get_exit_check_interval_from_env(self, monkeypatch):
        """Test exit check interval from env."""
        monkeypatch.setenv("DEMO_EXIT_CHECK_INTERVAL_SECONDS", "60")

        result = demo_orders._get_exit_check_interval_seconds()

        assert result == 60

    def test_get_exit_check_interval_minimum_5(self, monkeypatch):
        """Test exit check interval has minimum of 5 seconds."""
        monkeypatch.setenv("DEMO_EXIT_CHECK_INTERVAL_SECONDS", "1")

        result = demo_orders._get_exit_check_interval_seconds()

        assert result == 5

    def test_should_run_exit_checks_throttling(self, mock_context, sample_position, monkeypatch):
        """Test exit checks are throttled by interval."""
        monkeypatch.setenv("DEMO_EXIT_CHECKS", "1")
        monkeypatch.setenv("DEMO_EXIT_CHECK_INTERVAL_SECONDS", "10")
        mock_context.user_data["positions"] = [sample_position]

        # First call should run
        result1 = demo_orders._should_run_exit_checks(mock_context)
        assert result1 is True

        # Second call immediately should not run (throttled)
        result2 = demo_orders._should_run_exit_checks(mock_context)
        assert result2 is False

    def test_should_run_exit_checks_no_positions(self, mock_context, monkeypatch):
        """Test exit checks don't run without positions."""
        monkeypatch.setenv("DEMO_EXIT_CHECKS", "1")
        mock_context.user_data["positions"] = []

        result = demo_orders._should_run_exit_checks(mock_context)

        assert result is False


# =============================================================================
# Exit Trigger Tests
# =============================================================================


class TestExitTriggers:
    """Test exit trigger checking logic."""

    @pytest.mark.asyncio
    async def test_take_profit_trigger(self, mock_context, sample_position, mock_jupiter):
        """Test take-profit trigger detection."""
        # Set current price above TP threshold (50% profit)
        sample_position["current_price"] = 0.76  # > 0.75 (50% profit)

        with patch("tg_bot.handlers.demo.demo_trading._get_jupiter_client", return_value=mock_jupiter):
            alerts = await demo_orders._check_demo_exit_triggers(
                mock_context, [sample_position]
            )

        assert len(alerts) == 1
        assert alerts[0]["type"] == "take_profit"
        assert alerts[0]["position"]["id"] == "pos_123"
        assert sample_position["tp_triggered"] is True

    @pytest.mark.asyncio
    async def test_stop_loss_trigger(self, mock_context, sample_position, mock_jupiter):
        """Test stop-loss trigger detection."""
        # Set current price below SL threshold (20% loss)
        sample_position["current_price"] = 0.39  # < 0.40 (20% loss)

        with patch("tg_bot.handlers.demo.demo_trading._get_jupiter_client", return_value=mock_jupiter):
            alerts = await demo_orders._check_demo_exit_triggers(
                mock_context, [sample_position]
            )

        assert len(alerts) == 1
        assert alerts[0]["type"] == "stop_loss"
        assert alerts[0]["position"]["id"] == "pos_123"
        assert sample_position["sl_triggered"] is True

    @pytest.mark.asyncio
    async def test_trailing_stop_trigger(self, mock_context, sample_position, mock_jupiter):
        """Test trailing stop trigger detection."""
        mock_context.user_data["trailing_stops"] = [
            {
                "position_id": "pos_123",
                "active": True,
                "highest_price": 0.80,
                "current_stop_price": 0.72,  # 10% trail
                "trail_percent": 10,
            }
        ]
        sample_position["current_price"] = 0.70  # Below stop

        with patch("tg_bot.handlers.demo.demo_trading._get_jupiter_client", return_value=mock_jupiter):
            alerts = await demo_orders._check_demo_exit_triggers(
                mock_context, [sample_position]
            )

        assert len(alerts) == 1
        assert alerts[0]["type"] == "trailing_stop"
        assert mock_context.user_data["trailing_stops"][0]["triggered"] is True
        assert mock_context.user_data["trailing_stops"][0]["active"] is False

    @pytest.mark.asyncio
    async def test_trailing_stop_updates_highest(self, mock_context, sample_position, mock_jupiter):
        """Test trailing stop updates highest price."""
        mock_context.user_data["trailing_stops"] = [
            {
                "position_id": "pos_123",
                "active": True,
                "highest_price": 0.60,
                "current_stop_price": 0.54,
                "trail_percent": 10,
            }
        ]
        sample_position["current_price"] = 0.70  # Higher than previous highest

        with patch("tg_bot.handlers.demo.demo_trading._get_jupiter_client", return_value=mock_jupiter):
            await demo_orders._check_demo_exit_triggers(
                mock_context, [sample_position]
            )

        stop = mock_context.user_data["trailing_stops"][0]
        assert stop["highest_price"] == 0.70
        assert stop["current_stop_price"] == 0.63  # 0.70 * 0.9

    @pytest.mark.asyncio
    async def test_no_triggers_when_price_in_range(self, mock_context, sample_position, mock_jupiter):
        """Test no triggers when price is within TP/SL range."""
        sample_position["current_price"] = 0.55  # Between SL (0.40) and TP (0.75)

        with patch("tg_bot.handlers.demo.demo_trading._get_jupiter_client", return_value=mock_jupiter):
            alerts = await demo_orders._check_demo_exit_triggers(
                mock_context, [sample_position]
            )

        assert len(alerts) == 0

    @pytest.mark.asyncio
    async def test_fetches_current_price_from_jupiter(self, mock_context, sample_position, mock_jupiter):
        """Test fetches current price from Jupiter when missing."""
        sample_position["current_price"] = 0  # Missing price

        with patch("tg_bot.handlers.demo.demo_trading._get_jupiter_client", return_value=mock_jupiter):
            await demo_orders._check_demo_exit_triggers(
                mock_context, [sample_position]
            )

        # Should fetch from Jupiter
        mock_jupiter.get_token_price.assert_called_once_with("TokenMint123")
        assert sample_position["current_price"] == 0.60

    @pytest.mark.asyncio
    async def test_handles_user_data_dict_directly(self, sample_position, mock_jupiter):
        """Test accepts user_data dict directly (not just context)."""
        user_data = {"trailing_stops": []}

        with patch("tg_bot.handlers.demo.demo_trading._get_jupiter_client", return_value=mock_jupiter):
            alerts = await demo_orders._check_demo_exit_triggers(
                user_data, [sample_position]
            )

        # Should work without context object
        assert isinstance(alerts, list)


# =============================================================================
# Exit Execution Tests
# =============================================================================


class TestExitExecution:
    """Test auto-exit execution logic."""

    @pytest.mark.asyncio
    async def test_executes_exit_when_enabled(self, mock_context, sample_position, monkeypatch):
        """Test executes exit when auto-exit is enabled."""
        monkeypatch.setenv("DEMO_TPSL_AUTO_EXECUTE", "1")
        mock_context.user_data["ai_auto_trade"] = True
        mock_context.user_data["wallet_address"] = "wallet123"

        alert = {"type": "take_profit", "position": sample_position, "price": 0.75}

        mock_swap_result = {"success": True, "tx_hash": "tx_abc123", "source": "bags_fm"}
        with patch("tg_bot.handlers.demo.demo_trading._execute_swap_with_fallback", new_callable=AsyncMock, return_value=mock_swap_result):
            result = await demo_orders._maybe_execute_exit(mock_context, alert)

        assert result is True
        assert sample_position["exit_tx"] == "tx_abc123"
        assert sample_position["exit_source"] == "bags_fm"
        assert sample_position["exit_reason"] == "take_profit"
        assert "closed_at" in sample_position

    @pytest.mark.asyncio
    async def test_no_exit_when_auto_disabled(self, mock_context, sample_position, monkeypatch):
        """Test no exit when auto-exit is disabled."""
        monkeypatch.setenv("DEMO_TPSL_AUTO_EXECUTE", "0")
        mock_context.user_data["ai_auto_trade"] = True

        alert = {"type": "take_profit", "position": sample_position, "price": 0.75}

        result = await demo_orders._maybe_execute_exit(mock_context, alert)

        assert result is False

    @pytest.mark.asyncio
    async def test_no_exit_when_swap_fails(self, mock_context, sample_position, monkeypatch):
        """Test no exit when swap fails."""
        monkeypatch.setenv("DEMO_TPSL_AUTO_EXECUTE", "1")
        mock_context.user_data["ai_auto_trade"] = True

        alert = {"type": "stop_loss", "position": sample_position, "price": 0.39}

        mock_swap_result = {"success": False, "error": "Swap failed"}
        with patch("tg_bot.handlers.demo.demo_trading._execute_swap_with_fallback", new_callable=AsyncMock, return_value=mock_swap_result):
            result = await demo_orders._maybe_execute_exit(mock_context, alert)

        assert result is False


# =============================================================================
# Alert Formatting Tests
# =============================================================================


class TestAlertFormatting:
    """Test alert message formatting."""

    def test_format_take_profit_alert(self, sample_position):
        """Test formatting for take-profit alert."""
        alert = {"type": "take_profit", "position": sample_position, "price": 0.75}

        message = demo_orders._format_exit_alert_message(alert, auto_executed=False)

        assert "Target hit" in message
        assert "TEST" in message
        assert "$0.50" in message  # Entry
        assert "$0.75" in message  # Current
        assert "+50.0%" in message  # P&L
        assert "Auto-exit disabled" in message

    def test_format_stop_loss_alert(self, sample_position):
        """Test formatting for stop-loss alert."""
        alert = {"type": "stop_loss", "position": sample_position, "price": 0.40}

        message = demo_orders._format_exit_alert_message(alert, auto_executed=False)

        assert "Stop-loss hit" in message
        assert "TEST" in message
        assert "-20.0%" in message  # P&L

    def test_format_trailing_stop_alert(self, sample_position):
        """Test formatting for trailing stop alert."""
        alert = {"type": "trailing_stop", "position": sample_position, "price": 0.60}

        message = demo_orders._format_exit_alert_message(alert, auto_executed=False)

        assert "Trailing stop hit" in message
        assert "+20.0%" in message  # P&L

    def test_format_alert_with_auto_execution(self, sample_position):
        """Test formatting when auto-executed."""
        sample_position["exit_source"] = "jupiter"
        sample_position["exit_tx"] = "tx_abc123def456"
        alert = {"type": "take_profit", "position": sample_position, "price": 0.75}

        message = demo_orders._format_exit_alert_message(alert, auto_executed=True)

        assert "Auto-exit: jupiter" in message
        assert "TX: tx_abc12...23def456" in message


# =============================================================================
# Background Monitoring Tests
# =============================================================================


class TestBackgroundMonitoring:
    """Test background TP/SL monitor."""

    @pytest.mark.asyncio
    async def test_monitors_all_users(self, sample_position, mock_jupiter):
        """Test monitors all users in user_data."""
        mock_context = MagicMock()
        mock_context.application = MagicMock()
        mock_context.bot = AsyncMock()
        mock_context.application.user_data = {
            123: {"positions": [sample_position.copy()]},
            456: {"positions": [sample_position.copy()]},
        }

        with patch("tg_bot.handlers.demo.demo_trading._get_jupiter_client", return_value=mock_jupiter), \
             patch("tg_bot.handlers.demo.demo_orders._auto_exit_enabled", return_value=False):
            await demo_orders._background_tp_sl_monitor(mock_context)

        # Should check both users (but may not send messages if no triggers)

    @pytest.mark.asyncio
    async def test_sends_alerts_on_triggers(self, sample_position, mock_jupiter):
        """Test sends Telegram alerts when triggers hit."""
        sample_position["current_price"] = 0.76  # Above TP
        mock_context = MagicMock()
        mock_context.application = MagicMock()
        mock_context.bot = AsyncMock()
        mock_context.application.user_data = {
            123: {"positions": [sample_position]},
        }

        with patch("tg_bot.handlers.demo.demo_trading._get_jupiter_client", return_value=mock_jupiter), \
             patch("tg_bot.handlers.demo.demo_orders._auto_exit_enabled", return_value=False):
            await demo_orders._background_tp_sl_monitor(mock_context)

        # Should send message to user 123
        mock_context.bot.send_message.assert_called_once()
        call_kwargs = mock_context.bot.send_message.call_args.kwargs
        assert call_kwargs["chat_id"] == 123

    @pytest.mark.asyncio
    async def test_removes_closed_positions(self, sample_position, mock_jupiter):
        """Test removes positions after auto-exit."""
        sample_position["current_price"] = 0.76  # Above TP
        mock_context = MagicMock()
        mock_context.application = MagicMock()
        mock_context.bot = AsyncMock()
        user_data = {"positions": [sample_position], "ai_auto_trade": True}
        mock_context.application.user_data = {123: user_data}

        mock_swap = {"success": True, "tx_hash": "tx123", "source": "bags_fm"}

        with patch("tg_bot.handlers.demo.demo_trading._get_jupiter_client", return_value=mock_jupiter), \
             patch("tg_bot.handlers.demo.demo_orders._auto_exit_enabled", return_value=True), \
             patch("tg_bot.handlers.demo.demo_trading._execute_swap_with_fallback", new_callable=AsyncMock, return_value=mock_swap):
            await demo_orders._background_tp_sl_monitor(mock_context)

        # Position should be removed
        assert len(user_data["positions"]) == 0


# =============================================================================
# Per-Request Processing Tests
# =============================================================================


class TestPerRequestProcessing:
    """Test per-request exit check processing."""

    @pytest.mark.asyncio
    async def test_runs_exit_checks_on_callback(self, mock_update, mock_context, sample_position, mock_jupiter, monkeypatch):
        """Test runs exit checks during callback processing."""
        monkeypatch.setenv("DEMO_EXIT_CHECKS", "1")
        monkeypatch.setenv("DEMO_EXIT_CHECK_INTERVAL_SECONDS", "30")
        mock_context.user_data["positions"] = [sample_position]
        sample_position["current_price"] = 0.76  # Above TP

        with patch("tg_bot.handlers.demo.demo_trading._get_jupiter_client", return_value=mock_jupiter), \
             patch("tg_bot.handlers.demo.demo_orders._auto_exit_enabled", return_value=False):
            await demo_orders._process_demo_exit_checks(mock_update, mock_context)

        # Should send alert message
        mock_context.bot.send_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_throttles_exit_checks(self, mock_update, mock_context, sample_position, monkeypatch):
        """Test throttles exit checks based on interval."""
        monkeypatch.setenv("DEMO_EXIT_CHECKS", "1")
        monkeypatch.setenv("DEMO_EXIT_CHECK_INTERVAL_SECONDS", "10")
        mock_context.user_data["positions"] = [sample_position]

        # First call should run
        with patch("tg_bot.handlers.demo.demo_orders._check_demo_exit_triggers", new_callable=AsyncMock) as mock_check:
            await demo_orders._process_demo_exit_checks(mock_update, mock_context)
            assert mock_check.called

        # Second call immediately should not run (throttled)
        with patch("tg_bot.handlers.demo.demo_orders._check_demo_exit_triggers", new_callable=AsyncMock) as mock_check:
            await demo_orders._process_demo_exit_checks(mock_update, mock_context)
            assert not mock_check.called

    @pytest.mark.asyncio
    async def test_removes_closed_positions_on_exit(self, mock_update, mock_context, sample_position, mock_jupiter, monkeypatch):
        """Test removes positions after successful exit."""
        monkeypatch.setenv("DEMO_EXIT_CHECKS", "1")
        monkeypatch.setenv("DEMO_TPSL_AUTO_EXECUTE", "1")
        mock_context.user_data["positions"] = [sample_position]
        mock_context.user_data["ai_auto_trade"] = True
        sample_position["current_price"] = 0.76  # Above TP

        mock_swap = {"success": True, "tx_hash": "tx123", "source": "bags_fm"}

        with patch("tg_bot.handlers.demo.demo_trading._get_jupiter_client", return_value=mock_jupiter), \
             patch("tg_bot.handlers.demo.demo_trading._execute_swap_with_fallback", new_callable=AsyncMock, return_value=mock_swap):
            await demo_orders._process_demo_exit_checks(mock_update, mock_context)

        # Position should be removed
        assert len(mock_context.user_data["positions"]) == 0
