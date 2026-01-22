"""
Tool Call Log - Persistent storage for tool call replay.

Stores all tool calls with their inputs and outputs so they can be:
1. Audited
2. Replayed for debugging
3. Used for cost tracking
4. Analyzed for patterns

Usage:
    from core.tools.replay import get_call_log

    call_log = get_call_log()

    # Log a call
    await call_log.log_call(tool_call)
    await call_log.log_result(tool_result)

    # Query calls
    calls = await call_log.get_calls_for_session(session_id)
    call = await call_log.get_call(call_id)

    # Replay
    original = await call_log.get_call(call_id)
    # Re-execute with same inputs...
"""

import json
import logging
import sqlite3
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from .contract import ToolCall, ToolResult

logger = logging.getLogger(__name__)

# Singleton instance
_call_log: Optional["ToolCallLog"] = None


class ToolCallLog:
    """
    Persistent storage for tool calls.

    Stores all tool calls in SQLite for:
    - Audit trail
    - Replay capability
    - Cost analysis
    - Pattern detection
    """

    def __init__(self, db_path: Optional[str] = None):
        if db_path:
            self.db_path = Path(db_path)
        else:
            # Default to ~/.lifeos/tools/call_log.db
            self.db_path = Path.home() / ".lifeos" / "tools" / "call_log.db"

        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._init_db()

    def _init_db(self) -> None:
        """Initialize the database schema."""
        with self._lock:
            conn = sqlite3.connect(str(self.db_path))
            try:
                cursor = conn.cursor()

                # Tool calls table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS tool_calls (
                        id TEXT PRIMARY KEY,
                        tool_name TEXT NOT NULL,
                        inputs_json TEXT,
                        caller_id TEXT,
                        caller_component TEXT,
                        session_id TEXT,
                        created_at TEXT NOT NULL,

                        -- Result fields (populated after execution)
                        success INTEGER,
                        outputs_json TEXT,
                        error TEXT,
                        error_type TEXT,
                        started_at TEXT,
                        completed_at TEXT,
                        duration_ms REAL,
                        actual_cost REAL
                    )
                """)

                # Index for session queries
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_calls_session
                    ON tool_calls(session_id, created_at)
                """)

                # Index for tool queries
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_calls_tool
                    ON tool_calls(tool_name, created_at)
                """)

                # Index for caller queries
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_calls_caller
                    ON tool_calls(caller_component, created_at)
                """)

                # Index for date queries
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_calls_date
                    ON tool_calls(created_at)
                """)

                conn.commit()
            finally:
                conn.close()

    def _get_conn(self) -> sqlite3.Connection:
        """Get a database connection."""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    async def log_call(self, call: ToolCall) -> None:
        """Log a tool call (before execution)."""
        with self._lock:
            conn = self._get_conn()
            try:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO tool_calls (
                        id, tool_name, inputs_json, caller_id,
                        caller_component, session_id, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    call.id,
                    call.tool_name,
                    json.dumps(call.inputs),
                    call.caller_id,
                    call.caller_component,
                    call.session_id,
                    call.created_at.isoformat(),
                ))
                conn.commit()
                logger.debug(f"Logged tool call: {call.id} ({call.tool_name})")
            finally:
                conn.close()

    async def log_result(self, result: ToolResult) -> None:
        """Log a tool result (after execution)."""
        with self._lock:
            conn = self._get_conn()
            try:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE tool_calls SET
                        success = ?,
                        outputs_json = ?,
                        error = ?,
                        error_type = ?,
                        started_at = ?,
                        completed_at = ?,
                        duration_ms = ?,
                        actual_cost = ?
                    WHERE id = ?
                """, (
                    1 if result.success else 0,
                    json.dumps(result.outputs) if result.outputs else None,
                    result.error,
                    result.error_type,
                    result.started_at.isoformat() if result.started_at else None,
                    result.completed_at.isoformat() if result.completed_at else None,
                    result.duration_ms,
                    result.actual_cost,
                    result.call_id,
                ))
                conn.commit()
                logger.debug(f"Logged tool result: {result.call_id} (success={result.success})")
            finally:
                conn.close()

    async def get_call(self, call_id: str) -> Optional[ToolCall]:
        """Get a tool call by ID."""
        with self._lock:
            conn = self._get_conn()
            try:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM tool_calls WHERE id = ?", (call_id,))
                row = cursor.fetchone()
                if not row:
                    return None
                return self._row_to_call(row)
            finally:
                conn.close()

    async def get_result(self, call_id: str) -> Optional[ToolResult]:
        """Get a tool result by call ID."""
        with self._lock:
            conn = self._get_conn()
            try:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM tool_calls WHERE id = ?", (call_id,))
                row = cursor.fetchone()
                if not row or row["success"] is None:
                    return None
                return self._row_to_result(row)
            finally:
                conn.close()

    def _row_to_call(self, row: sqlite3.Row) -> ToolCall:
        """Convert a database row to a ToolCall object."""
        inputs = json.loads(row["inputs_json"]) if row["inputs_json"] else {}

        return ToolCall(
            id=row["id"],
            tool_name=row["tool_name"],
            inputs=inputs,
            caller_id=row["caller_id"],
            caller_component=row["caller_component"],
            session_id=row["session_id"],
            created_at=datetime.fromisoformat(row["created_at"]),
        )

    def _row_to_result(self, row: sqlite3.Row) -> ToolResult:
        """Convert a database row to a ToolResult object."""
        outputs = json.loads(row["outputs_json"]) if row["outputs_json"] else None

        return ToolResult(
            call_id=row["id"],
            success=bool(row["success"]),
            outputs=outputs,
            error=row["error"],
            error_type=row["error_type"],
            started_at=datetime.fromisoformat(row["started_at"]) if row["started_at"] else None,
            completed_at=datetime.fromisoformat(row["completed_at"]) if row["completed_at"] else None,
            duration_ms=row["duration_ms"] or 0.0,
            actual_cost=row["actual_cost"] or 0.0,
        )

    async def get_calls_for_session(
        self,
        session_id: str,
        limit: int = 100,
    ) -> List[ToolCall]:
        """Get all tool calls for a session."""
        with self._lock:
            conn = self._get_conn()
            try:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT * FROM tool_calls
                    WHERE session_id = ?
                    ORDER BY created_at DESC
                    LIMIT ?
                """, (session_id, limit))
                return [self._row_to_call(row) for row in cursor.fetchall()]
            finally:
                conn.close()

    async def get_calls_for_tool(
        self,
        tool_name: str,
        limit: int = 100,
    ) -> List[ToolCall]:
        """Get recent calls for a specific tool."""
        with self._lock:
            conn = self._get_conn()
            try:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT * FROM tool_calls
                    WHERE tool_name = ?
                    ORDER BY created_at DESC
                    LIMIT ?
                """, (tool_name, limit))
                return [self._row_to_call(row) for row in cursor.fetchall()]
            finally:
                conn.close()

    async def get_calls_for_component(
        self,
        component: str,
        limit: int = 100,
    ) -> List[ToolCall]:
        """Get recent calls from a specific component."""
        with self._lock:
            conn = self._get_conn()
            try:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT * FROM tool_calls
                    WHERE caller_component = ?
                    ORDER BY created_at DESC
                    LIMIT ?
                """, (component, limit))
                return [self._row_to_call(row) for row in cursor.fetchall()]
            finally:
                conn.close()

    async def get_recent_calls(
        self,
        hours: int = 24,
        limit: int = 500,
    ) -> List[ToolCall]:
        """Get recent tool calls."""
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        with self._lock:
            conn = self._get_conn()
            try:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT * FROM tool_calls
                    WHERE created_at > ?
                    ORDER BY created_at DESC
                    LIMIT ?
                """, (cutoff.isoformat(), limit))
                return [self._row_to_call(row) for row in cursor.fetchall()]
            finally:
                conn.close()

    async def get_failed_calls(
        self,
        hours: int = 24,
        limit: int = 100,
    ) -> List[ToolCall]:
        """Get recent failed tool calls."""
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        with self._lock:
            conn = self._get_conn()
            try:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT * FROM tool_calls
                    WHERE created_at > ?
                    AND success = 0
                    ORDER BY created_at DESC
                    LIMIT ?
                """, (cutoff.isoformat(), limit))
                return [self._row_to_call(row) for row in cursor.fetchall()]
            finally:
                conn.close()

    async def get_stats(
        self,
        hours: int = 24,
    ) -> Dict[str, Any]:
        """Get call statistics."""
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        with self._lock:
            conn = self._get_conn()
            try:
                cursor = conn.cursor()

                # Total calls
                cursor.execute("""
                    SELECT COUNT(*) as count FROM tool_calls
                    WHERE created_at > ?
                """, (cutoff.isoformat(),))
                total = cursor.fetchone()["count"]

                # Success/failure counts
                cursor.execute("""
                    SELECT success, COUNT(*) as count FROM tool_calls
                    WHERE created_at > ?
                    GROUP BY success
                """, (cutoff.isoformat(),))
                success_counts = {
                    row["success"]: row["count"]
                    for row in cursor.fetchall()
                }

                # By tool
                cursor.execute("""
                    SELECT tool_name, COUNT(*) as count FROM tool_calls
                    WHERE created_at > ?
                    GROUP BY tool_name
                    ORDER BY count DESC
                    LIMIT 10
                """, (cutoff.isoformat(),))
                by_tool = {
                    row["tool_name"]: row["count"]
                    for row in cursor.fetchall()
                }

                # Total cost
                cursor.execute("""
                    SELECT SUM(actual_cost) as total FROM tool_calls
                    WHERE created_at > ?
                """, (cutoff.isoformat(),))
                row = cursor.fetchone()
                total_cost = row["total"] if row["total"] else 0.0

                # Average duration
                cursor.execute("""
                    SELECT AVG(duration_ms) as avg FROM tool_calls
                    WHERE created_at > ?
                    AND duration_ms IS NOT NULL
                """, (cutoff.isoformat(),))
                row = cursor.fetchone()
                avg_duration = row["avg"] if row["avg"] else 0.0

                return {
                    "period_hours": hours,
                    "total_calls": total,
                    "successful": success_counts.get(1, 0),
                    "failed": success_counts.get(0, 0),
                    "success_rate": success_counts.get(1, 0) / total if total > 0 else 0,
                    "by_tool": by_tool,
                    "total_cost": total_cost,
                    "avg_duration_ms": avg_duration,
                }
            finally:
                conn.close()

    async def find_similar_calls(
        self,
        tool_name: str,
        inputs: Dict[str, Any],
        limit: int = 5,
    ) -> List[ToolCall]:
        """
        Find similar past calls for potential replay or caching.

        This is a basic implementation - could be enhanced with
        more sophisticated similarity matching.
        """
        # For now, just find calls with same tool and same input keys
        with self._lock:
            conn = self._get_conn()
            try:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT * FROM tool_calls
                    WHERE tool_name = ?
                    AND success = 1
                    ORDER BY created_at DESC
                    LIMIT ?
                """, (tool_name, limit * 2))

                # Filter for matching input structure
                results = []
                for row in cursor.fetchall():
                    call = self._row_to_call(row)
                    if set(call.inputs.keys()) == set(inputs.keys()):
                        results.append(call)
                        if len(results) >= limit:
                            break

                return results
            finally:
                conn.close()

    async def cleanup_old_calls(self, days: int = 30) -> int:
        """Clean up calls older than specified days."""
        cutoff = datetime.utcnow() - timedelta(days=days)
        with self._lock:
            conn = self._get_conn()
            try:
                cursor = conn.cursor()
                cursor.execute("""
                    DELETE FROM tool_calls
                    WHERE created_at < ?
                """, (cutoff.isoformat(),))
                deleted = cursor.rowcount
                conn.commit()
                logger.info(f"Cleaned up {deleted} old tool calls")
                return deleted
            finally:
                conn.close()


def get_call_log() -> ToolCallLog:
    """Get or create the singleton tool call log."""
    global _call_log
    if _call_log is None:
        _call_log = ToolCallLog()
    return _call_log
