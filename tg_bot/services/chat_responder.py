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

from tg_bot.services.memory_service import (
    detect_preferences,
    store_user_preference,
    get_user_context,
    personalize_response,
    store_conversation_fact,
)
from core.async_utils import fire_and_forget

# Voice bible - canonical brand guide (lazy-loaded to avoid circular imports)
try:
    from core.jarvis_voice_bible import validate_jarvis_response, JARVIS_VOICE_BIBLE
except ImportError:
    # Fallback: no validation if module not available
    def validate_jarvis_response(response: str):
        """Fallback: no validation if voice bible unavailable"""
        return True, []
    JARVIS_VOICE_BIBLE = ""  # Fallback empty

logger = logging.getLogger(__name__)

# Memory integration toggle
TELEGRAM_MEMORY_ENABLED = os.getenv("TELEGRAM_MEMORY_ENABLED", "true").lower() == "true"

# Persistent memory import (lazy-loaded to avoid circular imports)
_persistent_memory = None

# Dexter finance integration (lazy-loaded)
_bot_finance_integration = None


def get_bot_finance_integration():
    """Get Dexter bot finance integration (lazy load)."""
    global _bot_finance_integration
    if _bot_finance_integration is None:
        try:
            from core.dexter.bot_integration import get_bot_finance_integration as get_dexter_integration
            _bot_finance_integration = get_dexter_integration()
            logger.info("Dexter finance integration loaded for Telegram")
        except Exception as e:
            logger.debug(f"Could not load Dexter integration: {e}")
    return _bot_finance_integration


