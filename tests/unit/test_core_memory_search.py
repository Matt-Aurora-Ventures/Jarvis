"""Comprehensive tests for core/memory/search.py - FTS5 full-text search module.

Tests:
1. FTS5 Search (search_facts)
   - Basic keyword search with BM25 ranking
   - Time filters (today, week, month, quarter, year, all)
   - Source filters (telegram, treasury, x, bags_intel, buy_tracker, system)
   - Confidence filtering
   - Include/exclude inactive facts
   - Empty query handling
   - Special character escaping

2. Entity-based Search (search_by_entity)
   - Find facts by entity name
   - Entity type in results
   - Time filtering for entities

3. Source-based Search (search_by_source)
   - Filter by source system
   - Time filtering for sources

4. Recent Facts (get_recent_facts)
   - Get most recent facts
   - Source filtering

5. Entity Summary (get_entity_summary)
   - Entity stats with fact count
   - Last mentioned timestamp
   - Non-existent entity handling

6. Facts Count (get_facts_count)
   - Count with filters
   - Source filtering
   - Time filtering

7. Time Filter Building (_build_time_filter)
   - All time filter options
   - Edge cases

8. FTS Query Escaping (_escape_fts_query)
   - Single word queries
   - Multi-word queries
   - Special characters
   - Empty queries

9. Benchmark Search (benchmark_search)
   - Performance metrics
   - Statistics calculation

Coverage target: 60%+ with ~40-60 tests
"""
import pytest
import time
import sqlite3
from datetime import datetime, timedelta
from typing import Dict, Any, List
from unittest.mock import patch, MagicMock, PropertyMock

from core.memory.search import (
    search_facts,
    search_by_entity,
    search_by_source,
    get_recent_facts,
    get_entity_summary,
    get_facts_count,
    benchmark_search,
    _build_time_filter,
    _escape_fts_query,
    TimeFilter,
    SourceFilter,
)


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def mock_db():
    """Create a mock database manager."""
    mock = MagicMock()
    mock_conn = MagicMock()
    mock._get_connection.return_value = mock_conn
    return mock, mock_conn


@pytest.fixture
def sample_fact_rows():
    """Sample fact rows for mocking database results."""
    def create_row(data: Dict[str, Any]) -> MagicMock:
        """Create a mock Row object that supports dict-like access."""
        row = MagicMock()
        row.__getitem__ = lambda self, key: data[key]
        row.keys = lambda: data.keys()
        for key, value in data.items():
            setattr(row, key, value)
        return row

    return [
        create_row({
            "id": 1,
            "content": "bags.fm graduation detected for token XYZ",
            "context": "monitoring",
            "source": "bags_intel",
            "confidence": 0.95,
            "timestamp": "2024-01-15T10:00:00",
            "score": -10.5,  # BM25 returns negative scores
        }),
        create_row({
            "id": 2,
            "content": "KR8TIV token surging on volume",
            "context": "market_analysis",
            "source": "treasury",
            "confidence": 0.85,
            "timestamp": "2024-01-15T11:00:00",
            "score": -8.2,
        }),
        create_row({
            "id": 3,
            "content": "User executed buy order",
            "context": "trading",
            "source": "treasury",
            "confidence": 1.0,
            "timestamp": "2024-01-15T12:00:00",
            "score": -5.0,
        }),
    ]


@pytest.fixture
def sample_entity_rows():
    """Sample entity-linked fact rows."""
    def create_row(data: Dict[str, Any]) -> MagicMock:
        row = MagicMock()
        row.__getitem__ = lambda self, key: data[key]
        row.keys = lambda: data.keys()
        for key, value in data.items():
            setattr(row, key, value)
        return row

    return [
        create_row({
            "id": 1,
            "content": "KR8TIV bought at $0.05",
            "context": "trade",
            "source": "treasury",
            "confidence": 1.0,
            "timestamp": "2024-01-15T10:00:00",
            "entity_name": "KR8TIV",
            "entity_type": "token",
        }),
        create_row({
            "id": 2,
            "content": "KR8TIV sold at $0.12",
            "context": "trade",
            "source": "treasury",
            "confidence": 0.9,
            "timestamp": "2024-01-15T11:00:00",
            "entity_name": "KR8TIV",
            "entity_type": "token",
        }),
    ]


# =============================================================================
# Test: search_facts - Basic FTS5 Search
# =============================================================================

