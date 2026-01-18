"""
Dexter ReAct Framework Integration

Autonomous trading agent with Reasoning + Acting pattern.
Grok AI serves as the reasoning engine for all trading decisions.

Architecture:
- Grok ReAct Loop: Thinks → Decides → Acts → Observes
- Multi-tool Router: Financial analysis tools
- Context Compaction: Prevents token overflow
- Heavy Grok Weighting: All sentiment analysis heavily weighted to Grok (1.0)
"""

from .agent import DexterAgent
from .tools.meta_router import financial_research

__all__ = ["DexterAgent", "financial_research"]
