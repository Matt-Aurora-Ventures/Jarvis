"""
Configuration Sources.

Provides abstract ConfigSource and concrete implementations:
- EnvSource - load from environment variables
- FileSource - load from JSON/YAML files
- ChainedSource - fallback chain of sources
"""

import os
import re
import json
import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, List, Optional, Callable, Tuple

logger = logging.getLogger(__name__)

# Try to import yaml
try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False


class ConfigSource(ABC):
    """
    Abstract base class for configuration sources.

    All configuration sources must implement the load() method
    that returns a flattened dictionary of configuration values.
    """

    @abstractmethod
    def load(self) -> Dict[str, Any]:
        """
        Load configuration from this source.

        Returns:
            Dict with flattened configuration keys (dot notation)
        """
        pass


class EnvSource(ConfigSource):
    """
    Load configuration from environment variables.

    Args:
        prefix: Only load env vars with this prefix (e.g., "MYAPP_")
        strip_prefix: Remove prefix from keys (default: True)
        convert_types: Convert string values to int/float/bool/list
        exclude_patterns: List of patterns to exclude from loading
    """

    def __init__(
        self,
        prefix: str = "",
        strip_prefix: bool = True,
        convert_types: bool = False,
        exclude_patterns: Optional[List[str]] = None
    ):
        self.prefix = prefix
        self.strip_prefix = strip_prefix
        self.convert_types = convert_types
        self.exclude_patterns = exclude_patterns or []

    def load(self) -> Dict[str, Any]:
        """Load environment variables matching prefix."""
        config: Dict[str, Any] = {}

        for key, value in os.environ.items():
            # Filter by prefix
            if self.prefix and not key.startswith(self.prefix):
                continue

            # Check exclude patterns
            if self._should_exclude(key):
                continue

            # Determine output key
            if self.prefix and self.strip_prefix:
                output_key = key[len(self.prefix):]
            else:
                output_key = key

            # Convert types if requested
            if self.convert_types:
                value = self._convert_value(value)

            config[output_key] = value

        return config

    def _should_exclude(self, key: str) -> bool:
        """Check if key matches any exclude pattern."""
        for pattern in self.exclude_patterns:
            if pattern in key:
                return True
        return False

    def _convert_value(self, value: str) -> Any:
        """Convert string value to appropriate type."""
        # Boolean
        if value.lower() in ("true", "yes", "1", "on"):
            return True
        if value.lower() in ("false", "no", "0", "off"):
            return False

        # Integer
        try:
            return int(value)
        except ValueError:
            pass

        # Float
        try:
            return float(value)
        except ValueError:
            pass

        # List (comma-separated)
        if "," in value:
            return [v.strip() for v in value.split(",")]

        return value


class FileSource(ConfigSource):
    """
    Load configuration from JSON or YAML file.

    Args:
        path: Path to configuration file
        optional: If True, return empty dict if file not found
        expand_env: Expand ${VAR} patterns in values
    """

    def __init__(
        self,
        path: str,
        optional: bool = False,
        expand_env: bool = False
    ):
        self.path = Path(path)
        self.optional = optional
        self.expand_env = expand_env

    def load(self) -> Dict[str, Any]:
        """Load configuration from file."""
        if not self.path.exists():
            if self.optional:
                return {}
            raise FileNotFoundError(f"Config file not found: {self.path}")

        try:
            data = self._load_file()
        except Exception as e:
            raise ValueError(f"Failed to load config file {self.path}: {e}")

        # Flatten nested dict
        flattened = self._flatten(data)

        # Expand env vars if requested
        if self.expand_env:
            flattened = {k: self._expand_env(v) for k, v in flattened.items()}

        return flattened

    def _load_file(self) -> Dict[str, Any]:
        """Load raw data from file."""
        with open(self.path, "r", encoding="utf-8") as f:
            if self.path.suffix in (".yaml", ".yml"):
                if not HAS_YAML:
                    raise ValueError("PyYAML not installed, cannot load YAML files")
                return yaml.safe_load(f) or {}
            elif self.path.suffix == ".json":
                return json.load(f)
            else:
                # Try JSON first, then YAML
                try:
                    return json.load(f)
                except json.JSONDecodeError:
                    if HAS_YAML:
                        f.seek(0)
                        return yaml.safe_load(f) or {}
                    raise

    def _flatten(self, data: Dict[str, Any], prefix: str = "") -> Dict[str, Any]:
        """Flatten nested dictionary to dot notation."""
        result: Dict[str, Any] = {}

        for key, value in data.items():
            full_key = f"{prefix}.{key}" if prefix else key

            if isinstance(value, dict):
                result.update(self._flatten(value, full_key))
            else:
                result[full_key] = value

        return result

    def _expand_env(self, value: Any) -> Any:
        """Expand ${VAR} and ${VAR:default} patterns in string."""
        if not isinstance(value, str):
            return value

        pattern = r"\$\{([^}]+)\}"
        matches = re.findall(pattern, value)

        result = value
        for match in matches:
            placeholder = f"${{{match}}}"

            if ":" in match:
                var_name, default = match.split(":", 1)
                var_value = os.environ.get(var_name.strip(), default)
            else:
                var_name = match.strip()
                var_value = os.environ.get(var_name, "")

            result = result.replace(placeholder, var_value)

        return result


