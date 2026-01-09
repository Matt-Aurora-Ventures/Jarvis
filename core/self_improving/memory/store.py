"""
SQLite-based Memory Store for Jarvis Self-Improving Core.

Key insight: SQLite is enough. No vector database needed for personal AI.
Full-text search + intelligent queries = 80-90% cheaper than vector DBs.

Schema:
- entities: People, projects, concepts
- facts: Knowledge about entities
- reflections: Self-improvement notes
- predictions: Track prediction accuracy
- interactions: Conversation history
- trust: Trust levels per domain
- settings: Configuration state
"""

import sqlite3
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple
from contextlib import contextmanager
import threading

from core.self_improving.memory.models import (
    Entity,
    Fact,
    Reflection,
    Prediction,
    Interaction,
    ContextBundle,
)

logger = logging.getLogger("jarvis.memory")

# Schema version for migrations
SCHEMA_VERSION = 1

SCHEMA_SQL = """
-- Schema version tracking
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY,
    applied_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- Entities: People, projects, companies, concepts
CREATE TABLE IF NOT EXISTS entities (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    entity_type TEXT NOT NULL,  -- person, project, company, concept
    attributes TEXT DEFAULT '{}',  -- JSON for flexibility
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(name, entity_type)
);

-- Facts: Specific knowledge about entities
CREATE TABLE IF NOT EXISTS facts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entity TEXT NOT NULL,
    entity_id INTEGER,
    fact TEXT NOT NULL,
    confidence REAL DEFAULT 0.8,
    source TEXT DEFAULT 'conversation',
    learned_at TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(entity, fact),
    FOREIGN KEY (entity_id) REFERENCES entities(id)
);

-- Reflections: Self-improvement notes from failures
CREATE TABLE IF NOT EXISTS reflections (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    trigger TEXT NOT NULL,
    what_happened TEXT,
    why_failed TEXT,
    lesson TEXT NOT NULL,
    new_approach TEXT,
    applied INTEGER DEFAULT 0,
    applied_count INTEGER DEFAULT 0,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- Predictions: Track prediction accuracy for trust calibration
CREATE TABLE IF NOT EXISTS predictions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    prediction TEXT NOT NULL,
    confidence REAL NOT NULL,
    domain TEXT DEFAULT 'general',
    deadline TEXT,
    outcome TEXT,
    was_correct INTEGER,  -- NULL = unresolved, 0 = wrong, 1 = correct
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    resolved_at TEXT
);

-- Interactions: Conversation history with feedback
CREATE TABLE IF NOT EXISTS interactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_input TEXT NOT NULL,
    jarvis_response TEXT,
    feedback TEXT,  -- positive, negative, confused, retry
    session_id TEXT,
    timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
    metadata TEXT DEFAULT '{}'
);

-- Trust: Trust levels per domain
CREATE TABLE IF NOT EXISTS trust (
    domain TEXT PRIMARY KEY,
    level INTEGER DEFAULT 0,
    successes INTEGER DEFAULT 0,
    failures INTEGER DEFAULT 0,
    last_success TEXT,
    last_failure TEXT,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- Settings: Configuration and state
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for efficient queries
CREATE INDEX IF NOT EXISTS idx_entities_type ON entities(entity_type);
CREATE INDEX IF NOT EXISTS idx_entities_name ON entities(name);
CREATE INDEX IF NOT EXISTS idx_facts_entity ON facts(entity);
CREATE INDEX IF NOT EXISTS idx_facts_entity_id ON facts(entity_id);
CREATE INDEX IF NOT EXISTS idx_reflections_applied ON reflections(applied);
CREATE INDEX IF NOT EXISTS idx_reflections_created ON reflections(created_at);
CREATE INDEX IF NOT EXISTS idx_predictions_domain ON predictions(domain);
CREATE INDEX IF NOT EXISTS idx_predictions_resolved ON predictions(was_correct);
CREATE INDEX IF NOT EXISTS idx_interactions_timestamp ON interactions(timestamp);
CREATE INDEX IF NOT EXISTS idx_interactions_feedback ON interactions(feedback);
CREATE INDEX IF NOT EXISTS idx_interactions_session ON interactions(session_id);

-- Full-text search for facts and reflections
CREATE VIRTUAL TABLE IF NOT EXISTS facts_fts USING fts5(
    entity, fact, content='facts', content_rowid='id'
);

CREATE VIRTUAL TABLE IF NOT EXISTS reflections_fts USING fts5(
    trigger, lesson, new_approach, content='reflections', content_rowid='id'
);

-- Triggers to keep FTS in sync
CREATE TRIGGER IF NOT EXISTS facts_ai AFTER INSERT ON facts BEGIN
    INSERT INTO facts_fts(rowid, entity, fact) VALUES (new.id, new.entity, new.fact);
END;

CREATE TRIGGER IF NOT EXISTS facts_ad AFTER DELETE ON facts BEGIN
    INSERT INTO facts_fts(facts_fts, rowid, entity, fact) VALUES('delete', old.id, old.entity, old.fact);
END;

CREATE TRIGGER IF NOT EXISTS facts_au AFTER UPDATE ON facts BEGIN
    INSERT INTO facts_fts(facts_fts, rowid, entity, fact) VALUES('delete', old.id, old.entity, old.fact);
    INSERT INTO facts_fts(rowid, entity, fact) VALUES (new.id, new.entity, new.fact);
END;

CREATE TRIGGER IF NOT EXISTS reflections_ai AFTER INSERT ON reflections BEGIN
    INSERT INTO reflections_fts(rowid, trigger, lesson, new_approach)
    VALUES (new.id, new.trigger, new.lesson, new.new_approach);
END;

CREATE TRIGGER IF NOT EXISTS reflections_ad AFTER DELETE ON reflections BEGIN
    INSERT INTO reflections_fts(reflections_fts, rowid, trigger, lesson, new_approach)
    VALUES('delete', old.id, old.trigger, old.lesson, old.new_approach);
END;
"""


