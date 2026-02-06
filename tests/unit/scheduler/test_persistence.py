"""
Tests for core/scheduler/persistence.py

ScheduleStore tests covering:
- save_schedule(task) - persist scheduled tasks
- load_schedules() -> List[Task] - restore from persistence
- Survive restarts
- File-based and optional database persistence
"""

import pytest
import tempfile
import os
import json
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch, AsyncMock


class TestScheduleStore:
    """Tests for ScheduleStore class."""

    def test_schedule_store_creation_with_file_path(self):
        """ScheduleStore should accept file path for persistence."""
        from core.scheduler.persistence import ScheduleStore

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "schedules.json"
            store = ScheduleStore(persistence_path=path)

            assert store.persistence_path == path

    def test_schedule_store_creation_default_path(self):
        """ScheduleStore should use default path if none provided."""
        from core.scheduler.persistence import ScheduleStore

        store = ScheduleStore()

        assert store.persistence_path is not None
        assert "schedules" in str(store.persistence_path).lower()

    @pytest.mark.asyncio
    async def test_save_schedule_creates_file(self):
        """save_schedule should create persistence file."""
        from core.scheduler.persistence import ScheduleStore
        from core.scheduler.tasks import Task, ScheduledTask

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "schedules.json"
            store = ScheduleStore(persistence_path=path)

            task = Task(name="test_task", handler=lambda: None)
            scheduled = ScheduledTask(
                task=task,
                run_at=datetime.utcnow() + timedelta(hours=1),
            )

            await store.save_schedule(scheduled)

            assert path.exists()

    @pytest.mark.asyncio
    async def test_save_schedule_preserves_task_data(self):
        """save_schedule should preserve all task data."""
        from core.scheduler.persistence import ScheduleStore
        from core.scheduler.tasks import Task, ScheduledTask

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "schedules.json"
            store = ScheduleStore(persistence_path=path)

            task = Task(
                name="data_task",
                handler=lambda x: x,
                args=(1, 2, 3),
                kwargs={"key": "value"},
                tags=["important"],
            )
            run_at = datetime(2026, 6, 15, 9, 0, 0)
            scheduled = ScheduledTask(
                task=task,
                run_at=run_at,
                recurring=False,
            )

            await store.save_schedule(scheduled)

            # Read raw file
            with open(path) as f:
                data = json.load(f)

            assert len(data["schedules"]) == 1
            saved = data["schedules"][0]
            assert saved["task"]["name"] == "data_task"
            assert saved["task"]["args"] == [1, 2, 3]

    @pytest.mark.asyncio
    async def test_save_multiple_schedules(self):
        """save_schedule should handle multiple schedules."""
        from core.scheduler.persistence import ScheduleStore
        from core.scheduler.tasks import Task, ScheduledTask

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "schedules.json"
            store = ScheduleStore(persistence_path=path)

            for i in range(5):
                task = Task(name=f"task_{i}", handler=lambda: None)
                scheduled = ScheduledTask(
                    task=task,
                    run_at=datetime.utcnow() + timedelta(hours=i),
                )
                await store.save_schedule(scheduled)

            schedules = await store.load_schedules()
            assert len(schedules) == 5

    @pytest.mark.asyncio
    async def test_load_schedules_empty_file(self):
        """load_schedules should return empty list for new store."""
        from core.scheduler.persistence import ScheduleStore

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "schedules.json"
            store = ScheduleStore(persistence_path=path)

            schedules = await store.load_schedules()

            assert schedules == []

    @pytest.mark.asyncio
    async def test_load_schedules_restores_data(self):
        """load_schedules should restore saved schedules."""
        from core.scheduler.persistence import ScheduleStore
        from core.scheduler.tasks import Task, ScheduledTask

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "schedules.json"
            store = ScheduleStore(persistence_path=path)

            # Save a schedule
            task = Task(
                name="persistent_task",
                handler=lambda: "result",
                kwargs={"x": 42},
            )
            scheduled = ScheduledTask(
                task=task,
                run_at=datetime(2026, 1, 15, 10, 0, 0),
                recurring=True,
                interval_seconds=3600,
            )
            await store.save_schedule(scheduled)

            # Create new store and load
            store2 = ScheduleStore(persistence_path=path)
            loaded = await store2.load_schedules()

            assert len(loaded) == 1
            assert loaded[0].task.name == "persistent_task"
            assert loaded[0].recurring is True
            assert loaded[0].interval_seconds == 3600

    @pytest.mark.asyncio
    async def test_load_schedules_skips_past_one_time_tasks(self):
        """load_schedules should skip expired one-time tasks."""
        from core.scheduler.persistence import ScheduleStore
        from core.scheduler.tasks import Task, ScheduledTask

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "schedules.json"
            store = ScheduleStore(persistence_path=path)

            # Save an expired one-time task
            task = Task(name="expired_task", handler=lambda: None)
            scheduled = ScheduledTask(
                task=task,
                run_at=datetime.utcnow() - timedelta(hours=1),  # In the past
                recurring=False,
            )
            await store.save_schedule(scheduled)

            # Load should filter it out
            loaded = await store.load_schedules()
            assert len(loaded) == 0

    @pytest.mark.asyncio
    async def test_load_schedules_keeps_recurring_tasks(self):
        """load_schedules should keep recurring tasks even if past due."""
        from core.scheduler.persistence import ScheduleStore
        from core.scheduler.tasks import Task, ScheduledTask

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "schedules.json"
            store = ScheduleStore(persistence_path=path)

            # Save a past-due recurring task
            task = Task(name="recurring_task", handler=lambda: None)
            scheduled = ScheduledTask(
                task=task,
                run_at=datetime.utcnow() - timedelta(hours=1),
                recurring=True,
                interval_seconds=3600,
            )
            await store.save_schedule(scheduled)

            loaded = await store.load_schedules()
            assert len(loaded) == 1  # Should still be there

    @pytest.mark.asyncio
    async def test_delete_schedule(self):
        """delete_schedule should remove a schedule."""
        from core.scheduler.persistence import ScheduleStore
        from core.scheduler.tasks import Task, ScheduledTask

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "schedules.json"
            store = ScheduleStore(persistence_path=path)

            task = Task(name="to_delete", handler=lambda: None)
            scheduled = ScheduledTask(
                task=task,
                run_at=datetime.utcnow() + timedelta(hours=1),
            )
            await store.save_schedule(scheduled)

            # Delete
            result = await store.delete_schedule(scheduled.id)
            assert result is True

            loaded = await store.load_schedules()
            assert len(loaded) == 0

    @pytest.mark.asyncio
    async def test_delete_nonexistent_schedule(self):
        """delete_schedule should return False for unknown ID."""
        from core.scheduler.persistence import ScheduleStore

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "schedules.json"
            store = ScheduleStore(persistence_path=path)

            result = await store.delete_schedule("nonexistent-id")
            assert result is False

    @pytest.mark.asyncio
    async def test_update_schedule(self):
        """update_schedule should modify existing schedule."""
        from core.scheduler.persistence import ScheduleStore
        from core.scheduler.tasks import Task, ScheduledTask

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "schedules.json"
            store = ScheduleStore(persistence_path=path)

            task = Task(name="to_update", handler=lambda: None)
            scheduled = ScheduledTask(
                task=task,
                run_at=datetime.utcnow() + timedelta(hours=1),
                enabled=True,
            )
            await store.save_schedule(scheduled)

            # Update
            scheduled.enabled = False
            scheduled.run_count = 5
            await store.update_schedule(scheduled)

            loaded = await store.load_schedules()
            # Note: disabled tasks might be filtered, so check raw data
            with open(path) as f:
                data = json.load(f)
            assert data["schedules"][0]["enabled"] is False
            assert data["schedules"][0]["run_count"] == 5

    @pytest.mark.asyncio
    async def test_persistence_survives_restart(self):
        """Schedules should persist across store instances."""
        from core.scheduler.persistence import ScheduleStore
        from core.scheduler.tasks import Task, ScheduledTask

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "schedules.json"

            # First instance - save
            store1 = ScheduleStore(persistence_path=path)
            task = Task(name="restart_test", handler=lambda: None)
            scheduled = ScheduledTask(
                task=task,
                run_at=datetime.utcnow() + timedelta(days=1),
                recurring=True,
                cron_expression="0 9 * * *",
            )
            await store1.save_schedule(scheduled)
            del store1

            # Second instance - load
            store2 = ScheduleStore(persistence_path=path)
            loaded = await store2.load_schedules()

            assert len(loaded) == 1
            assert loaded[0].cron_expression == "0 9 * * *"

    @pytest.mark.asyncio
    async def test_corrupted_file_handling(self):
        """load_schedules should handle corrupted files gracefully."""
        from core.scheduler.persistence import ScheduleStore

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "schedules.json"

            # Write corrupted data
            with open(path, "w") as f:
                f.write("{ invalid json")

            store = ScheduleStore(persistence_path=path)

            # Should not raise, return empty
            schedules = await store.load_schedules()
            assert schedules == []

    @pytest.mark.asyncio
    async def test_save_creates_parent_directories(self):
        """save_schedule should create parent directories."""
        from core.scheduler.persistence import ScheduleStore
        from core.scheduler.tasks import Task, ScheduledTask

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "deep" / "nested" / "schedules.json"
            store = ScheduleStore(persistence_path=path)

            task = Task(name="nested_task", handler=lambda: None)
            scheduled = ScheduledTask(
                task=task,
                run_at=datetime.utcnow() + timedelta(hours=1),
            )

            await store.save_schedule(scheduled)

            assert path.exists()

    @pytest.mark.asyncio
    async def test_get_schedule_by_id(self):
        """get_schedule should retrieve by ID."""
        from core.scheduler.persistence import ScheduleStore
        from core.scheduler.tasks import Task, ScheduledTask

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "schedules.json"
            store = ScheduleStore(persistence_path=path)

            task = Task(name="findable_task", handler=lambda: None)
            scheduled = ScheduledTask(
                task=task,
                run_at=datetime.utcnow() + timedelta(hours=1),
            )
            await store.save_schedule(scheduled)

            found = await store.get_schedule(scheduled.id)
            assert found is not None
            assert found.task.name == "findable_task"

    @pytest.mark.asyncio
    async def test_get_schedule_not_found(self):
        """get_schedule should return None for unknown ID."""
        from core.scheduler.persistence import ScheduleStore

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "schedules.json"
            store = ScheduleStore(persistence_path=path)

            found = await store.get_schedule("unknown-id")
            assert found is None

    @pytest.mark.asyncio
    async def test_clear_all_schedules(self):
        """clear_all should remove all schedules."""
        from core.scheduler.persistence import ScheduleStore
        from core.scheduler.tasks import Task, ScheduledTask

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "schedules.json"
            store = ScheduleStore(persistence_path=path)

            # Add several schedules
            for i in range(5):
                task = Task(name=f"task_{i}", handler=lambda: None)
                scheduled = ScheduledTask(
                    task=task,
                    run_at=datetime.utcnow() + timedelta(hours=i+1),
                )
                await store.save_schedule(scheduled)

            # Clear all
            await store.clear_all()

            loaded = await store.load_schedules()
            assert len(loaded) == 0


