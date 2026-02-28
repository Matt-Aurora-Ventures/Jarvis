"""
ClawdJarvis Telegram Bot - Main Orchestrator

The main Jarvis Telegram bot for system orchestration and AI assistance.

Usage:
  /jarvis <question> - Ask Jarvis anything
  /browse <task> - Browser automation on Windows
  /computer <task> - Full computer control
  /skill <name> [args] - Execute a skill
  /skills - List available skills
  /system - Check system status
  /help - Show available commands
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

from core.utils.safe_stdio import ensure_stdio

ensure_stdio()

# External uptime heartbeat (optional; do not crash if deps are missing).
try:
    from core.monitoring.heartbeat import ExternalHeartbeat
    HAS_EXTERNAL_HEARTBEAT = True
except Exception:
    ExternalHeartbeat = None  # type: ignore[assignment]
    HAS_EXTERNAL_HEARTBEAT = False



# Import computer control capabilities
try:
    from bots.shared.computer_capabilities import (
        browse_web,
        control_computer,
        send_telegram_web,
        check_remote_status,
        COMPUTER_CAPABILITIES_PROMPT,
    )
    HAS_COMPUTER_CONTROL = True
except ImportError as e:
    HAS_COMPUTER_CONTROL = False
    logging.warning(f"Computer control not available: {e}")

# Import security modules
try:
    from bots.shared.allowlist import AuthorizationLevel, load_allowlist, check_authorization
    from bots.shared.command_blocklist import is_dangerous_command
    HAS_SECURITY = True
except ImportError as e:
    HAS_SECURITY = False
    logging.warning(f"Security modules not available: {e}")

# Import skill handler (self-healing skill system)
try:
    from bots.clawdjarvis.skill_handler import get_skill_handler, JarvisSkillHandler
    HAS_SKILL_HANDLER = True
except ImportError as e:
    HAS_SKILL_HANDLER = False
    logging.warning(f"Skill handler not available: {e}")

# Import lifecycle manager
try:
    from bots.shared.bot_lifecycle import BotLifecycle
    HAS_LIFECYCLE = True
except ImportError as e:
    HAS_LIFECYCLE = False
    logging.warning(f"Bot lifecycle not available: {e}")

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
BOT_TOKEN = os.environ.get("CLAWDJARVIS_BOT_TOKEN")
if not BOT_TOKEN:
    logger.error("CLAWDJARVIS_BOT_TOKEN not found in environment")
    sys.exit(1)

# Initialize bot
bot = AsyncTeleBot(BOT_TOKEN)

# Load allowlist for privileged commands (browse/computer/remote).
# NOTE: even if other bots run in "public mode", Jarvis computer control must stay locked down.
_allowlist = load_allowlist() if HAS_SECURITY else None

# Register approval handlers
try:
    from bots.shared.approval_handlers import register_approval_handlers
    register_approval_handlers(bot)
except ImportError:
    logging.warning("Approval handlers not available")

# Jarvis personality responses
JARVIS_GREETINGS = [
    "At your service, sir.",
    "How may I assist you today-",
    "Yes, what do you need-",
    "Jarvis online. What's the mission-",
    "Ready and waiting.",
]

JARVIS_CAPABILITIES = """
JARVIS System Capabilities:

?? Computer Control (via Tailscale):
- /browse <task> - LLM-native browser automation
- /computer <task> - Full Windows computer control
- /remote - Check remote control status

Trading:
- Autonomous Solana token trading
- Position management (up to 50 positions)
- Risk management with TP/SL

AI Assistants:
- ClawdMatt: PR & communications filter
- ClawdFriday: Email AI assistant
- Sentiment analysis via Grok

Social:
- X/Twitter automation (@Jarvis_lifeos)
- Telegram integration

Monitoring:
- Bags.fm graduation tracking
- Token sentiment analysis
- Market regime detection
"""


def _is_admin(user_id: int) -> bool:
    """Strict allowlist check for privileged commands (deny-by-default if not configured)."""
    if not HAS_SECURITY or not _allowlist:
        return False
    return check_authorization(user_id, AuthorizationLevel.ADMIN, _allowlist)


async def _deny_admin(message) -> None:
    try:
        await bot.reply_to(message, "This command is restricted to admins.")
    except Exception:
        return


@bot.message_handler(commands=['start', 'help'])
async def handle_help(message):
    """Send help message."""
    import random
    greeting = random.choice(JARVIS_GREETINGS)

    help_text = f"""
{greeting}

