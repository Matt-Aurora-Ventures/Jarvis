"""
Backtester Engine Tests

Comprehensive tests for the backtesting engine including:
- Historical data loading
- Strategy execution
- PnL calculation
- Performance metrics
- Trade simulation
- Indicator calculations
- Database operations
"""

import pytest
import tempfile
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch
import sqlite3


# =============================================================================
# ENUM AND DATACLASS TESTS
# =============================================================================

class TestBacktesterEnums:
    """Test enum definitions for backtester."""

    def test_order_side_enum_values(self):
        """Test OrderSide enum has expected values."""
        from core.backtester import OrderSide

        assert OrderSide.BUY.value == "buy"
        assert OrderSide.SELL.value == "sell"

    def test_position_side_enum_values(self):
        """Test PositionSide enum has expected values."""
        from core.backtester import PositionSide

        assert PositionSide.LONG.value == "long"
        assert PositionSide.SHORT.value == "short"
        assert PositionSide.FLAT.value == "flat"


class TestOHLCVDataclass:
    """Test OHLCV candle dataclass."""

    def test_create_ohlcv(self):
        """Test creating an OHLCV candle."""
        from core.backtester import OHLCV

        candle = OHLCV(
            timestamp="2024-01-01T00:00:00Z",
            open=100.0,
            high=105.0,
            low=98.0,
            close=103.0,
            volume=1000.0
        )

        assert candle.timestamp == "2024-01-01T00:00:00Z"
        assert candle.open == 100.0
        assert candle.high == 105.0
        assert candle.low == 98.0
        assert candle.close == 103.0
        assert candle.volume == 1000.0


class TestBacktestTradeDataclass:
    """Test BacktestTrade dataclass."""

    def test_create_backtest_trade(self):
        """Test creating a backtest trade."""
        from core.backtester import BacktestTrade, OrderSide

        trade = BacktestTrade(
            id="t_1",
            timestamp="2024-01-01T00:00:00Z",
            side=OrderSide.BUY,
            price=100.0,
            quantity=10.0,
            value=1000.0,
            fee=1.0,
            pnl=50.0,
            cumulative_pnl=50.0,
            position_after=10.0,
            reason="RSI oversold"
        )

        assert trade.id == "t_1"
        assert trade.side == OrderSide.BUY
        assert trade.price == 100.0
        assert trade.quantity == 10.0
        assert trade.value == 1000.0
        assert trade.fee == 1.0
        assert trade.pnl == 50.0
        assert trade.reason == "RSI oversold"

    def test_backtest_trade_defaults(self):
        """Test backtest trade has correct defaults."""
        from core.backtester import BacktestTrade, OrderSide

        trade = BacktestTrade(
            id="t_1",
            timestamp="2024-01-01T00:00:00Z",
            side=OrderSide.BUY,
            price=100.0,
            quantity=10.0,
            value=1000.0,
            fee=1.0
        )

        assert trade.pnl == 0.0
        assert trade.cumulative_pnl == 0.0
        assert trade.position_after == 0.0
        assert trade.reason == ""


class TestBacktestPositionDataclass:
    """Test BacktestPosition dataclass."""

    def test_create_backtest_position(self):
        """Test creating a backtest position."""
        from core.backtester import BacktestPosition, PositionSide

        position = BacktestPosition(
            side=PositionSide.LONG,
            quantity=10.0,
            entry_price=100.0,
            entry_time="2024-01-01T00:00:00Z",
            unrealized_pnl=50.0,
            current_price=105.0
        )

        assert position.side == PositionSide.LONG
        assert position.quantity == 10.0
        assert position.entry_price == 100.0
        assert position.unrealized_pnl == 50.0

    def test_backtest_position_defaults(self):
        """Test backtest position defaults."""
        from core.backtester import BacktestPosition, PositionSide

        position = BacktestPosition(
            side=PositionSide.FLAT,
            quantity=0,
            entry_price=0,
            entry_time=""
        )

        assert position.unrealized_pnl == 0.0
        assert position.current_price == 0.0


class TestBacktestConfigDataclass:
    """Test BacktestConfig dataclass."""

    def test_create_backtest_config(self):
        """Test creating a backtest configuration."""
        from core.backtester import BacktestConfig

        config = BacktestConfig(
            symbol="SOL",
            start_date="2024-01-01",
            end_date="2024-12-31",
            initial_capital=10000.0,
            fee_rate=0.001,
            slippage_bps=5,
            max_position_size=0.5,
            allow_short=True,
            use_leverage=False,
            max_leverage=1.0
        )

        assert config.symbol == "SOL"
        assert config.initial_capital == 10000.0
        assert config.fee_rate == 0.001
        assert config.slippage_bps == 5
        assert config.max_position_size == 0.5
        assert config.allow_short is True

    def test_backtest_config_defaults(self):
        """Test backtest config default values."""
        from core.backtester import BacktestConfig

        config = BacktestConfig(
            symbol="SOL",
            start_date="2024-01-01",
            end_date="2024-12-31",
            initial_capital=10000.0
        )

        assert config.fee_rate == 0.001
        assert config.slippage_bps == 5
        assert config.max_position_size == 1.0
        assert config.allow_short is False
        assert config.use_leverage is False
        assert config.max_leverage == 1.0


class TestBacktestMetricsDataclass:
    """Test BacktestMetrics dataclass."""

    def test_create_backtest_metrics(self):
        """Test creating backtest metrics."""
        from core.backtester import BacktestMetrics

        metrics = BacktestMetrics(
            total_return=1000.0,
            total_return_pct=10.0,
            annualized_return=12.0,
            sharpe_ratio=1.5,
            sortino_ratio=2.0,
            max_drawdown=5.0,
            max_drawdown_duration=10,
            win_rate=60.0,
            profit_factor=2.0,
            total_trades=100,
            winning_trades=60,
            losing_trades=40,
            avg_win=50.0,
            avg_loss=-25.0,
            largest_win=200.0,
            largest_loss=-100.0,
            avg_trade_duration=5.0,
            expectancy=15.0,
            calmar_ratio=2.4,
            volatility=8.0
        )

        assert metrics.total_return == 1000.0
        assert metrics.sharpe_ratio == 1.5
        assert metrics.max_drawdown == 5.0
        assert metrics.win_rate == 60.0
        assert metrics.profit_factor == 2.0


# =============================================================================
# HISTORICAL DATA LOADING TESTS
# =============================================================================

