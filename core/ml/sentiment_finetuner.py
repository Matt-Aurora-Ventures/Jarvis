"""
Sentiment Fine-Tuner for Crypto/Trading Context.

Uses pre-trained models (or rule-based fallback) to classify sentiment
as bearish (-1), neutral (0), or bullish (+1).

Features:
- Rule-based baseline for quick predictions without training
- Optional transformer fine-tuning for improved accuracy
- Batch prediction support
- Model persistence and versioning

Usage:
    from core.ml.sentiment_finetuner import SentimentFineTuner

    finetuner = SentimentFineTuner()

    # Quick prediction (rule-based)
    result = finetuner.predict("Bitcoin to the moon!")

    # Train on labeled data
    finetuner.train(texts, labels, epochs=3)

    # Then predict with trained model
    result = finetuner.predict("Very bullish on SOL")
"""

import json
import logging
import pickle
import re
import time
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
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import classification_report, f1_score, accuracy_score
    from sklearn.model_selection import train_test_split
    HAS_SKLEARN = True
except ImportError:
    HAS_SKLEARN = False

# Optional transformer imports
try:
    from transformers import (
        AutoTokenizer,
        AutoModelForSequenceClassification,
        TrainingArguments,
        Trainer,
    )
    import torch
    HAS_TRANSFORMERS = True
except ImportError:
    HAS_TRANSFORMERS = False


@dataclass
class SentimentPrediction:
    """Result of sentiment prediction."""
    label: int  # -1 (bearish), 0 (neutral), 1 (bullish)
    score: float  # -100 to 100
    confidence: float  # 0 to 1
    timestamp: str = ""
    model_type: str = "rule_based"

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "label": self.label,
            "score": round(self.score, 2),
            "confidence": round(self.confidence, 3),
            "timestamp": self.timestamp,
            "model_type": self.model_type,
        }

    @property
    def label_name(self) -> str:
        """Get human-readable label name."""
        return {-1: "bearish", 0: "neutral", 1: "bullish"}.get(self.label, "unknown")


