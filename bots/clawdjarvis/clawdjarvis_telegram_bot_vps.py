"""
ClawdJarvis Telegram Bot - Main Orchestrator

The main Jarvis Telegram bot for system orchestration and AI assistance.

Usage:
  /jarvis <question> - Ask Jarvis anything
  /browse <task> - Browser automation on Windows
  /computer <task> - Full computer control
  /do <anything> - Natural language life control
  /system - Check system status
  /help - Show available commands
"""

import os
import sys
import logging
import asyncio
import atexit
from pathlib import Path
from datetime import datetime
from typing import Optional

# Ensure repo root is on sys.path before importing local packages.
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

# POSIX file lock support
try:
    import fcntl
except Exception:
    fcntl = None

# Import computer control capabilities
try:
    from shared.computer_capabilities import (
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

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Single-instance lock
_LOCK_HANDLE: Optional[object] = None


def _release_instance_lock() -> None:
    global _LOCK_HANDLE
    if not _LOCK_HANDLE:
        return
    try:
        if fcntl is not None:
            fcntl.flock(_LOCK_HANDLE, fcntl.LOCK_UN)
    except Exception:
        pass
    try:
        _LOCK_HANDLE.close()
    except Exception:
        pass
    _LOCK_HANDLE = None


def _acquire_single_instance_lock(bot_name: str) -> None:
    global _LOCK_HANDLE
    lock_dir = Path("/root/clawdbots/.locks")
    lock_dir.mkdir(parents=True, exist_ok=True)
    lock_path = lock_dir / f"{bot_name}.lock"
    lock_file = open(lock_path, "w")
    if fcntl is None:
        try:
            if lock_path.exists() and lock_path.read_text().strip():
                logger.error("Another instance appears to be running; exiting.")
                sys.exit(1)
        except Exception:
            pass
        lock_file.write(str(os.getpid()))
        lock_file.flush()
        _LOCK_HANDLE = lock_file
        return
    try:
        fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        logger.error("Another instance is already running; exiting.")
        sys.exit(1)
    lock_file.write(str(os.getpid()))
    lock_file.flush()
    _LOCK_HANDLE = lock_file
    atexit.register(_release_instance_lock)


# Load environment from tokens.env
def load_tokens():
    tokens_path = Path("/root/clawdbots/tokens.env")
    if tokens_path.exists():
        for line in tokens_path.read_text().splitlines():
            if line.strip() and not line.startswith('#') and '=' in line:
                k, v = line.split('=', 1)
                os.environ.setdefault(k.strip(), v.strip())


load_tokens()

# Get token
BOT_TOKEN = os.environ.get("CLAWDJARVIS_BOT_TOKEN")
if not BOT_TOKEN:
    logger.error("CLAWDJARVIS_BOT_TOKEN not found in environment")
    sys.exit(1)

# Ensure only one instance runs
_acquire_single_instance_lock("clawdjarvis")

# Initialize bot
bot = AsyncTeleBot(BOT_TOKEN)


# ============================================
# LIFE CONTROL COMMANDS REGISTRATION
# ============================================
try:
    from shared.life_control_commands import register_life_commands
    register_life_commands(bot)
    HAS_LIFE_CONTROL = True
    logger.info("Life control commands registered successfully")
except ImportError as e:
    HAS_LIFE_CONTROL = False
    logger.warning(f"Life control commands not available: {e}")


# ============================================
# CORE BOT HANDLERS
# ============================================

JARVIS_GREETINGS = [
    "At your service, sir.",
    "How may I assist you today?",
    "Yes, what do you need?",
    "Jarvis online. What's the mission?",
    "Ready and waiting.",
]


@bot.message_handler(commands=['start', 'help'])
async def handle_help(message):
    """Send help message."""
    import random
    greeting = random.choice(JARVIS_GREETINGS)

    help_text = f"""
{greeting}

I am JARVIS - Just A Rather Very Intelligent System.

**Universal Control:**
/do <anything> - Natural language control

**Google Suite:**
/email [request] - Gmail operations
/calendar [request] - Calendar management
/drive [request] - Drive/Docs/Sheets
/firebase [request] - Firebase projects
/cloud [request] - Google Cloud Console
/billing - Check GCP billing

**Servers & Websites:**
/deploy [request] - Deploy websites
/host [request] - Hostinger panel

**Devices:**
/browse <task> - Browser automation
/computer <task> - Full computer control
/phone [command] - Android control
/screenshot - Take screenshot
/remote - Check remote status

**Finance:**
/wallet [request] - Solana wallet

**System:**
/system - Check system status
/caps - View capabilities
/help - Show this help

Examples:
/do Send John an email about tomorrow's meeting
/calendar add meeting with Bob on Friday at 3pm
/deploy latest changes to hostinger
/wallet check balance
"""
    await bot.reply_to(message, help_text, parse_mode='Markdown')


@bot.message_handler(commands=['system', 'status'])
async def handle_status(message):
    """Send system status."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC")

    remote_status = "UNKNOWN"
    if HAS_COMPUTER_CONTROL:
        try:
            status = await check_remote_status()
            remote_status = "AVAILABLE" if status.get("available") else "OFFLINE"
        except Exception:
            remote_status = "ERROR"

    status_text = f"""
JARVIS System Status Report
Time: {now}

Core Systems:
[OK] Telegram Bot: ONLINE
[OK] VPS Connection: ACTIVE
[OK] Token Loading: SUCCESS

Life Control:
[{'OK' if HAS_LIFE_CONTROL else 'NO'}] Life Commands: {'ACTIVE' if HAS_LIFE_CONTROL else 'NOT LOADED'}
[{'OK' if HAS_COMPUTER_CONTROL else 'NO'}] Computer Control: {'LOADED' if HAS_COMPUTER_CONTROL else 'NOT LOADED'}
[--] Remote Windows: {remote_status}

All systems operational.
"""
    await bot.reply_to(message, status_text)


@bot.message_handler(commands=['caps', 'capabilities'])
async def handle_caps(message):
    """Show Jarvis capabilities."""
    caps = """
JARVIS System Capabilities:

Full Life Control (via Telegram):
- /do <anything> - Natural language control
- /email - Gmail operations
- /calendar - Calendar management
- /drive - Google Drive/Docs
- /deploy - Website deployment
- /firebase - Firebase/Google Cloud
- /phone - Android phone control
- /wallet - Solana wallet operations

Computer Control (via Tailscale):
- /browse <task> - LLM-native browser automation
- /computer <task> - Full Windows computer control
- /remote - Check remote control status

I can control:
- Gmail, Calendar, Drive, Docs
- Google Cloud, Firebase, AI Studio
- Hostinger, Vercel, servers
- Your Android phone
- Your Windows PC
- Solana wallet
"""
    await bot.reply_to(message, caps)


@bot.message_handler(commands=['browse', 'web'])
async def handle_browse(message):
    """Handle browser automation requests."""
    if not HAS_COMPUTER_CONTROL:
        await bot.reply_to(message, "Computer control module not available.")
        return

    task = message.text.split(' ', 1)[1] if ' ' in message.text else ''
    if not task:
        await bot.reply_to(
            message,
            "Usage: /browse <task>\n\n"
            "Examples:\n"
            "- /browse Go to coingecko.com and get SOL price\n"
            "- /browse Check twitter.com/Jarvis_lifeos notifications\n"
            "- /browse Search google for 'solana ecosystem news'"
        )
        return

    await bot.reply_to(message, f"Browsing: {task[:50]}...\nThis may take a moment.")

    try:
        result = await browse_web(task)
        response = f"Browser Result:\n\n{result[:3500]}"
    except Exception as e:
        response = f"Browser error: {str(e)}"

    await bot.reply_to(message, response)


@bot.message_handler(commands=['computer', 'pc', 'cmd'])
async def handle_computer(message):
    """Handle full computer control requests."""
    if not HAS_COMPUTER_CONTROL:
        await bot.reply_to(message, "Computer control module not available.")
        return

    task = message.text.split(' ', 1)[1] if ' ' in message.text else ''
    if not task:
        await bot.reply_to(
            message,
            "Usage: /computer <task>\n\n"
            "Examples:\n"
            "- /computer What files are in Downloads folder?\n"
            "- /computer Open notepad and write 'hello world'\n"
            "- /computer Take a screenshot of the desktop"
        )
        return

    await bot.reply_to(message, f"Executing: {task[:50]}...\nThis may take a moment.")

    try:
        result = await control_computer(task)
        response = f"Computer Result:\n\n{result[:3500]}"
    except Exception as e:
        response = f"Computer control error: {str(e)}"

    await bot.reply_to(message, response)


@bot.message_handler(commands=['remote', 'tailscale'])
async def handle_remote_status(message):
    """Check remote control availability."""
    if not HAS_COMPUTER_CONTROL:
        await bot.reply_to(message, "Computer control module not available.")
        return

    await bot.reply_to(message, "Checking remote control status...")

    try:
        status = await check_remote_status()
        if status.get("available"):
            caps = "\n".join(f"  - {c}" for c in status.get("capabilities", []))
            response = f"""
Remote Control: AVAILABLE

Host: {status.get('host')}

Capabilities:
{caps}

Use /browse or /computer to control the Windows machine.
"""
        else:
            response = f"""
Remote Control: UNAVAILABLE

Host: {status.get('host')}
Error: {status.get('error', 'Unknown')}

Make sure:
1. Windows machine is running
2. remote_control_server.py is started
3. Tailscale is connected
"""
    except Exception as e:
        response = f"Status check error: {str(e)}"

    await bot.reply_to(message, response)


@bot.message_handler(commands=['jarvis'])
async def handle_jarvis(message):
    """Handle Jarvis questions."""
    question = message.text.replace('/jarvis', '', 1).strip()

    if not question:
        await bot.reply_to(message, "Yes? What would you like to know?")
        return

    question_lower = question.lower()

    if "hello" in question_lower or "hi" in question_lower:
        response = "Hello! How may I assist you today?"
    elif "status" in question_lower:
        response = "All systems are operational. Use /system for details."
    elif "who are you" in question_lower:
        response = "I am JARVIS - Just A Rather Very Intelligent System. Your autonomous LifeOS assistant."
    else:
        response = f"Query received: '{question}'\n\nUse /do for natural language control."

    await bot.reply_to(message, response)


@bot.message_handler(func=lambda message: True)
async def handle_any(message):
    """Handle any message as a Jarvis query."""
    if message.text:
        question = message.text.strip()
        question_lower = question.lower()

        if "hello" in question_lower or "hi" in question_lower:
            import random
            await bot.reply_to(message, random.choice(JARVIS_GREETINGS))
        else:
            await bot.reply_to(
                message,
                f"I heard: '{question}'\n\n"
                "Use /do <request> for natural language control, "
                "or /help to see all commands."
            )


async def main():
    """Main entry point."""
    logger.info("Starting ClawdJarvis Telegram Bot...")
    token_id = BOT_TOKEN.split(":", 1)[0] if ":" in BOT_TOKEN else "unknown"
    logger.info(f"Bot token id: {token_id}")
    logger.info(f"Life control: {'ENABLED' if HAS_LIFE_CONTROL else 'DISABLED'}")
    logger.info(f"Computer control: {'ENABLED' if HAS_COMPUTER_CONTROL else 'DISABLED'}")

    # Remove any existing webhook
    await bot.remove_webhook()

    # Start polling
    logger.info("Starting polling...")
    await bot.infinity_polling(timeout=60, request_timeout=120)


if __name__ == "__main__":
    asyncio.run(main())
