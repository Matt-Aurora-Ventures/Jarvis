"""
Tests for core/conversation/session_manager.py - Conversation manager.

Verifies:
- get_context() retrieval or creation
- create_context() explicit creation
- clear_context() cleanup
- TTL expiration (1 hour default)

Coverage Target: 90%+
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
import time


class TestConversationManagerInit:
    """Test ConversationManager initialization."""

    def test_init_with_defaults(self):
        """Test initialization with default parameters."""
        from core.conversation.session_manager import ConversationManager

        manager = ConversationManager()

        assert manager.default_ttl == 3600  # 1 hour default

    def test_init_with_custom_ttl(self):
        """Test initialization with custom TTL."""
        from core.conversation.session_manager import ConversationManager

        manager = ConversationManager(default_ttl=7200)  # 2 hours

        assert manager.default_ttl == 7200

    def test_init_with_storage(self):
        """Test initialization with storage backend."""
        from core.conversation.session_manager import ConversationManager
        from core.conversation.session_storage import InMemoryStorage

        storage = InMemoryStorage()
        manager = ConversationManager(storage=storage)

        assert manager._storage is storage


class TestGetContext:
    """Test get_context functionality."""

    def test_get_context_creates_new_if_not_exists(self):
        """Test that get_context creates new context if none exists."""
        from core.conversation.session_manager import ConversationManager

        manager = ConversationManager()
        ctx = manager.get_context("user_123", "chat_456")

        assert ctx is not None
        assert ctx.user_id == "user_123"
        assert ctx.chat_id == "chat_456"

    def test_get_context_returns_existing(self):
        """Test that get_context returns existing context."""
        from core.conversation.session_manager import ConversationManager

        manager = ConversationManager()

        # Create first
        ctx1 = manager.get_context("user_123", "chat_456")
        ctx1.add_message("user", "Hello!")

        # Get again
        ctx2 = manager.get_context("user_123", "chat_456")

        assert ctx2 is ctx1
        assert len(ctx2.history) == 1

    def test_get_context_with_bot_name(self):
        """Test get_context with bot_name parameter."""
        from core.conversation.session_manager import ConversationManager

        manager = ConversationManager()
        ctx = manager.get_context("user_123", "chat_456", bot_name="jarvis")

        assert ctx.bot_name == "jarvis"

    def test_get_context_different_chats_isolated(self):
        """Test that different chats have isolated contexts."""
        from core.conversation.session_manager import ConversationManager

        manager = ConversationManager()

        ctx1 = manager.get_context("user_123", "chat_1")
        ctx1.add_message("user", "Message in chat 1")

        ctx2 = manager.get_context("user_123", "chat_2")

        assert len(ctx2.history) == 0


class TestCreateContext:
    """Test create_context functionality."""

    def test_create_context_explicit(self):
        """Test explicitly creating a new context."""
        from core.conversation.session_manager import ConversationManager

        manager = ConversationManager()
        ctx = manager.create_context("user_123", "chat_456", bot_name="jarvis")

        assert ctx is not None
        assert ctx.user_id == "user_123"
        assert ctx.chat_id == "chat_456"
        assert ctx.bot_name == "jarvis"

    def test_create_context_replaces_existing(self):
        """Test that create_context replaces existing context."""
        from core.conversation.session_manager import ConversationManager

        manager = ConversationManager()

        # Create first with history
        ctx1 = manager.get_context("user_123", "chat_456")
        ctx1.add_message("user", "Old message")

        # Force create new
        ctx2 = manager.create_context("user_123", "chat_456")

        assert len(ctx2.history) == 0
        assert ctx2 is not ctx1

    def test_create_context_with_metadata(self):
        """Test create_context with initial metadata."""
        from core.conversation.session_manager import ConversationManager

        manager = ConversationManager()
        ctx = manager.create_context(
            "user_123",
            "chat_456",
            metadata={"source": "telegram"}
        )

        assert ctx.metadata["source"] == "telegram"


class TestClearContext:
    """Test clear_context functionality."""

    def test_clear_context_removes_context(self):
        """Test that clear_context removes the context."""
        from core.conversation.session_manager import ConversationManager

        manager = ConversationManager()

        ctx1 = manager.get_context("user_123", "chat_456")
        ctx1.add_message("user", "Hello!")

        manager.clear_context("user_123", "chat_456")

        # Getting context now should create a new one
        ctx2 = manager.get_context("user_123", "chat_456")
        assert len(ctx2.history) == 0

    def test_clear_context_nonexistent_no_error(self):
        """Test that clearing nonexistent context doesn't error."""
        from core.conversation.session_manager import ConversationManager

        manager = ConversationManager()

        # Should not raise
        manager.clear_context("nonexistent_user", "nonexistent_chat")

    def test_clear_context_returns_success(self):
        """Test that clear_context returns True on success."""
        from core.conversation.session_manager import ConversationManager

        manager = ConversationManager()
        manager.get_context("user_123", "chat_456")

        result = manager.clear_context("user_123", "chat_456")

        assert result is True


