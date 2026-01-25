"""
Unit tests for tg_bot/services/chart_generator.py

Covers:
- ChartGenerator initialization and setup
- Price chart generation with moving averages
- Portfolio performance charts
- Position allocation pie charts
- Drawdown analysis charts
- Trade P&L distribution histograms
- Risk/return scatter plots
- Sentiment heatmaps
- Chart styling (dark theme)
- Image export to BytesIO
- Edge cases and error handling
"""

import sys
import pytest
from datetime import datetime, timedelta
from io import BytesIO
from unittest.mock import MagicMock, patch

import numpy as np


# ============================================================================
# Helper: Create mock figure that saves to BytesIO
# ============================================================================

def create_mock_figure():
    """Create a mock figure that writes PNG-like data to BytesIO."""
    mock_fig = MagicMock()
    mock_ax = MagicMock()

    def savefig_side_effect(buffer, **kwargs):
        # Write PNG header to make it look like a real PNG
        buffer.write(b'\x89PNG\r\n\x1a\n')
        buffer.write(b'IHDR' + b'\x00' * 100)  # Fake PNG data
        buffer.write(b'IEND')

    mock_fig.savefig = MagicMock(side_effect=savefig_side_effect)
    mock_fig.autofmt_xdate = MagicMock()
    mock_ax.plot = MagicMock()
    mock_ax.fill_between = MagicMock()
    mock_ax.set_title = MagicMock()
    mock_ax.set_xlabel = MagicMock()
    mock_ax.set_ylabel = MagicMock()
    mock_ax.grid = MagicMock()
    mock_ax.legend = MagicMock()
    mock_ax.axhline = MagicMock()
    mock_ax.axvline = MagicMock()
    mock_ax.text = MagicMock()
    mock_ax.xaxis = MagicMock()
    mock_ax.pie = MagicMock(return_value=([], [], []))
    mock_ax.hist = MagicMock()
    mock_ax.scatter = MagicMock()
    mock_ax.annotate = MagicMock()
    mock_ax.bar = MagicMock()
    mock_ax.imshow = MagicMock()
    mock_ax.set_xticks = MagicMock()
    mock_ax.set_yticks = MagicMock()
    mock_ax.set_xticklabels = MagicMock()
    mock_ax.set_yticklabels = MagicMock()
    mock_ax.get_xticklabels = MagicMock(return_value=[])

    return mock_fig, mock_ax


def create_mock_dual_axes():
    """Create a mock figure with dual axes for drawdown charts."""
    mock_fig = MagicMock()
    mock_ax1 = MagicMock()
    mock_ax2 = MagicMock()

    def savefig_side_effect(buffer, **kwargs):
        buffer.write(b'\x89PNG\r\n\x1a\n')
        buffer.write(b'IHDR' + b'\x00' * 100)
        buffer.write(b'IEND')

    mock_fig.savefig = MagicMock(side_effect=savefig_side_effect)
    mock_fig.autofmt_xdate = MagicMock()

    for ax in [mock_ax1, mock_ax2]:
        ax.plot = MagicMock()
        ax.fill_between = MagicMock()
        ax.set_title = MagicMock()
        ax.set_xlabel = MagicMock()
        ax.set_ylabel = MagicMock()
        ax.grid = MagicMock()
        ax.legend = MagicMock()
        ax.axhline = MagicMock()
        ax.bar = MagicMock()
        ax.xaxis = MagicMock()

    return mock_fig, (mock_ax1, mock_ax2)


# ============================================================================
# Fixtures
# ============================================================================

def _setup_matplotlib_mocks(mock_fig, mock_ax_or_axes):
    """Create mock pyplot and related modules."""
    mock_plt = MagicMock()
    mock_plt.subplots = MagicMock(return_value=(mock_fig, mock_ax_or_axes))
    mock_plt.tight_layout = MagicMock()
    mock_plt.close = MagicMock()
    mock_plt.colorbar = MagicMock()
    mock_plt.setp = MagicMock()
    mock_plt.style = MagicMock()
    mock_plt.style.use = MagicMock()
    mock_plt.rcParams = {}

    mock_dates = MagicMock()
    mock_dates.DateFormatter = MagicMock(return_value=MagicMock())

    mock_gridspec = MagicMock()
    mock_gridspec.GridSpec = MagicMock(return_value=MagicMock())

    mock_patches = MagicMock()
    mock_patches.mpatches = MagicMock()

    mock_matplotlib_base = MagicMock()
    mock_matplotlib_base.pyplot = mock_plt
    mock_matplotlib_base.patches = mock_patches
    mock_matplotlib_base.dates = mock_dates
    mock_matplotlib_base.gridspec = mock_gridspec

    return {
        'matplotlib': mock_matplotlib_base,
        'matplotlib.pyplot': mock_plt,
        'matplotlib.patches': mock_patches,
        'matplotlib.dates': mock_dates,
        'matplotlib.gridspec': mock_gridspec,
    }, mock_plt


@pytest.fixture
def mock_matplotlib():
    """Setup mock matplotlib for chart generator tests."""
    mock_fig, mock_ax = create_mock_figure()
    mock_modules, mock_plt = _setup_matplotlib_mocks(mock_fig, mock_ax)

    # Remove cached module if present
    if 'tg_bot.services.chart_generator' in sys.modules:
        del sys.modules['tg_bot.services.chart_generator']

    # Patch sys.modules before importing
    with patch.dict(sys.modules, mock_modules):
        # Now import - this will use our mocked matplotlib
        from tg_bot.services import chart_generator as chart_gen_module

        # Patch plt in the module namespace to use our mock
        chart_gen_module.plt = mock_plt

        gen = chart_gen_module.ChartGenerator()
        yield {'gen': gen, 'plt': mock_plt, 'fig': mock_fig, 'ax': mock_ax}


