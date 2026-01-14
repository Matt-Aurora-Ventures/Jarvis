"""
JARVIS Soft Delete Patterns

Provides soft delete functionality for database models,
allowing records to be marked as deleted without physical removal.
"""

from datetime import datetime
from typing import TypeVar, Generic, Optional, List, Any, Type
from dataclasses import dataclass, field
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class DeletionState(Enum):
    """State of a soft-deleted record."""
    ACTIVE = "active"
    DELETED = "deleted"
    ARCHIVED = "archived"
    PENDING_DELETION = "pending_deletion"


@dataclass
class SoftDeleteMixin:
    """Mixin for soft-deletable models."""
    deleted_at: Optional[datetime] = None
    deleted_by: Optional[str] = None
    deletion_reason: Optional[str] = None
    is_deleted: bool = False

    def soft_delete(
        self,
        deleted_by: Optional[str] = None,
        reason: Optional[str] = None
    ) -> None:
        """Mark record as soft-deleted."""
        self.deleted_at = datetime.utcnow()
        self.deleted_by = deleted_by
        self.deletion_reason = reason
        self.is_deleted = True

    def restore(self) -> None:
        """Restore a soft-deleted record."""
        self.deleted_at = None
        self.deleted_by = None
        self.deletion_reason = None
        self.is_deleted = False

    @property
    def deletion_state(self) -> DeletionState:
        """Get current deletion state."""
        if self.is_deleted:
            return DeletionState.DELETED
        return DeletionState.ACTIVE


@dataclass
class ArchivableMixin(SoftDeleteMixin):
    """Extended mixin with archive support."""
    archived_at: Optional[datetime] = None
    archived_by: Optional[str] = None
    archive_location: Optional[str] = None

    def archive(
        self,
        archived_by: Optional[str] = None,
        location: Optional[str] = None
    ) -> None:
        """Archive the record."""
        self.archived_at = datetime.utcnow()
        self.archived_by = archived_by
        self.archive_location = location
        self.is_deleted = True

    @property
    def deletion_state(self) -> DeletionState:
        """Get current deletion state."""
        if self.archived_at:
            return DeletionState.ARCHIVED
        if self.is_deleted:
            return DeletionState.DELETED
        return DeletionState.ACTIVE


T = TypeVar('T')


class SoftDeleteManager(Generic[T]):
    """Manager for soft-deletable records."""

    def __init__(
        self,
        model_class: Type[T],
        db_session: Any,
        table_name: str
    ):
        self.model_class = model_class
        self.session = db_session
        self.table_name = table_name

    def get_active(self, **filters) -> List[T]:
        """Get only active (non-deleted) records."""
        query = f"SELECT * FROM {self.table_name} WHERE is_deleted = FALSE"

        for key, value in filters.items():
            query += f" AND {key} = ?"

        # Execute query and return results
        return self._execute_query(query, list(filters.values()))

    def get_deleted(self, **filters) -> List[T]:
        """Get only deleted records."""
        query = f"SELECT * FROM {self.table_name} WHERE is_deleted = TRUE"

        for key, value in filters.items():
            query += f" AND {key} = ?"

        return self._execute_query(query, list(filters.values()))

    def get_all(self, include_deleted: bool = False, **filters) -> List[T]:
        """Get all records, optionally including deleted."""
        query = f"SELECT * FROM {self.table_name}"
        conditions = []
        params = []

        if not include_deleted:
            conditions.append("is_deleted = FALSE")

        for key, value in filters.items():
            conditions.append(f"{key} = ?")
            params.append(value)

        if conditions:
            query += " WHERE " + " AND ".join(conditions)

        return self._execute_query(query, params)

    def soft_delete(
        self,
        record_id: str,
        deleted_by: Optional[str] = None,
        reason: Optional[str] = None
    ) -> bool:
        """Soft delete a record by ID."""
        now = datetime.utcnow().isoformat()

        query = f"""
        UPDATE {self.table_name}
        SET is_deleted = TRUE,
            deleted_at = ?,
            deleted_by = ?,
            deletion_reason = ?
        WHERE id = ? AND is_deleted = FALSE
        """

        result = self._execute_update(query, [now, deleted_by, reason, record_id])

        if result:
            logger.info(f"Soft deleted {self.table_name} record: {record_id}")

        return result

    def restore(self, record_id: str) -> bool:
        """Restore a soft-deleted record."""
        query = f"""
        UPDATE {self.table_name}
        SET is_deleted = FALSE,
            deleted_at = NULL,
            deleted_by = NULL,
            deletion_reason = NULL
        WHERE id = ? AND is_deleted = TRUE
        """

        result = self._execute_update(query, [record_id])

        if result:
            logger.info(f"Restored {self.table_name} record: {record_id}")

        return result

    def hard_delete(self, record_id: str) -> bool:
        """Permanently delete a record (use with caution)."""
        query = f"DELETE FROM {self.table_name} WHERE id = ?"
        result = self._execute_update(query, [record_id])

        if result:
            logger.warning(f"Hard deleted {self.table_name} record: {record_id}")

        return result

    def purge_deleted(self, older_than_days: int = 30) -> int:
        """Permanently remove records deleted more than N days ago."""
        cutoff = datetime.utcnow()
        # Calculate cutoff date
        from datetime import timedelta
        cutoff = (cutoff - timedelta(days=older_than_days)).isoformat()

        query = f"""
        DELETE FROM {self.table_name}
        WHERE is_deleted = TRUE AND deleted_at < ?
        """

        count = self._execute_delete_count(query, [cutoff])
        logger.info(f"Purged {count} old deleted records from {self.table_name}")

        return count

    def _execute_query(self, query: str, params: List[Any]) -> List[T]:
        """Execute a SELECT query."""
        try:
            result = self.session.execute(query, params)
            return result.fetchall()
        except Exception as e:
            logger.error(f"Query error: {e}")
            return []

    def _execute_update(self, query: str, params: List[Any]) -> bool:
        """Execute an UPDATE/DELETE query."""
        try:
            result = self.session.execute(query, params)
            self.session.commit()
            return result.rowcount > 0
        except Exception as e:
            logger.error(f"Update error: {e}")
            self.session.rollback()
            return False

    def _execute_delete_count(self, query: str, params: List[Any]) -> int:
        """Execute a DELETE query and return count."""
        try:
            result = self.session.execute(query, params)
            self.session.commit()
            return result.rowcount
        except Exception as e:
            logger.error(f"Delete error: {e}")
            self.session.rollback()
            return 0


