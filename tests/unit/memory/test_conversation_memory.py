"""
Tests for core/memory/conversation.py - Conversation memory system.

Verifies:
- Message addition and retrieval
- History management with limits
- Token counting
- Summarization
- Clear functionality
- Metadata handling

Coverage Target: 60%+ with ~40 tests
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
from typing import Dict, Any


# ==============================================================================
# Test Fixtures
# ==============================================================================

@pytest.fixture
def mock_storage():
    """Create a mock storage backend."""
    storage = Mock()
    storage.save_message = Mock(return_value="msg_123")
    storage.get_messages = Mock(return_value=[])
    storage.delete_messages = Mock(return_value=True)
    storage.get_message_count = Mock(return_value=0)
    return storage


@pytest.fixture
def mock_summarizer():
    """Create a mock summarizer."""
    summarizer = Mock()
    summarizer.summarize_conversation = Mock(return_value="Summary of conversation")
    return summarizer


@pytest.fixture
def sample_message():
    """Create a sample message dict."""
    return {
        "id": "msg_001",
        "role": "user",
        "content": "Hello, how are you?",
        "timestamp": datetime.utcnow().isoformat(),
        "metadata": {"source": "telegram"}
    }


@pytest.fixture
def sample_messages():
    """Create a list of sample messages."""
    now = datetime.utcnow()
    return [
        {
            "id": "msg_001",
            "role": "user",
            "content": "Hello",
            "timestamp": (now - timedelta(minutes=5)).isoformat(),
            "metadata": {}
        },
        {
            "id": "msg_002",
            "role": "assistant",
            "content": "Hi there! How can I help you today?",
            "timestamp": (now - timedelta(minutes=4)).isoformat(),
            "metadata": {}
        },
        {
            "id": "msg_003",
            "role": "user",
            "content": "What's the weather like?",
            "timestamp": (now - timedelta(minutes=3)).isoformat(),
            "metadata": {}
        },
    ]


# ==============================================================================
# Message Class Tests
# ==============================================================================

class TestMessage:
    """Test Message dataclass."""

    def test_message_creation(self):
        """Test creating a Message with required fields."""
        from core.memory.conversation import Message

        msg = Message(
            role="user",
            content="Hello world"
        )

        assert msg.role == "user"
        assert msg.content == "Hello world"
        assert msg.id is not None
        assert msg.timestamp is not None

    def test_message_with_metadata(self):
        """Test creating a Message with metadata."""
        from core.memory.conversation import Message

        msg = Message(
            role="assistant",
            content="I can help with that",
            metadata={"model": "claude-3", "tokens": 50}
        )

        assert msg.metadata["model"] == "claude-3"
        assert msg.metadata["tokens"] == 50

    def test_message_with_custom_id(self):
        """Test creating a Message with custom ID."""
        from core.memory.conversation import Message

        msg = Message(
            id="custom_123",
            role="user",
            content="Test message"
        )

        assert msg.id == "custom_123"

    def test_message_to_dict(self):
        """Test converting Message to dictionary."""
        from core.memory.conversation import Message

        msg = Message(
            role="user",
            content="Hello",
            metadata={"source": "telegram"}
        )

        d = msg.to_dict()

        assert d["role"] == "user"
        assert d["content"] == "Hello"
        assert d["metadata"]["source"] == "telegram"
        assert "id" in d
        assert "timestamp" in d

    def test_message_from_dict(self):
        """Test creating Message from dictionary."""
        from core.memory.conversation import Message

        data = {
            "id": "msg_123",
            "role": "assistant",
            "content": "Response text",
            "timestamp": datetime.utcnow().isoformat(),
            "metadata": {"tokens": 25}
        }

        msg = Message.from_dict(data)

        assert msg.id == "msg_123"
        assert msg.role == "assistant"
        assert msg.content == "Response text"
        assert msg.metadata["tokens"] == 25


# ==============================================================================
# ConversationMemory Initialization Tests
# ==============================================================================

class TestConversationMemoryInit:
    """Test ConversationMemory initialization."""

    def test_init_with_user_id(self, mock_storage):
        """Test initialization with user ID."""
        from core.memory.conversation import ConversationMemory

        memory = ConversationMemory(
            user_id="user_123",
            storage=mock_storage
        )

        assert memory.user_id == "user_123"
        assert memory._storage is mock_storage

    def test_init_with_default_storage(self):
        """Test initialization with default storage."""
        with patch('core.memory.conversation.get_default_storage') as mock_get:
            mock_storage = Mock()
            mock_get.return_value = mock_storage

            from core.memory.conversation import ConversationMemory

            memory = ConversationMemory(user_id="user_123")

            mock_get.assert_called_once()
            assert memory._storage is mock_storage

    def test_init_with_max_messages(self, mock_storage):
        """Test initialization with max messages limit."""
        from core.memory.conversation import ConversationMemory

        memory = ConversationMemory(
            user_id="user_123",
            storage=mock_storage,
            max_messages=100
        )

        assert memory.max_messages == 100

    def test_init_with_summarizer(self, mock_storage, mock_summarizer):
        """Test initialization with custom summarizer."""
        from core.memory.conversation import ConversationMemory

        memory = ConversationMemory(
            user_id="user_123",
            storage=mock_storage,
            summarizer=mock_summarizer
        )

        assert memory._summarizer is mock_summarizer


# ==============================================================================
# Add Message Tests
# ==============================================================================

class TestAddMessage:
    """Test add_message functionality."""

    def test_add_user_message(self, mock_storage):
        """Test adding a user message."""
        from core.memory.conversation import ConversationMemory

        memory = ConversationMemory(user_id="user_123", storage=mock_storage)
        msg_id = memory.add_message("user", "Hello!")

        assert msg_id is not None
        mock_storage.save_message.assert_called_once()

    def test_add_assistant_message(self, mock_storage):
        """Test adding an assistant message."""
        from core.memory.conversation import ConversationMemory

        memory = ConversationMemory(user_id="user_123", storage=mock_storage)
        msg_id = memory.add_message("assistant", "Hi there!")

        assert msg_id is not None
        call_args = mock_storage.save_message.call_args
        assert call_args is not None

    def test_add_message_with_metadata(self, mock_storage):
        """Test adding a message with metadata."""
        from core.memory.conversation import ConversationMemory

        memory = ConversationMemory(user_id="user_123", storage=mock_storage)
        metadata = {"source": "telegram", "chat_id": 12345}
        msg_id = memory.add_message("user", "Hello!", metadata=metadata)

        assert msg_id is not None
        call_args = mock_storage.save_message.call_args
        saved_msg = call_args[0][1]  # Second positional arg is message
        assert saved_msg.metadata["source"] == "telegram"

    def test_add_message_validates_role(self, mock_storage):
        """Test that add_message validates role."""
        from core.memory.conversation import ConversationMemory

        memory = ConversationMemory(user_id="user_123", storage=mock_storage)

        with pytest.raises(ValueError, match="Invalid role"):
            memory.add_message("invalid_role", "Content")

    def test_add_message_validates_empty_content(self, mock_storage):
        """Test that add_message validates empty content."""
        from core.memory.conversation import ConversationMemory

        memory = ConversationMemory(user_id="user_123", storage=mock_storage)

        with pytest.raises(ValueError, match="Content cannot be empty"):
            memory.add_message("user", "")

    def test_add_system_message(self, mock_storage):
        """Test adding a system message."""
        from core.memory.conversation import ConversationMemory

        memory = ConversationMemory(user_id="user_123", storage=mock_storage)
        msg_id = memory.add_message("system", "You are a helpful assistant.")

        assert msg_id is not None


# ==============================================================================
# Get History Tests
# ==============================================================================

class TestGetHistory:
    """Test get_history functionality."""

    def test_get_history_default_limit(self, mock_storage, sample_messages):
        """Test getting history with default limit."""
        from core.memory.conversation import ConversationMemory, Message

        mock_storage.get_messages.return_value = [
            Message.from_dict(m) for m in sample_messages
        ]

        memory = ConversationMemory(user_id="user_123", storage=mock_storage)
        history = memory.get_history()

        assert len(history) == 3
        mock_storage.get_messages.assert_called_once()

    def test_get_history_with_limit(self, mock_storage, sample_messages):
        """Test getting history with custom limit."""
        from core.memory.conversation import ConversationMemory, Message

        mock_storage.get_messages.return_value = [
            Message.from_dict(m) for m in sample_messages[:2]
        ]

        memory = ConversationMemory(user_id="user_123", storage=mock_storage)
        history = memory.get_history(limit=2)

        assert len(history) == 2
        mock_storage.get_messages.assert_called_with("user_123", limit=2)

    def test_get_history_empty(self, mock_storage):
        """Test getting history when empty."""
        from core.memory.conversation import ConversationMemory

        mock_storage.get_messages.return_value = []

        memory = ConversationMemory(user_id="user_123", storage=mock_storage)
        history = memory.get_history()

        assert history == []

    def test_get_history_returns_message_objects(self, mock_storage, sample_messages):
        """Test that get_history returns Message objects."""
        from core.memory.conversation import ConversationMemory, Message

        mock_storage.get_messages.return_value = [
            Message.from_dict(m) for m in sample_messages
        ]

        memory = ConversationMemory(user_id="user_123", storage=mock_storage)
        history = memory.get_history()

        for msg in history:
            assert isinstance(msg, Message)


# ==============================================================================
# Summarize Tests
# ==============================================================================

class TestSummarize:
    """Test summarize functionality."""

    def test_summarize_conversation(self, mock_storage, mock_summarizer, sample_messages):
        """Test summarizing conversation."""
        from core.memory.conversation import ConversationMemory, Message

        mock_storage.get_messages.return_value = [
            Message.from_dict(m) for m in sample_messages
        ]

        memory = ConversationMemory(
            user_id="user_123",
            storage=mock_storage,
            summarizer=mock_summarizer
        )
        summary = memory.summarize()

        assert summary == "Summary of conversation"
        mock_summarizer.summarize_conversation.assert_called_once()

    def test_summarize_empty_history(self, mock_storage, mock_summarizer):
        """Test summarizing empty history."""
        from core.memory.conversation import ConversationMemory

        mock_storage.get_messages.return_value = []

        memory = ConversationMemory(
            user_id="user_123",
            storage=mock_storage,
            summarizer=mock_summarizer
        )
        summary = memory.summarize()

        assert summary == ""  # Empty summary for empty history

    def test_summarize_without_summarizer(self, mock_storage, sample_messages):
        """Test summarizing without custom summarizer uses default."""
        from core.memory.conversation import ConversationMemory, Message

        mock_storage.get_messages.return_value = [
            Message.from_dict(m) for m in sample_messages
        ]

        with patch('core.memory.conversation.get_default_summarizer') as mock_get:
            mock_sum = Mock()
            mock_sum.summarize_conversation.return_value = "Default summary"
            mock_get.return_value = mock_sum

            memory = ConversationMemory(user_id="user_123", storage=mock_storage)
            summary = memory.summarize()

            assert summary == "Default summary"


# ==============================================================================
# Clear Tests
# ==============================================================================

class TestClear:
    """Test clear functionality."""

    def test_clear_all_messages(self, mock_storage):
        """Test clearing all messages."""
        from core.memory.conversation import ConversationMemory

        memory = ConversationMemory(user_id="user_123", storage=mock_storage)
        result = memory.clear()

        assert result is True
        mock_storage.delete_messages.assert_called_with("user_123")

    def test_clear_returns_success_status(self, mock_storage):
        """Test clear returns success status."""
        from core.memory.conversation import ConversationMemory

        mock_storage.delete_messages.return_value = False

        memory = ConversationMemory(user_id="user_123", storage=mock_storage)
        result = memory.clear()

        assert result is False


# ==============================================================================
# Token Count Tests
# ==============================================================================

class TestTokenCount:
    """Test token_count functionality."""

    def test_token_count_simple(self, mock_storage, sample_messages):
        """Test counting tokens in conversation."""
        from core.memory.conversation import ConversationMemory, Message

        mock_storage.get_messages.return_value = [
            Message.from_dict(m) for m in sample_messages
        ]

        memory = ConversationMemory(user_id="user_123", storage=mock_storage)
        count = memory.token_count()

        # Should return non-negative integer
        assert isinstance(count, int)
        assert count >= 0

    def test_token_count_empty_history(self, mock_storage):
        """Test token count for empty history."""
        from core.memory.conversation import ConversationMemory

        mock_storage.get_messages.return_value = []

        memory = ConversationMemory(user_id="user_123", storage=mock_storage)
        count = memory.token_count()

        assert count == 0

    def test_token_count_approximation(self, mock_storage):
        """Test token count uses reasonable approximation."""
        from core.memory.conversation import ConversationMemory, Message

        # Create a message with known word count
        msg = Message(role="user", content="hello world this is a test message")
        mock_storage.get_messages.return_value = [msg]

        memory = ConversationMemory(user_id="user_123", storage=mock_storage)
        count = memory.token_count()

        # Rough estimate: ~1.3 tokens per word, 7 words = ~9 tokens
        assert 5 <= count <= 20


# ==============================================================================
# Edge Cases Tests
# ==============================================================================

class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_very_long_message(self, mock_storage):
        """Test handling very long messages."""
        from core.memory.conversation import ConversationMemory

        memory = ConversationMemory(user_id="user_123", storage=mock_storage)
        long_content = "x" * 10000

        msg_id = memory.add_message("user", long_content)

        assert msg_id is not None

    def test_unicode_content(self, mock_storage):
        """Test handling unicode content."""
        from core.memory.conversation import ConversationMemory

        memory = ConversationMemory(user_id="user_123", storage=mock_storage)
        unicode_content = "Hello World"

        msg_id = memory.add_message("user", unicode_content)

        assert msg_id is not None

    def test_special_characters_in_content(self, mock_storage):
        """Test handling special characters."""
        from core.memory.conversation import ConversationMemory

        memory = ConversationMemory(user_id="user_123", storage=mock_storage)
        special_content = "Test: <script>alert('xss')</script> & more"

        msg_id = memory.add_message("user", special_content)

        assert msg_id is not None

    def test_whitespace_only_content(self, mock_storage):
        """Test rejecting whitespace-only content."""
        from core.memory.conversation import ConversationMemory

        memory = ConversationMemory(user_id="user_123", storage=mock_storage)

        with pytest.raises(ValueError, match="Content cannot be empty"):
            memory.add_message("user", "   ")

    def test_multiple_users_isolation(self, mock_storage):
        """Test that different users have isolated histories."""
        from core.memory.conversation import ConversationMemory

        memory1 = ConversationMemory(user_id="user_1", storage=mock_storage)
        memory2 = ConversationMemory(user_id="user_2", storage=mock_storage)

        memory1.add_message("user", "Hello from user 1")
        memory2.add_message("user", "Hello from user 2")

        # Verify different user IDs are passed to storage
        calls = mock_storage.save_message.call_args_list
        assert calls[0][0][0] == "user_1"
        assert calls[1][0][0] == "user_2"


# ==============================================================================
# Integration-like Tests (with real Message objects)
# ==============================================================================

class TestIntegrationLike:
    """Tests that verify component interaction."""

    def test_add_and_retrieve_flow(self, mock_storage):
        """Test adding and retrieving messages."""
        from core.memory.conversation import ConversationMemory, Message

        stored_messages = []

        def mock_save(user_id, msg):
            stored_messages.append(msg)
            return msg.id

        def mock_get(user_id, limit=10):
            return stored_messages[-limit:]

        mock_storage.save_message.side_effect = mock_save
        mock_storage.get_messages.side_effect = mock_get

        memory = ConversationMemory(user_id="user_123", storage=mock_storage)

        # Add messages
        memory.add_message("user", "Hello")
        memory.add_message("assistant", "Hi there!")

        # Retrieve
        history = memory.get_history()

        assert len(history) == 2
        assert history[0].content == "Hello"
        assert history[1].content == "Hi there!"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
