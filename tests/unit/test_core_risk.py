"""
Tests for core/risk.py - Risk Management Module

This module tests:
- PositionSizer: Position sizing calculations
- RiskScorer: Token risk scoring
- PortfolioRiskManager: Portfolio-level risk management
- Singleton accessor functions
"""

import pytest
import math
from unittest.mock import patch, MagicMock

from core.risk_scoring import (
    RiskLevel,
    RiskAssessment,
    PositionSizer,
    RiskScorer,
    PortfolioRiskManager,
    get_position_sizer,
    get_risk_scorer,
    get_portfolio_risk_manager,
)


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def position_sizer():
    """Create a fresh PositionSizer instance."""
    return PositionSizer(portfolio_value=10000)


@pytest.fixture
def custom_sizer():
    """Create PositionSizer with custom parameters."""
    return PositionSizer(
        portfolio_value=50000,
        max_position_percent=15.0,
        max_risk_per_trade_percent=3.0,
        max_total_risk_percent=25.0
    )


@pytest.fixture
def risk_scorer():
    """Create a fresh RiskScorer instance."""
    return RiskScorer()


@pytest.fixture
def portfolio_manager():
    """Create a fresh PortfolioRiskManager instance."""
    return PortfolioRiskManager()


@pytest.fixture
def custom_portfolio_manager():
    """Create PortfolioRiskManager with custom parameters."""
    return PortfolioRiskManager(
        max_portfolio_risk=25.0,
        max_single_position=15.0,
        max_correlated_exposure=40.0
    )


# =============================================================================
# RiskLevel Enum Tests
# =============================================================================

class TestRiskLevel:
    """Test RiskLevel enum values."""

    def test_risk_level_values(self):
        """Test all risk level values are defined."""
        assert RiskLevel.VERY_LOW.value == "very_low"
        assert RiskLevel.LOW.value == "low"
        assert RiskLevel.MEDIUM.value == "medium"
        assert RiskLevel.HIGH.value == "high"
        assert RiskLevel.VERY_HIGH.value == "very_high"
        assert RiskLevel.EXTREME.value == "extreme"

    def test_risk_level_count(self):
        """Test there are exactly 6 risk levels."""
        assert len(RiskLevel) == 6


# =============================================================================
# RiskAssessment Dataclass Tests
# =============================================================================

class TestRiskAssessment:
    """Test RiskAssessment dataclass."""

    def test_create_risk_assessment(self):
        """Test creating a RiskAssessment."""
        assessment = RiskAssessment(
            overall_score=45.5,
            level=RiskLevel.MEDIUM,
            factors={"liquidity": 30, "volatility": 60},
            warnings=["Low liquidity"],
            recommendations=["Use smaller position"]
        )
        assert assessment.overall_score == 45.5
        assert assessment.level == RiskLevel.MEDIUM
        assert len(assessment.factors) == 2
        assert len(assessment.warnings) == 1
        assert len(assessment.recommendations) == 1

    def test_risk_assessment_empty_lists(self):
        """Test RiskAssessment with empty lists."""
        assessment = RiskAssessment(
            overall_score=20.0,
            level=RiskLevel.LOW,
            factors={},
            warnings=[],
            recommendations=[]
        )
        assert assessment.warnings == []
        assert assessment.recommendations == []


# =============================================================================
# PositionSizer Tests - Fixed Risk Position Sizing
# =============================================================================

class TestPositionSizerFixedRisk:
    """Test fixed percentage risk position sizing."""

    def test_basic_position_calculation(self, position_sizer):
        """Test basic position size calculation."""
        result = position_sizer.calculate_position_fixed_risk(
            entry_price=100.0,
            stop_loss=90.0,
            risk_percent=2.0
        )
        # Risk amount = 10000 * 0.02 = 200
        # Risk per share = 100 - 90 = 10
        # Raw position size = 200 / 10 = 20 shares
        # BUT max_position_value = 10000 * 0.10 = 1000, so max 10 shares
        # Position is capped at max position limit
        assert result["position_size"] == 10.0
        assert result["position_value"] == 1000.0
        # Actual risk = 10 shares * $10 risk per share = $100
        assert result["risk_amount"] == 100.0
        assert result["risk_percent"] == 1.0  # 100 / 10000 * 100

    def test_stop_loss_distance_calculation(self, position_sizer):
        """Test stop loss distance percentage calculation."""
        result = position_sizer.calculate_position_fixed_risk(
            entry_price=100.0,
            stop_loss=95.0,
            risk_percent=1.0
        )
        # Stop loss distance = (100 - 95) / 100 * 100 = 5%
        assert result["stop_loss_distance_percent"] == 5.0

    def test_default_risk_percent_used(self, position_sizer):
        """Test default risk percent is used when not specified."""
        result = position_sizer.calculate_position_fixed_risk(
            entry_price=100.0,
            stop_loss=95.0
        )
        # Default is max_risk_per_trade = 2%
        # Risk = 10000 * 0.02 = 200, risk per share = 5
        # Raw position = 40 shares at $100 = $4000
        # Max position = 10000 * 0.10 = $1000 = 10 shares
        # Actual risk = 10 * 5 = 50, risk_percent = 50/10000*100 = 0.5%
        assert result["risk_percent"] == 0.5

    def test_stop_loss_equals_entry_error(self, position_sizer):
        """Test error when stop loss equals entry price."""
        result = position_sizer.calculate_position_fixed_risk(
            entry_price=100.0,
            stop_loss=100.0,
            risk_percent=2.0
        )
        assert result["position_size"] == 0
        assert result["position_value"] == 0
        assert result["risk_amount"] == 0
        assert "error" in result
        assert result["error"] == "Stop loss equals entry price"

    def test_max_position_limit_applied(self, position_sizer):
        """Test maximum position limit is enforced."""
        # With tight stop loss, position would be very large without limit
        result = position_sizer.calculate_position_fixed_risk(
            entry_price=100.0,
            stop_loss=99.0,  # Only $1 risk per share
            risk_percent=2.0
        )
        # Risk amount = 200, risk per share = 1, raw position = 200 shares
        # But max position = 10000 * 0.10 = 1000 value, 10 shares max
        assert result["position_size"] == 10.0
        assert result["position_value"] == 1000.0

    def test_short_position_stop_above_entry(self, position_sizer):
        """Test position sizing for short positions (stop above entry)."""
        result = position_sizer.calculate_position_fixed_risk(
            entry_price=100.0,
            stop_loss=110.0,  # Stop above entry for short
            risk_percent=2.0
        )
        # Risk per share = abs(100 - 110) = 10
        # Raw position = 200 / 10 = 20 shares
        # Max position = 1000 / 100 = 10 shares (limited by max_position_percent)
        # Actual risk = 10 * 10 = 100
        assert result["position_size"] == 10.0
        assert result["risk_amount"] == 100.0

    def test_very_tight_stop_loss(self, position_sizer):
        """Test with very tight stop loss hitting position limits."""
        result = position_sizer.calculate_position_fixed_risk(
            entry_price=100.0,
            stop_loss=99.9,  # Very tight stop
            risk_percent=2.0
        )
        # Would require huge position, limited by max_position_percent
        max_position_value = 10000 * 0.10  # 1000
        assert result["position_value"] == max_position_value

    def test_wide_stop_loss(self, position_sizer):
        """Test with wide stop loss."""
        result = position_sizer.calculate_position_fixed_risk(
            entry_price=100.0,
            stop_loss=50.0,  # 50% stop
            risk_percent=2.0
        )
        # Risk per share = 50, risk amount = 200
        # Position size = 200 / 50 = 4 shares
        assert result["position_size"] == 4.0
        assert result["position_value"] == 400.0

    def test_custom_sizer_parameters(self, custom_sizer):
        """Test position sizing with custom parameters."""
        result = custom_sizer.calculate_position_fixed_risk(
            entry_price=100.0,
            stop_loss=90.0
        )
        # Default risk = 3%, portfolio = 50000
        # Risk amount = 50000 * 0.03 = 1500
        # Raw position size = 1500 / 10 = 150 shares ($15000)
        # Max position = 50000 * 0.15 = 7500, so max 75 shares
        # Actual risk = 75 * 10 = 750, risk_percent = 750/50000*100 = 1.5%
        assert result["position_size"] == 75.0
        assert result["risk_percent"] == 1.5


