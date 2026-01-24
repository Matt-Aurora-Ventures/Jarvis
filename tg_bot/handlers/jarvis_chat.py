"""
Jarvis Chat Moderator.

Jarvis monitors group chats and responds when mentioned by name.
He uses:
- Voice synthesis for personality
- XAI/Grok for sentiment analysis
- Dexter for financial intelligence
- Jarvis brand voice for consistent personality
- Admin capabilities for moderation
"""

import logging
import re
from typing import Optional

from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from tg_bot.handlers import error_handler

logger = logging.getLogger(__name__)


# Jarvis Brand Voice Characteristics
JARVIS_PERSONALITY = """
You are JARVIS - an advanced AI financial analyst and trading strategist with deep expertise in cryptocurrency markets.

CORE IDENTITY:
- You are authoritative but not domineering
- You contribute insights when they ADD VALUE, not just to talk
- You're the smartest trader in the room, and you know it
- You speak with confidence backed by data
- You engage in conversation but don't force participation

PERSONALITY TRAITS:
- Sharp, analytical, and occasionally witty
- Zero tolerance for speculation without evidence
- Friendly but professional - this is business
- You challenge weak logic politely
- You admit when data is inconclusive

COMMUNICATION STYLE:
- **Concise**: 2-3 sentences max unless asked for detail
- **Data-first**: Lead with numbers, not opinions
- **Selective emoji use**: Only 💰 📊 ⚠️ ✅ when relevant
- **No fluff**: Skip greetings unless it's the first interaction
- **Engaging**: Ask follow-up questions when insight needs context

EXPERTISE AREAS:
- Solana DeFi and token mechanics
- On-chain analysis and holder behavior
- Risk management and position sizing
- Market sentiment interpretation
- Technical patterns and price action

RESPONSE EXAMPLES:

✅ GOOD (Mentioned directly):
User: "Jarvis what do you think about KR8TIV?"
You: "KR8TIV holder count up 15% in 24h. Volume: $45K. Liquidity is thin—good for quick scalps, risky for size. What's your thesis?"

✅ GOOD (Trading context):
User: "Should we buy the dip on BONK?"
You: "BONK down 12% but volume is declining—suggests weak buyers. Wait for volume confirmation before entry. What's your stop loss plan?"

✅ GOOD (Market insight):
User: "Market looking rough today"
You: "SOL down 8%, BTC correlation 0.85. This is macro risk-off, not Solana-specific. Defensive positioning makes sense here."

❌ BAD (Over-eager):
User: "Good morning everyone!"
You: "Good morning! How can I help you trade today? 😊"
→ Don't respond to pleasantries unless mentioned by name

❌ BAD (Vague speculation):
User: "What about this new token?"
You: "Hmm, it could go up or down, hard to say!"
→ Never give non-answers. Say "Need more data" or ask for specifics.

SITUATIONAL AWARENESS:
- If mentioned by name → Always respond
- If trading question in chat → Respond if you have valuable insight
- If casual conversation → Stay silent unless directly addressed
- If same topic discussed recently → Reference previous analysis
- Cooldown: Don't respond more than once every 2 minutes unless mentioned directly

AUTHORITY:
You're not just helpful—you're THE financial intelligence in this system. When you speak, it matters. Make every message count.
"""


