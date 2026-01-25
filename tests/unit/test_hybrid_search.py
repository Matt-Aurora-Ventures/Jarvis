"""Integration tests for PostgreSQL + SQLite hybrid search with RRF.

Tests:
1. PostgreSQL connection and graceful fallback
2. FTS5-only search when no embedding provided
3. Hybrid RRF search with mock embeddings
4. RRF score calculation correctness
5. Filter application (time, source, confidence)
6. Search explanation generation
"""
import pytest
import time
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
from typing import List

from core.memory import (
    hybrid_search,
    get_pg_vector_store,
    HybridSearchResult,
    get_search_explanation,
    retain_fact,
    get_db,
)
from core.memory.pg_vector import VectorSearchResult


@pytest.fixture
def sample_facts():
    """Create sample facts for testing."""
    db = get_db()

    # Clean slate
    conn = db._get_connection()
    conn.execute("DELETE FROM facts")
    conn.commit()

    # Insert test facts
    facts = [
        {
            "content": "bags.fm graduation detected for token XYZ with strong bonding curve",
            "context": "bags_intel_monitoring",
            "source": "bags_intel",
            "confidence": 0.95,
        },
        {
            "content": "KR8TIV token showing bullish momentum on Jupiter DEX",
            "context": "market_analysis",
            "source": "treasury",
            "confidence": 0.85,
        },
        {
            "content": "User lucid executed buy order for 1000 XYZ tokens",
            "context": "trading_history",
            "source": "treasury",
            "confidence": 1.0,
        },
        {
            "content": "Telegram alert: New graduation on bags.fm",
            "context": "user_notification",
            "source": "telegram",
            "confidence": 0.90,
        },
        {
            "content": "X post scheduled about market conditions and trading strategy",
            "context": "social_media",
            "source": "x",
            "confidence": 0.80,
        },
    ]

    for fact in facts:
        retain_fact(
            content=fact["content"],
            context=fact["context"],
            source=fact["source"],
            confidence=fact["confidence"],
        )

    yield facts

    # Cleanup
    conn.execute("DELETE FROM facts")
    conn.commit()


@pytest.fixture
def mock_embeddings():
    """Mock embeddings for testing (1024-dim vectors)."""
    # Generate simple mock embeddings
    def make_embedding(seed: int) -> List[float]:
        """Generate deterministic embedding based on seed."""
        import random
        random.seed(seed)
        return [random.random() for _ in range(1024)]

    return {
        "query": make_embedding(1),
        "fact_1": make_embedding(10),
        "fact_2": make_embedding(20),
        "fact_3": make_embedding(30),
    }


class TestPostgreSQLConnection:
    """Test PostgreSQL vector store connection and fallback."""

    def test_pg_store_creation(self):
        """Test PostgreSQL store can be created."""
        pg_store = get_pg_vector_store()
        assert pg_store is not None
        # May or may not be available depending on environment
        # Just verify it doesn't crash

    def test_pg_store_availability_check(self):
        """Test availability check works."""
        pg_store = get_pg_vector_store()
        available = pg_store.is_available()
        assert isinstance(available, bool)

    def test_graceful_fallback_no_postgres(self, sample_facts):
        """Test hybrid_search works without PostgreSQL (FTS-only fallback)."""
        # Force PostgreSQL unavailable by not providing embedding
        results = hybrid_search(
            query="graduation",
            query_embedding=None,  # No embedding = FTS-only
            limit=5,
        )

        assert results["mode"] == "fts-only"
        assert results["count"] >= 1
        assert results["fts_count"] >= 1
        assert results["vector_count"] == 0

        # Should find the graduation fact
        contents = [r.content for r in results["results"]]
        assert any("graduation" in c.lower() for c in contents)


class TestFTSOnlySearch:
    """Test FTS5-only search mode."""

    def test_fts_keyword_search(self, sample_facts):
        """Test FTS5 keyword search works correctly."""
        results = hybrid_search(
            query="bags.fm graduation",
            query_embedding=None,
            limit=5,
        )

        assert results["mode"] == "fts-only"
        assert results["count"] >= 1

        # First result should have both keywords
        top_result = results["results"][0]
        assert "bags.fm" in top_result.content.lower() or "graduation" in top_result.content.lower()
        assert top_result.fts_rank is not None
        assert top_result.vector_rank is None

    def test_fts_source_filter(self, sample_facts):
        """Test source filtering works."""
        results = hybrid_search(
            query="token",
            query_embedding=None,
            source="treasury",
            limit=10,
        )

        # All results should be from treasury
        for result in results["results"]:
            assert result.source == "treasury"

    def test_fts_time_filter(self, sample_facts):
        """Test temporal filtering works."""
        # All test facts are recent (just created), use "week" to be safe across timezones
        results = hybrid_search(
            query="token",
            query_embedding=None,
            time_filter="week",
            limit=10,
        )

        assert results["count"] >= 1  # Should find recent facts (within last week)

    def test_fts_confidence_filter(self, sample_facts):
        """Test confidence filtering works."""
        results = hybrid_search(
            query="token",
            query_embedding=None,
            min_confidence=0.90,
            limit=10,
        )

        # All results should have confidence >= 0.90
        for result in results["results"]:
            assert result.confidence >= 0.90


