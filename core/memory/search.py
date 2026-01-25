"""FTS5 full-text search for Jarvis memory system."""
import time
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Literal

from .database import get_db


# Type aliases
TimeFilter = Literal["all", "today", "week", "month", "quarter", "year"]
SourceFilter = Literal["telegram", "treasury", "x", "bags_intel", "buy_tracker", "system", None]


def search_facts(
    query: str,
    limit: int = 10,
    time_filter: TimeFilter = "all",
    source: Optional[SourceFilter] = None,
    min_confidence: float = 0.0,
    include_inactive: bool = False,
) -> Dict[str, Any]:
    """
    Search facts using FTS5 full-text search with BM25 ranking.

    Args:
        query: Search query (FTS5 syntax supported).
        limit: Maximum results to return (default 10).
        time_filter: Temporal filter ('all', 'today', 'week', 'month', 'quarter', 'year').
        source: Filter by source system.
        min_confidence: Minimum confidence threshold (0.0-1.0).
        include_inactive: Include soft-deleted facts.

    Returns:
        Dict with 'results' (list of facts), 'count', 'query', 'elapsed_ms'.

    Example:
        results = search_facts("bags.fm graduation", limit=5, time_filter="week")
    """
    db = get_db()
    start_time = time.perf_counter()

    # Build time filter
    time_clause, time_params = _build_time_filter(time_filter)

    # Build source filter
    source_clause = ""
    source_params: List[Any] = []
    if source:
        source_clause = "AND f.source = ?"
        source_params = [source]

    # Build active filter
    active_clause = "" if include_inactive else "AND f.is_active = 1"

    # Escape special FTS5 characters in query
    safe_query = _escape_fts_query(query)

    conn = db._get_connection()
    # Query using FTS5 with BM25 ranking
    sql = f"""
        SELECT
            f.id,
            f.content,
            f.context,
            f.source,
            f.confidence,
            f.timestamp,
            bm25(facts_fts) as score
        FROM facts_fts fts
        JOIN facts f ON fts.rowid = f.id
        WHERE facts_fts MATCH ?
        AND f.confidence >= ?
        {time_clause}
        {source_clause}
        {active_clause}
        ORDER BY bm25(facts_fts)
        LIMIT ?
    """

    params = [safe_query, min_confidence] + time_params + source_params + [limit]
    rows = conn.execute(sql, params).fetchall()

    results = [
        {
            "id": row["id"],
            "content": row["content"],
            "context": row["context"],
            "source": row["source"],
            "confidence": row["confidence"],
            "timestamp": row["timestamp"],
            "score": abs(row["score"]),  # BM25 returns negative scores
        }
        for row in rows
    ]

    elapsed_ms = (time.perf_counter() - start_time) * 1000

    # Return metadata-wrapped results
    return {
        "results": results,
        "count": len(results),
        "query": query,
        "elapsed_ms": round(elapsed_ms, 2),
    }


def search_by_entity(
    entity_name: str,
    limit: int = 20,
    time_filter: TimeFilter = "all",
) -> List[Dict[str, Any]]:
    """
    Get all facts mentioning a specific entity.

    Args:
        entity_name: Entity name (e.g., '@KR8TIV', 'lucid').
        limit: Maximum results.
        time_filter: Temporal filter.

    Returns:
        List of facts linked to this entity.
    """
    db = get_db()

    time_clause, time_params = _build_time_filter(time_filter)

    conn = db._get_connection()
    sql = f"""
        SELECT
            f.id,
            f.content,
            f.context,
            f.source,
            f.confidence,
            f.timestamp,
            e.name as entity_name,
            e.type as entity_type
        FROM facts f
        JOIN entity_mentions em ON f.id = em.fact_id
        JOIN entities e ON em.entity_id = e.id
        WHERE e.name = ?
        AND f.is_active = 1
        {time_clause}
        ORDER BY f.timestamp DESC
        LIMIT ?
    """

    params = [entity_name] + time_params + [limit]
    rows = conn.execute(sql, params).fetchall()

    return [
        {
            "id": row["id"],
            "content": row["content"],
            "context": row["context"],
            "source": row["source"],
            "confidence": row["confidence"],
            "timestamp": row["timestamp"],
            "entity_name": row["entity_name"],
            "entity_type": row["entity_type"],
        }
        for row in rows
    ]


