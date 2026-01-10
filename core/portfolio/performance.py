"""
Portfolio Performance Analyzer

Calculates performance metrics, benchmarks, and generates reports.
Includes risk-adjusted returns and comparison to market indices.

Prompts #107-108: Portfolio Tracking
"""

import asyncio
import logging
import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Any
from enum import Enum
from collections import defaultdict

from .tracker import Portfolio, Position, Transaction, TransactionType

logger = logging.getLogger(__name__)


class TimeFrame(str, Enum):
    """Time frames for performance analysis"""
    DAY_1 = "1d"
    WEEK_1 = "1w"
    MONTH_1 = "1m"
    MONTH_3 = "3m"
    MONTH_6 = "6m"
    YEAR_1 = "1y"
    ALL_TIME = "all"


@dataclass
class PerformanceMetrics:
    """Portfolio performance metrics"""
    timeframe: TimeFrame
    start_date: datetime
    end_date: datetime

    # Returns
    total_return: float = 0.0
    total_return_pct: float = 0.0
    annualized_return: float = 0.0

    # Risk metrics
    volatility: float = 0.0  # Standard deviation of returns
    sharpe_ratio: float = 0.0  # Risk-adjusted return
    sortino_ratio: float = 0.0  # Downside risk-adjusted
    max_drawdown: float = 0.0  # Maximum peak-to-trough decline
    max_drawdown_duration_days: int = 0

    # Win/Loss
    winning_trades: int = 0
    losing_trades: int = 0
    win_rate: float = 0.0
    avg_win: float = 0.0
    avg_loss: float = 0.0
    profit_factor: float = 0.0  # Gross profit / Gross loss

    # Trading metrics
    total_trades: int = 0
    total_volume: float = 0.0
    total_fees: float = 0.0
    avg_holding_period_days: float = 0.0

    # Benchmark comparison
    benchmark_return: float = 0.0  # e.g., SOL performance
    alpha: float = 0.0  # Excess return over benchmark
    beta: float = 0.0  # Correlation with benchmark

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "timeframe": self.timeframe.value,
            "start_date": self.start_date.isoformat(),
            "end_date": self.end_date.isoformat(),
            "total_return": self.total_return,
            "total_return_pct": self.total_return_pct,
            "annualized_return": self.annualized_return,
            "volatility": self.volatility,
            "sharpe_ratio": self.sharpe_ratio,
            "sortino_ratio": self.sortino_ratio,
            "max_drawdown": self.max_drawdown,
            "max_drawdown_duration_days": self.max_drawdown_duration_days,
            "winning_trades": self.winning_trades,
            "losing_trades": self.losing_trades,
            "win_rate": self.win_rate,
            "avg_win": self.avg_win,
            "avg_loss": self.avg_loss,
            "profit_factor": self.profit_factor,
            "total_trades": self.total_trades,
            "total_volume": self.total_volume,
            "total_fees": self.total_fees,
            "avg_holding_period_days": self.avg_holding_period_days,
            "benchmark_return": self.benchmark_return,
            "alpha": self.alpha,
            "beta": self.beta
        }


