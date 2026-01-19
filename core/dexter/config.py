"""Dexter configuration."""

from dataclasses import dataclass, field
from typing import List

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

__all__ = ["DexterConfig"]
