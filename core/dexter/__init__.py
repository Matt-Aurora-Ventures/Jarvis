"""
Dexter ReAct Framework Integration

Autonomous trading agent with Reasoning + Acting pattern.
Grok AI serves as the reasoning engine for all trading decisions.

Architecture:
- Grok ReAct Loop: Thinks → Decides → Acts → Observes
- Multi-tool Router: Financial analysis tools
- Context Compaction: Prevents token overflow
- Heavy Grok Weighting: All sentiment analysis heavily weighted to Grok (1.0)
- Paper Trading: Simulated trades for validation
- Cost Tracking: API cost monitoring and budget enforcement
"""

from .agent import DexterAgent, DecisionType, ReActDecision
from .config import DexterConfig, DexterModel
from .scratchpad import Scratchpad
from .context import ContextManager
from .paper_trader import DexterPaperTrader, PaperTrade, PaperTradingStats
from .cost_tracking import DexterCostTracker, CostEntry, CostStats
from .tools.meta_router import financial_research

__all__ = [
    # Agent
    "DexterAgent",
    "DecisionType",
    "ReActDecision",
    # Config
    "DexterConfig",
    "DexterModel",
    # Logging
    "Scratchpad",
    "ContextManager",
    # Paper Trading
    "DexterPaperTrader",
    "PaperTrade",
    "PaperTradingStats",
    # Cost Tracking
    "DexterCostTracker",
    "CostEntry",
    "CostStats",
    # Tools
    "financial_research",
]