class TestHistoricalDataLoading:
    """Test historical data loading functionality."""

    @pytest.fixture
    def engine(self, tmp_path):
        """Create a BacktestEngine instance with temp database."""
        from core.backtester import BacktestEngine
        return BacktestEngine(db_path=tmp_path / "test_backtests.db")

    @pytest.fixture
    def sample_candles(self):
        """Create sample OHLCV candles."""
        from core.backtester import OHLCV

        candles = []
        for i in range(100):
            candles.append(OHLCV(
                timestamp=f"2024-01-{(i % 30) + 1:02d}T00:00:00Z",
                open=100.0 + i * 0.1,
                high=105.0 + i * 0.1,
                low=98.0 + i * 0.1,
                close=103.0 + i * 0.1,
                volume=1000.0 + i * 10
            ))
        return candles

    def test_load_data_from_ohlcv_objects(self, engine, sample_candles):
        """Test loading data from OHLCV objects."""
        engine.load_data("SOL", sample_candles)

        assert "SOL" in engine._data
        assert len(engine._data["SOL"]) == 100

    def test_load_data_uppercase_symbol(self, engine, sample_candles):
        """Test that symbol is uppercased."""
        engine.load_data("sol", sample_candles)

        assert "SOL" in engine._data
        assert "sol" not in engine._data

    def test_load_data_from_dict(self, engine):
        """Test loading data from dictionaries."""
        data = [
            {"timestamp": "2024-01-01T00:00:00Z", "open": 100, "high": 105, "low": 98, "close": 103, "volume": 1000},
            {"timestamp": "2024-01-02T00:00:00Z", "open": 103, "high": 108, "low": 101, "close": 106, "volume": 1200},
            {"timestamp": "2024-01-03T00:00:00Z", "open": 106, "high": 110, "low": 104, "close": 108, "volume": 900},
        ]

        engine.load_data_from_dict("ETH", data)

        assert "ETH" in engine._data
        assert len(engine._data["ETH"]) == 3
        assert engine._data["ETH"][0].close == 103

    def test_load_data_from_dict_without_volume(self, engine):
        """Test loading data from dictionaries without volume field."""
        data = [
            {"timestamp": "2024-01-01T00:00:00Z", "open": 100, "high": 105, "low": 98, "close": 103},
        ]

        engine.load_data_from_dict("BTC", data)

        assert engine._data["BTC"][0].volume == 0

    def test_load_data_sorts_by_timestamp(self, engine):
        """Test that loaded data is sorted by timestamp."""
        from core.backtester import OHLCV

        candles = [
            OHLCV(timestamp="2024-01-03T00:00:00Z", open=100, high=105, low=98, close=103, volume=1000),
            OHLCV(timestamp="2024-01-01T00:00:00Z", open=98, high=102, low=96, close=100, volume=900),
            OHLCV(timestamp="2024-01-02T00:00:00Z", open=100, high=104, low=97, close=102, volume=1100),
        ]

        engine.load_data("SOL", candles)

        assert engine._data["SOL"][0].timestamp == "2024-01-01T00:00:00Z"
        assert engine._data["SOL"][1].timestamp == "2024-01-02T00:00:00Z"
        assert engine._data["SOL"][2].timestamp == "2024-01-03T00:00:00Z"

    def test_load_multiple_symbols(self, engine, sample_candles):
        """Test loading data for multiple symbols."""
        from core.backtester import OHLCV

        engine.load_data("SOL", sample_candles)
        engine.load_data("ETH", sample_candles[:50])
        engine.load_data("BTC", sample_candles[:25])

        assert len(engine._data) == 3
        assert len(engine._data["SOL"]) == 100
        assert len(engine._data["ETH"]) == 50
        assert len(engine._data["BTC"]) == 25


# =============================================================================
# STRATEGY EXECUTION TESTS
# =============================================================================

class TestStrategyExecution:
    """Test strategy execution functionality."""

    @pytest.fixture
    def engine_with_data(self, tmp_path):
        """Create an engine with pre-loaded data."""
        from core.backtester import BacktestEngine, OHLCV

        engine = BacktestEngine(db_path=tmp_path / "test_backtests.db")

        # Create 30 days of data
        candles = []
        for i in range(30):
            day = i + 1
            candles.append(OHLCV(
                timestamp=f"2024-01-{day:02d}T00:00:00Z",
                open=100.0 + i,
                high=105.0 + i,
                low=98.0 + i,
                close=103.0 + i,
                volume=1000.0
            ))

        engine.load_data("SOL", candles)
        return engine

    def test_run_backtest_basic(self, engine_with_data):
        """Test running a basic backtest."""
        from core.backtester import BacktestConfig

        config = BacktestConfig(
            symbol="SOL",
            start_date="2024-01-01",
            end_date="2024-01-30",
            initial_capital=10000.0
        )

        def simple_strategy(engine, candle):
            pass  # Do nothing

        result = engine_with_data.run(
            strategy=simple_strategy,
            config=config,
            strategy_name="simple"
        )

        assert result is not None
        assert result.config.symbol == "SOL"
        assert result.strategy_name == "simple"

    def test_run_backtest_with_buy_strategy(self, engine_with_data):
        """Test backtest with a strategy that buys."""
        from core.backtester import BacktestConfig

        config = BacktestConfig(
            symbol="SOL",
            start_date="2024-01-01",
            end_date="2024-01-30",
            initial_capital=10000.0
        )

        def buy_first_day_strategy(engine, candle):
            if engine.is_flat() and "01-01" in candle.timestamp:
                engine.buy(1.0, "First day buy")

        result = engine_with_data.run(
            strategy=buy_first_day_strategy,
            config=config,
            strategy_name="buy_first_day"
        )

        # Should have at least the buy trade and final close
        assert len(result.trades) >= 1
        assert result.trades[0].reason == "First day buy"

    def test_run_backtest_with_sell_strategy(self, engine_with_data):
        """Test backtest with buy and sell."""
        from core.backtester import BacktestConfig, OrderSide

        config = BacktestConfig(
            symbol="SOL",
            start_date="2024-01-01",
            end_date="2024-01-30",
            initial_capital=10000.0
        )

        def buy_sell_strategy(engine, candle):
            if engine.is_flat() and "01-05" in candle.timestamp:
                engine.buy(1.0, "Buy signal")
            elif engine.is_long() and "01-15" in candle.timestamp:
                engine.sell_all("Take profit")

        result = engine_with_data.run(
            strategy=buy_sell_strategy,
            config=config,
            strategy_name="buy_sell"
        )

        # Should have buy and sell trades
        assert len(result.trades) >= 2
        trade_sides = [t.side for t in result.trades]
        assert OrderSide.BUY in trade_sides
        assert OrderSide.SELL in trade_sides

    def test_run_backtest_no_data_raises_error(self, tmp_path):
        """Test that running backtest without data raises error."""
        from core.backtester import BacktestEngine, BacktestConfig

        engine = BacktestEngine(db_path=tmp_path / "test.db")
        config = BacktestConfig(
            symbol="SOL",
            start_date="2024-01-01",
            end_date="2024-01-30",
            initial_capital=10000.0
        )

        with pytest.raises(ValueError, match="No data loaded"):
            engine.run(
                strategy=lambda e, c: None,
                config=config,
                strategy_name="test"
            )

    def test_run_backtest_no_data_in_range_raises_error(self, engine_with_data):
        """Test that running backtest with no data in range raises error."""
        from core.backtester import BacktestConfig

        config = BacktestConfig(
            symbol="SOL",
            start_date="2025-01-01",  # No data in 2025
            end_date="2025-01-30",
            initial_capital=10000.0
        )

        with pytest.raises(ValueError, match="No data in specified date range"):
            engine_with_data.run(
                strategy=lambda e, c: None,
                config=config,
                strategy_name="test"
            )

    def test_strategy_error_handling(self, engine_with_data):
        """Test that strategy errors are caught and logged."""
        from core.backtester import BacktestConfig

        config = BacktestConfig(
            symbol="SOL",
            start_date="2024-01-01",
            end_date="2024-01-30",
            initial_capital=10000.0
        )

        def error_strategy(engine, candle):
            raise ValueError("Intentional error")

        # Should not raise, errors are logged
        result = engine_with_data.run(
            strategy=error_strategy,
            config=config,
            strategy_name="error_strategy"
        )

        assert result is not None

    def test_backtest_closes_position_at_end(self, engine_with_data):
        """Test that open position is closed at end of backtest."""
        from core.backtester import BacktestConfig

        config = BacktestConfig(
            symbol="SOL",
            start_date="2024-01-01",
            end_date="2024-01-30",
            initial_capital=10000.0
        )

        def hold_strategy(engine, candle):
            if engine.is_flat() and "01-01" in candle.timestamp:
                engine.buy(1.0, "Buy and hold")

        result = engine_with_data.run(
            strategy=hold_strategy,
            config=config,
            strategy_name="hold"
        )

        # Last trade should be a sell from position close
        last_trade = result.trades[-1]
        assert last_trade.reason == "End of backtest"


