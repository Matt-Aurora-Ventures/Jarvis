"""Migration utilities for PostgreSQL archival_memory to SQLite facts."""
import json
import logging
import os
from datetime import datetime
from typing import Optional, Dict, Any, List, Tuple
from contextlib import contextmanager

from .database import get_db
from .retain import retain_fact

logger = logging.getLogger(__name__)

# Optional PostgreSQL dependencies
try:
    import psycopg2
    import psycopg2.extras
    POSTGRES_AVAILABLE = True
except ImportError:
    POSTGRES_AVAILABLE = False
    logger.warning("psycopg2 not available - PostgreSQL migration disabled")


def is_postgres_available() -> bool:
    """Check if PostgreSQL is available for migration."""
    if not POSTGRES_AVAILABLE:
        return False

    connection_url = os.getenv("DATABASE_URL")
    if not connection_url:
        return False

    # Test connection
    try:
        with get_postgres_connection() as conn:
            return conn is not None
    except Exception:
        return False


@contextmanager
def get_postgres_connection():
    """Get PostgreSQL connection context manager."""
    if not POSTGRES_AVAILABLE:
        raise RuntimeError("psycopg2 not installed")

    connection_url = os.getenv("DATABASE_URL")
    if not connection_url:
        raise RuntimeError("DATABASE_URL not set")

    conn = None
    try:
        conn = psycopg2.connect(connection_url, cursor_factory=psycopg2.extras.RealDictCursor)
        yield conn
    finally:
        if conn:
            conn.close()


def get_archival_memory_count() -> int:
    """
    Get count of entries in PostgreSQL archival_memory table.

    Returns:
        Number of entries in archival_memory.
    """
    if not is_postgres_available():
        return 0

    try:
        with get_postgres_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) as cnt FROM archival_memory")
            result = cursor.fetchone()
            return result["cnt"] if result else 0
    except Exception as e:
        logger.error(f"Failed to get archival_memory count: {e}")
        return 0


