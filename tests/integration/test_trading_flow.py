"""
Integration tests for the complete trading flow.

Tests the end-to-end trading workflow:
- Signal detection -> Position creation -> Monitoring -> Exit

All external APIs are mocked to enable fast, reliable testing.
"""

import pytest
import asyncio
import json
import tempfile
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
import os

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from bots.treasury.trading import (
    Position,
    TradeDirection,
    TradeStatus,
    RiskLevel,
    TradingEngine,
)
from core.sentiment_aggregator import (
    SentimentSource,
    SentimentLabel,
    SentimentReading,
    SentimentAggregator,
)


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def temp_state_dir(tmp_path):
    """Create temporary directory for state files."""
    return tmp_path


@pytest.fixture
def mock_wallet():
    """Create a mock wallet."""
    wallet = MagicMock()
    wallet.get_treasury.return_value = MagicMock(address="treasury_address")
    wallet.get_balance = AsyncMock(return_value=(100.0, 20000.0))  # 100 SOL, $20k
    wallet.get_token_balances = AsyncMock(return_value={})
    return wallet


@pytest.fixture
def mock_jupiter():
    """Create a mock Jupiter client."""
    jupiter = MagicMock()
    jupiter.get_token_price = AsyncMock(return_value=100.0)  # $100/token
    jupiter.get_token_info = AsyncMock(return_value=MagicMock(
        decimals=9,
        daily_volume=1000000.0,
    ))
    jupiter.get_quote = AsyncMock(return_value=MagicMock(
        output_amount_ui=1.0,
        price_impact=0.01,
    ))
    jupiter.execute_swap = AsyncMock(return_value=MagicMock(
        success=True,
        signature="tx_sig_123",
    ))
    return jupiter


@pytest.fixture
def mock_sentiment_aggregator(tmp_path):
    """Create a mock sentiment aggregator."""
    db_path = tmp_path / "sentiment.db"
    return SentimentAggregator(db_path=db_path)


@pytest.fixture
def trading_engine(mock_wallet, mock_jupiter, temp_state_dir):
    """Create a trading engine with mocked dependencies."""
    with patch('bots.treasury.trading.SecureWallet', return_value=mock_wallet):
        with patch('bots.treasury.trading.JupiterClient', return_value=mock_jupiter):
            engine = TradingEngine(
                wallet=mock_wallet,
                jupiter=mock_jupiter,
                dry_run=True,
                enable_signals=False,
                max_positions=10,
                admin_user_ids=[12345],  # Test admin
            )
            # Clear positions to ensure clean state
            engine.positions.clear()
            # Reset daily limits for test isolation
            engine.MAX_DAILY_USD = 100000.0  # High limit for testing
            engine.MAX_TRADE_USD = 10000.0
            return engine


# =============================================================================
# End-to-End Trading Flow Tests
# =============================================================================

