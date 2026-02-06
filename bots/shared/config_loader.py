"""
Configuration Loader for ClawdBots.

Provides centralized configuration loading with:
- Environment variable support (highest priority)
- JSON file configuration (/root/clawdbots/config.json)
- Default values (lowest priority)
- Hot-reload support
- Schema validation
- Thread-safe access

Config sources in priority order:
1. Environment variables
2. JSON config file
3. Default values

Usage:
    from bots.shared.config_loader import get_config, load_config, validate_config

    # Load configuration (call once at startup)
    config = load_config()

    # Get a config value
    token = get_config("TELEGRAM_BOT_TOKEN")

    # Get with type conversion
    debug = get_config("DEBUG_MODE", type_=bool)
    admins = get_config("ADMIN_USER_IDS", type_=list)

    # Validate configuration
    errors = validate_config()
    if errors:
        print("Config errors:", errors)

    # Hot reload
    reload_config()
"""

import json
import logging
import os
import threading
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Type, Union

logger = logging.getLogger("clawdbots.config")

# Default config file path (VPS location)
DEFAULT_CONFIG_FILE = "/root/clawdbots/config.json"

# Global config state (thread-safe via lock)
_config_lock = threading.RLock()
_config_cache: Dict[str, Any] = {}
_config_file_path: Optional[str] = None


# =============================================================================
# Default Values
# =============================================================================

# Schema defines: (default_value, required, validator_func)
CONFIG_SCHEMA: Dict[str, tuple] = {
    # Required keys
    "TELEGRAM_BOT_TOKEN": (None, True, None),

    # Optional API keys
    "OPENAI_API_KEY": (None, False, None),
    "ANTHROPIC_API_KEY": (None, False, None),
    "XAI_API_KEY": (None, False, None),

    # Admin configuration
    "ADMIN_USER_IDS": ("", False, "_validate_admin_ids"),

    # Feature flags
    "DEBUG_MODE": ("false", False, "_validate_bool"),

    # Bot-specific settings
    "BOT_NAME": ("clawdbot", False, None),
    "LOG_LEVEL": ("INFO", False, "_validate_log_level"),
    "MAX_MESSAGE_LENGTH": ("4096", False, "_validate_positive_int"),
}

# Keys that contain secrets (should be masked)
SECRET_KEYS = {
    "TELEGRAM_BOT_TOKEN",
    "OPENAI_API_KEY",
    "ANTHROPIC_API_KEY",
    "XAI_API_KEY",
}


# =============================================================================
# Type Conversion
# =============================================================================

def _convert_bool(value: str) -> bool:
    """Convert string to boolean."""
    if isinstance(value, bool):
        return value
    return value.lower() in ("true", "1", "yes", "on")


def _convert_int(value: str) -> int:
    """Convert string to integer."""
    if isinstance(value, int):
        return value
    return int(value)


def _convert_list(value: str) -> List[str]:
    """Convert comma-separated string to list."""
    if isinstance(value, list):
        return value
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


TYPE_CONVERTERS: Dict[Type, Callable] = {
    bool: _convert_bool,
    int: _convert_int,
    list: _convert_list,
}


# =============================================================================
# Validators
# =============================================================================

def _validate_bool(value: str) -> Optional[str]:
    """Validate boolean value."""
    if value is None or value == "":
        return None
    valid_values = {"true", "false", "1", "0", "yes", "no", "on", "off"}
    if str(value).lower() not in valid_values:
        return f"Invalid boolean value: {value}"
    return None


def _validate_admin_ids(value: str) -> Optional[str]:
    """Validate ADMIN_USER_IDS format (comma-separated integers)."""
    if not value:
        return None
    parts = value.split(",")
    for part in parts:
        part = part.strip()
        if part and not part.isdigit():
            return f"Invalid ADMIN_USER_IDS format: '{part}' is not a valid integer"
    return None


def _validate_log_level(value: str) -> Optional[str]:
    """Validate log level."""
    if not value:
        return None
    valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
    if value.upper() not in valid_levels:
        return f"Invalid log level: {value}"
    return None


def _validate_positive_int(value: str) -> Optional[str]:
    """Validate positive integer."""
    if not value:
        return None
    try:
        num = int(value)
        if num <= 0:
            return f"Value must be positive: {value}"
    except ValueError:
        return f"Invalid integer: {value}"
    return None


VALIDATORS: Dict[str, Callable] = {
    "_validate_bool": _validate_bool,
    "_validate_admin_ids": _validate_admin_ids,
    "_validate_log_level": _validate_log_level,
    "_validate_positive_int": _validate_positive_int,
}


# =============================================================================
# Core Functions
# =============================================================================

