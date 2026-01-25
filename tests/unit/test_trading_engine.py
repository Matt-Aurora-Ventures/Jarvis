"""
Comprehensive unit tests for the Trading Engine.

Tests cover:
- Position class (creation, serialization, PnL calculations)
- Position sizing based on risk level
- TP/SL calculations by sentiment grade
- Spending limits validation
- Token risk classification
- Risk-adjusted position sizing
- Admin authorization
- Sentiment signal analysis
"""

import pytest
import asyncio
import json
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock

import sys
import os
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from bots.treasury.trading import (
    Position,
    TradeDirection,
    TradeStatus,
    RiskLevel,
    TradeReport,
    TradingEngine,
)


# =============================================================================
# Position Class Tests
# =============================================================================

class TestPosition:
    """Tests for the Position dataclass."""

    def test_position_creation(self):
        """Test basic position creation."""
        position = Position(
            id="test123",
            token_mint="So11111111111111111111111111111111111111112",
            token_symbol="SOL",
            direction=TradeDirection.LONG,
            entry_price=100.0,
            current_price=110.0,
            amount=10.0,
            amount_usd=1000.0,
            take_profit_price=120.0,
            stop_loss_price=90.0,
            status=TradeStatus.OPEN,
            opened_at="2024-01-01T00:00:00Z",
        )

        assert position.id == "test123"
        assert position.token_symbol == "SOL"
        assert position.direction == TradeDirection.LONG
        assert position.entry_price == 100.0
        assert position.current_price == 110.0
        assert position.status == TradeStatus.OPEN

    def test_position_is_open_property(self):
        """Test is_open property."""
        position = Position(
            id="test1",
            token_mint="mint1",
            token_symbol="TEST",
            direction=TradeDirection.LONG,
            entry_price=100.0,
            current_price=100.0,
            amount=1.0,
            amount_usd=100.0,
            take_profit_price=110.0,
            stop_loss_price=90.0,
            status=TradeStatus.OPEN,
            opened_at="2024-01-01T00:00:00Z",
        )
        assert position.is_open is True

        position.status = TradeStatus.CLOSED
        assert position.is_open is False

        position.status = TradeStatus.PENDING
        assert position.is_open is False

    def test_unrealized_pnl_calculation(self):
        """Test unrealized PnL calculation for long positions."""
        position = Position(
            id="pnl1",
            token_mint="mint1",
            token_symbol="TEST",
            direction=TradeDirection.LONG,
            entry_price=100.0,
            current_price=150.0,  # +50% gain
            amount=10.0,
            amount_usd=1000.0,
            take_profit_price=200.0,
            stop_loss_price=80.0,
            status=TradeStatus.OPEN,
            opened_at="2024-01-01T00:00:00Z",
        )

        # (150 - 100) / 100 * 1000 = 500
        assert position.unrealized_pnl == 500.0

    def test_unrealized_pnl_pct_calculation(self):
        """Test unrealized PnL percentage calculation."""
        position = Position(
            id="pnl2",
            token_mint="mint1",
            token_symbol="TEST",
            direction=TradeDirection.LONG,
            entry_price=100.0,
            current_price=120.0,  # +20%
            amount=10.0,
            amount_usd=1000.0,
            take_profit_price=150.0,
            stop_loss_price=90.0,
            status=TradeStatus.OPEN,
            opened_at="2024-01-01T00:00:00Z",
        )

        assert position.unrealized_pnl_pct == 20.0

    def test_unrealized_pnl_negative(self):
        """Test negative unrealized PnL."""
        position = Position(
            id="loss1",
            token_mint="mint1",
            token_symbol="TEST",
            direction=TradeDirection.LONG,
            entry_price=100.0,
            current_price=80.0,  # -20%
            amount=10.0,
            amount_usd=1000.0,
            take_profit_price=150.0,
            stop_loss_price=70.0,
            status=TradeStatus.OPEN,
            opened_at="2024-01-01T00:00:00Z",
        )

        # (80 - 100) / 100 * 1000 = -200
        assert position.unrealized_pnl == -200.0
        assert position.unrealized_pnl_pct == -20.0

    def test_unrealized_pnl_zero_entry_price(self):
        """Test unrealized PnL with zero entry price (edge case)."""
        position = Position(
            id="edge1",
            token_mint="mint1",
            token_symbol="TEST",
            direction=TradeDirection.LONG,
            entry_price=0.0,  # Edge case
            current_price=100.0,
            amount=10.0,
            amount_usd=0.0,
            take_profit_price=150.0,
            stop_loss_price=0.0,
            status=TradeStatus.OPEN,
            opened_at="2024-01-01T00:00:00Z",
        )

        assert position.unrealized_pnl_pct == 0.0

    def test_position_to_dict(self):
        """Test Position serialization to dict."""
        position = Position(
            id="serial1",
            token_mint="mint123",
            token_symbol="TEST",
            direction=TradeDirection.LONG,
            entry_price=100.0,
            current_price=110.0,
            amount=5.0,
            amount_usd=500.0,
            take_profit_price=130.0,
            stop_loss_price=85.0,
            status=TradeStatus.OPEN,
            opened_at="2024-01-01T00:00:00Z",
            sentiment_grade="A",
            sentiment_score=0.75,
        )

        data = position.to_dict()

        assert data["id"] == "serial1"
        assert data["token_mint"] == "mint123"
        assert data["direction"] == "LONG"
        assert data["status"] == "OPEN"
        assert data["sentiment_grade"] == "A"
        assert data["sentiment_score"] == 0.75

    def test_position_from_dict(self):
        """Test Position deserialization from dict."""
        data = {
            "id": "deserial1",
            "token_mint": "mint456",
            "token_symbol": "DESER",
            "direction": "LONG",
            "entry_price": 200.0,
            "current_price": 220.0,
            "amount": 2.5,
            "amount_usd": 500.0,
            "take_profit_price": 260.0,
            "stop_loss_price": 170.0,
            "status": "OPEN",
            "opened_at": "2024-06-01T12:00:00Z",
            "sentiment_grade": "B+",
            "sentiment_score": 0.55,
        }

        position = Position.from_dict(data)

        assert position.id == "deserial1"
        assert position.token_symbol == "DESER"
        assert position.direction == TradeDirection.LONG
        assert position.status == TradeStatus.OPEN
        assert position.sentiment_grade == "B+"

    def test_position_roundtrip_serialization(self):
        """Test Position survives serialization roundtrip."""
        original = Position(
            id="round1",
            token_mint="mintRT",
            token_symbol="ROUND",
            direction=TradeDirection.LONG,
            entry_price=50.0,
            current_price=55.0,
            amount=20.0,
            amount_usd=1000.0,
            take_profit_price=65.0,
            stop_loss_price=40.0,
            status=TradeStatus.OPEN,
            opened_at="2024-03-15T08:30:00Z",
            sentiment_grade="A-",
            sentiment_score=0.65,
            tp_order_id="tp123",
            sl_order_id="sl456",
        )

        # Serialize to dict, then to JSON, then back
        data = original.to_dict()
        json_str = json.dumps(data)
        loaded_data = json.loads(json_str)
        restored = Position.from_dict(loaded_data)

        assert restored.id == original.id
        assert restored.token_mint == original.token_mint
        assert restored.direction == original.direction
        assert restored.tp_order_id == original.tp_order_id
        assert restored.sl_order_id == original.sl_order_id


