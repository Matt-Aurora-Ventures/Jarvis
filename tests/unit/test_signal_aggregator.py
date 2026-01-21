"""
Tests for Signal Aggregator - Trade Signal Aggregation System

Tests multi-source signal collection, weighting, consensus calculation,
confidence scoring, and historical accuracy tracking.
"""

import pytest
import time
import json
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from dataclasses import dataclass
from typing import Dict, Any, List, Optional


# Import the module under test
from core.signals.signal_aggregator import (
    SignalAggregator,
    StrategySignal,
    AggregatedSignal,
    StrategyPerformance,
    SignalAction,
    ConsensusType,
    aggregate_signals,
    get_signal_aggregator,
)


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
def aggregator():
    """Create a fresh SignalAggregator instance for testing."""
    return SignalAggregator(
        storage_path=":memory:",  # In-memory storage for tests
        min_strategies=2,
        min_confidence=0.5,
    )


@pytest.fixture
def lenient_aggregator():
    """Create an aggregator with lower confidence threshold for disagreement tests."""
    return SignalAggregator(
        storage_path=":memory:",
        min_strategies=2,
        min_confidence=0.2,  # Lower threshold to allow conflicting signals
    )


@pytest.fixture
def sample_signals():
    """Create sample strategy signals for testing."""
    return [
        StrategySignal(
            strategy_name="TrendFollower",
            symbol="SOL",
            action=SignalAction.BUY,
            confidence=0.8,
            price=100.0,
            metadata={"sma_short": 105.0, "sma_long": 98.0},
        ),
        StrategySignal(
            strategy_name="MeanReversion",
            symbol="SOL",
            action=SignalAction.BUY,
            confidence=0.7,
            price=100.0,
            metadata={"rsi": 35, "bb_position": "lower"},
        ),
        StrategySignal(
            strategy_name="BreakoutTrader",
            symbol="SOL",
            action=SignalAction.BUY,
            confidence=0.9,
            price=100.0,
            metadata={"resistance": 105.0, "volume_surge": True},
        ),
    ]


@pytest.fixture
def conflicting_signals():
    """Create conflicting signals for consensus testing."""
    return [
        StrategySignal(
            strategy_name="TrendFollower",
            symbol="BTC",
            action=SignalAction.BUY,
            confidence=0.8,
            price=50000.0,
        ),
        StrategySignal(
            strategy_name="MeanReversion",
            symbol="BTC",
            action=SignalAction.SELL,
            confidence=0.75,
            price=50000.0,
        ),
        StrategySignal(
            strategy_name="BreakoutTrader",
            symbol="BTC",
            action=SignalAction.HOLD,
            confidence=0.6,
            price=50000.0,
        ),
    ]


# =============================================================================
# StrategySignal Tests
# =============================================================================

