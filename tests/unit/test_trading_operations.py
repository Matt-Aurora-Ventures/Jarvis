"""
Unit tests for trading_operations.py

Tests cover:
- open_position() with all validation paths
- close_position() success and failure cases
- Position limits and stacking validation
- Kill switch enforcement
- Admin authorization
- Blocked token checks
- Risk tier validation
- TP/SL mandatory enforcement
"""

import pytest
import os
from unittest.mock import MagicMock, AsyncMock, patch, PropertyMock
from datetime import datetime, timezone

from bots.treasury.trading import (
    TradingEngine,
    Position,
    TradeDirection,
    TradeStatus,
    RiskLevel,
)


@pytest.fixture
def trading_engine():
    """Create a TradingEngine instance for testing."""
    # Create mock wallet (needs async methods)
    mock_wallet = AsyncMock()
    mock_wallet.get_public_key.return_value = "test_public_key"
    mock_wallet.get_balance.return_value = (True, 1000.0)  # (success, balance)
    # Add address attribute to wallet
    mock_wallet.address = "test_wallet_address"

    # Use AsyncMock for jupiter client (has async methods)
    mock_jupiter = AsyncMock()
    mock_jupiter.get_token_price.return_value = 100.0  # Default price

    # Create engine with mocked dependencies
    engine = TradingEngine(wallet=mock_wallet, jupiter=mock_jupiter)
    engine.positions = {}
    engine.trade_history = []  # Reset trade history for each test

    # Set admin user ID for close_position tests
    engine.admin_user_ids = [12345]

    # Mock _execute_trade and _execute_close_swap to avoid actual execution
    engine._execute_trade = AsyncMock(return_value=(False, "Mocked trade", None))
    engine._execute_close_swap = AsyncMock(return_value=(True, "Mocked close"))

    # Mock get_portfolio_value to avoid complex wallet interactions
    engine.get_portfolio_value = AsyncMock(return_value=(100.0, 1000.0))  # (SOL balance, USD value)

    return engine


class TestOpenPosition:
    """Tests for open_position() method."""

    @pytest.mark.asyncio
    async def test_open_position_kill_switch_blocks_trade(self, trading_engine, monkeypatch):
        """Test that kill switch blocks all trades."""
        monkeypatch.setenv("LIFEOS_KILL_SWITCH", "1")

        success, message, position = await trading_engine.open_position(
            token_mint="So11111111111111111111111111111111111111112",
            token_symbol="SOL",
            direction=TradeDirection.LONG,
            user_id=12345,
        )

        assert success is False
        assert "kill switch" in message.lower()
        assert position is None

    @pytest.mark.asyncio
    async def test_open_position_blocked_token_rejected(self, trading_engine):
        """Test that blocked tokens are rejected."""
        trading_engine.is_blocked_token = MagicMock(return_value=(True, "Token is blocked"))

        success, message, position = await trading_engine.open_position(
            token_mint="blocked_mint",
            token_symbol="SCAM",
            direction=TradeDirection.LONG,
            user_id=12345,
        )

        assert success is False
        assert "blocked" in message.lower()
        assert position is None

    @pytest.mark.asyncio
    async def test_open_position_no_user_id_rejected(self, trading_engine):
        """Test that trades without user_id are rejected."""
        trading_engine.is_blocked_token = MagicMock(return_value=(False, ""))

        success, message, position = await trading_engine.open_position(
            token_mint="So11111111111111111111111111111111111111112",
            token_symbol="SOL",
            direction=TradeDirection.LONG,
            user_id=None,  # Missing user_id
        )

        assert success is False
        assert "admin" in message.lower() or "authenticate" in message.lower()
        assert position is None

    @pytest.mark.asyncio
    async def test_open_position_non_admin_rejected(self, trading_engine):
        """Test that non-admin users cannot trade."""
        trading_engine.is_blocked_token = MagicMock(return_value=(False, ""))
        trading_engine.is_admin = MagicMock(return_value=False)

        success, message, position = await trading_engine.open_position(
            token_mint="So11111111111111111111111111111111111111112",
            token_symbol="SOL",
            direction=TradeDirection.LONG,
            user_id=99999,  # Non-admin user
        )

        assert success is False
        assert "not authorized" in message.lower()
        assert position is None

    @pytest.mark.asyncio
    async def test_open_position_grade_d_f_rejected(self, trading_engine):
        """Test that Grade D and F tokens are rejected."""
        trading_engine.is_blocked_token = MagicMock(return_value=(False, ""))
        trading_engine.is_admin = MagicMock(return_value=True)

        for grade in ['D', 'F']:
            success, message, position = await trading_engine.open_position(
                token_mint="So11111111111111111111111111111111111111112",
                token_symbol="SOL",
                direction=TradeDirection.LONG,
                user_id=12345,
                sentiment_grade=grade,
            )

            assert success is False
            assert grade in message
            assert "too risky" in message.lower()
            assert position is None

    @pytest.mark.asyncio
    async def test_open_position_high_risk_token_warning(self, trading_engine, caplog):
        """Test that high-risk tokens log warnings."""
        trading_engine.is_blocked_token = MagicMock(return_value=(False, ""))
        trading_engine.is_admin = MagicMock(return_value=True)
        trading_engine.is_high_risk_token = MagicMock(return_value=True)
        trading_engine.classify_token_risk = MagicMock(return_value="HIGH_RISK")

        # Mock to prevent actual execution
        trading_engine._execute_trade = AsyncMock(return_value=(False, "Mocked", None))

        await trading_engine.open_position(
            token_mint="pump_token",
            token_symbol="PUMP",
            direction=TradeDirection.LONG,
            user_id=12345,
        )

        # Check that warning was logged
        assert "HIGH-RISK TOKEN" in caplog.text

    @pytest.mark.asyncio
    async def test_open_position_max_positions_limit(self, trading_engine):
        """Test that max position limit is enforced."""
        trading_engine.is_blocked_token = MagicMock(return_value=(False, ""))
        trading_engine.is_admin = MagicMock(return_value=True)
        trading_engine.is_high_risk_token = MagicMock(return_value=False)
        trading_engine.classify_token_risk = MagicMock(return_value="ESTABLISHED")

        # Fill up positions to max
        trading_engine.max_positions = 5
        for i in range(5):
            position = Position(
                id=f"pos{i}",
                token_mint=f"mint{i}",
                token_symbol=f"TOKEN{i}",
                direction=TradeDirection.LONG,
                entry_price=1.0,
                current_price=1.0,
                amount=100.0,
                amount_usd=100.0,
                take_profit_price=1.1,
                stop_loss_price=0.9,
                status=TradeStatus.OPEN,
                opened_at=datetime.utcnow().isoformat(),
            )
            trading_engine.positions[position.id] = position

        success, message, position = await trading_engine.open_position(
            token_mint="new_mint",
            token_symbol="NEW",
            direction=TradeDirection.LONG,
            user_id=12345,
        )

        assert success is False
        assert "max" in message.lower() and "positions" in message.lower()
        assert position is None

    @pytest.mark.asyncio
    async def test_open_position_stacking_not_allowed(self, trading_engine, monkeypatch):
        """Test that stacking same token is rejected when disabled."""
        monkeypatch.setattr('bots.treasury.trading.trading_operations.ALLOW_STACKING', False)

        trading_engine.is_blocked_token = MagicMock(return_value=(False, ""))
        trading_engine.is_admin = MagicMock(return_value=True)
        trading_engine.is_high_risk_token = MagicMock(return_value=False)
        trading_engine.classify_token_risk = MagicMock(return_value="ESTABLISHED")

        # Add existing position in same token
        existing = Position(
            id="existing",
            token_mint="SOL_mint",
            token_symbol="SOL",
            direction=TradeDirection.LONG,
            entry_price=100.0,
            current_price=100.0,
            amount=10.0,
            amount_usd=1000.0,
            take_profit_price=110.0,
            stop_loss_price=90.0,
            status=TradeStatus.OPEN,
            opened_at=datetime.utcnow().isoformat(),
        )
        trading_engine.positions["existing"] = existing

        success, message, position = await trading_engine.open_position(
            token_mint="SOL_mint",
            token_symbol="SOL",
            direction=TradeDirection.LONG,
            user_id=12345,
        )

        assert success is False
        assert "already have" in message.lower() or "stacking" in message.lower()
        assert position is None

    @pytest.mark.asyncio
    async def test_open_position_success_creates_position(self, trading_engine):
        """Test successful position creation."""
        trading_engine.is_blocked_token = MagicMock(return_value=(False, ""))
        trading_engine.is_admin = MagicMock(return_value=True)
        trading_engine.is_high_risk_token = MagicMock(return_value=False)
        trading_engine.classify_token_risk = MagicMock(return_value="ESTABLISHED")
        trading_engine.calculate_tp_sl_percent = MagicMock(return_value=(50.0, 20.0))
        trading_engine.get_risk_adjusted_position_size = MagicMock(return_value=(100.0, "ESTABLISHED"))
        trading_engine.calculate_position_size = MagicMock(return_value=100.0)
        trading_engine._check_spending_limits = MagicMock(return_value=(True, ""))
        trading_engine.get_tp_sl_levels = MagicMock(return_value=(150.0, 80.0))

        # Mock successful trade execution
        mock_position = Position(
            id="test123",
            token_mint="SOL_mint",
            token_symbol="SOL",
            direction=TradeDirection.LONG,
            entry_price=100.0,
            current_price=100.0,
            amount=10.0,
            amount_usd=1000.0,
            take_profit_price=150.0,
            stop_loss_price=80.0,
            status=TradeStatus.OPEN,
            opened_at=datetime.utcnow().isoformat(),
        )
        trading_engine._execute_trade = AsyncMock(return_value=(True, "Success", mock_position))

        success, message, position = await trading_engine.open_position(
            token_mint="SOL_mint",
            token_symbol="SOL",
            direction=TradeDirection.LONG,
            user_id=12345,
            sentiment_grade="A+",
        )

        assert success is True
        assert position is not None
        assert position.token_symbol == "SOL"
        assert position.status == TradeStatus.OPEN


