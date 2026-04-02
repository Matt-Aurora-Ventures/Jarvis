"""
Service Abstraction Layer - Core Interfaces

Defines abstract base classes for all service types in Jarvis.
These interfaces enable:
- Provider swapping without code changes
- Consistent error handling
- Testability through mocking
- Clear contracts between components

Architecture inspired by ElizaOS, adapted for Python async patterns.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, AsyncIterator, Callable, Dict, List, Optional, TypeVar, Generic
import logging

logger = logging.getLogger(__name__)


# =============================================================================
# Common Types
# =============================================================================

class ServiceStatus(Enum):
    """Service health status."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"
    INITIALIZING = "initializing"


@dataclass
class ServiceHealth:
    """Health check result for a service."""
    status: ServiceStatus
    latency_ms: Optional[float] = None
    message: Optional[str] = None
    last_check: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ServiceError(Exception):
    """Base exception for service errors."""
    service_name: str
    operation: str
    message: str
    original_error: Optional[Exception] = None
    retryable: bool = True

    def __str__(self) -> str:
        return f"[{self.service_name}] {self.operation} failed: {self.message}"


# =============================================================================
# LLM Service Interface
# =============================================================================

@dataclass
class LLMMessage:
    """A message in a conversation."""
    role: str  # "system", "user", "assistant"
    content: str
    name: Optional[str] = None
    tool_calls: Optional[List[Dict]] = None
    tool_call_id: Optional[str] = None


@dataclass
class LLMResponse:
    """Response from an LLM generation."""
    content: str
    model: str
    finish_reason: str  # "stop", "length", "tool_calls"
    usage: Dict[str, int] = field(default_factory=dict)  # prompt_tokens, completion_tokens
    tool_calls: Optional[List[Dict]] = None
    raw_response: Optional[Any] = None


@dataclass
class LLMConfig:
    """Configuration for LLM generation."""
    temperature: float = 0.7
    max_tokens: int = 500
    top_p: float = 1.0
    frequency_penalty: float = 0.0
    presence_penalty: float = 0.0
    stop: Optional[List[str]] = None
    tools: Optional[List[Dict]] = None
    tool_choice: Optional[str] = None  # "auto", "none", or specific tool


class LLMService(ABC):
    """
    Abstract interface for Language Model services.

    Implementations should handle:
    - Provider-specific authentication
    - Rate limiting and retries
    - Error normalization
    - Token counting

    Example:
        service = GroqLLMAdapter(api_key="...")
        response = await service.generate("What is the weather?")
        print(response.content)
    """

    @property
    @abstractmethod
    def service_name(self) -> str:
        """Return the service identifier (e.g., 'groq', 'ollama')."""
        ...

    @abstractmethod
    async def generate(
        self,
        prompt: str,
        config: Optional[LLMConfig] = None,
        system_prompt: Optional[str] = None,
    ) -> LLMResponse:
        """
        Generate a response from a simple prompt.

        Args:
            prompt: User prompt text
            config: Generation configuration
            system_prompt: Optional system prompt

        Returns:
            LLMResponse with generated content

        Raises:
            ServiceError: On generation failure
        """
        ...

    @abstractmethod
    async def chat(
        self,
        messages: List[LLMMessage],
        config: Optional[LLMConfig] = None,
    ) -> LLMResponse:
        """
        Generate response from a conversation history.

        Args:
            messages: List of conversation messages
            config: Generation configuration

        Returns:
            LLMResponse with generated content
        """
        ...

    @abstractmethod
    async def stream(
        self,
        prompt: str,
        config: Optional[LLMConfig] = None,
        system_prompt: Optional[str] = None,
    ) -> AsyncIterator[str]:
        """
        Stream response tokens.

        Args:
            prompt: User prompt text
            config: Generation configuration
            system_prompt: Optional system prompt

        Yields:
            String chunks as they are generated
        """
        ...

    @abstractmethod
    def get_context_limit(self) -> int:
        """Return max context window size in tokens."""
        ...

    @abstractmethod
    def get_model_name(self) -> str:
        """Return the current model identifier."""
        ...

    @abstractmethod
    async def health_check(self) -> ServiceHealth:
        """Check service availability and latency."""
        ...

    def count_tokens(self, text: str) -> int:
        """
        Estimate token count for text.
        Default implementation uses rough heuristic.
        Override for model-specific tokenization.
        """
        # Rough estimate: ~4 chars per token
        return len(text) // 4


