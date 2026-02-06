"""
Personal Knowledge Graph (PKG) for ClawdBots.

Uses SQLite with FTS5 for entity/relationship storage.
No external dependencies (Neo4j, NetworkX) - pure SQLite.

Schema:
- entities: (id, name, type, properties_json, created_at, updated_at)
- relationships: (id, from_id, to_id, type, properties_json, created_at)
- entity_fts: FTS5 virtual table for full-text search

Relationship types (from UNIFIED_GSD):
- UPDATES: State mutation (invalidates old facts)
- EXTENDS: Enrichment (adds context)
- DERIVES: Inference (new knowledge from patterns)
- OWNS, MANAGES, DEPENDS_ON, PREFERS, CAUSED, RESOLVED_BY

Usage:
    from bots.shared.knowledge_graph import KnowledgeGraph

    kg = KnowledgeGraph()
    kg.add_entity("Daryl", "person", {"role": "founder"})
    kg.add_entity("Jarvis", "bot", {"purpose": "trading"})
    kg.add_relationship("Daryl", "Jarvis", "OWNS")
    results = kg.search("trading")
"""

import json
import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

DEFAULT_DB_PATH = "/root/clawdbots/knowledge_graph.db"


class KnowledgeGraph:
    """SQLite-backed knowledge graph with FTS5 search."""

    def __init__(self, db_path: str = DEFAULT_DB_PATH):
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
        """Create tables if they don't exist."""
        conn = self._get_conn()
        try:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS entities (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    type TEXT NOT NULL,
                    properties_json TEXT DEFAULT '{}',
                    tags TEXT DEFAULT '[]',
                    is_superseded INTEGER DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(name, type)
                );

                CREATE TABLE IF NOT EXISTS relationships (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    from_id INTEGER NOT NULL,
                    to_id INTEGER NOT NULL,
                    type TEXT NOT NULL,
                    properties_json TEXT DEFAULT '{}',
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (from_id) REFERENCES entities(id),
                    FOREIGN KEY (to_id) REFERENCES entities(id)
                );

                CREATE INDEX IF NOT EXISTS idx_rel_from ON relationships(from_id);
                CREATE INDEX IF NOT EXISTS idx_rel_to ON relationships(to_id);
                CREATE INDEX IF NOT EXISTS idx_rel_type ON relationships(type);
                CREATE INDEX IF NOT EXISTS idx_entity_name ON entities(name);
                CREATE INDEX IF NOT EXISTS idx_entity_type ON entities(type);
            """)

            # Add tags column if missing (migration for existing DBs)
            try:
                conn.execute("ALTER TABLE entities ADD COLUMN tags TEXT DEFAULT '[]'")
            except sqlite3.OperationalError:
                pass  # Column already exists

            # Create FTS5 table if not exists
            try:
                conn.execute("""
                    CREATE VIRTUAL TABLE IF NOT EXISTS entity_fts
                    USING fts5(name, type, properties)
                """)
            except sqlite3.OperationalError:
                logger.warning("FTS5 not available, full-text search disabled")

            conn.commit()
        finally:
            conn.close()

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def add_entity(self, name: str, entity_type: str, properties: dict = None, tags: list = None) -> int:
        """Add or update an entity. Returns entity ID."""
        properties = properties or {}
        tags = tags or []
        tags_str = json.dumps(tags) if tags else "[]"
        now = self._now()
        conn = self._get_conn()
        try:
            # Check if exists
            row = conn.execute(
                "SELECT id, properties_json, tags FROM entities WHERE name = ? AND type = ?",
                (name, entity_type),
            ).fetchone()

            if row:
                # Merge properties
                existing = json.loads(row["properties_json"] or "{}")
                existing.update(properties)
                # Merge tags
                existing_tags = json.loads(row["tags"] or "[]") if row["tags"] else []
                merged_tags = list(set(existing_tags + tags))
                conn.execute(
                    "UPDATE entities SET properties_json = ?, tags = ?, updated_at = ? WHERE id = ?",
                    (json.dumps(existing), json.dumps(merged_tags), now, row["id"]),
                )
                eid = row["id"]
            else:
                cursor = conn.execute(
                    "INSERT INTO entities (name, type, properties_json, tags, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
                    (name, entity_type, json.dumps(properties), tags_str, now, now),
                )
                eid = cursor.lastrowid

            # Update FTS
            try:
                conn.execute("DELETE FROM entity_fts WHERE rowid = ?", (eid,))
                props_text = json.dumps(properties) if properties else ""
                conn.execute(
                    "INSERT INTO entity_fts(rowid, name, type, properties) VALUES (?, ?, ?, ?)",
                    (eid, name, entity_type, props_text),
                )
            except sqlite3.OperationalError:
                pass  # FTS not available

            conn.commit()
            return eid
        finally:
            conn.close()

    def get_entity(self, name: str) -> Optional[dict]:
        """Get a single entity by name. Returns None if not found."""
        conn = self._get_conn()
        try:
            row = conn.execute(
                "SELECT id, name, type, properties_json, tags, created_at, updated_at FROM entities WHERE name = ? AND is_superseded = 0",
                (name,),
            ).fetchone()
            if not row:
                return None
            return {
                "id": row["id"],
                "name": row["name"],
                "type": row["type"],
                "properties": json.loads(row["properties_json"] or "{}"),
                "tags": json.loads(row["tags"] or "[]") if row["tags"] else [],
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
            }
        finally:
            conn.close()

    def add_relationship(self, from_name: str, to_name: str, rel_type: str, properties: dict = None) -> int:
        """Add a relationship between two entities. Auto-creates entities if needed."""
        properties = properties or {}
        # Ensure both entities exist
        from_id = self._ensure_entity(from_name)
        to_id = self._ensure_entity(to_name)

        conn = self._get_conn()
        try:
            cursor = conn.execute(
                "INSERT INTO relationships (from_id, to_id, type, properties_json, created_at) VALUES (?, ?, ?, ?, ?)",
                (from_id, to_id, rel_type, json.dumps(properties), self._now()),
            )
            conn.commit()
            return cursor.lastrowid
        finally:
            conn.close()

    def _ensure_entity(self, name: str) -> int:
        """Get entity ID, creating with type 'unknown' if needed."""
        conn = self._get_conn()
        try:
            row = conn.execute("SELECT id FROM entities WHERE name = ?", (name,)).fetchone()
            if row:
                return row["id"]
        finally:
            conn.close()
        return self.add_entity(name, "unknown")

    def query(self, entity_name: str = None, entity_type: str = None, rel_type: str = None) -> List[dict]:
        """Query entities and relationships."""
        conn = self._get_conn()
        try:
            if rel_type:
                # Return entities involved in relationships of this type
                rows = conn.execute("""
                    SELECT DISTINCT e.id, e.name, e.type, e.properties_json, e.created_at, e.updated_at
                    FROM entities e
                    JOIN relationships r ON (e.id = r.from_id OR e.id = r.to_id)
                    WHERE r.type = ?
                """, (rel_type,)).fetchall()
            else:
                conditions = []
                params = []
                if entity_name:
                    conditions.append("name = ?")
                    params.append(entity_name)
                if entity_type:
                    conditions.append("type = ?")
                    params.append(entity_type)

                where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
                rows = conn.execute(
                    f"SELECT id, name, type, properties_json, created_at, updated_at FROM entities {where}",
                    params,
                ).fetchall()

            return [
                {
                    "id": r["id"],
                    "name": r["name"],
                    "type": r["type"],
                    "properties": json.loads(r["properties_json"] or "{}"),
                    "created_at": r["created_at"],
                    "updated_at": r["updated_at"],
                }
                for r in rows
            ]
        finally:
            conn.close()

    def get_related(self, entity_name: str, rel_type: str = None, direction: str = "outgoing") -> List[dict]:
        """Get entities related to a given entity."""
        conn = self._get_conn()
        try:
            entity = conn.execute("SELECT id FROM entities WHERE name = ?", (entity_name,)).fetchone()
            if not entity:
                return []

            eid = entity["id"]

            if direction == "outgoing":
                sql = """
                    SELECT e.id, e.name, e.type, e.properties_json, e.created_at, e.updated_at,
                           r.type as rel_type, r.properties_json as rel_properties
                    FROM relationships r
                    JOIN entities e ON e.id = r.to_id
                    WHERE r.from_id = ?
                """
            else:
                sql = """
                    SELECT e.id, e.name, e.type, e.properties_json, e.created_at, e.updated_at,
                           r.type as rel_type, r.properties_json as rel_properties
                    FROM relationships r
                    JOIN entities e ON e.id = r.from_id
                    WHERE r.to_id = ?
                """

            params = [eid]
            if rel_type:
                sql += " AND r.type = ?"
                params.append(rel_type)

            rows = conn.execute(sql, params).fetchall()
            return [
                {
                    "id": r["id"],
                    "name": r["name"],
                    "type": r["type"],
                    "properties": json.loads(r["properties_json"] or "{}"),
                    "rel_type": r["rel_type"],
                    "rel_properties": json.loads(r["rel_properties"] or "{}"),
                    "created_at": r["created_at"],
                    "updated_at": r["updated_at"],
                }
                for r in rows
            ]
        finally:
            conn.close()

    def search(self, query: str) -> List[dict]:
        """Full-text search across entities."""
        conn = self._get_conn()
        try:
            try:
                rows = conn.execute(
                    """
                    SELECT e.id, e.name, e.type, e.properties_json, e.tags, e.created_at, e.updated_at
                    FROM entity_fts fts
                    JOIN entities e ON e.rowid = fts.rowid
                    WHERE entity_fts MATCH ?
                    """,
                    (query,),
                ).fetchall()
            except sqlite3.OperationalError:
                # FTS not available, fall back to LIKE
                rows = conn.execute(
                    "SELECT id, name, type, properties_json, tags, created_at, updated_at FROM entities WHERE name LIKE ? AND is_superseded = 0",
                    (f"%{query.replace('*', '%')}%",),
                ).fetchall()

            return [
                {
                    "id": r["id"],
                    "name": r["name"],
                    "type": r["type"],
                    "properties": json.loads(r["properties_json"] or "{}"),
                    "tags": json.loads(r["tags"] or "[]") if r["tags"] else [],
                    "created_at": r["created_at"],
                    "updated_at": r["updated_at"],
                }
                for r in rows
            ]
        finally:
            conn.close()

    def update_fact(self, old_entity: str, new_properties: dict):
        """Update a fact (UPDATES relationship - stores history snapshot first)."""
        conn = self._get_conn()
        try:
            row = conn.execute(
                "SELECT id, properties_json, type FROM entities WHERE name = ?",
                (old_entity,),
            ).fetchone()
            if not row:
                return

            old_props = json.loads(row["properties_json"] or "{}")
            now = self._now()

            # Create history snapshot
            snapshot_name = f"{old_entity}__snapshot__{now}"
            cursor = conn.execute(
                "INSERT INTO entities (name, type, properties_json, is_superseded, created_at, updated_at) VALUES (?, ?, ?, 1, ?, ?)",
                (snapshot_name, row["type"], json.dumps(old_props), now, now),
            )
            snapshot_id = cursor.lastrowid

            # Create UPDATES relationship: current -> snapshot
            conn.execute(
                "INSERT INTO relationships (from_id, to_id, type, properties_json, created_at) VALUES (?, ?, 'UPDATES', '{}', ?)",
                (row["id"], snapshot_id, now),
            )

            # Update the entity properties
            merged = {**old_props, **new_properties}
            conn.execute(
                "UPDATE entities SET properties_json = ?, updated_at = ? WHERE id = ?",
                (json.dumps(merged), now, row["id"]),
            )

            conn.commit()
        finally:
            conn.close()

    def extend_fact(self, entity_name: str, additional_properties: dict):
        """Extend a fact (EXTENDS relationship - adds without replacing)."""
        conn = self._get_conn()
        try:
            row = conn.execute(
                "SELECT id, properties_json FROM entities WHERE name = ?",
                (entity_name,),
            ).fetchone()
            if not row:
                return

            existing = json.loads(row["properties_json"] or "{}")
            existing.update(additional_properties)
            now = self._now()
            conn.execute(
                "UPDATE entities SET properties_json = ?, updated_at = ? WHERE id = ?",
                (json.dumps(existing), now, row["id"]),
            )
            conn.commit()
        finally:
            conn.close()

    def derive_fact(self, source_entities: List[str], derived_name: str, derived_type: str, reasoning: str):
        """Derive new knowledge from existing entities (DERIVES relationship)."""
        derived_id = self.add_entity(derived_name, derived_type, {"reasoning": reasoning})

        for source_name in source_entities:
            source_id = self._ensure_entity(source_name)
            conn = self._get_conn()
            try:
                conn.execute(
                    "INSERT INTO relationships (from_id, to_id, type, properties_json, created_at) VALUES (?, ?, 'DERIVES', '{}', ?)",
                    (derived_id, source_id, self._now()),
                )
                conn.commit()
            finally:
                conn.close()

    def get_entity_history(self, entity_name: str) -> List[dict]:
        """Get temporal history of an entity (all UPDATES chain)."""
        conn = self._get_conn()
        try:
            row = conn.execute("SELECT id FROM entities WHERE name = ?", (entity_name,)).fetchone()
            if not row:
                return []

            eid = row["id"]
            # Get all snapshots via UPDATES chain
            snapshots = conn.execute("""
                SELECT e.id, e.name, e.type, e.properties_json, e.created_at, e.updated_at
                FROM relationships r
                JOIN entities e ON e.id = r.to_id
                WHERE r.from_id = ? AND r.type = 'UPDATES'
                ORDER BY e.created_at ASC
            """, (eid,)).fetchall()

            # Include current state
            current = conn.execute(
                "SELECT id, name, type, properties_json, created_at, updated_at FROM entities WHERE id = ?",
                (eid,),
            ).fetchone()

            result = [
                {
                    "id": r["id"],
                    "name": r["name"],
                    "type": r["type"],
                    "properties": json.loads(r["properties_json"] or "{}"),
                    "created_at": r["created_at"],
                    "updated_at": r["updated_at"],
                }
                for r in snapshots
            ]
            if current:
                result.append({
                    "id": current["id"],
                    "name": current["name"],
                    "type": current["type"],
                    "properties": json.loads(current["properties_json"] or "{}"),
                    "created_at": current["created_at"],
                    "updated_at": current["updated_at"],
                })

            return result
        finally:
            conn.close()

    def export_graph(self) -> dict:
        """Export entire graph as JSON-serializable dict."""
        conn = self._get_conn()
        try:
            entities = conn.execute(
                "SELECT id, name, type, properties_json, created_at, updated_at FROM entities WHERE is_superseded = 0"
            ).fetchall()
            relationships = conn.execute(
                "SELECT id, from_id, to_id, type, properties_json, created_at FROM relationships"
            ).fetchall()

            return {
                "entities": [
                    {
                        "id": e["id"],
                        "name": e["name"],
                        "type": e["type"],
                        "properties": json.loads(e["properties_json"] or "{}"),
                        "created_at": e["created_at"],
                        "updated_at": e["updated_at"],
                    }
                    for e in entities
                ],
                "relationships": [
                    {
                        "id": r["id"],
                        "from_id": r["from_id"],
                        "to_id": r["to_id"],
                        "type": r["type"],
                        "properties": json.loads(r["properties_json"] or "{}"),
                        "created_at": r["created_at"],
                    }
                    for r in relationships
                ],
            }
        finally:
            conn.close()


def seed_initial_entities(db_path: str = DEFAULT_DB_PATH):
    """Pre-populate the graph with known entities."""
    kg = KnowledgeGraph(db_path=db_path)

    # People
    kg.add_entity("Daryl", "person", {"role": "founder", "alias": "lucid"})

    # Bots
    kg.add_entity("Matt", "bot", {"full_name": "ClawdMatt", "role": "operations"})
    kg.add_entity("Friday", "bot", {"full_name": "ClawdFriday", "role": "marketing"})
    kg.add_entity("Jarvis", "bot", {"full_name": "ClawdJarvis", "role": "technical"})

    # Services
    kg.add_entity("VPS", "service", {"provider": "hosting", "os": "linux"})
    kg.add_entity("Telegram", "service", {"type": "messaging"})
    kg.add_entity("X/Twitter", "service", {"type": "social"})
    kg.add_entity("Solana", "service", {"type": "blockchain"})

    # Projects
    kg.add_entity("Trading Bot", "project", {"chain": "solana", "dex": "jupiter"})
    kg.add_entity("ClawdBots", "project", {"bots": 3})
    kg.add_entity("KR8TIV AI", "project", {"type": "brand"})

    # Relationships
    kg.add_relationship("Daryl", "Matt", "OWNS")
    kg.add_relationship("Daryl", "Friday", "OWNS")
    kg.add_relationship("Daryl", "Jarvis", "OWNS")
    kg.add_relationship("Jarvis", "Trading Bot", "MANAGES")
    kg.add_relationship("Jarvis", "Solana", "DEPENDS_ON")
    kg.add_relationship("Friday", "X/Twitter", "DEPENDS_ON")
    kg.add_relationship("Matt", "Telegram", "DEPENDS_ON")
    kg.add_relationship("ClawdBots", "VPS", "DEPENDS_ON")

    logger.info("Seeded knowledge graph with initial entities")
    return kg
