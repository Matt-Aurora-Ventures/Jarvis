"""
Demo Core Handlers

Primary entrypoints for the /demo command, demo callbacks, and demo message handler.
"""

import asyncio
import logging
from typing import Any, Dict, List, Tuple, Optional

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.error import BadRequest, NetworkError, TimedOut
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

_DEMO_NAV_STACK_KEY = "demo_nav_stack"
_DEMO_NAV_CURRENT_KEY = "demo_current_page"
_DEMO_NAV_MAX_DEPTH = 50


def _demo_nav_get_stack(context: ContextTypes.DEFAULT_TYPE) -> List[str]:
    try:
        stack = context.user_data.get(_DEMO_NAV_STACK_KEY, [])
        return stack if isinstance(stack, list) else []
    except Exception:
        return []


def _demo_nav_set_stack(context: ContextTypes.DEFAULT_TYPE, stack: List[str]) -> None:
    try:
        context.user_data[_DEMO_NAV_STACK_KEY] = (stack or [])[-_DEMO_NAV_MAX_DEPTH:]
    except Exception:
        pass


def _demo_nav_get_current(context: ContextTypes.DEFAULT_TYPE) -> str:
    try:
        cur = context.user_data.get(_DEMO_NAV_CURRENT_KEY, "")
        return cur if isinstance(cur, str) else ""
    except Exception:
        return ""


def _demo_nav_set_current(context: ContextTypes.DEFAULT_TYPE, page: str) -> None:
    try:
        context.user_data[_DEMO_NAV_CURRENT_KEY] = page
    except Exception:
        pass


def _demo_nav_push(context: ContextTypes.DEFAULT_TYPE, next_page: str) -> None:
    """Push current page onto stack (if it exists) and set new current page."""
    try:
        current = _demo_nav_get_current(context)
        if current and current != next_page:
            stack = _demo_nav_get_stack(context)
            # Avoid pushing duplicates to keep back navigation sane.
            if not stack or stack[-1] != current:
                stack.append(current)
            _demo_nav_set_stack(context, stack)
        _demo_nav_set_current(context, next_page)
    except Exception:
        pass


def _demo_nav_pop(context: ContextTypes.DEFAULT_TYPE) -> str:
    """Pop previous page from stack (or return main). Also updates current."""
    stack = _demo_nav_get_stack(context)
    target = stack.pop() if stack else "demo:main"
    _demo_nav_set_stack(context, stack)
    _demo_nav_set_current(context, target)
    return target