class ChainedSource(ConfigSource):
    """
    Chain multiple config sources with fallback/override behavior.

    Later sources override earlier sources (higher priority).
    Sources can also be added with explicit priority numbers.

    Args:
        sources: List of ConfigSource instances
    """

    def __init__(self, sources: Optional[List[ConfigSource]] = None):
        self._sources: List[Tuple[ConfigSource, int]] = []
        self._next_priority = 0

        if sources:
            for source in sources:
                self.add_source(source)

    def add_source(self, source: ConfigSource, priority: Optional[int] = None) -> None:
        """
        Add a source to the chain.

        Args:
            source: ConfigSource instance
            priority: Explicit priority (higher = higher priority).
                     If None, uses auto-incrementing priority.
        """
        if priority is None:
            priority = self._next_priority
            self._next_priority += 1

        self._sources.append((source, priority))

    def load(self) -> Dict[str, Any]:
        """
        Load configuration from all sources.

        Sources with higher priority override those with lower priority.
        """
        if not self._sources:
            return {}

        # Sort by priority (lower first, so higher overrides)
        sorted_sources = sorted(self._sources, key=lambda x: x[1])

        config: Dict[str, Any] = {}

        for source, _ in sorted_sources:
            try:
                source_config = source.load()
                config.update(source_config)
            except FileNotFoundError:
                # Optional sources that don't exist
                continue
            except Exception as e:
                logger.warning(f"Failed to load from source {source}: {e}")
                continue

        return config


# Convenience function to create a standard source chain
def create_default_source_chain(
    config_file: Optional[str] = None,
    env_prefix: str = "",
    extra_sources: Optional[List[ConfigSource]] = None
) -> ChainedSource:
    """
    Create a standard configuration source chain.

    Order (lowest to highest priority):
    1. Default config file (if exists)
    2. Custom config file (if provided)
    3. Environment variables
    4. Extra sources

    Args:
        config_file: Path to config file
        env_prefix: Prefix for environment variables
        extra_sources: Additional sources to add

    Returns:
        ChainedSource with standard configuration
    """
    chain = ChainedSource()

    # Default config locations
    default_paths = [
        Path.cwd() / "config.yaml",
        Path.cwd() / "config.json",
        Path.home() / ".lifeos" / "config.yaml",
    ]

    for path in default_paths:
        if path.exists():
            chain.add_source(FileSource(str(path), optional=True), priority=10)
            break

    # Custom config file
    if config_file:
        chain.add_source(FileSource(config_file, optional=True), priority=20)

    # Environment variables
    chain.add_source(EnvSource(prefix=env_prefix, strip_prefix=True), priority=30)

    # Extra sources
    if extra_sources:
        for i, source in enumerate(extra_sources):
            chain.add_source(source, priority=40 + i)

    return chain
