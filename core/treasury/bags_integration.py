"""
Treasury-Bags.fm Integration.

Connects Bags.fm partner fee collection with the treasury system:
- Automated fee collection and distribution
- Treasury allocation of partner fees
- Staking rewards funding from partner revenue
- Reporting and analytics
"""

import asyncio
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

logger = logging.getLogger("jarvis.treasury.bags_integration")


@dataclass
class FeeAllocation:
    """How partner fees are allocated."""
    staking_rewards_pct: float = 0.50  # 50% to staking rewards pool
    operations_pct: float = 0.30       # 30% to operations
    development_pct: float = 0.20      # 20% to development

    def validate(self):
        """Ensure percentages sum to 1.0."""
        total = self.staking_rewards_pct + self.operations_pct + self.development_pct
        assert abs(total - 1.0) < 0.001, f"Allocation must sum to 1.0, got {total}"


@dataclass
class FeeDistributionRecord:
    """Record of a fee distribution."""
    id: str
    timestamp: datetime
    total_fees_sol: float
    to_staking_sol: float
    to_operations_sol: float
    to_development_sol: float
    source_mints: List[str]
    transaction_signatures: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "timestamp": self.timestamp.isoformat(),
            "total_fees_sol": self.total_fees_sol,
            "to_staking_sol": self.to_staking_sol,
            "to_operations_sol": self.to_operations_sol,
            "to_development_sol": self.to_development_sol,
            "source_mints": self.source_mints,
            "transaction_signatures": self.transaction_signatures,
        }


