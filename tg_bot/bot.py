"""
Jarvis Telegram Bot - Secure Production Version

Features:
- Admin-only sentiment checks (only you can trigger expensive API calls)
- Rate limiting with cost tracking (once per hour, $1/day limit)
- Multi-source signal aggregation (Grok + GMGN + DexTools + DexScreener)
- Beautiful hourly digests with links
- Zero API key exposure

Security:
- Environment-only configuration (no hardcoded keys)
- Admin whitelist enforcement
- No sensitive data in logs
- Rate limiting on expensive operations
"""

import asyncio
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import List

# Add parent dir to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ChatMemberHandler,
    ContextTypes,
)
from telegram.constants import ParseMode, ChatMemberStatus

from tg_bot.config import get_config, reload_config
from tg_bot.services.signal_service import get_signal_service
from tg_bot.services.cost_tracker import get_tracker
from tg_bot.services import digest_formatter as fmt

# Ape trading buttons with mandatory TP/SL
try:
    from bots.buy_tracker.ape_buttons import (
        parse_ape_callback,
        create_trade_setup,
        fetch_token_price,
        RiskProfile,
        RISK_PROFILE_CONFIG,
    )
    APE_BUTTONS_AVAILABLE = True
except ImportError:
    APE_BUTTONS_AVAILABLE = False
    parse_ape_callback = None

# Full sentiment report generator
try:
    from bots.buy_tracker.sentiment_report import SentimentReportGenerator
    SENTIMENT_REPORT_AVAILABLE = True
except ImportError:
    SENTIMENT_REPORT_AVAILABLE = False
    SentimentReportGenerator = None

# Self-improving integration (optional)
try:
    from core.self_improving import integration as self_improving
    SELF_IMPROVING_AVAILABLE = True
except ImportError:
    SELF_IMPROVING_AVAILABLE = False

# Configure logging (NO API RESPONSES - security)
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# Suppress noisy loggers
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("telegram").setLevel(logging.WARNING)

_TREASURY_ENGINE = None


def _parse_admin_ids(value: str) -> List[int]:
    ids = []
    for item in value.split(","):
        item = item.strip()
        if item.isdigit():
            ids.append(int(item))
    return ids


def _get_treasury_admin_ids(config) -> List[int]:
    ids_str = os.environ.get("TREASURY_ADMIN_IDS", "")
    if ids_str:
        return _parse_admin_ids(ids_str)
    return list(config.admin_ids)


def _grade_for_signal(signal) -> str:
    mapping = {
        "STRONG_BUY": "A",
        "BUY": "B+",
        "NEUTRAL": "C+",
        "SELL": "C",
        "STRONG_SELL": "C",
        "AVOID": "C",
    }
    return mapping.get(signal.signal, "B")


async def _get_treasury_engine():
    global _TREASURY_ENGINE
    if _TREASURY_ENGINE:
        return _TREASURY_ENGINE

    from bots.treasury.trading import TreasuryTrader

    # Use TreasuryTrader which handles encrypted keypair loading
    trader = TreasuryTrader()
    initialized, msg = await trader._ensure_initialized()

    if not initialized:
        raise RuntimeError(f"Treasury wallet not initialized: {msg}")

    # Check if live mode is enabled
    live_mode = os.environ.get("TREASURY_LIVE_MODE", "false").lower() in ("1", "true", "yes", "on")
    if trader._engine:
        trader._engine.dry_run = not live_mode

    _TREASURY_ENGINE = trader._engine
    return _TREASURY_ENGINE


# =============================================================================
# Security Decorators
# =============================================================================

def admin_only(func):
    """Decorator to restrict command to admins only."""
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        config = get_config()
        user_id = update.effective_user.id

        if not config.is_admin(user_id):
            # Log attempt but don't expose admin IDs
            logger.warning(f"Unauthorized access attempt by user {user_id}")
            await update.message.reply_text(
                fmt.format_unauthorized(),
                parse_mode=ParseMode.MARKDOWN,
            )
            return

        return await func(update, context)

    return wrapper


def rate_limited(func):
    """Decorator to check rate limits for expensive operations."""
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        tracker = get_tracker()
        can_proceed, reason = tracker.can_make_sentiment_call()

        if not can_proceed:
            await update.message.reply_text(
                fmt.format_rate_limit(reason),
                parse_mode=ParseMode.MARKDOWN,
            )
            return

        return await func(update, context)

    return wrapper


# =============================================================================
# Public Commands (anyone can use)
# =============================================================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command."""
    config = get_config()
    user_id = update.effective_user.id

    is_admin = config.is_admin(user_id)
    admin_status = "Admin" if is_admin else "User"

    message = f"""
*Welcome to Jarvis Trading Bot* 🤖

*Your Status:* {admin_status}

_Use the buttons below for quick access:_
"""

    # Build keyboard based on user role
    keyboard = [
        [
            InlineKeyboardButton("📈 Trending", callback_data="menu_trending"),
            InlineKeyboardButton("📊 Status", callback_data="menu_status"),
        ],
        [
            InlineKeyboardButton("💰 Costs", callback_data="menu_costs"),
            InlineKeyboardButton("❓ Help", callback_data="menu_help"),
        ],
    ]

    if is_admin:
        keyboard.insert(0, [
            InlineKeyboardButton("🚀 SIGNALS", callback_data="menu_signals"),
            InlineKeyboardButton("📋 Digest", callback_data="menu_digest"),
        ])
        keyboard.append([
            InlineKeyboardButton("🧠 Brain Stats", callback_data="menu_brain"),
            InlineKeyboardButton("🔄 Reload", callback_data="menu_reload"),
        ])

    await update.message.reply_text(
        message.strip(),
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup(keyboard),
        disable_web_page_preview=True,
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /help command."""
    await start(update, context)


async def welcome_new_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Welcome new members to the group with links and getting started info.
    Triggered when someone joins the chat.
    """
    # Check if this is a new member joining (not leaving or other status changes)
    if update.chat_member is None:
        return

    old_status = update.chat_member.old_chat_member.status
    new_status = update.chat_member.new_chat_member.status

    # Only welcome if someone is joining (was not a member, now is a member)
    was_member = old_status in [ChatMemberStatus.MEMBER, ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER]
    is_member = new_status in [ChatMemberStatus.MEMBER, ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER]

    if was_member or not is_member:
        return  # Not a new join

    new_user = update.chat_member.new_chat_member.user
    first_name = new_user.first_name or "fren"

    welcome_message = f"""
━━━━━━━━━━━━━━━━━━━━━━
*welcome, {first_name}* 🤖
━━━━━━━━━━━━━━━━━━━━━━

im jarvis - an autonomous AI trading companion built completely in public

not another wrapper. a full system you can fork, run, and make your own

━━━ *what i do* ━━━

◆ solana microcap sentiment (every 30 min)
◆ grok-powered market analysis
◆ stock picks + pre-IPO plays
◆ all tracked for accuracy - i own my Ls

━━━ *links* ━━━

🐦 [twitter/x](https://x.com/Jarvis_lifeos)
💻 [github](https://github.com/Matt-Aurora-Ventures/Jarvis)
🟢 [buy $KR8TIV](https://jup.ag/swap/SOL-KR8TIV)
📊 [dexscreener](https://dexscreener.com/solana/u1zc8qpnrq3hbjubrwfywbqtlznscppgznegwxdbags)

━━━ *build with AI* ━━━

never coded? no problem

claude opus 4.5 is free on google antigravity:
→ idx.google.com/antigravity
→ drop the jarvis repo in
→ type "please make this work"
→ watch AI build it for you

━━━━━━━━━━━━━━━━━━━━━━
ask questions anytime
*lets build* ⚡
━━━━━━━━━━━━━━━━━━━━━━
"""

    try:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=welcome_message,
            parse_mode=ParseMode.MARKDOWN,
            disable_web_page_preview=True,
        )
    except Exception as e:
        logger.error(f"Failed to send welcome message: {e}")


async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /status command - show bot status."""
    config = get_config()
    service = get_signal_service()

    available = service.get_available_sources()
    missing = config.get_optional_missing()

    message = fmt.format_status(available, missing)

    await update.message.reply_text(
        message,
        parse_mode=ParseMode.MARKDOWN,
    )


async def costs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /costs command - show API costs."""
    message = fmt.format_cost_report()

    await update.message.reply_text(
        message,
        parse_mode=ParseMode.MARKDOWN,
    )


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


# =============================================================================
# Admin-Only Commands
# =============================================================================