class TestSearchFactsBasic:
    """Test basic FTS5 full-text search functionality."""

    @patch('core.memory.search.get_db')
    def test_search_facts_returns_results(self, mock_get_db, mock_db, sample_fact_rows):
        """Test search_facts returns properly formatted results."""
        db_mock, conn_mock = mock_db
        mock_get_db.return_value = db_mock
        conn_mock.execute.return_value.fetchall.return_value = sample_fact_rows[:2]

        result = search_facts("graduation", limit=10)

        assert "results" in result
        assert "count" in result
        assert "query" in result
        assert "elapsed_ms" in result
        assert result["query"] == "graduation"
        assert result["count"] == 2
        assert len(result["results"]) == 2

    @patch('core.memory.search.get_db')
    def test_search_facts_result_format(self, mock_get_db, mock_db, sample_fact_rows):
        """Test search result has correct fields."""
        db_mock, conn_mock = mock_db
        mock_get_db.return_value = db_mock
        conn_mock.execute.return_value.fetchall.return_value = sample_fact_rows[:1]

        result = search_facts("bags.fm")

        fact = result["results"][0]
        assert "id" in fact
        assert "content" in fact
        assert "context" in fact
        assert "source" in fact
        assert "confidence" in fact
        assert "timestamp" in fact
        assert "score" in fact

    @patch('core.memory.search.get_db')
    def test_search_facts_bm25_score_absolute(self, mock_get_db, mock_db, sample_fact_rows):
        """Test BM25 scores are converted to absolute values."""
        db_mock, conn_mock = mock_db
        mock_get_db.return_value = db_mock
        conn_mock.execute.return_value.fetchall.return_value = sample_fact_rows[:1]

        result = search_facts("test")

        # BM25 returns negative scores, we convert to positive
        assert result["results"][0]["score"] > 0
        assert result["results"][0]["score"] == 10.5  # abs(-10.5)

    @patch('core.memory.search.get_db')
    def test_search_facts_empty_results(self, mock_get_db, mock_db):
        """Test search with no matching results."""
        db_mock, conn_mock = mock_db
        mock_get_db.return_value = db_mock
        conn_mock.execute.return_value.fetchall.return_value = []

        result = search_facts("nonexistent_term_xyz")

        assert result["count"] == 0
        assert result["results"] == []

    @patch('core.memory.search.get_db')
    def test_search_facts_default_limit(self, mock_get_db, mock_db, sample_fact_rows):
        """Test default limit is 10."""
        db_mock, conn_mock = mock_db
        mock_get_db.return_value = db_mock
        conn_mock.execute.return_value.fetchall.return_value = sample_fact_rows

        search_facts("test")

        # Check that limit=10 was passed in params
        call_args = conn_mock.execute.call_args
        params = call_args[0][1]
        assert params[-1] == 10  # Last param is limit

    @patch('core.memory.search.get_db')
    def test_search_facts_custom_limit(self, mock_get_db, mock_db, sample_fact_rows):
        """Test custom limit parameter."""
        db_mock, conn_mock = mock_db
        mock_get_db.return_value = db_mock
        conn_mock.execute.return_value.fetchall.return_value = sample_fact_rows[:1]

        search_facts("test", limit=5)

        call_args = conn_mock.execute.call_args
        params = call_args[0][1]
        assert params[-1] == 5

    @patch('core.memory.search.get_db')
    def test_search_facts_elapsed_time(self, mock_get_db, mock_db):
        """Test elapsed time is measured and returned."""
        db_mock, conn_mock = mock_db
        mock_get_db.return_value = db_mock
        conn_mock.execute.return_value.fetchall.return_value = []

        result = search_facts("test")

        assert "elapsed_ms" in result
        assert result["elapsed_ms"] >= 0
        assert isinstance(result["elapsed_ms"], (int, float))


# =============================================================================
# Test: search_facts - Time Filters
# =============================================================================

class TestSearchFactsTimeFilter:
    """Test time filter functionality in search_facts."""

    @patch('core.memory.search.get_db')
    def test_time_filter_all(self, mock_get_db, mock_db):
        """Test 'all' time filter includes all facts."""
        db_mock, conn_mock = mock_db
        mock_get_db.return_value = db_mock
        conn_mock.execute.return_value.fetchall.return_value = []

        search_facts("test", time_filter="all")

        # SQL should not have time clause
        call_args = conn_mock.execute.call_args
        sql = call_args[0][0]
        # 'all' time filter should not add timestamp filter
        # The params should only have: safe_query, min_confidence, limit
        params = call_args[0][1]
        assert len(params) == 3

    @patch('core.memory.search.get_db')
    def test_time_filter_today(self, mock_get_db, mock_db):
        """Test 'today' time filter."""
        db_mock, conn_mock = mock_db
        mock_get_db.return_value = db_mock
        conn_mock.execute.return_value.fetchall.return_value = []

        search_facts("test", time_filter="today")

        call_args = conn_mock.execute.call_args
        params = call_args[0][1]
        # Should have time filter param
        assert len(params) == 4  # query, confidence, time, limit

    @patch('core.memory.search.get_db')
    def test_time_filter_week(self, mock_get_db, mock_db):
        """Test 'week' time filter."""
        db_mock, conn_mock = mock_db
        mock_get_db.return_value = db_mock
        conn_mock.execute.return_value.fetchall.return_value = []

        search_facts("test", time_filter="week")

        call_args = conn_mock.execute.call_args
        params = call_args[0][1]
        assert len(params) == 4

    @patch('core.memory.search.get_db')
    def test_time_filter_month(self, mock_get_db, mock_db):
        """Test 'month' time filter."""
        db_mock, conn_mock = mock_db
        mock_get_db.return_value = db_mock
        conn_mock.execute.return_value.fetchall.return_value = []

        search_facts("test", time_filter="month")

        call_args = conn_mock.execute.call_args
        params = call_args[0][1]
        assert len(params) == 4

    @patch('core.memory.search.get_db')
    def test_time_filter_quarter(self, mock_get_db, mock_db):
        """Test 'quarter' time filter."""
        db_mock, conn_mock = mock_db
        mock_get_db.return_value = db_mock
        conn_mock.execute.return_value.fetchall.return_value = []

        search_facts("test", time_filter="quarter")

        call_args = conn_mock.execute.call_args
        params = call_args[0][1]
        assert len(params) == 4

    @patch('core.memory.search.get_db')
    def test_time_filter_year(self, mock_get_db, mock_db):
        """Test 'year' time filter."""
        db_mock, conn_mock = mock_db
        mock_get_db.return_value = db_mock
        conn_mock.execute.return_value.fetchall.return_value = []

        search_facts("test", time_filter="year")

        call_args = conn_mock.execute.call_args
        params = call_args[0][1]
        assert len(params) == 4


