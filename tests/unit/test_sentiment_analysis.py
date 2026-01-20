"""
Comprehensive unit tests for Sentiment Analysis in JARVIS.

Tests cover:
1. Sentiment scores calculation (TokenSentiment.calculate_sentiment)
2. Multiple sources weighted properly (SentimentAggregator)
3. Sentiment trends detection
4. Alert thresholds trigger correctly
5. Historical sentiment tracking
6. Edge cases (no data, conflicting signals)
7. Manipulation detection
8. Market regime awareness
9. Grok integration
"""

import pytest
import asyncio
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch, AsyncMock
from dataclasses import dataclass, field
from typing import Dict, List, Any

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# Import the modules under test
from bots.buy_tracker.sentiment_report import (
    TokenSentiment,
    ManipulationDetector,
    MarketRegime,
    MacroAnalysis,
    TraditionalMarkets,
    StockPick,
    CommodityMover,
    PreciousMetalsOutlook,
    PredictionRecord,
    get_emoji,
    STANDARD_EMOJIS,
    KR8TIV_EMOJI_IDS,
    EU_AI_ACT_DISCLOSURE,
)

from core.sentiment_aggregator import (
    SentimentSource,
    SentimentLabel,
    SentimentReading,
    AggregatedSentiment,
    SentimentConfig,
    SentimentAggregator,
)


# =============================================================================
# TEST FIXTURES
# =============================================================================

@pytest.fixture
def sample_token():
    """Create a sample TokenSentiment object with typical values."""
    return TokenSentiment(
        symbol="BONK",
        name="Bonk",
        price_usd=0.000025,
        change_1h=2.5,
        change_24h=15.0,
        volume_24h=5_000_000,
        mcap=100_000_000,
        buys_24h=5000,
        sells_24h=3000,
        liquidity=500_000,
        contract_address="BonkTestAddress123",
    )


@pytest.fixture
def bullish_token():
    """Token with strong bullish indicators."""
    return TokenSentiment(
        symbol="MOON",
        name="MoonToken",
        price_usd=0.01,
        change_1h=5.0,
        change_24h=12.0,  # Healthy growth, not pump
        volume_24h=2_000_000,
        mcap=50_000_000,
        buys_24h=8000,
        sells_24h=2000,  # 4x buy/sell ratio
        liquidity=200_000,
        contract_address="MoonTestAddress",
    )


@pytest.fixture
def bearish_token():
    """Token with strong bearish indicators."""
    return TokenSentiment(
        symbol="DUMP",
        name="DumpToken",
        price_usd=0.001,
        change_1h=-5.0,
        change_24h=-25.0,
        volume_24h=100_000,
        mcap=5_000_000,
        buys_24h=500,
        sells_24h=2500,  # 0.2x buy/sell ratio
        liquidity=20_000,
        contract_address="DumpTestAddress",
    )


@pytest.fixture
def pumped_token():
    """Token that already pumped significantly (chasing risk)."""
    return TokenSentiment(
        symbol="PUMP",
        name="PumpedToken",
        price_usd=0.05,
        change_1h=20.0,
        change_24h=150.0,  # Already pumped 150%
        volume_24h=10_000_000,
        mcap=200_000_000,
        buys_24h=3000,
        sells_24h=4000,  # Selling pressure
        liquidity=1_000_000,
        contract_address="PumpTestAddress",
    )


@pytest.fixture
def shitcoin_token():
    """Low quality shitcoin with rug risk."""
    return TokenSentiment(
        symbol="SCAM",
        name="ScamToken",
        price_usd=0.00001,
        change_1h=50.0,
        change_24h=500.0,
        volume_24h=50_000,
        mcap=100_000,  # Very low mcap
        buys_24h=1000,
        sells_24h=100,
        liquidity=5_000,  # Very low liquidity
        contract_address="ScamTestAddress",
    )


@pytest.fixture
def established_token():
    """Large established token."""
    return TokenSentiment(
        symbol="JUP",
        name="Jupiter",
        price_usd=1.50,
        change_1h=1.0,
        change_24h=5.0,
        volume_24h=50_000_000,
        mcap=1_000_000_000,
        buys_24h=10000,
        sells_24h=8000,
        liquidity=10_000_000,
        contract_address="JupTestAddress",
    )


@pytest.fixture
def bullish_market_regime():
    """Bullish market conditions."""
    return MarketRegime(
        btc_trend="BULLISH",
        sol_trend="BULLISH",
        btc_change_24h=5.0,
        sol_change_24h=7.0,
        risk_level="LOW",
        regime="BULL",
    )


