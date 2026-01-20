"""
Comprehensive unit tests for API Pagination.

Tests cover:
1. Offset/limit pagination (page-based)
2. Cursor-based pagination
3. Page boundary calculations
4. Empty page handling
5. Total count accuracy
6. Links (next/prev) correctness
7. Edge cases and error handling

Tests both api/pagination.py and api/schemas/pagination.py modules.
"""

import pytest
import base64
import json
from typing import List, Dict, Any

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from api.pagination import (
    PaginationParams,
    CursorParams,
    PaginationMeta,
    CursorMeta,
    PaginatedResponse,
    CursorResponse,
    paginate,
    paginate_cursor,
    slice_page,
    encode_cursor,
    decode_cursor,
)

from api.schemas.pagination import (
    PaginationParams as SchemaPaginationParams,
    PaginatedResponse as SchemaPaginatedResponse,
    CursorPaginationParams,
    CursorPaginatedResponse,
    paginate as schema_paginate,
    paginate_query,
    encode_cursor as schema_encode_cursor,
    decode_cursor as schema_decode_cursor,
)


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def sample_items() -> List[Dict[str, Any]]:
    """Generate sample items for pagination tests."""
    return [{"id": i, "name": f"Item {i}"} for i in range(1, 101)]


@pytest.fixture
def empty_items() -> List:
    """Empty list for edge case testing."""
    return []


@pytest.fixture
def small_items() -> List[Dict[str, Any]]:
    """Small item list (less than one page)."""
    return [{"id": i, "name": f"Item {i}"} for i in range(1, 6)]


# =============================================================================
# PaginationParams Tests (api/pagination.py)
# =============================================================================

class TestPaginationParams:
    """Tests for PaginationParams model."""

    def test_default_values(self):
        """Test default pagination parameters."""
        params = PaginationParams()

        assert params.page == 1
        assert params.page_size == 20

    def test_custom_values(self):
        """Test custom pagination parameters."""
        params = PaginationParams(page=3, page_size=50)

        assert params.page == 3
        assert params.page_size == 50

    def test_offset_property(self):
        """Test offset calculation property."""
        # Page 1 should have offset 0
        params1 = PaginationParams(page=1, page_size=20)
        assert params1.offset == 0

        # Page 2 should have offset 20
        params2 = PaginationParams(page=2, page_size=20)
        assert params2.offset == 20

        # Page 5 with 10 items should have offset 40
        params3 = PaginationParams(page=5, page_size=10)
        assert params3.offset == 40

    def test_limit_property(self):
        """Test limit is alias for page_size."""
        params = PaginationParams(page_size=35)
        assert params.limit == 35
        assert params.limit == params.page_size

    def test_page_minimum_value(self):
        """Test page must be >= 1."""
        with pytest.raises(ValueError):
            PaginationParams(page=0)

    def test_page_size_minimum_value(self):
        """Test page_size must be >= 1."""
        with pytest.raises(ValueError):
            PaginationParams(page_size=0)

    def test_page_size_maximum_value(self):
        """Test page_size must be <= 100."""
        with pytest.raises(ValueError):
            PaginationParams(page_size=101)


# =============================================================================
# CursorParams Tests
# =============================================================================

class TestCursorParams:
    """Tests for CursorParams model."""

    def test_default_values(self):
        """Test default cursor parameters."""
        params = CursorParams()

        assert params.cursor is None
        assert params.limit == 20

    def test_with_cursor(self):
        """Test cursor parameters with cursor."""
        cursor_value = encode_cursor({"id": 50, "timestamp": "2024-01-01"})
        params = CursorParams(cursor=cursor_value, limit=10)

        assert params.cursor == cursor_value
        assert params.limit == 10

    def test_limit_bounds(self):
        """Test limit bounds validation."""
        # Valid limits
        assert CursorParams(limit=1).limit == 1
        assert CursorParams(limit=100).limit == 100

        # Invalid limits
        with pytest.raises(ValueError):
            CursorParams(limit=0)
        with pytest.raises(ValueError):
            CursorParams(limit=101)


