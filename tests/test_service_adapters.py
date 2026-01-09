"""
Tests for lifeos/services adapters.

Tests cover:
- LLM adapters (Groq, Ollama, OpenAI)
- Market data adapter (BirdEye)
- Notification adapter (Desktop)
- Service registry functionality
"""

import asyncio
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock
from datetime import datetime

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# Check for httpx availability
try:
    import httpx
    HAS_HTTPX = True
except ImportError:
    HAS_HTTPX = False

requires_httpx = pytest.mark.skipif(not HAS_HTTPX, reason="httpx not installed")

from lifeos.services.interfaces import (
    ServiceStatus,
    ServiceHealth,
    ServiceError,
    LLMMessage,
    LLMResponse,
    LLMConfig,
    TokenPrice,
    TokenInfo,
    LiquidityInfo,
    OHLCVCandle,
    NotificationPriority,
    NotificationResult,
    ServiceRegistry,
    llm_registry,
)


# =============================================================================
# Test ServiceError
# =============================================================================

class TestServiceError:
    """Test ServiceError exception class."""

    def test_error_message_format(self):
        """Should format error message correctly."""
        err = ServiceError(
            service_name="test_service",
            operation="test_op",
            message="Something went wrong",
        )
        assert "[test_service]" in str(err)
        assert "test_op" in str(err)
        assert "Something went wrong" in str(err)

    def test_error_retryable_default(self):
        """Should default to retryable=True."""
        err = ServiceError(
            service_name="test",
            operation="op",
            message="error",
        )
        assert err.retryable is True

    def test_error_with_original(self):
        """Should store original error."""
        original = ValueError("original error")
        err = ServiceError(
            service_name="test",
            operation="op",
            message="wrapped",
            original_error=original,
        )
        assert err.original_error is original


# =============================================================================
# Test ServiceRegistry
# =============================================================================

class TestServiceRegistry:
    """Test ServiceRegistry functionality."""

    def test_register_service(self):
        """Should register a service."""
        registry = ServiceRegistry("test")
        mock_service = MagicMock()
        mock_service.service_name = "mock"

        registry.register("mock", mock_service)

        assert registry.get("mock") is mock_service

    def test_first_registered_is_primary(self):
        """First registered service should be primary."""
        registry = ServiceRegistry("test")
        mock1 = MagicMock()
        mock2 = MagicMock()

        registry.register("first", mock1)
        registry.register("second", mock2)

        assert registry.get_primary() is mock1

    def test_explicit_primary(self):
        """Should set explicit primary."""
        registry = ServiceRegistry("test")
        mock1 = MagicMock()
        mock2 = MagicMock()

        registry.register("first", mock1)
        registry.register("second", mock2, primary=True)

        assert registry.get_primary() is mock2

    def test_get_all_services(self):
        """Should return all registered services."""
        registry = ServiceRegistry("test")
        mock1 = MagicMock()
        mock2 = MagicMock()

        registry.register("first", mock1)
        registry.register("second", mock2)

        all_services = registry.get_all()
        assert len(all_services) == 2
        assert "first" in all_services
        assert "second" in all_services

    def test_unregister_service(self):
        """Should unregister a service."""
        registry = ServiceRegistry("test")
        mock = MagicMock()

        registry.register("mock", mock)
        registry.unregister("mock")

        assert registry.get("mock") is None

    def test_set_primary(self):
        """Should change primary service."""
        registry = ServiceRegistry("test")
        mock1 = MagicMock()
        mock2 = MagicMock()

        registry.register("first", mock1)
        registry.register("second", mock2)
        registry.set_primary("second")

        assert registry.get_primary() is mock2

    def test_set_primary_not_registered(self):
        """Should raise error for unregistered service."""
        registry = ServiceRegistry("test")

        with pytest.raises(ValueError):
            registry.set_primary("nonexistent")


# =============================================================================
# Test Groq Adapter
# =============================================================================