def search_by_source(
    source: SourceFilter,
    limit: int = 20,
    time_filter: TimeFilter = "all",
) -> List[Dict[str, Any]]:
    """
    Get facts from a specific source system.

    Args:
        source: Source system name.
        limit: Maximum results.
        time_filter: Temporal filter.

    Returns:
        List of facts from this source.
    """
    db = get_db()

    time_clause, time_params = _build_time_filter(time_filter)

    conn = db._get_connection()
    sql = f"""
        SELECT
            id,
            content,
            context,
            source,
            confidence,
            timestamp
        FROM facts
        WHERE source = ?
        AND is_active = 1
        {time_clause}
        ORDER BY timestamp DESC
        LIMIT ?
    """

    params = [source] + time_params + [limit]
    rows = conn.execute(sql, params).fetchall()

    return [
        {
            "id": row["id"],
            "content": row["content"],
            "context": row["context"],
            "source": row["source"],
            "confidence": row["confidence"],
            "timestamp": row["timestamp"],
        }
        for row in rows
    ]


def get_recent_facts(
    limit: int = 20,
    source: Optional[SourceFilter] = None,
) -> List[Dict[str, Any]]:
    """
    Get most recent facts.

    Args:
        limit: Maximum results.
        source: Optional source filter.

    Returns:
        List of recent facts.
    """
    db = get_db()

    source_clause = ""
    source_params: List[Any] = []
    if source:
        source_clause = "AND source = ?"
        source_params = [source]

    conn = db._get_connection()
    sql = f"""
        SELECT
            id,
            content,
            context,
            source,
            confidence,
            timestamp
        FROM facts
        WHERE is_active = 1
        {source_clause}
        ORDER BY timestamp DESC
        LIMIT ?
    """

    params = source_params + [limit]
    rows = conn.execute(sql, params).fetchall()

    return [dict(row) for row in rows]


def get_entity_summary(entity_name: str) -> Optional[Dict[str, Any]]:
    """
    Get entity with fact count and recent activity.

    Args:
        entity_name: Entity name.

    Returns:
        Entity dict with summary stats, or None if not found.
    """
    db = get_db()

    conn = db._get_connection()
    # Get entity
    entity = conn.execute(
        "SELECT * FROM entities WHERE name = ?",
        (entity_name,)
    ).fetchone()

    if not entity:
        return None

    # Get fact count
    count = conn.execute(
        """
        SELECT COUNT(*) as count FROM entity_mentions
        WHERE entity_id = ?
        """,
        (entity["id"],)
    ).fetchone()["count"]

    # Get most recent fact
    recent = conn.execute(
        """
        SELECT f.timestamp FROM facts f
        JOIN entity_mentions em ON f.id = em.fact_id
        WHERE em.entity_id = ?
        ORDER BY f.timestamp DESC
        LIMIT 1
        """,
        (entity["id"],)
    ).fetchone()

    return {
        "id": entity["id"],
        "name": entity["name"],
        "type": entity["type"],
        "summary": entity["summary"],
        "fact_count": count,
        "last_mentioned": recent["timestamp"] if recent else None,
    }


def get_facts_count(
    source: Optional[SourceFilter] = None,
    time_filter: TimeFilter = "all",
) -> int:
    """
    Get count of facts matching filters.

    Args:
        source: Optional source filter.
        time_filter: Temporal filter.

    Returns:
        Count of matching facts.
    """
    db = get_db()

    time_clause, time_params = _build_time_filter(time_filter)

    source_clause = ""
    source_params: List[Any] = []
    if source:
        source_clause = "AND source = ?"
        source_params = [source]

    conn = db._get_connection()
    sql = f"""
        SELECT COUNT(*) as count FROM facts
        WHERE is_active = 1
        {time_clause}
        {source_clause}
    """

    params = time_params + source_params
    result = conn.execute(sql, params).fetchone()
    return result["count"]


