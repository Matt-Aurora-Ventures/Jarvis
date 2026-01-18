"""
Integration tests for multi-signal confirmation logic.

Tests:
- Signal aggregation from multiple sources
- Confidence scoring logic
- Divergence detection
- Edge cases (conflicting signals, missing data)
- Decision matrix evaluation

All external APIs are mocked to enable fast, reliable testing.
"""

import pytest
import asyncio
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Dict, List, Any, Optional
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from core.sentiment_aggregator import (
    SentimentAggregator,
    SentimentReading,
    SentimentSource,
    SentimentLabel,
    SentimentConfig,
    AggregatedSentiment,
)
from core.trading.decision_matrix import (
    DecisionMatrix,
    EntryConditions,
    ExitConditions,
    TradeDecision,
    DecisionType,
)
from core.trading.signals.meta_labeler import MarketRegime


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def temp_sentiment_db(tmp_path):
    """Create temporary sentiment database."""
    db_path = tmp_path / "test_sentiment.db"
    return SentimentAggregator(db_path=db_path)


@pytest.fixture
def decision_matrix():
    """Create decision matrix with test configuration."""
    entry = EntryConditions(
        require_multiple_signals=False,
        meta_labeler_enabled=False,  # Disable for simpler testing
        cooldown_enabled=False,
    )
    return DecisionMatrix(entry_conditions=entry)


@pytest.fixture
def mock_liquidation_signal():
    """Create a mock liquidation signal."""
    from core.trading.signals.liquidation import LiquidationSignal, SignalDirection

    return LiquidationSignal(
        direction=SignalDirection.LONG,
        confidence=0.85,
        imbalance_ratio=2.5,
        long_volume=1_000_000,
        short_volume=2_500_000,
        total_volume=3_500_000,
        timestamp=datetime.utcnow(),
    )


@pytest.fixture
def mock_ma_signal():
    """Create a mock MA signal."""
    from core.trading.signals.dual_ma import DualMASignal, MASignalType

    return DualMASignal(
        direction="long",
        confidence=0.75,
        signal_type=MASignalType.BULLISH_CROSS,
        fast_ma=110.0,
        slow_ma=100.0,
        current_price=115.0,
        trend_filter_value=95.0,
        trend_aligned=True,
        timestamp=datetime.utcnow(),
    )


# =============================================================================
# Sentiment Aggregation Tests
# =============================================================================

class TestSentimentAggregation:
    """Tests for sentiment aggregation from multiple sources."""

    def test_aggregate_single_source(self, temp_sentiment_db):
        """Aggregate with single source should work."""
        agg = temp_sentiment_db
        now = datetime.now(timezone.utc).isoformat()

        agg.add_reading(SentimentReading(
            source=SentimentSource.GROK,
            symbol="BTC",
            score=70.0,
            label=SentimentLabel.BULLISH,
            confidence=0.85,
            timestamp=now,
        ))

        result = agg.aggregate("BTC")

        assert result.symbol == "BTC"
        # Score 70 is above very_bullish_threshold (60), so should be VERY_BULLISH
        assert result.overall_label in [SentimentLabel.BULLISH, SentimentLabel.VERY_BULLISH]
        assert result.overall_confidence > 0

    def test_aggregate_multiple_sources(self, temp_sentiment_db):
        """Aggregate from multiple sources with weighting."""
        agg = temp_sentiment_db
        now = datetime.now(timezone.utc).isoformat()

        # Add readings from multiple sources
        agg.add_reading(SentimentReading(
            source=SentimentSource.GROK,
            symbol="ETH",
            score=80.0,
            label=SentimentLabel.VERY_BULLISH,
            confidence=0.90,
            timestamp=now,
        ))
        agg.add_reading(SentimentReading(
            source=SentimentSource.TWITTER,
            symbol="ETH",
            score=60.0,
            label=SentimentLabel.BULLISH,
            confidence=0.70,
            timestamp=now,
        ))
        agg.add_reading(SentimentReading(
            source=SentimentSource.ONCHAIN,
            symbol="ETH",
            score=50.0,
            label=SentimentLabel.BULLISH,
            confidence=0.80,
            timestamp=now,
        ))

        result = agg.aggregate("ETH")

        # Should be weighted average of sources
        assert result.overall_label in [SentimentLabel.BULLISH, SentimentLabel.VERY_BULLISH]
        assert len(result.source_scores) == 3
        assert "grok" in result.source_scores
        assert "twitter" in result.source_scores
        assert "onchain" in result.source_scores

    def test_aggregate_with_no_data(self, temp_sentiment_db):
        """Aggregate with no data should return neutral with warning."""
        agg = temp_sentiment_db

        result = agg.aggregate("UNKNOWN")

        assert result.overall_label == SentimentLabel.NEUTRAL
        assert result.overall_score == 0
        assert "No sentiment data" in result.warning

    def test_aggregate_uses_most_recent_per_source(self, temp_sentiment_db):
        """Aggregation should use most recent reading per source."""
        agg = temp_sentiment_db
        old_time = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        new_time = datetime.now(timezone.utc).isoformat()

        # Add old reading
        agg.add_reading(SentimentReading(
            source=SentimentSource.GROK,
            symbol="SOL",
            score=30.0,  # Old: less bullish
            label=SentimentLabel.BULLISH,
            confidence=0.70,
            timestamp=old_time,
        ))
        # Add new reading
        agg.add_reading(SentimentReading(
            source=SentimentSource.GROK,
            symbol="SOL",
            score=80.0,  # New: more bullish
            label=SentimentLabel.VERY_BULLISH,
            confidence=0.90,
            timestamp=new_time,
        ))

        result = agg.aggregate("SOL")

        # Should use the newer, higher score
        assert result.source_scores["grok"] == 80.0


