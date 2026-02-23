"""
ClawdJarvis - Conversational Life Control

This version responds to natural language, not just slash commands.
Just talk to Jarvis and it will do what you need.

Examples:
- "Check my email"
- "What's on my calendar today?"
- "Send John an email about the meeting tomorrow"
- "Deploy the website changes"
- "Check my Google Cloud billing"
"""

import os
import sys
import logging
import asyncio
import atexit
import re
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

# Import capabilities
try:
    from shared.computer_capabilities import (
        browse_web,
        control_computer,
        check_remote_status,
    )
    HAS_REMOTE = True
except ImportError as e:
    HAS_REMOTE = False
    logging.warning(f"Remote control not available: {e}")

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
                logger.error("Another instance running; exiting.")
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
        logger.error("Another instance running; exiting.")
        sys.exit(1)
    lock_file.write(str(os.getpid()))
    lock_file.flush()
    _LOCK_HANDLE = lock_file
    atexit.register(_release_instance_lock)


# Load tokens
def load_tokens():
    tokens_path = Path("/root/clawdbots/tokens.env")
    if tokens_path.exists():
        for line in tokens_path.read_text().splitlines():
            if line.strip() and not line.startswith('#') and '=' in line:
                k, v = line.split('=', 1)
                os.environ.setdefault(k.strip(), v.strip())


load_tokens()

BOT_TOKEN = os.environ.get("CLAWDJARVIS_BOT_TOKEN")
if not BOT_TOKEN:
    logger.error("CLAWDJARVIS_BOT_TOKEN not found")
    sys.exit(1)

_acquire_single_instance_lock("clawdjarvis")

bot = AsyncTeleBot(BOT_TOKEN)


# ============================================
# INTENT DETECTION - What does the user want?
# ============================================

def detect_intent(text: str) -> dict:
    """
    Detect what the user wants from their message.
    Returns intent type and extracted entities.
    """
    text_lower = text.lower().strip()

    # Email patterns
    email_patterns = [
        r'\b(email|mail|gmail|inbox|send.*email|check.*email|read.*email)\b',
        r'\b(compose|draft|reply|forward)\b.*\b(email|mail)\b',
    ]
    if any(re.search(p, text_lower) for p in email_patterns):
        return {"intent": "email", "request": text}

    # Calendar patterns
    calendar_patterns = [
        r'\b(calendar|schedule|meeting|appointment|event)\b',
        r"\b(what's|whats|show).*\b(today|tomorrow|this week)\b",
        r'\b(add|create|schedule).*\b(meeting|event|appointment)\b',
    ]
    if any(re.search(p, text_lower) for p in calendar_patterns):
        return {"intent": "calendar", "request": text}

    # Drive/Docs patterns
    drive_patterns = [
        r'\b(drive|docs|sheets|slides|document|spreadsheet)\b',
        r'\b(create|open|edit|share).*\b(doc|document|file|spreadsheet)\b',
    ]
    if any(re.search(p, text_lower) for p in drive_patterns):
        return {"intent": "drive", "request": text}

    # Deploy/Server patterns
    deploy_patterns = [
        r'\b(deploy|server|hosting|hostinger|website)\b',
        r'\b(push|upload|publish).*\b(code|changes|site)\b',
        r'\b(ssh|connect).*\b(server|vps)\b',
    ]
    if any(re.search(p, text_lower) for p in deploy_patterns):
        return {"intent": "deploy", "request": text}

    # Firebase/Cloud patterns
    cloud_patterns = [
        r'\b(firebase|gcloud|cloud|gcp|google cloud)\b',
        r'\b(billing|cost|spend|charges)\b',
        r'\b(api|apis|service|services)\b.*\b(enable|disable|check)\b',
    ]
    if any(re.search(p, text_lower) for p in cloud_patterns):
        return {"intent": "cloud", "request": text}

    # Wallet/Crypto patterns
    wallet_patterns = [
        r'\b(wallet|solana|sol|crypto|balance|token)\b',
        r'\b(send|transfer|swap|trade)\b.*\b(sol|token|crypto)\b',
    ]
    if any(re.search(p, text_lower) for p in wallet_patterns):
        return {"intent": "wallet", "request": text}

    # Phone patterns
    phone_patterns = [
        r'\b(phone|android|mobile|adb)\b',
        r'\b(call|text|sms|message)\b',
    ]
    if any(re.search(p, text_lower) for p in phone_patterns):
        return {"intent": "phone", "request": text}

    # Browser/Web patterns
    browse_patterns = [
        r'\b(browse|search|google|look up|find|website)\b',
        r'\b(go to|open|visit|check)\b.*\b(\.com|\.org|\.io|site|page)\b',
    ]
    if any(re.search(p, text_lower) for p in browse_patterns):
        return {"intent": "browse", "request": text}

    # Computer control patterns
    computer_patterns = [
        r'\b(screenshot|desktop|folder|file|download)\b',
        r'\b(open|run|start|close)\b.*\b(app|program|application)\b',
    ]
    if any(re.search(p, text_lower) for p in computer_patterns):
        return {"intent": "computer", "request": text}

    # Status/Help patterns
    if re.search(r'\b(status|help|what can you do|capabilities)\b', text_lower):
        return {"intent": "status", "request": text}

    # Greeting patterns
    if re.search(r'^(hi|hello|hey|sup|yo|good morning|good afternoon)[\s!?.]*$', text_lower):
        return {"intent": "greeting", "request": text}

    # Default: treat as general request
    return {"intent": "general", "request": text}