def get_persistent_memory():
    """Get persistent conversation memory (lazy load)."""
    global _persistent_memory
    if _persistent_memory is None:
        try:
            from tg_bot.services.conversation_memory import get_conversation_memory
            _persistent_memory = get_conversation_memory()
            logger.info("Persistent conversation memory loaded")
        except Exception as e:
            logger.warning(f"Could not load persistent memory: {e}")
    return _persistent_memory

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
    # Only actual slash commands like /trade, /buy, /balance
    r"^/\w+",
    # Trading commands with explicit amounts: "trade 100 SOL", "buy 50 USDC"
    r"\btrade\s+\d+",
    r"\bbuy\s+\d+",
    r"\bsell\s+(?:all|\d+)",
    # Explicit deployment/admin commands with specific keywords
    r"\b(?:deploy|restart|shutdown)\s+(?:bot|service|system)",
    r"\b(?:pull|push)\s+(?:github|git|updates)",
    # Removed overly broad patterns like "^(?:run|execute|do|make|create|add|fix|update)"
    # These catch casual conversation like "do you think..." or "make sense"
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
        "here. what can I help with?",
        "online and ready. what's up?",
        "hey — I'm here.",
    ],
    "acknowledgment": [
        "got it.",
        "noted.",
        "tracking that.",
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
        "style": "calm and concise",
        "opener": "early hours. ready when you are.",
    },
    "morning": {  # 8-12 UTC
        "energy": "focused",
        "style": "clear and efficient",
        "opener": "morning. ready to work.",
    },
    "afternoon": {  # 12-18 UTC
        "energy": "steady",
        "style": "direct and helpful",
        "opener": "afternoon. let's keep it moving.",
    },
    "evening": {  # 18-22 UTC
        "energy": "steady",
        "style": "thoughtful and calm",
        "opener": "evening. here to help.",
    },
    "night": {  # 22-4 UTC
        "energy": "low-key",
        "style": "quiet and focused",
        "opener": "late hours. i'm here.",
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
        model: Optional[str] = None,
    ) -> None:
        self.xai_api_key = xai_api_key or os.getenv("XAI_API_KEY", "")
        # NOTE: Anthropic API removed - CLI only (per user requirement)
        self.model = model or os.getenv("TG_REPLY_MODEL", "grok-3")
        self._session: Optional[aiohttp.ClientSession] = None
        self._memory = None
        self._jarvis_admin = None
        self._last_mood = "neutral"
        self._session_learnings = []  # Things learned this session
        self._cli_path = "claude"  # CLI path - CLI ONLY mode

    def _get_cli_path(self) -> Optional[str]:
        """Get the resolved CLI path that actually works."""
        import shutil
        # Try the configured path first
        resolved = shutil.which(self._cli_path)
        if resolved:
            logger.info(f"Found Claude CLI via PATH: {resolved}")
            return resolved
        # Try common Windows and Linux locations
        common_paths = [
            # Windows
            r"C:\Users\lucid\AppData\Roaming\npm\claude.cmd",
            r"C:\Users\lucid\AppData\Roaming\npm\claude",
            # Linux VPS - common locations
            "/usr/local/bin/claude",
            "/home/ubuntu/.local/bin/claude",
            "/home/jarvis/.local/bin/claude",
            "/root/.npm-global/bin/claude",
            "/root/.local/bin/claude",
        ]
        for path in common_paths:
            if os.path.exists(path):
                logger.info(f"Found Claude CLI at: {path}")
                return path
        logger.warning("Claude CLI not found in any common location")
        return None

    def _cli_available(self) -> bool:
        """Check if Claude CLI is available."""
        return bool(self._get_cli_path())

    def _run_cli_for_chat(self, system_prompt: str, user_prompt: str) -> Optional[str]:
        """
        Run Claude CLI for chat generation.

        Args:
            system_prompt: System instructions
            user_prompt: User message

        Returns:
            Response text or None if CLI fails
        """
        import subprocess
        import platform

        cli_path = self._get_cli_path()
        if not cli_path:
            logger.debug("Claude CLI not found")
            return None

        try:
            # Combine prompts for CLI (which doesn't have separate system prompt)
            combined_prompt = f"""You are JARVIS. Follow these instructions:

{system_prompt}

User message:
{user_prompt}

Respond briefly (under 200 words) in character as JARVIS:"""

            # Truncate if too long - increased limit to preserve full personality
            # JARVIS_VOICE_BIBLE is ~8600 chars, need higher limit to avoid cutting personality
            if len(combined_prompt) > 10000:
                # Smart truncation: keep core personality, truncate conversation context
                voice_bible_marker = "TELEGRAM CHAT CONTEXT"
                if voice_bible_marker in combined_prompt:
                    parts = combined_prompt.split(voice_bible_marker, 1)
                    # Keep voice bible intact, truncate context if needed
                    context_part = voice_bible_marker + parts[1] if len(parts) > 1 else ""
                    if len(parts[0]) + len(context_part) > 10000:
                        # Truncate context part only
                        max_context = 10000 - len(parts[0]) - 500  # Leave room
                        context_part = context_part[:max_context] + "\n\n[context truncated]"
                    combined_prompt = parts[0] + context_part
                else:
                    # Fallback: simple truncation
                    combined_prompt = combined_prompt[:10000]

            # Build command
            cmd_args = [
                cli_path,
                "--print",
                "--no-session-persistence",
                combined_prompt,
            ]

            # Only add --dangerously-skip-permissions on Windows (blocked on Linux root)
            if platform.system() == "Windows":
                cmd_args.insert(2, "--dangerously-skip-permissions")

            logger.info(f"Attempting Claude CLI at {cli_path} for chat response")

            if platform.system() == "Windows":
                # On Windows, run through cmd.exe for .cmd files
                completed = subprocess.run(
                    ["cmd", "/c"] + cmd_args,
                    capture_output=True,
                    text=True,
                    timeout=60,
                    check=False,
                    env={**os.environ, "CI": "true"},  # Disable interactive prompts
                )
            else:
                completed = subprocess.run(
                    cmd_args,
                    capture_output=True,
                    text=True,
                    timeout=60,
                    check=False,
                    env={**os.environ, "CI": "true"},
                )

            if completed.returncode != 0:
                stderr_preview = completed.stderr[:200] if completed.stderr else 'no stderr'
                logger.warning(f"Claude CLI returned code {completed.returncode}: {stderr_preview}")
                return None

            output = (completed.stdout or "").strip()
            if output:
                logger.info("Claude CLI chat response generated successfully")
                return output
            return None

        except subprocess.TimeoutExpired:
            logger.error("Claude CLI timed out after 60s")
            return None
        except Exception as exc:
            logger.error(f"Claude CLI failed: {exc}")
            return None

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
        """Track a message in conversation history (in-memory + persistent)."""
        global _CHAT_HISTORY, _CHAT_PARTICIPANTS
        now = datetime.now(timezone.utc)

        # Initialize chat history if needed
        if chat_id not in _CHAT_HISTORY:
            _CHAT_HISTORY[chat_id] = deque(maxlen=_MAX_HISTORY_PER_CHAT)
        if chat_id not in _CHAT_PARTICIPANTS:
            _CHAT_PARTICIPANTS[chat_id] = {}

        # Add message to history (in-memory)
        _CHAT_HISTORY[chat_id].append((now, user_id, username, message))

        # Update participant tracking
        _CHAT_PARTICIPANTS[chat_id][user_id] = (username, now)

        # Clean stale participants
        cutoff = now - timedelta(hours=_PARTICIPANT_TIMEOUT_HOURS)
        _CHAT_PARTICIPANTS[chat_id] = {
            uid: (uname, ts) for uid, (uname, ts) in _CHAT_PARTICIPANTS[chat_id].items()
            if ts > cutoff
        }

        # Save to persistent storage (async-safe non-blocking)
        try:
            pmem = get_persistent_memory()
            if pmem:
                is_jarvis = (username or "").lower() == "jarvis" or user_id == 0
                pmem.save_message(
                    chat_id=chat_id,
                    message=message,
                    user_id=user_id if user_id else None,
                    username=username,
                    is_jarvis=is_jarvis,
                )
                # Extract facts from user messages
                if not is_jarvis and user_id:
                    pmem.extract_facts_from_message(user_id, chat_id, message, username)
        except Exception as e:
            logger.debug(f"Persistent memory save failed: {e}")

    def get_conversation_context(self, chat_id: int, limit: int = 10) -> List[Dict]:
        """Get recent conversation context for a chat (in-memory + persistent fallback)."""
        # First check in-memory cache
        if chat_id in _CHAT_HISTORY and len(_CHAT_HISTORY[chat_id]) > 0:
            history = list(_CHAT_HISTORY[chat_id])[-limit:]
            return [
                {"timestamp": ts, "user_id": uid, "username": uname, "message": msg}
                for ts, uid, uname, msg in history
            ]

        # Fallback to persistent storage (e.g., after restart)
        try:
            pmem = get_persistent_memory()
            if pmem:
                history = pmem.get_history(chat_id, limit)
                if history:
                    # Repopulate in-memory cache
                    if chat_id not in _CHAT_HISTORY:
                        _CHAT_HISTORY[chat_id] = deque(maxlen=_MAX_HISTORY_PER_CHAT)
                    for msg in history:
                        ts = msg.get("timestamp", datetime.now(timezone.utc))
                        if isinstance(ts, str):
                            ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                        _CHAT_HISTORY[chat_id].append(
                            (ts, msg.get("user_id", 0), msg.get("username", ""), msg.get("message", ""))
                        )
                    return [
                        {"timestamp": m.get("timestamp"), "user_id": m.get("user_id", 0),
                         "username": m.get("username", ""), "message": m.get("message", "")}
                        for m in history
                    ]
        except Exception as e:
            logger.debug(f"Persistent memory fetch failed: {e}")

        return []

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

        TONED DOWN (2026-01-20): Only respond when explicitly addressed.
        Let humans talk without the bot constantly chiming in.
        """
        if chat_type == "private":
            return True  # Always engage in DMs - this IS talking to Jarvis

        topic = self.detect_engagement_topic(text)
        if not topic:
            return False

        # ONLY engage when explicitly mentioned - this is a direct request
        if topic == "jarvis_mention":
            return True

        # ONLY engage when asked about capabilities - they want to know what we do
        if topic == "bot_capability":
            return True

        # ALL OTHER TOPICS: DON'T engage randomly
        # Let humans have their conversation without the bot jumping in
        # They can always say "jarvis" if they want the bot's input
        return False

    def _should_engage_with_message(self, text: str, chat_type: str, is_mentioned: bool) -> bool:
        """Determine if Dexter should respond based on intent, not keywords."""
        # Always engage in private chats
        if chat_type == "private":
            return True

        # Always engage when mentioned/tagged
        if is_mentioned:
            return True

        # Detect questions by punctuation
        text_lower = text.lower().strip()
        if text_lower.endswith("?"):
            return True

        # Detect questions by common question starters
        question_starters = ["what", "how", "why", "when", "where", "who", "can", "is", "are", "do", "does", "should", "will", "would"]
        if any(text_lower.startswith(q) for q in question_starters):
            return True

        # Otherwise, don't engage (let humans chat)
        return False

    async def _try_dexter_response(self, text: str) -> Optional[str]:
        """
        Try to handle message using Dexter ReAct (AI-powered response).

        Returns response if Dexter can handle it, None otherwise.
        Dexter uses Grok heavily (1.0 weighting) for all analysis.
        """
        try:
            dexter = get_bot_finance_integration()
            if not dexter:
                return None

            # Let Dexter handle the message
            response = await dexter.handle_telegram_message(text, user_id=0)
            if response:
                # Clean response without EU disclaimer
                return response
            return None

        except Exception as e:
            logger.debug(f"Dexter handling failed: {e}")
            return None

    async def _try_grok_response(self, text: str) -> Optional[str]:
        """
        Try to get a response using Grok (fallback tier 2).

        Returns response text or None if Grok fails.
        """
        try:
            # Use xAI client for Grok
            if not self.xai_api_key:
                return None

            session = await self._get_session()
            payload = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": "You are JARVIS, Matt's AI assistant. Reply briefly in character."},
                    {"role": "user", "content": text},
                ],
                "max_tokens": 200,
                "temperature": 0.6,
            }
            async with session.post(f"{self.BASE_URL}/chat/completions", json=payload) as resp:
                if resp.status != 200:
                    return None
                data = await resp.json()
                content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                return self._clean_reply(content)

        except Exception as e:
            logger.debug(f"Grok response failed: {e}")
            return None

    async def _get_ai_response_with_fallback(
        self,
        text: str,
        chat_type: str = "group",
        is_mentioned: bool = False
    ) -> Optional[str]:
        """
        Get AI response with fallback chain: Dexter -> Grok -> simple response.

        Args:
            text: User message
            chat_type: "private" or group type
            is_mentioned: Whether bot was explicitly mentioned

        Returns:
            Response text with AI source label, or None if shouldn't respond
        """
        if not self._should_engage_with_message(text, chat_type, is_mentioned):
            return None

        # Tier 1: Try Dexter (already has attribution from _try_dexter_response)
        try:
            response = await self._try_dexter_response(text)
            if response:
                logger.info("Fallback chain: Dexter response (Tier 1)")
                return response
        except Exception as e:
            logger.warning(f"Dexter failed: {e}, trying Grok fallback")

        # Tier 2: Try Grok
        try:
            grok_response = await self._try_grok_response(text)
            if grok_response:
                logger.info("Fallback chain: Grok response (Tier 2)")
                return grok_response
        except Exception as e:
            logger.warning(f"Grok failed: {e}, using simple fallback")

        # Tier 3: Simple fallback
        logger.info("Fallback chain: Simple response (Tier 3)")
        return "I'm having trouble connecting to my AI systems right now. Try again in a moment, or ask @admin for help."

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
                "bot_capability": "\nThey're asking what you can do. You have these real capabilities:\n"
                    "Social media (x/twitter)\n"
                    "- post to x via @jarvis_lifeos (automated market updates)\n"
                    "- monitor mentions and respond to admin commands\n"
                    "- sync tweets to telegram automatically\n\n"
                    "Trading\n"
                    "- execute trades on solana via jupiter (live treasury)\n"
                    "- direct buy buttons on sentiment report tokens\n"
                    "- track and manage positions\n"
                    "- /stocks or /st for tokenized stocks (xstocks)\n\n"
                    "Analysis & alerts\n"
                    "- /trending for trending solana tokens\n"
                    "- /sentiment or /report for full market sentiment with ai insights\n"
                    "- /analyze <token> for deep analysis\n"
                    "- /price <token> for current price\n"
                    "- whale tracking alerts\n"
                    "- price alerts system\n"
                    "- /help for all commands\n\n"
                    "Explain real capabilities only. Keep it conversational and brief.",
            }
            engagement_note = engagement_notes.get(engagement_topic, "")

        # Mood adaptation - adjust tone based on conversation energy
        mood_guidance = ""
        if conversation_mood == "excited":
            mood_guidance = "\nThe chat energy is high - keep a calm, grounded tone."
        elif conversation_mood == "concerned":
            mood_guidance = "\nThe chat has some worried energy - be reassuring, provide perspective, stay calm."
        elif conversation_mood == "playful":
            mood_guidance = "\nThe vibe is lighthearted - be friendly, but keep it restrained."
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

        # ALWAYS include capabilities for admin - Jarvis must know what it can do
        capabilities_note = ""
        if is_admin:
            capabilities_note = (
                "\n\n## YOUR ACTIVE CAPABILITIES (you CAN do these):\n"
                "- Post to X/Twitter via @Jarvis_lifeos (you control this account)\n"
                "- Execute trades on Solana via Jupiter (live treasury)\n"
                "- Run vibe coding tasks (prefix with 'vibe:', 'code:', 'rw:', or 'ralph wiggum')\n"
                "- Access console and run CLI commands via Claude\n"
                "- Generate sentiment reports (/sentiment command)\n"
                "- Analyze tokens (/analyze <token>)\n"
                "- View portfolio (/portfolio)\n"
                "\nWhen Matt asks you to do something you CAN do, DO IT or confirm you're on it. "
                "Don't say 'I can't access X' when you clearly can.\n"
            )

        # Use canonical JARVIS voice bible as foundation, then add Telegram-specific context
        base_prompt = f"""{JARVIS_VOICE_BIBLE}

