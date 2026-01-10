"""
Revenue Distribution System
Prompt #95: Distribute marketplace revenue to contributors

Handles revenue distribution for data marketplace purchases.
"""

import logging
import os
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
import json

logger = logging.getLogger("jarvis.marketplace.distributor")


# =============================================================================
# MODELS
# =============================================================================

class PayoutStatus(Enum):
    """Status of a payout"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class PayoutRecord:
    """Record of a contributor payout"""
    id: str
    wallet: str
    amount_sol: float
    package_id: str
    contribution_pct: float
    status: PayoutStatus
    created_at: datetime
    processed_at: Optional[datetime] = None
    tx_signature: Optional[str] = None
    error: Optional[str] = None


@dataclass
class RevenueShare:
    """Revenue share configuration"""
    contributors_pct: float = 70.0  # 70% to data contributors
    platform_pct: float = 20.0      # 20% to platform
    staking_pct: float = 10.0       # 10% to staking rewards


@dataclass
class DistributionSummary:
    """Summary of revenue distribution"""
    package_id: str
    purchase_price: float
    contributor_total: float
    platform_total: float
    staking_total: float
    payouts: List[PayoutRecord]


# =============================================================================
# REVENUE DISTRIBUTOR
# =============================================================================

class RevenueDistributor:
    """
    Distributes marketplace revenue to contributors.

    Revenue split:
    - 70% to data contributors (proportional to contribution)
    - 20% to platform operations
    - 10% to staking rewards pool
    """

    def __init__(
        self,
        db_path: str = None,
        revenue_share: RevenueShare = None,
    ):
        self.db_path = db_path or os.getenv(
            "MARKETPLACE_DB",
            "data/marketplace.db"
        )
        self.revenue_share = revenue_share or RevenueShare()

        self._init_database()

    def _init_database(self):
        """Initialize payout tables"""
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Payouts table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS contributor_payouts (
                id TEXT PRIMARY KEY,
                wallet TEXT NOT NULL,
                amount_sol REAL NOT NULL,
                package_id TEXT NOT NULL,
                contribution_pct REAL NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                processed_at TEXT,
                tx_signature TEXT,
                error TEXT
            )
        """)

        # Accumulated balances
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS contributor_balances (
                wallet TEXT PRIMARY KEY,
                pending_sol REAL DEFAULT 0,
                total_earned_sol REAL DEFAULT 0,
                last_payout_at TEXT
            )
        """)

        # Platform revenue tracking
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS platform_revenue (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source TEXT NOT NULL,
                amount_sol REAL NOT NULL,
                package_id TEXT,
                recorded_at TEXT NOT NULL
            )
        """)

        conn.commit()
        conn.close()

    # =========================================================================
    # DISTRIBUTION
    # =========================================================================

    async def distribute_purchase(
        self,
        package_id: str,
        purchase_price: float,
        contributors: List[Dict[str, Any]],
    ) -> DistributionSummary:
        """
        Distribute revenue from a package purchase.

        Args:
            package_id: ID of purchased package
            purchase_price: Price paid in SOL
            contributors: List of {wallet, contribution_pct, data_count}

        Returns:
            DistributionSummary with payout details
        """
        # Calculate splits
        contributor_pool = purchase_price * (self.revenue_share.contributors_pct / 100)
        platform_share = purchase_price * (self.revenue_share.platform_pct / 100)
        staking_share = purchase_price * (self.revenue_share.staking_pct / 100)

        # Create payouts for contributors
        payouts = []
        for contributor in contributors:
            wallet = contributor["wallet"]
            pct = contributor["contribution_pct"]

            amount = contributor_pool * (pct / 100)

            if amount > 0:
                payout = await self._create_payout(
                    wallet=wallet,
                    amount=amount,
                    package_id=package_id,
                    contribution_pct=pct,
                )
                payouts.append(payout)

        # Record platform revenue
        await self._record_platform_revenue(
            "marketplace_sale",
            platform_share,
            package_id,
        )

        # Record staking pool contribution
        await self._record_platform_revenue(
            "staking_contribution",
            staking_share,
            package_id,
        )

        logger.info(
            f"Distributed {purchase_price} SOL for package {package_id}: "
            f"contributors={contributor_pool:.4f}, platform={platform_share:.4f}, "
            f"staking={staking_share:.4f}"
        )

        return DistributionSummary(
            package_id=package_id,
            purchase_price=purchase_price,
            contributor_total=contributor_pool,
            platform_total=platform_share,
            staking_total=staking_share,
            payouts=payouts,
        )

    async def _create_payout(
        self,
        wallet: str,
        amount: float,
        package_id: str,
        contribution_pct: float,
    ) -> PayoutRecord:
        """Create a payout record and update balance"""
        import hashlib

        payout_id = hashlib.sha256(
            f"{wallet}:{package_id}:{datetime.now(timezone.utc).isoformat()}".encode()
        ).hexdigest()[:16]

        payout = PayoutRecord(
            id=payout_id,
            wallet=wallet,
            amount_sol=amount,
            package_id=package_id,
            contribution_pct=contribution_pct,
            status=PayoutStatus.PENDING,
            created_at=datetime.now(timezone.utc),
        )

        # Save payout
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO contributor_payouts
            (id, wallet, amount_sol, package_id, contribution_pct,
             status, created_at, processed_at, tx_signature, error)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            payout.id,
            payout.wallet,
            payout.amount_sol,
            payout.package_id,
            payout.contribution_pct,
            payout.status.value,
            payout.created_at.isoformat(),
            None,
            None,
            None,
        ))

        # Update balance
        cursor.execute("""
            INSERT INTO contributor_balances (wallet, pending_sol, total_earned_sol)
            VALUES (?, ?, ?)
            ON CONFLICT(wallet) DO UPDATE SET
                pending_sol = pending_sol + ?,
                total_earned_sol = total_earned_sol + ?
        """, (
            wallet,
            amount,
            amount,
            amount,
            amount,
        ))

        conn.commit()
        conn.close()

        return payout

    async def _record_platform_revenue(
        self,
        source: str,
        amount: float,
        package_id: str = None,
    ):
        """Record platform revenue"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO platform_revenue
            (source, amount_sol, package_id, recorded_at)
            VALUES (?, ?, ?, ?)
        """, (
            source,
            amount,
            package_id,
            datetime.now(timezone.utc).isoformat(),
        ))

        conn.commit()
        conn.close()

    # =========================================================================
    # PAYOUT PROCESSING
    # =========================================================================

    async def process_pending_payouts(
        self,
        min_amount: float = 0.01,
        batch_size: int = 50,
    ) -> List[PayoutRecord]:
        """
        Process pending payouts to contributors.

        Args:
            min_amount: Minimum balance to process
            batch_size: Maximum payouts per batch

        Returns:
            List of processed payouts
        """
        # Get contributors with sufficient balance
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT wallet, pending_sol
            FROM contributor_balances
            WHERE pending_sol >= ?
            ORDER BY pending_sol DESC
            LIMIT ?
        """, (min_amount, batch_size))

        contributors = [(row[0], row[1]) for row in cursor.fetchall()]
        conn.close()

        processed = []

        for wallet, amount in contributors:
            try:
                payout = await self._execute_payout(wallet, amount)
                processed.append(payout)
            except Exception as e:
                logger.error(f"Payout failed for {wallet}: {e}")

        return processed

    async def _execute_payout(
        self,
        wallet: str,
        amount: float,
    ) -> PayoutRecord:
        """
        Execute a payout to a wallet.

        Note: This is a placeholder. In production, this would:
        1. Create a Solana transaction
        2. Sign with treasury key
        3. Submit to network
        4. Wait for confirmation
        """
        import hashlib

        payout_id = hashlib.sha256(
            f"batch:{wallet}:{datetime.now(timezone.utc).isoformat()}".encode()
        ).hexdigest()[:16]

        # In production: create and send Solana transaction here
        # tx_signature = await self._send_sol(wallet, amount)
        tx_signature = f"sim_{payout_id}"  # Simulated

        payout = PayoutRecord(
            id=payout_id,
            wallet=wallet,
            amount_sol=amount,
            package_id="batch",
            contribution_pct=0,
            status=PayoutStatus.COMPLETED,
            created_at=datetime.now(timezone.utc),
            processed_at=datetime.now(timezone.utc),
            tx_signature=tx_signature,
        )

        # Update database
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Record batch payout
        cursor.execute("""
            INSERT INTO contributor_payouts
            (id, wallet, amount_sol, package_id, contribution_pct,
             status, created_at, processed_at, tx_signature, error)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            payout.id,
            payout.wallet,
            payout.amount_sol,
            "batch_payout",
            0,
            payout.status.value,
            payout.created_at.isoformat(),
            payout.processed_at.isoformat(),
            payout.tx_signature,
            None,
        ))

        # Clear pending balance
        cursor.execute("""
            UPDATE contributor_balances
            SET pending_sol = 0, last_payout_at = ?
            WHERE wallet = ?
        """, (datetime.now(timezone.utc).isoformat(), wallet))

        # Mark individual payouts as completed
        cursor.execute("""
            UPDATE contributor_payouts
            SET status = ?, processed_at = ?, tx_signature = ?
            WHERE wallet = ? AND status = ?
        """, (
            PayoutStatus.COMPLETED.value,
            datetime.now(timezone.utc).isoformat(),
            tx_signature,
            wallet,
            PayoutStatus.PENDING.value,
        ))

        conn.commit()
        conn.close()

        logger.info(f"Processed payout of {amount:.4f} SOL to {wallet[:8]}...")

        return payout

    # =========================================================================
    # QUERIES
    # =========================================================================

    async def get_contributor_balance(self, wallet: str) -> Dict[str, float]:
        """Get contributor's balance information"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            "SELECT pending_sol, total_earned_sol FROM contributor_balances WHERE wallet = ?",
            (wallet,)
        )

        row = cursor.fetchone()
        conn.close()

        if row is None:
            return {"pending": 0, "total_earned": 0}

        return {
            "pending": row[0],
            "total_earned": row[1],
        }

    async def get_payout_history(
        self,
        wallet: str = None,
        status: PayoutStatus = None,
        limit: int = 50,
    ) -> List[PayoutRecord]:
        """Get payout history"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        query = "SELECT * FROM contributor_payouts WHERE 1=1"
        params = []

        if wallet:
            query += " AND wallet = ?"
            params.append(wallet)

        if status:
            query += " AND status = ?"
            params.append(status.value)

        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        cursor.execute(query, params)

        payouts = []
        for row in cursor.fetchall():
            payouts.append(PayoutRecord(
                id=row[0],
                wallet=row[1],
                amount_sol=row[2],
                package_id=row[3],
                contribution_pct=row[4],
                status=PayoutStatus(row[5]),
                created_at=datetime.fromisoformat(row[6]),
                processed_at=datetime.fromisoformat(row[7]) if row[7] else None,
                tx_signature=row[8],
                error=row[9],
            ))

        conn.close()
        return payouts

    async def get_platform_revenue(
        self,
        since: datetime = None,
        source: str = None,
    ) -> Dict[str, float]:
        """Get platform revenue summary"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        query = "SELECT source, SUM(amount_sol) FROM platform_revenue WHERE 1=1"
        params = []

        if since:
            query += " AND recorded_at >= ?"
            params.append(since.isoformat())

        if source:
            query += " AND source = ?"
            params.append(source)

        query += " GROUP BY source"

        cursor.execute(query, params)

        revenue = {row[0]: row[1] for row in cursor.fetchall()}

        conn.close()
        return revenue

    async def get_top_contributors(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get top contributors by total earnings"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT wallet, pending_sol, total_earned_sol
            FROM contributor_balances
            ORDER BY total_earned_sol DESC
            LIMIT ?
        """, (limit,))

        contributors = [
            {
                "wallet": row[0],
                "pending": row[1],
                "total_earned": row[2],
            }
            for row in cursor.fetchall()
        ]

        conn.close()
        return contributors


# =============================================================================
# SINGLETON
# =============================================================================

_distributor: Optional[RevenueDistributor] = None


def get_revenue_distributor() -> RevenueDistributor:
    """Get or create the revenue distributor singleton"""
    global _distributor
    if _distributor is None:
        _distributor = RevenueDistributor()
    return _distributor
