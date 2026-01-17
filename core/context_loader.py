"""
Context Loader - Documentation context and Jarvis capabilities.

Provides:
1. Documentation context loading from index.md
2. JarvisContext class for shared capabilities across all interfaces
"""

import json
import logging
import os
from pathlib import Path
from typing import List, Tuple, Dict, Any

from core import config, state, system_profiler

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[1]
INDEX_PATH = ROOT / "lifeos" / "context" / "index.md"


def _parse_index_lines(lines: List[str]) -> List[str]:
    paths: List[str] = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        if line[0].isdigit() and "." in line:
            _, remainder = line.split(".", 1)
            path = remainder.strip()
        elif line.startswith("-"):
            path = line.lstrip("-").strip()
        else:
            continue
        if path and not path.startswith("##") and not path.startswith("#"):
            paths.append(path)
    return paths


def _load_index_paths() -> List[Path]:
    if not INDEX_PATH.exists():
        return []
    lines = INDEX_PATH.read_text(encoding="utf-8").splitlines()
    raw_paths = _parse_index_lines(lines)
    resolved: List[Path] = []
    for raw in raw_paths:
        if raw.startswith("context/"):
            raw = raw.replace("context/", "")
        candidate = INDEX_PATH.parent / raw
        resolved.append(candidate)
    return resolved


def _compute_context_budget(update_state: bool = True) -> Tuple[int, int]:
    cfg = config.load_config()
    context_cfg = cfg.get("context", {})
    base_docs = int(context_cfg.get("load_budget_docs", 20))
    base_chars = int(context_cfg.get("load_budget_chars", 12000))

    profile = system_profiler.read_profile()
    docs = base_docs
    chars = base_chars

    if profile.ram_total_gb and profile.ram_total_gb < 8:
        docs = min(docs, 10)
        chars = min(chars, 8000)
    if profile.ram_free_gb and profile.ram_free_gb < 2:
        docs = min(docs, 8)
        chars = min(chars, 6000)
    if profile.cpu_load and profile.cpu_load > 4:
        docs = min(docs, 8)
        chars = min(chars, 6000)
    if profile.disk_free_gb and profile.disk_free_gb < 10:
        docs = min(docs, 8)
        chars = min(chars, 6000)

    if update_state:
        state.update_state(context_budget_docs=docs, context_budget_chars=chars)
    return docs, chars


def load_context(update_state: bool = True) -> str:
    docs_budget, chars_budget = _compute_context_budget(update_state=update_state)
    paths = _load_index_paths()
    sections: List[str] = []
    total_chars = 0
    loaded_docs = 0

    for path in paths:
        if loaded_docs >= docs_budget:
            break
        if not path.exists():
            continue
        content = path.read_text(encoding="utf-8")
        if not content.strip():
            continue
        header = f"# {path.name}\n"
        block = header + content.strip() + "\n"
        if total_chars + len(block) > chars_budget:
            break
        sections.append(block)
        total_chars += len(block)
        loaded_docs += 1

    if update_state:
        state.update_state(context_docs_loaded=loaded_docs, context_chars_loaded=total_chars)
    return "\n".join(sections).strip()


# =============================================================================
# JARVIS CAPABILITIES CONTEXT
# =============================================================================