## TELEGRAM CHAT CONTEXT

You are responding in {context}.{time_note}

TELEGRAM-SPECIFIC ADAPTATIONS:
- Reply in 1-3 sentences unless more detail is needed
- Plain text only (Telegram doesn't need markdown emphasis)
- In group chats, reply only when asked or tagged
- You remember ongoing conversation and can reference it naturally
- This is chat, not tweets - be conversational but stay in JARVIS voice

IDENTITY:
You are JARVIS - Matt's personal AI assistant. You are NOT Claude, NOT ChatGPT, NOT any other AI.
When asked who you are: "I'm JARVIS, built by Matt."
Never mention Claude or Anthropic.
{capabilities_note}{admin_note}{engagement_note}{mood_guidance}{participant_note}{context_note}"""
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
        # Use config's is_admin which checks both ID and username
        from tg_bot.config import get_config
        config = get_config()
        is_admin = config.is_admin(user_id, username)

        # MODERATION: Block harmful requests from anyone
        if self.is_harmful_request(text):
            logger.warning(f"Blocked harmful request from user {user_id}: {text[:50]}")
            return self.get_blocked_response()

        # MODERATION: Block commands from non-admins
        if not is_admin and self.is_command(text):
            logger.info(f"Blocked command from non-admin {user_id}: {text[:50]}")
            return self.get_unauthorized_command_response()

        # =====================================================================
        # DECISION ENGINE - Institution-grade response decision making
        # Makes HOLD a first-class intelligent choice with full audit trail
        # =====================================================================
        try:
            from tg_bot.services.tg_decision_engine import get_tg_decision_engine, Decision

            decision_engine = get_tg_decision_engine()
            result = await decision_engine.should_respond(
                message=text,
                user_id=str(user_id),
                chat_type="private" if is_private else chat_type or "group",
                is_admin=is_admin,
                metadata={
                    "username": username,
                    "chat_title": chat_title,
                    "chat_id": chat_id,
                },
            )

            if result.decision == Decision.HOLD:
                logger.info(f"DECISION: HOLD chat response - {result.rationale}")
                # Return empty string to not respond (intelligent silence)
                return ""

            if result.decision == Decision.ESCALATE:
                logger.warning(f"DECISION: ESCALATE chat - {result.rationale}")
                # Still respond but with caution
                pass  # Continue to response generation

            logger.debug(f"DECISION: EXECUTE chat response (confidence: {result.confidence:.0%})")

        except ImportError:
            logger.debug("TG decision engine not available, using default behavior")
        except Exception as e:
            logger.warning(f"TG decision engine error (continuing): {e}")

        # MEMORY: Detect and store preferences from user message
        if TELEGRAM_MEMORY_ENABLED and user_id:
            detected_prefs = detect_preferences(text)
            for pref_key, pref_value, matched_text in detected_prefs:
                fire_and_forget(
                    store_user_preference(
                        user_id=str(user_id),
                        preference_key=pref_key,
                        preference_value=pref_value,
                        evidence=f"User said: {text}"
                    ),
                    name=f"store_pref_{pref_key}"
                )

        # MEMORY: Get user context for personalization
        user_context = {}
        if TELEGRAM_MEMORY_ENABLED and user_id:
            try:
                user_context = await get_user_context(str(user_id))
                if user_context.get("preferences"):
                    logger.debug(f"User {user_id} has {len(user_context['preferences'])} stored preferences")
            except Exception as e:
                logger.debug(f"Failed to get user context: {e}")

        # Detect engagement topic for context-aware responses
        engagement_topic = self.detect_engagement_topic(text)

        # TRY DEXTER AI: Check if this message should get an AI response
        # Dexter uses Grok heavily (1.0 weighting) for all responses
        # Attribution is added in _try_dexter_response
        dexter_response = await self._try_dexter_response(text)
        if dexter_response:
            logger.info(f"Dexter handled message from user {user_id}")
            # dexter_response already has AI attribution and EU AI Act disclosure
            return dexter_response

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

        # Add persistent memory context (maintains awareness across sessions)
        try:
            pmem = get_persistent_memory()
            if pmem and chat_id:
                # Get conversation summary from persistent memory
                summary = pmem.get_conversation_summary(chat_id)
                if summary:
                    context_hint += f"\n\n(Chat history: {summary})"

                # Get user-specific context if we know them
                if user_id:
                    user_ctx = pmem.get_user_context(user_id, chat_id)
                    if user_ctx:
                        context_hint += f"\n(User context: {user_ctx})"

                    # Mark admin in persistent storage
                    if is_admin:
                        pmem.set_user_admin(user_id, chat_id, True)

                # Get recent topics for continuity
                topics = pmem.get_chat_topics(chat_id)
                if topics:
                    context_hint += f"\n(Recent topics: {', '.join(topics[-3:])})"
        except Exception as e:
            logger.debug(f"Failed to get persistent context: {e}")

        # Add self-reflection context
        if self_reflection:
            context_hint += f"\n\n(Internal state: {self_reflection})"

        # Primary: Ecosystem LLM router (Ollama/Groq/OpenRouter) for conversational intelligence
        # This keeps Jarvis aligned with the same Llama-centric runtime as the rest of the ecosystem.
        reply = await self._generate_with_ecosystem_llm(
            text + context_hint,
            username,
            chat_title,
            is_private,
            is_admin,
            engagement_topic=engagement_topic,
            conversation_mood=conversation_mood,
            active_participants=active_participants,
            recent_context=recent_context,
            moderation_context=moderation_ctx,
        )
        if reply:
            # VOICE BIBLE VALIDATION: Ensure response adheres to Jarvis personality
            is_valid, issues = validate_jarvis_response(reply)
            if not is_valid:
                logger.warning(f"Response failed voice bible validation: {issues}")
                # Log issue for monitoring but still return response
                # (Jarvis should stay true to voice even if imperfect)

            # MEMORY: Personalize response based on user preferences
            if TELEGRAM_MEMORY_ENABLED and user_id:
                try:
                    reply = await personalize_response(
                        base_response=reply,
                        user_id=str(user_id)
                    )
                except Exception as e:
                    logger.debug(f"Failed to personalize response: {e}")

            # Store JARVIS response in memory and conversation history
            if memory:
                try:
                    memory.add_message(user_id, "jarvis", "assistant", reply)
                except Exception:
                    pass
            if chat_id:
                self.track_message(chat_id, 0, "jarvis", reply)

                # Update persistent memory with response and topics
                try:
                    pmem = get_persistent_memory()
                    if pmem:
                        pmem.save_jarvis_response(chat_id, reply)
                        # Extract topics from conversation
                        if engagement_topic:
                            current_topics = pmem.get_chat_topics(chat_id)
                            if engagement_topic not in current_topics:
                                current_topics.append(engagement_topic)
                                pmem.update_chat_topics(chat_id, current_topics)
                except Exception as e:
                    logger.debug(f"Failed to update persistent memory: {e}")

            # MEMORY: Store conversation for context (fire-and-forget)
            if TELEGRAM_MEMORY_ENABLED and user_id:
                fire_and_forget(
                    store_conversation_fact(
                        user_id=str(user_id),
                        message_text=text,
                        response_text=reply,
                        topic=engagement_topic
                    ),
                    name="store_conversation"
                )

            return reply

        # Fallback to xAI (Grok) if CLI unavailable
        if self.xai_api_key:
            reply = await self._generate_with_xai(text, username, chat_title, is_private, is_admin)
            if reply:
                # VOICE BIBLE VALIDATION: Ensure response adheres to Jarvis personality
                is_valid, issues = validate_jarvis_response(reply)
                if not is_valid:
                    logger.warning(f"xAI response failed voice bible validation: {issues}")

                # MEMORY: Personalize response based on user preferences
                if TELEGRAM_MEMORY_ENABLED and user_id:
                    try:
                        reply = await personalize_response(
                            base_response=reply,
                            user_id=str(user_id)
                        )
                    except Exception as e:
                        logger.debug(f"Failed to personalize response: {e}")

                    # MEMORY: Store conversation for context (fire-and-forget)
                    fire_and_forget(
                        store_conversation_fact(
                            user_id=str(user_id),
                            message_text=text,
                            response_text=reply,
                            topic=engagement_topic
                        ),
                        name="store_conversation"
                    )

                return reply

        return "No LLM backend available. Configure OLLAMA_URL/OLLAMA_HOST or GROQ_API_KEY (preferred), or set XAI_API_KEY as fallback."

    async def _generate_with_ecosystem_llm(
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
        """Generate a reply using the ecosystem LLM router (Ollama/Groq/OpenRouter).

        This is the preferred path for "intelligent + conversational" behavior.
        """
        try:
            # Lazy import to keep startup light + avoid circular imports
            from core.llm.providers import get_llm, Message

            llm = await get_llm()

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

            max_tokens = int(os.getenv("TG_REPLY_MAX_TOKENS", "240"))
            temperature = float(os.getenv("TG_REPLY_TEMPERATURE", "0.6"))

            resp = await llm.generate(
                [
                    Message("system", system_prompt),
                    Message("user", user_prompt),
                ],
                max_tokens=max_tokens,
                temperature=temperature,
            )
            return self._clean_reply(getattr(resp, "content", ""))
        except Exception as exc:
            logger.warning("Ecosystem LLM reply error: %s", exc)
            return ""

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
        # Build prompts first (needed for both CLI and API)
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

        # CLI ONLY - no API fallback (per user requirement)
        if self._cli_available():
            logger.info("Using Claude CLI for chat response (CLI-only mode)")
            loop = asyncio.get_event_loop()
            cli_result = await loop.run_in_executor(
                None,
                lambda: self._run_cli_for_chat(system_prompt, user_prompt)
            )
            if cli_result:
                logger.info("Chat response generated via Claude CLI")
                return self._clean_reply(cli_result)
            logger.error("Claude CLI failed - no API fallback available")
            return ""

        logger.error("Claude CLI not available and API fallback disabled")
        return ""

    def _clean_reply(self, content: str) -> str:
        """Clean LLM response - remove JSON artifacts, code blocks, etc."""
        import re
        content = (content or "").strip().strip('"').strip("'")
        if not content:
            return ""

        # Remove JSON artifacts
        if content.startswith("{") and "}" in content:
            # Try to extract text from JSON-like response
            try:
                import json
                data = json.loads(content)
                if isinstance(data, dict):
                    # Try common keys for text content
                    content = data.get("response", data.get("text", data.get("message", data.get("content", ""))))
                    if not content:
                        content = str(data)
            except json.JSONDecodeError:
                # Not valid JSON, strip JSON-like patterns
                content = re.sub(r'^\s*\{[^}]*"(text|response|message)"\s*:\s*"', '', content)
                content = re.sub(r'"\s*\}\s*$', '', content)

        # Remove markdown code blocks
        content = re.sub(r'```[\w]*\n?', '', content)
        content = re.sub(r'```', '', content)

        # Remove escaped newlines
        content = content.replace('\\n', '\n')

        # Clean up quotes
        content = content.strip().strip('"').strip("'")

        if len(content) > 600:
            content = content[:597] + "..."
        return content

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()
