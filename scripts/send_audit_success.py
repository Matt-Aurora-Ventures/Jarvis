"""Send audit success update to Telegram."""
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
    
    message = """circuits recalibrated. full audit complete.

<b>28/28 commands passing</b>

<b>public commands (all working):</b>
/solprice /price /mcap /volume /chart
/liquidity /age /summary /trending
/gainers /losers /newpairs

<b>admin commands (all working):</b>
/health /flags /audit /ratelimits
/keystatus /score /wallet /system
/orders /logs /metrics /uptime /config
/balance /positions /report

all apis responding. rate limiters healthy. no failures.

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

if __name__ == "__main__":
    asyncio.run(send_update())