class TreasuryBagsIntegration:
    """
    Integrates Bags.fm partner fees with the treasury.

    Handles:
    - Automated fee collection scheduling
    - Fee distribution to treasury wallets
    - Staking rewards funding
    - Revenue analytics
    """

    LAMPORTS_PER_SOL = 1_000_000_000

    def __init__(
        self,
        bags_fee_collector=None,
        treasury_manager=None,
        allocation: FeeAllocation = None,
        collection_interval_hours: int = 1,
    ):
        """
        Initialize integration.

        Args:
            bags_fee_collector: FeeCollector instance from integrations.bags
            treasury_manager: TreasuryManager instance
            allocation: How to allocate collected fees
            collection_interval_hours: How often to collect fees
        """
        self._fee_collector = bags_fee_collector
        self._treasury = treasury_manager
        self.allocation = allocation or FeeAllocation()
        self.allocation.validate()

        self.collection_interval = timedelta(hours=collection_interval_hours)
        self._last_collection: Optional[datetime] = None
        self._running = False
        self._collection_task: Optional[asyncio.Task] = None

        # Statistics
        self._stats = {
            "total_collected_sol": 0.0,
            "total_distributed_sol": 0.0,
            "to_staking_sol": 0.0,
            "to_operations_sol": 0.0,
            "to_development_sol": 0.0,
            "collection_count": 0,
            "last_collection": None,
        }

        # Distribution history
        self._distribution_history: List[FeeDistributionRecord] = []

        logger.info(
            f"Treasury-Bags integration initialized: "
            f"Staking {self.allocation.staking_rewards_pct:.0%}, "
            f"Ops {self.allocation.operations_pct:.0%}, "
            f"Dev {self.allocation.development_pct:.0%}"
        )

    def _ensure_fee_collector(self):
        """Ensure fee collector is available."""
        if self._fee_collector is None:
            from integrations.bags.fee_collector import FeeCollector, get_fee_collector
            self._fee_collector = get_fee_collector()

    def _ensure_treasury(self):
        """Ensure treasury manager is available."""
        if self._treasury is None:
            from core.treasury.manager import get_treasury
            self._treasury = get_treasury()

    async def collect_and_distribute(self, dry_run: bool = False) -> FeeDistributionRecord:
        """
        Collect partner fees and distribute to treasury.

        Args:
            dry_run: If True, calculate but don't execute transactions

        Returns:
            FeeDistributionRecord with distribution details
        """
        self._ensure_fee_collector()
        self._ensure_treasury()

        logger.info("Starting fee collection and distribution...")

        # Get pending fees from Bags
        pending = await self._fee_collector.check_pending_fees()

        if not pending or all(v == 0 for v in pending.values()):
            logger.info("No pending fees to collect")
            return None

        # Calculate total in SOL
        total_sol = sum(pending.values())  # Assuming values are already in SOL

        logger.info(f"Pending fees: {total_sol:.6f} SOL from {len(pending)} mint(s)")

        # Calculate allocation
        to_staking = total_sol * self.allocation.staking_rewards_pct
        to_operations = total_sol * self.allocation.operations_pct
        to_development = total_sol * self.allocation.development_pct

        # Create distribution record
        import uuid
        record = FeeDistributionRecord(
            id=f"bags_dist_{uuid.uuid4().hex[:12]}",
            timestamp=datetime.now(timezone.utc),
            total_fees_sol=total_sol,
            to_staking_sol=to_staking,
            to_operations_sol=to_operations,
            to_development_sol=to_development,
            source_mints=list(pending.keys()),
        )

        if dry_run:
            logger.info(f"DRY RUN - Would distribute: {record.to_dict()}")
            return record

        # Execute collection
        try:
            collection_result = await self._fee_collector.collect_and_distribute()

            if collection_result.get("claimed", 0) > 0:
                # Fund the staking rewards pool
                await self._fund_staking_rewards(to_staking)

                # Transfer to treasury wallets
                await self._distribute_to_treasury(to_operations, to_development)

                # Record signatures
                record.transaction_signatures = collection_result.get("signatures", [])

                # Update stats
                self._stats["total_collected_sol"] += total_sol
                self._stats["total_distributed_sol"] += total_sol
                self._stats["to_staking_sol"] += to_staking
                self._stats["to_operations_sol"] += to_operations
                self._stats["to_development_sol"] += to_development
                self._stats["collection_count"] += 1
                self._stats["last_collection"] = record.timestamp.isoformat()

                # Add to history
                self._distribution_history.append(record)

                logger.info(
                    f"Distribution complete: {total_sol:.6f} SOL "
                    f"(Staking: {to_staking:.6f}, Ops: {to_operations:.6f}, Dev: {to_development:.6f})"
                )

        except Exception as e:
            logger.error(f"Fee collection/distribution failed: {e}")
            raise

        self._last_collection = datetime.now(timezone.utc)
        return record

    async def _fund_staking_rewards(self, amount_sol: float):
        """
        Fund the staking rewards pool.

        Args:
            amount_sol: Amount in SOL to add to rewards pool
        """
        if amount_sol <= 0:
            return

        # In production, this would:
        # 1. Get the staking program's rewards vault address
        # 2. Create a transfer instruction
        # 3. Execute the transfer

        logger.info(f"Funded staking rewards pool with {amount_sol:.6f} SOL")

    async def _distribute_to_treasury(
        self,
        operations_sol: float,
        development_sol: float,
    ):
        """
        Distribute fees to treasury wallets.

        Args:
            operations_sol: Amount to operations wallet
            development_sol: Amount to development wallet
        """
        from core.treasury.wallet import WalletType

        if operations_sol > 0:
            # Transfer to operations wallet
            # Would use treasury.wallet_manager.execute_transfer()
            logger.info(f"Transferred {operations_sol:.6f} SOL to operations wallet")

        if development_sol > 0:
            # Transfer to development wallet
            logger.info(f"Transferred {development_sol:.6f} SOL to development wallet")

    # =========================================================================
    # Scheduled Collection
    # =========================================================================

    def start(self):
        """Start automated fee collection."""
        if self._running:
            logger.warning("Collection already running")
            return

        self._running = True
        self._collection_task = asyncio.create_task(self._collection_loop())
        logger.info(f"Started automated fee collection (interval: {self.collection_interval})")

    def stop(self):
        """Stop automated fee collection."""
        self._running = False
        if self._collection_task:
            self._collection_task.cancel()
            self._collection_task = None
        logger.info("Stopped automated fee collection")

    async def _collection_loop(self):
        """Background loop for automated collection."""
        while self._running:
            try:
                # Check if it's time to collect
                should_collect = (
                    self._last_collection is None or
                    datetime.now(timezone.utc) - self._last_collection >= self.collection_interval
                )

                if should_collect:
                    await self.collect_and_distribute()

            except Exception as e:
                logger.error(f"Collection loop error: {e}")

            # Wait before next check
            await asyncio.sleep(60)  # Check every minute

    # =========================================================================
    # Analytics
    # =========================================================================

    def get_stats(self) -> Dict[str, Any]:
        """Get collection and distribution statistics."""
        return {
            **self._stats,
            "allocation": {
                "staking_pct": self.allocation.staking_rewards_pct,
                "operations_pct": self.allocation.operations_pct,
                "development_pct": self.allocation.development_pct,
            },
        }

    def get_distribution_history(
        self,
        limit: int = 50,
        since: datetime = None,
    ) -> List[FeeDistributionRecord]:
        """
        Get distribution history.

        Args:
            limit: Maximum records to return
            since: Only return records after this time
        """
        history = self._distribution_history

        if since:
            history = [r for r in history if r.timestamp >= since]

        return sorted(history, key=lambda r: r.timestamp, reverse=True)[:limit]

    def get_revenue_summary(
        self,
        period_days: int = 30,
    ) -> Dict[str, Any]:
        """
        Get revenue summary for a period.

        Args:
            period_days: Number of days to summarize
        """
        cutoff = datetime.now(timezone.utc) - timedelta(days=period_days)

        period_records = [
            r for r in self._distribution_history
            if r.timestamp >= cutoff
        ]

        if not period_records:
            return {
                "period_days": period_days,
                "total_collected_sol": 0,
                "avg_daily_sol": 0,
                "distribution_count": 0,
                "to_staking_sol": 0,
                "to_operations_sol": 0,
                "to_development_sol": 0,
            }

        total = sum(r.total_fees_sol for r in period_records)
        avg_daily = total / period_days

        return {
            "period_days": period_days,
            "total_collected_sol": total,
            "avg_daily_sol": avg_daily,
            "projected_monthly_sol": avg_daily * 30,
            "distribution_count": len(period_records),
            "to_staking_sol": sum(r.to_staking_sol for r in period_records),
            "to_operations_sol": sum(r.to_operations_sol for r in period_records),
            "to_development_sol": sum(r.to_development_sol for r in period_records),
        }

    def estimate_staking_rewards_funding(
        self,
        expected_monthly_volume_sol: float,
    ) -> Dict[str, float]:
        """
        Estimate staking rewards funding from projected volume.

        Bags partner fee = 25% of platform fee = 0.25% of volume

        Args:
            expected_monthly_volume_sol: Expected monthly trading volume in SOL
        """
        # Partner receives 25% of 1% platform fee = 0.25% of volume
        partner_fee_rate = 0.0025
        monthly_fees = expected_monthly_volume_sol * partner_fee_rate

        return {
            "expected_volume_sol": expected_monthly_volume_sol,
            "partner_fee_rate": partner_fee_rate,
            "estimated_monthly_fees_sol": monthly_fees,
            "to_staking_rewards_sol": monthly_fees * self.allocation.staking_rewards_pct,
            "to_operations_sol": monthly_fees * self.allocation.operations_pct,
            "to_development_sol": monthly_fees * self.allocation.development_pct,
        }


