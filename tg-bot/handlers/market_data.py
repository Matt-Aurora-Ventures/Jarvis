"""Market data command handlers.

Handles: price, chart, volume, mcap, liquidity, gainers, losers, newpairs, solprice
Extracted from bot_core.py to reduce file size.
"""

import logging
from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from tg_bot.handlers import error_handler
from tg_bot.services import digest_formatter as fmt

logger = logging.getLogger(__name__)


# Market data commands are currently defined in bot_core.py
# This module provides a foundation for future extraction.
# Import these from bot_core.py for now until full migration.

# To complete migration:
# 1. Move price(), chart(), volume(), mcap(), liquidity() here
# 2. Move gainers(), losers(), newpairs(), solprice() here
# 3. Update bot_core.py to import from this module
# 4. Update handler registration in bot.py

__all__ = [
    # Future exports after migration:
    # "price",
    # "chart", 
    # "volume",
    # "mcap",
    # "liquidity",
    # "gainers",
    # "losers",
    # "newpairs",
    # "solprice",
]
