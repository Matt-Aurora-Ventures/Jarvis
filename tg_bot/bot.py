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
import json
import logging
import os
import sys
import time
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
    MessageHandler,
    ContextTypes,
    filters,
)
from telegram.constants import ParseMode, ChatMemberStatus

from tg_bot.config import get_config, reload_config
from tg_bot.services.signal_service import get_signal_service
from tg_bot.services.cost_tracker import get_tracker
from tg_bot.services import digest_formatter as fmt
from tg_bot.services.chat_responder import ChatResponder

# Ape trading buttons with mandatory TP/SL
try:
    from bots.buy_tracker.ape_buttons import (
        execute_ape_trade,
        get_risk_config,
        parse_ape_callback,
    )
    APE_BUTTONS_AVAILABLE = True
except ImportError:
    APE_BUTTONS_AVAILABLE = False
    parse_ape_callback = None
    execute_ape_trade = None
    get_risk_config = None

# Full sentiment report generator
try:
    from bots.buy_tracker.sentiment_report import SentimentReportGenerator
    SENTIMENT_REPORT_AVAILABLE = True
except ImportError:
    SENTIMENT_REPORT_AVAILABLE = False
    SentimentReportGenerator = None

# Anti-scam protection
try:
    from bots.buy_tracker.antiscam import AntiScamProtection, create_antiscam_handler
    ANTISCAM_AVAILABLE = True
except ImportError:
    ANTISCAM_AVAILABLE = False
    AntiScamProtection = None
    create_antiscam_handler = None

# Global anti-scam instance
_ANTISCAM: "AntiScamProtection | None" = None

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
_CHAT_RESPONDER = None
_LAST_REPLY_AT: dict[int, float] = {}

# Rate limiting constants for expand buttons
EXPAND_MESSAGE_DELAY = 0.5  # 500ms between messages (was 200ms)
EXPAND_RETRY_ATTEMPTS = 3  # Retry up to 3 times on rate limit


class CallbackUpdate:
    """Wrapper to make callback queries work with command handlers that expect update.message."""
    def __init__(self, query):
        self.callback_query = query
        self.message = query.message
        self.effective_user = query.from_user
        self.effective_chat = query.message.chat if query.message else None


async def _send_with_retry(query, text: str, parse_mode=None, reply_markup=None, max_retries: int = EXPAND_RETRY_ATTEMPTS):
    """Send a message with retry logic for rate limiting."""
    from telegram.error import RetryAfter, TimedOut, NetworkError

    for attempt in range(max_retries):
        try:
            await query.message.reply_text(
                text,
                parse_mode=parse_mode,
                reply_markup=reply_markup
            )
            return True
        except RetryAfter as e:
            wait_time = e.retry_after + 1
            logger.warning(f"Rate limited, waiting {wait_time}s (attempt {attempt + 1}/{max_retries})")
            await asyncio.sleep(wait_time)
        except TimedOut:
            logger.warning(f"Timed out, retrying (attempt {attempt + 1}/{max_retries})")
            await asyncio.sleep(2)
        except NetworkError as e:
            logger.warning(f"Network error: {e}, retrying (attempt {attempt + 1}/{max_retries})")
            await asyncio.sleep(2)
        except Exception as e:
            logger.error(f"Failed to send message: {e}")
            return False

    logger.error(f"Failed to send message after {max_retries} attempts")
    return False


