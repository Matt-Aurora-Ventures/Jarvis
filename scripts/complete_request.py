"""
Complete a Telegram request and send result back.

Usage: python scripts/complete_request.py <request_id> "<result message>"
"""
import asyncio
import os
import sys
from pathlib import Path

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


async def complete_and_notify(request_id: str, result: str):
    """Complete request and notify Telegram."""
    import aiohttp
    from core.telegram_console_bridge import get_console_bridge
    
    bridge = get_console_bridge()
    
    # Complete the request
    bridge.complete_request(request_id, result)
    print(f"Marked request {request_id} as completed")
    
    # Send to Telegram
    bot_token = os.environ.get('TELEGRAM_BOT_TOKEN')
    chat_id = os.environ.get('TELEGRAM_BUY_BOT_CHAT_ID')
    
    if not bot_token or not chat_id:
        print("Missing Telegram credentials")
        return
    
    message = f"<b>request completed</b>\n\nid: <code>{request_id}</code>\n\n{result[:3500]}"
    
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    
    async with aiohttp.ClientSession() as session:
        async with session.post(url, json={
            "chat_id": chat_id,
            "text": message,
            "parse_mode": "HTML"
        }) as resp:
            data = await resp.json()
            if data.get("ok"):
                print("Telegram notified successfully")
            else:
                print(f"Telegram error: {data}")


def main():
    if len(sys.argv) < 3:
        print("Usage: python scripts/complete_request.py <request_id> \"<result>\"")
        print("\nPending requests:")
        
        from core.telegram_console_bridge import get_console_bridge
        bridge = get_console_bridge()
        pending = bridge.get_pending_requests()
        
        if pending:
            for r in pending:
                print(f"  - {r['id']}: {r['message'][:60]}...")
        else:
            print("  (none)")
        return
    
    request_id = sys.argv[1]
    result = sys.argv[2]
    
    asyncio.run(complete_and_notify(request_id, result))


if __name__ == "__main__":
    main()
