"""
Demo Bot - Learning & Performance Callback Handler

Handles: learning, learning_deep, performance, trade_history, history_page, pnl_chart, leaderboard, goals
"""

import logging
from typing import Any, Dict, Tuple

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)


async def handle_learning(
    ctx,
    action: str,
    data: str,
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    state: Dict[str, Any],
) -> Tuple[str, InlineKeyboardMarkup]:
    """
    Handle learning and performance callbacks.

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

    if action == "learning":
        intelligence = ctx.get_trade_intelligence()
        if intelligence:
            learning_stats = intelligence.get_learning_summary()
            compression_stats = intelligence.get_compression_stats()
        else:
            learning_stats = {
                "total_trades_analyzed": 0,
                "pattern_memories": 0,
                "stable_strategies": 0,
                "signals": {},
                "regimes": {},
                "optimal_hold_time": 60,
            }
            compression_stats = {"compression_ratio": 1.0, "learned_patterns": 0}

        return DemoMenuBuilder.learning_dashboard(
            learning_stats=learning_stats,
            compression_stats=compression_stats,
        )

    elif action == "learning_deep":
        intelligence = ctx.get_trade_intelligence()

        if intelligence:
            stats = intelligence.get_learning_summary()
            comp = intelligence.get_compression_stats()

            lines = [
                f"{theme.AUTO} *DEEP LEARNING ANALYSIS*",
                "=" * 20,
                "",
                "*Memory Architecture:*",
                "| Tier 0: Ephemeral (real-time)",
                "| Tier 1: Short-term (hours-days)",
                "| Tier 2: Medium-term (weeks)",
                "| Tier 3: Long-term (months+)",
                "",
                f"*Compression Efficiency:*",
                f"| Tier 1 Trades: {comp.get('tier1_trades', 0)}",
                f"| Tier 2 Patterns: {comp.get('tier2_patterns', 0)}",
                f"| Compression Ratio: {comp.get('compression_ratio', 1):.1f}x",
                f"| Raw -> Latent: ~{comp.get('compression_ratio', 1) * 100:.0f}% savings",
                "",
                "*Core Principle:*",
                "_Compression is Intelligence_",
                "_The better we predict, the better we compress_",
                "_The better we compress, the better we understand_",
            ]
            text = "\n".join(lines)
        else:
            text = f"{theme.AUTO} *Learning engine initializing...*"

        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(f"{theme.BACK} Back", callback_data="demo:learning")],
        ])
        return text, keyboard

    elif action == "performance":
        intelligence = ctx.get_trade_intelligence()

        if intelligence:
            summary = intelligence.get_learning_summary()
            performance_stats = {
                "total_trades": summary.get("total_trades_analyzed", 0),
                "wins": summary.get("wins", 0),
                "losses": summary.get("losses", 0),
                "win_rate": summary.get("win_rate", 0),
                "total_pnl": summary.get("total_pnl", 0),
                "total_pnl_pct": summary.get("total_pnl_pct", 0),
                "best_trade": summary.get("best_trade", {}),
                "worst_trade": summary.get("worst_trade", {}),
                "current_streak": summary.get("current_streak", 0),
                "avg_hold_time_minutes": summary.get("optimal_hold_time", 60),
                "daily_pnl": summary.get("daily_pnl", 0),
                "weekly_pnl": summary.get("weekly_pnl", 0),
                "monthly_pnl": summary.get("monthly_pnl", 0),
                "avg_trades_per_day": summary.get("avg_trades_per_day", 0),
            }
        else:
            # Real data only: don't fabricate performance numbers.
            performance_stats = {
                "total_trades": 0,
                "wins": 0,
                "losses": 0,
                "win_rate": 0.0,
                "total_pnl": 0.0,
                "total_pnl_pct": 0.0,
                "best_trade": {},
                "worst_trade": {},
                "current_streak": 0,
                "avg_hold_time_minutes": 0,
                "daily_pnl": 0.0,
                "weekly_pnl": 0.0,
                "monthly_pnl": 0.0,
                "avg_trades_per_day": 0.0,
            }

        return DemoMenuBuilder.performance_dashboard(performance_stats)

    elif action == "trade_history":
        intelligence = ctx.get_trade_intelligence()

        if intelligence:
            summary = intelligence.get_learning_summary()
            trades = summary.get("recent_trades", [])
        else:
            trades = []

        return DemoMenuBuilder.trade_history_view(trades)

    elif data.startswith("demo:history_page:"):
        parts = data.split(":")
        try:
            page = int(parts[2]) if len(parts) >= 3 else 0
        except (ValueError, TypeError):
            page = 0

        intelligence = ctx.get_trade_intelligence()
        if intelligence:
            summary = intelligence.get_learning_summary()
            trades = summary.get("recent_trades", [])
        else:
            trades = []

        return DemoMenuBuilder.trade_history_view(trades, page=page)

    elif action == "pnl_chart":
        text = """
{chart} *PnL CHART*
{'=' * 20}

_Generating performance chart..._

Visual PnL tracking with:
- Daily equity curve
- Win/loss distribution
- Drawdown analysis

Coming in V2!
"""
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(f"{theme.BACK} Back", callback_data="demo:performance")],
        ])
        return text, keyboard

    elif action == "leaderboard":
        text = """
{trophy} *LEADERBOARD*
{'=' * 20}

Compare your performance with
other JARVIS traders!

_Feature coming in V2_

For now, focus on beating
your own records!
"""
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(f"{theme.BACK} Back", callback_data="demo:performance")],
        ])
        return text, keyboard

    elif action == "goals":
        text = """
{target} *TRADING GOALS*
{'=' * 20}

Set and track your targets:

{chart} *Daily Goal:* $50
{chart} *Weekly Goal:* $250
{trophy} *Monthly Goal:* $1,000

_Goal customization coming in V2!_
"""
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(f"{theme.BACK} Back", callback_data="demo:performance")],
        ])
        return text, keyboard

    # Default
    return DemoMenuBuilder.learning_dashboard(
        learning_stats={},
        compression_stats={},
    )
