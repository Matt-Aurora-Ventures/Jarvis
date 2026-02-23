"""
Analytics Command Handlers for Telegram Bot.

Commands:
- /analytics - Full portfolio analytics report
- /stats - Quick performance stats
- /performers - Top/bottom performing positions
- /tokenperf - Performance breakdown by token
"""

import logging
from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from tg_bot.bot_core import get_config, is_admin
from core.trading.portfolio_analytics import get_portfolio_analytics

logger = logging.getLogger(__name__)


async def analytics_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Full portfolio analytics report.

    Usage: /analytics
    """
    if not update.message:
        return
    config = get_config()

    # Admin-only for now
    if not is_admin(update.effective_user.id, config.admin_ids):
        try:
            await update.message.reply_text("⛔ Admin only")
        except Exception:
            pass
        return

    try:
        analytics = get_portfolio_analytics()
        analytics.reload()  # Refresh data

        summary = analytics.get_summary_stats()

        # Format the report
        msg_lines = [
            "<b>📊 PORTFOLIO ANALYTICS</b>",
            "",
            "<b>💰 Portfolio Value</b>",
            f"Current: ${summary['portfolio_value']['current_usd']:.2f}",
            f"Invested: ${summary['portfolio_value']['invested_usd']:.2f}",
            f"Unrealized P&L: ${summary['portfolio_value']['unrealized_pnl_usd']:.2f} ({summary['portfolio_value']['unrealized_pnl_pct']:.2f}%)",
            "",
            "<b>📈 Performance</b>",
            f"Total Positions: {summary['performance']['total_positions']}",
            f"Open: {summary['performance']['open_positions']} | Closed: {summary['performance']['closed_positions']}",
            f"Win Rate: {summary['performance']['win_rate']:.1f}%",
            f"Profit Factor: {summary['performance']['profit_factor']:.2f}",
            "",
            f"Total P&L: ${summary['performance']['total_pnl_usd']:.2f}",
            f"  • Realized: ${summary['performance']['realized_pnl_usd']:.2f}",
            f"  • Unrealized: ${summary['performance']['unrealized_pnl_usd']:.2f}",
            "",
            "<b>🔥 Streaks</b>",
        ]

        # Current streak
        current_streak = summary['streaks']['current']
        if current_streak > 0:
            msg_lines.append(f"Current: {current_streak} wins 🟢")
        elif current_streak < 0:
            msg_lines.append(f"Current: {abs(current_streak)} losses 🔴")
        else:
            msg_lines.append("Current: None")

        msg_lines.extend([
            f"Best: {summary['streaks']['longest_winning']} wins",
            f"Worst: {summary['streaks']['longest_losing']} losses",
            "",
            "<b>🪙 Tokens</b>",
            f"Unique Tokens Traded: {summary['tokens']['total_unique_tokens']}",
        ])

        if summary['tokens']['top_performer']:
            msg_lines.append(
                f"Top Performer: {summary['tokens']['top_performer']} "
                f"(${summary['tokens']['top_performer_pnl_usd']:.2f})"
            )

        msg_lines.extend([
            "",
            f"<b>⏱️ Avg Hold Time:</b> {summary['avg_hold_time_hours']:.1f} hours",
        ])

        # Best/worst positions
        if summary['best_position']:
            best = summary['best_position']
            msg_lines.extend([
                "",
                "<b>🏆 Best Position</b>",
                f"{best.get('token_symbol', 'Unknown')}: {best.get('pnl_pct', 0):.2f}% "
                f"(${best.get('pnl_usd', 0):.2f})"
            ])

        if summary['worst_position']:
            worst = summary['worst_position']
            msg_lines.extend([
                "",
                "<b>💀 Worst Position</b>",
                f"{worst.get('token_symbol', 'Unknown')}: {worst.get('pnl_pct', 0):.2f}% "
                f"(${worst.get('pnl_usd', 0):.2f})"
            ])

        msg_lines.extend([
            "",
            "<i>Use /tokenperf for per-token breakdown</i>",
            "<i>Use /performers for top/bottom positions</i>"
        ])

        await update.message.reply_text(
            "\n".join(msg_lines),
            parse_mode=ParseMode.HTML
        )

    except Exception as e:
        logger.error(f"Analytics error: {e}", exc_info=True)
        await update.message.reply_text(f"❌ Error: {e}")


async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Quick performance stats.

    Usage: /stats
    """
    config = get_config()

    # Admin-only for now
    if not is_admin(update.effective_user.id, config.admin_ids):
        try:
            await update.message.reply_text("⛔ Admin only")
        except Exception:
            pass
        return

    try:
        analytics = get_portfolio_analytics()
        analytics.reload()

        metrics = analytics.get_performance_metrics()
        current_value, invested, unrealized = analytics.get_portfolio_value()

        msg_lines = [
            "<b>📊 Quick Stats</b>",
            "",
            f"💰 Portfolio: ${current_value:.2f}",
            f"📈 Unrealized P&L: ${unrealized:.2f}",
            "",
            f"🎯 Positions: {metrics.open_positions} open / {metrics.closed_positions} closed",
            f"✅ Win Rate: {metrics.win_rate:.1f}%",
            f"💵 Total P&L: ${metrics.total_pnl_usd:.2f}",
            f"🔄 Profit Factor: {metrics.profit_factor:.2f}",
            f"⏱️ Avg Hold: {metrics.avg_hold_time_hours:.1f}h",
        ]

        # Streak indicator
        if metrics.current_streak > 0:
            msg_lines.append(f"🔥 Streak: {metrics.current_streak} wins")
        elif metrics.current_streak < 0:
            msg_lines.append(f"❄️ Streak: {abs(metrics.current_streak)} losses")

        await update.message.reply_text(
            "\n".join(msg_lines),
            parse_mode=ParseMode.HTML
        )

    except Exception as e:
        logger.error(f"Stats error: {e}", exc_info=True)
        await update.message.reply_text(f"❌ Error: {e}")


