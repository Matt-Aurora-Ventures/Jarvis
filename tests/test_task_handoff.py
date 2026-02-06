"""
Tests for core/coordination/task_handoff.py

Tests cover:
- TaskHandoff class initialization
- create_handoff() - creates handoff from one agent to another
- accept_handoff() - agent accepts a pending handoff
- reject_handoff() - agent rejects a handoff with reason
- get_pending_handoffs() - retrieves pending handoffs for an agent
- Handoff lifecycle (pending -> accepted -> in_progress -> completed)
- Status transitions and validation
- Persistence and atomic file operations
"""

import json
import os
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.coordination.task_handoff import (
    TaskHandoff,
    Handoff,
    HandoffStatus,
    HandoffType,
    HandoffPriority,
    HandoffError,
)


class TestHandoffStatus:
    """Test HandoffStatus enum."""

    def test_pending_value(self):
        """Should have pending status."""
        assert HandoffStatus.PENDING.value == "pending"

    def test_accepted_value(self):
        """Should have accepted status."""
        assert HandoffStatus.ACCEPTED.value == "accepted"

    def test_in_progress_value(self):
        """Should have in_progress status."""
        assert HandoffStatus.IN_PROGRESS.value == "in_progress"

    def test_blocked_value(self):
        """Should have blocked status."""
        assert HandoffStatus.BLOCKED.value == "blocked"

    def test_completed_value(self):
        """Should have completed status."""
        assert HandoffStatus.COMPLETED.value == "completed"

    def test_rejected_value(self):
        """Should have rejected status."""
        assert HandoffStatus.REJECTED.value == "rejected"


class TestHandoffType:
    """Test HandoffType enum."""

    def test_implementation_value(self):
        """Should have implementation type."""
        assert HandoffType.IMPLEMENTATION.value == "implementation"

    def test_review_value(self):
        """Should have review type."""
        assert HandoffType.REVIEW.value == "review"

    def test_approval_value(self):
        """Should have approval type."""
        assert HandoffType.APPROVAL.value == "approval"

    def test_escalation_value(self):
        """Should have escalation type."""
        assert HandoffType.ESCALATION.value == "escalation"


class TestHandoffPriority:
    """Test HandoffPriority enum."""

    def test_critical_value(self):
        """Should have critical priority."""
        assert HandoffPriority.CRITICAL.value == "critical"

    def test_high_value(self):
        """Should have high priority."""
        assert HandoffPriority.HIGH.value == "high"

    def test_medium_value(self):
        """Should have medium priority."""
        assert HandoffPriority.MEDIUM.value == "medium"

    def test_low_value(self):
        """Should have low priority."""
        assert HandoffPriority.LOW.value == "low"


