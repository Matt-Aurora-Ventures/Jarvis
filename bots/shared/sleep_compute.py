"""
Real-Time Sleep-Compute System for ClawdBots.

Enables bots to execute background tasks during idle periods (when no user
messages are being received). Tasks are queued, executed during inactivity,
and paused immediately when user activity resumes.

Task Types:
- research: Gather information on topics
- analysis: Analyze data and trends
- content_prep: Draft social media posts
- maintenance: Cleanup, optimization, housekeeping

Usage:
    from bots.shared.sleep_compute import (
        queue_background_task,
        check_and_execute_idle_tasks,
        pause_background_work,
        get_completed_tasks,
        is_idle_period,
    )

    # Queue a task
    task_id = queue_background_task("research", {"topic": "solana defi"})

    # Check and execute during idle (call this periodically)
    await check_and_execute_idle_tasks()

    # Pause when user becomes active
    pause_background_work()

    # Get completed tasks
    completed = get_completed_tasks()

Author: Kraken Agent
Created: 2026-02-02
"""

import asyncio
import json
import logging
import os
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


# Default file paths for VPS deployment
DEFAULT_QUEUE_FILE = Path("/root/clawdbots/sleep_compute_queue.json")
DEFAULT_DONE_FILE = Path("/root/clawdbots/sleep_compute_done.json")


class TaskType(Enum):
    """Types of background tasks that can be queued."""

    RESEARCH = "research"
    ANALYSIS = "analysis"
    CONTENT_PREP = "content_prep"
    MAINTENANCE = "maintenance"


