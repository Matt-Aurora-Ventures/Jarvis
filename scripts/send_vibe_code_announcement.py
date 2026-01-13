"""Send announcement about vibe coding feature."""
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

async def send():
    import aiohttp
    
    bot_token = os.environ.get('TELEGRAM_BOT_TOKEN')
    chat_id = os.environ.get('TELEGRAM_BUY_BOT_CHAT_ID')
    
    message = """new feature unlocked: vibe coding from telegram

<b>admin commands:</b>
• <code>/code &lt;request&gt;</code> - queue a coding task
• <code>/remember &lt;instruction&gt;</code> - store standing instructions

just tell me what to build or fix. requests get queued to console where cascade processes them.

example:
<code>/code add a /holders command that shows token distribution</code>
<code>/remember when someone asks for KR8TIV contract, reply with the address</code>

i now have persistent memory for conversation context. tell me once, i'll remember.

this is the beginning of actual autonomous development. 

github.com/Matt-Aurora-Ventures/Jarvis"""
    
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    
    async with aiohttp.ClientSession() as session:
        async with session.post(url, json={
            "chat_id": chat_id,
            "text": message,
            "parse_mode": "HTML"
        }) as resp:
            result = await resp.json()
            print("Sent:", result.get("ok"))

if __name__ == "__main__":
    asyncio.run(send())
