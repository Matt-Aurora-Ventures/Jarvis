"""
Strategy Marketplace

Trading strategy listings, subscriptions, and management.
Allows strategy creators to monetize their strategies.

Prompts #105-106: Strategy Marketplace
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


class StrategyCategory(str, Enum):
    """Strategy categories"""
    MOMENTUM = "momentum"
    MEAN_REVERSION = "mean_reversion"
    TREND_FOLLOWING = "trend_following"
    ARBITRAGE = "arbitrage"
    DCA = "dca"
    SWING_TRADING = "swing_trading"
    SCALPING = "scalping"
    WHALE_FOLLOWING = "whale_following"
    SENTIMENT = "sentiment"
    HYBRID = "hybrid"


class RiskLevel(str, Enum):
    """Strategy risk levels"""
    VERY_LOW = "very_low"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    VERY_HIGH = "very_high"


class ListingStatus(str, Enum):
    """Strategy listing status"""
    DRAFT = "draft"
    PENDING_REVIEW = "pending_review"
    ACTIVE = "active"
    SUSPENDED = "suspended"
    ARCHIVED = "archived"


@dataclass
class StrategyPerformance:
    """Strategy performance metrics"""
    total_return_pct: float = 0.0
    sharpe_ratio: float = 0.0
    max_drawdown_pct: float = 0.0
    win_rate: float = 0.0
    profit_factor: float = 0.0
    avg_trade_duration_hours: float = 0.0
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0

    # Time-based returns
    return_7d_pct: float = 0.0
    return_30d_pct: float = 0.0
    return_90d_pct: float = 0.0
    return_ytd_pct: float = 0.0

    # Risk metrics
    volatility: float = 0.0
    sortino_ratio: float = 0.0
    calmar_ratio: float = 0.0

    last_updated: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "total_return_pct": self.total_return_pct,
            "sharpe_ratio": self.sharpe_ratio,
            "max_drawdown_pct": self.max_drawdown_pct,
            "win_rate": self.win_rate,
            "profit_factor": self.profit_factor,
            "avg_trade_duration_hours": self.avg_trade_duration_hours,
            "total_trades": self.total_trades,
            "winning_trades": self.winning_trades,
            "losing_trades": self.losing_trades,
            "return_7d_pct": self.return_7d_pct,
            "return_30d_pct": self.return_30d_pct,
            "return_90d_pct": self.return_90d_pct,
            "return_ytd_pct": self.return_ytd_pct,
            "volatility": self.volatility,
            "sortino_ratio": self.sortino_ratio,
            "calmar_ratio": self.calmar_ratio,
            "last_updated": self.last_updated.isoformat()
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "StrategyPerformance":
        """Create from dictionary"""
        return cls(
            **{k: v for k, v in data.items()
               if k != "last_updated" and hasattr(cls, k)},
            last_updated=datetime.fromisoformat(data["last_updated"]) if data.get("last_updated") else datetime.now()
        )


@dataclass
class Strategy:
    """A trading strategy"""
    strategy_id: str
    creator_id: str
    name: str
    description: str
    category: StrategyCategory
    risk_level: RiskLevel

    # Configuration
    parameters: Dict[str, Any] = field(default_factory=dict)
    supported_tokens: List[str] = field(default_factory=list)
    min_capital: float = 100.0

    # Performance
    performance: StrategyPerformance = field(default_factory=StrategyPerformance)

    # Metadata
    version: str = "1.0.0"
    tags: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def __post_init__(self):
        if not self.strategy_id:
            data = f"{self.creator_id}{self.name}{self.created_at.isoformat()}"
            self.strategy_id = f"STRAT-{hashlib.sha256(data.encode()).hexdigest()[:8].upper()}"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "strategy_id": self.strategy_id,
            "creator_id": self.creator_id,
            "name": self.name,
            "description": self.description,
            "category": self.category.value,
            "risk_level": self.risk_level.value,
            "parameters": self.parameters,
            "supported_tokens": self.supported_tokens,
            "min_capital": self.min_capital,
            "performance": self.performance.to_dict(),
            "version": self.version,
            "tags": self.tags,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat()
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Strategy":
        """Create from dictionary"""
        return cls(
            strategy_id=data["strategy_id"],
            creator_id=data["creator_id"],
            name=data["name"],
            description=data.get("description", ""),
            category=StrategyCategory(data["category"]),
            risk_level=RiskLevel(data["risk_level"]),
            parameters=data.get("parameters", {}),
            supported_tokens=data.get("supported_tokens", []),
            min_capital=data.get("min_capital", 100.0),
            performance=StrategyPerformance.from_dict(data.get("performance", {})),
            version=data.get("version", "1.0.0"),
            tags=data.get("tags", []),
            created_at=datetime.fromisoformat(data["created_at"]) if data.get("created_at") else datetime.now(),
            updated_at=datetime.fromisoformat(data["updated_at"]) if data.get("updated_at") else datetime.now()
        )


@dataclass
class StrategyListing:
    """A marketplace listing for a strategy"""
    listing_id: str
    strategy_id: str
    creator_id: str
    status: ListingStatus = ListingStatus.DRAFT

    # Pricing
    price_monthly: float = 0.0
    price_yearly: float = 0.0
    is_free: bool = False
    trial_days: int = 0

    # Stats
    subscriber_count: int = 0
    total_reviews: int = 0
    avg_rating: float = 0.0
    total_revenue: float = 0.0

    # Visibility
    is_featured: bool = False
    is_verified: bool = False
    rank: int = 0

    # Metadata
    created_at: datetime = field(default_factory=datetime.now)
    published_at: Optional[datetime] = None

    def __post_init__(self):
        if not self.listing_id:
            data = f"{self.strategy_id}{self.created_at.isoformat()}"
            self.listing_id = f"LIST-{hashlib.sha256(data.encode()).hexdigest()[:8].upper()}"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "listing_id": self.listing_id,
            "strategy_id": self.strategy_id,
            "creator_id": self.creator_id,
            "status": self.status.value,
            "price_monthly": self.price_monthly,
            "price_yearly": self.price_yearly,
            "is_free": self.is_free,
            "trial_days": self.trial_days,
            "subscriber_count": self.subscriber_count,
            "total_reviews": self.total_reviews,
            "avg_rating": self.avg_rating,
            "total_revenue": self.total_revenue,
            "is_featured": self.is_featured,
            "is_verified": self.is_verified,
            "rank": self.rank,
            "created_at": self.created_at.isoformat(),
            "published_at": self.published_at.isoformat() if self.published_at else None
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "StrategyListing":
        """Create from dictionary"""
        return cls(
            listing_id=data["listing_id"],
            strategy_id=data["strategy_id"],
            creator_id=data["creator_id"],
            status=ListingStatus(data.get("status", "draft")),
            price_monthly=data.get("price_monthly", 0.0),
            price_yearly=data.get("price_yearly", 0.0),
            is_free=data.get("is_free", False),
            trial_days=data.get("trial_days", 0),
            subscriber_count=data.get("subscriber_count", 0),
            total_reviews=data.get("total_reviews", 0),
            avg_rating=data.get("avg_rating", 0.0),
            total_revenue=data.get("total_revenue", 0.0),
            is_featured=data.get("is_featured", False),
            is_verified=data.get("is_verified", False),
            rank=data.get("rank", 0),
            created_at=datetime.fromisoformat(data["created_at"]) if data.get("created_at") else datetime.now(),
            published_at=datetime.fromisoformat(data["published_at"]) if data.get("published_at") else None
        )


@dataclass
class StrategySubscription:
    """A user's subscription to a strategy"""
    subscription_id: str
    user_id: str
    strategy_id: str
    listing_id: str

    # Subscription details
    is_active: bool = True
    is_trial: bool = False
    started_at: datetime = field(default_factory=datetime.now)
    expires_at: Optional[datetime] = None
    cancelled_at: Optional[datetime] = None

    # Payment
    amount_paid: float = 0.0
    billing_period: str = "monthly"

    def __post_init__(self):
        if not self.subscription_id:
            data = f"{self.user_id}{self.strategy_id}{self.started_at.isoformat()}"
            self.subscription_id = f"SSUB-{hashlib.sha256(data.encode()).hexdigest()[:8].upper()}"

    def is_valid(self) -> bool:
        """Check if subscription is currently valid"""
        if not self.is_active:
            return False
        if self.expires_at and datetime.now() > self.expires_at:
            return False
        return True

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "subscription_id": self.subscription_id,
            "user_id": self.user_id,
            "strategy_id": self.strategy_id,
            "listing_id": self.listing_id,
            "is_active": self.is_active,
            "is_trial": self.is_trial,
            "started_at": self.started_at.isoformat(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "cancelled_at": self.cancelled_at.isoformat() if self.cancelled_at else None,
            "amount_paid": self.amount_paid,
            "billing_period": self.billing_period
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "StrategySubscription":
        """Create from dictionary"""
        def parse_dt(val):
            return datetime.fromisoformat(val) if val else None

        return cls(
            subscription_id=data["subscription_id"],
            user_id=data["user_id"],
            strategy_id=data["strategy_id"],
            listing_id=data["listing_id"],
            is_active=data.get("is_active", True),
            is_trial=data.get("is_trial", False),
            started_at=parse_dt(data.get("started_at")) or datetime.now(),
            expires_at=parse_dt(data.get("expires_at")),
            cancelled_at=parse_dt(data.get("cancelled_at")),
            amount_paid=data.get("amount_paid", 0.0),
            billing_period=data.get("billing_period", "monthly")
        )


class StrategyManager:
    """
    Manages the strategy marketplace

    Handles strategy creation, listing, and subscriptions.
    """

    def __init__(self, storage_path: str = "data/strategy_marketplace/strategies.json"):
        self.storage_path = Path(storage_path)
        self.strategies: Dict[str, Strategy] = {}
        self.listings: Dict[str, StrategyListing] = {}
        self.subscriptions: Dict[str, StrategySubscription] = {}
        self.user_subscriptions: Dict[str, List[str]] = {}
        self._load()

    def _load(self):
        """Load data from storage"""
        if not self.storage_path.exists():
            return

        try:
            with open(self.storage_path) as f:
                data = json.load(f)

            for strat_data in data.get("strategies", []):
                strategy = Strategy.from_dict(strat_data)
                self.strategies[strategy.strategy_id] = strategy

            for list_data in data.get("listings", []):
                listing = StrategyListing.from_dict(list_data)
                self.listings[listing.listing_id] = listing

            for sub_data in data.get("subscriptions", []):
                sub = StrategySubscription.from_dict(sub_data)
                self.subscriptions[sub.subscription_id] = sub
                if sub.user_id not in self.user_subscriptions:
                    self.user_subscriptions[sub.user_id] = []
                self.user_subscriptions[sub.user_id].append(sub.subscription_id)

            logger.info(f"Loaded {len(self.strategies)} strategies, {len(self.listings)} listings")

        except Exception as e:
            logger.error(f"Failed to load strategy marketplace: {e}")

    def _save(self):
        """Save data to storage"""
        try:
            self.storage_path.parent.mkdir(parents=True, exist_ok=True)

            data = {
                "strategies": [s.to_dict() for s in self.strategies.values()],
                "listings": [l.to_dict() for l in self.listings.values()],
                "subscriptions": [s.to_dict() for s in self.subscriptions.values()],
                "updated_at": datetime.now().isoformat()
            }

            with open(self.storage_path, "w") as f:
                json.dump(data, f, indent=2)

        except Exception as e:
            logger.error(f"Failed to save strategy marketplace: {e}")
            raise

    async def create_strategy(
        self,
        creator_id: str,
        name: str,
        description: str,
        category: StrategyCategory,
        risk_level: RiskLevel,
        parameters: Optional[Dict[str, Any]] = None,
        supported_tokens: Optional[List[str]] = None
    ) -> Strategy:
        """Create a new strategy"""
        strategy = Strategy(
            strategy_id="",
            creator_id=creator_id,
            name=name,
            description=description,
            category=category,
            risk_level=risk_level,
            parameters=parameters or {},
            supported_tokens=supported_tokens or []
        )

        self.strategies[strategy.strategy_id] = strategy
        self._save()

        logger.info(f"Created strategy {strategy.strategy_id}: {name}")
        return strategy

    async def create_listing(
        self,
        strategy_id: str,
        price_monthly: float = 0.0,
        price_yearly: float = 0.0,
        trial_days: int = 0
    ) -> Optional[StrategyListing]:
        """Create a marketplace listing for a strategy"""
        strategy = self.strategies.get(strategy_id)
        if not strategy:
            return None

        listing = StrategyListing(
            listing_id="",
            strategy_id=strategy_id,
            creator_id=strategy.creator_id,
            price_monthly=price_monthly,
            price_yearly=price_yearly,
            is_free=price_monthly == 0,
            trial_days=trial_days
        )

        self.listings[listing.listing_id] = listing
        self._save()

        logger.info(f"Created listing {listing.listing_id} for strategy {strategy_id}")
        return listing

    async def publish_listing(self, listing_id: str) -> bool:
        """Publish a listing to make it active"""
        listing = self.listings.get(listing_id)
        if not listing:
            return False

        listing.status = ListingStatus.ACTIVE
        listing.published_at = datetime.now()
        self._save()

        return True

    async def subscribe_to_strategy(
        self,
        user_id: str,
        listing_id: str,
        billing_period: str = "monthly"
    ) -> Optional[StrategySubscription]:
        """Subscribe a user to a strategy"""
        listing = self.listings.get(listing_id)
        if not listing or listing.status != ListingStatus.ACTIVE:
            return None

        # Calculate expiry
        if billing_period == "yearly":
            expires_at = datetime.now() + timedelta(days=365)
            amount = listing.price_yearly
        else:
            expires_at = datetime.now() + timedelta(days=30)
            amount = listing.price_monthly

        # Create subscription
        sub = StrategySubscription(
            subscription_id="",
            user_id=user_id,
            strategy_id=listing.strategy_id,
            listing_id=listing_id,
            expires_at=expires_at,
            amount_paid=amount,
            billing_period=billing_period,
            is_trial=listing.trial_days > 0 and listing.price_monthly > 0
        )

        self.subscriptions[sub.subscription_id] = sub
        if user_id not in self.user_subscriptions:
            self.user_subscriptions[user_id] = []
        self.user_subscriptions[user_id].append(sub.subscription_id)

        # Update listing stats
        listing.subscriber_count += 1
        listing.total_revenue += amount

        self._save()
        logger.info(f"User {user_id} subscribed to strategy {listing.strategy_id}")
        return sub

    async def get_strategy(self, strategy_id: str) -> Optional[Strategy]:
        """Get a strategy by ID"""
        return self.strategies.get(strategy_id)

    async def get_listing(self, listing_id: str) -> Optional[StrategyListing]:
        """Get a listing by ID"""
        return self.listings.get(listing_id)

    async def search_strategies(
        self,
        category: Optional[StrategyCategory] = None,
        risk_level: Optional[RiskLevel] = None,
        min_return: Optional[float] = None,
        max_price: Optional[float] = None,
        free_only: bool = False,
        sort_by: str = "subscribers",
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """Search and filter strategy listings"""
        results = []

        for listing in self.listings.values():
            if listing.status != ListingStatus.ACTIVE:
                continue

            strategy = self.strategies.get(listing.strategy_id)
            if not strategy:
                continue

            # Apply filters
            if category and strategy.category != category:
                continue
            if risk_level and strategy.risk_level != risk_level:
                continue
            if min_return and strategy.performance.total_return_pct < min_return:
                continue
            if max_price and listing.price_monthly > max_price:
                continue
            if free_only and not listing.is_free:
                continue

            results.append({
                "listing": listing.to_dict(),
                "strategy": strategy.to_dict()
            })

        # Sort
        sort_keys = {
            "subscribers": lambda x: x["listing"]["subscriber_count"],
            "rating": lambda x: x["listing"]["avg_rating"],
            "return": lambda x: x["strategy"]["performance"]["total_return_pct"],
            "price_low": lambda x: x["listing"]["price_monthly"],
            "price_high": lambda x: -x["listing"]["price_monthly"]
        }
        sort_fn = sort_keys.get(sort_by, sort_keys["subscribers"])
        results.sort(key=sort_fn, reverse=True)

        return results[:limit]

    async def get_user_subscriptions(self, user_id: str) -> List[StrategySubscription]:
        """Get all subscriptions for a user"""
        sub_ids = self.user_subscriptions.get(user_id, [])
        return [self.subscriptions[sid] for sid in sub_ids if sid in self.subscriptions]

    async def is_subscribed(self, user_id: str, strategy_id: str) -> bool:
        """Check if user is subscribed to a strategy"""
        subs = await self.get_user_subscriptions(user_id)
        return any(s.strategy_id == strategy_id and s.is_valid() for s in subs)

    async def update_performance(
        self,
        strategy_id: str,
        performance: StrategyPerformance
    ) -> bool:
        """Update strategy performance metrics"""
        strategy = self.strategies.get(strategy_id)
        if not strategy:
            return False

        strategy.performance = performance
        strategy.updated_at = datetime.now()
        self._save()

        return True

    def get_stats(self) -> Dict[str, Any]:
        """Get marketplace statistics"""
        active_listings = sum(1 for l in self.listings.values() if l.status == ListingStatus.ACTIVE)
        total_subscribers = sum(l.subscriber_count for l in self.listings.values())
        total_revenue = sum(l.total_revenue for l in self.listings.values())

        by_category = {}
        for strategy in self.strategies.values():
            cat = strategy.category.value
            by_category[cat] = by_category.get(cat, 0) + 1

        return {
            "total_strategies": len(self.strategies),
            "active_listings": active_listings,
            "total_subscribers": total_subscribers,
            "total_revenue": total_revenue,
            "by_category": by_category
        }


# Singleton instance
_strategy_manager: Optional[StrategyManager] = None


def get_strategy_manager() -> StrategyManager:
    """Get strategy manager singleton"""
    global _strategy_manager

    if _strategy_manager is None:
        _strategy_manager = StrategyManager()

    return _strategy_manager


# Testing
if __name__ == "__main__":
    async def test():
        manager = StrategyManager("test_strategies.json")

        # Create a strategy
        strategy = await manager.create_strategy(
            creator_id="CREATOR_123",
            name="Whale Following Strategy",
            description="Follows large whale wallets and copies their trades",
            category=StrategyCategory.WHALE_FOLLOWING,
            risk_level=RiskLevel.MEDIUM,
            supported_tokens=["SOL", "ETH", "BTC"]
        )
        print(f"Created strategy: {strategy.strategy_id}")

        # Create listing
        listing = await manager.create_listing(
            strategy_id=strategy.strategy_id,
            price_monthly=29.99,
            price_yearly=299.99,
            trial_days=7
        )
        print(f"Created listing: {listing.listing_id}")

        # Publish
        await manager.publish_listing(listing.listing_id)

        # Subscribe
        sub = await manager.subscribe_to_strategy(
            user_id="USER_456",
            listing_id=listing.listing_id
        )
        print(f"Created subscription: {sub.subscription_id}")

        # Search
        results = await manager.search_strategies(category=StrategyCategory.WHALE_FOLLOWING)
        print(f"Search results: {len(results)}")

        # Stats
        print(f"Stats: {manager.get_stats()}")

        # Clean up
        import os
        os.remove("test_strategies.json")

    asyncio.run(test())
