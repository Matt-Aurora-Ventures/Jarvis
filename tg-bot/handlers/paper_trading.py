"""
Telegram handlers for paper trading simulator.
Mirrors the live trading interface but operates on simulated funds.
"""

import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from tg_bot.config import get_config
from tg_bot.handlers import error_handler, admin_only

logger = logging.getLogger(__name__)

# Singleton paper trading engine
_paper_engine = None


async def _get_paper_engine():
    """Get or create the paper trading engine singleton."""
    global _paper_engine
    if _paper_engine is None:
        from bots.treasury.paper_trading import PaperTradingEngine
        _paper_engine = PaperTradingEngine(initial_sol=100.0)
    return _paper_engine


@error_handler
@admin_only
async def paper_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /paper - Show paper trading status and menu.
    """
    engine = await _get_paper_engine()
    sol_balance, usd_value = await engine.get_portfolio_value()
    open_positions = engine.get_open_positions()

    # Calculate unrealized P&L
    unrealized_pnl = sum(p.unrealized_pnl for p in open_positions)
    pnl_emoji = "" if unrealized_pnl >= 0 else ""

    message = f"""*PAPER TRADING*

*portfolio*
sol: `{sol_balance:.4f}` | usd: `${usd_value:,.2f}`
positions: {len(open_positions)}
{pnl_emoji} unrealized: `${unrealized_pnl:+.2f}`

*daily limits*
volume: `${engine._daily_volume:.2f}` / `${engine.MAX_DAILY_USD}`
max trade: `${engine.MAX_TRADE_USD}`

*session stats*
total trades: {engine.metrics.total_trades}
win rate: {engine.metrics.win_rate:.1f}%
total P&L: `${engine.metrics.total_pnl_usd:+.2f}`
"""

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(" Buy", callback_data="paper_buy_menu"),
            InlineKeyboardButton(" Positions", callback_data="paper_positions"),
        ],
        [
            InlineKeyboardButton(" Report", callback_data="paper_report"),
            InlineKeyboardButton(" History", callback_data="paper_history"),
        ],
        [
            InlineKeyboardButton(" Check TP/SL", callback_data="paper_check_tpsl"),
            InlineKeyboardButton(" Reset", callback_data="paper_reset_confirm"),
        ],
    ])

    await update.message.reply_text(
        message,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=keyboard,
    )


@error_handler
@admin_only
async def paper_buy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /paper_buy <token_mint> <amount_usd> [grade] - Execute paper buy.

    Example: /paper_buy So111...112 50 A
    """
    args = context.args or []

    if len(args) < 2:
        await update.message.reply_text(
            "*paper buy*\n\n"
            "usage: `/paper_buy <token_mint> <amount_usd> [grade]`\n\n"
            "example: `/paper_buy DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263 50 B`\n\n"
            "grades: A+, A, A-, B+, B, B-, C+, C, C-, D, F\n"
            "(grade affects TP/SL levels)",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    token_mint = args[0]
    try:
        amount_usd = float(args[1])
    except ValueError:
        await update.message.reply_text(
            "*error*\n\ninvalid amount. use a number like `50` or `25.5`",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    grade = args[2].upper() if len(args) > 2 else "B"

    # Validate grade
    valid_grades = ['A+', 'A', 'A-', 'B+', 'B', 'B-', 'C+', 'C', 'C-', 'D', 'F']
    if grade not in valid_grades:
        grade = "B"

    await update.message.reply_text(
        f"*executing paper buy...*\n\ntoken: `{token_mint[:12]}...`\namount: `${amount_usd}`\ngrade: `{grade}`",
        parse_mode=ParseMode.MARKDOWN,
    )

    engine = await _get_paper_engine()
    success, msg, position = await engine.execute_buy(
        token_mint=token_mint,
        amount_usd=amount_usd,
        sentiment_grade=grade,
    )

    if success:
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(" View Positions", callback_data="paper_positions")],
        ])
        await update.message.reply_text(
            f"* paper trade executed*\n\n{msg}",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=keyboard,
        )
    else:
        await update.message.reply_text(
            f"* paper buy failed*\n\n{msg}",
            parse_mode=ParseMode.MARKDOWN,
        )