@admin_only
async def signals(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle /signals command - MASTER SIGNAL REPORT.

    Shows top 10 trending tokens with:
    - Clickable contract addresses
    - Entry recommendations (long/short term, leverage)
    - Full sentiment analysis
    - Risk assessment
    - All relevant links
    """
    await update.message.reply_text(
        "🚀 _Generating Master Signal Report..._",
        parse_mode=ParseMode.MARKDOWN,
    )

    service = get_signal_service()
    tracker = get_tracker()
    config = get_config()

    try:
        # Get top 10 trending
        signals_list = await service.get_trending_tokens(limit=10)

        if not signals_list:
            await update.message.reply_text(
                fmt.format_error(
                    "Could not fetch signals.",
                    "Check /status for data source availability."
                ),
                parse_mode=ParseMode.MARKDOWN,
            )
            return

        # Add Grok sentiment to top 3 if rate limit allows
        for i, sig in enumerate(signals_list[:3]):
            can_check, _ = tracker.can_make_sentiment_call()
            if can_check and config.has_grok():
                enhanced = await service.get_comprehensive_signal(
                    sig.address,
                    symbol=sig.symbol,
                    include_sentiment=True,
                )
                signals_list[i] = enhanced

        # Format the master report
        message = fmt.format_master_signal_report(signals_list)

        await update.message.reply_text(
            message,
            parse_mode=ParseMode.MARKDOWN,
            disable_web_page_preview=True,
        )

    except Exception as e:
        logger.error(f"Signals report failed: {e}")
        await update.message.reply_text(
            fmt.format_error(
                "Failed to generate signals report",
                "Check /status for issues."
            ),
            parse_mode=ParseMode.MARKDOWN,
        )


@admin_only
@rate_limited
async def analyze(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle /analyze command - full token analysis with Grok sentiment.

    ADMIN ONLY - Rate limited to 1/hour, costs ~$0.002 per call.
    """
    if not context.args:
        await update.message.reply_text(
            "Usage: `/analyze <token_address_or_symbol>`\n\n"
            "Examples:\n"
            "`/analyze SOL`\n"
            "`/analyze BONK`\n"
            "`/analyze DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263`",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    token = context.args[0]
    await update.message.reply_text(
        f"_Analyzing {token}... (includes Grok sentiment)_",
        parse_mode=ParseMode.MARKDOWN,
    )

    service = get_signal_service()

    # Resolve common symbols
    known_tokens = {
        "SOL": "So11111111111111111111111111111111111111112",
        "BONK": "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263",
        "WIF": "EKpQGSJtjMFqKZ9KQanSqYXRcF8fBopzLHYxdM65zcjm",
        "JUP": "JUPyiwrYJFskUPiHa7hkeR8VUtAeFoSYbKedZNsDvCN",
        "PYTH": "HZ1JovNiVvGrGNiiYvEozEVgZ58xaU3RKwX8eACQBCt3",
        "RAY": "4k3Dyjzvzp8eMZWUXbBCjEvwSkkk59S5iCNLY3QrkX6R",
        "ORCA": "orcaEKTdK7LKz57vaAYr9QeNsVEPfiu6QeMU1kektZE",
    }

    address = known_tokens.get(token.upper(), token)
    symbol = token.upper() if token.upper() in known_tokens else ""

    try:
        signal = await service.get_comprehensive_signal(
            address,
            symbol=symbol,
            include_sentiment=True,  # This is the expensive part
        )

        message = fmt.format_single_analysis(signal)

        # Add refresh button
        keyboard = [[
            InlineKeyboardButton(
                "Refresh (uses API)",
                callback_data=f"analyze_{token}",
            ),
            InlineKeyboardButton(
                "DexScreener",
                url=fmt.get_dexscreener_link(signal.address),
            ),
        ]]

        await update.message.reply_text(
            message,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup(keyboard),
            disable_web_page_preview=True,
        )

    except Exception as e:
        logger.error(f"Analysis failed: {e}")
        await update.message.reply_text(
            fmt.format_error(
                f"Analysis failed for {token}",
                "Check the token address and try again."
            ),
            parse_mode=ParseMode.MARKDOWN,
        )


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
        logger.error(f"Digest generation failed: {e}")
        await update.message.reply_text(
            fmt.format_error(
                "Failed to generate digest",
                "Check /status for issues."
            ),
            parse_mode=ParseMode.MARKDOWN,
        )


@admin_only
async def reload(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /reload command - reload config (admin only)."""
    reload_config()
    await update.message.reply_text(
        "Configuration reloaded from environment.",
        parse_mode=ParseMode.MARKDOWN,
    )


@admin_only
async def brain(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /brain command - show self-improving system stats (admin only)."""
    if not SELF_IMPROVING_AVAILABLE:
        await update.message.reply_text(
            "Self-improving module not installed.",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    try:
        stats = self_improving.get_stats()
        health = self_improving.health_check()

        # Format trust levels
        trust_info = stats.get("trust", {})
        trust_lines = []
        for domain, data in trust_info.items():
            if isinstance(data, dict):
                level = data.get("level", 0)
                level_names = ["STRANGER", "ACQUAINTANCE", "COLLEAGUE", "PARTNER", "OPERATOR"]
                level_name = level_names[level] if 0 <= level < len(level_names) else "UNKNOWN"
                trust_lines.append(f"  • {domain}: {level_name} ({level})")

        # Format memory stats
        memory = stats.get("memory", {})

        # Format message
        lines = [
            "*🧠 Self-Improving Brain Status*",
            "",
            f"*Uptime:* {stats.get('uptime_hours', 0):.1f} hours",
            f"*Sessions:* {stats.get('sessions', 0)}",
            f"*Last Reflection:* {stats.get('last_reflection', 'Never')}",
            "",
            "*Trust Levels:*",
        ]
        lines.extend(trust_lines if trust_lines else ["  No domains tracked yet"])

        lines.extend([
            "",
            "*Memory:*",
            f"  • Facts: {memory.get('facts_count', 0)}",
            f"  • Reflections: {memory.get('reflections_count', 0)}",
            f"  • Interactions: {memory.get('interactions_count', 0)}",
            f"  • Predictions: {memory.get('predictions_count', 0)}",
            "",
            "*Health:*",
            f"  • Memory: {'OK' if health.get('memory') else 'FAIL'}",
            f"  • Trust: {'OK' if health.get('trust') else 'FAIL'}",
            f"  • Reflexion: {'OK' if health.get('reflexion') else 'FAIL'}",
            f"  • LLM Client: {'OK' if health.get('llm_client') else 'Not Set'}",
        ])

        await update.message.reply_text(
            "\n".join(lines),
            parse_mode=ParseMode.MARKDOWN,
        )

    except Exception as e:
        logger.error(f"Brain stats failed: {e}")
        await update.message.reply_text(
            f"Failed to get brain stats: {str(e)[:100]}",
            parse_mode=ParseMode.MARKDOWN,
        )


# =============================================================================
# Paper Trading Commands
# =============================================================================

@admin_only
async def paper(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Paper trading commands: /paper [wallet|buy|sell|reset|history]"""
    try:
        from core import paper_trading

        args = context.args or []
        subcommand = args[0].lower() if args else "wallet"

        if subcommand == "wallet" or subcommand == "status":
            performance = paper_trading.get_performance()
            wallet = paper_trading.get_wallet()

            roi = performance["roi_pct"]
            roi_emoji = "📈" if roi >= 0 else "📉"

            lines = [
                "*💰 Paper Trading Wallet*",
                "",
                f"*Balance:* ${performance['balance_usd']:.2f}",
                f"*Initial:* ${performance['initial_balance']:.2f}",
                f"*P&L:* ${performance['total_pnl']:+.2f}",
                f"*ROI:* {roi_emoji} {roi:+.2f}%",
                "",
                f"*Trades:* {performance['total_trades']}",
                f"*Wins:* {performance['winning_trades']} | *Losses:* {performance['losing_trades']}",
                f"*Win Rate:* {performance['win_rate']:.1f}%",
                f"*Fees Paid:* ${performance['total_fees_paid']:.2f}",
            ]

            if performance["has_position"]:
                pos = performance["current_position"]
                lines.extend([
                    "",
                    "*Current Position:*",
                    f"  {pos['symbol']} @ ${pos['entry_price']:.8f}",
                    f"  Size: ${pos['position_usd']:.2f}",
                ])

            await update.message.reply_text(
                "\n".join(lines),
                parse_mode=ParseMode.MARKDOWN,
            )

        elif subcommand == "buy":
            # /paper buy <symbol> <mint> <price> [size_usd]
            if len(args) < 4:
                await update.message.reply_text(
                    "Usage: `/paper buy <symbol> <mint> <price> [size_usd]`",
                    parse_mode=ParseMode.MARKDOWN,
                )
                return

            symbol = args[1].upper()
            mint = args[2]
            price = float(args[3])
            size_usd = float(args[4]) if len(args) > 4 else None

            trade = paper_trading.open_position(
                symbol=symbol,
                mint=mint,
                price=price,
                position_usd=size_usd,
            )

            await update.message.reply_text(
                f"*✅ Paper Buy Executed*\n\n"
                f"*Symbol:* {trade.symbol}\n"
                f"*Entry:* ${trade.entry_price:.8f}\n"
                f"*Size:* ${trade.position_usd:.2f}\n"
                f"*Quantity:* {trade.quantity:.4f}\n"
                f"*Fee:* ${trade.fee_usd:.2f}",
                parse_mode=ParseMode.MARKDOWN,
            )

        elif subcommand == "sell":
            # /paper sell <price> [reason]
            if len(args) < 2:
                await update.message.reply_text(
                    "Usage: `/paper sell <price> [reason]`",
                    parse_mode=ParseMode.MARKDOWN,
                )
                return

            price = float(args[1])
            reason = " ".join(args[2:]) if len(args) > 2 else "MANUAL_EXIT"

            trade = paper_trading.close_position(price, reason)

            if trade:
                pnl_emoji = "🟢" if trade.pnl_usd >= 0 else "🔴"
                await update.message.reply_text(
                    f"*✅ Paper Sell Executed*\n\n"
                    f"*Symbol:* {trade.symbol}\n"
                    f"*Exit:* ${trade.exit_price:.8f}\n"
                    f"*P&L:* {pnl_emoji} ${trade.pnl_usd:+.2f} ({trade.pnl_pct:+.2f}%)\n"
                    f"*Reason:* {trade.exit_reason}",
                    parse_mode=ParseMode.MARKDOWN,
                )
            else:
                await update.message.reply_text("No open position to close.")

        elif subcommand == "reset":
            # /paper reset [initial_balance]
            initial = float(args[1]) if len(args) > 1 else 1000.0
            paper_trading.reset_wallet(initial)
            await update.message.reply_text(
                f"*🔄 Wallet Reset*\n\nNew balance: ${initial:.2f}",
                parse_mode=ParseMode.MARKDOWN,
            )

        elif subcommand == "history":
            engine = paper_trading.get_engine()
            trades = engine.get_trade_history(limit=10)

            if not trades:
                await update.message.reply_text("No trade history yet.")
                return

            lines = ["*📜 Recent Paper Trades*", ""]
            for t in trades:
                if t.status == "closed":
                    pnl_emoji = "🟢" if t.pnl_usd >= 0 else "🔴"
                    lines.append(
                        f"{pnl_emoji} {t.symbol}: ${t.pnl_usd:+.2f} ({t.pnl_pct:+.1f}%)"
                    )
                else:
                    lines.append(f"⏳ {t.symbol}: Open @ ${t.entry_price:.8f}")

            await update.message.reply_text(
                "\n".join(lines),
                parse_mode=ParseMode.MARKDOWN,
            )

        else:
            await update.message.reply_text(
                "*Paper Trading Commands:*\n"
                "`/paper` - View wallet status\n"
                "`/paper buy <symbol> <mint> <price> [size]` - Open position\n"
                "`/paper sell <price> [reason]` - Close position\n"
                "`/paper history` - View trade history\n"
                "`/paper reset [balance]` - Reset wallet",
                parse_mode=ParseMode.MARKDOWN,
            )

    except ValueError as e:
        await update.message.reply_text(f"Error: {str(e)}")
    except Exception as e:
        logger.error(f"Paper trading error: {e}")
        await update.message.reply_text(f"Paper trading error: {str(e)[:100]}")


# =============================================================================
# Treasury Trading Commands
# =============================================================================

ADMIN_USER_ID = 8527130908  # Authorized admin


@admin_only
async def report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /report - Send full sentiment report with trading buttons.

    Uses the SentimentReportGenerator for beautiful multi-message reports with:
    - TOP 10 tokens with Grok AI sentiment analysis
    - APE trading buttons (5%/2%/1% allocation x Safe/Med/Degen risk)
    - Market/macro analysis
    - XStocks/PreStocks tokenized equities
    - Treasury status
    """
    config = get_config()
    chat_id = update.effective_chat.id

    # Use full SentimentReportGenerator if available
    if SENTIMENT_REPORT_AVAILABLE:
        await update.message.reply_text(
            "📊 _Generating full Jarvis Sentiment Report..._\n_This includes Grok AI analysis, market data, and trading buttons._",
            parse_mode=ParseMode.MARKDOWN,
        )

        try:
            import aiohttp

            # Ensure env vars are loaded for treasury status
            env_path = Path(__file__).parent / ".env"
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
            generator = SentimentReportGenerator(
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
                logger.info(f"Full sentiment report posted to chat {chat_id}")
            finally:
                # Clean up session
                await generator._session.close()

        except Exception as e:
            logger.error(f"Full report generation failed: {e}")
            # Fall back to simplified report
            await _generate_simple_report(update, context)
    else:
        # Fall back to simplified report
        await update.message.reply_text(
            "📊 _Generating Jarvis Trading Report..._",
            parse_mode=ParseMode.MARKDOWN,
        )
        await _generate_simple_report(update, context)


async def _generate_simple_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Generate simplified report when SentimentReportGenerator is not available."""
    service = get_signal_service()
    tracker = get_tracker()
    config = get_config()

    try:
        # Get top 10 trending
        signals_list = await service.get_trending_tokens(limit=10)

        if not signals_list:
            await update.message.reply_text(
                "❌ *Error*\n\nCould not fetch signals.\nCheck /status for data source availability.",
                parse_mode=ParseMode.MARKDOWN,
            )
            return

        # Add Grok sentiment to top 5 if rate limit allows
        for i, sig in enumerate(signals_list[:5]):
            can_check, _ = tracker.can_make_sentiment_call()
            if can_check and config.has_grok():
                enhanced = await service.get_comprehensive_signal(
                    sig.address,
                    symbol=sig.symbol,
                    include_sentiment=True,
                )
                signals_list[i] = enhanced

        # Get treasury info
        try:
            engine = await _get_treasury_engine()
            _, portfolio_usd = await engine.get_portfolio_value()
            mode = "🟢 LIVE" if not engine.dry_run else "🟡 PAPER"
        except Exception:
            portfolio_usd = 0
            mode = "⚪ OFFLINE"

        # Build the full report as ONE message
        message = _build_full_trading_report(signals_list, portfolio_usd, mode)

        # Build trading buttons for top 3 tokens
        keyboard_rows = []
        for sig in signals_list[:3]:
            grade = _grade_for_signal(sig)
            grade_emoji = _get_grade_emoji(grade)
            keyboard_rows.append([
                InlineKeyboardButton(
                    f"📈 {sig.symbol} 1%",
                    callback_data=f"trade_pct:{sig.address}:1:{grade}"
                ),
                InlineKeyboardButton(
                    f"📈 {sig.symbol} 2%",
                    callback_data=f"trade_pct:{sig.address}:2:{grade}"
                ),
                InlineKeyboardButton(
                    f"📈 {sig.symbol} 5%",
                    callback_data=f"trade_pct:{sig.address}:5:{grade}"
                ),
            ])

        keyboard_rows.append([
            InlineKeyboardButton("🔄 Refresh", callback_data="refresh_report"),
            InlineKeyboardButton("💼 Positions", callback_data="show_positions_detail"),
        ])

        await update.message.reply_text(
            message,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup(keyboard_rows),
            disable_web_page_preview=True,
        )

    except Exception as e:
        logger.error(f"Report generation failed: {e}")
        await update.message.reply_text(
            f"❌ *Error*\n\nFailed to generate report: {str(e)[:100]}",
            parse_mode=ParseMode.MARKDOWN,
        )


def _build_full_trading_report(signals_list, portfolio_usd: float, mode: str) -> str:
    """Build a complete, non-fragmented trading report."""
    now = datetime.now(timezone.utc)
    lines = []

    # Header
    lines.append("═" * 28)
    lines.append("🤖 *JARVIS TRADING REPORT*")
    lines.append(f"📅 {now.strftime('%Y-%m-%d %H:%M')} UTC")
    lines.append("═" * 28)
    lines.append("")

    # Treasury Status
    lines.append("💰 *TREASURY STATUS*")
    lines.append(f"   Balance: ${portfolio_usd:,.2f}")
    lines.append(f"   Mode: {mode}")
    lines.append("")

    # Market Summary
    strong_buys = [s for s in signals_list if s.signal == "STRONG_BUY"]
    buys = [s for s in signals_list if s.signal == "BUY"]
    sells = [s for s in signals_list if s.signal in ["SELL", "STRONG_SELL"]]

    lines.append("📊 *MARKET OVERVIEW*")
    lines.append(f"   🟢 Strong Buy: {len(strong_buys)}")
    lines.append(f"   🟢 Buy: {len(buys)}")
    lines.append(f"   🔴 Avoid: {len(sells)}")
    lines.append("")

    # TOP 10 Tokens
    lines.append("─" * 28)
    lines.append("📈 *TOP 10 TRENDING TOKENS*")
    lines.append("─" * 28)
    lines.append("")

    for i, sig in enumerate(signals_list[:10], 1):
        grade = _grade_for_signal(sig)
        grade_emoji = _get_grade_emoji(grade)

        # Token header with grade
        lines.append(f"*{i}. {sig.symbol}* {grade_emoji} Grade: *{grade}*")

        # Price and changes
        price_str = fmt.format_price(sig.price_usd) if sig.price_usd else "$0.00"
        change_1h = f"+{sig.price_change_1h:.1f}%" if sig.price_change_1h > 0 else f"{sig.price_change_1h:.1f}%"
        change_24h = f"+{sig.price_change_24h:.1f}%" if sig.price_change_24h > 0 else f"{sig.price_change_24h:.1f}%"

        lines.append(f"   💵 {price_str}")
        lines.append(f"   📊 1h: {change_1h} | 24h: {change_24h}")

        # Volume and Mcap
        vol_str = fmt.format_volume(sig.volume_24h) if sig.volume_24h else "$0"
        liq_str = fmt.format_volume(sig.liquidity_usd) if sig.liquidity_usd else "$0"
        lines.append(f"   📈 Vol: {vol_str} | Liq: {liq_str}")

        # Sentiment if available
        if sig.sentiment and sig.sentiment != "neutral":
            sent_emoji = "😀" if sig.sentiment == "positive" else "😟" if sig.sentiment == "negative" else "🤔"
            lines.append(f"   {sent_emoji} Grok: {sig.sentiment.upper()}")

        # TP/SL levels
        tp_pct, sl_pct = _get_tp_sl_for_grade(grade)
        lines.append(f"   🎯 TP: +{int(tp_pct*100)}% | SL: -{int(sl_pct*100)}%")

        # Contract (shortened)
        if sig.address:
            short_addr = f"{sig.address[:6]}...{sig.address[-4:]}"
            lines.append(f"   📋 `{sig.address}`")

        # Links
        lines.append(f"   🔗 [Chart]({fmt.get_dexscreener_link(sig.address)})")
        lines.append("")

    # Footer
    lines.append("─" * 28)
    lines.append("⚡ _Tap buttons above to trade_")
    lines.append("_TP/SL auto-set based on grade_")

    return "\n".join(lines)


def _get_grade_emoji(grade: str) -> str:
    """Get emoji for grade."""
    emoji_map = {
        'A+': '🟢🟢', 'A': '🟢🟢', 'A-': '🟢',
        'B+': '🟢', 'B': '🟡', 'B-': '🟡',
        'C+': '🟡', 'C': '🟠', 'C-': '🟠',
        'D': '🔴', 'F': '🔴🔴'
    }
    return emoji_map.get(grade, '⚪')


def _get_tp_sl_for_grade(grade: str) -> tuple:
    """Get TP/SL percentages for grade."""
    tp_sl_map = {
        'A+': (0.30, 0.08), 'A': (0.30, 0.08), 'A-': (0.25, 0.10),
        'B+': (0.20, 0.10), 'B': (0.18, 0.12), 'B-': (0.15, 0.12),
        'C+': (0.12, 0.15), 'C': (0.10, 0.15), 'C-': (0.08, 0.15),
        'D': (0.05, 0.20), 'F': (0.05, 0.20)
    }
    return tp_sl_map.get(grade, (0.20, 0.10))


def _grade_for_signal(signal) -> str:
    """
    Calculate grade for a signal based on multiple factors.
    Returns A+, A, B+, B, C, D, or F.
    """
    score = 0

    # Signal type (+15 to -15)
    signal_scores = {
        'STRONG_BUY': 15, 'BUY': 10, 'NEUTRAL': 0,
        'SELL': -10, 'STRONG_SELL': -15, 'AVOID': -20
    }
    score += signal_scores.get(signal.signal, 0)

    # Sentiment (+10 to -10)
    if hasattr(signal, 'sentiment') and signal.sentiment:
        if signal.sentiment == 'positive':
            score += 10
        elif signal.sentiment == 'negative':
            score -= 10

    # Security score (+10 to -10)
    if hasattr(signal, 'security_score'):
        if signal.security_score >= 80:
            score += 10
        elif signal.security_score >= 60:
            score += 5
        elif signal.security_score < 40:
            score -= 10

    # Risk level
    risk_scores = {'low': 5, 'medium': 0, 'high': -5, 'critical': -15}
    if hasattr(signal, 'risk_level'):
        score += risk_scores.get(signal.risk_level, 0)

    # Liquidity bonus
    if hasattr(signal, 'liquidity_usd') and signal.liquidity_usd:
        if signal.liquidity_usd > 1_000_000:
            score += 5
        elif signal.liquidity_usd > 500_000:
            score += 3

    # Smart money signal
    if hasattr(signal, 'smart_money_signal'):
        if signal.smart_money_signal == 'bullish':
            score += 5
        elif signal.smart_money_signal == 'bearish':
            score -= 5

    # Convert score to grade
    if score >= 25:
        return 'A+'
    elif score >= 20:
        return 'A'
    elif score >= 15:
        return 'A-'
    elif score >= 10:
        return 'B+'
    elif score >= 5:
        return 'B'
    elif score >= 0:
        return 'B-'
    elif score >= -5:
        return 'C+'
    elif score >= -10:
        return 'C'
    elif score >= -15:
        return 'C-'
    elif score >= -20:
        return 'D'
    else:
        return 'F'


@admin_only
async def balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /balance - Show treasury balance and allocation.
    """
    try:
        engine = await _get_treasury_engine()
        sol_balance, usd_value = await engine.get_portfolio_value()
        mode = "🟢 LIVE" if not engine.dry_run else "🟡 PAPER"

        # Get wallet address
        treasury = engine.wallet.get_treasury()
        address = treasury.address if treasury else "Unknown"
        short_addr = f"{address[:8]}...{address[-4:]}" if address else "N/A"

        message = f"""
💰 *TREASURY BALANCE*

*Wallet:* `{short_addr}`
*SOL:* `{sol_balance:.4f}` SOL
*USD:* `${usd_value:,.2f}`

*Mode:* {mode}
*Max Positions:* {engine.max_positions}
*Risk Level:* {engine.risk_level.value}

⚠️ _Low balance warning: <0.05 SOL_
"""

        # Warning if low balance
        if sol_balance < 0.05:
            message += "\n🚨 *WARNING: Low balance!*"

        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("🔄 Refresh", callback_data="refresh_balance"),
                InlineKeyboardButton("📊 Report", callback_data="refresh_report"),
            ]
        ])

        await update.message.reply_text(
            message,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=keyboard,
        )

    except Exception as e:
        logger.error(f"Balance check failed: {e}")
        await update.message.reply_text(
            f"❌ *Error*\n\nFailed to get balance: {str(e)[:100]}",
            parse_mode=ParseMode.MARKDOWN,
        )


@admin_only
async def positions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /positions - Show open positions with P&L and sell buttons.
    """
    try:
        engine = await _get_treasury_engine()
        await engine.update_positions()
        open_positions = engine.get_open_positions()

        if not open_positions:
            await update.message.reply_text(
                "📋 *OPEN POSITIONS*\n\n_No open positions._\n\nUse /report to find trading opportunities.",
                parse_mode=ParseMode.MARKDOWN,
            )
            return

        lines = ["📋 *OPEN POSITIONS*", ""]

        keyboard_rows = []
        total_pnl = 0

        for pos in open_positions:
            pnl_pct = pos.unrealized_pnl_pct
            pnl_usd = pos.unrealized_pnl
            total_pnl += pnl_usd

            pnl_emoji = "🟢" if pnl_pct >= 0 else "🔴"

            lines.append(f"*{pos.token_symbol}* {pnl_emoji}")
            lines.append(f"   Entry: ${pos.entry_price:.8f}")
            lines.append(f"   Current: ${pos.current_price:.8f}")
            lines.append(f"   P&L: {pnl_pct:+.1f}% (${pnl_usd:+.2f})")
            lines.append(f"   🎯 TP: ${pos.take_profit_price:.8f}")
            lines.append(f"   🛑 SL: ${pos.stop_loss_price:.8f}")
            lines.append(f"   ID: `{pos.id}`")
            lines.append("")

            # Add sell button for each position
            keyboard_rows.append([
                InlineKeyboardButton(
                    f"🔴 SELL {pos.token_symbol}",
                    callback_data=f"sell_pos:{pos.id}"
                )
            ])

        # Summary
        total_emoji = "🟢" if total_pnl >= 0 else "🔴"
        lines.append(f"─" * 20)
        lines.append(f"*Total P&L:* {total_emoji} ${total_pnl:+.2f}")

        keyboard_rows.append([
            InlineKeyboardButton("🔄 Refresh", callback_data="show_positions_detail"),
        ])

        await update.message.reply_text(
            "\n".join(lines),
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup(keyboard_rows),
        )

    except Exception as e:
        logger.error(f"Positions check failed: {e}")
        await update.message.reply_text(
            f"❌ *Error*\n\nFailed to get positions: {str(e)[:100]}",
            parse_mode=ParseMode.MARKDOWN,
        )


@admin_only
async def settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /settings - Show current TP/SL settings and trading config.
    """
    try:
        engine = await _get_treasury_engine()
        mode = "🟢 LIVE" if not engine.dry_run else "🟡 PAPER"

        message = f"""
⚙️ *TRADING SETTINGS*

*Mode:* {mode}
*Risk Level:* {engine.risk_level.value}
*Max Positions:* {engine.max_positions}
*Slippage:* 20% max (2000 bps)

*TP/SL by Grade:*
🟢 A+/A: +30% TP / -8% SL
🟢 B+: +20% TP / -10% SL
🟡 B: +18% TP / -12% SL
🟠 C: +10% TP / -15% SL
🔴 D/F: ⛔ DO NOT TRADE

*Admin ID:* `{ADMIN_USER_ID}`
*RPC:* Helius (Primary)

_All trades require TP/SL - no exceptions_
"""

        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton(
                    "🟢 Go LIVE" if engine.dry_run else "🟡 Go PAPER",
                    callback_data="toggle_live_mode"
                ),
            ],
            [
                InlineKeyboardButton("📊 Report", callback_data="refresh_report"),
                InlineKeyboardButton("💰 Balance", callback_data="refresh_balance"),
            ]
        ])

        await update.message.reply_text(
            message,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=keyboard,
        )

    except Exception as e:
        logger.error(f"Settings check failed: {e}")
        await update.message.reply_text(
            f"❌ *Error*\n\nFailed to get settings: {str(e)[:100]}",
            parse_mode=ParseMode.MARKDOWN,
        )


