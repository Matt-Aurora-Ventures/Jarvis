"""
Freeze Telegram channel - remove all permissions from non-admins.
"""
import asyncio
import os
import sys

# Add parent to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from telegram import Bot, ChatPermissions

# Load env from tg_bot config
try:
    from tg_bot.config import get_config
    config = get_config()
except:
    pass

async def freeze_channel():
    """Remove all permissions from non-admins in the channel."""
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_BROADCAST_CHAT_ID")

    if not token:
        print("ERROR: TELEGRAM_BOT_TOKEN not set")
        return

    if not chat_id:
        print("ERROR: TELEGRAM_BROADCAST_CHAT_ID not set")
        return

    bot = Bot(token=token)

    # Completely restrictive permissions - nobody can do anything
    frozen_permissions = ChatPermissions(
        can_send_messages=False,
        can_send_audios=False,
        can_send_documents=False,
        can_send_photos=False,
        can_send_videos=False,
        can_send_video_notes=False,
        can_send_voice_notes=False,
        can_send_polls=False,
        can_send_other_messages=False,
        can_add_web_page_previews=False,
        can_change_info=False,
        can_invite_users=False,
        can_pin_messages=False,
        can_manage_topics=False,
    )

    try:
        # Set default permissions for the chat (affects all non-admins)
        await bot.set_chat_permissions(
            chat_id=int(chat_id),
            permissions=frozen_permissions
        )
        print(f"SUCCESS: Channel {chat_id} is now FROZEN")
        print("All non-admin members can no longer:")
        print("  - Send messages")
        print("  - Send media")
        print("  - Send polls")
        print("  - Add web previews")
        print("  - Change chat info")
        print("  - Invite users")
        print("  - Pin messages")
        print("\nAdmins retain full permissions.")

        # Send a message to the channel about the freeze
        await bot.send_message(
            chat_id=int(chat_id),
            text="🔒 *CHANNEL FROZEN*\n\nThis channel is temporarily locked. Only admins can post.\n\nStay tuned for updates.",
            parse_mode="Markdown"
        )
        print("\nFrozen notification sent to channel.")

    except Exception as e:
        print(f"ERROR: Failed to freeze channel: {e}")

    await bot.close()

if __name__ == "__main__":
    asyncio.run(freeze_channel())