# =============================================================================
# PNL CALCULATION TESTS
# =============================================================================

class TestPnLCalculation:
    """Test profit and loss calculation."""

    @pytest.fixture
    def engine_with_data(self, tmp_path):
        """Create an engine with pre-loaded data."""
        from core.backtester import BacktestEngine, OHLCV

        engine = BacktestEngine(db_path=tmp_path / "test_backtests.db")

        candles = []
        prices = [100, 105, 110, 108, 115, 120, 118, 125, 130, 128]
        for i, price in enumerate(prices):
            candles.append(OHLCV(
                timestamp=f"2024-01-{i + 1:02d}T00:00:00Z",
                open=price - 2,
                high=price + 3,
                low=price - 3,
                close=price,
                volume=1000.0
            ))

        engine.load_data("SOL", candles)
        return engine

    def test_pnl_profitable_long_trade(self, engine_with_data):
        """Test PnL calculation for profitable long trade."""
        from core.backtester import BacktestConfig

        config = BacktestConfig(
            symbol="SOL",
            start_date="2024-01-01",
            end_date="2024-01-10",
            initial_capital=10000.0,
            fee_rate=0.001,
            slippage_bps=0  # No slippage for precise calculation
        )

        def trade_strategy(engine, candle):
            if "01-01" in candle.timestamp:
                engine.buy(1.0, "Entry")
            elif "01-05" in candle.timestamp:
                engine.sell_all("Exit")

        result = engine_with_data.run(
            strategy=trade_strategy,
            config=config,
            strategy_name="profitable_long"
        )

        # Find the sell trade (second one)
        sell_trade = [t for t in result.trades if "Exit" in t.reason][0]
        assert sell_trade.pnl > 0  # Should be profitable

    def test_pnl_losing_long_trade(self, tmp_path):
        """Test PnL calculation for losing long trade."""
        from core.backtester import BacktestEngine, BacktestConfig, OHLCV

        engine = BacktestEngine(db_path=tmp_path / "test.db")

        # Declining price data
        candles = []
        prices = [100, 98, 95, 92, 90]
        for i, price in enumerate(prices):
            candles.append(OHLCV(
                timestamp=f"2024-01-{i + 1:02d}T00:00:00Z",
                open=price + 1,
                high=price + 3,
                low=price - 1,
                close=price,
                volume=1000.0
            ))

        engine.load_data("SOL", candles)

        config = BacktestConfig(
            symbol="SOL",
            start_date="2024-01-01",
            end_date="2024-01-05",
            initial_capital=10000.0,
            fee_rate=0.0,
            slippage_bps=0
        )

        def trade_strategy(engine, candle):
            if "01-01" in candle.timestamp:
                engine.buy(1.0, "Entry")
            elif "01-05" in candle.timestamp:
                engine.sell_all("Stop loss")

        result = engine.run(
            strategy=trade_strategy,
            config=config,
            strategy_name="losing_long"
        )

        # Check that we have a losing trade
        assert result.metrics.total_return < 0

    def test_pnl_with_fees(self, engine_with_data):
        """Test that fees are properly deducted from PnL."""
        from core.backtester import BacktestConfig

        config = BacktestConfig(
            symbol="SOL",
            start_date="2024-01-01",
            end_date="2024-01-10",
            initial_capital=10000.0,
            fee_rate=0.01,  # 1% fee
            slippage_bps=0
        )

        def trade_strategy(engine, candle):
            if "01-01" in candle.timestamp:
                engine.buy(1.0, "Entry")
            elif "01-10" in candle.timestamp:
                engine.sell_all("Exit")

        result = engine_with_data.run(
            strategy=trade_strategy,
            config=config,
            strategy_name="with_fees"
        )

        assert result.total_fees > 0
        # Final capital should be reduced by fees
        assert result.final_capital < config.initial_capital + result.metrics.total_return + result.total_fees

    def test_pnl_with_slippage(self, engine_with_data):
        """Test that slippage affects execution prices."""
        from core.backtester import BacktestConfig

        config = BacktestConfig(
            symbol="SOL",
            start_date="2024-01-01",
            end_date="2024-01-10",
            initial_capital=10000.0,
            fee_rate=0.0,
            slippage_bps=100  # 1% slippage
        )

        def trade_strategy(engine, candle):
            if "01-01" in candle.timestamp:
                engine.buy(1.0, "Entry")
            elif "01-10" in candle.timestamp:
                engine.sell_all("Exit")

        result = engine_with_data.run(
            strategy=trade_strategy,
            config=config,
            strategy_name="with_slippage"
        )

        # Buy price should be higher than close
        buy_trade = result.trades[0]
        assert buy_trade.price > engine_with_data._data["SOL"][0].close

    def test_cumulative_pnl_tracking(self, engine_with_data):
        """Test that cumulative PnL is tracked correctly."""
        from core.backtester import BacktestConfig

        config = BacktestConfig(
            symbol="SOL",
            start_date="2024-01-01",
            end_date="2024-01-10",
            initial_capital=10000.0,
            fee_rate=0.0,
            slippage_bps=0
        )

        def multi_trade_strategy(engine, candle):
            day = int(candle.timestamp[8:10])
            if day in [1, 3, 5, 7] and engine.is_flat():
                engine.buy(0.25, "Buy")
            elif day in [2, 4, 6, 8] and engine.is_long():
                engine.sell_all("Sell")

        result = engine_with_data.run(
            strategy=multi_trade_strategy,
            config=config,
            strategy_name="multi_trade"
        )

        # Verify cumulative PnL increases with each trade
        running_total = 0
        for trade in result.trades:
            running_total += trade.pnl
            assert abs(trade.cumulative_pnl - running_total) < 0.01


