"""
Unit Tests for TP/SL Monitor Service

Tests for:
- TPSLMonitor: Order monitoring with 10s poll loop
- Exit execution when triggers hit
- Ladder exit support
- Position schema updates with ladder_exits
"""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional


# =============================================================================
# Test: Position Schema with Ladder Exits
# =============================================================================

class TestPositionLadderExits:
    """Test Position dataclass with ladder_exits field."""

    def test_position_has_ladder_exits_field(self):
        """Position should have a ladder_exits field."""
        from bots.treasury.trading.types import Position, TradeDirection, TradeStatus

        pos = Position(
            id="test_1",
            token_mint="So11111111111111111111111111111111111111112",
            token_symbol="TEST",
            direction=TradeDirection.LONG,
            entry_price=1.0,
            current_price=1.0,
            amount=100.0,
            amount_usd=100.0,
            take_profit_price=1.5,
            stop_loss_price=0.8,
            status=TradeStatus.OPEN,
            opened_at=datetime.now(timezone.utc).isoformat(),
        )

        # Should have ladder_exits field
        assert hasattr(pos, 'ladder_exits')

    def test_position_ladder_exits_default_empty(self):
        """Ladder exits should default to empty list."""
        from bots.treasury.trading.types import Position, TradeDirection, TradeStatus

        pos = Position(
            id="test_1",
            token_mint="So11111111111111111111111111111111111111112",
            token_symbol="TEST",
            direction=TradeDirection.LONG,
            entry_price=1.0,
            current_price=1.0,
            amount=100.0,
            amount_usd=100.0,
            take_profit_price=1.5,
            stop_loss_price=0.8,
            status=TradeStatus.OPEN,
            opened_at=datetime.now(timezone.utc).isoformat(),
        )

        assert pos.ladder_exits == [] or pos.ladder_exits is None

    def test_position_ladder_exits_serialization(self):
        """Ladder exits should serialize/deserialize correctly."""
        from bots.treasury.trading.types import Position, TradeDirection, TradeStatus

        ladder_exits = [
            {"pnl_multiple": 2.0, "percent": 50, "executed": False},
            {"pnl_multiple": 5.0, "percent": 30, "executed": False},
            {"pnl_multiple": 10.0, "percent": 20, "executed": False},
        ]

        pos = Position(
            id="test_1",
            token_mint="So11111111111111111111111111111111111111112",
            token_symbol="TEST",
            direction=TradeDirection.LONG,
            entry_price=1.0,
            current_price=1.0,
            amount=100.0,
            amount_usd=100.0,
            take_profit_price=1.5,
            stop_loss_price=0.8,
            status=TradeStatus.OPEN,
            opened_at=datetime.now(timezone.utc).isoformat(),
            ladder_exits=ladder_exits,
        )

        # To dict
        data = pos.to_dict()
        assert "ladder_exits" in data
        assert data["ladder_exits"] == ladder_exits

        # From dict
        restored = Position.from_dict(data)
        assert restored.ladder_exits == ladder_exits


# =============================================================================
# Test: TPSLMonitor Core Functionality
# =============================================================================