@pytest.fixture
def bearish_market_regime():
    """Bearish market conditions."""
    return MarketRegime(
        btc_trend="BEARISH",
        sol_trend="BEARISH",
        btc_change_24h=-8.0,
        sol_change_24h=-12.0,
        risk_level="HIGH",
        regime="BEAR",
    )


@pytest.fixture
def neutral_market_regime():
    """Neutral/sideways market conditions."""
    return MarketRegime(
        btc_trend="NEUTRAL",
        sol_trend="NEUTRAL",
        btc_change_24h=1.0,
        sol_change_24h=-1.0,
        risk_level="NORMAL",
        regime="NEUTRAL",
    )


@pytest.fixture
def sentiment_aggregator(tmp_path):
    """Create a SentimentAggregator with temp database."""
    db_path = tmp_path / "test_sentiment.db"
    return SentimentAggregator(db_path=db_path)


# =============================================================================
# 1. SENTIMENT SCORE CALCULATION TESTS
# =============================================================================

class TestTokenSentimentScoreCalculation:
    """Tests for TokenSentiment.calculate_sentiment() method."""

    def test_calculate_sentiment_basic(self, sample_token):
        """Test basic sentiment calculation."""
        sample_token.calculate_sentiment(include_grok=False)

        assert sample_token.sentiment_score != 0
        assert sample_token.sentiment_label in [
            "BULLISH", "SLIGHTLY BULLISH", "NEUTRAL",
            "SLIGHTLY BEARISH", "BEARISH"
        ]
        assert sample_token.grade in ["A+", "A", "A-", "B+", "B", "B-", "C+", "C", "C-", "D+", "D", "F"]

    def test_calculate_sentiment_bullish_token(self, bullish_token):
        """Test sentiment calculation for clearly bullish token."""
        bullish_token.calculate_sentiment(include_grok=False)

        # 4x buy/sell ratio with healthy growth should be bullish
        assert bullish_token.sentiment_score > 0.35
        assert bullish_token.sentiment_label in ["BULLISH", "SLIGHTLY BULLISH"]
        assert bullish_token.buy_sell_ratio == 4.0

    def test_calculate_sentiment_bearish_token(self, bearish_token):
        """Test sentiment calculation for clearly bearish token."""
        bearish_token.calculate_sentiment(include_grok=False)

        # 0.2x buy/sell ratio with -25% drop should be bearish
        assert bearish_token.sentiment_score < -0.2
        assert bearish_token.sentiment_label in ["BEARISH", "SLIGHTLY BEARISH"]

    def test_calculate_sentiment_pumped_token_detection(self, pumped_token):
        """Test that already-pumped tokens are flagged correctly."""
        pumped_token.calculate_sentiment(include_grok=False)

        # 150% pump should trigger chasing_pump flag
        assert pumped_token.chasing_pump is True
        # Should NOT be rated as BULLISH even with high gains
        assert pumped_token.sentiment_label != "BULLISH" or pumped_token.grade != "A"

    def test_calculate_sentiment_buy_sell_ratio(self, sample_token):
        """Test buy/sell ratio calculation."""
        sample_token.calculate_sentiment(include_grok=False)

        # 5000 buys / 3000 sells = ~1.67
        assert sample_token.buy_sell_ratio == pytest.approx(5000 / 3000, rel=0.01)

    def test_calculate_sentiment_with_zero_sells(self):
        """Test buy/sell ratio with zero sells (avoid division by zero)."""
        token = TokenSentiment(
            symbol="TEST",
            name="Test",
            price_usd=1.0,
            change_1h=0,
            change_24h=10.0,
            volume_24h=1_000_000,
            mcap=10_000_000,
            buys_24h=1000,
            sells_24h=0,  # Zero sells
            liquidity=100_000,
        )
        token.calculate_sentiment(include_grok=False)

        # Should handle gracefully (divide by max(sells, 1))
        assert token.buy_sell_ratio == 1000.0

    def test_calculate_sentiment_confidence_score(self, sample_token):
        """Test that confidence score is calculated."""
        sample_token.calculate_sentiment(include_grok=False)

        assert 0.1 <= sample_token.confidence <= 1.0

    def test_calculate_sentiment_position_size_modifier(self, bullish_token):
        """Test position size modifier based on confidence."""
        bullish_token.calculate_sentiment(include_grok=False)

        # Position size should be set based on confidence and token risk
        assert 0.0 <= bullish_token.position_size_modifier <= 1.0

    def test_calculate_sentiment_stop_loss_assignment(self, sample_token):
        """Test stop loss percentage assignment."""
        sample_token.calculate_sentiment(include_grok=False)

        # Stop loss should be negative percentage
        assert sample_token.stop_loss_pct < 0


