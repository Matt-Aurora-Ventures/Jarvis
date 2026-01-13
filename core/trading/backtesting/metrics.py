"""
Performance Metrics Module

Calculates key trading performance metrics:
- Sharpe Ratio: Return / Total Volatility (target > 1.0)
- Sortino Ratio: Return / Downside Volatility (target > 2.0, better for crypto)
- Calmar Ratio: CAGR / Max Drawdown (target > 1.0)
- Profit Factor, Expectancy, Win Rate, etc.
"""

import math
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Dict, Any, Optional
import statistics

logger = logging.getLogger(__name__)


@dataclass
class Trade:
    """Record of a single trade."""
    entry_time: datetime
    exit_time: datetime
    entry_price: float
    exit_price: float
    direction: str  # 'long' or 'short'
    size: float
    pnl: float
    pnl_pct: float
    fees: float = 0.0

    @property
    def hold_time_hours(self) -> float:
        return (self.exit_time - self.entry_time).total_seconds() / 3600

    @property
    def is_winner(self) -> bool:
        return self.pnl > 0


@dataclass
class PerformanceMetrics:
    """
    Comprehensive performance metrics for a strategy.
    """
    # Return metrics
    total_return_pct: float = 0.0
    cagr: float = 0.0
    avg_return_per_trade: float = 0.0

    # Risk metrics
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    calmar_ratio: float = 0.0
    max_drawdown_pct: float = 0.0
    max_drawdown_duration_days: int = 0

    # Trade metrics
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    win_rate: float = 0.0
    profit_factor: float = 0.0
    expectancy: float = 0.0
    avg_win: float = 0.0
    avg_loss: float = 0.0
    best_trade: float = 0.0
    worst_trade: float = 0.0

    # Time metrics
    avg_hold_time_hours: float = 0.0
    exposure_time_pct: float = 0.0
    trading_days: int = 0

    # Additional
    sqn: float = 0.0  # System Quality Number
    volatility_annual: float = 0.0

    # Thresholds for validation
    @property
    def is_valid_strategy(self) -> bool:
        """Check if strategy meets minimum criteria."""
        return (
            self.sharpe_ratio >= 1.0 and
            self.sortino_ratio >= 2.0 and
            self.calmar_ratio >= 1.0 and
            self.max_drawdown_pct <= 50.0 and
            self.profit_factor >= 1.5
        )

    @property
    def risk_grade(self) -> str:
        """Grade the strategy's risk profile."""
        if self.max_drawdown_pct <= 15:
            return "A"
        elif self.max_drawdown_pct <= 25:
            return "B"
        elif self.max_drawdown_pct <= 40:
            return "C"
        elif self.max_drawdown_pct <= 50:
            return "D"
        else:
            return "F"

    def to_dict(self) -> Dict[str, Any]:
        return {
            'total_return_pct': self.total_return_pct,
            'cagr': self.cagr,
            'sharpe_ratio': self.sharpe_ratio,
            'sortino_ratio': self.sortino_ratio,
            'calmar_ratio': self.calmar_ratio,
            'max_drawdown_pct': self.max_drawdown_pct,
            'total_trades': self.total_trades,
            'win_rate': self.win_rate,
            'profit_factor': self.profit_factor,
            'expectancy': self.expectancy,
            'sqn': self.sqn,
            'is_valid': self.is_valid_strategy,
            'risk_grade': self.risk_grade,
        }


def calculate_sharpe(
    returns: List[float],
    risk_free_rate: float = 0.0,
    periods_per_year: int = 252,
) -> float:
    """
    Calculate Sharpe Ratio.

    Sharpe = (Mean Return - Risk Free Rate) / Std Dev of Returns

    Args:
        returns: List of period returns (e.g., daily returns)
        risk_free_rate: Annual risk-free rate (default 0)
        periods_per_year: Number of periods per year (252 for daily)

    Returns:
        Annualized Sharpe Ratio
    """
    if len(returns) < 2:
        return 0.0

    mean_return = statistics.mean(returns)
    std_dev = statistics.stdev(returns)

    if std_dev == 0:
        return 0.0

    # Convert risk-free rate to per-period
    rf_per_period = risk_free_rate / periods_per_year

    sharpe = (mean_return - rf_per_period) / std_dev

    # Annualize
    return sharpe * math.sqrt(periods_per_year)


