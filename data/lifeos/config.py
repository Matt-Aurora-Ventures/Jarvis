"""
Jarvis Configuration System

Centralized configuration management with:
- Environment variable loading
- File-based config (YAML/JSON)
- Validation and defaults
- Secret management
- Runtime config updates

Usage:
    from lifeos.config import Config, get_config

    config = get_config()
    api_key = config.get("groq.api_key")
    config.set("trading.enabled", True)
"""

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, TypeVar, Union
import logging

logger = logging.getLogger(__name__)

T = TypeVar('T')


@dataclass
class ConfigSection:
    """A section of configuration."""
    name: str
    data: Dict[str, Any] = field(default_factory=dict)
    sensitive_keys: Set[str] = field(default_factory=set)

    def get(self, key: str, default: T = None) -> T:
        """Get a value from this section."""
        return self.data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """Set a value in this section."""
        self.data[key] = value

    def to_dict(self, include_sensitive: bool = False) -> Dict[str, Any]:
        """Convert to dictionary, optionally masking sensitive values."""
        if include_sensitive:
            return dict(self.data)

        result = {}
        for key, value in self.data.items():
            if key in self.sensitive_keys:
                result[key] = "***MASKED***"
            else:
                result[key] = value
        return result


class Config:
    """
    Centralized configuration manager.

    Loads configuration from:
    1. Default values
    2. Config files (jarvis.json, jarvis.yaml)
    3. Environment variables (JARVIS_*)
    4. Runtime updates

    Later sources override earlier ones.
    """

    # Default configuration
    DEFAULTS = {
        "general": {
            "name": "Jarvis",
            "version": "4.0.0",
            "debug": False,
            "log_level": "INFO",
            "data_dir": "~/.jarvis",
        },
        "llm": {
            "provider": "groq",
            "model": "llama-3.3-70b-versatile",
            "temperature": 0.7,
            "max_tokens": 500,
            "fallback_provider": "ollama",
            "consensus_for_complex": False,
        },
        "trading": {
            "enabled": False,
            "paper_mode": True,
            "max_position_pct": 0.1,
            "default_slippage": 0.01,
            "rpc_url": "https://api.mainnet-beta.solana.com",
        },
        "persona": {
            "default": "jarvis",
            "voice_enabled": False,
            "voice_id": "morgan_freeman",
        },
        "plugins": {
            "enabled": True,
            "auto_load": True,
            "directories": ["plugins"],
        },
        "memory": {
            "max_history": 1000,
            "trading_ttl_hours": 24,
            "scratch_ttl_hours": 1,
        },
        "events": {
            "max_history": 1000,
            "max_dead_letters": 100,
        },
        "telegram": {
            "enabled": False,
            "polling_interval": 1.0,
        },
        "twitter": {
            "enabled": False,
            "polling_interval": 60.0,
        },
        "notifications": {
            "desktop_enabled": True,
            "sound_enabled": True,
        },
    }

    # Sensitive keys that should be masked in logs
    SENSITIVE_KEYS = {
        "api_key", "api_secret", "token", "password", "secret",
        "private_key", "wallet_key", "bot_token", "bearer_token",
    }

    def __init__(
        self,
        config_file: Optional[Path] = None,
        env_prefix: str = "JARVIS",
    ):
        """
        Initialize configuration.

        Args:
            config_file: Path to config file (auto-detected if None)
            env_prefix: Prefix for environment variables
        """
        self._sections: Dict[str, ConfigSection] = {}
        self._env_prefix = env_prefix
        self._config_file = config_file
        self._loaded = False

        # Initialize with defaults
        self._load_defaults()

    def _load_defaults(self) -> None:
        """Load default configuration."""
        for section_name, section_data in self.DEFAULTS.items():
            sensitive = {k for k in section_data.keys() if self._is_sensitive_key(k)}
            self._sections[section_name] = ConfigSection(
                name=section_name,
                data=dict(section_data),
                sensitive_keys=sensitive,
            )

    def _is_sensitive_key(self, key: str) -> bool:
        """Check if a key contains sensitive data."""
        key_lower = key.lower()
        return any(s in key_lower for s in self.SENSITIVE_KEYS)

    def load(self) -> "Config":
        """
        Load configuration from all sources.

        Returns:
            Self for chaining
        """
        # Load from file
        self._load_from_file()

        # Load from environment
        self._load_from_env()

        self._loaded = True
        logger.info("Configuration loaded")
        return self

    def _load_from_file(self) -> None:
        """Load configuration from file."""
        if self._config_file and self._config_file.exists():
            self._load_json_file(self._config_file)
            return

        # Auto-detect config file
        search_paths = [
            Path.cwd() / "jarvis.json",
            Path.cwd() / "config" / "jarvis.json",
            Path.home() / ".jarvis" / "config.json",
        ]

        for path in search_paths:
            if path.exists():
                self._load_json_file(path)
                self._config_file = path
                return

    def _load_json_file(self, path: Path) -> None:
        """Load a JSON config file."""
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)

            for section_name, section_data in data.items():
                if section_name in self._sections:
                    self._sections[section_name].data.update(section_data)
                else:
                    sensitive = {k for k in section_data.keys() if self._is_sensitive_key(k)}
                    self._sections[section_name] = ConfigSection(
                        name=section_name,
                        data=section_data,
                        sensitive_keys=sensitive,
                    )

            logger.debug(f"Loaded config from {path}")
        except Exception as e:
            logger.warning(f"Failed to load config from {path}: {e}")

    def _load_from_env(self) -> None:
        """Load configuration from environment variables."""
        prefix = f"{self._env_prefix}_"

        for key, value in os.environ.items():
            if not key.startswith(prefix):
                continue

            # Parse key: JARVIS_SECTION_KEY -> section.key
            parts = key[len(prefix):].lower().split("_", 1)
            if len(parts) != 2:
                continue

            section_name, config_key = parts

            # Convert value type
            parsed_value = self._parse_env_value(value)

            if section_name in self._sections:
                self._sections[section_name].set(config_key, parsed_value)
            else:
                sensitive = {config_key} if self._is_sensitive_key(config_key) else set()
                self._sections[section_name] = ConfigSection(
                    name=section_name,
                    data={config_key: parsed_value},
                    sensitive_keys=sensitive,
                )

    def _parse_env_value(self, value: str) -> Any:
        """Parse environment variable value to appropriate type."""
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

        # JSON
        if value.startswith(("{", "[")):
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                pass

        return value

    def get(self, key: str, default: T = None) -> T:
        """
        Get a configuration value.

        Args:
            key: Dot-separated key (e.g., "llm.api_key")
            default: Default value if not found

        Returns:
            Configuration value
        """
        parts = key.split(".", 1)
        if len(parts) == 1:
            # Just section name, return whole section
            section = self._sections.get(parts[0])
            return section.data if section else default

        section_name, config_key = parts
        section = self._sections.get(section_name)
        if section:
            return section.get(config_key, default)
        return default

    def set(self, key: str, value: Any) -> None:
        """
        Set a configuration value.

        Args:
            key: Dot-separated key
            value: Value to set
        """
        parts = key.split(".", 1)
        if len(parts) != 2:
            raise ValueError(f"Key must be section.key format: {key}")

        section_name, config_key = parts
        if section_name not in self._sections:
            self._sections[section_name] = ConfigSection(name=section_name)

        self._sections[section_name].set(config_key, value)

    def get_section(self, name: str) -> Optional[Dict[str, Any]]:
        """Get an entire configuration section."""
        section = self._sections.get(name)
        return section.data if section else None

    def has(self, key: str) -> bool:
        """Check if a configuration key exists."""
        return self.get(key) is not None

    def to_dict(self, include_sensitive: bool = False) -> Dict[str, Any]:
        """Convert entire config to dictionary."""
        return {
            name: section.to_dict(include_sensitive)
            for name, section in self._sections.items()
        }

    def save(self, path: Optional[Path] = None) -> bool:
        """
        Save configuration to file.

        Args:
            path: Path to save to (uses original if None)

        Returns:
            True if saved successfully
        """
        path = path or self._config_file
        if not path:
            return False

        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(self.to_dict(include_sensitive=True), f, indent=2)
            return True
        except Exception as e:
            logger.error(f"Failed to save config: {e}")
            return False

    def require(self, key: str) -> Any:
        """
        Get a required configuration value.

        Raises:
            ValueError: If key is not set
        """
        value = self.get(key)
        if value is None:
            raise ValueError(f"Required configuration missing: {key}")
        return value


# Global configuration instance
_global_config: Optional[Config] = None


def get_config() -> Config:
    """Get the global configuration instance."""
    global _global_config
    if _global_config is None:
        _global_config = Config().load()
    return _global_config


def set_config(config: Config) -> None:
    """Set the global configuration instance."""
    global _global_config
    _global_config = config
