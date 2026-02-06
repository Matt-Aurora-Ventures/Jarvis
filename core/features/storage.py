"""
Feature Flag Storage - Abstract storage interface and JSON implementation.

Provides:
- FlagStorage: Abstract base class for flag storage
- JSONFlagStorage: File-based JSON storage with hot reload support

Usage:
    from core.features.storage import JSONFlagStorage

    storage = JSONFlagStorage("bots/config/features.json")
    flags = storage.load()

    # Modify and save
    flags["new_feature"] = {"enabled": True}
    storage.save(flags)

    # Watch for changes
    stop = storage.watch_for_changes(on_change_callback)
    # ... later ...
    stop()
"""

import json
import logging
import os
import threading
import time
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Callable, Dict, Optional

logger = logging.getLogger(__name__)


class FlagStorage(ABC):
    """
    Abstract base class for feature flag storage.

    Subclasses must implement load() and save() methods.
    """

    @abstractmethod
    def load(self) -> Dict[str, Dict[str, Any]]:
        """
        Load all flags from storage.

        Returns:
            Dictionary mapping flag names to their configuration.
            Each flag config should have at least {"enabled": bool}.
        """
        pass

    @abstractmethod
    def save(self, flags: Dict[str, Dict[str, Any]]) -> None:
        """
        Save all flags to storage.

        Args:
            flags: Dictionary mapping flag names to their configuration.
        """
        pass

    def watch_for_changes(
        self,
        callback: Callable[[Dict[str, Dict[str, Any]]], None],
        poll_interval: float = 1.0
    ) -> Callable[[], None]:
        """
        Watch storage for changes and call callback when detected.

        Default implementation does nothing. Subclasses can override.

        Args:
            callback: Function to call when changes detected.
            poll_interval: How often to check for changes (seconds).

        Returns:
            Callable to stop watching.
        """
        def stop():
            pass
        return stop


class JSONFlagStorage(FlagStorage):
    """
    JSON file-based feature flag storage.

    Supports:
    - Loading from JSON file
    - Saving to JSON file
    - Automatic normalization of flag formats
    - File watching for hot reload

    File format:
    ```json
    {
        "self_healing": true,
        "sleep_compute": false,
        "new_ui": {"enabled": true, "percentage": 10}
    }
    ```

    Both simple boolean values and full config dicts are supported.
    """

    def __init__(self, path: Path | str):
        """
        Initialize JSON flag storage.

        Args:
            path: Path to the JSON file.
        """
        self.path = Path(path) if isinstance(path, str) else path
        self._last_mtime: Optional[float] = None
        self._watch_thread: Optional[threading.Thread] = None
        self._stop_watching = threading.Event()

    def load(self) -> Dict[str, Dict[str, Any]]:
        """
        Load flags from JSON file.

        Returns:
            Dictionary of normalized flag configurations.
            Returns empty dict if file doesn't exist or is invalid.
        """
        if not self.path.exists():
            logger.debug(f"Feature flags file not found: {self.path}")
            return {}

        try:
            with open(self.path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # Track file modification time
            self._last_mtime = self.path.stat().st_mtime

            return self._normalize_flags(data)

        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in feature flags file: {e}")
            return {}
        except Exception as e:
            logger.error(f"Error loading feature flags: {e}")
            return {}

    def _normalize_flags(self, data: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
        """
        Normalize flag data to consistent format.

        Converts simple booleans to full config dicts:
        - true -> {"enabled": true}
        - {"enabled": true, "percentage": 10} -> (unchanged)

        Args:
            data: Raw data from JSON file.

        Returns:
            Normalized flag configurations.
        """
        normalized = {}

        for name, config in data.items():
            if isinstance(config, bool):
                # Simple boolean format
                normalized[name] = {"enabled": config}
            elif isinstance(config, dict):
                # Full config format - ensure "enabled" key exists
                if "enabled" not in config:
                    config["enabled"] = False
                normalized[name] = config
            else:
                # Unknown format - skip with warning
                logger.warning(f"Unknown flag format for '{name}': {type(config)}")

        return normalized

    def save(self, flags: Dict[str, Dict[str, Any]]) -> None:
        """
        Save flags to JSON file.

        Creates parent directories if they don't exist.

        Args:
            flags: Dictionary of flag configurations to save.
        """
        try:
            # Ensure parent directory exists
            self.path.parent.mkdir(parents=True, exist_ok=True)

            with open(self.path, 'w', encoding='utf-8') as f:
                json.dump(flags, f, indent=2)

            # Update modification time
            self._last_mtime = self.path.stat().st_mtime

            logger.debug(f"Saved {len(flags)} flags to {self.path}")

        except Exception as e:
            logger.error(f"Error saving feature flags: {e}")
            raise

    def watch_for_changes(
        self,
        callback: Callable[[Dict[str, Dict[str, Any]]], None],
        poll_interval: float = 1.0
    ) -> Callable[[], None]:
        """
        Watch the JSON file for changes and call callback when modified.

        Uses polling to detect file modifications.

        Args:
            callback: Function to call with new flags when file changes.
            poll_interval: How often to check for changes (seconds).

        Returns:
            Callable to stop watching.
        """
        self._stop_watching.clear()

        def watch_loop():
            """Background thread that polls for file changes."""
            while not self._stop_watching.is_set():
                try:
                    if self.path.exists():
                        current_mtime = self.path.stat().st_mtime

                        if self._last_mtime is not None and current_mtime > self._last_mtime:
                            logger.info(f"Feature flags file changed: {self.path}")
                            new_flags = self.load()
                            callback(new_flags)

                        self._last_mtime = current_mtime

                except Exception as e:
                    logger.error(f"Error watching feature flags: {e}")

                time.sleep(poll_interval)

        self._watch_thread = threading.Thread(target=watch_loop, daemon=True)
        self._watch_thread.start()

        def stop():
            """Stop the watch thread."""
            self._stop_watching.set()
            if self._watch_thread and self._watch_thread.is_alive():
                self._watch_thread.join(timeout=2.0)

        return stop


__all__ = ["FlagStorage", "JSONFlagStorage"]
