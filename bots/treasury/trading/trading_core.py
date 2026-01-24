"""
Trading Core

Public entry points for treasury trading. This module is the canonical
import surface for TradingEngine and TreasuryTrader after refactor.
"""

from .trading_engine import TradingEngine
from .treasury_trader import TreasuryTrader, _SimpleWallet

__all__ = [
    "TradingEngine",
    "TreasuryTrader",
    "_SimpleWallet",
]
