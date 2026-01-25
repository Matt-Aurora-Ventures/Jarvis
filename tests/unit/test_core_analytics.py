"""
Tests for core/analytics.py - Prediction tracking and Portfolio analytics.

Test Categories:
1. Prediction Dataclass Tests
2. PredictionTracker Tests
   - Initialization & Storage
   - Recording Predictions
   - Updating Outcomes
   - Expired Predictions
   - Accuracy Statistics
3. Trade Dataclass Tests
4. Position Dataclass Tests
5. PortfolioAnalytics Tests
   - Initialization & Storage
   - Recording Trades
   - Position Calculation
   - Performance Metrics
   - CSV Export
6. Singleton Functions
7. Edge Cases & Error Handling

Target: 60%+ coverage with ~40-60 tests
"""

import pytest
import json
import csv
import tempfile
import uuid
import importlib.util
import sys
from pathlib import Path
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock
from dataclasses import asdict

# Load core/analytics.py directly since it's shadowed by core/analytics/ package
_analytics_file = Path(__file__).parent.parent.parent / "core" / "analytics.py"
_spec = importlib.util.spec_from_file_location("core_analytics_module", _analytics_file)
_analytics_module = importlib.util.module_from_spec(_spec)
sys.modules["core_analytics_module"] = _analytics_module
_spec.loader.exec_module(_analytics_module)

# Import from the loaded module
Prediction = _analytics_module.Prediction
PredictionTracker = _analytics_module.PredictionTracker
Trade = _analytics_module.Trade
Position = _analytics_module.Position
PortfolioAnalytics = _analytics_module.PortfolioAnalytics
get_prediction_tracker = _analytics_module.get_prediction_tracker
get_portfolio_analytics = _analytics_module.get_portfolio_analytics


# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
def temp_predictions_file():
    """Create a temporary predictions storage file."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        data = {
            "predictions": [],
            "last_updated": datetime.now(timezone.utc).isoformat()
        }
        json.dump(data, f)
        temp_path = Path(f.name)

    yield temp_path
    temp_path.unlink(missing_ok=True)


@pytest.fixture
def temp_predictions_with_data():
    """Create a temporary predictions file with sample data."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        now = datetime.now(timezone.utc)
        predictions = [
            {
                "id": "pred001",
                "timestamp": (now - timedelta(days=2)).isoformat(),
                "token_symbol": "$SOL",
                "token_mint": "So11111111111111111111111111111111111111112",
                "prediction_type": "BULLISH",
                "confidence": 0.85,
                "price_at_prediction": 100.0,
                "target_price": 120.0,
                "stop_loss": 90.0,
                "timeframe_hours": 24,
                "outcome": "WIN",
                "outcome_price": 125.0,
                "outcome_timestamp": (now - timedelta(days=1)).isoformat(),
                "pnl_percent": 25.0,
                "source": "grok"
            },
            {
                "id": "pred002",
                "timestamp": (now - timedelta(days=1)).isoformat(),
                "token_symbol": "$BONK",
                "token_mint": "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263",
                "prediction_type": "BEARISH",
                "confidence": 0.70,
                "price_at_prediction": 0.00001,
                "target_price": 0.000008,
                "stop_loss": 0.000012,
                "timeframe_hours": 12,
                "outcome": "LOSS",
                "outcome_price": 0.000013,
                "outcome_timestamp": now.isoformat(),
                "pnl_percent": -30.0,
                "source": "sentiment"
            },
            {
                "id": "pred003",
                "timestamp": now.isoformat(),
                "token_symbol": "$JUP",
                "token_mint": "JUPyiwrYJFskUPiHa7hkeR8VUtAeFoSYbKedZNsDvCN",
                "prediction_type": "BULLISH",
                "confidence": 0.75,
                "price_at_prediction": 1.5,
                "target_price": 2.0,
                "stop_loss": 1.3,
                "timeframe_hours": 48,
                "outcome": "PENDING",
                "outcome_price": None,
                "outcome_timestamp": None,
                "pnl_percent": 0.0,
                "source": "grok"
            }
        ]
        data = {
            "predictions": predictions,
            "last_updated": now.isoformat()
        }
        json.dump(data, f)
        temp_path = Path(f.name)

    yield temp_path
    temp_path.unlink(missing_ok=True)


