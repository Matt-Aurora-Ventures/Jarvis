"""
Walk-Forward Testing Module

Implements rolling window backtesting to simulate real trading conditions:
1. Optimize on training window (e.g., 3 years)
2. Trade on out-of-sample window (e.g., 6 months)
3. Roll forward and repeat
4. Stitch together OOS equity curves

This tests parameter stability and prevents overfitting.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import List, Dict, Any, Callable, Optional, Tuple
import statistics

from .metrics import PerformanceMetrics, calculate_all_metrics, Trade

logger = logging.getLogger(__name__)


@dataclass
class WalkForwardWindow:
    """Single walk-forward window results."""
    window_id: int
    train_start: datetime
    train_end: datetime
    test_start: datetime
    test_end: datetime
    optimal_params: Dict[str, Any]
    train_metrics: PerformanceMetrics
    test_metrics: PerformanceMetrics
    test_trades: List[Trade]
    test_equity: List[float]


@dataclass
class WalkForwardResult:
    """Complete walk-forward test results."""
    windows: List[WalkForwardWindow]
    aggregated_metrics: PerformanceMetrics
    stitched_equity: List[float]
    parameter_stability: Dict[str, Any]
    winning_windows: int
    losing_windows: int
    is_valid: bool
    warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'num_windows': len(self.windows),
            'winning_windows': self.winning_windows,
            'losing_windows': self.losing_windows,
            'aggregated_metrics': self.aggregated_metrics.to_dict(),
            'parameter_stability': self.parameter_stability,
            'is_valid': self.is_valid,
            'warnings': self.warnings,
        }


class WalkForwardTester:
    """
    Walk-Forward Testing Engine

    Simulates live trading by:
    1. Training on historical data
    2. Optimizing parameters
    3. Trading forward on unseen data
    4. Rolling the window and repeating

    Configuration:
        train_months: Length of training window (default 36 = 3 years)
        test_months: Length of test window (default 6 months)
        step_months: How far to roll forward (default 6 = test_months)
        compound: Whether to compound equity across windows
    """

    def __init__(
        self,
        train_months: int = 36,
        test_months: int = 6,
        step_months: int = 6,
        compound: bool = True,
        initial_capital: float = 1_000_000,
    ):
        self.train_months = train_months
        self.test_months = test_months
        self.step_months = step_months
        self.compound = compound
        self.initial_capital = initial_capital

    def run(
        self,
        data: Dict[datetime, float],  # Date -> Price mapping
        strategy_func: Callable[[List[float], Dict[str, Any]], Tuple[List[Trade], List[float]]],
        param_grid: Dict[str, List[Any]],
        optimize_metric: str = 'sharpe',
    ) -> WalkForwardResult:
        """
        Run walk-forward optimization and testing.

        Args:
            data: Price data as {datetime: price}
            strategy_func: Function that takes prices and params, returns (trades, equity)
            param_grid: Parameter values to test during optimization
            optimize_metric: Metric to optimize ('sharpe', 'sortino', 'calmar')

        Returns:
            WalkForwardResult with all window results and aggregated metrics
        """
        dates = sorted(data.keys())
        if len(dates) < 365:
            raise ValueError("Insufficient data for walk-forward testing")

        windows = []
        stitched_equity = [self.initial_capital]
        current_capital = self.initial_capital
        all_test_trades = []
        param_history = []

        # Calculate window boundaries
        start_date = dates[0]
        end_date = dates[-1]
        train_days = self.train_months * 30
        test_days = self.test_months * 30
        step_days = self.step_months * 30

        window_id = 0
        current_start = start_date

        while True:
            # Define window boundaries
            train_end = current_start + timedelta(days=train_days)
            test_start = train_end
            test_end = test_start + timedelta(days=test_days)

            # Check if we have enough data
            if test_end > end_date:
                break

            logger.info(f"Window {window_id}: Train {current_start.date()} - {train_end.date()}, "
                       f"Test {test_start.date()} - {test_end.date()}")

            # Extract data for windows
            train_dates = [d for d in dates if current_start <= d < train_end]
            test_dates = [d for d in dates if test_start <= d < test_end]

            if len(train_dates) < 100 or len(test_dates) < 20:
                current_start += timedelta(days=step_days)
                continue

            train_prices = [data[d] for d in train_dates]
            test_prices = [data[d] for d in test_dates]

            # Optimize on training data
            best_params, train_metrics = self._optimize_params(
                prices=train_prices,
                strategy_func=strategy_func,
                param_grid=param_grid,
                optimize_metric=optimize_metric,
                start_date=current_start,
                end_date=train_end,
            )

            param_history.append(best_params)

            # Test with optimal params
            test_trades, test_equity_raw = strategy_func(test_prices, best_params)

            # Adjust equity for compounding
            if self.compound and test_equity_raw:
                scale = current_capital / test_equity_raw[0]
                test_equity = [e * scale for e in test_equity_raw]
                for trade in test_trades:
                    trade.pnl *= scale
            else:
                test_equity = test_equity_raw

            # Calculate test metrics
            test_metrics = calculate_all_metrics(
                test_trades,
                test_equity,
                test_start,
                test_end,
                current_capital,
            )

            # Create window result
            window = WalkForwardWindow(
                window_id=window_id,
                train_start=current_start,
                train_end=train_end,
                test_start=test_start,
                test_end=test_end,
                optimal_params=best_params,
                train_metrics=train_metrics,
                test_metrics=test_metrics,
                test_trades=test_trades,
                test_equity=test_equity,
            )
            windows.append(window)

            # Update for next window
            if test_equity:
                stitched_equity.extend(test_equity[1:])  # Avoid duplicate first point
                current_capital = test_equity[-1]

            all_test_trades.extend(test_trades)
            window_id += 1
            current_start += timedelta(days=step_days)

        # Calculate aggregated metrics
        if windows and all_test_trades:
            aggregated = calculate_all_metrics(
                all_test_trades,
                stitched_equity,
                windows[0].test_start,
                windows[-1].test_end,
                self.initial_capital,
            )
        else:
            aggregated = PerformanceMetrics()

        # Analyze parameter stability
        param_stability = self._analyze_param_stability(param_history)

        # Count winning/losing windows
        winning = sum(1 for w in windows if w.test_metrics.total_return_pct > 0)
        losing = len(windows) - winning

        # Validation
        warnings = []
        if aggregated.sharpe_ratio < 0.8:
            warnings.append("Aggregated Sharpe < 0.8")
        if losing > winning:
            warnings.append(f"More losing windows ({losing}) than winning ({winning})")
        if param_stability.get('stability_score', 0) < 0.5:
            warnings.append("Low parameter stability across windows")

        is_valid = (
            aggregated.sharpe_ratio >= 1.0 and
            winning > losing and
            len(warnings) == 0
        )

        result = WalkForwardResult(
            windows=windows,
            aggregated_metrics=aggregated,
            stitched_equity=stitched_equity,
            parameter_stability=param_stability,
            winning_windows=winning,
            losing_windows=losing,
            is_valid=is_valid,
            warnings=warnings,
        )

        logger.info(f"Walk-forward complete: {len(windows)} windows, "
                   f"Sharpe={aggregated.sharpe_ratio:.2f}, Valid={is_valid}")

        return result

    def _optimize_params(
        self,
        prices: List[float],
        strategy_func: Callable,
        param_grid: Dict[str, List[Any]],
        optimize_metric: str,
        start_date: datetime,
        end_date: datetime,
    ) -> Tuple[Dict[str, Any], PerformanceMetrics]:
        """Find optimal parameters on training data."""
        best_params = {}
        best_score = float('-inf')
        best_metrics = PerformanceMetrics()

        # Generate all parameter combinations
        param_names = list(param_grid.keys())
        param_values = list(param_grid.values())

        def generate_combinations(idx=0, current={}):
            if idx == len(param_names):
                yield current.copy()
                return

            for value in param_values[idx]:
                current[param_names[idx]] = value
                yield from generate_combinations(idx + 1, current)

        for params in generate_combinations():
            try:
                trades, equity = strategy_func(prices, params)

                if not trades or not equity:
                    continue

                metrics = calculate_all_metrics(
                    trades, equity, start_date, end_date, equity[0]
                )

                # Get optimization score
                if optimize_metric == 'sharpe':
                    score = metrics.sharpe_ratio
                elif optimize_metric == 'sortino':
                    score = metrics.sortino_ratio
                elif optimize_metric == 'calmar':
                    score = metrics.calmar_ratio
                else:
                    score = metrics.sharpe_ratio

                if score > best_score:
                    best_score = score
                    best_params = params.copy()
                    best_metrics = metrics

            except Exception as e:
                logger.warning(f"Error testing params {params}: {e}")
                continue

        return best_params, best_metrics

    def _analyze_param_stability(
        self,
        param_history: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Analyze how stable parameters are across windows."""
        if len(param_history) < 2:
            return {'stability_score': 1.0, 'note': 'Insufficient windows'}

        stability = {}
        total_stability = 0
        num_params = 0

        # For each parameter, check how often it stayed the same
        all_params = set()
        for ph in param_history:
            all_params.update(ph.keys())

        for param in all_params:
            values = [ph.get(param) for ph in param_history if param in ph]
            if len(values) < 2:
                continue

            # Count unique values
            unique = len(set(values))
            param_stability = 1.0 - (unique - 1) / len(values)
            stability[param] = {
                'values': values,
                'unique_count': unique,
                'stability': param_stability,
            }
            total_stability += param_stability
            num_params += 1

        overall_stability = total_stability / num_params if num_params > 0 else 0

        return {
            'stability_score': overall_stability,
            'params': stability,
            'windows_tested': len(param_history),
        }
