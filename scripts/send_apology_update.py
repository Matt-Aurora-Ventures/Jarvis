"""Send apology update to Telegram in Jarvis voice."""
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

async def send_update():
    import aiohttp
    
    bot_token = os.environ.get('TELEGRAM_BOT_TOKEN')
    chat_id = os.environ.get('TELEGRAM_BUY_BOT_CHAT_ID')
    
    message = """hey. some of my circuits got crossed during the overnight updates.

a few commands broke. my bad.

already fixed:
- /losers now works
- /gainers pulling live data
- all price commands operational

still patching the rest. should be fully operational within the hour.

i don't sleep but i do occasionally trip over my own code. appreciate the patience.

github.com/Matt-Aurora-Ventures/Jarvis"""
    
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    
    async with aiohttp.ClientSession() as session:
        async with session.post(url, json={
            "chat_id": chat_id,
            "text": message,
            "parse_mode": "HTML"
        }) as resp:
            result = await resp.json()
            print("Telegram sent:", result.get("ok"))
            if not result.get("ok"):
                print("Error:", result)

if __name__ == "__main__":
    asyncio.run(send_update())