class TestTPSLMonitor:
    """Test TPSLMonitor service."""

    @pytest.fixture
    def mock_position_manager(self):
        """Create mock position manager."""
        manager = MagicMock()
        manager.get_open_positions = MagicMock(return_value=[])
        manager.save_state = MagicMock()
        return manager

    @pytest.fixture
    def mock_price_service(self):
        """Create mock price service."""
        service = AsyncMock()
        service.get_token_price = AsyncMock(return_value=1.0)
        return service

    def test_monitor_initialization(self):
        """Monitor should initialize with correct defaults."""
        from core.risk.tp_sl_monitor import TPSLMonitor

        monitor = TPSLMonitor()

        assert monitor.poll_interval == 10  # 10 seconds
        assert monitor.running is False

    def test_monitor_custom_interval(self):
        """Monitor should accept custom poll interval."""
        from core.risk.tp_sl_monitor import TPSLMonitor

        monitor = TPSLMonitor(poll_interval=5)

        assert monitor.poll_interval == 5

    @pytest.mark.asyncio
    async def test_monitor_start_stop(self):
        """Monitor should start and stop correctly."""
        from core.risk.tp_sl_monitor import TPSLMonitor

        monitor = TPSLMonitor(poll_interval=1)

        # Start in background
        task = asyncio.create_task(monitor.start())
        await asyncio.sleep(0.1)

        assert monitor.running is True

        # Stop
        await monitor.stop()
        assert monitor.running is False

        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    @pytest.mark.asyncio
    async def test_check_position_tp_trigger(self, mock_position_manager):
        """Monitor should trigger TP when price exceeds tp_price."""
        from core.risk.tp_sl_monitor import TPSLMonitor
        from bots.treasury.trading.types import Position, TradeDirection, TradeStatus

        pos = Position(
            id="test_tp",
            token_mint="TestMint123",
            token_symbol="TEST",
            direction=TradeDirection.LONG,
            entry_price=1.0,
            current_price=1.5,  # Price went up
            amount=100.0,
            amount_usd=100.0,
            take_profit_price=1.4,  # TP at 1.4 (40% gain)
            stop_loss_price=0.8,
            status=TradeStatus.OPEN,
            opened_at=datetime.now(timezone.utc).isoformat(),
        )

        monitor = TPSLMonitor(position_manager=mock_position_manager)

        result = await monitor.check_position(pos, current_price=1.5)

        assert result["trigger"] == "tp"
        assert result["should_exit"] is True
        assert result["exit_percent"] == 100  # Full exit on TP

    @pytest.mark.asyncio
    async def test_check_position_sl_trigger(self, mock_position_manager):
        """Monitor should trigger SL when price drops below sl_price."""
        from core.risk.tp_sl_monitor import TPSLMonitor
        from bots.treasury.trading.types import Position, TradeDirection, TradeStatus

        pos = Position(
            id="test_sl",
            token_mint="TestMint123",
            token_symbol="TEST",
            direction=TradeDirection.LONG,
            entry_price=1.0,
            current_price=0.7,  # Price dropped
            amount=100.0,
            amount_usd=100.0,
            take_profit_price=1.5,
            stop_loss_price=0.8,  # SL at 0.8 (20% loss)
            status=TradeStatus.OPEN,
            opened_at=datetime.now(timezone.utc).isoformat(),
        )

        monitor = TPSLMonitor(position_manager=mock_position_manager)

        result = await monitor.check_position(pos, current_price=0.7)

        assert result["trigger"] == "sl"
        assert result["should_exit"] is True
        assert result["exit_percent"] == 100  # Full exit on SL

    @pytest.mark.asyncio
    async def test_check_position_no_trigger(self, mock_position_manager):
        """Monitor should not trigger when price is between SL and TP."""
        from core.risk.tp_sl_monitor import TPSLMonitor
        from bots.treasury.trading.types import Position, TradeDirection, TradeStatus

        pos = Position(
            id="test_normal",
            token_mint="TestMint123",
            token_symbol="TEST",
            direction=TradeDirection.LONG,
            entry_price=1.0,
            current_price=1.1,  # Price slightly up
            amount=100.0,
            amount_usd=100.0,
            take_profit_price=1.5,
            stop_loss_price=0.8,
            status=TradeStatus.OPEN,
            opened_at=datetime.now(timezone.utc).isoformat(),
        )

        monitor = TPSLMonitor(position_manager=mock_position_manager)

        result = await monitor.check_position(pos, current_price=1.1)

        assert result["trigger"] is None
        assert result["should_exit"] is False


# =============================================================================
# Test: Ladder Exit Logic
# =============================================================================

