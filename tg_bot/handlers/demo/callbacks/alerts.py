"""
Demo Bot - Alerts Callback Handler

Handles: pnl_alerts, alert_setup, create_alert, delete_pos_alerts, custom_alert, clear_triggered_alerts
"""

import logging
from datetime import datetime
from typing import Any, Dict, Tuple

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)


async def handle_alerts(
    ctx,
    action: str,
    data: str,
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    state: Dict[str, Any],
) -> Tuple[str, InlineKeyboardMarkup]:
    """
    Handle P&L alerts callbacks.

    Args:
        ctx: DemoContextLoader instance
        action: The action
        data: Full callback data
        update: Telegram update
        context: Bot context
        state: Shared state dict

    Returns:
        Tuple of (text, keyboard)
    """
    theme = ctx.JarvisTheme
    DemoMenuBuilder = ctx.DemoMenuBuilder
    positions = state.get("positions", [])

    if action == "pnl_alerts":
        alerts = context.user_data.get("pnl_alerts", [])
        return DemoMenuBuilder.pnl_alerts_overview(
            alerts=alerts,
            positions=positions,
        )

    elif data.startswith("demo:alert_setup:"):
        parts = data.split(":")
        pos_id = parts[2] if len(parts) >= 3 else "0"

        target_pos = None
        for pos in positions:
            if str(pos.get("id", "")) == pos_id:
                target_pos = pos
                break

        if target_pos:
            alerts = context.user_data.get("pnl_alerts", [])
            return DemoMenuBuilder.position_alert_setup(
                position=target_pos,
                existing_alerts=alerts,
            )
        else:
            return DemoMenuBuilder.error_message("Position not found")

    elif data.startswith("demo:create_alert:"):
        parts = data.split(":")
        if len(parts) >= 5:
            pos_id = parts[2]
            alert_type = parts[3]
            try:
                target = float(parts[4])
            except (ValueError, TypeError):
                logger.warning("Invalid alert target in callback data: %s", data)
                return None

            target_pos = None
            for pos in positions:
                if str(pos.get("id", "")) == pos_id:
                    target_pos = pos
                    break

            if target_pos:
                symbol = target_pos.get("symbol", "???")
                direction = "above" if target > 0 else "below"

                new_alert = {
                    "id": f"alert_{pos_id}_{target}",
                    "position_id": pos_id,
                    "symbol": symbol,
                    "type": alert_type,
                    "target": target,
                    "direction": direction,
                    "triggered": False,
                    "created_at": datetime.now().isoformat(),
                }

                alerts = context.user_data.get("pnl_alerts", [])
                alerts.append(new_alert)
                context.user_data["pnl_alerts"] = alerts

                return DemoMenuBuilder.alert_created_success(
                    symbol=symbol,
                    alert_type=alert_type,
                    target=target,
                    direction=direction,
                )
            else:
                return DemoMenuBuilder.error_message("Position not found")
        else:
            return DemoMenuBuilder.error_message("Invalid alert data")

    elif data.startswith("demo:delete_pos_alerts:"):
        parts = data.split(":")
        pos_id = parts[2] if len(parts) >= 3 else "0"

        alerts = context.user_data.get("pnl_alerts", [])
        alerts = [a for a in alerts if a.get("position_id") != pos_id]
        context.user_data["pnl_alerts"] = alerts

        text = f"""
{theme.SUCCESS} *ALERTS DELETED*
{'=' * 20}

All alerts for this position have been removed.

{'=' * 20}
"""
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(f"{theme.BELL} All Alerts", callback_data="demo:pnl_alerts")],
            [InlineKeyboardButton(f"{theme.CHART} Positions", callback_data="demo:positions")],
        ])
        return text, keyboard

    elif action == "clear_triggered_alerts":
        alerts = context.user_data.get("pnl_alerts", [])
        alerts = [a for a in alerts if not a.get("triggered", False)]
        context.user_data["pnl_alerts"] = alerts

        text = f"""
{theme.SUCCESS} *TRIGGERED ALERTS CLEARED*
{'=' * 20}

All triggered alerts have been removed.

{'=' * 20}
"""
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(f"{theme.BELL} All Alerts", callback_data="demo:pnl_alerts")],
            [InlineKeyboardButton(f"{theme.BACK} Main Menu", callback_data="demo:main")],
        ])
        return text, keyboard

    elif data.startswith("demo:custom_alert:"):
        parts = data.split(":")
        pos_id = parts[2] if len(parts) >= 3 else "0"

        text = f"""
{theme.AUTO} *CUSTOM ALERT*
{'=' * 20}

Custom alert entry coming in V2!

For now, use the quick presets:
- +25%, +50%, +100% profit
- -10%, -25%, -50% loss

{'=' * 20}
_Custom values & price alerts soon_
"""
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(f"{theme.BACK} Back", callback_data=f"demo:alert_setup:{pos_id}")],
        ])
        return text, keyboard

    # Default
    alerts = context.user_data.get("pnl_alerts", [])
    return DemoMenuBuilder.pnl_alerts_overview(
        alerts=alerts,
        positions=positions,
    )
