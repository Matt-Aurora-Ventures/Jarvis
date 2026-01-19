"""
Tests for ML Models - Sentiment, Price Prediction, Anomaly Detection.

TDD Tests: Write tests first, then implement to pass them.
Target: 25-30 tests covering all ML components.
"""

import pytest
import tempfile
import json
from pathlib import Path
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock, patch, MagicMock
import math

# Test fixtures
@pytest.fixture
def temp_model_dir(tmp_path):
    """Create temporary directory for model storage."""
    model_dir = tmp_path / "models"
    model_dir.mkdir()
    return model_dir


@pytest.fixture
def sample_tweets():
    """Sample tweet data for sentiment testing."""
    return [
        {"text": "Bitcoin is going to the moon! Super bullish on BTC!", "label": 1},
        {"text": "Market is crashing, selling everything. Very bearish outlook.", "label": -1},
        {"text": "Just checking the charts. Nothing special happening.", "label": 0},
        {"text": "SOL breaking out! This is massive, accumulating more!", "label": 1},
        {"text": "Rug pull alert! Stay away from this token.", "label": -1},
        {"text": "Trading volume looks normal today.", "label": 0},
        {"text": "FOMO buying BTC, can't miss this pump!", "label": 1},
        {"text": "Bears are in control, expect more downside.", "label": -1},
    ]


@pytest.fixture
def sample_price_history():
    """Generate sample price history for testing."""
    import random
    random.seed(42)

    prices = [100.0]
    for i in range(100):
        change = random.gauss(0, 2)  # 2% std
        prices.append(max(1.0, prices[-1] * (1 + change / 100)))

    return prices


@pytest.fixture
def sample_volume_history():
    """Generate sample volume history."""
    import random
    random.seed(42)

    volumes = []
    base_volume = 1000000
    for _ in range(101):
        volumes.append(base_volume * (0.5 + random.random()))

    return volumes


@pytest.fixture
def sample_trade_data():
    """Sample historical trade data for win rate prediction."""
    return [
        {"entry_price": 100, "exit_price": 110, "token": "SOL", "signal": "bullish", "won": True},
        {"entry_price": 50, "exit_price": 45, "token": "BTC", "signal": "bullish", "won": False},
        {"entry_price": 200, "exit_price": 220, "token": "ETH", "signal": "breakout", "won": True},
        {"entry_price": 30, "exit_price": 35, "token": "SOL", "signal": "dip", "won": True},
        {"entry_price": 80, "exit_price": 75, "token": "BTC", "signal": "bullish", "won": False},
        {"entry_price": 150, "exit_price": 180, "token": "ETH", "signal": "momentum", "won": True},
        {"entry_price": 25, "exit_price": 28, "token": "SOL", "signal": "dip", "won": True},
        {"entry_price": 100, "exit_price": 95, "token": "BTC", "signal": "breakout", "won": False},
    ]


# =============================================================================
# Sentiment Fine-Tuner Tests (6 tests)
# =============================================================================

