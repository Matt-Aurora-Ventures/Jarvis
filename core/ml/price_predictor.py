"""
Price Direction Predictor for Crypto Trading.

Predicts price direction (up/down/flat) for different time horizons:
- 1h: Short-term prediction
- 4h: Medium-term prediction
- 24h: Daily prediction

Features used:
- Recent price history (momentum, volatility)
- Trading volume patterns
- Social sentiment scores
- On-chain metrics (if available)

Usage:
    from core.ml.price_predictor import PricePredictor

    predictor = PricePredictor()

    result = predictor.predict(
        prices=price_history,
        volumes=volume_history,
        sentiment_score=65
    )

    print(f"Direction: {result.direction}, Confidence: {result.confidence}")
"""

import json
import logging
import math
import pickle
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# Optional ML imports
try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False
    np = None

try:
    from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
    from sklearn.linear_model import LogisticRegression
    from sklearn.preprocessing import StandardScaler
    from sklearn.model_selection import train_test_split
    from sklearn.metrics import accuracy_score, classification_report
    HAS_SKLEARN = True
except ImportError:
    HAS_SKLEARN = False


@dataclass
class PricePrediction:
    """Result of price direction prediction."""
    direction: str  # "up", "down", "flat"
    confidence: float  # 0 to 1
    horizon: str  # "1h", "4h", "24h"
    features_used: Dict[str, float] = field(default_factory=dict)
    timestamp: str = ""
    model_type: str = "rule_based"

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "direction": self.direction,
            "confidence": round(self.confidence, 3),
            "horizon": self.horizon,
            "features": {k: round(v, 4) for k, v in self.features_used.items()},
            "timestamp": self.timestamp,
            "model_type": self.model_type,
        }


