"""
Tests for core/conversation/session_pruning.py - Context pruning utilities.

Verifies:
- prune_old_contexts(max_age)
- prune_by_count(max_contexts)
- Periodic pruning scheduling

Coverage Target: 90%+
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock


class TestPruneOldContexts:
    """Test prune_old_contexts functionality."""

    def test_prune_removes_old_contexts(self):
        """Test that prune_old_contexts removes expired contexts."""
        from core.conversation.session_pruning import prune_old_contexts
        from core.conversation.session_manager import ConversationManager

        manager = ConversationManager(default_ttl=60)

        ctx1 = manager.get_context("user_1", "chat_1")
        ctx2 = manager.get_context("user_2", "chat_2")

        # Make ctx1 old
        ctx1.last_activity = datetime.utcnow() - timedelta(seconds=120)

        removed = prune_old_contexts(manager, max_age_seconds=60)

        assert removed == 1
        assert manager.context_count() == 1

    def test_prune_keeps_recent_contexts(self):
        """Test that prune keeps recent contexts."""
        from core.conversation.session_pruning import prune_old_contexts
        from core.conversation.session_manager import ConversationManager

        manager = ConversationManager()

        manager.get_context("user_1", "chat_1")
        manager.get_context("user_2", "chat_2")

        removed = prune_old_contexts(manager, max_age_seconds=3600)

        assert removed == 0
        assert manager.context_count() == 2

    def test_prune_with_default_max_age(self):
        """Test prune with default max_age (1 hour)."""
        from core.conversation.session_pruning import prune_old_contexts
        from core.conversation.session_manager import ConversationManager

        manager = ConversationManager()

        ctx = manager.get_context("user_1", "chat_1")
        # Make it older than 1 hour
        ctx.last_activity = datetime.utcnow() - timedelta(hours=2)

        removed = prune_old_contexts(manager)  # Default 3600 seconds

        assert removed == 1

    def test_prune_empty_manager(self):
        """Test prune on empty manager."""
        from core.conversation.session_pruning import prune_old_contexts
        from core.conversation.session_manager import ConversationManager

        manager = ConversationManager()

        removed = prune_old_contexts(manager, max_age_seconds=60)

        assert removed == 0


class TestPruneByCount:
    """Test prune_by_count functionality."""

    def test_prune_removes_oldest_when_over_limit(self):
        """Test that prune_by_count removes oldest contexts when over limit."""
        from core.conversation.session_pruning import prune_by_count
        from core.conversation.session_manager import ConversationManager
        import time

        manager = ConversationManager()

        # Create contexts with slight time differences
        ctx1 = manager.get_context("user_1", "chat_1")
        ctx1.last_activity = datetime.utcnow() - timedelta(minutes=10)

        ctx2 = manager.get_context("user_2", "chat_2")
        ctx2.last_activity = datetime.utcnow() - timedelta(minutes=5)

        ctx3 = manager.get_context("user_3", "chat_3")
        # ctx3 is newest (current time)

        removed = prune_by_count(manager, max_contexts=2)

        assert removed == 1
        assert manager.context_count() == 2
        # Oldest (user_1) should be removed
        assert manager.get_context("user_3", "chat_3") is not None

    def test_prune_keeps_all_when_under_limit(self):
        """Test that prune keeps all contexts when under limit."""
        from core.conversation.session_pruning import prune_by_count
        from core.conversation.session_manager import ConversationManager

        manager = ConversationManager()

        manager.get_context("user_1", "chat_1")
        manager.get_context("user_2", "chat_2")

        removed = prune_by_count(manager, max_contexts=10)

        assert removed == 0
        assert manager.context_count() == 2

    def test_prune_at_exact_limit(self):
        """Test prune when exactly at limit."""
        from core.conversation.session_pruning import prune_by_count
        from core.conversation.session_manager import ConversationManager

        manager = ConversationManager()

        manager.get_context("user_1", "chat_1")
        manager.get_context("user_2", "chat_2")

        removed = prune_by_count(manager, max_contexts=2)

        assert removed == 0
        assert manager.context_count() == 2

    def test_prune_removes_multiple_contexts(self):
        """Test removing multiple contexts at once."""
        from core.conversation.session_pruning import prune_by_count
        from core.conversation.session_manager import ConversationManager

        manager = ConversationManager()

        for i in range(10):
            ctx = manager.get_context(f"user_{i}", f"chat_{i}")
            ctx.last_activity = datetime.utcnow() - timedelta(minutes=10-i)

        removed = prune_by_count(manager, max_contexts=3)

        assert removed == 7
        assert manager.context_count() == 3


class TestPruningScheduler:
    """Test periodic pruning scheduling."""

    def test_create_pruning_task(self):
        """Test creating a pruning background task."""
        from core.conversation.session_pruning import create_pruning_task
        from core.conversation.session_manager import ConversationManager

        manager = ConversationManager()

        task = create_pruning_task(
            manager,
            interval_seconds=60,
            max_age_seconds=3600
        )

        assert task is not None
        assert callable(task)

    def test_pruning_task_runs(self):
        """Test that pruning task executes pruning."""
        from core.conversation.session_pruning import create_pruning_task
        from core.conversation.session_manager import ConversationManager

        manager = ConversationManager()
        ctx = manager.get_context("user_1", "chat_1")
        ctx.last_activity = datetime.utcnow() - timedelta(hours=2)

        task = create_pruning_task(
            manager,
            interval_seconds=1,
            max_age_seconds=3600
        )

        # Execute the task function directly
        result = task()

        assert result["pruned_by_age"] == 1 or result["pruned_by_count"] == 1

    def test_combined_pruning(self):
        """Test combined age and count pruning."""
        from core.conversation.session_pruning import prune_all
        from core.conversation.session_manager import ConversationManager

        manager = ConversationManager()

        # Add some old contexts
        for i in range(5):
            ctx = manager.get_context(f"old_user_{i}", f"chat_{i}")
            ctx.last_activity = datetime.utcnow() - timedelta(hours=2)

        # Add some recent contexts
        for i in range(5):
            manager.get_context(f"new_user_{i}", f"chat_{i}")

        result = prune_all(manager, max_age_seconds=3600, max_contexts=3)

        assert result["pruned_by_age"] == 5
        assert manager.context_count() <= 3


class TestPruningWithStorage:
    """Test pruning with storage backends."""

    def test_prune_updates_storage(self):
        """Test that pruning updates storage backend."""
        from core.conversation.session_pruning import prune_old_contexts
        from core.conversation.session_manager import ConversationManager
        from core.conversation.session_storage import InMemoryStorage

        storage = InMemoryStorage()
        manager = ConversationManager(storage=storage)

        ctx = manager.get_context("user_1", "chat_1")
        ctx.last_activity = datetime.utcnow() - timedelta(hours=2)

        # Save to storage
        storage.save_context(ctx)

        prune_old_contexts(manager, max_age_seconds=3600)

        # Storage should also be cleared
        assert storage.load_context("user_1", "chat_1") is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
