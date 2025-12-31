#!/usr/bin/env python3
"""
Conversation backtesting harness.

Allows us to replay scripted user turns against `conversation.generate_response`
and assert conversational quality (latency, keyword coverage, etc.).
This is critical for Phase 7 reliability goals and self-improvement loops.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from core import conversation


@dataclass
class BacktestTurn:
    """Single conversational user turn."""

    user_text: str
    expected_keywords: List[str] = field(default_factory=list)
    max_latency_ms: Optional[int] = None
    screen_context: str = ""

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BacktestTurn":
        return cls(
            user_text=data.get("user") or data.get("user_text", ""),
            expected_keywords=list(data.get("expected_keywords", [])),
            max_latency_ms=data.get("max_latency_ms"),
            screen_context=data.get("screen_context", ""),
        )


@dataclass
class BacktestTurnResult:
    """Result of a single turn evaluation."""

    user_text: str
    assistant_text: str
    latency_ms: float
    passed: bool
    failures: List[str] = field(default_factory=list)


@dataclass
class BacktestScenario:
    """A complete scripted conversation scenario."""

    name: str
    description: str = ""
    turns: List[BacktestTurn] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BacktestScenario":
        turns = [BacktestTurn.from_dict(item) for item in data.get("turns", [])]
        return cls(
            name=data.get("name") or data.get("id") or "unnamed_scenario",
            description=data.get("description", ""),
            turns=turns,
            tags=list(data.get("tags", [])),
        )


@dataclass
class BacktestResult:
    """Aggregate scenario result."""

    scenario: BacktestScenario
    turns: List[BacktestTurnResult]

    @property
    def passed(self) -> bool:
        return all(turn.passed for turn in self.turns)

    @property
    def failure_reasons(self) -> List[str]:
        reasons: List[str] = []
        for turn in self.turns:
            if not turn.passed:
                reasons.extend(turn.failures)
        return reasons

    @property
    def avg_latency_ms(self) -> float:
        if not self.turns:
            return 0.0
        return sum(turn.latency_ms for turn in self.turns) / len(self.turns)


class ConversationBacktester:
    """Runs scripted conversations against the live conversation engine."""

    def __init__(self, default_latency_ms: int = 2500):
        self.default_latency_ms = default_latency_ms

    def run_scenario(self, scenario: BacktestScenario) -> BacktestResult:
        turn_results: List[BacktestTurnResult] = []
        for turn in scenario.turns:
            result = self._run_turn(turn)
            turn_results.append(result)
        return BacktestResult(scenario=scenario, turns=turn_results)

    def _run_turn(self, turn: BacktestTurn) -> BacktestTurnResult:
        start = time.perf_counter()
        assistant_text = conversation.generate_response(
            user_text=turn.user_text,
            screen_context=turn.screen_context,
            session_history=None,
        ).strip()
        latency_ms = (time.perf_counter() - start) * 1000
        failures: List[str] = []

        max_latency = turn.max_latency_ms or self.default_latency_ms
        if latency_ms > max_latency:
            failures.append(
                f"Latency {latency_ms:.1f}ms exceeded limit {max_latency}ms for '{turn.user_text[:40]}'"
            )

        normalized = assistant_text.lower()
        for keyword in turn.expected_keywords:
            if keyword.lower() not in normalized:
                failures.append(f"Missing keyword '{keyword}' in response to '{turn.user_text[:40]}'")

        return BacktestTurnResult(
            user_text=turn.user_text,
            assistant_text=assistant_text,
            latency_ms=latency_ms,
            passed=not failures,
            failures=failures,
        )


def load_scenarios_from_file(path: Path) -> List[BacktestScenario]:
    """Load one or multiple scenarios from JSON/YAML."""
    if not path.exists():
        raise FileNotFoundError(f"Scenario file not found: {path}")

    text = path.read_text(encoding="utf-8")
    data = _load_serialized(text, path.suffix.lower())

    if isinstance(data, dict) and "turns" in data:
        return [BacktestScenario.from_dict(data)]
    if isinstance(data, dict) and "scenarios" in data:
        return [BacktestScenario.from_dict(item) for item in data["scenarios"]]
    if isinstance(data, list):
        return [BacktestScenario.from_dict(item) for item in data]

    raise ValueError(f"Unrecognized scenario format in {path}")


def _load_serialized(text: str, suffix: str) -> Any:
    if suffix in {".yaml", ".yml"}:
        try:
            import yaml  # type: ignore
        except ImportError as exc:
            raise RuntimeError("PyYAML is required to load YAML backtest scenarios") from exc
        return yaml.safe_load(text)
    return json.loads(text)


def run_backtests(
    scenarios: Iterable[BacktestScenario],
    default_latency_ms: int = 2500,
) -> List[BacktestResult]:
    """Convenience helper to run multiple scenarios."""
    runner = ConversationBacktester(default_latency_ms=default_latency_ms)
    return [runner.run_scenario(scenario) for scenario in scenarios]


def run_from_file(path: Path, default_latency_ms: int = 2500) -> List[BacktestResult]:
    scenarios = load_scenarios_from_file(path)
    return run_backtests(scenarios, default_latency_ms=default_latency_ms)
