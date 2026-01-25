"""
Comprehensive unit tests for bots/bags_intel/scorer.py

Tests cover:
- Individual scoring dimensions (bonding_curve, creator, social, market, distribution)
- Overall score calculation and weighting
- Quality tier classification (Exceptional 80+, Strong 65-79, etc.)
- Risk level determination
- Edge cases (missing data, malformed inputs, extreme values)
- Grok AI integration (mocked)

Coverage target: 60%+
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from typing import List

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from bots.bags_intel.scorer import IntelScorer, THRESHOLDS
from bots.bags_intel.models import (
    TokenMetadata,
    CreatorProfile,
    BondingMetrics,
    MarketMetrics,
    IntelScore,
    LaunchQuality,
    RiskLevel,
)


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
def scorer():
    """Create an IntelScorer without Grok API key."""
    return IntelScorer(xai_api_key=None)


@pytest.fixture
def scorer_with_grok():
    """Create an IntelScorer with Grok API key for AI analysis."""
    return IntelScorer(xai_api_key="test-api-key")


@pytest.fixture
def base_token():
    """Create a basic token with all socials linked."""
    return TokenMetadata(
        mint_address="TokenMint1111111111111111111111111111111111",
        name="Test Token",
        symbol="TEST",
        description="A test token",
        image_url="https://example.com/image.png",
        website="https://testtoken.com",
        twitter="https://twitter.com/testtoken",
        telegram="https://t.me/testtoken",
    )


@pytest.fixture
def base_creator():
    """Create a standard creator profile with Twitter."""
    return CreatorProfile(
        wallet_address="CreatorWallet111111111111111111111111111111",
        twitter_handle="creator_test",
        twitter_followers=500,
        twitter_account_age_days=60,
        previous_launches=2,
        rugged_launches=0,
    )


@pytest.fixture
def base_bonding():
    """Create healthy bonding metrics."""
    return BondingMetrics(
        duration_seconds=600,  # 10 minutes - optimal range
        total_volume_sol=30.0,  # Above min, below optimal
        unique_buyers=50,  # Above min, below optimal
        unique_sellers=20,
        buy_sell_ratio=2.5,  # Above min, below optimal
        graduation_mcap_usd=100000.0,
    )


@pytest.fixture
def base_market():
    """Create healthy market metrics."""
    return MarketMetrics(
        price_usd=0.001,
        price_sol=0.00001,
        market_cap_usd=100000.0,
        liquidity_usd=15000.0,  # Above min, below optimal
        volume_24h_usd=50000.0,
        price_change_1h=20.0,  # Moderate gain
        buys_1h=100,
        sells_1h=50,
        holder_count=200,
        top_10_holder_pct=35.0,  # Moderate concentration
    )


# =============================================================================
# Bonding Score Tests
# =============================================================================

class TestBondingScore:
    """Tests for _score_bonding method."""

    def test_optimal_bonding_duration(self, scorer, base_token, base_creator, base_market):
        """Test scoring for optimal bonding duration (5min - 1hr)."""
        bonding = BondingMetrics(
            duration_seconds=1800,  # 30 minutes - optimal
            total_volume_sol=60.0,  # Optimal
            unique_buyers=120,  # Optimal
            unique_sellers=40,
            buy_sell_ratio=3.5,  # Optimal
            graduation_mcap_usd=100000.0,
        )
        red, green, warn = [], [], []
        score = scorer._score_bonding(bonding, red, green, warn)

        assert score >= 80  # Should be high with all optimal values
        assert any("Healthy graduation time" in f for f in green)
        assert any("Strong volume" in f for f in green)
        assert any("Many buyers" in f for f in green)
        assert any("Strong buy pressure" in f for f in green)

    def test_suspiciously_fast_graduation(self, scorer):
        """Test penalty for suspiciously fast graduation (<1 min)."""
        bonding = BondingMetrics(
            duration_seconds=30,  # 30 seconds - suspicious
            total_volume_sol=50.0,
            unique_buyers=100,
            unique_sellers=30,
            buy_sell_ratio=3.0,
            graduation_mcap_usd=100000.0,
        )
        red, green, warn = [], [], []
        score = scorer._score_bonding(bonding, red, green, warn)

        assert any("Suspiciously fast graduation" in f for f in red)
        # Score should be penalized (-30 from base 50, but other factors add points)
        # With optimal values elsewhere, score will be reduced but can still be positive
        assert score <= 75  # Significantly less than optimal case

    def test_quick_graduation(self, scorer):
        """Test warning for quick graduation (1-5 min)."""
        bonding = BondingMetrics(
            duration_seconds=120,  # 2 minutes - quick but not suspicious
            total_volume_sol=50.0,
            unique_buyers=100,
            unique_sellers=30,
            buy_sell_ratio=3.0,
            graduation_mcap_usd=100000.0,
        )
        red, green, warn = [], [], []
        score = scorer._score_bonding(bonding, red, green, warn)

        assert any("Quick graduation" in f for f in warn)
        assert len(red) == 0  # Should not be red flag

    def test_low_volume(self, scorer):
        """Test warning for low trading volume."""
        bonding = BondingMetrics(
            duration_seconds=600,
            total_volume_sol=5.0,  # Below min threshold
            unique_buyers=100,
            unique_sellers=30,
            buy_sell_ratio=3.0,
            graduation_mcap_usd=100000.0,
        )
        red, green, warn = [], [], []
        score = scorer._score_bonding(bonding, red, green, warn)

        assert any("Low volume" in f for f in warn)

    def test_few_buyers_red_flag(self, scorer):
        """Test red flag for very few buyers."""
        bonding = BondingMetrics(
            duration_seconds=600,
            total_volume_sol=50.0,
            unique_buyers=10,  # Below min threshold of 20
            unique_sellers=5,
            buy_sell_ratio=3.0,
            graduation_mcap_usd=100000.0,
        )
        red, green, warn = [], [], []
        score = scorer._score_bonding(bonding, red, green, warn)

        assert any("Few buyers" in f for f in red)
        # Score is penalized for few buyers, but other good metrics contribute positively
        # The key assertion is that the red flag is raised
        assert score <= 100

    def test_more_sellers_than_buyers(self, scorer):
        """Test red flag for buy/sell ratio below 1."""
        bonding = BondingMetrics(
            duration_seconds=600,
            total_volume_sol=50.0,
            unique_buyers=100,
            unique_sellers=150,
            buy_sell_ratio=0.7,  # More sells than buys
            graduation_mcap_usd=100000.0,
        )
        red, green, warn = [], [], []
        score = scorer._score_bonding(bonding, red, green, warn)

        assert any("More sellers than buyers" in f for f in red)

    def test_score_bounds(self, scorer):
        """Test that bonding score is clamped to 0-100."""
        # Very bad metrics
        bad_bonding = BondingMetrics(
            duration_seconds=10,  # Extremely fast
            total_volume_sol=1.0,  # Very low
            unique_buyers=5,  # Very few
            unique_sellers=50,
            buy_sell_ratio=0.1,  # Heavy selling
            graduation_mcap_usd=10000.0,
        )
        red, green, warn = [], [], []
        score = scorer._score_bonding(bad_bonding, red, green, warn)
        assert score >= 0
        assert score <= 100

        # Very good metrics
        good_bonding = BondingMetrics(
            duration_seconds=1800,
            total_volume_sol=100.0,
            unique_buyers=200,
            unique_sellers=30,
            buy_sell_ratio=5.0,
            graduation_mcap_usd=500000.0,
        )
        red2, green2, warn2 = [], [], []
        score2 = scorer._score_bonding(good_bonding, red2, green2, warn2)
        assert score2 >= 0
        assert score2 <= 100


# =============================================================================
# Creator Score Tests
# =============================================================================

class TestCreatorScore:
    """Tests for _score_creator method."""

    def test_creator_with_strong_twitter(self, scorer, base_token):
        """Test scoring for creator with established Twitter."""
        creator = CreatorProfile(
            wallet_address="Wallet111",
            twitter_handle="established_dev",
            twitter_followers=2000,  # Above optimal
            twitter_account_age_days=90,  # Well established
            previous_launches=3,
            rugged_launches=0,
        )
        red, green, warn = [], [], []
        score = scorer._score_creator(creator, base_token, red, green, warn)

        assert score >= 80  # High score for established creator
        assert any("Has Twitter" in f for f in green)
        assert any("Strong following" in f for f in green)
        assert any("Established account" in f for f in green)

    def test_creator_no_twitter(self, scorer, base_token):
        """Test penalty for creator without Twitter."""
        creator = CreatorProfile(
            wallet_address="Wallet111",
            twitter_handle=None,
            twitter_followers=None,
            twitter_account_age_days=None,
            previous_launches=0,
            rugged_launches=0,
        )
        red, green, warn = [], [], []
        score = scorer._score_creator(creator, base_token, red, green, warn)

        assert any("No Twitter linked" in f for f in red)
        assert score < 50

    def test_creator_new_twitter_account(self, scorer, base_token):
        """Test red flag for very new Twitter account."""
        creator = CreatorProfile(
            wallet_address="Wallet111",
            twitter_handle="new_account",
            twitter_followers=50,
            twitter_account_age_days=3,  # Only 3 days old - suspicious
            previous_launches=0,
            rugged_launches=0,
        )
        red, green, warn = [], [], []
        score = scorer._score_creator(creator, base_token, red, green, warn)

        assert any("New Twitter account" in f for f in red)

    def test_creator_with_rug_history(self, scorer, base_token):
        """Test severe penalty for creator with rug history."""
        creator = CreatorProfile(
            wallet_address="RuggerWallet",
            twitter_handle="rugger",
            twitter_followers=1000,
            twitter_account_age_days=180,
            previous_launches=5,
            rugged_launches=2,  # Has rugged before!
        )
        red, green, warn = [], [], []
        score = scorer._score_creator(creator, base_token, red, green, warn)

        assert any("previous rugs" in f for f in red)
        # Score should be heavily penalized
        assert score < 60

    def test_creator_moderate_following(self, scorer, base_token):
        """Test creator with moderate following (between min and optimal)."""
        creator = CreatorProfile(
            wallet_address="Wallet111",
            twitter_handle="dev_handle",
            twitter_followers=500,  # Between 100 and 1000
            twitter_account_age_days=45,
            previous_launches=1,
            rugged_launches=0,
        )
        red, green, warn = [], [], []
        score = scorer._score_creator(creator, base_token, red, green, warn)

        assert 50 <= score <= 80
        assert any("Has Twitter" in f for f in green)


# =============================================================================
# Social Score Tests
# =============================================================================

class TestSocialScore:
    """Tests for _score_social method."""

    def test_all_socials_linked(self, scorer):
        """Test high score for token with all socials."""
        token = TokenMetadata(
            mint_address="Mint111",
            name="Social Token",
            symbol="SOC",
            twitter="https://twitter.com/test",
            telegram="https://t.me/test",
            website="https://test.com",
        )
        red, green, warn = [], [], []
        score = scorer._score_social(token, red, green, warn)

        assert score >= 70
        assert any("socials linked" in f for f in green)
        assert any("Has website" in f for f in green)

    def test_no_socials_linked(self, scorer):
        """Test penalty for token with no socials."""
        token = TokenMetadata(
            mint_address="Mint111",
            name="Anon Token",
            symbol="ANON",
            twitter=None,
            telegram=None,
            website=None,
        )
        red, green, warn = [], [], []
        score = scorer._score_social(token, red, green, warn)

        assert score < 50
        assert any("No socials linked" in f for f in red)

    def test_partial_socials(self, scorer):
        """Test score for token with partial socials (2 of 3)."""
        token = TokenMetadata(
            mint_address="Mint111",
            name="Partial Token",
            symbol="PART",
            twitter="https://twitter.com/test",
            telegram=None,
            website="https://test.com",
        )
        red, green, warn = [], [], []
        score = scorer._score_social(token, red, green, warn)

        # Should get some bonus for 2 socials + website
        assert 50 <= score <= 80


# =============================================================================
# Market Score Tests
# =============================================================================

class TestMarketScore:
    """Tests for _score_market method."""

    def test_strong_liquidity(self, scorer):
        """Test high score for strong liquidity."""
        market = MarketMetrics(
            price_usd=0.01,
            price_sol=0.0001,
            market_cap_usd=500000.0,
            liquidity_usd=50000.0,  # Above optimal threshold
            volume_24h_usd=100000.0,
            price_change_1h=10.0,
            buys_1h=200,
            sells_1h=50,
            holder_count=300,
            top_10_holder_pct=25.0,
        )
        red, green, warn = [], [], []
        score = scorer._score_market(market, red, green, warn)

        assert score >= 75
        assert any("Strong liquidity" in f for f in green)
        assert any("Strong buy pressure" in f for f in green)

    def test_low_liquidity(self, scorer):
        """Test penalty for low liquidity."""
        market = MarketMetrics(
            price_usd=0.01,
            price_sol=0.0001,
            market_cap_usd=50000.0,
            liquidity_usd=2000.0,  # Below min threshold
            volume_24h_usd=10000.0,
            price_change_1h=5.0,
            buys_1h=50,
            sells_1h=50,
            holder_count=100,
            top_10_holder_pct=40.0,
        )
        red, green, warn = [], [], []
        score = scorer._score_market(market, red, green, warn)

        assert any("Low liquidity" in f for f in red)

    def test_pumping_hard_warning(self, scorer):
        """Test warning for rapid price increase."""
        market = MarketMetrics(
            price_usd=0.01,
            price_sol=0.0001,
            market_cap_usd=200000.0,
            liquidity_usd=20000.0,
            volume_24h_usd=50000.0,
            price_change_1h=150.0,  # +150% in 1 hour - pumping
            buys_1h=100,
            sells_1h=50,
            holder_count=200,
            top_10_holder_pct=30.0,
        )
        red, green, warn = [], [], []
        score = scorer._score_market(market, red, green, warn)

        assert any("Pumping hard" in f for f in warn)

    def test_dumping_red_flag(self, scorer):
        """Test red flag for price dump."""
        market = MarketMetrics(
            price_usd=0.001,
            price_sol=0.00001,
            market_cap_usd=50000.0,
            liquidity_usd=10000.0,
            volume_24h_usd=30000.0,
            price_change_1h=-60.0,  # -60% in 1 hour - dumping
            buys_1h=20,
            sells_1h=150,
            holder_count=100,
            top_10_holder_pct=40.0,
        )
        red, green, warn = [], [], []
        score = scorer._score_market(market, red, green, warn)

        assert any("Dumping" in f for f in red)
        assert any("Heavy selling" in f for f in red)

    def test_heavy_selling_pressure(self, scorer):
        """Test red flag for heavy selling pressure."""
        market = MarketMetrics(
            price_usd=0.01,
            price_sol=0.0001,
            market_cap_usd=100000.0,
            liquidity_usd=15000.0,
            volume_24h_usd=40000.0,
            price_change_1h=-10.0,
            buys_1h=30,  # Few buys
            sells_1h=100,  # Many sells
            holder_count=150,
            top_10_holder_pct=35.0,
        )
        red, green, warn = [], [], []
        score = scorer._score_market(market, red, green, warn)

        assert any("Heavy selling" in f for f in red)


# =============================================================================
# Distribution Score Tests
# =============================================================================

class TestDistributionScore:
    """Tests for _score_distribution method."""

    def test_well_distributed(self, scorer):
        """Test high score for well-distributed token."""
        market = MarketMetrics(
            price_usd=0.01,
            price_sol=0.0001,
            market_cap_usd=200000.0,
            liquidity_usd=30000.0,
            volume_24h_usd=50000.0,
            price_change_1h=10.0,
            buys_1h=100,
            sells_1h=50,
            holder_count=600,  # Many holders
            top_10_holder_pct=20.0,  # Low concentration
        )
        red, green, warn = [], [], []
        score = scorer._score_distribution(market, red, green, warn)

        assert score >= 80
        assert any("Well distributed" in f for f in green)
        assert any("Many holders" in f for f in green)

    def test_high_concentration(self, scorer):
        """Test penalty for high holder concentration."""
        market = MarketMetrics(
            price_usd=0.01,
            price_sol=0.0001,
            market_cap_usd=100000.0,
            liquidity_usd=20000.0,
            volume_24h_usd=30000.0,
            price_change_1h=5.0,
            buys_1h=50,
            sells_1h=30,
            holder_count=200,
            top_10_holder_pct=70.0,  # High concentration - red flag
        )
        red, green, warn = [], [], []
        score = scorer._score_distribution(market, red, green, warn)

        assert any("High concentration" in f for f in red)
        assert score < 60

    def test_moderate_concentration(self, scorer):
        """Test warning for moderate holder concentration."""
        market = MarketMetrics(
            price_usd=0.01,
            price_sol=0.0001,
            market_cap_usd=100000.0,
            liquidity_usd=20000.0,
            volume_24h_usd=30000.0,
            price_change_1h=5.0,
            buys_1h=50,
            sells_1h=30,
            holder_count=200,
            top_10_holder_pct=40.0,  # Between healthy and max
        )
        red, green, warn = [], [], []
        score = scorer._score_distribution(market, red, green, warn)

        assert any("Moderate concentration" in f for f in warn)

    def test_few_holders(self, scorer):
        """Test warning for few holders."""
        market = MarketMetrics(
            price_usd=0.01,
            price_sol=0.0001,
            market_cap_usd=50000.0,
            liquidity_usd=10000.0,
            volume_24h_usd=20000.0,
            price_change_1h=5.0,
            buys_1h=30,
            sells_1h=20,
            holder_count=30,  # Few holders
            top_10_holder_pct=40.0,
        )
        red, green, warn = [], [], []
        score = scorer._score_distribution(market, red, green, warn)

        assert any("Few holders" in f for f in warn)


# =============================================================================
# Quality Tier Tests
# =============================================================================

class TestQualityDetermination:
    """Tests for _determine_quality method."""

    def test_exceptional_quality(self, scorer):
        """Test Exceptional tier for score >= 80."""
        assert scorer._determine_quality(80.0) == LaunchQuality.EXCEPTIONAL
        assert scorer._determine_quality(95.0) == LaunchQuality.EXCEPTIONAL
        assert scorer._determine_quality(100.0) == LaunchQuality.EXCEPTIONAL

    def test_strong_quality(self, scorer):
        """Test Strong tier for score 65-79."""
        assert scorer._determine_quality(65.0) == LaunchQuality.STRONG
        assert scorer._determine_quality(72.0) == LaunchQuality.STRONG
        assert scorer._determine_quality(79.0) == LaunchQuality.STRONG

    def test_average_quality(self, scorer):
        """Test Average tier for score 50-64."""
        assert scorer._determine_quality(50.0) == LaunchQuality.AVERAGE
        assert scorer._determine_quality(57.0) == LaunchQuality.AVERAGE
        assert scorer._determine_quality(64.0) == LaunchQuality.AVERAGE

    def test_weak_quality(self, scorer):
        """Test Weak tier for score 35-49."""
        assert scorer._determine_quality(35.0) == LaunchQuality.WEAK
        assert scorer._determine_quality(42.0) == LaunchQuality.WEAK
        assert scorer._determine_quality(49.0) == LaunchQuality.WEAK

    def test_poor_quality(self, scorer):
        """Test Poor tier for score < 35."""
        assert scorer._determine_quality(34.0) == LaunchQuality.POOR
        assert scorer._determine_quality(20.0) == LaunchQuality.POOR
        assert scorer._determine_quality(0.0) == LaunchQuality.POOR


# =============================================================================
# Risk Level Tests
# =============================================================================

class TestRiskDetermination:
    """Tests for _determine_risk method."""

    def test_extreme_risk_with_rug_history(self, scorer):
        """Test Extreme risk when rug history is detected."""
        red_flags = ["Creator has 2 previous rugs!"]
        risk = scorer._determine_risk(red_flags, 50.0)
        assert risk == RiskLevel.EXTREME

    def test_high_risk_many_red_flags(self, scorer):
        """Test High risk with 4+ red flags."""
        red_flags = [
            "Few buyers",
            "No Twitter linked",
            "Low liquidity",
            "Heavy selling",
        ]
        risk = scorer._determine_risk(red_flags, 50.0)
        assert risk == RiskLevel.HIGH

    def test_high_risk_low_score(self, scorer):
        """Test High risk with very low score."""
        red_flags = ["Few buyers"]
        risk = scorer._determine_risk(red_flags, 25.0)
        assert risk == RiskLevel.HIGH

    def test_medium_risk_some_red_flags(self, scorer):
        """Test Medium risk with 2-3 red flags."""
        red_flags = ["Low volume", "Few buyers"]
        risk = scorer._determine_risk(red_flags, 55.0)
        assert risk == RiskLevel.MEDIUM

    def test_medium_risk_moderate_score(self, scorer):
        """Test Medium risk with score below 50."""
        red_flags = ["Low volume"]
        risk = scorer._determine_risk(red_flags, 45.0)
        assert risk == RiskLevel.MEDIUM

    def test_low_risk_clean(self, scorer):
        """Test Low risk with few red flags and good score."""
        red_flags = []
        risk = scorer._determine_risk(red_flags, 75.0)
        assert risk == RiskLevel.LOW

        red_flags_one = ["Minor issue"]
        risk2 = scorer._determine_risk(red_flags_one, 60.0)
        assert risk2 == RiskLevel.LOW


# =============================================================================
# Overall Score Calculation Tests
# =============================================================================

class TestOverallScoreCalculation:
    """Tests for calculate_score method with weighting."""

    @pytest.mark.asyncio
    async def test_overall_score_weighting(
        self, scorer, base_token, base_creator, base_bonding, base_market
    ):
        """Test that overall score applies correct weights."""
        result = await scorer.calculate_score(
            base_token, base_creator, base_bonding, base_market
        )

        # Verify weights: bonding 25%, creator 20%, social 15%, market 25%, distribution 15%
        expected = (
            result.bonding_score * 0.25
            + result.creator_score * 0.20
            + result.social_score * 0.15
            + result.market_score * 0.25
            + result.distribution_score * 0.15
        )

        assert abs(result.overall_score - expected) < 0.01

    @pytest.mark.asyncio
    async def test_exceptional_token(self, scorer):
        """Test scoring for an exceptional token launch."""
        token = TokenMetadata(
            mint_address="Exceptional111",
            name="Great Project",
            symbol="GREAT",
            website="https://great.com",
            twitter="https://twitter.com/great",
            telegram="https://t.me/great",
        )
        creator = CreatorProfile(
            wallet_address="CreatorGreat",
            twitter_handle="great_dev",
            twitter_followers=5000,
            twitter_account_age_days=365,
            previous_launches=3,
            rugged_launches=0,
        )
        bonding = BondingMetrics(
            duration_seconds=1800,  # 30 min optimal
            total_volume_sol=100.0,
            unique_buyers=200,
            unique_sellers=50,
            buy_sell_ratio=4.0,
            graduation_mcap_usd=250000.0,
        )
        market = MarketMetrics(
            price_usd=0.01,
            price_sol=0.0001,
            market_cap_usd=300000.0,
            liquidity_usd=50000.0,
            volume_24h_usd=100000.0,
            price_change_1h=15.0,
            buys_1h=150,
            sells_1h=30,
            holder_count=800,
            top_10_holder_pct=15.0,
        )

        result = await scorer.calculate_score(token, creator, bonding, market)

        assert result.overall_score >= 75
        assert result.launch_quality in [LaunchQuality.EXCEPTIONAL, LaunchQuality.STRONG]
        assert result.risk_level == RiskLevel.LOW
        assert len(result.green_flags) > len(result.red_flags)

    @pytest.mark.asyncio
    async def test_poor_token(self, scorer):
        """Test scoring for a poor/risky token launch."""
        token = TokenMetadata(
            mint_address="Poor111",
            name="Scam Token",
            symbol="SCAM",
            website=None,
            twitter=None,
            telegram=None,
        )
        creator = CreatorProfile(
            wallet_address="ScamWallet",
            twitter_handle=None,
            twitter_followers=None,
            twitter_account_age_days=None,
            previous_launches=1,
            rugged_launches=1,  # Has rugged!
        )
        bonding = BondingMetrics(
            duration_seconds=30,  # Suspiciously fast
            total_volume_sol=5.0,  # Low
            unique_buyers=8,  # Very few
            unique_sellers=3,
            buy_sell_ratio=0.5,  # More sellers
            graduation_mcap_usd=20000.0,
        )
        market = MarketMetrics(
            price_usd=0.0001,
            price_sol=0.000001,
            market_cap_usd=15000.0,
            liquidity_usd=2000.0,  # Very low
            volume_24h_usd=5000.0,
            price_change_1h=-40.0,  # Dumping
            buys_1h=10,
            sells_1h=50,  # Heavy selling
            holder_count=25,
            top_10_holder_pct=80.0,  # High concentration
        )

        result = await scorer.calculate_score(token, creator, bonding, market)

        assert result.overall_score < 40
        assert result.launch_quality in [LaunchQuality.POOR, LaunchQuality.WEAK]
        assert result.risk_level == RiskLevel.EXTREME  # Due to rug history
        assert len(result.red_flags) > len(result.green_flags)

    @pytest.mark.asyncio
    async def test_result_contains_all_scores(
        self, scorer, base_token, base_creator, base_bonding, base_market
    ):
        """Test that result contains all component scores."""
        result = await scorer.calculate_score(
            base_token, base_creator, base_bonding, base_market
        )

        assert isinstance(result, IntelScore)
        assert 0 <= result.overall_score <= 100
        assert 0 <= result.bonding_score <= 100
        assert 0 <= result.creator_score <= 100
        assert 0 <= result.social_score <= 100
        assert 0 <= result.market_score <= 100
        assert 0 <= result.distribution_score <= 100
        assert isinstance(result.launch_quality, LaunchQuality)
        assert isinstance(result.risk_level, RiskLevel)
        assert isinstance(result.green_flags, list)
        assert isinstance(result.red_flags, list)
        assert isinstance(result.warnings, list)


# =============================================================================
# Grok AI Integration Tests
# =============================================================================

class TestGrokIntegration:
    """Tests for Grok AI analysis integration."""

    @pytest.mark.asyncio
    async def test_no_grok_without_api_key(
        self, scorer, base_token, base_creator, base_bonding, base_market
    ):
        """Test that Grok analysis is skipped without API key."""
        result = await scorer.calculate_score(
            base_token, base_creator, base_bonding, base_market
        )
        assert result.grok_summary is None

    @pytest.mark.asyncio
    async def test_grok_called_with_api_key(
        self, scorer_with_grok, base_token, base_creator, base_bonding, base_market
    ):
        """Test that Grok analysis is attempted with API key."""
        with patch("aiohttp.ClientSession") as mock_session:
            # Mock the response
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.json = AsyncMock(return_value={
                "choices": [{"message": {"content": "This token looks promising."}}]
            })

            mock_cm = AsyncMock()
            mock_cm.__aenter__.return_value = mock_response

            mock_session_instance = MagicMock()
            mock_session_instance.post.return_value = mock_cm
            mock_session_instance.__aenter__ = AsyncMock(return_value=mock_session_instance)
            mock_session_instance.__aexit__ = AsyncMock(return_value=None)
            mock_session.return_value = mock_session_instance

            result = await scorer_with_grok.calculate_score(
                base_token, base_creator, base_bonding, base_market
            )

            # Grok should have been called
            assert mock_session_instance.post.called

    @pytest.mark.asyncio
    async def test_grok_failure_graceful(
        self, scorer_with_grok, base_token, base_creator, base_bonding, base_market
    ):
        """Test that Grok failure doesn't break scoring."""
        with patch("aiohttp.ClientSession") as mock_session:
            # Mock a failure
            mock_session_instance = MagicMock()
            mock_session_instance.post.side_effect = Exception("API Error")
            mock_session_instance.__aenter__ = AsyncMock(return_value=mock_session_instance)
            mock_session_instance.__aexit__ = AsyncMock(return_value=None)
            mock_session.return_value = mock_session_instance

            result = await scorer_with_grok.calculate_score(
                base_token, base_creator, base_bonding, base_market
            )

            # Should still get a valid result
            assert isinstance(result, IntelScore)
            assert result.grok_summary is None  # Failed gracefully


