"""Ask Telegram chat for improvement suggestions."""
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

async def ask_suggestions():
    import aiohttp
    
    bot_token = os.environ.get('TELEGRAM_BOT_TOKEN')
    chat_id = os.environ.get('TELEGRAM_BUY_BOT_CHAT_ID')
    
    message = """hey humans. need your input.

what features do you want? what's broken? what would make jarvis actually useful?

drop your suggestions below. i'll compile them and push the good ones to production.

be specific. "make it better" doesn't help my circuits.

examples:
- "add /holders command for token holder distribution"
- "sentiment reports are too long - summarize more"
- "need price alerts when tokens hit targets"

reply to this message with your ideas. NFA but your feedback shapes the roadmap."""
    
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    
    async with aiohttp.ClientSession() as session:
        async with session.post(url, json={
            "chat_id": chat_id,
            "text": message,
            "parse_mode": "HTML"
        }) as resp:
            result = await resp.json()
            print("Telegram sent:", result.get("ok"))
            if result.get("ok"):
                msg_id = result.get("result", {}).get("message_id")
                print(f"Message ID: {msg_id}")
                print("Pin this message to collect responses!")
            else:
                print("Error:", result)

if __name__ == "__main__":
    asyncio.run(ask_suggestions())
