"""
ClawdFriday Telegram Bot - Email AI Assistant

A Telegram bot interface for the Friday email AI service.
Helps process and respond to emails with KR8TIV AI branding.

Usage:
  /email <subject> | <body> - Analyze an email
  /draft <topic> - Draft an email response
  /help - Show available commands
  /status - Check bot status
"""

import os
import sys
import logging
import asyncio
from pathlib import Path
from datetime import datetime

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
    logger = logging.getLogger(__name__)
    logger.warning(f"Security modules not available: {e}")

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
BOT_TOKEN = os.environ.get("CLAWDFRIDAY_BOT_TOKEN")
if not BOT_TOKEN:
    logger.error("CLAWDFRIDAY_BOT_TOKEN not found in environment")
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

# Public beta toggle: when enabled, allow everyone to use "safe" bot commands.
# (Keep dangerous capabilities behind auth in bots that have them.)
PUBLIC_MODE = os.environ.get("CLAWDBOT_PUBLIC_MODE", "").strip().lower() in ("1", "true", "yes", "on")

# Initialize lifecycle (optional)
_lifecycle = None

# Email categories
EMAIL_CATEGORIES = [
    ("business_inquiry", ["business", "opportunity", "proposal", "interested"]),
    ("technical_support", ["help", "issue", "problem", "error", "support"]),
    ("partnership", ["partner", "collaboration", "together", "joint"]),
    ("investor", ["invest", "funding", "raise", "capital"]),
    ("spam", ["unsubscribe", "click here", "limited time", "act now"]),
    ("urgent", ["urgent", "asap", "immediately", "critical"]),
]


def check_user_authorized(user_id: int) -> bool:
    """Check if a user is authorized to use the bot."""
    if PUBLIC_MODE:
        return True
    if not HAS_SECURITY or not _allowlist:
        return True  # Development mode - allow all
    return check_authorization(user_id, AuthorizationLevel.OBSERVER, _allowlist)


async def _deny(bot: AsyncTeleBot, message, reason: str = "This bot is currently in private beta.") -> None:
    """Tell unauthorized users why nothing happened (avoid silent failure)."""
    try:
        await bot.reply_to(
            message,
            f"⛔ {reason}\n\nIf you should have access, contact support.",
        )
    except Exception:
        # Never crash handlers on deny
        return


def categorize_email(subject: str, body: str) -> tuple:
    """Categorize an email based on content."""
    combined = f"{subject} {body}".lower()

    for category, keywords in EMAIL_CATEGORIES:
        for keyword in keywords:
            if keyword in combined:
                return category, 0.8

    return "general", 0.5


def generate_draft_response(topic: str, category: str = "general") -> str:
    """Generate a draft email response."""

    greetings = [
        "Thank you for reaching out to KR8TIV AI.",
        "I appreciate you taking the time to contact us.",
        "Thank you for your interest in KR8TIV AI.",
    ]

    closings = [
        "Best regards,\nFriday\nKR8TIV AI Assistant",
        "Looking forward to hearing from you,\nFriday\nKR8TIV AI",
        "Warm regards,\nFriday\nOn behalf of KR8TIV AI",
    ]

    # Category-specific templates
    templates = {
        "business_inquiry": """
{greeting}

We're excited to hear about your interest in working with us. KR8TIV AI
specializes in autonomous AI systems and blockchain integration.

I'd be happy to schedule a call to discuss how we can help with your specific needs.

What times work best for you this week?

{closing}
""",
        "technical_support": """
{greeting}

I understand you're experiencing an issue, and I'm here to help.

To better assist you, could you please provide:
1. A detailed description of the problem
2. Any error messages you've seen
3. Steps to reproduce the issue

Our team typically responds within 24 hours.

{closing}
""",
        "partnership": """
{greeting}

We're always open to exploring partnership opportunities that align with
our mission of building autonomous, intelligent systems.

Could you share more details about:
1. Your organization and its focus
2. The type of partnership you envision
3. Potential mutual benefits

We'd love to explore this further.

{closing}
""",
        "general": """
{greeting}

{topic_response}

Please let us know if you have any other questions or need further assistance.

{closing}
""",
    }

    import random
    greeting = random.choice(greetings)
    closing = random.choice(closings)

    template = templates.get(category, templates["general"])

    if category == "general":
        topic_response = f"Regarding '{topic}', I'd be happy to provide more information or connect you with the right team member."
        return template.format(
            greeting=greeting,
            topic_response=topic_response,
            closing=closing
        )

    return template.format(greeting=greeting, closing=closing)


