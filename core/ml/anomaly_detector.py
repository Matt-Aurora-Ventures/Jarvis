"""
Anomaly Detector for Trading Patterns.

Detects unusual patterns in trading data:
- Sudden price spikes (>20% move in short time)
- Volume anomalies (10x normal volume)
- Sentiment flips (rapid sentiment reversal)

Uses Isolation Forest or simple statistical methods.

Usage:
    from core.ml.anomaly_detector import AnomalyDetector

    detector = AnomalyDetector()

    result = detector.detect(
        prices=price_history,
        volumes=volume_history
    )

    if result.is_anomaly:
        print(f"Anomaly detected: {result.anomaly_type}")
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
    from sklearn.ensemble import IsolationForest
    from sklearn.neighbors import LocalOutlierFactor
    from sklearn.preprocessing import StandardScaler
    HAS_SKLEARN = True
except ImportError:
    HAS_SKLEARN = False


@dataclass
class AnomalyResult:
    """Result of anomaly detection."""
    is_anomaly: bool
    anomaly_score: float  # 0-100, higher = more anomalous
    anomaly_type: str  # "price_spike", "volume_spike", "sentiment_flip", "normal"
    details: Dict[str, Any] = field(default_factory=dict)
    timestamp: str = ""
    detection_method: str = "statistical"

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "is_anomaly": self.is_anomaly,
            "anomaly_score": round(self.anomaly_score, 2),
            "anomaly_type": self.anomaly_type,
            "details": self.details,
            "timestamp": self.timestamp,
            "detection_method": self.detection_method,
        }


class AnomalyDetector:
    """
    Detect anomalies in trading data.

    Anomaly types:
    1. Price spike: >20% move in 1 minute
    2. Volume spike: >10x normal volume
    3. Sentiment flip: Rapid sentiment reversal

    Methods:
    - Statistical: Z-score based detection
    - Isolation Forest: ML-based outlier detection
    - Local Outlier Factor: Density-based detection
    """

    # Thresholds for anomaly detection
    PRICE_SPIKE_THRESHOLD = 0.20  # 20% move
    VOLUME_SPIKE_THRESHOLD = 10.0  # 10x normal
    Z_SCORE_THRESHOLD = 3.0  # Standard deviations

    def __init__(
        self,
        model_dir: Optional[Path] = None,
        contamination: float = 0.05,  # Expected anomaly rate
    ):
        """
        Initialize anomaly detector.

        Args:
            model_dir: Directory for model storage
            contamination: Expected proportion of anomalies
        """
        self.model_dir = model_dir or Path(__file__).parent.parent.parent / "data" / "ml" / "models"
        self.model_dir.mkdir(parents=True, exist_ok=True)

        self.contamination = contamination

        # ML models
        self._isolation_forest: Optional[Any] = None
        self._scaler: Optional[Any] = None
        self._is_trained = False

        # Load saved model if available
        self._load_model()

    def _load_model(self):
        """Load saved model if available."""
        model_path = self.model_dir / "anomaly_model.pkl"
        if model_path.exists() and HAS_SKLEARN:
            try:
                with open(model_path, "rb") as f:
                    saved = pickle.load(f)
                self._isolation_forest = saved.get("model")
                self._scaler = saved.get("scaler")
                self._is_trained = True
                logger.info("Loaded anomaly detection model")
            except Exception as e:
                logger.warning(f"Failed to load model: {e}")

    def detect(
        self,
        prices: List[float],
        volumes: Optional[List[float]] = None,
        sentiment_history: Optional[List[float]] = None,
    ) -> AnomalyResult:
        """
        Detect anomalies in trading data.

        Args:
            prices: Price history
            volumes: Optional volume history
            sentiment_history: Optional sentiment score history

        Returns:
            AnomalyResult with detection details
        """
        anomalies = []
        max_score = 0

        # Check price anomalies
        price_result = self._detect_price_anomaly(prices)
        if price_result["is_anomaly"]:
            anomalies.append(("price_spike", price_result["score"], price_result))
            max_score = max(max_score, price_result["score"])

        # Check volume anomalies
        if volumes:
            volume_result = self._detect_volume_anomaly(volumes)
            if volume_result["is_anomaly"]:
                anomalies.append(("volume_spike", volume_result["score"], volume_result))
                max_score = max(max_score, volume_result["score"])

        # Check sentiment anomalies
        if sentiment_history and len(sentiment_history) >= 5:
            sentiment_result = self._detect_sentiment_anomaly(sentiment_history)
            if sentiment_result["is_anomaly"]:
                anomalies.append(("sentiment_flip", sentiment_result["score"], sentiment_result))
                max_score = max(max_score, sentiment_result["score"])

        # Use ML if trained
        if self._is_trained and prices:
            ml_result = self._detect_ml(prices, volumes)
            if ml_result["is_anomaly"]:
                anomalies.append(("ml_detected", ml_result["score"], ml_result))
                max_score = max(max_score, ml_result["score"])

        # Combine results
        if anomalies:
            # Sort by score and take the most severe
            anomalies.sort(key=lambda x: x[1], reverse=True)
            top_anomaly = anomalies[0]

            return AnomalyResult(
                is_anomaly=True,
                anomaly_score=top_anomaly[1],
                anomaly_type=top_anomaly[0],
                details=top_anomaly[2],
                detection_method="combined",
            )

        return AnomalyResult(
            is_anomaly=False,
            anomaly_score=max_score,
            anomaly_type="normal",
            details={"checked": ["price", "volume" if volumes else None, "sentiment" if sentiment_history else None]},
            detection_method="statistical",
        )

    def _detect_price_anomaly(self, prices: List[float]) -> Dict[str, Any]:
        """Detect sudden price spikes."""
        if len(prices) < 10:
            return {"is_anomaly": False, "score": 0}

        # Calculate recent price changes
        returns = []
        for i in range(1, len(prices)):
            if prices[i-1] > 0:
                ret = (prices[i] - prices[i-1]) / prices[i-1]
                returns.append(ret)

        if not returns:
            return {"is_anomaly": False, "score": 0}

        # Check last return vs historical
        last_return = returns[-1]
        abs_return = abs(last_return)

        # Z-score approach
        mean_return = sum(abs(r) for r in returns[:-1]) / len(returns[:-1]) if len(returns) > 1 else 0
        std_return = self._std([abs(r) for r in returns[:-1]]) if len(returns) > 1 else 0.01

        if std_return > 0:
            z_score = (abs_return - mean_return) / std_return
        else:
            z_score = abs_return / 0.01  # Fallback

        # Calculate anomaly score (0-100)
        score = min(100, (z_score / self.Z_SCORE_THRESHOLD) * 50 + (abs_return / self.PRICE_SPIKE_THRESHOLD) * 50)

        is_anomaly = abs_return >= self.PRICE_SPIKE_THRESHOLD or z_score >= self.Z_SCORE_THRESHOLD

        return {
            "is_anomaly": is_anomaly,
            "score": score,
            "return": last_return,
            "z_score": z_score,
            "threshold": self.PRICE_SPIKE_THRESHOLD,
        }

    def _detect_volume_anomaly(self, volumes: List[float]) -> Dict[str, Any]:
        """Detect unusual volume spikes."""
        if len(volumes) < 10:
            return {"is_anomaly": False, "score": 0}

        # Calculate average volume (excluding last)
        avg_volume = sum(volumes[:-1]) / len(volumes[:-1]) if len(volumes) > 1 else volumes[-1]
        last_volume = volumes[-1]

        if avg_volume == 0:
            return {"is_anomaly": False, "score": 0}

        # Volume ratio
        volume_ratio = last_volume / avg_volume

        # Z-score
        std_volume = self._std(volumes[:-1]) if len(volumes) > 1 else 1
        z_score = (last_volume - avg_volume) / std_volume if std_volume > 0 else 0

        # Calculate anomaly score
        score = min(100, (volume_ratio / self.VOLUME_SPIKE_THRESHOLD) * 70 + (z_score / self.Z_SCORE_THRESHOLD) * 30)

        is_anomaly = volume_ratio >= self.VOLUME_SPIKE_THRESHOLD or z_score >= self.Z_SCORE_THRESHOLD * 2

        return {
            "is_anomaly": is_anomaly,
            "score": score,
            "volume_ratio": volume_ratio,
            "z_score": z_score,
            "threshold": self.VOLUME_SPIKE_THRESHOLD,
        }

    def _detect_sentiment_anomaly(self, sentiment_history: List[float]) -> Dict[str, Any]:
        """Detect sudden sentiment flips."""
        if len(sentiment_history) < 5:
            return {"is_anomaly": False, "score": 0}

        # Check for sentiment reversal
        recent = sentiment_history[-5:]
        avg_old = sum(recent[:3]) / 3
        avg_new = sum(recent[3:]) / 2 if len(recent) > 3 else recent[-1]

        # Flip detection
        flip_magnitude = abs(avg_new - avg_old)
        direction_change = (avg_old > 0 and avg_new < 0) or (avg_old < 0 and avg_new > 0)

        # Score based on magnitude and direction change
        score = flip_magnitude * (1.5 if direction_change else 1.0)
        score = min(100, score)

        is_anomaly = flip_magnitude > 50 and direction_change

        return {
            "is_anomaly": is_anomaly,
            "score": score,
            "old_sentiment": avg_old,
            "new_sentiment": avg_new,
            "flip_magnitude": flip_magnitude,
            "direction_change": direction_change,
        }

    def _detect_ml(
        self,
        prices: List[float],
        volumes: Optional[List[float]] = None,
    ) -> Dict[str, Any]:
        """ML-based anomaly detection using Isolation Forest."""
        if not HAS_SKLEARN or not HAS_NUMPY or self._isolation_forest is None:
            return {"is_anomaly": False, "score": 0}

        try:
            # Extract features
            features = self._extract_features(prices, volumes)
            if not features:
                return {"is_anomaly": False, "score": 0}

            X = np.array([features])
            if self._scaler:
                X = self._scaler.transform(X)

            # Predict
            prediction = self._isolation_forest.predict(X)[0]
            score = -self._isolation_forest.score_samples(X)[0]  # Higher = more anomalous

            # Normalize score to 0-100
            normalized_score = min(100, max(0, (score + 0.5) * 100))

            is_anomaly = prediction == -1  # -1 = anomaly in sklearn

            return {
                "is_anomaly": is_anomaly,
                "score": normalized_score,
                "raw_score": float(score),
            }

        except Exception as e:
            logger.warning(f"ML detection failed: {e}")
            return {"is_anomaly": False, "score": 0}

    def _extract_features(
        self,
        prices: List[float],
        volumes: Optional[List[float]] = None,
    ) -> List[float]:
        """Extract features for ML detection."""
        if len(prices) < 10:
            return []

        features = []

        # Price features
        returns = [(prices[i] - prices[i-1]) / prices[i-1] if prices[i-1] > 0 else 0
                   for i in range(1, len(prices))]

        features.append(returns[-1] if returns else 0)  # Last return
        features.append(max(abs(r) for r in returns) if returns else 0)  # Max abs return
        features.append(self._std(returns) if returns else 0)  # Return volatility

        # Volume features
        if volumes and len(volumes) >= 10:
            avg_vol = sum(volumes[:-1]) / len(volumes[:-1])
            features.append(volumes[-1] / avg_vol if avg_vol > 0 else 1)
            features.append(self._std(volumes) / avg_vol if avg_vol > 0 else 0)
        else:
            features.extend([1, 0])

        return features

    def train(
        self,
        prices_list: List[List[float]],
        volumes_list: Optional[List[List[float]]] = None,
    ) -> Dict[str, Any]:
        """
        Train anomaly detection model.

        Args:
            prices_list: List of price histories (mostly normal data)
            volumes_list: Optional list of volume histories

        Returns:
            Training result
        """
        if not HAS_SKLEARN or not HAS_NUMPY:
            return {"trained": False, "error": "scikit-learn not installed"}

        try:
            # Extract features from all samples
            X = []
            for i, prices in enumerate(prices_list):
                volumes = volumes_list[i] if volumes_list and i < len(volumes_list) else None
                features = self._extract_features(prices, volumes)
                if features:
                    X.append(features)

            if len(X) < 50:
                return {"trained": False, "error": "Need at least 50 samples"}

            X = np.array(X)

            # Scale features
            self._scaler = StandardScaler()
            X_scaled = self._scaler.fit_transform(X)

            # Train Isolation Forest
            self._isolation_forest = IsolationForest(
                contamination=self.contamination,
                random_state=42,
                n_estimators=100,
            )
            self._isolation_forest.fit(X_scaled)

            self._is_trained = True
            self._save_model()

            logger.info("Trained anomaly detection model")

            return {
                "trained": True,
                "samples": len(X),
                "contamination": self.contamination,
            }

        except Exception as e:
            logger.error(f"Training failed: {e}")
            return {"trained": False, "error": str(e)}

    def _save_model(self):
        """Save trained model."""
        if not self._is_trained:
            return

        model_path = self.model_dir / "anomaly_model.pkl"
        try:
            with open(model_path, "wb") as f:
                pickle.dump({
                    "model": self._isolation_forest,
                    "scaler": self._scaler,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }, f)
            logger.info(f"Saved anomaly model to {model_path}")
        except Exception as e:
            logger.error(f"Failed to save model: {e}")

    def _std(self, values: List[float]) -> float:
        """Calculate standard deviation."""
        if len(values) < 2:
            return 0.0
        mean = sum(values) / len(values)
        variance = sum((x - mean) ** 2 for x in values) / (len(values) - 1)
        return math.sqrt(variance)