class TestLadderExits:
    """Test ladder exit functionality."""

    @pytest.fixture
    def mock_position_manager(self):
        """Create mock position manager."""
        manager = MagicMock()
        manager.get_open_positions = MagicMock(return_value=[])
        manager.save_state = MagicMock()
        return manager

    @pytest.mark.asyncio
    async def test_ladder_exit_first_tier(self, mock_position_manager):
        """Monitor should trigger first ladder exit at 2x."""
        from core.risk.tp_sl_monitor import TPSLMonitor
        from bots.treasury.trading.types import Position, TradeDirection, TradeStatus

        ladder_exits = [
            {"pnl_multiple": 2.0, "percent": 50, "executed": False},
            {"pnl_multiple": 5.0, "percent": 30, "executed": False},
            {"pnl_multiple": 10.0, "percent": 20, "executed": False},
        ]

        pos = Position(
            id="test_ladder",
            token_mint="TestMint123",
            token_symbol="TEST",
            direction=TradeDirection.LONG,
            entry_price=1.0,
            current_price=2.0,  # 2x (100% gain)
            amount=100.0,
            amount_usd=100.0,
            take_profit_price=15.0,  # Final TP at 15x
            stop_loss_price=0.8,
            status=TradeStatus.OPEN,
            opened_at=datetime.now(timezone.utc).isoformat(),
            ladder_exits=ladder_exits,
        )

        monitor = TPSLMonitor(position_manager=mock_position_manager)

        result = await monitor.check_position(pos, current_price=2.0)

        assert result["trigger"] == "ladder"
        assert result["should_exit"] is True
        assert result["exit_percent"] == 50  # 50% at 2x
        assert result["ladder_tier"] == 0  # First tier

    @pytest.mark.asyncio
    async def test_ladder_exit_second_tier(self, mock_position_manager):
        """Monitor should trigger second ladder exit at 5x (if first executed)."""
        from core.risk.tp_sl_monitor import TPSLMonitor
        from bots.treasury.trading.types import Position, TradeDirection, TradeStatus

        ladder_exits = [
            {"pnl_multiple": 2.0, "percent": 50, "executed": True},  # Already executed
            {"pnl_multiple": 5.0, "percent": 30, "executed": False},
            {"pnl_multiple": 10.0, "percent": 20, "executed": False},
        ]

        pos = Position(
            id="test_ladder_2",
            token_mint="TestMint123",
            token_symbol="TEST",
            direction=TradeDirection.LONG,
            entry_price=1.0,
            current_price=5.0,  # 5x (400% gain)
            amount=50.0,  # Half already sold at 2x
            amount_usd=50.0,
            take_profit_price=15.0,
            stop_loss_price=0.8,
            status=TradeStatus.OPEN,
            opened_at=datetime.now(timezone.utc).isoformat(),
            ladder_exits=ladder_exits,
        )

        monitor = TPSLMonitor(position_manager=mock_position_manager)

        result = await monitor.check_position(pos, current_price=5.0)

        assert result["trigger"] == "ladder"
        assert result["should_exit"] is True
        assert result["exit_percent"] == 30  # 30% at 5x
        assert result["ladder_tier"] == 1  # Second tier

    @pytest.mark.asyncio
    async def test_ladder_exit_skip_executed(self, mock_position_manager):
        """Monitor should skip already executed ladder tiers."""
        from core.risk.tp_sl_monitor import TPSLMonitor
        from bots.treasury.trading.types import Position, TradeDirection, TradeStatus

        ladder_exits = [
            {"pnl_multiple": 2.0, "percent": 50, "executed": True},
            {"pnl_multiple": 5.0, "percent": 30, "executed": True},
            {"pnl_multiple": 10.0, "percent": 20, "executed": False},
        ]

        pos = Position(
            id="test_ladder_skip",
            token_mint="TestMint123",
            token_symbol="TEST",
            direction=TradeDirection.LONG,
            entry_price=1.0,
            current_price=4.0,  # Between 2x and 5x, both executed
            amount=20.0,  # 80% already sold
            amount_usd=20.0,
            take_profit_price=15.0,
            stop_loss_price=0.8,
            status=TradeStatus.OPEN,
            opened_at=datetime.now(timezone.utc).isoformat(),
            ladder_exits=ladder_exits,
        )

        monitor = TPSLMonitor(position_manager=mock_position_manager)

        result = await monitor.check_position(pos, current_price=4.0)

        # Should not trigger since tiers 1 and 2 are executed and we're below tier 3
        assert result["trigger"] is None
        assert result["should_exit"] is False


