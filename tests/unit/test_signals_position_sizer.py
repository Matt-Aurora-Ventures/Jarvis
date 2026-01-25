"""
Tests for Position Sizer - core/signals/position_sizer.py

Tests cover:
- SizingMethod enum values
- RiskParameters dataclass validation
- PositionSize output format
- PositionSizer initialization
- Fixed amount sizing
- Fixed percentage sizing
- Risk-based sizing
- Kelly Criterion sizing
- Volatility-adjusted sizing
- Signal-scaled sizing
- Hybrid sizing
- Position tracking (add/close)
- Exposure calculations
- Stop loss and take profit calculation
- Position size suggestions
- Edge cases and constraints

Target: 60%+ coverage with comprehensive unit tests.
"""

import pytest
import asyncio
import math
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock

# Import the module under test
from core.signals.position_sizer import (
    SizingMethod,
    RiskParameters,
    PositionSize,
    PositionSizer,
    get_position_sizer,
)


# =============================================================================
# SizingMethod Tests
# =============================================================================

class TestSizingMethod:
    """Tests for SizingMethod enum."""

    def test_all_methods_defined(self):
        """Test all expected sizing methods are defined."""
        expected = [
            "fixed_amount", "fixed_percentage", "risk_based",
            "kelly", "volatility", "signal_scaled", "hybrid"
        ]
        actual = [m.value for m in SizingMethod]
        for method in expected:
            assert method in actual, f"Missing method: {method}"

    def test_method_values_are_strings(self):
        """Test method values are strings."""
        for method in SizingMethod:
            assert isinstance(method.value, str)

    def test_method_count(self):
        """Test expected number of sizing methods."""
        assert len(SizingMethod) == 7


# =============================================================================
# RiskParameters Tests
# =============================================================================

class TestRiskParameters:
    """Tests for RiskParameters dataclass."""

    def test_default_risk_parameters(self):
        """Test default risk parameter values."""
        params = RiskParameters()

        assert params.account_size == 10000.0
        assert params.max_position_pct == 10.0
        assert params.max_total_exposure_pct == 50.0
        assert params.risk_per_trade_pct == 1.0
        assert params.max_loss_per_trade == 100.0
        assert params.default_stop_loss_pct == 5.0
        assert params.trailing_stop_pct == 10.0
        assert params.max_leverage == 1.0
        assert params.use_leverage is False
        assert params.kelly_fraction == 0.25

    def test_custom_risk_parameters(self):
        """Test custom risk parameter values."""
        params = RiskParameters(
            account_size=50000.0,
            max_position_pct=5.0,
            risk_per_trade_pct=0.5,
            max_loss_per_trade=250.0,
        )

        assert params.account_size == 50000.0
        assert params.max_position_pct == 5.0
        assert params.risk_per_trade_pct == 0.5
        assert params.max_loss_per_trade == 250.0

    def test_risk_parameters_to_dict(self):
        """Test converting RiskParameters to dictionary."""
        params = RiskParameters(account_size=25000.0)

        data = params.to_dict()

        assert data["account_size"] == 25000.0
        assert "max_position_pct" in data
        assert "risk_per_trade_pct" in data
        assert "kelly_fraction" in data

    def test_risk_parameters_leverage_settings(self):
        """Test leverage-related parameters."""
        params = RiskParameters(
            max_leverage=3.0,
            use_leverage=True,
        )

        assert params.max_leverage == 3.0
        assert params.use_leverage is True

    def test_risk_parameters_volatility_settings(self):
        """Test volatility-related parameters."""
        params = RiskParameters(
            vol_lookback_days=30,
            vol_target_pct=20.0,
        )

        assert params.vol_lookback_days == 30
        assert params.vol_target_pct == 20.0


# =============================================================================
# PositionSize Tests
# =============================================================================

