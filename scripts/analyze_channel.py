#!/usr/bin/env python3
"""
Analyze a Telegram channel for engagement metrics.
Uses the Telegram Bot API to fetch public channel info.
"""

import os
import asyncio
from pathlib import Path

# Manual .env loading
def load_env_manual():
    possible_paths = [
        Path(__file__).parent.parent / ".env",
        Path(__file__).parent.parent / "tg_bot" / ".env",
    ]
    for env_path in possible_paths:
        if not env_path.exists():
            continue
        try:
            content = env_path.read_text(encoding='utf-8')
        except UnicodeDecodeError:
            try:
                content = env_path.read_text(encoding='utf-16')
            except Exception:
                content = env_path.read_text(encoding='latin-1')
        for line in content.splitlines():
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, _, value = line.partition('=')
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key and value and key not in os.environ:
                    os.environ[key] = value
        print(f"[OK] Loaded env from: {env_path}")
        return
    print("[WARN] No .env file found!")

load_env_manual()

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHANNEL_USERNAME = "KobesCallz"  # Without the @


async def analyze_channel():
    from telegram import Bot
    from telegram.error import TelegramError

    bot = Bot(token=TOKEN)

    print(f"\n{'='*60}")
    print(f"TELEGRAM CHANNEL ANALYSIS: @{CHANNEL_USERNAME}")
    print(f"{'='*60}\n")

    try:
        # Get chat info
        chat = await bot.get_chat(f"@{CHANNEL_USERNAME}")

        print("=== BASIC INFO ===")
        print(f"Title: {chat.title}")
        print(f"Username: @{chat.username}")
        print(f"Type: {chat.type}")
        print(f"ID: {chat.id}")

        if chat.description:
            # Remove emojis for Windows console compatibility
            desc_clean = chat.description[:500].encode('ascii', 'ignore').decode('ascii')
            print(f"\nDescription:\n{desc_clean}")

        # Get member count
        member_count = await bot.get_chat_member_count(chat.id)
        print(f"\n=== METRICS ===")
        print(f"Subscriber Count: {member_count:,}")

        # Check if it's a channel or group
        print(f"Chat Type: {chat.type}")

        # Photo info
        if chat.photo:
            print(f"Has Profile Photo: Yes")
        else:
            print(f"Has Profile Photo: No")

        # Linked chat (if channel has discussion group)
        if hasattr(chat, 'linked_chat_id') and chat.linked_chat_id:
            print(f"Has Discussion Group: Yes (ID: {chat.linked_chat_id})")
        else:
            print(f"Has Discussion Group: No")

        # Additional info
        print(f"\n=== ANALYSIS ===")

        # Red flag checks
        red_flags = []
        yellow_flags = []
        green_flags = []

        # Check subscriber count
        if member_count < 1000:
            yellow_flags.append(f"Small audience ({member_count:,} subscribers)")
        elif member_count > 100000:
            yellow_flags.append(f"Large audience - verify not inflated ({member_count:,})")
        else:
            green_flags.append(f"Moderate audience size ({member_count:,})")

        # Check for description
        if not chat.description:
            red_flags.append("No channel description - low effort")
        elif len(chat.description) < 50:
            yellow_flags.append("Very short description")
        else:
            green_flags.append("Has detailed description")

        # Check for profile photo
        if not chat.photo:
            red_flags.append("No profile photo - potential fake/spam")
        else:
            green_flags.append("Has profile photo")

        # Check username format
        if any(x in CHANNEL_USERNAME.lower() for x in ['vip', 'premium', 'signals', '100x', 'millionaire']):
            yellow_flags.append("Username contains hype keywords")

        # Print flags
        if red_flags:
            print("\n[RED FLAGS]")
            for flag in red_flags:
                print(f"  - {flag}")

        if yellow_flags:
            print("\n[YELLOW FLAGS]")
            for flag in yellow_flags:
                print(f"  - {flag}")

        if green_flags:
            print("\n[GREEN FLAGS]")
            for flag in green_flags:
                print(f"  + {flag}")

        print(f"\n{'='*60}")
        print("NOTE: Cannot fetch post engagement (likes/views) via Bot API.")
        print("The Bot API only provides basic channel metadata.")
        print("")
        print("For full engagement analysis, you need:")
        print("1. Telegram User API (MTProto) - requires phone auth")
        print("2. Manual review of posts in the channel")
        print("3. Third-party tools like TGStat.com")
        print(f"{'='*60}")

        # Engagement estimation
        print(f"\n=== ENGAGEMENT ESTIMATION ===")
        print(f"With {member_count:,} subscribers, expect:")
        print(f"  - Healthy view rate: {int(member_count * 0.3):,} - {int(member_count * 0.5):,} views/post")
        print(f"  - Healthy like rate: {int(member_count * 0.01):,} - {int(member_count * 0.05):,} likes/post")
        print(f"  - If likes/views > 10%, likely fake engagement")
        print(f"  - If views < 10% of subscribers, dead/fake audience")

    except TelegramError as e:
        print(f"[ERROR] Could not fetch channel: {e}")
        print("\nPossible reasons:")
        print("  - Channel doesn't exist")
        print("  - Channel is private")
        print("  - Bot is banned from accessing it")

    except Exception as e:
        print(f"[ERROR] Unexpected error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(analyze_channel())