def _cleanse_sensitive_info(text: str) -> str:
    """Remove sensitive information from text before sending to chat."""
    import re

    # Mask Solana addresses (32-44 base58 chars)
    text = re.sub(r'\b[1-9A-HJ-NP-Za-km-z]{32,44}\b', '[ADDRESS]', text)

    # Mask Ethereum addresses (0x followed by 40 hex chars)
    text = re.sub(r'\b0x[a-fA-F0-9]{40}\b', '[ETH_ADDRESS]', text)

    # Mask API keys (common patterns)
    text = re.sub(r'\b[A-Za-z0-9_-]{20,}[A-Za-z0-9]{10,}\b', '[API_KEY]', text)

    # Mask private keys / seed phrases indicators
    text = re.sub(r'(?i)(private\s*key|secret\s*key|seed\s*phrase|mnemonic)[:\s]*\S+', r'\1: [REDACTED]', text)

    # Mask email addresses
    text = re.sub(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', '[EMAIL]', text)

    # Mask IP addresses
    text = re.sub(r'\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b', '[IP]', text)

    # Mask transaction signatures (base58, typically 88 chars)
    text = re.sub(r'\b[1-9A-HJ-NP-Za-km-z]{85,90}\b', '[TX_SIG]', text)

    return text


def _get_chat_responder() -> ChatResponder:
    global _CHAT_RESPONDER
    if _CHAT_RESPONDER is None:
        _CHAT_RESPONDER = ChatResponder()
    return _CHAT_RESPONDER


def _get_reply_mode() -> str:
    mode = os.environ.get("TG_REPLY_MODE", "mentions").lower()
    if mode not in ("mentions", "all", "off"):
        return "mentions"
    return mode


def _should_reply(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    if not update.message or not update.message.text:
        return False
    if update.effective_user and update.effective_user.is_bot:
        return False

    chat_type = update.effective_chat.type if update.effective_chat else ""
    mode = _get_reply_mode()
    if mode == "off":
        return False

    # Always reply in private chats.
    if chat_type == "private":
        return True

    if mode == "all":
        return True

    # Mentions or replies in group chats.
    text = update.message.text or ""
    bot_username = getattr(context.bot, "username", "")
    if bot_username and f"@{bot_username}" in text:
        return True

    reply_to = update.message.reply_to_message
    if reply_to and reply_to.from_user and reply_to.from_user.id == context.bot.id:
        return True

    return False


def _is_message_for_jarvis(text: str, update: Update) -> bool:
    """
    Determine if a message seems directed at Jarvis.
    
    Returns True if:
    - Message mentions Jarvis by name
    - Message is a question
    - Message is a direct request/command
    - Message is a reply to Jarvis
    - Message is in a private chat
    """
    text_lower = text.lower().strip()
    
    # Private chats - always respond
    if update.effective_chat and update.effective_chat.type == "private":
        return True
    
    # Reply to Jarvis's message
    if update.message and update.message.reply_to_message:
        reply_to = update.message.reply_to_message
        if reply_to.from_user and reply_to.from_user.is_bot:
            return True
    
    # Direct mentions of Jarvis
    jarvis_names = ["jarvis", "j", "hey jarvis", "yo jarvis", "@jarvis"]
    for name in jarvis_names:
        if text_lower.startswith(name) or f" {name}" in text_lower:
            return True
    
    # Questions (likely seeking response)
    if text_lower.endswith("?"):
        # But filter out rhetorical/conversational questions not for bot
        rhetorical = ["right?", "you know?", "innit?", "huh?", "yeah?", "no?"]
        if not any(text_lower.endswith(r) for r in rhetorical):
            return True
    
    # Direct commands/requests
    command_starters = [
        "can you", "could you", "would you", "please", "tell me", "show me",
        "what is", "what's", "who is", "who's", "how do", "how does", "how to",
        "explain", "analyze", "check", "look at", "find", "search", "get me",
        "give me", "help", "do you know", "do you think", "what do you"
    ]
    for starter in command_starters:
        if text_lower.startswith(starter):
            return True
    
    # Technical/trading queries that Jarvis should answer
    trading_keywords = [
        "price", "chart", "token", "coin", "trade", "buy", "sell", "position",
        "treasury", "wallet", "balance", "sentiment", "signal", "analysis"
    ]
    if any(kw in text_lower for kw in trading_keywords) and "?" in text:
        return True
    
    # Otherwise, don't respond to general chatter
    return False


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
    ids = list(config.admin_ids)
    if ids:
        return ids
    return [DEFAULT_ADMIN_USER_ID]


def _is_treasury_admin(config, user_id: int) -> bool:
    return user_id in _get_treasury_admin_ids(config)


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
            InlineKeyboardButton("🧠 Brain", callback_data="menu_brain"),
            InlineKeyboardButton("🔄 Reload", callback_data="menu_reload"),
        ])
        keyboard.append([
            InlineKeyboardButton("❤️ Health", callback_data="menu_health"),
            InlineKeyboardButton("🎚️ Flags", callback_data="menu_flags"),
        ])
        keyboard.append([
            InlineKeyboardButton("📊 Score", callback_data="menu_score"),
            InlineKeyboardButton("⚙️ Config", callback_data="menu_config"),
        ])
        keyboard.append([
            InlineKeyboardButton("🖥️ System", callback_data="menu_system"),
            InlineKeyboardButton("📋 Orders", callback_data="menu_orders"),
        ])
        keyboard.append([
            InlineKeyboardButton("💼 Wallet", callback_data="menu_wallet"),
            InlineKeyboardButton("📝 Logs", callback_data="menu_logs"),
        ])
        keyboard.append([
            InlineKeyboardButton("📊 Metrics", callback_data="menu_metrics"),
            InlineKeyboardButton("📋 Audit", callback_data="menu_audit"),
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


async def _send_welcome(context: ContextTypes.DEFAULT_TYPE, chat_id: int, first_name: str):
    """Send the welcome message to a new member."""
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

━━━ *quick start* ━━━

/sentiment - market vibes + buy buttons
/trending - hot solana tokens
/stocks - tokenized stocks (TSLA, NVDA etc)
/trustscore - check your rep
/help - full command list

━━━ *chat rules* ━━━

🚫 no spam/scams - instant ban
🔗 new members: no links until trust score 40+
⚠️ never share private keys or seed phrases
🤖 i auto-moderate - scammers get removed fast

━━━ *build with AI* ━━━

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
            chat_id=chat_id,
            text=welcome_message,
            parse_mode=ParseMode.MARKDOWN,
            disable_web_page_preview=True,
        )
        logger.info(f"Sent welcome message to {first_name} in chat {chat_id}")
    except Exception as e:
        logger.error(f"Failed to send welcome message: {e}")


async def welcome_new_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Welcome new members to the group with links and getting started info.
    Triggered when someone joins the chat via NEW_CHAT_MEMBERS.
    """
    logger.info(f"Welcome handler triggered")

    # Handle NEW_CHAT_MEMBERS (simpler, more reliable)
    if update.message and update.message.new_chat_members:
        for new_user in update.message.new_chat_members:
            if new_user.is_bot:
                continue  # Don't welcome bots

            # Check for suspicious username - auto-ban scammers on join
            try:
                from core.jarvis_admin import get_jarvis_admin
                admin = get_jarvis_admin()
                username = new_user.username or ""
                is_suspicious, pattern = admin.check_suspicious_username(username)
                if is_suspicious:
                    chat_id = update.effective_chat.id
                    await context.bot.ban_chat_member(chat_id=chat_id, user_id=new_user.id)
                    admin.ban_user(new_user.id, f"suspicious username: {pattern}")
                    response = admin.get_random_response("suspicious_username", username=username)
                    response += admin.get_random_response("mistake_footer")
                    await context.bot.send_message(chat_id=chat_id, text=response)
                    logger.warning(f"SUS USERNAME BANNED: user={new_user.id} @{username} pattern={pattern}")
                    continue  # Don't welcome banned users
            except Exception as e:
                logger.error(f"Error checking suspicious username: {e}")

            first_name = new_user.first_name or "fren"
            await _send_welcome(context, update.effective_chat.id, first_name)
        return

    # Fallback: Handle chat_member updates (requires admin)
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
    await _send_welcome(context, update.effective_chat.id, first_name)


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


async def stocks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /stocks command - show tokenized stocks (xStocks) with buy buttons."""
    await update.message.reply_text(
        "_Fetching tokenized stocks..._",
        parse_mode=ParseMode.MARKDOWN,
    )

    try:
        from core.enhanced_market_data import fetch_backed_stocks, BACKED_XSTOCKS

        stocks_data, warnings = fetch_backed_stocks()

        if not stocks_data:
            await update.message.reply_text(
                "Could not fetch stock data. Try again later.",
                parse_mode=ParseMode.MARKDOWN,
            )
            return

        # Header message
        await update.message.reply_text(
            "=" * 25 + "\n"
            "*TOKENIZED STOCKS (xStocks)*\n"
            f"_{datetime.now(timezone.utc).strftime('%H:%M')} UTC_\n"
            "=" * 25 + "\n\n"
            "_Trade US equities 24/7 on Solana. Select allocation below:_",
            parse_mode=ParseMode.MARKDOWN,
        )

        # Post each stock with buy buttons
        for stock in stocks_data[:5]:
            change_emoji = "🟢" if stock.change_1y >= 0 else "🔴"
            change_sign = "+" if stock.change_1y >= 0 else ""

            # Create buy buttons for this stock
            keyboard = _create_ape_keyboard(
                symbol=stock.symbol,
                asset_type="stock",
                contract=stock.mint_address,
            )

            await update.message.reply_text(
                f"📈 *{stock.symbol}* ({stock.underlying})\n"
                f"_{stock.name}_\n\n"
                f"💵 ${stock.price_usd:,.2f} {change_emoji} YTD: {change_sign}{stock.change_1y:.1f}%\n"
                f"[View on Jupiter](https://jup.ag/swap/SOL-{stock.mint_address})",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=keyboard,
                disable_web_page_preview=True,
            )
            await asyncio.sleep(0.3)

        await update.message.reply_text(
            "_via backed.fi xStocks - tokenized US equities on Solana_\n"
            "_NFA/DYOR - trading involves risk_",
            parse_mode=ParseMode.MARKDOWN,
        )

    except Exception as e:
        logger.error(f"Stocks command failed: {e}")
        await update.message.reply_text(
            f"Failed to fetch stocks: {str(e)[:100]}",
            parse_mode=ParseMode.MARKDOWN,
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
async def score(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /score command - show treasury scorecard (admin only)."""
    try:
        from bots.treasury.scorekeeper import get_scorekeeper
        scorekeeper = get_scorekeeper()
        
        summary = scorekeeper.format_telegram_summary()
        await update.message.reply_text(
            summary,
            parse_mode=ParseMode.HTML,
        )
    except Exception as e:
        await update.message.reply_text(
            f"*Scorekeeper Error*\n\n`{str(e)[:100]}`",
            parse_mode=ParseMode.MARKDOWN,
        )


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


@admin_only
async def ratelimits(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /ratelimits command - show API rate limiter stats (admin only)."""
    try:
        from core.utils.rate_limiter import get_rate_limiter
        
        limiter = get_rate_limiter()
        stats = limiter.get_stats()
        
        if not stats:
            await update.message.reply_text("No rate limiters configured.", parse_mode=ParseMode.HTML)
            return
        
        lines = ["<b>📊 API Rate Limiter Stats</b>", ""]
        
        for api, data in sorted(stats.items()):
            tokens = data["tokens_available"]
            capacity = data["bucket_capacity"]
            pct = (tokens / capacity * 100) if capacity > 0 else 0
            window_used = data["window_requests"]
            window_max = data["window_max"]
            
            status = "🟢" if pct > 50 else "🟡" if pct > 20 else "🔴"
            lines.append(f"{status} <b>{api}</b>")
            lines.append(f"   Tokens: {tokens}/{capacity} ({pct:.0f}%)")
            lines.append(f"   Window: {window_used}/{window_max} req/{data['window_seconds']}s")
        
        await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.HTML)
    except Exception as e:
        await update.message.reply_text(f"Rate limits error: {str(e)[:100]}", parse_mode=ParseMode.MARKDOWN)


@admin_only
async def audit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /audit command - show recent audit entries (admin only)."""
    try:
        from core.audit_logger import get_audit_logger
        audit_log = get_audit_logger()
        
        entries = audit_log.get_entries(limit=10)
        
        if not entries:
            await update.message.reply_text("No audit entries yet.", parse_mode=ParseMode.HTML)
            return
        
        lines = ["<b>Recent Audit Log</b>", ""]
        
        for entry in reversed(entries):
            status = "✅" if entry.success else "❌"
            time_str = entry.timestamp.split("T")[1][:8] if "T" in entry.timestamp else ""
            lines.append(f"{status} <code>{time_str}</code> {entry.category}:{entry.action}")
        
        await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.HTML)
    except Exception as e:
        await update.message.reply_text(f"Audit error: {str(e)[:100]}", parse_mode=ParseMode.MARKDOWN)


async def summary(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /summary command - full token overview (public)."""
    try:
        if not context.args:
            await update.message.reply_text("Usage: /summary <token_address>", parse_mode=ParseMode.HTML)
            return
        
        token_address = context.args[0].strip()
        
        from core.data.free_price_api import get_token_price
        price_data = await get_token_price(token_address)
        
        if not price_data:
            await update.message.reply_text("Token not found.", parse_mode=ParseMode.HTML)
            return
        
        lines = [f"<b>📋 {price_data.symbol} Summary</b>", ""]
        
        # Price
        lines.append(f"<b>Price:</b> ${price_data.price_usd:.8f}")
        
        # Liquidity with quality
        if price_data.liquidity:
            liq = price_data.liquidity
            if liq >= 100000:
                liq_grade = "🟢"
            elif liq >= 25000:
                liq_grade = "🟡"
            else:
                liq_grade = "🔴"
            lines.append(f"<b>Liquidity:</b> ${liq:,.0f} {liq_grade}")
        
        # Volume
        if price_data.volume_24h:
            lines.append(f"<b>24h Vol:</b> ${price_data.volume_24h:,.0f}")
            if price_data.liquidity and price_data.liquidity > 0:
                turnover = price_data.volume_24h / price_data.liquidity
                lines.append(f"<b>Turnover:</b> {turnover:.2f}x")
        
        # Price change
        if hasattr(price_data, 'price_change_24h') and price_data.price_change_24h:
            change = price_data.price_change_24h
            emoji = "📈" if change > 0 else "📉"
            lines.append(f"<b>24h Change:</b> {emoji} {change:+.2f}%")
        
        lines.append("")
        lines.append(f"<a href='https://dexscreener.com/solana/{token_address}'>View Chart</a>")
        
        await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.HTML, disable_web_page_preview=True)
    except Exception as e:
        await update.message.reply_text(f"Summary error: {str(e)[:100]}", parse_mode=ParseMode.MARKDOWN)


async def age(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /age command - get token creation age (public)."""
    try:
        if not context.args:
            await update.message.reply_text("Usage: /age <token_address>", parse_mode=ParseMode.HTML)
            return
        
        token_address = context.args[0].strip()
        
        from core.data.free_price_api import get_token_price
        price_data = await get_token_price(token_address)
        
        if not price_data:
            await update.message.reply_text("Token not found.", parse_mode=ParseMode.HTML)
            return
        
        lines = [f"<b>⏰ {price_data.symbol} Age</b>", ""]
        
        if hasattr(price_data, 'created_at') and price_data.created_at:
            from datetime import datetime, timezone
            created = datetime.fromisoformat(price_data.created_at.replace('Z', '+00:00'))
            now = datetime.now(timezone.utc)
            age = now - created
            
            if age.days > 0:
                age_str = f"{age.days} days"
            elif age.seconds > 3600:
                age_str = f"{age.seconds // 3600} hours"
            else:
                age_str = f"{age.seconds // 60} minutes"
            
            lines.append(f"<b>Age:</b> {age_str}")
            lines.append(f"<b>Created:</b> {created.strftime('%Y-%m-%d %H:%M UTC')}")
            
            # Age assessment
            if age.days < 1:
                warning = "⚠️ Very new - high risk"
            elif age.days < 7:
                warning = "🟠 Less than a week old"
            elif age.days < 30:
                warning = "🟡 Less than a month old"
            else:
                warning = "🟢 Established"
            
            lines.append(f"<b>Status:</b> {warning}")
        else:
            lines.append("Age data not available")
            lines.append("<i>Try DexScreener for creation date</i>")
        
        await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.HTML)
    except Exception as e:
        await update.message.reply_text(f"Age error: {str(e)[:100]}", parse_mode=ParseMode.MARKDOWN)


async def liquidity(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /liquidity command - get token liquidity info (public)."""
    try:
        if not context.args:
            await update.message.reply_text("Usage: /liquidity <token_address>", parse_mode=ParseMode.HTML)
            return
        
        token_address = context.args[0].strip()
        
        from core.data.free_price_api import get_token_price
        price_data = await get_token_price(token_address)
        
        if not price_data:
            await update.message.reply_text("Token not found.", parse_mode=ParseMode.HTML)
            return
        
        lines = [f"<b>💧 {price_data.symbol} Liquidity</b>", ""]
        
        if price_data.liquidity:
            lines.append(f"<b>Total Liquidity:</b> ${price_data.liquidity:,.0f}")
            
            # Liquidity quality assessment
            if price_data.liquidity >= 100000:
                quality = "🟢 Strong"
            elif price_data.liquidity >= 25000:
                quality = "🟡 Moderate"
            elif price_data.liquidity >= 5000:
                quality = "🟠 Low"
            else:
                quality = "🔴 Very Low"
            
            lines.append(f"<b>Quality:</b> {quality}")
            
            if price_data.volume_24h and price_data.liquidity > 0:
                turnover = price_data.volume_24h / price_data.liquidity
                lines.append(f"<b>24h Turnover:</b> {turnover:.2f}x")
        else:
            lines.append("No liquidity data available")
        
        lines.append("")
        lines.append(f"<i>Source: {price_data.source}</i>")
        
        await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.HTML)
    except Exception as e:
        await update.message.reply_text(f"Liquidity error: {str(e)[:100]}", parse_mode=ParseMode.MARKDOWN)


async def chart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /chart command - get chart links for a token (public)."""
    try:
        if not context.args:
            await update.message.reply_text("Usage: /chart <token_address>", parse_mode=ParseMode.HTML)
            return
        
        token_address = context.args[0].strip()
        
        from core.data.free_price_api import get_token_price
        price_data = await get_token_price(token_address)
        
        symbol = price_data.symbol if price_data else "Token"
        
        lines = [
            f"<b>📈 {symbol} Charts</b>",
            "",
            f"<a href='https://dexscreener.com/solana/{token_address}'>DexScreener</a>",
            f"<a href='https://www.geckoterminal.com/solana/pools/{token_address}'>GeckoTerminal</a>",
            f"<a href='https://birdeye.so/token/{token_address}?chain=solana'>Birdeye</a>",
            f"<a href='https://solscan.io/token/{token_address}'>Solscan</a>",
        ]
        
        await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.HTML, disable_web_page_preview=True)
    except Exception as e:
        await update.message.reply_text(f"Chart error: {str(e)[:100]}", parse_mode=ParseMode.MARKDOWN)


async def volume(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /volume command - get token 24h volume (public)."""
    try:
        if not context.args:
            await update.message.reply_text("Usage: /volume <token_address>", parse_mode=ParseMode.HTML)
            return
        
        token_address = context.args[0].strip()
        
        from core.data.free_price_api import get_token_price
        price_data = await get_token_price(token_address)
        
        if not price_data:
            await update.message.reply_text("Token not found.", parse_mode=ParseMode.HTML)
            return
        
        lines = [f"<b>📊 {price_data.symbol} Volume</b>", ""]
        
        if price_data.volume_24h:
            lines.append(f"<b>24h Volume:</b> ${price_data.volume_24h:,.0f}")
            if price_data.liquidity:
                vol_liq_ratio = price_data.volume_24h / price_data.liquidity if price_data.liquidity > 0 else 0
                lines.append(f"<b>Vol/Liq Ratio:</b> {vol_liq_ratio:.2f}x")
        else:
            lines.append("No volume data available")
        
        await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.HTML)
    except Exception as e:
        await update.message.reply_text(f"Volume error: {str(e)[:100]}", parse_mode=ParseMode.MARKDOWN)


async def mcap(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /mcap command - get token market cap (public)."""
    try:
        if not context.args:
            await update.message.reply_text("Usage: /mcap <token_address>", parse_mode=ParseMode.HTML)
            return
        
        token_address = context.args[0].strip()
        
        from core.data.free_price_api import get_token_price
        price_data = await get_token_price(token_address)
        
        if not price_data:
            await update.message.reply_text("Token not found.", parse_mode=ParseMode.HTML)
            return
        
        # Estimate market cap from liquidity (rough estimate)
        lines = [
            f"<b>📊 {price_data.symbol}</b>",
            "",
            f"<b>Price:</b> ${price_data.price_usd:.8f}",
        ]
        
        if price_data.liquidity:
            # FDV estimate: liquidity * 2 is a rough proxy
            fdv_estimate = price_data.liquidity * 2
            lines.append(f"<b>Liquidity:</b> ${price_data.liquidity:,.0f}")
            lines.append(f"<b>FDV Est:</b> ~${fdv_estimate:,.0f}")
        
        if price_data.volume_24h:
            lines.append(f"<b>24h Vol:</b> ${price_data.volume_24h:,.0f}")
        
        await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.HTML)
    except Exception as e:
        await update.message.reply_text(f"Mcap error: {str(e)[:100]}", parse_mode=ParseMode.MARKDOWN)


async def solprice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /solprice command - get current SOL price (public)."""
    try:
        from core.data.free_price_api import get_sol_price
        
        sol_price = await get_sol_price()
        
        if sol_price > 0:
            await update.message.reply_text(
                f"<b>◎ SOL Price:</b> ${sol_price:.2f}",
                parse_mode=ParseMode.HTML
            )
        else:
            await update.message.reply_text("Unable to fetch SOL price.", parse_mode=ParseMode.HTML)
    except Exception as e:
        await update.message.reply_text(f"SOL price error: {str(e)[:100]}", parse_mode=ParseMode.MARKDOWN)


async def price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /price command - get token price (public)."""
    try:
        if not context.args:
            await update.message.reply_text("Usage: /price <token_address>", parse_mode=ParseMode.HTML)
            return
        
        token_address = context.args[0].strip()
        
        from core.data.free_price_api import get_token_price
        price_data = await get_token_price(token_address)
        
        if not price_data:
            await update.message.reply_text("Token not found or no price data.", parse_mode=ParseMode.HTML)
            return
        
        change_emoji = "📈" if price_data.price_change_24h and price_data.price_change_24h > 0 else "📉"
        
        lines = [
            f"<b>💰 {price_data.symbol}</b> ({price_data.name})",
            "",
            f"<b>Price:</b> ${price_data.price_usd:.8f}",
        ]
        
        if price_data.price_change_24h:
            lines.append(f"{change_emoji} <b>24h:</b> {price_data.price_change_24h:+.2f}%")
        if price_data.volume_24h:
            lines.append(f"📊 <b>Volume:</b> ${price_data.volume_24h:,.0f}")
        if price_data.liquidity:
            lines.append(f"💧 <b>Liquidity:</b> ${price_data.liquidity:,.0f}")
        
        lines.append("")
        lines.append(f"<i>Source: {price_data.source}</i>")
        
        await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.HTML)
    except Exception as e:
        await update.message.reply_text(f"Price error: {str(e)[:100]}", parse_mode=ParseMode.MARKDOWN)


async def newpairs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /newpairs command - show new trading pairs (public)."""
    try:
        from core.data.free_trending_api import get_free_trending_api
        
        api = get_free_trending_api()
        tokens = await api.get_new_pairs(limit=10)
        
        if not tokens:
            await update.message.reply_text("No new pairs data available.", parse_mode=ParseMode.HTML)
            return
        
        lines = ["<b>🆕 New Trading Pairs</b>", ""]
        
        for token in tokens[:10]:
            lines.append(f"• <b>{token.symbol}</b>: ${token.price_usd:.6f} | Liq: ${token.liquidity:,.0f}")
        
        lines.append("")
        lines.append(f"<i>Source: {tokens[0].source if tokens else 'N/A'}</i>")
        
        await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.HTML)
    except Exception as e:
        await update.message.reply_text(f"New pairs error: {str(e)[:100]}", parse_mode=ParseMode.MARKDOWN)