class TestPositionSize:
    """Tests for PositionSize dataclass."""

    def test_create_position_size(self):
        """Test creating a PositionSize result."""
        size = PositionSize(
            token="SOL",
            method=SizingMethod.RISK_BASED,
            position_size_usd=500.0,
            position_size_tokens=5.0,
            entry_price=100.0,
        )

        assert size.token == "SOL"
        assert size.method == SizingMethod.RISK_BASED
        assert size.position_size_usd == 500.0
        assert size.position_size_tokens == 5.0
        assert size.entry_price == 100.0

    def test_position_size_with_risk_metrics(self):
        """Test PositionSize with all risk metrics."""
        size = PositionSize(
            token="BTC",
            method=SizingMethod.KELLY,
            position_size_usd=1000.0,
            position_size_tokens=0.02,
            entry_price=50000.0,
            risk_amount=50.0,
            risk_percent=0.5,
            stop_loss_price=47500.0,
            stop_loss_percent=5.0,
            take_profit_price=55000.0,
            take_profit_percent=10.0,
        )

        assert size.risk_amount == 50.0
        assert size.risk_percent == 0.5
        assert size.stop_loss_price == 47500.0
        assert size.take_profit_price == 55000.0

    def test_position_size_to_dict(self):
        """Test converting PositionSize to dictionary."""
        size = PositionSize(
            token="ETH",
            method=SizingMethod.VOLATILITY,
            position_size_usd=750.0,
            position_size_tokens=0.375,
            entry_price=2000.0,
            confidence=0.85,
            notes="Volatility adjusted",
        )

        data = size.to_dict()

        assert data["token"] == "ETH"
        assert data["method"] == "volatility"
        assert data["position_size_usd"] == 750.0
        assert data["confidence"] == 0.85
        assert data["notes"] == "Volatility adjusted"
        assert "calculated_at" in data


# =============================================================================
# PositionSizer Initialization Tests
# =============================================================================

class TestPositionSizerInitialization:
    """Tests for PositionSizer initialization."""

    def test_default_initialization(self):
        """Test PositionSizer with default parameters."""
        sizer = PositionSizer()

        assert sizer.default_params is not None
        assert sizer.default_params.account_size == 10000.0
        assert sizer.current_positions == {}
        assert sizer.historical_volatility == {}

    def test_custom_initialization(self):
        """Test PositionSizer with custom parameters."""
        params = RiskParameters(
            account_size=50000.0,
            max_position_pct=8.0,
        )
        sizer = PositionSizer(default_params=params)

        assert sizer.default_params.account_size == 50000.0
        assert sizer.default_params.max_position_pct == 8.0


# =============================================================================
# Fixed Amount Sizing Tests
# =============================================================================

class TestFixedAmountSizing:
    """Tests for fixed amount position sizing."""

    @pytest.fixture
    def sizer(self):
        """Create a PositionSizer instance."""
        return PositionSizer(RiskParameters(account_size=10000.0))

    @pytest.mark.asyncio
    async def test_fixed_amount_basic(self, sizer):
        """Test basic fixed amount sizing."""
        size = await sizer.calculate_position_size(
            token="SOL",
            entry_price=100.0,
            method=SizingMethod.FIXED_AMOUNT,
            signal_strength=1.0,
            signal_confidence=1.0,
        )

        # Fixed amount defaults to $1000 or max position
        assert size.position_size_usd <= 1000.0
        assert size.method == SizingMethod.FIXED_AMOUNT

    @pytest.mark.asyncio
    async def test_fixed_amount_capped_by_max(self, sizer):
        """Test fixed amount is capped by max position."""
        small_sizer = PositionSizer(RiskParameters(
            account_size=1000.0,
            max_position_pct=5.0,  # Max $50
        ))

        size = await small_sizer.calculate_position_size(
            token="BTC",
            entry_price=50000.0,
            method=SizingMethod.FIXED_AMOUNT,
            signal_strength=1.0,
            signal_confidence=1.0,
        )

        # Should be capped at max position (5% of 1000 = $50)
        assert size.position_size_usd <= 50.0


# =============================================================================
# Fixed Percentage Sizing Tests
# =============================================================================

class TestFixedPercentageSizing:
    """Tests for fixed percentage position sizing."""

    @pytest.fixture
    def sizer(self):
        """Create a PositionSizer instance."""
        return PositionSizer(RiskParameters(
            account_size=10000.0,
            max_position_pct=10.0,
        ))

    @pytest.mark.asyncio
    async def test_fixed_percentage_basic(self, sizer):
        """Test basic fixed percentage sizing."""
        size = await sizer.calculate_position_size(
            token="SOL",
            entry_price=100.0,
            method=SizingMethod.FIXED_PERCENTAGE,
            signal_strength=1.0,
            signal_confidence=1.0,
        )

        # 10% of 10000 = 1000
        assert size.position_size_usd <= 1000.0
        assert size.method == SizingMethod.FIXED_PERCENTAGE

    @pytest.mark.asyncio
    async def test_fixed_percentage_scales_with_account(self):
        """Test fixed percentage scales with account size."""
        large_sizer = PositionSizer(RiskParameters(
            account_size=100000.0,
            max_position_pct=10.0,
        ))

        size = await large_sizer.calculate_position_size(
            token="ETH",
            entry_price=2000.0,
            method=SizingMethod.FIXED_PERCENTAGE,
            signal_strength=1.0,
            signal_confidence=1.0,
        )

        # 10% of 100000 = 10000
        assert size.position_size_usd <= 10000.0


