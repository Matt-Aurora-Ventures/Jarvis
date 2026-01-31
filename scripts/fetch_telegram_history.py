#!/usr/bin/env python3
"""
Fetch Telegram message history from @ClawdMatt_bot conversations
Extracts incomplete tasks including voice messages
"""

import os
import sys
import asyncio
import json
from datetime import datetime, timedelta
from pathlib import Path

# Add project root
sys.path.insert(0, str(Path(__file__).parent.parent))

from telegram import Bot
from telegram.error import TelegramError

# Load secrets
SECRETS_FILE = Path(__file__).parent.parent / "secrets" / "keys.json"
with open(SECRETS_FILE) as f:
    secrets = json.load(f)

BOT_TOKEN = secrets["telegram"]["bot_token"]
ADMIN_USER_ID = 8527130908  # From config

async def fetch_messages():
    """Fetch recent messages from bot conversations"""
    bot = Bot(token=BOT_TOKEN)

    print("=" * 80)
    print("TELEGRAM MESSAGE HISTORY AUDIT")
    print("=" * 80)
    print(f"Bot: @ClawdMatt_bot")
    print(f"Admin User ID: {ADMIN_USER_ID}")
    print(f"Date Range: Last 5 days")
    print("=" * 80 + "\n")

    try:
        # Get bot info
        me = await bot.get_me()
        print(f"✓ Connected as: @{me.username}")

        # Get recent updates (last 100)
        print("\n📥 Fetching recent updates...")
        updates = await bot.get_updates(limit=100)

        print(f"✓ Found {len(updates)} recent updates\n")

        # Filter for messages from admin in last 5 days
        five_days_ago = datetime.now() - timedelta(days=5)
        messages = []
        voice_messages = []

        for update in updates:
            if update.message:
                msg = update.message
                if msg.from_user.id == ADMIN_USER_ID:
                    if msg.date >= five_days_ago:
                        messages.append({
                            'date': msg.date.isoformat(),
                            'text': msg.text or msg.caption or '[No text]',
                            'type': 'voice' if msg.voice else 'text',
                            'message_id': msg.message_id,
                            'chat_id': msg.chat_id
                        })

                        if msg.voice:
                            voice_messages.append({
                                'date': msg.date.isoformat(),
                                'file_id': msg.voice.file_id,
                                'duration': msg.voice.duration,
                                'message_id': msg.message_id
                            })

        print(f"📊 Summary:")
        print(f"  Total messages from admin (last 5 days): {len(messages)}")
        print(f"  Voice messages: {len(voice_messages)}")
        print("\n" + "=" * 80)

        # Display messages
        print("\n📝 RECENT MESSAGES:")
        print("=" * 80)
        for i, msg in enumerate(sorted(messages, key=lambda x: x['date']), 1):
            print(f"\n[{i}] {msg['date']}")
            print(f"Type: {msg['type']}")
            print(f"Message: {msg['text'][:200]}")
            if msg['type'] == 'voice':
                print("⚠️  VOICE MESSAGE - Needs transcription")
            print("-" * 80)

        # Save to file
        output_file = Path(__file__).parent.parent / "docs" / f"telegram_audit_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(output_file, 'w') as f:
            json.dump({
                'bot_username': me.username,
                'admin_user_id': ADMIN_USER_ID,
                'audit_date': datetime.now().isoformat(),
                'messages': messages,
                'voice_messages': voice_messages
            }, f, indent=2)

        print(f"\n✓ Audit saved to: {output_file}")

        # Extract tasks
        print("\n" + "=" * 80)
        print("🎯 TASK EXTRACTION:")
        print("=" * 80)

        task_keywords = ['todo', 'task', 'fix', 'implement', 'add', 'create', 'update',
                        'deploy', 'check', 'test', 'voice', 'translation', 'translate',
                        'incomplete', 'pending', 'broken', 'error', 'issue']

        potential_tasks = []
        for msg in messages:
            text_lower = msg['text'].lower()
            if any(keyword in text_lower for keyword in task_keywords):
                potential_tasks.append(msg)

        print(f"\nFound {len(potential_tasks)} messages with task-related keywords:\n")
        for i, task in enumerate(potential_tasks, 1):
            print(f"[{i}] {task['date']}")
            print(f"    {task['text'][:150]}")
            print()

        print("=" * 80)
        print(f"\n✓ Voice messages to transcribe: {len(voice_messages)}")
        if voice_messages:
            print("\n⚠️  ACTION REQUIRED: Voice messages need manual transcription")
            print("   Voice message transcription requires downloading audio files")
            print("   and processing through speech-to-text API\n")

    except TelegramError as e:
        print(f"❌ Telegram API Error: {e}")
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(fetch_messages())