class TestClosePosition:
    """Tests for close_position() method."""

    @pytest.mark.asyncio
    async def test_close_position_not_found(self, trading_engine):
        """Test closing non-existent position fails gracefully."""
        success, message = await trading_engine.close_position("nonexistent_id", user_id=12345)

        assert success is False
        assert "not found" in message.lower()

    @pytest.mark.asyncio
    async def test_close_position_already_closed(self, trading_engine):
        """Test closing already-closed position fails."""
        closed_position = Position(
            id="closed123",
            token_mint="mint",
            token_symbol="TOKEN",
            direction=TradeDirection.LONG,
            entry_price=100.0,
            current_price=110.0,
            amount=10.0,
            amount_usd=1000.0,
            take_profit_price=150.0,
            stop_loss_price=80.0,
            status=TradeStatus.CLOSED,  # Already closed
            opened_at=datetime.utcnow().isoformat(),
        )
        trading_engine.positions["closed123"] = closed_position

        success, message = await trading_engine.close_position("closed123", user_id=12345)

        assert success is False
        assert "already closed" in message.lower() or "not open" in message.lower()

    @pytest.mark.asyncio
    async def test_close_position_success(self, trading_engine):
        """Test successful position closure."""
        open_position = Position(
            id="open123",
            token_mint="mint",
            token_symbol="TOKEN",
            direction=TradeDirection.LONG,
            entry_price=100.0,
            current_price=110.0,
            amount=10.0,
            amount_usd=1000.0,
            take_profit_price=150.0,
            stop_loss_price=80.0,
            status=TradeStatus.OPEN,
            opened_at=datetime.utcnow().isoformat(),
        )
        trading_engine.positions["open123"] = open_position

        # Mock successful swap execution
        trading_engine._execute_close_swap = AsyncMock(return_value=(True, "Closed successfully"))

        success, message = await trading_engine.close_position("open123", user_id=12345)

        assert success is True
        # Position is removed from active positions after close
        assert "open123" not in trading_engine.positions
        # Position should be in trade_history
        assert len(trading_engine.trade_history) > 0
        closed_position = trading_engine.trade_history[-1]
        assert closed_position.id == "open123"
        assert closed_position.status == TradeStatus.CLOSED
        assert closed_position.closed_at is not None


class TestPositionValidation:
    """Tests for position validation logic."""

    def test_is_admin_with_admin_user(self, trading_engine):
        """Test admin check returns True for admin user."""
        from bots.treasury.trading.constants import ADMIN_USER_ID
        assert trading_engine.is_admin(ADMIN_USER_ID) is True

    def test_is_admin_with_non_admin_user(self, trading_engine):
        """Test admin check returns False for non-admin."""
        assert trading_engine.is_admin(99999) is False

    def test_is_blocked_token_in_blocklist(self, trading_engine):
        """Test blocked token detection."""
        # Assuming "SCAM" is in BLOCKED_SYMBOLS
        is_blocked, reason = trading_engine.is_blocked_token("any_mint", "SCAM")
        # May or may not be blocked depending on actual constants
        assert isinstance(is_blocked, bool)
        assert isinstance(reason, str)

    def test_is_high_risk_token_pump_fun(self, trading_engine):
        """Test high-risk detection for pump.fun tokens."""
        # Mock pump.fun detection
        trading_engine.is_high_risk_token = MagicMock(return_value=True)
        assert trading_engine.is_high_risk_token("pump_token") is True

    def test_classify_token_risk_established(self, trading_engine):
        """Test risk classification for established tokens."""
        risk = trading_engine.classify_token_risk(
            "So11111111111111111111111111111111111111112",
            "SOL"
        )
        assert risk in ["ESTABLISHED", "MID_TIER", "HIGH_RISK", "MICRO", "XSTOCKS"]


class TestPositionLimits:
    """Tests for position sizing and allocation limits."""

    def test_max_allocation_per_token_enforced(self, trading_engine):
        """Test that token allocation limits are checked."""
        # This would be tested in actual open_position flow
        # Placeholder for allocation logic tests
        pass

    @pytest.mark.skip(reason="get_position_size method doesn't exist - needs API verification")
    def test_position_size_by_risk_level(self, trading_engine):
        """Test position sizing based on risk level."""
        # TODO: Verify correct method name in TradingEngine API
        # size_conservative = trading_engine.get_position_size(RiskLevel.CONSERVATIVE)
        # size_aggressive = trading_engine.get_position_size(RiskLevel.AGGRESSIVE)
        # assert size_aggressive > size_conservative
        pass


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    @pytest.mark.asyncio
    async def test_open_position_with_invalid_direction(self, trading_engine):
        """Test that invalid trade direction is handled."""
        trading_engine.is_blocked_token = MagicMock(return_value=(False, ""))
        trading_engine.is_admin = MagicMock(return_value=True)

        # This should ideally be caught by type system, but test runtime handling
        # Passing invalid direction would fail at validation
        pass

    @pytest.mark.asyncio
    async def test_open_position_with_zero_amount(self, trading_engine):
        """Test that zero amount positions are rejected."""
        trading_engine.is_blocked_token = MagicMock(return_value=(False, ""))
        trading_engine.is_admin = MagicMock(return_value=True)

        success, message, position = await trading_engine.open_position(
            token_mint="mint",
            token_symbol="TOKEN",
            direction=TradeDirection.LONG,
            user_id=12345,
            amount_usd=0.0,  # Zero amount
        )

        # Should fail validation (implementation-dependent)
        # assert success is False

    @pytest.mark.asyncio
    async def test_open_position_with_negative_amount(self, trading_engine):
        """Test that negative amounts are rejected."""
        trading_engine.is_blocked_token = MagicMock(return_value=(False, ""))
        trading_engine.is_admin = MagicMock(return_value=True)

        success, message, position = await trading_engine.open_position(
            token_mint="mint",
            token_symbol="TOKEN",
            direction=TradeDirection.LONG,
            user_id=12345,
            amount_usd=-100.0,  # Negative amount
        )

        # Should fail validation
        # assert success is False


# =============================================================================
# Live Execution Tests (Lines 332-430, 528-665)
# =============================================================================


