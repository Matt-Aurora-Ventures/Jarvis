"""
Tests for core/scheduler/tasks.py

Task base class tests covering:
- Task creation with name, handler, args, kwargs
- run() execution and TaskResult generation
- on_success() and on_failure() callbacks
- Task validation
- Task serialization
"""

import asyncio
import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch


class TestTaskResult:
    """Tests for TaskResult dataclass."""

    def test_task_result_creation(self):
        """TaskResult should store execution results."""
        from core.scheduler.tasks import TaskResult

        result = TaskResult(
            success=True,
            result="test output",
            error=None,
            started_at=datetime(2026, 1, 1, 0, 0, 0),
            completed_at=datetime(2026, 1, 1, 0, 0, 1),
        )

        assert result.success is True
        assert result.result == "test output"
        assert result.error is None
        assert result.duration_ms == 1000.0

    def test_task_result_failure(self):
        """TaskResult should store failure information."""
        from core.scheduler.tasks import TaskResult

        result = TaskResult(
            success=False,
            result=None,
            error="Connection timeout",
            started_at=datetime(2026, 1, 1, 0, 0, 0),
            completed_at=datetime(2026, 1, 1, 0, 0, 5),
        )

        assert result.success is False
        assert result.error == "Connection timeout"
        assert result.duration_ms == 5000.0

    def test_task_result_duration_none_when_incomplete(self):
        """Duration should be None if timestamps are missing."""
        from core.scheduler.tasks import TaskResult

        result = TaskResult(success=True, result="ok")
        assert result.duration_ms is None

    def test_task_result_to_dict(self):
        """TaskResult should be serializable to dict."""
        from core.scheduler.tasks import TaskResult

        result = TaskResult(
            success=True,
            result={"data": [1, 2, 3]},
            error=None,
            started_at=datetime(2026, 1, 1, 0, 0, 0),
            completed_at=datetime(2026, 1, 1, 0, 0, 1),
        )

        data = result.to_dict()
        assert data["success"] is True
        assert data["result"] == {"data": [1, 2, 3]}
        assert "started_at" in data


