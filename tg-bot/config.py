"""
Secure Configuration for Jarvis Telegram Bot.

Security features:
- Admin whitelist (only you can run sentiment checks)
- API keys loaded from environment only (never hardcoded)
- Rate limiting with cost tracking
- No key exposure in logs or messages
"""

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Set

# Load .env file from tg_bot directory
_env_path = Path(__file__).parent / ".env"
if _env_path.exists():
    try:
        from dotenv import load_dotenv
        load_dotenv(_env_path)
    except ImportError:
        # Fallback: manually parse .env
        with open(_env_path, "r") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, _, value = line.partition("=")
                    key = key.strip()
                    value = value.strip().strip('"').strip("'")
                    if key and value and key not in os.environ:
                        os.environ[key] = value


def _hydrate_env_from_keys_json() -> None:
    """Populate os.environ from secrets/keys.json (if env vars are missing).

    This keeps secrets out of the repo and avoids needing them in tg_bot/.env.
    """
    keys = _load_keys_json()
    if not keys:
        return

    def _set_if_missing(env_name: str, value: str):
        if not os.getenv(env_name) and value:
            os.environ[env_name] = value

    # Top-level simple keys
    _set_if_missing("BIRDEYE_API_KEY", (keys.get("birdeye_api_key") or "").strip())
    _set_if_missing("BAGS_API_KEY", (keys.get("bags_api_key") or "").strip())
    _set_if_missing("BAGS_PARTNER_KEY", (keys.get("bags_partner_key") or "").strip())
    _set_if_missing("GROQ_API_KEY", (keys.get("groq_api_key") or "").strip())
    _set_if_missing("ANTHROPIC_API_KEY", (keys.get("anthropic_api_key") or "").strip())

    # Nested keys
    xai = (keys.get("xai") or {})
    _set_if_missing("XAI_API_KEY", (xai.get("api_key") or "").strip())

    helius = (keys.get("helius") or {})
    _set_if_missing("HELIUS_API_KEY", (helius.get("api_key") or "").strip())

    # Telegram handled via _get_telegram_token(), but hydrate for compatibility
    tg = (keys.get("telegram") or {})
    _set_if_missing("TELEGRAM_BOT_TOKEN", (tg.get("jarvis_cloudbot_token") or tg.get("clawdjarvis_token") or tg.get("bot_token") or "").strip())


# Resolve Anthropic key (local Ollama uses placeholder).
def _get_anthropic_key() -> str:
    try:
        from core.llm.anthropic_utils import get_anthropic_api_key
        return get_anthropic_api_key()
    except Exception:
        return os.getenv("ANTHROPIC_API_KEY", "")


# Cost per API call (USD estimates)
API_COSTS = {
    "grok": 0.002,  # ~$2 per 1000 calls
    "claude": 0.003,  # ~$3 per 1000 calls (sonnet)
    "birdeye": 0.0,  # Free tier
    "dexscreener": 0.0,  # Free
    "gmgn": 0.0,  # Free tier
}


def _get_secrets_path() -> Path:
    """Get path to secrets/keys.json with environment variable override.

    Priority:
    1. JARVIS_SECRETS_PATH environment variable
    2. Default: $HOME/.lifeos/secrets/keys.json (portable across systems)
    3. Fallback: Project root/secrets/keys.json
    """
    # Allow override via environment variable
    env_path = os.getenv("JARVIS_SECRETS_PATH", "").strip()
    if env_path:
        return Path(env_path)

    # Default: Home directory .lifeos structure (portable)
    default_path = Path.home() / ".lifeos" / "secrets" / "keys.json"
    if default_path.exists():
        return default_path

    # Fallback: Project root (for development/backwards compatibility)
    # Try to find project root by looking for lifeos/config directory
    current = Path(__file__).resolve()
    for parent in [current.parent.parent, current.parent.parent.parent]:
        candidate = parent / "secrets" / "keys.json"
        if candidate.exists():
            return candidate

    # Last resort: Return default path (even if doesn't exist yet)
    return default_path