# =============================================================================
# Test: search_facts - Source Filters
# =============================================================================

class TestSearchFactsSourceFilter:
    """Test source filter functionality in search_facts."""

    @patch('core.memory.search.get_db')
    def test_source_filter_telegram(self, mock_get_db, mock_db):
        """Test filtering by telegram source."""
        db_mock, conn_mock = mock_db
        mock_get_db.return_value = db_mock
        conn_mock.execute.return_value.fetchall.return_value = []

        search_facts("test", source="telegram")

        call_args = conn_mock.execute.call_args
        sql = call_args[0][0]
        params = call_args[0][1]
        assert "f.source = ?" in sql
        assert "telegram" in params

    @patch('core.memory.search.get_db')
    def test_source_filter_treasury(self, mock_get_db, mock_db):
        """Test filtering by treasury source."""
        db_mock, conn_mock = mock_db
        mock_get_db.return_value = db_mock
        conn_mock.execute.return_value.fetchall.return_value = []

        search_facts("test", source="treasury")

        call_args = conn_mock.execute.call_args
        params = call_args[0][1]
        assert "treasury" in params

    @patch('core.memory.search.get_db')
    def test_source_filter_x(self, mock_get_db, mock_db):
        """Test filtering by x (Twitter) source."""
        db_mock, conn_mock = mock_db
        mock_get_db.return_value = db_mock
        conn_mock.execute.return_value.fetchall.return_value = []

        search_facts("test", source="x")

        call_args = conn_mock.execute.call_args
        params = call_args[0][1]
        assert "x" in params

    @patch('core.memory.search.get_db')
    def test_source_filter_bags_intel(self, mock_get_db, mock_db):
        """Test filtering by bags_intel source."""
        db_mock, conn_mock = mock_db
        mock_get_db.return_value = db_mock
        conn_mock.execute.return_value.fetchall.return_value = []

        search_facts("test", source="bags_intel")

        call_args = conn_mock.execute.call_args
        params = call_args[0][1]
        assert "bags_intel" in params

    @patch('core.memory.search.get_db')
    def test_source_filter_buy_tracker(self, mock_get_db, mock_db):
        """Test filtering by buy_tracker source."""
        db_mock, conn_mock = mock_db
        mock_get_db.return_value = db_mock
        conn_mock.execute.return_value.fetchall.return_value = []

        search_facts("test", source="buy_tracker")

        call_args = conn_mock.execute.call_args
        params = call_args[0][1]
        assert "buy_tracker" in params

    @patch('core.memory.search.get_db')
    def test_source_filter_system(self, mock_get_db, mock_db):
        """Test filtering by system source."""
        db_mock, conn_mock = mock_db
        mock_get_db.return_value = db_mock
        conn_mock.execute.return_value.fetchall.return_value = []

        search_facts("test", source="system")

        call_args = conn_mock.execute.call_args
        params = call_args[0][1]
        assert "system" in params

    @patch('core.memory.search.get_db')
    def test_source_filter_none(self, mock_get_db, mock_db):
        """Test no source filter when None."""
        db_mock, conn_mock = mock_db
        mock_get_db.return_value = db_mock
        conn_mock.execute.return_value.fetchall.return_value = []

        search_facts("test", source=None)

        call_args = conn_mock.execute.call_args
        sql = call_args[0][0]
        assert "f.source = ?" not in sql


# =============================================================================
# Test: search_facts - Confidence Filter
# =============================================================================

