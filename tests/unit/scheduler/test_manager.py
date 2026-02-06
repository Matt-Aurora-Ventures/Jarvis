"""
Tests for core/scheduler/manager.py

Scheduler class tests covering:
- schedule_once(task, run_at)
- schedule_recurring(task, interval_seconds)
- schedule_cron(task, cron_expression)
- cancel(task_id)
- list_scheduled() -> List[ScheduledTask]
- Scheduler lifecycle (start/stop)
- Job execution and callbacks
"""

import asyncio
import pytest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, AsyncMock, patch


class TestSchedulerCreation:
    """Tests for Scheduler initialization."""

    def test_scheduler_creation_default(self):
        """Scheduler should be created with defaults."""
        from core.scheduler.manager import Scheduler

        scheduler = Scheduler()

        assert scheduler is not None
        assert scheduler.is_running is False

    def test_scheduler_creation_with_options(self):
        """Scheduler should accept configuration options."""
        from core.scheduler.manager import Scheduler

        scheduler = Scheduler(
            max_concurrent_jobs=5,
            check_interval=0.5,
        )

        assert scheduler.max_concurrent_jobs == 5
        assert scheduler.check_interval == 0.5

    def test_scheduler_with_persistence(self):
        """Scheduler should accept persistence store."""
        from core.scheduler.manager import Scheduler
        from core.scheduler.persistence import ScheduleStore

        store = MagicMock(spec=ScheduleStore)
        scheduler = Scheduler(persistence_store=store)

        assert scheduler.persistence_store == store


class TestScheduleOnce:
    """Tests for schedule_once method."""

    def test_schedule_once_returns_task_id(self):
        """schedule_once should return task ID."""
        from core.scheduler.manager import Scheduler
        from core.scheduler.tasks import Task

        scheduler = Scheduler()
        task = Task(name="one_time", handler=lambda: "done")
        run_at = datetime.utcnow() + timedelta(hours=1)

        task_id = scheduler.schedule_once(task, run_at)

        assert task_id is not None
        assert isinstance(task_id, str)

    def test_schedule_once_stores_task(self):
        """schedule_once should store task in scheduler."""
        from core.scheduler.manager import Scheduler
        from core.scheduler.tasks import Task

        scheduler = Scheduler()
        task = Task(name="stored_task", handler=lambda: None)
        run_at = datetime.utcnow() + timedelta(hours=1)

        task_id = scheduler.schedule_once(task, run_at)

        scheduled_tasks = scheduler.list_scheduled()
        assert len(scheduled_tasks) == 1
        assert scheduled_tasks[0].task.name == "stored_task"

    def test_schedule_once_sets_run_at(self):
        """schedule_once should set correct run_at time."""
        from core.scheduler.manager import Scheduler
        from core.scheduler.tasks import Task

        scheduler = Scheduler()
        task = Task(name="timed_task", handler=lambda: None)
        run_at = datetime(2026, 6, 15, 9, 0, 0)

        scheduler.schedule_once(task, run_at)

        scheduled = scheduler.list_scheduled()[0]
        assert scheduled.run_at == run_at

    def test_schedule_once_marks_non_recurring(self):
        """schedule_once should mark task as non-recurring."""
        from core.scheduler.manager import Scheduler
        from core.scheduler.tasks import Task

        scheduler = Scheduler()
        task = Task(name="single_task", handler=lambda: None)
        run_at = datetime.utcnow() + timedelta(hours=1)

        scheduler.schedule_once(task, run_at)

        scheduled = scheduler.list_scheduled()[0]
        assert scheduled.recurring is False

    def test_schedule_once_past_time_raises(self):
        """schedule_once should reject times in the past."""
        from core.scheduler.manager import Scheduler
        from core.scheduler.tasks import Task

        scheduler = Scheduler()
        task = Task(name="past_task", handler=lambda: None)
        run_at = datetime.utcnow() - timedelta(hours=1)

        with pytest.raises(ValueError, match="past"):
            scheduler.schedule_once(task, run_at)


