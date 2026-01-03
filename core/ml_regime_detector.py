"""
ML Volatility Regime Detector for Jarvis Trading Bot
=====================================================

The "Brain" enhancement - Machine learning volatility prediction.

Uses scikit-learn to predict market regimes and automatically
switch between trading strategies:
- Low volatility → Grid Trading (range-bound strategies)
- Medium volatility → Mean Reversion
- High volatility → Trend Following
- Extreme volatility → Risk-off (reduce position sizes)

Phase 3 Implementation per Quant Analyst specification.

Usage:
    from core.ml_regime_detector import VolatilityRegimeDetector
    
    detector = VolatilityRegimeDetector()
    detector.fit(historical_prices)
    regime = detector.predict(recent_prices)
"""

import json
import logging
import math
import pickle
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Optional ML imports
try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False
    np = None

try:
    from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
    from sklearn.preprocessing import StandardScaler
    from sklearn.model_selection import train_test_split
    from sklearn.metrics import classification_report
    HAS_SKLEARN = True
except ImportError:
    HAS_SKLEARN = False


logger = logging.getLogger(__name__)


# ============================================================================
# Regime Definitions
# ============================================================================

class MarketRegime:
    """Market regime classifications."""
    LOW_VOL = "low_volatility"       # Calm markets - Grid Trading
    MEDIUM_VOL = "medium_volatility"  # Normal markets - Mean Reversion
    HIGH_VOL = "high_volatility"      # Trending markets - Trend Following
    EXTREME_VOL = "extreme_volatility"  # Crisis - Risk-off
    
    @classmethod
    def all(cls) -> List[str]:
        return [cls.LOW_VOL, cls.MEDIUM_VOL, cls.HIGH_VOL, cls.EXTREME_VOL]
    
    @classmethod
    def to_strategy(cls, regime: str) -> str:
        """Map regime to recommended strategy."""
        mapping = {
            cls.LOW_VOL: "GridTrader",
            cls.MEDIUM_VOL: "MeanReversion",
            cls.HIGH_VOL: "TrendFollower",
            cls.EXTREME_VOL: "RiskOff",
        }
        return mapping.get(regime, "MeanReversion")


@dataclass
class RegimePrediction:
    """Result of regime prediction."""
    regime: str
    confidence: float
    recommended_strategy: str
    features: Dict[str, float]
    timestamp: float
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "regime": self.regime,
            "confidence": round(self.confidence, 4),
            "recommended_strategy": self.recommended_strategy,
            "features": {k: round(v, 4) for k, v in self.features.items()},
            "timestamp": self.timestamp,
        }


# ============================================================================
# Feature Engineering
# ============================================================================

