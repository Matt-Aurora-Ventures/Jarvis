#!/usr/bin/env python3
"""
Send a command to Telegram bot to extract treasury wallet from VPS.
"""

import asyncio
import json
from pathlib import Path
from telegram import Bot

# Load decrypted API keys
with open("temp_decrypted.json") as f:
    keys = json.load(f)

# Get bot token and your Telegram chat ID
BOT_TOKEN = keys["telegram"]["bot_token"]
# You need your chat ID - get it from @userinfobot or bot logs

async def send_command(command: str):
    """Send a command to the Telegram bot."""
    bot = Bot(token=BOT_TOKEN)

    # Get bot info
    me = await bot.get_me()
    print(f"Bot: @{me.username}")
    print(f"Bot ID: {me.id}")

    # Get updates to find your chat ID
    updates = await bot.get_updates()
    if updates:
        print("\nRecent chats:")
        for update in updates[-5:]:
            if update.message:
                chat_id = update.message.chat.id
                username = update.message.from_user.username or update.message.from_user.first_name
                text = update.message.text[:50] if update.message.text else "[no text]"
                print(f"  Chat ID: {chat_id}, User: {username}, Last msg: {text}")

    # If you know your chat ID, uncomment and use:
    # YOUR_CHAT_ID = 123456789  # Replace with your actual chat ID
    # await bot.send_message(
    #     chat_id=YOUR_CHAT_ID,
    #     text=command
    # )
    # print(f"\nSent command: {command}")

if __name__ == "__main__":
    # Command to have bot read and send treasury wallet
    command = "/admin_read_file /home/jarvis/Jarvis/bots/treasury/.wallets/registry.json"

    asyncio.run(send_command(command))