def list_archival_memories(limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
    """
    List entries from PostgreSQL archival_memory table.

    Args:
        limit: Maximum entries to return.
        offset: Offset for pagination.

    Returns:
        List of archival_memory entries.
    """
    if not is_postgres_available():
        return []

    try:
        with get_postgres_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, content, metadata, created_at
                FROM archival_memory
                ORDER BY id
                LIMIT %s OFFSET %s
            """, (limit, offset))

            rows = cursor.fetchall()
            return [dict(row) for row in rows]
    except Exception as e:
        logger.error(f"Failed to list archival_memories: {e}")
        return []


def get_migration_status() -> Dict[str, Any]:
    """
    Get current migration status.

    Returns:
        Dict with postgres_count, sqlite_count, migrated_count, pending_count.
    """
    # Get PostgreSQL count
    postgres_count = get_archival_memory_count() if is_postgres_available() else 0

    # Get SQLite counts
    db = get_db()
    conn = db._get_connection()

    # Total facts in SQLite
    sqlite_count = conn.execute(
        "SELECT COUNT(*) as cnt FROM facts"
    ).fetchone()["cnt"]

    # Facts with PostgreSQL links (already migrated)
    migrated_count = conn.execute(
        "SELECT COUNT(*) as cnt FROM fact_embeddings WHERE postgres_id IS NOT NULL"
    ).fetchone()["cnt"]

    return {
        "postgres_available": is_postgres_available(),
        "postgres_count": postgres_count,
        "sqlite_count": sqlite_count,
        "migrated_count": migrated_count,
        "pending_count": max(0, postgres_count - migrated_count),
    }


def get_migrated_postgres_ids() -> set:
    """
    Get set of PostgreSQL IDs that have already been migrated.

    Returns:
        Set of postgres_id values.
    """
    db = get_db()
    conn = db._get_connection()

    rows = conn.execute(
        "SELECT postgres_id FROM fact_embeddings WHERE postgres_id IS NOT NULL"
    ).fetchall()

    return {row["postgres_id"] for row in rows}


def migrate_single_entry(
    postgres_id: int,
    content: str,
    metadata: Optional[Dict],
    created_at: Optional[datetime] = None,
) -> int:
    """
    Migrate a single archival_memory entry to SQLite.

    Args:
        postgres_id: PostgreSQL archival_memory.id
        content: Memory content
        metadata: JSONB metadata (may contain context, tags, etc.)
        created_at: Original creation timestamp

    Returns:
        SQLite fact_id
    """
    # Extract context from metadata if present
    context = None
    source = "archival_memory"
    entities = []

    if metadata:
        if isinstance(metadata, str):
            try:
                metadata = json.loads(metadata)
            except json.JSONDecodeError:
                metadata = {}

        context = metadata.get("context")
        if not context:
            # Try other common metadata fields
            context = metadata.get("session_id") or metadata.get("type")

        # Extract tags as potential entities
        tags = metadata.get("tags", [])
        if isinstance(tags, str):
            tags = [t.strip() for t in tags.split(",")]
        entities = [f"#{tag}" for tag in tags if tag]

    # Store via retain_fact (handles SQLite insert + Markdown sync)
    fact_id = retain_fact(
        content=content,
        context=context or "migrated from archival_memory",
        entities=entities if entities else None,
        source=source,
        confidence=1.0,
        auto_extract_entities=True,  # Also extract from content
    )

    # Link to PostgreSQL ID
    db = get_db()
    with db.get_cursor() as cursor:
        cursor.execute(
            """
            INSERT OR REPLACE INTO fact_embeddings (fact_id, postgres_id)
            VALUES (?, ?)
            """,
            (fact_id, postgres_id)
        )

    return fact_id


def migrate_archival_memory(
    batch_size: int = 50,
    skip_existing: bool = True,
    verbose: bool = True,
) -> Dict[str, Any]:
    """
    Migrate all archival_memory entries from PostgreSQL to SQLite.

    Args:
        batch_size: Number of entries to fetch per batch
        skip_existing: Skip entries already migrated (idempotent)
        verbose: Print progress

    Returns:
        Dict with migrated_count, skipped_count, error_count, errors
    """
    if not is_postgres_available():
        return {
            "success": False,
            "error": "PostgreSQL not available (DATABASE_URL not set or psycopg2 not installed)",
            "migrated_count": 0,
            "skipped_count": 0,
            "error_count": 0,
        }

    # Get already migrated IDs
    existing_ids = get_migrated_postgres_ids() if skip_existing else set()

    if verbose:
        print(f"Found {len(existing_ids)} already migrated entries")

    # Track progress
    migrated_count = 0
    skipped_count = 0
    error_count = 0
    errors: List[Tuple[int, str]] = []

    # Fetch all entries from PostgreSQL
    offset = 0
    while True:
        try:
            with get_postgres_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT id, content, metadata, created_at
                    FROM archival_memory
                    ORDER BY id
                    LIMIT %s OFFSET %s
                """, (batch_size, offset))

                rows = cursor.fetchall()

                if not rows:
                    break  # No more entries

                for row in rows:
                    postgres_id = row["id"]

                    # Skip if already migrated
                    if postgres_id in existing_ids:
                        skipped_count += 1
                        continue

                    try:
                        fact_id = migrate_single_entry(
                            postgres_id=postgres_id,
                            content=row["content"],
                            metadata=row["metadata"],
                            created_at=row.get("created_at"),
                        )
                        migrated_count += 1

                        if verbose and migrated_count % 10 == 0:
                            print(f"Migrated {migrated_count} entries...")

                    except Exception as e:
                        error_count += 1
                        errors.append((postgres_id, str(e)))
                        if verbose:
                            print(f"Error migrating {postgres_id}: {e}")

                offset += batch_size

        except Exception as e:
            return {
                "success": False,
                "error": f"PostgreSQL query failed: {e}",
                "migrated_count": migrated_count,
                "skipped_count": skipped_count,
                "error_count": error_count,
                "errors": errors,
            }

    if verbose:
        print(f"\nMigration complete!")
        print(f"  Migrated: {migrated_count}")
        print(f"  Skipped (existing): {skipped_count}")
        print(f"  Errors: {error_count}")

    return {
        "success": True,
        "migrated_count": migrated_count,
        "skipped_count": skipped_count,
        "error_count": error_count,
        "errors": errors[:10] if errors else [],  # First 10 errors
    }


def verify_migration() -> Dict[str, Any]:
    """
    Verify migration completeness.

    Returns:
        Dict with verification results.
    """
    status = get_migration_status()

    # Check if all entries are migrated
    is_complete = status["pending_count"] == 0

    # Sample verification: check a few random entries
    db = get_db()
    conn = db._get_connection()

    rows = conn.execute("""
        SELECT f.id, f.content, fe.postgres_id
        FROM facts f
        JOIN fact_embeddings fe ON f.id = fe.fact_id
        WHERE fe.postgres_id IS NOT NULL
        LIMIT 5
    """).fetchall()

    sample_facts = [dict(row) for row in rows]

    return {
        "is_complete": is_complete,
        "status": status,
        "sample_facts": sample_facts,
    }
