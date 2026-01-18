"""
Dexter ReAct Agent Configuration

Manages settings for the Dexter autonomous trading agent including
LLM selection, iteration limits, cost controls, and safety parameters.

Built on Dexter framework: https://github.com/virattt/dexter
License: MIT
"""

from dataclasses import dataclass, field
from typing import List
from enum import Enum


class DexterModel(str, Enum):
    """Supported LLM models for Dexter reasoning"""
    GROK_3 = "grok-3"
    CLAUDE_OPUS = "claude-opus-4-5"
    CLAUDE_SONNET = "claude-sonnet-4"
    GPT_4 = "gpt-4-turbo"


@dataclass
class DexterConfig:
    """
    Configuration for Dexter ReAct agent

    Attributes:
        enabled: Global kill switch for Dexter trading
        model: Which LLM to use for reasoning
        max_iterations: Max ReAct loop iterations (prevent infinite loops)
        max_cost_per_decision: USD limit for API calls per decision
        scan_interval_minutes: How often to check for trading opportunities
        require_confirmation: Admin approval before executing trades
        min_confidence: Only trade if confidence >= this threshold
        tools_enabled: List of tools Dexter can access
        context_max_tokens: Max tokens in context (triggers compaction if exceeded)
        save_scratchpad: Log all reasoning steps to disk
    """
    enabled: bool = True
    model: DexterModel = DexterModel.GROK_3
    max_iterations: int = 15
    max_cost_per_decision: float = 0.50  # USD
    scan_interval_minutes: int = 15
    require_confirmation: bool = True
    min_confidence: float = 70.0
    tools_enabled: List[str] = field(
        default_factory=lambda: [
            "financial_research",
            "sentiment_analyze",
            "market_data",
            "liquidation_check",
            "dual_ma_signal",
            "position_status",
            "risk_check",
        ]
    )
    context_max_tokens: int = 100000
    save_scratchpad: bool = True
    scratchpad_dir: str = "data/dexter/scratchpad"
    session_dir: str = "data/dexter/sessions"

    def to_dict(self) -> dict:
        """Convert config to dictionary"""
        return {
            "enabled": self.enabled,
            "model": self.model.value,
            "max_iterations": self.max_iterations,
            "max_cost_per_decision": self.max_cost_per_decision,
            "scan_interval_minutes": self.scan_interval_minutes,
            "require_confirmation": self.require_confirmation,
            "min_confidence": self.min_confidence,
            "tools_enabled": self.tools_enabled,
            "context_max_tokens": self.context_max_tokens,
            "save_scratchpad": self.save_scratchpad,
        }


# Default configuration
DEFAULT_CONFIG = DexterConfig()
