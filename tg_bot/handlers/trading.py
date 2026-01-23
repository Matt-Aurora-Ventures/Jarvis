"""Handlers for trading-related commands and callbacks."""

import logging

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from tg_bot.config import get_config
from tg_bot.services import digest_formatter as fmt
from tg_bot.services.digest_formatter import escape_markdown_v1 as escape_md
from tg_bot.handlers import error_handler, admin_only
from tg_bot.handlers.admin import reload, config_cmd, logs, system
from tg_bot.handlers.sentiment import digest

# Import interactive UI components
from tg_bot.handlers.interactive_ui import (
    is_new_ui_enabled,
    route_interactive_callback,
)

# Error tracking integration
from core.logging.error_tracker import error_tracker

logger = logging.getLogger(__name__)

# Rate limiting for button callbacks to prevent flood control
import time as _time
_CALLBACK_RATE_LIMIT: dict = {}  # user_id -> last_callback_time
_CALLBACK_MIN_INTERVAL = 1.0  # Minimum seconds between callbacks per user


def _is_rate_limited(user_id: int) -> bool:
    """Check if user is rate limited for callbacks."""
    now = _time.time()
    last_time = _CALLBACK_RATE_LIMIT.get(user_id, 0)
    if now - last_time < _CALLBACK_MIN_INTERVAL:
        return True
    _CALLBACK_RATE_LIMIT[user_id] = now
    # Clean old entries periodically
    if len(_CALLBACK_RATE_LIMIT) > 1000:
        cutoff = now - 60
        _CALLBACK_RATE_LIMIT.clear()
    return False