def calculate_sortino(
    returns: List[float],
    target_return: float = 0.0,
    periods_per_year: int = 252,
) -> float:
    """
    Calculate Sortino Ratio.

    Sortino = (Mean Return - Target) / Downside Deviation

    Better than Sharpe for crypto as it only penalizes downside volatility,
    not the large upside moves that are normal in crypto.

    Args:
        returns: List of period returns
        target_return: Target return (default 0)
        periods_per_year: Number of periods per year

    Returns:
        Annualized Sortino Ratio
    """
    if len(returns) < 2:
        return 0.0

    mean_return = statistics.mean(returns)

    # Calculate downside deviation (only negative returns)
    downside_returns = [min(0, r - target_return) for r in returns]
    downside_variance = sum(r ** 2 for r in downside_returns) / len(downside_returns)
    downside_std = math.sqrt(downside_variance)

    if downside_std == 0:
        return float('inf') if mean_return > target_return else 0.0

    sortino = (mean_return - target_return) / downside_std

    # Annualize
    return sortino * math.sqrt(periods_per_year)


def calculate_calmar(
    total_return: float,
    max_drawdown: float,
    years: float,
) -> float:
    """
    Calculate Calmar Ratio.

    Calmar = CAGR / Max Drawdown

    Measures return efficiency relative to worst drawdown.

    Args:
        total_return: Total return as decimal (e.g., 1.5 for 150%)
        max_drawdown: Maximum drawdown as positive decimal (e.g., 0.25 for 25%)
        years: Number of years

    Returns:
        Calmar Ratio
    """
    if max_drawdown == 0 or years <= 0:
        return 0.0

    # Calculate CAGR
    cagr = (1 + total_return) ** (1 / years) - 1

    return cagr / max_drawdown


def calculate_max_drawdown(equity_curve: List[float]) -> tuple[float, int]:
    """
    Calculate maximum drawdown and duration.

    Args:
        equity_curve: List of equity values over time

    Returns:
        Tuple of (max_drawdown_pct, max_duration_periods)
    """
    if len(equity_curve) < 2:
        return 0.0, 0

    peak = equity_curve[0]
    max_dd = 0.0
    max_duration = 0
    current_duration = 0

    for value in equity_curve:
        if value > peak:
            peak = value
            current_duration = 0
        else:
            dd = (peak - value) / peak
            max_dd = max(max_dd, dd)
            current_duration += 1
            max_duration = max(max_duration, current_duration)

    return max_dd * 100, max_duration


def calculate_profit_factor(trades: List[Trade]) -> float:
    """
    Calculate profit factor.

    Profit Factor = Gross Profit / Gross Loss
    """
    gross_profit = sum(t.pnl for t in trades if t.pnl > 0)
    gross_loss = abs(sum(t.pnl for t in trades if t.pnl < 0))

    if gross_loss == 0:
        return float('inf') if gross_profit > 0 else 0.0

    return gross_profit / gross_loss


def calculate_expectancy(trades: List[Trade]) -> float:
    """
    Calculate expectancy (average profit per trade).

    Expectancy = (Win Rate * Avg Win) - (Loss Rate * Avg Loss)
    """
    if not trades:
        return 0.0

    winners = [t for t in trades if t.pnl > 0]
    losers = [t for t in trades if t.pnl <= 0]

    if not winners and not losers:
        return 0.0

    win_rate = len(winners) / len(trades)
    loss_rate = len(losers) / len(trades)

    avg_win = statistics.mean([t.pnl for t in winners]) if winners else 0
    avg_loss = abs(statistics.mean([t.pnl for t in losers])) if losers else 0

    return (win_rate * avg_win) - (loss_rate * avg_loss)