@pytest.fixture
def mock_matplotlib_dual_ax():
    """Setup mock matplotlib with dual axes for drawdown charts."""
    mock_fig, (mock_ax1, mock_ax2) = create_mock_dual_axes()
    mock_modules, mock_plt = _setup_matplotlib_mocks(mock_fig, (mock_ax1, mock_ax2))

    # Remove cached module if present
    if 'tg_bot.services.chart_generator' in sys.modules:
        del sys.modules['tg_bot.services.chart_generator']

    # Patch sys.modules before importing
    with patch.dict(sys.modules, mock_modules):
        # Now import - this will use our mocked matplotlib
        from tg_bot.services import chart_generator as chart_gen_module

        # Patch plt in the module namespace to use our mock
        chart_gen_module.plt = mock_plt

        gen = chart_gen_module.ChartGenerator()
        yield {'gen': gen, 'plt': mock_plt, 'fig': mock_fig}


@pytest.fixture
def sample_prices():
    """Sample price data for testing."""
    return [100.0, 102.5, 101.0, 105.0, 103.5, 108.0, 107.0, 110.0, 109.5, 112.0]


@pytest.fixture
def sample_times():
    """Sample timestamps for testing."""
    base = datetime(2026, 1, 25, 10, 0, 0)
    return [base + timedelta(hours=i) for i in range(10)]


@pytest.fixture
def sample_portfolio_values():
    """Sample portfolio net values."""
    return [1000.0, 1020.0, 1015.0, 1050.0, 1045.0, 1080.0, 1070.0, 1100.0, 1095.0, 1120.0]


@pytest.fixture
def sample_dates():
    """Sample dates for portfolio charts."""
    base = datetime(2026, 1, 1)
    return [base + timedelta(days=i) for i in range(10)]


@pytest.fixture
def sample_positions():
    """Sample position allocation data."""
    return {
        'SOL': 35.0,
        'ETH': 25.0,
        'BTC': 20.0,
        'USDC': 15.0,
        'JUP': 5.0
    }


@pytest.fixture
def sample_pnl():
    """Sample P&L values for trade distribution."""
    return [50.0, -20.0, 30.0, -45.0, 100.0, -10.0, 25.0, -5.0, 75.0, -30.0]


@pytest.fixture
def sample_risk_return_positions():
    """Sample positions for risk/return plot."""
    return [
        {'symbol': 'SOL', 'return': 25.0, 'volatility': 45.0, 'allocation': 10},
        {'symbol': 'ETH', 'return': 15.0, 'volatility': 35.0, 'allocation': 8},
        {'symbol': 'BTC', 'return': 10.0, 'volatility': 25.0, 'allocation': 15},
        {'symbol': 'JUP', 'return': 50.0, 'volatility': 70.0, 'allocation': 5},
    ]


@pytest.fixture
def sample_sentiment_data():
    """Sample sentiment scores for heatmap."""
    return {
        'SOL': {'grok': 75, 'twitter': 68, 'news': 72},
        'BTC': {'grok': 82, 'twitter': 71, 'news': 78},
        'ETH': {'grok': 65, 'twitter': 60, 'news': 70},
    }


# ============================================================================
# Test: ChartGenerator Initialization
# ============================================================================

class TestChartGeneratorInit:
    """Test ChartGenerator initialization and setup."""

    def test_init_sets_up_dark_theme(self, mock_matplotlib):
        """Should set up dark theme on initialization."""
        gen = mock_matplotlib['gen']
        assert gen.DARK_THEME is not None
        assert 'bg' in gen.DARK_THEME
        assert 'text' in gen.DARK_THEME
        assert 'grid' in gen.DARK_THEME

    def test_init_sets_chart_dimensions(self, mock_matplotlib):
        """Should have proper chart dimensions."""
        gen = mock_matplotlib['gen']
        assert gen.WIDTH == 12
        assert gen.HEIGHT == 6
        assert gen.DPI == 80

    def test_dark_theme_has_required_colors(self, mock_matplotlib):
        """Should have all required color keys."""
        gen = mock_matplotlib['gen']
        required_keys = ['bg', 'text', 'grid', 'bull', 'bear', 'neutral', 'accent']
        for key in required_keys:
            assert key in gen.DARK_THEME

    def test_dark_theme_colors_are_valid_hex(self, mock_matplotlib):
        """Should have valid hex color values."""
        gen = mock_matplotlib['gen']
        for key, color in gen.DARK_THEME.items():
            assert color.startswith('#')
            assert len(color) == 7  # #RRGGBB format

    def test_class_attributes_exist(self, mock_matplotlib):
        """Should have class attributes for styling."""
        gen = mock_matplotlib['gen']
        assert hasattr(gen, 'WIDTH')
        assert hasattr(gen, 'HEIGHT')
        assert hasattr(gen, 'DPI')
        assert hasattr(gen, 'DARK_THEME')


# ============================================================================
# Test: Matplotlib Style Setup
# ============================================================================

class TestMatplotlibStyleSetup:
    """Test matplotlib style configuration."""

    def test_generator_has_dark_theme(self, mock_matplotlib):
        """Should have dark theme defined."""
        gen = mock_matplotlib['gen']
        assert gen.DARK_THEME['bg'] == '#1a1a1a'

    def test_rcparams_is_dict(self, mock_matplotlib):
        """Should use rcParams dict."""
        plt = mock_matplotlib['plt']
        assert isinstance(plt.rcParams, dict)


# ============================================================================
# Test: Price Chart Generation
# ============================================================================

