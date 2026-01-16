"""Send v4.6.2 update to Telegram"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from bots.twitter.telegram_sync import TelegramSync

message = """🤖 *JARVIS v4.6.2 - Code Quality & Async Performance*

deep infrastructure work today. the kind that doesn't look flashy but keeps everything running smooth.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚡ *NATIVE ASYNC TWITTER POSTING*
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

rewrote post\\_tweet() from scratch:
• *before:* requests library (blocking)
• *after:* aiohttp (native async)
• *result:* no longer blocking the event loop

your tweets post faster. the system breathes easier.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔒 *SQLITE CONNECTION HARDENING*
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

added proper context managers to spam\\_protection.py:
• connections auto-cleanup after use
• no more database lock issues
• proper resource management

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🐛 *EXCEPTION HANDLING FIXES*
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

fixed bare except: statements that were catching everything:
• buy\\_tracker/bot.py → `except Exception:`
• treasury/backtest.py → `except (ValueError, TypeError):`
• spam\\_protection.py → `except ValueError:`

why it matters: bare except catches SystemExit and KeyboardInterrupt, preventing graceful shutdown.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📦 *FULL IMPROVEMENT LIST*
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. ✅ OAuth token persistence
2. ✅ Circuit breaker verification
3. ✅ Engagement tracker metrics
4. ✅ API caching verification
5. ✅ Max positions → 50
6. ✅ Backtest validation
7. ✅ Grok API cost tracking
8. ✅ Native aiohttp posting
9. ✅ SQLite context managers
10. ✅ Bare except fixes

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

open source: github.com/Matt-Aurora-Ventures/Jarvis
website: jarvislife.io
token: $KR8TIV on Solana

building in public. always. 🤖
"""

async def send():
    sync = TelegramSync()
    if sync.enabled:
        import aiohttp
        url = f"https://api.telegram.org/bot{sync.bot_token}/sendMessage"
        payload = {
            "chat_id": sync.channel_id,
            "text": message,
            "parse_mode": "Markdown"
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload) as resp:
                if resp.status == 200:
                    print('Message sent to Telegram!')
                else:
                    error = await resp.text()
                    print(f'Failed: {error}')
    else:
        print('Telegram sync not enabled - check tokens')

if __name__ == "__main__":
    asyncio.run(send())
