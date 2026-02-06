"""
Base API Client - Abstract base class for external API clients.

Provides:
- Common request/response handling
- Retry logic with exponential backoff
- Error handling with custom exceptions
- Session management
- Cost tracking hooks

Usage:
    from core.api.base import BaseAPIClient, RetryPolicy

    class MyClient(BaseAPIClient):
        @property
        def provider(self) -> str:
            return "my_provider"

        @property
        def base_url(self) -> str:
            return "https://api.example.com"
"""

import asyncio
import logging
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Dict, List, Optional, Tuple, Union

import aiohttp

from core.api.errors import (
    APIError,
    RateLimitError,
    ServiceUnavailableError,
    InternalError,
)

logger = logging.getLogger(__name__)


@dataclass
class RetryPolicy:
    """
    Configuration for retry behavior.

    Attributes:
        max_attempts: Maximum number of retry attempts
        base_delay: Initial delay between retries (seconds)
        max_delay: Maximum delay between retries (seconds)
        exponential_base: Base for exponential backoff calculation
        retryable_status_codes: HTTP status codes that trigger retries
    """
    max_attempts: int = 3
    base_delay: float = 1.0
    max_delay: float = 30.0
    exponential_base: float = 2.0
    retryable_status_codes: List[int] = field(
        default_factory=lambda: [429, 500, 502, 503, 504]
    )

    def get_delay(self, attempt: int) -> float:
        """Calculate delay for given attempt number."""
        delay = self.base_delay * (self.exponential_base ** attempt)
        return min(delay, self.max_delay)


@dataclass
class APIResponse:
    """
    Standardized API response wrapper.

    Attributes:
        status_code: HTTP status code
        data: Response data (parsed JSON)
        headers: Response headers
        raw: Raw response text (optional)
    """
    status_code: int
    data: Any
    headers: Dict[str, str] = field(default_factory=dict)
    raw: Optional[str] = None

    @property
    def success(self) -> bool:
        """Check if response indicates success."""
        return 200 <= self.status_code < 300