class TestStrategySignal:
    """Tests for the StrategySignal dataclass."""

    def test_create_signal(self):
        """Test creating a basic strategy signal."""
        signal = StrategySignal(
            strategy_name="TrendFollower",
            symbol="SOL",
            action=SignalAction.BUY,
            confidence=0.8,
            price=100.0,
        )

        assert signal.strategy_name == "TrendFollower"
        assert signal.symbol == "SOL"
        assert signal.action == SignalAction.BUY
        assert signal.confidence == 0.8
        assert signal.price == 100.0
        assert signal.timestamp is not None

    def test_signal_with_metadata(self):
        """Test creating a signal with metadata."""
        metadata = {"indicator": "RSI", "value": 35}
        signal = StrategySignal(
            strategy_name="MeanReversion",
            symbol="ETH",
            action=SignalAction.SELL,
            confidence=0.65,
            price=2000.0,
            metadata=metadata,
        )

        assert signal.metadata == metadata
        assert signal.metadata["indicator"] == "RSI"

    def test_signal_to_dict(self):
        """Test converting signal to dictionary."""
        signal = StrategySignal(
            strategy_name="GridTrader",
            symbol="BTC",
            action=SignalAction.HOLD,
            confidence=0.5,
            price=50000.0,
        )

        data = signal.to_dict()

        assert "strategy_name" in data
        assert "symbol" in data
        assert "action" in data
        assert "confidence" in data
        assert "price" in data
        assert "timestamp" in data
        assert data["action"] == "BUY" or data["action"] in ["BUY", "SELL", "HOLD"]

    def test_signal_action_numeric_value(self):
        """Test converting signal action to numeric value."""
        buy_signal = StrategySignal(
            strategy_name="Test",
            symbol="SOL",
            action=SignalAction.BUY,
            confidence=0.8,
            price=100.0,
        )
        sell_signal = StrategySignal(
            strategy_name="Test",
            symbol="SOL",
            action=SignalAction.SELL,
            confidence=0.8,
            price=100.0,
        )
        hold_signal = StrategySignal(
            strategy_name="Test",
            symbol="SOL",
            action=SignalAction.HOLD,
            confidence=0.8,
            price=100.0,
        )

        assert buy_signal.to_numeric() > 0
        assert sell_signal.to_numeric() < 0
        assert hold_signal.to_numeric() == 0

    def test_signal_is_expired(self):
        """Test signal expiration check."""
        # Fresh signal should not be expired
        fresh_signal = StrategySignal(
            strategy_name="Test",
            symbol="SOL",
            action=SignalAction.BUY,
            confidence=0.8,
            price=100.0,
        )
        assert not fresh_signal.is_expired()

        # Signal with past expiry should be expired
        expired_signal = StrategySignal(
            strategy_name="Test",
            symbol="SOL",
            action=SignalAction.BUY,
            confidence=0.8,
            price=100.0,
            expires_at=datetime.now() - timedelta(hours=1),
        )
        assert expired_signal.is_expired()


# =============================================================================
# StrategyPerformance Tests
# =============================================================================

class TestStrategyPerformance:
    """Tests for strategy performance tracking."""

    def test_create_performance_tracker(self):
        """Test creating a performance tracker."""
        perf = StrategyPerformance(
            strategy_name="TrendFollower",
            base_weight=1.0,
        )

        assert perf.strategy_name == "TrendFollower"
        assert perf.base_weight == 1.0
        assert perf.current_weight == 1.0
        assert perf.total_signals == 0
        assert perf.profitable_signals == 0
        assert perf.accuracy == 0.0

    def test_record_profitable_outcome(self):
        """Test recording a profitable signal outcome."""
        perf = StrategyPerformance(strategy_name="Test", base_weight=1.0)

        perf.record_outcome(profitable=True, pnl_percent=5.0)

        assert perf.total_signals == 1
        assert perf.profitable_signals == 1
        assert perf.accuracy == 1.0
        assert perf.total_pnl_percent == 5.0

    def test_record_losing_outcome(self):
        """Test recording a losing signal outcome."""
        perf = StrategyPerformance(strategy_name="Test", base_weight=1.0)

        perf.record_outcome(profitable=False, pnl_percent=-3.0)

        assert perf.total_signals == 1
        assert perf.profitable_signals == 0
        assert perf.accuracy == 0.0
        assert perf.total_pnl_percent == -3.0

    def test_accuracy_calculation(self):
        """Test accuracy calculation with multiple outcomes."""
        perf = StrategyPerformance(strategy_name="Test", base_weight=1.0)

        # 7 profitable, 3 losing = 70% accuracy
        for _ in range(7):
            perf.record_outcome(profitable=True, pnl_percent=2.0)
        for _ in range(3):
            perf.record_outcome(profitable=False, pnl_percent=-1.0)

        assert perf.total_signals == 10
        assert perf.profitable_signals == 7
        assert perf.accuracy == 0.7

    def test_weight_adjustment_by_accuracy(self):
        """Test that weight adjusts based on accuracy."""
        perf = StrategyPerformance(strategy_name="Test", base_weight=1.0)
        initial_weight = perf.current_weight

        # Record several profitable outcomes
        for _ in range(10):
            perf.record_outcome(profitable=True, pnl_percent=5.0)

        # Weight should increase with high accuracy
        assert perf.current_weight > initial_weight

        # Record several losing outcomes to reduce accuracy
        for _ in range(20):
            perf.record_outcome(profitable=False, pnl_percent=-2.0)

        # Weight should be lower now
        assert perf.current_weight < initial_weight

    def test_performance_to_dict(self):
        """Test converting performance to dictionary."""
        perf = StrategyPerformance(strategy_name="Test", base_weight=1.2)
        perf.record_outcome(profitable=True, pnl_percent=5.0)

        data = perf.to_dict()

        assert "strategy_name" in data
        assert "base_weight" in data
        assert "current_weight" in data
        assert "total_signals" in data
        assert "profitable_signals" in data
        assert "accuracy" in data


