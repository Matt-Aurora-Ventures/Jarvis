"""
Feature Flags System

Dynamic feature flag management for gradual rollouts,
A/B testing, and user-specific feature access.

Prompts #36-40: Business Model
"""

import asyncio
import logging
import json
import hashlib
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Dict, List, Any, Set
from enum import Enum
from pathlib import Path

logger = logging.getLogger(__name__)


class FeatureState(str, Enum):
    """Feature flag states"""
    DISABLED = "disabled"          # Off for everyone
    ENABLED = "enabled"            # On for everyone
    PERCENTAGE = "percentage"      # On for X% of users
    ALLOWLIST = "allowlist"        # On for specific users
    TIER_GATED = "tier_gated"      # On for specific tiers


@dataclass
class FeatureFlag:
    """A feature flag configuration"""
    flag_id: str
    name: str
    description: str
    state: FeatureState = FeatureState.DISABLED

    # Rollout settings
    percentage: float = 0.0              # For PERCENTAGE state
    allowed_users: List[str] = field(default_factory=list)  # For ALLOWLIST
    allowed_tiers: List[str] = field(default_factory=list)  # For TIER_GATED

    # Metadata
    category: str = "general"
    owner: str = ""
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    expires_at: Optional[datetime] = None

    # Tracking
    evaluation_count: int = 0
    enabled_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "flag_id": self.flag_id,
            "name": self.name,
            "description": self.description,
            "state": self.state.value,
            "percentage": self.percentage,
            "allowed_users": self.allowed_users,
            "allowed_tiers": self.allowed_tiers,
            "category": self.category,
            "owner": self.owner,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "evaluation_count": self.evaluation_count,
            "enabled_count": self.enabled_count
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "FeatureFlag":
        """Create from dictionary"""
        return cls(
            flag_id=data["flag_id"],
            name=data["name"],
            description=data.get("description", ""),
            state=FeatureState(data.get("state", "disabled")),
            percentage=data.get("percentage", 0.0),
            allowed_users=data.get("allowed_users", []),
            allowed_tiers=data.get("allowed_tiers", []),
            category=data.get("category", "general"),
            owner=data.get("owner", ""),
            created_at=datetime.fromisoformat(data["created_at"]) if data.get("created_at") else datetime.now(),
            updated_at=datetime.fromisoformat(data["updated_at"]) if data.get("updated_at") else datetime.now(),
            expires_at=datetime.fromisoformat(data["expires_at"]) if data.get("expires_at") else None,
            evaluation_count=data.get("evaluation_count", 0),
            enabled_count=data.get("enabled_count", 0)
        )

    def is_expired(self) -> bool:
        """Check if feature flag has expired"""
        if self.expires_at:
            return datetime.now() > self.expires_at
        return False


