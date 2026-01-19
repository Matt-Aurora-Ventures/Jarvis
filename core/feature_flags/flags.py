"""Feature flag implementation with percentage-based rollout."""

import logging
import json
from typing import Dict, Any, Optional
from pathlib import Path
from datetime import datetime

logger = logging.getLogger(__name__)


class Flag:
    """Feature flag definition."""

    def __init__(self, name: str, description: str = "", enabled: bool = False, 
                 rollout_percentage: int = 0, activated_at: Optional[str] = None):
        """Initialize feature flag."""
        self.name = name
        self.description = description
        self.enabled = enabled
        self.rollout_percentage = max(0, min(100, rollout_percentage))
        self.activated_at = activated_at or datetime.utcnow().isoformat()

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "description": self.description,
            "enabled": self.enabled,
            "rollout_percentage": self.rollout_percentage,
            "activated_at": self.activated_at,
        }


class FeatureFlags:
    """Feature flag manager."""

    def __init__(self, config_path: str = "lifeos/config/feature_flags.json"):
        """Initialize feature flag manager."""
        self.config_path = Path(config_path)
        self.flags: Dict[str, Flag] = {}
        self._load_config()

    def register(self, name: str, description: str = "", enabled: bool = False, 
                 rollout_percentage: int = 0) -> Flag:
        """Register a new feature flag."""
        flag = Flag(name, description, enabled, rollout_percentage)
        self.flags[name] = flag
        logger.info(f"Registered flag: {name}")
        return flag

    def is_enabled(self, flag_name: str, user_id: Optional[str] = None) -> bool:
        """Check if feature is enabled for user."""
        if flag_name not in self.flags:
            logger.warning(f"Unknown flag: {flag_name}")
            return False

        flag = self.flags[flag_name]

        if not flag.enabled:
            return False

        if flag.rollout_percentage >= 100:
            return True

        if flag.rollout_percentage <= 0:
            return False

        if user_id:
            user_hash = int(hash(user_id) % 100)
            return user_hash < flag.rollout_percentage

        return False

    def enable(self, flag_name: str, rollout_percentage: int = 100) -> bool:
        """Enable a feature flag."""
        if flag_name not in self.flags:
            logger.error(f"Flag not found: {flag_name}")
            return False

        flag = self.flags[flag_name]
        flag.enabled = True
        flag.rollout_percentage = max(0, min(100, rollout_percentage))
        logger.info(f"Enabled {flag_name} at {rollout_percentage}% rollout")
        return True

    def disable(self, flag_name: str) -> bool:
        """Disable a feature flag."""
        if flag_name not in self.flags:
            logger.error(f"Flag not found: {flag_name}")
            return False

        self.flags[flag_name].enabled = False
        logger.info(f"Disabled {flag_name}")
        return True

    def set_rollout(self, flag_name: str, percentage: int) -> bool:
        """Set rollout percentage for a flag."""
        if flag_name not in self.flags:
            logger.error(f"Flag not found: {flag_name}")
            return False

        self.flags[flag_name].rollout_percentage = max(0, min(100, percentage))
        logger.info(f"Set {flag_name} rollout to {percentage}%")
        return True

    def get_status(self, flag_name: str) -> Optional[Dict[str, Any]]:
        """Get flag status."""
        if flag_name not in self.flags:
            return None
        return self.flags[flag_name].to_dict()

    def list_flags(self) -> Dict[str, Dict[str, Any]]:
        """List all flags and their status."""
        return {name: flag.to_dict() for name, flag in self.flags.items()}

    def _load_config(self):
        """Load flags from config file."""
        if not self.config_path.exists():
            return

        try:
            with open(self.config_path) as f:
                config = json.load(f)

            if not isinstance(config, dict):
                logger.error("Config must be a dictionary")
                return

            flags_config = config.get("flags", [])
            if not isinstance(flags_config, list):
                logger.error("Flags config must be a list")
                return

            for flag_config in flags_config:
                if not isinstance(flag_config, dict):
                    logger.warning(f"Skipping invalid flag config: {flag_config}")
                    continue

                self.register(
                    flag_config.get("name", ""),
                    flag_config.get("description", ""),
                    flag_config.get("enabled", False),
                    flag_config.get("rollout_percentage", 0),
                )
        except (json.JSONDecodeError, IOError) as e:
            logger.error(f"Failed to load config: {e}")


__all__ = ["Flag", "FeatureFlags"]