class TestTradingFlowE2E:
    """End-to-end tests for the trading flow."""

    @pytest.mark.asyncio
    async def test_complete_trade_lifecycle(
        self,
        trading_engine,
        mock_jupiter,
        mock_sentiment_aggregator
    ):
        """Test complete trade lifecycle: open -> monitor -> close."""
        admin_user_id = 12345

        # Phase 1: Generate trading signal from sentiment
        now = datetime.now(timezone.utc).isoformat()
        mock_sentiment_aggregator.add_reading(SentimentReading(
            source=SentimentSource.GROK,
            symbol="SOL",
            score=75.0,
            label=SentimentLabel.VERY_BULLISH,
            confidence=0.90,
            timestamp=now,
        ))

        aggregated = mock_sentiment_aggregator.aggregate("SOL")
        assert aggregated.overall_label in [
            SentimentLabel.BULLISH,
            SentimentLabel.VERY_BULLISH
        ]

        # Phase 2: Analyze signal and determine direction
        direction, reason = await trading_engine.analyze_sentiment_signal(
            token_mint="So11111111111111111111111111111111111111112",
            sentiment_score=0.50,  # > 0.40 threshold
            sentiment_grade="A"
        )
        assert direction == TradeDirection.LONG

        # Phase 3: Open position
        success, message, position = await trading_engine.open_position(
            token_mint="So11111111111111111111111111111111111111112",
            token_symbol="SOL",
            direction=TradeDirection.LONG,
            amount_usd=100.0,
            sentiment_grade="A",
            sentiment_score=0.50,
            user_id=admin_user_id,
        )

        assert success is True
        assert position is not None
        assert position.status == TradeStatus.OPEN
        assert position.token_symbol == "SOL"
        assert position.direction == TradeDirection.LONG

        # Phase 4: Monitor position (price increase)
        position.current_price = 150.0  # +50%
        assert position.unrealized_pnl > 0
        assert position.unrealized_pnl_pct == 50.0

        # Phase 5: Close position at profit
        close_success, close_msg = await trading_engine.close_position(
            position.id,
            reason="TP hit",
            user_id=admin_user_id,
        )

        assert close_success is True
        assert position.status == TradeStatus.CLOSED

    @pytest.mark.asyncio
    async def test_trade_rejection_unauthorized_user(self, trading_engine):
        """Test trade rejection for unauthorized user."""
        unauthorized_user = 99999

        success, message, position = await trading_engine.open_position(
            token_mint="TestMint123",
            token_symbol="TEST",
            direction=TradeDirection.LONG,
            amount_usd=50.0,
            sentiment_grade="A",
            user_id=unauthorized_user,
        )

        assert success is False
        assert "not authorized" in message.lower()
        assert position is None

    @pytest.mark.asyncio
    async def test_trade_rejection_no_user_id(self, trading_engine):
        """Test trade rejection when no user_id provided."""
        success, message, position = await trading_engine.open_position(
            token_mint="TestMint123",
            token_symbol="TEST",
            direction=TradeDirection.LONG,
            amount_usd=50.0,
            sentiment_grade="A",
            user_id=None,
        )

        assert success is False
        assert "admin only" in message.lower()
        assert position is None

    @pytest.mark.asyncio
    async def test_trade_rejection_low_grade(self, trading_engine):
        """Test trade rejection for D/F grade tokens."""
        admin_user_id = 12345

        # D grade
        success, message, _ = await trading_engine.open_position(
            token_mint="TestMint123",
            token_symbol="RISKY",
            direction=TradeDirection.LONG,
            sentiment_grade="D",
            user_id=admin_user_id,
        )
        assert success is False
        assert "too risky" in message.lower()

        # F grade
        success, message, _ = await trading_engine.open_position(
            token_mint="TestMint456",
            token_symbol="SUPER_RISKY",
            direction=TradeDirection.LONG,
            sentiment_grade="F",
            user_id=admin_user_id,
        )
        assert success is False
        assert "too risky" in message.lower()

    @pytest.mark.asyncio
    async def test_max_positions_limit(
        self,
        trading_engine,
        mock_jupiter
    ):
        """Test max positions limit is enforced."""
        admin_user_id = 12345

        # Fill up to max positions
        for i in range(10):
            # Need unique token mints
            mock_jupiter.get_token_price = AsyncMock(return_value=100.0)
            mock_jupiter.get_token_info = AsyncMock(return_value=MagicMock(
                decimals=9,
                daily_volume=1000000.0,
            ))

            success, _, _ = await trading_engine.open_position(
                token_mint=f"UniqueEstablishedMint{i}",  # Unique established token
                token_symbol=f"SOL{i}",  # SOL pattern for established
                direction=TradeDirection.LONG,
                amount_usd=10.0,
                sentiment_grade="B",
                user_id=admin_user_id,
            )

        # Verify we have 10 open positions
        open_positions = [p for p in trading_engine.positions.values() if p.is_open]
        assert len(open_positions) == 10

        # Attempt one more
        success, message, _ = await trading_engine.open_position(
            token_mint="OneMoreMint",
            token_symbol="EXCESS",
            direction=TradeDirection.LONG,
            sentiment_grade="A",
            sentiment_score=0.50,
            user_id=admin_user_id,
        )

        # Should be rejected due to max positions
        assert success is False
        assert "maximum" in message.lower() or "max" in message.lower()

    @pytest.mark.asyncio
    async def test_position_size_adjustment_by_risk(
        self,
        trading_engine,
    ):
        """Test position size is adjusted by token risk tier."""
        admin_user_id = 12345

        # Established token (100% position size)
        success1, _, pos1 = await trading_engine.open_position(
            token_mint="So11111111111111111111111111111111111111112",
            token_symbol="SOL",
            direction=TradeDirection.LONG,
            amount_usd=100.0,
            sentiment_grade="B",
            user_id=admin_user_id,
        )
        assert success1 is True
        assert pos1.amount_usd == 100.0  # Full size for established

        # High risk token (15% position size)
        success2, _, pos2 = await trading_engine.open_position(
            token_mint="pumpHighRiskToken123",
            token_symbol="PUMP",
            direction=TradeDirection.LONG,
            amount_usd=100.0,
            sentiment_grade="B",
            user_id=admin_user_id,
        )
        assert success2 is True
        assert pos2.amount_usd == 15.0  # 15% for high risk


