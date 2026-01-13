#!/usr/bin/env python3
"""
Run all Jarvis Bot components:
- Buy tracker (real-time buy notifications)
- Sentiment reporter (Telegram every 30 min with Grok analysis)
- Twitter poster (Twitter every 30 min using Claude voice)
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
        project_root / "bots" / "twitter" / ".env",
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
    import subprocess
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    load_env()

    print("=" * 50)
    print("  JARVIS FULL SUITE")
    print("=" * 50)
    print()

    # Import components
    from bots.buy_tracker.bot import JarvisBuyBot
    from bots.buy_tracker.sentiment_report import SentimentReportGenerator
    from bots.twitter.sentiment_poster import SentimentTwitterPoster
    from bots.twitter.twitter_client import TwitterClient, TwitterCredentials
    from bots.twitter.claude_content import ClaudeContentGenerator

    tg_bot_proc = None

    # Ensure the main Telegram bot is running to process callback buttons
    run_main_bot = os.environ.get("RUN_MAIN_TG_BOT", "auto").lower()
    if run_main_bot not in ("0", "false", "no", "off"):
        tg_token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
        if tg_token:
            env = os.environ.copy()
            env["PYTHONPATH"] = str(project_root) + os.pathsep + env.get("PYTHONPATH", "")
            tg_bot_proc = subprocess.Popen(
                [sys.executable, str(project_root / "tg_bot" / "bot.py")],
                env=env,
            )

    # Initialize buy bot
    buy_bot = JarvisBuyBot()

    # Initialize Telegram sentiment reporter (Grok analysis)
    sentiment_reporter = SentimentReportGenerator(
        bot_token=os.environ.get("TELEGRAM_BOT_TOKEN", ""),
        chat_id=os.environ.get("TELEGRAM_BUY_BOT_CHAT_ID", ""),
        xai_api_key=os.environ.get("XAI_API_KEY", ""),
        interval_minutes=30,
    )

    # Initialize Twitter sentiment poster (Claude voice)
    twitter_creds = TwitterCredentials(
        api_key=os.environ.get("X_API_KEY", ""),
        api_secret=os.environ.get("X_API_SECRET", ""),
        access_token=os.environ.get("X_ACCESS_TOKEN", ""),
        access_token_secret=os.environ.get("X_ACCESS_TOKEN_SECRET", ""),
        bearer_token=os.environ.get("X_BEARER_TOKEN", ""),
        oauth2_client_id=os.environ.get("X_OAUTH2_CLIENT_ID", ""),
        oauth2_client_secret=os.environ.get("X_OAUTH2_CLIENT_SECRET", ""),
        oauth2_access_token=os.environ.get("X_OAUTH2_ACCESS_TOKEN", ""),
        oauth2_refresh_token=os.environ.get("X_OAUTH2_REFRESH_TOKEN", ""),
    )
    twitter_client = TwitterClient(twitter_creds)
    claude_client = ClaudeContentGenerator(api_key=os.environ.get("ANTHROPIC_API_KEY"))

    twitter_poster = SentimentTwitterPoster(
        twitter_client=twitter_client,
        claude_client=claude_client,
        interval_minutes=30,
    )

    print("Starting components:")
    print("  - Buy Tracker (real-time notifications)")
    print("  - Sentiment Reporter -> Telegram (every 30 min, Grok analysis)")
    print("  - Sentiment Poster -> Twitter (every 30 min, Claude voice)")
    if tg_bot_proc:
        print("  - Telegram Main Bot (callback handler)")
    print()
    print("Flow: Grok -> Predictions File -> Claude -> Twitter")
    print()
    print("=" * 50)
    print()

    try:
        # Run all concurrently
        await asyncio.gather(
            buy_bot.start(),
            sentiment_reporter.start(),
            twitter_poster.start(),
        )
    finally:
        if tg_bot_proc and tg_bot_proc.poll() is None:
            tg_bot_proc.terminate()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nShutting down...")
