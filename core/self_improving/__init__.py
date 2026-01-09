"""
Jarvis Self-Improving Core

A self-improving AI system built on the Reflexion pattern with:
- SQLite-based persistent memory (facts, reflections, predictions)
- Trust ladder for gradual autonomy
- Proactive suggestion engine
- Learning extraction from conversations
- Action framework with trust-based permissions

Architecture based on January 2026 research:
- Reflexion (NeurIPS 2023): Verbal self-reflection beats weight updates
- SQL-native memory: 80-90% cheaper than vector databases
- Gradual autonomy: Trust is earned, not given

Usage:
    from core.self_improving import create_orchestrator

    # Initialize
    orchestrator = create_orchestrator(
        db_path="data/jarvis_memory.db",
        llm_client=anthropic_client,
    )

    # Before responding to user
    context = orchestrator.build_response_context(user_query)

    # After conversation ends
    orchestrator.learn_from_conversation_sync(messages, session_id)

    # Nightly self-improvement (schedule at 3am)
    orchestrator.run_nightly_cycle_sync()
"""

from core.self_improving.memory.store import MemoryStore
from core.self_improving.memory.models import (
    Entity,
    Fact,
    Reflection,
    Prediction,
    Interaction,
    ContextBundle,
)
from core.self_improving.trust.ladder import TrustManager, TrustLevel
from core.self_improving.reflexion.engine import ReflexionEngine
from core.self_improving.proactive.engine import ProactiveEngine, SuggestionType
from core.self_improving.learning.extractor import LearningExtractor
from core.self_improving.actions.framework import (
    Action,
    ActionRegistry,
    ActionResult,
    ActionType,
    create_default_registry,
)
from core.self_improving.orchestrator import (
    SelfImprovingOrchestrator,
    create_orchestrator,
)
from core.self_improving.scheduler import (
    SelfImprovingScheduler,
    create_scheduler,
)

__all__ = [
    # Memory
    "MemoryStore",
    "Entity",
    "Fact",
    "Reflection",
    "Prediction",
    "Interaction",
    "ContextBundle",
    # Trust
    "TrustManager",
    "TrustLevel",
    # Reflexion
    "ReflexionEngine",
    # Proactive
    "ProactiveEngine",
    "SuggestionType",
    # Learning
    "LearningExtractor",
    # Actions
    "Action",
    "ActionRegistry",
    "ActionResult",
    "ActionType",
    "create_default_registry",
    # Orchestrator
    "SelfImprovingOrchestrator",
    "create_orchestrator",
    # Scheduler
    "SelfImprovingScheduler",
    "create_scheduler",
]

__version__ = "0.1.0"
