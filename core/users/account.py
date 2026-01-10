"""
User Account Management

Wallet-based user accounts with profile management.
No KYC - wallet verification only.

Prompts #36-40: Business Model
"""

import asyncio
import logging
import json
import hashlib
import secrets
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Any
from enum import Enum
from pathlib import Path

logger = logging.getLogger(__name__)


class UserStatus(str, Enum):
    """User account status"""
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"
    PENDING = "pending"


class AuthProvider(str, Enum):
    """Authentication providers"""
    WALLET = "wallet"         # Solana wallet signature
    TWITTER = "twitter"       # Twitter OAuth
    DISCORD = "discord"       # Discord OAuth
    TELEGRAM = "telegram"     # Telegram login


@dataclass
class UserProfile:
    """User profile information"""
    display_name: str = ""
    bio: str = ""
    avatar_url: str = ""
    twitter_handle: Optional[str] = None
    discord_id: Optional[str] = None
    telegram_id: Optional[str] = None
    website: Optional[str] = None
    is_public: bool = True
    show_portfolio: bool = False
    show_trades: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "display_name": self.display_name,
            "bio": self.bio,
            "avatar_url": self.avatar_url,
            "twitter_handle": self.twitter_handle,
            "discord_id": self.discord_id,
            "telegram_id": self.telegram_id,
            "website": self.website,
            "is_public": self.is_public,
            "show_portfolio": self.show_portfolio,
            "show_trades": self.show_trades
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "UserProfile":
        """Create from dictionary"""
        return cls(
            display_name=data.get("display_name", ""),
            bio=data.get("bio", ""),
            avatar_url=data.get("avatar_url", ""),
            twitter_handle=data.get("twitter_handle"),
            discord_id=data.get("discord_id"),
            telegram_id=data.get("telegram_id"),
            website=data.get("website"),
            is_public=data.get("is_public", True),
            show_portfolio=data.get("show_portfolio", False),
            show_trades=data.get("show_trades", False)
        )


@dataclass
class UserSettings:
    """User settings and preferences"""
    # Notifications
    email_alerts: bool = True
    push_alerts: bool = True
    telegram_alerts: bool = True
    discord_alerts: bool = True

    # Alert preferences
    price_alerts: bool = True
    whale_alerts: bool = True
    signal_alerts: bool = True

    # Privacy
    anonymous_analytics: bool = True
    share_trade_data: bool = False

    # Trading
    default_slippage: float = 1.0
    confirm_trades: bool = True
    auto_dca: bool = False

    # Display
    currency: str = "USD"
    timezone: str = "UTC"
    language: str = "en"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "email_alerts": self.email_alerts,
            "push_alerts": self.push_alerts,
            "telegram_alerts": self.telegram_alerts,
            "discord_alerts": self.discord_alerts,
            "price_alerts": self.price_alerts,
            "whale_alerts": self.whale_alerts,
            "signal_alerts": self.signal_alerts,
            "anonymous_analytics": self.anonymous_analytics,
            "share_trade_data": self.share_trade_data,
            "default_slippage": self.default_slippage,
            "confirm_trades": self.confirm_trades,
            "auto_dca": self.auto_dca,
            "currency": self.currency,
            "timezone": self.timezone,
            "language": self.language
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "UserSettings":
        """Create from dictionary"""
        return cls(**{k: v for k, v in data.items() if hasattr(cls, k)})


