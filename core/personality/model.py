"""
Personality Data Model.

Defines the Personality dataclass that represents a bot's personality
configuration including paths to SOUL, IDENTITY, and BOOTSTRAP files.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, List, Dict, Any
import logging

logger = logging.getLogger(__name__)


@dataclass
class Personality:
    """
    Represents a bot's personality configuration.

    Attributes:
        name: Bot's display name (e.g., "ClawdJarvis")
        role: Bot's role description (e.g., "System orchestrator")
        model: LLM model to use (e.g., "claude-3-opus")
        soul_path: Path to SOUL markdown file
        identity_path: Path to IDENTITY markdown file
        bootstrap_path: Path to BOOTSTRAP markdown file
        tone: Description of bot's tone (e.g., "professional, friendly")
        style: Description of communication style
        capabilities: List of bot capabilities
    """

    name: str
    role: str
    model: str
    soul_path: Optional[str] = None
    identity_path: Optional[str] = None
    bootstrap_path: Optional[str] = None
    tone: str = ""
    style: str = ""
    capabilities: List[str] = field(default_factory=list)

    # Internal: base path for resolving relative paths
    _base_path: Optional[str] = field(default=None, repr=False)

    def __post_init__(self):
        """Validate required fields after initialization."""
        if not self.name:
            raise ValueError("name is required")
        if not self.role:
            raise ValueError("role is required")
        if not self.model:
            raise ValueError("model is required")

    def load_files(self) -> Dict[str, Optional[str]]:
        """
        Load and return contents of SOUL, IDENTITY, and BOOTSTRAP files.

        Returns:
            Dict with keys 'soul', 'identity', 'bootstrap' containing
            file contents or None if file doesn't exist or path not set.
        """
        result = {
            "soul": self._load_file(self.soul_path),
            "identity": self._load_file(self.identity_path),
            "bootstrap": self._load_file(self.bootstrap_path),
        }
        return result

    def _load_file(self, file_path: Optional[str]) -> Optional[str]:
        """
        Load a single file's content.

        Args:
            file_path: Path to file (absolute or relative to _base_path)

        Returns:
            File contents as string, or None if path not set or file missing
        """
        if not file_path:
            return None

        # Resolve path
        path = Path(file_path)
        if not path.is_absolute() and self._base_path:
            path = Path(self._base_path) / file_path

        try:
            if path.exists():
                return path.read_text(encoding="utf-8")
            else:
                logger.warning(f"Personality file not found: {path}")
                return None
        except Exception as e:
            logger.error(f"Error reading personality file {path}: {e}")
            return None

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert Personality to dictionary.

        Returns:
            Dictionary representation of the personality.
        """
        return {
            "name": self.name,
            "role": self.role,
            "model": self.model,
            "soul_path": self.soul_path,
            "identity_path": self.identity_path,
            "bootstrap_path": self.bootstrap_path,
            "tone": self.tone,
            "style": self.style,
            "capabilities": self.capabilities,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any], base_path: Optional[str] = None) -> "Personality":
        """
        Create Personality from dictionary.

        Args:
            data: Dictionary with personality fields
            base_path: Base path for resolving relative file paths

        Returns:
            New Personality instance
        """
        return cls(
            name=data.get("name", ""),
            role=data.get("role", ""),
            model=data.get("model", ""),
            soul_path=data.get("soul_path"),
            identity_path=data.get("identity_path"),
            bootstrap_path=data.get("bootstrap_path"),
            tone=data.get("tone", ""),
            style=data.get("style", ""),
            capabilities=data.get("capabilities", []),
            _base_path=base_path,
        )