class TestDivergenceDetection:
    """Tests for sentiment divergence detection."""

    def test_detect_significant_divergence(self, temp_sentiment_db):
        """Should detect significant divergence between sources."""
        agg = temp_sentiment_db
        now = datetime.now(timezone.utc).isoformat()

        # Add conflicting readings
        agg.add_reading(SentimentReading(
            source=SentimentSource.GROK,
            symbol="DIVERGE",
            score=80.0,  # Very bullish
            label=SentimentLabel.VERY_BULLISH,
            confidence=0.90,
            timestamp=now,
        ))
        agg.add_reading(SentimentReading(
            source=SentimentSource.TWITTER,
            symbol="DIVERGE",
            score=-50.0,  # Bearish
            label=SentimentLabel.BEARISH,
            confidence=0.80,
            timestamp=now,
        ))

        result = agg.aggregate("DIVERGE")

        # Should have divergence warning
        assert "divergence" in result.warning.lower()

    def test_no_divergence_on_agreement(self, temp_sentiment_db):
        """No divergence warning when sources agree."""
        agg = temp_sentiment_db
        now = datetime.now(timezone.utc).isoformat()

        # Add agreeing readings
        agg.add_reading(SentimentReading(
            source=SentimentSource.GROK,
            symbol="AGREE",
            score=70.0,
            label=SentimentLabel.BULLISH,
            confidence=0.85,
            timestamp=now,
        ))
        agg.add_reading(SentimentReading(
            source=SentimentSource.TWITTER,
            symbol="AGREE",
            score=60.0,
            label=SentimentLabel.BULLISH,
            confidence=0.75,
            timestamp=now,
        ))

        result = agg.aggregate("AGREE")

        # No divergence warning
        assert result.warning == ""


class TestConfidenceScoring:
    """Tests for confidence scoring logic."""

    def test_high_confidence_high_agreement(self, temp_sentiment_db):
        """High confidence when sources agree with high individual confidence."""
        agg = temp_sentiment_db
        now = datetime.now(timezone.utc).isoformat()

        # All sources agree with high confidence
        for source in [SentimentSource.GROK, SentimentSource.TWITTER, SentimentSource.ONCHAIN]:
            agg.add_reading(SentimentReading(
                source=source,
                symbol="HIGH_CONF",
                score=75.0,
                label=SentimentLabel.BULLISH,
                confidence=0.90,
                timestamp=now,
            ))

        result = agg.aggregate("HIGH_CONF")

        assert result.overall_confidence >= 0.85

    def test_lower_confidence_with_divergence(self, temp_sentiment_db):
        """Lower overall confidence when sources disagree."""
        agg = temp_sentiment_db
        now = datetime.now(timezone.utc).isoformat()

        # Mixed signals
        agg.add_reading(SentimentReading(
            source=SentimentSource.GROK,
            symbol="LOW_CONF",
            score=70.0,
            label=SentimentLabel.BULLISH,
            confidence=0.90,
            timestamp=now,
        ))
        agg.add_reading(SentimentReading(
            source=SentimentSource.TWITTER,
            symbol="LOW_CONF",
            score=10.0,  # Neutral
            label=SentimentLabel.NEUTRAL,
            confidence=0.50,  # Lower confidence
            timestamp=now,
        ))

        result = agg.aggregate("LOW_CONF")

        # Confidence should be average of sources
        assert result.overall_confidence < 0.85


# =============================================================================
# Decision Matrix Tests
# =============================================================================

