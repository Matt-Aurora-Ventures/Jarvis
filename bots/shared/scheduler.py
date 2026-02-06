"""
ClawdBot Task Scheduler - Simple task scheduling for bots.

Features:
- One-time and recurring task scheduling
- Cron-like scheduling expressions
- Persistence across restarts
- Missed task handling (runs immediately)
- Task status and history tracking

Storage Paths (VPS):
- Tasks: /root/clawdbots/scheduled_tasks.json
- History: /root/clawdbots/task_history.json
"""

import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Union

logger = logging.getLogger(__name__)

# Default paths for VPS deployment
DEFAULT_TASKS_PATH = Path("/root/clawdbots/scheduled_tasks.json")
DEFAULT_HISTORY_PATH = Path("/root/clawdbots/task_history.json")


@dataclass
class ScheduledTask:
    """
    A scheduled task definition.

    Attributes:
        id: Unique task identifier
        name: Human-readable task name
        function_name: Name of the registered function to call
        args: Arguments to pass to the function
        scheduled_time: When the task should run
        recurring: Whether the task repeats
        cron: Cron expression for recurring tasks
        status: Current status (pending, running, completed, failed)
    """

    id: str
    name: str
    function_name: str
    scheduled_time: datetime
    args: Dict[str, Any] = field(default_factory=dict)
    recurring: bool = False
    cron: Optional[str] = None
    status: str = "pending"

    def to_dict(self) -> Dict[str, Any]:
        """Serialize task to dictionary for JSON storage."""
        return {
            "id": self.id,
            "name": self.name,
            "function_name": self.function_name,
            "args": self.args,
            "scheduled_time": self.scheduled_time.isoformat(),
            "recurring": self.recurring,
            "cron": self.cron,
            "status": self.status,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ScheduledTask":
        """Deserialize task from dictionary."""
        scheduled_time = data.get("scheduled_time")
        if isinstance(scheduled_time, str):
            scheduled_time = datetime.fromisoformat(scheduled_time)

        return cls(
            id=data["id"],
            name=data.get("name", data["function_name"]),
            function_name=data["function_name"],
            args=data.get("args", {}),
            scheduled_time=scheduled_time,
            recurring=data.get("recurring", False),
            cron=data.get("cron"),
            status=data.get("status", "pending"),
        )


@dataclass
class TaskHistory:
    """
    Record of a task execution.

    Attributes:
        task_id: ID of the executed task
        task_name: Name of the executed task
        executed_at: When the task was executed
        success: Whether execution succeeded
        result: Return value if successful
        error: Error message if failed
        duration_ms: Execution time in milliseconds
    """

    task_id: str
    task_name: str
    executed_at: datetime
    success: bool = False
    result: Any = None
    error: Optional[str] = None
    duration_ms: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Serialize history to dictionary for JSON storage."""
        # Safely serialize result (may not be JSON serializable)
        try:
            result = self.result
            # Test if it's JSON serializable
            json.dumps(result)
        except (TypeError, ValueError):
            result = str(self.result) if self.result is not None else None

        return {
            "task_id": self.task_id,
            "task_name": self.task_name,
            "executed_at": self.executed_at.isoformat(),
            "success": self.success,
            "result": result,
            "error": self.error,
            "duration_ms": self.duration_ms,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TaskHistory":
        """Deserialize history from dictionary."""
        executed_at = data.get("executed_at")
        if isinstance(executed_at, str):
            executed_at = datetime.fromisoformat(executed_at)

        return cls(
            task_id=data["task_id"],
            task_name=data.get("task_name", ""),
            executed_at=executed_at,
            success=data.get("success", False),
            result=data.get("result"),
            error=data.get("error"),
            duration_ms=data.get("duration_ms", 0.0),
        )


class CronParser:
    """
    Simple cron expression parser.

    Format: minute hour day_of_month month day_of_week
    Supports: *, specific values, ranges (1-5), lists (1,3,5), steps (*/5)
    """

    @staticmethod
    def parse(expression: str) -> Dict[str, List[int]]:
        """Parse cron expression into field values."""
        parts = expression.strip().split()
        if len(parts) != 5:
            raise ValueError(f"Invalid cron expression: {expression}")

        fields = ["minute", "hour", "day", "month", "weekday"]
        ranges = [
            (0, 59),  # minute
            (0, 23),  # hour
            (1, 31),  # day
            (1, 12),  # month
            (0, 6),   # weekday (0=Sunday)
        ]

        result = {}
        for i, (part, field_name, (min_val, max_val)) in enumerate(
            zip(parts, fields, ranges)
        ):
            result[field_name] = CronParser._parse_field(part, min_val, max_val)

        return result

    @staticmethod
    def _parse_field(part: str, min_val: int, max_val: int) -> List[int]:
        """Parse a single cron field."""
        if part == "*":
            return list(range(min_val, max_val + 1))

        values = set()

        for segment in part.split(","):
            if "/" in segment:
                # Step value
                base, step = segment.split("/")
                step = int(step)
                if base == "*":
                    start = min_val
                else:
                    start = int(base)
                values.update(range(start, max_val + 1, step))
            elif "-" in segment:
                # Range
                start, end = segment.split("-")
                values.update(range(int(start), int(end) + 1))
            else:
                # Single value
                values.add(int(segment))

        return sorted(v for v in values if min_val <= v <= max_val)

    @staticmethod
    def next_run(expression: str, from_time: Optional[datetime] = None) -> datetime:
        """Calculate next run time from cron expression."""
        if from_time is None:
            from_time = datetime.utcnow()

        parsed = CronParser.parse(expression)

        # Start from the next minute
        candidate = from_time.replace(second=0, microsecond=0) + timedelta(minutes=1)

        # Find next valid time (limit iterations to prevent infinite loop)
        for _ in range(366 * 24 * 60):  # Max 1 year of minutes
            if (
                candidate.minute in parsed["minute"]
                and candidate.hour in parsed["hour"]
                and candidate.day in parsed["day"]
                and candidate.month in parsed["month"]
                and candidate.weekday() in parsed["weekday"]
            ):
                return candidate
            candidate += timedelta(minutes=1)

        raise ValueError(f"Could not find next run time for: {expression}")


class ClawdBotScheduler:
    """
    Simple task scheduler for ClawdBots.

    Usage:
        scheduler = ClawdBotScheduler()

        # Register callable functions
        scheduler.register_function("my_task", my_task_function)

        # Schedule a one-time task
        scheduler.schedule_task(
            task_id="backup-001",
            func="my_task",
            when=datetime.utcnow() + timedelta(hours=1),
        )

        # Schedule a recurring task with cron
        scheduler.schedule_task(
            task_id="hourly-check",
            func="health_check",
            when=None,
            recurring=True,
            cron="0 * * * *",
        )

        # Run due tasks (call this periodically, e.g., every minute)
        scheduler.run_due_tasks()
    """

    def __init__(
        self,
        tasks_path: Optional[Path] = None,
        history_path: Optional[Path] = None,
    ):
        """
        Initialize the scheduler.

        Args:
            tasks_path: Path to scheduled tasks JSON file
            history_path: Path to task history JSON file
        """
        self.tasks_path = tasks_path or DEFAULT_TASKS_PATH
        self.history_path = history_path or DEFAULT_HISTORY_PATH
        self._tasks: Dict[str, ScheduledTask] = {}
        self._history: List[TaskHistory] = []
        self._functions: Dict[str, Callable] = {}
        self._max_history = 1000

        # Load existing state
        self._load_tasks()
        self._load_history()

    def _load_tasks(self) -> None:
        """Load tasks from persistence file."""
        if not self.tasks_path.exists():
            return

        try:
            data = json.loads(self.tasks_path.read_text())
            for task_data in data:
                task = ScheduledTask.from_dict(task_data)
                self._tasks[task.id] = task
            logger.info(f"Loaded {len(self._tasks)} tasks from {self.tasks_path}")
        except (json.JSONDecodeError, KeyError) as e:
            logger.warning(f"Failed to load tasks: {e}")
            self._tasks = {}

    def _load_history(self) -> None:
        """Load history from persistence file."""
        if not self.history_path.exists():
            return

        try:
            data = json.loads(self.history_path.read_text())
            for history_data in data:
                history = TaskHistory.from_dict(history_data)
                self._history.append(history)
            logger.info(f"Loaded {len(self._history)} history entries")
        except (json.JSONDecodeError, KeyError) as e:
            logger.warning(f"Failed to load history: {e}")
            self._history = []

    def _save_tasks(self) -> None:
        """Save tasks to persistence file."""
        try:
            self.tasks_path.parent.mkdir(parents=True, exist_ok=True)
            data = [task.to_dict() for task in self._tasks.values()]
            self.tasks_path.write_text(json.dumps(data, indent=2))
        except Exception as e:
            logger.error(f"Failed to save tasks: {e}")

    def _save_history(self) -> None:
        """Save history to persistence file."""
        try:
            self.history_path.parent.mkdir(parents=True, exist_ok=True)
            data = [h.to_dict() for h in self._history]
            self.history_path.write_text(json.dumps(data, indent=2))
        except Exception as e:
            logger.error(f"Failed to save history: {e}")

    def register_function(self, name: str, func: Callable) -> None:
        """
        Register a callable function that can be scheduled.

        Args:
            name: Name to reference the function by
            func: Callable to execute
        """
        self._functions[name] = func
        logger.debug(f"Registered function: {name}")

    def get_function(self, name: str) -> Optional[Callable]:
        """
        Get a registered function by name.

        Args:
            name: Name of the function

        Returns:
            The callable or None if not registered
        """
        return self._functions.get(name)

    def schedule_task(
        self,
        task_id: Optional[str],
        func: str,
        when: Optional[datetime],
        recurring: bool = False,
        cron: Optional[str] = None,
        args: Optional[Dict[str, Any]] = None,
        name: Optional[str] = None,
    ) -> str:
        """
        Schedule a task for execution.

        Args:
            task_id: Unique task ID (auto-generated if None)
            func: Name of the registered function to call
            when: When to run (None if using cron)
            recurring: Whether task repeats
            cron: Cron expression for recurring tasks
            args: Arguments to pass to the function
            name: Human-readable name for the task

        Returns:
            The task ID
        """
        if task_id is None:
            task_id = str(uuid.uuid4())[:12]

        # Calculate scheduled time
        if when is None and cron:
            scheduled_time = CronParser.next_run(cron)
        elif when is None:
            scheduled_time = datetime.utcnow()
        else:
            scheduled_time = when

        task = ScheduledTask(
            id=task_id,
            name=name or func,
            function_name=func,
            args=args or {},
            scheduled_time=scheduled_time,
            recurring=recurring,
            cron=cron,
            status="pending",
        )

        self._tasks[task_id] = task
        self._save_tasks()

        logger.info(
            f"Scheduled task '{task.name}' ({task_id}) for {scheduled_time}"
        )
        return task_id

    def cancel_task(self, task_id: str) -> bool:
        """
        Cancel a scheduled task.

        Args:
            task_id: ID of the task to cancel

        Returns:
            True if task was cancelled, False if not found
        """
        if task_id not in self._tasks:
            return False

        del self._tasks[task_id]
        self._save_tasks()

        logger.info(f"Cancelled task {task_id}")
        return True

    def get_scheduled_tasks(self) -> List[ScheduledTask]:
        """
        Get all pending scheduled tasks.

        Returns:
            List of pending tasks sorted by scheduled time
        """
        pending = [t for t in self._tasks.values() if t.status == "pending"]
        return sorted(pending, key=lambda t: t.scheduled_time)

    def get_task_history(self, limit: int = 50) -> List[TaskHistory]:
        """
        Get recent task execution history.

        Args:
            limit: Maximum number of entries to return

        Returns:
            List of recent history entries (most recent last)
        """
        return self._history[-limit:]

    def run_due_tasks(self) -> List[TaskHistory]:
        """
        Execute all tasks that are due.

        Returns:
            List of execution results
        """
        now = datetime.utcnow()
        results = []

        # Find due tasks
        due_tasks = [
            task
            for task in self._tasks.values()
            if task.status == "pending" and task.scheduled_time <= now
        ]

        for task in due_tasks:
            result = self._execute_task(task)
            results.append(result)

        return results

    def _execute_task(self, task: ScheduledTask) -> TaskHistory:
        """Execute a single task and record the result."""
        start_time = datetime.utcnow()
        history = TaskHistory(
            task_id=task.id,
            task_name=task.name,
            executed_at=start_time,
        )

        task.status = "running"

        try:
            # Get the registered function
            func = self.get_function(task.function_name)
            if func is None:
                raise ValueError(
                    f"Function '{task.function_name}' is not registered"
                )

            # Execute the function
            result = func(**task.args)

            history.success = True
            history.result = result
            task.status = "completed"

            logger.info(f"Task '{task.name}' completed successfully")

        except Exception as e:
            history.success = False
            history.error = str(e)
            task.status = "failed"

            logger.error(f"Task '{task.name}' failed: {e}")

        finally:
            end_time = datetime.utcnow()
            history.duration_ms = (end_time - start_time).total_seconds() * 1000

            # Record history
            self._history.append(history)
            if len(self._history) > self._max_history:
                self._history = self._history[-self._max_history:]
            self._save_history()

            # Handle recurring vs one-time tasks
            if task.recurring and task.cron:
                # Reschedule recurring task
                task.scheduled_time = CronParser.next_run(task.cron)
                task.status = "pending"
                logger.info(
                    f"Rescheduled recurring task '{task.name}' for {task.scheduled_time}"
                )
            else:
                # Remove one-time task
                if task.id in self._tasks:
                    del self._tasks[task.id]

            self._save_tasks()

        return history


# Module-level convenience functions
_scheduler: Optional[ClawdBotScheduler] = None


def get_scheduler(
    tasks_path: Optional[Path] = None,
    history_path: Optional[Path] = None,
) -> ClawdBotScheduler:
    """Get or create the global scheduler instance."""
    global _scheduler
    if _scheduler is None:
        _scheduler = ClawdBotScheduler(
            tasks_path=tasks_path,
            history_path=history_path,
        )
    return _scheduler


def schedule_task(
    task_id: Optional[str],
    func: Union[str, Callable],
    when: Optional[datetime],
    recurring: bool = False,
    cron: Optional[str] = None,
    args: Optional[Dict[str, Any]] = None,
    name: Optional[str] = None,
) -> str:
    """Convenience function to schedule a task using the global scheduler."""
    scheduler = get_scheduler()

    # If func is a callable, register it
    if callable(func):
        func_name = func.__name__
        scheduler.register_function(func_name, func)
    else:
        func_name = func

    return scheduler.schedule_task(
        task_id=task_id,
        func=func_name,
        when=when,
        recurring=recurring,
        cron=cron,
        args=args,
        name=name,
    )


def cancel_task(task_id: str) -> bool:
    """Convenience function to cancel a task using the global scheduler."""
    return get_scheduler().cancel_task(task_id)


def get_scheduled_tasks() -> List[ScheduledTask]:
    """Convenience function to get scheduled tasks using the global scheduler."""
    return get_scheduler().get_scheduled_tasks()


def get_task_history(limit: int = 50) -> List[TaskHistory]:
    """Convenience function to get task history using the global scheduler."""
    return get_scheduler().get_task_history(limit=limit)


def run_due_tasks() -> List[TaskHistory]:
    """Convenience function to run due tasks using the global scheduler."""
    return get_scheduler().run_due_tasks()
