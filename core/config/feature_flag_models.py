"""
Feature Flag Data Models.

Provides:
- FeatureFlagConfig: Configuration for a single feature flag
- FlagConfigFile: Structure for the JSON config file
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional


@dataclass
class ABTestConfig:
    """
    Configuration for A/B testing.

    Attributes:
        experiment_id: Unique identifier for the experiment
        variants: List of variant names (e.g., ["control", "treatment"])
    """
    experiment_id: str = ""
    variants: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "experiment_id": self.experiment_id,
            "variants": self.variants,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ABTestConfig":
        """Create ABTestConfig from dictionary."""
        if not data:
            return cls()
        return cls(
            experiment_id=data.get("experiment_id", ""),
            variants=data.get("variants", []),
        )


@dataclass
class FeatureFlagConfig:
    """
    Configuration for a single feature flag.

    Attributes:
        name: Unique flag identifier (e.g., "DEXTER_ENABLED")
        enabled: Whether the flag is enabled (base state)
        description: Human-readable description of what the flag controls
        rollout_percentage: Percentage of users to enable (0-100)
        user_whitelist: List of user IDs that always have the flag enabled
        start_date: Optional date when flag becomes active (YYYY-MM-DD)
        end_date: Optional date when flag expires (YYYY-MM-DD)
        ab_test: Optional A/B test configuration
        created_at: When the flag was created
        updated_at: When the flag was last modified
    """
    name: str
    enabled: bool = False
    description: str = ""
    rollout_percentage: int = 0
    user_whitelist: List[str] = field(default_factory=list)
    start_date: str = ""  # YYYY-MM-DD format, empty means no start constraint
    end_date: str = ""    # YYYY-MM-DD format, empty means no end constraint
    ab_test: Optional[ABTestConfig] = None
    created_at: str = ""
    updated_at: str = ""

    def __post_init__(self):
        """Initialize timestamps if not provided."""
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        if not self.created_at:
            self.created_at = now
        if not self.updated_at:
            self.updated_at = now

    def is_time_active(self) -> bool:
        """
        Check if the flag is within its active time window.

        Returns:
            True if current date is within start_date and end_date (inclusive),
            or if no time constraints are set.
        """
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        # Check start_date constraint
        if self.start_date and today < self.start_date:
            return False

        # Check end_date constraint
        if self.end_date and today > self.end_date:
            return False

        return True

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert to dictionary for JSON serialization.

        Returns:
            Dictionary representation of the flag config
        """
        result = {
            "name": self.name,
            "enabled": self.enabled,
            "description": self.description,
            "rollout_percentage": self.rollout_percentage,
            "user_whitelist": self.user_whitelist,
            "start_date": self.start_date,
            "end_date": self.end_date,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }
        if self.ab_test:
            result["ab_test"] = self.ab_test.to_dict()
        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "FeatureFlagConfig":
        """
        Create FeatureFlagConfig from dictionary.

        Args:
            data: Dictionary with flag configuration

        Returns:
            FeatureFlagConfig instance
        """
        ab_test_data = data.get("ab_test")
        ab_test = ABTestConfig.from_dict(ab_test_data) if ab_test_data else None

        return cls(
            name=data.get("name", ""),
            enabled=data.get("enabled", False),
            description=data.get("description", ""),
            rollout_percentage=data.get("rollout_percentage", 0),
            user_whitelist=data.get("user_whitelist", []),
            start_date=data.get("start_date", ""),
            end_date=data.get("end_date", ""),
            ab_test=ab_test,
            created_at=data.get("created_at", ""),
            updated_at=data.get("updated_at", ""),
        )


@dataclass
class FlagConfigFile:
    """
    Structure for the feature flags JSON config file.

    JSON format:
    {
        "flags": {
            "FLAG_NAME": {
                "enabled": false,
                "description": "...",
                ...
            }
        }
    }
    """
    flags: Dict[str, FeatureFlagConfig] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert to dictionary for JSON serialization.

        Returns:
            Dictionary in the expected JSON format
        """
        return {
            "flags": {
                name: flag.to_dict()
                for name, flag in self.flags.items()
            }
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "FlagConfigFile":
        """
        Create FlagConfigFile from dictionary.

        Args:
            data: Dictionary loaded from JSON file

        Returns:
            FlagConfigFile instance
        """
        flags = {}
        for name, flag_data in data.get("flags", {}).items():
            # Ensure name is set in the flag data
            flag_data["name"] = name
            flags[name] = FeatureFlagConfig.from_dict(flag_data)

        return cls(flags=flags)
