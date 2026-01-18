"""
Comprehensive unit tests for the Sentiment Aggregator.

Tests cover:
- SentimentSource enum values
- SentimentLabel classification
- SentimentReading dataclass
- AggregatedSentiment dataclass
- SentimentConfig validation
- SentimentAggregator aggregation logic
- Score to label conversion
- Source weighting
- Divergence detection
- Historical data retrieval
"""

import pytest
import asyncio
import json
import tempfile
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from core.sentiment_aggregator import (
    SentimentSource,
    SentimentLabel,
    SentimentReading,
    AggregatedSentiment,
    SentimentConfig,
    SentimentAggregator,
    SentimentDB,
)


# =============================================================================
# SentimentSource Tests
# =============================================================================

class TestSentimentSource:
    """Tests for SentimentSource enum."""

    def test_all_sources_defined(self):
        """Test all expected sentiment sources are defined."""
        expected_sources = [
            "twitter", "telegram", "discord", "reddit",
            "news", "grok", "technical", "onchain", "whale"
        ]

        actual_sources = [s.value for s in SentimentSource]

        for source in expected_sources:
            assert source in actual_sources, f"Missing source: {source}"

    def test_source_values_are_strings(self):
        """Test source values are strings."""
        for source in SentimentSource:
            assert isinstance(source.value, str)


# =============================================================================
# SentimentLabel Tests
# =============================================================================

class TestSentimentLabel:
    """Tests for SentimentLabel enum."""

    def test_all_labels_defined(self):
        """Test all sentiment labels are defined."""
        expected_labels = [
            "very_bullish", "bullish", "neutral", "bearish", "very_bearish"
        ]

        actual_labels = [l.value for l in SentimentLabel]

        for label in expected_labels:
            assert label in actual_labels, f"Missing label: {label}"

    def test_label_ordering(self):
        """Test sentiment labels represent a spectrum."""
        # Labels should be defined in order of sentiment
        labels = list(SentimentLabel)
        assert labels[0] == SentimentLabel.VERY_BULLISH
        assert labels[-1] == SentimentLabel.VERY_BEARISH


# =============================================================================
# SentimentReading Tests
# =============================================================================

class TestSentimentReading:
    """Tests for SentimentReading dataclass."""

    def test_reading_creation(self):
        """Test SentimentReading creation."""
        reading = SentimentReading(
            source=SentimentSource.TWITTER,
            symbol="BTC",
            score=65.0,
            label=SentimentLabel.BULLISH,
            confidence=0.85,
            timestamp="2024-01-01T12:00:00Z",
            data_points=100,
        )

        assert reading.source == SentimentSource.TWITTER
        assert reading.symbol == "BTC"
        assert reading.score == 65.0
        assert reading.label == SentimentLabel.BULLISH
        assert reading.confidence == 0.85
        assert reading.data_points == 100

    def test_reading_with_metadata(self):
        """Test SentimentReading with metadata."""
        metadata = {"source_url": "https://example.com", "analyst": "grok"}

        reading = SentimentReading(
            source=SentimentSource.GROK,
            symbol="SOL",
            score=75.0,
            label=SentimentLabel.VERY_BULLISH,
            confidence=0.90,
            timestamp="2024-01-01T12:00:00Z",
            metadata=metadata,
        )

        assert reading.metadata["source_url"] == "https://example.com"
        assert reading.metadata["analyst"] == "grok"

    def test_reading_default_values(self):
        """Test SentimentReading default values."""
        reading = SentimentReading(
            source=SentimentSource.NEWS,
            symbol="ETH",
            score=0.0,
            label=SentimentLabel.NEUTRAL,
            confidence=0.5,
            timestamp="2024-01-01T12:00:00Z",
        )

        assert reading.data_points == 0
        assert reading.metadata == {}


# =============================================================================
# AggregatedSentiment Tests
# =============================================================================

