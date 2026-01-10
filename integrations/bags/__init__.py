"""
Bags.fm Integration Module.

Provides integration with Bags.fm for:
- Trade routing with partner fee earning
- Fee collection and tracking
- Jupiter fallback for reliability
"""

from .client import BagsClient, BagsConfig
from .fee_collector import FeeCollector, FeeCollectorConfig
from .trade_router import TradeRouter, TradeResult

__all__ = [
    "BagsClient",
    "BagsConfig",
    "FeeCollector",
    "FeeCollectorConfig",
    "TradeRouter",
    "TradeResult",
]