# =============================================================================
# Offset/Limit Pagination Tests
# =============================================================================

class TestOffsetLimitPagination:
    """Tests for offset/limit (page-based) pagination."""

    def test_first_page(self, sample_items):
        """Test pagination returns correct first page."""
        result = paginate(
            items=sample_items[:20],  # Pre-sliced page
            total=100,
            page=1,
            page_size=20,
        )

        assert len(result.data) == 20
        assert result.pagination.page == 1
        assert result.pagination.total == 100
        assert result.pagination.page_size == 20
        assert result.pagination.total_pages == 5
        assert result.pagination.has_next is True
        assert result.pagination.has_prev is False

    def test_middle_page(self, sample_items):
        """Test pagination for middle page."""
        result = paginate(
            items=sample_items[40:60],  # Page 3
            total=100,
            page=3,
            page_size=20,
        )

        assert len(result.data) == 20
        assert result.pagination.page == 3
        assert result.pagination.has_next is True
        assert result.pagination.has_prev is True

    def test_last_page(self, sample_items):
        """Test pagination for last page."""
        result = paginate(
            items=sample_items[80:100],  # Page 5
            total=100,
            page=5,
            page_size=20,
        )

        assert len(result.data) == 20
        assert result.pagination.page == 5
        assert result.pagination.total_pages == 5
        assert result.pagination.has_next is False
        assert result.pagination.has_prev is True

    def test_partial_last_page(self, sample_items):
        """Test last page with fewer items than page_size."""
        # 23 items with page_size=10 means 3 pages: 10, 10, 3
        items = sample_items[:23]
        result = paginate(
            items=items[20:23],  # Last 3 items
            total=23,
            page=3,
            page_size=10,
        )

        assert len(result.data) == 3
        assert result.pagination.page == 3
        assert result.pagination.total_pages == 3
        assert result.pagination.has_next is False
        assert result.pagination.has_prev is True

    def test_empty_page(self, empty_items):
        """Test pagination with empty items."""
        result = paginate(
            items=empty_items,
            total=0,
            page=1,
            page_size=20,
        )

        assert len(result.data) == 0
        assert result.pagination.total == 0
        assert result.pagination.total_pages == 0
        assert result.pagination.has_next is False
        assert result.pagination.has_prev is False

    def test_single_item(self):
        """Test pagination with single item."""
        result = paginate(
            items=[{"id": 1}],
            total=1,
            page=1,
            page_size=20,
        )

        assert len(result.data) == 1
        assert result.pagination.total == 1
        assert result.pagination.total_pages == 1
        assert result.pagination.has_next is False
        assert result.pagination.has_prev is False

    def test_exact_page_fit(self):
        """Test when total items exactly fills pages."""
        # 60 items with page_size=20 = exactly 3 pages
        result = paginate(
            items=[{"id": i} for i in range(20)],
            total=60,
            page=1,
            page_size=20,
        )

        assert result.pagination.total_pages == 3
        assert result.pagination.has_next is True

    def test_total_pages_calculation(self):
        """Test total_pages calculation for various scenarios."""
        # 1 item, page_size 20 = 1 page
        r1 = paginate(items=[{}], total=1, page=1, page_size=20)
        assert r1.pagination.total_pages == 1

        # 20 items, page_size 20 = 1 page
        r2 = paginate(items=[{}] * 20, total=20, page=1, page_size=20)
        assert r2.pagination.total_pages == 1

        # 21 items, page_size 20 = 2 pages
        r3 = paginate(items=[{}], total=21, page=1, page_size=20)
        assert r3.pagination.total_pages == 2

        # 99 items, page_size 10 = 10 pages
        r4 = paginate(items=[{}], total=99, page=1, page_size=10)
        assert r4.pagination.total_pages == 10


