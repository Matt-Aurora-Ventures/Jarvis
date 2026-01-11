#!/usr/bin/env python3
"""
Run the Jarvis Buy Bot Tracker.

Usage:
    python -m bots.buy_tracker.run

Or:
    python bots/buy_tracker/run.py

Environment variables required:
    TELEGRAM_BOT_TOKEN - Telegram bot token from @BotFather
    TELEGRAM_BUY_BOT_CHAT_ID - Group/channel ID to post notifications
    BUY_BOT_TOKEN_ADDRESS - Token contract address to track
    HELIUS_API_KEY - Helius API key for Solana RPC

Optional:
    BUY_BOT_TOKEN_SYMBOL - Token symbol (default: KR8TIV)
    BUY_BOT_TOKEN_NAME - Token name (default: Kr8Tiv)
    BUY_BOT_MIN_USD - Minimum buy in USD to notify (default: 5.0)
"""

import asyncio
import os
import sys
from pathlib import Path

# Fix Windows console encoding for emojis
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

# Add project root to path
project_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(project_root))


def load_env():
    """Load environment variables from .env files."""
    # Try tg_bot/.env first
    env_files = [
        project_root / "tg_bot" / ".env",
        project_root / ".env",
    ]

    for env_path in env_files:
        if env_path.exists():
            print(f"Loading environment from: {env_path}")
            with open(env_path) as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        key, value = line.split("=", 1)
                        os.environ.setdefault(key.strip(), value.strip())


def check_config():
    """Check required configuration."""
    required = {
        "TELEGRAM_BOT_TOKEN": "Telegram bot token",
        "TELEGRAM_BUY_BOT_CHAT_ID": "Telegram chat ID",
        "BUY_BOT_TOKEN_ADDRESS": "Token contract address",
        "HELIUS_API_KEY": "Helius API key",
    }

    missing = []
    for key, desc in required.items():
        if not os.environ.get(key):
            missing.append(f"  - {key}: {desc}")

    if missing:
        print("\n❌ Missing required configuration:\n")
        print("\n".join(missing))
        print("\nAdd these to tg_bot/.env or set as environment variables.")
        print("\nExample .env file:")
        print("  TELEGRAM_BOT_TOKEN=your_bot_token")
        print("  TELEGRAM_BUY_BOT_CHAT_ID=-1001234567890")
        print("  BUY_BOT_TOKEN_ADDRESS=your_token_address")
        print("  HELIUS_API_KEY=your_helius_key")
        return False

    return True


def main():
    """Main entry point."""
    print("🤖 Jarvis Buy Bot Tracker")
    print("=" * 40)

    # Load environment
    load_env()

    # Check config
    if not check_config():
        sys.exit(1)

    # Show config
    print(f"\n📊 Token: {os.environ.get('BUY_BOT_TOKEN_SYMBOL', 'KR8TIV')}")
    print(f"💰 Min buy: ${os.environ.get('BUY_BOT_MIN_USD', '5.0')}")
    print(f"📺 Video: {'✅' if (project_root / 'buybot.mp4').exists() else '❌'}")

    # Check for video
    video_path = project_root / "buybot.mp4"
    if not video_path.exists():
        print(f"\n⚠️  Video not found at: {video_path}")
        print("    Notifications will be sent without video.")

    print("\n" + "=" * 40)
    print("Starting bot...\n")

    # Import and run
    from bots.buy_tracker.bot import run_buy_bot
    asyncio.run(run_buy_bot())


if __name__ == "__main__":
    main()
