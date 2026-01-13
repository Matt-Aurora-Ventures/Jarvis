#!/usr/bin/env python3
"""
Send goodnight message and freeze chat.
Run: python scripts/send_goodnight.py
"""

import os
import asyncio
from pathlib import Path

# Manual .env loading to handle encoding issues
def load_env_manual():
    # Check multiple locations for .env
    possible_paths = [
        Path(__file__).parent.parent / ".env",
        Path(__file__).parent.parent / "tg_bot" / ".env",
    ]

    for env_path in possible_paths:
        if not env_path.exists():
            continue

        try:
            # Try UTF-8 first
            content = env_path.read_text(encoding='utf-8')
        except UnicodeDecodeError:
            try:
                content = env_path.read_text(encoding='utf-16')
            except:
                content = env_path.read_text(encoding='latin-1')

        for line in content.splitlines():
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, _, value = line.partition('=')
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key and value and key not in os.environ:
                    os.environ[key] = value
        print(f"Loaded env from: {env_path}")
        return

    print("No .env file found!")

def load_env_manual_old():
    env_path = Path(__file__).parent.parent / ".env"
    if env_path.exists():
        try:
            # Try UTF-8 first
            content = env_path.read_text(encoding='utf-8')
        except UnicodeDecodeError:
            # Fall back to UTF-16 or Latin-1
            try:
                content = env_path.read_text(encoding='utf-16')
            except:
                content = env_path.read_text(encoding='latin-1')

        for line in content.splitlines():
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, _, value = line.partition('=')
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key and value and key not in os.environ:
                    os.environ[key] = value

load_env_manual()

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
# Try multiple chat ID env vars
CHAT_ID = os.getenv("TELEGRAM_ADMIN_CHAT_ID") or os.getenv("TELEGRAM_BUY_BOT_CHAT_ID")

if not TOKEN:
    print("ERROR: TELEGRAM_BOT_TOKEN not set in .env")
    exit(1)

if not CHAT_ID:
    print("ERROR: TELEGRAM_ADMIN_CHAT_ID not set in .env")
    print("Please set it to your group chat ID (e.g., -1001234567890)")
    exit(1)


MESSAGE = """
🌙 *Hey everyone - Matt here!*

Just wanted to hop in real quick before I crash...

*THANK YOU* to every single one of you in here. Seriously. The support has been unreal and I'm genuinely grateful for this community we're building together. 💜

Quick updates:
• 🤖 *Bot works!* We got JARVIS running
• 📺 *Live trading TOMORROW* - you don't want to miss it
• 🎥 *Streaming live ALL NEXT WEEK* - let's gooo
• 🐦 *X community + site touch-ups* tomorrow
• 📄 *Whitepaper* coming + testing everything we can

I gotta sleep (it's been a long one), but tomorrow I'll be way more vocal and we're going to have some fun.

*Much love to all of you.*

See you tomorrow. Let's make history. 🚀

— Matt

_Chat frozen for the night. Sweet dreams fam!_ 🔒
"""


async def main():
    from telegram import Bot, ChatPermissions

    bot = Bot(token=TOKEN)

    print(f"Sending message to chat {CHAT_ID}...")

    # Send the message
    msg = await bot.send_message(
        chat_id=CHAT_ID,
        text=MESSAGE,
        parse_mode="Markdown"
    )
    print(f"[OK] Message sent! Message ID: {msg.message_id}")

    # Freeze the chat (restrict all members from sending messages)
    print("Freezing chat...")
    try:
        await bot.set_chat_permissions(
            chat_id=CHAT_ID,
            permissions={
                "can_send_messages": False,
                "can_send_media_messages": False,
                "can_send_polls": False,
                "can_send_other_messages": False,
                "can_add_web_page_previews": False,
                "can_change_info": False,
                "can_invite_users": True,  # Allow invites still
                "can_pin_messages": False,
            }
        )
        print("[OK] Chat frozen! Members can read but not send messages.")
    except Exception as e:
        print(f"[WARN] Could not freeze chat: {e}")
        print("  (Bot may need admin permissions with 'Restrict Members' enabled)")

    print("\n" + "="*50)
    print("PROOF OF DELIVERY")
    print("="*50)
    print(f"Chat ID: {CHAT_ID}")
    print(f"Message ID: {msg.message_id}")
    print(f"Timestamp: {msg.date}")
    print(f"Chat frozen: Attempted")
    print("="*50)
    print("\nGoodnight! Tell them you love them!")


if __name__ == "__main__":
    asyncio.run(main())