class TestScheduleRecurring:
    """Tests for schedule_recurring method."""

    def test_schedule_recurring_returns_task_id(self):
        """schedule_recurring should return task ID."""
        from core.scheduler.manager import Scheduler
        from core.scheduler.tasks import Task

        scheduler = Scheduler()
        task = Task(name="recurring", handler=lambda: None)

        task_id = scheduler.schedule_recurring(task, interval_seconds=3600)

        assert task_id is not None

    def test_schedule_recurring_sets_interval(self):
        """schedule_recurring should set correct interval."""
        from core.scheduler.manager import Scheduler
        from core.scheduler.tasks import Task

        scheduler = Scheduler()
        task = Task(name="hourly", handler=lambda: None)

        scheduler.schedule_recurring(task, interval_seconds=3600)

        scheduled = scheduler.list_scheduled()[0]
        assert scheduled.interval_seconds == 3600
        assert scheduled.recurring is True

    def test_schedule_recurring_start_immediately(self):
        """schedule_recurring should optionally start immediately."""
        from core.scheduler.manager import Scheduler
        from core.scheduler.tasks import Task

        scheduler = Scheduler()
        task = Task(name="immediate", handler=lambda: None)

        before = datetime.utcnow()
        scheduler.schedule_recurring(task, interval_seconds=3600, start_immediately=True)
        after = datetime.utcnow() + timedelta(seconds=1)

        scheduled = scheduler.list_scheduled()[0]
        assert before <= scheduled.run_at <= after

    def test_schedule_recurring_start_delayed(self):
        """schedule_recurring should start after interval by default."""
        from core.scheduler.manager import Scheduler
        from core.scheduler.tasks import Task

        scheduler = Scheduler()
        task = Task(name="delayed", handler=lambda: None)

        before = datetime.utcnow() + timedelta(seconds=3599)
        scheduler.schedule_recurring(task, interval_seconds=3600, start_immediately=False)
        after = datetime.utcnow() + timedelta(seconds=3601)

        scheduled = scheduler.list_scheduled()[0]
        assert before <= scheduled.run_at <= after

    def test_schedule_recurring_invalid_interval(self):
        """schedule_recurring should reject zero/negative interval."""
        from core.scheduler.manager import Scheduler
        from core.scheduler.tasks import Task

        scheduler = Scheduler()
        task = Task(name="bad_interval", handler=lambda: None)

        with pytest.raises(ValueError, match="positive"):
            scheduler.schedule_recurring(task, interval_seconds=0)

        with pytest.raises(ValueError, match="positive"):
            scheduler.schedule_recurring(task, interval_seconds=-60)


class TestScheduleCron:
    """Tests for schedule_cron method."""

    def test_schedule_cron_returns_task_id(self):
        """schedule_cron should return task ID."""
        from core.scheduler.manager import Scheduler
        from core.scheduler.tasks import Task

        scheduler = Scheduler()
        task = Task(name="cron_task", handler=lambda: None)

        task_id = scheduler.schedule_cron(task, "0 9 * * *")

        assert task_id is not None

    def test_schedule_cron_stores_expression(self):
        """schedule_cron should store cron expression."""
        from core.scheduler.manager import Scheduler
        from core.scheduler.tasks import Task

        scheduler = Scheduler()
        task = Task(name="daily_9am", handler=lambda: None)

        scheduler.schedule_cron(task, "0 9 * * *")

        scheduled = scheduler.list_scheduled()[0]
        assert scheduled.cron_expression == "0 9 * * *"

    def test_schedule_cron_calculates_next_run(self):
        """schedule_cron should calculate next run time."""
        from core.scheduler.manager import Scheduler
        from core.scheduler.tasks import Task

        scheduler = Scheduler()
        task = Task(name="cron_next", handler=lambda: None)

        scheduler.schedule_cron(task, "0 9 * * *")

        scheduled = scheduler.list_scheduled()[0]
        assert scheduled.run_at is not None
        assert scheduled.run_at.hour == 9
        assert scheduled.run_at.minute == 0

    def test_schedule_cron_marks_recurring(self):
        """schedule_cron should mark task as recurring."""
        from core.scheduler.manager import Scheduler
        from core.scheduler.tasks import Task

        scheduler = Scheduler()
        task = Task(name="cron_recurring", handler=lambda: None)

        scheduler.schedule_cron(task, "*/5 * * * *")

        scheduled = scheduler.list_scheduled()[0]
        assert scheduled.recurring is True

    def test_schedule_cron_invalid_expression(self):
        """schedule_cron should reject invalid cron expressions."""
        from core.scheduler.manager import Scheduler
        from core.scheduler.tasks import Task

        scheduler = Scheduler()
        task = Task(name="bad_cron", handler=lambda: None)

        with pytest.raises(ValueError, match="Invalid cron"):
            scheduler.schedule_cron(task, "invalid cron")


