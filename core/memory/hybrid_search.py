"""Hybrid search combining FTS5 (keyword) + pgvector (semantic) with RRF.

RRF (Reciprocal Rank Fusion) merges ranked lists from different sources:
- FTS5: Fast keyword-based BM25 search (SQLite)
- Vector: Semantic similarity search (PostgreSQL pgvector)

Formula: RRF_score = Σ 1 / (k + rank_i) for each source
Default k=60 (standard RRF constant)

Benefits:
- Best of both: keyword precision + semantic understanding
- Graceful degradation: works with just FTS5 if PostgreSQL unavailable
- Proven effectiveness: used by search engines, RAG systems
"""
import logging
from typing import List, Dict, Any, Optional, Literal
from dataclasses import dataclass

from .search import search_facts, TimeFilter, SourceFilter
from .pg_vector import get_pg_vector_store, VectorSearchResult

logger = logging.getLogger(__name__)


@dataclass
class HybridSearchResult:
    """Result from hybrid search with RRF scoring."""
    content: str
    context: Optional[str]
    source: str
    confidence: float
    timestamp: str
    rrf_score: float
    fts_rank: Optional[int]  # Rank in FTS5 results (1-based, None if not in FTS5)
    vector_rank: Optional[int]  # Rank in vector results (1-based, None if not in vector)
    fts_bm25: Optional[float]  # Original BM25 score from FTS5
    vector_similarity: Optional[float]  # Original cosine similarity from vector search


def hybrid_search(
    query: str,
    query_embedding: Optional[List[float]] = None,
    limit: int = 10,
    time_filter: TimeFilter = "all",
    source: Optional[SourceFilter] = None,
    min_confidence: float = 0.0,
    fts_weight: float = 0.5,
    vector_weight: float = 0.5,
    rrf_k: int = 60,
    exclude_assistant_outputs: bool = True,
) -> Dict[str, Any]:
    """
    Hybrid search combining FTS5 keyword search and vector semantic search.

    Uses Reciprocal Rank Fusion (RRF) to merge results from both sources.

    Args:
        query: Search query string.
        query_embedding: Optional pre-computed query embedding (1024-dim BGE vector).
                         If None and PostgreSQL available, will skip vector search.
        limit: Maximum results to return.
        time_filter: Temporal filter ('all', 'today', 'week', 'month', 'quarter', 'year').
        source: Filter by source system.
        min_confidence: Minimum confidence threshold (0.0-1.0).
        fts_weight: Weight for FTS5 results in RRF (default 0.5).
        vector_weight: Weight for vector results in RRF (default 0.5).
        rrf_k: RRF constant (default 60, standard value).
        exclude_assistant_outputs: Exclude facts marked as assistant outputs (default True).
                                   This prevents the "echo chamber" effect.

    Returns:
        Dict with 'results' (HybridSearchResult list), 'count', 'query', 'elapsed_ms',
        'mode' (hybrid|fts-only), 'fts_count', 'vector_count'.

    Example:
        # With embedding
        results = hybrid_search("bags.fm graduation", query_embedding=embedding, limit=5)

        # FTS-only fallback (no embedding provided)
        results = hybrid_search("bags.fm graduation", limit=5)
    """
    import time
    start_time = time.perf_counter()

    # 1. FTS5 keyword search
    fts_results = search_facts(
        query=query,
        limit=limit * 2,  # Get more candidates for RRF
        time_filter=time_filter,
        source=source,
        exclude_assistant_outputs=exclude_assistant_outputs,
        min_confidence=min_confidence,
    )

    fts_facts = fts_results["results"]
    fts_count = len(fts_facts)

    # 2. Vector search (if embedding provided and PostgreSQL available)
    vector_results: List[VectorSearchResult] = []
    pg_store = get_pg_vector_store()

    if query_embedding and pg_store.is_available():
        vector_results = pg_store.vector_search(
            query_embedding=query_embedding,
            limit=limit * 2,  # Get more candidates for RRF
            similarity_threshold=0.3,  # Filter low-similarity matches
        )

    vector_count = len(vector_results)

    # 3. RRF fusion
    if vector_count > 0:
        # Hybrid mode: merge FTS + vector with RRF
        merged = _rrf_merge(
            fts_facts=fts_facts,
            vector_results=vector_results,
            fts_weight=fts_weight,
            vector_weight=vector_weight,
            k=rrf_k,
        )
        mode = "hybrid"
    else:
        # FTS-only fallback
        merged = _fts_only_results(fts_facts)
        mode = "fts-only"

    # 4. Apply time/source/confidence filters to merged results
    # (FTS5 already filtered, but vector results need filtering)
    if time_filter != "all" or source or min_confidence > 0.0:
        merged = _apply_filters(
            merged,
            time_filter=time_filter,
            source=source,
            min_confidence=min_confidence,
        )

    # 5. Sort by RRF score and limit
    merged.sort(key=lambda x: x.rrf_score, reverse=True)
    merged = merged[:limit]

    elapsed_ms = (time.perf_counter() - start_time) * 1000

    return {
        "results": merged,
        "count": len(merged),
        "query": query,
        "elapsed_ms": round(elapsed_ms, 2),
        "mode": mode,
        "fts_count": fts_count,
        "vector_count": vector_count,
    }


