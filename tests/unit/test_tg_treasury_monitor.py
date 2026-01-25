"""
Unit tests for tg_bot/services/treasury_monitor.py

Covers:
- Position loading and filtering
- Position price updates
- Treasury signals loading
- Price fetching from bags.fm API
- PnL alert system (gain/loss thresholds)
- TreasuryMonitor service lifecycle
- Periodic update scheduling
- Alert cooldown/deduplication
- Live treasury summary calculations
- Singleton pattern management
- Error handling and recovery
"""

import asyncio
import json
import pytest
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch, mock_open
from typing import Dict, Any, List

# Import the module under test
from tg_bot.services.treasury_monitor import (
    load_treasury_positions,
    update_position_price,
    load_treasury_signals,
    get_current_price,
    send_pnl_alert,
    TreasuryMonitor,
    get_treasury_monitor,
    start_treasury_monitor,
    get_live_treasury_summary,
    POSITIONS_FILE,
    TREASURY_SIGNALS_FILE,
    _monitor_instance,
)


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def sample_positions():
    """Create sample position data."""
    return {
        "positions": [
            {
                "id": "pos_001",
                "symbol": "SOL",
                "address": "So11111111111111111111111111111111111111112",
                "amount": 1000,
                "amount_sol": 0.5,
                "entry_price": 0.001,
                "current_price": 0.0012,
                "status": "open",
                "opened_at": "2026-01-20T10:00:00Z",
            },
            {
                "id": "pos_002",
                "symbol": "BONK",
                "address": "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263",
                "amount": 500000,
                "amount_sol": 0.3,
                "entry_price": 0.0000001,
                "current_price": 0.00000015,
                "status": "open",
                "opened_at": "2026-01-21T10:00:00Z",
            },
            {
                "id": "pos_003",
                "symbol": "CLOSED",
                "address": "closed_token_address",
                "amount": 100,
                "amount_sol": 0.1,
                "entry_price": 1.0,
                "current_price": 0.5,
                "status": "closed",
                "closed_at": "2026-01-22T10:00:00Z",
            },
        ]
    }


@pytest.fixture
def sample_signals():
    """Create sample trading signals data."""
    return {
        "signals": [
            {
                "id": "sig_001",
                "type": "buy",
                "symbol": "SOL",
                "timestamp": "2026-01-25T10:00:00Z",
                "score": 0.85,
                "reason": "High sentiment score",
            },
            {
                "id": "sig_002",
                "type": "sell",
                "symbol": "BONK",
                "timestamp": "2026-01-25T09:00:00Z",
                "score": -0.3,
                "reason": "Bearish momentum",
            },
            {
                "id": "sig_003",
                "type": "hold",
                "symbol": "WIF",
                "timestamp": "2026-01-24T12:00:00Z",
                "score": 0.0,
                "reason": "Neutral sentiment",
            },
        ]
    }


@pytest.fixture
def mock_positions_file(tmp_path, sample_positions):
    """Create a temporary positions file."""
    pos_file = tmp_path / ".lifeos" / "trading" / "demo_positions.json"
    pos_file.parent.mkdir(parents=True, exist_ok=True)
    pos_file.write_text(json.dumps(sample_positions))
    return pos_file


@pytest.fixture
def mock_signals_file(tmp_path, sample_signals):
    """Create a temporary signals file."""
    sig_file = tmp_path / "bots" / "treasury" / ".signals.json"
    sig_file.parent.mkdir(parents=True, exist_ok=True)
    sig_file.write_text(json.dumps(sample_signals))
    return sig_file


@pytest.fixture
def treasury_monitor():
    """Create a TreasuryMonitor instance."""
    return TreasuryMonitor(update_interval=1)


@pytest.fixture
def reset_singleton():
    """Reset the monitor singleton before/after tests."""
    import tg_bot.services.treasury_monitor as tm
    original = tm._monitor_instance
    tm._monitor_instance = None
    yield
    tm._monitor_instance = original


# ============================================================================
# Test: Position Loading
# ============================================================================

class TestLoadTreasuryPositions:
    """Tests for load_treasury_positions function."""

    def test_load_positions_success(self, sample_positions):
        """Should load and filter only open positions."""
        with patch("tg_bot.services.treasury_monitor.POSITIONS_FILE") as mock_file:
            mock_file.exists.return_value = True
            with patch("builtins.open", mock_open(read_data=json.dumps(sample_positions))):
                positions = load_treasury_positions()

        # Should only return open positions (2 out of 3)
        assert len(positions) == 2
        assert all(p["status"] == "open" for p in positions)
        assert positions[0]["symbol"] == "SOL"
        assert positions[1]["symbol"] == "BONK"

    def test_load_positions_file_not_exists(self):
        """Should return empty list when file doesn't exist."""
        with patch("tg_bot.services.treasury_monitor.POSITIONS_FILE") as mock_file:
            mock_file.exists.return_value = False
            positions = load_treasury_positions()

        assert positions == []

    def test_load_positions_empty_file(self):
        """Should return empty list for empty positions array."""
        data = {"positions": []}
        with patch("tg_bot.services.treasury_monitor.POSITIONS_FILE") as mock_file:
            mock_file.exists.return_value = True
            with patch("builtins.open", mock_open(read_data=json.dumps(data))):
                positions = load_treasury_positions()

        assert positions == []

    def test_load_positions_invalid_json(self):
        """Should handle invalid JSON gracefully."""
        with patch("tg_bot.services.treasury_monitor.POSITIONS_FILE") as mock_file:
            mock_file.exists.return_value = True
            with patch("builtins.open", mock_open(read_data="not valid json")):
                positions = load_treasury_positions()

        assert positions == []

    def test_load_positions_missing_status_field(self):
        """Should handle positions without status field."""
        data = {
            "positions": [
                {"id": "pos_001", "symbol": "SOL"},  # No status
                {"id": "pos_002", "symbol": "BONK", "status": "open"},
            ]
        }
        with patch("tg_bot.services.treasury_monitor.POSITIONS_FILE") as mock_file:
            mock_file.exists.return_value = True
            with patch("builtins.open", mock_open(read_data=json.dumps(data))):
                positions = load_treasury_positions()

        # Only the one with status="open" should be returned
        assert len(positions) == 1
        assert positions[0]["symbol"] == "BONK"

    def test_load_positions_all_closed(self):
        """Should return empty list when all positions are closed."""
        data = {
            "positions": [
                {"id": "pos_001", "symbol": "SOL", "status": "closed"},
                {"id": "pos_002", "symbol": "BONK", "status": "closed"},
            ]
        }
        with patch("tg_bot.services.treasury_monitor.POSITIONS_FILE") as mock_file:
            mock_file.exists.return_value = True
            with patch("builtins.open", mock_open(read_data=json.dumps(data))):
                positions = load_treasury_positions()

        assert positions == []

    def test_load_positions_io_error(self):
        """Should handle IO errors gracefully."""
        with patch("tg_bot.services.treasury_monitor.POSITIONS_FILE") as mock_file:
            mock_file.exists.return_value = True
            with patch("builtins.open", side_effect=IOError("Disk error")):
                positions = load_treasury_positions()

        assert positions == []