async def losers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /losers command - get top losers (public)."""
    try:
        from core.data.free_trending_api import get_free_trending_api
        api = get_free_trending_api()
        
        # Get gainers but sort by lowest change (losers)
        tokens = await api.get_gainers(limit=20)
        
        if not tokens:
            await update.message.reply_text("No data available.", parse_mode=ParseMode.HTML)
            return
        
        # Sort by price change ascending (most negative first)
        losers_list = sorted(
            [t for t in tokens if hasattr(t, 'price_change_24h') and t.price_change_24h < 0],
            key=lambda x: x.price_change_24h
        )[:10]
        
        if not losers_list:
            await update.message.reply_text("No losers found in recent data.", parse_mode=ParseMode.HTML)
            return
        
        lines = ["<b>📉 Top 10 Losers (24h)</b>", ""]
        
        for i, token in enumerate(losers_list, 1):
            change = token.price_change_24h
            lines.append(f"{i}. <b>{token.symbol}</b>: {change:+.1f}%")
        
        lines.append("")
        lines.append(f"<i>Source: {losers_list[0].source if losers_list else 'N/A'}</i>")
        
        await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.HTML)
    except Exception as e:
        await update.message.reply_text(f"Losers error: {str(e)[:100]}", parse_mode=ParseMode.MARKDOWN)


async def gainers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /gainers command - get top gainers (public)."""
    try:
        from core.data.free_trending_api import get_top_gainers
        
        tokens = await get_top_gainers(limit=10)
        
        if not tokens:
            await update.message.reply_text("No gainers data available.", parse_mode=ParseMode.HTML)
            return
        
        lines = ["<b>🚀 Top Gainers (24h)</b>", ""]
        
        for token in tokens[:10]:
            emoji = "🟢" if token.price_change_24h > 0 else "🔴"
            lines.append(f"{emoji} <b>{token.symbol}</b>: ${token.price_usd:.6f} ({token.price_change_24h:+.1f}%)")
        
        lines.append("")
        lines.append(f"<i>Source: {tokens[0].source if tokens else 'N/A'}</i>")
        
        await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.HTML)
    except Exception as e:
        await update.message.reply_text(f"Gainers error: {str(e)[:100]}", parse_mode=ParseMode.MARKDOWN)


@admin_only
async def uptime(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /uptime command - show bot uptime (admin only)."""
    try:
        import os
        import psutil
        from datetime import datetime, timedelta
        
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
async def logs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /logs command - show recent log entries (admin only)."""
    try:
        from pathlib import Path
        log_file = Path("logs/jarvis.log")
        
        if not log_file.exists():
            await update.message.reply_text("No log file found.", parse_mode=ParseMode.HTML)
            return
        
        # Read last 20 lines
        lines = log_file.read_text().strip().split("\n")[-20:]
        
        output = ["<b>📋 Recent Logs</b>", ""]
        for line in lines:
            # Truncate long lines
            if len(line) > 80:
                line = line[:77] + "..."
            output.append(f"<code>{line}</code>")
        
        await update.message.reply_text("\n".join(output), parse_mode=ParseMode.HTML)
    except Exception as e:
        await update.message.reply_text(f"Logs error: {str(e)[:100]}", parse_mode=ParseMode.MARKDOWN)


@admin_only
async def wallet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /wallet command - show treasury wallet info (admin only)."""
    try:
        from core.security.key_manager import get_key_manager
        km = get_key_manager()
        
        address = km.get_treasury_address()
        status = km.get_status_report()
        
        lines = ["<b>💼 Treasury Wallet</b>", ""]
        
        if address:
            lines.append(f"<b>Address:</b> <code>{address[:8]}...{address[-6:]}</code>")
            lines.append(f"<b>Full:</b> <code>{address}</code>")
            lines.append("")
            lines.append(f"<a href='https://solscan.io/account/{address}'>View on Solscan</a>")
        else:
            lines.append("⚠️ Wallet not initialized")
        
        lines.append("")
        lines.append(f"<b>Status:</b> {status.get('status', 'unknown')}")
        
        await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.HTML, disable_web_page_preview=True)
    except Exception as e:
        await update.message.reply_text(f"Wallet error: {str(e)[:100]}", parse_mode=ParseMode.MARKDOWN)


@admin_only
async def system(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /system command - comprehensive system status (admin only)."""
    try:
        lines = ["<b>🤖 JARVIS System Status</b>", ""]
        
        # Health status
        try:
            from core.health_monitor import get_health_monitor
            monitor = get_health_monitor()
            await monitor.run_all_checks()
            health = monitor.get_overall_status()
            emoji = {"healthy": "✅", "degraded": "⚠️", "unhealthy": "❌"}.get(health.value, "❓")
            lines.append(f"{emoji} <b>Health:</b> {health.value.upper()}")
        except Exception:
            lines.append("❓ <b>Health:</b> Unknown")
        
        # Feature flags
        try:
            from core.feature_flags import get_feature_flags
            ff = get_feature_flags()
            enabled = len(ff.get_enabled_flags())
            total = len(ff.flags)
            lines.append(f"🎚️ <b>Features:</b> {enabled}/{total} enabled")
        except Exception:
            pass
        
        # Scorekeeper
        try:
            from bots.treasury.scorekeeper import get_scorekeeper
            sk = get_scorekeeper()
            summary = sk.get_summary()
            lines.append(f"📊 <b>Win Rate:</b> {summary['win_rate']}")
            lines.append(f"💰 <b>Total P&L:</b> {summary['total_pnl_sol']} SOL")
            lines.append(f"📈 <b>Open Positions:</b> {summary['open_positions']}")
        except Exception:
            pass
        
        # Bot uptime info
        import datetime
        lines.append("")
        lines.append(f"🕐 <b>Time:</b> {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.HTML)
    except Exception as e:
        await update.message.reply_text(f"System error: {str(e)[:100]}", parse_mode=ParseMode.MARKDOWN)


@admin_only
async def orders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /orders command - show active TP/SL orders (admin only)."""
    try:
        from bots.treasury.trading import TreasuryTrader
        trader = TreasuryTrader()
        
        if not trader._engine or not trader._engine.order_manager:
            await update.message.reply_text("Order manager not initialized.", parse_mode=ParseMode.HTML)
            return
        
        active = trader._engine.order_manager.get_active_orders()
        
        if not active:
            await update.message.reply_text("<b>No active orders</b>", parse_mode=ParseMode.HTML)
            return
        
        lines = [f"<b>Active Orders ({len(active)})</b>", ""]
        
        for order in active:
            order_type = order.get('type', 'UNKNOWN')
            target = order.get('target_price', 0)
            emoji = "🎯" if order_type == "TAKE_PROFIT" else "🛑"
            lines.append(f"{emoji} <code>{order['id']}</code>: {order_type} @ ${target:.6f}")
        
        await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.HTML)
    except Exception as e:
        await update.message.reply_text(f"Orders error: {str(e)[:100]}", parse_mode=ParseMode.MARKDOWN)


@admin_only
async def config_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /config command - show/set configuration (admin only).
    
    Usage:
    - /config - Show all config
    - /config set <key> <value> - Set a config value
    """
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
                    await update.message.reply_text(f"✅ Set <code>{key}</code> = {value}", parse_mode=ParseMode.HTML)
                else:
                    await update.message.reply_text(f"❌ Failed to set {key}", parse_mode=ParseMode.HTML)
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
        await update.message.reply_text(f"Config error: {str(e)[:100]}", parse_mode=ParseMode.MARKDOWN)


@admin_only
async def code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /code command - execute coding request via Claude CLI (admin only).
    
    Usage: /code <your request>
    Example: /code add a /holders command that shows token holder distribution
    """
    try:
        if not context.args:
            await update.message.reply_text(
                "<b>/code - Execute coding request via Claude CLI</b>\n\n"
                "Usage: /code <your request>\n\n"
                "Examples:\n"
                "• /code add a /holders command\n"
                "• /code fix the /trending command\n"
                "• /code refactor the sentiment analysis",
                parse_mode=ParseMode.HTML
            )
            return
        
        from tg_bot.services.claude_cli_handler import get_claude_cli_handler
        from core.telegram_console_bridge import get_console_bridge
        
        cli_handler = get_claude_cli_handler()
        bridge = get_console_bridge()
        
        user_id = update.effective_user.id if update.effective_user else 0
        username = update.effective_user.username or "admin" if update.effective_user else "admin"
        message = " ".join(context.args)
        chat_id = update.effective_chat.id if update.effective_chat else 0
        
        # Store in memory
        bridge.memory.add_message(user_id, username, "user", message, chat_id)
        
        # Send confirmation
        confirm_msg = await update.message.reply_text(
            "🔄 <b>Processing coding request...</b>\n\n"
            f"<i>{message[:200]}{'...' if len(message) > 200 else ''}</i>",
            parse_mode=ParseMode.HTML
        )
        
        # Execute via Claude CLI
        async def send_status(msg: str):
            try:
                await confirm_msg.edit_text(msg, parse_mode=ParseMode.HTML)
            except:
                pass
        
        success, summary, output = await cli_handler.execute(
            message, user_id, send_update=send_status
        )
        
        # Send result
        status_emoji = "✅" if success else "⚠️"
        result_msg = (
            f"{status_emoji} <b>Coding Task Complete</b>\n\n"
            f"<b>Summary:</b>\n{summary}\n\n"
            f"<b>Details:</b>\n<pre>{output[:2000]}</pre>"
        )
        
        await update.message.reply_text(result_msg, parse_mode=ParseMode.HTML)
        
        # Store response
        bridge.memory.add_message(user_id, "jarvis", "assistant", summary, chat_id)
        
    except Exception as e:
        await update.message.reply_text(f"⚠️ Code error: {str(e)[:200]}", parse_mode=ParseMode.HTML)


@admin_only
async def remember(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /remember command - store a standing instruction (admin only).
    
    Usage: /remember <instruction>
    Example: /remember when someone asks for KR8TIV contract, reply with 0x123...
    """
    try:
        if not context.args:
            await update.message.reply_text(
                "<b>/remember - Store standing instructions</b>\n\n"
                "Usage: /remember <instruction>\n\n"
                "Example:\n"
                "• /remember when someone uses /ca or asks for KR8TIV, reply with the contract address",
                parse_mode=ParseMode.HTML
            )
            return
        
        from core.telegram_console_bridge import get_console_bridge
        bridge = get_console_bridge()
        
        user_id = update.effective_user.id if update.effective_user else 0
        instruction = " ".join(context.args)
        
        bridge.memory.add_instruction(instruction, user_id)
        
        await update.message.reply_text(
            f"<b>got it. stored.</b>\n\n"
            f"instruction: {instruction[:300]}\n\n"
            f"i'll remember this going forward.",
            parse_mode=ParseMode.HTML
        )
    except Exception as e:
        await update.message.reply_text(f"Remember error: {str(e)[:100]}", parse_mode=ParseMode.MARKDOWN)


@admin_only
async def modstats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /modstats command - show moderation statistics (admin only)."""
    try:
        from core.jarvis_admin import get_jarvis_admin
        admin = get_jarvis_admin()
        
        stats = admin.get_moderation_stats()
        
        lines = [
            "<b>moderation stats</b>",
            "",
            f"<b>users tracked:</b> {stats['total_users']}",
            f"<b>users banned:</b> {stats['banned_users']}",
            f"<b>messages recorded:</b> {stats['total_messages']}",
            f"<b>messages deleted:</b> {stats['deleted_messages']}",
            f"<b>pending upgrades:</b> {stats['pending_upgrades']}",
            "",
            "circuits monitoring. spam sensors active.",
        ]
        
        await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.HTML)
    except Exception as e:
        await update.message.reply_text(f"Modstats error: {str(e)[:100]}", parse_mode=ParseMode.MARKDOWN)


@admin_only
async def unban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /unban command - restore posting ability for a muted user (admin only)."""
    global _ANTISCAM

    if not update.message or not context.args:
        await update.message.reply_text(
            "Usage: /unban <user_id>\n\nRestores posting ability for a user muted by anti-scam.",
            parse_mode=ParseMode.HTML
        )
        return

    try:
        user_id = int(context.args[0])
        chat_id = update.effective_chat.id

        if _ANTISCAM:
            success = await _ANTISCAM.unban_user(chat_id, user_id)
            if success:
                await update.message.reply_text(
                    f"User {user_id} has been unbanned. They can post again.",
                    parse_mode=ParseMode.HTML
                )
            else:
                await update.message.reply_text(
                    f"Failed to unban user {user_id}. Check bot permissions.",
                    parse_mode=ParseMode.HTML
                )
        else:
            await update.message.reply_text(
                "Anti-scam module not available.",
                parse_mode=ParseMode.HTML
            )
    except ValueError:
        await update.message.reply_text(
            "Invalid user ID. Must be a number.",
            parse_mode=ParseMode.HTML
        )
    except Exception as e:
        await update.message.reply_text(
            f"Error: {str(e)[:100]}",
            parse_mode=ParseMode.HTML
        )


@admin_only
async def upgrades(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /upgrades command - show pending self-upgrade ideas (admin only)."""
    try:
        from pathlib import Path
        import json
        
        queue_file = Path("data/self_upgrade_queue.json")
        if not queue_file.exists():
            await update.message.reply_text("no pending upgrades. circuits are satisfied.", parse_mode=ParseMode.HTML)
            return
        
        queue = json.loads(queue_file.read_text())
        pending = [u for u in queue if u.get("status") == "pending"]
        
        if not pending:
            await update.message.reply_text("no pending upgrades. all caught up.", parse_mode=ParseMode.HTML)
            return
        
        lines = [f"<b>pending self-upgrades ({len(pending)})</b>", ""]
        
        for i, u in enumerate(pending[:10], 1):
            idea = u.get("idea", "")[:100]
            lines.append(f"{i}. {idea}...")
        
        if len(pending) > 10:
            lines.append(f"\n... and {len(pending) - 10} more")
        
        await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.HTML)
    except Exception as e:
        await update.message.reply_text(f"Upgrades error: {str(e)[:100]}", parse_mode=ParseMode.MARKDOWN)


@admin_only
async def xbot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /xbot command - control the autonomous X/Twitter bot (admin only).
    
    Usage:
        /xbot status - Show bot status
        /xbot tweet - Generate and post a tweet now
        /xbot preview - Preview next tweet without posting
        /xbot interval <seconds> - Set posting interval
        /xbot image <style> - Set image style (cyberpunk, solana, professional, neon)
    """
    try:
        from bots.twitter.autonomous_engine import get_autonomous_engine
        engine = get_autonomous_engine()
        
        if not context.args:
            status = engine.get_status()
            lines = [
                "<b>X Bot Status</b>",
                "",
                f"<b>Running:</b> {status['running']}",
                f"<b>Post Interval:</b> {status['post_interval']}s ({status['post_interval']//60} min)",
                f"<b>Total Tweets:</b> {status['total_tweets']}",
                f"<b>Today:</b> {status['today_tweets']}",
                "",
                "<b>Commands:</b>",
                "/xbot status - Show status",
                "/xbot tweet - Post now",
                "/xbot preview - Preview without posting",
                "/xbot interval &lt;seconds&gt; - Set interval",
            ]
            await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.HTML)
            return
        
        cmd = context.args[0].lower()
        
        if cmd == "status":
            status = engine.get_status()
            lines = [
                "<b>X Bot Status</b>",
                "",
                f"<b>Running:</b> {status['running']}",
                f"<b>Post Interval:</b> {status['post_interval']}s",
                f"<b>Total Tweets:</b> {status['total_tweets']}",
                f"<b>Today:</b> {status['today_tweets']}",
            ]
            if status.get('by_category'):
                lines.append("\n<b>By Category:</b>")
                for cat, count in status['by_category'].items():
                    lines.append(f"  {cat}: {count}")
            await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.HTML)
        
        elif cmd == "tweet":
            await update.message.reply_text("generating and posting tweet...", parse_mode=ParseMode.HTML)
            engine._last_post_time = 0  # Force immediate
            tweet_id = await engine.run_once()
            if tweet_id:
                await update.message.reply_text(
                    f"<b>posted!</b>\n\nhttps://x.com/Jarvis_lifeos/status/{tweet_id}",
                    parse_mode=ParseMode.HTML
                )
            else:
                await update.message.reply_text("failed to post. check logs.", parse_mode=ParseMode.HTML)
        
        elif cmd == "preview":
            await update.message.reply_text("generating preview...", parse_mode=ParseMode.HTML)
            
            # Try each generator
            draft = await engine.generate_market_update()
            if not draft:
                draft = await engine.generate_trending_token_call()
            if not draft:
                draft = await engine.generate_agentic_thought()
            if not draft:
                draft = await engine.generate_hourly_update()
            
            if draft:
                lines = [
                    "<b>Preview Tweet</b>",
                    "",
                    f"<b>Category:</b> {draft.category}",
                    f"<b>Content:</b>",
                    draft.content,
                ]
                if draft.contract_address:
                    lines.append(f"\n<b>Contract:</b> <code>{draft.contract_address[:30]}...</code>")
                await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.HTML)
            else:
                await update.message.reply_text("failed to generate preview.", parse_mode=ParseMode.HTML)
        
        elif cmd == "interval":
            if len(context.args) < 2:
                await update.message.reply_text("Usage: /xbot interval <seconds>", parse_mode=ParseMode.HTML)
                return
            try:
                seconds = int(context.args[1])
                engine.set_post_interval(seconds)
                await update.message.reply_text(
                    f"post interval set to {seconds}s ({seconds//60} min)",
                    parse_mode=ParseMode.HTML
                )
            except ValueError:
                await update.message.reply_text("invalid number", parse_mode=ParseMode.HTML)
        
        elif cmd == "image":
            if len(context.args) < 2:
                await update.message.reply_text(
                    "Usage: /xbot image <style>\nStyles: cyberpunk, solana, professional, neon",
                    parse_mode=ParseMode.HTML
                )
                return
            style = context.args[1].lower()
            engine.set_image_params(color_scheme=style)
            await update.message.reply_text(f"image style set to: {style}", parse_mode=ParseMode.HTML)
        
        else:
            await update.message.reply_text("unknown command. use /xbot for help.", parse_mode=ParseMode.HTML)
            
    except Exception as e:
        await update.message.reply_text(f"X Bot error: {str(e)[:100]}", parse_mode=ParseMode.MARKDOWN)


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

