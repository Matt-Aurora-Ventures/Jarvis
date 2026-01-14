"""
JARVIS LLM Module - Unified Multi-Provider AI

Provides:
- Unified access to multiple LLM backends (Ollama, Groq, xAI, OpenRouter)
- Task-based routing to appropriate models
- Structured output extraction
- Rate limiting and fallback

Usage:
    from core.llm import get_llm, quick_generate, route_task, TaskType

    # Quick one-off
    response = await quick_generate("What's the weather?")

    # Task-based routing
    analysis = await route_task("Analyze BTC", TaskType.TRADING)

    # Full control
    llm = await get_llm()
    response = await llm.generate(
        "Analyze this token",
        provider=LLMProvider.GROQ,
        temperature=0.5
    )
"""

# Structured outputs
from .structured_output import (
    StructuredLLM,
    create_structured_client,
    TradingSignal,
    SentimentAnalysis,
    ConversationIntent,
    TaskExtraction,
    ExtractedEntity,
)

# Multi-provider support
from .providers import (
    LLMProvider,
    LLMConfig,
    LLMResponse,
    Message,
    BaseLLMProvider,
    OllamaProvider,
    GroqProvider,
    XAIProvider,
    OpenRouterProvider,
    UnifiedLLM,
    create_provider,
    create_default_llm,
    get_default_configs,
    get_llm,
    quick_generate,
    quick_chat,
)

# Task-based routing
from .router import (
    TaskType,
    RoutingRule,
    LLMRouter,
    get_router,
    route_task,
    quick_analyze,
    quick_trade_analysis,
    quick_sentiment,
    quick_summarize,
)

# Cost tracking
from .cost_tracker import (
    LLMCostTracker,
    UsageRecord,
    UsageStats,
    BudgetAlert,
    MODEL_PRICING,
    get_cost_tracker,
    track_llm_cost,
)

__all__ = [
    # Structured outputs
    "StructuredLLM",
    "create_structured_client",
    "TradingSignal",
    "SentimentAnalysis",
    "ConversationIntent",
    "TaskExtraction",
    "ExtractedEntity",

    # Provider types
    "LLMProvider",
    "LLMConfig",
    "LLMResponse",
    "Message",

    # Provider classes
    "BaseLLMProvider",
    "OllamaProvider",
    "GroqProvider",
    "XAIProvider",
    "OpenRouterProvider",
    "UnifiedLLM",

    # Factory functions
    "create_provider",
    "create_default_llm",
    "get_default_configs",
    "get_llm",
    "quick_generate",
    "quick_chat",

    # Routing
    "TaskType",
    "RoutingRule",
    "LLMRouter",
    "get_router",
    "route_task",
    "quick_analyze",
    "quick_trade_analysis",
    "quick_sentiment",
    "quick_summarize",

    # Cost tracking
    "LLMCostTracker",
    "UsageRecord",
    "UsageStats",
    "BudgetAlert",
    "MODEL_PRICING",
    "get_cost_tracker",
    "track_llm_cost",
]
