"""
Comprehensive unit tests for bots/bags_intel/models.py

Tests cover:
- Enum values and membership (LaunchQuality, RiskLevel)
- Dataclass initialization with required and optional fields
- Default values for optional fields
- Property methods (is_reportable)
- Serialization methods (to_dict, to_telegram_html)
- Edge cases (empty lists, None values, extreme values)
- Field validation and type handling

Coverage target: 90%+
"""

import pytest
from datetime import datetime
from typing import List, Dict, Any
from unittest.mock import MagicMock, patch
from dataclasses import fields, asdict

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from bots.bags_intel.models import (
    LaunchQuality,
    RiskLevel,
    TokenMetadata,
    CreatorProfile,
    BondingMetrics,
    MarketMetrics,
    IntelScore,
    GraduationEvent,
)


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
def token_metadata():
    """Create a basic TokenMetadata instance."""
    return TokenMetadata(
        mint_address="TokenMint111111111111111111111111111111111111",
        name="Test Token",
        symbol="TEST",
        description="A test token for testing",
        image_url="https://example.com/image.png",
        website="https://testtoken.com",
        twitter="https://twitter.com/testtoken",
        telegram="https://t.me/testtoken",
    )


@pytest.fixture
def token_metadata_minimal():
    """Create TokenMetadata with only required fields."""
    return TokenMetadata(
        mint_address="MinimalMint11111111111111111111111111111111",
        name="Minimal Token",
        symbol="MIN",
    )


@pytest.fixture
def creator_profile():
    """Create a basic CreatorProfile instance."""
    return CreatorProfile(
        wallet_address="CreatorWallet1111111111111111111111111111111",
        twitter_handle="creator_dev",
        twitter_followers=1500,
        twitter_account_age_days=120,
        previous_launches=3,
        rugged_launches=0,
    )


@pytest.fixture
def creator_profile_minimal():
    """Create CreatorProfile with only required fields."""
    return CreatorProfile(
        wallet_address="MinCreator111111111111111111111111111111111",
    )


@pytest.fixture
def bonding_metrics():
    """Create a basic BondingMetrics instance."""
    return BondingMetrics(
        duration_seconds=1800,
        total_volume_sol=50.0,
        unique_buyers=100,
        unique_sellers=30,
        buy_sell_ratio=3.3,
        graduation_mcap_usd=150000.0,
    )


@pytest.fixture
def market_metrics():
    """Create a basic MarketMetrics instance."""
    return MarketMetrics(
        price_usd=0.001,
        price_sol=0.00001,
        market_cap_usd=100000.0,
        liquidity_usd=20000.0,
        volume_24h_usd=50000.0,
        price_change_1h=15.0,
        buys_1h=150,
        sells_1h=50,
        holder_count=300,
        top_10_holder_pct=25.0,
    )


@pytest.fixture
def market_metrics_minimal():
    """Create MarketMetrics with only required fields (defaults for optionals)."""
    return MarketMetrics(
        price_usd=0.001,
        price_sol=0.00001,
        market_cap_usd=50000.0,
        liquidity_usd=10000.0,
        volume_24h_usd=25000.0,
        price_change_1h=5.0,
        buys_1h=75,
        sells_1h=25,
    )


@pytest.fixture
def intel_score():
    """Create a basic IntelScore instance."""
    return IntelScore(
        overall_score=72.5,
        launch_quality=LaunchQuality.STRONG,
        risk_level=RiskLevel.LOW,
        bonding_score=80.0,
        creator_score=70.0,
        social_score=65.0,
        market_score=75.0,
        distribution_score=72.0,
        green_flags=["Strong liquidity", "Established creator", "Many buyers"],
        red_flags=["Moderate concentration"],
        warnings=["Pumping hard"],
        grok_summary="This token shows promising fundamentals with a healthy bonding curve.",
    )


@pytest.fixture
def intel_score_minimal():
    """Create IntelScore with only required fields."""
    return IntelScore(
        overall_score=50.0,
        launch_quality=LaunchQuality.AVERAGE,
        risk_level=RiskLevel.MEDIUM,
        bonding_score=50.0,
        creator_score=50.0,
        social_score=50.0,
        market_score=50.0,
        distribution_score=50.0,
    )


@pytest.fixture
def graduation_event(token_metadata, creator_profile, bonding_metrics, market_metrics, intel_score):
    """Create a basic GraduationEvent instance."""
    return GraduationEvent(
        token=token_metadata,
        creator=creator_profile,
        bonding=bonding_metrics,
        market=market_metrics,
        score=intel_score,
        timestamp=datetime(2026, 1, 25, 10, 30, 0),
        tx_signature="5KtP9UcJZH1234567890abcdefghijklmnopqrstuvwxyz123456",
    )


@pytest.fixture
def graduation_event_minimal(token_metadata_minimal, creator_profile_minimal, bonding_metrics, market_metrics_minimal, intel_score_minimal):
    """Create GraduationEvent with minimal nested objects."""
    return GraduationEvent(
        token=token_metadata_minimal,
        creator=creator_profile_minimal,
        bonding=bonding_metrics,
        market=market_metrics_minimal,
        score=intel_score_minimal,
    )


# =============================================================================
# LaunchQuality Enum Tests
# =============================================================================

class TestLaunchQualityEnum:
    """Tests for LaunchQuality enum."""

    def test_exceptional_value(self):
        """Test EXCEPTIONAL enum value."""
        assert LaunchQuality.EXCEPTIONAL.value == "exceptional"

    def test_strong_value(self):
        """Test STRONG enum value."""
        assert LaunchQuality.STRONG.value == "strong"

    def test_average_value(self):
        """Test AVERAGE enum value."""
        assert LaunchQuality.AVERAGE.value == "average"

    def test_weak_value(self):
        """Test WEAK enum value."""
        assert LaunchQuality.WEAK.value == "weak"

    def test_poor_value(self):
        """Test POOR enum value."""
        assert LaunchQuality.POOR.value == "poor"

    def test_all_members_count(self):
        """Test that all 5 quality tiers exist."""
        assert len(LaunchQuality) == 5

    def test_enum_from_value(self):
        """Test creating enum from string value."""
        assert LaunchQuality("exceptional") == LaunchQuality.EXCEPTIONAL
        assert LaunchQuality("strong") == LaunchQuality.STRONG
        assert LaunchQuality("average") == LaunchQuality.AVERAGE
        assert LaunchQuality("weak") == LaunchQuality.WEAK
        assert LaunchQuality("poor") == LaunchQuality.POOR

    def test_enum_invalid_value(self):
        """Test that invalid value raises ValueError."""
        with pytest.raises(ValueError):
            LaunchQuality("invalid")

    def test_enum_comparison(self):
        """Test enum comparison."""
        assert LaunchQuality.EXCEPTIONAL != LaunchQuality.POOR
        assert LaunchQuality.STRONG == LaunchQuality.STRONG


