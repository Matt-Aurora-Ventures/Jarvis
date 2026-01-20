"""
Standardized Pagination for Jarvis API.

Provides consistent pagination utilities for all list endpoints:
- Offset/limit pagination (traditional page-based)
- Cursor-based pagination (for large datasets)
- Response envelope with metadata
"""

from typing import Any, Dict, Generic, List, Optional, TypeVar
from pydantic import BaseModel, Field


T = TypeVar("T")


# =============================================================================
# Pagination Parameters
# =============================================================================


class PaginationParams(BaseModel):
    """Standard offset/limit pagination parameters."""

    page: int = Field(1, ge=1, description="Page number (1-indexed)")
    page_size: int = Field(20, ge=1, le=100, description="Items per page")

    @property
    def offset(self) -> int:
        """Calculate offset from page and page_size."""
        return (self.page - 1) * self.page_size

    @property
    def limit(self) -> int:
        """Alias for page_size."""
        return self.page_size


class CursorParams(BaseModel):
    """Cursor-based pagination parameters."""

    cursor: Optional[str] = Field(None, description="Cursor for next page")
    limit: int = Field(20, ge=1, le=100, description="Items per page")


# =============================================================================
# Pagination Metadata
# =============================================================================


class PaginationMeta(BaseModel):
    """Pagination metadata for responses."""

    total: int = Field(..., description="Total number of items")
    page: int = Field(..., description="Current page number")
    page_size: int = Field(..., description="Items per page")
    total_pages: int = Field(..., description="Total number of pages")
    has_next: bool = Field(..., description="Whether there are more pages")
    has_prev: bool = Field(..., description="Whether there are previous pages")


class CursorMeta(BaseModel):
    """Cursor-based pagination metadata."""

    next_cursor: Optional[str] = Field(None, description="Cursor for next page")
    prev_cursor: Optional[str] = Field(None, description="Cursor for previous page")
    has_next: bool = Field(..., description="Whether there are more items")
    has_prev: bool = Field(..., description="Whether there are previous items")


# =============================================================================
# Response Envelopes
# =============================================================================


class PaginatedResponse(BaseModel, Generic[T]):
    """
    Standardized paginated response envelope.

    Example:
        {
            "data": [...],
            "pagination": {
                "total": 100,
                "page": 1,
                "page_size": 20,
                "total_pages": 5,
                "has_next": true,
                "has_prev": false
            }
        }
    """

    data: List[T] = Field(..., description="List of items")
    pagination: PaginationMeta = Field(..., description="Pagination metadata")


class CursorResponse(BaseModel, Generic[T]):
    """
    Cursor-based paginated response.

    Better for large datasets where total count is expensive.

    Example:
        {
            "data": [...],
            "cursor": {
                "next_cursor": "eyJpZCI6MTIzfQ==",
                "has_next": true,
                "has_prev": false
            }
        }
    """

    data: List[T] = Field(..., description="List of items")
    cursor: CursorMeta = Field(..., description="Cursor metadata")


# =============================================================================
# Pagination Helpers
# =============================================================================


def paginate(
    items: List[T],
    total: int,
    page: int,
    page_size: int,
) -> PaginatedResponse[T]:
    """
    Create a paginated response from a list of items.

    Args:
        items: The items for the current page
        total: Total number of items across all pages
        page: Current page number (1-indexed)
        page_size: Number of items per page

    Returns:
        PaginatedResponse with data and pagination metadata
    """
    total_pages = (total + page_size - 1) // page_size  # Ceiling division

    return PaginatedResponse(
        data=items,
        pagination=PaginationMeta(
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
            has_next=page < total_pages,
            has_prev=page > 1,
        ),
    )


def paginate_cursor(
    items: List[T],
    next_cursor: Optional[str] = None,
    prev_cursor: Optional[str] = None,
) -> CursorResponse[T]:
    """
    Create a cursor-based paginated response.

    Args:
        items: The items for the current page
        next_cursor: Cursor for the next page (if exists)
        prev_cursor: Cursor for the previous page (if exists)

    Returns:
        CursorResponse with data and cursor metadata
    """
    return CursorResponse(
        data=items,
        cursor=CursorMeta(
            next_cursor=next_cursor,
            prev_cursor=prev_cursor,
            has_next=next_cursor is not None,
            has_prev=prev_cursor is not None,
        ),
    )


def slice_page(items: List[T], page: int, page_size: int) -> List[T]:
    """
    Slice a list to get items for a specific page.

    Args:
        items: Full list of items
        page: Page number (1-indexed)
        page_size: Items per page

    Returns:
        Slice of items for the requested page
    """
    start = (page - 1) * page_size
    end = start + page_size
    return items[start:end]


# =============================================================================
# Cursor Encoding/Decoding
# =============================================================================


import base64
import json


def encode_cursor(data: Dict[str, Any]) -> str:
    """
    Encode cursor data to a base64 string.

    Args:
        data: Dictionary with cursor data (e.g., {"id": 123, "timestamp": "..."})

    Returns:
        Base64 encoded cursor string
    """
    json_str = json.dumps(data, sort_keys=True)
    return base64.b64encode(json_str.encode()).decode()


def decode_cursor(cursor: str) -> Dict[str, Any]:
    """
    Decode a base64 cursor string.

    Args:
        cursor: Base64 encoded cursor string

    Returns:
        Dictionary with cursor data

    Raises:
        ValueError: If cursor is invalid
    """
    try:
        json_str = base64.b64decode(cursor.encode()).decode()
        return json.loads(json_str)
    except Exception as e:
        raise ValueError(f"Invalid cursor: {e}")
