"""
Configuration module for Jarvis.

Provides unified configuration management via config.yaml.
"""

import json
from pathlib import Path
from typing import Any, Dict

from core.config.unified_config import (
    UnifiedConfigLoader,
    get_unified_config,
    reset_config,
    config_get,
    config_get_bool,
    config_get_int,
    config_get_section,
)

from core.config.validator import (
    ConfigValidator,
    ConfigValidationError,
    ValidationLevel,
    ValidationResult,
    validate_config,
    get_validator,
    print_validation_summary,
)

ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = ROOT / "lifeos" / "config"
BASE_CONFIG = CONFIG_DIR / "lifeos.config.json"
LOCAL_CONFIG = CONFIG_DIR / "lifeos.config.local.json"


def _load_json(path: Path) -> Dict[str, Any]:
    try:
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        if isinstance(data, dict):
            return data
        return {}
    except FileNotFoundError:
        return {}
    except json.JSONDecodeError:
        return {}


def _deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    result: Dict[str, Any] = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def load_config() -> Dict[str, Any]:
    """Load legacy LifeOS JSON config (backward compatible)."""
    base = _load_json(BASE_CONFIG)
    local = _load_json(LOCAL_CONFIG)
    if local:
        return _deep_merge(base, local)
    return base


def save_local_config(config_data: Dict[str, Any]) -> None:
    """Persist overrides to the local config file."""
    LOCAL_CONFIG.parent.mkdir(parents=True, exist_ok=True)
    with open(LOCAL_CONFIG, "w", encoding="utf-8") as handle:
        json.dump(config_data, handle, indent=2, sort_keys=True)


def update_local_config(updates: Dict[str, Any]) -> Dict[str, Any]:
    """Merge updates into local config and return the merged config."""
    current = _load_json(LOCAL_CONFIG)
    merged = _deep_merge(current, updates)
    save_local_config(merged)
    base = _load_json(BASE_CONFIG)
    return _deep_merge(base, merged)


def resolve_path(path_value: str) -> Path:
    path = Path(path_value)
    if not path.is_absolute():
        return (ROOT / path).resolve()
    return path

__all__ = [
    # Unified config
    "UnifiedConfigLoader",
    "get_unified_config",
    "reset_config",
    "config_get",
    "config_get_bool",
    "config_get_int",
    "config_get_section",
    # Validation
    "ConfigValidator",
    "ConfigValidationError",
    "ValidationLevel",
    "ValidationResult",
    "validate_config",
    "get_validator",
    "print_validation_summary",
    # Legacy config
    "load_config",
    "save_local_config",
    "update_local_config",
    "resolve_path",
]