def _escape_markdown(text: str) -> str:
    """Escape markdown special characters to prevent entity parsing errors."""
    # Escape in order: \ first, then others
    escape_chars = ['\\', '_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
    for char in escape_chars:
        text = text.replace(char, f'\\{char}')
    return text


async def _safe_reply(message, text: str, parse_mode=None, **kwargs):
    """Safely reply with markdown, falling back to plain text on parse errors."""
    try:
        return await message.reply_text(text, parse_mode=parse_mode, **kwargs)
    except Exception as e:
        if "can't parse entities" in str(e).lower():
            # Markdown parsing failed, try plain text
            logger.warning(f"Markdown parse failed, using plain text: {e}")
            # Remove markdown formatting and try again
            plain_text = text.replace('*', '').replace('_', '').replace('`', '')
            return await message.reply_text(plain_text, **kwargs)
        raise


async def _safe_edit(message, text: str, parse_mode=None, **kwargs):
    """Safely edit message with markdown, falling back to plain text on parse errors."""
    try:
        return await message.edit_text(text, parse_mode=parse_mode, **kwargs)
    except Exception as e:
        if "can't parse entities" in str(e).lower():
            # Markdown parsing failed, try plain text
            logger.warning(f"Markdown parse failed on edit, using plain text: {e}")
            plain_text = text.replace('*', '').replace('_', '').replace('`', '')
            return await message.edit_text(plain_text, **kwargs)
        raise


async def _cleanup_menu_message(query):
    """Remove or neutralize the original menu message after opening a submenu."""
    if not query or not getattr(query, "message", None):
        return
    try:
        await query.message.delete()
        return
    except Exception as exc:
        try:
            await query.message.edit_reply_markup(reply_markup=None)
        except Exception:
            logger.debug(f"Failed to cleanup menu message: {exc}")


# Structured error logging integration
def _log_tg_error(error: Exception, context: str, metadata: dict = None):
    """Log Telegram handler error with structured data."""
    try:
        from core.monitoring.supervisor_health_bus import log_component_error
        log_component_error(
            component="telegram_bot",
            error=error,
            context={"handler": context, **(metadata or {})},
            severity="error"
        )
    except ImportError:
        logger.error(f"[{context}] {error}", exc_info=True)


@error_handler
@admin_only
async def balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /balance - Show treasury balance and allocation.
    """
    try:
        from tg_bot import bot_core as bot_module
        config = get_config()
        engine = await bot_module._get_treasury_engine()
        sol_balance, usd_value = await engine.get_portfolio_value()
        mode = "\U0001f7e2 LIVE" if not engine.dry_run else "\U0001f7e1 PAPER"

        # Get wallet address
        treasury = engine.wallet.get_treasury()
        address = treasury.address if treasury else "Unknown"
        short_addr = f"{address[:8]}...{address[-4:]}" if address else "N/A"

        # JARVIS voice - lowercase, no corporate filler
        message = f"""*treasury status*

wallet: `{short_addr}`
sol: `{sol_balance:.4f}` | usd: `${usd_value:,.2f}`

mode: {mode}
max positions: {engine.max_positions}
risk: {engine.risk_level.value}
"""

        # Warning if low balance (configurable via LOW_BALANCE_THRESHOLD env var)
        if sol_balance < config.low_balance_threshold:
            message += f"\n_running low. under {config.low_balance_threshold} sol._"

        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("\U0001f504 Refresh", callback_data="refresh_balance"),
                InlineKeyboardButton("\U0001f4ca Report", callback_data="refresh_report"),
            ]
        ])

        await update.message.reply_text(
            message,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=keyboard,
        )

    except Exception as e:
        logger.error(f"Balance check failed: {e}")
        from tg_bot.bot_core import safe_error_text
        await update.message.reply_text(
            f"*something broke*\n\ncouldn't pull balance: {safe_error_text(e)}",
            parse_mode=ParseMode.MARKDOWN,
        )


@error_handler
@admin_only
async def positions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /positions - Show open positions with P&L and sell buttons.
    """
    try:
        from tg_bot import bot_core as bot_module
        engine = await bot_module._get_treasury_engine()
        await engine.update_positions()
        open_positions = engine.get_open_positions()

        if not open_positions:
            await update.message.reply_text(
                "*positions*\n\n_nothing open right now._\n\nrun /report if you want to find something.",
                parse_mode=ParseMode.MARKDOWN,
            )
            return

        lines = ["*positions*", ""]

        keyboard_rows = []
        total_pnl = 0

        for pos in open_positions:
            pnl_pct = pos.unrealized_pnl_pct
            pnl_usd = pos.unrealized_pnl
            total_pnl += pnl_usd

            pnl_emoji = "\U0001f7e2" if pnl_pct >= 0 else "\U0001f534"
            safe_symbol = escape_md(pos.token_symbol or "???")

            lines.append(f"*{safe_symbol}* {pnl_emoji}")
            lines.append(f"   Entry: ${pos.entry_price:.8f}")
            lines.append(f"   Current: ${pos.current_price:.8f}")
            lines.append(f"   P&L: {pnl_pct:+.1f}% (${pnl_usd:+.2f})")
            lines.append(f"   \U0001f3af TP: ${pos.take_profit_price:.8f}")
            lines.append(f"   \U0001f6d1 SL: ${pos.stop_loss_price:.8f}")
            lines.append(f"   ID: `{pos.id}`")
            lines.append("")

            # Add sell button for each position
            keyboard_rows.append([
                InlineKeyboardButton(
                    f"\U0001f534 SELL {pos.token_symbol}",
                    callback_data=f"sell_pos:{pos.id}"
                )
            ])

        # Summary
        total_emoji = "\U0001f7e2" if total_pnl >= 0 else "\U0001f534"
        lines.append(f"\u2500" * 20)
        lines.append(f"*Total P&L:* {total_emoji} ${total_pnl:+.2f}")

        keyboard_rows.append([
            InlineKeyboardButton("\U0001f504 Refresh", callback_data="show_positions_detail"),
        ])

        await update.message.reply_text(
            "\n".join(lines),
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup(keyboard_rows),
            disable_web_page_preview=True,
        )

    except Exception as e:
        logger.error(f"Positions check failed: {e}")
        from tg_bot.bot_core import safe_error_text
        await update.message.reply_text(
            f"*something broke*\n\ncouldn't pull positions: {safe_error_text(e)}",
            parse_mode=ParseMode.MARKDOWN,
        )


@error_handler
@admin_only
async def wallet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /wallet command - show treasury wallet info (admin only)."""
    try:
        from core.security.key_manager import get_key_manager
        km = get_key_manager()

        address = km.get_treasury_address()
        status = km.get_status_report()

        # JARVIS voice
        lines = ["<b>wallet</b>", ""]

        if address:
            lines.append(f"address: <code>{address[:8]}...{address[-6:]}</code>")
            lines.append(f"full: <code>{address}</code>")
            lines.append("")
            lines.append(f"<a href='https://solscan.io/account/{address}'>view on solscan</a>")
        else:
            lines.append("wallet not set up yet")

        lines.append("")
        lines.append(f"status: {status.get('status', 'unknown')}")

        await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.HTML, disable_web_page_preview=True)
    except Exception as e:
        from tg_bot.bot_core import safe_error_text
        await update.message.reply_text(f"Wallet error: {safe_error_text(e)}", parse_mode=ParseMode.MARKDOWN)


@error_handler
@admin_only
async def dashboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /dashboard - Enhanced real-time positions with P&L, treasury stats, and quick actions.
    """
    import asyncio
    import aiohttp

    from bots.treasury.scorekeeper import get_scorekeeper
    from tg_bot import bot_core as bot_module

    engine = await bot_module._get_treasury_engine()
    await engine.update_positions()
    positions = engine.get_open_positions()

    scorekeeper = get_scorekeeper()
    scorecard = scorekeeper.scorecard

    # Get portfolio value
    try:
        sol_balance, usd_value = await engine.get_portfolio_value()
    except Exception:
        sol_balance, usd_value = 0.0, 0.0

    mode = "live" if not engine.dry_run else "paper"

    def fmt_price(price: float) -> str:
        if price <= 0:
            return "N/A"
        return f"${price:.8f}" if price < 0.01 else f"${price:.4f}"

    async def fetch_price(session: aiohttp.ClientSession, token_mint: str) -> float:
        url = f"https://api.dexscreener.com/latest/dex/tokens/{token_mint}"
        try:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status != 200:
                    return 0.0
                data = await resp.json()
                pairs = data.get("pairs", []) or []
                if not pairs:
                    return 0.0
                best = max(
                    pairs,
                    key=lambda p: (p.get("liquidity", {}) or {}).get("usd", 0) or 0
                )
                price = float(best.get("priceUsd", 0) or 0)
                return price
        except Exception:
            return 0.0

    # Quick action buttons
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("refresh", callback_data="refresh_dashboard"),
            InlineKeyboardButton("positions", callback_data="show_positions_detail"),
        ],
        [
            InlineKeyboardButton("report", callback_data="refresh_report"),
            InlineKeyboardButton("balance", callback_data="refresh_balance"),
        ]
    ])

    if not positions:
        # JARVIS voice - lowercase, casual with more context
        summary_lines = [
            "*dashboard*",
            f"_mode: {mode}_",
            "",
            f"portfolio: `{sol_balance:.4f}` sol (~${usd_value:,.0f})",
            "",
            f"stats:",
            f"  win rate: {scorecard.win_rate:.1f}%",
            f"  streak: {scorecard.current_streak:+d}",
            f"  realized: {scorecard.total_pnl_sol:+.4f} sol",
            "",
            "_nothing open. waiting for opportunities._",
        ]
        await update.message.reply_text(
            "\n".join(summary_lines),
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=keyboard,
        )
        return

    async with aiohttp.ClientSession() as session:
        prices = await asyncio.gather(*[
            fetch_price(session, pos.token_mint) for pos in positions
        ])

    total_unrealized = 0.0
    total_invested = 0.0
    best_pos = None
    worst_pos = None
    best_pnl = float('-inf')
    worst_pnl = float('inf')

    # Calculate totals and find best/worst
    for pos, price in zip(positions, prices):
        if price > 0:
            pos.current_price = price
        pnl_pct = pos.unrealized_pnl_pct
        pnl_usd = pos.unrealized_pnl
        total_unrealized += pnl_usd
        total_invested += pos.entry_usd if hasattr(pos, 'entry_usd') else 0

        if pnl_pct > best_pnl:
            best_pnl = pnl_pct
            best_pos = pos
        if pnl_pct < worst_pnl:
            worst_pnl = pnl_pct
            worst_pos = pos

    # JARVIS voice - enhanced dashboard
    lines = [
        "*dashboard*",
        f"_mode: {mode} | {len(positions)} positions_",
        "",
        f"portfolio: `{sol_balance:.4f}` sol (~${usd_value:,.0f})",
        "",
        f"stats:",
        f"  win rate: {scorecard.win_rate:.1f}%",
        f"  streak: {scorecard.current_streak:+d}",
        f"  realized: {scorecard.total_pnl_sol:+.4f} sol",
        "",
    ]

    # Best/worst performers
    if best_pos and len(positions) > 1:
        lines.append(f"top: *{escape_md(best_pos.token_symbol)}* {best_pnl:+.1f}%")
    if worst_pos and len(positions) > 1 and worst_pos != best_pos:
        lines.append(f"bottom: *{escape_md(worst_pos.token_symbol)}* {worst_pnl:+.1f}%")
    if best_pos or worst_pos:
        lines.append("")

    lines.append("*positions:*")

    for pos, price in zip(positions, prices):
        if price > 0:
            pos.current_price = price
        pnl_usd = pos.unrealized_pnl
        pnl_pct = pos.unrealized_pnl_pct

        pnl_emoji = "\U0001f7e2" if pnl_usd >= 0 else "\U0001f534"
        current_price = pos.current_price if pos.current_price > 0 else pos.entry_price
        safe_symbol = escape_md(pos.token_symbol or "???")

        lines.append(f"{pnl_emoji} *{safe_symbol}* {pnl_pct:+.1f}%")
        lines.append(f"   {fmt_price(pos.entry_price)} \u2192 {fmt_price(current_price)}")

    total_emoji = "\U0001f7e2" if total_unrealized >= 0 else "\U0001f534"
    lines.append("")
    lines.append(f"unrealized: {total_emoji} ${total_unrealized:+.2f}")

    await update.message.reply_text(
        "\n".join(lines),
        parse_mode=ParseMode.MARKDOWN,
        disable_web_page_preview=True,
        reply_markup=keyboard,
    )


