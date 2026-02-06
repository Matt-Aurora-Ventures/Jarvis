"""
Unit tests for bots/shared/scheduler.py - ClawdBot Task Scheduler.

Tests cover:
- Task scheduling (one-time and recurring)
- Cron expression parsing
- Task cancellation
- Task persistence (scheduled_tasks.json, task_history.json)
- Missed task handling (runs immediately)
- Task status and history tracking
- run_due_tasks execution
"""

import pytest
import json
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))


# =============================================================================
# Task Structure Tests
# =============================================================================

class TestTaskStructure:
    """Tests for ScheduledTask dataclass structure."""

    def test_task_has_required_fields(self):
        """Test that ScheduledTask has all required fields."""
        from bots.shared.scheduler import ScheduledTask

        task = ScheduledTask(
            id="test-001",
            name="Test Task",
            function_name="my_module.my_function",
            args={"key": "value"},
            scheduled_time=datetime.utcnow(),
            recurring=False,
            cron=None,
            status="pending",
        )

        assert task.id == "test-001"
        assert task.name == "Test Task"
        assert task.function_name == "my_module.my_function"
        assert task.args == {"key": "value"}
        assert task.status == "pending"
        assert task.recurring is False
        assert task.cron is None

    def test_task_default_values(self):
        """Test that ScheduledTask has sensible defaults."""
        from bots.shared.scheduler import ScheduledTask

        task = ScheduledTask(
            id="test-002",
            name="Simple Task",
            function_name="my_function",
            scheduled_time=datetime.utcnow(),
        )

        assert task.args == {}
        assert task.recurring is False
        assert task.cron is None
        assert task.status == "pending"

    def test_task_to_dict(self):
        """Test task serialization to dict for JSON storage."""
        from bots.shared.scheduler import ScheduledTask

        now = datetime.utcnow()
        task = ScheduledTask(
            id="test-003",
            name="Dict Task",
            function_name="module.func",
            args={"a": 1},
            scheduled_time=now,
            recurring=True,
            cron="0 * * * *",
            status="pending",
        )

        d = task.to_dict()

        assert d["id"] == "test-003"
        assert d["name"] == "Dict Task"
        assert d["function_name"] == "module.func"
        assert d["args"] == {"a": 1}
        assert d["scheduled_time"] == now.isoformat()
        assert d["recurring"] is True
        assert d["cron"] == "0 * * * *"
        assert d["status"] == "pending"

    def test_task_from_dict(self):
        """Test task deserialization from dict."""
        from bots.shared.scheduler import ScheduledTask

        now = datetime.utcnow()
        d = {
            "id": "test-004",
            "name": "From Dict Task",
            "function_name": "mod.fn",
            "args": {"x": 2},
            "scheduled_time": now.isoformat(),
            "recurring": False,
            "cron": None,
            "status": "completed",
        }

        task = ScheduledTask.from_dict(d)

        assert task.id == "test-004"
        assert task.name == "From Dict Task"
        assert task.function_name == "mod.fn"
        assert task.args == {"x": 2}
        assert task.recurring is False
        assert task.status == "completed"


# =============================================================================
# Task History Structure Tests
# =============================================================================

