"""
Win Rate Predictor for Trade Profitability.

Predicts the probability of a trade being profitable based on:
- Entry signal type
- Token being traded
- Position size
- Risk level
- Historical performance

Usage:
    from core.ml.win_rate_predictor import WinRatePredictor

    predictor = WinRatePredictor()

    prediction = predictor.predict(
        token="SOL",
        entry_signal="bullish",
        position_size=0.05,
        risk_level="medium"
    )

    print(f"Win probability: {prediction.win_probability}%")
"""

import json
import logging
import pickle
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from core.security.safe_pickle import safe_pickle_load

logger = logging.getLogger(__name__)


# Optional ML imports
try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False
    np = None

try:
    from sklearn.linear_model import LogisticRegression
    from sklearn.preprocessing import StandardScaler, LabelEncoder
    from sklearn.model_selection import train_test_split
    from sklearn.metrics import accuracy_score, brier_score_loss
    from sklearn.calibration import CalibratedClassifierCV
    HAS_SKLEARN = True
except ImportError:
    HAS_SKLEARN = False


@dataclass
class WinRatePrediction:
    """Result of win rate prediction."""
    win_probability: float  # 0-100%
    confidence: float  # 0-1, how confident the model is
    factors: Dict[str, float] = field(default_factory=dict)  # Contributing factors
    timestamp: str = ""
    model_type: str = "historical"

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "win_probability": round(self.win_probability, 2),
            "confidence": round(self.confidence, 3),
            "factors": {k: round(v, 3) for k, v in self.factors.items()},
            "timestamp": self.timestamp,
            "model_type": self.model_type,
        }