# ============================================================================
# Test: Position Price Updates
# ============================================================================

class TestUpdatePositionPrice:
    """Tests for update_position_price function."""

    def test_update_price_success(self, sample_positions):
        """Should update position with new price."""
        original_data = json.dumps(sample_positions)
        written_data = []

        def mock_write(data):
            written_data.append(data)

        mock_file_handle = MagicMock()
        mock_file_handle.read.return_value = original_data
        mock_file_handle.write.side_effect = mock_write

        with patch("tg_bot.services.treasury_monitor.POSITIONS_FILE") as mock_file:
            mock_file.exists.return_value = True
            with patch("builtins.open", return_value=mock_file_handle):
                mock_file_handle.__enter__ = MagicMock(return_value=mock_file_handle)
                mock_file_handle.__exit__ = MagicMock(return_value=False)
                update_position_price("pos_001", 0.002)

        # Verify write was called
        assert len(written_data) > 0

    def test_update_price_file_not_exists(self):
        """Should do nothing when file doesn't exist."""
        with patch("tg_bot.services.treasury_monitor.POSITIONS_FILE") as mock_file:
            mock_file.exists.return_value = False
            # Should not raise
            update_position_price("pos_001", 0.002)

    def test_update_price_position_not_found(self, sample_positions):
        """Should handle position not found gracefully."""
        with patch("tg_bot.services.treasury_monitor.POSITIONS_FILE") as mock_file:
            mock_file.exists.return_value = True
            with patch("builtins.open", mock_open(read_data=json.dumps(sample_positions))):
                # Should not raise for non-existent position
                update_position_price("nonexistent_pos", 0.002)

    def test_update_price_io_error(self):
        """Should handle IO errors gracefully."""
        with patch("tg_bot.services.treasury_monitor.POSITIONS_FILE") as mock_file:
            mock_file.exists.return_value = True
            with patch("builtins.open", side_effect=IOError("Write error")):
                # Should not raise
                update_position_price("pos_001", 0.002)


# ============================================================================
# Test: Treasury Signals Loading
# ============================================================================

class TestLoadTreasurySignals:
    """Tests for load_treasury_signals function."""

    def test_load_signals_success(self, sample_signals):
        """Should load and sort signals by timestamp."""
        with patch("tg_bot.services.treasury_monitor.TREASURY_SIGNALS_FILE") as mock_file:
            mock_file.exists.return_value = True
            with patch("builtins.open", mock_open(read_data=json.dumps(sample_signals))):
                signals = load_treasury_signals()

        # Should be sorted newest first
        assert len(signals) == 3
        assert signals[0]["id"] == "sig_001"  # Newest
        assert signals[2]["id"] == "sig_003"  # Oldest

    def test_load_signals_with_limit(self, sample_signals):
        """Should respect the limit parameter."""
        with patch("tg_bot.services.treasury_monitor.TREASURY_SIGNALS_FILE") as mock_file:
            mock_file.exists.return_value = True
            with patch("builtins.open", mock_open(read_data=json.dumps(sample_signals))):
                signals = load_treasury_signals(limit=2)

        assert len(signals) == 2

    def test_load_signals_file_not_exists(self):
        """Should return empty list when file doesn't exist."""
        with patch("tg_bot.services.treasury_monitor.TREASURY_SIGNALS_FILE") as mock_file:
            mock_file.exists.return_value = False
            signals = load_treasury_signals()

        assert signals == []

    def test_load_signals_empty_file(self):
        """Should return empty list for empty signals."""
        data = {"signals": []}
        with patch("tg_bot.services.treasury_monitor.TREASURY_SIGNALS_FILE") as mock_file:
            mock_file.exists.return_value = True
            with patch("builtins.open", mock_open(read_data=json.dumps(data))):
                signals = load_treasury_signals()

        assert signals == []

    def test_load_signals_invalid_json(self):
        """Should handle invalid JSON gracefully."""
        with patch("tg_bot.services.treasury_monitor.TREASURY_SIGNALS_FILE") as mock_file:
            mock_file.exists.return_value = True
            with patch("builtins.open", mock_open(read_data="invalid json")):
                signals = load_treasury_signals()

        assert signals == []

    def test_load_signals_limit_zero(self, sample_signals):
        """Should return empty list for limit=0."""
        with patch("tg_bot.services.treasury_monitor.TREASURY_SIGNALS_FILE") as mock_file:
            mock_file.exists.return_value = True
            with patch("builtins.open", mock_open(read_data=json.dumps(sample_signals))):
                signals = load_treasury_signals(limit=0)

        assert signals == []

    def test_load_signals_limit_exceeds_count(self, sample_signals):
        """Should return all signals when limit exceeds count."""
        with patch("tg_bot.services.treasury_monitor.TREASURY_SIGNALS_FILE") as mock_file:
            mock_file.exists.return_value = True
            with patch("builtins.open", mock_open(read_data=json.dumps(sample_signals))):
                signals = load_treasury_signals(limit=100)

        assert len(signals) == 3


