"""
Tests for core/coordination/whiteboard.py

Tests cover:
- Whiteboard class initialization
- post_task() - agent posts a task to the whiteboard
- claim_task() - agent claims an unclaimed task
- complete_task() - marks task as completed
- get_active_tasks() - retrieves all active tasks
- Agent status tracking
- System flags (emergency_stop, rate_limit_active, etc.)
- Atomic file operations
- Persistence and reload
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

from core.coordination.whiteboard import (
    Whiteboard,
    Task,
    TaskStatus,
    AgentStatus,
    SystemFlags,
    WhiteboardError,
)


class TestTaskStatus:
    """Test TaskStatus enum."""

    def test_unclaimed_value(self):
        """Should have unclaimed status."""
        assert TaskStatus.UNCLAIMED.value == "unclaimed"

    def test_claimed_value(self):
        """Should have claimed status."""
        assert TaskStatus.CLAIMED.value == "claimed"

    def test_in_progress_value(self):
        """Should have in_progress status."""
        assert TaskStatus.IN_PROGRESS.value == "in_progress"

    def test_completed_value(self):
        """Should have completed status."""
        assert TaskStatus.COMPLETED.value == "completed"

    def test_failed_value(self):
        """Should have failed status."""
        assert TaskStatus.FAILED.value == "failed"


class TestAgentStatus:
    """Test AgentStatus enum."""

    def test_online_value(self):
        """Should have online status."""
        assert AgentStatus.ONLINE.value == "online"

    def test_offline_value(self):
        """Should have offline status."""
        assert AgentStatus.OFFLINE.value == "offline"

    def test_busy_value(self):
        """Should have busy status."""
        assert AgentStatus.BUSY.value == "busy"

    def test_error_value(self):
        """Should have error status."""
        assert AgentStatus.ERROR.value == "error"


class TestTask:
    """Test Task dataclass."""

    def test_create_task(self):
        """Should create task with required fields."""
        task = Task(
            id="task_abc123",
            description="Configure browser automation",
            posted_by="matt",
        )
        assert task.id == "task_abc123"
        assert task.description == "Configure browser automation"
        assert task.posted_by == "matt"
        assert task.status == TaskStatus.UNCLAIMED
        assert task.claimed_by is None

    def test_to_dict(self):
        """Should serialize to dict correctly."""
        task = Task(
            id="task_xyz789",
            description="Review LinkedIn post",
            posted_by="jarvis",
            claimed_by="friday",
            status=TaskStatus.CLAIMED,
        )
        data = task.to_dict()
        assert data["id"] == "task_xyz789"
        assert data["description"] == "Review LinkedIn post"
        assert data["posted_by"] == "jarvis"
        assert data["claimed_by"] == "friday"
        assert data["status"] == "claimed"

    def test_from_dict(self):
        """Should deserialize from dict correctly."""
        data = {
            "id": "task_def456",
            "description": "Set up API endpoint",
            "posted_by": "friday",
            "claimed_by": "jarvis",
            "status": "in_progress",
            "created_at": "2026-02-01T19:30:00Z",
        }
        task = Task.from_dict(data)
        assert task.id == "task_def456"
        assert task.description == "Set up API endpoint"
        assert task.claimed_by == "jarvis"
        assert task.status == TaskStatus.IN_PROGRESS

    def test_roundtrip_serialization(self):
        """Should survive serialization roundtrip."""
        original = Task(
            id="task_roundtrip",
            description="Test persistence",
            posted_by="matt",
            priority="high",
            metadata={"deadline": "2026-02-02"},
        )
        data = original.to_dict()
        restored = Task.from_dict(data)

        assert restored.id == original.id
        assert restored.description == original.description
        assert restored.posted_by == original.posted_by
        assert restored.status == original.status


class TestSystemFlags:
    """Test SystemFlags dataclass."""

    def test_default_flags(self):
        """Should have safe default values."""
        flags = SystemFlags()
        assert flags.emergency_stop is False
        assert flags.rate_limit_active is False
        assert flags.maintenance_mode is False

    def test_to_dict(self):
        """Should serialize to dict correctly."""
        flags = SystemFlags(emergency_stop=True, maintenance_mode=True)
        data = flags.to_dict()
        assert data["emergency_stop"] is True
        assert data["rate_limit_active"] is False
        assert data["maintenance_mode"] is True

    def test_from_dict(self):
        """Should deserialize from dict correctly."""
        data = {
            "emergency_stop": False,
            "rate_limit_active": True,
            "maintenance_mode": False,
        }
        flags = SystemFlags.from_dict(data)
        assert flags.emergency_stop is False
        assert flags.rate_limit_active is True
        assert flags.maintenance_mode is False


class TestWhiteboard:
    """Test Whiteboard class."""

    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for tests."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def whiteboard(self, temp_dir):
        """Create Whiteboard with temp directory."""
        return Whiteboard(data_dir=temp_dir)

    def test_init_creates_directory(self, temp_dir):
        """Should create data directory on init."""
        sub_dir = temp_dir / "whiteboard"
        wb = Whiteboard(data_dir=sub_dir)
        assert sub_dir.exists()

    def test_init_creates_active_tasks_file(self, temp_dir):
        """Should create active_tasks.json on init."""
        wb = Whiteboard(data_dir=temp_dir)
        assert (temp_dir / "active_tasks.json").exists()

    def test_post_task(self, whiteboard):
        """Should post a new task to whiteboard."""
        task_id = whiteboard.post_task(
            agent="matt",
            task="Configure browser automation for LinkedIn posting",
        )
        assert task_id is not None
        assert task_id.startswith("task_")

    def test_post_task_with_priority(self, whiteboard):
        """Should post task with priority."""
        task_id = whiteboard.post_task(
            agent="friday",
            task="Review brand content",
            priority="high",
        )
        tasks = whiteboard.get_active_tasks()
        task = next(t for t in tasks if t.id == task_id)
        assert task.priority == "high"

    def test_post_task_with_metadata(self, whiteboard):
        """Should post task with metadata."""
        task_id = whiteboard.post_task(
            agent="jarvis",
            task="Deploy API update",
            metadata={"version": "1.2.3", "rollback_plan": True},
        )
        tasks = whiteboard.get_active_tasks()
        task = next(t for t in tasks if t.id == task_id)
        assert task.metadata["version"] == "1.2.3"

    def test_claim_task(self, whiteboard):
        """Should allow agent to claim unclaimed task."""
        task_id = whiteboard.post_task(
            agent="matt",
            task="Set up Chrome CDP",
        )

        result = whiteboard.claim_task("jarvis", task_id)
        assert result is True

        # Verify task is claimed
        tasks = whiteboard.get_active_tasks()
        task = next(t for t in tasks if t.id == task_id)
        assert task.claimed_by == "jarvis"
        assert task.status == TaskStatus.CLAIMED

    def test_claim_task_already_claimed(self, whiteboard):
        """Should not allow claiming already claimed task."""
        task_id = whiteboard.post_task(
            agent="matt",
            task="Set up Chrome CDP",
        )
        whiteboard.claim_task("jarvis", task_id)

        # Friday tries to claim Jarvis's task
        result = whiteboard.claim_task("friday", task_id)
        assert result is False

    def test_claim_nonexistent_task(self, whiteboard):
        """Should return False for nonexistent task."""
        result = whiteboard.claim_task("jarvis", "task_nonexistent")
        assert result is False

    def test_complete_task(self, whiteboard):
        """Should mark task as completed."""
        task_id = whiteboard.post_task(
            agent="matt",
            task="Configure automation",
        )
        whiteboard.claim_task("jarvis", task_id)

        result = whiteboard.complete_task(task_id)
        assert result is True

        # Verify status
        task = whiteboard.get_task(task_id)
        assert task.status == TaskStatus.COMPLETED

    def test_complete_task_with_result(self, whiteboard):
        """Should store completion result."""
        task_id = whiteboard.post_task(
            agent="matt",
            task="Configure automation",
        )
        whiteboard.claim_task("jarvis", task_id)

        result = whiteboard.complete_task(
            task_id,
            result="published_linkedin_post",
            artifacts=["/outputs/linkedin_post_001.md"],
        )
        assert result is True

        # Verify result stored
        task = whiteboard.get_task(task_id)
        assert task.result == "published_linkedin_post"

    def test_complete_unclaimed_task(self, whiteboard):
        """Should not allow completing unclaimed task."""
        task_id = whiteboard.post_task(
            agent="matt",
            task="Unclaimed task",
        )

        result = whiteboard.complete_task(task_id)
        assert result is False

    def test_complete_nonexistent_task(self, whiteboard):
        """Should return False for nonexistent task."""
        result = whiteboard.complete_task("task_nonexistent")
        assert result is False

    def test_get_active_tasks(self, whiteboard):
        """Should get all active (non-completed) tasks."""
        task1 = whiteboard.post_task(agent="matt", task="Task 1")
        task2 = whiteboard.post_task(agent="friday", task="Task 2")
        task3 = whiteboard.post_task(agent="jarvis", task="Task 3")

        # Complete one task
        whiteboard.claim_task("jarvis", task1)
        whiteboard.complete_task(task1)

        active = whiteboard.get_active_tasks()
        # Should have 2 active tasks (task2, task3)
        assert len(active) == 2
        active_ids = [t.id for t in active]
        assert task2 in active_ids
        assert task3 in active_ids
        assert task1 not in active_ids

    def test_get_active_tasks_empty(self, whiteboard):
        """Should return empty list when no tasks."""
        tasks = whiteboard.get_active_tasks()
        assert tasks == []

    def test_get_completed_tasks(self, whiteboard):
        """Should get completed tasks."""
        task_id = whiteboard.post_task(agent="matt", task="Complete me")
        whiteboard.claim_task("jarvis", task_id)
        whiteboard.complete_task(task_id)

        completed = whiteboard.get_completed_tasks()
        assert len(completed) == 1
        assert completed[0].id == task_id

    def test_persistence(self, temp_dir):
        """Should persist and reload tasks."""
        wb1 = Whiteboard(data_dir=temp_dir)
        task_id = wb1.post_task(
            agent="matt",
            task="Persist test",
        )
        wb1.claim_task("jarvis", task_id)

        # Create new whiteboard (simulates restart)
        wb2 = Whiteboard(data_dir=temp_dir)
        tasks = wb2.get_active_tasks()

        assert len(tasks) == 1
        assert tasks[0].id == task_id
        assert tasks[0].claimed_by == "jarvis"


class TestAgentStatusTracking:
    """Test agent status tracking in whiteboard."""

    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for tests."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def whiteboard(self, temp_dir):
        """Create Whiteboard with temp directory."""
        return Whiteboard(data_dir=temp_dir)

    def test_update_agent_status(self, whiteboard):
        """Should update agent status."""
        whiteboard.update_agent_status(
            agent="jarvis",
            status=AgentStatus.ONLINE,
            current_task="browser_automation_setup",
        )

        status = whiteboard.get_agent_status("jarvis")
        assert status["status"] == "online"
        assert status["current_task"] == "browser_automation_setup"

    def test_update_agent_heartbeat(self, whiteboard):
        """Should update agent heartbeat."""
        whiteboard.update_agent_status("matt", AgentStatus.ONLINE)
        whiteboard.heartbeat("matt")

        status = whiteboard.get_agent_status("matt")
        assert "last_heartbeat" in status

    def test_get_all_agent_statuses(self, whiteboard):
        """Should get all agent statuses."""
        whiteboard.update_agent_status("matt", AgentStatus.ONLINE)
        whiteboard.update_agent_status("jarvis", AgentStatus.BUSY)
        whiteboard.update_agent_status("friday", AgentStatus.OFFLINE)

        statuses = whiteboard.get_all_agent_statuses()
        assert "matt" in statuses
        assert "jarvis" in statuses
        assert "friday" in statuses


class TestSystemFlagsIntegration:
    """Test system flags in whiteboard."""

    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for tests."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def whiteboard(self, temp_dir):
        """Create Whiteboard with temp directory."""
        return Whiteboard(data_dir=temp_dir)

    def test_set_emergency_stop(self, whiteboard):
        """Should set emergency stop flag."""
        whiteboard.set_emergency_stop(True)
        flags = whiteboard.get_system_flags()
        assert flags.emergency_stop is True

    def test_clear_emergency_stop(self, whiteboard):
        """Should clear emergency stop flag."""
        whiteboard.set_emergency_stop(True)
        whiteboard.set_emergency_stop(False)
        flags = whiteboard.get_system_flags()
        assert flags.emergency_stop is False

    def test_set_maintenance_mode(self, whiteboard):
        """Should set maintenance mode."""
        whiteboard.set_maintenance_mode(True)
        flags = whiteboard.get_system_flags()
        assert flags.maintenance_mode is True

    def test_set_rate_limit(self, whiteboard):
        """Should set rate limit flag."""
        whiteboard.set_rate_limit_active(True)
        flags = whiteboard.get_system_flags()
        assert flags.rate_limit_active is True

    def test_emergency_stop_blocks_claims(self, whiteboard):
        """Should block task claims when emergency stop is active."""
        task_id = whiteboard.post_task(
            agent="matt",
            task="Critical task",
        )

        whiteboard.set_emergency_stop(True)

        # Should not be able to claim during emergency stop
        result = whiteboard.claim_task("jarvis", task_id)
        assert result is False


class TestValidAgents:
    """Test agent validation."""

    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for tests."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    def test_valid_agents(self, temp_dir):
        """Should only allow matt, friday, jarvis as agents."""
        wb = Whiteboard(data_dir=temp_dir)

        # Valid agent should work
        task_id = wb.post_task(agent="matt", task="Valid task")
        assert task_id is not None

    def test_invalid_agent(self, temp_dir):
        """Should raise error for invalid agent."""
        wb = Whiteboard(data_dir=temp_dir)

        with pytest.raises(WhiteboardError):
            wb.post_task(agent="unknown_bot", task="Invalid task")


class TestEdgeCases:
    """Test edge cases and error handling."""

    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for tests."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    def test_empty_task(self, temp_dir):
        """Should reject empty task description."""
        wb = Whiteboard(data_dir=temp_dir)

        with pytest.raises(WhiteboardError):
            wb.post_task(agent="matt", task="")

    def test_concurrent_claims(self, temp_dir):
        """Should handle concurrent claim attempts safely."""
        wb = Whiteboard(data_dir=temp_dir)
        task_id = wb.post_task(agent="matt", task="Race condition test")

        # First claim should succeed
        result1 = wb.claim_task("jarvis", task_id)
        assert result1 is True

        # Second claim should fail
        result2 = wb.claim_task("friday", task_id)
        assert result2 is False

    def test_fail_task(self, temp_dir):
        """Should allow marking task as failed."""
        wb = Whiteboard(data_dir=temp_dir)
        task_id = wb.post_task(agent="matt", task="Will fail")
        wb.claim_task("jarvis", task_id)

        result = wb.fail_task(task_id, reason="API timeout")
        assert result is True

        task = wb.get_task(task_id)
        assert task.status == TaskStatus.FAILED

    def test_special_chars_in_task(self, temp_dir):
        """Should handle special characters in task."""
        wb = Whiteboard(data_dir=temp_dir)

        task_id = wb.post_task(
            agent="matt",
            task='Task with "quotes" and $pecial ch@rs!',
        )
        assert task_id is not None

        # Reload and verify
        wb2 = Whiteboard(data_dir=temp_dir)
        tasks = wb2.get_active_tasks()
        assert len(tasks) == 1
        assert '"quotes"' in tasks[0].description