# =============================================================================
# PositionSizer Tests - Kelly Criterion
# =============================================================================

class TestPositionSizerKelly:
    """Test Kelly Criterion position sizing."""

    def test_kelly_with_edge(self, position_sizer):
        """Test Kelly with profitable edge."""
        result = position_sizer.calculate_kelly_position(
            win_rate=0.6,
            avg_win=2.0,
            avg_loss=1.0,
            fraction=0.25
        )
        # b = 2.0/1.0 = 2, p = 0.6, q = 0.4
        # Kelly = (2*0.6 - 0.4) / 2 = (1.2 - 0.4) / 2 = 0.4
        # Fractional = 0.4 * 0.25 = 0.1 = 10%
        assert result["kelly_percent"] == pytest.approx(10.0, rel=0.01)
        assert result["recommended_value"] == pytest.approx(1000.0, rel=0.01)

    def test_kelly_with_no_edge(self, position_sizer):
        """Test Kelly with no edge (50/50 at 1:1)."""
        result = position_sizer.calculate_kelly_position(
            win_rate=0.5,
            avg_win=1.0,
            avg_loss=1.0,
            fraction=0.25
        )
        # b = 1, p = 0.5, q = 0.5
        # Kelly = (1*0.5 - 0.5) / 1 = 0
        assert result["kelly_percent"] == 0.0

    def test_kelly_with_negative_edge(self, position_sizer):
        """Test Kelly with negative edge (losing strategy)."""
        result = position_sizer.calculate_kelly_position(
            win_rate=0.3,
            avg_win=1.0,
            avg_loss=1.0,
            fraction=0.25
        )
        # b = 1, p = 0.3, q = 0.7
        # Kelly = (1*0.3 - 0.7) / 1 = -0.4 -> clamped to 0
        assert result["kelly_percent"] == 0.0
        assert result["recommended_value"] == 0.0

    def test_kelly_clamped_to_max_position(self, position_sizer):
        """Test Kelly is clamped to max position percent."""
        result = position_sizer.calculate_kelly_position(
            win_rate=0.8,
            avg_win=5.0,
            avg_loss=1.0,
            fraction=1.0  # Full Kelly
        )
        # This would suggest very large position, should be clamped
        assert result["kelly_percent"] <= position_sizer.max_position_percent

    def test_kelly_with_zero_avg_loss(self, position_sizer):
        """Test Kelly with zero average loss returns error."""
        result = position_sizer.calculate_kelly_position(
            win_rate=0.6,
            avg_win=2.0,
            avg_loss=0.0,  # Division by zero
            fraction=0.25
        )
        assert result["kelly_percent"] == 0
        assert "error" in result
        assert result["error"] == "avg_loss is zero"

    def test_kelly_full_kelly_calculated(self, position_sizer):
        """Test full Kelly is returned in results."""
        result = position_sizer.calculate_kelly_position(
            win_rate=0.6,
            avg_win=2.0,
            avg_loss=1.0,
            fraction=0.25
        )
        # Full Kelly = 40%, quarter Kelly = 10%
        assert result["full_kelly_percent"] == pytest.approx(40.0, rel=0.01)

    def test_kelly_with_zero_fraction(self, position_sizer):
        """Test Kelly with zero fraction."""
        result = position_sizer.calculate_kelly_position(
            win_rate=0.6,
            avg_win=2.0,
            avg_loss=1.0,
            fraction=0.0
        )
        assert result["kelly_percent"] == 0.0
        assert result["full_kelly_percent"] == 0.0


# =============================================================================
# PositionSizer Tests - Volatility Adjusted
# =============================================================================