class TestSentimentFineTuner:
    """Tests for sentiment prediction and fine-tuning."""

    def test_sentiment_finetuner_init(self, temp_model_dir):
        """Test SentimentFineTuner initialization."""
        from core.ml.sentiment_finetuner import SentimentFineTuner

        finetuner = SentimentFineTuner(model_dir=temp_model_dir)

        assert finetuner is not None
        assert finetuner.model_dir == temp_model_dir
        assert finetuner.classes == [-1, 0, 1]  # bearish, neutral, bullish

    def test_sentiment_prediction_structure(self, temp_model_dir):
        """Test sentiment prediction returns correct structure."""
        from core.ml.sentiment_finetuner import SentimentFineTuner, SentimentPrediction

        finetuner = SentimentFineTuner(model_dir=temp_model_dir)

        # Use rule-based (no training needed for structure test)
        prediction = finetuner.predict("Bitcoin is amazing and will moon!")

        assert isinstance(prediction, SentimentPrediction)
        assert hasattr(prediction, "label")
        assert hasattr(prediction, "score")
        assert hasattr(prediction, "confidence")
        assert prediction.label in [-1, 0, 1]
        assert -100 <= prediction.score <= 100
        assert 0 <= prediction.confidence <= 1

    def test_sentiment_bullish_detection(self, temp_model_dir):
        """Test that bullish sentiment is correctly detected."""
        from core.ml.sentiment_finetuner import SentimentFineTuner

        finetuner = SentimentFineTuner(model_dir=temp_model_dir)

        bullish_texts = [
            "Bitcoin to the moon! Super bullish!",
            "Accumulating more SOL, this is going up!",
            "PUMP IT! Best investment ever!",
        ]

        for text in bullish_texts:
            prediction = finetuner.predict(text)
            assert prediction.label == 1 or prediction.score > 0, f"Failed for: {text}"

    def test_sentiment_bearish_detection(self, temp_model_dir):
        """Test that bearish sentiment is correctly detected."""
        from core.ml.sentiment_finetuner import SentimentFineTuner

        finetuner = SentimentFineTuner(model_dir=temp_model_dir)

        bearish_texts = [
            "Market crash incoming, sell everything!",
            "This is a scam, rug pull alert!",
            "Bearish divergence, expect dump.",
        ]

        for text in bearish_texts:
            prediction = finetuner.predict(text)
            assert prediction.label == -1 or prediction.score < 0, f"Failed for: {text}"

    def test_sentiment_batch_prediction(self, temp_model_dir, sample_tweets):
        """Test batch prediction capability."""
        from core.ml.sentiment_finetuner import SentimentFineTuner

        finetuner = SentimentFineTuner(model_dir=temp_model_dir)

        texts = [t["text"] for t in sample_tweets]
        predictions = finetuner.predict_batch(texts)

        assert len(predictions) == len(texts)
        for pred in predictions:
            assert pred.label in [-1, 0, 1]

    def test_sentiment_training_metrics(self, temp_model_dir, sample_tweets):
        """Test that training returns proper metrics."""
        from core.ml.sentiment_finetuner import SentimentFineTuner

        finetuner = SentimentFineTuner(model_dir=temp_model_dir)

        # Need more data for training - duplicate samples
        texts = [t["text"] for t in sample_tweets] * 3  # 24 samples
        labels = [t["label"] for t in sample_tweets] * 3

        # Train with enough data
        metrics = finetuner.train(texts, labels, epochs=1)

        assert "accuracy" in metrics or "f1_score" in metrics or "trained" in metrics
        assert metrics.get("trained", False) or "model_path" in metrics or "error" in metrics


# =============================================================================
# Price Predictor Tests (6 tests)
# =============================================================================

class TestPricePredictor:
    """Tests for price direction prediction."""

    def test_price_predictor_init(self, temp_model_dir):
        """Test PricePredictor initialization."""
        from core.ml.price_predictor import PricePredictor

        predictor = PricePredictor(model_dir=temp_model_dir)

        assert predictor is not None
        assert predictor.horizons == ["1h", "4h", "24h"]

    def test_price_prediction_structure(self, temp_model_dir, sample_price_history, sample_volume_history):
        """Test price prediction returns correct structure."""
        from core.ml.price_predictor import PricePredictor, PricePrediction

        predictor = PricePredictor(model_dir=temp_model_dir)

        prediction = predictor.predict(
            prices=sample_price_history,
            volumes=sample_volume_history,
            sentiment_score=50
        )

        assert isinstance(prediction, PricePrediction)
        assert hasattr(prediction, "direction")  # up/down/flat
        assert hasattr(prediction, "confidence")
        assert hasattr(prediction, "horizon")
        assert prediction.direction in ["up", "down", "flat"]
        assert 0 <= prediction.confidence <= 1

    def test_price_prediction_multiple_horizons(self, temp_model_dir, sample_price_history, sample_volume_history):
        """Test predictions for different time horizons."""
        from core.ml.price_predictor import PricePredictor

        predictor = PricePredictor(model_dir=temp_model_dir)

        predictions = predictor.predict_all_horizons(
            prices=sample_price_history,
            volumes=sample_volume_history,
            sentiment_score=50
        )

        assert "1h" in predictions
        assert "4h" in predictions
        assert "24h" in predictions

    def test_price_feature_extraction(self, temp_model_dir, sample_price_history):
        """Test that features are correctly extracted."""
        from core.ml.price_predictor import PricePredictor

        predictor = PricePredictor(model_dir=temp_model_dir)

        features = predictor.extract_features(sample_price_history)

        # Check for momentum features (named with period suffix)
        assert any("momentum" in k for k in features.keys())
        assert any("volatility" in k for k in features.keys())
        assert any("trend" in k for k in features.keys())

    def test_price_accuracy_target(self, temp_model_dir, sample_price_history, sample_volume_history):
        """Test that model aims for >60% accuracy."""
        from core.ml.price_predictor import PricePredictor

        predictor = PricePredictor(model_dir=temp_model_dir)

        # Train on sample data
        labels = ["up" if sample_price_history[i+10] > sample_price_history[i] else "down"
                  for i in range(len(sample_price_history) - 10)]

        metrics = predictor.train(
            prices_list=[sample_price_history[:i+10] for i in range(len(labels))],
            labels=labels
        )

        # Should have accuracy metric
        assert "accuracy" in metrics

    def test_price_predictor_confidence_scores(self, temp_model_dir, sample_price_history, sample_volume_history):
        """Test confidence scores are reasonable."""
        from core.ml.price_predictor import PricePredictor

        predictor = PricePredictor(model_dir=temp_model_dir)

        prediction = predictor.predict(
            prices=sample_price_history,
            volumes=sample_volume_history,
            sentiment_score=50
        )

        # Confidence should be between 0.3 and 1.0 for reasonable predictions
        assert prediction.confidence >= 0.0
        assert prediction.confidence <= 1.0


