"""
State Management System for ClawdBots

Provides persistent state management with:
- Per-bot state storage (JSON files)
- Atomic state updates with file locking
- State snapshots for rollback capability
- State change history tracking
- Concurrent access safety via file locks

State storage:
- Current state: {state_dir}/{bot_name}.json
- Snapshots: {state_dir}/snapshots/{bot_name}_{timestamp}.json

Default paths on VPS:
- State: /root/clawdbots/state/{bot_name}.json
- Snapshots: /root/clawdbots/state/snapshots/{bot_name}_{timestamp}.json

Usage:
    from bots.shared.state_manager import StateManager

    # Initialize for a bot
    manager = StateManager(bot_name="jarvis")

    # Basic state operations
    manager.set_state("jarvis", "counter", 42)
    value = manager.get_state("jarvis", "counter")
    full = manager.get_full_state("jarvis")

    # Snapshots
    snap_id = manager.save_snapshot("jarvis")
    manager.restore_snapshot("jarvis", snap_id)

    # History
    history = manager.get_state_history("jarvis", "counter")
"""

import copy
import json
import logging
import os
import re
import tempfile
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    import filelock
except ImportError:
    filelock = None

logger = logging.getLogger("clawdbots.state_manager")


# Default state directory (VPS location)
DEFAULT_STATE_DIR = "/root/clawdbots/state"

# Maximum history entries per key (prevents unbounded growth)
DEFAULT_MAX_HISTORY = 50

# Maximum snapshots to keep per bot
DEFAULT_MAX_SNAPSHOTS = 10


class StateError(Exception):
    """Raised when a state operation fails."""
    pass


@dataclass
class StateChange:
    """
    Record of a single state change.

    Tracks the key, old value, new value, timestamp, and optional metadata.
    """
    key: str
    old_value: Any
    new_value: Any
    timestamp: str
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "key": self.key,
            "old_value": self.old_value,
            "new_value": self.new_value,
            "timestamp": self.timestamp,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "StateChange":
        """Deserialize from dictionary."""
        return cls(
            key=data["key"],
            old_value=data.get("old_value"),
            new_value=data.get("new_value"),
            timestamp=data.get("timestamp", ""),
            metadata=data.get("metadata", {}),
        )