# ============================================================================
# Test: Price Fetching
# ============================================================================

class TestGetCurrentPrice:
    """Tests for get_current_price function."""

    @pytest.mark.asyncio
    async def test_get_price_success_price_usd(self):
        """Should fetch price from bags.fm API (price_usd field)."""
        mock_api = AsyncMock()
        mock_api.get_token_info = AsyncMock(return_value={"price_usd": 1.5})

        with patch("core.bags_api.get_bags_api", return_value=mock_api):
            price = await get_current_price("SOL_mint_address")

        assert price == 1.5
        mock_api.get_token_info.assert_called_once_with("SOL_mint_address")

    @pytest.mark.asyncio
    async def test_get_price_success_price_field(self):
        """Should fallback to price field if price_usd not present."""
        mock_api = AsyncMock()
        mock_api.get_token_info = AsyncMock(return_value={"price": 2.5})

        with patch("core.bags_api.get_bags_api", return_value=mock_api):
            price = await get_current_price("SOL_mint_address")

        assert price == 2.5

    @pytest.mark.asyncio
    async def test_get_price_no_token_info(self):
        """Should return None when token info not available."""
        mock_api = AsyncMock()
        mock_api.get_token_info = AsyncMock(return_value=None)

        with patch("core.bags_api.get_bags_api", return_value=mock_api):
            price = await get_current_price("unknown_token")

        assert price is None

    @pytest.mark.asyncio
    async def test_get_price_api_error(self):
        """Should handle API errors gracefully."""
        mock_api = AsyncMock()
        mock_api.get_token_info = AsyncMock(side_effect=Exception("API timeout"))

        with patch("core.bags_api.get_bags_api", return_value=mock_api):
            price = await get_current_price("SOL_mint_address")

        assert price is None

    @pytest.mark.asyncio
    async def test_get_price_zero_price(self):
        """Should return 0.0 for zero price."""
        mock_api = AsyncMock()
        mock_api.get_token_info = AsyncMock(return_value={"price_usd": 0})

        with patch("core.bags_api.get_bags_api", return_value=mock_api):
            price = await get_current_price("dead_token")

        assert price == 0.0

    @pytest.mark.asyncio
    async def test_get_price_string_price(self):
        """Should handle string price values."""
        mock_api = AsyncMock()
        mock_api.get_token_info = AsyncMock(return_value={"price_usd": "1.25"})

        with patch("core.bags_api.get_bags_api", return_value=mock_api):
            price = await get_current_price("SOL_mint")

        # Should be converted to float
        assert price == 1.25


# ============================================================================
# Test: PnL Alert System
# ============================================================================

