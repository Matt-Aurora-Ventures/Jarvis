"""
Staker Rewards Calculator
Prompt #99: Calculate and project staking rewards

Provides rewards calculation and projections for stakers.
"""

import logging
import os
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
import json
import math

logger = logging.getLogger("jarvis.staking.rewards")


# =============================================================================
# MODELS
# =============================================================================

class StakeTier(Enum):
    """Staking tiers with bonus multipliers"""
    BRONZE = "bronze"      # < 100 BAGS
    SILVER = "silver"      # 100-1000 BAGS
    GOLD = "gold"          # 1000-10000 BAGS
    PLATINUM = "platinum"  # > 10000 BAGS


@dataclass
class StakeInfo:
    """Information about a stake"""
    wallet: str
    staked_amount: float
    stake_start: datetime
    lock_duration_days: int
    tier: StakeTier
    bonus_multiplier: float


@dataclass
class RewardCalculation:
    """Calculated rewards for a period"""
    wallet: str
    period_start: datetime
    period_end: datetime
    base_reward: float
    tier_bonus: float
    lock_bonus: float
    total_reward: float
    apy: float


@dataclass
class RewardProjection:
    """Projected future rewards"""
    wallet: str
    staked_amount: float
    daily_reward: float
    weekly_reward: float
    monthly_reward: float
    yearly_reward: float
    projected_apy: float
    projections: List[Dict[str, float]] = field(default_factory=list)


# =============================================================================
# TIER CONFIGURATION
# =============================================================================

TIER_CONFIG = {
    StakeTier.BRONZE: {
        "min_stake": 0,
        "max_stake": 100,
        "base_multiplier": 1.0,
    },
    StakeTier.SILVER: {
        "min_stake": 100,
        "max_stake": 1000,
        "base_multiplier": 1.1,
    },
    StakeTier.GOLD: {
        "min_stake": 1000,
        "max_stake": 10000,
        "base_multiplier": 1.25,
    },
    StakeTier.PLATINUM: {
        "min_stake": 10000,
        "max_stake": float('inf'),
        "base_multiplier": 1.5,
    },
}

# Lock duration bonuses
LOCK_BONUSES = {
    0: 1.0,      # No lock
    30: 1.05,    # 1 month: 5% bonus
    90: 1.15,    # 3 months: 15% bonus
    180: 1.30,   # 6 months: 30% bonus
    365: 1.50,   # 1 year: 50% bonus
}


# =============================================================================
# STAKER REWARDS CALCULATOR
# =============================================================================

