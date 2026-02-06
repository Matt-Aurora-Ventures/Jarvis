"""
Tests for core/memory/storage.py - Memory storage backends.

Verifies:
- MemoryStorage abstract interface
- FileStorage (JSON files per user)
- SQLiteStorage (database backend)
- TTL support for expiration
- Thread safety

Coverage Target: 60%+ with ~45 tests
"""

import json
import pytest
import sqlite3
import tempfile
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock


# ==============================================================================
# Test Fixtures
# ==============================================================================

@pytest.fixture
def temp_dir(tmp_path):
    """Create a temporary directory for file storage."""
    return tmp_path / "memory"


@pytest.fixture
def temp_db_path(tmp_path):
    """Create a temporary database path."""
    return tmp_path / "conversation.db"


@pytest.fixture
def sample_message():
    """Create a sample message for testing."""
    from core.memory.conversation import Message
    return Message(
        id="msg_001",
        role="user",
        content="Hello, world!",
        metadata={"source": "test"}
    )


@pytest.fixture
def sample_messages():
    """Create a list of sample messages."""
    from core.memory.conversation import Message
    now = datetime.utcnow()
    return [
        Message(
            id="msg_001",
            role="user",
            content="First message",
            timestamp=now - timedelta(minutes=5)
        ),
        Message(
            id="msg_002",
            role="assistant",
            content="Second message",
            timestamp=now - timedelta(minutes=4)
        ),
        Message(
            id="msg_003",
            role="user",
            content="Third message",
            timestamp=now - timedelta(minutes=3)
        ),
    ]


# ==============================================================================
# MemoryStorage Abstract Interface Tests
# ==============================================================================

class TestMemoryStorageInterface:
    """Test MemoryStorage abstract interface."""

    def test_cannot_instantiate_abstract_class(self):
        """Test that MemoryStorage cannot be directly instantiated."""
        from core.memory.storage import MemoryStorage

        with pytest.raises(TypeError):
            MemoryStorage()

    def test_abstract_methods_defined(self):
        """Test that abstract methods are defined."""
        from core.memory.storage import MemoryStorage
        import abc

        # Check that the required methods are abstract
        assert hasattr(MemoryStorage, 'save_message')
        assert hasattr(MemoryStorage, 'get_messages')
        assert hasattr(MemoryStorage, 'delete_messages')
        assert hasattr(MemoryStorage, 'get_message_count')


# ==============================================================================
# FileStorage Tests
# ==============================================================================

class TestFileStorageInit:
    """Test FileStorage initialization."""

    def test_init_creates_directory(self, temp_dir):
        """Test that initialization creates the storage directory."""
        from core.memory.storage import FileStorage

        storage = FileStorage(base_path=temp_dir)

        assert temp_dir.exists()
        assert storage.base_path == temp_dir

    def test_init_with_existing_directory(self, temp_dir):
        """Test initialization with existing directory."""
        from core.memory.storage import FileStorage

        temp_dir.mkdir(parents=True, exist_ok=True)
        storage = FileStorage(base_path=temp_dir)

        assert storage.base_path == temp_dir

    def test_init_with_default_path(self):
        """Test initialization with default path."""
        with patch('core.memory.storage.get_default_memory_path') as mock_path:
            mock_path.return_value = Path("/tmp/memory")

            from core.memory.storage import FileStorage

            with patch.object(Path, 'mkdir'):
                storage = FileStorage()
                mock_path.assert_called_once()


class TestFileStorageSaveMessage:
    """Test FileStorage save_message functionality."""

    def test_save_message_creates_file(self, temp_dir, sample_message):
        """Test that save_message creates user file."""
        from core.memory.storage import FileStorage

        storage = FileStorage(base_path=temp_dir)
        msg_id = storage.save_message("user_123", sample_message)

        user_file = temp_dir / "user_123.json"
        assert user_file.exists()
        assert msg_id == sample_message.id

    def test_save_message_appends_to_existing(self, temp_dir, sample_messages):
        """Test that save_message appends to existing file."""
        from core.memory.storage import FileStorage

        storage = FileStorage(base_path=temp_dir)

        for msg in sample_messages:
            storage.save_message("user_123", msg)

        # Verify all messages saved
        user_file = temp_dir / "user_123.json"
        with open(user_file, 'r') as f:
            data = json.load(f)

        assert len(data["messages"]) == 3

    def test_save_message_stores_metadata(self, temp_dir, sample_message):
        """Test that save_message stores metadata."""
        from core.memory.storage import FileStorage

        storage = FileStorage(base_path=temp_dir)
        storage.save_message("user_123", sample_message)

        user_file = temp_dir / "user_123.json"
        with open(user_file, 'r') as f:
            data = json.load(f)

        assert data["messages"][0]["metadata"]["source"] == "test"

    def test_save_message_returns_id(self, temp_dir, sample_message):
        """Test that save_message returns message ID."""
        from core.memory.storage import FileStorage

        storage = FileStorage(base_path=temp_dir)
        msg_id = storage.save_message("user_123", sample_message)

        assert msg_id == "msg_001"