# =============================================================================
# Callback Query Handler
# =============================================================================

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle inline keyboard button presses."""
    query = update.callback_query
    await query.answer()

    data = query.data
    config = get_config()
    user_id = update.effective_user.id

    # Log all callbacks for debugging
    logger.info(f"Callback received: '{data}' from user {user_id}")

    # Menu navigation callbacks
    if data == "menu_trending":
        update.message = query.message
        context.args = []
        await _handle_trending_inline(query)
        return

    if data == "menu_status":
        update.message = query.message
        await _handle_status_inline(query)
        return

    if data == "menu_costs":
        message = fmt.format_cost_report()
        keyboard = [[InlineKeyboardButton("🏠 Back to Menu", callback_data="menu_back")]]
        await query.message.reply_text(
            message,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
        return

    if data == "menu_help":
        help_text = """
*Jarvis Bot Commands*

*Public:*
/trending - Top 5 trending tokens (free)
/status - Check API status
/costs - View daily costs

*Admin Only:*
/signals - 🚀 Master Signal Report
/analyze <token> - Full analysis
/digest - Generate digest
/brain - AI brain stats
"""
        keyboard = [[InlineKeyboardButton("🏠 Back to Menu", callback_data="menu_back")]]
        await query.message.reply_text(
            help_text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
        return

    if data == "menu_back":
        # Re-send main menu
        is_admin = config.is_admin(user_id)
        keyboard = [
            [
                InlineKeyboardButton("📈 Trending", callback_data="menu_trending"),
                InlineKeyboardButton("📊 Status", callback_data="menu_status"),
            ],
            [
                InlineKeyboardButton("💰 Costs", callback_data="menu_costs"),
                InlineKeyboardButton("❓ Help", callback_data="menu_help"),
            ],
        ]
        if is_admin:
            keyboard.insert(0, [
                InlineKeyboardButton("🚀 SIGNALS", callback_data="menu_signals"),
                InlineKeyboardButton("📋 Digest", callback_data="menu_digest"),
            ])
            keyboard.append([
                InlineKeyboardButton("🧠 Brain Stats", callback_data="menu_brain"),
                InlineKeyboardButton("🔄 Reload", callback_data="menu_reload"),
            ])
        await query.message.reply_text(
            "*Jarvis Trading Bot* 🤖\n\n_Select an option:_",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
        return

    # Admin-only menu callbacks
    if data == "menu_signals":
        if not config.is_admin(user_id):
            await query.message.reply_text(fmt.format_unauthorized(), parse_mode=ParseMode.MARKDOWN)
            return
        update.message = query.message
        context.args = []
        await signals(update, context)
        return

    if data == "menu_digest":
        if not config.is_admin(user_id):
            await query.message.reply_text(fmt.format_unauthorized(), parse_mode=ParseMode.MARKDOWN)
            return
        update.message = query.message
        context.args = []
        await digest(update, context)
        return

    if data == "menu_brain":
        if not config.is_admin(user_id):
            await query.message.reply_text(fmt.format_unauthorized(), parse_mode=ParseMode.MARKDOWN)
            return
        update.message = query.message
        context.args = []
        await brain(update, context)
        return

    if data == "menu_reload":
        if not config.is_admin(user_id):
            await query.message.reply_text(fmt.format_unauthorized(), parse_mode=ParseMode.MARKDOWN)
            return
        update.message = query.message
        context.args = []
        await reload(update, context)
        return

    # Trading callbacks
    if data.startswith("trade_"):
        if not config.is_admin(user_id):
            await query.message.reply_text(fmt.format_unauthorized(), parse_mode=ParseMode.MARKDOWN)
            return

        token_address = data.replace("trade_", "", 1)
        await _show_trade_ticket(query, token_address)
        return

    if data.startswith("buy_"):
        if not config.is_admin(user_id):
            await query.message.reply_text(fmt.format_unauthorized(), parse_mode=ParseMode.MARKDOWN)
            return

        await _execute_trade_percent(query, data)
        return

    # Token-specific callbacks
    if data.startswith("analyze_"):
        if not config.is_admin(user_id):
            await query.message.reply_text(fmt.format_unauthorized(), parse_mode=ParseMode.MARKDOWN)
            return

        token = data.replace("analyze_", "")
        context.args = [token]
        update.message = query.message
        await analyze(update, context)
        return

    if data == "refresh_trending":
        await _handle_trending_inline(query)
        return

    # New trading callbacks
    if data.startswith("trade_pct:"):
        if not config.is_admin(user_id):
            await query.message.reply_text(
                "⛔ *Admin Only*\n\nYou are not authorized to trade.",
                parse_mode=ParseMode.MARKDOWN
            )
            logger.warning(f"Unauthorized trade attempt by user {user_id}")
            return

        await _execute_trade_with_tp_sl(query, data)
        return

    if data.startswith("sell_pos:"):
        if not config.is_admin(user_id):
            await query.message.reply_text("⛔ *Admin Only*", parse_mode=ParseMode.MARKDOWN)
            return

        position_id = data.split(":")[1]
        await _close_position_callback(query, position_id)
        return

    if data == "refresh_report":
        if not config.is_admin(user_id):
            return
        await _refresh_report_inline(query)
        return

    if data == "refresh_balance":
        if not config.is_admin(user_id):
            return
        await _refresh_balance_inline(query)
        return

    if data == "show_positions_detail":
        if not config.is_admin(user_id):
            return
        await _show_positions_inline(query)
        return

    if data == "toggle_live_mode":
        if not config.is_admin(user_id):
            return
        await _toggle_live_mode(query)
        return

    # Ape button callbacks from sentiment reports (format: ape:{alloc}:{profile}:{type}:{symbol}:{contract})
    if data.startswith("ape:"):
        logger.info(f"Ape callback received: {data} from user {user_id}")

        if not APE_BUTTONS_AVAILABLE:
            await query.message.reply_text(
                "❌ Ape trading module not available",
                parse_mode=ParseMode.MARKDOWN
            )
            logger.error("APE_BUTTONS_AVAILABLE is False")
            return

        if not config.is_admin(user_id):
            await query.message.reply_text(
                f"⛔ *Admin Only*\n\nUser ID {user_id} is not authorized.\nAdmin ID: {ADMIN_USER_ID}",
                parse_mode=ParseMode.MARKDOWN
            )
            logger.warning(f"Unauthorized ape trade attempt by user {user_id}")
            return

        logger.info(f"Executing ape trade for admin {user_id}")
        await _execute_ape_trade(query, data)
        return


async def _execute_ape_trade(query, callback_data: str):
    """
    Execute an ape trade from sentiment report buttons.

    Callback format: ape:{alloc}:{profile}:{type}:{symbol}:{contract}
    Example: ape:5:m:t:BONK:DezXAZ8z7P

    All trades have MANDATORY TP/SL based on risk profile.
    """
    user_id = query.from_user.id

    # Parse the callback
    parsed = parse_ape_callback(callback_data)
    if not parsed:
        await query.message.reply_text(
            "❌ Invalid trade button format",
            parse_mode=ParseMode.MARKDOWN
        )
        return

    symbol = parsed["symbol"]
    allocation_pct = parsed["allocation_percent"]
    risk_profile = parsed["risk_profile"]
    contract = parsed.get("contract", "")

    # Get risk profile config
    profile_config = RISK_PROFILE_CONFIG[risk_profile]
    tp_pct = profile_config["tp_pct"]
    sl_pct = profile_config["sl_pct"]
    profile_label = profile_config["label"]

    await query.edit_message_text(
        f"⏳ *Processing APE Trade...*\n\n"
        f"Token: {symbol}\n"
        f"Allocation: {allocation_pct}%\n"
        f"Profile: {profile_label}\n"
        f"TP: +{int(tp_pct)}% | SL: -{int(sl_pct)}%",
        parse_mode=ParseMode.MARKDOWN
    )

    try:
        # Get treasury engine
        engine = await _get_treasury_engine()
        balance_sol, balance_usd = await engine.get_portfolio_value()

        if balance_sol <= 0:
            await query.message.reply_text(
                "❌ *Error*\n\nTreasury balance is zero.",
                parse_mode=ParseMode.MARKDOWN
            )
            return

        # Fetch current token price
        price = await fetch_token_price(contract, symbol)
        if price <= 0:
            await query.message.reply_text(
                f"❌ Could not fetch price for {symbol}",
                parse_mode=ParseMode.MARKDOWN
            )
            return

        # Create trade setup with TP/SL
        trade_setup = create_trade_setup(
            parsed_callback=parsed,
            entry_price=price,
            treasury_balance_sol=balance_sol,
            direction="LONG",
            grade=""
        )

        # Validate trade setup
        is_valid, error_msg = trade_setup.validate()
        if not is_valid:
            await query.message.reply_text(
                f"❌ *Invalid Trade Setup*\n\n{error_msg}",
                parse_mode=ParseMode.MARKDOWN
            )
            return

        # Calculate trade values
        amount_sol = trade_setup.amount_sol
        amount_usd = amount_sol * (balance_usd / balance_sol) if balance_sol > 0 else 0

        mode = "🟢 LIVE" if not engine.dry_run else "🟡 PAPER"

        # Execute trade via treasury engine
        if engine.dry_run:
            # Paper trade simulation
            result = f"✅ *{mode} APE Trade Simulated*\n\n"
            result += f"Token: *{symbol}*\n"
            result += f"Entry: ${price:.8f}\n"
            result += f"Amount: {amount_sol:.4f} SOL (~${amount_usd:.2f})\n"
            result += f"Profile: {profile_label}\n"
            result += f"TP: ${trade_setup.take_profit_price:.8f} (+{int(tp_pct)}%)\n"
            result += f"SL: ${trade_setup.stop_loss_price:.8f} (-{int(sl_pct)}%)\n\n"
            result += f"_Paper mode - no real trade executed_"
        else:
            # LIVE trade execution via Jupiter
            from bots.treasury.jupiter import JupiterSwap

            jupiter = JupiterSwap(
                rpc_url=os.environ.get("HELIUS_RPC_URL", ""),
                keypair=engine._wallet_keypair,
            )

            # SOL mint is constant
            sol_mint = "So11111111111111111111111111111111111111112"

            # Execute swap
            tx_sig = await jupiter.swap(
                input_mint=sol_mint,
                output_mint=contract if len(contract) > 20 else "",
                amount_in_lamports=int(amount_sol * 1_000_000_000),
                slippage_bps=100,  # 1% slippage
            )

            if tx_sig:
                result = f"✅ *{mode} APE Trade Executed!*\n\n"
                result += f"Token: *{symbol}*\n"
                result += f"Entry: ${price:.8f}\n"
                result += f"Amount: {amount_sol:.4f} SOL (~${amount_usd:.2f})\n"
                result += f"Profile: {profile_label}\n"
                result += f"TP: ${trade_setup.take_profit_price:.8f} (+{int(tp_pct)}%)\n"
                result += f"SL: ${trade_setup.stop_loss_price:.8f} (-{int(sl_pct)}%)\n\n"
                result += f"[View TX](https://solscan.io/tx/{tx_sig})"
            else:
                result = f"❌ *Trade Failed*\n\nCould not execute swap for {symbol}"

        await query.message.reply_text(result, parse_mode=ParseMode.MARKDOWN, disable_web_page_preview=True)

    except Exception as e:
        logger.error(f"Ape trade failed: {e}")
        await query.message.reply_text(
            f"❌ *Trade Error*\n\n{str(e)[:200]}",
            parse_mode=ParseMode.MARKDOWN
        )


async def _execute_trade_with_tp_sl(query, data: str):
    """Execute a trade with TP/SL based on grade. ADMIN ONLY."""
    # Parse: trade_pct:{token_address}:{percent}:{grade}
    parts = data.split(":")
    if len(parts) < 4:
        await query.message.reply_text("❌ Invalid trade format", parse_mode=ParseMode.MARKDOWN)
        return

    token_address = parts[1]
    pct = float(parts[2])
    grade = parts[3]

    user_id = query.from_user.id

    # Double-check admin
    if user_id != ADMIN_USER_ID:
        await query.message.reply_text(
            "⛔ *Admin Only*\n\nUser ID does not match authorized admin.",
            parse_mode=ParseMode.MARKDOWN
        )
        logger.warning(f"Trade blocked: User {user_id} != Admin {ADMIN_USER_ID}")
        return

    # Reject low grades
    if grade in ['D', 'F']:
        await query.message.reply_text(
            f"⛔ *Trade Blocked*\n\nGrade {grade} is too risky to trade.",
            parse_mode=ParseMode.MARKDOWN
        )
        return

    try:
        engine = await _get_treasury_engine()
        _, portfolio_usd = await engine.get_portfolio_value()

        if portfolio_usd <= 0:
            await query.message.reply_text(
                "❌ *Error*\n\nTreasury balance is zero.",
                parse_mode=ParseMode.MARKDOWN
            )
            return

        # Calculate trade amount
        amount_usd = portfolio_usd * (pct / 100.0)

        # Get token info
        service = get_signal_service()
        signal = await service.get_comprehensive_signal(token_address, include_sentiment=False)

        if not signal:
            await query.message.reply_text("❌ Could not fetch token data", parse_mode=ParseMode.MARKDOWN)
            return

        # Get TP/SL from grade
        tp_pct, sl_pct = _get_tp_sl_for_grade(grade)

        # Update message to show executing
        await query.edit_message_text(
            f"⏳ *Executing Trade...*\n\n"
            f"Token: {signal.symbol}\n"
            f"Amount: ${amount_usd:.2f} ({pct}%)\n"
            f"TP: +{int(tp_pct*100)}% | SL: -{int(sl_pct*100)}%\n"
            f"Mode: {'🟢 LIVE' if not engine.dry_run else '🟡 PAPER'}",
            parse_mode=ParseMode.MARKDOWN
        )

        # Execute via trading engine
        from bots.treasury.trading import TradeDirection

        success, msg, position = await engine.open_position(
            token_mint=token_address,
            token_symbol=signal.symbol,
            direction=TradeDirection.LONG,
            amount_usd=amount_usd,
            sentiment_grade=grade,
            sentiment_score=signal.sentiment_score if hasattr(signal, 'sentiment_score') else 0,
            custom_tp=tp_pct,
            custom_sl=sl_pct,
            user_id=user_id,
        )

        if success and position:
            mode = "🟢 LIVE" if not engine.dry_run else "🟡 PAPER"
            result_msg = f"""