class TestTaskHistory:
    """Tests for TaskHistory dataclass."""

    def test_history_has_required_fields(self):
        """Test that TaskHistory has all required fields."""
        from bots.shared.scheduler import TaskHistory

        history = TaskHistory(
            task_id="test-001",
            task_name="Test Task",
            executed_at=datetime.utcnow(),
            success=True,
            result="completed",
            error=None,
            duration_ms=150.5,
        )

        assert history.task_id == "test-001"
        assert history.task_name == "Test Task"
        assert history.success is True
        assert history.result == "completed"
        assert history.error is None
        assert history.duration_ms == 150.5

    def test_history_to_dict(self):
        """Test history serialization to dict."""
        from bots.shared.scheduler import TaskHistory

        now = datetime.utcnow()
        history = TaskHistory(
            task_id="test-002",
            task_name="History Task",
            executed_at=now,
            success=False,
            result=None,
            error="Connection failed",
            duration_ms=50.0,
        )

        d = history.to_dict()

        assert d["task_id"] == "test-002"
        assert d["task_name"] == "History Task"
        assert d["executed_at"] == now.isoformat()
        assert d["success"] is False
        assert d["error"] == "Connection failed"

    def test_history_from_dict(self):
        """Test history deserialization from dict."""
        from bots.shared.scheduler import TaskHistory

        now = datetime.utcnow()
        d = {
            "task_id": "test-003",
            "task_name": "From Dict History",
            "executed_at": now.isoformat(),
            "success": True,
            "result": "ok",
            "error": None,
            "duration_ms": 100.0,
        }

        history = TaskHistory.from_dict(d)

        assert history.task_id == "test-003"
        assert history.success is True
        assert history.result == "ok"


# =============================================================================
# Cron Parser Tests
# =============================================================================

class TestCronParser:
    """Tests for cron expression parsing."""

    def test_parse_all_wildcards(self):
        """Test parsing cron with all wildcards."""
        from bots.shared.scheduler import CronParser

        result = CronParser.parse("* * * * *")

        assert result["minute"] == list(range(0, 60))
        assert result["hour"] == list(range(0, 24))
        assert result["day"] == list(range(1, 32))
        assert result["month"] == list(range(1, 13))
        assert result["weekday"] == list(range(0, 7))

    def test_parse_specific_values(self):
        """Test parsing cron with specific values."""
        from bots.shared.scheduler import CronParser

        result = CronParser.parse("30 14 15 6 3")

        assert result["minute"] == [30]
        assert result["hour"] == [14]
        assert result["day"] == [15]
        assert result["month"] == [6]
        assert result["weekday"] == [3]

    def test_parse_step_values(self):
        """Test parsing cron with step values."""
        from bots.shared.scheduler import CronParser

        result = CronParser.parse("*/15 */6 * * *")

        assert result["minute"] == [0, 15, 30, 45]
        assert result["hour"] == [0, 6, 12, 18]

    def test_parse_range_values(self):
        """Test parsing cron with range values."""
        from bots.shared.scheduler import CronParser

        result = CronParser.parse("0-5 9-17 * * *")

        assert result["minute"] == [0, 1, 2, 3, 4, 5]
        assert result["hour"] == [9, 10, 11, 12, 13, 14, 15, 16, 17]

    def test_parse_list_values(self):
        """Test parsing cron with list values."""
        from bots.shared.scheduler import CronParser

        result = CronParser.parse("0,30 8,12,18 * * *")

        assert result["minute"] == [0, 30]
        assert result["hour"] == [8, 12, 18]

    def test_parse_invalid_expression_wrong_parts(self):
        """Test parsing invalid cron expression."""
        from bots.shared.scheduler import CronParser

        with pytest.raises(ValueError, match="Invalid cron expression"):
            CronParser.parse("* * *")

    def test_next_run_calculates_future_time(self):
        """Test next_run returns a future time."""
        from bots.shared.scheduler import CronParser

        now = datetime.utcnow()
        next_run = CronParser.next_run("* * * * *")

        assert next_run > now

    def test_next_run_specific_time(self):
        """Test next_run with specific hour/minute."""
        from bots.shared.scheduler import CronParser

        from_time = datetime(2025, 6, 15, 10, 0, 0)
        # Every hour at minute 30
        next_run = CronParser.next_run("30 * * * *", from_time)

        assert next_run.minute == 30


# =============================================================================
# Scheduler Initialization Tests
# =============================================================================

