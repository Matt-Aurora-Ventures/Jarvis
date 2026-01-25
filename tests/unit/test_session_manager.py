"""
Unit tests for Session Management System.

Tests:
- Session lifecycle (create, load, save, reset)
- Token tracking and estimation
- Context tracking
- Compaction functionality
- Database persistence
"""

import pytest
import tempfile
import os
from datetime import datetime, timezone, timedelta
from pathlib import Path


class TestSessionDataclass:
    """Test Session dataclass."""

    def test_session_creation_defaults(self):
        """Session should have sensible defaults."""
        from core.session.manager import Session

        session = Session(
            id="test-123",
            user_id=12345,
            platform="telegram"
        )

        assert session.id == "test-123"
        assert session.user_id == 12345
        assert session.platform == "telegram"
        assert session.tokens_in == 0
        assert session.tokens_out == 0
        assert session.context_used == 0
        assert session.context_limit == 200000
        assert session.compaction_count == 0
        assert session.messages == []
        assert session.metadata == {}

    def test_session_with_custom_values(self):
        """Session should accept custom values."""
        from core.session.manager import Session, Message

        messages = [
            Message(role="user", content="Hello", tokens=5),
            Message(role="assistant", content="Hi there!", tokens=10)
        ]

        session = Session(
            id="custom-456",
            user_id=67890,
            platform="twitter",
            tokens_in=100,
            tokens_out=200,
            context_used=5000,
            context_limit=100000,
            compaction_count=2,
            messages=messages,
            metadata={"test": "value"}
        )

        assert session.tokens_in == 100
        assert session.tokens_out == 200
        assert session.context_used == 5000
        assert session.context_limit == 100000
        assert session.compaction_count == 2
        assert len(session.messages) == 2
        assert session.metadata["test"] == "value"


class TestMessage:
    """Test Message dataclass."""

    def test_message_creation(self):
        """Message should store role, content, and tokens."""
        from core.session.manager import Message

        msg = Message(role="user", content="Hello world", tokens=3)

        assert msg.role == "user"
        assert msg.content == "Hello world"
        assert msg.tokens == 3
        assert msg.created_at is not None

    def test_message_default_tokens(self):
        """Message tokens should default to 0."""
        from core.session.manager import Message

        msg = Message(role="system", content="Be helpful")
        assert msg.tokens == 0


class TestTokenEstimator:
    """Test token estimation."""

    def test_estimate_empty_string(self):
        """Empty string should have 0 tokens."""
        from core.session.tokens import estimate_tokens

        assert estimate_tokens("") == 0

    def test_estimate_simple_text(self):
        """Simple text should give reasonable token count."""
        from core.session.tokens import estimate_tokens

        # "Hello world" should be roughly 2-3 tokens
        tokens = estimate_tokens("Hello world")
        assert 1 <= tokens <= 5

    def test_estimate_longer_text(self):
        """Longer text should scale appropriately."""
        from core.session.tokens import estimate_tokens

        short = estimate_tokens("Hello")
        long = estimate_tokens("Hello world, this is a longer message with more tokens.")

        assert long > short

    def test_estimate_with_special_chars(self):
        """Text with special characters should estimate correctly."""
        from core.session.tokens import estimate_tokens

        # Emojis and special chars
        tokens = estimate_tokens("Hello! @user #tag $100")
        assert tokens > 0


