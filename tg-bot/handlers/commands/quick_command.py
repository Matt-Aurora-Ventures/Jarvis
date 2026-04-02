"""
Quick Command Handler - /quick or /q for condensed menu of most-used actions.

Provides instant access to:
- View positions summary
- Quick market check
- Check wallet balance
- Recent alerts
- Common trading actions
"""

import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from tg_bot.handlers import error_handler
from tg_bot.config import get_config
from tg_bot.services import digest_formatter as fmt

logger = logging.getLogger(__name__)


@error_handler
async def quick_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /quick or /q command - condensed menu of most-used actions."""
    config = get_config()
    user_id = update.effective_user.id
    try:
        is_admin = config.is_admin(user_id, update.effective_user.username)
    except TypeError:
        is_admin = config.is_admin(user_id)

    # Quick intro - JARVIS voice
    if is_admin:
        message = """⚡ *QUICK ACCESS*

tap what you need. i'll handle it."""
    else:
        message = """⚡ *QUICK ACCESS*

standard user view. admin commands locked."""

    # Build keyboard with most-used actions
    keyboard = []

    # Row 1: Portfolio & Balance (universal)
    row1 = [
        InlineKeyboardButton("📊 Positions", callback_data="quick_positions"),
        InlineKeyboardButton("💰 Balance", callback_data="quick_balance"),
    ]
    keyboard.append(row1)

    # Row 2: Market & Price checks
    row2 = [
        InlineKeyboardButton("📈 Market", callback_data="quick_market"),
        InlineKeyboardButton("💵 Wallet", callback_data="quick_wallet"),
    ]
    keyboard.append(row2)

    if is_admin:
        # Row 3: Admin quick actions
        row3 = [
            InlineKeyboardButton("🔔 Alerts", callback_data="quick_alerts"),
            InlineKeyboardButton("📑 Report", callback_data="quick_report"),
        ]
        keyboard.append(row3)

        # Row 4: System status
        row4 = [
            InlineKeyboardButton("💊 Health", callback_data="quick_health"),
            InlineKeyboardButton("📊 Stats", callback_data="quick_stats"),
        ]
        keyboard.append(row4)

        # Row 5: Trading shortcuts
        row5 = [
            InlineKeyboardButton("📈 Dashboard", callback_data="quick_dashboard"),
            InlineKeyboardButton("🎯 Trending", callback_data="quick_trending"),
        ]
        keyboard.append(row5)

    # Row 6: Full menu (always available)
    row_menu = [
        InlineKeyboardButton("📋 Full Menu", callback_data="quick_full_menu"),
    ]
    keyboard.append(row_menu)

    await update.message.reply_text(
        message,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup(keyboard),
        disable_web_page_preview=True,
    )