class TestSchedulerInit:
    """Tests for ClawdBotScheduler initialization."""

    def test_scheduler_creates_with_default_paths(self):
        """Test scheduler uses default VPS paths."""
        from bots.shared.scheduler import ClawdBotScheduler

        with tempfile.TemporaryDirectory() as tmpdir:
            tasks_path = Path(tmpdir) / "scheduled_tasks.json"
            history_path = Path(tmpdir) / "task_history.json"

            scheduler = ClawdBotScheduler(
                tasks_path=tasks_path,
                history_path=history_path,
            )

            assert scheduler.tasks_path == tasks_path
            assert scheduler.history_path == history_path

    def test_scheduler_loads_existing_tasks(self):
        """Test scheduler loads tasks from existing file."""
        from bots.shared.scheduler import ClawdBotScheduler

        with tempfile.TemporaryDirectory() as tmpdir:
            tasks_path = Path(tmpdir) / "scheduled_tasks.json"
            history_path = Path(tmpdir) / "task_history.json"

            # Pre-create tasks file
            now = datetime.utcnow()
            tasks_data = [
                {
                    "id": "existing-001",
                    "name": "Existing Task",
                    "function_name": "mod.func",
                    "args": {},
                    "scheduled_time": now.isoformat(),
                    "recurring": False,
                    "cron": None,
                    "status": "pending",
                }
            ]
            tasks_path.write_text(json.dumps(tasks_data))

            scheduler = ClawdBotScheduler(
                tasks_path=tasks_path,
                history_path=history_path,
            )

            tasks = scheduler.get_scheduled_tasks()
            assert len(tasks) == 1
            assert tasks[0].id == "existing-001"

    def test_scheduler_handles_missing_files(self):
        """Test scheduler handles missing persistence files."""
        from bots.shared.scheduler import ClawdBotScheduler

        with tempfile.TemporaryDirectory() as tmpdir:
            tasks_path = Path(tmpdir) / "nonexistent" / "tasks.json"
            history_path = Path(tmpdir) / "nonexistent" / "history.json"

            scheduler = ClawdBotScheduler(
                tasks_path=tasks_path,
                history_path=history_path,
            )

            assert len(scheduler.get_scheduled_tasks()) == 0


# =============================================================================
# schedule_task Tests
# =============================================================================

