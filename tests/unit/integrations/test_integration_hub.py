"""
Unit tests for the Integration Hub.

Tests cover:
- IntegrationHub class (register, get, is_configured, list_integrations)
- Integration abstract base class
- TelegramIntegration concrete implementation
- XIntegration concrete implementation
"""

import pytest
from unittest.mock import Mock, patch, AsyncMock
import asyncio


class TestIntegrationBase:
    """Tests for the Integration abstract base class."""

    def test_integration_has_required_properties(self):
        """Integration must have name, description, required_config."""
        from core.integrations.base import Integration

        # Integration is abstract, so we need a concrete implementation
        class TestIntegration(Integration):
            @property
            def name(self) -> str:
                return "test"

            @property
            def description(self) -> str:
                return "Test integration"

            @property
            def required_config(self) -> list:
                return ["api_key"]

            def connect(self) -> bool:
                return True

            def disconnect(self) -> None:
                pass

            def is_connected(self) -> bool:
                return True

            def health_check(self) -> bool:
                return True

        integration = TestIntegration()
        assert integration.name == "test"
        assert integration.description == "Test integration"
        assert integration.required_config == ["api_key"]

    def test_integration_abstract_methods(self):
        """Integration abstract methods must be implemented by subclasses."""
        from core.integrations.base import Integration

        # Cannot instantiate abstract class directly
        with pytest.raises(TypeError):
            Integration()

    def test_integration_connect_returns_bool(self):
        """connect() must return a boolean."""
        from core.integrations.base import Integration

        class TestIntegration(Integration):
            @property
            def name(self) -> str:
                return "test"

            @property
            def description(self) -> str:
                return "Test"

            @property
            def required_config(self) -> list:
                return []

            def connect(self) -> bool:
                return True

            def disconnect(self) -> None:
                pass

            def is_connected(self) -> bool:
                return False

            def health_check(self) -> bool:
                return True

        integration = TestIntegration()
        result = integration.connect()
        assert isinstance(result, bool)
        assert result is True

    def test_integration_health_check_returns_bool(self):
        """health_check() must return a boolean."""
        from core.integrations.base import Integration

        class TestIntegration(Integration):
            @property
            def name(self) -> str:
                return "test"

            @property
            def description(self) -> str:
                return "Test"

            @property
            def required_config(self) -> list:
                return []

            def connect(self) -> bool:
                return True

            def disconnect(self) -> None:
                pass

            def is_connected(self) -> bool:
                return True

            def health_check(self) -> bool:
                return False

        integration = TestIntegration()
        result = integration.health_check()
        assert isinstance(result, bool)