def _ensure_prev_menu_button(keyboard: Optional[InlineKeyboardMarkup]) -> InlineKeyboardMarkup:
    """Append a 'Previous Menu' button to every demo page (unless already present)."""
    prev_btn = InlineKeyboardButton("↩️ Previous Menu", callback_data="demo:nav_back")

    if keyboard is None:
        return InlineKeyboardMarkup([[prev_btn]])

    try:
        rows = list(keyboard.inline_keyboard or [])
        for row in rows:
            for btn in row:
                if getattr(btn, "callback_data", None) == "demo:nav_back":
                    return keyboard
        rows.append([prev_btn])
        return InlineKeyboardMarkup(rows)
    except Exception:
        return keyboard


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
            market_regime = await asyncio.wait_for(get_market_regime(), timeout=4.0)
        except Exception as exc:
            logger.warning(f"Could not load market regime: {exc}")

        try:
            engine = await asyncio.wait_for(_get_demo_engine(), timeout=8.0)
            treasury = engine.wallet.get_treasury()
            if treasury:
                wallet_address = treasury.address

            sol_balance, usd_value = await asyncio.wait_for(engine.get_portfolio_value(), timeout=6.0)

            await asyncio.wait_for(engine.update_positions(), timeout=8.0)
            positions = engine.get_open_positions()
            open_positions = len(positions)

            for pos in positions:
                total_pnl += pos.unrealized_pnl

            is_live = not engine.dry_run

        except Exception as exc:
            logger.warning(f"Could not load treasury data: {exc}")

        # Reset demo navigation context on /demo entry.
        _demo_nav_set_stack(context, [])
        _demo_nav_set_current(context, "demo:main")

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
        keyboard = _ensure_prev_menu_button(keyboard)

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
    
    # CRITICAL: Entry logging to verify callbacks are reaching this handler
    logger.info(f"[DEMO_CALLBACK_ENTRY] data='{data}' user={query.from_user.id if query and query.from_user else 'N/A'}")

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
            except (TimedOut, NetworkError) as exc:
                logger.debug("Demo callback answer failed during admin check: %s", exc)
                return
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
    except (TimedOut, NetworkError) as exc:
        # Non-fatal: callback answers can time out during transient network issues.
        logger.debug("Demo callback answer timed out: %s", exc)
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

    # Global "Previous Menu" navigation for demo UI.
    # We keep a small per-user stack of rendered demo pages so every screen can reliably go back.
    if data == "demo:nav_back":
        data = _demo_nav_pop(context)
    else:
        # Don't treat noop/close as navigation targets.
        try:
            next_action = data.split(":")[1] if ":" in data else data
            # Some callbacks trigger side-effects (e.g., sending photos) while leaving the
            # current menu unchanged. Avoid polluting the nav stack with those actions.
            if next_action not in ("noop", "close", "view_chart", "copy_ca"):
                _demo_nav_push(context, data)
        except Exception:
            pass

    action = data.split(":")[1] if ":" in data else data

    # Build shared state for modular handlers
    wallet_address = "Not configured"
    sol_balance = 0.0
    usd_value = 0.0
    total_pnl = 0.0
    is_live = False
    positions: List[Dict[str, Any]] = []

    try:
        engine = await asyncio.wait_for(_get_demo_engine(), timeout=8.0)
        treasury = engine.wallet.get_treasury()
        if treasury:
            wallet_address = treasury.address

        sol_balance, usd_value = await asyncio.wait_for(engine.get_portfolio_value(), timeout=6.0)

        await asyncio.wait_for(engine.update_positions(), timeout=8.0)
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
        market_regime = await asyncio.wait_for(get_market_regime(), timeout=4.0)
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
         
        # Handler returned (None, None) = it already sent its own response
        if text is None and keyboard is None:
            logger.debug(f"[DEMO_CALLBACK] Handler returned None, None for action={action}")
            return

        if text is None:
            logger.debug(f"[DEMO_CALLBACK] Handler returned no text for action={action}")
            return

        # Ensure every page has a "Previous Menu" button (user UX requirement).
        keyboard = _ensure_prev_menu_button(keyboard)
         
        logger.info(f"[DEMO_CALLBACK] Got response for action={action}, text_len={len(text) if text else 0}, has_keyboard={keyboard is not None}")
         
        try:
            await query.message.edit_text(
                text,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=keyboard,
            )
            logger.debug(f"[DEMO_CALLBACK] Message edited successfully for action={action}")
        except BadRequest as exc:
            logger.warning(f"[DEMO_CALLBACK] BadRequest editing message for action={action}: {exc}")
            # Markdown can fail on dynamic content (unescaped _,*,`, etc). Fallback to plain text.
            if "can\u0027t parse entities" in str(exc).lower() or "can't parse entities" in str(exc).lower():
                try:
                    await query.message.edit_text(
                        text,
                        reply_markup=keyboard,
                        disable_web_page_preview=True,
                    )
                    logger.info(f"[DEMO_CALLBACK] Fallback edit_text without parse_mode succeeded for action={action}")
                    return
                except Exception as exc2:
                    logger.error(f"[DEMO_CALLBACK] Fallback edit_text failed for action={action}: {exc2}")
                    raise
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
        keyboard = _ensure_prev_menu_button(keyboard)
        try:
            await query.message.edit_text(
                text,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=keyboard,
            )
        except BadRequest as exc:
            # If even the error UI fails markdown, fall back to plain text
            if "can't parse entities" in str(exc).lower():
                try:
                    await query.message.edit_text(
                        text,
                        reply_markup=keyboard,
                        disable_web_page_preview=True,
                    )
                    return
                except Exception as edit_err:
                    logger.error(f"Failed to edit message after markdown error fallback: {edit_err}")
            logger.error(f"Failed to edit message after error: {exc}")
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
    # Null check - exit early if no message or text
    if not update.message or not update.message.text:
        return
    text = update.message.text.strip()
    
    # Debug logging
    user_id = update.message.from_user.id if update.message and update.message.from_user else 0
    awaiting_states = {
        "awaiting_custom_buy_amount": context.user_data.get("awaiting_custom_buy_amount"),
        "awaiting_watchlist_token": context.user_data.get("awaiting_watchlist_token"),
        "awaiting_wallet_import": context.user_data.get("awaiting_wallet_import"),
        "awaiting_token": context.user_data.get("awaiting_token"),
        "awaiting_token_search": context.user_data.get("awaiting_token_search"),
    }
    logger.info(f"[DEMO MSG] user={user_id} text='{text[:30]}...' awaiting={awaiting_states}")

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
            # Silent ignore for non-admins (prevents spam in group chats)
            logger.warning(f"Unauthorized demo message by user {user_id} (@{username})")
            return
    except Exception as exc:
        logger.warning(f"Demo message admin check failed: {exc}")

    # Run TP/SL/trailing stop checks for demo positions (throttled)
    await _process_demo_exit_checks(update, context)

    # Check if we're awaiting any input
    if not any([
        context.user_data.get("awaiting_custom_buy_amount"),
        context.user_data.get("awaiting_watchlist_token"),
        context.user_data.get("awaiting_wallet_import"),
        context.user_data.get("awaiting_token"),
        context.user_data.get("awaiting_token_search"),
    ]):
        return

    # Import modular handlers
    from .input_handlers import (
        handle_custom_buy_amount,
        handle_custom_hub_amount,
        handle_watchlist_token,
        handle_wallet_import,
        handle_token_input,
    )

    # Delegate to appropriate handler (first match wins)
    handlers = [
        handle_custom_buy_amount,
        handle_custom_hub_amount,
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
    from telegram.ext import CommandHandler, CallbackQueryHandler

    app.add_handler(CommandHandler("demo", demo))
    app.add_handler(CallbackQueryHandler(demo_callback, pattern=r"^demo:"))
    # NOTE: Do not register a catch-all text MessageHandler here.
    #
    # PTB executes at most one handler per group; a broad text handler would
    # intercept all user messages (including public DM wallet import flows),
    # causing the rest of the bot to appear "broken" and risking sensitive
    # message logging/leakage.
    #
    # Text routing for demo input is handled by the global message router in
    # tg_bot/bot.py, which only delegates to demo_message_handler when demo
    # is explicitly awaiting input.

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
