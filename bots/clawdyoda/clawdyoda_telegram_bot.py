"""
ClawdYoda Telegram Bot - Chief Innovation Officer (CIO)

Lightweight Telegram interface for "Master Yoda" (innovation + future-tech advisor).
This bot is intentionally non-custodial and does NOT perform any privileged actions.

Usage:
  /yoda <question> - Ask Yoda for innovation/tech strategy guidance
  /status - Check bot status
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

# Import security modules
try:
    from bots.shared.allowlist import AuthorizationLevel, load_allowlist, check_authorization
    from bots.shared.command_blocklist import is_dangerous_command
    HAS_SECURITY = True
except ImportError as e:
    HAS_SECURITY = False
    logging.getLogger(__name__).warning(f"Security modules not available: {e}")

# Import lifecycle (optional)
try:
    from bots.shared.bot_lifecycle import BotLifecycle
    HAS_LIFECYCLE = True
except ImportError:
    HAS_LIFECYCLE = False

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def load_tokens():
    """Load env vars from tokens.env (local dev or VPS)."""
    tokens_path = Path(__file__).parent.parent.parent / "tokens.env"
    if not tokens_path.exists():
        tokens_path = Path("/root/clawdbots/tokens.env")
    if tokens_path.exists():
        for line in tokens_path.read_text().splitlines():
            if line.strip() and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())


load_tokens()

# Silence token for heartbeat monitors (also used by unit tests).
HEARTBEAT_OK = "HEARTBEAT_OK"

# Get token
BOT_TOKEN = os.environ.get("CLAWDYODA_BOT_TOKEN")
if not BOT_TOKEN:
    logger.error("CLAWDYODA_BOT_TOKEN not found in environment")
    sys.exit(1)

# Initialize bot
bot = AsyncTeleBot(BOT_TOKEN)

# Register approval handlers (optional)
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

YODA_GREETINGS = [
    "Hmm. Ask, you may.",
    "The future, cloudy it is... but patterns, I see.",
    "Innovation calls. Speak your question.",
    "Curious, you are. Good.",
]

YODA_HELP = """
Master Yoda (CIO) — Innovation & Future-Tech Advisor

Commands:
/yoda <question>  - Ask about emerging tech, strategy, and innovation
/status           - Bot status
/help             - This message

Examples:
/yoda Predict the AI landscape in 2027
/yoda Should we adopt Rust or stay with TypeScript?
/yoda What's the most important infra upgrade for speed right now?
""".strip()


def check_user_authorized(user_id: int) -> bool:
    """Check if a user is authorized to use the bot."""
    if not HAS_SECURITY or not _allowlist:
        return True  # Dev mode - allow all
    return check_authorization(user_id, AuthorizationLevel.OBSERVER, _allowlist)


def _yoda_brief_answer(question: str) -> str:
    """
    Deterministic, safe-by-default response generator.
    This avoids requiring any external LLM keys to bring the bot online.
    """
    q = (question or "").strip()
    if not q:
        return "Ask a question, you must. Example: `/yoda What should we build next?`"

    ql = q.lower()

    if "quantum" in ql:
        return (
            "Quantum, powerful it will be. Near-term: error correction + niche advantage in optimization.\n"
            "Practical steps now:\n"
            "1) Track vendor roadmaps (Google/IBM/IonQ).\n"
            "2) Audit cryptography for post-quantum readiness.\n"
            "3) Identify workloads that map to QAOA/annealing.\n"
            "Future-proof, your systems become."
        )

    if "infra" in ql or "performance" in ql or "speed" in ql:
        return (
            "Speed you seek. Three levers exist:\n"
            "1) Reduce network round-trips (cache hot data; batch requests).\n"
            "2) Reduce signing latency (session wallet for automation).\n"
            "3) Improve propagation (priority fees, Jito, and reliable RPC).\n"
            "Measure first. Optimize second. Fast, then safe."
        )

    if "rust" in ql:
        return (
            "Rust: safety and speed, yes. But strict it is.\n"
            "If reliability + security matter most: Rust for core components.\n"
            "If iteration speed matters: TypeScript for edges.\n"
            "Hybrid, often best it is."
        )

    if "ai" in ql or "llm" in ql or "agent" in ql:
        return (
            "AI evolves fast. Your advantage: feedback loops and instrumentation.\n"
            "Do this:\n"
            "1) Log failures and outcomes.\n"
            "2) Backtest relentlessly with holdout validation.\n"
            "3) Add guardrails: rate limits, allowlists, circuit breakers.\n"
            "Without measurement, wisdom is guessing."
        )

    return (
        "Solve the present, but design for the future.\n"
        "Tell me: goal, constraints, and what failure looks like.\n"
        "Then a path, we will choose."
    )


@bot.message_handler(commands=["start", "help"])
async def handle_help(message):
    if not check_user_authorized(message.from_user.id):
        return
    await bot.reply_to(message, YODA_HELP)


@bot.message_handler(commands=["status"])
async def handle_status(message):
    if not check_user_authorized(message.from_user.id):
        return
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    text = f"ClawdYoda Status: ONLINE\nTime: {now}\nMode: Innovation & Future-Tech Advisor"
    await bot.reply_to(message, text)


@bot.message_handler(commands=["yoda"])
async def handle_yoda(message):
    if not check_user_authorized(message.from_user.id):
        return

    text = message.text or ""
    question = text.split(" ", 1)[1].strip() if " " in text else ""

    # Block obviously dangerous commands even if asked as a "question".
    if HAS_SECURITY and question and is_dangerous_command(question):
        await bot.reply_to(message, "Denied. Dangerous request detected.")
        return

    import random

    greeting = random.choice(YODA_GREETINGS)
    answer = _yoda_brief_answer(question)
    await bot.reply_to(message, f"{greeting}\n\n{answer}")


async def main():
    global _lifecycle

    ext_heartbeat = None
    logger.info("Starting ClawdYoda Telegram Bot...")

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

    # Optional external heartbeat ping (e.g. healthchecks/betterstack/custom webhook).
    yoda_hb_url = os.environ.get("YODA_HEARTBEAT_URL", "").strip()
    if HAS_EXTERNAL_HEARTBEAT and yoda_hb_url:
        try:
            ext_heartbeat = ExternalHeartbeat(custom_webhook=yoda_hb_url)  # type: ignore[misc]
            await ext_heartbeat.start()
            logger.info("ExternalHeartbeat started")
        except Exception as exc:
            logger.warning(f"ExternalHeartbeat failed to start (continuing): {exc}")
            ext_heartbeat = None

    # Initialize lifecycle if available
    if HAS_LIFECYCLE:
        try:
            _lifecycle = BotLifecycle(
                bot_name="ClawdYoda",
                bot_token=BOT_TOKEN,
                heartbeat_interval_hours=6.0,
                memory_threshold_mb=256,
            )
            _lifecycle.start()
            logger.info("Bot lifecycle started (heartbeat + watchdog)")
        except Exception as e:
            logger.error(f"Failed to start lifecycle: {e}")

    await bot.remove_webhook()
    logger.info("Starting polling...")
    try:
        await bot.infinity_polling(timeout=60, request_timeout=120)
    finally:
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