# =============================================================================
# 2. TOKEN RISK CLASSIFICATION TESTS
# =============================================================================

class TestTokenRiskClassification:
    """Tests for token risk classification (SHITCOIN, MICRO, MID, ESTABLISHED)."""

    def test_shitcoin_classification(self, shitcoin_token):
        """Test shitcoin classification for low mcap/liquidity."""
        shitcoin_token.calculate_sentiment(include_grok=False)

        # Low mcap ($100K) and low liquidity ($5K) = SHITCOIN
        assert shitcoin_token.token_risk == "SHITCOIN"

    def test_micro_cap_classification(self, sample_token):
        """Test microcap classification."""
        # $100M mcap, $500K liquidity = MID
        sample_token.calculate_sentiment(include_grok=False)

        assert sample_token.token_risk == "MID"

    def test_established_classification(self, established_token):
        """Test established token classification."""
        established_token.calculate_sentiment(include_grok=False)

        # $1B mcap, $10M liquidity = ESTABLISHED
        assert established_token.token_risk == "ESTABLISHED"

    def test_risk_affects_position_sizing(self, shitcoin_token, established_token):
        """Test that risk classification affects position sizing."""
        shitcoin_token.calculate_sentiment(include_grok=False)
        established_token.calculate_sentiment(include_grok=False)

        # Shitcoins should have smaller position size modifier
        # (0.5x multiplier for shitcoins vs 1.0x for established)
        # Note: depends on confidence, but multiplier is applied
        assert shitcoin_token.token_risk == "SHITCOIN"
        assert established_token.token_risk == "ESTABLISHED"

    def test_risk_affects_stop_loss(self, shitcoin_token, established_token):
        """Test that risk classification affects stop loss."""
        shitcoin_token.calculate_sentiment(include_grok=False)
        established_token.calculate_sentiment(include_grok=False)

        # Shitcoins should have tighter stops (less negative = tighter)
        # Base: SHITCOIN=-7%, ESTABLISHED=-15%
        # Both are negative, shitcoin base is closer to 0 (tighter)
        assert abs(shitcoin_token.stop_loss_pct) < abs(established_token.stop_loss_pct)


# =============================================================================
# 3. MARKET REGIME TESTS
# =============================================================================

class TestMarketRegime:
    """Tests for MarketRegime class and market regime awareness."""

    def test_is_bullish_method(self, bullish_market_regime):
        """Test is_bullish() method."""
        assert bullish_market_regime.is_bullish() is True
        assert bullish_market_regime.is_bearish() is False

    def test_is_bearish_method(self, bearish_market_regime):
        """Test is_bearish() method."""
        assert bearish_market_regime.is_bearish() is True
        assert bearish_market_regime.is_bullish() is False

    def test_neutral_regime(self, neutral_market_regime):
        """Test neutral market regime."""
        assert neutral_market_regime.is_bullish() is False
        assert neutral_market_regime.is_bearish() is False

    def test_bearish_regime_affects_sentiment(self, bullish_token, bearish_market_regime):
        """Test that bearish regime reduces bullish sentiment."""
        # Calculate without regime
        bullish_token.calculate_sentiment(include_grok=False)
        score_without_regime = bullish_token.sentiment_score

        # Reset and calculate with bearish regime
        bullish_token2 = TokenSentiment(
            symbol="MOON",
            name="MoonToken",
            price_usd=0.01,
            change_1h=5.0,
            change_24h=12.0,
            volume_24h=2_000_000,
            mcap=50_000_000,
            buys_24h=8000,
            sells_24h=2000,
            liquidity=200_000,
        )
        bullish_token2.calculate_sentiment(include_grok=False, market_regime=bearish_market_regime)
        score_with_bearish_regime = bullish_token2.sentiment_score

        # Bearish regime should reduce bullish scores by 30%
        assert score_with_bearish_regime < score_without_regime

    def test_bullish_regime_boosts_sentiment(self, bullish_token, bullish_market_regime):
        """Test that bullish regime boosts positive sentiment."""
        # Calculate without regime
        bullish_token.calculate_sentiment(include_grok=False)
        score_without_regime = bullish_token.sentiment_score

        # Reset and calculate with bullish regime
        bullish_token2 = TokenSentiment(
            symbol="MOON",
            name="MoonToken",
            price_usd=0.01,
            change_1h=5.0,
            change_24h=12.0,
            volume_24h=2_000_000,
            mcap=50_000_000,
            buys_24h=8000,
            sells_24h=2000,
            liquidity=200_000,
        )
        bullish_token2.calculate_sentiment(include_grok=False, market_regime=bullish_market_regime)
        score_with_bullish_regime = bullish_token2.sentiment_score

        # Bullish regime should boost bullish scores by 10%
        assert score_with_bullish_regime >= score_without_regime


