"""Pagination schemas and utilities."""
from pydantic import BaseModel, Field
from typing import Generic, TypeVar, List, Optional, Any
from math import ceil

T = TypeVar('T')


class PaginationParams(BaseModel):
    """Pagination query parameters."""
    page: int = Field(default=1, ge=1, description="Page number (1-indexed)")
    page_size: int = Field(default=20, ge=1, le=100, description="Items per page")
    sort_by: Optional[str] = Field(default=None, description="Field to sort by")
    sort_order: str = Field(default="desc", pattern="^(asc|desc)$", description="Sort order")


class PaginatedResponse(BaseModel, Generic[T]):
    """Generic paginated response wrapper."""
    items: List[T]
    total: int
    page: int
    page_size: int
    total_pages: int
    has_next: bool
    has_prev: bool
    
    class Config:
        from_attributes = True


class CursorPaginationParams(BaseModel):
    """Cursor-based pagination parameters."""
    cursor: Optional[str] = Field(default=None, description="Pagination cursor")
    limit: int = Field(default=20, ge=1, le=100, description="Number of items")
    direction: str = Field(default="next", pattern="^(next|prev)$")


class CursorPaginatedResponse(BaseModel, Generic[T]):
    """Cursor-based paginated response."""
    items: List[T]
    next_cursor: Optional[str] = None
    prev_cursor: Optional[str] = None
    has_more: bool = False


def paginate(
    items: List[Any],
    page: int = 1,
    page_size: int = 20,
    total: int = None
) -> PaginatedResponse:
    """
    Paginate a list of items.
    
    If items is the full list, it will be sliced.
    If items is already paginated, provide total count.
    """
    if total is None:
        total = len(items)
        start = (page - 1) * page_size
        end = start + page_size
        items = items[start:end]
    
    total_pages = ceil(total / page_size) if page_size > 0 else 0
    
    return PaginatedResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
        has_next=page < total_pages,
        has_prev=page > 1
    )


def paginate_query(query, params: PaginationParams):
    """
    Apply pagination to a database query.
    Returns (paginated_query, total_count).
    """
    total = query.count()
    
    if params.sort_by:
        if params.sort_order == "desc":
            query = query.order_by(getattr(query.model, params.sort_by).desc())
        else:
            query = query.order_by(getattr(query.model, params.sort_by).asc())
    
    offset = (params.page - 1) * params.page_size
    query = query.offset(offset).limit(params.page_size)
    
    return query, total


def encode_cursor(data: dict) -> str:
    """Encode cursor data to string."""
    import base64
    import json
    return base64.urlsafe_b64encode(json.dumps(data).encode()).decode()


def decode_cursor(cursor: str) -> dict:
    """Decode cursor string to data."""
    import base64
    import json
    try:
        return json.loads(base64.urlsafe_b64decode(cursor.encode()).decode())
    except Exception:
        return {}