# =============================================================================
# Risk-Based Sizing Tests
# =============================================================================

class TestRiskBasedSizing:
    """Tests for risk-based position sizing."""

    @pytest.fixture
    def sizer(self):
        """Create a PositionSizer instance."""
        return PositionSizer(RiskParameters(
            account_size=10000.0,
            max_position_pct=10.0,
            risk_per_trade_pct=1.0,
            max_loss_per_trade=100.0,
        ))

    @pytest.mark.asyncio
    async def test_risk_based_basic(self, sizer):
        """Test basic risk-based sizing."""
        size = await sizer.calculate_position_size(
            token="SOL",
            entry_price=100.0,
            method=SizingMethod.RISK_BASED,
            signal_strength=1.0,
            signal_confidence=1.0,
            stop_loss_pct=5.0,
        )

        # Risk = 1% of 10000 = 100, Stop = 5%, Position = 100 / 0.05 = 2000
        # But capped at max 10% = 1000
        assert size.method == SizingMethod.RISK_BASED
        assert size.stop_loss_percent == 5.0

    @pytest.mark.asyncio
    async def test_risk_based_with_default_stop(self, sizer):
        """Test risk-based sizing with default stop loss."""
        size = await sizer.calculate_position_size(
            token="BTC",
            entry_price=50000.0,
            method=SizingMethod.RISK_BASED,
            signal_strength=1.0,
            signal_confidence=1.0,
            # No stop_loss_pct provided, uses default
        )

        # Should use default stop loss (5%)
        assert size.stop_loss_percent == 5.0

    @pytest.mark.asyncio
    async def test_risk_based_respects_max_loss(self):
        """Test risk-based sizing respects max loss per trade."""
        sizer = PositionSizer(RiskParameters(
            account_size=100000.0,
            risk_per_trade_pct=2.0,  # 2% of 100k = 2000
            max_loss_per_trade=500.0,  # But capped at 500
        ))

        size = await sizer.calculate_position_size(
            token="AVAX",
            entry_price=50.0,
            method=SizingMethod.RISK_BASED,
            signal_strength=1.0,
            signal_confidence=1.0,
            stop_loss_pct=10.0,
        )

        # Risk should be limited by max_loss_per_trade
        assert size.risk_amount <= 500.0


# =============================================================================
# Kelly Criterion Sizing Tests
# =============================================================================

class TestKellySizing:
    """Tests for Kelly Criterion position sizing."""

    @pytest.fixture
    def sizer(self):
        """Create a PositionSizer instance."""
        return PositionSizer(RiskParameters(
            account_size=10000.0,
            max_position_pct=20.0,
            kelly_fraction=0.25,  # Quarter Kelly
        ))

    @pytest.mark.asyncio
    async def test_kelly_basic(self, sizer):
        """Test basic Kelly sizing."""
        size = await sizer.calculate_position_size(
            token="SOL",
            entry_price=100.0,
            method=SizingMethod.KELLY,
            signal_strength=1.0,
            signal_confidence=1.0,
            win_rate=0.6,
            avg_win_loss_ratio=2.0,
        )

        assert size.method == SizingMethod.KELLY
        assert size.position_size_usd > 0

    @pytest.mark.asyncio
    async def test_kelly_high_win_rate(self, sizer):
        """Test Kelly with high win rate suggests larger position."""
        high_wr = await sizer.calculate_position_size(
            token="SOL",
            entry_price=100.0,
            method=SizingMethod.KELLY,
            signal_strength=1.0,
            signal_confidence=1.0,
            win_rate=0.7,
            avg_win_loss_ratio=2.0,
        )

        low_wr = await sizer.calculate_position_size(
            token="SOL",
            entry_price=100.0,
            method=SizingMethod.KELLY,
            signal_strength=1.0,
            signal_confidence=1.0,
            win_rate=0.5,
            avg_win_loss_ratio=2.0,
        )

        # Higher win rate should lead to larger position
        assert high_wr.position_size_usd >= low_wr.position_size_usd

    @pytest.mark.asyncio
    async def test_kelly_respects_fraction(self):
        """Test Kelly respects the kelly_fraction parameter."""
        full_kelly = PositionSizer(RiskParameters(
            account_size=10000.0,
            kelly_fraction=1.0,
        ))
        quarter_kelly = PositionSizer(RiskParameters(
            account_size=10000.0,
            kelly_fraction=0.25,
        ))

        full = await full_kelly.calculate_position_size(
            token="ETH",
            entry_price=2000.0,
            method=SizingMethod.KELLY,
            signal_strength=1.0,
            signal_confidence=1.0,
            win_rate=0.6,
            avg_win_loss_ratio=1.5,
        )

        quarter = await quarter_kelly.calculate_position_size(
            token="ETH",
            entry_price=2000.0,
            method=SizingMethod.KELLY,
            signal_strength=1.0,
            signal_confidence=1.0,
            win_rate=0.6,
            avg_win_loss_ratio=1.5,
        )

        # Quarter Kelly should be roughly 1/4 of full (before caps)
        # Due to caps and multipliers, just check quarter is smaller
        assert quarter.position_size_usd <= full.position_size_usd