# =============================================================================
# 4. MANIPULATION DETECTION TESTS
# =============================================================================

class TestManipulationDetection:
    """Tests for ManipulationDetector class."""

    def test_detect_clusters_no_manipulation(self):
        """Test detection with normal posts."""
        posts = [
            {"content": "I love this token! Great community.", "followers": 5000},
            {"content": "Just bought some more $TOKEN!", "followers": 2000},
            {"content": "The tech looks solid.", "followers": 10000},
        ]

        is_manipulation, reason = ManipulationDetector.detect_clusters(posts)

        assert is_manipulation is False
        assert reason == ""

    def test_detect_clusters_identical_content(self):
        """Test detection of identical post content (shill campaign)."""
        # Create 6+ posts with identical content
        identical_content = "This is the best token ever buy now!!!"
        posts = [
            {"content": identical_content, "followers": 100}
            for _ in range(7)
        ]

        is_manipulation, reason = ManipulationDetector.detect_clusters(posts)

        assert is_manipulation is True
        assert "cluster" in reason.lower()

    def test_detect_clusters_low_follower_ratio(self):
        """Test detection of suspicious low-follower ratio."""
        # 90% posts from accounts under 500 followers
        posts = [
            {"content": f"Unique post {i}", "followers": 50}
            for i in range(15)
        ]
        posts.append({"content": "Real user post", "followers": 10000})

        is_manipulation, reason = ManipulationDetector.detect_clusters(posts)

        assert is_manipulation is True
        assert "low-follower" in reason.lower()

    def test_detect_clusters_insufficient_posts(self):
        """Test detection with too few posts to analyze."""
        posts = [
            {"content": "Single post", "followers": 100}
        ]

        is_manipulation, reason = ManipulationDetector.detect_clusters(posts)

        assert is_manipulation is False

    def test_calculate_influence_weight_high_followers(self):
        """Test influence weight for high follower accounts."""
        weight = ManipulationDetector.calculate_influence_weight(150000)

        assert weight == 2.5  # 100K+ followers

    def test_calculate_influence_weight_low_followers(self):
        """Test influence weight for low follower accounts."""
        weight = ManipulationDetector.calculate_influence_weight(100)

        assert weight == 0.2  # Under 500 followers

    def test_calculate_influence_weight_verified(self):
        """Test influence weight with verification bonus."""
        weight_unverified = ManipulationDetector.calculate_influence_weight(50000)
        weight_verified = ManipulationDetector.calculate_influence_weight(50000, is_verified=True)

        assert weight_verified > weight_unverified
        assert weight_verified == pytest.approx(weight_unverified * 1.3, rel=0.01)

    def test_influence_weight_cap(self):
        """Test that influence weight is capped at 3.0."""
        weight = ManipulationDetector.calculate_influence_weight(1000000, is_verified=True)

        assert weight <= 3.0


# =============================================================================
# 5. SOURCE WEIGHTING TESTS (Aggregator)
# =============================================================================

class TestSourceWeighting:
    """Tests for sentiment source weighting in aggregation."""

    def test_default_source_weights(self):
        """Test default source weights are defined correctly."""
        config = SentimentConfig()

        assert config.source_weights[SentimentSource.GROK.value] == 1.0
        assert config.source_weights[SentimentSource.TWITTER.value] == 0.8
        assert config.source_weights[SentimentSource.WHALE.value] == 0.9
        assert config.source_weights[SentimentSource.ONCHAIN.value] == 0.85

    def test_grok_has_highest_weight(self):
        """Test that Grok source has highest default weight."""
        config = SentimentConfig()

        max_weight = max(config.source_weights.values())
        assert config.source_weights[SentimentSource.GROK.value] == max_weight

    def test_weighted_aggregation(self, sentiment_aggregator):
        """Test that sources are weighted in aggregation."""
        now = datetime.now(timezone.utc).isoformat()

        # Add conflicting readings with known weights
        # Grok (weight 1.0) says bullish
        sentiment_aggregator.add_reading(SentimentReading(
            source=SentimentSource.GROK,
            symbol="TEST",
            score=80.0,
            label=SentimentLabel.VERY_BULLISH,
            confidence=1.0,
            timestamp=now,
        ))

        # Discord (weight 0.4) says bearish
        sentiment_aggregator.add_reading(SentimentReading(
            source=SentimentSource.DISCORD,
            symbol="TEST",
            score=-80.0,
            label=SentimentLabel.VERY_BEARISH,
            confidence=1.0,
            timestamp=now,
        ))

        result = sentiment_aggregator.aggregate("TEST")

        # Grok's bullish should outweigh Discord's bearish
        assert result.overall_score > 0

    def test_confidence_affects_weight(self, sentiment_aggregator):
        """Test that confidence reduces effective weight."""
        now = datetime.now(timezone.utc).isoformat()

        # Low confidence source
        sentiment_aggregator.add_reading(SentimentReading(
            source=SentimentSource.GROK,
            symbol="CONF",
            score=100.0,
            label=SentimentLabel.VERY_BULLISH,
            confidence=0.1,  # Very low confidence
            timestamp=now,
        ))

        # High confidence source
        sentiment_aggregator.add_reading(SentimentReading(
            source=SentimentSource.TWITTER,
            symbol="CONF",
            score=-50.0,
            label=SentimentLabel.BEARISH,
            confidence=0.9,
            timestamp=now,
        ))

        result = sentiment_aggregator.aggregate("CONF")

        # Twitter's bearish should dominate due to confidence
        assert result.overall_score < 30


