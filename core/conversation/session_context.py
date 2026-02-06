"""
Conversation Context - Track individual conversation sessions.

Provides:
- ConversationContext: Holds user_id, chat_id, bot_name, history, metadata
- Message history management with timestamps
- get_context_for_llm() for formatted output
- Serialization to/from dict for storage
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass
class ConversationContext:
    """
    A single conversation context for a user/chat session.

    Attributes:
        user_id: Unique identifier for the user
        chat_id: Unique identifier for the chat/channel
        bot_name: Name of the bot handling this conversation
        history: List of message dicts with role, content, timestamp
        metadata: Additional context metadata
        created_at: When the context was created
        last_activity: When the context was last active
        ttl: Optional TTL override in seconds (None uses manager default)
    """
    user_id: str
    chat_id: str
    bot_name: str
    history: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)
    last_activity: datetime = field(default=None)
    ttl: Optional[int] = None

    def __post_init__(self):
        """Initialize last_activity to created_at if not set."""
        if self.last_activity is None:
            self.last_activity = self.created_at

    def add_message(self, role: str, content: str) -> None:
        """
        Add a message to the conversation history.

        Args:
            role: Message role (user, assistant, system)
            content: Message content
        """
        message = {
            "role": role,
            "content": content,
            "timestamp": datetime.utcnow().isoformat()
        }
        self.history.append(message)
        self.last_activity = datetime.utcnow()

    def get_context_for_llm(self, max_messages: Optional[int] = None) -> str:
        """
        Get formatted conversation context for LLM consumption.

        Args:
            max_messages: Maximum number of messages to include (from end)

        Returns:
            Formatted string with conversation history
        """
        if not self.history:
            return ""

        messages = self.history
        if max_messages is not None and max_messages > 0:
            messages = self.history[-max_messages:]

        formatted_lines = []
        for msg in messages:
            role = msg["role"].capitalize()
            content = msg["content"]
            formatted_lines.append(f"{role}: {content}")

        return "\n".join(formatted_lines)

    def get_key(self) -> str:
        """
        Get unique key for this context (user_id:chat_id).

        Returns:
            String key combining user_id and chat_id
        """
        return f"{self.user_id}:{self.chat_id}"

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert context to dictionary for serialization.

        Returns:
            Dictionary representation of the context
        """
        return {
            "user_id": self.user_id,
            "chat_id": self.chat_id,
            "bot_name": self.bot_name,
            "history": self.history,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
            "last_activity": self.last_activity.isoformat(),
            "ttl": self.ttl
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ConversationContext":
        """
        Create context from dictionary.

        Args:
            data: Dictionary with context data

        Returns:
            New ConversationContext instance
        """
        created_at = data.get("created_at")
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at)
        elif created_at is None:
            created_at = datetime.utcnow()

        last_activity = data.get("last_activity")
        if isinstance(last_activity, str):
            last_activity = datetime.fromisoformat(last_activity)
        elif last_activity is None:
            last_activity = created_at

        return cls(
            user_id=data["user_id"],
            chat_id=data["chat_id"],
            bot_name=data.get("bot_name", "unknown"),
            history=data.get("history", []),
            metadata=data.get("metadata", {}),
            created_at=created_at,
            last_activity=last_activity,
            ttl=data.get("ttl")
        )

    def clear_history(self) -> None:
        """Clear all message history."""
        self.history = []
        self.last_activity = datetime.utcnow()

    def message_count(self) -> int:
        """Get the number of messages in history."""
        return len(self.history)

    def __repr__(self) -> str:
        return (
            f"ConversationContext(user_id={self.user_id!r}, "
            f"chat_id={self.chat_id!r}, bot_name={self.bot_name!r}, "
            f"messages={len(self.history)})"
        )