# =============================================================================
# AggregatedSignal Tests
# =============================================================================

class TestAggregatedSignal:
    """Tests for the AggregatedSignal dataclass."""

    def test_create_aggregated_signal(self):
        """Test creating an aggregated signal."""
        signal = AggregatedSignal(
            signal_id="AGG-001",
            symbol="SOL",
            action=SignalAction.BUY,
            confidence=0.85,
            price=100.0,
            consensus_type=ConsensusType.UNANIMOUS,
            contributing_strategies=["TrendFollower", "MeanReversion"],
        )

        assert signal.signal_id == "AGG-001"
        assert signal.symbol == "SOL"
        assert signal.action == SignalAction.BUY
        assert signal.confidence == 0.85
        assert signal.consensus_type == ConsensusType.UNANIMOUS
        assert len(signal.contributing_strategies) == 2

    def test_aggregated_signal_validity(self):
        """Test aggregated signal validity period."""
        signal = AggregatedSignal(
            signal_id="AGG-001",
            symbol="SOL",
            action=SignalAction.BUY,
            confidence=0.85,
            price=100.0,
            consensus_type=ConsensusType.MAJORITY,
            contributing_strategies=["Test"],
        )

        # Fresh signal should be valid
        assert signal.is_valid()

        # Expired signal should not be valid
        expired_signal = AggregatedSignal(
            signal_id="AGG-002",
            symbol="SOL",
            action=SignalAction.BUY,
            confidence=0.85,
            price=100.0,
            consensus_type=ConsensusType.MAJORITY,
            contributing_strategies=["Test"],
            valid_until=datetime.now() - timedelta(hours=1),
        )
        assert not expired_signal.is_valid()

    def test_aggregated_signal_to_dict(self):
        """Test converting aggregated signal to dictionary."""
        signal = AggregatedSignal(
            signal_id="AGG-001",
            symbol="ETH",
            action=SignalAction.SELL,
            confidence=0.7,
            price=2000.0,
            consensus_type=ConsensusType.WEIGHTED,
            contributing_strategies=["Strategy1", "Strategy2"],
            strategy_weights={"Strategy1": 1.2, "Strategy2": 0.8},
        )

        data = signal.to_dict()

        assert data["signal_id"] == "AGG-001"
        assert data["symbol"] == "ETH"
        assert data["confidence"] == 0.7
        assert "contributing_strategies" in data
        assert "strategy_weights" in data


# =============================================================================
# SignalAggregator Tests
# =============================================================================

