"""
Backup Scheduler - Automated backup scheduling with APScheduler.

Provides:
- Daily full backups at midnight UTC
- Hourly incremental backups
- Automatic cleanup of old backups
- Failure notifications
"""

import asyncio
import logging
from typing import Optional, Callable, Any
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from pathlib import Path

from core.backup.backup_manager import BackupManager, BackupConfig, BackupResult

logger = logging.getLogger(__name__)


@dataclass
class ScheduledJob:
    """Represents a scheduled backup job."""
    id: str
    job_type: str
    schedule: str
    next_run: Optional[datetime] = None
    last_run: Optional[datetime] = None
    last_result: Optional[BackupResult] = None


class BackupScheduler:
    """
    Schedules and manages automated backups.

    Features:
    - APScheduler integration for cron-like scheduling
    - Full backup: daily at midnight UTC
    - Incremental backup: hourly at :00
    - Automatic cleanup: remove backups older than retention period
    - Failure notifications
    """

    def __init__(self, config: BackupConfig):
        self.config = config
        self._backup_manager = BackupManager(config)
        self._jobs: dict = {}
        self._scheduler = None
        self._running = False
        self._on_failure_callback: Optional[Callable] = None
        self._on_success_callback: Optional[Callable] = None

    def _get_scheduler(self):
        """Get or create the APScheduler instance."""
        if self._scheduler is None:
            try:
                from apscheduler.schedulers.asyncio import AsyncIOScheduler
                self._scheduler = AsyncIOScheduler(timezone="UTC")
            except ImportError:
                logger.warning("APScheduler not installed, using simple scheduler")
                self._scheduler = SimpleScheduler()
        return self._scheduler

    def schedule_full_backup(
        self,
        hour: int = 0,
        minute: int = 0,
        enabled: bool = True
    ) -> ScheduledJob:
        """
        Schedule daily full backup.

        Args:
            hour: Hour to run (UTC)
            minute: Minute to run
            enabled: Whether to enable immediately

        Returns:
            ScheduledJob representing the scheduled task
        """
        job_id = "full_daily_backup"

        scheduler = self._get_scheduler()

        if isinstance(scheduler, SimpleScheduler):
            scheduler.add_job(
                job_id,
                self._run_full_backup,
                hours=24,
                first_run_hour=hour,
                first_run_minute=minute
            )
        else:
            scheduler.add_job(
                self._run_full_backup,
                "cron",
                hour=hour,
                minute=minute,
                id=job_id,
                replace_existing=True
            )

        # Calculate next run time
        now = datetime.now(timezone.utc)
        next_run = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if next_run <= now:
            next_run += timedelta(days=1)

        job = ScheduledJob(
            id=job_id,
            job_type="full",
            schedule=f"Daily at {hour:02d}:{minute:02d} UTC",
            next_run=next_run
        )

        self._jobs[job_id] = job
        logger.info(f"Scheduled full backup: {job.schedule}")

        return job

    def schedule_incremental_backup(
        self,
        minute: int = 0,
        enabled: bool = True
    ) -> ScheduledJob:
        """
        Schedule hourly incremental backup.

        Args:
            minute: Minute of each hour to run
            enabled: Whether to enable immediately

        Returns:
            ScheduledJob representing the scheduled task
        """
        job_id = "incremental_hourly_backup"

        scheduler = self._get_scheduler()

        if isinstance(scheduler, SimpleScheduler):
            scheduler.add_job(
                job_id,
                self._run_incremental_backup,
                hours=1,
                first_run_minute=minute
            )
        else:
            scheduler.add_job(
                self._run_incremental_backup,
                "cron",
                minute=minute,
                id=job_id,
                replace_existing=True
            )

        now = datetime.now(timezone.utc)
        next_run = now.replace(minute=minute, second=0, microsecond=0)
        if next_run <= now:
            next_run += timedelta(hours=1)

        job = ScheduledJob(
            id=job_id,
            job_type="incremental",
            schedule=f"Hourly at :{minute:02d}",
            next_run=next_run
        )

        self._jobs[job_id] = job
        logger.info(f"Scheduled incremental backup: {job.schedule}")

        return job

    def schedule_cleanup(
        self,
        days: int = 30,
        hour: int = 3,
        minute: int = 0
    ) -> ScheduledJob:
        """
        Schedule automatic cleanup of old backups.

        Args:
            days: Remove backups older than this
            hour: Hour to run (UTC)
            minute: Minute to run

        Returns:
            ScheduledJob representing the scheduled task
        """
        job_id = "backup_cleanup"

        async def run_cleanup():
            removed = self._backup_manager.cleanup_old_backups()
            logger.info(f"Cleanup completed: {removed} old backups removed")

        scheduler = self._get_scheduler()

        if isinstance(scheduler, SimpleScheduler):
            scheduler.add_job(
                job_id,
                run_cleanup,
                hours=24,
                first_run_hour=hour,
                first_run_minute=minute
            )
        else:
            scheduler.add_job(
                run_cleanup,
                "cron",
                hour=hour,
                minute=minute,
                id=job_id,
                replace_existing=True
            )

        now = datetime.now(timezone.utc)
        next_run = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if next_run <= now:
            next_run += timedelta(days=1)

        job = ScheduledJob(
            id=job_id,
            job_type="cleanup",
            schedule=f"Daily at {hour:02d}:{minute:02d} UTC",
            next_run=next_run
        )

        self._jobs[job_id] = job
        return job

    async def _run_full_backup(self):
        """Execute full backup with error handling."""
        try:
            result = self._backup_manager.create_full_backup(
                metadata={"scheduled": True, "type": "daily_full"}
            )

            if "full_daily_backup" in self._jobs:
                self._jobs["full_daily_backup"].last_run = datetime.now(timezone.utc)
                self._jobs["full_daily_backup"].last_result = result

            if result.success:
                logger.info(f"Scheduled full backup completed: {result.backup_path}")
                if self._on_success_callback:
                    await self._maybe_await(self._on_success_callback(result))
            else:
                logger.error(f"Scheduled full backup failed: {result.error}")
                if self._on_failure_callback:
                    await self._maybe_await(self._on_failure_callback(result))

            return result

        except Exception as e:
            logger.error(f"Full backup exception: {e}")
            result = BackupResult(success=False, error=str(e))
            if self._on_failure_callback:
                await self._maybe_await(self._on_failure_callback(result))
            return result

    async def _run_incremental_backup(self):
        """Execute incremental backup with error handling."""
        try:
            result = self._backup_manager.create_incremental_backup(
                metadata={"scheduled": True, "type": "hourly_incremental"}
            )

            if "incremental_hourly_backup" in self._jobs:
                self._jobs["incremental_hourly_backup"].last_run = datetime.now(timezone.utc)
                self._jobs["incremental_hourly_backup"].last_result = result

            if result.success:
                if result.files_count > 0:
                    logger.info(f"Scheduled incremental backup completed: {result.files_count} files")
                if self._on_success_callback:
                    await self._maybe_await(self._on_success_callback(result))
            else:
                logger.error(f"Scheduled incremental backup failed: {result.error}")
                if self._on_failure_callback:
                    await self._maybe_await(self._on_failure_callback(result))

            return result

        except Exception as e:
            logger.error(f"Incremental backup exception: {e}")
            result = BackupResult(success=False, error=str(e))
            if self._on_failure_callback:
                await self._maybe_await(self._on_failure_callback(result))
            return result

    async def _maybe_await(self, result):
        """Await if result is a coroutine."""
        if asyncio.iscoroutine(result):
            return await result
        return result

    async def run_backup_now(self, backup_type: str = "full") -> BackupResult:
        """
        Run an immediate backup.

        Args:
            backup_type: "full" or "incremental"

        Returns:
            BackupResult
        """
        if backup_type == "full":
            return await self._run_full_backup()
        else:
            return await self._run_incremental_backup()

    def get_next_backup_time(self) -> Optional[datetime]:
        """Get the next scheduled backup time."""
        next_times = [
            job.next_run for job in self._jobs.values()
            if job.next_run is not None
        ]

        return min(next_times) if next_times else None

    def get_scheduled_jobs(self) -> list:
        """Get all scheduled jobs."""
        return list(self._jobs.values())

    def on_failure(self, callback: Callable):
        """Set callback for backup failures."""
        self._on_failure_callback = callback

    def on_success(self, callback: Callable):
        """Set callback for backup successes."""
        self._on_success_callback = callback

    def start(self):
        """Start the scheduler."""
        scheduler = self._get_scheduler()
        if not isinstance(scheduler, SimpleScheduler):
            scheduler.start()
        self._running = True
        logger.info("Backup scheduler started")

    def stop(self):
        """Stop the scheduler."""
        if self._scheduler is not None and not isinstance(self._scheduler, SimpleScheduler):
            self._scheduler.shutdown()
        self._running = False
        logger.info("Backup scheduler stopped")


