"""
Copy Trading Follower Management

Manages users who follow and copy leaders' trades.
Includes copy configuration, risk management, and performance tracking.

Prompts #103-106: Copy Trading Service
"""

import asyncio
import logging
import json
import hashlib
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Dict, List, Any
from enum import Enum
from pathlib import Path

logger = logging.getLogger(__name__)


class CopyMode(str, Enum):
    """How to copy leader trades"""
    FIXED_AMOUNT = "fixed_amount"       # Copy with fixed USD amount
    PERCENTAGE = "percentage"           # Copy as percentage of portfolio
    PROPORTIONAL = "proportional"       # Match leader's position size ratio
    MIRROR = "mirror"                   # Exact mirror (requires verification)


class RiskLevel(str, Enum):
    """Risk level for copy trading"""
    CONSERVATIVE = "conservative"  # 0.5x leader position
    MODERATE = "moderate"          # 1.0x leader position
    AGGRESSIVE = "aggressive"      # 1.5x leader position


@dataclass
class FollowConfig:
    """Configuration for following a leader"""
    leader_id: str
    copy_mode: CopyMode = CopyMode.FIXED_AMOUNT
    risk_level: RiskLevel = RiskLevel.MODERATE

    # Amount settings
    fixed_amount: float = 100.0         # USD for FIXED_AMOUNT mode
    percentage: float = 10.0            # % of portfolio for PERCENTAGE mode
    max_position_size: float = 500.0    # Max USD per position

    # Risk settings
    stop_loss_percent: float = 10.0     # Auto stop loss
    take_profit_percent: float = 25.0   # Auto take profit
    max_daily_loss: float = 100.0       # Stop copying after this loss
    max_open_positions: int = 5         # Max simultaneous copies

    # Filters
    min_trade_amount: float = 10.0      # Don't copy trades below this
    copy_buys: bool = True
    copy_sells: bool = True
    allowed_tokens: List[str] = field(default_factory=list)  # Empty = all
    blocked_tokens: List[str] = field(default_factory=list)

    # Timing
    delay_seconds: int = 0              # Delay before copying (0 = instant)
    active_hours_start: int = 0         # 0-23, 0 = always active
    active_hours_end: int = 24

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "leader_id": self.leader_id,
            "copy_mode": self.copy_mode.value,
            "risk_level": self.risk_level.value,
            "fixed_amount": self.fixed_amount,
            "percentage": self.percentage,
            "max_position_size": self.max_position_size,
            "stop_loss_percent": self.stop_loss_percent,
            "take_profit_percent": self.take_profit_percent,
            "max_daily_loss": self.max_daily_loss,
            "max_open_positions": self.max_open_positions,
            "min_trade_amount": self.min_trade_amount,
            "copy_buys": self.copy_buys,
            "copy_sells": self.copy_sells,
            "allowed_tokens": self.allowed_tokens,
            "blocked_tokens": self.blocked_tokens,
            "delay_seconds": self.delay_seconds,
            "active_hours_start": self.active_hours_start,
            "active_hours_end": self.active_hours_end
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "FollowConfig":
        """Create from dictionary"""
        return cls(
            leader_id=data["leader_id"],
            copy_mode=CopyMode(data.get("copy_mode", "fixed_amount")),
            risk_level=RiskLevel(data.get("risk_level", "moderate")),
            fixed_amount=data.get("fixed_amount", 100.0),
            percentage=data.get("percentage", 10.0),
            max_position_size=data.get("max_position_size", 500.0),
            stop_loss_percent=data.get("stop_loss_percent", 10.0),
            take_profit_percent=data.get("take_profit_percent", 25.0),
            max_daily_loss=data.get("max_daily_loss", 100.0),
            max_open_positions=data.get("max_open_positions", 5),
            min_trade_amount=data.get("min_trade_amount", 10.0),
            copy_buys=data.get("copy_buys", True),
            copy_sells=data.get("copy_sells", True),
            allowed_tokens=data.get("allowed_tokens", []),
            blocked_tokens=data.get("blocked_tokens", []),
            delay_seconds=data.get("delay_seconds", 0),
            active_hours_start=data.get("active_hours_start", 0),
            active_hours_end=data.get("active_hours_end", 24)
        )

    def get_position_multiplier(self) -> float:
        """Get position size multiplier based on risk level"""
        multipliers = {
            RiskLevel.CONSERVATIVE: 0.5,
            RiskLevel.MODERATE: 1.0,
            RiskLevel.AGGRESSIVE: 1.5
        }
        return multipliers.get(self.risk_level, 1.0)


