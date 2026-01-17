"""
System monitoring and status handlers for Jarvis Telegram Bot.

Extracted from bot_core.py as part of refactoring.
Handles: health, uptime, metrics, costs, keystatus, clistats, cliqueue, flags
"""

import logging

from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from tg_bot.handlers import admin_only
from tg_bot.services import digest_formatter as fmt

logger = logging.getLogger(__name__)


# =============================================================================
# Public Commands
# =============================================================================

async def costs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /costs command - show API costs."""
    message = fmt.format_cost_report()

    await update.message.reply_text(
        message,
        parse_mode=ParseMode.MARKDOWN,
    )


# =============================================================================
# Admin-Only System Commands
# =============================================================================

@admin_only
async def health(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /health command - show system health (admin only)."""
    try:
        from core.health_monitor import get_health_monitor
        monitor = get_health_monitor()

        # Run all checks
        await monitor.run_all_checks()
        report = monitor.get_health_report()

        status_emoji = {"healthy": "✅", "degraded": "⚠️", "unhealthy": "❌", "unknown": "❓"}

        lines = [
            f"<b>System Health: {status_emoji.get(report['status'], '❓')} {report['status'].upper()}</b>",
            "",
        ]

        for name, check in report["checks"].items():
            emoji = status_emoji.get(check["status"], "❓")
            lines.append(f"{emoji} <b>{name}</b>: {check['message']} ({check['latency_ms']:.0f}ms)")

        await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.HTML)
    except Exception as e:
        await update.message.reply_text(f"Health check error: {str(e)[:100]}", parse_mode=ParseMode.MARKDOWN)


@admin_only
async def uptime(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /uptime command - show bot uptime (admin only)."""
    try:
        import os
        import psutil
        from datetime import datetime

        # Get process start time
        process = psutil.Process(os.getpid())
        start_time = datetime.fromtimestamp(process.create_time())
        uptime_delta = datetime.now() - start_time

        # Format uptime
        days = uptime_delta.days
        hours, remainder = divmod(uptime_delta.seconds, 3600)
        minutes, seconds = divmod(remainder, 60)

        uptime_str = ""
        if days > 0:
            uptime_str += f"{days}d "
        uptime_str += f"{hours}h {minutes}m {seconds}s"

        lines = [
            "<b>⏱️ Bot Uptime</b>",
            "",
            f"<b>Uptime:</b> {uptime_str}",
            f"<b>Started:</b> {start_time.strftime('%Y-%m-%d %H:%M:%S')}",
            f"<b>PID:</b> {os.getpid()}",
        ]

        await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.HTML)
    except ImportError:
        await update.message.reply_text("psutil not installed", parse_mode=ParseMode.HTML)
    except Exception as e:
        await update.message.reply_text(f"Uptime error: {str(e)[:100]}", parse_mode=ParseMode.MARKDOWN)


@admin_only
async def metrics(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /metrics command - show system metrics (admin only)."""
    try:
        import psutil
        import os

        # Get system metrics
        cpu = psutil.cpu_percent(interval=0.5)
        mem = psutil.virtual_memory()
        disk = psutil.disk_usage('/')

        lines = [
            "<b>📊 System Metrics</b>",
            "",
            f"💻 <b>CPU:</b> {cpu:.1f}%",
            f"🧠 <b>Memory:</b> {mem.percent:.1f}% ({mem.used / 1024 / 1024 / 1024:.1f}GB / {mem.total / 1024 / 1024 / 1024:.1f}GB)",
            f"💾 <b>Disk:</b> {disk.percent:.1f}% ({disk.used / 1024 / 1024 / 1024:.1f}GB / {disk.total / 1024 / 1024 / 1024:.1f}GB)",
            "",
            f"🐍 <b>Python PID:</b> {os.getpid()}",
        ]

        await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.HTML)
    except ImportError:
        await update.message.reply_text("psutil not installed", parse_mode=ParseMode.HTML)
    except Exception as e:
        await update.message.reply_text(f"Metrics error: {str(e)[:100]}", parse_mode=ParseMode.MARKDOWN)