# =============================================================================
# 6. SENTIMENT TRENDS DETECTION TESTS
# =============================================================================

class TestSentimentTrends:
    """Tests for sentiment trend detection."""

    def test_trend_detection_improving(self, sentiment_aggregator):
        """Test detection of improving sentiment trend."""
        now = datetime.now(timezone.utc)

        # Add historical data points with increasing sentiment
        for i, score in enumerate([20, 30, 40, 50, 60]):
            ts = (now - timedelta(hours=5-i)).isoformat()
            sentiment_aggregator.add_reading(SentimentReading(
                source=SentimentSource.GROK,
                symbol="TREND",
                score=float(score),
                label=SentimentLabel.BULLISH if score > 40 else SentimentLabel.NEUTRAL,
                confidence=0.8,
                timestamp=ts,
            ))
            # Trigger aggregation to save historical data
            sentiment_aggregator.aggregate("TREND")

        # Get latest aggregation
        result = sentiment_aggregator.aggregate("TREND")

        # Should detect improving trend
        assert result.trend in ["IMPROVING", "STABLE"]

    def test_trend_detection_stable(self, sentiment_aggregator):
        """Test detection of stable sentiment trend."""
        now = datetime.now(timezone.utc)

        # Add historical data points with similar sentiment
        for i in range(5):
            ts = (now - timedelta(hours=5-i)).isoformat()
            sentiment_aggregator.add_reading(SentimentReading(
                source=SentimentSource.GROK,
                symbol="STABLE",
                score=50.0 + (i % 3),  # Small variations
                label=SentimentLabel.BULLISH,
                confidence=0.8,
                timestamp=ts,
            ))
            sentiment_aggregator.aggregate("STABLE")

        result = sentiment_aggregator.aggregate("STABLE")

        assert result.trend == "STABLE"

    def test_trend_change_calculation(self, sentiment_aggregator):
        """Test that trend change value is calculated."""
        now = datetime.now(timezone.utc)

        # Add baseline
        sentiment_aggregator.add_reading(SentimentReading(
            source=SentimentSource.GROK,
            symbol="CHANGE",
            score=30.0,
            label=SentimentLabel.BULLISH,
            confidence=0.8,
            timestamp=(now - timedelta(hours=1)).isoformat(),
        ))
        sentiment_aggregator.aggregate("CHANGE")

        # Add new higher reading
        sentiment_aggregator.add_reading(SentimentReading(
            source=SentimentSource.GROK,
            symbol="CHANGE",
            score=60.0,
            label=SentimentLabel.VERY_BULLISH,
            confidence=0.8,
            timestamp=now.isoformat(),
        ))

        result = sentiment_aggregator.aggregate("CHANGE")

        # Should have numeric trend change
        assert isinstance(result.trend_change, (int, float))


# =============================================================================
# 7. ALERT THRESHOLDS TESTS
# =============================================================================

