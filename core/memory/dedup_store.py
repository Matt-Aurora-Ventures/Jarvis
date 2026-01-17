"""
Unified memory storage interface for JARVIS.

Consolidates:
- X bot duplicate detection (fingerprint, topic, semantic)
- Buy tracker duplicate alerts
- Treasury state (positions, trades)
- Telegram conversation memory
- Trade learnings

Provides single interface for:
- Storing memories with TTL
- Checking for duplicates (3-layer detection)
- Retrieving memories by entity
- Automatic cleanup
"""

import sqlite3
import logging
from abc import ABC, abstractmethod
from typing import Optional, Dict, List, Any, Tuple
from dataclasses import dataclass, asdict, field
from enum import Enum
from datetime import datetime, timedelta
import hashlib
from pathlib import Path

logger = logging.getLogger("jarvis.memory.store")


class MemoryType(Enum):
    """Memory classification."""
    DUPLICATE_CONTENT = "duplicate_content"      # Tweet, message, post
    DUPLICATE_INTENT = "duplicate_intent"        # Buy pick, action
    CONVERSATION = "conversation"                # User chat history
    TRADE_LEARNINGS = "trade_learnings"         # Win/loss patterns
    USER_PROFILE = "user_profile"               # User preferences
    SYSTEM_STATE = "system_state"               # Position, order state


@dataclass
class MemoryEntry:
    """Unified memory entry."""
    content: str                                 # Text content
    memory_type: MemoryType                      # Classification
    entity_id: str                               # Token symbol, user ID, pick ID, etc.
    entity_type: str                             # "token", "user", "pick", "tweet"
    id: Optional[str] = None                     # UUID or auto-increment (set by store)
    fingerprint: Optional[str] = None            # SHA256[:16] for exact dedup
    semantic_hash: Optional[str] = None          # Concept hash for soft dedup
    topic_hash: Optional[str] = None             # Topic/entity hash for clustering
    created_at: Optional[str] = None             # ISO timestamp
    expires_at: Optional[str] = None             # TTL for cleanup
    metadata: Dict[str, Any] = field(default_factory=dict)  # Extra fields

    def __post_init__(self):
        """Generate hashes if not provided."""
        if not self.fingerprint:
            self.fingerprint = hashlib.sha256(self.content.encode()).hexdigest()[:16]
        if not self.created_at:
            self.created_at = datetime.utcnow().isoformat()


class MemoryStore(ABC):
    """Abstract memory storage interface."""

    @abstractmethod
    async def store(self, entry: MemoryEntry) -> str:
        """Store a memory entry. Returns ID."""
        pass

    @abstractmethod
    async def is_duplicate(
        self,
        content: str,
        entity_id: str,
        entity_type: str,
        memory_type: MemoryType,
        hours: int = 24,
        similarity_threshold: float = 0.8
    ) -> Tuple[bool, Optional[str]]:
        """
        Check if content is duplicate within timeframe.

        Returns (is_duplicate, reason).
        Reason examples:
        - "Exact fingerprint match"
        - "Topic duplicate (same tokens: KR8TIV)"
        - "Semantic duplicate (bullish sentiment)"
        """
        pass

    @abstractmethod
    async def get_memories(
        self,
        entity_id: str,
        memory_type: Optional[MemoryType] = None,
        limit: int = 10
    ) -> List[MemoryEntry]:
        """Get memories for an entity."""
        pass

    @abstractmethod
    async def cleanup_expired(self) -> int:
        """Delete expired memories. Returns count deleted."""
        pass

    @abstractmethod
    def get_stats(self) -> Dict[str, Any]:
        """Get store statistics."""
        pass