class TestFileStorageGetMessages:
    """Test FileStorage get_messages functionality."""

    def test_get_messages_returns_list(self, temp_dir, sample_messages):
        """Test that get_messages returns a list."""
        from core.memory.storage import FileStorage

        storage = FileStorage(base_path=temp_dir)
        for msg in sample_messages:
            storage.save_message("user_123", msg)

        messages = storage.get_messages("user_123")

        assert isinstance(messages, list)
        assert len(messages) == 3

    def test_get_messages_with_limit(self, temp_dir, sample_messages):
        """Test get_messages with limit."""
        from core.memory.storage import FileStorage

        storage = FileStorage(base_path=temp_dir)
        for msg in sample_messages:
            storage.save_message("user_123", msg)

        messages = storage.get_messages("user_123", limit=2)

        assert len(messages) == 2

    def test_get_messages_empty_user(self, temp_dir):
        """Test get_messages for user with no history."""
        from core.memory.storage import FileStorage

        storage = FileStorage(base_path=temp_dir)
        messages = storage.get_messages("nonexistent_user")

        assert messages == []

    def test_get_messages_returns_most_recent(self, temp_dir, sample_messages):
        """Test that get_messages returns most recent messages."""
        from core.memory.storage import FileStorage

        storage = FileStorage(base_path=temp_dir)
        for msg in sample_messages:
            storage.save_message("user_123", msg)

        messages = storage.get_messages("user_123", limit=2)

        # Should return last 2 messages
        assert messages[-1].id == "msg_003"


class TestFileStorageDeleteMessages:
    """Test FileStorage delete_messages functionality."""

    def test_delete_messages_removes_file(self, temp_dir, sample_message):
        """Test that delete_messages removes user file."""
        from core.memory.storage import FileStorage

        storage = FileStorage(base_path=temp_dir)
        storage.save_message("user_123", sample_message)

        user_file = temp_dir / "user_123.json"
        assert user_file.exists()

        result = storage.delete_messages("user_123")

        assert result is True
        assert not user_file.exists()

    def test_delete_messages_nonexistent_user(self, temp_dir):
        """Test delete_messages for nonexistent user."""
        from core.memory.storage import FileStorage

        storage = FileStorage(base_path=temp_dir)
        result = storage.delete_messages("nonexistent_user")

        assert result is True  # Idempotent - already deleted

    def test_delete_messages_returns_status(self, temp_dir, sample_message):
        """Test that delete_messages returns correct status."""
        from core.memory.storage import FileStorage

        storage = FileStorage(base_path=temp_dir)
        storage.save_message("user_123", sample_message)

        result = storage.delete_messages("user_123")

        assert result is True


class TestFileStorageGetMessageCount:
    """Test FileStorage get_message_count functionality."""

    def test_get_message_count(self, temp_dir, sample_messages):
        """Test getting message count."""
        from core.memory.storage import FileStorage

        storage = FileStorage(base_path=temp_dir)
        for msg in sample_messages:
            storage.save_message("user_123", msg)

        count = storage.get_message_count("user_123")

        assert count == 3

    def test_get_message_count_empty_user(self, temp_dir):
        """Test message count for user with no history."""
        from core.memory.storage import FileStorage

        storage = FileStorage(base_path=temp_dir)
        count = storage.get_message_count("nonexistent_user")

        assert count == 0