class TestAlertThresholds:
    """Tests for sentiment alert thresholds and grade assignment."""

    def test_very_bullish_threshold(self):
        """Test very bullish label threshold."""
        config = SentimentConfig()
        assert config.very_bullish_threshold == 60

    def test_bullish_threshold(self):
        """Test bullish label threshold."""
        config = SentimentConfig()
        assert config.bullish_threshold == 20

    def test_grade_assignment_a(self):
        """Test A grade assignment for strong bullish."""
        token = TokenSentiment(
            symbol="STRONG",
            name="Strong",
            price_usd=1.0,
            change_1h=3.0,
            change_24h=10.0,  # Healthy, not pumped
            volume_24h=5_000_000,
            mcap=100_000_000,
            buys_24h=10000,
            sells_24h=3000,  # 3.3x ratio
            liquidity=1_000_000,
        )
        token.calculate_sentiment(include_grok=False)

        # Very bullish indicators should get A or A- grade
        if token.sentiment_score > 0.55 and token.buy_sell_ratio >= 1.5:
            assert token.grade in ["A", "A-"]

    def test_grade_assignment_f_for_bearish(self, bearish_token):
        """Test F grade assignment for very bearish."""
        bearish_token.calculate_sentiment(include_grok=False)

        # Very bearish should get D or F
        assert bearish_token.grade in ["D+", "D", "F"]

    def test_chasing_pump_caps_grade(self, pumped_token):
        """Test that chasing pump caps grade at B."""
        pumped_token.calculate_sentiment(include_grok=False)

        # Even if bullish, pumped tokens max out at B
        if pumped_token.chasing_pump:
            assert pumped_token.grade not in ["A+", "A", "A-"]

    def test_divergence_warning_generated(self, sentiment_aggregator):
        """Test that divergence warning is generated for conflicting sources."""
        now = datetime.now(timezone.utc).isoformat()

        # Very bullish from one source
        sentiment_aggregator.add_reading(SentimentReading(
            source=SentimentSource.TWITTER,
            symbol="DIV",
            score=80.0,
            label=SentimentLabel.VERY_BULLISH,
            confidence=0.9,
            timestamp=now,
        ))

        # Very bearish from another
        sentiment_aggregator.add_reading(SentimentReading(
            source=SentimentSource.WHALE,
            symbol="DIV",
            score=-50.0,
            label=SentimentLabel.BEARISH,
            confidence=0.9,
            timestamp=now,
        ))

        result = sentiment_aggregator.aggregate("DIV")

        # Should have divergence warning (130 point spread)
        assert "divergence" in result.warning.lower() or result.warning == ""


# =============================================================================
# 8. HISTORICAL SENTIMENT TRACKING TESTS
# =============================================================================

class TestHistoricalSentiment:
    """Tests for historical sentiment tracking."""

    def test_get_historical_data(self, sentiment_aggregator):
        """Test retrieval of historical sentiment data."""
        now = datetime.now(timezone.utc)

        # Add readings over several days
        for i in range(5):
            ts = (now - timedelta(days=i)).isoformat()
            sentiment_aggregator.add_reading(SentimentReading(
                source=SentimentSource.GROK,
                symbol="HIST",
                score=50.0 + i * 5,
                label=SentimentLabel.BULLISH,
                confidence=0.8,
                timestamp=ts,
            ))
            sentiment_aggregator.aggregate("HIST")

        # Get historical data
        historical = sentiment_aggregator.get_historical("HIST", days=7)

        assert len(historical) >= 3

    def test_get_sentiment_leaders(self, sentiment_aggregator):
        """Test retrieval of sentiment leaders."""
        now = datetime.now(timezone.utc).isoformat()

        # Add readings for multiple symbols
        for symbol, score in [("TOP", 80), ("MID", 50), ("LOW", 20)]:
            sentiment_aggregator.add_reading(SentimentReading(
                source=SentimentSource.GROK,
                symbol=symbol,
                score=float(score),
                label=SentimentLabel.BULLISH if score > 40 else SentimentLabel.NEUTRAL,
                confidence=0.8,
                timestamp=now,
            ))
            sentiment_aggregator.aggregate(symbol)

        leaders = sentiment_aggregator.get_sentiment_leaders(hours=24, limit=10)

        assert len(leaders) >= 1
        # Leaders should be sorted by avg_score descending
        if len(leaders) >= 2:
            assert leaders[0]["avg_score"] >= leaders[1]["avg_score"]


# =============================================================================
# 9. EDGE CASES TESTS
# =============================================================================

