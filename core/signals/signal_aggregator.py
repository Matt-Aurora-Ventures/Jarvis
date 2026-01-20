"""
Trade Signal Aggregation System
================================

Aggregates signals from multiple trading strategies with:
- Multi-source signal collection
- Signal weighting based on historical accuracy
- Consensus calculation (unanimous, majority, weighted)
- Confidence scoring
- Historical accuracy tracking

Usage:
    from core.signals.signal_aggregator import SignalAggregator, StrategySignal, SignalAction

    aggregator = SignalAggregator()
    aggregator.register_strategy("TrendFollower", base_weight=1.2)
    aggregator.register_strategy("MeanReversion", base_weight=1.0)

    signals = [
        StrategySignal(strategy_name="TrendFollower", symbol="SOL", action=SignalAction.BUY, confidence=0.8, price=100.0),
        StrategySignal(strategy_name="MeanReversion", symbol="SOL", action=SignalAction.BUY, confidence=0.75, price=100.0),
    ]

    result = aggregator.aggregate(signals)
    if result:
        print(f"Aggregated: {result.action} with {result.confidence:.0%} confidence")
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# =============================================================================
# Enums
# =============================================================================

class SignalAction(str, Enum):
    """Trading signal action."""
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"


class ConsensusType(str, Enum):
    """Type of consensus reached."""
    UNANIMOUS = "unanimous"      # All strategies agree
    MAJORITY = "majority"        # >50% agree on direction
    WEIGHTED = "weighted"        # Weighted by accuracy/confidence
    SPLIT = "split"              # No clear consensus


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class StrategySignal:
    """
    A signal from a single trading strategy.

    Attributes:
        strategy_name: Name of the strategy that generated this signal
        symbol: Trading symbol (e.g., "SOL", "BTC")
        action: BUY, SELL, or HOLD
        confidence: Strategy's confidence in this signal (0.0 to 1.0)
        price: Current price when signal was generated
        timestamp: When the signal was generated
        metadata: Additional strategy-specific data
        expires_at: When this signal becomes invalid
    """
    strategy_name: str
    symbol: str
    action: SignalAction
    confidence: float
    price: float
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)
    expires_at: Optional[datetime] = None

    def __post_init__(self):
        # Clamp confidence to valid range
        self.confidence = max(0.0, min(1.0, self.confidence))

        # Set default expiration if not provided (1 hour)
        if self.expires_at is None:
            self.expires_at = self.timestamp + timedelta(hours=1)

    def to_numeric(self) -> float:
        """
        Convert signal action to numeric value.

        Returns:
            1.0 for BUY, -1.0 for SELL, 0.0 for HOLD
        """
        if self.action == SignalAction.BUY:
            return 1.0
        elif self.action == SignalAction.SELL:
            return -1.0
        return 0.0

    def is_expired(self) -> bool:
        """Check if this signal has expired."""
        if self.expires_at is None:
            return False
        return datetime.now() > self.expires_at

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "strategy_name": self.strategy_name,
            "symbol": self.symbol,
            "action": self.action.value,
            "confidence": self.confidence,
            "price": self.price,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
        }


@dataclass
class StrategyPerformance:
    """
    Tracks historical performance of a trading strategy.

    Used to adjust signal weights based on past accuracy.
    """
    strategy_name: str
    base_weight: float = 1.0
    current_weight: float = 1.0

    # Performance metrics
    total_signals: int = 0
    profitable_signals: int = 0
    total_pnl_percent: float = 0.0

    # Rolling window tracking
    last_n_outcomes: List[bool] = field(default_factory=list)
    rolling_window: int = 50  # Track last N outcomes for weight adjustment

    # Timestamps
    created_at: datetime = field(default_factory=datetime.now)
    last_updated: datetime = field(default_factory=datetime.now)

    @property
    def accuracy(self) -> float:
        """Calculate accuracy as profitable / total signals."""
        if self.total_signals == 0:
            return 0.0
        return self.profitable_signals / self.total_signals

    def record_outcome(self, profitable: bool, pnl_percent: float = 0.0) -> None:
        """
        Record the outcome of a signal from this strategy.

        Args:
            profitable: Whether the signal resulted in profit
            pnl_percent: Percentage profit/loss from this signal
        """
        self.total_signals += 1
        if profitable:
            self.profitable_signals += 1
        self.total_pnl_percent += pnl_percent

        # Update rolling window
        self.last_n_outcomes.append(profitable)
        if len(self.last_n_outcomes) > self.rolling_window:
            self.last_n_outcomes.pop(0)

        # Recalculate weight based on recent accuracy
        self._update_weight()
        self.last_updated = datetime.now()

    def _update_weight(self) -> None:
        """Update current weight based on historical accuracy."""
        if len(self.last_n_outcomes) == 0:
            self.current_weight = self.base_weight
            return

        # Calculate recent accuracy
        recent_accuracy = sum(self.last_n_outcomes) / len(self.last_n_outcomes)

        # Weight multiplier: 0.5x at 0% accuracy, 1.5x at 100% accuracy
        # Formula: multiplier = 0.5 + accuracy
        multiplier = 0.5 + recent_accuracy

        self.current_weight = self.base_weight * multiplier

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "strategy_name": self.strategy_name,
            "base_weight": self.base_weight,
            "current_weight": self.current_weight,
            "total_signals": self.total_signals,
            "profitable_signals": self.profitable_signals,
            "accuracy": self.accuracy,
            "total_pnl_percent": self.total_pnl_percent,
            "recent_window_size": len(self.last_n_outcomes),
            "created_at": self.created_at.isoformat(),
            "last_updated": self.last_updated.isoformat(),
        }


@dataclass
class AggregatedSignal:
    """
    An aggregated signal combining multiple strategy signals.

    Includes consensus information and contributing strategy details.
    """
    signal_id: str
    symbol: str
    action: SignalAction
    confidence: float
    price: float
    consensus_type: ConsensusType
    contributing_strategies: List[str]

    # Weight contributions
    strategy_weights: Dict[str, float] = field(default_factory=dict)
    strategy_contributions: Dict[str, float] = field(default_factory=dict)

    # Metadata
    timestamp: datetime = field(default_factory=datetime.now)
    valid_until: datetime = field(default_factory=lambda: datetime.now() + timedelta(hours=2))

    # Tracking
    outcome: Optional[str] = None  # "profitable", "loss", "neutral"
    pnl_percent: Optional[float] = None

    def __post_init__(self):
        # Generate signal ID if not provided
        if not self.signal_id:
            data = f"{self.symbol}{self.timestamp.isoformat()}{self.action.value}"
            self.signal_id = f"AGG-{hashlib.sha256(data.encode()).hexdigest()[:12].upper()}"

    def is_valid(self) -> bool:
        """Check if this aggregated signal is still valid."""
        return datetime.now() < self.valid_until

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "signal_id": self.signal_id,
            "symbol": self.symbol,
            "action": self.action.value,
            "confidence": self.confidence,
            "price": self.price,
            "consensus_type": self.consensus_type.value,
            "contributing_strategies": self.contributing_strategies,
            "strategy_weights": self.strategy_weights,
            "strategy_contributions": self.strategy_contributions,
            "timestamp": self.timestamp.isoformat(),
            "valid_until": self.valid_until.isoformat(),
            "outcome": self.outcome,
            "pnl_percent": self.pnl_percent,
        }


# =============================================================================
# Signal Aggregator
# =============================================================================

class SignalAggregator:
    """
    Aggregates signals from multiple trading strategies.

    Features:
    - Multi-source signal collection
    - Signal weighting based on historical accuracy
    - Consensus calculation (unanimous, majority, weighted)
    - Confidence scoring
    - Historical accuracy tracking

    Args:
        storage_path: Path to store performance data (":memory:" for in-memory)
        min_strategies: Minimum number of strategies required to aggregate
        min_confidence: Minimum confidence threshold for output signals
    """

    def __init__(
        self,
        storage_path: str = "data/signals/aggregator.json",
        min_strategies: int = 2,
        min_confidence: float = 0.5,
    ):
        self.storage_path = storage_path
        self.min_strategies = min_strategies
        self.min_confidence = min_confidence

        # Strategy performance tracking
        self.strategy_performances: Dict[str, StrategyPerformance] = {}

        # Pending signals by symbol
        self.pending_signals: Dict[str, Dict[str, StrategySignal]] = defaultdict(dict)

        # Generated aggregated signals
        self.aggregated_signals: Dict[str, AggregatedSignal] = {}

        # Statistics
        self.total_aggregations: int = 0
        self.profitable_aggregations: int = 0

        # Load persisted data
        if storage_path != ":memory:":
            self._load()

    def register_strategy(
        self,
        strategy_name: str,
        base_weight: float = 1.0,
    ) -> None:
        """
        Register a trading strategy for signal aggregation.

        Args:
            strategy_name: Unique name for the strategy
            base_weight: Base weight for this strategy (default 1.0)
        """
        if strategy_name not in self.strategy_performances:
            self.strategy_performances[strategy_name] = StrategyPerformance(
                strategy_name=strategy_name,
                base_weight=base_weight,
                current_weight=base_weight,
            )
            logger.info(f"Registered strategy: {strategy_name} (weight={base_weight})")

    def add_signal(self, signal: StrategySignal) -> None:
        """
        Add a signal to pending signals for aggregation.

        Auto-registers the strategy if not already registered.

        Args:
            signal: The strategy signal to add
        """
        if signal.is_expired():
            logger.debug(f"Ignoring expired signal from {signal.strategy_name}")
            return

        # Auto-register unknown strategies
        if signal.strategy_name not in self.strategy_performances:
            self.register_strategy(signal.strategy_name)

        # Store signal (replacing any existing from same strategy)
        self.pending_signals[signal.symbol][signal.strategy_name] = signal
        logger.debug(f"Added {signal.strategy_name} signal for {signal.symbol}: {signal.action.value}")

    def get_pending_signals(self, symbol: str) -> List[StrategySignal]:
        """Get all pending (non-expired) signals for a symbol."""
        pending = self.pending_signals.get(symbol, {})
        return [s for s in pending.values() if not s.is_expired()]

    def aggregate(self, signals: List[StrategySignal]) -> Optional[AggregatedSignal]:
        """
        Aggregate multiple strategy signals into one.

        Args:
            signals: List of strategy signals to aggregate

        Returns:
            AggregatedSignal if enough valid signals, None otherwise
        """
        if not signals:
            return None

        # Filter out expired signals
        valid_signals = [s for s in signals if not s.is_expired()]

        if len(valid_signals) < self.min_strategies:
            logger.debug(f"Not enough valid signals: {len(valid_signals)} < {self.min_strategies}")
            return None

        # Deduplicate by strategy (keep most recent)
        signals_by_strategy: Dict[str, StrategySignal] = {}
        for signal in valid_signals:
            existing = signals_by_strategy.get(signal.strategy_name)
            if existing is None or signal.timestamp > existing.timestamp:
                signals_by_strategy[signal.strategy_name] = signal

        valid_signals = list(signals_by_strategy.values())

        if len(valid_signals) < self.min_strategies:
            return None

        # Get symbol from first signal (all should be same)
        symbol = valid_signals[0].symbol

        # Ensure all strategies are registered
        for signal in valid_signals:
            if signal.strategy_name not in self.strategy_performances:
                self.register_strategy(signal.strategy_name)

        # Calculate weighted aggregate
        aggregated = self._calculate_weighted_aggregate(valid_signals)

        if aggregated and aggregated.confidence >= self.min_confidence:
            self.aggregated_signals[aggregated.signal_id] = aggregated
            self.total_aggregations += 1
            logger.info(
                f"Generated aggregated signal {aggregated.signal_id} for {symbol}: "
                f"{aggregated.action.value} ({aggregated.confidence:.0%} confidence, "
                f"{aggregated.consensus_type.value})"
            )
            return aggregated

        return None

    def _calculate_weighted_aggregate(
        self,
        signals: List[StrategySignal],
    ) -> AggregatedSignal:
        """
        Calculate the weighted aggregate of signals.

        Uses strategy historical accuracy to weight contributions.
        """
        symbol = signals[0].symbol

        # Collect weights and contributions
        weights: Dict[str, float] = {}
        contributions: Dict[str, float] = {}

        weighted_sum = 0.0
        total_weight = 0.0
        confidences = []

        for signal in signals:
            perf = self.strategy_performances.get(signal.strategy_name)
            weight = perf.current_weight if perf else 1.0

            numeric_value = signal.to_numeric()
            contribution = numeric_value * weight * signal.confidence

            weights[signal.strategy_name] = weight
            contributions[signal.strategy_name] = contribution

            weighted_sum += contribution
            total_weight += weight * signal.confidence
            confidences.append(signal.confidence)

        # Calculate final numeric value
        if total_weight > 0:
            final_value = weighted_sum / total_weight
        else:
            final_value = 0.0

        # Determine action
        if final_value > 0.1:
            action = SignalAction.BUY
        elif final_value < -0.1:
            action = SignalAction.SELL
        else:
            action = SignalAction.HOLD

        # Calculate consensus type
        consensus_type = self._calculate_consensus(signals)

        # Calculate confidence
        avg_confidence = sum(confidences) / len(confidences)
        agreement_factor = self._calculate_agreement_factor(signals)

        # Final confidence = average * agreement factor
        final_confidence = avg_confidence * agreement_factor

        # Boost confidence for unanimous consensus
        if consensus_type == ConsensusType.UNANIMOUS:
            final_confidence = min(1.0, final_confidence * 1.1)

        # Reduce confidence for split consensus
        if consensus_type == ConsensusType.SPLIT:
            final_confidence *= 0.7

        # Get average price
        avg_price = sum(s.price for s in signals) / len(signals)

        return AggregatedSignal(
            signal_id="",  # Will be auto-generated
            symbol=symbol,
            action=action,
            confidence=min(1.0, max(0.0, final_confidence)),
            price=avg_price,
            consensus_type=consensus_type,
            contributing_strategies=[s.strategy_name for s in signals],
            strategy_weights=weights,
            strategy_contributions=contributions,
        )

    def _calculate_consensus(self, signals: List[StrategySignal]) -> ConsensusType:
        """Determine the type of consensus among signals."""
        actions = [s.action for s in signals]
        unique_actions = set(actions)

        if len(unique_actions) == 1:
            return ConsensusType.UNANIMOUS

        # Count each action
        action_counts = {}
        for action in actions:
            action_counts[action] = action_counts.get(action, 0) + 1

        # Find majority
        max_count = max(action_counts.values())
        total = len(actions)

        if max_count > total / 2:
            return ConsensusType.MAJORITY

        if max_count == total / 2 and len(unique_actions) == 2:
            return ConsensusType.SPLIT

        return ConsensusType.WEIGHTED

    def _calculate_agreement_factor(self, signals: List[StrategySignal]) -> float:
        """
        Calculate how much the signals agree.

        Returns:
            1.0 for unanimous, lower for disagreement
        """
        if len(signals) <= 1:
            return 1.0

        actions = [s.action for s in signals]
        unique_actions = set(actions)

        if len(unique_actions) == 1:
            return 1.0  # Unanimous
        elif len(unique_actions) == 2:
            return 0.7  # Two different opinions
        else:
            return 0.5  # Three-way split

    def record_outcome(
        self,
        signal_id: str,
        profitable: bool,
        pnl_percent: float = 0.0,
    ) -> None:
        """
        Record the outcome of an aggregated signal.

        Updates historical accuracy for all contributing strategies.

        Args:
            signal_id: ID of the aggregated signal
            profitable: Whether the signal resulted in profit
            pnl_percent: Percentage profit/loss
        """
        signal = self.aggregated_signals.get(signal_id)
        if not signal:
            logger.warning(f"Signal {signal_id} not found for outcome recording")
            return

        # Update signal outcome
        signal.outcome = "profitable" if profitable else "loss"
        signal.pnl_percent = pnl_percent

        # Update statistics
        if profitable:
            self.profitable_aggregations += 1

        # Update contributing strategies
        for strategy_name in signal.contributing_strategies:
            perf = self.strategy_performances.get(strategy_name)
            if perf:
                # Determine if this strategy's contribution was correct
                contribution = signal.strategy_contributions.get(strategy_name, 0)
                strategy_was_right = (contribution > 0) == profitable

                perf.record_outcome(strategy_was_right, pnl_percent)
                logger.debug(
                    f"Updated {strategy_name}: accuracy={perf.accuracy:.1%}, "
                    f"weight={perf.current_weight:.2f}"
                )

        # Persist changes
        self._save()

    def get_strategy_rankings(self) -> List[Tuple[str, float]]:
        """
        Get strategies ranked by accuracy.

        Returns:
            List of (strategy_name, accuracy) sorted by accuracy descending
        """
        rankings = [
            (name, perf.accuracy)
            for name, perf in self.strategy_performances.items()
        ]
        return sorted(rankings, key=lambda x: x[1], reverse=True)

    def get_aggregation_stats(self) -> Dict[str, Any]:
        """Get overall aggregation statistics."""
        accuracy = 0.0
        if self.total_aggregations > 0:
            accuracy = self.profitable_aggregations / self.total_aggregations

        return {
            "total_signals_generated": self.total_aggregations,
            "profitable_signals": self.profitable_aggregations,
            "overall_accuracy": accuracy,
            "strategy_count": len(self.strategy_performances),
            "active_signals": sum(1 for s in self.aggregated_signals.values() if s.is_valid()),
            "strategies": {
                name: perf.to_dict()
                for name, perf in self.strategy_performances.items()
            },
        }

    def _load(self) -> None:
        """Load persisted data from storage."""
        if self.storage_path == ":memory:":
            return

        path = Path(self.storage_path)
        if not path.exists():
            return

        try:
            with open(path) as f:
                data = json.load(f)

            # Load strategy performances
            for perf_data in data.get("performances", []):
                name = perf_data["strategy_name"]
                perf = StrategyPerformance(
                    strategy_name=name,
                    base_weight=perf_data.get("base_weight", 1.0),
                    current_weight=perf_data.get("current_weight", 1.0),
                    total_signals=perf_data.get("total_signals", 0),
                    profitable_signals=perf_data.get("profitable_signals", 0),
                    total_pnl_percent=perf_data.get("total_pnl_percent", 0.0),
                )
                self.strategy_performances[name] = perf

            # Load statistics
            self.total_aggregations = data.get("total_aggregations", 0)
            self.profitable_aggregations = data.get("profitable_aggregations", 0)

            logger.info(f"Loaded aggregator state: {len(self.strategy_performances)} strategies")

        except Exception as e:
            logger.error(f"Failed to load aggregator state: {e}")

    def _save(self) -> None:
        """Persist data to storage."""
        if self.storage_path == ":memory:":
            return

        try:
            path = Path(self.storage_path)
            path.parent.mkdir(parents=True, exist_ok=True)

            data = {
                "performances": [p.to_dict() for p in self.strategy_performances.values()],
                "total_aggregations": self.total_aggregations,
                "profitable_aggregations": self.profitable_aggregations,
                "updated_at": datetime.now().isoformat(),
            }

            with open(path, "w") as f:
                json.dump(data, f, indent=2)

        except Exception as e:
            logger.error(f"Failed to save aggregator state: {e}")


# =============================================================================
# Module-Level Functions
# =============================================================================

# Singleton instance
_signal_aggregator: Optional[SignalAggregator] = None


def get_signal_aggregator() -> SignalAggregator:
    """Get the singleton SignalAggregator instance."""
    global _signal_aggregator

    if _signal_aggregator is None:
        _signal_aggregator = SignalAggregator()

    return _signal_aggregator


def aggregate_signals(
    signals: List[StrategySignal],
    min_strategies: int = 2,
    min_confidence: float = 0.5,
) -> Optional[AggregatedSignal]:
    """
    Convenience function to aggregate signals.

    Args:
        signals: List of strategy signals to aggregate
        min_strategies: Minimum strategies required
        min_confidence: Minimum confidence threshold

    Returns:
        AggregatedSignal if successful, None otherwise
    """
    aggregator = SignalAggregator(
        storage_path=":memory:",
        min_strategies=min_strategies,
        min_confidence=min_confidence,
    )

    # Register all strategies
    for signal in signals:
        if signal.strategy_name not in aggregator.strategy_performances:
            aggregator.register_strategy(signal.strategy_name)

    return aggregator.aggregate(signals)


# =============================================================================
# Testing
# =============================================================================

if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO)

    print("=== Signal Aggregator Demo ===\n")

    # Create aggregator
    aggregator = SignalAggregator(storage_path=":memory:")

    # Register strategies
    aggregator.register_strategy("TrendFollower", base_weight=1.2)
    aggregator.register_strategy("MeanReversion", base_weight=1.0)
    aggregator.register_strategy("BreakoutTrader", base_weight=1.1)

    # Create signals
    signals = [
        StrategySignal(
            strategy_name="TrendFollower",
            symbol="SOL",
            action=SignalAction.BUY,
            confidence=0.85,
            price=100.0,
            metadata={"sma_short": 105, "sma_long": 98},
        ),
        StrategySignal(
            strategy_name="MeanReversion",
            symbol="SOL",
            action=SignalAction.BUY,
            confidence=0.75,
            price=100.0,
            metadata={"rsi": 35},
        ),
        StrategySignal(
            strategy_name="BreakoutTrader",
            symbol="SOL",
            action=SignalAction.BUY,
            confidence=0.90,
            price=100.0,
            metadata={"resistance": 105},
        ),
    ]

    # Aggregate
    result = aggregator.aggregate(signals)

    if result:
        print(f"Signal ID: {result.signal_id}")
        print(f"Action: {result.action.value}")
        print(f"Confidence: {result.confidence:.1%}")
        print(f"Consensus: {result.consensus_type.value}")
        print(f"Strategies: {', '.join(result.contributing_strategies)}")
        print("\nStrategy Weights:")
        for name, weight in result.strategy_weights.items():
            print(f"  {name}: {weight:.2f}")

        # Record outcome
        print("\n--- Recording profitable outcome ---")
        aggregator.record_outcome(result.signal_id, profitable=True, pnl_percent=8.5)

        # Show updated stats
        print("\nStrategy Rankings:")
        for name, accuracy in aggregator.get_strategy_rankings():
            perf = aggregator.strategy_performances[name]
            print(f"  {name}: accuracy={accuracy:.1%}, weight={perf.current_weight:.2f}")

    print("\n=== Demo Complete ===")