class BaseAPIClient(ABC):
    """
    Abstract base class for external API clients.

    Provides common functionality for:
    - HTTP request handling (sync and async)
    - Retry logic with exponential backoff
    - Error handling and response parsing
    - Session management
    """

    def __init__(
        self,
        timeout: int = 30,
        retry_policy: Optional[RetryPolicy] = None,
        headers: Optional[Dict[str, str]] = None,
    ):
        """
        Initialize the API client.

        Args:
            timeout: Request timeout in seconds
            retry_policy: Custom retry policy (default: 3 attempts with exponential backoff)
            headers: Additional headers to include in all requests
        """
        self._timeout = timeout
        self._retry_policy = retry_policy or RetryPolicy()
        self._custom_headers = headers or {}
        self._session: Optional[aiohttp.ClientSession] = None

    @property
    @abstractmethod
    def provider(self) -> str:
        """Return the provider name (e.g., 'grok', 'telegram')."""
        pass

    @property
    @abstractmethod
    def base_url(self) -> str:
        """Return the base URL for API requests."""
        pass

    @property
    def timeout(self) -> int:
        """Get the request timeout."""
        return self._timeout

    @property
    def retry_policy(self) -> RetryPolicy:
        """Get the retry policy."""
        return self._retry_policy

    @property
    def headers(self) -> Dict[str, str]:
        """Get the default headers for requests."""
        base_headers = {
            "Content-Type": "application/json",
        }
        base_headers.update(self._custom_headers)
        return base_headers

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create the aiohttp session."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                headers=self.headers,
                timeout=aiohttp.ClientTimeout(total=self._timeout)
            )
        return self._session

    async def close(self) -> None:
        """Close the aiohttp session."""
        if self._session and not self._session.closed:
            await self._session.close()

    def _build_url(self, endpoint: str) -> str:
        """Build full URL from base URL and endpoint."""
        base = self.base_url.rstrip('/')
        endpoint = endpoint.lstrip('/')
        return f"{base}/{endpoint}"

    async def _make_request(
        self,
        method: str,
        url: str,
        data: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> Tuple[int, Any]:
        """
        Make a single HTTP request.

        Args:
            method: HTTP method (GET, POST, etc.)
            url: Full URL
            data: Request body data
            params: Query parameters
            headers: Additional headers

        Returns:
            Tuple of (status_code, response_data)
        """
        session = await self._get_session()
        request_headers = self.headers.copy()
        if headers:
            request_headers.update(headers)

        kwargs: Dict[str, Any] = {"headers": request_headers}
        if data:
            kwargs["json"] = data
        if params:
            kwargs["params"] = params

        async with session.request(method, url, **kwargs) as response:
            status = response.status
            try:
                response_data = await response.json()
            except Exception:
                response_data = await response.text()
            return status, response_data

    async def request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> APIResponse:
        """
        Make an HTTP request with retry logic.

        Args:
            method: HTTP method (GET, POST, PUT, DELETE)
            endpoint: API endpoint (appended to base_url)
            data: Request body data
            params: Query parameters
            headers: Additional headers

        Returns:
            APIResponse with status, data, and headers

        Raises:
            APIError: If all retry attempts fail
        """
        url = self._build_url(endpoint)
        last_error: Optional[Exception] = None

        for attempt in range(self._retry_policy.max_attempts):
            try:
                status, response_data = await self._make_request(
                    method, url, data, params, headers
                )

                # Check if we should retry
                if status in self._retry_policy.retryable_status_codes:
                    if attempt < self._retry_policy.max_attempts - 1:
                        delay = self._retry_policy.get_delay(attempt)

                        # Check for Retry-After header
                        if status == 429 and isinstance(response_data, dict):
                            retry_after = response_data.get("parameters", {}).get("retry_after")
                            if retry_after:
                                delay = min(float(retry_after), self._retry_policy.max_delay)

                        logger.warning(
                            f"{self.provider}: Retrying in {delay}s (attempt {attempt + 1}/{self._retry_policy.max_attempts})"
                        )
                        await asyncio.sleep(delay)
                        continue

                return APIResponse(
                    status_code=status,
                    data=response_data,
                )

            except aiohttp.ClientError as e:
                last_error = e
                if attempt < self._retry_policy.max_attempts - 1:
                    delay = self._retry_policy.get_delay(attempt)
                    logger.warning(
                        f"{self.provider}: Connection error, retrying in {delay}s: {e}"
                    )
                    await asyncio.sleep(delay)
                else:
                    raise ServiceUnavailableError(
                        message=f"Connection failed after {self._retry_policy.max_attempts} attempts",
                        service=self.provider,
                    ) from e

        # Should not reach here, but handle gracefully
        raise InternalError(
            message=f"Request failed after {self._retry_policy.max_attempts} attempts",
            details={"last_error": str(last_error)} if last_error else None,
        )

    async def async_request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> APIResponse:
        """
        Alias for request() method for consistency.

        This method exists to match the interface specification and provides
        the same functionality as request().
        """
        return await self.request(method, endpoint, data, params, headers)

    def handle_error(self, response: Any) -> None:
        """
        Handle error response and raise appropriate APIError.

        Args:
            response: Response object or dict with status and error info

        Raises:
            APIError: Appropriate error based on status code
        """
        # Handle dict-like response
        if isinstance(response, dict):
            status_code = response.get("status_code", 500)
            error_msg = response.get("error", "Unknown error")
        else:
            # Handle object with attributes
            status_code = getattr(response, "status_code", 500)
            try:
                error_data = response.json()
                error_msg = error_data.get("error", str(error_data))
            except Exception:
                error_msg = "Unknown error"

        if status_code == 429:
            raise RateLimitError(message=error_msg)
        elif status_code >= 500:
            raise ServiceUnavailableError(message=error_msg, service=self.provider)
        else:
            raise APIError(
                message=error_msg,
                status_code=status_code,
            )

    async def _stream_request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> AsyncIterator[Dict[str, Any]]:
        """
        Make a streaming HTTP request.

        Args:
            method: HTTP method
            endpoint: API endpoint
            data: Request body data
            headers: Additional headers

        Yields:
            Parsed JSON chunks from the stream
        """
        url = self._build_url(endpoint)
        session = await self._get_session()
        request_headers = self.headers.copy()
        if headers:
            request_headers.update(headers)

        kwargs: Dict[str, Any] = {"headers": request_headers}
        if data:
            kwargs["json"] = data

        async with session.request(method, url, **kwargs) as response:
            async for line in response.content:
                line = line.decode("utf-8").strip()
                if line.startswith("data: "):
                    line = line[6:]
                if line and line != "[DONE]":
                    try:
                        import json
                        yield json.loads(line)
                    except json.JSONDecodeError:
                        continue

    async def health_check(self) -> bool:
        """
        Check if the API is reachable.

        Returns:
            True if healthy, False otherwise
        """
        try:
            # Default implementation - subclasses can override
            session = await self._get_session()
            async with session.head(self.base_url) as response:
                return response.status < 500
        except Exception as e:
            logger.warning(f"{self.provider} health check failed: {e}")
            return False

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(provider={self.provider}, base_url={self.base_url})"
