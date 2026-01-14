"""Send vibe coding v2 enhancement announcement."""
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

    message = """<b>JARVIS Vibe Coding v2.1 - Queue Fix</b>

<b>New Commands</b>
- <code>/queue</code> - show pending CLI executions
- <code>/stats</code> - show execution metrics

<b>Bug Fixes</b>
- Fixed queue depth tracking (now properly cleans up after execution)
- Added finally block for guaranteed queue cleanup

<b>Test Coverage</b>
12 tests passing (added queue status test)

vibe code anything. i'll build it."""

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"

    async with aiohttp.ClientSession() as session:
        async with session.post(url, json={
            "chat_id": chat_id,
            "text": message,
            "parse_mode": "HTML"
        }) as resp:
            result = await resp.json()
            if result.get("ok"):
                print("Message sent to Telegram!")
            else:
                print(f"Failed: {result}")

if __name__ == "__main__":
    asyncio.run(send())
