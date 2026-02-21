"""
Demo Bot - Modular Package

This package contains the demo trading bot functionality split into logical modules:
- demo_core: Main handlers (demo, demo_callback, demo_message_handler)
- demo_trading: Buy/sell execution with Bags.fm/Jupiter
- demo_ui: JarvisTheme and DemoMenuBuilder UI components
- demo_sentiment: Market regime and AI sentiment functions
- demo_orders: TP/SL order management and monitoring

Usage:
    from tg_bot.handlers.demo import register_demo_handlers
    register_demo_handlers(app)

Legacy module `demo_legacy.py` remains as a fallback, but handlers now live in
`demo_core.py`.
"""

# Import core handlers (delegates to legacy until fully extracted)
from tg_bot.handlers.demo.demo_core import (
    demo,
    demo_callback,
    demo_message_handler,
    register_demo_handlers,
    JarvisTheme,
    DemoMenuBuilder,
)

from tg_bot.handlers.demo.demo_ui import safe_symbol
from tg_bot.config import get_config

# Import from modular components
from tg_bot.handlers.demo.demo_trading import (
    execute_buy_with_tpsl,
    get_bags_client,
    get_trade_intelligence,
    get_success_fee_manager,
    validate_buy_amount,
    _get_jupiter_client,  # For testing
    _get_demo_engine,  # For testing
    _execute_swap_with_fallback,  # For testing
)

from tg_bot.handlers.demo.demo_sentiment import (
    get_market_regime,
    get_ai_sentiment_for_token,
    get_trending_with_sentiment,
    get_conviction_picks,
    get_bags_top_tokens_with_sentiment,
    get_cached_sentiment_tokens,
    get_cached_macro_sentiment,
    get_sentiment_cache_age,
    _update_sentiment_cache,
)

from tg_bot.handlers.demo.demo_orders import (
    _background_tp_sl_monitor,
    _process_demo_exit_checks,
    _check_demo_exit_triggers,  # For testing
    _maybe_execute_exit,  # For testing
)

# Import callback router (Phase 2 refactoring)
from tg_bot.handlers.demo.demo_callbacks import (
    CallbackRouter,
    DemoContextLoader,
    get_callback_router,
)
from tg_bot.handlers.demo.interfaces import (
    DemoMenuService,
    DemoRequestContext,
    DemoStateStore,
    DemoTradingService,
)

__all__ = [
    # Main handlers
    "demo",
    "demo_callback",
    "demo_message_handler",
    "register_demo_handlers",
    # UI (legacy-backed for now)
    "JarvisTheme",
    "DemoMenuBuilder",
    "safe_symbol",
    "get_config",
    # Trading (modular)
    "execute_buy_with_tpsl",
    "get_bags_client",
    "get_trade_intelligence",
    "get_success_fee_manager",
    "validate_buy_amount",
    "_get_demo_engine",
    # Sentiment (modular)
    "get_market_regime",
    "get_ai_sentiment_for_token",
    "get_trending_with_sentiment",
    "get_conviction_picks",
    "get_bags_top_tokens_with_sentiment",
    "get_cached_sentiment_tokens",
    "get_cached_macro_sentiment",
    "get_sentiment_cache_age",
    "_update_sentiment_cache",
    # Orders (modular)
    "_background_tp_sl_monitor",
    "_process_demo_exit_checks",
    # Callback router (Phase 2)
    "CallbackRouter",
    "DemoContextLoader",
    "get_callback_router",
    # Domain interfaces
    "DemoRequestContext",
    "DemoStateStore",
    "DemoTradingService",
    "DemoMenuService",
]