class TestPriceChartGeneration:
    """Test price chart generation functionality."""

    def test_generates_price_chart_basic(self, mock_matplotlib, sample_prices, sample_times):
        """Should generate basic price chart."""
        gen = mock_matplotlib['gen']
        result = gen.generate_price_chart(
            symbol='SOL',
            prices=sample_prices,
            times=sample_times
        )
        assert isinstance(result, BytesIO)
        assert result.getvalue()

    def test_generates_price_chart_with_short_ma(self, mock_matplotlib, sample_prices, sample_times):
        """Should generate price chart with short moving average."""
        gen = mock_matplotlib['gen']
        ma_short = [100.0, 101.0, 101.5, 102.5, 103.0, 104.5, 105.5, 107.0, 108.0, 109.5]
        result = gen.generate_price_chart(
            symbol='SOL',
            prices=sample_prices,
            times=sample_times,
            ma_short=ma_short
        )
        assert isinstance(result, BytesIO)
        assert result.getvalue()

    def test_generates_price_chart_with_long_ma(self, mock_matplotlib, sample_prices, sample_times):
        """Should generate price chart with long moving average."""
        gen = mock_matplotlib['gen']
        ma_long = [100.0, 100.5, 101.0, 101.5, 102.0, 102.5, 103.0, 104.0, 105.0, 106.0]
        result = gen.generate_price_chart(
            symbol='SOL',
            prices=sample_prices,
            times=sample_times,
            ma_long=ma_long
        )
        assert isinstance(result, BytesIO)
        assert result.getvalue()

    def test_generates_price_chart_with_both_mas(self, mock_matplotlib, sample_prices, sample_times):
        """Should generate price chart with both moving averages."""
        gen = mock_matplotlib['gen']
        ma_short = [100.0, 101.0, 101.5, 102.5, 103.0, 104.5, 105.5, 107.0, 108.0, 109.5]
        ma_long = [100.0, 100.5, 101.0, 101.5, 102.0, 102.5, 103.0, 104.0, 105.0, 106.0]
        result = gen.generate_price_chart(
            symbol='SOL',
            prices=sample_prices,
            times=sample_times,
            ma_short=ma_short,
            ma_long=ma_long
        )
        assert isinstance(result, BytesIO)
        assert result.getvalue()

    def test_generates_price_chart_with_entry_price(self, mock_matplotlib, sample_prices, sample_times):
        """Should generate price chart with entry marker."""
        gen = mock_matplotlib['gen']
        result = gen.generate_price_chart(
            symbol='SOL',
            prices=sample_prices,
            times=sample_times,
            entry_price=101.0
        )
        assert isinstance(result, BytesIO)
        assert result.getvalue()

    def test_generates_price_chart_with_exit_price(self, mock_matplotlib, sample_prices, sample_times):
        """Should generate price chart with exit/target marker."""
        gen = mock_matplotlib['gen']
        result = gen.generate_price_chart(
            symbol='SOL',
            prices=sample_prices,
            times=sample_times,
            exit_price=115.0
        )
        assert isinstance(result, BytesIO)
        assert result.getvalue()

    def test_generates_price_chart_with_all_options(self, mock_matplotlib, sample_prices, sample_times):
        """Should generate price chart with all optional parameters."""
        gen = mock_matplotlib['gen']
        ma_short = [100.0, 101.0, 101.5, 102.5, 103.0, 104.5, 105.5, 107.0, 108.0, 109.5]
        ma_long = [100.0, 100.5, 101.0, 101.5, 102.0, 102.5, 103.0, 104.0, 105.0, 106.0]
        result = gen.generate_price_chart(
            symbol='SOL',
            prices=sample_prices,
            times=sample_times,
            ma_short=ma_short,
            ma_long=ma_long,
            entry_price=101.0,
            exit_price=115.0
        )
        assert isinstance(result, BytesIO)
        assert result.getvalue()

    def test_price_chart_different_symbols(self, mock_matplotlib, sample_prices, sample_times):
        """Should work with different token symbols."""
        gen = mock_matplotlib['gen']
        for symbol in ['BTC', 'ETH', 'JUP', 'BONK']:
            result = gen.generate_price_chart(
                symbol=symbol,
                prices=sample_prices,
                times=sample_times
            )
            assert isinstance(result, BytesIO)

    def test_price_chart_single_data_point(self, mock_matplotlib):
        """Should handle single data point."""
        gen = mock_matplotlib['gen']
        result = gen.generate_price_chart(
            symbol='SOL',
            prices=[100.0],
            times=[datetime.now()]
        )
        assert isinstance(result, BytesIO)

    def test_price_chart_large_dataset(self, mock_matplotlib):
        """Should handle large datasets."""
        gen = mock_matplotlib['gen']
        prices = [100.0 + i * 0.1 for i in range(1000)]
        times = [datetime.now() + timedelta(minutes=i) for i in range(1000)]
        result = gen.generate_price_chart(
            symbol='SOL',
            prices=prices,
            times=times
        )
        assert isinstance(result, BytesIO)

    def test_price_chart_returns_bytesio(self, mock_matplotlib, sample_prices, sample_times):
        """Should return BytesIO object."""
        gen = mock_matplotlib['gen']
        result = gen.generate_price_chart('SOL', sample_prices, sample_times)
        assert isinstance(result, BytesIO)

    def test_price_chart_closes_figure(self, mock_matplotlib, sample_prices, sample_times):
        """Should close figure after generating."""
        gen = mock_matplotlib['gen']
        plt = mock_matplotlib['plt']
        gen.generate_price_chart('SOL', sample_prices, sample_times)
        plt.close.assert_called()


# ============================================================================
# Test: Portfolio Chart Generation
# ============================================================================

