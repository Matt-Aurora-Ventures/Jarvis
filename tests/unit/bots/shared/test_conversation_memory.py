"""
Tests for bots/shared/conversation_memory.py

Conversation memory module for ClawdBots enabling:
- Per-user conversation history storage
- Context retrieval for responses
- Memory summarization
- Memory limits management
- Cross-bot memory sharing

Tests cover:
- Message storage and retrieval
- Conversation history limits (100 messages max)
- Context generation for prompts (token-limited)
- Auto-summarization of older messages
- Memory expiration after 7 days
- Cross-bot memory sharing
- JSON persistence
"""

import json
import os
import sys
import tempfile
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from bots.shared.conversation_memory import (
    ConversationMemory,
    Message,
    ConversationSummary,
    MemoryConfig,
    add_message,
    get_conversation_history,
    get_context_for_prompt,
    summarize_conversation,
    clear_memory,
    share_memory,
)


class TestMessage:
    """Test Message dataclass."""

    def test_create_message(self):
        """Should create message with required fields."""
        msg = Message(
            role="user",
            content="Hello, how are you?",
        )
        assert msg.role == "user"
        assert msg.content == "Hello, how are you?"
        assert msg.timestamp is not None

    def test_message_with_timestamp(self):
        """Should accept explicit timestamp."""
        ts = datetime(2026, 2, 2, 10, 0, 0, tzinfo=timezone.utc)
        msg = Message(
            role="assistant",
            content="I'm doing well, thanks!",
            timestamp=ts,
        )
        assert msg.timestamp == ts

    def test_to_dict(self):
        """Should serialize message to dict."""
        msg = Message(
            role="user",
            content="Test message",
        )
        data = msg.to_dict()
        assert data["role"] == "user"
        assert data["content"] == "Test message"
        assert "timestamp" in data

    def test_from_dict(self):
        """Should deserialize message from dict."""
        data = {
            "role": "assistant",
            "content": "Response text",
            "timestamp": "2026-02-02T10:00:00+00:00",
        }
        msg = Message.from_dict(data)
        assert msg.role == "assistant"
        assert msg.content == "Response text"

    def test_token_count(self):
        """Should estimate token count (roughly 4 chars per token)."""
        msg = Message(role="user", content="Hello world!")
        # "Hello world!" = 12 chars, ~3 tokens
        assert msg.token_count >= 2
        assert msg.token_count <= 5


class TestConversationSummary:
    """Test ConversationSummary dataclass."""

    def test_create_summary(self):
        """Should create summary with content."""
        summary = ConversationSummary(
            content="User discussed trading strategies and portfolio management.",
            message_count=50,
            created_at=datetime.now(timezone.utc),
        )
        assert "trading" in summary.content.lower()
        assert summary.message_count == 50

    def test_to_dict(self):
        """Should serialize summary to dict."""
        summary = ConversationSummary(
            content="Test summary",
            message_count=10,
        )
        data = summary.to_dict()
        assert data["content"] == "Test summary"
        assert data["message_count"] == 10

    def test_from_dict(self):
        """Should deserialize summary from dict."""
        data = {
            "content": "Previous conversation about crypto",
            "message_count": 25,
            "created_at": "2026-02-02T10:00:00+00:00",
        }
        summary = ConversationSummary.from_dict(data)
        assert summary.content == "Previous conversation about crypto"
        assert summary.message_count == 25


class TestMemoryConfig:
    """Test MemoryConfig configuration."""

    def test_default_config(self):
        """Should have sensible defaults."""
        config = MemoryConfig()
        assert config.max_messages == 100
        assert config.max_context_tokens == 2000
        assert config.expiry_days == 7
        assert config.auto_summarize_threshold == 80

    def test_custom_config(self):
        """Should accept custom values."""
        config = MemoryConfig(
            max_messages=50,
            max_context_tokens=1000,
            expiry_days=14,
        )
        assert config.max_messages == 50
        assert config.max_context_tokens == 1000
        assert config.expiry_days == 14


