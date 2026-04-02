"""
Sentiment Hub UI Handler - US-002

Main sentiment dashboard showing:
- Grok top 10 picks with grades and targets
- Macro economic analysis
- Treasury positions with live PnL
- Bags.fm recent graduations

Data Source: ~/.lifeos/trading/demo_sentiment_hub.json (updated every 15min by sentiment_updater service)

Navigation:
- /demo → sentiment → Shows sentiment hub
- Auto-refresh button for manual update
- Individual token buttons for quick buy

Architecture:
- Reads from cache (instant load, no API calls)
- sentiment_updater.py keeps data fresh in background
- Beautiful formatting with emojis and grades
"""

import logging
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

logger = logging.getLogger(__name__)


# =============================================================================
# Data Loading
# =============================================================================

def load_sentiment_hub_data() -> Dict[str, Any]:
    """Load sentiment hub data from cache."""
    from tg_bot.services.sentiment_updater import load_sentiment_hub_data
    return load_sentiment_hub_data()


def format_time_ago(iso_timestamp: Optional[str]) -> str:
    """Format ISO timestamp as 'X minutes ago'."""
    if not iso_timestamp:
        return "Never"

    try:
        from dateutil.parser import isoparse
        then = isoparse(iso_timestamp)
        now = datetime.now(timezone.utc)
        diff = (now - then).total_seconds()

        if diff < 60:
            return "Just now"
        elif diff < 3600:
            return f"{int(diff / 60)}m ago"
        elif diff < 86400:
            return f"{int(diff / 3600)}h ago"
        else:
            return f"{int(diff / 86400)}d ago"

    except Exception as e:
        logger.error(f"Failed to parse timestamp: {e}")
        return "Unknown"


# =============================================================================
# UI Formatters
# =============================================================================

def format_sentiment_hub(data: Dict[str, Any]) -> tuple[str, InlineKeyboardMarkup]:
    """
    Format sentiment hub data into Telegram message.

    Returns:
        (message_text, inline_keyboard)
    """
    # Header
    last_updated = format_time_ago(data.get("last_updated"))
    message = f"🎯 <b>SENTIMENT HUB</b>\n"
    message += f"<i>Updated: {last_updated}</i>\n\n"

    # =================================================================
    # GROK TOP 10 PICKS
    # =================================================================
    grok_picks = data.get("grok_picks", [])

    if grok_picks:
        message += "━━━━━━━━━━━━━━━━━━━━\n"
        message += "🤖 <b>GROK TOP 10 PICKS</b>\n"
        message += "━━━━━━━━━━━━━━━━━━━━\n\n"

        for i, pick in enumerate(grok_picks[:10], 1):
            symbol = pick.get("symbol", "???")
            grade = pick.get("grade", "C")
            sentiment = pick.get("sentiment_label", "NEUTRAL")
            price = pick.get("price_usd", 0)
            change_24h = pick.get("change_24h", 0)
            reasoning = pick.get("grok_reasoning", "No analysis")[:100]  # Truncate

            # Emoji based on grade
            grade_emoji = {
                "A+": "🏆", "A": "⭐", "A-": "⭐",
                "B+": "🔥", "B": "🔥", "B-": "🟢",
                "C+": "🟡", "C": "🟡", "C-": "🟠",
                "D+": "🟠", "D": "🔴", "F": "❌"
            }.get(grade, "🟡")

            # Sentiment emoji
            sentiment_emoji = {
                "BULLISH": "📈",
                "SLIGHTLY BULLISH": "📊",
                "NEUTRAL": "➖",
                "SLIGHTLY BEARISH": "📉",
                "BEARISH": "📉"
            }.get(sentiment, "➖")

            message += f"{i}. <b>{symbol}</b> {grade_emoji} {grade}\n"
            message += f"   {sentiment_emoji} {sentiment}\n"
            message += f"   💰 ${price:.8f} ({change_24h:+.1f}%)\n"
            message += f"   <i>{reasoning}...</i>\n\n"

    else:
        message += "🔍 <i>No picks available yet (service starting up)</i>\n\n"

    # =================================================================
    # MACRO ANALYSIS
    # =================================================================
    macro = data.get("macro", {})

    if macro.get("short_term") or macro.get("medium_term"):
        message += "━━━━━━━━━━━━━━━━━━━━\n"
        message += "🌍 <b>MACRO ANALYSIS</b>\n"
        message += "━━━━━━━━━━━━━━━━━━━━\n\n"

        if macro.get("short_term"):
            message += f"<b>📅 Next 24h:</b>\n{macro['short_term']}\n\n"

        if macro.get("medium_term"):
            message += f"<b>📆 Next 3 Days:</b>\n{macro['medium_term']}\n\n"

        if macro.get("long_term"):
            message += f"<b>📊 This Month:</b>\n{macro['long_term']}\n\n"

        if macro.get("key_events"):
            events_str = "\n".join(f"• {evt}" for evt in macro["key_events"][:5])
            message += f"<b>🔔 Key Events:</b>\n{events_str}\n\n"

    # =================================================================
    # TREASURY POSITIONS
    # =================================================================
    treasury = data.get("treasury_positions", [])

    if treasury:
        message += "━━━━━━━━━━━━━━━━━━━━\n"
        message += "💼 <b>TREASURY POSITIONS</b>\n"
        message += "━━━━━━━━━━━━━━━━━━━━\n\n"

        total_pnl = sum(p.get("pnl_usd", 0) for p in treasury)
        total_invested = sum(p.get("amount_sol", 0) for p in treasury)

        for pos in treasury[:5]:  # Show top 5
            symbol = pos.get("symbol", "???")
            pnl_pct = pos.get("pnl_pct", 0)
            pnl_usd = pos.get("pnl_usd", 0)
            entry = pos.get("entry_price", 0)
            current = pos.get("current_price", 0)

            emoji = "✅" if pnl_pct > 0 else "❌"
            message += f"{emoji} <b>{symbol}</b>: {pnl_pct:+.1f}% (${pnl_usd:+,.2f})\n"
            message += f"   Entry: ${entry:.6f} → ${current:.6f}\n"

        message += f"\n<b>Total PnL:</b> ${total_pnl:+,.2f}\n"
        message += f"<b>Invested:</b> {total_invested:.2f} SOL\n\n"

    # =================================================================
    # BAGS.FM GRADUATIONS
    # =================================================================
    bags = data.get("bags_graduations", [])

    if bags:
        message += "━━━━━━━━━━━━━━━━━━━━\n"
        message += "🎓 <b>RECENT GRADUATIONS</b>\n"
        message += "━━━━━━━━━━━━━━━━━━━━\n\n"

        for grad in bags[:5]:
            symbol = grad.get("symbol", "???")
            score = grad.get("score", 0)
            time = grad.get("time", "Unknown")

            message += f"• <b>{symbol}</b> (Score: {score}/100)\n"
            message += f"  <i>{time}</i>\n\n"
    else:
        message += "🎓 <i>No recent graduations</i>\n\n"

    # =================================================================
    # FOOTER
    # =================================================================
    message += "━━━━━━━━━━━━━━━━━━━━\n"
    message += "<i>Data updates every 15 minutes</i>\n"

    # =================================================================
    # INLINE KEYBOARD
    # =================================================================
    keyboard = [
        [
            InlineKeyboardButton("🔄 Refresh Now", callback_data="demo:sentiment_refresh"),
            InlineKeyboardButton("🏠 Main Menu", callback_data="demo:main"),
        ],
    ]

    # Add quick buy buttons for top 3 picks
    if len(grok_picks) >= 1:
        row1 = []
        for i, pick in enumerate(grok_picks[:3]):
            symbol = pick["symbol"]
            row1.append(
                InlineKeyboardButton(
                    f"⚡ Buy {symbol}",
                    callback_data=f"demo:quick_buy:{pick['contract_address']}"
                )
            )
        keyboard.append(row1)

    reply_markup = InlineKeyboardMarkup(keyboard)

    return message, reply_markup