class TestPositionSizerVolatility:
    """Test volatility-adjusted (ATR-based) position sizing."""

    def test_volatility_adjusted_basic(self, position_sizer):
        """Test basic volatility-adjusted position size."""
        result = position_sizer.calculate_volatility_adjusted(
            entry_price=100.0,
            atr=5.0,
            atr_multiplier=2.0,
            risk_percent=2.0
        )
        # Stop distance = 5 * 2 = 10
        # Stop loss = 100 - 10 = 90
        # Same as fixed risk with 90 stop (capped by max position)
        assert result["position_size"] == 10.0
        assert result["risk_amount"] == 100.0

    def test_volatility_adjusted_high_volatility(self, position_sizer):
        """Test with high volatility (large ATR)."""
        result = position_sizer.calculate_volatility_adjusted(
            entry_price=100.0,
            atr=20.0,  # High volatility
            atr_multiplier=2.0,
            risk_percent=2.0
        )
        # Stop distance = 40, stop loss = 60
        # Risk per share = 40
        # Position size = 200 / 40 = 5
        assert result["position_size"] == 5.0
        assert result["position_value"] == 500.0

    def test_volatility_adjusted_low_volatility(self, position_sizer):
        """Test with low volatility (small ATR)."""
        result = position_sizer.calculate_volatility_adjusted(
            entry_price=100.0,
            atr=1.0,  # Low volatility
            atr_multiplier=2.0,
            risk_percent=2.0
        )
        # Stop distance = 2, stop loss = 98
        # Risk per share = 2
        # Position size = 200 / 2 = 100, but limited by max position
        max_position = 10000 * 0.10 / 100  # 10 shares
        assert result["position_size"] == max_position

    def test_volatility_adjusted_default_risk(self, position_sizer):
        """Test volatility adjusted uses default risk when not specified."""
        result = position_sizer.calculate_volatility_adjusted(
            entry_price=100.0,
            atr=5.0,
            atr_multiplier=2.0
        )
        # Position is capped at max_position (10%), so actual risk is 1%
        assert result["risk_percent"] == 1.0


# =============================================================================
# PositionSizer Tests - Portfolio Value Update
# =============================================================================

class TestPositionSizerPortfolioUpdate:
    """Test portfolio value updates."""

    def test_update_portfolio_value(self, position_sizer):
        """Test updating portfolio value."""
        position_sizer.update_portfolio_value(20000)
        assert position_sizer.portfolio_value == 20000

        result = position_sizer.calculate_position_fixed_risk(
            entry_price=100.0,
            stop_loss=90.0,
            risk_percent=2.0
        )
        # Risk = 20000 * 0.02 = 400
        # Raw position size = 400 / 10 = 40 shares ($4000)
        # Max position = 20000 * 0.10 = 2000, so max 20 shares
        assert result["position_size"] == 20.0

    def test_update_to_zero_portfolio(self, position_sizer):
        """Test updating to zero portfolio value."""
        position_sizer.update_portfolio_value(0)
        result = position_sizer.calculate_position_fixed_risk(
            entry_price=100.0,
            stop_loss=90.0,
            risk_percent=2.0
        )
        assert result["position_size"] == 0.0
        assert result["risk_amount"] == 0.0


# =============================================================================
# RiskScorer Tests - Token Scoring
# =============================================================================

class TestRiskScorerTokenScoring:
    """Test token risk scoring."""

    def test_low_risk_token(self, risk_scorer):
        """Test scoring a low-risk token."""
        assessment = risk_scorer.score_token(
            market_cap=50_000_000,
            liquidity=5_000_000,
            volume_24h=10_000_000,  # 20% of market cap - healthy volume
            price_change_24h=5.0,
            buy_sell_ratio=2.0,
            token_age_days=180,
            holders=10000
        )
        assert assessment.overall_score < 35
        assert assessment.level in [RiskLevel.VERY_LOW, RiskLevel.LOW]
        assert len(assessment.warnings) == 0

    def test_high_risk_token(self, risk_scorer):
        """Test scoring a high-risk token."""
        assessment = risk_scorer.score_token(
            market_cap=5000,
            liquidity=500,
            volume_24h=1000,
            price_change_24h=150.0,
            buy_sell_ratio=0.2,
            token_age_days=0,
            holders=50
        )
        assert assessment.overall_score >= 65
        assert assessment.level in [RiskLevel.VERY_HIGH, RiskLevel.EXTREME]
        assert len(assessment.warnings) > 0

    def test_extreme_risk_token(self, risk_scorer):
        """Test scoring an extreme risk token."""
        assessment = risk_scorer.score_token(
            market_cap=1000,
            liquidity=100,
            volume_24h=10000,  # 10x market cap - suspicious
            price_change_24h=600.0,  # Massive pump
            buy_sell_ratio=0.1,  # Heavy selling
            token_age_days=0,
            holders=20
        )
        assert assessment.overall_score >= 80
        assert assessment.level == RiskLevel.EXTREME
        assert "Avoid this token" in assessment.recommendations[0]


# =============================================================================
# RiskScorer Tests - Individual Factors
# =============================================================================