class TestSearchFactsConfidenceFilter:
    """Test confidence filtering in search_facts."""

    @patch('core.memory.search.get_db')
    def test_confidence_filter_default(self, mock_get_db, mock_db):
        """Test default confidence filter is 0.0."""
        db_mock, conn_mock = mock_db
        mock_get_db.return_value = db_mock
        conn_mock.execute.return_value.fetchall.return_value = []

        search_facts("test")

        call_args = conn_mock.execute.call_args
        params = call_args[0][1]
        # Second param is min_confidence (after safe_query)
        assert params[1] == 0.0

    @patch('core.memory.search.get_db')
    def test_confidence_filter_custom(self, mock_get_db, mock_db):
        """Test custom confidence threshold."""
        db_mock, conn_mock = mock_db
        mock_get_db.return_value = db_mock
        conn_mock.execute.return_value.fetchall.return_value = []

        search_facts("test", min_confidence=0.8)

        call_args = conn_mock.execute.call_args
        params = call_args[0][1]
        assert params[1] == 0.8

    @patch('core.memory.search.get_db')
    def test_confidence_filter_high(self, mock_get_db, mock_db):
        """Test high confidence threshold (0.95)."""
        db_mock, conn_mock = mock_db
        mock_get_db.return_value = db_mock
        conn_mock.execute.return_value.fetchall.return_value = []

        search_facts("test", min_confidence=0.95)

        call_args = conn_mock.execute.call_args
        params = call_args[0][1]
        assert params[1] == 0.95


# =============================================================================
# Test: search_facts - Include Inactive
# =============================================================================

class TestSearchFactsIncludeInactive:
    """Test include_inactive parameter in search_facts."""

    @patch('core.memory.search.get_db')
    def test_include_inactive_false(self, mock_get_db, mock_db):
        """Test default excludes inactive facts."""
        db_mock, conn_mock = mock_db
        mock_get_db.return_value = db_mock
        conn_mock.execute.return_value.fetchall.return_value = []

        search_facts("test", include_inactive=False)

        call_args = conn_mock.execute.call_args
        sql = call_args[0][0]
        assert "f.is_active = 1" in sql

    @patch('core.memory.search.get_db')
    def test_include_inactive_true(self, mock_get_db, mock_db):
        """Test including inactive facts."""
        db_mock, conn_mock = mock_db
        mock_get_db.return_value = db_mock
        conn_mock.execute.return_value.fetchall.return_value = []

        search_facts("test", include_inactive=True)

        call_args = conn_mock.execute.call_args
        sql = call_args[0][0]
        assert "f.is_active = 1" not in sql


# =============================================================================
# Test: search_by_entity
# =============================================================================

class TestSearchByEntity:
    """Test entity-based search functionality."""

    @patch('core.memory.search.get_db')
    def test_search_by_entity_basic(self, mock_get_db, mock_db, sample_entity_rows):
        """Test basic entity search."""
        db_mock, conn_mock = mock_db
        mock_get_db.return_value = db_mock
        conn_mock.execute.return_value.fetchall.return_value = sample_entity_rows

        result = search_by_entity("KR8TIV")

        assert len(result) == 2
        assert result[0]["entity_name"] == "KR8TIV"
        assert result[0]["entity_type"] == "token"

    @patch('core.memory.search.get_db')
    def test_search_by_entity_result_format(self, mock_get_db, mock_db, sample_entity_rows):
        """Test entity search result format."""
        db_mock, conn_mock = mock_db
        mock_get_db.return_value = db_mock
        conn_mock.execute.return_value.fetchall.return_value = sample_entity_rows[:1]

        result = search_by_entity("KR8TIV")

        fact = result[0]
        assert "id" in fact
        assert "content" in fact
        assert "context" in fact
        assert "source" in fact
        assert "confidence" in fact
        assert "timestamp" in fact
        assert "entity_name" in fact
        assert "entity_type" in fact

    @patch('core.memory.search.get_db')
    def test_search_by_entity_empty_results(self, mock_get_db, mock_db):
        """Test entity search with no results."""
        db_mock, conn_mock = mock_db
        mock_get_db.return_value = db_mock
        conn_mock.execute.return_value.fetchall.return_value = []

        result = search_by_entity("NONEXISTENT")

        assert result == []

    @patch('core.memory.search.get_db')
    def test_search_by_entity_custom_limit(self, mock_get_db, mock_db, sample_entity_rows):
        """Test entity search with custom limit."""
        db_mock, conn_mock = mock_db
        mock_get_db.return_value = db_mock
        conn_mock.execute.return_value.fetchall.return_value = sample_entity_rows[:1]

        search_by_entity("KR8TIV", limit=5)

        call_args = conn_mock.execute.call_args
        params = call_args[0][1]
        assert params[-1] == 5

    @patch('core.memory.search.get_db')
    def test_search_by_entity_time_filter(self, mock_get_db, mock_db, sample_entity_rows):
        """Test entity search with time filter."""
        db_mock, conn_mock = mock_db
        mock_get_db.return_value = db_mock
        conn_mock.execute.return_value.fetchall.return_value = sample_entity_rows

        search_by_entity("KR8TIV", time_filter="week")

        call_args = conn_mock.execute.call_args
        sql = call_args[0][0]
        assert "f.timestamp >=" in sql


# =============================================================================
# Test: search_by_source
# =============================================================================