class TestScheduleTask:
    """Tests for schedule_task function."""

    def test_schedule_one_time_task(self):
        """Test scheduling a one-time task."""
        from bots.shared.scheduler import ClawdBotScheduler

        with tempfile.TemporaryDirectory() as tmpdir:
            scheduler = ClawdBotScheduler(
                tasks_path=Path(tmpdir) / "tasks.json",
                history_path=Path(tmpdir) / "history.json",
            )

            future_time = datetime.utcnow() + timedelta(hours=1)
            task_id = scheduler.schedule_task(
                task_id="one-time-001",
                func="my_module.my_function",
                when=future_time,
                recurring=False,
            )

            assert task_id == "one-time-001"
            tasks = scheduler.get_scheduled_tasks()
            assert len(tasks) == 1
            assert tasks[0].recurring is False

    def test_schedule_recurring_task_with_cron(self):
        """Test scheduling a recurring task with cron expression."""
        from bots.shared.scheduler import ClawdBotScheduler

        with tempfile.TemporaryDirectory() as tmpdir:
            scheduler = ClawdBotScheduler(
                tasks_path=Path(tmpdir) / "tasks.json",
                history_path=Path(tmpdir) / "history.json",
            )

            task_id = scheduler.schedule_task(
                task_id="cron-001",
                func="my_module.hourly_task",
                when=None,  # Cron handles timing
                recurring=True,
                cron="0 * * * *",
            )

            tasks = scheduler.get_scheduled_tasks()
            assert len(tasks) == 1
            assert tasks[0].recurring is True
            assert tasks[0].cron == "0 * * * *"

    def test_schedule_task_with_args(self):
        """Test scheduling a task with arguments."""
        from bots.shared.scheduler import ClawdBotScheduler

        with tempfile.TemporaryDirectory() as tmpdir:
            scheduler = ClawdBotScheduler(
                tasks_path=Path(tmpdir) / "tasks.json",
                history_path=Path(tmpdir) / "history.json",
            )

            future_time = datetime.utcnow() + timedelta(hours=1)
            task_id = scheduler.schedule_task(
                task_id="args-001",
                func="my_module.task_with_args",
                when=future_time,
                args={"message": "hello", "count": 5},
            )

            tasks = scheduler.get_scheduled_tasks()
            assert tasks[0].args == {"message": "hello", "count": 5}

    def test_schedule_task_persists_to_file(self):
        """Test that scheduled tasks are persisted to file."""
        from bots.shared.scheduler import ClawdBotScheduler

        with tempfile.TemporaryDirectory() as tmpdir:
            tasks_path = Path(tmpdir) / "tasks.json"
            scheduler = ClawdBotScheduler(
                tasks_path=tasks_path,
                history_path=Path(tmpdir) / "history.json",
            )

            future_time = datetime.utcnow() + timedelta(hours=1)
            scheduler.schedule_task(
                task_id="persist-001",
                func="my_module.func",
                when=future_time,
            )

            # Verify file exists and contains task
            assert tasks_path.exists()
            data = json.loads(tasks_path.read_text())
            assert len(data) == 1
            assert data[0]["id"] == "persist-001"

    def test_schedule_task_with_name(self):
        """Test scheduling a task with custom name."""
        from bots.shared.scheduler import ClawdBotScheduler

        with tempfile.TemporaryDirectory() as tmpdir:
            scheduler = ClawdBotScheduler(
                tasks_path=Path(tmpdir) / "tasks.json",
                history_path=Path(tmpdir) / "history.json",
            )

            future_time = datetime.utcnow() + timedelta(hours=1)
            scheduler.schedule_task(
                task_id="named-001",
                func="my_module.func",
                when=future_time,
                name="My Custom Task Name",
            )

            tasks = scheduler.get_scheduled_tasks()
            assert tasks[0].name == "My Custom Task Name"

    def test_schedule_task_generates_id_if_none(self):
        """Test that task ID is auto-generated if not provided."""
        from bots.shared.scheduler import ClawdBotScheduler

        with tempfile.TemporaryDirectory() as tmpdir:
            scheduler = ClawdBotScheduler(
                tasks_path=Path(tmpdir) / "tasks.json",
                history_path=Path(tmpdir) / "history.json",
            )

            future_time = datetime.utcnow() + timedelta(hours=1)
            task_id = scheduler.schedule_task(
                task_id=None,
                func="my_module.func",
                when=future_time,
            )

            assert task_id is not None
            assert len(task_id) > 0


# =============================================================================
# cancel_task Tests
# =============================================================================

class TestCancelTask:
    """Tests for cancel_task function."""

    def test_cancel_existing_task(self):
        """Test cancelling an existing task."""
        from bots.shared.scheduler import ClawdBotScheduler

        with tempfile.TemporaryDirectory() as tmpdir:
            scheduler = ClawdBotScheduler(
                tasks_path=Path(tmpdir) / "tasks.json",
                history_path=Path(tmpdir) / "history.json",
            )

            future_time = datetime.utcnow() + timedelta(hours=1)
            scheduler.schedule_task(
                task_id="cancel-001",
                func="my_module.func",
                when=future_time,
            )

            result = scheduler.cancel_task("cancel-001")

            assert result is True
            assert len(scheduler.get_scheduled_tasks()) == 0

    def test_cancel_nonexistent_task(self):
        """Test cancelling a task that doesn't exist."""
        from bots.shared.scheduler import ClawdBotScheduler

        with tempfile.TemporaryDirectory() as tmpdir:
            scheduler = ClawdBotScheduler(
                tasks_path=Path(tmpdir) / "tasks.json",
                history_path=Path(tmpdir) / "history.json",
            )

            result = scheduler.cancel_task("nonexistent-001")

            assert result is False

    def test_cancel_task_persists_changes(self):
        """Test that cancellation persists to file."""
        from bots.shared.scheduler import ClawdBotScheduler

        with tempfile.TemporaryDirectory() as tmpdir:
            tasks_path = Path(tmpdir) / "tasks.json"
            scheduler = ClawdBotScheduler(
                tasks_path=tasks_path,
                history_path=Path(tmpdir) / "history.json",
            )

            future_time = datetime.utcnow() + timedelta(hours=1)
            scheduler.schedule_task(
                task_id="cancel-persist-001",
                func="my_module.func",
                when=future_time,
            )
            scheduler.cancel_task("cancel-persist-001")

            # Verify file is empty
            data = json.loads(tasks_path.read_text())
            assert len(data) == 0


