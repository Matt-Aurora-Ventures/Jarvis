"""
Tests for core/conversation/session_storage.py - Context storage backends.

Verifies:
- ContextStorage abstract interface
- InMemoryStorage implementation
- FileStorage implementation (persistent JSON)
- save_context() and load_context() operations

Coverage Target: 90%+
"""

import pytest
import os
import json
import tempfile
import shutil
from datetime import datetime
from unittest.mock import Mock, patch, mock_open


class TestContextStorageInterface:
    """Test abstract ContextStorage interface."""

    def test_abstract_class_cannot_be_instantiated(self):
        """Test that ContextStorage is abstract."""
        from core.conversation.session_storage import ContextStorage

        with pytest.raises(TypeError):
            ContextStorage()

    def test_interface_defines_required_methods(self):
        """Test that interface defines required methods."""
        from core.conversation.session_storage import ContextStorage
        import abc

        # Check that abstract methods exist
        assert hasattr(ContextStorage, 'save_context')
        assert hasattr(ContextStorage, 'load_context')
        assert hasattr(ContextStorage, 'delete_context')
        assert hasattr(ContextStorage, 'list_contexts')


class TestInMemoryStorage:
    """Test InMemoryStorage implementation."""

    def test_save_context(self):
        """Test saving context to memory."""
        from core.conversation.session_storage import InMemoryStorage
        from core.conversation.session_context import ConversationContext

        storage = InMemoryStorage()
        ctx = ConversationContext(
            user_id="user_123",
            chat_id="chat_456",
            bot_name="jarvis"
        )
        ctx.add_message("user", "Hello!")

        result = storage.save_context(ctx)

        assert result is True

    def test_load_context(self):
        """Test loading context from memory."""
        from core.conversation.session_storage import InMemoryStorage
        from core.conversation.session_context import ConversationContext

        storage = InMemoryStorage()
        ctx = ConversationContext(
            user_id="user_123",
            chat_id="chat_456",
            bot_name="jarvis"
        )
        ctx.add_message("user", "Hello!")
        storage.save_context(ctx)

        loaded = storage.load_context("user_123", "chat_456")

        assert loaded is not None
        assert loaded.user_id == "user_123"
        assert len(loaded.history) == 1

    def test_load_nonexistent_returns_none(self):
        """Test loading nonexistent context returns None."""
        from core.conversation.session_storage import InMemoryStorage

        storage = InMemoryStorage()

        loaded = storage.load_context("nonexistent", "nonexistent")

        assert loaded is None

    def test_delete_context(self):
        """Test deleting context from memory."""
        from core.conversation.session_storage import InMemoryStorage
        from core.conversation.session_context import ConversationContext

        storage = InMemoryStorage()
        ctx = ConversationContext(
            user_id="user_123",
            chat_id="chat_456",
            bot_name="jarvis"
        )
        storage.save_context(ctx)

        result = storage.delete_context("user_123", "chat_456")

        assert result is True
        assert storage.load_context("user_123", "chat_456") is None

    def test_delete_nonexistent_returns_false(self):
        """Test deleting nonexistent context returns False."""
        from core.conversation.session_storage import InMemoryStorage

        storage = InMemoryStorage()

        result = storage.delete_context("nonexistent", "nonexistent")

        assert result is False

    def test_list_contexts_empty(self):
        """Test listing contexts when empty."""
        from core.conversation.session_storage import InMemoryStorage

        storage = InMemoryStorage()

        contexts = storage.list_contexts()

        assert contexts == []

    def test_list_contexts(self):
        """Test listing all stored contexts."""
        from core.conversation.session_storage import InMemoryStorage
        from core.conversation.session_context import ConversationContext

        storage = InMemoryStorage()
        storage.save_context(ConversationContext("user_1", "chat_1", "bot"))
        storage.save_context(ConversationContext("user_2", "chat_2", "bot"))

        contexts = storage.list_contexts()

        assert len(contexts) == 2

    def test_count_contexts(self):
        """Test counting stored contexts."""
        from core.conversation.session_storage import InMemoryStorage
        from core.conversation.session_context import ConversationContext

        storage = InMemoryStorage()
        storage.save_context(ConversationContext("user_1", "chat_1", "bot"))
        storage.save_context(ConversationContext("user_2", "chat_2", "bot"))

        assert storage.count() == 2

    def test_clear_all(self):
        """Test clearing all contexts."""
        from core.conversation.session_storage import InMemoryStorage
        from core.conversation.session_context import ConversationContext

        storage = InMemoryStorage()
        storage.save_context(ConversationContext("user_1", "chat_1", "bot"))
        storage.save_context(ConversationContext("user_2", "chat_2", "bot"))

        storage.clear_all()

        assert storage.count() == 0