class PricePredictor:
    """
    ML-based price direction predictor.

    Uses technical features and sentiment to predict price direction.
    Target accuracy: >60% (better than random for binary classification).
    """

    def __init__(
        self,
        model_dir: Optional[Path] = None,
        lookback: int = 20,
    ):
        """
        Initialize price predictor.

        Args:
            model_dir: Directory for model storage
            lookback: Number of periods for feature calculation
        """
        self.model_dir = model_dir or Path(__file__).parent.parent.parent / "data" / "ml" / "models"
        self.model_dir.mkdir(parents=True, exist_ok=True)

        self.lookback = lookback
        self.horizons = ["1h", "4h", "24h"]

        # ML models (one per horizon)
        self._models: Dict[str, Any] = {}
        self._scalers: Dict[str, Any] = {}
        self._is_trained: Dict[str, bool] = {h: False for h in self.horizons}

        # Feature names for consistency
        self._feature_names = [
            "momentum_5", "momentum_10", "momentum_20",
            "volatility_5", "volatility_10", "volatility_20",
            "trend_slope", "trend_strength",
            "rsi", "bb_position",
            "volume_ratio", "volume_trend",
            "sentiment",
        ]

        # Try to load saved models
        self._load_models()

    def _load_models(self):
        """Load saved models if available."""
        for horizon in self.horizons:
            model_path = self.model_dir / f"price_model_{horizon}.pkl"
            if model_path.exists() and HAS_SKLEARN:
                try:
                    with open(model_path, "rb") as f:
                        saved = pickle.load(f)
                    self._models[horizon] = saved.get("model")
                    self._scalers[horizon] = saved.get("scaler")
                    self._is_trained[horizon] = True
                    logger.info(f"Loaded price model for {horizon}")
                except Exception as e:
                    logger.warning(f"Failed to load model for {horizon}: {e}")

    def extract_features(
        self,
        prices: List[float],
        volumes: Optional[List[float]] = None,
        sentiment_score: float = 0,
    ) -> Dict[str, float]:
        """
        Extract features from price/volume data.

        Args:
            prices: Historical prices (newest last)
            volumes: Optional volume data
            sentiment_score: Social sentiment (-100 to 100)

        Returns:
            Dictionary of feature name -> value
        """
        if len(prices) < self.lookback:
            return {}

        features = {}

        # Momentum features (returns over different periods)
        for period in [5, 10, 20]:
            if len(prices) >= period:
                momentum = (prices[-1] - prices[-period]) / prices[-period] if prices[-period] > 0 else 0
                features[f"momentum_{period}"] = momentum

        # Volatility features (std of returns)
        for period in [5, 10, 20]:
            if len(prices) >= period + 1:
                returns = self._calculate_returns(prices[-period-1:])
                features[f"volatility_{period}"] = self._std(returns) if returns else 0

        # Trend features
        recent = prices[-self.lookback:]
        features["trend_slope"] = self._linear_slope(recent)
        features["trend_strength"] = self._r_squared(recent)

        # RSI
        features["rsi"] = self._calculate_rsi(prices) / 100  # Normalize to 0-1

        # Bollinger Band position
        features["bb_position"] = self._bb_position(prices)

        # Volume features
        if volumes and len(volumes) >= self.lookback:
            recent_vol = volumes[-self.lookback:]
            avg_vol = sum(recent_vol) / len(recent_vol) if recent_vol else 1
            features["volume_ratio"] = recent_vol[-1] / avg_vol if avg_vol > 0 else 1
            features["volume_trend"] = self._linear_slope(recent_vol)
        else:
            features["volume_ratio"] = 1.0
            features["volume_trend"] = 0.0

        # Sentiment
        features["sentiment"] = sentiment_score / 100  # Normalize to -1 to 1

        return features

    def predict(
        self,
        prices: List[float],
        volumes: Optional[List[float]] = None,
        sentiment_score: float = 0,
        horizon: str = "1h",
    ) -> PricePrediction:
        """
        Predict price direction.

        Args:
            prices: Historical prices
            volumes: Optional volume data
            sentiment_score: Social sentiment (-100 to 100)
            horizon: Prediction horizon ("1h", "4h", "24h")

        Returns:
            PricePrediction with direction and confidence
        """
        features = self.extract_features(prices, volumes, sentiment_score)

        if not features:
            return PricePrediction(
                direction="flat",
                confidence=0.0,
                horizon=horizon,
                features_used={},
                model_type="insufficient_data",
            )

        # Use trained model if available
        if self._is_trained.get(horizon) and horizon in self._models:
            return self._predict_ml(features, horizon)

        # Fallback to rule-based
        return self._predict_rule_based(features, horizon)

    def predict_all_horizons(
        self,
        prices: List[float],
        volumes: Optional[List[float]] = None,
        sentiment_score: float = 0,
    ) -> Dict[str, PricePrediction]:
        """Predict for all time horizons."""
        features = self.extract_features(prices, volumes, sentiment_score)

        results = {}
        for horizon in self.horizons:
            results[horizon] = self.predict(prices, volumes, sentiment_score, horizon)

        return results

    def _predict_rule_based(
        self,
        features: Dict[str, float],
        horizon: str,
    ) -> PricePrediction:
        """Rule-based prediction using simple heuristics."""
        momentum = features.get("momentum_10", 0)
        trend = features.get("trend_slope", 0)
        rsi = features.get("rsi", 0.5) * 100  # Convert back to 0-100
        sentiment = features.get("sentiment", 0) * 100  # Convert back to -100 to 100
        volatility = features.get("volatility_10", 0)

        # Scoring system
        score = 0
        factors = 0

        # Momentum (strong predictor)
        if momentum > 0.02:
            score += 2
        elif momentum < -0.02:
            score -= 2
        factors += 2

        # Trend
        if trend > 0.001:
            score += 1
        elif trend < -0.001:
            score -= 1
        factors += 1

        # RSI (contrarian at extremes)
        if rsi > 70:
            score -= 0.5  # Overbought, might reverse
        elif rsi < 30:
            score += 0.5  # Oversold, might bounce
        factors += 0.5

        # Sentiment
        if sentiment > 30:
            score += 1
        elif sentiment < -30:
            score -= 1
        factors += 1

        # Determine direction
        if score > 1:
            direction = "up"
        elif score < -1:
            direction = "down"
        else:
            direction = "flat"

        # Calculate confidence
        confidence = min(0.9, 0.4 + abs(score) / (factors * 2))

        # Adjust confidence for horizon (longer = less confident)
        horizon_factor = {"1h": 1.0, "4h": 0.9, "24h": 0.8}.get(horizon, 0.8)
        confidence *= horizon_factor

        return PricePrediction(
            direction=direction,
            confidence=confidence,
            horizon=horizon,
            features_used=features,
            model_type="rule_based",
        )

    def _predict_ml(
        self,
        features: Dict[str, float],
        horizon: str,
    ) -> PricePrediction:
        """ML-based prediction."""
        if not HAS_SKLEARN or not HAS_NUMPY:
            return self._predict_rule_based(features, horizon)

        try:
            model = self._models.get(horizon)
            scaler = self._scalers.get(horizon)

            if model is None or scaler is None:
                return self._predict_rule_based(features, horizon)

            # Prepare feature vector
            X = np.array([[features.get(f, 0) for f in self._feature_names]])
            X_scaled = scaler.transform(X)

            # Predict
            prediction = model.predict(X_scaled)[0]
            probas = model.predict_proba(X_scaled)[0]

            # Map prediction to direction
            direction_map = {0: "down", 1: "flat", 2: "up"}
            direction = direction_map.get(prediction, "flat")

            confidence = max(probas)

            return PricePrediction(
                direction=direction,
                confidence=confidence,
                horizon=horizon,
                features_used=features,
                model_type="random_forest",
            )

        except Exception as e:
            logger.warning(f"ML prediction failed: {e}")
            return self._predict_rule_based(features, horizon)

    def train(
        self,
        prices_list: List[List[float]],
        labels: List[str],
        volumes_list: Optional[List[List[float]]] = None,
        sentiment_scores: Optional[List[float]] = None,
        horizon: str = "1h",
    ) -> Dict[str, Any]:
        """
        Train price prediction model.

        Args:
            prices_list: List of price histories
            labels: List of labels ("up", "down", "flat")
            volumes_list: Optional list of volume histories
            sentiment_scores: Optional sentiment scores
            horizon: Time horizon to train for

        Returns:
            Training metrics
        """
        if not HAS_SKLEARN or not HAS_NUMPY:
            return {"accuracy": 0, "error": "scikit-learn not installed"}

        if len(prices_list) < 20:
            return {"accuracy": 0, "error": "Need at least 20 samples"}

        try:
            # Extract features for all samples
            X = []
            valid_labels = []

            for i, prices in enumerate(prices_list):
                volumes = volumes_list[i] if volumes_list and i < len(volumes_list) else None
                sentiment = sentiment_scores[i] if sentiment_scores and i < len(sentiment_scores) else 0

                features = self.extract_features(prices, volumes, sentiment)
                if features:
                    feature_vec = [features.get(f, 0) for f in self._feature_names]
                    X.append(feature_vec)
                    valid_labels.append(labels[i])

            if len(X) < 20:
                return {"accuracy": 0, "error": "Insufficient valid samples"}

            X = np.array(X)

            # Convert labels to numeric
            label_map = {"down": 0, "flat": 1, "up": 2}
            y = np.array([label_map.get(l, 1) for l in valid_labels])

            # Split data
            X_train, X_test, y_train, y_test = train_test_split(
                X, y, test_size=0.2, random_state=42
            )

            # Scale features
            scaler = StandardScaler()
            X_train_scaled = scaler.fit_transform(X_train)
            X_test_scaled = scaler.transform(X_test)

            # Train model
            model = RandomForestClassifier(
                n_estimators=100,
                max_depth=10,
                random_state=42,
            )
            model.fit(X_train_scaled, y_train)

            # Evaluate
            y_pred = model.predict(X_test_scaled)
            accuracy = accuracy_score(y_test, y_pred)

            # Save model
            self._models[horizon] = model
            self._scalers[horizon] = scaler
            self._is_trained[horizon] = True
            self._save_model(horizon)

            logger.info(f"Trained price model for {horizon}: accuracy={accuracy:.2%}")

            return {
                "accuracy": accuracy,
                "train_samples": len(X_train),
                "test_samples": len(X_test),
                "horizon": horizon,
            }

        except Exception as e:
            logger.error(f"Training failed: {e}")
            return {"accuracy": 0, "error": str(e)}

    def _save_model(self, horizon: str):
        """Save model for a specific horizon."""
        model_path = self.model_dir / f"price_model_{horizon}.pkl"
        try:
            with open(model_path, "wb") as f:
                pickle.dump({
                    "model": self._models.get(horizon),
                    "scaler": self._scalers.get(horizon),
                    "feature_names": self._feature_names,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }, f)
            logger.info(f"Saved price model to {model_path}")
        except Exception as e:
            logger.error(f"Failed to save model: {e}")

    # Feature calculation helpers
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

    def _linear_slope(self, values: List[float]) -> float:
        """Calculate normalized linear regression slope."""
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
        return slope / y_mean if y_mean > 0 else 0

    def _r_squared(self, values: List[float]) -> float:
        """Calculate R-squared (trend strength)."""
        if len(values) < 2:
            return 0.0

        n = len(values)
        y_mean = sum(values) / n

        ss_tot = sum((y - y_mean) ** 2 for y in values)
        if ss_tot == 0:
            return 0.0

        x_mean = (n - 1) / 2
        numerator = sum((i - x_mean) * (values[i] - y_mean) for i in range(n))
        denominator = sum((i - x_mean) ** 2 for i in range(n))

        if denominator == 0:
            return 0.0

        slope = numerator / denominator
        intercept = y_mean - slope * x_mean

        ss_res = sum((values[i] - (slope * i + intercept)) ** 2 for i in range(n))
        r_squared = 1 - (ss_res / ss_tot)

        return max(0, r_squared)

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
        """Position within Bollinger Bands (-1 to 1)."""
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
