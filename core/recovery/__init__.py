"""
JARVIS Unified Recovery Engine

One brain for all recovery decisions. Bots are adapters, not decision-makers.

All retries, cooldowns, and circuit breakers live in one place.

Usage:
    from core.recovery import get_recovery_engine, RecoveryContext

    engine = get_recovery_engine()

    # Register a component
    engine.register_component("x_bot", ComponentConfig(
        max_retries=3,
        circuit_threshold=5,
        cooldown_seconds=60,
    ))

    # Execute with automatic recovery
    result = await engine.execute_with_recovery(
        component="x_bot",
        operation="post_tweet",
        func=post_tweet_func,
        args=(tweet_content,),
    )

    # Check if component can run
    if engine.can_execute("x_bot"):
        await do_something()

    # Record outcomes
    engine.record_success("x_bot", "post_tweet")
    engine.record_failure("x_bot", "post_tweet", error="API error")
"""

from .engine import (
    RecoveryEngine,
    get_recovery_engine,
)
from .config import (
    ComponentConfig,
    RecoveryPolicy,
    RecoveryOutcome,
    RecoveryContext,
)
from .adapters import (
    TelegramAdapter,
    XBotAdapter,
    TradingAdapter,
    ToolAdapter,
)

__all__ = [
    # Engine
    "RecoveryEngine",
    "get_recovery_engine",
    # Config
    "ComponentConfig",
    "RecoveryPolicy",
    "RecoveryOutcome",
    "RecoveryContext",
    # Adapters
    "TelegramAdapter",
    "XBotAdapter",
    "TradingAdapter",
    "ToolAdapter",
]