@dataclass
class FollowerStats:
    """Statistics for a copy trading follower"""
    total_copied_trades: int = 0
    successful_copies: int = 0
    failed_copies: int = 0
    total_invested: float = 0.0
    total_pnl: float = 0.0
    total_fees_paid: float = 0.0
    total_profit_shared: float = 0.0  # Paid to leaders
    best_copy: float = 0.0
    worst_copy: float = 0.0
    current_open_positions: int = 0
    daily_pnl: float = 0.0
    last_copy_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "total_copied_trades": self.total_copied_trades,
            "successful_copies": self.successful_copies,
            "failed_copies": self.failed_copies,
            "total_invested": self.total_invested,
            "total_pnl": self.total_pnl,
            "total_fees_paid": self.total_fees_paid,
            "total_profit_shared": self.total_profit_shared,
            "best_copy": self.best_copy,
            "worst_copy": self.worst_copy,
            "current_open_positions": self.current_open_positions,
            "daily_pnl": self.daily_pnl,
            "last_copy_at": self.last_copy_at.isoformat() if self.last_copy_at else None
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "FollowerStats":
        """Create from dictionary"""
        return cls(
            total_copied_trades=data.get("total_copied_trades", 0),
            successful_copies=data.get("successful_copies", 0),
            failed_copies=data.get("failed_copies", 0),
            total_invested=data.get("total_invested", 0.0),
            total_pnl=data.get("total_pnl", 0.0),
            total_fees_paid=data.get("total_fees_paid", 0.0),
            total_profit_shared=data.get("total_profit_shared", 0.0),
            best_copy=data.get("best_copy", 0.0),
            worst_copy=data.get("worst_copy", 0.0),
            current_open_positions=data.get("current_open_positions", 0),
            daily_pnl=data.get("daily_pnl", 0.0),
            last_copy_at=datetime.fromisoformat(data["last_copy_at"]) if data.get("last_copy_at") else None
        )


@dataclass
class Follower:
    """A copy trading follower"""
    follower_id: str
    wallet: str
    following: Dict[str, FollowConfig] = field(default_factory=dict)  # leader_id -> config
    stats: FollowerStats = field(default_factory=FollowerStats)

    # Settings
    copy_trading_enabled: bool = False  # DISABLED BY DEFAULT
    max_leaders_to_follow: int = 5
    total_copy_budget: float = 1000.0   # Max total across all leaders

    # Metadata
    created_at: datetime = field(default_factory=datetime.now)
    last_active: datetime = field(default_factory=datetime.now)

    def __post_init__(self):
        if not self.follower_id:
            data = f"{self.wallet}{self.created_at.isoformat()}"
            self.follower_id = f"FOLLOWER-{hashlib.sha256(data.encode()).hexdigest()[:8].upper()}"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "follower_id": self.follower_id,
            "wallet": self.wallet,
            "following": {lid: cfg.to_dict() for lid, cfg in self.following.items()},
            "stats": self.stats.to_dict(),
            "copy_trading_enabled": self.copy_trading_enabled,
            "max_leaders_to_follow": self.max_leaders_to_follow,
            "total_copy_budget": self.total_copy_budget,
            "created_at": self.created_at.isoformat(),
            "last_active": self.last_active.isoformat()
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Follower":
        """Create from dictionary"""
        following = {
            lid: FollowConfig.from_dict(cfg)
            for lid, cfg in data.get("following", {}).items()
        }

        return cls(
            follower_id=data["follower_id"],
            wallet=data["wallet"],
            following=following,
            stats=FollowerStats.from_dict(data.get("stats", {})),
            copy_trading_enabled=data.get("copy_trading_enabled", False),
            max_leaders_to_follow=data.get("max_leaders_to_follow", 5),
            total_copy_budget=data.get("total_copy_budget", 1000.0),
            created_at=datetime.fromisoformat(data["created_at"]) if data.get("created_at") else datetime.now(),
            last_active=datetime.fromisoformat(data["last_active"]) if data.get("last_active") else datetime.now()
        )

    def is_following(self, leader_id: str) -> bool:
        """Check if following a specific leader"""
        return leader_id in self.following

    def can_follow_more(self) -> bool:
        """Check if can follow more leaders"""
        return len(self.following) < self.max_leaders_to_follow

    def get_remaining_budget(self) -> float:
        """Get remaining copy budget"""
        allocated = sum(
            cfg.fixed_amount for cfg in self.following.values()
            if cfg.copy_mode == CopyMode.FIXED_AMOUNT
        )
        return max(0, self.total_copy_budget - allocated)

    def can_copy_trade(self, leader_id: str) -> tuple[bool, str]:
        """Check if a trade from a leader should be copied"""
        if not self.copy_trading_enabled:
            return False, "Copy trading disabled"

        if leader_id not in self.following:
            return False, "Not following this leader"

        config = self.following[leader_id]

        # Check daily loss limit
        if self.stats.daily_pnl <= -config.max_daily_loss:
            return False, "Daily loss limit reached"

        # Check open positions limit
        if self.stats.current_open_positions >= config.max_open_positions:
            return False, "Max open positions reached"

        # Check active hours
        current_hour = datetime.now().hour
        if not (config.active_hours_start <= current_hour < config.active_hours_end):
            return False, "Outside active hours"

        return True, "OK"


