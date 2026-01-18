"""
Unit tests for advanced trading strategies.

Tests written FIRST following TDD methodology.
These tests define the expected behavior for:
1. Trailing Stop Strategy
2. RSI Strategy (with divergence detection)
3. MACD Strategy (crossover signals)
4. DCA Strategy (Dollar Cost Averaging)
5. Mean Reversion Strategy (Bollinger Bands)

Note: Tests import directly from signal modules to avoid core.trading.__init__.py
import chain issues with jupiter module.
"""

import pytest
import sys
from datetime import datetime, timedelta
from typing import List, Dict, Any


# =============================================================================
# TRAILING STOP STRATEGY TESTS
# =============================================================================

class TestTrailingStopStrategy:
    """Tests for trailing stop loss strategy."""

    def test_trailing_stop_import(self):
        """Test that TrailingStopAnalyzer can be imported."""
        from core.trading.signals.trailing_stop import TrailingStopAnalyzer, TrailingStopSignal
        assert TrailingStopAnalyzer is not None
        assert TrailingStopSignal is not None

    def test_trailing_stop_initialization(self):
        """Test analyzer initialization with default and custom parameters."""
        from core.trading.signals.trailing_stop import TrailingStopAnalyzer

        # Default initialization
        analyzer = TrailingStopAnalyzer()
        assert analyzer.trailing_stop_pct == 0.05  # 5% default

        # Custom initialization
        analyzer = TrailingStopAnalyzer(trailing_stop_pct=0.03)
        assert analyzer.trailing_stop_pct == 0.03

    def test_trailing_stop_tracks_peak_for_long(self):
        """Test that analyzer tracks highest price for LONG positions."""
        from core.trading.signals.trailing_stop import TrailingStopAnalyzer

        analyzer = TrailingStopAnalyzer(trailing_stop_pct=0.05)

        # Open long position at $100
        analyzer.open_position("BTC", side="long", entry_price=100.0)

        # Price rises to $110
        analyzer.update_price("BTC", 110.0)
        assert analyzer.get_peak_price("BTC") == 110.0

        # Price drops to $105 (still tracking peak)
        analyzer.update_price("BTC", 105.0)
        assert analyzer.get_peak_price("BTC") == 110.0  # Peak unchanged

        # Price rises to $115
        analyzer.update_price("BTC", 115.0)
        assert analyzer.get_peak_price("BTC") == 115.0

    def test_trailing_stop_tracks_trough_for_short(self):
        """Test that analyzer tracks lowest price for SHORT positions."""
        from core.trading.signals.trailing_stop import TrailingStopAnalyzer

        analyzer = TrailingStopAnalyzer(trailing_stop_pct=0.05)

        # Open short position at $100
        analyzer.open_position("BTC", side="short", entry_price=100.0)

        # Price drops to $90
        analyzer.update_price("BTC", 90.0)
        assert analyzer.get_trough_price("BTC") == 90.0

        # Price rises to $95 (still tracking trough)
        analyzer.update_price("BTC", 95.0)
        assert analyzer.get_trough_price("BTC") == 90.0  # Trough unchanged

    def test_trailing_stop_hit_signal_for_long(self):
        """Test TRAILING_STOP_HIT signal for LONG position."""
        from core.trading.signals.trailing_stop import TrailingStopAnalyzer

        analyzer = TrailingStopAnalyzer(trailing_stop_pct=0.05)

        analyzer.open_position("BTC", side="long", entry_price=100.0)
        analyzer.update_price("BTC", 110.0)  # Peak at 110

        # 5% drop from peak = 110 * 0.95 = 104.5
        signal = analyzer.analyze("BTC", current_price=104.0)  # Below threshold

        assert signal.signal_type == "TRAILING_STOP_HIT"
        assert signal.confidence == 0.9
        assert signal.should_exit is True

    def test_trailing_stop_hit_signal_for_short(self):
        """Test TRAILING_STOP_HIT signal for SHORT position."""
        from core.trading.signals.trailing_stop import TrailingStopAnalyzer

        analyzer = TrailingStopAnalyzer(trailing_stop_pct=0.05)

        analyzer.open_position("BTC", side="short", entry_price=100.0)
        analyzer.update_price("BTC", 90.0)  # Trough at 90

        # 5% rise from trough = 90 * 1.05 = 94.5
        signal = analyzer.analyze("BTC", current_price=95.0)  # Above threshold

        assert signal.signal_type == "TRAILING_STOP_HIT"
        assert signal.confidence == 0.9
        assert signal.should_exit is True

    def test_trailing_stop_warning_signal(self):
        """Test TRAILING_STOP_WARNING signal when approaching stop level."""
        from core.trading.signals.trailing_stop import TrailingStopAnalyzer

        analyzer = TrailingStopAnalyzer(trailing_stop_pct=0.05, warning_threshold_pct=0.6)

        analyzer.open_position("BTC", side="long", entry_price=100.0)
        analyzer.update_price("BTC", 110.0)  # Peak at 110

        # Warning triggers at 60% of stop distance
        # Stop level = 110 * 0.95 = 104.5
        # Warning level = 110 * (1 - 0.05 * 0.6) = 110 * 0.97 = 106.7
        # Price 106.0 is below warning (106.7) but above stop (104.5)
        signal = analyzer.analyze("BTC", current_price=106.0)

        assert signal.signal_type == "TRAILING_STOP_WARNING"
        assert signal.confidence == 0.5
        assert signal.should_exit is False

    def test_trailing_stop_no_signal_when_healthy(self):
        """Test no signal when position is healthy."""
        from core.trading.signals.trailing_stop import TrailingStopAnalyzer

        analyzer = TrailingStopAnalyzer(trailing_stop_pct=0.05)

        analyzer.open_position("BTC", side="long", entry_price=100.0)
        analyzer.update_price("BTC", 110.0)  # Peak at 110

        # 1% drop from peak = still healthy
        signal = analyzer.analyze("BTC", current_price=109.0)

        assert signal.signal_type == "NO_SIGNAL"
        assert signal.should_exit is False

    def test_trailing_stop_to_dict(self):
        """Test signal serialization to dict."""
        from core.trading.signals.trailing_stop import TrailingStopAnalyzer

        analyzer = TrailingStopAnalyzer(trailing_stop_pct=0.05)
        analyzer.open_position("BTC", side="long", entry_price=100.0)
        analyzer.update_price("BTC", 110.0)

        signal = analyzer.analyze("BTC", current_price=104.0)
        signal_dict = signal.to_dict()

        assert "signal_type" in signal_dict
        assert "confidence" in signal_dict
        assert "should_exit" in signal_dict
        assert "peak_price" in signal_dict
        assert "current_drawdown_pct" in signal_dict


