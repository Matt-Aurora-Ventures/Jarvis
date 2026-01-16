"""Handlers for sentiment-related commands."""

import os
from datetime import datetime, timezone
from pathlib import Path

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from tg_bot.config import get_config
from tg_bot.services.signal_service import get_signal_service
from tg_bot.services.cost_tracker import get_tracker
from tg_bot.services import digest_formatter as fmt
from tg_bot.handlers import error_handler, admin_only


@error_handler
async def trending(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /trending command - show trending tokens (FREE - no sentiment)."""
    config = get_config()
    user_id = update.effective_user.id
    await update.message.reply_text(
        "_Fetching trending tokens..._",
        parse_mode=ParseMode.MARKDOWN,
    )

    service = get_signal_service()
    signals = await service.get_trending_tokens(limit=5)

    if not signals:
        await update.message.reply_text(
            fmt.format_error(
                "Could not fetch trending tokens.",
                "Check /status for data source availability."
            ),
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    # Format as simple list (NO sentiment to save costs)
    lines = [
        "=" * 25,
        "*TRENDING TOKENS*",
        f"_{datetime.now(timezone.utc).strftime('%H:%M')} UTC_",
        "=" * 25,
        "",
    ]

    for i, sig in enumerate(signals, 1):
        emoji = fmt.SIGNAL_EMOJI.get(sig.signal, "")
        lines.append(f"*{i}. {sig.symbol}* {emoji}")
        lines.append(f"   {fmt.format_price(sig.price_usd)} ({fmt.format_change(sig.price_change_1h)})")
        lines.append(f"   Vol: {fmt.format_volume(sig.volume_24h)} | Liq: {fmt.format_volume(sig.liquidity_usd)}")
        lines.append(f"   [Chart]({fmt.get_dexscreener_link(sig.address)})")
        lines.append("")

    lines.append("_Use /signals for full Master Report (admin only)_")

    keyboard = None
    if config.is_admin(user_id):
        trade_buttons = [
            [InlineKeyboardButton(f"Trade {sig.symbol} (1/2/5%)", callback_data=f"trade_{sig.address}")]
            for sig in signals[:3]
        ]
        if trade_buttons:
            keyboard = InlineKeyboardMarkup(trade_buttons)

    await update.message.reply_text(
        "\n".join(lines),
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=keyboard,
        disable_web_page_preview=True,
    )


@error_handler
@admin_only
async def digest(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle /digest command - generate comprehensive digest.

    ADMIN ONLY - Uses up to 3 sentiment checks from rate limit.
    """
    await update.message.reply_text(
        "_Generating comprehensive digest..._",
        parse_mode=ParseMode.MARKDOWN,
    )

    service = get_signal_service()
    tracker = get_tracker()
    config = get_config()

    try:
        # Get trending tokens
        signals = await service.get_trending_tokens(limit=10)

        # Add sentiment to top 3 (if rate limit allows)
        sentiment_added = 0
        for i, sig in enumerate(signals[:3]):
            can_check, _ = tracker.can_make_sentiment_call()
            if can_check and config.has_grok():
                enhanced = await service.get_comprehensive_signal(
                    sig.address,
                    symbol=sig.symbol,
                    include_sentiment=True,
                )
                signals[i] = enhanced
                sentiment_added += 1

        title = f"Signal Digest ({sentiment_added} with sentiment)"
        message = fmt.format_hourly_digest(signals, title=title)

        await update.message.reply_text(
            message,
            parse_mode=ParseMode.MARKDOWN,
            disable_web_page_preview=True,
        )

    except Exception as e:
        await update.message.reply_text(
            fmt.format_error(
                "Failed to generate digest",
                f"{str(e)[:100]}"
            ),
            parse_mode=ParseMode.MARKDOWN,
        )


@error_handler
@admin_only
async def report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /report - Send full sentiment report with trading buttons.
    """
    config = get_config()
    chat_id = update.effective_chat.id

    from tg_bot import bot_core as bot_module

    # Use full SentimentReportGenerator if available
    if bot_module.SENTIMENT_REPORT_AVAILABLE:
        await update.message.reply_text(
            "\U0001f4ca _Generating full Jarvis Sentiment Report..._\n"
            "_This includes Grok AI analysis, market data, and trading buttons._",
            parse_mode=ParseMode.MARKDOWN,
        )

        try:
            import aiohttp

            # Ensure env vars are loaded for treasury status
            env_path = Path(__file__).parent.parent / ".env"
            if env_path.exists():
                with open(env_path) as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith("#") and "=" in line:
                            key, value = line.split("=", 1)
                            os.environ.setdefault(key.strip(), value.strip())

            # Get tokens and API keys from environment
            bot_token = config.telegram_token
            xai_key = os.environ.get("XAI_API_KEY", "")

            # Create the generator
            generator = bot_module.SentimentReportGenerator(
                bot_token=bot_token,
                chat_id=str(chat_id),
                xai_api_key=xai_key,
                interval_minutes=30,  # Not used for single report
            )

            # Create session (normally done by start())
            generator._session = aiohttp.ClientSession()

            try:
                # Generate and post the full report
                await generator.generate_and_post_report()
            finally:
                # Clean up session
                await generator._session.close()

        except Exception:
            # Fall back to simplified report
            await bot_module._generate_simple_report(update, context)
    else:
        # Fall back to simplified report
        await update.message.reply_text(
            "\U0001f4ca _Generating Jarvis Trading Report..._",
            parse_mode=ParseMode.MARKDOWN,
        )
        await bot_module._generate_simple_report(update, context)


@error_handler
async def sentiment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Alias for /sentiment -> /report."""
    await report(update, context)


@error_handler
async def picks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /picks - Show Grok's top conviction picks across all asset classes.

    Displays cached picks if available, or generates fresh picks.
    """
    import json
    import tempfile

    config = get_config()
    user_id = update.effective_user.id

    # Load cached picks
    temp_dir = Path(tempfile.gettempdir())
    picks_file = temp_dir / "jarvis_top_picks.json"

    if picks_file.exists():
        try:
            with open(picks_file) as f:
                picks_data = json.load(f)

            if picks_data:
                # Format picks message
                lines = [
                    "=" * 30,
                    "*JARVIS TOP PICKS*",
                    f"_Grok's highest conviction trades_",
                    "=" * 30,
                    "",
                ]

                for i, pick in enumerate(picks_data[:5]):
                    # Conviction color
                    conv = pick.get("conviction", 0)
                    if conv >= 80:
                        conv_emoji = "🟢"
                    elif conv >= 60:
                        conv_emoji = "🟡"
                    else:
                        conv_emoji = "🟠"

                    # Medal for top 3
                    medal = "🥇" if i == 0 else "🥈" if i == 1 else "🥉" if i == 2 else f"#{i+1}"

                    asset_class = pick.get("asset_class", "token").upper()
                    symbol = pick.get("symbol", "???")
                    reasoning = pick.get("reasoning", "")[:60]
                    timeframe = pick.get("timeframe", "medium")

                    lines.append(f"{medal} *{symbol}* ({asset_class}) {conv_emoji} {conv}/100")
                    lines.append(f"   {reasoning}...")
                    lines.append(f"   ⏱ {timeframe.capitalize()} term")
                    lines.append("")

                # Add expand button for trading
                from telegram import InlineKeyboardButton, InlineKeyboardMarkup
                keyboard = InlineKeyboardMarkup([
                    [InlineKeyboardButton("🏆 Trading Options", callback_data="expand:top_picks")]
                ])

                lines.append("_Use /report for full sentiment analysis_")

                await update.message.reply_text(
                    "\n".join(lines),
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=keyboard,
                )
                return
        except Exception as e:
            pass  # Fall through to "no picks" message

    # No cached picks available
    await update.message.reply_text(
        "🏆 *No picks available*\n\n"
        "Top picks are generated with the hourly sentiment report.\n"
        "Use /report to generate fresh picks with Grok analysis.\n\n"
        "_Or wait for the next scheduled report._",
        parse_mode=ParseMode.MARKDOWN,
    )
