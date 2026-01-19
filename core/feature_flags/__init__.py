"""Feature flag management for safe feature rollouts."""

from core.feature_flags.flags import FeatureFlags, Flag

# Global feature flags instance
_feature_flags: FeatureFlags = None


def get_feature_flags() -> FeatureFlags:
    """Get global feature flags instance."""
    global _feature_flags
    if _feature_flags is None:
        _feature_flags = FeatureFlags()
    return _feature_flags


def is_feature_enabled(flag_name: str, user_id: str = None) -> bool:
    """Check if feature is enabled."""
    return get_feature_flags().is_enabled(flag_name, user_id)


__all__ = ["FeatureFlags", "Flag", "get_feature_flags", "is_feature_enabled"]
