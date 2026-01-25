"""
/about command - Shows information about JARVIS and AI systems.

Provides attribution for Dexter AI integration and EU AI Act compliance.
"""

import logging
from telegram import Update
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)


async def about_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Show information about JARVIS AI systems.

    Includes:
    - Dexter AI attribution with GitHub link
    - EU AI Act Article 50 compliance info
    - System overview
    """
    if not update.message:
        return

    message = """*JARVIS - AI Trading Assistant*

_Built by Matt using advanced AI systems_

*AI Systems*
Primary: Dexter AI (financial analysis)
- GitHub: https://github.com/dexterslaboratory/dexter
- Powered by Grok with 1.0 sentiment weighting
- ReAct agent for trading decisions

Fallback: Grok (conversational AI)
- Used when Dexter unavailable
- General purpose responses

*EU AI Act Compliance*
Article 50 - Transparency Obligations:
All AI-generated responses are labeled with their source ([AI: Dexter] or [AI: Grok]) and include transparency disclosure as required by EU regulations.

*Capabilities*
- Real-time Solana trading via Jupiter DEX
- Token sentiment analysis
- Market trend detection
- Portfolio management
- Twitter/X integration (@Jarvis_lifeos)

Use /help for command list or /commands for detailed reference.

_AI systems attribution per EU AI Act Article 50_"""

    await update.message.reply_text(
        message,
        parse_mode="Markdown",
        disable_web_page_preview=True,
    )
    logger.info(f"About info sent to user {update.effective_user.id}")
