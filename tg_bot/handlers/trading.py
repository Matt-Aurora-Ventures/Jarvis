"""Handlers for trading-related commands and callbacks."""

import logging

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from tg_bot.config import get_config
from tg_bot.services import digest_formatter as fmt
from tg_bot.handlers import error_handler, admin_only
from tg_bot.handlers.admin import reload, config_cmd, logs, system
from tg_bot.handlers.sentiment import digest

logger = logging.getLogger(__name__)


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

        message = f"""
\U0001f4b0 *TREASURY BALANCE*

*Wallet:* `{short_addr}`
*SOL:* `{sol_balance:.4f}` SOL
*USD:* `${usd_value:,.2f}`

*Mode:* {mode}
*Max Positions:* {engine.max_positions}
*Risk Level:* {engine.risk_level.value}

\u26a0\ufe0f _Low balance warning: <{config.low_balance_threshold} SOL_
"""

        # Warning if low balance (configurable via LOW_BALANCE_THRESHOLD env var)
        if sol_balance < config.low_balance_threshold:
            message += "\n\U0001f6a8 *WARNING: Low balance!*"

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
        await update.message.reply_text(
            f"\u274c *Error*\n\nFailed to get balance: {str(e)[:100]}",
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
                "\U0001f4cb *OPEN POSITIONS*\n\n_No open positions._\n\nUse /report to find trading opportunities.",
                parse_mode=ParseMode.MARKDOWN,
            )
            return

        lines = ["\U0001f4cb *OPEN POSITIONS*", ""]

        keyboard_rows = []
        total_pnl = 0

        for pos in open_positions:
            pnl_pct = pos.unrealized_pnl_pct
            pnl_usd = pos.unrealized_pnl
            total_pnl += pnl_usd

            pnl_emoji = "\U0001f7e2" if pnl_pct >= 0 else "\U0001f534"

            lines.append(f"*{pos.token_symbol}* {pnl_emoji}")
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
        await update.message.reply_text(
            f"\u274c *Error*\n\nFailed to get positions: {str(e)[:100]}",
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

        lines = ["<b>\U0001f4bc Treasury Wallet</b>", ""]

        if address:
            lines.append(f"<b>Address:</b> <code>{address[:8]}...{address[-6:]}</code>")
            lines.append(f"<b>Full:</b> <code>{address}</code>")
            lines.append("")
            lines.append(f"<a href='https://solscan.io/account/{address}'>View on Solscan</a>")
        else:
            lines.append("\u26a0\ufe0f Wallet not initialized")

        lines.append("")
        lines.append(f"<b>Status:</b> {status.get('status', 'unknown')}")

        await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.HTML, disable_web_page_preview=True)
    except Exception as e:
        await update.message.reply_text(f"Wallet error: {str(e)[:100]}", parse_mode=ParseMode.MARKDOWN)