class TestSessionManager:
    """Test SessionManager functionality."""

    @pytest.fixture
    def temp_db(self):
        """Create temporary database for testing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test_sessions.db"
            yield db_path

    @pytest.fixture
    def manager(self, temp_db):
        """Create SessionManager with temp database."""
        from core.session.manager import SessionManager

        mgr = SessionManager(db_path=temp_db)
        yield mgr
        mgr.close()  # Close connection to allow cleanup on Windows

    def test_create_session(self, manager):
        """create_session should return a new Session."""
        session = manager.create_session(user_id=12345, platform="telegram")

        assert session is not None
        assert session.user_id == 12345
        assert session.platform == "telegram"
        assert session.id is not None
        assert len(session.id) > 0

    def test_create_session_generates_unique_ids(self, manager):
        """Each session should have unique ID."""
        s1 = manager.create_session(user_id=1, platform="telegram")
        s2 = manager.create_session(user_id=1, platform="telegram")

        assert s1.id != s2.id

    def test_save_and_load_session(self, manager):
        """Session should persist and reload correctly."""
        session = manager.create_session(user_id=12345, platform="telegram")
        session.tokens_in = 500
        session.tokens_out = 250
        session.metadata["key"] = "value"

        manager.save_session(session)

        loaded = manager.load_session(session.id)

        assert loaded is not None
        assert loaded.id == session.id
        assert loaded.user_id == 12345
        assert loaded.tokens_in == 500
        assert loaded.tokens_out == 250
        assert loaded.metadata["key"] == "value"

    def test_load_nonexistent_session(self, manager):
        """Loading nonexistent session should return None."""
        loaded = manager.load_session("nonexistent-id")
        assert loaded is None

    def test_reset_session(self, manager):
        """reset_session should clear messages and stats."""
        session = manager.create_session(user_id=12345, platform="telegram")
        session.tokens_in = 500
        session.tokens_out = 250
        session.compaction_count = 3
        manager.save_session(session)

        new_session = manager.reset_session(session.id)

        assert new_session is not None
        assert new_session.id != session.id  # New ID
        assert new_session.user_id == 12345  # Same user
        assert new_session.tokens_in == 0
        assert new_session.tokens_out == 0
        assert new_session.compaction_count == 0
        assert new_session.messages == []

    def test_get_or_create_session(self, manager):
        """get_or_create should return existing or create new."""
        # First call creates
        s1 = manager.get_or_create_session(user_id=12345, platform="telegram")
        manager.save_session(s1)

        # Modify and save
        s1.tokens_in = 100
        manager.save_session(s1)

        # Second call loads existing
        s2 = manager.get_or_create_session(user_id=12345, platform="telegram")

        assert s2.tokens_in == 100

    def test_get_stats(self, manager):
        """get_stats should return formatted statistics."""
        session = manager.create_session(user_id=12345, platform="telegram")
        session.tokens_in = 15200
        session.tokens_out = 8400
        session.context_used = 48000
        session.context_limit = 200000
        session.compaction_count = 2

        stats = manager.get_stats(session)

        assert "tokens_in" in stats
        assert "tokens_out" in stats
        assert "context_used" in stats
        assert "context_limit" in stats
        assert "context_percentage" in stats
        assert "compaction_count" in stats

        assert stats["tokens_in"] == 15200
        assert stats["tokens_out"] == 8400
        assert stats["context_percentage"] == 24.0  # 48000/200000 * 100


class TestSessionMessages:
    """Test session message handling."""

    @pytest.fixture
    def manager(self):
        """Create SessionManager with temp database."""
        from core.session.manager import SessionManager

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test_sessions.db"
            mgr = SessionManager(db_path=db_path)
            yield mgr
            mgr.close()  # Close connection to allow cleanup on Windows

    def test_add_message(self, manager):
        """Adding message should update tokens and context."""
        session = manager.create_session(user_id=12345, platform="telegram")

        manager.add_message(session, role="user", content="Hello, how are you?")

        assert len(session.messages) == 1
        assert session.messages[0].role == "user"
        assert session.messages[0].content == "Hello, how are you?"
        assert session.tokens_in > 0
        assert session.context_used > 0

    def test_add_assistant_message(self, manager):
        """Assistant messages should update tokens_out."""
        session = manager.create_session(user_id=12345, platform="telegram")

        initial_out = session.tokens_out
        manager.add_message(session, role="assistant", content="I'm doing great!")

        assert session.tokens_out > initial_out

    def test_message_tracking_accumulates(self, manager):
        """Multiple messages should accumulate tokens."""
        session = manager.create_session(user_id=12345, platform="telegram")

        manager.add_message(session, role="user", content="First message")
        tokens_after_first = session.tokens_in

        manager.add_message(session, role="user", content="Second message")
        tokens_after_second = session.tokens_in

        assert tokens_after_second > tokens_after_first


class TestContextCompaction:
    """Test context compaction functionality."""

    @pytest.fixture
    def manager(self):
        """Create SessionManager with temp database."""
        from core.session.manager import SessionManager

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test_sessions.db"
            mgr = SessionManager(db_path=db_path)
            yield mgr
            mgr.close()  # Close connection to allow cleanup on Windows

    def test_compact_reduces_context(self, manager):
        """Compaction should reduce message count and add summary."""
        session = manager.create_session(user_id=12345, platform="telegram")

        # Add many messages
        for i in range(20):
            manager.add_message(session, role="user", content=f"Message {i}: This is a test message with some content.")
            manager.add_message(session, role="assistant", content=f"Response {i}: Here is my helpful reply.")

        initial_messages = len(session.messages)

        # Compact
        compacted = manager.compact_session(session)

        # After compaction: fewer messages (summary + recent)
        assert len(compacted.messages) < initial_messages
        assert compacted.compaction_count == 1
        # First message should be the system summary
        assert compacted.messages[0].role == "system"
        assert "[Compacted context]" in compacted.messages[0].content

    def test_compact_preserves_recent(self, manager):
        """Compaction should preserve recent messages."""
        session = manager.create_session(user_id=12345, platform="telegram")

        # Add messages
        for i in range(10):
            manager.add_message(session, role="user", content=f"Old message {i}")

        manager.add_message(session, role="user", content="Recent important message")

        compacted = manager.compact_session(session)

        # Recent message should be preserved
        contents = [m.content for m in compacted.messages]
        assert any("Recent important message" in c for c in contents)

    def test_compact_empty_session(self, manager):
        """Compacting empty session should not error."""
        session = manager.create_session(user_id=12345, platform="telegram")

        compacted = manager.compact_session(session)

        assert compacted is not None
        assert compacted.compaction_count == 1


class TestDatabasePersistence:
    """Test database persistence layer."""

    @pytest.fixture
    def temp_db(self):
        """Create temporary database for testing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test_sessions.db"
            yield db_path

    def test_session_persists_across_instances(self, temp_db):
        """Session should persist across manager instances."""
        from core.session.manager import SessionManager

        # Create and save with first instance
        manager1 = SessionManager(db_path=temp_db)
        session = manager1.create_session(user_id=12345, platform="telegram")
        session.tokens_in = 999
        manager1.save_session(session)
        session_id = session.id

        # Load with second instance
        manager2 = SessionManager(db_path=temp_db)
        loaded = manager2.load_session(session_id)

        assert loaded is not None
        assert loaded.tokens_in == 999

    def test_messages_persist(self, temp_db):
        """Messages should persist with session."""
        from core.session.manager import SessionManager

        manager1 = SessionManager(db_path=temp_db)
        session = manager1.create_session(user_id=12345, platform="telegram")
        manager1.add_message(session, role="user", content="Test message")
        manager1.save_session(session)
        session_id = session.id

        manager2 = SessionManager(db_path=temp_db)
        loaded = manager2.load_session(session_id)

        assert len(loaded.messages) == 1
        assert loaded.messages[0].content == "Test message"

    def test_get_user_sessions(self, temp_db):
        """Should retrieve all sessions for a user."""
        from core.session.manager import SessionManager

        manager = SessionManager(db_path=temp_db)

        # Create multiple sessions
        s1 = manager.create_session(user_id=12345, platform="telegram")
        s2 = manager.create_session(user_id=12345, platform="telegram")
        s3 = manager.create_session(user_id=99999, platform="telegram")  # Different user

        manager.save_session(s1)
        manager.save_session(s2)
        manager.save_session(s3)

        user_sessions = manager.get_user_sessions(12345)

        assert len(user_sessions) == 2
        assert all(s.user_id == 12345 for s in user_sessions)
