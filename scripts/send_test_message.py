"""Send a test message to verify bot is working."""
import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

env_path = Path(__file__).resolve().parents[1] / "tg_bot" / ".env"
for line in env_path.read_text().splitlines():
    if line.strip() and not line.startswith('#') and '=' in line:
        k, v = line.split('=', 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"'))

async def send_test():
    import aiohttp
    
    bot_token = os.environ.get('TELEGRAM_BOT_TOKEN')
    chat_id = os.environ.get('TELEGRAM_BUY_BOT_CHAT_ID')
    
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    
    async with aiohttp.ClientSession() as session:
        async with session.post(url, json={
            "chat_id": chat_id,
            "text": "BUY BUTTONS FIXED - Click any button above to test!\n\nFixes applied:\n- Contract address resolution\n- Unicode encoding\n- Trade execution logging",
            "parse_mode": "HTML"
        }) as resp:
            result = await resp.json()
            print("Message sent:", result.get("ok"))

if __name__ == "__main__":
    asyncio.run(send_test())