# =============================================================================
# TradeReport Tests
# =============================================================================

class TestTradeReport:
    """Tests for the TradeReport dataclass."""

    def test_trade_report_creation(self):
        """Test TradeReport creation with defaults."""
        report = TradeReport()

        assert report.total_trades == 0
        assert report.winning_trades == 0
        assert report.win_rate == 0.0
        assert report.total_pnl_usd == 0.0

    def test_trade_report_with_data(self):
        """Test TradeReport with populated data."""
        report = TradeReport(
            total_trades=100,
            winning_trades=60,
            losing_trades=40,
            win_rate=60.0,
            total_pnl_usd=5000.0,
            total_pnl_pct=25.0,
            best_trade_pnl=500.0,
            worst_trade_pnl=-200.0,
            avg_trade_pnl=50.0,
            average_win_usd=120.0,
            average_loss_usd=55.0,
            open_positions=5,
            unrealized_pnl=200.0,
        )

        assert report.total_trades == 100
        assert report.win_rate == 60.0
        assert report.best_trade_pnl == 500.0

    def test_trade_report_to_telegram_message(self):
        """Test TradeReport formats to Telegram correctly."""
        report = TradeReport(
            total_trades=50,
            winning_trades=30,
            losing_trades=20,
            win_rate=60.0,
            total_pnl_usd=1500.0,
            total_pnl_pct=15.0,
            best_trade_pnl=300.0,
            worst_trade_pnl=-100.0,
            avg_trade_pnl=30.0,
        )

        message = report.to_telegram_message()

        assert "TRADING PERFORMANCE REPORT" in message
        assert "50" in message  # total trades
        assert "60.0%" in message  # win rate
        # Format is $+1500.00 with sign
        assert "1500" in message  # total PnL value present


# =============================================================================
# TradingEngine Position Sizing Tests
# =============================================================================

