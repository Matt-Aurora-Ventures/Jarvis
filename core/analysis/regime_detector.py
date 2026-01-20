"""
Market Regime Detection System for Jarvis Trading Bot.
======================================================

Detects market regimes (trending, ranging, volatile, crash) and provides:
- Regime classification with probability estimates
- Transition detection between regimes
- Historical regime analysis
- Strategy recommendations per regime

Usage:
    from core.analysis.regime_detector import RegimeDetector, StrategyRecommendation

    detector = RegimeDetector()
    result = detector.detect(prices)

    print(f"Current regime: {result.regime}")
    print(f"Confidence: {result.confidence:.1%}")

    strategy = StrategyRecommendation.for_regime(result.regime)
    print(f"Recommended strategy: {strategy.name}")
"""

import logging
import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# =============================================================================
# Regime Definitions
# =============================================================================


class MarketRegime(str, Enum):
    """
    Market regime classifications.

    - TRENDING_UP: Clear upward price movement
    - TRENDING_DOWN: Clear downward price movement
    - RANGING: Sideways, range-bound market
    - VOLATILE: High volatility without clear direction
    - CRASH: Rapid decline with high volatility
    - RECOVERY: Rebound from crash/bottom
    """
    TRENDING_UP = "trending_up"
    TRENDING_DOWN = "trending_down"
    RANGING = "ranging"
    VOLATILE = "volatile"
    CRASH = "crash"
    RECOVERY = "recovery"

    @classmethod
    def all(cls) -> List["MarketRegime"]:
        """Get all regime values."""
        return list(cls)

    @classmethod
    def get_description(cls, regime: "MarketRegime") -> str:
        """Get human-readable description of a regime."""
        descriptions = {
            cls.TRENDING_UP: "Strong upward price movement with consistent higher highs and higher lows",
            cls.TRENDING_DOWN: "Strong downward price movement with consistent lower highs and lower lows",
            cls.RANGING: "Sideways price action oscillating within a defined range",
            cls.VOLATILE: "High price volatility without clear directional trend",
            cls.CRASH: "Rapid price decline with elevated volatility and panic selling",
            cls.RECOVERY: "Rebound from crash with increasing prices and decreasing volatility",
        }
        return descriptions.get(regime, "Unknown regime")


# =============================================================================
# Strategy Recommendations
# =============================================================================


@dataclass
class StrategyRecommendation:
    """
    Trading strategy recommendation for a market regime.

    Attributes:
        name: Strategy name (e.g., "TrendFollowing", "MeanReversion")
        position_size_multiplier: Multiplier for position sizing (1.0 = normal)
        description: Human-readable strategy description
        parameters: Strategy-specific parameters
    """
    name: str
    position_size_multiplier: float
    description: str
    parameters: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def for_regime(cls, regime: MarketRegime) -> "StrategyRecommendation":
        """Get recommended strategy for a market regime."""
        recommendations = {
            MarketRegime.TRENDING_UP: cls(
                name="TrendFollowing",
                position_size_multiplier=1.2,
                description="Follow the uptrend with momentum-based entries",
                parameters={
                    "stop_loss_type": "trailing",
                    "trailing_stop_pct": 0.05,
                    "add_on_pullbacks": True,
                    "take_profit_type": "trailing",
                },
            ),
            MarketRegime.TRENDING_DOWN: cls(
                name="TrendFollowing",
                position_size_multiplier=0.5,
                description="Short or avoid, use tight stops on any longs",
                parameters={
                    "stop_loss_type": "fixed",
                    "stop_loss_pct": 0.03,
                    "prefer_shorts": True,
                    "avoid_new_longs": True,
                },
            ),
            MarketRegime.RANGING: cls(
                name="MeanReversion",
                position_size_multiplier=1.0,
                description="Buy support, sell resistance within the range",
                parameters={
                    "stop_loss_type": "fixed",
                    "stop_loss_pct": 0.03,
                    "entry_at_support": True,
                    "exit_at_resistance": True,
                    "use_bb_bands": True,
                },
            ),
            MarketRegime.VOLATILE: cls(
                name="ReducedExposure",
                position_size_multiplier=0.5,
                description="Reduce position sizes, wider stops, avoid overtrading",
                parameters={
                    "stop_loss_type": "atr_based",
                    "atr_multiplier": 2.0,
                    "max_positions": 3,
                    "wait_for_clarity": True,
                },
            ),
            MarketRegime.CRASH: cls(
                name="DefensiveMode",
                position_size_multiplier=0.2,
                description="Minimize exposure, preserve capital, wait for stability",
                parameters={
                    "stop_loss_type": "fixed",
                    "stop_loss_pct": 0.02,
                    "avoid_new_longs": True,
                    "close_losing_positions": True,
                    "hedge_existing": True,
                },
            ),
            MarketRegime.RECOVERY: cls(
                name="Accumulation",
                position_size_multiplier=0.8,
                description="Cautiously accumulate as market stabilizes",
                parameters={
                    "stop_loss_type": "fixed",
                    "stop_loss_pct": 0.05,
                    "dca_enabled": True,
                    "entry_on_confirmation": True,
                    "avoid_fomo": True,
                },
            ),
        }
        return recommendations.get(
            regime,
            cls(
                name="Neutral",
                position_size_multiplier=0.5,
                description="Unknown regime - proceed with caution",
                parameters={"stop_loss_type": "fixed", "stop_loss_pct": 0.03},
            ),
        )