class TestSendPnlAlert:
    """Tests for send_pnl_alert function."""

    @pytest.fixture
    def mock_alert_modules(self):
        """Create mocks for modules imported inside send_pnl_alert."""
        import sys

        mock_bot = AsyncMock()
        mock_bot.send_message = AsyncMock()

        mock_app = MagicMock()
        mock_app.bot = mock_bot

        mock_bot_core = MagicMock()
        mock_bot_core.application = mock_app

        mock_config_loader = MagicMock()
        mock_config_loader.load_config = MagicMock(return_value={"telegram": {"admin_ids": [12345]}})

        return {
            "mock_bot": mock_bot,
            "mock_app": mock_app,
            "mock_bot_core": mock_bot_core,
            "mock_config_loader": mock_config_loader,
        }

    @pytest.mark.asyncio
    async def test_send_gain_alert(self, mock_alert_modules):
        """Should send gain alert with correct formatting."""
        import sys
        position = {
            "symbol": "SOL",
            "entry_price": 1.0,
            "current_price": 1.15,
            "amount": 1000,
        }

        mock_bot = mock_alert_modules["mock_bot"]
        mock_bot_core = mock_alert_modules["mock_bot_core"]
        mock_config_loader = mock_alert_modules["mock_config_loader"]

        with patch.dict(sys.modules, {
            "tg_bot.bot_core": mock_bot_core,
            "core.config.loader": mock_config_loader,
        }):
            await send_pnl_alert(position, 15.0, "gain")

        mock_bot.send_message.assert_called_once()
        call_args = mock_bot.send_message.call_args
        assert call_args.kwargs["chat_id"] == 12345
        assert "GAIN" in call_args.kwargs["text"]
        assert "SOL" in call_args.kwargs["text"]

    @pytest.mark.asyncio
    async def test_send_loss_alert(self, mock_alert_modules):
        """Should send loss alert with correct formatting."""
        import sys
        position = {
            "symbol": "BONK",
            "entry_price": 0.001,
            "current_price": 0.00093,
            "amount": 500000,
        }

        mock_bot = mock_alert_modules["mock_bot"]
        mock_bot_core = mock_alert_modules["mock_bot_core"]
        mock_config_loader = mock_alert_modules["mock_config_loader"]

        with patch.dict(sys.modules, {
            "tg_bot.bot_core": mock_bot_core,
            "core.config.loader": mock_config_loader,
        }):
            await send_pnl_alert(position, -7.0, "loss")

        call_args = mock_bot.send_message.call_args
        assert "LOSS" in call_args.kwargs["text"]

    @pytest.mark.asyncio
    async def test_send_alert_multiple_admins(self):
        """Should send alerts to all admin IDs."""
        import sys
        position = {"symbol": "SOL", "entry_price": 1.0, "current_price": 1.1, "amount": 100}

        mock_bot = AsyncMock()
        mock_bot.send_message = AsyncMock()

        mock_app = MagicMock()
        mock_app.bot = mock_bot

        mock_bot_core = MagicMock()
        mock_bot_core.application = mock_app

        mock_config_loader = MagicMock()
        mock_config_loader.load_config = MagicMock(return_value={"telegram": {"admin_ids": [111, 222, 333]}})

        with patch.dict(sys.modules, {
            "tg_bot.bot_core": mock_bot_core,
            "core.config.loader": mock_config_loader,
        }):
            await send_pnl_alert(position, 10.0, "gain")

        # Should be called 3 times (once per admin)
        assert mock_bot.send_message.call_count == 3

    @pytest.mark.asyncio
    async def test_send_alert_no_admins(self):
        """Should handle empty admin list gracefully."""
        import sys
        position = {"symbol": "SOL", "entry_price": 1.0, "current_price": 1.1, "amount": 100}

        mock_bot_core = MagicMock()
        mock_bot_core.application = MagicMock()

        mock_config_loader = MagicMock()
        mock_config_loader.load_config = MagicMock(return_value={"telegram": {"admin_ids": []}})

        with patch.dict(sys.modules, {
            "tg_bot.bot_core": mock_bot_core,
            "core.config.loader": mock_config_loader,
        }):
            # Should not raise
            await send_pnl_alert(position, 10.0, "gain")

    @pytest.mark.asyncio
    async def test_send_alert_no_application(self):
        """Should handle missing application gracefully."""
        import sys
        position = {"symbol": "SOL", "entry_price": 1.0, "current_price": 1.1, "amount": 100}

        mock_bot_core = MagicMock()
        mock_bot_core.application = None

        mock_config_loader = MagicMock()
        mock_config_loader.load_config = MagicMock(return_value={"telegram": {"admin_ids": [12345]}})

        with patch.dict(sys.modules, {
            "tg_bot.bot_core": mock_bot_core,
            "core.config.loader": mock_config_loader,
        }):
            # Should not raise
            await send_pnl_alert(position, 10.0, "gain")

    @pytest.mark.asyncio
    async def test_send_alert_telegram_error(self, mock_alert_modules):
        """Should handle Telegram API errors gracefully."""
        import sys
        position = {"symbol": "SOL", "entry_price": 1.0, "current_price": 1.1, "amount": 100}

        mock_bot = mock_alert_modules["mock_bot"]
        mock_bot.send_message = AsyncMock(side_effect=Exception("Telegram API error"))

        mock_bot_core = mock_alert_modules["mock_bot_core"]
        mock_config_loader = mock_alert_modules["mock_config_loader"]

        with patch.dict(sys.modules, {
            "tg_bot.bot_core": mock_bot_core,
            "core.config.loader": mock_config_loader,
        }):
            # Should not raise
            await send_pnl_alert(position, 10.0, "gain")

    @pytest.mark.asyncio
    async def test_alert_message_format_gain(self, mock_alert_modules):
        """Should format gain message correctly."""
        import sys
        position = {
            "symbol": "TEST",
            "entry_price": 1.0,
            "current_price": 1.5,
            "amount": 1000,
        }

        mock_bot = mock_alert_modules["mock_bot"]
        mock_bot_core = mock_alert_modules["mock_bot_core"]
        mock_config_loader = mock_alert_modules["mock_config_loader"]

        with patch.dict(sys.modules, {
            "tg_bot.bot_core": mock_bot_core,
            "core.config.loader": mock_config_loader,
        }):
            await send_pnl_alert(position, 50.0, "gain")

        call_args = mock_bot.send_message.call_args
        text = call_args.kwargs["text"]
        assert "TEST" in text
        assert "+50.0%" in text
        assert "$1.000000" in text  # Entry price
        assert "$1.500000" in text  # Current price

    @pytest.mark.asyncio
    async def test_alert_parse_mode_markdown(self, mock_alert_modules):
        """Should use Markdown parse mode."""
        import sys
        position = {"symbol": "SOL", "entry_price": 1.0, "current_price": 1.1, "amount": 100}

        mock_bot = mock_alert_modules["mock_bot"]
        mock_bot_core = mock_alert_modules["mock_bot_core"]
        mock_config_loader = mock_alert_modules["mock_config_loader"]

        with patch.dict(sys.modules, {
            "tg_bot.bot_core": mock_bot_core,
            "core.config.loader": mock_config_loader,
        }):
            await send_pnl_alert(position, 10.0, "gain")

        call_args = mock_bot.send_message.call_args
        assert call_args.kwargs["parse_mode"] == "Markdown"


# ============================================================================
# Test: TreasuryMonitor Service
# ============================================================================

class TestTreasuryMonitorInit:
    """Tests for TreasuryMonitor initialization."""

    def test_default_update_interval(self):
        """Should use default 5s update interval."""
        monitor = TreasuryMonitor()
        assert monitor.update_interval == 5

    def test_custom_update_interval(self):
        """Should accept custom update interval."""
        monitor = TreasuryMonitor(update_interval=10)
        assert monitor.update_interval == 10

    def test_initial_state(self):
        """Should initialize with correct default state."""
        monitor = TreasuryMonitor()
        assert monitor.running is False
        assert monitor.last_alerts == {}


