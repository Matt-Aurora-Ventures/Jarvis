"""
Task classes for the scheduler.

Provides:
- Task: Base class for executable tasks
- TaskResult: Result of task execution
- ScheduledTask: Task with schedule information
- ScheduleStatus: Status enum for scheduled tasks
"""

import asyncio
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

logger = logging.getLogger(__name__)


class ScheduleStatus(Enum):
    """Status of a scheduled task."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    PAUSED = "paused"
    CANCELLED = "cancelled"


@dataclass
class TaskResult:
    """
    Result of task execution.

    Attributes:
        success: Whether the task completed successfully
        result: Return value from the task handler
        error: Error message if task failed
        started_at: When task execution started
        completed_at: When task execution completed
    """
    success: bool
    result: Any = None
    error: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    @property
    def duration_ms(self) -> Optional[float]:
        """Get execution duration in milliseconds."""
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds() * 1000
        return None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "success": self.success,
            "result": self.result,
            "error": self.error,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "duration_ms": self.duration_ms,
        }


@dataclass
class Task:
    """
    Base class for executable tasks.

    Attributes:
        name: Human-readable task name
        handler: Callable to execute (sync or async)
        args: Positional arguments for handler
        kwargs: Keyword arguments for handler
        timeout: Maximum execution time in seconds
        retry_count: Number of retry attempts
        retry_delay: Delay between retries in seconds
        tags: Tags for categorization
        metadata: Additional metadata
        id: Unique task identifier
        created_at: When the task was created
    """
    name: str
    handler: Callable
    args: Tuple = field(default_factory=tuple)
    kwargs: Dict[str, Any] = field(default_factory=dict)
    timeout: float = 300.0
    retry_count: int = 0
    retry_delay: float = 1.0
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:12])
    created_at: datetime = field(default_factory=datetime.utcnow)

    # Callbacks (set after creation)
    on_success: Optional[Callable[["TaskResult"], Any]] = field(default=None, repr=False)
    on_failure: Optional[Callable[["TaskResult"], Any]] = field(default=None, repr=False)

    def __post_init__(self):
        """Validate task configuration."""
        if not self.name:
            raise ValueError("Task name cannot be empty")
        if self.handler is None:
            raise ValueError("Task handler cannot be None")

    async def run(self) -> TaskResult:
        """
        Execute the task and return result.

        Returns:
            TaskResult with success status and result/error
        """
        started_at = datetime.utcnow()
        result = TaskResult(success=False, started_at=started_at)

        try:
            # Execute handler with timeout
            if asyncio.iscoroutinefunction(self.handler):
                task_result = await asyncio.wait_for(
                    self.handler(*self.args, **self.kwargs),
                    timeout=self.timeout,
                )
            else:
                # Run sync handler in executor for timeout support
                loop = asyncio.get_event_loop()
                task_result = await asyncio.wait_for(
                    loop.run_in_executor(
                        None,
                        lambda: self.handler(*self.args, **self.kwargs)
                    ),
                    timeout=self.timeout,
                )

            result.success = True
            result.result = task_result

        except asyncio.TimeoutError:
            result.error = f"Task timed out after {self.timeout}s"
            logger.warning(f"Task '{self.name}' timed out")

        except Exception as e:
            result.error = str(e)
            logger.error(f"Task '{self.name}' failed: {e}")

        finally:
            result.completed_at = datetime.utcnow()

            # Call callbacks (don't let callback errors affect result)
            try:
                if result.success and self.on_success:
                    callback_result = self.on_success(result)
                    if asyncio.iscoroutine(callback_result):
                        await callback_result
                elif not result.success and self.on_failure:
                    callback_result = self.on_failure(result)
                    if asyncio.iscoroutine(callback_result):
                        await callback_result
            except Exception as e:
                logger.warning(f"Callback error for task '{self.name}': {e}")

        return result

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "id": self.id,
            "name": self.name,
            "handler": f"{self.handler.__module__}.{self.handler.__name__}" if hasattr(self.handler, "__module__") else str(self.handler),
            "args": list(self.args),
            "kwargs": self.kwargs,
            "timeout": self.timeout,
            "retry_count": self.retry_count,
            "retry_delay": self.retry_delay,
            "tags": self.tags,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
        }


@dataclass
class ScheduledTask:
    """
    A task with schedule information.

    Attributes:
        task: The underlying Task to execute
        run_at: Next scheduled run time
        recurring: Whether this is a recurring schedule
        interval_seconds: Interval for recurring tasks
        cron_expression: Cron expression for cron-based scheduling
        enabled: Whether the schedule is active
        status: Current schedule status
        run_count: Number of times task has run
        max_runs: Maximum number of runs (None = unlimited)
        last_run: Last execution time
        last_result: Result of last execution
    """
    task: Task
    run_at: Optional[datetime] = None
    recurring: bool = False
    interval_seconds: Optional[int] = None
    cron_expression: Optional[str] = None
    enabled: bool = True
    status: ScheduleStatus = ScheduleStatus.PENDING
    run_count: int = 0
    max_runs: Optional[int] = None
    last_run: Optional[datetime] = None
    last_result: Optional[TaskResult] = None
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:12])
    created_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "id": self.id,
            "task": self.task.to_dict(),
            "run_at": self.run_at.isoformat() if self.run_at else None,
            "recurring": self.recurring,
            "interval_seconds": self.interval_seconds,
            "cron_expression": self.cron_expression,
            "enabled": self.enabled,
            "status": self.status.value,
            "run_count": self.run_count,
            "max_runs": self.max_runs,
            "last_run": self.last_run.isoformat() if self.last_run else None,
            "created_at": self.created_at.isoformat(),
        }
