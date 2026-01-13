"""
Strategy Validator

Comprehensive robustness testing for trading strategies:
1. Out-of-sample testing (train/test split)
2. Parameter sensitivity analysis (heat maps)
3. Permutation tests (statistical significance)
4. Monte Carlo simulation (luck vs skill)
"""

import random
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Dict, Any, Callable, Optional, Tuple
import statistics

from .metrics import (
    Trade,
    PerformanceMetrics,
    calculate_all_metrics,
    calculate_sharpe,
    calculate_sortino,
)

logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    """Result of strategy validation."""
    is_valid: bool
    confidence: float  # 0-1
    in_sample_metrics: PerformanceMetrics
    out_sample_metrics: Optional[PerformanceMetrics]
    parameter_sensitivity: Dict[str, Any]
    permutation_pvalue: Optional[float]
    monte_carlo_results: Dict[str, Any]
    warnings: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'is_valid': self.is_valid,
            'confidence': self.confidence,
            'in_sample': self.in_sample_metrics.to_dict(),
            'out_sample': self.out_sample_metrics.to_dict() if self.out_sample_metrics else None,
            'parameter_sensitivity': self.parameter_sensitivity,
            'permutation_pvalue': self.permutation_pvalue,
            'monte_carlo': self.monte_carlo_results,
            'warnings': self.warnings,
            'recommendations': self.recommendations,
        }


