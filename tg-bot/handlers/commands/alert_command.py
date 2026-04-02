"""
/alert Command Handler

Provides price alert management with:
- Add price threshold alerts (above/below)
- Add percentage change alerts
- View all active alerts
- Remove specific alerts
- Persistent storage (survives restarts)

Usage:
    /alert add SOL above 150     - Alert when SOL goes above $150
    /alert add SOL below 100     - Alert when SOL goes below $100
    /alert add SOL +5%           - Alert when SOL goes up 5%
    /alert add SOL -10%          - Alert when SOL goes down 10%
    /alert list                  - List all active alerts
    /alert remove <alert_id>     - Remove specific alert
    /alert clear                 - Clear all alerts
"""

import logging
from typing import Optional

from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from core.alerts import get_alert_engine, AlertType, DeliveryChannel
from tg_bot.handlers import error_handler

logger = logging.getLogger(__name__)

# Known token mappings
KNOWN_TOKENS = {
    "SOL": "So11111111111111111111111111111111111111112",
    "BONK": "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263",
    "WIF": "EKpQGSJtjMFqKZ9KQanSqYXRcF8fBopzLHYxdM65zcjm",
    "JUP": "JUPyiwrYJFskUPiHa7hkeR8VUtAeFoSYbKedZNsDvCN",
    "PYTH": "HZ1JovNiVvGrGNiiYvEozEVgZ58xaU3RKwX8eACQBCt3",
    "RAY": "4k3Dyjzvzp8eMZWUXbBCjEvwSkkk59S5iCNLY3QrkX6R",
}


@error_handler
async def alert_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle /alert command for managing price alerts.
    """
    user_id = str(update.effective_user.id) if update.effective_user else "0"

    if not user_id or user_id == "0":
        await update.message.reply_text("Could not identify user.")
        return

    engine = get_alert_engine()

    # Parse subcommand
    if not context.args:
        await _show_usage(update)
        return

    subcommand = context.args[0].lower()

    # Handle different subcommands
    if subcommand == "add":
        await _handle_add_alert(update, context, user_id, engine)
    elif subcommand == "list":
        await _handle_list_alerts(update, user_id, engine)
    elif subcommand == "remove":
        await _handle_remove_alert(update, context, user_id, engine)
    elif subcommand == "clear":
        await _handle_clear_alerts(update, user_id, engine)
    else:
        await _show_usage(update)


async def _show_usage(update: Update):
    """Show command usage help."""
    usage = """
*Price Alert Commands*

*Add Alerts:*
`/alert add SOL above 150` - Price threshold
`/alert add SOL below 100` - Price threshold
`/alert add SOL +5%` - Percentage up
`/alert add SOL -10%` - Percentage down

*Manage Alerts:*
`/alert list` - View all alerts
`/alert remove <id>` - Remove alert
`/alert clear` - Remove all alerts

*Examples:*
• Alert when SOL hits $150:
  `/alert add SOL above 150`