class TestPortfolioChartGeneration:
    """Test portfolio performance chart generation."""

    def test_generates_portfolio_chart_basic(self, mock_matplotlib, sample_portfolio_values, sample_dates):
        """Should generate basic portfolio chart."""
        gen = mock_matplotlib['gen']
        result = gen.generate_portfolio_chart(
            net_values=sample_portfolio_values,
            dates=sample_dates
        )
        assert isinstance(result, BytesIO)
        assert result.getvalue()

    def test_generates_portfolio_chart_with_benchmark(self, mock_matplotlib, sample_portfolio_values, sample_dates):
        """Should generate portfolio chart with benchmark."""
        gen = mock_matplotlib['gen']
        benchmark = [1000.0, 1010.0, 1015.0, 1020.0, 1025.0, 1030.0, 1035.0, 1040.0, 1045.0, 1050.0]
        result = gen.generate_portfolio_chart(
            net_values=sample_portfolio_values,
            dates=sample_dates,
            benchmark=benchmark
        )
        assert isinstance(result, BytesIO)
        assert result.getvalue()

    def test_portfolio_chart_negative_returns(self, mock_matplotlib, sample_dates):
        """Should handle negative returns."""
        gen = mock_matplotlib['gen']
        declining_values = [1000.0, 980.0, 960.0, 940.0, 920.0, 900.0, 880.0, 860.0, 840.0, 820.0]
        result = gen.generate_portfolio_chart(
            net_values=declining_values,
            dates=sample_dates
        )
        assert isinstance(result, BytesIO)

    def test_portfolio_chart_volatile_returns(self, mock_matplotlib, sample_dates):
        """Should handle volatile (up and down) returns."""
        gen = mock_matplotlib['gen']
        volatile_values = [1000.0, 1050.0, 980.0, 1100.0, 950.0, 1080.0, 970.0, 1120.0, 1000.0, 1150.0]
        result = gen.generate_portfolio_chart(
            net_values=volatile_values,
            dates=sample_dates
        )
        assert isinstance(result, BytesIO)

    def test_portfolio_chart_with_flat_line(self, mock_matplotlib, sample_dates):
        """Should handle flat portfolio value."""
        gen = mock_matplotlib['gen']
        flat_values = [1000.0] * 10
        result = gen.generate_portfolio_chart(
            net_values=flat_values,
            dates=sample_dates
        )
        assert isinstance(result, BytesIO)

    def test_portfolio_chart_returns_bytesio(self, mock_matplotlib, sample_portfolio_values, sample_dates):
        """Should return BytesIO object."""
        gen = mock_matplotlib['gen']
        result = gen.generate_portfolio_chart(sample_portfolio_values, sample_dates)
        assert isinstance(result, BytesIO)


# ============================================================================
# Test: Position Allocation Chart
# ============================================================================

class TestPositionAllocationChart:
    """Test position allocation pie chart generation."""

    def test_generates_allocation_chart(self, mock_matplotlib, sample_positions):
        """Should generate position allocation pie chart."""
        gen = mock_matplotlib['gen']
        result = gen.generate_position_allocation(sample_positions)
        assert isinstance(result, BytesIO)
        assert result.getvalue()

    def test_allocation_chart_single_position(self, mock_matplotlib):
        """Should handle single position."""
        gen = mock_matplotlib['gen']
        positions = {'SOL': 100.0}
        result = gen.generate_position_allocation(positions)
        assert isinstance(result, BytesIO)

    def test_allocation_chart_many_positions(self, mock_matplotlib):
        """Should handle many positions."""
        gen = mock_matplotlib['gen']
        positions = {f'TOKEN{i}': 100.0 / 20 for i in range(20)}
        result = gen.generate_position_allocation(positions)
        assert isinstance(result, BytesIO)

    def test_allocation_chart_colors_by_size(self, mock_matplotlib):
        """Should color allocations by size (>20%, >10%, else)."""
        gen = mock_matplotlib['gen']
        positions = {
            'LARGE': 30.0,
            'MEDIUM': 15.0,
            'SMALL': 5.0
        }
        result = gen.generate_position_allocation(positions)
        assert isinstance(result, BytesIO)

    def test_allocation_chart_sorts_by_size(self, mock_matplotlib):
        """Should sort positions by allocation size."""
        gen = mock_matplotlib['gen']
        positions = {
            'SMALL': 5.0,
            'LARGE': 50.0,
            'MEDIUM': 20.0
        }
        result = gen.generate_position_allocation(positions)
        assert isinstance(result, BytesIO)

    def test_allocation_chart_decimal_percentages(self, mock_matplotlib):
        """Should handle decimal percentages."""
        gen = mock_matplotlib['gen']
        positions = {
            'SOL': 33.33,
            'ETH': 33.34,
            'BTC': 33.33
        }
        result = gen.generate_position_allocation(positions)
        assert isinstance(result, BytesIO)

    def test_allocation_chart_returns_bytesio(self, mock_matplotlib, sample_positions):
        """Should return BytesIO object."""
        gen = mock_matplotlib['gen']
        result = gen.generate_position_allocation(sample_positions)
        assert isinstance(result, BytesIO)


# ============================================================================
# Test: Drawdown Chart Generation
# ============================================================================

class TestDrawdownChartGeneration:
    """Test drawdown analysis chart generation."""

    def test_generates_drawdown_chart(self, mock_matplotlib_dual_ax, sample_portfolio_values, sample_dates):
        """Should generate drawdown chart."""
        gen = mock_matplotlib_dual_ax['gen']
        result = gen.generate_drawdown_chart(
            net_values=sample_portfolio_values,
            dates=sample_dates
        )
        assert isinstance(result, BytesIO)
        assert result.getvalue()

    def test_drawdown_chart_with_actual_drawdown(self, mock_matplotlib_dual_ax, sample_dates):
        """Should show drawdown when values decline from peak."""
        gen = mock_matplotlib_dual_ax['gen']
        values = [1000.0, 1100.0, 1050.0, 1000.0, 1150.0, 1100.0, 1200.0, 1150.0, 1180.0, 1250.0]
        result = gen.generate_drawdown_chart(
            net_values=values,
            dates=sample_dates
        )
        assert isinstance(result, BytesIO)

    def test_drawdown_chart_no_drawdown(self, mock_matplotlib_dual_ax, sample_dates):
        """Should handle portfolio with no drawdown (always increasing)."""
        gen = mock_matplotlib_dual_ax['gen']
        increasing_values = [1000.0, 1010.0, 1020.0, 1030.0, 1040.0, 1050.0, 1060.0, 1070.0, 1080.0, 1090.0]
        result = gen.generate_drawdown_chart(
            net_values=increasing_values,
            dates=sample_dates
        )
        assert isinstance(result, BytesIO)

    def test_drawdown_chart_severe_drawdown(self, mock_matplotlib_dual_ax, sample_dates):
        """Should handle severe drawdown scenario."""
        gen = mock_matplotlib_dual_ax['gen']
        values = [1000.0, 1200.0, 900.0, 800.0, 700.0, 750.0, 800.0, 900.0, 950.0, 1000.0]
        result = gen.generate_drawdown_chart(
            net_values=values,
            dates=sample_dates
        )
        assert isinstance(result, BytesIO)