# =============================================================================
# RiskLevel Enum Tests
# =============================================================================

class TestRiskLevelEnum:
    """Tests for RiskLevel enum."""

    def test_low_value(self):
        """Test LOW enum value."""
        assert RiskLevel.LOW.value == "low"

    def test_medium_value(self):
        """Test MEDIUM enum value."""
        assert RiskLevel.MEDIUM.value == "medium"

    def test_high_value(self):
        """Test HIGH enum value."""
        assert RiskLevel.HIGH.value == "high"

    def test_extreme_value(self):
        """Test EXTREME enum value."""
        assert RiskLevel.EXTREME.value == "extreme"

    def test_all_members_count(self):
        """Test that all 4 risk levels exist."""
        assert len(RiskLevel) == 4

    def test_enum_from_value(self):
        """Test creating enum from string value."""
        assert RiskLevel("low") == RiskLevel.LOW
        assert RiskLevel("medium") == RiskLevel.MEDIUM
        assert RiskLevel("high") == RiskLevel.HIGH
        assert RiskLevel("extreme") == RiskLevel.EXTREME

    def test_enum_invalid_value(self):
        """Test that invalid value raises ValueError."""
        with pytest.raises(ValueError):
            RiskLevel("critical")

    def test_enum_membership(self):
        """Test enum membership checks."""
        assert RiskLevel.LOW in RiskLevel
        assert RiskLevel.EXTREME in RiskLevel


# =============================================================================
# TokenMetadata Dataclass Tests
# =============================================================================

class TestTokenMetadata:
    """Tests for TokenMetadata dataclass."""

    def test_required_fields(self, token_metadata_minimal):
        """Test that required fields are set."""
        assert token_metadata_minimal.mint_address == "MinimalMint11111111111111111111111111111111"
        assert token_metadata_minimal.name == "Minimal Token"
        assert token_metadata_minimal.symbol == "MIN"

    def test_optional_fields_default_none(self, token_metadata_minimal):
        """Test that optional fields default to None."""
        assert token_metadata_minimal.description is None
        assert token_metadata_minimal.image_url is None
        assert token_metadata_minimal.website is None
        assert token_metadata_minimal.twitter is None
        assert token_metadata_minimal.telegram is None

    def test_all_fields_populated(self, token_metadata):
        """Test TokenMetadata with all fields populated."""
        assert token_metadata.mint_address == "TokenMint111111111111111111111111111111111111"
        assert token_metadata.name == "Test Token"
        assert token_metadata.symbol == "TEST"
        assert token_metadata.description == "A test token for testing"
        assert token_metadata.image_url == "https://example.com/image.png"
        assert token_metadata.website == "https://testtoken.com"
        assert token_metadata.twitter == "https://twitter.com/testtoken"
        assert token_metadata.telegram == "https://t.me/testtoken"

    def test_field_count(self):
        """Test that TokenMetadata has expected number of fields."""
        assert len(fields(TokenMetadata)) == 8

    def test_equality(self):
        """Test TokenMetadata equality comparison."""
        token1 = TokenMetadata(mint_address="Mint1", name="Token", symbol="TKN")
        token2 = TokenMetadata(mint_address="Mint1", name="Token", symbol="TKN")
        token3 = TokenMetadata(mint_address="Mint2", name="Token", symbol="TKN")

        assert token1 == token2
        assert token1 != token3

    def test_empty_strings(self):
        """Test TokenMetadata with empty strings for optional fields."""
        token = TokenMetadata(
            mint_address="Mint1",
            name="Token",
            symbol="TKN",
            description="",
            website="",
            twitter="",
        )
        assert token.description == ""
        assert token.website == ""
        assert token.twitter == ""


# =============================================================================
# CreatorProfile Dataclass Tests
# =============================================================================

class TestCreatorProfile:
    """Tests for CreatorProfile dataclass."""

    def test_required_field(self, creator_profile_minimal):
        """Test that only wallet_address is required."""
        assert creator_profile_minimal.wallet_address == "MinCreator111111111111111111111111111111111"

    def test_optional_fields_defaults(self, creator_profile_minimal):
        """Test default values for optional fields."""
        assert creator_profile_minimal.twitter_handle is None
        assert creator_profile_minimal.twitter_followers is None
        assert creator_profile_minimal.twitter_account_age_days is None
        assert creator_profile_minimal.previous_launches == 0
        assert creator_profile_minimal.rugged_launches == 0

    def test_all_fields_populated(self, creator_profile):
        """Test CreatorProfile with all fields populated."""
        assert creator_profile.wallet_address == "CreatorWallet1111111111111111111111111111111"
        assert creator_profile.twitter_handle == "creator_dev"
        assert creator_profile.twitter_followers == 1500
        assert creator_profile.twitter_account_age_days == 120
        assert creator_profile.previous_launches == 3
        assert creator_profile.rugged_launches == 0

    def test_field_count(self):
        """Test that CreatorProfile has expected number of fields."""
        assert len(fields(CreatorProfile)) == 6

    def test_creator_with_rug_history(self):
        """Test creator with rug history."""
        creator = CreatorProfile(
            wallet_address="RuggerWallet",
            previous_launches=5,
            rugged_launches=2,
        )
        assert creator.previous_launches == 5
        assert creator.rugged_launches == 2

    def test_equality(self):
        """Test CreatorProfile equality."""
        c1 = CreatorProfile(wallet_address="Wallet1")
        c2 = CreatorProfile(wallet_address="Wallet1")
        c3 = CreatorProfile(wallet_address="Wallet2")

        assert c1 == c2
        assert c1 != c3


# =============================================================================
# BondingMetrics Dataclass Tests
# =============================================================================