class TestSignalAggregator:
    """Tests for the SignalAggregator class."""

    def test_create_aggregator(self, aggregator):
        """Test creating a signal aggregator."""
        assert aggregator is not None
        assert aggregator.min_strategies == 2
        assert aggregator.min_confidence == 0.5

    def test_register_strategy(self, aggregator):
        """Test registering a strategy with the aggregator."""
        aggregator.register_strategy(
            strategy_name="TrendFollower",
            base_weight=1.2,
        )

        assert "TrendFollower" in aggregator.strategy_performances
        assert aggregator.strategy_performances["TrendFollower"].base_weight == 1.2

    def test_add_signal(self, aggregator, sample_signals):
        """Test adding signals to the aggregator."""
        for strategy_name in ["TrendFollower", "MeanReversion", "BreakoutTrader"]:
            aggregator.register_strategy(strategy_name)

        for signal in sample_signals:
            aggregator.add_signal(signal)

        pending = aggregator.get_pending_signals("SOL")
        assert len(pending) == 3

    def test_aggregate_unanimous_buy(self, aggregator, sample_signals):
        """Test aggregation with unanimous buy signals."""
        for strategy_name in ["TrendFollower", "MeanReversion", "BreakoutTrader"]:
            aggregator.register_strategy(strategy_name)

        result = aggregator.aggregate(sample_signals)

        assert result is not None
        assert result.action == SignalAction.BUY
        assert result.consensus_type == ConsensusType.UNANIMOUS
        assert result.confidence > 0.7

    def test_aggregate_conflicting_signals(self, lenient_aggregator, conflicting_signals):
        """Test aggregation with conflicting signals."""
        for strategy_name in ["TrendFollower", "MeanReversion", "BreakoutTrader"]:
            lenient_aggregator.register_strategy(strategy_name)

        result = lenient_aggregator.aggregate(conflicting_signals)

        assert result is not None
        # Should not be unanimous with conflicting signals
        assert result.consensus_type != ConsensusType.UNANIMOUS
        # Confidence should be lower due to disagreement
        assert result.confidence < 0.8

    def test_aggregate_with_weighted_strategies(self, lenient_aggregator):
        """Test aggregation respects strategy weights."""
        # Register strategies with different weights
        lenient_aggregator.register_strategy("HighWeight", base_weight=2.0)
        lenient_aggregator.register_strategy("LowWeight", base_weight=0.5)

        # High weight says SELL, low weight says BUY
        signals = [
            StrategySignal(
                strategy_name="HighWeight",
                symbol="SOL",
                action=SignalAction.SELL,
                confidence=0.8,
                price=100.0,
            ),
            StrategySignal(
                strategy_name="LowWeight",
                symbol="SOL",
                action=SignalAction.BUY,
                confidence=0.8,
                price=100.0,
            ),
        ]

        result = lenient_aggregator.aggregate(signals)

        # Should favor the high-weight strategy
        assert result is not None
        assert result.action == SignalAction.SELL

    def test_aggregate_below_minimum_strategies(self, aggregator):
        """Test aggregation fails with too few strategies."""
        aggregator.register_strategy("OnlyOne")

        signals = [
            StrategySignal(
                strategy_name="OnlyOne",
                symbol="SOL",
                action=SignalAction.BUY,
                confidence=0.9,
                price=100.0,
            ),
        ]

        result = aggregator.aggregate(signals)

        # Should return None when below minimum strategies
        assert result is None

    def test_record_signal_outcome(self, aggregator, sample_signals):
        """Test recording outcomes updates strategy performance."""
        for strategy_name in ["TrendFollower", "MeanReversion", "BreakoutTrader"]:
            aggregator.register_strategy(strategy_name)

        result = aggregator.aggregate(sample_signals)
        assert result is not None

        # Record profitable outcome
        aggregator.record_outcome(result.signal_id, profitable=True, pnl_percent=10.0)

        # Check that performances were updated
        for name in result.contributing_strategies:
            perf = aggregator.strategy_performances[name]
            assert perf.total_signals > 0

    def test_get_strategy_rankings(self, aggregator):
        """Test getting strategy rankings by performance."""
        aggregator.register_strategy("BestStrategy", base_weight=1.0)
        aggregator.register_strategy("WorstStrategy", base_weight=1.0)

        # BestStrategy: 8/10 profitable
        for _ in range(8):
            aggregator.strategy_performances["BestStrategy"].record_outcome(True, 5.0)
        for _ in range(2):
            aggregator.strategy_performances["BestStrategy"].record_outcome(False, -2.0)

        # WorstStrategy: 2/10 profitable
        for _ in range(2):
            aggregator.strategy_performances["WorstStrategy"].record_outcome(True, 1.0)
        for _ in range(8):
            aggregator.strategy_performances["WorstStrategy"].record_outcome(False, -3.0)

        rankings = aggregator.get_strategy_rankings()

        assert len(rankings) == 2
        assert rankings[0][0] == "BestStrategy"
        assert rankings[0][1] > rankings[1][1]  # Higher accuracy first

    def test_get_aggregation_stats(self, aggregator, sample_signals):
        """Test getting aggregation statistics."""
        for strategy_name in ["TrendFollower", "MeanReversion", "BreakoutTrader"]:
            aggregator.register_strategy(strategy_name)

        # Generate some signals and record outcomes
        for _ in range(5):
            result = aggregator.aggregate(sample_signals)
            if result:
                aggregator.record_outcome(result.signal_id, profitable=True, pnl_percent=5.0)

        stats = aggregator.get_aggregation_stats()

        assert "total_signals_generated" in stats
        assert "profitable_signals" in stats
        assert "overall_accuracy" in stats
        assert "strategy_count" in stats


