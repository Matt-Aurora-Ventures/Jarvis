"""
Copy Trading Leader Management

Manages traders who share their strategies for others to copy.
Includes verification, performance tracking, and tier management.

Prompts #103-106: Copy Trading Service
"""

import asyncio
import logging
import json
import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Any
from enum import Enum
from pathlib import Path

logger = logging.getLogger(__name__)


class LeaderTier(str, Enum):
    """Leader tier based on performance and verification"""
    UNVERIFIED = "unverified"
    BRONZE = "bronze"
    SILVER = "silver"
    GOLD = "gold"
    PLATINUM = "platinum"
    DIAMOND = "diamond"


@dataclass
class LeaderStats:
    """Performance statistics for a copy trading leader"""
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    total_pnl: float = 0.0
    total_pnl_percent: float = 0.0
    max_drawdown: float = 0.0
    win_rate: float = 0.0
    avg_profit_per_trade: float = 0.0
    avg_loss_per_trade: float = 0.0
    profit_factor: float = 0.0
    sharpe_ratio: float = 0.0
    best_trade: float = 0.0
    worst_trade: float = 0.0
    avg_trade_duration_hours: float = 0.0
    follower_count: int = 0
    total_copied_volume: float = 0.0

    # Time-based stats
    pnl_7d: float = 0.0
    pnl_30d: float = 0.0
    pnl_90d: float = 0.0
    pnl_all_time: float = 0.0

    last_updated: datetime = field(default_factory=datetime.now)

    def calculate_derived_stats(self):
        """Calculate derived statistics"""
        if self.total_trades > 0:
            self.win_rate = (self.winning_trades / self.total_trades) * 100

        if self.losing_trades > 0 and self.winning_trades > 0:
            avg_win = self.total_pnl / self.winning_trades if self.total_pnl > 0 else 0
            avg_loss = abs(self.total_pnl) / self.losing_trades if self.total_pnl < 0 else 0
            if avg_loss > 0:
                self.profit_factor = avg_win / avg_loss

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "total_trades": self.total_trades,
            "winning_trades": self.winning_trades,
            "losing_trades": self.losing_trades,
            "total_pnl": self.total_pnl,
            "total_pnl_percent": self.total_pnl_percent,
            "max_drawdown": self.max_drawdown,
            "win_rate": self.win_rate,
            "avg_profit_per_trade": self.avg_profit_per_trade,
            "avg_loss_per_trade": self.avg_loss_per_trade,
            "profit_factor": self.profit_factor,
            "sharpe_ratio": self.sharpe_ratio,
            "best_trade": self.best_trade,
            "worst_trade": self.worst_trade,
            "avg_trade_duration_hours": self.avg_trade_duration_hours,
            "follower_count": self.follower_count,
            "total_copied_volume": self.total_copied_volume,
            "pnl_7d": self.pnl_7d,
            "pnl_30d": self.pnl_30d,
            "pnl_90d": self.pnl_90d,
            "pnl_all_time": self.pnl_all_time,
            "last_updated": self.last_updated.isoformat()
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "LeaderStats":
        """Create from dictionary"""
        return cls(
            total_trades=data.get("total_trades", 0),
            winning_trades=data.get("winning_trades", 0),
            losing_trades=data.get("losing_trades", 0),
            total_pnl=data.get("total_pnl", 0.0),
            total_pnl_percent=data.get("total_pnl_percent", 0.0),
            max_drawdown=data.get("max_drawdown", 0.0),
            win_rate=data.get("win_rate", 0.0),
            avg_profit_per_trade=data.get("avg_profit_per_trade", 0.0),
            avg_loss_per_trade=data.get("avg_loss_per_trade", 0.0),
            profit_factor=data.get("profit_factor", 0.0),
            sharpe_ratio=data.get("sharpe_ratio", 0.0),
            best_trade=data.get("best_trade", 0.0),
            worst_trade=data.get("worst_trade", 0.0),
            avg_trade_duration_hours=data.get("avg_trade_duration_hours", 0.0),
            follower_count=data.get("follower_count", 0),
            total_copied_volume=data.get("total_copied_volume", 0.0),
            pnl_7d=data.get("pnl_7d", 0.0),
            pnl_30d=data.get("pnl_30d", 0.0),
            pnl_90d=data.get("pnl_90d", 0.0),
            pnl_all_time=data.get("pnl_all_time", 0.0),
            last_updated=datetime.fromisoformat(data["last_updated"]) if data.get("last_updated") else datetime.now()
        )