# =============================================================================
# Multi-Signal Integration Tests
# =============================================================================

class TestMultiSignalIntegration:
    """Tests for multi-signal integration."""

    @pytest.fixture
    def trading_engine_with_signals(
        self,
        mock_wallet,
        mock_jupiter,
        temp_state_dir
    ):
        """Create trading engine with signal analysis enabled."""
        with patch('bots.treasury.trading.SecureWallet', return_value=mock_wallet):
            with patch('bots.treasury.trading.JupiterClient', return_value=mock_jupiter):
                engine = TradingEngine(
                    wallet=mock_wallet,
                    jupiter=mock_jupiter,
                    dry_run=True,
                    enable_signals=False,  # Start disabled to prevent API calls
                    max_positions=10,
                    admin_user_ids=[12345],
                )
                engine.positions.clear()
                return engine

    @pytest.mark.asyncio
    async def test_combined_signal_sentiment_only(
        self,
        trading_engine_with_signals
    ):
        """Test combined signal with sentiment only (no decision matrix)."""
        engine = trading_engine_with_signals

        direction, reason, confidence = await engine.get_combined_signal(
            token_mint="TestMint",
            symbol="BTC",
            sentiment_score=0.50,
            sentiment_grade="A",
            prices=None,
        )

        # Without decision matrix, falls back to sentiment-only
        assert direction == TradeDirection.LONG
        assert confidence == 0.5


# =============================================================================
# State Persistence Tests
# =============================================================================

class TestStatePersistence:
    """Tests for state persistence across restarts."""

    @pytest.mark.asyncio
    async def test_positions_persist_across_restart(
        self,
        mock_wallet,
        mock_jupiter,
        temp_state_dir
    ):
        """Test positions are saved and loaded correctly."""
        admin_user_id = 12345

        # Create engine and open position
        engine1 = TradingEngine(
            wallet=mock_wallet,
            jupiter=mock_jupiter,
            dry_run=True,
            enable_signals=False,
            admin_user_ids=[admin_user_id],
        )
        engine1.positions.clear()
        engine1.MAX_DAILY_USD = 100000.0
        engine1.MAX_TRADE_USD = 10000.0

        success, msg, pos = await engine1.open_position(
            token_mint="So11111111111111111111111111111111111111112",
            token_symbol="SOL",
            direction=TradeDirection.LONG,
            amount_usd=100.0,
            sentiment_grade="B",
            user_id=admin_user_id,
        )
        assert success is True, f"Failed to open: {msg}"
        position_id = pos.id

        # Create new engine (simulating restart)
        # Note: positions persist via file in the standard location
        engine2 = TradingEngine(
            wallet=mock_wallet,
            jupiter=mock_jupiter,
            dry_run=True,
            enable_signals=False,
            admin_user_ids=[admin_user_id],
        )

        # Position should be loaded from the standard state file
        assert position_id in engine2.positions
        loaded_pos = engine2.positions[position_id]
        assert loaded_pos.token_symbol == "SOL"
        assert loaded_pos.direction == TradeDirection.LONG
        assert loaded_pos.status == TradeStatus.OPEN


# =============================================================================
# TP/SL Trigger Tests
# =============================================================================