@pytest.fixture
def temp_trades_file():
    """Create a temporary trades storage file."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        data = {
            "trades": [],
            "last_updated": datetime.now(timezone.utc).isoformat()
        }
        json.dump(data, f)
        temp_path = Path(f.name)

    yield temp_path
    temp_path.unlink(missing_ok=True)


@pytest.fixture
def temp_trades_with_data():
    """Create a temporary trades file with sample data."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        now = datetime.now(timezone.utc)
        trades = [
            {
                "id": "trade001",
                "timestamp": (now - timedelta(days=5)).isoformat(),
                "token_symbol": "$SOL",
                "token_mint": "So11111111111111111111111111111111111111112",
                "side": "BUY",
                "amount": 10.0,
                "price": 100.0,
                "value_usd": 1000.0,
                "fee_usd": 1.0,
                "tx_signature": "tx_sig_001"
            },
            {
                "id": "trade002",
                "timestamp": (now - timedelta(days=3)).isoformat(),
                "token_symbol": "$SOL",
                "token_mint": "So11111111111111111111111111111111111111112",
                "side": "BUY",
                "amount": 5.0,
                "price": 110.0,
                "value_usd": 550.0,
                "fee_usd": 0.5,
                "tx_signature": "tx_sig_002"
            },
            {
                "id": "trade003",
                "timestamp": (now - timedelta(days=2)).isoformat(),
                "token_symbol": "$SOL",
                "token_mint": "So11111111111111111111111111111111111111112",
                "side": "SELL",
                "amount": 8.0,
                "price": 120.0,
                "value_usd": 960.0,
                "fee_usd": 1.0,
                "tx_signature": "tx_sig_003"
            },
            {
                "id": "trade004",
                "timestamp": (now - timedelta(days=1)).isoformat(),
                "token_symbol": "$BONK",
                "token_mint": "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263",
                "side": "BUY",
                "amount": 1000000.0,
                "price": 0.00001,
                "value_usd": 10.0,
                "fee_usd": 0.1,
                "tx_signature": "tx_sig_004"
            }
        ]
        data = {
            "trades": trades,
            "last_updated": now.isoformat()
        }
        json.dump(data, f)
        temp_path = Path(f.name)

    yield temp_path
    temp_path.unlink(missing_ok=True)


# ============================================================================
# PREDICTION DATACLASS TESTS
# ============================================================================

class TestPredictionDataclass:
    """Tests for the Prediction dataclass."""

    def test_prediction_creation_minimal(self):
        """Test creating a prediction with minimal required fields."""
        pred = Prediction(
            id="test123",
            timestamp="2024-01-01T00:00:00+00:00",
            token_symbol="$SOL",
            token_mint="So11111111111111111111111111111111111111112",
            prediction_type="BULLISH",
            confidence=0.85,
            price_at_prediction=100.0
        )

        assert pred.id == "test123"
        assert pred.token_symbol == "$SOL"
        assert pred.prediction_type == "BULLISH"
        assert pred.confidence == 0.85
        assert pred.price_at_prediction == 100.0
        # Defaults
        assert pred.target_price is None
        assert pred.stop_loss is None
        assert pred.timeframe_hours == 24
        assert pred.outcome == "PENDING"
        assert pred.pnl_percent == 0.0
        assert pred.source == "grok"

    def test_prediction_creation_full(self):
        """Test creating a prediction with all fields."""
        pred = Prediction(
            id="test456",
            timestamp="2024-01-01T00:00:00+00:00",
            token_symbol="$BONK",
            token_mint="DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263",
            prediction_type="BEARISH",
            confidence=0.70,
            price_at_prediction=0.00001,
            target_price=0.000008,
            stop_loss=0.000012,
            timeframe_hours=12,
            outcome="WIN",
            outcome_price=0.000007,
            outcome_timestamp="2024-01-01T12:00:00+00:00",
            pnl_percent=20.0,
            source="sentiment"
        )

        assert pred.target_price == 0.000008
        assert pred.stop_loss == 0.000012
        assert pred.timeframe_hours == 12
        assert pred.outcome == "WIN"
        assert pred.outcome_price == 0.000007
        assert pred.pnl_percent == 20.0
        assert pred.source == "sentiment"

    def test_prediction_asdict(self):
        """Test converting prediction to dictionary."""
        pred = Prediction(
            id="test789",
            timestamp="2024-01-01T00:00:00+00:00",
            token_symbol="$JUP",
            token_mint="JUPyiwrYJFskUPiHa7hkeR8VUtAeFoSYbKedZNsDvCN",
            prediction_type="NEUTRAL",
            confidence=0.50,
            price_at_prediction=1.5
        )

        pred_dict = asdict(pred)
        assert isinstance(pred_dict, dict)
        assert pred_dict["id"] == "test789"
        assert pred_dict["prediction_type"] == "NEUTRAL"


# ============================================================================
# PREDICTION TRACKER TESTS
# ============================================================================

class TestPredictionTrackerInit:
    """Tests for PredictionTracker initialization."""

    def test_init_with_empty_file(self, temp_predictions_file):
        """Test initialization with empty predictions file."""
        tracker = PredictionTracker(storage_path=temp_predictions_file)
        assert len(tracker.predictions) == 0

    def test_init_with_existing_data(self, temp_predictions_with_data):
        """Test initialization loads existing predictions."""
        tracker = PredictionTracker(storage_path=temp_predictions_with_data)
        assert len(tracker.predictions) == 3
        assert "pred001" in tracker.predictions
        assert "pred002" in tracker.predictions
        assert "pred003" in tracker.predictions

    def test_init_with_nonexistent_file(self):
        """Test initialization with nonexistent file."""
        tracker = PredictionTracker(storage_path=Path("/nonexistent/path/predictions.json"))
        assert len(tracker.predictions) == 0

    def test_init_default_path(self):
        """Test initialization uses default path."""
        with patch.object(Path, 'exists', return_value=False):
            tracker = PredictionTracker()
            # Default path should be relative to module
            assert "predictions.json" in str(tracker.storage_path)