class TestFileStorage:
    """Test FileStorage implementation."""

    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for testing."""
        dirpath = tempfile.mkdtemp()
        yield dirpath
        shutil.rmtree(dirpath)

    def test_init_creates_directory(self, temp_dir):
        """Test that FileStorage creates directory if not exists."""
        from core.conversation.session_storage import FileStorage

        storage_path = os.path.join(temp_dir, "conversations")
        storage = FileStorage(storage_path)

        assert os.path.exists(storage_path)

    def test_save_context_creates_file(self, temp_dir):
        """Test that save_context creates JSON file."""
        from core.conversation.session_storage import FileStorage
        from core.conversation.session_context import ConversationContext

        storage = FileStorage(temp_dir)
        ctx = ConversationContext(
            user_id="user_123",
            chat_id="chat_456",
            bot_name="jarvis"
        )
        ctx.add_message("user", "Hello!")

        result = storage.save_context(ctx)

        assert result is True
        # Check file exists
        expected_file = os.path.join(temp_dir, "user_123_chat_456.json")
        assert os.path.exists(expected_file)

    def test_load_context_from_file(self, temp_dir):
        """Test loading context from JSON file."""
        from core.conversation.session_storage import FileStorage
        from core.conversation.session_context import ConversationContext

        storage = FileStorage(temp_dir)
        ctx = ConversationContext(
            user_id="user_123",
            chat_id="chat_456",
            bot_name="jarvis"
        )
        ctx.add_message("user", "Hello!")
        storage.save_context(ctx)

        loaded = storage.load_context("user_123", "chat_456")

        assert loaded is not None
        assert loaded.user_id == "user_123"
        assert len(loaded.history) == 1
        assert loaded.history[0]["content"] == "Hello!"

    def test_load_nonexistent_file(self, temp_dir):
        """Test loading from nonexistent file returns None."""
        from core.conversation.session_storage import FileStorage

        storage = FileStorage(temp_dir)

        loaded = storage.load_context("nonexistent", "nonexistent")

        assert loaded is None

    def test_delete_context_removes_file(self, temp_dir):
        """Test that delete_context removes JSON file."""
        from core.conversation.session_storage import FileStorage
        from core.conversation.session_context import ConversationContext

        storage = FileStorage(temp_dir)
        ctx = ConversationContext("user_123", "chat_456", "jarvis")
        storage.save_context(ctx)

        result = storage.delete_context("user_123", "chat_456")

        assert result is True
        expected_file = os.path.join(temp_dir, "user_123_chat_456.json")
        assert not os.path.exists(expected_file)

    def test_list_contexts(self, temp_dir):
        """Test listing all contexts from files."""
        from core.conversation.session_storage import FileStorage
        from core.conversation.session_context import ConversationContext

        storage = FileStorage(temp_dir)
        storage.save_context(ConversationContext("user_1", "chat_1", "bot"))
        storage.save_context(ConversationContext("user_2", "chat_2", "bot"))

        contexts = storage.list_contexts()

        assert len(contexts) == 2

    def test_file_content_is_valid_json(self, temp_dir):
        """Test that saved file contains valid JSON."""
        from core.conversation.session_storage import FileStorage
        from core.conversation.session_context import ConversationContext

        storage = FileStorage(temp_dir)
        ctx = ConversationContext("user_123", "chat_456", "jarvis")
        ctx.add_message("user", "Hello!")
        storage.save_context(ctx)

        file_path = os.path.join(temp_dir, "user_123_chat_456.json")
        with open(file_path, 'r') as f:
            data = json.load(f)

        assert data["user_id"] == "user_123"
        assert data["chat_id"] == "chat_456"
        assert len(data["history"]) == 1

    def test_handles_special_characters_in_ids(self, temp_dir):
        """Test handling special characters in user/chat IDs."""
        from core.conversation.session_storage import FileStorage
        from core.conversation.session_context import ConversationContext

        storage = FileStorage(temp_dir)
        ctx = ConversationContext(
            user_id="user@123",
            chat_id="chat#456",
            bot_name="jarvis"
        )

        result = storage.save_context(ctx)
        loaded = storage.load_context("user@123", "chat#456")

        assert result is True
        assert loaded is not None
        assert loaded.user_id == "user@123"


class TestFileStorageEdgeCases:
    """Test FileStorage edge cases and error handling."""

    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for testing."""
        dirpath = tempfile.mkdtemp()
        yield dirpath
        shutil.rmtree(dirpath)

    def test_handles_corrupted_json(self, temp_dir):
        """Test handling of corrupted JSON files."""
        from core.conversation.session_storage import FileStorage

        storage = FileStorage(temp_dir)

        # Write corrupted JSON
        file_path = os.path.join(temp_dir, "user_123_chat_456.json")
        with open(file_path, 'w') as f:
            f.write("not valid json{")

        loaded = storage.load_context("user_123", "chat_456")

        assert loaded is None

    def test_concurrent_access_safety(self, temp_dir):
        """Test basic concurrent access handling."""
        from core.conversation.session_storage import FileStorage
        from core.conversation.session_context import ConversationContext
        import threading

        storage = FileStorage(temp_dir)
        errors = []

        def save_context(user_id):
            try:
                ctx = ConversationContext(user_id, "chat_1", "bot")
                ctx.add_message("user", f"Message from {user_id}")
                storage.save_context(ctx)
            except Exception as e:
                errors.append(e)

        threads = [
            threading.Thread(target=save_context, args=(f"user_{i}",))
            for i in range(5)
        ]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert storage.count() == 5


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