✅ *TRADE EXECUTED*

*Token:* {signal.symbol}
*Size:* {pct}% (~${amount_usd:.2f})
*Entry:* ${position.entry_price:.8f}
*Amount:* {position.amount:.4f} tokens

*Risk Controls:*
🎯 TP: ${position.take_profit_price:.8f} (+{int(tp_pct*100)}%)
🛑 SL: ${position.stop_loss_price:.8f} (-{int(sl_pct*100)}%)

*Mode:* {mode}
*Position ID:* `{position.id}`

_TP/SL orders active - monitoring price_
"""
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("📋 Positions", callback_data="show_positions_detail")],
                [InlineKeyboardButton("📊 Report", callback_data="refresh_report")],
            ])

            await query.edit_message_text(
                result_msg,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=keyboard
            )
        else:
            await query.edit_message_text(
                f"❌ *Trade Failed*\n\n{msg}",
                parse_mode=ParseMode.MARKDOWN
            )

    except Exception as e:
        logger.error(f"Trade execution failed: {e}")
        await query.edit_message_text(
            f"❌ *Trade Failed*\n\n{str(e)[:100]}",
            parse_mode=ParseMode.MARKDOWN
        )


async def _close_position_callback(query, position_id: str):
    """Close a position via callback. ADMIN ONLY."""
    try:
        engine = await _get_treasury_engine()
        success, msg = await engine.close_position(position_id, user_id=query.from_user.id)

        if success:
            await query.edit_message_text(
                f"✅ *Position Closed*\n\n{msg}",
                parse_mode=ParseMode.MARKDOWN
            )
        else:
            await query.edit_message_text(
                f"❌ *Close Failed*\n\n{msg}",
                parse_mode=ParseMode.MARKDOWN
            )

    except Exception as e:
        logger.error(f"Position close failed: {e}")
        await query.edit_message_text(
            f"❌ *Error*\n\n{str(e)[:100]}",
            parse_mode=ParseMode.MARKDOWN
        )


async def _refresh_report_inline(query):
    """Refresh the trading report inline."""
    await query.edit_message_text(
        "📊 _Refreshing report..._",
        parse_mode=ParseMode.MARKDOWN
    )

    service = get_signal_service()
    tracker = get_tracker()
    config = get_config()

    try:
        signals_list = await service.get_trending_tokens(limit=10)

        if not signals_list:
            await query.edit_message_text(
                "❌ Could not fetch signals",
                parse_mode=ParseMode.MARKDOWN
            )
            return

        # Add sentiment to top 3
        for i, sig in enumerate(signals_list[:3]):
            can_check, _ = tracker.can_make_sentiment_call()
            if can_check and config.has_grok():
                enhanced = await service.get_comprehensive_signal(
                    sig.address, symbol=sig.symbol, include_sentiment=True
                )
                signals_list[i] = enhanced

        try:
            engine = await _get_treasury_engine()
            _, portfolio_usd = await engine.get_portfolio_value()
            mode = "🟢 LIVE" if not engine.dry_run else "🟡 PAPER"
        except Exception:
            portfolio_usd = 0
            mode = "⚪ OFFLINE"

        message = _build_full_trading_report(signals_list, portfolio_usd, mode)

        keyboard_rows = []
        for sig in signals_list[:3]:
            grade = _grade_for_signal(sig)
            keyboard_rows.append([
                InlineKeyboardButton(f"📈 {sig.symbol} 1%", callback_data=f"trade_pct:{sig.address}:1:{grade}"),
                InlineKeyboardButton(f"📈 {sig.symbol} 2%", callback_data=f"trade_pct:{sig.address}:2:{grade}"),
                InlineKeyboardButton(f"📈 {sig.symbol} 5%", callback_data=f"trade_pct:{sig.address}:5:{grade}"),
            ])

        keyboard_rows.append([
            InlineKeyboardButton("🔄 Refresh", callback_data="refresh_report"),
            InlineKeyboardButton("💼 Positions", callback_data="show_positions_detail"),
        ])

        await query.edit_message_text(
            message,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup(keyboard_rows),
            disable_web_page_preview=True,
        )

    except Exception as e:
        logger.error(f"Report refresh failed: {e}")
        await query.edit_message_text(f"❌ Error: {str(e)[:100]}", parse_mode=ParseMode.MARKDOWN)


async def _refresh_balance_inline(query):
    """Refresh balance inline."""
    try:
        engine = await _get_treasury_engine()
        sol_balance, usd_value = await engine.get_portfolio_value()
        mode = "🟢 LIVE" if not engine.dry_run else "🟡 PAPER"

        treasury = engine.wallet.get_treasury()
        address = treasury.address if treasury else "Unknown"
        short_addr = f"{address[:8]}...{address[-4:]}" if address else "N/A"

        message = f"""
