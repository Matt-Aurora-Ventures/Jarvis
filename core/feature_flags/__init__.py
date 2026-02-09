"""Feature flag management for safe feature rollouts.

This package provides two complementary mechanisms:
1. Config-driven feature flags with rollout percentages (FeatureFlags / Flag).
2. Lightweight env-driven kill-switches for cost-heavy / risky behavior.
"""

import os

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

def env_flag(name: str, default: bool = False) -> bool:
    """Parse a boolean-ish env var with a safe default.

    - Unset or empty: default
    - "1/true/yes/on": True
    - everything else: False
    """
    raw = os.getenv(name)
    if raw is None or raw == "":
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


def is_cooldown_mode() -> bool:
    """Master kill-switch for cost-heavy / risky behavior."""
    return env_flag("JARVIS_COOLDOWN_MODE", False)


def is_xai_enabled(*, default: bool = True) -> bool:
    """Return True if xAI/Grok calls are allowed.

    This is intentionally conservative: cooldown mode always disables xAI.
    """
    if is_cooldown_mode():
        return False
    return env_flag("XAI_ENABLED", default)


__all__ = [
    "FeatureFlags",
    "Flag",
    "get_feature_flags",
    "is_feature_enabled",
    "env_flag",
    "is_cooldown_mode",
    "is_xai_enabled",
]