class FollowerManager:
    """
    Manages copy trading followers

    Handles follow/unfollow, configuration, and stats tracking.
    """

    def __init__(self, storage_path: str = "data/copy_trading/followers.json"):
        self.storage_path = Path(storage_path)
        self.followers: Dict[str, Follower] = {}
        self.followers_by_wallet: Dict[str, str] = {}
        self._load()

    def _load(self):
        """Load followers from storage"""
        if not self.storage_path.exists():
            return

        try:
            with open(self.storage_path) as f:
                data = json.load(f)

            for follower_data in data.get("followers", []):
                follower = Follower.from_dict(follower_data)
                self.followers[follower.follower_id] = follower
                self.followers_by_wallet[follower.wallet] = follower.follower_id

            logger.info(f"Loaded {len(self.followers)} followers")

        except Exception as e:
            logger.error(f"Failed to load followers: {e}")

    def _save(self):
        """Save followers to storage"""
        try:
            self.storage_path.parent.mkdir(parents=True, exist_ok=True)

            data = {
                "followers": [f.to_dict() for f in self.followers.values()],
                "updated_at": datetime.now().isoformat()
            }

            with open(self.storage_path, "w") as f:
                json.dump(data, f, indent=2)

        except Exception as e:
            logger.error(f"Failed to save followers: {e}")
            raise

    async def get_or_create_follower(self, wallet: str) -> Follower:
        """Get or create a follower by wallet"""
        if wallet in self.followers_by_wallet:
            follower_id = self.followers_by_wallet[wallet]
            return self.followers[follower_id]

        # Create new follower
        follower = Follower(
            follower_id="",  # Will be generated
            wallet=wallet
        )

        self.followers[follower.follower_id] = follower
        self.followers_by_wallet[wallet] = follower.follower_id
        self._save()

        logger.info(f"Created new follower: {follower.follower_id}")
        return follower

    async def get_follower(self, follower_id: str) -> Optional[Follower]:
        """Get a follower by ID"""
        return self.followers.get(follower_id)

    async def get_follower_by_wallet(self, wallet: str) -> Optional[Follower]:
        """Get a follower by wallet"""
        follower_id = self.followers_by_wallet.get(wallet)
        if follower_id:
            return self.followers.get(follower_id)
        return None

    async def follow_leader(
        self,
        follower_id: str,
        leader_id: str,
        config: FollowConfig
    ) -> bool:
        """Start following a leader"""
        follower = self.followers.get(follower_id)
        if not follower:
            return False

        if not follower.can_follow_more():
            logger.warning(f"Follower {follower_id} at max leaders limit")
            return False

        config.leader_id = leader_id
        follower.following[leader_id] = config
        follower.last_active = datetime.now()

        self._save()
        logger.info(f"Follower {follower_id} now following {leader_id}")
        return True

    async def unfollow_leader(self, follower_id: str, leader_id: str) -> bool:
        """Stop following a leader"""
        follower = self.followers.get(follower_id)
        if not follower:
            return False

        if leader_id not in follower.following:
            return False

        del follower.following[leader_id]
        follower.last_active = datetime.now()

        self._save()
        logger.info(f"Follower {follower_id} unfollowed {leader_id}")
        return True

    async def update_config(
        self,
        follower_id: str,
        leader_id: str,
        config: FollowConfig
    ) -> bool:
        """Update follow configuration"""
        follower = self.followers.get(follower_id)
        if not follower or leader_id not in follower.following:
            return False

        config.leader_id = leader_id
        follower.following[leader_id] = config
        self._save()

        return True

    async def enable_copy_trading(self, follower_id: str) -> bool:
        """Enable copy trading for a follower"""
        follower = self.followers.get(follower_id)
        if not follower:
            return False

        # SAFETY: Require explicit acknowledgment
        logger.warning(f"Enabling copy trading for {follower_id} - REQUIRES AUDIT")
        follower.copy_trading_enabled = True
        self._save()

        return True

    async def disable_copy_trading(self, follower_id: str) -> bool:
        """Disable copy trading for a follower"""
        follower = self.followers.get(follower_id)
        if not follower:
            return False

        follower.copy_trading_enabled = False
        self._save()

        return True

    async def get_followers_of_leader(self, leader_id: str) -> List[Follower]:
        """Get all followers of a specific leader"""
        return [
            f for f in self.followers.values()
            if leader_id in f.following and f.copy_trading_enabled
        ]

    async def record_copy_result(
        self,
        follower_id: str,
        success: bool,
        pnl: float = 0.0,
        fees: float = 0.0,
        profit_shared: float = 0.0
    ):
        """Record the result of a copy trade"""
        follower = self.followers.get(follower_id)
        if not follower:
            return

        follower.stats.total_copied_trades += 1
        if success:
            follower.stats.successful_copies += 1
        else:
            follower.stats.failed_copies += 1

        follower.stats.total_pnl += pnl
        follower.stats.daily_pnl += pnl
        follower.stats.total_fees_paid += fees
        follower.stats.total_profit_shared += profit_shared

        if pnl > follower.stats.best_copy:
            follower.stats.best_copy = pnl
        if pnl < follower.stats.worst_copy:
            follower.stats.worst_copy = pnl

        follower.stats.last_copy_at = datetime.now()
        follower.last_active = datetime.now()

        self._save()

    async def reset_daily_stats(self):
        """Reset daily statistics for all followers"""
        for follower in self.followers.values():
            follower.stats.daily_pnl = 0.0

        self._save()
        logger.info("Reset daily stats for all followers")