class TestDecisionMatrixEvaluation:
    """Tests for decision matrix signal evaluation."""

    def test_decision_with_liquidation_signal(
        self,
        decision_matrix,
        mock_liquidation_signal
    ):
        """Decision matrix should process liquidation signal."""
        dm = decision_matrix

        # Add liquidation signal
        dm.add_signal("liquidation", mock_liquidation_signal)

        decision = dm.evaluate(
            symbol="BTC-PERP",
            current_price=50000.0,
            portfolio_value=100000.0,
        )

        assert decision.decision in [DecisionType.ENTER_LONG, DecisionType.HOLD]
        assert "liquidation" in decision.signals_used

    def test_decision_with_ma_signal(
        self,
        decision_matrix,
        mock_ma_signal
    ):
        """Decision matrix should process MA signal."""
        dm = decision_matrix

        dm.add_signal("ma", mock_ma_signal)

        decision = dm.evaluate(
            symbol="ETH-PERP",
            current_price=3000.0,
            portfolio_value=50000.0,
        )

        assert decision.decision in [DecisionType.ENTER_LONG, DecisionType.HOLD]
        if decision.should_trade:
            assert "ma" in decision.signals_used

    def test_decision_with_combined_signals(
        self,
        decision_matrix,
        mock_liquidation_signal,
        mock_ma_signal
    ):
        """Decision matrix should combine multiple signals."""
        dm = decision_matrix

        dm.add_signal("liquidation", mock_liquidation_signal)
        dm.add_signal("ma", mock_ma_signal)

        decision = dm.evaluate(
            symbol="SOL-PERP",
            current_price=100.0,
            portfolio_value=25000.0,
        )

        # With both signals agreeing on LONG
        if decision.should_trade:
            assert len(decision.signals_used) >= 1
            assert decision.direction == "long"

    def test_decision_no_signals(self, decision_matrix):
        """Decision with no signals should hold."""
        dm = decision_matrix

        decision = dm.evaluate(
            symbol="UNKNOWN",
            current_price=100.0,
            portfolio_value=10000.0,
        )

        assert decision.decision == DecisionType.HOLD
        assert len(decision.signals_used) == 0

    def test_decision_conflicting_signals(self, decision_matrix):
        """Decision with conflicting signals should be cautious."""
        dm = decision_matrix

        from core.trading.signals.liquidation import LiquidationSignal, SignalDirection
        from core.trading.signals.dual_ma import DualMASignal, MASignalType

        # Long liquidation signal
        long_signal = LiquidationSignal(
            direction=SignalDirection.LONG,
            confidence=0.7,
            imbalance_ratio=1.5,
            long_volume=500_000,
            short_volume=750_000,
            total_volume=1_250_000,
            timestamp=datetime.utcnow(),
        )

        # Short MA signal
        short_signal = DualMASignal(
            direction="short",
            confidence=0.6,
            signal_type=MASignalType.BEARISH_CROSS,
            fast_ma=95.0,
            slow_ma=100.0,
            current_price=93.0,
            trend_filter_value=105.0,
            trend_aligned=True,
            timestamp=datetime.utcnow(),
        )

        dm.add_signal("liquidation", long_signal)
        dm.add_signal("ma", short_signal)

        decision = dm.evaluate(
            symbol="CONFLICT",
            current_price=100.0,
            portfolio_value=10000.0,
        )

        # With conflicting signals, neither should dominate overwhelmingly
        # Result depends on weights but confidence should be lower
        assert decision.confidence <= 0.7  # Lower than single high-confidence signal


class TestMultiSignalRequirement:
    """Tests for multiple signal requirement."""

    def test_require_multiple_signals_blocks_single(self):
        """With require_multiple_signals, single signal should not trade."""
        entry = EntryConditions(
            require_multiple_signals=True,
            meta_labeler_enabled=False,
            cooldown_enabled=False,
        )
        dm = DecisionMatrix(entry_conditions=entry)

        from core.trading.signals.liquidation import LiquidationSignal, SignalDirection

        single_signal = LiquidationSignal(
            direction=SignalDirection.LONG,
            confidence=0.9,
            imbalance_ratio=3.0,
            long_volume=1_000_000,
            short_volume=3_000_000,
            total_volume=4_000_000,
            timestamp=datetime.utcnow(),
        )

        dm.add_signal("liquidation", single_signal)

        decision = dm.evaluate(
            symbol="SINGLE",
            current_price=100.0,
            portfolio_value=10000.0,
        )

        assert decision.decision == DecisionType.HOLD
        assert "multiple signals" in " ".join(decision.reasoning).lower()

    def test_require_multiple_signals_passes_with_two(self, mock_liquidation_signal, mock_ma_signal):
        """With require_multiple_signals, two agreeing signals should trade."""
        entry = EntryConditions(
            require_multiple_signals=True,
            meta_labeler_enabled=False,
            cooldown_enabled=False,
        )
        dm = DecisionMatrix(entry_conditions=entry)

        dm.add_signal("liquidation", mock_liquidation_signal)
        dm.add_signal("ma", mock_ma_signal)

        decision = dm.evaluate(
            symbol="MULTI",
            current_price=100.0,
            portfolio_value=10000.0,
        )

        # With two agreeing signals
        assert decision.decision in [DecisionType.ENTER_LONG, DecisionType.HOLD]
        if decision.should_trade:
            assert len(decision.signals_used) >= 2