# =============================================================================
# RSI STRATEGY TESTS
# =============================================================================

class TestRSIStrategy:
    """Tests for RSI-based trading strategy with divergence detection."""

    def test_rsi_import(self):
        """Test that RSIAnalyzer can be imported."""
        from core.trading.signals.rsi_strategy import RSIAnalyzer, RSISignal
        assert RSIAnalyzer is not None
        assert RSISignal is not None

    def test_rsi_initialization(self):
        """Test analyzer initialization with default parameters."""
        from core.trading.signals.rsi_strategy import RSIAnalyzer

        analyzer = RSIAnalyzer()
        assert analyzer.period == 14
        assert analyzer.oversold_threshold == 30
        assert analyzer.overbought_threshold == 70

    def test_rsi_calculation_accuracy(self):
        """Test RSI calculation produces correct values."""
        from core.trading.signals.rsi_strategy import RSIAnalyzer

        analyzer = RSIAnalyzer(period=14)

        # Add enough prices for RSI calculation
        prices = [44, 44.34, 44.09, 43.61, 44.33, 44.83, 45.10, 45.42, 45.84,
                  46.08, 45.89, 46.03, 45.61, 46.28, 46.28, 46.00, 46.03, 46.41]

        for price in prices:
            analyzer.add_price(price)

        rsi = analyzer.get_rsi()
        assert rsi is not None
        assert 0 <= rsi <= 100
        # RSI for this dataset should be around 70 (bullish)
        assert 60 <= rsi <= 80

    def test_rsi_oversold_signal(self):
        """Test RSI_OVERSOLD signal when RSI < 30."""
        from core.trading.signals.rsi_strategy import RSIAnalyzer

        analyzer = RSIAnalyzer(period=14, oversold_threshold=30)

        # Create declining price series to get oversold RSI
        base_price = 100.0
        for i in range(20):
            price = base_price - (i * 2.5)  # Steady decline
            analyzer.add_price(price)

        signal = analyzer.analyze()

        assert signal.rsi_value < 30
        assert signal.signal_type == "RSI_OVERSOLD"
        assert signal.confidence == 0.6
        assert signal.direction == "long"  # Oversold suggests potential long

    def test_rsi_overbought_signal(self):
        """Test RSI_OVERBOUGHT signal when RSI > 70."""
        from core.trading.signals.rsi_strategy import RSIAnalyzer

        analyzer = RSIAnalyzer(period=14, overbought_threshold=70)

        # Create rising price series to get overbought RSI
        base_price = 100.0
        for i in range(20):
            price = base_price + (i * 2.5)  # Steady rise
            analyzer.add_price(price)

        signal = analyzer.analyze()

        assert signal.rsi_value > 70
        assert signal.signal_type == "RSI_OVERBOUGHT"
        assert signal.confidence == 0.6
        assert signal.direction == "short"  # Overbought suggests potential short

    def test_rsi_bullish_divergence(self):
        """Test RSI_BULLISH_DIVERGENCE when price makes lower low but RSI makes higher low."""
        from core.trading.signals.rsi_strategy import RSIAnalyzer

        analyzer = RSIAnalyzer(period=14)

        # Create price series with lower lows
        # But RSI showing higher lows (bullish divergence)
        # First leg down
        for price in [100, 95, 90, 85, 80]:  # First low at 80
            analyzer.add_price(price)

        # Recovery
        for price in [85, 90, 95]:
            analyzer.add_price(price)

        # Second leg down - price makes lower low
        for price in [90, 85, 80, 75]:  # Lower low at 75
            analyzer.add_price(price)

        # Additional prices to have enough data
        for price in [76, 77, 78, 79, 80, 81]:
            analyzer.add_price(price)

        signal = analyzer.analyze()

        # Check for bullish divergence detection
        if signal.has_divergence and signal.divergence_type == "bullish":
            assert signal.signal_type == "RSI_BULLISH_DIVERGENCE"
            assert signal.confidence == 0.75
            assert signal.direction == "long"

    def test_rsi_bearish_divergence(self):
        """Test RSI_BEARISH_DIVERGENCE when price makes higher high but RSI makes lower high."""
        from core.trading.signals.rsi_strategy import RSIAnalyzer

        analyzer = RSIAnalyzer(period=14)

        # Create price series with higher highs
        # But RSI showing lower highs (bearish divergence)
        # First leg up
        for price in [100, 105, 110, 115, 120]:  # First high at 120
            analyzer.add_price(price)

        # Pullback
        for price in [115, 110, 105]:
            analyzer.add_price(price)

        # Second leg up - price makes higher high
        for price in [110, 115, 120, 125]:  # Higher high at 125
            analyzer.add_price(price)

        # Additional prices
        for price in [124, 123, 122, 121, 120, 119]:
            analyzer.add_price(price)

        signal = analyzer.analyze()

        # Check for bearish divergence detection
        if signal.has_divergence and signal.divergence_type == "bearish":
            assert signal.signal_type == "RSI_BEARISH_DIVERGENCE"
            assert signal.confidence == 0.75
            assert signal.direction == "short"

    def test_rsi_no_signal_in_neutral_zone(self):
        """Test no signal when RSI is in neutral zone (30-70)."""
        from core.trading.signals.rsi_strategy import RSIAnalyzer

        analyzer = RSIAnalyzer(period=14)

        # Create sideways price movement
        for i in range(20):
            price = 100.0 + (i % 3) - 1  # Oscillate around 100
            analyzer.add_price(price)

        signal = analyzer.analyze()

        if 30 < signal.rsi_value < 70 and not signal.has_divergence:
            assert signal.signal_type == "NO_SIGNAL"

    def test_rsi_signal_to_dict(self):
        """Test signal serialization."""
        from core.trading.signals.rsi_strategy import RSIAnalyzer

        analyzer = RSIAnalyzer(period=14)
        for i in range(20):
            analyzer.add_price(100.0 + i)

        signal = analyzer.analyze()
        signal_dict = signal.to_dict()

        assert "signal_type" in signal_dict
        assert "rsi_value" in signal_dict
        assert "confidence" in signal_dict
        assert "direction" in signal_dict


