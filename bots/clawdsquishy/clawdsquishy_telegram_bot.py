"""
ClawdSquishy Telegram Bot - Research Assistant (CRO)

Lightweight Telegram interface for Squishy (research + due diligence).
This runner is intentionally safe-by-default and does not require LLM keys
to be "online" and responsive.

Usage:
  /squishy <question> - Ask for research framing + next steps
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
BOT_TOKEN = os.environ.get("CLAWDSQUISHY_BOT_TOKEN")
if not BOT_TOKEN:
    logger.error("CLAWDSQUISHY_BOT_TOKEN not found in environment")
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

# Public beta toggle: when enabled, allow everyone to use "safe" bot commands.
PUBLIC_MODE = os.environ.get("CLAWDBOT_PUBLIC_MODE", "").strip().lower() in ("1", "true", "yes", "on")

# Initialize lifecycle (optional)
_lifecycle = None

SQUISHY_HELP = """
Squishy (CRO) — Research + Due Diligence

Commands:
/squishy <question>  - Research framing + what to measure next
/status              - Bot status
/help                - This message

Examples:
/squishy Is this tokenomics design sustainable?
/squishy What are the biggest risks before public launch?
/squishy Find 3 approaches and compare tradeoffs.
""".strip()


def check_user_authorized(user_id: int) -> bool:
    """Check if a user is authorized to use the bot."""
    if PUBLIC_MODE:
        return True
    if not HAS_SECURITY or not _allowlist:
        return True  # Dev mode - allow all
    return check_authorization(user_id, AuthorizationLevel.OBSERVER, _allowlist)


async def _deny(reason: str, message) -> None:
    """Tell unauthorized users why nothing happened (avoid silent failure)."""
    try:
        await bot.reply_to(message, f"⛔ {reason}\n\nIf you should have access, contact support.")
    except Exception:
        return


def _research_frame(question: str) -> str:
    q = (question or "").strip()
    if not q:
        return "Question missing. Example: `/squishy What should we test next?`"

    ql = q.lower()
    lines = [
        "Research framing:",
        f"- Question: {q}",
        "",
        "What I need to answer confidently:",
        "- Goal (what decision are we making?)",
        "- Constraints (time, budget, safety)",
        "- Success metric (what does 'better' mean?)",
        "",
        "Method (fast + reliable):",
        "1) Identify measurable signals",
        "2) Collect a small sample quickly",
        "3) Validate on holdout data",
        "4) Add guardrails + monitoring",
    ]

    if "security" in ql or "secure" in ql:
        lines += [
            "",
            "Security checklist (minimum):",
            "- Remove secrets from repo and client bundles",
            "- Add rate limiting + schema validation on all endpoints",
            "- Add audit logs for trades/exits",
            "- Add allowlist for privileged actions",
        ]

    if "backtest" in ql or "algo" in ql or "strategy" in ql:
        lines += [
            "",
            "Algo validation (minimum):",
            "- Walk-forward backtests (no lookahead)",
            "- Slippage + fee modelling",
            "- Sensitivity tests (thresholds + liquidity regimes)",
            "- Live-paper mode with real routes and execution logs",
        ]

    return "\n".join(lines)


@bot.message_handler(commands=["start", "help"])
async def handle_help(message):
    if not check_user_authorized(message.from_user.id):
        await _deny("This bot is currently in private beta.", message)
        return
    await bot.reply_to(message, SQUISHY_HELP)


@bot.message_handler(commands=["status"])
async def handle_status(message):
    if not check_user_authorized(message.from_user.id):
        await _deny("This bot is currently in private beta.", message)
        return
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    text = f"ClawdSquishy Status: ONLINE\nTime: {now}\nMode: Research & Due Diligence"
    await bot.reply_to(message, text)


@bot.message_handler(commands=["squishy", "research"])
async def handle_squishy(message):
    if not check_user_authorized(message.from_user.id):
        await _deny("This bot is currently in private beta.", message)
        return

    text = message.text or ""
    question = text.split(" ", 1)[1].strip() if " " in text else ""

    # Block obviously dangerous commands even if asked as a "question".
    if HAS_SECURITY and question and is_dangerous_command(question):
        await bot.reply_to(message, "Denied. Dangerous request detected.")
        return

    await bot.reply_to(message, _research_frame(question))


async def main():
    global _lifecycle

    ext_heartbeat = None
    logger.info("Starting ClawdSquishy Telegram Bot...")

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
    hb_url = os.environ.get("SQUISHY_HEARTBEAT_URL", "").strip()
    if HAS_EXTERNAL_HEARTBEAT and hb_url:
        try:
            ext_heartbeat = ExternalHeartbeat(custom_webhook=hb_url)  # type: ignore[misc]
            await ext_heartbeat.start()
            logger.info("ExternalHeartbeat started")
        except Exception as exc:
            logger.warning(f"ExternalHeartbeat failed to start (continuing): {exc}")
            ext_heartbeat = None

    # Initialize lifecycle if available
    if HAS_LIFECYCLE:
        try:
            _lifecycle = BotLifecycle(
                bot_name="ClawdSquishy",
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
