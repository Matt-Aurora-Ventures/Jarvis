"""
JARVIS Unified Configuration System

Centralizes all configuration loading and access across the entire system.
- Loads from multiple sources (.env files, JSON configs, environment)
- Provides type-safe access with defaults
- Validates required keys
- Supports hot-reloading
- Integrates with JarvisCore

Usage:
    from core.unified_config import config

    # Access values
    api_key = config.get("telegram.bot_token")
    rpc_url = config.get("solana.rpc_url", "https://api.mainnet-beta.solana.com")

    # Type-safe access
    max_trades = config.get_int("trading.max_daily_trades", 10)
    enabled = config.get_bool("features.auto_trade", False)

    # Nested access
    all_trading = config.section("trading")
"""

import os
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, TypeVar, Union
from dataclasses import dataclass, field
from datetime import datetime

logger = logging.getLogger(__name__)

T = TypeVar('T')


# Find project root
def _find_project_root() -> Path:
    """Find the project root directory."""
    current = Path(__file__).parent
    while current != current.parent:
        if (current / '.git').exists() or (current / 'core').exists():
            return current
        current = current.parent
    return Path(__file__).parent.parent


PROJECT_ROOT = _find_project_root()


@dataclass
class ConfigSource:
    """Represents a configuration source."""
    path: Path
    loaded_at: float
    values: Dict[str, Any]
    priority: int = 0  # Higher = override lower