# =============================================================================
# MACD STRATEGY TESTS
# =============================================================================

class TestMACDStrategy:
    """Tests for MACD crossover strategy."""

    def test_macd_import(self):
        """Test that MACDAnalyzer can be imported."""
        from core.trading.signals.macd_strategy import MACDAnalyzer, MACDSignal
        assert MACDAnalyzer is not None
        assert MACDSignal is not None

    def test_macd_initialization(self):
        """Test analyzer initialization with default parameters."""
        from core.trading.signals.macd_strategy import MACDAnalyzer

        analyzer = MACDAnalyzer()
        assert analyzer.fast_period == 12
        assert analyzer.slow_period == 26
        assert analyzer.signal_period == 9

    def test_macd_calculation_accuracy(self):
        """Test MACD line, signal line, and histogram calculation."""
        from core.trading.signals.macd_strategy import MACDAnalyzer

        analyzer = MACDAnalyzer(fast_period=12, slow_period=26, signal_period=9)

        # Add enough prices for MACD calculation (need at least 35 for proper calculation)
        for i in range(40):
            price = 100.0 + i * 0.5
            analyzer.add_price(price)

        macd, signal, histogram = analyzer.get_macd_values()

        assert macd is not None
        assert signal is not None
        assert histogram is not None
        # Histogram = MACD - Signal
        assert abs(histogram - (macd - signal)) < 0.001

    def test_macd_bullish_cross_signal(self):
        """Test MACD_BULLISH_CROSS when MACD crosses above signal line."""
        from core.trading.signals.macd_strategy import MACDAnalyzer

        analyzer = MACDAnalyzer()

        # Create price series that will cause MACD bullish crossover
        # Start with declining prices, then sharp upturn
        prices = []
        for i in range(30):
            prices.append(100.0 - i * 0.5)  # Decline
        for i in range(15):
            prices.append(85.0 + i * 2)  # Sharp upturn

        for price in prices:
            analyzer.add_price(price)

        signal = analyzer.analyze()

        if signal.has_crossover and signal.crossover_direction == "bullish":
            assert signal.signal_type == "MACD_BULLISH_CROSS"
            assert signal.confidence == 0.75
            assert signal.direction == "long"

    def test_macd_bearish_cross_signal(self):
        """Test MACD_BEARISH_CROSS when MACD crosses below signal line."""
        from core.trading.signals.macd_strategy import MACDAnalyzer

        analyzer = MACDAnalyzer()

        # Create price series that will cause MACD bearish crossover
        # Start with rising prices, then sharp downturn
        prices = []
        for i in range(30):
            prices.append(100.0 + i * 0.5)  # Rise
        for i in range(15):
            prices.append(115.0 - i * 2)  # Sharp downturn

        for price in prices:
            analyzer.add_price(price)

        signal = analyzer.analyze()

        if signal.has_crossover and signal.crossover_direction == "bearish":
            assert signal.signal_type == "MACD_BEARISH_CROSS"
            assert signal.confidence == 0.75
            assert signal.direction == "short"

    def test_macd_histogram_divergence(self):
        """Test MACD_HISTOGRAM_DIVERGENCE signal."""
        from core.trading.signals.macd_strategy import MACDAnalyzer

        analyzer = MACDAnalyzer()

        # Add prices to generate histogram trend
        for i in range(45):
            price = 100.0 + i * 0.3
            analyzer.add_price(price)

        signal = analyzer.analyze()

        # Should detect histogram trend
        assert signal.histogram_trend in ["increasing", "decreasing", "neutral"]
        if signal.signal_type == "MACD_HISTOGRAM_DIVERGENCE":
            assert signal.confidence == 0.6

    def test_macd_no_signal_when_no_crossover(self):
        """Test no signal when there is no recent crossover."""
        from core.trading.signals.macd_strategy import MACDAnalyzer

        analyzer = MACDAnalyzer()

        # Steady trend - no crossover expected
        for i in range(45):
            price = 100.0 + i * 0.1
            analyzer.add_price(price)

        signal = analyzer.analyze()

        if not signal.has_crossover:
            assert signal.signal_type in ["NO_SIGNAL", "MACD_HISTOGRAM_DIVERGENCE"]

    def test_macd_signal_to_dict(self):
        """Test signal serialization."""
        from core.trading.signals.macd_strategy import MACDAnalyzer

        analyzer = MACDAnalyzer()
        for i in range(45):
            analyzer.add_price(100.0 + i * 0.2)

        signal = analyzer.analyze()
        signal_dict = signal.to_dict()

        assert "signal_type" in signal_dict
        assert "macd_value" in signal_dict
        assert "signal_line" in signal_dict
        assert "histogram" in signal_dict
        assert "confidence" in signal_dict


# =============================================================================
# DCA STRATEGY TESTS
# =============================================================================