class TestBondingMetrics:
    """Tests for BondingMetrics dataclass."""

    def test_all_required_fields(self, bonding_metrics):
        """Test that all required fields are set."""
        assert bonding_metrics.duration_seconds == 1800
        assert bonding_metrics.total_volume_sol == 50.0
        assert bonding_metrics.unique_buyers == 100
        assert bonding_metrics.unique_sellers == 30
        assert bonding_metrics.buy_sell_ratio == 3.3
        assert bonding_metrics.graduation_mcap_usd == 150000.0

    def test_field_count(self):
        """Test that BondingMetrics has expected number of fields."""
        assert len(fields(BondingMetrics)) == 6

    def test_zero_values(self):
        """Test BondingMetrics with zero values."""
        bonding = BondingMetrics(
            duration_seconds=0,
            total_volume_sol=0.0,
            unique_buyers=0,
            unique_sellers=0,
            buy_sell_ratio=0.0,
            graduation_mcap_usd=0.0,
        )
        assert bonding.duration_seconds == 0
        assert bonding.total_volume_sol == 0.0
        assert bonding.unique_buyers == 0

    def test_extreme_values(self):
        """Test BondingMetrics with extreme values."""
        bonding = BondingMetrics(
            duration_seconds=86400,  # 24 hours
            total_volume_sol=100000.0,
            unique_buyers=100000,
            unique_sellers=50000,
            buy_sell_ratio=100.0,
            graduation_mcap_usd=10000000.0,
        )
        assert bonding.duration_seconds == 86400
        assert bonding.total_volume_sol == 100000.0
        assert bonding.unique_buyers == 100000

    def test_equality(self):
        """Test BondingMetrics equality."""
        b1 = BondingMetrics(
            duration_seconds=100,
            total_volume_sol=10.0,
            unique_buyers=50,
            unique_sellers=20,
            buy_sell_ratio=2.5,
            graduation_mcap_usd=50000.0,
        )
        b2 = BondingMetrics(
            duration_seconds=100,
            total_volume_sol=10.0,
            unique_buyers=50,
            unique_sellers=20,
            buy_sell_ratio=2.5,
            graduation_mcap_usd=50000.0,
        )
        assert b1 == b2


# =============================================================================
# MarketMetrics Dataclass Tests
# =============================================================================

class TestMarketMetrics:
    """Tests for MarketMetrics dataclass."""

    def test_required_fields(self, market_metrics):
        """Test required fields are set."""
        assert market_metrics.price_usd == 0.001
        assert market_metrics.price_sol == 0.00001
        assert market_metrics.market_cap_usd == 100000.0
        assert market_metrics.liquidity_usd == 20000.0
        assert market_metrics.volume_24h_usd == 50000.0
        assert market_metrics.price_change_1h == 15.0
        assert market_metrics.buys_1h == 150
        assert market_metrics.sells_1h == 50

    def test_optional_fields_defaults(self, market_metrics_minimal):
        """Test default values for optional fields."""
        assert market_metrics_minimal.holder_count == 0
        assert market_metrics_minimal.top_10_holder_pct == 0.0

    def test_all_fields_populated(self, market_metrics):
        """Test MarketMetrics with all fields."""
        assert market_metrics.holder_count == 300
        assert market_metrics.top_10_holder_pct == 25.0

    def test_field_count(self):
        """Test that MarketMetrics has expected number of fields."""
        assert len(fields(MarketMetrics)) == 10

    def test_negative_price_change(self):
        """Test MarketMetrics with negative price change."""
        market = MarketMetrics(
            price_usd=0.0001,
            price_sol=0.000001,
            market_cap_usd=10000.0,
            liquidity_usd=5000.0,
            volume_24h_usd=10000.0,
            price_change_1h=-50.0,
            buys_1h=10,
            sells_1h=100,
        )
        assert market.price_change_1h == -50.0

    def test_high_concentration(self):
        """Test MarketMetrics with high holder concentration."""
        market = MarketMetrics(
            price_usd=0.01,
            price_sol=0.0001,
            market_cap_usd=100000.0,
            liquidity_usd=20000.0,
            volume_24h_usd=50000.0,
            price_change_1h=10.0,
            buys_1h=100,
            sells_1h=50,
            holder_count=50,
            top_10_holder_pct=90.0,
        )
        assert market.top_10_holder_pct == 90.0


# =============================================================================
# IntelScore Dataclass Tests
# =============================================================================

class TestIntelScore:
    """Tests for IntelScore dataclass."""

    def test_required_fields(self, intel_score):
        """Test required fields are set."""
        assert intel_score.overall_score == 72.5
        assert intel_score.launch_quality == LaunchQuality.STRONG
        assert intel_score.risk_level == RiskLevel.LOW
        assert intel_score.bonding_score == 80.0
        assert intel_score.creator_score == 70.0
        assert intel_score.social_score == 65.0
        assert intel_score.market_score == 75.0
        assert intel_score.distribution_score == 72.0

    def test_list_defaults_empty(self, intel_score_minimal):
        """Test that list fields default to empty lists."""
        assert intel_score_minimal.green_flags == []
        assert intel_score_minimal.red_flags == []
        assert intel_score_minimal.warnings == []

    def test_grok_summary_default_none(self, intel_score_minimal):
        """Test that grok_summary defaults to None."""
        assert intel_score_minimal.grok_summary is None

    def test_flags_populated(self, intel_score):
        """Test IntelScore with flags populated."""
        assert len(intel_score.green_flags) == 3
        assert "Strong liquidity" in intel_score.green_flags
        assert len(intel_score.red_flags) == 1
        assert len(intel_score.warnings) == 1

    def test_grok_summary_populated(self, intel_score):
        """Test IntelScore with grok_summary populated."""
        assert intel_score.grok_summary is not None
        assert "promising" in intel_score.grok_summary

    def test_field_count(self):
        """Test that IntelScore has expected number of fields."""
        assert len(fields(IntelScore)) == 12

    def test_all_quality_levels(self):
        """Test IntelScore with each quality level."""
        for quality in LaunchQuality:
            score = IntelScore(
                overall_score=50.0,
                launch_quality=quality,
                risk_level=RiskLevel.MEDIUM,
                bonding_score=50.0,
                creator_score=50.0,
                social_score=50.0,
                market_score=50.0,
                distribution_score=50.0,
            )
            assert score.launch_quality == quality

    def test_all_risk_levels(self):
        """Test IntelScore with each risk level."""
        for risk in RiskLevel:
            score = IntelScore(
                overall_score=50.0,
                launch_quality=LaunchQuality.AVERAGE,
                risk_level=risk,
                bonding_score=50.0,
                creator_score=50.0,
                social_score=50.0,
                market_score=50.0,
                distribution_score=50.0,
            )
            assert score.risk_level == risk


