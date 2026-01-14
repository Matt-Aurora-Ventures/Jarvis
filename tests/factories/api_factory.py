"""
API Factory

Factory classes for generating API request and response test data.
"""

from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List
from datetime import datetime
from enum import Enum

from .base import BaseFactory, RandomData, SequenceGenerator


class HTTPMethod(Enum):
    """HTTP methods."""
    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    PATCH = "PATCH"
    DELETE = "DELETE"


@dataclass
class RequestHeaders:
    """Request headers for testing."""
    content_type: str
    authorization: Optional[str]
    x_request_id: str
    user_agent: str
    accept: str
    custom_headers: Dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, str]:
        """Convert to dictionary."""
        headers = {
            "Content-Type": self.content_type,
            "X-Request-ID": self.x_request_id,
            "User-Agent": self.user_agent,
            "Accept": self.accept,
            **self.custom_headers,
        }
        if self.authorization:
            headers["Authorization"] = self.authorization
        return headers


class RequestHeadersFactory(BaseFactory[RequestHeaders]):
    """Factory for request headers."""

    @classmethod
    def _build(
        cls,
        content_type: str = "application/json",
        authorization: Optional[str] = None,
        x_request_id: Optional[str] = None,
        user_agent: str = "JARVIS-Test/1.0",
        accept: str = "application/json",
        custom_headers: Optional[Dict[str, str]] = None,
        with_auth: bool = False,
        **kwargs
    ) -> RequestHeaders:
        """Build RequestHeaders instance."""
        auth = authorization
        if with_auth and not auth:
            auth = f"Bearer test_token_{RandomData.string(20)}"

        return RequestHeaders(
            content_type=content_type,
            authorization=auth,
            x_request_id=x_request_id or RandomData.uuid(),
            user_agent=user_agent,
            accept=accept,
            custom_headers=custom_headers or {},
        )


@dataclass
class Request:
    """HTTP request model for testing."""
    method: HTTPMethod
    path: str
    headers: RequestHeaders
    body: Optional[Dict[str, Any]]
    query_params: Dict[str, str]
    path_params: Dict[str, str]


class RequestFactory(BaseFactory[Request]):
    """Factory for HTTP requests."""

    @classmethod
    def _build(
        cls,
        method: HTTPMethod = HTTPMethod.GET,
        path: str = "/api/v1/health",
        headers: Optional[RequestHeaders] = None,
        body: Optional[Dict[str, Any]] = None,
        query_params: Optional[Dict[str, str]] = None,
        path_params: Optional[Dict[str, str]] = None,
        with_auth: bool = False,
        **kwargs
    ) -> Request:
        """Build a Request instance."""
        return Request(
            method=method,
            path=path,
            headers=headers or RequestHeadersFactory.build(with_auth=with_auth),
            body=body,
            query_params=query_params or {},
            path_params=path_params or {},
        )


class GetRequestFactory(RequestFactory):
    """Factory for GET requests."""

    @classmethod
    def _build(cls, **kwargs) -> Request:
        kwargs.setdefault('method', HTTPMethod.GET)
        return super()._build(**kwargs)


class PostRequestFactory(RequestFactory):
    """Factory for POST requests."""

    @classmethod
    def _build(cls, **kwargs) -> Request:
        kwargs.setdefault('method', HTTPMethod.POST)
        kwargs.setdefault('body', {})
        return super()._build(**kwargs)


class AuthenticatedRequestFactory(RequestFactory):
    """Factory for authenticated requests."""

    @classmethod
    def _build(cls, **kwargs) -> Request:
        kwargs.setdefault('with_auth', True)
        return super()._build(**kwargs)


@dataclass
class ResponseHeaders:
    """Response headers for testing."""
    content_type: str
    x_request_id: str
    x_rate_limit_limit: int
    x_rate_limit_remaining: int
    x_rate_limit_reset: int
    custom_headers: Dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, str]:
        """Convert to dictionary."""
        return {
            "Content-Type": self.content_type,
            "X-Request-ID": self.x_request_id,
            "X-RateLimit-Limit": str(self.x_rate_limit_limit),
            "X-RateLimit-Remaining": str(self.x_rate_limit_remaining),
            "X-RateLimit-Reset": str(self.x_rate_limit_reset),
            **self.custom_headers,
        }


