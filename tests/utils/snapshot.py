"""
JARVIS Snapshot Testing Utilities

Provides snapshot testing for API responses, configurations,
and other data structures that should remain consistent.
"""

import json
import hashlib
from pathlib import Path
from typing import Any, Dict, Optional, Union
from dataclasses import dataclass
from datetime import datetime
import difflib


@dataclass
class SnapshotResult:
    """Result of a snapshot comparison."""
    matched: bool
    snapshot_path: Path
    diff: Optional[str] = None
    message: str = ""


class SnapshotManager:
    """
    Manages snapshot testing for consistent data validation.

    Usage:
        snapshots = SnapshotManager()

        def test_api_response(snapshots):
            response = api.get("/users")
            snapshots.assert_match(response.json(), "users_list")
    """

    def __init__(
        self,
        snapshot_dir: Optional[Path] = None,
        update_snapshots: bool = False
    ):
        self.snapshot_dir = snapshot_dir or Path(__file__).parent.parent / "snapshots"
        self.snapshot_dir.mkdir(parents=True, exist_ok=True)
        self.update_snapshots = update_snapshots
        self._accessed_snapshots: set = set()

    def _get_snapshot_path(self, name: str, extension: str = "json") -> Path:
        """Get the path for a named snapshot."""
        safe_name = name.replace("/", "_").replace("\\", "_")
        return self.snapshot_dir / f"{safe_name}.{extension}"

    def _normalize_data(self, data: Any) -> Any:
        """Normalize data for consistent comparison."""
        if isinstance(data, dict):
            # Sort keys and normalize values
            return {k: self._normalize_data(v) for k, v in sorted(data.items())}
        elif isinstance(data, list):
            return [self._normalize_data(item) for item in data]
        elif isinstance(data, (datetime,)):
            return data.isoformat()
        elif isinstance(data, bytes):
            return data.decode("utf-8", errors="replace")
        return data

    def _serialize(self, data: Any) -> str:
        """Serialize data to string for storage."""
        normalized = self._normalize_data(data)
        return json.dumps(normalized, indent=2, sort_keys=True, default=str)

    def _deserialize(self, content: str) -> Any:
        """Deserialize stored snapshot."""
        return json.loads(content)

    def _create_diff(self, expected: str, actual: str) -> str:
        """Create a diff between expected and actual."""
        expected_lines = expected.splitlines(keepends=True)
        actual_lines = actual.splitlines(keepends=True)

        diff = difflib.unified_diff(
            expected_lines,
            actual_lines,
            fromfile="snapshot",
            tofile="actual",
            lineterm=""
        )
        return "".join(diff)

    def save_snapshot(self, name: str, data: Any) -> Path:
        """Save a new snapshot."""
        path = self._get_snapshot_path(name)
        content = self._serialize(data)
        path.write_text(content, encoding="utf-8")
        return path

    def load_snapshot(self, name: str) -> Optional[Any]:
        """Load an existing snapshot."""
        path = self._get_snapshot_path(name)
        if not path.exists():
            return None
        content = path.read_text(encoding="utf-8")
        return self._deserialize(content)

    def compare(self, name: str, actual: Any) -> SnapshotResult:
        """Compare actual data against stored snapshot."""
        path = self._get_snapshot_path(name)
        self._accessed_snapshots.add(name)

        actual_serialized = self._serialize(actual)

        if not path.exists():
            if self.update_snapshots:
                self.save_snapshot(name, actual)
                return SnapshotResult(
                    matched=True,
                    snapshot_path=path,
                    message=f"Created new snapshot: {name}"
                )
            return SnapshotResult(
                matched=False,
                snapshot_path=path,
                message=f"Snapshot not found: {name}. Run with --update-snapshots to create."
            )

        expected_content = path.read_text(encoding="utf-8")
        expected = self._deserialize(expected_content)
        expected_serialized = self._serialize(expected)

        if actual_serialized == expected_serialized:
            return SnapshotResult(
                matched=True,
                snapshot_path=path,
                message="Snapshot matched"
            )

        if self.update_snapshots:
            self.save_snapshot(name, actual)
            return SnapshotResult(
                matched=True,
                snapshot_path=path,
                message=f"Updated snapshot: {name}"
            )

        diff = self._create_diff(expected_serialized, actual_serialized)
        return SnapshotResult(
            matched=False,
            snapshot_path=path,
            diff=diff,
            message=f"Snapshot mismatch for: {name}"
        )

    def assert_match(self, actual: Any, name: str) -> None:
        """Assert that actual data matches the snapshot."""
        result = self.compare(name, actual)
        if not result.matched:
            error_msg = f"\n{result.message}\n"
            if result.diff:
                error_msg += f"\nDiff:\n{result.diff}"
            raise AssertionError(error_msg)

    def get_orphaned_snapshots(self) -> list:
        """Find snapshots that were not accessed during tests."""
        all_snapshots = set(
            p.stem for p in self.snapshot_dir.glob("*.json")
        )
        return list(all_snapshots - self._accessed_snapshots)


