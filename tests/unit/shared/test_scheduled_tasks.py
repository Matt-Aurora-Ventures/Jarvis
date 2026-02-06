"""Tests for the TaskScheduler system."""

import time
import threading
import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone, timedelta

from bots.shared.scheduled_tasks import TaskScheduler, ScheduledTask


class TestScheduledTask:
    """Test ScheduledTask helper."""

    def test_seconds_until_next_future_today(self):
        """If target time is later today, returns positive seconds."""
        now = datetime.now(timezone.utc)
        # Schedule 1 hour from now
        future = now + timedelta(hours=1)
        task = ScheduledTask("test", future.hour, future.minute, lambda: None)
        secs = task.seconds_until_next()
        assert 3500 < secs < 3700  # ~1 hour

    def test_seconds_until_next_past_today(self):
        """If target time already passed today, schedules for tomorrow."""
        now = datetime.now(timezone.utc)
        past = now - timedelta(hours=1)
        task = ScheduledTask("test", past.hour, past.minute, lambda: None)
        secs = task.seconds_until_next()
        # Should be ~23 hours
        assert 82000 < secs < 87000


class TestTaskScheduler:
    """Test TaskScheduler."""

    def test_schedule_daily_adds_task(self):
        scheduler = TaskScheduler()
        scheduler.schedule_daily(8, 0, lambda: None, name="test")
        assert len(scheduler.tasks) == 1
        assert scheduler.tasks[0].name == "test"
        assert scheduler.tasks[0].hour == 8
        assert scheduler.tasks[0].minute == 0

    def test_start_sets_running(self):
        scheduler = TaskScheduler()
        cb = MagicMock()
        scheduler.schedule_daily(8, 0, cb, name="test")
        scheduler.start()
        assert scheduler._running is True
        # Timer should be set
        assert scheduler.tasks[0].timer is not None
        scheduler.stop()

    def test_stop_cancels_timers(self):
        scheduler = TaskScheduler()
        scheduler.schedule_daily(8, 0, lambda: None, name="test")
        scheduler.start()
        timer = scheduler.tasks[0].timer
        scheduler.stop()
        assert scheduler._running is False
        # Timer was cancelled (it won't fire), give it a moment to clean up
        timer.join(timeout=1.0)
        assert not timer.is_alive()

    def test_multiple_tasks(self):
        scheduler = TaskScheduler()
        scheduler.schedule_daily(8, 0, lambda: None, name="morning")
        scheduler.schedule_daily(20, 0, lambda: None, name="evening")
        assert len(scheduler.tasks) == 2
        scheduler.start()
        scheduler.stop()

    def test_run_task_calls_callback(self):
        """Test that _run_task executes the callback."""
        scheduler = TaskScheduler()
        cb = MagicMock()
        task = ScheduledTask("test", 8, 0, cb)
        scheduler._running = False  # Prevent rescheduling
        scheduler._run_task(task)
        cb.assert_called_once()

    def test_run_task_handles_async_callback(self):
        """Test that _run_task handles coroutine callbacks."""
        import asyncio

        async def async_cb():
            return "done"

        scheduler = TaskScheduler()
        task = ScheduledTask("test", 8, 0, async_cb)
        scheduler._running = False
        # Should not raise
        scheduler._run_task(task)

    def test_run_task_handles_exception(self):
        """Test that _run_task catches exceptions gracefully."""
        scheduler = TaskScheduler()

        def bad_cb():
            raise ValueError("boom")

        task = ScheduledTask("test", 8, 0, bad_cb)
        scheduler._running = False
        # Should not raise
        scheduler._run_task(task)