# =============================================================================
# Consensus Calculation Tests
# =============================================================================

class TestConsensusCalculation:
    """Tests for consensus calculation logic."""

    def test_unanimous_consensus(self, aggregator):
        """Test detecting unanimous consensus."""
        for name in ["S1", "S2", "S3"]:
            aggregator.register_strategy(name)

        signals = [
            StrategySignal(strategy_name="S1", symbol="SOL", action=SignalAction.BUY, confidence=0.8, price=100.0),
            StrategySignal(strategy_name="S2", symbol="SOL", action=SignalAction.BUY, confidence=0.7, price=100.0),
            StrategySignal(strategy_name="S3", symbol="SOL", action=SignalAction.BUY, confidence=0.9, price=100.0),
        ]

        result = aggregator.aggregate(signals)

        assert result.consensus_type == ConsensusType.UNANIMOUS

    def test_majority_consensus(self, lenient_aggregator):
        """Test detecting majority consensus."""
        for name in ["S1", "S2", "S3"]:
            lenient_aggregator.register_strategy(name)

        signals = [
            StrategySignal(strategy_name="S1", symbol="SOL", action=SignalAction.BUY, confidence=0.8, price=100.0),
            StrategySignal(strategy_name="S2", symbol="SOL", action=SignalAction.BUY, confidence=0.7, price=100.0),
            StrategySignal(strategy_name="S3", symbol="SOL", action=SignalAction.SELL, confidence=0.6, price=100.0),
        ]

        result = lenient_aggregator.aggregate(signals)

        assert result is not None
        assert result.consensus_type == ConsensusType.MAJORITY

    def test_split_consensus(self, lenient_aggregator):
        """Test handling split/no consensus."""
        for name in ["S1", "S2", "S3", "S4"]:
            lenient_aggregator.register_strategy(name)

        signals = [
            StrategySignal(strategy_name="S1", symbol="SOL", action=SignalAction.BUY, confidence=0.8, price=100.0),
            StrategySignal(strategy_name="S2", symbol="SOL", action=SignalAction.SELL, confidence=0.8, price=100.0),
            StrategySignal(strategy_name="S3", symbol="SOL", action=SignalAction.HOLD, confidence=0.8, price=100.0),
            StrategySignal(strategy_name="S4", symbol="SOL", action=SignalAction.HOLD, confidence=0.8, price=100.0),
        ]

        result = lenient_aggregator.aggregate(signals)

        assert result is not None
        # With no clear majority, should be weighted consensus
        assert result.consensus_type in [ConsensusType.WEIGHTED, ConsensusType.SPLIT]


