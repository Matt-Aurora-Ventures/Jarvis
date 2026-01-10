"""
Data Deletion System
Prompt #89: GDPR-compliant data deletion with audit trail

Handles user data deletion requests with verification and audit logging.
"""

import asyncio
import hashlib
import logging
import os
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set
import json

logger = logging.getLogger("jarvis.data.deletion")


# =============================================================================
# MODELS
# =============================================================================

class DeletionStatus(Enum):
    """Status of a deletion request"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    PARTIAL = "partial"  # Some data deleted, some retained


class DeletionScope(Enum):
    """Scope of data to delete"""
    ALL = "all"
    TRADE_DATA = "trade_data"
    CONSENT_DATA = "consent_data"
    ANALYTICS_DATA = "analytics_data"
    MARKETPLACE_DATA = "marketplace_data"


@dataclass
class DeletionTarget:
    """A data source that can be deleted from"""
    name: str
    delete_func: Callable[[str], int]  # Takes user_hash, returns count deleted
    verify_func: Optional[Callable[[str], bool]] = None  # Verify deletion


@dataclass
class DeletionRequest:
    """A request to delete user data"""
    id: str
    user_hash: str
    scope: DeletionScope
    status: DeletionStatus = DeletionStatus.PENDING
    requested_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    processed_at: Optional[datetime] = None
    records_deleted: int = 0
    targets_processed: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)


@dataclass
class DeletionResult:
    """Result of a deletion operation"""
    success: bool
    request_id: str
    records_deleted: int
    targets_processed: List[str]
    errors: List[str]
    processing_time_ms: int


# =============================================================================
# DATA DELETION SERVICE
# =============================================================================

class DataDeletionService:
    """
    GDPR-compliant data deletion service.

    Features:
    - Register deletion targets (databases, caches, etc.)
    - Execute deletions with verification
    - Maintain audit trail
    - Support partial deletion by scope
    """

    def __init__(self, db_path: str = None):
        self.db_path = db_path or os.getenv(
            "DELETION_AUDIT_DB",
            "data/deletion_audit.db"
        )
        self._targets: Dict[str, DeletionTarget] = {}
        self._callbacks: List[Callable] = []

        self._init_database()
        self._register_default_targets()

    def _init_database(self):
        """Initialize audit database"""
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Deletion requests table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS deletion_requests (
                id TEXT PRIMARY KEY,
                user_hash TEXT NOT NULL,
                scope TEXT NOT NULL,
                status TEXT NOT NULL,
                requested_at TEXT NOT NULL,
                processed_at TEXT,
                records_deleted INTEGER DEFAULT 0,
                targets_processed TEXT,
                errors TEXT
            )
        """)

        # Audit log for compliance
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS deletion_audit (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                request_id TEXT NOT NULL,
                action TEXT NOT NULL,
                target TEXT,
                records_affected INTEGER,
                details TEXT,
                timestamp TEXT NOT NULL,
                FOREIGN KEY (request_id) REFERENCES deletion_requests(id)
            )
        """)

        # Indexes
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_requests_user
            ON deletion_requests(user_hash)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_requests_status
            ON deletion_requests(status)
        """)

        conn.commit()
        conn.close()

    def _register_default_targets(self):
        """Register default deletion targets"""
        # Trade data target
        self.register_target(DeletionTarget(
            name="trade_data",
            delete_func=self._delete_trade_data,
            verify_func=self._verify_trade_deletion,
        ))

        # Collection audit target
        self.register_target(DeletionTarget(
            name="collection_audit",
            delete_func=self._delete_collection_audit,
        ))

        # Analytics events target
        self.register_target(DeletionTarget(
            name="analytics_events",
            delete_func=self._delete_analytics_events,
        ))

    # =========================================================================
    # TARGET REGISTRATION
    # =========================================================================

    def register_target(self, target: DeletionTarget):
        """Register a deletion target"""
        self._targets[target.name] = target
        logger.info(f"Registered deletion target: {target.name}")

    def unregister_target(self, name: str):
        """Unregister a deletion target"""
        if name in self._targets:
            del self._targets[name]
            logger.info(f"Unregistered deletion target: {name}")

    def get_targets(self) -> List[str]:
        """Get list of registered targets"""
        return list(self._targets.keys())

    # =========================================================================
    # DELETION OPERATIONS
    # =========================================================================

    async def request_deletion(
        self,
        user_id: str,
        scope: DeletionScope = DeletionScope.ALL,
    ) -> DeletionRequest:
        """
        Create a deletion request for a user.

        Args:
            user_id: User identifier (will be hashed)
            scope: Scope of data to delete

        Returns:
            DeletionRequest object
        """
        # Hash user ID for privacy
        user_hash = self._hash_user_id(user_id)

        # Generate request ID
        request_id = hashlib.sha256(
            f"{user_hash}:{datetime.now(timezone.utc).isoformat()}".encode()
        ).hexdigest()[:16]

        request = DeletionRequest(
            id=request_id,
            user_hash=user_hash,
            scope=scope,
        )

        # Store request
        await self._store_request(request)

        # Log audit
        await self._log_audit(
            request_id=request_id,
            action="request_created",
            details=f"Deletion requested for scope: {scope.value}",
        )

        logger.info(f"Deletion request created: {request_id}")

        return request

    async def execute_deletion(
        self,
        request_id: str,
    ) -> DeletionResult:
        """
        Execute a deletion request.

        Args:
            request_id: ID of the deletion request

        Returns:
            DeletionResult with outcome
        """
        start_time = datetime.now(timezone.utc)

        # Get request
        request = await self.get_request(request_id)
        if request is None:
            return DeletionResult(
                success=False,
                request_id=request_id,
                records_deleted=0,
                targets_processed=[],
                errors=["Request not found"],
                processing_time_ms=0,
            )

        # Update status
        request.status = DeletionStatus.PROCESSING
        await self._update_request(request)

        await self._log_audit(
            request_id=request_id,
            action="processing_started",
        )

        # Get targets based on scope
        targets = self._get_targets_for_scope(request.scope)

        total_deleted = 0
        processed = []
        errors = []

        # Execute deletion for each target
        for target_name in targets:
            target = self._targets.get(target_name)
            if target is None:
                continue

            try:
                # Execute deletion
                deleted = await asyncio.to_thread(
                    target.delete_func, request.user_hash
                )

                total_deleted += deleted
                processed.append(target_name)

                await self._log_audit(
                    request_id=request_id,
                    action="target_deleted",
                    target=target_name,
                    records_affected=deleted,
                )

                # Verify if available
                if target.verify_func:
                    verified = await asyncio.to_thread(
                        target.verify_func, request.user_hash
                    )
                    if not verified:
                        errors.append(f"Verification failed for {target_name}")

            except Exception as e:
                error_msg = f"Error deleting from {target_name}: {e}"
                errors.append(error_msg)
                logger.error(error_msg)

                await self._log_audit(
                    request_id=request_id,
                    action="target_error",
                    target=target_name,
                    details=str(e),
                )

        # Update request
        end_time = datetime.now(timezone.utc)
        request.status = (
            DeletionStatus.COMPLETED if not errors
            else DeletionStatus.PARTIAL if processed
            else DeletionStatus.FAILED
        )
        request.processed_at = end_time
        request.records_deleted = total_deleted
        request.targets_processed = processed
        request.errors = errors

        await self._update_request(request)

        await self._log_audit(
            request_id=request_id,
            action="processing_completed",
            records_affected=total_deleted,
            details=f"Status: {request.status.value}",
        )

        # Notify callbacks
        for callback in self._callbacks:
            try:
                await callback(request)
            except Exception as e:
                logger.error(f"Callback error: {e}")

        processing_time = int((end_time - start_time).total_seconds() * 1000)

        return DeletionResult(
            success=request.status == DeletionStatus.COMPLETED,
            request_id=request_id,
            records_deleted=total_deleted,
            targets_processed=processed,
            errors=errors,
            processing_time_ms=processing_time,
        )

    def _get_targets_for_scope(self, scope: DeletionScope) -> List[str]:
        """Get target names for a deletion scope"""
        if scope == DeletionScope.ALL:
            return list(self._targets.keys())

        scope_mapping = {
            DeletionScope.TRADE_DATA: ["trade_data", "collection_audit"],
            DeletionScope.CONSENT_DATA: ["consent_data"],
            DeletionScope.ANALYTICS_DATA: ["analytics_events"],
            DeletionScope.MARKETPLACE_DATA: ["marketplace_data"],
        }

        return scope_mapping.get(scope, [])

    # =========================================================================
    # DEFAULT TARGET IMPLEMENTATIONS
    # =========================================================================

    def _delete_trade_data(self, user_hash: str) -> int:
        """Delete trade data for a user"""
        trade_db = os.getenv("TRADE_DATA_DB", "data/trade_data.db")

        if not os.path.exists(trade_db):
            return 0

        conn = sqlite3.connect(trade_db)
        cursor = conn.cursor()

        cursor.execute(
            "DELETE FROM anonymized_trades WHERE user_hash = ?",
            (user_hash,)
        )

        deleted = cursor.rowcount
        conn.commit()
        conn.close()

        return deleted

    def _verify_trade_deletion(self, user_hash: str) -> bool:
        """Verify trade data was deleted"""
        trade_db = os.getenv("TRADE_DATA_DB", "data/trade_data.db")

        if not os.path.exists(trade_db):
            return True

        conn = sqlite3.connect(trade_db)
        cursor = conn.cursor()

        cursor.execute(
            "SELECT COUNT(*) FROM anonymized_trades WHERE user_hash = ?",
            (user_hash,)
        )

        count = cursor.fetchone()[0]
        conn.close()

        return count == 0

    def _delete_collection_audit(self, user_hash: str) -> int:
        """Delete collection audit records for a user"""
        trade_db = os.getenv("TRADE_DATA_DB", "data/trade_data.db")

        if not os.path.exists(trade_db):
            return 0

        conn = sqlite3.connect(trade_db)
        cursor = conn.cursor()

        cursor.execute(
            "DELETE FROM collection_audit WHERE user_hash = ?",
            (user_hash,)
        )

        deleted = cursor.rowcount
        conn.commit()
        conn.close()

        return deleted

    def _delete_analytics_events(self, user_hash: str) -> int:
        """Delete analytics events for a user"""
        analytics_db = os.getenv("ANALYTICS_DB", "data/analytics.db")

        if not os.path.exists(analytics_db):
            return 0

        conn = sqlite3.connect(analytics_db)
        cursor = conn.cursor()

        # Delete events with this user hash in properties
        cursor.execute("""
            DELETE FROM events
            WHERE properties LIKE ?
        """, (f'%"{user_hash}"%',))

        deleted = cursor.rowcount
        conn.commit()
        conn.close()

        return deleted

    # =========================================================================
    # HELPERS
    # =========================================================================

    def _hash_user_id(self, user_id: str) -> str:
        """Hash user ID for storage"""
        salt = os.getenv("ANONYMIZATION_SALT", "jarvis-default-salt")
        return hashlib.sha256(f"{salt}:{user_id}".encode()).hexdigest()

    async def _store_request(self, request: DeletionRequest):
        """Store a deletion request"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO deletion_requests
            (id, user_hash, scope, status, requested_at, processed_at,
             records_deleted, targets_processed, errors)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            request.id,
            request.user_hash,
            request.scope.value,
            request.status.value,
            request.requested_at.isoformat(),
            request.processed_at.isoformat() if request.processed_at else None,
            request.records_deleted,
            json.dumps(request.targets_processed),
            json.dumps(request.errors),
        ))

        conn.commit()
        conn.close()

    async def _update_request(self, request: DeletionRequest):
        """Update a deletion request"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            UPDATE deletion_requests SET
                status = ?,
                processed_at = ?,
                records_deleted = ?,
                targets_processed = ?,
                errors = ?
            WHERE id = ?
        """, (
            request.status.value,
            request.processed_at.isoformat() if request.processed_at else None,
            request.records_deleted,
            json.dumps(request.targets_processed),
            json.dumps(request.errors),
            request.id,
        ))

        conn.commit()
        conn.close()

    async def get_request(self, request_id: str) -> Optional[DeletionRequest]:
        """Get a deletion request by ID"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            "SELECT * FROM deletion_requests WHERE id = ?",
            (request_id,)
        )

        row = cursor.fetchone()
        conn.close()

        if row is None:
            return None

        return DeletionRequest(
            id=row[0],
            user_hash=row[1],
            scope=DeletionScope(row[2]),
            status=DeletionStatus(row[3]),
            requested_at=datetime.fromisoformat(row[4]),
            processed_at=datetime.fromisoformat(row[5]) if row[5] else None,
            records_deleted=row[6],
            targets_processed=json.loads(row[7]) if row[7] else [],
            errors=json.loads(row[8]) if row[8] else [],
        )

    async def get_user_requests(self, user_id: str) -> List[DeletionRequest]:
        """Get all deletion requests for a user"""
        user_hash = self._hash_user_id(user_id)

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            "SELECT * FROM deletion_requests WHERE user_hash = ?",
            (user_hash,)
        )

        requests = []
        for row in cursor.fetchall():
            requests.append(DeletionRequest(
                id=row[0],
                user_hash=row[1],
                scope=DeletionScope(row[2]),
                status=DeletionStatus(row[3]),
                requested_at=datetime.fromisoformat(row[4]),
                processed_at=datetime.fromisoformat(row[5]) if row[5] else None,
                records_deleted=row[6],
                targets_processed=json.loads(row[7]) if row[7] else [],
                errors=json.loads(row[8]) if row[8] else [],
            ))

        conn.close()
        return requests

    async def _log_audit(
        self,
        request_id: str,
        action: str,
        target: str = None,
        records_affected: int = 0,
        details: str = None,
    ):
        """Log an audit entry"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO deletion_audit
            (request_id, action, target, records_affected, details, timestamp)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            request_id,
            action,
            target,
            records_affected,
            details,
            datetime.now(timezone.utc).isoformat(),
        ))

        conn.commit()
        conn.close()

    async def get_audit_log(
        self,
        request_id: str = None,
        since: datetime = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Get audit log entries"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        query = "SELECT * FROM deletion_audit WHERE 1=1"
        params = []

        if request_id:
            query += " AND request_id = ?"
            params.append(request_id)

        if since:
            query += " AND timestamp >= ?"
            params.append(since.isoformat())

        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)

        cursor.execute(query, params)

        columns = [d[0] for d in cursor.description]
        entries = [dict(zip(columns, row)) for row in cursor.fetchall()]

        conn.close()
        return entries

    # =========================================================================
    # CALLBACKS
    # =========================================================================

    def on_deletion_complete(self, callback: Callable):
        """Register a callback for deletion completion"""
        self._callbacks.append(callback)


# =============================================================================
# SINGLETON
# =============================================================================

_deletion_service: Optional[DataDeletionService] = None


def get_deletion_service() -> DataDeletionService:
    """Get or create the deletion service singleton"""
    global _deletion_service
    if _deletion_service is None:
        _deletion_service = DataDeletionService()
    return _deletion_service