class TestFileStorageTTL:
    """Test FileStorage TTL (time-to-live) support."""

    def test_ttl_expires_old_messages(self, temp_dir):
        """Test that TTL expires old messages."""
        from core.memory.storage import FileStorage
        from core.memory.conversation import Message

        storage = FileStorage(base_path=temp_dir, ttl_seconds=1)

        # Add a message
        old_msg = Message(
            role="user",
            content="Old message",
            timestamp=datetime.utcnow() - timedelta(seconds=10)
        )
        storage.save_message("user_123", old_msg)

        # Wait and check
        messages = storage.get_messages("user_123")

        assert len(messages) == 0  # Message expired

    def test_ttl_keeps_recent_messages(self, temp_dir, sample_message):
        """Test that TTL keeps recent messages."""
        from core.memory.storage import FileStorage

        storage = FileStorage(base_path=temp_dir, ttl_seconds=3600)
        storage.save_message("user_123", sample_message)

        messages = storage.get_messages("user_123")

        assert len(messages) == 1

    def test_ttl_disabled_by_default(self, temp_dir, sample_message):
        """Test that TTL is disabled by default (no expiration)."""
        from core.memory.storage import FileStorage

        storage = FileStorage(base_path=temp_dir)

        assert storage.ttl_seconds is None


# ==============================================================================
# SQLiteStorage Tests
# ==============================================================================

class TestSQLiteStorageInit:
    """Test SQLiteStorage initialization."""

    def test_init_creates_database(self, temp_db_path):
        """Test that initialization creates database."""
        from core.memory.storage import SQLiteStorage

        storage = SQLiteStorage(db_path=temp_db_path)

        assert temp_db_path.exists()

    def test_init_creates_tables(self, temp_db_path):
        """Test that initialization creates required tables."""
        from core.memory.storage import SQLiteStorage

        storage = SQLiteStorage(db_path=temp_db_path)

        # Verify table exists
        conn = sqlite3.connect(str(temp_db_path))
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='conversation_messages'"
        )
        result = cursor.fetchone()
        conn.close()

        assert result is not None

    def test_init_with_default_path(self):
        """Test initialization with default path."""
        with patch('core.memory.storage.get_default_db_path') as mock_path:
            mock_path.return_value = Path("/tmp/test.db")

            with patch('core.memory.storage.sqlite3.connect'):
                from core.memory.storage import SQLiteStorage

                with patch.object(SQLiteStorage, '_initialize_schema'):
                    storage = SQLiteStorage()
                    mock_path.assert_called_once()


class TestSQLiteStorageSaveMessage:
    """Test SQLiteStorage save_message functionality."""

    def test_save_message_inserts_record(self, temp_db_path, sample_message):
        """Test that save_message inserts database record."""
        from core.memory.storage import SQLiteStorage

        storage = SQLiteStorage(db_path=temp_db_path)
        msg_id = storage.save_message("user_123", sample_message)

        # Verify record exists
        conn = sqlite3.connect(str(temp_db_path))
        cursor = conn.execute(
            "SELECT * FROM conversation_messages WHERE id = ?",
            (msg_id,)
        )
        result = cursor.fetchone()
        conn.close()

        assert result is not None

    def test_save_message_stores_all_fields(self, temp_db_path, sample_message):
        """Test that save_message stores all message fields."""
        from core.memory.storage import SQLiteStorage

        storage = SQLiteStorage(db_path=temp_db_path)
        storage.save_message("user_123", sample_message)

        conn = sqlite3.connect(str(temp_db_path))
        conn.row_factory = sqlite3.Row
        cursor = conn.execute(
            "SELECT * FROM conversation_messages WHERE user_id = ?",
            ("user_123",)
        )
        row = cursor.fetchone()
        conn.close()

        assert row["role"] == "user"
        assert row["content"] == "Hello, world!"


class TestSQLiteStorageGetMessages:
    """Test SQLiteStorage get_messages functionality."""

    def test_get_messages_returns_list(self, temp_db_path, sample_messages):
        """Test that get_messages returns a list."""
        from core.memory.storage import SQLiteStorage

        storage = SQLiteStorage(db_path=temp_db_path)
        for msg in sample_messages:
            storage.save_message("user_123", msg)

        messages = storage.get_messages("user_123")

        assert isinstance(messages, list)
        assert len(messages) == 3

    def test_get_messages_ordered_by_timestamp(self, temp_db_path, sample_messages):
        """Test that messages are ordered by timestamp."""
        from core.memory.storage import SQLiteStorage

        storage = SQLiteStorage(db_path=temp_db_path)
        for msg in sample_messages:
            storage.save_message("user_123", msg)

        messages = storage.get_messages("user_123")

        # Should be ordered oldest to newest
        assert messages[0].id == "msg_001"
        assert messages[-1].id == "msg_003"

    def test_get_messages_with_limit(self, temp_db_path, sample_messages):
        """Test get_messages with limit."""
        from core.memory.storage import SQLiteStorage

        storage = SQLiteStorage(db_path=temp_db_path)
        for msg in sample_messages:
            storage.save_message("user_123", msg)

        messages = storage.get_messages("user_123", limit=2)

        assert len(messages) == 2


