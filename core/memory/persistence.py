"""
Long-term Memory Persistence - Durable storage for memories with semantic retrieval.

Features:
- SQLite-based persistent storage
- Embedding-based semantic search
- Memory consolidation and summarization
- Knowledge graph relationships
- Importance scoring and decay
"""

import asyncio
import hashlib
import json
import logging
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple
import uuid

logger = logging.getLogger(__name__)


class MemoryType(Enum):
    """Types of long-term memories."""
    FACT = "fact"           # Factual knowledge
    EVENT = "event"         # Past events
    PREFERENCE = "preference"  # User preferences
    SKILL = "skill"         # Learned procedures
    RELATIONSHIP = "relationship"  # Entity relationships
    INSIGHT = "insight"     # Derived conclusions


class MemoryPriority(Enum):
    """Priority levels for memory retention."""
    CRITICAL = 5    # Never forget
    HIGH = 4        # Very important
    NORMAL = 3      # Standard importance
    LOW = 2         # Can be forgotten if needed
    TRANSIENT = 1   # Short-term only


@dataclass
class LongTermMemory:
    """A persistent memory entry."""
    content: str
    memory_type: MemoryType
    priority: MemoryPriority = MemoryPriority.NORMAL
    source: str = "system"
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    embedding: Optional[List[float]] = None
    related_ids: List[str] = field(default_factory=list)

    # Timestamps
    created_at: datetime = field(default_factory=datetime.utcnow)
    accessed_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)

    # Metrics
    access_count: int = 0
    importance_score: float = 0.5
    confidence: float = 1.0

    # Identity
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    content_hash: str = ""

    def __post_init__(self):
        if not self.content_hash:
            self.content_hash = hashlib.sha256(self.content.encode()).hexdigest()[:16]


@dataclass
class MemorySearchResult:
    """Result from memory search."""
    memory: LongTermMemory
    relevance_score: float
    match_type: str  # "exact", "semantic", "tag", "related"


@dataclass
class ConsolidationResult:
    """Result of memory consolidation."""
    memories_processed: int
    memories_merged: int
    memories_archived: int
    memories_deleted: int
    summary_created: bool