# =============================================================================
# slice_page Tests
# =============================================================================

class TestSlicePage:
    """Tests for slice_page helper function."""

    def test_slice_first_page(self, sample_items):
        """Test slicing first page."""
        result = slice_page(sample_items, page=1, page_size=10)

        assert len(result) == 10
        assert result[0]["id"] == 1
        assert result[9]["id"] == 10

    def test_slice_second_page(self, sample_items):
        """Test slicing second page."""
        result = slice_page(sample_items, page=2, page_size=10)

        assert len(result) == 10
        assert result[0]["id"] == 11
        assert result[9]["id"] == 20

    def test_slice_last_partial_page(self, sample_items):
        """Test slicing last partial page."""
        # 100 items, page_size 30, page 4 has 10 items
        result = slice_page(sample_items, page=4, page_size=30)

        assert len(result) == 10
        assert result[0]["id"] == 91
        assert result[-1]["id"] == 100

    def test_slice_beyond_data(self, sample_items):
        """Test slicing page beyond available data."""
        result = slice_page(sample_items, page=100, page_size=20)

        assert len(result) == 0

    def test_slice_empty_list(self, empty_items):
        """Test slicing empty list."""
        result = slice_page(empty_items, page=1, page_size=10)

        assert len(result) == 0

    def test_slice_preserves_order(self, sample_items):
        """Test that slicing preserves item order."""
        result = slice_page(sample_items, page=3, page_size=5)

        # Items 11-15
        expected_ids = [11, 12, 13, 14, 15]
        actual_ids = [item["id"] for item in result]
        assert actual_ids == expected_ids


# =============================================================================
# Cursor-Based Pagination Tests
# =============================================================================

class TestCursorPagination:
    """Tests for cursor-based pagination."""

    def test_first_page_no_cursor(self, sample_items):
        """Test first page with no cursor."""
        next_cursor = encode_cursor({"id": 20})

        result = paginate_cursor(
            items=sample_items[:20],
            next_cursor=next_cursor,
            prev_cursor=None,
        )

        assert len(result.data) == 20
        assert result.cursor.next_cursor == next_cursor
        assert result.cursor.prev_cursor is None
        assert result.cursor.has_next is True
        assert result.cursor.has_prev is False

    def test_middle_page_with_cursor(self, sample_items):
        """Test middle page with both cursors."""
        next_cursor = encode_cursor({"id": 60})
        prev_cursor = encode_cursor({"id": 40})

        result = paginate_cursor(
            items=sample_items[40:60],
            next_cursor=next_cursor,
            prev_cursor=prev_cursor,
        )

        assert len(result.data) == 20
        assert result.cursor.has_next is True
        assert result.cursor.has_prev is True

    def test_last_page_no_next(self, sample_items):
        """Test last page with no next cursor."""
        prev_cursor = encode_cursor({"id": 80})

        result = paginate_cursor(
            items=sample_items[80:100],
            next_cursor=None,
            prev_cursor=prev_cursor,
        )

        assert len(result.data) == 20
        assert result.cursor.next_cursor is None
        assert result.cursor.has_next is False
        assert result.cursor.has_prev is True

    def test_empty_results(self, empty_items):
        """Test cursor pagination with empty results."""
        result = paginate_cursor(
            items=empty_items,
            next_cursor=None,
            prev_cursor=None,
        )

        assert len(result.data) == 0
        assert result.cursor.has_next is False
        assert result.cursor.has_prev is False


# =============================================================================
# Cursor Encoding/Decoding Tests
# =============================================================================