class TestPositionSizing:
    """Tests for position sizing calculations."""

    @pytest.fixture
    def mock_engine(self):
        """Create a mock trading engine for testing."""
        with patch('bots.treasury.trading.SecureWallet') as MockWallet, \
             patch('bots.treasury.trading.JupiterClient') as MockJupiter:

            wallet = MockWallet.return_value
            jupiter = MockJupiter.return_value

            engine = TradingEngine(
                wallet=wallet,
                jupiter=jupiter,
                dry_run=True,
                enable_signals=False,
            )
            return engine

    def test_position_size_conservative(self, mock_engine):
        """Test conservative position sizing (1%)."""
        portfolio = 10000.0
        size = mock_engine.calculate_position_size(portfolio, RiskLevel.CONSERVATIVE)
        assert size == 100.0  # 1% of 10000

    def test_position_size_moderate(self, mock_engine):
        """Test moderate position sizing (2%)."""
        portfolio = 10000.0
        size = mock_engine.calculate_position_size(portfolio, RiskLevel.MODERATE)
        assert size == 200.0  # 2% of 10000

    def test_position_size_aggressive(self, mock_engine):
        """Test aggressive position sizing (5%)."""
        portfolio = 10000.0
        size = mock_engine.calculate_position_size(portfolio, RiskLevel.AGGRESSIVE)
        assert size == 500.0  # 5% of 10000

    def test_position_size_degen(self, mock_engine):
        """Test degen position sizing (10%)."""
        portfolio = 10000.0
        size = mock_engine.calculate_position_size(portfolio, RiskLevel.DEGEN)
        assert size == 1000.0  # 10% of 10000

    def test_position_size_uses_engine_default(self, mock_engine):
        """Test position sizing uses engine's default risk level."""
        mock_engine.risk_level = RiskLevel.CONSERVATIVE
        portfolio = 5000.0
        size = mock_engine.calculate_position_size(portfolio)
        assert size == 50.0  # 1% of 5000


# =============================================================================
# TradingEngine TP/SL Calculation Tests
# =============================================================================

class TestTakeProfitStopLoss:
    """Tests for take profit and stop loss calculations."""

    @pytest.fixture
    def mock_engine(self):
        """Create a mock trading engine for testing."""
        with patch('bots.treasury.trading.SecureWallet') as MockWallet, \
             patch('bots.treasury.trading.JupiterClient') as MockJupiter:

            wallet = MockWallet.return_value
            jupiter = MockJupiter.return_value

            engine = TradingEngine(
                wallet=wallet,
                jupiter=jupiter,
                dry_run=True,
                enable_signals=False,
            )
            return engine

    def test_tp_sl_grade_a_plus(self, mock_engine):
        """Test TP/SL for A+ grade (30% TP, 8% SL)."""
        entry = 100.0
        tp, sl = mock_engine.get_tp_sl_levels(entry, "A+")

        assert tp == 130.0  # +30%
        assert sl == 92.0   # -8%

    def test_tp_sl_grade_a(self, mock_engine):
        """Test TP/SL for A grade."""
        entry = 100.0
        tp, sl = mock_engine.get_tp_sl_levels(entry, "A")

        assert tp == 130.0  # +30%
        assert sl == 92.0   # -8%

    def test_tp_sl_grade_b(self, mock_engine):
        """Test TP/SL for B grade (18% TP, 12% SL)."""
        entry = 100.0
        tp, sl = mock_engine.get_tp_sl_levels(entry, "B")

        assert tp == 118.0  # +18%
        assert sl == 88.0   # -12%

    def test_tp_sl_grade_c(self, mock_engine):
        """Test TP/SL for C grade (10% TP, 15% SL)."""
        entry = 100.0
        tp, sl = mock_engine.get_tp_sl_levels(entry, "C")

        # Use approximate comparison for floating point
        assert abs(tp - 110.0) < 0.01  # +10%
        assert abs(sl - 85.0) < 0.01   # -15%

    def test_tp_sl_grade_f(self, mock_engine):
        """Test TP/SL for F grade (very risky)."""
        entry = 100.0
        tp, sl = mock_engine.get_tp_sl_levels(entry, "F")

        assert tp == 105.0  # +5%
        assert sl == 80.0   # -20%

    def test_tp_sl_unknown_grade_defaults(self, mock_engine):
        """Test TP/SL for unknown grade uses defaults."""
        entry = 100.0
        tp, sl = mock_engine.get_tp_sl_levels(entry, "UNKNOWN")

        # Default: +20% TP, -10% SL
        assert tp == 120.0
        assert sl == 90.0

    def test_tp_sl_custom_override(self, mock_engine):
        """Test custom TP/SL override."""
        entry = 100.0
        tp, sl = mock_engine.get_tp_sl_levels(
            entry, "B",
            custom_tp=0.50,  # 50% TP
            custom_sl=0.25   # 25% SL
        )

        assert tp == 150.0  # +50%
        assert sl == 75.0   # -25%


# =============================================================================
# Token Risk Classification Tests
# =============================================================================