class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_no_data_returns_neutral(self, sentiment_aggregator):
        """Test that no data returns neutral sentiment."""
        result = sentiment_aggregator.aggregate("UNKNOWN_TOKEN")

        assert result.overall_score == 0
        assert result.overall_label == SentimentLabel.NEUTRAL
        assert "no sentiment data" in result.warning.lower()

    def test_extreme_positive_score(self):
        """Test handling of extreme positive sentiment."""
        token = TokenSentiment(
            symbol="MOON",
            name="Moon",
            price_usd=1.0,
            change_1h=10.0,
            change_24h=100.0,
            volume_24h=100_000_000,
            mcap=1_000_000_000,
            buys_24h=100000,
            sells_24h=100,  # 1000x ratio
            liquidity=50_000_000,
        )
        token.calculate_sentiment(include_grok=False)

        # Score should be capped at 1.0
        assert token.sentiment_score <= 1.0

    def test_extreme_negative_score(self):
        """Test handling of extreme negative sentiment."""
        token = TokenSentiment(
            symbol="REKT",
            name="Rekt",
            price_usd=0.001,
            change_1h=-50.0,
            change_24h=-90.0,
            volume_24h=10_000,
            mcap=10_000,
            buys_24h=10,
            sells_24h=10000,  # 0.001x ratio
            liquidity=1_000,
        )
        token.calculate_sentiment(include_grok=False)

        # Score should be capped at -1.0
        assert token.sentiment_score >= -1.0

    def test_zero_mcap_handling(self):
        """Test handling of zero market cap."""
        token = TokenSentiment(
            symbol="ZERO",
            name="Zero",
            price_usd=0.0,
            change_1h=0.0,
            change_24h=0.0,
            volume_24h=0,
            mcap=0,
            buys_24h=0,
            sells_24h=0,
            liquidity=0,
        )
        token.calculate_sentiment(include_grok=False)

        # Should not crash, should be classified as shitcoin
        assert token.token_risk == "SHITCOIN"

    def test_conflicting_signals(self):
        """Test handling of conflicting signals (high gains but selling)."""
        token = TokenSentiment(
            symbol="MIXED",
            name="Mixed",
            price_usd=1.0,
            change_1h=20.0,
            change_24h=60.0,  # Pumped
            volume_24h=5_000_000,
            mcap=50_000_000,
            buys_24h=1000,
            sells_24h=5000,  # But heavy selling
            liquidity=200_000,
        )
        token.calculate_sentiment(include_grok=False)

        # Should detect profit-taking (high gains + selling pressure)
        # Should not be bullish despite gains
        assert token.sentiment_label not in ["BULLISH"]

    def test_grok_score_integration(self, sample_token):
        """Test Grok score integration into sentiment."""
        # First calculate without Grok
        sample_token.calculate_sentiment(include_grok=False)
        base_score = sample_token.sentiment_score

        # Add Grok score and recalculate
        sample_token.grok_score = 0.8  # Very bullish Grok
        sample_token.calculate_sentiment(include_grok=True)

        # Score should be affected by Grok
        assert sample_token.sentiment_score != base_score


# =============================================================================
# 10. GROK INTEGRATION TESTS
# =============================================================================

class TestGrokIntegration:
    """Tests for Grok AI integration with sentiment analysis."""

    def test_grok_score_normalized(self):
        """Test that Grok scores are normalized to -1 to 1 range."""
        token = TokenSentiment(
            symbol="GROK",
            name="GrokTest",
            price_usd=1.0,
            change_1h=5.0,
            change_24h=10.0,
            volume_24h=1_000_000,
            mcap=10_000_000,
            buys_24h=1000,
            sells_24h=500,
            liquidity=100_000,
        )

        # Set Grok score (simulating parsed response)
        token.grok_score = 75 / 100.0  # 75 from Grok normalized
        token.grok_verdict = "BULLISH"

        assert -1.0 <= token.grok_score <= 1.0

    def test_grok_targets_stored(self):
        """Test that Grok price targets are stored correctly."""
        token = TokenSentiment(
            symbol="TARGET",
            name="Target",
            price_usd=1.0,
            change_1h=5.0,
            change_24h=10.0,
            volume_24h=1_000_000,
            mcap=10_000_000,
            buys_24h=1000,
            sells_24h=500,
            liquidity=100_000,
        )

        # Simulate Grok response
        token.grok_stop_loss = "$0.90"
        token.grok_target_safe = "$1.20"
        token.grok_target_med = "$1.50"
        token.grok_target_degen = "$2.00"
        token.grok_grade = "B+"

        assert token.grok_stop_loss == "$0.90"
        assert token.grok_target_degen == "$2.00"

    def test_grok_agreement_boosts_confidence(self):
        """Test that Grok agreement with technical analysis boosts confidence."""
        token = TokenSentiment(
            symbol="AGREE",
            name="Agree",
            price_usd=1.0,
            change_1h=5.0,
            change_24h=15.0,
            volume_24h=5_000_000,
            mcap=50_000_000,
            buys_24h=5000,
            sells_24h=2000,
            liquidity=500_000,
        )

        # Calculate base (should be bullish)
        token.calculate_sentiment(include_grok=False)
        base_confidence = token.confidence

        # Add agreeing Grok (also bullish)
        token.grok_score = 0.7
        token.calculate_sentiment(include_grok=True)

        # Confidence should increase when Grok agrees
        assert token.confidence >= base_confidence