@error_handler
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle inline keyboard button presses."""
    from telegram.error import BadRequest, TimedOut, NetworkError, RetryAfter
    import asyncio
    import time

    from tg_bot import bot_core as bot_module

    # Aliases for handlers/helpers still hosted in bot.py
    signals = bot_module.signals
    analyze = bot_module.analyze
    brain = bot_module.brain
    health = bot_module.health
    flags = bot_module.flags
    score = bot_module.score
    orders = bot_module.orders
    metrics = bot_module.metrics
    audit = bot_module.audit
    _handle_trending_inline = bot_module._handle_trending_inline
    _handle_status_inline = bot_module._handle_status_inline
    _handle_expand_section = bot_module._handle_expand_section
    _execute_trade_percent = bot_module._execute_trade_percent
    _execute_trade_with_tp_sl = bot_module._execute_trade_with_tp_sl
    _close_position_callback = bot_module._close_position_callback
    _refresh_report_inline = bot_module._refresh_report_inline
    _refresh_balance_inline = bot_module._refresh_balance_inline
    _show_positions_inline = bot_module._show_positions_inline
    _toggle_live_mode = bot_module._toggle_live_mode
    _show_trade_ticket = bot_module._show_trade_ticket
    _execute_ape_trade = bot_module._execute_ape_trade
    _handle_dev_refine = bot_module._handle_dev_refine
    _handle_dev_copy = bot_module._handle_dev_copy
    _send_with_retry = bot_module._send_with_retry
    CallbackUpdate = bot_module.CallbackUpdate
    _is_treasury_admin = bot_module._is_treasury_admin
    APE_BUTTONS_AVAILABLE = bot_module.APE_BUTTONS_AVAILABLE

    query = update.callback_query
    data = query.data if query else "None"
    user_id = update.effective_user.id if update.effective_user else 0
    username = update.effective_user.username if update.effective_user else None
    callback_start = time.time()

    # ENTRY LOGGING: Track all callback entries for debugging
    logger.info(f"[CALLBACK_ENTRY] data='{data}' user={user_id} msg_id={query.message.message_id if query and query.message else 'N/A'}")

    # RATE LIMITING: Prevent button hammering / flood control
    if _is_rate_limited(user_id):
        logger.debug(f"[RATE_LIMITED] user={user_id} data='{data}'")
        try:
            await query.answer("Too fast! Wait a moment.", show_alert=False)
        except Exception:
            pass
        return

    # CRITICAL: Always answer callback first to stop loading spinner
    answer_success = False
    try:
        await query.answer()
        answer_success = True
    except BadRequest as e:
        logger.warning(f"[CALLBACK_ANSWER] Could not answer callback (stale?): {e}")
        # Continue processing even if answer fails
    except Exception as e:
        logger.error(f"[CALLBACK_ANSWER] Error answering callback: {e}")
        error_tracker.track_error(
            e,
            context=f"button_callback.answer:{data}",
            component="telegram_callback",
            metadata={"user_id": user_id, "callback_data": data}
        )

    # Check if query.message exists (can be None for inline mode)
    if not query.message:
        logger.warning(f"Callback has no message object: {data}")
        return

    config = get_config()

    # Route to interactive UI handler for new UI callbacks
    # This handles: chart:, holders:, trades:, signal:, details:, ui_close:, etc.
    if is_new_ui_enabled():
        interactive_prefixes = (
            "chart:", "holders:", "holders_page:", "holders_top100:",
            "trades:", "trades_whales:", "trades_100:",
            "signal:", "signal_details:", "signal_remind:",
            "details:", "analyze_back:", "ui_close:",
            "chart_1h:", "chart_4h:", "chart_1d:", "chart_1w:",
            "watch_view:", "watch_remove:", "watch_add", "watch_clear", "watch_refresh",
            "compare_sort:", "compare_details:",
            "noop",
        )
        if data.startswith(interactive_prefixes) or data == "noop":
            handled = await route_interactive_callback(query, context, user_id)
            if handled:
                return

    # Quick action callbacks (top of menu for admins)
    if data == "quick_dashboard":
        if not config.is_admin(user_id, username):
            await query.message.reply_text(fmt.format_unauthorized(), parse_mode=ParseMode.MARKDOWN)
            return
        cb_update = CallbackUpdate(query)
        context.args = []
        await dashboard(cb_update, context)
        await _cleanup_menu_message(query)
        return

    if data == "quick_report":
        if not config.is_admin(user_id, username):
            await query.message.reply_text(fmt.format_unauthorized(), parse_mode=ParseMode.MARKDOWN)
            return
        from tg_bot.handlers.sentiment import report
        cb_update = CallbackUpdate(query)
        context.args = []
        await report(cb_update, context)
        await _cleanup_menu_message(query)
        return

    # Handle quick command callbacks
    quick_callbacks = [
        "quick_positions", "quick_balance", "quick_market", "quick_wallet",
        "quick_alerts", "quick_health", "quick_stats", "quick_trending",
        "quick_full_menu"
    ]
    if data in quick_callbacks:
        from tg_bot.handlers.commands.quick_command import handle_quick_callback
        await handle_quick_callback(update, context)
        return

    # Menu navigation callbacks
    if data == "menu_trending":
        await _handle_trending_inline(query)
        return

    if data == "menu_status":
        await _handle_status_inline(query)
        return

    if data == "menu_costs":
        message = fmt.format_cost_report()
        keyboard = [[InlineKeyboardButton("\U0001f3e0 Back to Menu", callback_data="menu_back")]]
        try:
            await query.message.edit_text(
                message,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=InlineKeyboardMarkup(keyboard),
            )
        except Exception as e:
            logger.warning(f"Failed to edit message for menu_costs: {e}")
            await query.message.reply_text(
                message,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=InlineKeyboardMarkup(keyboard),
            )
        return

    if data == "menu_help":
        # JARVIS voice
        help_text = """*commands*