class FeatureExtractor:
    """
    Extract features for regime classification.
    
    Features:
    - Volatility metrics (std, ATR, Parkinson)
    - Trend indicators (ADX, MA slope)
    - Mean reversion indicators (RSI, BB position)
    - Volume patterns (relative volume, volume trend)
    """
    
    def __init__(self, lookback: int = 20):
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
        if len(prices) < self.lookback:
            return {}
        
        recent = prices[-self.lookback:]
        
        features = {}
        
        # 1. Volatility Features
        returns = self._calculate_returns(recent)
        features["volatility_std"] = self._std(returns) if returns else 0
        features["volatility_range"] = (max(recent) - min(recent)) / self._mean(recent) if recent else 0
        features["volatility_parkinson"] = self._parkinson_volatility(recent)
        
        # 2. Trend Features
        features["trend_slope"] = self._linear_slope(recent)
        features["trend_strength"] = self._trend_strength(recent)
        features["ma_distance"] = self._ma_distance(prices, 20)
        
        # 3. Mean Reversion Features
        features["rsi"] = self._calculate_rsi(prices)
        features["bb_position"] = self._bb_position(prices)
        
        # 4. Momentum Features
        features["momentum_5"] = self._momentum(recent, 5)
        features["momentum_10"] = self._momentum(recent, 10)
        
        # 5. Volume Features (if available)
        if volumes and len(volumes) >= self.lookback:
            recent_vol = volumes[-self.lookback:]
            features["volume_relative"] = recent_vol[-1] / self._mean(recent_vol) if self._mean(recent_vol) > 0 else 1
            features["volume_trend"] = self._linear_slope(recent_vol)
        else:
            features["volume_relative"] = 1.0
            features["volume_trend"] = 0.0
        
        return features
    
    def _calculate_returns(self, prices: List[float]) -> List[float]:
        """Calculate log returns."""
        if len(prices) < 2:
            return []
        returns = []
        for i in range(1, len(prices)):
            if prices[i-1] > 0:
                returns.append(math.log(prices[i] / prices[i-1]))
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
    
    def _parkinson_volatility(self, prices: List[float]) -> float:
        """
        Parkinson volatility estimator.
        Uses high-low range (approximated from price differences).
        """
        if len(prices) < 2:
            return 0.0
        
        # Approximate high-low as absolute price changes
        ranges = [abs(prices[i] - prices[i-1]) for i in range(1, len(prices))]
        if not ranges:
            return 0.0
        
        mean_range = sum(ranges) / len(ranges)
        return mean_range / self._mean(prices) if self._mean(prices) > 0 else 0
    
    def _linear_slope(self, values: List[float]) -> float:
        """Calculate linear regression slope (normalized)."""
        if len(values) < 2:
            return 0.0
        
        n = len(values)
        x_mean = (n - 1) / 2
        y_mean = sum(values) / n
        
        numerator = sum((i - x_mean) * (values[i] - y_mean) for i in range(n))
        denominator = sum((i - x_mean) ** 2 for i in range(n))
        
        if denominator == 0:
            return 0.0
        
        slope = numerator / denominator
        # Normalize by mean price
        return slope / y_mean if y_mean > 0 else 0
    
    def _trend_strength(self, prices: List[float]) -> float:
        """
        Measure trend strength (0 = no trend, 1 = strong trend).
        Uses R-squared of linear fit.
        """
        if len(prices) < 2:
            return 0.0
        
        n = len(prices)
        x_mean = (n - 1) / 2
        y_mean = sum(prices) / n
        
        ss_tot = sum((y - y_mean) ** 2 for y in prices)
        if ss_tot == 0:
            return 0.0
        
        # Calculate regression line
        numerator = sum((i - x_mean) * (prices[i] - y_mean) for i in range(n))
        denominator = sum((i - x_mean) ** 2 for i in range(n))
        
        if denominator == 0:
            return 0.0
        
        slope = numerator / denominator
        intercept = y_mean - slope * x_mean
        
        # Calculate R-squared
        ss_res = sum((prices[i] - (slope * i + intercept)) ** 2 for i in range(n))
        r_squared = 1 - (ss_res / ss_tot)
        
        return max(0, r_squared)
    
    def _ma_distance(self, prices: List[float], period: int) -> float:
        """Distance from moving average (normalized)."""
        if len(prices) < period:
            return 0.0
        
        ma = sum(prices[-period:]) / period
        current = prices[-1]
        
        return (current - ma) / ma if ma > 0 else 0
    
    def _calculate_rsi(self, prices: List[float], period: int = 14) -> float:
        """Calculate RSI (0-100)."""
        if len(prices) < period + 1:
            return 50.0
        
        gains = []
        losses = []
        
        for i in range(1, len(prices)):
            change = prices[i] - prices[i-1]
            if change > 0:
                gains.append(change)
                losses.append(0)
            else:
                gains.append(0)
                losses.append(abs(change))
        
        avg_gain = sum(gains[-period:]) / period
        avg_loss = sum(losses[-period:]) / period
        
        if avg_loss == 0:
            return 100.0
        
        rs = avg_gain / avg_loss
        return 100 - (100 / (1 + rs))
    
    def _bb_position(self, prices: List[float], period: int = 20, std_dev: float = 2.0) -> float:
        """
        Position within Bollinger Bands (-1 to 1).
        -1 = at lower band, 0 = at middle, 1 = at upper band
        """
        if len(prices) < period:
            return 0.0
        
        recent = prices[-period:]
        middle = sum(recent) / period
        
        variance = sum((p - middle) ** 2 for p in recent) / period
        std = math.sqrt(variance)
        
        if std == 0:
            return 0.0
        
        upper = middle + (std_dev * std)
        lower = middle - (std_dev * std)
        
        current = prices[-1]
        band_width = upper - lower
        
        if band_width == 0:
            return 0.0
        
        position = (current - middle) / (band_width / 2)
        return max(-1, min(1, position))
    
    def _momentum(self, prices: List[float], period: int) -> float:
        """Calculate price momentum (normalized return over period)."""
        if len(prices) < period:
            return 0.0
        
        return (prices[-1] - prices[-period]) / prices[-period] if prices[-period] > 0 else 0