class TestTTLExpiration:
    """Test TTL expiration functionality."""

    def test_expired_context_recreated(self):
        """Test that expired context is recreated on access."""
        from core.conversation.session_manager import ConversationManager
        from core.conversation.session_context import ConversationContext

        manager = ConversationManager(default_ttl=1)  # 1 second TTL

        ctx1 = manager.get_context("user_123", "chat_456")
        ctx1.add_message("user", "Hello!")

        # Simulate expiration by manipulating last_activity
        ctx1.last_activity = datetime.utcnow() - timedelta(seconds=2)

        ctx2 = manager.get_context("user_123", "chat_456")

        # Should be a new context (expired one was removed)
        assert len(ctx2.history) == 0

    def test_is_expired_method(self):
        """Test is_expired helper method."""
        from core.conversation.session_manager import ConversationManager

        manager = ConversationManager(default_ttl=3600)

        ctx = manager.get_context("user_123", "chat_456")

        # Fresh context should not be expired
        assert manager.is_expired(ctx) is False

        # Simulate old context
        ctx.last_activity = datetime.utcnow() - timedelta(seconds=3601)
        assert manager.is_expired(ctx) is True

    def test_custom_ttl_per_context(self):
        """Test custom TTL override per context."""
        from core.conversation.session_manager import ConversationManager

        manager = ConversationManager(default_ttl=3600)

        ctx = manager.create_context("user_123", "chat_456", ttl=60)

        # Simulate 61 seconds old
        ctx.last_activity = datetime.utcnow() - timedelta(seconds=61)

        assert manager.is_expired(ctx) is True


class TestContextListing:
    """Test context listing and counting."""

    def test_list_active_contexts(self):
        """Test listing all active contexts."""
        from core.conversation.session_manager import ConversationManager

        manager = ConversationManager()

        manager.get_context("user_1", "chat_1")
        manager.get_context("user_2", "chat_2")
        manager.get_context("user_3", "chat_3")

        contexts = manager.list_contexts()

        assert len(contexts) == 3

    def test_count_contexts(self):
        """Test counting active contexts."""
        from core.conversation.session_manager import ConversationManager

        manager = ConversationManager()

        manager.get_context("user_1", "chat_1")
        manager.get_context("user_2", "chat_2")

        assert manager.context_count() == 2

    def test_list_contexts_for_user(self):
        """Test listing contexts for a specific user."""
        from core.conversation.session_manager import ConversationManager

        manager = ConversationManager()

        manager.get_context("user_1", "chat_1")
        manager.get_context("user_1", "chat_2")
        manager.get_context("user_2", "chat_3")

        user1_contexts = manager.list_contexts(user_id="user_1")

        assert len(user1_contexts) == 2


class TestCleanupExpired:
    """Test cleanup_expired functionality."""

    def test_cleanup_removes_expired(self):
        """Test that cleanup removes expired contexts."""
        from core.conversation.session_manager import ConversationManager

        manager = ConversationManager(default_ttl=1)

        ctx1 = manager.get_context("user_1", "chat_1")
        ctx2 = manager.get_context("user_2", "chat_2")

        # Expire one context
        ctx1.last_activity = datetime.utcnow() - timedelta(seconds=2)

        removed = manager.cleanup_expired()

        assert removed == 1
        assert manager.context_count() == 1

    def test_cleanup_keeps_active(self):
        """Test that cleanup keeps active contexts."""
        from core.conversation.session_manager import ConversationManager

        manager = ConversationManager(default_ttl=3600)

        manager.get_context("user_1", "chat_1")
        manager.get_context("user_2", "chat_2")

        removed = manager.cleanup_expired()

        assert removed == 0
        assert manager.context_count() == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
