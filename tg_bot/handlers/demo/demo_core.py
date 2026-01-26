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
    """Handle text messages when awaiting token input or watchlist add."""
    text = update.message.text.strip()

    # Enforce admin-only demo access
    try:
        config = get_config()
        user_id = update.message.from_user.id if update.message and update.message.from_user else 0
        username = update.message.from_user.username if update.message and update.message.from_user else None
        try:
            is_admin = config.is_admin(user_id, username)
        except TypeError:
            is_admin = config.is_admin(user_id)
        if not is_admin:
            await update.message.reply_text("Unauthorized: Demo is admin-only.")
            logger.warning(f"Unauthorized demo message by user {user_id} (@{username})")
            return
    except Exception as exc:
        logger.warning(f"Demo message admin check failed: {exc}")

    # Run TP/SL/trailing stop checks for demo positions (throttled)
    await _process_demo_exit_checks(update, context)

    if not any([
        context.user_data.get("awaiting_custom_buy_amount"),
        context.user_data.get("awaiting_watchlist_token"),
        context.user_data.get("awaiting_wallet_import"),
        context.user_data.get("awaiting_token"),
        context.user_data.get("awaiting_token_search"),
    ]):
        return

    # ---------------------------------------------------------------------
    # Custom Buy Amount Input
    # ---------------------------------------------------------------------
    if context.user_data.get("awaiting_custom_buy_amount"):
        context.user_data["awaiting_custom_buy_amount"] = False
        token_ref = context.user_data.pop("custom_buy_token_ref", "")

        try:
            amount = float(text)
            is_valid, error_msg = validate_buy_amount(amount)

            if not is_valid:
                error_text, keyboard = DemoMenuBuilder.error_message(error_msg)
                await update.message.reply_text(
                    error_text,
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=keyboard,
                )
                return

            token_addr = _resolve_token_ref(context, token_ref)
            sentiment_data = await get_ai_sentiment_for_token(token_addr)
            token_symbol = sentiment_data.get("symbol", "TOKEN")
            token_price = sentiment_data.get("price", 0) or 0
            sentiment = sentiment_data.get("sentiment", "neutral")
            score = sentiment_data.get("score", 0)
            signal = sentiment_data.get("signal", "NEUTRAL")

            theme = JarvisTheme
            confirm_text = f"""
{theme.BUY} *CONFIRM CUSTOM BUY*

*Token:* {safe_symbol(token_symbol)}
*Amount:* {amount} SOL
*Est. Price:* ${token_price:.8f}

{theme.AUTO} *AI Analysis*
- Sentiment: *{sentiment.upper()}*
- Score: *{score:.2f}*
- Signal: *{signal}*

_Tap Confirm to execute_
"""
            keyboard = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton(
                        f"{theme.SUCCESS} Confirm Buy",
                        callback_data=f"demo:execute_buy:{token_ref}:{amount}",
                    ),
                ],
                [
                    InlineKeyboardButton(
                        f"{theme.CLOSE} Cancel",
                        callback_data="demo:main",
                    ),
                ],
            ])

            await update.message.reply_text(
                confirm_text,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=keyboard,
            )

        except ValueError:
            error_text, keyboard = DemoMenuBuilder.error_message(
                "Invalid amount. Please enter a number like 0.5 or 2.5"
            )
            await update.message.reply_text(
                error_text,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=keyboard,
            )
        except Exception as exc:
            logger.error(f"Custom buy amount error: {exc}")
            error_text, keyboard = DemoMenuBuilder.error_message(
                f"Error: {str(exc)[:50]}"
            )
            await update.message.reply_text(
                error_text,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=keyboard,
            )
        return

    # ---------------------------------------------------------------------
    # Watchlist Token Addition
    # ---------------------------------------------------------------------
    if context.user_data.get("awaiting_watchlist_token"):
        context.user_data["awaiting_watchlist_token"] = False

        if len(text) < 32 or len(text) > 44:
            error_text, keyboard = DemoMenuBuilder.error_message(
                "Invalid Solana address. Must be 32-44 characters."
            )
            await update.message.reply_text(
                error_text,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=keyboard,
            )
            return

        try:
            sentiment = await get_ai_sentiment_for_token(text)
            token_data = {
                "symbol": sentiment.get("symbol", "TOKEN"),
                "address": text,
                "price": sentiment.get("price", 0),
                "change_24h": sentiment.get("change_24h", 0),
            }
            token_data["token_id"] = _register_token_id(context, text)

            watchlist = context.user_data.get("watchlist", [])
            if any(t.get("address") == text for t in watchlist):
                error_text, keyboard = DemoMenuBuilder.error_message(
                    "Token already in watchlist"
                )
                await update.message.reply_text(
                    error_text,
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=keyboard,
                )
                return

            watchlist.append(token_data)
            context.user_data["watchlist"] = watchlist

            success_text, keyboard = DemoMenuBuilder.success_message(
                action="Token Added",
                details=f"Added {token_data['symbol']} to your watchlist!\n\n"
                        f"Current price: ${token_data['price']:.6f}",
            )
            await update.message.reply_text(
                success_text,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=keyboard,
            )
        except Exception as exc:
            error_text, keyboard = DemoMenuBuilder.error_message(
                f"Failed to add token: {str(exc)[:50]}"
            )
            await update.message.reply_text(
                error_text,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=keyboard,
            )
        return

    # ---------------------------------------------------------------------
    # Wallet Import Input
    # ---------------------------------------------------------------------
    if context.user_data.get("awaiting_wallet_import"):
        context.user_data["awaiting_wallet_import"] = False
        import_mode = context.user_data.get("import_mode", "key")

        try:
            from bots.treasury.wallet import SecureWallet
            from core.wallet_service import WalletService

            wallet_password = _get_demo_wallet_password()
            if not wallet_password:
                raise ValueError("Demo wallet password not configured")

            wallet_service = WalletService()
            private_key = None

            if import_mode == "seed":
                words = text.strip().split()
                if len(words) not in [12, 24]:
                    raise ValueError(f"Seed phrase must be 12 or 24 words, got {len(words)}")
                wallet_data, _ = await wallet_service.import_wallet(
                    seed_phrase=text.strip(),
                    user_password=wallet_password,
                )
                private_key = wallet_data.private_key
            else:
                if len(text.strip()) < 64:
                    raise ValueError("Private key too short (min 64 chars)")
                wallet_data, _ = await wallet_service.import_from_private_key(
                    private_key=text.strip(),
                    user_password=wallet_password,
                )
                private_key = wallet_data.private_key

            secure_wallet = SecureWallet(
                master_password=wallet_password,
                wallet_dir=_get_demo_wallet_dir(),
            )
            wallet_info = secure_wallet.import_wallet(private_key, label="Demo Imported")
            wallet_address = wallet_info.address

            result_text, keyboard = DemoMenuBuilder.wallet_import_result(
                success=True,
                wallet_address=wallet_address,
            )
            logger.info(f"Wallet imported: {wallet_address[:8]}...")

        except Exception as exc:
            logger.error(f"Wallet import failed: {exc}")
            result_text, keyboard = DemoMenuBuilder.wallet_import_result(
                success=False,
                error=str(exc)[:100],
            )

        await update.message.reply_text(
            result_text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=keyboard,
        )
        return

    # ---------------------------------------------------------------------
    # Buy Token Input
    # ---------------------------------------------------------------------
    if not context.user_data.get("awaiting_token"):
        return

    context.user_data["awaiting_token"] = False

    if len(text) < 32 or len(text) > 44:
        error_text, keyboard = DemoMenuBuilder.error_message(
            "Invalid Solana address. Must be 32-44 characters."
        )
        await update.message.reply_text(
            error_text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=keyboard,
        )
        return

    amount = context.user_data.get("buy_amount", 0.1)
    token_ref = _register_token_id(context, text)

    confirm_text, keyboard = DemoMenuBuilder.buy_confirmation(
        token_symbol="TOKEN",
        token_address=text,
        amount_sol=amount,
        estimated_tokens=1000000,
        price_usd=0.00001,
        token_ref=token_ref,
    )

    await update.message.reply_text(
        confirm_text,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=keyboard,
    )


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
        group=1,
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
