"""
Tests for Context Manager Module.

Tests cover:
- Context dataclasses (MasterContext, ActivityContext, ConversationContext)
- Context loading and saving
- Context document management
- Context summarization
"""

import json
import sys
import tempfile
import time
from dataclasses import asdict
from pathlib import Path
from unittest.mock import MagicMock, patch, mock_open

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core import context_manager
from core.context_manager import (
    MasterContext,
    ActivityContext,
    ConversationContext,
    ContextDocument,
    load_master_context,
    save_master_context,
    load_activity_context,
    save_activity_context,
    load_conversation_context,
    save_conversation_context,
)


# =============================================================================
# Test MasterContext Dataclass
# =============================================================================

class TestMasterContext:
    """Test MasterContext dataclass."""

    def test_create_default(self):
        """Should create with default values."""
        ctx = MasterContext()
        assert ctx.user_name == "User"
        assert ctx.user_goals == []
        assert ctx.current_projects == []
        assert ctx.recent_topics == []
        assert ctx.preferences == {}
        assert ctx.learned_patterns == []
        assert ctx.last_updated == 0.0

    def test_create_with_values(self):
        """Should create with custom values."""
        ctx = MasterContext(
            user_name="Alice",
            user_goals=["Build app", "Learn Python"],
            current_projects=["Project X"],
        )
        assert ctx.user_name == "Alice"
        assert len(ctx.user_goals) == 2
        assert "Project X" in ctx.current_projects

    def test_asdict_works(self):
        """Should convert to dictionary."""
        ctx = MasterContext(user_name="Bob")
        data = asdict(ctx)
        assert isinstance(data, dict)
        assert data["user_name"] == "Bob"


# =============================================================================
# Test ActivityContext Dataclass
# =============================================================================

class TestActivityContext:
    """Test ActivityContext dataclass."""

    def test_create_default(self):
        """Should create with default values."""
        ctx = ActivityContext()
        assert ctx.current_app == ""
        assert ctx.current_window == ""
        assert ctx.recent_apps == []
        assert ctx.idle_time == 0.0
        assert ctx.focus_score == 0.0

    def test_create_with_activity(self):
        """Should track current activity."""
        ctx = ActivityContext(
            current_app="VSCode",
            current_window="test.py",
            idle_time=5.0,
            focus_score=0.8,
        )
        assert ctx.current_app == "VSCode"
        assert ctx.current_window == "test.py"
        assert ctx.focus_score == 0.8


# =============================================================================
# Test ConversationContext Dataclass
# =============================================================================

class TestConversationContext:
    """Test ConversationContext dataclass."""

    def test_create_default(self):
        """Should create with default values."""
        ctx = ConversationContext()
        assert ctx.recent_messages == []
        assert ctx.pending_tasks == []
        assert ctx.mentioned_topics == []
        assert ctx.action_history == []
        assert ctx.session_start == 0.0

    def test_track_messages(self):
        """Should track recent messages."""
        ctx = ConversationContext(
            recent_messages=[
                {"role": "user", "content": "Hello"},
                {"role": "assistant", "content": "Hi there!"},
            ]
        )
        assert len(ctx.recent_messages) == 2
        assert ctx.recent_messages[0]["role"] == "user"


# =============================================================================
# Test ContextDocument Dataclass
# =============================================================================

class TestContextDocument:
    """Test ContextDocument dataclass."""

    def test_create_document(self):
        """Should create context document."""
        doc = ContextDocument(
            doc_id="doc-001",
            title="Test Document",
            source="test_source",
            category="notes",
            summary="A test document",
            path="/path/to/doc",
            created_at=time.time(),
        )
        assert doc.doc_id == "doc-001"
        assert doc.title == "Test Document"
        assert doc.category == "notes"

    def test_document_with_tags(self):
        """Should accept tags list."""
        doc = ContextDocument(
            doc_id="doc-002",
            title="Tagged Document",
            source="test",
            category="research",
            summary="Has tags",
            path="/path",
            created_at=time.time(),
            tags=["python", "testing"],
        )
        assert "python" in doc.tags
        assert "testing" in doc.tags


# =============================================================================
# Test Context Loading and Saving
# =============================================================================

class TestContextPersistence:
    """Test context persistence functions."""

    def test_load_master_context_returns_default_when_no_file(self):
        """Should return default context when file doesn't exist."""
        with patch.object(context_manager, "MASTER_CONTEXT_FILE") as mock_path:
            mock_path.exists.return_value = False
            ctx = load_master_context()
            assert isinstance(ctx, MasterContext)
            assert ctx.user_name == "User"

    def test_load_master_context_from_file(self):
        """Should load context from file."""
        test_data = {
            "user_name": "TestUser",
            "user_goals": ["Goal 1"],
            "current_projects": [],
            "recent_topics": [],
            "preferences": {},
            "learned_patterns": [],
            "last_updated": 1234567890.0,
        }

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(test_data, f)
            f.flush()
            temp_path = Path(f.name)

        try:
            with patch.object(context_manager, "MASTER_CONTEXT_FILE", temp_path):
                with patch.object(context_manager, "_ensure_paths"):
                    ctx = load_master_context()
                    assert ctx.user_name == "TestUser"
                    assert ctx.user_goals == ["Goal 1"]
        finally:
            temp_path.unlink()

    def test_save_master_context_updates_timestamp(self):
        """Should update last_updated timestamp."""
        ctx = MasterContext(user_name="Test")
        original_time = ctx.last_updated

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            temp_path = Path(f.name)

        try:
            with patch.object(context_manager, "MASTER_CONTEXT_FILE", temp_path):
                with patch.object(context_manager, "_ensure_paths"):
                    save_master_context(ctx)
                    assert ctx.last_updated > original_time
        finally:
            temp_path.unlink()

    def test_load_activity_context_default(self):
        """Should return default activity context."""
        with patch.object(context_manager, "ACTIVITY_CONTEXT_FILE") as mock_path:
            mock_path.exists.return_value = False
            ctx = load_activity_context()
            assert isinstance(ctx, ActivityContext)
            assert ctx.current_app == ""

    def test_load_conversation_context_default(self):
        """Should return default conversation context."""
        with patch.object(context_manager, "CONVERSATION_CONTEXT_FILE") as mock_path:
            mock_path.exists.return_value = False
            ctx = load_conversation_context()
            assert isinstance(ctx, ConversationContext)
            assert ctx.recent_messages == []


# =============================================================================
# Test Context Updates
# =============================================================================

class TestContextUpdates:
    """Test context update functions."""

    def test_master_context_update_goals(self):
        """Should be able to update goals."""
        ctx = MasterContext()
        ctx.user_goals.append("New Goal")
        assert "New Goal" in ctx.user_goals

    def test_activity_context_update_app(self):
        """Should be able to update current app."""
        ctx = ActivityContext()
        ctx.current_app = "Firefox"
        ctx.timestamp = time.time()
        assert ctx.current_app == "Firefox"

    def test_conversation_context_add_message(self):
        """Should be able to add messages."""
        ctx = ConversationContext()
        ctx.recent_messages.append({"role": "user", "content": "Test"})
        assert len(ctx.recent_messages) == 1


# =============================================================================
# Test Ensure Paths
# =============================================================================

class TestEnsurePaths:
    """Test path creation function."""

    def test_ensure_paths_creates_directories(self):
        """Should create context directories without error."""
        # Just verify the function runs without error
        # Actual directory creation depends on filesystem
        try:
            context_manager._ensure_paths()
        except Exception as e:
            pytest.fail(f"_ensure_paths should not raise: {e}")
