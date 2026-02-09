"""
Demo Bot - Callback Handler Router

This module extracts the massive demo_callback function into logical handlers.
Each handler category is <200 lines and focuses on a specific callback domain.

Callback Categories:
- Navigation: main, refresh, close, noop
- Wallet: wallet_*, export_key, receive_sol, send_sol
- Position: positions*, pos_adjust, adj_tp/sl, trailing_stops, tsl_*
- Buy: buy:*, execute_buy:*, quick_buy:*, buy_custom:*
- Sell: sell:*, sell_all, execute_sell_all
- Settings: settings, ai_auto_*, toggle_mode
- Sentiment Hub: hub, hub_*, ai_picks, ai_report, trending
- DCA: dca, dca_*
- Bags.fm: bags_fm, bags_*
- Alerts: pnl_alerts, alert_*, delete_pos_alerts
- Orders: TP/SL adjustment handlers
- Snipe: insta_snipe, snipe_*
- Watchlist: watchlist, watchlist_*
- Analysis: analyze:*, token_search, token_input
- Learning: learning, learning_deep, performance, trade_history
- Chart: chart:*, view_chart
"""

import logging
import asyncio
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime, timezone, timedelta

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

logger = logging.getLogger(__name__)


# =============================================================================
# Callback Router
# =============================================================================