@bot.message_handler(commands=['start', 'help'])
async def handle_help(message):
    """Send help message."""
    # Security check
    if not check_user_authorized(message.from_user.id):
        await _deny(bot, message)
        return

    help_text = """
Welcome to ClawdFriday - Email AI Assistant

Commands:
/email <subject> | <body> - Analyze an email
/draft <topic> - Draft an email response
/status - Check bot status
/help - Show this help message

Examples:
/email Partnership Inquiry | We'd like to explore...
/draft business inquiry response

I'll help categorize emails and draft professional responses aligned with KR8TIV AI's brand voice.
"""
    await bot.reply_to(message, help_text)


@bot.message_handler(commands=['status'])
async def handle_status(message):
    """Send status message."""
    # Security check
    if not check_user_authorized(message.from_user.id):
        await _deny(bot, message)
        return

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    status_text = f"""
ClawdFriday Status: ONLINE

Bot: @ClawdFriday_bot
Purpose: Email AI Assistant
Mode: Active
Time: {now}

I help process emails and generate professional responses for KR8TIV AI.
"""
    await bot.reply_to(message, status_text)


@bot.message_handler(commands=['email'])
async def handle_email(message):
    """Analyze an email."""
    # Security check
    if not check_user_authorized(message.from_user.id):
        await _deny(bot, message)
        return

    # Get the text after /email
    text = message.text.replace('/email', '', 1).strip()

    if not text:
        await bot.reply_to(message, "Usage: /email <subject> | <body>")
        return

    # Split subject and body
    parts = text.split('|', 1)
    subject = parts[0].strip()
    body = parts[1].strip() if len(parts) > 1 else ""

    # Categorize
    category, confidence = categorize_email(subject, body)

    # Determine priority
    priority = "URGENT" if category == "urgent" else "NORMAL"

    response = f"""
Email Analysis:

Subject: {subject}
Category: {category.upper()}
Priority: {priority}
Confidence: {confidence*100:.0f}%

Suggested action: {"Respond within 4 hours" if priority == "URGENT" else "Respond within 24 hours"}

Use /draft {category} to generate a response template.
"""

    await bot.reply_to(message, response)


@bot.message_handler(commands=['draft'])
async def handle_draft(message):
    """Draft an email response."""
    # Security check
    if not check_user_authorized(message.from_user.id):
        await _deny(bot, message)
        return

    # Get the topic after /draft
    topic = message.text.replace('/draft', '', 1).strip()

    if not topic:
        await bot.reply_to(message, "Usage: /draft <topic or category>")
        return

    # Determine category from topic
    topic_lower = topic.lower()
    category = "general"
    for cat, keywords in EMAIL_CATEGORIES:
        for keyword in keywords:
            if keyword in topic_lower:
                category = cat
                break

    # Generate draft
    draft = generate_draft_response(topic, category)

    response = f"""
Draft Response ({category.upper()}):
---
{draft}
---

Feel free to customize this template for your specific needs.
"""

    await bot.reply_to(message, response)


@bot.message_handler(func=lambda message: True)
async def handle_any(message):
    """Handle any message."""
    # Security check
    if not check_user_authorized(message.from_user.id):
        await _deny(bot, message)
        return

    if message.text:
        await bot.reply_to(
            message,
            "Hi! I'm Friday, your email AI assistant.\n\n"
            "Use /help to see available commands, or:\n"
            "- /email <subject> | <body> - Analyze an email\n"
            "- /draft <topic> - Generate a response template"
        )


async def main():
    """Main entry point."""
    global _lifecycle

    ext_heartbeat = None
    logger.info("Starting ClawdFriday Telegram Bot...")
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
        logger.exception(
            "Failed to acquire Telegram polling lock; exiting to avoid token poller conflicts: %s",
            exc,
        )
        return

    # Optional external heartbeat ping (e.g., healthchecks/betterstack/custom webhook).
    friday_hb_url = os.environ.get("FRIDAY_HEARTBEAT_URL", "").strip()
    if HAS_EXTERNAL_HEARTBEAT and friday_hb_url:
        try:
            ext_heartbeat = ExternalHeartbeat(custom_webhook=friday_hb_url)  # type: ignore[misc]
            await ext_heartbeat.start()
            logger.info("ExternalHeartbeat started")
        except Exception as exc:
            logger.warning(f"ExternalHeartbeat failed to start (continuing): {exc}")
            ext_heartbeat = None

    # Initialize lifecycle if available
    if HAS_LIFECYCLE:
        try:
            _lifecycle = BotLifecycle(
                bot_name="ClawdFriday",
                bot_token=BOT_TOKEN,
                heartbeat_interval_hours=6.0,
                memory_threshold_mb=256
            )
            _lifecycle.start()
            logger.info("Bot lifecycle started (heartbeat + watchdog)")
        except Exception as e:
            logger.error(f"Failed to start lifecycle: {e}")

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