class ResponseHeadersFactory(BaseFactory[ResponseHeaders]):
    """Factory for response headers."""

    @classmethod
    def _build(
        cls,
        content_type: str = "application/json",
        x_request_id: Optional[str] = None,
        x_rate_limit_limit: int = 100,
        x_rate_limit_remaining: int = 99,
        x_rate_limit_reset: Optional[int] = None,
        custom_headers: Optional[Dict[str, str]] = None,
        **kwargs
    ) -> ResponseHeaders:
        """Build ResponseHeaders instance."""
        import time

        return ResponseHeaders(
            content_type=content_type,
            x_request_id=x_request_id or RandomData.uuid(),
            x_rate_limit_limit=x_rate_limit_limit,
            x_rate_limit_remaining=x_rate_limit_remaining,
            x_rate_limit_reset=x_rate_limit_reset or int(time.time()) + 60,
            custom_headers=custom_headers or {},
        )


@dataclass
class Response:
    """HTTP response model for testing."""
    status_code: int
    headers: ResponseHeaders
    body: Dict[str, Any]
    elapsed_ms: float


class ResponseFactory(BaseFactory[Response]):
    """Factory for HTTP responses."""

    @classmethod
    def _build(
        cls,
        status_code: int = 200,
        headers: Optional[ResponseHeaders] = None,
        body: Optional[Dict[str, Any]] = None,
        elapsed_ms: Optional[float] = None,
        **kwargs
    ) -> Response:
        """Build a Response instance."""
        return Response(
            status_code=status_code,
            headers=headers or ResponseHeadersFactory.build(),
            body=body or {"status": "ok"},
            elapsed_ms=elapsed_ms or RandomData.decimal(10.0, 200.0),
        )


class SuccessResponseFactory(ResponseFactory):
    """Factory for success responses."""

    @classmethod
    def _build(cls, **kwargs) -> Response:
        kwargs.setdefault('status_code', 200)
        return super()._build(**kwargs)


class ErrorResponseFactory(ResponseFactory):
    """Factory for error responses."""

    @classmethod
    def _build(
        cls,
        status_code: int = 400,
        error_code: str = "BAD_REQUEST",
        message: str = "Invalid request",
        **kwargs
    ) -> Response:
        kwargs.setdefault('status_code', status_code)
        kwargs.setdefault('body', {
            "error": {
                "code": error_code,
                "message": message,
            }
        })
        return super()._build(**kwargs)


class NotFoundResponseFactory(ErrorResponseFactory):
    """Factory for 404 responses."""

    @classmethod
    def _build(cls, **kwargs) -> Response:
        kwargs.setdefault('status_code', 404)
        kwargs.setdefault('error_code', "NOT_FOUND")
        kwargs.setdefault('message', "Resource not found")
        return super()._build(**kwargs)


class UnauthorizedResponseFactory(ErrorResponseFactory):
    """Factory for 401 responses."""

    @classmethod
    def _build(cls, **kwargs) -> Response:
        kwargs.setdefault('status_code', 401)
        kwargs.setdefault('error_code', "UNAUTHORIZED")
        kwargs.setdefault('message', "Authentication required")
        return super()._build(**kwargs)


class RateLimitResponseFactory(ErrorResponseFactory):
    """Factory for 429 responses."""

    @classmethod
    def _build(cls, **kwargs) -> Response:
        kwargs.setdefault('status_code', 429)
        kwargs.setdefault('error_code', "RATE_LIMITED")
        kwargs.setdefault('message', "Too many requests")
        return super()._build(**kwargs)


@dataclass
class APIError:
    """API error model for testing."""
    code: str
    message: str
    details: Optional[Dict[str, Any]]
    request_id: str
    timestamp: datetime


class APIErrorFactory(BaseFactory[APIError]):
    """Factory for API errors."""

    @classmethod
    def _build(
        cls,
        code: str = "INTERNAL_ERROR",
        message: str = "An internal error occurred",
        details: Optional[Dict[str, Any]] = None,
        request_id: Optional[str] = None,
        timestamp: Optional[datetime] = None,
        **kwargs
    ) -> APIError:
        """Build an APIError instance."""
        return APIError(
            code=code,
            message=message,
            details=details,
            request_id=request_id or RandomData.uuid(),
            timestamp=timestamp or datetime.utcnow(),
        )