# ============================================================================
# Volatility Regime Detector
# ============================================================================

class VolatilityRegimeDetector:
    """
    ML-based volatility regime detector.
    
    Uses Random Forest or Gradient Boosting to classify market regimes
    based on extracted features.
    
    Training:
        1. Extract features from historical data
        2. Label regimes based on forward volatility
        3. Train classifier on labeled data
        
    Prediction:
        1. Extract features from recent data
        2. Classify current regime
        3. Return recommended strategy
    """
    
    def __init__(
        self,
        model_type: str = "random_forest",  # or "gradient_boosting"
        lookback: int = 20,
        model_path: Optional[Path] = None,
    ):
        self.model_type = model_type
        self.lookback = lookback
        self.model_path = model_path
        
        self.feature_extractor = FeatureExtractor(lookback=lookback)
        self._model = None
        self._scaler = None
        self._feature_names: List[str] = []
        self._is_fitted = False
        
        # Volatility thresholds for labeling (percentiles)
        self.vol_thresholds = {
            "low": 0.25,      # 25th percentile
            "medium": 0.50,   # 50th percentile
            "high": 0.75,     # 75th percentile
        }
    
    def _create_model(self):
        """Create the ML model."""
        if not HAS_SKLEARN:
            logger.error("scikit-learn not installed")
            return None
        
        if self.model_type == "gradient_boosting":
            return GradientBoostingClassifier(
                n_estimators=100,
                max_depth=5,
                learning_rate=0.1,
                random_state=42,
            )
        else:
            return RandomForestClassifier(
                n_estimators=100,
                max_depth=10,
                min_samples_split=5,
                random_state=42,
            )
    
    def fit(
        self,
        prices: List[float],
        volumes: Optional[List[float]] = None,
        forward_window: int = 10,
    ) -> bool:
        """
        Train the regime detector on historical data.
        
        Args:
            prices: Historical price data
            volumes: Optional volume data
            forward_window: Window for calculating forward volatility (labeling)
            
        Returns:
            True if training successful
        """
        if not HAS_SKLEARN or not HAS_NUMPY:
            logger.error("Required libraries not installed (numpy, scikit-learn)")
            return False
        
        min_data = self.lookback + forward_window + 100
        if len(prices) < min_data:
            logger.error(f"Need at least {min_data} data points for training")
            return False
        
        logger.info("Extracting features...")
        
        # Extract features for each point
        X = []
        y = []
        
        for i in range(self.lookback, len(prices) - forward_window):
            # Extract features using data up to point i
            features = self.feature_extractor.extract(
                prices[:i+1],
                volumes[:i+1] if volumes else None
            )
            
            if not features:
                continue
            
            # Calculate forward volatility for labeling
            forward_prices = prices[i:i+forward_window]
            forward_returns = [
                math.log(forward_prices[j] / forward_prices[j-1])
                for j in range(1, len(forward_prices))
                if forward_prices[j-1] > 0
            ]
            
            if not forward_returns:
                continue
            
            forward_vol = self._std(forward_returns)
            
            X.append(list(features.values()))
            y.append(forward_vol)
            
            if not self._feature_names:
                self._feature_names = list(features.keys())
        
        if len(X) < 100:
            logger.error("Not enough valid samples for training")
            return False
        
        X = np.array(X)
        y = np.array(y)
        
        # Convert volatility to regime labels
        y_labels = self._volatility_to_regime(y)
        
        logger.info(f"Training on {len(X)} samples...")
        
        # Scale features
        self._scaler = StandardScaler()
        X_scaled = self._scaler.fit_transform(X)
        
        # Train/test split
        X_train, X_test, y_train, y_test = train_test_split(
            X_scaled, y_labels, test_size=0.2, random_state=42
        )
        
        # Train model
        self._model = self._create_model()
        self._model.fit(X_train, y_train)
        
        # Evaluate
        y_pred = self._model.predict(X_test)
        logger.info(f"Training complete. Test accuracy: {(y_pred == y_test).mean():.2%}")
        
        self._is_fitted = True
        
        # Save model if path provided
        if self.model_path:
            self.save(self.model_path)
        
        return True
    
    def _volatility_to_regime(self, volatilities: 'np.ndarray') -> List[str]:
        """Convert volatility values to regime labels."""
        if not HAS_NUMPY:
            return []
        
        percentiles = {
            "low": np.percentile(volatilities, self.vol_thresholds["low"] * 100),
            "medium": np.percentile(volatilities, self.vol_thresholds["medium"] * 100),
            "high": np.percentile(volatilities, self.vol_thresholds["high"] * 100),
        }
        
        labels = []
        for vol in volatilities:
            if vol <= percentiles["low"]:
                labels.append(MarketRegime.LOW_VOL)
            elif vol <= percentiles["medium"]:
                labels.append(MarketRegime.MEDIUM_VOL)
            elif vol <= percentiles["high"]:
                labels.append(MarketRegime.HIGH_VOL)
            else:
                labels.append(MarketRegime.EXTREME_VOL)
        
        return labels
    
    def _std(self, values: List[float]) -> float:
        """Calculate standard deviation."""
        if len(values) < 2:
            return 0.0
        mean = sum(values) / len(values)
        variance = sum((x - mean) ** 2 for x in values) / (len(values) - 1)
        return math.sqrt(variance)
    
    def predict(
        self,
        prices: List[float],
        volumes: Optional[List[float]] = None,
    ) -> RegimePrediction:
        """
        Predict current market regime.
        
        Args:
            prices: Recent price data
            volumes: Optional volume data
            
        Returns:
            RegimePrediction with regime and recommended strategy
        """
        # Extract features
        features = self.feature_extractor.extract(prices, volumes)
        
        if not features:
            return RegimePrediction(
                regime=MarketRegime.MEDIUM_VOL,
                confidence=0.0,
                recommended_strategy=MarketRegime.to_strategy(MarketRegime.MEDIUM_VOL),
                features={},
                timestamp=time.time(),
            )
        
        # Use ML model if fitted
        if self._is_fitted and self._model and self._scaler and HAS_NUMPY:
            X = np.array([list(features.values())])
            X_scaled = self._scaler.transform(X)
            
            regime = self._model.predict(X_scaled)[0]
            probabilities = self._model.predict_proba(X_scaled)[0]
            confidence = max(probabilities)
        else:
            # Fallback to rule-based classification
            regime, confidence = self._rule_based_classify(features)
        
        return RegimePrediction(
            regime=regime,
            confidence=confidence,
            recommended_strategy=MarketRegime.to_strategy(regime),
            features=features,
            timestamp=time.time(),
        )
    
    def _rule_based_classify(self, features: Dict[str, float]) -> Tuple[str, float]:
        """
        Rule-based regime classification (fallback).
        
        Uses simple thresholds on volatility and trend features.
        """
        vol = features.get("volatility_std", 0)
        trend = features.get("trend_strength", 0)
        rsi = features.get("rsi", 50)
        
        # Volatility thresholds (daily returns)
        if vol < 0.01:  # <1% daily volatility
            regime = MarketRegime.LOW_VOL
            confidence = 0.7
        elif vol < 0.025:  # 1-2.5%
            regime = MarketRegime.MEDIUM_VOL
            confidence = 0.6
        elif vol < 0.05:  # 2.5-5%
            regime = MarketRegime.HIGH_VOL
            confidence = 0.7
        else:  # >5%
            regime = MarketRegime.EXTREME_VOL
            confidence = 0.8
        
        # Adjust based on trend strength
        if trend > 0.7 and regime == MarketRegime.MEDIUM_VOL:
            regime = MarketRegime.HIGH_VOL
            confidence = 0.65
        elif trend < 0.3 and regime == MarketRegime.HIGH_VOL:
            regime = MarketRegime.MEDIUM_VOL
            confidence = 0.55
        
        return regime, confidence
    
    def save(self, path: Path):
        """Save model to disk."""
        if not self._is_fitted:
            logger.warning("Model not fitted, nothing to save")
            return
        
        save_data = {
            "model": self._model,
            "scaler": self._scaler,
            "feature_names": self._feature_names,
            "model_type": self.model_type,
            "lookback": self.lookback,
        }
        
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "wb") as f:
            pickle.dump(save_data, f)
        
        logger.info(f"Model saved to {path}")
    
    def load(self, path: Path) -> bool:
        """Load model from disk."""
        if not path.exists():
            logger.warning(f"Model file not found: {path}")
            return False
        
        try:
            with open(path, "rb") as f:
                save_data = pickle.load(f)
            
            self._model = save_data["model"]
            self._scaler = save_data["scaler"]
            self._feature_names = save_data["feature_names"]
            self.model_type = save_data.get("model_type", "random_forest")
            self.lookback = save_data.get("lookback", 20)
            self._is_fitted = True
            
            logger.info(f"Model loaded from {path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to load model: {e}")
            return False