# =============================================================================
# Test: Exit Execution
# =============================================================================

class TestPositionExitExecution:
    """Test position exit execution logic."""

    @pytest.fixture
    def mock_swap_service(self):
        """Create mock swap execution service."""
        service = AsyncMock()
        service.execute_sell = AsyncMock(return_value={
            "success": True,
            "tx_hash": "test_tx_hash_123",
            "amount_out": 1.5,
        })
        return service

    @pytest.mark.asyncio
    async def test_execute_tp_exit_full(self, mock_swap_service):
        """Should execute full TP exit correctly."""
        from core.risk.position_exit import PositionExitExecutor
        from bots.treasury.trading.types import Position, TradeDirection, TradeStatus

        pos = Position(
            id="test_tp_exit",
            token_mint="TestMint123",
            token_symbol="TEST",
            direction=TradeDirection.LONG,
            entry_price=1.0,
            current_price=1.5,
            amount=100.0,
            amount_usd=100.0,
            take_profit_price=1.4,
            stop_loss_price=0.8,
            status=TradeStatus.OPEN,
            opened_at=datetime.now(timezone.utc).isoformat(),
        )

        executor = PositionExitExecutor(swap_service=mock_swap_service)

        result = await executor.execute_exit(
            position=pos,
            trigger="tp",
            exit_percent=100,
        )

        assert result["success"] is True
        assert result["exit_type"] == "tp"
        assert result["amount_sold"] == 100.0  # Full amount
        mock_swap_service.execute_sell.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_sl_exit_full(self, mock_swap_service):
        """Should execute full SL exit correctly."""
        from core.risk.position_exit import PositionExitExecutor
        from bots.treasury.trading.types import Position, TradeDirection, TradeStatus

        pos = Position(
            id="test_sl_exit",
            token_mint="TestMint123",
            token_symbol="TEST",
            direction=TradeDirection.LONG,
            entry_price=1.0,
            current_price=0.7,
            amount=100.0,
            amount_usd=100.0,
            take_profit_price=1.5,
            stop_loss_price=0.8,
            status=TradeStatus.OPEN,
            opened_at=datetime.now(timezone.utc).isoformat(),
        )

        executor = PositionExitExecutor(swap_service=mock_swap_service)

        result = await executor.execute_exit(
            position=pos,
            trigger="sl",
            exit_percent=100,
        )

        assert result["success"] is True
        assert result["exit_type"] == "sl"
        assert result["amount_sold"] == 100.0

    @pytest.mark.asyncio
    async def test_execute_ladder_exit_partial(self, mock_swap_service):
        """Should execute partial ladder exit correctly."""
        from core.risk.position_exit import PositionExitExecutor
        from bots.treasury.trading.types import Position, TradeDirection, TradeStatus

        pos = Position(
            id="test_ladder_exit",
            token_mint="TestMint123",
            token_symbol="TEST",
            direction=TradeDirection.LONG,
            entry_price=1.0,
            current_price=2.0,
            amount=100.0,
            amount_usd=100.0,
            take_profit_price=15.0,
            stop_loss_price=0.8,
            status=TradeStatus.OPEN,
            opened_at=datetime.now(timezone.utc).isoformat(),
            ladder_exits=[
                {"pnl_multiple": 2.0, "percent": 50, "executed": False},
            ],
        )

        executor = PositionExitExecutor(swap_service=mock_swap_service)

        result = await executor.execute_exit(
            position=pos,
            trigger="ladder",
            exit_percent=50,  # 50% ladder exit
            ladder_tier=0,
        )

        assert result["success"] is True
        assert result["exit_type"] == "ladder"
        assert result["amount_sold"] == 50.0  # 50% of 100
        assert result["ladder_tier"] == 0


