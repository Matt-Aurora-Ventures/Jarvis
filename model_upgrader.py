"""Model upgrader utility with scan, decisioning, hot-swap, and rollback."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional


@dataclass
class UpgradeDecision:
    current_model: str
    candidate_model: str
    action: str
    reason: str


class ModelUpgrader:
    def __init__(self, config_path: str | Path = "model_registry.json"):
        self.config_path = Path(config_path)
        self._previous_model: Optional[str] = None

    def scan_candidates(self, available: List[str], current: str) -> List[str]:
        return [model for model in available if model != current]

    def decide(self, metrics: Dict[str, float], current: str, candidate: str) -> UpgradeDecision:
        quality_gain = metrics.get("quality_gain", 0.0)
        latency_delta = metrics.get("latency_delta", 0.0)
        error_delta = metrics.get("error_delta", 0.0)

        if quality_gain >= 0.08 and latency_delta <= 0.15 and error_delta <= 0.02:
            return UpgradeDecision(current, candidate, "upgrade", "Quality improvement outweighs risk")
        if quality_gain < 0:
            return UpgradeDecision(current, candidate, "rollback", "Candidate quality regressed")
        return UpgradeDecision(current, candidate, "hold", "Insufficient confidence for upgrade")

    def hot_swap(self, runtime_config: Dict[str, str], new_model: str) -> Dict[str, str]:
        self._previous_model = runtime_config.get("model")
        runtime_config["model"] = new_model
        return runtime_config

    def rollback(self, runtime_config: Dict[str, str]) -> Dict[str, str]:
        if self._previous_model:
            runtime_config["model"] = self._previous_model
        return runtime_config
