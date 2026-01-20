#!/usr/bin/env python3
"""
Scheduled Backup Daemon

Automatically creates backups at specified intervals.
Integrates with supervisor or can run standalone.
"""

import argparse
import asyncio
import logging
import sys
from pathlib import Path
from datetime import datetime, time
from typing import Optional

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from core.backup_manager import BackupManager

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class BackupScheduler:
    """Schedules and manages automatic backups"""

    def __init__(self,
                 interval_hours: int = 6,
                 backup_type: str = "incremental",
                 backup_dir: Optional[Path] = None,
                 cleanup_on_start: bool = True):
        """
        Initialize backup scheduler

        Args:
            interval_hours: Hours between automatic backups
            backup_type: Type of backup to create
            backup_dir: Custom backup directory
            cleanup_on_start: Run cleanup when starting
        """
        self.interval_hours = interval_hours
        self.backup_type = backup_type

        self.manager = BackupManager(
            backup_dir=backup_dir,
            project_root=PROJECT_ROOT
        )

        self.cleanup_on_start = cleanup_on_start
        self.running = False

    async def run_backup(self):
        """Execute a backup"""
        try:
            logger.info(f"Starting {self.backup_type} backup...")

            metadata = self.manager.create_backup(
                backup_type=self.backup_type,
                description=f"Scheduled backup at {datetime.now().isoformat()}"
            )

            logger.info(
                f"✓ Backup completed: {metadata.backup_id} "
                f"({len(metadata.files_backed_up)} files, "
                f"{metadata.size_bytes:,} bytes)"
            )

            # Verify backup
            verify_results = self.manager.verify_backup(metadata.backup_id)
            if verify_results["valid"]:
                logger.info("✓ Backup verification passed")
            else:
                logger.error(f"✗ Backup verification failed: {verify_results}")

        except Exception as e:
            logger.error(f"Backup failed: {e}", exc_info=True)

    async def run_cleanup(self):
        """Run backup cleanup"""
        try:
            logger.info("Running backup cleanup...")

            results = self.manager.cleanup_old_backups(dry_run=False)

            logger.info(
                f"✓ Cleanup completed: deleted {len(results['deleted_backups'])} backups, "
                f"freed {results['total_freed_bytes']:,} bytes"
            )

        except Exception as e:
            logger.error(f"Cleanup failed: {e}", exc_info=True)

    async def scheduled_backup_loop(self):
        """Main loop for scheduled backups"""
        logger.info(
            f"Starting backup scheduler: every {self.interval_hours}h, "
            f"type={self.backup_type}"
        )

        # Initial cleanup if requested
        if self.cleanup_on_start:
            await self.run_cleanup()

        # Initial backup
        await self.run_backup()

        self.running = True

        try:
            while self.running:
                # Wait for interval
                await asyncio.sleep(self.interval_hours * 3600)

                # Run backup
                await self.run_backup()

                # Cleanup old backups every 24 hours
                current_hour = datetime.now().hour
                if current_hour == 0:  # Cleanup at midnight
                    await self.run_cleanup()

        except asyncio.CancelledError:
            logger.info("Backup scheduler stopped")
            raise

    def stop(self):
        """Stop the scheduler"""
        self.running = False
        logger.info("Stopping backup scheduler...")


async def run_daily_backup_at(hour: int, minute: int = 0):
    """
    Run backup once daily at specified time

    Args:
        hour: Hour to run backup (0-23)
        minute: Minute to run backup (0-59)
    """
    manager = BackupManager(project_root=PROJECT_ROOT)
    target_time = time(hour=hour, minute=minute)

    logger.info(f"Daily backup scheduled for {target_time}")

    while True:
        now = datetime.now()
        target = datetime.combine(now.date(), target_time)

        # If target time has passed today, schedule for tomorrow
        if now > target:
            target = datetime.combine(
                now.date() + timedelta(days=1),
                target_time
            )

        # Wait until target time
        wait_seconds = (target - now).total_seconds()
        logger.info(f"Next backup in {wait_seconds / 3600:.1f} hours")

        await asyncio.sleep(wait_seconds)

        # Run backup
        try:
            logger.info("Running daily backup...")
            metadata = manager.create_backup(
                backup_type="full",
                description=f"Daily backup at {datetime.now().isoformat()}"
            )
            logger.info(f"✓ Daily backup completed: {metadata.backup_id}")

            # Cleanup old backups
            results = manager.cleanup_old_backups(dry_run=False)
            logger.info(f"✓ Cleanup: deleted {len(results['deleted_backups'])} old backups")

        except Exception as e:
            logger.error(f"Daily backup failed: {e}", exc_info=True)


def main():
    parser = argparse.ArgumentParser(description="Scheduled backup daemon")
    parser.add_argument("--interval", type=int, default=6,
                       help="Hours between backups (default: 6)")
    parser.add_argument("--type", choices=["full", "incremental", "positions_only"],
                       default="incremental",
                       help="Type of backup to create")
    parser.add_argument("--backup-dir", type=Path,
                       help="Custom backup directory")
    parser.add_argument("--no-cleanup", action="store_true",
                       help="Skip cleanup on start")
    parser.add_argument("--daily", action="store_true",
                       help="Run once daily instead of at intervals")
    parser.add_argument("--daily-hour", type=int, default=2,
                       help="Hour for daily backup (0-23, default: 2)")

    args = parser.parse_args()

    if args.daily:
        # Daily backup mode
        logger.info(f"Starting daily backup at {args.daily_hour}:00")
        asyncio.run(run_daily_backup_at(hour=args.daily_hour))
    else:
        # Interval backup mode
        scheduler = BackupScheduler(
            interval_hours=args.interval,
            backup_type=args.type,
            backup_dir=args.backup_dir,
            cleanup_on_start=not args.no_cleanup
        )

        try:
            asyncio.run(scheduler.scheduled_backup_loop())
        except KeyboardInterrupt:
            logger.info("Received interrupt signal")
            scheduler.stop()


if __name__ == "__main__":
    main()