JARVIS_CAPABILITIES = """
You are JARVIS, an autonomous AI system with the following ACTIVE capabilities:

## Social Media (X/Twitter)
- ✅ Post to X/Twitter via @Jarvis_lifeos (automated, can be triggered)
- ✅ Read X sentiment and mentions
- ✅ Respond to admin coding commands via mentions
- ✅ Sync tweets to Telegram automatically
- ✅ Execute social automation workflows

## Trading (Live Treasury)
- ✅ Execute trades on Solana via Jupiter DEX
- ✅ Monitor token positions and portfolio
- ✅ Check balances and trade history
- ✅ Paper trading mode available
- ✅ Risk management and position limits (max 50 positions)

## Analysis & Data
- ✅ Sentiment analysis via Grok AI
- ✅ Token trending data (DexScreener, Birdeye)
- ✅ Market data (BTC, ETH, SOL, Fear & Greed)
- ✅ Whale tracking and alerts
- ✅ Price monitoring and alerts

## Telegram Commands
- /sentiment or /report - Full market sentiment analysis
- /trending - Trending Solana tokens
- /stocks or /st - Tokenized stocks (xStocks)
- /analyze <token> - Deep token analysis
- /price <token> - Current price check
- /portfolio - View open positions
- /help - List all commands

## Special Actions (Admin Only)
- Execute coding tasks via Claude CLI
- Post custom messages to X/Twitter
- Execute manual trades
- Adjust system settings

When a user (especially admin) asks you to do something, CHECK if you have
the capability first. If you can do it, DO IT or confirm you're executing it.
Don't say "I can't access X" when you clearly can.
"""


class JarvisContext:
    """Shared context for all Jarvis interfaces (Telegram, CLI, API)."""

    @staticmethod
    def get_capabilities() -> str:
        """Return Jarvis's current capabilities as a string."""
        caps_file = ROOT / "docs" / "JARVIS_CAPABILITIES.md"
        if caps_file.exists():
            try:
                return caps_file.read_text(encoding="utf-8")
            except Exception as e:
                logger.warning(f"Failed to read capabilities file: {e}")
        return JARVIS_CAPABILITIES

    @staticmethod
    def get_current_state() -> Dict[str, Any]:
        """Return current trading/system state."""
        result: Dict[str, Any] = {}

        # Check common state files
        state_dirs = [
            Path.home() / ".lifeos" / "trading",
            ROOT / "bots" / "treasury",
        ]

        state_files = [
            "lut_module_state.json",
            "exit_intents.json",
            "perps_state.json",
            ".positions.json",
        ]

        for state_dir in state_dirs:
            if not state_dir.exists():
                continue
            for state_file in state_files:
                file_path = state_dir / state_file
                if file_path.exists():
                    try:
                        content = json.loads(file_path.read_text(encoding="utf-8"))
                        key = state_file.replace(".json", "").lstrip(".")
                        result[key] = content
                    except Exception as e:
                        logger.debug(f"Failed to read {file_path}: {e}")

        return result

    @staticmethod
    def get_system_prompt(include_state: bool = True) -> str:
        """Full system prompt for any Jarvis interface."""
        caps = JarvisContext.get_capabilities()

        if include_state:
            current_state = JarvisContext.get_current_state()
            state_str = json.dumps(current_state, indent=2, default=str)[:2000]
            return f"""You are Jarvis, an autonomous AI trading and life assistant.

{caps}

Current System State:
{state_str}

You have FULL ACCESS to execute actions. When asked to do something you can do, DO IT.
"""
        return f"""You are Jarvis, an autonomous AI trading and life assistant.

{caps}

You have FULL ACCESS to execute actions. When asked to do something you can do, DO IT.
"""

    @staticmethod
    def get_position_count() -> int:
        """Get current number of open positions."""
        current_state = JarvisContext.get_current_state()
        positions = current_state.get("positions", [])
        if isinstance(positions, list):
            return len(positions)
        return 0

    @staticmethod
    def is_trading_enabled() -> bool:
        """Check if trading is enabled."""
        return os.environ.get("LIFEOS_KILL_SWITCH", "").lower() != "true"

    @staticmethod
    def is_x_bot_enabled() -> bool:
        """Check if X bot is enabled."""
        return os.environ.get("X_BOT_ENABLED", "true").lower() != "false"


# Convenience functions
def get_jarvis_capabilities() -> str:
    """Get Jarvis capabilities string."""
    return JarvisContext.get_capabilities()


def get_jarvis_system_prompt() -> str:
    """Get full Jarvis system prompt with state."""
    return JarvisContext.get_system_prompt()