# =============================================================================
# Data Classes
# =============================================================================


@dataclass
class RegimeDetectionResult:
    """
    Result of regime detection.

    Attributes:
        regime: Detected market regime
        confidence: Confidence level (0-1)
        probabilities: Probability distribution over all regimes
        features: Extracted features used for classification
        timestamp: When detection was performed
    """
    regime: MarketRegime
    confidence: float
    probabilities: Dict[MarketRegime, float]
    features: Dict[str, float]
    timestamp: datetime

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "regime": self.regime.value,
            "confidence": round(self.confidence, 4),
            "probabilities": {k.value: round(v, 4) for k, v in self.probabilities.items()},
            "features": {k: round(v, 4) for k, v in self.features.items()},
            "timestamp": self.timestamp.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RegimeDetectionResult":
        """Create from dictionary."""
        # Parse regime
        regime_str = data.get("regime", "ranging")
        regime = MarketRegime(regime_str) if regime_str in [r.value for r in MarketRegime] else MarketRegime.RANGING

        # Parse probabilities
        raw_probs = data.get("probabilities", {})
        probabilities = {}
        for k, v in raw_probs.items():
            try:
                probabilities[MarketRegime(k)] = float(v)
            except (ValueError, TypeError):
                pass

        # Parse timestamp
        ts_str = data.get("timestamp", "")
        try:
            timestamp = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
        except (ValueError, TypeError):
            timestamp = datetime.now(timezone.utc)

        return cls(
            regime=regime,
            confidence=float(data.get("confidence", 0.0)),
            probabilities=probabilities,
            features=data.get("features", {}),
            timestamp=timestamp,
        )


@dataclass
class RegimeTransition:
    """
    Represents a transition between market regimes.

    Attributes:
        from_regime: Previous regime
        to_regime: New regime
        confidence: Confidence in the transition
        timestamp: When transition was detected
    """
    from_regime: MarketRegime
    to_regime: MarketRegime
    confidence: float
    timestamp: datetime

    def is_significant(self) -> bool:
        """
        Check if this is a significant regime change.

        Significant transitions include:
        - Any transition to CRASH
        - Transition from CRASH to RECOVERY
        - Transition between trending and ranging
        """
        # Same regime is not significant
        if self.from_regime == self.to_regime:
            return False

        # Crash transitions are always significant
        if self.to_regime == MarketRegime.CRASH:
            return True

        if self.from_regime == MarketRegime.CRASH:
            return True

        # Trend reversals are significant
        if self.from_regime == MarketRegime.TRENDING_UP and self.to_regime == MarketRegime.TRENDING_DOWN:
            return True

        if self.from_regime == MarketRegime.TRENDING_DOWN and self.to_regime == MarketRegime.TRENDING_UP:
            return True

        # Default: changes with high confidence are significant
        return self.confidence >= 0.7


# =============================================================================
# Feature Extraction
# =============================================================================


