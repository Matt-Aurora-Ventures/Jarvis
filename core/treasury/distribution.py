"""
Profit Distribution System.

Handles automated distribution of treasury profits to stakers.

Distribution Schedule:
- Weekly profit sweep every Sunday at midnight UTC
- Profits moved from Profit Buffer to Staking Rewards Pool
- Stakers can claim their share based on stake weight

Revenue Split:
- 60% → Staking Rewards
- 25% → Operations
- 15% → Development Reserve
"""

import logging
import os
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger("jarvis.treasury.distribution")


@dataclass
class DistributionConfig:
    """Configuration for profit distribution."""

    # Revenue split percentages
    staking_rewards_pct: float = 0.60
    operations_pct: float = 0.25
    development_pct: float = 0.15

    # Wallet addresses
    staking_pool_wallet: str = ""
    operations_wallet: str = ""
    development_wallet: str = ""

    # Schedule
    distribution_day: int = 6  # Sunday (0=Monday, 6=Sunday)
    distribution_hour_utc: int = 0

    # Thresholds
    min_distribution_lamports: int = 100_000_000  # 0.1 SOL minimum

    def validate(self):
        """Validate configuration."""
        total = self.staking_rewards_pct + self.operations_pct + self.development_pct
        if abs(total - 1.0) > 0.001:
            raise ValueError(f"Distribution percentages must sum to 1.0, got {total}")

        if not self.staking_pool_wallet:
            raise ValueError("Staking pool wallet required")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "staking_rewards_pct": self.staking_rewards_pct,
            "operations_pct": self.operations_pct,
            "development_pct": self.development_pct,
            "distribution_day": self.distribution_day,
            "distribution_hour_utc": self.distribution_hour_utc,
            "min_distribution_lamports": self.min_distribution_lamports,
        }


@dataclass
class Distribution:
    """Record of a profit distribution."""
    id: int
    timestamp: datetime
    total_amount: int
    staking_amount: int
    operations_amount: int
    development_amount: int
    staking_signature: Optional[str] = None
    operations_signature: Optional[str] = None
    development_signature: Optional[str] = None
    status: str = "pending"  # pending, completed, failed

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "timestamp": self.timestamp.isoformat(),
            "total_amount": self.total_amount,
            "staking_amount": self.staking_amount,
            "operations_amount": self.operations_amount,
            "development_amount": self.development_amount,
            "staking_signature": self.staking_signature,
            "operations_signature": self.operations_signature,
            "development_signature": self.development_signature,
            "status": self.status,
        }