@admin_only
async def keystatus(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /keystatus command - show key manager status (admin only)."""
    try:
        from core.security.key_manager import get_key_manager
        km = get_key_manager()
        status = km.verify_key_access()

        # Format status
        pw_status = "SET" if status["password_available"] else "NOT SET"
        treasury_status = "ACCESSIBLE" if status["treasury_accessible"] else "NOT ACCESSIBLE"

        lines = [
            "*Key Manager Status*",
            "",
            f"*Password:* `{pw_status}`",
            f"*Treasury:* `{treasury_status}`",
        ]

        if status.get("treasury_address"):
            addr = status["treasury_address"]
            lines.append(f"*Address:* `{addr[:8]}...{addr[-6:]}`")

        lines.append("")
        lines.append("*Key Locations:*")

        for name, info in status["locations"].items():
            exists = "YES" if info["exists"] else "NO"
            lines.append(f"  {name}: {exists}")

        await update.message.reply_text(
            "\n".join(lines),
            parse_mode=ParseMode.MARKDOWN,
        )
    except Exception as e:
        await update.message.reply_text(
            f"*Key Manager Error*\n\n`{str(e)[:100]}`",
            parse_mode=ParseMode.MARKDOWN,
        )


@admin_only
async def clistats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /clistats command - show CLI execution metrics (admin only)."""
    try:
        from tg_bot.services.claude_cli_handler import ClaudeCLIHandler

        handler = ClaudeCLIHandler()
        metrics = handler.get_metrics()

        lines = [
            "<b>🤖 CLI Execution Stats</b>",
            "",
            f"📊 <b>Total Executions:</b> {metrics.get('total', 0)}",
            f"✅ <b>Successful:</b> {metrics.get('successful', 0)}",
            f"❌ <b>Failed:</b> {metrics.get('failed', 0)}",
            f"📈 <b>Success Rate:</b> {metrics.get('success_rate', 'N/A')}",
            f"⏱️ <b>Avg Duration:</b> {metrics.get('avg_duration', 'N/A')}",
            f"🕐 <b>Last Execution:</b> {metrics.get('last_execution', 'Never')}",
            "",
            "<i>Note: Stats reset when bot restarts</i>"
        ]

        await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.HTML)
    except Exception as e:
        await update.message.reply_text(f"CLI stats error: {str(e)[:100]}", parse_mode=ParseMode.HTML)


@admin_only
async def cliqueue(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /queue command - show CLI queue status (admin only)."""
    try:
        from tg_bot.services.claude_cli_handler import ClaudeCLIHandler

        handler = ClaudeCLIHandler()
        status = handler.get_queue_status()

        lines = [
            "<b>📋 CLI Queue Status</b>",
            "",
            f"📊 <b>Queue Depth:</b> {status.get('depth', 0)}/{status.get('max_depth', 3)}",
            f"🔒 <b>Locked:</b> {'Yes' if status.get('is_locked') else 'No'}",
        ]

        pending = status.get('pending', [])
        if pending:
            lines.append("")
            lines.append("<b>Pending Commands:</b>")
            for i, cmd in enumerate(pending, 1):
                preview = cmd.get('prompt_preview', 'Unknown')
                queued = cmd.get('queued_at', 'Unknown')[:19]
                lines.append(f"{i}. <code>{preview}</code>")
                lines.append(f"   Queued: {queued}")
        else:
            lines.append("")
            lines.append("<i>No pending commands</i>")

        await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.HTML)
    except Exception as e:
        await update.message.reply_text(f"Queue status error: {str(e)[:100]}", parse_mode=ParseMode.HTML)


@admin_only
async def flags(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /flags command - show feature flags (admin only).

    Usage:
    - /flags - Show all flags
    - /flags enable <name> - Enable a flag
    - /flags disable <name> - Disable a flag
    """
    try:
        from core.feature_flags import get_feature_flags
        ff = get_feature_flags()

        # Check for enable/disable subcommands
        if context.args:
            action = context.args[0].lower()
            if action in ("enable", "disable") and len(context.args) > 1:
                flag_name = context.args[1]
                if flag_name not in ff.flags:
                    await update.message.reply_text(f"Unknown flag: {flag_name}", parse_mode=ParseMode.HTML)
                    return

                if action == "enable":
                    ff.enable(flag_name)
                    await update.message.reply_text(f"✅ Enabled: <code>{flag_name}</code>", parse_mode=ParseMode.HTML)
                else:
                    ff.disable(flag_name)
                    await update.message.reply_text(f"❌ Disabled: <code>{flag_name}</code>", parse_mode=ParseMode.HTML)
                return

        all_flags = ff.get_all_flags()

        lines = ["<b>Feature Flags</b>", "", "<i>Use: /flags enable|disable &lt;name&gt;</i>", ""]

        for name, flag in sorted(all_flags.items()):
            state = flag["state"]
            emoji = "✅" if state == "on" else "❌" if state == "off" else "⚡"
            lines.append(f"{emoji} <code>{name}</code>: {state}")

        await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.HTML)
    except Exception as e:
        await update.message.reply_text(f"Feature flags error: {str(e)[:100]}", parse_mode=ParseMode.MARKDOWN)


# =============================================================================
# Handler Registration
# =============================================================================

def get_handlers():
    """Return list of handlers for registration."""
    from telegram.ext import CommandHandler

    return [
        CommandHandler("costs", costs),
        CommandHandler("health", health),
        CommandHandler("uptime", uptime),
        CommandHandler("metrics", metrics),
        CommandHandler("keystatus", keystatus),
        CommandHandler("clistats", clistats),
        CommandHandler("cliqueue", cliqueue),
        CommandHandler("flags", flags),
    ]


__all__ = [
    "costs",
    "health",
    "uptime",
    "metrics",
    "keystatus",
    "clistats",
    "cliqueue",
    "flags",
    "get_handlers",
]