class TestTokenRiskClassification:
    """Tests for token risk classification."""

    @pytest.fixture
    def mock_engine(self):
        """Create a mock trading engine for testing."""
        with patch('bots.treasury.trading.SecureWallet') as MockWallet, \
             patch('bots.treasury.trading.JupiterClient') as MockJupiter:

            wallet = MockWallet.return_value
            jupiter = MockJupiter.return_value

            engine = TradingEngine(
                wallet=wallet,
                jupiter=jupiter,
                dry_run=True,
                enable_signals=False,
            )
            return engine

    def test_is_established_token_sol(self, mock_engine):
        """Test SOL is established."""
        sol_mint = "So11111111111111111111111111111111111111112"
        assert mock_engine.is_established_token(sol_mint) is True

    def test_is_established_token_bonk(self, mock_engine):
        """Test BONK is established."""
        bonk_mint = "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263"
        assert mock_engine.is_established_token(bonk_mint) is True

    def test_is_established_token_unknown(self, mock_engine):
        """Test unknown token is not established."""
        unknown_mint = "SomeUnknownMintAddress123456789"
        assert mock_engine.is_established_token(unknown_mint) is False

    def test_is_high_risk_pump_token(self, mock_engine):
        """Test pump.fun token detection."""
        pump_mint = "pump123456789"
        assert mock_engine.is_high_risk_token(pump_mint) is True

    def test_is_high_risk_normal_token(self, mock_engine):
        """Test normal token is not high risk."""
        normal_mint = "NormalMintAddress123"
        assert mock_engine.is_high_risk_token(normal_mint) is False

    def test_classify_token_established(self, mock_engine):
        """Test ESTABLISHED classification."""
        sol_mint = "So11111111111111111111111111111111111111112"
        tier = mock_engine.classify_token_risk(sol_mint, "SOL")
        assert tier == "ESTABLISHED"

    def test_classify_token_xstocks(self, mock_engine):
        """Test XStocks classified as ESTABLISHED."""
        xstock_mint = "XsoCS1TfEyfFhfvj8EtZ528L3CaKBDBRqRapnBbDF2W"
        tier = mock_engine.classify_token_risk(xstock_mint, "SPYx")
        assert tier == "ESTABLISHED"

    def test_classify_token_high_risk(self, mock_engine):
        """Test pump.fun token classified as HIGH_RISK."""
        pump_mint = "pumpNewToken123"
        tier = mock_engine.classify_token_risk(pump_mint, "PUMP")
        assert tier == "HIGH_RISK"

    def test_classify_token_mid_tier_major(self, mock_engine):
        """Test major symbol on unknown mint classified as MID."""
        unknown_mint = "UnknownMintForBTC"
        tier = mock_engine.classify_token_risk(unknown_mint, "BTC")
        assert tier == "MID"

    def test_classify_token_micro(self, mock_engine):
        """Test unknown token classified as MICRO."""
        random_mint = "RandomUnknownMint123"
        tier = mock_engine.classify_token_risk(random_mint, "RANDOM")
        assert tier == "MICRO"

    def test_risk_adjusted_position_established(self, mock_engine):
        """Test ESTABLISHED gets full position size."""
        sol_mint = "So11111111111111111111111111111111111111112"
        base = 100.0
        adjusted, tier = mock_engine.get_risk_adjusted_position_size(sol_mint, "SOL", base)

        assert adjusted == 100.0  # 100%
        assert tier == "ESTABLISHED"

    def test_risk_adjusted_position_mid(self, mock_engine):
        """Test MID tier gets 50% position size."""
        unknown_mint = "UnknownMintForETH"
        base = 100.0
        adjusted, tier = mock_engine.get_risk_adjusted_position_size(unknown_mint, "ETH", base)

        assert adjusted == 50.0  # 50%
        assert tier == "MID"

    def test_risk_adjusted_position_high_risk(self, mock_engine):
        """Test HIGH_RISK gets 15% position size."""
        pump_mint = "pumpToken123"
        base = 100.0
        adjusted, tier = mock_engine.get_risk_adjusted_position_size(pump_mint, "PUMP", base)

        assert adjusted == 15.0  # 15%
        assert tier == "HIGH_RISK"

    def test_risk_adjusted_position_micro(self, mock_engine):
        """Test MICRO gets 25% position size."""
        random_mint = "RandomNewToken"
        base = 100.0
        adjusted, tier = mock_engine.get_risk_adjusted_position_size(random_mint, "RANDOM", base)

        assert adjusted == 25.0  # 25%
        assert tier == "MICRO"


# =============================================================================
# Spending Limits Tests
# =============================================================================

