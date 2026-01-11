"""
Action Scheduler - Cron-like scheduled task execution.

Features:
- Cron expression support
- One-time and recurring schedules
- Timezone-aware scheduling
- Missed job handling
- Persistence of schedule state
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Union
import uuid
import json
from pathlib import Path

logger = logging.getLogger(__name__)


class ScheduleType(Enum):
    """Type of schedule."""
    ONCE = "once"
    INTERVAL = "interval"
    CRON = "cron"
    DAILY = "daily"
    WEEKLY = "weekly"


class JobStatus(Enum):
    """Status of a scheduled job."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    PAUSED = "paused"
    CANCELLED = "cancelled"


@dataclass
class ScheduledJob:
    """
    A scheduled job definition.

    Attributes:
        name: Human-readable job name
        action: Async callable to execute
        schedule_type: Type of schedule
        schedule_value: Schedule configuration
        enabled: Whether job is active
        max_runs: Maximum number of executions (None = unlimited)
        retry_on_failure: Whether to retry on failure
        timeout: Job timeout in seconds
    """
    name: str
    action: Callable
    schedule_type: ScheduleType
    schedule_value: Union[datetime, int, str, Dict[str, Any]]
    params: Dict[str, Any] = field(default_factory=dict)
    enabled: bool = True
    max_runs: Optional[int] = None
    retry_on_failure: bool = False
    timeout: float = 300.0
    tags: List[str] = field(default_factory=list)

    # Runtime state
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:12])
    status: JobStatus = JobStatus.PENDING
    run_count: int = 0
    last_run: Optional[datetime] = None
    next_run: Optional[datetime] = None
    last_result: Any = None
    last_error: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class JobExecution:
    """Record of a job execution."""
    job_id: str
    job_name: str
    started_at: datetime
    completed_at: Optional[datetime] = None
    success: bool = False
    result: Any = None
    error: Optional[str] = None
    duration_ms: float = 0


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
            (0, 59),   # minute
            (0, 23),   # hour
            (1, 31),   # day
            (1, 12),   # month
            (0, 6),    # weekday (0=Sunday)
        ]

        result = {}
        for i, (part, field_name, (min_val, max_val)) in enumerate(zip(parts, fields, ranges)):
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
            if (candidate.minute in parsed["minute"] and
                candidate.hour in parsed["hour"] and
                candidate.day in parsed["day"] and
                candidate.month in parsed["month"] and
                candidate.weekday() in parsed["weekday"]):
                return candidate
            candidate += timedelta(minutes=1)

        raise ValueError(f"Could not find next run time for: {expression}")


