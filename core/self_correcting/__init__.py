"""
Self-Correcting AI System

A comprehensive self-improvement system for Jarvis bots.

Components:
- SharedMemory: Centralized learning storage across all bots
- MessageBus: Real-time inter-bot communication
- OllamaRouter: Local AI model integration with automatic fallback
- SelfAdjuster: Automatic parameter tuning based on performance

Usage:
    from core.self_correcting import (
        get_shared_memory,
        get_message_bus,
        get_ollama_router,
        get_self_adjuster
    )

    # Store a learning
    memory = get_shared_memory()
    memory.add_learning(
        component="trading_bot",
        learning_type=LearningType.SUCCESS_PATTERN,
        content="Buy when RSI < 30 and volume > 2x avg",
        confidence=0.9
    )

    # Send a message to other bots
    bus = get_message_bus()
    await bus.publish(
        sender="sentiment_bot",
        message_type=MessageType.SENTIMENT_CHANGED,
        data={"token": "SOL", "sentiment": "bullish", "score": 0.8}
    )

    # Query AI (will use Ollama if available, otherwise Claude)
    router = get_ollama_router()
    response = await router.query(
        prompt="Analyze this tweet sentiment...",
        task_type=TaskType.SENTIMENT_ANALYSIS
    )

    # Register tunable parameters
    adjuster = get_self_adjuster()
    adjuster.register_component("trading_bot", {
        "stop_loss_pct": Parameter(
            name="stop_loss_pct",
            current_value=5.0,
            min_value=1.0,
            max_value=10.0,
            step=0.5,
            affects_metrics=[MetricType.SUCCESS_RATE, MetricType.COST]
        )
    })
"""

from .shared_memory import (
    SharedMemory,
    Learning,
    LearningType,
    get_shared_memory
)

from .message_bus import (
    MessageBus,
    Message,
    MessageType,
    MessagePriority,
    get_message_bus
)

from .ollama_router import (
    OllamaRouter,
    TaskType,
    ModelTier,
    ModelResponse,
    get_ollama_router
)

from .self_adjuster import (
    SelfAdjuster,
    Parameter,
    MetricType,
    get_self_adjuster
)

__all__ = [
    # Shared Memory
    "SharedMemory",
    "Learning",
    "LearningType",
    "get_shared_memory",

    # Message Bus
    "MessageBus",
    "Message",
    "MessageType",
    "MessagePriority",
    "get_message_bus",

    # Ollama Router
    "OllamaRouter",
    "TaskType",
    "ModelTier",
    "ModelResponse",
    "get_ollama_router",

    # Self Adjuster
    "SelfAdjuster",
    "Parameter",
    "MetricType",
    "get_self_adjuster",
]