def _build_time_filter(time_filter: TimeFilter) -> tuple:
    """
    Build SQL time filter clause.

    Returns:
        Tuple of (sql_clause, params).
    """
    now = datetime.utcnow()

    if time_filter == "all":
        return "", []
    elif time_filter == "today":
        cutoff = now.replace(hour=0, minute=0, second=0, microsecond=0)
    elif time_filter == "week":
        cutoff = now - timedelta(days=7)
    elif time_filter == "month":
        cutoff = now - timedelta(days=30)
    elif time_filter == "quarter":
        cutoff = now - timedelta(days=90)
    elif time_filter == "year":
        cutoff = now - timedelta(days=365)
    else:
        return "", []

    return "AND f.timestamp >= ?", [cutoff.isoformat()]


def _escape_fts_query(query: str) -> str:
    """
    Escape special FTS5 characters in query.

    FTS5 special characters: * - " ( ) : ^

    Args:
        query: Raw query string.

    Returns:
        Escaped query safe for FTS5 MATCH.
    """
    # For simple queries, just wrap tokens in quotes to match literally
    # This avoids issues with special characters

    # Split on whitespace, wrap each term in quotes
    tokens = query.split()

    # Filter out empty tokens
    tokens = [t for t in tokens if t.strip()]

    if not tokens:
        return '""'  # Empty query

    # For single word, use as-is (common case)
    if len(tokens) == 1:
        # Escape quotes within the token
        token = tokens[0].replace('"', '""')
        return f'"{token}"'

    # For multiple words, create phrase or OR query
    escaped_tokens = [t.replace('"', '""') for t in tokens]

    # Use OR to match any term (more flexible than phrase)
    return " OR ".join(f'"{t}"' for t in escaped_tokens)


def benchmark_search(iterations: int = 100) -> Dict[str, Any]:
    """
    Benchmark search performance.

    Args:
        iterations: Number of iterations per query type.

    Returns:
        Dict with timing statistics.
    """
    import statistics
    from .retain import retain_fact

    db = get_db()

    # Ensure we have some data
    fact_count = get_facts_count()
    if fact_count < 10:
        # Add sample data for benchmarking
        sample_facts = [
            "bags.fm graduation detected for token XYZ",
            "Strong bonding curve activity on KR8TIV",
            "User lucid executed trade on Jupiter",
            "Telegram command received for portfolio check",
            "X post scheduled about market conditions",
        ]
        for content in sample_facts:
            retain_fact(content, context="benchmark", source="system")

    queries = [
        "bags.fm",
        "graduation",
        "trade",
        "KR8TIV",
        "bonding curve",
    ]

    results = {"queries": {}, "summary": {}}
    all_times = []

    for query in queries:
        times = []
        for _ in range(iterations):
            start = time.perf_counter()
            search_facts(query, limit=10)
            elapsed = (time.perf_counter() - start) * 1000
            times.append(elapsed)

        results["queries"][query] = {
            "min_ms": round(min(times), 2),
            "max_ms": round(max(times), 2),
            "avg_ms": round(statistics.mean(times), 2),
            "p95_ms": round(sorted(times)[int(0.95 * len(times))], 2),
        }
        all_times.extend(times)

    results["summary"] = {
        "iterations_per_query": iterations,
        "total_queries": len(queries) * iterations,
        "overall_avg_ms": round(statistics.mean(all_times), 2),
        "overall_p95_ms": round(sorted(all_times)[int(0.95 * len(all_times))], 2),
        "meets_target": sorted(all_times)[int(0.95 * len(all_times))] < 100,
    }

    return results
