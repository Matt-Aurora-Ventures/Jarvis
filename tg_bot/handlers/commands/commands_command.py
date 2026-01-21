"""
/commands handler - Show all available bot commands (admin only).

This provides matthaynes88 with a complete list of all available commands
organized by category for easy reference.
"""

import html
import logging
from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from tg_bot.handlers import error_handler, admin_only

logger = logging.getLogger(__name__)

# All commands organized by category
COMMAND_CATEGORIES = {
    "General": [
        ("/start", "Start the bot"),
        ("/help", "Show help message"),
        ("/status", "Check bot status"),
        ("/subscribe", "Subscribe to updates"),
        ("/unsubscribe", "Unsubscribe from updates"),
        ("/commands", "Show this command list"),
    ],
    "Market Data": [
        ("/price <token>", "Get current price"),
        ("/chart <token>", "View price chart"),
        ("/mcap <token>", "Market cap info"),
        ("/volume <token>", "Trading volume"),
        ("/liquidity <token>", "Liquidity info"),
        ("/age <token>", "Token age/creation date"),
        ("/summary <token>", "Full token summary"),
        ("/solprice", "Current SOL price"),
        ("/trending", "Trending tokens"),
        ("/gainers", "Top gainers"),
        ("/losers", "Top losers"),
        ("/newpairs", "New token pairs"),
    ],
    "Analysis": [
        ("/analyze <token>", "AI analysis (Grok)"),
        ("/a <token>", "Quick analyze alias"),
        ("/sentiment", "Market sentiment"),
        ("/score <token>", "Token score"),
        ("/signals", "Trading signals"),
        ("/picks", "AI top picks"),
        ("/compare", "Compare tokens"),
    ],
    "Portfolio & Trading": [
        ("/balance", "View wallet balance"),
        ("/b", "Balance alias"),
        ("/positions", "Open positions"),
        ("/portfolio", "Full portfolio view"),
        ("/p", "Portfolio alias"),
        ("/pnl", "Profit/Loss summary"),
        ("/dashboard", "Trading dashboard"),
        ("/dash", "Dashboard alias"),
        ("/treasury", "Treasury overview"),
        ("/sector", "Sector breakdown"),
        ("/orders", "Pending orders"),
        ("/calibrate", "Calibrate risk settings"),
        ("/cal", "Calibrate alias"),
    ],
    "Watchlist": [
        ("/watchlist", "View watchlist"),
        ("/w", "Watchlist alias"),
        ("/watch <token>", "Add to watchlist"),
        ("/unwatch <token>", "Remove from watchlist"),
    ],
    "Quick Actions": [
        ("/quick", "Quick action menu"),
        ("/q", "Quick alias"),
        ("/search <query>", "Search tokens"),
        ("/searchp <query>", "Search with prices"),
    ],
    "Analytics": [
        ("/analytics", "Portfolio analytics"),
        ("/perfstats", "Performance statistics"),
        ("/performers", "Top performers"),
        ("/tokenperf <token>", "Token performance"),
    ],
    "Export": [
        ("/export", "Export data menu"),
        ("/exportpos", "Export positions"),
        ("/exporttrades", "Export trade history"),
    ],
    "Paper Trading": [
        ("/paper", "Paper trading mode"),
        ("/sim", "Simulation status"),
        ("/simbuy <token> <amount>", "Simulated buy"),
        ("/simsell <token> <amount>", "Simulated sell"),
        ("/simpos", "Simulated positions"),
    ],
    "Admin": [
        ("/costs", "API cost tracking"),
        ("/keystatus", "API key status"),
        ("/health", "System health"),
        ("/flags", "Feature flags"),
        ("/config", "View config"),
        ("/reload", "Reload config"),
        ("/system", "System status"),
        ("/logs", "Recent logs"),
        ("/metrics", "System metrics"),
        ("/memory", "Memory usage"),
        ("/sysmem", "System memory"),
        ("/uptime", "Bot uptime"),
        ("/audit", "Audit log"),
        ("/ratelimits", "Rate limit status"),
    ],
    "X Bot Control": [
        ("/xbot", "X bot status/control"),
        ("/brain", "AI brain status"),
        ("/code", "Execute code"),
        ("/remember", "Store memory"),
        ("/clistats", "CLI statistics"),
        ("/stats", "Stats alias"),
        ("/s", "Stats alias"),
        ("/queue", "Command queue"),
    ],
    "Moderation": [
        ("/away", "Set away status"),
        ("/back", "Return from away"),
        ("/awaystatus", "Check away status"),
        ("/addscam <address>", "Mark scam token"),
        ("/trust <address>", "Mark trusted"),
        ("/trustscore <address>", "Check trust score"),
        ("/warn <user>", "Warn user"),
        ("/flag", "Report spam"),
        ("/togglemedia", "Toggle media mode"),
        ("/unban <user>", "Unban user"),
        ("/modstats", "Moderation stats"),
    ],
    "Reports": [
        ("/digest", "Daily digest"),
        ("/report", "Generate report"),
        ("/stocks", "Stock market update"),
        ("/st", "Stocks alias"),
        ("/equities", "Equities alias"),
    ],
    "Development": [
        ("/dev", "Developer tools"),
        ("/upgrades", "Available upgrades"),
    ],
    "AI Trading Demo": [
        ("/demo", "Launch AI Trading Interface"),
        ("", "├── AI Market Regime Detection"),
        ("", "├── Sentiment-Aware Trading"),
        ("", "├── AI Token Analysis"),
        ("", "├── Conviction Picks"),
        ("", "└── Self-Improving Engine"),
    ],
}


@error_handler
@admin_only
async def commands_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /commands - show all available commands (admin only)."""
    lines = ["<b>JARVIS Command Reference</b>", ""]

    for category, commands in COMMAND_CATEGORIES.items():
        lines.append(f"<b>{category}</b>")
        for cmd, desc in commands:
            lines.append(
                f"  <code>{html.escape(cmd)}</code> - {html.escape(desc)}"
            )
        lines.append("")

    # Add footer
    lines.append("<i>All commands restricted to admin users.</i>")
    lines.append("<i>Use /help for quick reference.</i>")

    # Split into chunks if too long (Telegram 4096 char limit)
    message = "\n".join(lines)

    if len(message) <= 4000:
        await update.message.reply_text(message, parse_mode=ParseMode.HTML)
    else:
        # Split by category
        current_chunk = ["<b>JARVIS Command Reference</b>", ""]

        for category, commands in COMMAND_CATEGORIES.items():
            category_lines = [f"<b>{category}</b>"]
            for cmd, desc in commands:
                category_lines.append(
                    f"  <code>{html.escape(cmd)}</code> - {html.escape(desc)}"
                )
            category_lines.append("")

            chunk_text = "\n".join(current_chunk + category_lines)

            if len(chunk_text) > 3800:
                # Send current chunk
                await update.message.reply_text(
                    "\n".join(current_chunk),
                    parse_mode=ParseMode.HTML
                )
                current_chunk = category_lines
            else:
                current_chunk.extend(category_lines)

        # Send remaining
        if current_chunk:
            current_chunk.append("<i>All commands restricted to admin users.</i>")
            await update.message.reply_text(
                "\n".join(current_chunk),
                parse_mode=ParseMode.HTML
            )

    logger.info(f"Commands list shown to user {update.effective_user.id}")


# Export for bot.py
__all__ = ["commands_command"]
