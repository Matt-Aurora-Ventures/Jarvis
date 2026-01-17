"""
Safe State Management - Thread/Process-safe file operations with locking.

This module provides atomic file operations to prevent race conditions when
multiple processes (supervisor, bots, monitors) access the same state files.

Features:
- File locking (works on Windows and Unix)
- Atomic writes (write to temp, then rename)
- Automatic retries with backoff
- JSON serialization with validation

Usage:
    from core.safe_state import SafeState

    state = SafeState(Path("data/positions.json"))

    # Read
    data = state.read()

    # Write atomically
    state.write({"positions": [...]})

    # Read-modify-write with lock held
    with state.locked() as data:
        data["positions"].append(new_position)
        state.write(data)
"""

import json
import logging
import os
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, List, Optional, TypeVar, Union

logger = logging.getLogger(__name__)

# Try to import filelock, fall back to basic implementation
try:
    from filelock import FileLock, Timeout as FileLockTimeout
    FILELOCK_AVAILABLE = True
except ImportError:
    FILELOCK_AVAILABLE = False
    FileLock = None
    FileLockTimeout = None

T = TypeVar('T')


class StateLockError(Exception):
    """Raised when unable to acquire state file lock."""
    pass


class StateReadError(Exception):
    """Raised when unable to read state file."""
    pass


class StateWriteError(Exception):
    """Raised when unable to write state file."""
    pass