# =============================================================================
# get_scheduled_tasks Tests
# =============================================================================

class TestGetScheduledTasks:
    """Tests for get_scheduled_tasks function."""

    def test_get_empty_tasks(self):
        """Test getting tasks when none scheduled."""
        from bots.shared.scheduler import ClawdBotScheduler

        with tempfile.TemporaryDirectory() as tmpdir:
            scheduler = ClawdBotScheduler(
                tasks_path=Path(tmpdir) / "tasks.json",
                history_path=Path(tmpdir) / "history.json",
            )

            tasks = scheduler.get_scheduled_tasks()
            assert tasks == []

    def test_get_multiple_tasks(self):
        """Test getting multiple scheduled tasks."""
        from bots.shared.scheduler import ClawdBotScheduler

        with tempfile.TemporaryDirectory() as tmpdir:
            scheduler = ClawdBotScheduler(
                tasks_path=Path(tmpdir) / "tasks.json",
                history_path=Path(tmpdir) / "history.json",
            )

            future_time = datetime.utcnow() + timedelta(hours=1)
            scheduler.schedule_task(task_id="multi-001", func="f1", when=future_time)
            scheduler.schedule_task(task_id="multi-002", func="f2", when=future_time)
            scheduler.schedule_task(task_id="multi-003", func="f3", when=future_time)

            tasks = scheduler.get_scheduled_tasks()
            assert len(tasks) == 3

    def test_get_tasks_returns_pending_only(self):
        """Test that get_scheduled_tasks returns only pending tasks."""
        from bots.shared.scheduler import ClawdBotScheduler

        with tempfile.TemporaryDirectory() as tmpdir:
            scheduler = ClawdBotScheduler(
                tasks_path=Path(tmpdir) / "tasks.json",
                history_path=Path(tmpdir) / "history.json",
            )

            future_time = datetime.utcnow() + timedelta(hours=1)
            scheduler.schedule_task(task_id="pending-001", func="f1", when=future_time)

            # The tasks returned should be pending by default
            tasks = scheduler.get_scheduled_tasks()
            assert all(t.status == "pending" for t in tasks)


# =============================================================================
# get_task_history Tests
# =============================================================================

class TestGetTaskHistory:
    """Tests for get_task_history function."""

    def test_get_empty_history(self):
        """Test getting history when none exists."""
        from bots.shared.scheduler import ClawdBotScheduler

        with tempfile.TemporaryDirectory() as tmpdir:
            scheduler = ClawdBotScheduler(
                tasks_path=Path(tmpdir) / "tasks.json",
                history_path=Path(tmpdir) / "history.json",
            )

            history = scheduler.get_task_history()
            assert history == []

    def test_get_history_with_limit(self):
        """Test getting history with limit."""
        from bots.shared.scheduler import ClawdBotScheduler, TaskHistory

        with tempfile.TemporaryDirectory() as tmpdir:
            history_path = Path(tmpdir) / "history.json"

            # Pre-create history entries
            history_data = [
                {
                    "task_id": f"hist-{i}",
                    "task_name": f"Task {i}",
                    "executed_at": datetime.utcnow().isoformat(),
                    "success": True,
                    "result": None,
                    "error": None,
                    "duration_ms": 100.0,
                }
                for i in range(100)
            ]
            history_path.write_text(json.dumps(history_data))

            scheduler = ClawdBotScheduler(
                tasks_path=Path(tmpdir) / "tasks.json",
                history_path=history_path,
            )

            history = scheduler.get_task_history(limit=50)
            assert len(history) == 50

    def test_get_history_default_limit(self):
        """Test that default limit is 50."""
        from bots.shared.scheduler import ClawdBotScheduler

        with tempfile.TemporaryDirectory() as tmpdir:
            history_path = Path(tmpdir) / "history.json"

            # Pre-create 100 history entries
            history_data = [
                {
                    "task_id": f"hist-{i}",
                    "task_name": f"Task {i}",
                    "executed_at": datetime.utcnow().isoformat(),
                    "success": True,
                    "result": None,
                    "error": None,
                    "duration_ms": 100.0,
                }
                for i in range(100)
            ]
            history_path.write_text(json.dumps(history_data))

            scheduler = ClawdBotScheduler(
                tasks_path=Path(tmpdir) / "tasks.json",
                history_path=history_path,
            )

            history = scheduler.get_task_history()  # Default limit
            assert len(history) == 50