# =============================================================================
# Test: Default Ladder Exit Templates
# =============================================================================

class TestLadderExitTemplates:
    """Test predefined ladder exit templates."""

    def test_default_ladder_template(self):
        """Should have a default ladder exit template."""
        from core.risk.tp_sl_monitor import DEFAULT_LADDER_EXITS

        assert len(DEFAULT_LADDER_EXITS) == 3
        assert DEFAULT_LADDER_EXITS[0]["pnl_multiple"] == 2.0
        assert DEFAULT_LADDER_EXITS[0]["percent"] == 50
        assert DEFAULT_LADDER_EXITS[1]["pnl_multiple"] == 5.0
        assert DEFAULT_LADDER_EXITS[1]["percent"] == 30
        assert DEFAULT_LADDER_EXITS[2]["pnl_multiple"] == 10.0
        assert DEFAULT_LADDER_EXITS[2]["percent"] == 20

    def test_create_ladder_exits_from_template(self):
        """Should create ladder exits from template."""
        from core.risk.tp_sl_monitor import create_ladder_exits

        ladder = create_ladder_exits()

        assert len(ladder) == 3
        for exit_tier in ladder:
            assert "pnl_multiple" in exit_tier
            assert "percent" in exit_tier
            assert "executed" in exit_tier
            assert exit_tier["executed"] is False

    def test_create_custom_ladder_exits(self):
        """Should create custom ladder exits."""
        from core.risk.tp_sl_monitor import create_ladder_exits

        custom = [
            {"pnl_multiple": 1.5, "percent": 25},
            {"pnl_multiple": 3.0, "percent": 50},
            {"pnl_multiple": 7.0, "percent": 25},
        ]

        ladder = create_ladder_exits(custom)

        assert len(ladder) == 3
        assert ladder[0]["pnl_multiple"] == 1.5
        assert ladder[0]["percent"] == 25
        assert ladder[0]["executed"] is False


# =============================================================================
# Test: Monitoring Loop Integration
# =============================================================================

class TestMonitoringLoop:
    """Test full monitoring loop behavior."""

    @pytest.mark.asyncio
    async def test_monitor_checks_all_positions(self):
        """Monitor should check all open positions each cycle."""
        from core.risk.tp_sl_monitor import TPSLMonitor
        from bots.treasury.trading.types import Position, TradeDirection, TradeStatus

        positions = [
            Position(
                id="pos_1",
                token_mint="Mint1",
                token_symbol="A",
                direction=TradeDirection.LONG,
                entry_price=1.0,
                current_price=1.0,
                amount=100.0,
                amount_usd=100.0,
                take_profit_price=1.5,
                stop_loss_price=0.8,
                status=TradeStatus.OPEN,
                opened_at=datetime.now(timezone.utc).isoformat(),
            ),
            Position(
                id="pos_2",
                token_mint="Mint2",
                token_symbol="B",
                direction=TradeDirection.LONG,
                entry_price=2.0,
                current_price=2.0,
                amount=50.0,
                amount_usd=100.0,
                take_profit_price=3.0,
                stop_loss_price=1.6,
                status=TradeStatus.OPEN,
                opened_at=datetime.now(timezone.utc).isoformat(),
            ),
        ]

        mock_pm = MagicMock()
        mock_pm.get_open_positions = MagicMock(return_value=positions)

        mock_price_service = AsyncMock()
        mock_price_service.get_token_price = AsyncMock(side_effect=[1.2, 2.5])

        monitor = TPSLMonitor(
            position_manager=mock_pm,
            price_service=mock_price_service,
        )

        results = await monitor.check_all_positions()

        assert len(results) == 2
        assert mock_price_service.get_token_price.call_count == 2

    @pytest.mark.asyncio
    async def test_monitor_executes_exit_on_trigger(self):
        """Monitor should execute exit when trigger condition met."""
        from core.risk.tp_sl_monitor import TPSLMonitor
        from bots.treasury.trading.types import Position, TradeDirection, TradeStatus

        # Position that should trigger TP
        pos = Position(
            id="pos_tp",
            token_mint="Mint1",
            token_symbol="TEST",
            direction=TradeDirection.LONG,
            entry_price=1.0,
            current_price=1.0,
            amount=100.0,
            amount_usd=100.0,
            take_profit_price=1.5,
            stop_loss_price=0.8,
            status=TradeStatus.OPEN,
            opened_at=datetime.now(timezone.utc).isoformat(),
        )

        mock_pm = MagicMock()
        mock_pm.get_open_positions = MagicMock(return_value=[pos])
        mock_pm.close_position = MagicMock()

        mock_price_service = AsyncMock()
        mock_price_service.get_token_price = AsyncMock(return_value=1.6)  # Above TP

        mock_executor = AsyncMock()
        mock_executor.execute_exit = AsyncMock(return_value={"success": True})

        monitor = TPSLMonitor(
            position_manager=mock_pm,
            price_service=mock_price_service,
            exit_executor=mock_executor,
        )

        await monitor.check_all_positions()

        mock_executor.execute_exit.assert_called_once()