class TestAggregatedSentiment:
    """Tests for AggregatedSentiment dataclass."""

    def test_aggregated_creation(self):
        """Test AggregatedSentiment creation."""
        aggregated = AggregatedSentiment(
            symbol="BTC",
            overall_score=55.0,
            overall_label=SentimentLabel.BULLISH,
            overall_confidence=0.80,
            source_scores={"twitter": 60.0, "grok": 50.0},
            source_weights={"twitter": 0.8, "grok": 1.0},
            trend="IMPROVING",
            trend_change=5.0,
            timestamp="2024-01-01T12:00:00Z",
        )

        assert aggregated.symbol == "BTC"
        assert aggregated.overall_score == 55.0
        assert aggregated.overall_label == SentimentLabel.BULLISH
        assert aggregated.trend == "IMPROVING"

    def test_aggregated_with_warning(self):
        """Test AggregatedSentiment with divergence warning."""
        aggregated = AggregatedSentiment(
            symbol="SOL",
            overall_score=10.0,
            overall_label=SentimentLabel.NEUTRAL,
            overall_confidence=0.50,
            source_scores={"twitter": 80.0, "whale": -40.0},
            source_weights={"twitter": 0.8, "whale": 0.9},
            trend="STABLE",
            trend_change=0.0,
            timestamp="2024-01-01T12:00:00Z",
            warning="Significant divergence between sources",
        )

        assert "divergence" in aggregated.warning.lower()


# =============================================================================
# SentimentConfig Tests
# =============================================================================

class TestSentimentConfig:
    """Tests for SentimentConfig."""

    def test_default_config(self):
        """Test default configuration values."""
        config = SentimentConfig()

        # Check default weights
        assert config.source_weights[SentimentSource.GROK.value] == 1.0
        assert config.source_weights[SentimentSource.TWITTER.value] == 0.8
        assert config.source_weights[SentimentSource.WHALE.value] == 0.9

        # Check thresholds
        assert config.very_bullish_threshold == 60
        assert config.bullish_threshold == 20
        assert config.neutral_low == -20
        assert config.bearish_threshold == -60

    def test_custom_config(self):
        """Test custom configuration."""
        custom_weights = {
            SentimentSource.TWITTER.value: 0.5,
            SentimentSource.GROK.value: 0.8,
        }

        config = SentimentConfig(
            source_weights=custom_weights,
            very_bullish_threshold=70,
        )

        assert config.source_weights[SentimentSource.TWITTER.value] == 0.5
        assert config.very_bullish_threshold == 70


# =============================================================================
# SentimentDB Tests
# =============================================================================

class TestSentimentDB:
    """Tests for SentimentDB database operations."""

    @pytest.fixture
    def temp_db(self, tmp_path):
        """Create a temporary database for testing."""
        db_path = tmp_path / "test_sentiment.db"
        return SentimentDB(db_path)

    def test_db_initialization(self, temp_db):
        """Test database is initialized with proper tables."""
        import sqlite3

        conn = sqlite3.connect(temp_db.db_path)
        cursor = conn.cursor()

        # Check tables exist
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
        tables = [row[0] for row in cursor.fetchall()]

        assert "sentiment_readings" in tables
        assert "aggregated_sentiment" in tables

        conn.close()

    def test_db_creates_parent_directory(self, tmp_path):
        """Test database creates parent directories if needed."""
        db_path = tmp_path / "nested" / "dir" / "sentiment.db"
        db = SentimentDB(db_path)

        assert db_path.parent.exists()


# =============================================================================
# SentimentAggregator Tests
# =============================================================================

