"""Dexter configuration."""

from dataclasses import dataclass, field
from enum import Enum
from typing import List


class DexterModel(str, Enum):
    """Available models for Dexter agent."""
    GROK_3 = "grok-3"
    GROK_2 = "grok-2"
    CLAUDE = "claude-3-sonnet"
    GPT4 = "gpt-4-turbo"

    def __str__(self) -> str:
        return self.value


@dataclass
class DexterConfig:
    """Dexter agent configuration."""
    enabled: bool = True
    model: DexterModel = DexterModel.GROK_3
    max_iterations: int = 15
    max_cost_per_decision: float = 0.50  # USD limit
    scan_interval_minutes: int = 15
    require_confirmation: bool = True  # Admin approval before trades
    min_confidence: float = 70.0
    save_scratchpad: bool = True
    tools_enabled: List[str] = field(default_factory=lambda: [
        "financial_research",
        "sentiment_analyze",
        "market_data",
        "liquidations",
        "technical_indicators",
        "onchain_analysis",
    ])

    def to_dict(self) -> dict:
        """Serialize config to dict."""
        return {
            "enabled": self.enabled,
            "model": self.model.value if isinstance(self.model, DexterModel) else str(self.model),
            "max_iterations": self.max_iterations,
            "max_cost_per_decision": self.max_cost_per_decision,
            "scan_interval_minutes": self.scan_interval_minutes,
            "require_confirmation": self.require_confirmation,
            "min_confidence": self.min_confidence,
            "save_scratchpad": self.save_scratchpad,
            "tools_enabled": list(self.tools_enabled),
        }

__all__ = ["DexterConfig", "DexterModel"]