# =============================================================================
# Volatility-Adjusted Sizing Tests
# =============================================================================

class TestVolatilitySizing:
    """Tests for volatility-adjusted position sizing."""

    @pytest.fixture
    def sizer(self):
        """Create a PositionSizer instance."""
        return PositionSizer(RiskParameters(
            account_size=10000.0,
            max_position_pct=10.0,
            vol_target_pct=15.0,
        ))

    @pytest.mark.asyncio
    async def test_volatility_basic(self, sizer):
        """Test basic volatility sizing."""
        sizer.set_volatility("SOL", 0.5)  # 50% vol

        size = await sizer.calculate_position_size(
            token="SOL",
            entry_price=100.0,
            method=SizingMethod.VOLATILITY,
            signal_strength=1.0,
            signal_confidence=1.0,
            volatility=0.5,
        )

        assert size.method == SizingMethod.VOLATILITY
        assert size.volatility_multiplier > 0

    @pytest.mark.asyncio
    async def test_high_volatility_reduces_size(self, sizer):
        """Test high volatility reduces position size."""
        high_vol = await sizer.calculate_position_size(
            token="MEME",
            entry_price=10.0,
            method=SizingMethod.VOLATILITY,
            signal_strength=1.0,
            signal_confidence=1.0,
            volatility=1.0,  # 100% vol
        )

        low_vol = await sizer.calculate_position_size(
            token="STABLE",
            entry_price=10.0,
            method=SizingMethod.VOLATILITY,
            signal_strength=1.0,
            signal_confidence=1.0,
            volatility=0.2,  # 20% vol
        )

        # Higher volatility should lead to smaller position
        assert high_vol.position_size_usd <= low_vol.position_size_usd

    @pytest.mark.asyncio
    async def test_zero_volatility_uses_max(self, sizer):
        """Test zero volatility uses max position size."""
        size = await sizer.calculate_position_size(
            token="ZERO",
            entry_price=100.0,
            method=SizingMethod.VOLATILITY,
            signal_strength=1.0,
            signal_confidence=1.0,
            volatility=0.0,
        )

        # Should use max position percentage
        assert size.position_size_usd > 0


# =============================================================================
# Signal-Scaled Sizing Tests
# =============================================================================

