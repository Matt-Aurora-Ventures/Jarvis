"""
Tests for APIClientFactory class.

TDD Phase 1: Write failing tests first.
"""

import pytest
from unittest.mock import MagicMock, patch


class TestAPIClientFactory:
    """Tests for the APIClientFactory class."""

    def test_import_factory(self):
        """Should be able to import APIClientFactory."""
        from core.api.factory import APIClientFactory
        assert APIClientFactory is not None

    def test_factory_singleton(self):
        """Factory should implement singleton pattern."""
        from core.api.factory import APIClientFactory

        factory1 = APIClientFactory()
        factory2 = APIClientFactory()
        assert factory1 is factory2

    def test_get_factory_function(self):
        """Should have a get_factory convenience function."""
        from core.api.factory import get_factory, APIClientFactory

        factory = get_factory()
        assert isinstance(factory, APIClientFactory)


class TestAPIClientFactoryCreate:
    """Tests for create method."""

    def test_create_returns_new_client(self):
        """create() should return a new client instance."""
        from core.api.factory import APIClientFactory
        from core.api.base import BaseAPIClient

        factory = APIClientFactory()
        client = factory.create("grok")

        assert client is not None
        assert isinstance(client, BaseAPIClient)

    def test_create_unknown_provider_raises(self):
        """create() should raise ValueError for unknown provider."""
        from core.api.factory import APIClientFactory

        factory = APIClientFactory()

        with pytest.raises(ValueError, match="Unknown provider"):
            factory.create("unknown_provider")

    def test_create_with_config(self):
        """create() should pass config to client."""
        from core.api.factory import APIClientFactory

        factory = APIClientFactory()
        client = factory.create("grok", api_key="test-key", timeout=60)

        assert client.timeout == 60


class TestAPIClientFactoryGetClient:
    """Tests for get_client method (cached)."""

    def test_get_client_returns_cached(self):
        """get_client() should return cached instance."""
        from core.api.factory import APIClientFactory

        # Reset singleton for fresh test
        APIClientFactory._instance = None
        factory = APIClientFactory()

        client1 = factory.get_client("grok")
        client2 = factory.get_client("grok")

        assert client1 is client2

    def test_get_client_different_providers(self):
        """get_client() should return different instances for different providers."""
        from core.api.factory import APIClientFactory

        APIClientFactory._instance = None
        factory = APIClientFactory()

        grok_client = factory.get_client("grok")
        telegram_client = factory.get_client("telegram")

        assert grok_client is not telegram_client

    def test_get_client_with_force_new(self):
        """get_client() with force_new should return new instance."""
        from core.api.factory import APIClientFactory

        APIClientFactory._instance = None
        factory = APIClientFactory()

        client1 = factory.get_client("grok")
        client2 = factory.get_client("grok", force_new=True)

        assert client1 is not client2


class TestAPIClientFactoryRegister:
    """Tests for register method."""

    def test_register_new_provider(self):
        """register() should add new provider."""
        from core.api.factory import APIClientFactory
        from core.api.base import BaseAPIClient

        class CustomClient(BaseAPIClient):
            @property
            def provider(self) -> str:
                return "custom"

            @property
            def base_url(self) -> str:
                return "https://api.custom.com"

        APIClientFactory._instance = None
        factory = APIClientFactory()

        factory.register("custom", CustomClient)
        client = factory.create("custom")

        assert client.provider == "custom"

    def test_register_overwrite_existing(self):
        """register() should overwrite existing provider."""
        from core.api.factory import APIClientFactory
        from core.api.base import BaseAPIClient

        class NewGrokClient(BaseAPIClient):
            @property
            def provider(self) -> str:
                return "grok-v2"

            @property
            def base_url(self) -> str:
                return "https://api.x.ai/v2"

        APIClientFactory._instance = None
        factory = APIClientFactory()

        factory.register("grok", NewGrokClient)
        client = factory.create("grok")

        assert client.provider == "grok-v2"


class TestAPIClientFactorySupportedProviders:
    """Tests for supported providers."""

    def test_grok_provider_registered(self):
        """Grok provider should be registered by default."""
        from core.api.factory import APIClientFactory

        APIClientFactory._instance = None
        factory = APIClientFactory()

        assert "grok" in factory.providers

    def test_telegram_provider_registered(self):
        """Telegram provider should be registered by default."""
        from core.api.factory import APIClientFactory

        APIClientFactory._instance = None
        factory = APIClientFactory()

        assert "telegram" in factory.providers

    def test_openai_provider_registered(self):
        """OpenAI provider should be registered by default."""
        from core.api.factory import APIClientFactory

        APIClientFactory._instance = None
        factory = APIClientFactory()

        assert "openai" in factory.providers

    def test_anthropic_provider_registered(self):
        """Anthropic provider should be registered by default."""
        from core.api.factory import APIClientFactory

        APIClientFactory._instance = None
        factory = APIClientFactory()

        assert "anthropic" in factory.providers

    def test_providers_property(self):
        """providers property should list all registered providers."""
        from core.api.factory import APIClientFactory

        APIClientFactory._instance = None
        factory = APIClientFactory()

        providers = factory.providers
        assert isinstance(providers, list)
        assert len(providers) >= 4  # At least grok, telegram, openai, anthropic


class TestAPIClientFactoryHealthCheck:
    """Tests for health check functionality."""

    @pytest.mark.asyncio
    async def test_health_check_all(self):
        """health_check_all() should check all cached clients."""
        from core.api.factory import APIClientFactory

        APIClientFactory._instance = None
        factory = APIClientFactory()

        # Create some clients first
        factory.get_client("grok")
        factory.get_client("telegram")

        results = await factory.health_check_all()

        assert isinstance(results, dict)
        assert "grok" in results
        assert "telegram" in results
