"""
Run Ledger - Persistent storage for durable runs.

The ledger stores run state in SQLite so operations can:
1. Survive crashes
2. Resume from the last successful step
3. Be audited

On startup, the system checks for incomplete runs and either:
- Resumes them if safe
- Aborts them cleanly
- Escalates them for human review
"""

import asyncio
import json
import logging
import sqlite3
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any

from .models import Run, RunState, RunStep, StepState

logger = logging.getLogger(__name__)

# Singleton instance
_run_ledger: Optional["RunLedger"] = None


class RunLedger:
    """
    Persistent run ledger for durable operations.

    Stores run state in SQLite and provides methods for:
    - Creating and managing runs
    - Tracking step progress
    - Recovering from crashes
    - Querying run history
    """

    def __init__(self, db_path: Optional[str] = None):
        if db_path:
            self.db_path = Path(db_path)
        else:
            # Default to ~/.lifeos/runs/ledger.db
            self.db_path = Path.home() / ".lifeos" / "runs" / "ledger.db"

        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._init_db()

    def _init_db(self) -> None:
        """Initialize the database schema."""
        with self._lock:
            conn = sqlite3.connect(str(self.db_path))
            try:
                cursor = conn.cursor()

                # Runs table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS runs (
                        id TEXT PRIMARY KEY,
                        platform TEXT NOT NULL,
                        intent TEXT NOT NULL,
                        state TEXT NOT NULL,
                        steps_json TEXT,
                        current_step_index INTEGER DEFAULT 0,
                        created_at TEXT NOT NULL,
                        started_at TEXT,
                        completed_at TEXT,
                        metadata_json TEXT,
                        error TEXT,
                        recovery_count INTEGER DEFAULT 0,
                        last_recovery_at TEXT
                    )
                """)

                # Index for querying incomplete runs
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_runs_state
                    ON runs(state, platform)
                """)

                # Index for recent runs
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_runs_created
                    ON runs(created_at)
                """)

                conn.commit()
            finally:
                conn.close()

    def _get_conn(self) -> sqlite3.Connection:
        """Get a database connection."""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    async def start_run(
        self,
        platform: str,
        intent: str,
        steps: List[str],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Run:
        """
        Start a new durable run.

        Args:
            platform: The platform/component (e.g., "telegram", "x_bot")
            intent: What the run is doing (e.g., "send_broadcast")
            steps: List of step names in order
            metadata: Additional metadata to store

        Returns:
            The created Run object
        """
        run = Run.create(platform, intent, steps, metadata)
        run.state = RunState.RUNNING
        run.started_at = datetime.utcnow()
        run.steps[0].state = StepState.RUNNING
        run.steps[0].started_at = datetime.utcnow()

        await self._save_run(run)
        logger.info(f"Started run: {run.summary()}")
        return run

    async def _save_run(self, run: Run) -> None:
        """Save a run to the database."""
        with self._lock:
            conn = self._get_conn()
            try:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT OR REPLACE INTO runs (
                        id, platform, intent, state, steps_json, current_step_index,
                        created_at, started_at, completed_at, metadata_json, error,
                        recovery_count, last_recovery_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    run.id,
                    run.platform,
                    run.intent,
                    run.state.value,
                    json.dumps([s.to_dict() for s in run.steps]),
                    run.current_step_index,
                    run.created_at.isoformat(),
                    run.started_at.isoformat() if run.started_at else None,
                    run.completed_at.isoformat() if run.completed_at else None,
                    json.dumps(run.metadata),
                    run.error,
                    run.recovery_count,
                    run.last_recovery_at.isoformat() if run.last_recovery_at else None,
                ))
                conn.commit()
            finally:
                conn.close()

    async def get_run(self, run_id: str) -> Optional[Run]:
        """Get a run by ID."""
        with self._lock:
            conn = self._get_conn()
            try:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM runs WHERE id = ?", (run_id,))
                row = cursor.fetchone()
                if not row:
                    return None
                return self._row_to_run(row)
            finally:
                conn.close()

    def _row_to_run(self, row: sqlite3.Row) -> Run:
        """Convert a database row to a Run object."""
        steps_data = json.loads(row["steps_json"]) if row["steps_json"] else []
        metadata = json.loads(row["metadata_json"]) if row["metadata_json"] else {}

        return Run(
            id=row["id"],
            platform=row["platform"],
            intent=row["intent"],
            state=RunState(row["state"]),
            steps=[RunStep.from_dict(s) for s in steps_data],
            current_step_index=row["current_step_index"],
            created_at=datetime.fromisoformat(row["created_at"]),
            started_at=datetime.fromisoformat(row["started_at"]) if row["started_at"] else None,
            completed_at=datetime.fromisoformat(row["completed_at"]) if row["completed_at"] else None,
            metadata=metadata,
            error=row["error"],
            recovery_count=row["recovery_count"],
            last_recovery_at=datetime.fromisoformat(row["last_recovery_at"]) if row["last_recovery_at"] else None,
        )

    async def complete_step(
        self,
        run_id: str,
        step_name: str,
        result: Any = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[Run]:
        """
        Mark a step as completed and advance to the next step.

        Args:
            run_id: The run ID
            step_name: The step to complete
            result: Optional result to store
            metadata: Optional metadata to add to the step

        Returns:
            Updated Run object, or None if not found
        """
        run = await self.get_run(run_id)
        if not run:
            return None

        # Find and complete the step
        for i, step in enumerate(run.steps):
            if step.name == step_name:
                step.state = StepState.COMPLETED
                step.completed_at = datetime.utcnow()
                step.result = result
                if metadata:
                    step.metadata.update(metadata)

                # Advance to next step
                if i + 1 < len(run.steps):
                    run.current_step_index = i + 1
                    run.steps[i + 1].state = StepState.RUNNING
                    run.steps[i + 1].started_at = datetime.utcnow()
                else:
                    # All steps complete
                    run.state = RunState.COMPLETED
                    run.completed_at = datetime.utcnow()

                break

        await self._save_run(run)
        logger.info(f"Completed step '{step_name}' in run {run_id}")
        return run

    async def fail_step(
        self,
        run_id: str,
        step_name: str,
        error: str,
    ) -> Optional[Run]:
        """Mark a step as failed."""
        run = await self.get_run(run_id)
        if not run:
            return None

        for step in run.steps:
            if step.name == step_name:
                step.state = StepState.FAILED
                step.completed_at = datetime.utcnow()
                step.error = error
                break

        run.state = RunState.FAILED
        run.error = error
        run.completed_at = datetime.utcnow()

        await self._save_run(run)
        logger.error(f"Failed step '{step_name}' in run {run_id}: {error}")
        return run

    async def skip_step(
        self,
        run_id: str,
        step_name: str,
        reason: str = "",
    ) -> Optional[Run]:
        """Skip a step and advance to the next."""
        run = await self.get_run(run_id)
        if not run:
            return None

        for i, step in enumerate(run.steps):
            if step.name == step_name:
                step.state = StepState.SKIPPED
                step.completed_at = datetime.utcnow()
                step.metadata["skip_reason"] = reason

                if i + 1 < len(run.steps):
                    run.current_step_index = i + 1
                    run.steps[i + 1].state = StepState.RUNNING
                    run.steps[i + 1].started_at = datetime.utcnow()
                break

        await self._save_run(run)
        return run

    async def abort_run(self, run_id: str, reason: str = "") -> Optional[Run]:
        """Abort a run."""
        run = await self.get_run(run_id)
        if not run:
            return None

        run.state = RunState.ABORTED
        run.completed_at = datetime.utcnow()
        run.error = reason or "Manually aborted"

        await self._save_run(run)
        logger.warning(f"Aborted run {run_id}: {reason}")
        return run

    async def get_incomplete_runs(
        self,
        platform: Optional[str] = None,
    ) -> List[Run]:
        """
        Get all incomplete runs.

        These are runs that were interrupted (RUNNING, PAUSED, RECOVERING)
        and need to be resumed or aborted on restart.
        """
        with self._lock:
            conn = self._get_conn()
            try:
                cursor = conn.cursor()
                if platform:
                    cursor.execute("""
                        SELECT * FROM runs
                        WHERE state IN ('running', 'paused', 'recovering')
                        AND platform = ?
                        ORDER BY created_at DESC
                    """, (platform,))
                else:
                    cursor.execute("""
                        SELECT * FROM runs
                        WHERE state IN ('running', 'paused', 'recovering')
                        ORDER BY created_at DESC
                    """)
                return [self._row_to_run(row) for row in cursor.fetchall()]
            finally:
                conn.close()

    async def mark_for_recovery(self, run_id: str) -> Optional[Run]:
        """Mark a run for recovery (called on startup)."""
        run = await self.get_run(run_id)
        if not run:
            return None

        run.state = RunState.RECOVERING
        run.recovery_count += 1
        run.last_recovery_at = datetime.utcnow()

        await self._save_run(run)
        logger.info(f"Marked run {run_id} for recovery (attempt #{run.recovery_count})")
        return run

    async def get_recent_runs(
        self,
        platform: Optional[str] = None,
        limit: int = 50,
    ) -> List[Run]:
        """Get recent runs."""
        with self._lock:
            conn = self._get_conn()
            try:
                cursor = conn.cursor()
                if platform:
                    cursor.execute("""
                        SELECT * FROM runs
                        WHERE platform = ?
                        ORDER BY created_at DESC
                        LIMIT ?
                    """, (platform, limit))
                else:
                    cursor.execute("""
                        SELECT * FROM runs
                        ORDER BY created_at DESC
                        LIMIT ?
                    """, (limit,))
                return [self._row_to_run(row) for row in cursor.fetchall()]
            finally:
                conn.close()

    async def cleanup_old_runs(self, days: int = 30) -> int:
        """Clean up runs older than the specified days."""
        cutoff = datetime.utcnow() - timedelta(days=days)
        with self._lock:
            conn = self._get_conn()
            try:
                cursor = conn.cursor()
                cursor.execute("""
                    DELETE FROM runs
                    WHERE created_at < ?
                    AND state IN ('completed', 'failed', 'aborted')
                """, (cutoff.isoformat(),))
                deleted = cursor.rowcount
                conn.commit()
                return deleted
            finally:
                conn.close()

    async def get_stats(self) -> Dict[str, Any]:
        """Get ledger statistics."""
        with self._lock:
            conn = self._get_conn()
            try:
                cursor = conn.cursor()

                # Count by state
                cursor.execute("""
                    SELECT state, COUNT(*) as count
                    FROM runs
                    GROUP BY state
                """)
                by_state = {row["state"]: row["count"] for row in cursor.fetchall()}

                # Count by platform
                cursor.execute("""
                    SELECT platform, COUNT(*) as count
                    FROM runs
                    GROUP BY platform
                """)
                by_platform = {row["platform"]: row["count"] for row in cursor.fetchall()}

                # Total
                cursor.execute("SELECT COUNT(*) as count FROM runs")
                total = cursor.fetchone()["count"]

                return {
                    "total_runs": total,
                    "by_state": by_state,
                    "by_platform": by_platform,
                }
            finally:
                conn.close()


def get_run_ledger() -> RunLedger:
    """Get or create the singleton run ledger."""
    global _run_ledger
    if _run_ledger is None:
        _run_ledger = RunLedger()
    return _run_ledger
