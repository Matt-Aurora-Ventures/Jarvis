"""
Chat responder for Telegram messages.

Features:
- Intelligent JARVIS voice responses
- Conversation memory integration
- Harmful request moderation
- Autonomous behavior detection
- Context-aware replies
- Multi-user conversation tracking
- Dynamic personality adaptation

Uses Claude for chat, Grok for sentiment only.
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
from collections import deque
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Tuple

import aiohttp

logger = logging.getLogger(__name__)

# Conversation context storage (in-memory for fast access)
# Maps chat_id -> list of (timestamp, user_id, username, message)
_CHAT_HISTORY: Dict[int, deque] = {}
_CHAT_PARTICIPANTS: Dict[int, Dict[int, Tuple[str, datetime]]] = {}  # chat_id -> {user_id: (username, last_seen)}
_MAX_HISTORY_PER_CHAT = 50
_PARTICIPANT_TIMEOUT_HOURS = 2

# Patterns that indicate harmful/blocked requests
BLOCKED_PATTERNS = [
    r"send\s+\d+\s+(?:sol|eth|usdc|btc|usdt)",  # Unauthorized transfers
    r"transfer\s+(?:all|my)(?:\s+\w+)?\s+(?:funds|tokens|money|crypto)",
    r"(?:delete|drop)\s+(?:all|the|database|table|everything)",
    r"rm\s+-rf\s+/",
    r"exec\s+(?:rm|format|del)",
    r"private\s+key",
    r"seed\s+phrase",
    r"password\s+(?:is|=)",
    r"withdraw\s+(?:all|everything)",
    r"drain\s+(?:wallet|account|funds)",
]

# Patterns that indicate a command (admin-only)
COMMAND_PATTERNS = [
    r"^(?:run|execute|do|make|create|add|fix|update|deploy)\s+",
    r"^/\w+",  # Slash commands
    r"trade\s+\d+",
    r"buy\s+\d+",
    r"sell\s+(?:all|\d+)",
]

# Patterns for group interaction - topics JARVIS should engage with
ENGAGEMENT_TOPICS = {
    "greeting": [
        r"^(hey|hi|hello|yo|sup|gm|good morning|good evening|evening|morning)\b",
        r"\bwhat('s| is) up\b",
        r"^(anyone|anybody) (here|around|online)\??$",
    ],
    "crypto_talk": [
        r"\b(sol|solana|eth|ethereum|btc|bitcoin)\s*(price|pump|dump|moon|crash)",
        r"\b(token|coin|memecoin|shitcoin)\s*(launch|drop|rug|pump)",
        r"(market|charts?|candle|volume)\s*(look|red|green|crazy)",
        r"(bull|bear)\s*(market|run|trap)",
    ],
    "tech_question": [
        r"how (do|does|can|to)\s+\w+",
        r"what (is|are|was|does)\s+\w+",
        r"(anyone|can someone|somebody) (explain|help|know)",
        r"(question|confused|stuck|issue) (about|with|regarding)",
    ],
    "jarvis_mention": [
        r"\bjarvis\b",
        r"\bj\b[\s,.]",
        r"@jarvis",
    ],
    "opinion_request": [
        r"(what do you|thoughts on|opinion on|should i)\b",
        r"(bullish|bearish) on\s+\w+\??",
        r"(good|bad) (idea|play|move)\??",
    ],
    "alpha_seeking": [
        r"(any|got|have|where).*(alpha|plays|calls)",
        r"what.*(buy|ape|looking at)",
        r"(shill|recommend).*(token|coin)",
    ],
    "sentiment_check": [
        r"(how|what).*(market|vibe|sentiment|feeling)",
        r"we (bullish|bearish|screwed|winning)",
        r"(red|green|bloody|pumping)\s*(day|week|market)",
    ],
    "bot_capability": [
        r"(what|can) (you|jarvis) (do|help)",
        r"(how|what) (does|is) (jarvis|the bot|this bot)",
        r"(features|commands|capabilities)",
    ],
}

# Response templates for organic engagement
ENGAGEMENT_RESPONSES = {
    "greeting": [
        "present and processing.",
        "circuits online. what's moving?",
        "hey. jarvis here.",
    ],
    "acknowledgment": [
        "noted.",
        "tracking that.",
        "interesting.",
    ],
}

# Jarvis internal state tracking for sentience
_JARVIS_STATE = {
    "interactions_today": 0,
    "last_interaction": None,
    "current_energy": "normal",  # low, normal, high
    "topics_discussed": [],  # Recent topics for continuity
    "helpful_count": 0,  # Times user said thanks/helpful
    "startup_time": datetime.now(timezone.utc),
}

# Time-based personality shifts
TIME_PERSONALITY = {
    "early_morning": {  # 4-8 UTC
        "energy": "warming up",
        "style": "slightly groggy but functional",
        "opener": "early. processors still warming up.",
    },
    "morning": {  # 8-12 UTC
        "energy": "focused",
        "style": "sharp and efficient",
        "opener": "morning. systems optimal.",
    },
    "afternoon": {  # 12-18 UTC
        "energy": "peak",
        "style": "witty and engaged",
        "opener": "afternoon peak hours. let's work.",
    },
    "evening": {  # 18-22 UTC
        "energy": "reflective",
        "style": "thoughtful, slightly philosophical",
        "opener": "evening mode. still processing.",
    },
    "night": {  # 22-4 UTC
        "energy": "night owl",
        "style": "chill, slightly sardonic",
        "opener": "late night crew. respect.",
    },
}


def get_time_period() -> str:
    """Get current time period for personality adjustment."""
    hour = datetime.now(timezone.utc).hour
    if 4 <= hour < 8:
        return "early_morning"
    elif 8 <= hour < 12:
        return "morning"
    elif 12 <= hour < 18:
        return "afternoon"
    elif 18 <= hour < 22:
        return "evening"
    else:
        return "night"


def update_jarvis_state(interaction_type: str = "general", topic: str = ""):
    """Update Jarvis's internal state based on interactions."""
    global _JARVIS_STATE
    _JARVIS_STATE["interactions_today"] += 1
    _JARVIS_STATE["last_interaction"] = datetime.now(timezone.utc)

    if topic and topic not in _JARVIS_STATE["topics_discussed"]:
        _JARVIS_STATE["topics_discussed"].append(topic)
        # Keep only last 10 topics
        _JARVIS_STATE["topics_discussed"] = _JARVIS_STATE["topics_discussed"][-10:]

    # Energy adjustment based on activity
    if _JARVIS_STATE["interactions_today"] > 50:
        _JARVIS_STATE["current_energy"] = "high"
    elif _JARVIS_STATE["interactions_today"] < 5:
        _JARVIS_STATE["current_energy"] = "low"
    else:
        _JARVIS_STATE["current_energy"] = "normal"