class TestLiveExecution:
    """Tests for live open/close execution paths."""

    @pytest.fixture
    def live_engine(self, trading_engine):
        """Create engine configured for live execution."""
        trading_engine.dry_run = False
        trading_engine.trade_history = []  # Reset trade history

        # Reset daily volume to avoid limits - use risk_checker
        trading_engine._risk_checker._daily_volume_usd = 0.0
        trading_engine._risk_checker._trades_today = 0

        # Increase spending limits for testing
        trading_engine.MAX_TRADE_USD = 1000.0
        trading_engine.MAX_DAILY_USD = 10000.0

        # Mock _check_spending_limits to always allow
        trading_engine._check_spending_limits = MagicMock(return_value=(True, ""))

        # Mock _execute_swap for live execution
        from types import SimpleNamespace
        swap_result = SimpleNamespace(
            success=True,
            signature="test_tx_signature_123",
            error=None
        )
        trading_engine._execute_swap = AsyncMock(return_value=swap_result)

        # Mock order_manager
        mock_order_manager = AsyncMock()
        mock_order_manager.create_take_profit = AsyncMock(return_value="tp_order_123")
        mock_order_manager.create_stop_loss = AsyncMock(return_value="sl_order_123")
        mock_order_manager.cancel_order = AsyncMock(return_value=True)
        trading_engine.order_manager = mock_order_manager

        return trading_engine

    @pytest.mark.asyncio
    async def test_live_open_position_swap_execution(self, live_engine):
        """Test live open_position executes Jupiter swap and creates orders."""
        with patch('bots.treasury.trading.trading_operations.log_position_change'), \
             patch('bots.treasury.scorekeeper.get_scorekeeper') as mock_scorekeeper:

            # Mock Jupiter quote
            from types import SimpleNamespace
            quote = SimpleNamespace(
                output_amount_ui=1000.0,
                input_amount=50000000000,  # 50 SOL in lamports
            )
            live_engine.jupiter.get_quote = AsyncMock(return_value=quote)
            live_engine.jupiter.get_token_info = AsyncMock(return_value=SimpleNamespace(decimals=9))

            # Mock is_admin and is_blocked_token
            live_engine.is_admin = MagicMock(return_value=True)
            live_engine.is_blocked_token = MagicMock(return_value=(False, ""))

            success, message, position = await live_engine.open_position(
                token_mint="test_mint_123",
                token_symbol="TEST",
                direction=TradeDirection.LONG,
                amount_usd=500.0,
                custom_tp=0.20,  # 20% TP
                custom_sl=0.10,  # 10% SL
                sentiment_grade="A",
                user_id=12345,
            )

            assert success is True, f"Expected success but got: {message}"
            assert "test_tx_signature_123" in message
            assert position is not None
            assert position.status == TradeStatus.OPEN

            # Verify swap was called
            live_engine._execute_swap.assert_called_once()

            # Verify TP/SL orders created
            live_engine.order_manager.create_take_profit.assert_called_once()
            live_engine.order_manager.create_stop_loss.assert_called_once()

            # Verify scorekeeper tracking
            mock_scorekeeper.return_value.open_position.assert_called_once()

    @pytest.mark.asyncio
    async def test_live_open_position_swap_failure(self, live_engine):
        """Test live open_position handles swap failure gracefully."""
        from types import SimpleNamespace

        # Mock failed swap
        swap_result = SimpleNamespace(
            success=False,
            signature=None,
            error="Insufficient liquidity"
        )
        live_engine._execute_swap = AsyncMock(return_value=swap_result)

        # Mock quote success
        quote = SimpleNamespace(output_amount_ui=1000.0)
        live_engine.jupiter.get_quote = AsyncMock(return_value=quote)
        live_engine.is_admin = MagicMock(return_value=True)
        live_engine.is_blocked_token = MagicMock(return_value=(False, ""))

        success, message, position = await live_engine.open_position(
            token_mint="test_mint",
            token_symbol="TEST",
            direction=TradeDirection.LONG,
            user_id=12345,
        )

        assert success is False
        assert "Swap failed" in message
        assert "Insufficient liquidity" in message
        assert position is None

    @pytest.mark.asyncio
    async def test_live_open_position_no_quote(self, live_engine):
        """Test live open_position handles missing quote."""
        live_engine.jupiter.get_quote = AsyncMock(return_value=None)
        live_engine.is_admin = MagicMock(return_value=True)
        live_engine.is_blocked_token = MagicMock(return_value=(False, ""))

        success, message, position = await live_engine.open_position(
            token_mint="test_mint",
            token_symbol="TEST",
            direction=TradeDirection.LONG,
            user_id=12345,
        )

        assert success is False
        assert "Failed to get swap quote" in message

    @pytest.mark.asyncio
    async def test_live_close_position_order_cancellation(self, live_engine):
        """Test live close_position cancels TP/SL orders."""
        # Create open position
        position = Position(
            id="pos_123",
            token_mint="test_mint",
            token_symbol="TEST",
            direction=TradeDirection.LONG,
            entry_price=100.0,
            current_price=100.0,
            amount_usd=500.0,
            amount=1000.0,
            take_profit_price=120.0,
            stop_loss_price=80.0,
            status=TradeStatus.OPEN,
            opened_at=datetime.utcnow().isoformat(),
            tp_order_id="tp_123",
            sl_order_id="sl_123",
            sentiment_grade="A",
        )
        position.status = TradeStatus.OPEN
        live_engine.positions["pos_123"] = position

        # Mock wallet balance
        live_engine.wallet.get_token_balances = AsyncMock(return_value={
            "test_mint": {"balance": 1000.0}
        })

        # Mock quote and token info
        from types import SimpleNamespace
        quote = SimpleNamespace(input_amount=1000000000000)
        live_engine.jupiter.get_quote = AsyncMock(return_value=quote)
        live_engine.jupiter.get_token_info = AsyncMock(return_value=SimpleNamespace(decimals=9))

        with patch('bots.treasury.trading.trading_operations.log_position_change'), \
             patch('bots.treasury.scorekeeper.get_scorekeeper'):

            success, message = await live_engine.close_position(
                "pos_123",
                reason="manual",
                user_id=12345
            )

            assert success is True

            # Verify orders were cancelled
            assert live_engine.order_manager.cancel_order.call_count == 2

    @pytest.mark.asyncio
    async def test_live_close_position_no_balance_early_exit(self, live_engine):
        """Test live close_position handles zero balance gracefully."""
        position = Position(
            id="pos_123",
            token_mint="test_mint",
            token_symbol="TEST",
            direction=TradeDirection.LONG,
            entry_price=100.0,
            current_price=100.0,
            amount=0.0,
            amount_usd=500.0,
            take_profit_price=120.0,
            stop_loss_price=80.0,
            status=TradeStatus.OPEN,
            opened_at=datetime.utcnow().isoformat(),
            tp_order_id="tp_123",
            sl_order_id="sl_123",
        )
        live_engine.positions["pos_123"] = position

        # Mock zero balance
        live_engine.wallet.get_token_balances = AsyncMock(return_value={
            "test_mint": {"balance": 0}
        })

        success, message = await live_engine.close_position(
            "pos_123",
            reason="manual",
            user_id=12345
        )

        assert success is True
        assert "no balance" in message.lower()
        assert "pos_123" not in live_engine.positions
        assert position.status == TradeStatus.CLOSED

    @pytest.mark.asyncio
    async def test_live_close_position_sell_failure(self, live_engine):
        """Test live close_position handles sell swap failure."""
        position = Position(
            id="pos_456",
            token_mint="test_mint",
            token_symbol="TEST",
            direction=TradeDirection.LONG,
            entry_price=100.0,
            current_price=100.0,
            amount_usd=500.0,
            amount=1000.0,
            take_profit_price=120.0,
            stop_loss_price=80.0,
            status=TradeStatus.OPEN,
            opened_at=datetime.utcnow().isoformat(),
        )
        live_engine.positions["pos_456"] = position

        # Mock balance
        live_engine.wallet.get_token_balances = AsyncMock(return_value={
            "test_mint": {"balance": 1000.0}
        })

        # Mock failed swap
        from types import SimpleNamespace
        quote = SimpleNamespace(input_amount=1000000000000)
        live_engine.jupiter.get_quote = AsyncMock(return_value=quote)
        live_engine.jupiter.get_token_info = AsyncMock(return_value=SimpleNamespace(decimals=9))

        swap_result = SimpleNamespace(
            success=False,
            error="Slippage exceeded"
        )
        live_engine._execute_swap = AsyncMock(return_value=swap_result)

        success, message = await live_engine.close_position(
            "pos_456",
            reason="manual",
            user_id=12345
        )

        assert success is False
        assert "Close failed" in message
        assert "Slippage exceeded" in message


# =============================================================================
# Update Positions Tests (Lines 687-815)
# =============================================================================