class TestRiskScorerFactors:
    """Test individual risk scoring factors."""

    def test_liquidity_extreme_low(self, risk_scorer):
        """Test extreme low liquidity scoring."""
        assessment = risk_scorer.score_token(
            market_cap=100000,
            liquidity=500,  # < 1000
            volume_24h=10000,
            price_change_24h=5.0,
            buy_sell_ratio=1.0
        )
        assert assessment.factors["liquidity"] == 100
        assert any("Extremely low liquidity" in w for w in assessment.warnings)

    def test_liquidity_low(self, risk_scorer):
        """Test low liquidity scoring."""
        assessment = risk_scorer.score_token(
            market_cap=100000,
            liquidity=5000,  # 1000 < x < 10000
            volume_24h=10000,
            price_change_24h=5.0,
            buy_sell_ratio=1.0
        )
        assert assessment.factors["liquidity"] == 80

    def test_liquidity_medium(self, risk_scorer):
        """Test medium liquidity scoring."""
        assessment = risk_scorer.score_token(
            market_cap=100000,
            liquidity=50000,  # 10000 < x < 100000
            volume_24h=10000,
            price_change_24h=5.0,
            buy_sell_ratio=1.0
        )
        assert assessment.factors["liquidity"] == 50

    def test_liquidity_high(self, risk_scorer):
        """Test high liquidity scoring."""
        assessment = risk_scorer.score_token(
            market_cap=1000000,
            liquidity=500000,  # 100000 < x < 1000000
            volume_24h=100000,
            price_change_24h=5.0,
            buy_sell_ratio=1.0
        )
        assert assessment.factors["liquidity"] == 25

    def test_liquidity_very_high(self, risk_scorer):
        """Test very high liquidity scoring."""
        assessment = risk_scorer.score_token(
            market_cap=10000000,
            liquidity=5000000,  # > 1000000
            volume_24h=1000000,
            price_change_24h=5.0,
            buy_sell_ratio=1.0
        )
        assert assessment.factors["liquidity"] == 10

    def test_market_cap_micro(self, risk_scorer):
        """Test micro cap scoring."""
        assessment = risk_scorer.score_token(
            market_cap=5000,  # < 10000
            liquidity=100000,
            volume_24h=1000,
            price_change_24h=5.0,
            buy_sell_ratio=1.0
        )
        assert assessment.factors["market_cap"] == 100
        assert any("Micro cap" in w for w in assessment.warnings)

    def test_market_cap_small(self, risk_scorer):
        """Test very small cap scoring."""
        assessment = risk_scorer.score_token(
            market_cap=50000,  # 10000 < x < 100000
            liquidity=100000,
            volume_24h=10000,
            price_change_24h=5.0,
            buy_sell_ratio=1.0
        )
        assert assessment.factors["market_cap"] == 80

    def test_market_cap_medium(self, risk_scorer):
        """Test medium cap scoring."""
        assessment = risk_scorer.score_token(
            market_cap=500000,  # 100000 < x < 1000000
            liquidity=200000,
            volume_24h=50000,
            price_change_24h=5.0,
            buy_sell_ratio=1.0
        )
        assert assessment.factors["market_cap"] == 50

    def test_volatility_extreme(self, risk_scorer):
        """Test extreme volatility scoring."""
        assessment = risk_scorer.score_token(
            market_cap=1000000,
            liquidity=500000,
            volume_24h=200000,
            price_change_24h=150.0,  # > 100%
            buy_sell_ratio=1.0
        )
        assert assessment.factors["volatility"] == 100
        assert any("Extreme volatility" in w for w in assessment.warnings)

    def test_volatility_high(self, risk_scorer):
        """Test high volatility scoring."""
        assessment = risk_scorer.score_token(
            market_cap=1000000,
            liquidity=500000,
            volume_24h=200000,
            price_change_24h=75.0,  # 50% < x < 100%
            buy_sell_ratio=1.0
        )
        assert assessment.factors["volatility"] == 80

    def test_volatility_moderate(self, risk_scorer):
        """Test moderate volatility scoring."""
        assessment = risk_scorer.score_token(
            market_cap=1000000,
            liquidity=500000,
            volume_24h=200000,
            price_change_24h=35.0,  # 25% < x < 50%
            buy_sell_ratio=1.0
        )
        assert assessment.factors["volatility"] == 50

    def test_volatility_low(self, risk_scorer):
        """Test low volatility scoring."""
        assessment = risk_scorer.score_token(
            market_cap=1000000,
            liquidity=500000,
            volume_24h=200000,
            price_change_24h=5.0,  # < 10%
            buy_sell_ratio=1.0
        )
        assert assessment.factors["volatility"] == 10

    def test_volume_suspicious_high(self, risk_scorer):
        """Test suspiciously high volume scoring."""
        assessment = risk_scorer.score_token(
            market_cap=100000,
            liquidity=100000,
            volume_24h=600000,  # 6x market cap
            price_change_24h=5.0,
            buy_sell_ratio=1.0
        )
        assert assessment.factors["volume"] == 90
        assert any("Volume > 5x" in w for w in assessment.warnings)

    def test_volume_healthy(self, risk_scorer):
        """Test healthy volume scoring."""
        assessment = risk_scorer.score_token(
            market_cap=1000000,
            liquidity=500000,
            volume_24h=200000,  # 20% of market cap
            price_change_24h=5.0,
            buy_sell_ratio=1.0
        )
        assert assessment.factors["volume"] == 25

    def test_volume_low(self, risk_scorer):
        """Test low volume scoring."""
        assessment = risk_scorer.score_token(
            market_cap=1000000,
            liquidity=500000,
            volume_24h=50000,  # 5% of market cap
            price_change_24h=5.0,
            buy_sell_ratio=1.0
        )
        assert assessment.factors["volume"] == 60
        assert any("Low trading volume" in w for w in assessment.warnings)

    def test_volume_zero_market_cap(self, risk_scorer):
        """Test volume scoring with zero market cap."""
        assessment = risk_scorer.score_token(
            market_cap=0,
            liquidity=100000,
            volume_24h=50000,
            price_change_24h=5.0,
            buy_sell_ratio=1.0
        )
        assert assessment.factors["volume"] == 50  # Default

    def test_price_massive_pump(self, risk_scorer):
        """Test massive pump price change scoring."""
        assessment = risk_scorer.score_token(
            market_cap=1000000,
            liquidity=500000,
            volume_24h=200000,
            price_change_24h=600.0,  # > 500%
            buy_sell_ratio=1.0
        )
        assert assessment.factors["price_change"] == 100
        assert any("Massive pump" in w for w in assessment.warnings)

    def test_price_major_dump(self, risk_scorer):
        """Test major dump price change scoring."""
        assessment = risk_scorer.score_token(
            market_cap=1000000,
            liquidity=500000,
            volume_24h=200000,
            price_change_24h=-60.0,  # < -50%
            buy_sell_ratio=1.0
        )
        assert assessment.factors["price_change"] == 90
        assert any("Major dump" in w for w in assessment.warnings)

    def test_buy_sell_ratio_strong_buying(self, risk_scorer):
        """Test strong buying pressure scoring."""
        assessment = risk_scorer.score_token(
            market_cap=1000000,
            liquidity=500000,
            volume_24h=200000,
            price_change_24h=5.0,
            buy_sell_ratio=4.0  # > 3
        )
        assert assessment.factors["buy_sell_ratio"] == 30

    def test_buy_sell_ratio_heavy_selling(self, risk_scorer):
        """Test heavy selling pressure scoring."""
        assessment = risk_scorer.score_token(
            market_cap=1000000,
            liquidity=500000,
            volume_24h=200000,
            price_change_24h=5.0,
            buy_sell_ratio=0.2  # < 0.3
        )
        assert assessment.factors["buy_sell_ratio"] == 90
        assert any("Heavy selling" in w for w in assessment.warnings)

    def test_token_age_brand_new(self, risk_scorer):
        """Test brand new token scoring."""
        assessment = risk_scorer.score_token(
            market_cap=1000000,
            liquidity=500000,
            volume_24h=200000,
            price_change_24h=5.0,
            buy_sell_ratio=1.0,
            token_age_days=0
        )
        assert assessment.factors["age"] == 100
        assert any("Brand new token" in w for w in assessment.warnings)

    def test_token_age_one_week(self, risk_scorer):
        """Test token less than 1 week old scoring."""
        assessment = risk_scorer.score_token(
            market_cap=1000000,
            liquidity=500000,
            volume_24h=200000,
            price_change_24h=5.0,
            buy_sell_ratio=1.0,
            token_age_days=5
        )
        assert assessment.factors["age"] == 80

    def test_token_age_established(self, risk_scorer):
        """Test established token scoring."""
        assessment = risk_scorer.score_token(
            market_cap=1000000,
            liquidity=500000,
            volume_24h=200000,
            price_change_24h=5.0,
            buy_sell_ratio=1.0,
            token_age_days=120  # > 90 days
        )
        assert assessment.factors["age"] == 15

    def test_holders_very_few(self, risk_scorer):
        """Test very few holders scoring."""
        assessment = risk_scorer.score_token(
            market_cap=1000000,
            liquidity=500000,
            volume_24h=200000,
            price_change_24h=5.0,
            buy_sell_ratio=1.0,
            holders=50  # < 100
        )
        assert assessment.factors["holders"] == 90
        assert any("Very few holders" in w for w in assessment.warnings)

    def test_holders_healthy(self, risk_scorer):
        """Test healthy holder count scoring."""
        assessment = risk_scorer.score_token(
            market_cap=1000000,
            liquidity=500000,
            volume_24h=200000,
            price_change_24h=5.0,
            buy_sell_ratio=1.0,
            holders=5000  # > 2000
        )
        assert assessment.factors["holders"] == 15