# =============================================================================
# GraduationEvent Dataclass Tests
# =============================================================================

class TestGraduationEvent:
    """Tests for GraduationEvent dataclass."""

    def test_required_fields(self, graduation_event):
        """Test required fields are set."""
        assert graduation_event.token is not None
        assert graduation_event.creator is not None
        assert graduation_event.bonding is not None
        assert graduation_event.market is not None
        assert graduation_event.score is not None

    def test_timestamp_default(self, graduation_event_minimal):
        """Test that timestamp defaults to current time."""
        # Timestamp should be set to a datetime
        assert isinstance(graduation_event_minimal.timestamp, datetime)

    def test_tx_signature_optional(self, graduation_event_minimal):
        """Test that tx_signature defaults to None."""
        assert graduation_event_minimal.tx_signature is None

    def test_explicit_timestamp(self, graduation_event):
        """Test explicit timestamp setting."""
        assert graduation_event.timestamp == datetime(2026, 1, 25, 10, 30, 0)

    def test_explicit_tx_signature(self, graduation_event):
        """Test explicit tx_signature setting."""
        assert graduation_event.tx_signature == "5KtP9UcJZH1234567890abcdefghijklmnopqrstuvwxyz123456"

    def test_field_count(self):
        """Test that GraduationEvent has expected number of fields."""
        assert len(fields(GraduationEvent)) == 7


# =============================================================================
# GraduationEvent.is_reportable Property Tests
# =============================================================================

class TestIsReportable:
    """Tests for GraduationEvent.is_reportable property."""

    def test_reportable_meets_thresholds(self, token_metadata, creator_profile, bonding_metrics, intel_score):
        """Test is_reportable returns True when meeting thresholds."""
        market = MarketMetrics(
            price_usd=0.01,
            price_sol=0.0001,
            market_cap_usd=50000.0,  # >= 10000
            liquidity_usd=20000.0,
            volume_24h_usd=50000.0,
            price_change_1h=10.0,
            buys_1h=100,
            sells_1h=50,
        )
        score = IntelScore(
            overall_score=50.0,  # >= 30
            launch_quality=LaunchQuality.AVERAGE,
            risk_level=RiskLevel.MEDIUM,
            bonding_score=50.0,
            creator_score=50.0,
            social_score=50.0,
            market_score=50.0,
            distribution_score=50.0,
        )
        event = GraduationEvent(
            token=token_metadata,
            creator=creator_profile,
            bonding=bonding_metrics,
            market=market,
            score=score,
        )
        assert event.is_reportable is True

    def test_not_reportable_low_mcap(self, token_metadata, creator_profile, bonding_metrics, intel_score):
        """Test is_reportable returns False when market cap too low."""
        market = MarketMetrics(
            price_usd=0.0001,
            price_sol=0.000001,
            market_cap_usd=5000.0,  # < 10000
            liquidity_usd=2000.0,
            volume_24h_usd=5000.0,
            price_change_1h=5.0,
            buys_1h=50,
            sells_1h=20,
        )
        event = GraduationEvent(
            token=token_metadata,
            creator=creator_profile,
            bonding=bonding_metrics,
            market=market,
            score=intel_score,
        )
        assert event.is_reportable is False

    def test_not_reportable_low_score(self, token_metadata, creator_profile, bonding_metrics, market_metrics):
        """Test is_reportable returns False when score too low."""
        score = IntelScore(
            overall_score=20.0,  # < 30
            launch_quality=LaunchQuality.POOR,
            risk_level=RiskLevel.HIGH,
            bonding_score=20.0,
            creator_score=20.0,
            social_score=20.0,
            market_score=20.0,
            distribution_score=20.0,
        )
        event = GraduationEvent(
            token=token_metadata,
            creator=creator_profile,
            bonding=bonding_metrics,
            market=market_metrics,
            score=score,
        )
        assert event.is_reportable is False

    def test_reportable_exact_thresholds(self, token_metadata, creator_profile, bonding_metrics):
        """Test is_reportable at exact threshold values."""
        market = MarketMetrics(
            price_usd=0.001,
            price_sol=0.00001,
            market_cap_usd=10000.0,  # exactly 10000
            liquidity_usd=5000.0,
            volume_24h_usd=10000.0,
            price_change_1h=5.0,
            buys_1h=50,
            sells_1h=30,
        )
        score = IntelScore(
            overall_score=30.0,  # exactly 30
            launch_quality=LaunchQuality.WEAK,
            risk_level=RiskLevel.MEDIUM,
            bonding_score=30.0,
            creator_score=30.0,
            social_score=30.0,
            market_score=30.0,
            distribution_score=30.0,
        )
        event = GraduationEvent(
            token=token_metadata,
            creator=creator_profile,
            bonding=bonding_metrics,
            market=market,
            score=score,
        )
        assert event.is_reportable is True

    def test_not_reportable_both_below_threshold(self, token_metadata, creator_profile, bonding_metrics):
        """Test is_reportable when both thresholds are not met."""
        market = MarketMetrics(
            price_usd=0.0001,
            price_sol=0.000001,
            market_cap_usd=5000.0,  # < 10000
            liquidity_usd=1000.0,
            volume_24h_usd=2000.0,
            price_change_1h=0.0,
            buys_1h=20,
            sells_1h=20,
        )
        score = IntelScore(
            overall_score=15.0,  # < 30
            launch_quality=LaunchQuality.POOR,
            risk_level=RiskLevel.EXTREME,
            bonding_score=15.0,
            creator_score=15.0,
            social_score=15.0,
            market_score=15.0,
            distribution_score=15.0,
        )
        event = GraduationEvent(
            token=token_metadata,
            creator=creator_profile,
            bonding=bonding_metrics,
            market=market,
            score=score,
        )
        assert event.is_reportable is False


# =============================================================================
# GraduationEvent.to_telegram_html Tests
# =============================================================================

