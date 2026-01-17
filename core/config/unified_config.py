"""
Unified Configuration Loader.

Loads master config.yaml with environment variable expansion.
Replaces all scattered config modules with a single source of truth.

Features:
- Single config.yaml with all settings
- Environment variable expansion: ${VAR_NAME} or ${VAR_NAME:default}
- Backward compatible with existing code patterns
- Section-based access: config.get("trading.max_positions")
- Type-aware parsing: booleans, numbers, lists

Usage:
    from core.config.unified_config import get_unified_config

    config = get_unified_config()
    api_key = config.get("twitter.api_key")
    max_pos = config.get("trading.max_positions", 50)
"""

import os
import re
import logging
from pathlib import Path
from typing import Any, Dict, Optional, List, TypeVar, Union
from dataclasses import dataclass

logger = logging.getLogger(__name__)

T = TypeVar("T")

# Try to import yaml, fall back to json
try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False
    import json


@dataclass
class ConfigValue:
    """A configuration value with metadata."""
    value: Any
    source: str  # "file", "env", "default"
    key: str


class UnifiedConfigLoader:
    """Load and manage unified configuration."""

    # Default config file locations
    DEFAULT_CONFIG_PATHS = [
        Path.cwd() / "config.yaml",
        Path.cwd() / "config" / "config.yaml",
        Path(__file__).parent.parent.parent / "config.yaml",  # Project root
        Path.home() / ".lifeos" / "config.yaml",
    ]

    # Sensitive keys that should never be logged
    SENSITIVE_KEYS = {
        "api_key", "api_secret", "token", "password", "secret",
        "private_key", "wallet_key", "bot_token", "bearer_token",
        "access_token", "refresh_token", "oauth", "credential",
    }

    def __init__(self, config_path: Optional[Path] = None):
        """
        Initialize configuration loader.

        Args:
            config_path: Explicit path to config.yaml (auto-detected if None)
        """
        self._config: Dict[str, Any] = {}
        self._raw_config: Dict[str, Any] = {}
        self._config_path: Optional[Path] = None
        self._env_expansions: Dict[str, str] = {}

        # Load configuration
        self._load(config_path)

    def _load(self, config_path: Optional[Path] = None) -> None:
        """Load configuration from file."""
        path = config_path or self._find_config_file()

        if not path or not path.exists():
            logger.warning("No config.yaml found, using defaults only")
            self._raw_config = {}
        else:
            self._config_path = path
            self._raw_config = self._load_file(path)
            logger.info(f"Loaded config from {path}")

        # Flatten and expand config
        self._config = self._flatten_and_expand(self._raw_config)

    def _find_config_file(self) -> Optional[Path]:
        """Find config.yaml in default locations."""
        for path in self.DEFAULT_CONFIG_PATHS:
            if path.exists():
                return path
        return None

    def _load_file(self, path: Path) -> Dict[str, Any]:
        """Load config file (YAML or JSON)."""
        try:
            if path.suffix in (".yaml", ".yml"):
                if not HAS_YAML:
                    logger.warning("PyYAML not installed, trying JSON fallback")
                    return {}
                with open(path, "r", encoding="utf-8") as f:
                    return yaml.safe_load(f) or {}
            elif path.suffix == ".json":
                with open(path, "r", encoding="utf-8") as f:
                    return json.load(f)
            else:
                logger.warning(f"Unsupported config format: {path.suffix}")
                return {}
        except Exception as e:
            logger.error(f"Failed to load config from {path}: {e}")
            return {}

    def _flatten_and_expand(self, data: Dict[str, Any], prefix: str = "") -> Dict[str, Any]:
        """
        Flatten nested dictionary and expand environment variables.

        Converts:
            {"trading": {"max_positions": 50}}
        To:
            {"trading.max_positions": 50}

        Also expands ${VAR_NAME} and ${VAR_NAME:default} patterns.
        """
        result = {}

        for key, value in data.items():
            full_key = f"{prefix}.{key}" if prefix else key

            if isinstance(value, dict):
                # Recurse into nested dict
                result.update(self._flatten_and_expand(value, full_key))
            elif isinstance(value, list):
                # Expand environment variables in list items
                expanded_list = [self._expand_value(item) for item in value]
                result[full_key] = expanded_list
            else:
                # Expand value
                result[full_key] = self._expand_value(value)

        return result

    def _expand_value(self, value: Any) -> Any:
        """
        Expand environment variables in a value.

        Supports:
            ${VAR_NAME}          - Required, raises if not found
            ${VAR_NAME:default}  - Uses default if not found
            ${VAR_NAME:}         - Empty string default
        """
        if not isinstance(value, str):
            return value

        # Find all ${...} patterns
        pattern = r"\$\{([^}]+)\}"
        matches = re.findall(pattern, value)

        expanded = value
        for match in matches:
            placeholder = f"${{{match}}}"

            # Parse VAR_NAME or VAR_NAME:default
            if ":" in match:
                var_name, default = match.split(":", 1)
                var_value = os.environ.get(var_name.strip(), default)
            else:
                var_name = match.strip()
                var_value = os.environ.get(var_name)
                if var_value is None:
                    raise ValueError(
                        f"Required environment variable not found: {var_name}. "
                        f"Set it or provide a default: {{{var_name}:default_value}}"
                    )

            # Cache expansion for logging
            self._env_expansions[var_name] = var_value or ""

            expanded = expanded.replace(placeholder, str(var_value))

        # Parse type
        return self._parse_value(expanded)

    def _parse_value(self, value: str) -> Any:
        """Parse string value to appropriate Python type."""
        if not isinstance(value, str):
            return value

        # Boolean
        if value.lower() in ("true", "yes", "1"):
            return True
        if value.lower() in ("false", "no", "0"):
            return False

        # Number
        try:
            if "." in value:
                return float(value)
            return int(value)
        except ValueError:
            pass

        # JSON list/dict
        if value.startswith(("[", "{")):
            try:
                import json
                return json.loads(value)
            except (json.JSONDecodeError, ValueError):
                pass

        # Path expansion
        if value.startswith("~"):
            return str(Path(value).expanduser())

        return value

    def get(
        self,
        key: str,
        default: T = None,
    ) -> Union[Any, T]:
        """
        Get configuration value.

        Args:
            key: Dot-separated key (e.g., "trading.max_positions")
            default: Default value if key not found

        Returns:
            Configuration value or default
        """
        value = self._config.get(key, default)

        # Handle None/empty string for optional values
        if value is None:
            return default

        return value

    def get_section(self, section: str) -> Dict[str, Any]:
        """
        Get all keys in a section.

        Example:
            config.get_section("trading")
            # Returns {"trading.max_positions": 50, "trading.enabled": True, ...}
        """
        prefix = f"{section}."
        return {
            k: v
            for k, v in self._config.items()
            if k.startswith(prefix)
        }

    def get_int(self, key: str, default: int = 0) -> int:
        """Get integer config value."""
        value = self.get(key, default)
        return int(value) if value is not None else default

    def get_float(self, key: str, default: float = 0.0) -> float:
        """Get float config value."""
        value = self.get(key, default)
        return float(value) if value is not None else default

    def get_bool(self, key: str, default: bool = False) -> bool:
        """Get boolean config value."""
        value = self.get(key, default)
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.lower() in ("true", "yes", "1")
        return bool(value) if value is not None else default

    def get_list(self, key: str, default: Optional[List[str]] = None) -> List[str]:
        """Get list config value."""
        value = self.get(key, default)
        if isinstance(value, list):
            return value
        if isinstance(value, str):
            return [v.strip() for v in value.split(",")]
        return value or (default or [])

    def get_path(self, key: str, default: Optional[Path] = None) -> Path:
        """Get path config value with ~ expansion."""
        value = self.get(key, default)
        if value is None:
            return default
        path = Path(value) if isinstance(value, str) else value
        return path.expanduser()

    def has(self, key: str) -> bool:
        """Check if configuration key exists and is not None."""
        return self.get(key) is not None

    def to_dict(self, include_sensitive: bool = False) -> Dict[str, Any]:
        """
        Get all configuration as dictionary.

        Args:
            include_sensitive: If False, mask sensitive values

        Returns:
            Configuration dictionary
        """
        if include_sensitive:
            return self._config.copy()

        result = {}
        for key, value in self._config.items():
            if self._is_sensitive_key(key):
                result[key] = "***MASKED***"
            else:
                result[key] = value

        return result

    def _is_sensitive_key(self, key: str) -> bool:
        """Check if key contains sensitive data."""
        key_lower = key.lower()
        return any(s in key_lower for s in self.SENSITIVE_KEYS)

    def validate(self) -> tuple[bool, List[str]]:
        """
        Validate required configuration.

        Returns:
            (is_valid, list_of_errors)
        """
        errors = []

        # Check required keys (customize as needed)
        required_keys = [
            # Add required keys here
        ]

        for key in required_keys:
            if not self.has(key):
                errors.append(f"Required config key missing: {key}")

        return len(errors) == 0, errors

    @property
    def config_path(self) -> Optional[Path]:
        """Get path to loaded config file."""
        return self._config_path

    def __repr__(self) -> str:
        return f"UnifiedConfig(path={self._config_path}, keys={len(self._config)})"


# Global singleton instance
_global_config: Optional[UnifiedConfigLoader] = None


def get_unified_config(config_path: Optional[Path] = None) -> UnifiedConfigLoader:
    """
    Get global unified configuration instance.

    Args:
        config_path: Explicit path to config file (if not already loaded)

    Returns:
        UnifiedConfigLoader instance
    """
    global _global_config
    if _global_config is None:
        _global_config = UnifiedConfigLoader(config_path)
    return _global_config


def reset_config() -> None:
    """Reset global config instance (for testing)."""
    global _global_config
    _global_config = None


# Convenience functions
def config_get(key: str, default: Any = None) -> Any:
    """Get config value (convenience function)."""
    return get_unified_config().get(key, default)


def config_get_bool(key: str, default: bool = False) -> bool:
    """Get boolean config value."""
    return get_unified_config().get_bool(key, default)


def config_get_int(key: str, default: int = 0) -> int:
    """Get integer config value."""
    return get_unified_config().get_int(key, default)


def config_get_section(section: str) -> Dict[str, Any]:
    """Get all values in a configuration section."""
    return get_unified_config().get_section(section)
