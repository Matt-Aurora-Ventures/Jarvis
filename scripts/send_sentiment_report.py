"""Send a single sentiment report with buy buttons to Telegram."""
import asyncio
import os
import sys
from pathlib import Path

# Fix Windows encoding
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# Load env
env_path = Path(__file__).resolve().parents[1] / "tg_bot" / ".env"
if env_path.exists():
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith('#') and '=' in line:
            key, value = line.split('=', 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"'))


async def send_report():
    import aiohttp
    from bots.buy_tracker.sentiment_report import SentimentReportGenerator
    
    bot_token = os.environ.get('TELEGRAM_BOT_TOKEN')
    chat_id = os.environ.get('TELEGRAM_BUY_BOT_CHAT_ID')
    xai_key = os.environ.get('XAI_API_KEY')
    
    if not bot_token or not chat_id:
        print('Missing TELEGRAM_BOT_TOKEN or TELEGRAM_BUY_BOT_CHAT_ID')
        return
    
    print('Generating sentiment report with buy buttons...')
    generator = SentimentReportGenerator(
        bot_token=bot_token,
        chat_id=chat_id,
        xai_api_key=xai_key,
        interval_minutes=30,
    )
    
    generator._session = aiohttp.ClientSession()
    
    try:
        await generator.generate_and_post_report()
        print('Report sent successfully!')
    finally:
        await generator._session.close()


if __name__ == "__main__":
    asyncio.run(send_report())