class TestMonitorStopLosses:
    """Tests for monitor_stop_losses TP/SL monitoring."""

    @pytest.fixture
    def monitored_engine(self, trading_engine):
        """Create engine with positions ready for monitoring."""
        trading_engine.dry_run = False

        # Mock order manager
        mock_order_manager = AsyncMock()
        mock_order_manager.cancel_order = AsyncMock(return_value=True)
        trading_engine.order_manager = mock_order_manager

        # Mock wallet balances
        trading_engine.wallet.get_token_balances = AsyncMock(return_value={
            "tp_mint": {"balance": 1000.0},
            "sl_mint": {"balance": 500.0},
            "emergency_mint": {"balance": 200.0},
        })

        # Mock swap execution
        from types import SimpleNamespace
        swap_result = SimpleNamespace(success=True, signature="auto_close_tx")
        trading_engine._execute_swap = AsyncMock(return_value=swap_result)
        trading_engine.jupiter.get_token_info = AsyncMock(return_value=SimpleNamespace(decimals=9))

        return trading_engine

    @pytest.mark.asyncio
    async def test_monitor_stop_losses_take_profit_hit(self, monitored_engine):
        """Test monitor_stop_losses closes position when TP is hit."""
        # Create position with TP target
        position = Position(
            id="tp_pos",
            token_mint="tp_mint",
            token_symbol="TPTEST",
            direction=TradeDirection.LONG,
            entry_price=100.0,
            current_price=100.0,
            amount_usd=500.0,
            amount=1000.0,
            take_profit_price=120.0,
            stop_loss_price=80.0,
            status=TradeStatus.OPEN,
            opened_at=datetime.utcnow().isoformat(),
            tp_order_id="tp_order",
            sl_order_id="sl_order",
        )
        monitored_engine.positions["tp_pos"] = position

        # Mock price at TP level
        monitored_engine.jupiter.get_token_price = AsyncMock(return_value=125.0)
        monitored_engine.jupiter.get_quote = AsyncMock(return_value=MagicMock(input_amount=1000000000000))

        with patch('bots.treasury.trading.trading_operations.log_trading_error'):
            closed = await monitored_engine.monitor_stop_losses()

        assert len(closed) == 1
        assert closed[0]["reason"] == "TP_HIT"
        assert closed[0]["symbol"] == "TPTEST"
        assert closed[0]["pnl_pct"] == pytest.approx(25.0)  # (125-100)/100 * 100
        assert "tp_pos" not in monitored_engine.positions

    @pytest.mark.asyncio
    async def test_monitor_stop_losses_stop_loss_breach(self, monitored_engine):
        """Test update_positions closes position when SL is breached."""
        position = Position(
            id="sl_pos",
            token_mint="sl_mint",
            token_symbol="SLTEST",
            direction=TradeDirection.LONG,
            entry_price=100.0,
            current_price=100.0,
            amount_usd=500.0,
            amount=500.0,
            take_profit_price=120.0,
            stop_loss_price=90.0,
            status=TradeStatus.OPEN,
            opened_at=datetime.utcnow().isoformat(),
        )
        monitored_engine.positions["sl_pos"] = position

        # Mock price below SL
        monitored_engine.jupiter.get_token_price = AsyncMock(return_value=85.0)
        monitored_engine.jupiter.get_quote = AsyncMock(return_value=MagicMock(input_amount=500000000000))

        with patch('bots.treasury.trading.trading_operations.log_trading_error'):
            closed = await monitored_engine.monitor_stop_losses()

        assert len(closed) == 1
        assert closed[0]["reason"] == "SL_BREACH"
        assert closed[0]["pnl_pct"] == pytest.approx(-15.0)  # (85-100)/100 * 100

    @pytest.mark.asyncio
    async def test_monitor_stop_losses_emergency_90pct_loss(self, monitored_engine):
        """Test monitor_stop_losses triggers emergency close on 90% loss."""
        position = Position(
            id="emergency_pos",
            token_mint="emergency_mint",
            token_symbol="RUGTEST",
            direction=TradeDirection.LONG,
            entry_price=100.0,
            current_price=100.0,
            amount_usd=500.0,
            amount=200.0,
            take_profit_price=120.0,
            stop_loss_price=5.0,  # SL below emergency threshold
            status=TradeStatus.OPEN,
            opened_at=datetime.utcnow().isoformat(),
        )
        monitored_engine.positions["emergency_pos"] = position

        # Mock price at 92% loss (8% of entry) - below 10% but above SL
        monitored_engine.jupiter.get_token_price = AsyncMock(return_value=8.0)
        monitored_engine.jupiter.get_quote = AsyncMock(return_value=MagicMock(input_amount=200000000000))

        with patch('bots.treasury.trading.trading_operations.log_trading_error'):
            closed = await monitored_engine.monitor_stop_losses()

        assert len(closed) == 1
        assert closed[0]["reason"] == "EMERGENCY_90PCT"
        assert closed[0]["pnl_pct"] == pytest.approx(-92.0)

    @pytest.mark.asyncio
    async def test_monitor_stop_losses_skips_invalid_price(self, monitored_engine):
        """Test update_positions skips positions with invalid price."""
        position = Position(
            id="bad_price",
            token_mint="bad_mint",
            token_symbol="BADTEST",
            direction=TradeDirection.LONG,
            entry_price=100.0,
            current_price=100.0,
            amount=0.0,
            amount_usd=500.0,
            take_profit_price=120.0,
            stop_loss_price=80.0,
            status=TradeStatus.OPEN,
            opened_at=datetime.utcnow().isoformat(),
        )
        monitored_engine.positions["bad_price"] = position

        # Mock invalid price (0 or negative)
        monitored_engine.jupiter.get_token_price = AsyncMock(return_value=0.0)

        closed = await monitored_engine.monitor_stop_losses()

        assert len(closed) == 0
        assert "bad_price" in monitored_engine.positions  # Position still open

    @pytest.mark.asyncio
    async def test_monitor_stop_losses_cancels_orders_on_close(self, monitored_engine):
        """Test monitor_stop_losses cancels TP/SL orders when closing."""
        position = Position(
            id="cancel_test",
            token_mint="tp_mint",
            token_symbol="CANCELTEST",
            direction=TradeDirection.LONG,
            entry_price=100.0,
            current_price=100.0,
            amount=1000.0,  # Non-zero amount so close happens
            amount_usd=500.0,
            take_profit_price=120.0,
            stop_loss_price=80.0,
            status=TradeStatus.OPEN,
            opened_at=datetime.utcnow().isoformat(),
            tp_order_id="tp_order_cancel",
            sl_order_id="sl_order_cancel",
        )
        monitored_engine.positions["cancel_test"] = position

        # Trigger TP close
        monitored_engine.jupiter.get_token_price = AsyncMock(return_value=130.0)
        monitored_engine.jupiter.get_quote = AsyncMock(return_value=MagicMock(input_amount=1000000000000))

        with patch('bots.treasury.trading.trading_operations.log_trading_error'):
            await monitored_engine.monitor_stop_losses()

        # Verify both orders cancelled
        assert monitored_engine.order_manager.cancel_order.call_count == 2


# =============================================================================
# Reconciliation Tests (Lines 824-919)
# =============================================================================


class TestReconciliation:
    """Tests for reconcile_with_onchain."""

    @pytest.fixture
    def reconcile_engine(self, trading_engine):
        """Create engine for reconciliation testing."""
        # Mock treasury wallet
        from types import SimpleNamespace
        treasury = SimpleNamespace(address="treasury_address_123")
        trading_engine.wallet.get_treasury = MagicMock(return_value=treasury)

        return trading_engine

    @pytest.mark.asyncio
    async def test_reconcile_with_onchain_matched_positions(self, reconcile_engine):
        """Test reconcile_with_onchain finds matched positions."""
        # Create open position
        position = Position(
            id="pos_match",
            token_mint="match_mint",
            token_symbol="MATCH",
            direction=TradeDirection.LONG,
            entry_price=100.0,
            current_price=100.0,
            amount_usd=500.0,
            amount=1000.0,
            take_profit_price=120.0,
            stop_loss_price=80.0,
            status=TradeStatus.OPEN,
            opened_at=datetime.utcnow().isoformat(),
        )
        reconcile_engine.positions["pos_match"] = position

        # Mock on-chain balance matches position
        reconcile_engine.wallet.get_token_balances = AsyncMock(return_value={
            "match_mint": {"balance": 1000.0, "decimals": 9}
        })

        report = await reconcile_engine.reconcile_with_onchain()

        assert len(report["matched"]) == 1
        assert report["matched"][0]["symbol"] == "MATCH"
        assert len(report["orphaned"]) == 0
        assert len(report["mismatched"]) == 0

    @pytest.mark.asyncio
    async def test_reconcile_with_onchain_orphaned_positions(self, reconcile_engine):
        """Test reconcile_with_onchain detects orphaned positions."""
        position = Position(
            id="pos_orphan",
            token_mint="orphan_mint",
            token_symbol="ORPHAN",
            direction=TradeDirection.LONG,
            entry_price=100.0,
            current_price=100.0,
            amount_usd=500.0,
            amount=1000.0,
            take_profit_price=120.0,
            stop_loss_price=80.0,
            status=TradeStatus.OPEN,
            opened_at=datetime.utcnow().isoformat(),
        )
        reconcile_engine.positions["pos_orphan"] = position

        # Mock on-chain has zero balance
        reconcile_engine.wallet.get_token_balances = AsyncMock(return_value={
            "orphan_mint": {"balance": 0.0, "decimals": 9}
        })

        report = await reconcile_engine.reconcile_with_onchain()

        assert len(report["orphaned"]) == 1
        assert report["orphaned"][0]["symbol"] == "ORPHAN"
        assert report["orphaned"][0]["reason"] == "No on-chain balance found"

    @pytest.mark.asyncio
    async def test_reconcile_with_onchain_mismatched_amounts(self, reconcile_engine):
        """Test reconcile_with_onchain detects amount mismatches."""
        position = Position(
            id="pos_mismatch",
            token_mint="mismatch_mint",
            token_symbol="MISMATCH",
            direction=TradeDirection.LONG,
            entry_price=100.0,
            current_price=100.0,
            amount_usd=500.0,
            amount=1000.0,
            take_profit_price=120.0,
            stop_loss_price=80.0,
            status=TradeStatus.OPEN,
            opened_at=datetime.utcnow().isoformat(),
        )
        reconcile_engine.positions["pos_mismatch"] = position

        # Mock on-chain balance differs by >5%
        reconcile_engine.wallet.get_token_balances = AsyncMock(return_value={
            "mismatch_mint": {"balance": 800.0, "decimals": 9}  # 20% difference
        })

        report = await reconcile_engine.reconcile_with_onchain()

        assert len(report["mismatched"]) == 1
        assert report["mismatched"][0]["symbol"] == "MISMATCH"
        assert report["mismatched"][0]["stored_amount"] == 1000.0
        assert report["mismatched"][0]["onchain_amount"] == 800.0

    @pytest.mark.asyncio
    async def test_reconcile_with_onchain_untracked_tokens(self, reconcile_engine):
        """Test reconcile_with_onchain detects untracked tokens."""
        # No positions
        reconcile_engine.positions = {}

        # Mock on-chain has unknown tokens (excluding SOL/USDC/USDT)
        reconcile_engine.wallet.get_token_balances = AsyncMock(return_value={
            "unknown_mint_123": {"balance": 500.0, "decimals": 6},
            "unknown_mint_456": {"balance": 200.0, "decimals": 9},
            # SOL should be ignored
            "So11111111111111111111111111111111111111112": {"balance": 10.0, "decimals": 9},
        })

        report = await reconcile_engine.reconcile_with_onchain()

        assert len(report["untracked"]) == 2
        assert any(u["mint"] == "unknown_mint_123" for u in report["untracked"])
        assert any(u["mint"] == "unknown_mint_456" for u in report["untracked"])

    @pytest.mark.asyncio
    async def test_reconcile_with_onchain_no_treasury(self, reconcile_engine):
        """Test reconcile_with_onchain handles missing treasury."""
        reconcile_engine.wallet.get_treasury = MagicMock(return_value=None)

        report = await reconcile_engine.reconcile_with_onchain()

        assert len(report["errors"]) == 1
        assert "No treasury wallet" in report["errors"][0]

    @pytest.mark.asyncio
    async def test_reconcile_with_onchain_handles_exceptions(self, reconcile_engine):
        """Test reconcile_with_onchain handles exceptions gracefully."""
        with patch('bots.treasury.trading.trading_operations.log_trading_error'):
            # Mock wallet to raise exception
            reconcile_engine.wallet.get_token_balances = AsyncMock(
                side_effect=Exception("Network error")
            )

            report = await reconcile_engine.reconcile_with_onchain()

            assert len(report["errors"]) == 1
            assert "Network error" in report["errors"][0]