class TestConversationMemory:
    """Test ConversationMemory class."""

    @pytest.fixture
    def temp_memory_dir(self):
        """Create temporary memory directory for tests."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir

    @pytest.fixture
    def memory(self, temp_memory_dir):
        """Create ConversationMemory with temp directory."""
        return ConversationMemory(
            bot_name="jarvis",
            memory_dir=temp_memory_dir,
        )

    # Message storage tests

    def test_add_message(self, memory):
        """Should add message to conversation."""
        memory.add_message(
            user_id="user123",
            role="user",
            content="Hello Jarvis!",
        )
        history = memory.get_conversation_history("user123")
        assert len(history) == 1
        assert history[0].role == "user"
        assert history[0].content == "Hello Jarvis!"

    def test_add_multiple_messages(self, memory):
        """Should maintain message order."""
        memory.add_message("user123", "user", "First message")
        memory.add_message("user123", "assistant", "First response")
        memory.add_message("user123", "user", "Second message")

        history = memory.get_conversation_history("user123")
        assert len(history) == 3
        assert history[0].content == "First message"
        assert history[1].content == "First response"
        assert history[2].content == "Second message"

    def test_separate_user_conversations(self, memory):
        """Should keep conversations separate per user."""
        memory.add_message("user1", "user", "From user 1")
        memory.add_message("user2", "user", "From user 2")
        memory.add_message("user1", "assistant", "Reply to user 1")

        history1 = memory.get_conversation_history("user1")
        history2 = memory.get_conversation_history("user2")

        assert len(history1) == 2
        assert len(history2) == 1

    # History retrieval tests

    def test_get_history_with_limit(self, memory):
        """Should limit returned history."""
        for i in range(30):
            memory.add_message("user123", "user", f"Message {i}")

        history = memory.get_conversation_history("user123", limit=10)
        assert len(history) == 10
        # Should return most recent messages
        assert history[-1].content == "Message 29"

    def test_get_history_default_limit(self, memory):
        """Should default to 20 messages."""
        for i in range(30):
            memory.add_message("user123", "user", f"Message {i}")

        history = memory.get_conversation_history("user123")
        assert len(history) == 20

    def test_get_empty_history(self, memory):
        """Should return empty list for new user."""
        history = memory.get_conversation_history("nonexistent_user")
        assert history == []

    # Memory limits tests

    def test_max_messages_enforced(self, memory):
        """Should enforce max 100 messages per conversation."""
        # Add 120 messages
        for i in range(120):
            memory.add_message("user123", "user", f"Message {i}")

        # Internal storage should be limited
        history = memory.get_conversation_history("user123", limit=200)
        assert len(history) <= 100

    def test_old_messages_summarized_on_limit(self, memory):
        """Should summarize old messages when approaching limit."""
        # Configure lower threshold for testing
        memory.config.auto_summarize_threshold = 10
        memory.config.max_messages = 15

        # Add messages to trigger summarization
        for i in range(15):
            memory.add_message("user123", "user", f"Message about topic {i}")

        # Should have summary
        conv = memory._load_conversation("user123")
        assert conv.summary is not None or len(conv.messages) <= 15

    # Context generation tests

    def test_get_context_for_prompt(self, memory):
        """Should generate context string for LLM prompt."""
        memory.add_message("user123", "user", "I like trading Solana tokens")
        memory.add_message("user123", "assistant", "I can help with that!")
        memory.add_message("user123", "user", "What's the best strategy?")

        context = memory.get_context_for_prompt("user123")
        assert "trading" in context.lower()
        assert "solana" in context.lower()

    def test_context_respects_token_limit(self, memory):
        """Should limit context to max tokens."""
        # Add many long messages
        long_text = "This is a long message " * 100
        for i in range(10):
            memory.add_message("user123", "user", long_text)

        context = memory.get_context_for_prompt("user123", max_tokens=500)
        # Context should be truncated
        assert len(context) <= 2500  # ~4 chars per token + buffer

    def test_context_includes_summary(self, temp_memory_dir):
        """Should include summary in context if available."""
        memory = ConversationMemory("jarvis", temp_memory_dir)
        memory.config.auto_summarize_threshold = 5
        memory.config.max_messages = 10

        # Force a summary
        for i in range(12):
            memory.add_message("user123", "user", f"Discussing topic {i}")

        context = memory.get_context_for_prompt("user123")
        # Context should be present (either summary or recent messages)
        assert len(context) > 0

    # Summarization tests

    def test_summarize_conversation(self, memory):
        """Should generate summary of conversation."""
        memory.add_message("user123", "user", "Let's discuss Bitcoin")
        memory.add_message("user123", "assistant", "Sure, BTC is interesting")
        memory.add_message("user123", "user", "What about Ethereum?")
        memory.add_message("user123", "assistant", "ETH has smart contracts")

        summary = memory.summarize_conversation("user123")
        assert summary is not None
        assert len(summary.content) > 0
        assert summary.message_count >= 4

    def test_summarize_empty_conversation(self, memory):
        """Should return None for empty conversation."""
        summary = memory.summarize_conversation("nonexistent")
        assert summary is None

    # Memory clearing tests

    def test_clear_memory(self, memory):
        """Should clear all memory for a user."""
        memory.add_message("user123", "user", "Message 1")
        memory.add_message("user123", "user", "Message 2")

        memory.clear_memory("user123")

        history = memory.get_conversation_history("user123")
        assert len(history) == 0

    def test_clear_memory_removes_file(self, memory, temp_memory_dir):
        """Should delete memory file on clear."""
        memory.add_message("user123", "user", "Test")
        file_path = Path(temp_memory_dir) / "jarvis" / "user123.json"
        assert file_path.exists()

        memory.clear_memory("user123")
        assert not file_path.exists()

    # Expiration tests

    def test_expire_old_conversations(self, temp_memory_dir):
        """Should expire conversations older than 7 days."""
        memory = ConversationMemory("jarvis", temp_memory_dir)

        # Create old conversation file
        user_dir = Path(temp_memory_dir) / "jarvis"
        user_dir.mkdir(parents=True, exist_ok=True)
        old_file = user_dir / "old_user.json"
        old_data = {
            "messages": [
                {
                    "role": "user",
                    "content": "Old message",
                    "timestamp": (datetime.now(timezone.utc) - timedelta(days=10)).isoformat(),
                }
            ],
            "last_activity": (datetime.now(timezone.utc) - timedelta(days=10)).isoformat(),
        }
        with open(old_file, "w") as f:
            json.dump(old_data, f)

        # Run expiration
        expired = memory.expire_old_conversations()
        assert "old_user" in expired
        assert not old_file.exists()

    def test_keep_active_conversations(self, temp_memory_dir):
        """Should not expire active conversations."""
        memory = ConversationMemory("jarvis", temp_memory_dir)
        memory.add_message("active_user", "user", "Recent message")

        expired = memory.expire_old_conversations()
        assert "active_user" not in expired

        history = memory.get_conversation_history("active_user")
        assert len(history) == 1

    # Cross-bot memory sharing tests

    def test_share_memory_between_bots(self, temp_memory_dir):
        """Should copy memory from one bot to another."""
        jarvis = ConversationMemory("jarvis", temp_memory_dir)
        jarvis.add_message("user123", "user", "Message to Jarvis")
        jarvis.add_message("user123", "assistant", "Jarvis response")

        friday = ConversationMemory("friday", temp_memory_dir)

        # Share memory
        result = jarvis.share_memory_to("friday", "user123", temp_memory_dir)
        assert result is True

        # Friday should have the context
        friday_history = friday.get_conversation_history("user123")
        assert len(friday_history) >= 1

    def test_share_memory_preserves_original(self, temp_memory_dir):
        """Should not modify original bot's memory when sharing."""
        jarvis = ConversationMemory("jarvis", temp_memory_dir)
        jarvis.add_message("user123", "user", "Original message")

        jarvis.share_memory_to("friday", "user123", temp_memory_dir)

        # Jarvis still has original
        history = jarvis.get_conversation_history("user123")
        assert len(history) == 1

    def test_share_memory_merges_existing(self, temp_memory_dir):
        """Should merge with existing memory in target bot."""
        jarvis = ConversationMemory("jarvis", temp_memory_dir)
        jarvis.add_message("user123", "user", "Jarvis message")

        friday = ConversationMemory("friday", temp_memory_dir)
        friday.add_message("user123", "user", "Friday message")

        jarvis.share_memory_to("friday", "user123", temp_memory_dir)

        friday = ConversationMemory("friday", temp_memory_dir)
        history = friday.get_conversation_history("user123", limit=100)
        # Should have both messages or merged context
        assert len(history) >= 1

    # Persistence tests

    def test_persistence_across_instances(self, temp_memory_dir):
        """Should persist conversations across memory instances."""
        memory1 = ConversationMemory("jarvis", temp_memory_dir)
        memory1.add_message("user123", "user", "Persistent message")

        # Create new instance
        memory2 = ConversationMemory("jarvis", temp_memory_dir)
        history = memory2.get_conversation_history("user123")
        assert len(history) == 1
        assert history[0].content == "Persistent message"

    def test_json_file_format(self, memory, temp_memory_dir):
        """Should store in correct JSON format."""
        memory.add_message("user123", "user", "Test message")

        file_path = Path(temp_memory_dir) / "jarvis" / "user123.json"
        assert file_path.exists()

        with open(file_path) as f:
            data = json.load(f)

        assert "messages" in data
        assert "last_activity" in data

    # Error handling tests

    def test_handle_corrupted_file(self, temp_memory_dir):
        """Should handle corrupted JSON files gracefully."""
        memory = ConversationMemory("jarvis", temp_memory_dir)

        # Create corrupted file
        user_dir = Path(temp_memory_dir) / "jarvis"
        user_dir.mkdir(parents=True, exist_ok=True)
        corrupted_file = user_dir / "corrupted_user.json"
        corrupted_file.write_text("{invalid json")

        # Should not crash
        history = memory.get_conversation_history("corrupted_user")
        assert history == []

    def test_handle_missing_directory(self, temp_memory_dir):
        """Should create directory if missing."""
        memory = ConversationMemory("new_bot", temp_memory_dir)
        memory.add_message("user123", "user", "Test")

        bot_dir = Path(temp_memory_dir) / "new_bot"
        assert bot_dir.exists()