# ============================================================================
# Adaptive Strategy Switcher
# ============================================================================

class AdaptiveStrategySwitcher:
    """
    Automatically switches between strategies based on detected regime.
    
    This is what makes AI Agents different from static bots:
    - Static bots use fixed rules
    - AI Agents adapt to market conditions
    """
    
    def __init__(
        self,
        detector: Optional[VolatilityRegimeDetector] = None,
        switch_cooldown_minutes: int = 30,
    ):
        self.detector = detector or VolatilityRegimeDetector()
        self.switch_cooldown_minutes = switch_cooldown_minutes
        
        self._current_strategy: Optional[str] = None
        self._last_switch_time: float = 0
        self._regime_history: List[RegimePrediction] = []
    
    def update(
        self,
        prices: List[float],
        volumes: Optional[List[float]] = None,
    ) -> Dict[str, Any]:
        """
        Update regime detection and potentially switch strategies.
        
        Returns:
            Dict with current regime, strategy, and whether a switch occurred
        """
        prediction = self.detector.predict(prices, volumes)
        self._regime_history.append(prediction)
        
        # Keep history bounded
        if len(self._regime_history) > 100:
            self._regime_history = self._regime_history[-100:]
        
        recommended = prediction.recommended_strategy
        switched = False
        
        # Check if we should switch
        current_time = time.time()
        minutes_since_switch = (current_time - self._last_switch_time) / 60
        
        if self._current_strategy is None:
            # First run
            self._current_strategy = recommended
            self._last_switch_time = current_time
            switched = True
        elif recommended != self._current_strategy:
            # Check cooldown
            if minutes_since_switch >= self.switch_cooldown_minutes:
                # Check if regime is stable (last 3 predictions agree)
                if len(self._regime_history) >= 3:
                    recent_regimes = [p.regime for p in self._regime_history[-3:]]
                    if len(set(recent_regimes)) == 1:  # All same
                        self._current_strategy = recommended
                        self._last_switch_time = current_time
                        switched = True
        
        return {
            "current_strategy": self._current_strategy,
            "recommended_strategy": recommended,
            "regime": prediction.regime,
            "confidence": prediction.confidence,
            "switched": switched,
            "minutes_since_switch": round(minutes_since_switch, 1),
            "features": prediction.features,
        }
    
    def get_strategy_distribution(self) -> Dict[str, int]:
        """Get distribution of regimes from history."""
        distribution = {}
        for pred in self._regime_history:
            regime = pred.regime
            distribution[regime] = distribution.get(regime, 0) + 1
        return distribution


