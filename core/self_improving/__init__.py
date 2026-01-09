"""
Jarvis Self-Improving Core

A self-improving AI system built on the Reflexion pattern with:
- SQLite-based persistent memory (facts, reflections, predictions)
- Trust ladder for gradual autonomy
- Proactive suggestion engine
- Learning extraction from conversations

Architecture based on January 2026 research:
- Reflexion (NeurIPS 2023): Verbal self-reflection beats weight updates
- SQL-native memory: 80-90% cheaper than vector databases
- Gradual autonomy: Trust is earned, not given
"""

from core.self_improving.memory.store import MemoryStore
from core.self_improving.trust.ladder import TrustManager, TrustLevel
from core.self_improving.reflexion.engine import ReflexionEngine
from core.self_improving.proactive.engine import ProactiveEngine
from core.self_improving.learning.extractor import LearningExtractor

__all__ = [
    "MemoryStore",
    "TrustManager",
    "TrustLevel",
    "ReflexionEngine",
    "ProactiveEngine",
    "LearningExtractor",
]

__version__ = "0.1.0"