class MemoryStore:
    """
    SQLite-backed persistent memory storage.

    Usage:
        store = MemoryStore("path/to/memory.db")
        await store.initialize()

        # Store memory
        memory = LongTermMemory(
            content="User prefers dark mode",
            memory_type=MemoryType.PREFERENCE,
            priority=MemoryPriority.HIGH,
        )
        await store.save(memory)

        # Search memories
        results = await store.search("dark mode preference")
    """

    def __init__(
        self,
        db_path: Path,
        embedding_fn: Optional[Callable[[str], List[float]]] = None,
    ):
        self.db_path = Path(db_path)
        self._embedding_fn = embedding_fn
        self._conn: Optional[sqlite3.Connection] = None

    async def initialize(self) -> None:
        """Initialize the database schema."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row

        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS memories (
                id TEXT PRIMARY KEY,
                content TEXT NOT NULL,
                content_hash TEXT NOT NULL,
                memory_type TEXT NOT NULL,
                priority INTEGER NOT NULL,
                source TEXT,
                tags TEXT,
                metadata TEXT,
                embedding BLOB,
                related_ids TEXT,
                created_at TEXT NOT NULL,
                accessed_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                access_count INTEGER DEFAULT 0,
                importance_score REAL DEFAULT 0.5,
                confidence REAL DEFAULT 1.0,
                is_archived INTEGER DEFAULT 0
            );

            CREATE INDEX IF NOT EXISTS idx_memory_type ON memories(memory_type);
            CREATE INDEX IF NOT EXISTS idx_priority ON memories(priority);
            CREATE INDEX IF NOT EXISTS idx_created_at ON memories(created_at);
            CREATE INDEX IF NOT EXISTS idx_content_hash ON memories(content_hash);
            CREATE INDEX IF NOT EXISTS idx_is_archived ON memories(is_archived);

            CREATE TABLE IF NOT EXISTS memory_relations (
                source_id TEXT NOT NULL,
                target_id TEXT NOT NULL,
                relation_type TEXT NOT NULL,
                strength REAL DEFAULT 1.0,
                created_at TEXT NOT NULL,
                PRIMARY KEY (source_id, target_id, relation_type),
                FOREIGN KEY (source_id) REFERENCES memories(id),
                FOREIGN KEY (target_id) REFERENCES memories(id)
            );

            CREATE TABLE IF NOT EXISTS consolidation_log (
                id TEXT PRIMARY KEY,
                timestamp TEXT NOT NULL,
                memories_processed INTEGER,
                memories_merged INTEGER,
                memories_archived INTEGER,
                memories_deleted INTEGER,
                summary_id TEXT
            );
        """)
        self._conn.commit()
        logger.info(f"Initialized memory store at {self.db_path}")

    async def close(self) -> None:
        """Close the database connection."""
        if self._conn:
            self._conn.close()
            self._conn = None

    async def save(self, memory: LongTermMemory) -> str:
        """Save a memory to the store."""
        if not self._conn:
            raise RuntimeError("Store not initialized")

        # Generate embedding if function provided
        if self._embedding_fn and not memory.embedding:
            try:
                memory.embedding = self._embedding_fn(memory.content)
            except Exception as e:
                logger.warning(f"Failed to generate embedding: {e}")

        embedding_blob = (
            json.dumps(memory.embedding).encode()
            if memory.embedding else None
        )

        self._conn.execute("""
            INSERT OR REPLACE INTO memories (
                id, content, content_hash, memory_type, priority, source,
                tags, metadata, embedding, related_ids, created_at,
                accessed_at, updated_at, access_count, importance_score, confidence
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            memory.id,
            memory.content,
            memory.content_hash,
            memory.memory_type.value,
            memory.priority.value,
            memory.source,
            json.dumps(memory.tags),
            json.dumps(memory.metadata),
            embedding_blob,
            json.dumps(memory.related_ids),
            memory.created_at.isoformat(),
            memory.accessed_at.isoformat(),
            memory.updated_at.isoformat(),
            memory.access_count,
            memory.importance_score,
            memory.confidence,
        ))
        self._conn.commit()

        logger.debug(f"Saved memory {memory.id}: {memory.content[:50]}...")
        return memory.id

    async def get(self, memory_id: str) -> Optional[LongTermMemory]:
        """Get a memory by ID."""
        if not self._conn:
            raise RuntimeError("Store not initialized")

        cursor = self._conn.execute(
            "SELECT * FROM memories WHERE id = ?", (memory_id,)
        )
        row = cursor.fetchone()

        if not row:
            return None

        memory = self._row_to_memory(row)

        # Update access tracking
        self._conn.execute("""
            UPDATE memories SET
                accessed_at = ?,
                access_count = access_count + 1
            WHERE id = ?
        """, (datetime.utcnow().isoformat(), memory_id))
        self._conn.commit()

        return memory

    async def search(
        self,
        query: str,
        memory_type: Optional[MemoryType] = None,
        tags: Optional[List[str]] = None,
        min_priority: MemoryPriority = MemoryPriority.TRANSIENT,
        limit: int = 10,
        include_archived: bool = False,
    ) -> List[MemorySearchResult]:
        """Search memories by content and filters."""
        if not self._conn:
            raise RuntimeError("Store not initialized")

        results = []

        # Build base query
        where_clauses = ["is_archived = 0" if not include_archived else "1=1"]
        params: List[Any] = []

        if memory_type:
            where_clauses.append("memory_type = ?")
            params.append(memory_type.value)

        where_clauses.append("priority >= ?")
        params.append(min_priority.value)

        # Full-text search on content
        where_clauses.append("content LIKE ?")
        params.append(f"%{query}%")

        sql = f"""
            SELECT * FROM memories
            WHERE {' AND '.join(where_clauses)}
            ORDER BY importance_score DESC, accessed_at DESC
            LIMIT ?
        """
        params.append(limit)

        cursor = self._conn.execute(sql, params)

        for row in cursor.fetchall():
            memory = self._row_to_memory(row)

            # Calculate relevance
            relevance = self._calculate_relevance(query, memory)

            # Filter by tags if specified
            if tags and not any(t in memory.tags for t in tags):
                continue

            results.append(MemorySearchResult(
                memory=memory,
                relevance_score=relevance,
                match_type="content",
            ))

        # Sort by relevance
        results.sort(key=lambda r: r.relevance_score, reverse=True)
        return results[:limit]

    async def search_semantic(
        self,
        query: str,
        limit: int = 10,
        threshold: float = 0.7,
    ) -> List[MemorySearchResult]:
        """Search memories using semantic similarity."""
        if not self._embedding_fn:
            logger.warning("No embedding function configured for semantic search")
            return await self.search(query, limit=limit)

        if not self._conn:
            raise RuntimeError("Store not initialized")

        try:
            query_embedding = self._embedding_fn(query)
        except Exception as e:
            logger.error(f"Failed to generate query embedding: {e}")
            return await self.search(query, limit=limit)

        results = []
        cursor = self._conn.execute(
            "SELECT * FROM memories WHERE embedding IS NOT NULL AND is_archived = 0"
        )

        for row in cursor.fetchall():
            memory = self._row_to_memory(row)
            if not memory.embedding:
                continue

            # Calculate cosine similarity
            similarity = self._cosine_similarity(query_embedding, memory.embedding)

            if similarity >= threshold:
                results.append(MemorySearchResult(
                    memory=memory,
                    relevance_score=similarity,
                    match_type="semantic",
                ))

        results.sort(key=lambda r: r.relevance_score, reverse=True)
        return results[:limit]

    async def get_related(
        self,
        memory_id: str,
        relation_type: Optional[str] = None,
    ) -> List[Tuple[LongTermMemory, str, float]]:
        """Get memories related to the given memory."""
        if not self._conn:
            raise RuntimeError("Store not initialized")

        where = "source_id = ?"
        params: List[Any] = [memory_id]

        if relation_type:
            where += " AND relation_type = ?"
            params.append(relation_type)

        cursor = self._conn.execute(f"""
            SELECT m.*, r.relation_type, r.strength
            FROM memory_relations r
            JOIN memories m ON r.target_id = m.id
            WHERE {where}
            ORDER BY r.strength DESC
        """, params)

        results = []
        for row in cursor.fetchall():
            memory = self._row_to_memory(row)
            relation = row["relation_type"]
            strength = row["strength"]
            results.append((memory, relation, strength))

        return results

    async def add_relation(
        self,
        source_id: str,
        target_id: str,
        relation_type: str,
        strength: float = 1.0,
    ) -> None:
        """Add a relationship between memories."""
        if not self._conn:
            raise RuntimeError("Store not initialized")

        self._conn.execute("""
            INSERT OR REPLACE INTO memory_relations
            (source_id, target_id, relation_type, strength, created_at)
            VALUES (?, ?, ?, ?, ?)
        """, (source_id, target_id, relation_type, strength, datetime.utcnow().isoformat()))
        self._conn.commit()

    async def delete(self, memory_id: str) -> bool:
        """Delete a memory."""
        if not self._conn:
            raise RuntimeError("Store not initialized")

        cursor = self._conn.execute(
            "DELETE FROM memories WHERE id = ?", (memory_id,)
        )
        self._conn.execute(
            "DELETE FROM memory_relations WHERE source_id = ? OR target_id = ?",
            (memory_id, memory_id)
        )
        self._conn.commit()

        return cursor.rowcount > 0

    async def archive(self, memory_id: str) -> bool:
        """Archive a memory (soft delete)."""
        if not self._conn:
            raise RuntimeError("Store not initialized")

        cursor = self._conn.execute(
            "UPDATE memories SET is_archived = 1 WHERE id = ?", (memory_id,)
        )
        self._conn.commit()
        return cursor.rowcount > 0

    async def consolidate(
        self,
        older_than_days: int = 30,
        summarize_fn: Optional[Callable[[List[str]], str]] = None,
    ) -> ConsolidationResult:
        """
        Consolidate old memories to reduce storage.

        - Merges similar memories
        - Archives low-importance memories
        - Creates summary memories for groups
        """
        if not self._conn:
            raise RuntimeError("Store not initialized")

        cutoff = datetime.utcnow() - timedelta(days=older_than_days)
        result = ConsolidationResult(
            memories_processed=0,
            memories_merged=0,
            memories_archived=0,
            memories_deleted=0,
            summary_created=False,
        )

        # Find old, low-priority memories
        cursor = self._conn.execute("""
            SELECT * FROM memories
            WHERE created_at < ?
            AND priority <= ?
            AND is_archived = 0
            ORDER BY memory_type, created_at
        """, (cutoff.isoformat(), MemoryPriority.LOW.value))

        memories_by_type: Dict[str, List[LongTermMemory]] = {}
        for row in cursor.fetchall():
            memory = self._row_to_memory(row)
            result.memories_processed += 1

            mem_type = memory.memory_type.value
            if mem_type not in memories_by_type:
                memories_by_type[mem_type] = []
            memories_by_type[mem_type].append(memory)

        # Process each type
        for mem_type, memories in memories_by_type.items():
            if len(memories) < 3:
                continue

            # Create summary if function provided
            if summarize_fn and len(memories) >= 5:
                contents = [m.content for m in memories]
                try:
                    summary = summarize_fn(contents)

                    summary_memory = LongTermMemory(
                        content=summary,
                        memory_type=MemoryType(mem_type),
                        priority=MemoryPriority.NORMAL,
                        source="consolidation",
                        metadata={
                            "consolidated_from": [m.id for m in memories],
                            "original_count": len(memories),
                        },
                    )
                    await self.save(summary_memory)
                    result.summary_created = True
                    result.memories_merged += len(memories)

                    # Archive originals
                    for memory in memories:
                        await self.archive(memory.id)
                        result.memories_archived += 1

                except Exception as e:
                    logger.error(f"Consolidation summarization failed: {e}")
            else:
                # Archive low-access memories
                for memory in memories:
                    if memory.access_count < 2:
                        await self.archive(memory.id)
                        result.memories_archived += 1

        # Log consolidation
        self._conn.execute("""
            INSERT INTO consolidation_log
            (id, timestamp, memories_processed, memories_merged,
             memories_archived, memories_deleted)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            str(uuid.uuid4()),
            datetime.utcnow().isoformat(),
            result.memories_processed,
            result.memories_merged,
            result.memories_archived,
            result.memories_deleted,
        ))
        self._conn.commit()

        logger.info(f"Consolidation complete: {result}")
        return result

    async def get_stats(self) -> Dict[str, Any]:
        """Get memory store statistics."""
        if not self._conn:
            raise RuntimeError("Store not initialized")

        stats = {
            "total_memories": 0,
            "active_memories": 0,
            "archived_memories": 0,
            "by_type": {},
            "by_priority": {},
            "total_relations": 0,
            "avg_importance": 0,
            "avg_access_count": 0,
        }

        # Total counts
        cursor = self._conn.execute("SELECT COUNT(*) FROM memories")
        stats["total_memories"] = cursor.fetchone()[0]

        cursor = self._conn.execute("SELECT COUNT(*) FROM memories WHERE is_archived = 0")
        stats["active_memories"] = cursor.fetchone()[0]

        stats["archived_memories"] = stats["total_memories"] - stats["active_memories"]

        # By type
        cursor = self._conn.execute("""
            SELECT memory_type, COUNT(*) FROM memories
            WHERE is_archived = 0 GROUP BY memory_type
        """)
        stats["by_type"] = dict(cursor.fetchall())

        # By priority
        cursor = self._conn.execute("""
            SELECT priority, COUNT(*) FROM memories
            WHERE is_archived = 0 GROUP BY priority
        """)
        stats["by_priority"] = dict(cursor.fetchall())

        # Relations
        cursor = self._conn.execute("SELECT COUNT(*) FROM memory_relations")
        stats["total_relations"] = cursor.fetchone()[0]

        # Averages
        cursor = self._conn.execute("""
            SELECT AVG(importance_score), AVG(access_count)
            FROM memories WHERE is_archived = 0
        """)
        row = cursor.fetchone()
        stats["avg_importance"] = row[0] or 0
        stats["avg_access_count"] = row[1] or 0

        return stats

    def _row_to_memory(self, row: sqlite3.Row) -> LongTermMemory:
        """Convert a database row to LongTermMemory."""
        embedding = None
        if row["embedding"]:
            try:
                embedding = json.loads(row["embedding"].decode())
            except Exception:
                pass

        return LongTermMemory(
            id=row["id"],
            content=row["content"],
            content_hash=row["content_hash"],
            memory_type=MemoryType(row["memory_type"]),
            priority=MemoryPriority(row["priority"]),
            source=row["source"],
            tags=json.loads(row["tags"]) if row["tags"] else [],
            metadata=json.loads(row["metadata"]) if row["metadata"] else {},
            embedding=embedding,
            related_ids=json.loads(row["related_ids"]) if row["related_ids"] else [],
            created_at=datetime.fromisoformat(row["created_at"]),
            accessed_at=datetime.fromisoformat(row["accessed_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
            access_count=row["access_count"],
            importance_score=row["importance_score"],
            confidence=row["confidence"],
        )

    def _calculate_relevance(self, query: str, memory: LongTermMemory) -> float:
        """Calculate relevance score for a memory."""
        query_lower = query.lower()
        content_lower = memory.content.lower()

        # Exact match
        if query_lower in content_lower:
            base_score = 0.8
        else:
            # Partial word matching
            query_words = set(query_lower.split())
            content_words = set(content_lower.split())
            overlap = len(query_words & content_words)
            base_score = overlap / max(len(query_words), 1) * 0.6

        # Boost by importance
        importance_boost = memory.importance_score * 0.2

        # Boost by recency
        age_days = (datetime.utcnow() - memory.accessed_at).days
        recency_boost = max(0, (30 - age_days) / 30) * 0.1

        # Boost by access frequency
        frequency_boost = min(memory.access_count / 10, 0.1)

        return min(base_score + importance_boost + recency_boost + frequency_boost, 1.0)

    def _cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """Calculate cosine similarity between two vectors."""
        if len(vec1) != len(vec2):
            return 0.0

        dot_product = sum(a * b for a, b in zip(vec1, vec2))
        norm1 = sum(a * a for a in vec1) ** 0.5
        norm2 = sum(b * b for b in vec2) ** 0.5

        if norm1 == 0 or norm2 == 0:
            return 0.0

        return dot_product / (norm1 * norm2)


# Singleton instance
_store: Optional[MemoryStore] = None


def get_memory_store(db_path: Optional[Path] = None) -> MemoryStore:
    """Get the global memory store instance."""
    global _store
    if _store is None:
        path = db_path or Path("data/memory/long_term.db")
        _store = MemoryStore(path)
    return _store
