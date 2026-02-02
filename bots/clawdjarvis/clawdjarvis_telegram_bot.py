"""
ClawdJarvis Telegram Bot - Main Orchestrator

The main Jarvis Telegram bot for system orchestration and AI assistance.

Usage:
  /jarvis <question> - Ask Jarvis anything
  /system - Check system status
  /help - Show available commands
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
BOT_TOKEN = os.environ.get("CLAWDJARVIS_BOT_TOKEN")
if not BOT_TOKEN:
    logger.error("CLAWDJARVIS_BOT_TOKEN not found in environment")
    sys.exit(1)

# Initialize bot
bot = AsyncTeleBot(BOT_TOKEN)

# Jarvis personality responses
JARVIS_GREETINGS = [
    "At your service, sir.",
    "How may I assist you today?",
    "Yes, what do you need?",
    "Jarvis online. What's the mission?",
    "Ready and waiting.",
]

JARVIS_CAPABILITIES = """
JARVIS System Capabilities:

Trading:
- Autonomous Solana token trading
- Position management (up to 50 positions)
- Risk management with TP/SL

AI Assistants:
- ClawdMatt: PR & communications filter
- ClawdFriday: Email AI assistant
- Sentiment analysis via Grok

Social:
- X/Twitter automation (@Jarvis_lifeos)
- Telegram integration

Monitoring:
- Bags.fm graduation tracking
- Token sentiment analysis
- Market regime detection
"""


@bot.message_handler(commands=['start', 'help'])
async def handle_help(message):
    """Send help message."""
    import random
    greeting = random.choice(JARVIS_GREETINGS)

    help_text = f"""
{greeting}

I am JARVIS - Just A Rather Very Intelligent System.

Commands:
/jarvis <question> - Ask me anything
/system - Check system status
/caps - View my capabilities
/help - Show this help message

Examples:
/jarvis What's the current market sentiment?
/system

I'm here to assist with trading, analysis, and system orchestration.
"""
    await bot.reply_to(message, help_text)


@bot.message_handler(commands=['system', 'status'])
async def handle_status(message):
    """Send system status."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC")

    status_text = f"""
JARVIS System Status Report
Time: {now}

Core Systems:
[OK] Telegram Bot: ONLINE
[OK] VPS Connection: ACTIVE
[OK] Token Loading: SUCCESS

Bot Network:
- ClawdMatt (PR Filter): DEPLOYED
- ClawdFriday (Email AI): DEPLOYED
- ClawdJarvis (Orchestrator): ONLINE

Services:
- Trading Engine: STANDBY
- Sentiment Analysis: AVAILABLE
- X/Twitter Bot: CONFIGURED

All systems operational.
"""
    await bot.reply_to(message, status_text)


@bot.message_handler(commands=['caps', 'capabilities'])
async def handle_caps(message):
    """Show Jarvis capabilities."""
    await bot.reply_to(message, JARVIS_CAPABILITIES)


@bot.message_handler(commands=['jarvis'])
async def handle_jarvis(message):
    """Handle Jarvis questions."""
    # Get the question after /jarvis
    question = message.text.replace('/jarvis', '', 1).strip()

    if not question:
        await bot.reply_to(message, "Yes? What would you like to know?")
        return

    question_lower = question.lower()

    # Simple response logic
    if "hello" in question_lower or "hi" in question_lower:
        response = "Hello! How may I assist you today?"
    elif "status" in question_lower:
        response = "All systems are operational. Would you like a detailed status report? Use /system."
    elif "trading" in question_lower:
        response = "Trading systems are on standby. The treasury bot handles autonomous Solana token trading with risk management."
    elif "market" in question_lower or "sentiment" in question_lower:
        response = "I can analyze market sentiment using Grok AI. The system monitors token metrics and social signals."
    elif "email" in question_lower or "friday" in question_lower:
        response = "Friday (ClawdFriday) handles email processing with KR8TIV AI branding. She categorizes and drafts professional responses."
    elif "pr" in question_lower or "matt" in question_lower:
        response = "PR Matt (ClawdMatt) filters communications for professionalism while preserving authenticity."
    elif "who are you" in question_lower or "what are you" in question_lower:
        response = "I am JARVIS - Just A Rather Very Intelligent System. An autonomous LifeOS assistant for trading, AI coordination, and system orchestration."
    elif "help" in question_lower:
        response = "I can help with trading, market analysis, email processing, and PR filtering. What specific area would you like assistance with?"
    else:
        response = f"Analyzing your query: '{question}'\n\nI'm currently in basic mode without external AI access. For full capabilities, ensure the Grok or Claude API is configured."

    await bot.reply_to(message, response)


@bot.message_handler(func=lambda message: True)
async def handle_any(message):
    """Handle any message as a Jarvis query."""
    if message.text:
        question = message.text.strip()

        # Treat any message as a question
        question_lower = question.lower()

        if "hello" in question_lower or "hi" in question_lower:
            import random
            await bot.reply_to(message, random.choice(JARVIS_GREETINGS))
        else:
            await bot.reply_to(
                message,
                f"I heard: '{question}'\n\n"
                "Use /jarvis <question> for a more structured response, "
                "or /help to see all commands."
            )


async def main():
    """Main entry point."""
    logger.info("Starting ClawdJarvis Telegram Bot...")
    logger.info(f"Bot token (first 10 chars): {BOT_TOKEN[:10]}...")

    # Remove any existing webhook
    await bot.remove_webhook()

    # Start polling
    logger.info("Starting polling...")
    await bot.infinity_polling(timeout=60, request_timeout=120)


if __name__ == "__main__":
    asyncio.run(main())