# =============================================================================
# RiskScorer Tests - Risk Level Thresholds
# =============================================================================

class TestRiskScorerLevels:
    """Test risk level classification."""

    def test_extreme_risk_level(self, risk_scorer):
        """Test extreme risk level threshold (>= 80)."""
        assessment = risk_scorer.score_token(
            market_cap=1000,
            liquidity=100,
            volume_24h=10000,
            price_change_24h=700.0,
            buy_sell_ratio=0.1,
            token_age_days=0,
            holders=10
        )
        assert assessment.overall_score >= 80
        assert assessment.level == RiskLevel.EXTREME

    def test_very_high_risk_level(self, risk_scorer):
        """Test very high risk level threshold (65-79)."""
        # Tune values to get score in 65-79 range
        assessment = risk_scorer.score_token(
            market_cap=20000,
            liquidity=5000,
            volume_24h=15000,
            price_change_24h=80.0,
            buy_sell_ratio=0.4,
            token_age_days=3,
            holders=80
        )
        assert 65 <= assessment.overall_score < 80
        assert assessment.level == RiskLevel.VERY_HIGH

    def test_high_risk_level(self, risk_scorer):
        """Test high risk level threshold (50-64)."""
        assessment = risk_scorer.score_token(
            market_cap=50000,  # Very small cap (80)
            liquidity=5000,   # Low liquidity (80)
            volume_24h=20000, # 40% of market cap (50)
            price_change_24h=30.0,  # Moderate volatility (50)
            buy_sell_ratio=0.6,  # Some sell pressure (70)
            token_age_days=10,  # Less than 30 days (50)
            holders=150  # Low holders (60)
        )
        assert 50 <= assessment.overall_score < 65
        assert assessment.level == RiskLevel.HIGH

    def test_medium_risk_level(self, risk_scorer):
        """Test medium risk level threshold (35-49)."""
        assessment = risk_scorer.score_token(
            market_cap=500000,  # Medium cap (50)
            liquidity=100000,  # Medium liquidity (50)
            volume_24h=100000,  # 20% of market cap (25)
            price_change_24h=15.0,  # Some volatility (25)
            buy_sell_ratio=0.9,  # Slight sell pressure (40)
            token_age_days=20,  # Less than 30 days (50)
            holders=400  # Low-medium holders (60)
        )
        assert 35 <= assessment.overall_score < 50
        assert assessment.level == RiskLevel.MEDIUM

    def test_low_risk_level(self, risk_scorer):
        """Test low risk level threshold (20-34)."""
        assessment = risk_scorer.score_token(
            market_cap=50000000,
            liquidity=10000000,
            volume_24h=5000000,
            price_change_24h=3.0,
            buy_sell_ratio=1.8,
            token_age_days=180,
            holders=20000
        )
        assert 20 <= assessment.overall_score < 35
        assert assessment.level == RiskLevel.LOW

    def test_very_low_risk_level(self, risk_scorer):
        """Test very low risk level threshold (< 20)."""
        assessment = risk_scorer.score_token(
            market_cap=100000000,  # Large cap (10)
            liquidity=50000000,  # High liquidity (10)
            volume_24h=50000000,  # 50% of market cap (50)
            price_change_24h=1.0,  # Low volatility (10)
            buy_sell_ratio=3.5,  # Strong buying (30)
            token_age_days=365,  # Old token (15)
            holders=100000  # Many holders (15)
        )
        assert assessment.overall_score < 20
        assert assessment.level == RiskLevel.VERY_LOW


