"""
Subscription & Tier Management
Prompts #65-70: Access control, feature gating, and token utility
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Any, Callable, Dict, List, Optional
import json

logger = logging.getLogger(__name__)


# =============================================================================
# TIER DEFINITIONS
# =============================================================================

class SubscriptionTier(str, Enum):
    FREE = "free"
    STARTER = "starter"
    PRO = "pro"
    ENTERPRISE = "enterprise"
    WHALE = "whale"  # Dynamic tier based on holdings


@dataclass
class TierBenefits:
    """Benefits for a subscription tier"""
    tier: SubscriptionTier
    monthly_price_usd: float
    features: Dict[str, Any]
    api_rate_limit: int  # Requests per minute
    ai_credits_monthly: int
    max_portfolios: int
    max_strategies: int
    trading_fee_discount: int  # Basis points
    staking_apy_boost: int  # Basis points
    priority_support: bool
    custom_strategies: bool
    white_label: bool


TIER_BENEFITS: Dict[SubscriptionTier, TierBenefits] = {
    SubscriptionTier.FREE: TierBenefits(
        tier=SubscriptionTier.FREE,
        monthly_price_usd=0,
        features={
            "basic_trading": True,
            "portfolio_tracking": True,
            "market_data": True,
            "basic_alerts": True
        },
        api_rate_limit=10,
        ai_credits_monthly=100,
        max_portfolios=1,
        max_strategies=0,
        trading_fee_discount=0,
        staking_apy_boost=0,
        priority_support=False,
        custom_strategies=False,
        white_label=False
    ),
    SubscriptionTier.STARTER: TierBenefits(
        tier=SubscriptionTier.STARTER,
        monthly_price_usd=9.99,
        features={
            "basic_trading": True,
            "portfolio_tracking": True,
            "market_data": True,
            "basic_alerts": True,
            "advanced_alerts": True,
            "basic_automation": True,
            "dca_orders": True
        },
        api_rate_limit=30,
        ai_credits_monthly=1000,
        max_portfolios=3,
        max_strategies=2,
        trading_fee_discount=10,
        staking_apy_boost=0,
        priority_support=False,
        custom_strategies=False,
        white_label=False
    ),
    SubscriptionTier.PRO: TierBenefits(
        tier=SubscriptionTier.PRO,
        monthly_price_usd=29.99,
        features={
            "basic_trading": True,
            "portfolio_tracking": True,
            "market_data": True,
            "basic_alerts": True,
            "advanced_alerts": True,
            "basic_automation": True,
            "dca_orders": True,
            "advanced_automation": True,
            "copy_trading": True,
            "analytics_dashboard": True,
            "api_access": True
        },
        api_rate_limit=100,
        ai_credits_monthly=5000,
        max_portfolios=10,
        max_strategies=10,
        trading_fee_discount=20,
        staking_apy_boost=10,
        priority_support=True,
        custom_strategies=True,
        white_label=False
    ),
    SubscriptionTier.ENTERPRISE: TierBenefits(
        tier=SubscriptionTier.ENTERPRISE,
        monthly_price_usd=99.99,
        features={
            "basic_trading": True,
            "portfolio_tracking": True,
            "market_data": True,
            "basic_alerts": True,
            "advanced_alerts": True,
            "basic_automation": True,
            "dca_orders": True,
            "advanced_automation": True,
            "copy_trading": True,
            "analytics_dashboard": True,
            "api_access": True,
            "custom_integrations": True,
            "dedicated_support": True,
            "sla_guarantee": True
        },
        api_rate_limit=500,
        ai_credits_monthly=25000,
        max_portfolios=-1,  # Unlimited
        max_strategies=-1,
        trading_fee_discount=30,
        staking_apy_boost=25,
        priority_support=True,
        custom_strategies=True,
        white_label=True
    ),
    SubscriptionTier.WHALE: TierBenefits(
        tier=SubscriptionTier.WHALE,
        monthly_price_usd=0,  # Free for whales (determined by holdings)
        features={
            "basic_trading": True,
            "portfolio_tracking": True,
            "market_data": True,
            "basic_alerts": True,
            "advanced_alerts": True,
            "basic_automation": True,
            "dca_orders": True,
            "advanced_automation": True,
            "copy_trading": True,
            "analytics_dashboard": True,
            "api_access": True,
            "whale_chat": True,
            "early_access": True
        },
        api_rate_limit=200,
        ai_credits_monthly=10000,
        max_portfolios=-1,
        max_strategies=20,
        trading_fee_discount=40,
        staking_apy_boost=50,
        priority_support=True,
        custom_strategies=True,
        white_label=False
    )
}


# =============================================================================
# MODELS
# =============================================================================

@dataclass
class UserSubscription:
    """User's subscription state"""
    user_id: str
    wallet: str
    tier: SubscriptionTier
    started_at: datetime
    expires_at: Optional[datetime] = None
    auto_renew: bool = True
    payment_method: str = "token"  # "token", "card", "crypto"
    token_stake_amount: int = 0  # $KR8TIV staked for tier
    is_trial: bool = False
    trial_ends: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def is_active(self) -> bool:
        if self.tier == SubscriptionTier.FREE:
            return True
        if self.expires_at is None:
            return True
        return datetime.utcnow() < self.expires_at

    @property
    def days_remaining(self) -> int:
        if self.expires_at is None:
            return -1
        delta = self.expires_at - datetime.utcnow()
        return max(0, delta.days)