# =============================================================================
# PERFORMANCE METRICS TESTS
# =============================================================================

class TestPerformanceMetrics:
    """Test performance metrics calculation."""

    @pytest.fixture
    def engine_with_varied_data(self, tmp_path):
        """Create an engine with varied price data for metrics testing."""
        from core.backtester import BacktestEngine, OHLCV

        engine = BacktestEngine(db_path=tmp_path / "test_backtests.db")

        # Create data with ups and downs for realistic metrics
        candles = []
        prices = [100, 102, 98, 105, 103, 110, 108, 115, 112, 120,
                  118, 115, 120, 125, 122, 130, 128, 135, 132, 140]

        for i, price in enumerate(prices):
            candles.append(OHLCV(
                timestamp=f"2024-01-{i + 1:02d}T00:00:00Z",
                open=price - 1,
                high=price + 2,
                low=price - 2,
                close=price,
                volume=1000.0 + i * 50
            ))

        engine.load_data("SOL", candles)
        return engine

    def test_total_return_calculation(self, engine_with_varied_data):
        """Test total return calculation."""
        from core.backtester import BacktestConfig

        config = BacktestConfig(
            symbol="SOL",
            start_date="2024-01-01",
            end_date="2024-01-20",
            initial_capital=10000.0,
            fee_rate=0.0,
            slippage_bps=0
        )

        def hold_strategy(engine, candle):
            if engine.is_flat() and "01-01" in candle.timestamp:
                engine.buy(1.0, "Buy")

        result = engine_with_varied_data.run(
            strategy=hold_strategy,
            config=config,
            strategy_name="hold"
        )

        # Total return should be positive (price went from 100 to 140)
        assert result.metrics.total_return > 0
        assert result.metrics.total_return_pct > 0

    def test_win_rate_calculation(self, engine_with_varied_data):
        """Test win rate calculation."""
        from core.backtester import BacktestConfig

        config = BacktestConfig(
            symbol="SOL",
            start_date="2024-01-01",
            end_date="2024-01-20",
            initial_capital=10000.0,
            fee_rate=0.0,
            slippage_bps=0
        )

        def multi_trade_strategy(engine, candle):
            day = int(candle.timestamp[8:10])
            if day in [1, 5, 10, 15] and engine.is_flat():
                engine.buy(0.25, "Buy")
            elif day in [3, 8, 12, 18] and engine.is_long():
                engine.sell_all("Sell")

        result = engine_with_varied_data.run(
            strategy=multi_trade_strategy,
            config=config,
            strategy_name="multi_trade"
        )

        # Win rate should be between 0 and 100
        assert 0 <= result.metrics.win_rate <= 100

    def test_profit_factor_calculation(self, engine_with_varied_data):
        """Test profit factor calculation."""
        from core.backtester import BacktestConfig

        config = BacktestConfig(
            symbol="SOL",
            start_date="2024-01-01",
            end_date="2024-01-20",
            initial_capital=10000.0,
            fee_rate=0.0,
            slippage_bps=0
        )

        def multi_trade_strategy(engine, candle):
            day = int(candle.timestamp[8:10])
            if day in [1, 5, 10, 15] and engine.is_flat():
                engine.buy(0.25, "Buy")
            elif day in [3, 8, 12, 18] and engine.is_long():
                engine.sell_all("Sell")

        result = engine_with_varied_data.run(
            strategy=multi_trade_strategy,
            config=config,
            strategy_name="multi_trade"
        )

        # Profit factor should be >= 0
        assert result.metrics.profit_factor >= 0

    def test_max_drawdown_calculation(self, tmp_path):
        """Test max drawdown calculation."""
        from core.backtester import BacktestEngine, BacktestConfig, OHLCV

        engine = BacktestEngine(db_path=tmp_path / "test.db")

        # Create data with a significant drawdown
        candles = []
        prices = [100, 110, 120, 115, 100, 90, 95, 105, 115, 120]

        for i, price in enumerate(prices):
            candles.append(OHLCV(
                timestamp=f"2024-01-{i + 1:02d}T00:00:00Z",
                open=price,
                high=price + 2,
                low=price - 2,
                close=price,
                volume=1000.0
            ))

        engine.load_data("SOL", candles)

        config = BacktestConfig(
            symbol="SOL",
            start_date="2024-01-01",
            end_date="2024-01-10",
            initial_capital=10000.0,
            fee_rate=0.0,
            slippage_bps=0
        )

        def hold_strategy(engine, candle):
            if engine.is_flat() and "01-01" in candle.timestamp:
                engine.buy(1.0, "Buy")

        result = engine.run(
            strategy=hold_strategy,
            config=config,
            strategy_name="hold"
        )

        # Max drawdown should be positive (represents percentage drop from peak)
        assert result.metrics.max_drawdown > 0

    def test_sharpe_ratio_calculation(self, engine_with_varied_data):
        """Test Sharpe ratio calculation."""
        from core.backtester import BacktestConfig

        config = BacktestConfig(
            symbol="SOL",
            start_date="2024-01-01",
            end_date="2024-01-20",
            initial_capital=10000.0,
            fee_rate=0.0,
            slippage_bps=0
        )

        def hold_strategy(engine, candle):
            if engine.is_flat() and "01-01" in candle.timestamp:
                engine.buy(1.0, "Buy")

        result = engine_with_varied_data.run(
            strategy=hold_strategy,
            config=config,
            strategy_name="hold"
        )

        # Sharpe ratio should be a real number (could be positive or negative)
        assert not math.isnan(result.metrics.sharpe_ratio)
        assert not math.isinf(result.metrics.sharpe_ratio)

    def test_sortino_ratio_calculation(self, engine_with_varied_data):
        """Test Sortino ratio calculation."""
        from core.backtester import BacktestConfig

        config = BacktestConfig(
            symbol="SOL",
            start_date="2024-01-01",
            end_date="2024-01-20",
            initial_capital=10000.0,
            fee_rate=0.0,
            slippage_bps=0
        )

        def hold_strategy(engine, candle):
            if engine.is_flat() and "01-01" in candle.timestamp:
                engine.buy(1.0, "Buy")

        result = engine_with_varied_data.run(
            strategy=hold_strategy,
            config=config,
            strategy_name="hold"
        )

        # Sortino ratio should be a real number
        assert not math.isnan(result.metrics.sortino_ratio)
        assert not math.isinf(result.metrics.sortino_ratio)

    def test_calmar_ratio_calculation(self, engine_with_varied_data):
        """Test Calmar ratio calculation."""
        from core.backtester import BacktestConfig

        config = BacktestConfig(
            symbol="SOL",
            start_date="2024-01-01",
            end_date="2024-01-20",
            initial_capital=10000.0,
            fee_rate=0.0,
            slippage_bps=0
        )

        def hold_strategy(engine, candle):
            if engine.is_flat() and "01-01" in candle.timestamp:
                engine.buy(1.0, "Buy")

        result = engine_with_varied_data.run(
            strategy=hold_strategy,
            config=config,
            strategy_name="hold"
        )

        # Calmar ratio should be a real number
        assert not math.isnan(result.metrics.calmar_ratio)
        assert not math.isinf(result.metrics.calmar_ratio)

    def test_empty_equity_curve_metrics(self, tmp_path):
        """Test metrics calculation with empty equity curve."""
        from core.backtester import BacktestEngine

        engine = BacktestEngine(db_path=tmp_path / "test.db")
        engine._equity_curve = []
        engine._trades = []
        engine._config = type('obj', (object,), {'initial_capital': 10000})()
        engine._capital = 10000

        metrics = engine._calculate_metrics()

        assert metrics.total_return == 0
        assert metrics.total_trades == 0
        assert metrics.win_rate == 0