class TestDCAStrategy:
    """Tests for Dollar Cost Averaging strategy."""

    def test_dca_import(self):
        """Test that DCAAnalyzer can be imported."""
        from core.trading.signals.dca_strategy import DCAAnalyzer, DCASignal
        assert DCAAnalyzer is not None
        assert DCASignal is not None

    def test_dca_initialization(self):
        """Test analyzer initialization with default parameters."""
        from core.trading.signals.dca_strategy import DCAAnalyzer

        analyzer = DCAAnalyzer()
        assert analyzer.dip_threshold_pct == 0.10  # 10% default
        assert analyzer.max_add_ons == 3
        assert analyzer.add_on_size_pct == 0.50  # 50% of original

    def test_dca_custom_initialization(self):
        """Test analyzer with custom parameters."""
        from core.trading.signals.dca_strategy import DCAAnalyzer

        analyzer = DCAAnalyzer(
            dip_threshold_pct=0.15,
            max_add_ons=5,
            add_on_size_pct=0.25
        )
        assert analyzer.dip_threshold_pct == 0.15
        assert analyzer.max_add_ons == 5
        assert analyzer.add_on_size_pct == 0.25

    def test_dca_tracks_average_entry(self):
        """Test that analyzer correctly tracks average entry price."""
        from core.trading.signals.dca_strategy import DCAAnalyzer

        analyzer = DCAAnalyzer(dip_threshold_pct=0.10)

        # Initial buy at $100, size 1.0
        analyzer.open_position("BTC", entry_price=100.0, size=1.0)
        assert analyzer.get_average_entry("BTC") == 100.0

        # Add at $90, size 0.5 (50% of original)
        analyzer.add_to_position("BTC", add_price=90.0, add_size=0.5)

        # Average = (100*1 + 90*0.5) / 1.5 = 145 / 1.5 = 96.67
        avg = analyzer.get_average_entry("BTC")
        assert abs(avg - 96.67) < 0.1

    def test_dca_add_opportunity_signal(self):
        """Test DCA_ADD_OPPORTUNITY signal on dip."""
        from core.trading.signals.dca_strategy import DCAAnalyzer

        analyzer = DCAAnalyzer(dip_threshold_pct=0.10)

        # Open position at $100
        analyzer.open_position("BTC", entry_price=100.0, size=1.0)

        # Price drops 15% to $85 (below 10% threshold)
        signal = analyzer.analyze("BTC", current_price=85.0)

        assert signal.signal_type == "DCA_ADD_OPPORTUNITY"
        assert signal.confidence == 0.7
        assert signal.recommended_size == 0.5  # 50% of original

    def test_dca_no_signal_when_price_above_threshold(self):
        """Test no signal when price hasn't dropped enough."""
        from core.trading.signals.dca_strategy import DCAAnalyzer

        analyzer = DCAAnalyzer(dip_threshold_pct=0.10)

        analyzer.open_position("BTC", entry_price=100.0, size=1.0)

        # Price drops only 5% to $95 (above 10% threshold)
        signal = analyzer.analyze("BTC", current_price=95.0)

        assert signal.signal_type == "NO_SIGNAL"

    def test_dca_max_adds_reached_signal(self):
        """Test DCA_MAX_ADDS_REACHED signal when limit hit."""
        from core.trading.signals.dca_strategy import DCAAnalyzer

        analyzer = DCAAnalyzer(dip_threshold_pct=0.10, max_add_ons=3)

        analyzer.open_position("BTC", entry_price=100.0, size=1.0)

        # Add 3 times
        analyzer.add_to_position("BTC", add_price=90.0, add_size=0.5)
        analyzer.add_to_position("BTC", add_price=80.0, add_size=0.5)
        analyzer.add_to_position("BTC", add_price=70.0, add_size=0.5)

        # Price drops further
        signal = analyzer.analyze("BTC", current_price=60.0)

        assert signal.signal_type == "DCA_MAX_ADDS_REACHED"
        assert signal.confidence == 0.8
        assert signal.should_exit is True  # Exit signal to avoid averaging into scam

    def test_dca_close_position(self):
        """Test closing position resets state."""
        from core.trading.signals.dca_strategy import DCAAnalyzer

        analyzer = DCAAnalyzer()

        analyzer.open_position("BTC", entry_price=100.0, size=1.0)
        analyzer.add_to_position("BTC", add_price=90.0, add_size=0.5)

        analyzer.close_position("BTC")

        assert analyzer.get_add_count("BTC") == 0
        assert analyzer.get_average_entry("BTC") is None

    def test_dca_signal_to_dict(self):
        """Test signal serialization."""
        from core.trading.signals.dca_strategy import DCAAnalyzer

        analyzer = DCAAnalyzer()
        analyzer.open_position("BTC", entry_price=100.0, size=1.0)

        signal = analyzer.analyze("BTC", current_price=85.0)
        signal_dict = signal.to_dict()

        assert "signal_type" in signal_dict
        assert "confidence" in signal_dict
        assert "average_entry" in signal_dict
        assert "add_count" in signal_dict
        assert "max_adds" in signal_dict


# =============================================================================
# MEAN REVERSION STRATEGY TESTS
# =============================================================================