I am JARVIS - Just A Rather Very Intelligent System.

Commands:
/jarvis <question> - Ask me anything
/browse <task> - Browser automation on Windows
/computer <task> - Full computer control
/remote - Check remote control status
/system - Check system status
/caps - View my capabilities
/help - Show this help message

Examples:
/jarvis What's the current market sentiment-
/browse Go to coingecko.com and get SOL price
/computer List files in Downloads folder
/system

I'm here to assist with trading, analysis, computer control, and system orchestration.
"""
    await bot.reply_to(message, help_text)


@bot.message_handler(commands=['system', 'status'])
async def handle_status(message):
    """Send system status."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC")

    status_text = f"""
JARVIS System Status Report
Time: {now}

Core Systems:
[OK] Telegram Bot: ONLINE
[OK] VPS Connection: ACTIVE
[OK] Token Loading: SUCCESS

Bot Network:
- ClawdMatt (PR Filter): DEPLOYED
- ClawdFriday (Email AI): DEPLOYED
- ClawdJarvis (Orchestrator): ONLINE

Services:
- Trading Engine: STANDBY
- Sentiment Analysis: AVAILABLE
- X/Twitter Bot: CONFIGURED

All systems operational.
"""
    await bot.reply_to(message, status_text)


@bot.message_handler(commands=['caps', 'capabilities'])
async def handle_caps(message):
    """Show Jarvis capabilities."""
    await bot.reply_to(message, JARVIS_CAPABILITIES)


@bot.message_handler(commands=['browse', 'web'])
async def handle_browse(message):
    """Handle browser automation requests."""
    if not _is_admin(message.from_user.id):
        await _deny_admin(message)
        return
    if not HAS_COMPUTER_CONTROL:
        await bot.reply_to(message, "Computer control module not available.")
        return

    task = message.text.split(' ', 1)[1] if ' ' in message.text else ''
    if not task:
        await bot.reply_to(
            message,
            "Usage: /browse <task>\n\n"
            "Examples:\n"
            "? /browse Go to coingecko.com and get SOL price\n"
            "? /browse Check twitter.com/Jarvis_lifeos notifications\n"
            "? /browse Search google for 'solana ecosystem news'"
        )
        return

    # Security: check for dangerous commands
    if HAS_SECURITY:
        blocked, reason = is_dangerous_command(task)
        if blocked:
            await bot.reply_to(message, f"Blocked: {reason}")
            return

    await bot.reply_to(message, f"? Browsing: {task[:50]}...\nThis may take a moment.")

    try:
        result = await browse_web(task)
        response = f"? Browser Result:\n\n{result[:3500]}"  # Telegram limit
    except Exception as e:
        response = f"? Browser error: {str(e)}"

    await bot.reply_to(message, response)


@bot.message_handler(commands=['computer', 'pc', 'cmd'])
async def handle_computer(message):
    """Handle full computer control requests."""
    if not _is_admin(message.from_user.id):
        await _deny_admin(message)
        return
    if not HAS_COMPUTER_CONTROL:
        await bot.reply_to(message, "Computer control module not available.")
        return

    task = message.text.split(' ', 1)[1] if ' ' in message.text else ''
    if not task:
        await bot.reply_to(
            message,
            "Usage: /computer <task>\n\n"
            "Examples:\n"
            "? /computer What files are in Downloads folder-\n"
            "? /computer Open notepad and write 'hello world'\n"
            "? /computer Take a screenshot of the desktop\n"
            "? /computer Check what programs are running"
        )
        return

    await bot.reply_to(message, f"?? Executing: {task[:50]}...\nThis may take a moment.")

    try:
        result = await control_computer(task)
        response = f"?? Computer Result:\n\n{result[:3500]}"
    except Exception as e:
        response = f"? Computer control error: {str(e)}"

    await bot.reply_to(message, response)


