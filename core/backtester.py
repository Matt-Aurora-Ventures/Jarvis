"""
Backtesting Engine - Historical strategy backtesting.
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from enum import Enum
import json
import sqlite3
from pathlib import Path
from contextlib import contextmanager
import uuid
import math

logger = logging.getLogger(__name__)


class OrderSide(Enum):
    """Order side."""
    BUY = "buy"
    SELL = "sell"


class PositionSide(Enum):
    """Position side."""
    LONG = "long"
    SHORT = "short"
    FLAT = "flat"


@dataclass
class OHLCV:
    """OHLCV candle data."""
    timestamp: str
    open: float
    high: float
    low: float
    close: float
    volume: float


@dataclass
class BacktestTrade:
    """A trade executed during backtest."""
    id: str
    timestamp: str
    side: OrderSide
    price: float
    quantity: float
    value: float
    fee: float
    pnl: float = 0.0
    cumulative_pnl: float = 0.0
    position_after: float = 0.0
    reason: str = ""


@dataclass
class BacktestPosition:
    """Current position during backtest."""
    side: PositionSide
    quantity: float
    entry_price: float
    entry_time: str
    unrealized_pnl: float = 0.0
    current_price: float = 0.0


@dataclass
class BacktestConfig:
    """Backtesting configuration."""
    symbol: str
    start_date: str
    end_date: str
    initial_capital: float
    fee_rate: float = 0.001  # 0.1% per trade
    slippage_bps: float = 5  # 5 basis points
    max_position_size: float = 1.0  # As fraction of capital
    allow_short: bool = False
    use_leverage: bool = False
    max_leverage: float = 1.0


@dataclass
class BacktestMetrics:
    """Backtesting performance metrics."""
    total_return: float
    total_return_pct: float
    annualized_return: float
    sharpe_ratio: float
    sortino_ratio: float
    max_drawdown: float
    max_drawdown_duration: int  # In candles
    win_rate: float
    profit_factor: float
    total_trades: int
    winning_trades: int
    losing_trades: int
    avg_win: float
    avg_loss: float
    largest_win: float
    largest_loss: float
    avg_trade_duration: float
    expectancy: float
    calmar_ratio: float
    volatility: float


@dataclass
class BacktestResult:
    """Complete backtest result."""
    id: str
    config: BacktestConfig
    metrics: BacktestMetrics
    trades: List[BacktestTrade]
    equity_curve: List[Dict[str, float]]
    drawdown_curve: List[Dict[str, float]]
    final_capital: float
    total_fees: float
    start_time: str
    end_time: str
    duration_seconds: float
    strategy_name: str
    parameters: Dict[str, Any]


class BacktestDB:
    """SQLite storage for backtest results."""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        """Initialize database schema."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        with self._get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS backtest_results (
                    id TEXT PRIMARY KEY,
                    symbol TEXT,
                    strategy_name TEXT,
                    start_date TEXT,
                    end_date TEXT,
                    initial_capital REAL,
                    final_capital REAL,
                    total_return_pct REAL,
                    sharpe_ratio REAL,
                    max_drawdown REAL,
                    win_rate REAL,
                    total_trades INTEGER,
                    total_fees REAL,
                    parameters_json TEXT,
                    metrics_json TEXT,
                    created_at TEXT
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS backtest_trades (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    backtest_id TEXT NOT NULL,
                    trade_id TEXT,
                    timestamp TEXT,
                    side TEXT,
                    price REAL,
                    quantity REAL,
                    value REAL,
                    fee REAL,
                    pnl REAL,
                    cumulative_pnl REAL,
                    reason TEXT,
                    FOREIGN KEY (backtest_id) REFERENCES backtest_results(id)
                )
            """)

            cursor.execute("CREATE INDEX IF NOT EXISTS idx_bt_symbol ON backtest_results(symbol)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_bt_strategy ON backtest_results(strategy_name)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_trades_bt ON backtest_trades(backtest_id)")

            conn.commit()

    @contextmanager
    def _get_connection(self):
        """Get database connection."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()