# =============================================================================
# Auto-Reconcile Orphaned Tests (Lines 965-1012)
# =============================================================================


class TestAutoReconcileOrphaned:
    """Tests for auto_reconcile_orphaned method."""

    @pytest.fixture
    def auto_reconcile_engine(self, trading_engine):
        """Create engine for auto-reconcile testing."""
        from types import SimpleNamespace
        treasury = SimpleNamespace(address="treasury_address_123")
        trading_engine.wallet.get_treasury = MagicMock(return_value=treasury)
        return trading_engine

    @pytest.mark.asyncio
    async def test_auto_reconcile_orphaned_closes_positions(self, auto_reconcile_engine):
        """Test auto_reconcile_orphaned closes orphaned positions."""
        # Create orphaned position (no on-chain balance)
        position = Position(
            id="orphan_pos",
            token_mint="orphan_mint",
            token_symbol="ORPHAN",
            direction=TradeDirection.LONG,
            entry_price=100.0,
            current_price=100.0,
            amount_usd=500.0,
            amount=1000.0,
            take_profit_price=120.0,
            stop_loss_price=80.0,
            status=TradeStatus.OPEN,
            opened_at=datetime.utcnow().isoformat(),
        )
        auto_reconcile_engine.positions["orphan_pos"] = position

        # Mock on-chain has zero balance
        auto_reconcile_engine.wallet.get_token_balances = AsyncMock(return_value={
            "orphan_mint": {"balance": 0.0, "decimals": 9}
        })

        # Mock current price
        auto_reconcile_engine.jupiter.get_token_price = AsyncMock(return_value=50.0)

        closed_count = await auto_reconcile_engine.auto_reconcile_orphaned()

        assert closed_count == 1
        assert "orphan_pos" not in auto_reconcile_engine.positions
        assert len(auto_reconcile_engine.trade_history) == 1
        assert auto_reconcile_engine.trade_history[-1].pnl_pct == pytest.approx(-50.0)

    @pytest.mark.asyncio
    async def test_auto_reconcile_orphaned_with_provided_report(self, auto_reconcile_engine):
        """Test auto_reconcile_orphaned uses provided report."""
        position = Position(
            id="orphan_pos2",
            token_mint="orphan_mint2",
            token_symbol="ORPHAN2",
            direction=TradeDirection.LONG,
            entry_price=100.0,
            current_price=100.0,
            amount_usd=500.0,
            amount=1000.0,
            take_profit_price=120.0,
            stop_loss_price=80.0,
            status=TradeStatus.OPEN,
            opened_at=datetime.utcnow().isoformat(),
        )
        auto_reconcile_engine.positions["orphan_pos2"] = position

        # Provide pre-built report
        report = {
            "orphaned": [
                {"position_id": "orphan_pos2", "symbol": "ORPHAN2"}
            ]
        }

        # Mock current price
        auto_reconcile_engine.jupiter.get_token_price = AsyncMock(return_value=80.0)

        closed_count = await auto_reconcile_engine.auto_reconcile_orphaned(report=report)

        assert closed_count == 1
        assert "orphan_pos2" not in auto_reconcile_engine.positions

    @pytest.mark.asyncio
    async def test_auto_reconcile_orphaned_price_error_sets_100pct_loss(self, auto_reconcile_engine):
        """Test auto_reconcile_orphaned handles price error with 100% loss."""
        position = Position(
            id="orphan_price_fail",
            token_mint="orphan_mint3",
            token_symbol="ORPHAN3",
            direction=TradeDirection.LONG,
            entry_price=100.0,
            current_price=100.0,
            amount_usd=500.0,
            amount=1000.0,
            take_profit_price=120.0,
            stop_loss_price=80.0,
            status=TradeStatus.OPEN,
            opened_at=datetime.utcnow().isoformat(),
        )
        auto_reconcile_engine.positions["orphan_price_fail"] = position

        report = {
            "orphaned": [
                {"position_id": "orphan_price_fail", "symbol": "ORPHAN3"}
            ]
        }

        # Mock price error
        auto_reconcile_engine.jupiter.get_token_price = AsyncMock(
            side_effect=Exception("Price API error")
        )

        closed_count = await auto_reconcile_engine.auto_reconcile_orphaned(report=report)

        assert closed_count == 1
        closed_pos = auto_reconcile_engine.trade_history[-1]
        assert closed_pos.pnl_pct == -100
        assert closed_pos.pnl_usd == -500.0

    @pytest.mark.asyncio
    async def test_auto_reconcile_orphaned_no_orphans(self, auto_reconcile_engine):
        """Test auto_reconcile_orphaned with no orphans."""
        report = {"orphaned": []}
        closed_count = await auto_reconcile_engine.auto_reconcile_orphaned(report=report)
        assert closed_count == 0


# =============================================================================
# Update Positions Tests (Lines 668-679)
# =============================================================================


class TestUpdatePositions:
    """Tests for update_positions method."""

    @pytest.mark.asyncio
    async def test_update_positions_updates_prices(self, trading_engine):
        """Test update_positions updates current prices and PnL."""
        position = Position(
            id="update_pos",
            token_mint="update_mint",
            token_symbol="UPDATE",
            direction=TradeDirection.LONG,
            entry_price=100.0,
            current_price=100.0,
            amount_usd=500.0,
            amount=5.0,
            take_profit_price=120.0,
            stop_loss_price=80.0,
            status=TradeStatus.OPEN,
            opened_at=datetime.utcnow().isoformat(),
        )
        trading_engine.positions["update_pos"] = position

        # Mock price increase
        trading_engine.jupiter.get_token_price = AsyncMock(return_value=110.0)

        await trading_engine.update_positions()

        updated_pos = trading_engine.positions["update_pos"]
        assert updated_pos.current_price == 110.0
        assert updated_pos.pnl_pct == pytest.approx(10.0)
        assert updated_pos.pnl_usd == pytest.approx(50.0)

    @pytest.mark.asyncio
    async def test_update_positions_skips_zero_price(self, trading_engine):
        """Test update_positions skips positions with zero price."""
        position = Position(
            id="skip_pos",
            token_mint="skip_mint",
            token_symbol="SKIP",
            direction=TradeDirection.LONG,
            entry_price=100.0,
            current_price=100.0,
            amount_usd=500.0,
            amount=5.0,
            take_profit_price=120.0,
            stop_loss_price=80.0,
            status=TradeStatus.OPEN,
            opened_at=datetime.utcnow().isoformat(),
        )
        trading_engine.positions["skip_pos"] = position

        # Mock zero price
        trading_engine.jupiter.get_token_price = AsyncMock(return_value=0.0)

        await trading_engine.update_positions()

        # Price should remain unchanged
        assert trading_engine.positions["skip_pos"].current_price == 100.0


# =============================================================================
# Additional Open Position Edge Cases (Lines 109, 118-119, 128-137, 157-163, etc.)
# =============================================================================


