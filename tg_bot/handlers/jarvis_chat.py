"""
Jarvis Chat Moderator.

Jarvis monitors group chats and responds when mentioned by name.
He uses:
- Voice synthesis for personality
- XAI/Grok for sentiment analysis
- Dexter for financial intelligence
- Jarvis brand voice for consistent personality
- Admin capabilities for moderation
- Enhanced Memory System (5 game AI enhancements)
"""

import logging
import re
from typing import Optional

from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from tg_bot.handlers import error_handler

# Enhanced memory system
try:
    from core.memory.enhanced_memory import (
        get_enhanced_memory_manager,
        ImportanceLevel,
        EmotionalContext,
        QuestStatus,
        QuestPriority,
    )
    ENHANCED_MEMORY_AVAILABLE = True
except ImportError:
    ENHANCED_MEMORY_AVAILABLE = False

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
    
    Now enhanced with 5 game AI memory features:
    1. Richer World Model — time awareness, context
    2. Emotional Memory — sentiment-aware responses
    3. Quest/Goal Management — tracks user objectives
    4. Adaptive Learning — adjusts to user expertise
    5. Memory Pruning — manages memory efficiently

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
        
        # ══════════════════════════════════════════════════════════════
        # ENHANCED MEMORY INTEGRATION
        # ══════════════════════════════════════════════════════════════
        enhanced_context = ""
        suggested_tone = "professional"
        response_style = {}
        
        if ENHANCED_MEMORY_AVAILABLE:
            try:
                memory_manager = get_enhanced_memory_manager()
                user_key = str(user_id)
                
                # Store incoming message with emotional analysis
                memory_manager.add_memory(
                    user_id=user_key,
                    content=message,
                    importance=ImportanceLevel.MEDIUM,
                    source="telegram",
                    analyze_emotion=True,
                )
                
                # Get rich context for response
                context = memory_manager.get_context_for_response(user_key)
                
                # Extract useful context
                suggested_tone = context.get("suggested_tone", "professional")
                response_style = context.get("response_style", {})
                
                # Build enhanced context string
                context_parts = []
                
                # World state (time awareness)
                if context.get("world_state"):
                    context_parts.append(f"Current State: {context['world_state']}")
                    
                # User profile (adaptive learning)
                if context.get("user_profile"):
                    context_parts.append(f"User: {context['user_profile']}")
                    
                # Active quests/goals
                if context.get("quest_summary") and "No active goals" not in context.get("quest_summary", ""):
                    context_parts.append(context["quest_summary"])
                    
                # Overdue quests (important!)
                if context.get("overdue_quests"):
                    context_parts.append(f"⚠️ Overdue goals: {', '.join(context['overdue_quests'])}")
                    
                # Recent emotional context
                recent_emotions = [e for e in context.get("recent_emotions", []) if e]
                if recent_emotions:
                    last_emotion = recent_emotions[-1]
                    if last_emotion.get("primary_emotion") != "neutral":
                        context_parts.append(
                            f"User mood: {last_emotion.get('primary_emotion')} "
                            f"(intensity: {last_emotion.get('intensity', 0):.1f})"
                        )
                
                if context_parts:
                    enhanced_context = "\n".join(context_parts)
                    
            except Exception as e:
                logger.warning(f"Enhanced memory error (non-fatal): {e}")
                enhanced_context = ""

        # LLM Provider: Grok (primary) → Anthropic (fallback)
        import os
        from openai import OpenAI

        xai_key = os.getenv("XAI_API_KEY")
        anthropic_key = os.getenv("ANTHROPIC_API_KEY")
        
        if not xai_key and not anthropic_key:
            return "⚠️ No LLM API keys configured. Unable to respond."

        # Build context-aware prompt with enhanced memory
        tone_instruction = ""
        if suggested_tone != "professional":
            tone_map = {
                "enthusiastic": "Match the user's excitement while staying grounded in data.",
                "empathetic": "Acknowledge any frustration and be supportive while offering solutions.",
                "educational": "Take time to explain concepts clearly since the user is curious.",
                "affirmative": "Validate their thinking and build on their confidence.",
                "reassuring": "Address concerns calmly and provide perspective on risks.",
                "warm": "Be friendly and appreciative in your response.",
            }
            tone_instruction = tone_map.get(suggested_tone, "")
            
        # Adaptive complexity based on user profile
        complexity_instruction = ""
        if response_style.get("explain_basics"):
            complexity_instruction = "Explain any technical terms simply - user may be newer to trading."
        elif response_style.get("assume_knowledge"):
            complexity_instruction = "User is experienced - you can use technical language freely."
            
        system_prompt = f"""{JARVIS_PERSONALITY}

CURRENT MARKET CONTEXT:
{sentiment_context}

{"ENHANCED CONTEXT (from memory system):" if enhanced_context else ""}
{enhanced_context}

{"TONE ADJUSTMENT: " + tone_instruction if tone_instruction else ""}
{"COMPLEXITY: " + complexity_instruction if complexity_instruction else ""}

Respond to the user's query following the Jarvis brand voice guidelines above.
Be helpful, data-driven, and concise.
"""

        response = None
        provider_used = None
        
        # Try Grok (primary)
        if xai_key:
            try:
                client = OpenAI(
                    api_key=xai_key,
                    base_url="https://api.x.ai/v1"
                )
                response = client.chat.completions.create(
                    model="grok-3-fast",
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": message}
                    ],
                    temperature=0.7,
                    max_tokens=500
                )
                provider_used = "grok"
                logger.info("Jarvis response generated via Grok (primary)")
            except Exception as grok_error:
                logger.warning(f"Grok failed, trying Anthropic fallback: {grok_error}")
                response = None
        
        # Fallback to Anthropic
        if response is None and anthropic_key:
            try:
                import anthropic
                client = anthropic.Anthropic(api_key=anthropic_key)
                anthropic_response = client.messages.create(
                    model="claude-sonnet-4-20250514",
                    max_tokens=500,
                    system=system_prompt,
                    messages=[
                        {"role": "user", "content": message}
                    ]
                )
                # Wrap in compatible format
                class MockChoice:
                    def __init__(self, content):
                        self.message = type('obj', (object,), {'content': content})()
                class MockResponse:
                    def __init__(self, content):
                        self.choices = [MockChoice(content)]
                response = MockResponse(anthropic_response.content[0].text)
                provider_used = "anthropic"
                logger.info("Jarvis response generated via Anthropic (fallback)")
            except Exception as anthropic_error:
                logger.error(f"Anthropic fallback also failed: {anthropic_error}")
                return f"⚠️ Both Grok and Anthropic failed. Try again later."
        
        if response is None:
            return "⚠️ No LLM provider available."

        jarvis_response = response.choices[0].message.content
        
        # Store response in memory (for continuity)
        if ENHANCED_MEMORY_AVAILABLE:
            try:
                memory_manager.add_memory(
                    user_id=str(user_id),
                    content=f"[JARVIS RESPONSE]: {jarvis_response[:200]}...",
                    importance=ImportanceLevel.LOW,
                    source="jarvis",
                    analyze_emotion=False,
                )
            except Exception:
                pass  # Non-critical

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


