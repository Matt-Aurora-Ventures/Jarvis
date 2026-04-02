"""
Demo Bot - Main Entry Point

This module provides backward-compatible imports from the modular demo package.
The actual implementation is split across:
- demo/demo_core.py - Main handlers
- demo/demo_trading.py - Trade execution
- demo/demo_sentiment.py - Sentiment analysis
- demo/demo_orders.py - TP/SL management
- demo/demo_ui.py - UI components (re-exports from demo_legacy.py)
- demo_legacy.py - Original monolithic implementation

For new code, prefer importing from tg_bot.handlers.demo package directly.
"""

# Re-export everything from the legacy module for backward compatibility
from tg_bot.handlers.demo_legacy import *

# Also import from modular components to ensure they're available
from tg_bot.handlers.demo.demo_trading import (
    execute_buy_with_tpsl,
    validate_buy_amount,
)
from tg_bot.handlers.demo.demo_sentiment import (
    get_market_regime,
    get_ai_sentiment_for_token,
    get_trending_with_sentiment,
    get_conviction_picks,
    get_bags_top_tokens_with_sentiment,
)
from tg_bot.handlers.demo.demo_orders import (
    _background_tp_sl_monitor as background_tp_sl_monitor_v2,
    _process_demo_exit_checks as process_exit_checks_v2,
)