class MemoryStore:
    """SQLite-based persistent memory for Jarvis self-improving core."""

    def __init__(self, db_path: str = "data/jarvis_memory.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._local = threading.local()
        self._init_schema()
        logger.info(f"Memory store initialized at {self.db_path}")

    def _get_connection(self) -> sqlite3.Connection:
        """Get thread-local database connection."""
        if not hasattr(self._local, "conn") or self._local.conn is None:
            self._local.conn = sqlite3.connect(
                str(self.db_path),
                check_same_thread=False,
                timeout=30.0,
            )
            self._local.conn.row_factory = sqlite3.Row
            self._local.conn.execute("PRAGMA journal_mode=WAL")
            self._local.conn.execute("PRAGMA foreign_keys=ON")
        return self._local.conn

    @property
    def conn(self) -> sqlite3.Connection:
        return self._get_connection()

    @contextmanager
    def transaction(self):
        """Context manager for transactions."""
        conn = self.conn
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise

    def _init_schema(self):
        """Initialize database schema."""
        conn = self.conn
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='schema_version'"
        )
        if cursor.fetchone() is None:
            conn.executescript(SCHEMA_SQL)
            conn.execute(
                "INSERT INTO schema_version (version) VALUES (?)",
                (SCHEMA_VERSION,)
            )
            conn.commit()
            logger.info("Database schema created")
        else:
            # Check for migrations
            cursor = conn.execute("SELECT MAX(version) FROM schema_version")
            current = cursor.fetchone()[0] or 0
            if current < SCHEMA_VERSION:
                self._run_migrations(current, SCHEMA_VERSION)

    def _run_migrations(self, from_version: int, to_version: int):
        """Run schema migrations."""
        logger.info(f"Migrating schema from v{from_version} to v{to_version}")
        # Add migration logic here as schema evolves

    # =========================================================================
    # ENTITY OPERATIONS
    # =========================================================================

    def store_entity(self, entity: Entity) -> int:
        """Store or update an entity. Returns entity ID."""
        with self.transaction() as conn:
            cursor = conn.execute(
                """
                INSERT INTO entities (name, entity_type, attributes, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(name, entity_type) DO UPDATE SET
                    attributes = excluded.attributes,
                    updated_at = excluded.updated_at
                """,
                (
                    entity.name,
                    entity.entity_type,
                    json.dumps(entity.attributes),
                    entity.created_at.isoformat(),
                    datetime.utcnow().isoformat(),
                ),
            )
            return cursor.lastrowid

    def get_entity(self, name: str, entity_type: Optional[str] = None) -> Optional[Entity]:
        """Get an entity by name and optionally type."""
        if entity_type:
            cursor = self.conn.execute(
                "SELECT * FROM entities WHERE name = ? AND entity_type = ?",
                (name, entity_type),
            )
        else:
            cursor = self.conn.execute(
                "SELECT * FROM entities WHERE name = ?",
                (name,),
            )
        row = cursor.fetchone()
        return Entity.from_row(dict(row)) if row else None

    def get_entities_by_type(self, entity_type: str) -> List[Entity]:
        """Get all entities of a specific type."""
        cursor = self.conn.execute(
            "SELECT * FROM entities WHERE entity_type = ? ORDER BY updated_at DESC",
            (entity_type,),
        )
        return [Entity.from_row(dict(row)) for row in cursor.fetchall()]

    def search_entities(self, query: str, limit: int = 10) -> List[Entity]:
        """Search entities by name."""
        cursor = self.conn.execute(
            "SELECT * FROM entities WHERE name LIKE ? ORDER BY updated_at DESC LIMIT ?",
            (f"%{query}%", limit),
        )
        return [Entity.from_row(dict(row)) for row in cursor.fetchall()]

    # =========================================================================
    # FACT OPERATIONS
    # =========================================================================

    def store_fact(self, fact: Fact) -> int:
        """Store or update a fact. Returns fact ID."""
        with self.transaction() as conn:
            cursor = conn.execute(
                """
                INSERT INTO facts (entity, entity_id, fact, confidence, source, learned_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(entity, fact) DO UPDATE SET
                    confidence = MAX(excluded.confidence, facts.confidence),
                    source = excluded.source,
                    learned_at = excluded.learned_at
                """,
                (
                    fact.entity,
                    fact.entity_id,
                    fact.fact,
                    fact.confidence,
                    fact.source,
                    fact.learned_at.isoformat(),
                ),
            )
            return cursor.lastrowid

    def get_facts_about(self, entity: str, limit: int = 20) -> List[Fact]:
        """Get all facts about an entity."""
        cursor = self.conn.execute(
            """
            SELECT * FROM facts
            WHERE entity LIKE ?
            ORDER BY confidence DESC, learned_at DESC
            LIMIT ?
            """,
            (f"%{entity}%", limit),
        )
        return [Fact.from_row(dict(row)) for row in cursor.fetchall()]

    def search_facts(self, query: str, limit: int = 20) -> List[Fact]:
        """Full-text search across facts."""
        cursor = self.conn.execute(
            """
            SELECT f.* FROM facts f
            JOIN facts_fts fts ON f.id = fts.rowid
            WHERE facts_fts MATCH ?
            ORDER BY rank
            LIMIT ?
            """,
            (query, limit),
        )
        return [Fact.from_row(dict(row)) for row in cursor.fetchall()]

    def update_fact(self, entity: str, old_fact: str, new_fact: str, source: str = "correction") -> bool:
        """Update a fact (used when correcting knowledge)."""
        with self.transaction() as conn:
            cursor = conn.execute(
                """
                UPDATE facts SET fact = ?, source = ?, learned_at = ?
                WHERE entity = ? AND fact = ?
                """,
                (new_fact, source, datetime.utcnow().isoformat(), entity, old_fact),
            )
            return cursor.rowcount > 0

    def delete_fact(self, entity: str, fact: str) -> bool:
        """Delete a fact."""
        with self.transaction() as conn:
            cursor = conn.execute(
                "DELETE FROM facts WHERE entity = ? AND fact = ?",
                (entity, fact),
            )
            return cursor.rowcount > 0

    # =========================================================================
    # REFLECTION OPERATIONS
    # =========================================================================

    def store_reflection(self, reflection: Reflection) -> int:
        """Store a new reflection."""
        with self.transaction() as conn:
            cursor = conn.execute(
                """
                INSERT INTO reflections (trigger, what_happened, why_failed, lesson, new_approach, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    reflection.trigger,
                    reflection.what_happened,
                    reflection.why_failed,
                    reflection.lesson,
                    reflection.new_approach,
                    reflection.created_at.isoformat(),
                ),
            )
            return cursor.lastrowid

    def get_relevant_reflections(self, context: str, limit: int = 5) -> List[Reflection]:
        """Get reflections relevant to the current context."""
        # First try FTS search
        cursor = self.conn.execute(
            """
            SELECT r.* FROM reflections r
            JOIN reflections_fts fts ON r.id = fts.rowid
            WHERE reflections_fts MATCH ?
            ORDER BY rank, r.applied_count DESC
            LIMIT ?
            """,
            (context, limit),
        )
        results = [Reflection.from_row(dict(row)) for row in cursor.fetchall()]

        # Fallback to recent if no FTS matches
        if not results:
            cursor = self.conn.execute(
                """
                SELECT * FROM reflections
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (limit,),
            )
            results = [Reflection.from_row(dict(row)) for row in cursor.fetchall()]

        return results

    def get_unapplied_reflections(self, limit: int = 10) -> List[Reflection]:
        """Get reflections that haven't been applied yet."""
        cursor = self.conn.execute(
            """
            SELECT * FROM reflections
            WHERE applied = 0
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (limit,),
        )
        return [Reflection.from_row(dict(row)) for row in cursor.fetchall()]

    def mark_reflection_applied(self, reflection_id: int) -> bool:
        """Mark a reflection as applied."""
        with self.transaction() as conn:
            cursor = conn.execute(
                """
                UPDATE reflections
                SET applied = 1, applied_count = applied_count + 1
                WHERE id = ?
                """,
                (reflection_id,),
            )
            return cursor.rowcount > 0

    # =========================================================================
    # PREDICTION OPERATIONS
    # =========================================================================

    def store_prediction(self, prediction: Prediction) -> int:
        """Store a new prediction."""
        with self.transaction() as conn:
            cursor = conn.execute(
                """
                INSERT INTO predictions (prediction, confidence, domain, deadline, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    prediction.prediction,
                    prediction.confidence,
                    prediction.domain,
                    prediction.deadline.isoformat() if prediction.deadline else None,
                    prediction.created_at.isoformat(),
                ),
            )
            return cursor.lastrowid

    def resolve_prediction(
        self, prediction_id: int, outcome: str, was_correct: bool
    ) -> bool:
        """Record the outcome of a prediction."""
        with self.transaction() as conn:
            cursor = conn.execute(
                """
                UPDATE predictions
                SET outcome = ?, was_correct = ?, resolved_at = ?
                WHERE id = ?
                """,
                (outcome, int(was_correct), datetime.utcnow().isoformat(), prediction_id),
            )
            return cursor.rowcount > 0

    def get_prediction_accuracy(
        self, domain: Optional[str] = None, days: int = 30
    ) -> Dict[str, Any]:
        """Calculate prediction accuracy for trust calibration."""
        cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat()

        if domain:
            cursor = self.conn.execute(
                """
                SELECT
                    COUNT(*) as total,
                    SUM(CASE WHEN was_correct = 1 THEN 1 ELSE 0 END) as correct,
                    AVG(confidence) as avg_confidence
                FROM predictions
                WHERE domain = ? AND was_correct IS NOT NULL AND created_at > ?
                """,
                (domain, cutoff),
            )
        else:
            cursor = self.conn.execute(
                """
                SELECT
                    COUNT(*) as total,
                    SUM(CASE WHEN was_correct = 1 THEN 1 ELSE 0 END) as correct,
                    AVG(confidence) as avg_confidence
                FROM predictions
                WHERE was_correct IS NOT NULL AND created_at > ?
                """,
                (cutoff,),
            )

        row = cursor.fetchone()
        total = row["total"] or 0
        correct = row["correct"] or 0
        avg_confidence = row["avg_confidence"] or 0.5

        return {
            "total": total,
            "correct": correct,
            "accuracy": correct / total if total > 0 else 0.0,
            "avg_confidence": avg_confidence,
            "calibration_error": abs((correct / total if total > 0 else 0.5) - avg_confidence),
        }

    def get_unresolved_predictions(self, limit: int = 20) -> List[Prediction]:
        """Get predictions awaiting resolution."""
        cursor = self.conn.execute(
            """
            SELECT * FROM predictions
            WHERE was_correct IS NULL
            ORDER BY deadline ASC, created_at ASC
            LIMIT ?
            """,
            (limit,),
        )
        return [Prediction.from_row(dict(row)) for row in cursor.fetchall()]

    # =========================================================================
    # INTERACTION OPERATIONS
    # =========================================================================

    def store_interaction(self, interaction: Interaction) -> int:
        """Store a conversation interaction."""
        with self.transaction() as conn:
            cursor = conn.execute(
                """
                INSERT INTO interactions (user_input, jarvis_response, feedback, session_id, timestamp, metadata)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    interaction.user_input,
                    interaction.jarvis_response,
                    interaction.feedback,
                    interaction.session_id,
                    interaction.timestamp.isoformat(),
                    json.dumps(interaction.metadata),
                ),
            )
            return cursor.lastrowid

    def update_interaction_feedback(self, interaction_id: int, feedback: str) -> bool:
        """Update feedback for an interaction."""
        with self.transaction() as conn:
            cursor = conn.execute(
                "UPDATE interactions SET feedback = ? WHERE id = ?",
                (feedback, interaction_id),
            )
            return cursor.rowcount > 0

    def get_recent_interactions(
        self, hours: int = 24, limit: int = 50
    ) -> List[Interaction]:
        """Get recent interactions."""
        cutoff = (datetime.utcnow() - timedelta(hours=hours)).isoformat()
        cursor = self.conn.execute(
            """
            SELECT * FROM interactions
            WHERE timestamp > ?
            ORDER BY timestamp DESC
            LIMIT ?
            """,
            (cutoff, limit),
        )
        return [Interaction.from_row(dict(row)) for row in cursor.fetchall()]

    def get_problematic_interactions(
        self, hours: int = 24, limit: int = 20
    ) -> List[Interaction]:
        """Get interactions with negative feedback or retries."""
        cutoff = (datetime.utcnow() - timedelta(hours=hours)).isoformat()
        cursor = self.conn.execute(
            """
            SELECT * FROM interactions
            WHERE timestamp > ?
            AND feedback IN ('negative', 'confused', 'retry')
            ORDER BY timestamp DESC
            LIMIT ?
            """,
            (cutoff, limit),
        )
        return [Interaction.from_row(dict(row)) for row in cursor.fetchall()]

    def get_session_interactions(self, session_id: str) -> List[Interaction]:
        """Get all interactions from a session."""
        cursor = self.conn.execute(
            """
            SELECT * FROM interactions
            WHERE session_id = ?
            ORDER BY timestamp ASC
            """,
            (session_id,),
        )
        return [Interaction.from_row(dict(row)) for row in cursor.fetchall()]

    # =========================================================================
    # CONTEXT BUILDING
    # =========================================================================

    def build_context(self, query: str, limit: int = 10) -> ContextBundle:
        """Build a comprehensive context bundle for a query."""
        # Extract potential entity names from query
        words = query.split()
        capitalized = [w for w in words if w and w[0].isupper()]

        # Gather facts
        facts = self.search_facts(query, limit=limit)
        for entity in capitalized:
            facts.extend(self.get_facts_about(entity, limit=5))
        # Deduplicate
        seen_facts = set()
        unique_facts = []
        for f in facts:
            key = (f.entity, f.fact)
            if key not in seen_facts:
                seen_facts.add(key)
                unique_facts.append(f)
        facts = unique_facts[:limit]

        # Gather reflections
        reflections = self.get_relevant_reflections(query, limit=5)

        # Gather recent interactions
        recent = self.get_recent_interactions(hours=2, limit=5)

        # Gather related entities
        entities = []
        for entity_name in capitalized:
            entity = self.get_entity(entity_name)
            if entity:
                entities.append(entity)

        return ContextBundle(
            query=query,
            facts=facts,
            reflections=reflections,
            recent_interactions=recent,
            related_entities=entities,
        )

    # =========================================================================
    # TRUST OPERATIONS
    # =========================================================================

    def get_trust_level(self, domain: str) -> int:
        """Get trust level for a domain."""
        cursor = self.conn.execute(
            "SELECT level FROM trust WHERE domain = ?",
            (domain,),
        )
        row = cursor.fetchone()
        return row["level"] if row else 0

    def set_trust_level(self, domain: str, level: int) -> bool:
        """Set trust level for a domain."""
        with self.transaction() as conn:
            conn.execute(
                """
                INSERT INTO trust (domain, level, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(domain) DO UPDATE SET
                    level = excluded.level,
                    updated_at = excluded.updated_at
                """,
                (domain, level, datetime.utcnow().isoformat()),
            )
            return True

    def record_trust_success(self, domain: str) -> Tuple[int, int]:
        """Record a success for trust building. Returns (successes, failures)."""
        with self.transaction() as conn:
            conn.execute(
                """
                INSERT INTO trust (domain, successes, last_success, updated_at)
                VALUES (?, 1, ?, ?)
                ON CONFLICT(domain) DO UPDATE SET
                    successes = trust.successes + 1,
                    last_success = excluded.last_success,
                    updated_at = excluded.updated_at
                """,
                (domain, datetime.utcnow().isoformat(), datetime.utcnow().isoformat()),
            )
            cursor = conn.execute(
                "SELECT successes, failures FROM trust WHERE domain = ?",
                (domain,),
            )
            row = cursor.fetchone()
            return (row["successes"], row["failures"]) if row else (1, 0)

    def record_trust_failure(self, domain: str) -> Tuple[int, int]:
        """Record a failure for trust. Returns (successes, failures)."""
        with self.transaction() as conn:
            conn.execute(
                """
                INSERT INTO trust (domain, failures, last_failure, updated_at)
                VALUES (?, 1, ?, ?)
                ON CONFLICT(domain) DO UPDATE SET
                    failures = trust.failures + 1,
                    last_failure = excluded.last_failure,
                    updated_at = excluded.updated_at
                """,
                (domain, datetime.utcnow().isoformat(), datetime.utcnow().isoformat()),
            )
            cursor = conn.execute(
                "SELECT successes, failures FROM trust WHERE domain = ?",
                (domain,),
            )
            row = cursor.fetchone()
            return (row["successes"], row["failures"]) if row else (0, 1)

    def get_all_trust_levels(self) -> Dict[str, Dict[str, Any]]:
        """Get trust levels for all domains."""
        cursor = self.conn.execute("SELECT * FROM trust")
        return {
            row["domain"]: {
                "level": row["level"],
                "successes": row["successes"],
                "failures": row["failures"],
                "last_success": row["last_success"],
                "last_failure": row["last_failure"],
            }
            for row in cursor.fetchall()
        }

    # =========================================================================
    # SETTINGS OPERATIONS
    # =========================================================================

    def get_setting(self, key: str, default: Any = None) -> Any:
        """Get a setting value."""
        cursor = self.conn.execute(
            "SELECT value FROM settings WHERE key = ?",
            (key,),
        )
        row = cursor.fetchone()
        if row is None:
            return default
        try:
            return json.loads(row["value"])
        except (json.JSONDecodeError, TypeError):
            return row["value"]

    def set_setting(self, key: str, value: Any) -> bool:
        """Set a setting value."""
        with self.transaction() as conn:
            conn.execute(
                """
                INSERT INTO settings (key, value, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET
                    value = excluded.value,
                    updated_at = excluded.updated_at
                """,
                (key, json.dumps(value), datetime.utcnow().isoformat()),
            )
            return True

    # =========================================================================
    # STATISTICS
    # =========================================================================

    def get_stats(self) -> Dict[str, Any]:
        """Get memory store statistics."""
        stats = {}

        for table in ["entities", "facts", "reflections", "predictions", "interactions"]:
            cursor = self.conn.execute(f"SELECT COUNT(*) as count FROM {table}")
            stats[f"{table}_count"] = cursor.fetchone()["count"]

        # Recent activity
        cutoff = (datetime.utcnow() - timedelta(hours=24)).isoformat()
        cursor = self.conn.execute(
            "SELECT COUNT(*) as count FROM interactions WHERE timestamp > ?",
            (cutoff,),
        )
        stats["interactions_24h"] = cursor.fetchone()["count"]

        # Prediction accuracy
        stats["prediction_accuracy"] = self.get_prediction_accuracy()

        return stats

    def close(self):
        """Close database connection."""
        if hasattr(self._local, "conn") and self._local.conn:
            self._local.conn.close()
            self._local.conn = None