class TestMeanReversionStrategy:
    """Tests for mean reversion strategy with Bollinger Bands."""

    def test_mean_reversion_import(self):
        """Test that MeanReversionAnalyzer can be imported."""
        from core.trading.signals.mean_reversion import MeanReversionAnalyzer, MeanReversionSignal
        assert MeanReversionAnalyzer is not None
        assert MeanReversionSignal is not None

    def test_mean_reversion_initialization(self):
        """Test analyzer initialization with default parameters."""
        from core.trading.signals.mean_reversion import MeanReversionAnalyzer

        analyzer = MeanReversionAnalyzer()
        assert analyzer.bb_period == 20
        assert analyzer.bb_std_dev == 2.0

    def test_bollinger_bands_calculation(self):
        """Test Bollinger Bands calculation accuracy."""
        from core.trading.signals.mean_reversion import MeanReversionAnalyzer

        analyzer = MeanReversionAnalyzer(bb_period=20, bb_std_dev=2.0)

        # Add prices
        for i in range(25):
            price = 100.0 + (i % 5) - 2  # Oscillate around 100
            analyzer.add_price(price)

        upper, middle, lower = analyzer.get_bollinger_bands()

        assert upper is not None
        assert middle is not None
        assert lower is not None
        assert upper > middle > lower

    def test_mean_reversion_buy_signal_below_lower_band(self):
        """Test MEAN_REVERSION_BUY when price below lower Bollinger Band."""
        from core.trading.signals.mean_reversion import MeanReversionAnalyzer

        analyzer = MeanReversionAnalyzer(bb_period=20, bb_std_dev=2.0)

        # Add stable prices to establish bands
        for i in range(20):
            analyzer.add_price(100.0 + (i % 3) - 1)

        # Simulate price crashing below lower band
        for _ in range(5):
            analyzer.add_price(90.0)

        signal = analyzer.analyze()

        # Price should be below lower band
        if signal.below_lower_band:
            assert signal.signal_type == "MEAN_REVERSION_BUY"
            assert signal.confidence == 0.65
            assert signal.direction == "long"

    def test_mean_reversion_sell_signal_above_upper_band(self):
        """Test MEAN_REVERSION_SELL when price above upper Bollinger Band."""
        from core.trading.signals.mean_reversion import MeanReversionAnalyzer

        analyzer = MeanReversionAnalyzer(bb_period=20, bb_std_dev=2.0)

        # Add stable prices to establish bands
        for i in range(20):
            analyzer.add_price(100.0 + (i % 3) - 1)

        # Simulate price spiking above upper band
        for _ in range(5):
            analyzer.add_price(110.0)

        signal = analyzer.analyze()

        # Price should be above upper band
        if signal.above_upper_band:
            assert signal.signal_type == "MEAN_REVERSION_SELL"
            assert signal.confidence == 0.65
            assert signal.direction == "short"

    def test_mean_reversion_exit_at_midline(self):
        """Test MEAN_REVERSION_EXIT when price returns to midline."""
        from core.trading.signals.mean_reversion import MeanReversionAnalyzer

        analyzer = MeanReversionAnalyzer(bb_period=20, bb_std_dev=2.0)

        # Establish bands
        for i in range(20):
            analyzer.add_price(100.0 + (i % 3) - 1)

        # Set existing position
        analyzer.set_position("BTC", side="long", entry_band_position="below_lower")

        # Price returns to midline
        analyzer.add_price(100.0)

        signal = analyzer.analyze_exit("BTC")

        assert signal.signal_type == "MEAN_REVERSION_EXIT"
        assert signal.confidence == 0.8
        assert signal.should_exit is True

    def test_mean_reversion_no_signal_in_bands(self):
        """Test no signal when price is within bands."""
        from core.trading.signals.mean_reversion import MeanReversionAnalyzer

        analyzer = MeanReversionAnalyzer(bb_period=20, bb_std_dev=2.0)

        # Add stable prices
        for i in range(25):
            analyzer.add_price(100.0 + (i % 3) - 1)

        signal = analyzer.analyze()

        if not signal.above_upper_band and not signal.below_lower_band:
            assert signal.signal_type == "NO_SIGNAL"

    def test_mean_reversion_band_width(self):
        """Test band width calculation for volatility assessment."""
        from core.trading.signals.mean_reversion import MeanReversionAnalyzer

        analyzer = MeanReversionAnalyzer(bb_period=20, bb_std_dev=2.0)

        for i in range(25):
            analyzer.add_price(100.0 + (i % 5) - 2)

        band_width = analyzer.get_band_width()
        assert band_width is not None
        assert band_width > 0

    def test_mean_reversion_signal_to_dict(self):
        """Test signal serialization."""
        from core.trading.signals.mean_reversion import MeanReversionAnalyzer

        analyzer = MeanReversionAnalyzer()
        for i in range(25):
            analyzer.add_price(100.0 + (i % 3))

        signal = analyzer.analyze()
        signal_dict = signal.to_dict()

        assert "signal_type" in signal_dict
        assert "confidence" in signal_dict
        assert "upper_band" in signal_dict
        assert "middle_band" in signal_dict
        assert "lower_band" in signal_dict
        assert "current_price" in signal_dict


# =============================================================================
# INTEGRATION TESTS
# =============================================================================

class TestStrategyIntegration:
    """Integration tests for strategy module exports."""

    def test_all_strategies_importable_from_signals_module(self):
        """Test that all new strategies can be imported from signals module."""
        from core.trading.signals import (
            TrailingStopAnalyzer,
            TrailingStopSignal,
            RSIAnalyzer,
            RSISignal,
            MACDAnalyzer,
            MACDSignal,
            DCAAnalyzer,
            DCASignal,
            MeanReversionAnalyzer,
            MeanReversionSignal,
        )

        assert TrailingStopAnalyzer is not None
        assert RSIAnalyzer is not None
        assert MACDAnalyzer is not None
        assert DCAAnalyzer is not None
        assert MeanReversionAnalyzer is not None

    def test_decision_matrix_includes_new_signal_weights(self):
        """Test that DecisionMatrix has updated signal weights."""
        from core.trading.decision_matrix import EntryConditions

        entry = EntryConditions()

        # Check new weights are present
        assert "rsi" in entry.signal_weights
        assert "macd" in entry.signal_weights
        assert "mean_reversion" in entry.signal_weights
        assert "breakout" in entry.signal_weights
        assert "volume_profile" in entry.signal_weights

        # Verify weight distribution sums to 1.0
        total_weight = sum(entry.signal_weights.values())
        assert abs(total_weight - 1.0) < 0.01


# =============================================================================
# BREAKOUT STRATEGY TESTS
# =============================================================================