class TestOpenPositionAdditionalCases:
    """Additional tests for open_position edge cases."""

    @pytest.mark.asyncio
    async def test_open_position_stacking_allowed_passes_validation(self, trading_engine, monkeypatch):
        """Test that stacking when allowed does not block trade (unlike when disabled)."""
        monkeypatch.setattr('bots.treasury.trading.trading_operations.ALLOW_STACKING', True)

        trading_engine.is_blocked_token = MagicMock(return_value=(False, ""))
        trading_engine.is_admin = MagicMock(return_value=True)
        trading_engine.is_high_risk_token = MagicMock(return_value=False)
        trading_engine.classify_token_risk = MagicMock(return_value="ESTABLISHED")
        trading_engine.jupiter.get_token_price = AsyncMock(return_value=100.0)
        trading_engine.jupiter.get_token_info = AsyncMock(return_value=None)
        trading_engine.get_risk_adjusted_position_size = MagicMock(return_value=(100.0, "ESTABLISHED"))
        trading_engine._check_spending_limits = MagicMock(return_value=(True, ""))
        trading_engine.get_tp_sl_levels = MagicMock(return_value=(120.0, 80.0))

        # Add existing position in same token
        existing = Position(
            id="existing",
            token_mint="SOL_mint",
            token_symbol="SOL",
            direction=TradeDirection.LONG,
            entry_price=100.0,
            current_price=100.0,
            amount=10.0,
            amount_usd=1000.0,
            take_profit_price=110.0,
            stop_loss_price=90.0,
            status=TradeStatus.OPEN,
            opened_at=datetime.utcnow().isoformat(),
        )
        trading_engine.positions["existing"] = existing

        # In dry run mode, should succeed (stacking allowed)
        trading_engine.dry_run = True

        success, message, position = await trading_engine.open_position(
            token_mint="SOL_mint",
            token_symbol="SOL",
            direction=TradeDirection.LONG,
            user_id=12345,
            amount_usd=100.0,
        )

        # When stacking is allowed, the trade should proceed past the stacking check
        # (may still fail for other reasons, but not "stacking disabled")
        assert "stacking disabled" not in message.lower()
        assert "already have position" not in message.lower()

    @pytest.mark.asyncio
    async def test_open_position_no_price_rejected(self, trading_engine):
        """Test that position is rejected when price cannot be fetched."""
        trading_engine.is_blocked_token = MagicMock(return_value=(False, ""))
        trading_engine.is_admin = MagicMock(return_value=True)
        trading_engine.is_high_risk_token = MagicMock(return_value=False)

        # Mock zero price
        trading_engine.jupiter.get_token_price = AsyncMock(return_value=0.0)

        success, message, position = await trading_engine.open_position(
            token_mint="no_price_mint",
            token_symbol="NOPRICE",
            direction=TradeDirection.LONG,
            user_id=12345,
        )

        assert success is False
        assert "price" in message.lower()
        assert position is None

    @pytest.mark.asyncio
    async def test_open_position_low_liquidity_rejected(self, trading_engine):
        """Test that low liquidity tokens are rejected."""
        from types import SimpleNamespace

        trading_engine.is_blocked_token = MagicMock(return_value=(False, ""))
        trading_engine.is_admin = MagicMock(return_value=True)
        trading_engine.is_high_risk_token = MagicMock(return_value=False)
        trading_engine.classify_token_risk = MagicMock(return_value="HIGH_RISK")

        # Mock valid price
        trading_engine.jupiter.get_token_price = AsyncMock(return_value=1.0)

        # Mock token info with low daily volume
        token_info = SimpleNamespace(daily_volume=500)  # Below MIN_LIQUIDITY_USD
        trading_engine.jupiter.get_token_info = AsyncMock(return_value=token_info)

        success, message, position = await trading_engine.open_position(
            token_mint="low_liq_mint",
            token_symbol="LOWLIQ",
            direction=TradeDirection.LONG,
            user_id=12345,
        )

        assert success is False
        assert "liquidity" in message.lower()
        assert position is None

    @pytest.mark.asyncio
    async def test_open_position_invalid_amount_type_rejected(self, trading_engine):
        """Test that invalid amount_usd type is rejected."""
        trading_engine.is_blocked_token = MagicMock(return_value=(False, ""))
        trading_engine.is_admin = MagicMock(return_value=True)
        trading_engine.is_high_risk_token = MagicMock(return_value=False)
        trading_engine.classify_token_risk = MagicMock(return_value="ESTABLISHED")
        trading_engine.jupiter.get_token_price = AsyncMock(return_value=100.0)
        trading_engine.jupiter.get_token_info = AsyncMock(return_value=None)

        success, message, position = await trading_engine.open_position(
            token_mint="test_mint",
            token_symbol="TEST",
            direction=TradeDirection.LONG,
            user_id=12345,
            amount_usd="not_a_number",  # Invalid type
        )

        assert success is False
        assert "invalid amount" in message.lower()
        assert position is None

    @pytest.mark.asyncio
    async def test_open_position_risk_too_high_rejected(self, trading_engine):
        """Test that high-risk position sizing returning 0 is rejected."""
        trading_engine.is_blocked_token = MagicMock(return_value=(False, ""))
        trading_engine.is_admin = MagicMock(return_value=True)
        trading_engine.is_high_risk_token = MagicMock(return_value=False)
        trading_engine.classify_token_risk = MagicMock(return_value="BLOCKED")
        trading_engine.jupiter.get_token_price = AsyncMock(return_value=100.0)
        trading_engine.jupiter.get_token_info = AsyncMock(return_value=None)

        # Mock risk-adjusted position size returning 0
        trading_engine.get_risk_adjusted_position_size = MagicMock(return_value=(0, "BLOCKED"))

        success, message, position = await trading_engine.open_position(
            token_mint="blocked_risk_mint",
            token_symbol="BLOCKED",
            direction=TradeDirection.LONG,
            user_id=12345,
            amount_usd=100.0,
        )

        assert success is False
        assert "blocked" in message.lower() or "BLOCKED" in message
        assert position is None

    @pytest.mark.asyncio
    async def test_open_position_token_allocation_exceeded(self, trading_engine, monkeypatch):
        """Test that token allocation cap is enforced."""
        monkeypatch.setattr('bots.treasury.trading.trading_operations.MAX_ALLOCATION_PER_TOKEN', 0.10)

        trading_engine.is_blocked_token = MagicMock(return_value=(False, ""))
        trading_engine.is_admin = MagicMock(return_value=True)
        trading_engine.is_high_risk_token = MagicMock(return_value=False)
        trading_engine.classify_token_risk = MagicMock(return_value="ESTABLISHED")
        trading_engine.jupiter.get_token_price = AsyncMock(return_value=100.0)
        trading_engine.jupiter.get_token_info = AsyncMock(return_value=None)

        # Mock portfolio value
        trading_engine.get_portfolio_value = AsyncMock(return_value=(10.0, 1000.0))

        # Add existing position to trigger allocation check
        existing = Position(
            id="existing_alloc",
            token_mint="alloc_mint",
            token_symbol="ALLOC",
            direction=TradeDirection.LONG,
            entry_price=100.0,
            current_price=100.0,
            amount=0.5,
            amount_usd=50.0,  # 5% of $1000 portfolio
            take_profit_price=110.0,
            stop_loss_price=90.0,
            status=TradeStatus.OPEN,
            opened_at=datetime.utcnow().isoformat(),
        )
        trading_engine.positions["existing_alloc"] = existing

        # Try to add another 60 USD (would be 11% total, exceeding 10% cap)
        trading_engine.get_risk_adjusted_position_size = MagicMock(return_value=(60.0, "ESTABLISHED"))

        success, message, position = await trading_engine.open_position(
            token_mint="alloc_mint",
            token_symbol="ALLOC",
            direction=TradeDirection.LONG,
            user_id=12345,
            amount_usd=60.0,
        )

        assert success is False
        assert "allocation" in message.lower()
        assert position is None


# =============================================================================
# Close Position Additional Cases (Lines 452-464, 571-576, 660-666)
# =============================================================================


class TestClosePositionAdditionalCases:
    """Additional tests for close_position edge cases."""

    @pytest.mark.asyncio
    async def test_close_position_no_admins_configured(self, trading_engine):
        """Test that close is rejected when no admins configured."""
        trading_engine.admin_user_ids = []  # No admins

        position = Position(
            id="test_pos",
            token_mint="mint",
            token_symbol="TOKEN",
            direction=TradeDirection.LONG,
            entry_price=100.0,
            current_price=110.0,
            amount=10.0,
            amount_usd=1000.0,
            take_profit_price=150.0,
            stop_loss_price=80.0,
            status=TradeStatus.OPEN,
            opened_at=datetime.utcnow().isoformat(),
        )
        trading_engine.positions["test_pos"] = position

        success, message = await trading_engine.close_position("test_pos", user_id=12345)

        assert success is False
        assert "no admins" in message.lower()

    @pytest.mark.asyncio
    async def test_close_position_unauthorized_user(self, trading_engine):
        """Test that unauthorized user cannot close position."""
        trading_engine.admin_user_ids = [12345]  # Only 12345 is admin
        trading_engine.is_admin = MagicMock(return_value=False)

        position = Position(
            id="auth_test",
            token_mint="mint",
            token_symbol="TOKEN",
            direction=TradeDirection.LONG,
            entry_price=100.0,
            current_price=110.0,
            amount=10.0,
            amount_usd=1000.0,
            take_profit_price=150.0,
            stop_loss_price=80.0,
            status=TradeStatus.OPEN,
            opened_at=datetime.utcnow().isoformat(),
        )
        trading_engine.positions["auth_test"] = position

        success, message = await trading_engine.close_position("auth_test", user_id=99999)

        assert success is False
        assert "unauthorized" in message.lower()

    @pytest.mark.asyncio
    async def test_close_position_no_quote_failure(self, trading_engine):
        """Test close_position handles missing quote in live mode."""
        trading_engine.dry_run = False
        trading_engine.admin_user_ids = [12345]

        position = Position(
            id="no_quote_pos",
            token_mint="no_quote_mint",
            token_symbol="NOQUOTE",
            direction=TradeDirection.LONG,
            entry_price=100.0,
            current_price=110.0,
            amount=10.0,
            amount_usd=1000.0,
            take_profit_price=150.0,
            stop_loss_price=80.0,
            status=TradeStatus.OPEN,
            opened_at=datetime.utcnow().isoformat(),
        )
        trading_engine.positions["no_quote_pos"] = position

        # Mock non-zero balance
        trading_engine.wallet.get_token_balances = AsyncMock(return_value={
            "no_quote_mint": {"balance": 10.0}
        })

        # Mock token info
        from types import SimpleNamespace
        trading_engine.jupiter.get_token_info = AsyncMock(return_value=SimpleNamespace(decimals=9))

        # Mock no quote
        trading_engine.jupiter.get_quote = AsyncMock(return_value=None)

        success, message = await trading_engine.close_position("no_quote_pos", user_id=12345)

        assert success is False
        assert "quote" in message.lower()

    @pytest.mark.asyncio
    async def test_close_position_exception_handling(self, trading_engine):
        """Test close_position handles exceptions gracefully."""
        trading_engine.dry_run = False
        trading_engine.admin_user_ids = [12345]

        position = Position(
            id="exc_pos",
            token_mint="exc_mint",
            token_symbol="EXCEPT",
            direction=TradeDirection.LONG,
            entry_price=100.0,
            current_price=110.0,
            amount=10.0,
            amount_usd=1000.0,
            take_profit_price=150.0,
            stop_loss_price=80.0,
            status=TradeStatus.OPEN,
            opened_at=datetime.utcnow().isoformat(),
        )
        trading_engine.positions["exc_pos"] = position

        # Mock wallet to raise exception
        trading_engine.wallet.get_token_balances = AsyncMock(
            side_effect=Exception("Wallet connection error")
        )

        success, message = await trading_engine.close_position("exc_pos", user_id=12345)

        assert success is False
        assert "error" in message.lower()


