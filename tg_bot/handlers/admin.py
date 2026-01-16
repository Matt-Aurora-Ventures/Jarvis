"""Admin-only handlers."""

import logging
from pathlib import Path

from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from tg_bot.config import reload_config
from tg_bot.handlers import error_handler, admin_only

logger = logging.getLogger(__name__)


@error_handler
@admin_only
async def reload(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /reload command - reload config (admin only)."""
    reload_config()
    await update.message.reply_text(
        "Configuration reloaded from environment.",
        parse_mode=ParseMode.MARKDOWN,
    )


@error_handler
@admin_only
async def logs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /logs command - show recent log entries (admin only)."""
    try:
        log_file = Path("logs/jarvis.log")

        if not log_file.exists():
            await update.message.reply_text("No log file found.", parse_mode=ParseMode.HTML)
            return

        # Read last 20 lines
        lines = log_file.read_text().strip().split("\n")[-20:]

        output = ["<b>\U0001f4cb Recent Logs</b>", ""]
        for line in lines:
            # Truncate long lines
            if len(line) > 80:
                line = line[:77] + "..."
            output.append(f"<code>{line}</code>")

        await update.message.reply_text("\n".join(output), parse_mode=ParseMode.HTML)
    except Exception as e:
        logger.error(f"Logs error: {e}")
        await update.message.reply_text(f"Logs error: {str(e)[:100]}", parse_mode=ParseMode.MARKDOWN)


@error_handler
@admin_only
async def system(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /system command - comprehensive system status (admin only)."""
    try:
        lines = ["<b>\U0001f916 JARVIS System Status</b>", ""]

        # Health status
        try:
            from core.health_monitor import get_health_monitor
            monitor = get_health_monitor()
            await monitor.run_all_checks()
            health = monitor.get_overall_status()
            emoji = {"healthy": "\u2705", "degraded": "\u26a0\ufe0f", "unhealthy": "\u274c"}.get(
                health.value, "\u2753"
            )
            lines.append(f"{emoji} <b>Health:</b> {health.value.upper()}")
        except Exception:
            lines.append("\u2753 <b>Health:</b> Unknown")

        # Feature flags
        try:
            from core.feature_flags import get_feature_flags
            ff = get_feature_flags()
            enabled = len(ff.get_enabled_flags())
            total = len(ff.flags)
            lines.append(f"\U0001f39a\ufe0f <b>Features:</b> {enabled}/{total} enabled")
        except Exception:
            pass

        # Scorekeeper
        try:
            from bots.treasury.scorekeeper import get_scorekeeper
            sk = get_scorekeeper()
            summary = sk.get_summary()
            lines.append(f"\U0001f4ca <b>Win Rate:</b> {summary['win_rate']}")
            lines.append(f"\U0001f4b0 <b>Total P&L:</b> {summary['total_pnl_sol']} SOL")
            lines.append(f"\U0001f4c8 <b>Open Positions:</b> {summary['open_positions']}")
        except Exception:
            pass

        # Bot uptime info
        import datetime
        lines.append("")
        lines.append(f"\U0001f550 <b>Time:</b> {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

        await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.HTML)
    except Exception as e:
        logger.error(f"System error: {e}")
        await update.message.reply_text(f"System error: {str(e)[:100]}", parse_mode=ParseMode.MARKDOWN)


@error_handler
@admin_only
async def config_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /config command - show/set configuration (admin only)."""
    try:
        from core.config_hot_reload import get_config_manager
        cfg = get_config_manager()

        # Check for set subcommand
        if context.args and len(context.args) >= 3:
            if context.args[0].lower() == "set":
                key = context.args[1]
                value = " ".join(context.args[2:])

                # Parse value type
                if value.lower() == "true":
                    value = True
                elif value.lower() == "false":
                    value = False
                else:
                    try:
                        value = float(value) if "." in value else int(value)
                    except ValueError:
                        pass

                if cfg.set(key, value):
                    await update.message.reply_text(
                        f"\u2705 Set <code>{key}</code> = {value}",
                        parse_mode=ParseMode.HTML,
                    )
                else:
                    await update.message.reply_text(
                        f"\u274c Failed to set {key}",
                        parse_mode=ParseMode.HTML,
                    )
                return

        # Show key config values
        trading = cfg.get_by_prefix("trading")
        bot_cfg = cfg.get_by_prefix("bot")

        lines = [
            "<b>Current Configuration</b>",
            "",
            "<i>Use: /config set &lt;key&gt; &lt;value&gt;</i>",
            "",
            "<b>Trading:</b>",
        ]
        for k, v in sorted(trading.items()):
            lines.append(f"  <code>{k}</code>: {v}")

        lines.append("")
        lines.append("<b>Bot:</b>")
        for k, v in sorted(bot_cfg.items()):
            lines.append(f"  <code>{k}</code>: {v}")

        await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.HTML)
    except Exception as e:
        logger.error(f"Config error: {e}")
        await update.message.reply_text(f"Config error: {str(e)[:100]}", parse_mode=ParseMode.MARKDOWN)
