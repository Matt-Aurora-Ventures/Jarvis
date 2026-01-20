"""
Image Generator Tests

Tests for core/social/image_generator.py:
- Sentiment visualization (bull/bear charts)
- Price action visualization (candlesticks)
- Portfolio composition charts
"""

import pytest
import tempfile
from pathlib import Path
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

# Check for matplotlib availability
try:
    import matplotlib
    HAS_MATPLOTLIB = True
except ImportError:
    HAS_MATPLOTLIB = False

# Skip marker for tests requiring matplotlib
requires_matplotlib = pytest.mark.skipif(
    not HAS_MATPLOTLIB,
    reason="matplotlib not installed"
)


@pytest.fixture
def temp_dir():
    """Create a temporary directory for test files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


class TestImageGeneratorImport:
    """Test that image generator module imports correctly."""

    def test_image_generator_import(self):
        """Test that ImageGenerator can be imported."""
        from core.social.image_generator import ImageGenerator
        assert ImageGenerator is not None

    def test_image_config_import(self):
        """Test that ImageConfig can be imported."""
        from core.social.image_generator import ImageConfig
        assert ImageConfig is not None


class TestImageGeneratorInit:
    """Test ImageGenerator initialization."""

    def test_default_init(self, temp_dir):
        """Test default initialization."""
        from core.social.image_generator import ImageGenerator
        generator = ImageGenerator(output_dir=temp_dir)
        assert generator is not None
        assert generator.output_dir == temp_dir

    def test_custom_config(self, temp_dir):
        """Test initialization with custom config."""
        from core.social.image_generator import ImageGenerator, ImageConfig
        config = ImageConfig(
            width=1200,
            height=800,
            theme="dark"
        )
        generator = ImageGenerator(output_dir=temp_dir, config=config)
        assert generator.config.width == 1200
        assert generator.config.height == 800


class TestSentimentVisualization:
    """Tests for sentiment bull/bear chart generation."""

    @requires_matplotlib
    def test_generate_sentiment_chart_creates_image(self, temp_dir):
        """Test that generate_sentiment_chart creates a PNG image."""
        from core.social.image_generator import ImageGenerator

        generator = ImageGenerator(output_dir=temp_dir)

        sentiment_data = {
            "SOL": 0.75,
            "BTC": 0.45,
            "ETH": 0.30,
            "WIF": -0.25,
            "BONK": 0.85,
        }

        result = generator.generate_sentiment_chart(sentiment_data)

        assert result is not None
        assert result.exists()
        assert result.suffix == ".png"

    @requires_matplotlib
    def test_sentiment_chart_bullish_theme(self, temp_dir):
        """Test bullish theme for positive sentiment."""
        from core.social.image_generator import ImageGenerator

        generator = ImageGenerator(output_dir=temp_dir)

        # All bullish sentiment
        sentiment_data = {"SOL": 0.9, "BTC": 0.8}

        result = generator.generate_sentiment_chart(sentiment_data)
        assert result is not None

    @requires_matplotlib
    def test_sentiment_chart_bearish_theme(self, temp_dir):
        """Test bearish theme for negative sentiment."""
        from core.social.image_generator import ImageGenerator

        generator = ImageGenerator(output_dir=temp_dir)

        # All bearish sentiment
        sentiment_data = {"SOL": -0.7, "BTC": -0.6}

        result = generator.generate_sentiment_chart(sentiment_data)
        assert result is not None

    @requires_matplotlib
    def test_sentiment_chart_with_timestamps(self, temp_dir):
        """Test sentiment chart with time series data."""
        from core.social.image_generator import ImageGenerator

        generator = ImageGenerator(output_dir=temp_dir)

        # Time series sentiment
        sentiment_series = {
            "SOL": [0.5, 0.6, 0.7, 0.8, 0.75],
            "BTC": [0.4, 0.45, 0.5, 0.55, 0.6],
        }
        timestamps = ["12:00", "13:00", "14:00", "15:00", "16:00"]

        result = generator.generate_sentiment_timeseries(sentiment_series, timestamps)
        assert result is not None
        assert result.exists()

    def test_sentiment_empty_data(self, temp_dir):
        """Test handling of empty sentiment data."""
        from core.social.image_generator import ImageGenerator

        generator = ImageGenerator(output_dir=temp_dir)

        result = generator.generate_sentiment_chart({})
        assert result is None


class TestPriceVisualization:
    """Tests for price action candlestick visualization."""

    @requires_matplotlib
    def test_generate_candlestick_chart(self, temp_dir):
        """Test candlestick chart generation."""
        from core.social.image_generator import ImageGenerator

        generator = ImageGenerator(output_dir=temp_dir)

        ohlc_data = [
            {"open": 100, "high": 105, "low": 98, "close": 103},
            {"open": 103, "high": 108, "low": 101, "close": 106},
            {"open": 106, "high": 110, "low": 104, "close": 108},
            {"open": 108, "high": 112, "low": 105, "close": 107},
            {"open": 107, "high": 115, "low": 106, "close": 114},
        ]

        result = generator.generate_candlestick_chart(
            ohlc_data,
            symbol="SOL",
            timeframe="1h"
        )

        assert result is not None
        assert result.exists()
        assert result.suffix == ".png"

    @requires_matplotlib
    def test_candlestick_with_volume(self, temp_dir):
        """Test candlestick chart with volume overlay."""
        from core.social.image_generator import ImageGenerator

        generator = ImageGenerator(output_dir=temp_dir)

        ohlc_data = [
            {"open": 100, "high": 105, "low": 98, "close": 103, "volume": 1000000},
            {"open": 103, "high": 108, "low": 101, "close": 106, "volume": 1200000},
        ]

        result = generator.generate_candlestick_chart(
            ohlc_data,
            symbol="SOL",
            include_volume=True
        )

        assert result is not None

    @requires_matplotlib
    def test_candlestick_green_candles(self, temp_dir):
        """Test that bullish candles are green."""
        from core.social.image_generator import ImageGenerator

        generator = ImageGenerator(output_dir=temp_dir)

        # All bullish candles (close > open)
        ohlc_data = [
            {"open": 100, "high": 110, "low": 99, "close": 108},
            {"open": 108, "high": 115, "low": 107, "close": 113},
        ]

        result = generator.generate_candlestick_chart(ohlc_data, symbol="SOL")
        assert result is not None

    @requires_matplotlib
    def test_candlestick_red_candles(self, temp_dir):
        """Test that bearish candles are red."""
        from core.social.image_generator import ImageGenerator

        generator = ImageGenerator(output_dir=temp_dir)

        # All bearish candles (close < open)
        ohlc_data = [
            {"open": 110, "high": 112, "low": 100, "close": 102},
            {"open": 102, "high": 104, "low": 95, "close": 97},
        ]

        result = generator.generate_candlestick_chart(ohlc_data, symbol="SOL")
        assert result is not None


class TestPortfolioVisualization:
    """Tests for portfolio composition charts."""

    @requires_matplotlib
    def test_generate_portfolio_pie_chart(self, temp_dir):
        """Test portfolio pie chart generation."""
        from core.social.image_generator import ImageGenerator

        generator = ImageGenerator(output_dir=temp_dir)

        portfolio = {
            "SOL": {"value_usd": 5000, "percentage": 50},
            "BTC": {"value_usd": 3000, "percentage": 30},
            "ETH": {"value_usd": 2000, "percentage": 20},
        }

        result = generator.generate_portfolio_chart(portfolio)

        assert result is not None
        assert result.exists()
        assert result.suffix == ".png"

    @requires_matplotlib
    def test_portfolio_donut_chart(self, temp_dir):
        """Test portfolio donut chart variant."""
        from core.social.image_generator import ImageGenerator

        generator = ImageGenerator(output_dir=temp_dir)

        portfolio = {
            "SOL": {"value_usd": 5000, "percentage": 50},
            "BTC": {"value_usd": 3000, "percentage": 30},
        }

        result = generator.generate_portfolio_chart(portfolio, chart_type="donut")
        assert result is not None

    @requires_matplotlib
    def test_portfolio_with_pnl_colors(self, temp_dir):
        """Test portfolio chart with PnL coloring."""
        from core.social.image_generator import ImageGenerator

        generator = ImageGenerator(output_dir=temp_dir)

        portfolio = {
            "SOL": {"value_usd": 5000, "percentage": 50, "pnl_percent": 25.5},
            "BTC": {"value_usd": 3000, "percentage": 30, "pnl_percent": -5.2},
        }

        result = generator.generate_portfolio_chart(portfolio, show_pnl=True)
        assert result is not None

    def test_portfolio_chart_empty(self, temp_dir):
        """Test handling of empty portfolio."""
        from core.social.image_generator import ImageGenerator

        generator = ImageGenerator(output_dir=temp_dir)

        result = generator.generate_portfolio_chart({})
        assert result is None


class TestImageConfig:
    """Tests for ImageConfig settings."""

    def test_config_defaults(self):
        """Test default configuration values."""
        from core.social.image_generator import ImageConfig

        config = ImageConfig()
        assert config.width == 1080
        assert config.height == 720
        assert config.theme == "dark"
        assert config.dpi == 150

    def test_config_custom_values(self):
        """Test custom configuration values."""
        from core.social.image_generator import ImageConfig

        config = ImageConfig(
            width=1920,
            height=1080,
            theme="light",
            dpi=300
        )
        assert config.width == 1920
        assert config.height == 1080
        assert config.theme == "light"
        assert config.dpi == 300

    def test_config_dark_theme_colors(self):
        """Test dark theme color palette."""
        from core.social.image_generator import ImageConfig

        config = ImageConfig(theme="dark")
        colors = config.get_colors()

        assert "background" in colors
        assert "text" in colors
        assert "bullish" in colors
        assert "bearish" in colors


class TestImageUtilities:
    """Tests for utility functions."""

    def test_cleanup_old_images(self, temp_dir):
        """Test cleanup of old generated images."""
        from core.social.image_generator import ImageGenerator

        generator = ImageGenerator(output_dir=temp_dir)

        # Create some test images with proper prefixes
        import time
        for i in range(15):
            file = temp_dir / f"sentiment_{i}.png"
            file.write_text("test")
            time.sleep(0.01)  # Ensure different mtimes

        generator.cleanup_old_images(keep_last=5)

        remaining = list(temp_dir.glob("sentiment_*.png"))
        assert len(remaining) == 5

    def test_get_supported_formats(self, temp_dir):
        """Test getting supported image formats."""
        from core.social.image_generator import ImageGenerator

        generator = ImageGenerator(output_dir=temp_dir)
        formats = generator.get_supported_formats()

        assert "png" in formats
        assert "jpg" in formats

    def test_add_branding_overlay(self, temp_dir):
        """Test adding Jarvis branding to images."""
        from core.social.image_generator import ImageGenerator

        generator = ImageGenerator(output_dir=temp_dir)

        # Create a simple test image first
        sentiment_data = {"SOL": 0.5}
        base_image = generator.generate_sentiment_chart(sentiment_data)

        if base_image:
            branded = generator.add_branding(base_image)
            assert branded is not None
            assert branded.exists()