class StateManager:
    """
    Manages persistent state for ClawdBots.

    Features:
    - Thread-safe state operations via file locking
    - Automatic state persistence to JSON files
    - Snapshot creation and restoration
    - State change history tracking
    - Cross-bot state access

    Each bot has its own state file, but any StateManager can
    read/write state for any bot (useful for coordination).
    """

    def __init__(
        self,
        bot_name: str,
        state_dir: Optional[str] = None,
        max_history: int = DEFAULT_MAX_HISTORY,
        max_snapshots: int = DEFAULT_MAX_SNAPSHOTS,
    ):
        """
        Initialize StateManager for a bot.

        Args:
            bot_name: Name of the bot (jarvis, matt, friday, etc.)
            state_dir: Directory for state files (default: /root/clawdbots/state)
            max_history: Maximum history entries per key
            max_snapshots: Maximum snapshots to keep per bot
        """
        # Validate bot name
        if not bot_name or not isinstance(bot_name, str):
            raise StateError("Bot name must be a non-empty string")

        # Security: prevent path traversal
        if ".." in bot_name or "/" in bot_name or "\\" in bot_name:
            raise StateError(f"Invalid bot name: {bot_name} (path traversal detected)")

        # Validate bot name characters
        if not re.match(r"^[a-zA-Z0-9_-]+$", bot_name):
            raise StateError(
                f"Invalid bot name: {bot_name} "
                "(only alphanumeric, underscore, hyphen allowed)"
            )

        self._bot_name = bot_name
        self._state_dir = state_dir or DEFAULT_STATE_DIR
        self._max_history = max_history
        self._max_snapshots = max_snapshots

        # Create directories
        self._ensure_directories()

        # Setup file locks (per state file)
        self._locks: Dict[str, Any] = {}

        # Initialize state file if needed
        state_file = self._get_state_file(bot_name)
        if not os.path.exists(state_file):
            self._save_state_data(bot_name, self._default_state_data())

        logger.info(f"StateManager initialized for {bot_name} at {self._state_dir}")

    def _ensure_directories(self) -> None:
        """Create state and snapshots directories if needed."""
        Path(self._state_dir).mkdir(parents=True, exist_ok=True)
        Path(self._state_dir, "snapshots").mkdir(parents=True, exist_ok=True)

    def _default_state_data(self) -> Dict[str, Any]:
        """Return default empty state data structure."""
        return {
            "version": "1.0",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "state": {},
            "history": [],
            "metadata": {},
        }

    def _get_state_file(self, bot_name: str) -> str:
        """Get path to state file for a bot."""
        return os.path.join(self._state_dir, f"{bot_name}.json")

    def _get_lock(self, bot_name: str) -> Any:
        """Get or create file lock for a bot's state file."""
        if bot_name not in self._locks:
            if filelock:
                lock_path = self._get_state_file(bot_name) + ".lock"
                self._locks[bot_name] = filelock.FileLock(lock_path, timeout=10)
            else:
                # No file lock available - create a placeholder
                self._locks[bot_name] = None
                logger.warning(
                    f"filelock not available for {bot_name}, "
                    "concurrent access may cause issues"
                )
        return self._locks[bot_name]

    def _with_lock(self, bot_name: str, func):
        """Execute function with file lock for a bot."""
        lock = self._get_lock(bot_name)
        if lock:
            with lock:
                return func()
        else:
            return func()

    def _load_state_data(self, bot_name: str) -> Dict[str, Any]:
        """Load state data from disk."""
        state_file = self._get_state_file(bot_name)
        try:
            if os.path.exists(state_file):
                with open(state_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, dict) and "state" in data:
                        return data
            return self._default_state_data()
        except (json.JSONDecodeError, IOError) as e:
            logger.warning(
                f"Failed to load state for {bot_name}: {e}, using default"
            )
            return self._default_state_data()

    def _save_state_data(self, bot_name: str, data: Dict[str, Any]) -> None:
        """Atomically save state data to disk."""
        data["updated_at"] = datetime.now(timezone.utc).isoformat()
        state_file = self._get_state_file(bot_name)

        # Ensure directory exists (in case of cross-bot writes)
        self._ensure_directories()

        # Write to temp file then rename (atomic on most filesystems)
        state_path = Path(state_file)
        try:
            temp_fd, temp_path = tempfile.mkstemp(
                dir=state_path.parent,
                suffix=".json.tmp",
            )
            try:
                with os.fdopen(temp_fd, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
                os.replace(temp_path, state_file)
            except Exception:
                if os.path.exists(temp_path):
                    os.unlink(temp_path)
                raise
        except Exception as e:
            logger.error(f"Failed to save state for {bot_name}: {e}")
            raise StateError(f"Failed to save state: {e}")

    def _get_snapshot_file(self, snapshot_id: str) -> str:
        """Get path to snapshot file."""
        return os.path.join(self._state_dir, "snapshots", f"{snapshot_id}.json")

    def _record_change(
        self,
        data: Dict[str, Any],
        key: str,
        old_value: Any,
        new_value: Any,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Record a state change in history."""
        change = StateChange(
            key=key,
            old_value=old_value,
            new_value=new_value,
            timestamp=datetime.now(timezone.utc).isoformat(),
            metadata=metadata or {},
        )

        data["history"].append(change.to_dict())

        # Trim history per key to prevent unbounded growth
        # Group by key and keep only max_history entries per key
        self._trim_history(data)

    def _trim_history(self, data: Dict[str, Any]) -> None:
        """Trim history to keep only max_history entries per key."""
        history = data.get("history", [])
        if not history:
            return

        # Group entries by key
        by_key: Dict[str, List[Dict[str, Any]]] = {}
        for entry in history:
            key = entry.get("key", "")
            if key not in by_key:
                by_key[key] = []
            by_key[key].append(entry)

        # Trim each key's history
        trimmed = []
        for key, entries in by_key.items():
            # Keep only the most recent max_history entries per key
            if len(entries) > self._max_history:
                entries = entries[-self._max_history:]
            trimmed.extend(entries)

        # Sort by timestamp to maintain chronological order
        trimmed.sort(key=lambda x: x.get("timestamp", ""))
        data["history"] = trimmed

    def _cleanup_snapshots(self, bot_name: str) -> None:
        """Remove old snapshots to keep only max_snapshots."""
        snapshots_dir = os.path.join(self._state_dir, "snapshots")
        if not os.path.exists(snapshots_dir):
            return

        # Find all snapshots for this bot
        pattern = f"{bot_name}_"
        snapshot_files = [
            f for f in os.listdir(snapshots_dir)
            if f.startswith(pattern) and f.endswith(".json")
        ]

        if len(snapshot_files) <= self._max_snapshots:
            return

        # Sort by file modification time to get proper ordering
        # This ensures we keep the most recently created snapshots
        snapshot_files_with_mtime = []
        for filename in snapshot_files:
            filepath = os.path.join(snapshots_dir, filename)
            try:
                mtime = os.path.getmtime(filepath)
                snapshot_files_with_mtime.append((filename, mtime))
            except OSError:
                # If we can't get mtime, use 0 (oldest)
                snapshot_files_with_mtime.append((filename, 0))

        # Sort by modification time
        snapshot_files_with_mtime.sort(key=lambda x: x[1])

        # Delete oldest (those with smallest mtime)
        to_delete = snapshot_files_with_mtime[:-self._max_snapshots]
        for filename, _ in to_delete:
            try:
                os.unlink(os.path.join(snapshots_dir, filename))
                logger.debug(f"Deleted old snapshot: {filename}")
            except OSError as e:
                logger.warning(f"Failed to delete snapshot {filename}: {e}")

    # -------------------------
    # Public API Methods
    # -------------------------

    def get_state(
        self,
        bot_name: str,
        key: str,
        default: Any = None,
    ) -> Any:
        """
        Get a state value for a bot.

        Args:
            bot_name: Name of the bot
            key: State key to retrieve
            default: Default value if key doesn't exist

        Returns:
            The state value or default
        """
        def _do_get():
            data = self._load_state_data(bot_name)
            return data["state"].get(key, default)

        return self._with_lock(bot_name, _do_get)

    def set_state(
        self,
        bot_name: str,
        key: str,
        value: Any,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Set a state value for a bot.

        Args:
            bot_name: Name of the bot
            key: State key to set
            value: Value to store
            metadata: Optional metadata for the change

        Returns:
            True on success
        """
        def _do_set():
            data = self._load_state_data(bot_name)
            old_value = data["state"].get(key)

            # Record change
            self._record_change(data, key, old_value, value, metadata)

            # Update state
            data["state"][key] = value
            self._save_state_data(bot_name, data)
            return True

        return self._with_lock(bot_name, _do_set)

    def delete_state(
        self,
        bot_name: str,
        key: str,
    ) -> bool:
        """
        Delete a state key for a bot.

        Args:
            bot_name: Name of the bot
            key: State key to delete

        Returns:
            True if key was deleted, False if key didn't exist
        """
        def _do_delete():
            data = self._load_state_data(bot_name)
            if key not in data["state"]:
                return False

            old_value = data["state"].pop(key)
            self._record_change(data, key, old_value, None, {"action": "delete"})
            self._save_state_data(bot_name, data)
            return True

        return self._with_lock(bot_name, _do_delete)

    def get_full_state(self, bot_name: str) -> Dict[str, Any]:
        """
        Get complete state dictionary for a bot.

        Args:
            bot_name: Name of the bot

        Returns:
            Copy of the full state dictionary
        """
        def _do_get():
            data = self._load_state_data(bot_name)
            return copy.deepcopy(data["state"])

        return self._with_lock(bot_name, _do_get)

    def save_snapshot(self, bot_name: str, description: str = "") -> str:
        """
        Save a snapshot of the current state.

        Args:
            bot_name: Name of the bot
            description: Optional description of the snapshot

        Returns:
            Snapshot ID
        """
        def _do_snapshot():
            data = self._load_state_data(bot_name)

            # Generate snapshot ID with timestamp
            timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            snapshot_id = f"{bot_name}_{timestamp}_{uuid.uuid4().hex[:6]}"

            # Create snapshot data
            snapshot_data = {
                "id": snapshot_id,
                "bot_name": bot_name,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "description": description,
                "state": copy.deepcopy(data["state"]),
                "metadata": copy.deepcopy(data.get("metadata", {})),
            }

            # Save snapshot
            snapshot_file = self._get_snapshot_file(snapshot_id)
            with open(snapshot_file, "w", encoding="utf-8") as f:
                json.dump(snapshot_data, f, indent=2, ensure_ascii=False)

            logger.info(f"Created snapshot {snapshot_id} for {bot_name}")

            # Cleanup old snapshots
            self._cleanup_snapshots(bot_name)

            return snapshot_id

        return self._with_lock(bot_name, _do_snapshot)

    def restore_snapshot(self, bot_name: str, snapshot_id: str) -> bool:
        """
        Restore state from a snapshot.

        Creates a backup snapshot before restoring.

        Args:
            bot_name: Name of the bot
            snapshot_id: ID of the snapshot to restore

        Returns:
            True on success

        Raises:
            StateError: If snapshot not found
        """
        def _do_restore():
            snapshot_file = self._get_snapshot_file(snapshot_id)
            if not os.path.exists(snapshot_file):
                raise StateError(f"Snapshot not found: {snapshot_id}")

            # Load snapshot
            with open(snapshot_file, "r", encoding="utf-8") as f:
                snapshot_data = json.load(f)

            # Create backup of current state before restore
            self.save_snapshot(bot_name, f"Pre-restore backup (restoring {snapshot_id})")

            # Load current state data
            data = self._load_state_data(bot_name)

            # Record the restore in history
            self._record_change(
                data,
                "_snapshot_restore",
                None,
                snapshot_id,
                {"action": "restore", "snapshot_id": snapshot_id},
            )

            # Replace state
            data["state"] = copy.deepcopy(snapshot_data["state"])

            # Save
            self._save_state_data(bot_name, data)

            logger.info(f"Restored snapshot {snapshot_id} for {bot_name}")
            return True

        return self._with_lock(bot_name, _do_restore)

    def list_snapshots(self, bot_name: str) -> List[Dict[str, Any]]:
        """
        List all snapshots for a bot.

        Args:
            bot_name: Name of the bot

        Returns:
            List of snapshot info dictionaries with id, created_at, description
        """
        snapshots_dir = os.path.join(self._state_dir, "snapshots")
        if not os.path.exists(snapshots_dir):
            return []

        pattern = f"{bot_name}_"
        snapshot_files = [
            f for f in os.listdir(snapshots_dir)
            if f.startswith(pattern) and f.endswith(".json")
        ]

        snapshots = []
        for filename in sorted(snapshot_files):
            snapshot_file = os.path.join(snapshots_dir, filename)
            try:
                with open(snapshot_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    snapshots.append({
                        "id": data.get("id", filename[:-5]),
                        "created_at": data.get("created_at"),
                        "description": data.get("description", ""),
                    })
            except (json.JSONDecodeError, IOError) as e:
                logger.warning(f"Failed to read snapshot {filename}: {e}")

        return snapshots

    def get_state_history(
        self,
        bot_name: str,
        key: str,
        limit: Optional[int] = None,
    ) -> List[StateChange]:
        """
        Get change history for a specific key.

        Args:
            bot_name: Name of the bot
            key: State key to get history for
            limit: Maximum number of entries to return (None = all)

        Returns:
            List of StateChange objects in chronological order
        """
        def _do_get():
            data = self._load_state_data(bot_name)

            # Filter history for this key
            key_history = [
                StateChange.from_dict(entry)
                for entry in data.get("history", [])
                if entry.get("key") == key
            ]

            # Apply limit
            if limit is not None:
                key_history = key_history[-limit:]

            return key_history

        return self._with_lock(bot_name, _do_get)


# -------------------------
# Convenience Functions
# -------------------------

def get_state_manager(
    bot_name: str,
    state_dir: Optional[str] = None,
) -> StateManager:
    """
    Get a StateManager instance for a bot.

    Args:
        bot_name: Name of the bot
        state_dir: Optional custom state directory

    Returns:
        StateManager instance
    """
    return StateManager(bot_name, state_dir=state_dir)
