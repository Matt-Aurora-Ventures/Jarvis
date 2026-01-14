"""
JARVIS API Changelog

Provides API changelog tracking and versioning:
- Semantic versioning
- Change categories (added, changed, deprecated, removed, fixed)
- Version comparison
- API endpoint for changelog

Usage:
    from core.api.changelog import changelog, get_changelog_router

    # Add change
    changelog.add_change(
        version="1.2.0",
        category="added",
        description="New trading endpoint /api/v1/trade"
    )

    # Get router
    app.include_router(get_changelog_router())
"""

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from functools import total_ordering
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Query

logger = logging.getLogger("jarvis.api.changelog")


# =============================================================================
# MODELS
# =============================================================================

class ChangeCategory(str, Enum):
    """Categories of changes"""
    ADDED = "added"
    CHANGED = "changed"
    DEPRECATED = "deprecated"
    REMOVED = "removed"
    FIXED = "fixed"
    SECURITY = "security"


@total_ordering
@dataclass
class Version:
    """Semantic version"""
    major: int
    minor: int
    patch: int
    prerelease: str = ""
    build: str = ""

    @classmethod
    def parse(cls, version_str: str) -> "Version":
        """Parse version string"""
        # Remove leading 'v' if present
        version_str = version_str.lstrip("v")

        # Match semantic version pattern
        pattern = r"^(\d+)\.(\d+)\.(\d+)(?:-([a-zA-Z0-9.-]+))?(?:\+([a-zA-Z0-9.-]+))?$"
        match = re.match(pattern, version_str)

        if not match:
            raise ValueError(f"Invalid version format: {version_str}")

        return cls(
            major=int(match.group(1)),
            minor=int(match.group(2)),
            patch=int(match.group(3)),
            prerelease=match.group(4) or "",
            build=match.group(5) or "",
        )

    def __str__(self) -> str:
        result = f"{self.major}.{self.minor}.{self.patch}"
        if self.prerelease:
            result += f"-{self.prerelease}"
        if self.build:
            result += f"+{self.build}"
        return result

    def __eq__(self, other) -> bool:
        if not isinstance(other, Version):
            return NotImplemented
        return (self.major, self.minor, self.patch) == (other.major, other.minor, other.patch)

    def __lt__(self, other) -> bool:
        if not isinstance(other, Version):
            return NotImplemented
        return (self.major, self.minor, self.patch) < (other.major, other.minor, other.patch)


@dataclass
class Change:
    """A single change entry"""
    version: str
    category: ChangeCategory
    description: str
    date: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    breaking: bool = False
    migration_notes: str = ""
    related_issue: str = ""
    author: str = ""


@dataclass
class VersionRelease:
    """A version release with all its changes"""
    version: str
    date: datetime
    changes: List[Change]
    summary: str = ""
    breaking_changes: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "version": self.version,
            "date": self.date.isoformat(),
            "summary": self.summary,
            "breaking_changes": self.breaking_changes,
            "changes": {
                cat.value: [
                    {
                        "description": c.description,
                        "breaking": c.breaking,
                        "migration_notes": c.migration_notes,
                    }
                    for c in self.changes if c.category == cat
                ]
                for cat in ChangeCategory
                if any(c.category == cat for c in self.changes)
            }
        }


# =============================================================================
# CHANGELOG MANAGER
# =============================================================================