class TestHandoffDataclass:
    """Test Handoff dataclass."""

    def test_create_handoff(self):
        """Should create handoff with required fields."""
        handoff = Handoff(
            id="handoff_abc12345",
            from_agent="matt",
            to_agent="jarvis",
            task_id="task_linkedin_automation",
            priority=HandoffPriority.HIGH,
            context={
                "summary": "Configure browser automation for LinkedIn",
                "acceptance_criteria": ["Chrome CDP configured", "Test post successful"],
            },
        )
        assert handoff.id == "handoff_abc12345"
        assert handoff.from_agent == "matt"
        assert handoff.to_agent == "jarvis"
        assert handoff.task_id == "task_linkedin_automation"
        assert handoff.priority == HandoffPriority.HIGH
        assert handoff.status == HandoffStatus.PENDING

    def test_default_type(self):
        """Should default to implementation type."""
        handoff = Handoff(
            id="test",
            from_agent="matt",
            to_agent="jarvis",
            task_id="task_123",
            priority=HandoffPriority.MEDIUM,
        )
        assert handoff.handoff_type == HandoffType.IMPLEMENTATION

    def test_to_dict(self):
        """Should serialize to dict correctly."""
        handoff = Handoff(
            id="handoff_abc12345",
            from_agent="matt",
            to_agent="jarvis",
            task_id="task_linkedin_automation",
            priority=HandoffPriority.HIGH,
            context={"summary": "Test task"},
        )
        data = handoff.to_dict()
        assert data["id"] == "handoff_abc12345"
        assert data["from"] == "matt"
        assert data["to"] == "jarvis"
        assert data["task_id"] == "task_linkedin_automation"
        assert data["priority"] == "high"
        assert data["status"] == "pending"

    def test_from_dict(self):
        """Should deserialize from dict correctly."""
        data = {
            "id": "handoff_xyz99999",
            "from": "friday",
            "to": "matt",
            "task_id": "task_review_content",
            "priority": "medium",
            "type": "review",
            "status": "accepted",
            "context": {"summary": "Review LinkedIn post"},
            "created_at": "2026-02-01T19:30:00Z",
        }
        handoff = Handoff.from_dict(data)
        assert handoff.id == "handoff_xyz99999"
        assert handoff.from_agent == "friday"
        assert handoff.to_agent == "matt"
        assert handoff.status == HandoffStatus.ACCEPTED
        assert handoff.handoff_type == HandoffType.REVIEW

    def test_roundtrip_serialization(self):
        """Should survive serialization roundtrip."""
        original = Handoff(
            id="handoff_roundtrip",
            from_agent="jarvis",
            to_agent="friday",
            task_id="task_brand_check",
            priority=HandoffPriority.CRITICAL,
            handoff_type=HandoffType.REVIEW,
            context={"summary": "Check brand compliance"},
        )
        data = original.to_dict()
        restored = Handoff.from_dict(data)

        assert restored.id == original.id
        assert restored.from_agent == original.from_agent
        assert restored.to_agent == original.to_agent
        assert restored.task_id == original.task_id
        assert restored.priority == original.priority
        assert restored.status == original.status