class TestTreasuryMonitorStart:
    """Tests for TreasuryMonitor.start() method."""

    @pytest.mark.asyncio
    async def test_start_sets_running(self, treasury_monitor):
        """Should set running=True when started."""
        async def stop_after_delay():
            await asyncio.sleep(0.05)
            treasury_monitor.stop()

        asyncio.create_task(stop_after_delay())

        with patch.object(treasury_monitor, "update_all_positions", new_callable=AsyncMock):
            await treasury_monitor.start()

        # After stop, running should be False
        assert treasury_monitor.running is False

    @pytest.mark.asyncio
    async def test_start_calls_update_positions(self, treasury_monitor):
        """Should call update_all_positions in the loop."""
        call_count = 0

        async def mock_update():
            nonlocal call_count
            call_count += 1
            if call_count >= 2:
                treasury_monitor.stop()

        treasury_monitor.update_all_positions = mock_update

        await treasury_monitor.start()

        assert call_count >= 2

    @pytest.mark.asyncio
    async def test_start_handles_errors(self, treasury_monitor):
        """Should continue running after errors in update."""
        call_count = 0

        async def mock_update_with_error():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise Exception("Test error")
            if call_count >= 3:
                treasury_monitor.stop()

        treasury_monitor.update_all_positions = mock_update_with_error

        await treasury_monitor.start()

        # Should have continued despite error
        assert call_count >= 3


class TestTreasuryMonitorStop:
    """Tests for TreasuryMonitor.stop() method."""

    def test_stop_sets_running_false(self, treasury_monitor):
        """Should set running=False."""
        treasury_monitor.running = True
        treasury_monitor.stop()
        assert treasury_monitor.running is False


class TestTreasuryMonitorUpdateAllPositions:
    """Tests for TreasuryMonitor.update_all_positions() method."""

    @pytest.mark.asyncio
    async def test_update_all_with_positions(self, treasury_monitor, sample_positions):
        """Should update each open position."""
        open_positions = [p for p in sample_positions["positions"] if p["status"] == "open"]

        with patch("tg_bot.services.treasury_monitor.load_treasury_positions", return_value=open_positions):
            with patch.object(treasury_monitor, "update_position", new_callable=AsyncMock) as mock_update:
                await treasury_monitor.update_all_positions()

        assert mock_update.call_count == 2  # 2 open positions

    @pytest.mark.asyncio
    async def test_update_all_no_positions(self, treasury_monitor):
        """Should handle empty positions gracefully."""
        with patch("tg_bot.services.treasury_monitor.load_treasury_positions", return_value=[]):
            with patch.object(treasury_monitor, "update_position", new_callable=AsyncMock) as mock_update:
                await treasury_monitor.update_all_positions()

        mock_update.assert_not_called()

    @pytest.mark.asyncio
    async def test_update_all_handles_individual_errors(self, treasury_monitor, sample_positions):
        """Should continue updating other positions if one fails."""
        open_positions = [p for p in sample_positions["positions"] if p["status"] == "open"]

        async def fail_on_first(position):
            if position["id"] == "pos_001":
                raise Exception("Failed to update first position")

        with patch("tg_bot.services.treasury_monitor.load_treasury_positions", return_value=open_positions):
            with patch.object(treasury_monitor, "update_position", side_effect=fail_on_first):
                # Should not raise
                await treasury_monitor.update_all_positions()


class TestTreasuryMonitorUpdatePosition:
    """Tests for TreasuryMonitor.update_position() method."""

    @pytest.mark.asyncio
    async def test_update_position_success(self, treasury_monitor):
        """Should fetch price and update position."""
        position = {
            "id": "pos_001",
            "address": "SOL_mint",
            "entry_price": 1.0,
            "symbol": "SOL",
        }

        with patch("tg_bot.services.treasury_monitor.get_current_price", new_callable=AsyncMock, return_value=1.15):
            with patch("tg_bot.services.treasury_monitor.update_position_price") as mock_update:
                with patch.object(treasury_monitor, "check_alerts", new_callable=AsyncMock):
                    await treasury_monitor.update_position(position)

        mock_update.assert_called_once_with("pos_001", 1.15)

    @pytest.mark.asyncio
    async def test_update_position_no_address(self, treasury_monitor):
        """Should skip position without address."""
        position = {"id": "pos_001", "entry_price": 1.0}

        with patch("tg_bot.services.treasury_monitor.get_current_price", new_callable=AsyncMock) as mock_price:
            await treasury_monitor.update_position(position)

        mock_price.assert_not_called()

    @pytest.mark.asyncio
    async def test_update_position_zero_entry_price(self, treasury_monitor):
        """Should skip position with zero entry price."""
        position = {"id": "pos_001", "address": "SOL_mint", "entry_price": 0}

        with patch("tg_bot.services.treasury_monitor.get_current_price", new_callable=AsyncMock) as mock_price:
            await treasury_monitor.update_position(position)

        mock_price.assert_not_called()

    @pytest.mark.asyncio
    async def test_update_position_no_price_available(self, treasury_monitor):
        """Should skip when price is unavailable."""
        position = {"id": "pos_001", "address": "SOL_mint", "entry_price": 1.0}

        with patch("tg_bot.services.treasury_monitor.get_current_price", new_callable=AsyncMock, return_value=None):
            with patch("tg_bot.services.treasury_monitor.update_position_price") as mock_update:
                await treasury_monitor.update_position(position)

        mock_update.assert_not_called()

    @pytest.mark.asyncio
    async def test_update_position_calculates_pnl(self, treasury_monitor):
        """Should calculate correct PnL percentage."""
        position = {
            "id": "pos_001",
            "address": "SOL_mint",
            "entry_price": 1.0,
            "symbol": "SOL",
        }

        with patch("tg_bot.services.treasury_monitor.get_current_price", new_callable=AsyncMock, return_value=1.2):
            with patch("tg_bot.services.treasury_monitor.update_position_price"):
                with patch.object(treasury_monitor, "check_alerts", new_callable=AsyncMock) as mock_check:
                    await treasury_monitor.update_position(position)

        # PnL should be +20%
        mock_check.assert_called_once()
        call_args = mock_check.call_args[0]
        assert abs(call_args[1] - 20.0) < 0.01  # PnL pct