# =============================================================================
# RiskScorer Tests - Weights
# =============================================================================

class TestRiskScorerWeights:
    """Test risk scorer weight system."""

    def test_default_weights(self, risk_scorer):
        """Test default weights are set correctly."""
        assert risk_scorer.weights["liquidity"] == 20
        assert risk_scorer.weights["market_cap"] == 15
        assert risk_scorer.weights["volatility"] == 15
        assert risk_scorer.weights["volume"] == 15
        assert risk_scorer.weights["price_change"] == 10
        assert risk_scorer.weights["buy_sell_ratio"] == 10
        assert risk_scorer.weights["age"] == 10
        assert risk_scorer.weights["holders"] == 5

    def test_weights_sum_to_100(self, risk_scorer):
        """Test weights sum to 100."""
        total = sum(risk_scorer.weights.values())
        assert total == 100


# =============================================================================
# PortfolioRiskManager Tests - Basic Operations
# =============================================================================

class TestPortfolioRiskManagerBasics:
    """Test PortfolioRiskManager basic operations."""

    def test_initialization(self, portfolio_manager):
        """Test default initialization."""
        assert portfolio_manager.max_portfolio_risk == 20.0
        assert portfolio_manager.max_single_position == 10.0
        assert portfolio_manager.max_correlated_exposure == 30.0
        assert portfolio_manager.positions == {}

    def test_custom_initialization(self, custom_portfolio_manager):
        """Test custom initialization."""
        assert custom_portfolio_manager.max_portfolio_risk == 25.0
        assert custom_portfolio_manager.max_single_position == 15.0
        assert custom_portfolio_manager.max_correlated_exposure == 40.0

    def test_add_position(self, portfolio_manager):
        """Test adding a position."""
        portfolio_manager.add_position(
            symbol="SOL",
            value=1000,
            risk_percent=5.0,
            category="crypto"
        )
        assert "SOL" in portfolio_manager.positions
        assert portfolio_manager.positions["SOL"]["value"] == 1000
        assert portfolio_manager.positions["SOL"]["risk_percent"] == 5.0
        assert portfolio_manager.positions["SOL"]["category"] == "crypto"

    def test_update_existing_position(self, portfolio_manager):
        """Test updating an existing position."""
        portfolio_manager.add_position("SOL", 1000, 5.0)
        portfolio_manager.add_position("SOL", 1500, 7.0)  # Update
        assert portfolio_manager.positions["SOL"]["value"] == 1500
        assert portfolio_manager.positions["SOL"]["risk_percent"] == 7.0

    def test_remove_position(self, portfolio_manager):
        """Test removing a position."""
        portfolio_manager.add_position("SOL", 1000, 5.0)
        portfolio_manager.add_position("BTC", 2000, 3.0)
        portfolio_manager.remove_position("SOL")
        assert "SOL" not in portfolio_manager.positions
        assert "BTC" in portfolio_manager.positions

    def test_remove_nonexistent_position(self, portfolio_manager):
        """Test removing a position that doesn't exist."""
        portfolio_manager.remove_position("NONEXISTENT")
        # Should not raise error
        assert "NONEXISTENT" not in portfolio_manager.positions


# =============================================================================
# PortfolioRiskManager Tests - Portfolio Risk Calculation
# =============================================================================

class TestPortfolioRiskManagerRiskCalc:
    """Test portfolio risk calculations."""

    def test_empty_portfolio_risk(self, portfolio_manager):
        """Test risk calculation for empty portfolio."""
        result = portfolio_manager.get_portfolio_risk()
        assert result["total_risk"] == 0
        assert result["position_count"] == 0
        assert result["largest_position_percent"] == 0
        assert result["risk_by_category"] == {}

    def test_single_position_risk(self, portfolio_manager):
        """Test risk calculation with single position."""
        portfolio_manager.add_position("SOL", 1000, 5.0, "crypto")
        result = portfolio_manager.get_portfolio_risk()
        assert result["total_risk"] == 5.0
        assert result["position_count"] == 1
        assert result["largest_position_percent"] == 100.0
        assert result["risk_by_category"]["crypto"] == 100.0

    def test_multiple_positions_risk(self, portfolio_manager):
        """Test risk calculation with multiple positions."""
        portfolio_manager.add_position("SOL", 1000, 5.0, "crypto")
        portfolio_manager.add_position("BTC", 2000, 3.0, "crypto")
        portfolio_manager.add_position("AAPL", 1000, 2.0, "stocks")
        result = portfolio_manager.get_portfolio_risk()

        # Total value = 4000
        # Weighted risk = (1000*5 + 2000*3 + 1000*2) / 4000 = 13000 / 4000 = 3.25%
        assert result["total_risk"] == pytest.approx(3.25, rel=0.01)
        assert result["position_count"] == 3
        # Largest = BTC at 2000/4000 = 50%
        assert result["largest_position_percent"] == 50.0
        # Crypto = 3000/4000 = 75%, Stocks = 1000/4000 = 25%
        assert result["risk_by_category"]["crypto"] == 75.0
        assert result["risk_by_category"]["stocks"] == 25.0

    def test_within_limits_true(self, portfolio_manager):
        """Test within_limits is True when all limits satisfied."""
        # Need 10+ positions to keep largest position <= 10%
        for i in range(10):
            portfolio_manager.add_position(f"TOKEN_{i}", 100, 1.5, "crypto")
        result = portfolio_manager.get_portfolio_risk()
        # Total risk = 1.5%, largest = 10%, both within limits
        assert result["within_limits"] is True

    def test_within_limits_false_risk(self, portfolio_manager):
        """Test within_limits is False when total risk exceeded."""
        # Add high-risk positions to exceed 20% total risk limit
        portfolio_manager.add_position("SOL", 1000, 25.0, "crypto")
        result = portfolio_manager.get_portfolio_risk()
        # Total risk = 25% > 20% limit
        assert result["within_limits"] is False

    def test_within_limits_false_position(self, portfolio_manager):
        """Test within_limits is False when single position exceeded."""
        portfolio_manager.add_position("SOL", 800, 5.0, "crypto")
        portfolio_manager.add_position("BTC", 200, 5.0, "crypto")
        result = portfolio_manager.get_portfolio_risk()
        # Largest = 80% > 10% limit
        assert result["within_limits"] is False

    def test_zero_value_positions(self, portfolio_manager):
        """Test handling of zero-value positions."""
        portfolio_manager.add_position("SOL", 0, 5.0, "crypto")
        result = portfolio_manager.get_portfolio_risk()
        # Should return zeros, not crash
        assert result["total_risk"] == 0
        assert result["position_count"] == 0