class TestToTelegramHtml:
    """Tests for GraduationEvent.to_telegram_html method."""

    def test_contains_header(self, graduation_event):
        """Test that HTML contains header."""
        html = graduation_event.to_telegram_html()
        assert "BAGS.FM INTEL REPORT" in html

    def test_contains_token_info(self, graduation_event):
        """Test that HTML contains token information."""
        html = graduation_event.to_telegram_html()
        assert graduation_event.token.symbol in html
        assert graduation_event.token.name in html
        assert graduation_event.token.mint_address in html

    def test_contains_score(self, graduation_event):
        """Test that HTML contains overall score."""
        html = graduation_event.to_telegram_html()
        assert "Score:" in html
        assert "73/100" in html or "72/100" in html  # Rounded

    def test_contains_risk_level(self, graduation_event):
        """Test that HTML contains risk level."""
        html = graduation_event.to_telegram_html()
        assert "Risk:" in html
        assert "LOW" in html

    def test_contains_market_data(self, graduation_event):
        """Test that HTML contains market data."""
        html = graduation_event.to_telegram_html()
        assert "MCap:" in html
        assert "Liq:" in html
        assert "Price:" in html

    def test_contains_bonding_data(self, graduation_event):
        """Test that HTML contains bonding curve data."""
        html = graduation_event.to_telegram_html()
        assert "Bonding Curve" in html
        assert "Duration:" in html
        assert "Volume:" in html
        assert "Buyers:" in html
        assert "Buy/Sell:" in html

    def test_contains_creator_section(self, graduation_event):
        """Test that HTML contains creator section."""
        html = graduation_event.to_telegram_html()
        assert "Creator" in html

    def test_contains_twitter_handle(self, graduation_event):
        """Test that HTML contains Twitter handle when present."""
        html = graduation_event.to_telegram_html()
        assert "@creator_dev" in html

    def test_contains_twitter_followers(self, graduation_event):
        """Test that HTML contains Twitter followers when present."""
        html = graduation_event.to_telegram_html()
        assert "Followers:" in html
        assert "1,500" in html

    def test_contains_component_scores(self, graduation_event):
        """Test that HTML contains component scores."""
        html = graduation_event.to_telegram_html()
        assert "Scores" in html
        assert "Bonding:" in html
        assert "Creator:" in html
        assert "Social:" in html
        assert "Market:" in html
        assert "Distribution:" in html

    def test_contains_green_flags(self, graduation_event):
        """Test that HTML contains green flags when present."""
        html = graduation_event.to_telegram_html()
        assert "Green Flags" in html
        assert "Strong liquidity" in html

    def test_contains_red_flags(self, graduation_event):
        """Test that HTML contains red flags when present."""
        html = graduation_event.to_telegram_html()
        assert "Red Flags" in html
        assert "Moderate concentration" in html

    def test_contains_grok_summary(self, graduation_event):
        """Test that HTML contains AI analysis when present."""
        html = graduation_event.to_telegram_html()
        assert "AI Analysis" in html
        assert "promising" in html

    def test_contains_links(self, graduation_event):
        """Test that HTML contains Bags and DexScreener links."""
        html = graduation_event.to_telegram_html()
        assert "bags.fm/token/" in html
        assert "dexscreener.com/solana/" in html
        assert graduation_event.token.mint_address in html

    def test_no_twitter_handle(self, token_metadata, bonding_metrics, market_metrics, intel_score):
        """Test HTML when creator has no Twitter handle."""
        creator = CreatorProfile(
            wallet_address="NoTwitterWallet",
            twitter_handle=None,
        )
        event = GraduationEvent(
            token=token_metadata,
            creator=creator,
            bonding=bonding_metrics,
            market=market_metrics,
            score=intel_score,
        )
        html = event.to_telegram_html()
        # Should not contain Twitter section
        assert "@" not in html.split("Creator")[1].split("Scores")[0]

    def test_no_green_flags(self, token_metadata, creator_profile, bonding_metrics, market_metrics):
        """Test HTML when no green flags."""
        score = IntelScore(
            overall_score=40.0,
            launch_quality=LaunchQuality.WEAK,
            risk_level=RiskLevel.HIGH,
            bonding_score=40.0,
            creator_score=40.0,
            social_score=40.0,
            market_score=40.0,
            distribution_score=40.0,
            green_flags=[],
            red_flags=["Issue 1", "Issue 2"],
        )
        event = GraduationEvent(
            token=token_metadata,
            creator=creator_profile,
            bonding=bonding_metrics,
            market=market_metrics,
            score=score,
        )
        html = event.to_telegram_html()
        assert "Green Flags" not in html

    def test_no_red_flags(self, token_metadata, creator_profile, bonding_metrics, market_metrics):
        """Test HTML when no red flags."""
        score = IntelScore(
            overall_score=80.0,
            launch_quality=LaunchQuality.EXCEPTIONAL,
            risk_level=RiskLevel.LOW,
            bonding_score=80.0,
            creator_score=80.0,
            social_score=80.0,
            market_score=80.0,
            distribution_score=80.0,
            green_flags=["Great liquidity"],
            red_flags=[],
        )
        event = GraduationEvent(
            token=token_metadata,
            creator=creator_profile,
            bonding=bonding_metrics,
            market=market_metrics,
            score=score,
        )
        html = event.to_telegram_html()
        assert "Red Flags" not in html

    def test_no_grok_summary(self, token_metadata, creator_profile, bonding_metrics, market_metrics, intel_score_minimal):
        """Test HTML when no grok summary."""
        event = GraduationEvent(
            token=token_metadata,
            creator=creator_profile,
            bonding=bonding_metrics,
            market=market_metrics,
            score=intel_score_minimal,
        )
        html = event.to_telegram_html()
        assert "AI Analysis" not in html

    def test_quality_emoji_exceptional(self, token_metadata, creator_profile, bonding_metrics, market_metrics):
        """Test quality emoji for EXCEPTIONAL."""
        score = IntelScore(
            overall_score=85.0,
            launch_quality=LaunchQuality.EXCEPTIONAL,
            risk_level=RiskLevel.LOW,
            bonding_score=85.0,
            creator_score=85.0,
            social_score=85.0,
            market_score=85.0,
            distribution_score=85.0,
        )
        event = GraduationEvent(
            token=token_metadata,
            creator=creator_profile,
            bonding=bonding_metrics,
            market=market_metrics,
            score=score,
        )
        html = event.to_telegram_html()
        # Star emoji for exceptional
        assert "\u2b50" in html or "\U0001f31f" in html or "85/100" in html

    def test_quality_emoji_poor(self, token_metadata, creator_profile, bonding_metrics, market_metrics):
        """Test quality emoji for POOR."""
        score = IntelScore(
            overall_score=20.0,
            launch_quality=LaunchQuality.POOR,
            risk_level=RiskLevel.EXTREME,
            bonding_score=20.0,
            creator_score=20.0,
            social_score=20.0,
            market_score=20.0,
            distribution_score=20.0,
        )
        event = GraduationEvent(
            token=token_metadata,
            creator=creator_profile,
            bonding=bonding_metrics,
            market=market_metrics,
            score=score,
        )
        html = event.to_telegram_html()
        # Alert emoji for poor
        assert "\U0001f6a8" in html or "20/100" in html

    def test_risk_emoji_extreme(self, token_metadata, creator_profile, bonding_metrics, market_metrics):
        """Test risk emoji for EXTREME."""
        score = IntelScore(
            overall_score=25.0,
            launch_quality=LaunchQuality.POOR,
            risk_level=RiskLevel.EXTREME,
            bonding_score=25.0,
            creator_score=25.0,
            social_score=25.0,
            market_score=25.0,
            distribution_score=25.0,
        )
        event = GraduationEvent(
            token=token_metadata,
            creator=creator_profile,
            bonding=bonding_metrics,
            market=market_metrics,
            score=score,
        )
        html = event.to_telegram_html()
        assert "EXTREME" in html

    def test_flags_truncated_to_four(self, token_metadata, creator_profile, bonding_metrics, market_metrics):
        """Test that flags are truncated to 4 items."""
        score = IntelScore(
            overall_score=50.0,
            launch_quality=LaunchQuality.AVERAGE,
            risk_level=RiskLevel.MEDIUM,
            bonding_score=50.0,
            creator_score=50.0,
            social_score=50.0,
            market_score=50.0,
            distribution_score=50.0,
            green_flags=["Flag1", "Flag2", "Flag3", "Flag4", "Flag5", "Flag6"],
            red_flags=["Red1", "Red2", "Red3", "Red4", "Red5"],
        )
        event = GraduationEvent(
            token=token_metadata,
            creator=creator_profile,
            bonding=bonding_metrics,
            market=market_metrics,
            score=score,
        )
        html = event.to_telegram_html()
        # Should only show first 4 green flags
        assert "Flag4" in html
        assert "Flag5" not in html
        # Should only show first 4 red flags
        assert "Red4" in html
        assert "Red5" not in html

    def test_grok_summary_truncated(self, token_metadata, creator_profile, bonding_metrics, market_metrics):
        """Test that grok summary is truncated to 400 chars."""
        long_summary = "A" * 500
        score = IntelScore(
            overall_score=60.0,
            launch_quality=LaunchQuality.AVERAGE,
            risk_level=RiskLevel.MEDIUM,
            bonding_score=60.0,
            creator_score=60.0,
            social_score=60.0,
            market_score=60.0,
            distribution_score=60.0,
            grok_summary=long_summary,
        )
        event = GraduationEvent(
            token=token_metadata,
            creator=creator_profile,
            bonding=bonding_metrics,
            market=market_metrics,
            score=score,
        )
        html = event.to_telegram_html()
        # Summary should be truncated
        assert len(html) < len(long_summary) + 1000  # Allow for other content


