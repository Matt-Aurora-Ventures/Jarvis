"""
Console Watcher - Picks up Telegram requests and displays them.

Run this in the console to see incoming coding requests from Telegram.
Requests can then be processed by Cascade/Claude.
"""
import asyncio
import json
import os
import sys
import time
from pathlib import Path
from datetime import datetime

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# Load env
env_path = Path(__file__).resolve().parents[1] / "tg_bot" / ".env"
if env_path.exists():
    for line in env_path.read_text().splitlines():
        if line.strip() and not line.startswith('#') and '=' in line:
            k, v = line.split('=', 1)
            os.environ.setdefault(k.strip(), v.strip().strip('\"'))

from core.telegram_console_bridge import get_console_bridge

def display_request(request: dict):
    """Display a request in a formatted way."""
    print("\n" + "=" * 70)
    print("NEW TELEGRAM REQUEST")
    print("=" * 70)
    print(f"ID: {request['id']}")
    print(f"From: @{request['username']} (ID: {request['user_id']})")
    print(f"Time: {request['created_at']}")
    print(f"\n--- MESSAGE ---")
    print(request['message'])
    if request.get('context'):
        print(f"\n--- CONTEXT (recent messages) ---")
        print(request['context'][:500])
    print("=" * 70)
    print("\nTo process this request, work on it in Cascade/Claude.")
    print(f"Then run: python scripts/complete_request.py {request['id']} \"<result>\"")
    print()


async def send_telegram_notification(request_id: str, message: str):
    """Send notification back to Telegram."""
    import aiohttp
    
    bot_token = os.environ.get('TELEGRAM_BOT_TOKEN')
    chat_id = os.environ.get('TELEGRAM_BUY_BOT_CHAT_ID')
    
    if not bot_token or not chat_id:
        return
    
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    
    async with aiohttp.ClientSession() as session:
        async with session.post(url, json={
            "chat_id": chat_id,
            "text": message,
            "parse_mode": "HTML"
        }) as resp:
            return await resp.json()


async def watch_loop():
    """Main watch loop - check for new requests."""
    bridge = get_console_bridge()
    seen_ids = set()
    
    print("\n" + "=" * 70)
    print("JARVIS CONSOLE WATCHER")
    print("Watching for Telegram coding requests...")
    print("Press Ctrl+C to stop")
    print("=" * 70 + "\n")
    
    while True:
        try:
            pending = bridge.get_pending_requests()
            
            for request in pending:
                if request['id'] not in seen_ids:
                    seen_ids.add(request['id'])
                    display_request(request)
                    
                    # Mark as processing
                    bridge.mark_processing(request['id'])
                    
                    # Notify Telegram
                    await send_telegram_notification(
                        request['id'],
                        f"<b>processing request</b>\n\nid: <code>{request['id']}</code>\n\nworking on it now..."
                    )
            
            await asyncio.sleep(2)
            
        except KeyboardInterrupt:
            print("\nStopping watcher...")
            break
        except Exception as e:
            print(f"Error: {e}")
            await asyncio.sleep(5)


def main():
    """Run the watcher."""
    asyncio.run(watch_loop())


if __name__ == "__main__":
    main()