class RegimeFeatureExtractor:
    """
    Extract features for regime classification.

    Features extracted:
    - Volatility metrics (std, range, ATR)
    - Trend indicators (slope, strength, ADX approximation)
    - Momentum indicators (ROC, RSI)
    - Mean reversion indicators (BB position, MA distance)
    """

    def __init__(self, lookback: int = 20):
        """
        Initialize feature extractor.

        Args:
            lookback: Number of periods for lookback calculations
        """
        self.lookback = lookback

    def extract(self, prices: List[float], volumes: Optional[List[float]] = None) -> Dict[str, float]:
        """
        Extract features from price data.

        Args:
            prices: Historical prices (newest last)
            volumes: Optional volume data

        Returns:
            Dictionary of feature name -> value
        """
        # Clean prices - remove NaN and inf
        prices = self._clean_prices(prices)

        if len(prices) < self.lookback:
            return {}

        recent = prices[-self.lookback:]

        features = {}

        # 1. Volatility Features
        returns = self._calculate_returns(recent)
        features["volatility_std"] = self._std(returns) if returns else 0.0
        features["volatility_range"] = self._range_volatility(recent)
        features["volatility_atr"] = self._atr_approximation(recent)

        # 2. Trend Features
        features["trend_slope"] = self._linear_slope(recent)
        features["trend_strength"] = self._trend_strength(recent)
        features["trend_adx"] = self._adx_approximation(prices)

        # 3. Momentum Features
        features["momentum_roc"] = self._rate_of_change(recent, min(10, len(recent) - 1))
        features["momentum_rsi"] = self._calculate_rsi(prices)

        # 4. Mean Reversion Features
        features["mr_bb_position"] = self._bb_position(prices)
        features["mr_ma_distance"] = self._ma_distance(prices)

        # 5. Directional Features
        features["higher_highs"] = self._higher_highs_ratio(recent)
        features["lower_lows"] = self._lower_lows_ratio(recent)

        return features

    def _clean_prices(self, prices: List[float]) -> List[float]:
        """Remove NaN and inf values from prices."""
        cleaned = []
        last_valid = None

        for p in prices:
            if math.isnan(p) or math.isinf(p):
                if last_valid is not None:
                    cleaned.append(last_valid)
            else:
                cleaned.append(p)
                last_valid = p

        return cleaned

    def _calculate_returns(self, prices: List[float]) -> List[float]:
        """Calculate log returns."""
        if len(prices) < 2:
            return []

        returns = []
        for i in range(1, len(prices)):
            if prices[i - 1] > 0 and prices[i] > 0:
                returns.append(math.log(prices[i] / prices[i - 1]))

        return returns

    def _std(self, values: List[float]) -> float:
        """Calculate standard deviation."""
        if len(values) < 2:
            return 0.0

        mean = sum(values) / len(values)
        variance = sum((x - mean) ** 2 for x in values) / (len(values) - 1)
        return math.sqrt(variance)

    def _mean(self, values: List[float]) -> float:
        """Calculate mean."""
        return sum(values) / len(values) if values else 0.0

    def _range_volatility(self, prices: List[float]) -> float:
        """Calculate range-based volatility."""
        if not prices:
            return 0.0

        mean_price = self._mean(prices)
        if mean_price == 0:
            return 0.0

        return (max(prices) - min(prices)) / mean_price

    def _atr_approximation(self, prices: List[float]) -> float:
        """Approximate ATR from close prices only."""
        if len(prices) < 2:
            return 0.0

        true_ranges = []
        for i in range(1, len(prices)):
            # Approximate true range as absolute price change
            tr = abs(prices[i] - prices[i - 1])
            true_ranges.append(tr)

        if not true_ranges:
            return 0.0

        mean_price = self._mean(prices)
        if mean_price == 0:
            return 0.0

        return self._mean(true_ranges) / mean_price

    def _linear_slope(self, values: List[float]) -> float:
        """Calculate normalized linear regression slope."""
        if len(values) < 2:
            return 0.0

        n = len(values)
        x_mean = (n - 1) / 2
        y_mean = self._mean(values)

        if y_mean == 0:
            return 0.0

        numerator = sum((i - x_mean) * (values[i] - y_mean) for i in range(n))
        denominator = sum((i - x_mean) ** 2 for i in range(n))

        if denominator == 0:
            return 0.0

        slope = numerator / denominator
        # Normalize by mean
        return slope / y_mean

    def _trend_strength(self, prices: List[float]) -> float:
        """
        Calculate trend strength using R-squared.

        Returns value between 0 (no trend) and 1 (perfect trend).
        """
        if len(prices) < 2:
            return 0.0

        n = len(prices)
        x_mean = (n - 1) / 2
        y_mean = self._mean(prices)

        ss_tot = sum((y - y_mean) ** 2 for y in prices)
        if ss_tot == 0:
            return 0.0

        # Calculate regression
        numerator = sum((i - x_mean) * (prices[i] - y_mean) for i in range(n))
        denominator = sum((i - x_mean) ** 2 for i in range(n))

        if denominator == 0:
            return 0.0

        slope = numerator / denominator
        intercept = y_mean - slope * x_mean

        ss_res = sum((prices[i] - (slope * i + intercept)) ** 2 for i in range(n))
        r_squared = 1 - (ss_res / ss_tot)

        return max(0, min(1, r_squared))

    def _adx_approximation(self, prices: List[float], period: int = 14) -> float:
        """
        Approximate ADX from close prices.

        This is a simplified approximation since we don't have high/low data.
        """
        if len(prices) < period + 1:
            return 0.0

        # Use directional movement approximation
        plus_dm = []
        minus_dm = []

        for i in range(1, len(prices)):
            change = prices[i] - prices[i - 1]
            if change > 0:
                plus_dm.append(change)
                minus_dm.append(0)
            else:
                plus_dm.append(0)
                minus_dm.append(abs(change))

        # Smooth using EMA
        plus_di = self._ema(plus_dm, period)
        minus_di = self._ema(minus_dm, period)

        if plus_di + minus_di == 0:
            return 0.0

        dx = abs(plus_di - minus_di) / (plus_di + minus_di)

        # Scale to 0-100 range then normalize to 0-1
        return min(1.0, dx)

    def _ema(self, values: List[float], period: int) -> float:
        """Calculate EMA of values."""
        if len(values) < period:
            return self._mean(values) if values else 0.0

        multiplier = 2 / (period + 1)
        ema = sum(values[:period]) / period

        for value in values[period:]:
            ema = (value - ema) * multiplier + ema

        return ema

    def _rate_of_change(self, prices: List[float], period: int) -> float:
        """Calculate rate of change (momentum)."""
        if len(prices) <= period or period <= 0:
            return 0.0

        if prices[-period - 1] == 0:
            return 0.0

        return (prices[-1] - prices[-period - 1]) / prices[-period - 1]

    def _calculate_rsi(self, prices: List[float], period: int = 14) -> float:
        """Calculate RSI (0-100)."""
        if len(prices) < period + 1:
            return 50.0

        gains = []
        losses = []

        for i in range(1, len(prices)):
            change = prices[i] - prices[i - 1]
            if change > 0:
                gains.append(change)
                losses.append(0)
            else:
                gains.append(0)
                losses.append(abs(change))

        recent_gains = gains[-period:]
        recent_losses = losses[-period:]

        avg_gain = sum(recent_gains) / period if recent_gains else 0
        avg_loss = sum(recent_losses) / period if recent_losses else 0

        if avg_loss == 0:
            return 100.0 if avg_gain > 0 else 50.0

        rs = avg_gain / avg_loss
        return 100 - (100 / (1 + rs))

    def _bb_position(self, prices: List[float], period: int = 20, std_mult: float = 2.0) -> float:
        """
        Calculate position within Bollinger Bands.

        Returns value from -1 (at lower band) to 1 (at upper band).
        """
        if len(prices) < period:
            return 0.0

        recent = prices[-period:]
        middle = self._mean(recent)

        variance = sum((p - middle) ** 2 for p in recent) / period
        std = math.sqrt(variance)

        if std == 0:
            return 0.0

        upper = middle + (std_mult * std)
        lower = middle - (std_mult * std)
        band_width = upper - lower

        if band_width == 0:
            return 0.0

        current = prices[-1]
        position = (current - middle) / (band_width / 2)

        return max(-1, min(1, position))

    def _ma_distance(self, prices: List[float], period: int = 20) -> float:
        """Calculate distance from moving average (normalized)."""
        if len(prices) < period:
            return 0.0

        ma = sum(prices[-period:]) / period
        if ma == 0:
            return 0.0

        return (prices[-1] - ma) / ma

    def _higher_highs_ratio(self, prices: List[float]) -> float:
        """Calculate ratio of higher highs in recent prices."""
        if len(prices) < 3:
            return 0.5

        higher_count = 0
        total = 0

        for i in range(1, len(prices)):
            if prices[i] > prices[i - 1]:
                higher_count += 1
            total += 1

        return higher_count / total if total > 0 else 0.5

    def _lower_lows_ratio(self, prices: List[float]) -> float:
        """Calculate ratio of lower lows in recent prices."""
        if len(prices) < 3:
            return 0.5

        lower_count = 0
        total = 0

        for i in range(1, len(prices)):
            if prices[i] < prices[i - 1]:
                lower_count += 1
            total += 1

        return lower_count / total if total > 0 else 0.5


