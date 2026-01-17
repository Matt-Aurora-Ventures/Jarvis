"""
Automated memory import system - syncs learnings from past sessions into unified context.

This module provides functionality to:
1. Query past session learnings from PostgreSQL
2. Extract actionable patterns (trading rules, bug fixes, architectural decisions)
3. Organize by topic for quick retrieval
4. Auto-index new learnings into SQLite for zero-latency access
"""

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Any
import sqlite3
import os

logger = logging.getLogger(__name__)


class MemoryImporter:
    """Automatically imports learnings from PostgreSQL to local SQLite."""

    def __init__(self, sqlite_db: str = None, postgres_url: str = None):
        """
        Initialize memory importer.

        Args:
            sqlite_db: Path to local SQLite database
            postgres_url: PostgreSQL connection string (from DATABASE_URL env var)
        """
        self.sqlite_db = sqlite_db or os.environ.get(
            "SQLITE_DB_PATH", "./data/jarvis.db"
        )
        self.postgres_url = postgres_url or os.environ.get("DATABASE_URL", "")
        self.jsonl_memory = Path("./data/memory/jarvis-memory.jsonl")

    def import_from_postgres(self, days_back: int = 30) -> dict:
        """
        Query PostgreSQL for recent learnings and import to SQLite.

        Args:
            days_back: Only import learnings from last N days

        Returns:
            Dict with import stats {imported: int, errors: int, topics: dict}
        """
        if not self.postgres_url or "postgresql://" not in self.postgres_url:
            logger.warning("PostgreSQL not configured, skipping import")
            return {"imported": 0, "errors": 0, "topics": {}}

        try:
            import psycopg2
            from psycopg2.extras import RealDictCursor
        except ImportError:
            logger.error("psycopg2 not installed. Run: pip install psycopg2-binary")
            return {"imported": 0, "errors": 1, "topics": {}}

        stats = {"imported": 0, "errors": 0, "topics": {}}
        cutoff_date = datetime.utcnow() - timedelta(days=days_back)

        try:
            conn = psycopg2.connect(self.postgres_url)
            cur = conn.cursor(cursor_factory=RealDictCursor)

            # Query archival_memory table for recent entries
            query = """
                SELECT id, session_id, type, content, context, tags,
                       confidence, created_at, updated_at
                FROM archival_memory
                WHERE updated_at > %s
                ORDER BY confidence DESC, updated_at DESC
                LIMIT 1000
            """

            cur.execute(query, (cutoff_date,))
            learnings = cur.fetchall()

            for learning in learnings:
                try:
                    self._import_single_learning(learning, stats)
                except Exception as e:
                    logger.error(f"Failed to import learning {learning['id']}: {e}")
                    stats["errors"] += 1

            cur.close()
            conn.close()

            logger.info(
                f"Imported {stats['imported']} learnings from PostgreSQL "
                f"({stats['errors']} errors, {len(stats['topics'])} topics)"
            )

        except Exception as e:
            logger.error(f"PostgreSQL import failed: {e}")
            stats["errors"] += 1

        return stats

    def _import_single_learning(self, learning: dict, stats: dict) -> None:
        """Store a single learning in SQLite and JSONL."""
        topic = learning.get("context", "general").split()[0]

        # Track topic counts
        if topic not in stats["topics"]:
            stats["topics"][topic] = 0
        stats["topics"][topic] += 1

        # Store in JSONL for MCP memory server
        memory_entry = {
            "id": str(learning["id"]),
            "type": learning["type"],
            "content": learning["content"],
            "context": learning["context"],
            "tags": learning.get("tags", "").split(",") if learning.get("tags") else [],
            "confidence": learning.get("confidence", "medium"),
            "timestamp": learning["updated_at"].isoformat() if learning.get("updated_at") else None,
            "session_id": learning.get("session_id"),
        }

        # Append to JSONL
        self.jsonl_memory.parent.mkdir(parents=True, exist_ok=True)
        with open(self.jsonl_memory, "a") as f:
            f.write(json.dumps(memory_entry) + "\n")

        # Also store in SQLite for indexed access
        self._store_in_sqlite(memory_entry)
        stats["imported"] += 1

    def _store_in_sqlite(self, entry: dict) -> None:
        """Store memory entry in SQLite for indexed search."""
        try:
            conn = sqlite3.connect(self.sqlite_db)
            conn.execute("PRAGMA journal_mode=WAL")
            cur = conn.cursor()

            # Create table if not exists
            cur.execute("""
                CREATE TABLE IF NOT EXISTS memory_entries (
                    id TEXT PRIMARY KEY,
                    type TEXT,
                    content TEXT,
                    context TEXT,
                    tags TEXT,
                    confidence TEXT,
                    timestamp TEXT,
                    session_id TEXT,
                    imported_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            cur.execute("""
                INSERT OR REPLACE INTO memory_entries
                (id, type, content, context, tags, confidence, timestamp, session_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                entry["id"],
                entry["type"],
                entry["content"],
                entry["context"],
                json.dumps(entry.get("tags", [])),
                entry.get("confidence", "medium"),
                entry.get("timestamp"),
                entry.get("session_id"),
            ))

            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"SQLite storage failed: {e}")

    def search_imported_memories(self, query: str, limit: int = 10) -> list:
        """Search imported memories from SQLite."""
        try:
            conn = sqlite3.connect(self.sqlite_db)
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()

            # Full-text search pattern
            search_pattern = f"%{query}%"
            cur.execute("""
                SELECT * FROM memory_entries
                WHERE content LIKE ? OR context LIKE ? OR tags LIKE ?
                ORDER BY
                    CASE confidence
                        WHEN 'high' THEN 1
                        WHEN 'medium' THEN 2
                        ELSE 3
                    END,
                    imported_at DESC
                LIMIT ?
            """, (search_pattern, search_pattern, search_pattern, limit))

            results = [dict(row) for row in cur.fetchall()]
            conn.close()
            return results
        except Exception as e:
            logger.error(f"Memory search failed: {e}")
            return []

    def get_recent_by_type(self, memory_type: str, limit: int = 20) -> list:
        """Get recent learnings of a specific type."""
        try:
            conn = sqlite3.connect(self.sqlite_db)
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()

            cur.execute("""
                SELECT * FROM memory_entries
                WHERE type = ?
                ORDER BY imported_at DESC
                LIMIT ?
            """, (memory_type, limit))

            results = [dict(row) for row in cur.fetchall()]
            conn.close()
            return results
        except Exception as e:
            logger.error(f"Failed to retrieve memories by type: {e}")
            return []

    def get_memory_stats(self) -> dict:
        """Get statistics about imported memories."""
        try:
            conn = sqlite3.connect(self.sqlite_db)
            cur = conn.cursor()

            stats = {
                "total_entries": 0,
                "by_type": {},
                "by_confidence": {},
                "most_recent": None,
                "topics": []
            }

            # Total count
            cur.execute("SELECT COUNT(*) FROM memory_entries")
            stats["total_entries"] = cur.fetchone()[0]

            # By type
            cur.execute("""
                SELECT type, COUNT(*) as count
                FROM memory_entries
                GROUP BY type
            """)
            stats["by_type"] = {row[0]: row[1] for row in cur.fetchall()}

            # By confidence
            cur.execute("""
                SELECT confidence, COUNT(*) as count
                FROM memory_entries
                GROUP BY confidence
            """)
            stats["by_confidence"] = {row[0]: row[1] for row in cur.fetchall()}

            # Most recent
            cur.execute("""
                SELECT id, type, context, imported_at
                FROM memory_entries
                ORDER BY imported_at DESC
                LIMIT 1
            """)
            recent = cur.fetchone()
            if recent:
                stats["most_recent"] = {
                    "id": recent[0],
                    "type": recent[1],
                    "context": recent[2],
                    "imported_at": recent[3]
                }

            # Top topics
            cur.execute("""
                SELECT context, COUNT(*) as count
                FROM memory_entries
                GROUP BY context
                ORDER BY count DESC
                LIMIT 10
            """)
            stats["topics"] = [{"topic": row[0], "count": row[1]} for row in cur.fetchall()]

            conn.close()
            return stats
        except Exception as e:
            logger.error(f"Failed to get memory stats: {e}")
            return {}


def import_all_memories() -> dict:
    """One-liner to import all memories from PostgreSQL to local cache."""
    importer = MemoryImporter()
    return importer.import_from_postgres(days_back=180)  # Last 6 months


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    importer = MemoryImporter()

    # Import memories
    print("📥 Importing memories from PostgreSQL...")
    stats = importer.import_from_postgres(days_back=180)
    print(f"✅ Import complete: {stats['imported']} learnings, {stats['errors']} errors")
    print(f"Topics: {stats['topics']}")

    # Show stats
    print("\n📊 Memory Statistics:")
    mem_stats = importer.get_memory_stats()
    print(json.dumps(mem_stats, indent=2, default=str))

    # Search example
    print("\n🔍 Example search for 'trading':")
    results = importer.search_imported_memories("trading", limit=5)
    for r in results:
        print(f"  - {r['type']}: {r['context']}")
