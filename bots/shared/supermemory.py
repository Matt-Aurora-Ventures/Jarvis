"""
SuperMemory - Shared knowledge graph for ClawdBot team.

Fact-based memory with relationships, access control, and temporal reasoning.
Uses SQLite for storage (shared across bots on VPS).

Relationship types:
- updates: State mutation (new fact invalidates old)
- extends: Enrichment (adds context to existing fact)
- derives: Inference (new knowledge from pattern of facts)

Memory tags (access control):
- company_core: Shared, all read, Matt writes
- technical_stack: Jarvis owns, Matt+Jarvis read
- marketing_creative: Friday owns, Matt+Friday read
- crypto_ops: Jarvis owns, Matt+Jarvis read
- ops_logs: Matt owns, all read

Usage:
    from bots.shared.supermemory import SuperMemory

    sm = SuperMemory('matt')
    fid = sm.remember("VPS IP is 76.13.106.100", "company_core")
    sm.extend(fid, "Tailscale IP is 100.72.121.115")
    results = sm.recall("VPS IP")
"""

import logging
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger(__name__)

DEFAULT_DB_PATH = "/root/clawdbots/data/supermemory.db"

TAG_PERMISSIONS = {
    "company_core": {"read": ["matt", "friday", "jarvis"], "write": ["matt"]},
    "technical_stack": {"read": ["matt", "jarvis"], "write": ["jarvis"]},
    "marketing_creative": {"read": ["matt", "friday"], "write": ["friday"]},
    "crypto_ops": {"read": ["matt", "jarvis"], "write": ["jarvis"]},
    "ops_logs": {"read": ["matt", "friday", "jarvis"], "write": ["matt"]},
}