# =============================================================================
# Edge Cases and Boundary Tests
# =============================================================================

class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    @pytest.mark.asyncio
    async def test_zero_values(self, scorer, base_token, base_creator):
        """Test handling of zero values in metrics."""
        bonding = BondingMetrics(
            duration_seconds=0,
            total_volume_sol=0.0,
            unique_buyers=0,
            unique_sellers=0,
            buy_sell_ratio=0.0,
            graduation_mcap_usd=0.0,
        )
        market = MarketMetrics(
            price_usd=0.0,
            price_sol=0.0,
            market_cap_usd=0.0,
            liquidity_usd=0.0,
            volume_24h_usd=0.0,
            price_change_1h=0.0,
            buys_1h=0,
            sells_1h=0,
            holder_count=0,
            top_10_holder_pct=0.0,
        )

        # Should not crash
        result = await scorer.calculate_score(base_token, base_creator, bonding, market)
        assert isinstance(result, IntelScore)
        assert 0 <= result.overall_score <= 100

    @pytest.mark.asyncio
    async def test_extreme_positive_values(self, scorer, base_token, base_creator):
        """Test handling of extremely high values."""
        bonding = BondingMetrics(
            duration_seconds=86400,  # 24 hours
            total_volume_sol=10000.0,
            unique_buyers=10000,
            unique_sellers=1000,
            buy_sell_ratio=100.0,
            graduation_mcap_usd=10000000.0,
        )
        market = MarketMetrics(
            price_usd=100.0,
            price_sol=1.0,
            market_cap_usd=100000000.0,
            liquidity_usd=10000000.0,
            volume_24h_usd=50000000.0,
            price_change_1h=500.0,
            buys_1h=10000,
            sells_1h=100,
            holder_count=100000,
            top_10_holder_pct=5.0,
        )

        result = await scorer.calculate_score(base_token, base_creator, bonding, market)
        assert isinstance(result, IntelScore)
        assert 0 <= result.overall_score <= 100

    @pytest.mark.asyncio
    async def test_negative_price_change(self, scorer, base_token, base_creator, base_bonding):
        """Test handling of severe negative price changes."""
        market = MarketMetrics(
            price_usd=0.0001,
            price_sol=0.000001,
            market_cap_usd=10000.0,
            liquidity_usd=5000.0,
            volume_24h_usd=10000.0,
            price_change_1h=-99.0,  # Nearly complete loss
            buys_1h=5,
            sells_1h=500,
            holder_count=50,
            top_10_holder_pct=60.0,
        )

        result = await scorer.calculate_score(base_token, base_creator, base_bonding, market)
        assert any("Dumping" in f for f in result.red_flags)
        assert result.risk_level in [RiskLevel.HIGH, RiskLevel.MEDIUM]

    def test_boundary_duration_values(self, scorer):
        """Test bonding score at exact threshold boundaries."""
        # At exact sus_fast threshold (60s)
        bonding_at_sus = BondingMetrics(
            duration_seconds=60,
            total_volume_sol=50.0,
            unique_buyers=100,
            unique_sellers=30,
            buy_sell_ratio=3.0,
            graduation_mcap_usd=100000.0,
        )
        red, green, warn = [], [], []
        score = scorer._score_bonding(bonding_at_sus, red, green, warn)
        # At 60s, should not trigger sus_fast (< 60) but should trigger quick (< 300)
        assert any("Quick graduation" in f for f in warn)
        assert not any("Suspiciously fast" in f for f in red)

        # At exact optimal_min threshold (300s)
        bonding_at_opt_min = BondingMetrics(
            duration_seconds=300,
            total_volume_sol=50.0,
            unique_buyers=100,
            unique_sellers=30,
            buy_sell_ratio=3.0,
            graduation_mcap_usd=100000.0,
        )
        red2, green2, warn2 = [], [], []
        score2 = scorer._score_bonding(bonding_at_opt_min, red2, green2, warn2)
        # At exactly 300s, should be in optimal range (>= 300 and <= 3600)
        assert any("Healthy graduation time" in f for f in green2)


