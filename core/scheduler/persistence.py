"""
Schedule persistence for surviving restarts.

Provides:
- ScheduleStore: Persist and load scheduled tasks
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.scheduler.tasks import ScheduledTask, Task, ScheduleStatus

logger = logging.getLogger(__name__)

# Version for schema migrations
PERSISTENCE_VERSION = 1

# Default persistence path
DEFAULT_PERSISTENCE_PATH = Path.home() / ".lifeos" / "scheduler" / "schedules.json"


class ScheduleStore:
    """
    Persistent storage for scheduled tasks.

    Saves schedules to JSON file and restores them on restart.
    Handlers are stored by reference (module.function path).
    """

    def __init__(self, persistence_path: Optional[Path] = None):
        """
        Initialize the schedule store.

        Args:
            persistence_path: Path to persistence file (default: ~/.lifeos/scheduler/schedules.json)
        """
        self.persistence_path = persistence_path or DEFAULT_PERSISTENCE_PATH
        self._schedules: Dict[str, ScheduledTask] = {}
        self._handler_registry: Dict[str, Any] = {}

    def register_handler(self, name: str, handler: Any) -> None:
        """
        Register a handler for restoration.

        Args:
            name: Handler name (module.function format)
            handler: The actual handler function
        """
        self._handler_registry[name] = handler

    async def save_schedule(self, scheduled_task: ScheduledTask) -> None:
        """
        Save a scheduled task to persistence.

        Args:
            scheduled_task: The task to save
        """
        self._schedules[scheduled_task.id] = scheduled_task
        await self._write_to_file()

    async def update_schedule(self, scheduled_task: ScheduledTask) -> None:
        """
        Update an existing scheduled task.

        Args:
            scheduled_task: The task to update
        """
        if scheduled_task.id in self._schedules:
            self._schedules[scheduled_task.id] = scheduled_task
            await self._write_to_file()

    async def delete_schedule(self, schedule_id: str) -> bool:
        """
        Delete a scheduled task.

        Args:
            schedule_id: ID of the schedule to delete

        Returns:
            True if deleted, False if not found
        """
        if schedule_id in self._schedules:
            del self._schedules[schedule_id]
            await self._write_to_file()
            return True
        return False

    async def get_schedule(self, schedule_id: str) -> Optional[ScheduledTask]:
        """
        Get a scheduled task by ID.

        Args:
            schedule_id: ID of the schedule

        Returns:
            ScheduledTask or None if not found
        """
        return self._schedules.get(schedule_id)

    async def load_schedules(self) -> List[ScheduledTask]:
        """
        Load schedules from persistence file.

        Filters out:
        - Expired one-time tasks
        - Disabled tasks (optionally)

        Returns:
            List of valid ScheduledTask objects
        """
        if not self.persistence_path.exists():
            return []

        try:
            with open(self.persistence_path, "r") as f:
                data = json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            logger.error(f"Failed to load schedules from {self.persistence_path}: {e}")
            return []

        schedules_data = data.get("schedules", [])
        now = datetime.utcnow()
        valid_schedules = []

        for item in schedules_data:
            try:
                scheduled = self._deserialize_schedule(item)

                # Skip expired one-time tasks
                if not scheduled.recurring and scheduled.run_at and scheduled.run_at < now:
                    logger.debug(f"Skipping expired one-time task: {scheduled.task.name}")
                    continue

                self._schedules[scheduled.id] = scheduled
                valid_schedules.append(scheduled)

            except Exception as e:
                logger.warning(f"Failed to deserialize schedule: {e}")
                continue

        return valid_schedules

    async def clear_all(self) -> None:
        """Remove all schedules."""
        self._schedules.clear()
        await self._write_to_file()

    async def _write_to_file(self) -> None:
        """Write current schedules to persistence file."""
        # Ensure parent directory exists
        self.persistence_path.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "version": PERSISTENCE_VERSION,
            "saved_at": datetime.utcnow().isoformat(),
            "schedules": [
                self._serialize_schedule(s) for s in self._schedules.values()
            ],
        }

        try:
            with open(self.persistence_path, "w") as f:
                json.dump(data, f, indent=2)
        except IOError as e:
            logger.error(f"Failed to save schedules to {self.persistence_path}: {e}")

    def _serialize_schedule(self, scheduled: ScheduledTask) -> Dict[str, Any]:
        """Serialize a ScheduledTask to dict."""
        task_data = {
            "id": scheduled.task.id,
            "name": scheduled.task.name,
            "handler": self._get_handler_name(scheduled.task.handler),
            "args": list(scheduled.task.args),
            "kwargs": scheduled.task.kwargs,
            "timeout": scheduled.task.timeout,
            "retry_count": scheduled.task.retry_count,
            "retry_delay": scheduled.task.retry_delay,
            "tags": scheduled.task.tags,
            "metadata": scheduled.task.metadata,
            "created_at": scheduled.task.created_at.isoformat(),
        }

        return {
            "id": scheduled.id,
            "task": task_data,
            "run_at": scheduled.run_at.isoformat() if scheduled.run_at else None,
            "recurring": scheduled.recurring,
            "interval_seconds": scheduled.interval_seconds,
            "cron_expression": scheduled.cron_expression,
            "enabled": scheduled.enabled,
            "status": scheduled.status.value,
            "run_count": scheduled.run_count,
            "max_runs": scheduled.max_runs,
            "last_run": scheduled.last_run.isoformat() if scheduled.last_run else None,
            "created_at": scheduled.created_at.isoformat(),
        }

    def _deserialize_schedule(self, data: Dict[str, Any]) -> ScheduledTask:
        """Deserialize a ScheduledTask from dict."""
        task_data = data["task"]

        # Get handler from registry or create placeholder
        handler_name = task_data.get("handler", "")
        handler = self._handler_registry.get(handler_name)

        if handler is None:
            # Create a placeholder handler that logs a warning
            def placeholder_handler(*args, **kwargs):
                logger.warning(f"Handler '{handler_name}' not registered")
                return None
            handler = placeholder_handler

        task = Task(
            id=task_data.get("id"),
            name=task_data["name"],
            handler=handler,
            args=tuple(task_data.get("args", [])),
            kwargs=task_data.get("kwargs", {}),
            timeout=task_data.get("timeout", 300.0),
            retry_count=task_data.get("retry_count", 0),
            retry_delay=task_data.get("retry_delay", 1.0),
            tags=task_data.get("tags", []),
            metadata=task_data.get("metadata", {}),
            created_at=datetime.fromisoformat(task_data["created_at"]) if task_data.get("created_at") else datetime.utcnow(),
        )

        run_at = None
        if data.get("run_at"):
            run_at = datetime.fromisoformat(data["run_at"])

        last_run = None
        if data.get("last_run"):
            last_run = datetime.fromisoformat(data["last_run"])

        return ScheduledTask(
            id=data.get("id"),
            task=task,
            run_at=run_at,
            recurring=data.get("recurring", False),
            interval_seconds=data.get("interval_seconds"),
            cron_expression=data.get("cron_expression"),
            enabled=data.get("enabled", True),
            status=ScheduleStatus(data.get("status", "pending")),
            run_count=data.get("run_count", 0),
            max_runs=data.get("max_runs"),
            last_run=last_run,
            created_at=datetime.fromisoformat(data["created_at"]) if data.get("created_at") else datetime.utcnow(),
        )

    def _get_handler_name(self, handler: Any) -> str:
        """Get a string identifier for a handler function."""
        if hasattr(handler, "__module__") and hasattr(handler, "__name__"):
            return f"{handler.__module__}.{handler.__name__}"
        return str(handler)