class TestIntegrationHub:
    """Tests for the IntegrationHub class."""

    def test_hub_can_be_instantiated(self):
        """IntegrationHub can be instantiated."""
        from core.integrations.hub import IntegrationHub

        hub = IntegrationHub()
        assert hub is not None

    def test_hub_register_integration(self):
        """Hub can register an integration."""
        from core.integrations.hub import IntegrationHub
        from core.integrations.base import Integration

        class MockIntegration(Integration):
            @property
            def name(self) -> str:
                return "mock"

            @property
            def description(self) -> str:
                return "Mock integration"

            @property
            def required_config(self) -> list:
                return []

            def connect(self) -> bool:
                return True

            def disconnect(self) -> None:
                pass

            def is_connected(self) -> bool:
                return True

            def health_check(self) -> bool:
                return True

        hub = IntegrationHub()
        integration = MockIntegration()
        hub.register("mock", integration)

        # Should be able to get it back
        retrieved = hub.get("mock")
        assert retrieved is integration

    def test_hub_get_nonexistent_returns_none(self):
        """Hub.get() returns None for unregistered integrations."""
        from core.integrations.hub import IntegrationHub

        hub = IntegrationHub()
        result = hub.get("nonexistent")
        assert result is None

    def test_hub_is_configured_true_when_registered(self):
        """Hub.is_configured() returns True for registered integrations."""
        from core.integrations.hub import IntegrationHub
        from core.integrations.base import Integration

        class MockIntegration(Integration):
            @property
            def name(self) -> str:
                return "mock"

            @property
            def description(self) -> str:
                return "Mock"

            @property
            def required_config(self) -> list:
                return []

            def connect(self) -> bool:
                return True

            def disconnect(self) -> None:
                pass

            def is_connected(self) -> bool:
                return True

            def health_check(self) -> bool:
                return True

        hub = IntegrationHub()
        hub.register("mock", MockIntegration())

        assert hub.is_configured("mock") is True

    def test_hub_is_configured_false_when_not_registered(self):
        """Hub.is_configured() returns False for unregistered integrations."""
        from core.integrations.hub import IntegrationHub

        hub = IntegrationHub()
        assert hub.is_configured("nonexistent") is False

    def test_hub_list_integrations(self):
        """Hub.list_integrations() returns list of registered integration names."""
        from core.integrations.hub import IntegrationHub
        from core.integrations.base import Integration

        class MockIntegration(Integration):
            @property
            def name(self) -> str:
                return "mock"

            @property
            def description(self) -> str:
                return "Mock"

            @property
            def required_config(self) -> list:
                return []

            def connect(self) -> bool:
                return True

            def disconnect(self) -> None:
                pass

            def is_connected(self) -> bool:
                return True

            def health_check(self) -> bool:
                return True

        hub = IntegrationHub()
        hub.register("integration1", MockIntegration())
        hub.register("integration2", MockIntegration())

        integrations = hub.list_integrations()
        assert isinstance(integrations, list)
        assert "integration1" in integrations
        assert "integration2" in integrations
        assert len(integrations) == 2

    def test_hub_list_integrations_empty_initially(self):
        """Hub.list_integrations() returns empty list when no integrations registered."""
        from core.integrations.hub import IntegrationHub

        hub = IntegrationHub()
        integrations = hub.list_integrations()
        assert integrations == []

    def test_hub_register_validates_integration_type(self):
        """Hub.register() only accepts Integration instances."""
        from core.integrations.hub import IntegrationHub

        hub = IntegrationHub()

        with pytest.raises(TypeError):
            hub.register("invalid", "not an integration")

        with pytest.raises(TypeError):
            hub.register("invalid", None)

    def test_hub_singleton_instance(self):
        """Hub provides a singleton instance via get_hub()."""
        from core.integrations.hub import get_hub

        hub1 = get_hub()
        hub2 = get_hub()
        assert hub1 is hub2