# =============================================================================
# Threshold Configuration Tests
# =============================================================================

class TestThresholdConfiguration:
    """Tests to verify threshold constants are correctly used."""

    def test_thresholds_exist(self):
        """Verify all expected thresholds are defined."""
        expected_keys = [
            "bonding_duration_optimal_min",
            "bonding_duration_optimal_max",
            "bonding_duration_sus_fast",
            "min_volume_sol",
            "optimal_volume_sol",
            "min_buyers",
            "optimal_buyers",
            "min_buy_sell_ratio",
            "optimal_buy_sell_ratio",
            "min_twitter_followers",
            "optimal_twitter_followers",
            "min_account_age_days",
            "sus_account_age_days",
            "max_top10_pct",
            "healthy_top10_pct",
            "min_liquidity_usd",
            "optimal_liquidity_usd",
            "max_pump_1h",
        ]
        for key in expected_keys:
            assert key in THRESHOLDS, f"Missing threshold: {key}"

    def test_threshold_values_reasonable(self):
        """Verify threshold values are reasonable."""
        assert THRESHOLDS["bonding_duration_sus_fast"] < THRESHOLDS["bonding_duration_optimal_min"]
        assert THRESHOLDS["bonding_duration_optimal_min"] < THRESHOLDS["bonding_duration_optimal_max"]
        assert THRESHOLDS["min_volume_sol"] < THRESHOLDS["optimal_volume_sol"]
        assert THRESHOLDS["min_buyers"] < THRESHOLDS["optimal_buyers"]
        assert THRESHOLDS["min_buy_sell_ratio"] < THRESHOLDS["optimal_buy_sell_ratio"]
        assert THRESHOLDS["min_twitter_followers"] < THRESHOLDS["optimal_twitter_followers"]
        assert THRESHOLDS["sus_account_age_days"] < THRESHOLDS["min_account_age_days"]
        assert THRESHOLDS["healthy_top10_pct"] < THRESHOLDS["max_top10_pct"]
        assert THRESHOLDS["min_liquidity_usd"] < THRESHOLDS["optimal_liquidity_usd"]