class StakerRewardsCalculator:
    """
    Calculates staking rewards and projections.

    Features:
    - Tiered rewards based on stake amount
    - Lock duration bonuses
    - APY calculations
    - Reward projections
    - Historical tracking
    """

    # Base APY before multipliers
    BASE_APY = 0.15  # 15% base APY

    def __init__(
        self,
        db_path: str = None,
        base_apy: float = None,
    ):
        self.db_path = db_path or os.getenv(
            "STAKING_DB",
            "data/staking.db"
        )
        self.base_apy = base_apy or self.BASE_APY

        self._init_database()

    def _init_database(self):
        """Initialize staking database"""
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Stakes table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS stakes (
                wallet TEXT PRIMARY KEY,
                staked_amount REAL NOT NULL,
                stake_start TEXT NOT NULL,
                lock_duration_days INTEGER DEFAULT 0,
                last_claim TEXT
            )
        """)

        # Rewards history
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS reward_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                wallet TEXT NOT NULL,
                period_start TEXT NOT NULL,
                period_end TEXT NOT NULL,
                base_reward REAL,
                tier_bonus REAL,
                lock_bonus REAL,
                total_reward REAL,
                claimed_at TEXT,
                tx_signature TEXT
            )
        """)

        # Pool stats
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS reward_pool (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                total_pool REAL NOT NULL,
                distributed REAL DEFAULT 0,
                remaining REAL NOT NULL,
                period_start TEXT NOT NULL,
                period_end TEXT,
                created_at TEXT NOT NULL
            )
        """)

        conn.commit()
        conn.close()

    # =========================================================================
    # TIER CALCULATION
    # =========================================================================

    def get_tier(self, staked_amount: float) -> StakeTier:
        """Get staking tier for an amount"""
        for tier in [StakeTier.PLATINUM, StakeTier.GOLD, StakeTier.SILVER, StakeTier.BRONZE]:
            config = TIER_CONFIG[tier]
            if staked_amount >= config["min_stake"]:
                return tier
        return StakeTier.BRONZE

    def get_tier_multiplier(self, tier: StakeTier) -> float:
        """Get multiplier for a tier"""
        return TIER_CONFIG[tier]["base_multiplier"]

    def get_lock_multiplier(self, lock_days: int) -> float:
        """Get multiplier for lock duration"""
        # Find highest applicable lock bonus
        for days, mult in sorted(LOCK_BONUSES.items(), reverse=True):
            if lock_days >= days:
                return mult
        return 1.0

    # =========================================================================
    # REWARD CALCULATION
    # =========================================================================

    async def calculate_rewards(
        self,
        wallet: str,
        period_start: datetime = None,
        period_end: datetime = None,
    ) -> RewardCalculation:
        """
        Calculate rewards for a staker for a period.

        Args:
            wallet: Wallet address
            period_start: Start of reward period
            period_end: End of reward period

        Returns:
            RewardCalculation with breakdown
        """
        # Get stake info
        stake = await self.get_stake(wallet)
        if stake is None:
            return RewardCalculation(
                wallet=wallet,
                period_start=period_start or datetime.now(timezone.utc),
                period_end=period_end or datetime.now(timezone.utc),
                base_reward=0,
                tier_bonus=0,
                lock_bonus=0,
                total_reward=0,
                apy=0,
            )

        # Default to current period
        if period_end is None:
            period_end = datetime.now(timezone.utc)
        if period_start is None:
            # Default to last claim or stake start
            period_start = stake.stake_start

        # Calculate period in days
        period_days = (period_end - period_start).days
        if period_days <= 0:
            period_days = 1

        # Base reward calculation
        # Daily reward = (staked * base_apy) / 365
        daily_rate = self.base_apy / 365
        base_reward = stake.staked_amount * daily_rate * period_days

        # Apply tier multiplier
        tier_mult = self.get_tier_multiplier(stake.tier)
        tier_bonus = base_reward * (tier_mult - 1)

        # Apply lock multiplier
        lock_mult = self.get_lock_multiplier(stake.lock_duration_days)
        lock_bonus = base_reward * (lock_mult - 1)

        # Total reward
        total_reward = base_reward * tier_mult * lock_mult

        # Calculate effective APY
        effective_apy = self.base_apy * tier_mult * lock_mult

        return RewardCalculation(
            wallet=wallet,
            period_start=period_start,
            period_end=period_end,
            base_reward=base_reward,
            tier_bonus=tier_bonus,
            lock_bonus=lock_bonus,
            total_reward=total_reward,
            apy=effective_apy,
        )

    async def project_rewards(
        self,
        wallet: str,
        projection_days: int = 365,
    ) -> RewardProjection:
        """
        Project future rewards for a staker.

        Args:
            wallet: Wallet address
            projection_days: Days to project

        Returns:
            RewardProjection with future estimates
        """
        stake = await self.get_stake(wallet)
        if stake is None:
            return RewardProjection(
                wallet=wallet,
                staked_amount=0,
                daily_reward=0,
                weekly_reward=0,
                monthly_reward=0,
                yearly_reward=0,
                projected_apy=0,
            )

        # Get multipliers
        tier_mult = self.get_tier_multiplier(stake.tier)
        lock_mult = self.get_lock_multiplier(stake.lock_duration_days)
        total_mult = tier_mult * lock_mult

        # Calculate daily reward
        daily_rate = self.base_apy / 365
        daily_reward = stake.staked_amount * daily_rate * total_mult

        # Calculate projected APY
        projected_apy = self.base_apy * total_mult

        # Generate projection timeline
        projections = []
        cumulative = 0

        for day in range(1, projection_days + 1):
            cumulative += daily_reward

            # Add milestones
            if day == 7:
                projections.append({
                    "label": "1 Week",
                    "days": day,
                    "reward": cumulative,
                })
            elif day == 30:
                projections.append({
                    "label": "1 Month",
                    "days": day,
                    "reward": cumulative,
                })
            elif day == 90:
                projections.append({
                    "label": "3 Months",
                    "days": day,
                    "reward": cumulative,
                })
            elif day == 180:
                projections.append({
                    "label": "6 Months",
                    "days": day,
                    "reward": cumulative,
                })
            elif day == 365:
                projections.append({
                    "label": "1 Year",
                    "days": day,
                    "reward": cumulative,
                })

        return RewardProjection(
            wallet=wallet,
            staked_amount=stake.staked_amount,
            daily_reward=daily_reward,
            weekly_reward=daily_reward * 7,
            monthly_reward=daily_reward * 30,
            yearly_reward=daily_reward * 365,
            projected_apy=projected_apy,
            projections=projections,
        )

    # =========================================================================
    # STAKE MANAGEMENT
    # =========================================================================

    async def get_stake(self, wallet: str) -> Optional[StakeInfo]:
        """Get stake information for a wallet"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            "SELECT * FROM stakes WHERE wallet = ?",
            (wallet,)
        )

        row = cursor.fetchone()
        conn.close()

        if row is None:
            return None

        staked = row[1]
        tier = self.get_tier(staked)

        return StakeInfo(
            wallet=row[0],
            staked_amount=staked,
            stake_start=datetime.fromisoformat(row[2]),
            lock_duration_days=row[3],
            tier=tier,
            bonus_multiplier=self.get_tier_multiplier(tier) * self.get_lock_multiplier(row[3]),
        )

    async def record_stake(
        self,
        wallet: str,
        amount: float,
        lock_days: int = 0,
    ):
        """Record a new stake or update existing"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO stakes (wallet, staked_amount, stake_start, lock_duration_days)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(wallet) DO UPDATE SET
                staked_amount = staked_amount + ?,
                lock_duration_days = MAX(lock_duration_days, ?)
        """, (
            wallet,
            amount,
            datetime.now(timezone.utc).isoformat(),
            lock_days,
            amount,
            lock_days,
        ))

        conn.commit()
        conn.close()

    async def record_claim(
        self,
        wallet: str,
        reward: RewardCalculation,
        tx_signature: str = None,
    ):
        """Record a reward claim"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Record in history
        cursor.execute("""
            INSERT INTO reward_history
            (wallet, period_start, period_end, base_reward, tier_bonus,
             lock_bonus, total_reward, claimed_at, tx_signature)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            wallet,
            reward.period_start.isoformat(),
            reward.period_end.isoformat(),
            reward.base_reward,
            reward.tier_bonus,
            reward.lock_bonus,
            reward.total_reward,
            datetime.now(timezone.utc).isoformat(),
            tx_signature,
        ))

        # Update last claim
        cursor.execute("""
            UPDATE stakes SET last_claim = ? WHERE wallet = ?
        """, (datetime.now(timezone.utc).isoformat(), wallet))

        conn.commit()
        conn.close()

    # =========================================================================
    # POOL MANAGEMENT
    # =========================================================================

    async def get_total_staked(self) -> float:
        """Get total staked amount"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("SELECT SUM(staked_amount) FROM stakes")

        total = cursor.fetchone()[0] or 0

        conn.close()
        return total

    async def get_staker_count(self) -> int:
        """Get number of stakers"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(*) FROM stakes WHERE staked_amount > 0")

        count = cursor.fetchone()[0]

        conn.close()
        return count

    async def get_reward_pool_status(self) -> Dict[str, float]:
        """Get current reward pool status"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT total_pool, distributed, remaining
            FROM reward_pool
            ORDER BY created_at DESC
            LIMIT 1
        """)

        row = cursor.fetchone()
        conn.close()

        if row is None:
            return {"total": 0, "distributed": 0, "remaining": 0}

        return {
            "total": row[0],
            "distributed": row[1],
            "remaining": row[2],
        }

    async def add_to_pool(self, amount: float, source: str = "treasury"):
        """Add funds to the reward pool"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO reward_pool
            (total_pool, distributed, remaining, period_start, created_at)
            VALUES (?, 0, ?, ?, ?)
        """, (
            amount,
            amount,
            datetime.now(timezone.utc).isoformat(),
            datetime.now(timezone.utc).isoformat(),
        ))

        conn.commit()
        conn.close()

        logger.info(f"Added {amount} to reward pool from {source}")

    # =========================================================================
    # ANALYTICS
    # =========================================================================

    async def get_reward_history(
        self,
        wallet: str = None,
        days: int = 30,
    ) -> List[Dict[str, Any]]:
        """Get reward claim history"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()

        query = "SELECT * FROM reward_history WHERE claimed_at >= ?"
        params = [since]

        if wallet:
            query += " AND wallet = ?"
            params.append(wallet)

        query += " ORDER BY claimed_at DESC"

        cursor.execute(query, params)

        columns = [d[0] for d in cursor.description]
        history = [dict(zip(columns, row)) for row in cursor.fetchall()]

        conn.close()
        return history

    async def get_tier_distribution(self) -> Dict[str, int]:
        """Get distribution of stakers by tier"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("SELECT staked_amount FROM stakes WHERE staked_amount > 0")

        distribution = {tier.value: 0 for tier in StakeTier}

        for row in cursor.fetchall():
            tier = self.get_tier(row[0])
            distribution[tier.value] += 1

        conn.close()
        return distribution

    async def get_apy_range(self) -> Dict[str, float]:
        """Get APY range based on tier and lock combinations"""
        min_apy = self.base_apy
        max_apy = self.base_apy * TIER_CONFIG[StakeTier.PLATINUM]["base_multiplier"] * max(LOCK_BONUSES.values())

        return {
            "base": self.base_apy,
            "min": min_apy,
            "max": max_apy,
            "average": (min_apy + max_apy) / 2,
        }


# =============================================================================
# SINGLETON
# =============================================================================

_calculator: Optional[StakerRewardsCalculator] = None


def get_rewards_calculator() -> StakerRewardsCalculator:
    """Get or create the rewards calculator singleton"""
    global _calculator
    if _calculator is None:
        _calculator = StakerRewardsCalculator()
    return _calculator
