"""
Advanced Backtesting Engine

Enhanced backtesting engine with:
- Comprehensive metrics (Sharpe, Sortino, Calmar, Recovery Factor)
- JSON/Text report generation
- Live vs backtest comparison
- OHLCV data management
"""

import json
import logging
import math
import uuid
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Any, Callable, Tuple

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
    volume: float = 0.0


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
    recovery_factor: float
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

    def to_json(self) -> Dict[str, Any]:
        """Convert result to JSON-serializable dictionary."""
        return {
            'id': self.id,
            'strategy_name': self.strategy_name,
            'parameters': self.parameters,
            'config': {
                'symbol': self.config.symbol,
                'start_date': self.config.start_date,
                'end_date': self.config.end_date,
                'initial_capital': self.config.initial_capital,
                'fee_rate': self.config.fee_rate,
            },
            'metrics': {
                'total_return': self.metrics.total_return,
                'total_return_pct': self.metrics.total_return_pct,
                'annualized_return': self.metrics.annualized_return,
                'sharpe_ratio': self.metrics.sharpe_ratio,
                'sortino_ratio': self.metrics.sortino_ratio,
                'max_drawdown': self.metrics.max_drawdown,
                'win_rate': self.metrics.win_rate,
                'profit_factor': self.metrics.profit_factor,
                'recovery_factor': self.metrics.recovery_factor,
                'total_trades': self.metrics.total_trades,
                'winning_trades': self.metrics.winning_trades,
                'losing_trades': self.metrics.losing_trades,
                'calmar_ratio': self.metrics.calmar_ratio,
                'expectancy': self.metrics.expectancy,
            },
            'trades': [
                {
                    'id': t.id,
                    'timestamp': t.timestamp,
                    'side': t.side.value,
                    'price': t.price,
                    'quantity': t.quantity,
                    'value': t.value,
                    'fee': t.fee,
                    'pnl': t.pnl,
                    'reason': t.reason,
                }
                for t in self.trades
            ],
            'equity_curve': self.equity_curve,
            'final_capital': self.final_capital,
            'total_fees': self.total_fees,
            'start_time': self.start_time,
            'end_time': self.end_time,
            'duration_seconds': self.duration_seconds,
        }

    def to_text(self) -> str:
        """Generate text report."""
        return f"""
BACKTEST REPORT: {self.strategy_name}
{'=' * 60}

CONFIGURATION:
  Symbol: {self.config.symbol}
  Period: {self.config.start_date} to {self.config.end_date}
  Initial Capital: ${self.config.initial_capital:,.2f}
  Fee Rate: {self.config.fee_rate * 100:.2f}%

PERFORMANCE:
  Total Return: ${self.metrics.total_return:+,.2f} ({self.metrics.total_return_pct:+.2f}%)
  Annualized Return: {self.metrics.annualized_return:+.2f}%
  Final Capital: ${self.final_capital:,.2f}

RISK METRICS:
  Sharpe Ratio: {self.metrics.sharpe_ratio:.2f}
  Sortino Ratio: {self.metrics.sortino_ratio:.2f}
  Calmar Ratio: {self.metrics.calmar_ratio:.2f}
  Max Drawdown: {self.metrics.max_drawdown:.2f}%
  Recovery Factor: {self.metrics.recovery_factor:.2f}

TRADE STATISTICS:
  Total Trades: {self.metrics.total_trades}
  Winning Trades: {self.metrics.winning_trades}
  Losing Trades: {self.metrics.losing_trades}
  Win Rate: {self.metrics.win_rate:.1f}%
  Profit Factor: {self.metrics.profit_factor:.2f}
  Expectancy: ${self.metrics.expectancy:.2f}

  Avg Win: ${self.metrics.avg_win:+.2f}
  Avg Loss: ${self.metrics.avg_loss:+.2f}
  Largest Win: ${self.metrics.largest_win:+.2f}
  Largest Loss: ${self.metrics.largest_loss:+.2f}

EXECUTION:
  Total Fees Paid: ${self.total_fees:,.2f}
  Backtest Duration: {self.duration_seconds:.2f}s
"""