# ============================================================================
# Demo
# ============================================================================

if __name__ == "__main__":
    import random
    
    print("=== ML Volatility Regime Detector Demo ===\n")
    
    # Generate sample data with different regimes
    print("Generating synthetic price data with varying volatility...")
    
    prices = [100.0]
    
    # Low volatility period
    for _ in range(100):
        change = random.gauss(0, 0.5)  # 0.5% std
        prices.append(prices[-1] * (1 + change/100))
    
    # High volatility period (trending up)
    for _ in range(100):
        change = random.gauss(0.5, 3)  # 3% std, upward drift
        prices.append(prices[-1] * (1 + change/100))
    
    # Medium volatility period
    for _ in range(100):
        change = random.gauss(0, 1.5)  # 1.5% std
        prices.append(prices[-1] * (1 + change/100))
    
    # Extreme volatility period
    for _ in range(50):
        change = random.gauss(-1, 6)  # 6% std, downward drift
        prices.append(prices[-1] * (1 + change/100))
    
    print(f"Generated {len(prices)} price points")
    print(f"Price range: ${min(prices):.2f} - ${max(prices):.2f}")
    
    # Create detector
    detector = VolatilityRegimeDetector(lookback=20)
    
    # Test feature extraction
    print("\n1. Feature Extraction")
    print("-" * 40)
    features = detector.feature_extractor.extract(prices[-50:])
    for name, value in features.items():
        print(f"  {name}: {value:.4f}")
    
    # Test rule-based prediction (no training)
    print("\n2. Rule-Based Prediction (no ML)")
    print("-" * 40)
    prediction = detector.predict(prices[-50:])
    print(f"  Regime: {prediction.regime}")
    print(f"  Confidence: {prediction.confidence:.2%}")
    print(f"  Strategy: {prediction.recommended_strategy}")
    
    # Test ML training if sklearn available
    if HAS_SKLEARN and HAS_NUMPY:
        print("\n3. ML Training")
        print("-" * 40)
        success = detector.fit(prices)
        print(f"  Training successful: {success}")
        
        if success:
            print("\n4. ML Prediction")
            print("-" * 40)
            
            # Test on different parts of the data
            test_points = [
                (prices[50:100], "Low Vol Period"),
                (prices[150:200], "High Vol Period"),
                (prices[250:300], "Medium Vol Period"),
                (prices[300:350], "Extreme Vol Period"),
            ]
            
            for test_prices, label in test_points:
                pred = detector.predict(test_prices)
                print(f"  {label}: {pred.regime} ({pred.confidence:.1%})")
    else:
        print("\n⚠ scikit-learn or numpy not installed, skipping ML training")
        print("  Install: pip install scikit-learn numpy")
    
    # Test adaptive switcher
    print("\n5. Adaptive Strategy Switcher")
    print("-" * 40)
    switcher = AdaptiveStrategySwitcher(detector, switch_cooldown_minutes=0)  # No cooldown for demo
    
    # Simulate receiving prices over time
    for i in range(0, len(prices) - 50, 50):
        result = switcher.update(prices[i:i+50])
        print(f"  T={i}: {result['current_strategy']} (switched={result['switched']})")
    
    print("\nRegime distribution:")
    dist = switcher.get_strategy_distribution()
    for regime, count in sorted(dist.items()):
        print(f"  {regime}: {count}")
    
    print("\n✓ ML regime detector ready")