class ProfitDistributor:
    """
    Manages profit distribution from treasury.

    Workflow:
    1. Calculate realized profits in Profit Buffer
    2. Split according to config percentages
    3. Execute transfers to destination wallets
    4. Update staking contract reward rate
    5. Log distribution for transparency
    """

    def __init__(
        self,
        config: DistributionConfig,
        wallet_manager: Any = None,
        db_path: str = None,
        on_distribution: Optional[Callable[[Distribution], None]] = None,
    ):
        """
        Initialize profit distributor.

        Args:
            config: Distribution configuration
            wallet_manager: WalletManager instance
            db_path: Path to distribution log database
            on_distribution: Callback when distribution completes
        """
        self.config = config
        self.wallet_manager = wallet_manager
        self.on_distribution = on_distribution

        self.db_path = db_path or str(
            Path(os.getenv("DATA_DIR", "data")) / "distributions.db"
        )
        self._init_database()

        self._last_distribution: Optional[datetime] = None
        self._running = False

    def _init_database(self):
        """Initialize distribution log database."""
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS distributions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                total_amount INTEGER NOT NULL,
                staking_amount INTEGER NOT NULL,
                operations_amount INTEGER NOT NULL,
                development_amount INTEGER NOT NULL,
                staking_signature TEXT,
                operations_signature TEXT,
                development_signature TEXT,
                status TEXT DEFAULT 'pending',
                error_message TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_distributions_timestamp
            ON distributions(timestamp)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_distributions_status
            ON distributions(status)
        """)

        conn.commit()
        conn.close()

        logger.info(f"Distribution database initialized: {self.db_path}")

    def is_distribution_due(self) -> bool:
        """Check if distribution is due based on schedule."""
        now = datetime.now(timezone.utc)

        # Check if it's the right day and hour
        if now.weekday() != self.config.distribution_day:
            return False

        if now.hour != self.config.distribution_hour_utc:
            return False

        # Check if we already distributed today
        if self._last_distribution:
            if self._last_distribution.date() == now.date():
                return False

        return True

    async def calculate_distributable(self) -> int:
        """
        Calculate amount available for distribution.

        Returns profit buffer balance minus minimum reserve.
        """
        if not self.wallet_manager:
            return 0

        from core.treasury.wallet import WalletType

        balance = await self.wallet_manager.get_balance(WalletType.PROFIT)
        if not balance:
            return 0

        return balance.sol_balance

    def calculate_split(self, total_amount: int) -> Dict[str, int]:
        """
        Calculate distribution split.

        Args:
            total_amount: Total amount to distribute

        Returns:
            Dict with amounts for each destination
        """
        return {
            "staking": int(total_amount * self.config.staking_rewards_pct),
            "operations": int(total_amount * self.config.operations_pct),
            "development": int(total_amount * self.config.development_pct),
        }

    async def execute_distribution(
        self,
        amount: int = None,
        dry_run: bool = False,
    ) -> Distribution:
        """
        Execute profit distribution.

        Args:
            amount: Amount to distribute (uses profit buffer if not specified)
            dry_run: If True, don't execute transfers

        Returns:
            Distribution record
        """
        now = datetime.now(timezone.utc)

        # Calculate amount
        if amount is None:
            amount = await self.calculate_distributable()

        if amount < self.config.min_distribution_lamports:
            logger.info(f"Amount {amount} below minimum {self.config.min_distribution_lamports}")
            raise ValueError(f"Amount below minimum threshold")

        # Calculate split
        split = self.calculate_split(amount)

        # Create distribution record
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT INTO distributions
            (timestamp, total_amount, staking_amount, operations_amount, development_amount, status)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                now.isoformat(),
                amount,
                split["staking"],
                split["operations"],
                split["development"],
                "dry_run" if dry_run else "pending",
            ),
        )

        dist_id = cursor.lastrowid
        conn.commit()
        conn.close()

        distribution = Distribution(
            id=dist_id,
            timestamp=now,
            total_amount=amount,
            staking_amount=split["staking"],
            operations_amount=split["operations"],
            development_amount=split["development"],
            status="dry_run" if dry_run else "pending",
        )

        if dry_run:
            logger.info(f"Dry run distribution: {distribution.to_dict()}")
            return distribution

        # Execute transfers
        try:
            from core.treasury.wallet import WalletType

            # Transfer to staking pool
            if split["staking"] > 0 and self.config.staking_pool_wallet:
                sig = await self.wallet_manager.execute_transfer(
                    from_wallet=WalletType.PROFIT,
                    to_address=self.config.staking_pool_wallet,
                    amount_lamports=split["staking"],
                    memo="Weekly staking rewards",
                )
                distribution.staking_signature = sig

            # Transfer to operations
            if split["operations"] > 0 and self.config.operations_wallet:
                sig = await self.wallet_manager.execute_transfer(
                    from_wallet=WalletType.PROFIT,
                    to_address=self.config.operations_wallet,
                    amount_lamports=split["operations"],
                    memo="Operations allocation",
                )
                distribution.operations_signature = sig

            # Transfer to development
            if split["development"] > 0 and self.config.development_wallet:
                sig = await self.wallet_manager.execute_transfer(
                    from_wallet=WalletType.PROFIT,
                    to_address=self.config.development_wallet,
                    amount_lamports=split["development"],
                    memo="Development allocation",
                )
                distribution.development_signature = sig

            distribution.status = "completed"
            self._last_distribution = now

            logger.info(f"Distribution completed: {amount} lamports distributed")

        except Exception as e:
            distribution.status = "failed"
            logger.error(f"Distribution failed: {e}")

        # Update database
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            UPDATE distributions
            SET status = ?, staking_signature = ?, operations_signature = ?, development_signature = ?
            WHERE id = ?
            """,
            (
                distribution.status,
                distribution.staking_signature,
                distribution.operations_signature,
                distribution.development_signature,
                dist_id,
            ),
        )

        conn.commit()
        conn.close()

        # Callback
        if self.on_distribution:
            self.on_distribution(distribution)

        return distribution

    def get_distribution_history(
        self,
        limit: int = 52,  # ~1 year of weekly distributions
        status: str = None,
    ) -> List[Distribution]:
        """Get distribution history."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        if status:
            cursor.execute(
                """
                SELECT * FROM distributions
                WHERE status = ?
                ORDER BY timestamp DESC
                LIMIT ?
                """,
                (status, limit),
            )
        else:
            cursor.execute(
                """
                SELECT * FROM distributions
                ORDER BY timestamp DESC
                LIMIT ?
                """,
                (limit,),
            )

        rows = cursor.fetchall()
        conn.close()

        distributions = []
        for row in rows:
            distributions.append(Distribution(
                id=row[0],
                timestamp=datetime.fromisoformat(row[1]),
                total_amount=row[2],
                staking_amount=row[3],
                operations_amount=row[4],
                development_amount=row[5],
                staking_signature=row[6],
                operations_signature=row[7],
                development_signature=row[8],
                status=row[9],
            ))

        return distributions

    def get_distribution_stats(self) -> Dict[str, Any]:
        """Get distribution statistics."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Total distributed
        cursor.execute(
            """
            SELECT SUM(total_amount), SUM(staking_amount), COUNT(*)
            FROM distributions
            WHERE status = 'completed'
            """
        )
        row = cursor.fetchone()

        total_distributed = row[0] or 0
        total_to_staking = row[1] or 0
        distribution_count = row[2] or 0

        # Recent distributions
        cursor.execute(
            """
            SELECT total_amount
            FROM distributions
            WHERE status = 'completed'
            ORDER BY timestamp DESC
            LIMIT 4
            """
        )
        recent = [r[0] for r in cursor.fetchall()]

        conn.close()

        return {
            "total_distributed": total_distributed,
            "total_to_staking": total_to_staking,
            "distribution_count": distribution_count,
            "avg_distribution": total_distributed / distribution_count if distribution_count > 0 else 0,
            "recent_distributions": recent,
            "last_distribution": self._last_distribution.isoformat() if self._last_distribution else None,
        }

    async def update_staking_reward_rate(self, new_rewards: int):
        """
        Update staking contract with new rewards.

        Calls the staking contract's deposit_rewards instruction.
        """
        # This would interact with the Anchor staking program
        # For now, just log
        logger.info(f"Would update staking reward rate with {new_rewards} lamports")

        # In production:
        # 1. Call deposit_rewards on staking contract
        # 2. Update reward_rate based on total staked

    def get_status(self) -> Dict[str, Any]:
        """Get distributor status."""
        return {
            "config": self.config.to_dict(),
            "stats": self.get_distribution_stats(),
            "is_due": self.is_distribution_due(),
            "running": self._running,
        }
