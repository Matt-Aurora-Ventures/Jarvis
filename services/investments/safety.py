"""Five-layer safety system for autonomous investment operations.

Layer 1: Portfolio Guard — position limits
Layer 2: Loss Limiter — drawdown protection
Layer 3: Bridge Limiter — transfer caps
Layer 4: Kill Switch — immediate halt
Layer 5: Idempotency Guard — prevent double-execution
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import asyncpg
    import redis.asyncio as aioredis

logger = logging.getLogger("investments.safety")


class SafetySystem:

    def __init__(self, db_pool: asyncpg.Pool, redis: aioredis.Redis) -> None:
        self.db = db_pool
        self.redis = redis

    # ── Layer 1: Portfolio Guard ──────────────────────────────────────────

    async def check_portfolio_limits(
        self,
        proposed_weights: dict[str, float],
        current_weights: dict[str, float],
        *,
        max_single_token_pct: float = 0.30,
        max_rebalance_change_pct: float = 0.25,
    ) -> tuple[bool, str]:
        for token, weight in proposed_weights.items():
            if weight > max_single_token_pct:
                return False, f"{token} weight {weight:.0%} exceeds {max_single_token_pct:.0%} limit"

        if proposed_weights.get("ALVA", 0) < 0.05:
            return False, "ALVA weight below 5% minimum"

        all_tokens = set(list(proposed_weights) + list(current_weights))
        total_change = sum(
            abs(proposed_weights.get(t, 0) - current_weights.get(t, 0))
            for t in all_tokens
        ) / 2
        if total_change > max_rebalance_change_pct:
            return False, (
                f"Total change {total_change:.0%} exceeds "
                f"{max_rebalance_change_pct:.0%} per-rebalance limit"
            )

        added = set(proposed_weights) - set(current_weights)
        removed = set(current_weights) - set(proposed_weights)
        if len(added) + len(removed) > 4:
            return False, (
                f"Too many token changes: {len(added)} added + "
                f"{len(removed)} removed > 4 max"
            )

        return True, ""

    # ── Layer 2: Loss Limiter ─────────────────────────────────────────────

    async def check_loss_limits(self) -> tuple[bool, str]:
        halted = await self.redis.get("inv:loss_halt")
        # decode_responses=True returns str; handle both bytes and str safely
        halted_str = halted.decode() if isinstance(halted, bytes) else (halted or "")
        if halted_str == "true":
            return False, (
                "Loss limiter active: NAV dropped >15% in 24h. "
                "Manual re-enable required."
            )

        # Use portable SQL that works on both plain PostgreSQL and TimescaleDB
        row = await self.db.fetchrow("""
            SELECT
                (SELECT nav_usd FROM inv_nav_snapshots
                 WHERE ts > NOW() - INTERVAL '24 hours'
                 ORDER BY ts ASC LIMIT 1) AS nav_24h_ago,
                (SELECT nav_usd FROM inv_nav_snapshots
                 WHERE ts > NOW() - INTERVAL '24 hours'
                 ORDER BY ts DESC LIMIT 1) AS nav_now
        """)

        if row and row["nav_24h_ago"] and float(row["nav_24h_ago"]) > 0:
            change = (float(row["nav_now"]) - float(row["nav_24h_ago"])) / float(row["nav_24h_ago"])
            if change < -0.15:
                await self.redis.set("inv:loss_halt", "true")
                msg = f"NAV dropped {change:.1%} in 24h — operations halted"
                await self._alert(f"LOSS HALT: {msg}")
                return False, msg

        return True, ""

    # ── Layer 3: Bridge Limiter ───────────────────────────────────────────

    async def check_bridge_limits(
        self,
        amount_usdc: float,
        *,
        max_single: float = 10_000.0,
        max_daily: float = 50_000.0,
    ) -> tuple[bool, str]:
        if amount_usdc > max_single:
            return False, f"Single bridge ${amount_usdc} exceeds ${max_single} limit"

        row = await self.db.fetchrow("""
            SELECT COALESCE(SUM(amount_usdc), 0) as total
            FROM inv_bridge_jobs
            WHERE created_at > NOW() - INTERVAL '24 hours'
            AND state NOT IN ('FAILED', 'CANCELLED')
        """)
        daily_total = float(row["total"]) if row else 0.0
        if daily_total + amount_usdc > max_daily:
            return False, (
                f"Daily bridge total ${daily_total + amount_usdc:.2f} "
                f"would exceed ${max_daily} limit"
            )

        return True, ""

    # ── Layer 4: Kill Switch ──────────────────────────────────────────────

    async def is_killed(self) -> bool:
        val = await self.redis.get("inv:kill_switch")
        val_str = val.decode() if isinstance(val, bytes) else (val or "")
        return val_str == "true"

    async def activate_kill_switch(self, reason: str) -> None:
        await self.redis.set("inv:kill_switch", "true")
        await self._alert(f"KILL SWITCH ACTIVATED: {reason}")
        logger.critical("Kill switch activated: %s", reason)

    async def deactivate_kill_switch(self) -> None:
        await self.redis.set("inv:kill_switch", "false")
        await self._alert("Kill switch deactivated. Operations resumed.")

    # ── Layer 5: Idempotency Guard ────────────────────────────────────────

    async def check_idempotency(self, operation_key: str) -> bool:
        result = await self.redis.set(
            f"inv:idempotency:{operation_key}",
            "running",
            nx=True,
            ex=3600,
        )
        return result is not None

    async def clear_idempotency(self, operation_key: str) -> None:
        await self.redis.delete(f"inv:idempotency:{operation_key}")

    # ── Alerts ────────────────────────────────────────────────────────────

    async def _alert(self, message: str) -> None:
        await self.redis.publish("telegram:alerts", message)
        logger.warning("Safety alert: %s", message)
