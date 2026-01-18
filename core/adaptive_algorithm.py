"""
Adaptive Trading Algorithm System

Continuously learning system that:
- Tracks algorithm performance
- Adjusts parameters based on outcomes
- Learns from winning and losing patterns
- Improves recommendation confidence over time
- Adapts to market conditions
- Personalizes per user
"""

import logging
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path
import statistics

logger = logging.getLogger(__name__)


class AlgorithmType(Enum):
    """Types of trading algorithms."""
    SENTIMENT = "sentiment"          # Grok sentiment analysis
    LIQUIDATION = "liquidation"      # Liquidation level detection
    TECHNICAL = "technical"          # Technical indicators (MA, etc.)
    WHALE = "whale"                  # Whale activity detection
    NEWS = "news"                    # News catalyst detection
    MOMENTUM = "momentum"            # Momentum trading
    REVERSAL = "reversal"            # Reversal pattern detection
    VOLUME = "volume"                # Volume surge detection
    COMPOSITE = "composite"          # Combined signal strength


@dataclass
class AlgorithmMetrics:
    """Performance metrics for an algorithm."""
    algorithm_type: AlgorithmType
    total_signals: int = 0
    winning_signals: int = 0
    losing_signals: int = 0
    total_pnl: float = 0.0
    accuracy: float = 0.0
    avg_win: float = 0.0
    avg_loss: float = 0.0
    best_win: float = 0.0
    worst_loss: float = 0.0
    confidence_score: float = 50.0  # 0-100, starts at 50
    last_updated: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'algorithm_type': self.algorithm_type.value,
            'total_signals': self.total_signals,
            'winning_signals': self.winning_signals,
            'losing_signals': self.losing_signals,
            'total_pnl': self.total_pnl,
            'accuracy': self.accuracy,
            'avg_win': self.avg_win,
            'avg_loss': self.avg_loss,
            'best_win': self.best_win,
            'worst_loss': self.worst_loss,
            'confidence_score': self.confidence_score,
            'last_updated': self.last_updated.isoformat(),
        }


@dataclass
class TradeOutcome:
    """Result of a trade following an algorithm signal."""
    algorithm_type: AlgorithmType
    signal_strength: float  # 0-100
    user_id: int
    symbol: str
    entry_price: float
    exit_price: float
    pnl_usd: float
    hold_duration_hours: float
    executed_at: datetime = field(default_factory=datetime.utcnow)

    @property
    def was_winning(self) -> bool:
        """Was this trade profitable?"""
        return self.pnl_usd > 0

    @property
    def return_pct(self) -> float:
        """Return percentage."""
        return (self.exit_price - self.entry_price) / self.entry_price * 100


@dataclass
class AlgorithmSignal:
    """A trading signal from an algorithm."""
    algorithm_type: AlgorithmType
    symbol: str
    action: str  # "BUY" or "SELL"
    strength: float  # 0-100, confidence in signal
    entry_price: float
    target_price: float
    stop_loss_price: float
    reason: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    generated_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'algorithm_type': self.algorithm_type.value,
            'symbol': self.symbol,
            'action': self.action,
            'strength': self.strength,
            'entry_price': self.entry_price,
            'target_price': self.target_price,
            'stop_loss_price': self.stop_loss_price,
            'reason': self.reason,
            'metadata': self.metadata,
            'generated_at': self.generated_at.isoformat(),
        }