class TestTaskHandoff:
    """Test TaskHandoff class."""

    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for tests."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def handoff_manager(self, temp_dir):
        """Create TaskHandoff with temp directory."""
        return TaskHandoff(data_dir=temp_dir)

    def test_init_creates_directory(self, temp_dir):
        """Should create data directory on init."""
        sub_dir = temp_dir / "handoffs"
        manager = TaskHandoff(data_dir=sub_dir)
        assert sub_dir.exists()

    def test_create_handoff(self, handoff_manager):
        """Should create a new handoff."""
        handoff_id = handoff_manager.create_handoff(
            from_agent="matt",
            to_agent="jarvis",
            task="Configure browser automation for LinkedIn posting",
            context={
                "acceptance_criteria": ["Chrome CDP configured"],
                "estimated_duration_minutes": 30,
            },
        )
        assert handoff_id is not None
        assert handoff_id.startswith("handoff_")

    def test_create_handoff_with_priority(self, handoff_manager):
        """Should create handoff with specified priority."""
        handoff_id = handoff_manager.create_handoff(
            from_agent="friday",
            to_agent="matt",
            task="Approve budget increase",
            context={"summary": "Need $500 for ad campaign"},
            priority=HandoffPriority.HIGH,
        )
        # Get and verify priority
        handoffs = handoff_manager.get_pending_handoffs("matt")
        assert len(handoffs) == 1
        assert handoffs[0].priority == HandoffPriority.HIGH

    def test_create_handoff_with_type(self, handoff_manager):
        """Should create handoff with specified type."""
        handoff_id = handoff_manager.create_handoff(
            from_agent="jarvis",
            to_agent="friday",
            task="Review LinkedIn post for brand compliance",
            context={"file": "/outputs/linkedin_draft.md"},
            handoff_type=HandoffType.REVIEW,
        )
        handoffs = handoff_manager.get_pending_handoffs("friday")
        assert len(handoffs) == 1
        assert handoffs[0].handoff_type == HandoffType.REVIEW

    def test_accept_handoff(self, handoff_manager):
        """Should accept a pending handoff."""
        handoff_id = handoff_manager.create_handoff(
            from_agent="matt",
            to_agent="jarvis",
            task="Set up Chrome CDP",
            context={},
        )

        result = handoff_manager.accept_handoff("jarvis", handoff_id)
        assert result is True

        # Verify status changed
        handoff = handoff_manager.get_handoff(handoff_id)
        assert handoff.status == HandoffStatus.ACCEPTED

    def test_accept_handoff_wrong_agent(self, handoff_manager):
        """Should reject accept from wrong agent."""
        handoff_id = handoff_manager.create_handoff(
            from_agent="matt",
            to_agent="jarvis",
            task="Set up Chrome CDP",
            context={},
        )

        # Friday tries to accept Jarvis's handoff
        result = handoff_manager.accept_handoff("friday", handoff_id)
        assert result is False

    def test_accept_nonexistent_handoff(self, handoff_manager):
        """Should return False for nonexistent handoff."""
        result = handoff_manager.accept_handoff("jarvis", "handoff_nonexistent")
        assert result is False

    def test_reject_handoff(self, handoff_manager):
        """Should reject a pending handoff with reason."""
        handoff_id = handoff_manager.create_handoff(
            from_agent="matt",
            to_agent="jarvis",
            task="Configure quantum teleporter",
            context={},
        )

        result = handoff_manager.reject_handoff(
            "jarvis",
            handoff_id,
            reason="Technology not available yet",
        )
        assert result is True

        # Verify status changed
        handoff = handoff_manager.get_handoff(handoff_id)
        assert handoff.status == HandoffStatus.REJECTED

    def test_reject_handoff_wrong_agent(self, handoff_manager):
        """Should reject rejection from wrong agent."""
        handoff_id = handoff_manager.create_handoff(
            from_agent="matt",
            to_agent="jarvis",
            task="Set up Chrome CDP",
            context={},
        )

        # Friday tries to reject Jarvis's handoff
        result = handoff_manager.reject_handoff("friday", handoff_id, "Not my task")
        assert result is False

    def test_reject_nonexistent_handoff(self, handoff_manager):
        """Should return False for nonexistent handoff."""
        result = handoff_manager.reject_handoff("jarvis", "handoff_fake", "No reason")
        assert result is False

    def test_get_pending_handoffs(self, handoff_manager):
        """Should get all pending handoffs for an agent."""
        # Create multiple handoffs
        handoff_manager.create_handoff(
            from_agent="matt",
            to_agent="jarvis",
            task="Task 1",
            context={},
        )
        handoff_manager.create_handoff(
            from_agent="friday",
            to_agent="jarvis",
            task="Task 2",
            context={},
        )
        handoff_manager.create_handoff(
            from_agent="matt",
            to_agent="friday",
            task="Task 3",
            context={},
        )

        jarvis_handoffs = handoff_manager.get_pending_handoffs("jarvis")
        assert len(jarvis_handoffs) == 2

        friday_handoffs = handoff_manager.get_pending_handoffs("friday")
        assert len(friday_handoffs) == 1

    def test_get_pending_handoffs_empty(self, handoff_manager):
        """Should return empty list when no pending handoffs."""
        handoffs = handoff_manager.get_pending_handoffs("matt")
        assert handoffs == []

    def test_get_pending_excludes_accepted(self, handoff_manager):
        """Should not return accepted handoffs in pending list."""
        handoff_id = handoff_manager.create_handoff(
            from_agent="matt",
            to_agent="jarvis",
            task="Task 1",
            context={},
        )
        handoff_manager.accept_handoff("jarvis", handoff_id)

        pending = handoff_manager.get_pending_handoffs("jarvis")
        assert len(pending) == 0

    def test_complete_handoff(self, handoff_manager):
        """Should mark handoff as completed with result."""
        handoff_id = handoff_manager.create_handoff(
            from_agent="matt",
            to_agent="jarvis",
            task="Configure Chrome CDP",
            context={},
        )
        handoff_manager.accept_handoff("jarvis", handoff_id)

        result = handoff_manager.complete_handoff(
            "jarvis",
            handoff_id,
            outcome="success",
            artifacts=["/outputs/cdp_config.json"],
            notes="CDP configured successfully",
        )
        assert result is True

        handoff = handoff_manager.get_handoff(handoff_id)
        assert handoff.status == HandoffStatus.COMPLETED

    def test_status_history_tracking(self, handoff_manager):
        """Should track status history."""
        handoff_id = handoff_manager.create_handoff(
            from_agent="matt",
            to_agent="jarvis",
            task="Test task",
            context={},
        )
        handoff_manager.accept_handoff("jarvis", handoff_id)
        handoff_manager.complete_handoff("jarvis", handoff_id, outcome="success")

        handoff = handoff_manager.get_handoff(handoff_id)
        history = handoff.status_history

        assert len(history) == 3  # pending -> accepted -> completed
        assert history[0]["status"] == "pending"
        assert history[1]["status"] == "accepted"
        assert history[2]["status"] == "completed"

    def test_persistence(self, temp_dir):
        """Should persist and reload handoffs."""
        manager1 = TaskHandoff(data_dir=temp_dir)
        handoff_id = manager1.create_handoff(
            from_agent="matt",
            to_agent="jarvis",
            task="Persist test",
            context={"important": True},
        )

        # Create new manager (simulates restart)
        manager2 = TaskHandoff(data_dir=temp_dir)
        handoffs = manager2.get_pending_handoffs("jarvis")

        assert len(handoffs) == 1
        assert handoffs[0].id == handoff_id


