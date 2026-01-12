"""
Configuration for Jarvis Buy Bot Tracker.
"""

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass
class BuyBotConfig:
    """Configuration for the buy bot."""

    # Telegram settings
    bot_token: str
    chat_id: str  # Group/channel ID to post notifications

    # Token settings
    token_address: str  # The token contract address to track
    token_symbol: str = "KR8TIV"
    token_name: str = "Kr8Tiv"
    pair_address: str = ""  # The LP pair address where trades happen

    # RPC settings
    helius_api_key: str = ""
    rpc_url: str = ""
    websocket_url: str = ""

    # Notification settings
    min_buy_usd: float = 5.0  # Minimum buy amount in USD to notify
    video_path: str = ""  # Path to MP4 video to attach

    # Display settings
    bot_name: str = "Jarvis Buy Bot Tracker"
    buy_emoji: str = "🤖"  # Robot emoji as requested

    def __post_init__(self):
        """Set up derived values."""
        if self.helius_api_key and not self.rpc_url:
            self.rpc_url = f"https://mainnet.helius-rpc.com/?api-key={self.helius_api_key}"
        if self.helius_api_key and not self.websocket_url:
            self.websocket_url = f"wss://mainnet.helius-rpc.com/?api-key={self.helius_api_key}"


def load_config() -> BuyBotConfig:
    """Load configuration from environment variables."""

    # Get the project root
    project_root = Path(__file__).resolve().parents[2]
    video_path = project_root / "buybot.mp4"

    # Get pair address from env or fetch from DexScreener
    pair_address = os.environ.get("BUY_BOT_PAIR_ADDRESS", "")
    token_address = os.environ.get("BUY_BOT_TOKEN_ADDRESS", "")

    if not pair_address and token_address:
        # Try to fetch pair address from DexScreener
        try:
            import requests
            resp = requests.get(
                f"https://api.dexscreener.com/latest/dex/tokens/{token_address}",
                timeout=10
            )
            if resp.status_code == 200:
                data = resp.json()
                pairs = data.get("pairs", [])
                if pairs:
                    pair_address = pairs[0].get("pairAddress", "")
        except Exception:
            pass

    return BuyBotConfig(
        bot_token=os.environ.get("TELEGRAM_BOT_TOKEN", ""),
        chat_id=os.environ.get("TELEGRAM_BUY_BOT_CHAT_ID", ""),
        token_address=token_address,
        token_symbol=os.environ.get("BUY_BOT_TOKEN_SYMBOL", "KR8TIV"),
        token_name=os.environ.get("BUY_BOT_TOKEN_NAME", "Kr8Tiv"),
        pair_address=pair_address,
        helius_api_key=os.environ.get("HELIUS_API_KEY", ""),
        min_buy_usd=float(os.environ.get("BUY_BOT_MIN_USD", "5.0")),
        video_path=str(video_path) if video_path.exists() else "",
    )