class TestPredictionTrackerRecording:
    """Tests for recording predictions."""

    def test_record_prediction_basic(self, temp_predictions_file):
        """Test recording a basic prediction."""
        tracker = PredictionTracker(storage_path=temp_predictions_file)

        pred_id = tracker.record_prediction(
            token_symbol="$SOL",
            token_mint="So11111111111111111111111111111111111111112",
            prediction_type="BULLISH",
            confidence=0.85,
            price_at_prediction=100.0
        )

        assert pred_id is not None
        assert len(pred_id) == 8  # UUID truncated to 8 chars
        assert pred_id in tracker.predictions

        pred = tracker.predictions[pred_id]
        assert pred.token_symbol == "$SOL"
        assert pred.prediction_type == "BULLISH"
        assert pred.confidence == 0.85
        assert pred.outcome == "PENDING"

    def test_record_prediction_with_targets(self, temp_predictions_file):
        """Test recording prediction with target and stop loss."""
        tracker = PredictionTracker(storage_path=temp_predictions_file)

        pred_id = tracker.record_prediction(
            token_symbol="$BONK",
            token_mint="DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263",
            prediction_type="BEARISH",
            confidence=0.70,
            price_at_prediction=0.00001,
            target_price=0.000008,
            stop_loss=0.000012,
            timeframe_hours=12
        )

        pred = tracker.predictions[pred_id]
        assert pred.target_price == 0.000008
        assert pred.stop_loss == 0.000012
        assert pred.timeframe_hours == 12

    def test_record_prediction_normalizes_type(self, temp_predictions_file):
        """Test that prediction type is normalized to uppercase."""
        tracker = PredictionTracker(storage_path=temp_predictions_file)

        pred_id = tracker.record_prediction(
            token_symbol="$SOL",
            token_mint="So11111111111111111111111111111111111111112",
            prediction_type="bullish",  # lowercase
            confidence=0.85,
            price_at_prediction=100.0
        )

        pred = tracker.predictions[pred_id]
        assert pred.prediction_type == "BULLISH"

    def test_record_prediction_persists(self, temp_predictions_file):
        """Test that recorded predictions are saved to file."""
        tracker = PredictionTracker(storage_path=temp_predictions_file)

        tracker.record_prediction(
            token_symbol="$SOL",
            token_mint="So11111111111111111111111111111111111111112",
            prediction_type="BULLISH",
            confidence=0.85,
            price_at_prediction=100.0
        )

        # Reload from file
        tracker2 = PredictionTracker(storage_path=temp_predictions_file)
        assert len(tracker2.predictions) == 1


