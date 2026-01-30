"""
Demo Core Handlers

Primary entrypoints for the /demo command, demo callbacks, and demo message handler.
"""

import logging
from typing import Any, Dict, List, Tuple

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.error import BadRequest
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from tg_bot.config import get_config
from tg_bot.handlers import error_handler, admin_only

from tg_bot.handlers.demo.demo_ui import DemoMenuBuilder, JarvisTheme, safe_symbol
from tg_bot.handlers.demo.demo_trading import (
    _get_demo_engine,
    _get_demo_wallet_password,
    _get_demo_wallet_dir,
    _register_token_id,
    _resolve_token_ref,
    validate_buy_amount,
)
from tg_bot.handlers.demo.demo_sentiment import (
    get_market_regime,
    get_ai_sentiment_for_token,
)
from tg_bot.handlers.demo.demo_orders import _process_demo_exit_checks
from tg_bot.handlers.demo.demo_callbacks import get_callback_router

logger = logging.getLogger(__name__)


# =============================================================================
# Demo Command Handler
# =============================================================================

@error_handler
@admin_only
async def demo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /demo - Launch the JARVIS V1 AI trading demo (admin only).
    """
    try:
        wallet_address = "Not configured"
        sol_balance = 0.0
        usd_value = 0.0
        open_positions = 0
        total_pnl = 0.0
        is_live = False
        market_regime = {}

        try:
            market_regime = await get_market_regime()
        except Exception as exc:
            logger.warning(f"Could not load market regime: {exc}")

        try:
            engine = await _get_demo_engine()
            treasury = engine.wallet.get_treasury()
            if treasury:
                wallet_address = treasury.address

            sol_balance, usd_value = await engine.get_portfolio_value()

            await engine.update_positions()
            positions = engine.get_open_positions()
            open_positions = len(positions)

            for pos in positions:
                total_pnl += pos.unrealized_pnl

            is_live = not engine.dry_run

        except Exception as exc:
            logger.warning(f"Could not load treasury data: {exc}")

        ai_auto_enabled = context.user_data.get("ai_auto_trade", False)
        text, keyboard = DemoMenuBuilder.main_menu(
            wallet_address=wallet_address,
            sol_balance=sol_balance,
            usd_value=usd_value,
            is_live=is_live,
            open_positions=open_positions,
            total_pnl=total_pnl,
            market_regime=market_regime,
            ai_auto_enabled=ai_auto_enabled,
        )

        await update.message.reply_text(
            text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=keyboard,
        )

    except Exception as exc:
        logger.error(f"Demo command failed: {exc}")
        text, keyboard = DemoMenuBuilder.error_message(f"Failed to load: {str(exc)[:100]}")
        await update.message.reply_text(
            text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=keyboard,
        )


# =============================================================================
# Callback Handler for Demo UI
# =============================================================================

@error_handler
async def demo_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle all demo:* callbacks via the modular callback router."""
    query = update.callback_query
    data = query.data if query else ""

    # Enforce admin-only demo access (callbacks can be clicked by anyone)
    try:
        config = get_config()
        user_id = query.from_user.id if query and query.from_user else 0
        username = query.from_user.username if query and query.from_user else None
        try:
            is_admin = config.is_admin(user_id, username)
        except TypeError:
            is_admin = config.is_admin(user_id)
        if not is_admin:
            try:
                await query.answer("Admin only.", show_alert=True)
            except BadRequest as exc:
                if (
                    "Query is too old" in str(exc)
                    or "response timeout expired" in str(exc)
                    or "query id is invalid" in str(exc)
                ):
                    logger.debug("Demo callback expired before admin check.")
                    return
                raise
            logger.warning(f"Unauthorized demo callback by user {user_id} (@{username})")
            return
    except Exception as exc:
        logger.warning(f"Demo admin check failed: {exc}")

    try:
        await query.answer()
    except BadRequest as exc:
        if (
            "Query is too old" in str(exc)
            or "response timeout expired" in str(exc)
            or "query id is invalid" in str(exc)
        ):
            logger.debug("Demo callback expired before answer.")
            return
        raise

    # Run TP/SL/trailing stop checks for demo positions (throttled)
    await _process_demo_exit_checks(update, context)

    if not data.startswith("demo:"):
        logger.warning(f"Non-demo callback received: {data}")
        return

    action = data.split(":")[1] if ":" in data else data

    # Build shared state for modular handlers
    wallet_address = "Not configured"
    sol_balance = 0.0
    usd_value = 0.0
    total_pnl = 0.0
    is_live = False
    positions: List[Dict[str, Any]] = []

    try:
        engine = await _get_demo_engine()
        treasury = engine.wallet.get_treasury()
        if treasury:
            wallet_address = treasury.address

        sol_balance, usd_value = await engine.get_portfolio_value()

        await engine.update_positions()
        open_pos = engine.get_open_positions()
        positions = [
            {
                "symbol": p.token_symbol,
                "pnl_pct": p.unrealized_pnl_pct,
                "pnl_usd": p.unrealized_pnl,
                "entry_price": p.entry_price,
                "current_price": p.current_price,
                "id": p.id,
                "address": p.token_mint,
                "amount": getattr(p, "token_amount", getattr(p, "amount", 0)),  # Token balance for selling
                "amount_sol": getattr(p, "amount_sol", getattr(p, "entry_amount_sol", 0)),  # SOL amount invested
            }
            for p in open_pos
        ]
        for p in open_pos:
            total_pnl += p.unrealized_pnl

        is_live = not engine.dry_run

    except Exception as exc:
        logger.warning(f"Could not load treasury data in callback: {exc}")

    try:
        market_regime = await get_market_regime()
    except Exception as exc:
        logger.warning(f"Could not load market regime in callback: {exc}")
        market_regime = {}

    ai_auto_enabled = context.user_data.get("ai_auto_trade", False)

    shared_state = {
        "wallet_address": wallet_address,
        "sol_balance": sol_balance,
        "usd_value": usd_value,
        "is_live": is_live,
        "positions": positions,
        "total_pnl": total_pnl,
        "market_regime": market_regime,
        "ai_auto_enabled": ai_auto_enabled,
    }

    router = get_callback_router()

    try:
        text, keyboard = await router.route(action, data, update, context, shared_state)
        try:
            await query.message.edit_text(
                text,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=keyboard,
            )
        except BadRequest as exc:
            if "Message is not modified" not in str(exc):
                raise

    except Exception as exc:
        # Track error for automatic fixing
        try:
            from core.logging.error_tracker import error_tracker
            error_id = error_tracker.track_error(
                exc,
                context=f"demo_callback action={action}",
                component="telegram_demo",
                metadata={"action": action, "callback_data": data},
            )
        except Exception:
            error_id = "unknown"

        logger.error(
            f"Demo callback error [{error_id}]: action={action}, error={exc}",
            exc_info=True,
        )

        text, keyboard = DemoMenuBuilder.error_message(
            error=str(exc)[:100],
            retry_action=f"demo:{action}",
            context_hint=f"Error ID: {error_id}",
        )
        try:
            await query.message.edit_text(
                text,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=keyboard,
            )
        except Exception as edit_err:
            logger.error(f"Failed to edit message after error: {edit_err}")


