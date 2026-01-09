"""
Plugin Manifest Schema

Defines the structure for plugin metadata and configuration.
Uses Pydantic for validation and type safety.

Example manifest.json:
{
    "name": "crypto-alerts",
    "version": "1.0.0",
    "description": "Real-time crypto price alerts",
    "author": "Jarvis Team",
    "dependencies": ["market-data"],
    "entry_point": "main.py",
    "permissions": ["notifications", "market_read"]
}
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class PluginPermission(Enum):
    """Available plugin permissions."""
    # Service access
    LLM_READ = "llm_read"
    LLM_WRITE = "llm_write"
    MARKET_READ = "market_read"
    MARKET_WRITE = "market_write"
    NOTIFICATIONS = "notifications"

    # System access
    FILE_READ = "file_read"
    FILE_WRITE = "file_write"
    NETWORK = "network"
    SUBPROCESS = "subprocess"

    # Data access
    MEMORY_READ = "memory_read"
    MEMORY_WRITE = "memory_write"
    CONFIG_READ = "config_read"
    CONFIG_WRITE = "config_write"


class PluginStatus(Enum):
    """Plugin lifecycle status."""
    UNLOADED = "unloaded"
    LOADING = "loading"
    LOADED = "loaded"
    ENABLED = "enabled"
    DISABLED = "disabled"
    ERROR = "error"
    UNLOADING = "unloading"


@dataclass
class PluginDependency:
    """A plugin dependency specification."""
    name: str
    version: Optional[str] = None  # Semver constraint, e.g., ">=1.0.0"
    optional: bool = False


@dataclass
class PluginManifest:
    """
    Plugin manifest containing metadata and configuration.

    This is the contract between plugins and the host system.
    """
    # Required fields
    name: str
    version: str
    entry_point: str  # Relative path to main module

    # Optional metadata
    description: str = ""
    author: str = ""
    license: str = ""
    homepage: str = ""
    repository: str = ""

    # Dependencies
    dependencies: List[PluginDependency] = field(default_factory=list)
    python_requires: str = ">=3.10"

    # Permissions
    permissions: List[str] = field(default_factory=list)

    # Configuration schema (JSON Schema format)
    config_schema: Optional[Dict[str, Any]] = None
    default_config: Dict[str, Any] = field(default_factory=dict)

    # Lifecycle settings
    auto_enable: bool = True
    priority: int = 100  # Lower = loads earlier

    # Runtime info (set by loader)
    path: Optional[Path] = None
    loaded_at: Optional[datetime] = None
    status: PluginStatus = PluginStatus.UNLOADED
    error_message: Optional[str] = None

    def validate(self) -> List[str]:
        """
        Validate manifest fields.

        Returns:
            List of validation error messages (empty if valid)
        """
        errors = []

        # Required fields
        if not self.name:
            errors.append("Plugin name is required")
        elif not self.name.replace("-", "").replace("_", "").isalnum():
            errors.append("Plugin name must be alphanumeric (with - or _)")

        if not self.version:
            errors.append("Plugin version is required")
        elif not self._is_valid_semver(self.version):
            errors.append(f"Invalid version format: {self.version}")

        if not self.entry_point:
            errors.append("Entry point is required")
        elif not self.entry_point.endswith(".py"):
            errors.append("Entry point must be a .py file")

        # Validate permissions
        valid_permissions = {p.value for p in PluginPermission}
        for perm in self.permissions:
            if perm not in valid_permissions:
                errors.append(f"Invalid permission: {perm}")

        # Validate dependencies
        for dep in self.dependencies:
            if not dep.name:
                errors.append("Dependency name is required")

        return errors

    def _is_valid_semver(self, version: str) -> bool:
        """Check if version follows semver format."""
        parts = version.split(".")
        if len(parts) < 2 or len(parts) > 3:
            return False
        try:
            for part in parts:
                # Handle prerelease tags like 1.0.0-beta
                base = part.split("-")[0]
                int(base)
            return True
        except ValueError:
            return False

    def has_permission(self, permission: str) -> bool:
        """Check if plugin has a specific permission."""
        return permission in self.permissions

    def to_dict(self) -> Dict[str, Any]:
        """Convert manifest to dictionary."""
        return {
            "name": self.name,
            "version": self.version,
            "entry_point": self.entry_point,
            "description": self.description,
            "author": self.author,
            "license": self.license,
            "homepage": self.homepage,
            "repository": self.repository,
            "dependencies": [
                {"name": d.name, "version": d.version, "optional": d.optional}
                for d in self.dependencies
            ],
            "python_requires": self.python_requires,
            "permissions": self.permissions,
            "config_schema": self.config_schema,
            "default_config": self.default_config,
            "auto_enable": self.auto_enable,
            "priority": self.priority,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any], path: Optional[Path] = None) -> "PluginManifest":
        """
        Create manifest from dictionary.

        Args:
            data: Manifest data dictionary
            path: Optional path to plugin directory

        Returns:
            PluginManifest instance
        """
        dependencies = []
        for dep in data.get("dependencies", []):
            if isinstance(dep, str):
                dependencies.append(PluginDependency(name=dep))
            elif isinstance(dep, dict):
                dependencies.append(PluginDependency(
                    name=dep.get("name", ""),
                    version=dep.get("version"),
                    optional=dep.get("optional", False),
                ))

        return cls(
            name=data.get("name", ""),
            version=data.get("version", "0.0.0"),
            entry_point=data.get("entry_point", "main.py"),
            description=data.get("description", ""),
            author=data.get("author", ""),
            license=data.get("license", ""),
            homepage=data.get("homepage", ""),
            repository=data.get("repository", ""),
            dependencies=dependencies,
            python_requires=data.get("python_requires", ">=3.10"),
            permissions=data.get("permissions", []),
            config_schema=data.get("config_schema"),
            default_config=data.get("default_config", {}),
            auto_enable=data.get("auto_enable", True),
            priority=data.get("priority", 100),
            path=path,
        )

    @classmethod
    def from_file(cls, manifest_path: Path) -> "PluginManifest":
        """
        Load manifest from JSON file.

        Args:
            manifest_path: Path to manifest.json

        Returns:
            PluginManifest instance

        Raises:
            FileNotFoundError: If manifest doesn't exist
            json.JSONDecodeError: If manifest is invalid JSON
        """
        with open(manifest_path) as f:
            data = json.load(f)
        return cls.from_dict(data, path=manifest_path.parent)


class ManifestValidationError(Exception):
    """Raised when manifest validation fails."""

    def __init__(self, errors: List[str]):
        self.errors = errors
        super().__init__(f"Manifest validation failed: {'; '.join(errors)}")
