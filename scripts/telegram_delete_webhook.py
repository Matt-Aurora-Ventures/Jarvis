#!/usr/bin/env python3
"""Delete Telegram webhook to allow polling."""

import asyncio
import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

# Load environment
from dotenv import load_dotenv
load_dotenv(project_root / ".env")

from telegram import Bot


async def delete_webhook():
    """Delete webhook and allow polling."""
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        print("ERROR: TELEGRAM_BOT_TOKEN not set")
        return False

    bot = Bot(token)

    try:
        # Get current webhook info
        info = await bot.get_webhook_info()
        print(f"Current webhook URL: {info.url or '(none)'}")
        print(f"Pending updates: {info.pending_update_count}")
        print(f"Last error: {info.last_error_message or '(none)'}")

        # Delete webhook
        if info.url:
            print("\nDeleting webhook...")
            await bot.delete_webhook(drop_pending_updates=True)
            print("✓ Webhook deleted")
        else:
            print("\n✓ No webhook configured (polling mode)")

        # Verify
        info = await bot.get_webhook_info()
        print(f"\nVerified webhook URL: {info.url or '(none)'}")

        return True
    except Exception as e:
        print(f"ERROR: {e}")
        return False


if __name__ == "__main__":
    success = asyncio.run(delete_webhook())
    sys.exit(0 if success else 1)