💰 *TREASURY BALANCE*

*Wallet:* `{short_addr}`
*SOL:* `{sol_balance:.4f}` SOL
*USD:* `${usd_value:,.2f}`

*Mode:* {mode}
"""
        if sol_balance < 0.05:
            message += "\n🚨 *WARNING: Low balance!*"

        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("🔄 Refresh", callback_data="refresh_balance"),
                InlineKeyboardButton("📊 Report", callback_data="refresh_report"),
            ]
        ])

        await query.edit_message_text(message, parse_mode=ParseMode.MARKDOWN, reply_markup=keyboard)

    except Exception as e:
        await query.edit_message_text(f"❌ Error: {str(e)[:100]}", parse_mode=ParseMode.MARKDOWN)


async def _show_positions_inline(query):
    """Show positions inline."""
    try:
        engine = await _get_treasury_engine()
        await engine.update_positions()
        open_positions = engine.get_open_positions()

        if not open_positions:
            await query.edit_message_text(
                "📋 *OPEN POSITIONS*\n\n_No open positions._",
                parse_mode=ParseMode.MARKDOWN
            )
            return

        lines = ["📋 *OPEN POSITIONS*", ""]
        keyboard_rows = []
        total_pnl = 0

        for pos in open_positions:
            pnl_pct = pos.unrealized_pnl_pct
            pnl_usd = pos.unrealized_pnl
            total_pnl += pnl_usd

            pnl_emoji = "🟢" if pnl_pct >= 0 else "🔴"
            lines.append(f"*{pos.token_symbol}* {pnl_emoji}")
            lines.append(f"   P&L: {pnl_pct:+.1f}% (${pnl_usd:+.2f})")
            lines.append(f"   TP: ${pos.take_profit_price:.8f}")
            lines.append(f"   SL: ${pos.stop_loss_price:.8f}")
            lines.append("")

            keyboard_rows.append([
                InlineKeyboardButton(f"🔴 SELL {pos.token_symbol}", callback_data=f"sell_pos:{pos.id}")
            ])

        total_emoji = "🟢" if total_pnl >= 0 else "🔴"
        lines.append(f"*Total P&L:* {total_emoji} ${total_pnl:+.2f}")

        keyboard_rows.append([
            InlineKeyboardButton("🔄 Refresh", callback_data="show_positions_detail"),
        ])

        await query.edit_message_text(
            "\n".join(lines),
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup(keyboard_rows)
        )

    except Exception as e:
        await query.edit_message_text(f"❌ Error: {str(e)[:100]}", parse_mode=ParseMode.MARKDOWN)


async def _toggle_live_mode(query):
    """Toggle between live and paper trading. ADMIN ONLY."""
    try:
        engine = await _get_treasury_engine()
        engine.dry_run = not engine.dry_run
        mode = "🟢 LIVE TRADING" if not engine.dry_run else "🟡 PAPER TRADING"

        await query.edit_message_text(
            f"✅ *Mode Changed*\n\nNow in: *{mode}*",
            parse_mode=ParseMode.MARKDOWN
        )

    except Exception as e:
        await query.edit_message_text(f"❌ Error: {str(e)[:100]}", parse_mode=ParseMode.MARKDOWN)


async def _handle_trending_inline(query):
    """Handle trending request from inline keyboard."""
    await query.message.reply_text(
        "_Fetching trending tokens..._",
        parse_mode=ParseMode.MARKDOWN,
    )

    config = get_config()
    service = get_signal_service()
    signals_list = await service.get_trending_tokens(limit=5)

    if not signals_list:
        await query.message.reply_text(
            fmt.format_error("Could not fetch trending tokens.", "Check /status for availability."),
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    lines = [
        "=" * 25,
        "*TRENDING TOKENS*",
        f"_{datetime.now(timezone.utc).strftime('%H:%M')} UTC_",
        "=" * 25,
        "",
    ]

    for i, sig in enumerate(signals_list, 1):
        emoji = fmt.SIGNAL_EMOJI.get(sig.signal, "")
        lines.append(f"*{i}. {sig.symbol}* {emoji}")
        lines.append(f"   {fmt.format_price(sig.price_usd)} ({fmt.format_change(sig.price_change_1h)})")
        lines.append(f"   Vol: {fmt.format_volume(sig.volume_24h)} | Liq: {fmt.format_volume(sig.liquidity_usd)}")
        lines.append("")

    # Add inline buttons for quick actions
    keyboard = []
    if config.is_admin(query.from_user.id):
        for sig in signals_list[:3]:
            keyboard.append([
                InlineKeyboardButton(f"Trade {sig.symbol} (1/2/5%)", callback_data=f"trade_{sig.address}")
            ])
        keyboard.append([
            InlineKeyboardButton(f"Analyze {signals_list[0].symbol}", callback_data=f"analyze_{signals_list[0].symbol}")
        ])

    keyboard.append([
        InlineKeyboardButton("Refresh", callback_data="refresh_trending"),
        InlineKeyboardButton("Menu", callback_data="menu_back"),
    ])

    await query.message.reply_text(
        "\n".join(lines),
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup(keyboard),
        disable_web_page_preview=True,
    )


async def _show_trade_ticket(query, token_address: str):
    """Show a Jupiter-style trade ticket with treasury sizing."""
    service = get_signal_service()

    try:
        signal = await service.get_comprehensive_signal(
            token_address,
            include_sentiment=False,
        )
    except Exception as e:
        logger.error(f"Trade ticket failed: {e}")
        await query.message.reply_text(
            fmt.format_error("Trade ticket failed", "Unable to load token data."),
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    if signal.is_honeypot or signal.risk_level == "critical":
        await query.message.reply_text(
            fmt.format_error("Trade blocked", "Token flagged as high risk."),
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    if signal.price_usd <= 0:
        await query.message.reply_text(
            fmt.format_error("Trade blocked", "Invalid token price."),
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    try:
        engine = await _get_treasury_engine()
        _, portfolio_usd = await engine.get_portfolio_value()
    except Exception as e:
        logger.error(f"Treasury engine unavailable: {e}")
        await query.message.reply_text(
            fmt.format_error("Trading not configured", str(e)),
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    if portfolio_usd <= 0:
        await query.message.reply_text(
            fmt.format_error("Trade blocked", "Treasury balance is zero."),
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    grade = _grade_for_signal(signal)
    tp_price, sl_price = engine.get_tp_sl_levels(signal.price_usd, grade)
    tp_pct = ((tp_price / signal.price_usd) - 1) * 100
    sl_pct = (1 - (sl_price / signal.price_usd)) * 100

    size_1 = portfolio_usd * 0.01
    size_2 = portfolio_usd * 0.02
    size_5 = portfolio_usd * 0.05

    mode = "DRY RUN" if engine.dry_run else "LIVE"

    lines = [
        "*JUPITER TRADE TICKET*",
        "",
        f"*{signal.symbol}*",
        f"`{signal.address}`",
        f"Price: {fmt.format_price(signal.price_usd)}",
        f"1h: {fmt.format_change(signal.price_change_1h)} | 24h: {fmt.format_change(signal.price_change_24h)}",
        f"Vol 24h: {fmt.format_volume(signal.volume_24h)} | Liq: {fmt.format_volume(signal.liquidity_usd)}",
        "",
        f"*Treasury Sizing* (total ~{fmt.format_price(portfolio_usd)})",
        f"1% ~ {fmt.format_price(size_1)} | 2% ~ {fmt.format_price(size_2)} | 5% ~ {fmt.format_price(size_5)}",
        "",
        f"*Risk Controls* (grade {grade})",
        f"TP: {fmt.format_price(tp_price)} (+{tp_pct:.0f}%)",
        f"SL: {fmt.format_price(sl_price)} (-{sl_pct:.0f}%)",
        "",
        f"*Mode:* {mode}",
        f"[Chart]({fmt.get_dexscreener_link(signal.address)})",
    ]

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("BUY 1%", callback_data=f"buy_1_{signal.address}"),
            InlineKeyboardButton("BUY 2%", callback_data=f"buy_2_{signal.address}"),
            InlineKeyboardButton("BUY 5%", callback_data=f"buy_5_{signal.address}"),
        ],
        [
            InlineKeyboardButton("Cancel", callback_data="menu_back"),
        ],
    ])

    await query.message.reply_text(
        "\n".join(lines),
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=keyboard,
        disable_web_page_preview=True,
    )


async def _execute_trade_percent(query, data: str):
    """Execute a trade as a percentage of treasury value."""
    parts = data.split("_", 2)
    if len(parts) != 3:
        await query.message.reply_text(
            fmt.format_error("Trade failed", "Invalid trade request."),
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    try:
        pct = float(parts[1])
    except ValueError:
        await query.message.reply_text(
            fmt.format_error("Trade failed", "Invalid size percent."),
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    token_address = parts[2]
    service = get_signal_service()

    try:
        signal = await service.get_comprehensive_signal(
            token_address,
            include_sentiment=False,
        )
    except Exception as e:
        logger.error(f"Trade execution failed: {e}")
        await query.message.reply_text(
            fmt.format_error("Trade failed", "Unable to load token data."),
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    if signal.is_honeypot or signal.risk_level == "critical":
        await query.message.reply_text(
            fmt.format_error("Trade blocked", "Token flagged as high risk."),
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    if signal.price_usd <= 0:
        await query.message.reply_text(
            fmt.format_error("Trade failed", "Invalid token price."),
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    try:
        engine = await _get_treasury_engine()
        _, portfolio_usd = await engine.get_portfolio_value()
    except Exception as e:
        logger.error(f"Treasury engine unavailable: {e}")
        await query.message.reply_text(
            fmt.format_error("Trading not configured", str(e)),
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    if portfolio_usd <= 0:
        await query.message.reply_text(
            fmt.format_error("Trade blocked", "Treasury balance is zero."),
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    amount_usd = portfolio_usd * (pct / 100.0)
    grade = _grade_for_signal(signal)

    try:
        from bots.treasury.trading import TradeDirection

        success, msg, position = await engine.open_position(
            token_mint=signal.address,
            token_symbol=signal.symbol,
            direction=TradeDirection.LONG,
            amount_usd=amount_usd,
            sentiment_grade=grade,
            sentiment_score=signal.sentiment_score,
            user_id=query.from_user.id,
        )
    except Exception as e:
        logger.error(f"Trade execution failed: {e}")
        await query.message.reply_text(
            fmt.format_error("Trade failed", "Execution error."),
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    if not success:
        await query.message.reply_text(
            fmt.format_error("Trade failed", msg),
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    tp_price, sl_price = engine.get_tp_sl_levels(signal.price_usd, grade)
    tp_pct = ((tp_price / signal.price_usd) - 1) * 100
    sl_pct = (1 - (sl_price / signal.price_usd)) * 100
    mode = "DRY RUN" if engine.dry_run else "LIVE"

    entry_price = position.entry_price if position else signal.price_usd
    amount_line = f"Amount: {position.amount:.4f}" if position else "Amount: n/a"

    lines = [
        "*TRADE EXECUTED*",
        "",
        f"Token: *{signal.symbol}*",
        f"Size: {pct:.0f}% (~{fmt.format_price(amount_usd)})",
        f"Entry: {fmt.format_price(entry_price)}",
        amount_line,
        "",
        f"TP: {fmt.format_price(tp_price)} (+{tp_pct:.0f}%)",
        f"SL: {fmt.format_price(sl_price)} (-{sl_pct:.0f}%)",
        "",
        f"Mode: {mode}",
    ]

    await query.edit_message_text(
        "\n".join(lines),
        parse_mode=ParseMode.MARKDOWN,
        disable_web_page_preview=True,
    )


async def _handle_status_inline(query):
    """Handle status request from inline keyboard."""
    config = get_config()
    service = get_signal_service()

    available = service.get_available_sources()
    missing = config.get_optional_missing()

    message = fmt.format_status(available, missing)

    keyboard = [[InlineKeyboardButton("🏠 Back to Menu", callback_data="menu_back")]]

    await query.message.reply_text(
        message,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


# =============================================================================
# Scheduled Tasks
# =============================================================================

async def scheduled_digest(context: ContextTypes.DEFAULT_TYPE):
    """
    Send scheduled hourly digest to all admins.

    Runs at configured hours (default: 8, 14, 20 UTC).
    Includes sentiment for top 3 tokens if rate limit allows.
    """
    config = get_config()

    if not config.admin_ids:
        logger.warning("No admin IDs configured for scheduled digest")
        return

    logger.info(f"Running scheduled digest for {len(config.admin_ids)} admins")

    service = get_signal_service()
    tracker = get_tracker()

    try:
        signals = await service.get_trending_tokens(limit=10)

        # Add sentiment to top 3 if rate limit allows
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

        title = f"Hourly Digest ({sentiment_added} with Grok)"
        message = fmt.format_hourly_digest(signals, title=title)

        # Send to all admins
        for admin_id in config.admin_ids:
            try:
                await context.bot.send_message(
                    chat_id=admin_id,
                    text=message,
                    parse_mode=ParseMode.MARKDOWN,
                    disable_web_page_preview=True,
                )
                logger.info(f"Sent digest to admin {admin_id}")
            except Exception as e:
                logger.error(f"Failed to send digest to {admin_id}: {e}")

    except Exception as e:
        logger.error(f"Scheduled digest failed: {e}")


# =============================================================================
# Error Handler
# =============================================================================

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Log errors without exposing sensitive info."""
    # Don't log full error which might contain API keys
    logger.error(f"Bot error: {type(context.error).__name__}")

    if update and update.effective_message:
        await update.effective_message.reply_text(
            "Something went wrong. Please try again.",
            parse_mode=ParseMode.MARKDOWN,
        )


# =============================================================================
# Main
# =============================================================================

def main():
    """Run the bot."""
    config = get_config()

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

    # Build application
    app = Application.builder().token(config.telegram_token).build()

    # Add handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(CommandHandler("costs", costs))
    app.add_handler(CommandHandler("trending", trending))
    app.add_handler(CommandHandler("signals", signals))
    app.add_handler(CommandHandler("analyze", analyze))
    app.add_handler(CommandHandler("digest", digest))
    app.add_handler(CommandHandler("reload", reload))
    app.add_handler(CommandHandler("brain", brain))
    app.add_handler(CommandHandler("paper", paper))

    # Treasury Trading Commands
    app.add_handler(CommandHandler("report", report))
    app.add_handler(CommandHandler("balance", balance))
    app.add_handler(CommandHandler("positions", positions))
    app.add_handler(CommandHandler("settings", settings))

    app.add_handler(CallbackQueryHandler(button_callback))

    # Welcome new members
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

    # Run
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
