"""Admin-only handlers."""

import logging
import time
from pathlib import Path

from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from tg_bot.config import reload_config
from tg_bot.handlers import error_handler, admin_only
from tg_bot.handlers.ui_nav import ensure_prev_menu

logger = logging.getLogger(__name__)


@error_handler
@admin_only
async def reload(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /reload command - reload config (admin only)."""
    reload_config()
    await update.message.reply_text(
        "config reloaded. fresh settings loaded.",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=ensure_prev_menu(None),
    )


@error_handler
@admin_only
async def logs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /logs command - show recent log entries (admin only)."""
    try:
        log_file = Path("logs/jarvis.log")

        if not log_file.exists():
            await update.message.reply_text(
                "no log file. nothing to show.",
                parse_mode=ParseMode.HTML,
                reply_markup=ensure_prev_menu(None),
            )
            return

        # Read last 20 lines
        lines = log_file.read_text().strip().split("\n")[-20:]

        output = ["<b>recent logs</b>", ""]
        for line in lines:
            # Truncate long lines
            if len(line) > 80:
                line = line[:77] + "..."
            output.append(f"<code>{line}</code>")

        await update.message.reply_text(
            "\n".join(output),
            parse_mode=ParseMode.HTML,
            reply_markup=ensure_prev_menu(None),
        )
    except Exception as e:
        logger.error(f"Logs error: {e}")
        await update.message.reply_text(
            f"Logs error: {str(e)[:100]}",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=ensure_prev_menu(None),
        )


@error_handler
@admin_only
async def errors(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /errors command - show deduplicated error summary (admin only)."""
    try:
        from core.logging.error_tracker import error_tracker

        frequent = error_tracker.get_frequent_errors(min_count=1)
        critical = error_tracker.get_critical_errors()

        lines = ["<b>error summary</b>", ""]

        if critical:
            lines.append("<b>critical</b>")
            for e in critical[:5]:
                lines.append(f"- <code>{e['id']}</code> {e['component']} {e['type']} x{e['count']}")
            lines.append("")

        if frequent:
            lines.append("<b>recent</b>")
            for e in frequent[:10]:
                lines.append(f"- <code>{e['id']}</code> {e['component']} {e['type']} x{e['count']}")
        else:
            lines.append("no errors recorded.")

        await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.HTML)
    except Exception as e:
        logger.error(f"Errors command failed: {e}")
        await update.message.reply_text(f"Errors error: {str(e)[:100]}", parse_mode=ParseMode.MARKDOWN)

@error_handler
@admin_only
async def system(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /system command - comprehensive system status (admin only)."""
    try:
        # JARVIS voice
        lines = ["<b>system status</b>", ""]

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

        # Feature flags (try new system first, fall back to legacy)
        try:
            from core.config.feature_flags import get_feature_flag_manager
            manager = get_feature_flag_manager()
            enabled = len(manager.get_enabled_flags())
            total = len(manager.get_all_flags())
            lines.append(f"\U0001f39a\ufe0f <b>Features:</b> {enabled}/{total} enabled (config)")
        except Exception:
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

        await update.message.reply_text(
            "\n".join(lines),
            parse_mode=ParseMode.HTML,
            reply_markup=ensure_prev_menu(None),
        )
    except Exception as e:
        logger.error(f"System error: {e}")
        await update.message.reply_text(
            f"System error: {str(e)[:100]}",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=ensure_prev_menu(None),
        )


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
                        reply_markup=ensure_prev_menu(None),
                    )
                else:
                    await update.message.reply_text(
                        f"\u274c Failed to set {key}",
                        parse_mode=ParseMode.HTML,
                        reply_markup=ensure_prev_menu(None),
                    )
                return

        # Show key config values - JARVIS voice
        trading = cfg.get_by_prefix("trading")
        bot_cfg = cfg.get_by_prefix("bot")

        lines = [
            "<b>config</b>",
            "",
            "<i>/config set &lt;key&gt; &lt;value&gt; to change</i>",
            "",
            "<b>trading:</b>",
        ]
        for k, v in sorted(trading.items()):
            lines.append(f"  <code>{k}</code>: {v}")

        lines.append("")
        lines.append("<b>bot:</b>")
        for k, v in sorted(bot_cfg.items()):
            lines.append(f"  <code>{k}</code>: {v}")

        await update.message.reply_text(
            "\n".join(lines),
            parse_mode=ParseMode.HTML,
            reply_markup=ensure_prev_menu(None),
        )
    except Exception as e:
        logger.error(f"Config error: {e}")
        await update.message.reply_text(
            f"Config error: {str(e)[:100]}",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=ensure_prev_menu(None),
        )


@error_handler
@admin_only
async def away(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle /away command - enable auto-responder (admin only).

    Usage:
        /away - Enable with default message
        /away 2h - Enable for 2 hours
        /away 30m Going for lunch - Enable for 30 min with custom message
        /away Custom message only - Enable with just message (no duration)
    """
    try:
        from tg_bot.services.auto_responder import get_auto_responder, parse_duration

        responder = get_auto_responder()

        # Parse arguments
        duration = None
        message = None

        if context.args:
            # Check if first arg is a duration
            first_arg = context.args[0]
            parsed = parse_duration(first_arg)
            if parsed:
                duration = parsed
                # Rest is the message
                if len(context.args) > 1:
                    message = " ".join(context.args[1:])
            else:
                # Entire args is the message
                message = " ".join(context.args)

        result = responder.enable(message=message, duration_minutes=duration)
        await update.message.reply_text(f"\U0001f4a4 {result}", parse_mode=ParseMode.HTML)

    except Exception as e:
        logger.error(f"Away command error: {e}")
        await update.message.reply_text(f"Error: {str(e)[:100]}", parse_mode=ParseMode.MARKDOWN)


@error_handler
@admin_only
async def back(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /back command - disable auto-responder (admin only)."""
    try:
        from tg_bot.services.auto_responder import get_auto_responder

        responder = get_auto_responder()
        result = responder.disable()
        await update.message.reply_text(f"\U0001f44b {result}", parse_mode=ParseMode.HTML)

    except Exception as e:
        logger.error(f"Back command error: {e}")
        await update.message.reply_text(f"Error: {str(e)[:100]}", parse_mode=ParseMode.MARKDOWN)


@error_handler
@admin_only
async def awaystatus(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /awaystatus command - check auto-responder status (admin only)."""
    try:
        from tg_bot.services.auto_responder import get_auto_responder

        responder = get_auto_responder()
        status = responder.get_status()

        # JARVIS voice
        if status["enabled"]:
            lines = [
                "<b>away mode: on</b>",
                "",
                f"message: {status.get('message', 'N/A')}",
            ]
            if status.get("return_time"):
                lines.append(f"back at: {status['return_time']}")
            if status.get("remaining"):
                lines.append(f"time left: {status['remaining']}")
            if status.get("enabled_at"):
                lines.append(f"started: {status['enabled_at']}")
        else:
            lines = ["<b>away mode: off</b>", "", "i'm around."]

        await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.HTML)

    except Exception as e:
        logger.error(f"Awaystatus error: {e}")
        await update.message.reply_text(f"Error: {str(e)[:100]}", parse_mode=ParseMode.MARKDOWN)


@error_handler
@admin_only
async def memory(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle /memory command - show what JARVIS remembers (admin only).

    Usage:
        /memory - Show what I know about you
        /memory @username - Show what I know about another user
    """
    try:
        from tg_bot.services.conversation_memory import get_conversation_memory

        chat_id = update.effective_chat.id
        user_id = update.effective_user.id

        # Check if looking up another user
        if context.args and context.args[0].startswith("@"):
            # Would need to lookup user by username - for now just show self
            pass

        pmem = get_conversation_memory()
        if not pmem:
            await update.message.reply_text(
                "memory system offline.",
                parse_mode=ParseMode.MARKDOWN,
            )
            return

        # Get user facts
        facts = pmem.get_user_facts(user_id, chat_id)

        # Get user context
        user_ctx = pmem.get_user_context(user_id, chat_id)

        # Get conversation summary
        summary = pmem.get_conversation_summary(chat_id)

        # Get recent topics
        topics = pmem.get_chat_topics(chat_id)

        # JARVIS voice - lowercase, no corporate filler
        lines = ["<b>what i remember</b>", ""]

        if user_ctx:
            lines.append(f"<b>about you:</b> {user_ctx}")
            lines.append("")

        if facts:
            lines.append("<b>facts:</b>")
            for f in facts[:8]:
                fact_type = f.get("fact_type", "unknown")
                content = f.get("fact_content", "")[:60]
                lines.append(f"  • {fact_type}: {content}")
            lines.append("")

        if topics:
            lines.append(f"<b>recent topics:</b> {', '.join(topics[-5:])}")
            lines.append("")

        if summary:
            lines.append(f"<b>chat stats:</b> {summary}")

        if len(lines) <= 2:
            lines.append("nothing yet. talk to me more.")

        await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.HTML)

    except Exception as e:
        logger.error(f"Memory error: {e}")
        await update.message.reply_text(f"memory error: {str(e)[:100]}", parse_mode=ParseMode.MARKDOWN)


@error_handler
@admin_only
async def sysmem(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle /sysmem command - show system memory profiling (admin only).

    Usage:
        /sysmem - Show current memory status
        /sysmem start - Start background monitoring
        /sysmem stop - Stop background monitoring
        /sysmem snapshot - Take manual snapshot
        /sysmem trend - Show memory trend
        /sysmem alerts - Show recent alerts
        /sysmem clear - Clear alerts
    """
    try:
        from core.performance.memory_monitor import memory_monitor
        import datetime

        # Parse subcommand
        subcommand = context.args[0].lower() if context.args else "status"

        if subcommand == "start":
            if not memory_monitor._tracking:
                memory_monitor.start_tracking()
            memory_monitor.start_background_monitoring()
            await update.message.reply_text(
                "memory monitoring started.",
                parse_mode=ParseMode.HTML,
            )
            return

        elif subcommand == "stop":
            memory_monitor.stop_background_monitoring()
            await update.message.reply_text(
                "memory monitoring stopped.",
                parse_mode=ParseMode.HTML,
            )
            return

        elif subcommand == "snapshot":
            snapshot = memory_monitor.take_snapshot()
            lines = [
                "<b>memory snapshot</b>",
                "",
                f"rss: {snapshot.rss_mb:.1f}mb",
                f"heap: {snapshot.heap_mb:.1f}mb",
                f"gc: {snapshot.gc_counts}",
                f"time: {datetime.datetime.fromtimestamp(snapshot.timestamp).strftime('%H:%M:%S')}"
            ]
            await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.HTML)
            return

        elif subcommand == "trend":
            trend = memory_monitor.get_memory_trend()
            emoji = {"increasing": "📈", "decreasing": "📉", "stable": "➡️"}.get(trend["trend"], "❓")
            lines = [
                "<b>memory trend (60min)</b>",
                "",
                f"{emoji} trend: {trend['trend']}",
                f"samples: {trend.get('samples', 0)}",
            ]
            if trend.get("growth_mb") is not None:
                lines.append(f"growth: {trend['growth_mb']:.1f}mb")
                lines.append(f"rate: {trend['growth_rate_mb_per_min']:.2f}mb/min")
            await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.HTML)
            return

        elif subcommand == "alerts":
            alerts = memory_monitor.get_alerts(since=time.time() - 3600)
            if not alerts:
                await update.message.reply_text(
                    "no alerts in last hour.",
                    parse_mode=ParseMode.HTML,
                )
                return

            lines = ["<b>memory alerts (1h)</b>", ""]
            for alert in alerts[-10:]:
                emoji = "⚠️" if alert.severity == "warning" else "🚨"
                timestamp = datetime.datetime.fromtimestamp(alert.timestamp).strftime('%H:%M:%S')
                lines.append(f"{emoji} [{timestamp}] {alert.message}")

            await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.HTML)
            return

        elif subcommand == "clear":
            memory_monitor.clear_alerts()
            await update.message.reply_text(
                "alerts cleared.",
                parse_mode=ParseMode.HTML,
            )
            return

        # Default: show status
        if not memory_monitor.snapshots:
            await update.message.reply_text(
                "no memory data. use /sysmem start to begin monitoring.",
                parse_mode=ParseMode.HTML,
            )
            return

        latest = memory_monitor.snapshots[-1]
        trend = memory_monitor.get_memory_trend()
        recent_alerts = memory_monitor.get_alerts(since=time.time() - 3600)

        lines = [
            "<b>system memory</b>",
            "",
            f"rss: {latest.rss_mb:.1f}mb",
            f"heap: {latest.heap_mb:.1f}mb",
            f"gc: {latest.gc_counts}",
        ]

        if memory_monitor.baseline:
            growth = latest.rss_mb - memory_monitor.baseline.rss_mb
            lines.append(f"growth: {growth:+.1f}mb")

        if trend["trend"] != "unknown":
            emoji = {"increasing": "📈", "decreasing": "📉", "stable": "➡️"}.get(trend["trend"], "❓")
            lines.append(f"{emoji} trend: {trend['trend']}")

        if recent_alerts:
            critical = len([a for a in recent_alerts if a.severity == "critical"])
            warning = len([a for a in recent_alerts if a.severity == "warning"])
            if critical > 0:
                lines.append(f"🚨 alerts: {critical} critical, {warning} warning")
            elif warning > 0:
                lines.append(f"⚠️ alerts: {warning} warning")

        lines.append("")
        lines.append("<i>/sysmem start|stop|snapshot|trend|alerts</i>")

        await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.HTML)

    except Exception as e:
        logger.error(f"Sysmem error: {e}")
        await update.message.reply_text(f"sysmem error: {str(e)[:100]}", parse_mode=ParseMode.MARKDOWN)


@error_handler
@admin_only
async def flags(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle /flags command - view/update feature flags (admin only).

    Usage:
        /flags - Show all feature flags
        /flags FLAG_NAME - Show specific flag details
        /flags FLAG_NAME on - Enable flag
        /flags FLAG_NAME off - Disable flag
        /flags FLAG_NAME 50 - Set 50% rollout
        /flags reload - Reload from config file
    """
    try:
        from core.config.feature_flags import get_feature_flag_manager

        manager = get_feature_flag_manager()

        # Handle subcommands
        if context.args:
            arg1 = context.args[0].upper()

            # Reload command
            if arg1 == "RELOAD":
                manager.reload_from_file()
                await update.message.reply_text(
                    "feature flags reloaded from config.",
                    parse_mode=ParseMode.HTML,
                )
                return

            # Flag name provided
            flag_name = arg1

            # Check if setting value
            if len(context.args) >= 2:
                value = context.args[1].lower()

                if value in ("on", "true", "enable", "1"):
                    manager.set_flag(flag_name, enabled=True)
                    await update.message.reply_text(
                        f"\u2705 <code>{flag_name}</code> enabled",
                        parse_mode=ParseMode.HTML,
                    )
                elif value in ("off", "false", "disable", "0"):
                    manager.set_flag(flag_name, enabled=False)
                    await update.message.reply_text(
                        f"\u274c <code>{flag_name}</code> disabled",
                        parse_mode=ParseMode.HTML,
                    )
                elif value.isdigit():
                    percentage = int(value)
                    manager.set_flag(flag_name, enabled=True, percentage=percentage)
                    await update.message.reply_text(
                        f"\U0001f4ca <code>{flag_name}</code> set to {percentage}% rollout",
                        parse_mode=ParseMode.HTML,
                    )
                else:
                    await update.message.reply_text(
                        f"invalid value: {value}. use on/off or a percentage.",
                        parse_mode=ParseMode.HTML,
                    )
                return

            # Show specific flag details
            flag = manager.get_flag(flag_name)
            if flag:
                status = "\u2705 ON" if flag.enabled else "\u274c OFF"
                lines = [
                    f"<b>{flag_name}</b>",
                    "",
                    f"status: {status}",
                    f"description: {flag.description}",
                    f"rollout: {flag.rollout_percentage}%",
                ]
                if flag.user_whitelist:
                    lines.append(f"whitelist: {len(flag.user_whitelist)} users")
                lines.append(f"updated: {flag.updated_at}")

                await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.HTML)
            else:
                await update.message.reply_text(
                    f"flag not found: {flag_name}",
                    parse_mode=ParseMode.HTML,
                )
            return

        # Show all flags
        all_flags = manager.get_all_flags()

        if not all_flags:
            await update.message.reply_text(
                "no feature flags configured.",
                parse_mode=ParseMode.HTML,
            )
            return

        lines = [
            "<b>feature flags</b>",
            "",
            "<i>/flags FLAG_NAME on/off to toggle</i>",
            "",
        ]

        for name, data in sorted(all_flags.items()):
            enabled = data.get("enabled", False)
            percentage = data.get("rollout_percentage", 0)

            if enabled and percentage > 0:
                status = f"\U0001f4ca {percentage}%"
            elif enabled:
                status = "\u2705"
            else:
                status = "\u274c"

            description = data.get("description", "")[:40]
            if len(data.get("description", "")) > 40:
                description += "..."

            lines.append(f"{status} <code>{name}</code>")
            if description:
                lines.append(f"   <i>{description}</i>")

        await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.HTML)

    except Exception as e:
        logger.error(f"Flags error: {e}")
        await update.message.reply_text(f"flags error: {str(e)[:100]}", parse_mode=ParseMode.MARKDOWN)