class FeatureFlags:
    """
    Feature flag management system

    Evaluates feature flags for users based on various criteria.
    """

    def __init__(self, storage_path: str = "data/features/flags.json"):
        self.storage_path = Path(storage_path)
        self.flags: Dict[str, FeatureFlag] = {}
        self.overrides: Dict[str, Dict[str, bool]] = {}  # user_id -> {flag_id: bool}
        self._load()
        self._init_default_flags()

    def _init_default_flags(self):
        """Initialize default feature flags"""
        default_flags = [
            FeatureFlag(
                flag_id="copy_trading",
                name="Copy Trading",
                description="Enable copy trading feature",
                state=FeatureState.DISABLED,  # DISABLED until audited
                category="trading"
            ),
            FeatureFlag(
                flag_id="whale_alerts",
                name="Whale Alerts",
                description="Real-time whale activity alerts",
                state=FeatureState.TIER_GATED,
                allowed_tiers=["starter", "pro", "whale", "enterprise"],
                category="alerts"
            ),
            FeatureFlag(
                flag_id="api_access",
                name="API Access",
                description="Programmatic API access",
                state=FeatureState.TIER_GATED,
                allowed_tiers=["pro", "whale", "enterprise"],
                category="developer"
            ),
            FeatureFlag(
                flag_id="real_time_signals",
                name="Real-Time Signals",
                description="Zero delay trading signals",
                state=FeatureState.TIER_GATED,
                allowed_tiers=["pro", "whale", "enterprise"],
                category="signals"
            ),
            FeatureFlag(
                flag_id="portfolio_sharing",
                name="Portfolio Sharing",
                description="Share portfolio publicly",
                state=FeatureState.ENABLED,
                category="social"
            ),
            FeatureFlag(
                flag_id="dark_mode",
                name="Dark Mode",
                description="Dark theme UI",
                state=FeatureState.ENABLED,
                category="ui"
            ),
            FeatureFlag(
                flag_id="beta_features",
                name="Beta Features",
                description="Access to beta features",
                state=FeatureState.PERCENTAGE,
                percentage=10.0,  # 10% of users
                category="beta"
            ),
            FeatureFlag(
                flag_id="governance_voting",
                name="Governance Voting",
                description="Vote on governance proposals",
                state=FeatureState.TIER_GATED,
                allowed_tiers=["whale", "enterprise"],
                category="governance"
            ),
            FeatureFlag(
                flag_id="advanced_analytics",
                name="Advanced Analytics",
                description="Advanced portfolio analytics",
                state=FeatureState.TIER_GATED,
                allowed_tiers=["pro", "whale", "enterprise"],
                category="analytics"
            ),
            FeatureFlag(
                flag_id="auto_dca",
                name="Auto DCA",
                description="Automated dollar-cost averaging",
                state=FeatureState.DISABLED,  # Not yet implemented
                category="trading"
            ),
        ]

        for flag in default_flags:
            if flag.flag_id not in self.flags:
                self.flags[flag.flag_id] = flag

        self._save()

    def _load(self):
        """Load flags from storage"""
        if not self.storage_path.exists():
            return

        try:
            with open(self.storage_path) as f:
                data = json.load(f)

            for flag_data in data.get("flags", []):
                flag = FeatureFlag.from_dict(flag_data)
                self.flags[flag.flag_id] = flag

            self.overrides = data.get("overrides", {})
            logger.info(f"Loaded {len(self.flags)} feature flags")

        except Exception as e:
            logger.error(f"Failed to load feature flags: {e}")

    def _save(self):
        """Save flags to storage"""
        try:
            self.storage_path.parent.mkdir(parents=True, exist_ok=True)

            data = {
                "flags": [f.to_dict() for f in self.flags.values()],
                "overrides": self.overrides,
                "updated_at": datetime.now().isoformat()
            }

            with open(self.storage_path, "w") as f:
                json.dump(data, f, indent=2)

        except Exception as e:
            logger.error(f"Failed to save feature flags: {e}")

    def _hash_user_for_percentage(self, user_id: str, flag_id: str) -> float:
        """Generate consistent hash for user percentage evaluation"""
        data = f"{user_id}:{flag_id}"
        hash_value = int(hashlib.md5(data.encode()).hexdigest(), 16)
        return (hash_value % 100) / 100.0  # 0.0 to 0.99

    async def is_enabled(
        self,
        flag_id: str,
        user_id: Optional[str] = None,
        user_tier: str = "free",
        default: bool = False
    ) -> bool:
        """
        Check if a feature flag is enabled for a user

        Args:
            flag_id: Feature flag ID
            user_id: User ID for evaluation
            user_tier: User's subscription tier
            default: Default value if flag not found
        """
        flag = self.flags.get(flag_id)
        if not flag:
            return default

        # Check expiry
        if flag.is_expired():
            return False

        # Track evaluation
        flag.evaluation_count += 1

        # Check user override first
        if user_id and user_id in self.overrides:
            if flag_id in self.overrides[user_id]:
                result = self.overrides[user_id][flag_id]
                if result:
                    flag.enabled_count += 1
                return result

        # Evaluate based on state
        result = False

        if flag.state == FeatureState.DISABLED:
            result = False

        elif flag.state == FeatureState.ENABLED:
            result = True

        elif flag.state == FeatureState.PERCENTAGE:
            if user_id:
                user_percentage = self._hash_user_for_percentage(user_id, flag_id)
                result = user_percentage < (flag.percentage / 100.0)
            else:
                result = False

        elif flag.state == FeatureState.ALLOWLIST:
            result = user_id in flag.allowed_users if user_id else False

        elif flag.state == FeatureState.TIER_GATED:
            result = user_tier.lower() in [t.lower() for t in flag.allowed_tiers]

        if result:
            flag.enabled_count += 1

        return result

    async def get_enabled_flags(
        self,
        user_id: Optional[str] = None,
        user_tier: str = "free"
    ) -> List[str]:
        """Get all enabled flags for a user"""
        enabled = []

        for flag_id in self.flags:
            if await self.is_enabled(flag_id, user_id, user_tier):
                enabled.append(flag_id)

        return enabled

    async def set_flag_state(
        self,
        flag_id: str,
        state: FeatureState,
        percentage: Optional[float] = None,
        allowed_users: Optional[List[str]] = None,
        allowed_tiers: Optional[List[str]] = None
    ) -> bool:
        """Update a feature flag's state"""
        flag = self.flags.get(flag_id)
        if not flag:
            return False

        flag.state = state
        flag.updated_at = datetime.now()

        if percentage is not None:
            flag.percentage = percentage

        if allowed_users is not None:
            flag.allowed_users = allowed_users

        if allowed_tiers is not None:
            flag.allowed_tiers = allowed_tiers

        self._save()
        logger.info(f"Updated flag {flag_id} to state {state.value}")
        return True

    async def create_flag(
        self,
        flag_id: str,
        name: str,
        description: str = "",
        state: FeatureState = FeatureState.DISABLED,
        category: str = "general",
        owner: str = ""
    ) -> FeatureFlag:
        """Create a new feature flag"""
        flag = FeatureFlag(
            flag_id=flag_id,
            name=name,
            description=description,
            state=state,
            category=category,
            owner=owner
        )

        self.flags[flag_id] = flag
        self._save()

        logger.info(f"Created feature flag: {flag_id}")
        return flag

    async def delete_flag(self, flag_id: str) -> bool:
        """Delete a feature flag"""
        if flag_id not in self.flags:
            return False

        del self.flags[flag_id]

        # Remove from overrides
        for user_overrides in self.overrides.values():
            if flag_id in user_overrides:
                del user_overrides[flag_id]

        self._save()
        logger.info(f"Deleted feature flag: {flag_id}")
        return True

    async def set_user_override(
        self,
        user_id: str,
        flag_id: str,
        enabled: bool
    ):
        """Set a user-specific override for a flag"""
        if user_id not in self.overrides:
            self.overrides[user_id] = {}

        self.overrides[user_id][flag_id] = enabled
        self._save()

        logger.info(f"Set override for {user_id} on {flag_id}: {enabled}")

    async def remove_user_override(self, user_id: str, flag_id: str):
        """Remove a user-specific override"""
        if user_id in self.overrides and flag_id in self.overrides[user_id]:
            del self.overrides[user_id][flag_id]
            self._save()

    async def add_to_allowlist(self, flag_id: str, user_id: str) -> bool:
        """Add a user to a flag's allowlist"""
        flag = self.flags.get(flag_id)
        if not flag:
            return False

        if user_id not in flag.allowed_users:
            flag.allowed_users.append(user_id)
            flag.updated_at = datetime.now()
            self._save()

        return True

    async def remove_from_allowlist(self, flag_id: str, user_id: str) -> bool:
        """Remove a user from a flag's allowlist"""
        flag = self.flags.get(flag_id)
        if not flag:
            return False

        if user_id in flag.allowed_users:
            flag.allowed_users.remove(user_id)
            flag.updated_at = datetime.now()
            self._save()

        return True

    async def get_flag(self, flag_id: str) -> Optional[FeatureFlag]:
        """Get a feature flag by ID"""
        return self.flags.get(flag_id)

    async def list_flags(
        self,
        category: Optional[str] = None,
        state: Optional[FeatureState] = None
    ) -> List[FeatureFlag]:
        """List feature flags with optional filters"""
        flags = list(self.flags.values())

        if category:
            flags = [f for f in flags if f.category == category]

        if state:
            flags = [f for f in flags if f.state == state]

        return flags

    def get_stats(self) -> Dict[str, Any]:
        """Get feature flag statistics"""
        by_state = {}
        by_category = {}

        for flag in self.flags.values():
            state = flag.state.value
            category = flag.category

            by_state[state] = by_state.get(state, 0) + 1
            by_category[category] = by_category.get(category, 0) + 1

        total_evaluations = sum(f.evaluation_count for f in self.flags.values())
        total_enabled = sum(f.enabled_count for f in self.flags.values())

        return {
            "total_flags": len(self.flags),
            "by_state": by_state,
            "by_category": by_category,
            "total_evaluations": total_evaluations,
            "total_enabled_evaluations": total_enabled,
            "enable_rate": total_enabled / total_evaluations if total_evaluations > 0 else 0
        }


