"""
Market data service adapters.

Provides unified interface for crypto market data from various providers.
"""

from .birdeye_adapter import BirdEyeMarketAdapter

__all__ = ["BirdEyeMarketAdapter"]
