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
    model: str = "grok-3"
    max_iterations: int = 15
    max_cost_per_decision: float = 0.50  # USD limit
    scan_interval_minutes: int = 15
    require_confirmation: bool = True  # Admin approval before trades
    min_confidence: float = 70.0
    tools_enabled: List[str] = field(default_factory=lambda: [
        "market_data", "sentiment", "liquidations",
        "technical_indicators", "onchain_analysis"
    ])

__all__ = ["DexterConfig", "DexterModel"]