# ============================================
# REQUEST HANDLERS
# ============================================

async def handle_email_request(request: str) -> str:
    """Handle email-related requests."""
    if not HAS_REMOTE:
        return "Remote control not available. Cannot access Gmail."

    result = await browse_web(f"""
Go to Gmail (https://mail.google.com).
{request}

If checking email: Show recent emails with subjects and senders.
If composing: Click Compose, fill in details, send.
Report what you did and the result.
""")

    if result.get("success"):
        return f"**Email:**\n\n{result.get('result', 'Done')[:3000]}"
    return f"Email error: {result.get('error', 'Unknown error')}"


async def handle_calendar_request(request: str) -> str:
    """Handle calendar-related requests."""
    if not HAS_REMOTE:
        return "Remote control not available. Cannot access Calendar."

    result = await browse_web(f"""
Go to Google Calendar (https://calendar.google.com).
{request}

Show events with time, title, and location.
If creating event: Use the + button, fill in details, save.
Report what you see or what you did.
""")

    if result.get("success"):
        return f"**Calendar:**\n\n{result.get('result', 'Done')[:3000]}"
    return f"Calendar error: {result.get('error', 'Unknown error')}"


async def handle_drive_request(request: str) -> str:
    """Handle Drive/Docs requests."""
    if not HAS_REMOTE:
        return "Remote control not available. Cannot access Drive."

    result = await browse_web(f"""
Go to Google Drive (https://drive.google.com).
{request}

If creating doc: Click + New, select type, give it a name.
If searching: Use the search bar.
Report what you found or created.
""")

    if result.get("success"):
        return f"**Drive:**\n\n{result.get('result', 'Done')[:3000]}"
    return f"Drive error: {result.get('error', 'Unknown error')}"


async def handle_deploy_request(request: str) -> str:
    """Handle deployment requests."""
    if not HAS_REMOTE:
        return "Remote control not available. Cannot deploy."

    if 'deploy' in request.lower():
        result = await control_computer(f"""
Deployment request: {request}

Steps:
1. SSH to the server
2. cd to website directory
3. git pull origin main
4. npm install (if needed)
5. npm run build (if needed)
6. Restart services

Report deployment status.
""")
    else:
        result = await browse_web(f"""
Go to Hostinger panel (https://hpanel.hostinger.com).
{request}
Report what you see or did.
""")

    if result.get("success"):
        return f"**Deploy:**\n\n{result.get('result', result.get('output', 'Done'))[:3000]}"
    return f"Deploy error: {result.get('error', 'Unknown error')}"


async def handle_cloud_request(request: str) -> str:
    """Handle Google Cloud/Firebase requests."""
    if not HAS_REMOTE:
        return "Remote control not available. Cannot access Cloud."

    # Determine which console
    if 'firebase' in request.lower():
        url = 'https://console.firebase.google.com'
    elif 'billing' in request.lower():
        url = 'https://console.cloud.google.com/billing'
    else:
        url = 'https://console.cloud.google.com'

    result = await browse_web(f"""
Go to {url}.
{request}

Report what you see - projects, billing, services, etc.
""")

    if result.get("success"):
        return f"**Cloud:**\n\n{result.get('result', 'Done')[:3000]}"
    return f"Cloud error: {result.get('error', 'Unknown error')}"


async def handle_wallet_request(request: str) -> str:
    """Handle crypto wallet requests."""
    if not HAS_REMOTE:
        return "Remote control not available. Cannot access wallet."

    result = await control_computer(f"""
Solana wallet operation: {request}

Access the treasury wallet and:
- If checking balance: Show SOL and token balances
- If sending: Prepare transaction (DO NOT execute without confirmation)
- If swapping: Use Jupiter aggregator

Report the result.
""")

    if result.get("success"):
        return f"**Wallet:**\n\n{result.get('result', result.get('output', 'Done'))[:3000]}"
    return f"Wallet error: {result.get('error', 'Unknown error')}"


async def handle_phone_request(request: str) -> str:
    """Handle phone control requests."""
    if not HAS_REMOTE:
        return "Remote control not available. Cannot access phone."

    result = await control_computer(f"""
Android phone control via ADB over Tailscale:

First connect: adb connect 100.88.183.6:5555

Then: {request}

Report the result.
""")

    if result.get("success"):
        return f"**Phone:**\n\n{result.get('result', result.get('output', 'Done'))[:3000]}"
    return f"Phone error: {result.get('error', 'Unknown error')}"