class TestTelegramIntegration:
    """Tests for TelegramIntegration."""

    def test_telegram_integration_has_correct_name(self):
        """TelegramIntegration has correct name property."""
        from core.integrations.telegram import TelegramIntegration

        integration = TelegramIntegration()
        assert integration.name == "telegram"

    def test_telegram_integration_has_required_config(self):
        """TelegramIntegration requires bot_token."""
        from core.integrations.telegram import TelegramIntegration

        integration = TelegramIntegration()
        assert "bot_token" in integration.required_config

    def test_telegram_connect_without_token_fails(self):
        """TelegramIntegration.connect() fails without token."""
        from core.integrations.telegram import TelegramIntegration

        integration = TelegramIntegration()
        result = integration.connect()
        assert result is False
        assert integration.is_connected() is False

    def test_telegram_connect_with_token_succeeds(self):
        """TelegramIntegration.connect() succeeds with valid token."""
        from core.integrations.telegram import TelegramIntegration

        integration = TelegramIntegration(bot_token="test_token_123")

        with patch.object(integration, '_validate_token', return_value=True):
            result = integration.connect()
            assert result is True
            assert integration.is_connected() is True

    def test_telegram_disconnect(self):
        """TelegramIntegration.disconnect() sets connected to False."""
        from core.integrations.telegram import TelegramIntegration

        integration = TelegramIntegration(bot_token="test_token")

        with patch.object(integration, '_validate_token', return_value=True):
            integration.connect()
            assert integration.is_connected() is True

            integration.disconnect()
            assert integration.is_connected() is False

    @pytest.mark.asyncio
    async def test_telegram_send_message(self):
        """TelegramIntegration.send_message() sends a message."""
        from core.integrations.telegram import TelegramIntegration

        integration = TelegramIntegration(bot_token="test_token")

        with patch.object(integration, '_validate_token', return_value=True):
            integration.connect()

        with patch.object(integration, '_send_request', new_callable=AsyncMock) as mock_send:
            mock_send.return_value = {"ok": True, "result": {"message_id": 123}}

            result = await integration.send_message(chat_id=12345, text="Hello")
            assert result is True
            mock_send.assert_called_once()

    @pytest.mark.asyncio
    async def test_telegram_send_photo(self):
        """TelegramIntegration.send_photo() sends a photo."""
        from core.integrations.telegram import TelegramIntegration

        integration = TelegramIntegration(bot_token="test_token")

        with patch.object(integration, '_validate_token', return_value=True):
            integration.connect()

        with patch.object(integration, '_send_request', new_callable=AsyncMock) as mock_send:
            mock_send.return_value = {"ok": True, "result": {"message_id": 123}}

            result = await integration.send_photo(
                chat_id=12345,
                photo="https://example.com/photo.jpg",
                caption="Test photo"
            )
            assert result is True

    @pytest.mark.asyncio
    async def test_telegram_get_updates(self):
        """TelegramIntegration.get_updates() retrieves updates."""
        from core.integrations.telegram import TelegramIntegration

        integration = TelegramIntegration(bot_token="test_token")

        with patch.object(integration, '_validate_token', return_value=True):
            integration.connect()

        with patch.object(integration, '_send_request', new_callable=AsyncMock) as mock_send:
            mock_send.return_value = {
                "ok": True,
                "result": [
                    {"update_id": 1, "message": {"text": "Hello"}},
                    {"update_id": 2, "message": {"text": "World"}}
                ]
            }

            updates = await integration.get_updates()
            assert isinstance(updates, list)
            assert len(updates) == 2

    def test_telegram_health_check_when_connected(self):
        """TelegramIntegration.health_check() returns True when connected."""
        from core.integrations.telegram import TelegramIntegration

        integration = TelegramIntegration(bot_token="test_token")

        with patch.object(integration, '_validate_token', return_value=True):
            integration.connect()
            assert integration.health_check() is True

    def test_telegram_health_check_when_disconnected(self):
        """TelegramIntegration.health_check() returns False when disconnected."""
        from core.integrations.telegram import TelegramIntegration

        integration = TelegramIntegration()
        assert integration.health_check() is False