@error_handler
@admin_only
async def paper_sell(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /paper_sell <position_id> - Execute paper sell.
    """
    args = context.args or []

    if not args:
        await update.message.reply_text(
            "*paper sell*\n\n"
            "usage: `/paper_sell <position_id>`\n\n"
            "use `/paper_positions` to see position IDs",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    position_id = args[0]

    await update.message.reply_text(
        f"*executing paper sell...*\n\nposition: `{position_id}`",
        parse_mode=ParseMode.MARKDOWN,
    )

    engine = await _get_paper_engine()
    success, msg = await engine.execute_sell(position_id, reason="manual")

    if success:
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(" View Report", callback_data="paper_report")],
        ])
        await update.message.reply_text(
            f"* paper sell executed*\n\n{msg}",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=keyboard,
        )
    else:
        await update.message.reply_text(
            f"* paper sell failed*\n\n{msg}",
            parse_mode=ParseMode.MARKDOWN,
        )


@error_handler
@admin_only
async def paper_positions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /paper_positions - Show paper trading positions.
    """
    engine = await _get_paper_engine()
    await engine.update_positions()
    open_positions = engine.get_open_positions()

    if not open_positions:
        await update.message.reply_text(
            "*paper positions*\n\n_no open positions_\n\nuse `/paper_buy` to open a position",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    lines = ["*paper positions*", ""]
    keyboard_rows = []
    total_pnl = 0

    for pos in open_positions:
        pnl_pct = pos.unrealized_pnl_pct
        pnl_usd = pos.unrealized_pnl
        total_pnl += pnl_usd

        pnl_emoji = "" if pnl_pct >= 0 else ""

        lines.append(f"*{pos.token_symbol}* {pnl_emoji}")
        lines.append(f"   entry: `${pos.entry_price:.8f}`")
        lines.append(f"   current: `${pos.current_price:.8f}`")
        lines.append(f"   P&L: `{pnl_pct:+.1f}%` (`${pnl_usd:+.2f}`)")
        lines.append(f"    TP: `${pos.take_profit_price:.8f}`")
        lines.append(f"    SL: `${pos.stop_loss_price:.8f}`")
        lines.append(f"   ID: `{pos.id}`")
        lines.append("")

        # Add sell button
        keyboard_rows.append([
            InlineKeyboardButton(
                f" SELL {pos.token_symbol}",
                callback_data=f"paper_sell:{pos.id}"
            )
        ])

    # Summary
    total_emoji = "" if total_pnl >= 0 else ""
    lines.append("")
    lines.append(f"*total P&L:* {total_emoji} `${total_pnl:+.2f}`")

    keyboard_rows.append([
        InlineKeyboardButton(" Refresh", callback_data="paper_positions"),
        InlineKeyboardButton(" Check TP/SL", callback_data="paper_check_tpsl"),
    ])

    await update.message.reply_text(
        "\n".join(lines),
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup(keyboard_rows),
    )


@error_handler
@admin_only
async def paper_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /paper_report - Show paper trading performance report.
    """
    engine = await _get_paper_engine()
    await engine._update_metrics()

    m = engine.metrics
    pnl_emoji = "" if m.total_pnl_usd >= 0 else ""

    total_return = 0.0
    if m.start_balance_usd > 0:
        total_return = ((m.current_balance_usd - m.start_balance_usd) / m.start_balance_usd) * 100

    message = f"""*PAPER TRADING REPORT*

*account*
starting: `${m.start_balance_usd:,.2f}`
current: `${m.current_balance_usd:,.2f}`
peak: `${m.peak_balance_usd:,.2f}`
return: `{total_return:+.2f}%`

*trading stats*
total trades: {m.total_trades}
win rate: `{m.win_rate:.1f}%`
winning: {m.winning_trades} | losing: {m.losing_trades}

*P&L*
{pnl_emoji} total: `${m.total_pnl_usd:+,.2f}`
best: `${m.best_trade_pnl:+,.2f}`
worst: `${m.worst_trade_pnl:+,.2f}`
avg win: `${m.avg_win_usd:+,.2f}`
avg loss: `${m.avg_loss_usd:,.2f}`
fees: `${m.total_fees_paid:.2f}`

*risk metrics*
max drawdown: `{m.max_drawdown_pct:.1f}%`
profit factor: `{m.profit_factor:.2f}`

_session started: {m.started_at[:19]}_
"""

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(" Refresh", callback_data="paper_report"),
            InlineKeyboardButton(" History", callback_data="paper_history"),
        ],
    ])

    await update.message.reply_text(
        message,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=keyboard,
    )


@error_handler
@admin_only
async def paper_history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /paper_history - Show recent paper trade history.
    """
    engine = await _get_paper_engine()
    history = engine.trade_history[-10:]  # Last 10

    if not history:
        await update.message.reply_text(
            "*paper history*\n\n_no closed trades yet_",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    lines = [f"*paper history* ({len(engine.trade_history)} total)", ""]

    for t in reversed(history):  # Most recent first
        emoji = "" if t.pnl_usd >= 0 else ""
        lines.append(f"{emoji} *{t.token_symbol}*: `${t.pnl_usd:+.2f}` (`{t.pnl_pct:+.1f}%`)")
        lines.append(f"   entry: `${t.entry_price:.8f}` exit: `${t.exit_price:.8f}`")
        lines.append(f"   _{t.closed_at[:16]}_")
        lines.append("")

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(" Report", callback_data="paper_report")],
    ])

    await update.message.reply_text(
        "\n".join(lines),
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=keyboard,
    )