# =============================================================================
# Command Handlers
# =============================================================================

async def show_sentiment_hub(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show sentiment hub dashboard."""
    try:
        # Load data
        data = load_sentiment_hub_data()

        # Format message
        message, reply_markup = format_sentiment_hub(data)

        # Send or edit message
        if update.callback_query:
            await update.callback_query.edit_message_text(
                text=message,
                parse_mode=ParseMode.HTML,
                reply_markup=reply_markup,
                disable_web_page_preview=True,
            )
        else:
            await update.message.reply_html(
                text=message,
                reply_markup=reply_markup,
                disable_web_page_preview=True,
            )

    except Exception as e:
        logger.error(f"Failed to show sentiment hub: {e}")
        error_msg = "⚠️ Failed to load sentiment hub. Service may be starting up."

        if update.callback_query:
            await update.callback_query.answer(error_msg, show_alert=True)
        else:
            await update.message.reply_text(error_msg)


async def refresh_sentiment_hub(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Manually trigger sentiment hub refresh."""
    try:
        # Trigger immediate update
        from tg_bot.services.sentiment_updater import get_sentiment_updater

        updater = get_sentiment_updater()
        await updater.update_all_data()

        # Show updated hub
        await show_sentiment_hub(update, context)

        await update.callback_query.answer("✅ Sentiment hub refreshed!", show_alert=False)

    except Exception as e:
        logger.error(f"Failed to refresh sentiment hub: {e}")
        await update.callback_query.answer("⚠️ Refresh failed", show_alert=True)


async def quick_buy_from_sentiment(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    token_address: str
):
    """Quick buy a token from sentiment hub."""
    try:
        # Redirect to buy flow
        # Import demo handler
        from tg_bot.handlers.demo import show_buy_ui

        # Store token address in user data
        context.user_data["pending_token_address"] = token_address

        # Show buy UI
        await show_buy_ui(update, context, token_address=token_address)

    except Exception as e:
        logger.error(f"Failed to start quick buy: {e}")
        await update.callback_query.answer("⚠️ Failed to start buy", show_alert=True)


# =============================================================================
# Callback Router
# =============================================================================

async def handle_sentiment_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    action: str
):
    """
    Route sentiment hub callbacks.

    Callbacks:
    - demo:sentiment → Show sentiment hub
    - demo:sentiment_refresh → Refresh and show
    - demo:quick_buy:<address> → Quick buy token
    """
    if action == "sentiment":
        await show_sentiment_hub(update, context)

    elif action == "sentiment_refresh":
        await refresh_sentiment_hub(update, context)

    elif action.startswith("quick_buy:"):
        parts = action.split(":")
        if len(parts) >= 2:
            token_address = parts[1]
            await quick_buy_from_sentiment(update, context, token_address)

    else:
        logger.warning(f"Unknown sentiment callback: {action}")
        await update.callback_query.answer("⚠️ Unknown action", show_alert=True)