# =============================================================================
# TRADE SIMULATION TESTS
# =============================================================================

class TestTradeSimulation:
    """Test trade simulation functionality."""

    @pytest.fixture
    def engine_with_data(self, tmp_path):
        """Create an engine with pre-loaded data."""
        from core.backtester import BacktestEngine, OHLCV

        engine = BacktestEngine(db_path=tmp_path / "test_backtests.db")

        candles = []
        for i in range(20):
            candles.append(OHLCV(
                timestamp=f"2024-01-{i + 1:02d}T00:00:00Z",
                open=100.0 + i,
                high=105.0 + i,
                low=98.0 + i,
                close=103.0 + i,
                volume=1000.0
            ))

        engine.load_data("SOL", candles)
        return engine

    def test_buy_creates_long_position(self, engine_with_data):
        """Test that buy creates a long position."""
        from core.backtester import BacktestConfig, PositionSide

        config = BacktestConfig(
            symbol="SOL",
            start_date="2024-01-01",
            end_date="2024-01-20",
            initial_capital=10000.0
        )

        position_side = None

        def check_position_strategy(engine, candle):
            nonlocal position_side
            if engine.is_flat() and "01-01" in candle.timestamp:
                engine.buy(1.0, "Buy")
            elif "01-02" in candle.timestamp:
                position_side = engine.position.side

        engine_with_data.run(
            strategy=check_position_strategy,
            config=config,
            strategy_name="check_position"
        )

        assert position_side == PositionSide.LONG

    def test_sell_all_closes_position(self, engine_with_data):
        """Test that sell_all closes the position."""
        from core.backtester import BacktestConfig, PositionSide

        config = BacktestConfig(
            symbol="SOL",
            start_date="2024-01-01",
            end_date="2024-01-20",
            initial_capital=10000.0
        )

        position_side_after_sell = None

        def close_position_strategy(engine, candle):
            nonlocal position_side_after_sell
            if engine.is_flat() and "01-01" in candle.timestamp:
                engine.buy(1.0, "Buy")
            elif "01-05" in candle.timestamp and engine.is_long():
                engine.sell_all("Close")
            elif "01-06" in candle.timestamp:
                position_side_after_sell = engine.position.side

        engine_with_data.run(
            strategy=close_position_strategy,
            config=config,
            strategy_name="close_position"
        )

        assert position_side_after_sell == PositionSide.FLAT

    def test_position_size_respects_max(self, engine_with_data):
        """Test that position size respects max_position_size."""
        from core.backtester import BacktestConfig

        config = BacktestConfig(
            symbol="SOL",
            start_date="2024-01-01",
            end_date="2024-01-20",
            initial_capital=10000.0,
            max_position_size=0.5  # 50% max
        )

        def buy_full_strategy(engine, candle):
            if engine.is_flat() and "01-01" in candle.timestamp:
                engine.buy(1.0, "Buy full")  # Requests 100%

        result = engine_with_data.run(
            strategy=buy_full_strategy,
            config=config,
            strategy_name="buy_full"
        )

        # First trade value should be at most 50% of capital
        first_trade = result.trades[0]
        assert first_trade.value <= config.initial_capital * config.max_position_size * 1.01  # Allow small tolerance

    def test_short_position_when_allowed(self, tmp_path):
        """Test creating a short position when allowed."""
        from core.backtester import BacktestEngine, BacktestConfig, OHLCV, PositionSide

        engine = BacktestEngine(db_path=tmp_path / "test.db")

        candles = []
        for i in range(10):
            candles.append(OHLCV(
                timestamp=f"2024-01-{i + 1:02d}T00:00:00Z",
                open=100.0 - i,
                high=102.0 - i,
                low=98.0 - i,
                close=99.0 - i,
                volume=1000.0
            ))

        engine.load_data("SOL", candles)

        config = BacktestConfig(
            symbol="SOL",
            start_date="2024-01-01",
            end_date="2024-01-10",
            initial_capital=10000.0,
            allow_short=True
        )

        position_side = None

        def short_strategy(engine, candle):
            nonlocal position_side
            if engine.is_flat() and "01-01" in candle.timestamp:
                engine.sell(1.0, "Short")
            elif "01-02" in candle.timestamp:
                position_side = engine.position.side

        engine.run(
            strategy=short_strategy,
            config=config,
            strategy_name="short"
        )

        assert position_side == PositionSide.SHORT

    def test_no_double_buy(self, engine_with_data):
        """Test that buying when already long does nothing."""
        from core.backtester import BacktestConfig

        config = BacktestConfig(
            symbol="SOL",
            start_date="2024-01-01",
            end_date="2024-01-20",
            initial_capital=10000.0
        )

        buy_count = 0

        def double_buy_strategy(engine, candle):
            nonlocal buy_count
            if "01-01" in candle.timestamp:
                engine.buy(1.0, "First buy")
                buy_count += 1
            elif "01-02" in candle.timestamp:
                engine.buy(1.0, "Second buy")  # Should be ignored
                if engine.is_long():
                    buy_count += 1

        result = engine_with_data.run(
            strategy=double_buy_strategy,
            config=config,
            strategy_name="double_buy"
        )

        # Should only have buy + end close, not two buys
        buy_trades = [t for t in result.trades if "buy" in t.reason.lower()]
        assert len(buy_trades) == 1

    def test_close_position_does_nothing_when_flat(self, engine_with_data):
        """Test that close_position when flat does nothing."""
        from core.backtester import BacktestConfig

        config = BacktestConfig(
            symbol="SOL",
            start_date="2024-01-01",
            end_date="2024-01-20",
            initial_capital=10000.0
        )

        def close_when_flat_strategy(engine, candle):
            if "01-01" in candle.timestamp:
                engine.close_position("Close nothing")

        result = engine_with_data.run(
            strategy=close_when_flat_strategy,
            config=config,
            strategy_name="close_when_flat"
        )

        assert len(result.trades) == 0


