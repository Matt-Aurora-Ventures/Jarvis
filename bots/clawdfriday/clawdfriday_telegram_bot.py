"""
ClawdFriday Telegram Bot - Email AI Assistant

A Telegram bot interface for the Friday email AI service.
Helps process and respond to emails with KR8TIV AI branding.

Usage:
  /email <subject> | <body> - Analyze an email
  /draft <topic> - Draft an email response
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
from datetime import datetime

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
BOT_TOKEN = os.environ.get("CLAWDFRIDAY_BOT_TOKEN")
if not BOT_TOKEN:
    logger.error("CLAWDFRIDAY_BOT_TOKEN not found in environment")
    sys.exit(1)

# Initialize bot
bot = AsyncTeleBot(BOT_TOKEN)

# Email categories
EMAIL_CATEGORIES = [
    ("business_inquiry", ["business", "opportunity", "proposal", "interested"]),
    ("technical_support", ["help", "issue", "problem", "error", "support"]),
    ("partnership", ["partner", "collaboration", "together", "joint"]),
    ("investor", ["invest", "funding", "raise", "capital"]),
    ("spam", ["unsubscribe", "click here", "limited time", "act now"]),
    ("urgent", ["urgent", "asap", "immediately", "critical"]),
]


def categorize_email(subject: str, body: str) -> tuple:
    """Categorize an email based on content."""
    combined = f"{subject} {body}".lower()

    for category, keywords in EMAIL_CATEGORIES:
        for keyword in keywords:
            if keyword in combined:
                return category, 0.8

    return "general", 0.5


def generate_draft_response(topic: str, category: str = "general") -> str:
    """Generate a draft email response."""

    greetings = [
        "Thank you for reaching out to KR8TIV AI.",
        "I appreciate you taking the time to contact us.",
        "Thank you for your interest in KR8TIV AI.",
    ]

    closings = [
        "Best regards,\nFriday\nKR8TIV AI Assistant",
        "Looking forward to hearing from you,\nFriday\nKR8TIV AI",
        "Warm regards,\nFriday\nOn behalf of KR8TIV AI",
    ]

    # Category-specific templates
    templates = {
        "business_inquiry": """
{greeting}

We're excited to hear about your interest in working with us. KR8TIV AI
specializes in autonomous AI systems and blockchain integration.

I'd be happy to schedule a call to discuss how we can help with your specific needs.

What times work best for you this week?

{closing}
""",
        "technical_support": """
{greeting}

I understand you're experiencing an issue, and I'm here to help.

To better assist you, could you please provide:
1. A detailed description of the problem
2. Any error messages you've seen
3. Steps to reproduce the issue

Our team typically responds within 24 hours.

{closing}
""",
        "partnership": """
{greeting}

We're always open to exploring partnership opportunities that align with
our mission of building autonomous, intelligent systems.

Could you share more details about:
1. Your organization and its focus
2. The type of partnership you envision
3. Potential mutual benefits

We'd love to explore this further.

{closing}
""",
        "general": """
{greeting}

{topic_response}

Please let us know if you have any other questions or need further assistance.

{closing}
""",
    }

    import random
    greeting = random.choice(greetings)
    closing = random.choice(closings)

    template = templates.get(category, templates["general"])

    if category == "general":
        topic_response = f"Regarding '{topic}', I'd be happy to provide more information or connect you with the right team member."
        return template.format(
            greeting=greeting,
            topic_response=topic_response,
            closing=closing
        )

    return template.format(greeting=greeting, closing=closing)


@bot.message_handler(commands=['start', 'help'])
async def handle_help(message):
    """Send help message."""
    help_text = """
Welcome to ClawdFriday - Email AI Assistant

Commands:
/email <subject> | <body> - Analyze an email
/draft <topic> - Draft an email response
/status - Check bot status
/help - Show this help message

Examples:
/email Partnership Inquiry | We'd like to explore...
/draft business inquiry response

I'll help categorize emails and draft professional responses aligned with KR8TIV AI's brand voice.
"""
    await bot.reply_to(message, help_text)


@bot.message_handler(commands=['status'])
async def handle_status(message):
    """Send status message."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    status_text = f"""
ClawdFriday Status: ONLINE

Bot: @ClawdFriday_bot
Purpose: Email AI Assistant
Mode: Active
Time: {now}

I help process emails and generate professional responses for KR8TIV AI.
"""
    await bot.reply_to(message, status_text)


@bot.message_handler(commands=['email'])
async def handle_email(message):
    """Analyze an email."""
    # Get the text after /email
    text = message.text.replace('/email', '', 1).strip()

    if not text:
        await bot.reply_to(message, "Usage: /email <subject> | <body>")
        return

    # Split subject and body
    parts = text.split('|', 1)
    subject = parts[0].strip()
    body = parts[1].strip() if len(parts) > 1 else ""

    # Categorize
    category, confidence = categorize_email(subject, body)

    # Determine priority
    priority = "URGENT" if category == "urgent" else "NORMAL"

    response = f"""
Email Analysis:

Subject: {subject}
Category: {category.upper()}
Priority: {priority}
Confidence: {confidence*100:.0f}%

Suggested action: {"Respond within 4 hours" if priority == "URGENT" else "Respond within 24 hours"}

Use /draft {category} to generate a response template.
"""

    await bot.reply_to(message, response)


@bot.message_handler(commands=['draft'])
async def handle_draft(message):
    """Draft an email response."""
    # Get the topic after /draft
    topic = message.text.replace('/draft', '', 1).strip()

    if not topic:
        await bot.reply_to(message, "Usage: /draft <topic or category>")
        return

    # Determine category from topic
    topic_lower = topic.lower()
    category = "general"
    for cat, keywords in EMAIL_CATEGORIES:
        for keyword in keywords:
            if keyword in topic_lower:
                category = cat
                break

    # Generate draft
    draft = generate_draft_response(topic, category)

    response = f"""
Draft Response ({category.upper()}):
---
{draft}
---

Feel free to customize this template for your specific needs.
"""

    await bot.reply_to(message, response)


@bot.message_handler(func=lambda message: True)
async def handle_any(message):
    """Handle any message."""
    if message.text:
        await bot.reply_to(
            message,
            "Hi! I'm Friday, your email AI assistant.\n\n"
            "Use /help to see available commands, or:\n"
            "- /email <subject> | <body> - Analyze an email\n"
            "- /draft <topic> - Generate a response template"
        )


async def main():
    """Main entry point."""
    logger.info("Starting ClawdFriday Telegram Bot...")
    logger.info(f"Bot token (first 10 chars): {BOT_TOKEN[:10]}...")

    # Remove any existing webhook
    await bot.remove_webhook()

    # Start polling
    logger.info("Starting polling...")
    await bot.infinity_polling(timeout=60, request_timeout=120)


if __name__ == "__main__":
    asyncio.run(main())