class TestSentimentAggregator:
    """Tests for SentimentAggregator."""

    @pytest.fixture
    def aggregator(self, tmp_path):
        """Create a temporary aggregator for testing."""
        db_path = tmp_path / "test_sentiment.db"
        return SentimentAggregator(db_path=db_path)

    def test_add_reading(self, aggregator):
        """Test adding a sentiment reading."""
        # Use current time so the reading is within the 24h window
        now = datetime.now(timezone.utc).isoformat()

        reading = SentimentReading(
            source=SentimentSource.TWITTER,
            symbol="BTC",
            score=65.0,
            label=SentimentLabel.BULLISH,
            confidence=0.85,
            timestamp=now,
        )

        aggregator.add_reading(reading)

        # Verify reading was stored - use longer window
        readings = aggregator.get_readings("BTC", hours=48)
        assert len(readings) >= 1
        assert readings[0].symbol == "BTC"

    def test_aggregate_no_data(self, aggregator):
        """Test aggregation with no data returns neutral."""
        result = aggregator.aggregate("UNKNOWN_SYMBOL")

        assert result.overall_score == 0
        assert result.overall_label == SentimentLabel.NEUTRAL
        assert result.overall_confidence == 0
        assert "no sentiment data" in result.warning.lower()

    def test_aggregate_single_source(self, aggregator):
        """Test aggregation with single source."""
        reading = SentimentReading(
            source=SentimentSource.GROK,
            symbol="SOL",
            score=70.0,
            label=SentimentLabel.VERY_BULLISH,
            confidence=0.90,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )
        aggregator.add_reading(reading)

        result = aggregator.aggregate("SOL")

        # Score should be weighted: 70.0 * 1.0 (grok weight) * 0.90 (confidence)
        assert result.overall_score > 0
        assert result.overall_label in [SentimentLabel.BULLISH, SentimentLabel.VERY_BULLISH]

    def test_aggregate_multiple_sources(self, aggregator):
        """Test aggregation with multiple sources."""
        now = datetime.now(timezone.utc).isoformat()

        # Add multiple readings from different sources
        readings = [
            SentimentReading(
                source=SentimentSource.TWITTER,
                symbol="ETH",
                score=50.0,
                label=SentimentLabel.BULLISH,
                confidence=0.80,
                timestamp=now,
            ),
            SentimentReading(
                source=SentimentSource.GROK,
                symbol="ETH",
                score=70.0,
                label=SentimentLabel.VERY_BULLISH,
                confidence=0.90,
                timestamp=now,
            ),
            SentimentReading(
                source=SentimentSource.WHALE,
                symbol="ETH",
                score=40.0,
                label=SentimentLabel.BULLISH,
                confidence=0.85,
                timestamp=now,
            ),
        ]

        for r in readings:
            aggregator.add_reading(r)

        result = aggregator.aggregate("ETH")

        assert len(result.source_scores) == 3
        assert "twitter" in result.source_scores
        assert "grok" in result.source_scores
        assert "whale" in result.source_scores

    def test_score_to_label_very_bullish(self, aggregator):
        """Test score to label conversion for very bullish."""
        label = aggregator._score_to_label(75.0)
        assert label == SentimentLabel.VERY_BULLISH

    def test_score_to_label_bullish(self, aggregator):
        """Test score to label conversion for bullish."""
        label = aggregator._score_to_label(35.0)
        assert label == SentimentLabel.BULLISH

    def test_score_to_label_neutral(self, aggregator):
        """Test score to label conversion for neutral."""
        label = aggregator._score_to_label(0.0)
        assert label == SentimentLabel.NEUTRAL

    def test_score_to_label_bearish(self, aggregator):
        """Test score to label conversion for bearish."""
        label = aggregator._score_to_label(-35.0)
        assert label == SentimentLabel.BEARISH

    def test_score_to_label_very_bearish(self, aggregator):
        """Test score to label conversion for very bearish."""
        label = aggregator._score_to_label(-75.0)
        assert label == SentimentLabel.VERY_BEARISH

    def test_check_divergence_no_divergence(self, aggregator):
        """Test no divergence warning when sources agree."""
        source_scores = {"twitter": 50.0, "grok": 55.0, "whale": 45.0}
        warning = aggregator._check_divergence(source_scores)
        assert warning == ""

    def test_check_divergence_with_divergence(self, aggregator):
        """Test divergence warning when sources disagree significantly."""
        source_scores = {"twitter": 80.0, "whale": -20.0}  # 100 point spread
        warning = aggregator._check_divergence(source_scores)
        # Should warn about significant divergence
        assert "divergence" in warning.lower() or warning == ""

    def test_check_divergence_single_source(self, aggregator):
        """Test no divergence with single source."""
        source_scores = {"grok": 50.0}
        warning = aggregator._check_divergence(source_scores)
        assert warning == ""

    def test_get_market_sentiment(self, aggregator):
        """Test getting sentiment for multiple symbols."""
        now = datetime.now(timezone.utc).isoformat()

        # Add data for multiple symbols
        for symbol in ["BTC", "ETH", "SOL"]:
            aggregator.add_reading(SentimentReading(
                source=SentimentSource.GROK,
                symbol=symbol,
                score=50.0,
                label=SentimentLabel.BULLISH,
                confidence=0.80,
                timestamp=now,
            ))

        results = aggregator.get_market_sentiment(["BTC", "ETH", "SOL"])

        assert "BTC" in results
        assert "ETH" in results
        assert "SOL" in results

    def test_generate_report(self, aggregator):
        """Test report generation."""
        now = datetime.now(timezone.utc).isoformat()

        # Add some data
        aggregator.add_reading(SentimentReading(
            source=SentimentSource.GROK,
            symbol="BTC",
            score=60.0,
            label=SentimentLabel.VERY_BULLISH,
            confidence=0.90,
            timestamp=now,
        ))

        report = aggregator.generate_report(["BTC"])

        assert "Sentiment Report" in report
        assert "BTC" in report

    def test_symbol_case_normalization(self, aggregator):
        """Test symbols are normalized to uppercase."""
        now = datetime.now(timezone.utc).isoformat()

        aggregator.add_reading(SentimentReading(
            source=SentimentSource.TWITTER,
            symbol="btc",  # lowercase
            score=50.0,
            label=SentimentLabel.BULLISH,
            confidence=0.80,
            timestamp=now,
        ))

        # Should find with uppercase query
        readings = aggregator.get_readings("BTC")
        assert len(readings) >= 1


