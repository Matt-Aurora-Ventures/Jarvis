"""
Tests for bots/shared/coordination.py

Inter-bot coordination system for ClawdBots (Jarvis/CTO, Matt/COO, Friday/CMO).

Tests cover:
- BotCoordinator initialization and state management
- Task delegation between bots
- Task claiming and ownership
- Message queuing between bots
- Status reporting and aggregation
- Shared state persistence
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

from bots.shared.coordination import (
    BotCoordinator,
    BotRole,
    TaskPriority,
    TaskStatus,
    CoordinationTask,
    BotMessage,
    BotStatus,
    CoordinationError,
)


class TestBotRole:
    """Test BotRole enum."""

    def test_jarvis_role(self):
        """Jarvis should be CTO role."""
        assert BotRole.JARVIS.value == "jarvis"
        assert BotRole.JARVIS.title == "CTO"

    def test_matt_role(self):
        """Matt should be COO role."""
        assert BotRole.MATT.value == "matt"
        assert BotRole.MATT.title == "COO"

    def test_friday_role(self):
        """Friday should be CMO role."""
        assert BotRole.FRIDAY.value == "friday"
        assert BotRole.FRIDAY.title == "CMO"


class TestTaskPriority:
    """Test TaskPriority enum."""

    def test_critical_value(self):
        """Should have critical priority (highest)."""
        assert TaskPriority.CRITICAL.value == 1

    def test_high_value(self):
        """Should have high priority."""
        assert TaskPriority.HIGH.value == 2

    def test_medium_value(self):
        """Should have medium priority."""
        assert TaskPriority.MEDIUM.value == 3

    def test_low_value(self):
        """Should have low priority (lowest)."""
        assert TaskPriority.LOW.value == 4


class TestTaskStatus:
    """Test TaskStatus enum."""

    def test_pending_status(self):
        """Should have pending status."""
        assert TaskStatus.PENDING.value == "pending"

    def test_claimed_status(self):
        """Should have claimed status."""
        assert TaskStatus.CLAIMED.value == "claimed"

    def test_in_progress_status(self):
        """Should have in_progress status."""
        assert TaskStatus.IN_PROGRESS.value == "in_progress"

    def test_completed_status(self):
        """Should have completed status."""
        assert TaskStatus.COMPLETED.value == "completed"

    def test_failed_status(self):
        """Should have failed status."""
        assert TaskStatus.FAILED.value == "failed"


class TestCoordinationTask:
    """Test CoordinationTask dataclass."""

    def test_create_task(self):
        """Should create task with required fields."""
        task = CoordinationTask(
            id="task_abc123",
            description="Research competitor marketing",
            delegated_by=BotRole.MATT,
            delegated_to=BotRole.FRIDAY,
            priority=TaskPriority.HIGH,
        )
        assert task.id == "task_abc123"
        assert task.description == "Research competitor marketing"
        assert task.delegated_by == BotRole.MATT
        assert task.delegated_to == BotRole.FRIDAY
        assert task.priority == TaskPriority.HIGH
        assert task.status == TaskStatus.PENDING

    def test_default_priority(self):
        """Should default to medium priority."""
        task = CoordinationTask(
            id="task_123",
            description="Test task",
            delegated_by=BotRole.JARVIS,
            delegated_to=BotRole.MATT,
        )
        assert task.priority == TaskPriority.MEDIUM

    def test_to_dict(self):
        """Should serialize to dict correctly."""
        task = CoordinationTask(
            id="task_xyz789",
            description="Coordinate campaign",
            delegated_by=BotRole.MATT,
            delegated_to=BotRole.FRIDAY,
            priority=TaskPriority.CRITICAL,
            context={"campaign_id": "summer_2026"},
        )
        data = task.to_dict()
        assert data["id"] == "task_xyz789"
        assert data["description"] == "Coordinate campaign"
        assert data["delegated_by"] == "matt"
        assert data["delegated_to"] == "friday"
        assert data["priority"] == 1
        assert data["status"] == "pending"
        assert data["context"]["campaign_id"] == "summer_2026"

    def test_from_dict(self):
        """Should deserialize from dict correctly."""
        data = {
            "id": "task_restore",
            "description": "Restore from dict",
            "delegated_by": "jarvis",
            "delegated_to": "matt",
            "priority": 2,
            "status": "in_progress",
            "claimed_at": "2026-02-02T10:00:00Z",
        }
        task = CoordinationTask.from_dict(data)
        assert task.id == "task_restore"
        assert task.delegated_by == BotRole.JARVIS
        assert task.delegated_to == BotRole.MATT
        assert task.priority == TaskPriority.HIGH
        assert task.status == TaskStatus.IN_PROGRESS


class TestBotMessage:
    """Test BotMessage dataclass."""

    def test_create_message(self):
        """Should create message between bots."""
        msg = BotMessage(
            id="msg_001",
            from_bot=BotRole.JARVIS,
            to_bot=BotRole.FRIDAY,
            content="Please research token sentiment for $SOL",
        )
        assert msg.id == "msg_001"
        assert msg.from_bot == BotRole.JARVIS
        assert msg.to_bot == BotRole.FRIDAY
        assert msg.content == "Please research token sentiment for $SOL"
        assert msg.read is False

    def test_to_dict(self):
        """Should serialize message to dict."""
        msg = BotMessage(
            id="msg_002",
            from_bot=BotRole.MATT,
            to_bot=BotRole.JARVIS,
            content="Campaign metrics ready",
            related_task_id="task_123",
        )
        data = msg.to_dict()
        assert data["id"] == "msg_002"
        assert data["from_bot"] == "matt"
        assert data["to_bot"] == "jarvis"
        assert data["related_task_id"] == "task_123"

    def test_from_dict(self):
        """Should deserialize message from dict."""
        data = {
            "id": "msg_restore",
            "from_bot": "friday",
            "to_bot": "matt",
            "content": "Marketing report complete",
            "read": True,
            "created_at": "2026-02-02T11:00:00Z",
        }
        msg = BotMessage.from_dict(data)
        assert msg.from_bot == BotRole.FRIDAY
        assert msg.to_bot == BotRole.MATT
        assert msg.read is True


class TestBotStatus:
    """Test BotStatus dataclass."""

    def test_create_status(self):
        """Should create bot status."""
        status = BotStatus(
            bot=BotRole.JARVIS,
            online=True,
            current_task="Monitoring trading signals",
        )
        assert status.bot == BotRole.JARVIS
        assert status.online is True
        assert status.current_task == "Monitoring trading signals"

    def test_to_dict(self):
        """Should serialize status to dict."""
        status = BotStatus(
            bot=BotRole.MATT,
            online=True,
            current_task="Reviewing PR content",
            tasks_completed=5,
            tasks_pending=2,
        )
        data = status.to_dict()
        assert data["bot"] == "matt"
        assert data["online"] is True
        assert data["tasks_completed"] == 5
        assert data["tasks_pending"] == 2


class TestBotCoordinator:
    """Test BotCoordinator class."""

    @pytest.fixture
    def temp_state_file(self):
        """Create temporary state file for tests."""
        with tempfile.NamedTemporaryFile(
            mode='w', suffix='.json', delete=False
        ) as f:
            f.write('{}')
            temp_path = f.name
        yield temp_path
        # Cleanup
        if os.path.exists(temp_path):
            os.unlink(temp_path)
        lock_path = temp_path + ".lock"
        if os.path.exists(lock_path):
            os.unlink(lock_path)

    @pytest.fixture
    def coordinator(self, temp_state_file):
        """Create BotCoordinator with temp state file."""
        return BotCoordinator(
            bot_role=BotRole.JARVIS,
            state_file=temp_state_file,
        )

    # Initialization tests

    def test_init_creates_state_file(self, temp_state_file):
        """Should initialize state file on creation."""
        os.unlink(temp_state_file)  # Remove the file
        coord = BotCoordinator(
            bot_role=BotRole.JARVIS,
            state_file=temp_state_file,
        )
        assert os.path.exists(temp_state_file)

    def test_init_loads_existing_state(self, temp_state_file):
        """Should load existing state on init."""
        # Pre-populate state
        state = {
            "tasks": [
                {
                    "id": "task_existing",
                    "description": "Pre-existing task",
                    "delegated_by": "matt",
                    "delegated_to": "jarvis",
                    "priority": 3,
                    "status": "pending",
                    "created_at": "2026-02-02T09:00:00Z",
                }
            ],
            "messages": [],
            "bot_statuses": {},
        }
        with open(temp_state_file, 'w') as f:
            json.dump(state, f)

        coord = BotCoordinator(
            bot_role=BotRole.JARVIS,
            state_file=temp_state_file,
        )
        pending = coord.get_pending_tasks()
        assert len(pending) == 1
        assert pending[0].id == "task_existing"

    # Task delegation tests

    def test_delegate_task(self, coordinator):
        """Should delegate task to another bot."""
        task_id = coordinator.delegate_task(
            to_bot=BotRole.FRIDAY,
            description="Research competitor social media strategy",
            priority=TaskPriority.HIGH,
        )
        assert task_id is not None
        assert task_id.startswith("task_")

    def test_delegate_task_with_context(self, coordinator):
        """Should delegate task with context metadata."""
        task_id = coordinator.delegate_task(
            to_bot=BotRole.MATT,
            description="Review and approve campaign budget",
            context={
                "budget_amount": 5000,
                "campaign_name": "Q1 Launch",
            },
        )
        task = coordinator.get_task(task_id)
        assert task.context["budget_amount"] == 5000
        assert task.context["campaign_name"] == "Q1 Launch"

    def test_cannot_delegate_to_self(self, coordinator):
        """Should raise error when delegating to self."""
        with pytest.raises(CoordinationError):
            coordinator.delegate_task(
                to_bot=BotRole.JARVIS,  # Same as coordinator's role
                description="Self-delegation test",
            )

    def test_delegate_task_creates_pending_status(self, coordinator):
        """Delegated task should start with pending status."""
        task_id = coordinator.delegate_task(
            to_bot=BotRole.FRIDAY,
            description="Write blog post",
        )
        task = coordinator.get_task(task_id)
        assert task.status == TaskStatus.PENDING

    # Task claiming tests

    def test_claim_task(self, temp_state_file):
        """Should claim a task delegated to this bot."""
        # Jarvis delegates to Matt
        jarvis = BotCoordinator(BotRole.JARVIS, temp_state_file)
        task_id = jarvis.delegate_task(
            to_bot=BotRole.MATT,
            description="Coordinate team meeting",
        )

        # Matt claims the task
        matt = BotCoordinator(BotRole.MATT, temp_state_file)
        result = matt.claim_task(task_id)
        assert result is True

        task = matt.get_task(task_id)
        assert task.status == TaskStatus.CLAIMED
        assert task.claimed_at is not None

    def test_cannot_claim_others_task(self, temp_state_file):
        """Should not allow claiming tasks delegated to other bots."""
        # Jarvis delegates to Matt
        jarvis = BotCoordinator(BotRole.JARVIS, temp_state_file)
        task_id = jarvis.delegate_task(
            to_bot=BotRole.MATT,
            description="Coordinate team meeting",
        )

        # Friday tries to claim Matt's task
        friday = BotCoordinator(BotRole.FRIDAY, temp_state_file)
        result = friday.claim_task(task_id)
        assert result is False

    def test_cannot_claim_already_claimed_task(self, temp_state_file):
        """Should not allow re-claiming an already claimed task."""
        # Setup
        jarvis = BotCoordinator(BotRole.JARVIS, temp_state_file)
        task_id = jarvis.delegate_task(
            to_bot=BotRole.MATT,
            description="Review document",
        )

        # Matt claims
        matt = BotCoordinator(BotRole.MATT, temp_state_file)
        matt.claim_task(task_id)

        # Matt tries to claim again
        result = matt.claim_task(task_id)
        assert result is False

    # Task completion tests

    def test_complete_task(self, temp_state_file):
        """Should mark task as completed with result."""
        # Setup and claim
        jarvis = BotCoordinator(BotRole.JARVIS, temp_state_file)
        task_id = jarvis.delegate_task(
            to_bot=BotRole.FRIDAY,
            description="Write marketing copy",
        )

        friday = BotCoordinator(BotRole.FRIDAY, temp_state_file)
        friday.claim_task(task_id)

        # Complete
        result = friday.complete_task(
            task_id,
            result="Marketing copy completed - 500 words",
            artifacts=["/outputs/marketing_copy.md"],
        )
        assert result is True

        task = friday.get_task(task_id)
        assert task.status == TaskStatus.COMPLETED
        assert task.result == "Marketing copy completed - 500 words"

    def test_fail_task(self, temp_state_file):
        """Should mark task as failed with reason."""
        # Setup and claim
        jarvis = BotCoordinator(BotRole.JARVIS, temp_state_file)
        task_id = jarvis.delegate_task(
            to_bot=BotRole.MATT,
            description="Connect to external API",
        )

        matt = BotCoordinator(BotRole.MATT, temp_state_file)
        matt.claim_task(task_id)

        # Fail
        result = matt.fail_task(
            task_id,
            reason="API endpoint unreachable",
        )
        assert result is True

        task = matt.get_task(task_id)
        assert task.status == TaskStatus.FAILED

    # Message queue tests

    def test_send_message(self, coordinator):
        """Should send message to another bot."""
        msg_id = coordinator.send_message(
            to_bot=BotRole.FRIDAY,
            content="Please prioritize the social media audit",
        )
        assert msg_id is not None
        assert msg_id.startswith("msg_")

    def test_send_message_with_task_reference(self, coordinator):
        """Should send message referencing a task."""
        task_id = coordinator.delegate_task(
            to_bot=BotRole.MATT,
            description="Review budget",
        )
        msg_id = coordinator.send_message(
            to_bot=BotRole.MATT,
            content="Task is urgent, please prioritize",
            related_task_id=task_id,
        )
        # Verify in Matt's inbox
        matt = BotCoordinator(
            BotRole.MATT,
            state_file=coordinator._state_file,
        )
        messages = matt.get_unread_messages()
        assert len(messages) == 1
        assert messages[0].related_task_id == task_id

    def test_get_unread_messages(self, temp_state_file):
        """Should get unread messages for this bot."""
        # Jarvis sends messages
        jarvis = BotCoordinator(BotRole.JARVIS, temp_state_file)
        jarvis.send_message(BotRole.FRIDAY, "Message 1")
        jarvis.send_message(BotRole.FRIDAY, "Message 2")
        jarvis.send_message(BotRole.MATT, "Message to Matt")

        # Friday checks inbox
        friday = BotCoordinator(BotRole.FRIDAY, temp_state_file)
        messages = friday.get_unread_messages()
        assert len(messages) == 2

    def test_mark_message_read(self, temp_state_file):
        """Should mark message as read."""
        jarvis = BotCoordinator(BotRole.JARVIS, temp_state_file)
        msg_id = jarvis.send_message(BotRole.FRIDAY, "Read this")

        friday = BotCoordinator(BotRole.FRIDAY, temp_state_file)
        friday.mark_message_read(msg_id)

        # Should not appear in unread anymore
        unread = friday.get_unread_messages()
        assert len(unread) == 0

    # Status reporting tests

    def test_update_status(self, coordinator):
        """Should update bot's own status."""
        coordinator.update_status(
            current_task="Processing trading signals",
            tasks_completed=10,
            tasks_pending=3,
        )
        status = coordinator.get_my_status()
        assert status.current_task == "Processing trading signals"
        assert status.tasks_completed == 10

    def test_get_all_statuses(self, temp_state_file):
        """Should get status of all bots."""
        # Each bot updates status
        jarvis = BotCoordinator(BotRole.JARVIS, temp_state_file)
        jarvis.update_status(current_task="Trading", tasks_completed=5)

        matt = BotCoordinator(BotRole.MATT, temp_state_file)
        matt.update_status(current_task="PR Review", tasks_completed=3)

        friday = BotCoordinator(BotRole.FRIDAY, temp_state_file)
        friday.update_status(current_task="Marketing", tasks_completed=7)

        # Get all statuses
        statuses = jarvis.get_all_bot_statuses()
        assert len(statuses) == 3
        assert statuses[BotRole.JARVIS].tasks_completed == 5
        assert statuses[BotRole.MATT].tasks_completed == 3
        assert statuses[BotRole.FRIDAY].tasks_completed == 7

    def test_heartbeat(self, coordinator):
        """Should update heartbeat timestamp."""
        coordinator.heartbeat()
        status = coordinator.get_my_status()
        assert status.last_heartbeat is not None

    # Aggregated status report tests

    def test_generate_status_report(self, temp_state_file):
        """Should generate aggregated status report."""
        jarvis = BotCoordinator(BotRole.JARVIS, temp_state_file)

        # Create some tasks
        jarvis.delegate_task(BotRole.MATT, "Task 1")
        jarvis.delegate_task(BotRole.FRIDAY, "Task 2")

        # Update statuses
        jarvis.update_status(current_task="Coordinating")

        matt = BotCoordinator(BotRole.MATT, temp_state_file)
        matt.update_status(current_task="Working")

        friday = BotCoordinator(BotRole.FRIDAY, temp_state_file)
        friday.update_status(current_task="Marketing")

        # Generate report
        report = jarvis.generate_status_report()
        assert "jarvis" in report.lower()
        assert "matt" in report.lower()
        assert "friday" in report.lower()

    # Persistence tests

    def test_state_persistence(self, temp_state_file):
        """Should persist state across coordinator instances."""
        # Create coordinator and delegate task
        coord1 = BotCoordinator(BotRole.JARVIS, temp_state_file)
        task_id = coord1.delegate_task(
            to_bot=BotRole.MATT,
            description="Persistent task",
        )

        # Create new coordinator instance (simulates restart)
        coord2 = BotCoordinator(BotRole.JARVIS, temp_state_file)
        task = coord2.get_task(task_id)
        assert task is not None
        assert task.description == "Persistent task"

    def test_concurrent_access(self, temp_state_file):
        """Should handle concurrent access safely."""
        # Create multiple coordinators
        jarvis = BotCoordinator(BotRole.JARVIS, temp_state_file)
        matt = BotCoordinator(BotRole.MATT, temp_state_file)
        friday = BotCoordinator(BotRole.FRIDAY, temp_state_file)

        # All delegate tasks simultaneously
        task1 = jarvis.delegate_task(BotRole.MATT, "Task from Jarvis")
        task2 = matt.delegate_task(BotRole.FRIDAY, "Task from Matt")
        task3 = friday.delegate_task(BotRole.JARVIS, "Task from Friday")

        # All tasks should exist
        assert jarvis.get_task(task1) is not None
        assert jarvis.get_task(task2) is not None
        assert jarvis.get_task(task3) is not None

    # Edge cases

    def test_get_nonexistent_task(self, coordinator):
        """Should return None for nonexistent task."""
        task = coordinator.get_task("task_nonexistent")
        assert task is None

    def test_get_pending_tasks_for_bot(self, temp_state_file):
        """Should get only pending tasks delegated to this bot."""
        jarvis = BotCoordinator(BotRole.JARVIS, temp_state_file)
        jarvis.delegate_task(BotRole.MATT, "Task 1 for Matt")
        jarvis.delegate_task(BotRole.MATT, "Task 2 for Matt")
        jarvis.delegate_task(BotRole.FRIDAY, "Task for Friday")

        matt = BotCoordinator(BotRole.MATT, temp_state_file)
        pending = matt.get_pending_tasks()
        assert len(pending) == 2

    def test_get_tasks_by_status(self, temp_state_file):
        """Should filter tasks by status."""
        jarvis = BotCoordinator(BotRole.JARVIS, temp_state_file)
        task_id = jarvis.delegate_task(BotRole.MATT, "Test task")

        matt = BotCoordinator(BotRole.MATT, temp_state_file)
        matt.claim_task(task_id)

        # Get claimed tasks
        claimed = matt.get_tasks_by_status(TaskStatus.CLAIMED)
        assert len(claimed) == 1

        # Get pending should be empty
        pending = matt.get_pending_tasks()
        assert len(pending) == 0