class UnifiedConfig:
    """
    Unified configuration system for JARVIS.

    Loads configuration from multiple sources in priority order:
    1. Environment variables (highest priority)
    2. Local config files (.local.json, .env.local)
    3. Module-specific configs
    4. Base config files
    5. Default values (lowest priority)
    """

    # Standard .env file locations to search
    ENV_SEARCH_PATHS = [
        PROJECT_ROOT / '.env',
        PROJECT_ROOT / '.env.local',
        PROJECT_ROOT / 'bots' / 'twitter' / '.env',
        PROJECT_ROOT / 'bots' / 'buy_tracker' / '.env',
        PROJECT_ROOT / 'bots' / 'treasury' / '.env',
        PROJECT_ROOT / 'tg_bot' / '.env',
        PROJECT_ROOT / 'lifeos' / '.env',
    ]

    # Standard JSON config locations
    JSON_SEARCH_PATHS = [
        PROJECT_ROOT / 'lifeos' / 'config' / 'lifeos.config.json',
        PROJECT_ROOT / 'lifeos' / 'config' / 'lifeos.config.local.json',
        PROJECT_ROOT / 'config.json',
        PROJECT_ROOT / 'config.local.json',
    ]

    # Environment variable name mappings (normalize different naming conventions)
    ENV_ALIASES = {
        # Telegram
        'telegram.bot_token': ['TELEGRAM_BOT_TOKEN', 'TG_BOT_TOKEN'],
        'telegram.chat_id': ['TELEGRAM_CHAT_ID', 'TG_CHAT_ID', 'TELEGRAM_BUY_BOT_CHAT_ID'],
        'telegram.api_id': ['TELEGRAM_API_ID', 'TG_API_ID'],
        'telegram.api_hash': ['TELEGRAM_API_HASH', 'TG_API_HASH'],

        # Twitter/X
        'twitter.api_key': ['TWITTER_API_KEY', 'X_API_KEY'],
        'twitter.api_secret': ['TWITTER_API_SECRET', 'X_API_SECRET'],
        'twitter.access_token': ['TWITTER_ACCESS_TOKEN', 'X_ACCESS_TOKEN'],
        'twitter.access_token_secret': ['TWITTER_ACCESS_TOKEN_SECRET', 'X_ACCESS_TOKEN_SECRET'],
        'twitter.bearer_token': ['TWITTER_BEARER_TOKEN', 'X_BEARER_TOKEN'],

        # xAI/Grok
        'xai.api_key': ['XAI_API_KEY', 'GROK_API_KEY'],

        # Solana
        'solana.rpc_url': ['SOLANA_RPC_URL', 'RPC_URL', 'HELIUS_RPC_URL'],
        'solana.private_key': ['SOLANA_PRIVATE_KEY', 'WALLET_PRIVATE_KEY'],

        # APIs
        'hyperliquid.api_key': ['HYPERLIQUID_API_KEY', 'HL_API_KEY'],
        'twelve_data.api_key': ['TWELVE_DATA_API_KEY', 'TWELVEDATA_API_KEY'],
        'birdeye.api_key': ['BIRDEYE_API_KEY'],
        'helius.api_key': ['HELIUS_API_KEY'],
    }

    def __init__(self):
        self._values: Dict[str, Any] = {}
        self._sources: List[ConfigSource] = []
        self._loaded_env_files: Set[Path] = set()
        self._required_keys: Set[str] = set()
        self._validators: Dict[str, callable] = {}

        # Load all sources
        self._load_all()

    def _load_all(self):
        """Load configuration from all sources."""
        # 1. Load JSON configs (lowest priority)
        for path in self.JSON_SEARCH_PATHS:
            if path.exists():
                self._load_json(path)

        # 2. Load .env files
        for path in self.ENV_SEARCH_PATHS:
            if path.exists():
                self._load_env_file(path)

        # 3. Load environment variables (highest priority)
        self._load_environment()

        logger.info(f"Loaded config from {len(self._sources)} sources")

    def _load_json(self, path: Path):
        """Load a JSON config file."""
        try:
            with open(path) as f:
                data = json.load(f)

            self._sources.append(ConfigSource(
                path=path,
                loaded_at=datetime.now().timestamp(),
                values=data,
                priority=10,
            ))

            self._merge_values(data)
            logger.debug(f"Loaded JSON config: {path}")

        except Exception as e:
            logger.warning(f"Failed to load {path}: {e}")

    def _load_env_file(self, path: Path):
        """Load a .env file."""
        if path in self._loaded_env_files:
            return

        try:
            values = {}
            with open(path) as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith('#'):
                        continue
                    if '=' in line:
                        key, value = line.split('=', 1)
                        key = key.strip()
                        value = value.strip().strip('"').strip("'")
                        values[key] = value

            self._sources.append(ConfigSource(
                path=path,
                loaded_at=datetime.now().timestamp(),
                values=values,
                priority=50,
            ))

            # Also set in environment
            for key, value in values.items():
                if key not in os.environ:
                    os.environ[key] = value

            self._merge_env_values(values)
            self._loaded_env_files.add(path)
            logger.debug(f"Loaded .env file: {path}")

        except Exception as e:
            logger.warning(f"Failed to load {path}: {e}")

    def _load_environment(self):
        """Load from system environment variables."""
        # Map environment variables to canonical keys
        for canonical, env_names in self.ENV_ALIASES.items():
            for env_name in env_names:
                value = os.environ.get(env_name)
                if value:
                    self._set_nested(canonical, value)
                    break

        # Also load any env vars with our prefixes
        for key, value in os.environ.items():
            if key.startswith(('JARVIS_', 'LIFEOS_')):
                # Convert JARVIS_TRADING_MAX_TRADES to trading.max_trades
                clean_key = key.replace('JARVIS_', '').replace('LIFEOS_', '')
                canonical = clean_key.lower().replace('_', '.')
                self._set_nested(canonical, value)

    def _merge_values(self, data: Dict[str, Any], prefix: str = ''):
        """Recursively merge values into the config."""
        for key, value in data.items():
            full_key = f"{prefix}.{key}" if prefix else key

            if isinstance(value, dict):
                self._merge_values(value, full_key)
            else:
                self._set_nested(full_key, value)

    def _merge_env_values(self, data: Dict[str, Any]):
        """Merge environment variable style values."""
        for key, value in data.items():
            # Try to find canonical key
            for canonical, env_names in self.ENV_ALIASES.items():
                if key in env_names:
                    self._set_nested(canonical, value)
                    break
            else:
                # Use as-is, converting to lowercase dotted
                canonical = key.lower().replace('_', '.')
                self._set_nested(canonical, value)

    def _set_nested(self, key: str, value: Any):
        """Set a value using dotted key notation."""
        parts = key.split('.')
        current = self._values

        for part in parts[:-1]:
            if part not in current:
                current[part] = {}
            elif not isinstance(current[part], dict):
                # Key collision - existing value is not a dict
                # Skip this nested key to avoid overwriting
                return
            current = current[part]

        if isinstance(current, dict):
            current[parts[-1]] = value

    def _get_nested(self, key: str) -> Optional[Any]:
        """Get a value using dotted key notation."""
        parts = key.split('.')
        current = self._values

        for part in parts:
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                return None

        return current

    # ==================== Public API ====================

    def get(self, key: str, default: Any = None) -> Any:
        """
        Get a configuration value.

        Args:
            key: Dotted key path (e.g., "telegram.bot_token")
            default: Default value if not found

        Returns:
            Configuration value or default
        """
        value = self._get_nested(key)

        if value is None:
            # Try environment variable aliases
            if key in self.ENV_ALIASES:
                for env_name in self.ENV_ALIASES[key]:
                    value = os.environ.get(env_name)
                    if value:
                        break

        return value if value is not None else default

    def get_str(self, key: str, default: str = '') -> str:
        """Get a string value."""
        value = self.get(key, default)
        return str(value) if value is not None else default

    def get_int(self, key: str, default: int = 0) -> int:
        """Get an integer value."""
        value = self.get(key, default)
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    def get_float(self, key: str, default: float = 0.0) -> float:
        """Get a float value."""
        value = self.get(key, default)
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    def get_bool(self, key: str, default: bool = False) -> bool:
        """Get a boolean value."""
        value = self.get(key, default)
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.lower() in ('true', '1', 'yes', 'on')
        return bool(value) if value is not None else default

    def get_list(self, key: str, default: List = None) -> List:
        """Get a list value."""
        value = self.get(key, default)
        if value is None:
            return default or []
        if isinstance(value, list):
            return value
        if isinstance(value, str):
            return [x.strip() for x in value.split(',')]
        return [value]

    def section(self, prefix: str) -> Dict[str, Any]:
        """Get all values under a prefix as a dict."""
        result = {}
        prefix_parts = prefix.split('.')

        current = self._values
        for part in prefix_parts:
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                return {}

        if isinstance(current, dict):
            return current.copy()
        return {}

    def has(self, key: str) -> bool:
        """Check if a key exists and has a value."""
        return self.get(key) is not None

    def require(self, *keys: str) -> 'UnifiedConfig':
        """
        Mark keys as required. Call validate() to check.

        Usage:
            config.require('telegram.bot_token', 'xai.api_key').validate()
        """
        self._required_keys.update(keys)
        return self

    def validate(self) -> tuple:
        """
        Validate required keys are present.

        Returns:
            Tuple of (is_valid, list of missing keys)
        """
        missing = []
        for key in self._required_keys:
            if not self.has(key):
                missing.append(key)

        return len(missing) == 0, missing

    def add_validator(self, key: str, validator: callable):
        """Add a custom validator for a key."""
        self._validators[key] = validator

    def validate_all(self) -> Dict[str, str]:
        """
        Run all validators.

        Returns:
            Dict of key -> error message for failed validations
        """
        errors = {}

        for key, validator in self._validators.items():
            value = self.get(key)
            try:
                if not validator(value):
                    errors[key] = f"Validation failed for {key}"
            except Exception as e:
                errors[key] = str(e)

        return errors

    def reload(self):
        """Reload all configuration sources."""
        self._values = {}
        self._sources = []
        self._loaded_env_files = set()
        self._load_all()
        logger.info("Configuration reloaded")

    def to_dict(self) -> Dict[str, Any]:
        """Export all configuration as a dictionary."""
        return self._values.copy()

    def get_sources(self) -> List[str]:
        """Get list of loaded configuration sources."""
        return [str(s.path) for s in self._sources]

    def set(self, key: str, value: Any):
        """
        Set a configuration value at runtime.

        Note: This doesn't persist to disk.
        """
        self._set_nested(key, value)

    # ==================== Convenience Properties ====================

    @property
    def telegram_bot_token(self) -> str:
        return self.get_str('telegram.bot_token')

    @property
    def telegram_chat_id(self) -> str:
        return self.get_str('telegram.chat_id')

    @property
    def xai_api_key(self) -> str:
        return self.get_str('xai.api_key')

    @property
    def solana_rpc_url(self) -> str:
        return self.get_str('solana.rpc_url', 'https://api.mainnet-beta.solana.com')

    @property
    def twitter_api_key(self) -> str:
        return self.get_str('twitter.api_key')


# ==================== Global Instance ====================

# Singleton configuration instance
config = UnifiedConfig()


# ==================== Utility Functions ====================

def get(key: str, default: Any = None) -> Any:
    """Shortcut for config.get()."""
    return config.get(key, default)


def require(*keys: str) -> bool:
    """Check if required keys are present."""
    valid, missing = config.require(*keys).validate()
    if not valid:
        logger.error(f"Missing required config keys: {missing}")
    return valid


def reload():
    """Reload configuration."""
    config.reload()