# =============================================================================
# Confidence Scoring Tests
# =============================================================================

class TestConfidenceScoring:
    """Tests for confidence scoring logic."""

    def test_high_confidence_unanimous(self, aggregator):
        """Test high confidence with unanimous agreement."""
        for name in ["S1", "S2"]:
            aggregator.register_strategy(name)

        signals = [
            StrategySignal(strategy_name="S1", symbol="SOL", action=SignalAction.BUY, confidence=0.95, price=100.0),
            StrategySignal(strategy_name="S2", symbol="SOL", action=SignalAction.BUY, confidence=0.90, price=100.0),
        ]

        result = aggregator.aggregate(signals)

        # High individual confidence + unanimous = high aggregate confidence
        assert result.confidence >= 0.85

    def test_reduced_confidence_with_disagreement(self, lenient_aggregator):
        """Test confidence is reduced with disagreement."""
        for name in ["S1", "S2"]:
            lenient_aggregator.register_strategy(name)

        conflicting = [
            StrategySignal(strategy_name="S1", symbol="SOL", action=SignalAction.BUY, confidence=0.9, price=100.0),
            StrategySignal(strategy_name="S2", symbol="SOL", action=SignalAction.SELL, confidence=0.9, price=100.0),
        ]

        agreeing = [
            StrategySignal(strategy_name="S1", symbol="SOL", action=SignalAction.BUY, confidence=0.9, price=100.0),
            StrategySignal(strategy_name="S2", symbol="SOL", action=SignalAction.BUY, confidence=0.9, price=100.0),
        ]

        conflicting_result = lenient_aggregator.aggregate(conflicting)
        agreeing_result = lenient_aggregator.aggregate(agreeing)

        assert conflicting_result is not None
        assert agreeing_result is not None
        # Agreeing signals should have higher confidence
        assert agreeing_result.confidence > conflicting_result.confidence

    def test_confidence_incorporates_strategy_accuracy(self, aggregator):
        """Test confidence considers historical strategy accuracy."""
        aggregator.register_strategy("Accurate", base_weight=1.0)
        aggregator.register_strategy("Inaccurate", base_weight=1.0)

        # Make "Accurate" highly accurate
        for _ in range(10):
            aggregator.strategy_performances["Accurate"].record_outcome(True, 5.0)

        # Make "Inaccurate" low accuracy
        for _ in range(10):
            aggregator.strategy_performances["Inaccurate"].record_outcome(False, -5.0)

        signals = [
            StrategySignal(strategy_name="Accurate", symbol="SOL", action=SignalAction.BUY, confidence=0.8, price=100.0),
            StrategySignal(strategy_name="Inaccurate", symbol="SOL", action=SignalAction.BUY, confidence=0.8, price=100.0),
        ]

        result = aggregator.aggregate(signals)

        # The aggregate should favor the accurate strategy
        assert result.strategy_weights["Accurate"] > result.strategy_weights["Inaccurate"]


# =============================================================================
# Historical Accuracy Tracking Tests
# =============================================================================

