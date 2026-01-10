"""
Reputation Scoring System
Prompt #96: On-chain reputation scoring

Calculates reputation scores based on on-chain activity.
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

logger = logging.getLogger("jarvis.verification.reputation")


# =============================================================================
# MODELS
# =============================================================================

class ReputationTier(Enum):
    """Reputation tiers"""
    NEWCOMER = "newcomer"      # 0-20
    BRONZE = "bronze"          # 21-40
    SILVER = "silver"          # 41-60
    GOLD = "gold"              # 61-80
    PLATINUM = "platinum"      # 81-95
    DIAMOND = "diamond"        # 96-100


@dataclass
class ReputationFactor:
    """A single factor contributing to reputation"""
    name: str
    score: float  # 0-100
    weight: float  # Contribution weight
    details: str


@dataclass
class ReputationScore:
    """Complete reputation score for a wallet"""
    wallet: str
    total_score: float  # 0-100
    tier: ReputationTier
    factors: List[ReputationFactor]
    history_trend: str  # "rising", "stable", "falling"
    calculated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class ReputationHistory:
    """Historical reputation data"""
    wallet: str
    score: float
    tier: ReputationTier
    recorded_at: datetime


# =============================================================================
# REPUTATION SCORER
# =============================================================================

class ReputationScorer:
    """
    Calculates on-chain reputation scores.

    Factors:
    - Wallet age and consistency
    - Transaction volume and frequency
    - DeFi participation
    - NFT activity
    - Trading performance (if JARVIS user)
    - Community participation
    """

    # Factor weights (must sum to 1.0)
    WEIGHTS = {
        "age": 0.15,
        "balance": 0.10,
        "activity": 0.20,
        "defi": 0.15,
        "trading": 0.25,
        "community": 0.15,
    }

    def __init__(self, db_path: str = None):
        self.db_path = db_path or os.getenv(
            "REPUTATION_DB",
            "data/reputation.db"
        )

        self._init_database()

    def _init_database(self):
        """Initialize reputation database"""
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Current reputation scores
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS reputation_scores (
                wallet TEXT PRIMARY KEY,
                total_score REAL NOT NULL,
                tier TEXT NOT NULL,
                factors_json TEXT,
                history_trend TEXT,
                calculated_at TEXT NOT NULL
            )
        """)

        # Historical scores
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS reputation_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                wallet TEXT NOT NULL,
                score REAL NOT NULL,
                tier TEXT NOT NULL,
                recorded_at TEXT NOT NULL
            )
        """)

        # Activity records
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS wallet_activity (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                wallet TEXT NOT NULL,
                activity_type TEXT NOT NULL,
                score_impact REAL,
                details_json TEXT,
                recorded_at TEXT NOT NULL
            )
        """)

        # Indexes
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_history_wallet
            ON reputation_history(wallet)
        """)

        conn.commit()
        conn.close()

    # =========================================================================
    # SCORING
    # =========================================================================

    async def calculate_score(
        self,
        wallet: str,
        wallet_profile: Dict[str, Any] = None,
        trading_stats: Dict[str, Any] = None,
    ) -> ReputationScore:
        """
        Calculate reputation score for a wallet.

        Args:
            wallet: Wallet address
            wallet_profile: Pre-fetched wallet profile data
            trading_stats: Trading statistics if JARVIS user

        Returns:
            ReputationScore with all factors
        """
        factors = []

        # Age factor
        age_score = self._calculate_age_score(wallet_profile)
        factors.append(ReputationFactor(
            name="age",
            score=age_score,
            weight=self.WEIGHTS["age"],
            details=f"Wallet age contributes {age_score:.0f} points",
        ))

        # Balance factor
        balance_score = self._calculate_balance_score(wallet_profile)
        factors.append(ReputationFactor(
            name="balance",
            score=balance_score,
            weight=self.WEIGHTS["balance"],
            details=f"Balance history contributes {balance_score:.0f} points",
        ))

        # Activity factor
        activity_score = self._calculate_activity_score(wallet_profile)
        factors.append(ReputationFactor(
            name="activity",
            score=activity_score,
            weight=self.WEIGHTS["activity"],
            details=f"On-chain activity contributes {activity_score:.0f} points",
        ))

        # DeFi factor
        defi_score = self._calculate_defi_score(wallet_profile)
        factors.append(ReputationFactor(
            name="defi",
            score=defi_score,
            weight=self.WEIGHTS["defi"],
            details=f"DeFi participation contributes {defi_score:.0f} points",
        ))

        # Trading factor (JARVIS-specific)
        trading_score = self._calculate_trading_score(trading_stats)
        factors.append(ReputationFactor(
            name="trading",
            score=trading_score,
            weight=self.WEIGHTS["trading"],
            details=f"Trading performance contributes {trading_score:.0f} points",
        ))

        # Community factor
        community_score = await self._calculate_community_score(wallet)
        factors.append(ReputationFactor(
            name="community",
            score=community_score,
            weight=self.WEIGHTS["community"],
            details=f"Community engagement contributes {community_score:.0f} points",
        ))

        # Calculate weighted total
        total_score = sum(f.score * f.weight for f in factors)

        # Determine tier
        tier = self._get_tier(total_score)

        # Get trend
        trend = await self._get_trend(wallet, total_score)

        score = ReputationScore(
            wallet=wallet,
            total_score=total_score,
            tier=tier,
            factors=factors,
            history_trend=trend,
        )

        # Save score
        await self._save_score(score)

        return score

    # =========================================================================
    # FACTOR CALCULATIONS
    # =========================================================================

    def _calculate_age_score(self, profile: Dict[str, Any]) -> float:
        """Calculate score based on wallet age"""
        if not profile:
            return 0

        age_days = profile.get("age_days", 0)

        # Logarithmic scaling: 1 year = 50, 2 years = 70, 3 years = 85
        if age_days <= 0:
            return 0
        elif age_days < 30:
            return 10
        elif age_days < 90:
            return 20
        elif age_days < 180:
            return 35
        elif age_days < 365:
            return 50
        else:
            # Logarithmic bonus for older wallets
            years = age_days / 365
            return min(50 + 25 * math.log2(years + 1), 100)

    def _calculate_balance_score(self, profile: Dict[str, Any]) -> float:
        """Calculate score based on balance"""
        if not profile:
            return 0

        balance = profile.get("balance_sol", 0)

        # Tiered scoring
        if balance < 0.01:
            return 0
        elif balance < 0.1:
            return 20
        elif balance < 1.0:
            return 40
        elif balance < 10.0:
            return 60
        elif balance < 100.0:
            return 80
        else:
            return 100

    def _calculate_activity_score(self, profile: Dict[str, Any]) -> float:
        """Calculate score based on transaction activity"""
        if not profile:
            return 0

        tx_count = profile.get("transaction_count", 0)
        programs = profile.get("unique_programs", 0)

        # Transaction score (logarithmic)
        if tx_count <= 0:
            tx_score = 0
        else:
            tx_score = min(25 * math.log10(tx_count + 1), 50)

        # Program diversity score
        program_score = min(programs * 5, 50)

        return tx_score + program_score

    def _calculate_defi_score(self, profile: Dict[str, Any]) -> float:
        """Calculate score based on DeFi activity"""
        if not profile:
            return 0

        score = 0

        # DeFi participation
        if profile.get("defi_activity"):
            score += 40

        # Known DeFi programs
        programs = profile.get("unique_programs", 0)
        if programs >= 5:
            score += 30
        elif programs >= 3:
            score += 20
        elif programs >= 1:
            score += 10

        # NFT holdings (indicates ecosystem participation)
        nft_count = profile.get("nft_count", 0)
        if nft_count > 0:
            score += min(nft_count * 2, 30)

        return min(score, 100)

    def _calculate_trading_score(self, stats: Dict[str, Any]) -> float:
        """Calculate score based on JARVIS trading performance"""
        if not stats:
            return 50  # Neutral if no trading history

        score = 50  # Base score

        # Win rate adjustment
        win_rate = stats.get("win_rate", 0.5)
        if win_rate > 0.6:
            score += 20
        elif win_rate > 0.5:
            score += 10
        elif win_rate < 0.4:
            score -= 10

        # Profitability
        total_pnl = stats.get("total_pnl_pct", 0)
        if total_pnl > 50:
            score += 20
        elif total_pnl > 10:
            score += 10
        elif total_pnl < -20:
            score -= 10

        # Consistency
        trade_count = stats.get("trade_count", 0)
        if trade_count > 100:
            score += 10
        elif trade_count > 50:
            score += 5

        return max(0, min(score, 100))

    async def _calculate_community_score(self, wallet: str) -> float:
        """Calculate score based on community participation"""
        # Check for community activities
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT COUNT(*), SUM(score_impact)
            FROM wallet_activity
            WHERE wallet = ? AND activity_type IN (
                'referral', 'governance_vote', 'data_contribution', 'staking'
            )
        """, (wallet,))

        row = cursor.fetchone()
        conn.close()

        if row[0] == 0:
            return 30  # Base community score

        activity_count = row[0]
        impact_sum = row[1] or 0

        # Score based on participation
        score = 30 + min(activity_count * 5, 35) + min(impact_sum, 35)

        return min(score, 100)

    # =========================================================================
    # HELPERS
    # =========================================================================

    def _get_tier(self, score: float) -> ReputationTier:
        """Get tier from score"""
        if score >= 96:
            return ReputationTier.DIAMOND
        elif score >= 81:
            return ReputationTier.PLATINUM
        elif score >= 61:
            return ReputationTier.GOLD
        elif score >= 41:
            return ReputationTier.SILVER
        elif score >= 21:
            return ReputationTier.BRONZE
        else:
            return ReputationTier.NEWCOMER

    async def _get_trend(self, wallet: str, current_score: float) -> str:
        """Calculate score trend"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Get score from 30 days ago
        thirty_days_ago = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()

        cursor.execute("""
            SELECT score FROM reputation_history
            WHERE wallet = ? AND recorded_at >= ?
            ORDER BY recorded_at ASC
            LIMIT 1
        """, (wallet, thirty_days_ago))

        row = cursor.fetchone()
        conn.close()

        if row is None:
            return "stable"

        old_score = row[0]
        diff = current_score - old_score

        if diff > 5:
            return "rising"
        elif diff < -5:
            return "falling"
        else:
            return "stable"

    # =========================================================================
    # ACTIVITY TRACKING
    # =========================================================================

    async def record_activity(
        self,
        wallet: str,
        activity_type: str,
        score_impact: float = 0,
        details: Dict[str, Any] = None,
    ):
        """Record an activity that affects reputation"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO wallet_activity
            (wallet, activity_type, score_impact, details_json, recorded_at)
            VALUES (?, ?, ?, ?, ?)
        """, (
            wallet,
            activity_type,
            score_impact,
            json.dumps(details) if details else None,
            datetime.now(timezone.utc).isoformat(),
        ))

        conn.commit()
        conn.close()

    # =========================================================================
    # PERSISTENCE
    # =========================================================================

    async def _save_score(self, score: ReputationScore):
        """Save reputation score"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Save current score
        cursor.execute("""
            INSERT OR REPLACE INTO reputation_scores
            (wallet, total_score, tier, factors_json, history_trend, calculated_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            score.wallet,
            score.total_score,
            score.tier.value,
            json.dumps([
                {
                    "name": f.name,
                    "score": f.score,
                    "weight": f.weight,
                    "details": f.details,
                }
                for f in score.factors
            ]),
            score.history_trend,
            score.calculated_at.isoformat(),
        ))

        # Add to history
        cursor.execute("""
            INSERT INTO reputation_history
            (wallet, score, tier, recorded_at)
            VALUES (?, ?, ?, ?)
        """, (
            score.wallet,
            score.total_score,
            score.tier.value,
            score.calculated_at.isoformat(),
        ))

        conn.commit()
        conn.close()

    async def get_score(self, wallet: str) -> Optional[ReputationScore]:
        """Get current reputation score"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            "SELECT * FROM reputation_scores WHERE wallet = ?",
            (wallet,)
        )

        row = cursor.fetchone()
        conn.close()

        if row is None:
            return None

        factors_data = json.loads(row[3]) if row[3] else []
        factors = [
            ReputationFactor(
                name=f["name"],
                score=f["score"],
                weight=f["weight"],
                details=f["details"],
            )
            for f in factors_data
        ]

        return ReputationScore(
            wallet=row[0],
            total_score=row[1],
            tier=ReputationTier(row[2]),
            factors=factors,
            history_trend=row[4],
            calculated_at=datetime.fromisoformat(row[5]),
        )

    async def get_history(
        self,
        wallet: str,
        days: int = 90,
    ) -> List[ReputationHistory]:
        """Get reputation history"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()

        cursor.execute("""
            SELECT wallet, score, tier, recorded_at
            FROM reputation_history
            WHERE wallet = ? AND recorded_at >= ?
            ORDER BY recorded_at ASC
        """, (wallet, since))

        history = [
            ReputationHistory(
                wallet=row[0],
                score=row[1],
                tier=ReputationTier(row[2]),
                recorded_at=datetime.fromisoformat(row[3]),
            )
            for row in cursor.fetchall()
        ]

        conn.close()
        return history

    async def get_leaderboard(self, limit: int = 100) -> List[ReputationScore]:
        """Get top wallets by reputation"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT * FROM reputation_scores
            ORDER BY total_score DESC
            LIMIT ?
        """, (limit,))

        scores = []
        for row in cursor.fetchall():
            factors_data = json.loads(row[3]) if row[3] else []
            factors = [
                ReputationFactor(
                    name=f["name"],
                    score=f["score"],
                    weight=f["weight"],
                    details=f["details"],
                )
                for f in factors_data
            ]

            scores.append(ReputationScore(
                wallet=row[0],
                total_score=row[1],
                tier=ReputationTier(row[2]),
                factors=factors,
                history_trend=row[4],
                calculated_at=datetime.fromisoformat(row[5]),
            ))

        conn.close()
        return scores


# =============================================================================
# SINGLETON
# =============================================================================

_scorer: Optional[ReputationScorer] = None


def get_reputation_scorer() -> ReputationScorer:
    """Get or create the reputation scorer singleton"""
    global _scorer
    if _scorer is None:
        _scorer = ReputationScorer()
    return _scorer
