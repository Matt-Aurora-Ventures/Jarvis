"""
Persistence Manager

High-level persistence manager for LifeOS components.

Provides:
- State saving/loading
- Auto-save functionality
- Backup management
"""

import asyncio
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set

from lifeos.persistence.store import PersistenceStore, get_default_store

logger = logging.getLogger(__name__)


class PersistenceManager:
    """
    Manages persistence for LifeOS components.

    Features:
    - Namespace-based organization
    - Auto-save with configurable interval
    - Change tracking
    - Backup support
    """

    def __init__(
        self,
        store: Optional[PersistenceStore] = None,
        auto_save_interval: float = 60.0,
    ):
        """
        Initialize persistence manager.

        Args:
            store: Persistence store to use (default: JSONStore)
            auto_save_interval: Seconds between auto-saves (0 to disable)
        """
        self._store = store or get_default_store()
        self._auto_save_interval = auto_save_interval
        self._dirty_namespaces: Set[str] = set()
        self._callbacks: Dict[str, List[Callable[[str, str, Any], None]]] = {}
        self._auto_save_task: Optional[asyncio.Task] = None
        self._running = False

    async def start(self) -> None:
        """Start the persistence manager."""
        if self._running:
            return

        self._running = True
        if self._auto_save_interval > 0:
            self._auto_save_task = asyncio.create_task(self._auto_save_loop())
            logger.info(f"Persistence auto-save started (interval: {self._auto_save_interval}s)")

    async def stop(self) -> None:
        """Stop the persistence manager."""
        self._running = False
        if self._auto_save_task:
            self._auto_save_task.cancel()
            try:
                await self._auto_save_task
            except asyncio.CancelledError:
                pass
            self._auto_save_task = None

        # Final save
        await self.flush()
        self._store.close()
        logger.info("Persistence manager stopped")

    async def _auto_save_loop(self) -> None:
        """Background auto-save loop."""
        while self._running:
            try:
                await asyncio.sleep(self._auto_save_interval)
                if self._dirty_namespaces:
                    await self.flush()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Auto-save error: {e}")

    async def flush(self) -> int:
        """
        Flush all pending changes to storage.

        Returns:
            Number of namespaces saved
        """
        if not self._dirty_namespaces:
            return 0

        count = len(self._dirty_namespaces)
        self._dirty_namespaces.clear()
        logger.debug(f"Flushed {count} namespaces to storage")
        return count

    # Core Operations

    def get(self, namespace: str, key: str, default: Any = None) -> Any:
        """
        Get a value from persistent storage.

        Args:
            namespace: Namespace for the value
            key: Key to retrieve
            default: Default value if not found

        Returns:
            The stored value or default
        """
        value = self._store.get(namespace, key)
        return value if value is not None else default

    def set(self, namespace: str, key: str, value: Any) -> bool:
        """
        Set a value in persistent storage.

        Args:
            namespace: Namespace for the value
            key: Key to store
            value: Value to store

        Returns:
            True if successful
        """
        success = self._store.set(namespace, key, value)
        if success:
            self._dirty_namespaces.add(namespace)
            self._notify_callbacks(namespace, key, value)
        return success

    def delete(self, namespace: str, key: str) -> bool:
        """
        Delete a value from persistent storage.

        Args:
            namespace: Namespace for the value
            key: Key to delete

        Returns:
            True if deleted
        """
        success = self._store.delete(namespace, key)
        if success:
            self._dirty_namespaces.add(namespace)
            self._notify_callbacks(namespace, key, None)
        return success

    def list_keys(self, namespace: str) -> List[str]:
        """List all keys in a namespace."""
        return self._store.list_keys(namespace)

    def list_namespaces(self) -> List[str]:
        """List all namespaces."""
        return self._store.list_namespaces()

    def clear_namespace(self, namespace: str) -> int:
        """Clear all keys in a namespace."""
        count = self._store.clear_namespace(namespace)
        self._dirty_namespaces.discard(namespace)
        return count

    # State Management

    def save_state(self, state_id: str, state: Dict[str, Any]) -> bool:
        """
        Save component state.

        Args:
            state_id: Identifier for the state (e.g., "jarvis", "memory")
            state: State dictionary to save

        Returns:
            True if successful
        """
        state_with_meta = {
            **state,
            "_saved_at": datetime.now(timezone.utc).isoformat(),
            "_state_id": state_id,
        }
        return self.set("_states", state_id, state_with_meta)

    def load_state(self, state_id: str) -> Optional[Dict[str, Any]]:
        """
        Load component state.

        Args:
            state_id: Identifier for the state

        Returns:
            State dictionary or None
        """
        return self.get("_states", state_id)

    def delete_state(self, state_id: str) -> bool:
        """Delete saved state."""
        return self.delete("_states", state_id)

    def list_states(self) -> List[str]:
        """List all saved states."""
        return self.list_keys("_states")

    # Callbacks

    def on_change(
        self,
        namespace: str,
        callback: Callable[[str, str, Any], None],
    ) -> None:
        """
        Register a callback for changes to a namespace.

        Args:
            namespace: Namespace to watch
            callback: Function called with (namespace, key, value)
        """
        if namespace not in self._callbacks:
            self._callbacks[namespace] = []
        self._callbacks[namespace].append(callback)

    def _notify_callbacks(self, namespace: str, key: str, value: Any) -> None:
        """Notify callbacks of a change."""
        if namespace in self._callbacks:
            for callback in self._callbacks[namespace]:
                try:
                    callback(namespace, key, value)
                except Exception as e:
                    logger.error(f"Callback error: {e}")

        # Also notify wildcard callbacks
        if "*" in self._callbacks:
            for callback in self._callbacks["*"]:
                try:
                    callback(namespace, key, value)
                except Exception as e:
                    logger.error(f"Callback error: {e}")

    # Backup Management

    def create_backup(self, backup_name: Optional[str] = None) -> str:
        """
        Create a backup of all data.

        Args:
            backup_name: Optional name for backup (default: timestamp)

        Returns:
            Backup identifier
        """
        if backup_name is None:
            backup_name = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

        backup_data = {}
        for namespace in self.list_namespaces():
            backup_data[namespace] = {}
            for key in self.list_keys(namespace):
                backup_data[namespace][key] = self.get(namespace, key)

        self.set("_backups", backup_name, {
            "created_at": datetime.now(timezone.utc).isoformat(),
            "data": backup_data,
        })

        logger.info(f"Created backup: {backup_name}")
        return backup_name

    def restore_backup(self, backup_name: str) -> bool:
        """
        Restore from a backup.

        Args:
            backup_name: Backup identifier

        Returns:
            True if successful
        """
        backup = self.get("_backups", backup_name)
        if not backup:
            logger.error(f"Backup not found: {backup_name}")
            return False

        data = backup.get("data", {})
        for namespace, keys in data.items():
            if namespace.startswith("_"):
                continue  # Skip internal namespaces
            for key, value in keys.items():
                self.set(namespace, key, value)

        logger.info(f"Restored backup: {backup_name}")
        return True

    def list_backups(self) -> List[Dict[str, Any]]:
        """List all backups."""
        backups = []
        for name in self.list_keys("_backups"):
            backup = self.get("_backups", name)
            if backup:
                backups.append({
                    "name": name,
                    "created_at": backup.get("created_at"),
                })
        return sorted(backups, key=lambda b: b.get("created_at", ""), reverse=True)

    def delete_backup(self, backup_name: str) -> bool:
        """Delete a backup."""
        return self.delete("_backups", backup_name)

    # Statistics

    def get_stats(self) -> Dict[str, Any]:
        """Get persistence statistics."""
        namespaces = self.list_namespaces()
        total_keys = sum(len(self.list_keys(ns)) for ns in namespaces)
        states = self.list_states()
        backups = self.list_backups()

        return {
            "namespace_count": len(namespaces),
            "total_keys": total_keys,
            "dirty_namespaces": len(self._dirty_namespaces),
            "state_count": len(states),
            "backup_count": len(backups),
            "auto_save_interval": self._auto_save_interval,
            "running": self._running,
        }


# Singleton instance
_persistence_manager: Optional[PersistenceManager] = None


def get_persistence_manager() -> PersistenceManager:
    """Get the global persistence manager."""
    global _persistence_manager
    if _persistence_manager is None:
        _persistence_manager = PersistenceManager()
    return _persistence_manager


def set_persistence_manager(manager: PersistenceManager) -> None:
    """Set the global persistence manager."""
    global _persistence_manager
    _persistence_manager = manager