def calculate_sqn(trades: List[Trade]) -> float:
    """
    Calculate System Quality Number.

    SQN = sqrt(N) * (Mean R-Multiple / StdDev R-Multiple)

    Where R-Multiple is the return multiple of each trade.
    """
    if len(trades) < 20:
        return 0.0

    r_multiples = [t.pnl_pct for t in trades]
    mean_r = statistics.mean(r_multiples)
    std_r = statistics.stdev(r_multiples)

    if std_r == 0:
        return 0.0

    return math.sqrt(len(trades)) * (mean_r / std_r)


def calculate_all_metrics(
    trades: List[Trade],
    equity_curve: List[float],
    start_date: datetime,
    end_date: datetime,
    initial_capital: float = 1_000_000,
) -> PerformanceMetrics:
    """
    Calculate all performance metrics for a strategy.

    Args:
        trades: List of Trade objects
        equity_curve: List of equity values over time
        start_date: Strategy start date
        end_date: Strategy end date
        initial_capital: Starting capital

    Returns:
        PerformanceMetrics object with all calculated values
    """
    if not trades or not equity_curve:
        return PerformanceMetrics()

    # Time calculations
    days = (end_date - start_date).days
    years = days / 365.25

    # Return calculations
    final_equity = equity_curve[-1]
    total_return = (final_equity - initial_capital) / initial_capital
    total_return_pct = total_return * 100

    # CAGR
    cagr = ((final_equity / initial_capital) ** (1 / years) - 1) if years > 0 else 0

    # Calculate daily returns for ratios
    daily_returns = []
    for i in range(1, len(equity_curve)):
        if equity_curve[i-1] > 0:
            daily_returns.append(
                (equity_curve[i] - equity_curve[i-1]) / equity_curve[i-1]
            )

    # Risk metrics
    sharpe = calculate_sharpe(daily_returns) if daily_returns else 0
    sortino = calculate_sortino(daily_returns) if daily_returns else 0
    max_dd, max_dd_duration = calculate_max_drawdown(equity_curve)
    calmar = calculate_calmar(total_return, max_dd / 100, years) if max_dd > 0 else 0

    # Trade metrics
    winners = [t for t in trades if t.pnl > 0]
    losers = [t for t in trades if t.pnl <= 0]

    win_rate = len(winners) / len(trades) if trades else 0
    profit_factor = calculate_profit_factor(trades)
    expectancy = calculate_expectancy(trades)
    sqn = calculate_sqn(trades)

    avg_win = statistics.mean([t.pnl_pct for t in winners]) if winners else 0
    avg_loss = statistics.mean([t.pnl_pct for t in losers]) if losers else 0

    # Exposure time
    total_hold_time = sum(t.hold_time_hours for t in trades)
    total_hours = days * 24
    exposure_pct = (total_hold_time / total_hours * 100) if total_hours > 0 else 0

    # Volatility
    volatility = statistics.stdev(daily_returns) * math.sqrt(252) if len(daily_returns) > 1 else 0

    return PerformanceMetrics(
        total_return_pct=total_return_pct,
        cagr=cagr * 100,
        avg_return_per_trade=statistics.mean([t.pnl_pct for t in trades]) if trades else 0,
        sharpe_ratio=sharpe,
        sortino_ratio=sortino,
        calmar_ratio=calmar,
        max_drawdown_pct=max_dd,
        max_drawdown_duration_days=max_dd_duration,
        total_trades=len(trades),
        winning_trades=len(winners),
        losing_trades=len(losers),
        win_rate=win_rate * 100,
        profit_factor=profit_factor,
        expectancy=expectancy,
        avg_win=avg_win * 100,
        avg_loss=avg_loss * 100,
        best_trade=max(t.pnl_pct for t in trades) * 100 if trades else 0,
        worst_trade=min(t.pnl_pct for t in trades) * 100 if trades else 0,
        avg_hold_time_hours=statistics.mean([t.hold_time_hours for t in trades]) if trades else 0,
        exposure_time_pct=exposure_pct,
        trading_days=days,
        sqn=sqn,
        volatility_annual=volatility * 100,
    )