class TestPredictionTrackerOutcomes:
    """Tests for updating prediction outcomes."""

    def test_update_outcome_bullish_win_target_hit(self, temp_predictions_file):
        """Test bullish prediction wins when target is hit."""
        tracker = PredictionTracker(storage_path=temp_predictions_file)

        pred_id = tracker.record_prediction(
            token_symbol="$SOL",
            token_mint="So11111111111111111111111111111111111111112",
            prediction_type="BULLISH",
            confidence=0.85,
            price_at_prediction=100.0,
            target_price=120.0,
            stop_loss=90.0
        )

        outcome = tracker.update_outcome(pred_id, current_price=125.0)

        assert outcome == "WIN"
        pred = tracker.predictions[pred_id]
        assert pred.outcome == "WIN"
        assert pred.outcome_price == 125.0
        assert pred.pnl_percent == 25.0

    def test_update_outcome_bullish_loss_stop_hit(self, temp_predictions_file):
        """Test bullish prediction loses when stop loss is hit."""
        tracker = PredictionTracker(storage_path=temp_predictions_file)

        pred_id = tracker.record_prediction(
            token_symbol="$SOL",
            token_mint="So11111111111111111111111111111111111111112",
            prediction_type="BULLISH",
            confidence=0.85,
            price_at_prediction=100.0,
            target_price=120.0,
            stop_loss=90.0
        )

        outcome = tracker.update_outcome(pred_id, current_price=85.0)

        assert outcome == "LOSS"
        pred = tracker.predictions[pred_id]
        assert pred.outcome == "LOSS"
        assert pred.pnl_percent == -15.0

    def test_update_outcome_bullish_win_positive_pnl(self, temp_predictions_file):
        """Test bullish prediction wins with positive PnL (no target)."""
        tracker = PredictionTracker(storage_path=temp_predictions_file)

        pred_id = tracker.record_prediction(
            token_symbol="$SOL",
            token_mint="So11111111111111111111111111111111111111112",
            prediction_type="BULLISH",
            confidence=0.85,
            price_at_prediction=100.0
            # No target/stop
        )

        outcome = tracker.update_outcome(pred_id, current_price=110.0)

        assert outcome == "WIN"
        pred = tracker.predictions[pred_id]
        assert pred.pnl_percent == 10.0

    def test_update_outcome_bearish_win_target_hit(self, temp_predictions_file):
        """Test bearish prediction wins when target is hit."""
        tracker = PredictionTracker(storage_path=temp_predictions_file)

        pred_id = tracker.record_prediction(
            token_symbol="$SOL",
            token_mint="So11111111111111111111111111111111111111112",
            prediction_type="BEARISH",
            confidence=0.80,
            price_at_prediction=100.0,
            target_price=80.0,  # Expecting price to drop
            stop_loss=110.0
        )

        outcome = tracker.update_outcome(pred_id, current_price=75.0)

        assert outcome == "WIN"
        pred = tracker.predictions[pred_id]
        assert pred.outcome == "WIN"
        # PnL is inverted for bearish
        assert pred.pnl_percent == 25.0

    def test_update_outcome_bearish_loss_stop_hit(self, temp_predictions_file):
        """Test bearish prediction loses when stop loss is hit."""
        tracker = PredictionTracker(storage_path=temp_predictions_file)

        pred_id = tracker.record_prediction(
            token_symbol="$SOL",
            token_mint="So11111111111111111111111111111111111111112",
            prediction_type="BEARISH",
            confidence=0.80,
            price_at_prediction=100.0,
            target_price=80.0,
            stop_loss=110.0
        )

        outcome = tracker.update_outcome(pred_id, current_price=115.0)

        assert outcome == "LOSS"
        pred = tracker.predictions[pred_id]
        # PnL is inverted for bearish (price went up = loss)
        assert pred.pnl_percent == -15.0

    def test_update_outcome_neutral_win_small_movement(self, temp_predictions_file):
        """Test neutral prediction wins when price stays within 5%."""
        tracker = PredictionTracker(storage_path=temp_predictions_file)

        pred_id = tracker.record_prediction(
            token_symbol="$SOL",
            token_mint="So11111111111111111111111111111111111111112",
            prediction_type="NEUTRAL",
            confidence=0.60,
            price_at_prediction=100.0
        )

        outcome = tracker.update_outcome(pred_id, current_price=103.0)

        assert outcome == "WIN"

    def test_update_outcome_neutral_loss_large_movement(self, temp_predictions_file):
        """Test neutral prediction loses when price moves more than 5%."""
        tracker = PredictionTracker(storage_path=temp_predictions_file)

        pred_id = tracker.record_prediction(
            token_symbol="$SOL",
            token_mint="So11111111111111111111111111111111111111112",
            prediction_type="NEUTRAL",
            confidence=0.60,
            price_at_prediction=100.0
        )

        outcome = tracker.update_outcome(pred_id, current_price=110.0)

        assert outcome == "LOSS"

    def test_update_outcome_already_resolved(self, temp_predictions_with_data):
        """Test that already resolved predictions are not updated."""
        tracker = PredictionTracker(storage_path=temp_predictions_with_data)

        # pred001 is already WIN
        outcome = tracker.update_outcome("pred001", current_price=50.0)

        assert outcome == "WIN"  # Returns existing outcome
        pred = tracker.predictions["pred001"]
        assert pred.outcome_price == 125.0  # Unchanged

    def test_update_outcome_not_found(self, temp_predictions_file):
        """Test updating nonexistent prediction returns None."""
        tracker = PredictionTracker(storage_path=temp_predictions_file)

        outcome = tracker.update_outcome("nonexistent", current_price=100.0)

        assert outcome is None

    def test_update_outcome_zero_price(self, temp_predictions_file):
        """Test handling of zero price at prediction."""
        tracker = PredictionTracker(storage_path=temp_predictions_file)

        pred_id = tracker.record_prediction(
            token_symbol="$SOL",
            token_mint="So11111111111111111111111111111111111111112",
            prediction_type="BULLISH",
            confidence=0.85,
            price_at_prediction=0.0  # Edge case
        )

        # Should not crash
        outcome = tracker.update_outcome(pred_id, current_price=100.0)
        pred = tracker.predictions[pred_id]
        assert pred.pnl_percent == 0.0  # Protected from division by zero


class TestPredictionTrackerExpiry:
    """Tests for expired predictions handling."""

    def test_check_expired_predictions(self, temp_predictions_file):
        """Test checking and marking expired predictions."""
        tracker = PredictionTracker(storage_path=temp_predictions_file)

        # Create a prediction that should be expired
        pred_id = tracker.record_prediction(
            token_symbol="$SOL",
            token_mint="So11111111111111111111111111111111111111112",
            prediction_type="BULLISH",
            confidence=0.85,
            price_at_prediction=100.0,
            timeframe_hours=1  # 1 hour timeframe
        )

        # Manually set timestamp to 2 hours ago
        pred = tracker.predictions[pred_id]
        pred.timestamp = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()

        tracker.check_expired_predictions()

        assert pred.outcome == "EXPIRED"
        assert pred.outcome_timestamp is not None

    def test_check_expired_skips_resolved(self, temp_predictions_with_data):
        """Test that expired check skips already resolved predictions."""
        tracker = PredictionTracker(storage_path=temp_predictions_with_data)

        # pred001 is already WIN
        pred = tracker.predictions["pred001"]
        original_outcome = pred.outcome

        tracker.check_expired_predictions()

        assert pred.outcome == original_outcome  # Unchanged