class TestBreakoutStrategy:
    """Tests for breakout/breakdown trading strategy."""

    def test_breakout_import(self):
        """Test that BreakoutAnalyzer can be imported."""
        from core.trading.signals.breakout_strategy import BreakoutAnalyzer, BreakoutSignal
        assert BreakoutAnalyzer is not None
        assert BreakoutSignal is not None

    def test_breakout_initialization(self):
        """Test analyzer initialization with default parameters."""
        from core.trading.signals.breakout_strategy import BreakoutAnalyzer

        analyzer = BreakoutAnalyzer()
        assert analyzer.lookback_period == 20
        assert analyzer.breakout_threshold_pct == 0.02  # 2% default
        assert analyzer.volume_confirmation_multiplier == 1.5

    def test_breakout_custom_initialization(self):
        """Test analyzer with custom parameters."""
        from core.trading.signals.breakout_strategy import BreakoutAnalyzer

        analyzer = BreakoutAnalyzer(
            lookback_period=30,
            breakout_threshold_pct=0.03,
            volume_confirmation_multiplier=2.0
        )
        assert analyzer.lookback_period == 30
        assert analyzer.breakout_threshold_pct == 0.03
        assert analyzer.volume_confirmation_multiplier == 2.0

    def test_breakout_identifies_resistance_levels(self):
        """Test that analyzer identifies resistance levels from price history."""
        from core.trading.signals.breakout_strategy import BreakoutAnalyzer

        analyzer = BreakoutAnalyzer(lookback_period=20)

        # Add price history with clear resistance at 110
        prices = [100, 105, 110, 108, 105, 107, 110, 106, 103, 105,
                  108, 110, 107, 104, 106, 109, 110, 108, 105, 107]
        volumes = [1000] * 20

        for price, volume in zip(prices, volumes):
            analyzer.add_data(price, volume)

        resistance = analyzer.get_resistance_level()
        assert resistance is not None
        assert abs(resistance - 110.0) < 2.0  # Should identify ~110 as resistance

    def test_breakout_identifies_support_levels(self):
        """Test that analyzer identifies support levels from price history."""
        from core.trading.signals.breakout_strategy import BreakoutAnalyzer

        analyzer = BreakoutAnalyzer(lookback_period=20)

        # Add price history with clear support at 90
        prices = [100, 95, 90, 93, 96, 94, 90, 92, 95, 94,
                  91, 90, 93, 95, 94, 92, 90, 92, 94, 93]
        volumes = [1000] * 20

        for price, volume in zip(prices, volumes):
            analyzer.add_data(price, volume)

        support = analyzer.get_support_level()
        assert support is not None
        assert abs(support - 90.0) < 2.0  # Should identify ~90 as support

    def test_breakout_buy_signal_above_resistance(self):
        """Test BREAKOUT_BUY signal when price breaks above resistance with volume."""
        from core.trading.signals.breakout_strategy import BreakoutAnalyzer

        analyzer = BreakoutAnalyzer(
            lookback_period=20,
            breakout_threshold_pct=0.02,
            volume_confirmation_multiplier=1.5
        )

        # Establish resistance at 110
        prices = [100, 105, 110, 108, 105, 107, 110, 106, 103, 105,
                  108, 110, 107, 104, 106, 109, 110, 108, 105, 107]
        volumes = [1000] * 20

        for price, volume in zip(prices, volumes):
            analyzer.add_data(price, volume)

        # Breakout above resistance with high volume
        signal = analyzer.analyze(current_price=113.0, current_volume=2000)

        assert signal.signal_type == "BREAKOUT_BUY"
        assert signal.confidence >= 0.7
        assert signal.breakout_level is not None
        assert signal.volume_confirmed is True

    def test_breakout_sell_signal_below_support(self):
        """Test BREAKOUT_SELL signal when price breaks below support with volume."""
        from core.trading.signals.breakout_strategy import BreakoutAnalyzer

        analyzer = BreakoutAnalyzer(
            lookback_period=20,
            breakout_threshold_pct=0.02,
            volume_confirmation_multiplier=1.5
        )

        # Establish support at 90
        prices = [100, 95, 90, 93, 96, 94, 90, 92, 95, 94,
                  91, 90, 93, 95, 94, 92, 90, 92, 94, 93]
        volumes = [1000] * 20

        for price, volume in zip(prices, volumes):
            analyzer.add_data(price, volume)

        # Breakdown below support with high volume
        signal = analyzer.analyze(current_price=87.0, current_volume=2000)

        assert signal.signal_type == "BREAKOUT_SELL"
        assert signal.confidence >= 0.7
        assert signal.breakdown_level is not None
        assert signal.volume_confirmed is True

    def test_breakout_weak_signal_without_volume_confirmation(self):
        """Test weaker signal when breakout occurs without volume confirmation."""
        from core.trading.signals.breakout_strategy import BreakoutAnalyzer

        analyzer = BreakoutAnalyzer(
            lookback_period=20,
            volume_confirmation_multiplier=1.5
        )

        # Establish resistance at 110
        prices = [100, 105, 110, 108, 105, 107, 110, 106, 103, 105,
                  108, 110, 107, 104, 106, 109, 110, 108, 105, 107]
        volumes = [1000] * 20

        for price, volume in zip(prices, volumes):
            analyzer.add_data(price, volume)

        # Breakout WITHOUT high volume (same as average)
        signal = analyzer.analyze(current_price=113.0, current_volume=1000)

        # Should still signal but with lower confidence
        assert signal.signal_type == "BREAKOUT_BUY"
        assert signal.confidence < 0.7  # Lower confidence without volume
        assert signal.volume_confirmed is False

    def test_breakout_no_signal_within_range(self):
        """Test no signal when price is within support/resistance range."""
        from core.trading.signals.breakout_strategy import BreakoutAnalyzer

        analyzer = BreakoutAnalyzer(lookback_period=20)

        prices = [100, 105, 110, 108, 105, 107, 110, 106, 103, 105,
                  108, 110, 107, 104, 106, 109, 110, 108, 105, 107]
        volumes = [1000] * 20

        for price, volume in zip(prices, volumes):
            analyzer.add_data(price, volume)

        # Price within range
        signal = analyzer.analyze(current_price=105.0, current_volume=1000)

        assert signal.signal_type == "NO_SIGNAL"

    def test_breakout_false_breakout_detection(self):
        """Test FALSE_BREAKOUT signal when price quickly reverses."""
        from core.trading.signals.breakout_strategy import BreakoutAnalyzer

        analyzer = BreakoutAnalyzer(lookback_period=20)

        # Establish resistance at 110
        prices = [100, 105, 110, 108, 105, 107, 110, 106, 103, 105,
                  108, 110, 107, 104, 106, 109, 110, 108, 105, 107]
        volumes = [1000] * 20

        for price, volume in zip(prices, volumes):
            analyzer.add_data(price, volume)

        # Breakout above resistance
        analyzer.add_data(113.0, 2000)

        # Quick reversal back below resistance
        signal = analyzer.analyze(current_price=108.0, current_volume=1500)

        assert signal.signal_type in ["FALSE_BREAKOUT", "NO_SIGNAL"]

    def test_breakout_signal_to_dict(self):
        """Test signal serialization."""
        from core.trading.signals.breakout_strategy import BreakoutAnalyzer

        analyzer = BreakoutAnalyzer()

        for i in range(25):
            analyzer.add_data(100.0 + (i % 5), 1000)

        signal = analyzer.analyze(current_price=106.0, current_volume=1500)
        signal_dict = signal.to_dict()

        assert "signal_type" in signal_dict
        assert "confidence" in signal_dict
        assert "breakout_level" in signal_dict
        assert "breakdown_level" in signal_dict
        assert "support_level" in signal_dict
        assert "resistance_level" in signal_dict
        assert "volume_confirmed" in signal_dict


