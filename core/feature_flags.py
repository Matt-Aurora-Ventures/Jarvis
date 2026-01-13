"""
Feature Flags - Runtime feature toggles for gradual rollouts.

Provides:
- Runtime feature toggling without restarts
- Percentage-based rollouts
- User segment targeting
- A/B testing support
- Feature dependencies
"""

import json
import logging
import os
from datetime import datetime, timezone
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Dict, Any, Optional, List, Set, Callable
from threading import Lock
import hashlib

logger = logging.getLogger(__name__)


class FeatureState(Enum):
    """Feature flag states."""
    OFF = "off"
    ON = "on"
    PERCENTAGE = "percentage"
    SEGMENT = "segment"


@dataclass
class FeatureFlag:
    """A single feature flag definition."""
    name: str
    description: str
    state: FeatureState = FeatureState.OFF
    percentage: int = 0  # For percentage rollouts (0-100)
    segments: List[str] = field(default_factory=list)  # User segments
    dependencies: List[str] = field(default_factory=list)  # Required flags
    created_at: str = ""
    updated_at: str = ""
    owner: str = ""
    
    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now(timezone.utc).isoformat()
        if not self.updated_at:
            self.updated_at = self.created_at


class FeatureFlags:
    """
    Feature flag management system.
    
    Features:
    - Runtime toggles without restarts
    - Percentage-based rollouts
    - User segment targeting
    - Feature dependencies
    - Persistent storage
    """

    _instance: Optional["FeatureFlags"] = None
    _lock = Lock()

    # Default flags - ready to activate
    DEFAULT_FLAGS = {
        # Trading features
        "live_trading": FeatureFlag(
            name="live_trading",
            description="Enable live trading (vs paper trading)",
            state=FeatureState.OFF,
            owner="treasury"
        ),
        "advanced_signals": FeatureFlag(
            name="advanced_signals",
            description="Enable advanced trading signals (liquidation, MA)",
            state=FeatureState.OFF,
            owner="trading"
        ),
        "auto_tp_sl": FeatureFlag(
            name="auto_tp_sl",
            description="Automatic take profit and stop loss orders",
            state=FeatureState.OFF,
            owner="treasury"
        ),
        
        # Bot features
        "smart_response_filter": FeatureFlag(
            name="smart_response_filter",
            description="Filter bot responses to only reply when addressed",
            state=FeatureState.ON,
            owner="telegram"
        ),
        "sentiment_reports": FeatureFlag(
            name="sentiment_reports",
            description="Enable sentiment report generation",
            state=FeatureState.ON,
            owner="telegram"
        ),
        "buy_buttons": FeatureFlag(
            name="buy_buttons",
            description="Show buy buttons in sentiment reports",
            state=FeatureState.ON,
            owner="telegram"
        ),
        
        # Security features
        "hash_chain_audit": FeatureFlag(
            name="hash_chain_audit",
            description="Enable immutable hash chain for audit logs",
            state=FeatureState.OFF,
            owner="security"
        ),
        "enhanced_encryption": FeatureFlag(
            name="enhanced_encryption",
            description="Use enhanced encryption for sensitive data",
            state=FeatureState.OFF,
            owner="security"
        ),
        
        # Performance features
        "async_processing": FeatureFlag(
            name="async_processing",
            description="Enable async batch processing",
            state=FeatureState.ON,
            owner="performance"
        ),
        "cache_enabled": FeatureFlag(
            name="cache_enabled",
            description="Enable response caching",
            state=FeatureState.ON,
            owner="performance"
        ),
        
        # Experimental features
        "ml_regime_detection": FeatureFlag(
            name="ml_regime_detection",
            description="ML-based market regime detection",
            state=FeatureState.OFF,
            owner="trading"
        ),
        "voice_commands": FeatureFlag(
            name="voice_commands",
            description="Enable voice command processing",
            state=FeatureState.OFF,
            owner="voice"
        ),
        "autonomous_trading": FeatureFlag(
            name="autonomous_trading",
            description="Full autonomous trading without confirmation",
            state=FeatureState.OFF,
            dependencies=["live_trading", "auto_tp_sl"],
            owner="treasury"
        ),
    }

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self.flags_file = Path(os.getenv("FEATURE_FLAGS_FILE", "data/feature_flags.json"))
        self.flags: Dict[str, FeatureFlag] = {}
        self._callbacks: Dict[str, List[Callable]] = {}
        
        self._load_flags()
        self._initialized = True
        logger.info(f"FeatureFlags initialized: {len(self.flags)} flags")

    def _load_flags(self):
        """Load flags from file or use defaults."""
        # Start with defaults
        self.flags = {k: v for k, v in self.DEFAULT_FLAGS.items()}

        # Override from file if exists
        if self.flags_file.exists():
            try:
                with open(self.flags_file) as f:
                    saved = json.load(f)
                    for name, data in saved.items():
                        if name in self.flags:
                            flag = self.flags[name]
                            flag.state = FeatureState(data.get("state", "off"))
                            flag.percentage = data.get("percentage", 0)
                            flag.segments = data.get("segments", [])
                            flag.updated_at = data.get("updated_at", "")
            except Exception as e:
                logger.warning(f"Failed to load feature flags: {e}")

    def _save_flags(self):
        """Save flags to file."""
        self.flags_file.parent.mkdir(parents=True, exist_ok=True)
        try:
            data = {}
            for name, flag in self.flags.items():
                data[name] = {
                    "state": flag.state.value,
                    "percentage": flag.percentage,
                    "segments": flag.segments,
                    "updated_at": flag.updated_at,
                }
            with open(self.flags_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save feature flags: {e}")

    def is_enabled(
        self,
        flag_name: str,
        user_id: str = None,
        user_segments: List[str] = None,
    ) -> bool:
        """Check if a feature is enabled for the given context."""
        if flag_name not in self.flags:
            return False

        flag = self.flags[flag_name]

        # Check dependencies first
        for dep in flag.dependencies:
            if not self.is_enabled(dep, user_id, user_segments):
                return False

        if flag.state == FeatureState.OFF:
            return False
        
        if flag.state == FeatureState.ON:
            return True

        if flag.state == FeatureState.PERCENTAGE:
            if not user_id:
                return False
            # Consistent hashing for user
            hash_val = int(hashlib.md5(f"{flag_name}:{user_id}".encode()).hexdigest(), 16)
            return (hash_val % 100) < flag.percentage

        if flag.state == FeatureState.SEGMENT:
            if not user_segments:
                return False
            return bool(set(flag.segments) & set(user_segments))

        return False

    def enable(self, flag_name: str):
        """Enable a feature flag."""
        if flag_name in self.flags:
            old_state = self.flags[flag_name].state
            self.flags[flag_name].state = FeatureState.ON
            self.flags[flag_name].updated_at = datetime.now(timezone.utc).isoformat()
            self._save_flags()
            self._trigger_callbacks(flag_name, old_state, FeatureState.ON)
            logger.info(f"Feature flag enabled: {flag_name}")

    def disable(self, flag_name: str):
        """Disable a feature flag."""
        if flag_name in self.flags:
            old_state = self.flags[flag_name].state
            self.flags[flag_name].state = FeatureState.OFF
            self.flags[flag_name].updated_at = datetime.now(timezone.utc).isoformat()
            self._save_flags()
            self._trigger_callbacks(flag_name, old_state, FeatureState.OFF)
            logger.info(f"Feature flag disabled: {flag_name}")

    def set_percentage(self, flag_name: str, percentage: int):
        """Set percentage rollout for a flag."""
        if flag_name in self.flags:
            self.flags[flag_name].state = FeatureState.PERCENTAGE
            self.flags[flag_name].percentage = max(0, min(100, percentage))
            self.flags[flag_name].updated_at = datetime.now(timezone.utc).isoformat()
            self._save_flags()
            logger.info(f"Feature flag {flag_name} set to {percentage}% rollout")

    def set_segments(self, flag_name: str, segments: List[str]):
        """Set segment targeting for a flag."""
        if flag_name in self.flags:
            self.flags[flag_name].state = FeatureState.SEGMENT
            self.flags[flag_name].segments = segments
            self.flags[flag_name].updated_at = datetime.now(timezone.utc).isoformat()
            self._save_flags()
            logger.info(f"Feature flag {flag_name} targeted to segments: {segments}")

    def register_callback(self, flag_name: str, callback: Callable):
        """Register callback for flag changes."""
        if flag_name not in self._callbacks:
            self._callbacks[flag_name] = []
        self._callbacks[flag_name].append(callback)

    def _trigger_callbacks(self, flag_name: str, old_state: FeatureState, new_state: FeatureState):
        """Trigger callbacks for flag change."""
        for callback in self._callbacks.get(flag_name, []):
            try:
                callback(flag_name, old_state, new_state)
            except Exception as e:
                logger.error(f"Feature flag callback error: {e}")

    def get_all_flags(self) -> Dict[str, Dict]:
        """Get all flags with their status."""
        return {
            name: {
                "description": flag.description,
                "state": flag.state.value,
                "percentage": flag.percentage,
                "segments": flag.segments,
                "dependencies": flag.dependencies,
                "owner": flag.owner,
                "updated_at": flag.updated_at,
            }
            for name, flag in self.flags.items()
        }

    def get_enabled_flags(self, user_id: str = None, user_segments: List[str] = None) -> List[str]:
        """Get list of enabled flags for context."""
        return [
            name for name in self.flags
            if self.is_enabled(name, user_id, user_segments)
        ]


# Singleton accessor
def get_feature_flags() -> FeatureFlags:
    """Get the feature flags singleton."""
    return FeatureFlags()


# Convenience function
def is_feature_enabled(flag_name: str, user_id: str = None) -> bool:
    """Check if a feature is enabled."""
    return get_feature_flags().is_enabled(flag_name, user_id)