class TestSpendingLimits:
    """Tests for spending limits validation."""

    @pytest.fixture
    def mock_engine(self):
        """Create a mock trading engine for testing."""
        with patch('bots.treasury.trading.SecureWallet') as MockWallet, \
             patch('bots.treasury.trading.JupiterClient') as MockJupiter:

            wallet = MockWallet.return_value
            jupiter = MockJupiter.return_value

            engine = TradingEngine(
                wallet=wallet,
                jupiter=jupiter,
                dry_run=True,
                enable_signals=False,
            )
            # Reset daily limits for test isolation
            engine.MAX_DAILY_USD = 100000.0
            engine.MAX_TRADE_USD = 100.0
            return engine

    def test_trade_within_limits(self, mock_engine):
        """Test trade within all limits passes."""
        allowed, reason = mock_engine._check_spending_limits(50.0, 10000.0)
        assert allowed is True
        assert reason == ""

    def test_trade_exceeds_max_single(self, mock_engine):
        """Test trade exceeding max single trade is rejected."""
        # MAX_TRADE_USD = 100.0
        allowed, reason = mock_engine._check_spending_limits(150.0, 10000.0)
        assert allowed is False
        assert "exceeds max single trade" in reason.lower()

    def test_trade_exceeds_position_concentration(self, mock_engine):
        """Test trade exceeding position concentration is rejected."""
        # MAX_POSITION_PCT = 0.20 (20%)
        portfolio = 1000.0
        amount = 250.0  # 25% of portfolio

        allowed, reason = mock_engine._check_spending_limits(amount, portfolio)
        assert allowed is False
        assert "exceeds max" in reason.lower()


# =============================================================================
# Admin Authorization Tests
# =============================================================================

class TestAdminAuthorization:
    """Tests for admin authorization."""

    @pytest.fixture
    def mock_engine(self):
        """Create a mock trading engine for testing."""
        with patch('bots.treasury.trading.SecureWallet') as MockWallet, \
             patch('bots.treasury.trading.JupiterClient') as MockJupiter:

            wallet = MockWallet.return_value
            jupiter = MockJupiter.return_value

            # Set known admin ID for testing
            with patch.dict(os.environ, {"JARVIS_ADMIN_USER_ID": "12345"}):
                engine = TradingEngine(
                    wallet=wallet,
                    jupiter=jupiter,
                    admin_user_ids=[99999],
                    dry_run=True,
                    enable_signals=False,
                )
            return engine

    def test_is_admin_with_admin_user_id(self, mock_engine):
        """Test ADMIN_USER_ID is recognized as admin."""
        # Should recognize the configured admin
        assert mock_engine.is_admin(mock_engine.ADMIN_USER_ID) is True

    def test_is_admin_with_added_admin(self, mock_engine):
        """Test manually added admin is recognized."""
        assert mock_engine.is_admin(99999) is True

    def test_is_admin_unauthorized_user(self, mock_engine):
        """Test unauthorized user is not admin."""
        assert mock_engine.is_admin(11111) is False

    def test_add_admin(self, mock_engine):
        """Test adding a new admin."""
        new_admin_id = 77777
        assert mock_engine.is_admin(new_admin_id) is False

        mock_engine.add_admin(new_admin_id)

        assert mock_engine.is_admin(new_admin_id) is True


# =============================================================================
# Sentiment Signal Analysis Tests
# =============================================================================

class TestSentimentSignalAnalysis:
    """Tests for sentiment signal analysis."""

    @pytest.fixture
    def mock_engine(self):
        """Create a mock trading engine for testing with cleared positions."""
        with patch('bots.treasury.trading.SecureWallet') as MockWallet, \
             patch('bots.treasury.trading.JupiterClient') as MockJupiter:

            wallet = MockWallet.return_value
            jupiter = MockJupiter.return_value

            engine = TradingEngine(
                wallet=wallet,
                jupiter=jupiter,
                dry_run=True,
                enable_signals=False,
                max_positions=10,
            )
            # Clear any positions loaded from disk to ensure clean test state
            engine.positions.clear()
            return engine

    @pytest.mark.asyncio
    async def test_high_conviction_long_signal(self, mock_engine):
        """Test high conviction bullish signal generates LONG."""
        # Thresholds: score > 0.40 AND grade in [A+, A]
        direction, reason = await mock_engine.analyze_sentiment_signal(
            token_mint="mint1",
            sentiment_score=0.50,  # >0.40 (strict inequality)
            sentiment_grade="A"
        )

        assert direction == TradeDirection.LONG
        assert "bullish" in reason.lower()

    @pytest.mark.asyncio
    async def test_strong_bullish_signal(self, mock_engine):
        """Test strong bullish signal for A-/B+ grades."""
        # Thresholds: score > 0.35 AND grade in [A-, B+]
        direction, reason = await mock_engine.analyze_sentiment_signal(
            token_mint="mint1",
            sentiment_score=0.45,  # >0.35 (strict inequality)
            sentiment_grade="B+"
        )

        assert direction == TradeDirection.LONG
        assert "bullish" in reason.lower()

    @pytest.mark.asyncio
    async def test_moderate_bullish_signal(self, mock_engine):
        """Test moderate bullish signal for B grade."""
        # Thresholds: score > 0.30 AND grade == B
        direction, reason = await mock_engine.analyze_sentiment_signal(
            token_mint="mint1",
            sentiment_score=0.40,  # >0.30 (strict inequality)
            sentiment_grade="B"
        )

        assert direction == TradeDirection.LONG
        assert "bullish" in reason.lower()

    @pytest.mark.asyncio
    async def test_bearish_signal(self, mock_engine):
        """Test strong bearish signal."""
        # Thresholds: score < -0.30
        direction, reason = await mock_engine.analyze_sentiment_signal(
            token_mint="mint1",
            sentiment_score=-0.40,  # < -0.30
            sentiment_grade="F"
        )

        assert direction == TradeDirection.SHORT
        assert "bearish" in reason.lower() or "avoid" in reason.lower()

    @pytest.mark.asyncio
    async def test_neutral_signal_weak_score(self, mock_engine):
        """Test neutral signal for weak score."""
        direction, reason = await mock_engine.analyze_sentiment_signal(
            token_mint="mint1",
            sentiment_score=0.15,  # Too weak for any threshold
            sentiment_grade="B"
        )

        assert direction == TradeDirection.NEUTRAL
        # Reason should indicate signal not strong enough or similar

    @pytest.mark.asyncio
    async def test_neutral_signal_low_grade(self, mock_engine):
        """Test neutral signal for low grade."""
        direction, reason = await mock_engine.analyze_sentiment_signal(
            token_mint="mint1",
            sentiment_score=0.35,  # Good score
            sentiment_grade="C"  # But grade too low for 0.35 threshold
        )

        assert direction == TradeDirection.NEUTRAL

    @pytest.mark.asyncio
    async def test_max_positions_reached(self, mock_engine):
        """Test neutral signal when max positions reached."""
        # Fill up positions
        for i in range(10):
            mock_engine.positions[f"pos{i}"] = Position(
                id=f"pos{i}",
                token_mint=f"mint{i}",
                token_symbol=f"TOK{i}",
                direction=TradeDirection.LONG,
                entry_price=100.0,
                current_price=100.0,
                amount=1.0,
                amount_usd=100.0,
                take_profit_price=110.0,
                stop_loss_price=90.0,
                status=TradeStatus.OPEN,
                opened_at="2024-01-01T00:00:00Z",
            )

        direction, reason = await mock_engine.analyze_sentiment_signal(
            token_mint="newmint",
            sentiment_score=0.80,  # Very strong
            sentiment_grade="A+"
        )

        assert direction == TradeDirection.NEUTRAL
        assert "max positions" in reason.lower()