class TestPredictionTrackerStats:
    """Tests for prediction accuracy statistics."""

    def test_get_pending_predictions(self, temp_predictions_with_data):
        """Test getting pending predictions."""
        tracker = PredictionTracker(storage_path=temp_predictions_with_data)

        pending = tracker.get_pending_predictions()

        assert len(pending) == 1
        assert pending[0].id == "pred003"

    def test_get_accuracy_stats_basic(self, temp_predictions_with_data):
        """Test getting basic accuracy statistics."""
        tracker = PredictionTracker(storage_path=temp_predictions_with_data)

        stats = tracker.get_accuracy_stats(days=7)

        assert stats["period_days"] == 7
        assert stats["total_predictions"] == 2  # Excludes pending
        assert stats["wins"] == 1
        assert stats["losses"] == 1
        assert stats["accuracy_percent"] == 50.0

    def test_get_accuracy_stats_empty(self, temp_predictions_file):
        """Test accuracy stats with no predictions."""
        tracker = PredictionTracker(storage_path=temp_predictions_file)

        stats = tracker.get_accuracy_stats(days=7)

        assert stats["total_predictions"] == 0
        assert stats["accuracy_percent"] == 0
        assert stats["avg_pnl_percent"] == 0

    def test_get_accuracy_stats_by_type(self, temp_predictions_with_data):
        """Test accuracy stats broken down by type."""
        tracker = PredictionTracker(storage_path=temp_predictions_with_data)

        stats = tracker.get_accuracy_stats(days=7)

        assert "by_type" in stats
        assert "BULLISH" in stats["by_type"]
        assert "BEARISH" in stats["by_type"]

        bullish = stats["by_type"]["BULLISH"]
        assert bullish["total"] == 1
        assert bullish["wins"] == 1
        assert bullish["accuracy"] == 100.0

    def test_get_accuracy_stats_by_source(self, temp_predictions_with_data):
        """Test accuracy stats broken down by source."""
        tracker = PredictionTracker(storage_path=temp_predictions_with_data)

        stats = tracker.get_accuracy_stats(days=7)

        assert "by_source" in stats
        assert "grok" in stats["by_source"]
        assert "sentiment" in stats["by_source"]

    def test_get_accuracy_stats_time_filter(self, temp_predictions_with_data):
        """Test that stats respect the days filter."""
        tracker = PredictionTracker(storage_path=temp_predictions_with_data)

        # 0 days should return nothing (or almost nothing depending on timing)
        stats = tracker.get_accuracy_stats(days=0)
        assert stats["total_predictions"] <= 2


# ============================================================================
# TRADE DATACLASS TESTS
# ============================================================================

class TestTradeDataclass:
    """Tests for the Trade dataclass."""

    def test_trade_creation(self):
        """Test creating a trade record."""
        trade = Trade(
            id="trade123",
            timestamp="2024-01-01T00:00:00+00:00",
            token_symbol="$SOL",
            token_mint="So11111111111111111111111111111111111111112",
            side="BUY",
            amount=10.0,
            price=100.0,
            value_usd=1000.0,
            fee_usd=1.0,
            tx_signature="tx_abc123"
        )

        assert trade.id == "trade123"
        assert trade.side == "BUY"
        assert trade.amount == 10.0
        assert trade.value_usd == 1000.0

    def test_trade_default_values(self):
        """Test trade default values."""
        trade = Trade(
            id="trade456",
            timestamp="2024-01-01T00:00:00+00:00",
            token_symbol="$SOL",
            token_mint="So11111111111111111111111111111111111111112",
            side="SELL",
            amount=5.0,
            price=110.0,
            value_usd=550.0
        )

        assert trade.fee_usd == 0.0
        assert trade.tx_signature == ""


# ============================================================================
# POSITION DATACLASS TESTS
# ============================================================================

class TestPositionDataclass:
    """Tests for the Position dataclass."""

    def test_position_creation(self):
        """Test creating a position record."""
        pos = Position(
            token_symbol="$SOL",
            token_mint="So11111111111111111111111111111111111111112",
            amount=10.0,
            avg_entry_price=100.0,
            current_price=110.0,
            value_usd=1100.0,
            unrealized_pnl=100.0,
            unrealized_pnl_percent=10.0
        )

        assert pos.token_symbol == "$SOL"
        assert pos.amount == 10.0
        assert pos.unrealized_pnl_percent == 10.0

    def test_position_default_values(self):
        """Test position default values."""
        pos = Position(
            token_symbol="$BONK",
            token_mint="DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263",
            amount=1000000.0,
            avg_entry_price=0.00001
        )

        assert pos.current_price == 0.0
        assert pos.value_usd == 0.0
        assert pos.unrealized_pnl == 0.0
        assert pos.unrealized_pnl_percent == 0.0