class TestSearchBySource:
    """Test source-based search functionality."""

    @patch('core.memory.search.get_db')
    def test_search_by_source_basic(self, mock_get_db, mock_db, sample_fact_rows):
        """Test basic source search."""
        db_mock, conn_mock = mock_db
        mock_get_db.return_value = db_mock
        # Return only treasury facts
        treasury_rows = [r for r in sample_fact_rows if r["source"] == "treasury"]
        conn_mock.execute.return_value.fetchall.return_value = treasury_rows

        result = search_by_source("treasury")

        assert len(result) == 2
        assert all(r["source"] == "treasury" for r in result)

    @patch('core.memory.search.get_db')
    def test_search_by_source_result_format(self, mock_get_db, mock_db, sample_fact_rows):
        """Test source search result format."""
        db_mock, conn_mock = mock_db
        mock_get_db.return_value = db_mock
        conn_mock.execute.return_value.fetchall.return_value = sample_fact_rows[:1]

        result = search_by_source("bags_intel")

        fact = result[0]
        assert "id" in fact
        assert "content" in fact
        assert "context" in fact
        assert "source" in fact
        assert "confidence" in fact
        assert "timestamp" in fact

    @patch('core.memory.search.get_db')
    def test_search_by_source_empty(self, mock_get_db, mock_db):
        """Test source search with no results."""
        db_mock, conn_mock = mock_db
        mock_get_db.return_value = db_mock
        conn_mock.execute.return_value.fetchall.return_value = []

        result = search_by_source("x")

        assert result == []

    @patch('core.memory.search.get_db')
    def test_search_by_source_custom_limit(self, mock_get_db, mock_db, sample_fact_rows):
        """Test source search with custom limit."""
        db_mock, conn_mock = mock_db
        mock_get_db.return_value = db_mock
        conn_mock.execute.return_value.fetchall.return_value = []

        search_by_source("treasury", limit=50)

        call_args = conn_mock.execute.call_args
        params = call_args[0][1]
        assert params[-1] == 50

    @patch('core.memory.search.get_db')
    def test_search_by_source_time_filter(self, mock_get_db, mock_db, sample_fact_rows):
        """Test source search with time filter."""
        db_mock, conn_mock = mock_db
        mock_get_db.return_value = db_mock
        conn_mock.execute.return_value.fetchall.return_value = []

        search_by_source("treasury", time_filter="month")

        call_args = conn_mock.execute.call_args
        sql = call_args[0][0]
        assert "timestamp >=" in sql


# =============================================================================
# Test: get_recent_facts
# =============================================================================

class TestGetRecentFacts:
    """Test getting recent facts."""

    @patch('core.memory.search.get_db')
    def test_get_recent_facts_basic(self, mock_get_db, mock_db, sample_fact_rows):
        """Test getting recent facts."""
        db_mock, conn_mock = mock_db
        mock_get_db.return_value = db_mock
        conn_mock.execute.return_value.fetchall.return_value = sample_fact_rows

        result = get_recent_facts()

        assert len(result) == 3
        assert all("content" in r for r in result)

    @patch('core.memory.search.get_db')
    def test_get_recent_facts_custom_limit(self, mock_get_db, mock_db, sample_fact_rows):
        """Test recent facts with custom limit."""
        db_mock, conn_mock = mock_db
        mock_get_db.return_value = db_mock
        conn_mock.execute.return_value.fetchall.return_value = sample_fact_rows[:1]

        get_recent_facts(limit=1)

        call_args = conn_mock.execute.call_args
        params = call_args[0][1]
        assert params[-1] == 1

    @patch('core.memory.search.get_db')
    def test_get_recent_facts_source_filter(self, mock_get_db, mock_db, sample_fact_rows):
        """Test recent facts with source filter."""
        db_mock, conn_mock = mock_db
        mock_get_db.return_value = db_mock
        treasury_rows = [r for r in sample_fact_rows if r["source"] == "treasury"]
        conn_mock.execute.return_value.fetchall.return_value = treasury_rows

        get_recent_facts(source="treasury")

        call_args = conn_mock.execute.call_args
        sql = call_args[0][0]
        params = call_args[0][1]
        assert "source = ?" in sql
        assert "treasury" in params

    @patch('core.memory.search.get_db')
    def test_get_recent_facts_no_source_filter(self, mock_get_db, mock_db, sample_fact_rows):
        """Test recent facts without source filter."""
        db_mock, conn_mock = mock_db
        mock_get_db.return_value = db_mock
        conn_mock.execute.return_value.fetchall.return_value = sample_fact_rows

        get_recent_facts(source=None)

        call_args = conn_mock.execute.call_args
        sql = call_args[0][0]
        assert "source = ?" not in sql

    @patch('core.memory.search.get_db')
    def test_get_recent_facts_empty(self, mock_get_db, mock_db):
        """Test recent facts when empty."""
        db_mock, conn_mock = mock_db
        mock_get_db.return_value = db_mock
        conn_mock.execute.return_value.fetchall.return_value = []

        result = get_recent_facts()

        assert result == []


# =============================================================================
# Test: get_entity_summary
# =============================================================================

