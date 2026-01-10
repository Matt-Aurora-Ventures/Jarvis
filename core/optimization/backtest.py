"""
Backtesting Engine
Prompt #92: Historical backtesting for strategy evaluation

Provides backtesting capabilities for strategy optimization.
"""

import logging
import os
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict, List, Optional, Tuple
import statistics
import json

logger = logging.getLogger("jarvis.optimization.backtest")


# =============================================================================
# MODELS
# =============================================================================

@dataclass
class Trade:
    """A simulated trade"""
    timestamp: datetime
    side: str  # "buy" or "sell"
    price: float
    amount: float
    fee: float = 0.0
    pnl: float = 0.0
    pnl_pct: float = 0.0
    hold_duration: float = 0.0


@dataclass
class Position:
    """Current position state"""
    token: str
    entry_price: float
    entry_time: datetime
    amount: float
    side: str
    unrealized_pnl: float = 0.0


@dataclass
class BacktestResult:
    """Complete backtest results"""
    strategy_name: str
    parameters: Dict[str, Any]
    start_date: datetime
    end_date: datetime
    initial_capital: float
    final_capital: float
    total_return: float
    total_return_pct: float
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    avg_win: float
    avg_loss: float
    profit_factor: float
    max_drawdown: float
    max_drawdown_pct: float
    sharpe_ratio: float
    sortino_ratio: float
    calmar_ratio: float
    avg_trade_duration: float
    trades: List[Trade] = field(default_factory=list)
    equity_curve: List[Tuple[datetime, float]] = field(default_factory=list)


@dataclass
class WalkForwardResult:
    """Walk-forward optimization result"""
    in_sample_results: List[BacktestResult]
    out_sample_results: List[BacktestResult]
    best_parameters: Dict[str, Any]
    overall_performance: Dict[str, float]


# =============================================================================
# BACKTESTER
# =============================================================================

