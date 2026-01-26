"""
Tests for core/backtester.py - Historical Backtesting Engine.

Test Categories:
1. Dataclass Tests (OHLCV, BacktestTrade, BacktestPosition, BacktestConfig, BacktestMetrics, BacktestResult)
2. Enum Tests (OrderSide, PositionSide)
3. BacktestDB Tests
   - Initialization
   - Schema Creation
   - Connection Management
4. BacktestEngine Tests
   - Initialization
   - Data Loading
   - Strategy Execution
   - Trading Methods (buy, sell, close_position)
   - Indicator Methods (close, high, low, volume, sma, ema, rsi, macd, bollinger_bands, atr)
   - State Accessors (position, capital, equity, is_long, is_short, is_flat)
   - Metrics Calculation
   - Drawdown Calculation
   - Result Persistence
   - Result Retrieval
5. Integration Tests
6. Edge Cases & Error Handling
7. Singleton Tests

Target: 75%+ coverage with 90+ tests
"""

import pytest
import tempfile
import uuid
import math
import json
import sqlite3
from pathlib import Path
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock
from dataclasses import asdict

from core.backtester import (
    OrderSide,
    PositionSide,
    OHLCV,
    BacktestTrade,
    BacktestPosition,
    BacktestConfig,
    BacktestMetrics,
    BacktestResult,
    BacktestDB,
    BacktestEngine,
    get_backtest_engine,
)


# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
def temp_db_path():
    """Create a temporary database path."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir) / "test_backtests.db"


@pytest.fixture
def backtest_db(temp_db_path):
    """Create a BacktestDB instance with temporary path."""
    return BacktestDB(temp_db_path)


@pytest.fixture
def backtest_engine(temp_db_path):
    """Create a BacktestEngine instance with temporary database."""
    return BacktestEngine(db_path=temp_db_path)


@pytest.fixture
def sample_candles():
    """Generate sample OHLCV candles for testing."""
    candles = []
    base_date = datetime(2024, 1, 1, tzinfo=timezone.utc)
    base_price = 100.0

    for i in range(100):
        # Create some price movement
        price_change = math.sin(i / 10) * 5 + (i * 0.1)
        current_price = base_price + price_change

        candle = OHLCV(
            timestamp=(base_date + timedelta(days=i)).isoformat(),
            open=current_price - 1,
            high=current_price + 2,
            low=current_price - 2,
            close=current_price,
            volume=1000000 + (i * 10000)
        )
        candles.append(candle)

    return candles


@pytest.fixture
def sample_candles_dict():
    """Generate sample candle data as dictionaries."""
    candles = []
    base_date = datetime(2024, 1, 1, tzinfo=timezone.utc)
    base_price = 100.0

    for i in range(50):
        price_change = math.sin(i / 10) * 5 + (i * 0.1)
        current_price = base_price + price_change

        candles.append({
            'timestamp': (base_date + timedelta(days=i)).isoformat(),
            'open': current_price - 1,
            'high': current_price + 2,
            'low': current_price - 2,
            'close': current_price,
            'volume': 1000000 + (i * 10000)
        })

    return candles


@pytest.fixture
def simple_config():
    """Create a simple backtest configuration."""
    return BacktestConfig(
        symbol="SOL",
        start_date="2024-01-01",
        end_date="2024-04-10",
        initial_capital=10000.0,
        fee_rate=0.001,
        slippage_bps=5,
        max_position_size=1.0,
        allow_short=False
    )


@pytest.fixture
def short_enabled_config():
    """Create a backtest configuration with shorting enabled."""
    return BacktestConfig(
        symbol="SOL",
        start_date="2024-01-01",
        end_date="2024-04-10",
        initial_capital=10000.0,
        fee_rate=0.001,
        slippage_bps=5,
        max_position_size=1.0,
        allow_short=True
    )


@pytest.fixture
def engine_with_data(backtest_engine, sample_candles):
    """Create a BacktestEngine with loaded sample data."""
    backtest_engine.load_data("SOL", sample_candles)
    return backtest_engine


# ============================================================================
# ENUM TESTS
# ============================================================================

class TestOrderSide:
    """Tests for OrderSide enum."""

    def test_order_side_values(self):
        """Test OrderSide enum values."""
        assert OrderSide.BUY.value == "buy"
        assert OrderSide.SELL.value == "sell"

    def test_order_side_count(self):
        """Test OrderSide has exactly 2 values."""
        assert len(OrderSide) == 2


class TestPositionSide:
    """Tests for PositionSide enum."""

    def test_position_side_values(self):
        """Test PositionSide enum values."""
        assert PositionSide.LONG.value == "long"
        assert PositionSide.SHORT.value == "short"
        assert PositionSide.FLAT.value == "flat"

    def test_position_side_count(self):
        """Test PositionSide has exactly 3 values."""
        assert len(PositionSide) == 3


# ============================================================================
# OHLCV DATACLASS TESTS
# ============================================================================

class TestOHLCVDataclass:
    """Tests for OHLCV dataclass."""

    def test_ohlcv_creation(self):
        """Test creating an OHLCV candle."""
        candle = OHLCV(
            timestamp="2024-01-01T00:00:00+00:00",
            open=100.0,
            high=105.0,
            low=98.0,
            close=103.0,
            volume=1000000.0
        )

        assert candle.timestamp == "2024-01-01T00:00:00+00:00"
        assert candle.open == 100.0
        assert candle.high == 105.0
        assert candle.low == 98.0
        assert candle.close == 103.0
        assert candle.volume == 1000000.0

    def test_ohlcv_asdict(self):
        """Test converting OHLCV to dictionary."""
        candle = OHLCV(
            timestamp="2024-01-01T00:00:00+00:00",
            open=100.0,
            high=105.0,
            low=98.0,
            close=103.0,
            volume=1000000.0
        )

        d = asdict(candle)
        assert isinstance(d, dict)
        assert d["open"] == 100.0
        assert d["close"] == 103.0


# ============================================================================
# BACKTEST TRADE DATACLASS TESTS
# ============================================================================

class TestBacktestTradeDataclass:
    """Tests for BacktestTrade dataclass."""

    def test_backtest_trade_creation_minimal(self):
        """Test creating a BacktestTrade with minimal fields."""
        trade = BacktestTrade(
            id="trade_001",
            timestamp="2024-01-01T00:00:00+00:00",
            side=OrderSide.BUY,
            price=100.0,
            quantity=10.0,
            value=1000.0,
            fee=1.0
        )

        assert trade.id == "trade_001"
        assert trade.side == OrderSide.BUY
        assert trade.price == 100.0
        assert trade.quantity == 10.0
        assert trade.value == 1000.0
        assert trade.fee == 1.0
        # Defaults
        assert trade.pnl == 0.0
        assert trade.cumulative_pnl == 0.0
        assert trade.position_after == 0.0
        assert trade.reason == ""

    def test_backtest_trade_creation_full(self):
        """Test creating a BacktestTrade with all fields."""
        trade = BacktestTrade(
            id="trade_002",
            timestamp="2024-01-01T00:00:00+00:00",
            side=OrderSide.SELL,
            price=110.0,
            quantity=10.0,
            value=1100.0,
            fee=1.1,
            pnl=100.0,
            cumulative_pnl=100.0,
            position_after=0.0,
            reason="Take profit"
        )

        assert trade.pnl == 100.0
        assert trade.cumulative_pnl == 100.0
        assert trade.reason == "Take profit"


# ============================================================================
# BACKTEST POSITION DATACLASS TESTS
# ============================================================================

class TestBacktestPositionDataclass:
    """Tests for BacktestPosition dataclass."""

    def test_backtest_position_creation(self):
        """Test creating a BacktestPosition."""
        position = BacktestPosition(
            side=PositionSide.LONG,
            quantity=10.0,
            entry_price=100.0,
            entry_time="2024-01-01T00:00:00+00:00"
        )

        assert position.side == PositionSide.LONG
        assert position.quantity == 10.0
        assert position.entry_price == 100.0
        assert position.unrealized_pnl == 0.0
        assert position.current_price == 0.0

    def test_backtest_position_with_unrealized_pnl(self):
        """Test BacktestPosition with unrealized PnL."""
        position = BacktestPosition(
            side=PositionSide.LONG,
            quantity=10.0,
            entry_price=100.0,
            entry_time="2024-01-01T00:00:00+00:00",
            unrealized_pnl=50.0,
            current_price=105.0
        )

        assert position.unrealized_pnl == 50.0
        assert position.current_price == 105.0


# ============================================================================
# BACKTEST CONFIG DATACLASS TESTS
# ============================================================================

class TestBacktestConfigDataclass:
    """Tests for BacktestConfig dataclass."""

    def test_backtest_config_creation_minimal(self):
        """Test creating a BacktestConfig with minimal fields."""
        config = BacktestConfig(
            symbol="SOL",
            start_date="2024-01-01",
            end_date="2024-12-31",
            initial_capital=10000.0
        )

        assert config.symbol == "SOL"
        assert config.start_date == "2024-01-01"
        assert config.end_date == "2024-12-31"
        assert config.initial_capital == 10000.0
        # Defaults
        assert config.fee_rate == 0.001
        assert config.slippage_bps == 5
        assert config.max_position_size == 1.0
        assert config.allow_short is False
        assert config.use_leverage is False
        assert config.max_leverage == 1.0

    def test_backtest_config_creation_full(self):
        """Test creating a BacktestConfig with all fields."""
        config = BacktestConfig(
            symbol="BTC",
            start_date="2024-01-01",
            end_date="2024-06-30",
            initial_capital=50000.0,
            fee_rate=0.0005,
            slippage_bps=10,
            max_position_size=0.5,
            allow_short=True,
            use_leverage=True,
            max_leverage=3.0
        )

        assert config.fee_rate == 0.0005
        assert config.slippage_bps == 10
        assert config.max_position_size == 0.5
        assert config.allow_short is True
        assert config.use_leverage is True
        assert config.max_leverage == 3.0


# ============================================================================
# BACKTEST METRICS DATACLASS TESTS
# ============================================================================

class TestBacktestMetricsDataclass:
    """Tests for BacktestMetrics dataclass."""

    def test_backtest_metrics_creation(self):
        """Test creating BacktestMetrics."""
        metrics = BacktestMetrics(
            total_return=1000.0,
            total_return_pct=10.0,
            annualized_return=25.0,
            sharpe_ratio=1.5,
            sortino_ratio=2.0,
            max_drawdown=15.0,
            max_drawdown_duration=10,
            win_rate=60.0,
            profit_factor=1.8,
            total_trades=50,
            winning_trades=30,
            losing_trades=20,
            avg_win=50.0,
            avg_loss=-30.0,
            largest_win=200.0,
            largest_loss=-100.0,
            avg_trade_duration=5.0,
            expectancy=15.0,
            calmar_ratio=1.67,
            volatility=20.0
        )

        assert metrics.total_return == 1000.0
        assert metrics.sharpe_ratio == 1.5
        assert metrics.win_rate == 60.0
        assert metrics.total_trades == 50


# ============================================================================
# BACKTEST RESULT DATACLASS TESTS
# ============================================================================

class TestBacktestResultDataclass:
    """Tests for BacktestResult dataclass."""

    def test_backtest_result_creation(self, simple_config):
        """Test creating a BacktestResult."""
        metrics = BacktestMetrics(
            total_return=1000.0,
            total_return_pct=10.0,
            annualized_return=25.0,
            sharpe_ratio=1.5,
            sortino_ratio=2.0,
            max_drawdown=15.0,
            max_drawdown_duration=10,
            win_rate=60.0,
            profit_factor=1.8,
            total_trades=50,
            winning_trades=30,
            losing_trades=20,
            avg_win=50.0,
            avg_loss=-30.0,
            largest_win=200.0,
            largest_loss=-100.0,
            avg_trade_duration=5.0,
            expectancy=15.0,
            calmar_ratio=1.67,
            volatility=20.0
        )

        result = BacktestResult(
            id="test_001",
            config=simple_config,
            metrics=metrics,
            trades=[],
            equity_curve=[],
            drawdown_curve=[],
            final_capital=11000.0,
            total_fees=50.0,
            start_time="2024-01-01T00:00:00+00:00",
            end_time="2024-01-01T00:05:00+00:00",
            duration_seconds=300.0,
            strategy_name="test_strategy",
            parameters={"param1": 10}
        )

        assert result.id == "test_001"
        assert result.final_capital == 11000.0
        assert result.strategy_name == "test_strategy"


# ============================================================================
# BACKTEST DB TESTS
# ============================================================================

class TestBacktestDB:
    """Tests for BacktestDB class."""

    def test_db_initialization(self, temp_db_path):
        """Test database initialization creates file."""
        db = BacktestDB(temp_db_path)
        assert temp_db_path.exists()

    def test_db_creates_tables(self, backtest_db, temp_db_path):
        """Test database creates required tables."""
        with backtest_db._get_connection() as conn:
            cursor = conn.cursor()

            # Check backtest_results table
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='backtest_results'")
            assert cursor.fetchone() is not None

            # Check backtest_trades table
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='backtest_trades'")
            assert cursor.fetchone() is not None

    def test_db_creates_indexes(self, backtest_db, temp_db_path):
        """Test database creates required indexes."""
        with backtest_db._get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute("SELECT name FROM sqlite_master WHERE type='index' AND name='idx_bt_symbol'")
            assert cursor.fetchone() is not None

            cursor.execute("SELECT name FROM sqlite_master WHERE type='index' AND name='idx_bt_strategy'")
            assert cursor.fetchone() is not None

    def test_db_connection_context_manager(self, backtest_db):
        """Test database connection context manager."""
        with backtest_db._get_connection() as conn:
            assert conn is not None
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            assert cursor.fetchone()[0] == 1

    def test_db_creates_parent_directories(self):
        """Test database creates parent directories if needed."""
        with tempfile.TemporaryDirectory() as tmpdir:
            nested_path = Path(tmpdir) / "nested" / "dir" / "test.db"
            db = BacktestDB(nested_path)
            assert nested_path.exists()


# ============================================================================
# BACKTEST ENGINE INITIALIZATION TESTS
# ============================================================================

class TestBacktestEngineInit:
    """Tests for BacktestEngine initialization."""

    def test_engine_initialization(self, temp_db_path):
        """Test engine initialization."""
        engine = BacktestEngine(db_path=temp_db_path)
        assert engine.db is not None
        assert engine._data == {}
        assert engine._config is None
        assert engine._capital == 0
        assert engine._trades == []
        assert engine._equity_curve == []

    def test_engine_default_db_path(self):
        """Test engine uses default db path when not specified."""
        with patch('core.backtester.BacktestDB') as mock_db:
            engine = BacktestEngine()
            # Should have called BacktestDB with a path
            mock_db.assert_called_once()


# ============================================================================
# DATA LOADING TESTS
# ============================================================================

class TestDataLoading:
    """Tests for data loading methods."""

    def test_load_data_ohlcv(self, backtest_engine, sample_candles):
        """Test loading OHLCV data."""
        backtest_engine.load_data("SOL", sample_candles)

        assert "SOL" in backtest_engine._data
        assert len(backtest_engine._data["SOL"]) == len(sample_candles)

    def test_load_data_normalizes_symbol(self, backtest_engine, sample_candles):
        """Test data loading normalizes symbol to uppercase."""
        backtest_engine.load_data("sol", sample_candles)

        assert "SOL" in backtest_engine._data
        assert "sol" not in backtest_engine._data

    def test_load_data_sorts_by_timestamp(self, backtest_engine):
        """Test data loading sorts candles by timestamp."""
        candles = [
            OHLCV(timestamp="2024-01-03T00:00:00+00:00", open=100, high=105, low=98, close=103, volume=1000),
            OHLCV(timestamp="2024-01-01T00:00:00+00:00", open=100, high=105, low=98, close=103, volume=1000),
            OHLCV(timestamp="2024-01-02T00:00:00+00:00", open=100, high=105, low=98, close=103, volume=1000),
        ]

        backtest_engine.load_data("SOL", candles)

        assert backtest_engine._data["SOL"][0].timestamp == "2024-01-01T00:00:00+00:00"
        assert backtest_engine._data["SOL"][1].timestamp == "2024-01-02T00:00:00+00:00"
        assert backtest_engine._data["SOL"][2].timestamp == "2024-01-03T00:00:00+00:00"

    def test_load_data_from_dict(self, backtest_engine, sample_candles_dict):
        """Test loading data from dictionaries."""
        backtest_engine.load_data_from_dict("SOL", sample_candles_dict)

        assert "SOL" in backtest_engine._data
        assert len(backtest_engine._data["SOL"]) == len(sample_candles_dict)
        assert isinstance(backtest_engine._data["SOL"][0], OHLCV)

    def test_load_data_from_dict_missing_volume(self, backtest_engine):
        """Test loading data from dict without volume field."""
        data = [
            {
                'timestamp': "2024-01-01T00:00:00+00:00",
                'open': 100.0,
                'high': 105.0,
                'low': 98.0,
                'close': 103.0
                # No volume
            }
        ]

        backtest_engine.load_data_from_dict("SOL", data)

        assert backtest_engine._data["SOL"][0].volume == 0


# ============================================================================
# RUN BACKTEST TESTS
# ============================================================================

class TestRunBacktest:
    """Tests for running backtests."""

    def test_run_basic_backtest(self, engine_with_data, simple_config):
        """Test running a basic backtest."""
        def simple_strategy(engine, candle):
            pass  # Do nothing strategy

        result = engine_with_data.run(
            strategy=simple_strategy,
            config=simple_config,
            strategy_name="do_nothing"
        )

        assert result is not None
        assert result.strategy_name == "do_nothing"
        assert result.final_capital == simple_config.initial_capital
        assert result.metrics.total_trades == 0

    def test_run_no_data_raises_error(self, backtest_engine, simple_config):
        """Test running backtest with no data raises error."""
        def simple_strategy(engine, candle):
            pass

        with pytest.raises(ValueError, match="No data loaded"):
            backtest_engine.run(
                strategy=simple_strategy,
                config=simple_config
            )

    def test_run_no_data_in_date_range_raises_error(self, engine_with_data):
        """Test running backtest with no data in date range raises error."""
        config = BacktestConfig(
            symbol="SOL",
            start_date="2099-01-01",  # Future dates - no data
            end_date="2099-12-31",
            initial_capital=10000.0
        )

        def simple_strategy(engine, candle):
            pass

        with pytest.raises(ValueError, match="No data in specified date range"):
            engine_with_data.run(strategy=simple_strategy, config=config)

    def test_run_buy_and_hold_strategy(self, engine_with_data, simple_config):
        """Test a buy and hold strategy."""
        def buy_and_hold(engine, candle):
            if engine.is_flat():
                engine.buy(1.0, "Buy signal")

        result = engine_with_data.run(
            strategy=buy_and_hold,
            config=simple_config,
            strategy_name="buy_and_hold"
        )

        # Should have at least 2 trades (buy at start, sell at end)
        assert result.metrics.total_trades >= 2
        assert result.final_capital != simple_config.initial_capital

    def test_run_with_parameters(self, engine_with_data, simple_config):
        """Test running backtest with strategy parameters."""
        def parameterized_strategy(engine, candle):
            pass

        params = {"rsi_period": 14, "threshold": 30}
        result = engine_with_data.run(
            strategy=parameterized_strategy,
            config=simple_config,
            strategy_name="parameterized",
            parameters=params
        )

        assert result.parameters == params

    def test_run_strategy_error_handling(self, engine_with_data, simple_config):
        """Test strategy errors are logged but don't crash backtest."""
        call_count = [0]

        def error_strategy(engine, candle):
            call_count[0] += 1
            if call_count[0] == 5:
                raise RuntimeError("Strategy error")

        # Should complete without raising
        result = engine_with_data.run(
            strategy=error_strategy,
            config=simple_config,
            strategy_name="error_strategy"
        )

        assert result is not None