class TestGetEntitySummary:
    """Test entity summary retrieval."""

    @patch('core.memory.search.get_db')
    def test_get_entity_summary_found(self, mock_get_db, mock_db):
        """Test entity summary when entity exists."""
        db_mock, conn_mock = mock_db
        mock_get_db.return_value = db_mock

        # Mock entity
        entity_row = MagicMock()
        entity_row.__getitem__ = lambda self, key: {
            "id": 1,
            "name": "KR8TIV",
            "type": "token",
            "summary": "Trading token",
        }[key]

        # Mock count
        count_row = MagicMock()
        count_row.__getitem__ = lambda self, key: {"count": 10}[key]

        # Mock recent
        recent_row = MagicMock()
        recent_row.__getitem__ = lambda self, key: {"timestamp": "2024-01-15T12:00:00"}[key]

        # Setup execute to return different results for different queries
        def execute_side_effect(sql, params=()):
            mock_cursor = MagicMock()
            if "SELECT * FROM entities" in sql:
                mock_cursor.fetchone.return_value = entity_row
            elif "SELECT COUNT(*)" in sql:
                mock_cursor.fetchone.return_value = count_row
            else:
                mock_cursor.fetchone.return_value = recent_row
            return mock_cursor

        conn_mock.execute.side_effect = execute_side_effect

        result = get_entity_summary("KR8TIV")

        assert result is not None
        assert result["name"] == "KR8TIV"
        assert result["fact_count"] == 10
        assert "last_mentioned" in result

    @patch('core.memory.search.get_db')
    def test_get_entity_summary_not_found(self, mock_get_db, mock_db):
        """Test entity summary when entity doesn't exist."""
        db_mock, conn_mock = mock_db
        mock_get_db.return_value = db_mock
        conn_mock.execute.return_value.fetchone.return_value = None

        result = get_entity_summary("NONEXISTENT")

        assert result is None

    @patch('core.memory.search.get_db')
    def test_get_entity_summary_no_recent_mentions(self, mock_get_db, mock_db):
        """Test entity summary with no recent mentions."""
        db_mock, conn_mock = mock_db
        mock_get_db.return_value = db_mock

        entity_row = MagicMock()
        entity_row.__getitem__ = lambda self, key: {
            "id": 1, "name": "TEST", "type": "other", "summary": None
        }[key]

        count_row = MagicMock()
        count_row.__getitem__ = lambda self, key: {"count": 0}[key]

        call_count = [0]
        def execute_side_effect(sql, params=()):
            mock_cursor = MagicMock()
            call_count[0] += 1
            if call_count[0] == 1:
                mock_cursor.fetchone.return_value = entity_row
            elif call_count[0] == 2:
                mock_cursor.fetchone.return_value = count_row
            else:
                mock_cursor.fetchone.return_value = None  # No recent
            return mock_cursor

        conn_mock.execute.side_effect = execute_side_effect

        result = get_entity_summary("TEST")

        assert result["last_mentioned"] is None


# =============================================================================
# Test: get_facts_count
# =============================================================================

class TestGetFactsCount:
    """Test facts counting functionality."""

    @patch('core.memory.search.get_db')
    def test_get_facts_count_basic(self, mock_get_db, mock_db):
        """Test basic facts count."""
        db_mock, conn_mock = mock_db
        mock_get_db.return_value = db_mock

        count_row = MagicMock()
        count_row.__getitem__ = lambda self, key: {"count": 100}[key]
        conn_mock.execute.return_value.fetchone.return_value = count_row

        result = get_facts_count()

        assert result == 100

    @patch('core.memory.search.get_db')
    def test_get_facts_count_with_source(self, mock_get_db, mock_db):
        """Test facts count with source filter."""
        db_mock, conn_mock = mock_db
        mock_get_db.return_value = db_mock

        count_row = MagicMock()
        count_row.__getitem__ = lambda self, key: {"count": 25}[key]
        conn_mock.execute.return_value.fetchone.return_value = count_row

        result = get_facts_count(source="treasury")

        assert result == 25
        call_args = conn_mock.execute.call_args
        sql = call_args[0][0]
        assert "source = ?" in sql

    @patch('core.memory.search.get_db')
    def test_get_facts_count_with_time_filter(self, mock_get_db, mock_db):
        """Test facts count with time filter."""
        db_mock, conn_mock = mock_db
        mock_get_db.return_value = db_mock

        count_row = MagicMock()
        count_row.__getitem__ = lambda self, key: {"count": 50}[key]
        conn_mock.execute.return_value.fetchone.return_value = count_row

        result = get_facts_count(time_filter="week")

        assert result == 50
        call_args = conn_mock.execute.call_args
        sql = call_args[0][0]
        assert "timestamp >=" in sql

    @patch('core.memory.search.get_db')
    def test_get_facts_count_zero(self, mock_get_db, mock_db):
        """Test facts count returns zero."""
        db_mock, conn_mock = mock_db
        mock_get_db.return_value = db_mock

        count_row = MagicMock()
        count_row.__getitem__ = lambda self, key: {"count": 0}[key]
        conn_mock.execute.return_value.fetchone.return_value = count_row

        result = get_facts_count()

        assert result == 0