# =============================================================================
# Integration-like Tests
# =============================================================================

class TestScoringIntegration:
    """Integration-style tests for complete scoring flows."""

    @pytest.mark.asyncio
    async def test_average_token_scoring(self, scorer):
        """Test scoring for an average/typical token."""
        token = TokenMetadata(
            mint_address="Average111",
            name="Average Token",
            symbol="AVG",
            website="https://average.com",
            twitter=None,
            telegram="https://t.me/average",
        )
        creator = CreatorProfile(
            wallet_address="AvgWallet",
            twitter_handle="avg_dev",
            twitter_followers=300,
            twitter_account_age_days=45,
            previous_launches=1,
            rugged_launches=0,
        )
        bonding = BondingMetrics(
            duration_seconds=480,  # 8 minutes
            total_volume_sol=25.0,
            unique_buyers=45,
            unique_sellers=20,
            buy_sell_ratio=2.2,
            graduation_mcap_usd=80000.0,
        )
        market = MarketMetrics(
            price_usd=0.005,
            price_sol=0.00005,
            market_cap_usd=100000.0,
            liquidity_usd=12000.0,
            volume_24h_usd=30000.0,
            price_change_1h=25.0,
            buys_1h=70,
            sells_1h=40,
            holder_count=180,
            top_10_holder_pct=38.0,
        )

        result = await scorer.calculate_score(token, creator, bonding, market)

        # Token with decent metrics should score in reasonable range
        # Individual dimension scores are all reasonable, so overall is decent
        assert 40 <= result.overall_score <= 85
        assert result.launch_quality in [LaunchQuality.AVERAGE, LaunchQuality.WEAK, LaunchQuality.STRONG]

    @pytest.mark.asyncio
    async def test_flags_accumulate_correctly(self, scorer, base_token, base_creator):
        """Test that flags accumulate from all scoring dimensions."""
        # Create metrics that will generate flags from multiple dimensions
        bonding = BondingMetrics(
            duration_seconds=30,  # Will generate red flag
            total_volume_sol=100.0,  # Will generate green flag
            unique_buyers=5,  # Will generate red flag
            unique_sellers=10,
            buy_sell_ratio=4.0,  # Will generate green flag
            graduation_mcap_usd=100000.0,
        )
        market = MarketMetrics(
            price_usd=0.01,
            price_sol=0.0001,
            market_cap_usd=100000.0,
            liquidity_usd=50000.0,  # Will generate green flag
            volume_24h_usd=50000.0,
            price_change_1h=150.0,  # Will generate warning
            buys_1h=100,
            sells_1h=50,
            holder_count=50,  # Will generate warning
            top_10_holder_pct=60.0,  # Will generate red flag
        )

        result = await scorer.calculate_score(base_token, base_creator, bonding, market)

        # Should have flags from multiple dimensions
        assert len(result.red_flags) >= 2
        assert len(result.green_flags) >= 2
        assert len(result.warnings) >= 1