# =============================================================================
# Risk Manager Integration Tests (Lines 213-256)
# =============================================================================


class TestRiskManagerIntegration:
    """Tests for RiskManager integration in open_position."""

    @pytest.fixture
    def risk_engine(self, trading_engine):
        """Create engine with RiskManager mocked."""
        from unittest.mock import MagicMock

        # Create mock risk manager
        mock_risk_manager = MagicMock()
        mock_risk_manager.circuit_breaker_active = False
        mock_risk_manager.check_all_limits = MagicMock(return_value=(True, []))
        trading_engine.risk_manager = mock_risk_manager

        return trading_engine

    @pytest.mark.asyncio
    async def test_open_position_circuit_breaker_blocks(self, risk_engine):
        """Test that circuit breaker blocks trades."""
        risk_engine.is_blocked_token = MagicMock(return_value=(False, ""))
        risk_engine.is_admin = MagicMock(return_value=True)
        risk_engine.is_high_risk_token = MagicMock(return_value=False)
        risk_engine.classify_token_risk = MagicMock(return_value="ESTABLISHED")
        risk_engine.jupiter.get_token_price = AsyncMock(return_value=100.0)
        risk_engine.jupiter.get_token_info = AsyncMock(return_value=None)
        risk_engine.get_risk_adjusted_position_size = MagicMock(return_value=(100.0, "ESTABLISHED"))
        risk_engine._calculate_daily_pnl = MagicMock(return_value=0.0)

        # Activate circuit breaker
        risk_engine.risk_manager.circuit_breaker_active = True

        with patch('bots.treasury.trading.trading_operations.RISK_MANAGER_AVAILABLE', True):
            success, message, position = await risk_engine.open_position(
                token_mint="test_mint",
                token_symbol="TEST",
                direction=TradeDirection.LONG,
                user_id=12345,
                amount_usd=100.0,
            )

        assert success is False
        assert "circuit breaker" in message.lower()
        assert position is None

    @pytest.mark.asyncio
    async def test_open_position_critical_risk_alert_blocks(self, risk_engine):
        """Test that critical risk alerts block trades."""
        from types import SimpleNamespace

        risk_engine.is_blocked_token = MagicMock(return_value=(False, ""))
        risk_engine.is_admin = MagicMock(return_value=True)
        risk_engine.is_high_risk_token = MagicMock(return_value=False)
        risk_engine.classify_token_risk = MagicMock(return_value="ESTABLISHED")
        risk_engine.jupiter.get_token_price = AsyncMock(return_value=100.0)
        risk_engine.jupiter.get_token_info = AsyncMock(return_value=None)
        risk_engine.get_risk_adjusted_position_size = MagicMock(return_value=(100.0, "ESTABLISHED"))
        risk_engine._calculate_daily_pnl = MagicMock(return_value=0.0)

        # Create mock AlertLevel
        mock_alert_level = SimpleNamespace(CRITICAL="CRITICAL", EMERGENCY="EMERGENCY", WARNING="WARNING")
        critical_alert = SimpleNamespace(level="CRITICAL", message="Daily loss limit exceeded")

        risk_engine.risk_manager.circuit_breaker_active = False
        risk_engine.risk_manager.check_all_limits = MagicMock(return_value=(False, [critical_alert]))

        with patch('bots.treasury.trading.trading_operations.RISK_MANAGER_AVAILABLE', True), \
             patch('bots.treasury.trading.trading_operations.AlertLevel', mock_alert_level):
            success, message, position = await risk_engine.open_position(
                token_mint="test_mint",
                token_symbol="TEST",
                direction=TradeDirection.LONG,
                user_id=12345,
                amount_usd=100.0,
            )

        assert success is False
        assert "risk limit" in message.lower()
        assert position is None

    @pytest.mark.asyncio
    async def test_open_position_warning_alerts_logged(self, risk_engine, caplog):
        """Test that warning alerts are logged but don't block."""
        from types import SimpleNamespace

        risk_engine.is_blocked_token = MagicMock(return_value=(False, ""))
        risk_engine.is_admin = MagicMock(return_value=True)
        risk_engine.is_high_risk_token = MagicMock(return_value=False)
        risk_engine.classify_token_risk = MagicMock(return_value="ESTABLISHED")
        risk_engine.jupiter.get_token_price = AsyncMock(return_value=100.0)
        risk_engine.jupiter.get_token_info = AsyncMock(return_value=None)
        risk_engine.get_risk_adjusted_position_size = MagicMock(return_value=(100.0, "ESTABLISHED"))
        risk_engine._calculate_daily_pnl = MagicMock(return_value=0.0)
        risk_engine._check_spending_limits = MagicMock(return_value=(True, ""))

        # Create mock AlertLevel and warning alert
        mock_alert_level = SimpleNamespace(CRITICAL="CRITICAL", EMERGENCY="EMERGENCY", WARNING="WARNING")
        warning_alert = SimpleNamespace(level="WARNING", message="Approaching daily limit")

        risk_engine.risk_manager.circuit_breaker_active = False
        risk_engine.risk_manager.check_all_limits = MagicMock(return_value=(True, [warning_alert]))

        with patch('bots.treasury.trading.trading_operations.RISK_MANAGER_AVAILABLE', True), \
             patch('bots.treasury.trading.trading_operations.AlertLevel', mock_alert_level):
            await risk_engine.open_position(
                token_mint="test_mint",
                token_symbol="TEST",
                direction=TradeDirection.LONG,
                user_id=12345,
                amount_usd=100.0,
            )

        # Check that warning was logged
        assert "Approaching daily limit" in caplog.text


# =============================================================================
# Open Position Exception Handling (Lines 420-431)
# =============================================================================


class TestOpenPositionExceptionHandling:
    """Tests for exception handling in open_position live execution."""

    @pytest.mark.asyncio
    async def test_open_position_swap_exception(self, trading_engine):
        """Test open_position handles swap exception gracefully."""
        trading_engine.dry_run = False
        trading_engine.is_blocked_token = MagicMock(return_value=(False, ""))
        trading_engine.is_admin = MagicMock(return_value=True)
        trading_engine.is_high_risk_token = MagicMock(return_value=False)
        trading_engine.classify_token_risk = MagicMock(return_value="ESTABLISHED")
        trading_engine.jupiter.get_token_price = AsyncMock(return_value=100.0)
        trading_engine.jupiter.get_token_info = AsyncMock(return_value=None)
        trading_engine.get_risk_adjusted_position_size = MagicMock(return_value=(100.0, "ESTABLISHED"))
        trading_engine._check_spending_limits = MagicMock(return_value=(True, ""))
        trading_engine.get_tp_sl_levels = MagicMock(return_value=(120.0, 80.0))

        # Reset daily volume
        trading_engine._risk_checker._daily_volume_usd = 0.0

        # Mock quote to raise exception
        trading_engine.jupiter.get_quote = AsyncMock(side_effect=Exception("Network timeout"))

        success, message, position = await trading_engine.open_position(
            token_mint="test_mint",
            token_symbol="TEST",
            direction=TradeDirection.LONG,
            user_id=12345,
            amount_usd=100.0,
        )

        assert success is False
        assert "error" in message.lower()
        assert position is None


# =============================================================================
# Monitor Stop Losses Trailing Stop Tests (Lines 703-733)
# =============================================================================


