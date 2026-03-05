"""
Compute Unit Optimizer — Simulate-then-set CU limits before broadcasting.

Default 200,000 CU wastes priority fee budget. This module:
    1. Simulates the transaction to get actual CU usage
    2. Adds a 10% buffer
    3. Sets ComputeBudgetProgram.setComputeUnitLimit accordingly

Usage::

    from core.trading.compute_units import optimize_compute_units

    cu_limit = await optimize_compute_units(transaction, rpc_client)
"""

from __future__ import annotations

import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Solana default if no CU limit is set
DEFAULT_CU_LIMIT = 200_000

# Buffer added to simulation result (10%)
CU_BUFFER_MULTIPLIER = 1.10

# Absolute minimum and maximum
MIN_CU_LIMIT = 10_000
MAX_CU_LIMIT = 1_400_000  # Solana per-transaction max


async def simulate_compute_units(
    transaction: Any,
    rpc_client: Any,
    *,
    commitment: str = "confirmed",
) -> Optional[int]:
    """
    Simulate a transaction to determine actual compute unit usage.

    Args:
        transaction: A serialized or Transaction object
        rpc_client: Solana RPC client (AsyncClient)
        commitment: RPC commitment level

    Returns:
        Consumed CU count, or None if simulation fails
    """
    try:
        # solana-py / solders async client
        resp = await rpc_client.simulate_transaction(
            transaction,
            commitment=commitment,
        )

        # Handle solders response types
        value = getattr(resp, "value", None)
        if value is None and hasattr(resp, "__getitem__"):
            value = resp.get("result", {}).get("value", {})

        if value is None:
            logger.warning("Simulation returned no value")
            return None

        # Check for simulation error
        err = getattr(value, "err", None) or (value.get("err") if isinstance(value, dict) else None)
        if err:
            logger.warning("Simulation error: %s", err)
            return None

        # Extract units consumed
        units = getattr(value, "units_consumed", None)
        if units is None and isinstance(value, dict):
            units = value.get("unitsConsumed")

        if units is not None:
            return int(units)

        logger.warning("Simulation did not return units_consumed")
        return None

    except Exception as exc:
        logger.error("CU simulation failed: %s", exc)
        return None


async def optimize_compute_units(
    transaction: Any,
    rpc_client: Any,
    *,
    buffer_multiplier: float = CU_BUFFER_MULTIPLIER,
    fallback_cu: int = DEFAULT_CU_LIMIT,
) -> int:
    """
    Simulate transaction and return optimal CU limit.

    Steps:
        1. Simulate to get actual CU usage
        2. Add buffer (default 10%)
        3. Clamp to [MIN_CU_LIMIT, MAX_CU_LIMIT]

    If simulation fails, returns *fallback_cu*.
    """
    simulated = await simulate_compute_units(transaction, rpc_client)

    if simulated is None:
        logger.info("Using fallback CU limit: %d", fallback_cu)
        return fallback_cu

    optimized = int(simulated * buffer_multiplier)
    optimized = max(MIN_CU_LIMIT, min(optimized, MAX_CU_LIMIT))

    savings = DEFAULT_CU_LIMIT - optimized
    if savings > 0:
        logger.info(
            "CU optimized: %d → %d (simulated: %d, saved: %d CU, %.0f%%)",
            DEFAULT_CU_LIMIT, optimized, simulated,
            savings, (savings / DEFAULT_CU_LIMIT) * 100,
        )
    else:
        logger.info("CU limit: %d (simulated: %d)", optimized, simulated)

    return optimized
