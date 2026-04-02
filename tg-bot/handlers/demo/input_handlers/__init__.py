"""
Demo Input Handlers - Modular text input processing.

Each module handles a specific input state:
- buy_amount: Custom buy amount entry
- watchlist: Watchlist token addition
- wallet_import: Wallet import (seed/key)
- token_input: Token address entry for buying
"""

from .buy_amount import handle_custom_buy_amount, handle_custom_hub_amount
from .watchlist import handle_watchlist_token
from .wallet_import import handle_wallet_import
from .token_input import handle_token_input

__all__ = [
    "handle_custom_buy_amount",
    "handle_custom_hub_amount",
    "handle_watchlist_token",
    "handle_wallet_import",
    "handle_token_input",
]
