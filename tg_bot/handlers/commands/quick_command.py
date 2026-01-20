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

logger = logging.getLogger(__name__)


@error_handler
async def quick_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /quick or /q command - condensed menu of most-used actions."""
    config = get_config()
    user_id = update.effective_user.id
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

    # Route to appropriate handler
    if callback_data == "quick_positions":
        # Call portfolio handler directly with query
        await _handle_positions_quick(query)

    elif callback_data == "quick_balance":
        # Call balance handler directly with query
        await _handle_balance_quick(query)

    elif callback_data == "quick_market":
        # Show market summary
        await _quick_market_summary(query, context)

    elif callback_data == "quick_wallet":
        # Call wallet handler
        await _handle_wallet_quick(query)

    elif callback_data == "quick_alerts":
        # Show recent alerts
        await _quick_alerts(query, context)

    elif callback_data == "quick_report":
        # Call report handler
        await _handle_report_quick(query)

    elif callback_data == "quick_health":
        # Call health handler
        await _handle_health_quick(query)

    elif callback_data == "quick_stats":
        # Call stats handler
        await _handle_stats_quick(query)

    elif callback_data == "quick_dashboard":
        # Call dashboard handler
        await _handle_dashboard_quick(query)

    elif callback_data == "quick_trending":
        # Call trending handler
        await _handle_trending_quick(query)

    elif callback_data == "quick_full_menu":
        # Return to main menu
        await _handle_full_menu_quick(query)


async def _handle_positions_quick(query):
    """Handle quick positions callback."""
    try:
        from tg_bot.handlers.treasury import TreasuryHandler
        handler = TreasuryHandler()

        # Create minimal update-like object
        class QuickUpdate:
            def __init__(self, query):
                self.message = query.message
                self.effective_user = None
                self.effective_chat = None

        class QuickContext:
            pass

        quick_update = QuickUpdate(query)
        quick_context = QuickContext()

        await handler.handle_portfolio(quick_update, quick_context)
    except Exception as e:
        logger.error(f"Quick positions error: {e}")
        await query.message.reply_text("❌ Failed to load positions", parse_mode=ParseMode.MARKDOWN)


async def _handle_balance_quick(query):
    """Handle quick balance callback."""
    try:
        from tg_bot.handlers.treasury import TreasuryHandler
        handler = TreasuryHandler()

        class QuickUpdate:
            def __init__(self, query):
                self.message = query.message
                self.effective_user = None
                self.effective_chat = None

        class QuickContext:
            pass

        quick_update = QuickUpdate(query)
        quick_context = QuickContext()

        await handler.handle_balance(quick_update, quick_context)
    except Exception as e:
        logger.error(f"Quick balance error: {e}")
        await query.message.reply_text("❌ Failed to load balance", parse_mode=ParseMode.MARKDOWN)


async def _handle_wallet_quick(query):
    """Handle quick wallet callback."""
    await query.message.reply_text(
        "💵 *Wallet*\n\nUse /wallet for full wallet info.",
        parse_mode=ParseMode.MARKDOWN,
    )


async def _handle_report_quick(query):
    """Handle quick report callback."""
    await query.message.reply_text(
        "📑 *Report*\n\nGenerating report... Use /report for full details.",
        parse_mode=ParseMode.MARKDOWN,
    )


async def _handle_health_quick(query):
    """Handle quick health callback."""
    await query.message.reply_text(
        "💊 *Health*\n\nUse /health for full system health check.",
        parse_mode=ParseMode.MARKDOWN,
    )


async def _handle_stats_quick(query):
    """Handle quick stats callback."""
    await query.message.reply_text(
        "📊 *Stats*\n\nUse /stats for full CLI statistics.",
        parse_mode=ParseMode.MARKDOWN,
    )


async def _handle_dashboard_quick(query):
    """Handle quick dashboard callback."""
    await query.message.reply_text(
        "📈 *Dashboard*\n\nUse /dashboard for full trading dashboard.",
        parse_mode=ParseMode.MARKDOWN,
    )


async def _handle_trending_quick(query):
    """Handle quick trending callback."""
    await query.message.reply_text(
        "🎯 *Trending*\n\nUse /trending for full trending tokens.",
        parse_mode=ParseMode.MARKDOWN,
    )


async def _handle_full_menu_quick(query):
    """Handle quick full menu callback."""
    await query.message.reply_text(
        "📋 *Full Menu*\n\nUse /start for full bot menu.",
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