# =============================================================================
# run_due_tasks Tests
# =============================================================================

class TestRunDueTasks:
    """Tests for run_due_tasks function."""

    def test_run_due_tasks_executes_past_tasks(self):
        """Test that past-due tasks are executed."""
        from bots.shared.scheduler import ClawdBotScheduler

        with tempfile.TemporaryDirectory() as tmpdir:
            scheduler = ClawdBotScheduler(
                tasks_path=Path(tmpdir) / "tasks.json",
                history_path=Path(tmpdir) / "history.json",
            )

            # Schedule task in the past (missed)
            past_time = datetime.utcnow() - timedelta(minutes=5)

            # Use a mock function
            mock_func = MagicMock(return_value="executed")
            scheduler.register_function("test_func", mock_func)

            scheduler.schedule_task(
                task_id="due-001",
                func="test_func",
                when=past_time,
            )

            results = scheduler.run_due_tasks()

            assert len(results) == 1
            mock_func.assert_called_once()

    def test_run_due_tasks_skips_future_tasks(self):
        """Test that future tasks are not executed."""
        from bots.shared.scheduler import ClawdBotScheduler

        with tempfile.TemporaryDirectory() as tmpdir:
            scheduler = ClawdBotScheduler(
                tasks_path=Path(tmpdir) / "tasks.json",
                history_path=Path(tmpdir) / "history.json",
            )

            # Schedule task in the future
            future_time = datetime.utcnow() + timedelta(hours=1)

            mock_func = MagicMock()
            scheduler.register_function("future_func", mock_func)

            scheduler.schedule_task(
                task_id="future-001",
                func="future_func",
                when=future_time,
            )

            results = scheduler.run_due_tasks()

            assert len(results) == 0
            mock_func.assert_not_called()

    def test_run_due_tasks_records_history(self):
        """Test that executed tasks are recorded in history."""
        from bots.shared.scheduler import ClawdBotScheduler

        with tempfile.TemporaryDirectory() as tmpdir:
            scheduler = ClawdBotScheduler(
                tasks_path=Path(tmpdir) / "tasks.json",
                history_path=Path(tmpdir) / "history.json",
            )

            past_time = datetime.utcnow() - timedelta(minutes=5)
            mock_func = MagicMock(return_value="result_value")
            scheduler.register_function("history_func", mock_func)

            scheduler.schedule_task(
                task_id="history-001",
                func="history_func",
                when=past_time,
            )

            scheduler.run_due_tasks()

            history = scheduler.get_task_history()
            assert len(history) == 1
            assert history[0].task_id == "history-001"
            assert history[0].success is True

    def test_run_due_tasks_removes_one_time_tasks(self):
        """Test that one-time tasks are removed after execution."""
        from bots.shared.scheduler import ClawdBotScheduler

        with tempfile.TemporaryDirectory() as tmpdir:
            scheduler = ClawdBotScheduler(
                tasks_path=Path(tmpdir) / "tasks.json",
                history_path=Path(tmpdir) / "history.json",
            )

            past_time = datetime.utcnow() - timedelta(minutes=5)
            mock_func = MagicMock()
            scheduler.register_function("once_func", mock_func)

            scheduler.schedule_task(
                task_id="once-001",
                func="once_func",
                when=past_time,
                recurring=False,
            )

            scheduler.run_due_tasks()

            # Task should be removed
            tasks = scheduler.get_scheduled_tasks()
            assert len(tasks) == 0

    def test_run_due_tasks_reschedules_recurring_tasks(self):
        """Test that recurring tasks are rescheduled."""
        from bots.shared.scheduler import ClawdBotScheduler

        with tempfile.TemporaryDirectory() as tmpdir:
            scheduler = ClawdBotScheduler(
                tasks_path=Path(tmpdir) / "tasks.json",
                history_path=Path(tmpdir) / "history.json",
            )

            past_time = datetime.utcnow() - timedelta(minutes=5)
            mock_func = MagicMock()
            scheduler.register_function("recurring_func", mock_func)

            scheduler.schedule_task(
                task_id="recurring-001",
                func="recurring_func",
                when=past_time,
                recurring=True,
                cron="*/5 * * * *",  # Every 5 minutes
            )

            scheduler.run_due_tasks()

            # Task should still exist with new scheduled time
            tasks = scheduler.get_scheduled_tasks()
            assert len(tasks) == 1
            assert tasks[0].scheduled_time > datetime.utcnow()

    def test_run_due_tasks_handles_errors(self):
        """Test that task errors are recorded in history."""
        from bots.shared.scheduler import ClawdBotScheduler

        with tempfile.TemporaryDirectory() as tmpdir:
            scheduler = ClawdBotScheduler(
                tasks_path=Path(tmpdir) / "tasks.json",
                history_path=Path(tmpdir) / "history.json",
            )

            past_time = datetime.utcnow() - timedelta(minutes=5)
            mock_func = MagicMock(side_effect=RuntimeError("Task failed"))
            scheduler.register_function("error_func", mock_func)

            scheduler.schedule_task(
                task_id="error-001",
                func="error_func",
                when=past_time,
            )

            results = scheduler.run_due_tasks()

            assert len(results) == 1
            history = scheduler.get_task_history()
            assert history[0].success is False
            assert "Task failed" in history[0].error


