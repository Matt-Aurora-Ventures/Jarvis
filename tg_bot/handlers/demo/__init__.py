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

For backward compatibility, you can still use:
    from tg_bot.handlers.demo_legacy import demo, demo_callback
"""

# Import from legacy module for backward compatibility
from tg_bot.handlers.demo_legacy import (
    demo,
    demo_callback,
    demo_message_handler,
    register_demo_handlers,
    JarvisTheme,
    DemoMenuBuilder,
    safe_symbol,
)

# Import from modular components
from tg_bot.handlers.demo.demo_trading import (
    execute_buy_with_tpsl,
    get_bags_client,
    get_trade_intelligence,
    get_success_fee_manager,
    validate_buy_amount,
    _get_jupiter_client,  # For testing
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

__all__ = [
    # Main handlers (from legacy)
    "demo",
    "demo_callback",
    "demo_message_handler",
    "register_demo_handlers",
    # UI (from legacy)
    "JarvisTheme",
    "DemoMenuBuilder",
    "safe_symbol",
    # Trading (modular)
    "execute_buy_with_tpsl",
    "get_bags_client",
    "get_trade_intelligence",
    "get_success_fee_manager",
    "validate_buy_amount",
    # Sentiment (modular)
    "get_market_regime",
    "get_ai_sentiment_for_token",
    "get_trending_with_sentiment",
    "get_conviction_picks",
    "get_bags_top_tokens_with_sentiment",
    "get_cached_sentiment_tokens",
    "get_cached_macro_sentiment",
    "get_sentiment_cache_age",
    # Orders (modular)
    "_background_tp_sl_monitor",
    "_process_demo_exit_checks",
    # Callback router (Phase 2)
    "CallbackRouter",
    "DemoContextLoader",
    "get_callback_router",
]