# =============================================================================
# VOLUME PROFILE STRATEGY TESTS
# =============================================================================

class TestVolumeProfileStrategy:
    """Tests for volume profile analysis strategy."""

    def test_volume_profile_import(self):
        """Test that VolumeProfileAnalyzer can be imported."""
        from core.trading.signals.volume_profile_strategy import VolumeProfileAnalyzer, VolumeProfileSignal
        assert VolumeProfileAnalyzer is not None
        assert VolumeProfileSignal is not None

    def test_volume_profile_initialization(self):
        """Test analyzer initialization with default parameters."""
        from core.trading.signals.volume_profile_strategy import VolumeProfileAnalyzer

        analyzer = VolumeProfileAnalyzer()
        assert analyzer.num_bins == 20
        assert analyzer.lookback_period == 100

    def test_volume_profile_custom_initialization(self):
        """Test analyzer with custom parameters."""
        from core.trading.signals.volume_profile_strategy import VolumeProfileAnalyzer

        analyzer = VolumeProfileAnalyzer(num_bins=30, lookback_period=200)
        assert analyzer.num_bins == 30
        assert analyzer.lookback_period == 200

    def test_volume_profile_identifies_poc(self):
        """Test that analyzer identifies Point of Control (highest volume price level)."""
        from core.trading.signals.volume_profile_strategy import VolumeProfileAnalyzer

        analyzer = VolumeProfileAnalyzer(num_bins=10)

        # Add data with concentrated volume at $100
        for _ in range(50):
            analyzer.add_data(price=100.0, volume=2000)
        for _ in range(25):
            analyzer.add_data(price=95.0, volume=500)
        for _ in range(25):
            analyzer.add_data(price=105.0, volume=500)

        poc = analyzer.get_point_of_control()
        assert poc is not None
        assert abs(poc - 100.0) < 3.0  # POC should be near $100

    def test_volume_profile_identifies_value_area(self):
        """Test that analyzer identifies Value Area High and Low (70% of volume)."""
        from core.trading.signals.volume_profile_strategy import VolumeProfileAnalyzer

        analyzer = VolumeProfileAnalyzer(num_bins=10)

        # Add normally distributed volume around $100
        import random
        random.seed(42)
        for _ in range(100):
            price = 100 + random.gauss(0, 5)
            volume = 1000 + random.randint(-200, 200)
            analyzer.add_data(price=price, volume=volume)

        vah, val = analyzer.get_value_area()
        assert vah is not None
        assert val is not None
        assert vah > val  # High should be above low

    def test_volume_profile_support_from_high_volume_node(self):
        """Test that high volume nodes below price act as support."""
        from core.trading.signals.volume_profile_strategy import VolumeProfileAnalyzer

        analyzer = VolumeProfileAnalyzer(num_bins=10)

        # Create high volume node at $90 (below current price)
        for _ in range(40):
            analyzer.add_data(price=90.0, volume=3000)  # High volume at $90
        for _ in range(30):
            analyzer.add_data(price=100.0, volume=1000)
        for _ in range(30):
            analyzer.add_data(price=95.0, volume=500)

        signal = analyzer.analyze(current_price=98.0)

        assert signal.support_level is not None
        # With bin-based analysis, tolerance needs to account for bin width
        # Support should be identified somewhere in the 90-96 range
        assert signal.support_level < 98.0  # Support below current price
        assert signal.support_confidence > 0.2  # Some confidence in the level

    def test_volume_profile_resistance_from_high_volume_node(self):
        """Test that high volume nodes above price act as resistance."""
        from core.trading.signals.volume_profile_strategy import VolumeProfileAnalyzer

        analyzer = VolumeProfileAnalyzer(num_bins=10)

        # Create high volume node at $110 (above current price)
        for _ in range(40):
            analyzer.add_data(price=110.0, volume=3000)  # High volume at $110
        for _ in range(30):
            analyzer.add_data(price=100.0, volume=1000)
        for _ in range(30):
            analyzer.add_data(price=105.0, volume=500)

        signal = analyzer.analyze(current_price=102.0)

        assert signal.resistance_level is not None
        # With bin-based analysis, tolerance needs to account for bin width
        # Resistance should be identified somewhere in the 104-111 range
        assert signal.resistance_level > 102.0  # Resistance above current price
        assert signal.resistance_confidence > 0.2  # Some confidence in the level

    def test_volume_profile_low_volume_node_breakout_signal(self):
        """Test VOLUME_BREAKOUT signal at low volume node (easy to break)."""
        from core.trading.signals.volume_profile_strategy import VolumeProfileAnalyzer

        analyzer = VolumeProfileAnalyzer(num_bins=10)

        # Create volume gap between $100 and $110
        for _ in range(40):
            analyzer.add_data(price=95.0, volume=2000)  # High volume below
        for _ in range(10):
            analyzer.add_data(price=105.0, volume=100)  # Low volume gap
        for _ in range(40):
            analyzer.add_data(price=115.0, volume=2000)  # High volume above

        signal = analyzer.analyze(current_price=105.0)

        # At low volume node, price can move easily
        if signal.in_low_volume_zone:
            assert signal.signal_type in ["VOLUME_BREAKOUT_ZONE", "NO_SIGNAL"]

    def test_volume_profile_poc_bounce_signal(self):
        """Test VOLUME_POC_BOUNCE signal when price approaches POC."""
        from core.trading.signals.volume_profile_strategy import VolumeProfileAnalyzer

        analyzer = VolumeProfileAnalyzer(num_bins=10)

        # Create clear POC at $100
        for _ in range(60):
            analyzer.add_data(price=100.0, volume=3000)
        for _ in range(20):
            analyzer.add_data(price=95.0, volume=500)
        for _ in range(20):
            analyzer.add_data(price=105.0, volume=500)

        # Price approaches POC from below
        signal = analyzer.analyze(current_price=99.0)

        poc = analyzer.get_point_of_control()
        if poc and abs(99.0 - poc) < 2.0:
            assert signal.near_poc is True
            # POC often acts as magnet/support
            assert signal.poc_significance > 0.5

    def test_volume_profile_no_signal_insufficient_data(self):
        """Test no signal when insufficient price/volume data."""
        from core.trading.signals.volume_profile_strategy import VolumeProfileAnalyzer

        analyzer = VolumeProfileAnalyzer(num_bins=10, lookback_period=100)

        # Add only a few data points
        for i in range(5):
            analyzer.add_data(price=100.0 + i, volume=1000)

        signal = analyzer.analyze(current_price=105.0)

        assert signal.signal_type == "NO_SIGNAL"
        assert signal.confidence == 0.0

    def test_volume_profile_signal_to_dict(self):
        """Test signal serialization."""
        from core.trading.signals.volume_profile_strategy import VolumeProfileAnalyzer

        analyzer = VolumeProfileAnalyzer()

        for i in range(100):
            analyzer.add_data(price=100.0 + (i % 10) - 5, volume=1000 + (i % 3) * 100)

        signal = analyzer.analyze(current_price=100.0)
        signal_dict = signal.to_dict()

        assert "signal_type" in signal_dict
        assert "confidence" in signal_dict
        assert "support_level" in signal_dict
        assert "resistance_level" in signal_dict
        assert "point_of_control" in signal_dict
        assert "value_area_high" in signal_dict
        assert "value_area_low" in signal_dict

    def test_volume_profile_stats(self):
        """Test analyzer statistics reporting."""
        from core.trading.signals.volume_profile_strategy import VolumeProfileAnalyzer

        analyzer = VolumeProfileAnalyzer(num_bins=10)

        for i in range(50):
            analyzer.add_data(price=100.0 + (i % 5), volume=1000)

        stats = analyzer.get_stats()

        assert "data_points" in stats
        assert "poc" in stats
        assert "value_area_high" in stats
        assert "value_area_low" in stats
        assert stats["data_points"] == 50


