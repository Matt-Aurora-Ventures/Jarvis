"""
Post available commands to the Telegram channel.
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from telegram import Bot

try:
    from tg_bot.config import get_config
    config = get_config()
except:
    pass

async def post_commands():
    """Post command list to channel."""
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_BROADCAST_CHAT_ID")

    bot = Bot(token=token)

    commands_message = """
🤖 *JARVIS COMMANDS*

━━━ *Trading* ━━━
`/report` - Sentiment report with top picks
`/trending` - Trending tokens (free)
`/analyze <token>` - Deep analysis on any token
`/balance` - Treasury balance
`/positions` - Open positions
`/settings` - Trading settings

━━━ *Market Data* ━━━
`/stock <symbol>` - Stock price & analysis
`/xstock <symbol>` - Solana-backed stock tokens
`/fear` - Fear & Greed index

━━━ *Moderation (Admin)* ━━━
`/modstats` - Moderation statistics
`/addscam <wallet>` - Flag scam wallet
`/trust` - Mark user as trusted (reply)
`/warn [reason]` - Warn user (reply)
`/report` - Report spam (reply to msg)

━━━ *Info* ━━━
`/start` - Welcome message
`/status` - Bot status
`/costs` - API usage costs
`/help` - This help

━━━━━━━━━━━━━━━━━━━━━━
_Channel is currently frozen_
_Only admins can post_
━━━━━━━━━━━━━━━━━━━━━━
"""

    try:
        await bot.send_message(
            chat_id=int(chat_id),
            text=commands_message,
            parse_mode="Markdown"
        )
        print("Commands posted to channel")
    except Exception as e:
        print(f"Error: {e}")

    await bot.close()

if __name__ == "__main__":
    asyncio.run(post_commands())
