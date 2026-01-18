"""
Advanced Backtesting Module

Provides:
- AdvancedBacktestEngine: Full-featured backtesting with metrics
- WalkForwardAnalyzer: Walk-forward analysis for overfitting detection
- MonteCarloSimulator: Monte Carlo simulation for risk analysis
- ParameterOptimizer: Grid search parameter optimization
"""

from core.backtesting.backtest_engine import (
    AdvancedBacktestEngine,
    BacktestConfig,
    BacktestMetrics,
    BacktestResult,
)
from core.backtesting.walk_forward import WalkForwardAnalyzer
from core.backtesting.monte_carlo import MonteCarloSimulator
from core.backtesting.parameter_optimizer import ParameterOptimizer

__all__ = [
    'AdvancedBacktestEngine',
    'BacktestConfig',
    'BacktestMetrics',
    'BacktestResult',
    'WalkForwardAnalyzer',
    'MonteCarloSimulator',
    'ParameterOptimizer',
]