class SuperMemory:
    """SQLite-backed shared memory with access control and temporal reasoning."""

    def __init__(self, bot_name: str, db_path: str = DEFAULT_DB_PATH):
        self.bot_name = bot_name.lower()
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def _init_db(self):
        conn = self._get_conn()
        try:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS facts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    content TEXT NOT NULL,
                    tag TEXT NOT NULL,
                    author TEXT NOT NULL,
                    document_date TEXT NOT NULL,
                    event_date TEXT,
                    superseded_by INTEGER,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS relationships (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source_id INTEGER NOT NULL,
                    target_id INTEGER NOT NULL,
                    rel_type TEXT NOT NULL CHECK(rel_type IN ('updates', 'extends', 'derives')),
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (source_id) REFERENCES facts(id),
                    FOREIGN KEY (target_id) REFERENCES facts(id)
                );

                CREATE INDEX IF NOT EXISTS idx_facts_tag ON facts(tag);
                CREATE INDEX IF NOT EXISTS idx_facts_author ON facts(author);
                CREATE INDEX IF NOT EXISTS idx_relationships_source ON relationships(source_id);
                CREATE INDEX IF NOT EXISTS idx_relationships_target ON relationships(target_id);
            """)
            conn.commit()
        finally:
            conn.close()

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def can_read(self, tag: str) -> bool:
        """Check if this bot can read the given tag."""
        perms = TAG_PERMISSIONS.get(tag)
        if not perms:
            return False
        return self.bot_name in perms.get("read", [])

    def can_write(self, tag: str) -> bool:
        """Check if this bot can write to the given tag."""
        perms = TAG_PERMISSIONS.get(tag)
        if not perms:
            return False
        return self.bot_name in perms.get("write", [])

    def remember(self, content: str, tag: str, event_date: str = None) -> int:
        """Store a new fact with tag and optional event date. Returns fact ID."""
        if not self.can_write(tag):
            raise PermissionError(
                f"Bot '{self.bot_name}' cannot write to tag '{tag}'"
            )
        now = self._now()
        conn = self._get_conn()
        try:
            cursor = conn.execute(
                "INSERT INTO facts (content, tag, author, document_date, event_date, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (content, tag, self.bot_name, now, event_date, now),
            )
            conn.commit()
            return cursor.lastrowid
        finally:
            conn.close()

    def update(self, old_fact_id: int, new_content: str) -> int:
        """Create Updates relationship - new fact invalidates old. Returns new fact ID."""
        conn = self._get_conn()
        try:
            old = conn.execute(
                "SELECT id, tag, author FROM facts WHERE id = ?", (old_fact_id,)
            ).fetchone()
            if not old:
                raise ValueError(f"Fact {old_fact_id} not found")

            now = self._now()
            # Create new fact with same tag
            cursor = conn.execute(
                "INSERT INTO facts (content, tag, author, document_date, event_date, created_at) "
                "VALUES (?, ?, ?, ?, NULL, ?)",
                (new_content, old["tag"], self.bot_name, now, now),
            )
            new_id = cursor.lastrowid

            # Mark old as superseded
            conn.execute(
                "UPDATE facts SET superseded_by = ? WHERE id = ?",
                (new_id, old_fact_id),
            )

            # Create relationship
            conn.execute(
                "INSERT INTO relationships (source_id, target_id, rel_type, created_at) "
                "VALUES (?, ?, 'updates', ?)",
                (new_id, old_fact_id, now),
            )
            conn.commit()
            return new_id
        finally:
            conn.close()

    def extend(self, fact_id: int, extension: str) -> int:
        """Create Extends relationship - add context to existing fact. Returns new fact ID."""
        conn = self._get_conn()
        try:
            original = conn.execute(
                "SELECT id, tag FROM facts WHERE id = ?", (fact_id,)
            ).fetchone()
            if not original:
                raise ValueError(f"Fact {fact_id} not found")

            now = self._now()
            cursor = conn.execute(
                "INSERT INTO facts (content, tag, author, document_date, event_date, created_at) "
                "VALUES (?, ?, ?, ?, NULL, ?)",
                (extension, original["tag"], self.bot_name, now, now),
            )
            ext_id = cursor.lastrowid

            conn.execute(
                "INSERT INTO relationships (source_id, target_id, rel_type, created_at) "
                "VALUES (?, ?, 'extends', ?)",
                (ext_id, fact_id, now),
            )
            conn.commit()
            return ext_id
        finally:
            conn.close()

    def derive(self, source_fact_ids: list, inference: str) -> int:
        """Create Derives relationship - new knowledge from patterns. Returns new fact ID."""
        if not source_fact_ids:
            raise ValueError("Must provide at least one source fact")

        conn = self._get_conn()
        try:
            # Get tag from first source
            first = conn.execute(
                "SELECT tag FROM facts WHERE id = ?", (source_fact_ids[0],)
            ).fetchone()
            tag = first["tag"] if first else "company_core"

            now = self._now()
            cursor = conn.execute(
                "INSERT INTO facts (content, tag, author, document_date, event_date, created_at) "
                "VALUES (?, ?, ?, ?, NULL, ?)",
                (inference, tag, self.bot_name, now, now),
            )
            derived_id = cursor.lastrowid

            for src_id in source_fact_ids:
                conn.execute(
                    "INSERT INTO relationships (source_id, target_id, rel_type, created_at) "
                    "VALUES (?, ?, 'derives', ?)",
                    (derived_id, src_id, now),
                )
            conn.commit()
            return derived_id
        finally:
            conn.close()

    def recall(self, query: str, tag: str = None, limit: int = 10) -> list:
        """Search facts by keyword with optional tag filter. Respects access control."""
        conn = self._get_conn()
        try:
            conditions = ["superseded_by IS NULL"]
            params = []

            if query:
                conditions.append("content LIKE ?")
                params.append(f"%{query}%")

            if tag:
                if not self.can_read(tag):
                    return []
                conditions.append("tag = ?")
                params.append(tag)
            else:
                # Filter to only readable tags
                readable = [t for t in TAG_PERMISSIONS if self.can_read(t)]
                if not readable:
                    return []
                placeholders = ",".join("?" * len(readable))
                conditions.append(f"tag IN ({placeholders})")
                params.extend(readable)

            where = " AND ".join(conditions)
            params.append(limit)

            rows = conn.execute(
                f"SELECT id, content, tag, author, document_date, event_date, created_at "
                f"FROM facts WHERE {where} ORDER BY document_date DESC LIMIT ?",
                params,
            ).fetchall()

            return [
                {
                    "id": r["id"],
                    "content": r["content"],
                    "tag": r["tag"],
                    "author": r["author"],
                    "document_date": r["document_date"],
                    "event_date": r["event_date"],
                }
                for r in rows
            ]
        finally:
            conn.close()

    def get_timeline(self, tag: str = None, days: int = 7) -> list:
        """Get facts ordered by event_date for temporal reasoning."""
        conn = self._get_conn()
        try:
            conditions = ["event_date IS NOT NULL", "superseded_by IS NULL"]
            params = []

            if tag:
                if not self.can_read(tag):
                    return []
                conditions.append("tag = ?")
                params.append(tag)
            else:
                readable = [t for t in TAG_PERMISSIONS if self.can_read(t)]
                if not readable:
                    return []
                placeholders = ",".join("?" * len(readable))
                conditions.append(f"tag IN ({placeholders})")
                params.extend(readable)

            cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
            conditions.append("event_date >= ?")
            params.append(cutoff[:10])  # date portion only

            where = " AND ".join(conditions)
            rows = conn.execute(
                f"SELECT id, content, tag, author, document_date, event_date "
                f"FROM facts WHERE {where} ORDER BY event_date ASC",
                params,
            ).fetchall()

            return [
                {
                    "id": r["id"],
                    "content": r["content"],
                    "tag": r["tag"],
                    "author": r["author"],
                    "document_date": r["document_date"],
                    "event_date": r["event_date"],
                }
                for r in rows
            ]
        finally:
            conn.close()