• Alert when BONK drops 5%:
  `/alert add BONK -5%`
    """
    await update.message.reply_text(usage, parse_mode=ParseMode.MARKDOWN)


async def _handle_add_alert(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    user_id: str,
    engine
):
    """Handle adding a new alert."""
    # Need at least: add TOKEN DIRECTION VALUE
    # Example: add SOL above 150
    # Example: add SOL +5%
    if len(context.args) < 3:
        await update.message.reply_text(
            "Usage: `/alert add <token> <direction> <value>`\n"
            "Example: `/alert add SOL above 150`\n"
            "Example: `/alert add SOL +5%`",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    token = context.args[1].upper()
    direction_or_percent = context.args[2]

    # Resolve token
    token_symbol = token if token in KNOWN_TOKENS else token[:8]

    try:
        # Check if percentage alert
        if direction_or_percent.endswith("%"):
            # Percentage alert: +5% or -5%
            percent_str = direction_or_percent.rstrip("%")
            percentage = float(percent_str)

            direction = "up" if percentage > 0 else "down"

            alert_id = await engine.add_percentage_alert(
                user_id=user_id,
                token=token_symbol,
                percentage_change=abs(percentage),
                direction=direction,
            )

            await update.message.reply_text(
                f"✅ *Alert Created*\n\n"
                f"Token: *{token_symbol}*\n"
                f"Trigger: {percentage:+.1f}% {direction}\n"
                f"ID: `{alert_id}`\n\n"
                f"You'll be notified when {token_symbol} moves {abs(percentage):.1f}% {direction}.",
                parse_mode=ParseMode.MARKDOWN,
            )

        else:
            # Price threshold alert: above 150 or below 100
            direction = direction_or_percent.lower()
            if direction not in ["above", "below"]:
                await update.message.reply_text(
                    "Direction must be 'above' or 'below' (or use +/-X% for percentage alerts)"
                )
                return

            if len(context.args) < 4:
                await update.message.reply_text(
                    "Missing price value. Usage: `/alert add SOL above 150`",
                    parse_mode=ParseMode.MARKDOWN,
                )
                return

            price = float(context.args[3])

            alert_id = await engine.add_price_alert(
                user_id=user_id,
                token=token_symbol,
                threshold_price=price,
                direction=direction,
            )

            await update.message.reply_text(
                f"✅ *Alert Created*\n\n"
                f"Token: *{token_symbol}*\n"
                f"Trigger: {direction} ${price:.6f}\n"
                f"ID: `{alert_id}`\n\n"
                f"You'll be notified when {token_symbol} goes {direction} ${price:.6f}.",
                parse_mode=ParseMode.MARKDOWN,
            )

    except ValueError as e:
        await update.message.reply_text(f"Invalid number format: {e}")
    except Exception as e:
        logger.error(f"Failed to add alert: {e}")
        await update.message.reply_text(f"Failed to create alert: {e}")


async def _handle_list_alerts(update: Update, user_id: str, engine):
    """Handle listing user's alerts."""
    try:
        alerts = await engine.get_user_alerts(user_id)

        if not alerts:
            await update.message.reply_text(
                "*Your Alerts*\n\n"
                "_No active alerts_\n\n"
                "Add alerts with `/alert add <token> <direction> <value>`",
                parse_mode=ParseMode.MARKDOWN,
            )
            return

        lines = [f"*Your Alerts* ({len(alerts)} active)", ""]

        for i, alert in enumerate(alerts, 1):
            alert_id = alert.get("alert_id", "???")
            token = alert.get("token", "???")
            alert_type = alert.get("type", "unknown")

            if alert_type == "price":
                threshold = alert.get("threshold", 0)
                direction = alert.get("direction", "?")
                lines.append(
                    f"{i}. *{token}* {direction} ${threshold:.6f}\n"
                    f"   ID: `{alert_id}`"
                )

            elif alert_type == "percentage":
                percentage = alert.get("percentage", 0)
                direction = alert.get("direction", "?")
                sign = "+" if direction == "up" else "-"
                lines.append(
                    f"{i}. *{token}* {sign}{percentage:.1f}% {direction}\n"
                    f"   ID: `{alert_id}`"
                )

            lines.append("")

        lines.append("_Use `/alert remove <id>` to remove_")

        await update.message.reply_text(
            "\n".join(lines),
            parse_mode=ParseMode.MARKDOWN,
        )

    except Exception as e:
        logger.error(f"Failed to list alerts: {e}")
        await update.message.reply_text(f"Failed to list alerts: {e}")


async def _handle_remove_alert(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    user_id: str,
    engine
):
    """Handle removing a specific alert."""
    if len(context.args) < 2:
        await update.message.reply_text(
            "Usage: `/alert remove <alert_id>`\n"
            "Example: `/alert remove PRICE-A1B2C3D4E5F6`",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    alert_id = context.args[1]

    try:
        removed = await engine.remove_alert(user_id, alert_id)

        if removed:
            await update.message.reply_text(
                f"✅ Removed alert `{alert_id}`",
                parse_mode=ParseMode.MARKDOWN,
            )
        else:
            await update.message.reply_text(
                f"❌ Alert `{alert_id}` not found",
                parse_mode=ParseMode.MARKDOWN,
            )

    except Exception as e:
        logger.error(f"Failed to remove alert: {e}")
        await update.message.reply_text(f"Failed to remove alert: {e}")


async def _handle_clear_alerts(update: Update, user_id: str, engine):
    """Handle clearing all user alerts."""
    try:
        # Get current alerts count
        alerts = await engine.get_user_alerts(user_id)
        count = len(alerts)

        if count == 0:
            await update.message.reply_text("You have no active alerts.")
            return

        # Unsubscribe from all price threshold alerts
        await engine.unsubscribe(user_id, AlertType.PRICE_THRESHOLD)

        await update.message.reply_text(
            f"✅ Cleared {count} alert{'s' if count != 1 else ''}",
        )

    except Exception as e:
        logger.error(f"Failed to clear alerts: {e}")
        await update.message.reply_text(f"Failed to clear alerts: {e}")


__all__ = [
    "alert_command",
]