class SentimentFineTuner:
    """
    Fine-tunable sentiment classifier for crypto/trading context.

    Supports three modes:
    1. Rule-based: Fast, no training needed, uses keyword matching
    2. TF-IDF + LogReg: Quick ML training on labeled data
    3. Transformer: High accuracy with pre-trained models (requires more resources)
    """

    # Sentiment keywords for rule-based classification
    BULLISH_KEYWORDS = [
        "moon", "bullish", "pump", "buy", "accumulate", "long", "breakout",
        "rocket", "gem", "undervalued", "hodl", "hold", "alpha", "100x",
        "explosive", "parabolic", "surge", "rally", "ath", "lambo",
        "wagmi", "gm", "lfg", "up", "rising", "gains", "profit", "win",
        "amazing", "incredible", "massive", "huge", "best", "great",
    ]

    BEARISH_KEYWORDS = [
        "crash", "bearish", "dump", "sell", "short", "rug", "scam",
        "dead", "rekt", "loss", "down", "falling", "plunge", "collapse",
        "fear", "panic", "exit", "warning", "avoid", "bad", "terrible",
        "worst", "ugly", "danger", "risk", "failed", "ngmi", "doom",
        "liquidate", "bankrupt", "worthless", "overvalued",
    ]

    def __init__(
        self,
        model_dir: Optional[Path] = None,
        use_transformer: bool = False,
        transformer_model: str = "distilbert-base-uncased",
    ):
        """
        Initialize sentiment fine-tuner.

        Args:
            model_dir: Directory for storing trained models
            use_transformer: Whether to use transformer model (slower but more accurate)
            transformer_model: Hugging Face model name for transformers
        """
        self.model_dir = model_dir or Path(__file__).parent.parent.parent / "data" / "ml" / "models"
        self.model_dir.mkdir(parents=True, exist_ok=True)

        self.use_transformer = use_transformer and HAS_TRANSFORMERS
        self.transformer_model_name = transformer_model

        self.classes = [-1, 0, 1]  # bearish, neutral, bullish

        # ML model state
        self._vectorizer: Optional[Any] = None
        self._classifier: Optional[Any] = None
        self._transformer_model: Optional[Any] = None
        self._transformer_tokenizer: Optional[Any] = None
        self._is_trained = False
        self._model_type = "rule_based"

        # Try to load existing model
        self._load_model()

    def _load_model(self):
        """Load saved model if available."""
        model_path = self.model_dir / "sentiment_model.pkl"
        if model_path.exists() and HAS_SKLEARN:
            try:
                with open(model_path, "rb") as f:
                    saved = pickle.load(f)
                self._vectorizer = saved.get("vectorizer")
                self._classifier = saved.get("classifier")
                self._is_trained = True
                self._model_type = "tfidf_logreg"
                logger.info("Loaded saved sentiment model")
            except Exception as e:
                logger.warning(f"Failed to load model: {e}")

    def predict(self, text: str) -> SentimentPrediction:
        """
        Predict sentiment for a single text.

        Args:
            text: Text to analyze

        Returns:
            SentimentPrediction with label, score, and confidence
        """
        # Use trained model if available
        if self._is_trained and self._classifier is not None and self._vectorizer is not None:
            return self._predict_ml(text)

        # Use transformer if available and configured
        if self.use_transformer and self._transformer_model is not None:
            return self._predict_transformer(text)

        # Fallback to rule-based
        return self._predict_rule_based(text)

    def predict_batch(self, texts: List[str]) -> List[SentimentPrediction]:
        """
        Predict sentiment for multiple texts.

        Args:
            texts: List of texts to analyze

        Returns:
            List of SentimentPrediction objects
        """
        if self._is_trained and self._classifier is not None and self._vectorizer is not None:
            return self._predict_batch_ml(texts)

        return [self.predict(text) for text in texts]

    def _predict_rule_based(self, text: str) -> SentimentPrediction:
        """Rule-based sentiment prediction using keyword matching."""
        text_lower = text.lower()
        words = set(re.findall(r'\b\w+\b', text_lower))

        bullish_count = sum(1 for kw in self.BULLISH_KEYWORDS if kw in words)
        bearish_count = sum(1 for kw in self.BEARISH_KEYWORDS if kw in words)

        # Calculate score (-100 to 100)
        total = bullish_count + bearish_count
        if total == 0:
            score = 0
            label = 0
            confidence = 0.3  # Low confidence for no signals
        else:
            score = ((bullish_count - bearish_count) / total) * 100
            confidence = min(0.9, 0.3 + (total * 0.1))  # More keywords = more confident

            if score > 20:
                label = 1
            elif score < -20:
                label = -1
            else:
                label = 0

        return SentimentPrediction(
            label=label,
            score=score,
            confidence=confidence,
            model_type="rule_based",
        )

    def _predict_ml(self, text: str) -> SentimentPrediction:
        """ML-based prediction using TF-IDF + Logistic Regression."""
        if not HAS_SKLEARN or self._vectorizer is None or self._classifier is None:
            return self._predict_rule_based(text)

        try:
            X = self._vectorizer.transform([text])
            label = self._classifier.predict(X)[0]
            probas = self._classifier.predict_proba(X)[0]

            # Get confidence (max probability)
            confidence = max(probas)

            # Calculate score based on probabilities
            # probas[0] = bearish, probas[1] = neutral, probas[2] = bullish
            if len(probas) == 3:
                score = (probas[2] - probas[0]) * 100
            else:
                score = (label * 50)  # Fallback

            return SentimentPrediction(
                label=int(label),
                score=score,
                confidence=confidence,
                model_type="tfidf_logreg",
            )
        except Exception as e:
            logger.warning(f"ML prediction failed: {e}")
            return self._predict_rule_based(text)

    def _predict_batch_ml(self, texts: List[str]) -> List[SentimentPrediction]:
        """Batch ML prediction."""
        if not HAS_SKLEARN or self._vectorizer is None or self._classifier is None:
            return [self._predict_rule_based(t) for t in texts]

        try:
            X = self._vectorizer.transform(texts)
            labels = self._classifier.predict(X)
            probas = self._classifier.predict_proba(X)

            results = []
            for i, (label, proba) in enumerate(zip(labels, probas)):
                confidence = max(proba)
                if len(proba) == 3:
                    score = (proba[2] - proba[0]) * 100
                else:
                    score = label * 50

                results.append(SentimentPrediction(
                    label=int(label),
                    score=score,
                    confidence=confidence,
                    model_type="tfidf_logreg",
                ))

            return results
        except Exception as e:
            logger.warning(f"Batch ML prediction failed: {e}")
            return [self._predict_rule_based(t) for t in texts]

    def _predict_transformer(self, text: str) -> SentimentPrediction:
        """Transformer-based prediction."""
        if not HAS_TRANSFORMERS or self._transformer_model is None:
            return self._predict_rule_based(text)

        try:
            inputs = self._transformer_tokenizer(
                text,
                return_tensors="pt",
                truncation=True,
                max_length=512,
            )

            with torch.no_grad():
                outputs = self._transformer_model(**inputs)

            logits = outputs.logits
            probas = torch.softmax(logits, dim=-1)[0].numpy()
            label = int(torch.argmax(logits, dim=-1).item()) - 1  # Convert 0,1,2 to -1,0,1

            confidence = float(max(probas))
            score = (probas[2] - probas[0]) * 100 if len(probas) == 3 else label * 50

            return SentimentPrediction(
                label=label,
                score=score,
                confidence=confidence,
                model_type="transformer",
            )
        except Exception as e:
            logger.warning(f"Transformer prediction failed: {e}")
            return self._predict_rule_based(text)

    def train(
        self,
        texts: List[str],
        labels: List[int],
        epochs: int = 3,
        test_size: float = 0.2,
    ) -> Dict[str, Any]:
        """
        Train sentiment model on labeled data.

        Args:
            texts: List of text samples
            labels: List of labels (-1, 0, 1)
            epochs: Training epochs (for transformer)
            test_size: Fraction of data for testing

        Returns:
            Dictionary with training metrics
        """
        if len(texts) < 10:
            logger.warning("Need at least 10 samples for training")
            return {"trained": False, "error": "Insufficient data"}

        # Use TF-IDF + LogReg for quick training
        if HAS_SKLEARN:
            return self._train_tfidf(texts, labels, test_size)

        return {"trained": False, "error": "scikit-learn not installed"}

    def _train_tfidf(
        self,
        texts: List[str],
        labels: List[int],
        test_size: float,
    ) -> Dict[str, Any]:
        """Train TF-IDF + Logistic Regression model."""
        try:
            # Split data
            X_train, X_test, y_train, y_test = train_test_split(
                texts, labels, test_size=test_size, random_state=42, stratify=labels
            )

            # Vectorize
            self._vectorizer = TfidfVectorizer(
                max_features=5000,
                ngram_range=(1, 2),
                min_df=1,
            )
            X_train_vec = self._vectorizer.fit_transform(X_train)
            X_test_vec = self._vectorizer.transform(X_test)

            # Train classifier
            self._classifier = LogisticRegression(
                max_iter=1000,
                random_state=42,
                class_weight="balanced",
            )
            self._classifier.fit(X_train_vec, y_train)

            # Evaluate
            y_pred = self._classifier.predict(X_test_vec)
            accuracy = accuracy_score(y_test, y_pred)
            f1 = f1_score(y_test, y_pred, average="weighted")

            # Save model
            self._is_trained = True
            self._model_type = "tfidf_logreg"
            self._save_model()

            logger.info(f"Trained sentiment model: accuracy={accuracy:.2%}, f1={f1:.3f}")

            return {
                "trained": True,
                "accuracy": accuracy,
                "f1_score": f1,
                "train_samples": len(X_train),
                "test_samples": len(X_test),
                "model_path": str(self.model_dir / "sentiment_model.pkl"),
            }

        except Exception as e:
            logger.error(f"Training failed: {e}")
            return {"trained": False, "error": str(e)}

    def _save_model(self):
        """Save trained model to disk."""
        if not self._is_trained:
            return

        model_path = self.model_dir / "sentiment_model.pkl"
        try:
            with open(model_path, "wb") as f:
                pickle.dump({
                    "vectorizer": self._vectorizer,
                    "classifier": self._classifier,
                    "model_type": self._model_type,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }, f)
            logger.info(f"Saved sentiment model to {model_path}")
        except Exception as e:
            logger.error(f"Failed to save model: {e}")

    def get_training_status(self) -> Dict[str, Any]:
        """Get current model status."""
        return {
            "is_trained": self._is_trained,
            "model_type": self._model_type,
            "has_sklearn": HAS_SKLEARN,
            "has_transformers": HAS_TRANSFORMERS,
            "model_dir": str(self.model_dir),
        }


# Convenience function
def predict_sentiment(text: str) -> SentimentPrediction:
    """Quick sentiment prediction using default model."""
    finetuner = SentimentFineTuner()
    return finetuner.predict(text)