class TestCancel:
    """Tests for cancel method."""

    def test_cancel_returns_true_on_success(self):
        """cancel should return True when task is found."""
        from core.scheduler.manager import Scheduler
        from core.scheduler.tasks import Task

        scheduler = Scheduler()
        task = Task(name="to_cancel", handler=lambda: None)
        task_id = scheduler.schedule_once(task, datetime.utcnow() + timedelta(hours=1))

        result = scheduler.cancel(task_id)

        assert result is True

    def test_cancel_removes_task(self):
        """cancel should remove task from scheduler."""
        from core.scheduler.manager import Scheduler
        from core.scheduler.tasks import Task

        scheduler = Scheduler()
        task = Task(name="will_remove", handler=lambda: None)
        task_id = scheduler.schedule_once(task, datetime.utcnow() + timedelta(hours=1))

        scheduler.cancel(task_id)

        assert len(scheduler.list_scheduled()) == 0

    def test_cancel_returns_false_for_unknown(self):
        """cancel should return False for unknown task ID."""
        from core.scheduler.manager import Scheduler

        scheduler = Scheduler()

        result = scheduler.cancel("unknown-id")

        assert result is False

    @pytest.mark.asyncio
    async def test_cancel_stops_running_task(self):
        """cancel should stop a currently running task."""
        from core.scheduler.manager import Scheduler
        from core.scheduler.tasks import Task

        scheduler = Scheduler()
        cancelled = asyncio.Event()

        async def long_running():
            try:
                await asyncio.sleep(100)
            except asyncio.CancelledError:
                cancelled.set()
                raise

        task = Task(name="long_task", handler=long_running)
        task_id = scheduler.schedule_once(task, datetime.utcnow())

        await scheduler.start()
        await asyncio.sleep(0.1)  # Let it start

        scheduler.cancel(task_id)
        await asyncio.sleep(0.1)

        await scheduler.stop()

        # Task should have been cancelled
        assert cancelled.is_set()


class TestListScheduled:
    """Tests for list_scheduled method."""

    def test_list_scheduled_empty(self):
        """list_scheduled should return empty list initially."""
        from core.scheduler.manager import Scheduler

        scheduler = Scheduler()

        result = scheduler.list_scheduled()

        assert result == []

    def test_list_scheduled_returns_all(self):
        """list_scheduled should return all scheduled tasks."""
        from core.scheduler.manager import Scheduler
        from core.scheduler.tasks import Task

        scheduler = Scheduler()
        for i in range(5):
            task = Task(name=f"task_{i}", handler=lambda: None)
            scheduler.schedule_once(task, datetime.utcnow() + timedelta(hours=i+1))

        result = scheduler.list_scheduled()

        assert len(result) == 5

    def test_list_scheduled_sorted_by_run_at(self):
        """list_scheduled should return tasks sorted by run_at."""
        from core.scheduler.manager import Scheduler
        from core.scheduler.tasks import Task

        scheduler = Scheduler()

        # Add in reverse order
        for i in [3, 1, 2]:
            task = Task(name=f"task_{i}", handler=lambda: None)
            scheduler.schedule_once(task, datetime.utcnow() + timedelta(hours=i))

        result = scheduler.list_scheduled()

        # Should be sorted: task_1, task_2, task_3
        run_times = [s.run_at for s in result]
        assert run_times == sorted(run_times)

    def test_list_scheduled_with_filter(self):
        """list_scheduled should support filtering."""
        from core.scheduler.manager import Scheduler
        from core.scheduler.tasks import Task

        scheduler = Scheduler()

        task1 = Task(name="tagged", handler=lambda: None, tags=["important"])
        task2 = Task(name="untagged", handler=lambda: None, tags=[])

        scheduler.schedule_once(task1, datetime.utcnow() + timedelta(hours=1))
        scheduler.schedule_once(task2, datetime.utcnow() + timedelta(hours=2))

        result = scheduler.list_scheduled(tags=["important"])

        assert len(result) == 1
        assert result[0].task.name == "tagged"


