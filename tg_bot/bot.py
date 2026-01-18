"""Jarvis Telegram bot entrypoint."""

import os
import sys
from datetime import datetime, timezone

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ChatMemberHandler,
    MessageHandler,
    filters,
)

import tg_bot.bot_core as bot_core
from tg_bot.bot_core import *  # re-export non-underscore symbols for legacy imports
from tg_bot.handlers.commands import start, help_command, status, subscribe, unsubscribe
from tg_bot.handlers.sentiment import trending, digest, report, sentiment, picks
from tg_bot.handlers.admin import reload, config_cmd, logs, system, away, back, awaystatus, memory
from tg_bot.handlers.trading import balance, positions, wallet, dashboard, button_callback, calibrate
from tg_bot.handlers import treasury as treasury_handlers
from tg_bot.handlers.sim_commands import sim, sim_buy, sim_sell, sim_pos

# Quick Wins imports (v4.9.0)
from tg_bot.handlers.commands.search_command import search_command, search_with_prices
from tg_bot.handlers.commands.export_command import export_command, export_positions, export_trades


def main():
    config = get_config()
    from core.utils.instance_lock import acquire_instance_lock

    lock = acquire_instance_lock(
        config.telegram_token,
        name="telegram_polling",
        max_wait_seconds=30,
    )
    if not lock:
        print("\n" + "=" * 50)
        print("ERROR: Telegram polling lock is already held")
        print("=" * 50)
        print("\nAnother process is already polling with this token.")
        print("Stop the other process or use a different token.")
        sys.exit(1)

    # Validate config
    if not config.telegram_token:
        print("\n" + "=" * 50)
        print("ERROR: TELEGRAM_BOT_TOKEN not set!")
        print("=" * 50)
        print("\nSet it with:")
        print("  export TELEGRAM_BOT_TOKEN='your-bot-token'")
        print("\nGet a token from @BotFather on Telegram")
        sys.exit(1)

    if not config.admin_ids:
        print("\n" + "=" * 50)
        print("WARNING: No TELEGRAM_ADMIN_IDS set")
        print("=" * 50)
        print("\nAdmin commands (analyze, digest) will be disabled.")
        print("\nTo enable, set your Telegram user ID:")
        print("  export TELEGRAM_ADMIN_IDS='your-telegram-user-id'")
        print("\nGet your ID by messaging @userinfobot on Telegram")

    # Show config status (no secrets!)
    print("\n" + "=" * 50)
    print("JARVIS TELEGRAM BOT")
    print("=" * 50)
    print(f"Admin IDs configured: {len(config.admin_ids)}")
    print(f"Grok API (XAI_API_KEY): {'Configured' if config.has_grok() else 'NOT SET'}")
    print(f"Claude API: {'Configured' if config.has_claude() else 'NOT SET'}")
    print(f"Birdeye API: {'Configured' if config.birdeye_api_key else 'NOT SET'}")
    print(f"Daily cost limit: ${config.daily_cost_limit_usd:.2f}")
    print(f"Sentiment interval: {config.sentiment_interval_seconds}s (1 hour)")
    print(f"Digest hours (UTC): {config.digest_hours}")

    # Check core modules
    service = get_signal_service()
    sources = service.get_available_sources()
    print(f"Data sources: {', '.join(sources) if sources else 'None'}")

    # Start metrics server (best-effort)
    try:
        from core.monitoring.metrics import start_metrics_server
        start_metrics_server()
    except Exception as exc:
        logger.warning(f"Metrics server unavailable: {exc}")

    # Build application
    app = Application.builder().token(config.telegram_token).build()

    # Add handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(CommandHandler("subscribe", subscribe))
    app.add_handler(CommandHandler("unsubscribe", unsubscribe))
    app.add_handler(CommandHandler("costs", costs))
    app.add_handler(CommandHandler("trending", trending))
    app.add_handler(CommandHandler("stocks", stocks))
    app.add_handler(CommandHandler("st", stocks))
    app.add_handler(CommandHandler("equities", stocks))
    app.add_handler(CommandHandler("solprice", solprice))
    app.add_handler(CommandHandler("mcap", mcap))
    app.add_handler(CommandHandler("volume", volume))
    app.add_handler(CommandHandler("chart", chart))
    app.add_handler(CommandHandler("liquidity", liquidity))
    app.add_handler(CommandHandler("age", age))
    app.add_handler(CommandHandler("summary", summary))
    app.add_handler(CommandHandler("price", price))
    app.add_handler(CommandHandler("gainers", gainers))
    app.add_handler(CommandHandler("losers", losers))
    app.add_handler(CommandHandler("newpairs", newpairs))
    app.add_handler(CommandHandler("signals", signals))
    app.add_handler(CommandHandler("analyze", analyze))
    app.add_handler(CommandHandler("a", analyze))  # Quick alias for analyze
    app.add_handler(CommandHandler("digest", digest))
    app.add_handler(CommandHandler("reload", reload))
    app.add_handler(CommandHandler("keystatus", keystatus))
    app.add_handler(CommandHandler("score", score))
    app.add_handler(CommandHandler("health", health))
    app.add_handler(CommandHandler("flags", flags))
    app.add_handler(CommandHandler("audit", audit))
    app.add_handler(CommandHandler("ratelimits", ratelimits))
    app.add_handler(CommandHandler("config", config_cmd))
    app.add_handler(CommandHandler("orders", orders))
    app.add_handler(CommandHandler("system", system))
    app.add_handler(CommandHandler("wallet", wallet))
    app.add_handler(CommandHandler("logs", logs))
    app.add_handler(CommandHandler("away", away))
    app.add_handler(CommandHandler("back", back))
    app.add_handler(CommandHandler("awaystatus", awaystatus))
    app.add_handler(CommandHandler("memory", memory))
    app.add_handler(CommandHandler("metrics", metrics))
    app.add_handler(CommandHandler("clistats", clistats))
    app.add_handler(CommandHandler("stats", clistats))
    app.add_handler(CommandHandler("s", clistats))  # Quick alias for stats
    app.add_handler(CommandHandler("queue", cliqueue))
    app.add_handler(CommandHandler("q", cliqueue))
    app.add_handler(CommandHandler("uptime", uptime))
    app.add_handler(CommandHandler("brain", brain))
    app.add_handler(CommandHandler("code", code))
    app.add_handler(CommandHandler("remember", remember))
    app.add_handler(CommandHandler("modstats", modstats))
    app.add_handler(CommandHandler("unban", unban))
    app.add_handler(CommandHandler("upgrades", upgrades))
    app.add_handler(CommandHandler("xbot", xbot))
    app.add_handler(CommandHandler("paper", paper))

    # Paper Trading Simulator (SOL-based, real prices)
    app.add_handler(CommandHandler("sim", sim))
    app.add_handler(CommandHandler("simbuy", sim_buy))
    app.add_handler(CommandHandler("simsell", sim_sell))
    app.add_handler(CommandHandler("simpos", sim_pos))
    app.add_handler(CommandHandler("dev", dev))

    # Treasury Trading Commands
    app.add_handler(CommandHandler("report", report))
    app.add_handler(CommandHandler("sentiment", sentiment))
    app.add_handler(CommandHandler("picks", picks))
    app.add_handler(CommandHandler("balance", balance))
    app.add_handler(CommandHandler("positions", positions))
    app.add_handler(CommandHandler("dashboard", dashboard))
    app.add_handler(CommandHandler("dash", dashboard))
    app.add_handler(CommandHandler("calibrate", calibrate))
    app.add_handler(CommandHandler("cal", calibrate))

    # Treasury Display Commands (v4.7.0)
    app.add_handler(CommandHandler("treasury", treasury_handlers.handle_treasury))
    app.add_handler(CommandHandler("portfolio", treasury_handlers.handle_portfolio))
    app.add_handler(CommandHandler("p", treasury_handlers.handle_portfolio))
    app.add_handler(CommandHandler("b", treasury_handlers.handle_balance))
    app.add_handler(CommandHandler("pnl", treasury_handlers.handle_pnl))
    app.add_handler(CommandHandler("sector", treasury_handlers.handle_sector))
    app.add_handler(CommandHandler("settings", settings))

    # Interactive UI Commands (v4.8.0)
    app.add_handler(CommandHandler("compare", compare))
    app.add_handler(CommandHandler("watchlist", watchlist))
    app.add_handler(CommandHandler("w", watchlist))

    # Quick Wins Commands (v4.9.0)
    app.add_handler(CommandHandler("search", search_command))
    app.add_handler(CommandHandler("searchp", search_with_prices))
    app.add_handler(CommandHandler("export", export_command))
    app.add_handler(CommandHandler("exportpos", export_positions))
    app.add_handler(CommandHandler("exporttrades", export_trades))

    app.add_handler(CommandHandler("addscam", addscam))
    app.add_handler(CommandHandler("trust", trust))
    app.add_handler(CommandHandler("trustscore", trustscore))
    app.add_handler(CommandHandler("warn", warn))
    app.add_handler(CommandHandler("flag", report_spam))
    app.add_handler(CommandHandler("togglemedia", toggle_media))

    app.add_handler(CallbackQueryHandler(button_callback))

    # Anti-scam protection (runs BEFORE regular message handler)
    if ANTISCAM_AVAILABLE and config.admin_ids:
        bot_core._ANTISCAM = AntiScamProtection(
            bot=app.bot,
            admin_ids=list(config.admin_ids),
            auto_restrict=True,
            auto_delete=True,
            alert_admins=True,
        )
        antiscam_handler = create_antiscam_handler(bot_core._ANTISCAM)
        app.add_handler(antiscam_handler, group=-1)
        print("Anti-scam protection: ENABLED")
    else:
        print("Anti-scam protection: DISABLED (no antiscam module or admin IDs)")

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Media handler - blocks GIFs/animations when restricted mode is active
    app.add_handler(MessageHandler(
        filters.ANIMATION | filters.Sticker.ALL | filters.VIDEO_NOTE,
        handle_media
    ))

    # Welcome new members - use StatusUpdate for reliability (doesn't require admin)
    app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, welcome_new_member))
    # Also keep ChatMemberHandler as backup (requires admin privileges)
    app.add_handler(ChatMemberHandler(welcome_new_member, ChatMemberHandler.CHAT_MEMBER))

    # Error handler
    app.add_error_handler(error_handler)

    # Schedule hourly digests
    job_queue = app.job_queue
    if job_queue and config.admin_ids:
        for hour in config.digest_hours:
            job_queue.run_daily(
                scheduled_digest,
                time=datetime.now(timezone.utc).replace(
                    hour=hour, minute=0, second=0, microsecond=0
                ).timetz(),
                name=f"digest_{hour}",
            )
        print(f"Scheduled digests: {config.digest_hours} UTC")
    else:
        print("Scheduled digests: DISABLED (no admin IDs)")

    print("=" * 50)
    print("Bot started! Press Ctrl+C to stop.")
    print("=" * 50 + "\n")

    # Start background services (TP/SL monitoring, health checks)
    async def startup_tasks(app):
        try:
            # Initialize health monitoring
            from core.health_monitor import get_health_monitor
            monitor = get_health_monitor()
            await monitor.start_monitoring()
            print("Health monitoring: STARTED")
        except Exception as e:
            print(f"Health monitoring: FAILED - {e}")

    app.post_init = startup_tasks

    # Run
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