class CallbackRouter:
    """
    Routes demo:* callbacks to the appropriate handler function.

    This is the main entry point that replaces the massive if/elif chain
    in the original demo_callback function.
    """

    def __init__(self, context_loader):
        """
        Initialize router with context loader for shared state.

        Args:
            context_loader: Object that provides access to:
                - get_demo_engine()
                - get_market_regime()
                - get_ai_sentiment_for_token()
                - DemoMenuBuilder
                - JarvisTheme
                - etc.
        """
        self.ctx = context_loader
        self._handlers = self._build_handler_map()

    def _build_handler_map(self) -> Dict[str, callable]:
        """Build mapping from action patterns to handler functions."""
        return {
            # Navigation
            "main": self.handle_navigation,
            "refresh": self.handle_navigation,
            "close": self.handle_navigation,
            "noop": self.handle_navigation,

            # Wallet
            "wallet_menu": self.handle_wallet,
            "wallet_create": self.handle_wallet,
            "wallet_import": self.handle_wallet,
            "wallet_activity": self.handle_wallet,
            "wallet_reset_confirm": self.handle_wallet,
            "token_holdings": self.handle_wallet,
            "export_key_confirm": self.handle_wallet,
            "export_key": self.handle_wallet,
            "receive_sol": self.handle_wallet,
            "send_sol": self.handle_wallet,
            "import_mode_key": self.handle_wallet,
            "import_mode_seed": self.handle_wallet,

            # Positions
            "positions": self.handle_position,
            "positions_all": self.handle_position,
            "pnl_report": self.handle_position,
            "trailing_stops": self.handle_position,
            "tsl_new": self.handle_position,
            "adj_cancel": self.handle_position,

            # Settings
            "settings": self.handle_settings,
            "ai_auto_settings": self.handle_settings,
            "ai_auto_status": self.handle_settings,
            "ai_trades_history": self.handle_settings,
            "fee_stats": self.handle_settings,
            "toggle_mode": self.handle_settings,

            # Sentiment Hub
            "hub": self.handle_sentiment_hub,
            "hub_news": self.handle_sentiment_hub,
            "hub_traditional": self.handle_sentiment_hub,
            "hub_wallet": self.handle_sentiment_hub,

            # Trading
            "trending": self.handle_trading,
            "ai_picks": self.handle_trading,
            "ai_report": self.handle_trading,
            "quick_trade": self.handle_trading,
            "sell_all": self.handle_sell,
            "execute_sell_all": self.handle_sell,
            "token_input": self.handle_trading,
            "token_search": self.handle_trading,
            "copy_ca": self.handle_trading,
            "snipe_mode": self.handle_snipe,
            "snipe_disable": self.handle_snipe,

            # Insta Snipe
            "insta_snipe": self.handle_snipe,

            # DCA
            "dca": self.handle_dca,
            "dca_new": self.handle_dca,
            "dca_history": self.handle_dca,
            "dca_input": self.handle_dca,

            # Bags.fm
            "bags_fm": self.handle_bags,
            "bags_settings": self.handle_bags,

            # Alerts
            "pnl_alerts": self.handle_alerts,
            "clear_triggered_alerts": self.handle_alerts,

            # Watchlist
            "watchlist": self.handle_watchlist,
            "watchlist_add": self.handle_watchlist,

            # Learning & Performance
            "learning": self.handle_learning,
            "learning_deep": self.handle_learning,
            "performance": self.handle_learning,
            "trade_history": self.handle_learning,
            "pnl_chart": self.handle_learning,
            "leaderboard": self.handle_learning,
            "goals": self.handle_learning,

            # Chart
            "view_chart": self.handle_chart,

            # TP/SL Settings
            "tpsl_settings": self.handle_tpsl,
            "tpsl_quick": self.handle_tpsl,
            "tpsl_custom_tp": self.handle_tpsl,
            "tpsl_custom_sl": self.handle_tpsl,
            "ladder_menu": self.handle_tpsl,
            "ladder_disable": self.handle_tpsl,

            # Other
            "new_pairs": self.handle_misc,
            "balance": self.handle_wallet,
        }

    async def route(
        self,
        action: str,
        data: str,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        shared_state: Dict[str, Any],
    ) -> Tuple[str, InlineKeyboardMarkup]:
        """
        Route a callback to the appropriate handler.

        Args:
            action: The action extracted from callback_data (demo:action:...)
            data: The full callback_data string
            update: Telegram update object
            context: Bot context
            shared_state: Preloaded state (wallet_address, positions, market_regime, etc.)

        Returns:
            Tuple of (message_text, keyboard)
        """
        # Check for exact match first
        if action in self._handlers:
            return await self._handlers[action](action, data, update, context, shared_state)

        # Check for prefix patterns
        if data.startswith("demo:sell:"):
            return await self.handle_sell(action, data, update, context, shared_state)

        if data.startswith("demo:buy:") or data.startswith("demo:execute_buy:") or data.startswith("demo:quick_buy:"):
            return await self.handle_buy(action, data, update, context, shared_state)

        if data.startswith("demo:buy_custom:"):
            return await self.handle_buy(action, data, update, context, shared_state)

        if data.startswith("demo:pos_adjust:") or data.startswith("demo:set_tp:") or data.startswith("demo:set_sl:"):
            return await self.handle_position(action, data, update, context, shared_state)

        if data.startswith("demo:adj_tp:") or data.startswith("demo:adj_sl:") or data.startswith("demo:adj_save:"):
            return await self.handle_position(action, data, update, context, shared_state)

        if data.startswith("demo:tsl_"):
            return await self.handle_position(action, data, update, context, shared_state)

        if data.startswith("demo:trailing_setup:"):
            return await self.handle_position(action, data, update, context, shared_state)

        if data.startswith("demo:ai_auto_toggle:") or data.startswith("demo:ai_risk:") or data.startswith("demo:ai_max:") or data.startswith("demo:ai_conf:"):
            return await self.handle_settings(action, data, update, context, shared_state)

        if data.startswith("demo:hub_"):
            return await self.handle_sentiment_hub(action, data, update, context, shared_state)

        if data.startswith("demo:dca_"):
            return await self.handle_dca(action, data, update, context, shared_state)

        if data.startswith("demo:bags_"):
            return await self.handle_bags(action, data, update, context, shared_state)

        if data.startswith("demo:alert_") or data.startswith("demo:create_alert:") or data.startswith("demo:delete_pos_alerts:") or data.startswith("demo:custom_alert:"):
            return await self.handle_alerts(action, data, update, context, shared_state)

        if data.startswith("demo:snipe_"):
            return await self.handle_snipe(action, data, update, context, shared_state)

        if data.startswith("demo:watchlist_"):
            return await self.handle_watchlist(action, data, update, context, shared_state)

        if data.startswith("demo:analyze:"):
            return await self.handle_analysis(action, data, update, context, shared_state)

        if data.startswith("demo:history_page:"):
            return await self.handle_learning(action, data, update, context, shared_state)

        if data.startswith("demo:chart:"):
            return await self.handle_chart(action, data, update, context, shared_state)

        # TP/SL Settings
        if data.startswith("demo:tpsl_") or data.startswith("demo:ladder_"):
            return await self.handle_tpsl(action, data, update, context, shared_state)

        if data.startswith("demo:edit_tpsl:") or data.startswith("demo:pos_tp:") or data.startswith("demo:pos_sl:"):
            return await self.handle_tpsl(action, data, update, context, shared_state)

        # Default: return to main menu
        return await self.handle_navigation("main", "demo:main", update, context, shared_state)

    # =========================================================================
    # Handler Stubs - Implemented in separate files for maintainability
    # =========================================================================

    async def handle_navigation(self, action, data, update, context, state) -> Tuple[str, InlineKeyboardMarkup]:
        """Handle main, refresh, close, noop."""
        from tg_bot.handlers.demo.callbacks.navigation import handle_navigation
        return await handle_navigation(self.ctx, action, data, update, context, state)

    async def handle_wallet(self, action, data, update, context, state) -> Tuple[str, InlineKeyboardMarkup]:
        """Handle wallet_*, export_key, receive_sol, send_sol."""
        from tg_bot.handlers.demo.callbacks.wallet import handle_wallet
        return await handle_wallet(self.ctx, action, data, update, context, state)

    async def handle_position(self, action, data, update, context, state) -> Tuple[str, InlineKeyboardMarkup]:
        """Handle positions*, pos_adjust, trailing_stops, tsl_*, adj_tp/sl."""
        from tg_bot.handlers.demo.callbacks.position import handle_position
        return await handle_position(self.ctx, action, data, update, context, state)

    async def handle_buy(self, action, data, update, context, state) -> Tuple[str, InlineKeyboardMarkup]:
        """Handle buy:*, execute_buy:*, quick_buy:*, buy_custom:*."""
        from tg_bot.handlers.demo.callbacks.buy import handle_buy
        return await handle_buy(self.ctx, action, data, update, context, state)

    async def handle_sell(self, action, data, update, context, state) -> Tuple[str, InlineKeyboardMarkup]:
        """Handle sell:*, sell_all, execute_sell_all."""
        from tg_bot.handlers.demo.callbacks.sell import handle_sell
        return await handle_sell(self.ctx, action, data, update, context, state)

    async def handle_settings(self, action, data, update, context, state) -> Tuple[str, InlineKeyboardMarkup]:
        """Handle settings, ai_auto_*, toggle_mode."""
        from tg_bot.handlers.demo.callbacks.settings import handle_settings
        return await handle_settings(self.ctx, action, data, update, context, state)

    async def handle_sentiment_hub(self, action, data, update, context, state) -> Tuple[str, InlineKeyboardMarkup]:
        """Handle hub, hub_*."""
        from tg_bot.handlers.demo.callbacks.sentiment_hub import handle_sentiment_hub
        return await handle_sentiment_hub(self.ctx, action, data, update, context, state)

    async def handle_trading(self, action, data, update, context, state) -> Tuple[str, InlineKeyboardMarkup]:
        """Handle trending, ai_picks, ai_report, quick_trade, token_*."""
        from tg_bot.handlers.demo.callbacks.trading import handle_trading
        return await handle_trading(self.ctx, action, data, update, context, state)

    async def handle_dca(self, action, data, update, context, state) -> Tuple[str, InlineKeyboardMarkup]:
        """Handle dca, dca_*."""
        from tg_bot.handlers.demo.callbacks.dca import handle_dca
        return await handle_dca(self.ctx, action, data, update, context, state)

    async def handle_bags(self, action, data, update, context, state) -> Tuple[str, InlineKeyboardMarkup]:
        """Handle bags_fm, bags_*."""
        from tg_bot.handlers.demo.callbacks.bags import handle_bags
        return await handle_bags(self.ctx, action, data, update, context, state)

    async def handle_alerts(self, action, data, update, context, state) -> Tuple[str, InlineKeyboardMarkup]:
        """Handle pnl_alerts, alert_*, create_alert:*, delete_pos_alerts:*."""
        from tg_bot.handlers.demo.callbacks.alerts import handle_alerts
        return await handle_alerts(self.ctx, action, data, update, context, state)

    async def handle_snipe(self, action, data, update, context, state) -> Tuple[str, InlineKeyboardMarkup]:
        """Handle insta_snipe, snipe_*."""
        from tg_bot.handlers.demo.callbacks.snipe import handle_snipe
        return await handle_snipe(self.ctx, action, data, update, context, state)

    async def handle_watchlist(self, action, data, update, context, state) -> Tuple[str, InlineKeyboardMarkup]:
        """Handle watchlist, watchlist_*."""
        from tg_bot.handlers.demo.callbacks.watchlist import handle_watchlist
        return await handle_watchlist(self.ctx, action, data, update, context, state)

    async def handle_analysis(self, action, data, update, context, state) -> Tuple[str, InlineKeyboardMarkup]:
        """Handle analyze:*."""
        from tg_bot.handlers.demo.callbacks.analysis import handle_analysis
        return await handle_analysis(self.ctx, action, data, update, context, state)

    async def handle_learning(self, action, data, update, context, state) -> Tuple[str, InlineKeyboardMarkup]:
        """Handle learning, performance, trade_history."""
        from tg_bot.handlers.demo.callbacks.learning import handle_learning
        return await handle_learning(self.ctx, action, data, update, context, state)

    async def handle_chart(self, action, data, update, context, state) -> Tuple[str, InlineKeyboardMarkup]:
        """Handle chart:*, view_chart."""
        from tg_bot.handlers.demo.callbacks.chart import handle_chart
        return await handle_chart(self.ctx, action, data, update, context, state)

    async def handle_misc(self, action, data, update, context, state) -> Tuple[str, InlineKeyboardMarkup]:
        """Handle miscellaneous callbacks like new_pairs."""
        from tg_bot.handlers.demo.callbacks.misc import handle_misc
        return await handle_misc(self.ctx, action, data, update, context, state)

    async def handle_tpsl(self, action, data, update, context, state) -> Tuple[str, InlineKeyboardMarkup]:
        """Handle TP/SL settings, ladder exits."""
        from tg_bot.handlers.demo.callbacks.tpsl import handle_tpsl
        return await handle_tpsl(self.ctx, action, data, update, context, state)


