#!/usr/bin/env python3
"""
Fetch Telegram message history and analyze AI picks for 15% win / 15% stop loss strategy.
"""

import asyncio
import os
import re
import json
from datetime import datetime, timedelta
from telegram import Bot
from dotenv import load_dotenv
from typing import List, Dict, Optional
from dataclasses import dataclass, asdict

load_dotenv()

@dataclass
class TokenPick:
    """Represents an AI pick from Telegram."""
    date: str
    token_symbol: str
    token_name: Optional[str]
    entry_price: Optional[float]
    sentiment: Optional[str]
    score: Optional[float]
    message_text: str
    message_id: int

async def fetch_messages_via_export(chat_id: int):
    """
    Note: Bot API can't read message history for groups.
    We need to either:
    1. Export chat history manually from Telegram desktop
    2. Use MTProto client (Telethon/Pyrogram) with user credentials
    3. Parse from bot's own sent messages if we have message IDs

    For now, let's try to use the bot to get its own sent messages.
    """
    bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
    bot = Bot(token=bot_token)

    me = await bot.get_me()
    print(f"Bot: @{me.username} (ID: {me.id})")
    print(f"Chat ID: {chat_id}")
    print()

    # Bot API limitation: can't read message history without message IDs
    # Let's try to get chat info at least
    try:
        chat = await bot.get_chat(chat_id)
        print(f"Chat info:")
        print(f"  Title: {chat.title}")
        print(f"  Type: {chat.type}")
        print(f"  Description: {chat.description[:100] if chat.description else 'None'}...")
        print()
    except Exception as e:
        print(f"Could not get chat info: {e}")

    return None

def parse_message_for_pick(text: str, message_id: int, date: str) -> Optional[TokenPick]:
    """Extract token pick information from message text."""
    if not text:
        return None

    # Look for bullish sentiment indicators
    if not any(word in text.upper() for word in ['BULLISH', 'BUY', 'LONG', 'ENTRY', '🎯', '📈']):
        return None

    # Extract token symbol
    # Common patterns: $SYMBOL, SYMBOL/USD, Token: SYMBOL, etc.
    symbol_patterns = [
        r'\$([A-Z0-9]{2,10})',  # $TOKEN
        r'Token:\s*([A-Z0-9]{2,10})',  # Token: SYMBOL
        r'Symbol:\s*([A-Z0-9]{2,10})',  # Symbol: SYMBOL
        r'^([A-Z0-9]{2,10})\s*[-:]',  # SYMBOL: or SYMBOL -
    ]

    symbol = None
    for pattern in symbol_patterns:
        match = re.search(pattern, text, re.MULTILINE)
        if match:
            symbol = match.group(1)
            break

    if not symbol:
        return None

    # Extract entry price
    price = None
    price_patterns = [
        r'Entry[:\s]*\$?([0-9]+\.?[0-9]*)',
        r'Price[:\s]*\$?([0-9]+\.?[0-9]*)',
        r'\$([0-9]+\.?[0-9]+)',
    ]

    for pattern in price_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            try:
                price = float(match.group(1))
                break
            except ValueError:
                pass

    # Extract sentiment
    sentiment = None
    if 'BULLISH' in text.upper():
        sentiment = 'BULLISH'
    elif 'SLIGHTLY BULLISH' in text.upper():
        sentiment = 'SLIGHTLY BULLISH'

    # Extract score
    score = None
    score_match = re.search(r'Score[:\s]*([0-9\.]+)', text, re.IGNORECASE)
    if score_match:
        try:
            score = float(score_match.group(1))
        except ValueError:
            pass

    if symbol and (price or sentiment):
        return TokenPick(
            date=date,
            token_symbol=symbol,
            token_name=None,  # Extract if available
            entry_price=price,
            sentiment=sentiment,
            score=score,
            message_text=text[:500],  # First 500 chars
            message_id=message_id
        )

    return None

async def analyze_exported_json(json_file: str):
    """
    Analyze Telegram export JSON file.

    To export chat history:
    1. Open Telegram Desktop
    2. Go to the chat
    3. Click ⋮ (menu) → Export chat history
    4. Choose JSON format
    5. Save and provide the path here
    """
    if not os.path.exists(json_file):
        print(f"Export file not found: {json_file}")
        print()
        print("TO EXPORT TELEGRAM CHAT HISTORY:")
        print("1. Open Telegram Desktop")
        print("2. Go to your Jarvis bot chat")
        print("3. Click ⋮ (three dots menu)")
        print("4. Select 'Export chat history'")
        print("5. Choose 'Machine-readable JSON' format")
        print("6. Export and save to:", json_file)
        return None

    with open(json_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    print(f"Loaded {len(data.get('messages', []))} messages from export")

    picks = []
    for msg in data.get('messages', []):
        text = msg.get('text', '')
        if isinstance(text, list):
            # Text can be array of objects in exports
            text = ' '.join(t.get('text', '') if isinstance(t, dict) else str(t) for t in text)

        date = msg.get('date', '')
        msg_id = msg.get('id', 0)

        pick = parse_message_for_pick(text, msg_id, date)
        if pick:
            picks.append(pick)

    print(f"Found {len(picks)} AI picks")
    print()

    # Print picks
    for i, pick in enumerate(picks[:20], 1):
        print(f"{i}. {pick.token_symbol}")
        print(f"   Date: {pick.date}")
        print(f"   Entry: ${pick.entry_price}" if pick.entry_price else "   Entry: Unknown")
        print(f"   Sentiment: {pick.sentiment}")
        print(f"   Score: {pick.score}" if pick.score else "")
        print()

    # Save picks to JSON
    picks_file = 'ai_picks_analysis.json'
    with open(picks_file, 'w') as f:
        json.dump([asdict(p) for p in picks], f, indent=2)

    print(f"✓ Saved {len(picks)} picks to {picks_file}")
    print()
    print("NEXT STEPS:")
    print("1. For each pick, we need the subsequent price data")
    print("2. Check if price hit +15% (win) or -15% (stop loss) first")
    print("3. Calculate win rate and expected value of the strategy")

    return picks

async def main():
    """Main entry point."""
    chat_id = -1003408655098

    print("TELEGRAM AI PICKS ANALYZER")
    print("=" * 60)
    print()

    # Try bot API first (won't work for reading history)
    await fetch_messages_via_export(chat_id)

    # Check for exported JSON
    export_file = 'telegram_export.json'
    if os.path.exists(export_file):
        await analyze_exported_json(export_file)
    else:
        print("=" * 60)
        print("IMPORTANT: Bot API cannot read message history")
        print("=" * 60)
        print()
        print("Please export your Telegram chat history:")
        print()
        print("1. Open Telegram Desktop")
        print("2. Open the Jarvis bot chat")
        print("3. Click the menu (three dots)")
        print("4. Select 'Export chat history'")
        print("5. Choose 'Machine-readable JSON'")
        print("6. Save as 'telegram_export.json' in this directory")
        print()
        print(f"Then run this script again!")
        print()
        print(f"Alternatively, you can manually:")
        print("- Scroll through your Telegram chat")
        print("- Find messages with 🏆 Top Picks or BULLISH sentiment")
        print("- Check if those tokens hit +15% or -15% first")
        print("- Count wins vs losses")

if __name__ == '__main__':
    asyncio.run(main())
