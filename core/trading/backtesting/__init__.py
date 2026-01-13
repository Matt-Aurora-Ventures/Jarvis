"""
JARVIS Backtesting & Robustness Testing Framework

Implements comprehensive strategy validation:
1. Hold-out out-of-sample testing
2. Walk-forward testing
3. Parameter heat maps
4. Permutation tests
5. Monte Carlo resampling
"""

from .validator import StrategyValidator
from .walk_forward import WalkForwardTester
from .metrics import PerformanceMetrics, calculate_sharpe, calculate_sortino, calculate_calmar

__all__ = [
    'StrategyValidator',
    'WalkForwardTester',
    'PerformanceMetrics',
    'calculate_sharpe',
    'calculate_sortino',
    'calculate_calmar',
]