class TestXIntegration:
    """Tests for XIntegration (X/Twitter)."""

    def test_x_integration_has_correct_name(self):
        """XIntegration has correct name property."""
        from core.integrations.x_twitter import XTwitterIntegration

        integration = XTwitterIntegration()
        assert integration.name == "x_twitter"

    def test_x_integration_has_required_config(self):
        """XIntegration requires OAuth credentials."""
        from core.integrations.x_twitter import XTwitterIntegration

        integration = XTwitterIntegration()
        required = integration.required_config
        assert "bearer_token" in required or "api_key" in required

    def test_x_connect_without_credentials_fails(self):
        """XIntegration.connect() fails without credentials."""
        from core.integrations.x_twitter import XTwitterIntegration

        integration = XTwitterIntegration()
        result = integration.connect()
        assert result is False

    def test_x_connect_with_bearer_token(self):
        """XIntegration.connect() succeeds with bearer token."""
        from core.integrations.x_twitter import XTwitterIntegration

        integration = XTwitterIntegration(bearer_token="test_bearer_token")

        with patch.object(integration, '_validate_credentials', return_value=True):
            result = integration.connect()
            assert result is True
            assert integration.is_connected() is True

    def test_x_disconnect(self):
        """XIntegration.disconnect() sets connected to False."""
        from core.integrations.x_twitter import XTwitterIntegration

        integration = XTwitterIntegration(bearer_token="test_token")

        with patch.object(integration, '_validate_credentials', return_value=True):
            integration.connect()
            integration.disconnect()
            assert integration.is_connected() is False

    @pytest.mark.asyncio
    async def test_x_post_tweet_stub(self):
        """XIntegration.post_tweet() is a stub that returns placeholder."""
        from core.integrations.x_twitter import XTwitterIntegration

        integration = XTwitterIntegration(bearer_token="test_token")

        with patch.object(integration, '_validate_credentials', return_value=True):
            integration.connect()

        # Stub implementation should return a dict with tweet info
        result = await integration.post_tweet("Test tweet content")
        assert isinstance(result, dict)
        assert "id" in result or "stub" in result

    @pytest.mark.asyncio
    async def test_x_get_mentions_stub(self):
        """XIntegration.get_mentions() is a stub that returns placeholder."""
        from core.integrations.x_twitter import XTwitterIntegration

        integration = XTwitterIntegration(bearer_token="test_token")

        with patch.object(integration, '_validate_credentials', return_value=True):
            integration.connect()

        # Stub implementation should return a list
        result = await integration.get_mentions()
        assert isinstance(result, list)

    def test_x_health_check(self):
        """XIntegration.health_check() works correctly."""
        from core.integrations.x_twitter import XTwitterIntegration

        integration = XTwitterIntegration(bearer_token="test_token")

        # When not connected
        assert integration.health_check() is False

        # When connected
        with patch.object(integration, '_validate_credentials', return_value=True):
            integration.connect()
            assert integration.health_check() is True


class TestIntegrationHubWithConcreteIntegrations:
    """Tests for IntegrationHub with concrete integrations."""

    def test_hub_registers_telegram(self):
        """Hub can register TelegramIntegration."""
        from core.integrations.hub import IntegrationHub
        from core.integrations.telegram import TelegramIntegration

        hub = IntegrationHub()
        telegram = TelegramIntegration(bot_token="test_token")
        hub.register("telegram", telegram)

        retrieved = hub.get("telegram")
        assert retrieved is telegram
        assert retrieved.name == "telegram"

    def test_hub_registers_x_twitter(self):
        """Hub can register XIntegration."""
        from core.integrations.hub import IntegrationHub
        from core.integrations.x_twitter import XTwitterIntegration

        hub = IntegrationHub()
        x = XTwitterIntegration(bearer_token="test_token")
        hub.register("x_twitter", x)

        retrieved = hub.get("x_twitter")
        assert retrieved is x
        assert retrieved.name == "x_twitter"

    def test_hub_connect_all(self):
        """Hub can connect all registered integrations."""
        from core.integrations.hub import IntegrationHub
        from core.integrations.telegram import TelegramIntegration
        from core.integrations.x_twitter import XTwitterIntegration

        hub = IntegrationHub()

        telegram = TelegramIntegration(bot_token="test_token")
        x = XTwitterIntegration(bearer_token="test_token")

        with patch.object(telegram, '_validate_token', return_value=True):
            with patch.object(x, '_validate_credentials', return_value=True):
                hub.register("telegram", telegram)
                hub.register("x_twitter", x)

                results = hub.connect_all()

                assert "telegram" in results
                assert "x_twitter" in results
                assert results["telegram"] is True
                assert results["x_twitter"] is True

    def test_hub_health_check_all(self):
        """Hub can health check all registered integrations."""
        from core.integrations.hub import IntegrationHub
        from core.integrations.telegram import TelegramIntegration
        from core.integrations.x_twitter import XTwitterIntegration

        hub = IntegrationHub()

        telegram = TelegramIntegration(bot_token="test_token")
        x = XTwitterIntegration(bearer_token="test_token")

        with patch.object(telegram, '_validate_token', return_value=True):
            with patch.object(x, '_validate_credentials', return_value=True):
                hub.register("telegram", telegram)
                hub.register("x_twitter", x)

                telegram.connect()
                x.connect()

                health = hub.health_check_all()

                assert "telegram" in health
                assert "x_twitter" in health
                assert health["telegram"] is True
                assert health["x_twitter"] is True
