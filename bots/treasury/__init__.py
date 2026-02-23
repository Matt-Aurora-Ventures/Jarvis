"""Jarvis Treasury Trading System.

Keep this package `__init__` lightweight.

Some treasury modules pull in optional/heavy dependencies (e.g. crypto/wallet
libraries). Importing them at package import time makes simple tasks (and unit
tests that only patch `bots.treasury.jupiter.JupiterClient`) fail in minimal
environments.

We provide lazy attribute exports for convenience without forcing all
dependencies to be present.
"""

from __future__ import annotations

from importlib import import_module
from typing import Any

# Public re-exports (resolved lazily via __getattr__).
__all__ = [
    # Wallet
    "SecureWallet",
    "WalletManager",
    "WalletInfo",
    # Jupiter
    "JupiterClient",
    "SwapQuote",
    "SwapResult",
    "LimitOrderManager",
    # Trading
    "TradingEngine",
    "Position",
    "TradeDirection",
    "RiskLevel",
    "TradeReport",
    "TreasuryTrader",
    "_SimpleWallet",
    "TradeStatus",
    # UI
    "TradingUI",
    # Backtest
    "SentimentBacktester",
    "BacktestResult",
]

_LAZY_EXPORTS: dict[str, tuple[str, str]] = {
    # Wallet
    "SecureWallet": (".wallet", "SecureWallet"),
    "WalletManager": (".wallet", "WalletManager"),
    "WalletInfo": (".wallet", "WalletInfo"),
    # Jupiter
    "JupiterClient": (".jupiter", "JupiterClient"),
    "SwapQuote": (".jupiter", "SwapQuote"),
    "SwapResult": (".jupiter", "SwapResult"),
    "LimitOrderManager": (".jupiter", "LimitOrderManager"),
    # Trading
    "TradingEngine": (".trading", "TradingEngine"),
    "Position": (".trading", "Position"),
    "TradeDirection": (".trading", "TradeDirection"),
    "RiskLevel": (".trading", "RiskLevel"),
    "TradeReport": (".trading", "TradeReport"),
    "TreasuryTrader": (".trading", "TreasuryTrader"),
    "_SimpleWallet": (".trading", "_SimpleWallet"),
    "TradeStatus": (".trading", "TradeStatus"),
    # UI
    "TradingUI": (".telegram_ui", "TradingUI"),
    # Backtest
    "SentimentBacktester": (".backtest", "SentimentBacktester"),
    "BacktestResult": (".backtest", "BacktestResult"),
}


def __getattr__(name: str) -> Any:
    target = _LAZY_EXPORTS.get(name)
    if target is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

    module_name, attr_name = target
    module = import_module(module_name, __name__)
    value = getattr(module, attr_name)
    globals()[name] = value  # cache for next access
    return value

