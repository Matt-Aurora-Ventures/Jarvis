"""
Tests for GrokClient implementation.

TDD Phase 1: Write failing tests first.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import json


class TestGrokClientBasics:
    """Basic tests for GrokClient."""

    def test_import_grok_client(self):
        """Should be able to import GrokClient."""
        from core.api.clients.grok import GrokClient
        assert GrokClient is not None

    def test_grok_client_inherits_base(self):
        """GrokClient should inherit from BaseAPIClient."""
        from core.api.clients.grok import GrokClient
        from core.api.base import BaseAPIClient

        assert issubclass(GrokClient, BaseAPIClient)

    def test_grok_client_provider(self):
        """GrokClient should have provider 'grok'."""
        from core.api.clients.grok import GrokClient

        client = GrokClient(api_key="test-key")
        assert client.provider == "grok"

    def test_grok_client_base_url(self):
        """GrokClient should use xAI API base URL."""
        from core.api.clients.grok import GrokClient

        client = GrokClient(api_key="test-key")
        assert "api.x.ai" in client.base_url


class TestGrokClientConfiguration:
    """Tests for GrokClient configuration."""

    def test_api_key_from_env(self):
        """Should read API key from environment if not provided."""
        from core.api.clients.grok import GrokClient

        with patch.dict('os.environ', {'XAI_API_KEY': 'env-key'}):
            client = GrokClient()
            # Key should be loaded from env
            assert client._api_key is not None

    def test_api_key_from_argument(self):
        """Should use API key from argument if provided."""
        from core.api.clients.grok import GrokClient

        client = GrokClient(api_key="arg-key")
        assert client._api_key == "arg-key"

    def test_default_model(self):
        """Should have default model set."""
        from core.api.clients.grok import GrokClient

        client = GrokClient(api_key="test-key")
        assert client.model is not None
        assert "grok" in client.model.lower()


class TestGrokClientChat:
    """Tests for chat method."""

    @pytest.mark.asyncio
    async def test_chat_method_exists(self):
        """chat() method should exist."""
        from core.api.clients.grok import GrokClient

        client = GrokClient(api_key="test-key")
        assert hasattr(client, 'chat')

    @pytest.mark.asyncio
    async def test_chat_returns_response(self):
        """chat() should return a response object."""
        from core.api.clients.grok import GrokClient, GrokResponse

        client = GrokClient(api_key="test-key")

        with patch.object(client, '_make_request', new_callable=AsyncMock) as mock_req:
            mock_req.return_value = (200, {
                "choices": [{"message": {"content": "Hello!"}}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 5}
            })

            response = await client.chat([{"role": "user", "content": "Hi"}])

            assert isinstance(response, GrokResponse)
            assert response.success is True
            assert response.content == "Hello!"

    @pytest.mark.asyncio
    async def test_chat_with_system_message(self):
        """chat() should support system messages."""
        from core.api.clients.grok import GrokClient

        client = GrokClient(api_key="test-key")

        with patch.object(client, '_make_request', new_callable=AsyncMock) as mock_req:
            mock_req.return_value = (200, {
                "choices": [{"message": {"content": "I am JARVIS"}}],
                "usage": {"prompt_tokens": 20, "completion_tokens": 10}
            })

            messages = [
                {"role": "system", "content": "You are JARVIS"},
                {"role": "user", "content": "Who are you?"}
            ]

            await client.chat(messages)

            # Verify system message was passed
            call_args = mock_req.call_args
            assert "system" in str(call_args)

    @pytest.mark.asyncio
    async def test_chat_handles_api_error(self):
        """chat() should handle API errors gracefully."""
        from core.api.clients.grok import GrokClient, GrokResponse

        client = GrokClient(api_key="test-key")

        with patch.object(client, '_make_request', new_callable=AsyncMock) as mock_req:
            mock_req.return_value = (429, {"error": "Rate limited"})

            response = await client.chat([{"role": "user", "content": "Hi"}])

            assert isinstance(response, GrokResponse)
            assert response.success is False
            assert response.error is not None


class TestGrokClientStreamChat:
    """Tests for stream_chat method."""

    @pytest.mark.asyncio
    async def test_stream_chat_method_exists(self):
        """stream_chat() method should exist."""
        from core.api.clients.grok import GrokClient

        client = GrokClient(api_key="test-key")
        assert hasattr(client, 'stream_chat')

    @pytest.mark.asyncio
    async def test_stream_chat_returns_async_iterator(self):
        """stream_chat() should return an async iterator."""
        from core.api.clients.grok import GrokClient
        import inspect

        client = GrokClient(api_key="test-key")

        # Mock streaming response
        async def mock_stream():
            yield {"choices": [{"delta": {"content": "Hello"}}]}
            yield {"choices": [{"delta": {"content": " world"}}]}

        with patch.object(client, '_stream_request', return_value=mock_stream()):
            result = client.stream_chat([{"role": "user", "content": "Hi"}])

            # Should be async generator
            assert inspect.isasyncgen(result)


class TestGrokClientCostTracking:
    """Tests for cost tracking integration."""

    def test_has_cost_tracker(self):
        """GrokClient should have cost tracking capability."""
        from core.api.clients.grok import GrokClient

        client = GrokClient(api_key="test-key")
        assert hasattr(client, 'get_usage_stats')

    @pytest.mark.asyncio
    async def test_tracks_token_usage(self):
        """Should track token usage from API responses."""
        from core.api.clients.grok import GrokClient

        client = GrokClient(api_key="test-key")

        with patch.object(client, '_make_request', new_callable=AsyncMock) as mock_req:
            mock_req.return_value = (200, {
                "choices": [{"message": {"content": "Hello!"}}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 5}
            })

            await client.chat([{"role": "user", "content": "Hi"}])

            stats = client.get_usage_stats()
            assert stats['total_input_tokens'] >= 10
            assert stats['total_output_tokens'] >= 5

    def test_calculates_cost(self):
        """Should calculate cost based on token usage."""
        from core.api.clients.grok import GrokClient

        client = GrokClient(api_key="test-key")

        # Use internal method to test cost calculation
        cost = client._calculate_cost({
            "prompt_tokens": 1000,
            "completion_tokens": 500
        })

        assert cost > 0
        assert isinstance(cost, float)


class TestGrokResponse:
    """Tests for GrokResponse dataclass."""

    def test_grok_response_success(self):
        """GrokResponse should store successful response."""
        from core.api.clients.grok import GrokResponse

        response = GrokResponse(
            success=True,
            content="Hello!",
            usage={"prompt_tokens": 10, "completion_tokens": 5}
        )

        assert response.success is True
        assert response.content == "Hello!"
        assert response.error is None

    def test_grok_response_failure(self):
        """GrokResponse should store error response."""
        from core.api.clients.grok import GrokResponse

        response = GrokResponse(
            success=False,
            error="Rate limited"
        )

        assert response.success is False
        assert response.content == ""
        assert response.error == "Rate limited"
