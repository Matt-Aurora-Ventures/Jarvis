#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Telegram 5-Day History Audit
Systematically reviews last 5 days of messages from specified groups/chats
Extracts tasks, bugs, requests, and action items

Per user directive: Review these chats:
1. KR8TIV space AI group
2. JarvisLifeOS group
3. Claude Matt (C-L-A-W-D Matt) private chats
"""

import os
import sys
import asyncio

# Fix Windows Unicode issues
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Any

sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from telegram import Bot, Update
    from telegram.error import TelegramError
    from dotenv import load_dotenv
except ImportError:
    print("ERROR: Required modules not found.")
    print("Install: pip install python-telegram-bot python-dotenv")
    sys.exit(1)

# Load environment - try multiple locations
env_paths = [
    Path(__file__).parent.parent / "tg_bot" / ".env",
    Path(__file__).parent.parent / "lifeos" / "config" / ".env",
    Path(__file__).parent.parent / ".env",
]

for env_path in env_paths:
    if env_path.exists():
        load_dotenv(env_path)
        break

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
if not BOT_TOKEN:
    print("ERROR: TELEGRAM_BOT_TOKEN not set!")
    sys.exit(1)

# Target chats to audit (will be identified by name)
TARGET_CHATS = [
    "KR8TIV space AI",
    "JarvisLifeOS",
    "Claude Matt",
    "ClawdMatt",  # Alternative spelling
]

# Date range
DAYS_BACK = 5
cutoff_date = datetime.now() - timedelta(days=DAYS_BACK)

# Task keywords to detect
TASK_KEYWORDS = [
    "todo", "task", "fix", "bug", "issue", "problem", "error",
    "need to", "should", "must", "have to", "implement", "add",
    "update", "change", "improve", "optimize", "refactor",
    "deploy", "test", "verify", "check", "review", "audit",
    "investigate", "debug", "resolve", "handle", "create",
    "research", "analyze", "monitor", "track", "document"
]

async def fetch_chat_list(bot: Bot) -> List[Dict]:
    """Get list of all chats bot is in"""
    print("\n🔍 Scanning for accessible chats...")

    chats = []

    # Try to get recent updates to find chat IDs
    try:
        updates = await bot.get_updates(limit=100)
        for update in updates:
            if update.message:
                chat = update.message.chat
                chat_info = {
                    "id": chat.id,
                    "title": chat.title or chat.first_name or "Unknown",
                    "type": chat.type,
                    "username": chat.username
                }

                # Deduplicate
                if not any(c["id"] == chat_info["id"] for c in chats):
                    chats.append(chat_info)

    except TelegramError as e:
        print(f"⚠️  Error fetching updates: {e}")

    return chats


async def fetch_chat_history(bot: Bot, chat_id: int, chat_name: str) -> List[Dict]:
    """
    Fetch message history from a chat.
    Note: Telegram Bot API has limitations - can only see messages the bot can access.
    """
    print(f"\n📥 Fetching history from: {chat_name}")

    messages = []

    try:
        # Get recent messages via updates
        # Note: This only works for messages where bot was mentioned or is admin
        updates = await bot.get_updates(limit=100)

        for update in updates:
            if not update.message:
                continue

            msg = update.message
            if msg.chat.id != chat_id:
                continue

            # Check if message is within date range
            if msg.date < cutoff_date:
                continue

            # Extract message data
            message_data = {
                "id": msg.message_id,
                "date": msg.date.isoformat(),
                "from": msg.from_user.username if msg.from_user else "Unknown",
                "text": msg.text or msg.caption or "[Media]",
                "has_media": bool(msg.photo or msg.video or msg.document),
            }

            messages.append(message_data)

    except TelegramError as e:
        print(f"⚠️  Error fetching from {chat_name}: {e}")

    return messages


def extract_tasks(messages: List[Dict]) -> List[Dict]:
    """Extract potential tasks from messages"""
    tasks = []

    for msg in messages:
        text = msg.get("text", "").lower()

        # Check for task keywords
        has_keyword = any(keyword in text for keyword in TASK_KEYWORDS)

        if has_keyword:
            tasks.append({
                "date": msg["date"],
                "from": msg["from"],
                "text": msg["text"],
                "message_id": msg["id"],
            })

    return tasks


async def main():
    """Main audit function"""
    bot = Bot(token=BOT_TOKEN)

    print("=" * 80)
    print("TELEGRAM 5-DAY HISTORY AUDIT")
    print("=" * 80)
    print(f"Date Range: {cutoff_date.strftime('%Y-%m-%d')} to {datetime.now().strftime('%Y-%m-%d')}")
    print(f"Target Chats: {', '.join(TARGET_CHATS)}")
    print("=" * 80)

    try:
        # Get bot info
        me = await bot.get_me()
        print(f"\n✓ Connected as: @{me.username}\n")

        # Scan for chats
        all_chats = await fetch_chat_list(bot)

        if not all_chats:
            print("\n⚠️  No chats found!")
            print("\nREASON: Telegram Bot API limitations:")
            print("  - Bots can only see messages where they're mentioned or are admin")
            print("  - Cannot access chat history before bot was added")
            print("  - Cannot access private groups unless bot is admin")
            print("\nWORKAROUND:")
            print("  1. Make bot admin in target groups")
            print("  2. Have someone mention bot in recent messages")
            print("  3. Or manually review chat history")
            return

        print(f"\n📊 Found {len(all_chats)} accessible chats:")
        for chat in all_chats:
            print(f"  - {chat['title']} (ID: {chat['id']}, Type: {chat['type']})")

        # Find target chats
        target_chats_found = []
        for chat in all_chats:
            chat_name = chat["title"].lower()
            if any(target.lower() in chat_name for target in TARGET_CHATS):
                target_chats_found.append(chat)

        if not target_chats_found:
            print(f"\n⚠️  None of the target chats found: {', '.join(TARGET_CHATS)}")
            print("\nMake sure:")
            print("  1. Bot is member/admin of these groups")
            print("  2. Bot has been active in these groups recently")
            print("  3. Chat names are spelled correctly")
            return

        # Audit each target chat
        all_tasks = {}

        for chat in target_chats_found:
            messages = await fetch_chat_history(bot, chat["id"], chat["title"])

            if not messages:
                print(f"  ⚠️  No messages found (bot may not have access)")
                continue

            print(f"  ✓ Found {len(messages)} messages")

            # Extract tasks
            tasks = extract_tasks(messages)
            all_tasks[chat["title"]] = tasks

            if tasks:
                print(f"  ✓ Extracted {len(tasks)} potential tasks")

        # Generate report
        print("\n" + "=" * 80)
        print("AUDIT REPORT")
        print("=" * 80)

        total_tasks = sum(len(tasks) for tasks in all_tasks.values())
        print(f"\nTotal Tasks Found: {total_tasks}\n")

        output_file = Path(__file__).parent.parent / "docs" / "TELEGRAM_AUDIT_RESULTS_JAN_31.md"

        with open(output_file, "w", encoding="utf-8") as f:
            f.write(f"# Telegram 5-Day Audit Results\\n")
            f.write(f"**Date Range:** {cutoff_date.strftime('%Y-%m-%d')} to {datetime.now().strftime('%Y-%m-%d')}\\n")
            f.write(f"**Generated:** {datetime.now().isoformat()}\\n\\n")
            f.write("---\\n\\n")

            for chat_name, tasks in all_tasks.items():
                f.write(f"## {chat_name} ({len(tasks)} tasks)\\n\\n")

                if not tasks:
                    f.write("No tasks found.\\n\\n")
                    continue

                for i, task in enumerate(tasks, 1):
                    f.write(f"### Task {i}\\n")
                    f.write(f"- **Date:** {task['date']}\\n")
                    f.write(f"- **From:** {task['from']}\\n")
                    f.write(f"- **Message ID:** {task['message_id']}\\n")
                    f.write(f"- **Text:**\\n```\\n{task['text']}\\n```\\n\\n")

        print(f"✓ Results saved to: {output_file}")

    except TelegramError as e:
        print(f"\\n❌ Telegram API Error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\\n❌ Unexpected Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