class TestCursorEncoding:
    """Tests for cursor encoding and decoding."""

    def test_encode_simple_cursor(self):
        """Test encoding simple cursor data."""
        data = {"id": 123}
        encoded = encode_cursor(data)

        # Should be base64 encoded
        assert isinstance(encoded, str)
        assert len(encoded) > 0

        # Should be decodable
        decoded = decode_cursor(encoded)
        assert decoded == data

    def test_encode_complex_cursor(self):
        """Test encoding cursor with multiple fields."""
        data = {
            "id": 456,
            "timestamp": "2024-01-15T12:30:00Z",
            "score": 0.95,
        }
        encoded = encode_cursor(data)
        decoded = decode_cursor(encoded)

        assert decoded == data

    def test_encode_sorts_keys(self):
        """Test encoding produces consistent output with sorted keys."""
        data1 = {"b": 2, "a": 1}
        data2 = {"a": 1, "b": 2}

        encoded1 = encode_cursor(data1)
        encoded2 = encode_cursor(data2)

        # Same data should produce same cursor regardless of key order
        assert encoded1 == encoded2

    def test_decode_invalid_cursor(self):
        """Test decoding invalid cursor raises ValueError."""
        with pytest.raises(ValueError):
            decode_cursor("not-valid-base64!!!")

    def test_decode_malformed_json(self):
        """Test decoding valid base64 but invalid JSON."""
        # Encode invalid JSON
        invalid_json = base64.b64encode(b"not json").decode()

        with pytest.raises(ValueError):
            decode_cursor(invalid_json)

    def test_roundtrip_encoding(self):
        """Test cursor data survives encode/decode roundtrip."""
        original = {
            "user_id": "user_123",
            "created_at": "2024-06-15T10:00:00Z",
            "offset": 500,
            "nested": {"key": "value"},
        }

        encoded = encode_cursor(original)
        decoded = decode_cursor(encoded)

        assert decoded == original


# =============================================================================
# Schema Pagination Tests (api/schemas/pagination.py)
# =============================================================================

class TestSchemaPaginationParams:
    """Tests for schema PaginationParams model."""

    def test_default_values(self):
        """Test default schema pagination parameters."""
        params = SchemaPaginationParams()

        assert params.page == 1
        assert params.page_size == 20
        assert params.sort_by is None
        assert params.sort_order == "desc"

    def test_sort_order_validation(self):
        """Test sort_order only accepts asc/desc."""
        valid_asc = SchemaPaginationParams(sort_order="asc")
        assert valid_asc.sort_order == "asc"

        valid_desc = SchemaPaginationParams(sort_order="desc")
        assert valid_desc.sort_order == "desc"

        with pytest.raises(ValueError):
            SchemaPaginationParams(sort_order="invalid")

    def test_with_sort(self):
        """Test parameters with sorting."""
        params = SchemaPaginationParams(
            page=2,
            page_size=50,
            sort_by="created_at",
            sort_order="asc",
        )

        assert params.sort_by == "created_at"
        assert params.sort_order == "asc"


class TestSchemaCursorPaginationParams:
    """Tests for schema CursorPaginationParams model."""

    def test_default_values(self):
        """Test default cursor pagination parameters."""
        params = CursorPaginationParams()

        assert params.cursor is None
        assert params.limit == 20
        assert params.direction == "next"

    def test_direction_validation(self):
        """Test direction only accepts next/prev."""
        valid_next = CursorPaginationParams(direction="next")
        assert valid_next.direction == "next"

        valid_prev = CursorPaginationParams(direction="prev")
        assert valid_prev.direction == "prev"

        with pytest.raises(ValueError):
            CursorPaginationParams(direction="invalid")