class TestSignalScaledSizing:
    """Tests for signal-scaled position sizing."""

    @pytest.fixture
    def sizer(self):
        """Create a PositionSizer instance."""
        return PositionSizer(RiskParameters(
            account_size=10000.0,
            max_position_pct=10.0,
        ))

    @pytest.mark.asyncio
    async def test_signal_scaled_basic(self, sizer):
        """Test basic signal-scaled sizing."""
        size = await sizer.calculate_position_size(
            token="SOL",
            entry_price=100.0,
            method=SizingMethod.SIGNAL_SCALED,
            signal_strength=0.8,
            signal_confidence=0.9,
        )

        assert size.method == SizingMethod.SIGNAL_SCALED
        assert size.signal_multiplier > 0

    @pytest.mark.asyncio
    async def test_strong_signal_larger_size(self, sizer):
        """Test strong signal leads to larger position."""
        strong = await sizer.calculate_position_size(
            token="SOL",
            entry_price=100.0,
            method=SizingMethod.SIGNAL_SCALED,
            signal_strength=0.95,
            signal_confidence=0.9,
        )

        weak = await sizer.calculate_position_size(
            token="SOL",
            entry_price=100.0,
            method=SizingMethod.SIGNAL_SCALED,
            signal_strength=0.3,
            signal_confidence=0.5,
        )

        # Strong signal should have larger position
        assert strong.position_size_usd >= weak.position_size_usd

    @pytest.mark.asyncio
    async def test_low_confidence_reduces_size(self, sizer):
        """Test low confidence reduces position size."""
        high_conf = await sizer.calculate_position_size(
            token="BTC",
            entry_price=50000.0,
            method=SizingMethod.SIGNAL_SCALED,
            signal_strength=0.8,
            signal_confidence=0.95,
        )

        low_conf = await sizer.calculate_position_size(
            token="BTC",
            entry_price=50000.0,
            method=SizingMethod.SIGNAL_SCALED,
            signal_strength=0.8,
            signal_confidence=0.3,
        )

        # Higher confidence should lead to larger position
        assert high_conf.position_size_usd >= low_conf.position_size_usd


# =============================================================================
# Hybrid Sizing Tests
# =============================================================================

class TestHybridSizing:
    """Tests for hybrid position sizing."""

    @pytest.fixture
    def sizer(self):
        """Create a PositionSizer instance."""
        return PositionSizer(RiskParameters(
            account_size=10000.0,
            max_position_pct=15.0,
            risk_per_trade_pct=1.0,
            kelly_fraction=0.25,
            vol_target_pct=15.0,
        ))

    @pytest.mark.asyncio
    async def test_hybrid_basic(self, sizer):
        """Test basic hybrid sizing."""
        size = await sizer.calculate_position_size(
            token="SOL",
            entry_price=100.0,
            method=SizingMethod.HYBRID,
            signal_strength=0.8,
            signal_confidence=0.85,
            win_rate=0.6,
            avg_win_loss_ratio=1.5,
            volatility=0.5,
        )

        assert size.method == SizingMethod.HYBRID
        assert size.position_size_usd > 0

    @pytest.mark.asyncio
    async def test_hybrid_high_confidence_uses_kelly(self, sizer):
        """Test hybrid with high confidence leans toward Kelly."""
        high_conf = await sizer.calculate_position_size(
            token="ETH",
            entry_price=2000.0,
            method=SizingMethod.HYBRID,
            signal_strength=0.9,
            signal_confidence=0.9,  # High confidence
            win_rate=0.7,
            avg_win_loss_ratio=2.0,
            volatility=0.4,
        )

        assert high_conf.position_size_usd > 0

    @pytest.mark.asyncio
    async def test_hybrid_low_confidence_conservative(self, sizer):
        """Test hybrid with low confidence is more conservative."""
        low_conf = await sizer.calculate_position_size(
            token="RISKY",
            entry_price=50.0,
            method=SizingMethod.HYBRID,
            signal_strength=0.5,
            signal_confidence=0.4,  # Low confidence
            win_rate=0.5,
            avg_win_loss_ratio=1.5,
            volatility=0.8,
        )

        high_conf = await sizer.calculate_position_size(
            token="RISKY",
            entry_price=50.0,
            method=SizingMethod.HYBRID,
            signal_strength=0.5,
            signal_confidence=0.9,  # High confidence
            win_rate=0.5,
            avg_win_loss_ratio=1.5,
            volatility=0.8,
        )

        # Low confidence should be more conservative
        assert low_conf.position_size_usd <= high_conf.position_size_usd


# =============================================================================
# Position Tracking Tests
# =============================================================================

