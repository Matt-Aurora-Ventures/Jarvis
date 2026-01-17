"""
Admin setup - Send messages, pin, unmute chat
"""

import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / "tg_bot" / ".env")

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN") or os.getenv("TG_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_BROADCAST_CHAT_ID", "-1003408655098")


async def send_and_pin():
    """Send Matt sleeping message and pin it."""
    import aiohttp

    base_url = f"https://api.telegram.org/bot{BOT_TOKEN}"

    async with aiohttp.ClientSession() as session:
        # Send the message
        msg = """hey everyone - matt needs one more hour of sleep but will be up soon.

jarvis will be admin in the meantime. he's watching the chat and ready to help.

feel free to chat, ask questions, drop suggestions. jarvis is here.

-- jarvis (on behalf of matt)"""

        print("Sending Matt sleeping message...")
        async with session.post(f"{base_url}/sendMessage", json={
            "chat_id": CHAT_ID,
            "text": msg
        }) as resp:
            if resp.status == 200:
                data = await resp.json()
                msg_id = data["result"]["message_id"]
                print(f"  [OK] Message sent: {msg_id}")

                # Pin the message
                print("Pinning message...")
                async with session.post(f"{base_url}/pinChatMessage", json={
                    "chat_id": CHAT_ID,
                    "message_id": msg_id,
                    "disable_notification": True
                }) as pin_resp:
                    if pin_resp.status == 200:
                        print("  [OK] Message pinned")
                    else:
                        err = await pin_resp.text()
                        print(f"  [FAIL] Pin error: {err}")
            else:
                err = await resp.text()
                print(f"  [FAIL] Send error: {err}")

        # Unmute the chat (set permissions to allow messages)
        print("\nUnmuting chat (enabling messages)...")
        async with session.post(f"{base_url}/setChatPermissions", json={
            "chat_id": CHAT_ID,
            "permissions": {
                "can_send_messages": True,
                "can_send_audios": True,
                "can_send_documents": True,
                "can_send_photos": True,
                "can_send_videos": True,
                "can_send_video_notes": True,
                "can_send_voice_notes": True,
                "can_send_polls": True,
                "can_send_other_messages": True,
                "can_add_web_page_previews": True,
                "can_change_info": False,
                "can_invite_users": True,
                "can_pin_messages": False,
                "can_manage_topics": False
            }
        }) as perm_resp:
            if perm_resp.status == 200:
                print("  [OK] Chat unmuted - everyone can speak")
            else:
                err = await perm_resp.text()
                print(f"  [FAIL] Unmute error: {err}")


async def main():
    print("=" * 50)
    print("ADMIN SETUP")
    print("=" * 50)
    await send_and_pin()
    print("\n[DONE]")


if __name__ == "__main__":
    asyncio.run(main())
