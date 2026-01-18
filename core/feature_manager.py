"""
Feature Manager - Simplified facade for feature flags.

This module provides a clean, simple interface for checking feature flags
throughout the Jarvis codebase. It wraps the more complex FeatureFlagManager.

Usage:
    from core.feature_manager import is_enabled

    if is_enabled("DEXTER_REACT_ENABLED"):
        # Run Dexter ReAct agent
        agent.run()

    # With user context for percentage rollouts
    if is_enabled("NEW_UI", user_id="user123"):
        # Show new UI
        render_new_ui()

    # Get A/B test variant
    from core.feature_manager import get_variant

    variant = get_variant("AB_TEST", user_id="user123")
    if variant == "treatment":
        # Show treatment version
        pass
"""

import os
from pathlib import Path
from typing import Optional, Dict, Any, List

from core.config.feature_flags import (
    FeatureFlagManager,
    get_feature_flag_manager,
    _reset_manager as _reset_internal_manager,
)


def get_manager() -> FeatureFlagManager:
    """
    Get the feature flag manager singleton.

    Returns:
        FeatureFlagManager instance
    """
    # Allow override via environment variable for testing
    config_path = os.environ.get("FEATURE_FLAGS_PATH")
    if config_path:
        return FeatureFlagManager(config_path=Path(config_path))
    return get_feature_flag_manager()


def is_enabled(
    flag_name: str,
    user_id: Optional[str] = None,
    context: Optional[Dict[str, Any]] = None,
) -> bool:
    """
    Check if a feature flag is enabled.

    This is the primary function for checking feature flags.
    Supports:
    - Boolean flags (on/off)
    - Percentage rollouts (X% of users)
    - User whitelisting
    - Time-based activation (start_date, end_date)
    - Environment variable overrides (FF_FLAG_NAME=true/false)

    Args:
        flag_name: Name of the feature flag (e.g., "DEXTER_REACT_ENABLED")
        user_id: Optional user ID for percentage rollouts and whitelisting
        context: Optional additional context (for future extensibility)

    Returns:
        True if the feature is enabled for this context

    Examples:
        # Simple check
        if is_enabled("ADVANCED_STRATEGIES_ENABLED"):
            run_advanced_strategies()

        # With user context
        if is_enabled("NEW_TELEGRAM_UI", user_id=telegram_user_id):
            show_new_ui()
    """
    return get_manager().is_enabled(flag_name, user_id=user_id, context=context)


def get_variant(
    flag_name: str,
    user_id: Optional[str] = None,
) -> Optional[str]:
    """
    Get the A/B test variant for a user.

    Returns the assigned variant name for the given flag and user.
    Uses consistent hashing so the same user always gets the same variant.

    Args:
        flag_name: Name of the flag with A/B test configuration
        user_id: User identifier for consistent variant assignment

    Returns:
        Variant name (e.g., "control", "treatment") or None if no A/B test

    Example:
        variant = get_variant("CHECKOUT_FLOW_TEST", user_id="user123")
        if variant == "treatment":
            show_new_checkout()
        else:
            show_old_checkout()
    """
    return get_manager().get_variant(flag_name, user_id=user_id)


def get_flag(flag_name: str) -> Optional[Any]:
    """
    Get the full flag configuration.

    Useful for debugging or getting detailed flag information.

    Args:
        flag_name: Name of the flag

    Returns:
        FeatureFlagConfig or None if not found
    """
    return get_manager().get_flag(flag_name)


def get_all_flags() -> Dict[str, Dict[str, Any]]:
    """
    Get all flags with their current configuration.

    Returns:
        Dictionary of flag_name -> flag config dict
    """
    return get_manager().get_all_flags()


def get_enabled_flags(user_id: Optional[str] = None) -> List[str]:
    """
    Get list of all enabled flags for the given context.

    Args:
        user_id: Optional user ID for context-aware evaluation

    Returns:
        List of enabled flag names
    """
    return get_manager().get_enabled_flags(user_id=user_id)


def set_flag(
    flag_name: str,
    enabled: bool,
    percentage: Optional[int] = None,
    user_list: Optional[List[str]] = None,
) -> None:
    """
    Update a flag's configuration.

    Changes are persisted to the JSON config file.
    Use with caution in production.

    Args:
        flag_name: Name of the flag to update
        enabled: New enabled state
        percentage: Optional rollout percentage (0-100)
        user_list: Optional list of whitelisted user IDs
    """
    get_manager().set_flag(flag_name, enabled, percentage, user_list)


def reload_flags() -> None:
    """
    Force reload flags from the config file.

    Call this to pick up config changes without restarting.
    """
    get_manager().reload_from_file()


# Alias for testing
_reset_manager = _reset_internal_manager
