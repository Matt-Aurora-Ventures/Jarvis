"""Standard API response schemas."""
from pydantic import BaseModel
from typing import Any, Dict, Optional, List, Union
from datetime import datetime


class ErrorDetail(BaseModel):
    """Error detail schema."""
    code: str
    message: str
    field: Optional[str] = None
    details: Optional[Dict[str, Any]] = None


class APIResponse(BaseModel):
    """Standard API response wrapper."""
    success: bool
    data: Optional[Any] = None
    error: Optional[ErrorDetail] = None
    meta: Optional[Dict[str, Any]] = None
    timestamp: datetime = None
    
    def __init__(self, **data):
        if 'timestamp' not in data:
            data['timestamp'] = datetime.utcnow()
        super().__init__(**data)


class ValidationErrorResponse(BaseModel):
    """Validation error response."""
    success: bool = False
    errors: List[ErrorDetail]
    timestamp: datetime = None
    
    def __init__(self, **data):
        if 'timestamp' not in data:
            data['timestamp'] = datetime.utcnow()
        super().__init__(**data)


def success_response(
    data: Any = None,
    meta: Dict[str, Any] = None,
    message: str = None
) -> Dict:
    """Create a success response."""
    response = APIResponse(
        success=True,
        data=data,
        meta=meta
    )
    if message:
        response.meta = response.meta or {}
        response.meta["message"] = message
    return response.model_dump()


def error_response(
    code: str,
    message: str,
    field: str = None,
    details: Dict[str, Any] = None,
    status_code: int = None
) -> Dict:
    """Create an error response."""
    response = APIResponse(
        success=False,
        error=ErrorDetail(
            code=code,
            message=message,
            field=field,
            details=details
        )
    )
    result = response.model_dump()
    if status_code:
        result["_status_code"] = status_code
    return result


def validation_error_response(errors: List[Dict]) -> Dict:
    """Create a validation error response."""
    error_details = [
        ErrorDetail(
            code="VAL_001",
            message=err.get("msg", "Validation error"),
            field=".".join(str(loc) for loc in err.get("loc", [])),
            details={"type": err.get("type")}
        )
        for err in errors
    ]
    return ValidationErrorResponse(errors=error_details).model_dump()


def paginated_response(
    items: List[Any],
    total: int,
    page: int,
    page_size: int,
    meta: Dict[str, Any] = None
) -> Dict:
    """Create a paginated response."""
    from math import ceil
    total_pages = ceil(total / page_size) if page_size > 0 else 0
    
    return success_response(
        data=items,
        meta={
            "pagination": {
                "total": total,
                "page": page,
                "page_size": page_size,
                "total_pages": total_pages,
                "has_next": page < total_pages,
                "has_prev": page > 1
            },
            **(meta or {})
        }
    )


ERROR_CODES = {
    "VAL_001": ("Validation error", 400),
    "VAL_002": ("Invalid input format", 400),
    "AUTH_001": ("Authentication required", 401),
    "AUTH_002": ("Invalid credentials", 401),
    "AUTH_003": ("Token expired", 401),
    "AUTH_004": ("Insufficient permissions", 403),
    "RATE_001": ("Rate limit exceeded", 429),
    "SYS_001": ("Internal server error", 500),
    "SYS_002": ("Service unavailable", 503),
    "SYS_003": ("Resource not found", 404),
    "TRADE_001": ("Insufficient balance", 400),
    "TRADE_002": ("Invalid order", 400),
    "TRADE_003": ("Order not found", 404),
    "PROV_001": ("Provider error", 502),
    "PROV_002": ("Provider rate limited", 429),
}


def make_error_response(code: str, message: str = None) -> Dict:
    """Create error response from error code."""
    default_msg, status = ERROR_CODES.get(code, ("Unknown error", 500))
    return error_response(
        code=code,
        message=message or default_msg,
        status_code=status
    )
