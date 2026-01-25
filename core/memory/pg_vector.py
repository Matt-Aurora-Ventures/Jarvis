"""PostgreSQL vector integration for semantic search.

Integrates with existing archival_memory table for hybrid search:
- FTS5 (keyword-based) via SQLite
- pgvector (semantic) via PostgreSQL
- Hybrid RRF (Reciprocal Rank Fusion) for best results

Graceful fallback: If PostgreSQL unavailable, FTS5 continues working.
"""
import logging
import os
from typing import Optional, List, Dict, Any, Literal
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Optional PostgreSQL dependencies
try:
    import psycopg2
    import psycopg2.extras
    POSTGRES_AVAILABLE = True
except ImportError:
    POSTGRES_AVAILABLE = False
    logger.warning("psycopg2 not available - PostgreSQL vector search disabled")


@dataclass
class VectorSearchResult:
    """Result from vector similarity search."""
    content: str
    score: float  # Cosine similarity (0-1, higher is better)
    metadata: Dict[str, Any]


class PostgresVectorStore:
    """PostgreSQL vector store with pgvector for semantic search."""

    def __init__(self, connection_url: Optional[str] = None):
        """
        Initialize PostgreSQL vector store.

        Args:
            connection_url: PostgreSQL connection string (defaults to DATABASE_URL env var).
        """
        self.connection_url = connection_url or os.getenv("DATABASE_URL")
        self._conn: Optional[Any] = None
        self._available = False

        if not POSTGRES_AVAILABLE:
            logger.warning("psycopg2 not installed - PostgreSQL vector search disabled")
            return

        if not self.connection_url:
            logger.warning("DATABASE_URL not set - PostgreSQL vector search disabled")
            return

        # Test connection
        try:
            self._connect()
            self._available = True
            logger.info("PostgreSQL vector store initialized")
        except Exception as e:
            logger.warning(f"PostgreSQL connection failed: {e}")
            self._available = False

    def _connect(self) -> Any:
        """Get or create PostgreSQL connection."""
        if self._conn is None or self._conn.closed:
            self._conn = psycopg2.connect(self.connection_url)
            self._conn.set_session(autocommit=False)
        return self._conn

    def is_available(self) -> bool:
        """Check if PostgreSQL vector store is available."""
        return self._available

    def vector_search(
        self,
        query_embedding: List[float],
        limit: int = 10,
        similarity_threshold: float = 0.0,
    ) -> List[VectorSearchResult]:
        """
        Search for similar content using vector embeddings.

        Args:
            query_embedding: Query vector (1024-dim BGE embedding).
            limit: Maximum results to return.
            similarity_threshold: Minimum cosine similarity (0-1).

        Returns:
            List of VectorSearchResult ordered by similarity (highest first).
        """
        if not self.is_available():
            logger.debug("PostgreSQL unavailable, returning empty vector results")
            return []

        try:
            conn = self._connect()
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

            # Query archival_memory with vector similarity
            # Using cosine similarity operator <=>
            sql = """
                SELECT
                    id,
                    content,
                    metadata,
                    session_id,
                    created_at,
                    1 - (embedding <=> %s::vector) as similarity
                FROM archival_memory
                WHERE embedding IS NOT NULL
                AND 1 - (embedding <=> %s::vector) >= %s
                ORDER BY embedding <=> %s::vector
                LIMIT %s
            """

            # Convert embedding to PostgreSQL vector format
            embedding_str = "[" + ",".join(str(x) for x in query_embedding) + "]"

            cur.execute(
                sql,
                (embedding_str, embedding_str, similarity_threshold, embedding_str, limit)
            )

            rows = cur.fetchall()
            cur.close()

            results = [
                VectorSearchResult(
                    content=row["content"],
                    score=float(row["similarity"]),
                    metadata={
                        "id": row["id"],
                        "session_id": row["session_id"],
                        "created_at": row["created_at"].isoformat() if row["created_at"] else None,
                        **(row["metadata"] or {}),
                    }
                )
                for row in rows
            ]

            logger.debug(f"Vector search returned {len(results)} results")
            return results

        except Exception as e:
            logger.error(f"Vector search failed: {e}")
            return []

    def get_fact_embedding(self, fact_id: int) -> Optional[List[float]]:
        """
        Get embedding for a fact from PostgreSQL.

        Args:
            fact_id: SQLite fact ID to look up.

        Returns:
            Embedding vector if found, None otherwise.
        """
        if not self.is_available():
            return None

        try:
            conn = self._connect()
            cur = conn.cursor()

            # Check fact_embeddings table
            sql = """
                SELECT embedding
                FROM fact_embeddings
                WHERE fact_id = %s
            """

            cur.execute(sql, (fact_id,))
            row = cur.fetchone()
            cur.close()

            if row and row[0]:
                # PostgreSQL returns vector as string, parse it
                return [float(x) for x in row[0].strip("[]").split(",")]

            return None

        except Exception as e:
            logger.error(f"Failed to get fact embedding: {e}")
            return None

    def close(self):
        """Close PostgreSQL connection."""
        if self._conn and not self._conn.closed:
            self._conn.close()


# Global instance
_pg_vector_store: Optional[PostgresVectorStore] = None


def get_pg_vector_store() -> PostgresVectorStore:
    """
    Get or create global PostgreSQL vector store.

    Returns:
        Global PostgresVectorStore singleton.
    """
    global _pg_vector_store
    if _pg_vector_store is None:
        _pg_vector_store = PostgresVectorStore()
    return _pg_vector_store