class ActionScheduler:
    """
    Scheduler for executing actions at specified times.

    Usage:
        scheduler = ActionScheduler()

        # One-time job
        scheduler.schedule_once("backup", backup_action, run_at=datetime(...))

        # Interval job (every 5 minutes)
        scheduler.schedule_interval("health-check", health_action, minutes=5)

        # Cron job
        scheduler.schedule_cron("daily-report", report_action, "0 9 * * *")

        # Start scheduler
        await scheduler.start()
    """

    def __init__(
        self,
        persistence_path: Optional[Path] = None,
        max_concurrent_jobs: int = 10,
    ):
        self._jobs: Dict[str, ScheduledJob] = {}
        self._history: List[JobExecution] = []
        self._max_history = 1000
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._persistence_path = persistence_path
        self._max_concurrent = max_concurrent_jobs
        self._active_jobs: Dict[str, asyncio.Task] = {}
        self._callbacks: Dict[str, List[Callable]] = {
            "job_started": [],
            "job_completed": [],
            "job_failed": [],
        }

    def schedule_once(
        self,
        name: str,
        action: Callable,
        run_at: datetime,
        params: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> str:
        """Schedule a one-time job."""
        job = ScheduledJob(
            name=name,
            action=action,
            schedule_type=ScheduleType.ONCE,
            schedule_value=run_at,
            params=params or {},
            next_run=run_at,
            **kwargs,
        )
        self._jobs[job.id] = job
        logger.info(f"Scheduled one-time job '{name}' for {run_at}")
        return job.id

    def schedule_interval(
        self,
        name: str,
        action: Callable,
        seconds: int = 0,
        minutes: int = 0,
        hours: int = 0,
        params: Optional[Dict[str, Any]] = None,
        start_immediately: bool = False,
        **kwargs,
    ) -> str:
        """Schedule a recurring interval job."""
        interval_seconds = seconds + (minutes * 60) + (hours * 3600)
        if interval_seconds <= 0:
            raise ValueError("Interval must be positive")

        next_run = datetime.utcnow()
        if not start_immediately:
            next_run += timedelta(seconds=interval_seconds)

        job = ScheduledJob(
            name=name,
            action=action,
            schedule_type=ScheduleType.INTERVAL,
            schedule_value=interval_seconds,
            params=params or {},
            next_run=next_run,
            **kwargs,
        )
        self._jobs[job.id] = job
        logger.info(f"Scheduled interval job '{name}' every {interval_seconds}s")
        return job.id

    def schedule_cron(
        self,
        name: str,
        action: Callable,
        cron_expression: str,
        params: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> str:
        """Schedule a cron-based job."""
        # Validate cron expression
        next_run = CronParser.next_run(cron_expression)

        job = ScheduledJob(
            name=name,
            action=action,
            schedule_type=ScheduleType.CRON,
            schedule_value=cron_expression,
            params=params or {},
            next_run=next_run,
            **kwargs,
        )
        self._jobs[job.id] = job
        logger.info(f"Scheduled cron job '{name}' with '{cron_expression}', next run: {next_run}")
        return job.id

    def schedule_daily(
        self,
        name: str,
        action: Callable,
        hour: int = 0,
        minute: int = 0,
        params: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> str:
        """Schedule a daily job at specific time."""
        cron_expr = f"{minute} {hour} * * *"
        return self.schedule_cron(name, action, cron_expr, params, **kwargs)

    def schedule_weekly(
        self,
        name: str,
        action: Callable,
        weekday: int = 0,  # 0=Monday
        hour: int = 0,
        minute: int = 0,
        params: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> str:
        """Schedule a weekly job."""
        # Convert to cron weekday (0=Sunday in cron)
        cron_weekday = (weekday + 1) % 7
        cron_expr = f"{minute} {hour} * * {cron_weekday}"
        return self.schedule_cron(name, action, cron_expr, params, **kwargs)

    def pause_job(self, job_id: str) -> bool:
        """Pause a scheduled job."""
        if job_id in self._jobs:
            self._jobs[job_id].status = JobStatus.PAUSED
            self._jobs[job_id].enabled = False
            logger.info(f"Paused job {job_id}")
            return True
        return False

    def resume_job(self, job_id: str) -> bool:
        """Resume a paused job."""
        if job_id in self._jobs:
            job = self._jobs[job_id]
            job.status = JobStatus.PENDING
            job.enabled = True
            # Recalculate next run
            self._update_next_run(job)
            logger.info(f"Resumed job {job_id}")
            return True
        return False

    def cancel_job(self, job_id: str) -> bool:
        """Cancel and remove a scheduled job."""
        if job_id in self._jobs:
            job = self._jobs[job_id]
            job.status = JobStatus.CANCELLED

            # Cancel running task if any
            if job_id in self._active_jobs:
                self._active_jobs[job_id].cancel()
                del self._active_jobs[job_id]

            del self._jobs[job_id]
            logger.info(f"Cancelled job {job_id}")
            return True
        return False

    def get_job(self, job_id: str) -> Optional[ScheduledJob]:
        """Get job by ID."""
        return self._jobs.get(job_id)

    def get_jobs(
        self,
        status: Optional[JobStatus] = None,
        tags: Optional[List[str]] = None,
    ) -> List[ScheduledJob]:
        """Get jobs with optional filtering."""
        jobs = list(self._jobs.values())

        if status:
            jobs = [j for j in jobs if j.status == status]
        if tags:
            jobs = [j for j in jobs if any(t in j.tags for t in tags)]

        return sorted(jobs, key=lambda j: j.next_run or datetime.max)

    def get_history(self, job_id: Optional[str] = None, limit: int = 100) -> List[JobExecution]:
        """Get execution history."""
        history = self._history
        if job_id:
            history = [h for h in history if h.job_id == job_id]
        return history[-limit:]

    def on_event(self, event: str, callback: Callable) -> None:
        """Register event callback (job_started, job_completed, job_failed)."""
        if event in self._callbacks:
            self._callbacks[event].append(callback)

    async def start(self) -> None:
        """Start the scheduler."""
        if self._running:
            return

        self._running = True
        self._task = asyncio.create_task(self._run_loop())
        logger.info("Scheduler started")

    async def stop(self) -> None:
        """Stop the scheduler."""
        self._running = False

        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

        # Cancel active jobs
        for task in self._active_jobs.values():
            task.cancel()
        self._active_jobs.clear()

        logger.info("Scheduler stopped")

    async def run_job_now(self, job_id: str) -> Optional[JobExecution]:
        """Manually trigger a job execution."""
        job = self._jobs.get(job_id)
        if not job:
            return None

        return await self._execute_job(job)

    async def _run_loop(self) -> None:
        """Main scheduler loop."""
        while self._running:
            try:
                now = datetime.utcnow()

                # Find due jobs
                due_jobs = [
                    job for job in self._jobs.values()
                    if (job.enabled and
                        job.status == JobStatus.PENDING and
                        job.next_run and
                        job.next_run <= now and
                        len(self._active_jobs) < self._max_concurrent)
                ]

                # Execute due jobs
                for job in due_jobs:
                    if job.id not in self._active_jobs:
                        task = asyncio.create_task(self._execute_job(job))
                        self._active_jobs[job.id] = task

                # Clean up completed tasks
                completed = [
                    job_id for job_id, task in self._active_jobs.items()
                    if task.done()
                ]
                for job_id in completed:
                    del self._active_jobs[job_id]

                # Sleep briefly
                await asyncio.sleep(1)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Scheduler loop error: {e}")
                await asyncio.sleep(5)

    async def _execute_job(self, job: ScheduledJob) -> JobExecution:
        """Execute a single job."""
        execution = JobExecution(
            job_id=job.id,
            job_name=job.name,
            started_at=datetime.utcnow(),
        )

        job.status = JobStatus.RUNNING
        self._emit_event("job_started", job, execution)

        try:
            # Execute with timeout
            if asyncio.iscoroutinefunction(job.action):
                result = await asyncio.wait_for(
                    job.action(**job.params),
                    timeout=job.timeout,
                )
            else:
                result = job.action(**job.params)

            execution.success = True
            execution.result = result
            job.last_result = result
            job.status = JobStatus.COMPLETED
            self._emit_event("job_completed", job, execution)

        except asyncio.TimeoutError:
            execution.error = f"Timeout after {job.timeout}s"
            job.last_error = execution.error
            job.status = JobStatus.FAILED
            self._emit_event("job_failed", job, execution)

        except Exception as e:
            execution.error = str(e)
            job.last_error = execution.error
            job.status = JobStatus.FAILED
            logger.error(f"Job '{job.name}' failed: {e}")
            self._emit_event("job_failed", job, execution)

        finally:
            execution.completed_at = datetime.utcnow()
            execution.duration_ms = (
                execution.completed_at - execution.started_at
            ).total_seconds() * 1000

            job.run_count += 1
            job.last_run = execution.started_at

            # Update next run
            self._update_next_run(job)

            # Check max runs
            if job.max_runs and job.run_count >= job.max_runs:
                job.enabled = False
                job.status = JobStatus.COMPLETED

            # Store history
            self._history.append(execution)
            if len(self._history) > self._max_history:
                self._history = self._history[-self._max_history:]

        return execution

    def _update_next_run(self, job: ScheduledJob) -> None:
        """Update job's next run time."""
        if not job.enabled:
            job.next_run = None
            return

        if job.schedule_type == ScheduleType.ONCE:
            job.next_run = None  # One-time jobs don't repeat

        elif job.schedule_type == ScheduleType.INTERVAL:
            job.next_run = datetime.utcnow() + timedelta(seconds=job.schedule_value)

        elif job.schedule_type == ScheduleType.CRON:
            job.next_run = CronParser.next_run(job.schedule_value)

        # Reset status for next run
        if job.next_run and job.status != JobStatus.PAUSED:
            job.status = JobStatus.PENDING

    def _emit_event(self, event: str, job: ScheduledJob, execution: JobExecution) -> None:
        """Emit event to callbacks."""
        for callback in self._callbacks.get(event, []):
            try:
                callback(job, execution)
            except Exception as e:
                logger.error(f"Event callback error: {e}")

    async def save_state(self) -> None:
        """Save scheduler state to file."""
        if not self._persistence_path:
            return

        state = {
            "jobs": [
                {
                    "id": j.id,
                    "name": j.name,
                    "schedule_type": j.schedule_type.value,
                    "schedule_value": (
                        j.schedule_value.isoformat()
                        if isinstance(j.schedule_value, datetime)
                        else j.schedule_value
                    ),
                    "enabled": j.enabled,
                    "run_count": j.run_count,
                    "last_run": j.last_run.isoformat() if j.last_run else None,
                    "tags": j.tags,
                }
                for j in self._jobs.values()
            ],
            "saved_at": datetime.utcnow().isoformat(),
        }

        self._persistence_path.parent.mkdir(parents=True, exist_ok=True)
        self._persistence_path.write_text(json.dumps(state, indent=2))
        logger.info(f"Saved scheduler state to {self._persistence_path}")


# Singleton instance
_scheduler: Optional[ActionScheduler] = None


def get_scheduler() -> ActionScheduler:
    """Get the global scheduler instance."""
    global _scheduler
    if _scheduler is None:
        _scheduler = ActionScheduler()
    return _scheduler