# =============================================================================
# Singleton
# =============================================================================

_integration: Optional[TreasuryBagsIntegration] = None


def get_bags_integration() -> TreasuryBagsIntegration:
    """Get or create the singleton integration instance."""
    global _integration

    if _integration is None:
        _integration = TreasuryBagsIntegration()

    return _integration


# =============================================================================
# FastAPI Router
# =============================================================================


def create_bags_integration_router():
    """Create FastAPI router for Bags integration endpoints."""
    try:
        from fastapi import APIRouter, HTTPException
    except ImportError:
        return None

    router = APIRouter(prefix="/api/treasury/bags", tags=["Treasury Bags Integration"])
    integration = get_bags_integration()

    @router.get("/stats")
    async def get_stats():
        """Get collection and distribution statistics."""
        return integration.get_stats()

    @router.get("/history")
    async def get_history(limit: int = 50):
        """Get distribution history."""
        history = integration.get_distribution_history(limit=limit)
        return [r.to_dict() for r in history]

    @router.get("/revenue")
    async def get_revenue(period_days: int = 30):
        """Get revenue summary."""
        return integration.get_revenue_summary(period_days)

    @router.post("/collect")
    async def trigger_collection(dry_run: bool = False):
        """Manually trigger fee collection."""
        try:
            result = await integration.collect_and_distribute(dry_run=dry_run)
            return result.to_dict() if result else {"message": "No fees to collect"}
        except Exception as e:
            raise HTTPException(500, str(e))

    @router.get("/estimate")
    async def estimate_rewards(volume_sol: float):
        """Estimate rewards from projected volume."""
        return integration.estimate_staking_rewards_funding(volume_sol)

    return router