class TestSQLiteStorageDeleteMessages:
    """Test SQLiteStorage delete_messages functionality."""

    def test_delete_messages_removes_records(self, temp_db_path, sample_messages):
        """Test that delete_messages removes database records."""
        from core.memory.storage import SQLiteStorage

        storage = SQLiteStorage(db_path=temp_db_path)
        for msg in sample_messages:
            storage.save_message("user_123", msg)

        result = storage.delete_messages("user_123")

        assert result is True

        # Verify records deleted
        messages = storage.get_messages("user_123")
        assert len(messages) == 0


class TestSQLiteStorageGetMessageCount:
    """Test SQLiteStorage get_message_count functionality."""

    def test_get_message_count(self, temp_db_path, sample_messages):
        """Test getting message count."""
        from core.memory.storage import SQLiteStorage

        storage = SQLiteStorage(db_path=temp_db_path)
        for msg in sample_messages:
            storage.save_message("user_123", msg)

        count = storage.get_message_count("user_123")

        assert count == 3


class TestSQLiteStorageTTL:
    """Test SQLiteStorage TTL support."""

    def test_ttl_expires_old_messages(self, temp_db_path):
        """Test that TTL expires old messages on retrieval."""
        from core.memory.storage import SQLiteStorage
        from core.memory.conversation import Message

        storage = SQLiteStorage(db_path=temp_db_path, ttl_seconds=1)

        # Add an old message
        old_msg = Message(
            role="user",
            content="Old message",
            timestamp=datetime.utcnow() - timedelta(seconds=10)
        )
        storage.save_message("user_123", old_msg)

        messages = storage.get_messages("user_123")

        assert len(messages) == 0

    def test_cleanup_expired_messages(self, temp_db_path):
        """Test cleanup of expired messages."""
        from core.memory.storage import SQLiteStorage
        from core.memory.conversation import Message

        storage = SQLiteStorage(db_path=temp_db_path, ttl_seconds=1)

        # Add old message directly to DB
        old_msg = Message(
            role="user",
            content="Very old message",
            timestamp=datetime.utcnow() - timedelta(hours=1)
        )
        storage.save_message("user_123", old_msg)

        # Trigger cleanup
        storage.cleanup_expired()

        count = storage.get_message_count("user_123")
        assert count == 0


# ==============================================================================
# Thread Safety Tests
# ==============================================================================

class TestThreadSafety:
    """Test thread safety of storage backends."""

    def test_file_storage_concurrent_writes(self, temp_dir, sample_message):
        """Test FileStorage handles concurrent writes."""
        from core.memory.storage import FileStorage

        storage = FileStorage(base_path=temp_dir)
        errors = []

        def write_message(msg_num):
            try:
                from core.memory.conversation import Message
                msg = Message(
                    id=f"msg_{msg_num}",
                    role="user",
                    content=f"Message {msg_num}"
                )
                storage.save_message("user_123", msg)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=write_message, args=(i,)) for i in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0

    def test_sqlite_storage_concurrent_writes(self, temp_db_path):
        """Test SQLiteStorage handles concurrent writes."""
        from core.memory.storage import SQLiteStorage

        storage = SQLiteStorage(db_path=temp_db_path)
        errors = []

        def write_message(msg_num):
            try:
                from core.memory.conversation import Message
                msg = Message(
                    id=f"msg_{msg_num}",
                    role="user",
                    content=f"Message {msg_num}"
                )
                storage.save_message("user_123", msg)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=write_message, args=(i,)) for i in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0


# ==============================================================================
# Factory Function Tests
# ==============================================================================

class TestFactoryFunctions:
    """Test storage factory functions."""

    def test_get_default_storage_returns_file_storage(self, temp_dir):
        """Test that get_default_storage returns FileStorage by default."""
        with patch('core.memory.storage.get_default_memory_path', return_value=temp_dir):
            from core.memory.storage import get_default_storage

            storage = get_default_storage()

            from core.memory.storage import FileStorage
            assert isinstance(storage, FileStorage)

    def test_get_default_storage_respects_env_var(self, temp_db_path):
        """Test that get_default_storage respects environment variable."""
        with patch.dict('os.environ', {'CONVERSATION_STORAGE': 'sqlite'}):
            with patch('core.memory.storage.get_default_db_path', return_value=temp_db_path):
                from core.memory.storage import get_default_storage

                storage = get_default_storage()

                from core.memory.storage import SQLiteStorage
                assert isinstance(storage, SQLiteStorage)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