@error_handler
@admin_only
async def dashboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /dashboard - Show real-time positions with P&L and treasury stats.
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

    if not positions:
        summary_lines = [
            "\U0001f4ca *TREASURY DASHBOARD*",
            "",
            f"*Win Rate:* {scorecard.win_rate:.1f}%",
            f"*Streak:* {scorecard.current_streak:+d}",
            f"*Total P&L:* {scorecard.total_pnl_sol:+.4f} SOL",
            "",
            "_No open positions._",
        ]
        await update.message.reply_text(
            "\n".join(summary_lines),
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    async with aiohttp.ClientSession() as session:
        prices = await asyncio.gather(*[
            fetch_price(session, pos.token_mint) for pos in positions
        ])

    total_unrealized = 0.0
    lines = [
        "\U0001f4ca *TREASURY DASHBOARD*",
        "",
        f"*Win Rate:* {scorecard.win_rate:.1f}%",
        f"*Streak:* {scorecard.current_streak:+d}",
        f"*Total P&L:* {scorecard.total_pnl_sol:+.4f} SOL",
        "",
    ]

    for pos, price in zip(positions, prices):
        if price > 0:
            pos.current_price = price
        pnl_usd = pos.unrealized_pnl
        pnl_pct = pos.unrealized_pnl_pct
        total_unrealized += pnl_usd

        pnl_emoji = "\U0001f7e2" if pnl_usd >= 0 else "\U0001f534"
        current_price = pos.current_price if pos.current_price > 0 else pos.entry_price

        lines.append(f"{pnl_emoji} *{pos.token_symbol}*")
        lines.append(f"   Entry: {fmt_price(pos.entry_price)}")
        lines.append(f"   Current: {fmt_price(current_price)}")
        lines.append(f"   P&L: {pnl_pct:+.1f}% (${pnl_usd:+.2f})")
        lines.append("")

    total_emoji = "\U0001f7e2" if total_unrealized >= 0 else "\U0001f534"
    lines.append("-" * 24)
    lines.append(f"*Unrealized:* {total_emoji} ${total_unrealized:+.2f}")

    await update.message.reply_text(
        "\n".join(lines),
        parse_mode=ParseMode.MARKDOWN,
        disable_web_page_preview=True,
    )


@error_handler
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle inline keyboard button presses."""
    from telegram.error import BadRequest, TimedOut, NetworkError, RetryAfter
    import asyncio

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

    # Log all callbacks for debugging
    logger.info(f"Callback received: '{data}' from user {user_id}")

    # CRITICAL: Always answer callback first to stop loading spinner
    try:
        await query.answer()
    except BadRequest as e:
        logger.warning(f"Could not answer callback (stale?): {e}")
        # Continue processing even if answer fails
    except Exception as e:
        logger.error(f"Error answering callback: {e}")

    # Check if query.message exists (can be None for inline mode)
    if not query.message:
        logger.warning(f"Callback has no message object: {data}")
        return

    config = get_config()

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
        await query.message.reply_text(
            message,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
        return

    if data == "menu_help":
        help_text = """
*Jarvis Bot Commands*

*Public:*
/trending - Top 5 trending tokens (free)
/status - Check API status
/costs - View daily costs

*Admin Only:*
/signals - \U0001f680 Master Signal Report
/analyze <token> - Full analysis
/digest - Generate digest
/brain - AI brain stats
"""
        keyboard = [[InlineKeyboardButton("\U0001f3e0 Back to Menu", callback_data="menu_back")]]
        await query.message.reply_text(
            help_text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
        return

    if data == "menu_back":
        # Re-send main menu
        is_admin = config.is_admin(user_id)
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
        await query.message.reply_text(
            "*Jarvis Trading Bot* \U0001f916\n\n_Select an option:_",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
        return

    # Admin-only menu callbacks - use CallbackUpdate wrapper
    if data == "menu_signals":
        if not config.is_admin(user_id):
            await query.message.reply_text(fmt.format_unauthorized(), parse_mode=ParseMode.MARKDOWN)
            return
        cb_update = CallbackUpdate(query)
        context.args = []
        await signals(cb_update, context)
        return

    if data == "menu_digest":
        if not config.is_admin(user_id):
            await query.message.reply_text(fmt.format_unauthorized(), parse_mode=ParseMode.MARKDOWN)
            return
        cb_update = CallbackUpdate(query)
        context.args = []
        await digest(cb_update, context)
        return

    if data == "menu_brain":
        if not config.is_admin(user_id):
            await query.message.reply_text(fmt.format_unauthorized(), parse_mode=ParseMode.MARKDOWN)
            return
        cb_update = CallbackUpdate(query)
        context.args = []
        await brain(cb_update, context)
        return

    if data == "menu_reload":
        if not config.is_admin(user_id):
            await query.message.reply_text(fmt.format_unauthorized(), parse_mode=ParseMode.MARKDOWN)
            return
        cb_update = CallbackUpdate(query)
        context.args = []
        await reload(cb_update, context)
        return

    if data == "menu_health":
        if not config.is_admin(user_id):
            await query.message.reply_text(fmt.format_unauthorized(), parse_mode=ParseMode.MARKDOWN)
            return
        cb_update = CallbackUpdate(query)
        context.args = []
        await health(cb_update, context)
        return

    if data == "menu_flags":
        if not config.is_admin(user_id):
            await query.message.reply_text(fmt.format_unauthorized(), parse_mode=ParseMode.MARKDOWN)
            return
        cb_update = CallbackUpdate(query)
        context.args = []
        await flags(cb_update, context)
        return

    if data == "menu_score":
        if not config.is_admin(user_id):
            await query.message.reply_text(fmt.format_unauthorized(), parse_mode=ParseMode.MARKDOWN)
            return
        cb_update = CallbackUpdate(query)
        context.args = []
        await score(cb_update, context)
        return

    if data == "menu_config":
        if not config.is_admin(user_id):
            await query.message.reply_text(fmt.format_unauthorized(), parse_mode=ParseMode.MARKDOWN)
            return
        cb_update = CallbackUpdate(query)
        context.args = []
        await config_cmd(cb_update, context)
        return

    if data == "menu_system":
        if not config.is_admin(user_id):
            await query.message.reply_text(fmt.format_unauthorized(), parse_mode=ParseMode.MARKDOWN)
            return
        cb_update = CallbackUpdate(query)
        context.args = []
        await system(cb_update, context)
        return

    if data == "menu_orders":
        if not config.is_admin(user_id):
            await query.message.reply_text(fmt.format_unauthorized(), parse_mode=ParseMode.MARKDOWN)
            return
        cb_update = CallbackUpdate(query)
        context.args = []
        await orders(cb_update, context)
        return

    if data == "menu_wallet":
        if not config.is_admin(user_id):
            await query.message.reply_text(fmt.format_unauthorized(), parse_mode=ParseMode.MARKDOWN)
            return
        cb_update = CallbackUpdate(query)
        context.args = []
        await wallet(cb_update, context)
        return

    if data == "menu_logs":
        if not config.is_admin(user_id):
            await query.message.reply_text(fmt.format_unauthorized(), parse_mode=ParseMode.MARKDOWN)
            return
        cb_update = CallbackUpdate(query)
        context.args = []
        await logs(cb_update, context)
        return

    if data == "menu_metrics":
        if not config.is_admin(user_id):
            await query.message.reply_text(fmt.format_unauthorized(), parse_mode=ParseMode.MARKDOWN)
            return
        cb_update = CallbackUpdate(query)
        context.args = []
        await metrics(cb_update, context)
        return

    if data == "menu_audit":
        if not config.is_admin(user_id):
            await query.message.reply_text(fmt.format_unauthorized(), parse_mode=ParseMode.MARKDOWN)
            return
        cb_update = CallbackUpdate(query)
        context.args = []
        await audit(cb_update, context)
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
        if not config.is_admin(user_id):
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
                "\u26d4 *Admin Only*\n\nYou are not authorized to trade.",
                parse_mode=ParseMode.MARKDOWN
            )
            logger.warning(f"Unauthorized trade attempt by user {user_id}")
            return

        await _execute_trade_with_tp_sl(query, data)
        return

    if data.startswith("sell_pos:"):
        if not _is_treasury_admin(config, user_id):
            await query.message.reply_text("\u26d4 *Admin Only*", parse_mode=ParseMode.MARKDOWN)
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
        if not config.is_admin(user_id):
            await query.message.reply_text(fmt.format_unauthorized(), parse_mode=ParseMode.MARKDOWN)
            return
        result_id = data.replace("dev_refine:", "")
        await _handle_dev_refine(query, result_id, context)
        return

    if data.startswith("dev_copy:"):
        if not config.is_admin(user_id):
            await query.message.reply_text(fmt.format_unauthorized(), parse_mode=ParseMode.MARKDOWN)
            return
        result_id = data.replace("dev_copy:", "")
        await _handle_dev_copy(query, result_id)
        return

    # Ape button callbacks from sentiment reports (format: ape:{alloc}:{profile}:{type}:{symbol}:{contract})
    if data.startswith("ape:"):
        logger.info(f"Ape callback received: {data} from user {user_id}")

        if not APE_BUTTONS_AVAILABLE:
            await _send_with_retry(
                query,
                "\u274c Ape trading module not available",
                parse_mode=ParseMode.MARKDOWN
            )
            logger.error("APE_BUTTONS_AVAILABLE is False")
            return

        if not _is_treasury_admin(config, user_id):
            await _send_with_retry(
                query,
                f"\u26d4 *Admin Only*\n\nUser ID {user_id} is not authorized.",
                parse_mode=ParseMode.MARKDOWN
            )
            logger.warning(f"Unauthorized ape trade attempt by user {user_id}")
            return

        try:
            await _execute_ape_trade(query, data)
        except Exception as e:
            logger.error(f"APE trade failed: {e}")
            await _send_with_retry(
                query,
                f"\u274c Trade failed: {str(e)[:120]}",
                parse_mode=ParseMode.MARKDOWN
            )
        return