async def handle_browse_request(request: str) -> str:
    """Handle browser requests."""
    if not HAS_REMOTE:
        return "Remote control not available. Cannot browse."

    result = await browse_web(request)

    if result.get("success"):
        return f"**Browser:**\n\n{result.get('result', 'Done')[:3000]}"
    return f"Browse error: {result.get('error', 'Unknown error')}"


async def handle_computer_request(request: str) -> str:
    """Handle computer control requests."""
    if not HAS_REMOTE:
        return "Remote control not available."

    result = await control_computer(request)

    if result.get("success"):
        return f"**Computer:**\n\n{result.get('result', result.get('output', 'Done'))[:3000]}"
    return f"Computer error: {result.get('error', 'Unknown error')}"


async def handle_general_request(request: str) -> str:
    """Handle general requests - route to computer control."""
    if not HAS_REMOTE:
        return "Remote control not available."

    result = await control_computer(f"""
Execute this request: {request}

You have access to:
- Browser (logged into Google, Hostinger, etc.)
- SSH to servers
- Full computer control
- File system access

Do whatever is needed to complete this request and report the result.
""")

    if result.get("success"):
        return f"{result.get('result', result.get('output', 'Done'))[:3500]}"
    return f"Error: {result.get('error', 'Unknown error')}"


# ============================================
# BOT HANDLERS
# ============================================

@bot.message_handler(commands=['start', 'help'])
async def handle_help(message):
    """Send help message."""
    help_text = """
**Jarvis - Full Life Control**

Just talk to me naturally. I can:

- **Email:** "Check my email" / "Send John an email about..."
- **Calendar:** "What's on my calendar today?" / "Schedule a meeting..."
- **Drive:** "Create a doc called..." / "Find the spreadsheet..."
- **Deploy:** "Deploy the website" / "Check server status"
- **Cloud:** "Check GCP billing" / "List Firebase projects"
- **Wallet:** "Check my SOL balance" / "What tokens do I have?"
- **Phone:** "Check battery" / "Take a screenshot"
- **Browse:** "Go to coingecko and get SOL price"
- **Computer:** "What files are in Downloads?"

Just tell me what you need - no commands required.
"""
    await bot.reply_to(message, help_text, parse_mode='Markdown')


@bot.message_handler(commands=['status', 'system'])
async def handle_status(message):
    """Check system status."""
    remote_status = "UNKNOWN"
    if HAS_REMOTE:
        try:
            status = await check_remote_status()
            remote_status = "ONLINE" if status.get("available") else "OFFLINE"
        except Exception:
            remote_status = "ERROR"

    status_text = f"""
**Jarvis Status**

Remote Control: {remote_status}
Bot: ONLINE

Ready for your commands.
"""
    await bot.reply_to(message, status_text, parse_mode='Markdown')


@bot.message_handler(func=lambda m: True)
async def handle_message(message):
    """
    Handle ANY message as a natural language request.
    This is the conversational interface.
    """
    if not message.text:
        return

    text = message.text.strip()

    # Skip if it's a command we already handled
    if text.startswith('/'):
        return

    # Detect intent
    intent_data = detect_intent(text)
    intent = intent_data["intent"]
    request = intent_data["request"]

    logger.info(f"Detected intent: {intent} for: {text[:50]}...")

    # Handle greetings quickly
    if intent == "greeting":
        await bot.reply_to(message, "At your service. What do you need?")
        return

    # Handle status
    if intent == "status":
        await handle_status(message)
        return

    # Show processing message
    await bot.reply_to(message, f"Processing: {text[:50]}...")

    # Route to appropriate handler
    try:
        if intent == "email":
            response = await handle_email_request(request)
        elif intent == "calendar":
            response = await handle_calendar_request(request)
        elif intent == "drive":
            response = await handle_drive_request(request)
        elif intent == "deploy":
            response = await handle_deploy_request(request)
        elif intent == "cloud":
            response = await handle_cloud_request(request)
        elif intent == "wallet":
            response = await handle_wallet_request(request)
        elif intent == "phone":
            response = await handle_phone_request(request)
        elif intent == "browse":
            response = await handle_browse_request(request)
        elif intent == "computer":
            response = await handle_computer_request(request)
        else:
            response = await handle_general_request(request)

        await bot.reply_to(message, response, parse_mode='Markdown')

    except Exception as e:
        logger.error(f"Handler error: {e}")
        await bot.reply_to(message, f"Error: {str(e)[:500]}")


async def main():
    """Main entry point."""
    logger.info("Starting ClawdJarvis (Conversational)...")
    logger.info(f"Remote control: {'ENABLED' if HAS_REMOTE else 'DISABLED'}")

    await bot.remove_webhook()
    logger.info("Starting polling...")
    await bot.infinity_polling(timeout=60, request_timeout=120)


if __name__ == "__main__":
    asyncio.run(main())