def load_config(config_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Load configuration from all sources.

    Priority order (highest to lowest):
    1. Environment variables
    2. Config file (JSON)
    3. Default values

    Args:
        config_path: Path to config JSON file. If None, uses DEFAULT_CONFIG_FILE.

    Returns:
        Dictionary containing all configuration values.
    """
    global _config_cache, _config_file_path

    with _config_lock:
        config: Dict[str, Any] = {}

        # Store config path for reload
        _config_file_path = config_path or DEFAULT_CONFIG_FILE

        # Step 1: Load defaults
        for key, (default, _, _) in CONFIG_SCHEMA.items():
            if default is not None:
                config[key] = default

        # Step 2: Load from file
        file_config = _load_config_file(_config_file_path)
        config.update(file_config)

        # Step 3: Load from environment (overrides everything)
        for key in CONFIG_SCHEMA:
            env_value = os.environ.get(key)
            if env_value is not None:
                config[key] = env_value

        # Also load any env vars that match schema keys
        for key in list(config.keys()):
            env_value = os.environ.get(key)
            if env_value is not None:
                config[key] = env_value

        # Store in cache
        _config_cache = config.copy()

        logger.debug(f"Config loaded: {len(config)} keys")
        return config


def _load_config_file(path: str) -> Dict[str, Any]:
    """Load configuration from JSON file."""
    try:
        file_path = Path(path)
        if not file_path.exists():
            logger.debug(f"Config file not found: {path}")
            return {}

        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        if not isinstance(data, dict):
            logger.warning(f"Config file is not a dict: {path}")
            return {}

        logger.debug(f"Loaded {len(data)} keys from {path}")
        return data

    except json.JSONDecodeError as e:
        logger.warning(f"Invalid JSON in config file {path}: {e}")
        return {}
    except Exception as e:
        logger.warning(f"Failed to load config file {path}: {e}")
        return {}


def get_config(
    key: str,
    default: Any = None,
    type_: Optional[Type] = None,
) -> Any:
    """
    Get a configuration value.

    Priority: Environment variable > Cache > Schema default > Provided default

    Args:
        key: Configuration key name.
        default: Default value if key not found.
        type_: Optional type to convert value to (bool, int, list).

    Returns:
        Configuration value (optionally converted to specified type).
    """
    with _config_lock:
        # Environment variables always take highest priority
        value = os.environ.get(key)

        # Check cache if env not set
        if value is None and _config_cache:
            value = _config_cache.get(key)

        # Check schema defaults if still not found
        if value is None and key in CONFIG_SCHEMA:
            value = CONFIG_SCHEMA[key][0]  # default value

        # Fall back to provided default
        if value is None:
            value = default

        # Type conversion
        if type_ is not None and value is not None:
            converter = TYPE_CONVERTERS.get(type_)
            if converter:
                try:
                    value = converter(value)
                except (ValueError, TypeError) as e:
                    logger.warning(f"Failed to convert {key} to {type_.__name__}: {e}")
                    return default

        return value


def reload_config() -> Dict[str, Any]:
    """
    Reload configuration from all sources.

    Hot-reload support: picks up changes from environment and config file.

    Returns:
        New configuration dictionary.
    """
    global _config_file_path

    with _config_lock:
        config_path = _config_file_path or DEFAULT_CONFIG_FILE
        return load_config(config_path=config_path)


def validate_config() -> List[str]:
    """
    Validate the current configuration.

    Checks:
    - Required keys are present and non-empty
    - Values pass schema validation

    Returns:
        List of error messages (empty if valid).
    """
    errors: List[str] = []

    with _config_lock:
        config = _config_cache or {}

        for key, (default, required, validator_name) in CONFIG_SCHEMA.items():
            value = config.get(key) or os.environ.get(key)

            # Check required keys
            if required and not value:
                errors.append(f"Missing required config: {key}")
                continue

            # Run validator if specified
            if validator_name and value:
                validator = VALIDATORS.get(validator_name)
                if validator:
                    error = validator(value)
                    if error:
                        errors.append(f"{key}: {error}")

    return errors


def get_config_debug_info() -> str:
    """
    Get configuration info for debugging (secrets masked).

    Returns:
        Formatted string with config keys and masked values.
    """
    with _config_lock:
        lines = ["Configuration Debug Info:", "-" * 40]

        for key in sorted(_config_cache.keys()):
            value = _config_cache[key]

            # Mask secrets
            if key in SECRET_KEYS and value:
                if len(str(value)) > 8:
                    masked = f"{str(value)[:4]}...{str(value)[-4:]}"
                else:
                    masked = "***"
                lines.append(f"  {key}: {masked}")
            else:
                lines.append(f"  {key}: {value}")

        return "\n".join(lines)


# =============================================================================
# Convenience Functions
# =============================================================================

def is_debug_mode() -> bool:
    """Check if debug mode is enabled."""
    return get_config("DEBUG_MODE", type_=bool, default=False)


def get_admin_ids() -> List[int]:
    """Get list of admin user IDs."""
    ids_str = get_config("ADMIN_USER_IDS", default="")
    if not ids_str:
        return []
    try:
        return [int(x.strip()) for x in ids_str.split(",") if x.strip().isdigit()]
    except ValueError:
        return []


def is_admin(user_id: int) -> bool:
    """Check if a user ID is an admin."""
    return user_id in get_admin_ids()


def get_api_key(provider: str) -> Optional[str]:
    """
    Get API key for a provider.

    Args:
        provider: Provider name (openai, anthropic, xai)

    Returns:
        API key or None if not configured.
    """
    key_map = {
        "openai": "OPENAI_API_KEY",
        "anthropic": "ANTHROPIC_API_KEY",
        "xai": "XAI_API_KEY",
    }
    env_key = key_map.get(provider.lower())
    if env_key:
        return get_config(env_key)
    return None


# =============================================================================
# Module Exports
# =============================================================================

__all__ = [
    # Core functions
    "get_config",
    "load_config",
    "reload_config",
    "validate_config",
    "get_config_debug_info",
    # Convenience functions
    "is_debug_mode",
    "get_admin_ids",
    "is_admin",
    "get_api_key",
    # Constants
    "CONFIG_SCHEMA",
    "SECRET_KEYS",
    "DEFAULT_CONFIG_FILE",
]