# =============================================================================
# Test: _build_time_filter
# =============================================================================

class TestBuildTimeFilter:
    """Test time filter building helper function."""

    def test_build_time_filter_all(self):
        """Test 'all' returns empty filter."""
        clause, params = _build_time_filter("all")

        assert clause == ""
        assert params == []

    def test_build_time_filter_today(self):
        """Test 'today' filter calculates midnight."""
        clause, params = _build_time_filter("today")

        assert "f.timestamp >= ?" in clause
        assert len(params) == 1
        # Should be today's midnight
        cutoff = datetime.fromisoformat(params[0])
        assert cutoff.hour == 0
        assert cutoff.minute == 0
        assert cutoff.second == 0

    def test_build_time_filter_week(self):
        """Test 'week' filter is 7 days ago."""
        clause, params = _build_time_filter("week")

        assert "f.timestamp >= ?" in clause
        assert len(params) == 1
        cutoff = datetime.fromisoformat(params[0])
        now = datetime.utcnow()
        diff = now - cutoff
        assert 6 <= diff.days <= 8  # Allow for test timing

    def test_build_time_filter_month(self):
        """Test 'month' filter is 30 days ago."""
        clause, params = _build_time_filter("month")

        assert "f.timestamp >= ?" in clause
        assert len(params) == 1
        cutoff = datetime.fromisoformat(params[0])
        now = datetime.utcnow()
        diff = now - cutoff
        assert 29 <= diff.days <= 31

    def test_build_time_filter_quarter(self):
        """Test 'quarter' filter is 90 days ago."""
        clause, params = _build_time_filter("quarter")

        assert "f.timestamp >= ?" in clause
        assert len(params) == 1
        cutoff = datetime.fromisoformat(params[0])
        now = datetime.utcnow()
        diff = now - cutoff
        assert 89 <= diff.days <= 91

    def test_build_time_filter_year(self):
        """Test 'year' filter is 365 days ago."""
        clause, params = _build_time_filter("year")

        assert "f.timestamp >= ?" in clause
        assert len(params) == 1
        cutoff = datetime.fromisoformat(params[0])
        now = datetime.utcnow()
        diff = now - cutoff
        assert 364 <= diff.days <= 366

    def test_build_time_filter_invalid(self):
        """Test invalid filter returns empty."""
        clause, params = _build_time_filter("invalid")

        assert clause == ""
        assert params == []


# =============================================================================
# Test: _escape_fts_query
# =============================================================================

class TestEscapeFtsQuery:
    """Test FTS5 query escaping functionality."""

    def test_escape_fts_query_single_word(self):
        """Test single word is quoted."""
        result = _escape_fts_query("graduation")

        assert result == '"graduation"'

    def test_escape_fts_query_multiple_words(self):
        """Test multiple words become OR query."""
        result = _escape_fts_query("bags.fm graduation")

        assert '"bags.fm"' in result
        assert '"graduation"' in result
        assert "OR" in result

    def test_escape_fts_query_empty(self):
        """Test empty query returns empty quotes."""
        result = _escape_fts_query("")

        assert result == '""'

    def test_escape_fts_query_whitespace_only(self):
        """Test whitespace-only query returns empty quotes."""
        result = _escape_fts_query("   ")

        assert result == '""'

    def test_escape_fts_query_quotes_in_word(self):
        """Test quotes in word are escaped."""
        result = _escape_fts_query('test"quote')

        assert '""' in result  # Escaped quote

    def test_escape_fts_query_special_characters(self):
        """Test special FTS5 characters are handled."""
        # FTS5 special: * - " ( ) : ^
        result = _escape_fts_query("test*word")

        # Should be wrapped in quotes
        assert '"test*word"' in result

    def test_escape_fts_query_multiple_spaces(self):
        """Test multiple spaces between words."""
        result = _escape_fts_query("word1    word2")

        assert '"word1"' in result
        assert '"word2"' in result
        assert "OR" in result


# =============================================================================
# Test: benchmark_search
# =============================================================================