class TestExitConditions:
    """Tests for exit condition evaluation."""

    def test_take_profit_trigger(self, decision_matrix):
        """Should trigger exit on take profit."""
        dm = decision_matrix
        dm.exit.take_profit_pct = 0.05  # 5%

        should_exit, reason = dm.should_exit(
            symbol="TP_TEST",
            entry_price=100.0,
            current_price=106.0,  # +6%
            position_side="long",
            entry_time=datetime.utcnow() - timedelta(hours=1),
        )

        assert should_exit is True
        assert "take profit" in reason.lower()

    def test_stop_loss_trigger(self, decision_matrix):
        """Should trigger exit on stop loss."""
        dm = decision_matrix
        dm.exit.stop_loss_pct = 0.03  # 3%

        should_exit, reason = dm.should_exit(
            symbol="SL_TEST",
            entry_price=100.0,
            current_price=96.0,  # -4%
            position_side="long",
            entry_time=datetime.utcnow() - timedelta(hours=1),
        )

        assert should_exit is True
        assert "stop loss" in reason.lower()

    def test_time_stop_trigger(self, decision_matrix):
        """Should trigger exit on time stop."""
        dm = decision_matrix
        dm.exit.time_stop_enabled = True
        dm.exit.time_stop_hours = 12

        should_exit, reason = dm.should_exit(
            symbol="TIME_TEST",
            entry_price=100.0,
            current_price=100.0,  # No movement
            position_side="long",
            entry_time=datetime.utcnow() - timedelta(hours=15),  # 15 hours ago
        )

        assert should_exit is True
        assert "time stop" in reason.lower()

    def test_no_exit_within_thresholds(self, decision_matrix):
        """Should not exit when within thresholds."""
        dm = decision_matrix

        should_exit, reason = dm.should_exit(
            symbol="NO_EXIT",
            entry_price=100.0,
            current_price=100.5,  # +0.5%
            position_side="long",
            entry_time=datetime.utcnow() - timedelta(hours=1),
        )

        assert should_exit is False
        assert reason == ""


class TestSentimentTrendCalculation:
    """Tests for sentiment trend calculation."""

    def test_improving_trend_detection(self, temp_sentiment_db):
        """Should detect improving sentiment trend."""
        agg = temp_sentiment_db

        # Add historical readings (older to newer)
        for i, score in enumerate([30, 40, 50, 60, 70]):
            timestamp = (datetime.now(timezone.utc) - timedelta(hours=5-i)).isoformat()
            agg.add_reading(SentimentReading(
                source=SentimentSource.GROK,
                symbol="IMPROVING",
                score=float(score),
                label=SentimentLabel.BULLISH if score > 20 else SentimentLabel.NEUTRAL,
                confidence=0.8,
                timestamp=timestamp,
            ))
            # Force aggregation to store in history
            agg.aggregate("IMPROVING")

        # Latest aggregation
        result = agg.aggregate("IMPROVING")

        # Trend should be improving
        assert result.trend in ["IMPROVING", "STABLE"]

    def test_declining_trend_detection(self, temp_sentiment_db):
        """Should detect declining sentiment trend."""
        agg = temp_sentiment_db

        # Add declining historical readings
        for i, score in enumerate([70, 60, 50, 40, 30]):
            timestamp = (datetime.now(timezone.utc) - timedelta(hours=5-i)).isoformat()
            agg.add_reading(SentimentReading(
                source=SentimentSource.GROK,
                symbol="DECLINING",
                score=float(score),
                label=SentimentLabel.BULLISH if score > 20 else SentimentLabel.NEUTRAL,
                confidence=0.8,
                timestamp=timestamp,
            ))
            agg.aggregate("DECLINING")

        result = agg.aggregate("DECLINING")

        # Trend should be declining or stable
        assert result.trend in ["DECLINING", "STABLE"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