@dataclass
class FeatureAccess:
    """Result of feature access check"""
    allowed: bool
    reason: str = ""
    upgrade_tier: Optional[SubscriptionTier] = None
    current_usage: int = 0
    limit: int = 0


# =============================================================================
# STAKE-TO-TIER MAPPING
# =============================================================================

STAKE_TIER_THRESHOLDS = {
    0: SubscriptionTier.FREE,
    10_000: SubscriptionTier.STARTER,      # 10K tokens = Starter
    50_000: SubscriptionTier.PRO,          # 50K tokens = Pro
    250_000: SubscriptionTier.ENTERPRISE,  # 250K tokens = Enterprise
    1_000_000: SubscriptionTier.WHALE      # 1M tokens = Whale
}


# =============================================================================
# TIER MANAGER
# =============================================================================

class TierManager:
    """Manages user subscriptions and tier access"""

    def __init__(
        self,
        staking_service: Optional[Any] = None,
        payment_service: Optional[Any] = None
    ):
        self.staking_service = staking_service
        self.payment_service = payment_service

        self.subscriptions: Dict[str, UserSubscription] = {}
        self.usage_tracking: Dict[str, Dict[str, int]] = {}  # user_id -> feature -> usage

    # =========================================================================
    # SUBSCRIPTION MANAGEMENT
    # =========================================================================

    async def get_subscription(self, user_id: str) -> UserSubscription:
        """Get user's current subscription"""
        if user_id not in self.subscriptions:
            await self._init_subscription(user_id)
        return self.subscriptions[user_id]

    async def upgrade_tier(
        self,
        user_id: str,
        new_tier: SubscriptionTier,
        payment_method: str = "token"
    ) -> UserSubscription:
        """Upgrade user's subscription tier"""
        sub = await self.get_subscription(user_id)
        old_tier = sub.tier
        benefits = TIER_BENEFITS[new_tier]

        if payment_method == "token":
            # Lock tokens for tier access
            required_stake = self._get_required_stake(new_tier)
            if self.staking_service:
                success = await self.staking_service.lock_for_tier(
                    user_id, required_stake
                )
                if not success:
                    raise ValueError("Failed to lock tokens for tier")
            sub.token_stake_amount = required_stake

        elif payment_method == "card":
            # Process card payment
            if self.payment_service:
                success = await self.payment_service.charge(
                    user_id, benefits.monthly_price_usd
                )
                if not success:
                    raise ValueError("Payment failed")

        sub.tier = new_tier
        sub.started_at = datetime.utcnow()
        sub.expires_at = datetime.utcnow() + timedelta(days=30)
        sub.payment_method = payment_method

        logger.info(f"User {user_id} upgraded from {old_tier.value} to {new_tier.value}")
        return sub

    async def downgrade_tier(
        self,
        user_id: str,
        new_tier: SubscriptionTier
    ) -> UserSubscription:
        """Downgrade user's subscription tier"""
        sub = await self.get_subscription(user_id)

        # Release locked tokens if any
        if sub.token_stake_amount > 0 and self.staking_service:
            await self.staking_service.unlock_tier_stake(
                user_id, sub.token_stake_amount
            )

        sub.tier = new_tier
        sub.token_stake_amount = 0
        sub.expires_at = None if new_tier == SubscriptionTier.FREE else sub.expires_at

        logger.info(f"User {user_id} downgraded to {new_tier.value}")
        return sub

    async def sync_stake_tier(self, user_id: str) -> UserSubscription:
        """Sync tier based on user's staking position"""
        sub = await self.get_subscription(user_id)

        if not self.staking_service:
            return sub

        # Get staking info
        stake_info = await self.staking_service.get_stake(user_id)
        if not stake_info:
            return sub

        stake_amount = stake_info.get("amount", 0) / 10**9

        # Determine tier from stake
        new_tier = SubscriptionTier.FREE
        for threshold, tier in sorted(STAKE_TIER_THRESHOLDS.items(), reverse=True):
            if stake_amount >= threshold:
                new_tier = tier
                break

        if new_tier != sub.tier and sub.payment_method == "token":
            sub.tier = new_tier
            sub.token_stake_amount = int(stake_amount * 10**9)
            logger.info(f"User {user_id} tier synced to {new_tier.value} based on stake")

        return sub

    async def start_trial(
        self,
        user_id: str,
        tier: SubscriptionTier,
        days: int = 7
    ) -> UserSubscription:
        """Start a free trial"""
        sub = await self.get_subscription(user_id)

        # Check if user already had a trial
        if sub.metadata.get("trial_used"):
            raise ValueError("Trial already used")

        sub.tier = tier
        sub.is_trial = True
        sub.trial_ends = datetime.utcnow() + timedelta(days=days)
        sub.expires_at = sub.trial_ends
        sub.metadata["trial_used"] = True

        logger.info(f"User {user_id} started {days}-day trial of {tier.value}")
        return sub

    async def cancel_subscription(self, user_id: str) -> UserSubscription:
        """Cancel subscription (will expire at end of period)"""
        sub = await self.get_subscription(user_id)
        sub.auto_renew = False

        logger.info(f"User {user_id} cancelled subscription, expires {sub.expires_at}")
        return sub

    async def renew_subscription(self, user_id: str) -> UserSubscription:
        """Renew subscription for another period"""
        sub = await self.get_subscription(user_id)

        if sub.tier == SubscriptionTier.FREE:
            return sub

        if sub.payment_method == "token":
            # Verify stake is still sufficient
            await self.sync_stake_tier(user_id)
        elif sub.payment_method == "card":
            # Charge card
            benefits = TIER_BENEFITS[sub.tier]
            if self.payment_service:
                await self.payment_service.charge(user_id, benefits.monthly_price_usd)

        sub.expires_at = datetime.utcnow() + timedelta(days=30)
        logger.info(f"User {user_id} subscription renewed")
        return sub

    # =========================================================================
    # FEATURE ACCESS
    # =========================================================================

    async def check_feature_access(
        self,
        user_id: str,
        feature: str
    ) -> FeatureAccess:
        """Check if user has access to a feature"""
        sub = await self.get_subscription(user_id)

        if not sub.is_active:
            return FeatureAccess(
                allowed=False,
                reason="Subscription expired",
                upgrade_tier=SubscriptionTier.STARTER
            )

        benefits = TIER_BENEFITS[sub.tier]

        # Check feature availability
        if feature not in benefits.features:
            # Find minimum tier with this feature
            upgrade_tier = None
            for tier in SubscriptionTier:
                if feature in TIER_BENEFITS[tier].features:
                    upgrade_tier = tier
                    break

            return FeatureAccess(
                allowed=False,
                reason=f"Feature '{feature}' not available in {sub.tier.value} tier",
                upgrade_tier=upgrade_tier
            )

        if not benefits.features[feature]:
            return FeatureAccess(
                allowed=False,
                reason=f"Feature '{feature}' is disabled"
            )

        return FeatureAccess(allowed=True)

    async def check_limit(
        self,
        user_id: str,
        limit_type: str
    ) -> FeatureAccess:
        """Check if user is within usage limits"""
        sub = await self.get_subscription(user_id)
        benefits = TIER_BENEFITS[sub.tier]

        # Get current usage
        if user_id not in self.usage_tracking:
            self.usage_tracking[user_id] = {}
        current = self.usage_tracking[user_id].get(limit_type, 0)

        # Get limit
        limit = getattr(benefits, limit_type, None)
        if limit is None:
            return FeatureAccess(allowed=True)

        if limit == -1:  # Unlimited
            return FeatureAccess(allowed=True, current_usage=current, limit=-1)

        if current >= limit:
            return FeatureAccess(
                allowed=False,
                reason=f"Limit reached: {current}/{limit} {limit_type}",
                current_usage=current,
                limit=limit
            )

        return FeatureAccess(
            allowed=True,
            current_usage=current,
            limit=limit
        )

    async def increment_usage(
        self,
        user_id: str,
        usage_type: str,
        amount: int = 1
    ):
        """Increment usage counter"""
        if user_id not in self.usage_tracking:
            self.usage_tracking[user_id] = {}
        if usage_type not in self.usage_tracking[user_id]:
            self.usage_tracking[user_id][usage_type] = 0
        self.usage_tracking[user_id][usage_type] += amount

    async def reset_monthly_usage(self, user_id: str):
        """Reset monthly usage counters"""
        self.usage_tracking[user_id] = {}

    # =========================================================================
    # REWARDS INTEGRATION
    # =========================================================================

    async def get_tier_benefits(
        self,
        user_id: str
    ) -> Dict[str, Any]:
        """Get all benefits for user's tier"""
        sub = await self.get_subscription(user_id)
        benefits = TIER_BENEFITS[sub.tier]

        return {
            "tier": sub.tier.value,
            "is_active": sub.is_active,
            "expires_at": sub.expires_at.isoformat() if sub.expires_at else None,
            "benefits": {
                "features": benefits.features,
                "api_rate_limit": benefits.api_rate_limit,
                "ai_credits_monthly": benefits.ai_credits_monthly,
                "max_portfolios": benefits.max_portfolios,
                "max_strategies": benefits.max_strategies,
                "trading_fee_discount_bps": benefits.trading_fee_discount,
                "staking_apy_boost_bps": benefits.staking_apy_boost,
                "priority_support": benefits.priority_support
            }
        }

    async def apply_fee_discount(
        self,
        user_id: str,
        base_fee: int
    ) -> int:
        """Apply tier-based fee discount"""
        sub = await self.get_subscription(user_id)
        benefits = TIER_BENEFITS[sub.tier]

        discount = benefits.trading_fee_discount
        discounted = base_fee * (10000 - discount) // 10000
        return discounted

    async def get_apy_boost(self, user_id: str) -> int:
        """Get APY boost in basis points"""
        sub = await self.get_subscription(user_id)
        benefits = TIER_BENEFITS[sub.tier]
        return benefits.staking_apy_boost

    # =========================================================================
    # INTERNAL
    # =========================================================================

    async def _init_subscription(self, user_id: str):
        """Initialize a new user subscription"""
        self.subscriptions[user_id] = UserSubscription(
            user_id=user_id,
            wallet="",
            tier=SubscriptionTier.FREE,
            started_at=datetime.utcnow()
        )

        # Sync with staking if available
        await self.sync_stake_tier(user_id)

    def _get_required_stake(self, tier: SubscriptionTier) -> int:
        """Get required stake amount for tier"""
        for threshold, t in sorted(STAKE_TIER_THRESHOLDS.items(), reverse=True):
            if t == tier:
                return int(threshold * 10**9)
        return 0


