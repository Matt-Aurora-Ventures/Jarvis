#!/usr/bin/env python3
"""
Verify Telegram bot token and connection.
Tests that the new Telegram token works correctly.
"""

import asyncio
import sys
import os
from pathlib import Path

# Add parent dir to path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


async def verify_telegram_token():
    """Verify that Telegram token is valid and bot is responsive."""
    from dotenv import load_dotenv
    from telegram import Bot

    # Load environment
    env_file = Path(__file__).parent.parent / "tg_bot" / ".env"
    load_dotenv(env_file)

    token = os.getenv("TELEGRAM_BOT_TOKEN")

    if not token:
        print("ERROR: TELEGRAM_BOT_TOKEN not found in .env")
        return False

    print(f"Testing token: {token[:20]}...")

    try:
        # Create bot instance
        bot = Bot(token=token)

        # Test getMe call (basic connectivity test)
        me = await bot.get_me()

        print("[OK] Bot connected successfully!")
        print(f"  Bot name: @{me.username}")
        print(f"  Bot ID: {me.id}")
        print(f"  First name: {me.first_name}")

        return True

    except Exception as e:
        print(f"ERROR: Token verification failed!")
        print(f"  {type(e).__name__}: {str(e)}")
        return False


async def main():
    """Run verification."""
    print("=" * 50)
    print("TELEGRAM TOKEN VERIFICATION")
    print("=" * 50)
    print()

    success = await verify_telegram_token()

    print()
    print("=" * 50)
    if success:
        print("Status: VERIFIED")
        sys.exit(0)
    else:
        print("Status: FAILED")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