# =============================================================================
# Market Data Service Interface
# =============================================================================

@dataclass
class TokenPrice:
    """Token price information."""
    symbol: str
    address: Optional[str]
    price_usd: float
    change_24h: Optional[float] = None
    change_1h: Optional[float] = None
    volume_24h: Optional[float] = None
    market_cap: Optional[float] = None
    last_updated: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    source: str = "unknown"


@dataclass
class TokenInfo:
    """Detailed token information."""
    symbol: str
    name: str
    address: str
    decimals: int
    chain: str = "solana"
    logo_url: Optional[str] = None
    website: Optional[str] = None
    twitter: Optional[str] = None
    telegram: Optional[str] = None
    description: Optional[str] = None
    tags: List[str] = field(default_factory=list)


@dataclass
class LiquidityInfo:
    """Token liquidity information."""
    token_address: str
    total_liquidity_usd: float
    pools: List[Dict[str, Any]] = field(default_factory=list)
    main_pool_address: Optional[str] = None
    main_pool_dex: Optional[str] = None
    lp_locked_percent: Optional[float] = None
    last_updated: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class OHLCVCandle:
    """OHLCV candlestick data."""
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float


class MarketDataService(ABC):
    """
    Abstract interface for market data providers.

    Implementations should handle:
    - API rate limiting
    - Data caching (configurable TTL)
    - Error normalization
    - Multiple chains if supported

    Example:
        service = BirdeyeMarketAdapter(api_key="...")
        price = await service.get_price("SOL")
        print(f"SOL is ${price.price_usd}")
    """

    @property
    @abstractmethod
    def service_name(self) -> str:
        """Return the service identifier."""
        ...

    @property
    @abstractmethod
    def supported_chains(self) -> List[str]:
        """Return list of supported blockchain networks."""
        ...

    @abstractmethod
    async def get_price(self, token: str, chain: str = "solana") -> TokenPrice:
        """
        Get current price for a token.

        Args:
            token: Token symbol or address
            chain: Blockchain network

        Returns:
            TokenPrice with current data

        Raises:
            ServiceError: If token not found or API fails
        """
        ...

    @abstractmethod
    async def get_token_info(self, token: str, chain: str = "solana") -> TokenInfo:
        """
        Get detailed token information.

        Args:
            token: Token symbol or address
            chain: Blockchain network

        Returns:
            TokenInfo with metadata
        """
        ...

    @abstractmethod
    async def get_liquidity(self, token: str, chain: str = "solana") -> LiquidityInfo:
        """
        Get liquidity information for a token.

        Args:
            token: Token symbol or address
            chain: Blockchain network

        Returns:
            LiquidityInfo with pool data
        """
        ...

    @abstractmethod
    async def get_ohlcv(
        self,
        token: str,
        interval: str = "1h",
        limit: int = 100,
        chain: str = "solana",
    ) -> List[OHLCVCandle]:
        """
        Get historical OHLCV data.

        Args:
            token: Token symbol or address
            interval: Candle interval (1m, 5m, 15m, 1h, 4h, 1d)
            limit: Number of candles to return
            chain: Blockchain network

        Returns:
            List of OHLCV candles, oldest first
        """
        ...

    @abstractmethod
    async def search_tokens(
        self,
        query: str,
        chain: str = "solana",
        limit: int = 10,
    ) -> List[TokenInfo]:
        """
        Search for tokens by name or symbol.

        Args:
            query: Search string
            chain: Blockchain network
            limit: Max results to return

        Returns:
            List of matching tokens
        """
        ...

    @abstractmethod
    async def health_check(self) -> ServiceHealth:
        """Check service availability and latency."""
        ...


# =============================================================================
# Notification Service Interface
# =============================================================================

class NotificationPriority(Enum):
    """Notification priority levels."""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class NotificationResult:
    """Result of sending a notification."""
    success: bool
    notification_id: Optional[str] = None
    channel: str = "unknown"
    error: Optional[str] = None
    delivered_at: Optional[datetime] = None


