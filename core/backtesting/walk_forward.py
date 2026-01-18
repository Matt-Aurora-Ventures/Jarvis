"""
Walk-Forward Analysis Module

Provides walk-forward testing to detect overfitting:
- Split data into rolling train/test periods
- Train on period 1, test on period 2, slide window
- Calculate robustness ratio and overfitting score
- Generate degradation curves
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Any, Callable, Optional

from core.backtesting.backtest_engine import (
    AdvancedBacktestEngine,
    BacktestConfig,
    BacktestMetrics,
)

logger = logging.getLogger(__name__)


@dataclass
class WalkForwardPeriod:
    """Results for a single walk-forward period."""
    period_index: int
    train_start: str
    train_end: str
    test_start: str
    test_end: str
    train_performance: Dict[str, float]
    test_performance: Dict[str, float]
    train_metrics: Optional[BacktestMetrics] = None
    test_metrics: Optional[BacktestMetrics] = None


@dataclass
class WalkForwardResult:
    """Complete walk-forward analysis result."""
    periods: List[WalkForwardPeriod]
    symbol: str
    strategy_name: str
    n_splits: int
    train_size: float
    test_size: float
    aggregate_train_sharpe: float
    aggregate_test_sharpe: float
    robustness_ratio: float
    overfitting_score: float

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'symbol': self.symbol,
            'strategy_name': self.strategy_name,
            'n_splits': self.n_splits,
            'train_size': self.train_size,
            'test_size': self.test_size,
            'aggregate_train_sharpe': self.aggregate_train_sharpe,
            'aggregate_test_sharpe': self.aggregate_test_sharpe,
            'robustness_ratio': self.robustness_ratio,
            'overfitting_score': self.overfitting_score,
            'periods': [
                {
                    'period': p.period_index,
                    'train_start': p.train_start,
                    'train_end': p.train_end,
                    'test_start': p.test_start,
                    'test_end': p.test_end,
                    'train_sharpe': p.train_performance.get('sharpe_ratio', 0),
                    'test_sharpe': p.test_performance.get('sharpe_ratio', 0),
                    'train_return': p.train_performance.get('total_return_pct', 0),
                    'test_return': p.test_performance.get('total_return_pct', 0),
                }
                for p in self.periods
            ]
        }


class WalkForwardAnalyzer:
    """
    Walk-forward analysis for strategy validation.

    Walk-forward testing helps detect overfitting by:
    1. Splitting data into overlapping train/test windows
    2. Training (backtesting) on the train window
    3. Testing on the out-of-sample test window
    4. Sliding the window forward and repeating

    A robust strategy should have similar performance on train and test data.
    Large gaps indicate overfitting.
    """

    def __init__(self):
        self._engine = AdvancedBacktestEngine()

    def create_splits(
        self,
        data: List[Dict],
        train_size: float = 0.7,
        test_size: float = 0.3,
        n_splits: int = 5
    ) -> List[Dict[str, List[Dict]]]:
        """
        Create train/test splits for walk-forward analysis.

        Args:
            data: List of OHLCV dictionaries
            train_size: Fraction of window for training (0-1)
            test_size: Fraction of window for testing (0-1)
            n_splits: Number of splits to create

        Returns:
            List of {'train': [...], 'test': [...]} dictionaries
        """
        if len(data) < 10:
            raise ValueError("Insufficient data for walk-forward analysis (need >= 10 points)")

        total_size = len(data)
        window_size = total_size // n_splits

        if window_size < 2:
            raise ValueError(f"Window size too small ({window_size}) for {n_splits} splits")

        splits = []

        for i in range(n_splits):
            # Calculate window boundaries
            window_start = i * (total_size - window_size) // max(1, (n_splits - 1))
            window_end = window_start + window_size

            if window_end > total_size:
                window_end = total_size
                window_start = max(0, window_end - window_size)

            # Split into train/test
            window_data = data[window_start:window_end]
            train_end_idx = int(len(window_data) * train_size)

            train_data = window_data[:train_end_idx]
            test_data = window_data[train_end_idx:]

            if len(train_data) > 0 and len(test_data) > 0:
                splits.append({
                    'train': train_data,
                    'test': test_data
                })

        return splits

    def run_walk_forward(
        self,
        data: List[Dict],
        strategy: Callable,
        symbol: str,
        train_size: float = 0.7,
        test_size: float = 0.3,
        n_splits: int = 5,
        initial_capital: float = 10000,
        strategy_name: str = "unnamed"
    ) -> WalkForwardResult:
        """
        Run walk-forward analysis.

        Args:
            data: Historical OHLCV data
            strategy: Strategy function (engine, candle) -> None
            symbol: Trading symbol
            train_size: Fraction for training
            test_size: Fraction for testing
            n_splits: Number of walk-forward periods
            initial_capital: Starting capital for each period
            strategy_name: Name of the strategy

        Returns:
            WalkForwardResult with all period results
        """
        if len(data) < n_splits * 2:
            raise ValueError(f"Insufficient data for {n_splits} walk-forward splits")

        splits = self.create_splits(data, train_size, test_size, n_splits)
        periods: List[WalkForwardPeriod] = []

        for i, split in enumerate(splits):
            train_data = split['train']
            test_data = split['test']

            if not train_data or not test_data:
                continue

            # Get date ranges
            train_start = train_data[0]['timestamp'][:10]
            train_end = train_data[-1]['timestamp'][:10]
            test_start = test_data[0]['timestamp'][:10]
            test_end = test_data[-1]['timestamp'][:10]

            # Run train backtest
            train_engine = AdvancedBacktestEngine()
            train_engine.load_data(symbol, train_data)

            train_config = BacktestConfig(
                symbol=symbol,
                start_date=train_start,
                end_date=train_end,
                initial_capital=initial_capital
            )

            try:
                train_result = train_engine.run(strategy, train_config, strategy_name)
                train_perf = {
                    'sharpe_ratio': train_result.metrics.sharpe_ratio,
                    'total_return_pct': train_result.metrics.total_return_pct,
                    'max_drawdown': train_result.metrics.max_drawdown,
                    'win_rate': train_result.metrics.win_rate,
                    'profit_factor': train_result.metrics.profit_factor,
                }
                train_metrics = train_result.metrics
            except Exception as e:
                logger.warning(f"Train period {i} failed: {e}")
                train_perf = {'sharpe_ratio': 0, 'total_return_pct': 0}
                train_metrics = None

            # Run test backtest
            test_engine = AdvancedBacktestEngine()
            test_engine.load_data(symbol, test_data)

            test_config = BacktestConfig(
                symbol=symbol,
                start_date=test_start,
                end_date=test_end,
                initial_capital=initial_capital
            )

            try:
                test_result = test_engine.run(strategy, test_config, strategy_name)
                test_perf = {
                    'sharpe_ratio': test_result.metrics.sharpe_ratio,
                    'total_return_pct': test_result.metrics.total_return_pct,
                    'max_drawdown': test_result.metrics.max_drawdown,
                    'win_rate': test_result.metrics.win_rate,
                    'profit_factor': test_result.metrics.profit_factor,
                }
                test_metrics = test_result.metrics
            except Exception as e:
                logger.warning(f"Test period {i} failed: {e}")
                test_perf = {'sharpe_ratio': 0, 'total_return_pct': 0}
                test_metrics = None

            periods.append(WalkForwardPeriod(
                period_index=i,
                train_start=train_start,
                train_end=train_end,
                test_start=test_start,
                test_end=test_end,
                train_performance=train_perf,
                test_performance=test_perf,
                train_metrics=train_metrics,
                test_metrics=test_metrics
            ))

        # Calculate aggregate metrics
        train_sharpes = [p.train_performance.get('sharpe_ratio', 0) for p in periods]
        test_sharpes = [p.test_performance.get('sharpe_ratio', 0) for p in periods]

        agg_train_sharpe = sum(train_sharpes) / len(train_sharpes) if train_sharpes else 0
        agg_test_sharpe = sum(test_sharpes) / len(test_sharpes) if test_sharpes else 0

        robustness = self._calculate_robustness(periods)
        overfitting = self._calculate_overfitting_score_internal(periods)

        return WalkForwardResult(
            periods=periods,
            symbol=symbol,
            strategy_name=strategy_name,
            n_splits=n_splits,
            train_size=train_size,
            test_size=test_size,
            aggregate_train_sharpe=agg_train_sharpe,
            aggregate_test_sharpe=agg_test_sharpe,
            robustness_ratio=robustness,
            overfitting_score=overfitting
        )

    def calculate_overfitting_score(self, result: WalkForwardResult) -> float:
        """
        Calculate overfitting score.

        Score interpretation:
        - 0: No overfitting (test == train performance)
        - 0.5: Moderate overfitting (test = 50% of train)
        - 1.0: Severe overfitting (test = 0% of train)
        - >1.0: Extreme overfitting (test is negative)

        Returns:
            Overfitting score (0 = good, higher = worse)
        """
        return self._calculate_overfitting_score_internal(result.periods)

    def _calculate_overfitting_score_internal(self, periods: List[WalkForwardPeriod]) -> float:
        """Calculate overfitting score from periods."""
        if not periods:
            return 0

        train_returns = [p.train_performance.get('total_return_pct', 0) for p in periods]
        test_returns = [p.test_performance.get('total_return_pct', 0) for p in periods]

        avg_train = sum(train_returns) / len(train_returns) if train_returns else 0
        avg_test = sum(test_returns) / len(test_returns) if test_returns else 0

        if avg_train <= 0:
            return 0  # Can't calculate meaningful score

        # Score: how much performance degrades from train to test
        degradation = 1 - (avg_test / avg_train)
        return max(0, degradation)

    def calculate_robustness_ratio(self, result: WalkForwardResult) -> float:
        """
        Calculate robustness ratio.

        Robustness = Test Performance / Train Performance

        Interpretation:
        - 1.0: Perfect robustness (test matches train)
        - 0.8: Good robustness (test is 80% of train)
        - 0.5: Poor robustness (test is 50% of train)
        - <0.3: Likely overfit

        Returns:
            Robustness ratio (0-1+, higher is better)
        """
        return self._calculate_robustness(result.periods)

    def _calculate_robustness(self, periods: List[WalkForwardPeriod]) -> float:
        """Calculate robustness from periods."""
        if not periods:
            return 0

        train_sharpes = [p.train_performance.get('sharpe_ratio', 0) for p in periods]
        test_sharpes = [p.test_performance.get('sharpe_ratio', 0) for p in periods]

        avg_train = sum(train_sharpes) / len(train_sharpes) if train_sharpes else 0
        avg_test = sum(test_sharpes) / len(test_sharpes) if test_sharpes else 0

        if avg_train == 0:
            return 1.0 if avg_test >= 0 else 0

        return avg_test / avg_train

    def get_degradation_curve(self, result: WalkForwardResult) -> List[Dict[str, Any]]:
        """
        Get walk-forward degradation curve.

        Shows how performance degrades from train to test across periods.

        Returns:
            List of {period, train_sharpe, test_sharpe, degradation} points
        """
        curve = []

        for period in result.periods:
            train_sharpe = period.train_performance.get('sharpe_ratio', 0)
            test_sharpe = period.test_performance.get('sharpe_ratio', 0)

            degradation = train_sharpe - test_sharpe

            curve.append({
                'period': period.period_index,
                'train_start': period.train_start,
                'test_end': period.test_end,
                'train_sharpe': train_sharpe,
                'test_sharpe': test_sharpe,
                'train_return': period.train_performance.get('total_return_pct', 0),
                'test_return': period.test_performance.get('total_return_pct', 0),
                'degradation': degradation
            })

        return curve

    def generate_report(self, result: WalkForwardResult) -> str:
        """Generate text report for walk-forward analysis."""
        report = f"""