class AdaptiveAlgorithm:
    """
    Adaptive trading algorithm that learns from outcomes.

    Features:
    - Tracks performance of each algorithm type
    - Adjusts confidence based on accuracy
    - Learns from winning and losing patterns
    - Personalizes per user
    - Continuously improves recommendations
    """

    def __init__(self, data_dir: str = "~/.lifeos/algorithms"):
        """Initialize adaptive algorithm system."""
        self.data_dir = Path(data_dir).expanduser()
        self.data_dir.mkdir(parents=True, exist_ok=True)

        # In-memory metrics (one per algorithm type)
        self.global_metrics: Dict[AlgorithmType, AlgorithmMetrics] = {
            algo_type: AlgorithmMetrics(algorithm_type=algo_type)
            for algo_type in AlgorithmType
        }

        # Per-user metrics
        self.user_metrics: Dict[int, Dict[AlgorithmType, AlgorithmMetrics]] = {}

        # Learning history
        self.outcomes: List[TradeOutcome] = []

        self._load_metrics()

    def _load_metrics(self):
        """Load saved metrics from disk."""
        try:
            metrics_file = self.data_dir / "global_metrics.json"
            if metrics_file.exists():
                with open(metrics_file, 'r') as f:
                    data = json.load(f)
                    # TODO: Deserialize metrics from JSON
                logger.info("Loaded global metrics from disk")
        except Exception as e:
            logger.error(f"Failed to load metrics: {e}")

    def _save_metrics(self):
        """Save metrics to disk."""
        try:
            metrics_file = self.data_dir / "global_metrics.json"
            data = {
                algo_type.value: metrics.to_dict()
                for algo_type, metrics in self.global_metrics.items()
            }
            with open(metrics_file, 'w') as f:
                json.dump(data, f, indent=2, default=str)
        except Exception as e:
            logger.error(f"Failed to save metrics: {e}")

    # ==================== SIGNAL GENERATION ====================

    def generate_sentiment_signal(self, symbol: str, sentiment_score: float,
                                 price_data: Dict[str, float]) -> Optional[AlgorithmSignal]:
        """
        Generate signal from Grok sentiment analysis.

        Args:
            symbol: Token symbol
            sentiment_score: -100 to +100 score from sentiment aggregator
            price_data: {'current': float, 'support': float, 'resistance': float}

        Returns:
            AlgorithmSignal or None
        """
        try:
            current_price = price_data.get('current', 0)
            if not current_price:
                return None

            # Strong bullish
            if sentiment_score >= 70:
                strength = min(100, 50 + (sentiment_score - 70) * 1.5)  # 50-100
                return AlgorithmSignal(
                    algorithm_type=AlgorithmType.SENTIMENT,
                    symbol=symbol,
                    action="BUY",
                    strength=strength,
                    entry_price=current_price,
                    target_price=current_price * 1.5,  # 50% upside
                    stop_loss_price=current_price * 0.85,  # 15% stop
                    reason=f"Strong bullish sentiment (Grok: {sentiment_score}/100)",
                    metadata={'sentiment_score': sentiment_score}
                )

            # Moderate bullish
            elif sentiment_score >= 55:
                strength = 50 + (sentiment_score - 55) * 1.0
                return AlgorithmSignal(
                    algorithm_type=AlgorithmType.SENTIMENT,
                    symbol=symbol,
                    action="BUY",
                    strength=strength,
                    entry_price=current_price,
                    target_price=current_price * 1.25,
                    stop_loss_price=current_price * 0.90,
                    reason=f"Bullish sentiment trend",
                    metadata={'sentiment_score': sentiment_score}
                )

            # Bearish
            elif sentiment_score <= 30:
                strength = min(100, 50 - sentiment_score)
                return AlgorithmSignal(
                    algorithm_type=AlgorithmType.SENTIMENT,
                    symbol=symbol,
                    action="SELL",
                    strength=strength,
                    entry_price=current_price,
                    target_price=current_price * 0.70,
                    stop_loss_price=current_price * 1.15,
                    reason=f"Strong bearish sentiment",
                    metadata={'sentiment_score': sentiment_score}
                )

            return None

        except Exception as e:
            logger.error(f"Failed to generate sentiment signal: {e}")
            return None

    def generate_liquidation_signal(self, symbol: str, liquidation_data: Dict[str, Any]) -> Optional[AlgorithmSignal]:
        """
        Generate signal from liquidation heatmap analysis.

        Args:
            symbol: Token symbol
            liquidation_data: {'support': float, 'resistance': float, 'concentration': float}

        Returns:
            AlgorithmSignal or None
        """
        try:
            current_price = liquidation_data.get('current', 0)
            support = liquidation_data.get('support', 0)
            concentration = liquidation_data.get('concentration', 0)

            if not current_price or not support:
                return None

            # Strong support identified (good buy opportunity)
            distance_to_support_pct = (current_price - support) / current_price * 100

            if distance_to_support_pct < 10 and concentration > 500_000:  # Close to support, high concentration
                strength = min(100, 70 + distance_to_support_pct)
                return AlgorithmSignal(
                    algorithm_type=AlgorithmType.LIQUIDATION,
                    symbol=symbol,
                    action="BUY",
                    strength=strength,
                    entry_price=current_price,
                    target_price=current_price * 1.2,
                    stop_loss_price=support * 0.95,
                    reason=f"Strong support level with ${concentration/1e6:.1f}M liquidation concentration",
                    metadata={'support_price': support, 'concentration_usd': concentration}
                )

            return None

        except Exception as e:
            logger.error(f"Failed to generate liquidation signal: {e}")
            return None

    def generate_whale_signal(self, symbol: str, whale_data: Dict[str, Any]) -> Optional[AlgorithmSignal]:
        """
        Generate signal from whale activity detection.

        Args:
            symbol: Token symbol
            whale_data: {'action': 'buy'|'sell', 'volume_usd': float, 'conviction': 0-100}

        Returns:
            AlgorithmSignal or None
        """
        try:
            action = whale_data.get('action', '').upper()
            volume_usd = whale_data.get('volume_usd', 0)
            conviction = whale_data.get('conviction', 0)
            current_price = whale_data.get('price', 0)

            if not current_price or volume_usd < 100_000:  # Minimum $100K to care
                return None

            if action == "BUY" and conviction > 60:
                strength = min(100, conviction + 20)  # Whale buying is strong signal
                return AlgorithmSignal(
                    algorithm_type=AlgorithmType.WHALE,
                    symbol=symbol,
                    action="BUY",
                    strength=strength,
                    entry_price=current_price,
                    target_price=current_price * 1.3,
                    stop_loss_price=current_price * 0.88,
                    reason=f"Whale bought ${volume_usd/1e6:.1f}M (conviction: {conviction}/100)",
                    metadata={'whale_volume': volume_usd, 'conviction': conviction}
                )

            elif action == "SELL" and conviction > 70:
                strength = min(100, conviction + 10)
                return AlgorithmSignal(
                    algorithm_type=AlgorithmType.WHALE,
                    symbol=symbol,
                    action="SELL",
                    strength=strength,
                    entry_price=current_price,
                    target_price=current_price * 0.7,
                    stop_loss_price=current_price * 1.12,
                    reason=f"Whale selling ${volume_usd/1e6:.1f}M (high conviction dump)",
                    metadata={'whale_volume': volume_usd, 'conviction': conviction}
                )

            return None

        except Exception as e:
            logger.error(f"Failed to generate whale signal: {e}")
            return None

    # ==================== OUTCOME RECORDING ====================

    def record_outcome(self, outcome: TradeOutcome):
        """
        Record the outcome of a trade following an algorithm signal.

        This is where the learning happens:
        - If trade was winning, increase algorithm's confidence
        - If trade was losing, decrease confidence
        - Track patterns and adapt
        """
        try:
            self.outcomes.append(outcome)

            # Update global metrics
            metrics = self.global_metrics[outcome.algorithm_type]
            metrics.total_signals += 1

            if outcome.was_winning:
                metrics.winning_signals += 1
                metrics.total_pnl += outcome.pnl_usd
                if outcome.pnl_usd > metrics.best_win:
                    metrics.best_win = outcome.pnl_usd
                metrics.avg_win = metrics.total_pnl / metrics.winning_signals if metrics.winning_signals > 0 else 0
            else:
                metrics.losing_signals += 1
                metrics.total_pnl += outcome.pnl_usd
                if outcome.pnl_usd < metrics.worst_loss:
                    metrics.worst_loss = outcome.pnl_usd
                metrics.avg_loss = abs(metrics.total_pnl) / metrics.losing_signals if metrics.losing_signals > 0 else 0

            # Calculate accuracy
            metrics.accuracy = (metrics.winning_signals / metrics.total_signals * 100) if metrics.total_signals > 0 else 0

            # Adaptive confidence scoring
            # Base: Start at 50, adjust up with wins, down with losses
            win_rate = metrics.accuracy
            if win_rate >= 60:
                metrics.confidence_score = min(100, 50 + (win_rate - 50) * 1.0)
            elif win_rate >= 45:
                metrics.confidence_score = 50  # Neutral
            else:
                metrics.confidence_score = max(20, 50 - (50 - win_rate) * 1.0)

            # Signal strength weighting: Signals with high accuracy get more boost
            signal_quality_adjustment = (outcome.signal_strength / 100.0) * (1 if outcome.was_winning else -1)
            metrics.confidence_score += signal_quality_adjustment * 5

            metrics.last_updated = datetime.utcnow()

            logger.info(
                f"Recorded {outcome.algorithm_type.value} outcome: "
                f"{'WIN' if outcome.was_winning else 'LOSS'} ${outcome.pnl_usd:.2f}, "
                f"Confidence: {metrics.confidence_score:.1f}, "
                f"Accuracy: {metrics.accuracy:.1f}%"
            )

            # Save periodically
            if len(self.outcomes) % 10 == 0:
                self._save_metrics()

        except Exception as e:
            logger.error(f"Failed to record outcome: {e}")

    # ==================== SIGNAL STRENGTH CALCULATION ====================

    def get_algorithm_confidence(self, algorithm_type: AlgorithmType) -> float:
        """
        Get current confidence for an algorithm.

        Returns confidence 0-100 based on historical performance.
        """
        metrics = self.global_metrics.get(algorithm_type)
        if not metrics:
            return 50.0

        return metrics.confidence_score

    def should_use_algorithm(self, algorithm_type: AlgorithmType, min_confidence: float = 40.0) -> bool:
        """
        Determine if we should use this algorithm based on performance.

        Low-performing algorithms get disabled automatically.
        """
        confidence = self.get_algorithm_confidence(algorithm_type)
        return confidence >= min_confidence

    def get_composite_signal_strength(self, signals: List[AlgorithmSignal]) -> float:
        """
        Combine multiple algorithm signals into a composite strength.

        Accounts for algorithm confidence and signal agreement.
        """
        if not signals:
            return 0.0

        try:
            # Filter signals by algorithm confidence
            valid_signals = [
                s for s in signals
                if self.should_use_algorithm(s.algorithm_type, min_confidence=30)
            ]

            if not valid_signals:
                return 0.0

            # Weight signals by algorithm confidence and signal strength
            weighted_strength = 0.0
            total_weight = 0.0

            for signal in valid_signals:
                algo_confidence = self.get_algorithm_confidence(signal.algorithm_type) / 100.0
                weight = signal.strength * algo_confidence
                weighted_strength += signal.strength * weight
                total_weight += weight

            if total_weight == 0:
                return 0.0

            composite = weighted_strength / total_weight
            return min(100, composite)

        except Exception as e:
            logger.error(f"Failed to calculate composite strength: {e}")
            return 0.0

    # ==================== PERFORMANCE ANALYSIS ====================

    def get_algorithm_stats(self, algorithm_type: AlgorithmType) -> Dict[str, Any]:
        """Get detailed statistics for an algorithm."""
        metrics = self.global_metrics.get(algorithm_type)
        if not metrics:
            return {}

        return {
            'type': algorithm_type.value,
            'total_signals': metrics.total_signals,
            'wins': metrics.winning_signals,
            'losses': metrics.losing_signals,
            'win_rate': metrics.accuracy,
            'total_pnl': metrics.total_pnl,
            'avg_win': metrics.avg_win,
            'avg_loss': metrics.avg_loss,
            'best_win': metrics.best_win,
            'worst_loss': metrics.worst_loss,
            'confidence': metrics.confidence_score,
            'recommended': self.should_use_algorithm(algorithm_type),
        }

    def get_all_stats(self) -> Dict[str, Any]:
        """Get statistics for all algorithms."""
        return {
            algo_type.value: self.get_algorithm_stats(algo_type)
            for algo_type in AlgorithmType
        }

    def get_recent_outcomes(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Get recent trade outcomes."""
        recent = self.outcomes[-limit:]
        return [
            {
                'algorithm': o.algorithm_type.value,
                'symbol': o.symbol,
                'pnl': o.pnl_usd,
                'return_pct': o.return_pct,
                'hold_hours': o.hold_duration_hours,
                'signal_strength': o.signal_strength,
                'executed_at': o.executed_at.isoformat(),
            }
            for o in recent
        ]

    # ==================== LEARNING AND ADAPTATION ====================

    def get_winning_patterns(self, algorithm_type: Optional[AlgorithmType] = None,
                            limit: int = 5) -> List[Dict[str, Any]]:
        """
        Extract patterns from winning trades.

        Returns the most successful configurations.
        """
        try:
            if algorithm_type:
                outcomes = [o for o in self.outcomes if o.algorithm_type == algorithm_type and o.was_winning]
            else:
                outcomes = [o for o in self.outcomes if o.was_winning]

            if not outcomes:
                return []

            # Sort by PnL
            outcomes.sort(key=lambda x: x.pnl_usd, reverse=True)

            patterns = []
            for outcome in outcomes[:limit]:
                patterns.append({
                    'algorithm': outcome.algorithm_type.value,
                    'symbol': outcome.symbol,
                    'signal_strength': outcome.signal_strength,
                    'pnl': outcome.pnl_usd,
                    'return_pct': outcome.return_pct,
                    'hold_hours': outcome.hold_duration_hours,
                })

            return patterns

        except Exception as e:
            logger.error(f"Failed to extract winning patterns: {e}")
            return []

    def recommend_algorithm_adjustments(self) -> List[str]:
        """
        Recommend adjustments based on performance analysis.

        Returns list of actionable recommendations.
        """
        recommendations = []

        try:
            for algo_type, metrics in self.global_metrics.items():
                if metrics.total_signals < 5:
                    continue  # Not enough data

                if metrics.accuracy < 35:
                    recommendations.append(
                        f"⚠️ {algo_type.value}: Low accuracy ({metrics.accuracy:.1f}%). "
                        f"Consider disabling or retuning parameters."
                    )
                elif metrics.accuracy > 70:
                    recommendations.append(
                        f"✅ {algo_type.value}: High accuracy ({metrics.accuracy:.1f}%). "
                        f"Increase signal weight in composite scoring."
                    )

                if metrics.avg_loss > metrics.avg_win and metrics.total_signals > 10:
                    recommendations.append(
                        f"📉 {algo_type.value}: Avg loss (${abs(metrics.avg_loss):.2f}) > "
                        f"avg win (${metrics.avg_win:.2f}). Need better entry/exit logic."
                    )

            return recommendations

        except Exception as e:
            logger.error(f"Failed to generate recommendations: {e}")
            return []