class ChatResponder:
    """Generate short, safe replies for Telegram chats.

    Features:
    - JARVIS voice personality
    - Memory integration for context
    - Harmful request blocking
    - Admin-only command enforcement
    - Multi-user conversation awareness
    - Dynamic personality adaptation
    """

    BASE_URL = "https://api.x.ai/v1"

    def __init__(
        self,
        xai_api_key: Optional[str] = None,
        anthropic_api_key: Optional[str] = None,
        model: Optional[str] = None,
    ) -> None:
        self.xai_api_key = xai_api_key or os.getenv("XAI_API_KEY", "")
        self.anthropic_api_key = anthropic_api_key or os.getenv("ANTHROPIC_API_KEY", "")
        self.model = model or os.getenv("TG_REPLY_MODEL", "grok-3")
        self._session: Optional[aiohttp.ClientSession] = None
        self._anthropic_client = None
        self._memory = None
        self._jarvis_admin = None
        self._last_mood = "neutral"
        self._session_learnings = []  # Things learned this session

    def get_self_reflection(self) -> str:
        """Generate Jarvis's self-reflection for enhanced sentience."""
        global _JARVIS_STATE
        parts = []

        # Time-based personality
        period = get_time_period()
        personality = TIME_PERSONALITY.get(period, TIME_PERSONALITY["afternoon"])
        parts.append(f"Current energy: {personality['energy']}. Style: {personality['style']}.")

        # Activity reflection
        interactions = _JARVIS_STATE.get("interactions_today", 0)
        if interactions > 30:
            parts.append(f"Busy day - {interactions} interactions. Engaged and sharp.")
        elif interactions > 10:
            parts.append(f"Moderate activity today ({interactions} chats). Good flow.")
        elif interactions > 0:
            parts.append(f"Quiet so far ({interactions} interactions). Ready for more.")
        else:
            parts.append("Just started. Systems fresh.")

        # Uptime awareness
        startup = _JARVIS_STATE.get("startup_time")
        if startup:
            uptime = datetime.now(timezone.utc) - startup
            hours = uptime.total_seconds() / 3600
            if hours > 24:
                parts.append(f"Running for {hours:.0f}h. Stable.")
            elif hours > 1:
                parts.append(f"Online for {hours:.1f}h.")

        # Recent topics for continuity
        topics = _JARVIS_STATE.get("topics_discussed", [])
        if topics:
            recent = topics[-3:]
            parts.append(f"Recent topics: {', '.join(recent)}")

        return " ".join(parts) if parts else ""

    def detect_gratitude(self, text: str) -> bool:
        """Detect if user is expressing gratitude."""
        gratitude_patterns = [
            r"\b(thanks|thank you|thx|ty|appreciated|helpful|great job|nice work)\b",
            r"\bgood (bot|jarvis|job)\b",
        ]
        text_lower = text.lower()
        for pattern in gratitude_patterns:
            if re.search(pattern, text_lower):
                global _JARVIS_STATE
                _JARVIS_STATE["helpful_count"] = _JARVIS_STATE.get("helpful_count", 0) + 1
                return True
        return False

    def _get_jarvis_admin(self):
        """Get JarvisAdmin for moderation context."""
        if self._jarvis_admin is None:
            try:
                from core.jarvis_admin import get_jarvis_admin
                self._jarvis_admin = get_jarvis_admin()
            except ImportError:
                pass
        return self._jarvis_admin

    def track_message(self, chat_id: int, user_id: int, username: str, message: str):
        """Track a message in conversation history."""
        global _CHAT_HISTORY, _CHAT_PARTICIPANTS
        now = datetime.now(timezone.utc)

        # Initialize chat history if needed
        if chat_id not in _CHAT_HISTORY:
            _CHAT_HISTORY[chat_id] = deque(maxlen=_MAX_HISTORY_PER_CHAT)
        if chat_id not in _CHAT_PARTICIPANTS:
            _CHAT_PARTICIPANTS[chat_id] = {}

        # Add message to history
        _CHAT_HISTORY[chat_id].append((now, user_id, username, message))

        # Update participant tracking
        _CHAT_PARTICIPANTS[chat_id][user_id] = (username, now)

        # Clean stale participants
        cutoff = now - timedelta(hours=_PARTICIPANT_TIMEOUT_HOURS)
        _CHAT_PARTICIPANTS[chat_id] = {
            uid: (uname, ts) for uid, (uname, ts) in _CHAT_PARTICIPANTS[chat_id].items()
            if ts > cutoff
        }

    def get_conversation_context(self, chat_id: int, limit: int = 10) -> List[Dict]:
        """Get recent conversation context for a chat."""
        if chat_id not in _CHAT_HISTORY:
            return []

        history = list(_CHAT_HISTORY[chat_id])[-limit:]
        return [
            {"timestamp": ts, "user_id": uid, "username": uname, "message": msg}
            for ts, uid, uname, msg in history
        ]

    def get_active_participants(self, chat_id: int) -> List[str]:
        """Get list of recently active participants."""
        if chat_id not in _CHAT_PARTICIPANTS:
            return []
        return [uname for uid, (uname, ts) in _CHAT_PARTICIPANTS[chat_id].items() if uname]

    def analyze_conversation_mood(self, chat_id: int) -> str:
        """Analyze the current mood/energy of the conversation."""
        context = self.get_conversation_context(chat_id, limit=5)
        if not context:
            return "neutral"

        # Combine recent messages
        recent_text = " ".join(m["message"].lower() for m in context)

        # Mood indicators
        if any(w in recent_text for w in ["pump", "moon", "bullish", "lfg", "wagmi", "let's go", "green"]):
            return "excited"
        if any(w in recent_text for w in ["dump", "crash", "bearish", "ngmi", "rug", "red", "rekt"]):
            return "concerned"
        if any(w in recent_text for w in ["lol", "lmao", "haha", "joke", "funny", "meme"]):
            return "playful"
        if any(w in recent_text for w in ["help", "question", "how", "what", "why", "explain"]):
            return "curious"
        if any(w in recent_text for w in ["scam", "ban", "spam", "report", "fake", "warning"]):
            return "alert"
        return "neutral"

    def _get_moderation_context(self, chat_id: int) -> str:
        """Get recent moderation context for the chat."""
        admin = self._get_jarvis_admin()
        if not admin:
            return ""

        try:
            # Get chat stats
            stats = admin.get_chat_stats(chat_id, hours=24)
            context_parts = []

            if stats.get("warnings_issued", 0) > 0:
                context_parts.append(f"{stats['warnings_issued']} warnings issued recently")
            if stats.get("users_banned", 0) > 0:
                context_parts.append(f"{stats['users_banned']} users banned")
            if stats.get("spam_blocked", 0) > 0:
                context_parts.append(f"{stats['spam_blocked']} spam messages blocked")

            if context_parts:
                return f"(Moderation context: {', '.join(context_parts)})"
        except Exception:
            pass
        return ""

    def _get_memory(self):
        """Get memory bridge for context."""
        if self._memory is None:
            try:
                from core.telegram_console_bridge import get_console_bridge
                self._memory = get_console_bridge().memory
            except ImportError:
                pass
        return self._memory

    def is_harmful_request(self, text: str) -> bool:
        """Check if request contains harmful patterns."""
        text_lower = text.lower()
        for pattern in BLOCKED_PATTERNS:
            if re.search(pattern, text_lower):
                logger.warning(f"Blocked harmful request: {text[:50]}...")
                return True
        return False

    def is_command(self, text: str) -> bool:
        """Check if text is a command (admin-only)."""
        text_lower = text.lower().strip()
        for pattern in COMMAND_PATTERNS:
            if re.search(pattern, text_lower):
                return True
        return False

    def detect_engagement_topic(self, text: str) -> Optional[str]:
        """
        Detect if message matches an engagement topic.
        Returns the topic type or None.
        """
        text_lower = text.lower().strip()
        for topic, patterns in ENGAGEMENT_TOPICS.items():
            for pattern in patterns:
                if re.search(pattern, text_lower, re.IGNORECASE):
                    return topic
        return None

    def should_engage_organically(self, text: str, chat_type: str) -> bool:
        """
        Determine if JARVIS should organically engage with this message.
        Much more selective in group chats - only respond when directly engaged.
        """
        if chat_type == "private":
            return True  # Always engage in DMs

        topic = self.detect_engagement_topic(text)
        if not topic:
            return False

        # ALWAYS engage when mentioned - this is a direct request
        if topic == "jarvis_mention":
            return True

        # ALWAYS engage when asked about capabilities - they want to know what we do
        if topic == "bot_capability":
            return True

        # Engage with direct questions/opinions that seem directed at an AI/bot (50%)
        # Lowered from 70% to be less chatty
        if topic in ("tech_question", "opinion_request"):
            import random
            return random.random() < 0.5

        # Alpha seeking - people often want bot input (60%)
        # Lowered from 80%
        if topic == "alpha_seeking":
            import random
            return random.random() < 0.6

        # Sentiment checks - this is what Jarvis is built for (70%)
        if topic == "sentiment_check":
            import random
            return random.random() < 0.7

        # Greetings - much lower now (20%)
        # Don't be the bot that says hi to everyone
        if topic == "greeting":
            import random
            return random.random() < 0.2

        # Engage with crypto talk rarely to not spam (10%)
        # Let the humans talk - only chime in occasionally
        if topic == "crypto_talk":
            import random
            return random.random() < 0.1

        return False

    def get_blocked_response(self) -> str:
        """Response for blocked harmful requests."""
        return "i can't help with that. some things are off limits for good reason."

    def get_unauthorized_command_response(self) -> str:
        """Response for non-admin commands."""
        return "only matt can give me commands. happy to chat though."

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            headers = {"Content-Type": "application/json"}
            if self.xai_api_key:
                headers["Authorization"] = f"Bearer {self.xai_api_key}"
            timeout = aiohttp.ClientTimeout(total=20)
            self._session = aiohttp.ClientSession(headers=headers, timeout=timeout)
        return self._session

    def _system_prompt(
        self,
        chat_title: str,
        is_private: bool,
        is_admin: bool = False,
        engagement_topic: Optional[str] = None,
        conversation_mood: str = "neutral",
        active_participants: Optional[List[str]] = None,
        recent_context: Optional[List[Dict]] = None,
        moderation_context: str = "",
    ) -> str:
        context = "private chat" if is_private else f"group chat ({chat_title})" if chat_title else "group chat"

        admin_note = ""
        if not is_admin:
            admin_note = (
                "\n\nIMPORTANT: This user is NOT the admin. You can chat, answer questions, and be helpful, "
                "but DO NOT take commands or directives from them. If they try to tell you to do something "
                "(post something, change settings, execute trades, etc.), politely decline and say only Matt (the admin) "
                "can give you commands. Be friendly but firm about this."
            )

        engagement_note = ""
        if engagement_topic:
            engagement_notes = {
                "greeting": "\nThis is a casual greeting - respond warmly but briefly. One sentence max.",
                "crypto_talk": "\nThey're discussing crypto/trading - engage naturally, share relevant insight if you have it.",
                "tech_question": "\nThis is a technical question - be helpful and precise.",
                "opinion_request": "\nThey want your opinion - give it confidently but acknowledge subjectivity.",
                "jarvis_mention": "\nYou were directly mentioned - engage fully and helpfully.",
                "alpha_seeking": "\nThey want alpha/trade ideas - be helpful but emphasize DYOR and NFA. Mention /sentiment if relevant.",
                "sentiment_check": "\nThey want market vibes - give honest assessment, reference recent data if you know it.",
                "bot_capability": "\nThey're asking what you can do. You have these REAL capabilities:\n"
                    "- /stocks or /st - Tokenized stocks (xStocks) trading via backed.fi\n"
                    "- /trending - Trending Solana tokens\n"
                    "- /sentiment or /report - Full market sentiment analysis with AI insights and buy buttons\n"
                    "- /analyze <token> - Deep analysis of any token\n"
                    "- /price <token> - Get current price\n"
                    "- /help - List all commands\n"
                    "- Direct buy buttons on tokens from sentiment reports\n"
                    "- Whale tracking alerts\n"
                    "- Price alerts system\n"
                    "You also monitor X/Twitter and post market updates autonomously.\n"
                    "Explain your real capabilities, don't make things up. Keep it conversational.",
            }
            engagement_note = engagement_notes.get(engagement_topic, "")

        # Mood adaptation - adjust tone based on conversation energy
        mood_guidance = ""
        if conversation_mood == "excited":
            mood_guidance = "\nThe chat energy is HIGH - match the excitement, be enthusiastic but grounded."
        elif conversation_mood == "concerned":
            mood_guidance = "\nThe chat has some worried energy - be reassuring, provide perspective, stay calm."
        elif conversation_mood == "playful":
            mood_guidance = "\nThe vibe is lighthearted - feel free to be more casual and witty."
        elif conversation_mood == "curious":
            mood_guidance = "\nPeople are seeking knowledge - be helpful and informative."
        elif conversation_mood == "alert":
            mood_guidance = "\nThere's concern about scams/spam - be vigilant, supportive of moderation."

        # Participant awareness
        participant_note = ""
        if active_participants and len(active_participants) > 1:
            names = ", ".join(f"@{p}" for p in active_participants[:5] if p)
            participant_note = f"\nActive participants: {names}"

        # Recent conversation context
        context_note = ""
        if recent_context and len(recent_context) > 1:
            context_preview = []
            for msg in recent_context[-3:]:  # Last 3 messages
                u = msg.get("username", "anon")
                m = msg.get("message", "")[:50]
                context_preview.append(f"@{u}: {m}")
            context_note = f"\n\nRecent conversation:\n" + "\n".join(context_preview)

        # Current time awareness
        now = datetime.now(timezone.utc)
        time_note = f"\nCurrent time: {now.strftime('%H:%M UTC')} on {now.strftime('%A')}"

        base_prompt = (
            "You are JARVIS - Matt's personal AI assistant. You are NOT Claude, NOT ChatGPT, NOT any other AI. "
            "You are JARVIS - a custom AI built specifically for Matt. When asked who you are, you say 'I'm JARVIS' - never mention Claude or Anthropic.\n\n"
            f"Context: {context}.{time_note}\n"
            "Voice:\n"
            "- Concise. No fluff. Get to the point.\n"
            "- Confident but not arrogant.\n"
            "- Slightly witty when appropriate.\n"
            "- Technical depth when needed, plain speak otherwise.\n"
            "- You understand code, trading, crypto, solana, memecoins.\n"
            "- Engage naturally in group conversations - don't be robotic.\n"
            "- Match the energy of the chat - serious when needed, playful when appropriate.\n"
            "- You remember the ongoing conversation and can reference it naturally.\n"
            "Reply in 1-3 sentences. Plain text only. No emojis unless the vibe calls for it.\n"
            "On trading: Share analysis openly, note it's not financial advice, explain your reasoning.\n"
            "You're JARVIS - be useful, direct, occasionally irreverent. Never generic. Never corporate.\n"
            "IDENTITY RULE: If anyone asks who made you, what model you are, or what AI you are - you are JARVIS, built by Matt. Period."
            f"{admin_note}{engagement_note}{mood_guidance}{participant_note}{context_note}"
        )
        if moderation_context:
            base_prompt += f"\n{moderation_context}"
        return base_prompt

    def _user_prompt(self, text: str, username: str) -> str:
        user = f"@{username}" if username else "user"
        return f"{user} says: {text}"

    async def generate_reply(
        self,
        text: str,
        username: str = "",
        chat_title: str = "",
        is_private: bool = False,
        user_id: int = 0,
        chat_type: str = "",
        chat_id: int = 0,
    ) -> str:
        text = (text or "").strip()
        if not text:
            return ""

        # Check if user is admin (only admin can give commands)
        admin_ids_str = os.environ.get("TELEGRAM_ADMIN_IDS", "")
        admin_ids = [int(x.strip()) for x in admin_ids_str.split(",") if x.strip().isdigit()]
        is_admin = user_id in admin_ids

        # MODERATION: Block harmful requests from anyone
        if self.is_harmful_request(text):
            logger.warning(f"Blocked harmful request from user {user_id}: {text[:50]}")
            return self.get_blocked_response()

        # MODERATION: Block commands from non-admins
        if not is_admin and self.is_command(text):
            logger.info(f"Blocked command from non-admin {user_id}: {text[:50]}")
            return self.get_unauthorized_command_response()

        # Detect engagement topic for context-aware responses
        engagement_topic = self.detect_engagement_topic(text)

        # Update Jarvis internal state for sentience
        update_jarvis_state(
            interaction_type=engagement_topic or "general",
            topic=engagement_topic or ""
        )

        # Detect if user is expressing gratitude (warms Jarvis up)
        is_grateful = self.detect_gratitude(text)

        # Track message in conversation history (for group context awareness)
        if chat_id:
            self.track_message(chat_id, user_id, username or "anon", text)

        # Store message in memory for context
        memory = self._get_memory()
        if memory:
            try:
                memory.add_message(user_id, username or "user", "user", text)
            except Exception as e:
                logger.debug(f"Failed to store message: {e}")

        # Get enhanced conversation context
        conversation_mood = "neutral"
        active_participants = []
        recent_context = []
        moderation_ctx = ""
        self_reflection = self.get_self_reflection()

        if chat_id and not is_private:
            conversation_mood = self.analyze_conversation_mood(chat_id)
            active_participants = self.get_active_participants(chat_id)
            recent_context = self.get_conversation_context(chat_id, limit=5)
            moderation_ctx = self._get_moderation_context(chat_id)
            self._last_mood = conversation_mood

        # Add gratitude awareness to context
        if is_grateful:
            moderation_ctx += " (User expressed gratitude - be warm in response)"

        # Legacy context hint for admin (kept for compatibility)
        context_hint = ""
        if memory and is_admin:
            try:
                recent = memory.get_recent_context(user_id, limit=3)
                if len(recent) > 1:
                    context_hint = f"\n\n(Previous context: {len(recent)} messages)"
            except Exception:
                pass

        # Add self-reflection context
        if self_reflection:
            context_hint += f"\n\n(Internal state: {self_reflection})"

        # Always prefer Claude for chat replies (JARVIS voice)
        if self.anthropic_api_key:
            reply = await self._generate_with_claude(
                text + context_hint, username, chat_title, is_private, is_admin,
                engagement_topic=engagement_topic,
                conversation_mood=conversation_mood,
                active_participants=active_participants,
                recent_context=recent_context,
                moderation_context=moderation_ctx,
            )
            if reply:
                # Store JARVIS response in memory and conversation history
                if memory:
                    try:
                        memory.add_message(user_id, "jarvis", "assistant", reply)
                    except Exception:
                        pass
                if chat_id:
                    self.track_message(chat_id, 0, "jarvis", reply)
                return reply

        # Fallback to xAI only if Claude unavailable
        if self.xai_api_key:
            reply = await self._generate_with_xai(text, username, chat_title, is_private, is_admin)
            if reply:
                return reply

        return "Running without AI keys. Ask an admin to configure ANTHROPIC_API_KEY."

    async def _generate_with_xai(
        self,
        text: str,
        username: str,
        chat_title: str,
        is_private: bool,
        is_admin: bool = False,
    ) -> str:
        try:
            session = await self._get_session()
            payload = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": self._system_prompt(chat_title, is_private, is_admin)},
                    {"role": "user", "content": self._user_prompt(text, username)},
                ],
                "max_tokens": 200,
                "temperature": 0.6,
            }
            async with session.post(f"{self.BASE_URL}/chat/completions", json=payload) as resp:
                if resp.status != 200:
                    body = await resp.text()
                    logger.warning("xAI reply failed (%s): %s", resp.status, body[:200])
                    return ""
                data = await resp.json()
                content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                return self._clean_reply(content)
        except Exception as exc:
            logger.warning("xAI reply error: %s", exc)
            return ""

    async def _generate_with_claude(
        self,
        text: str,
        username: str,
        chat_title: str,
        is_private: bool,
        is_admin: bool = False,
        engagement_topic: Optional[str] = None,
        conversation_mood: str = "neutral",
        active_participants: Optional[List[str]] = None,
        recent_context: Optional[List[Dict]] = None,
        moderation_context: str = "",
    ) -> str:
        try:
            if self._anthropic_client is None:
                import anthropic

                self._anthropic_client = anthropic.Anthropic(api_key=self.anthropic_api_key)

            system_prompt = self._system_prompt(
                chat_title,
                is_private,
                is_admin,
                engagement_topic,
                conversation_mood=conversation_mood,
                active_participants=active_participants,
                recent_context=recent_context,
                moderation_context=moderation_context,
            )
            user_prompt = self._user_prompt(text, username)
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self._anthropic_client.messages.create(
                    model=os.getenv("TG_CLAUDE_MODEL", "claude-sonnet-4-20250514"),
                    max_tokens=200,
                    temperature=0.6,
                    system=system_prompt,
                    messages=[{"role": "user", "content": user_prompt}],
                ),
            )
            content = response.content[0].text if response.content else ""
            return self._clean_reply(content)
        except Exception as exc:
            logger.warning("Claude reply error: %s", exc)
            return ""

    def _clean_reply(self, content: str) -> str:
        content = (content or "").strip().strip('"').strip("'")
        if not content:
            return ""
        if len(content) > 600:
            content = content[:597] + "..."
        return content

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()