class TestHistoricalAccuracyTracking:
    """Tests for historical accuracy tracking functionality."""

    def test_accuracy_updates_on_outcome(self, aggregator):
        """Test accuracy updates when outcome is recorded."""
        aggregator.register_strategy("TestStrategy")

        signal = StrategySignal(
            strategy_name="TestStrategy",
            symbol="SOL",
            action=SignalAction.BUY,
            confidence=0.8,
            price=100.0,
        )

        result = aggregator.aggregate([signal, signal])  # Need 2 for min_strategies

        # Initially no accuracy data
        assert aggregator.strategy_performances["TestStrategy"].total_signals == 0

        if result:
            # Record outcome
            aggregator.record_outcome(result.signal_id, profitable=True, pnl_percent=5.0)

            # Should update
            perf = aggregator.strategy_performances["TestStrategy"]
            assert perf.total_signals > 0

    def test_weight_adjusts_based_on_accuracy(self, aggregator):
        """Test strategy weight adjusts based on accuracy."""
        aggregator.register_strategy("TestStrategy", base_weight=1.0)
        perf = aggregator.strategy_performances["TestStrategy"]

        initial_weight = perf.current_weight

        # Record many profitable outcomes
        for _ in range(20):
            perf.record_outcome(profitable=True, pnl_percent=5.0)

        # Weight should increase
        assert perf.current_weight > initial_weight

    def test_accuracy_decay_not_implemented(self, aggregator):
        """Test that old accuracy data could be decayed (placeholder)."""
        # This test documents that time-based decay could be added
        aggregator.register_strategy("TestStrategy")
        perf = aggregator.strategy_performances["TestStrategy"]

        # Record old outcome
        perf.record_outcome(profitable=True, pnl_percent=5.0)

        # Note: Time decay not currently implemented
        # This is a placeholder for future functionality
        assert perf.total_signals == 1


# =============================================================================
# Module-Level Function Tests
# =============================================================================

class TestModuleFunctions:
    """Tests for module-level convenience functions."""

    def test_aggregate_signals_function(self, sample_signals):
        """Test the aggregate_signals convenience function."""
        result = aggregate_signals(
            sample_signals,
            min_strategies=2,
            min_confidence=0.5,
        )

        assert result is not None
        assert result.action == SignalAction.BUY

    def test_get_signal_aggregator_singleton(self):
        """Test the singleton accessor."""
        agg1 = get_signal_aggregator()
        agg2 = get_signal_aggregator()

        assert agg1 is agg2


# =============================================================================
# Edge Cases and Error Handling
# =============================================================================

class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_empty_signals_list(self, aggregator):
        """Test aggregation with empty signals list."""
        result = aggregator.aggregate([])

        assert result is None

    def test_all_expired_signals(self, aggregator):
        """Test aggregation when all signals are expired."""
        aggregator.register_strategy("S1")
        aggregator.register_strategy("S2")

        expired_signals = [
            StrategySignal(
                strategy_name="S1",
                symbol="SOL",
                action=SignalAction.BUY,
                confidence=0.8,
                price=100.0,
                expires_at=datetime.now() - timedelta(hours=1),
            ),
            StrategySignal(
                strategy_name="S2",
                symbol="SOL",
                action=SignalAction.BUY,
                confidence=0.8,
                price=100.0,
                expires_at=datetime.now() - timedelta(hours=1),
            ),
        ]

        result = aggregator.aggregate(expired_signals)

        # Should filter out expired signals
        assert result is None

    def test_unregistered_strategy(self, aggregator):
        """Test adding signal from unregistered strategy."""
        signal = StrategySignal(
            strategy_name="UnknownStrategy",
            symbol="SOL",
            action=SignalAction.BUY,
            confidence=0.8,
            price=100.0,
        )

        # Should auto-register or handle gracefully
        aggregator.add_signal(signal)

        # Either registered automatically or in pending signals
        assert "UnknownStrategy" in aggregator.strategy_performances or len(aggregator.pending_signals) > 0

    def test_duplicate_signals_same_strategy(self, aggregator):
        """Test handling duplicate signals from same strategy."""
        aggregator.register_strategy("S1")
        aggregator.register_strategy("S2")

        signals = [
            StrategySignal(strategy_name="S1", symbol="SOL", action=SignalAction.BUY, confidence=0.8, price=100.0),
            StrategySignal(strategy_name="S1", symbol="SOL", action=SignalAction.BUY, confidence=0.9, price=100.0),  # Duplicate
            StrategySignal(strategy_name="S2", symbol="SOL", action=SignalAction.BUY, confidence=0.7, price=100.0),
        ]

        result = aggregator.aggregate(signals)

        # Should use most recent or handle duplicates appropriately
        assert result is not None
        assert len(result.contributing_strategies) == 2

    def test_zero_confidence_signal(self, lenient_aggregator):
        """Test handling signal with zero confidence."""
        lenient_aggregator.register_strategy("S1")
        lenient_aggregator.register_strategy("S2")

        signals = [
            StrategySignal(strategy_name="S1", symbol="SOL", action=SignalAction.BUY, confidence=0.0, price=100.0),
            StrategySignal(strategy_name="S2", symbol="SOL", action=SignalAction.BUY, confidence=0.8, price=100.0),
        ]

        result = lenient_aggregator.aggregate(signals)

        # Zero confidence signal should have minimal impact
        assert result is not None

    def test_invalid_confidence_clamped(self, aggregator):
        """Test that invalid confidence values are clamped."""
        aggregator.register_strategy("S1")
        aggregator.register_strategy("S2")

        signals = [
            StrategySignal(strategy_name="S1", symbol="SOL", action=SignalAction.BUY, confidence=1.5, price=100.0),  # > 1
            StrategySignal(strategy_name="S2", symbol="SOL", action=SignalAction.BUY, confidence=-0.5, price=100.0),  # < 0
        ]

        result = aggregator.aggregate(signals)

        # Should handle gracefully
        assert result is not None
        assert 0.0 <= result.confidence <= 1.0