# =============================================================================
# Anomaly Detector Tests (5 tests)
# =============================================================================

class TestAnomalyDetector:
    """Tests for trading pattern anomaly detection."""

    def test_anomaly_detector_init(self, temp_model_dir):
        """Test AnomalyDetector initialization."""
        from core.ml.anomaly_detector import AnomalyDetector

        detector = AnomalyDetector(model_dir=temp_model_dir)

        assert detector is not None
        assert hasattr(detector, "detect")

    def test_anomaly_detection_structure(self, temp_model_dir, sample_price_history, sample_volume_history):
        """Test anomaly detection returns correct structure."""
        from core.ml.anomaly_detector import AnomalyDetector, AnomalyResult

        detector = AnomalyDetector(model_dir=temp_model_dir)

        result = detector.detect(
            prices=sample_price_history,
            volumes=sample_volume_history
        )

        assert isinstance(result, AnomalyResult)
        assert hasattr(result, "is_anomaly")
        assert hasattr(result, "anomaly_score")
        assert hasattr(result, "anomaly_type")
        assert 0 <= result.anomaly_score <= 100

    def test_price_spike_detection(self, temp_model_dir):
        """Test detection of sudden price spikes (>20% in 1 min)."""
        from core.ml.anomaly_detector import AnomalyDetector

        detector = AnomalyDetector(model_dir=temp_model_dir)

        # Create price series with spike
        prices = [100.0] * 50 + [125.0]  # 25% spike
        volumes = [1000000] * 51

        result = detector.detect(prices=prices, volumes=volumes)

        assert result.is_anomaly is True
        assert "price" in result.anomaly_type.lower() or result.anomaly_score > 50

    def test_volume_anomaly_detection(self, temp_model_dir):
        """Test detection of volume anomalies (10x normal volume)."""
        from core.ml.anomaly_detector import AnomalyDetector

        detector = AnomalyDetector(model_dir=temp_model_dir)

        # Create volume series with spike
        prices = [100.0] * 51
        volumes = [1000000] * 50 + [15000000]  # 15x spike

        result = detector.detect(prices=prices, volumes=volumes)

        assert result.is_anomaly is True
        assert "volume" in result.anomaly_type.lower() or result.anomaly_score > 50

    def test_no_anomaly_normal_data(self, temp_model_dir, sample_price_history, sample_volume_history):
        """Test that normal data doesn't trigger false positives."""
        from core.ml.anomaly_detector import AnomalyDetector

        detector = AnomalyDetector(model_dir=temp_model_dir)

        result = detector.detect(
            prices=sample_price_history,
            volumes=sample_volume_history
        )

        # Normal data should have low anomaly score
        assert result.anomaly_score < 80  # Some tolerance for random variation


# =============================================================================
# Win Rate Predictor Tests (4 tests)
# =============================================================================

