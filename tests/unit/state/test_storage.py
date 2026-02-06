"""
State Storage Tests

Tests for:
- StateStorage abstract interface
- InMemoryStorage implementation
- JSONFileStorage implementation
- RedisStorage stub

Run with: pytest tests/unit/state/test_storage.py -v
"""

import pytest
import os
import json
import tempfile
from pathlib import Path
from typing import Optional


class TestInMemoryStorage:
    """Tests for in-memory state storage."""

    def test_create_storage(self):
        """Can create in-memory storage."""
        from core.state.storage import InMemoryStorage

        storage = InMemoryStorage()
        assert storage is not None

    def test_save_and_get_context(self):
        """Can save and retrieve context."""
        from core.state.storage import InMemoryStorage
        from core.state.context import ConversationContext

        storage = InMemoryStorage()
        ctx = ConversationContext(user_id="user1", chat_id="chat1")
        ctx.state = "testing"

        storage.save(ctx)
        retrieved = storage.get(ctx.key)

        assert retrieved is not None
        assert retrieved.state == "testing"

    def test_get_nonexistent_returns_none(self):
        """Getting nonexistent key returns None."""
        from core.state.storage import InMemoryStorage

        storage = InMemoryStorage()
        result = storage.get("nonexistent_key")

        assert result is None

    def test_delete_context(self):
        """Can delete context."""
        from core.state.storage import InMemoryStorage
        from core.state.context import ConversationContext

        storage = InMemoryStorage()
        ctx = ConversationContext(user_id="user1", chat_id="chat1")
        storage.save(ctx)

        storage.delete(ctx.key)

        assert storage.get(ctx.key) is None

    def test_delete_nonexistent_no_error(self):
        """Deleting nonexistent key doesn't raise error."""
        from core.state.storage import InMemoryStorage

        storage = InMemoryStorage()
        storage.delete("nonexistent")  # Should not raise

    def test_get_by_user_id(self):
        """Can get all contexts for a user."""
        from core.state.storage import InMemoryStorage
        from core.state.context import ConversationContext

        storage = InMemoryStorage()
        ctx1 = ConversationContext(user_id="user1", chat_id="chat1")
        ctx2 = ConversationContext(user_id="user1", chat_id="chat2")
        ctx3 = ConversationContext(user_id="user2", chat_id="chat3")

        storage.save(ctx1)
        storage.save(ctx2)
        storage.save(ctx3)

        user1_contexts = storage.get_by_user_id("user1")

        assert len(user1_contexts) == 2

    def test_clear_expired(self):
        """Can clear expired contexts."""
        from core.state.storage import InMemoryStorage
        from core.state.context import ConversationContext
        import time

        storage = InMemoryStorage()
        expired = ConversationContext(
            user_id="user1", chat_id="chat1", ttl_seconds=0
        )
        fresh = ConversationContext(
            user_id="user2", chat_id="chat2", ttl_seconds=3600
        )

        storage.save(expired)
        storage.save(fresh)
        time.sleep(0.01)

        removed = storage.clear_expired()

        assert removed == 1
        assert storage.get(expired.key) is None
        assert storage.get(fresh.key) is not None


class TestJSONFileStorage:
    """Tests for JSON file-based storage."""

    def test_create_storage(self):
        """Can create file storage with path."""
        from core.state.storage import JSONFileStorage

        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "state.json")
            storage = JSONFileStorage(path)
            assert storage is not None

    def test_save_creates_file(self):
        """Saving context creates file."""
        from core.state.storage import JSONFileStorage
        from core.state.context import ConversationContext

        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "state.json")
            storage = JSONFileStorage(path)
            ctx = ConversationContext(user_id="user1", chat_id="chat1")

            storage.save(ctx)

            assert os.path.exists(path)

    def test_save_and_get(self):
        """Can save and retrieve from file."""
        from core.state.storage import JSONFileStorage
        from core.state.context import ConversationContext

        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "state.json")
            storage = JSONFileStorage(path)
            ctx = ConversationContext(user_id="user1", chat_id="chat1")
            ctx.state = "file_test"
            ctx.data["key"] = "value"

            storage.save(ctx)
            retrieved = storage.get(ctx.key)

            assert retrieved is not None
            assert retrieved.state == "file_test"
            assert retrieved.data["key"] == "value"

    def test_persistence_across_instances(self):
        """Data persists across storage instances."""
        from core.state.storage import JSONFileStorage
        from core.state.context import ConversationContext

        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "state.json")

            # Save with first instance
            storage1 = JSONFileStorage(path)
            ctx = ConversationContext(user_id="user1", chat_id="chat1")
            ctx.state = "persistent"
            storage1.save(ctx)

            # Load with second instance
            storage2 = JSONFileStorage(path)
            retrieved = storage2.get(ctx.key)

            assert retrieved is not None
            assert retrieved.state == "persistent"

    def test_delete_context(self):
        """Can delete context from file storage."""
        from core.state.storage import JSONFileStorage
        from core.state.context import ConversationContext

        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "state.json")
            storage = JSONFileStorage(path)
            ctx = ConversationContext(user_id="user1", chat_id="chat1")

            storage.save(ctx)
            storage.delete(ctx.key)

            assert storage.get(ctx.key) is None

    def test_handles_corrupted_file(self):
        """Handles corrupted JSON file gracefully."""
        from core.state.storage import JSONFileStorage

        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "state.json")

            # Write invalid JSON
            with open(path, "w") as f:
                f.write("not valid json{{{")

            storage = JSONFileStorage(path)
            result = storage.get("any_key")

            assert result is None  # Should not crash


class TestRedisStorageStub:
    """Tests for Redis storage stub."""

    def test_create_redis_storage(self):
        """Can create Redis storage stub."""
        from core.state.storage import RedisStorage

        storage = RedisStorage(host="localhost", port=6379)
        assert storage is not None

    def test_redis_not_connected_by_default(self):
        """Redis storage is not connected by default (stub)."""
        from core.state.storage import RedisStorage

        storage = RedisStorage(host="localhost", port=6379)
        assert storage.is_connected() is False

    def test_redis_operations_when_disconnected(self):
        """Redis operations return None/fail gracefully when disconnected."""
        from core.state.storage import RedisStorage
        from core.state.context import ConversationContext

        storage = RedisStorage(host="localhost", port=6379)
        ctx = ConversationContext(user_id="user1", chat_id="chat1")

        # These should not raise, just return appropriate values
        result = storage.get("any_key")
        assert result is None

        # Save should not raise
        storage.save(ctx)

        # Delete should not raise
        storage.delete("any_key")


class TestStorageInterface:
    """Tests for abstract storage interface."""

    def test_storage_is_abstract(self):
        """StateStorage is an abstract base class."""
        from core.state.storage import StateStorage

        with pytest.raises(TypeError):
            StateStorage()  # Cannot instantiate abstract class

    def test_all_implementations_have_required_methods(self):
        """All storage implementations have required methods."""
        from core.state.storage import InMemoryStorage, JSONFileStorage, RedisStorage

        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "test.json")

            implementations = [
                InMemoryStorage(),
                JSONFileStorage(path),
                RedisStorage(host="localhost", port=6379),
            ]

            for impl in implementations:
                assert hasattr(impl, "save")
                assert hasattr(impl, "get")
                assert hasattr(impl, "delete")
                assert hasattr(impl, "get_by_user_id")
                assert hasattr(impl, "clear_expired")
