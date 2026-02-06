"""
Configuration for Jarvis Buy Bot Tracker.
"""

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Tuple


# Additional LP pairs to monitor (name -> address)
# These are tracked alongside the main KR8TIV pair
# Format: "name": "pair_address"
ADDITIONAL_LP_PAIRS: Dict[str, str] = {
    "kr8tiv/main-alt": "GNFeekyLr79S7jkBipPznLkiVm1UFqmPNbqS96mXmGqq",
    "kr8tiv/Eliza Town": "5VU8r7BFQBxUuNXMWLVPzjEQS2Z7oUt1vex3YJa95fw3",
    "kr8tiv/ralph": "EYGvaFsXk1baLN8sJycLgYgnmUk6R3Bb4UXBzKweqXS7",
    "kr8tiv/ralph-tui": "EipU3y7ojVqadEQNGWSu26je8iHixs1Xf7BP7dWPheUS",
    "kr8tiv/gas": "AAvjH1V16bua6Jyxbj8Tex8rpNZepzw71MmjL3FUQ117",
    "kr8tiv/weth": "9vW5Byh6h3j7AKrL8WtXW6uwKP3E4hRSRCXSZmCCyJfx",
    "kr8tiv/wbtc": "HSfu6s84FpqUDfZDbt8J4ii1K6FWsN7oJFPRfh2QsvuC",
    "verdis/kr8tiv": "EAWrGR2pwn5wXUNSfeR66uZ7CG536qX4jXYiS2otxxR2",
    "loom/kr8tiv": "7qXmDiVvVdNj3sYFcvE1vGE8hDtZMdDxWr2vMceY99nY",
    "continuous/kr8tiv": "s3KFNeaTFmkFbuw4gJmXgUDTzFaFgGtLR1DzmtTQA8X",
    "ATH/kr8tiv": "FsezrNYYXdTHY4PuffDkTGTpXLqu6tR3qEgd7vfjhPW2",
}


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

    # Additional LP pairs to monitor: list of (name, address) tuples
    # Graceful: if empty or invalid, bot continues with main pair only
    additional_pairs: List[Tuple[str, str]] = field(default_factory=list)

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

    buy_bot_token = (os.environ.get("TELEGRAM_BUY_BOT_TOKEN", "") or "").strip()
    if not buy_bot_token:
        import logging
        logging.getLogger(__name__).error("TELEGRAM_BUY_BOT_TOKEN not set - buy bot will not start. Do NOT fall back to main bot token to avoid polling conflicts.")

    # Load additional LP pairs from config dict
    # These are gracefully handled - if any are invalid, they're just skipped
    additional_pairs: List[Tuple[str, str]] = []
    for name, address in ADDITIONAL_LP_PAIRS.items():
        if address and len(address) >= 32:  # Basic Solana address validation
            additional_pairs.append((name, address))

    chat_id_raw = (os.environ.get("TELEGRAM_BUY_BOT_CHAT_ID", "") or "").strip()
    # Prefer int chat IDs for python-telegram-bot. If non-numeric (e.g. @channel),
    # keep the string.
    if chat_id_raw and chat_id_raw.lstrip("-").isdigit():
        chat_id: str | int = int(chat_id_raw)
    else:
        chat_id = chat_id_raw

    return BuyBotConfig(
        bot_token=buy_bot_token,
        chat_id=chat_id,
        token_address=token_address,
        token_symbol=os.environ.get("BUY_BOT_TOKEN_SYMBOL", "KR8TIV"),
        token_name=os.environ.get("BUY_BOT_TOKEN_NAME", "Kr8Tiv"),
        pair_address=pair_address,
        additional_pairs=additional_pairs,
        helius_api_key=os.environ.get("HELIUS_API_KEY", ""),
        min_buy_usd=float(os.environ.get("BUY_BOT_MIN_USD", "5.0")),
        video_path=str(video_path) if video_path.exists() else "",
    )
