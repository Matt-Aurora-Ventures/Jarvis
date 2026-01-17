"""
RALPH WIGGUM LOOP - Continuous Jarvis Monitoring

Monitors:
- Twitter bot posting and interactions
- Telegram bot conversations and responses
- Suggests and implements improvements
- Restarts bots when needed
- Keeps Jarvis engaging and improving
"""

import asyncio
import os
import sys
import json
import subprocess
import time
from pathlib import Path
from datetime import datetime, timedelta

# Setup
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / "tg_bot" / ".env")
load_dotenv(Path(__file__).parent.parent / "bots" / "twitter" / ".env")

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN") or os.getenv("TG_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_BROADCAST_CHAT_ID", "-1003408655098")
ADMIN_ID = os.getenv("TELEGRAM_ADMIN_IDS", "8527130908")

# State
last_twitter_post = 0
last_sentiment_report = 0
last_audit = 0
improvements_made = []


async def get_recent_messages(hours: int = 48):
    """Fetch recent messages from the Telegram chat."""
    import aiohttp

    messages = []
    base_url = f"https://api.telegram.org/bot{BOT_TOKEN}"

    async with aiohttp.ClientSession() as session:
        # Get updates
        async with session.get(f"{base_url}/getUpdates", params={"limit": 100, "offset": -100}) as resp:
            if resp.status == 200:
                data = await resp.json()
                for update in data.get("result", []):
                    msg = update.get("message", {})
                    if msg:
                        messages.append({
                            "id": msg.get("message_id"),
                            "from": msg.get("from", {}).get("username", "unknown"),
                            "text": msg.get("text", ""),
                            "date": msg.get("date", 0)
                        })

    return messages


async def send_telegram(text: str, reply_to: int = None):
    """Send a message to the Telegram chat."""
    import aiohttp

    base_url = f"https://api.telegram.org/bot{BOT_TOKEN}"

    async with aiohttp.ClientSession() as session:
        payload = {
            "chat_id": CHAT_ID,
            "text": text,
            "parse_mode": "HTML"
        }
        if reply_to:
            payload["reply_to_message_id"] = reply_to

        async with session.post(f"{base_url}/sendMessage", json=payload) as resp:
            return resp.status == 200


async def audit_suggestions():
    """Audit last 48h for user suggestions."""
    print("\n[AUDIT] Scanning for suggestions...")

    messages = await get_recent_messages(48)

    suggestion_keywords = [
        "could you", "can you add", "would be cool", "suggestion",
        "feature request", "idea:", "what if", "maybe add",
        "it would be nice", "please add", "need a", "want a"
    ]

    suggestions = []
    for msg in messages:
        text = msg.get("text", "").lower()
        if any(kw in text for kw in suggestion_keywords):
            suggestions.append({
                "from": msg.get("from"),
                "text": msg.get("text"),
                "date": datetime.fromtimestamp(msg.get("date", 0)).strftime("%Y-%m-%d %H:%M")
            })

    return suggestions


async def check_twitter_bot():
    """Check Twitter bot status and post if needed."""
    global last_twitter_post

    now = time.time()

    # Post every 60 minutes
    if now - last_twitter_post > 3600:
        print("\n[TWITTER] Time for a post...")
        try:
            result = subprocess.run(
                ["python", "bots/twitter/run_autonomous.py", "--once"],
                capture_output=True,
                text=True,
                timeout=120,
                cwd=str(Path(__file__).parent.parent)
            )

            if "SUCCESS" in result.stdout:
                print("  [OK] Tweet posted")
                last_twitter_post = now
            else:
                print(f"  [WARN] Twitter output: {result.stdout[-200:]}")

        except Exception as e:
            print(f"  [ERROR] Twitter bot: {e}")