class TestTreasuryMonitorCheckAlerts:
    """Tests for TreasuryMonitor.check_alerts() method."""

    @pytest.mark.asyncio
    async def test_gain_alert_triggered(self, treasury_monitor):
        """Should trigger gain alert when PnL >= 10%."""
        position = {"id": "pos_001", "symbol": "SOL", "current_price": 1.0}

        with patch("tg_bot.services.treasury_monitor.send_pnl_alert", new_callable=AsyncMock) as mock_alert:
            await treasury_monitor.check_alerts(position, 15.0)

        mock_alert.assert_called_once_with(position, 15.0, "gain")
        assert "pos_001" in treasury_monitor.last_alerts

    @pytest.mark.asyncio
    async def test_loss_alert_triggered(self, treasury_monitor):
        """Should trigger loss alert when PnL <= -5%."""
        position = {"id": "pos_002", "symbol": "BONK", "current_price": 0.0009}

        with patch("tg_bot.services.treasury_monitor.send_pnl_alert", new_callable=AsyncMock) as mock_alert:
            await treasury_monitor.check_alerts(position, -7.0)

        mock_alert.assert_called_once_with(position, -7.0, "loss")

    @pytest.mark.asyncio
    async def test_no_alert_within_threshold(self, treasury_monitor):
        """Should not trigger alert when PnL is within thresholds."""
        position = {"id": "pos_001", "symbol": "SOL"}

        with patch("tg_bot.services.treasury_monitor.send_pnl_alert", new_callable=AsyncMock) as mock_alert:
            await treasury_monitor.check_alerts(position, 5.0)  # +5% (below 10% gain)
            await treasury_monitor.check_alerts(position, -3.0)  # -3% (above -5% loss)

        mock_alert.assert_not_called()

    @pytest.mark.asyncio
    async def test_alert_cooldown(self, treasury_monitor):
        """Should not send duplicate alerts within 1 hour."""
        position = {"id": "pos_001", "symbol": "SOL"}

        # Set last alert time to recent
        treasury_monitor.last_alerts["pos_001"] = datetime.now(timezone.utc)

        with patch("tg_bot.services.treasury_monitor.send_pnl_alert", new_callable=AsyncMock) as mock_alert:
            await treasury_monitor.check_alerts(position, 15.0)

        mock_alert.assert_not_called()

    @pytest.mark.asyncio
    async def test_alert_after_cooldown(self, treasury_monitor):
        """Should send alert after cooldown period."""
        position = {"id": "pos_001", "symbol": "SOL"}

        # Set last alert time to over 1 hour ago
        treasury_monitor.last_alerts["pos_001"] = datetime.now(timezone.utc) - timedelta(hours=2)

        with patch("tg_bot.services.treasury_monitor.send_pnl_alert", new_callable=AsyncMock) as mock_alert:
            await treasury_monitor.check_alerts(position, 15.0)

        mock_alert.assert_called_once()

    @pytest.mark.asyncio
    async def test_exact_threshold_gain(self, treasury_monitor):
        """Should trigger at exactly 10% gain."""
        position = {"id": "pos_001", "symbol": "SOL"}

        with patch("tg_bot.services.treasury_monitor.send_pnl_alert", new_callable=AsyncMock) as mock_alert:
            await treasury_monitor.check_alerts(position, 10.0)

        mock_alert.assert_called_once_with(position, 10.0, "gain")

    @pytest.mark.asyncio
    async def test_exact_threshold_loss(self, treasury_monitor):
        """Should trigger at exactly -5% loss."""
        position = {"id": "pos_001", "symbol": "SOL"}

        with patch("tg_bot.services.treasury_monitor.send_pnl_alert", new_callable=AsyncMock) as mock_alert:
            await treasury_monitor.check_alerts(position, -5.0)

        mock_alert.assert_called_once_with(position, -5.0, "loss")


# ============================================================================
# Test: Singleton and Factory Functions
# ============================================================================

class TestGetTreasuryMonitor:
    """Tests for get_treasury_monitor singleton function."""

    def test_returns_same_instance(self, reset_singleton):
        """Should return the same instance on multiple calls."""
        monitor1 = get_treasury_monitor()
        monitor2 = get_treasury_monitor()

        assert monitor1 is monitor2

    def test_creates_instance_on_first_call(self, reset_singleton):
        """Should create new instance if none exists."""
        monitor = get_treasury_monitor()

        assert isinstance(monitor, TreasuryMonitor)


class TestStartTreasuryMonitor:
    """Tests for start_treasury_monitor function."""

    @pytest.mark.asyncio
    async def test_starts_monitor(self, reset_singleton):
        """Should start the singleton monitor."""
        with patch.object(TreasuryMonitor, "start", new_callable=AsyncMock) as mock_start:
            await start_treasury_monitor()

        mock_start.assert_called_once()


