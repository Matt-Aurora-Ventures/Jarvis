"""
Tests for BaseAPIClient abstract class.

TDD Phase 1: Write failing tests first.
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Dict, Any


class TestBaseAPIClient:
    """Tests for the BaseAPIClient abstract class."""

    def test_import_base_client(self):
        """Should be able to import BaseAPIClient."""
        from core.api.base import BaseAPIClient
        assert BaseAPIClient is not None

    def test_base_client_is_abstract(self):
        """BaseAPIClient should be abstract and not instantiable."""
        from core.api.base import BaseAPIClient

        with pytest.raises(TypeError):
            BaseAPIClient()

    def test_base_client_requires_provider_property(self):
        """Subclass must implement provider property."""
        from core.api.base import BaseAPIClient

        class IncompleteClient(BaseAPIClient):
            pass

        with pytest.raises(TypeError):
            IncompleteClient()

    def test_concrete_client_instantiation(self):
        """Concrete subclass should be instantiable."""
        from core.api.base import BaseAPIClient

        class ConcreteClient(BaseAPIClient):
            @property
            def provider(self) -> str:
                return "test"

            @property
            def base_url(self) -> str:
                return "https://api.test.com"

        client = ConcreteClient()
        assert client.provider == "test"
        assert client.base_url == "https://api.test.com"


class TestBaseAPIClientConfiguration:
    """Tests for BaseAPIClient configuration options."""

    def test_default_timeout(self):
        """Should have default timeout of 30 seconds."""
        from core.api.base import BaseAPIClient

        class TestClient(BaseAPIClient):
            @property
            def provider(self) -> str:
                return "test"

            @property
            def base_url(self) -> str:
                return "https://api.test.com"

        client = TestClient()
        assert client.timeout == 30

    def test_custom_timeout(self):
        """Should allow custom timeout."""
        from core.api.base import BaseAPIClient

        class TestClient(BaseAPIClient):
            @property
            def provider(self) -> str:
                return "test"

            @property
            def base_url(self) -> str:
                return "https://api.test.com"

        client = TestClient(timeout=60)
        assert client.timeout == 60

    def test_default_retry_policy(self):
        """Should have default retry policy with 3 attempts."""
        from core.api.base import BaseAPIClient, RetryPolicy

        class TestClient(BaseAPIClient):
            @property
            def provider(self) -> str:
                return "test"

            @property
            def base_url(self) -> str:
                return "https://api.test.com"

        client = TestClient()
        assert isinstance(client.retry_policy, RetryPolicy)
        assert client.retry_policy.max_attempts == 3

    def test_custom_retry_policy(self):
        """Should allow custom retry policy."""
        from core.api.base import BaseAPIClient, RetryPolicy

        class TestClient(BaseAPIClient):
            @property
            def provider(self) -> str:
                return "test"

            @property
            def base_url(self) -> str:
                return "https://api.test.com"

        policy = RetryPolicy(max_attempts=5, base_delay=2.0)
        client = TestClient(retry_policy=policy)
        assert client.retry_policy.max_attempts == 5
        assert client.retry_policy.base_delay == 2.0

    def test_default_headers(self):
        """Should have content-type header by default."""
        from core.api.base import BaseAPIClient

        class TestClient(BaseAPIClient):
            @property
            def provider(self) -> str:
                return "test"

            @property
            def base_url(self) -> str:
                return "https://api.test.com"

        client = TestClient()
        assert "Content-Type" in client.headers
        assert client.headers["Content-Type"] == "application/json"

    def test_custom_headers(self):
        """Should allow adding custom headers."""
        from core.api.base import BaseAPIClient

        class TestClient(BaseAPIClient):
            @property
            def provider(self) -> str:
                return "test"

            @property
            def base_url(self) -> str:
                return "https://api.test.com"

        client = TestClient(headers={"X-Custom": "value"})
        assert client.headers.get("X-Custom") == "value"


class TestRetryPolicy:
    """Tests for RetryPolicy configuration."""

    def test_retry_policy_defaults(self):
        """RetryPolicy should have sensible defaults."""
        from core.api.base import RetryPolicy

        policy = RetryPolicy()
        assert policy.max_attempts == 3
        assert policy.base_delay == 1.0
        assert policy.max_delay == 30.0
        assert policy.exponential_base == 2.0

    def test_retry_policy_custom_values(self):
        """RetryPolicy should accept custom values."""
        from core.api.base import RetryPolicy

        policy = RetryPolicy(
            max_attempts=5,
            base_delay=0.5,
            max_delay=60.0,
            exponential_base=3.0
        )
        assert policy.max_attempts == 5
        assert policy.base_delay == 0.5
        assert policy.max_delay == 60.0
        assert policy.exponential_base == 3.0

    def test_retry_policy_retryable_status_codes(self):
        """RetryPolicy should define retryable status codes."""
        from core.api.base import RetryPolicy

        policy = RetryPolicy()
        assert 429 in policy.retryable_status_codes  # Rate limit
        assert 500 in policy.retryable_status_codes  # Server error
        assert 502 in policy.retryable_status_codes  # Bad gateway
        assert 503 in policy.retryable_status_codes  # Service unavailable
        assert 504 in policy.retryable_status_codes  # Gateway timeout


class TestBaseAPIClientRequest:
    """Tests for BaseAPIClient request method."""

    @pytest.mark.asyncio
    async def test_request_method_exists(self):
        """Should have a request method."""
        from core.api.base import BaseAPIClient

        class TestClient(BaseAPIClient):
            @property
            def provider(self) -> str:
                return "test"

            @property
            def base_url(self) -> str:
                return "https://api.test.com"

        client = TestClient()
        assert hasattr(client, 'request')
        assert asyncio.iscoroutinefunction(client.request)

    @pytest.mark.asyncio
    async def test_request_builds_url(self):
        """Request should build full URL from base_url and endpoint."""
        from core.api.base import BaseAPIClient

        class TestClient(BaseAPIClient):
            @property
            def provider(self) -> str:
                return "test"

            @property
            def base_url(self) -> str:
                return "https://api.test.com/v1"

        client = TestClient()

        with patch.object(client, '_make_request', new_callable=AsyncMock) as mock_req:
            mock_req.return_value = (200, {"success": True})
            await client.request("GET", "/users")
            mock_req.assert_called_once()
            call_args = mock_req.call_args
            assert "https://api.test.com/v1/users" in str(call_args)


class TestBaseAPIClientAsyncRequest:
    """Tests for async request handling."""

    @pytest.mark.asyncio
    async def test_async_request_method_exists(self):
        """Should have an async_request method."""
        from core.api.base import BaseAPIClient

        class TestClient(BaseAPIClient):
            @property
            def provider(self) -> str:
                return "test"

            @property
            def base_url(self) -> str:
                return "https://api.test.com"

        client = TestClient()
        assert hasattr(client, 'async_request')
        assert asyncio.iscoroutinefunction(client.async_request)


class TestBaseAPIClientErrorHandling:
    """Tests for error handling."""

    def test_handle_error_method_exists(self):
        """Should have a handle_error method."""
        from core.api.base import BaseAPIClient

        class TestClient(BaseAPIClient):
            @property
            def provider(self) -> str:
                return "test"

            @property
            def base_url(self) -> str:
                return "https://api.test.com"

        client = TestClient()
        assert hasattr(client, 'handle_error')

    def test_handle_error_raises_api_error(self):
        """handle_error should raise appropriate APIError."""
        from core.api.base import BaseAPIClient
        from core.api.errors import APIError

        class TestClient(BaseAPIClient):
            @property
            def provider(self) -> str:
                return "test"

            @property
            def base_url(self) -> str:
                return "https://api.test.com"

        client = TestClient()

        # Mock response with error
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.json.return_value = {"error": "Bad request"}

        with pytest.raises(APIError):
            client.handle_error(mock_response)


class TestAPIResponse:
    """Tests for APIResponse dataclass."""

    def test_api_response_dataclass(self):
        """APIResponse should be a dataclass with expected fields."""
        from core.api.base import APIResponse

        response = APIResponse(
            status_code=200,
            data={"id": 1},
            headers={"Content-Type": "application/json"}
        )

        assert response.status_code == 200
        assert response.data == {"id": 1}
        assert response.headers == {"Content-Type": "application/json"}
        assert response.success is True

    def test_api_response_failure(self):
        """APIResponse with error status should have success=False."""
        from core.api.base import APIResponse

        response = APIResponse(
            status_code=400,
            data={"error": "Bad request"},
            headers={}
        )

        assert response.success is False
