"""
Treasury Bot Handler Integration

Registers all Treasury Bot commands and callbacks with the Telegram application.
"""

import logging
from typing import List

from telegram.ext import Application, CommandHandler, CallbackQueryHandler

from tg_bot.services.treasury_bot import TreasuryBot
from bots.treasury.trading import TradingEngine

logger = logging.getLogger(__name__)


def register_treasury_handlers(
    app: Application,
    trading_engine: TradingEngine,
    admin_ids: List[int],
    bot_token: str,
) -> TreasuryBot:
    """
    Register all Treasury Bot handlers with the Telegram application.

    Args:
        app: Telegram Application instance
        trading_engine: TradingEngine instance
        admin_ids: List of admin user IDs
        bot_token: Telegram bot token

    Returns:
        TreasuryBot instance for monitoring control
    """
    treasury_bot = TreasuryBot(
        trading_engine=trading_engine,
        admin_ids=admin_ids,
        bot_token=bot_token,
    )

    # Register command handlers
    app.add_handler(CommandHandler(
        "treasury_dashboard",
        treasury_bot.cmd_dashboard
    ))

    app.add_handler(CommandHandler(
        "treasury_positions",
        treasury_bot.cmd_positions
    ))

    app.add_handler(CommandHandler(
        "treasury_trades",
        treasury_bot.cmd_trades
    ))

    app.add_handler(CommandHandler(
        "treasury_report",
        treasury_bot.cmd_report
    ))

    app.add_handler(CommandHandler(
        "treasury_settings",
        treasury_bot.cmd_settings
    ))

    app.add_handler(CommandHandler(
        "treasury_help",
        treasury_bot.cmd_help
    ))

    # Register callback handlers
    app.add_handler(CallbackQueryHandler(
        treasury_bot.handle_callback
    ))

    logger.info(f"Treasury Bot handlers registered for {len(admin_ids)} admins")

    return treasury_bot