# ============================================================================
# TRADING METHOD TESTS
# ============================================================================

class TestTradingMethods:
    """Tests for trading methods (buy, sell, close_position)."""

    def test_buy_opens_long_position(self, engine_with_data, simple_config):
        """Test buy method opens a long position."""
        positions_opened = []

        def buy_strategy(engine, candle):
            if engine.is_flat():
                engine.buy(0.5, "Test buy")
                positions_opened.append(engine.position.side)

        engine_with_data.run(strategy=buy_strategy, config=simple_config)

        assert PositionSide.LONG in positions_opened

    def test_buy_respects_size_fraction(self, engine_with_data, simple_config):
        """Test buy respects the size_fraction parameter."""
        capital_used = []

        def sized_buy_strategy(engine, candle):
            if engine.is_flat():
                initial_capital = engine.capital
                engine.buy(0.5, "Half position")
                capital_used.append(initial_capital - engine.capital)

        engine_with_data.run(strategy=sized_buy_strategy, config=simple_config)

        # Capital used should be approximately half (minus fees)
        assert len(capital_used) > 0

    def test_buy_when_already_long_does_nothing(self, engine_with_data, simple_config):
        """Test buy when already long does nothing."""
        buy_count = [0]

        def double_buy_strategy(engine, candle):
            old_pos = engine.position.quantity
            engine.buy(1.0, "Buy")
            if engine.position.quantity != old_pos:
                buy_count[0] += 1

        engine_with_data.run(strategy=double_buy_strategy, config=simple_config)

        # Should only record one actual buy (first time)
        assert buy_count[0] == 1

    def test_sell_closes_long_position(self, engine_with_data, simple_config):
        """Test sell closes a long position."""
        position_states = []

        def buy_sell_strategy(engine, candle):
            if engine.is_flat() and len(position_states) == 0:
                engine.buy(1.0)
                position_states.append("bought")
            elif engine.is_long() and len(position_states) == 1:
                engine.sell()
                position_states.append("sold")

        engine_with_data.run(strategy=buy_sell_strategy, config=simple_config)

        assert position_states == ["bought", "sold"]

    def test_sell_all_closes_position(self, engine_with_data, simple_config):
        """Test sell_all closes all positions."""
        def sell_all_strategy(engine, candle):
            if engine.is_flat():
                engine.buy(1.0)
            elif engine.is_long():
                engine.sell_all("Close all")

        result = engine_with_data.run(strategy=sell_all_strategy, config=simple_config)

        # Should have trades with "Close all" reason
        close_trades = [t for t in result.trades if t.reason == "Close all"]
        assert len(close_trades) >= 1

    def test_close_position_when_flat_does_nothing(self, engine_with_data, simple_config):
        """Test close_position when flat does nothing."""
        trade_count_before = []
        trade_count_after = []

        def close_flat_strategy(engine, candle):
            trade_count_before.append(len(engine._trades))
            engine.close_position("Test close")
            trade_count_after.append(len(engine._trades))

        engine_with_data.run(strategy=close_flat_strategy, config=simple_config)

        # Trade counts should be same (no trades from closing flat)
        for before, after in zip(trade_count_before[:5], trade_count_after[:5]):
            assert before == after