class BacktestEngine:
    """
    Historical backtesting engine.

    Usage:
        engine = BacktestEngine()

        # Load historical data
        engine.load_data("SOL", candles)

        # Define strategy
        def my_strategy(engine, candle):
            if engine.rsi() < 30:
                engine.buy(0.5)  # Buy with 50% of capital
            elif engine.rsi() > 70:
                engine.sell_all()

        # Run backtest
        result = engine.run(
            strategy=my_strategy,
            config=BacktestConfig(
                symbol="SOL",
                start_date="2024-01-01",
                end_date="2024-12-31",
                initial_capital=10000
            )
        )
    """

    def __init__(self, db_path: Optional[Path] = None):
        db_path = db_path or Path(__file__).parent.parent / "data" / "backtests.db"
        self.db = BacktestDB(db_path)

        # Data
        self._data: Dict[str, List[OHLCV]] = {}

        # State during backtest
        self._config: Optional[BacktestConfig] = None
        self._capital: float = 0
        self._position: BacktestPosition = None
        self._trades: List[BacktestTrade] = []
        self._equity_curve: List[Dict] = []
        self._current_idx: int = 0
        self._current_candle: Optional[OHLCV] = None

        # Indicators cache
        self._indicator_cache: Dict[str, Any] = {}

    def load_data(self, symbol: str, candles: List[OHLCV]):
        """Load historical data for backtesting."""
        self._data[symbol.upper()] = sorted(candles, key=lambda c: c.timestamp)
        logger.info(f"Loaded {len(candles)} candles for {symbol}")

    def load_data_from_dict(self, symbol: str, data: List[Dict]):
        """Load data from list of dictionaries."""
        candles = [
            OHLCV(
                timestamp=d['timestamp'],
                open=d['open'],
                high=d['high'],
                low=d['low'],
                close=d['close'],
                volume=d.get('volume', 0)
            )
            for d in data
        ]
        self.load_data(symbol, candles)

    def run(
        self,
        strategy: Callable,
        config: BacktestConfig,
        strategy_name: str = "unnamed",
        parameters: Dict[str, Any] = None
    ) -> BacktestResult:
        """Run a backtest."""
        start_time = datetime.now(timezone.utc)
        backtest_id = str(uuid.uuid4())[:8]

        # Initialize state
        self._config = config
        self._capital = config.initial_capital
        self._position = BacktestPosition(
            side=PositionSide.FLAT,
            quantity=0,
            entry_price=0,
            entry_time=""
        )
        self._trades = []
        self._equity_curve = []
        self._indicator_cache = {}

        # Get data
        candles = self._data.get(config.symbol.upper(), [])
        if not candles:
            raise ValueError(f"No data loaded for {config.symbol}")

        # Filter by date range
        filtered_candles = [
            c for c in candles
            if config.start_date <= c.timestamp[:10] <= config.end_date
        ]

        if not filtered_candles:
            raise ValueError("No data in specified date range")

        logger.info(f"Running backtest {backtest_id}: {strategy_name} on {config.symbol}")

        # Main loop
        for i, candle in enumerate(filtered_candles):
            self._current_idx = i
            self._current_candle = candle

            # Update position value
            if self._position.side != PositionSide.FLAT:
                self._position.current_price = candle.close
                if self._position.side == PositionSide.LONG:
                    self._position.unrealized_pnl = (candle.close - self._position.entry_price) * self._position.quantity
                else:
                    self._position.unrealized_pnl = (self._position.entry_price - candle.close) * self._position.quantity

            # Record equity using side-aware accounting.
            # For longs, capital excludes deployed principal, so include full market value.
            # For shorts, capital retains collateral under the current margin model; use
            # unrealized PnL adjustment on top of capital.
            if self._position.side == PositionSide.LONG:
                equity = self._capital + (self._position.quantity * candle.close)
            elif self._position.side == PositionSide.SHORT:
                equity = self._capital + self._position.unrealized_pnl
            else:
                equity = self._capital
            self._equity_curve.append({
                'timestamp': candle.timestamp,
                'equity': equity,
                'price': candle.close
            })

            # Run strategy
            try:
                strategy(self, candle)
            except Exception as e:
                logger.error(f"Strategy error at {candle.timestamp}: {e}")

        # Close any remaining position
        if self._position.side != PositionSide.FLAT:
            self.close_position("End of backtest")

        # Calculate metrics
        metrics = self._calculate_metrics()

        end_time = datetime.now(timezone.utc)
        duration = (end_time - start_time).total_seconds()

        result = BacktestResult(
            id=backtest_id,
            config=config,
            metrics=metrics,
            trades=self._trades,
            equity_curve=self._equity_curve,
            drawdown_curve=self._calculate_drawdown_curve(),
            final_capital=self._capital,
            total_fees=sum(t.fee for t in self._trades),
            start_time=start_time.isoformat(),
            end_time=end_time.isoformat(),
            duration_seconds=duration,
            strategy_name=strategy_name,
            parameters=parameters or {}
        )

        # Save result
        self._save_result(result)

        logger.info(f"Backtest complete: Return={metrics.total_return_pct:.2f}%, "
                   f"Sharpe={metrics.sharpe_ratio:.2f}, MaxDD={metrics.max_drawdown:.2f}%")

        return result

    # Trading methods (called by strategy)

    def buy(self, size_fraction: float = 1.0, reason: str = ""):
        """Buy with fraction of available capital."""
        if self._position.side == PositionSide.LONG:
            return  # Already long

        price = self._get_execution_price(OrderSide.BUY)
        available = self._capital * min(size_fraction, self._config.max_position_size)
        quantity = available / price

        fee = available * self._config.fee_rate
        self._capital -= (available + fee)

        # Close short if exists
        pnl = 0
        if self._position.side == PositionSide.SHORT:
            pnl = self._position.unrealized_pnl
            self._capital += pnl

        # Open long
        self._position = BacktestPosition(
            side=PositionSide.LONG,
            quantity=quantity,
            entry_price=price,
            entry_time=self._current_candle.timestamp,
            current_price=price
        )

        self._record_trade(OrderSide.BUY, price, quantity, fee, pnl, reason)

    def sell(self, size_fraction: float = 1.0, reason: str = ""):
        """Sell position or go short."""
        if self._position.side == PositionSide.FLAT:
            if self._config.allow_short:
                self._open_short(size_fraction, reason)
            return

        if self._position.side == PositionSide.SHORT:
            return  # Already short

        # Close long
        self.close_position(reason)

    def sell_all(self, reason: str = ""):
        """Close all positions."""
        self.close_position(reason)

    def close_position(self, reason: str = ""):
        """Close current position."""
        if self._position.side == PositionSide.FLAT:
            return

        price = self._get_execution_price(
            OrderSide.SELL if self._position.side == PositionSide.LONG else OrderSide.BUY
        )

        value = self._position.quantity * price
        fee = value * self._config.fee_rate

        if self._position.side == PositionSide.LONG:
            pnl = (price - self._position.entry_price) * self._position.quantity
        else:
            pnl = (self._position.entry_price - price) * self._position.quantity

        # Sale/purchase proceeds already embed realized PnL via execution price.
        self._capital += value - fee

        side = OrderSide.SELL if self._position.side == PositionSide.LONG else OrderSide.BUY
        self._record_trade(side, price, self._position.quantity, fee, pnl, reason)

        self._position = BacktestPosition(
            side=PositionSide.FLAT,
            quantity=0,
            entry_price=0,
            entry_time=""
        )

    def _open_short(self, size_fraction: float, reason: str):
        """Open short position."""
        price = self._get_execution_price(OrderSide.SELL)
        size = self._capital * min(size_fraction, self._config.max_position_size)
        quantity = size / price

        fee = size * self._config.fee_rate
        self._capital -= fee

        self._position = BacktestPosition(
            side=PositionSide.SHORT,
            quantity=quantity,
            entry_price=price,
            entry_time=self._current_candle.timestamp,
            current_price=price
        )

        self._record_trade(OrderSide.SELL, price, quantity, fee, 0, reason)

    def _get_execution_price(self, side: OrderSide) -> float:
        """Get execution price with slippage."""
        price = self._current_candle.close
        slippage = price * (self._config.slippage_bps / 10000)

        if side == OrderSide.BUY:
            return price + slippage
        else:
            return price - slippage

    def _record_trade(
        self,
        side: OrderSide,
        price: float,
        quantity: float,
        fee: float,
        pnl: float,
        reason: str
    ):
        """Record a trade."""
        cumulative_pnl = sum(t.pnl for t in self._trades) + pnl

        trade = BacktestTrade(
            id=f"t_{len(self._trades) + 1}",
            timestamp=self._current_candle.timestamp,
            side=side,
            price=price,
            quantity=quantity,
            value=price * quantity,
            fee=fee,
            pnl=pnl,
            cumulative_pnl=cumulative_pnl,
            position_after=self._position.quantity if self._position.side != PositionSide.FLAT else 0,
            reason=reason
        )

        self._trades.append(trade)

    # Indicator methods (called by strategy)

    def close(self, lookback: int = 0) -> float:
        """Get closing price."""
        idx = self._current_idx - lookback
        candles = self._data.get(self._config.symbol.upper(), [])
        if 0 <= idx < len(candles):
            return candles[idx].close
        return 0

    def high(self, lookback: int = 0) -> float:
        """Get high price."""
        idx = self._current_idx - lookback
        candles = self._data.get(self._config.symbol.upper(), [])
        if 0 <= idx < len(candles):
            return candles[idx].high
        return 0

    def low(self, lookback: int = 0) -> float:
        """Get low price."""
        idx = self._current_idx - lookback
        candles = self._data.get(self._config.symbol.upper(), [])
        if 0 <= idx < len(candles):
            return candles[idx].low
        return 0

    def volume(self, lookback: int = 0) -> float:
        """Get volume."""
        idx = self._current_idx - lookback
        candles = self._data.get(self._config.symbol.upper(), [])
        if 0 <= idx < len(candles):
            return candles[idx].volume
        return 0

    def sma(self, period: int = 20) -> float:
        """Simple Moving Average."""
        closes = [self.close(i) for i in range(period)]
        return sum(closes) / len(closes) if closes else 0

    def ema(self, period: int = 20) -> float:
        """Exponential Moving Average."""
        candles = self._data.get(self._config.symbol.upper(), [])
        if not candles or self._current_idx < 0:
            return 0

        start_idx = max(0, self._current_idx - (period * 2) + 1)
        closes = [c.close for c in candles[start_idx:self._current_idx + 1]]
        if len(closes) < period:
            return 0

        multiplier = 2 / (period + 1)
        ema = sum(closes[:period]) / period

        for price in closes[period:]:
            ema = (price * multiplier) + (ema * (1 - multiplier))

        return ema

    def rsi(self, period: int = 14) -> float:
        """Relative Strength Index."""
        candles = self._data.get(self._config.symbol.upper(), [])
        if not candles or self._current_idx < 0:
            return 50

        start_idx = max(0, self._current_idx - period)
        closes = [c.close for c in candles[start_idx:self._current_idx + 1]]
        if len(closes) < period + 1:
            return 50

        gains = []
        losses = []

        for i in range(1, len(closes)):
            change = closes[i] - closes[i - 1]
            gains.append(max(change, 0))
            losses.append(abs(min(change, 0)))

        avg_gain = sum(gains[-period:]) / period
        avg_loss = sum(losses[-period:]) / period

        if avg_loss == 0:
            return 100

        rs = avg_gain / avg_loss
        return 100 - (100 / (1 + rs))

    def macd(self) -> Dict[str, float]:
        """MACD indicator."""
        fast_ema = self.ema(12)
        slow_ema = self.ema(26)
        macd_line = fast_ema - slow_ema
        signal = macd_line * 0.9  # Simplified
        return {
            'macd': macd_line,
            'signal': signal,
            'histogram': macd_line - signal
        }

    def bollinger_bands(self, period: int = 20, std_dev: float = 2) -> Dict[str, float]:
        """Bollinger Bands."""
        closes = [self.close(i) for i in range(period)]
        if not closes:
            return {'upper': 0, 'middle': 0, 'lower': 0}

        sma = sum(closes) / len(closes)
        variance = sum((p - sma) ** 2 for p in closes) / len(closes)
        std = math.sqrt(variance)

        return {
            'upper': sma + (std_dev * std),
            'middle': sma,
            'lower': sma - (std_dev * std)
        }

    def atr(self, period: int = 14) -> float:
        """Average True Range."""
        candles = self._data.get(self._config.symbol.upper(), [])
        idx = self._current_idx

        if idx < period:
            return 0

        true_ranges = []
        for i in range(idx - period, idx):
            if i > 0:
                current = candles[i]
                prev = candles[i - 1]
                tr = max(
                    current.high - current.low,
                    abs(current.high - prev.close),
                    abs(current.low - prev.close)
                )
                true_ranges.append(tr)

        return sum(true_ranges) / len(true_ranges) if true_ranges else 0

    # State accessors

    @property
    def position(self) -> BacktestPosition:
        """Get current position."""
        return self._position

    @property
    def capital(self) -> float:
        """Get current capital."""
        return self._capital

    @property
    def equity(self) -> float:
        """Get current equity (capital + unrealized PnL)."""
        return self._capital + self._position.unrealized_pnl

    def is_long(self) -> bool:
        """Check if currently long."""
        return self._position.side == PositionSide.LONG

    def is_short(self) -> bool:
        """Check if currently short."""
        return self._position.side == PositionSide.SHORT

    def is_flat(self) -> bool:
        """Check if no position."""
        return self._position.side == PositionSide.FLAT

    # Metrics calculation

    def _calculate_metrics(self) -> BacktestMetrics:
        """Calculate backtest performance metrics."""
        if not self._equity_curve:
            return BacktestMetrics(
                total_return=0, total_return_pct=0, annualized_return=0,
                sharpe_ratio=0, sortino_ratio=0, max_drawdown=0,
                max_drawdown_duration=0, win_rate=0, profit_factor=0,
                total_trades=0, winning_trades=0, losing_trades=0,
                avg_win=0, avg_loss=0, largest_win=0, largest_loss=0,
                avg_trade_duration=0, expectancy=0, calmar_ratio=0,
                volatility=0
            )

        initial = self._config.initial_capital
        final = self._capital
        total_return = final - initial
        total_return_pct = (total_return / initial) * 100

        # Calculate returns for Sharpe
        equities = [e['equity'] for e in self._equity_curve]
        returns = []
        for i in range(1, len(equities)):
            if equities[i - 1] > 0:
                returns.append((equities[i] - equities[i - 1]) / equities[i - 1])

        # Sharpe Ratio (annualized, assuming daily data)
        if returns:
            avg_return = sum(returns) / len(returns)
            std_return = math.sqrt(sum((r - avg_return) ** 2 for r in returns) / len(returns))
            sharpe_ratio = (avg_return / std_return) * math.sqrt(252) if std_return > 0 else 0
        else:
            sharpe_ratio = 0
            avg_return = 0
            std_return = 0

        # Sortino Ratio
        downside_returns = [r for r in returns if r < 0]
        if downside_returns:
            downside_std = math.sqrt(sum(r ** 2 for r in downside_returns) / len(downside_returns))
            sortino_ratio = (avg_return / downside_std) * math.sqrt(252) if downside_std > 0 else 0
        else:
            sortino_ratio = sharpe_ratio

        # Max Drawdown
        peak = equities[0]
        max_dd = 0
        max_dd_duration = 0
        current_dd_duration = 0

        for equity in equities:
            if equity > peak:
                peak = equity
                current_dd_duration = 0
            else:
                dd = (peak - equity) / peak
                max_dd = max(max_dd, dd)
                current_dd_duration += 1
                max_dd_duration = max(max_dd_duration, current_dd_duration)

        max_drawdown = max_dd * 100

        # Trade statistics
        total_trades = len(self._trades)
        winning_trades = len([t for t in self._trades if t.pnl > 0])
        losing_trades = len([t for t in self._trades if t.pnl < 0])

        win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0

        wins = [t.pnl for t in self._trades if t.pnl > 0]
        losses = [t.pnl for t in self._trades if t.pnl < 0]

        avg_win = sum(wins) / len(wins) if wins else 0
        avg_loss = sum(losses) / len(losses) if losses else 0
        largest_win = max(wins) if wins else 0
        largest_loss = min(losses) if losses else 0

        # Profit Factor
        gross_profit = sum(wins)
        gross_loss = abs(sum(losses))
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else 0

        # Expectancy
        expectancy = (win_rate / 100 * avg_win) + ((1 - win_rate / 100) * avg_loss)

        # Annualized return (assume 252 trading days)
        num_days = len(self._equity_curve)
        if num_days > 1:
            annualized_return = ((final / initial) ** (252 / num_days) - 1) * 100
        else:
            annualized_return = 0

        # Calmar Ratio
        calmar_ratio = annualized_return / max_drawdown if max_drawdown > 0 else 0

        return BacktestMetrics(
            total_return=total_return,
            total_return_pct=total_return_pct,
            annualized_return=annualized_return,
            sharpe_ratio=sharpe_ratio,
            sortino_ratio=sortino_ratio,
            max_drawdown=max_drawdown,
            max_drawdown_duration=max_dd_duration,
            win_rate=win_rate,
            profit_factor=profit_factor,
            total_trades=total_trades,
            winning_trades=winning_trades,
            losing_trades=losing_trades,
            avg_win=avg_win,
            avg_loss=avg_loss,
            largest_win=largest_win,
            largest_loss=largest_loss,
            avg_trade_duration=0,  # Would need position tracking
            expectancy=expectancy,
            calmar_ratio=calmar_ratio,
            volatility=std_return * math.sqrt(252) * 100 if returns else 0
        )

    def _calculate_drawdown_curve(self) -> List[Dict[str, float]]:
        """Calculate drawdown curve."""
        if not self._equity_curve:
            return []

        equities = [e['equity'] for e in self._equity_curve]
        timestamps = [e['timestamp'] for e in self._equity_curve]

        peak = equities[0]
        drawdowns = []

        for i, equity in enumerate(equities):
            if equity > peak:
                peak = equity
            dd = ((peak - equity) / peak) * 100
            drawdowns.append({
                'timestamp': timestamps[i],
                'drawdown': dd
            })

        return drawdowns

    def _save_result(self, result: BacktestResult):
        """Save backtest result to database."""
        with self.db._get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute("""
                INSERT INTO backtest_results
                (id, symbol, strategy_name, start_date, end_date, initial_capital,
                 final_capital, total_return_pct, sharpe_ratio, max_drawdown,
                 win_rate, total_trades, total_fees, parameters_json, metrics_json,
                 created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                result.id, result.config.symbol, result.strategy_name,
                result.config.start_date, result.config.end_date,
                result.config.initial_capital, result.final_capital,
                result.metrics.total_return_pct, result.metrics.sharpe_ratio,
                result.metrics.max_drawdown, result.metrics.win_rate,
                result.metrics.total_trades, result.total_fees,
                json.dumps(result.parameters),
                json.dumps({
                    'sharpe_ratio': result.metrics.sharpe_ratio,
                    'sortino_ratio': result.metrics.sortino_ratio,
                    'profit_factor': result.metrics.profit_factor,
                    'calmar_ratio': result.metrics.calmar_ratio,
                    'expectancy': result.metrics.expectancy
                }),
                datetime.now(timezone.utc).isoformat()
            ))

            # Save trades
            for trade in result.trades:
                cursor.execute("""
                    INSERT INTO backtest_trades
                    (backtest_id, trade_id, timestamp, side, price, quantity,
                     value, fee, pnl, cumulative_pnl, reason)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    result.id, trade.id, trade.timestamp, trade.side.value,
                    trade.price, trade.quantity, trade.value, trade.fee,
                    trade.pnl, trade.cumulative_pnl, trade.reason
                ))

            conn.commit()

    def get_result(self, backtest_id: str) -> Optional[Dict]:
        """Get backtest result by ID."""
        with self.db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM backtest_results WHERE id = ?", (backtest_id,))
            row = cursor.fetchone()
            if row:
                return dict(row)
        return None

    def get_results(
        self,
        symbol: Optional[str] = None,
        strategy: Optional[str] = None,
        limit: int = 50
    ) -> List[Dict]:
        """Get backtest results."""
        with self.db._get_connection() as conn:
            cursor = conn.cursor()

            query = "SELECT * FROM backtest_results WHERE 1=1"
            params = []

            if symbol:
                query += " AND symbol = ?"
                params.append(symbol.upper())

            if strategy:
                query += " AND strategy_name = ?"
                params.append(strategy)

            query += " ORDER BY created_at DESC LIMIT ?"
            params.append(limit)

            cursor.execute(query, params)

            return [dict(row) for row in cursor.fetchall()]


# Singleton
_engine: Optional[BacktestEngine] = None


def get_backtest_engine() -> BacktestEngine:
    """Get singleton backtest engine."""
    global _engine
    if _engine is None:
        _engine = BacktestEngine()
    return _engine