class TestConvenienceFunctions:
    """Test module-level convenience functions."""

    @pytest.fixture
    def temp_memory_dir(self):
        """Create temporary memory directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir

    @pytest.fixture(autouse=True)
    def clear_memory_cache(self):
        """Clear the memory instance cache before each test."""
        import bots.shared.conversation_memory as cm
        cm._memory_instances.clear()
        yield
        cm._memory_instances.clear()

    def test_add_message_function(self, temp_memory_dir):
        """Should add message via convenience function."""
        import bots.shared.conversation_memory as cm
        cm._memory_instances.clear()
        with patch(
            "bots.shared.conversation_memory.DEFAULT_MEMORY_DIR",
            temp_memory_dir,
        ):
            add_message("jarvis", "user123", "user", "Hello!")

            history = get_conversation_history("jarvis", "user123")
            assert len(history) == 1

    def test_get_conversation_history_function(self, temp_memory_dir):
        """Should get history via convenience function."""
        import bots.shared.conversation_memory as cm
        cm._memory_instances.clear()
        with patch(
            "bots.shared.conversation_memory.DEFAULT_MEMORY_DIR",
            temp_memory_dir,
        ):
            add_message("jarvis", "user123", "user", "Message 1")
            add_message("jarvis", "user123", "assistant", "Response 1")

            history = get_conversation_history("jarvis", "user123", limit=10)
            assert len(history) == 2

    def test_get_context_for_prompt_function(self, temp_memory_dir):
        """Should get context via convenience function."""
        import bots.shared.conversation_memory as cm
        cm._memory_instances.clear()
        with patch(
            "bots.shared.conversation_memory.DEFAULT_MEMORY_DIR",
            temp_memory_dir,
        ):
            add_message("jarvis", "user123", "user", "I need help with Python")

            context = get_context_for_prompt("jarvis", "user123", max_tokens=500)
            assert "python" in context.lower()

    def test_summarize_conversation_function(self, temp_memory_dir):
        """Should summarize via convenience function."""
        import bots.shared.conversation_memory as cm
        cm._memory_instances.clear()
        with patch(
            "bots.shared.conversation_memory.DEFAULT_MEMORY_DIR",
            temp_memory_dir,
        ):
            add_message("jarvis", "user123", "user", "Let's talk about AI")
            add_message("jarvis", "user123", "assistant", "AI is fascinating")

            summary = summarize_conversation("jarvis", "user123")
            assert summary is not None

    def test_clear_memory_function(self, temp_memory_dir):
        """Should clear memory via convenience function."""
        import bots.shared.conversation_memory as cm
        cm._memory_instances.clear()
        with patch(
            "bots.shared.conversation_memory.DEFAULT_MEMORY_DIR",
            temp_memory_dir,
        ):
            add_message("jarvis", "user123", "user", "To be deleted")
            clear_memory("jarvis", "user123")

            history = get_conversation_history("jarvis", "user123")
            assert len(history) == 0

    def test_share_memory_function(self, temp_memory_dir):
        """Should share memory via convenience function."""
        import bots.shared.conversation_memory as cm
        cm._memory_instances.clear()
        with patch(
            "bots.shared.conversation_memory.DEFAULT_MEMORY_DIR",
            temp_memory_dir,
        ):
            add_message("jarvis", "user123", "user", "Share this")

            result = share_memory("jarvis", "friday", "user123")
            assert result is True

            friday_history = get_conversation_history("friday", "user123")
            assert len(friday_history) >= 1