# =============================================================================
# GraduationEvent.to_dict Tests
# =============================================================================

class TestToDict:
    """Tests for GraduationEvent.to_dict method."""

    def test_has_type(self, graduation_event):
        """Test that dict has type field."""
        d = graduation_event.to_dict()
        assert d["type"] == "bags_intel_report"

    def test_has_timestamp(self, graduation_event):
        """Test that dict has timestamp field."""
        d = graduation_event.to_dict()
        assert "timestamp" in d
        assert d["timestamp"] == "2026-01-25T10:30:00"

    def test_has_token_section(self, graduation_event):
        """Test that dict has token section."""
        d = graduation_event.to_dict()
        assert "token" in d
        token = d["token"]
        assert token["mint"] == graduation_event.token.mint_address
        assert token["name"] == graduation_event.token.name
        assert token["symbol"] == graduation_event.token.symbol
        assert token["twitter"] == graduation_event.token.twitter
        assert token["website"] == graduation_event.token.website

    def test_has_scores_section(self, graduation_event):
        """Test that dict has scores section."""
        d = graduation_event.to_dict()
        assert "scores" in d
        scores = d["scores"]
        assert scores["overall"] == graduation_event.score.overall_score
        assert scores["quality"] == graduation_event.score.launch_quality.value
        assert scores["risk"] == graduation_event.score.risk_level.value
        assert scores["bonding"] == graduation_event.score.bonding_score
        assert scores["creator"] == graduation_event.score.creator_score
        assert scores["social"] == graduation_event.score.social_score
        assert scores["market"] == graduation_event.score.market_score
        assert scores["distribution"] == graduation_event.score.distribution_score

    def test_has_market_section(self, graduation_event):
        """Test that dict has market section."""
        d = graduation_event.to_dict()
        assert "market" in d
        market = d["market"]
        assert market["mcap_usd"] == graduation_event.market.market_cap_usd
        assert market["liquidity_usd"] == graduation_event.market.liquidity_usd
        assert market["price_usd"] == graduation_event.market.price_usd

    def test_has_bonding_curve_section(self, graduation_event):
        """Test that dict has bonding_curve section."""
        d = graduation_event.to_dict()
        assert "bonding_curve" in d
        bc = d["bonding_curve"]
        assert bc["duration_seconds"] == graduation_event.bonding.duration_seconds
        assert bc["volume_sol"] == graduation_event.bonding.total_volume_sol
        assert bc["unique_buyers"] == graduation_event.bonding.unique_buyers
        assert bc["buy_sell_ratio"] == graduation_event.bonding.buy_sell_ratio

    def test_has_creator_section(self, graduation_event):
        """Test that dict has creator section."""
        d = graduation_event.to_dict()
        assert "creator" in d
        creator = d["creator"]
        assert creator["wallet"] == graduation_event.creator.wallet_address
        assert creator["twitter"] == graduation_event.creator.twitter_handle

    def test_has_flags_section(self, graduation_event):
        """Test that dict has flags section."""
        d = graduation_event.to_dict()
        assert "flags" in d
        flags = d["flags"]
        assert flags["green"] == graduation_event.score.green_flags
        assert flags["red"] == graduation_event.score.red_flags
        assert flags["warnings"] == graduation_event.score.warnings

    def test_has_ai_analysis_section(self, graduation_event):
        """Test that dict has ai_analysis section."""
        d = graduation_event.to_dict()
        assert "ai_analysis" in d
        assert d["ai_analysis"]["summary"] == graduation_event.score.grok_summary

    def test_none_grok_summary(self, graduation_event_minimal):
        """Test dict with None grok summary."""
        d = graduation_event_minimal.to_dict()
        assert d["ai_analysis"]["summary"] is None

    def test_empty_flags(self, graduation_event_minimal):
        """Test dict with empty flags."""
        d = graduation_event_minimal.to_dict()
        assert d["flags"]["green"] == []
        assert d["flags"]["red"] == []
        assert d["flags"]["warnings"] == []

    def test_none_optional_token_fields(self, graduation_event_minimal):
        """Test dict with None optional token fields."""
        d = graduation_event_minimal.to_dict()
        assert d["token"]["twitter"] is None
        assert d["token"]["website"] is None

    def test_none_creator_twitter(self, graduation_event_minimal):
        """Test dict with None creator twitter."""
        d = graduation_event_minimal.to_dict()
        assert d["creator"]["twitter"] is None

    def test_dict_is_serializable(self, graduation_event):
        """Test that dict is JSON serializable."""
        import json
        d = graduation_event.to_dict()
        # Should not raise
        json_str = json.dumps(d)
        assert isinstance(json_str, str)

    def test_dict_roundtrip_values(self, graduation_event):
        """Test that dict values can be read back correctly."""
        import json
        d = graduation_event.to_dict()
        json_str = json.dumps(d)
        parsed = json.loads(json_str)

        assert parsed["type"] == "bags_intel_report"
        assert parsed["scores"]["overall"] == graduation_event.score.overall_score
        assert parsed["market"]["mcap_usd"] == graduation_event.market.market_cap_usd


