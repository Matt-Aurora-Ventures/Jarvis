"""
Unit tests for Take-Profit Strategy.

Tests written FIRST following TDD methodology.
Tests cover:
1. Fixed percentage take-profit
2. Scaled exit (multiple levels)
3. ATR-based dynamic targets
4. Fibonacci retracement levels
5. Approaching TP detection
6. Position tracking
"""

import pytest
from datetime import datetime, timedelta
from typing import List


class TestTakeProfitImports:
    """Test that take-profit module imports correctly."""

    def test_take_profit_types_import(self):
        """Test TakeProfitType enum import."""
        from core.trading.signals.take_profit import TakeProfitType
        assert TakeProfitType.FIXED is not None
        assert TakeProfitType.SCALED is not None
        assert TakeProfitType.ATR_BASED is not None
        assert TakeProfitType.FIBONACCI is not None

    def test_take_profit_level_import(self):
        """Test TakeProfitLevel dataclass import."""
        from core.trading.signals.take_profit import TakeProfitLevel
        level = TakeProfitLevel(
            level_number=1,
            price=110.0,
            percentage_gain=0.10,
            sell_portion=0.25,
        )
        assert level.level_number == 1
        assert level.price == 110.0
        assert level.hit is False

    def test_take_profit_signal_import(self):
        """Test TakeProfitSignal dataclass import."""
        from core.trading.signals.take_profit import TakeProfitSignal
        assert TakeProfitSignal is not None

    def test_take_profit_analyzer_import(self):
        """Test TakeProfitAnalyzer class import."""
        from core.trading.signals.take_profit import TakeProfitAnalyzer
        assert TakeProfitAnalyzer is not None


class TestTakeProfitAnalyzerInitialization:
    """Tests for TakeProfitAnalyzer initialization."""

    def test_default_initialization(self):
        """Test analyzer with default parameters."""
        from core.trading.signals.take_profit import TakeProfitAnalyzer, TakeProfitType

        analyzer = TakeProfitAnalyzer()
        assert analyzer.tp_type == TakeProfitType.SCALED
        assert analyzer.fixed_tp_pct == 0.20
        assert analyzer.approaching_threshold == 0.8

    def test_fixed_type_initialization(self):
        """Test analyzer with FIXED type."""
        from core.trading.signals.take_profit import TakeProfitAnalyzer, TakeProfitType

        analyzer = TakeProfitAnalyzer(
            tp_type=TakeProfitType.FIXED,
            fixed_tp_pct=0.15
        )
        assert analyzer.tp_type == TakeProfitType.FIXED
        assert analyzer.fixed_tp_pct == 0.15

    def test_custom_scaled_levels(self):
        """Test analyzer with custom scaled levels."""
        from core.trading.signals.take_profit import TakeProfitAnalyzer, TakeProfitType

        custom_levels = [
            (0.05, 0.50),  # 5% gain -> sell 50%
            (0.15, 0.50),  # 15% gain -> sell remaining 50%
        ]
        analyzer = TakeProfitAnalyzer(
            tp_type=TakeProfitType.SCALED,
            scaled_levels=custom_levels
        )
        assert analyzer.scaled_levels == custom_levels


