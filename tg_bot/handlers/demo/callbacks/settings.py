"""
Demo Bot - Settings Callback Handler

Handles: settings, ai_auto_*, toggle_mode, fee_stats
"""

import logging
from typing import Any, Dict, Tuple

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)


async def handle_settings(
    ctx,
    action: str,
    data: str,
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    state: Dict[str, Any],
) -> Tuple[str, InlineKeyboardMarkup]:
    """
    Handle settings callbacks.

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
    is_live = state.get("is_live", False)

    if action == "settings":
        ai_auto = context.user_data.get("ai_auto_trade", False)
        return DemoMenuBuilder.settings_menu(
            is_live=is_live,
            ai_auto_trade=ai_auto,
        )

    elif action == "fee_stats":
        fee_manager = ctx.get_success_fee_manager()
        if fee_manager:
            stats = fee_manager.get_fee_stats()
        else:
            stats = {}
        return DemoMenuBuilder.fee_stats_view(
            fee_percent=stats.get("fee_percent", 0.5),
            total_collected=stats.get("total_collected", 0.0),
            transaction_count=stats.get("transaction_count", 0),
            recent_fees=stats.get("recent_fees", []),
        )

    elif action == "ai_auto_settings":
        ai_settings = context.user_data.get("ai_settings", {})
        return DemoMenuBuilder.ai_auto_trade_settings(
            enabled=ai_settings.get("enabled", False),
            risk_level=ai_settings.get("risk_level", "MEDIUM"),
            max_position_size=ai_settings.get("max_position_size", 0.5),
            min_confidence=ai_settings.get("min_confidence", 0.7),
            daily_limit=ai_settings.get("daily_limit", 2.0),
            cooldown_minutes=ai_settings.get("cooldown_minutes", 30),
        )

    elif data.startswith("demo:ai_auto_toggle:"):
        parts = data.split(":")
        new_state = parts[2].lower() == "true" if len(parts) >= 3 else False

        ai_settings = context.user_data.get("ai_settings", {})
        ai_settings["enabled"] = new_state
        context.user_data["ai_settings"] = ai_settings
        context.user_data["ai_auto_trade"] = new_state

        action_text = "ENABLED" if new_state else "DISABLED"
        return DemoMenuBuilder.success_message(
            action=f"AI Auto-Trade {action_text}",
            details=f"Autonomous trading is now {'active' if new_state else 'paused'}.\n\n{'JARVIS will monitor markets and execute trades based on your settings.' if new_state else 'JARVIS will not execute trades automatically.'}",
        )

    elif data.startswith("demo:ai_risk:"):
        parts = data.split(":")
        risk_level = parts[2] if len(parts) >= 3 else "MEDIUM"

        ai_settings = context.user_data.get("ai_settings", {})
        ai_settings["risk_level"] = risk_level
        context.user_data["ai_settings"] = ai_settings

        return DemoMenuBuilder.ai_auto_trade_settings(
            enabled=ai_settings.get("enabled", False),
            risk_level=risk_level,
            max_position_size=ai_settings.get("max_position_size", 0.5),
            min_confidence=ai_settings.get("min_confidence", 0.7),
        )

    elif data.startswith("demo:ai_max:"):
        parts = data.split(":")
        max_size = float(parts[2]) if len(parts) >= 3 else 0.5

        ai_settings = context.user_data.get("ai_settings", {})
        ai_settings["max_position_size"] = max_size
        context.user_data["ai_settings"] = ai_settings

        return DemoMenuBuilder.ai_auto_trade_settings(
            enabled=ai_settings.get("enabled", False),
            risk_level=ai_settings.get("risk_level", "MEDIUM"),
            max_position_size=max_size,
            min_confidence=ai_settings.get("min_confidence", 0.7),
        )

    elif data.startswith("demo:ai_conf:"):
        parts = data.split(":")
        min_conf = float(parts[2]) if len(parts) >= 3 else 0.7

        ai_settings = context.user_data.get("ai_settings", {})
        ai_settings["min_confidence"] = min_conf
        context.user_data["ai_settings"] = ai_settings

        return DemoMenuBuilder.ai_auto_trade_settings(
            enabled=ai_settings.get("enabled", False),
            risk_level=ai_settings.get("risk_level", "MEDIUM"),
            max_position_size=ai_settings.get("max_position_size", 0.5),
            min_confidence=min_conf,
        )

    elif action == "ai_auto_status":
        ai_settings = context.user_data.get("ai_settings", {})
        return DemoMenuBuilder.ai_auto_trade_status(
            enabled=ai_settings.get("enabled", False),
            trades_today=context.user_data.get("ai_trades_today", 0),
            pnl_today=context.user_data.get("ai_pnl_today", 0.0),
        )

    elif action == "ai_trades_history":
        text = f"""
{theme.AUTO} *AI TRADE HISTORY*
{'=' * 20}

_No AI trades executed yet_

When AI auto-trading is enabled,
JARVIS will:
- Analyze market conditions
- Find high-confidence opportunities
- Execute trades within your limits
- Record all trades here

{'=' * 20}
_Feature tracking all AI trades coming in V2_
"""
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(f"{theme.BACK} Back", callback_data="demo:ai_auto_settings")],
        ])
        return text, keyboard

    elif action == "toggle_mode":
        try:
            engine = await ctx.get_demo_engine()
            engine.dry_run = not engine.dry_run
            new_mode = "PAPER" if engine.dry_run else "LIVE"
            return DemoMenuBuilder.success_message(
                action=f"Mode Changed to {new_mode}",
                details=f"Trading is now in {'paper' if engine.dry_run else 'live'} mode.",
            )
        except Exception as e:
            return DemoMenuBuilder.error_message(f"Mode toggle failed: {e}")

    # Default
    ai_auto = context.user_data.get("ai_auto_trade", False)
    return DemoMenuBuilder.settings_menu(
        is_live=is_live,
        ai_auto_trade=ai_auto,
    )