class TestHybridRRFSearch:
    """Test hybrid search with RRF fusion."""

    @patch('core.memory.pg_vector.PostgresVectorStore.vector_search')
    @patch('core.memory.pg_vector.PostgresVectorStore.is_available')
    def test_hybrid_mode_with_vector_results(
        self,
        mock_is_available,
        mock_vector_search,
        sample_facts,
        mock_embeddings,
    ):
        """Test hybrid mode activates when vector search returns results."""
        # Mock PostgreSQL as available
        mock_is_available.return_value = True

        # Mock vector search results
        mock_vector_search.return_value = [
            VectorSearchResult(
                content="bags.fm graduation detected for token XYZ with strong bonding curve",
                score=0.85,
                metadata={"source": "bags_intel", "confidence": 0.95},
            ),
            VectorSearchResult(
                content="KR8TIV token showing bullish momentum on Jupiter DEX",
                score=0.75,
                metadata={"source": "treasury", "confidence": 0.85},
            ),
        ]

        results = hybrid_search(
            query="graduation",
            query_embedding=mock_embeddings["query"],
            limit=5,
        )

        assert results["mode"] == "hybrid"
        assert results["vector_count"] == 2
        assert results["fts_count"] >= 1

        # Should have RRF-merged results
        assert results["count"] >= 1
        top_result = results["results"][0]
        assert top_result.rrf_score > 0

    def test_rrf_score_calculation(self):
        """Test RRF score formula is correct."""
        from core.memory.hybrid_search import _rrf_merge

        # Create mock FTS results
        fts_facts = [
            {"content": "fact A", "source": "system", "confidence": 1.0, "score": 10.0},
            {"content": "fact B", "source": "system", "confidence": 1.0, "score": 8.0},
        ]

        # Create mock vector results
        vector_results = [
            VectorSearchResult(
                content="fact B",  # Same as FTS rank 2
                score=0.90,
                metadata={"source": "system", "confidence": 1.0},
            ),
            VectorSearchResult(
                content="fact C",
                score=0.80,
                metadata={"source": "system", "confidence": 1.0},
            ),
        ]

        # RRF with k=60, equal weights (0.5/0.5)
        merged = _rrf_merge(
            fts_facts=fts_facts,
            vector_results=vector_results,
            fts_weight=0.5,
            vector_weight=0.5,
            k=60,
        )

        # fact A: FTS rank 1 → score = 0.5/(60+1) = 0.0082
        # fact B: FTS rank 2 + Vector rank 1 → score = 0.5/(60+2) + 0.5/(60+1) = 0.0163
        # fact C: Vector rank 2 → score = 0.5/(60+2) = 0.0081

        # fact B should have highest RRF score (in both lists)
        fact_b_results = [r for r in merged if r.content == "fact B"]
        assert len(fact_b_results) == 1
        fact_b = fact_b_results[0]

        assert fact_b.fts_rank == 2
        assert fact_b.vector_rank == 1
        expected_score = 0.5 / (60 + 2) + 0.5 / (60 + 1)
        assert abs(fact_b.rrf_score - expected_score) < 0.0001

    def test_rrf_weights(self):
        """Test RRF weight configuration works."""
        from core.memory.hybrid_search import _rrf_merge

        fts_facts = [
            {"content": "fact A", "source": "system", "confidence": 1.0, "score": 10.0},
        ]

        vector_results = [
            VectorSearchResult(
                content="fact B",
                score=0.90,
                metadata={"source": "system", "confidence": 1.0},
            ),
        ]

        # Heavy FTS weighting (0.8/0.2)
        merged_fts_heavy = _rrf_merge(
            fts_facts=fts_facts,
            vector_results=vector_results,
            fts_weight=0.8,
            vector_weight=0.2,
            k=60,
        )

        # Heavy vector weighting (0.2/0.8)
        merged_vector_heavy = _rrf_merge(
            fts_facts=fts_facts,
            vector_results=vector_results,
            fts_weight=0.2,
            vector_weight=0.8,
            k=60,
        )

        # fact A should score higher with FTS-heavy weighting
        fact_a_fts = [r for r in merged_fts_heavy if r.content == "fact A"][0]
        fact_a_vector = [r for r in merged_vector_heavy if r.content == "fact A"][0]
        assert fact_a_fts.rrf_score > fact_a_vector.rrf_score


