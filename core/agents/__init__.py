"""
Jarvis Multi-Agent System.

Four specialized agents forming an internal organization:
- Researcher: Web research, summarization, knowledge graph (Groq - fast)
- Operator: Task execution, UI automation, integrations (Groq - fast)
- Trader: Crypto pipeline with backtesting and risk management (Claude - quality)
- Architect: Self-improvement proposals with quality gates (Claude - quality)

The Orchestrator brain delegates to these agents based on objective type.
"""

from core.agents.registry import AgentRegistry, get_registry
from core.agents.base import BaseAgent, AgentRole, AgentCapability
from core.agents.researcher import ResearcherAgent
from core.agents.operator import OperatorAgent
from core.agents.trader import TraderAgent
from core.agents.architect import ArchitectAgent

__all__ = [
    "AgentRegistry",
    "get_registry",
    "BaseAgent",
    "AgentRole",
    "AgentCapability",
    "ResearcherAgent",
    "OperatorAgent",
    "TraderAgent",
    "ArchitectAgent",
]