# =============================================================================
# TP/SL Config Coverage Tests
# =============================================================================

class TestTPSLConfigCoverage:
    """Tests ensuring all TP/SL grade configurations are valid."""

    @pytest.fixture
    def mock_engine(self):
        """Create a mock trading engine for testing."""
        with patch('bots.treasury.trading.SecureWallet') as MockWallet, \
             patch('bots.treasury.trading.JupiterClient') as MockJupiter:

            wallet = MockWallet.return_value
            jupiter = MockJupiter.return_value

            engine = TradingEngine(
                wallet=wallet,
                jupiter=jupiter,
                dry_run=True,
                enable_signals=False,
            )
            return engine

    def test_all_grades_have_config(self, mock_engine):
        """Test all expected grades have TP/SL config."""
        expected_grades = ["A+", "A", "A-", "B+", "B", "B-", "C+", "C", "C-", "D", "F"]

        for grade in expected_grades:
            assert grade in mock_engine.TP_SL_CONFIG, f"Missing config for grade {grade}"

    def test_tp_always_positive(self, mock_engine):
        """Test take profit is always positive."""
        for grade, config in mock_engine.TP_SL_CONFIG.items():
            assert config["take_profit"] > 0, f"TP must be positive for {grade}"

    def test_sl_always_positive(self, mock_engine):
        """Test stop loss is always positive (represents percentage below entry)."""
        for grade, config in mock_engine.TP_SL_CONFIG.items():
            assert config["stop_loss"] > 0, f"SL must be positive for {grade}"

    def test_higher_grades_have_tighter_sl(self, mock_engine):
        """Test higher conviction grades have tighter stop losses."""
        a_plus_sl = mock_engine.TP_SL_CONFIG["A+"]["stop_loss"]
        f_sl = mock_engine.TP_SL_CONFIG["F"]["stop_loss"]

        # A+ should have tighter SL than F
        assert a_plus_sl < f_sl


# =============================================================================
# Order Filled Callback Tests (Lines 648-713)
# =============================================================================


