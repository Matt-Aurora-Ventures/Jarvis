#!/usr/bin/env python3
"""Analyze AI picks from Telegram messages and check 15% win / 15% stop loss strategy."""

import asyncio
import os
import re
from datetime import datetime, timedelta
from telegram import Bot
from dotenv import load_dotenv
import json

load_dotenv()

async def fetch_recent_messages(bot, chat_id, hours=24):
    """Fetch messages from the last N hours."""
    messages = []
    offset = 0

    # Get updates
    updates = await bot.get_updates(offset=offset, limit=100)

    cutoff = datetime.now() - timedelta(hours=hours)

    for update in updates:
        if update.message:
            msg = update.message
            if msg.date > cutoff:
                messages.append({
                    'date': msg.date,
                    'text': msg.text or '',
                    'chat_id': msg.chat_id
                })

    return messages

async def get_chat_history(chat_id=None):
    """Get chat history using the bot."""
    bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
    bot = Bot(token=bot_token)

    # Get bot info
    me = await bot.get_me()
    print(f"Bot: @{me.username}")

    # If no chat_id provided, get updates to find it
    if not chat_id:
        print("\nFetching recent updates to find chat IDs...")
        updates = await bot.get_updates(limit=10)

        chat_ids = set()
        for update in updates:
            if update.message:
                chat_ids.add(update.message.chat_id)

        print(f"\nFound chat IDs: {chat_ids}")

        if len(chat_ids) == 1:
            chat_id = list(chat_ids)[0]
            print(f"Using chat ID: {chat_id}")
        else:
            print("\nMultiple chats found. Please specify which one to analyze.")
            for cid in chat_ids:
                print(f"  {cid}")
            return

    # Fetch messages
    messages = await fetch_recent_messages(bot, chat_id, hours=168)  # Last week
    print(f"\nFetched {len(messages)} messages from last 7 days")

    # Parse for AI picks
    picks = []
    for msg in messages:
        text = msg['text']

        # Look for top picks or sentiment reports
        if '🏆' in text or 'Top' in text or 'Pick' in text or 'BULLISH' in text:
            # Extract token info
            lines = text.split('\n')
            for i, line in enumerate(lines):
                # Look for token mentions with price/entry
                if any(keyword in line.upper() for keyword in ['ENTRY', 'PRICE', '$']):
                    pick_info = {
                        'date': msg['date'],
                        'text': text,
                        'line': line
                    }
                    picks.append(pick_info)

    print(f"\nFound {len(picks)} potential AI picks in messages")

    # Print sample picks
    for i, pick in enumerate(picks[:10], 1):
        print(f"\n{i}. {pick['date']}")
        print(f"   {pick['line'][:100]}")

    return picks, messages

async def main():
    """Main entry point."""
    try:
        picks, messages = await get_chat_history()

        # Save to JSON for manual analysis
        output = {
            'picks': [
                {
                    'date': str(p['date']),
                    'text': p['text']
                }
                for p in picks
            ],
            'total_messages': len(messages)
        }

        output_file = 'telegram_ai_picks.json'
        with open(output_file, 'w') as f:
            json.dump(output, f, indent=2)

        print(f"\n✓ Saved analysis to {output_file}")

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    asyncio.run(main())