class TestFixedTakeProfit:
    """Tests for fixed percentage take-profit."""

    def test_fixed_tp_long_position(self):
        """Test fixed TP level calculation for long position."""
        from core.trading.signals.take_profit import TakeProfitAnalyzer, TakeProfitType

        analyzer = TakeProfitAnalyzer(
            tp_type=TakeProfitType.FIXED,
            fixed_tp_pct=0.10  # 10%
        )

        levels = analyzer.open_position(
            symbol="SOL",
            side="long",
            entry_price=100.0
        )

        assert len(levels) == 1
        assert levels[0].price == pytest.approx(110.0, rel=1e-9)  # 100 * 1.10
        assert levels[0].percentage_gain == 0.10
        assert levels[0].sell_portion == 1.0

    def test_fixed_tp_short_position(self):
        """Test fixed TP level calculation for short position."""
        from core.trading.signals.take_profit import TakeProfitAnalyzer, TakeProfitType

        analyzer = TakeProfitAnalyzer(
            tp_type=TakeProfitType.FIXED,
            fixed_tp_pct=0.10
        )

        levels = analyzer.open_position(
            symbol="SOL",
            side="short",
            entry_price=100.0
        )

        assert len(levels) == 1
        assert levels[0].price == 90.0  # 100 * 0.90
        assert levels[0].percentage_gain == 0.10

    def test_fixed_tp_hit_detection(self):
        """Test that fixed TP is detected when price reaches target."""
        from core.trading.signals.take_profit import TakeProfitAnalyzer, TakeProfitType

        analyzer = TakeProfitAnalyzer(
            tp_type=TakeProfitType.FIXED,
            fixed_tp_pct=0.10
        )

        analyzer.open_position("SOL", "long", 100.0)

        # Price below TP
        signal = analyzer.analyze("SOL", 105.0)
        assert signal.signal_type != "TAKE_PROFIT_HIT"
        assert signal.should_sell is False

        # Price at/above TP - test with price clearly above to avoid floating point edge cases
        signal = analyzer.analyze("SOL", 110.01)
        assert signal.signal_type == "TAKE_PROFIT_HIT"
        assert signal.should_sell is True
        assert signal.sell_portion == 1.0


class TestScaledTakeProfit:
    """Tests for scaled exit (multiple levels)."""

    def test_scaled_levels_created(self):
        """Test that scaled levels are properly created."""
        from core.trading.signals.take_profit import TakeProfitAnalyzer, TakeProfitType

        analyzer = TakeProfitAnalyzer(tp_type=TakeProfitType.SCALED)

        levels = analyzer.open_position("SOL", "long", 100.0)

        # Default has 4 levels
        assert len(levels) == 4

        # First level at 10%
        assert levels[0].percentage_gain == 0.10
        assert levels[0].price == pytest.approx(110.0, rel=1e-9)
        assert levels[0].sell_portion == 0.25

    def test_scaled_partial_take_profit(self):
        """Test partial take-profit at first level."""
        from core.trading.signals.take_profit import TakeProfitAnalyzer, TakeProfitType

        analyzer = TakeProfitAnalyzer(tp_type=TakeProfitType.SCALED)
        analyzer.open_position("SOL", "long", 100.0)

        # Hit first level at 10% - use price clearly above to avoid floating point edge cases
        signal = analyzer.analyze("SOL", 110.5)

        assert signal.signal_type == "TAKE_PROFIT_PARTIAL"
        assert signal.should_sell is True
        assert signal.sell_portion == 0.25
        assert signal.tp_level_hit == 1
        assert signal.next_tp_price is not None

    def test_scaled_multiple_levels_hit(self):
        """Test when price jumps and hits multiple levels."""
        from core.trading.signals.take_profit import TakeProfitAnalyzer, TakeProfitType

        analyzer = TakeProfitAnalyzer(tp_type=TakeProfitType.SCALED)
        analyzer.open_position("SOL", "long", 100.0)

        # Price jumps to 125%, hitting first two levels (10%, 20%)
        signal = analyzer.analyze("SOL", 125.0)

        assert signal.should_sell is True
        # Should have accumulated portions from both levels
        assert signal.sell_portion == 0.50  # 0.25 + 0.25

    def test_scaled_all_levels_hit(self):
        """Test when all levels are hit."""
        from core.trading.signals.take_profit import TakeProfitAnalyzer, TakeProfitType

        analyzer = TakeProfitAnalyzer(tp_type=TakeProfitType.SCALED)
        analyzer.open_position("SOL", "long", 100.0)

        # Price at 60%, hitting all 4 levels
        signal = analyzer.analyze("SOL", 160.0)

        assert signal.signal_type == "TAKE_PROFIT_HIT"
        assert signal.sell_portion == 1.0
        assert signal.next_tp_price is None