# SQL migrations for adding soft delete columns
SOFT_DELETE_MIGRATION = """
-- Add soft delete columns to a table
ALTER TABLE {table_name} ADD COLUMN IF NOT EXISTS is_deleted BOOLEAN DEFAULT FALSE;
ALTER TABLE {table_name} ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMP;
ALTER TABLE {table_name} ADD COLUMN IF NOT EXISTS deleted_by TEXT;
ALTER TABLE {table_name} ADD COLUMN IF NOT EXISTS deletion_reason TEXT;

-- Create index for filtering active records
CREATE INDEX IF NOT EXISTS idx_{table_name}_is_deleted ON {table_name}(is_deleted);
CREATE INDEX IF NOT EXISTS idx_{table_name}_deleted_at ON {table_name}(deleted_at);
"""

ARCHIVE_MIGRATION = """
-- Add archive columns to a table
ALTER TABLE {table_name} ADD COLUMN IF NOT EXISTS archived_at TIMESTAMP;
ALTER TABLE {table_name} ADD COLUMN IF NOT EXISTS archived_by TEXT;
ALTER TABLE {table_name} ADD COLUMN IF NOT EXISTS archive_location TEXT;

-- Create index for archive queries
CREATE INDEX IF NOT EXISTS idx_{table_name}_archived_at ON {table_name}(archived_at);
"""


def generate_soft_delete_migration(table_name: str) -> str:
    """Generate SQL migration for adding soft delete to a table."""
    return SOFT_DELETE_MIGRATION.format(table_name=table_name)


def generate_archive_migration(table_name: str) -> str:
    """Generate SQL migration for adding archive support to a table."""
    return ARCHIVE_MIGRATION.format(table_name=table_name)


# Decorator for soft-delete aware queries
def exclude_deleted(func):
    """Decorator to automatically exclude deleted records from queries."""
    def wrapper(*args, **kwargs):
        # Add is_deleted=False to query if not explicitly specified
        if 'include_deleted' not in kwargs:
            kwargs['include_deleted'] = False
        return func(*args, **kwargs)
    return wrapper


# Context manager for including deleted records
class IncludeDeleted:
    """Context manager to temporarily include deleted records in queries."""

    def __init__(self, manager: SoftDeleteManager):
        self.manager = manager
        self._original_get_all = None

    def __enter__(self):
        self._original_get_all = self.manager.get_all

        def include_deleted_get_all(**filters):
            return self._original_get_all(include_deleted=True, **filters)

        self.manager.get_all = include_deleted_get_all
        return self.manager

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.manager.get_all = self._original_get_all
        return False


# Cascade soft delete helper
def cascade_soft_delete(
    session: Any,
    parent_table: str,
    parent_id: str,
    child_tables: List[str],
    foreign_key: str,
    deleted_by: Optional[str] = None,
    reason: Optional[str] = None
) -> dict:
    """Cascade soft delete to related tables."""
    results = {"parent": False, "children": {}}
    now = datetime.utcnow().isoformat()

    # Soft delete parent
    parent_query = f"""
    UPDATE {parent_table}
    SET is_deleted = TRUE, deleted_at = ?, deleted_by = ?, deletion_reason = ?
    WHERE id = ? AND is_deleted = FALSE
    """

    try:
        result = session.execute(parent_query, [now, deleted_by, reason, parent_id])
        results["parent"] = result.rowcount > 0

        # Soft delete children
        for child_table in child_tables:
            child_query = f"""
            UPDATE {child_table}
            SET is_deleted = TRUE, deleted_at = ?, deleted_by = ?, deletion_reason = ?
            WHERE {foreign_key} = ? AND is_deleted = FALSE
            """

            result = session.execute(child_query, [now, deleted_by, f"Parent deleted: {reason}", parent_id])
            results["children"][child_table] = result.rowcount

        session.commit()
        logger.info(f"Cascade soft delete completed for {parent_table}:{parent_id}")

    except Exception as e:
        session.rollback()
        logger.error(f"Cascade soft delete failed: {e}")
        raise

    return results