class TestOrderFilledCallback:
    """Tests for handle_order_filled callback method."""

    @pytest.fixture
    def mock_engine(self):
        """Create a mock trading engine for testing."""
        with patch('bots.treasury.trading.SecureWallet') as MockWallet, \
             patch('bots.treasury.trading.JupiterClient') as MockJupiter:

            wallet = MockWallet.return_value
            jupiter = MockJupiter.return_value

            engine = TradingEngine(
                wallet=wallet,
                jupiter=jupiter,
                risk_level=RiskLevel.MODERATE,
                admin_user_ids=[123456],
            )

            yield engine

    @pytest.mark.asyncio
    async def test_take_profit_order_filled(self, mock_engine, tmp_path):
        """Test handling TP order fill closes position correctly."""
        # Setup: Create an open position
        mock_engine.STATE_FILE = tmp_path / "state.json"

        position = Position(
            id="pos_123",
            token_mint="test_mint",
            token_symbol="TEST",
            direction=TradeDirection.LONG,
            entry_price=100.0,
            current_price=120.0,
            amount=10.0,
            amount_usd=1000.0,
            take_profit_price=120.0,
            stop_loss_price=80.0,
            status=TradeStatus.OPEN,
            opened_at=datetime.utcnow().isoformat(),
        )
        position.tp_order_id = "tp_order_123"
        position.sl_order_id = "sl_order_456"

        mock_engine.positions = {"pos_123": position}
        mock_engine.trade_history = []

        # Mock order manager
        mock_engine.order_manager = AsyncMock()
        mock_engine.order_manager.cancel_order = AsyncMock()

        # Mock jupiter price
        mock_engine.jupiter.get_token_price = AsyncMock(return_value=150.0)

        # Handle TP order fill at exit price $120
        await mock_engine._handle_order_filled(
            order_id="tp_order_123",
            order_type="TAKE_PROFIT",
            token_mint="test_mint",
            exit_price=120.0,
            output_amount=1.0,  # Swapped to SOL
            tx_signature="tx_sig_123"
        )

        # Verify position was closed
        assert "pos_123" not in mock_engine.positions
        assert len(mock_engine.trade_history) == 1

        closed_pos = mock_engine.trade_history[0]
        assert closed_pos.status == TradeStatus.CLOSED
        assert closed_pos.exit_price == 120.0
        assert closed_pos.pnl_pct == pytest.approx(20.0)  # (120-100)/100 = 20%
        assert closed_pos.pnl_usd == pytest.approx(200.0)  # 1000 * 0.20

        # Verify SL order was cancelled
        mock_engine.order_manager.cancel_order.assert_called_once_with("sl_order_456")

    @pytest.mark.asyncio
    async def test_stop_loss_order_filled(self, mock_engine, tmp_path):
        """Test handling SL order fill closes position with loss."""
        mock_engine.STATE_FILE = tmp_path / "state.json"

        position = Position(
            id="pos_456",
            token_mint="test_mint_2",
            token_symbol="LOSS",
            direction=TradeDirection.LONG,
            entry_price=100.0,
            current_price=70.0,
            amount=5.0,
            amount_usd=500.0,
            take_profit_price=120.0,
            stop_loss_price=80.0,
            status=TradeStatus.OPEN,
            opened_at=datetime.utcnow().isoformat(),
        )
        position.tp_order_id = "tp_order_789"
        position.sl_order_id = "sl_order_101"

        mock_engine.positions = {"pos_456": position}
        mock_engine.trade_history = []
        mock_engine.order_manager = AsyncMock()
        mock_engine.order_manager.cancel_order = AsyncMock()
        mock_engine.jupiter.get_token_price = AsyncMock(return_value=150.0)

        # Handle SL order fill at exit price $80
        await mock_engine._handle_order_filled(
            order_id="sl_order_101",
            order_type="STOP_LOSS",
            token_mint="test_mint_2",
            exit_price=80.0,
            output_amount=0.5,
            tx_signature="tx_sig_456"
        )

        # Verify position was closed with loss
        assert "pos_456" not in mock_engine.positions
        closed_pos = mock_engine.trade_history[0]
        assert closed_pos.pnl_pct == pytest.approx(-20.0)  # (80-100)/100 = -20%
        assert closed_pos.pnl_usd == pytest.approx(-100.0)  # 500 * -0.20

        # Verify TP order was cancelled
        mock_engine.order_manager.cancel_order.assert_called_once_with("tp_order_789")

    @pytest.mark.asyncio
    async def test_order_filled_no_matching_position(self, mock_engine, tmp_path):
        """Test order fill when no matching position exists (logs warning)."""
        mock_engine.STATE_FILE = tmp_path / "state.json"
        mock_engine.positions = {}
        mock_engine.trade_history = []

        # Should log warning but not crash
        await mock_engine._handle_order_filled(
            order_id="unknown_order",
            order_type="TAKE_PROFIT",
            token_mint="unknown_mint",
            exit_price=100.0,
            output_amount=1.0,
            tx_signature="tx_sig"
        )

        # No positions should be closed
        assert len(mock_engine.positions) == 0
        assert len(mock_engine.trade_history) == 0

    @pytest.mark.asyncio
    async def test_order_filled_scorekeeper_update(self, mock_engine, tmp_path):
        """Test order fill updates scorekeeper."""
        mock_engine.STATE_FILE = tmp_path / "state.json"

        position = Position(
            id="pos_score",
            token_mint="test_mint",
            token_symbol="TEST",
            direction=TradeDirection.LONG,
            entry_price=100.0,
            current_price=110.0,
            amount=10.0,
            amount_usd=1000.0,
            take_profit_price=120.0,
            stop_loss_price=80.0,
            status=TradeStatus.OPEN,
            opened_at=datetime.utcnow().isoformat(),
        )
        position.tp_order_id = "tp_123"

        mock_engine.positions = {"pos_score": position}
        mock_engine.trade_history = []
        mock_engine.order_manager = None  # No order manager
        mock_engine.jupiter.get_token_price = AsyncMock(return_value=150.0)

        # Mock scorekeeper
        mock_scorekeeper = MagicMock()
        mock_scorekeeper.close_position = MagicMock()

        with patch("bots.treasury.trading.trading_engine.get_scorekeeper", return_value=mock_scorekeeper):
            await mock_engine._handle_order_filled(
                order_id="tp_123",
                order_type="TAKE_PROFIT",
                token_mint="test_mint",
                exit_price=110.0,
                output_amount=1.5,
                tx_signature="tx_sig_score"
            )

        # Verify scorekeeper was called
        mock_scorekeeper.close_position.assert_called_once()
        call_kwargs = mock_scorekeeper.close_position.call_args.kwargs
        assert call_kwargs["position_id"] == "pos_score"
        assert call_kwargs["exit_price"] == 110.0
        assert call_kwargs["close_type"] == "tp"
        assert call_kwargs["tx_signature"] == "tx_sig_score"