class AdvancedBacktestEngine:
    """
    Advanced historical backtesting engine.

    Features:
    - Comprehensive performance metrics
    - Technical indicators (SMA, EMA, RSI, MACD, Bollinger Bands, ATR)
    - Position management
    - Report generation (JSON, text)
    - Live vs backtest comparison
    """

    def __init__(self, results_dir: Optional[Path] = None):
        self.results_dir = results_dir or Path(__file__).parent.parent.parent / "data" / "backtests"
        self.results_dir.mkdir(parents=True, exist_ok=True)

        # Data storage
        self._data: Dict[str, List[OHLCV]] = {}

        # State during backtest
        self._config: Optional[BacktestConfig] = None
        self._capital: float = 0
        self._position: BacktestPosition = None
        self._trades: List[BacktestTrade] = []
        self._equity_curve: List[Dict] = []
        self._current_idx: int = 0
        self._current_candle: Optional[OHLCV] = None
        self._all_candles: List[OHLCV] = []

    def load_data(self, symbol: str, data: List[Dict]) -> None:
        """Load historical OHLCV data."""
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
        self._data[symbol.upper()] = sorted(candles, key=lambda c: c.timestamp)
        logger.info(f"Loaded {len(candles)} candles for {symbol}")

    def has_data(self, symbol: str) -> bool:
        """Check if data is loaded for symbol."""
        return symbol.upper() in self._data

    def get_data(self, symbol: str) -> List[OHLCV]:
        """Get loaded data for symbol."""
        return self._data.get(symbol.upper(), [])

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

        # Validate data exists
        if not self.has_data(config.symbol):
            raise ValueError(f"No data loaded for {config.symbol}")

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

        # Get and filter data
        candles = self._data.get(config.symbol.upper(), [])
        filtered_candles = [
            c for c in candles
            if config.start_date <= c.timestamp[:10] <= config.end_date
        ]

        if not filtered_candles:
            raise ValueError("No data in specified date range")

        self._all_candles = filtered_candles
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

        logger.info(f"Backtest complete: Return={metrics.total_return_pct:.2f}%, "
                   f"Sharpe={metrics.sharpe_ratio:.2f}, MaxDD={metrics.max_drawdown:.2f}%")

        return result

    # Trading methods (called by strategy)

    def buy(self, size_fraction: float = 1.0, reason: str = "") -> None:
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

    def sell(self, size_fraction: float = 1.0, reason: str = "") -> None:
        """Sell position or go short."""
        if self._position.side == PositionSide.FLAT:
            if self._config.allow_short:
                self._open_short(size_fraction, reason)
            return

        if self._position.side == PositionSide.SHORT:
            return  # Already short

        # Close long
        self.close_position(reason)

    def sell_all(self, reason: str = "") -> None:
        """Close all positions."""
        self.close_position(reason)

    def close_position(self, reason: str = "") -> None:
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

        # Add back the value (sale proceeds) minus fees
        # Note: pnl is already reflected in value since value = quantity * exit_price
        self._capital += value - fee

        side = OrderSide.SELL if self._position.side == PositionSide.LONG else OrderSide.BUY
        self._record_trade(side, price, self._position.quantity, fee, pnl, reason)

        self._position = BacktestPosition(
            side=PositionSide.FLAT,
            quantity=0,
            entry_price=0,
            entry_time=""
        )

    def _open_short(self, size_fraction: float, reason: str) -> None:
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
    ) -> None:
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
        if 0 <= idx < len(self._all_candles):
            return self._all_candles[idx].close
        return 0

    def high(self, lookback: int = 0) -> float:
        """Get high price."""
        idx = self._current_idx - lookback
        if 0 <= idx < len(self._all_candles):
            return self._all_candles[idx].high
        return 0

    def low(self, lookback: int = 0) -> float:
        """Get low price."""
        idx = self._current_idx - lookback
        if 0 <= idx < len(self._all_candles):
            return self._all_candles[idx].low
        return 0

    def volume(self, lookback: int = 0) -> float:
        """Get volume."""
        idx = self._current_idx - lookback
        if 0 <= idx < len(self._all_candles):
            return self._all_candles[idx].volume
        return 0

    def sma(self, period: int = 20) -> float:
        """Simple Moving Average."""
        if self._current_idx < period - 1:
            return self.close()
        closes = [self.close(i) for i in range(period)]
        return sum(closes) / len(closes) if closes else 0

    def ema(self, period: int = 20) -> float:
        """Exponential Moving Average."""
        closes = [self.close(i) for i in range(min(period * 2, self._current_idx + 1))][::-1]
        if len(closes) < period:
            return sum(closes) / len(closes) if closes else 0

        multiplier = 2 / (period + 1)
        ema = sum(closes[:period]) / period

        for price in closes[period:]:
            ema = (price * multiplier) + (ema * (1 - multiplier))

        return ema

    def rsi(self, period: int = 14) -> float:
        """Relative Strength Index."""
        if self._current_idx < period:
            return 50

        closes = [self.close(i) for i in range(period + 1)][::-1]
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
        signal = macd_line * 0.9  # Simplified signal
        return {
            'macd': macd_line,
            'signal': signal,
            'histogram': macd_line - signal
        }

    def bollinger_bands(self, period: int = 20, std_dev: float = 2) -> Dict[str, float]:
        """Bollinger Bands."""
        closes = [self.close(i) for i in range(min(period, self._current_idx + 1))]
        if not closes:
            return {'upper': 0, 'middle': 0, 'lower': 0}

        sma = sum(closes) / len(closes)
        if len(closes) < 2:
            return {'upper': sma, 'middle': sma, 'lower': sma}

        variance = sum((p - sma) ** 2 for p in closes) / len(closes)
        std = math.sqrt(variance)

        return {
            'upper': sma + (std_dev * std),
            'middle': sma,
            'lower': sma - (std_dev * std)
        }

    def atr(self, period: int = 14) -> float:
        """Average True Range."""
        if self._current_idx < period:
            return 0

        true_ranges = []
        for i in range(period):
            idx = self._current_idx - i
            if idx > 0:
                current = self._all_candles[idx]
                prev = self._all_candles[idx - 1]
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
            return self._empty_metrics()

        initial = self._config.initial_capital
        final = self._capital
        total_return = final - initial
        total_return_pct = (total_return / initial) * 100 if initial else 0

        # Calculate returns for risk metrics
        equities = [e['equity'] for e in self._equity_curve]
        returns = []
        for i in range(1, len(equities)):
            if equities[i - 1] > 0:
                returns.append((equities[i] - equities[i - 1]) / equities[i - 1])

        # Sharpe Ratio (annualized, assuming daily data)
        if returns and len(returns) > 1:
            avg_return = sum(returns) / len(returns)
            std_return = math.sqrt(sum((r - avg_return) ** 2 for r in returns) / len(returns))
            sharpe_ratio = (avg_return / std_return) * math.sqrt(252) if std_return > 0 else 0
        else:
            sharpe_ratio = 0
            avg_return = 0
            std_return = 0

        # Sortino Ratio
        downside_returns = [r for r in returns if r < 0]
        if downside_returns and len(downside_returns) > 0:
            downside_std = math.sqrt(sum(r ** 2 for r in downside_returns) / len(downside_returns))
            sortino_ratio = (avg_return / downside_std) * math.sqrt(252) if downside_std > 0 else 0
        else:
            sortino_ratio = sharpe_ratio if sharpe_ratio else 0

        # Max Drawdown
        peak = equities[0] if equities else initial
        max_dd = 0
        max_dd_duration = 0
        current_dd_duration = 0

        for equity in equities:
            if equity > peak:
                peak = equity
                current_dd_duration = 0
            else:
                dd = (peak - equity) / peak if peak > 0 else 0
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
        gross_profit = sum(wins) if wins else 0
        gross_loss = abs(sum(losses)) if losses else 0
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else (float('inf') if gross_profit > 0 else 0)

        # Recovery Factor: Total Return / Max Drawdown
        recovery_factor = abs(total_return_pct / max_drawdown) if max_drawdown > 0 else 0

        # Expectancy
        if total_trades > 0:
            expectancy = (win_rate / 100 * avg_win) + ((1 - win_rate / 100) * avg_loss)
        else:
            expectancy = 0

        # Annualized return
        num_days = len(self._equity_curve)
        if num_days > 1 and final > 0 and initial > 0:
            annualized_return = ((final / initial) ** (252 / num_days) - 1) * 100
        else:
            annualized_return = 0

        # Calmar Ratio
        calmar_ratio = annualized_return / max_drawdown if max_drawdown > 0 else 0

        # Volatility
        volatility = std_return * math.sqrt(252) * 100 if returns else 0

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
            recovery_factor=recovery_factor,
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
            volatility=volatility
        )

    def _empty_metrics(self) -> BacktestMetrics:
        """Return empty metrics."""
        return BacktestMetrics(
            total_return=0, total_return_pct=0, annualized_return=0,
            sharpe_ratio=0, sortino_ratio=0, max_drawdown=0,
            max_drawdown_duration=0, win_rate=0, profit_factor=0,
            recovery_factor=0, total_trades=0, winning_trades=0,
            losing_trades=0, avg_win=0, avg_loss=0, largest_win=0,
            largest_loss=0, avg_trade_duration=0, expectancy=0,
            calmar_ratio=0, volatility=0
        )

    def _calculate_drawdown_curve(self) -> List[Dict[str, float]]:
        """Calculate drawdown curve."""
        if not self._equity_curve:
            return []

        equities = [e['equity'] for e in self._equity_curve]
        timestamps = [e['timestamp'] for e in self._equity_curve]

        peak = equities[0] if equities else 0
        drawdowns = []

        for i, equity in enumerate(equities):
            if equity > peak:
                peak = equity
            dd = ((peak - equity) / peak * 100) if peak > 0 else 0
            drawdowns.append({
                'timestamp': timestamps[i],
                'drawdown': dd
            })

        return drawdowns

    def compare_with_live(
        self,
        backtest_result: BacktestResult,
        live_trades: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Compare backtest results with live trading performance."""
        # Calculate live performance
        live_pnl = sum(t.get('pnl', 0) for t in live_trades)
        initial_capital = backtest_result.config.initial_capital
        live_return = (live_pnl / initial_capital * 100) if initial_capital else 0

        backtest_return = backtest_result.metrics.total_return_pct

        deviation = backtest_return - live_return

        return {
            'backtest_return': backtest_return,
            'live_return': live_return,
            'deviation': deviation,
            'deviation_pct': (deviation / abs(backtest_return) * 100) if backtest_return else 0,
            'backtest_trades': backtest_result.metrics.total_trades,
            'live_trades': len(live_trades),
            'backtest_win_rate': backtest_result.metrics.win_rate,
            'live_win_rate': (
                len([t for t in live_trades if t.get('pnl', 0) > 0]) / len(live_trades) * 100
                if live_trades else 0
            ),
        }

    def save_result(self, result: BacktestResult, filename: str = None) -> Path:
        """Save backtest result to JSON file."""
        if filename is None:
            filename = f"backtest_{result.id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

        filepath = self.results_dir / filename

        with open(filepath, 'w') as f:
            json.dump(result.to_json(), f, indent=2)

        logger.info(f"Saved backtest result to {filepath}")
        return filepath
