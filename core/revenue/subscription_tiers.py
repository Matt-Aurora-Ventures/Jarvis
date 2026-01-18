"""
Subscription Tiers - Manage user subscription plans.

Tiers:
- Free: 5 positions, 1 analysis/day
- Pro: Unlimited positions, 100 analyses/day, $29/mo
- Enterprise: Custom features, dedicated bot, $299/mo
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional


# Tier definitions
TIERS = {
    'free': {
        'name': 'free',
        'max_positions': 5,
        'analyses_per_day': 1,
        'price_usd': 0.0,
        'priority_support': False,
        'dedicated_bot': False,
        'white_label': False,
    },
    'pro': {
        'name': 'pro',
        'max_positions': -1,  # Unlimited
        'analyses_per_day': 100,
        'price_usd': 29.0,
        'priority_support': True,
        'dedicated_bot': False,
        'white_label': False,
    },
    'enterprise': {
        'name': 'enterprise',
        'max_positions': -1,  # Unlimited
        'analyses_per_day': -1,  # Unlimited
        'price_usd': 299.0,
        'priority_support': True,
        'dedicated_bot': True,
        'white_label': True,
    },
}


@dataclass
class Subscription:
    """A user subscription."""
    user_id: str
    tier: str
    started_at: float = field(default_factory=time.time)
    expires_at: Optional[float] = None
    auto_renew: bool = False
    payment_method: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @property
    def is_active(self) -> bool:
        """Check if subscription is active."""
        if self.tier == 'free':
            return True
        if self.expires_at is None:
            return True
        # Use <= to ensure expired subscriptions are caught immediately
        return time.time() < self.expires_at

    @property
    def is_expired(self) -> bool:
        """Check if subscription has expired."""
        if self.tier == 'free':
            return False
        if self.expires_at is None:
            return False
        return time.time() >= self.expires_at


class SubscriptionManager:
    """
    Manages user subscriptions.

    Usage:
        manager = SubscriptionManager()

        # Check user's tier
        tier = manager.get_user_tier("user_1")

        # Upgrade user
        manager.upgrade_user("user_1", "pro")

        # Check position limit
        can_open = manager.can_open_position("user_1", current_positions=3)
    """

    def __init__(self, data_dir: Optional[Path] = None):
        if data_dir:
            self.data_dir = Path(data_dir)
        else:
            self.data_dir = Path(__file__).resolve().parents[2] / "data" / "revenue"

        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.subscriptions_file = self.data_dir / "subscriptions.json"

        # Load subscriptions
        self._subscriptions: Dict[str, Subscription] = self._load_subscriptions()

    def _load_subscriptions(self) -> Dict[str, Subscription]:
        """Load subscriptions from file."""
        if self.subscriptions_file.exists():
            try:
                data = json.loads(self.subscriptions_file.read_text())
                return {
                    k: Subscription(**v)
                    for k, v in data.items()
                    if k != '_metadata'
                }
            except json.JSONDecodeError:
                return {}
        return {}

    def _save_subscriptions(self) -> None:
        """Save subscriptions to file."""
        data = {k: v.to_dict() for k, v in self._subscriptions.items()}
        data['_metadata'] = {'updated_at': time.time()}
        self.subscriptions_file.write_text(json.dumps(data, indent=2))

    def get_user_tier(self, user_id: str) -> Dict[str, Any]:
        """
        Get user's current subscription tier.

        Args:
            user_id: User identifier

        Returns:
            Tier details
        """
        subscription = self._subscriptions.get(user_id)

        if subscription and subscription.is_active:
            tier_name = subscription.tier
        else:
            tier_name = 'free'

        tier = TIERS.get(tier_name, TIERS['free']).copy()

        # Add subscription info
        if subscription:
            tier['expires_at'] = subscription.expires_at
            tier['started_at'] = subscription.started_at
            tier['auto_renew'] = subscription.auto_renew

        return tier

    def upgrade_user(
        self,
        user_id: str,
        tier: str,
        duration_days: int = 30,
        payment_method: Optional[str] = None
    ) -> Subscription:
        """
        Upgrade user to a new tier.

        Args:
            user_id: User identifier
            tier: Target tier ('pro' or 'enterprise')
            duration_days: Subscription duration in days
            payment_method: Payment method used

        Returns:
            Created subscription
        """
        if tier not in TIERS:
            raise ValueError(f"Invalid tier: {tier}")

        expires_at = None
        if duration_days == 0:
            # Special case: 0 means expire immediately (for testing)
            expires_at = time.time() - 1  # Already expired
        elif duration_days > 0:
            expires_at = time.time() + (duration_days * 86400)

        subscription = Subscription(
            user_id=user_id,
            tier=tier,
            expires_at=expires_at,
            payment_method=payment_method,
        )

        self._subscriptions[user_id] = subscription
        self._save_subscriptions()

        return subscription

    def downgrade_user(self, user_id: str) -> None:
        """
        Downgrade user to free tier.

        Args:
            user_id: User identifier
        """
        if user_id in self._subscriptions:
            self._subscriptions[user_id].tier = 'free'
            self._subscriptions[user_id].expires_at = None
            self._save_subscriptions()

    def can_open_position(
        self,
        user_id: str,
        current_positions: int
    ) -> bool:
        """
        Check if user can open a new position.

        Args:
            user_id: User identifier
            current_positions: Current number of open positions

        Returns:
            True if user can open position
        """
        tier = self.get_user_tier(user_id)
        max_positions = tier.get('max_positions', 5)

        if max_positions < 0:  # Unlimited
            return True

        return current_positions < max_positions

    def can_run_analysis(
        self,
        user_id: str,
        analyses_today: int
    ) -> bool:
        """
        Check if user can run analysis.

        Args:
            user_id: User identifier
            analyses_today: Number of analyses run today

        Returns:
            True if user can run analysis
        """
        tier = self.get_user_tier(user_id)
        max_analyses = tier.get('analyses_per_day', 1)

        if max_analyses < 0:  # Unlimited
            return True

        return analyses_today < max_analyses

    def check_expirations(self) -> List[str]:
        """
        Check and process expired subscriptions.

        Returns:
            List of user IDs that were downgraded
        """
        downgraded = []
        now = time.time()

        for user_id, subscription in self._subscriptions.items():
            if (
                subscription.tier != 'free' and
                subscription.expires_at is not None and
                subscription.expires_at <= now
            ):
                if subscription.auto_renew:
                    # In production, attempt to charge
                    # For now, just extend
                    subscription.expires_at = now + (30 * 86400)
                else:
                    subscription.tier = 'free'
                    subscription.expires_at = None
                    downgraded.append(user_id)

        if downgraded:
            self._save_subscriptions()

        return downgraded

    def get_subscribers(self, tier: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get list of subscribers.

        Args:
            tier: Filter by tier (optional)

        Returns:
            List of subscription details
        """
        subscribers = []

        for user_id, subscription in self._subscriptions.items():
            if tier and subscription.tier != tier:
                continue
            if not subscription.is_active:
                continue

            subscribers.append({
                'user_id': user_id,
                **subscription.to_dict(),
                **self.get_user_tier(user_id),
            })

        return subscribers

    def get_revenue_summary(self) -> Dict[str, Any]:
        """
        Get subscription revenue summary.

        Returns:
            Revenue breakdown by tier
        """
        summary = {
            'total_subscribers': 0,
            'by_tier': {},
            'monthly_revenue': 0.0,
        }

        for subscription in self._subscriptions.values():
            if not subscription.is_active or subscription.tier == 'free':
                continue

            tier_name = subscription.tier
            tier_info = TIERS.get(tier_name, {})
            price = tier_info.get('price_usd', 0)

            if tier_name not in summary['by_tier']:
                summary['by_tier'][tier_name] = {
                    'count': 0,
                    'price': price,
                    'revenue': 0.0,
                }

            summary['by_tier'][tier_name]['count'] += 1
            summary['by_tier'][tier_name]['revenue'] += price
            summary['total_subscribers'] += 1
            summary['monthly_revenue'] += price

        return summary