# ============================================================================
# Test: Live Treasury Summary
# ============================================================================

class TestGetLiveTreasurySummary:
    """Tests for get_live_treasury_summary function."""

    def test_summary_with_positions(self, sample_positions):
        """Should calculate correct summary for positions."""
        open_positions = [p for p in sample_positions["positions"] if p["status"] == "open"]

        with patch("tg_bot.services.treasury_monitor.load_treasury_positions", return_value=open_positions):
            summary = get_live_treasury_summary()

        assert summary["total_positions"] == 2
        assert summary["total_value_sol"] == 0.8  # 0.5 + 0.3
        assert "top_gainers" in summary
        assert "top_losers" in summary

    def test_summary_no_positions(self):
        """Should return zeros for empty positions."""
        with patch("tg_bot.services.treasury_monitor.load_treasury_positions", return_value=[]):
            summary = get_live_treasury_summary()

        assert summary["total_positions"] == 0
        assert summary["total_value_sol"] == 0.0
        assert summary["total_pnl_usd"] == 0.0
        assert summary["total_pnl_pct"] == 0.0
        assert summary["top_gainers"] == []
        assert summary["top_losers"] == []

    def test_summary_pnl_calculations(self):
        """Should calculate PnL correctly."""
        positions = [
            {
                "id": "pos_001",
                "symbol": "GAINER",
                "amount": 1000,
                "amount_sol": 1.0,
                "entry_price": 1.0,
                "current_price": 1.5,  # +50%
                "status": "open",
            },
            {
                "id": "pos_002",
                "symbol": "LOSER",
                "amount": 1000,
                "amount_sol": 1.0,
                "entry_price": 1.0,
                "current_price": 0.8,  # -20%
                "status": "open",
            },
        ]

        with patch("tg_bot.services.treasury_monitor.load_treasury_positions", return_value=positions):
            summary = get_live_treasury_summary()

        # GAINER: (1.5 - 1.0) * 1000 = +500
        # LOSER: (0.8 - 1.0) * 1000 = -200
        # Total PnL: +300
        assert abs(summary["total_pnl_usd"] - 300.0) < 0.01

        # Top gainers should be GAINER (first in sorted list)
        assert len(summary["top_gainers"]) >= 1
        assert summary["top_gainers"][0]["symbol"] == "GAINER"
        assert abs(summary["top_gainers"][0]["pnl_pct"] - 50.0) < 0.01

    def test_summary_top_gainers_losers_sorting(self):
        """Should sort top gainers/losers correctly."""
        positions = [
            {"id": "1", "symbol": "A", "amount": 100, "amount_sol": 0.1, "entry_price": 1.0, "current_price": 1.1, "status": "open"},  # +10%
            {"id": "2", "symbol": "B", "amount": 100, "amount_sol": 0.1, "entry_price": 1.0, "current_price": 1.3, "status": "open"},  # +30%
            {"id": "3", "symbol": "C", "amount": 100, "amount_sol": 0.1, "entry_price": 1.0, "current_price": 0.9, "status": "open"},  # -10%
            {"id": "4", "symbol": "D", "amount": 100, "amount_sol": 0.1, "entry_price": 1.0, "current_price": 0.7, "status": "open"},  # -30%
        ]

        with patch("tg_bot.services.treasury_monitor.load_treasury_positions", return_value=positions):
            summary = get_live_treasury_summary()

        # Top gainers should be B (+30%), A (+10%), C (-10%)
        assert summary["top_gainers"][0]["symbol"] == "B"
        assert summary["top_gainers"][1]["symbol"] == "A"

        # Top losers should be D (-30%), C (-10%), A (+10%)
        assert summary["top_losers"][0]["symbol"] == "D"

    def test_summary_handles_zero_entry_price(self):
        """Should handle zero entry price gracefully."""
        positions = [
            {"id": "1", "symbol": "ZERO", "amount": 100, "amount_sol": 0.1, "entry_price": 0, "current_price": 1.0, "status": "open"},
            {"id": "2", "symbol": "VALID", "amount": 100, "amount_sol": 0.1, "entry_price": 1.0, "current_price": 1.1, "status": "open"},
        ]

        with patch("tg_bot.services.treasury_monitor.load_treasury_positions", return_value=positions):
            summary = get_live_treasury_summary()

        # Should only include VALID in calculations
        assert summary["total_positions"] == 2
        assert len(summary["top_gainers"]) == 1

    def test_summary_handles_zero_current_price(self):
        """Should handle zero current price gracefully."""
        positions = [
            {"id": "1", "symbol": "RUGGED", "amount": 100, "amount_sol": 0.1, "entry_price": 1.0, "current_price": 0, "status": "open"},
        ]

        with patch("tg_bot.services.treasury_monitor.load_treasury_positions", return_value=positions):
            summary = get_live_treasury_summary()

        # Should handle but not include in PnL calc
        assert summary["total_positions"] == 1

    def test_summary_error_handling(self):
        """Should return empty summary on error."""
        with patch("tg_bot.services.treasury_monitor.load_treasury_positions", side_effect=Exception("DB error")):
            summary = get_live_treasury_summary()

        assert summary["total_positions"] == 0
        assert summary["total_value_sol"] == 0.0

    def test_summary_limits_top_gainers_losers(self):
        """Should limit top gainers/losers to 3 each."""
        positions = [
            {"id": str(i), "symbol": f"T{i}", "amount": 100, "amount_sol": 0.1, "entry_price": 1.0, "current_price": 1.0 + i * 0.1, "status": "open"}
            for i in range(10)
        ]

        with patch("tg_bot.services.treasury_monitor.load_treasury_positions", return_value=positions):
            summary = get_live_treasury_summary()

        assert len(summary["top_gainers"]) == 3
        assert len(summary["top_losers"]) == 3


