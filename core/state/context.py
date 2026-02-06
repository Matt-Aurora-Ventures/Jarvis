"""
Conversation Context

Manages conversation state and data for multi-turn bot interactions.

Example:
    ctx = ConversationContext(user_id="123", chat_id="456")
    ctx.state = "awaiting_confirmation"
    ctx.data["token"] = "SOL"
    ctx.data["amount"] = 100

    # Check expiration
    if ctx.is_expired():
        ctx = ConversationContext(user_id="123", chat_id="456")  # Fresh context
"""

from datetime import datetime
from typing import Any, Dict, Optional


class ConversationContext:
    """
    Context object for storing conversation state and data.

    Attributes:
        user_id: Unique identifier for the user
        chat_id: Unique identifier for the chat/conversation
        state: Current state name in the conversation flow
        data: Dictionary for storing arbitrary conversation data
        created_at: When the context was created
        updated_at: When the context was last updated
        ttl_seconds: Time-to-live in seconds (default: 3600 = 1 hour)
    """

    DEFAULT_TTL = 3600  # 1 hour

    def __init__(
        self,
        user_id: str,
        chat_id: str,
        state: Optional[str] = None,
        ttl_seconds: int = DEFAULT_TTL,
        data: Optional[Dict[str, Any]] = None,
        created_at: Optional[datetime] = None,
        updated_at: Optional[datetime] = None,
    ):
        """
        Initialize conversation context.

        Args:
            user_id: Unique user identifier
            chat_id: Unique chat/conversation identifier
            state: Initial state name (default: None)
            ttl_seconds: Time-to-live in seconds (default: 3600)
            data: Initial data dictionary (default: empty dict)
            created_at: Creation timestamp (default: now)
            updated_at: Last update timestamp (default: now)
        """
        self.user_id = user_id
        self.chat_id = chat_id
        self._state = state
        self.ttl_seconds = ttl_seconds
        self.data: Dict[str, Any] = data if data is not None else {}

        now = datetime.utcnow()
        self.created_at = created_at if created_at is not None else now
        self.updated_at = updated_at if updated_at is not None else now

    @property
    def state(self) -> Optional[str]:
        """Get current state."""
        return self._state

    @state.setter
    def state(self, value: Optional[str]) -> None:
        """Set state (does not update timestamp, use set_state for that)."""
        self._state = value

    def set_state(self, state: Optional[str]) -> None:
        """
        Set state and update the timestamp.

        Args:
            state: New state name
        """
        self._state = state
        self.updated_at = datetime.utcnow()

    @property
    def key(self) -> str:
        """
        Generate a unique key for this context.

        Returns:
            String key combining user_id and chat_id
        """
        return f"{self.user_id}:{self.chat_id}"

    def is_expired(self) -> bool:
        """
        Check if the context has expired based on TTL.

        Returns:
            True if expired, False otherwise
        """
        elapsed = (datetime.utcnow() - self.updated_at).total_seconds()
        return elapsed > self.ttl_seconds

    def touch(self) -> None:
        """Update the timestamp to extend TTL."""
        self.updated_at = datetime.utcnow()

    def to_dict(self) -> Dict[str, Any]:
        """
        Serialize context to dictionary.

        Returns:
            Dictionary representation of the context
        """
        return {
            "user_id": self.user_id,
            "chat_id": self.chat_id,
            "state": self._state,
            "data": self.data,
            "ttl_seconds": self.ttl_seconds,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ConversationContext":
        """
        Deserialize context from dictionary.

        Args:
            data: Dictionary representation of a context

        Returns:
            ConversationContext instance
        """
        created_at = None
        updated_at = None

        if "created_at" in data:
            created_at = datetime.fromisoformat(data["created_at"])
        if "updated_at" in data:
            updated_at = datetime.fromisoformat(data["updated_at"])

        return cls(
            user_id=data["user_id"],
            chat_id=data["chat_id"],
            state=data.get("state"),
            ttl_seconds=data.get("ttl_seconds", cls.DEFAULT_TTL),
            data=data.get("data", {}),
            created_at=created_at,
            updated_at=updated_at,
        )

    def __repr__(self) -> str:
        return (
            f"ConversationContext(user_id={self.user_id!r}, "
            f"chat_id={self.chat_id!r}, state={self._state!r})"
        )