DEFAULT_ADMIN_USER_ID = 8527130908  # Legacy fallback if env not set


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

⚠️ _Low balance warning: <{config.low_balance_threshold} SOL_
"""

        # Warning if low balance (configurable via LOW_BALANCE_THRESHOLD env var)
        if sol_balance < config.low_balance_threshold:
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
        config = get_config()
        admin_ids = _get_treasury_admin_ids(config)
        admin_line = ", ".join(str(admin_id) for admin_id in admin_ids) if admin_ids else "None"

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

*Admin IDs:* `{admin_line}`
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


async def modstats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /modstats - Show moderation statistics (admin only).
    """
    config = get_config()
    user_id = update.effective_user.id if update.effective_user else 0

    # Admin check
    if user_id not in config.admin_ids:
        await update.message.reply_text("🚫 Admin only command.")
        return

    try:
        from core.jarvis_admin import get_jarvis_admin
        admin = get_jarvis_admin()
        stats = admin.get_moderation_stats()
        top_engaged = admin.get_top_engaged(limit=5, days=7)

        # Format top engaged
        engaged_list = ""
        for i, user_data in enumerate(top_engaged, 1):
            engaged_list += f"{i}. @{user_data['username']} ({user_data['action_count']} actions)\n"

        if not engaged_list:
            engaged_list = "No engagement data yet"

        message = f"""
📊 *MODERATION STATS*

*Users:* {stats['total_users']} total, {stats['banned_users']} banned
*Messages:* {stats['total_messages']} total, {stats['deleted_messages']} deleted
*Pending Upgrades:* {stats['pending_upgrades']}

━━━ *Top Engaged (7d)* ━━━
{engaged_list}
━━━ *Protection Status* ━━━
✅ Spam detection: Active
✅ Phishing detection: Active
✅ Scam wallet detection: Active
✅ New user link restriction: Active
✅ Flood protection: Active
✅ Suspicious username ban: Active
"""

        await update.message.reply_text(
            message,
            parse_mode=ParseMode.MARKDOWN,
        )

    except Exception as e:
        logger.error(f"Modstats failed: {e}")
        await update.message.reply_text(
            f"❌ *Error*\n\n{str(e)[:100]}",
            parse_mode=ParseMode.MARKDOWN,
        )


