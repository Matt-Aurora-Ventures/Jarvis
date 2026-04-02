"""
Demo Bot - DCA Callback Handler

Handles: dca, dca_new, dca_select, dca_amount, dca_create, dca_pause, dca_delete, dca_history
"""

import logging
from datetime import datetime
from typing import Any, Dict, Tuple

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)


async def handle_dca(
    ctx,
    action: str,
    data: str,
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    state: Dict[str, Any],
) -> Tuple[str, InlineKeyboardMarkup]:
    """
    Handle DCA callbacks.

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

    if action == "dca":
        dca_plans = context.user_data.get("dca_plans", [])
        total_invested = sum(p.get("total_invested", 0) for p in dca_plans)
        return DemoMenuBuilder.dca_overview(
            dca_plans=dca_plans,
            total_invested=total_invested,
        )

    elif action == "dca_new":
        watchlist = context.user_data.get("watchlist", [])
        for token in watchlist:
            token["token_id"] = ctx.register_token_id(context, token.get("address"))
        return DemoMenuBuilder.dca_setup(watchlist=watchlist)

    elif data.startswith("demo:dca_select:"):
        parts = data.split(":")
        token_ref = parts[2] if len(parts) >= 3 else ""
        token_address = ctx.resolve_token_ref(context, token_ref)

        watchlist = context.user_data.get("watchlist", [])
        token_symbol = "TOKEN"
        for token in watchlist:
            if token.get("address") == token_address:
                token_symbol = token.get("symbol", "TOKEN")
                break

        return DemoMenuBuilder.dca_setup(
            token_symbol=token_symbol,
            token_address=token_address,
            token_ref=token_ref,
            watchlist=watchlist,
        )

    elif data.startswith("demo:dca_amount:"):
        try:
            parts = data.split(":")
            if len(parts) >= 4:
                token_ref = parts[2]
                token_address = ctx.resolve_token_ref(context, token_ref)
                amount = float(parts[3])

                watchlist = context.user_data.get("watchlist", [])
                token_symbol = "TOKEN"
                for token in watchlist:
                    if token.get("address") == token_address:
                        token_symbol = token.get("symbol", "TOKEN")
                        break

                return DemoMenuBuilder.dca_frequency_select(
                    token_symbol=token_symbol,
                    token_address=token_address,
                    token_ref=token_ref,
                    amount=amount,
                )
            else:
                return DemoMenuBuilder.error_message(
                    "Invalid DCA configuration",
                    retry_action="demo:dca_new",
                    context_hint="Amount selection failed"
                )
        except (ValueError, IndexError) as e:
            logger.warning(f"DCA amount parse error: {e}")
            return DemoMenuBuilder.error_message(
                f"Invalid amount: {str(e)[:50]}",
                retry_action="demo:dca_new"
            )

    elif data.startswith("demo:dca_create:"):
        try:
            parts = data.split(":")
            if len(parts) >= 5:
                token_ref = parts[2]
                token_address = ctx.resolve_token_ref(context, token_ref)
                amount = float(parts[3])
                frequency = parts[4]

                watchlist = context.user_data.get("watchlist", [])
                token_symbol = "TOKEN"
                for token in watchlist:
                    if token.get("address") == token_address:
                        token_symbol = token.get("symbol", "TOKEN")
                        break

                new_plan = {
                    "id": f"dca_{token_address[:8]}_{datetime.now().strftime('%H%M%S')}",
                    "symbol": token_symbol,
                    "address": token_address,
                    "amount": amount,
                    "frequency": frequency,
                    "active": True,
                    "executions": 0,
                    "total_invested": 0.0,
                    "next_execution": "In 1 " + ("hour" if frequency == "hourly" else "day" if frequency == "daily" else "week"),
                    "created_at": datetime.now().isoformat(),
                }

                dca_plans = context.user_data.get("dca_plans", [])
                dca_plans.append(new_plan)
                context.user_data["dca_plans"] = dca_plans

                return DemoMenuBuilder.dca_plan_created(
                    token_symbol=token_symbol,
                    amount=amount,
                    frequency=frequency,
                    first_execution="Starting soon",
                )
            else:
                return DemoMenuBuilder.error_message(
                    "Invalid DCA configuration",
                    retry_action="demo:dca_new"
                )
        except (ValueError, IndexError) as e:
            logger.warning(f"DCA create error: {e}")
            return DemoMenuBuilder.operation_failed(
                "DCA Plan Creation",
                f"Could not create plan: {str(e)[:50]}",
                retry_action="demo:dca_new"
            )

    elif data.startswith("demo:dca_pause:"):
        parts = data.split(":")
        plan_id = parts[2] if len(parts) >= 3 else ""

        dca_plans = context.user_data.get("dca_plans", [])
        for plan in dca_plans:
            if plan.get("id") == plan_id:
                plan["active"] = not plan.get("active", True)
                break
        context.user_data["dca_plans"] = dca_plans

        total_invested = sum(p.get("total_invested", 0) for p in dca_plans)
        return DemoMenuBuilder.dca_overview(
            dca_plans=dca_plans,
            total_invested=total_invested,
        )

    elif data.startswith("demo:dca_delete:"):
        parts = data.split(":")
        plan_id = parts[2] if len(parts) >= 3 else ""

        dca_plans = context.user_data.get("dca_plans", [])
        dca_plans = [p for p in dca_plans if p.get("id") != plan_id]
        context.user_data["dca_plans"] = dca_plans

        text = f"""
{theme.SUCCESS} *DCA PLAN DELETED*
{'=' * 20}

The DCA plan has been removed.
No further automatic purchases
will be made.

{'=' * 20}
"""
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(f"{theme.AUTO} View DCA Plans", callback_data="demo:dca")],
            [InlineKeyboardButton(f"{theme.BACK} Main Menu", callback_data="demo:main")],
        ])
        return text, keyboard

    elif action == "dca_history":
        dca_plans = context.user_data.get("dca_plans", [])
        total_executions = sum(p.get("executions", 0) for p in dca_plans)

        text = f"""
{theme.AUTO} *DCA EXECUTION HISTORY*
{'=' * 20}

{theme.CHART} *Total Executions:* {total_executions}

_Detailed execution history coming in V2_

Each DCA execution will be logged with:
- Timestamp
- Token purchased
- Amount spent
- Price at execution
- Tokens received

{'=' * 20}
"""
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(f"{theme.AUTO} DCA Plans", callback_data="demo:dca")],
            [InlineKeyboardButton(f"{theme.BACK} Main Menu", callback_data="demo:main")],
        ])
        return text, keyboard

    elif action == "dca_input":
        text = f"""
{theme.AUTO} *ENTER TOKEN ADDRESS*
{'=' * 20}

Paste a Solana token address to
set up a DCA plan.

_Manual address input coming in V2_

For now, add tokens to your watchlist
first, then create DCA plans from there.

{'=' * 20}
"""
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(f"{theme.GEM} Go to Watchlist", callback_data="demo:watchlist")],
            [InlineKeyboardButton(f"{theme.BACK} Back", callback_data="demo:dca_new")],
        ])
        return text, keyboard

    # Default
    dca_plans = context.user_data.get("dca_plans", [])
    total_invested = sum(p.get("total_invested", 0) for p in dca_plans)
    return DemoMenuBuilder.dca_overview(
        dca_plans=dca_plans,
        total_invested=total_invested,
    )