_anyone can use:_
/trending - what's hot
/status - api health
/costs - today's bill

_admin only:_
/signals - the good stuff
/analyze <token> - deep dive
/digest - market summary
/brain - how my circuits are doing
"""
        keyboard = [[InlineKeyboardButton("back", callback_data="menu_back")]]
        try:
            await query.message.edit_text(
                help_text,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=InlineKeyboardMarkup(keyboard),
            )
        except Exception as e:
            logger.warning(f"Failed to edit message for menu_help: {e}")
            await query.message.reply_text(
                help_text,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=InlineKeyboardMarkup(keyboard),
            )
        return

    if data == "menu_back":
        # Edit current message to show main menu (not reply)
        is_admin = config.is_admin(user_id, username)
        keyboard = [
            [
                InlineKeyboardButton("\U0001f4c8 Trending", callback_data="menu_trending"),
                InlineKeyboardButton("\U0001f4ca Status", callback_data="menu_status"),
            ],
            [
                InlineKeyboardButton("\U0001f4b0 Costs", callback_data="menu_costs"),
                InlineKeyboardButton("\u2753 Help", callback_data="menu_help"),
            ],
        ]
        if is_admin:
            keyboard.insert(0, [
                InlineKeyboardButton("\U0001f680 SIGNALS", callback_data="menu_signals"),
                InlineKeyboardButton("\U0001f4cb Digest", callback_data="menu_digest"),
            ])
            keyboard.append([
                InlineKeyboardButton("\U0001f9e0 Brain Stats", callback_data="menu_brain"),
                InlineKeyboardButton("\U0001f504 Reload", callback_data="menu_reload"),
            ])
        try:
            await query.message.edit_text(
                "*jarvis*\n\n_pick something:_",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=InlineKeyboardMarkup(keyboard),
            )
        except Exception as e:
            logger.warning(f"Failed to edit message for menu_back: {e}")
            # Only fall back to reply if edit fails
            await query.message.reply_text(
                "*jarvis*\n\n_pick something:_",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=InlineKeyboardMarkup(keyboard),
            )
        return

    # Admin-only menu callbacks - use CallbackUpdate wrapper
    if data == "menu_signals":
        if not config.is_admin(user_id, username):
            await query.message.reply_text(fmt.format_unauthorized(), parse_mode=ParseMode.MARKDOWN)
            return
        cb_update = CallbackUpdate(query)
        context.args = []
        await signals(cb_update, context)
        await _cleanup_menu_message(query)
        return

    if data == "menu_digest":
        if not config.is_admin(user_id, username):
            await query.message.reply_text(fmt.format_unauthorized(), parse_mode=ParseMode.MARKDOWN)
            return
        cb_update = CallbackUpdate(query)
        context.args = []
        await digest(cb_update, context)
        await _cleanup_menu_message(query)
        return

    if data == "menu_brain":
        if not config.is_admin(user_id, username):
            await query.message.reply_text(fmt.format_unauthorized(), parse_mode=ParseMode.MARKDOWN)
            return
        cb_update = CallbackUpdate(query)
        context.args = []
        await brain(cb_update, context)
        await _cleanup_menu_message(query)
        return

    if data == "menu_reload":
        if not config.is_admin(user_id, username):
            await query.message.reply_text(fmt.format_unauthorized(), parse_mode=ParseMode.MARKDOWN)
            return
        cb_update = CallbackUpdate(query)
        context.args = []
        await reload(cb_update, context)
        await _cleanup_menu_message(query)
        return

    if data == "menu_health":
        if not config.is_admin(user_id, username):
            await query.message.reply_text(fmt.format_unauthorized(), parse_mode=ParseMode.MARKDOWN)
            return
        cb_update = CallbackUpdate(query)
        context.args = []
        await health(cb_update, context)
        await _cleanup_menu_message(query)
        return

    if data == "menu_flags":
        if not config.is_admin(user_id, username):
            await query.message.reply_text(fmt.format_unauthorized(), parse_mode=ParseMode.MARKDOWN)
            return
        cb_update = CallbackUpdate(query)
        context.args = []
        await flags(cb_update, context)
        await _cleanup_menu_message(query)
        return

    if data == "menu_score":
        if not config.is_admin(user_id, username):
            await query.message.reply_text(fmt.format_unauthorized(), parse_mode=ParseMode.MARKDOWN)
            return
        cb_update = CallbackUpdate(query)
        context.args = []
        await score(cb_update, context)
        await _cleanup_menu_message(query)
        return

    if data == "menu_config":
        if not config.is_admin(user_id, username):
            await query.message.reply_text(fmt.format_unauthorized(), parse_mode=ParseMode.MARKDOWN)
            return
        cb_update = CallbackUpdate(query)
        context.args = []
        await config_cmd(cb_update, context)
        await _cleanup_menu_message(query)
        return

    if data == "menu_system":
        if not config.is_admin(user_id, username):
            await query.message.reply_text(fmt.format_unauthorized(), parse_mode=ParseMode.MARKDOWN)
            return
        cb_update = CallbackUpdate(query)
        context.args = []
        await system(cb_update, context)
        await _cleanup_menu_message(query)
        return

    if data == "menu_orders":
        if not config.is_admin(user_id, username):
            await query.message.reply_text(fmt.format_unauthorized(), parse_mode=ParseMode.MARKDOWN)
            return
        cb_update = CallbackUpdate(query)
        context.args = []
        await orders(cb_update, context)
        await _cleanup_menu_message(query)
        return

    if data == "menu_wallet":
        if not config.is_admin(user_id, username):
            await query.message.reply_text(fmt.format_unauthorized(), parse_mode=ParseMode.MARKDOWN)
            return
        cb_update = CallbackUpdate(query)
        context.args = []
        await wallet(cb_update, context)
        await _cleanup_menu_message(query)
        return

    if data == "menu_logs":
        if not config.is_admin(user_id, username):
            await query.message.reply_text(fmt.format_unauthorized(), parse_mode=ParseMode.MARKDOWN)
            return
        cb_update = CallbackUpdate(query)
        context.args = []
        await logs(cb_update, context)
        await _cleanup_menu_message(query)
        return

    if data == "menu_metrics":
        if not config.is_admin(user_id, username):
            await query.message.reply_text(fmt.format_unauthorized(), parse_mode=ParseMode.MARKDOWN)
            return
        cb_update = CallbackUpdate(query)
        context.args = []
        await metrics(cb_update, context)
        await _cleanup_menu_message(query)
        return

    if data == "menu_audit":
        if not config.is_admin(user_id, username):
            await query.message.reply_text(fmt.format_unauthorized(), parse_mode=ParseMode.MARKDOWN)
            return
        cb_update = CallbackUpdate(query)
        context.args = []
        await audit(cb_update, context)
        await _cleanup_menu_message(query)
        return

    # Trading callbacks
    if data.startswith("trade_"):
        if not _is_treasury_admin(config, user_id):
            await query.message.reply_text(fmt.format_unauthorized(), parse_mode=ParseMode.MARKDOWN)
            return

        token_address = data.replace("trade_", "", 1)
        await _show_trade_ticket(query, token_address)
        return

    if data.startswith("buy_"):
        if not _is_treasury_admin(config, user_id):
            await query.message.reply_text(fmt.format_unauthorized(), parse_mode=ParseMode.MARKDOWN)
            return

        await _execute_trade_percent(query, data)
        return

    # Token-specific callbacks
    if data.startswith("analyze_"):
        if not config.is_admin(user_id, username):
            await query.message.reply_text(fmt.format_unauthorized(), parse_mode=ParseMode.MARKDOWN)
            return

        token = data.replace("analyze_", "")
        context.args = [token]
        cb_update = CallbackUpdate(query)
        await analyze(cb_update, context)
        return

    if data == "refresh_trending":
        await _handle_trending_inline(query)
        return

    # New trading callbacks
    if data.startswith("trade_pct:"):
        if not _is_treasury_admin(config, user_id):
            await query.message.reply_text(
                "*nope*\n\nyou're not on the list.",
                parse_mode=ParseMode.MARKDOWN
            )
            logger.warning(f"Unauthorized trade attempt by user {user_id}")
            return

        await _execute_trade_with_tp_sl(query, data)
        return

    if data.startswith("sell_pos:"):
        if not _is_treasury_admin(config, user_id):
            await query.message.reply_text("*nope*\n\nnot authorized.", parse_mode=ParseMode.MARKDOWN)
            return

        position_id = data.split(":")[1]
        await _close_position_callback(query, position_id)
        return

    if data == "refresh_report":
        if not _is_treasury_admin(config, user_id):
            return
        await _refresh_report_inline(query)
        return

    if data == "refresh_balance":
        if not _is_treasury_admin(config, user_id):
            return
        await _refresh_balance_inline(query)
        return

    if data == "refresh_dashboard":
        if not _is_treasury_admin(config, user_id):
            return
        # Re-generate dashboard inline
        await query.message.reply_text("_refreshing dashboard..._", parse_mode=ParseMode.MARKDOWN)
        # Import and call dashboard logic
        cb_update = CallbackUpdate(query)
        await dashboard(cb_update, context)
        return

    if data == "show_positions_detail":
        if not _is_treasury_admin(config, user_id):
            return
        await _show_positions_inline(query)
        return

    if data == "toggle_live_mode":
        if not _is_treasury_admin(config, user_id):
            return
        await _toggle_live_mode(query)
        return

    # Expand button callbacks from sentiment reports (format: expand:{section})
    if data.startswith("expand:"):
        logger.info(f"Expand callback received: {data} from user {user_id}")
        section = data.replace("expand:", "")
        await _handle_expand_section(query, section, config, user_id)
        return

    # Dev/vibe coding callbacks (format: dev_refine:{id} or dev_copy:{id})
    if data.startswith("dev_refine:"):
        if not config.is_admin(user_id, username):
            await query.message.reply_text(fmt.format_unauthorized(), parse_mode=ParseMode.MARKDOWN)
            return
        result_id = data.replace("dev_refine:", "")
        await _handle_dev_refine(query, result_id, context)
        return

    if data.startswith("dev_copy:"):
        if not config.is_admin(user_id, username):
            await query.message.reply_text(fmt.format_unauthorized(), parse_mode=ParseMode.MARKDOWN)
            return
        result_id = data.replace("dev_copy:", "")
        await _handle_dev_copy(query, result_id)
        return

    # Ape button callbacks from sentiment reports (format: ape:{alloc}:{profile}:{type}:{symbol}:{contract})
    if data.startswith("ape:"):
        logger.info(f"[APE_CALLBACK] Ape callback received: {data} from user {user_id}")

        if not APE_BUTTONS_AVAILABLE:
            await _send_with_retry(
                query,
                "ape module offline. can't do that right now.",
                parse_mode=ParseMode.MARKDOWN
            )
            logger.error("[APE_CALLBACK] APE_BUTTONS_AVAILABLE is False")
            return

        if not _is_treasury_admin(config, user_id):
            await _send_with_retry(
                query,
                f"*nope*\n\nuser {user_id} isn't on the list.",
                parse_mode=ParseMode.MARKDOWN
            )
            logger.warning(f"[APE_CALLBACK] Unauthorized ape trade attempt by user {user_id}")
            return

        try:
            logger.info(f"[APE_CALLBACK] Executing ape trade for {data}")
            await _execute_ape_trade(query, data)
            logger.info(f"[APE_CALLBACK] Ape trade completed for {data}")
        except Exception as e:
            logger.error(f"[APE_CALLBACK] APE trade failed: {e}", exc_info=True)
            error_tracker.track_error(
                e,
                context=f"button_callback.ape_trade:{data}",
                component="telegram_callback",
                metadata={"user_id": user_id, "callback_data": data}
            )
            from tg_bot.bot_core import safe_error_text
            await _send_with_retry(
                query,
                f"*trade failed*\n\n{safe_error_text(e, max_len=120)}",
                parse_mode=ParseMode.MARKDOWN
            )
        return

    # Unhandled callback - log for debugging
    logger.warning(f"[CALLBACK_UNHANDLED] No handler matched for callback: '{data}' from user {user_id}")


@error_handler
@admin_only
async def calibrate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /calibrate - Show pick performance and TP/SL calibration stats.
    """
    try:
        from bots.treasury.scorekeeper import get_scorekeeper
        sk = get_scorekeeper()

        # Get performance and calibration data
        perf = sk.get_historical_performance()
        cal = sk.get_calibration_stats()
        open_picks = sk.get_open_picks()

        lines = ["<b>pick performance calibration</b>", ""]

        # Overall performance
        if perf.get('total_picks', 0) > 0:
            lines.append(f"📊 <b>Overall:</b>")
            lines.append(f"  picks: {perf['total_picks']} | wins: {perf['wins']} | losses: {perf['losses']}")
            lines.append(f"  win rate: {perf['win_rate']}%")
            lines.append(f"  avg gain: +{perf['avg_gain_pct']}% | avg loss: {perf['avg_loss_pct']}%")
            if perf.get('high_conviction_win_rate'):
                lines.append(f"  high conviction (70+): {perf['high_conviction_win_rate']}% win rate")
            lines.append("")
        else:
            lines.append("<i>no closed picks yet - tracking started</i>")
            lines.append("")

        # Calibration insights
        if cal.get('total_closed', 0) > 0:
            lines.append("🎯 <b>TP/SL Calibration:</b>")
            lines.append(f"  TP hits: {cal['tp_hits']} | SL hits: {cal['sl_hits']} | expired: {cal['expired']}")
            if cal.get('avg_max_gain_before_sl'):
                lines.append(f"  avg max gain before SL: +{cal['avg_max_gain_before_sl']}%")
            if cal.get('avg_pnl_at_tp'):
                lines.append(f"  avg pnl at TP: +{cal['avg_pnl_at_tp']}%")
            if cal.get('optimal_tp_suggestion'):
                lines.append(f"  💡 {cal['optimal_tp_suggestion']}")
            lines.append("")

        # Open picks summary
        lines.append(f"📈 <b>Open Picks:</b> {len(open_picks)}")
        if open_picks:
            for pick in open_picks[:5]:
                # HTML needs different escaping - use basic text escape
                symbol = str(pick.get('symbol', '?')).replace('<', '&lt;').replace('>', '&gt;')
                conv = pick.get('conviction_score', 0)
                days = pick.get('days_held', 0)
                pnl = pick.get('pnl_pct', 0)
                emoji = "🟢" if pnl > 0 else "🔴" if pnl < 0 else "⚪"
                lines.append(f"  {emoji} {symbol}: {pnl:+.1f}% (conv:{conv}, {days}d)")
            if len(open_picks) > 5:
                lines.append(f"  <i>...and {len(open_picks) - 5} more</i>")

        await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.HTML)

    except Exception as e:
        logger.error(f"Calibrate error: {e}")
        from tg_bot.bot_core import safe_error_text
        await update.message.reply_text(
            f"calibration error: {safe_error_text(e)}",
            parse_mode=ParseMode.MARKDOWN
        )
