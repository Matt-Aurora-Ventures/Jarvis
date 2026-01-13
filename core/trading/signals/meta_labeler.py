"""
Meta-Labeling / Corrective AI Module

Instead of predicting price directly, this module predicts whether
a trade SIGNAL will be profitable. This is a two-stage approach:

1. Base Model: Generates trade signals (long/short/neutral)
2. Meta-Labeler: Classifies if the signal is worth taking

Features used for classification:
- Signal strength from base model
- Recent hit rate of similar signals
- Current market regime (trending/ranging)
- Funding rate skew
- Order flow imbalance
- Liquidity conditions
- Time-based factors
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from enum import Enum
import statistics

logger = logging.getLogger(__name__)


class MarketRegime(Enum):
    """Current market regime classification."""
    TRENDING_UP = "trending_up"
    TRENDING_DOWN = "trending_down"
    RANGING = "ranging"
    HIGH_VOLATILITY = "high_volatility"
    LOW_VOLATILITY = "low_volatility"
    UNKNOWN = "unknown"


@dataclass
class SignalFeatures:
    """
    Features extracted for meta-labeling classification.
    """
    # Base signal info
    signal_direction: str  # 'long', 'short', 'neutral'
    signal_strength: float  # 0.0 to 1.0
    signal_source: str  # 'liquidation', 'ma', 'sentiment', etc.

    # Market context
    market_regime: MarketRegime = MarketRegime.UNKNOWN
    volatility_percentile: float = 50.0  # 0-100
    volume_percentile: float = 50.0  # 0-100

    # Recent performance
    recent_hit_rate: float = 0.5  # Win rate of similar signals
    recent_avg_return: float = 0.0
    signals_last_24h: int = 0

    # Market microstructure
    funding_rate: float = 0.0
    funding_skew: float = 0.0  # Positive = longs paying, Negative = shorts paying
    order_flow_imbalance: float = 0.0  # -1 to 1
    bid_ask_spread: float = 0.0

    # Liquidity
    liquidity_score: float = 1.0  # 0-1, higher is better
    large_orders_nearby: int = 0

    # Time factors
    hour_of_day: int = 12
    day_of_week: int = 0  # 0=Monday
    is_weekend: bool = False

    timestamp: datetime = field(default_factory=datetime.utcnow)

    def to_feature_vector(self) -> List[float]:
        """Convert to numerical feature vector for ML."""
        return [
            1.0 if self.signal_direction == 'long' else (-1.0 if self.signal_direction == 'short' else 0.0),
            self.signal_strength,
            self._regime_to_float(),
            self.volatility_percentile / 100.0,
            self.volume_percentile / 100.0,
            self.recent_hit_rate,
            self.recent_avg_return,
            min(self.signals_last_24h / 10.0, 1.0),  # Normalize
            self.funding_rate * 100,  # Scale up
            self.funding_skew,
            self.order_flow_imbalance,
            self.bid_ask_spread * 1000,  # Scale up
            self.liquidity_score,
            min(self.large_orders_nearby / 5.0, 1.0),  # Normalize
            self.hour_of_day / 24.0,
            self.day_of_week / 7.0,
            1.0 if self.is_weekend else 0.0,
        ]

    def _regime_to_float(self) -> float:
        """Convert regime to numerical value."""
        mapping = {
            MarketRegime.TRENDING_UP: 1.0,
            MarketRegime.TRENDING_DOWN: -1.0,
            MarketRegime.RANGING: 0.0,
            MarketRegime.HIGH_VOLATILITY: 0.5,
            MarketRegime.LOW_VOLATILITY: -0.5,
            MarketRegime.UNKNOWN: 0.0,
        }
        return mapping.get(self.market_regime, 0.0)


@dataclass
class MetaLabelResult:
    """
    Result of meta-labeling classification.
    """
    should_trade: bool
    probability: float  # Probability trade will be profitable
    confidence: float   # Confidence in the prediction
    features: SignalFeatures
    reasoning: List[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'should_trade': self.should_trade,
            'probability': self.probability,
            'confidence': self.confidence,
            'reasoning': self.reasoning,
            'timestamp': self.timestamp.isoformat(),
        }


@dataclass
class TradeOutcome:
    """Record of a trade outcome for learning."""
    signal_features: SignalFeatures
    was_profitable: bool
    return_pct: float
    hold_time_minutes: int
    timestamp: datetime = field(default_factory=datetime.utcnow)


class MetaLabeler:
    """
    Meta-labeling classifier that predicts trade signal quality.

    Uses a rule-based approach initially, can be upgraded to ML.

    Configuration:
        probability_threshold: Minimum probability to approve trade (default 0.6)
        min_confidence: Minimum confidence required (default 0.5)
        max_signals_per_day: Rate limit on signals (default 10)
    """

    def __init__(
        self,
        probability_threshold: float = 0.6,
        min_confidence: float = 0.5,
        max_signals_per_day: int = 10,
    ):
        self.probability_threshold = probability_threshold
        self.min_confidence = min_confidence
        self.max_signals_per_day = max_signals_per_day

        # Historical outcomes for learning
        self._outcomes: List[TradeOutcome] = []

        # Signals approved today
        self._daily_signals: List[datetime] = []

        # Performance tracking by signal source
        self._source_performance: Dict[str, List[bool]] = {}

        logger.info(
            f"MetaLabeler initialized: threshold={probability_threshold:.0%}, "
            f"min_confidence={min_confidence:.0%}"
        )

    def classify(self, features: SignalFeatures) -> MetaLabelResult:
        """
        Classify whether a signal should be traded.

        Args:
            features: SignalFeatures with all context information

        Returns:
            MetaLabelResult with trading recommendation
        """
        reasoning = []
        probability = 0.5  # Base probability
        confidence = 0.5

        # 1. Check signal strength
        if features.signal_strength >= 0.8:
            probability += 0.15
            reasoning.append("Strong signal strength (+15%)")
        elif features.signal_strength >= 0.6:
            probability += 0.05
            reasoning.append("Moderate signal strength (+5%)")
        elif features.signal_strength < 0.4:
            probability -= 0.1
            reasoning.append("Weak signal strength (-10%)")

        # 2. Check recent hit rate
        if features.recent_hit_rate >= 0.7:
            probability += 0.15
            confidence += 0.1
            reasoning.append(f"High recent hit rate {features.recent_hit_rate:.0%} (+15%)")
        elif features.recent_hit_rate >= 0.5:
            probability += 0.05
            reasoning.append(f"Average hit rate {features.recent_hit_rate:.0%} (+5%)")
        elif features.recent_hit_rate < 0.4:
            probability -= 0.15
            reasoning.append(f"Poor hit rate {features.recent_hit_rate:.0%} (-15%)")

        # 3. Check market regime alignment
        if features.signal_direction == 'long':
            if features.market_regime == MarketRegime.TRENDING_UP:
                probability += 0.1
                reasoning.append("Long signal aligned with uptrend (+10%)")
            elif features.market_regime == MarketRegime.TRENDING_DOWN:
                probability -= 0.15
                reasoning.append("Long signal against downtrend (-15%)")
        elif features.signal_direction == 'short':
            if features.market_regime == MarketRegime.TRENDING_DOWN:
                probability += 0.1
                reasoning.append("Short signal aligned with downtrend (+10%)")
            elif features.market_regime == MarketRegime.TRENDING_UP:
                probability -= 0.15
                reasoning.append("Short signal against uptrend (-15%)")

        # 4. Check funding rate
        if features.signal_direction == 'long' and features.funding_rate < -0.01:
            probability += 0.05
            reasoning.append("Negative funding favors longs (+5%)")
        elif features.signal_direction == 'short' and features.funding_rate > 0.01:
            probability += 0.05
            reasoning.append("Positive funding favors shorts (+5%)")

        # 5. Check order flow
        if features.signal_direction == 'long' and features.order_flow_imbalance > 0.3:
            probability += 0.05
            reasoning.append("Positive order flow (+5%)")
        elif features.signal_direction == 'short' and features.order_flow_imbalance < -0.3:
            probability += 0.05
            reasoning.append("Negative order flow (+5%)")

        # 6. Check liquidity
        if features.liquidity_score < 0.5:
            probability -= 0.1
            confidence -= 0.1
            reasoning.append("Low liquidity warning (-10%)")

        # 7. Check volatility
        if features.volatility_percentile > 90:
            probability -= 0.05
            reasoning.append("Extreme volatility caution (-5%)")
        elif features.volatility_percentile < 20:
            probability -= 0.05
            reasoning.append("Very low volatility, may lack momentum (-5%)")

        # 8. Check time factors
        if features.is_weekend:
            probability -= 0.05
            confidence -= 0.05
            reasoning.append("Weekend trading caution (-5%)")

        # 9. Check signal frequency
        self._clean_daily_signals()
        if len(self._daily_signals) >= self.max_signals_per_day:
            probability -= 0.2
            reasoning.append(f"Daily signal limit reached ({self.max_signals_per_day})")

        # 10. Check historical source performance
        source_history = self._source_performance.get(features.signal_source, [])
        if len(source_history) >= 10:
            source_win_rate = sum(source_history) / len(source_history)
            if source_win_rate >= 0.6:
                probability += 0.1
                reasoning.append(f"Source '{features.signal_source}' has good track record (+10%)")
            elif source_win_rate < 0.4:
                probability -= 0.1
                reasoning.append(f"Source '{features.signal_source}' has poor track record (-10%)")

        # Clamp probability
        probability = max(0.0, min(1.0, probability))
        confidence = max(0.0, min(1.0, confidence))

        # Make decision
        should_trade = (
            probability >= self.probability_threshold and
            confidence >= self.min_confidence and
            len(self._daily_signals) < self.max_signals_per_day
        )

        if should_trade:
            self._daily_signals.append(datetime.utcnow())

        result = MetaLabelResult(
            should_trade=should_trade,
            probability=probability,
            confidence=confidence,
            features=features,
            reasoning=reasoning,
        )

        logger.info(
            f"META-LABEL: {'APPROVE' if should_trade else 'REJECT'} "
            f"(prob={probability:.0%}, conf={confidence:.0%})"
        )

        return result

    def record_outcome(self, outcome: TradeOutcome) -> None:
        """Record the outcome of a trade for learning."""
        self._outcomes.append(outcome)

        # Update source performance
        source = outcome.signal_features.signal_source
        if source not in self._source_performance:
            self._source_performance[source] = []
        self._source_performance[source].append(outcome.was_profitable)

        # Keep history bounded
        if len(self._source_performance[source]) > 100:
            self._source_performance[source] = self._source_performance[source][-50:]

        if len(self._outcomes) > 1000:
            self._outcomes = self._outcomes[-500:]

    def _clean_daily_signals(self) -> None:
        """Remove signals older than 24 hours."""
        cutoff = datetime.utcnow() - timedelta(hours=24)
        self._daily_signals = [
            ts for ts in self._daily_signals if ts > cutoff
        ]

    def get_stats(self) -> Dict[str, Any]:
        """Get meta-labeler statistics."""
        profitable_outcomes = [o for o in self._outcomes if o.was_profitable]

        source_stats = {}
        for source, history in self._source_performance.items():
            if history:
                source_stats[source] = {
                    'trades': len(history),
                    'win_rate': sum(history) / len(history),
                }

        return {
            'total_outcomes': len(self._outcomes),
            'profitable_outcomes': len(profitable_outcomes),
            'overall_win_rate': (
                len(profitable_outcomes) / len(self._outcomes)
                if self._outcomes else 0
            ),
            'avg_return': (
                statistics.mean(o.return_pct for o in self._outcomes)
                if self._outcomes else 0
            ),
            'signals_today': len(self._daily_signals),
            'source_performance': source_stats,
        }

    def get_source_win_rate(self, source: str) -> float:
        """Get win rate for a specific signal source."""
        history = self._source_performance.get(source, [])
        if len(history) < 5:
            return 0.5  # Default to neutral
        return sum(history) / len(history)
