"""
Subscription Management

Tiered subscription system with crypto payments.
Manages access to premium features based on subscription level.

Prompts #36-40: Business Model
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


class SubscriptionTier(str, Enum):
    """Subscription tiers"""
    FREE = "free"
    STARTER = "starter"
    PRO = "pro"
    WHALE = "whale"
    ENTERPRISE = "enterprise"


class SubscriptionStatus(str, Enum):
    """Subscription status"""
    ACTIVE = "active"
    EXPIRED = "expired"
    CANCELLED = "cancelled"
    PENDING = "pending"
    TRIAL = "trial"


class PaymentMethod(str, Enum):
    """Payment methods"""
    SOL = "sol"
    USDC = "usdc"
    KR8TIV = "kr8tiv"  # $KR8TIV token
    STRIPE = "stripe"  # Fiat via Stripe


@dataclass
class TierConfig:
    """Configuration for a subscription tier"""
    tier: SubscriptionTier
    name: str
    price_monthly_usd: float
    price_yearly_usd: float
    kr8tiv_discount_pct: float = 20.0  # Discount for paying with $KR8TIV

    # Feature limits
    alerts_per_day: int = 5
    api_calls_per_day: int = 100
    wallets_tracked: int = 1
    copy_trading_leaders: int = 0
    signal_delay_minutes: int = 15

    # Features
    features: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "tier": self.tier.value,
            "name": self.name,
            "price_monthly_usd": self.price_monthly_usd,
            "price_yearly_usd": self.price_yearly_usd,
            "kr8tiv_discount_pct": self.kr8tiv_discount_pct,
            "alerts_per_day": self.alerts_per_day,
            "api_calls_per_day": self.api_calls_per_day,
            "wallets_tracked": self.wallets_tracked,
            "copy_trading_leaders": self.copy_trading_leaders,
            "signal_delay_minutes": self.signal_delay_minutes,
            "features": self.features
        }


# Tier configurations
TIER_CONFIGS = {
    SubscriptionTier.FREE: TierConfig(
        tier=SubscriptionTier.FREE,
        name="Free",
        price_monthly_usd=0,
        price_yearly_usd=0,
        alerts_per_day=3,
        api_calls_per_day=50,
        wallets_tracked=1,
        copy_trading_leaders=0,
        signal_delay_minutes=15,
        features=[
            "basic_portfolio_tracking",
            "limited_alerts",
            "community_access"
        ]
    ),
    SubscriptionTier.STARTER: TierConfig(
        tier=SubscriptionTier.STARTER,
        name="Starter",
        price_monthly_usd=9.99,
        price_yearly_usd=99.99,
        alerts_per_day=25,
        api_calls_per_day=500,
        wallets_tracked=3,
        copy_trading_leaders=1,
        signal_delay_minutes=5,
        features=[
            "basic_portfolio_tracking",
            "standard_alerts",
            "whale_watching_basic",
            "1_copy_trading_leader",
            "community_access"
        ]
    ),
    SubscriptionTier.PRO: TierConfig(
        tier=SubscriptionTier.PRO,
        name="Pro",
        price_monthly_usd=29.99,
        price_yearly_usd=299.99,
        alerts_per_day=100,
        api_calls_per_day=5000,
        wallets_tracked=10,
        copy_trading_leaders=5,
        signal_delay_minutes=0,
        features=[
            "advanced_portfolio_tracking",
            "unlimited_alerts",
            "whale_watching_full",
            "copy_trading",
            "real_time_signals",
            "api_access",
            "priority_support",
            "community_access"
        ]
    ),
    SubscriptionTier.WHALE: TierConfig(
        tier=SubscriptionTier.WHALE,
        name="Whale",
        price_monthly_usd=99.99,
        price_yearly_usd=999.99,
        alerts_per_day=10000,
        api_calls_per_day=100000,
        wallets_tracked=50,
        copy_trading_leaders=20,
        signal_delay_minutes=0,
        features=[
            "advanced_portfolio_tracking",
            "unlimited_alerts",
            "whale_watching_full",
            "copy_trading",
            "real_time_signals",
            "api_access",
            "dedicated_support",
            "custom_integrations",
            "early_access_features",
            "governance_voting",
            "community_access"
        ]
    ),
    SubscriptionTier.ENTERPRISE: TierConfig(
        tier=SubscriptionTier.ENTERPRISE,
        name="Enterprise",
        price_monthly_usd=499.99,
        price_yearly_usd=4999.99,
        alerts_per_day=1000000,
        api_calls_per_day=1000000,
        wallets_tracked=1000,
        copy_trading_leaders=100,
        signal_delay_minutes=0,
        features=[
            "everything_in_whale",
            "custom_deployment",
            "sla_guarantee",
            "dedicated_account_manager",
            "white_label_option"
        ]
    )
}


@dataclass
class Subscription:
    """A user's subscription"""
    subscription_id: str
    user_id: str
    tier: SubscriptionTier
    status: SubscriptionStatus
    payment_method: PaymentMethod

    # Billing
    price_paid: float = 0.0
    currency: str = "USD"
    billing_period: str = "monthly"  # monthly, yearly

    # Timeline
    starts_at: datetime = field(default_factory=datetime.now)
    expires_at: Optional[datetime] = None
    cancelled_at: Optional[datetime] = None
    renewed_at: Optional[datetime] = None

    # Payment tracking
    last_payment_at: Optional[datetime] = None
    next_payment_at: Optional[datetime] = None
    payment_failures: int = 0
    tx_hashes: List[str] = field(default_factory=list)

    # Metadata
    created_at: datetime = field(default_factory=datetime.now)

    def __post_init__(self):
        if not self.subscription_id:
            data = f"{self.user_id}{self.tier.value}{self.created_at.isoformat()}"
            self.subscription_id = f"SUB-{hashlib.sha256(data.encode()).hexdigest()[:12].upper()}"

    def is_active(self) -> bool:
        """Check if subscription is currently active"""
        if self.status not in [SubscriptionStatus.ACTIVE, SubscriptionStatus.TRIAL]:
            return False
        if self.expires_at and datetime.now() > self.expires_at:
            return False
        return True

    def days_remaining(self) -> int:
        """Get days remaining in subscription"""
        if not self.expires_at:
            return 0
        delta = self.expires_at - datetime.now()
        return max(0, delta.days)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "subscription_id": self.subscription_id,
            "user_id": self.user_id,
            "tier": self.tier.value,
            "status": self.status.value,
            "payment_method": self.payment_method.value,
            "price_paid": self.price_paid,
            "currency": self.currency,
            "billing_period": self.billing_period,
            "starts_at": self.starts_at.isoformat(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "cancelled_at": self.cancelled_at.isoformat() if self.cancelled_at else None,
            "renewed_at": self.renewed_at.isoformat() if self.renewed_at else None,
            "last_payment_at": self.last_payment_at.isoformat() if self.last_payment_at else None,
            "next_payment_at": self.next_payment_at.isoformat() if self.next_payment_at else None,
            "payment_failures": self.payment_failures,
            "tx_hashes": self.tx_hashes,
            "created_at": self.created_at.isoformat()
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Subscription":
        """Create from dictionary"""
        def parse_dt(val):
            return datetime.fromisoformat(val) if val else None

        return cls(
            subscription_id=data["subscription_id"],
            user_id=data["user_id"],
            tier=SubscriptionTier(data["tier"]),
            status=SubscriptionStatus(data["status"]),
            payment_method=PaymentMethod(data.get("payment_method", "usdc")),
            price_paid=data.get("price_paid", 0.0),
            currency=data.get("currency", "USD"),
            billing_period=data.get("billing_period", "monthly"),
            starts_at=parse_dt(data.get("starts_at")) or datetime.now(),
            expires_at=parse_dt(data.get("expires_at")),
            cancelled_at=parse_dt(data.get("cancelled_at")),
            renewed_at=parse_dt(data.get("renewed_at")),
            last_payment_at=parse_dt(data.get("last_payment_at")),
            next_payment_at=parse_dt(data.get("next_payment_at")),
            payment_failures=data.get("payment_failures", 0),
            tx_hashes=data.get("tx_hashes", []),
            created_at=parse_dt(data.get("created_at")) or datetime.now()
        )


class SubscriptionManager:
    """
    Manages user subscriptions

    Handles subscription creation, renewal, and cancellation.
    """

    def __init__(
        self,
        storage_path: str = "data/subscriptions/subscriptions.json",
        payment_processor: Any = None
    ):
        self.storage_path = Path(storage_path)
        self.payment_processor = payment_processor
        self.subscriptions: Dict[str, Subscription] = {}
        self.user_subscriptions: Dict[str, str] = {}  # user_id -> subscription_id
        self._load()

    def _load(self):
        """Load subscriptions from storage"""
        if not self.storage_path.exists():
            return

        try:
            with open(self.storage_path) as f:
                data = json.load(f)

            for sub_data in data.get("subscriptions", []):
                sub = Subscription.from_dict(sub_data)
                self.subscriptions[sub.subscription_id] = sub
                self.user_subscriptions[sub.user_id] = sub.subscription_id

            logger.info(f"Loaded {len(self.subscriptions)} subscriptions")

        except Exception as e:
            logger.error(f"Failed to load subscriptions: {e}")

    def _save(self):
        """Save subscriptions to storage"""
        try:
            self.storage_path.parent.mkdir(parents=True, exist_ok=True)

            data = {
                "subscriptions": [s.to_dict() for s in self.subscriptions.values()],
                "updated_at": datetime.now().isoformat()
            }

            with open(self.storage_path, "w") as f:
                json.dump(data, f, indent=2)

        except Exception as e:
            logger.error(f"Failed to save subscriptions: {e}")
            raise

    def get_tier_config(self, tier: SubscriptionTier) -> TierConfig:
        """Get configuration for a tier"""
        return TIER_CONFIGS.get(tier, TIER_CONFIGS[SubscriptionTier.FREE])

    async def get_user_subscription(self, user_id: str) -> Optional[Subscription]:
        """Get a user's current subscription"""
        sub_id = self.user_subscriptions.get(user_id)
        if sub_id:
            return self.subscriptions.get(sub_id)
        return None

    async def get_user_tier(self, user_id: str) -> SubscriptionTier:
        """Get a user's current tier"""
        sub = await self.get_user_subscription(user_id)
        if sub and sub.is_active():
            return sub.tier
        return SubscriptionTier.FREE

    async def create_subscription(
        self,
        user_id: str,
        tier: SubscriptionTier,
        payment_method: PaymentMethod = PaymentMethod.USDC,
        billing_period: str = "monthly",
        tx_hash: Optional[str] = None
    ) -> Optional[Subscription]:
        """Create a new subscription"""
        # Get tier config
        config = self.get_tier_config(tier)

        # Calculate price
        if billing_period == "yearly":
            price = config.price_yearly_usd
            expires_at = datetime.now() + timedelta(days=365)
        else:
            price = config.price_monthly_usd
            expires_at = datetime.now() + timedelta(days=30)

        # Apply $KR8TIV discount
        if payment_method == PaymentMethod.KR8TIV:
            price *= (1 - config.kr8tiv_discount_pct / 100)

        # Create subscription
        sub = Subscription(
            subscription_id="",
            user_id=user_id,
            tier=tier,
            status=SubscriptionStatus.ACTIVE,
            payment_method=payment_method,
            price_paid=price,
            billing_period=billing_period,
            expires_at=expires_at,
            last_payment_at=datetime.now(),
            next_payment_at=expires_at
        )

        if tx_hash:
            sub.tx_hashes.append(tx_hash)

        # Store
        self.subscriptions[sub.subscription_id] = sub
        self.user_subscriptions[user_id] = sub.subscription_id
        self._save()

        logger.info(f"Created subscription {sub.subscription_id} for user {user_id}: {tier.value}")
        return sub

    async def renew_subscription(
        self,
        user_id: str,
        tx_hash: Optional[str] = None
    ) -> bool:
        """Renew an existing subscription"""
        sub = await self.get_user_subscription(user_id)
        if not sub:
            return False

        config = self.get_tier_config(sub.tier)

        # Calculate new expiry
        if sub.billing_period == "yearly":
            extension = timedelta(days=365)
            price = config.price_yearly_usd
        else:
            extension = timedelta(days=30)
            price = config.price_monthly_usd

        # Apply discount
        if sub.payment_method == PaymentMethod.KR8TIV:
            price *= (1 - config.kr8tiv_discount_pct / 100)

        # Extend from current expiry or now
        base_date = sub.expires_at if sub.expires_at and sub.expires_at > datetime.now() else datetime.now()
        sub.expires_at = base_date + extension
        sub.renewed_at = datetime.now()
        sub.last_payment_at = datetime.now()
        sub.next_payment_at = sub.expires_at
        sub.status = SubscriptionStatus.ACTIVE
        sub.payment_failures = 0

        if tx_hash:
            sub.tx_hashes.append(tx_hash)

        self._save()
        logger.info(f"Renewed subscription for user {user_id}")
        return True

    async def upgrade_subscription(
        self,
        user_id: str,
        new_tier: SubscriptionTier,
        tx_hash: Optional[str] = None
    ) -> bool:
        """Upgrade to a higher tier"""
        sub = await self.get_user_subscription(user_id)

        if not sub:
            # Create new subscription
            await self.create_subscription(user_id, new_tier, tx_hash=tx_hash)
            return True

        # Calculate prorated credit
        if sub.expires_at and sub.is_active():
            days_remaining = sub.days_remaining()
            old_config = self.get_tier_config(sub.tier)
            new_config = self.get_tier_config(new_tier)

            daily_old = old_config.price_monthly_usd / 30
            daily_new = new_config.price_monthly_usd / 30

            credit = days_remaining * daily_old
            additional = days_remaining * (daily_new - daily_old)

            logger.info(f"Upgrade credit: ${credit:.2f}, Additional: ${additional:.2f}")

        sub.tier = new_tier
        sub.renewed_at = datetime.now()

        if tx_hash:
            sub.tx_hashes.append(tx_hash)

        self._save()
        logger.info(f"Upgraded subscription for user {user_id} to {new_tier.value}")
        return True

    async def cancel_subscription(self, user_id: str) -> bool:
        """Cancel a subscription"""
        sub = await self.get_user_subscription(user_id)
        if not sub:
            return False

        sub.status = SubscriptionStatus.CANCELLED
        sub.cancelled_at = datetime.now()
        # Let it run until expiry
        self._save()

        logger.info(f"Cancelled subscription for user {user_id}")
        return True

    async def check_feature_access(
        self,
        user_id: str,
        feature: str
    ) -> bool:
        """Check if user has access to a feature"""
        tier = await self.get_user_tier(user_id)
        config = self.get_tier_config(tier)
        return feature in config.features

    async def get_tier_limits(self, user_id: str) -> Dict[str, Any]:
        """Get usage limits for user's tier"""
        tier = await self.get_user_tier(user_id)
        config = self.get_tier_config(tier)

        return {
            "tier": tier.value,
            "alerts_per_day": config.alerts_per_day,
            "api_calls_per_day": config.api_calls_per_day,
            "wallets_tracked": config.wallets_tracked,
            "copy_trading_leaders": config.copy_trading_leaders,
            "signal_delay_minutes": config.signal_delay_minutes,
            "features": config.features
        }

    async def process_expired_subscriptions(self):
        """Process expired subscriptions"""
        now = datetime.now()
        expired_count = 0

        for sub in self.subscriptions.values():
            if sub.status == SubscriptionStatus.ACTIVE and sub.expires_at:
                if now > sub.expires_at:
                    sub.status = SubscriptionStatus.EXPIRED
                    expired_count += 1
                    logger.info(f"Subscription {sub.subscription_id} expired")

        if expired_count > 0:
            self._save()

        return expired_count

    def get_pricing(self) -> Dict[str, Any]:
        """Get pricing information for all tiers"""
        return {
            tier.value: config.to_dict()
            for tier, config in TIER_CONFIGS.items()
        }

    def get_stats(self) -> Dict[str, Any]:
        """Get subscription statistics"""
        by_tier = {}
        by_status = {}
        mrr = 0.0  # Monthly recurring revenue

        for sub in self.subscriptions.values():
            tier = sub.tier.value
            status = sub.status.value

            by_tier[tier] = by_tier.get(tier, 0) + 1
            by_status[status] = by_status.get(status, 0) + 1

            if sub.is_active():
                config = self.get_tier_config(sub.tier)
                if sub.billing_period == "yearly":
                    mrr += config.price_yearly_usd / 12
                else:
                    mrr += config.price_monthly_usd

        return {
            "total_subscriptions": len(self.subscriptions),
            "by_tier": by_tier,
            "by_status": by_status,
            "monthly_recurring_revenue": mrr,
            "active_subscriptions": by_status.get("active", 0)
        }


# Singleton instance
_subscription_manager: Optional[SubscriptionManager] = None


def get_subscription_manager() -> SubscriptionManager:
    """Get subscription manager singleton"""
    global _subscription_manager

    if _subscription_manager is None:
        _subscription_manager = SubscriptionManager()

    return _subscription_manager


# Testing
if __name__ == "__main__":
    async def test():
        manager = SubscriptionManager("test_subscriptions.json")

        # Show pricing
        print("Pricing:")
        for tier, config in manager.get_pricing().items():
            print(f"  {tier}: ${config['price_monthly_usd']}/mo or ${config['price_yearly_usd']}/yr")

        # Create subscription
        sub = await manager.create_subscription(
            user_id="TEST_USER",
            tier=SubscriptionTier.PRO,
            payment_method=PaymentMethod.USDC
        )
        print(f"\nCreated: {sub.subscription_id}")
        print(f"  Tier: {sub.tier.value}")
        print(f"  Expires: {sub.expires_at}")
        print(f"  Days remaining: {sub.days_remaining()}")

        # Check feature access
        has_api = await manager.check_feature_access("TEST_USER", "api_access")
        print(f"\nHas API access: {has_api}")

        # Get limits
        limits = await manager.get_tier_limits("TEST_USER")
        print(f"Limits: {limits}")

        # Stats
        print(f"\nStats: {manager.get_stats()}")

        # Clean up
        import os
        os.remove("test_subscriptions.json")

    asyncio.run(test())