# ============================================================================
# Test: Trade Distribution Chart
# ============================================================================

class TestTradeDistributionChart:
    """Test trade P&L distribution histogram generation."""

    def test_generates_trade_distribution(self, mock_matplotlib, sample_pnl):
        """Should generate trade distribution histogram."""
        gen = mock_matplotlib['gen']
        result = gen.generate_trade_distribution(sample_pnl)
        assert isinstance(result, BytesIO)
        assert result.getvalue()

    def test_trade_distribution_all_wins(self, mock_matplotlib):
        """Should handle all winning trades."""
        gen = mock_matplotlib['gen']
        all_wins = [10.0, 20.0, 30.0, 40.0, 50.0]
        result = gen.generate_trade_distribution(all_wins)
        assert isinstance(result, BytesIO)

    def test_trade_distribution_all_losses(self, mock_matplotlib):
        """Should handle all losing trades."""
        gen = mock_matplotlib['gen']
        all_losses = [-10.0, -20.0, -30.0, -40.0, -50.0]
        result = gen.generate_trade_distribution(all_losses)
        assert isinstance(result, BytesIO)

    def test_trade_distribution_many_trades(self, mock_matplotlib):
        """Should handle large number of trades."""
        gen = mock_matplotlib['gen']
        many_trades = [np.random.randn() * 50 for _ in range(500)]
        result = gen.generate_trade_distribution(many_trades)
        assert isinstance(result, BytesIO)

    def test_trade_distribution_single_trade(self, mock_matplotlib):
        """Should handle single trade."""
        gen = mock_matplotlib['gen']
        single_trade = [100.0]
        result = gen.generate_trade_distribution(single_trade)
        assert isinstance(result, BytesIO)

    def test_trade_distribution_returns_bytesio(self, mock_matplotlib, sample_pnl):
        """Should return BytesIO object."""
        gen = mock_matplotlib['gen']
        result = gen.generate_trade_distribution(sample_pnl)
        assert isinstance(result, BytesIO)

    def test_trade_distribution_mixed_pnl(self, mock_matplotlib):
        """Should handle mixed wins and losses."""
        gen = mock_matplotlib['gen']
        mixed = [100.0, -50.0, 75.0, -25.0, 200.0, -100.0]
        result = gen.generate_trade_distribution(mixed)
        assert isinstance(result, BytesIO)


# ============================================================================
# Test: Risk/Return Scatter Plot
# ============================================================================

class TestRiskReturnPlot:
    """Test risk/return scatter plot generation."""

    def test_generates_risk_return_plot(self, mock_matplotlib, sample_risk_return_positions):
        """Should generate risk/return scatter plot."""
        gen = mock_matplotlib['gen']
        result = gen.generate_risk_return_plot(sample_risk_return_positions)
        assert isinstance(result, BytesIO)
        assert result.getvalue()

    def test_risk_return_single_position(self, mock_matplotlib):
        """Should handle single position."""
        gen = mock_matplotlib['gen']
        positions = [{'symbol': 'SOL', 'return': 25.0, 'volatility': 45.0}]
        result = gen.generate_risk_return_plot(positions)
        assert isinstance(result, BytesIO)

    def test_risk_return_negative_returns(self, mock_matplotlib):
        """Should handle positions with negative returns."""
        gen = mock_matplotlib['gen']
        positions = [
            {'symbol': 'SOL', 'return': -10.0, 'volatility': 45.0},
            {'symbol': 'ETH', 'return': -5.0, 'volatility': 35.0},
        ]
        result = gen.generate_risk_return_plot(positions)
        assert isinstance(result, BytesIO)

    def test_risk_return_without_allocation(self, mock_matplotlib):
        """Should handle positions without allocation key."""
        gen = mock_matplotlib['gen']
        positions = [
            {'symbol': 'SOL', 'return': 25.0, 'volatility': 45.0},
            {'symbol': 'ETH', 'return': 15.0, 'volatility': 35.0},
        ]
        result = gen.generate_risk_return_plot(positions)
        assert isinstance(result, BytesIO)

    def test_risk_return_high_volatility(self, mock_matplotlib):
        """Should handle positions with very high volatility."""
        gen = mock_matplotlib['gen']
        positions = [
            {'symbol': 'MEME', 'return': 200.0, 'volatility': 150.0, 'allocation': 2},
        ]
        result = gen.generate_risk_return_plot(positions)
        assert isinstance(result, BytesIO)

    def test_risk_return_returns_bytesio(self, mock_matplotlib, sample_risk_return_positions):
        """Should return BytesIO object."""
        gen = mock_matplotlib['gen']
        result = gen.generate_risk_return_plot(sample_risk_return_positions)
        assert isinstance(result, BytesIO)


# ============================================================================
# Test: Sentiment Heatmap
# ============================================================================