class SafeState:
    """
    Thread/process-safe state file management.

    Provides atomic read/write operations with file locking to prevent
    race conditions when multiple processes access the same state.
    """

    def __init__(
        self,
        file_path: Union[str, Path],
        default_value: Any = None,
        lock_timeout: float = 10.0,
        retry_count: int = 3,
        retry_delay: float = 0.1,
    ):
        """
        Initialize safe state manager.

        Args:
            file_path: Path to the state JSON file
            default_value: Value to return if file doesn't exist (default: empty dict)
            lock_timeout: Seconds to wait for lock acquisition
            retry_count: Number of retries on transient failures
            retry_delay: Base delay between retries (uses exponential backoff)
        """
        self.file_path = Path(file_path)
        self.default_value = default_value if default_value is not None else {}
        self.lock_timeout = lock_timeout
        self.retry_count = retry_count
        self.retry_delay = retry_delay

        # Lock file path
        self.lock_path = self.file_path.with_suffix(self.file_path.suffix + '.lock')

        # Create parent directory if needed
        self.file_path.parent.mkdir(parents=True, exist_ok=True)

        # Initialize lock
        self._lock: Optional[Any] = None
        if FILELOCK_AVAILABLE:
            self._lock = FileLock(str(self.lock_path), timeout=lock_timeout)

    def _acquire_lock(self) -> bool:
        """Acquire file lock. Returns True if successful."""
        if not FILELOCK_AVAILABLE:
            # Fallback: use simple file-based locking
            return self._acquire_simple_lock()

        try:
            self._lock.acquire(timeout=self.lock_timeout)
            return True
        except FileLockTimeout:
            logger.warning(f"Timeout acquiring lock for {self.file_path}")
            return False
        except Exception as e:
            logger.error(f"Error acquiring lock: {e}")
            return False

    def _release_lock(self) -> None:
        """Release file lock."""
        if not FILELOCK_AVAILABLE:
            self._release_simple_lock()
            return

        try:
            if self._lock.is_locked:
                self._lock.release()
        except Exception as e:
            logger.warning(f"Error releasing lock: {e}")

    def _acquire_simple_lock(self) -> bool:
        """Simple file-based lock for when filelock isn't available."""
        start_time = time.time()
        while time.time() - start_time < self.lock_timeout:
            try:
                # Try to create lock file exclusively
                fd = os.open(
                    str(self.lock_path),
                    os.O_CREAT | os.O_EXCL | os.O_WRONLY
                )
                os.write(fd, str(os.getpid()).encode())
                os.close(fd)
                return True
            except FileExistsError:
                # Check if lock is stale (older than 60 seconds)
                try:
                    if self.lock_path.exists():
                        age = time.time() - self.lock_path.stat().st_mtime
                        if age > 60:
                            logger.warning(f"Removing stale lock file (age: {age:.1f}s)")
                            self.lock_path.unlink()
                            continue
                except Exception:
                    pass
                time.sleep(0.05)
            except Exception as e:
                logger.warning(f"Lock acquisition error: {e}")
                time.sleep(0.05)
        return False

    def _release_simple_lock(self) -> None:
        """Release simple file-based lock."""
        try:
            if self.lock_path.exists():
                self.lock_path.unlink()
        except Exception as e:
            logger.warning(f"Error removing lock file: {e}")

    @contextmanager
    def locked(self):
        """
        Context manager that holds lock while yielding current state.

        Usage:
            with state.locked() as data:
                data["key"] = "value"
                state.write(data)
        """
        if not self._acquire_lock():
            raise StateLockError(f"Could not acquire lock for {self.file_path}")
        try:
            yield self.read(skip_lock=True)
        finally:
            self._release_lock()

    def read(self, skip_lock: bool = False) -> Any:
        """
        Read state from file with automatic locking.

        Args:
            skip_lock: Skip locking (use when already holding lock)

        Returns:
            Parsed JSON data or default_value if file doesn't exist
        """
        if not skip_lock:
            if not self._acquire_lock():
                raise StateLockError(f"Could not acquire lock for {self.file_path}")

        try:
            return self._read_with_retry()
        finally:
            if not skip_lock:
                self._release_lock()

    def _read_with_retry(self) -> Any:
        """Read file with retries on transient failures."""
        last_error = None

        for attempt in range(self.retry_count):
            try:
                if not self.file_path.exists():
                    return self.default_value

                with open(self.file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    if not content.strip():
                        return self.default_value
                    return json.loads(content)

            except json.JSONDecodeError as e:
                # JSON corruption - try to recover from backup
                backup_path = self.file_path.with_suffix('.json.bak')
                if backup_path.exists():
                    logger.warning(f"JSON decode error, trying backup: {e}")
                    try:
                        with open(backup_path, 'r', encoding='utf-8') as f:
                            return json.load(f)
                    except Exception:
                        pass
                last_error = e

            except (IOError, OSError) as e:
                last_error = e
                if attempt < self.retry_count - 1:
                    delay = self.retry_delay * (2 ** attempt)
                    time.sleep(delay)

        if last_error:
            logger.error(f"Failed to read {self.file_path} after {self.retry_count} attempts: {last_error}")
            raise StateReadError(f"Could not read {self.file_path}: {last_error}")

        return self.default_value

    def write(self, data: Any, skip_lock: bool = False) -> bool:
        """
        Write state to file atomically with locking.

        Args:
            data: Data to serialize as JSON
            skip_lock: Skip locking (use when already holding lock)

        Returns:
            True if successful
        """
        if not skip_lock:
            if not self._acquire_lock():
                raise StateLockError(f"Could not acquire lock for {self.file_path}")

        try:
            return self._write_with_retry(data)
        finally:
            if not skip_lock:
                self._release_lock()

    def _write_with_retry(self, data: Any) -> bool:
        """Write file atomically with retries."""
        last_error = None

        for attempt in range(self.retry_count):
            try:
                # Create backup of existing file
                if self.file_path.exists():
                    backup_path = self.file_path.with_suffix('.json.bak')
                    try:
                        import shutil
                        shutil.copy2(self.file_path, backup_path)
                    except Exception:
                        pass

                # Write to temp file first
                temp_path = self.file_path.with_suffix('.json.tmp')
                with open(temp_path, 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=2, default=str)
                    f.flush()
                    os.fsync(f.fileno())

                # Atomic rename (on same filesystem)
                # On Windows, we need to remove target first
                if os.name == 'nt' and self.file_path.exists():
                    self.file_path.unlink()

                temp_path.rename(self.file_path)
                return True

            except (IOError, OSError) as e:
                last_error = e
                if attempt < self.retry_count - 1:
                    delay = self.retry_delay * (2 ** attempt)
                    time.sleep(delay)

        if last_error:
            logger.error(f"Failed to write {self.file_path} after {self.retry_count} attempts: {last_error}")
            raise StateWriteError(f"Could not write {self.file_path}: {last_error}")

        return False

    def update(self, updater: callable) -> Any:
        """
        Atomically update state using a function.

        Args:
            updater: Function that takes current state and returns new state

        Returns:
            The new state after update
        """
        with self.locked() as data:
            new_data = updater(data)
            self.write(new_data, skip_lock=True)
            return new_data

    def append_to_list(self, key: str, item: Any, max_items: Optional[int] = None) -> None:
        """
        Atomically append an item to a list in the state.

        Args:
            key: Key of the list in the state dict
            item: Item to append
            max_items: Optional max items to keep (removes oldest)
        """
        def updater(data: Dict) -> Dict:
            if not isinstance(data, dict):
                data = {}
            if key not in data:
                data[key] = []
            data[key].append(item)
            if max_items and len(data[key]) > max_items:
                data[key] = data[key][-max_items:]
            return data

        self.update(updater)

    def remove_from_list(self, key: str, predicate: callable) -> Optional[Any]:
        """
        Atomically remove items matching predicate from a list.

        Args:
            key: Key of the list in the state dict
            predicate: Function that returns True for items to remove

        Returns:
            List of removed items
        """
        removed = []

        def updater(data: Dict) -> Dict:
            if not isinstance(data, dict) or key not in data:
                return data
            original = data[key]
            data[key] = [item for item in original if not predicate(item)]
            removed.extend([item for item in original if predicate(item)])
            return data

        self.update(updater)
        return removed


# Convenience function for migration
def migrate_json_to_safe_state(
    file_path: Union[str, Path],
    default_value: Any = None
) -> SafeState:
    """
    Create a SafeState wrapper for an existing JSON file.

    This is a drop-in migration helper. Just replace:
        with open(file_path) as f:
            data = json.load(f)

    With:
        state = migrate_json_to_safe_state(file_path)
        data = state.read()
    """
    return SafeState(file_path, default_value=default_value)


# Pre-configured instances for common state files
def get_positions_state() -> SafeState:
    """Get SafeState for positions file."""
    from pathlib import Path
    positions_file = Path(__file__).parent.parent / 'bots' / 'treasury' / '.positions.json'
    return SafeState(positions_file, default_value=[])


def get_trade_history_state() -> SafeState:
    """Get SafeState for trade history file."""
    from pathlib import Path
    history_file = Path(__file__).parent.parent / 'bots' / 'treasury' / '.trade_history.json'
    return SafeState(history_file, default_value=[])


def get_daily_volume_state() -> SafeState:
    """Get SafeState for daily volume file."""
    from pathlib import Path
    volume_file = Path(__file__).parent.parent / 'bots' / 'treasury' / '.daily_volume.json'
    return SafeState(volume_file, default_value={})


def get_audit_log_state() -> SafeState:
    """Get SafeState for audit log file."""
    from pathlib import Path
    audit_file = Path(__file__).parent.parent / 'bots' / 'treasury' / '.audit_log.json'
    return SafeState(audit_file, default_value=[])