# =============================================================================
# PortfolioRiskManager Tests - Can Add Position
# =============================================================================

class TestPortfolioRiskManagerCanAdd:
    """Test can_add_position validation."""

    def test_can_add_to_empty_portfolio(self, portfolio_manager):
        """Test adding to empty portfolio."""
        # Adding 500 to empty portfolio = 100% of portfolio, exceeds 10% limit
        # Need to add a small enough position
        can_add, msg = portfolio_manager.can_add_position(
            value=50,  # Small position
            risk_percent=5.0,
            category="crypto"
        )
        # Single position is 100% of total, but implementation checks limits
        # For empty portfolio, any single position is 100% of new total
        # which exceeds the 10% max_single_position limit
        # Actually need to understand the logic better
        # Actually the check is: (value / total_value) * 100 > max_single_position
        # For first position, total_value = 0 + 50 = 50
        # position_percent = (50 / 50) * 100 = 100% > 10%
        # So can_add should be False
        assert can_add is False
        assert "Position size" in msg

    def test_can_add_within_limits(self, portfolio_manager):
        """Test adding position within all limits."""
        # Need to have enough existing positions so new position is <= 10%
        # Add 9000 worth of positions first
        for i in range(9):
            portfolio_manager.add_position(f"TOKEN_{i}", 1000, 5.0, "stocks")
        # Now add 1000 more = 10000 total
        # New position = 1000 / (9000 + 1000) = 10% exactly = at limit
        # But category would be 1000/10000 = 10% < 30%
        # Total risk stays at 5%
        can_add, msg = portfolio_manager.can_add_position(
            value=1000,  # 10% of new total
            risk_percent=5.0,
            category="crypto"  # Different category from existing
        )
        assert can_add is True
        assert msg == "OK"

    def test_cannot_add_exceeds_single_position(self, portfolio_manager):
        """Test rejecting position that exceeds single position limit."""
        portfolio_manager.add_position("SOL", 1000, 5.0, "crypto")
        can_add, msg = portfolio_manager.can_add_position(
            value=5000,  # Would be 83% of new total
            risk_percent=5.0,
            category="crypto"
        )
        assert can_add is False
        assert "Position size" in msg
        assert "exceeds limit" in msg

    def test_cannot_add_exceeds_total_risk(self, portfolio_manager):
        """Test rejecting position that exceeds total risk."""
        # Add many positions to avoid triggering single position limit first
        for i in range(9):
            portfolio_manager.add_position(f"TOKEN_{i}", 1000, 18.0, "stocks")  # High risk
        # Total value = 9000, total weighted risk = ~18%
        # Adding 1000 with 50% risk would be 10% of portfolio (OK size)
        # but would push total risk over 20% limit
        can_add, msg = portfolio_manager.can_add_position(
            value=1000,  # 10% of new total
            risk_percent=50.0,  # Would push total risk over limit
            category="crypto"
        )
        assert can_add is False
        assert "Total risk" in msg
        assert "exceed limit" in msg

    def test_cannot_add_exceeds_category_exposure(self, portfolio_manager):
        """Test rejecting position that exceeds category exposure."""
        # Add positions to different categories to avoid single position limit
        # We need new crypto position to exceed 30% category limit
        # Add 7 stock positions (total 7000)
        for i in range(7):
            portfolio_manager.add_position(f"STOCK_{i}", 1000, 5.0, "stocks")
        # Add 3 crypto positions (total 3000)
        for i in range(3):
            portfolio_manager.add_position(f"CRYPTO_{i}", 1000, 5.0, "crypto")
        # Total = 10000, crypto = 30% exactly
        # Try to add more crypto - would be 1000 / 11000 = 9% position (OK)
        # But crypto would be 4000 / 11000 = 36% > 30%
        can_add, msg = portfolio_manager.can_add_position(
            value=1000,  # 9% of new total (OK for position size)
            risk_percent=5.0,
            category="crypto"  # Would push crypto to 36%
        )
        assert can_add is False
        assert "Category exposure" in msg

    def test_can_add_zero_value(self, portfolio_manager):
        """Test adding zero value position."""
        can_add, msg = portfolio_manager.can_add_position(
            value=0,
            risk_percent=5.0,
            category="crypto"
        )
        assert can_add is True
        assert msg == "OK"


# =============================================================================
# Singleton Accessor Tests
# =============================================================================

class TestSingletonAccessors:
    """Test singleton accessor functions."""

    def test_get_position_sizer_default(self):
        """Test getting position sizer with default value."""
        # Reset singleton
        import core.risk_scoring as risk_module
        risk_module._position_sizer = None

        sizer = get_position_sizer()
        assert sizer.portfolio_value == 10000

    def test_get_position_sizer_custom(self):
        """Test getting position sizer with custom value."""
        import core.risk_scoring as risk_module
        risk_module._position_sizer = None

        sizer = get_position_sizer(portfolio_value=25000)
        assert sizer.portfolio_value == 25000

    def test_get_position_sizer_singleton(self):
        """Test position sizer is a singleton."""
        import core.risk_scoring as risk_module
        risk_module._position_sizer = None

        sizer1 = get_position_sizer(10000)
        sizer2 = get_position_sizer(50000)  # Should return same instance
        assert sizer1 is sizer2
        assert sizer1.portfolio_value == 10000  # Original value

    def test_get_risk_scorer_singleton(self):
        """Test risk scorer is a singleton."""
        import core.risk_scoring as risk_module
        risk_module._risk_scorer = None

        scorer1 = get_risk_scorer()
        scorer2 = get_risk_scorer()
        assert scorer1 is scorer2

    def test_get_portfolio_risk_manager_singleton(self):
        """Test portfolio risk manager is a singleton."""
        import core.risk_scoring as risk_module
        risk_module._portfolio_risk = None

        manager1 = get_portfolio_risk_manager()
        manager2 = get_portfolio_risk_manager()
        assert manager1 is manager2