# =============================================================================
# Message Handler for Token Input
# =============================================================================

@error_handler
async def demo_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle text messages when awaiting input in demo mode.
    
    This is a router that delegates to specialized input handlers.
    """
    # PTB can invoke handlers for updates where `update.message` is None (e.g., edited messages,
    # service updates, etc.). Guard so we don't crash on `.text`.
    msg = update.effective_message or update.message
    if not msg or not getattr(msg, "text", None):
        return

    text = msg.text.strip()

    # Check if we're awaiting any input FIRST - don't process random messages
    if not any([
        context.user_data.get("awaiting_custom_buy_amount"),
        context.user_data.get("awaiting_watchlist_token"),
        context.user_data.get("awaiting_wallet_import"),
        context.user_data.get("awaiting_token"),
        context.user_data.get("awaiting_token_search"),
    ]):
        return

    # Only enforce admin check if we're actually awaiting demo input
    try:
        config = get_config()
        user_id = msg.from_user.id if msg and msg.from_user else 0
        username = msg.from_user.username if msg and msg.from_user else None
        try:
            is_admin = config.is_admin(user_id, username)
        except TypeError:
            is_admin = config.is_admin(user_id)
        if not is_admin:
            await msg.reply_text("Unauthorized: Demo is admin-only.")
            logger.warning(f"Unauthorized demo message by user {user_id} (@{username})")
            return
    except Exception as exc:
        logger.warning(f"Demo message admin check failed: {exc}")

    # Run TP/SL/trailing stop checks for demo positions (throttled)
    await _process_demo_exit_checks(update, context)

    # Import modular handlers
    from .input_handlers import (
        handle_custom_buy_amount,
        handle_watchlist_token,
        handle_wallet_import,
        handle_token_input,
    )

    # Delegate to appropriate handler (first match wins)
    handlers = [
        handle_custom_buy_amount,
        handle_watchlist_token,
        handle_wallet_import,
        handle_token_input,
    ]
    
    for handler in handlers:
        if await handler(update, context, text):
            return


# =============================================================================
# Registration Helper
# =============================================================================

def register_demo_handlers(app) -> None:
    """Register demo handlers with the application."""
    from telegram.ext import CommandHandler, CallbackQueryHandler, MessageHandler, filters

    app.add_handler(CommandHandler("demo", demo))
    app.add_handler(CallbackQueryHandler(demo_callback, pattern=r"^demo:"))
    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            demo_message_handler,
        ),
        group=0,
    )

    logger.info("Demo handlers registered")


__all__ = [
    "demo",
    "demo_callback",
    "demo_message_handler",
    "register_demo_handlers",
    "JarvisTheme",
    "DemoMenuBuilder",
    "safe_symbol",
]
