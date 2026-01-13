"""
JARVIS Proactive Module - Anticipatory AI Assistance

Provides proactive suggestions and notifications:
- Time-based triggers (morning briefing, market hours)
- Event-based triggers (price alerts, news)
- Pattern-based triggers (detected habits)

Usage:
    from core.proactive import get_suggestion_engine, suggest

    # Get engine
    engine = get_suggestion_engine()

    # Add price alert
    engine.add_price_alert("BTC", 100000, "above")

    # Add reminder
    engine.add_scheduled_reminder(
        "Check portfolio",
        "Time to review your portfolio",
        times=[time(9, 0), time(16, 0)]
    )

    # Manual suggestion
    suggest("Opportunity", "BTC momentum increasing", Priority.HIGH)
"""

from .suggestions import (
    # Types
    TriggerType,
    SuggestionCategory,
    Priority,
    Suggestion,

    # Triggers
    SuggestionTrigger,
    TimeBasedTrigger,
    ThresholdTrigger,
    PatternTrigger,

    # Engine
    ProactiveSuggestionEngine,
    get_suggestion_engine,
    start_suggestion_engine,

    # Helper
    suggest,
)

__all__ = [
    "TriggerType",
    "SuggestionCategory",
    "Priority",
    "Suggestion",
    "SuggestionTrigger",
    "TimeBasedTrigger",
    "ThresholdTrigger",
    "PatternTrigger",
    "ProactiveSuggestionEngine",
    "get_suggestion_engine",
    "start_suggestion_engine",
    "suggest",
]
