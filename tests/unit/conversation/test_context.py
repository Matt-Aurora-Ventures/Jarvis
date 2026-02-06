"""
Tests for core/conversation/session_context.py - Conversation context management.

Verifies:
- ConversationContext creation and metadata
- Message history management
- get_context_for_llm() formatting
- created_at and last_activity timestamps

Coverage Target: 90%+
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import patch


class TestConversationContextCreation:
    """Test ConversationContext initialization."""

    def test_create_context_with_required_fields(self):
        """Test creating context with user_id, chat_id, bot_name."""
        from core.conversation.session_context import ConversationContext

        ctx = ConversationContext(
            user_id="user_123",
            chat_id="chat_456",
            bot_name="jarvis"
        )

        assert ctx.user_id == "user_123"
        assert ctx.chat_id == "chat_456"
        assert ctx.bot_name == "jarvis"

    def test_context_has_empty_history_initially(self):
        """Test that new context has empty history."""
        from core.conversation.session_context import ConversationContext

        ctx = ConversationContext(
            user_id="user_123",
            chat_id="chat_456",
            bot_name="jarvis"
        )

        assert ctx.history == []
        assert len(ctx.history) == 0

    def test_context_has_empty_metadata_initially(self):
        """Test that new context has empty metadata dict."""
        from core.conversation.session_context import ConversationContext

        ctx = ConversationContext(
            user_id="user_123",
            chat_id="chat_456",
            bot_name="jarvis"
        )

        assert ctx.metadata == {}
        assert isinstance(ctx.metadata, dict)

    def test_context_has_created_at_timestamp(self):
        """Test that context has created_at timestamp."""
        from core.conversation.session_context import ConversationContext

        before = datetime.utcnow()
        ctx = ConversationContext(
            user_id="user_123",
            chat_id="chat_456",
            bot_name="jarvis"
        )
        after = datetime.utcnow()

        assert ctx.created_at is not None
        assert before <= ctx.created_at <= after

    def test_context_has_last_activity_timestamp(self):
        """Test that context has last_activity matching created_at initially."""
        from core.conversation.session_context import ConversationContext

        ctx = ConversationContext(
            user_id="user_123",
            chat_id="chat_456",
            bot_name="jarvis"
        )

        assert ctx.last_activity is not None
        assert ctx.last_activity == ctx.created_at

    def test_context_with_initial_metadata(self):
        """Test creating context with initial metadata."""
        from core.conversation.session_context import ConversationContext

        ctx = ConversationContext(
            user_id="user_123",
            chat_id="chat_456",
            bot_name="jarvis",
            metadata={"platform": "telegram", "language": "en"}
        )

        assert ctx.metadata["platform"] == "telegram"
        assert ctx.metadata["language"] == "en"


class TestAddMessage:
    """Test add_message functionality."""

    def test_add_user_message(self):
        """Test adding a user message."""
        from core.conversation.session_context import ConversationContext

        ctx = ConversationContext(
            user_id="user_123",
            chat_id="chat_456",
            bot_name="jarvis"
        )

        ctx.add_message("user", "Hello!")

        assert len(ctx.history) == 1
        assert ctx.history[0]["role"] == "user"
        assert ctx.history[0]["content"] == "Hello!"

    def test_add_assistant_message(self):
        """Test adding an assistant message."""
        from core.conversation.session_context import ConversationContext

        ctx = ConversationContext(
            user_id="user_123",
            chat_id="chat_456",
            bot_name="jarvis"
        )

        ctx.add_message("assistant", "Hi there! How can I help?")

        assert len(ctx.history) == 1
        assert ctx.history[0]["role"] == "assistant"

    def test_add_system_message(self):
        """Test adding a system message."""
        from core.conversation.session_context import ConversationContext

        ctx = ConversationContext(
            user_id="user_123",
            chat_id="chat_456",
            bot_name="jarvis"
        )

        ctx.add_message("system", "You are a helpful assistant.")

        assert len(ctx.history) == 1
        assert ctx.history[0]["role"] == "system"

    def test_add_message_updates_last_activity(self):
        """Test that adding message updates last_activity timestamp."""
        from core.conversation.session_context import ConversationContext
        import time

        ctx = ConversationContext(
            user_id="user_123",
            chat_id="chat_456",
            bot_name="jarvis"
        )

        initial_activity = ctx.last_activity
        time.sleep(0.01)  # Small delay
        ctx.add_message("user", "Hello!")

        assert ctx.last_activity > initial_activity

    def test_add_message_includes_timestamp(self):
        """Test that each message includes a timestamp."""
        from core.conversation.session_context import ConversationContext

        ctx = ConversationContext(
            user_id="user_123",
            chat_id="chat_456",
            bot_name="jarvis"
        )

        ctx.add_message("user", "Hello!")

        assert "timestamp" in ctx.history[0]
        assert isinstance(ctx.history[0]["timestamp"], str)

    def test_multiple_messages_maintain_order(self):
        """Test that multiple messages maintain chronological order."""
        from core.conversation.session_context import ConversationContext

        ctx = ConversationContext(
            user_id="user_123",
            chat_id="chat_456",
            bot_name="jarvis"
        )

        ctx.add_message("user", "Hello!")
        ctx.add_message("assistant", "Hi there!")
        ctx.add_message("user", "How are you?")

        assert len(ctx.history) == 3
        assert ctx.history[0]["content"] == "Hello!"
        assert ctx.history[1]["content"] == "Hi there!"
        assert ctx.history[2]["content"] == "How are you?"


class TestGetContextForLLM:
    """Test get_context_for_llm() formatting."""

    def test_get_context_empty_history(self):
        """Test get_context_for_llm with empty history."""
        from core.conversation.session_context import ConversationContext

        ctx = ConversationContext(
            user_id="user_123",
            chat_id="chat_456",
            bot_name="jarvis"
        )

        result = ctx.get_context_for_llm()

        assert isinstance(result, str)
        assert result == ""

    def test_get_context_single_message(self):
        """Test get_context_for_llm with single message."""
        from core.conversation.session_context import ConversationContext

        ctx = ConversationContext(
            user_id="user_123",
            chat_id="chat_456",
            bot_name="jarvis"
        )
        ctx.add_message("user", "Hello!")

        result = ctx.get_context_for_llm()

        assert "user:" in result.lower() or "User:" in result
        assert "Hello!" in result

    def test_get_context_conversation_flow(self):
        """Test get_context_for_llm with conversation flow."""
        from core.conversation.session_context import ConversationContext

        ctx = ConversationContext(
            user_id="user_123",
            chat_id="chat_456",
            bot_name="jarvis"
        )
        ctx.add_message("user", "What is 2+2?")
        ctx.add_message("assistant", "2+2 equals 4.")

        result = ctx.get_context_for_llm()

        assert "What is 2+2?" in result
        assert "2+2 equals 4" in result

    def test_get_context_respects_max_messages(self):
        """Test get_context_for_llm respects max_messages parameter."""
        from core.conversation.session_context import ConversationContext

        ctx = ConversationContext(
            user_id="user_123",
            chat_id="chat_456",
            bot_name="jarvis"
        )

        # Add many messages
        for i in range(10):
            ctx.add_message("user", f"Message {i}")

        result = ctx.get_context_for_llm(max_messages=3)

        # Should only include last 3 messages
        assert "Message 9" in result
        assert "Message 8" in result
        assert "Message 7" in result
        assert "Message 0" not in result


class TestContextSerialization:
    """Test context serialization."""

    def test_to_dict(self):
        """Test converting context to dictionary."""
        from core.conversation.session_context import ConversationContext

        ctx = ConversationContext(
            user_id="user_123",
            chat_id="chat_456",
            bot_name="jarvis",
            metadata={"platform": "telegram"}
        )
        ctx.add_message("user", "Hello!")

        d = ctx.to_dict()

        assert d["user_id"] == "user_123"
        assert d["chat_id"] == "chat_456"
        assert d["bot_name"] == "jarvis"
        assert d["metadata"]["platform"] == "telegram"
        assert len(d["history"]) == 1
        assert "created_at" in d
        assert "last_activity" in d

    def test_from_dict(self):
        """Test creating context from dictionary."""
        from core.conversation.session_context import ConversationContext

        data = {
            "user_id": "user_123",
            "chat_id": "chat_456",
            "bot_name": "jarvis",
            "history": [
                {"role": "user", "content": "Hello!", "timestamp": "2026-01-01T12:00:00"}
            ],
            "metadata": {"platform": "telegram"},
            "created_at": "2026-01-01T12:00:00",
            "last_activity": "2026-01-01T12:00:00"
        }

        ctx = ConversationContext.from_dict(data)

        assert ctx.user_id == "user_123"
        assert ctx.chat_id == "chat_456"
        assert ctx.bot_name == "jarvis"
        assert len(ctx.history) == 1


class TestContextKey:
    """Test context key generation."""

    def test_context_key_format(self):
        """Test that context key is generated correctly."""
        from core.conversation.session_context import ConversationContext

        ctx = ConversationContext(
            user_id="user_123",
            chat_id="chat_456",
            bot_name="jarvis"
        )

        key = ctx.get_key()

        assert key == "user_123:chat_456"

    def test_context_key_different_users(self):
        """Test that different users have different keys."""
        from core.conversation.session_context import ConversationContext

        ctx1 = ConversationContext(user_id="user_1", chat_id="chat_1", bot_name="bot")
        ctx2 = ConversationContext(user_id="user_2", chat_id="chat_1", bot_name="bot")

        assert ctx1.get_key() != ctx2.get_key()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
