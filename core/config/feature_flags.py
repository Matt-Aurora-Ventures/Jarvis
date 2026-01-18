"""
Feature Flag Manager - Enhanced feature toggling system.

Provides:
- JSON config file support (lifeos/config/feature_flags.json)
- Environment variable overrides (FF_*)
- Caching with configurable TTL
- Hot reload from file
- Percentage-based rollouts with hash consistency
- User whitelist support

Usage:
    from core.config.feature_flags import get_feature_flag_manager

    manager = get_feature_flag_manager()

    # Check if flag is enabled
    if manager.is_enabled("DEXTER_ENABLED"):
        # Feature is on

    # Check with user context for percentage rollouts
    if manager.is_enabled("NEW_FEATURE", user_id="user123"):
        # User has feature

    # Hot reload from file
    manager.reload_from_file()
"""

import json
import logging
import os
import time
import hashlib
from pathlib import Path
from threading import Lock
from typing import Dict, Any, Optional, List

from core.config.feature_flag_models import FeatureFlagConfig, FlagConfigFile

logger = logging.getLogger(__name__)


# Default config file location
DEFAULT_CONFIG_PATH = Path(__file__).parent.parent.parent / "lifeos" / "config" / "feature_flags.json"


class FeatureFlagManager:
    """
    Feature flag management system with caching and env overrides.

    Features:
    - JSON config file support
    - Environment variable overrides (FF_FLAG_NAME=true/false)
    - Caching with configurable TTL (default: 60 seconds)
    - Hot reload from file
    - Percentage-based rollouts (consistent hashing)
    - User whitelist support
    """

    _instance: Optional["FeatureFlagManager"] = None
    _lock = Lock()

    def __new__(cls, config_path: Optional[Path] = None, cache_ttl_seconds: float = 60.0):
        """Singleton pattern - returns existing instance or creates new one."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    instance = super().__new__(cls)
                    instance._initialized = False
                    cls._instance = instance
        return cls._instance

    def __init__(self, config_path: Optional[Path] = None, cache_ttl_seconds: float = 60.0):
        """
        Initialize the feature flag manager.

        Args:
            config_path: Path to feature_flags.json (uses default if None)
            cache_ttl_seconds: How long to cache flag values (default: 60s)
        """
        if self._initialized:
            return

        self._config_path = config_path or DEFAULT_CONFIG_PATH
        self._cache_ttl = cache_ttl_seconds
        self._flags: Dict[str, FeatureFlagConfig] = {}
        self._cache: Dict[str, Any] = {}
        self._cache_timestamp: float = 0
        self._env_overrides: Dict[str, bool] = {}

        self._load_env_overrides()
        self._load_from_file()
        self._initialized = True

        logger.info(f"FeatureFlagManager initialized: {len(self._flags)} flags from {self._config_path}")

    def _load_env_overrides(self):
        """Load FF_* environment variable overrides."""
        self._env_overrides = {}

        for key, value in os.environ.items():
            if key.startswith("FF_"):
                flag_name = key[3:]  # Remove "FF_" prefix
                self._env_overrides[flag_name] = self._parse_bool(value)
                logger.debug(f"Env override: {flag_name}={self._env_overrides[flag_name]}")

    def _parse_bool(self, value: str) -> bool:
        """Parse string to boolean."""
        return value.lower() in ("true", "1", "yes")

    def _load_from_file(self):
        """Load flags from JSON config file."""
        if not self._config_path.exists():
            logger.warning(f"Feature flags config not found: {self._config_path}")
            self._flags = {}
            return

        try:
            with open(self._config_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            config_file = FlagConfigFile.from_dict(data)
            self._flags = config_file.flags
            self._cache_timestamp = time.time()

            logger.debug(f"Loaded {len(self._flags)} flags from {self._config_path}")

        except Exception as e:
            logger.error(f"Failed to load feature flags: {e}")
            self._flags = {}

    def _is_cache_valid(self) -> bool:
        """Check if cache is still valid (within TTL)."""
        return (time.time() - self._cache_timestamp) < self._cache_ttl

    def _maybe_reload(self):
        """Reload from file if cache expired."""
        if not self._is_cache_valid():
            self._load_from_file()

    def reload_from_file(self):
        """
        Force reload flags from JSON config file.

        Call this to pick up config changes without restarting.
        """
        self._load_from_file()
        self._load_env_overrides()  # Re-check env overrides
        logger.info(f"Reloaded feature flags: {len(self._flags)} flags")

    def is_enabled(
        self,
        flag_name: str,
        user_id: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Check if a feature flag is enabled.

        Evaluation order:
        1. Environment variable override (FF_FLAG_NAME)
        2. Time-based activation (start_date, end_date)
        3. User whitelist (if user_id provided)
        4. Percentage rollout (if user_id provided and percentage > 0)
        5. Base enabled state

        Args:
            flag_name: Name of the flag to check
            user_id: Optional user ID for percentage/whitelist checks
            context: Optional additional context (for future use)

        Returns:
            True if flag is enabled for this context
        """
        self._maybe_reload()

        # 1. Check environment override first
        if flag_name in self._env_overrides:
            return self._env_overrides[flag_name]

        # 2. Check if flag exists
        flag = self._flags.get(flag_name)
        if flag is None:
            return False

        # 3. Check time-based activation
        if not flag.is_time_active():
            return False

        # 4. Check user whitelist
        if user_id and flag.user_whitelist:
            if str(user_id) in flag.user_whitelist:
                return True
            # If whitelist exists and user not in it, check percentage
            if flag.rollout_percentage > 0:
                return self._check_percentage(flag_name, user_id, flag.rollout_percentage)
            # Whitelist exists but user not in it and no percentage rollout
            return False

        # 5. Check percentage rollout
        if user_id and flag.rollout_percentage > 0:
            return self._check_percentage(flag_name, user_id, flag.rollout_percentage)

        # 6. Return base enabled state
        return flag.enabled

    def _check_percentage(self, flag_name: str, user_id: str, percentage: int) -> bool:
        """
        Check percentage-based rollout using consistent hashing.

        The same user_id will always get the same result for a given flag.

        Args:
            flag_name: Flag name
            user_id: User identifier
            percentage: Rollout percentage (0-100)

        Returns:
            True if user is in the rollout percentage
        """
        # Create consistent hash from flag + user
        hash_input = f"{flag_name}:{user_id}".encode('utf-8')
        hash_val = int(hashlib.md5(hash_input).hexdigest(), 16)
        bucket = hash_val % 100

        return bucket < percentage

    def get_variant(
        self,
        flag_name: str,
        user_id: Optional[str] = None,
    ) -> Optional[str]:
        """
        Get the A/B test variant for a user.

        Uses consistent hashing to assign users to variants.
        Returns None if flag doesn't exist or doesn't have A/B test config.

        Args:
            flag_name: Name of the flag with A/B test config
            user_id: User identifier for consistent assignment

        Returns:
            Variant name (e.g., "control" or "treatment") or None
        """
        self._maybe_reload()

        flag = self._flags.get(flag_name)
        if flag is None:
            return None

        if not flag.ab_test or not flag.ab_test.variants:
            return None

        if not user_id:
            # Return first variant as default when no user_id
            return flag.ab_test.variants[0]

        # Use consistent hashing to assign variant
        hash_input = f"{flag_name}:variant:{user_id}".encode('utf-8')
        hash_val = int(hashlib.md5(hash_input).hexdigest(), 16)
        variant_index = hash_val % len(flag.ab_test.variants)

        return flag.ab_test.variants[variant_index]

    def get_flag(self, flag_name: str) -> Optional[FeatureFlagConfig]:
        """
        Get flag configuration by name.

        Args:
            flag_name: Name of the flag

        Returns:
            FeatureFlagConfig or None if not found
        """
        self._maybe_reload()
        return self._flags.get(flag_name)

    def set_flag(
        self,
        flag_name: str,
        enabled: bool,
        percentage: Optional[int] = None,
        user_list: Optional[List[str]] = None,
    ):
        """
        Update a flag's configuration.

        Changes are persisted to the JSON config file.

        Args:
            flag_name: Name of the flag to update
            enabled: New enabled state
            percentage: Optional rollout percentage (0-100)
            user_list: Optional list of whitelisted user IDs
        """
        from datetime import datetime, timezone

        flag = self._flags.get(flag_name)
        if flag is None:
            # Create new flag
            flag = FeatureFlagConfig(name=flag_name)
            self._flags[flag_name] = flag

        flag.enabled = enabled
        flag.updated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        if percentage is not None:
            flag.rollout_percentage = max(0, min(100, percentage))

        if user_list is not None:
            flag.user_whitelist = user_list

        # Persist to file
        self._save_to_file()

        logger.info(f"Updated flag {flag_name}: enabled={enabled}, percentage={flag.rollout_percentage}")

    def _save_to_file(self):
        """Save current flags to JSON config file."""
        try:
            # Ensure directory exists
            self._config_path.parent.mkdir(parents=True, exist_ok=True)

            config_file = FlagConfigFile(flags=self._flags)
            data = config_file.to_dict()

            with open(self._config_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)

            self._cache_timestamp = time.time()
            logger.debug(f"Saved {len(self._flags)} flags to {self._config_path}")

        except Exception as e:
            logger.error(f"Failed to save feature flags: {e}")

    def get_all_flags(self) -> Dict[str, Dict[str, Any]]:
        """
        Get all flags with their configuration.

        Returns:
            Dictionary of flag_name -> flag config dict
        """
        self._maybe_reload()
        return {name: flag.to_dict() for name, flag in self._flags.items()}

    def get_enabled_flags(
        self,
        user_id: Optional[str] = None,
    ) -> List[str]:
        """
        Get list of enabled flag names for the given context.

        Args:
            user_id: Optional user ID for context-aware evaluation

        Returns:
            List of enabled flag names
        """
        self._maybe_reload()
        return [
            name for name in self._flags
            if self.is_enabled(name, user_id=user_id)
        ]


# Singleton instance
_manager_instance: Optional[FeatureFlagManager] = None


def get_feature_flag_manager(
    config_path: Optional[Path] = None,
    cache_ttl_seconds: float = 60.0,
) -> FeatureFlagManager:
    """
    Get the feature flag manager singleton.

    Args:
        config_path: Optional path to config file
        cache_ttl_seconds: Cache TTL in seconds

    Returns:
        FeatureFlagManager instance
    """
    global _manager_instance
    if _manager_instance is None:
        _manager_instance = FeatureFlagManager(config_path, cache_ttl_seconds)
    return _manager_instance


def _reset_manager():
    """Reset the manager singleton (for testing)."""
    global _manager_instance
    _manager_instance = None
    FeatureFlagManager._instance = None


# Convenience function for simple checks
def is_flag_enabled(flag_name: str, user_id: Optional[str] = None) -> bool:
    """
    Check if a feature flag is enabled.

    Convenience function that uses the default manager.

    Args:
        flag_name: Name of the flag
        user_id: Optional user ID

    Returns:
        True if flag is enabled
    """
    return get_feature_flag_manager().is_enabled(flag_name, user_id=user_id)