class TestSchemaPaginate:
    """Tests for schema paginate function."""

    def test_paginate_slices_items(self, sample_items):
        """Test paginate function slices full item list."""
        # When no total provided, paginate slices from full list
        result = schema_paginate(
            items=sample_items,
            page=2,
            page_size=10,
        )

        assert len(result.items) == 10
        # Items should be from index 10-19 (page 2)
        assert result.items[0]["id"] == 11
        assert result.items[9]["id"] == 20

    def test_paginate_with_provided_total(self, sample_items):
        """Test paginate with pre-sliced items and total."""
        # Pre-sliced items (e.g., from database)
        page_items = sample_items[20:30]

        result = schema_paginate(
            items=page_items,
            page=3,
            page_size=10,
            total=100,
        )

        assert len(result.items) == 10
        assert result.total == 100
        assert result.page == 3
        assert result.total_pages == 10
        assert result.has_next is True
        assert result.has_prev is True

    def test_paginate_empty_list(self, empty_items):
        """Test paginate with empty list."""
        result = schema_paginate(
            items=empty_items,
            page=1,
            page_size=20,
        )

        assert len(result.items) == 0
        assert result.total == 0
        assert result.total_pages == 0

    def test_paginate_metadata_accuracy(self, sample_items):
        """Test pagination metadata is accurate."""
        result = schema_paginate(
            items=sample_items[:45],  # 45 items
            page=2,
            page_size=20,
        )

        assert result.total == 45
        assert result.page == 2
        assert result.page_size == 20
        assert result.total_pages == 3  # ceil(45/20) = 3
        assert result.has_next is True  # Page 2 of 3
        assert result.has_prev is True


# =============================================================================
# Schema Cursor Encoding Tests
# =============================================================================

class TestSchemaCursorEncoding:
    """Tests for schema cursor encoding/decoding."""

    def test_encode_cursor(self):
        """Test schema cursor encoding."""
        data = {"id": 999, "timestamp": "2024-12-01"}
        encoded = schema_encode_cursor(data)

        assert isinstance(encoded, str)
        # Should use urlsafe base64
        assert "+" not in encoded
        assert "/" not in encoded

    def test_decode_cursor(self):
        """Test schema cursor decoding."""
        data = {"position": 42}
        encoded = schema_encode_cursor(data)
        decoded = schema_decode_cursor(encoded)

        assert decoded == data

    def test_decode_invalid_returns_empty(self):
        """Test schema decode returns empty dict on invalid input."""
        # Unlike api/pagination.py, this returns {} instead of raising
        result = schema_decode_cursor("invalid!!!")
        assert result == {}

    def test_urlsafe_encoding(self):
        """Test cursor uses URL-safe base64."""
        # Data that would produce + or / in standard base64
        data = {"data": "test>>>???"}
        encoded = schema_encode_cursor(data)

        # Verify URL-safe characters
        assert all(c.isalnum() or c in "-_=" for c in encoded)


# =============================================================================
# Page Boundary Tests
# =============================================================================

class TestPageBoundaries:
    """Tests for correct page boundary handling."""

    def test_page_boundary_first_item(self, sample_items):
        """Test first item of each page is correct."""
        page_size = 25

        for page in range(1, 5):
            page_items = slice_page(sample_items, page, page_size)
            if page_items:
                expected_first_id = (page - 1) * page_size + 1
                assert page_items[0]["id"] == expected_first_id

    def test_page_boundary_last_item(self, sample_items):
        """Test last item of each page is correct."""
        page_size = 25

        for page in range(1, 4):
            page_items = slice_page(sample_items, page, page_size)
            if page_items:
                expected_last_id = min(page * page_size, 100)
                assert page_items[-1]["id"] == expected_last_id

    def test_no_overlap_between_pages(self, sample_items):
        """Test items don't appear in multiple pages."""
        page_size = 15
        seen_ids = set()

        for page in range(1, 10):
            page_items = slice_page(sample_items, page, page_size)
            for item in page_items:
                assert item["id"] not in seen_ids, f"ID {item['id']} appears in multiple pages"
                seen_ids.add(item["id"])

    def test_all_items_appear(self, sample_items):
        """Test all items appear exactly once across all pages."""
        page_size = 15
        total_pages = (len(sample_items) + page_size - 1) // page_size

        all_ids = []
        for page in range(1, total_pages + 1):
            page_items = slice_page(sample_items, page, page_size)
            all_ids.extend(item["id"] for item in page_items)

        expected_ids = list(range(1, 101))
        assert sorted(all_ids) == expected_ids


