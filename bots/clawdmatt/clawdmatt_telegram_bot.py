"""
ClawdMatt Telegram Bot - Marketing Communications Filter

A Telegram bot interface for the PR Matt content review service.
Reviews messages for brand alignment before publishing.

Usage:
  /review <message> - Review a message for PR compliance
  /help - Show available commands
  /status - Check bot status
"""

import os
import sys
import logging
import asyncio
import telebot
from telebot.async_telebot import AsyncTeleBot
from pathlib import Path

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment from tokens.env
def load_tokens():
    tokens_path = Path(__file__).parent.parent.parent / "tokens.env"
    if not tokens_path.exists():
        tokens_path = Path("/root/clawdbots/tokens.env")
    if tokens_path.exists():
        for line in tokens_path.read_text().splitlines():
            if line.strip() and not line.startswith('#') and '=' in line:
                k, v = line.split('=', 1)
                os.environ.setdefault(k.strip(), v.strip())

load_tokens()

# Get token
BOT_TOKEN = os.environ.get("CLAWDMATT_BOT_TOKEN")
if not BOT_TOKEN:
    logger.error("CLAWDMATT_BOT_TOKEN not found in environment")
    sys.exit(1)

# Initialize bot
bot = AsyncTeleBot(BOT_TOKEN)

# Blocked words list
HARD_BLOCKED_WORDS = [
    "fucking", "fuck", "shit", "damn", "hell", "bitch",
    "ass", "crap", "piss", "cock", "dick", "pussy"
]

# Warning patterns
WARNING_PATTERNS = [
    "we're the best", "number one", "guaranteed",
    "100%", "to the moon", "wen moon", "lambo"
]


def review_message(text: str) -> dict:
    """Review a message for PR compliance."""
    concerns = []
    decision = "APPROVED"

    text_lower = text.lower()

    # Check for blocked words
    for word in HARD_BLOCKED_WORDS:
        if word in text_lower:
            concerns.append(f"Blocked word: '{word}'")
            decision = "BLOCKED"

    # Check for warning patterns
    for pattern in WARNING_PATTERNS:
        if pattern in text_lower:
            concerns.append(f"Warning pattern: '{pattern}'")
            if decision != "BLOCKED":
                decision = "NEEDS_REVISION"

    # Build response
    if decision == "APPROVED":
        return {
            "decision": "APPROVED",
            "message": "Message looks good for public posting.",
            "concerns": []
        }
    elif decision == "BLOCKED":
        return {
            "decision": "BLOCKED",
            "message": "Message contains inappropriate content.",
            "concerns": concerns
        }
    else:
        return {
            "decision": "NEEDS_REVISION",
            "message": "Message may need revision before posting.",
            "concerns": concerns
        }


@bot.message_handler(commands=['start', 'help'])
async def handle_help(message):
    """Send help message."""
    help_text = """
Welcome to ClawdMatt - PR Filter Bot

Commands:
/review <message> - Review a message for PR compliance
/status - Check bot status
/help - Show this help message

Example:
/review Check out our amazing new feature!

I'll analyze your message and let you know if it's safe to post publicly.
"""
    await bot.reply_to(message, help_text)


@bot.message_handler(commands=['status'])
async def handle_status(message):
    """Send status message."""
    status_text = """
ClawdMatt Status: ONLINE

Bot: @ClawdMatt_bot
Purpose: Marketing Communications Filter
Mode: Active

I review messages before public posting to maintain professionalism while preserving authenticity.
"""
    await bot.reply_to(message, status_text)


@bot.message_handler(commands=['review'])
async def handle_review(message):
    """Review a message for PR compliance."""
    # Get the message text after /review
    text = message.text.replace('/review', '', 1).strip()

    if not text:
        await bot.reply_to(message, "Usage: /review <your message to review>")
        return

    # Review the message
    result = review_message(text)

    # Format response
    if result["decision"] == "APPROVED":
        emoji = "OK"
        response = f"[{emoji}] {result['decision']}\n\n{result['message']}"
    elif result["decision"] == "BLOCKED":
        emoji = "X"
        response = f"[{emoji}] {result['decision']}\n\n{result['message']}\n\nConcerns:\n"
        for concern in result["concerns"]:
            response += f"  - {concern}\n"
    else:
        emoji = "!"
        response = f"[{emoji}] {result['decision']}\n\n{result['message']}\n\nConcerns:\n"
        for concern in result["concerns"]:
            response += f"  - {concern}\n"

    await bot.reply_to(message, response)


@bot.message_handler(func=lambda message: True)
async def handle_any(message):
    """Handle any message as a review request."""
    if message.text:
        # Automatically review any message
        result = review_message(message.text)

        # Format response
        if result["decision"] == "APPROVED":
            await bot.reply_to(message, f"[OK] APPROVED - Safe to post!")
        elif result["decision"] == "BLOCKED":
            concerns = "\n".join([f"  - {c}" for c in result["concerns"]])
            await bot.reply_to(message, f"[X] BLOCKED\n\nConcerns:\n{concerns}")
        else:
            concerns = "\n".join([f"  - {c}" for c in result["concerns"]])
            await bot.reply_to(message, f"[!] NEEDS_REVISION\n\nConcerns:\n{concerns}")


async def main():
    """Main entry point."""
    logger.info("Starting ClawdMatt Telegram Bot...")
    logger.info(f"Bot token (first 10 chars): {BOT_TOKEN[:10]}...")

    # Remove any existing webhook
    await bot.remove_webhook()

    # Start polling
    logger.info("Starting polling...")
    await bot.infinity_polling(timeout=60, request_timeout=120)


if __name__ == "__main__":
    asyncio.run(main())