class TestSchedulerLifecycle:
    """Tests for scheduler start/stop."""

    @pytest.mark.asyncio
    async def test_start_scheduler(self):
        """start should start the scheduler loop."""
        from core.scheduler.manager import Scheduler

        scheduler = Scheduler()

        await scheduler.start()

        assert scheduler.is_running is True

        await scheduler.stop()

    @pytest.mark.asyncio
    async def test_stop_scheduler(self):
        """stop should stop the scheduler loop."""
        from core.scheduler.manager import Scheduler

        scheduler = Scheduler()
        await scheduler.start()

        await scheduler.stop()

        assert scheduler.is_running is False

    @pytest.mark.asyncio
    async def test_start_twice_is_safe(self):
        """Starting twice should be safe."""
        from core.scheduler.manager import Scheduler

        scheduler = Scheduler()

        await scheduler.start()
        await scheduler.start()  # Should not raise

        assert scheduler.is_running is True

        await scheduler.stop()

    @pytest.mark.asyncio
    async def test_stop_without_start_is_safe(self):
        """Stopping without starting should be safe."""
        from core.scheduler.manager import Scheduler

        scheduler = Scheduler()

        await scheduler.stop()  # Should not raise

        assert scheduler.is_running is False


class TestSchedulerExecution:
    """Tests for task execution."""

    @pytest.mark.asyncio
    async def test_executes_due_task(self):
        """Scheduler should execute tasks when due."""
        from core.scheduler.manager import Scheduler
        from core.scheduler.tasks import Task

        scheduler = Scheduler(check_interval=0.05)
        result_holder = []

        def handler():
            result_holder.append("executed")
            return "done"

        task = Task(name="due_task", handler=handler)
        scheduler.schedule_once(task, datetime.utcnow())

        await scheduler.start()
        await asyncio.sleep(0.2)
        await scheduler.stop()

        assert "executed" in result_holder

    @pytest.mark.asyncio
    async def test_executes_async_task(self):
        """Scheduler should execute async tasks."""
        from core.scheduler.manager import Scheduler
        from core.scheduler.tasks import Task

        scheduler = Scheduler(check_interval=0.05)
        result_holder = []

        async def async_handler():
            await asyncio.sleep(0.01)
            result_holder.append("async_done")
            return "async_result"

        task = Task(name="async_task", handler=async_handler)
        scheduler.schedule_once(task, datetime.utcnow())

        await scheduler.start()
        await asyncio.sleep(0.2)
        await scheduler.stop()

        assert "async_done" in result_holder

    @pytest.mark.asyncio
    async def test_recurring_task_reschedules(self):
        """Recurring tasks should reschedule after execution."""
        from core.scheduler.manager import Scheduler
        from core.scheduler.tasks import Task

        scheduler = Scheduler(check_interval=0.05)
        execution_count = [0]

        def handler():
            execution_count[0] += 1

        task = Task(name="repeat", handler=handler)
        scheduler.schedule_recurring(task, interval_seconds=0.1, start_immediately=True)

        await scheduler.start()
        await asyncio.sleep(0.35)  # Should run ~3 times
        await scheduler.stop()

        assert execution_count[0] >= 2

    @pytest.mark.asyncio
    async def test_max_concurrent_jobs(self):
        """Scheduler should respect max concurrent jobs."""
        from core.scheduler.manager import Scheduler
        from core.scheduler.tasks import Task

        scheduler = Scheduler(max_concurrent_jobs=2, check_interval=0.05)
        concurrent_count = [0]
        max_concurrent = [0]

        async def slow_handler():
            concurrent_count[0] += 1
            max_concurrent[0] = max(max_concurrent[0], concurrent_count[0])
            await asyncio.sleep(0.2)
            concurrent_count[0] -= 1

        # Schedule 5 tasks
        for i in range(5):
            task = Task(name=f"concurrent_{i}", handler=slow_handler)
            scheduler.schedule_once(task, datetime.utcnow())

        await scheduler.start()
        await asyncio.sleep(0.5)
        await scheduler.stop()

        assert max_concurrent[0] <= 2

    @pytest.mark.asyncio
    async def test_task_timeout(self):
        """Task should timeout if it takes too long."""
        from core.scheduler.manager import Scheduler
        from core.scheduler.tasks import Task

        scheduler = Scheduler(check_interval=0.05)
        timed_out = [False]

        async def slow_handler():
            await asyncio.sleep(10)

        task = Task(name="timeout_task", handler=slow_handler, timeout=0.1)

        def on_failure(result):
            if "timeout" in str(result.error).lower():
                timed_out[0] = True

        task.on_failure = on_failure
        scheduler.schedule_once(task, datetime.utcnow())

        await scheduler.start()
        await asyncio.sleep(0.3)
        await scheduler.stop()

        assert timed_out[0]