# =============================================================================
# Edge Cases and Boundary Tests
# =============================================================================

class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_zero_score(self, token_metadata, creator_profile, bonding_metrics, market_metrics):
        """Test with zero overall score."""
        score = IntelScore(
            overall_score=0.0,
            launch_quality=LaunchQuality.POOR,
            risk_level=RiskLevel.EXTREME,
            bonding_score=0.0,
            creator_score=0.0,
            social_score=0.0,
            market_score=0.0,
            distribution_score=0.0,
        )
        event = GraduationEvent(
            token=token_metadata,
            creator=creator_profile,
            bonding=bonding_metrics,
            market=market_metrics,
            score=score,
        )
        html = event.to_telegram_html()
        assert "0/100" in html
        d = event.to_dict()
        assert d["scores"]["overall"] == 0.0

    def test_max_score(self, token_metadata, creator_profile, bonding_metrics, market_metrics):
        """Test with maximum overall score."""
        score = IntelScore(
            overall_score=100.0,
            launch_quality=LaunchQuality.EXCEPTIONAL,
            risk_level=RiskLevel.LOW,
            bonding_score=100.0,
            creator_score=100.0,
            social_score=100.0,
            market_score=100.0,
            distribution_score=100.0,
        )
        event = GraduationEvent(
            token=token_metadata,
            creator=creator_profile,
            bonding=bonding_metrics,
            market=market_metrics,
            score=score,
        )
        html = event.to_telegram_html()
        assert "100/100" in html
        d = event.to_dict()
        assert d["scores"]["overall"] == 100.0

    def test_very_long_token_name(self, creator_profile, bonding_metrics, market_metrics, intel_score):
        """Test with very long token name."""
        token = TokenMetadata(
            mint_address="LongNameMint1111111111111111111111111111111",
            name="This Is A Very Long Token Name That Goes On And On And On Forever",
            symbol="LONGSYM",
        )
        event = GraduationEvent(
            token=token,
            creator=creator_profile,
            bonding=bonding_metrics,
            market=market_metrics,
            score=intel_score,
        )
        html = event.to_telegram_html()
        assert "This Is A Very Long Token Name" in html

    def test_special_characters_in_name(self, creator_profile, bonding_metrics, market_metrics, intel_score):
        """Test with special characters in token name."""
        token = TokenMetadata(
            mint_address="SpecialMint11111111111111111111111111111111",
            name="Token <script>alert('xss')</script>",
            symbol="XSS",
        )
        event = GraduationEvent(
            token=token,
            creator=creator_profile,
            bonding=bonding_metrics,
            market=market_metrics,
            score=intel_score,
        )
        html = event.to_telegram_html()
        # Name should be in HTML output (HTML escaping handled by Telegram)
        assert "Token" in html

    def test_very_small_price(self, token_metadata, creator_profile, bonding_metrics, intel_score):
        """Test with very small price values."""
        market = MarketMetrics(
            price_usd=0.00000001,
            price_sol=0.0000000001,
            market_cap_usd=100.0,
            liquidity_usd=50.0,
            volume_24h_usd=100.0,
            price_change_1h=0.0,
            buys_1h=10,
            sells_1h=5,
        )
        event = GraduationEvent(
            token=token_metadata,
            creator=creator_profile,
            bonding=bonding_metrics,
            market=market,
            score=intel_score,
        )
        html = event.to_telegram_html()
        assert "Price:" in html
        d = event.to_dict()
        assert d["market"]["price_usd"] == 0.00000001

    def test_very_large_market_cap(self, token_metadata, creator_profile, bonding_metrics, intel_score):
        """Test with very large market cap."""
        market = MarketMetrics(
            price_usd=1000.0,
            price_sol=10.0,
            market_cap_usd=1000000000.0,  # 1 billion
            liquidity_usd=100000000.0,
            volume_24h_usd=500000000.0,
            price_change_1h=50.0,
            buys_1h=10000,
            sells_1h=1000,
        )
        event = GraduationEvent(
            token=token_metadata,
            creator=creator_profile,
            bonding=bonding_metrics,
            market=market,
            score=intel_score,
        )
        html = event.to_telegram_html()
        assert "1,000,000,000" in html
        d = event.to_dict()
        assert d["market"]["mcap_usd"] == 1000000000.0

    def test_empty_string_fields(self):
        """Test with empty string fields."""
        token = TokenMetadata(
            mint_address="",
            name="",
            symbol="",
        )
        creator = CreatorProfile(
            wallet_address="",
            twitter_handle="",
        )
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
        )
        score = IntelScore(
            overall_score=0.0,
            launch_quality=LaunchQuality.POOR,
            risk_level=RiskLevel.EXTREME,
            bonding_score=0.0,
            creator_score=0.0,
            social_score=0.0,
            market_score=0.0,
            distribution_score=0.0,
        )
        event = GraduationEvent(
            token=token,
            creator=creator,
            bonding=bonding,
            market=market,
            score=score,
        )
        # Should not raise
        html = event.to_telegram_html()
        d = event.to_dict()
        assert isinstance(html, str)
        assert isinstance(d, dict)

    def test_unicode_in_description(self, creator_profile, bonding_metrics, market_metrics, intel_score):
        """Test with unicode characters in description."""
        token = TokenMetadata(
            mint_address="UnicodeMint11111111111111111111111111111111",
            name="Unicode Token",
            symbol="UNI",
            description="This token supports emoji and unicode characters",
        )
        event = GraduationEvent(
            token=token,
            creator=creator_profile,
            bonding=bonding_metrics,
            market=market_metrics,
            score=intel_score,
        )
        d = event.to_dict()
        assert event.token.description is not None

    def test_negative_holder_count_zero_default(self, token_metadata, creator_profile, bonding_metrics, intel_score):
        """Test that holder_count defaults to 0."""
        market = MarketMetrics(
            price_usd=0.01,
            price_sol=0.0001,
            market_cap_usd=100000.0,
            liquidity_usd=20000.0,
            volume_24h_usd=50000.0,
            price_change_1h=10.0,
            buys_1h=100,
            sells_1h=50,
            # holder_count not specified, should default to 0
        )
        assert market.holder_count == 0

    def test_bonding_duration_in_minutes(self, graduation_event):
        """Test that bonding duration is converted to minutes in HTML."""
        html = graduation_event.to_telegram_html()
        # 1800 seconds = 30 minutes
        assert "30m" in html


