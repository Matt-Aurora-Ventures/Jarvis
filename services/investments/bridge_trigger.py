"""Bridge Trigger — decides WHEN to initiate a CCTP bridge from Base to Solana.

Evaluates five conditions before starting a new bridge job:
  1. Accrued fees >= bridge_threshold_usd ($50 default)
  2. Base gas price <= bridge_max_gas_gwei (5 gwei default)
  3. Safety system approves (single-tx and daily limits)
  4. No other bridge job currently in-progress
  5. Kill switch is not active

If all conditions pass, a new bridge job is created via the BridgeController.
Designed to be called on a schedule (e.g. every 15 minutes from the scheduler).
"""

from __future__ import annotations

import logging
from typing import Optional

import asyncpg
import redis.asyncio as aioredis
from web3 import AsyncWeb3
from web3.providers import AsyncHTTPProvider

from services.investments.bridge_controller import BridgeController
from services.investments.config import InvestmentConfig
from services.investments.safety import SafetySystem

logger = logging.getLogger("investments.bridge_trigger")


class BridgeTrigger:
    """Evaluates conditions and triggers CCTP bridge jobs when appropriate."""

    def __init__(
        self,
        config: InvestmentConfig,
        db: asyncpg.Pool,
        redis: aioredis.Redis,
        bridge_controller: BridgeController,
        safety: SafetySystem,
    ) -> None:
        self.cfg = config
        self.db = db
        self.redis = redis
        self.bridge = bridge_controller
        self.safety = safety

        # Web3 provider for gas price reads
        self.w3 = AsyncWeb3(AsyncHTTPProvider(config.base_rpc_url))

    async def check_and_trigger(self) -> Optional[int]:
        """Check all bridge conditions and start a job if they pass.

        Returns:
            The new bridge job ID if a bridge was initiated, or None if
            conditions were not met.
        """
        # -- Gate 0: Kill switch --
        if await self.safety.is_killed():
            logger.info("Bridge trigger skipped: kill switch active")
            return None

        # -- Gate 1: Check for in-progress bridge jobs --
        pending = await self.bridge.get_pending_jobs()
        if pending:
            active_ids = [j["id"] for j in pending]
            logger.info(
                "Bridge trigger skipped: %d job(s) already in progress — %s",
                len(pending),
                active_ids,
            )
            return None

        # -- Gate 2: Accrued fees above threshold --
        accrued = await self.get_accrued_fees()
        if accrued < self.cfg.bridge_threshold_usd:
            logger.info(
                "Bridge trigger skipped: accrued fees $%.2f < threshold $%.2f",
                accrued,
                self.cfg.bridge_threshold_usd,
            )
            return None

        # -- Gate 3: Gas price within budget --
        gas_gwei = await self.get_base_gas_price()
        if gas_gwei > self.cfg.bridge_max_gas_gwei:
            logger.info(
                "Bridge trigger skipped: gas %.2f gwei > max %.2f gwei",
                gas_gwei,
                self.cfg.bridge_max_gas_gwei,
            )
            return None

        # -- Gate 4: Safety system approval (single-tx and daily limits) --
        # Clamp the bridge amount to the per-tx limit
        bridge_amount = min(accrued, self.cfg.max_single_bridge_usd)

        safe, reason = await self.safety.check_bridge_limits(
            bridge_amount,
            max_single=self.cfg.max_single_bridge_usd,
            max_daily=self.cfg.max_daily_bridge_usd,
        )
        if not safe:
            logger.info("Bridge trigger skipped: safety check failed — %s", reason)
            return None

        # -- Gate 5: Idempotency (prevent double-trigger within the same window) --
        can_run = await self.safety.check_idempotency("bridge_trigger")
        if not can_run:
            logger.info("Bridge trigger skipped: idempotency guard (already running)")
            return None

        try:
            # All gates passed — start the bridge
            logger.info(
                "Bridge trigger: all conditions met — bridging $%.2f USDC "
                "(accrued=$%.2f, gas=%.2f gwei)",
                bridge_amount,
                accrued,
                gas_gwei,
            )

            job_id = await self.bridge.start_bridge(bridge_amount)

            logger.info("Bridge job #%d created by trigger", job_id)

            # Publish trigger event for monitoring
            import json
            from datetime import datetime, timezone

            await self.redis.publish(
                "investments:bridge_events",
                json.dumps({
                    "event": "trigger_fired",
                    "job_id": job_id,
                    "amount_usdc": bridge_amount,
                    "accrued_fees": accrued,
                    "gas_gwei": gas_gwei,
                    "ts": datetime.now(timezone.utc).isoformat(),
                }),
            )

            return job_id

        except Exception as exc:
            logger.exception("Bridge trigger failed to start job: %s", exc)
            # Clear idempotency so it can be retried next cycle
            await self.safety.clear_idempotency("bridge_trigger")
            return None

        finally:
            # Always clear idempotency after the trigger attempt completes
            # (whether success or failure) so the next scheduled check can run.
            await self.safety.clear_idempotency("bridge_trigger")

    async def get_accrued_fees(self) -> float:
        """Query accrued but unbridged management fees.

        In dry-run mode, reads from the database (simulated fee accrual).
        In live mode, reads the accruedManagementFee from the basket contract
        and converts to USD.

        Returns:
            Accrued fee amount in USD.
        """
        if self.cfg.dry_run:
            return await self._get_accrued_fees_from_db()

        return await self._get_accrued_fees_from_chain()

    async def _get_accrued_fees_from_db(self) -> float:
        """Read accrued fees from the database for dry-run mode.

        Calculates: total fees collected - total fees already bridged.
        """
        row = await self.db.fetchrow(
            """
            SELECT
                COALESCE(
                    (SELECT SUM(event_data->'decoded'->>'amount_raw')::numeric
                     FROM inv_basket_events
                     WHERE event_data->>'event' = 'FeeCollected'),
                    0
                ) as total_collected_raw,
                COALESCE(
                    (SELECT SUM(amount_raw)
                     FROM inv_bridge_jobs
                     WHERE state NOT IN ('FAILED')),
                    0
                ) as total_bridged_raw
            """
        )

        if row is None:
            return 0.0

        total_collected = float(row["total_collected_raw"]) / 10**6  # USDC decimals
        total_bridged = float(row["total_bridged_raw"]) / 10**6
        accrued = max(0.0, total_collected - total_bridged)

        logger.debug(
            "Accrued fees (DB): collected=$%.2f - bridged=$%.2f = $%.2f",
            total_collected,
            total_bridged,
            accrued,
        )
        return accrued

    async def _get_accrued_fees_from_chain(self) -> float:
        """Read accrued management fees directly from the basket contract.

        Uses the AlvaraManager-style contract call to read accruedManagementFee,
        then converts from basket-token units to USD.
        """
        from services.investments.alvara_manager import AlvaraManager

        try:
            manager = AlvaraManager(self.cfg)
            try:
                fee_tokens = await manager.get_management_fee_accrued()
            finally:
                await manager.close()

            # The fee is denominated in the basket token. To get USD value,
            # we would need the basket token's NAV per unit. For simplicity,
            # if the fee is already collected as USDC (post-collectManagementFee
            # and swap), we can read the USDC balance directly.
            #
            # For now, we use the management fee in basket-token units as a
            # reasonable proxy (basket NAV ~ 1:1 with USD in most configurations).
            # A production system would read the actual USDC balance of the
            # management wallet on Base.
            logger.debug("Accrued fees (chain): %.6f basket-token units", fee_tokens)
            return fee_tokens

        except Exception as exc:
            logger.error("Failed to read accrued fees from chain: %s", exc)
            # Fall back to DB-based calculation
            logger.info("Falling back to DB-based fee calculation")
            return await self._get_accrued_fees_from_db()

    async def get_base_gas_price(self) -> float:
        """Get the current gas price on Base chain in gwei.

        Uses the EIP-1559 base fee from the latest block header, which is
        the most accurate representation of current gas costs on Base.

        Returns:
            Gas price in gwei (e.g. 0.01 for typical Base conditions).
        """
        try:
            latest_block = await self.w3.eth.get_block("latest")
            base_fee_wei = latest_block.get("baseFeePerGas", 0)
            gas_gwei = base_fee_wei / 10**9

            logger.debug("Base gas price: %.4f gwei (base fee: %d wei)", gas_gwei, base_fee_wei)
            return gas_gwei

        except Exception as exc:
            logger.error("Failed to read Base gas price: %s", exc)
            # Return a high value to prevent bridging when we can't read gas price.
            # This is a safety-first approach — if we can't verify gas is cheap,
            # we assume it's expensive and skip the bridge.
            return 999.0