@dataclass
class User:
    """A JARVIS user account"""
    user_id: str
    primary_wallet: str
    status: UserStatus = UserStatus.ACTIVE
    profile: UserProfile = field(default_factory=UserProfile)
    settings: UserSettings = field(default_factory=UserSettings)

    # Linked accounts
    linked_wallets: List[str] = field(default_factory=list)
    auth_providers: List[AuthProvider] = field(default_factory=list)

    # Subscription
    subscription_tier: str = "free"
    subscription_expires: Optional[datetime] = None

    # Referral
    referral_code: str = ""
    referred_by: Optional[str] = None
    referral_count: int = 0

    # Metadata
    created_at: datetime = field(default_factory=datetime.now)
    last_login: datetime = field(default_factory=datetime.now)
    login_count: int = 0
    api_key: Optional[str] = None

    def __post_init__(self):
        if not self.user_id:
            data = f"{self.primary_wallet}{self.created_at.isoformat()}"
            self.user_id = f"USER-{hashlib.sha256(data.encode()).hexdigest()[:12].upper()}"

        if not self.referral_code:
            self.referral_code = hashlib.sha256(
                f"{self.user_id}{secrets.token_hex(8)}".encode()
            ).hexdigest()[:8].upper()

        if not self.profile.display_name:
            self.profile.display_name = f"User_{self.user_id[-6:]}"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "user_id": self.user_id,
            "primary_wallet": self.primary_wallet,
            "status": self.status.value,
            "profile": self.profile.to_dict(),
            "settings": self.settings.to_dict(),
            "linked_wallets": self.linked_wallets,
            "auth_providers": [p.value for p in self.auth_providers],
            "subscription_tier": self.subscription_tier,
            "subscription_expires": self.subscription_expires.isoformat() if self.subscription_expires else None,
            "referral_code": self.referral_code,
            "referred_by": self.referred_by,
            "referral_count": self.referral_count,
            "created_at": self.created_at.isoformat(),
            "last_login": self.last_login.isoformat(),
            "login_count": self.login_count,
            "api_key": self.api_key
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "User":
        """Create from dictionary"""
        return cls(
            user_id=data["user_id"],
            primary_wallet=data["primary_wallet"],
            status=UserStatus(data.get("status", "active")),
            profile=UserProfile.from_dict(data.get("profile", {})),
            settings=UserSettings.from_dict(data.get("settings", {})),
            linked_wallets=data.get("linked_wallets", []),
            auth_providers=[AuthProvider(p) for p in data.get("auth_providers", [])],
            subscription_tier=data.get("subscription_tier", "free"),
            subscription_expires=datetime.fromisoformat(data["subscription_expires"]) if data.get("subscription_expires") else None,
            referral_code=data.get("referral_code", ""),
            referred_by=data.get("referred_by"),
            referral_count=data.get("referral_count", 0),
            created_at=datetime.fromisoformat(data["created_at"]) if data.get("created_at") else datetime.now(),
            last_login=datetime.fromisoformat(data["last_login"]) if data.get("last_login") else datetime.now(),
            login_count=data.get("login_count", 0),
            api_key=data.get("api_key")
        )

    def is_premium(self) -> bool:
        """Check if user has premium subscription"""
        if self.subscription_tier == "free":
            return False
        if self.subscription_expires and datetime.now() > self.subscription_expires:
            return False
        return True

    def has_feature(self, feature: str) -> bool:
        """Check if user has access to a feature based on tier"""
        # Would integrate with feature flags
        tier_features = {
            "free": ["basic_alerts", "portfolio_tracking"],
            "pro": ["basic_alerts", "portfolio_tracking", "whale_alerts", "signals", "copy_trading"],
            "whale": ["basic_alerts", "portfolio_tracking", "whale_alerts", "signals", "copy_trading", "api_access", "priority_support"]
        }
        features = tier_features.get(self.subscription_tier, tier_features["free"])
        return feature in features

    def generate_api_key(self) -> str:
        """Generate a new API key"""
        self.api_key = f"jrv_{secrets.token_hex(32)}"
        return self.api_key


