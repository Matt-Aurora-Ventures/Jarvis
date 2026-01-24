"""
Demo Bot - Callback Handlers Package

Each module handles a specific category of callbacks:
- navigation: main, refresh, close
- wallet: wallet operations
- position: position management
- buy: buy operations
- sell: sell operations
- settings: bot settings
- sentiment_hub: sentiment hub
- trading: trading views
- dca: DCA plans
- bags: Bags.fm integration
- alerts: P&L alerts
- snipe: snipe operations
- watchlist: token watchlist
- analysis: token analysis
- learning: learning dashboard
- chart: chart generation
- misc: miscellaneous
"""

from tg_bot.handlers.demo.callbacks.navigation import handle_navigation
from tg_bot.handlers.demo.callbacks.wallet import handle_wallet
from tg_bot.handlers.demo.callbacks.position import handle_position
from tg_bot.handlers.demo.callbacks.buy import handle_buy
from tg_bot.handlers.demo.callbacks.sell import handle_sell
from tg_bot.handlers.demo.callbacks.settings import handle_settings
from tg_bot.handlers.demo.callbacks.sentiment_hub import handle_sentiment_hub
from tg_bot.handlers.demo.callbacks.trading import handle_trading
from tg_bot.handlers.demo.callbacks.dca import handle_dca
from tg_bot.handlers.demo.callbacks.bags import handle_bags
from tg_bot.handlers.demo.callbacks.alerts import handle_alerts
from tg_bot.handlers.demo.callbacks.snipe import handle_snipe
from tg_bot.handlers.demo.callbacks.watchlist import handle_watchlist
from tg_bot.handlers.demo.callbacks.analysis import handle_analysis
from tg_bot.handlers.demo.callbacks.learning import handle_learning
from tg_bot.handlers.demo.callbacks.chart import handle_chart
from tg_bot.handlers.demo.callbacks.misc import handle_misc

__all__ = [
    "handle_navigation",
    "handle_wallet",
    "handle_position",
    "handle_buy",
    "handle_sell",
    "handle_settings",
    "handle_sentiment_hub",
    "handle_trading",
    "handle_dca",
    "handle_bags",
    "handle_alerts",
    "handle_snipe",
    "handle_watchlist",
    "handle_analysis",
    "handle_learning",
    "handle_chart",
    "handle_misc",
]