class TestScheduleStoreSerialization:
    """Tests for schedule serialization/deserialization."""

    @pytest.mark.asyncio
    async def test_serialize_datetime(self):
        """Datetime should be serialized as ISO string."""
        from core.scheduler.persistence import ScheduleStore
        from core.scheduler.tasks import Task, ScheduledTask

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "schedules.json"
            store = ScheduleStore(persistence_path=path)

            run_at = datetime(2026, 6, 15, 9, 30, 0)
            task = Task(name="datetime_task", handler=lambda: None)
            scheduled = ScheduledTask(task=task, run_at=run_at)

            await store.save_schedule(scheduled)

            with open(path) as f:
                data = json.load(f)

            assert data["schedules"][0]["run_at"] == "2026-06-15T09:30:00"

    @pytest.mark.asyncio
    async def test_deserialize_datetime(self):
        """ISO datetime string should be deserialized correctly."""
        from core.scheduler.persistence import ScheduleStore
        from core.scheduler.tasks import Task, ScheduledTask

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "schedules.json"
            store = ScheduleStore(persistence_path=path)

            run_at = datetime(2026, 6, 15, 9, 30, 0)
            task = Task(name="datetime_task", handler=lambda: None)
            scheduled = ScheduledTask(task=task, run_at=run_at)

            await store.save_schedule(scheduled)
            loaded = await store.load_schedules()

            assert loaded[0].run_at == run_at

    @pytest.mark.asyncio
    async def test_handler_not_serialized(self):
        """Handler functions should not be serialized."""
        from core.scheduler.persistence import ScheduleStore
        from core.scheduler.tasks import Task, ScheduledTask

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "schedules.json"
            store = ScheduleStore(persistence_path=path)

            def my_handler():
                return "result"

            task = Task(name="handler_task", handler=my_handler)
            scheduled = ScheduledTask(
                task=task,
                run_at=datetime.utcnow() + timedelta(hours=1),
            )

            await store.save_schedule(scheduled)

            with open(path) as f:
                data = json.load(f)

            # Handler should be stored as reference, not function
            task_data = data["schedules"][0]["task"]
            assert "handler" in task_data
            # Could be handler name or module.function path
            assert isinstance(task_data["handler"], str)