class TestTask:
    """Tests for Task base class."""

    def test_task_creation_with_sync_handler(self):
        """Task should be created with a synchronous handler."""
        from core.scheduler.tasks import Task

        def my_handler(x, y):
            return x + y

        task = Task(name="add_task", handler=my_handler, args=(1, 2))

        assert task.name == "add_task"
        assert task.handler == my_handler
        assert task.args == (1, 2)
        assert task.kwargs == {}
        assert task.id is not None

    def test_task_creation_with_async_handler(self):
        """Task should be created with an async handler."""
        from core.scheduler.tasks import Task

        async def my_async_handler(message):
            return f"Processed: {message}"

        task = Task(
            name="async_task",
            handler=my_async_handler,
            kwargs={"message": "hello"}
        )

        assert task.name == "async_task"
        assert task.kwargs == {"message": "hello"}

    def test_task_creation_with_all_options(self):
        """Task should accept all configuration options."""
        from core.scheduler.tasks import Task

        def handler():
            pass

        task = Task(
            name="full_task",
            handler=handler,
            args=(1, 2, 3),
            kwargs={"key": "value"},
            timeout=60.0,
            retry_count=3,
            retry_delay=5.0,
            tags=["critical", "daily"],
            metadata={"source": "api"},
        )

        assert task.timeout == 60.0
        assert task.retry_count == 3
        assert task.retry_delay == 5.0
        assert "critical" in task.tags
        assert task.metadata["source"] == "api"

    def test_task_id_generation(self):
        """Each task should have a unique ID."""
        from core.scheduler.tasks import Task

        task1 = Task(name="task1", handler=lambda: None)
        task2 = Task(name="task2", handler=lambda: None)

        assert task1.id != task2.id

    def test_task_custom_id(self):
        """Task should accept a custom ID."""
        from core.scheduler.tasks import Task

        task = Task(
            name="custom_id_task",
            handler=lambda: None,
            id="custom-123"
        )

        assert task.id == "custom-123"

    @pytest.mark.asyncio
    async def test_task_run_sync_handler(self):
        """run() should execute sync handler and return TaskResult."""
        from core.scheduler.tasks import Task

        def handler(a, b):
            return a * b

        task = Task(name="multiply", handler=handler, args=(3, 4))
        result = await task.run()

        assert result.success is True
        assert result.result == 12
        assert result.error is None

    @pytest.mark.asyncio
    async def test_task_run_async_handler(self):
        """run() should execute async handler and return TaskResult."""
        from core.scheduler.tasks import Task

        async def handler(items):
            await asyncio.sleep(0.01)
            return sum(items)

        task = Task(name="sum_async", handler=handler, kwargs={"items": [1, 2, 3]})
        result = await task.run()

        assert result.success is True
        assert result.result == 6

    @pytest.mark.asyncio
    async def test_task_run_with_exception(self):
        """run() should capture exceptions in TaskResult."""
        from core.scheduler.tasks import Task

        def bad_handler():
            raise ValueError("Something went wrong")

        task = Task(name="bad_task", handler=bad_handler)
        result = await task.run()

        assert result.success is False
        assert result.result is None
        assert "Something went wrong" in result.error

    @pytest.mark.asyncio
    async def test_task_run_with_timeout(self):
        """run() should timeout if handler takes too long."""
        from core.scheduler.tasks import Task

        async def slow_handler():
            await asyncio.sleep(10)
            return "done"

        task = Task(name="slow_task", handler=slow_handler, timeout=0.1)
        result = await task.run()

        assert result.success is False
        assert "timeout" in result.error.lower()

    @pytest.mark.asyncio
    async def test_task_on_success_callback(self):
        """on_success() should be called when task succeeds."""
        from core.scheduler.tasks import Task

        success_callback = MagicMock()

        def handler():
            return "success"

        task = Task(name="success_task", handler=handler)
        task.on_success = success_callback

        result = await task.run()

        success_callback.assert_called_once()
        call_args = success_callback.call_args[0]
        assert call_args[0].success is True

    @pytest.mark.asyncio
    async def test_task_on_failure_callback(self):
        """on_failure() should be called when task fails."""
        from core.scheduler.tasks import Task

        failure_callback = MagicMock()

        def handler():
            raise RuntimeError("Failed!")

        task = Task(name="failure_task", handler=handler)
        task.on_failure = failure_callback

        result = await task.run()

        failure_callback.assert_called_once()
        call_args = failure_callback.call_args[0]
        assert call_args[0].success is False

    @pytest.mark.asyncio
    async def test_task_on_success_async_callback(self):
        """on_success() should support async callbacks."""
        from core.scheduler.tasks import Task

        called_with = []

        async def success_callback(result):
            called_with.append(result)

        def handler():
            return 42

        task = Task(name="async_success_task", handler=handler)
        task.on_success = success_callback

        await task.run()

        assert len(called_with) == 1
        assert called_with[0].result == 42

    @pytest.mark.asyncio
    async def test_task_callback_exception_does_not_affect_result(self):
        """Callback exceptions should not affect task result."""
        from core.scheduler.tasks import Task

        def bad_callback(result):
            raise Exception("Callback error")

        def handler():
            return "ok"

        task = Task(name="callback_error_task", handler=handler)
        task.on_success = bad_callback

        result = await task.run()

        # Task should still show as successful
        assert result.success is True
        assert result.result == "ok"

    def test_task_validation_requires_name(self):
        """Task should require a name."""
        from core.scheduler.tasks import Task

        with pytest.raises((ValueError, TypeError)):
            Task(name="", handler=lambda: None)

    def test_task_validation_requires_handler(self):
        """Task should require a handler."""
        from core.scheduler.tasks import Task

        with pytest.raises((ValueError, TypeError)):
            Task(name="no_handler", handler=None)

    def test_task_to_dict(self):
        """Task should be serializable to dict."""
        from core.scheduler.tasks import Task

        def handler():
            return 1

        task = Task(
            name="serializable_task",
            handler=handler,
            args=(1, 2),
            kwargs={"x": 3},
            tags=["test"]
        )

        data = task.to_dict()
        assert data["name"] == "serializable_task"
        assert data["args"] == (1, 2)
        assert data["kwargs"] == {"x": 3}
        assert "test" in data["tags"]

    def test_task_created_at_timestamp(self):
        """Task should have a created_at timestamp."""
        from core.scheduler.tasks import Task

        before = datetime.utcnow()
        task = Task(name="timestamped", handler=lambda: None)
        after = datetime.utcnow()

        assert before <= task.created_at <= after