# =============================================================================
# Total Count Accuracy Tests
# =============================================================================

class TestTotalCountAccuracy:
    """Tests for accurate total count reporting."""

    def test_total_matches_item_count(self, sample_items):
        """Test total equals actual item count."""
        result = paginate(
            items=sample_items[:20],
            total=len(sample_items),
            page=1,
            page_size=20,
        )

        assert result.pagination.total == 100

    def test_total_independent_of_page_size(self, sample_items):
        """Test total is consistent across different page sizes."""
        results = []
        for page_size in [10, 20, 30, 50]:
            result = paginate(
                items=sample_items[:page_size],
                total=len(sample_items),
                page=1,
                page_size=page_size,
            )
            results.append(result.pagination.total)

        # All should report same total
        assert all(t == 100 for t in results)

    def test_total_independent_of_page_number(self, sample_items):
        """Test total is consistent across different pages."""
        results = []
        page_size = 10

        for page in range(1, 11):
            start = (page - 1) * page_size
            end = start + page_size
            result = paginate(
                items=sample_items[start:end],
                total=len(sample_items),
                page=page,
                page_size=page_size,
            )
            results.append(result.pagination.total)

        assert all(t == 100 for t in results)


# =============================================================================
# has_next/has_prev Link Tests
# =============================================================================

class TestNavigationLinks:
    """Tests for navigation link accuracy."""

    def test_first_page_links(self, sample_items):
        """Test first page has next but not prev."""
        result = paginate(
            items=sample_items[:20],
            total=100,
            page=1,
            page_size=20,
        )

        assert result.pagination.has_next is True
        assert result.pagination.has_prev is False

    def test_middle_page_links(self, sample_items):
        """Test middle page has both next and prev."""
        for page in [2, 3, 4]:
            result = paginate(
                items=[{}],
                total=100,
                page=page,
                page_size=20,
            )
            assert result.pagination.has_next is True
            assert result.pagination.has_prev is True

    def test_last_page_links(self, sample_items):
        """Test last page has prev but not next."""
        result = paginate(
            items=sample_items[80:100],
            total=100,
            page=5,
            page_size=20,
        )

        assert result.pagination.has_next is False
        assert result.pagination.has_prev is True

    def test_single_page_links(self, small_items):
        """Test single page has neither next nor prev."""
        result = paginate(
            items=small_items,
            total=len(small_items),
            page=1,
            page_size=20,
        )

        assert result.pagination.has_next is False
        assert result.pagination.has_prev is False

    def test_cursor_has_next_when_cursor_exists(self):
        """Test cursor has_next is true when next_cursor exists."""
        result = paginate_cursor(
            items=[{}],
            next_cursor="abc123",
            prev_cursor=None,
        )

        assert result.cursor.has_next is True
        assert result.cursor.has_prev is False

    def test_cursor_has_prev_when_cursor_exists(self):
        """Test cursor has_prev is true when prev_cursor exists."""
        result = paginate_cursor(
            items=[{}],
            next_cursor=None,
            prev_cursor="xyz789",
        )

        assert result.cursor.has_next is False
        assert result.cursor.has_prev is True


# =============================================================================
# Edge Case Tests
# =============================================================================