def _load_keys_json() -> dict:
    """Load secrets/keys.json safely from configurable location.

    Never print this content; caller must treat values as secrets.
    """
    try:
        import json
        p = _get_secrets_path()
        if not p.exists():
            return {}
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}


# Populate env vars from keys.json (so tg_bot/.env can stay blank)
_hydrate_env_from_keys_json()


def _get_telegram_token() -> str:
    """Resolve Telegram bot token.

    Priority:
    1) TELEGRAM_BOT_TOKEN env var (legacy)
    2) secrets/keys.json: telegram.jarvis_cloudbot_token (new)
    3) secrets/keys.json: telegram.clawdjarvis_token (fallback)
    4) secrets/keys.json: telegram.bot_token (last resort)
    """
    env = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    if env:
        return env

    keys = _load_keys_json()
    tg = (keys or {}).get("telegram") or {}

    for k in ("jarvis_cloudbot_token", "clawdjarvis_token", "bot_token"):
        v = (tg.get(k) or "").strip()
        if v:
            return v

    return ""


@dataclass
class BotConfig:
    """Secure Telegram bot configuration."""

    # === REQUIRED ===
    telegram_token: str = field(default_factory=_get_telegram_token)

    # === API KEYS (from environment only) ===
    grok_api_key: str = field(default_factory=lambda: os.getenv("XAI_API_KEY", ""))
    anthropic_api_key: str = field(default_factory=lambda: _get_anthropic_key())
    birdeye_api_key: str = field(default_factory=lambda: os.getenv("BIRDEYE_API_KEY", ""))

    # === ADMIN SECURITY ===
    # Only these Telegram user IDs can run sentiment checks
    # Set via TELEGRAM_ADMIN_IDS="123456789,987654321"
    admin_ids: Set[int] = field(default_factory=lambda: _parse_admin_ids())

    # === RATE LIMITING ===
    sentiment_interval_seconds: int = 3600  # 1 hour minimum between sentiment checks
    max_sentiment_per_day: int = 24  # Max 24 sentiment checks per day
    daily_cost_limit_usd: float = 10.00  # Stop if daily cost exceeds this

    # === MODEL SETTINGS ===
    grok_model: str = "grok-3-mini"  # cheapest: grok-3-mini, best: grok-4
    claude_model: str = "claude-opus-4-5-20251101"  # Opus 4.5 (best reasoning)
    claude_max_tokens: int = 1024

    # === DATABASE ===
    db_path: Path = field(default_factory=lambda: Path.home() / ".lifeos" / "telegram" / "jarvis_secure.db")

    # === SCHEDULER ===
    digest_hours: List[int] = field(default_factory=lambda: [8, 14, 20])  # UTC hours for digests

    # === BROADCAST CHAT ===
    # Main group chat to push sentiment digests to
    # Set via TELEGRAM_BROADCAST_CHAT_ID="-1001234567890"
    broadcast_chat_id: Optional[int] = field(default_factory=lambda: _parse_broadcast_chat_id())

    # === PAPER TRADING ===
    paper_starting_balance: float = 100.0  # SOL
    paper_max_position_pct: float = 0.20
    paper_slippage_pct: float = 0.003

    # === TREASURY ===
    # Low balance warning threshold (in SOL)
    # Set via LOW_BALANCE_THRESHOLD=0.01
    low_balance_threshold: float = field(default_factory=lambda: float(os.getenv("LOW_BALANCE_THRESHOLD", "0.01")))

    # === SECURITY FLAGS ===
    log_api_calls: bool = False  # Never log actual API responses (could leak data)
    mask_addresses: bool = True  # Truncate addresses in logs

    def __post_init__(self):
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    def is_valid(self) -> bool:
        """Check if minimum required config is set."""
        return bool(self.telegram_token and self.admin_ids)

    def has_grok(self) -> bool:
        """Check if Grok API is configured."""
        if not self.grok_api_key:
            return False
        try:
            from core.feature_flags import is_xai_enabled
            return is_xai_enabled(default=True)
        except Exception:
            # Be conservative: if flags can't be evaluated, assume disabled.
            return False

    def has_claude(self) -> bool:
        """Check if Claude API is configured."""
        return bool(self.anthropic_api_key)

    def get_missing(self) -> List[str]:
        """Get list of missing required config."""
        missing = []
        if not self.telegram_token:
            missing.append("TELEGRAM_BOT_TOKEN")
        if not self.admin_ids:
            missing.append("TELEGRAM_ADMIN_IDS")
        return missing

    def get_optional_missing(self) -> List[str]:
        """Get list of missing optional config."""
        missing = []
        if not self.grok_api_key:
            missing.append("XAI_API_KEY (for Grok sentiment)")
        if not self.anthropic_api_key:
            missing.append("ANTHROPIC_API_KEY or ANTHROPIC_AUTH_TOKEN (for local Claude-compatible)")
        if not self.birdeye_api_key:
            missing.append("BIRDEYE_API_KEY (for token data)")
        return missing

    def is_admin(self, user_id: int, username: str = None) -> bool:
        """Check if user is an admin by ID or username (case insensitive).

        Args:
            user_id: Telegram user ID
            username: Telegram username (without @)

        Returns:
            True if user is admin, False otherwise
        """
        import logging
        logger = logging.getLogger(__name__)

        # Check by ID first
        if user_id in self.admin_ids:
            logger.debug(f"Admin check passed for user_id={user_id} (ID match)")
            return True

        # Check by username (case insensitive)
        if username:
            username_lower = username.lower().lstrip('@')
            admin_usernames = _parse_admin_usernames()

            if username_lower in admin_usernames:
                logger.debug(f"Admin check passed for user_id={user_id}, username={username} (username match)")
                return True

        logger.warning(f"Admin check failed for user_id={user_id}, username={username}")
        return False

    def mask_key(self, key: str) -> str:
        """Mask API key for safe logging."""
        if not key or len(key) < 8:
            return "***"
        return f"{key[:4]}...{key[-4:]}"