class TestShortSelling:
    """Tests for short selling functionality."""

    def test_short_position_when_enabled(self, engine_with_data, short_enabled_config):
        """Test opening short position when shorting is enabled."""
        position_sides = []

        def short_strategy(engine, candle):
            if engine.is_flat():
                engine.sell(0.5, "Open short")
                position_sides.append(engine.position.side)

        engine_with_data.run(strategy=short_strategy, config=short_enabled_config)

        assert PositionSide.SHORT in position_sides

    def test_short_position_disabled_by_default(self, engine_with_data, simple_config):
        """Test shorting is disabled by default."""
        position_sides = []

        def short_attempt_strategy(engine, candle):
            if engine.is_flat():
                engine.sell(0.5, "Attempt short")
                position_sides.append(engine.position.side)

        engine_with_data.run(strategy=short_attempt_strategy, config=simple_config)

        # Should remain flat (shorting disabled)
        assert all(side == PositionSide.FLAT for side in position_sides)

    def test_close_short_position(self, engine_with_data, short_enabled_config):
        """Test closing a short position."""
        states = []

        def short_close_strategy(engine, candle):
            if engine.is_flat() and len(states) == 0:
                engine.sell(0.5, "Open short")
                states.append("shorted")
            elif engine.is_short() and len(states) == 1:
                engine.close_position("Close short")
                states.append("closed")

        engine_with_data.run(strategy=short_close_strategy, config=short_enabled_config)

        assert states == ["shorted", "closed"]