# ============================================================================
# Test: Error Handling and Edge Cases
# ============================================================================

class TestErrorHandling:
    """Tests for error handling and edge cases."""

    @pytest.mark.asyncio
    async def test_update_position_missing_fields(self, treasury_monitor):
        """Should handle positions with missing fields."""
        position = {"id": "incomplete"}

        # Should not raise
        await treasury_monitor.update_position(position)

    @pytest.mark.asyncio
    async def test_check_alerts_missing_position_id(self, treasury_monitor):
        """Should handle position without id."""
        position = {"symbol": "SOL"}

        with patch("tg_bot.services.treasury_monitor.send_pnl_alert", new_callable=AsyncMock) as mock_alert:
            await treasury_monitor.check_alerts(position, 15.0)

        # Should still send alert
        mock_alert.assert_called_once()

    def test_load_positions_permission_error(self):
        """Should handle permission errors."""
        with patch("tg_bot.services.treasury_monitor.POSITIONS_FILE") as mock_file:
            mock_file.exists.return_value = True
            with patch("builtins.open", side_effect=PermissionError("Access denied")):
                positions = load_treasury_positions()

        assert positions == []

    def test_summary_none_values(self):
        """Should handle None values in position fields - triggers exception catch."""
        positions = [
            {
                "id": "1",
                "symbol": "TEST",
                "amount": None,
                "amount_sol": None,
                "entry_price": None,
                "current_price": None,
                "status": "open",
            },
        ]

        with patch("tg_bot.services.treasury_monitor.load_treasury_positions", return_value=positions):
            summary = get_live_treasury_summary()

        # None values cause TypeError in sum(), caught by exception handler
        # Returns empty summary
        assert summary["total_positions"] == 0

    def test_summary_string_values(self):
        """Should handle string values that should be numeric - amount_sol strings cause TypeError."""
        positions = [
            {
                "id": "1",
                "symbol": "TEST",
                "amount": "100",
                "amount_sol": "0.1",  # String here will cause sum() to fail
                "entry_price": "1.0",
                "current_price": "1.1",
                "status": "open",
            },
        ]

        with patch("tg_bot.services.treasury_monitor.load_treasury_positions", return_value=positions):
            summary = get_live_treasury_summary()

        # String in amount_sol causes TypeError in sum(), caught by exception handler
        assert summary["total_positions"] == 0

    def test_summary_float_amount_sol_string_others(self):
        """Should handle string values for entry/current price but float amount_sol."""
        positions = [
            {
                "id": "1",
                "symbol": "TEST",
                "amount": "100",
                "amount_sol": 0.1,  # Float - sum works
                "entry_price": "1.0",
                "current_price": "1.1",
                "status": "open",
            },
        ]

        with patch("tg_bot.services.treasury_monitor.load_treasury_positions", return_value=positions):
            summary = get_live_treasury_summary()

        # amount_sol is float, so sum() works; entry_price/current_price are converted via float()
        assert summary["total_positions"] == 1
        assert summary["total_value_sol"] == 0.1


# ============================================================================
# Test: Integration Scenarios
# ============================================================================

class TestIntegrationScenarios:
    """Integration tests for complete workflows."""

    @pytest.mark.asyncio
    async def test_full_update_cycle(self, treasury_monitor):
        """Test complete position update cycle."""
        positions = [
            {
                "id": "pos_001",
                "symbol": "SOL",
                "address": "SOL_mint",
                "amount": 1000,
                "amount_sol": 1.0,
                "entry_price": 1.0,
                "status": "open",
            },
        ]

        with patch("tg_bot.services.treasury_monitor.load_treasury_positions", return_value=positions):
            with patch("tg_bot.services.treasury_monitor.get_current_price", new_callable=AsyncMock, return_value=1.15):
                with patch("tg_bot.services.treasury_monitor.update_position_price") as mock_update:
                    with patch("tg_bot.services.treasury_monitor.send_pnl_alert", new_callable=AsyncMock) as mock_alert:
                        await treasury_monitor.update_all_positions()

        # Should update price
        mock_update.assert_called_once_with("pos_001", 1.15)

        # Should trigger gain alert (+15%)
        mock_alert.assert_called_once()

    @pytest.mark.asyncio
    async def test_multiple_positions_mixed_alerts(self, treasury_monitor):
        """Test multiple positions with different alert states."""
        positions = [
            {"id": "gainer", "symbol": "WIN", "address": "win_mint", "entry_price": 1.0, "status": "open"},
            {"id": "loser", "symbol": "LOSE", "address": "lose_mint", "entry_price": 1.0, "status": "open"},
            {"id": "stable", "symbol": "HOLD", "address": "hold_mint", "entry_price": 1.0, "status": "open"},
        ]

        async def mock_price(address):
            prices = {"win_mint": 1.2, "lose_mint": 0.9, "hold_mint": 1.02}
            return prices.get(address, 1.0)

        with patch("tg_bot.services.treasury_monitor.load_treasury_positions", return_value=positions):
            with patch("tg_bot.services.treasury_monitor.get_current_price", side_effect=mock_price):
                with patch("tg_bot.services.treasury_monitor.update_position_price"):
                    with patch("tg_bot.services.treasury_monitor.send_pnl_alert", new_callable=AsyncMock) as mock_alert:
                        await treasury_monitor.update_all_positions()

        # Gainer: +20% (alert), Loser: -10% (alert), Stable: +2% (no alert)
        assert mock_alert.call_count == 2
