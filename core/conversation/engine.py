"""
Conversation Engine - Main engine for natural conversations.

Handles:
- Multi-turn conversations
- Reference resolution
- Personality configuration
- Response generation coordination
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple
import asyncio

from .memory import ConversationMemory, MemoryType, get_memory_manager
from .intent import Intent, IntentClassifier, IntentType, get_intent_classifier
from .context import ContextManager, ContextPriority, get_context_manager


class Formality(Enum):
    """Conversation formality level."""
    CASUAL = "casual"
    NEUTRAL = "neutral"
    FORMAL = "formal"


class Verbosity(Enum):
    """Response verbosity level."""
    CONCISE = "concise"
    BALANCED = "balanced"
    VERBOSE = "verbose"


class Humor(Enum):
    """Humor frequency."""
    NEVER = "never"
    OCCASIONAL = "occasional"
    FREQUENT = "frequent"


class Proactivity(Enum):
    """Proactive suggestion level."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


@dataclass
class Personality:
    """Personality configuration for the conversation engine."""
    formality: Formality = Formality.CASUAL
    verbosity: Verbosity = Verbosity.CONCISE
    humor: Humor = Humor.OCCASIONAL
    proactivity: Proactivity = Proactivity.HIGH
    name: str = "JARVIS"

    def to_system_prompt(self) -> str:
        """Convert personality to system prompt additions."""
        parts = [f"You are {self.name}, an AI trading assistant."]

        if self.formality == Formality.CASUAL:
            parts.append("Be friendly and casual in your responses.")
        elif self.formality == Formality.FORMAL:
            parts.append("Maintain a professional and formal tone.")

        if self.verbosity == Verbosity.CONCISE:
            parts.append("Keep responses brief and to the point.")
        elif self.verbosity == Verbosity.VERBOSE:
            parts.append("Provide detailed explanations when helpful.")

        if self.humor == Humor.OCCASIONAL:
            parts.append("Add occasional light humor when appropriate.")
        elif self.humor == Humor.NEVER:
            parts.append("Stay focused and professional, avoid humor.")

        if self.proactivity == Proactivity.HIGH:
            parts.append("Proactively suggest relevant actions and insights.")
        elif self.proactivity == Proactivity.LOW:
            parts.append("Only provide information when explicitly asked.")

        return " ".join(parts)


@dataclass
class ConversationConfig:
    """Configuration for the conversation engine."""
    max_history: int = 50  # Max messages in history
    max_context_tokens: int = 8000
    auto_summarize_threshold: int = 30  # Summarize after N messages
    clarification_threshold: float = 0.5  # Ask for clarification below this confidence
    personality: Personality = field(default_factory=Personality)


@dataclass
class ConversationTurn:
    """A single turn in a conversation."""
    user_message: str
    assistant_response: str
    intent: Intent
    timestamp: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)