WALK-FORWARD ANALYSIS REPORT
{'=' * 60}

Strategy: {result.strategy_name}
Symbol: {result.symbol}
Periods: {result.n_splits}
Train/Test Split: {result.train_size:.0%}/{result.test_size:.0%}

SUMMARY METRICS:
  Aggregate Train Sharpe: {result.aggregate_train_sharpe:.2f}
  Aggregate Test Sharpe: {result.aggregate_test_sharpe:.2f}
  Robustness Ratio: {result.robustness_ratio:.2%}
  Overfitting Score: {result.overfitting_score:.2f}

INTERPRETATION:
"""
        # Add interpretation
        if result.robustness_ratio >= 0.8:
            report += "  Strategy appears ROBUST - test performance closely matches train\n"
        elif result.robustness_ratio >= 0.5:
            report += "  Strategy shows MODERATE robustness - some performance decay in test\n"
        else:
            report += "  Strategy may be OVERFIT - significant performance decay in test\n"

        if result.overfitting_score < 0.3:
            report += "  Low overfitting risk\n"
        elif result.overfitting_score < 0.6:
            report += "  Moderate overfitting risk\n"
        else:
            report += "  HIGH overfitting risk - strategy likely curve-fitted\n"

        report += f"""
PERIOD BREAKDOWN:
{'-' * 60}
"""
        for period in result.periods:
            report += f"""
Period {period.period_index + 1}:
  Train: {period.train_start} to {period.train_end}
  Test: {period.test_start} to {period.test_end}
  Train Sharpe: {period.train_performance.get('sharpe_ratio', 0):.2f}
  Test Sharpe: {period.test_performance.get('sharpe_ratio', 0):.2f}
  Train Return: {period.train_performance.get('total_return_pct', 0):.2f}%
  Test Return: {period.test_performance.get('total_return_pct', 0):.2f}%
"""

        return report