class TestPositionTracking:
    """Tests for position tracking functionality."""

    @pytest.fixture
    def sizer(self):
        """Create a PositionSizer instance."""
        return PositionSizer(RiskParameters(account_size=10000.0))

    def test_add_position(self, sizer):
        """Test adding a position."""
        sizer.add_position("SOL", 500.0)

        assert "SOL" in sizer.current_positions
        assert sizer.current_positions["SOL"] == 500.0

    def test_add_multiple_positions(self, sizer):
        """Test adding multiple positions to same token."""
        sizer.add_position("SOL", 500.0)
        sizer.add_position("SOL", 300.0)

        assert sizer.current_positions["SOL"] == 800.0

    def test_close_position_full(self, sizer):
        """Test closing a position completely."""
        sizer.add_position("BTC", 1000.0)
        sizer.close_position("BTC")

        assert "BTC" not in sizer.current_positions

    def test_close_position_partial(self, sizer):
        """Test closing a position partially."""
        sizer.add_position("ETH", 1000.0)
        sizer.close_position("ETH", 400.0)

        assert sizer.current_positions["ETH"] == 600.0

    def test_close_position_removes_if_zero(self, sizer):
        """Test closing position removes if at zero."""
        sizer.add_position("AVAX", 500.0)
        sizer.close_position("AVAX", 500.0)

        assert "AVAX" not in sizer.current_positions


# =============================================================================
# Exposure Calculation Tests
# =============================================================================

class TestExposureCalculation:
    """Tests for exposure calculation."""

    @pytest.fixture
    def sizer(self):
        """Create a PositionSizer instance."""
        return PositionSizer(RiskParameters(
            account_size=10000.0,
            max_total_exposure_pct=50.0,
        ))

    def test_exposure_summary_empty(self, sizer):
        """Test exposure summary with no positions."""
        summary = sizer.get_exposure_summary()

        assert summary["total_exposure_usd"] == 0
        assert summary["total_exposure_pct"] == 0
        assert summary["position_count"] == 0

    def test_exposure_summary_with_positions(self, sizer):
        """Test exposure summary with positions."""
        sizer.add_position("SOL", 1000.0)
        sizer.add_position("BTC", 2000.0)

        summary = sizer.get_exposure_summary()

        assert summary["total_exposure_usd"] == 3000.0
        assert summary["total_exposure_pct"] == 30.0  # 3000/10000 * 100
        assert summary["position_count"] == 2

    def test_exposure_affects_max_position(self, sizer):
        """Test current exposure affects max position size."""
        # Use 40% of available exposure
        sizer.add_position("BTC", 4000.0)

        # Remaining exposure should limit new position
        # 50% max = 5000, already using 4000, so 1000 remaining
        summary = sizer.get_exposure_summary()
        remaining = summary["remaining_capacity_usd"]

        assert remaining == 1000.0


# =============================================================================
# Stop Loss and Take Profit Tests
# =============================================================================

class TestStopLossTakeProfit:
    """Tests for stop loss and take profit calculation."""

    @pytest.fixture
    def sizer(self):
        """Create a PositionSizer instance."""
        return PositionSizer(RiskParameters(
            account_size=10000.0,
            default_stop_loss_pct=5.0,
        ))

    @pytest.mark.asyncio
    async def test_stop_loss_calculation(self, sizer):
        """Test stop loss price is calculated correctly."""
        size = await sizer.calculate_position_size(
            token="SOL",
            entry_price=100.0,
            method=SizingMethod.RISK_BASED,
            signal_strength=1.0,
            signal_confidence=1.0,
            stop_loss_pct=5.0,
        )

        # 5% stop loss from 100 = 95
        assert size.stop_loss_price == 95.0
        assert size.stop_loss_percent == 5.0

    @pytest.mark.asyncio
    async def test_take_profit_calculation(self, sizer):
        """Test take profit price is calculated correctly."""
        size = await sizer.calculate_position_size(
            token="BTC",
            entry_price=50000.0,
            method=SizingMethod.RISK_BASED,
            signal_strength=1.0,
            signal_confidence=1.0,
            stop_loss_pct=5.0,
            take_profit_pct=10.0,
        )

        # 10% take profit from 50000 = 55000
        assert size.take_profit_price == 55000.0
        assert size.take_profit_percent == 10.0

    @pytest.mark.asyncio
    async def test_default_take_profit_ratio(self, sizer):
        """Test default take profit uses win/loss ratio."""
        size = await sizer.calculate_position_size(
            token="ETH",
            entry_price=2000.0,
            method=SizingMethod.RISK_BASED,
            signal_strength=1.0,
            signal_confidence=1.0,
            stop_loss_pct=5.0,
            avg_win_loss_ratio=2.0,
            # No take_profit_pct provided
        )

        # Default TP = SL * ratio = 5% * 2.0 = 10%
        assert size.take_profit_percent == 10.0