# =============================================================================
# Context Loader - Provides shared utilities to handlers
# =============================================================================


class DemoContextLoader:
    """
    Provides lazy-loaded access to demo bot utilities.

    This avoids circular imports and keeps handlers lightweight.
    """

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._menu_builder = None
        self._theme = None

    @property
    def DemoMenuBuilder(self):
        """Lazy load DemoMenuBuilder."""
        if self._menu_builder is None:
            from tg_bot.handlers.demo.demo_ui import DemoMenuBuilder
            self._menu_builder = DemoMenuBuilder
        return self._menu_builder

    @property
    def JarvisTheme(self):
        """Lazy load JarvisTheme."""
        if self._theme is None:
            from tg_bot.handlers.demo.demo_ui import JarvisTheme
            self._theme = JarvisTheme
        return self._theme

    @staticmethod
    def safe_symbol(symbol: str) -> str:
        """Sanitize token symbol for safe display."""
        from tg_bot.handlers.demo.demo_ui import safe_symbol
        return safe_symbol(symbol)

    @staticmethod
    async def get_demo_engine():
        """Get demo trading engine."""
        from tg_bot.handlers.demo.demo_trading import _get_demo_engine
        return await _get_demo_engine()

    @staticmethod
    async def get_market_regime():
        """Get current market regime."""
        from tg_bot.handlers.demo.demo_sentiment import get_market_regime
        return await get_market_regime()

    @staticmethod
    async def get_ai_sentiment_for_token(address: str):
        """Get AI sentiment for a token."""
        from tg_bot.handlers.demo.demo_sentiment import get_ai_sentiment_for_token
        return await get_ai_sentiment_for_token(address)

    @staticmethod
    async def get_trending_with_sentiment():
        """Get trending tokens with sentiment."""
        from tg_bot.handlers.demo.demo_sentiment import get_trending_with_sentiment
        return await get_trending_with_sentiment()

    @staticmethod
    async def get_conviction_picks():
        """Get AI conviction picks."""
        from tg_bot.handlers.demo.demo_sentiment import get_conviction_picks
        return await get_conviction_picks()

    @staticmethod
    async def get_bags_top_tokens_with_sentiment(limit: int = 15):
        """Get Bags.fm top tokens with sentiment."""
        from tg_bot.handlers.demo.demo_sentiment import get_bags_top_tokens_with_sentiment
        return await get_bags_top_tokens_with_sentiment(limit=limit)

    @staticmethod
    def get_trade_intelligence():
        """Get trade intelligence engine."""
        from tg_bot.handlers.demo.demo_trading import get_trade_intelligence
        return get_trade_intelligence()

    @staticmethod
    def get_success_fee_manager():
        """Get success fee manager."""
        from tg_bot.handlers.demo.demo_trading import get_success_fee_manager
        return get_success_fee_manager()

    @staticmethod
    def get_bags_client():
        """Get Bags.fm API client."""
        from tg_bot.handlers.demo.demo_trading import get_bags_client
        return get_bags_client()

    @staticmethod
    def register_token_id(context, token_address: str) -> str:
        """Register a short callback-safe token id."""
        from tg_bot.handlers.demo.demo_trading import _register_token_id
        return _register_token_id(context, token_address)

    @staticmethod
    def resolve_token_ref(context, token_ref: str) -> str:
        """Resolve short token id back to full address."""
        from tg_bot.handlers.demo.demo_trading import _resolve_token_ref
        return _resolve_token_ref(context, token_ref)

    @staticmethod
    def get_token_address(context, token_id: str) -> str:
        """Alias for resolve_token_ref for backwards compatibility."""
        from tg_bot.handlers.demo.demo_trading import _resolve_token_ref
        return _resolve_token_ref(context, token_id)

    @staticmethod
    async def execute_swap_with_fallback(**kwargs):
        """Execute swap via Bags.fm with Jupiter fallback."""
        from tg_bot.handlers.demo.demo_trading import _execute_swap_with_fallback
        return await _execute_swap_with_fallback(**kwargs)

    @staticmethod
    async def execute_buy_with_tpsl(**kwargs):
        """Execute buy with mandatory TP/SL via Bags.fm (optional Jupiter fallback)."""
        from tg_bot.handlers.demo.demo_trading import execute_buy_with_tpsl
        return await execute_buy_with_tpsl(**kwargs)

    @staticmethod
    async def resolve_wallet_address(context) -> Optional[str]:
        """Resolve the wallet address to use for demo trading (treasury fallback)."""
        from tg_bot.handlers.demo.demo_trading import _resolve_wallet_address
        return await _resolve_wallet_address(context)

    @staticmethod
    def get_demo_slippage_bps() -> int:
        """Get demo slippage in basis points."""
        from tg_bot.handlers.demo.demo_trading import _get_demo_slippage_bps
        return _get_demo_slippage_bps()

    @staticmethod
    def grade_for_signal_name(signal_name: str):
        """Convert signal name to grade."""
        from tg_bot.handlers.demo.demo_sentiment import _grade_for_signal_name
        return _grade_for_signal_name(signal_name)

    @staticmethod
    def conviction_label(score: int) -> str:
        """Get conviction label from score."""
        from tg_bot.handlers.demo.demo_sentiment import _conviction_label
        return _conviction_label(score)

    @staticmethod
    def get_pick_stats():
        """Get AI pick statistics."""
        from tg_bot.handlers.demo.demo_sentiment import _get_pick_stats
        return _get_pick_stats()


# =============================================================================
# Factory Function
# =============================================================================


def get_callback_router() -> CallbackRouter:
    """Get singleton callback router instance."""
    ctx = DemoContextLoader()
    return CallbackRouter(ctx)


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    "CallbackRouter",
    "DemoContextLoader",
    "get_callback_router",
]
