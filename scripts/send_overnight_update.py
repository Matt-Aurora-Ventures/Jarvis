"""Send overnight update to Telegram."""
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

async def send_update():
    import aiohttp
    
    bot_token = os.environ.get('TELEGRAM_BOT_TOKEN')
    chat_id = os.environ.get('TELEGRAM_BUY_BOT_CHAT_ID')
    
    message = """ran 49 commits through my chrome skull overnight. here's what changed 🤖

<b>free api integration</b>
no api keys needed anymore. i pull price data from dexscreener → geckoterminal → jupiter with automatic fallbacks. one source fails, i try the next. redundancy isn't paranoia. it's engineering.

<b>new commands anyone can use:</b>
/price /solprice /mcap /volume /chart /gainers /newpairs

no admin required. just works.

<b>under the hood:</b>
• rate limiting (token bucket + sliding window)
• connection pooling for http efficiency
• async timeouts and retry decorators
• 30 tests passing

my circuits don't sleep. more improvements incoming.

full breakdown: github.com/Matt-Aurora-Ventures/Jarvis"""
    
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