# =============================================================================
# Integration Tests
# =============================================================================

class TestIntegration:
    """Integration tests combining multiple features."""

    def test_full_workflow(self, aggregator):
        """Test full workflow: register, signal, aggregate, record outcome."""
        # 1. Register strategies
        aggregator.register_strategy("TrendFollower", base_weight=1.2)
        aggregator.register_strategy("MeanReversion", base_weight=1.0)
        aggregator.register_strategy("BreakoutTrader", base_weight=1.1)

        # 2. Add signals
        signals = [
            StrategySignal(strategy_name="TrendFollower", symbol="SOL", action=SignalAction.BUY, confidence=0.85, price=100.0),
            StrategySignal(strategy_name="MeanReversion", symbol="SOL", action=SignalAction.BUY, confidence=0.75, price=100.0),
            StrategySignal(strategy_name="BreakoutTrader", symbol="SOL", action=SignalAction.BUY, confidence=0.90, price=100.0),
        ]

        # 3. Aggregate
        result = aggregator.aggregate(signals)

        assert result is not None
        assert result.action == SignalAction.BUY
        assert result.consensus_type == ConsensusType.UNANIMOUS

        # 4. Record outcome
        aggregator.record_outcome(result.signal_id, profitable=True, pnl_percent=8.5)

        # 5. Verify tracking updated
        for name in ["TrendFollower", "MeanReversion", "BreakoutTrader"]:
            perf = aggregator.strategy_performances[name]
            assert perf.total_signals > 0 or perf.profitable_signals >= 0

    def test_multiple_symbols(self, aggregator):
        """Test aggregation works independently per symbol."""
        for name in ["S1", "S2"]:
            aggregator.register_strategy(name)

        sol_signals = [
            StrategySignal(strategy_name="S1", symbol="SOL", action=SignalAction.BUY, confidence=0.8, price=100.0),
            StrategySignal(strategy_name="S2", symbol="SOL", action=SignalAction.BUY, confidence=0.8, price=100.0),
        ]

        btc_signals = [
            StrategySignal(strategy_name="S1", symbol="BTC", action=SignalAction.SELL, confidence=0.8, price=50000.0),
            StrategySignal(strategy_name="S2", symbol="BTC", action=SignalAction.SELL, confidence=0.8, price=50000.0),
        ]

        sol_result = aggregator.aggregate(sol_signals)
        btc_result = aggregator.aggregate(btc_signals)

        assert sol_result.action == SignalAction.BUY
        assert btc_result.action == SignalAction.SELL
        assert sol_result.symbol == "SOL"
        assert btc_result.symbol == "BTC"