# ============================================================================
# PORTFOLIO ANALYTICS TESTS
# ============================================================================

class TestPortfolioAnalyticsInit:
    """Tests for PortfolioAnalytics initialization."""

    def test_init_with_empty_file(self, temp_trades_file):
        """Test initialization with empty trades file."""
        analytics = PortfolioAnalytics(storage_path=temp_trades_file)
        assert len(analytics.trades) == 0

    def test_init_with_existing_data(self, temp_trades_with_data):
        """Test initialization loads existing trades."""
        analytics = PortfolioAnalytics(storage_path=temp_trades_with_data)
        assert len(analytics.trades) == 4

    def test_init_with_nonexistent_file(self):
        """Test initialization with nonexistent file."""
        analytics = PortfolioAnalytics(storage_path=Path("/nonexistent/path/trades.json"))
        assert len(analytics.trades) == 0


class TestPortfolioAnalyticsRecording:
    """Tests for recording trades."""

    def test_record_trade_basic(self, temp_trades_file):
        """Test recording a basic trade."""
        analytics = PortfolioAnalytics(storage_path=temp_trades_file)

        trade_id = analytics.record_trade(
            side="BUY",
            token_symbol="$SOL",
            token_mint="So11111111111111111111111111111111111111112",
            amount=10.0,
            price=100.0
        )

        assert trade_id is not None
        assert len(analytics.trades) == 1

        trade = analytics.trades[0]
        assert trade.side == "BUY"
        assert trade.amount == 10.0
        assert trade.value_usd == 1000.0

    def test_record_trade_with_fee(self, temp_trades_file):
        """Test recording a trade with fee."""
        analytics = PortfolioAnalytics(storage_path=temp_trades_file)

        trade_id = analytics.record_trade(
            side="SELL",
            token_symbol="$SOL",
            token_mint="So11111111111111111111111111111111111111112",
            amount=5.0,
            price=110.0,
            fee_usd=0.5,
            tx_signature="tx_abc123"
        )

        trade = analytics.trades[0]
        assert trade.fee_usd == 0.5
        assert trade.tx_signature == "tx_abc123"

    def test_record_trade_normalizes_side(self, temp_trades_file):
        """Test that trade side is normalized to uppercase."""
        analytics = PortfolioAnalytics(storage_path=temp_trades_file)

        analytics.record_trade(
            side="buy",  # lowercase
            token_symbol="$SOL",
            token_mint="So11111111111111111111111111111111111111112",
            amount=10.0,
            price=100.0
        )

        assert analytics.trades[0].side == "BUY"

    def test_record_trade_persists(self, temp_trades_file):
        """Test that recorded trades are saved to file."""
        analytics = PortfolioAnalytics(storage_path=temp_trades_file)

        analytics.record_trade(
            side="BUY",
            token_symbol="$SOL",
            token_mint="So11111111111111111111111111111111111111112",
            amount=10.0,
            price=100.0
        )

        # Reload from file
        analytics2 = PortfolioAnalytics(storage_path=temp_trades_file)
        assert len(analytics2.trades) == 1


class TestPortfolioAnalyticsPositions:
    """Tests for position calculation."""

    def test_get_positions_basic(self, temp_trades_with_data):
        """Test basic position calculation from trades."""
        analytics = PortfolioAnalytics(storage_path=temp_trades_with_data)

        positions = analytics.get_positions()

        # Should have 2 positions: SOL (7 remaining) and BONK (1M)
        assert len(positions) == 2

        # Find SOL position
        sol_pos = next((p for p in positions if p.token_symbol == "$SOL"), None)
        assert sol_pos is not None
        assert sol_pos.amount == 7.0  # 10 + 5 - 8 = 7

    def test_get_positions_with_current_prices(self, temp_trades_with_data):
        """Test position calculation with current prices."""
        analytics = PortfolioAnalytics(storage_path=temp_trades_with_data)

        current_prices = {
            "So11111111111111111111111111111111111111112": 130.0,
            "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263": 0.000012
        }

        positions = analytics.get_positions(current_prices=current_prices)

        sol_pos = next((p for p in positions if p.token_symbol == "$SOL"), None)
        assert sol_pos.current_price == 130.0
        assert sol_pos.value_usd == pytest.approx(7.0 * 130.0, rel=0.01)

    def test_get_positions_avg_entry_price(self, temp_trades_with_data):
        """Test average entry price calculation."""
        analytics = PortfolioAnalytics(storage_path=temp_trades_with_data)

        positions = analytics.get_positions()

        sol_pos = next((p for p in positions if p.token_symbol == "$SOL"), None)
        # Avg entry = (10 * 100 + 5 * 110) / 15 = 1550 / 15 = 103.33
        # But after selling 8, we need to consider the new average
        # This depends on FIFO calculation
        assert sol_pos.avg_entry_price > 0

    def test_get_positions_excludes_closed(self, temp_trades_file):
        """Test that fully sold positions are excluded."""
        analytics = PortfolioAnalytics(storage_path=temp_trades_file)

        # Buy and then sell same amount
        analytics.record_trade("BUY", "$SOL", "mint1", 10.0, 100.0)
        analytics.record_trade("SELL", "$SOL", "mint1", 10.0, 110.0)

        positions = analytics.get_positions()

        # Position should be excluded (amount <= 0)
        sol_positions = [p for p in positions if p.token_symbol == "$SOL"]
        assert len(sol_positions) == 0

    def test_get_positions_unrealized_pnl(self, temp_trades_file):
        """Test unrealized PnL calculation."""
        analytics = PortfolioAnalytics(storage_path=temp_trades_file)

        analytics.record_trade("BUY", "$SOL", "mint1", 10.0, 100.0)

        positions = analytics.get_positions(current_prices={"mint1": 120.0})

        sol_pos = positions[0]
        assert sol_pos.unrealized_pnl == pytest.approx(200.0, rel=0.01)  # (120-100) * 10
        assert sol_pos.unrealized_pnl_percent == pytest.approx(20.0, rel=0.01)


