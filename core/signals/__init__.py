"""
JARVIS Signal System

Multi-source signal fusion, position sizing, and trade execution.
Combines technical analysis, sentiment, whale activity, and ML predictions.

Prompts #128-135: Signal Processing
"""

from .fusion import (
    SignalFusion,
    FusedSignal,
    SignalSource,
    SignalWeight,
    get_signal_fusion,
)
from .position_sizer import (
    PositionSizer,
    PositionSize,
    SizingMethod,
    RiskParameters,
    get_position_sizer,
)
from .signal_aggregator import (
    SignalAggregator,
    StrategySignal,
    AggregatedSignal,
    StrategyPerformance,
    SignalAction,
    ConsensusType,
    aggregate_signals,
    get_signal_aggregator,
)

__all__ = [
    # Fusion
    "SignalFusion",
    "FusedSignal",
    "SignalSource",
    "SignalWeight",
    "get_signal_fusion",
    # Position Sizing
    "PositionSizer",
    "PositionSize",
    "SizingMethod",
    "RiskParameters",
    "get_position_sizer",
    # Signal Aggregation
    "SignalAggregator",
    "StrategySignal",
    "AggregatedSignal",
    "StrategyPerformance",
    "SignalAction",
    "ConsensusType",
    "aggregate_signals",
    "get_signal_aggregator",
]
