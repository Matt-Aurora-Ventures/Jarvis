#!/usr/bin/env python3
"""
Run all Jarvis Buy Bot components:
- Buy tracker (real-time buy notifications)
- Sentiment reporter (30-minute sentiment reports)
"""

import asyncio
import os
import sys
from pathlib import Path

# Fix Windows encoding
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

# Add project root to path
project_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(project_root))


def load_env():
    """Load environment variables."""
    env_files = [
        project_root / "tg_bot" / ".env",
        project_root / ".env",
    ]
    for env_path in env_files:
        if env_path.exists():
            with open(env_path) as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        key, value = line.split("=", 1)
                        os.environ.setdefault(key.strip(), value.strip())


async def main():
    """Run all bot components."""
    import logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    load_env()

    print("=" * 50)
    print("  JARVIS BUY BOT - FULL SUITE")
    print("=" * 50)
    print()

    # Import components
    from bots.buy_tracker.bot import JarvisBuyBot
    from bots.buy_tracker.sentiment_report import SentimentReportGenerator

    # Initialize buy bot
    buy_bot = JarvisBuyBot()

    # Initialize sentiment reporter
    sentiment_reporter = SentimentReportGenerator(
        bot_token=os.environ.get("TELEGRAM_BOT_TOKEN", ""),
        chat_id=os.environ.get("TELEGRAM_BUY_BOT_CHAT_ID", ""),
        xai_api_key=os.environ.get("XAI_API_KEY", ""),
        interval_minutes=30,
    )

    print("Starting components:")
    print("  - Buy Tracker (real-time notifications)")
    print("  - Sentiment Reporter (every 30 min)")
    print()
    print("=" * 50)
    print()

    # Run both concurrently
    await asyncio.gather(
        buy_bot.start(),
        sentiment_reporter.start(),
    )


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nShutting down...")