class UserManager:
    """
    Manages user accounts

    Handles registration, authentication, and profile management.
    """

    def __init__(self, storage_path: str = "data/users/users.json"):
        self.storage_path = Path(storage_path)
        self.users: Dict[str, User] = {}
        self.users_by_wallet: Dict[str, str] = {}  # wallet -> user_id
        self.users_by_referral: Dict[str, str] = {}  # referral_code -> user_id
        self._load()

    def _load(self):
        """Load users from storage"""
        if not self.storage_path.exists():
            return

        try:
            with open(self.storage_path) as f:
                data = json.load(f)

            for user_data in data.get("users", []):
                user = User.from_dict(user_data)
                self.users[user.user_id] = user
                self.users_by_wallet[user.primary_wallet] = user.user_id
                self.users_by_referral[user.referral_code] = user.user_id

                for wallet in user.linked_wallets:
                    self.users_by_wallet[wallet] = user.user_id

            logger.info(f"Loaded {len(self.users)} users")

        except Exception as e:
            logger.error(f"Failed to load users: {e}")

    def _save(self):
        """Save users to storage"""
        try:
            self.storage_path.parent.mkdir(parents=True, exist_ok=True)

            data = {
                "users": [u.to_dict() for u in self.users.values()],
                "updated_at": datetime.now().isoformat()
            }

            with open(self.storage_path, "w") as f:
                json.dump(data, f, indent=2)

        except Exception as e:
            logger.error(f"Failed to save users: {e}")
            raise

    async def register(
        self,
        wallet: str,
        display_name: Optional[str] = None,
        referral_code: Optional[str] = None
    ) -> Optional[User]:
        """Register a new user"""
        # Check if wallet already registered
        if wallet in self.users_by_wallet:
            logger.warning(f"Wallet {wallet} already registered")
            return None

        # Handle referral
        referred_by = None
        if referral_code and referral_code in self.users_by_referral:
            referrer_id = self.users_by_referral[referral_code]
            referred_by = referrer_id

            # Increment referrer's count
            referrer = self.users.get(referrer_id)
            if referrer:
                referrer.referral_count += 1

        # Create user
        user = User(
            user_id="",
            primary_wallet=wallet,
            referred_by=referred_by
        )

        if display_name:
            user.profile.display_name = display_name

        user.auth_providers.append(AuthProvider.WALLET)

        # Store
        self.users[user.user_id] = user
        self.users_by_wallet[wallet] = user.user_id
        self.users_by_referral[user.referral_code] = user.user_id
        self._save()

        logger.info(f"Registered new user: {user.user_id}")
        return user

    async def authenticate(
        self,
        wallet: str,
        signature: Optional[str] = None,
        message: Optional[str] = None
    ) -> Optional[User]:
        """
        Authenticate a user by wallet

        In production, would verify signature against message.
        """
        user_id = self.users_by_wallet.get(wallet)
        if not user_id:
            return None

        user = self.users.get(user_id)
        if not user or user.status != UserStatus.ACTIVE:
            return None

        # TODO: Verify signature in production
        # For now, just trust the wallet address

        # Update login stats
        user.last_login = datetime.now()
        user.login_count += 1
        self._save()

        return user

    async def get_user(self, user_id: str) -> Optional[User]:
        """Get a user by ID"""
        return self.users.get(user_id)

    async def get_user_by_wallet(self, wallet: str) -> Optional[User]:
        """Get a user by wallet address"""
        user_id = self.users_by_wallet.get(wallet)
        if user_id:
            return self.users.get(user_id)
        return None

    async def update_profile(
        self,
        user_id: str,
        profile_updates: Dict[str, Any]
    ) -> bool:
        """Update user profile"""
        user = self.users.get(user_id)
        if not user:
            return False

        for key, value in profile_updates.items():
            if hasattr(user.profile, key):
                setattr(user.profile, key, value)

        self._save()
        return True

    async def update_settings(
        self,
        user_id: str,
        settings_updates: Dict[str, Any]
    ) -> bool:
        """Update user settings"""
        user = self.users.get(user_id)
        if not user:
            return False

        for key, value in settings_updates.items():
            if hasattr(user.settings, key):
                setattr(user.settings, key, value)

        self._save()
        return True

    async def link_wallet(self, user_id: str, wallet: str) -> bool:
        """Link an additional wallet to user"""
        user = self.users.get(user_id)
        if not user:
            return False

        if wallet in self.users_by_wallet:
            logger.warning(f"Wallet {wallet} already linked to another user")
            return False

        user.linked_wallets.append(wallet)
        self.users_by_wallet[wallet] = user_id
        self._save()

        return True

    async def link_social(
        self,
        user_id: str,
        provider: AuthProvider,
        social_id: str
    ) -> bool:
        """Link a social account"""
        user = self.users.get(user_id)
        if not user:
            return False

        if provider == AuthProvider.TWITTER:
            user.profile.twitter_handle = social_id
        elif provider == AuthProvider.DISCORD:
            user.profile.discord_id = social_id
        elif provider == AuthProvider.TELEGRAM:
            user.profile.telegram_id = social_id

        if provider not in user.auth_providers:
            user.auth_providers.append(provider)

        self._save()
        return True

    async def update_subscription(
        self,
        user_id: str,
        tier: str,
        expires: Optional[datetime] = None
    ) -> bool:
        """Update user subscription"""
        user = self.users.get(user_id)
        if not user:
            return False

        user.subscription_tier = tier
        user.subscription_expires = expires
        self._save()

        logger.info(f"Updated subscription for {user_id}: {tier}")
        return True

    async def suspend_user(self, user_id: str, reason: str = "") -> bool:
        """Suspend a user account"""
        user = self.users.get(user_id)
        if not user:
            return False

        user.status = UserStatus.SUSPENDED
        self._save()

        logger.warning(f"Suspended user {user_id}: {reason}")
        return True

    async def generate_api_key(self, user_id: str) -> Optional[str]:
        """Generate API key for user"""
        user = self.users.get(user_id)
        if not user:
            return None

        if not user.is_premium():
            logger.warning(f"User {user_id} not premium, cannot generate API key")
            return None

        api_key = user.generate_api_key()
        self._save()

        return api_key

    def get_stats(self) -> Dict[str, Any]:
        """Get user statistics"""
        total = len(self.users)
        active = sum(1 for u in self.users.values() if u.status == UserStatus.ACTIVE)

        by_tier = {}
        for user in self.users.values():
            tier = user.subscription_tier
            by_tier[tier] = by_tier.get(tier, 0) + 1

        return {
            "total_users": total,
            "active_users": active,
            "by_tier": by_tier,
            "premium_users": sum(1 for u in self.users.values() if u.is_premium()),
            "total_referrals": sum(u.referral_count for u in self.users.values())
        }


# Singleton instance
_user_manager: Optional[UserManager] = None


def get_user_manager() -> UserManager:
    """Get user manager singleton"""
    global _user_manager

    if _user_manager is None:
        _user_manager = UserManager()

    return _user_manager


# Testing
if __name__ == "__main__":
    async def test():
        manager = UserManager("test_users.json")

        # Register user
        user = await manager.register(
            wallet="WALLET_123456789",
            display_name="TestUser"
        )
        print(f"Registered: {user.user_id}")

        # Authenticate
        auth_user = await manager.authenticate("WALLET_123456789")
        print(f"Authenticated: {auth_user.user_id}")

        # Update profile
        await manager.update_profile(user.user_id, {
            "bio": "JARVIS trader",
            "twitter_handle": "@testuser"
        })

        # Check premium
        print(f"Is premium: {user.is_premium()}")

        # Update subscription
        await manager.update_subscription(
            user.user_id,
            "pro",
            datetime.now() + timedelta(days=30)
        )
        print(f"Is premium after upgrade: {user.is_premium()}")

        # Stats
        print(f"Stats: {manager.get_stats()}")

        # Clean up
        import os
        os.remove("test_users.json")

    asyncio.run(test())