class PerformanceAnalyzer:
    """
    Analyzes portfolio performance

    Calculates risk-adjusted returns, drawdowns, and
    compares to benchmarks.
    """

    def __init__(self, risk_free_rate: float = 0.05):
        self.risk_free_rate = risk_free_rate  # Annualized risk-free rate

    async def analyze_performance(
        self,
        portfolio: Portfolio,
        timeframe: TimeFrame = TimeFrame.MONTH_1,
        benchmark_returns: Optional[List[float]] = None
    ) -> PerformanceMetrics:
        """
        Analyze portfolio performance for a given timeframe

        Args:
            portfolio: Portfolio to analyze
            timeframe: Time period for analysis
            benchmark_returns: Daily returns of benchmark (optional)
        """
        # Determine date range
        end_date = datetime.now()
        start_date = self._get_start_date(end_date, timeframe)

        # Filter transactions in timeframe
        txs = [
            t for t in portfolio.transactions
            if t.timestamp >= start_date and t.timestamp <= end_date
        ]

        # Calculate basic metrics
        metrics = PerformanceMetrics(
            timeframe=timeframe,
            start_date=start_date,
            end_date=end_date
        )

        if not txs:
            return metrics

        # Total return
        metrics.total_return = portfolio.total_unrealized_pnl + portfolio.total_realized_pnl
        if portfolio.total_cost_basis > 0:
            metrics.total_return_pct = (metrics.total_return / portfolio.total_cost_basis) * 100

        # Annualized return
        days = (end_date - start_date).days or 1
        if days >= 365:
            metrics.annualized_return = metrics.total_return_pct
        else:
            metrics.annualized_return = metrics.total_return_pct * (365 / days)

        # Trading metrics
        metrics.total_trades = len(txs)
        metrics.total_volume = sum(t.total_usd for t in txs)
        metrics.total_fees = sum(t.fee_usd for t in txs)

        # Win/Loss analysis
        self._analyze_wins_losses(txs, metrics)

        # Calculate daily returns for risk metrics
        daily_returns = self._calculate_daily_returns(portfolio, txs)

        if daily_returns:
            # Volatility
            metrics.volatility = self._calculate_volatility(daily_returns) * 100

            # Sharpe ratio
            metrics.sharpe_ratio = self._calculate_sharpe(
                metrics.annualized_return / 100,
                metrics.volatility / 100
            )

            # Sortino ratio
            metrics.sortino_ratio = self._calculate_sortino(
                daily_returns,
                metrics.annualized_return / 100
            )

            # Max drawdown
            metrics.max_drawdown = self._calculate_max_drawdown(daily_returns) * 100

        # Benchmark comparison
        if benchmark_returns:
            metrics.benchmark_return = sum(benchmark_returns) * 100
            metrics.alpha = metrics.total_return_pct - metrics.benchmark_return

            if daily_returns:
                metrics.beta = self._calculate_beta(daily_returns, benchmark_returns)

        return metrics

    def _get_start_date(self, end_date: datetime, timeframe: TimeFrame) -> datetime:
        """Get start date for timeframe"""
        timeframe_days = {
            TimeFrame.DAY_1: 1,
            TimeFrame.WEEK_1: 7,
            TimeFrame.MONTH_1: 30,
            TimeFrame.MONTH_3: 90,
            TimeFrame.MONTH_6: 180,
            TimeFrame.YEAR_1: 365,
            TimeFrame.ALL_TIME: 3650  # 10 years
        }
        days = timeframe_days.get(timeframe, 30)
        return end_date - timedelta(days=days)

    def _analyze_wins_losses(
        self,
        transactions: List[Transaction],
        metrics: PerformanceMetrics
    ):
        """Analyze winning and losing trades"""
        sell_txs = [t for t in transactions if t.tx_type == TransactionType.SELL]

        if not sell_txs:
            return

        wins = []
        losses = []

        # This is simplified - real implementation would track
        # actual P&L per trade using cost basis
        for tx in sell_txs:
            # Placeholder: would need actual P&L tracking
            # For now, we'll use a simple heuristic
            pass

        # Use portfolio-level realized P&L as proxy
        # In production, track P&L per trade

    def _calculate_daily_returns(
        self,
        portfolio: Portfolio,
        transactions: List[Transaction]
    ) -> List[float]:
        """Calculate daily returns from transactions"""
        # Group transactions by day
        by_day = defaultdict(lambda: {"invested": 0.0, "withdrawn": 0.0})

        for tx in transactions:
            day = tx.timestamp.strftime("%Y-%m-%d")
            if tx.tx_type in [TransactionType.BUY, TransactionType.TRANSFER_IN]:
                by_day[day]["invested"] += tx.total_usd
            elif tx.tx_type in [TransactionType.SELL, TransactionType.TRANSFER_OUT]:
                by_day[day]["withdrawn"] += tx.total_usd

        # Calculate daily returns
        # This is simplified - real implementation would use
        # daily portfolio values
        returns = []
        prev_value = portfolio.total_cost_basis

        for day in sorted(by_day.keys()):
            data = by_day[day]
            current_value = prev_value + data["invested"] - data["withdrawn"]

            if prev_value > 0:
                daily_return = (current_value - prev_value) / prev_value
                returns.append(daily_return)

            prev_value = current_value

        return returns

    def _calculate_volatility(self, returns: List[float]) -> float:
        """Calculate annualized volatility"""
        if len(returns) < 2:
            return 0.0

        # Standard deviation
        mean = sum(returns) / len(returns)
        variance = sum((r - mean) ** 2 for r in returns) / len(returns)
        daily_vol = math.sqrt(variance)

        # Annualize (assuming 365 trading days for crypto)
        return daily_vol * math.sqrt(365)

    def _calculate_sharpe(
        self,
        annualized_return: float,
        annualized_volatility: float
    ) -> float:
        """Calculate Sharpe ratio"""
        if annualized_volatility == 0:
            return 0.0

        return (annualized_return - self.risk_free_rate) / annualized_volatility

    def _calculate_sortino(
        self,
        returns: List[float],
        annualized_return: float
    ) -> float:
        """Calculate Sortino ratio (downside deviation)"""
        # Only consider negative returns
        negative_returns = [r for r in returns if r < 0]

        if not negative_returns:
            return 0.0

        # Downside deviation
        mean_negative = sum(negative_returns) / len(negative_returns)
        variance = sum((r - mean_negative) ** 2 for r in negative_returns) / len(negative_returns)
        downside_vol = math.sqrt(variance) * math.sqrt(365)

        if downside_vol == 0:
            return 0.0

        return (annualized_return - self.risk_free_rate) / downside_vol

    def _calculate_max_drawdown(self, returns: List[float]) -> float:
        """Calculate maximum drawdown"""
        if not returns:
            return 0.0

        # Calculate cumulative returns
        cumulative = [1.0]
        for r in returns:
            cumulative.append(cumulative[-1] * (1 + r))

        # Find maximum drawdown
        peak = cumulative[0]
        max_drawdown = 0.0

        for value in cumulative:
            if value > peak:
                peak = value
            drawdown = (peak - value) / peak
            max_drawdown = max(max_drawdown, drawdown)

        return max_drawdown

    def _calculate_beta(
        self,
        portfolio_returns: List[float],
        benchmark_returns: List[float]
    ) -> float:
        """Calculate beta (correlation with benchmark)"""
        if len(portfolio_returns) != len(benchmark_returns) or not portfolio_returns:
            return 0.0

        # Calculate covariance and variance
        n = len(portfolio_returns)
        mean_p = sum(portfolio_returns) / n
        mean_b = sum(benchmark_returns) / n

        covariance = sum(
            (portfolio_returns[i] - mean_p) * (benchmark_returns[i] - mean_b)
            for i in range(n)
        ) / n

        variance_b = sum((r - mean_b) ** 2 for r in benchmark_returns) / n

        if variance_b == 0:
            return 0.0

        return covariance / variance_b

    async def get_performance_report(
        self,
        portfolio: Portfolio
    ) -> Dict[str, Any]:
        """Generate a comprehensive performance report"""
        # Analyze multiple timeframes
        timeframes = [
            TimeFrame.DAY_1,
            TimeFrame.WEEK_1,
            TimeFrame.MONTH_1,
            TimeFrame.MONTH_3,
            TimeFrame.YEAR_1
        ]

        results = {}
        for tf in timeframes:
            metrics = await self.analyze_performance(portfolio, tf)
            results[tf.value] = metrics.to_dict()

        # Best/worst performers
        positions = list(portfolio.positions.values())
        positions.sort(key=lambda p: p.unrealized_pnl_pct, reverse=True)

        best_performers = [
            {
                "token": p.token,
                "pnl_pct": p.unrealized_pnl_pct,
                "value": p.current_value
            }
            for p in positions[:3] if p.unrealized_pnl_pct > 0
        ]

        worst_performers = [
            {
                "token": p.token,
                "pnl_pct": p.unrealized_pnl_pct,
                "value": p.current_value
            }
            for p in positions[-3:] if p.unrealized_pnl_pct < 0
        ]

        return {
            "portfolio_id": portfolio.portfolio_id,
            "total_value": portfolio.total_value,
            "total_pnl": portfolio.total_unrealized_pnl + portfolio.total_realized_pnl,
            "performance_by_timeframe": results,
            "best_performers": best_performers,
            "worst_performers": worst_performers,
            "generated_at": datetime.now().isoformat()
        }

    async def get_risk_report(self, portfolio: Portfolio) -> Dict[str, Any]:
        """Generate risk analysis report"""
        metrics = await self.analyze_performance(portfolio, TimeFrame.MONTH_3)

        # Position concentration
        positions = list(portfolio.positions.values())
        total_value = portfolio.total_value or 1

        concentration = [
            {
                "token": p.token,
                "percentage": (p.current_value / total_value) * 100
            }
            for p in positions
            if p.current_value > 0
        ]
        concentration.sort(key=lambda x: x["percentage"], reverse=True)

        # Risk score (0-100, higher = riskier)
        risk_score = self._calculate_risk_score(metrics, concentration)

        return {
            "volatility_90d": metrics.volatility,
            "max_drawdown": metrics.max_drawdown,
            "sharpe_ratio": metrics.sharpe_ratio,
            "sortino_ratio": metrics.sortino_ratio,
            "concentration_risk": concentration[:5],
            "top_position_pct": concentration[0]["percentage"] if concentration else 0,
            "risk_score": risk_score,
            "risk_level": self._get_risk_level(risk_score)
        }

    def _calculate_risk_score(
        self,
        metrics: PerformanceMetrics,
        concentration: List[Dict]
    ) -> float:
        """Calculate overall risk score (0-100)"""
        score = 50  # Base score

        # Volatility component (higher vol = higher risk)
        if metrics.volatility > 100:
            score += 20
        elif metrics.volatility > 50:
            score += 10
        elif metrics.volatility < 20:
            score -= 10

        # Drawdown component
        if metrics.max_drawdown > 30:
            score += 15
        elif metrics.max_drawdown > 15:
            score += 5

        # Concentration component
        if concentration:
            top_pct = concentration[0]["percentage"]
            if top_pct > 50:
                score += 15
            elif top_pct > 30:
                score += 5

        # Sharpe ratio (better risk-adjusted returns = lower risk)
        if metrics.sharpe_ratio > 2:
            score -= 15
        elif metrics.sharpe_ratio > 1:
            score -= 5
        elif metrics.sharpe_ratio < 0:
            score += 10

        return max(0, min(100, score))

    def _get_risk_level(self, score: float) -> str:
        """Convert risk score to level"""
        if score < 30:
            return "low"
        elif score < 50:
            return "moderate"
        elif score < 70:
            return "high"
        else:
            return "very_high"


