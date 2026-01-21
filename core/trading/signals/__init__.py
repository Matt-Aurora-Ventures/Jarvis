"""
JARVIS Trading Signals Module

Signal generators for various trading strategies.
"""

from .liquidation import LiquidationSignal, LiquidationAnalyzer
from .dual_ma import DualMASignal, TrendFilter
from .meta_labeler import MetaLabeler

# Advanced strategies
from .trailing_stop import TrailingStopSignal, TrailingStopAnalyzer
from .rsi_strategy import RSISignal, RSIAnalyzer
from .macd_strategy import MACDSignal, MACDAnalyzer
from .dca_strategy import DCASignal, DCAAnalyzer
from .mean_reversion import MeanReversionSignal, MeanReversionAnalyzer
from .breakout_strategy import BreakoutSignal, BreakoutAnalyzer
from .volume_profile_strategy import VolumeProfileSignal, VolumeProfileAnalyzer
from .take_profit import (
    TakeProfitType,
    TakeProfitLevel,
    TakeProfitSignal,
    TakeProfitAnalyzer,
    calculate_fibonacci_levels,
)

__all__ = [
    # Original signals
    'LiquidationSignal',
    'LiquidationAnalyzer',
    'DualMASignal',
    'TrendFilter',
    'MetaLabeler',
    # Advanced strategies
    'TrailingStopSignal',
    'TrailingStopAnalyzer',
    'RSISignal',
    'RSIAnalyzer',
    'MACDSignal',
    'MACDAnalyzer',
    'DCASignal',
    'DCAAnalyzer',
    'MeanReversionSignal',
    'MeanReversionAnalyzer',
    'BreakoutSignal',
    'BreakoutAnalyzer',
    'VolumeProfileSignal',
    'VolumeProfileAnalyzer',
    # Take-profit strategies
    'TakeProfitType',
    'TakeProfitLevel',
    'TakeProfitSignal',
    'TakeProfitAnalyzer',
    'calculate_fibonacci_levels',
]