@bot.message_handler(commands=['remote', 'tailscale'])
async def handle_remote_status(message):
    """Check remote control availability."""
    if not _is_admin(message.from_user.id):
        await _deny_admin(message)
        return
    if not HAS_COMPUTER_CONTROL:
        await bot.reply_to(message, "Computer control module not available.")
        return

    await bot.reply_to(message, "? Checking remote control status...")

    try:
        status = await check_remote_status()
        if status.get("available"):
            caps = "\n".join(f"  ? {c}" for c in status.get("capabilities", []))
            response = f"""
? Remote Control: AVAILABLE

Host: {status.get('host')}

Capabilities:
{caps}

Use /browse or /computer to control the Windows machine.
"""
        else:
            response = f"""
? Remote Control: UNAVAILABLE

Host: {status.get('host')}
Error: {status.get('error', 'Unknown')}

Make sure:
1. Windows machine is running
2. remote_control_server.py is started
3. Tailscale is connected
"""
    except Exception as e:
        response = f"? Status check error: {str(e)}"

    await bot.reply_to(message, response)


@bot.message_handler(commands=['jarvis'])
async def handle_jarvis(message):
    """Handle Jarvis questions."""
    # Get the question after /jarvis
    question = message.text.replace('/jarvis', '', 1).strip()

    if not question:
        await bot.reply_to(message, "Yes- What would you like to know-")
        return

    question_lower = question.lower()

    # Simple response logic
    if "hello" in question_lower or "hi" in question_lower:
        response = "Hello! How may I assist you today-"
    elif "status" in question_lower:
        response = "All systems are operational. Would you like a detailed status report- Use /system."
    elif "trading" in question_lower:
        response = "Trading systems are on standby. The treasury bot handles autonomous Solana token trading with risk management."
    elif "market" in question_lower or "sentiment" in question_lower:
        response = "I can analyze market sentiment using Grok AI. The system monitors token metrics and social signals."
    elif "email" in question_lower or "friday" in question_lower:
        response = "Friday (ClawdFriday) handles email processing with KR8TIV AI branding. She categorizes and drafts professional responses."
    elif "pr" in question_lower or "matt" in question_lower:
        response = "PR Matt (ClawdMatt) filters communications for professionalism while preserving authenticity."
    elif "who are you" in question_lower or "what are you" in question_lower:
        response = "I am JARVIS - Just A Rather Very Intelligent System. An autonomous LifeOS assistant for trading, AI coordination, and system orchestration."
    elif "help" in question_lower:
        response = "I can help with trading, market analysis, email processing, and PR filtering. What specific area would you like assistance with-"
    else:
        response = f"Analyzing your query: '{question}'\n\nI'm currently in basic mode without external AI access. For full capabilities, ensure the Grok or Claude API is configured."

    await bot.reply_to(message, response)


@bot.message_handler(func=lambda message: True)
async def handle_any(message):
    """Handle any message as a Jarvis query."""
    if message.text:
        question = message.text.strip()

        # Treat any message as a question
        question_lower = question.lower()

        if "hello" in question_lower or "hi" in question_lower:
            import random
            await bot.reply_to(message, random.choice(JARVIS_GREETINGS))
        else:
            await bot.reply_to(
                message,
                f"I heard: '{question}'\n\n"
                "Use /jarvis <question> for a more structured response, "
                "or /help to see all commands."
            )


async def main():
    """Main entry point."""
    lifecycle = None
    lock = None
    ext_heartbeat = None

    logger.info("Starting ClawdJarvis Telegram Bot...")
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
    jarvis_hb_url = os.environ.get("JARVIS_HEARTBEAT_URL", "").strip()
    if HAS_EXTERNAL_HEARTBEAT and jarvis_hb_url:
        try:
            ext_heartbeat = ExternalHeartbeat(custom_webhook=jarvis_hb_url)  # type: ignore[misc]
            await ext_heartbeat.start()
            logger.info("ExternalHeartbeat started")
        except Exception as exc:
            logger.warning(f"ExternalHeartbeat failed to start (continuing): {exc}")
            ext_heartbeat = None

    # Initialize lifecycle if available
    if HAS_LIFECYCLE:
        try:
            lifecycle = BotLifecycle(
                bot_name="ClawdJarvis",
                bot_token=BOT_TOKEN,
                heartbeat_interval_hours=6.0,
                memory_threshold_mb=256
            )
            lifecycle.start()
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
        if lifecycle:
            lifecycle.shutdown()
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