class TestSchedulerEvents:
    """Tests for scheduler events/callbacks."""

    @pytest.mark.asyncio
    async def test_on_task_started_callback(self):
        """Scheduler should call on_task_started callback."""
        from core.scheduler.manager import Scheduler
        from core.scheduler.tasks import Task

        scheduler = Scheduler(check_interval=0.05)
        started_tasks = []

        def on_started(scheduled_task):
            started_tasks.append(scheduled_task.task.name)

        scheduler.on_task_started = on_started

        task = Task(name="started_task", handler=lambda: None)
        scheduler.schedule_once(task, datetime.utcnow())

        await scheduler.start()
        await asyncio.sleep(0.2)
        await scheduler.stop()

        assert "started_task" in started_tasks

    @pytest.mark.asyncio
    async def test_on_task_completed_callback(self):
        """Scheduler should call on_task_completed callback."""
        from core.scheduler.manager import Scheduler
        from core.scheduler.tasks import Task

        scheduler = Scheduler(check_interval=0.05)
        completed_tasks = []

        def on_completed(scheduled_task, result):
            completed_tasks.append((scheduled_task.task.name, result.success))

        scheduler.on_task_completed = on_completed

        task = Task(name="completed_task", handler=lambda: "result")
        scheduler.schedule_once(task, datetime.utcnow())

        await scheduler.start()
        await asyncio.sleep(0.2)
        await scheduler.stop()

        assert ("completed_task", True) in completed_tasks

    @pytest.mark.asyncio
    async def test_on_task_failed_callback(self):
        """Scheduler should call on_task_failed callback."""
        from core.scheduler.manager import Scheduler
        from core.scheduler.tasks import Task

        scheduler = Scheduler(check_interval=0.05)
        failed_tasks = []

        def on_failed(scheduled_task, result):
            failed_tasks.append((scheduled_task.task.name, result.error))

        scheduler.on_task_failed = on_failed

        def bad_handler():
            raise ValueError("Task error")

        task = Task(name="failed_task", handler=bad_handler)
        scheduler.schedule_once(task, datetime.utcnow())

        await scheduler.start()
        await asyncio.sleep(0.2)
        await scheduler.stop()

        assert len(failed_tasks) == 1
        assert failed_tasks[0][0] == "failed_task"
        assert "Task error" in failed_tasks[0][1]


class TestSchedulerPersistence:
    """Tests for scheduler persistence integration."""

    @pytest.mark.asyncio
    async def test_loads_schedules_on_start(self):
        """Scheduler should load schedules from persistence on start."""
        from core.scheduler.manager import Scheduler
        from core.scheduler.persistence import ScheduleStore
        from core.scheduler.tasks import Task, ScheduledTask

        mock_store = AsyncMock(spec=ScheduleStore)
        mock_task = Task(name="persisted", handler=lambda: None)
        mock_scheduled = ScheduledTask(
            task=mock_task,
            run_at=datetime.utcnow() + timedelta(hours=1),
        )
        mock_store.load_schedules.return_value = [mock_scheduled]

        scheduler = Scheduler(persistence_store=mock_store)
        await scheduler.start()

        mock_store.load_schedules.assert_called_once()

        await scheduler.stop()

    @pytest.mark.asyncio
    async def test_saves_schedule_to_persistence(self):
        """Scheduler should save schedules to persistence."""
        from core.scheduler.manager import Scheduler
        from core.scheduler.persistence import ScheduleStore
        from core.scheduler.tasks import Task

        mock_store = AsyncMock(spec=ScheduleStore)
        mock_store.load_schedules.return_value = []

        scheduler = Scheduler(persistence_store=mock_store)
        await scheduler.start()

        task = Task(name="to_persist", handler=lambda: None)
        scheduler.schedule_once(task, datetime.utcnow() + timedelta(hours=1))

        mock_store.save_schedule.assert_called_once()

        await scheduler.stop()


class TestGetScheduledTask:
    """Tests for get_scheduled_task method."""

    def test_get_by_id(self):
        """get_scheduled_task should retrieve by ID."""
        from core.scheduler.manager import Scheduler
        from core.scheduler.tasks import Task

        scheduler = Scheduler()
        task = Task(name="findme", handler=lambda: None)
        task_id = scheduler.schedule_once(task, datetime.utcnow() + timedelta(hours=1))

        found = scheduler.get_scheduled_task(task_id)

        assert found is not None
        assert found.task.name == "findme"

    def test_get_unknown_id_returns_none(self):
        """get_scheduled_task should return None for unknown ID."""
        from core.scheduler.manager import Scheduler

        scheduler = Scheduler()

        found = scheduler.get_scheduled_task("unknown")

        assert found is None