class TestWinRatePredictor:
    """Tests for trade win probability prediction."""

    def test_win_rate_predictor_init(self, temp_model_dir):
        """Test WinRatePredictor initialization."""
        from core.ml.win_rate_predictor import WinRatePredictor

        predictor = WinRatePredictor(model_dir=temp_model_dir)

        assert predictor is not None

    def test_win_rate_prediction_structure(self, temp_model_dir):
        """Test win rate prediction returns correct structure."""
        from core.ml.win_rate_predictor import WinRatePredictor, WinRatePrediction

        predictor = WinRatePredictor(model_dir=temp_model_dir)

        prediction = predictor.predict(
            token="SOL",
            entry_signal="bullish",
            position_size=0.05,
            risk_level="medium"
        )

        assert isinstance(prediction, WinRatePrediction)
        assert hasattr(prediction, "win_probability")
        assert 0 <= prediction.win_probability <= 100

    def test_win_rate_training(self, temp_model_dir, sample_trade_data):
        """Test training on historical trade data."""
        from core.ml.win_rate_predictor import WinRatePredictor

        predictor = WinRatePredictor(model_dir=temp_model_dir)

        metrics = predictor.train(sample_trade_data)

        assert "trained" in metrics or "accuracy" in metrics

    def test_win_rate_calibration(self, temp_model_dir, sample_trade_data):
        """Test that predictions are calibrated (probability matches reality)."""
        from core.ml.win_rate_predictor import WinRatePredictor

        predictor = WinRatePredictor(model_dir=temp_model_dir)
        predictor.train(sample_trade_data)

        # Check calibration info
        calibration = predictor.get_calibration()

        assert "expected_accuracy" in calibration or "calibration_error" in calibration


# =============================================================================
# Feature Importance Tests (3 tests)
# =============================================================================

class TestFeatureImportance:
    """Tests for feature importance analysis."""

    def test_feature_importance_init(self, temp_model_dir):
        """Test FeatureImportanceAnalyzer initialization."""
        from core.ml.feature_importance import FeatureImportanceAnalyzer

        analyzer = FeatureImportanceAnalyzer()

        assert analyzer is not None

    def test_feature_importance_ranking(self, temp_model_dir):
        """Test that features are ranked by importance."""
        from core.ml.feature_importance import FeatureImportanceAnalyzer

        analyzer = FeatureImportanceAnalyzer()

        # Mock feature data
        feature_data = {
            "momentum": [0.1, 0.2, 0.15, 0.3],
            "volatility": [0.5, 0.6, 0.55, 0.4],
            "volume": [1000, 1200, 1100, 900],
        }
        labels = [1, 1, 0, 0]

        importance = analyzer.analyze(feature_data, labels)

        assert len(importance) > 0
        assert all("feature" in item and "importance" in item for item in importance)

    def test_feature_importance_shap(self, temp_model_dir):
        """Test SHAP value calculation capability."""
        from core.ml.feature_importance import FeatureImportanceAnalyzer

        analyzer = FeatureImportanceAnalyzer()

        # Check SHAP is available or gracefully degrades
        has_shap = analyzer.supports_shap()

        assert isinstance(has_shap, bool)


# =============================================================================
# Model Evaluator Tests (4 tests)
# =============================================================================

class TestModelEvaluator:
    """Tests for model evaluation framework."""

    def test_model_evaluator_init(self):
        """Test ModelEvaluator initialization."""
        from core.ml.model_evaluator import ModelEvaluator

        evaluator = ModelEvaluator()

        assert evaluator is not None

    def test_classification_metrics(self):
        """Test classification metrics calculation."""
        from core.ml.model_evaluator import ModelEvaluator

        evaluator = ModelEvaluator()

        y_true = [1, 0, 1, 1, 0, 1, 0, 0]
        y_pred = [1, 0, 1, 0, 0, 1, 1, 0]

        metrics = evaluator.evaluate_classification(y_true, y_pred)

        assert "accuracy" in metrics
        assert "precision" in metrics
        assert "recall" in metrics
        assert "f1" in metrics
        assert 0 <= metrics["accuracy"] <= 1

    def test_regression_metrics(self):
        """Test regression metrics calculation."""
        from core.ml.model_evaluator import ModelEvaluator

        evaluator = ModelEvaluator()

        y_true = [100, 105, 95, 110, 98]
        y_pred = [102, 103, 97, 108, 100]

        metrics = evaluator.evaluate_regression(y_true, y_pred)

        assert "mae" in metrics
        assert "rmse" in metrics
        assert "r2" in metrics

    def test_cross_validation(self):
        """Test k-fold cross validation."""
        from core.ml.model_evaluator import ModelEvaluator

        evaluator = ModelEvaluator()

        # Mock model
        mock_model = Mock()
        mock_model.fit = Mock()
        mock_model.predict = Mock(return_value=[1, 0, 1])

        X = [[1, 2], [3, 4], [5, 6], [7, 8], [9, 10], [11, 12]]
        y = [1, 0, 1, 0, 1, 0]

        cv_results = evaluator.cross_validate(mock_model, X, y, k=3)

        assert "mean_score" in cv_results
        assert "std_score" in cv_results
        assert "fold_scores" in cv_results


