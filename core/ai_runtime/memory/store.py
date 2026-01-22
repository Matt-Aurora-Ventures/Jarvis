"""
Agent Memory Store

SQLite-backed persistent memory with namespace isolation.
Integrates with the existing Self-Improving Core patterns.
"""
import sqlite3
import json
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime
from pathlib import Path
import threading

from ..exceptions import MemoryException
from ..constants import MAX_MEMORY_ENTRIES_PER_NAMESPACE

logger = logging.getLogger(__name__)


class MemoryStore:
    """
    Persistent memory store for AI agents.

    Features:
    - Namespace isolation (each agent has its own space)
    - Automatic pruning (oldest entries removed when limit hit)
    - Compression-friendly (stores summaries, not raw data)
    """

    def __init__(
        self, db_path: str, max_entries_per_namespace: int = MAX_MEMORY_ENTRIES_PER_NAMESPACE
    ):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.max_entries = max_entries_per_namespace
        self._local = threading.local()
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        """Get thread-local connection."""
        if not hasattr(self._local, "conn"):
            self._local.conn = sqlite3.connect(str(self.db_path))
        return self._local.conn

    def _init_db(self):
        """Initialize database schema."""
        try:
            conn = self._get_conn()
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS memories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    namespace TEXT NOT NULL,
                    key TEXT NOT NULL,
                    value TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    accessed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    access_count INTEGER DEFAULT 0,
                    UNIQUE(namespace, key)
                )
            """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_namespace ON memories(namespace)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_created ON memories(created_at)"
            )
            conn.commit()
            logger.debug(f"Memory store initialized at {self.db_path}")
        except Exception as e:
            logger.error(f"Failed to initialize memory store: {e}")
            raise MemoryException(f"Failed to initialize memory store: {e}")

    async def store(self, namespace: str, key: str, value: str) -> bool:
        """
        Store a memory.

        If namespace is at capacity, prunes oldest entries first.
        """
        try:
            conn = self._get_conn()

            # Check namespace size
            cursor = conn.execute(
                "SELECT COUNT(*) FROM memories WHERE namespace = ?", (namespace,)
            )
            count = cursor.fetchone()[0]

            # Prune if needed
            if count >= self.max_entries:
                conn.execute(
                    """
                    DELETE FROM memories WHERE id IN (
                        SELECT id FROM memories
                        WHERE namespace = ?
                        ORDER BY accessed_at ASC
                        LIMIT ?
                    )
                """,
                    (namespace, count - self.max_entries + 100),
                )

            # Insert or update
            conn.execute(
                """
                INSERT OR REPLACE INTO memories (namespace, key, value, created_at)
                VALUES (?, ?, ?, ?)
            """,
                (namespace, key, value, datetime.utcnow().isoformat()),
            )

            conn.commit()
            return True

        except Exception as e:
            logger.error(f"Memory store error: {e}")
            return False

    async def retrieve(self, namespace: str, key: str) -> Optional[str]:
        """Retrieve a specific memory."""
        try:
            conn = self._get_conn()
            cursor = conn.execute(
                "SELECT value FROM memories WHERE namespace = ? AND key = ?",
                (namespace, key),
            )
            row = cursor.fetchone()

            if row:
                # Update access tracking
                conn.execute(
                    """
                    UPDATE memories
                    SET accessed_at = ?, access_count = access_count + 1
                    WHERE namespace = ? AND key = ?
                """,
                    (datetime.utcnow().isoformat(), namespace, key),
                )
                conn.commit()
                return row[0]

            return None

        except Exception as e:
            logger.error(f"Memory retrieve error: {e}")
            return None

    async def search(
        self, namespace: str, limit: int = 10, since: Optional[datetime] = None
    ) -> List[Dict[str, Any]]:
        """Search memories in a namespace."""
        try:
            conn = self._get_conn()

            if since:
                cursor = conn.execute(
                    """
                    SELECT key, value, created_at, access_count
                    FROM memories
                    WHERE namespace = ? AND created_at > ?
                    ORDER BY created_at DESC
                    LIMIT ?
                """,
                    (namespace, since.isoformat(), limit),
                )
            else:
                cursor = conn.execute(
                    """
                    SELECT key, value, created_at, access_count
                    FROM memories
                    WHERE namespace = ?
                    ORDER BY created_at DESC
                    LIMIT ?
                """,
                    (namespace, limit),
                )

            return [
                {
                    "key": row[0],
                    "value": row[1],
                    "created_at": row[2],
                    "access_count": row[3],
                }
                for row in cursor.fetchall()
            ]

        except Exception as e:
            logger.error(f"Memory search error: {e}")
            return []

    async def get_namespace_stats(self, namespace: str) -> Dict[str, Any]:
        """Get statistics for a namespace."""
        try:
            conn = self._get_conn()
            cursor = conn.execute(
                """
                SELECT
                    COUNT(*) as count,
                    MIN(created_at) as oldest,
                    MAX(created_at) as newest,
                    SUM(access_count) as total_accesses
                FROM memories WHERE namespace = ?
            """,
                (namespace,),
            )
            row = cursor.fetchone()

            return {
                "count": row[0],
                "oldest": row[1],
                "newest": row[2],
                "total_accesses": row[3] or 0,
            }

        except Exception as e:
            logger.error(f"Memory stats error: {e}")
            return {}

    def close(self):
        """Close the database connection."""
        if hasattr(self._local, "conn"):
            self._local.conn.close()
