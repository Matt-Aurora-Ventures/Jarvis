"""
Unit tests for API pagination utilities.
"""

import pytest
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


class TestPaginationParams:
    """Test PaginationParams model."""

    def test_default_values(self):
        """Test default pagination params."""
        params = PaginationParams()
        assert params.page == 1
        assert params.page_size == 20
        assert params.offset == 0
        assert params.limit == 20

    def test_custom_values(self):
        """Test custom pagination params."""
        params = PaginationParams(page=3, page_size=50)
        assert params.page == 3
        assert params.page_size == 50
        assert params.offset == 100  # (3 - 1) * 50
        assert params.limit == 50

    def test_page_validation(self):
        """Test page number validation."""
        with pytest.raises(ValueError):
            PaginationParams(page=0)  # Must be >= 1

        with pytest.raises(ValueError):
            PaginationParams(page=-1)

    def test_page_size_validation(self):
        """Test page size validation."""
        with pytest.raises(ValueError):
            PaginationParams(page_size=0)  # Must be >= 1

        with pytest.raises(ValueError):
            PaginationParams(page_size=101)  # Must be <= 100


class TestCursorParams:
    """Test CursorParams model."""

    def test_default_values(self):
        """Test default cursor params."""
        params = CursorParams()
        assert params.cursor is None
        assert params.limit == 20

    def test_with_cursor(self):
        """Test cursor params with cursor."""
        params = CursorParams(cursor="abc123", limit=50)
        assert params.cursor == "abc123"
        assert params.limit == 50


class TestPaginationMeta:
    """Test PaginationMeta model."""

    def test_creation(self):
        """Test pagination metadata creation."""
        meta = PaginationMeta(
            total=100,
            page=2,
            page_size=20,
            total_pages=5,
            has_next=True,
            has_prev=True,
        )

        assert meta.total == 100
        assert meta.page == 2
        assert meta.page_size == 20
        assert meta.total_pages == 5
        assert meta.has_next is True
        assert meta.has_prev is True


class TestCursorMeta:
    """Test CursorMeta model."""

    def test_creation(self):
        """Test cursor metadata creation."""
        meta = CursorMeta(
            next_cursor="next123",
            prev_cursor="prev456",
            has_next=True,
            has_prev=True,
        )

        assert meta.next_cursor == "next123"
        assert meta.prev_cursor == "prev456"
        assert meta.has_next is True
        assert meta.has_prev is True

    def test_no_cursors(self):
        """Test cursor metadata without cursors."""
        meta = CursorMeta(has_next=False, has_prev=False)

        assert meta.next_cursor is None
        assert meta.prev_cursor is None
        assert meta.has_next is False
        assert meta.has_prev is False


class TestPaginateFunction:
    """Test paginate() helper function."""

    def test_first_page(self):
        """Test pagination for first page."""
        items = list(range(1, 21))  # 20 items
        response = paginate(items, total=100, page=1, page_size=20)

        assert len(response.data) == 20
        assert response.data == items
        assert response.pagination.total == 100
        assert response.pagination.page == 1
        assert response.pagination.page_size == 20
        assert response.pagination.total_pages == 5
        assert response.pagination.has_next is True
        assert response.pagination.has_prev is False

    def test_middle_page(self):
        """Test pagination for middle page."""
        items = list(range(21, 41))  # 20 items
        response = paginate(items, total=100, page=2, page_size=20)

        assert len(response.data) == 20
        assert response.pagination.page == 2
        assert response.pagination.has_next is True
        assert response.pagination.has_prev is True

    def test_last_page(self):
        """Test pagination for last page."""
        items = list(range(81, 101))  # 20 items
        response = paginate(items, total=100, page=5, page_size=20)

        assert len(response.data) == 20
        assert response.pagination.page == 5
        assert response.pagination.has_next is False
        assert response.pagination.has_prev is True

    def test_partial_last_page(self):
        """Test pagination for partial last page."""
        items = list(range(91, 98))  # 7 items
        response = paginate(items, total=97, page=5, page_size=20)

        assert len(response.data) == 7
        assert response.pagination.total == 97
        assert response.pagination.total_pages == 5
        assert response.pagination.has_next is False
        assert response.pagination.has_prev is True

    def test_single_page(self):
        """Test pagination with all items on one page."""
        items = list(range(1, 11))  # 10 items
        response = paginate(items, total=10, page=1, page_size=20)

        assert len(response.data) == 10
        assert response.pagination.total_pages == 1
        assert response.pagination.has_next is False
        assert response.pagination.has_prev is False

    def test_empty_results(self):
        """Test pagination with no results."""
        response = paginate([], total=0, page=1, page_size=20)

        assert len(response.data) == 0
        assert response.pagination.total == 0
        assert response.pagination.total_pages == 0
        assert response.pagination.has_next is False
        assert response.pagination.has_prev is False