class Changelog:
    """
    API changelog manager.

    Tracks all API changes with version information.
    """

    # Current API version
    CURRENT_VERSION = "1.0.0"

    def __init__(self):
        self._changes: List[Change] = []
        self._releases: Dict[str, VersionRelease] = {}

        # Initialize with default changelog
        self._init_default_changelog()

    def _init_default_changelog(self):
        """Initialize with default changelog entries"""
        self.add_release(
            version="1.0.0",
            date=datetime(2026, 1, 1, tzinfo=timezone.utc),
            summary="Initial release",
            changes=[
                Change(
                    version="1.0.0",
                    category=ChangeCategory.ADDED,
                    description="Initial API with core endpoints",
                    date=datetime(2026, 1, 1, tzinfo=timezone.utc),
                ),
                Change(
                    version="1.0.0",
                    category=ChangeCategory.ADDED,
                    description="Health check endpoints",
                    date=datetime(2026, 1, 1, tzinfo=timezone.utc),
                ),
                Change(
                    version="1.0.0",
                    category=ChangeCategory.ADDED,
                    description="WebSocket connections for real-time data",
                    date=datetime(2026, 1, 1, tzinfo=timezone.utc),
                ),
            ]
        )

        self.add_release(
            version="1.1.0",
            date=datetime(2026, 1, 10, tzinfo=timezone.utc),
            summary="Trading and monitoring improvements",
            changes=[
                Change(
                    version="1.1.0",
                    category=ChangeCategory.ADDED,
                    description="Trading execution endpoints",
                    date=datetime(2026, 1, 10, tzinfo=timezone.utc),
                ),
                Change(
                    version="1.1.0",
                    category=ChangeCategory.ADDED,
                    description="Bot health monitoring endpoints",
                    date=datetime(2026, 1, 10, tzinfo=timezone.utc),
                ),
                Change(
                    version="1.1.0",
                    category=ChangeCategory.ADDED,
                    description="LLM cost tracking endpoints",
                    date=datetime(2026, 1, 10, tzinfo=timezone.utc),
                ),
                Change(
                    version="1.1.0",
                    category=ChangeCategory.CHANGED,
                    description="Improved error response format",
                    date=datetime(2026, 1, 10, tzinfo=timezone.utc),
                ),
            ]
        )

        # Update current version
        self.CURRENT_VERSION = "1.1.0"

    # =========================================================================
    # CHANGE MANAGEMENT
    # =========================================================================

    def add_change(
        self,
        version: str,
        category: ChangeCategory,
        description: str,
        breaking: bool = False,
        migration_notes: str = "",
        related_issue: str = "",
        author: str = "",
    ) -> Change:
        """Add a new change"""
        if isinstance(category, str):
            category = ChangeCategory(category)

        change = Change(
            version=version,
            category=category,
            description=description,
            breaking=breaking,
            migration_notes=migration_notes,
            related_issue=related_issue,
            author=author,
        )

        self._changes.append(change)

        # Update release if exists
        if version in self._releases:
            self._releases[version].changes.append(change)
            if breaking:
                self._releases[version].breaking_changes = True

        return change

    def add_release(
        self,
        version: str,
        date: datetime = None,
        summary: str = "",
        changes: List[Change] = None,
    ) -> VersionRelease:
        """Add a new version release"""
        release = VersionRelease(
            version=version,
            date=date or datetime.now(timezone.utc),
            changes=changes or [],
            summary=summary,
            breaking_changes=any(c.breaking for c in (changes or [])),
        )

        self._releases[version] = release
        self._changes.extend(changes or [])

        return release

    # =========================================================================
    # QUERIES
    # =========================================================================

    def get_current_version(self) -> str:
        """Get current API version"""
        return self.CURRENT_VERSION

    def get_releases(self, limit: int = None) -> List[VersionRelease]:
        """Get all releases, newest first"""
        releases = sorted(
            self._releases.values(),
            key=lambda r: Version.parse(r.version),
            reverse=True,
        )

        if limit:
            releases = releases[:limit]

        return releases

    def get_release(self, version: str) -> Optional[VersionRelease]:
        """Get a specific release"""
        return self._releases.get(version)

    def get_changes_since(self, version: str) -> List[Change]:
        """Get all changes since a version"""
        try:
            since_version = Version.parse(version)
        except ValueError:
            return []

        return [
            c for c in self._changes
            if Version.parse(c.version) > since_version
        ]

    def get_breaking_changes(self, since: str = None) -> List[Change]:
        """Get breaking changes, optionally since a version"""
        changes = self._changes if not since else self.get_changes_since(since)
        return [c for c in changes if c.breaking]

    def has_breaking_changes(self, since: str) -> bool:
        """Check if there are breaking changes since a version"""
        return len(self.get_breaking_changes(since)) > 0

    # =========================================================================
    # FORMATTING
    # =========================================================================

    def to_markdown(self) -> str:
        """Generate markdown changelog"""
        lines = ["# API Changelog\n"]

        for release in self.get_releases():
            lines.append(f"## [{release.version}] - {release.date.strftime('%Y-%m-%d')}")

            if release.summary:
                lines.append(f"\n{release.summary}\n")

            if release.breaking_changes:
                lines.append("\n⚠️ **Breaking Changes**\n")

            for category in ChangeCategory:
                category_changes = [c for c in release.changes if c.category == category]
                if category_changes:
                    lines.append(f"\n### {category.value.title()}\n")
                    for change in category_changes:
                        prefix = "⚠️ " if change.breaking else ""
                        lines.append(f"- {prefix}{change.description}")
                        if change.migration_notes:
                            lines.append(f"  - Migration: {change.migration_notes}")

            lines.append("\n")

        return "\n".join(lines)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "current_version": self.CURRENT_VERSION,
            "releases": [r.to_dict() for r in self.get_releases()],
        }