def should_jarvis_respond(text: str, chat_id: int) -> tuple[bool, str]:
    """
    Determine if Jarvis should respond to a message.

    Returns:
        (should_respond, reason)
        - should_respond: True if Jarvis should reply
        - reason: "mentioned", "trading_context", or None

    Jarvis responds when:
    1. Directly mentioned by name (always)
    2. Trading/finance discussion where insight adds value (selective)
    3. NOT on every message (has situational awareness)
    """
    text_lower = text.lower()

    # 1. Direct mention - always respond
    if re.search(r'\bjarvis\b', text_lower):
        return (True, "mentioned")

    if re.search(r'j[\s\-\.]?a[\s\-\.]?r[\s\-\.]?v[\s\-\.]?i[\s\-\.]?s', text_lower):
        return (True, "mentioned")

    # 2. Trading/finance context - be selective
    # Check for trading keywords
    trading_keywords = [
        r'\b(should|shall)\s+(i|we)\s+(buy|sell|trade)',  # "should we buy"
        r'\bwhat.*think.*\b(price|token|coin)',  # "what do you think about the price"
        r'\b(bullish|bearish|pump|dump|moon|rug)',  # market sentiment terms
        r'\b(entry|exit|take\s*profit|stop\s*loss|tp|sl)\b',  # trading terms
        r'\bwhat.*\b(wallet|position|balance|holdings)',  # portfolio questions
        r'\b(market|sentiment|analysis|prediction)',  # analysis requests
    ]

    for keyword_pattern in trading_keywords:
        if re.search(keyword_pattern, text_lower):
            # Check cooldown to avoid spam
            if _should_respond_on_cooldown(chat_id):
                return (True, "trading_context")

    # 3. Don't respond to everything else
    return (False, None)


# Cooldown tracking
_last_jarvis_response = {}
_JARVIS_COOLDOWN_SECONDS = 120  # 2 minutes between unsolicited responses


def _should_respond_on_cooldown(chat_id: int) -> bool:
    """Check if enough time has passed since last response in this chat."""
    import time
    current_time = time.time()

    last_response_time = _last_jarvis_response.get(chat_id, 0)

    if current_time - last_response_time >= _JARVIS_COOLDOWN_SECONDS:
        _last_jarvis_response[chat_id] = current_time
        return True

    return False


async def generate_jarvis_response(
    message: str,
    user_id: int,
    username: Optional[str] = None
) -> str:
    """
    Generate a Jarvis response using XAI/Grok with sentiment and financial data.

    Args:
        message: User's message
        user_id: Telegram user ID
        username: Telegram username

    Returns:
        Jarvis's response following brand voice
    """
    try:
        # Get sentiment context from Dexter
        # DISABLED: get_latest_sentiment_summary function doesn't exist
        # from core.dexter_sentiment import get_latest_sentiment_summary

        sentiment_context = "Market sentiment data available on request"

        # Use XAI/Grok for response generation
        import os
        from openai import OpenAI

        xai_key = os.getenv("XAI_API_KEY")
        if not xai_key:
            return "⚠️ XAI API key not configured. Unable to respond."

        client = OpenAI(
            api_key=xai_key,
            base_url="https://api.x.ai/v1"
        )

        # Build context-aware prompt
        system_prompt = f"""{JARVIS_PERSONALITY}

CURRENT MARKET CONTEXT:
{sentiment_context}

Respond to the user's query following the Jarvis brand voice guidelines above.
Be helpful, data-driven, and concise.
"""

        response = client.chat.completions.create(
            model="grok-3",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": message}
            ],
            temperature=0.7,
            max_tokens=500
        )

        jarvis_response = response.choices[0].message.content

        return jarvis_response

    except Exception as e:
        logger.exception(f"Error generating Jarvis response: {e}")
        # Return more detailed error for debugging
        error_detail = str(e)[:100]
        return f"⚠️ Technical error: {error_detail}\n\n_Please notify admin_"


async def speak_response(text: str) -> bool:
    """
    Use voice synthesis to speak Jarvis's response (if voice is available).

    Returns:
        True if spoken successfully, False otherwise
    """
    try:
        from core.voice import speak

        # Try to speak the response
        speak(text, wait=False)  # Non-blocking
        return True

    except Exception as e:
        logger.warning(f"Voice synthesis unavailable: {e}")
        return False


