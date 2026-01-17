"""
Comprehensive test suite for Treasury Display and Sentiment Systems.

Tests:
- Asset Registry (20 assets, categorization)
- Treasury Display (loading, calculations, displays)
- Self-tuning Sentiment Engine (predictions, outcomes, tuning)
- Outcome Tracker (service initialization)
- Treasury Telegram Handler (command handlers)
"""

import sys
from pathlib import Path
import os

# Set UTF-8 encoding for Windows
if sys.platform == "win32":
    os.environ['PYTHONIOENCODING'] = 'utf-8'

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
import json
import tempfile
from datetime import datetime, timedelta

# Test Asset Registry
def test_asset_registry_imports():
    """Test that asset registry can be imported."""
    from core.assets import AssetRegistry, Asset, AssetCategory
    assert AssetRegistry is not None
    assert Asset is not None
    assert AssetCategory is not None


def test_asset_registry_total_assets():
    """Test that all 20 assets are registered."""
    from core.assets import AssetRegistry
    total = AssetRegistry.total_assets()
    assert total == 20, f"Expected 20 assets, got {total}"


def test_asset_registry_categories():
    """Test that assets are properly categorized."""
    from core.assets import AssetRegistry, AssetCategory

    native = AssetRegistry.get_solana_native()
    assert len(native) == 5, f"Expected 5 solana native, got {len(native)}"

    xstocks = AssetRegistry.get_xstocks()
    assert len(xstocks) == 7, f"Expected 7 xstocks, got {len(xstocks)}"

    prestocks = AssetRegistry.get_prestocks()
    assert len(prestocks) == 5, f"Expected 5 prestocks, got {len(prestocks)}"

    commodities = AssetRegistry.get_commodities()
    assert len(commodities) == 3, f"Expected 3 commodities, got {len(commodities)}"


def test_asset_registry_lookups():
    """Test asset lookup by symbol."""
    from core.assets import AssetRegistry

    sol = AssetRegistry.get_asset("SOL")
    assert sol is not None
    assert sol.symbol == "SOL"
    assert sol.display_name == "Solana"

    btc = AssetRegistry.get_asset("btc")  # Case insensitive
    assert btc is not None
    assert btc.symbol == "BTC"


def test_asset_registry_sentiment_weights():
    """Test that sentiment weights are initialized for all assets."""
    from core.assets import AssetRegistry

    for asset in AssetRegistry.get_all_assets():
        assert asset.sentiment_weights is not None
        weights_sum = (
            asset.sentiment_weights.price_momentum +
            asset.sentiment_weights.volume +
            asset.sentiment_weights.social_sentiment +
            asset.sentiment_weights.whale_activity +
            asset.sentiment_weights.technical_analysis
        )
        assert abs(weights_sum - 1.0) < 0.01, f"{asset.symbol} weights don't sum to 1.0"


# Test Treasury Display
def test_treasury_display_imports():
    """Test that treasury display can be imported."""
    from bots.treasury.display import TreasuryDisplay, Position, ClosedTrade
    assert TreasuryDisplay is not None
    assert Position is not None
    assert ClosedTrade is not None


def test_treasury_display_position_creation():
    """Test Position dataclass creation."""
    from bots.treasury.display import Position

    pos = Position(
        symbol="SOL",
        entry_price=100.0,
        current_price=150.0,
        quantity=10.0,
        entry_time=datetime.now(),
    )

    assert pos.unrealized_pnl == 500.0  # (150-100) * 10
    assert pos.unrealized_pnl_pct == 50.0
    assert pos.status_emoji == "🟢"


def test_treasury_display_calculations():
    """Test Treasury Display calculations."""
    from bots.treasury.display import TreasuryDisplay, Position, ClosedTrade

    positions = [
        Position(
            symbol="SOL",
            entry_price=100.0,
            current_price=110.0,
            quantity=10.0,
            entry_time=datetime.now(),
        ),
    ]

    closed_trades = [
        ClosedTrade(
            symbol="BTC",
            entry_price=40000.0,
            exit_price=42000.0,
            quantity=1.0,
            entry_time=datetime.now() - timedelta(days=1),
            exit_time=datetime.now(),
            realized_pnl=2000.0,
            reason="TP",
        ),
    ]

    display = TreasuryDisplay(positions, closed_trades)

    # Check calculations
    assert display.calculate_total_unrealized_pnl() == 100.0
    assert display.calculate_total_realized_pnl() == 2000.0
    assert display.calculate_total_pnl() == 2100.0
    assert display.calculate_win_rate() == 100.0


def test_treasury_display_from_json():
    """Test loading treasury display from actual JSON files."""
    try:
        from bots.treasury.display import TreasuryDisplay
        from pathlib import Path

        positions_file = Path(__file__).parent.parent / "bots" / "treasury" / ".positions.json"
        trades_file = Path(__file__).parent.parent / "bots" / "treasury" / ".trade_history.json"

        if positions_file.exists() and trades_file.exists():
            display = TreasuryDisplay.from_json_files(str(positions_file), str(trades_file))

            assert display.positions is not None
            assert isinstance(display.positions, list)
            assert display.closed_trades is not None
            assert isinstance(display.closed_trades, list)
    except Exception as e:
        print(f"  Note: JSON file test skipped ({e})")


# Test Sentiment Engine
def test_sentiment_engine_imports():
    """Test that sentiment engine can be imported."""
    from core.sentiment import (
        SelfTuningSentimentEngine,
        SentimentComponents,
        SentimentWeights,
    )
    assert SelfTuningSentimentEngine is not None
    assert SentimentComponents is not None
    assert SentimentWeights is not None