# =============================================================================
# Missed Task Handling Tests
# =============================================================================

class TestMissedTaskHandling:
    """Tests for missed task handling (runs immediately)."""

    def test_missed_tasks_run_immediately(self):
        """Test that missed tasks are run immediately when scheduler starts."""
        from bots.shared.scheduler import ClawdBotScheduler

        with tempfile.TemporaryDirectory() as tmpdir:
            tasks_path = Path(tmpdir) / "tasks.json"
            history_path = Path(tmpdir) / "history.json"

            # Pre-create a task that was scheduled in the past
            past_time = datetime.utcnow() - timedelta(hours=2)
            tasks_data = [
                {
                    "id": "missed-001",
                    "name": "Missed Task",
                    "function_name": "missed_func",
                    "args": {},
                    "scheduled_time": past_time.isoformat(),
                    "recurring": False,
                    "cron": None,
                    "status": "pending",
                }
            ]
            tasks_path.write_text(json.dumps(tasks_data))

            scheduler = ClawdBotScheduler(
                tasks_path=tasks_path,
                history_path=history_path,
            )

            mock_func = MagicMock()
            scheduler.register_function("missed_func", mock_func)

            # Run due tasks should pick up the missed task
            results = scheduler.run_due_tasks()

            assert len(results) == 1
            mock_func.assert_called_once()


# =============================================================================
# Function Registry Tests
# =============================================================================

