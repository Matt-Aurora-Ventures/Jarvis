"""
User Factory

Factory classes for generating user-related test data.
"""

from dataclasses import dataclass
from typing import Optional, List
from datetime import datetime
from enum import Enum

from .base import BaseFactory, RandomData, SequenceGenerator


class UserRole(Enum):
    """User roles for testing."""
    USER = "user"
    ADMIN = "admin"
    MODERATOR = "moderator"


@dataclass
class User:
    """User model for testing."""
    id: str
    username: str
    email: str
    full_name: str
    role: UserRole
    telegram_id: Optional[int]
    twitter_id: Optional[str]
    wallet_address: Optional[str]
    is_active: bool
    created_at: datetime
    last_login: Optional[datetime]


class UserFactory(BaseFactory[User]):
    """Factory for creating User test instances."""

    @classmethod
    def _build(
        cls,
        id: Optional[str] = None,
        username: Optional[str] = None,
        email: Optional[str] = None,
        full_name: Optional[str] = None,
        role: UserRole = UserRole.USER,
        telegram_id: Optional[int] = None,
        twitter_id: Optional[str] = None,
        wallet_address: Optional[str] = None,
        is_active: bool = True,
        created_at: Optional[datetime] = None,
        last_login: Optional[datetime] = None,
        **kwargs
    ) -> User:
        """Build a User instance."""
        seq = SequenceGenerator.next("user")

        return User(
            id=id or RandomData.uuid(),
            username=username or f"user_{seq}",
            email=email or f"user{seq}@test.com",
            full_name=full_name or RandomData.full_name(),
            role=role,
            telegram_id=telegram_id,
            twitter_id=twitter_id,
            wallet_address=wallet_address,
            is_active=is_active,
            created_at=created_at or datetime.utcnow(),
            last_login=last_login,
        )


class AdminUserFactory(UserFactory):
    """Factory for creating admin users."""

    @classmethod
    def _build(cls, **kwargs) -> User:
        kwargs.setdefault('role', UserRole.ADMIN)
        kwargs.setdefault('username', f"admin_{SequenceGenerator.next('admin')}")
        return super()._build(**kwargs)


class TelegramUserFactory(UserFactory):
    """Factory for creating users with Telegram integration."""

    @classmethod
    def _build(cls, **kwargs) -> User:
        kwargs.setdefault('telegram_id', RandomData.telegram_id())
        return super()._build(**kwargs)


class TwitterUserFactory(UserFactory):
    """Factory for creating users with Twitter integration."""

    @classmethod
    def _build(cls, **kwargs) -> User:
        kwargs.setdefault('twitter_id', RandomData.twitter_id())
        return super()._build(**kwargs)


class WalletUserFactory(UserFactory):
    """Factory for creating users with wallet integration."""

    @classmethod
    def _build(cls, **kwargs) -> User:
        kwargs.setdefault('wallet_address', RandomData.wallet_address())
        return super()._build(**kwargs)


@dataclass
class APIKey:
    """API key model for testing."""
    id: str
    user_id: str
    key: str
    name: str
    scopes: List[str]
    is_active: bool
    created_at: datetime
    expires_at: Optional[datetime]
    last_used: Optional[datetime]


class APIKeyFactory(BaseFactory[APIKey]):
    """Factory for creating API key test instances."""

    @classmethod
    def _build(
        cls,
        id: Optional[str] = None,
        user_id: Optional[str] = None,
        key: Optional[str] = None,
        name: Optional[str] = None,
        scopes: Optional[List[str]] = None,
        is_active: bool = True,
        created_at: Optional[datetime] = None,
        expires_at: Optional[datetime] = None,
        last_used: Optional[datetime] = None,
        **kwargs
    ) -> APIKey:
        """Build an API key instance."""
        seq = SequenceGenerator.next("apikey")

        return APIKey(
            id=id or RandomData.uuid(),
            user_id=user_id or RandomData.uuid(),
            key=key or f"jrv_{RandomData.string(32)}",
            name=name or f"Test Key {seq}",
            scopes=scopes or ["read"],
            is_active=is_active,
            created_at=created_at or datetime.utcnow(),
            expires_at=expires_at,
            last_used=last_used,
        )


class ReadOnlyAPIKeyFactory(APIKeyFactory):
    """Factory for read-only API keys."""

    @classmethod
    def _build(cls, **kwargs) -> APIKey:
        kwargs.setdefault('scopes', ["read"])
        return super()._build(**kwargs)


class AdminAPIKeyFactory(APIKeyFactory):
    """Factory for admin API keys."""

    @classmethod
    def _build(cls, **kwargs) -> APIKey:
        kwargs.setdefault('scopes', ["read", "write", "admin"])
        return super()._build(**kwargs)