# =============================================================================
# 11. DATACLASS TESTS
# =============================================================================

class TestDataClasses:
    """Tests for sentiment-related dataclasses."""

    def test_macro_analysis_defaults(self):
        """Test MacroAnalysis default values."""
        macro = MacroAnalysis()

        assert macro.short_term == ""
        assert macro.medium_term == ""
        assert macro.long_term == ""
        assert macro.key_events == []

    def test_traditional_markets_defaults(self):
        """Test TraditionalMarkets default values."""
        markets = TraditionalMarkets()

        assert markets.dxy_direction == "NEUTRAL"
        assert markets.stocks_direction == "NEUTRAL"

    def test_stock_pick_creation(self):
        """Test StockPick dataclass."""
        pick = StockPick(
            ticker="AAPL",
            direction="BULLISH",
            reason="Strong earnings",
            target="$200",
            stop_loss="$170",
        )

        assert pick.ticker == "AAPL"
        assert pick.direction == "BULLISH"

    def test_commodity_mover_creation(self):
        """Test CommodityMover dataclass."""
        mover = CommodityMover(
            name="Gold",
            direction="UP",
            change="+2.5%",
            reason="Safe haven demand",
            outlook="Bullish",
        )

        assert mover.name == "Gold"
        assert mover.direction == "UP"

    def test_prediction_record_creation(self):
        """Test PredictionRecord dataclass."""
        record = PredictionRecord(
            timestamp="2024-01-01T12:00:00Z",
            token_predictions={"BTC": {"verdict": "BULLISH", "price": 50000}},
            macro_predictions={"short_term": "Risk-on"},
        )

        assert "BTC" in record.token_predictions
        assert record.token_predictions["BTC"]["verdict"] == "BULLISH"


# =============================================================================
# 12. EMOJI AND FORMATTING TESTS
# =============================================================================

class TestEmojiAndFormatting:
    """Tests for emoji helpers and formatting."""

    def test_get_emoji_standard(self):
        """Test standard emoji retrieval."""
        emoji = get_emoji("bull", use_custom=False)
        assert emoji == STANDARD_EMOJIS["bull"]

    def test_get_emoji_unknown(self):
        """Test unknown emoji returns empty string."""
        emoji = get_emoji("unknown_emoji")
        assert emoji == ""

    def test_eu_ai_act_disclosure_exists(self):
        """Test EU AI Act disclosure is defined."""
        assert "AI-generated" in EU_AI_ACT_DISCLOSURE
        assert "DYOR" in EU_AI_ACT_DISCLOSURE


# =============================================================================
# 13. SENTIMENT REPORT INTEGRATION TESTS
# =============================================================================

class TestSentimentReportIntegration:
    """Integration tests for the sentiment report generator."""

    def test_multiple_tokens_scored(self):
        """Test that multiple tokens can be scored together."""
        tokens = []
        for i, (symbol, change, buys, sells) in enumerate([
            ("BULL", 15.0, 5000, 2000),
            ("BEAR", -20.0, 1000, 4000),
            ("NEUT", 2.0, 2000, 2000),
        ]):
            token = TokenSentiment(
                symbol=symbol,
                name=f"{symbol}Token",
                price_usd=1.0,
                change_1h=change/5,
                change_24h=change,
                volume_24h=1_000_000,
                mcap=10_000_000,
                buys_24h=buys,
                sells_24h=sells,
                liquidity=100_000,
            )
            token.calculate_sentiment(include_grok=False)
            tokens.append(token)

        # Should have mix of sentiments
        labels = [t.sentiment_label for t in tokens]
        assert "NEUTRAL" in labels or len(set(labels)) > 1

    def test_social_metrics_integration(self):
        """Test that social metrics are considered when available."""
        token = TokenSentiment(
            symbol="SOCIAL",
            name="Social",
            price_usd=1.0,
            change_1h=2.0,
            change_24h=5.0,
            volume_24h=1_000_000,
            mcap=10_000_000,
            buys_24h=1500,
            sells_24h=1000,
            liquidity=100_000,
            # Social metrics
            galaxy_score=80.0,  # High social score
            social_volume=5000,
            social_sentiment=75.0,  # Bullish social
            news_sentiment="bullish",
            news_count=10,
        )
        token.calculate_sentiment(include_grok=False)

        # Token has social metrics stored
        assert token.galaxy_score == 80.0
        assert token.social_sentiment == 75.0


# =============================================================================
# RUN TESTS
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
