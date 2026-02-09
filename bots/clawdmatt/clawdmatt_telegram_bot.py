"""
Arsenal Telegram Bot - Marketing Communications Filter

A Telegram bot interface for the Arsenal communications review service.
Reviews messages for brand alignment and risk before publishing.

Usage:
  /review <message> - Review a message for PR compliance
  /help - Show available commands
  /status - Check bot status
"""

import os
import sys
import logging
import asyncio
from pathlib import Path

# Ensure repo root is on sys.path (systemd ExecStart runs a script in a subdir).
_project_root = Path(__file__).resolve().parents[2]
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

try:
    import telebot  # noqa: F401
    from telebot.async_telebot import AsyncTeleBot
except Exception as exc:
    raise SystemExit(
        "Missing Telegram dependency: install `pyTelegramBotAPI` "
        "(module name `telebot`)."
    ) from exc

# External uptime heartbeat (optional; do not crash if deps are missing).
try:
    from core.monitoring.heartbeat import ExternalHeartbeat
    HAS_EXTERNAL_HEARTBEAT = True
except Exception:
    ExternalHeartbeat = None  # type: ignore[assignment]
    HAS_EXTERNAL_HEARTBEAT = False

# Import security modules
try:
    from bots.shared.allowlist import AuthorizationLevel, load_allowlist, check_authorization
    from bots.shared.command_blocklist import is_dangerous_command
    HAS_SECURITY = True
except ImportError as e:
    HAS_SECURITY = False
    logging.warning(f"Security modules not available: {e}")

# Optional: Morning Brief and Scheduler
try:
    from bots.shared.morning_brief import MorningBrief
    from bots.shared.scheduled_tasks import TaskScheduler
    HAS_MORNING_BRIEF = True
except ImportError:
    HAS_MORNING_BRIEF = False

# Optional: Multi-Agent Dispatching
try:
    from bots.shared.multi_agent import MultiAgentDispatcher
    HAS_MULTI_AGENT = True
except ImportError:
    HAS_MULTI_AGENT = False

# Import lifecycle (optional)
try:
    from bots.shared.bot_lifecycle import BotLifecycle
    HAS_LIFECYCLE = True
except ImportError as e:
    HAS_LIFECYCLE = False

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment from tokens.env
def load_tokens():
    tokens_path = Path(__file__).parent.parent.parent / "tokens.env"
    if not tokens_path.exists():
        tokens_path = Path("/root/clawdbots/tokens.env")
    if tokens_path.exists():
        for line in tokens_path.read_text().splitlines():
            if line.strip() and not line.startswith('#') and '=' in line:
                k, v = line.split('=', 1)
                os.environ.setdefault(k.strip(), v.strip())

load_tokens()

# Silence token for heartbeat monitors (also used by unit tests).
HEARTBEAT_OK = "HEARTBEAT_OK"

# Get token
BOT_TOKEN = os.environ.get("CLAWDMATT_BOT_TOKEN")
if not BOT_TOKEN:
    logger.error("CLAWDMATT_BOT_TOKEN not found in environment")
    sys.exit(1)

# Initialize bot
bot = AsyncTeleBot(BOT_TOKEN)

# Register approval handlers
try:
    from bots.shared.approval_handlers import register_approval_handlers
    register_approval_handlers(bot)
except ImportError:
    logging.warning("Approval handlers not available")

# Load allowlist for security
_allowlist = None
if HAS_SECURITY:
    _allowlist = load_allowlist()
    logger.info(f"Loaded allowlist with {len(_allowlist)} authorized users")

# Initialize lifecycle (optional)
_lifecycle = None

# Initialize multi-agent dispatcher (optional)
_dispatcher = None

# Blocked words list
HARD_BLOCKED_WORDS = [
    "fucking", "fuck", "shit", "damn", "hell", "bitch",
    "ass", "crap", "piss", "cock", "dick", "pussy"
]

# Warning patterns
WARNING_PATTERNS = [
    "we're the best", "number one", "guaranteed",
    "100%", "to the moon", "wen moon", "lambo"
]


def check_user_authorized(user_id: int) -> bool:
    """Check if a user is authorized to use the bot."""
    if not HAS_SECURITY or not _allowlist:
        return True  # Development mode - allow all
    return check_authorization(user_id, AuthorizationLevel.OBSERVER, _allowlist)


