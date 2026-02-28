"""Dry-run fallback runtime for environments without Postgres/Redis.

This keeps the investments API contract alive for UI validation and staged
rollouts while avoiding hard startup failure when stateful dependencies are
unavailable.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class _FallbackSafety:
    _killed: bool = False

    async def is_killed(self) -> bool:
        return self._killed

    async def activate_kill_switch(self, _reason: str) -> None:
        self._killed = True

    async def deactivate_kill_switch(self) -> None:
        self._killed = False


class FallbackOrchestrator:
    """In-memory orchestrator implementing the API-facing contract."""

    def __init__(self, cfg: Any) -> None:
        self.cfg = cfg
        self.safety = _FallbackSafety()
        self._next_decision_id = 1

        self._basket_tokens = {
            "ALVA": {"weight": 0.10, "price_usd": 0.50, "liquidity_usd": 200_000},
            "WETH": {"weight": 0.25, "price_usd": 3200.0, "liquidity_usd": 5_000_000},
            "cbBTC": {"weight": 0.20, "price_usd": 95_000.0, "liquidity_usd": 3_000_000},
            "USDC": {"weight": 0.15, "price_usd": 1.0, "liquidity_usd": 50_000_000},
            "AERO": {"weight": 0.15, "price_usd": 1.80, "liquidity_usd": 500_000},
            "DEGEN": {"weight": 0.15, "price_usd": 0.012, "liquidity_usd": 300_000},
        }
        self._nav_usd = 200.0
        self._decisions: list[dict[str, Any]] = []
        self._reflections: list[dict[str, Any]] = []

    async def _get_basket_state(self) -> dict[str, Any]:
        return {"tokens": self._basket_tokens, "nav_usd": self._nav_usd}

    async def get_performance(self, hours: int) -> dict[str, Any]:
        now = _utc_now()
        start = now - timedelta(hours=max(1, int(hours)))
        points = []
        for idx in range(6):
            ts = start + (now - start) * (idx / 5)
            nav = self._nav_usd * (0.995 + (idx * 0.001))
            points.append({"ts": ts.isoformat(), "nav_usd": round(float(nav), 4)})

        if len(points) >= 2 and points[0]["nav_usd"] > 0:
            change_pct = (points[-1]["nav_usd"] - points[0]["nav_usd"]) / points[0]["nav_usd"]
        else:
            change_pct = 0.0

        return {
            "basket_id": self.cfg.basket_id,
            "hours": hours,
            "points": points,
            "change_pct": float(change_pct),
        }

    async def get_decisions(self, limit: int = 20) -> list[dict[str, Any]]:
        return list(reversed(self._decisions))[: max(1, int(limit))]

    async def get_decision_detail(self, decision_id: int) -> dict[str, Any] | None:
        for row in self._decisions:
            if int(row["id"]) == int(decision_id):
                return row
        return None

    async def get_reflections(self, limit: int = 10) -> list[dict[str, Any]]:
        return list(reversed(self._reflections))[: max(1, int(limit))]

    async def run_cycle(self) -> dict[str, Any]:
        ts = _utc_now()
        if await self.safety.is_killed():
            return {"status": "killed", "ts": ts.isoformat()}

        decision_id = self._next_decision_id
        self._next_decision_id += 1

        decision = {
            "id": decision_id,
            "action": "HOLD",
            "summary": "Fallback dry-run cycle completed.",
            "reasoning": "Fallback dry-run cycle completed.",
            "confidence": 0.5,
            "nav_usd": float(self._nav_usd),
            "final_weights": {k: float(v["weight"]) for k, v in self._basket_tokens.items()},
            "previous_weights": {k: float(v["weight"]) for k, v in self._basket_tokens.items()},
            "debate_rounds": [],
            "agent_reports": [],
            "risk_assessment": {
                "overall_risk": "LOW",
                "max_drawdown_pct": 0.0,
                "var_95": 0.0,
                "concentration_risk": "N/A",
                "liquidity_risk": "N/A",
            },
            "tx_hash": None,
            "execution_status": "dry_run",
            "ts": ts.isoformat(),
            "created_at": ts.isoformat(),
            "timestamp": ts.isoformat(),
            "navAtDecision": float(self._nav_usd),
        }
        self._decisions.append(decision)
        self._reflections.append(
            {
                "id": decision_id,
                "decision_id": decision_id,
                "data": {"summary": "Fallback reflection placeholder"},
                "calibration_hint": "No adjustments in fallback mode.",
                "ts": ts.isoformat(),
            }
        )

        return {
            "status": "completed",
            "decision_id": decision_id,
            "action": decision["action"],
            "confidence": decision["confidence"],
            "nav_usd": decision["nav_usd"],
            "tx_hash": None,
            "elapsed_s": 0.1,
            "ts": ts.isoformat(),
        }

    async def close(self) -> None:
        return None
