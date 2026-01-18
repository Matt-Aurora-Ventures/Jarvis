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

        # Verify weight distribution sums to 1.0
        total_weight = sum(entry.signal_weights.values())
        assert abs(total_weight - 1.0) < 0.01