class TestScheduleStoreMetadata:
    """Tests for persistence metadata."""

    @pytest.mark.asyncio
    async def test_saved_at_timestamp(self):
        """Persistence file should include saved_at timestamp."""
        from core.scheduler.persistence import ScheduleStore
        from core.scheduler.tasks import Task, ScheduledTask

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "schedules.json"
            store = ScheduleStore(persistence_path=path)

            task = Task(name="timestamped", handler=lambda: None)
            scheduled = ScheduledTask(
                task=task,
                run_at=datetime.utcnow() + timedelta(hours=1),
            )

            before = datetime.utcnow()
            await store.save_schedule(scheduled)
            after = datetime.utcnow()

            with open(path) as f:
                data = json.load(f)

            saved_at = datetime.fromisoformat(data["saved_at"])
            assert before <= saved_at <= after

    @pytest.mark.asyncio
    async def test_version_in_persistence(self):
        """Persistence file should include version for migrations."""
        from core.scheduler.persistence import ScheduleStore
        from core.scheduler.tasks import Task, ScheduledTask

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "schedules.json"
            store = ScheduleStore(persistence_path=path)

            task = Task(name="versioned", handler=lambda: None)
            scheduled = ScheduledTask(
                task=task,
                run_at=datetime.utcnow() + timedelta(hours=1),
            )
            await store.save_schedule(scheduled)

            with open(path) as f:
                data = json.load(f)

            assert "version" in data
            assert isinstance(data["version"], (int, str))