class ConversationEngine:
    """
    Main conversation engine for JARVIS.

    Handles multi-turn conversations with context awareness,
    intent classification, and personality-based responses.
    """

    def __init__(self, config: Optional[ConversationConfig] = None):
        self.config = config or ConversationConfig()
        self.memory_manager = get_memory_manager()
        self.intent_classifier = get_intent_classifier()
        self.context_manager = get_context_manager()

        # Conversation history per user
        self.histories: Dict[str, List[ConversationTurn]] = {}

        # Response handlers by intent type
        self._intent_handlers: Dict[IntentType, Callable] = {}

        # Reference tracking (for "that token", "the other one", etc.)
        self._references: Dict[str, Dict[str, Any]] = {}

    def configure(
        self,
        formality: Optional[str] = None,
        verbosity: Optional[str] = None,
        humor: Optional[str] = None,
        proactivity: Optional[str] = None,
    ) -> None:
        """Configure personality traits."""
        if formality:
            self.config.personality.formality = Formality(formality)
        if verbosity:
            self.config.personality.verbosity = Verbosity(verbosity)
        if humor:
            self.config.personality.humor = Humor(humor)
        if proactivity:
            self.config.personality.proactivity = Proactivity(proactivity)

    def register_handler(
        self,
        intent_type: IntentType,
        handler: Callable,
    ) -> None:
        """Register a handler for a specific intent type."""
        self._intent_handlers[intent_type] = handler

    async def process_message(
        self,
        user_id: str,
        message: str,
        platform: str = "web",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Process a user message and generate a response.

        Returns:
            Dict with response, intent, suggestions, and metadata
        """
        # Classify intent
        intent = self.intent_classifier.classify(message)

        # Resolve references
        resolved_message = self._resolve_references(user_id, message, intent)

        # Update context
        self.context_manager.add_message(
            user_id,
            resolved_message,
            role="user",
            priority=ContextPriority.HIGH if intent.is_trading else ContextPriority.MEDIUM,
        )

        # Store in memory
        memory = self.memory_manager.get_user_memory(user_id)
        memory.add(
            f"User said: {resolved_message}",
            MemoryType.SHORT_TERM,
            {"intent": intent.intent_type.value, "platform": platform},
        )

        # Check if clarification needed
        if intent.needs_clarification:
            response = self._generate_clarification(intent)
        else:
            # Generate response based on intent
            response = await self._generate_response(user_id, intent, metadata or {})

        # Update references
        self._update_references(user_id, intent)

        # Add assistant response to context
        self.context_manager.add_message(
            user_id,
            response["text"],
            role="assistant",
        )

        # Store turn in history
        turn = ConversationTurn(
            user_message=message,
            assistant_response=response["text"],
            intent=intent,
            metadata=metadata or {},
        )
        self._add_to_history(user_id, turn)

        # Get suggestions
        suggestions = self.intent_classifier.get_suggested_responses(intent)

        return {
            "response": response["text"],
            "intent": intent.to_dict(),
            "suggestions": suggestions,
            "actions": response.get("actions", []),
            "metadata": {
                "platform": platform,
                "confidence": intent.confidence,
                "turn_count": len(self.histories.get(user_id, [])),
            }
        }

    def _resolve_references(
        self,
        user_id: str,
        message: str,
        intent: Intent,
    ) -> str:
        """Resolve references like 'that token', 'the other one'."""
        refs = self._references.get(user_id, {})

        # Common reference patterns
        reference_patterns = [
            ("that token", "last_token"),
            ("the same token", "last_token"),
            ("that one", "last_token"),
            ("the other one", "alternative_token"),
            ("it", "last_subject"),
        ]

        resolved = message
        for pattern, ref_key in reference_patterns:
            if pattern in message.lower() and ref_key in refs:
                resolved = message.lower().replace(
                    pattern,
                    refs[ref_key]
                )

        return resolved

    def _update_references(self, user_id: str, intent: Intent) -> None:
        """Update reference tracking based on intent."""
        if user_id not in self._references:
            self._references[user_id] = {}

        # Track tokens mentioned
        if "tokens" in intent.entities:
            tokens = intent.entities["tokens"]
            if tokens:
                # Store last mentioned token
                if len(tokens) >= 1:
                    self._references[user_id]["last_token"] = tokens[0]
                if len(tokens) >= 2:
                    self._references[user_id]["alternative_token"] = tokens[1]

        # Track last subject based on intent
        if intent.is_trading:
            self._references[user_id]["last_subject"] = "trading"
        elif intent.is_staking:
            self._references[user_id]["last_subject"] = "staking"

    def _generate_clarification(self, intent: Intent) -> Dict[str, Any]:
        """Generate a clarification request."""
        if intent.alternatives:
            options = [intent.intent_type] + [a[0] for a in intent.alternatives[:2]]
            options_text = ", ".join([o.value.split(".")[-1] for o in options])
            text = f"I'm not quite sure what you mean. Did you want to: {options_text}?"
        else:
            text = "Could you please clarify what you'd like me to help you with?"

        return {
            "text": text,
            "actions": [],
            "needs_clarification": True,
        }

    async def _generate_response(
        self,
        user_id: str,
        intent: Intent,
        metadata: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Generate response based on intent."""
        # Check for registered handler
        if intent.intent_type in self._intent_handlers:
            handler = self._intent_handlers[intent.intent_type]
            return await handler(user_id, intent, metadata)

        # Default responses by intent type
        default_responses = {
            IntentType.GENERAL_GREETING: {
                "text": f"Hey! I'm {self.config.personality.name}. How can I help you with trading today?",
                "actions": [],
            },
            IntentType.GENERAL_FAREWELL: {
                "text": "Take care! Feel free to come back anytime you need trading help.",
                "actions": [],
            },
            IntentType.GENERAL_THANKS: {
                "text": "You're welcome! Let me know if there's anything else.",
                "actions": [],
            },
            IntentType.TRADING_PORTFOLIO: {
                "text": "Let me fetch your portfolio...",
                "actions": [{"type": "fetch_portfolio", "user_id": user_id}],
            },
            IntentType.TRADING_PRICE: {
                "text": "Let me check the current prices...",
                "actions": [{"type": "fetch_prices", "tokens": intent.entities.get("tokens", [])}],
            },
            IntentType.TECHNICAL_HELP: {
                "text": "I can help you with trading, portfolio management, staking, and more. What would you like to know?",
                "actions": [],
            },
            IntentType.TECHNICAL_STATUS: {
                "text": "All systems operational! Trading engine is running smoothly.",
                "actions": [{"type": "check_status"}],
            },
        }

        if intent.intent_type in default_responses:
            return default_responses[intent.intent_type]

        # Generic fallback
        return {
            "text": f"I understood you want to {intent.intent_type.value.replace('.', ' ')}. Let me help you with that.",
            "actions": [],
        }

    def _add_to_history(self, user_id: str, turn: ConversationTurn) -> None:
        """Add turn to conversation history."""
        if user_id not in self.histories:
            self.histories[user_id] = []

        self.histories[user_id].append(turn)

        # Trim history if needed
        if len(self.histories[user_id]) > self.config.max_history:
            # Summarize old history
            self._summarize_history(user_id)

    def _summarize_history(self, user_id: str) -> None:
        """Summarize old conversation history."""
        if user_id not in self.histories:
            return

        history = self.histories[user_id]
        if len(history) <= self.config.auto_summarize_threshold:
            return

        # Keep recent messages
        recent = history[-self.config.auto_summarize_threshold:]

        # Create summary of old messages
        old = history[:-self.config.auto_summarize_threshold]
        summary_parts = []
        for turn in old:
            summary_parts.append(f"- {turn.intent.intent_type.value}: {turn.user_message[:50]}...")

        summary = f"Previous conversation topics:\n" + "\n".join(summary_parts)

        # Update context with summary
        self.context_manager.summarize_old_context(user_id, summary)

        # Store summary in memory
        memory = self.memory_manager.get_user_memory(user_id)
        memory.add(summary, MemoryType.EPISODIC, {"type": "conversation_summary"})

        # Update history to only recent
        self.histories[user_id] = recent

    def get_history(self, user_id: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Get conversation history for user."""
        if user_id not in self.histories:
            return []

        history = self.histories[user_id][-limit:]
        return [
            {
                "user": turn.user_message,
                "assistant": turn.assistant_response,
                "intent": turn.intent.intent_type.value,
                "timestamp": turn.timestamp.isoformat(),
            }
            for turn in history
        ]

    def clear_history(self, user_id: str) -> None:
        """Clear conversation history for user."""
        if user_id in self.histories:
            del self.histories[user_id]
        self.context_manager.clear_context(user_id)
        if user_id in self._references:
            del self._references[user_id]

    def get_stats(self) -> Dict[str, Any]:
        """Get conversation engine statistics."""
        return {
            "total_users": len(self.histories),
            "total_turns": sum(len(h) for h in self.histories.values()),
            "registered_handlers": list(self._intent_handlers.keys()),
            "personality": {
                "formality": self.config.personality.formality.value,
                "verbosity": self.config.personality.verbosity.value,
                "humor": self.config.personality.humor.value,
                "proactivity": self.config.personality.proactivity.value,
            },
            "context_stats": self.context_manager.get_stats(),
            "memory_stats": self.memory_manager.get_stats(),
        }


# Singleton instance
_conversation_engine: Optional[ConversationEngine] = None


def get_conversation_engine() -> ConversationEngine:
    """Get the global conversation engine instance."""
    global _conversation_engine
    if _conversation_engine is None:
        _conversation_engine = ConversationEngine()
    return _conversation_engine