# =============================================================================
# API ENDPOINTS
# =============================================================================

def create_tier_endpoints(manager: TierManager):
    """Create API endpoints for tier management"""
    from fastapi import APIRouter, HTTPException
    from pydantic import BaseModel

    router = APIRouter(prefix="/api/subscription", tags=["Subscriptions"])

    class UpgradeRequest(BaseModel):
        tier: str
        payment_method: str = "token"

    class TrialRequest(BaseModel):
        tier: str
        days: int = 7

    @router.get("/{user_id}")
    async def get_subscription(user_id: str):
        """Get user's subscription"""
        sub = await manager.get_subscription(user_id)
        return {
            "user_id": sub.user_id,
            "tier": sub.tier.value,
            "is_active": sub.is_active,
            "started_at": sub.started_at.isoformat(),
            "expires_at": sub.expires_at.isoformat() if sub.expires_at else None,
            "days_remaining": sub.days_remaining,
            "auto_renew": sub.auto_renew,
            "payment_method": sub.payment_method,
            "token_stake": sub.token_stake_amount
        }

    @router.get("/{user_id}/benefits")
    async def get_benefits(user_id: str):
        """Get user's tier benefits"""
        return await manager.get_tier_benefits(user_id)

    @router.post("/{user_id}/upgrade")
    async def upgrade(user_id: str, request: UpgradeRequest):
        """Upgrade subscription"""
        try:
            sub = await manager.upgrade_tier(
                user_id,
                SubscriptionTier(request.tier),
                request.payment_method
            )
            return {"status": "upgraded", "tier": sub.tier.value}
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

    @router.post("/{user_id}/trial")
    async def start_trial(user_id: str, request: TrialRequest):
        """Start free trial"""
        try:
            sub = await manager.start_trial(
                user_id,
                SubscriptionTier(request.tier),
                request.days
            )
            return {
                "status": "trial_started",
                "tier": sub.tier.value,
                "ends": sub.trial_ends.isoformat()
            }
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

    @router.post("/{user_id}/cancel")
    async def cancel(user_id: str):
        """Cancel subscription"""
        sub = await manager.cancel_subscription(user_id)
        return {
            "status": "cancelled",
            "expires_at": sub.expires_at.isoformat() if sub.expires_at else None
        }

    @router.get("/{user_id}/check/{feature}")
    async def check_feature(user_id: str, feature: str):
        """Check feature access"""
        access = await manager.check_feature_access(user_id, feature)
        return {
            "allowed": access.allowed,
            "reason": access.reason,
            "upgrade_tier": access.upgrade_tier.value if access.upgrade_tier else None
        }

    @router.get("/tiers")
    async def list_tiers():
        """List all available tiers"""
        return [
            {
                "tier": tier.value,
                "price_usd": benefits.monthly_price_usd,
                "features": list(benefits.features.keys()),
                "ai_credits": benefits.ai_credits_monthly,
                "fee_discount_bps": benefits.trading_fee_discount
            }
            for tier, benefits in TIER_BENEFITS.items()
        ]

    return router