# =============================================================================
# Audit Logging Tests (Lines 350-394)
# =============================================================================


class TestAuditLogging:
    """Tests for _log_audit method."""

    @pytest.fixture
    def mock_engine(self):
        """Create a mock trading engine for testing."""
        with patch('bots.treasury.trading.SecureWallet') as MockWallet, \
             patch('bots.treasury.trading.JupiterClient') as MockJupiter:
            wallet = MockWallet.return_value
            jupiter = MockJupiter.return_value
            engine = TradingEngine(
                wallet=wallet,
                jupiter=jupiter,
                risk_level=RiskLevel.MODERATE,
                admin_user_ids=[123456],
            )
            yield engine

    def test_log_audit_creates_file(self, mock_engine, tmp_path):
        """Test audit logging creates file on first log."""
        audit_file = tmp_path / "audit.json"
        mock_engine.AUDIT_LOG_FILE = audit_file

        mock_engine._log_audit("TEST_ACTION", {"key": "value"}, 123456, True)

        assert audit_file.exists()
        with open(audit_file) as f:
            logs = json.load(f)

        assert len(logs) == 1
        assert logs[0]["action"] == "TEST_ACTION"
        assert logs[0]["user_id"] == 123456
        assert logs[0]["success"] is True
        assert logs[0]["details"]["key"] == "value"

    def test_log_audit_appends_to_existing(self, mock_engine, tmp_path):
        """Test audit logging appends to existing log file."""
        audit_file = tmp_path / "audit.json"
        mock_engine.AUDIT_LOG_FILE = audit_file

        # Create initial log
        with open(audit_file, "w") as f:
            json.dump([{"action": "PREVIOUS", "success": True}], f)

        mock_engine._log_audit("NEW_ACTION", {}, None, True)

        with open(audit_file) as f:
            logs = json.load(f)

        assert len(logs) == 2
        assert logs[0]["action"] == "PREVIOUS"
        assert logs[1]["action"] == "NEW_ACTION"

    def test_log_audit_trims_old_entries(self, mock_engine, tmp_path):
        """Test audit log trims to 1000 entries max."""
        audit_file = tmp_path / "audit.json"
        mock_engine.AUDIT_LOG_FILE = audit_file

        # Create 1000 entries
        old_logs = [{"action": f"OLD_{i}", "success": True} for i in range(1000)]
        with open(audit_file, "w") as f:
            json.dump(old_logs, f)

        # Add one more
        mock_engine._log_audit("NEW_ACTION", {}, None, True)

        with open(audit_file) as f:
            logs = json.load(f)

        # Should have exactly 1000 entries (trimmed oldest)
        assert len(logs) == 1000
        assert logs[-1]["action"] == "NEW_ACTION"
        assert logs[0]["action"] == "OLD_1"  # OLD_0 was trimmed

    def test_log_audit_handles_missing_file_gracefully(self, mock_engine, tmp_path):
        """Test audit logging handles missing parent directory."""
        audit_file = tmp_path / "nested" / "path" / "audit.json"
        mock_engine.AUDIT_LOG_FILE = audit_file

        # Should create parent directories
        mock_engine._log_audit("ACTION", {}, None, True)

        assert audit_file.exists()
        assert audit_file.parent.exists()

    def test_log_audit_handles_json_errors(self, mock_engine, tmp_path):
        """Test audit logging handles corrupted JSON gracefully."""
        audit_file = tmp_path / "audit.json"
        mock_engine.AUDIT_LOG_FILE = audit_file

        # Write corrupted JSON
        with open(audit_file, "w") as f:
            f.write("not valid json{")

        # Should not crash, just start fresh log
        mock_engine._log_audit("ACTION", {}, None, True)

        # File should still have valid JSON now (or be handled)
        assert audit_file.exists()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
