"""
Strategy Optimization Module

Provides hyperparameter tuning and backtesting for trading strategies.
"""

from core.optimization.optimizer import StrategyOptimizer, OptimizationResult
from core.optimization.backtest import Backtester, BacktestResult
from core.optimization.parameter_space import ParameterSpace, Parameter

__all__ = [
    "StrategyOptimizer",
    "OptimizationResult",
    "Backtester",
    "BacktestResult",
    "ParameterSpace",
    "Parameter",
]