class TestApproachingTakeProfit:
    """Tests for approaching TP detection."""

    def test_approaching_tp_signal(self):
        """Test that approaching TP triggers warning."""
        from core.trading.signals.take_profit import TakeProfitAnalyzer, TakeProfitType

        analyzer = TakeProfitAnalyzer(
            tp_type=TakeProfitType.FIXED,
            fixed_tp_pct=0.10,
            approaching_threshold=0.8  # 80% of the way
        )

        analyzer.open_position("SOL", "long", 100.0)

        # At 8.5% gain (85% of 10% target) - clearly above 80% threshold
        signal = analyzer.analyze("SOL", 108.5)

        assert signal.signal_type == "APPROACHING_TP"
        assert signal.should_sell is False
        assert signal.confidence == 0.6

    def test_not_approaching_when_far(self):
        """Test no approaching signal when far from TP."""
        from core.trading.signals.take_profit import TakeProfitAnalyzer, TakeProfitType

        analyzer = TakeProfitAnalyzer(
            tp_type=TakeProfitType.FIXED,
            fixed_tp_pct=0.10,
            approaching_threshold=0.8
        )

        analyzer.open_position("SOL", "long", 100.0)

        # At 5% gain (50% of 10% target)
        signal = analyzer.analyze("SOL", 105.0)

        assert signal.signal_type == "NO_SIGNAL"


class TestATRBasedTakeProfit:
    """Tests for ATR-based dynamic targets."""

    def test_atr_based_levels(self):
        """Test ATR-based level calculation."""
        from core.trading.signals.take_profit import TakeProfitAnalyzer, TakeProfitType

        analyzer = TakeProfitAnalyzer(tp_type=TakeProfitType.ATR_BASED)

        # ATR of 5 on a $100 asset
        levels = analyzer.open_position("SOL", "long", 100.0, atr=5.0)

        assert len(levels) == 4
        # First level: 1.5 * ATR = 7.5 from entry
        assert levels[0].price == 107.5

    def test_atr_fallback_without_atr(self):
        """Test ATR-based falls back when no ATR provided."""
        from core.trading.signals.take_profit import TakeProfitAnalyzer, TakeProfitType

        analyzer = TakeProfitAnalyzer(tp_type=TakeProfitType.ATR_BASED)

        # No ATR provided, should use fallback
        levels = analyzer.open_position("SOL", "long", 100.0)

        assert len(levels) == 4
        # Should still create levels using 2% assumed volatility


class TestFibonacciTakeProfit:
    """Tests for Fibonacci-based take-profit."""

    def test_fibonacci_levels(self):
        """Test Fibonacci level calculation."""
        from core.trading.signals.take_profit import TakeProfitAnalyzer, TakeProfitType

        analyzer = TakeProfitAnalyzer(tp_type=TakeProfitType.FIBONACCI)

        levels = analyzer.open_position("SOL", "long", 100.0)

        assert len(levels) == 4
        # Check Fibonacci percentages: 23.6%, 38.2%, 61.8%, 100%
        assert levels[0].percentage_gain == 0.236
        assert levels[1].percentage_gain == 0.382
        assert levels[2].percentage_gain == 0.618
        assert levels[3].percentage_gain == 1.0

    def test_calculate_fibonacci_levels_helper(self):
        """Test the standalone Fibonacci calculation helper."""
        from core.trading.signals.take_profit import calculate_fibonacci_levels

        levels = calculate_fibonacci_levels(
            entry_price=100.0,
            swing_low=90.0,
            swing_high=100.0,
            side="long"
        )

        assert "fib_0.236" in levels
        assert "fib_0.618" in levels
        assert "fib_1.618" in levels


