"""Reflection Engine — runs 24-72h post-trade, compares predictions to outcomes."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Optional

logger = logging.getLogger("investments.consensus.reflection")


class ReflectionEngine:
    """Runs post-trade. Compares predictions to outcomes. Updates calibration."""

    def __init__(self, db_pool: Any) -> None:
        self.db = db_pool

    async def run_reflection(self, decision_id: int) -> dict:
        decision = await self._get_decision(decision_id)
        if not decision:
            return {"error": "Decision not found"}

        decision_time = decision["created_at"]
        hours_elapsed = (
            datetime.now(timezone.utc) - decision_time
        ).total_seconds() / 3600

        if hours_elapsed < 24:
            return {"status": "too_early", "hours_elapsed": hours_elapsed}

        actual_nav_change = await self._get_nav_change_since(decision_time)
        token_performance = await self._get_token_performance_since(decision_time)

        # Score each agent's accuracy
        agent_scores: dict[str, float] = {}
        for agent_name in [
            "grok_sentiment",
            "claude_risk",
            "chatgpt_macro",
            "dexter_fundamental",
        ]:
            col = f"{agent_name}_report"
            report = decision.get(col)
            if isinstance(report, str):
                try:
                    report = json.loads(report)
                except json.JSONDecodeError:
                    report = {}
            agent_scores[agent_name] = self._score_prediction(
                report or {}, token_performance
            )

        calibration = self._generate_calibration(
            decision, actual_nav_change, agent_scores
        )

        await self._store_reflection(
            decision_id,
            {
                "hours_elapsed": hours_elapsed,
                "predicted_action": decision["action"],
                "nav_change_pct": actual_nav_change,
                "agent_accuracy_scores": agent_scores,
                "calibration_hint": calibration,
                "best_agent": max(agent_scores, key=agent_scores.get),
            },
        )

        return {"status": "reflected", "calibration": calibration}

    async def get_calibration_hints(self, limit: int = 10) -> str:
        rows = await self.db.fetch(
            "SELECT calibration_hint FROM inv_reflections "
            "ORDER BY created_at DESC LIMIT $1",
            limit,
        )
        if rows:
            return "\n".join(r["calibration_hint"] for r in rows)
        return "No calibration data yet."

    def _score_prediction(self, report: dict, actual_performance: dict) -> float:
        if not report:
            return 0.5
        predicted_trend = report.get(
            "trend", report.get("market_regime", "UNCERTAIN")
        )
        actual_direction = (
            "UP" if sum(actual_performance.values()) > 0 else "DOWN"
        )

        bullish = predicted_trend in {"RISING", "RISK_ON", "BULL"}
        bearish = predicted_trend in {"DECLINING", "RISK_OFF", "BEAR"}

        if (bullish and actual_direction == "UP") or (
            bearish and actual_direction == "DOWN"
        ):
            return 0.8 + report.get("confidence", 0.5) * 0.2
        elif not bullish and not bearish:
            return 0.5
        else:
            return 0.2

    def _generate_calibration(
        self, decision: dict, nav_change: float, scores: dict[str, float]
    ) -> str:
        best = max(scores, key=scores.get)
        worst = min(scores, key=scores.get)
        action = decision["action"]

        hint = (
            f"Decision '{action}' resulted in {nav_change:+.1%} NAV change. "
            f"Most accurate: {best} ({scores[best]:.0%}). "
            f"Least accurate: {worst} ({scores[worst]:.0%}). "
        )

        if action == "REBALANCE" and nav_change < -0.02:
            hint += "Rebalance was net negative — consider higher HOLD bias. "
        elif action == "HOLD" and nav_change > 0.05:
            hint += "Holding missed upside — consider lower HOLD bias. "

        return hint

    async def _get_decision(self, decision_id: int) -> Optional[dict]:
        return await self.db.fetchrow(
            "SELECT * FROM inv_decisions WHERE id = $1", decision_id
        )

    async def _get_nav_change_since(self, since: datetime) -> float:
        # Use MIN/MAX subquery as fallback for non-TimescaleDB environments
        row = await self.db.fetchrow(
            """
            SELECT
                (SELECT nav_usd FROM inv_nav_snapshots WHERE ts >= $1 ORDER BY ts ASC LIMIT 1) as nav_start,
                (SELECT nav_usd FROM inv_nav_snapshots ORDER BY ts DESC LIMIT 1) as nav_end
            """,
            since,
        )
        if row and row["nav_start"] and row["nav_end"] and float(row["nav_start"]) > 0:
            return (float(row["nav_end"]) - float(row["nav_start"])) / float(
                row["nav_start"]
            )
        return 0.0

    async def _get_token_performance_since(self, since: datetime) -> dict:
        rows = await self.db.fetch(
            """
            SELECT symbol,
                   (SELECT price_usd FROM inv_token_prices p2
                    WHERE p2.symbol = p1.symbol ORDER BY ts DESC LIMIT 1)
                   -
                   (SELECT price_usd FROM inv_token_prices p3
                    WHERE p3.symbol = p1.symbol AND p3.ts >= $1
                    ORDER BY ts ASC LIMIT 1) as price_diff
            FROM inv_token_prices p1
            WHERE ts >= $1
            GROUP BY symbol
            """,
            since,
        )
        return {r["symbol"]: float(r["price_diff"] or 0) for r in rows}

    async def _store_reflection(self, decision_id: int, data: dict) -> None:
        await self.db.execute(
            """
            INSERT INTO inv_reflections (decision_id, data, calibration_hint, created_at)
            VALUES ($1, $2, $3, NOW())
            """,
            decision_id,
            json.dumps(data),
            data["calibration_hint"],
        )
