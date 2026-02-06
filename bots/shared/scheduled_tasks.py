"""
Lightweight task scheduler for ClawdBots.

Uses threading.Timer for recurring tasks. No external dependencies.
"""

import logging
import threading
from datetime import datetime, timezone, timedelta
from typing import Callable, List, Optional

logger = logging.getLogger(__name__)

class ScheduledTask:
    def __init__(self, name: str, hour: int, minute: int, callback: Callable):
        self.name = name
        self.hour = hour
        self.minute = minute
        self.callback = callback
        self.timer: Optional[threading.Timer] = None

    def seconds_until_next(self) -> float:
        now = datetime.now(timezone.utc)
        target = now.replace(hour=self.hour, minute=self.minute, second=0, microsecond=0)
        if target <= now:
            target += timedelta(days=1)
        return (target - now).total_seconds()

class TaskScheduler:
    """Simple daily task scheduler using threading.Timer."""

    def __init__(self):
        self.tasks: List[ScheduledTask] = []
        self._running = False

    def schedule_daily(self, hour: int, minute: int, callback: Callable, name: str = "task"):
        self.tasks.append(ScheduledTask(name, hour, minute, callback))

    def start(self):
        self._running = True
        for task in self.tasks:
            self._schedule_next(task)
        logger.info(f"Scheduler started with {len(self.tasks)} tasks")

    def _schedule_next(self, task: ScheduledTask):
        if not self._running:
            return
        delay = task.seconds_until_next()
        logger.info(f"Scheduling '{task.name}' in {delay:.0f}s")
        task.timer = threading.Timer(delay, self._run_task, args=[task])
        task.timer.daemon = True
        task.timer.start()

    def _run_task(self, task: ScheduledTask):
        try:
            logger.info(f"Running scheduled task: {task.name}")
            result = task.callback()
            # Handle coroutines
            import asyncio
            if asyncio.iscoroutine(result):
                loop = asyncio.new_event_loop()
                try:
                    loop.run_until_complete(result)
                finally:
                    loop.close()
        except Exception as e:
            logger.error(f"Scheduled task '{task.name}' failed: {e}")
        finally:
            self._schedule_next(task)

    def stop(self):
        self._running = False
        for task in self.tasks:
            if task.timer:
                task.timer.cancel()
        logger.info("Scheduler stopped")
