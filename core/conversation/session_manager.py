"""
Conversation Manager - Manage conversation contexts with TTL expiration.

Provides:
- ConversationManager: Get, create, clear contexts
- TTL-based expiration (1 hour default)
- Optional storage backend integration
"""

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
import logging

from .session_context import ConversationContext
from .session_storage import ContextStorage, InMemoryStorage


logger = logging.getLogger(__name__)


class ConversationManager:
    """
    Manager for conversation contexts with TTL expiration.

    Handles:
    - Context creation and retrieval
    - TTL-based expiration
    - Storage backend integration
    - Context listing and counting
    """

    def __init__(
        self,
        default_ttl: int = 3600,
        storage: Optional[ContextStorage] = None
    ):
        """
        Initialize ConversationManager.

        Args:
            default_ttl: Default TTL in seconds (default 1 hour)
            storage: Optional storage backend (defaults to InMemoryStorage)
        """
        self.default_ttl = default_ttl
        self._storage = storage or InMemoryStorage()
        self._contexts: Dict[str, ConversationContext] = {}

    def _make_key(self, user_id: str, chat_id: str) -> str:
        """Create context key from user_id and chat_id."""
        return f"{user_id}:{chat_id}"

    def get_context(
        self,
        user_id: str,
        chat_id: str,
        bot_name: str = "unknown"
    ) -> ConversationContext:
        """
        Get or create a conversation context.

        If the context exists and is not expired, returns it.
        If expired or doesn't exist, creates a new one.

        Args:
            user_id: User identifier
            chat_id: Chat identifier
            bot_name: Name of the bot

        Returns:
            ConversationContext for the user/chat
        """
        key = self._make_key(user_id, chat_id)

        # Check in-memory cache first
        if key in self._contexts:
            ctx = self._contexts[key]
            if not self.is_expired(ctx):
                return ctx
            else:
                # Expired - remove it
                del self._contexts[key]
                self._storage.delete_context(user_id, chat_id)

        # Try loading from storage
        ctx = self._storage.load_context(user_id, chat_id)
        if ctx is not None:
            if not self.is_expired(ctx):
                self._contexts[key] = ctx
                return ctx
            else:
                # Expired in storage - delete it
                self._storage.delete_context(user_id, chat_id)

        # Create new context
        return self.create_context(user_id, chat_id, bot_name)

    def create_context(
        self,
        user_id: str,
        chat_id: str,
        bot_name: str = "unknown",
        metadata: Optional[Dict[str, Any]] = None,
        ttl: Optional[int] = None
    ) -> ConversationContext:
        """
        Explicitly create a new conversation context.

        Replaces any existing context for the same user/chat.

        Args:
            user_id: User identifier
            chat_id: Chat identifier
            bot_name: Name of the bot
            metadata: Optional initial metadata
            ttl: Optional TTL override in seconds

        Returns:
            New ConversationContext
        """
        key = self._make_key(user_id, chat_id)

        ctx = ConversationContext(
            user_id=user_id,
            chat_id=chat_id,
            bot_name=bot_name,
            metadata=metadata or {},
            ttl=ttl
        )

        self._contexts[key] = ctx
        self._storage.save_context(ctx)

        return ctx

    def clear_context(self, user_id: str, chat_id: str) -> bool:
        """
        Clear/remove a conversation context.

        Args:
            user_id: User identifier
            chat_id: Chat identifier

        Returns:
            True if context was removed, False if not found
        """
        key = self._make_key(user_id, chat_id)

        removed = False

        if key in self._contexts:
            del self._contexts[key]
            removed = True

        if self._storage.delete_context(user_id, chat_id):
            removed = True

        return removed

    def is_expired(self, context: ConversationContext) -> bool:
        """
        Check if a context has expired based on TTL.

        Args:
            context: ConversationContext to check

        Returns:
            True if expired, False otherwise
        """
        ttl = context.ttl if context.ttl is not None else self.default_ttl
        expiry_time = context.last_activity + timedelta(seconds=ttl)
        return datetime.utcnow() > expiry_time

    def list_contexts(
        self,
        user_id: Optional[str] = None
    ) -> List[ConversationContext]:
        """
        List all active (non-expired) contexts.

        Args:
            user_id: Optional filter by user_id

        Returns:
            List of ConversationContext objects
        """
        all_contexts = list(self._contexts.values())

        # Filter out expired
        active = [ctx for ctx in all_contexts if not self.is_expired(ctx)]

        # Filter by user if specified
        if user_id is not None:
            active = [ctx for ctx in active if ctx.user_id == user_id]

        return active

    def context_count(self) -> int:
        """
        Count active (non-expired) contexts.

        Returns:
            Number of active contexts
        """
        return len(self.list_contexts())

    def cleanup_expired(self) -> int:
        """
        Remove all expired contexts.

        Returns:
            Number of contexts removed
        """
        expired_keys = []

        for key, ctx in self._contexts.items():
            if self.is_expired(ctx):
                expired_keys.append((key, ctx.user_id, ctx.chat_id))

        for key, user_id, chat_id in expired_keys:
            del self._contexts[key]
            self._storage.delete_context(user_id, chat_id)

        return len(expired_keys)

    def save_all(self) -> int:
        """
        Save all contexts to storage.

        Returns:
            Number of contexts saved
        """
        saved = 0
        for ctx in self._contexts.values():
            if self._storage.save_context(ctx):
                saved += 1
        return saved

    def get_stats(self) -> Dict[str, Any]:
        """
        Get manager statistics.

        Returns:
            Dictionary with stats
        """
        active = self.list_contexts()
        return {
            "total_contexts": len(self._contexts),
            "active_contexts": len(active),
            "default_ttl_seconds": self.default_ttl,
            "storage_type": type(self._storage).__name__
        }


# Singleton instance
_conversation_manager: Optional[ConversationManager] = None


def get_conversation_manager() -> ConversationManager:
    """Get the global conversation manager instance."""
    global _conversation_manager
    if _conversation_manager is None:
        _conversation_manager = ConversationManager()
    return _conversation_manager