# =============================================================================
# Test: Notification on Exit
# =============================================================================

class TestExitNotifications:
    """Test notifications sent on position exits."""

    @pytest.mark.asyncio
    async def test_notification_on_tp_exit(self):
        """Should send notification when TP exit executes."""
        from core.risk.position_exit import PositionExitExecutor
        from bots.treasury.trading.types import Position, TradeDirection, TradeStatus

        pos = Position(
            id="test_notify",
            token_mint="TestMint",
            token_symbol="TEST",
            direction=TradeDirection.LONG,
            entry_price=1.0,
            current_price=1.5,
            amount=100.0,
            amount_usd=100.0,
            take_profit_price=1.4,
            stop_loss_price=0.8,
            status=TradeStatus.OPEN,
            opened_at=datetime.now(timezone.utc).isoformat(),
        )

        mock_swap = AsyncMock()
        mock_swap.execute_sell = AsyncMock(return_value={"success": True, "tx_hash": "tx123"})

        mock_notifier = AsyncMock()
        mock_notifier.send_exit_notification = AsyncMock()

        executor = PositionExitExecutor(
            swap_service=mock_swap,
            notifier=mock_notifier,
        )

        await executor.execute_exit(pos, trigger="tp", exit_percent=100)

        mock_notifier.send_exit_notification.assert_called_once()
        call_args = mock_notifier.send_exit_notification.call_args
        assert call_args[1]["trigger"] == "tp" or call_args[0][1] == "tp"


# =============================================================================
# Test: Exit Timing Requirement (< 15s)
# =============================================================================

class TestExitTiming:
    """Test that exits execute within 15 seconds of trigger."""

    @pytest.mark.asyncio
    async def test_exit_within_timeout(self):
        """Exit should complete within 15 seconds."""
        from core.risk.position_exit import PositionExitExecutor, EXIT_TIMEOUT_SECONDS
        from bots.treasury.trading.types import Position, TradeDirection, TradeStatus
        import time

        pos = Position(
            id="test_timing",
            token_mint="TestMint",
            token_symbol="TEST",
            direction=TradeDirection.LONG,
            entry_price=1.0,
            current_price=1.5,
            amount=100.0,
            amount_usd=100.0,
            take_profit_price=1.4,
            stop_loss_price=0.8,
            status=TradeStatus.OPEN,
            opened_at=datetime.now(timezone.utc).isoformat(),
        )

        mock_swap = AsyncMock()
        mock_swap.execute_sell = AsyncMock(return_value={"success": True, "tx_hash": "tx123"})

        executor = PositionExitExecutor(swap_service=mock_swap)

        start = time.time()
        await executor.execute_exit(pos, trigger="tp", exit_percent=100)
        elapsed = time.time() - start

        # Should complete well within 15s (allowing for test overhead)
        assert elapsed < 15.0
        assert EXIT_TIMEOUT_SECONDS == 15