class APISnapshotManager(SnapshotManager):
    """
    Snapshot manager specialized for API responses.

    Automatically filters out dynamic fields like timestamps and IDs.
    """

    DEFAULT_IGNORE_FIELDS = [
        "created_at",
        "updated_at",
        "timestamp",
        "request_id",
        "trace_id",
        "session_id",
    ]

    def __init__(
        self,
        snapshot_dir: Optional[Path] = None,
        update_snapshots: bool = False,
        ignore_fields: Optional[list] = None
    ):
        super().__init__(snapshot_dir, update_snapshots)
        self.ignore_fields = ignore_fields or self.DEFAULT_IGNORE_FIELDS

    def _filter_dynamic_fields(self, data: Any, path: str = "") -> Any:
        """Remove dynamic fields that change between runs."""
        if isinstance(data, dict):
            return {
                k: self._filter_dynamic_fields(v, f"{path}.{k}")
                for k, v in data.items()
                if k not in self.ignore_fields
            }
        elif isinstance(data, list):
            return [
                self._filter_dynamic_fields(item, f"{path}[{i}]")
                for i, item in enumerate(data)
            ]
        return data

    def _normalize_data(self, data: Any) -> Any:
        """Filter and normalize data."""
        filtered = self._filter_dynamic_fields(data)
        return super()._normalize_data(filtered)


class ConfigSnapshotManager(SnapshotManager):
    """
    Snapshot manager for configuration files.

    Useful for detecting unintended config changes.
    """

    def __init__(
        self,
        snapshot_dir: Optional[Path] = None,
        update_snapshots: bool = False
    ):
        super().__init__(snapshot_dir, update_snapshots)

    def snapshot_config_file(self, config_path: Path, name: str) -> SnapshotResult:
        """Snapshot a configuration file."""
        if not config_path.exists():
            return SnapshotResult(
                matched=False,
                snapshot_path=self._get_snapshot_path(name),
                message=f"Config file not found: {config_path}"
            )

        content = config_path.read_text(encoding="utf-8")

        # Parse based on extension
        if config_path.suffix in (".json",):
            data = json.loads(content)
        elif config_path.suffix in (".yaml", ".yml"):
            try:
                import yaml
                data = yaml.safe_load(content)
            except ImportError:
                data = {"raw_content": content}
        else:
            # Store as raw content with hash
            data = {
                "content_hash": hashlib.sha256(content.encode()).hexdigest(),
                "line_count": len(content.splitlines()),
            }

        return self.compare(name, data)


# Pytest fixtures
import pytest


@pytest.fixture
def snapshot(request):
    """
    Pytest fixture for snapshot testing.

    Usage:
        def test_api_response(snapshot):
            response = api.get("/users")
            snapshot.assert_match(response.json(), "users_response")
    """
    update = request.config.getoption("--update-snapshots", default=False)

    # Get test-specific snapshot directory
    test_file = Path(request.fspath)
    snapshot_dir = test_file.parent / "snapshots" / test_file.stem

    manager = SnapshotManager(
        snapshot_dir=snapshot_dir,
        update_snapshots=update
    )

    yield manager

    # Report orphaned snapshots
    orphaned = manager.get_orphaned_snapshots()
    if orphaned:
        pytest.warning(f"Orphaned snapshots: {orphaned}")


@pytest.fixture
def api_snapshot(request):
    """
    Pytest fixture for API snapshot testing.

    Automatically filters dynamic fields.

    Usage:
        def test_users_endpoint(api_snapshot):
            response = client.get("/api/v1/users")
            api_snapshot.assert_match(response.json(), "users_list")
    """
    update = request.config.getoption("--update-snapshots", default=False)

    test_file = Path(request.fspath)
    snapshot_dir = test_file.parent / "snapshots" / test_file.stem

    manager = APISnapshotManager(
        snapshot_dir=snapshot_dir,
        update_snapshots=update
    )

    yield manager


def pytest_addoption(parser):
    """Add snapshot-related pytest options."""
    parser.addoption(
        "--update-snapshots",
        action="store_true",
        default=False,
        help="Update snapshot files with new data"
    )


# Convenience functions for inline use
def assert_snapshot(actual: Any, name: str, **kwargs) -> None:
    """
    Quick snapshot assertion without fixture.

    Usage:
        from tests.utils.snapshot import assert_snapshot

        def test_something():
            result = compute_something()
            assert_snapshot(result, "compute_result")
    """
    manager = SnapshotManager(**kwargs)
    manager.assert_match(actual, name)


def create_snapshot(name: str, data: Any, **kwargs) -> Path:
    """
    Create a snapshot file directly.

    Usage:
        from tests.utils.snapshot import create_snapshot

        # In setup or fixture
        create_snapshot("initial_state", {"users": []})
    """
    manager = SnapshotManager(**kwargs)
    return manager.save_snapshot(name, data)