def _rrf_merge(
    fts_facts: List[Dict[str, Any]],
    vector_results: List[VectorSearchResult],
    fts_weight: float,
    vector_weight: float,
    k: int,
) -> List[HybridSearchResult]:
    """
    Merge FTS5 and vector results using Reciprocal Rank Fusion.

    RRF formula: score = Σ weight_i / (k + rank_i)

    Args:
        fts_facts: Results from FTS5 search.
        vector_results: Results from vector search.
        fts_weight: Weight for FTS5 contribution.
        vector_weight: Weight for vector contribution.
        k: RRF constant (typically 60).

    Returns:
        List of HybridSearchResult with RRF scores.
    """
    # Create lookup maps
    content_to_result: Dict[str, HybridSearchResult] = {}

    # Process FTS5 results (rank 1-based)
    for rank, fact in enumerate(fts_facts, start=1):
        content = fact["content"]
        rrf_score = fts_weight / (k + rank)

        content_to_result[content] = HybridSearchResult(
            content=content,
            context=fact.get("context"),
            source=fact.get("source", "unknown"),
            confidence=fact.get("confidence", 1.0),
            timestamp=fact.get("timestamp", ""),
            rrf_score=rrf_score,
            fts_rank=rank,
            vector_rank=None,
            fts_bm25=fact.get("score"),
            vector_similarity=None,
        )

    # Process vector results (rank 1-based)
    for rank, vec_result in enumerate(vector_results, start=1):
        content = vec_result.content
        rrf_contribution = vector_weight / (k + rank)

        if content in content_to_result:
            # Already seen in FTS5, boost score
            content_to_result[content].rrf_score += rrf_contribution
            content_to_result[content].vector_rank = rank
            content_to_result[content].vector_similarity = vec_result.score
        else:
            # New result from vector search only
            content_to_result[content] = HybridSearchResult(
                content=content,
                context=vec_result.metadata.get("context"),
                source=vec_result.metadata.get("source", "unknown"),
                confidence=vec_result.metadata.get("confidence", 1.0),
                timestamp=vec_result.metadata.get("created_at", ""),
                rrf_score=rrf_contribution,
                fts_rank=None,
                vector_rank=rank,
                fts_bm25=None,
                vector_similarity=vec_result.score,
            )

    return list(content_to_result.values())


def _fts_only_results(fts_facts: List[Dict[str, Any]]) -> List[HybridSearchResult]:
    """
    Convert FTS5 results to HybridSearchResult format (FTS-only fallback).

    Args:
        fts_facts: Results from FTS5 search.

    Returns:
        List of HybridSearchResult with FTS-only data.
    """
    results = []
    for rank, fact in enumerate(fts_facts, start=1):
        results.append(
            HybridSearchResult(
                content=fact["content"],
                context=fact.get("context"),
                source=fact.get("source", "unknown"),
                confidence=fact.get("confidence", 1.0),
                timestamp=fact.get("timestamp", ""),
                rrf_score=fact.get("score", 0.0),  # Use BM25 as RRF score
                fts_rank=rank,
                vector_rank=None,
                fts_bm25=fact.get("score"),
                vector_similarity=None,
            )
        )
    return results


def _apply_filters(
    results: List[HybridSearchResult],
    time_filter: TimeFilter,
    source: Optional[SourceFilter],
    min_confidence: float,
) -> List[HybridSearchResult]:
    """
    Apply filters to hybrid search results.

    FTS5 results already filtered, but vector-only results need filtering.

    Args:
        results: Hybrid search results.
        time_filter: Temporal filter.
        source: Source filter.
        min_confidence: Minimum confidence.

    Returns:
        Filtered results.
    """
    from datetime import datetime, timedelta

    filtered = []

    # Calculate time cutoff
    now = datetime.utcnow()
    cutoff = None

    if time_filter == "today":
        cutoff = now.replace(hour=0, minute=0, second=0, microsecond=0)
    elif time_filter == "week":
        cutoff = now - timedelta(days=7)
    elif time_filter == "month":
        cutoff = now - timedelta(days=30)
    elif time_filter == "quarter":
        cutoff = now - timedelta(days=90)
    elif time_filter == "year":
        cutoff = now - timedelta(days=365)

    for result in results:
        # Source filter
        if source and result.source != source:
            continue

        # Confidence filter
        if result.confidence < min_confidence:
            continue

        # Time filter
        if cutoff and result.timestamp:
            try:
                ts = datetime.fromisoformat(result.timestamp.replace("Z", "+00:00"))
                if ts < cutoff:
                    continue
            except (ValueError, AttributeError):
                # Invalid timestamp, skip filter
                pass

        filtered.append(result)

    return filtered


def get_search_explanation(result: HybridSearchResult) -> str:
    """
    Generate human-readable explanation of why this result ranked.

    Args:
        result: Hybrid search result.

    Returns:
        Explanation string.
    """
    parts = []

    if result.fts_rank and result.vector_rank:
        parts.append(f"Hybrid match: FTS rank #{result.fts_rank}, Vector rank #{result.vector_rank}")
    elif result.fts_rank:
        parts.append(f"Keyword match (FTS rank #{result.fts_rank})")
    elif result.vector_rank:
        parts.append(f"Semantic match (Vector rank #{result.vector_rank})")

    if result.fts_bm25:
        parts.append(f"BM25={result.fts_bm25:.2f}")

    if result.vector_similarity:
        parts.append(f"Similarity={result.vector_similarity:.3f}")

    parts.append(f"RRF={result.rrf_score:.4f}")

    return " | ".join(parts)
