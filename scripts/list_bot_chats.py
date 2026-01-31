#!/usr/bin/env python3
"""
List all chats/channels the bot is a member of
"""

import asyncio
import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(project_root))

from telegram import Bot
from telegram.error import TelegramError


async def list_chats(token: str):
    """List all chats the bot has access to."""
    try:
        bot = Bot(token=token)

        # Get bot info
        me = await bot.get_me()
        print(f"Bot: @{me.username} ({me.first_name})")
        print(f"ID: {me.id}")
        print()

        # Note: Telegram doesn't provide a direct API to list all chats
        # The bot only knows about chats where messages were sent
        print("Note: Telegram bots can't list all chats they're in.")
        print("You need to use the channel ID or @username when posting.")
        print()
        print("Common channel formats:")
        print("  - @channel_username")
        print("  - -1001234567890 (numeric ID)")
        print()
        print("To find your channel:")
        print("1. Forward a message from the channel to @userinfobot")
        print("2. Or check your .env for TELEGRAM_ANNOUNCEMENTS_CHANNEL")

        return True

    except TelegramError as e:
        print(f"❌ Telegram error: {e}")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


async def main():
    token = os.environ.get("TELEGRAM_BOT_TOKEN")

    if not token:
        print("❌ Error: TELEGRAM_BOT_TOKEN not set")
        sys.exit(1)

    await list_chats(token)


if __name__ == "__main__":
    asyncio.run(main())