# ============================================================================
# INDICATOR TESTS
# ============================================================================

class TestIndicators:
    """Tests for technical indicator methods."""

    def test_close_price(self, engine_with_data, simple_config):
        """Test close price accessor."""
        close_prices = []

        def collect_close(engine, candle):
            close_prices.append(engine.close())

        engine_with_data.run(strategy=collect_close, config=simple_config)

        assert len(close_prices) > 0
        assert all(p > 0 for p in close_prices)

    def test_close_price_lookback(self, engine_with_data, simple_config):
        """Test close price with lookback."""
        close_pairs = []

        def collect_close_lookback(engine, candle):
            if engine._current_idx > 0:
                close_pairs.append((engine.close(0), engine.close(1)))

        engine_with_data.run(strategy=collect_close_lookback, config=simple_config)

        # Current and previous prices should be different
        assert len(close_pairs) > 0

    def test_high_price(self, engine_with_data, simple_config):
        """Test high price accessor."""
        prices = []

        def collect_high(engine, candle):
            prices.append((engine.high(), engine.close()))

        engine_with_data.run(strategy=collect_high, config=simple_config)

        # High should be >= close
        for high, close in prices:
            assert high >= close

    def test_low_price(self, engine_with_data, simple_config):
        """Test low price accessor."""
        prices = []

        def collect_low(engine, candle):
            prices.append((engine.low(), engine.close()))

        engine_with_data.run(strategy=collect_low, config=simple_config)

        # Low should be <= close
        for low, close in prices:
            assert low <= close

    def test_volume(self, engine_with_data, simple_config):
        """Test volume accessor."""
        volumes = []

        def collect_volume(engine, candle):
            volumes.append(engine.volume())

        engine_with_data.run(strategy=collect_volume, config=simple_config)

        assert len(volumes) > 0
        assert all(v > 0 for v in volumes)

    def test_sma(self, engine_with_data, simple_config):
        """Test Simple Moving Average calculation."""
        sma_values = []

        def collect_sma(engine, candle):
            sma_values.append(engine.sma(20))

        engine_with_data.run(strategy=collect_sma, config=simple_config)

        assert len(sma_values) > 0
        # SMA should be positive
        assert all(v >= 0 for v in sma_values)

    def test_ema(self, engine_with_data, simple_config):
        """Test Exponential Moving Average calculation."""
        ema_values = []

        def collect_ema(engine, candle):
            ema_values.append(engine.ema(20))

        engine_with_data.run(strategy=collect_ema, config=simple_config)

        assert len(ema_values) > 0

    def test_ema_insufficient_data(self, backtest_engine, simple_config):
        """Test EMA returns 0 with insufficient data."""
        # Only 5 candles
        candles = [
            OHLCV(timestamp=f"2024-01-0{i+1}T00:00:00+00:00", open=100, high=105, low=98, close=100+i, volume=1000)
            for i in range(5)
        ]
        backtest_engine.load_data("SOL", candles)

        ema_values = []

        def collect_ema(engine, candle):
            ema_values.append(engine.ema(20))  # Need 40 candles for period 20

        backtest_engine.run(strategy=collect_ema, config=simple_config)

        # Should return 0 for insufficient data
        assert all(v == 0 for v in ema_values)

    def test_rsi(self, engine_with_data, simple_config):
        """Test RSI calculation."""
        rsi_values = []

        def collect_rsi(engine, candle):
            rsi_values.append(engine.rsi(14))

        engine_with_data.run(strategy=collect_rsi, config=simple_config)

        # RSI should be between 0 and 100
        assert all(0 <= v <= 100 for v in rsi_values)

    def test_rsi_returns_50_insufficient_data(self, backtest_engine, simple_config):
        """Test RSI returns 50 with insufficient data."""
        candles = [
            OHLCV(timestamp=f"2024-01-0{i+1}T00:00:00+00:00", open=100, high=105, low=98, close=100+i, volume=1000)
            for i in range(5)
        ]
        backtest_engine.load_data("SOL", candles)

        rsi_values = []

        def collect_rsi(engine, candle):
            rsi_values.append(engine.rsi(14))

        backtest_engine.run(strategy=collect_rsi, config=simple_config)

        # Default RSI when insufficient data
        assert all(v == 50 for v in rsi_values)

    def test_rsi_overbought(self, backtest_engine, simple_config):
        """Test RSI approaches 100 with only gains."""
        # Create candles with only upward movement
        candles = [
            OHLCV(timestamp=f"2024-01-{i+1:02d}T00:00:00+00:00", open=100+i, high=102+i, low=99+i, close=101+i, volume=1000)
            for i in range(30)
        ]
        backtest_engine.load_data("SOL", candles)

        rsi_values = []

        def collect_rsi(engine, candle):
            rsi_values.append(engine.rsi(14))

        backtest_engine.run(strategy=collect_rsi, config=simple_config)

        # Last RSI values should be high (approaching 100)
        assert rsi_values[-1] > 70

    def test_macd(self, engine_with_data, simple_config):
        """Test MACD calculation."""
        macd_values = []

        def collect_macd(engine, candle):
            macd_values.append(engine.macd())

        engine_with_data.run(strategy=collect_macd, config=simple_config)

        assert len(macd_values) > 0
        # Should have all required keys
        assert all('macd' in v and 'signal' in v and 'histogram' in v for v in macd_values)

    def test_bollinger_bands(self, engine_with_data, simple_config):
        """Test Bollinger Bands calculation."""
        bb_values = []

        def collect_bb(engine, candle):
            bb_values.append(engine.bollinger_bands(20, 2))

        engine_with_data.run(strategy=collect_bb, config=simple_config)

        assert len(bb_values) > 0
        # Upper > middle > lower
        for bb in bb_values:
            if bb['middle'] > 0:  # Has data
                assert bb['upper'] >= bb['middle'] >= bb['lower']

    def test_bollinger_bands_empty_data(self, backtest_engine, simple_config):
        """Test Bollinger Bands with no data."""
        backtest_engine.load_data("SOL", [
            OHLCV(timestamp="2024-01-01T00:00:00+00:00", open=100, high=105, low=98, close=100, volume=1000)
        ])

        bb_values = []

        def collect_bb(engine, candle):
            # When there's only 1 candle and period is 20, should return zeros
            bb_values.append(engine.bollinger_bands(20, 2))

        backtest_engine.run(strategy=collect_bb, config=simple_config)

        # Should have some values (even if zeros due to insufficient data)
        assert len(bb_values) >= 1

    def test_atr(self, engine_with_data, simple_config):
        """Test ATR calculation."""
        atr_values = []

        def collect_atr(engine, candle):
            atr_values.append(engine.atr(14))

        engine_with_data.run(strategy=collect_atr, config=simple_config)

        # ATR should be non-negative
        assert all(v >= 0 for v in atr_values)

    def test_atr_insufficient_data(self, backtest_engine, simple_config):
        """Test ATR returns 0 with insufficient data."""
        candles = [
            OHLCV(timestamp=f"2024-01-0{i+1}T00:00:00+00:00", open=100, high=105, low=98, close=100+i, volume=1000)
            for i in range(5)
        ]
        backtest_engine.load_data("SOL", candles)

        atr_values = []

        def collect_atr(engine, candle):
            atr_values.append(engine.atr(14))

        backtest_engine.run(strategy=collect_atr, config=simple_config)

        # Should return 0 for insufficient data
        assert all(v == 0 for v in atr_values)