@requires_httpx
class TestGroqAdapter:
    """Test Groq LLM adapter."""

    def test_service_name(self):
        """Should return correct service name."""
        from lifeos.services.llm import GroqLLMAdapter

        adapter = GroqLLMAdapter(api_key="test")
        assert adapter.service_name == "groq"

    def test_model_name(self):
        """Should return configured model."""
        from lifeos.services.llm import GroqLLMAdapter

        adapter = GroqLLMAdapter(api_key="test", model="mixtral-8x7b-32768")
        assert adapter.get_model_name() == "mixtral-8x7b-32768"

    def test_context_limit(self):
        """Should return correct context limit."""
        from lifeos.services.llm import GroqLLMAdapter

        adapter = GroqLLMAdapter(api_key="test", model="llama-3.3-70b-versatile")
        assert adapter.get_context_limit() == 131072

    @pytest.mark.asyncio
    async def test_chat_no_api_key(self):
        """Should raise error without API key."""
        from lifeos.services.llm import GroqLLMAdapter

        adapter = GroqLLMAdapter(api_key=None)

        with pytest.raises(ServiceError) as exc_info:
            await adapter.chat([LLMMessage(role="user", content="hello")])

        assert "No API key" in exc_info.value.message
        assert exc_info.value.retryable is False

    @pytest.mark.asyncio
    async def test_health_check_no_key(self):
        """Health check should report unavailable without key."""
        from lifeos.services.llm import GroqLLMAdapter

        adapter = GroqLLMAdapter(api_key=None)
        health = await adapter.health_check()

        assert health.status == ServiceStatus.UNAVAILABLE
        assert "No API key" in health.message


# =============================================================================
# Test Ollama Adapter
# =============================================================================

@requires_httpx
class TestOllamaAdapter:
    """Test Ollama LLM adapter."""

    def test_service_name(self):
        """Should return correct service name."""
        from lifeos.services.llm import OllamaLLMAdapter

        adapter = OllamaLLMAdapter()
        assert adapter.service_name == "ollama"

    def test_default_model(self):
        """Should use default model."""
        from lifeos.services.llm import OllamaLLMAdapter

        adapter = OllamaLLMAdapter()
        assert "llama" in adapter.get_model_name().lower()

    def test_context_limit_known_model(self):
        """Should return correct context for known models."""
        from lifeos.services.llm import OllamaLLMAdapter

        adapter = OllamaLLMAdapter(model="mistral")
        assert adapter.get_context_limit() == 32768

    def test_context_limit_unknown_model(self):
        """Should return default for unknown models."""
        from lifeos.services.llm import OllamaLLMAdapter

        adapter = OllamaLLMAdapter(model="unknown-model")
        assert adapter.get_context_limit() == 4096


# =============================================================================
# Test OpenAI Adapter
# =============================================================================

@requires_httpx
class TestOpenAIAdapter:
    """Test OpenAI LLM adapter."""

    def test_service_name(self):
        """Should return correct service name."""
        from lifeos.services.llm import OpenAILLMAdapter

        adapter = OpenAILLMAdapter(api_key="test")
        assert adapter.service_name == "openai"

    def test_context_limits(self):
        """Should return correct context limits."""
        from lifeos.services.llm import OpenAILLMAdapter

        adapter = OpenAILLMAdapter(api_key="test", model="gpt-4o")
        assert adapter.get_context_limit() == 128000

        adapter = OpenAILLMAdapter(api_key="test", model="gpt-4")
        assert adapter.get_context_limit() == 8192

    @pytest.mark.asyncio
    async def test_chat_no_api_key(self):
        """Should raise error without API key."""
        from lifeos.services.llm import OpenAILLMAdapter

        adapter = OpenAILLMAdapter(api_key=None)

        with pytest.raises(ServiceError) as exc_info:
            await adapter.chat([LLMMessage(role="user", content="hello")])

        assert "No API key" in exc_info.value.message


# =============================================================================
# Test BirdEye Adapter
# =============================================================================