class SQLiteMemoryStore(MemoryStore):
    """SQLite implementation of MemoryStore."""

    def __init__(self, db_path: str = "~/.lifeos/memory.db"):
        """Initialize SQLite memory store."""
        self.db_path = Path(db_path).expanduser()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
        logger.info(f"MemoryStore initialized at {self.db_path}")

    def _get_conn(self) -> sqlite3.Connection:
        """Get database connection with row factory."""
        conn = sqlite3.connect(str(self.db_path), timeout=10.0, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        """Initialize database schema."""
        try:
            with self._get_conn() as conn:
                # Main memories table
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS memories (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        content TEXT NOT NULL,
                        memory_type TEXT NOT NULL,
                        entity_id TEXT NOT NULL,
                        entity_type TEXT NOT NULL,
                        fingerprint TEXT,
                        semantic_hash TEXT,
                        topic_hash TEXT,
                        created_at TEXT NOT NULL,
                        expires_at TEXT,
                        metadata TEXT,
                        UNIQUE(fingerprint, memory_type)
                    )
                """)

                # Create indexes for performance
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_entity
                    ON memories(entity_id, entity_type, memory_type)
                """)
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_fingerprint
                    ON memories(fingerprint, created_at)
                """)
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_semantic
                    ON memories(semantic_hash, created_at)
                """)
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_topic
                    ON memories(topic_hash, created_at)
                """)
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_expires
                    ON memories(expires_at)
                """)

                conn.commit()
                logger.debug("Memory schema initialized")

        except Exception as e:
            logger.error(f"Failed to initialize memory schema: {e}")
            raise

    async def store(self, entry: MemoryEntry) -> str:
        """Store a memory entry. Returns ID."""
        try:
            with self._get_conn() as conn:
                cursor = conn.execute("""
                    INSERT OR REPLACE INTO memories (
                        content, memory_type, entity_id, entity_type,
                        fingerprint, semantic_hash, topic_hash,
                        created_at, expires_at, metadata
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    entry.content,
                    entry.memory_type.value,
                    entry.entity_id,
                    entry.entity_type,
                    entry.fingerprint,
                    entry.semantic_hash,
                    entry.topic_hash,
                    entry.created_at,
                    entry.expires_at,
                    str(entry.metadata) if entry.metadata else None
                ))
                conn.commit()
                entry_id = str(cursor.lastrowid)
                logger.debug(f"Stored memory: {entry_id} ({entry.entity_id})")
                return entry_id

        except Exception as e:
            logger.error(f"Failed to store memory: {e}")
            raise

    async def is_duplicate(
        self,
        content: str,
        entity_id: str,
        entity_type: str,
        memory_type: MemoryType,
        hours: int = 24,
        similarity_threshold: float = 0.8
    ) -> Tuple[bool, Optional[str]]:
        """
        Check if content is duplicate within timeframe.

        3-layer detection:
        1. Exact fingerprint match (SHA256[:16])
        2. Topic hash match (same entities/concepts)
        3. Semantic similarity (word overlap ≥ threshold)
        """
        try:
            cutoff = (datetime.utcnow() - timedelta(hours=hours)).isoformat()
            fingerprint = hashlib.sha256(content.encode()).hexdigest()[:16]

            with self._get_conn() as conn:
                # Layer 1: Exact fingerprint match
                row = conn.execute("""
                    SELECT id FROM memories
                    WHERE fingerprint = ? AND memory_type = ? AND created_at > ?
                    LIMIT 1
                """, (fingerprint, memory_type.value, cutoff)).fetchone()

                if row:
                    return True, f"Exact duplicate (id: {row[0]})"

                # Layer 2: Topic hash match (entity_id match)
                # This catches "same entity, different wording" type duplicates
                # Works for any entity_type (tokens, tweets, etc.)
                row = conn.execute("""
                    SELECT id FROM memories
                    WHERE entity_id = ? AND memory_type = ?
                    AND created_at > ?
                    LIMIT 1
                """, (entity_id, memory_type.value, cutoff)).fetchone()

                if row:
                    return True, f"Topic duplicate (same entity)"

                # Layer 3: Semantic similarity (word overlap)
                # For now, simple word overlap check
                words_content = set(content.lower().split())
                if len(words_content) > 0:
                    rows = conn.execute("""
                        SELECT id, content FROM memories
                        WHERE memory_type = ? AND entity_id = ? AND created_at > ?
                        LIMIT 10
                    """, (memory_type.value, entity_id, cutoff)).fetchall()

                    for row in rows:
                        words_stored = set(row[1].lower().split())
                        overlap = len(words_content & words_stored) / max(len(words_content), len(words_stored))
                        if overlap >= similarity_threshold:
                            return True, f"Semantic duplicate ({overlap:.0%} word overlap)"

            return False, None

        except Exception as e:
            logger.error(f"Duplicate check error: {e}")
            # On error, allow (don't block)
            return False, None

    async def get_memories(
        self,
        entity_id: str,
        memory_type: Optional[MemoryType] = None,
        limit: int = 10
    ) -> List[MemoryEntry]:
        """Get memories for an entity."""
        try:
            with self._get_conn() as conn:
                if memory_type:
                    rows = conn.execute("""
                        SELECT * FROM memories
                        WHERE entity_id = ? AND memory_type = ?
                        ORDER BY created_at DESC
                        LIMIT ?
                    """, (entity_id, memory_type.value, limit)).fetchall()
                else:
                    rows = conn.execute("""
                        SELECT * FROM memories
                        WHERE entity_id = ?
                        ORDER BY created_at DESC
                        LIMIT ?
                    """, (entity_id, limit)).fetchall()

                memories = []
                for row in rows:
                    entry = MemoryEntry(
                        id=str(row["id"]),
                        content=row["content"],
                        memory_type=MemoryType(row["memory_type"]),
                        entity_id=row["entity_id"],
                        entity_type=row["entity_type"],
                        fingerprint=row["fingerprint"],
                        semantic_hash=row["semantic_hash"],
                        topic_hash=row["topic_hash"],
                        created_at=row["created_at"],
                        expires_at=row["expires_at"],
                        metadata=eval(row["metadata"]) if row["metadata"] else {}
                    )
                    memories.append(entry)

                return memories

        except Exception as e:
            logger.error(f"Failed to get memories: {e}")
            return []

    async def cleanup_expired(self) -> int:
        """Delete expired memories. Returns count deleted."""
        try:
            with self._get_conn() as conn:
                total_deleted = 0

                # Delete memories past expiration (explicit expires_at)
                cursor1 = conn.execute("""
                    DELETE FROM memories
                    WHERE expires_at IS NOT NULL AND expires_at < ?
                """, (datetime.utcnow().isoformat(),))
                total_deleted += cursor1.rowcount

                # Also delete old duplicate detection entries (>24h old)
                cutoff = (datetime.utcnow() - timedelta(hours=24)).isoformat()
                cursor2 = conn.execute("""
                    DELETE FROM memories
                    WHERE memory_type = ? AND created_at < ?
                """, (MemoryType.DUPLICATE_CONTENT.value, cutoff))
                total_deleted += cursor2.rowcount

                conn.commit()
                logger.info(f"Cleaned up {total_deleted} expired memories")
                return total_deleted

        except Exception as e:
            logger.error(f"Cleanup failed: {e}")
            return 0

    def get_stats(self) -> Dict[str, Any]:
        """Get store statistics."""
        try:
            with self._get_conn() as conn:
                total = conn.execute("SELECT COUNT(*) FROM memories").fetchone()[0]
                by_type = {}
                for mtype in MemoryType:
                    count = conn.execute(
                        "SELECT COUNT(*) FROM memories WHERE memory_type = ?",
                        (mtype.value,)
                    ).fetchone()[0]
                    by_type[mtype.name] = count

                return {
                    "total_entries": total,
                    "by_type": by_type,
                    "db_size_bytes": self.db_path.stat().st_size if self.db_path.exists() else 0
                }

        except Exception as e:
            logger.error(f"Failed to get stats: {e}")
            return {"error": str(e)}


# Singleton accessor
_memory_store: Optional[MemoryStore] = None


def get_memory_store() -> MemoryStore:
    """Get global memory store instance."""
    global _memory_store
    if not _memory_store:
        _memory_store = SQLiteMemoryStore(db_path="~/.lifeos/memory.db")
    return _memory_store


def set_memory_store(store: MemoryStore) -> None:
    """Set memory store (for testing)."""
    global _memory_store
    _memory_store = store