class SimpleScheduler:
    """
    Simple async scheduler fallback when APScheduler is not available.
    """

    def __init__(self):
        self._jobs = {}
        self._tasks = {}

    def add_job(
        self,
        job_id: str,
        func: Callable,
        hours: int = 24,
        first_run_hour: int = None,
        first_run_minute: int = 0
    ):
        """Add a scheduled job."""
        self._jobs[job_id] = {
            "func": func,
            "hours": hours,
            "first_run_hour": first_run_hour,
            "first_run_minute": first_run_minute
        }

    async def run(self):
        """Run the scheduler loop."""
        for job_id, job_config in self._jobs.items():
            task = asyncio.create_task(
                self._run_job_loop(job_id, job_config)
            )
            self._tasks[job_id] = task

    async def _run_job_loop(self, job_id: str, config: dict):
        """Run a job on schedule."""
        # Calculate initial delay
        now = datetime.now(timezone.utc)
        if config["first_run_hour"] is not None:
            next_run = now.replace(
                hour=config["first_run_hour"],
                minute=config["first_run_minute"],
                second=0,
                microsecond=0
            )
            if next_run <= now:
                next_run += timedelta(hours=config["hours"])
        else:
            next_run = now.replace(
                minute=config["first_run_minute"],
                second=0,
                microsecond=0
            )
            if next_run <= now:
                next_run += timedelta(hours=config["hours"])

        initial_delay = (next_run - now).total_seconds()
        await asyncio.sleep(initial_delay)

        while True:
            try:
                result = config["func"]()
                if asyncio.iscoroutine(result):
                    await result
            except Exception as e:
                logger.error(f"Job {job_id} failed: {e}")

            await asyncio.sleep(config["hours"] * 3600)