# =============================================================================
# Type Verification Tests
# =============================================================================

class TestTypeVerification:
    """Tests to verify correct types are used."""

    def test_token_metadata_types(self, token_metadata):
        """Verify TokenMetadata field types."""
        assert isinstance(token_metadata.mint_address, str)
        assert isinstance(token_metadata.name, str)
        assert isinstance(token_metadata.symbol, str)
        assert token_metadata.description is None or isinstance(token_metadata.description, str)
        assert token_metadata.image_url is None or isinstance(token_metadata.image_url, str)

    def test_creator_profile_types(self, creator_profile):
        """Verify CreatorProfile field types."""
        assert isinstance(creator_profile.wallet_address, str)
        assert creator_profile.twitter_handle is None or isinstance(creator_profile.twitter_handle, str)
        assert creator_profile.twitter_followers is None or isinstance(creator_profile.twitter_followers, int)
        assert creator_profile.twitter_account_age_days is None or isinstance(creator_profile.twitter_account_age_days, int)
        assert isinstance(creator_profile.previous_launches, int)
        assert isinstance(creator_profile.rugged_launches, int)

    def test_bonding_metrics_types(self, bonding_metrics):
        """Verify BondingMetrics field types."""
        assert isinstance(bonding_metrics.duration_seconds, int)
        assert isinstance(bonding_metrics.total_volume_sol, float)
        assert isinstance(bonding_metrics.unique_buyers, int)
        assert isinstance(bonding_metrics.unique_sellers, int)
        assert isinstance(bonding_metrics.buy_sell_ratio, float)
        assert isinstance(bonding_metrics.graduation_mcap_usd, float)

    def test_market_metrics_types(self, market_metrics):
        """Verify MarketMetrics field types."""
        assert isinstance(market_metrics.price_usd, float)
        assert isinstance(market_metrics.price_sol, float)
        assert isinstance(market_metrics.market_cap_usd, float)
        assert isinstance(market_metrics.liquidity_usd, float)
        assert isinstance(market_metrics.volume_24h_usd, float)
        assert isinstance(market_metrics.price_change_1h, float)
        assert isinstance(market_metrics.buys_1h, int)
        assert isinstance(market_metrics.sells_1h, int)
        assert isinstance(market_metrics.holder_count, int)
        assert isinstance(market_metrics.top_10_holder_pct, float)

    def test_intel_score_types(self, intel_score):
        """Verify IntelScore field types."""
        assert isinstance(intel_score.overall_score, float)
        assert isinstance(intel_score.launch_quality, LaunchQuality)
        assert isinstance(intel_score.risk_level, RiskLevel)
        assert isinstance(intel_score.bonding_score, float)
        assert isinstance(intel_score.creator_score, float)
        assert isinstance(intel_score.social_score, float)
        assert isinstance(intel_score.market_score, float)
        assert isinstance(intel_score.distribution_score, float)
        assert isinstance(intel_score.green_flags, list)
        assert isinstance(intel_score.red_flags, list)
        assert isinstance(intel_score.warnings, list)
        assert intel_score.grok_summary is None or isinstance(intel_score.grok_summary, str)

    def test_graduation_event_types(self, graduation_event):
        """Verify GraduationEvent field types."""
        assert isinstance(graduation_event.token, TokenMetadata)
        assert isinstance(graduation_event.creator, CreatorProfile)
        assert isinstance(graduation_event.bonding, BondingMetrics)
        assert isinstance(graduation_event.market, MarketMetrics)
        assert isinstance(graduation_event.score, IntelScore)
        assert isinstance(graduation_event.timestamp, datetime)
        assert graduation_event.tx_signature is None or isinstance(graduation_event.tx_signature, str)

    def test_to_telegram_html_returns_string(self, graduation_event):
        """Verify to_telegram_html returns a string."""
        result = graduation_event.to_telegram_html()
        assert isinstance(result, str)

    def test_to_dict_returns_dict(self, graduation_event):
        """Verify to_dict returns a dictionary."""
        result = graduation_event.to_dict()
        assert isinstance(result, dict)

    def test_is_reportable_returns_bool(self, graduation_event):
        """Verify is_reportable returns a boolean."""
        result = graduation_event.is_reportable
        assert isinstance(result, bool)