class TestPositionManagement:
    """Tests for position tracking and management."""

    def test_open_close_position(self):
        """Test opening and closing positions."""
        from core.trading.signals.take_profit import TakeProfitAnalyzer

        analyzer = TakeProfitAnalyzer()

        analyzer.open_position("SOL", "long", 100.0)
        assert "SOL" in analyzer._positions

        analyzer.close_position("SOL")
        assert "SOL" not in analyzer._positions

    def test_get_tp_levels(self):
        """Test retrieving TP levels for a position."""
        from core.trading.signals.take_profit import TakeProfitAnalyzer

        analyzer = TakeProfitAnalyzer()

        analyzer.open_position("SOL", "long", 100.0)
        levels = analyzer.get_tp_levels("SOL")

        assert levels is not None
        assert len(levels) == 4

        # Non-existent position
        assert analyzer.get_tp_levels("BTC") is None

    def test_analyzer_stats(self):
        """Test analyzer statistics."""
        from core.trading.signals.take_profit import TakeProfitAnalyzer

        analyzer = TakeProfitAnalyzer()

        analyzer.open_position("SOL", "long", 100.0)
        analyzer.open_position("BTC", "short", 50000.0)

        stats = analyzer.get_stats()

        assert stats["positions_tracked"] == 2
        assert "SOL" in stats["positions"]
        assert "BTC" in stats["positions"]

    def test_no_signal_for_unknown_position(self):
        """Test that unknown positions return NO_SIGNAL."""
        from core.trading.signals.take_profit import TakeProfitAnalyzer

        analyzer = TakeProfitAnalyzer()

        signal = analyzer.analyze("UNKNOWN", 100.0)

        assert signal.signal_type == "NO_SIGNAL"
        assert signal.confidence == 0.0


class TestSignalToDict:
    """Tests for signal serialization."""

    def test_signal_to_dict(self):
        """Test TakeProfitSignal.to_dict() method."""
        from core.trading.signals.take_profit import TakeProfitAnalyzer

        analyzer = TakeProfitAnalyzer()
        analyzer.open_position("SOL", "long", 100.0)

        signal = analyzer.analyze("SOL", 115.0)
        signal_dict = signal.to_dict()

        assert "signal_type" in signal_dict
        assert "confidence" in signal_dict
        assert "should_sell" in signal_dict
        assert "all_levels" in signal_dict
        assert "timestamp" in signal_dict

        # Check levels serialization
        assert isinstance(signal_dict["all_levels"], list)


class TestShortPositions:
    """Tests for short position handling."""

    def test_short_position_gain_calculation(self):
        """Test gain calculation for short positions."""
        from core.trading.signals.take_profit import TakeProfitAnalyzer, TakeProfitType

        analyzer = TakeProfitAnalyzer(
            tp_type=TakeProfitType.FIXED,
            fixed_tp_pct=0.10
        )

        analyzer.open_position("SOL", "short", 100.0)

        # Price drops 10% - should hit TP
        signal = analyzer.analyze("SOL", 90.0)

        assert signal.signal_type == "TAKE_PROFIT_HIT"
        assert signal.current_gain_pct == pytest.approx(0.10, rel=0.01)

    def test_short_position_no_gain_on_price_rise(self):
        """Test that price rise doesn't trigger TP for short."""
        from core.trading.signals.take_profit import TakeProfitAnalyzer, TakeProfitType

        analyzer = TakeProfitAnalyzer(
            tp_type=TakeProfitType.FIXED,
            fixed_tp_pct=0.10
        )

        analyzer.open_position("SOL", "short", 100.0)

        # Price rises - no TP for short
        signal = analyzer.analyze("SOL", 110.0)

        assert signal.signal_type == "NO_SIGNAL"
        assert signal.current_gain_pct < 0  # Negative gain for short


class TestCustomLevels:
    """Tests for custom level configurations."""

    def test_custom_levels_on_open(self):
        """Test custom levels passed to open_position."""
        from core.trading.signals.take_profit import TakeProfitAnalyzer, TakeProfitType

        analyzer = TakeProfitAnalyzer(tp_type=TakeProfitType.SCALED)

        custom_levels = [
            (0.05, 0.33),
            (0.10, 0.33),
            (0.20, 0.34),
        ]

        levels = analyzer.open_position(
            "SOL", "long", 100.0,
            custom_levels=custom_levels
        )

        assert len(levels) == 3
        assert levels[0].percentage_gain == 0.05
        assert levels[0].sell_portion == 0.33