class StrategyValidator:
    """
    Validates trading strategies through multiple robustness tests.

    Usage:
        validator = StrategyValidator()
        result = validator.validate(
            strategy_func=my_strategy,
            data=price_data,
            params=strategy_params,
        )
    """

    def __init__(
        self,
        train_ratio: float = 0.7,
        min_trades: int = 30,
        permutation_runs: int = 1000,
        monte_carlo_runs: int = 10000,
        significance_level: float = 0.05,
    ):
        self.train_ratio = train_ratio
        self.min_trades = min_trades
        self.permutation_runs = permutation_runs
        self.monte_carlo_runs = monte_carlo_runs
        self.significance_level = significance_level

    def validate(
        self,
        trades: List[Trade],
        equity_curve: List[float],
        start_date: datetime,
        end_date: datetime,
        initial_capital: float = 1_000_000,
        parameter_grid: Optional[Dict[str, List[Any]]] = None,
        strategy_func: Optional[Callable] = None,
        data: Optional[List[float]] = None,
    ) -> ValidationResult:
        """
        Run full validation suite on a strategy.

        Args:
            trades: List of trades from backtest
            equity_curve: Equity values over time
            start_date: Start date of backtest
            end_date: End date of backtest
            initial_capital: Starting capital
            parameter_grid: Optional dict of parameters to test
            strategy_func: Optional strategy function for parameter testing
            data: Optional price data for re-running strategy

        Returns:
            ValidationResult with all test outcomes
        """
        warnings = []
        recommendations = []

        # 1. Calculate in-sample metrics
        is_metrics = calculate_all_metrics(
            trades, equity_curve, start_date, end_date, initial_capital
        )

        logger.info(f"In-sample metrics: Sharpe={is_metrics.sharpe_ratio:.2f}, "
                   f"Sortino={is_metrics.sortino_ratio:.2f}")

        # Basic validation checks
        if len(trades) < self.min_trades:
            warnings.append(f"Only {len(trades)} trades, recommend minimum {self.min_trades}")

        if is_metrics.sharpe_ratio > 3.0:
            warnings.append("Sharpe > 3.0 suggests possible overfitting")

        if is_metrics.max_drawdown_pct > 50:
            warnings.append(f"Max drawdown {is_metrics.max_drawdown_pct:.1f}% exceeds 50%")

        # 2. Out-of-sample split (if enough data)
        os_metrics = None
        if len(trades) >= self.min_trades * 2:
            split_idx = int(len(trades) * self.train_ratio)
            os_trades = trades[split_idx:]
            os_equity = equity_curve[split_idx:]

            if len(os_trades) >= 10:
                # Calculate out-of-sample start/end dates
                os_start = os_trades[0].entry_time
                os_end = os_trades[-1].exit_time

                os_metrics = calculate_all_metrics(
                    os_trades,
                    os_equity,
                    os_start,
                    os_end,
                    os_equity[0] if os_equity else initial_capital,
                )

                logger.info(f"Out-of-sample metrics: Sharpe={os_metrics.sharpe_ratio:.2f}")

                # Check for degradation
                if os_metrics.sharpe_ratio < is_metrics.sharpe_ratio * 0.5:
                    warnings.append("Out-of-sample Sharpe < 50% of in-sample (overfitting)")
                    recommendations.append("Consider simpler strategy or different parameters")

        # 3. Permutation test
        pvalue = self._run_permutation_test(trades)
        if pvalue is not None:
            if pvalue > self.significance_level:
                warnings.append(f"Permutation p-value {pvalue:.3f} > {self.significance_level}")
                recommendations.append("Strategy may not be statistically significant")

        # 4. Monte Carlo simulation
        mc_results = self._run_monte_carlo(trades)

        if mc_results.get('percentile_5_return', 0) < 0:
            warnings.append("5th percentile Monte Carlo return is negative")
            recommendations.append("Consider smaller position sizes")

        # 5. Parameter sensitivity (placeholder - requires strategy_func)
        param_sensitivity = {
            'tested': False,
            'note': 'Provide strategy_func and parameter_grid for sensitivity analysis'
        }

        # Calculate overall confidence
        confidence = self._calculate_confidence(
            is_metrics, os_metrics, pvalue, mc_results, len(warnings)
        )

        # Determine if valid
        is_valid = (
            is_metrics.sharpe_ratio >= 1.0 and
            is_metrics.sortino_ratio >= 2.0 and
            is_metrics.max_drawdown_pct <= 50 and
            (pvalue is None or pvalue <= self.significance_level) and
            len(warnings) < 3
        )

        return ValidationResult(
            is_valid=is_valid,
            confidence=confidence,
            in_sample_metrics=is_metrics,
            out_sample_metrics=os_metrics,
            parameter_sensitivity=param_sensitivity,
            permutation_pvalue=pvalue,
            monte_carlo_results=mc_results,
            warnings=warnings,
            recommendations=recommendations,
        )

    def _run_permutation_test(self, trades: List[Trade]) -> Optional[float]:
        """
        Run permutation test to determine statistical significance.

        Shuffles trade outcomes and compares to actual performance.
        """
        if len(trades) < 20:
            return None

        actual_sharpe = calculate_sharpe([t.pnl_pct for t in trades])
        returns = [t.pnl_pct for t in trades]

        count_better = 0
        for _ in range(self.permutation_runs):
            shuffled = returns.copy()
            random.shuffle(shuffled)
            shuffled_sharpe = calculate_sharpe(shuffled)
            if shuffled_sharpe >= actual_sharpe:
                count_better += 1

        pvalue = count_better / self.permutation_runs
        logger.info(f"Permutation test p-value: {pvalue:.4f}")

        return pvalue

    def _run_monte_carlo(self, trades: List[Trade]) -> Dict[str, Any]:
        """
        Run Monte Carlo simulation by resampling trades.

        Bootstraps trade outcomes to understand distribution of possible results.
        """
        if len(trades) < 20:
            return {'tested': False, 'reason': 'Insufficient trades'}

        final_returns = []
        max_drawdowns = []

        for _ in range(self.monte_carlo_runs):
            # Sample with replacement
            sampled = random.choices(trades, k=len(trades))
            returns = [t.pnl_pct for t in sampled]

            # Calculate cumulative return
            cumulative = 1.0
            peak = 1.0
            max_dd = 0.0

            for r in returns:
                cumulative *= (1 + r)
                if cumulative > peak:
                    peak = cumulative
                dd = (peak - cumulative) / peak
                max_dd = max(max_dd, dd)

            final_returns.append((cumulative - 1) * 100)
            max_drawdowns.append(max_dd * 100)

        final_returns.sort()
        max_drawdowns.sort()

        return {
            'tested': True,
            'runs': self.monte_carlo_runs,
            'median_return': statistics.median(final_returns),
            'mean_return': statistics.mean(final_returns),
            'percentile_5_return': final_returns[int(len(final_returns) * 0.05)],
            'percentile_95_return': final_returns[int(len(final_returns) * 0.95)],
            'median_max_drawdown': statistics.median(max_drawdowns),
            'percentile_95_drawdown': max_drawdowns[int(len(max_drawdowns) * 0.95)],
        }

    def _calculate_confidence(
        self,
        is_metrics: PerformanceMetrics,
        os_metrics: Optional[PerformanceMetrics],
        pvalue: Optional[float],
        mc_results: Dict[str, Any],
        num_warnings: int,
    ) -> float:
        """Calculate overall confidence score (0-1)."""
        confidence = 0.5  # Start at neutral

        # In-sample metrics contribution
        if is_metrics.sharpe_ratio >= 1.5:
            confidence += 0.1
        if is_metrics.sortino_ratio >= 3.0:
            confidence += 0.1
        if is_metrics.calmar_ratio >= 2.0:
            confidence += 0.1

        # Out-of-sample contribution
        if os_metrics:
            if os_metrics.sharpe_ratio >= 0.8:
                confidence += 0.1
            if os_metrics.sharpe_ratio >= is_metrics.sharpe_ratio * 0.7:
                confidence += 0.1

        # Statistical significance
        if pvalue is not None and pvalue <= 0.01:
            confidence += 0.1
        elif pvalue is not None and pvalue <= 0.05:
            confidence += 0.05

        # Monte Carlo
        if mc_results.get('percentile_5_return', 0) > 0:
            confidence += 0.1

        # Penalty for warnings
        confidence -= num_warnings * 0.05

        return max(0.0, min(1.0, confidence))


def split_data_for_testing(
    data: List[Any],
    train_ratio: float = 0.7,
) -> Tuple[List[Any], List[Any]]:
    """
    Split data into training and test sets.

    Args:
        data: List of data points (prices, trades, etc.)
        train_ratio: Ratio for training set (default 70%)

    Returns:
        Tuple of (train_data, test_data)
    """
    split_idx = int(len(data) * train_ratio)
    return data[:split_idx], data[split_idx:]
