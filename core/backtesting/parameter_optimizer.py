"""
Parameter Optimization Module

Provides grid search and optimization for trading strategies:
- Define parameter search space
- Grid search all combinations
- Find optimal parameters
- Generate parameter matrix with scores
- Support parameter constraints
"""

import logging
import itertools
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Any, Callable, Optional, Tuple

from core.backtesting.backtest_engine import (
    AdvancedBacktestEngine,
    BacktestConfig,
    BacktestMetrics,
    BacktestResult,
)

logger = logging.getLogger(__name__)


@dataclass
class OptimizationResult:
    """Result of parameter optimization."""
    best_params: Dict[str, Any]
    best_score: float
    best_metrics: Optional[BacktestMetrics]
    all_results: List[Dict[str, Any]]
    metric_used: str
    total_combinations: int
    valid_combinations: int
    optimization_time: float

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'best_params': self.best_params,
            'best_score': self.best_score,
            'metric_used': self.metric_used,
            'total_combinations': self.total_combinations,
            'valid_combinations': self.valid_combinations,
            'optimization_time': self.optimization_time,
            'all_results': self.all_results,
        }


class ParameterOptimizer:
    """
    Parameter optimizer for trading strategies.

    Features:
    - Define parameter search spaces
    - Grid search optimization
    - Parameter constraints
    - Multiple optimization metrics
    - Parallel evaluation (future)
    """

    def __init__(self):
        self._parameters: Dict[str, List[Any]] = {}
        self._constraints: List[Callable[[Dict], bool]] = []

    def add_parameter(self, name: str, values: List[Any]) -> None:
        """
        Add a parameter to the search space.

        Args:
            name: Parameter name
            values: List of values to test
        """
        self._parameters[name] = values
        logger.debug(f"Added parameter '{name}' with {len(values)} values")

    def get_parameter_space(self) -> Dict[str, List[Any]]:
        """Get the current parameter search space."""
        return self._parameters.copy()

    def add_constraint(self, constraint: Callable[[Dict], bool]) -> None:
        """
        Add a constraint function.

        Args:
            constraint: Function that takes params dict and returns True if valid
        """
        self._constraints.append(constraint)
        logger.debug(f"Added constraint (total: {len(self._constraints)})")

    def clear_constraints(self) -> None:
        """Clear all constraints."""
        self._constraints = []

    def _check_constraints(self, params: Dict[str, Any]) -> bool:
        """Check if parameters satisfy all constraints."""
        for constraint in self._constraints:
            try:
                if not constraint(params):
                    return False
            except Exception as e:
                logger.warning(f"Constraint check failed: {e}")
                return False
        return True

    def _generate_combinations(self) -> List[Dict[str, Any]]:
        """Generate all parameter combinations."""
        if not self._parameters:
            return [{}]

        keys = list(self._parameters.keys())
        values = [self._parameters[k] for k in keys]

        combinations = []
        for combo in itertools.product(*values):
            params = dict(zip(keys, combo))
            combinations.append(params)

        return combinations

    def grid_search(
        self,
        data: List[Dict],
        symbol: str,
        strategy_factory: Callable[[Dict], Callable],
        initial_capital: float = 10000,
        metric: str = 'sharpe_ratio',
        start_date: str = None,
        end_date: str = None
    ) -> Dict[str, Any]:
        """
        Run grid search optimization.

        Args:
            data: Historical OHLCV data
            symbol: Trading symbol
            strategy_factory: Function that takes params and returns strategy function
            initial_capital: Starting capital
            metric: Metric to optimize ('sharpe_ratio', 'total_return_pct', 'calmar_ratio', etc.)
            start_date: Start date (default: first date in data)
            end_date: End date (default: last date in data)

        Returns:
            Dictionary with best_params, best_score, all_results
        """
        start_time = datetime.now()

        # Determine date range from data
        if not data:
            raise ValueError("No data provided")

        if start_date is None:
            start_date = data[0]['timestamp'][:10]
        if end_date is None:
            end_date = data[-1]['timestamp'][:10]

        # Generate all combinations
        all_combinations = self._generate_combinations()
        total_combinations = len(all_combinations)

        # Filter by constraints
        valid_combinations = [c for c in all_combinations if self._check_constraints(c)]
        valid_count = len(valid_combinations)

        logger.info(f"Grid search: {valid_count}/{total_combinations} valid combinations")

        results = []
        best_score = float('-inf')
        best_params = None
        best_metrics = None

        for i, params in enumerate(valid_combinations):
            try:
                # Create strategy from parameters
                strategy = strategy_factory(params)

                # Run backtest
                engine = AdvancedBacktestEngine()
                engine.load_data(symbol, data)

                config = BacktestConfig(
                    symbol=symbol,
                    start_date=start_date,
                    end_date=end_date,
                    initial_capital=initial_capital
                )

                result = engine.run(strategy, config, strategy_name=f"opt_{i}")

                # Get score
                score = self._get_metric_value(result.metrics, metric)

                results.append({
                    'params': params,
                    'score': score,
                    'metrics': {
                        'sharpe_ratio': result.metrics.sharpe_ratio,
                        'total_return_pct': result.metrics.total_return_pct,
                        'max_drawdown': result.metrics.max_drawdown,
                        'win_rate': result.metrics.win_rate,
                        'profit_factor': result.metrics.profit_factor,
                        'calmar_ratio': result.metrics.calmar_ratio,
                    }
                })

                if score > best_score:
                    best_score = score
                    best_params = params
                    best_metrics = result.metrics

                if (i + 1) % 10 == 0:
                    logger.info(f"Progress: {i + 1}/{valid_count} combinations tested")

            except Exception as e:
                logger.warning(f"Combination {params} failed: {e}")
                results.append({
                    'params': params,
                    'score': float('-inf'),
                    'error': str(e)
                })

        end_time = datetime.now()
        optimization_time = (end_time - start_time).total_seconds()

        logger.info(f"Grid search complete. Best score: {best_score:.4f}")
        logger.info(f"Best params: {best_params}")

        return {
            'best_params': best_params or {},
            'best_score': best_score,
            'best_metrics': best_metrics,
            'all_results': results,
            'metric_used': metric,
            'total_combinations': total_combinations,
            'valid_combinations': valid_count,
            'optimization_time': optimization_time
        }

    def _get_metric_value(self, metrics: BacktestMetrics, metric_name: str) -> float:
        """Get metric value by name."""
        metric_map = {
            'sharpe_ratio': metrics.sharpe_ratio,
            'sortino_ratio': metrics.sortino_ratio,
            'total_return_pct': metrics.total_return_pct,
            'total_return': metrics.total_return,
            'annualized_return': metrics.annualized_return,
            'max_drawdown': -metrics.max_drawdown,  # Negate so higher is better
            'win_rate': metrics.win_rate,
            'profit_factor': metrics.profit_factor,
            'recovery_factor': metrics.recovery_factor,
            'calmar_ratio': metrics.calmar_ratio,
            'expectancy': metrics.expectancy,
        }

        return metric_map.get(metric_name, 0)

    def get_parameter_matrix(
        self,
        result: Dict[str, Any],
        sort_by: str = 'score',
        ascending: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Get parameter matrix with performance scores.

        Args:
            result: Result from grid_search
            sort_by: Field to sort by
            ascending: Sort order

        Returns:
            List of {params, score, metrics} dictionaries
        """
        all_results = result.get('all_results', [])

        # Sort results
        sorted_results = sorted(
            all_results,
            key=lambda x: x.get(sort_by, 0) if x.get(sort_by, 0) != float('-inf') else float('-inf'),
            reverse=not ascending
        )

        return sorted_results

    def get_heatmap_data(
        self,
        result: Dict[str, Any],
        param_x: str,
        param_y: str
    ) -> Dict[str, Any]:
        """
        Get data for parameter heatmap visualization.

        Args:
            result: Result from grid_search
            param_x: Parameter for x-axis
            param_y: Parameter for y-axis

        Returns:
            Dictionary with heatmap data
        """
        all_results = result.get('all_results', [])

        # Extract unique values
        x_values = sorted(set(r['params'].get(param_x) for r in all_results if param_x in r.get('params', {})))
        y_values = sorted(set(r['params'].get(param_y) for r in all_results if param_y in r.get('params', {})))

        # Build matrix
        matrix = []
        for y in y_values:
            row = []
            for x in x_values:
                # Find matching result
                matching = [
                    r for r in all_results
                    if r.get('params', {}).get(param_x) == x
                    and r.get('params', {}).get(param_y) == y
                ]
                if matching:
                    row.append(matching[0].get('score', 0))
                else:
                    row.append(None)
            matrix.append(row)

        return {
            'x_param': param_x,
            'y_param': param_y,
            'x_values': x_values,
            'y_values': y_values,
            'matrix': matrix
        }

    def sensitivity_analysis(
        self,
        result: Dict[str, Any],
        base_params: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Perform sensitivity analysis on parameters.

        Shows how much score changes when each parameter varies.

        Args:
            result: Result from grid_search
            base_params: Base parameters (default: best params)

        Returns:
            Dictionary with sensitivity scores per parameter
        """
        base_params = base_params or result.get('best_params', {})
        all_results = result.get('all_results', [])

        if not base_params or not all_results:
            return {}

        sensitivities = {}

        for param_name, param_values in self._parameters.items():
            scores = []

            for value in param_values:
                # Find result where only this param differs
                test_params = base_params.copy()
                test_params[param_name] = value

                matching = [
                    r for r in all_results
                    if all(r.get('params', {}).get(k) == v for k, v in test_params.items())
                ]

                if matching:
                    scores.append(matching[0].get('score', 0))

            if len(scores) >= 2:
                # Calculate sensitivity as range of scores
                valid_scores = [s for s in scores if s != float('-inf')]
                if valid_scores:
                    sensitivity = max(valid_scores) - min(valid_scores)
                    sensitivities[param_name] = {
                        'sensitivity': sensitivity,
                        'scores': scores,
                        'values': param_values
                    }

        return sensitivities

    def generate_report(
        self,
        result: Dict[str, Any],
        top_n: int = 10
    ) -> str:
        """Generate text report for optimization results."""
        best_params = result.get('best_params', {})
        best_score = result.get('best_score', 0)
        metric = result.get('metric_used', 'unknown')
        total = result.get('total_combinations', 0)
        valid = result.get('valid_combinations', 0)
        time_taken = result.get('optimization_time', 0)

        report = f"""
PARAMETER OPTIMIZATION REPORT
{'=' * 60}

SUMMARY:
  Metric Optimized: {metric}
  Total Combinations: {total}
  Valid Combinations: {valid}
  Optimization Time: {time_taken:.2f}s

BEST PARAMETERS:
"""
        for param, value in best_params.items():
            report += f"  {param}: {value}\n"

        report += f"""
BEST SCORE:
  {metric}: {best_score:.4f}
"""

        # Top results
        top_results = self.get_parameter_matrix(result)[:top_n]
        if top_results:
            report += f"""
TOP {min(top_n, len(top_results))} PARAMETER COMBINATIONS:
{'-' * 60}
"""
            for i, r in enumerate(top_results):
                params_str = ', '.join(f"{k}={v}" for k, v in r.get('params', {}).items())
                score = r.get('score', 0)
                if score != float('-inf'):
                    report += f"  {i+1}. Score={score:.4f} | {params_str}\n"

        return report