# =============================================================================
# INDICATOR TESTS
# =============================================================================

class TestIndicators:
    """Test technical indicator calculations."""

    @pytest.fixture
    def engine_with_indicator_data(self, tmp_path):
        """Create an engine with data for indicator testing."""
        from core.backtester import BacktestEngine, BacktestConfig, OHLCV

        engine = BacktestEngine(db_path=tmp_path / "test_backtests.db")

        # Create predictable data for indicator testing
        # Use sequential timestamps to avoid sorting issues
        candles = []
        for i in range(50):
            base_price = 100 + i
            # Format: 2024-01-01T00:00:00Z, 2024-01-01T01:00:00Z, etc.
            day = (i // 24) + 1
            hour = i % 24
            candles.append(OHLCV(
                timestamp=f"2024-01-{day:02d}T{hour:02d}:00:00Z",
                open=base_price - 1,
                high=base_price + 3,
                low=base_price - 2,
                close=base_price,
                volume=1000.0 + i * 10
            ))

        engine.load_data("SOL", candles)

        # Initialize for indicator access
        engine._config = BacktestConfig(
            symbol="SOL",
            start_date="2024-01-01",
            end_date="2024-01-30",
            initial_capital=10000.0
        )
        engine._current_idx = 30  # Enough history for indicators
        engine._current_candle = candles[30]

        return engine

    def test_close_accessor(self, engine_with_indicator_data):
        """Test close price accessor."""
        close = engine_with_indicator_data.close()
        # Index 30 has base_price = 100 + 30 = 130
        assert close == 130

    def test_close_lookback(self, engine_with_indicator_data):
        """Test close price with lookback."""
        close_5_bars_ago = engine_with_indicator_data.close(5)
        # Index 30 - 5 = 25, which has base_price = 100 + 25 = 125
        assert close_5_bars_ago == 125

    def test_high_accessor(self, engine_with_indicator_data):
        """Test high price accessor."""
        high = engine_with_indicator_data.high()
        # Index 30 has base_price = 130, high = 133
        assert high == 133

    def test_low_accessor(self, engine_with_indicator_data):
        """Test low price accessor."""
        low = engine_with_indicator_data.low()
        # Index 30 has base_price = 130, low = 128
        assert low == 128

    def test_volume_accessor(self, engine_with_indicator_data):
        """Test volume accessor."""
        volume = engine_with_indicator_data.volume()
        # Index 30: volume = 1000 + 30 * 10 = 1300
        assert volume == 1300

    def test_sma_calculation(self, engine_with_indicator_data):
        """Test simple moving average calculation."""
        sma = engine_with_indicator_data.sma(20)

        # SMA of last 20 closes starting from index 30
        # Lookback 0 to 19 means indices 30, 29, 28, ..., 11
        # Closes: 130, 129, ..., 111
        # Average of 111 to 130 = (111 + 130) * 20 / 2 / 20 = 120.5
        expected = sum(100 + i for i in range(11, 31)) / 20  # 120.5
        assert abs(sma - expected) < 0.01

    def test_ema_calculation(self, engine_with_indicator_data):
        """Test exponential moving average calculation."""
        ema = engine_with_indicator_data.ema(20)

        # EMA should be close to SMA for trending data
        sma = engine_with_indicator_data.sma(20)
        assert abs(ema - sma) < 10  # Should be in same ballpark

    def test_rsi_calculation(self, engine_with_indicator_data):
        """Test RSI calculation."""
        rsi = engine_with_indicator_data.rsi(14)

        # RSI should be between 0 and 100
        assert 0 <= rsi <= 100

        # With steady uptrend, RSI should be high
        assert rsi > 50

    def test_rsi_no_losses_returns_100(self, tmp_path):
        """Test RSI returns 100 when there are no losses."""
        from core.backtester import BacktestEngine, BacktestConfig, OHLCV

        engine = BacktestEngine(db_path=tmp_path / "test.db")

        # Strictly increasing prices
        candles = []
        for i in range(20):
            candles.append(OHLCV(
                timestamp=f"2024-01-{i + 1:02d}T00:00:00Z",
                open=100.0 + i,
                high=101.0 + i,
                low=99.0 + i,
                close=100.5 + i,
                volume=1000.0
            ))

        engine.load_data("SOL", candles)
        engine._config = BacktestConfig(symbol="SOL", start_date="2024-01-01", end_date="2024-01-20", initial_capital=10000.0)
        engine._current_idx = 19
        engine._current_candle = candles[19]

        rsi = engine.rsi(14)
        assert rsi == 100

    def test_macd_calculation(self, engine_with_indicator_data):
        """Test MACD calculation."""
        macd = engine_with_indicator_data.macd()

        assert "macd" in macd
        assert "signal" in macd
        assert "histogram" in macd

        # Histogram should equal macd - signal
        assert abs(macd["histogram"] - (macd["macd"] - macd["signal"])) < 0.01

    def test_bollinger_bands_calculation(self, engine_with_indicator_data):
        """Test Bollinger Bands calculation."""
        bb = engine_with_indicator_data.bollinger_bands(20, 2)

        assert "upper" in bb
        assert "middle" in bb
        assert "lower" in bb

        # Upper > middle > lower
        assert bb["upper"] > bb["middle"]
        assert bb["middle"] > bb["lower"]

    def test_bollinger_bands_empty_data(self, tmp_path):
        """Test Bollinger Bands with no data returns zeros."""
        from core.backtester import BacktestEngine, BacktestConfig

        engine = BacktestEngine(db_path=tmp_path / "test.db")
        engine._data = {}
        engine._config = BacktestConfig(symbol="SOL", start_date="2024-01-01", end_date="2024-01-20", initial_capital=10000.0)
        engine._current_idx = 0

        bb = engine.bollinger_bands(20, 2)

        assert bb["upper"] == 0
        assert bb["middle"] == 0
        assert bb["lower"] == 0

    def test_atr_calculation(self, engine_with_indicator_data):
        """Test Average True Range calculation."""
        atr = engine_with_indicator_data.atr(14)

        # ATR should be positive
        assert atr > 0

    def test_atr_insufficient_data(self, tmp_path):
        """Test ATR returns 0 with insufficient data."""
        from core.backtester import BacktestEngine, BacktestConfig, OHLCV

        engine = BacktestEngine(db_path=tmp_path / "test.db")

        candles = [
            OHLCV(timestamp="2024-01-01T00:00:00Z", open=100, high=102, low=98, close=101, volume=1000)
        ]

        engine.load_data("SOL", candles)
        engine._config = BacktestConfig(symbol="SOL", start_date="2024-01-01", end_date="2024-01-01", initial_capital=10000.0)
        engine._current_idx = 0
        engine._current_candle = candles[0]

        atr = engine.atr(14)
        assert atr == 0


# =============================================================================
# STATE ACCESSOR TESTS
# =============================================================================

class TestStateAccessors:
    """Test state accessor methods."""

    @pytest.fixture
    def engine_with_position(self, tmp_path):
        """Create an engine with a position."""
        from core.backtester import BacktestEngine, BacktestPosition, BacktestConfig, PositionSide

        engine = BacktestEngine(db_path=tmp_path / "test.db")
        engine._config = BacktestConfig(symbol="SOL", start_date="2024-01-01", end_date="2024-01-20", initial_capital=10000.0)
        engine._capital = 5000.0
        engine._position = BacktestPosition(
            side=PositionSide.LONG,
            quantity=50.0,
            entry_price=100.0,
            entry_time="2024-01-01T00:00:00Z",
            unrealized_pnl=500.0,
            current_price=110.0
        )

        return engine

    def test_capital_accessor(self, engine_with_position):
        """Test capital accessor."""
        assert engine_with_position.capital == 5000.0

    def test_equity_accessor(self, engine_with_position):
        """Test equity accessor includes unrealized PnL."""
        equity = engine_with_position.equity
        assert equity == 5500.0  # capital + unrealized PnL

    def test_position_accessor(self, engine_with_position):
        """Test position accessor."""
        position = engine_with_position.position
        assert position.quantity == 50.0
        assert position.entry_price == 100.0

    def test_is_long(self, engine_with_position):
        """Test is_long returns True when long."""
        assert engine_with_position.is_long() is True

    def test_is_short_when_long(self, engine_with_position):
        """Test is_short returns False when long."""
        assert engine_with_position.is_short() is False

    def test_is_flat_when_long(self, engine_with_position):
        """Test is_flat returns False when long."""
        assert engine_with_position.is_flat() is False

    def test_is_flat_when_flat(self, tmp_path):
        """Test is_flat returns True when no position."""
        from core.backtester import BacktestEngine, BacktestPosition, BacktestConfig, PositionSide

        engine = BacktestEngine(db_path=tmp_path / "test.db")
        engine._config = BacktestConfig(symbol="SOL", start_date="2024-01-01", end_date="2024-01-20", initial_capital=10000.0)
        engine._position = BacktestPosition(
            side=PositionSide.FLAT,
            quantity=0,
            entry_price=0,
            entry_time=""
        )

        assert engine.is_flat() is True
        assert engine.is_long() is False
        assert engine.is_short() is False


# =============================================================================
# DATABASE TESTS
# =============================================================================

class TestBacktestDatabase:
    """Test database operations."""

    @pytest.fixture
    def db(self, tmp_path):
        """Create a BacktestDB instance."""
        from core.backtester import BacktestDB
        return BacktestDB(tmp_path / "test_backtest.db")

    def test_db_initialization(self, tmp_path):
        """Test database initializes correctly."""
        from core.backtester import BacktestDB

        db_path = tmp_path / "test.db"
        db = BacktestDB(db_path)

        assert db_path.exists()

        # Check tables exist
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='backtest_results'")
        assert cursor.fetchone() is not None

        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='backtest_trades'")
        assert cursor.fetchone() is not None

        conn.close()

    def test_db_creates_directory(self, tmp_path):
        """Test database creates parent directory if needed."""
        from core.backtester import BacktestDB

        db_path = tmp_path / "subdir" / "deep" / "test.db"
        db = BacktestDB(db_path)

        assert db_path.exists()

    def test_save_and_retrieve_result(self, tmp_path):
        """Test saving and retrieving a backtest result."""
        from core.backtester import BacktestEngine, BacktestConfig, OHLCV

        engine = BacktestEngine(db_path=tmp_path / "test.db")

        candles = []
        for i in range(10):
            candles.append(OHLCV(
                timestamp=f"2024-01-{i + 1:02d}T00:00:00Z",
                open=100.0 + i,
                high=105.0 + i,
                low=98.0 + i,
                close=103.0 + i,
                volume=1000.0
            ))

        engine.load_data("SOL", candles)

        config = BacktestConfig(
            symbol="SOL",
            start_date="2024-01-01",
            end_date="2024-01-10",
            initial_capital=10000.0
        )

        result = engine.run(
            strategy=lambda e, c: e.buy(1.0) if e.is_flat() else None,
            config=config,
            strategy_name="test_strategy"
        )

        # Retrieve the saved result
        retrieved = engine.get_result(result.id)

        assert retrieved is not None
        assert retrieved["id"] == result.id
        assert retrieved["symbol"] == "SOL"
        assert retrieved["strategy_name"] == "test_strategy"

    def test_get_nonexistent_result(self, tmp_path):
        """Test getting a non-existent result returns None."""
        from core.backtester import BacktestEngine

        engine = BacktestEngine(db_path=tmp_path / "test.db")
        result = engine.get_result("nonexistent_id")

        assert result is None

    def test_get_results_with_filters(self, tmp_path):
        """Test getting results with filters."""
        from core.backtester import BacktestEngine, BacktestConfig, OHLCV

        engine = BacktestEngine(db_path=tmp_path / "test.db")

        candles = []
        for i in range(10):
            candles.append(OHLCV(
                timestamp=f"2024-01-{i + 1:02d}T00:00:00Z",
                open=100.0 + i,
                high=105.0 + i,
                low=98.0 + i,
                close=103.0 + i,
                volume=1000.0
            ))

        engine.load_data("SOL", candles)
        engine.load_data("ETH", candles)

        config_sol = BacktestConfig(symbol="SOL", start_date="2024-01-01", end_date="2024-01-10", initial_capital=10000.0)
        config_eth = BacktestConfig(symbol="ETH", start_date="2024-01-01", end_date="2024-01-10", initial_capital=10000.0)

        # Run backtests
        engine.run(strategy=lambda e, c: None, config=config_sol, strategy_name="momentum")
        engine.run(strategy=lambda e, c: None, config=config_sol, strategy_name="breakout")
        engine.run(strategy=lambda e, c: None, config=config_eth, strategy_name="momentum")

        # Filter by symbol
        sol_results = engine.get_results(symbol="SOL")
        assert len(sol_results) == 2

        # Filter by strategy
        momentum_results = engine.get_results(strategy="momentum")
        assert len(momentum_results) == 2

        # Filter by both
        sol_momentum = engine.get_results(symbol="SOL", strategy="momentum")
        assert len(sol_momentum) == 1

    def test_get_results_limit(self, tmp_path):
        """Test limiting results."""
        from core.backtester import BacktestEngine, BacktestConfig, OHLCV

        engine = BacktestEngine(db_path=tmp_path / "test.db")

        candles = [OHLCV(
            timestamp=f"2024-01-{i + 1:02d}T00:00:00Z",
            open=100.0 + i,
            high=105.0 + i,
            low=98.0 + i,
            close=103.0 + i,
            volume=1000.0
        ) for i in range(10)]

        engine.load_data("SOL", candles)

        config = BacktestConfig(symbol="SOL", start_date="2024-01-01", end_date="2024-01-10", initial_capital=10000.0)

        # Run multiple backtests
        for i in range(5):
            engine.run(strategy=lambda e, c: None, config=config, strategy_name=f"strategy_{i}")

        # Limit results
        results = engine.get_results(limit=3)
        assert len(results) == 3


# =============================================================================
# EQUITY AND DRAWDOWN CURVE TESTS
# =============================================================================

class TestEquityAndDrawdownCurves:
    """Test equity and drawdown curve generation."""

    @pytest.fixture
    def engine_with_data(self, tmp_path):
        """Create engine with test data."""
        from core.backtester import BacktestEngine, OHLCV

        engine = BacktestEngine(db_path=tmp_path / "test.db")

        candles = []
        prices = [100, 105, 103, 108, 106, 112, 110, 115, 113, 120]
        for i, price in enumerate(prices):
            candles.append(OHLCV(
                timestamp=f"2024-01-{i + 1:02d}T00:00:00Z",
                open=price - 1,
                high=price + 2,
                low=price - 2,
                close=price,
                volume=1000.0
            ))

        engine.load_data("SOL", candles)
        return engine

    def test_equity_curve_generated(self, engine_with_data):
        """Test that equity curve is generated."""
        from core.backtester import BacktestConfig

        config = BacktestConfig(
            symbol="SOL",
            start_date="2024-01-01",
            end_date="2024-01-10",
            initial_capital=10000.0
        )

        result = engine_with_data.run(
            strategy=lambda e, c: e.buy(1.0) if e.is_flat() else None,
            config=config,
            strategy_name="test"
        )

        assert len(result.equity_curve) > 0
        assert "timestamp" in result.equity_curve[0]
        assert "equity" in result.equity_curve[0]
        assert "price" in result.equity_curve[0]

    def test_drawdown_curve_generated(self, engine_with_data):
        """Test that drawdown curve is generated."""
        from core.backtester import BacktestConfig

        config = BacktestConfig(
            symbol="SOL",
            start_date="2024-01-01",
            end_date="2024-01-10",
            initial_capital=10000.0
        )

        result = engine_with_data.run(
            strategy=lambda e, c: e.buy(1.0) if e.is_flat() else None,
            config=config,
            strategy_name="test"
        )

        assert len(result.drawdown_curve) > 0
        assert "timestamp" in result.drawdown_curve[0]
        assert "drawdown" in result.drawdown_curve[0]

    def test_drawdown_starts_at_zero(self, engine_with_data):
        """Test that drawdown starts at zero."""
        from core.backtester import BacktestConfig

        config = BacktestConfig(
            symbol="SOL",
            start_date="2024-01-01",
            end_date="2024-01-10",
            initial_capital=10000.0
        )

        result = engine_with_data.run(
            strategy=lambda e, c: None,  # No trades
            config=config,
            strategy_name="test"
        )

        # First drawdown should be 0 (at peak)
        assert result.drawdown_curve[0]["drawdown"] == 0


# =============================================================================
# SINGLETON TESTS
# =============================================================================

class TestSingleton:
    """Test singleton pattern."""

    def test_get_backtest_engine_returns_engine(self):
        """Test that get_backtest_engine returns an engine."""
        from core.backtester import get_backtest_engine

        engine = get_backtest_engine()
        assert engine is not None

    def test_get_backtest_engine_returns_same_instance(self):
        """Test that get_backtest_engine returns the same instance."""
        from core.backtester import get_backtest_engine

        engine1 = get_backtest_engine()
        engine2 = get_backtest_engine()

        assert engine1 is engine2


# =============================================================================
# BACKTEST RESULT DATACLASS TESTS
# =============================================================================

class TestBacktestResultDataclass:
    """Test BacktestResult dataclass."""

    def test_create_backtest_result(self):
        """Test creating a BacktestResult."""
        from core.backtester import (
            BacktestResult, BacktestConfig, BacktestMetrics,
            BacktestTrade, OrderSide
        )

        config = BacktestConfig(
            symbol="SOL",
            start_date="2024-01-01",
            end_date="2024-01-31",
            initial_capital=10000.0
        )

        metrics = BacktestMetrics(
            total_return=1000.0,
            total_return_pct=10.0,
            annualized_return=120.0,
            sharpe_ratio=1.5,
            sortino_ratio=2.0,
            max_drawdown=5.0,
            max_drawdown_duration=3,
            win_rate=60.0,
            profit_factor=2.0,
            total_trades=10,
            winning_trades=6,
            losing_trades=4,
            avg_win=200.0,
            avg_loss=-100.0,
            largest_win=500.0,
            largest_loss=-200.0,
            avg_trade_duration=2.5,
            expectancy=80.0,
            calmar_ratio=24.0,
            volatility=8.0
        )

        trade = BacktestTrade(
            id="t_1",
            timestamp="2024-01-01T00:00:00Z",
            side=OrderSide.BUY,
            price=100.0,
            quantity=10.0,
            value=1000.0,
            fee=1.0
        )

        result = BacktestResult(
            id="bt_123",
            config=config,
            metrics=metrics,
            trades=[trade],
            equity_curve=[{"timestamp": "2024-01-01", "equity": 10000}],
            drawdown_curve=[{"timestamp": "2024-01-01", "drawdown": 0}],
            final_capital=11000.0,
            total_fees=10.0,
            start_time="2024-01-01T00:00:00Z",
            end_time="2024-01-01T00:01:00Z",
            duration_seconds=60.0,
            strategy_name="test_strategy",
            parameters={"param1": "value1"}
        )

        assert result.id == "bt_123"
        assert result.config.symbol == "SOL"
        assert result.metrics.total_return == 1000.0
        assert len(result.trades) == 1
        assert result.final_capital == 11000.0
        assert result.strategy_name == "test_strategy"
        assert result.parameters["param1"] == "value1"