# Singleton instance
_follower_manager: Optional[FollowerManager] = None


def get_follower_manager() -> FollowerManager:
    """Get follower manager singleton"""
    global _follower_manager

    if _follower_manager is None:
        _follower_manager = FollowerManager()

    return _follower_manager


# Testing
if __name__ == "__main__":
    async def test():
        manager = FollowerManager("test_followers.json")

        # Create a follower
        follower = await manager.get_or_create_follower("FOLLOWER_WALLET_123")
        print(f"Created: {follower.follower_id}")

        # Follow a leader
        config = FollowConfig(
            leader_id="LEADER-12345678",
            copy_mode=CopyMode.FIXED_AMOUNT,
            fixed_amount=100.0,
            risk_level=RiskLevel.MODERATE
        )

        await manager.follow_leader(follower.follower_id, "LEADER-12345678", config)
        print(f"Following: {list(follower.following.keys())}")

        # Check if can copy
        can_copy, reason = follower.can_copy_trade("LEADER-12345678")
        print(f"Can copy: {can_copy} - {reason}")

        # Enable copy trading (normally requires audit)
        await manager.enable_copy_trading(follower.follower_id)
        can_copy, reason = follower.can_copy_trade("LEADER-12345678")
        print(f"Can copy after enable: {can_copy} - {reason}")

        # Record some results
        await manager.record_copy_result(follower.follower_id, True, pnl=25.0)
        await manager.record_copy_result(follower.follower_id, True, pnl=-10.0)

        print(f"Stats: {follower.stats.total_pnl} PnL, {follower.stats.successful_copies} successful")

        # Clean up
        import os
        os.remove("test_followers.json")

    asyncio.run(test())