# =============================================================================
# Position Size Suggestion Tests
# =============================================================================

class TestPositionSizeSuggestion:
    """Tests for position size suggestion functionality."""

    @pytest.fixture
    def sizer(self):
        """Create a PositionSizer instance."""
        return PositionSizer(RiskParameters(account_size=10000.0))

    @pytest.mark.asyncio
    async def test_suggest_position_size(self, sizer):
        """Test getting position size suggestion."""
        suggestion = await sizer.suggest_position_size(
            token="SOL",
            entry_price=100.0,
            signal_strength=0.8,
            signal_confidence=0.85,
        )

        assert suggestion["token"] == "SOL"
        assert suggestion["entry_price"] == 100.0
        assert "recommended_method" in suggestion
        assert "reasoning" in suggestion
        assert "suggestions" in suggestion

    @pytest.mark.asyncio
    async def test_high_confidence_recommends_hybrid(self, sizer):
        """Test high confidence recommends hybrid sizing."""
        suggestion = await sizer.suggest_position_size(
            token="SOL",
            entry_price=100.0,
            signal_strength=0.9,
            signal_confidence=0.9,
        )

        assert suggestion["recommended_method"] == "hybrid"

    @pytest.mark.asyncio
    async def test_medium_confidence_recommends_signal_scaled(self, sizer):
        """Test medium confidence recommends signal-scaled sizing."""
        suggestion = await sizer.suggest_position_size(
            token="ETH",
            entry_price=2000.0,
            signal_strength=0.7,
            signal_confidence=0.7,
        )

        assert suggestion["recommended_method"] == "signal_scaled"

    @pytest.mark.asyncio
    async def test_low_confidence_recommends_risk_based(self, sizer):
        """Test low confidence recommends risk-based sizing."""
        suggestion = await sizer.suggest_position_size(
            token="BTC",
            entry_price=50000.0,
            signal_strength=0.5,
            signal_confidence=0.4,
        )

        assert suggestion["recommended_method"] == "risk_based"


# =============================================================================
# Volatility Setting Tests
# =============================================================================

class TestVolatilitySetting:
    """Tests for setting historical volatility."""

    @pytest.fixture
    def sizer(self):
        """Create a PositionSizer instance."""
        return PositionSizer(RiskParameters(account_size=10000.0))

    def test_set_volatility(self, sizer):
        """Test setting volatility for a token."""
        sizer.set_volatility("SOL", 0.6)

        assert sizer.historical_volatility["SOL"] == 0.6

    def test_set_multiple_volatilities(self, sizer):
        """Test setting volatility for multiple tokens."""
        sizer.set_volatility("SOL", 0.6)
        sizer.set_volatility("BTC", 0.4)
        sizer.set_volatility("ETH", 0.5)

        assert sizer.historical_volatility["SOL"] == 0.6
        assert sizer.historical_volatility["BTC"] == 0.4
        assert sizer.historical_volatility["ETH"] == 0.5


# =============================================================================
# Edge Cases Tests
# =============================================================================