def review_message(text: str) -> dict:
    """Review a message for PR compliance."""
    concerns = []
    decision = "APPROVED"

    text_lower = text.lower()

    # Check for blocked words
    for word in HARD_BLOCKED_WORDS:
        if word in text_lower:
            concerns.append(f"Blocked word: '{word}'")
            decision = "BLOCKED"

    # Check for warning patterns
    for pattern in WARNING_PATTERNS:
        if pattern in text_lower:
            concerns.append(f"Warning pattern: '{pattern}'")
            if decision != "BLOCKED":
                decision = "NEEDS_REVISION"

    # Build response
    if decision == "APPROVED":
        return {
            "decision": "APPROVED",
            "message": "Message looks good for public posting.",
            "concerns": []
        }
    elif decision == "BLOCKED":
        return {
            "decision": "BLOCKED",
            "message": "Message contains inappropriate content.",
            "concerns": concerns
        }
    else:
        return {
            "decision": "NEEDS_REVISION",
            "message": "Message may need revision before posting.",
            "concerns": concerns
        }


@bot.message_handler(commands=['start', 'help'])
async def handle_help(message):
    """Send help message."""
    # Security check
    if not check_user_authorized(message.from_user.id):
        return  # Silently ignore unauthorized users

    help_text = """
Welcome to Arsenal - PR Filter Bot

Commands:
/review <message> - Review a message for PR compliance
/brief - Generate morning intelligence brief
/status - Check bot status
/help - Show this help message

Example:
/review Check out our amazing new feature!

I'll analyze your message and let you know if it's safe to post publicly.
"""
    await bot.reply_to(message, help_text)


@bot.message_handler(commands=['status'])
async def handle_status(message):
    """Send status message."""
    # Security check
    if not check_user_authorized(message.from_user.id):
        return  # Silently ignore unauthorized users

    status_text = """
Arsenal Status: ONLINE

Bot: @kr8tiv_arsenalcoo_bot
Purpose: Marketing Communications Filter
Mode: Active

I review messages before public posting to maintain professionalism while preserving authenticity.
"""
    await bot.reply_to(message, status_text)


@bot.message_handler(commands=['brief'])
async def handle_brief(message):
    """Generate and send the morning brief."""
    # Security check
    if not check_user_authorized(message.from_user.id):
        return  # Silently ignore unauthorized users

    if not HAS_MORNING_BRIEF:
        await bot.reply_to(message, "Morning brief module not available.")
        return
    try:
        brief = MorningBrief()
        text = await brief.generate_brief()
        await bot.reply_to(message, text)
    except Exception as e:
        logger.error(f"Failed to generate brief: {e}")
        await bot.reply_to(message, f"Failed to generate brief: {e}")


@bot.message_handler(commands=['review'])
async def handle_review(message):
    """Review a message for PR compliance."""
    # Security check
    if not check_user_authorized(message.from_user.id):
        return  # Silently ignore unauthorized users

    # Get the message text after /review
    text = message.text.replace('/review', '', 1).strip()

    if not text:
        await bot.reply_to(message, "Usage: /review <your message to review>")
        return

    # Review the message
    result = review_message(text)

    # Format response
    if result["decision"] == "APPROVED":
        emoji = "OK"
        response = f"[{emoji}] {result['decision']}\n\n{result['message']}"
    elif result["decision"] == "BLOCKED":
        emoji = "X"
        response = f"[{emoji}] {result['decision']}\n\n{result['message']}\n\nConcerns:\n"
        for concern in result["concerns"]:
            response += f"  - {concern}\n"
    else:
        emoji = "!"
        response = f"[{emoji}] {result['decision']}\n\n{result['message']}\n\nConcerns:\n"
        for concern in result["concerns"]:
            response += f"  - {concern}\n"

    await bot.reply_to(message, response)


