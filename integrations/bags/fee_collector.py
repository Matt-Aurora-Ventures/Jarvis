"""
Fee Collector for Bags.fm Partner Fees.

Monitors and claims accumulated partner fees:
- Periodic fee balance checks
- Automatic claiming when threshold reached
- Distribution to treasury
- Event tracking for analytics
"""

import asyncio
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

from .client import BagsClient, get_bags_client

logger = logging.getLogger("jarvis.integrations.bags.fee_collector")


# =============================================================================
# Configuration
# =============================================================================


@dataclass
class FeeCollectorConfig:
    """Configuration for fee collector."""

    # Claim settings
    claim_threshold_sol: float = 0.1  # Minimum SOL to trigger claim
    claim_wallet: str = field(default_factory=lambda: os.getenv("TREASURY_WALLET", ""))

    # Check interval
    check_interval: int = 3600  # 1 hour

    # Retry settings
    max_claim_retries: int = 3
    retry_delay: float = 5.0


@dataclass
class FeeClaimEvent:
    """Record of a fee claim."""

    id: str
    timestamp: datetime
    amount_lamports: int
    amount_sol: float
    signature: str
    destination: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "timestamp": self.timestamp.isoformat(),
            "amount_lamports": self.amount_lamports,
            "amount_sol": self.amount_sol,
            "signature": self.signature,
            "destination": self.destination,
        }


# =============================================================================
# Fee Collector
# =============================================================================


class FeeCollector:
    """
    Collects and manages Bags.fm partner fees.

    Features:
    - Automatic fee monitoring
    - Threshold-based claiming
    - Treasury distribution integration
    - Comprehensive analytics
    """

    LAMPORTS_PER_SOL = 1_000_000_000

    def __init__(
        self,
        config: FeeCollectorConfig = None,
        bags_client: BagsClient = None,
        on_claim: Callable[[FeeClaimEvent], None] = None,
    ):
        self.config = config or FeeCollectorConfig()
        self._client = bags_client or get_bags_client()
        self._on_claim = on_claim

        # State
        self._running = False
        self._monitor_task: Optional[asyncio.Task] = None

        # Statistics
        self._claim_history: List[FeeClaimEvent] = []
        self._total_claimed_lamports = 0
        self._last_check: Optional[datetime] = None
        self._pending_fees: int = 0

    # =========================================================================
    # Fee Monitoring
    # =========================================================================

    async def check_fees(self) -> Dict[str, Any]:
        """Check current fee balance."""
        try:
            stats = await self._client.get_partner_stats()
            self._pending_fees = stats.get("pending_fees", 0)
            self._last_check = datetime.now(timezone.utc)

            return {
                "pending_fees_lamports": self._pending_fees,
                "pending_fees_sol": self._pending_fees / self.LAMPORTS_PER_SOL,
                "threshold_sol": self.config.claim_threshold_sol,
                "should_claim": self._should_claim(),
                "total_earned": stats.get("total_fees_earned", 0),
                "total_claimed": stats.get("claimed_fees", 0),
            }

        except Exception as e:
            logger.error(f"Failed to check fees: {e}")
            return {"error": str(e)}

    def _should_claim(self) -> bool:
        """Check if we should claim fees."""
        threshold_lamports = int(self.config.claim_threshold_sol * self.LAMPORTS_PER_SOL)
        return self._pending_fees >= threshold_lamports

    # =========================================================================
    # Fee Claiming
    # =========================================================================

    async def claim_fees(self, force: bool = False) -> Optional[FeeClaimEvent]:
        """
        Claim accumulated fees.

        Args:
            force: Claim even if below threshold

        Returns:
            FeeClaimEvent if successful
        """
        # Check threshold
        if not force and not self._should_claim():
            logger.debug(
                f"Below threshold: {self._pending_fees / self.LAMPORTS_PER_SOL:.6f} SOL "
                f"< {self.config.claim_threshold_sol} SOL"
            )
            return None

        if not self.config.claim_wallet:
            logger.error("No claim wallet configured")
            return None

        # Attempt claim with retries
        for attempt in range(self.config.max_claim_retries):
            try:
                result = await self._client.claim_fees(self.config.claim_wallet)

                if result.get("success"):
                    import uuid

                    event = FeeClaimEvent(
                        id=f"fee_{uuid.uuid4().hex[:12]}",
                        timestamp=datetime.now(timezone.utc),
                        amount_lamports=result.get("amount", 0),
                        amount_sol=result.get("amount", 0) / self.LAMPORTS_PER_SOL,
                        signature=result.get("signature", ""),
                        destination=self.config.claim_wallet,
                    )

                    # Update state
                    self._claim_history.append(event)
                    self._total_claimed_lamports += event.amount_lamports
                    self._pending_fees = 0

                    logger.info(
                        f"Claimed {event.amount_sol:.6f} SOL in fees "
                        f"(tx: {event.signature[:16]}...)"
                    )

                    # Notify callback
                    if self._on_claim:
                        try:
                            self._on_claim(event)
                        except Exception as e:
                            logger.error(f"Claim callback failed: {e}")

                    return event

                else:
                    error = result.get("error", "Unknown error")
                    logger.warning(f"Claim failed (attempt {attempt + 1}): {error}")

            except Exception as e:
                logger.warning(f"Claim error (attempt {attempt + 1}): {e}")

            if attempt < self.config.max_claim_retries - 1:
                await asyncio.sleep(self.config.retry_delay)

        logger.error("Fee claim failed after all retries")
        return None

    # =========================================================================
    # Monitoring Service
    # =========================================================================

    async def start(self):
        """Start the fee monitoring service."""
        if self._running:
            return

        self._running = True
        self._monitor_task = asyncio.create_task(self._monitor_loop())
        logger.info("Fee collector started")

    async def stop(self):
        """Stop the fee monitoring service."""
        self._running = False
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
        logger.info("Fee collector stopped")

    async def _monitor_loop(self):
        """Background monitoring loop."""
        while self._running:
            try:
                # Check fees
                await self.check_fees()

                # Claim if threshold met
                if self._should_claim():
                    await self.claim_fees()

            except Exception as e:
                logger.error(f"Monitor loop error: {e}")

            await asyncio.sleep(self.config.check_interval)

    # =========================================================================
    # Statistics
    # =========================================================================

    def get_stats(self) -> Dict[str, Any]:
        """Get fee collector statistics."""
        return {
            "running": self._running,
            "pending_fees_sol": self._pending_fees / self.LAMPORTS_PER_SOL,
            "total_claimed_sol": self._total_claimed_lamports / self.LAMPORTS_PER_SOL,
            "claim_count": len(self._claim_history),
            "last_check": self._last_check.isoformat() if self._last_check else None,
            "threshold_sol": self.config.claim_threshold_sol,
        }

    def get_claim_history(self, limit: int = 50) -> List[Dict]:
        """Get recent claim history."""
        return [e.to_dict() for e in self._claim_history[-limit:]]


# =============================================================================
# Singleton
# =============================================================================

_collector: Optional[FeeCollector] = None


def get_fee_collector() -> FeeCollector:
    """Get singleton fee collector."""
    global _collector
    if _collector is None:
        _collector = FeeCollector()
    return _collector