# =============================================================================
# SINGLETON
# =============================================================================

_changelog: Optional[Changelog] = None


def get_changelog() -> Changelog:
    """Get or create the changelog singleton"""
    global _changelog
    if _changelog is None:
        _changelog = Changelog()
    return _changelog


# Convenience alias
changelog = get_changelog()


# =============================================================================
# FASTAPI ROUTER
# =============================================================================

def get_changelog_router() -> APIRouter:
    """Get FastAPI router for changelog endpoints"""
    router = APIRouter(prefix="/changelog", tags=["Changelog"])

    @router.get("")
    async def get_all_changes(
        limit: int = Query(10, ge=1, le=100, description="Number of releases to return"),
    ):
        """
        Get API changelog

        Returns all releases with their changes.
        """
        return get_changelog().to_dict()

    @router.get("/version")
    async def get_current_api_version():
        """
        Get current API version

        Returns the current API version number.
        """
        return {"version": get_changelog().get_current_version()}

    @router.get("/release/{version}")
    async def get_release_details(version: str):
        """
        Get specific release details

        Returns changes for a specific version.
        """
        release = get_changelog().get_release(version)
        if not release:
            return {"error": f"Version {version} not found"}
        return release.to_dict()

    @router.get("/since/{version}")
    async def get_changes_since_version(version: str):
        """
        Get changes since version

        Returns all changes made after the specified version.
        """
        changes = get_changelog().get_changes_since(version)
        breaking = get_changelog().has_breaking_changes(version)

        return {
            "since_version": version,
            "current_version": get_changelog().get_current_version(),
            "breaking_changes": breaking,
            "changes": [
                {
                    "version": c.version,
                    "category": c.category.value,
                    "description": c.description,
                    "breaking": c.breaking,
                }
                for c in changes
            ]
        }

    @router.get("/breaking")
    async def get_breaking_changes_list(
        since: str = Query(None, description="Version to check from"),
    ):
        """
        Get breaking changes

        Returns all breaking changes, optionally since a specific version.
        """
        changes = get_changelog().get_breaking_changes(since)

        return {
            "since_version": since,
            "breaking_changes": [
                {
                    "version": c.version,
                    "description": c.description,
                    "migration_notes": c.migration_notes,
                }
                for c in changes
            ]
        }

    @router.get("/markdown")
    async def get_changelog_markdown():
        """
        Get changelog as markdown

        Returns the full changelog in markdown format.
        """
        return {"markdown": get_changelog().to_markdown()}

    return router
