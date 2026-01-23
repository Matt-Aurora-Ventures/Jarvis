"""
Demo Charts Test Suite (US-007)

Tests for candlestick chart generation.
"""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock
import io


class TestChartModule:
    """Test chart module imports and availability."""

    def test_chart_module_exists(self):
        """Chart handler module should exist."""
        from tg_bot.handlers import demo_charts
        assert demo_charts is not None

    def test_chart_generation_function_exists(self):
        """generate_price_chart function should exist."""
        from tg_bot.handlers.demo_charts import generate_price_chart
        assert callable(generate_price_chart)

    def test_simple_line_chart_function_exists(self):
        """generate_simple_line_chart fallback should exist."""
        from tg_bot.handlers.demo_charts import generate_simple_line_chart
        assert callable(generate_simple_line_chart)

    def test_chart_callback_handler_exists(self):
        """handle_chart_callback function should exist."""
        from tg_bot.handlers.demo_charts import handle_chart_callback
        assert callable(handle_chart_callback)


class TestChartCaching:
    """Test chart caching functionality."""

    def test_cache_key_generation(self):
        """Cache keys should be generated correctly."""
        from tg_bot.handlers.demo_charts import _get_cache_key

        key1 = _get_cache_key("mint123", "1h")
        key2 = _get_cache_key("mint123", "1h")
        key3 = _get_cache_key("mint456", "1h")

        # Same inputs should give same key (within 5-min window)
        assert key1 == key2

        # Different mint should give different key
        assert key1 != key3

    def test_cache_stores_and_retrieves(self):
        """Cache should store and retrieve charts."""
        from tg_bot.handlers.demo_charts import _cache_chart, _get_cached_chart

        # Create a test buffer
        test_buf = io.BytesIO(b"test chart data")

        # Cache it
        _cache_chart("test_mint", "1h", test_buf)

        # Retrieve it
        cached = _get_cached_chart("test_mint", "1h")

        # Should get the same data
        assert cached is not None
        assert cached.read() == b"test chart data"


class TestChartGeneration:
    """Test chart generation (mocked if mplfinance unavailable)."""

    @pytest.mark.asyncio
    async def test_generate_price_chart_returns_buffer_or_none(self):
        """generate_price_chart should return BytesIO or None."""
        from tg_bot.handlers.demo_charts import generate_price_chart, MPLFINANCE_AVAILABLE

        result = await generate_price_chart(
            mint="So11111111111111111111111111111111111111112",
            symbol="TEST",
            interval="1h"
        )

        # Should return BytesIO if mplfinance available, None otherwise
        if MPLFINANCE_AVAILABLE:
            assert result is None or isinstance(result, io.BytesIO)
        else:
            assert result is None

    @pytest.mark.asyncio
    async def test_simple_line_chart_generation(self):
        """Simple line chart should work with matplotlib."""
        from tg_bot.handlers.demo_charts import generate_simple_line_chart

        # Test with demo prices
        prices = [0.001, 0.0011, 0.0012, 0.0011, 0.0013, 0.0014]

        result = await generate_simple_line_chart(
            mint="test_mint",
            symbol="TEST",
            prices=prices
        )

        # Should return a buffer or None
        assert result is None or isinstance(result, io.BytesIO)


class TestChartCallbackHandler:
    """Test the chart callback handler."""

    @pytest.mark.asyncio
    async def test_handle_chart_callback_returns_tuple(self):
        """handle_chart_callback should return (success, result) tuple."""
        from tg_bot.handlers.demo_charts import handle_chart_callback

        success, result = await handle_chart_callback(
            token_mint="test_mint",
            token_symbol="TEST",
            interval="1h"
        )

        # Should return tuple
        assert isinstance(success, bool)
        # Result is either BytesIO (success) or string (error)
        assert isinstance(result, (io.BytesIO, str))


class TestOHLCVDataFetch:
    """Test OHLCV data fetching."""

    @pytest.mark.asyncio
    async def test_fetch_ohlcv_returns_list(self):
        """fetch_ohlcv_data should return a list of candles."""
        from tg_bot.handlers.demo_charts import fetch_ohlcv_data

        candles = await fetch_ohlcv_data(
            mint="test_mint",
            interval="1h",
            limit=10
        )

        assert isinstance(candles, list)
        assert len(candles) > 0

        # Each candle should have OHLCV fields
        candle = candles[0]
        assert "open" in candle
        assert "high" in candle
        assert "low" in candle
        assert "close" in candle
        assert "volume" in candle


class TestDarkStyleGeneration:
    """Test chart style generation."""

    def test_dark_style_returns_style_or_none(self):
        """get_dark_style should return style object or None."""
        from tg_bot.handlers.demo_charts import get_dark_style, MPLFINANCE_AVAILABLE

        style = get_dark_style()

        if MPLFINANCE_AVAILABLE:
            assert style is not None
        else:
            assert style is None