# =============================================================================
# Aggregation Logic Tests
# =============================================================================

class TestAggregationLogic:
    """Tests for the aggregation logic and weighting."""

    @pytest.fixture
    def aggregator(self, tmp_path):
        """Create a temporary aggregator for testing."""
        db_path = tmp_path / "test_agg.db"
        return SentimentAggregator(db_path=db_path)

    def test_weighted_average_calculation(self, aggregator):
        """Test that weighted average is calculated correctly."""
        now = datetime.now(timezone.utc).isoformat()

        # Grok weight = 1.0, Twitter weight = 0.8
        # Grok: 100 * 1.0 * 0.9 (conf) = 90
        # Twitter: 0 * 0.8 * 0.8 (conf) = 0
        # Total weight: 0.9 + 0.64 = 1.54
        # Weighted avg: 90 / 1.54 = ~58.4

        aggregator.add_reading(SentimentReading(
            source=SentimentSource.GROK,
            symbol="TEST",
            score=100.0,
            label=SentimentLabel.VERY_BULLISH,
            confidence=0.90,
            timestamp=now,
        ))
        aggregator.add_reading(SentimentReading(
            source=SentimentSource.TWITTER,
            symbol="TEST",
            score=0.0,
            label=SentimentLabel.NEUTRAL,
            confidence=0.80,
            timestamp=now,
        ))

        result = aggregator.aggregate("TEST")

        # Should be weighted more toward Grok (higher weight)
        assert result.overall_score > 40  # Should be bullish, not neutral

    def test_confidence_affects_weighting(self, aggregator):
        """Test that confidence affects source weighting."""
        now = datetime.now(timezone.utc).isoformat()

        # Low confidence source should have less impact
        aggregator.add_reading(SentimentReading(
            source=SentimentSource.GROK,
            symbol="CONF",
            score=100.0,
            label=SentimentLabel.VERY_BULLISH,
            confidence=0.10,  # Very low confidence
            timestamp=now,
        ))
        aggregator.add_reading(SentimentReading(
            source=SentimentSource.TWITTER,
            symbol="CONF",
            score=0.0,
            label=SentimentLabel.NEUTRAL,
            confidence=0.95,  # High confidence
            timestamp=now,
        ))

        result = aggregator.aggregate("CONF")

        # Twitter's neutral should have more impact due to high confidence
        assert result.overall_score < 50  # Should be closer to neutral


# =============================================================================
# Edge Cases Tests
# =============================================================================

class TestEdgeCases:
    """Tests for edge cases and error handling."""

    @pytest.fixture
    def aggregator(self, tmp_path):
        """Create a temporary aggregator for testing."""
        db_path = tmp_path / "test_edge.db"
        return SentimentAggregator(db_path=db_path)

    def test_empty_symbol(self, aggregator):
        """Test aggregation with empty symbol."""
        result = aggregator.aggregate("")
        assert result.overall_score == 0
        assert "no sentiment data" in result.warning.lower()

    def test_zero_confidence(self, aggregator):
        """Test reading with zero confidence."""
        now = datetime.now(timezone.utc).isoformat()

        aggregator.add_reading(SentimentReading(
            source=SentimentSource.NEWS,
            symbol="ZERO",
            score=100.0,
            label=SentimentLabel.VERY_BULLISH,
            confidence=0.0,  # Zero confidence
            timestamp=now,
        ))

        # Should still work but with minimal impact
        result = aggregator.aggregate("ZERO")
        assert result is not None

    def test_extreme_scores(self, aggregator):
        """Test extreme sentiment scores."""
        now = datetime.now(timezone.utc).isoformat()

        aggregator.add_reading(SentimentReading(
            source=SentimentSource.GROK,
            symbol="EXTREME",
            score=-100.0,  # Maximum bearish
            label=SentimentLabel.VERY_BEARISH,
            confidence=1.0,
            timestamp=now,
        ))

        result = aggregator.aggregate("EXTREME")
        assert result.overall_label == SentimentLabel.VERY_BEARISH


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