@error_handler
async def handle_quick_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle callback queries from quick command buttons."""
    query = update.callback_query
    await query.answer()

    callback_data = query.data

    config = get_config()
    user_id = update.effective_user.id if update and update.effective_user else 0
    username = update.effective_user.username if update and update.effective_user else None
    try:
        is_admin = config.is_admin(user_id, username)
    except TypeError:
        is_admin = config.is_admin(user_id)

    admin_only_actions = {
        "quick_alerts",
        "quick_report",
        "quick_health",
        "quick_stats",
        "quick_dashboard",
        "quick_trending",
    }

    if callback_data in admin_only_actions and not is_admin:
        await query.message.reply_text(
            fmt.format_unauthorized(),
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    # Route to appropriate handler
    if callback_data == "quick_positions":
        # Call portfolio handler directly with query
        await _handle_positions_quick(query, update, context)

    elif callback_data == "quick_balance":
        # Call balance handler directly with query
        await _handle_balance_quick(query, update, context)

    elif callback_data == "quick_market":
        # Show market summary
        await _quick_market_summary(query, context)

    elif callback_data == "quick_wallet":
        # Call wallet handler
        await _handle_wallet_quick(query, update, context)

    elif callback_data == "quick_alerts":
        # Show recent alerts
        await _quick_alerts(query, context)

    elif callback_data == "quick_report":
        # Call report handler
        await _handle_report_quick(query, update, context)

    elif callback_data == "quick_health":
        # Call health handler
        await _handle_health_quick(query, update, context)

    elif callback_data == "quick_stats":
        # Call stats handler
        await _handle_stats_quick(query, update, context)

    elif callback_data == "quick_dashboard":
        # Call dashboard handler
        await _handle_dashboard_quick(query, update, context)

    elif callback_data == "quick_trending":
        # Call trending handler
        await _handle_trending_quick(query, update, context)

    elif callback_data == "quick_full_menu":
        # Return to main menu
        await _handle_full_menu_quick(query, update, context)


def _build_quick_update(update, query):
    class QuickUpdate:
        def __init__(self, update, query):
            self.message = query.message
            self.effective_user = update.effective_user
            self.effective_chat = update.effective_chat

    return QuickUpdate(update, query)


async def _handle_positions_quick(query, update, context):
    """Handle quick positions callback."""
    try:
        from tg_bot.handlers.treasury import handle_portfolio
        quick_update = _build_quick_update(update, query)
        await handle_portfolio(quick_update, context)
    except Exception as e:
        logger.error(f"Quick positions error: {e}")
        await query.message.reply_text("❌ Failed to load positions", parse_mode=ParseMode.MARKDOWN)


async def _handle_balance_quick(query, update, context):
    """Handle quick balance callback."""
    try:
        from tg_bot.handlers.treasury import handle_balance
        quick_update = _build_quick_update(update, query)
        await handle_balance(quick_update, context)
    except Exception as e:
        logger.error(f"Quick balance error: {e}")
        await query.message.reply_text("❌ Failed to load balance", parse_mode=ParseMode.MARKDOWN)


async def _handle_wallet_quick(query, update, context):
    """Handle quick wallet callback."""
    try:
        from tg_bot.handlers.trading import wallet
        quick_update = _build_quick_update(update, query)
        await wallet(quick_update, context)
    except Exception as e:
        logger.error(f"Quick wallet error: {e}")
        await query.message.reply_text(
            "❌ Wallet unavailable",
            parse_mode=ParseMode.MARKDOWN,
        )


async def _handle_report_quick(query, update, context):
    """Handle quick report callback."""
    try:
        from tg_bot.handlers.sentiment import report
        quick_update = _build_quick_update(update, query)
        await report(quick_update, context)
    except Exception as e:
        logger.error(f"Quick report error: {e}")
        await query.message.reply_text(
            "❌ Report unavailable",
            parse_mode=ParseMode.MARKDOWN,
        )


async def _handle_health_quick(query, update, context):
    """Handle quick health callback."""
    try:
        from tg_bot.handlers.system import health
        quick_update = _build_quick_update(update, query)
        await health(quick_update, context)
    except Exception as e:
        logger.error(f"Quick health error: {e}")
        await query.message.reply_text(
            "❌ Health unavailable",
            parse_mode=ParseMode.MARKDOWN,
        )


async def _handle_stats_quick(query, update, context):
    """Handle quick stats callback."""
    try:
        from tg_bot.handlers.analytics import stats_command
        quick_update = _build_quick_update(update, query)
        await stats_command(quick_update, context)
    except Exception as e:
        logger.error(f"Quick stats error: {e}")
        await query.message.reply_text(
            "❌ Stats unavailable",
            parse_mode=ParseMode.MARKDOWN,
        )


async def _handle_dashboard_quick(query, update, context):
    """Handle quick dashboard callback."""
    try:
        from tg_bot.handlers.trading import dashboard
        quick_update = _build_quick_update(update, query)
        await dashboard(quick_update, context)
    except Exception as e:
        logger.error(f"Quick dashboard error: {e}")
        await query.message.reply_text(
            "❌ Dashboard unavailable",
            parse_mode=ParseMode.MARKDOWN,
        )


async def _handle_trending_quick(query, update, context):
    """Handle quick trending callback."""
    try:
        from tg_bot.handlers.sentiment import trending
        quick_update = _build_quick_update(update, query)
        await trending(quick_update, context)
    except Exception as e:
        logger.error(f"Quick trending error: {e}")
        await query.message.reply_text(
            "❌ Trending unavailable",
            parse_mode=ParseMode.MARKDOWN,
        )


async def _handle_full_menu_quick(query, update, context):
    """Handle quick full menu callback."""
    try:
        from tg_bot.handlers.commands_base import start
        quick_update = _build_quick_update(update, query)
        await start(quick_update, context)
    except Exception as e:
        logger.error(f"Quick full menu error: {e}")
        await query.message.reply_text(
            "❌ Menu unavailable",
            parse_mode=ParseMode.MARKDOWN,
        )


async def _quick_market_summary(query, context):
    """Generate quick market summary."""
    try:
        from tg_bot.services.signal_service import get_signal_service
        service = get_signal_service()

        # Get top trending tokens
        trending = service.get_trending_tokens(limit=3)

        if not trending:
            await query.message.reply_text(
                "📈 *Market Check*\n\nno trending data available.",
                parse_mode=ParseMode.MARKDOWN,
            )
            return

        lines = ["📈 *Quick Market Check*", ""]

        for i, token in enumerate(trending, 1):
            symbol = token.get('symbol', 'Unknown')
            price = token.get('price', 0)
            change_24h = token.get('price_change_24h', 0)

            # Format change with emoji
            change_emoji = "🟢" if change_24h >= 0 else "🔴"

            lines.append(f"{i}. *{symbol}*")
            lines.append(f"   ${price:.6f} {change_emoji} {change_24h:+.2f}%")

        await query.message.reply_text(
            "\n".join(lines),
            parse_mode=ParseMode.MARKDOWN,
        )
    except Exception as e:
        logger.error(f"Quick market summary error: {e}")
        await query.message.reply_text(
            "❌ Market data unavailable",
            parse_mode=ParseMode.MARKDOWN,
        )


async def _quick_alerts(query, context):
    """Show recent alerts."""
    try:
        # Check for active alerts from treasury/trading systems
        from pathlib import Path
        import json

        # Check for exit intents (alerts)
        exit_intents_path = Path.home() / ".lifeos" / "trading" / "exit_intents.json"

        if exit_intents_path.exists():
            with open(exit_intents_path, 'r') as f:
                exit_intents = json.load(f)

            if exit_intents:
                lines = ["🔔 *Active Alerts*", ""]
                for symbol, intent in list(exit_intents.items())[:5]:
                    reason = intent.get('reason', 'Unknown')
                    timestamp = intent.get('timestamp', 'Unknown')
                    lines.append(f"• *{symbol}*: {reason}")
                    lines.append(f"  {timestamp[:19]}")

                await query.message.reply_text(
                    "\n".join(lines),
                    parse_mode=ParseMode.MARKDOWN,
                )
                return

        # No alerts
        await query.message.reply_text(
            "🔔 *Alerts*\n\nno active alerts.",
            parse_mode=ParseMode.MARKDOWN,
        )
    except Exception as e:
        logger.error(f"Quick alerts error: {e}")
        await query.message.reply_text(
            "❌ Alerts unavailable",
            parse_mode=ParseMode.MARKDOWN,
        )


__all__ = [
    'quick_command',
    'handle_quick_callback',
]