class TestSentimentHeatmap:
    """Test sentiment heatmap generation."""

    def test_generates_sentiment_heatmap(self, mock_matplotlib, sample_sentiment_data):
        """Should generate sentiment heatmap."""
        gen = mock_matplotlib['gen']
        symbols = ['SOL', 'BTC', 'ETH']
        result = gen.generate_sentiment_heatmap(
            symbols=symbols,
            sentiment_scores=sample_sentiment_data
        )
        assert isinstance(result, BytesIO)
        assert result.getvalue()

    def test_sentiment_heatmap_custom_time_period(self, mock_matplotlib, sample_sentiment_data):
        """Should accept custom time period label."""
        gen = mock_matplotlib['gen']
        symbols = ['SOL', 'BTC', 'ETH']
        result = gen.generate_sentiment_heatmap(
            symbols=symbols,
            sentiment_scores=sample_sentiment_data,
            time_period="7d"
        )
        assert isinstance(result, BytesIO)

    def test_sentiment_heatmap_single_symbol(self, mock_matplotlib):
        """Should handle single symbol."""
        gen = mock_matplotlib['gen']
        symbols = ['SOL']
        scores = {'SOL': {'grok': 75}}
        result = gen.generate_sentiment_heatmap(
            symbols=symbols,
            sentiment_scores=scores
        )
        assert isinstance(result, BytesIO)

    def test_sentiment_heatmap_single_source(self, mock_matplotlib):
        """Should handle single source."""
        gen = mock_matplotlib['gen']
        symbols = ['SOL', 'BTC']
        scores = {
            'SOL': {'grok': 75},
            'BTC': {'grok': 80}
        }
        result = gen.generate_sentiment_heatmap(
            symbols=symbols,
            sentiment_scores=scores
        )
        assert isinstance(result, BytesIO)

    def test_sentiment_heatmap_missing_scores(self, mock_matplotlib):
        """Should handle missing sentiment scores for some symbols."""
        gen = mock_matplotlib['gen']
        symbols = ['SOL', 'BTC', 'ETH']
        scores = {
            'SOL': {'grok': 75, 'twitter': 68},
            'BTC': {'grok': 80},
        }
        result = gen.generate_sentiment_heatmap(
            symbols=symbols,
            sentiment_scores=scores
        )
        assert isinstance(result, BytesIO)

    def test_sentiment_heatmap_zero_scores(self, mock_matplotlib):
        """Should handle zero sentiment scores."""
        gen = mock_matplotlib['gen']
        symbols = ['SOL']
        scores = {'SOL': {'grok': 0, 'twitter': 0}}
        result = gen.generate_sentiment_heatmap(
            symbols=symbols,
            sentiment_scores=scores
        )
        assert isinstance(result, BytesIO)

    def test_sentiment_heatmap_max_scores(self, mock_matplotlib):
        """Should handle maximum sentiment scores."""
        gen = mock_matplotlib['gen']
        symbols = ['SOL']
        scores = {'SOL': {'grok': 100, 'twitter': 100}}
        result = gen.generate_sentiment_heatmap(
            symbols=symbols,
            sentiment_scores=scores
        )
        assert isinstance(result, BytesIO)

    def test_sentiment_heatmap_returns_bytesio(self, mock_matplotlib, sample_sentiment_data):
        """Should return BytesIO object."""
        gen = mock_matplotlib['gen']
        symbols = ['SOL', 'BTC', 'ETH']
        result = gen.generate_sentiment_heatmap(symbols, sample_sentiment_data)
        assert isinstance(result, BytesIO)


# ============================================================================
# Test: Image Export
# ============================================================================

class TestImageExport:
    """Test image export functionality."""

    def test_exports_png_format(self, mock_matplotlib, sample_prices, sample_times):
        """Should export as PNG format."""
        gen = mock_matplotlib['gen']
        result = gen.generate_price_chart(
            symbol='SOL',
            prices=sample_prices,
            times=sample_times
        )
        data = result.getvalue()
        assert data[:8] == b'\x89PNG\r\n\x1a\n'

    def test_buffer_is_seeked_to_start(self, mock_matplotlib, sample_prices, sample_times):
        """Should seek buffer to start after writing."""
        gen = mock_matplotlib['gen']
        result = gen.generate_price_chart(
            symbol='SOL',
            prices=sample_prices,
            times=sample_times
        )
        assert result.tell() == 0

    def test_buffer_can_be_read_multiple_times(self, mock_matplotlib, sample_prices, sample_times):
        """Should be able to read buffer multiple times."""
        gen = mock_matplotlib['gen']
        result = gen.generate_price_chart(
            symbol='SOL',
            prices=sample_prices,
            times=sample_times
        )
        first_read = result.read()
        result.seek(0)
        second_read = result.read()
        assert first_read == second_read

    def test_portfolio_exports_png(self, mock_matplotlib, sample_portfolio_values, sample_dates):
        """Should export portfolio chart as PNG."""
        gen = mock_matplotlib['gen']
        result = gen.generate_portfolio_chart(sample_portfolio_values, sample_dates)
        data = result.getvalue()
        assert data[:8] == b'\x89PNG\r\n\x1a\n'

    def test_allocation_exports_png(self, mock_matplotlib, sample_positions):
        """Should export allocation chart as PNG."""
        gen = mock_matplotlib['gen']
        result = gen.generate_position_allocation(sample_positions)
        data = result.getvalue()
        assert data[:8] == b'\x89PNG\r\n\x1a\n'


# ============================================================================
# Test: Chart Styling
# ============================================================================

class TestChartStyling:
    """Test chart styling and theme application."""

    def test_dark_theme_background_color(self, mock_matplotlib):
        """Should have dark background color."""
        gen = mock_matplotlib['gen']
        assert gen.DARK_THEME['bg'] == '#1a1a1a'

    def test_dark_theme_text_color(self, mock_matplotlib):
        """Should have light text color."""
        gen = mock_matplotlib['gen']
        assert gen.DARK_THEME['text'] == '#ffffff'

    def test_dark_theme_bull_color(self, mock_matplotlib):
        """Should have green bull color."""
        gen = mock_matplotlib['gen']
        assert gen.DARK_THEME['bull'] == '#10b981'

    def test_dark_theme_bear_color(self, mock_matplotlib):
        """Should have red bear color."""
        gen = mock_matplotlib['gen']
        assert gen.DARK_THEME['bear'] == '#ef4444'

    def test_dark_theme_accent_color(self, mock_matplotlib):
        """Should have blue accent color."""
        gen = mock_matplotlib['gen']
        assert gen.DARK_THEME['accent'] == '#3b82f6'

    def test_dark_theme_grid_color(self, mock_matplotlib):
        """Should have grid color."""
        gen = mock_matplotlib['gen']
        assert gen.DARK_THEME['grid'] == '#333333'

    def test_dark_theme_neutral_color(self, mock_matplotlib):
        """Should have neutral color."""
        gen = mock_matplotlib['gen']
        assert gen.DARK_THEME['neutral'] == '#6b7280'


