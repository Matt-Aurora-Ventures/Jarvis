"""Budget and timeout guardrails for action proposals."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass
class Budget:
    timeout_s: int = 30
    max_steps: int = 20
    max_cost_usd: float = 0.05

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timeout_s": self.timeout_s,
            "max_steps": self.max_steps,
            "max_cost_usd": self.max_cost_usd,
        }


def budget_from_payload(payload: Optional[Dict[str, Any]]) -> Optional[Budget]:
    if not payload:
        return None
    return Budget(
        timeout_s=int(payload.get("timeout_s", 30)),
        max_steps=int(payload.get("max_steps", 20)),
        max_cost_usd=float(payload.get("max_cost_usd", 0.05)),
    )