@error_handler
@admin_only
async def paper_reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /paper_reset [initial_sol] - Reset paper trading state.
    """
    args = context.args or []
    initial_sol = float(args[0]) if args else 100.0

    engine = await _get_paper_engine()
    engine.reset(initial_sol=initial_sol)

    await update.message.reply_text(
        f"* paper trading reset*\n\nstarting balance: `{initial_sol}` SOL\n\nall positions and history cleared.",
        parse_mode=ParseMode.MARKDOWN,
    )


async def paper_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle paper trading callbacks."""
    query = update.callback_query
    await query.answer()

    data = query.data

    try:
        engine = await _get_paper_engine()

        if data == "paper_positions":
            await engine.update_positions()
            open_positions = engine.get_open_positions()

            if not open_positions:
                await query.edit_message_text(
                    "*paper positions*\n\n_no open positions_",
                    parse_mode=ParseMode.MARKDOWN,
                )
                return

            lines = ["*paper positions*", ""]
            keyboard_rows = []
            total_pnl = 0

            for pos in open_positions:
                pnl_pct = pos.unrealized_pnl_pct
                pnl_usd = pos.unrealized_pnl
                total_pnl += pnl_usd

                pnl_emoji = "" if pnl_pct >= 0 else ""

                lines.append(f"*{pos.token_symbol}* {pnl_emoji}")
                lines.append(f"   entry: `${pos.entry_price:.8f}`")
                lines.append(f"   current: `${pos.current_price:.8f}`")
                lines.append(f"   P&L: `{pnl_pct:+.1f}%` (`${pnl_usd:+.2f}`)")
                lines.append(f"   ID: `{pos.id}`")
                lines.append("")

                keyboard_rows.append([
                    InlineKeyboardButton(
                        f" SELL {pos.token_symbol}",
                        callback_data=f"paper_sell:{pos.id}"
                    )
                ])

            total_emoji = "" if total_pnl >= 0 else ""
            lines.append(f"*total:* {total_emoji} `${total_pnl:+.2f}`")

            keyboard_rows.append([
                InlineKeyboardButton(" Refresh", callback_data="paper_positions"),
            ])

            await query.edit_message_text(
                "\n".join(lines),
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=InlineKeyboardMarkup(keyboard_rows),
            )

        elif data.startswith("paper_sell:"):
            position_id = data.split(":")[1]
            success, msg = await engine.execute_sell(position_id, reason="manual")

            if success:
                await query.edit_message_text(
                    f"* paper sell executed*\n\n{msg}",
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton(" Positions", callback_data="paper_positions")],
                    ]),
                )
            else:
                await query.edit_message_text(
                    f"* sell failed*\n\n{msg}",
                    parse_mode=ParseMode.MARKDOWN,
                )

        elif data == "paper_report":
            await engine._update_metrics()
            m = engine.metrics
            pnl_emoji = "" if m.total_pnl_usd >= 0 else ""

            total_return = 0.0
            if m.start_balance_usd > 0:
                total_return = ((m.current_balance_usd - m.start_balance_usd) / m.start_balance_usd) * 100

            message = f"""*PAPER TRADING REPORT*

*account*
starting: `${m.start_balance_usd:,.2f}`
current: `${m.current_balance_usd:,.2f}`
return: `{total_return:+.2f}%`

*trading*
trades: {m.total_trades} | win rate: `{m.win_rate:.1f}%`
{pnl_emoji} total P&L: `${m.total_pnl_usd:+,.2f}`

*risk*
drawdown: `{m.max_drawdown_pct:.1f}%` | PF: `{m.profit_factor:.2f}`
"""

            await query.edit_message_text(
                message,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton(" Refresh", callback_data="paper_report")],
                ]),
            )

        elif data == "paper_history":
            history = engine.trade_history[-5:]
            if not history:
                await query.edit_message_text(
                    "*paper history*\n\n_no trades yet_",
                    parse_mode=ParseMode.MARKDOWN,
                )
                return

            lines = ["*paper history*", ""]
            for t in reversed(history):
                emoji = "" if t.pnl_usd >= 0 else ""
                lines.append(f"{emoji} *{t.token_symbol}*: `${t.pnl_usd:+.2f}` (`{t.pnl_pct:+.1f}%`)")
                lines.append("")

            await query.edit_message_text(
                "\n".join(lines),
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton(" Report", callback_data="paper_report")],
                ]),
            )

        elif data == "paper_check_tpsl":
            triggered = await engine.check_tp_sl()
            if triggered:
                lines = ["* TP/SL triggered*", ""]
                for pos_id, action, msg in triggered:
                    lines.append(f"*{action}*: {msg}")
                    lines.append("")
                await query.edit_message_text(
                    "\n".join(lines),
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton(" Positions", callback_data="paper_positions")],
                    ]),
                )
            else:
                await query.edit_message_text(
                    "*TP/SL check*\n\n_no triggers_",
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton(" Back", callback_data="paper_positions")],
                    ]),
                )

        elif data == "paper_reset_confirm":
            await query.edit_message_text(
                "* reset paper trading?*\n\nthis will clear all positions and history.",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=InlineKeyboardMarkup([
                    [
                        InlineKeyboardButton(" Yes, Reset", callback_data="paper_reset_yes"),
                        InlineKeyboardButton(" Cancel", callback_data="paper_positions"),
                    ],
                ]),
            )

        elif data == "paper_reset_yes":
            engine.reset()
            await query.edit_message_text(
                "* paper trading reset*\n\nstarting balance: `100` SOL",
                parse_mode=ParseMode.MARKDOWN,
            )

        elif data == "paper_buy_menu":
            await query.edit_message_text(
                "*paper buy*\n\n"
                "use command:\n"
                "`/paper_buy <token_mint> <amount_usd> [grade]`\n\n"
                "example:\n"
                "`/paper_buy DezXAZ8z... 50 B`\n\n"
                "popular tokens:\n"
                " BONK: `DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263`\n"
                " WIF: `EKpQGSJtjMFqKZ9KQanSqYXRcF8fBopzLHYxdM65zcjm`\n"
                " JUP: `JUPyiwrYJFskUPiHa7hkeR8VUtAeFoSYbKedZNsDvCN`",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton(" Back", callback_data="paper_positions")],
                ]),
            )

    except Exception as e:
        logger.error(f"Paper callback error: {e}")
        await query.edit_message_text(
            f"*error*\n\n{str(e)[:100]}",
            parse_mode=ParseMode.MARKDOWN,
        )


# Command to bot mapping
PAPER_COMMANDS = {
    'paper': paper_status,
    'paper_buy': paper_buy,
    'paper_sell': paper_sell,
    'paper_positions': paper_positions,
    'paper_report': paper_report,
    'paper_history': paper_history,
    'paper_reset': paper_reset,
}