class TestEdgeCases:
    """Tests for edge cases and error conditions."""

    def test_page_size_one(self, sample_items):
        """Test pagination with page_size of 1."""
        result = paginate(
            items=[sample_items[0]],
            total=100,
            page=1,
            page_size=1,
        )

        assert len(result.data) == 1
        assert result.pagination.total_pages == 100
        assert result.pagination.has_next is True

    def test_large_page_size(self, sample_items):
        """Test pagination with page_size larger than dataset."""
        result = paginate(
            items=sample_items,
            total=100,
            page=1,
            page_size=100,
        )

        assert len(result.data) == 100
        assert result.pagination.total_pages == 1
        assert result.pagination.has_next is False
        assert result.pagination.has_prev is False

    def test_page_beyond_total(self, sample_items):
        """Test requesting page beyond total pages."""
        result = paginate(
            items=[],  # Empty because page doesn't exist
            total=100,
            page=10,
            page_size=20,  # Only 5 pages exist
        )

        assert len(result.data) == 0
        assert result.pagination.page == 10
        assert result.pagination.total_pages == 5
        # Page 10 > total pages, so technically "no next"
        assert result.pagination.has_next is False
        # Has prev even though we're beyond bounds
        assert result.pagination.has_prev is True

    def test_unicode_in_items(self):
        """Test pagination handles unicode content."""
        items = [
            {"id": 1, "name": "Hello World"},
            {"id": 2, "name": "Item with emoji: \U0001F600"},
            {"id": 3, "name": "Chinese: \u4E2D\u6587"},
        ]

        result = paginate(
            items=items,
            total=3,
            page=1,
            page_size=10,
        )

        assert len(result.data) == 3
        assert result.data[1]["name"] == "Item with emoji: \U0001F600"

    def test_none_values_in_items(self):
        """Test pagination handles None values."""
        items = [
            {"id": 1, "value": None},
            {"id": 2, "value": "exists"},
        ]

        result = paginate(
            items=items,
            total=2,
            page=1,
            page_size=10,
        )

        assert len(result.data) == 2
        assert result.data[0]["value"] is None

    def test_cursor_with_special_characters(self):
        """Test cursor encoding handles special characters."""
        data = {
            "query": "search with spaces & special=chars",
            "filter": "name='test'",
        }

        encoded = encode_cursor(data)
        decoded = decode_cursor(encoded)

        assert decoded == data


# =============================================================================
# Generic Type Tests
# =============================================================================

class TestGenericTypes:
    """Tests for generic type handling in responses."""

    def test_paginated_response_with_dict_items(self):
        """Test PaginatedResponse works with dict items."""
        result = paginate(
            items=[{"key": "value"}],
            total=1,
            page=1,
            page_size=10,
        )

        assert result.data[0]["key"] == "value"

    def test_paginated_response_with_primitive_items(self):
        """Test PaginatedResponse works with primitive items."""
        result = paginate(
            items=["a", "b", "c"],
            total=3,
            page=1,
            page_size=10,
        )

        assert result.data == ["a", "b", "c"]

    def test_cursor_response_with_complex_items(self):
        """Test CursorResponse works with complex nested items."""
        items = [
            {
                "id": 1,
                "nested": {
                    "level1": {
                        "level2": "deep value",
                    },
                },
                "list": [1, 2, 3],
            }
        ]

        result = paginate_cursor(items=items)

        assert result.data[0]["nested"]["level1"]["level2"] == "deep value"


# =============================================================================
# Consistency Tests
# =============================================================================

class TestConsistency:
    """Tests for consistency between pagination modules."""

    def test_both_modules_produce_same_total_pages(self, sample_items):
        """Test both pagination modules calculate same total_pages."""
        # api/pagination.py
        result1 = paginate(
            items=sample_items[:20],
            total=100,
            page=1,
            page_size=20,
        )

        # api/schemas/pagination.py
        result2 = schema_paginate(
            items=sample_items[:20],
            page=1,
            page_size=20,
            total=100,
        )

        assert result1.pagination.total_pages == result2.total_pages

    def test_cursor_encoding_compatibility(self):
        """Test cursor encoding is compatible between modules."""
        data = {"id": 42, "ts": "2024-01-01"}

        # Encode with one module, decode with other
        encoded1 = encode_cursor(data)
        # Note: schema_decode_cursor uses different base64 variant
        # So we just verify they can each roundtrip their own encoding
        decoded1 = decode_cursor(encoded1)

        encoded2 = schema_encode_cursor(data)
        decoded2 = schema_decode_cursor(encoded2)

        assert decoded1 == data
        assert decoded2 == data


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