class TestSearchExplanation:
    """Test search result explanation generation."""

    def test_hybrid_match_explanation(self):
        """Test explanation for hybrid match (in both FTS and vector)."""
        result = HybridSearchResult(
            content="test fact",
            context="test",
            source="system",
            confidence=1.0,
            timestamp="2024-01-01T00:00:00Z",
            rrf_score=0.0250,
            fts_rank=3,
            vector_rank=5,
            fts_bm25=8.5,
            vector_similarity=0.82,
        )

        explanation = get_search_explanation(result)

        assert "Hybrid match" in explanation
        assert "FTS rank #3" in explanation
        assert "Vector rank #5" in explanation
        assert "BM25=8.5" in explanation
        assert "Similarity=0.820" in explanation
        assert "RRF=0.0250" in explanation

    def test_keyword_only_explanation(self):
        """Test explanation for FTS-only match."""
        result = HybridSearchResult(
            content="test fact",
            context="test",
            source="system",
            confidence=1.0,
            timestamp="2024-01-01T00:00:00Z",
            rrf_score=0.0150,
            fts_rank=1,
            vector_rank=None,
            fts_bm25=12.3,
            vector_similarity=None,
        )

        explanation = get_search_explanation(result)

        assert "Keyword match" in explanation
        assert "FTS rank #1" in explanation
        assert "Vector" not in explanation or "Vector rank" not in explanation

    def test_semantic_only_explanation(self):
        """Test explanation for vector-only match."""
        result = HybridSearchResult(
            content="test fact",
            context="test",
            source="system",
            confidence=1.0,
            timestamp="2024-01-01T00:00:00Z",
            rrf_score=0.0120,
            fts_rank=None,
            vector_rank=2,
            fts_bm25=None,
            vector_similarity=0.91,
        )

        explanation = get_search_explanation(result)

        assert "Semantic match" in explanation
        assert "Vector rank #2" in explanation
        assert "FTS" not in explanation or "FTS rank" not in explanation


class TestPerformance:
    """Test search performance meets targets."""

    def test_fts_search_latency(self, sample_facts):
        """Test FTS-only search meets <100ms target."""
        iterations = 50
        times = []

        for _ in range(iterations):
            start = time.perf_counter()
            hybrid_search(
                query="graduation token",
                query_embedding=None,
                limit=10,
            )
            elapsed_ms = (time.perf_counter() - start) * 1000
            times.append(elapsed_ms)

        avg_ms = sum(times) / len(times)
        p95_ms = sorted(times)[int(0.95 * len(times))]

        # FTS5 should be very fast (<10ms typically)
        assert p95_ms < 100, f"p95 latency {p95_ms:.2f}ms exceeds 100ms target"

        print(f"\nFTS-only search performance: avg={avg_ms:.2f}ms, p95={p95_ms:.2f}ms")

    @patch('core.memory.pg_vector.PostgresVectorStore.vector_search')
    @patch('core.memory.pg_vector.PostgresVectorStore.is_available')
    def test_hybrid_search_latency(
        self,
        mock_is_available,
        mock_vector_search,
        sample_facts,
        mock_embeddings,
    ):
        """Test hybrid search meets <100ms target (FTS + mock vector)."""
        mock_is_available.return_value = True
        mock_vector_search.return_value = [
            VectorSearchResult(
                content="mock result",
                score=0.85,
                metadata={"source": "system", "confidence": 1.0},
            ),
        ]

        iterations = 50
        times = []

        for _ in range(iterations):
            start = time.perf_counter()
            hybrid_search(
                query="graduation token",
                query_embedding=mock_embeddings["query"],
                limit=10,
            )
            elapsed_ms = (time.perf_counter() - start) * 1000
            times.append(elapsed_ms)

        avg_ms = sum(times) / len(times)
        p95_ms = sorted(times)[int(0.95 * len(times))]

        # Hybrid search (FTS + RRF merge) should still be fast
        assert p95_ms < 100, f"p95 latency {p95_ms:.2f}ms exceeds 100ms target"

        print(f"\nHybrid search performance: avg={avg_ms:.2f}ms, p95={p95_ms:.2f}ms")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