# ═══════════════════════════════════════════════════════════════════════════════
# QUEST/GOAL MANAGEMENT COMMANDS
# ═══════════════════════════════════════════════════════════════════════════════

@error_handler
async def jarvis_goal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /goal <title> - Create a new goal/quest.
    
    Example: /goal Make 10 SOL profit this week
    """
    if not ENHANCED_MEMORY_AVAILABLE:
        await update.message.reply_text("⚠️ Enhanced memory system not available.")
        return
        
    try:
        if not context.args:
            await update.message.reply_text(
                "🎯 *Goal Management*\n\n"
                "Usage:\n"
                "• `/goal <title>` - Create new goal\n"
                "• `/goals` - View active goals\n"
                "• `/milestone <goal_id> <milestone>` - Add milestone\n"
                "• `/complete <milestone_id>` - Complete milestone\n\n"
                "Example: `/goal Make 10 SOL profit this week`",
                parse_mode=ParseMode.MARKDOWN
            )
            return
            
        title = " ".join(context.args)
        user_id = str(update.effective_user.id)
        
        memory_manager = get_enhanced_memory_manager()
        quest = memory_manager.quest_manager.create_quest(
            user_id=user_id,
            title=title,
            description=f"Goal created via Telegram: {title}",
            category="trading" if any(w in title.lower() for w in ["profit", "sol", "trade", "buy", "sell"]) else "general",
        )
        
        await update.message.reply_text(
            f"🎯 *Goal Created*\n\n"
            f"**{quest.title}**\n"
            f"ID: `{quest.id}`\n"
            f"Category: {quest.category}\n\n"
            f"Add milestones with:\n"
            f"`/milestone {quest.id} <step description>`",
            parse_mode=ParseMode.MARKDOWN
        )
        
    except Exception as e:
        logger.exception(f"Error creating goal: {e}")
        await update.message.reply_text(f"⚠️ Error creating goal: {str(e)[:100]}")


@error_handler
async def jarvis_goals(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /goals - View active goals.
    """
    if not ENHANCED_MEMORY_AVAILABLE:
        await update.message.reply_text("⚠️ Enhanced memory system not available.")
        return
        
    try:
        user_id = str(update.effective_user.id)
        memory_manager = get_enhanced_memory_manager()
        
        quests = memory_manager.quest_manager.get_active_quests(user_id)
        
        if not quests:
            await update.message.reply_text(
                "📋 *No Active Goals*\n\n"
                "Create one with `/goal <title>`",
                parse_mode=ParseMode.MARKDOWN
            )
            return
            
        lines = ["📋 *Your Active Goals*\n"]
        
        for quest in quests[:10]:
            progress_bar = "█" * int(quest.progress * 10) + "░" * (10 - int(quest.progress * 10))
            status = "⚠️ OVERDUE" if quest.is_overdue() else f"{int(quest.progress*100)}%"
            
            lines.append(f"\n**{quest.title}**")
            lines.append(f"`{quest.id}` | {quest.category}")
            lines.append(f"[{progress_bar}] {status}")
            
            if quest.milestones:
                for m in quest.milestones[:3]:
                    check = "✅" if m.completed else "⬜"
                    lines.append(f"  {check} {m.description[:40]}")
                if len(quest.milestones) > 3:
                    lines.append(f"  ... +{len(quest.milestones) - 3} more")
                    
        await update.message.reply_text(
            "\n".join(lines),
            parse_mode=ParseMode.MARKDOWN
        )
        
    except Exception as e:
        logger.exception(f"Error listing goals: {e}")
        await update.message.reply_text(f"⚠️ Error: {str(e)[:100]}")


