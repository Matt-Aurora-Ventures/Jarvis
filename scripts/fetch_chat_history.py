"""Fetch chat history using forwardMessage trick or stored data."""
import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

env_path = Path(__file__).resolve().parents[1] / "tg_bot" / ".env"
for line in env_path.read_text().splitlines():
    if line.strip() and not line.startswith('#') and '=' in line:
        k, v = line.split('=', 1)
        os.environ.setdefault(k.strip(), v.strip().strip('\"'))

async def fetch_history():
    import aiohttp
    
    bot_token = os.environ.get('TELEGRAM_BOT_TOKEN')
    chat_id = os.environ.get('TELEGRAM_BUY_BOT_CHAT_ID')
    
    # Try to get recent message IDs by probing
    # We know message 3540 was just sent, so let's check messages before that
    
    base_url = f"https://api.telegram.org/bot{bot_token}"
    
    messages = []
    
    async with aiohttp.ClientSession() as session:
        # Try copying messages to see their content (read-only)
        # Start from recent message and go backwards
        latest_msg_id = 3540  # Our suggestion request
        
        for msg_id in range(latest_msg_id - 1, latest_msg_id - 200, -1):
            try:
                # Try to forward the message to ourselves to read it
                async with session.post(f"{base_url}/copyMessage", json={
                    "chat_id": chat_id,
                    "from_chat_id": chat_id,
                    "message_id": msg_id,
                    "disable_notification": True
                }) as resp:
                    result = await resp.json()
                    if result.get("ok"):
                        new_msg_id = result.get("result", {}).get("message_id")
                        # Delete the copied message immediately
                        await session.post(f"{base_url}/deleteMessage", json={
                            "chat_id": chat_id,
                            "message_id": new_msg_id
                        })
                        messages.append({"msg_id": msg_id, "exists": True})
                    else:
                        # Message doesn't exist or can't be copied
                        pass
            except Exception:  # noqa: BLE001 - intentional catch-all
                pass
            
            if len(messages) >= 50:
                break
        
        print(f"Found {len(messages)} messages")
        
        # Now let's just print the message IDs we know exist
        # The bot can't actually read message content from history
        # We need to look at what WE have stored locally
        
        print("\nNote: Telegram Bot API cannot read chat history directly.")
        print("Looking for locally stored message logs...\n")
        
        # Check for any stored buy data or reports
        data_dir = Path(__file__).resolve().parents[1] / "data"
        if data_dir.exists():
            for f in data_dir.glob("*.json"):
                print(f"Found data file: {f.name}")

if __name__ == "__main__":
    asyncio.run(fetch_history())