async def performers_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Top and bottom performing positions.

    Usage: /performers [limit]
    """
    config = get_config()

    # Admin-only for now
    if not is_admin(update.effective_user.id, config.admin_ids):
        try:
            await update.message.reply_text("⛔ Admin only")
        except Exception:
            pass
        return

    try:
        # Parse limit argument
        limit = 5
        if context.args and context.args[0].isdigit():
            limit = int(context.args[0])
            limit = min(limit, 10)  # Cap at 10

        analytics = get_portfolio_analytics()
        analytics.reload()

        best, worst = analytics.get_top_performers(limit=limit, metric="pnl_pct")

        msg_lines = [
            f"<b>🏆 Top {limit} Performers</b>",
            ""
        ]

        for i, pos in enumerate(best, 1):
            symbol = pos.get("token_symbol", "Unknown")
            pnl_pct = pos.get("pnl_pct", 0)
            pnl_usd = pos.get("pnl_usd", 0)
            status = pos.get("status", "UNKNOWN")
            status_emoji = "🟢" if status == "OPEN" else "⚪"

            msg_lines.append(
                f"{i}. {status_emoji} {symbol}: <b>{pnl_pct:+.2f}%</b> (${pnl_usd:+.2f})"
            )

        msg_lines.extend([
            "",
            f"<b>💀 Bottom {limit} Performers</b>",
            ""
        ])

        for i, pos in enumerate(worst, 1):
            symbol = pos.get("token_symbol", "Unknown")
            pnl_pct = pos.get("pnl_pct", 0)
            pnl_usd = pos.get("pnl_usd", 0)
            status = pos.get("status", "UNKNOWN")
            status_emoji = "🟢" if status == "OPEN" else "⚪"

            msg_lines.append(
                f"{i}. {status_emoji} {symbol}: <b>{pnl_pct:+.2f}%</b> (${pnl_usd:+.2f})"
            )

        msg_lines.append("\n<i>🟢 Open | ⚪ Closed</i>")

        await update.message.reply_text(
            "\n".join(msg_lines),
            parse_mode=ParseMode.HTML
        )

    except Exception as e:
        logger.error(f"Performers error: {e}", exc_info=True)
        await update.message.reply_text(f"❌ Error: {e}")


async def tokenperf_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Performance breakdown by token.

    Usage: /tokenperf
    """
    config = get_config()

    # Admin-only for now
    if not is_admin(update.effective_user.id, config.admin_ids):
        try:
            await update.message.reply_text("⛔ Admin only")
        except Exception:
            pass
        return

    try:
        analytics = get_portfolio_analytics()
        analytics.reload()

        token_performance = analytics.get_token_performance()

        if not token_performance:
            await update.message.reply_text("No token data available.")
            return

        msg_lines = [
            "<b>🪙 Performance by Token</b>",
            ""
        ]

        for tp in token_performance[:10]:  # Limit to top 10 tokens
            msg_lines.extend([
                f"<b>{tp.token_symbol}</b>",
                f"  Positions: {tp.total_positions} ({tp.open_positions} open)",
                f"  Win Rate: {tp.win_rate:.1f}% ({tp.wins}W / {tp.losses}L)",
                f"  Total P&L: ${tp.total_pnl_usd:+.2f}",
                f"  Avg P&L: {tp.avg_pnl_pct:+.2f}%",
                f"  Best/Worst: {tp.best_pnl_pct:+.2f}% / {tp.worst_pnl_pct:+.2f}%",
                f"  Avg Hold: {tp.avg_hold_time_hours:.1f}h",
                ""
            ])

            # Show unrealized if open positions exist
            if tp.open_positions > 0:
                msg_lines.append(
                    f"  Unrealized: ${tp.unrealized_pnl_usd:+.2f} "
                    f"({tp.current_value_usd:.2f}/{tp.total_invested_usd:.2f})"
                )
                msg_lines.append("")

        if len(token_performance) > 10:
            msg_lines.append(f"<i>...and {len(token_performance) - 10} more tokens</i>")

        await update.message.reply_text(
            "\n".join(msg_lines),
            parse_mode=ParseMode.HTML
        )

    except Exception as e:
        logger.error(f"Token performance error: {e}", exc_info=True)
        await update.message.reply_text(f"❌ Error: {e}")