@error_handler
async def jarvis_milestone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /milestone <goal_id> <description> - Add milestone to a goal.
    """
    if not ENHANCED_MEMORY_AVAILABLE:
        await update.message.reply_text("⚠️ Enhanced memory system not available.")
        return
        
    try:
        if len(context.args) < 2:
            await update.message.reply_text(
                "Usage: `/milestone <goal_id> <milestone description>`\n\n"
                "Example: `/milestone abc123 Research top 5 tokens`",
                parse_mode=ParseMode.MARKDOWN
            )
            return
            
        goal_id = context.args[0]
        milestone_desc = " ".join(context.args[1:])
        
        memory_manager = get_enhanced_memory_manager()
        
        if goal_id not in memory_manager.quest_manager.quests:
            await update.message.reply_text(f"⚠️ Goal `{goal_id}` not found. Use `/goals` to see your goals.")
            return
            
        quest = memory_manager.quest_manager.quests[goal_id]
        milestone = quest.add_milestone(milestone_desc)
        
        await update.message.reply_text(
            f"✅ *Milestone Added*\n\n"
            f"Goal: {quest.title}\n"
            f"Milestone: {milestone.description}\n"
            f"ID: `{milestone.id}`\n\n"
            f"Complete it with: `/complete {milestone.id}`",
            parse_mode=ParseMode.MARKDOWN
        )
        
    except Exception as e:
        logger.exception(f"Error adding milestone: {e}")
        await update.message.reply_text(f"⚠️ Error: {str(e)[:100]}")


@error_handler  
async def jarvis_complete(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /complete <milestone_id> - Mark milestone as complete.
    """
    if not ENHANCED_MEMORY_AVAILABLE:
        await update.message.reply_text("⚠️ Enhanced memory system not available.")
        return
        
    try:
        if not context.args:
            await update.message.reply_text("Usage: `/complete <milestone_id>`", parse_mode=ParseMode.MARKDOWN)
            return
            
        milestone_id = context.args[0]
        evidence = " ".join(context.args[1:]) if len(context.args) > 1 else None
        
        memory_manager = get_enhanced_memory_manager()
        
        # Find quest containing this milestone
        for quest in memory_manager.quest_manager.quests.values():
            for milestone in quest.milestones:
                if milestone.id == milestone_id:
                    quest.complete_milestone(milestone_id, evidence)
                    
                    response = f"✅ *Milestone Completed!*\n\n{milestone.description}\n\n"
                    
                    if quest.progress >= 1.0:
                        response += f"🎉 *GOAL COMPLETE: {quest.title}*\nCongratulations!"
                    else:
                        progress_bar = "█" * int(quest.progress * 10) + "░" * (10 - int(quest.progress * 10))
                        response += f"Goal progress: [{progress_bar}] {int(quest.progress*100)}%"
                        
                    await update.message.reply_text(response, parse_mode=ParseMode.MARKDOWN)
                    return
                    
        await update.message.reply_text(f"⚠️ Milestone `{milestone_id}` not found.")
        
    except Exception as e:
        logger.exception(f"Error completing milestone: {e}")
        await update.message.reply_text(f"⚠️ Error: {str(e)[:100]}")