# Singleton instance
_feature_flags: Optional[FeatureFlags] = None


def get_feature_flags() -> FeatureFlags:
    """Get feature flags singleton"""
    global _feature_flags

    if _feature_flags is None:
        _feature_flags = FeatureFlags()

    return _feature_flags


# Convenience function
async def is_feature_enabled(
    flag_id: str,
    user_id: Optional[str] = None,
    user_tier: str = "free",
    default: bool = False
) -> bool:
    """Check if a feature is enabled"""
    return await get_feature_flags().is_enabled(flag_id, user_id, user_tier, default)


# Testing
if __name__ == "__main__":
    async def test():
        ff = FeatureFlags("test_flags.json")

        # List all flags
        print("Feature Flags:")
        for flag in await ff.list_flags():
            print(f"  {flag.flag_id}: {flag.state.value}")

        # Check flag for free user
        is_api = await ff.is_enabled("api_access", "user1", "free")
        print(f"\nAPI access for free user: {is_api}")

        # Check flag for pro user
        is_api_pro = await ff.is_enabled("api_access", "user2", "pro")
        print(f"API access for pro user: {is_api_pro}")

        # Check percentage flag
        for i in range(10):
            is_beta = await ff.is_enabled("beta_features", f"user_{i}", "free")
            print(f"Beta features for user_{i}: {is_beta}")

        # Get enabled flags for a user
        enabled = await ff.get_enabled_flags("user1", "whale")
        print(f"\nEnabled flags for whale user: {enabled}")

        # Stats
        print(f"\nStats: {ff.get_stats()}")

        # Clean up
        import os
        os.remove("test_flags.json")

    asyncio.run(test())
