"""
Persistence Layer

Provides persistent storage capabilities for LifeOS:
- State persistence (save/load system state)
- Memory persistence (durable memory storage)
- Configuration persistence
- Event history persistence
"""

from lifeos.persistence.store import (
    PersistenceStore,
    JSONStore,
    SQLiteStore,
    get_default_store,
)
from lifeos.persistence.manager import (
    PersistenceManager,
    get_persistence_manager,
)

__all__ = [
    "PersistenceStore",
    "JSONStore",
    "SQLiteStore",
    "get_default_store",
    "PersistenceManager",
    "get_persistence_manager",
]