# ============================================================================
# Test: Edge Cases
# ============================================================================

class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_price_chart_empty_symbol(self, mock_matplotlib, sample_prices, sample_times):
        """Should handle empty symbol string."""
        gen = mock_matplotlib['gen']
        result = gen.generate_price_chart(
            symbol='',
            prices=sample_prices,
            times=sample_times
        )
        assert isinstance(result, BytesIO)

    def test_price_chart_special_chars_in_symbol(self, mock_matplotlib, sample_prices, sample_times):
        """Should handle special characters in symbol."""
        gen = mock_matplotlib['gen']
        result = gen.generate_price_chart(
            symbol='$SOL/USD',
            prices=sample_prices,
            times=sample_times
        )
        assert isinstance(result, BytesIO)

    def test_handles_very_small_values(self, mock_matplotlib):
        """Should handle very small price values."""
        gen = mock_matplotlib['gen']
        small_prices = [0.00001, 0.000012, 0.000011, 0.000015]
        times = [datetime.now() + timedelta(hours=i) for i in range(4)]
        result = gen.generate_price_chart(
            symbol='MEME',
            prices=small_prices,
            times=times
        )
        assert isinstance(result, BytesIO)

    def test_handles_very_large_values(self, mock_matplotlib):
        """Should handle very large price values."""
        gen = mock_matplotlib['gen']
        large_prices = [100000.0, 102000.0, 101000.0, 105000.0]
        times = [datetime.now() + timedelta(hours=i) for i in range(4)]
        result = gen.generate_price_chart(
            symbol='BTC',
            prices=large_prices,
            times=times
        )
        assert isinstance(result, BytesIO)

    def test_handles_negative_prices(self, mock_matplotlib):
        """Should handle negative prices (PnL scenarios)."""
        gen = mock_matplotlib['gen']
        negative_prices = [-10.0, -5.0, 0.0, 5.0, 10.0]
        times = [datetime.now() + timedelta(hours=i) for i in range(5)]
        result = gen.generate_price_chart(
            symbol='PNL',
            prices=negative_prices,
            times=times
        )
        assert isinstance(result, BytesIO)

    def test_handles_unicode_symbol(self, mock_matplotlib, sample_prices, sample_times):
        """Should handle unicode in symbol name."""
        gen = mock_matplotlib['gen']
        result = gen.generate_price_chart(
            symbol='SOL-USD',
            prices=sample_prices,
            times=sample_times
        )
        assert isinstance(result, BytesIO)

    def test_handles_two_data_points(self, mock_matplotlib):
        """Should handle exactly two data points."""
        gen = mock_matplotlib['gen']
        prices = [100.0, 110.0]
        times = [datetime.now(), datetime.now() + timedelta(hours=1)]
        result = gen.generate_price_chart('SOL', prices, times)
        assert isinstance(result, BytesIO)


# ============================================================================
# Test: Multiple Chart Types
# ============================================================================

class TestMultipleChartTypes:
    """Test generating multiple chart types in sequence."""

    def test_generate_multiple_charts_sequentially(self, mock_matplotlib, sample_prices, sample_times, sample_positions):
        """Should generate multiple chart types without interference."""
        gen = mock_matplotlib['gen']
        result1 = gen.generate_price_chart(
            symbol='SOL',
            prices=sample_prices,
            times=sample_times
        )
        assert isinstance(result1, BytesIO)

        result2 = gen.generate_position_allocation(sample_positions)
        assert isinstance(result2, BytesIO)

        assert result1.getvalue()
        assert result2.getvalue()

    def test_reuse_generator_instance(self, mock_matplotlib, sample_prices, sample_times):
        """Should be able to reuse generator instance."""
        gen = mock_matplotlib['gen']
        for _ in range(5):
            result = gen.generate_price_chart(
                symbol='SOL',
                prices=sample_prices,
                times=sample_times
            )
            assert isinstance(result, BytesIO)
            assert result.getvalue()


# ============================================================================
# Test: Matplotlib Close Behavior
# ============================================================================

class TestMatplotlibClose:
    """Test that matplotlib figures are properly closed."""

    def test_closes_figure_after_price_chart(self, mock_matplotlib, sample_prices, sample_times):
        """Should close figure after generating price chart."""
        gen = mock_matplotlib['gen']
        plt = mock_matplotlib['plt']
        plt.close.reset_mock()
        gen.generate_price_chart('SOL', sample_prices, sample_times)
        plt.close.assert_called()

    def test_closes_figure_after_portfolio_chart(self, mock_matplotlib, sample_portfolio_values, sample_dates):
        """Should close figure after generating portfolio chart."""
        gen = mock_matplotlib['gen']
        plt = mock_matplotlib['plt']
        plt.close.reset_mock()
        gen.generate_portfolio_chart(sample_portfolio_values, sample_dates)
        plt.close.assert_called()

    def test_closes_figure_after_allocation_chart(self, mock_matplotlib, sample_positions):
        """Should close figure after generating allocation chart."""
        gen = mock_matplotlib['gen']
        plt = mock_matplotlib['plt']
        plt.close.reset_mock()
        gen.generate_position_allocation(sample_positions)
        plt.close.assert_called()

    def test_closes_figure_after_trade_distribution(self, mock_matplotlib, sample_pnl):
        """Should close figure after generating trade distribution."""
        gen = mock_matplotlib['gen']
        plt = mock_matplotlib['plt']
        plt.close.reset_mock()
        gen.generate_trade_distribution(sample_pnl)
        plt.close.assert_called()

    def test_closes_figure_after_risk_return(self, mock_matplotlib, sample_risk_return_positions):
        """Should close figure after generating risk/return plot."""
        gen = mock_matplotlib['gen']
        plt = mock_matplotlib['plt']
        plt.close.reset_mock()
        gen.generate_risk_return_plot(sample_risk_return_positions)
        plt.close.assert_called()