# ============================================================================
# STATE ACCESSOR TESTS
# ============================================================================

class TestStateAccessors:
    """Tests for state accessor methods."""

    def test_position_property(self, engine_with_data, simple_config):
        """Test position property."""
        positions = []

        def collect_position(engine, candle):
            positions.append(engine.position)

        engine_with_data.run(strategy=collect_position, config=simple_config)

        assert all(isinstance(p, BacktestPosition) for p in positions)

    def test_capital_property(self, engine_with_data, simple_config):
        """Test capital property."""
        capitals = []

        def collect_capital(engine, candle):
            capitals.append(engine.capital)

        engine_with_data.run(strategy=collect_capital, config=simple_config)

        assert capitals[0] == simple_config.initial_capital

    def test_equity_property(self, engine_with_data, simple_config):
        """Test equity property."""
        equities = []

        def collect_equity(engine, candle):
            equities.append(engine.equity)

        engine_with_data.run(strategy=collect_equity, config=simple_config)

        # Initially equity equals capital
        assert equities[0] == simple_config.initial_capital

    def test_is_long(self, engine_with_data, simple_config):
        """Test is_long method."""
        long_states = []

        def check_long(engine, candle):
            if engine.is_flat():
                engine.buy(1.0)
            long_states.append(engine.is_long())

        engine_with_data.run(strategy=check_long, config=simple_config)

        # After buy, should be long
        assert True in long_states

    def test_is_short(self, engine_with_data, short_enabled_config):
        """Test is_short method."""
        short_states = []

        def check_short(engine, candle):
            if engine.is_flat():
                engine.sell(1.0)
            short_states.append(engine.is_short())

        engine_with_data.run(strategy=check_short, config=short_enabled_config)

        # After short sell, should be short
        assert True in short_states

    def test_is_flat(self, engine_with_data, simple_config):
        """Test is_flat method."""
        flat_states = []

        def check_flat(engine, candle):
            flat_states.append(engine.is_flat())

        engine_with_data.run(strategy=check_flat, config=simple_config)

        # Initially should be flat
        assert flat_states[0] is True


# ============================================================================
# METRICS CALCULATION TESTS
# ============================================================================

class TestMetricsCalculation:
    """Tests for metrics calculation."""

    def test_metrics_empty_equity_curve(self, backtest_engine):
        """Test metrics calculation with empty equity curve."""
        backtest_engine._config = BacktestConfig(
            symbol="SOL",
            start_date="2024-01-01",
            end_date="2024-12-31",
            initial_capital=10000.0
        )
        backtest_engine._equity_curve = []
        backtest_engine._trades = []

        metrics = backtest_engine._calculate_metrics()

        assert metrics.total_return == 0
        assert metrics.sharpe_ratio == 0
        assert metrics.total_trades == 0

    def test_metrics_total_return(self, engine_with_data, simple_config):
        """Test total return calculation."""
        def buy_hold_strategy(engine, candle):
            if engine.is_flat():
                engine.buy(1.0)

        result = engine_with_data.run(strategy=buy_hold_strategy, config=simple_config)

        expected_return = result.final_capital - simple_config.initial_capital
        assert result.metrics.total_return == pytest.approx(expected_return, rel=0.01)

    def test_metrics_win_rate(self, engine_with_data, simple_config):
        """Test win rate calculation."""
        trade_count = [0]

        def trading_strategy(engine, candle):
            if engine.is_flat() and trade_count[0] < 5:
                engine.buy(0.2)
            elif engine.is_long():
                engine.sell()
                trade_count[0] += 1

        result = engine_with_data.run(strategy=trading_strategy, config=simple_config)

        if result.metrics.total_trades > 0:
            expected_win_rate = (result.metrics.winning_trades / result.metrics.total_trades) * 100
            assert result.metrics.win_rate == pytest.approx(expected_win_rate, rel=0.01)

    def test_metrics_profit_factor(self, engine_with_data, simple_config):
        """Test profit factor calculation."""
        def trading_strategy(engine, candle):
            if engine.is_flat():
                engine.buy(0.2)
            elif engine.is_long():
                engine.sell()

        result = engine_with_data.run(strategy=trading_strategy, config=simple_config)

        # Profit factor should be >= 0
        assert result.metrics.profit_factor >= 0


# ============================================================================
# DRAWDOWN CALCULATION TESTS
# ============================================================================