class TestScheduledTask:
    """Tests for ScheduledTask wrapper."""

    def test_scheduled_task_creation(self):
        """ScheduledTask should wrap Task with schedule info."""
        from core.scheduler.tasks import Task, ScheduledTask
        from datetime import datetime, timedelta

        task = Task(name="base_task", handler=lambda: None)
        run_at = datetime.utcnow() + timedelta(hours=1)

        scheduled = ScheduledTask(
            task=task,
            run_at=run_at,
            recurring=False,
        )

        assert scheduled.task == task
        assert scheduled.run_at == run_at
        assert scheduled.recurring is False

    def test_scheduled_task_recurring(self):
        """ScheduledTask should support recurring schedules."""
        from core.scheduler.tasks import Task, ScheduledTask

        task = Task(name="recurring_task", handler=lambda: None)

        scheduled = ScheduledTask(
            task=task,
            interval_seconds=3600,
            recurring=True,
        )

        assert scheduled.recurring is True
        assert scheduled.interval_seconds == 3600

    def test_scheduled_task_cron_expression(self):
        """ScheduledTask should support cron expressions."""
        from core.scheduler.tasks import Task, ScheduledTask

        task = Task(name="cron_task", handler=lambda: None)

        scheduled = ScheduledTask(
            task=task,
            cron_expression="0 9 * * *",
            recurring=True,
        )

        assert scheduled.cron_expression == "0 9 * * *"

    def test_scheduled_task_status_tracking(self):
        """ScheduledTask should track execution status."""
        from core.scheduler.tasks import Task, ScheduledTask, ScheduleStatus

        task = Task(name="status_task", handler=lambda: None)
        scheduled = ScheduledTask(task=task, run_at=datetime.utcnow())

        assert scheduled.status == ScheduleStatus.PENDING

    def test_scheduled_task_run_count(self):
        """ScheduledTask should track run count."""
        from core.scheduler.tasks import Task, ScheduledTask

        task = Task(name="counted_task", handler=lambda: None)
        scheduled = ScheduledTask(task=task, run_at=datetime.utcnow())

        assert scheduled.run_count == 0
        scheduled.run_count += 1
        assert scheduled.run_count == 1

    def test_scheduled_task_last_run(self):
        """ScheduledTask should track last run time."""
        from core.scheduler.tasks import Task, ScheduledTask

        task = Task(name="tracked_task", handler=lambda: None)
        scheduled = ScheduledTask(task=task, run_at=datetime.utcnow())

        assert scheduled.last_run is None

    def test_scheduled_task_max_runs(self):
        """ScheduledTask should support max run limit."""
        from core.scheduler.tasks import Task, ScheduledTask

        task = Task(name="limited_task", handler=lambda: None)
        scheduled = ScheduledTask(
            task=task,
            run_at=datetime.utcnow(),
            max_runs=5,
        )

        assert scheduled.max_runs == 5

    def test_scheduled_task_enabled_flag(self):
        """ScheduledTask should have enabled flag."""
        from core.scheduler.tasks import Task, ScheduledTask

        task = Task(name="enabled_task", handler=lambda: None)
        scheduled = ScheduledTask(task=task, run_at=datetime.utcnow())

        assert scheduled.enabled is True
        scheduled.enabled = False
        assert scheduled.enabled is False