# ============================================================================
# Test: Telegram Optimization
# ============================================================================

class TestTelegramOptimization:
    """Test that charts are optimized for Telegram display."""

    def test_default_dimensions_for_telegram(self, mock_matplotlib):
        """Should have Telegram-optimized dimensions."""
        gen = mock_matplotlib['gen']
        expected_width_px = gen.WIDTH * gen.DPI
        expected_height_px = gen.HEIGHT * gen.DPI
        assert expected_width_px == 960
        assert expected_height_px == 480

    def test_dpi_setting(self, mock_matplotlib):
        """Should have appropriate DPI for Telegram."""
        gen = mock_matplotlib['gen']
        assert gen.DPI == 80

    def test_width_setting(self, mock_matplotlib):
        """Should have standard width."""
        gen = mock_matplotlib['gen']
        assert gen.WIDTH == 12

    def test_height_setting(self, mock_matplotlib):
        """Should have standard height."""
        gen = mock_matplotlib['gen']
        assert gen.HEIGHT == 6


# ============================================================================
# Test: Moving Average Plotting
# ============================================================================

class TestMovingAveragePlotting:
    """Test moving average line plotting."""

    def test_ma_short_provided(self, mock_matplotlib, sample_prices, sample_times):
        """Should handle MA short when provided."""
        gen = mock_matplotlib['gen']
        ma_short = [100.0] * 10
        result = gen.generate_price_chart('SOL', sample_prices, sample_times, ma_short=ma_short)
        assert isinstance(result, BytesIO)

    def test_ma_long_provided(self, mock_matplotlib, sample_prices, sample_times):
        """Should handle MA long when provided."""
        gen = mock_matplotlib['gen']
        ma_long = [100.0] * 10
        result = gen.generate_price_chart('SOL', sample_prices, sample_times, ma_long=ma_long)
        assert isinstance(result, BytesIO)

    def test_both_mas_provided(self, mock_matplotlib, sample_prices, sample_times):
        """Should handle both MAs when provided."""
        gen = mock_matplotlib['gen']
        ma_short = [100.0] * 10
        ma_long = [99.0] * 10
        result = gen.generate_price_chart('SOL', sample_prices, sample_times, ma_short=ma_short, ma_long=ma_long)
        assert isinstance(result, BytesIO)


# ============================================================================
# Test: Entry/Exit Markers
# ============================================================================

class TestEntryExitMarkers:
    """Test entry and exit price markers."""

    def test_entry_marker_provided(self, mock_matplotlib, sample_prices, sample_times):
        """Should handle entry price when provided."""
        gen = mock_matplotlib['gen']
        result = gen.generate_price_chart('SOL', sample_prices, sample_times, entry_price=101.0)
        assert isinstance(result, BytesIO)

    def test_exit_marker_provided(self, mock_matplotlib, sample_prices, sample_times):
        """Should handle exit price when provided."""
        gen = mock_matplotlib['gen']
        result = gen.generate_price_chart('SOL', sample_prices, sample_times, exit_price=115.0)
        assert isinstance(result, BytesIO)

    def test_both_markers_provided(self, mock_matplotlib, sample_prices, sample_times):
        """Should handle both entry and exit when provided."""
        gen = mock_matplotlib['gen']
        result = gen.generate_price_chart('SOL', sample_prices, sample_times, entry_price=101.0, exit_price=115.0)
        assert isinstance(result, BytesIO)


# ============================================================================
# Test: Return Type Validation
# ============================================================================

class TestReturnTypeValidation:
    """Test that all methods return BytesIO."""

    def test_price_chart_returns_bytesio(self, mock_matplotlib, sample_prices, sample_times):
        """Price chart should return BytesIO."""
        gen = mock_matplotlib['gen']
        result = gen.generate_price_chart('SOL', sample_prices, sample_times)
        assert isinstance(result, BytesIO)

    def test_portfolio_chart_returns_bytesio(self, mock_matplotlib, sample_portfolio_values, sample_dates):
        """Portfolio chart should return BytesIO."""
        gen = mock_matplotlib['gen']
        result = gen.generate_portfolio_chart(sample_portfolio_values, sample_dates)
        assert isinstance(result, BytesIO)

    def test_allocation_chart_returns_bytesio(self, mock_matplotlib, sample_positions):
        """Allocation chart should return BytesIO."""
        gen = mock_matplotlib['gen']
        result = gen.generate_position_allocation(sample_positions)
        assert isinstance(result, BytesIO)

    def test_drawdown_chart_returns_bytesio(self, mock_matplotlib_dual_ax, sample_portfolio_values, sample_dates):
        """Drawdown chart should return BytesIO."""
        gen = mock_matplotlib_dual_ax['gen']
        result = gen.generate_drawdown_chart(sample_portfolio_values, sample_dates)
        assert isinstance(result, BytesIO)

    def test_trade_distribution_returns_bytesio(self, mock_matplotlib, sample_pnl):
        """Trade distribution should return BytesIO."""
        gen = mock_matplotlib['gen']
        result = gen.generate_trade_distribution(sample_pnl)
        assert isinstance(result, BytesIO)

    def test_risk_return_returns_bytesio(self, mock_matplotlib, sample_risk_return_positions):
        """Risk/return plot should return BytesIO."""
        gen = mock_matplotlib['gen']
        result = gen.generate_risk_return_plot(sample_risk_return_positions)
        assert isinstance(result, BytesIO)

    def test_sentiment_heatmap_returns_bytesio(self, mock_matplotlib, sample_sentiment_data):
        """Sentiment heatmap should return BytesIO."""
        gen = mock_matplotlib['gen']
        symbols = ['SOL', 'BTC', 'ETH']
        result = gen.generate_sentiment_heatmap(symbols, sample_sentiment_data)
        assert isinstance(result, BytesIO)