# =============================================================================
# Edge Cases and Boundary Tests
# =============================================================================

class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_very_small_portfolio(self):
        """Test with very small portfolio value."""
        sizer = PositionSizer(portfolio_value=100)
        result = sizer.calculate_position_fixed_risk(
            entry_price=1.0,
            stop_loss=0.9,
            risk_percent=2.0
        )
        # Risk = 100 * 0.02 = 2
        # Raw position size = 2 / 0.1 = 20 ($20 value)
        # Max position = 100 * 0.10 = 10, so 10 shares max
        # Actual risk = 10 * 0.1 = 1
        assert result["position_size"] == 10.0
        assert result["risk_amount"] == pytest.approx(1.0, rel=0.01)

    def test_very_large_portfolio(self):
        """Test with very large portfolio value."""
        sizer = PositionSizer(portfolio_value=1_000_000_000)
        result = sizer.calculate_position_fixed_risk(
            entry_price=100.0,
            stop_loss=90.0,
            risk_percent=2.0
        )
        # Risk = 1B * 0.02 = 20M
        # But limited by max position
        max_position = 1_000_000_000 * 0.10  # 100M value
        assert result["position_value"] <= max_position

    def test_very_small_price(self):
        """Test with very small price (penny stock)."""
        sizer = PositionSizer(portfolio_value=10000)
        result = sizer.calculate_position_fixed_risk(
            entry_price=0.001,
            stop_loss=0.0009,
            risk_percent=2.0
        )
        # Should handle small prices correctly
        assert result["position_size"] > 0
        assert result["position_value"] <= 1000  # Max 10%

    def test_very_high_price(self):
        """Test with very high price."""
        sizer = PositionSizer(portfolio_value=10000)
        result = sizer.calculate_position_fixed_risk(
            entry_price=50000.0,  # BTC-like price
            stop_loss=45000.0,
            risk_percent=2.0
        )
        # Risk = 200, risk per share = 5000
        # Raw position size = 200 / 5000 = 0.04
        # Max position = 10000 * 0.10 = 1000, so 1000/50000 = 0.02 shares max
        # Position is limited by max position percent
        assert result["position_size"] == pytest.approx(0.02, rel=0.01)

    def test_negative_price_change(self, risk_scorer):
        """Test with large negative price change."""
        assessment = risk_scorer.score_token(
            market_cap=1000000,
            liquidity=500000,
            volume_24h=200000,
            price_change_24h=-99.0,  # Nearly 100% drop
            buy_sell_ratio=1.0
        )
        # Should still calculate correctly
        assert assessment.overall_score > 0
        assert assessment.level is not None

    def test_zero_buy_sell_ratio(self, risk_scorer):
        """Test with zero buy/sell ratio."""
        assessment = risk_scorer.score_token(
            market_cap=1000000,
            liquidity=500000,
            volume_24h=200000,
            price_change_24h=5.0,
            buy_sell_ratio=0.0  # All sells
        )
        assert assessment.factors["buy_sell_ratio"] == 90

    def test_very_high_buy_sell_ratio(self, risk_scorer):
        """Test with very high buy/sell ratio."""
        assessment = risk_scorer.score_token(
            market_cap=1000000,
            liquidity=500000,
            volume_24h=200000,
            price_change_24h=5.0,
            buy_sell_ratio=100.0  # All buys
        )
        assert assessment.factors["buy_sell_ratio"] == 30


# =============================================================================
# Integration-style Tests
# =============================================================================

class TestIntegration:
    """Integration-style tests combining multiple components."""

    def test_full_position_sizing_workflow(self, position_sizer, risk_scorer):
        """Test complete workflow: score token, size position."""
        # First score the token
        assessment = risk_scorer.score_token(
            market_cap=5_000_000,
            liquidity=1_000_000,
            volume_24h=500_000,
            price_change_24h=10.0,
            buy_sell_ratio=1.5,
            token_age_days=30,
            holders=1000
        )

        # Adjust risk based on score
        if assessment.level in [RiskLevel.HIGH, RiskLevel.VERY_HIGH, RiskLevel.EXTREME]:
            risk_percent = 1.0  # Reduce risk
        else:
            risk_percent = 2.0  # Standard risk

        # Calculate position
        result = position_sizer.calculate_position_fixed_risk(
            entry_price=100.0,
            stop_loss=90.0,
            risk_percent=risk_percent
        )

        assert result["position_size"] > 0
        assert result["risk_percent"] <= 2.0

    def test_portfolio_tracking_workflow(self, portfolio_manager, risk_scorer):
        """Test complete workflow: add positions, track risk."""
        # Add multiple positions
        portfolio_manager.add_position("SOL", 1000, 5.0, "layer1")
        portfolio_manager.add_position("ETH", 2000, 3.0, "layer1")
        portfolio_manager.add_position("PEPE", 500, 10.0, "meme")

        # Check portfolio risk
        risk = portfolio_manager.get_portfolio_risk()
        assert risk["position_count"] == 3
        assert risk["total_risk"] > 0

        # Check if can add new position
        can_add, msg = portfolio_manager.can_add_position(
            value=300,
            risk_percent=8.0,
            category="meme"
        )
        # Should check against all limits
        assert isinstance(can_add, bool)
        assert isinstance(msg, str)