@dataclass
class Leader:
    """A copy trading leader"""
    leader_id: str
    wallet: str
    display_name: str
    tier: LeaderTier = LeaderTier.UNVERIFIED
    stats: LeaderStats = field(default_factory=LeaderStats)

    # Settings
    is_public: bool = True
    accepting_followers: bool = True
    max_followers: int = 100
    min_copy_amount: float = 10.0  # Minimum USD to copy
    profit_share_percent: float = 10.0  # Leader takes 10% of follower profits

    # Metadata
    bio: str = ""
    twitter_handle: Optional[str] = None
    verified_at: Optional[datetime] = None
    created_at: datetime = field(default_factory=datetime.now)
    last_active: datetime = field(default_factory=datetime.now)

    def __post_init__(self):
        if not self.leader_id:
            data = f"{self.wallet}{self.created_at.isoformat()}"
            self.leader_id = f"LEADER-{hashlib.sha256(data.encode()).hexdigest()[:8].upper()}"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "leader_id": self.leader_id,
            "wallet": self.wallet,
            "display_name": self.display_name,
            "tier": self.tier.value,
            "stats": self.stats.to_dict(),
            "is_public": self.is_public,
            "accepting_followers": self.accepting_followers,
            "max_followers": self.max_followers,
            "min_copy_amount": self.min_copy_amount,
            "profit_share_percent": self.profit_share_percent,
            "bio": self.bio,
            "twitter_handle": self.twitter_handle,
            "verified_at": self.verified_at.isoformat() if self.verified_at else None,
            "created_at": self.created_at.isoformat(),
            "last_active": self.last_active.isoformat()
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Leader":
        """Create from dictionary"""
        return cls(
            leader_id=data["leader_id"],
            wallet=data["wallet"],
            display_name=data["display_name"],
            tier=LeaderTier(data.get("tier", "unverified")),
            stats=LeaderStats.from_dict(data.get("stats", {})),
            is_public=data.get("is_public", True),
            accepting_followers=data.get("accepting_followers", True),
            max_followers=data.get("max_followers", 100),
            min_copy_amount=data.get("min_copy_amount", 10.0),
            profit_share_percent=data.get("profit_share_percent", 10.0),
            bio=data.get("bio", ""),
            twitter_handle=data.get("twitter_handle"),
            verified_at=datetime.fromisoformat(data["verified_at"]) if data.get("verified_at") else None,
            created_at=datetime.fromisoformat(data["created_at"]) if data.get("created_at") else datetime.now(),
            last_active=datetime.fromisoformat(data["last_active"]) if data.get("last_active") else datetime.now()
        )

    def can_accept_followers(self) -> bool:
        """Check if leader can accept new followers"""
        return (
            self.accepting_followers and
            self.stats.follower_count < self.max_followers
        )

    def get_tier_badge(self) -> str:
        """Get emoji badge for tier"""
        badges = {
            LeaderTier.UNVERIFIED: "⚪",
            LeaderTier.BRONZE: "🥉",
            LeaderTier.SILVER: "🥈",
            LeaderTier.GOLD: "🥇",
            LeaderTier.PLATINUM: "💎",
            LeaderTier.DIAMOND: "👑"
        }
        return badges.get(self.tier, "⚪")


# Tier requirements
TIER_REQUIREMENTS = {
    LeaderTier.BRONZE: {
        "min_trades": 10,
        "min_win_rate": 40,
        "min_pnl_percent": 0,
        "min_days_active": 7
    },
    LeaderTier.SILVER: {
        "min_trades": 50,
        "min_win_rate": 50,
        "min_pnl_percent": 10,
        "min_days_active": 30
    },
    LeaderTier.GOLD: {
        "min_trades": 100,
        "min_win_rate": 55,
        "min_pnl_percent": 25,
        "min_days_active": 60
    },
    LeaderTier.PLATINUM: {
        "min_trades": 250,
        "min_win_rate": 60,
        "min_pnl_percent": 50,
        "min_days_active": 90
    },
    LeaderTier.DIAMOND: {
        "min_trades": 500,
        "min_win_rate": 65,
        "min_pnl_percent": 100,
        "min_days_active": 180
    }
}