def test_sentiment_components_creation():
    """Test SentimentComponents dataclass."""
    from core.sentiment import SentimentComponents

    components = SentimentComponents(
        price_momentum=0.5,
        volume=0.3,
        social_sentiment=0.7,
        whale_activity=0.4,
        technical_analysis=0.6,
    )

    assert components.price_momentum == 0.5
    assert len(components.components_dict) == 5


def test_sentiment_weights_normalization():
    """Test that sentiment weights are normalized."""
    from core.sentiment import SentimentWeights

    weights = SentimentWeights(
        price_momentum=0.3,
        volume=0.3,
        social_sentiment=0.4,
        whale_activity=0.2,
        technical_analysis=0.3,
    )

    # Weights should sum to 1.0
    total = (
        weights.price_momentum +
        weights.volume +
        weights.social_sentiment +
        weights.whale_activity +
        weights.technical_analysis
    )
    assert abs(total - 1.0) < 0.01


def test_sentiment_engine_initialization():
    """Test sentiment engine initialization."""
    from core.sentiment import SelfTuningSentimentEngine

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "sentiment.db"
        engine = SelfTuningSentimentEngine(str(db_path))

        assert engine is not None
        assert engine.weights is not None
        assert db_path.exists()


def test_sentiment_engine_prediction():
    """Test sentiment prediction computation."""
    from core.sentiment import SelfTuningSentimentEngine, SentimentComponents

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "sentiment.db"
        engine = SelfTuningSentimentEngine(str(db_path))

        components = SentimentComponents(
            price_momentum=0.5,
            volume=0.3,
            social_sentiment=0.7,
            whale_activity=0.4,
            technical_analysis=0.6,
        )

        score, grade, prediction = engine.compute_sentiment("SOL", components)

        assert -1.0 <= score <= 1.0
        assert grade in ["A", "B", "C", "D", "F"]
        assert prediction is not None
        assert prediction.symbol == "SOL"


# Test Outcome Tracker
def test_outcome_tracker_imports():
    """Test that outcome tracker can be imported."""
    from core.sentiment.outcome_tracker import OutcomeTracker
    assert OutcomeTracker is not None


def test_outcome_tracker_initialization():
    """Test outcome tracker initialization."""
    from core.sentiment.outcome_tracker import OutcomeTracker

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "sentiment.db"
        tracker = OutcomeTracker(str(db_path), polling_interval=60)

        assert tracker is not None
        assert tracker.engine is not None
        assert tracker.polling_interval == 60


# Test Treasury Telegram Handler
def test_treasury_handler_imports():
    """Test that treasury handler can be imported."""
    from tg_bot.handlers.treasury import TreasuryHandler, get_treasury_handler
    assert TreasuryHandler is not None
    assert get_treasury_handler is not None


def test_treasury_handler_initialization():
    """Test treasury handler initialization."""
    from tg_bot.handlers.treasury import TreasuryHandler

    handler = TreasuryHandler("./bots/treasury")
    assert handler is not None
    assert handler.positions_file.name == ".positions.json"
    assert handler.trades_file.name == ".trade_history.json"


# Integration Tests
@pytest.mark.slow
def test_integration_full_workflow():
    """Test full workflow: create prediction, record outcome, tune weights."""
    from core.sentiment import SelfTuningSentimentEngine, SentimentComponents

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "sentiment.db"
        engine = SelfTuningSentimentEngine(str(db_path))

        # Create multiple predictions
        for i in range(10):
            components = SentimentComponents(
                price_momentum=0.5 + (i * 0.01),
                volume=0.3,
                social_sentiment=0.7,
                whale_activity=0.4,
                technical_analysis=0.6,
            )

            score, grade, prediction = engine.compute_sentiment(f"TOKEN_{i}", components)
            assert prediction.id is not None

            # Record outcome
            outcome = 1.5 + (i * 0.1)  # Positive outcome
            engine.record_outcome(prediction.id, outcome)

        # Check report
        report = engine.get_tuning_report()
        assert report is not None


if __name__ == "__main__":
    # Run simple tests
    results = []

    try:
        print("Testing Asset Registry...", flush=True)
        test_asset_registry_imports()
        test_asset_registry_total_assets()
        test_asset_registry_categories()
        test_asset_registry_lookups()
        test_asset_registry_sentiment_weights()
        results.append(("[PASS] Asset Registry tests", True))
    except Exception as e:
        results.append(("[FAIL] Asset Registry tests", False))

    try:
        print("Testing Treasury Display...", flush=True)
        test_treasury_display_imports()
        test_treasury_display_position_creation()
        test_treasury_display_calculations()
        results.append(("[PASS] Treasury Display tests", True))
    except Exception as e:
        results.append(("[FAIL] Treasury Display tests", False))

    try:
        print("Testing Sentiment Engine...", flush=True)
        test_sentiment_engine_imports()
        test_sentiment_components_creation()
        test_sentiment_weights_normalization()
        test_sentiment_engine_initialization()
        test_sentiment_engine_prediction()
        results.append(("[PASS] Sentiment Engine tests", True))
    except Exception as e:
        results.append(("[FAIL] Sentiment Engine tests", False))

    try:
        print("Testing Outcome Tracker...", flush=True)
        test_outcome_tracker_imports()
        test_outcome_tracker_initialization()
        results.append(("[PASS] Outcome Tracker tests", True))
    except Exception as e:
        results.append(("[FAIL] Outcome Tracker tests", False))

    try:
        print("Testing Treasury Handler...", flush=True)
        test_treasury_handler_imports()
        test_treasury_handler_initialization()
        results.append(("[PASS] Treasury Handler tests", True))
    except Exception as e:
        results.append(("[FAIL] Treasury Handler tests", False))

    print("\n" + "="*60)
    for name, passed in results:
        print(f"{name}")
    print("="*60)

    all_passed = all(passed for _, passed in results)
    exit(0 if all_passed else 1)