# Testing
if __name__ == "__main__":
    async def test():
        from .tracker import Portfolio, Position

        # Create test portfolio
        portfolio = Portfolio(
            portfolio_id="TEST",
            user_id="TEST_USER"
        )

        # Add some positions
        sol_position = Position(
            token="SOL",
            amount=100,
            avg_cost_basis=100.0,
            total_cost_basis=10000.0
        )
        sol_position.update_price(150.0)
        portfolio.positions["SOL"] = sol_position

        eth_position = Position(
            token="ETH",
            amount=5,
            avg_cost_basis=2500.0,
            total_cost_basis=12500.0
        )
        eth_position.update_price=3000.0
        portfolio.positions["ETH"] = eth_position

        portfolio.recalculate()

        # Analyze performance
        analyzer = PerformanceAnalyzer()

        metrics = await analyzer.analyze_performance(portfolio, TimeFrame.MONTH_1)
        print("Performance Metrics (1M):")
        print(f"  Total Return: ${metrics.total_return:,.2f} ({metrics.total_return_pct:.1f}%)")
        print(f"  Sharpe Ratio: {metrics.sharpe_ratio:.2f}")

        # Get full report
        report = await analyzer.get_performance_report(portfolio)
        print(f"\nPerformance Report: {report['total_value']:,.2f}")

        # Risk report
        risk = await analyzer.get_risk_report(portfolio)
        print(f"\nRisk Score: {risk['risk_score']:.0f} ({risk['risk_level']})")

    asyncio.run(test())