class LeaderManager:
    """
    Manages copy trading leaders

    Handles registration, verification, and performance tracking.
    """

    def __init__(self, storage_path: str = "data/copy_trading/leaders.json"):
        self.storage_path = Path(storage_path)
        self.leaders: Dict[str, Leader] = {}
        self.leaders_by_wallet: Dict[str, str] = {}  # wallet -> leader_id
        self._load()

    def _load(self):
        """Load leaders from storage"""
        if not self.storage_path.exists():
            return

        try:
            with open(self.storage_path) as f:
                data = json.load(f)

            for leader_data in data.get("leaders", []):
                leader = Leader.from_dict(leader_data)
                self.leaders[leader.leader_id] = leader
                self.leaders_by_wallet[leader.wallet] = leader.leader_id

            logger.info(f"Loaded {len(self.leaders)} leaders")

        except Exception as e:
            logger.error(f"Failed to load leaders: {e}")

    def _save(self):
        """Save leaders to storage"""
        try:
            self.storage_path.parent.mkdir(parents=True, exist_ok=True)

            data = {
                "leaders": [l.to_dict() for l in self.leaders.values()],
                "updated_at": datetime.now().isoformat()
            }

            with open(self.storage_path, "w") as f:
                json.dump(data, f, indent=2)

        except Exception as e:
            logger.error(f"Failed to save leaders: {e}")
            raise

    async def register_leader(
        self,
        wallet: str,
        display_name: str,
        bio: str = "",
        twitter_handle: Optional[str] = None
    ) -> Optional[Leader]:
        """Register a new copy trading leader"""
        # Check if wallet already registered
        if wallet in self.leaders_by_wallet:
            logger.warning(f"Wallet {wallet} already registered as leader")
            return None

        leader = Leader(
            leader_id="",  # Will be generated
            wallet=wallet,
            display_name=display_name,
            bio=bio,
            twitter_handle=twitter_handle
        )

        self.leaders[leader.leader_id] = leader
        self.leaders_by_wallet[wallet] = leader.leader_id
        self._save()

        logger.info(f"Registered new leader: {leader.leader_id} ({display_name})")
        return leader

    async def get_leader(self, leader_id: str) -> Optional[Leader]:
        """Get a leader by ID"""
        return self.leaders.get(leader_id)

    async def get_leader_by_wallet(self, wallet: str) -> Optional[Leader]:
        """Get a leader by wallet address"""
        leader_id = self.leaders_by_wallet.get(wallet)
        if leader_id:
            return self.leaders.get(leader_id)
        return None

    async def update_stats(self, leader_id: str, stats: LeaderStats):
        """Update leader statistics"""
        leader = self.leaders.get(leader_id)
        if not leader:
            return

        leader.stats = stats
        leader.last_active = datetime.now()

        # Check for tier upgrade
        new_tier = self._calculate_tier(leader)
        if new_tier != leader.tier:
            old_tier = leader.tier
            leader.tier = new_tier
            logger.info(f"Leader {leader_id} upgraded from {old_tier.value} to {new_tier.value}")

        self._save()

    def _calculate_tier(self, leader: Leader) -> LeaderTier:
        """Calculate tier based on stats"""
        days_active = (datetime.now() - leader.created_at).days

        for tier in [LeaderTier.DIAMOND, LeaderTier.PLATINUM, LeaderTier.GOLD, LeaderTier.SILVER, LeaderTier.BRONZE]:
            reqs = TIER_REQUIREMENTS[tier]

            if (leader.stats.total_trades >= reqs["min_trades"] and
                leader.stats.win_rate >= reqs["min_win_rate"] and
                leader.stats.total_pnl_percent >= reqs["min_pnl_percent"] and
                days_active >= reqs["min_days_active"]):
                return tier

        return LeaderTier.UNVERIFIED

    async def verify_leader(self, leader_id: str) -> bool:
        """Mark a leader as verified"""
        leader = self.leaders.get(leader_id)
        if not leader:
            return False

        leader.verified_at = datetime.now()
        if leader.tier == LeaderTier.UNVERIFIED:
            leader.tier = LeaderTier.BRONZE

        self._save()
        logger.info(f"Leader {leader_id} verified")
        return True

    async def list_leaders(
        self,
        tier: Optional[LeaderTier] = None,
        public_only: bool = True,
        accepting_followers: bool = True,
        sort_by: str = "pnl_30d",
        limit: int = 50
    ) -> List[Leader]:
        """List leaders with filters"""
        leaders = list(self.leaders.values())

        if public_only:
            leaders = [l for l in leaders if l.is_public]

        if accepting_followers:
            leaders = [l for l in leaders if l.can_accept_followers()]

        if tier:
            leaders = [l for l in leaders if l.tier == tier]

        # Sort
        sort_keys = {
            "pnl_30d": lambda l: l.stats.pnl_30d,
            "win_rate": lambda l: l.stats.win_rate,
            "followers": lambda l: l.stats.follower_count,
            "total_trades": lambda l: l.stats.total_trades,
            "profit_factor": lambda l: l.stats.profit_factor
        }

        sort_fn = sort_keys.get(sort_by, lambda l: l.stats.pnl_30d)
        leaders.sort(key=sort_fn, reverse=True)

        return leaders[:limit]

    async def record_trade(
        self,
        leader_id: str,
        pnl: float,
        pnl_percent: float,
        duration_hours: float = 0
    ):
        """Record a completed trade for a leader"""
        leader = self.leaders.get(leader_id)
        if not leader:
            return

        leader.stats.total_trades += 1
        leader.stats.total_pnl += pnl
        leader.stats.pnl_all_time += pnl

        if pnl > 0:
            leader.stats.winning_trades += 1
            leader.stats.best_trade = max(leader.stats.best_trade, pnl)
        else:
            leader.stats.losing_trades += 1
            leader.stats.worst_trade = min(leader.stats.worst_trade, pnl)

        leader.stats.calculate_derived_stats()
        leader.last_active = datetime.now()

        self._save()

    async def add_follower(self, leader_id: str):
        """Increment follower count"""
        leader = self.leaders.get(leader_id)
        if leader:
            leader.stats.follower_count += 1
            self._save()

    async def remove_follower(self, leader_id: str):
        """Decrement follower count"""
        leader = self.leaders.get(leader_id)
        if leader and leader.stats.follower_count > 0:
            leader.stats.follower_count -= 1
            self._save()

    def get_leaderboard(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get top leaders leaderboard"""
        leaders = sorted(
            self.leaders.values(),
            key=lambda l: l.stats.pnl_30d,
            reverse=True
        )[:limit]

        return [
            {
                "rank": i + 1,
                "leader_id": l.leader_id,
                "display_name": l.display_name,
                "badge": l.get_tier_badge(),
                "tier": l.tier.value,
                "pnl_30d": f"{l.stats.pnl_30d:+.2f}%",
                "win_rate": f"{l.stats.win_rate:.1f}%",
                "followers": l.stats.follower_count
            }
            for i, l in enumerate(leaders)
        ]


# Singleton instance
_leader_manager: Optional[LeaderManager] = None


def get_leader_manager() -> LeaderManager:
    """Get leader manager singleton"""
    global _leader_manager

    if _leader_manager is None:
        _leader_manager = LeaderManager()

    return _leader_manager


# Testing
if __name__ == "__main__":
    async def test():
        manager = LeaderManager("test_leaders.json")

        # Register a leader
        leader = await manager.register_leader(
            wallet="LEADER_WALLET_123",
            display_name="CryptoKing",
            bio="Professional trader with 5 years experience",
            twitter_handle="@cryptoking"
        )
        print(f"Registered: {leader.leader_id}")

        # Record some trades
        for i in range(15):
            pnl = 100 if i % 3 != 0 else -50
            await manager.record_trade(leader.leader_id, pnl, pnl / 10)

        # Get updated leader
        leader = await manager.get_leader(leader.leader_id)
        print(f"Stats: {leader.stats.total_trades} trades, {leader.stats.win_rate:.1f}% win rate")
        print(f"Tier: {leader.tier.value} {leader.get_tier_badge()}")

        # Leaderboard
        print("\nLeaderboard:")
        for entry in manager.get_leaderboard():
            print(f"  {entry['rank']}. {entry['badge']} {entry['display_name']} - {entry['pnl_30d']}")

        # Clean up
        import os
        os.remove("test_leaders.json")

    asyncio.run(test())
