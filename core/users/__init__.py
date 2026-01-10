"""
JARVIS User Management System

User accounts, authentication, and profile management.
Wallet-based authentication with optional social login.

Prompts #36-40: Business Model
"""

from .account import (
    User,
    UserProfile,
    UserStatus,
    UserManager,
    get_user_manager,
)
from .subscriptions import (
    Subscription,
    SubscriptionTier,
    SubscriptionStatus,
    SubscriptionManager,
    get_subscription_manager,
)
from .features import (
    FeatureFlag,
    FeatureFlags,
    get_feature_flags,
)

__all__ = [
    # Users
    "User",
    "UserProfile",
    "UserStatus",
    "UserManager",
    "get_user_manager",
    # Subscriptions
    "Subscription",
    "SubscriptionTier",
    "SubscriptionStatus",
    "SubscriptionManager",
    "get_subscription_manager",
    # Features
    "FeatureFlag",
    "FeatureFlags",
    "get_feature_flags",
]