class TaskStatus(Enum):
    """Status of a background task."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    PAUSED = "paused"
    FAILED = "failed"


class TaskPriority(Enum):
    """Priority levels for task execution order."""

    LOW = 1
    MEDIUM = 2
    HIGH = 3


@dataclass
class BackgroundTask:
    """
    A background task to be executed during idle periods.

    Attributes:
        task_type: Type of task (research, analysis, etc.)
        params: Parameters specific to the task type
        id: Unique identifier for the task
        status: Current status of the task
        priority: Execution priority (higher = sooner)
        created_at: When the task was queued
        started_at: When execution began (if started)
        completed_at: When execution finished (if completed)
        result: Result data from successful execution
        error: Error message if task failed
    """

    task_type: TaskType
    params: dict[str, Any]
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    status: TaskStatus = TaskStatus.PENDING
    priority: TaskPriority = TaskPriority.MEDIUM
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    result: Optional[dict[str, Any]] = None
    error: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize task to dictionary for JSON storage."""
        return {
            "id": self.id,
            "task_type": self.task_type.value,
            "params": self.params,
            "status": self.status.value,
            "priority": self.priority.value,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "result": self.result,
            "error": self.error,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "BackgroundTask":
        """Deserialize task from dictionary."""
        return cls(
            id=data["id"],
            task_type=TaskType(data["task_type"]),
            params=data["params"],
            status=TaskStatus(data["status"]),
            priority=TaskPriority(data["priority"]),
            created_at=datetime.fromisoformat(data["created_at"]),
            started_at=datetime.fromisoformat(data["started_at"]) if data.get("started_at") else None,
            completed_at=datetime.fromisoformat(data["completed_at"]) if data.get("completed_at") else None,
            result=data.get("result"),
            error=data.get("error"),
        )


class SleepComputeManager:
    """
    Manages background task queue and idle-time execution.

    The manager tracks user activity, maintains a task queue, and executes
    tasks during idle periods. Tasks are automatically paused when user
    activity resumes.

    Attributes:
        queue_file: Path to persist pending tasks
        done_file: Path to persist completed tasks
        idle_threshold_minutes: Minutes of inactivity before considered idle
    """

    def __init__(
        self,
        queue_file: Optional[Path] = None,
        done_file: Optional[Path] = None,
        idle_threshold_minutes: int = 5,
        task_executors: Optional[dict[TaskType, Callable]] = None,
    ):
        """
        Initialize the sleep-compute manager.

        Args:
            queue_file: Path to queue JSON file (default: /root/clawdbots/sleep_compute_queue.json)
            done_file: Path to completed tasks JSON file
            idle_threshold_minutes: Minutes of inactivity to consider idle
            task_executors: Optional dict mapping TaskType to executor functions
        """
        self.queue_file = queue_file or DEFAULT_QUEUE_FILE
        self.done_file = done_file or DEFAULT_DONE_FILE
        self.idle_threshold_minutes = idle_threshold_minutes

        self._queue: list[BackgroundTask] = []
        self._completed: list[BackgroundTask] = []
        self._last_activity: datetime = datetime.now(timezone.utc)
        self._paused: bool = False
        self._current_task: Optional[BackgroundTask] = None

        # Custom executors can be injected
        self._task_executors = task_executors or {}

        # Load existing queue from disk
        self._load_queue()
        self._load_completed()

    def _ensure_parent_dirs(self, file_path: Path) -> None:
        """Ensure parent directories exist for a file."""
        file_path.parent.mkdir(parents=True, exist_ok=True)

    def _load_queue(self) -> None:
        """Load pending tasks from queue file."""
        if not self.queue_file.exists():
            logger.debug(f"Queue file not found: {self.queue_file}")
            return

        try:
            data = json.loads(self.queue_file.read_text(encoding="utf-8"))
            self._queue = [BackgroundTask.from_dict(t) for t in data.get("tasks", [])]
            logger.info(f"Loaded {len(self._queue)} pending tasks from queue")
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logger.warning(f"Failed to load queue file (starting fresh): {e}")
            self._queue = []

    def _load_completed(self) -> None:
        """Load completed tasks from done file."""
        if not self.done_file.exists():
            return

        try:
            data = json.loads(self.done_file.read_text(encoding="utf-8"))
            self._completed = [BackgroundTask.from_dict(t) for t in data.get("tasks", [])]
            logger.debug(f"Loaded {len(self._completed)} completed tasks")
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logger.warning(f"Failed to load done file: {e}")
            self._completed = []

    def _persist_queue(self) -> None:
        """Save pending tasks to queue file."""
        try:
            self._ensure_parent_dirs(self.queue_file)
            data = {"tasks": [t.to_dict() for t in self._queue]}
            self.queue_file.write_text(json.dumps(data, indent=2), encoding="utf-8")
            logger.debug(f"Persisted {len(self._queue)} tasks to queue")
        except Exception as e:
            logger.error(f"Failed to persist queue: {e}")

    def _persist_completed(self) -> None:
        """Save completed tasks to done file."""
        try:
            self._ensure_parent_dirs(self.done_file)
            data = {"tasks": [t.to_dict() for t in self._completed]}
            self.done_file.write_text(json.dumps(data, indent=2), encoding="utf-8")
            logger.debug(f"Persisted {len(self._completed)} completed tasks")
        except Exception as e:
            logger.error(f"Failed to persist completed: {e}")

    def record_user_activity(self) -> None:
        """
        Record that user activity was detected.

        Call this whenever a user message is received to reset the idle timer.
        """
        self._last_activity = datetime.now(timezone.utc)
        logger.debug("User activity recorded")

    def is_idle_period(self) -> bool:
        """
        Check if the system is currently in an idle period.

        Returns:
            True if no user activity for idle_threshold_minutes
        """
        if self._paused:
            return False

        elapsed = datetime.now(timezone.utc) - self._last_activity
        elapsed_minutes = elapsed.total_seconds() / 60
        return elapsed_minutes >= self.idle_threshold_minutes

    def queue_task(
        self,
        task_type: TaskType,
        params: dict[str, Any],
        priority: TaskPriority = TaskPriority.MEDIUM,
    ) -> str:
        """
        Queue a background task for idle-time execution.

        Args:
            task_type: Type of task to execute
            params: Parameters for the task
            priority: Execution priority (default: MEDIUM)

        Returns:
            Task ID for tracking
        """
        task = BackgroundTask(
            task_type=task_type,
            params=params,
            priority=priority,
        )

        self._queue.append(task)
        self._persist_queue()

        logger.info(f"Queued {task_type.value} task {task.id} with priority {priority.value}")
        return task.id

    def _get_sorted_queue(self) -> list[BackgroundTask]:
        """Get queue sorted by priority (highest first) then creation time."""
        return sorted(
            [t for t in self._queue if t.status == TaskStatus.PENDING],
            key=lambda t: (-t.priority.value, t.created_at),
        )

    def pause(self) -> None:
        """Pause background task execution."""
        self._paused = True
        logger.info("Sleep-compute paused")

    def resume(self) -> None:
        """Resume background task execution."""
        self._paused = False
        logger.info("Sleep-compute resumed")

    def get_pending_tasks(self) -> list[dict[str, Any]]:
        """
        Get all pending tasks.

        Returns:
            List of task dictionaries
        """
        return [t.to_dict() for t in self._queue if t.status == TaskStatus.PENDING]

    def get_completed_tasks(self) -> list[dict[str, Any]]:
        """
        Get all completed tasks.

        Returns:
            List of completed task dictionaries
        """
        return [t.to_dict() for t in self._completed]

    async def check_and_execute_idle_tasks(self) -> int:
        """
        Check if idle and execute pending tasks.

        This method should be called periodically (e.g., every minute) to
        process background tasks when the system is idle.

        Returns:
            Number of tasks executed
        """
        if not self.is_idle_period():
            logger.debug("Not idle, skipping task execution")
            return 0

        if self._paused:
            logger.debug("Paused, skipping task execution")
            return 0

        executed = 0
        sorted_queue = self._get_sorted_queue()

        for task in sorted_queue:
            # Check if we should continue
            if self._paused or not self.is_idle_period():
                logger.info("Stopping task execution (no longer idle or paused)")
                break

            try:
                # Mark as in progress
                task.status = TaskStatus.IN_PROGRESS
                task.started_at = datetime.now(timezone.utc)
                self._current_task = task
                self._persist_queue()

                # Execute the task
                logger.info(f"Executing {task.task_type.value} task {task.id}")
                result = await self._execute_task(task)

                # Mark as completed
                task.status = TaskStatus.COMPLETED
                task.completed_at = datetime.now(timezone.utc)
                task.result = result

                # Move to completed list
                self._queue.remove(task)
                self._completed.append(task)
                self._persist_queue()
                self._persist_completed()

                executed += 1
                logger.info(f"Completed task {task.id}")

            except Exception as e:
                logger.error(f"Task {task.id} failed: {e}")
                task.status = TaskStatus.FAILED
                task.error = str(e)
                task.completed_at = datetime.now(timezone.utc)

                # Move failed task to completed (for tracking)
                self._queue.remove(task)
                self._completed.append(task)
                self._persist_queue()
                self._persist_completed()

            finally:
                self._current_task = None

        return executed

    async def _execute_task(self, task: BackgroundTask) -> dict[str, Any]:
        """
        Execute a single background task.

        Routes to the appropriate executor based on task type.

        Args:
            task: The task to execute

        Returns:
            Result dictionary from the executor
        """
        # Check for custom executor first
        if task.task_type in self._task_executors:
            executor = self._task_executors[task.task_type]
            return await executor(task)

        # Use built-in executors
        executors = {
            TaskType.RESEARCH: self._execute_research_task,
            TaskType.ANALYSIS: self._execute_analysis_task,
            TaskType.CONTENT_PREP: self._execute_content_prep_task,
            TaskType.MAINTENANCE: self._execute_maintenance_task,
        }

        executor = executors.get(task.task_type)
        if not executor:
            raise ValueError(f"Unknown task type: {task.task_type}")

        return await executor(task)

    async def _execute_research_task(self, task: BackgroundTask) -> dict[str, Any]:
        """
        Execute a research task.

        Gathers information on the specified topic. In production, this would
        integrate with web search, API calls, or LLM research capabilities.

        Args:
            task: Research task with 'topic' in params

        Returns:
            Dictionary with research findings
        """
        topic = task.params.get("topic", "unknown")
        logger.info(f"Executing research task on: {topic}")

        # Stub implementation - in production, this would:
        # - Call web search APIs
        # - Query knowledge bases
        # - Use LLM to synthesize findings

        # Simulate some work
        await asyncio.sleep(0.1)

        return {
            "status": "completed",
            "topic": topic,
            "findings": f"Research results for '{topic}' (stub implementation)",
            "sources": [],
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    async def _execute_analysis_task(self, task: BackgroundTask) -> dict[str, Any]:
        """
        Execute an analysis task.

        Analyzes data or trends based on parameters. In production, this would
        perform actual data analysis.

        Args:
            task: Analysis task with data parameters

        Returns:
            Dictionary with analysis results
        """
        data_type = task.params.get("data_type", "general")
        logger.info(f"Executing analysis task for: {data_type}")

        # Stub implementation
        await asyncio.sleep(0.1)

        return {
            "status": "completed",
            "data_type": data_type,
            "insights": f"Analysis results for '{data_type}' (stub implementation)",
            "metrics": {},
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    async def _execute_content_prep_task(self, task: BackgroundTask) -> dict[str, Any]:
        """
        Execute a content preparation task.

        Drafts social media posts or other content. In production, this would
        use LLM to generate contextually appropriate content.

        Args:
            task: Content prep task with platform and topic

        Returns:
            Dictionary with drafted content
        """
        platform = task.params.get("platform", "twitter")
        topic = task.params.get("topic", "general update")
        logger.info(f"Executing content_prep task for {platform}: {topic}")

        # Stub implementation
        await asyncio.sleep(0.1)

        return {
            "status": "completed",
            "platform": platform,
            "topic": topic,
            "drafts": [
                f"Draft post about {topic} for {platform} (stub implementation)"
            ],
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    async def _execute_maintenance_task(self, task: BackgroundTask) -> dict[str, Any]:
        """
        Execute a maintenance task.

        Performs cleanup, optimization, or housekeeping operations.

        Args:
            task: Maintenance task with action specification

        Returns:
            Dictionary with maintenance results
        """
        action = task.params.get("action", "general_cleanup")
        logger.info(f"Executing maintenance task: {action}")

        # Stub implementation
        await asyncio.sleep(0.1)

        return {
            "status": "completed",
            "action": action,
            "result": f"Maintenance action '{action}' completed (stub implementation)",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }


# Module-level singleton manager
_default_manager: Optional[SleepComputeManager] = None


def _get_default_manager() -> SleepComputeManager:
    """Get or create the default singleton manager."""
    global _default_manager
    if _default_manager is None:
        _default_manager = SleepComputeManager()
    return _default_manager


def configure_manager(
    queue_file: Optional[Path] = None,
    done_file: Optional[Path] = None,
    idle_threshold_minutes: int = 5,
) -> SleepComputeManager:
    """
    Configure and return the default manager.

    Call this at startup to customize the manager configuration.

    Args:
        queue_file: Path to queue file
        done_file: Path to completed tasks file
        idle_threshold_minutes: Idle threshold in minutes

    Returns:
        Configured SleepComputeManager
    """
    global _default_manager
    _default_manager = SleepComputeManager(
        queue_file=queue_file,
        done_file=done_file,
        idle_threshold_minutes=idle_threshold_minutes,
    )
    return _default_manager


# Convenience functions for simple usage


def queue_background_task(
    task_type: str,
    params: dict[str, Any],
    priority: str = "medium",
) -> str:
    """
    Queue a background task for idle-time execution.

    Args:
        task_type: Type of task ("research", "analysis", "content_prep", "maintenance")
        params: Parameters for the task
        priority: Priority level ("low", "medium", "high")

    Returns:
        Task ID for tracking

    Example:
        task_id = queue_background_task(
            "research",
            {"topic": "solana defi trends"},
            priority="high"
        )
    """
    manager = _get_default_manager()

    # Convert string to enum
    type_map = {
        "research": TaskType.RESEARCH,
        "analysis": TaskType.ANALYSIS,
        "content_prep": TaskType.CONTENT_PREP,
        "maintenance": TaskType.MAINTENANCE,
    }
    priority_map = {
        "low": TaskPriority.LOW,
        "medium": TaskPriority.MEDIUM,
        "high": TaskPriority.HIGH,
    }

    return manager.queue_task(
        task_type=type_map[task_type],
        params=params,
        priority=priority_map.get(priority, TaskPriority.MEDIUM),
    )


async def check_and_execute_idle_tasks() -> int:
    """
    Check if idle and execute pending background tasks.

    Call this periodically (e.g., every minute) to process background tasks.

    Returns:
        Number of tasks executed
    """
    manager = _get_default_manager()
    return await manager.check_and_execute_idle_tasks()


def pause_background_work() -> None:
    """
    Pause background task execution.

    Call this when user activity is detected to immediately pause
    any ongoing background work.
    """
    manager = _get_default_manager()
    manager.pause()


def resume_background_work() -> None:
    """
    Resume background task execution.

    Call this to allow background tasks to resume during idle periods.
    """
    manager = _get_default_manager()
    manager.resume()


def record_user_activity() -> None:
    """
    Record that user activity was detected.

    Call this whenever a user message is received to reset the idle timer
    and pause any ongoing background work.
    """
    manager = _get_default_manager()
    manager.record_user_activity()
    manager.pause()  # Also pause to stop current work


def get_completed_tasks() -> list[dict[str, Any]]:
    """
    Get all completed background tasks.

    Returns:
        List of completed task dictionaries with results
    """
    manager = _get_default_manager()
    return manager.get_completed_tasks()


def get_pending_tasks() -> list[dict[str, Any]]:
    """
    Get all pending background tasks.

    Returns:
        List of pending task dictionaries
    """
    manager = _get_default_manager()
    return manager.get_pending_tasks()


def is_idle_period() -> bool:
    """
    Check if the system is currently in an idle period.

    Returns:
        True if no user activity for the configured threshold
    """
    manager = _get_default_manager()
    return manager.is_idle_period()


def get_queue_status() -> dict[str, Any]:
    """
    Get current status of the background task queue.

    Returns:
        Dictionary with queue statistics
    """
    manager = _get_default_manager()
    pending = manager.get_pending_tasks()
    completed = manager.get_completed_tasks()

    return {
        "pending_count": len(pending),
        "completed_count": len(completed),
        "is_idle": manager.is_idle_period(),
        "is_paused": manager._paused,
        "idle_threshold_minutes": manager.idle_threshold_minutes,
        "pending_by_type": {
            t.value: len([p for p in pending if p["task_type"] == t.value])
            for t in TaskType
        },
    }