class TestFunctionRegistry:
    """Tests for function registration and lookup."""

    def test_register_function(self):
        """Test registering a callable function."""
        from bots.shared.scheduler import ClawdBotScheduler

        with tempfile.TemporaryDirectory() as tmpdir:
            scheduler = ClawdBotScheduler(
                tasks_path=Path(tmpdir) / "tasks.json",
                history_path=Path(tmpdir) / "history.json",
            )

            def my_task():
                return "done"

            scheduler.register_function("my_task", my_task)

            assert scheduler.get_function("my_task") is my_task

    def test_get_unregistered_function_returns_none(self):
        """Test getting an unregistered function returns None."""
        from bots.shared.scheduler import ClawdBotScheduler

        with tempfile.TemporaryDirectory() as tmpdir:
            scheduler = ClawdBotScheduler(
                tasks_path=Path(tmpdir) / "tasks.json",
                history_path=Path(tmpdir) / "history.json",
            )

            assert scheduler.get_function("nonexistent") is None

    def test_run_task_with_unregistered_function(self):
        """Test running a task with unregistered function records error."""
        from bots.shared.scheduler import ClawdBotScheduler

        with tempfile.TemporaryDirectory() as tmpdir:
            scheduler = ClawdBotScheduler(
                tasks_path=Path(tmpdir) / "tasks.json",
                history_path=Path(tmpdir) / "history.json",
            )

            past_time = datetime.utcnow() - timedelta(minutes=5)
            scheduler.schedule_task(
                task_id="unregistered-001",
                func="nonexistent_func",
                when=past_time,
            )

            results = scheduler.run_due_tasks()

            assert len(results) == 1
            history = scheduler.get_task_history()
            assert history[0].success is False
            assert "not registered" in history[0].error.lower()


# =============================================================================
# Persistence Tests
# =============================================================================

class TestPersistence:
    """Tests for file persistence across restarts."""

    def test_tasks_persist_across_scheduler_instances(self):
        """Test that tasks persist across scheduler restarts."""
        from bots.shared.scheduler import ClawdBotScheduler

        with tempfile.TemporaryDirectory() as tmpdir:
            tasks_path = Path(tmpdir) / "tasks.json"
            history_path = Path(tmpdir) / "history.json"

            # First scheduler instance
            scheduler1 = ClawdBotScheduler(
                tasks_path=tasks_path,
                history_path=history_path,
            )

            future_time = datetime.utcnow() + timedelta(hours=1)
            scheduler1.schedule_task(
                task_id="persist-001",
                func="my_func",
                when=future_time,
            )

            # Second scheduler instance (simulates restart)
            scheduler2 = ClawdBotScheduler(
                tasks_path=tasks_path,
                history_path=history_path,
            )

            tasks = scheduler2.get_scheduled_tasks()
            assert len(tasks) == 1
            assert tasks[0].id == "persist-001"

    def test_history_persists_across_scheduler_instances(self):
        """Test that history persists across scheduler restarts."""
        from bots.shared.scheduler import ClawdBotScheduler

        with tempfile.TemporaryDirectory() as tmpdir:
            tasks_path = Path(tmpdir) / "tasks.json"
            history_path = Path(tmpdir) / "history.json"

            # First scheduler instance
            scheduler1 = ClawdBotScheduler(
                tasks_path=tasks_path,
                history_path=history_path,
            )

            past_time = datetime.utcnow() - timedelta(minutes=5)
            mock_func = MagicMock()
            scheduler1.register_function("persist_func", mock_func)

            scheduler1.schedule_task(
                task_id="history-persist-001",
                func="persist_func",
                when=past_time,
            )
            scheduler1.run_due_tasks()

            # Second scheduler instance (simulates restart)
            scheduler2 = ClawdBotScheduler(
                tasks_path=tasks_path,
                history_path=history_path,
            )

            history = scheduler2.get_task_history()
            assert len(history) == 1
            assert history[0].task_id == "history-persist-001"

    def test_corrupted_tasks_file_handled(self):
        """Test that corrupted tasks file is handled gracefully."""
        from bots.shared.scheduler import ClawdBotScheduler

        with tempfile.TemporaryDirectory() as tmpdir:
            tasks_path = Path(tmpdir) / "tasks.json"
            history_path = Path(tmpdir) / "history.json"

            # Write corrupted JSON
            tasks_path.write_text("{ invalid json }")

            scheduler = ClawdBotScheduler(
                tasks_path=tasks_path,
                history_path=history_path,
            )

            # Should not crash, start with empty tasks
            tasks = scheduler.get_scheduled_tasks()
            assert tasks == []
