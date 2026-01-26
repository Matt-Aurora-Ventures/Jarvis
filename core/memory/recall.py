"""Core recall API for memory retrieval.

User-friendly interface wrapping hybrid search for bot systems.
"""
import logging
import asyncio
from typing import List, Dict, Any, Optional, Literal
from datetime import datetime, timedelta

from .hybrid_search import hybrid_search, HybridSearchResult
from .search import TimeFilter, SourceFilter

logger = logging.getLogger(__name__)

# Performance threshold for warning (100ms)
PERFORMANCE_THRESHOLD_MS = 100


async def recall(
    query: str,
    k: int = 10,
    time_filter: TimeFilter = "all",
    source_filter: Optional[SourceFilter] = None,
    context_filter: Optional[str] = None,
    entity_filter: Optional[str] = None,
    confidence_min: float = 0.0,
    include_embeddings: bool = False,
    exclude_assistant_outputs: bool = True,
) -> List[Dict[str, Any]]:
    """
    Recall facts from memory using hybrid search.

    Wraps hybrid_search() with async interface for bot integration.
    Uses FTS5 keyword search + optional vector semantic search.

    Args:
        query: Search query string.
        k: Maximum results to return (default 10).
        time_filter: Temporal filter ('all', 'today', 'week', 'month', 'quarter', 'year').
        source_filter: Filter by source ('telegram', 'treasury', 'x', 'bags_intel', 'buy_tracker').
        context_filter: Filter by context field (e.g., 'trade_outcome', 'user_preference').
        entity_filter: Filter by entity mention (e.g., '@KR8TIV', '@lucid').
        confidence_min: Minimum confidence threshold (0.0-1.0).
        include_embeddings: Whether to use vector search (requires PostgreSQL).
        exclude_assistant_outputs: Exclude facts marked as assistant outputs (default True).
                                   This prevents the "echo chamber" effect where LLM sees
                                   its own previous responses as external facts.

    Returns:
        List of dicts with keys:
        - id: Fact ID
        - content: Fact text
        - context: Context field
        - source: Source system
        - timestamp: Created timestamp
        - confidence: Confidence score
        - entities: Extracted entity mentions
        - relevance_score: RRF score from hybrid search

    Performance:
        Logs warning if query takes >100ms.

    Example:
        # Recent trade outcomes (excludes assistant outputs by default)
        results = await recall(
            "KR8TIV trade outcomes",
            k=5,
            time_filter="week",
            context_filter="trade_outcome"
        )

        # User preferences
        prefs = await recall(
            "risk tolerance",
            k=3,
            source_filter="telegram",
            context_filter="user_preference"
        )

        # Include assistant outputs (for debugging/context review)
        all_facts = await recall("analysis", exclude_assistant_outputs=False)
    """
    start_time = asyncio.get_event_loop().time()

    # Build query string with filters
    query_parts = [query]

    if context_filter:
        query_parts.append(context_filter)

    if entity_filter:
        query_parts.append(entity_filter)

    full_query = " ".join(query_parts)

    # Get query embedding if requested (requires PostgreSQL)
    query_embedding = None
    if include_embeddings:
        # Import here to avoid circular dependency
        from .pg_vector import get_pg_vector_store
        pg_store = get_pg_vector_store()

        if pg_store.is_available():
            try:
                # Generate embedding in thread pool (sync operation)
                from sentence_transformers import SentenceTransformer
                model = SentenceTransformer('BAAI/bge-large-en-v1.5')
                query_embedding = await asyncio.to_thread(
                    lambda: model.encode(query).tolist()
                )
            except Exception as e:
                logger.warning(f"Failed to generate query embedding: {e}")
                # Continue with FTS5-only search

    # Run hybrid search in thread pool (sync SQLite operation)
    search_results = await asyncio.to_thread(
        hybrid_search,
        query=full_query,
        query_embedding=query_embedding,
        limit=k,
        time_filter=time_filter,
        source=source_filter,
        min_confidence=confidence_min,
        exclude_assistant_outputs=exclude_assistant_outputs,
    )

    # Convert HybridSearchResult to dict format
    results = []
    for result in search_results["results"]:
        results.append({
            "id": None,  # Not exposed by hybrid_search
            "content": result.content,
            "context": result.context,
            "source": result.source,
            "timestamp": result.timestamp,
            "confidence": result.confidence,
            "entities": [],  # TODO: Extract from entity_mentions table
            "relevance_score": result.rrf_score,
        })

    # Log performance
    elapsed_ms = (asyncio.get_event_loop().time() - start_time) * 1000

    if elapsed_ms > PERFORMANCE_THRESHOLD_MS:
        logger.warning(
            f"Recall query slow: {elapsed_ms:.2f}ms (threshold: {PERFORMANCE_THRESHOLD_MS}ms) "
            f"- query: '{query[:50]}...', results: {len(results)}"
        )
    else:
        logger.debug(f"Recall query: {elapsed_ms:.2f}ms, {len(results)} results")

    return results


async def recall_by_entity(
    entity_name: str,
    k: int = 10,
    time_filter: TimeFilter = "all",
) -> List[Dict[str, Any]]:
    """
    Recall facts mentioning a specific entity.

    Args:
        entity_name: Entity to search for (e.g., '@KR8TIV', '@lucid').
        k: Maximum results to return.
        time_filter: Temporal filter.

    Returns:
        List of facts mentioning the entity.

    Example:
        # All facts about KR8TIV token
        kr8tiv_facts = await recall_by_entity("@KR8TIV", k=20, time_filter="month")
    """
    # Use entity_filter in base recall function
    return await recall(
        query=entity_name,
        k=k,
        time_filter=time_filter,
        entity_filter=entity_name,
    )


async def recall_recent(
    k: int = 10,
    source_filter: Optional[SourceFilter] = None,
) -> List[Dict[str, Any]]:
    """
    Recall most recent facts.

    Args:
        k: Maximum results to return.
        source_filter: Filter by source system.

    Returns:
        List of recent facts, sorted by timestamp descending.

    Example:
        # Recent treasury trades
        recent_trades = await recall_recent(k=5, source_filter="treasury")
    """
    from .search import get_recent_facts

    # Run in thread pool (sync operation)
    facts = await asyncio.to_thread(
        get_recent_facts,
        limit=k,
        source=source_filter,
    )

    # get_recent_facts returns a list directly, not a dict
    # Convert to recall format
    results = []
    for fact in facts:
        results.append({
            "id": fact.get("id"),
            "content": fact["content"],
            "context": fact.get("context"),
            "source": fact.get("source", "unknown"),
            "timestamp": fact.get("timestamp", ""),
            "confidence": fact.get("confidence", 1.0),
            "entities": [],  # TODO: Extract from entity_mentions
            "relevance_score": 1.0,  # Recent = always relevant
        })

    return results
