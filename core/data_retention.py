"""
Data Retention Policies - Manage data lifecycle, cleanup, and archival.
"""

import asyncio
import logging
import sqlite3
import shutil
import gzip
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass, field
from pathlib import Path
from enum import Enum
import json

from core.security_validation import sanitize_sql_identifier

logger = logging.getLogger(__name__)


class RetentionAction(Enum):
    """Actions to take on expired data."""
    DELETE = "delete"
    ARCHIVE = "archive"
    COMPRESS = "compress"
    ANONYMIZE = "anonymize"


@dataclass
class RetentionPolicy:
    """Policy for data retention."""
    name: str
    table_or_path: str  # Table name or file path pattern
    retention_days: int
    action: RetentionAction = RetentionAction.DELETE
    timestamp_column: str = "timestamp"  # For SQLite tables
    archive_path: Optional[Path] = None
    is_enabled: bool = True
    last_run: Optional[str] = None
    records_affected: int = 0


@dataclass
class RetentionStats:
    """Statistics from retention run."""
    policy_name: str
    records_processed: int
    records_deleted: int
    records_archived: int
    bytes_freed: int
    duration_seconds: float
    timestamp: str


class RetentionManager:
    """
    Manage data retention across the application.

    Usage:
        manager = RetentionManager()

        # Add policies
        manager.add_policy(RetentionPolicy(
            name="old_errors",
            table_or_path="errors",
            retention_days=30,
            action=RetentionAction.DELETE
        ))

        # Run cleanup
        await manager.run_all_policies()
    """

    def __init__(
        self,
        db_path: Optional[Path] = None,
        archive_dir: Optional[Path] = None
    ):
        self.db_path = db_path or Path(__file__).parent.parent / "data"
        self.archive_dir = archive_dir or self.db_path / "archive"
        self.policies: Dict[str, RetentionPolicy] = {}
        self._stats: List[RetentionStats] = []
        self._setup_default_policies()

    def _setup_default_policies(self):
        """Setup default retention policies for Jarvis."""
        defaults = [
            RetentionPolicy(
                name="error_logs",
                table_or_path="errors.db:errors",
                retention_days=30,
                action=RetentionAction.DELETE,
                timestamp_column="timestamp"
            ),
            RetentionPolicy(
                name="old_trades",
                table_or_path="trades.db:trades",
                retention_days=365,
                action=RetentionAction.ARCHIVE,
                timestamp_column="timestamp"
            ),
            RetentionPolicy(
                name="metrics_history",
                table_or_path="metrics.db:metrics_history",
                retention_days=90,
                action=RetentionAction.DELETE,
                timestamp_column="timestamp"
            ),
            RetentionPolicy(
                name="alert_dedup",
                table_or_path="buy_tracker.db:sent_alerts",
                retention_days=7,
                action=RetentionAction.DELETE,
                timestamp_column="sent_at"
            ),
            RetentionPolicy(
                name="engagement_history",
                table_or_path="engagement.db:metrics_history",
                retention_days=90,
                action=RetentionAction.COMPRESS,
                timestamp_column="timestamp"
            ),
            RetentionPolicy(
                name="old_backups",
                table_or_path="backups/*.tar.gz",
                retention_days=30,
                action=RetentionAction.DELETE
            ),
            RetentionPolicy(
                name="audit_logs",
                table_or_path="audit.log",
                retention_days=90,
                action=RetentionAction.ARCHIVE
            ),
        ]

        for policy in defaults:
            self.policies[policy.name] = policy

    def add_policy(self, policy: RetentionPolicy):
        """Add or update a retention policy."""
        self.policies[policy.name] = policy
        logger.info(f"Added retention policy: {policy.name}")

    def remove_policy(self, name: str):
        """Remove a retention policy."""
        if name in self.policies:
            del self.policies[name]

    def get_policy(self, name: str) -> Optional[RetentionPolicy]:
        """Get a specific policy."""
        return self.policies.get(name)

    async def run_policy(self, policy_name: str) -> Optional[RetentionStats]:
        """Run a specific retention policy."""
        policy = self.policies.get(policy_name)
        if not policy:
            logger.error(f"Unknown policy: {policy_name}")
            return None

        if not policy.is_enabled:
            logger.info(f"Policy {policy_name} is disabled, skipping")
            return None

        start_time = datetime.now(timezone.utc)

        try:
            if ":" in policy.table_or_path:
                # SQLite table
                stats = await self._process_sqlite_policy(policy)
            elif "*" in policy.table_or_path:
                # File pattern
                stats = await self._process_file_pattern_policy(policy)
            else:
                # Single file
                stats = await self._process_file_policy(policy)

            duration = (datetime.now(timezone.utc) - start_time).total_seconds()
            stats.duration_seconds = duration
            stats.timestamp = datetime.now(timezone.utc).isoformat()

            policy.last_run = stats.timestamp
            policy.records_affected = stats.records_processed

            self._stats.append(stats)
            logger.info(
                f"Retention policy {policy_name}: processed {stats.records_processed}, "
                f"freed {stats.bytes_freed} bytes in {duration:.2f}s"
            )

            return stats

        except Exception as e:
            logger.error(f"Failed to run retention policy {policy_name}: {e}")
            return None

    async def _process_sqlite_policy(self, policy: RetentionPolicy) -> RetentionStats:
        """Process a SQLite table retention policy."""
        db_file, table_name = policy.table_or_path.split(":")
        db_path = self.db_path / db_file

        if not db_path.exists():
            return RetentionStats(
                policy_name=policy.name,
                records_processed=0,
                records_deleted=0,
                records_archived=0,
                bytes_freed=0,
                duration_seconds=0,
                timestamp=""
            )

        cutoff_date = (
            datetime.now(timezone.utc) - timedelta(days=policy.retention_days)
        ).isoformat()

        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Get count of records to process
        safe_table = sanitize_sql_identifier(table_name)
        safe_timestamp_col = sanitize_sql_identifier(policy.timestamp_column)
        cursor.execute(f"""
            SELECT COUNT(*) FROM {safe_table}
            WHERE {safe_timestamp_col} < ?
        """, (cutoff_date,))
        record_count = cursor.fetchone()[0]

        records_deleted = 0
        records_archived = 0
        bytes_freed = 0

        if record_count > 0:
            if policy.action == RetentionAction.ARCHIVE:
                # Export to archive first
                archive_path = self._get_archive_path(policy, table_name)
                records_archived = self._archive_sqlite_records(
                    conn, table_name, policy.timestamp_column, cutoff_date, archive_path
                )
                records_deleted = records_archived

            elif policy.action == RetentionAction.DELETE:
                cursor.execute(f"""
                    DELETE FROM {safe_table}
                    WHERE {safe_timestamp_col} < ?
                """, (cutoff_date,))
                records_deleted = cursor.rowcount
                conn.commit()

            elif policy.action == RetentionAction.ANONYMIZE:
                # Anonymize sensitive fields instead of deleting
                records_deleted = self._anonymize_sqlite_records(
                    conn, table_name, policy.timestamp_column, cutoff_date
                )

            # Vacuum to reclaim space
            cursor.execute("VACUUM")
            conn.commit()

        conn.close()

        # Calculate space freed (approximate)
        bytes_freed = record_count * 200  # Rough estimate per record

        return RetentionStats(
            policy_name=policy.name,
            records_processed=record_count,
            records_deleted=records_deleted,
            records_archived=records_archived,
            bytes_freed=bytes_freed,
            duration_seconds=0,
            timestamp=""
        )

    def _archive_sqlite_records(
        self,
        conn: sqlite3.Connection,
        table_name: str,
        timestamp_col: str,
        cutoff_date: str,
        archive_path: Path
    ) -> int:
        """Archive SQLite records to JSON file."""
        cursor = conn.cursor()

        safe_table = sanitize_sql_identifier(table_name)
        safe_timestamp_col = sanitize_sql_identifier(timestamp_col)

        cursor.execute(f"""
            SELECT * FROM {safe_table}
            WHERE {safe_timestamp_col} < ?
        """, (cutoff_date,))

        columns = [description[0] for description in cursor.description]
        rows = cursor.fetchall()

        if not rows:
            return 0

        # Save to JSON archive
        archive_path.parent.mkdir(parents=True, exist_ok=True)
        records = [dict(zip(columns, row)) for row in rows]

        with gzip.open(f"{archive_path}.json.gz", 'wt', encoding='utf-8') as f:
            json.dump(records, f)

        # Delete archived records
        cursor.execute(f"""
            DELETE FROM {safe_table}
            WHERE {safe_timestamp_col} < ?
        """, (cutoff_date,))
        conn.commit()

        return len(rows)

    def _anonymize_sqlite_records(
        self,
        conn: sqlite3.Connection,
        table_name: str,
        timestamp_col: str,
        cutoff_date: str
    ) -> int:
        """Anonymize old records instead of deleting."""
        cursor = conn.cursor()

        safe_table = sanitize_sql_identifier(table_name)
        safe_timestamp_col = sanitize_sql_identifier(timestamp_col)

        # Common sensitive columns to anonymize
        sensitive_columns = [
            'wallet_address', 'buyer_wallet', 'user_id', 'email',
            'ip_address', 'tx_signature'
        ]

        # Get actual columns in table
        cursor.execute(f"PRAGMA table_info({safe_table})")
        table_columns = {row[1] for row in cursor.fetchall()}

        # Find columns to anonymize (sanitize each column name)
        columns_to_anon = [
            sanitize_sql_identifier(c)
            for c in sensitive_columns
            if c in table_columns
        ]

        if not columns_to_anon:
            return 0

        # Build update query (columns already sanitized)
        set_clauses = [f"{col} = '[REDACTED]'" for col in columns_to_anon]
        cursor.execute(f"""
            UPDATE {safe_table}
            SET {', '.join(set_clauses)}
            WHERE {safe_timestamp_col} < ?
        """, (cutoff_date,))
        conn.commit()

        return cursor.rowcount

    async def _process_file_pattern_policy(self, policy: RetentionPolicy) -> RetentionStats:
        """Process a file pattern retention policy."""
        pattern_parts = policy.table_or_path.split("/")
        if len(pattern_parts) > 1:
            base_path = self.db_path / "/".join(pattern_parts[:-1])
            pattern = pattern_parts[-1]
        else:
            base_path = self.db_path
            pattern = pattern_parts[0]

        if not base_path.exists():
            return RetentionStats(
                policy_name=policy.name,
                records_processed=0,
                records_deleted=0,
                records_archived=0,
                bytes_freed=0,
                duration_seconds=0,
                timestamp=""
            )

        cutoff_time = datetime.now(timezone.utc) - timedelta(days=policy.retention_days)
        files_processed = 0
        bytes_freed = 0

        for file_path in base_path.glob(pattern):
            if not file_path.is_file():
                continue

            mtime = datetime.fromtimestamp(file_path.stat().st_mtime, tz=timezone.utc)
            if mtime < cutoff_time:
                file_size = file_path.stat().st_size

                if policy.action == RetentionAction.DELETE:
                    file_path.unlink()
                elif policy.action == RetentionAction.ARCHIVE:
                    archive_path = self._get_archive_path(policy, file_path.name)
                    shutil.move(str(file_path), str(archive_path))

                files_processed += 1
                bytes_freed += file_size

        return RetentionStats(
            policy_name=policy.name,
            records_processed=files_processed,
            records_deleted=files_processed if policy.action == RetentionAction.DELETE else 0,
            records_archived=files_processed if policy.action == RetentionAction.ARCHIVE else 0,
            bytes_freed=bytes_freed,
            duration_seconds=0,
            timestamp=""
        )

    async def _process_file_policy(self, policy: RetentionPolicy) -> RetentionStats:
        """Process a single file retention policy."""
        file_path = self.db_path / policy.table_or_path

        if not file_path.exists():
            return RetentionStats(
                policy_name=policy.name,
                records_processed=0,
                records_deleted=0,
                records_archived=0,
                bytes_freed=0,
                duration_seconds=0,
                timestamp=""
            )

        file_size = file_path.stat().st_size
        mtime = datetime.fromtimestamp(file_path.stat().st_mtime, tz=timezone.utc)
        cutoff_time = datetime.now(timezone.utc) - timedelta(days=policy.retention_days)

        if mtime >= cutoff_time:
            # File is not old enough, but might need line-level processing
            if file_path.suffix == '.log':
                return await self._process_log_file(policy, file_path)

        # Process entire file
        if policy.action == RetentionAction.DELETE:
            file_path.unlink()
        elif policy.action == RetentionAction.ARCHIVE:
            archive_path = self._get_archive_path(policy, file_path.name)
            with open(file_path, 'rb') as f_in:
                with gzip.open(f"{archive_path}.gz", 'wb') as f_out:
                    shutil.copyfileobj(f_in, f_out)
            file_path.unlink()

        return RetentionStats(
            policy_name=policy.name,
            records_processed=1,
            records_deleted=1 if policy.action == RetentionAction.DELETE else 0,
            records_archived=1 if policy.action == RetentionAction.ARCHIVE else 0,
            bytes_freed=file_size,
            duration_seconds=0,
            timestamp=""
        )

    async def _process_log_file(self, policy: RetentionPolicy, file_path: Path) -> RetentionStats:
        """Process a log file line by line."""
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=policy.retention_days)
        lines_kept = []
        lines_removed = 0
        original_size = file_path.stat().st_size

        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            for line in f:
                # Try to parse timestamp from beginning of line
                try:
                    # Common log format: 2024-01-15 10:30:00 | ...
                    timestamp_str = line[:19]
                    line_time = datetime.fromisoformat(timestamp_str)
                    if line_time.tzinfo is None:
                        line_time = line_time.replace(tzinfo=timezone.utc)

                    if line_time >= cutoff_date:
                        lines_kept.append(line)
                    else:
                        lines_removed += 1
                except (ValueError, IndexError):
                    # Can't parse timestamp, keep the line
                    lines_kept.append(line)

        # Rewrite file with kept lines
        with open(file_path, 'w', encoding='utf-8') as f:
            f.writelines(lines_kept)

        new_size = file_path.stat().st_size

        return RetentionStats(
            policy_name=policy.name,
            records_processed=lines_removed + len(lines_kept),
            records_deleted=lines_removed,
            records_archived=0,
            bytes_freed=original_size - new_size,
            duration_seconds=0,
            timestamp=""
        )

    def _get_archive_path(self, policy: RetentionPolicy, filename: str) -> Path:
        """Get archive path for a file."""
        archive_dir = policy.archive_path or self.archive_dir
        archive_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        return archive_dir / f"{filename}_{timestamp}"

    async def run_all_policies(self) -> List[RetentionStats]:
        """Run all enabled retention policies."""
        logger.info("Running all retention policies...")
        results = []

        for policy_name in self.policies:
            stats = await self.run_policy(policy_name)
            if stats:
                results.append(stats)

        total_freed = sum(s.bytes_freed for s in results)
        logger.info(f"Retention complete: freed {total_freed / 1024 / 1024:.2f} MB total")

        return results

    def get_stats(self, days: int = 30) -> List[RetentionStats]:
        """Get recent retention stats."""
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        return [
            s for s in self._stats
            if datetime.fromisoformat(s.timestamp) > cutoff
        ]

    def get_policy_status(self) -> Dict[str, Dict]:
        """Get status of all policies."""
        return {
            name: {
                'enabled': p.is_enabled,
                'retention_days': p.retention_days,
                'action': p.action.value,
                'last_run': p.last_run,
                'records_affected': p.records_affected
            }
            for name, p in self.policies.items()
        }


# Background scheduler
async def retention_scheduler(manager: RetentionManager, interval_hours: int = 24):
    """Run retention policies on a schedule."""
    while True:
        try:
            await manager.run_all_policies()
        except Exception as e:
            logger.error(f"Retention scheduler error: {e}")

        await asyncio.sleep(interval_hours * 3600)


# Singleton
_manager: Optional[RetentionManager] = None

def get_retention_manager() -> RetentionManager:
    """Get singleton retention manager."""
    global _manager
    if _manager is None:
        _manager = RetentionManager()
    return _manager