def _parse_admin_ids() -> Set[int]:
    """Parse admin IDs from environment variable."""
    ids_str = os.getenv("TELEGRAM_ADMIN_IDS", "")
    if not ids_str:
        return set()

    ids = set()
    for id_str in ids_str.split(","):
        id_str = id_str.strip()
        if id_str.isdigit():
            ids.add(int(id_str))
    return ids


def _parse_admin_usernames() -> Set[str]:
    """Parse admin usernames from environment variable."""
    names_str = os.getenv("TELEGRAM_ADMIN_USERNAMES", "")
    if not names_str:
        return {"matthaynes88"}

    names = set()
    for name in names_str.split(","):
        cleaned = name.strip().lower().lstrip("@")
        if cleaned:
            names.add(cleaned)
    return names


def _parse_broadcast_chat_id() -> Optional[int]:
    """Parse broadcast chat ID from environment variable."""
    chat_id_str = os.getenv("TELEGRAM_BROADCAST_CHAT_ID") or os.getenv("TELEGRAM_BUY_BOT_CHAT_ID")
    if not chat_id_str:
        return None
    try:
        return int(chat_id_str.strip())
    except ValueError:
        return None


_config: Optional[BotConfig] = None


def get_config() -> BotConfig:
    """Get singleton config instance."""
    global _config
    if _config is None:
        _config = BotConfig()
    return _config


def reload_config() -> BotConfig:
    """Reload config from the environment / secrets and reset the singleton."""
    global _config
    try:
        _hydrate_env_from_keys_json()
    except Exception:
        pass
    _config = BotConfig()
    return _config