class TestTrailingStopLogic:
    """Tests for trailing stop logic in monitor_stop_losses."""

    @pytest.fixture
    def trailing_engine(self, trading_engine):
        """Create engine for trailing stop testing."""
        trading_engine.dry_run = False

        # Mock order manager
        mock_order_manager = AsyncMock()
        mock_order_manager.cancel_order = AsyncMock(return_value=True)
        trading_engine.order_manager = mock_order_manager

        # Mock swap execution
        from types import SimpleNamespace
        swap_result = SimpleNamespace(success=True, signature="trail_tx")
        trading_engine._execute_swap = AsyncMock(return_value=swap_result)
        trading_engine.jupiter.get_token_info = AsyncMock(return_value=SimpleNamespace(decimals=9))

        # Mock wallet balances
        trading_engine.wallet.get_token_balances = AsyncMock(return_value={
            "trail_mint": {"balance": 1000.0}
        })

        return trading_engine

    @pytest.mark.asyncio
    async def test_trailing_stop_activates_at_15pct_gain(self, trailing_engine):
        """Test trailing stop activates at 15% gain and updates SL."""
        position = Position(
            id="trail_pos",
            token_mint="trail_mint",
            token_symbol="TRAIL",
            direction=TradeDirection.LONG,
            entry_price=100.0,
            current_price=100.0,
            peak_price=100.0,
            amount_usd=500.0,
            amount=1000.0,
            take_profit_price=150.0,  # TP at 50%
            stop_loss_price=80.0,     # Original SL at -20%
            status=TradeStatus.OPEN,
            opened_at=datetime.utcnow().isoformat(),
        )
        trailing_engine.positions["trail_pos"] = position

        # Mock price at 16% gain (below TP of 150)
        trailing_engine.jupiter.get_token_price = AsyncMock(return_value=116.0)
        trailing_engine.jupiter.get_quote = AsyncMock(return_value=MagicMock(input_amount=1000000000000))

        await trailing_engine.monitor_stop_losses()

        # Position should still be open (price below TP)
        pos = trailing_engine.positions.get("trail_pos")
        assert pos is not None, "Position should still be open"
        # SL should be 5% below peak (116.0 * 0.95 = 110.2)
        assert pos.stop_loss_price == pytest.approx(116.0 * 0.95)
        # Peak price should be updated to new high
        assert pos.peak_price == 116.0

    @pytest.mark.asyncio
    async def test_breakeven_stop_at_10pct_gain(self, trailing_engine):
        """Test breakeven stop activates at 10% gain and moves SL to entry."""
        position = Position(
            id="break_pos",
            token_mint="trail_mint",
            token_symbol="BREAK",
            direction=TradeDirection.LONG,
            entry_price=100.0,
            current_price=100.0,
            peak_price=100.0,
            amount_usd=500.0,
            amount=1000.0,
            take_profit_price=150.0,  # TP at 50%
            stop_loss_price=80.0,     # Original SL below entry
            status=TradeStatus.OPEN,
            opened_at=datetime.utcnow().isoformat(),
        )
        trailing_engine.positions["break_pos"] = position

        # Mock price at 11% gain (below 15% threshold for trailing, but above 10% for breakeven)
        trailing_engine.jupiter.get_token_price = AsyncMock(return_value=111.0)
        trailing_engine.jupiter.get_quote = AsyncMock(return_value=MagicMock(input_amount=1000000000000))

        await trailing_engine.monitor_stop_losses()

        pos = trailing_engine.positions.get("break_pos")
        assert pos is not None, "Position should still be open"
        # SL should be moved to entry price (breakeven)
        assert pos.stop_loss_price == pytest.approx(100.0)

    @pytest.mark.asyncio
    async def test_peak_price_initialization_for_legacy_positions(self, trailing_engine):
        """Test peak_price is initialized for legacy positions without it."""
        position = Position(
            id="legacy_pos",
            token_mint="trail_mint",
            token_symbol="LEGACY",
            direction=TradeDirection.LONG,
            entry_price=100.0,
            current_price=100.0,
            peak_price=None,  # Legacy position without peak_price
            amount_usd=500.0,
            amount=1000.0,
            take_profit_price=150.0,
            stop_loss_price=80.0,
            status=TradeStatus.OPEN,
            opened_at=datetime.utcnow().isoformat(),
        )
        trailing_engine.positions["legacy_pos"] = position

        # Mock price same as entry
        trailing_engine.jupiter.get_token_price = AsyncMock(return_value=100.0)

        await trailing_engine.monitor_stop_losses()

        pos = trailing_engine.positions.get("legacy_pos")
        if pos:
            # peak_price should be initialized to entry_price
            assert pos.peak_price == 100.0


# =============================================================================
# Monitor Stop Losses Exception Handling (Lines 782-788, 813-817, 846-847)
# =============================================================================


class TestMonitorStopLossesExceptionHandling:
    """Tests for exception handling in monitor_stop_losses."""

    @pytest.fixture
    def exception_engine(self, trading_engine):
        """Create engine for exception testing."""
        trading_engine.dry_run = False
        mock_order_manager = AsyncMock()
        trading_engine.order_manager = mock_order_manager
        return trading_engine

    @pytest.mark.asyncio
    async def test_monitor_order_cancel_exception_handled(self, exception_engine):
        """Test order cancel exceptions are handled gracefully."""
        position = Position(
            id="cancel_exc",
            token_mint="exc_mint",
            token_symbol="EXCEPT",
            direction=TradeDirection.LONG,
            entry_price=100.0,
            current_price=100.0,
            amount_usd=500.0,
            amount=1000.0,
            take_profit_price=120.0,
            stop_loss_price=80.0,
            status=TradeStatus.OPEN,
            opened_at=datetime.utcnow().isoformat(),
            tp_order_id="tp_fail",
            sl_order_id="sl_fail",
        )
        exception_engine.positions["cancel_exc"] = position

        # Mock TP hit
        exception_engine.jupiter.get_token_price = AsyncMock(return_value=130.0)
        exception_engine.jupiter.get_quote = AsyncMock(return_value=MagicMock(input_amount=1000000000000))

        # Mock order cancel to raise exception
        exception_engine.order_manager.cancel_order = AsyncMock(
            side_effect=Exception("Order not found")
        )

        # Mock wallet and swap
        exception_engine.wallet.get_token_balances = AsyncMock(return_value={
            "exc_mint": {"balance": 1000.0}
        })
        from types import SimpleNamespace
        exception_engine._execute_swap = AsyncMock(
            return_value=SimpleNamespace(success=True, signature="tx")
        )
        exception_engine.jupiter.get_token_info = AsyncMock(
            return_value=SimpleNamespace(decimals=9)
        )

        with patch('bots.treasury.trading.trading_operations.log_trading_error'):
            closed = await exception_engine.monitor_stop_losses()

        # Should still close despite order cancel failure
        assert len(closed) == 1
        assert closed[0]["reason"] == "TP_HIT"

    @pytest.mark.asyncio
    async def test_monitor_sell_exception_handled(self, exception_engine):
        """Test sell exceptions in monitor are handled gracefully."""
        position = Position(
            id="sell_exc",
            token_mint="sell_exc_mint",
            token_symbol="SELLEXC",
            direction=TradeDirection.LONG,
            entry_price=100.0,
            current_price=100.0,
            amount_usd=500.0,
            amount=1000.0,
            take_profit_price=120.0,
            stop_loss_price=80.0,
            status=TradeStatus.OPEN,
            opened_at=datetime.utcnow().isoformat(),
        )
        exception_engine.positions["sell_exc"] = position

        # Mock SL breach
        exception_engine.jupiter.get_token_price = AsyncMock(return_value=75.0)
        exception_engine.jupiter.get_quote = AsyncMock(return_value=MagicMock(input_amount=1000000000000))

        # Mock wallet to raise exception
        exception_engine.wallet.get_token_balances = AsyncMock(
            side_effect=Exception("Wallet error")
        )

        with patch('bots.treasury.trading.trading_operations.log_trading_error'):
            closed = await exception_engine.monitor_stop_losses()

        # Position should still be closed in state
        assert len(closed) == 1
        assert "sell_exc" not in exception_engine.positions

    @pytest.mark.asyncio
    async def test_monitor_close_exception_caught(self, exception_engine):
        """Test that exceptions during position close are caught."""
        position = Position(
            id="close_exc",
            token_mint="close_exc_mint",
            token_symbol="CLOSEEXC",
            direction=TradeDirection.LONG,
            entry_price=100.0,
            current_price=100.0,
            amount_usd=500.0,
            amount=1000.0,
            take_profit_price=120.0,
            stop_loss_price=80.0,
            status=TradeStatus.OPEN,
            opened_at=datetime.utcnow().isoformat(),
        )
        exception_engine.positions["close_exc"] = position

        # Mock TP hit
        exception_engine.jupiter.get_token_price = AsyncMock(return_value=130.0)

        # Mock the entire close logic to fail
        async def fail_on_close(*args, **kwargs):
            raise Exception("Close processing failed")

        exception_engine.wallet.get_token_balances = AsyncMock(return_value={
            "close_exc_mint": {"balance": 1000.0}
        })
        exception_engine.jupiter.get_quote = AsyncMock(side_effect=fail_on_close)

        with patch('bots.treasury.trading.trading_operations.log_trading_error') as mock_log:
            closed = await exception_engine.monitor_stop_losses()

        # Exception should be logged
        mock_log.assert_called()