# ═══════════════════════════════════════════════════════════════════════════════
# FEEDBACK COMMANDS (for adaptive learning)
# ═══════════════════════════════════════════════════════════════════════════════

@error_handler
async def jarvis_feedback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /feedback <good|bad> [topic] - Give feedback to help Jarvis adapt.
    
    Examples:
    - /feedback good - Jarvis's last response was helpful
    - /feedback bad technical - Too technical for me
    """
    if not ENHANCED_MEMORY_AVAILABLE:
        await update.message.reply_text("⚠️ Enhanced memory system not available.")
        return
        
    try:
        if not context.args:
            await update.message.reply_text(
                "📊 *Feedback*\n\n"
                "Help Jarvis learn your preferences:\n"
                "• `/feedback good` - Response was helpful\n"
                "• `/feedback bad` - Response wasn't helpful\n"
                "• `/feedback good trading` - Good at trading advice\n"
                "• `/feedback bad technical` - Too technical\n\n"
                "Your feedback adjusts how Jarvis responds to you!",
                parse_mode=ParseMode.MARKDOWN
            )
            return
            
        sentiment = context.args[0].lower()
        topic = context.args[1] if len(context.args) > 1 else None
        
        if sentiment not in ["good", "bad", "positive", "negative", "👍", "👎"]:
            await update.message.reply_text("Usage: `/feedback good` or `/feedback bad`", parse_mode=ParseMode.MARKDOWN)
            return
            
        positive = sentiment in ["good", "positive", "👍"]
        user_id = str(update.effective_user.id)
        
        memory_manager = get_enhanced_memory_manager()
        memory_manager.record_feedback(user_id, positive, topic)
        
        profile = memory_manager.get_user_profile(user_id)
        
        emoji = "👍" if positive else "👎"
        response = f"{emoji} *Feedback Recorded*\n\n"
        response += f"Thanks! I'll adjust my responses.\n\n"
        response += f"Your profile:\n"
        response += f"• Expertise: {profile.expertise_level.name.lower()}\n"
        response += f"• Feedback ratio: {profile.positive_feedback_count}👍 / {profile.negative_feedback_count}👎"
        
        if topic:
            if positive:
                response += f"\n• Added to known topics: {topic}"
            else:
                response += f"\n• Will explain better: {topic}"
                
        await update.message.reply_text(response, parse_mode=ParseMode.MARKDOWN)
        
    except Exception as e:
        logger.exception(f"Error recording feedback: {e}")
        await update.message.reply_text(f"⚠️ Error: {str(e)[:100]}")


@error_handler
async def jarvis_memory_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /memorystats - View memory system statistics (admin only).
    """
    if not ENHANCED_MEMORY_AVAILABLE:
        await update.message.reply_text("⚠️ Enhanced memory system not available.")
        return
        
    try:
        memory_manager = get_enhanced_memory_manager()
        user_id = str(update.effective_user.id)
        
        # Get stats
        total_memories = len(memory_manager.memories)
        user_memory_count = len(memory_manager.user_memories.get(user_id, []))
        total_users = len(memory_manager.user_profiles)
        total_quests = len(memory_manager.quest_manager.quests)
        
        # User profile
        profile = memory_manager.get_user_profile(user_id)
        
        # World state
        memory_manager.world_state.update_time()
        
        response = "🧠 *Enhanced Memory Statistics*\n\n"
        response += "*Global:*\n"
        response += f"• Total memories: {total_memories}\n"
        response += f"• User profiles: {total_users}\n"
        response += f"• Active quests: {total_quests}\n\n"
        response += "*Your Profile:*\n"
        response += f"• Memories: {user_memory_count}\n"
        response += f"• Expertise: {profile.expertise_level.name}\n"
        response += f"• Feedback: {profile.positive_feedback_count}👍 / {profile.negative_feedback_count}👎\n\n"
        response += "*World State:*\n"
        response += f"• {memory_manager.world_state.to_context_string()}\n"
        
        await update.message.reply_text(response, parse_mode=ParseMode.MARKDOWN)
        
    except Exception as e:
        logger.exception(f"Error getting memory stats: {e}")
        await update.message.reply_text(f"⚠️ Error: {str(e)[:100]}")
