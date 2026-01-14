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


# Cost per API call (USD estimates)
API_COSTS = {
    "grok": 0.002,  # ~$2 per 1000 calls
    "claude": 0.003,  # ~$3 per 1000 calls (sonnet)
    "birdeye": 0.0,  # Free tier
    "dexscreener": 0.0,  # Free
    "gmgn": 0.0,  # Free tier
}


@dataclass
class BotConfig:
    """Secure Telegram bot configuration."""

    # === REQUIRED (from environment only) ===
    telegram_token: str = field(default_factory=lambda: os.getenv("TELEGRAM_BOT_TOKEN", ""))

    # === API KEYS (from environment only) ===
    grok_api_key: str = field(default_factory=lambda: os.getenv("XAI_API_KEY", ""))
    anthropic_api_key: str = field(default_factory=lambda: os.getenv("ANTHROPIC_API_KEY", ""))
    birdeye_api_key: str = field(default_factory=lambda: os.getenv("BIRDEYE_API_KEY", ""))

    # === ADMIN SECURITY ===
    # Only these Telegram user IDs can run sentiment checks
    # Set via TELEGRAM_ADMIN_IDS="123456789,987654321"
    admin_ids: Set[int] = field(default_factory=lambda: _parse_admin_ids())

    # === RATE LIMITING ===
    sentiment_interval_seconds: int = 3600  # 1 hour minimum between sentiment checks
    max_sentiment_per_day: int = 24  # Max 24 sentiment checks per day
    daily_cost_limit_usd: float = 1.00  # Stop if daily cost exceeds this

    # === MODEL SETTINGS ===
    grok_model: str = "grok-3-mini"  # cheapest: grok-3-mini, best: grok-4
    claude_model: str = "claude-sonnet-4-20250514"
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
        return bool(self.grok_api_key)

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
            missing.append("ANTHROPIC_API_KEY (for Claude fallback)")
        if not self.birdeye_api_key:
            missing.append("BIRDEYE_API_KEY (for token data)")
        return missing

    def is_admin(self, user_id: int) -> bool:
        """Check if user is an admin."""
        return user_id in self.admin_ids

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
    """Reload config from environment."""
    global _config
    _config = BotConfig()
    return _config