class NotificationService(ABC):
    """
    Abstract interface for notification delivery.

    Implementations should handle:
    - Platform-specific delivery (macOS, Windows, Linux)
    - Multiple channels (system, Telegram, Discord, etc.)
    - Priority-based routing
    - Delivery confirmation

    Example:
        service = MacOSNotificationAdapter()
        result = await service.send("Trade executed!", priority=NotificationPriority.HIGH)
        if result.success:
            print("User notified")
    """

    @property
    @abstractmethod
    def service_name(self) -> str:
        """Return the service identifier."""
        ...

    @property
    @abstractmethod
    def channel(self) -> str:
        """Return the notification channel (e.g., 'system', 'telegram')."""
        ...

    @abstractmethod
    async def send(
        self,
        message: str,
        title: Optional[str] = None,
        priority: NotificationPriority = NotificationPriority.NORMAL,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> NotificationResult:
        """
        Send a notification.

        Args:
            message: Notification body text
            title: Optional notification title
            priority: Priority level
            metadata: Additional data (icons, actions, etc.)

        Returns:
            NotificationResult indicating success/failure
        """
        ...

    @abstractmethod
    async def send_batch(
        self,
        notifications: List[Dict[str, Any]],
    ) -> List[NotificationResult]:
        """
        Send multiple notifications.

        Args:
            notifications: List of notification dicts with message, title, priority

        Returns:
            List of results for each notification
        """
        ...

    @abstractmethod
    async def health_check(self) -> ServiceHealth:
        """Check service availability."""
        ...


# =============================================================================
# Service Registry
# =============================================================================

T = TypeVar('T')


class ServiceRegistry(Generic[T]):
    """
    Generic service registry for managing service instances.
    Supports multiple implementations with priority-based selection.
    """

    def __init__(self, service_type: str):
        self._service_type = service_type
        self._services: Dict[str, T] = {}
        self._primary: Optional[str] = None
        self._fallback_order: List[str] = []

    def register(
        self,
        name: str,
        service: T,
        primary: bool = False,
    ) -> None:
        """Register a service instance."""
        self._services[name] = service
        if primary or self._primary is None:
            self._primary = name
        if name not in self._fallback_order:
            self._fallback_order.append(name)
        logger.info(f"Registered {self._service_type} service: {name}")

    def unregister(self, name: str) -> None:
        """Remove a service from the registry."""
        if name in self._services:
            del self._services[name]
            if name in self._fallback_order:
                self._fallback_order.remove(name)
            if self._primary == name:
                self._primary = self._fallback_order[0] if self._fallback_order else None

    def get(self, name: Optional[str] = None) -> Optional[T]:
        """Get a service by name, or the primary service."""
        if name:
            return self._services.get(name)
        return self._services.get(self._primary) if self._primary else None

    def get_primary(self) -> Optional[T]:
        """Get the primary service."""
        return self.get(self._primary)

    def get_all(self) -> Dict[str, T]:
        """Get all registered services."""
        return dict(self._services)

    def set_primary(self, name: str) -> None:
        """Set the primary service."""
        if name in self._services:
            self._primary = name
        else:
            raise ValueError(f"Service '{name}' not registered")

    def set_fallback_order(self, order: List[str]) -> None:
        """Set the fallback order for service selection."""
        for name in order:
            if name not in self._services:
                raise ValueError(f"Service '{name}' not registered")
        self._fallback_order = order

    async def get_healthy(self) -> Optional[T]:
        """Get the first healthy service in fallback order."""
        for name in self._fallback_order:
            service = self._services.get(name)
            if service:
                try:
                    health = await service.health_check()
                    if health.status in (ServiceStatus.HEALTHY, ServiceStatus.DEGRADED):
                        return service
                except Exception as e:
                    logger.warning(f"Health check failed for {name}: {e}")
        return None


# =============================================================================
# Global Registries
# =============================================================================

llm_registry: ServiceRegistry[LLMService] = ServiceRegistry("LLM")
market_registry: ServiceRegistry[MarketDataService] = ServiceRegistry("MarketData")
notification_registry: ServiceRegistry[NotificationService] = ServiceRegistry("Notification")


def get_llm_service(name: Optional[str] = None) -> Optional[LLMService]:
    """Get an LLM service by name or the primary."""
    return llm_registry.get(name)


def get_market_service(name: Optional[str] = None) -> Optional[MarketDataService]:
    """Get a market data service by name or the primary."""
    return market_registry.get(name)


def get_notification_service(name: Optional[str] = None) -> Optional[NotificationService]:
    """Get a notification service by name or the primary."""
    return notification_registry.get(name)