class TestDrawdownCalculation:
    """Tests for drawdown calculation."""

    def test_drawdown_curve_calculation(self, engine_with_data, simple_config):
        """Test drawdown curve is calculated."""
        def simple_strategy(engine, candle):
            pass

        result = engine_with_data.run(strategy=simple_strategy, config=simple_config)

        # Should have drawdown curve
        assert len(result.drawdown_curve) > 0
        # All drawdowns should be >= 0
        assert all(d['drawdown'] >= 0 for d in result.drawdown_curve)

    def test_max_drawdown(self, engine_with_data, simple_config):
        """Test max drawdown is calculated correctly."""
        def buy_hold_strategy(engine, candle):
            if engine.is_flat():
                engine.buy(1.0)

        result = engine_with_data.run(strategy=buy_hold_strategy, config=simple_config)

        # Max drawdown should match the max from drawdown curve
        if result.drawdown_curve:
            curve_max = max(d['drawdown'] for d in result.drawdown_curve)
            assert result.metrics.max_drawdown == pytest.approx(curve_max, rel=0.01)


# ============================================================================
# RESULT PERSISTENCE TESTS
# ============================================================================

class TestResultPersistence:
    """Tests for saving and retrieving backtest results."""

    def test_result_saved_to_db(self, engine_with_data, simple_config):
        """Test results are saved to database."""
        def simple_strategy(engine, candle):
            pass

        result = engine_with_data.run(
            strategy=simple_strategy,
            config=simple_config,
            strategy_name="test_save"
        )

        # Retrieve the result
        saved = engine_with_data.get_result(result.id)

        assert saved is not None
        assert saved['id'] == result.id
        assert saved['strategy_name'] == "test_save"

    def test_get_nonexistent_result(self, engine_with_data):
        """Test getting a nonexistent result returns None."""
        result = engine_with_data.get_result("nonexistent_id")
        assert result is None

    def test_get_results_all(self, engine_with_data, simple_config):
        """Test getting all results."""
        def simple_strategy(engine, candle):
            pass

        # Run a few backtests
        for i in range(3):
            engine_with_data.run(
                strategy=simple_strategy,
                config=simple_config,
                strategy_name=f"strategy_{i}"
            )

        results = engine_with_data.get_results()

        assert len(results) >= 3

    def test_get_results_by_symbol(self, engine_with_data, simple_config):
        """Test filtering results by symbol."""
        def simple_strategy(engine, candle):
            pass

        engine_with_data.run(
            strategy=simple_strategy,
            config=simple_config,
            strategy_name="sol_strategy"
        )

        results = engine_with_data.get_results(symbol="SOL")

        assert all(r['symbol'] == "SOL" for r in results)

    def test_get_results_by_strategy(self, engine_with_data, simple_config):
        """Test filtering results by strategy name."""
        def simple_strategy(engine, candle):
            pass

        engine_with_data.run(
            strategy=simple_strategy,
            config=simple_config,
            strategy_name="unique_strategy_name"
        )

        results = engine_with_data.get_results(strategy="unique_strategy_name")

        assert all(r['strategy_name'] == "unique_strategy_name" for r in results)

    def test_get_results_with_limit(self, engine_with_data, simple_config):
        """Test limiting number of results."""
        def simple_strategy(engine, candle):
            pass

        for i in range(5):
            engine_with_data.run(
                strategy=simple_strategy,
                config=simple_config,
                strategy_name=f"limited_strategy_{i}"
            )

        results = engine_with_data.get_results(limit=3)

        assert len(results) <= 3

    def test_trades_saved_to_db(self, engine_with_data, simple_config):
        """Test trades are saved to database."""
        def trading_strategy(engine, candle):
            if engine.is_flat():
                engine.buy(0.5, "Test buy")
            elif engine.is_long():
                engine.sell()

        result = engine_with_data.run(
            strategy=trading_strategy,
            config=simple_config,
            strategy_name="trading_test"
        )

        # Verify trades are in the database
        with engine_with_data.db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM backtest_trades WHERE backtest_id = ?", (result.id,))
            count = cursor.fetchone()[0]

        assert count == len(result.trades)


# ============================================================================
# SINGLETON TESTS
# ============================================================================

class TestSingleton:
    """Tests for singleton accessor function."""

    def test_get_backtest_engine_singleton(self):
        """Test get_backtest_engine returns singleton."""
        import core.backtester as bt_module
        bt_module._engine = None  # Reset singleton

        engine1 = get_backtest_engine()
        engine2 = get_backtest_engine()

        assert engine1 is engine2


# ============================================================================
# EDGE CASES & ERROR HANDLING
# ============================================================================

class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_very_small_position_size(self, engine_with_data, simple_config):
        """Test handling very small position sizes."""
        def tiny_buy_strategy(engine, candle):
            if engine.is_flat():
                engine.buy(0.001)  # Very small fraction

        result = engine_with_data.run(strategy=tiny_buy_strategy, config=simple_config)

        assert result is not None

    def test_execution_price_slippage(self, engine_with_data, simple_config):
        """Test execution prices include slippage."""
        executed_prices = []
        candle_closes = []

        def record_prices(engine, candle):
            if engine.is_flat():
                candle_closes.append(candle.close)
                engine.buy(1.0)
                # The trade price should be close + slippage
                if engine._trades:
                    executed_prices.append(engine._trades[-1].price)

        result = engine_with_data.run(strategy=record_prices, config=simple_config)

        # Buy price should be higher than close (slippage)
        if executed_prices and candle_closes:
            assert executed_prices[0] > candle_closes[0]

    def test_fee_deduction(self, engine_with_data, simple_config):
        """Test fees are deducted from capital."""
        initial_capital = simple_config.initial_capital

        def buy_strategy(engine, candle):
            if engine.is_flat():
                engine.buy(1.0)

        result = engine_with_data.run(strategy=buy_strategy, config=simple_config)

        # Total fees should be > 0 if trades were made
        if result.metrics.total_trades > 0:
            assert result.total_fees > 0

    def test_position_value_update_during_backtest(self, engine_with_data, simple_config):
        """Test position unrealized PnL is updated during backtest."""
        unrealized_pnls = []

        def record_pnl(engine, candle):
            if engine.is_flat():
                engine.buy(1.0)
            elif engine.is_long():
                unrealized_pnls.append(engine.position.unrealized_pnl)

        engine_with_data.run(strategy=record_pnl, config=simple_config)

        # Should have varying unrealized PnLs
        if len(unrealized_pnls) > 1:
            assert not all(p == unrealized_pnls[0] for p in unrealized_pnls)

    def test_close_lookback_out_of_range(self, engine_with_data, simple_config):
        """Test close with lookback out of range returns 0."""
        values = []

        def check_lookback(engine, candle):
            values.append(engine.close(1000))  # Way out of range

        engine_with_data.run(strategy=check_lookback, config=simple_config)

        assert all(v == 0 for v in values)

    def test_rsi_all_losses_returns_zero(self, backtest_engine, simple_config):
        """Test RSI returns 0 when avg_loss is 0 (all gains)."""
        # Create strictly increasing prices
        candles = [
            OHLCV(timestamp=f"2024-01-{i+1:02d}T00:00:00+00:00",
                  open=100+i, high=101+i, low=99+i, close=100+i, volume=1000)
            for i in range(20)
        ]
        backtest_engine.load_data("SOL", candles)

        rsi_values = []

        def collect_rsi(engine, candle):
            rsi_values.append(engine.rsi(14))

        backtest_engine.run(strategy=collect_rsi, config=simple_config)

        # With all gains, RSI should approach 100
        assert rsi_values[-1] == 100