# =============================================================================
# Regime Detector
# =============================================================================


class RegimeDetector:
    """
    Market regime detector.

    Classifies market conditions into regimes and provides:
    - Current regime detection with confidence
    - Probability distribution over regimes
    - Transition detection
    - Historical analysis
    """

    def __init__(
        self,
        lookback: int = 20,
        smoothing: int = 3,
        crash_threshold: float = -0.15,
        trend_threshold: float = 0.03,
        volatility_threshold: float = 0.04,
    ):
        """
        Initialize regime detector.

        Args:
            lookback: Periods for feature calculation
            smoothing: Number of detections to smooth
            crash_threshold: Return threshold for crash detection
            trend_threshold: Slope threshold for trend detection
            volatility_threshold: Volatility threshold for volatile regime
        """
        self.lookback = lookback
        self.smoothing = smoothing
        self.crash_threshold = crash_threshold
        self.trend_threshold = trend_threshold
        self.volatility_threshold = volatility_threshold

        self.feature_extractor = RegimeFeatureExtractor(lookback=lookback)
        self._detection_history: List[RegimeDetectionResult] = []

    def detect(self, prices: List[float], volumes: Optional[List[float]] = None) -> RegimeDetectionResult:
        """
        Detect current market regime.

        Args:
            prices: Historical prices (newest last)
            volumes: Optional volume data

        Returns:
            RegimeDetectionResult with regime and probabilities
        """
        timestamp = datetime.now(timezone.utc)

        # Handle edge cases
        if not prices or len(prices) < 2:
            return self._default_result(timestamp)

        # Extract features
        features = self.feature_extractor.extract(prices, volumes)

        if not features:
            return self._default_result(timestamp)

        # Calculate probabilities for each regime
        probabilities = self._calculate_probabilities(features, prices)

        # Normalize probabilities
        total = sum(probabilities.values())
        if total > 0:
            probabilities = {k: v / total for k, v in probabilities.items()}
        else:
            # Equal probabilities if something went wrong
            probabilities = {r: 1.0 / len(MarketRegime.all()) for r in MarketRegime.all()}

        # Get highest probability regime
        regime = max(probabilities, key=probabilities.get)
        confidence = probabilities[regime]

        # Apply smoothing if we have history
        if self._detection_history and self.smoothing > 1:
            regime, confidence = self._apply_smoothing(regime, confidence, probabilities)

        result = RegimeDetectionResult(
            regime=regime,
            confidence=confidence,
            probabilities=probabilities,
            features=features,
            timestamp=timestamp,
        )

        # Store in history
        self._detection_history.append(result)
        if len(self._detection_history) > 100:
            self._detection_history = self._detection_history[-100:]

        return result

    def _default_result(self, timestamp: datetime) -> RegimeDetectionResult:
        """Return default result for insufficient data."""
        return RegimeDetectionResult(
            regime=MarketRegime.RANGING,
            confidence=0.0,
            probabilities={r: 0.0 for r in MarketRegime.all()},
            features={},
            timestamp=timestamp,
        )

    def _calculate_probabilities(
        self,
        features: Dict[str, float],
        prices: List[float],
    ) -> Dict[MarketRegime, float]:
        """
        Calculate probability scores for each regime.

        Uses a rule-based scoring approach combining multiple indicators.
        """
        scores = {regime: 0.0 for regime in MarketRegime.all()}

        # Get feature values with defaults
        vol_std = features.get("volatility_std", 0.02)
        trend_slope = features.get("trend_slope", 0)
        trend_strength = features.get("trend_strength", 0.5)
        rsi = features.get("momentum_rsi", 50)
        bb_pos = features.get("mr_bb_position", 0)
        higher_highs = features.get("higher_highs", 0.5)
        lower_lows = features.get("lower_lows", 0.5)
        ma_distance = features.get("mr_ma_distance", 0)

        # Calculate recent return
        recent_return = 0.0
        if len(prices) >= 20:
            if prices[-20] > 0:
                recent_return = (prices[-1] - prices[-20]) / prices[-20]

        # Score CRASH regime
        if recent_return < self.crash_threshold:
            scores[MarketRegime.CRASH] += 3.0
        if recent_return < -0.10:
            scores[MarketRegime.CRASH] += 2.0
        if vol_std > self.volatility_threshold * 1.5:
            scores[MarketRegime.CRASH] += 1.5
        if rsi < 30:
            scores[MarketRegime.CRASH] += 1.0
        if lower_lows > 0.7:
            scores[MarketRegime.CRASH] += 1.0

        # Score TRENDING_UP regime
        if trend_slope > self.trend_threshold:
            scores[MarketRegime.TRENDING_UP] += 2.5
        if trend_strength > 0.7:
            scores[MarketRegime.TRENDING_UP] += 2.0
        if higher_highs > 0.6:
            scores[MarketRegime.TRENDING_UP] += 1.5
        if rsi > 55:
            scores[MarketRegime.TRENDING_UP] += 1.0
        if ma_distance > 0.02:
            scores[MarketRegime.TRENDING_UP] += 1.0

        # Score TRENDING_DOWN regime
        if trend_slope < -self.trend_threshold:
            scores[MarketRegime.TRENDING_DOWN] += 2.5
        if trend_strength > 0.7 and trend_slope < 0:
            scores[MarketRegime.TRENDING_DOWN] += 2.0
        if lower_lows > 0.6:
            scores[MarketRegime.TRENDING_DOWN] += 1.5
        if rsi < 45:
            scores[MarketRegime.TRENDING_DOWN] += 1.0
        if ma_distance < -0.02:
            scores[MarketRegime.TRENDING_DOWN] += 1.0

        # Score RANGING regime
        if trend_strength < 0.3:
            scores[MarketRegime.RANGING] += 2.5
        if abs(trend_slope) < self.trend_threshold / 2:
            scores[MarketRegime.RANGING] += 2.0
        if vol_std < self.volatility_threshold * 0.5:
            scores[MarketRegime.RANGING] += 1.5
        if 40 < rsi < 60:
            scores[MarketRegime.RANGING] += 1.0
        if abs(bb_pos) < 0.5:
            scores[MarketRegime.RANGING] += 1.0

        # Score VOLATILE regime
        if vol_std > self.volatility_threshold:
            scores[MarketRegime.VOLATILE] += 2.5
        if trend_strength < 0.4 and vol_std > self.volatility_threshold * 0.75:
            scores[MarketRegime.VOLATILE] += 2.0
        if abs(bb_pos) > 0.8:
            scores[MarketRegime.VOLATILE] += 1.5
        if rsi < 25 or rsi > 75:
            scores[MarketRegime.VOLATILE] += 1.0

        # Score RECOVERY regime
        if recent_return > 0.05 and prices[-1] < prices[0]:  # Bouncing but still below start
            scores[MarketRegime.RECOVERY] += 2.0
        if rsi > 40 and rsi < 60 and lower_lows > 0.3 and higher_highs > 0.5:
            scores[MarketRegime.RECOVERY] += 1.5
        if vol_std < self.volatility_threshold and trend_slope > 0:
            scores[MarketRegime.RECOVERY] += 1.0

        # Ensure minimum scores for stability
        for regime in scores:
            scores[regime] = max(0.1, scores[regime])

        return scores

    def _apply_smoothing(
        self,
        current_regime: MarketRegime,
        current_confidence: float,
        current_probs: Dict[MarketRegime, float],
    ) -> Tuple[MarketRegime, float]:
        """
        Apply smoothing using recent detection history.

        Prevents rapid regime flipping by requiring consistent signals.
        """
        # Get recent detections
        recent = self._detection_history[-self.smoothing:]
        if not recent:
            return current_regime, current_confidence

        # Count regimes in history
        regime_counts = {}
        for result in recent:
            regime_counts[result.regime] = regime_counts.get(result.regime, 0) + 1

        # Add current detection
        regime_counts[current_regime] = regime_counts.get(current_regime, 0) + 1

        # Get most common regime
        smoothed_regime = max(regime_counts, key=regime_counts.get)

        # Calculate smoothed confidence
        consistency = regime_counts[smoothed_regime] / (len(recent) + 1)
        smoothed_confidence = current_confidence * consistency

        return smoothed_regime, smoothed_confidence

    def detect_transitions(
        self,
        prices: List[float],
        window_step: int = 10,
    ) -> List[RegimeTransition]:
        """
        Detect regime transitions over a price series.

        Args:
            prices: Historical prices
            window_step: Step size between detection windows

        Returns:
            List of detected transitions
        """
        if len(prices) < self.lookback * 2:
            return []

        transitions = []
        prev_regime = None

        for i in range(self.lookback, len(prices), window_step):
            window = prices[max(0, i - self.lookback * 2):i]
            result = self.detect(window)

            if prev_regime is not None and result.regime != prev_regime:
                transition = RegimeTransition(
                    from_regime=prev_regime,
                    to_regime=result.regime,
                    confidence=result.confidence,
                    timestamp=result.timestamp,
                )
                transitions.append(transition)

            prev_regime = result.regime

        return transitions

    def analyze_history(
        self,
        prices: List[float],
        window_size: int = 50,
        step: int = 25,
    ) -> Dict[str, Any]:
        """
        Analyze historical regime distribution.

        Args:
            prices: Historical prices
            window_size: Size of detection windows
            step: Step between windows

        Returns:
            Dictionary with regime distribution, durations, and transitions
        """
        if len(prices) < window_size:
            return {
                "regime_distribution": {},
                "regime_durations": {},
                "transitions": [],
                "total_windows": 0,
            }

        regimes = []

        for i in range(window_size, len(prices) + 1, step):
            window = prices[i - window_size:i]
            result = self.detect(window)
            regimes.append(result.regime)

        # Calculate distribution
        distribution = {}
        for regime in regimes:
            distribution[regime] = distribution.get(regime, 0) + 1

        total = len(regimes)
        distribution = {k: v / total for k, v in distribution.items()}

        # Calculate average durations
        durations = {}
        current_regime = regimes[0] if regimes else None
        current_duration = 0
        regime_runs = {regime: [] for regime in MarketRegime.all()}

        for regime in regimes:
            if regime == current_regime:
                current_duration += 1
            else:
                if current_regime is not None:
                    regime_runs[current_regime].append(current_duration)
                current_regime = regime
                current_duration = 1

        # Don't forget last run
        if current_regime is not None and current_duration > 0:
            regime_runs[current_regime].append(current_duration)

        for regime, runs in regime_runs.items():
            if runs:
                durations[regime] = sum(runs) / len(runs) * step  # Convert to price periods

        # Get transitions
        transitions = []
        for i in range(1, len(regimes)):
            if regimes[i] != regimes[i - 1]:
                transitions.append({
                    "from": regimes[i - 1].value,
                    "to": regimes[i].value,
                    "position": i * step,
                })

        return {
            "regime_distribution": distribution,
            "regime_durations": durations,
            "transitions": transitions,
            "total_windows": total,
        }


# =============================================================================
# Convenience Functions
# =============================================================================


def get_regime_detector(
    lookback: int = 20,
    smoothing: int = 3,
) -> RegimeDetector:
    """
    Get a configured regime detector instance.

    Args:
        lookback: Periods for feature calculation
        smoothing: Number of detections to smooth

    Returns:
        Configured RegimeDetector
    """
    return RegimeDetector(lookback=lookback, smoothing=smoothing)


# =============================================================================
# Module Exports
# =============================================================================

__all__ = [
    "MarketRegime",
    "RegimeDetectionResult",
    "RegimeTransition",
    "RegimeFeatureExtractor",
    "RegimeDetector",
    "StrategyRecommendation",
    "get_regime_detector",
]