async def send_sentiment_report():
    """Generate and send a SINGLE sentiment report (not continuous)."""
    global last_sentiment_report

    now = time.time()

    # Report every 60 minutes
    if now - last_sentiment_report > 3600:
        print("\n[SENTIMENT] Generating single report...")
        try:
            # Run single report, not continuous loop
            result = subprocess.run(
                ["python", "-c", """
import asyncio
import sys
import os
sys.path.insert(0, '.')
from pathlib import Path
from dotenv import load_dotenv
load_dotenv(Path('tg_bot') / '.env')

async def run_once():
    from bots.buy_tracker.sentiment_report import SentimentReportGenerator

    bot_token = os.environ.get('TELEGRAM_BOT_TOKEN')
    chat_id = os.environ.get('TELEGRAM_BUY_BOT_CHAT_ID') or os.environ.get('TELEGRAM_BROADCAST_CHAT_ID')
    xai_key = os.environ.get('XAI_API_KEY')

    if not bot_token or not chat_id:
        print('Missing tokens')
        return

    generator = SentimentReportGenerator(
        bot_token=bot_token,
        chat_id=chat_id,
        xai_api_key=xai_key,
        interval_minutes=60,
    )

    # Run SINGLE report, not continuous loop
    await generator.generate_and_post_report()
    print('Report posted!')

asyncio.run(run_once())
"""],
                capture_output=True,
                text=True,
                timeout=180,
                cwd=str(Path(__file__).parent.parent)
            )

            if result.returncode == 0 or "Report posted" in result.stdout:
                print("  [OK] Sentiment report sent")
                last_sentiment_report = now
            else:
                print(f"  [WARN] Report output: {result.stdout[-200:]}")
                print(f"  [WARN] Report error: {result.stderr[-200:]}")

        except Exception as e:
            print(f"  [ERROR] Sentiment report: {e}")


async def monitor_telegram_responses():
    """Monitor how Jarvis responds in Telegram."""
    import aiohttp

    base_url = f"https://api.telegram.org/bot{BOT_TOKEN}"

    async with aiohttp.ClientSession() as session:
        async with session.get(f"{base_url}/getUpdates", params={"limit": 10, "offset": -10}) as resp:
            if resp.status == 200:
                data = await resp.json()

                for update in data.get("result", []):
                    msg = update.get("message", {})
                    text = msg.get("text", "")
                    username = msg.get("from", {}).get("username", "")

                    # Check if someone mentioned Jarvis
                    if "jarvis" in text.lower() and username != "jarvis_lifeos":
                        print(f"\n[MONITOR] @{username}: {text[:100]}...")


async def run_continuous():
    """Main continuous monitoring loop."""
    print("=" * 60)
    print("RALPH WIGGUM LOOP - CONTINUOUS MONITORING")
    print("=" * 60)
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("Press Ctrl+C to stop\n")

    iteration = 0

    while True:
        iteration += 1
        print(f"\n{'='*40}")
        print(f"[ITERATION {iteration}] {datetime.now().strftime('%H:%M:%S')}")
        print(f"{'='*40}")

        try:
            # Check Twitter bot
            await check_twitter_bot()

            # Monitor Telegram
            await monitor_telegram_responses()

            # Sentiment report
            await send_sentiment_report()

            # Audit suggestions every 4 hours
            global last_audit
            if time.time() - last_audit > 14400:
                suggestions = await audit_suggestions()
                if suggestions:
                    print(f"\n[AUDIT] Found {len(suggestions)} suggestions")
                    for s in suggestions[:5]:
                        print(f"  - @{s['from']}: {s['text'][:50]}...")
                last_audit = time.time()

            print("\n[SLEEP] Waiting 5 minutes...")
            await asyncio.sleep(300)  # Check every 5 minutes

        except KeyboardInterrupt:
            print("\n\n[STOP] Monitoring stopped by user")
            break
        except Exception as e:
            print(f"\n[ERROR] Loop error: {e}")
            await asyncio.sleep(60)


if __name__ == "__main__":
    asyncio.run(run_continuous())
