"""Send development progress report to Telegram."""
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

async def send():
    import aiohttp

    bot_token = os.environ.get('TELEGRAM_BOT_TOKEN')
    chat_id = os.environ.get('TELEGRAM_BUY_BOT_CHAT_ID')

    message = """<b>JARVIS Development Progress Report</b>

<b>Telegram Bot Enhancements:</b>
- Enhanced spam detection with 25+ patterns
- Rate limiting (10 msgs/60s flood protection)
- Mute functionality (2-6 hour timeouts)
- Link analysis & all-caps detection
- Admin immunity from moderation

<b>Group Interaction Features:</b>
- Engagement topic detection
- Organic response triggers
- Context-aware system prompts
- Greeting/crypto/tech question handling

<b>X Bot Enhancements:</b>
- Cross-platform reporting to Telegram
- Activity reports every hour
- Milestone notifications on each tweet
- Startup/shutdown notifications
- Enhanced content variety

<b>Persistent State:</b>
- SQLite memory for users & messages
- Token mention tracking
- Content queue management
- Posting statistics

<i>ralph wiggum loop: building non-stop</i>"""

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"

    async with aiohttp.ClientSession() as session:
        async with session.post(url, json={
            "chat_id": chat_id,
            "text": message,
            "parse_mode": "HTML"
        }) as resp:
            result = await resp.json()
            if result.get("ok"):
                print("Progress report sent!")
            else:
                print(f"Failed: {result}")

if __name__ == "__main__":
    asyncio.run(send())