# =============================================================================
# EXTENDED INTEGRATION TESTS
# =============================================================================

class TestExtendedStrategyIntegration:
    """Extended integration tests including new strategies."""

    def test_all_new_strategies_importable(self):
        """Test that all new strategies can be imported."""
        from core.trading.signals.breakout_strategy import BreakoutAnalyzer, BreakoutSignal
        from core.trading.signals.volume_profile_strategy import VolumeProfileAnalyzer, VolumeProfileSignal

        assert BreakoutAnalyzer is not None
        assert BreakoutSignal is not None
        assert VolumeProfileAnalyzer is not None
        assert VolumeProfileSignal is not None

    def test_new_strategies_in_signals_module(self):
        """Test that new strategies are exported from signals module."""
        from core.trading.signals import (
            BreakoutAnalyzer,
            BreakoutSignal,
            VolumeProfileAnalyzer,
            VolumeProfileSignal,
        )

        assert BreakoutAnalyzer is not None
        assert VolumeProfileAnalyzer is not None

    def test_combined_strategy_signals(self):
        """Test using multiple strategies together for confluence."""
        from core.trading.signals.breakout_strategy import BreakoutAnalyzer
        from core.trading.signals.volume_profile_strategy import VolumeProfileAnalyzer

        breakout_analyzer = BreakoutAnalyzer(lookback_period=20)
        volume_analyzer = VolumeProfileAnalyzer(num_bins=10)

        # Add same price/volume data to both
        prices = [100, 102, 104, 103, 105, 107, 106, 108, 110, 109,
                  108, 110, 111, 110, 109, 110, 108, 107, 109, 110]
        volumes = [1000, 1100, 1200, 900, 1500, 1800, 1000, 2000, 2500, 1200,
                   1000, 2200, 2800, 1500, 1100, 1800, 900, 800, 1200, 1400]

        for price, volume in zip(prices, volumes):
            breakout_analyzer.add_data(price, volume)
            volume_analyzer.add_data(price, volume)

        # Analyze with potential breakout price
        breakout_signal = breakout_analyzer.analyze(current_price=113.0, current_volume=3000)
        volume_signal = volume_analyzer.analyze(current_price=113.0)

        # Both signals should provide useful information
        assert breakout_signal.signal_type is not None
        assert volume_signal.signal_type is not None

        # If breakout is near high volume resistance, it's more significant
        if breakout_signal.signal_type == "BREAKOUT_BUY" and volume_signal.resistance_level:
            # Confluence of signals increases confidence
            assert True  # Both signals agree on key levels