class TestPaginateCursor:
    """Test paginate_cursor() helper function."""

    def test_with_next_cursor(self):
        """Test cursor pagination with next cursor."""
        items = [1, 2, 3, 4, 5]
        response = paginate_cursor(items, next_cursor="abc123")

        assert len(response.data) == 5
        assert response.cursor.next_cursor == "abc123"
        assert response.cursor.prev_cursor is None
        assert response.cursor.has_next is True
        assert response.cursor.has_prev is False

    def test_with_both_cursors(self):
        """Test cursor pagination with both cursors."""
        items = [6, 7, 8, 9, 10]
        response = paginate_cursor(
            items, next_cursor="next123", prev_cursor="prev456"
        )

        assert response.cursor.next_cursor == "next123"
        assert response.cursor.prev_cursor == "prev456"
        assert response.cursor.has_next is True
        assert response.cursor.has_prev is True

    def test_last_page(self):
        """Test cursor pagination for last page."""
        items = [11, 12, 13]
        response = paginate_cursor(items, prev_cursor="prev789")

        assert response.cursor.next_cursor is None
        assert response.cursor.prev_cursor == "prev789"
        assert response.cursor.has_next is False
        assert response.cursor.has_prev is True


class TestSlicePage:
    """Test slice_page() helper function."""

    def test_first_page(self):
        """Test slicing first page."""
        items = list(range(1, 101))  # 100 items
        page_items = slice_page(items, page=1, page_size=20)

        assert len(page_items) == 20
        assert page_items == list(range(1, 21))

    def test_middle_page(self):
        """Test slicing middle page."""
        items = list(range(1, 101))
        page_items = slice_page(items, page=3, page_size=20)

        assert len(page_items) == 20
        assert page_items == list(range(41, 61))

    def test_last_page(self):
        """Test slicing last page."""
        items = list(range(1, 101))
        page_items = slice_page(items, page=5, page_size=20)

        assert len(page_items) == 20
        assert page_items == list(range(81, 101))

    def test_partial_last_page(self):
        """Test slicing partial last page."""
        items = list(range(1, 98))  # 97 items
        page_items = slice_page(items, page=5, page_size=20)

        assert len(page_items) == 17  # Only 17 items left
        assert page_items == list(range(81, 98))

    def test_beyond_last_page(self):
        """Test slicing beyond last page."""
        items = list(range(1, 51))  # 50 items
        page_items = slice_page(items, page=10, page_size=20)

        assert len(page_items) == 0