class TestBirdEyeAdapter:
    """Test BirdEye market data adapter."""

    def test_service_name(self):
        """Should return correct service name."""
        from lifeos.services.market import BirdEyeMarketAdapter

        adapter = BirdEyeMarketAdapter()
        assert adapter.service_name == "birdeye"

    def test_supported_chains(self):
        """Should support solana."""
        from lifeos.services.market import BirdEyeMarketAdapter

        adapter = BirdEyeMarketAdapter()
        assert "solana" in adapter.supported_chains

    def test_resolve_known_symbol(self):
        """Should resolve known symbols to addresses."""
        from lifeos.services.market import BirdEyeMarketAdapter

        adapter = BirdEyeMarketAdapter()
        address = adapter._resolve_address("SOL")
        assert address == "So11111111111111111111111111111111111111112"

    def test_resolve_address_passthrough(self):
        """Should pass through addresses unchanged."""
        from lifeos.services.market import BirdEyeMarketAdapter

        adapter = BirdEyeMarketAdapter()
        address = "4k3Dyjzvzp8eMZWUXbBCjEvwSkkk59S5iCNLY3QrkX6R"
        resolved = adapter._resolve_address(address)
        assert resolved == address


# =============================================================================
# Test Desktop Notification Adapter
# =============================================================================

class TestDesktopNotificationAdapter:
    """Test desktop notification adapter."""

    def test_service_name(self):
        """Should return correct service name."""
        from lifeos.services.notifications import DesktopNotificationAdapter

        adapter = DesktopNotificationAdapter()
        assert adapter.service_name == "desktop_notifications"

    def test_channel(self):
        """Should return system channel."""
        from lifeos.services.notifications import DesktopNotificationAdapter

        adapter = DesktopNotificationAdapter()
        assert adapter.channel == "system"

    @pytest.mark.asyncio
    async def test_send_fallback(self):
        """Should succeed with fallback method."""
        from lifeos.services.notifications import DesktopNotificationAdapter

        adapter = DesktopNotificationAdapter()
        adapter._method = "fallback"

        result = await adapter.send("Test message", title="Test")

        assert result.success is True
        assert result.channel == "system"

    @pytest.mark.asyncio
    async def test_health_check_fallback(self):
        """Should report degraded for fallback."""
        from lifeos.services.notifications import DesktopNotificationAdapter

        adapter = DesktopNotificationAdapter()
        adapter._method = "fallback"

        health = await adapter.health_check()

        assert health.status == ServiceStatus.DEGRADED

    @pytest.mark.asyncio
    async def test_send_batch(self):
        """Should send multiple notifications."""
        from lifeos.services.notifications import DesktopNotificationAdapter

        adapter = DesktopNotificationAdapter()
        adapter._method = "fallback"

        notifications = [
            {"message": "First", "title": "Test 1"},
            {"message": "Second", "title": "Test 2"},
        ]

        results = await adapter.send_batch(notifications)

        assert len(results) == 2
        assert all(r.success for r in results)


# =============================================================================
# Test Data Classes
# =============================================================================

class TestDataClasses:
    """Test data class structures."""

    def test_llm_message(self):
        """LLMMessage should have required fields."""
        msg = LLMMessage(role="user", content="hello")
        assert msg.role == "user"
        assert msg.content == "hello"
        assert msg.name is None

    def test_llm_response(self):
        """LLMResponse should have required fields."""
        resp = LLMResponse(
            content="response",
            model="test-model",
            finish_reason="stop",
        )
        assert resp.content == "response"
        assert resp.model == "test-model"
        assert resp.usage == {}

    def test_llm_config_defaults(self):
        """LLMConfig should have sensible defaults."""
        config = LLMConfig()
        assert config.temperature == 0.7
        assert config.max_tokens == 500
        assert config.top_p == 1.0

    def test_token_price(self):
        """TokenPrice should have required fields."""
        price = TokenPrice(
            symbol="SOL",
            address="So111...",
            price_usd=100.0,
        )
        assert price.symbol == "SOL"
        assert price.price_usd == 100.0
        assert price.source == "unknown"

    def test_service_health(self):
        """ServiceHealth should have status."""
        health = ServiceHealth(status=ServiceStatus.HEALTHY)
        assert health.status == ServiceStatus.HEALTHY
        assert health.last_check is not None

    def test_notification_result(self):
        """NotificationResult should have success flag."""
        result = NotificationResult(success=True, channel="system")
        assert result.success is True
        assert result.channel == "system"