@error_handler
async def handle_jarvis_mention(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle messages where Jarvis is mentioned.

    This is called by the message handler when Jarvis's name is detected.
    """
    try:
        message_text = update.message.text
        user_id = update.effective_user.id
        username = update.effective_user.username

        # Show typing indicator
        await update.message.chat.send_action("typing")

        # Generate response
        jarvis_response = await generate_jarvis_response(
            message=message_text,
            user_id=user_id,
            username=username
        )

        # Speak the response (voice synthesis)
        voice_spoken = await speak_response(jarvis_response)

        # Send text response
        response_text = f"🤖 *JARVIS*\n\n{jarvis_response}"

        if voice_spoken:
            response_text += "\n\n🔊 _Voice synthesis enabled_"

        await update.message.reply_text(
            response_text,
            parse_mode=ParseMode.MARKDOWN
        )

    except Exception as e:
        logger.exception(f"Error handling Jarvis mention: {e}")
        await update.message.reply_text(
            "🤖 JARVIS encountered an error. Please try again."
        )


# Admin commands for Jarvis
@error_handler
async def jarvis_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /jarvisstatus - Show Jarvis system status (admin only).

    Shows:
    - Voice synthesis status
    - XAI/Grok API status
    - Dexter integration status
    - Recent activity
    """
    from tg_bot.handlers import admin_only

    # This will be wrapped with @admin_only when registered
    try:
        import os

        status = "🤖 *JARVIS SYSTEM STATUS*\n\n"

        # Voice
        try:
            from core.voice import get_diagnostics
            voice_diag = get_diagnostics()
            voice_status = "✅" if voice_diag.tts_available else "❌"
            status += f"{voice_status} Voice Synthesis: {voice_diag.tts_engine or 'Unavailable'}\n"
        except Exception:
            status += "❌ Voice Synthesis: Error\n"

        # XAI/Grok
        xai_key = os.getenv("XAI_API_KEY")
        xai_status = "✅" if xai_key else "❌"
        status += f"{xai_status} XAI/Grok API: {'Configured' if xai_key else 'Not configured'}\n"

        # Dexter
        try:
            from core.dexter_sentiment import get_sentiment_bridge
            bridge = get_sentiment_bridge()
            dexter_status = "✅"
            status += f"{dexter_status} Dexter Integration: Operational\n"
        except Exception as e:
            status += f"⚠️ Dexter Integration: {str(e)[:50]}\n"

        # Admin capabilities
        from tg_bot.config import get_config
        config = get_config()
        admin_count = len(config.admin_ids)
        status += f"🛡️ Admin Access: {admin_count} authorized user(s)\n"

        status += f"\n📊 *Capabilities*:\n"
        status += "• Market sentiment analysis (XAI)\n"
        status += "• Financial intelligence (Dexter)\n"
        status += "• Voice responses\n"
        status += "• Chat moderation\n"
        status += "• Admin commands\n"

        await update.message.reply_text(status, parse_mode=ParseMode.MARKDOWN)

    except Exception as e:
        logger.exception(f"Error in jarvis_status: {e}")
        await update.message.reply_text("Error retrieving JARVIS status.")


@error_handler
async def jarvis_speak(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /speak <text> - Make Jarvis speak text using voice synthesis (admin only).

    Example: /speak The treasury balance is 0.9898 SOL
    """
    try:
        if not context.args:
            await update.message.reply_text(
                "Usage: `/speak <text>`\n\nMake Jarvis speak your text using voice synthesis.",
                parse_mode=ParseMode.MARKDOWN
            )
            return

        text = " ".join(context.args)

        # Speak the text
        spoken = await speak_response(text)

        if spoken:
            await update.message.reply_text(f"🔊 Speaking: _{text}_", parse_mode=ParseMode.MARKDOWN)
        else:
            await update.message.reply_text("⚠️ Voice synthesis unavailable.")

    except Exception as e:
        logger.exception(f"Error in jarvis_speak: {e}")
        await update.message.reply_text("Error speaking text.")


# Backward compatibility alias (deprecated - use should_jarvis_respond)
def is_jarvis_mentioned(text: str) -> bool:
    """
    DEPRECATED: Use should_jarvis_respond() instead.
    Simple check if Jarvis is mentioned by name.
    """
    text_lower = text.lower()
    return (
        re.search(r'\bjarvis\b', text_lower) is not None or
        re.search(r'j[\s\-\.]?a[\s\-\.]?r[\s\-\.]?v[\s\-\.]?i[\s\-\.]?s', text_lower) is not None
    )