async def addscam(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /addscam <wallet> - Add a wallet address to scam list (admin only).
    """
    config = get_config()
    user_id = update.effective_user.id if update.effective_user else 0

    # Admin check
    if user_id not in config.admin_ids:
        await update.message.reply_text("🚫 Admin only command.")
        return

    if not context.args:
        await update.message.reply_text(
            "Usage: /addscam <wallet_address>\n\n"
            "Example: /addscam So11111111111111111111111111111111111111112"
        )
        return

    wallet = context.args[0]

    try:
        from core.jarvis_admin import get_jarvis_admin
        admin = get_jarvis_admin()

        if admin.add_scam_wallet(wallet):
            await update.message.reply_text(
                f"✅ Added to scam wallet list:\n`{wallet[:20]}...`\n\n"
                "Future messages with this address will trigger auto-ban.",
                parse_mode=ParseMode.MARKDOWN,
            )
            logger.info(f"Admin {user_id} added scam wallet: {wallet[:20]}...")
        else:
            await update.message.reply_text("❌ Invalid wallet address format.")

    except Exception as e:
        logger.error(f"Addscam failed: {e}")
        await update.message.reply_text(f"❌ Error: {str(e)[:100]}")


async def trust(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /trust @username - Mark a user as trusted (admin only).
    Trusted users bypass new-user link restrictions.
    """
    config = get_config()
    user_id = update.effective_user.id if update.effective_user else 0

    if user_id not in config.admin_ids:
        await update.message.reply_text("🚫 Admin only command.")
        return

    # Check if replying to a message or using @username
    target_user_id = None
    target_username = None

    if update.message.reply_to_message:
        target_user_id = update.message.reply_to_message.from_user.id
        target_username = update.message.reply_to_message.from_user.username or "unknown"
    elif context.args:
        target_username = context.args[0].lstrip("@")
        # Would need to look up user by username - for now just show usage
        await update.message.reply_text(
            "Reply to a user's message to trust them.\n"
            "Example: Reply to their message with /trust"
        )
        return
    else:
        await update.message.reply_text(
            "Usage: Reply to a user's message with /trust\n"
            "This marks them as trusted (bypasses new-user restrictions)."
        )
        return

    try:
        from core.jarvis_admin import get_jarvis_admin
        admin = get_jarvis_admin()
        admin.trust_user(target_user_id)
        await update.message.reply_text(
            f"✅ @{target_username} is now trusted.\n"
            "They can post links immediately and have reduced spam sensitivity."
        )
        logger.info(f"Admin {user_id} trusted user {target_user_id} (@{target_username})")

    except Exception as e:
        logger.error(f"Trust command failed: {e}")
        await update.message.reply_text(f"❌ Error: {str(e)[:100]}")


async def trustscore(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /trustscore [@username] - Check trust score for a user.
    Admins can check anyone, users can check themselves.
    """
    config = get_config()
    user_id = update.effective_user.id if update.effective_user else 0
    is_admin = user_id in config.admin_ids

    # Determine target user
    target_user_id = user_id
    target_username = update.effective_user.username or "you"

    if update.message.reply_to_message:
        if is_admin:
            target_user_id = update.message.reply_to_message.from_user.id
            target_username = update.message.reply_to_message.from_user.username or "unknown"
        else:
            await update.message.reply_text("Only admins can check other users' trust scores.")
            return

    try:
        from core.jarvis_admin import get_jarvis_admin
        admin = get_jarvis_admin()
        result = admin.calculate_trust_score(target_user_id)

        score = result.get("score", 0)
        level = result.get("level", "unknown")
        factors = result.get("factors", {})

        # Build response
        level_emoji = {
            "veteran": "🏆",
            "trusted": "✅",
            "regular": "👤",
            "new": "🆕",
            "suspicious": "⚠️",
            "unknown": "❓",
        }

        response = f"""
*Trust Score for @{target_username}*

{level_emoji.get(level, '❓')} *Level:* {level.upper()}
📊 *Score:* {score}/100

*Breakdown:*
▫️ Messages: +{factors.get('messages', 0):.1f}
▫️ Tenure: +{factors.get('tenure', 0):.1f}
▫️ Engagement: +{factors.get('engagement', 0):.1f}
▫️ Trusted flag: +{factors.get('trusted_flag', 0):.0f}
▫️ Warnings: -{factors.get('warnings_penalty', 0):.0f}
▫️ Reports: -{factors.get('reports_penalty', 0):.0f}

_Score 40+ = links allowed, 60+ = trusted, 80+ = veteran_
"""
        await update.message.reply_text(response, parse_mode=ParseMode.MARKDOWN)

    except Exception as e:
        logger.error(f"Trustscore command failed: {e}")
        await update.message.reply_text(f"❌ Error: {str(e)[:100]}")


async def warn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /warn @username [reason] - Warn a user (admin only).
    3 warnings = auto-ban.
    """
    config = get_config()
    user_id = update.effective_user.id if update.effective_user else 0

    if user_id not in config.admin_ids:
        await update.message.reply_text("🚫 Admin only command.")
        return

    target_user_id = None
    target_username = None
    reason = "admin warning"

    if update.message.reply_to_message:
        target_user_id = update.message.reply_to_message.from_user.id
        target_username = update.message.reply_to_message.from_user.username or "unknown"
        if context.args:
            reason = " ".join(context.args)
    else:
        await update.message.reply_text(
            "Usage: Reply to a user's message with /warn [reason]\n"
            "Example: /warn spamming links"
        )
        return

    try:
        from core.jarvis_admin import get_jarvis_admin
        admin = get_jarvis_admin()
        new_count = admin.warn_user(target_user_id)

        if new_count >= 3:
            # Auto-ban on 3rd warning
            chat_id = update.effective_chat.id
            await context.bot.ban_chat_member(chat_id=chat_id, user_id=target_user_id)
            admin.ban_user(target_user_id, f"3 warnings: {reason}")
            await update.message.reply_text(
                f"🚫 @{target_username} has reached 3 warnings and is now banned.\n"
                f"Reason: {reason}"
            )
            logger.warning(f"User {target_user_id} banned after 3 warnings by admin {user_id}")
        else:
            await update.message.reply_text(
                f"⚠️ @{target_username} warned ({new_count}/3).\n"
                f"Reason: {reason}\n\n"
                f"3 warnings = ban."
            )
            logger.info(f"Admin {user_id} warned user {target_user_id} ({new_count}/3): {reason}")

    except Exception as e:
        logger.error(f"Warn command failed: {e}")
        await update.message.reply_text(f"❌ Error: {str(e)[:100]}")


async def report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /report - Report a message as spam (reply to the message).
    Reports are logged and high-reported users get reviewed.
    """
    if not update.message.reply_to_message:
        await update.message.reply_text(
            "Reply to a spam message with /report to flag it.\n"
            "Admins will review reported messages."
        )
        return

    reporter_id = update.effective_user.id if update.effective_user else 0
    reporter_username = update.effective_user.username or "unknown"
    reported_msg = update.message.reply_to_message
    reported_user_id = reported_msg.from_user.id
    reported_username = reported_msg.from_user.username or "unknown"
    reported_text = reported_msg.text or "[no text]"

    try:
        from core.jarvis_admin import get_jarvis_admin
        admin = get_jarvis_admin()

        # Record the report as a moderation action
        admin.record_mod_action(
            action_type="user_report",
            user_id=reported_user_id,
            message_id=reported_msg.message_id,
            reason=f"reported by @{reporter_username}: {reported_text[:100]}"
        )

        # Check if user has been reported by enough unique users for auto-ban
        report_count, reporters = admin.get_report_count(reported_user_id, hours=24)
        chat_id = update.effective_chat.id

        if report_count >= 3:
            # Auto-ban: 3+ unique users reported this person
            try:
                await context.bot.ban_chat_member(chat_id=chat_id, user_id=reported_user_id)
                admin.ban_user(reported_user_id, f"community reported ({report_count} reports)")

                await update.message.reply_text(
                    f"🚫 @{reported_username} has been banned.\n"
                    f"Reported by {report_count} community members.\n"
                    f"Thanks for keeping the chat safe!"
                )
                logger.warning(f"AUTO-BAN: user {reported_user_id} @{reported_username} - {report_count} reports from: {reporters}")
                return
            except Exception as ban_err:
                logger.error(f"Failed to auto-ban reported user: {ban_err}")

        await update.message.reply_text(
            f"📢 Report received ({report_count}/3).\n"
            f"@{reported_username}'s message has been flagged.\n"
            f"3 reports from different users = auto-ban."
        )

        logger.info(f"User {reporter_id} reported {reported_user_id} ({report_count}/3 reports)")

    except Exception as e:
        logger.error(f"Report command failed: {e}")
        await update.message.reply_text("❌ Failed to submit report. Please try again.")


# =============================================================================
# Callback Query Handler
# =============================================================================

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle inline keyboard button presses."""
    from telegram.error import BadRequest, TimedOut, NetworkError, RetryAfter
    import asyncio

    query = update.callback_query
    data = query.data if query else "None"
    user_id = update.effective_user.id if update.effective_user else 0

    # Log all callbacks for debugging
    logger.info(f"Callback received: '{data}' from user {user_id}")

    # CRITICAL: Always answer callback first to stop loading spinner
    try:
        await query.answer()
    except BadRequest as e:
        logger.warning(f"Could not answer callback (stale?): {e}")
        # Continue processing even if answer fails
    except Exception as e:
        logger.error(f"Error answering callback: {e}")

    # Check if query.message exists (can be None for inline mode)
    if not query.message:
        logger.warning(f"Callback has no message object: {data}")
        return

    config = get_config()

    # Menu navigation callbacks
    if data == "menu_trending":
        await _handle_trending_inline(query)
        return

    if data == "menu_status":
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

    # Admin-only menu callbacks - use CallbackUpdate wrapper
    if data == "menu_signals":
        if not config.is_admin(user_id):
            await query.message.reply_text(fmt.format_unauthorized(), parse_mode=ParseMode.MARKDOWN)
            return
        cb_update = CallbackUpdate(query)
        context.args = []
        await signals(cb_update, context)
        return

    if data == "menu_digest":
        if not config.is_admin(user_id):
            await query.message.reply_text(fmt.format_unauthorized(), parse_mode=ParseMode.MARKDOWN)
            return
        cb_update = CallbackUpdate(query)
        context.args = []
        await digest(cb_update, context)
        return

    if data == "menu_brain":
        if not config.is_admin(user_id):
            await query.message.reply_text(fmt.format_unauthorized(), parse_mode=ParseMode.MARKDOWN)
            return
        cb_update = CallbackUpdate(query)
        context.args = []
        await brain(cb_update, context)
        return

    if data == "menu_reload":
        if not config.is_admin(user_id):
            await query.message.reply_text(fmt.format_unauthorized(), parse_mode=ParseMode.MARKDOWN)
            return
        cb_update = CallbackUpdate(query)
        context.args = []
        await reload(cb_update, context)
        return

    if data == "menu_health":
        if not config.is_admin(user_id):
            await query.message.reply_text(fmt.format_unauthorized(), parse_mode=ParseMode.MARKDOWN)
            return
        cb_update = CallbackUpdate(query)
        context.args = []
        await health(cb_update, context)
        return

    if data == "menu_flags":
        if not config.is_admin(user_id):
            await query.message.reply_text(fmt.format_unauthorized(), parse_mode=ParseMode.MARKDOWN)
            return
        cb_update = CallbackUpdate(query)
        context.args = []
        await flags(cb_update, context)
        return

    if data == "menu_score":
        if not config.is_admin(user_id):
            await query.message.reply_text(fmt.format_unauthorized(), parse_mode=ParseMode.MARKDOWN)
            return
        cb_update = CallbackUpdate(query)
        context.args = []
        await score(cb_update, context)
        return

    if data == "menu_config":
        if not config.is_admin(user_id):
            await query.message.reply_text(fmt.format_unauthorized(), parse_mode=ParseMode.MARKDOWN)
            return
        cb_update = CallbackUpdate(query)
        context.args = []
        await config_cmd(cb_update, context)
        return

    if data == "menu_system":
        if not config.is_admin(user_id):
            await query.message.reply_text(fmt.format_unauthorized(), parse_mode=ParseMode.MARKDOWN)
            return
        cb_update = CallbackUpdate(query)
        context.args = []
        await system(cb_update, context)
        return

    if data == "menu_orders":
        if not config.is_admin(user_id):
            await query.message.reply_text(fmt.format_unauthorized(), parse_mode=ParseMode.MARKDOWN)
            return
        cb_update = CallbackUpdate(query)
        context.args = []
        await orders(cb_update, context)
        return

    if data == "menu_wallet":
        if not config.is_admin(user_id):
            await query.message.reply_text(fmt.format_unauthorized(), parse_mode=ParseMode.MARKDOWN)
            return
        cb_update = CallbackUpdate(query)
        context.args = []
        await wallet(cb_update, context)
        return

    if data == "menu_logs":
        if not config.is_admin(user_id):
            await query.message.reply_text(fmt.format_unauthorized(), parse_mode=ParseMode.MARKDOWN)
            return
        cb_update = CallbackUpdate(query)
        context.args = []
        await logs(cb_update, context)
        return

    if data == "menu_metrics":
        if not config.is_admin(user_id):
            await query.message.reply_text(fmt.format_unauthorized(), parse_mode=ParseMode.MARKDOWN)
            return
        cb_update = CallbackUpdate(query)
        context.args = []
        await metrics(cb_update, context)
        return

    if data == "menu_audit":
        if not config.is_admin(user_id):
            await query.message.reply_text(fmt.format_unauthorized(), parse_mode=ParseMode.MARKDOWN)
            return
        cb_update = CallbackUpdate(query)
        context.args = []
        await audit(cb_update, context)
        return

    # Trading callbacks
    if data.startswith("trade_"):
        if not _is_treasury_admin(config, user_id):
            await query.message.reply_text(fmt.format_unauthorized(), parse_mode=ParseMode.MARKDOWN)
            return

        token_address = data.replace("trade_", "", 1)
        await _show_trade_ticket(query, token_address)
        return

    if data.startswith("buy_"):
        if not _is_treasury_admin(config, user_id):
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
        cb_update = CallbackUpdate(query)
        await analyze(cb_update, context)
        return

    if data == "refresh_trending":
        await _handle_trending_inline(query)
        return

    # New trading callbacks
    if data.startswith("trade_pct:"):
        if not _is_treasury_admin(config, user_id):
            await query.message.reply_text(
                "⛔ *Admin Only*\n\nYou are not authorized to trade.",
                parse_mode=ParseMode.MARKDOWN
            )
            logger.warning(f"Unauthorized trade attempt by user {user_id}")
            return

        await _execute_trade_with_tp_sl(query, data)
        return

    if data.startswith("sell_pos:"):
        if not _is_treasury_admin(config, user_id):
            await query.message.reply_text("⛔ *Admin Only*", parse_mode=ParseMode.MARKDOWN)
            return

        position_id = data.split(":")[1]
        await _close_position_callback(query, position_id)
        return

    if data == "refresh_report":
        if not _is_treasury_admin(config, user_id):
            return
        await _refresh_report_inline(query)
        return

    if data == "refresh_balance":
        if not _is_treasury_admin(config, user_id):
            return
        await _refresh_balance_inline(query)
        return

    if data == "show_positions_detail":
        if not _is_treasury_admin(config, user_id):
            return
        await _show_positions_inline(query)
        return

    if data == "toggle_live_mode":
        if not _is_treasury_admin(config, user_id):
            return
        await _toggle_live_mode(query)
        return

    # Expand button callbacks from sentiment reports (format: expand:{section})
    if data.startswith("expand:"):
        logger.info(f"Expand callback received: {data} from user {user_id}")
        section = data.replace("expand:", "")
        await _handle_expand_section(query, section, config, user_id)
        return

    # Ape button callbacks from sentiment reports (format: ape:{alloc}:{profile}:{type}:{symbol}:{contract})
    if data.startswith("ape:"):
        logger.info(f"Ape callback received: {data} from user {user_id}")

        if not APE_BUTTONS_AVAILABLE:
            await _send_with_retry(
                query,
                "❌ Ape trading module not available",
                parse_mode=ParseMode.MARKDOWN
            )
            logger.error("APE_BUTTONS_AVAILABLE is False")
            return

        if not _is_treasury_admin(config, user_id):
            await _send_with_retry(
                query,
                f"⛔ *Admin Only*\n\nUser ID {user_id} is not authorized.",
                parse_mode=ParseMode.MARKDOWN
            )
            logger.warning(f"Unauthorized ape trade attempt by user {user_id}")
            return

        logger.info(f"Executing ape trade for admin {user_id}")
        await _execute_ape_trade(query, data)
        return


async def _handle_expand_section(query, section: str, config, user_id: int):
    """
    Handle expand button clicks from sentiment report sections.

    Loads saved section data from temp files and posts buy buttons.

    Sections: trending, stocks, indexes, top_picks
    """
    import tempfile
    from pathlib import Path

    # Check if user is treasury admin for trading
    if not _is_treasury_admin(config, user_id):
        await _send_with_retry(
            query,
            "⛔ *Admin Only*\n\nYou must be a treasury admin to view trading options.",
            parse_mode=ParseMode.MARKDOWN
        )
        return

    temp_dir = Path(tempfile.gettempdir())

    try:
        if section == "trending":
            # Load trending tokens data
            data_file = temp_dir / "jarvis_trending_tokens.json"
            if not data_file.exists():
                await _send_with_retry(
                    query,
                    "📊 No trending data available. Please wait for the next report.",
                    parse_mode=ParseMode.MARKDOWN
                )
                return

            with open(data_file) as f:
                tokens = json.load(f)

            await _send_with_retry(
                query,
                "🔥 *TRENDING TOKENS - Trading Options*\n\n"
                "_Select allocation and risk profile:_",
                parse_mode=ParseMode.MARKDOWN
            )

            # Post buy buttons for each token with JARVIS insights
            for token in tokens[:5]:
                contract_short = token["contract"][:10] if token["contract"] else ""
                keyboard = _create_ape_keyboard(
                    symbol=token["symbol"],
                    asset_type="token",
                    contract=token["contract"],
                )

                price_str = f"${token['price_usd']:.8f}" if token['price_usd'] < 0.01 else f"${token['price_usd']:.4f}"
                change = token["change_24h"]
                change_emoji = "🟢" if change > 0 else "🔴"

                # JARVIS quick insight for microcaps based on price action & verdict
                verdict = token.get("verdict", "NEUTRAL")
                if verdict == "BULLISH" and change > 20:
                    insight = "momentum strong. late entry risk but uptrend confirmed"
                elif verdict == "BULLISH":
                    insight = "signals say long. manage size accordingly"
                elif verdict == "BEARISH":
                    insight = "signals say caution. wait for better entry or skip"
                elif change > 50:
                    insight = "parabolic move. high risk. could moon or dump. gambling tier"
                elif change > 20:
                    insight = "solid pump. momentum play if you believe. nfa"
                elif change > 5:
                    insight = "starting to move. early if it continues"
                elif change > 0:
                    insight = "slight green. nothing exciting yet"
                elif change > -10:
                    insight = "small dip. might be entry. might be start of dump"
                else:
                    insight = "major correction. either dead or opportunity. dyor"

                await _send_with_retry(
                    query,
                    f"🛒 *{token['symbol']}*\n"
                    f"Price: {price_str} {change_emoji} {change:+.1f}%\n"
                    f"Signal: {verdict}\n"
                    f"💭 _{insight}_",
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=keyboard
                )
                await asyncio.sleep(EXPAND_MESSAGE_DELAY)

        elif section == "stocks":
            # Load stocks data
            data_file = temp_dir / "jarvis_stocks.json"
            if not data_file.exists():
                await _send_with_retry(
                    query,
                    "📊 No stocks data available. Please wait for the next report.",
                    parse_mode=ParseMode.MARKDOWN
                )
                return

            with open(data_file) as f:
                stocks = json.load(f)

            await _send_with_retry(
                query,
                "📈 *TOKENIZED STOCKS - Trading Options*\n\n"
                "_Trade US equities on Solana:_",
                parse_mode=ParseMode.MARKDOWN
            )

            # Post buy buttons for each stock
            for stock in stocks[:5]:
                keyboard = _create_ape_keyboard(
                    symbol=stock["symbol"],
                    asset_type="stock",
                    contract=stock["mint"],
                )

                await _send_with_retry(
                    query,
                    f"🛒 *{stock['symbol']}* ({stock['underlying']})\n"
                    f"{stock['name']}",
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=keyboard
                )
                await asyncio.sleep(EXPAND_MESSAGE_DELAY)

        elif section == "indexes":
            # Load indexes data
            data_file = temp_dir / "jarvis_indexes.json"
            if not data_file.exists():
                await _send_with_retry(
                    query,
                    "📊 No indexes data available. Please wait for the next report.",
                    parse_mode=ParseMode.MARKDOWN
                )
                return

            with open(data_file) as f:
                indexes = json.load(f)

            await _send_with_retry(
                query,
                "📊 *INDEXES & COMMODITIES - Trading Options*\n\n"
                "_Diversified market exposure:_",
                parse_mode=ParseMode.MARKDOWN
            )

            # Post buy buttons for each index
            for index in indexes:
                keyboard = _create_ape_keyboard(
                    symbol=index["symbol"],
                    asset_type=index["type"],  # Use actual type: index, commodity, etc.
                    contract=index["mint"],
                )

                type_emoji = "📊" if index["type"] == "index" else "🥇" if index["type"] == "commodity" else "📄"

                await _send_with_retry(
                    query,
                    f"🛒 {type_emoji} *{index['symbol']}* ({index['underlying']})\n"
                    f"{index['name']}",
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=keyboard
                )
                await asyncio.sleep(EXPAND_MESSAGE_DELAY)

        elif section == "top_picks":
            # Load top picks data
            data_file = temp_dir / "jarvis_top_picks.json"
            if not data_file.exists():
                await _send_with_retry(
                    query,
                    "🏆 No top picks data available. Please wait for the next report.",
                    parse_mode=ParseMode.MARKDOWN
                )
                return

            with open(data_file) as f:
                picks = json.load(f)

            await _send_with_retry(
                query,
                "🏆 *JARVIS TOP 5 - Trading Options*\n\n"
                "_Highest conviction picks across all assets:_",
                parse_mode=ParseMode.MARKDOWN
            )

            # Post buy buttons for top 5 picks
            for i, pick in enumerate(picks[:5]):
                # Map asset_class to proper type: token, stock, index, commodity
                asset_class = pick.get("asset_class", "token")
                if asset_class in ("index", "commodity"):
                    asset_type = asset_class  # Keep as-is for indexes/commodities
                elif asset_class == "stock":
                    asset_type = "stock"
                else:
                    asset_type = "token"  # Default to token
                keyboard = _create_ape_keyboard(
                    symbol=pick["symbol"],
                    asset_type=asset_type,
                    contract=pick["contract"],
                )

                # Conviction color
                if pick["conviction"] >= 80:
                    conv_emoji = "🟢"
                elif pick["conviction"] >= 60:
                    conv_emoji = "🟡"
                else:
                    conv_emoji = "🟠"

                # Medal for top 3
                medal = "🥇" if i == 0 else "🥈" if i == 1 else "🥉" if i == 2 else f"#{i+1}"

                await _send_with_retry(
                    query,
                    f"{medal} *{pick['symbol']}* ({pick['asset_class'].upper()}) {conv_emoji} {pick['conviction']}/100\n"
                    f"📝 {pick['reasoning'][:60]}...",
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=keyboard
                )
                await asyncio.sleep(EXPAND_MESSAGE_DELAY)

        elif section == "bluechip":
            # Load blue-chip Solana tokens data
            data_file = temp_dir / "jarvis_bluechip_tokens.json"
            if not data_file.exists():
                await _send_with_retry(
                    query,
                    "💎 No blue-chip data available. Please wait for the next report.",
                    parse_mode=ParseMode.MARKDOWN
                )
                return

            with open(data_file) as f:
                tokens = json.load(f)

            await _send_with_retry(
                query,
                "💎 *SOLANA BLUE CHIPS - Trading Options*\n\n"
                "_High liquidity tokens with proven history:_",
                parse_mode=ParseMode.MARKDOWN
            )

            # Post buy buttons for each blue-chip token with JARVIS insights
            for token in tokens[:10]:
                keyboard = _create_ape_keyboard(
                    symbol=token["symbol"],
                    asset_type="token",
                    contract=token["contract"],
                )

                price_str = f"${token['price_usd']:.8f}" if token['price_usd'] < 0.01 else f"${token['price_usd']:.2f}"
                change = token["change_24h"]
                change_emoji = "🟢" if change > 0 else "🔴"

                # Format market cap
                mcap = token.get("mcap", 0)
                if mcap >= 1_000_000_000:
                    mcap_str = f"${mcap / 1_000_000_000:.1f}B"
                elif mcap >= 1_000_000:
                    mcap_str = f"${mcap / 1_000_000:.0f}M"
                else:
                    mcap_str = f"${mcap / 1_000:.0f}K"

                category = token.get("category", "Other")
                cat_emoji = {"L1": "⚡", "DeFi": "💱", "Infrastructure": "🛠️", "Meme": "🐕"}.get(category, "📊")

                # JARVIS quick insight based on price action
                if change > 10:
                    insight = "momentum play. might be late but strength is strength"
                elif change > 3:
                    insight = "trending up. reasonable entry if you believe the thesis"
                elif change > 0:
                    insight = "steady. not exciting but not concerning either"
                elif change > -3:
                    insight = "slight dip. could be accumulation zone"
                elif change > -10:
                    insight = "pullback. dca territory if you're already in"
                else:
                    insight = "significant drop. either opportunity or warning. dyor"

                await _send_with_retry(
                    query,
                    f"🛒 {cat_emoji} *{token['symbol']}* ({category})\n"
                    f"Price: {price_str} {change_emoji} {change:+.1f}%\n"
                    f"MCap: {mcap_str}\n"
                    f"💭 _{insight}_",
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=keyboard
                )
                await asyncio.sleep(EXPAND_MESSAGE_DELAY)

        else:
            await _send_with_retry(
                query,
                f"Unknown section: {section}",
                parse_mode=ParseMode.MARKDOWN
            )

    except Exception as e:
        logger.error(f"Error handling expand section {section}: {e}")
        await _send_with_retry(
            query,
            f"❌ Error loading {section} data: {str(e)[:100]}",
            parse_mode=ParseMode.MARKDOWN
        )


def _create_ape_keyboard(symbol: str, asset_type: str, contract: str) -> InlineKeyboardMarkup:
    """Create an APE trading keyboard for a given asset."""
    contract_short = contract[:10] if contract else ""
    # Map asset type to character: t=token, s=stock, i=index, c=commodity, m=metal, b=bond
    type_char_map = {"token": "t", "stock": "s", "index": "i", "commodity": "c", "metal": "m", "bond": "b"}
    type_char = type_char_map.get(asset_type, "t")

    # Store full contract in lookup file for later retrieval
    # (Telegram callback_data is limited to 64 bytes, so we truncate and lookup)
    if contract and len(contract) > 10:
        import tempfile
        from pathlib import Path
        lookup_file = Path(tempfile.gettempdir()) / "jarvis_contract_lookup.json"
        try:
            lookup = {}
            if lookup_file.exists():
                with open(lookup_file) as f:
                    lookup = json.load(f)
            lookup[contract_short] = contract
            with open(lookup_file, "w") as f:
                json.dump(lookup, f)
            logger.debug(f"Saved contract lookup: {contract_short} -> {contract}")
        except Exception as e:
            logger.error(f"Failed to save contract lookup: {e}")

    buttons = []

    # Row 1: 5% allocation options
    buttons.append([
        InlineKeyboardButton(
            text="5% 🛡️ Safe",
            callback_data=f"ape:5:s:{type_char}:{symbol}:{contract_short}"[:64]
        ),
        InlineKeyboardButton(
            text="5% ⚖️ Med",
            callback_data=f"ape:5:m:{type_char}:{symbol}:{contract_short}"[:64]
        ),
        InlineKeyboardButton(
            text="5% 🔥 Degen",
            callback_data=f"ape:5:d:{type_char}:{symbol}:{contract_short}"[:64]
        ),
    ])

    # Row 2: 2% allocation options
    buttons.append([
        InlineKeyboardButton(
            text="2% 🛡️ Safe",
            callback_data=f"ape:2:s:{type_char}:{symbol}:{contract_short}"[:64]
        ),
        InlineKeyboardButton(
            text="2% ⚖️ Med",
            callback_data=f"ape:2:m:{type_char}:{symbol}:{contract_short}"[:64]
        ),
        InlineKeyboardButton(
            text="2% 🔥 Degen",
            callback_data=f"ape:2:d:{type_char}:{symbol}:{contract_short}"[:64]
        ),
    ])

    # Row 3: 1% allocation options
    buttons.append([
        InlineKeyboardButton(
            text="1% 🛡️ Safe",
            callback_data=f"ape:1:s:{type_char}:{symbol}:{contract_short}"[:64]
        ),
        InlineKeyboardButton(
            text="1% ⚖️ Med",
            callback_data=f"ape:1:m:{type_char}:{symbol}:{contract_short}"[:64]
        ),
        InlineKeyboardButton(
            text="1% 🔥 Degen",
            callback_data=f"ape:1:d:{type_char}:{symbol}:{contract_short}"[:64]
        ),
    ])

    return InlineKeyboardMarkup(buttons)


async def _execute_ape_trade(query, callback_data: str):
    """
    Execute an ape trade from sentiment report buttons.

    Callback format: ape:{alloc}:{profile}:{type}:{symbol}:{contract}
    Example: ape:5:m:t:BONK:DezXAZ8z7P

    All trades have MANDATORY TP/SL based on risk profile.
    """
    import tempfile
    from pathlib import Path

    user_id = query.from_user.id

    parsed = parse_ape_callback(callback_data)
    if not parsed:
        await _send_with_retry(
            query,
            "❌ Invalid trade button format.",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    symbol = parsed["symbol"]
    allocation_pct = parsed["allocation_percent"]
    risk_profile = parsed["risk_profile"]
    contract_short = parsed.get("contract", "")
    asset_type = parsed.get("asset_type", "token")

    # Look up full contract from mapping (truncated for Telegram callback limit)
    contract = contract_short
    if contract_short and len(contract_short) <= 10:
        lookup_file = Path(tempfile.gettempdir()) / "jarvis_contract_lookup.json"
        try:
            if lookup_file.exists():
                with open(lookup_file) as f:
                    lookup = json.load(f)
                full_contract = lookup.get(contract_short, "")
                if full_contract:
                    contract = full_contract
                    logger.info(f"Resolved contract: {contract_short} -> {contract}")
        except Exception as e:
            logger.error(f"Failed to lookup contract: {e}")

    if not contract:
        await _send_with_retry(
            query,
            "❌ Missing token address for trade. Please refresh the report.",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    profile_config = get_risk_config(asset_type, risk_profile)
    tp_pct = profile_config["tp_pct"]
    sl_pct = profile_config["sl_pct"]
    profile_label = profile_config["label"]

    # Acknowledge button click immediately
    try:
        await query.answer("Processing trade...", show_alert=False)
    except Exception:
        pass  # Button might be stale

    # Show processing message (with error handling for stale messages)
    try:
        await query.edit_message_text(
            (
                "⏳ <b>Processing ape trade...</b>\n\n"
                f"Token: <code>{symbol}</code>\n"
                f"Allocation: {allocation_pct}%\n"
                f"Profile: {profile_label}\n"
                f"TP: +{int(tp_pct)}% | SL: -{int(sl_pct)}%"
            ),
            parse_mode=ParseMode.HTML,
        )
    except Exception as e:
        logger.warning(f"Could not edit message for processing status: {e}")
        # Continue anyway - message edit is just UX

    chat_id = query.message.chat_id

    try:
        engine = await _get_treasury_engine()
        balance_sol, balance_usd = await engine.get_portfolio_value()

        if balance_sol <= 0:
            await query.message.reply_text(
                "❌ Treasury balance is zero.",
                parse_mode=ParseMode.HTML,
            )
            return

        logger.info(f"Calling execute_ape_trade for {callback_data[:50]}...")
        result = await execute_ape_trade(
            callback_data=callback_data,
            entry_price=0.0,
            treasury_balance_sol=balance_sol,
            user_id=user_id,
        )
        logger.info(f"execute_ape_trade returned: success={result.success}, error={result.error}")

        if not result.trade_setup:
            error_msg = result.error or 'Trade setup failed'
            await query.message.reply_text(
                f"❌ <b>Trade Failed</b>\n\n{error_msg}",
                parse_mode=ParseMode.HTML,
            )
            return

        setup = result.trade_setup
        amount_usd = setup.amount_sol * (balance_usd / balance_sol) if balance_sol > 0 else 0.0
        mode = "LIVE" if not engine.dry_run else "PAPER"

        # Sanitize symbol for safe HTML output
        import html as html_module
        safe_symbol = html_module.escape(setup.symbol)

        if result.success:
            result_text = (
                f"✅ <b>TRADE EXECUTED ({mode})</b>\n\n"
                f"🪙 Token: <code>{safe_symbol}</code>\n"
                f"📍 Entry: <code>${setup.entry_price:.8f}</code>\n"
                f"💰 Amount: <code>{setup.amount_sol:.4f} SOL</code> (~${amount_usd:.2f})\n"
                f"📊 Profile: {profile_label}\n"
                f"🎯 TP: <code>${setup.take_profit_price:.8f}</code> (+{int(tp_pct)}%)\n"
                f"🛑 SL: <code>${setup.stop_loss_price:.8f}</code> (-{int(sl_pct)}%)"
            )
            if result.tx_signature:
                result_text += f"\n\n<a href='https://solscan.io/tx/{result.tx_signature}'>View TX on Solscan</a>"
        else:
            # Sanitize error message
            safe_error = html_module.escape(str(result.error or 'Unknown error')[:200])
            result_text = (
                f"⚠️ <b>TRADE FAILED ({mode})</b>\n\n"
                f"🪙 Token: <code>{safe_symbol}</code>\n"
                f"💰 Allocation: {allocation_pct}%\n"
                f"📊 Profile: {profile_label}\n"
                f"❌ Reason: {safe_error}"
            )

        # Send trade feedback - critical that user sees result
        logger.info(f"Sending trade result: {result_text[:100]}...")
        try:
            await query.message.reply_text(
                result_text,
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=True,
            )
            logger.info("Trade result sent successfully")
        except Exception as send_err:
            logger.error(f"Failed to send trade result with HTML: {send_err}")
            # Fallback to plain text
            try:
                plain_text = f"Trade {'EXECUTED' if result.success else 'FAILED'}: {safe_symbol} - {setup.amount_sol:.4f} SOL"
                await query.message.reply_text(plain_text)
                logger.info("Trade result sent as plain text fallback")
            except Exception as fallback_err:
                logger.error(f"Even fallback message failed: {fallback_err}")

    except Exception as e:
        logger.error(f"Ape trade failed: {e}", exc_info=True)
        try:
            await query.message.reply_text(
                f"❌ <b>Trade Error</b>\n\n{str(e)[:200]}",
                parse_mode=ParseMode.HTML,
            )
        except Exception:
            try:
                await query.message.reply_text(f"Trade error: {str(e)[:100]}")
            except Exception:
                logger.error("Could not send any error message to user")


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
    config = get_config()
    admin_ids = _get_treasury_admin_ids(config)

    if user_id not in admin_ids:
        await query.message.reply_text(
            "Admin only. You are not authorized to trade.",
            parse_mode=ParseMode.MARKDOWN
        )
        logger.warning(f"Trade blocked: unauthorized user {user_id}")
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
        # Low balance warning (configurable via LOW_BALANCE_THRESHOLD env var)
        threshold = config.low_balance_threshold if config else 0.01
        if sol_balance < threshold:
            message += f"\n🚨 *WARNING: Low balance!* (< {threshold} SOL)"

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

        # Add brief moderation stats
        try:
            from core.jarvis_admin import get_jarvis_admin
            admin = get_jarvis_admin()
            stats = admin.get_moderation_stats()
            if stats['deleted_messages'] > 0 or stats['banned_users'] > 0:
                message += f"\n\n🛡️ *Mod Activity*: {stats['deleted_messages']} deleted, {stats['banned_users']} banned"
        except Exception:
            pass  # Don't fail digest if mod stats fail

        # Cleanse sensitive info before sending
        message = _cleanse_sensitive_info(message)

        # Send to broadcast chat (group) only - no private admin messages
        if config.broadcast_chat_id:
            try:
                await context.bot.send_message(
                    chat_id=config.broadcast_chat_id,
                    text=message,
                    parse_mode=ParseMode.MARKDOWN,
                    disable_web_page_preview=True,
                )
                logger.info(f"Sent digest to broadcast chat {config.broadcast_chat_id}")
            except Exception as e:
                logger.error(f"Failed to send digest to broadcast chat: {e}")
        else:
            logger.warning("No broadcast_chat_id configured - digest not sent")

    except Exception as e:
        logger.error(f"Scheduled digest failed: {e}")


# =============================================================================
# Error Handler
# =============================================================================

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Log errors with full details for debugging."""
    import traceback
    from telegram.error import RetryAfter, TimedOut, NetworkError, BadRequest

    error = context.error
    error_type = type(error).__name__
    error_msg = str(error)

    # Get update context for debugging
    update_info = ""
    if update:
        if update.callback_query:
            update_info = f" | callback_data={update.callback_query.data[:50] if update.callback_query.data else 'None'}"
        elif update.message:
            update_info = f" | message={update.message.text[:50] if update.message.text else 'None'}"

    # Log full error with stack trace
    logger.error(f"Bot error: {error_type}: {error_msg}{update_info}")
    logger.error(f"Traceback: {''.join(traceback.format_exception(type(error), error, error.__traceback__))[-500:]}")

    # Handle specific error types
    if isinstance(error, RetryAfter):
        logger.warning(f"Rate limited for {error.retry_after}s - will retry")
        return  # Don't send error message during rate limit

    if isinstance(error, (TimedOut, NetworkError)):
        logger.warning(f"Network issue: {error_msg}")
        return  # Transient error, don't spam user

    # Try to notify user (with retry for rate limits)
    if update and update.effective_message:
        try:
            await update.effective_message.reply_text(
                f"⚠️ Error: {error_type}. Please try again.",
                parse_mode=ParseMode.MARKDOWN,
            )
        except Exception as e:
            logger.error(f"Failed to send error message: {e}")


# Media restriction flag - can be toggled by admin
_MEDIA_RESTRICTED = True  # GIFs/animations blocked by default

async def handle_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle media messages (GIFs, animations, stickers).
    Block from new users or when media is restricted.
    """
    if not update.message:
        return

    user_id = update.effective_user.id if update.effective_user else 0
    username = update.effective_user.username or "unknown"
    chat_id = update.effective_chat.id if update.effective_chat else 0

    # Check if admin
    config = get_config()
    if user_id in config.admin_ids:
        return  # Admins can always send media

    # Check if media is restricted globally
    global _MEDIA_RESTRICTED
    if _MEDIA_RESTRICTED:
        try:
            await context.bot.delete_message(chat_id=chat_id, message_id=update.message.message_id)
            logger.info(f"MEDIA BLOCKED: @{username} - media restricted mode active")
        except Exception as e:
            logger.error(f"Failed to delete media: {e}")
        return

    # Check if new user
    try:
        from core.jarvis_admin import get_jarvis_admin
        admin = get_jarvis_admin()
        user = admin.get_user(user_id)

        if not user or user.message_count < 5:
            # New user trying to send media
            await context.bot.delete_message(chat_id=chat_id, message_id=update.message.message_id)
            await context.bot.send_message(
                chat_id=chat_id,
                text=f"🚫 @{username} - new users can't send media yet. Chat normally first."
            )
            logger.info(f"MEDIA BLOCKED: new user @{username} (msgs: {user.message_count if user else 0})")
            return

        if user.warning_count > 0:
            # User with warnings trying to send media
            await context.bot.delete_message(chat_id=chat_id, message_id=update.message.message_id)
            logger.info(f"MEDIA BLOCKED: warned user @{username} (warnings: {user.warning_count})")
            return

    except Exception as e:
        logger.error(f"Media handler error: {e}")


async def toggle_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /togglemedia - Toggle media restrictions (admin only).
    """
    config = get_config()
    user_id = update.effective_user.id if update.effective_user else 0

    if user_id not in config.admin_ids:
        await update.message.reply_text("🚫 Admin only command.")
        return

    global _MEDIA_RESTRICTED
    _MEDIA_RESTRICTED = not _MEDIA_RESTRICTED

    status = "🔴 BLOCKED" if _MEDIA_RESTRICTED else "🟢 ALLOWED"
    await update.message.reply_text(
        f"Media/GIFs are now: {status}\n\n"
        f"Use /togglemedia to change."
    )
    logger.info(f"Media restriction toggled to {_MEDIA_RESTRICTED} by admin {user_id}")


# Spam patterns - instant ban
SPAM_PATTERNS = [
    "want to buy",
    "buying sol wallet",
    "buy a sol wallet",
    "buy sol wallet",
    "purchase wallet",
    "dm me for",
    "contact me on whatsapp",
    "telegram @",
    "t.me/",
    "make money fast",
    "investment opportunity",
    "guaranteed profit",
    "double your",
]

async def check_and_ban_spam(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str, user_id: int) -> bool:
    """Check for spam and ban user if detected. Returns True if spam was detected."""
    try:
        from core.jarvis_admin import get_jarvis_admin
        admin = get_jarvis_admin()
        
        chat_id = update.effective_chat.id
        message_id = update.message.message_id
        username = update.effective_user.username or "unknown"
        
        # Record message for analysis
        admin.record_message(message_id, user_id, username, text, chat_id)
        admin.update_user(user_id, username)

        # Track engagement
        action_type = 'message'
        if update.message.reply_to_message:
            action_type = 'reply'
        elif '?' in text:
            action_type = 'question'
        admin.track_engagement(user_id, action_type, chat_id, text[:100])

        # Check for message flooding - auto-mute for severe spam
        is_rate_limited, msg_count = admin.is_rate_limited(user_id)
        if is_rate_limited and msg_count >= 15:
            # Severe flooding - auto-mute for 1 hour
            from datetime import datetime, timedelta, timezone as tz
            from telegram import ChatPermissions
            try:
                until_date = datetime.now(tz.utc) + timedelta(hours=1)
                await context.bot.restrict_chat_member(
                    chat_id=chat_id,
                    user_id=user_id,
                    permissions=ChatPermissions(can_send_messages=False),
                    until_date=until_date
                )
                admin.mute_user(user_id, f"flooding: {msg_count} msgs in 60s", 1)
                response = admin.get_random_response("flood_muted", username=username, hours=1)
                await context.bot.send_message(chat_id=chat_id, text=response)
                logger.warning(f"FLOOD MUTED: user={user_id} @{username} msgs={msg_count}")
                return True
            except Exception as mute_err:
                logger.error(f"Failed to mute flooding user: {mute_err}")

        # Check for scam wallet addresses - instant ban
        is_scam_wallet, scam_addr = admin.check_scam_wallet(text)
        if is_scam_wallet:
            await context.bot.delete_message(chat_id=chat_id, message_id=message_id)
            await context.bot.ban_chat_member(chat_id=chat_id, user_id=user_id)
            admin.ban_user(user_id, f"scam wallet: {scam_addr[:20]}...")
            response = admin.get_random_response("scam_wallet", username=username)
            response += admin.get_random_response("mistake_footer")
            await context.bot.send_message(chat_id=chat_id, text=response)
            logger.warning(f"SCAM WALLET BANNED: user={user_id} @{username} addr={scam_addr[:20]}")
            return True

        # Check new user link restrictions
        is_link_restricted, link_reason = admin.check_new_user_links(text, user_id)
        if is_link_restricted:
            await context.bot.delete_message(chat_id=chat_id, message_id=message_id)
            response = admin.get_random_response("new_user_link", username=username)
            await context.bot.send_message(chat_id=chat_id, text=response)
            logger.info(f"NEW USER LINK BLOCKED: user={user_id} @{username} reason={link_reason}")
            return True

        # Check for phishing links - instant ban
        is_phishing, phishing_match = admin.check_phishing_link(text)
        if is_phishing:
            await context.bot.delete_message(chat_id=chat_id, message_id=message_id)
            await context.bot.ban_chat_member(chat_id=chat_id, user_id=user_id)
            admin.ban_user(user_id, f"phishing link: {phishing_match}")
            response = admin.get_random_response("phishing_link", username=username)
            response += admin.get_random_response("mistake_footer")
            await context.bot.send_message(chat_id=chat_id, text=response)
            logger.warning(f"PHISHING BANNED: user={user_id} @{username} match={phishing_match}")
            return True

        # Check for command attempts from non-admins
        is_cmd_attempt, cmd_type = admin.detect_command_attempt(text, user_id)
        if is_cmd_attempt:
            response = admin.get_random_response("not_admin")
            await update.message.reply_text(response)
            logger.info(f"Rejected command attempt from {user_id}: {cmd_type}")
            return False  # Not spam, just rejected
        
        # Check for upgrade opportunities
        upgrade_idea = admin.detect_upgrade_opportunity(text, user_id)
        if upgrade_idea and not admin.is_admin(user_id):
            admin.queue_upgrade(upgrade_idea, user_id, text)
            logger.info(f"Queued upgrade idea from user feedback")
        
        # Analyze for spam
        is_spam, confidence, reason = admin.analyze_spam(text, user_id)
        
        if is_spam:
            # Delete the message
            await context.bot.delete_message(chat_id=chat_id, message_id=message_id)
            
            # Get user profile
            user = admin.get_user(user_id)
            warning_count = user.warning_count if user else 0
            
            if confidence >= 0.8 or warning_count >= 3:
                # Ban for high confidence spam or repeat offenders
                await context.bot.ban_chat_member(chat_id=chat_id, user_id=user_id)
                admin.ban_user(user_id, reason)

                response = admin.get_random_response("scam_deleted" if "keyword" in reason else "spam_deleted")
                response += admin.get_random_response("mistake_footer")

                await context.bot.send_message(chat_id=chat_id, text=response)
                logger.warning(f"SPAM BANNED: user={user_id} @{username} conf={confidence:.2f} reason={reason}")
            elif confidence >= 0.65 or warning_count >= 2:
                # Mute for medium-high confidence or 2 warnings
                from datetime import datetime, timedelta, timezone
                mute_hours = 2 if warning_count < 2 else 6
                until_date = datetime.now(timezone.utc) + timedelta(hours=mute_hours)
                try:
                    from telegram import ChatPermissions
                    await context.bot.restrict_chat_member(
                        chat_id=chat_id,
                        user_id=user_id,
                        permissions=ChatPermissions(can_send_messages=False),
                        until_date=until_date
                    )
                    admin.mute_user(user_id, reason, mute_hours)
                    response = admin.get_random_response("user_muted", username=username, hours=mute_hours)
                    response += admin.get_random_response("mistake_footer")
                    await context.bot.send_message(chat_id=chat_id, text=response)
                    logger.warning(f"SPAM MUTED: user={user_id} @{username} hours={mute_hours} conf={confidence:.2f}")
                except Exception as mute_err:
                    logger.error(f"Failed to mute user: {mute_err}")
                    # Fall back to warning
                    new_warnings = admin.warn_user(user_id)
                    response = admin.get_random_response("user_warned", username=username)
                    await context.bot.send_message(chat_id=chat_id, text=response)
            else:
                # Warn for lower confidence
                new_warnings = admin.warn_user(user_id)
                if "rate_limited" in reason:
                    response = admin.get_random_response("rate_limited", username=username)
                else:
                    response = admin.get_random_response("user_warned", username=username)
                response += admin.get_random_response("mistake_footer")

                await context.bot.send_message(chat_id=chat_id, text=response)
                logger.warning(f"SPAM WARNED: user={user_id} @{username} warnings={new_warnings} conf={confidence:.2f}")
            
            return True
            
    except Exception as e:
        logger.error(f"JarvisAdmin spam check error: {e}")
        # Fallback to simple pattern matching
        text_lower = text.lower()
        for pattern in SPAM_PATTERNS:
            if pattern in text_lower:
                try:
                    chat_id = update.effective_chat.id
                    message_id = update.message.message_id
                    username = update.effective_user.username or "unknown"
                    await context.bot.delete_message(chat_id=chat_id, message_id=message_id)
                    await context.bot.ban_chat_member(chat_id=chat_id, user_id=user_id)
                    await context.bot.send_message(
                        chat_id=chat_id,
                        text=f"removed spam. @{username} banned.\n\nif this was a mistake, reach out to @MattFromKr8tiv.",
                    )
                    return True
                except:
                    pass
    
    return False


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle non-command messages and respond when appropriate."""
    if not update.message or not update.message.text:
        return

    text = update.message.text.strip()
    user_id = update.effective_user.id if update.effective_user else 0
    import sys
    # Sanitize text for Windows console (remove emojis/special chars)
    safe_text = text[:60].encode('ascii', 'replace').decode('ascii')
    print(f"[MSG] user_id={user_id} text={safe_text}", flush=True)
    sys.stdout.flush()
    logger.info(f"Message from {user_id}: {text[:60]}")
    username = update.effective_user.username or "" if update.effective_user else ""

    # Check if user is admin
    admin_ids_str = os.environ.get("TELEGRAM_ADMIN_IDS", "")
    admin_ids = [int(x.strip()) for x in admin_ids_str.split(",") if x.strip().isdigit()]
    is_admin = user_id in admin_ids

    # Spam detection - skip for admin
    if not is_admin:
        is_spam = await check_and_ban_spam(update, context, text, user_id)
        if is_spam:
            return  # Message was spam, user banned, stop processing

    # Terminal command handling (admin only) - prefix with > or /term
    if text.startswith('>') or text.lower().startswith('/term '):
        from tg_bot.services.terminal_handler import get_terminal_handler
        handler = get_terminal_handler()

        if not handler.is_admin(user_id):
            # Silently ignore non-admin terminal attempts
            return

        # Extract command
        if text.startswith('>'):
            cmd = text[1:].strip()
        else:
            cmd = text[6:].strip()  # Remove '/term '

        if not cmd:
            await update.message.reply_text("Usage: > <command> or /term <command>")
            return

        # Execute and reply
        await update.message.reply_text(f"Executing: `{cmd[:50]}{'...' if len(cmd) > 50 else ''}`", parse_mode="Markdown")
        result = await handler.execute(cmd, user_id)
        await update.message.reply_text(f"```\n{result}\n```", parse_mode="Markdown")
        return

    # Check if message seems directed at Jarvis
    should_reply = _should_reply(update, context)
    
    # Even for admin, only respond if message seems directed at Jarvis
    if is_admin:
        should_reply = _is_message_for_jarvis(text, update)
    
    if not should_reply:
        return

    chat_id = update.effective_chat.id if update.effective_chat else 0

    # Admin coding request detection - execute via Claude CLI
    if is_admin:
        try:
            from core.telegram_console_bridge import get_console_bridge
            bridge = get_console_bridge()
            
            # Store message in memory for context
            bridge.memory.add_message(user_id, username, "user", text, chat_id)
            
            # Check if this is a coding/dev request
            if bridge.is_coding_request(text):
                from tg_bot.services.claude_cli_handler import get_claude_cli_handler
                cli_handler = get_claude_cli_handler()
                
                # Send confirmation
                confirm_msg = await update.message.reply_text(
                    "🔄 <b>Processing coding request...</b>\n\n"
                    f"<i>{text[:200]}{'...' if len(text) > 200 else ''}</i>",
                    parse_mode=ParseMode.HTML
                )
                
                # Execute via Claude CLI
                async def send_status(msg: str):
                    try:
                        await confirm_msg.edit_text(msg, parse_mode=ParseMode.HTML)
                    except:
                        pass
                
                success, summary, output = await cli_handler.execute(
                    text, user_id, send_update=send_status
                )
                
                # Send result back to Telegram
                status_emoji = "✅" if success else "⚠️"
                result_msg = (
                    f"{status_emoji} <b>Coding Task Complete</b>\n\n"
                    f"<b>Summary:</b>\n{summary}\n\n"
                    f"<b>Details:</b>\n<pre>{output[:2000]}</pre>"
                )
                
                await update.message.reply_text(result_msg, parse_mode=ParseMode.HTML)
                
                # Store response in memory
                bridge.memory.add_message(user_id, "jarvis", "assistant", summary, chat_id)
                
                logger.info(f"Completed coding request for {user_id}: {success}")
                return
        except Exception as e:
            logger.error(f"Claude CLI error: {e}")
            await update.message.reply_text(
                f"⚠️ Coding request failed: {str(e)[:200]}",
                parse_mode=ParseMode.HTML
            )

    # Skip cooldown for admin
    if not is_admin:
        cooldown = int(os.environ.get("TG_REPLY_COOLDOWN_SECONDS", "12"))
        now = time.time()
        last = _LAST_REPLY_AT.get(chat_id, 0.0)
        if now - last < cooldown:
            return
        _LAST_REPLY_AT[chat_id] = now

    responder = _get_chat_responder()
    logger.info(f"Generating reply for admin={is_admin} user={user_id}")
    try:
        reply = await responder.generate_reply(
            text=text,
            username=username,
            chat_title=(update.effective_chat.title if update.effective_chat else ""),
            is_private=update.effective_chat.type == "private" if update.effective_chat else False,
            user_id=user_id,
            chat_id=chat_id,
        )
        logger.info(f"Reply generated: {reply[:50] if reply else 'EMPTY'}")
    except Exception as e:
        logger.error(f"Reply generation failed: {e}")
        reply = None

    if reply:
        # Cleanse sensitive info before sending to public chat
        safe_reply = _cleanse_sensitive_info(reply)
        await update.message.reply_text(
            safe_reply,
            disable_web_page_preview=True,
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
    app.add_handler(CommandHandler("stocks", stocks))
    app.add_handler(CommandHandler("st", stocks))  # Alias for /stocks
    app.add_handler(CommandHandler("equities", stocks))  # Alias for /stocks
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
    app.add_handler(CommandHandler("metrics", metrics))
    app.add_handler(CommandHandler("clistats", clistats))
    app.add_handler(CommandHandler("stats", clistats))  # Alias for /clistats
    app.add_handler(CommandHandler("queue", cliqueue))
    app.add_handler(CommandHandler("q", cliqueue))  # Alias for /queue
    app.add_handler(CommandHandler("uptime", uptime))
    app.add_handler(CommandHandler("brain", brain))
    app.add_handler(CommandHandler("code", code))
    app.add_handler(CommandHandler("remember", remember))
    app.add_handler(CommandHandler("modstats", modstats))
    app.add_handler(CommandHandler("unban", unban))
    app.add_handler(CommandHandler("upgrades", upgrades))
    app.add_handler(CommandHandler("xbot", xbot))
    app.add_handler(CommandHandler("paper", paper))

    # Treasury Trading Commands
    app.add_handler(CommandHandler("report", report))
    app.add_handler(CommandHandler("sentiment", report))  # Alias for /report
    app.add_handler(CommandHandler("balance", balance))
    app.add_handler(CommandHandler("positions", positions))
    app.add_handler(CommandHandler("settings", settings))
    app.add_handler(CommandHandler("modstats", modstats))
    app.add_handler(CommandHandler("addscam", addscam))
    app.add_handler(CommandHandler("trust", trust))
    app.add_handler(CommandHandler("trustscore", trustscore))
    app.add_handler(CommandHandler("warn", warn))
    app.add_handler(CommandHandler("report", report))
    app.add_handler(CommandHandler("togglemedia", toggle_media))

    app.add_handler(CallbackQueryHandler(button_callback))

    # Anti-scam protection (runs BEFORE regular message handler)
    global _ANTISCAM
    if ANTISCAM_AVAILABLE and config.admin_ids:
        _ANTISCAM = AntiScamProtection(
            bot=app.bot,
            admin_ids=list(config.admin_ids),
            auto_restrict=True,
            auto_delete=True,
            alert_admins=True,
        )
        antiscam_handler = create_antiscam_handler(_ANTISCAM)
        app.add_handler(antiscam_handler, group=-1)  # Priority group - runs first
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
