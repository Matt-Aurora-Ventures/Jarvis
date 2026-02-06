"""
Personality Loader.

Provides PersonalityLoader class for loading bot personalities from
configuration files in the bots/ directory.
"""

import json
import logging
from pathlib import Path
from typing import Dict, Optional

from core.personality.model import Personality

logger = logging.getLogger(__name__)


class PersonalityNotFoundError(Exception):
    """Raised when a requested bot personality is not found."""
    pass


class PersonalityLoadError(Exception):
    """Raised when there's an error loading a personality configuration."""
    pass


# Singleton instance
_loader_instance: Optional["PersonalityLoader"] = None


def get_loader(bots_dir: Optional[str] = None) -> "PersonalityLoader":
    """
    Get the singleton PersonalityLoader instance.

    Args:
        bots_dir: Path to bots directory. Only used on first call.

    Returns:
        PersonalityLoader singleton instance.
    """
    global _loader_instance
    if _loader_instance is None:
        _loader_instance = PersonalityLoader(bots_dir=bots_dir)
    return _loader_instance


def _reset_loader():
    """Reset the singleton instance. Used for testing."""
    global _loader_instance
    _loader_instance = None


class PersonalityLoader:
    """
    Loads and caches bot personality configurations.

    Looks for personality.json files in each subdirectory of the bots/
    directory and parses them into Personality objects.

    Usage:
        loader = PersonalityLoader(bots_dir="path/to/bots")
        personality = loader.load("clawdjarvis")
        all_personalities = loader.get_all()
    """

    def __init__(self, bots_dir: Optional[str] = None):
        """
        Initialize PersonalityLoader.

        Args:
            bots_dir: Path to bots directory. If None, uses default.
        """
        if bots_dir:
            self.bots_dir = Path(bots_dir)
        else:
            # Default to bots/ relative to project root
            self.bots_dir = Path(__file__).parent.parent.parent / "bots"

        self._cache: Dict[str, Personality] = {}
        logger.info(f"PersonalityLoader initialized with bots_dir: {self.bots_dir}")

    def load(self, bot_name: str) -> Personality:
        """
        Load a bot's personality configuration.

        Args:
            bot_name: Name of the bot directory (e.g., "clawdjarvis")

        Returns:
            Personality object for the bot

        Raises:
            PersonalityNotFoundError: If bot directory or config not found
            PersonalityLoadError: If config file is invalid
        """
        # Check cache first
        if bot_name in self._cache:
            return self._cache[bot_name]

        # Load from disk
        personality = self._load_from_disk(bot_name)
        self._cache[bot_name] = personality
        return personality

    def reload(self, bot_name: str) -> Personality:
        """
        Reload a bot's personality from disk, clearing cache.

        Args:
            bot_name: Name of the bot directory

        Returns:
            Fresh Personality object loaded from disk

        Raises:
            PersonalityNotFoundError: If bot not found
            PersonalityLoadError: If config invalid
        """
        # Clear from cache
        if bot_name in self._cache:
            del self._cache[bot_name]

        # Load fresh
        return self.load(bot_name)

    def get_all(self) -> Dict[str, Personality]:
        """
        Load and return all bot personalities.

        Returns:
            Dictionary mapping bot name to Personality object
        """
        result: Dict[str, Personality] = {}

        if not self.bots_dir.exists():
            logger.warning(f"Bots directory does not exist: {self.bots_dir}")
            return result

        for bot_dir in self.bots_dir.iterdir():
            if not bot_dir.is_dir():
                continue

            config_path = bot_dir / "personality.json"
            if not config_path.exists():
                continue

            try:
                personality = self.load(bot_dir.name)
                result[bot_dir.name] = personality
            except (PersonalityNotFoundError, PersonalityLoadError) as e:
                logger.warning(f"Skipping bot {bot_dir.name}: {e}")
                continue

        return result

    def _load_from_disk(self, bot_name: str) -> Personality:
        """
        Load a personality from disk.

        Args:
            bot_name: Name of the bot directory

        Returns:
            Personality object

        Raises:
            PersonalityNotFoundError: If bot directory or config not found
            PersonalityLoadError: If config file is invalid
        """
        bot_dir = self.bots_dir / bot_name

        # Check bot directory exists
        if not bot_dir.exists() or not bot_dir.is_dir():
            raise PersonalityNotFoundError(
                f"Bot directory not found: {bot_dir}"
            )

        # Check for personality.json
        config_path = bot_dir / "personality.json"
        if not config_path.exists():
            raise PersonalityNotFoundError(
                f"personality.json not found in {bot_dir}"
            )

        # Load and parse JSON
        try:
            config_text = config_path.read_text(encoding="utf-8")
            config_data = json.loads(config_text)
        except json.JSONDecodeError as e:
            raise PersonalityLoadError(
                f"Invalid JSON in {config_path}: {e}"
            )
        except Exception as e:
            raise PersonalityLoadError(
                f"Error reading {config_path}: {e}"
            )

        # Create Personality from config
        try:
            personality = Personality.from_dict(
                config_data,
                base_path=str(bot_dir)
            )
            return personality
        except ValueError as e:
            raise PersonalityLoadError(
                f"Invalid personality config in {config_path}: {e}"
            )