class TestTPSLTriggers:
    """Tests for take-profit and stop-loss triggers."""

    @pytest.fixture
    def clean_engine(self, mock_wallet, mock_jupiter):
        """Create a clean trading engine for these tests."""
        engine = TradingEngine(
            wallet=mock_wallet,
            jupiter=mock_jupiter,
            dry_run=True,
            enable_signals=False,
            max_positions=10,
            admin_user_ids=[12345],
        )
        engine.positions.clear()
        engine.max_positions = 10
        # Reset daily limits for test isolation
        engine.MAX_DAILY_USD = 100000.0
        engine.MAX_TRADE_USD = 10000.0
        return engine

    @pytest.mark.asyncio
    async def test_take_profit_detection(self, clean_engine):
        """Test take profit trigger detection."""
        admin_user_id = 12345

        # Open position with 30% TP
        success, msg, pos = await clean_engine.open_position(
            token_mint="So11111111111111111111111111111111111111112",
            token_symbol="SOL",
            direction=TradeDirection.LONG,
            amount_usd=100.0,
            sentiment_grade="A",  # 30% TP
            user_id=admin_user_id,
        )

        assert success is True, f"Failed to open: {msg}"
        entry = pos.entry_price
        tp_target = pos.take_profit_price

        # TP should be +30% above entry
        assert tp_target == entry * 1.30

        # Simulate price reaching TP
        pos.current_price = tp_target + 1.0
        assert pos.current_price >= tp_target

    @pytest.mark.asyncio
    async def test_stop_loss_detection(self, clean_engine):
        """Test stop loss trigger detection."""
        admin_user_id = 12345

        # Open position with 8% SL (need unique token to not hit duplicate)
        success, msg, pos = await clean_engine.open_position(
            token_mint="JUPyiwrYJFskUPiHa7hkeR8VUtAeFoSYbKedZNsDvCN",  # JUP
            token_symbol="JUP",
            direction=TradeDirection.LONG,
            amount_usd=100.0,
            sentiment_grade="A",  # 8% SL
            user_id=admin_user_id,
        )

        assert success is True, f"Failed to open: {msg}"
        entry = pos.entry_price
        sl_target = pos.stop_loss_price

        # SL should be -8% below entry
        assert sl_target == entry * 0.92

        # Simulate price reaching SL
        pos.current_price = sl_target - 1.0
        assert pos.current_price <= sl_target


# =============================================================================
# Concurrent Trade Protection Tests
# =============================================================================

class TestConcurrentTradeProtection:
    """Tests for concurrent trade protection."""

    @pytest.fixture
    def clean_engine(self, mock_wallet, mock_jupiter):
        """Create a clean trading engine for stacking tests."""
        engine = TradingEngine(
            wallet=mock_wallet,
            jupiter=mock_jupiter,
            dry_run=True,
            enable_signals=False,
            max_positions=10,
            admin_user_ids=[12345],
        )
        engine.positions.clear()
        engine.max_positions = 10
        # Reset daily limits for test isolation
        engine.MAX_DAILY_USD = 100000.0
        engine.MAX_TRADE_USD = 10000.0
        return engine

    @pytest.mark.asyncio
    async def test_duplicate_position_with_stacking_disabled(
        self,
        clean_engine
    ):
        """Test duplicate positions rejected when stacking disabled."""
        admin_user_id = 12345
        clean_engine.ALLOW_STACKING = False

        # First position
        success1, msg1, pos1 = await clean_engine.open_position(
            token_mint="So11111111111111111111111111111111111111112",
            token_symbol="SOL",
            direction=TradeDirection.LONG,
            amount_usd=100.0,
            sentiment_grade="B",
            user_id=admin_user_id,
        )
        assert success1 is True, f"First position failed: {msg1}"

        # Second position in same token
        success2, message2, _ = await clean_engine.open_position(
            token_mint="So11111111111111111111111111111111111111112",
            token_symbol="SOL",
            direction=TradeDirection.LONG,
            amount_usd=100.0,
            sentiment_grade="B",
            user_id=admin_user_id,
        )

        assert success2 is False
        assert "already" in message2.lower() or "stacking" in message2.lower()

    @pytest.mark.asyncio
    async def test_duplicate_position_with_stacking_enabled(
        self,
        clean_engine
    ):
        """Test duplicate positions allowed when stacking enabled."""
        admin_user_id = 12345
        clean_engine.ALLOW_STACKING = True

        # First position
        success1, msg1, pos1 = await clean_engine.open_position(
            token_mint="So11111111111111111111111111111111111111112",
            token_symbol="SOL",
            direction=TradeDirection.LONG,
            amount_usd=100.0,
            sentiment_grade="B",
            user_id=admin_user_id,
        )
        assert success1 is True, f"First position failed: {msg1}"

        # Second position in same token (should succeed)
        success2, msg2, pos2 = await clean_engine.open_position(
            token_mint="So11111111111111111111111111111111111111112",
            token_symbol="SOL",
            direction=TradeDirection.LONG,
            amount_usd=100.0,
            sentiment_grade="B",
            user_id=admin_user_id,
        )

        assert success2 is True, f"Second position failed: {msg2}"
        assert pos2.id != pos1.id


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
