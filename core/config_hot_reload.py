"""
Config Hot Reload - Runtime configuration updates without restart.

Provides:
- File-based config watching
- Environment variable overrides
- Callback system for config changes
- Validation before applying
- Rollback on failure
"""

import json
import logging
import os
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, Optional, List, Callable, Set
from threading import Lock
import hashlib

logger = logging.getLogger(__name__)


@dataclass
class ConfigChange:
    """Record of a configuration change."""
    key: str
    old_value: Any
    new_value: Any
    timestamp: str
    source: str  # "file", "env", "api"


class ConfigHotReload:
    """
    Hot-reloadable configuration system.
    
    Features:
    - Watch config files for changes
    - Apply updates without restart
    - Validation before applying
    - Rollback on errors
    - Change history
    """

    _instance: Optional["ConfigHotReload"] = None
    _lock = Lock()

    # Feature flags (ready to activate)
    ENABLE_FILE_WATCHING = False  # Watch files for changes
    ENABLE_VALIDATION = True  # Validate before applying
    ENABLE_ROLLBACK = True  # Rollback on failure

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

        self.config: Dict[str, Any] = {}
        self.config_files: Dict[str, Path] = {}
        self.file_hashes: Dict[str, str] = {}
        self.callbacks: Dict[str, List[Callable]] = {}
        self.validators: Dict[str, Callable] = {}
        self.change_history: List[ConfigChange] = []
        
        self._watching = False
        self._watch_thread: Optional[threading.Thread] = None
        
        self._load_defaults()
        self._initialized = True
        logger.info("ConfigHotReload initialized")

    def _load_defaults(self):
        """Load default configuration."""
        self.config = {
            # Trading defaults
            "trading.max_position_pct": 25.0,
            "trading.daily_loss_limit_pct": 10.0,
            "trading.max_positions": 5,
            "trading.slippage_bps": 50,
            "trading.dry_run": True,
            
            # Bot defaults
            "bot.reply_cooldown_seconds": 12,
            "bot.smart_filter_enabled": True,
            "bot.admin_ids": [],
            
            # API defaults
            "api.rate_limit_per_minute": 60,
            "api.timeout_seconds": 30,
            "api.retry_attempts": 3,
            
            # Monitoring defaults
            "monitoring.health_check_interval": 30,
            "monitoring.metrics_enabled": True,
            "monitoring.log_level": "INFO",
            
            # Security defaults
            "security.require_auth": True,
            "security.session_timeout_minutes": 60,
            "security.max_failed_logins": 5,
        }

    def register_config_file(self, name: str, path: Path):
        """Register a config file for watching."""
        self.config_files[name] = path
        if path.exists():
            self.file_hashes[name] = self._hash_file(path)
            self._load_config_file(name, path)

    def _hash_file(self, path: Path) -> str:
        """Get hash of file contents."""
        try:
            return hashlib.md5(path.read_bytes()).hexdigest()
        except Exception:
            return ""

    def _load_config_file(self, name: str, path: Path):
        """Load config from file."""
        try:
            if path.suffix == ".json":
                with open(path) as f:
                    data = json.load(f)
            elif path.suffix in (".yaml", ".yml"):
                try:
                    import yaml
                    with open(path) as f:
                        data = yaml.safe_load(f)
                except ImportError:
                    logger.warning("PyYAML not installed, skipping YAML config")
                    return
            else:
                return

            for key, value in self._flatten_dict(data, name).items():
                self.set(key, value, source="file", skip_callbacks=True)
                
            logger.info(f"Loaded config from {path}")
        except Exception as e:
            logger.error(f"Failed to load config file {path}: {e}")

    def _flatten_dict(self, d: Dict, prefix: str = "") -> Dict[str, Any]:
        """Flatten nested dict to dot notation."""
        items = {}
        for k, v in d.items():
            key = f"{prefix}.{k}" if prefix else k
            if isinstance(v, dict):
                items.update(self._flatten_dict(v, key))
            else:
                items[key] = v
        return items

    def get(self, key: str, default: Any = None) -> Any:
        """Get a config value."""
        # Check environment override first
        env_key = key.upper().replace(".", "_")
        env_val = os.environ.get(env_key)
        if env_val is not None:
            return self._parse_env_value(env_val)
        
        return self.config.get(key, default)

    def _parse_env_value(self, value: str) -> Any:
        """Parse environment variable to appropriate type."""
        if value.lower() in ("true", "yes", "1"):
            return True
        if value.lower() in ("false", "no", "0"):
            return False
        try:
            return int(value)
        except ValueError:
            pass
        try:
            return float(value)
        except ValueError:
            pass
        return value

    def set(
        self,
        key: str,
        value: Any,
        source: str = "api",
        skip_callbacks: bool = False,
    ) -> bool:
        """Set a config value."""
        # Validate if validator registered
        if self.ENABLE_VALIDATION and key in self.validators:
            try:
                if not self.validators[key](value):
                    logger.warning(f"Config validation failed for {key}")
                    return False
            except Exception as e:
                logger.error(f"Config validator error for {key}: {e}")
                return False

        old_value = self.config.get(key)
        
        # Record change
        change = ConfigChange(
            key=key,
            old_value=old_value,
            new_value=value,
            timestamp=datetime.now(timezone.utc).isoformat(),
            source=source,
        )
        self.change_history.append(change)
        
        # Apply change
        self.config[key] = value
        
        # Trigger callbacks
        if not skip_callbacks:
            self._trigger_callbacks(key, old_value, value)
        
        logger.debug(f"Config updated: {key} = {value} (source: {source})")
        return True

    def register_callback(self, key: str, callback: Callable):
        """Register callback for config changes."""
        if key not in self.callbacks:
            self.callbacks[key] = []
        self.callbacks[key].append(callback)

    def register_validator(self, key: str, validator: Callable):
        """Register validator for config key."""
        self.validators[key] = validator

    def _trigger_callbacks(self, key: str, old_value: Any, new_value: Any):
        """Trigger callbacks for config change."""
        # Exact match callbacks
        for callback in self.callbacks.get(key, []):
            try:
                callback(key, old_value, new_value)
            except Exception as e:
                logger.error(f"Config callback error: {e}")
                if self.ENABLE_ROLLBACK:
                    self.config[key] = old_value
                    logger.info(f"Rolled back {key} to {old_value}")

        # Prefix match callbacks (e.g., "trading.*")
        for pattern, callbacks in self.callbacks.items():
            if pattern.endswith(".*") and key.startswith(pattern[:-2]):
                for callback in callbacks:
                    try:
                        callback(key, old_value, new_value)
                    except Exception as e:
                        logger.error(f"Config callback error: {e}")

    def start_watching(self, interval_seconds: int = 5):
        """Start watching config files for changes."""
        if not self.ENABLE_FILE_WATCHING:
            logger.info("File watching disabled")
            return

        if self._watching:
            return

        self._watching = True
        self._watch_thread = threading.Thread(
            target=self._watch_loop,
            args=(interval_seconds,),
            daemon=True,
        )
        self._watch_thread.start()
        logger.info("Config file watching started")

    def stop_watching(self):
        """Stop watching config files."""
        self._watching = False

    def _watch_loop(self, interval: int):
        """Watch loop for file changes."""
        while self._watching:
            for name, path in self.config_files.items():
                if not path.exists():
                    continue

                new_hash = self._hash_file(path)
                if new_hash != self.file_hashes.get(name):
                    logger.info(f"Config file changed: {path}")
                    self.file_hashes[name] = new_hash
                    self._load_config_file(name, path)

            time.sleep(interval)

    def get_all(self) -> Dict[str, Any]:
        """Get all config values."""
        return self.config.copy()

    def get_by_prefix(self, prefix: str) -> Dict[str, Any]:
        """Get all config values with prefix."""
        return {
            k: v for k, v in self.config.items()
            if k.startswith(prefix)
        }

    def get_change_history(self, limit: int = 50) -> List[Dict]:
        """Get recent config changes."""
        return [
            {
                "key": c.key,
                "old_value": c.old_value,
                "new_value": c.new_value,
                "timestamp": c.timestamp,
                "source": c.source,
            }
            for c in self.change_history[-limit:]
        ]

    def reload_all(self):
        """Reload all config files."""
        for name, path in self.config_files.items():
            if path.exists():
                self._load_config_file(name, path)
                self.file_hashes[name] = self._hash_file(path)

    def export_config(self, path: Path):
        """Export current config to file."""
        try:
            with open(path, 'w') as f:
                json.dump(self.config, f, indent=2)
            logger.info(f"Config exported to {path}")
        except Exception as e:
            logger.error(f"Failed to export config: {e}")


# Singleton accessor
def get_config_manager() -> ConfigHotReload:
    """Get the config manager singleton."""
    return ConfigHotReload()


# Convenience functions
def get_config(key: str, default: Any = None) -> Any:
    """Get a config value."""
    return get_config_manager().get(key, default)


def set_config(key: str, value: Any) -> bool:
    """Set a config value."""
    return get_config_manager().set(key, value)