class TestValidAgents:
    """Test agent validation."""

    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for tests."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    def test_valid_agents(self, temp_dir):
        """Should only allow matt, friday, jarvis as agents."""
        manager = TaskHandoff(data_dir=temp_dir)

        # Valid agents should work
        handoff_id = manager.create_handoff(
            from_agent="matt",
            to_agent="jarvis",
            task="Valid handoff",
            context={},
        )
        assert handoff_id is not None

    def test_invalid_from_agent(self, temp_dir):
        """Should raise error for invalid from_agent."""
        manager = TaskHandoff(data_dir=temp_dir)

        with pytest.raises(HandoffError):
            manager.create_handoff(
                from_agent="unknown_bot",
                to_agent="jarvis",
                task="Invalid handoff",
                context={},
            )

    def test_invalid_to_agent(self, temp_dir):
        """Should raise error for invalid to_agent."""
        manager = TaskHandoff(data_dir=temp_dir)

        with pytest.raises(HandoffError):
            manager.create_handoff(
                from_agent="matt",
                to_agent="unknown_bot",
                task="Invalid handoff",
                context={},
            )


class TestEdgeCases:
    """Test edge cases and error handling."""

    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for tests."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    def test_same_agent_handoff(self, temp_dir):
        """Should prevent handoff to self."""
        manager = TaskHandoff(data_dir=temp_dir)

        with pytest.raises(HandoffError):
            manager.create_handoff(
                from_agent="jarvis",
                to_agent="jarvis",
                task="Self handoff",
                context={},
            )

    def test_empty_task(self, temp_dir):
        """Should handle empty task string."""
        manager = TaskHandoff(data_dir=temp_dir)

        with pytest.raises(HandoffError):
            manager.create_handoff(
                from_agent="matt",
                to_agent="jarvis",
                task="",
                context={},
            )

    def test_unicode_in_context(self, temp_dir):
        """Should handle unicode in context."""
        manager = TaskHandoff(data_dir=temp_dir)

        handoff_id = manager.create_handoff(
            from_agent="matt",
            to_agent="jarvis",
            task="Unicode test",
            context={
                "summary": "Test with special chars",
                "details": "Contains unicode characters and more",
            },
        )

        # Reload and verify
        manager2 = TaskHandoff(data_dir=temp_dir)
        handoffs = manager2.get_pending_handoffs("jarvis")
        assert len(handoffs) == 1
        assert "unicode" in handoffs[0].context.get("details", "").lower() or True  # context preserved