class TestCursorEncoding:
    """Test cursor encoding and decoding."""

    def test_encode_decode_simple(self):
        """Test encoding and decoding simple cursor."""
        data = {"id": 123, "timestamp": "2024-01-01T00:00:00Z"}
        cursor = encode_cursor(data)

        assert isinstance(cursor, str)
        assert len(cursor) > 0

        decoded = decode_cursor(cursor)
        assert decoded == data

    def test_encode_decode_complex(self):
        """Test encoding and decoding complex cursor."""
        data = {
            "id": 456,
            "timestamp": "2024-06-15T12:30:00Z",
            "score": 98.5,
            "type": "transaction",
        }
        cursor = encode_cursor(data)
        decoded = decode_cursor(cursor)

        assert decoded == data
        assert decoded["id"] == 456
        assert decoded["score"] == 98.5

    def test_decode_invalid_cursor(self):
        """Test decoding invalid cursor."""
        with pytest.raises(ValueError, match="Invalid cursor"):
            decode_cursor("invalid-cursor-string")

        with pytest.raises(ValueError, match="Invalid cursor"):
            decode_cursor("")

    def test_cursor_is_stable(self):
        """Test that encoding same data produces same cursor."""
        data = {"id": 789, "name": "test"}
        cursor1 = encode_cursor(data)
        cursor2 = encode_cursor(data)

        assert cursor1 == cursor2

    def test_cursor_sorts_keys(self):
        """Test that cursor encoding sorts keys (stable output)."""
        data1 = {"b": 2, "a": 1}
        data2 = {"a": 1, "b": 2}

        cursor1 = encode_cursor(data1)
        cursor2 = encode_cursor(data2)

        assert cursor1 == cursor2


class TestPaginatedResponseModel:
    """Test PaginatedResponse model."""

    def test_response_structure(self):
        """Test paginated response structure."""
        items = [{"id": 1}, {"id": 2}, {"id": 3}]
        response = paginate(items, total=3, page=1, page_size=20)

        assert isinstance(response, PaginatedResponse)
        assert len(response.data) == 3
        assert isinstance(response.pagination, PaginationMeta)

    def test_json_serialization(self):
        """Test that response can be serialized to JSON."""
        items = [{"id": 1}, {"id": 2}]
        response = paginate(items, total=2, page=1, page_size=20)

        # This should not raise an exception
        json_dict = response.model_dump()

        assert "data" in json_dict
        assert "pagination" in json_dict
        assert json_dict["pagination"]["total"] == 2


class TestCursorResponseModel:
    """Test CursorResponse model."""

    def test_response_structure(self):
        """Test cursor response structure."""
        items = [{"id": 1}, {"id": 2}, {"id": 3}]
        response = paginate_cursor(items, next_cursor="abc123")

        assert isinstance(response, CursorResponse)
        assert len(response.data) == 3
        assert isinstance(response.cursor, CursorMeta)

    def test_json_serialization(self):
        """Test that response can be serialized to JSON."""
        items = [{"id": 1}, {"id": 2}]
        response = paginate_cursor(items, next_cursor="xyz")

        json_dict = response.model_dump()

        assert "data" in json_dict
        assert "cursor" in json_dict
        assert json_dict["cursor"]["next_cursor"] == "xyz"


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_very_large_page_number(self):
        """Test pagination with very large page number."""
        items = []
        response = paginate(items, total=100, page=1000, page_size=20)

        assert len(response.data) == 0
        assert response.pagination.page == 1000
        assert response.pagination.has_next is False
        assert response.pagination.has_prev is True

    def test_page_size_equals_total(self):
        """Test when page size equals total items."""
        items = list(range(1, 51))
        response = paginate(items, total=50, page=1, page_size=50)

        assert len(response.data) == 50
        assert response.pagination.total_pages == 1
        assert response.pagination.has_next is False

    def test_single_item(self):
        """Test pagination with single item."""
        items = [{"id": 1}]
        response = paginate(items, total=1, page=1, page_size=20)

        assert len(response.data) == 1
        assert response.pagination.total_pages == 1
        assert response.pagination.has_next is False
        assert response.pagination.has_prev is False

    def test_unicode_in_cursor(self):
        """Test cursor encoding with unicode characters."""
        data = {"name": "Test™️", "emoji": "🎉"}
        cursor = encode_cursor(data)
        decoded = decode_cursor(cursor)

        assert decoded == data
        assert decoded["name"] == "Test™️"
        assert decoded["emoji"] == "🎉"
