"""
Treasury Paper Trading Simulator Commands.
Uses real market prices with simulated SOL funds.
"""

import logging
from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from tg_bot.handlers import admin_only, error_handler

logger = logging.getLogger(__name__)

# Paper trading engine singleton
_PAPER_SIM_ENGINE = None


async def _get_paper_sim_engine():
    """Get or create the treasury paper trading engine."""
    global _PAPER_SIM_ENGINE
    if _PAPER_SIM_ENGINE is None:
        from bots.treasury.paper_trading import PaperTradingEngine
        _PAPER_SIM_ENGINE = PaperTradingEngine(initial_sol=100.0)
    return _PAPER_SIM_ENGINE


@error_handler
@admin_only
async def sim(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Treasury paper trading simulator (SOL-based).
    Uses real market prices with simulated funds.

    /sim - Show status
    /sim buy <mint> <usd> [grade] - Buy with real prices
    /sim sell <position_id> - Sell position
    /sim pos - Show positions
    /sim report - Performance report
    /sim history - Trade history
    /sim check - Check TP/SL triggers
    /sim reset [sol] - Reset with new balance
    """
    try:
        engine = await _get_paper_sim_engine()
        args = context.args or []
        subcommand = args[0].lower() if args else "status"

        if subcommand in ("status", "wallet"):
            sol_balance, usd_value = await engine.get_portfolio_value()
            open_positions = engine.get_open_positions()
            unrealized_pnl = sum(p.unrealized_pnl for p in open_positions)
            pnl_emoji = "" if unrealized_pnl >= 0 else ""

            lines = [
                "*PAPER TRADING SIMULATOR*",
                "_Real prices, simulated funds_",
                "",
                f"*Portfolio:* ${usd_value:,.2f} ({sol_balance:.4f} SOL)",
                f"*Positions:* {len(open_positions)}",
                f"*Unrealized:* {pnl_emoji} ${unrealized_pnl:+.2f}",
                "",
                f"*Daily:* ${engine._daily_volume:.2f} / ${engine.MAX_DAILY_USD}",
                f"*Trades:* {engine.metrics.total_trades}",
                f"*Win Rate:* {engine.metrics.win_rate:.1f}%",
            ]

            await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN)

        elif subcommand == "buy":
            if len(args) < 3:
                await update.message.reply_text(
                    "*sim buy*\n\n`/sim buy <mint> <usd> [grade]`\n\n"
                    "example: `/sim buy DezXAZ8z... 50 B`\n\n"
                    "grades: A+, A, A-, B+, B, B-, C+, C, C-, D, F",
                    parse_mode=ParseMode.MARKDOWN,
                )
                return

            mint = args[1]
            try:
                amount = float(args[2])
            except (ValueError, TypeError):
                await update.message.reply_text(
                    "*error*\n\ninvalid amount — use a number like `50` or `25.5`",
                    parse_mode=ParseMode.MARKDOWN,
                )
                return
            grade = args[3].upper() if len(args) > 3 else "B"

            await update.message.reply_text(" executing paper buy...")
            success, msg, _ = await engine.execute_buy(
                token_mint=mint,
                amount_usd=amount,
                sentiment_grade=grade
            )
            emoji = "" if success else ""
            await update.message.reply_text(f"*{emoji} {msg}*", parse_mode=ParseMode.MARKDOWN)

        elif subcommand == "sell":
            if len(args) < 2:
                await update.message.reply_text(
                    "`/sim sell <position_id>`\n\nuse `/sim pos` for IDs",
                    parse_mode=ParseMode.MARKDOWN
                )
                return

            success, msg = await engine.execute_sell(args[1], reason="manual")
            emoji = "" if success else ""
            await update.message.reply_text(f"*{emoji} {msg}*", parse_mode=ParseMode.MARKDOWN)

        elif subcommand in ("positions", "pos"):
            await engine.update_positions()
            positions = engine.get_open_positions()

            if not positions:
                await update.message.reply_text(
                    "*positions*\n\n_none open_",
                    parse_mode=ParseMode.MARKDOWN
                )
                return

            lines = ["*paper positions*", ""]
            total_pnl = 0

            for p in positions:
                pnl_pct, pnl_usd = p.unrealized_pnl_pct, p.unrealized_pnl
                total_pnl += pnl_usd
                emoji = "" if pnl_pct >= 0 else ""
                lines.append(f"*{p.token_symbol}* {emoji} `{pnl_pct:+.1f}%` (${pnl_usd:+.2f})")
                lines.append(f"  entry: `${p.entry_price:.8f}`")
                lines.append(f"  now: `${p.current_price:.8f}`")
                lines.append(f"   TP: `${p.take_profit_price:.8f}`")
                lines.append(f"   SL: `${p.stop_loss_price:.8f}`")
                lines.append(f"  ID: `{p.id}`")
                lines.append("")

            emoji = "" if total_pnl >= 0 else ""
            lines.append(f"*total:* {emoji} `${total_pnl:+.2f}`")
            await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN)

        elif subcommand == "report":
            await engine._update_metrics()
            m = engine.metrics
            ret = ((m.current_balance_usd - m.start_balance_usd) / m.start_balance_usd * 100) if m.start_balance_usd > 0 else 0
            emoji = "" if m.total_pnl_usd >= 0 else ""

            lines = [
                "*PAPER REPORT*", "",
                f"balance: `${m.current_balance_usd:,.2f}` (start: ${m.start_balance_usd:,.2f})",
                f"return: `{ret:+.2f}%`", "",
                f"trades: {m.total_trades} | win rate: `{m.win_rate:.1f}%`",
                f"wins: {m.winning_trades} | losses: {m.losing_trades}",
                "",
                f"{emoji} P&L: `${m.total_pnl_usd:+,.2f}`",
                f"best: `${m.best_trade_pnl:+.2f}` | worst: `${m.worst_trade_pnl:+.2f}`",
                f"avg win: `${m.avg_win_usd:+.2f}` | avg loss: `${m.avg_loss_usd:.2f}`",
                f"fees: `${m.total_fees_paid:.2f}`",
                "",
                f"drawdown: `{m.max_drawdown_pct:.1f}%` | profit factor: `{m.profit_factor:.2f}`",
            ]
            await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN)

        elif subcommand == "history":
            history = engine.trade_history[-10:]
            if not history:
                await update.message.reply_text(
                    "*history*\n\n_no closed trades_",
                    parse_mode=ParseMode.MARKDOWN
                )
                return

            lines = [f"*history* ({len(engine.trade_history)} total)", ""]
            for t in reversed(history):
                emoji = "" if t.pnl_usd >= 0 else ""
                lines.append(f"{emoji} *{t.token_symbol}*: `${t.pnl_usd:+.2f}` ({t.pnl_pct:+.1f}%)")
                lines.append(f"   entry: ${t.entry_price:.8f} -> exit: ${t.exit_price:.8f}")
                lines.append("")

            await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN)

        elif subcommand == "check":
            triggered = await engine.check_tp_sl()
            if triggered:
                lines = ["* TP/SL triggered*", ""]
                for _, action, msg in triggered:
                    lines.append(f"*{action}:* {msg}")
                await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN)
            else:
                await update.message.reply_text(
                    "*check*\n\n_no triggers - all positions within limits_",
                    parse_mode=ParseMode.MARKDOWN
                )

        elif subcommand == "reset":
            try:
                initial_sol = float(args[1]) if len(args) > 1 else 100.0
            except (ValueError, TypeError):
                initial_sol = 100.0
            engine.reset(initial_sol=initial_sol)
            await update.message.reply_text(
                f"* reset*\n\nstarting: `{initial_sol}` SOL\nall positions cleared",
                parse_mode=ParseMode.MARKDOWN
            )

        else:
            await update.message.reply_text(
                "*paper trading sim*\n\n"
                "`/sim` - status\n"
                "`/sim buy <mint> <usd> [grade]` - buy\n"
                "`/sim sell <id>` - sell\n"
                "`/sim pos` - positions\n"
                "`/sim report` - stats\n"
                "`/sim history` - trades\n"
                "`/sim check` - TP/SL\n"
                "`/sim reset [sol]` - reset\n\n"
                "_uses real market prices_",
                parse_mode=ParseMode.MARKDOWN,
            )

    except ValueError as e:
        await update.message.reply_text(f"Error: {str(e)}")
    except Exception as e:
        logger.error(f"Paper sim error: {e}")
        await update.message.reply_text(f"Error: {str(e)[:100]}")


# Shorthand commands
@error_handler
@admin_only
async def sim_buy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Quick buy: /simbuy <mint> <usd> [grade]"""
    context.args = ["buy"] + (context.args or [])
    await sim(update, context)


@error_handler
@admin_only
async def sim_sell(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Quick sell: /simsell <position_id>"""
    context.args = ["sell"] + (context.args or [])
    await sim(update, context)


@error_handler
@admin_only
async def sim_pos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Quick positions: /simpos"""
    context.args = ["pos"]
    await sim(update, context)
