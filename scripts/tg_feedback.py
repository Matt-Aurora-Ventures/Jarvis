"""
Quick Telegram feedback helper for Cascade/console.

Usage:
    python scripts/tg_feedback.py "message to send"
    python scripts/tg_feedback.py --complete <request_id> "result message"
    python scripts/tg_feedback.py --status  # Show pending requests
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


async def send_message(text: str):
    """Send a message to Telegram."""
    import aiohttp
    
    bot_token = os.environ.get('TELEGRAM_BOT_TOKEN')
    chat_id = os.environ.get('TELEGRAM_BUY_BOT_CHAT_ID')
    
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    
    async with aiohttp.ClientSession() as session:
        async with session.post(url, json={
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML"
        }) as resp:
            data = await resp.json()
            return data.get("ok", False)


async def complete_request(request_id: str, result: str):
    """Complete a request and send feedback to Telegram."""
    from core.telegram_console_bridge import get_console_bridge
    
    bridge = get_console_bridge()
    bridge.complete_request(request_id, result)
    
    message = f"<b>done.</b>\n\nrequest: <code>{request_id}</code>\n\n{result[:3500]}"
    success = await send_message(message)
    return success


def show_pending():
    """Show pending requests."""
    from core.telegram_console_bridge import get_console_bridge
    
    bridge = get_console_bridge()
    pending = bridge.get_pending_requests()
    
    if not pending:
        print("No pending requests.")
        return
    
    print(f"\n{'='*60}")
    print(f"PENDING REQUESTS ({len(pending)})")
    print('='*60)
    
    for r in pending:
        print(f"\nID: {r['id']}")
        print(f"From: @{r['username']}")
        print(f"Request: {r['message'][:100]}...")
        print(f"Time: {r['created_at']}")
    
    print('='*60)


def main():
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python scripts/tg_feedback.py \"message\"")
        print("  python scripts/tg_feedback.py --complete <id> \"result\"")
        print("  python scripts/tg_feedback.py --status")
        return
    
    if sys.argv[1] == "--status":
        show_pending()
        return
    
    if sys.argv[1] == "--complete":
        if len(sys.argv) < 4:
            print("Usage: python scripts/tg_feedback.py --complete <request_id> \"result\"")
            return
        request_id = sys.argv[2]
        result = sys.argv[3]
        success = asyncio.run(complete_request(request_id, result))
        print(f"Completed and sent to Telegram: {success}")
        return
    
    # Just send a message
    message = " ".join(sys.argv[1:])
    success = asyncio.run(send_message(message))
    print(f"Sent to Telegram: {success}")


if __name__ == "__main__":
    main()