@bot.message_handler(func=lambda message: True)
async def handle_any(message):
    """Handle any message - check for multi-agent dispatch first, then review."""
    # Security check
    if not check_user_authorized(message.from_user.id):
        return  # Silently ignore unauthorized users

    if not message.text:
        return

    text = message.text.strip()
    if not text:
        return

    # Avoid spamming groups and avoid double-handling commands.
    chat = getattr(message, "chat", None)
    chat_type = getattr(chat, "type", None)
    if chat_type in ("group", "supergroup", "channel"):
        # Only respond in groups if explicitly invoked.
        bot_username = (bot.get_me().username or "").lower()
        invoked = False
        if bot_username and f"@{bot_username}" in text.lower():
            invoked = True
        if text.startswith("/review"):
            invoked = True
        if not invoked:
            return
    if text.startswith("/"):
        return

    if message.text and _dispatcher:
        # Check if this needs multi-agent dispatch
        try:
            result = await _dispatcher.dispatch_and_synthesize(message.text, timeout=120)
            if result:
                await bot.reply_to(message, result)
                return
        except Exception as e:
            logger.error(f"Multi-agent dispatch failed: {e}")
            # Fall through to normal handling

    if message.text:
        # Automatically review any message
        result = review_message(message.text)

        # Format response
        public_group_ids = {
            gid.strip()
            for gid in os.environ.get("CLAWDMATT_PUBLIC_GROUP_IDS", "").split(",")
            if gid.strip()
        }
        chat_id = str(getattr(chat, "id", ""))
        redact_details = chat_id in public_group_ids

        if result["decision"] == "APPROVED":
            await bot.reply_to(message, "[OK] APPROVED - Safe to post!")
        elif result["decision"] == "BLOCKED":
            if redact_details:
                await bot.reply_to(message, "[X] BLOCKED")
            else:
                concerns = "\n".join([f"  - {c}" for c in result["concerns"]])
                await bot.reply_to(message, f"[X] BLOCKED\n\nConcerns:\n{concerns}")
        else:
            if redact_details:
                await bot.reply_to(message, "[!] NEEDS_REVISION")
            else:
                concerns = "\n".join([f"  - {c}" for c in result["concerns"]])
                await bot.reply_to(message, f"[!] NEEDS_REVISION\n\nConcerns:\n{concerns}")


async def main():
    """Main entry point."""
    global _lifecycle, _dispatcher

    ext_heartbeat = None
    logger.info("Starting Arsenal Telegram Bot...")
    token_id = BOT_TOKEN.split(":", 1)[0] if ":" in BOT_TOKEN else "unknown"
    logger.info(f"Bot token id: {token_id}")

    # Prevent multiple pollers using the same token (409 conflicts).
    try:
        from core.utils.instance_lock import acquire_instance_lock

        lock = acquire_instance_lock(
            BOT_TOKEN,
            name="telegram_polling",
            max_wait_seconds=0,
            validate_pid=True,
        )
        if not lock:
            logger.error("Telegram polling lock is already held; exiting to avoid 409 conflicts")
            return
    except Exception as exc:
        logger.warning(f"Could not acquire polling lock (continuing): {exc}")
        lock = None

    # Optional external heartbeat ping (e.g., healthchecks/betterstack/custom webhook).
    matt_hb_url = os.environ.get("MATT_HEARTBEAT_URL", "").strip()
    if HAS_EXTERNAL_HEARTBEAT and matt_hb_url:
        try:
            ext_heartbeat = ExternalHeartbeat(custom_webhook=matt_hb_url)  # type: ignore[misc]
            await ext_heartbeat.start()
            logger.info("ExternalHeartbeat started")
        except Exception as exc:
            logger.warning(f"ExternalHeartbeat failed to start (continuing): {exc}")
            ext_heartbeat = None

    # Initialize lifecycle if available
    if HAS_LIFECYCLE:
        try:
            _lifecycle = BotLifecycle(
                bot_name="Arsenal",
                bot_token=BOT_TOKEN,
                heartbeat_interval_hours=6.0,
                memory_threshold_mb=256
            )
            _lifecycle.start()
            logger.info("Bot lifecycle started (heartbeat + watchdog)")
        except Exception as e:
            logger.error(f"Failed to start lifecycle: {e}")

    # Initialize multi-agent dispatcher
    if HAS_MULTI_AGENT:
        try:
            from bots.shared.coordination import BotCoordinator, BotRole
            coord = BotCoordinator(BotRole.MATT)
            _dispatcher = MultiAgentDispatcher(coordinator=coord, bot_name="matt")
            logger.info("Multi-agent dispatcher initialized")
        except Exception as e:
            logger.warning(f"Multi-agent dispatcher not available: {e}")

    # Schedule morning brief at 08:00 UTC
    if HAS_MORNING_BRIEF:
        scheduler = TaskScheduler()
        brief = MorningBrief()
        scheduler.schedule_daily(8, 0, brief.generate_brief, name="morning_brief")
        scheduler.start()
        logger.info("Morning brief scheduled for 08:00 UTC daily")

    # Remove any existing webhook
    await bot.remove_webhook()

    # Start polling
    logger.info("Starting polling...")
    try:
        await bot.infinity_polling(timeout=60, request_timeout=120)
    finally:
        # Cleanup on shutdown
        if _lifecycle:
            _lifecycle.shutdown()
        try:
            if ext_heartbeat:
                await ext_heartbeat.stop()
        except Exception:
            pass
        try:
            if lock:
                lock.close()
        except Exception:
            pass


if __name__ == "__main__":
    asyncio.run(main())
