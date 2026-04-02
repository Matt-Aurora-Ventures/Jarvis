"""
Jarvis Service Abstraction Layer

Provides unified interfaces for:
- LLM providers (Groq, Ollama, OpenAI)
- Market data (BirdEye, DexScreener)
- Notifications (macOS, Windows, Linux, Telegram)

Usage:
    from lifeos.services import get_llm_service, get_market_service

    # Get primary LLM service
    llm = get_llm_service()
    response = await llm.generate("Hello, world!")

    # Get specific service
    groq = get_llm_service("groq")
"""

from lifeos.services.interfaces import (
    # Types
    ServiceStatus,
    ServiceHealth,
    ServiceError,
    # LLM
    LLMService,
    LLMMessage,
    LLMResponse,
    LLMConfig,
    # Market
    MarketDataService,
    TokenPrice,
    TokenInfo,
    LiquidityInfo,
    OHLCVCandle,
    # Notifications
    NotificationService,
    NotificationPriority,
    NotificationResult,
    # Registry
    ServiceRegistry,
    llm_registry,
    market_registry,
    notification_registry,
    get_llm_service,
    get_market_service,
    get_notification_service,
)

__all__ = [
    # Types
    "ServiceStatus",
    "ServiceHealth",
    "ServiceError",
    # LLM
    "LLMService",
    "LLMMessage",
    "LLMResponse",
    "LLMConfig",
    # Market
    "MarketDataService",
    "TokenPrice",
    "TokenInfo",
    "LiquidityInfo",
    "OHLCVCandle",
    # Notifications
    "NotificationService",
    "NotificationPriority",
    "NotificationResult",
    # Registry
    "ServiceRegistry",
    "llm_registry",
    "market_registry",
    "notification_registry",
    "get_llm_service",
    "get_market_service",
    "get_notification_service",
]