class WinRatePredictor:
    """
    Predict probability of trade profitability.

    Uses historical trade data to learn which factors correlate with winning trades.
    Supports both rule-based and ML-based prediction.
    """

    # Default win rates by signal type (used when no training data)
    DEFAULT_WIN_RATES = {
        "bullish": 0.55,
        "bearish": 0.45,
        "breakout": 0.50,
        "dip": 0.52,
        "momentum": 0.48,
        "reversal": 0.45,
        "default": 0.50,
    }

    # Risk level adjustments
    RISK_ADJUSTMENTS = {
        "low": 1.05,  # Low risk = slightly better odds
        "medium": 1.00,
        "high": 0.95,  # High risk = slightly worse odds
        "very_high": 0.90,
    }

    def __init__(
        self,
        model_dir: Optional[Path] = None,
    ):
        """
        Initialize win rate predictor.

        Args:
            model_dir: Directory for model storage
        """
        self.model_dir = model_dir or Path(__file__).parent.parent.parent / "data" / "ml" / "models"
        self.model_dir.mkdir(parents=True, exist_ok=True)

        # ML model state
        self._model: Optional[Any] = None
        self._scaler: Optional[Any] = None
        self._label_encoders: Dict[str, Any] = {}
        self._is_trained = False

        # Historical statistics (fallback)
        self._historical_stats: Dict[str, Dict[str, Any]] = defaultdict(lambda: {"wins": 0, "total": 0})

        # Load saved model
        self._load_model()

    def _load_model(self):
        """Load saved model if available."""
        model_path = self.model_dir / "win_rate_model.pkl"
        if model_path.exists() and HAS_SKLEARN:
            try:
                # Use safe pickle loader to prevent code execution attacks
                saved = safe_pickle_load(model_path)
                self._model = saved.get("model")
                self._scaler = saved.get("scaler")
                self._label_encoders = saved.get("encoders", {})
                self._historical_stats = saved.get("stats", self._historical_stats)
                self._is_trained = saved.get("is_trained", False)
                logger.info("Loaded win rate model")
            except Exception as e:
                logger.warning(f"Failed to load model: {e}")

    def predict(
        self,
        token: str,
        entry_signal: str,
        position_size: float = 0.05,
        risk_level: str = "medium",
        additional_features: Optional[Dict[str, float]] = None,
    ) -> WinRatePrediction:
        """
        Predict win probability for a trade.

        Args:
            token: Token being traded (e.g., "SOL", "BTC")
            entry_signal: Type of entry signal
            position_size: Position size as fraction of portfolio
            risk_level: Risk level ("low", "medium", "high", "very_high")
            additional_features: Optional extra features

        Returns:
            WinRatePrediction with probability and factors
        """
        if self._is_trained and self._model is not None:
            return self._predict_ml(token, entry_signal, position_size, risk_level, additional_features)

        return self._predict_rule_based(token, entry_signal, position_size, risk_level)

    def _predict_rule_based(
        self,
        token: str,
        entry_signal: str,
        position_size: float,
        risk_level: str,
    ) -> WinRatePrediction:
        """Rule-based prediction using historical averages."""
        factors = {}

        # Base win rate from signal type
        base_rate = self.DEFAULT_WIN_RATES.get(entry_signal.lower(), self.DEFAULT_WIN_RATES["default"])
        factors["signal_base"] = base_rate

        # Risk adjustment
        risk_adj = self.RISK_ADJUSTMENTS.get(risk_level.lower(), 1.0)
        adjusted_rate = base_rate * risk_adj
        factors["risk_adjustment"] = risk_adj

        # Position size adjustment (larger positions have slightly lower win rates due to slippage)
        size_adj = 1.0 - (position_size - 0.05) * 0.5  # Penalty for sizes > 5%
        size_adj = max(0.8, min(1.1, size_adj))
        adjusted_rate *= size_adj
        factors["size_adjustment"] = size_adj

        # Historical stats for token/signal combination
        key = f"{token.upper()}_{entry_signal.lower()}"
        stats = self._historical_stats.get(key, {"wins": 0, "total": 0})
        if stats["total"] >= 10:
            historical_rate = stats["wins"] / stats["total"]
            # Blend with base rate
            adjusted_rate = 0.7 * adjusted_rate + 0.3 * historical_rate
            factors["historical_rate"] = historical_rate

        # Clamp to valid range
        win_probability = max(20, min(80, adjusted_rate * 100))

        # Confidence based on data availability
        confidence = 0.4  # Low confidence for rule-based
        if stats["total"] >= 30:
            confidence = 0.6
        elif stats["total"] >= 10:
            confidence = 0.5

        return WinRatePrediction(
            win_probability=win_probability,
            confidence=confidence,
            factors=factors,
            model_type="rule_based",
        )

    def _predict_ml(
        self,
        token: str,
        entry_signal: str,
        position_size: float,
        risk_level: str,
        additional_features: Optional[Dict[str, float]] = None,
    ) -> WinRatePrediction:
        """ML-based prediction using trained model."""
        if not HAS_SKLEARN or not HAS_NUMPY:
            return self._predict_rule_based(token, entry_signal, position_size, risk_level)

        try:
            # Encode categorical features
            token_encoded = self._safe_encode("token", token.upper())
            signal_encoded = self._safe_encode("signal", entry_signal.lower())
            risk_encoded = self._safe_encode("risk", risk_level.lower())

            # Build feature vector
            features = [token_encoded, signal_encoded, position_size, risk_encoded]

            # Add additional features if provided
            if additional_features:
                for key in sorted(additional_features.keys()):
                    features.append(additional_features[key])

            X = np.array([features])

            # Scale if scaler available
            if self._scaler:
                X = self._scaler.transform(X)

            # Predict probability
            probability = self._model.predict_proba(X)[0][1]  # Probability of class 1 (win)
            win_probability = probability * 100

            # Get feature importances if available
            factors = {}
            if hasattr(self._model, "coef_"):
                coef = self._model.coef_[0]
                factors = {
                    "token": float(coef[0]) if len(coef) > 0 else 0,
                    "signal": float(coef[1]) if len(coef) > 1 else 0,
                    "position_size": float(coef[2]) if len(coef) > 2 else 0,
                    "risk_level": float(coef[3]) if len(coef) > 3 else 0,
                }

            return WinRatePrediction(
                win_probability=win_probability,
                confidence=0.7,  # Higher confidence for ML
                factors=factors,
                model_type="logistic_regression",
            )

        except Exception as e:
            logger.warning(f"ML prediction failed: {e}")
            return self._predict_rule_based(token, entry_signal, position_size, risk_level)

    def _safe_encode(self, encoder_name: str, value: str) -> int:
        """Safely encode a categorical value."""
        if encoder_name not in self._label_encoders:
            return 0

        encoder = self._label_encoders[encoder_name]
        try:
            return encoder.transform([value])[0]
        except ValueError:
            # Unknown category
            return 0

    def train(
        self,
        trade_data: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Train win rate predictor on historical trade data.

        Args:
            trade_data: List of trade records with fields:
                - token: Token traded
                - signal: Entry signal type
                - position_size: Position size (optional)
                - risk_level: Risk level (optional)
                - won: Boolean - whether trade was profitable

        Returns:
            Training metrics
        """
        if len(trade_data) < 10:
            # Update historical stats even with few samples
            self._update_historical_stats(trade_data)
            return {"trained": False, "error": "Need at least 10 trades", "stats_updated": True}

        # Update historical stats
        self._update_historical_stats(trade_data)

        if not HAS_SKLEARN or not HAS_NUMPY:
            return {"trained": False, "error": "scikit-learn not installed", "stats_updated": True}

        try:
            # Extract features and labels
            tokens = [t.get("token", "UNKNOWN").upper() for t in trade_data]
            signals = [t.get("signal", "default").lower() for t in trade_data]
            sizes = [t.get("position_size", 0.05) for t in trade_data]
            risks = [t.get("risk_level", "medium").lower() for t in trade_data]
            labels = [1 if t.get("won", False) else 0 for t in trade_data]

            # Encode categorical features
            self._label_encoders["token"] = LabelEncoder()
            self._label_encoders["signal"] = LabelEncoder()
            self._label_encoders["risk"] = LabelEncoder()

            tokens_encoded = self._label_encoders["token"].fit_transform(tokens)
            signals_encoded = self._label_encoders["signal"].fit_transform(signals)
            risks_encoded = self._label_encoders["risk"].fit_transform(risks)

            # Build feature matrix
            X = np.column_stack([tokens_encoded, signals_encoded, sizes, risks_encoded])
            y = np.array(labels)

            # Split data
            X_train, X_test, y_train, y_test = train_test_split(
                X, y, test_size=0.2, random_state=42
            )

            # Scale features
            self._scaler = StandardScaler()
            X_train_scaled = self._scaler.fit_transform(X_train)
            X_test_scaled = self._scaler.transform(X_test)

            # Train calibrated logistic regression
            base_model = LogisticRegression(max_iter=1000, random_state=42)
            self._model = CalibratedClassifierCV(base_model, cv=3, method='sigmoid')
            self._model.fit(X_train_scaled, y_train)

            # Evaluate
            y_pred = self._model.predict(X_test_scaled)
            y_prob = self._model.predict_proba(X_test_scaled)[:, 1]

            accuracy = accuracy_score(y_test, y_pred)
            brier = brier_score_loss(y_test, y_prob)

            self._is_trained = True
            self._save_model()

            logger.info(f"Trained win rate model: accuracy={accuracy:.2%}, brier={brier:.4f}")

            return {
                "trained": True,
                "accuracy": accuracy,
                "brier_score": brier,
                "train_samples": len(X_train),
                "test_samples": len(X_test),
            }

        except Exception as e:
            logger.error(f"Training failed: {e}")
            return {"trained": False, "error": str(e)}

    def _update_historical_stats(self, trade_data: List[Dict[str, Any]]):
        """Update historical statistics from trade data."""
        for trade in trade_data:
            token = trade.get("token", "UNKNOWN").upper()
            signal = trade.get("signal", "default").lower()
            won = trade.get("won", False)

            key = f"{token}_{signal}"
            if key not in self._historical_stats:
                self._historical_stats[key] = {"wins": 0, "total": 0}

            self._historical_stats[key]["total"] += 1
            if won:
                self._historical_stats[key]["wins"] += 1

    def get_calibration(self) -> Dict[str, Any]:
        """Get model calibration information."""
        if not self._is_trained:
            return {
                "calibrated": False,
                "expected_accuracy": 0.5,
                "calibration_error": None,
                "message": "Model not trained - using rule-based predictions",
            }

        return {
            "calibrated": True,
            "expected_accuracy": 0.55,  # Target accuracy
            "calibration_error": 0.05,  # Estimated
            "message": "Model trained with calibrated probabilities",
        }

    def _save_model(self):
        """Save trained model."""
        model_path = self.model_dir / "win_rate_model.pkl"
        try:
            with open(model_path, "wb") as f:
                pickle.dump({
                    "model": self._model,
                    "scaler": self._scaler,
                    "encoders": self._label_encoders,
                    "stats": dict(self._historical_stats),
                    "is_trained": self._is_trained,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }, f)
            logger.info(f"Saved win rate model to {model_path}")
        except Exception as e:
            logger.error(f"Failed to save model: {e}")

    def record_trade(
        self,
        token: str,
        entry_signal: str,
        won: bool,
        position_size: float = 0.05,
        risk_level: str = "medium",
    ):
        """
        Record a single trade outcome for future training.

        Args:
            token: Token traded
            entry_signal: Entry signal type
            won: Whether trade was profitable
            position_size: Position size
            risk_level: Risk level
        """
        trade = {
            "token": token,
            "signal": entry_signal,
            "position_size": position_size,
            "risk_level": risk_level,
            "won": won,
        }
        self._update_historical_stats([trade])
        self._save_model()  # Save updated stats