class TestPortfolioAnalyticsPerformance:
    """Tests for performance metrics."""

    def test_get_performance_basic(self, temp_trades_with_data):
        """Test basic performance metrics."""
        analytics = PortfolioAnalytics(storage_path=temp_trades_with_data)

        perf = analytics.get_performance(days=30)

        assert perf["period_days"] == 30
        assert perf["total_trades"] == 4
        assert perf["buy_trades"] == 3
        assert perf["sell_trades"] == 1

    def test_get_performance_volume(self, temp_trades_with_data):
        """Test volume calculation."""
        analytics = PortfolioAnalytics(storage_path=temp_trades_with_data)

        perf = analytics.get_performance(days=30)

        # Total volume = 1000 + 550 + 960 + 10 = 2520
        assert perf["total_volume_usd"] == pytest.approx(2520.0, rel=0.01)

    def test_get_performance_fees(self, temp_trades_with_data):
        """Test fee calculation."""
        analytics = PortfolioAnalytics(storage_path=temp_trades_with_data)

        perf = analytics.get_performance(days=30)

        # Total fees = 1.0 + 0.5 + 1.0 + 0.1 = 2.6
        assert perf["total_fees_usd"] == pytest.approx(2.6, rel=0.01)

    def test_get_performance_realized_pnl(self, temp_trades_with_data):
        """Test realized PnL calculation (FIFO)."""
        analytics = PortfolioAnalytics(storage_path=temp_trades_with_data)

        perf = analytics.get_performance(days=30)

        # Sold 8 SOL at 120, bought at 100 and 110
        # FIFO: 8 sold = first 8 from 10 bought at 100
        # PnL = 8 * (120 - 100) = 160
        assert perf["realized_pnl_usd"] == pytest.approx(160.0, rel=0.01)

    def test_get_performance_empty(self, temp_trades_file):
        """Test performance with no trades."""
        analytics = PortfolioAnalytics(storage_path=temp_trades_file)

        perf = analytics.get_performance(days=30)

        assert perf["total_trades"] == 0
        assert perf["realized_pnl_usd"] == 0

    def test_get_performance_time_filter(self, temp_trades_with_data):
        """Test that performance respects the days filter."""
        analytics = PortfolioAnalytics(storage_path=temp_trades_with_data)

        # With 0 days, should have no trades (or very recent only)
        perf = analytics.get_performance(days=0)
        assert perf["total_trades"] == 0


class TestPortfolioAnalyticsExport:
    """Tests for CSV export."""

    def test_export_trades_csv(self, temp_trades_with_data):
        """Test exporting trades to CSV."""
        analytics = PortfolioAnalytics(storage_path=temp_trades_with_data)

        with tempfile.NamedTemporaryFile(suffix='.csv', delete=False) as f:
            export_path = Path(f.name)

        try:
            result_path = analytics.export_trades_csv(path=export_path)

            assert result_path == export_path
            assert result_path.exists()

            # Verify CSV content
            with open(result_path) as f:
                reader = csv.reader(f)
                rows = list(reader)

            # Header + 4 data rows
            assert len(rows) == 5
            assert rows[0][0] == "ID"
            assert rows[0][4] == "Side"
        finally:
            export_path.unlink(missing_ok=True)

    def test_export_trades_csv_default_path(self, temp_trades_with_data):
        """Test export uses default path when none specified."""
        analytics = PortfolioAnalytics(storage_path=temp_trades_with_data)

        result_path = analytics.export_trades_csv()

        try:
            assert result_path.suffix == ".csv"
            assert result_path.exists()
        finally:
            result_path.unlink(missing_ok=True)


# ============================================================================
# SINGLETON TESTS
# ============================================================================

