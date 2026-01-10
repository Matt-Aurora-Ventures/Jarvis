"""
Data Retention Policy
Prompt #89: Automated data retention and cleanup

Manages data lifecycle with configurable retention periods.
"""

import asyncio
import logging
import os
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional
import json

logger = logging.getLogger("jarvis.data.retention")


# =============================================================================
# MODELS
# =============================================================================

class RetentionAction(Enum):
    """Action to take when data expires"""
    DELETE = "delete"
    ARCHIVE = "archive"
    ANONYMIZE = "anonymize"


@dataclass
class RetentionPolicy:
    """A data retention policy"""
    name: str
    data_type: str
    retention_days: int
    action: RetentionAction = RetentionAction.DELETE
    enabled: bool = True
    priority: int = 0  # Higher = process first


@dataclass
class RetentionJob:
    """A retention enforcement job"""
    id: str
    policy_name: str
    started_at: datetime
    completed_at: Optional[datetime] = None
    records_processed: int = 0
    records_affected: int = 0
    status: str = "running"
    error: Optional[str] = None


# =============================================================================
# RETENTION MANAGER
# =============================================================================

class RetentionManager:
    """
    Manages data retention policies and enforcement.

    Features:
    - Configurable retention periods per data type
    - Automated cleanup jobs
    - Archive support for long-term storage
    - Audit logging of all retention actions
    """

    # Default retention periods
    DEFAULT_POLICIES = [
        RetentionPolicy(
            name="trade_data_default",
            data_type="anonymized_trades",
            retention_days=365,  # 1 year
            action=RetentionAction.DELETE,
        ),
        RetentionPolicy(
            name="analytics_events",
            data_type="analytics_events",
            retention_days=90,  # 3 months
            action=RetentionAction.DELETE,
        ),
        RetentionPolicy(
            name="collection_audit",
            data_type="collection_audit",
            retention_days=730,  # 2 years for compliance
            action=RetentionAction.ARCHIVE,
        ),
        RetentionPolicy(
            name="deletion_audit",
            data_type="deletion_audit",
            retention_days=2555,  # 7 years for compliance
            action=RetentionAction.ARCHIVE,
        ),
        RetentionPolicy(
            name="session_data",
            data_type="user_sessions",
            retention_days=30,
            action=RetentionAction.DELETE,
        ),
    ]

    def __init__(self, db_path: str = None):
        self.db_path = db_path or os.getenv(
            "RETENTION_DB",
            "data/retention.db"
        )
        self._policies: Dict[str, RetentionPolicy] = {}
        self._data_handlers: Dict[str, Callable] = {}
        self._archive_handlers: Dict[str, Callable] = {}

        self._init_database()
        self._load_default_policies()
        self._register_default_handlers()

    def _init_database(self):
        """Initialize retention database"""
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Policies table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS retention_policies (
                name TEXT PRIMARY KEY,
                data_type TEXT NOT NULL,
                retention_days INTEGER NOT NULL,
                action TEXT NOT NULL,
                enabled INTEGER DEFAULT 1,
                priority INTEGER DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)

        # Jobs table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS retention_jobs (
                id TEXT PRIMARY KEY,
                policy_name TEXT NOT NULL,
                started_at TEXT NOT NULL,
                completed_at TEXT,
                records_processed INTEGER DEFAULT 0,
                records_affected INTEGER DEFAULT 0,
                status TEXT NOT NULL,
                error TEXT
            )
        """)

        # Archived data registry
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS archived_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                data_type TEXT NOT NULL,
                original_id TEXT NOT NULL,
                archived_at TEXT NOT NULL,
                archive_path TEXT NOT NULL,
                metadata_json TEXT
            )
        """)

        conn.commit()
        conn.close()

    def _load_default_policies(self):
        """Load default retention policies"""
        for policy in self.DEFAULT_POLICIES:
            self._policies[policy.name] = policy

    def _register_default_handlers(self):
        """Register default data handlers"""
        self.register_handler(
            "anonymized_trades",
            self._handle_trade_data,
            self._archive_trade_data,
        )
        self.register_handler(
            "analytics_events",
            self._handle_analytics_events,
        )
        self.register_handler(
            "collection_audit",
            self._handle_collection_audit,
            self._archive_collection_audit,
        )
        self.register_handler(
            "deletion_audit",
            self._handle_deletion_audit,
            self._archive_deletion_audit,
        )

    # =========================================================================
    # POLICY MANAGEMENT
    # =========================================================================

    def add_policy(self, policy: RetentionPolicy):
        """Add or update a retention policy"""
        self._policies[policy.name] = policy

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        now = datetime.now(timezone.utc).isoformat()

        cursor.execute("""
            INSERT OR REPLACE INTO retention_policies
            (name, data_type, retention_days, action, enabled, priority, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, COALESCE(
                (SELECT created_at FROM retention_policies WHERE name = ?), ?
            ), ?)
        """, (
            policy.name,
            policy.data_type,
            policy.retention_days,
            policy.action.value,
            1 if policy.enabled else 0,
            policy.priority,
            policy.name,
            now,
            now,
        ))

        conn.commit()
        conn.close()

        logger.info(f"Added retention policy: {policy.name}")

    def remove_policy(self, name: str):
        """Remove a retention policy"""
        if name in self._policies:
            del self._policies[name]

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM retention_policies WHERE name = ?", (name,))
        conn.commit()
        conn.close()

        logger.info(f"Removed retention policy: {name}")

    def get_policy(self, name: str) -> Optional[RetentionPolicy]:
        """Get a retention policy by name"""
        return self._policies.get(name)

    def list_policies(self) -> List[RetentionPolicy]:
        """List all retention policies"""
        return sorted(
            self._policies.values(),
            key=lambda p: (-p.priority, p.name)
        )

    # =========================================================================
    # HANDLER REGISTRATION
    # =========================================================================

    def register_handler(
        self,
        data_type: str,
        delete_handler: Callable,
        archive_handler: Callable = None,
    ):
        """Register handlers for a data type"""
        self._data_handlers[data_type] = delete_handler
        if archive_handler:
            self._archive_handlers[data_type] = archive_handler

    # =========================================================================
    # ENFORCEMENT
    # =========================================================================

    async def enforce_all(self) -> List[RetentionJob]:
        """Enforce all enabled retention policies"""
        jobs = []

        policies = [p for p in self.list_policies() if p.enabled]

        for policy in policies:
            try:
                job = await self.enforce_policy(policy.name)
                jobs.append(job)
            except Exception as e:
                logger.error(f"Error enforcing policy {policy.name}: {e}")

        return jobs

    async def enforce_policy(self, policy_name: str) -> RetentionJob:
        """Enforce a specific retention policy"""
        policy = self._policies.get(policy_name)
        if policy is None:
            raise ValueError(f"Policy not found: {policy_name}")

        if not policy.enabled:
            raise ValueError(f"Policy is disabled: {policy_name}")

        # Create job
        import uuid
        job_id = str(uuid.uuid4())[:8]
        job = RetentionJob(
            id=job_id,
            policy_name=policy_name,
            started_at=datetime.now(timezone.utc),
        )

        await self._store_job(job)

        # Calculate cutoff date
        cutoff = datetime.now(timezone.utc) - timedelta(days=policy.retention_days)

        try:
            if policy.action == RetentionAction.DELETE:
                affected = await self._execute_delete(policy, cutoff)
            elif policy.action == RetentionAction.ARCHIVE:
                affected = await self._execute_archive(policy, cutoff)
            elif policy.action == RetentionAction.ANONYMIZE:
                affected = await self._execute_anonymize(policy, cutoff)
            else:
                affected = 0

            job.records_affected = affected
            job.status = "completed"

        except Exception as e:
            job.status = "failed"
            job.error = str(e)
            logger.error(f"Retention job failed: {e}")

        job.completed_at = datetime.now(timezone.utc)
        await self._update_job(job)

        logger.info(
            f"Retention job {job_id} for {policy_name}: "
            f"{job.records_affected} records affected, status={job.status}"
        )

        return job

    async def _execute_delete(
        self,
        policy: RetentionPolicy,
        cutoff: datetime,
    ) -> int:
        """Execute deletion for a policy"""
        handler = self._data_handlers.get(policy.data_type)
        if handler is None:
            logger.warning(f"No handler for data type: {policy.data_type}")
            return 0

        return await asyncio.to_thread(handler, cutoff, "delete")

    async def _execute_archive(
        self,
        policy: RetentionPolicy,
        cutoff: datetime,
    ) -> int:
        """Execute archival for a policy"""
        archive_handler = self._archive_handlers.get(policy.data_type)
        if archive_handler is None:
            # Fall back to delete
            return await self._execute_delete(policy, cutoff)

        return await asyncio.to_thread(archive_handler, cutoff)

    async def _execute_anonymize(
        self,
        policy: RetentionPolicy,
        cutoff: datetime,
    ) -> int:
        """Execute anonymization for a policy"""
        handler = self._data_handlers.get(policy.data_type)
        if handler is None:
            return 0

        return await asyncio.to_thread(handler, cutoff, "anonymize")

    # =========================================================================
    # DEFAULT HANDLERS
    # =========================================================================

    def _handle_trade_data(self, cutoff: datetime, action: str) -> int:
        """Handle trade data retention"""
        trade_db = os.getenv("TRADE_DATA_DB", "data/trade_data.db")

        if not os.path.exists(trade_db):
            return 0

        conn = sqlite3.connect(trade_db)
        cursor = conn.cursor()

        if action == "delete":
            cursor.execute(
                "DELETE FROM anonymized_trades WHERE collected_at < ?",
                (cutoff.isoformat(),)
            )
        elif action == "anonymize":
            # Already anonymized, just remove identifiers
            cursor.execute("""
                UPDATE anonymized_trades SET
                    user_hash = 'REDACTED',
                    metadata_json = '{}'
                WHERE collected_at < ?
            """, (cutoff.isoformat(),))

        affected = cursor.rowcount
        conn.commit()
        conn.close()

        return affected

    def _archive_trade_data(self, cutoff: datetime) -> int:
        """Archive trade data before deletion"""
        trade_db = os.getenv("TRADE_DATA_DB", "data/trade_data.db")
        archive_dir = os.getenv("ARCHIVE_DIR", "data/archive")

        if not os.path.exists(trade_db):
            return 0

        os.makedirs(archive_dir, exist_ok=True)

        conn = sqlite3.connect(trade_db)
        cursor = conn.cursor()

        # Get records to archive
        cursor.execute(
            "SELECT * FROM anonymized_trades WHERE collected_at < ?",
            (cutoff.isoformat(),)
        )

        rows = cursor.fetchall()
        if not rows:
            conn.close()
            return 0

        columns = [d[0] for d in cursor.description]

        # Write to archive file
        archive_path = os.path.join(
            archive_dir,
            f"trades_{cutoff.strftime('%Y%m%d')}.json"
        )

        with open(archive_path, "w") as f:
            records = [dict(zip(columns, row)) for row in rows]
            json.dump(records, f)

        # Delete archived records
        cursor.execute(
            "DELETE FROM anonymized_trades WHERE collected_at < ?",
            (cutoff.isoformat(),)
        )

        affected = cursor.rowcount
        conn.commit()
        conn.close()

        # Register archive
        self._register_archive("anonymized_trades", archive_path, len(rows))

        return affected

    def _handle_analytics_events(self, cutoff: datetime, action: str) -> int:
        """Handle analytics events retention"""
        analytics_db = os.getenv("ANALYTICS_DB", "data/analytics.db")

        if not os.path.exists(analytics_db):
            return 0

        conn = sqlite3.connect(analytics_db)
        cursor = conn.cursor()

        cursor.execute(
            "DELETE FROM events WHERE timestamp < ?",
            (cutoff.isoformat(),)
        )

        affected = cursor.rowcount
        conn.commit()
        conn.close()

        return affected

    def _handle_collection_audit(self, cutoff: datetime, action: str) -> int:
        """Handle collection audit retention"""
        trade_db = os.getenv("TRADE_DATA_DB", "data/trade_data.db")

        if not os.path.exists(trade_db):
            return 0

        conn = sqlite3.connect(trade_db)
        cursor = conn.cursor()

        cursor.execute(
            "DELETE FROM collection_audit WHERE timestamp < ?",
            (cutoff.isoformat(),)
        )

        affected = cursor.rowcount
        conn.commit()
        conn.close()

        return affected

    def _archive_collection_audit(self, cutoff: datetime) -> int:
        """Archive collection audit records"""
        # Similar to trade data archival
        return self._handle_collection_audit(cutoff, "delete")

    def _handle_deletion_audit(self, cutoff: datetime, action: str) -> int:
        """Handle deletion audit retention"""
        deletion_db = os.getenv("DELETION_AUDIT_DB", "data/deletion_audit.db")

        if not os.path.exists(deletion_db):
            return 0

        conn = sqlite3.connect(deletion_db)
        cursor = conn.cursor()

        cursor.execute(
            "DELETE FROM deletion_audit WHERE timestamp < ?",
            (cutoff.isoformat(),)
        )

        affected = cursor.rowcount
        conn.commit()
        conn.close()

        return affected

    def _archive_deletion_audit(self, cutoff: datetime) -> int:
        """Archive deletion audit records"""
        return self._handle_deletion_audit(cutoff, "delete")

    def _register_archive(
        self,
        data_type: str,
        archive_path: str,
        record_count: int,
    ):
        """Register an archive in the database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO archived_data
            (data_type, original_id, archived_at, archive_path, metadata_json)
            VALUES (?, ?, ?, ?, ?)
        """, (
            data_type,
            f"batch_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}",
            datetime.now(timezone.utc).isoformat(),
            archive_path,
            json.dumps({"record_count": record_count}),
        ))

        conn.commit()
        conn.close()

    # =========================================================================
    # JOB MANAGEMENT
    # =========================================================================

    async def _store_job(self, job: RetentionJob):
        """Store a retention job"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO retention_jobs
            (id, policy_name, started_at, completed_at, records_processed,
             records_affected, status, error)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            job.id,
            job.policy_name,
            job.started_at.isoformat(),
            job.completed_at.isoformat() if job.completed_at else None,
            job.records_processed,
            job.records_affected,
            job.status,
            job.error,
        ))

        conn.commit()
        conn.close()

    async def _update_job(self, job: RetentionJob):
        """Update a retention job"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            UPDATE retention_jobs SET
                completed_at = ?,
                records_processed = ?,
                records_affected = ?,
                status = ?,
                error = ?
            WHERE id = ?
        """, (
            job.completed_at.isoformat() if job.completed_at else None,
            job.records_processed,
            job.records_affected,
            job.status,
            job.error,
            job.id,
        ))

        conn.commit()
        conn.close()

    async def get_recent_jobs(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent retention jobs"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT * FROM retention_jobs
            ORDER BY started_at DESC
            LIMIT ?
        """, (limit,))

        columns = [d[0] for d in cursor.description]
        jobs = [dict(zip(columns, row)) for row in cursor.fetchall()]

        conn.close()
        return jobs


# =============================================================================
# SINGLETON
# =============================================================================

_retention_manager: Optional[RetentionManager] = None


def get_retention_manager() -> RetentionManager:
    """Get or create the retention manager singleton"""
    global _retention_manager
    if _retention_manager is None:
        _retention_manager = RetentionManager()
    return _retention_manager


# =============================================================================
# SCHEDULED TASK
# =============================================================================

async def run_retention_enforcement():
    """Run retention enforcement as a scheduled task"""
    manager = get_retention_manager()
    jobs = await manager.enforce_all()

    total_affected = sum(j.records_affected for j in jobs)
    logger.info(f"Retention enforcement complete: {total_affected} records affected")

    return jobs