class Backtester:
    """
    Backtesting engine for strategy evaluation.

    Features:
    - Historical simulation with realistic constraints
    - Multiple performance metrics
    - Walk-forward optimization
    - Equity curve analysis
    """

    # Default configuration
    DEFAULT_INITIAL_CAPITAL = 10.0  # SOL
    DEFAULT_TRADING_FEE = 0.001  # 0.1%
    DEFAULT_SLIPPAGE = 0.002  # 0.2%

    def __init__(
        self,
        initial_capital: float = None,
        trading_fee: float = None,
        slippage: float = None,
    ):
        self.initial_capital = initial_capital or self.DEFAULT_INITIAL_CAPITAL
        self.trading_fee = trading_fee or self.DEFAULT_TRADING_FEE
        self.slippage = slippage or self.DEFAULT_SLIPPAGE

    # =========================================================================
    # BACKTESTING
    # =========================================================================

    async def run(
        self,
        strategy_func: Callable,
        parameters: Dict[str, Any],
        price_data: List[Dict[str, Any]],
        strategy_name: str = "unknown",
    ) -> BacktestResult:
        """
        Run a backtest with given strategy and parameters.

        Args:
            strategy_func: Strategy function (price_data, params) -> signals
            parameters: Strategy parameters
            price_data: Historical price data
            strategy_name: Name of strategy

        Returns:
            BacktestResult with performance metrics
        """
        if not price_data:
            return self._empty_result(strategy_name, parameters)

        # Initialize state
        capital = self.initial_capital
        position: Optional[Position] = None
        trades: List[Trade] = []
        equity_curve: List[Tuple[datetime, float]] = []
        peak_equity = capital

        # Sort price data by time
        sorted_data = sorted(price_data, key=lambda x: x.get("timestamp", ""))

        # Get start and end dates
        start_date = self._parse_timestamp(sorted_data[0].get("timestamp"))
        end_date = self._parse_timestamp(sorted_data[-1].get("timestamp"))

        # Generate signals
        try:
            signals = await strategy_func(sorted_data, parameters)
        except Exception as e:
            logger.error(f"Strategy error: {e}")
            return self._empty_result(strategy_name, parameters)

        # Execute trades
        for i, data_point in enumerate(sorted_data):
            timestamp = self._parse_timestamp(data_point.get("timestamp"))
            price = data_point.get("price", 0)

            if price <= 0:
                continue

            # Get signal for this point
            signal = signals.get(i) if isinstance(signals, dict) else (
                signals[i] if i < len(signals) else None
            )

            # Process signal
            if signal:
                action = signal.get("action")
                size = signal.get("size", 1.0)

                if action == "buy" and position is None:
                    # Open long position
                    adjusted_price = price * (1 + self.slippage)
                    fee = capital * size * self.trading_fee
                    amount = (capital * size - fee) / adjusted_price

                    position = Position(
                        token=data_point.get("token", "unknown"),
                        entry_price=adjusted_price,
                        entry_time=timestamp,
                        amount=amount,
                        side="long",
                    )

                    capital -= fee

                elif action == "sell" and position is not None:
                    # Close position
                    adjusted_price = price * (1 - self.slippage)
                    exit_value = position.amount * adjusted_price
                    fee = exit_value * self.trading_fee
                    exit_value -= fee

                    entry_value = position.amount * position.entry_price
                    pnl = exit_value - entry_value
                    pnl_pct = (pnl / entry_value) * 100 if entry_value > 0 else 0

                    hold_duration = (timestamp - position.entry_time).total_seconds()

                    trades.append(Trade(
                        timestamp=timestamp,
                        side="sell",
                        price=adjusted_price,
                        amount=position.amount,
                        fee=fee,
                        pnl=pnl,
                        pnl_pct=pnl_pct,
                        hold_duration=hold_duration,
                    ))

                    capital += exit_value
                    position = None

            # Update equity curve
            current_equity = capital
            if position:
                current_equity += position.amount * price

            equity_curve.append((timestamp, current_equity))

            # Track peak for drawdown
            if current_equity > peak_equity:
                peak_equity = current_equity

        # Close any remaining position at last price
        if position and sorted_data:
            last_price = sorted_data[-1].get("price", 0)
            if last_price > 0:
                exit_value = position.amount * last_price * (1 - self.slippage)
                fee = exit_value * self.trading_fee
                exit_value -= fee
                capital += exit_value

        # Calculate metrics
        return self._calculate_metrics(
            strategy_name=strategy_name,
            parameters=parameters,
            start_date=start_date,
            end_date=end_date,
            initial_capital=self.initial_capital,
            final_capital=capital,
            trades=trades,
            equity_curve=equity_curve,
        )

    async def run_walk_forward(
        self,
        strategy_func: Callable,
        parameter_space: Any,
        price_data: List[Dict[str, Any]],
        n_splits: int = 5,
        train_ratio: float = 0.7,
        n_trials: int = 50,
    ) -> WalkForwardResult:
        """
        Run walk-forward optimization.

        Args:
            strategy_func: Strategy function
            parameter_space: Parameter space to optimize
            price_data: Historical price data
            n_splits: Number of train/test splits
            train_ratio: Ratio of data for training
            n_trials: Number of optimization trials per split

        Returns:
            WalkForwardResult with in/out sample performance
        """
        # Sort data by time
        sorted_data = sorted(price_data, key=lambda x: x.get("timestamp", ""))
        n_samples = len(sorted_data)

        if n_samples < 100:
            logger.warning("Insufficient data for walk-forward optimization")
            return WalkForwardResult(
                in_sample_results=[],
                out_sample_results=[],
                best_parameters={},
                overall_performance={},
            )

        split_size = n_samples // n_splits
        in_sample_results = []
        out_sample_results = []
        all_best_params = []

        for i in range(n_splits):
            start_idx = i * split_size
            end_idx = min((i + 2) * split_size, n_samples)

            split_data = sorted_data[start_idx:end_idx]
            train_size = int(len(split_data) * train_ratio)

            train_data = split_data[:train_size]
            test_data = split_data[train_size:]

            # Optimize on training data
            best_result = None
            best_params = None

            for _ in range(n_trials):
                params = parameter_space.sample()

                result = await self.run(
                    strategy_func=strategy_func,
                    parameters=params,
                    price_data=train_data,
                )

                if best_result is None or result.sharpe_ratio > best_result.sharpe_ratio:
                    best_result = result
                    best_params = params

            if best_result:
                in_sample_results.append(best_result)
                all_best_params.append(best_params)

                # Test on out-of-sample data
                test_result = await self.run(
                    strategy_func=strategy_func,
                    parameters=best_params,
                    price_data=test_data,
                )
                out_sample_results.append(test_result)

        # Aggregate best parameters
        best_parameters = self._aggregate_parameters(all_best_params)

        # Calculate overall performance
        overall_performance = self._calculate_overall_performance(
            in_sample_results, out_sample_results
        )

        return WalkForwardResult(
            in_sample_results=in_sample_results,
            out_sample_results=out_sample_results,
            best_parameters=best_parameters,
            overall_performance=overall_performance,
        )

    # =========================================================================
    # METRICS CALCULATION
    # =========================================================================

    def _calculate_metrics(
        self,
        strategy_name: str,
        parameters: Dict[str, Any],
        start_date: datetime,
        end_date: datetime,
        initial_capital: float,
        final_capital: float,
        trades: List[Trade],
        equity_curve: List[Tuple[datetime, float]],
    ) -> BacktestResult:
        """Calculate all performance metrics"""
        total_return = final_capital - initial_capital
        total_return_pct = (total_return / initial_capital) * 100 if initial_capital > 0 else 0

        # Win/loss analysis
        wins = [t for t in trades if t.pnl > 0]
        losses = [t for t in trades if t.pnl < 0]

        winning_trades = len(wins)
        losing_trades = len(losses)
        total_trades = len(trades)

        win_rate = winning_trades / total_trades if total_trades > 0 else 0
        avg_win = statistics.mean([t.pnl for t in wins]) if wins else 0
        avg_loss = abs(statistics.mean([t.pnl for t in losses])) if losses else 0

        # Profit factor
        total_wins = sum(t.pnl for t in wins) if wins else 0
        total_losses = abs(sum(t.pnl for t in losses)) if losses else 0
        profit_factor = total_wins / total_losses if total_losses > 0 else float('inf')

        # Drawdown analysis
        max_drawdown, max_drawdown_pct = self._calculate_drawdown(equity_curve)

        # Risk-adjusted returns
        returns = [t.pnl_pct for t in trades]
        sharpe_ratio = self._calculate_sharpe(returns)
        sortino_ratio = self._calculate_sortino(returns)

        # Calmar ratio
        years = (end_date - start_date).days / 365.25 if end_date > start_date else 1
        annual_return = total_return_pct / years if years > 0 else 0
        calmar_ratio = annual_return / max_drawdown_pct if max_drawdown_pct > 0 else 0

        # Average trade duration
        avg_duration = statistics.mean([t.hold_duration for t in trades]) if trades else 0

        return BacktestResult(
            strategy_name=strategy_name,
            parameters=parameters,
            start_date=start_date,
            end_date=end_date,
            initial_capital=initial_capital,
            final_capital=final_capital,
            total_return=total_return,
            total_return_pct=total_return_pct,
            total_trades=total_trades,
            winning_trades=winning_trades,
            losing_trades=losing_trades,
            win_rate=win_rate,
            avg_win=avg_win,
            avg_loss=avg_loss,
            profit_factor=profit_factor,
            max_drawdown=max_drawdown,
            max_drawdown_pct=max_drawdown_pct,
            sharpe_ratio=sharpe_ratio,
            sortino_ratio=sortino_ratio,
            calmar_ratio=calmar_ratio,
            avg_trade_duration=avg_duration,
            trades=trades,
            equity_curve=equity_curve,
        )

    def _calculate_drawdown(
        self,
        equity_curve: List[Tuple[datetime, float]],
    ) -> Tuple[float, float]:
        """Calculate maximum drawdown"""
        if not equity_curve:
            return 0.0, 0.0

        peak = equity_curve[0][1]
        max_dd = 0.0
        max_dd_pct = 0.0

        for _, equity in equity_curve:
            if equity > peak:
                peak = equity
            else:
                dd = peak - equity
                dd_pct = (dd / peak) * 100 if peak > 0 else 0

                if dd > max_dd:
                    max_dd = dd
                    max_dd_pct = dd_pct

        return max_dd, max_dd_pct

    def _calculate_sharpe(self, returns: List[float], risk_free_rate: float = 0) -> float:
        """Calculate Sharpe ratio"""
        if len(returns) < 2:
            return 0.0

        excess_returns = [r - risk_free_rate for r in returns]
        avg_return = statistics.mean(excess_returns)
        std_dev = statistics.stdev(excess_returns)

        return avg_return / std_dev if std_dev > 0 else 0

    def _calculate_sortino(self, returns: List[float], risk_free_rate: float = 0) -> float:
        """Calculate Sortino ratio (downside deviation)"""
        if len(returns) < 2:
            return 0.0

        excess_returns = [r - risk_free_rate for r in returns]
        avg_return = statistics.mean(excess_returns)

        # Downside deviation
        negative_returns = [r for r in excess_returns if r < 0]
        if not negative_returns:
            return float('inf') if avg_return > 0 else 0

        downside_dev = statistics.stdev(negative_returns) if len(negative_returns) > 1 else abs(negative_returns[0])

        return avg_return / downside_dev if downside_dev > 0 else 0

    # =========================================================================
    # HELPERS
    # =========================================================================

    def _empty_result(
        self,
        strategy_name: str,
        parameters: Dict[str, Any],
    ) -> BacktestResult:
        """Return empty result for failed backtests"""
        now = datetime.now(timezone.utc)
        return BacktestResult(
            strategy_name=strategy_name,
            parameters=parameters,
            start_date=now,
            end_date=now,
            initial_capital=self.initial_capital,
            final_capital=self.initial_capital,
            total_return=0,
            total_return_pct=0,
            total_trades=0,
            winning_trades=0,
            losing_trades=0,
            win_rate=0,
            avg_win=0,
            avg_loss=0,
            profit_factor=0,
            max_drawdown=0,
            max_drawdown_pct=0,
            sharpe_ratio=0,
            sortino_ratio=0,
            calmar_ratio=0,
            avg_trade_duration=0,
        )

    def _parse_timestamp(self, ts: Any) -> datetime:
        """Parse various timestamp formats"""
        if isinstance(ts, datetime):
            return ts
        if isinstance(ts, str):
            try:
                return datetime.fromisoformat(ts.replace("Z", "+00:00"))
            except ValueError:
                pass
        return datetime.now(timezone.utc)

    def _aggregate_parameters(
        self,
        params_list: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Aggregate parameters from multiple optimizations"""
        if not params_list:
            return {}

        aggregated = {}
        all_keys = set()
        for params in params_list:
            all_keys.update(params.keys())

        for key in all_keys:
            values = [p.get(key) for p in params_list if key in p]
            if not values:
                continue

            # Average for numeric, mode for categorical
            if all(isinstance(v, (int, float)) for v in values):
                aggregated[key] = statistics.mean(values)
            else:
                # Most common value
                from collections import Counter
                counter = Counter(values)
                aggregated[key] = counter.most_common(1)[0][0]

        return aggregated

    def _calculate_overall_performance(
        self,
        in_sample: List[BacktestResult],
        out_sample: List[BacktestResult],
    ) -> Dict[str, float]:
        """Calculate overall walk-forward performance"""
        if not out_sample:
            return {}

        return {
            "avg_in_sample_return": statistics.mean([r.total_return_pct for r in in_sample]) if in_sample else 0,
            "avg_out_sample_return": statistics.mean([r.total_return_pct for r in out_sample]),
            "avg_in_sample_sharpe": statistics.mean([r.sharpe_ratio for r in in_sample]) if in_sample else 0,
            "avg_out_sample_sharpe": statistics.mean([r.sharpe_ratio for r in out_sample]),
            "consistency_ratio": (
                statistics.mean([r.total_return_pct for r in out_sample]) /
                statistics.mean([r.total_return_pct for r in in_sample])
                if in_sample and statistics.mean([r.total_return_pct for r in in_sample]) != 0
                else 0
            ),
            "total_out_sample_trades": sum(r.total_trades for r in out_sample),
        }