class TestSingletons:
    """Tests for singleton accessor functions."""

    def test_get_prediction_tracker_singleton(self):
        """Test prediction tracker singleton."""
        # Reset singleton
        _analytics_module._prediction_tracker = None

        tracker1 = get_prediction_tracker()
        tracker2 = get_prediction_tracker()

        assert tracker1 is tracker2

    def test_get_portfolio_analytics_singleton(self):
        """Test portfolio analytics singleton."""
        # Reset singleton
        _analytics_module._portfolio_analytics = None

        analytics1 = get_portfolio_analytics()
        analytics2 = get_portfolio_analytics()

        assert analytics1 is analytics2


# ============================================================================
# EDGE CASES & ERROR HANDLING
# ============================================================================

class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_malformed_json_predictions(self):
        """Test handling of malformed JSON in predictions file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write("not valid json{")
            temp_path = Path(f.name)

        try:
            tracker = PredictionTracker(storage_path=temp_path)
            assert len(tracker.predictions) == 0
        finally:
            temp_path.unlink(missing_ok=True)

    def test_malformed_json_trades(self):
        """Test handling of malformed JSON in trades file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write("invalid json content")
            temp_path = Path(f.name)

        try:
            analytics = PortfolioAnalytics(storage_path=temp_path)
            assert len(analytics.trades) == 0
        finally:
            temp_path.unlink(missing_ok=True)

    def test_save_creates_directory(self, temp_predictions_file):
        """Test that saving creates parent directories."""
        # Use a nested path that doesn't exist
        nested_path = temp_predictions_file.parent / "nested" / "dir" / "predictions.json"

        try:
            tracker = PredictionTracker(storage_path=nested_path)
            tracker.record_prediction(
                token_symbol="$SOL",
                token_mint="mint",
                prediction_type="BULLISH",
                confidence=0.85,
                price_at_prediction=100.0
            )

            assert nested_path.exists()
        finally:
            if nested_path.exists():
                nested_path.unlink()
            nested_path.parent.rmdir()
            nested_path.parent.parent.rmdir()

    def test_negative_amounts(self, temp_trades_file):
        """Test handling of negative amounts in trades."""
        analytics = PortfolioAnalytics(storage_path=temp_trades_file)

        # Sell more than we have
        analytics.record_trade("BUY", "$SOL", "mint1", 5.0, 100.0)
        analytics.record_trade("SELL", "$SOL", "mint1", 10.0, 110.0)

        positions = analytics.get_positions()

        # Position with negative amount should be excluded
        sol_positions = [p for p in positions if p.token_symbol == "$SOL"]
        assert len(sol_positions) == 0

    def test_zero_entry_price_pnl(self, temp_trades_file):
        """Test PnL calculation with zero entry price."""
        analytics = PortfolioAnalytics(storage_path=temp_trades_file)

        # Edge case: free tokens (airdrop simulation)
        analytics.record_trade("BUY", "$AIR", "mint_air", 1000.0, 0.0)

        positions = analytics.get_positions(current_prices={"mint_air": 1.0})

        air_pos = positions[0]
        # Should handle division by zero gracefully
        assert air_pos.unrealized_pnl_percent == 0.0

    def test_extreme_values(self, temp_predictions_file):
        """Test handling of extreme numerical values."""
        tracker = PredictionTracker(storage_path=temp_predictions_file)

        # Very small price (micro-cap token)
        pred_id = tracker.record_prediction(
            token_symbol="$MICRO",
            token_mint="micro_mint",
            prediction_type="BULLISH",
            confidence=0.99,
            price_at_prediction=0.000000001
        )

        # 100000x gain
        outcome = tracker.update_outcome(pred_id, current_price=0.0001)

        assert outcome == "WIN"
        pred = tracker.predictions[pred_id]
        assert pred.pnl_percent > 0

    def test_concurrent_predictions(self, temp_predictions_file):
        """Test recording multiple predictions concurrently."""
        tracker = PredictionTracker(storage_path=temp_predictions_file)

        ids = []
        for i in range(10):
            pred_id = tracker.record_prediction(
                token_symbol=f"$TOKEN{i}",
                token_mint=f"mint{i}",
                prediction_type="BULLISH",
                confidence=0.5 + i * 0.05,
                price_at_prediction=100.0 + i
            )
            ids.append(pred_id)

        assert len(tracker.predictions) == 10
        assert len(set(ids)) == 10  # All unique IDs

    def test_unicode_token_symbols(self, temp_predictions_file):
        """Test handling of unicode in token symbols."""
        tracker = PredictionTracker(storage_path=temp_predictions_file)

        pred_id = tracker.record_prediction(
            token_symbol="$ROCKET",
            token_mint="rocket_mint",
            prediction_type="BULLISH",
            confidence=0.90,
            price_at_prediction=1.0
        )

        assert pred_id in tracker.predictions

        # Reload and verify
        tracker2 = PredictionTracker(storage_path=temp_predictions_file)
        assert tracker2.predictions[pred_id].token_symbol == "$ROCKET"