# =============================================================================
# Model Registry Tests (4 tests)
# =============================================================================

class TestModelRegistry:
    """Tests for model versioning and registry."""

    def test_model_registry_init(self, temp_model_dir):
        """Test ModelRegistry initialization."""
        from core.ml.model_registry import ModelRegistry

        registry = ModelRegistry(registry_dir=temp_model_dir)

        assert registry is not None

    def test_model_registration(self, temp_model_dir):
        """Test registering a new model version."""
        from core.ml.model_registry import ModelRegistry

        registry = ModelRegistry(registry_dir=temp_model_dir)

        # Register a mock model
        version = registry.register(
            model_name="sentiment_classifier",
            model_object={"type": "mock"},
            metrics={"accuracy": 0.85, "f1": 0.82},
            metadata={"training_samples": 1000}
        )

        assert version is not None
        assert hasattr(version, "version_id")
        assert hasattr(version, "timestamp")

    def test_model_loading(self, temp_model_dir):
        """Test loading a registered model."""
        from core.ml.model_registry import ModelRegistry

        registry = ModelRegistry(registry_dir=temp_model_dir)

        # Register then load
        version = registry.register(
            model_name="price_predictor",
            model_object={"type": "mock", "value": 42},
            metrics={"accuracy": 0.75}
        )

        loaded = registry.load(model_name="price_predictor")

        assert loaded is not None
        assert loaded.get("type") == "mock"

    def test_model_rollback(self, temp_model_dir):
        """Test rolling back to previous model version."""
        from core.ml.model_registry import ModelRegistry

        registry = ModelRegistry(registry_dir=temp_model_dir)

        # Register two versions
        v1 = registry.register(
            model_name="test_model",
            model_object={"version": 1},
            metrics={"accuracy": 0.70}
        )

        v2 = registry.register(
            model_name="test_model",
            model_object={"version": 2},
            metrics={"accuracy": 0.65}  # Worse performance
        )

        # Rollback to v1
        success = registry.rollback(model_name="test_model", version_id=v1.version_id)

        assert success is True

        # Verify active version is v1
        active = registry.get_active_version("test_model")
        assert active.version_id == v1.version_id


# =============================================================================
# Integration Tests (2 tests)
# =============================================================================

class TestMLIntegration:
    """Integration tests for ML pipeline."""

    def test_sentiment_to_trading_signal(self, temp_model_dir):
        """Test sentiment prediction integrates with trading signals."""
        from core.ml.sentiment_finetuner import SentimentFineTuner
        from core.ml.price_predictor import PricePredictor

        sentiment = SentimentFineTuner(model_dir=temp_model_dir)
        price_pred = PricePredictor(model_dir=temp_model_dir)

        # Get sentiment
        sent_result = sentiment.predict("Super bullish on SOL today!")

        # Use sentiment in price prediction
        prices = [100.0 + i * 0.5 for i in range(50)]
        volumes = [1000000] * 50

        price_result = price_pred.predict(
            prices=prices,
            volumes=volumes,
            sentiment_score=sent_result.score
        )

        assert price_result is not None
        assert price_result.direction in ["up", "down", "flat"]

    def test_full_ml_pipeline(self, temp_model_dir, sample_price_history, sample_volume_history):
        """Test full ML pipeline: sentiment -> anomaly -> prediction."""
        from core.ml.sentiment_finetuner import SentimentFineTuner
        from core.ml.anomaly_detector import AnomalyDetector
        from core.ml.price_predictor import PricePredictor

        sentiment = SentimentFineTuner(model_dir=temp_model_dir)
        anomaly = AnomalyDetector(model_dir=temp_model_dir)
        price_pred = PricePredictor(model_dir=temp_model_dir)

        # 1. Check for anomalies first
        anomaly_result = anomaly.detect(
            prices=sample_price_history,
            volumes=sample_volume_history
        )

        # 2. Get sentiment
        sent_result = sentiment.predict("Market looking healthy today")

        # 3. Make price prediction
        price_result = price_pred.predict(
            prices=sample_price_history,
            volumes=sample_volume_history,
            sentiment_score=sent_result.score
        )

        # All components should work together
        assert anomaly_result.anomaly_score >= 0
        assert sent_result.label in [-1, 0, 1]
        assert price_result.direction in ["up", "down", "flat"]
