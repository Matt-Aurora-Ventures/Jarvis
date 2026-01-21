"""Configuration for Bags Intel service."""

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

# Load .env files (same pattern as tg_bot/config.py)
def _load_env_file(path: Path) -> None:
    """Load environment variables from a file."""
    if path.exists():
        try:
            from dotenv import load_dotenv
            load_dotenv(path)
        except ImportError:
            # Fallback: manually parse .env
            with open(path, "r") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        key, _, value = line.partition("=")
                        key = key.strip()
                        value = value.strip().strip('"').strip("'")
                        if key and value and key not in os.environ:
                            os.environ[key] = value

# Load from tg_bot/.env (main credentials) and root .env (additional keys)
_project_root = Path(__file__).resolve().parents[2]
_load_env_file(_project_root / "tg_bot" / ".env")
_load_env_file(_project_root / ".env")


@dataclass
class BagsIntelConfig:
    """Configuration for bags.fm intelligence reports."""

    # Bitquery (for real-time WebSocket monitoring) - NEW key needed
    bitquery_api_key: str = ""
    bitquery_ws_url: str = "wss://streaming.bitquery.io/graphql"

    # Reuse existing Jarvis keys
    helius_api_key: str = ""
    helius_rpc_url: str = ""

    # Telegram - reuse existing bot
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""  # Can use same as buy bot or different

    # Twitter - reuse existing
    twitter_bearer_token: str = ""

    # Grok AI - reuse existing
    xai_api_key: str = ""

    # Bags.fm API (optional, for enhanced metadata)
    bags_api_key: str = ""
    bags_api_url: str = "https://public-api-v2.bags.fm/api/v1"

    # Monitoring settings
    min_graduation_mcap: float = 10000.0  # Min market cap to report
    min_score_to_report: float = 30.0  # Min score to send report
    report_cooldown_seconds: int = 60  # Cooldown between reports for same token

    # Program addresses (Bags.fm / Meteora)
    meteora_dbc_program: str = "dbcij3LWUppWqq96dh6gJWwBifmcGfLSB5D4DuSMaqN"
    bags_token_signer: str = "BAGSB9TpGrZxQbEsrEznv5jXXdwyP6AXerN8aVRiAmcv"

    @property
    def is_configured(self) -> bool:
        """Check if minimum required config is present."""
        return bool(self.bitquery_api_key and self.telegram_bot_token)


def load_config() -> BagsIntelConfig:
    """Load configuration from environment variables."""
    helius_key = os.environ.get("HELIUS_API_KEY", "")

    return BagsIntelConfig(
        # New key for Bitquery
        bitquery_api_key=os.environ.get("BITQUERY_API_KEY", ""),

        # Reuse existing keys
        helius_api_key=helius_key,
        helius_rpc_url=f"https://mainnet.helius-rpc.com/?api-key={helius_key}" if helius_key else "",
        telegram_bot_token=os.environ.get("TELEGRAM_BOT_TOKEN", ""),
        telegram_chat_id=os.environ.get("TELEGRAM_BUY_BOT_CHAT_ID", ""),  # Same channel as buy bot
        twitter_bearer_token=os.environ.get("TWITTER_BEARER_TOKEN", ""),
        xai_api_key=os.environ.get("XAI_API_KEY", ""),

        # Optional Bags.fm API
        bags_api_key=os.environ.get("BAGS_API_KEY", ""),

        # Settings
        min_graduation_mcap=float(os.environ.get("BAGS_INTEL_MIN_MCAP", "10000")),
        min_score_to_report=float(os.environ.get("BAGS_INTEL_MIN_SCORE", "30")),
    )