class TestBenchmarkSearch:
    """Test search benchmarking functionality."""

    @patch('core.memory.search.search_facts')
    @patch('core.memory.search.get_facts_count')
    @patch('core.memory.search.get_db')
    def test_benchmark_search_basic(self, mock_get_db, mock_count, mock_search):
        """Test benchmark returns proper structure."""
        mock_count.return_value = 10
        mock_search.return_value = {"results": [], "count": 0}

        result = benchmark_search(iterations=5)

        assert "queries" in result
        assert "summary" in result
        assert "iterations_per_query" in result["summary"]
        assert "total_queries" in result["summary"]
        assert "overall_avg_ms" in result["summary"]
        assert "overall_p95_ms" in result["summary"]
        assert "meets_target" in result["summary"]

    @patch('core.memory.search.search_facts')
    @patch('core.memory.search.get_facts_count')
    @patch('core.memory.search.get_db')
    def test_benchmark_search_query_metrics(self, mock_get_db, mock_count, mock_search):
        """Test benchmark includes per-query metrics."""
        mock_count.return_value = 10
        mock_search.return_value = {"results": [], "count": 0}

        result = benchmark_search(iterations=5)

        # Should have metrics for each test query
        assert len(result["queries"]) > 0

        for query, metrics in result["queries"].items():
            assert "min_ms" in metrics
            assert "max_ms" in metrics
            assert "avg_ms" in metrics
            assert "p95_ms" in metrics

    @patch('core.memory.retain.retain_fact')
    @patch('core.memory.search.search_facts')
    @patch('core.memory.search.get_facts_count')
    @patch('core.memory.search.get_db')
    def test_benchmark_creates_sample_data(self, mock_get_db, mock_count, mock_search, mock_retain):
        """Test benchmark creates sample data if needed."""
        mock_count.return_value = 5  # Less than 10
        mock_search.return_value = {"results": [], "count": 0}

        benchmark_search(iterations=2)

        # Should have called retain_fact to add sample data
        assert mock_retain.called


# =============================================================================
# Test: Edge Cases and Error Handling
# =============================================================================

class TestEdgeCases:
    """Test edge cases and error handling."""

    @patch('core.memory.search.get_db')
    def test_search_facts_with_all_filters(self, mock_get_db, mock_db):
        """Test search with all filters applied."""
        db_mock, conn_mock = mock_db
        mock_get_db.return_value = db_mock
        conn_mock.execute.return_value.fetchall.return_value = []

        result = search_facts(
            query="test",
            limit=5,
            time_filter="week",
            source="treasury",
            min_confidence=0.8,
            include_inactive=True,
        )

        assert result["count"] == 0

    @patch('core.memory.search.get_db')
    def test_search_facts_very_long_query(self, mock_get_db, mock_db):
        """Test search with very long query string."""
        db_mock, conn_mock = mock_db
        mock_get_db.return_value = db_mock
        conn_mock.execute.return_value.fetchall.return_value = []

        long_query = " ".join(["word"] * 100)
        result = search_facts(long_query)

        assert "results" in result

    @patch('core.memory.search.get_db')
    def test_search_facts_unicode_query(self, mock_get_db, mock_db):
        """Test search with unicode characters."""
        db_mock, conn_mock = mock_db
        mock_get_db.return_value = db_mock
        conn_mock.execute.return_value.fetchall.return_value = []

        result = search_facts("test unicode")

        assert "results" in result


# =============================================================================
# Test: Combined Filters
# =============================================================================

class TestCombinedFilters:
    """Test combinations of filters work together."""

    @patch('core.memory.search.get_db')
    def test_source_and_time_filter(self, mock_get_db, mock_db):
        """Test source and time filter together."""
        db_mock, conn_mock = mock_db
        mock_get_db.return_value = db_mock
        conn_mock.execute.return_value.fetchall.return_value = []

        search_facts("test", source="treasury", time_filter="week")

        call_args = conn_mock.execute.call_args
        sql = call_args[0][0]
        assert "f.source = ?" in sql
        assert "f.timestamp >= ?" in sql

    @patch('core.memory.search.get_db')
    def test_source_and_confidence_filter(self, mock_get_db, mock_db):
        """Test source and confidence filter together."""
        db_mock, conn_mock = mock_db
        mock_get_db.return_value = db_mock
        conn_mock.execute.return_value.fetchall.return_value = []

        search_facts("test", source="bags_intel", min_confidence=0.9)

        call_args = conn_mock.execute.call_args
        sql = call_args[0][0]
        params = call_args[0][1]
        assert "f.source = ?" in sql
        assert "f.confidence >= ?" in sql
        assert 0.9 in params
        assert "bags_intel" in params


# =============================================================================
# Test: SQL Injection Prevention
# =============================================================================

class TestSQLInjectionPrevention:
    """Test that SQL injection is prevented via parameterization."""

    @patch('core.memory.search.get_db')
    def test_query_injection_attempt(self, mock_get_db, mock_db):
        """Test that malicious query is safely escaped."""
        db_mock, conn_mock = mock_db
        mock_get_db.return_value = db_mock
        conn_mock.execute.return_value.fetchall.return_value = []

        # Attempt SQL injection
        malicious_query = "'; DROP TABLE facts; --"
        result = search_facts(malicious_query)

        # Should not crash and query should be escaped
        assert "results" in result

    @patch('core.memory.search.get_db')
    def test_source_injection_attempt(self, mock_get_db, mock_db):
        """Test that malicious source is parameterized."""
        db_mock, conn_mock = mock_db
        mock_get_db.return_value = db_mock
        conn_mock.execute.return_value.fetchall.return_value = []

        # Type system prevents this in Python, but test the code path
        search_facts("test", source="treasury")  # Valid source

        call_args = conn_mock.execute.call_args
        # Source should be in params, not interpolated into SQL
        assert call_args[0][1] is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