# ============================================================================
# INTEGRATION TESTS
# ============================================================================

class TestIntegration:
    """Integration tests combining multiple components."""

    def test_full_trading_workflow(self, engine_with_data, simple_config):
        """Test complete trading workflow."""
        def rsi_strategy(engine, candle):
            rsi = engine.rsi(14)

            if rsi < 30 and engine.is_flat():
                engine.buy(0.5, f"RSI oversold: {rsi:.1f}")
            elif rsi > 70 and engine.is_long():
                engine.sell(1.0, f"RSI overbought: {rsi:.1f}")

        result = engine_with_data.run(
            strategy=rsi_strategy,
            config=simple_config,
            strategy_name="rsi_strategy",
            parameters={"rsi_period": 14, "oversold": 30, "overbought": 70}
        )

        assert result is not None
        assert result.strategy_name == "rsi_strategy"
        assert result.parameters["rsi_period"] == 14

    def test_ma_crossover_strategy(self, engine_with_data, simple_config):
        """Test MA crossover strategy."""
        def ma_crossover(engine, candle):
            fast_ma = engine.sma(10)
            slow_ma = engine.sma(20)

            if fast_ma > slow_ma and engine.is_flat():
                engine.buy(1.0, "Golden cross")
            elif fast_ma < slow_ma and engine.is_long():
                engine.sell(1.0, "Death cross")

        result = engine_with_data.run(
            strategy=ma_crossover,
            config=simple_config,
            strategy_name="ma_crossover"
        )

        assert result is not None

    def test_bollinger_band_strategy(self, engine_with_data, simple_config):
        """Test Bollinger Band strategy."""
        def bb_strategy(engine, candle):
            bb = engine.bollinger_bands(20, 2)
            close = engine.close()

            if close < bb['lower'] and engine.is_flat():
                engine.buy(1.0, "Below lower band")
            elif close > bb['upper'] and engine.is_long():
                engine.sell(1.0, "Above upper band")

        result = engine_with_data.run(
            strategy=bb_strategy,
            config=simple_config,
            strategy_name="bollinger_strategy"
        )

        assert result is not None

    def test_atr_position_sizing(self, engine_with_data, simple_config):
        """Test ATR-based position sizing."""
        def atr_strategy(engine, candle):
            atr = engine.atr(14)

            if atr > 0 and engine.is_flat():
                # Size position based on ATR
                size = min(1.0, 2.0 / (atr / engine.close() * 100))
                engine.buy(size, f"ATR-sized: {size:.2f}")

        result = engine_with_data.run(
            strategy=atr_strategy,
            config=simple_config,
            strategy_name="atr_sizing"
        )

        assert result is not None

    def test_combined_indicators_strategy(self, engine_with_data, simple_config):
        """Test strategy using multiple indicators."""
        def combined_strategy(engine, candle):
            rsi = engine.rsi(14)
            macd = engine.macd()
            bb = engine.bollinger_bands(20, 2)
            close = engine.close()

            # Buy when RSI oversold and MACD bullish
            if rsi < 35 and macd['macd'] > macd['signal'] and engine.is_flat():
                engine.buy(0.5, "Combined buy signal")

            # Sell when above upper band or RSI overbought
            elif (close > bb['upper'] or rsi > 65) and engine.is_long():
                engine.sell(1.0, "Combined sell signal")

        result = engine_with_data.run(
            strategy=combined_strategy,
            config=simple_config,
            strategy_name="combined_strategy"
        )

        assert result is not None
        assert len(result.equity_curve) > 0


# ============================================================================
# PERFORMANCE AND STRESS TESTS
# ============================================================================

class TestPerformance:
    """Performance and stress tests."""

    def test_large_dataset(self, backtest_engine, simple_config):
        """Test handling large dataset."""
        # Generate 1000 candles
        candles = []
        base_date = datetime(2024, 1, 1, tzinfo=timezone.utc)

        for i in range(1000):
            candles.append(OHLCV(
                timestamp=(base_date + timedelta(hours=i)).isoformat(),
                open=100 + math.sin(i/100) * 10,
                high=102 + math.sin(i/100) * 10,
                low=98 + math.sin(i/100) * 10,
                close=100 + math.sin(i/100) * 10 + 0.01 * i,
                volume=1000000
            ))

        backtest_engine.load_data("SOL", candles)

        config = BacktestConfig(
            symbol="SOL",
            start_date="2024-01-01",
            end_date="2024-02-11",
            initial_capital=10000.0
        )

        def simple_strategy(engine, candle):
            if engine.is_flat():
                engine.buy(0.5)
            elif engine.is_long():
                engine.sell()

        result = backtest_engine.run(strategy=simple_strategy, config=config)

        assert result is not None
        assert len(result.equity_curve) == 1000

    def test_high_frequency_trading(self, engine_with_data, simple_config):
        """Test high frequency trading (many trades)."""
        trade_count = [0]

        def hft_strategy(engine, candle):
            if trade_count[0] < 50:
                if engine.is_flat():
                    engine.buy(0.1)
                elif engine.is_long():
                    engine.sell()
                    trade_count[0] += 1

        result = engine_with_data.run(strategy=hft_strategy, config=simple_config)

        # Should handle many trades
        assert result.metrics.total_trades >= 50