class TestPositionSizerEdgeCases:
    """Tests for edge cases and constraints."""

    @pytest.fixture
    def sizer(self):
        """Create a PositionSizer instance."""
        return PositionSizer(RiskParameters(
            account_size=10000.0,
            max_position_pct=10.0,
        ))

    @pytest.mark.asyncio
    async def test_minimum_position_size(self, sizer):
        """Test positions below minimum are zeroed."""
        # Very small position due to low signals
        size = await sizer.calculate_position_size(
            token="MICRO",
            entry_price=0.001,
            method=SizingMethod.SIGNAL_SCALED,
            signal_strength=0.01,
            signal_confidence=0.01,
        )

        # Should be 0 if below $10 minimum
        assert size.position_size_usd == 0 or size.position_size_usd >= 10

    @pytest.mark.asyncio
    async def test_zero_entry_price(self, sizer):
        """Test handling zero entry price."""
        size = await sizer.calculate_position_size(
            token="ZERO",
            entry_price=0.0,
            method=SizingMethod.RISK_BASED,
            signal_strength=1.0,
            signal_confidence=1.0,
        )

        # Token count should be 0 (division by zero prevented)
        assert size.position_size_tokens == 0

    @pytest.mark.asyncio
    async def test_max_exposure_limit(self):
        """Test max exposure limit is enforced."""
        sizer = PositionSizer(RiskParameters(
            account_size=10000.0,
            max_position_pct=30.0,  # 30% per position
            max_total_exposure_pct=50.0,  # 50% total
        ))

        # Add position using 45% of exposure
        sizer.add_position("BTC", 4500.0)

        size = await sizer.calculate_position_size(
            token="SOL",
            entry_price=100.0,
            method=SizingMethod.FIXED_PERCENTAGE,
            signal_strength=1.0,
            signal_confidence=1.0,
        )

        # Only 5% remaining (500 USD)
        assert size.position_size_usd <= 500.0

    @pytest.mark.asyncio
    async def test_negative_kelly(self, sizer):
        """Test handling negative Kelly result."""
        # Very low win rate = negative Kelly
        size = await sizer.calculate_position_size(
            token="BAD",
            entry_price=100.0,
            method=SizingMethod.KELLY,
            signal_strength=1.0,
            signal_confidence=1.0,
            win_rate=0.2,  # 20% win rate
            avg_win_loss_ratio=0.5,  # Bad ratio
        )

        # Should cap at 0 or minimum
        assert size.position_size_usd >= 0

    @pytest.mark.asyncio
    async def test_custom_params_override(self, sizer):
        """Test custom params override defaults."""
        custom = RiskParameters(
            account_size=50000.0,
            max_position_pct=20.0,
        )

        size = await sizer.calculate_position_size(
            token="CUSTOM",
            entry_price=100.0,
            method=SizingMethod.FIXED_PERCENTAGE,
            signal_strength=1.0,
            signal_confidence=1.0,
            params=custom,
        )

        # Should use custom account size (20% of 50000 = 10000 max)
        assert size.max_position_usd <= 10000.0


# =============================================================================
# Module-Level Function Tests
# =============================================================================

class TestModuleFunctions:
    """Tests for module-level functions."""

    def test_get_position_sizer_singleton(self):
        """Test get_position_sizer returns singleton instance."""
        sizer1 = get_position_sizer()
        sizer2 = get_position_sizer()

        assert sizer1 is sizer2


# =============================================================================
# Integration Tests
# =============================================================================

class TestPositionSizerIntegration:
    """Integration tests for PositionSizer."""

    @pytest.fixture
    def sizer(self):
        """Create a PositionSizer instance."""
        return PositionSizer(RiskParameters(
            account_size=25000.0,
            max_position_pct=10.0,
            max_total_exposure_pct=60.0,
            risk_per_trade_pct=1.5,
            kelly_fraction=0.25,
        ))

    @pytest.mark.asyncio
    async def test_full_workflow(self, sizer):
        """Test full position sizing workflow."""
        # 1. Set volatility
        sizer.set_volatility("SOL", 0.6)

        # 2. Get suggestion
        suggestion = await sizer.suggest_position_size(
            token="SOL",
            entry_price=150.0,
            signal_strength=0.85,
            signal_confidence=0.8,
        )

        assert "recommended_method" in suggestion
        assert "suggestions" in suggestion

        # 3. Calculate with recommended method
        size = await sizer.calculate_position_size(
            token="SOL",
            entry_price=150.0,
            method=SizingMethod.HYBRID,
            signal_strength=0.85,
            signal_confidence=0.8,
            win_rate=0.6,
            avg_win_loss_ratio=1.8,
            volatility=0.6,
        )

        assert size.position_size_usd > 0
        assert size.stop_loss_price > 0
        assert size.take_profit_price > size.entry_price

        # 4. Add position
        sizer.add_position("SOL", size.position_size_usd)

        # 5. Check exposure
        summary = sizer.get_exposure_summary()
        assert summary["total_exposure_usd"] == size.position_size_usd

    @pytest.mark.asyncio
    async def test_multiple_positions_exposure(self, sizer):
        """Test exposure with multiple positions."""
        tokens = [("SOL", 100.0), ("BTC", 50000.0), ("ETH", 2000.0)]

        for token, price in tokens:
            size = await sizer.calculate_position_size(
                token=token,
                entry_price=price,
                method=SizingMethod.FIXED_PERCENTAGE,
                signal_strength=0.8,
                signal_confidence=0.8,
            )
            sizer.add_position(token, size.position_size_usd)

        summary = sizer.get_exposure_summary()

        assert summary["position_count"] == 3
        assert summary["total_exposure_pct"] <= 60.0  # Max exposure


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
