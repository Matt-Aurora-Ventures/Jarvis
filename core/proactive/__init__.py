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

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

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

def _load_legacy_proactive_module():
    legacy_path = Path(__file__).resolve().parents[1] / "proactive.py"
    if not legacy_path.exists():
        return None
    spec = spec_from_file_location("core._proactive_legacy", legacy_path)
    if spec is None or spec.loader is None:
        return None
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_legacy_proactive = _load_legacy_proactive_module()
ProactiveMonitor = (
    getattr(_legacy_proactive, "ProactiveMonitor", None) if _legacy_proactive else None
)
start_monitoring = (
    getattr(_legacy_proactive, "start_monitoring", None) if _legacy_proactive else None
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
    "ProactiveMonitor",
    "start_monitoring",
]
