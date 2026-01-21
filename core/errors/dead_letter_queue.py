"""
Dead Letter Queue for Failed API Calls
Reliability Audit Item #11: DLQ for failed requests

Captures and stores failed requests after retries are exhausted,
allowing for later analysis, retry, or manual intervention.

Features:
- Persistent storage of failed requests
- Automatic retry scheduling
- Manual retry capability
- Failure analytics
- Configurable retention
"""

import asyncio
import json
import logging
import os
import time
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional
import threading

logger = logging.getLogger("jarvis.errors.dlq")


class FailureReason(Enum):
    """Categorized failure reasons"""
    TIMEOUT = "timeout"
    RATE_LIMITED = "rate_limited"
    AUTH_ERROR = "auth_error"
    VALIDATION_ERROR = "validation_error"
    SERVER_ERROR = "server_error"
    NETWORK_ERROR = "network_error"
    UNKNOWN = "unknown"


class DLQItemStatus(Enum):
    """Status of a DLQ item"""
    PENDING = "pending"        # Awaiting retry
    RETRYING = "retrying"      # Currently being retried
    RESOLVED = "resolved"      # Successfully processed
    ABANDONED = "abandoned"    # Manually marked as abandoned
    EXPIRED = "expired"        # Past retention period


@dataclass
class DLQItem:
    """A dead letter queue item"""
    id: str
    created_at: datetime
    service: str
    endpoint: str
    method: str
    request_data: Dict[str, Any]
    failure_reason: FailureReason
    error_message: str
    retry_count: int
    max_retries: int
    status: DLQItemStatus
    last_retry_at: Optional[datetime] = None
    next_retry_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "created_at": self.created_at.isoformat(),
            "service": self.service,
            "endpoint": self.endpoint,
            "method": self.method,
            "request_data": self.request_data,
            "failure_reason": self.failure_reason.value,
            "error_message": self.error_message,
            "retry_count": self.retry_count,
            "max_retries": self.max_retries,
            "status": self.status.value,
            "last_retry_at": self.last_retry_at.isoformat() if self.last_retry_at else None,
            "next_retry_at": self.next_retry_at.isoformat() if self.next_retry_at else None,
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DLQItem":
        return cls(
            id=data["id"],
            created_at=datetime.fromisoformat(data["created_at"]),
            service=data["service"],
            endpoint=data["endpoint"],
            method=data["method"],
            request_data=data["request_data"],
            failure_reason=FailureReason(data["failure_reason"]),
            error_message=data["error_message"],
            retry_count=data["retry_count"],
            max_retries=data["max_retries"],
            status=DLQItemStatus(data["status"]),
            last_retry_at=datetime.fromisoformat(data["last_retry_at"]) if data.get("last_retry_at") else None,
            next_retry_at=datetime.fromisoformat(data["next_retry_at"]) if data.get("next_retry_at") else None,
            resolved_at=datetime.fromisoformat(data["resolved_at"]) if data.get("resolved_at") else None,
            metadata=data.get("metadata", {}),
        )


class DeadLetterQueue:
    """
    Dead Letter Queue for storing and managing failed requests.

    Failed requests are stored with their full context and can be
    retried manually or automatically based on configuration.
    """

    def __init__(
        self,
        storage_dir: str = None,
        max_items: int = 10000,
        retention_days: int = 7,
        auto_retry_enabled: bool = True,
        auto_retry_interval_sec: int = 300,  # 5 minutes
    ):
        self.storage_dir = Path(storage_dir or os.path.expanduser("~/.lifeos/dlq"))
        self.storage_dir.mkdir(parents=True, exist_ok=True)

        self.max_items = max_items
        self.retention_days = retention_days
        self.auto_retry_enabled = auto_retry_enabled
        self.auto_retry_interval_sec = auto_retry_interval_sec

        # In-memory cache of items
        self._items: Dict[str, DLQItem] = {}

        # Retry handlers by service
        self._retry_handlers: Dict[str, Callable] = {}

        # Lock for thread safety
        self._lock = threading.Lock()

        # Load existing items
        self._load_items()

        # Start auto-retry thread if enabled
        self._running = True
        if auto_retry_enabled:
            self._retry_thread = threading.Thread(
                target=self._auto_retry_loop,
                daemon=True,
                name="DLQAutoRetry"
            )
            self._retry_thread.start()

    def stop(self):
        """Stop the DLQ"""
        self._running = False

    def _load_items(self):
        """Load items from persistent storage"""
        items_file = self.storage_dir / "dlq_items.json"
        if not items_file.exists():
            return

        try:
            with open(items_file) as f:
                data = json.load(f)

            for item_data in data.get("items", []):
                try:
                    item = DLQItem.from_dict(item_data)
                    # Skip expired items
                    if item.status != DLQItemStatus.EXPIRED:
                        self._items[item.id] = item
                except Exception as e:
                    logger.warning(f"Failed to load DLQ item: {e}")

            logger.info(f"Loaded {len(self._items)} DLQ items")

        except Exception as e:
            logger.error(f"Failed to load DLQ items: {e}")

    def _save_items(self):
        """Persist items to storage"""
        items_file = self.storage_dir / "dlq_items.json"

        try:
            data = {
                "items": [item.to_dict() for item in self._items.values()],
                "saved_at": datetime.now(timezone.utc).isoformat(),
            }
            with open(items_file, "w") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save DLQ items: {e}")

    def _auto_retry_loop(self):
        """Background loop for automatic retries"""
        while self._running:
            try:
                asyncio.run(self._process_retry_batch())
            except Exception as e:
                logger.error(f"Auto-retry error: {e}")

            time.sleep(self.auto_retry_interval_sec)

    async def _process_retry_batch(self):
        """Process a batch of items due for retry"""
        now = datetime.now(timezone.utc)

        with self._lock:
            due_items = [
                item for item in self._items.values()
                if item.status == DLQItemStatus.PENDING
                and item.next_retry_at
                and item.next_retry_at <= now
                and item.retry_count < item.max_retries
            ]

        for item in due_items[:10]:  # Process 10 at a time
            await self.retry_item(item.id)

    def add_item(
        self,
        service: str,
        endpoint: str,
        method: str,
        request_data: Dict[str, Any],
        error: Exception,
        failure_reason: FailureReason = None,
        max_retries: int = 3,
        metadata: Dict[str, Any] = None,
    ) -> str:
        """
        Add a failed request to the DLQ.

        Args:
            service: Service name (e.g., 'jupiter', 'helius')
            endpoint: API endpoint that failed
            method: HTTP method
            request_data: Request payload
            error: The exception that caused failure
            failure_reason: Categorized reason
            max_retries: Maximum retry attempts
            metadata: Additional context

        Returns:
            Item ID
        """
        item_id = str(uuid.uuid4())[:12]
        now = datetime.now(timezone.utc)

        # Determine failure reason from exception if not provided
        if failure_reason is None:
            failure_reason = self._classify_error(error)

        # Calculate next retry time (exponential backoff)
        next_retry = now + timedelta(minutes=5)

        item = DLQItem(
            id=item_id,
            created_at=now,
            service=service,
            endpoint=endpoint,
            method=method,
            request_data=request_data,
            failure_reason=failure_reason,
            error_message=str(error)[:500],
            retry_count=0,
            max_retries=max_retries,
            status=DLQItemStatus.PENDING,
            next_retry_at=next_retry,
            metadata=metadata or {},
        )

        with self._lock:
            # Enforce max items limit
            if len(self._items) >= self.max_items:
                self._evict_oldest()

            self._items[item_id] = item
            self._save_items()

        logger.warning(f"Added to DLQ [{item_id}]: {service}/{endpoint} - {error}")

        return item_id

    def _classify_error(self, error: Exception) -> FailureReason:
        """Classify an error into a failure reason"""
        error_str = str(error).lower()

        if "timeout" in error_str:
            return FailureReason.TIMEOUT
        elif "rate" in error_str and "limit" in error_str:
            return FailureReason.RATE_LIMITED
        elif "401" in error_str or "403" in error_str or "auth" in error_str:
            return FailureReason.AUTH_ERROR
        elif "400" in error_str or "validation" in error_str:
            return FailureReason.VALIDATION_ERROR
        elif "500" in error_str or "502" in error_str or "503" in error_str:
            return FailureReason.SERVER_ERROR
        elif "connection" in error_str or "network" in error_str:
            return FailureReason.NETWORK_ERROR
        else:
            return FailureReason.UNKNOWN

    def _evict_oldest(self):
        """Remove oldest resolved/expired items to make room"""
        # First try to remove resolved/expired items
        for item_id, item in list(self._items.items()):
            if item.status in [DLQItemStatus.RESOLVED, DLQItemStatus.EXPIRED, DLQItemStatus.ABANDONED]:
                del self._items[item_id]
                if len(self._items) < self.max_items:
                    return

        # If still full, remove oldest pending items
        sorted_items = sorted(self._items.values(), key=lambda x: x.created_at)
        for item in sorted_items[:100]:
            del self._items[item.id]
            if len(self._items) < self.max_items:
                return

    def register_retry_handler(
        self,
        service: str,
        handler: Callable,
    ):
        """
        Register a retry handler for a service.

        Handler signature: async def handler(item: DLQItem) -> bool
        Returns True if retry succeeded.
        """
        self._retry_handlers[service] = handler
        logger.info(f"Registered DLQ retry handler for {service}")

    async def retry_item(self, item_id: str) -> bool:
        """
        Retry a specific item.

        Returns True if retry succeeded.
        """
        with self._lock:
            item = self._items.get(item_id)
            if item is None:
                return False

            if item.retry_count >= item.max_retries:
                item.status = DLQItemStatus.ABANDONED
                self._save_items()
                return False

            item.status = DLQItemStatus.RETRYING
            item.retry_count += 1
            item.last_retry_at = datetime.now(timezone.utc)

        # Get handler for service
        handler = self._retry_handlers.get(item.service)
        if handler is None:
            logger.warning(f"No retry handler for service: {item.service}")
            with self._lock:
                item.status = DLQItemStatus.PENDING
                # Exponential backoff for next retry
                backoff_minutes = 5 * (2 ** item.retry_count)
                item.next_retry_at = datetime.now(timezone.utc) + timedelta(minutes=backoff_minutes)
                self._save_items()
            return False

        # Attempt retry
        try:
            success = await handler(item)

            with self._lock:
                if success:
                    item.status = DLQItemStatus.RESOLVED
                    item.resolved_at = datetime.now(timezone.utc)
                    logger.info(f"DLQ item {item_id} resolved on retry {item.retry_count}")
                else:
                    item.status = DLQItemStatus.PENDING
                    backoff_minutes = 5 * (2 ** item.retry_count)
                    item.next_retry_at = datetime.now(timezone.utc) + timedelta(minutes=backoff_minutes)

                self._save_items()

            return success

        except Exception as e:
            logger.error(f"DLQ retry failed for {item_id}: {e}")

            with self._lock:
                item.status = DLQItemStatus.PENDING
                item.error_message = str(e)[:500]
                backoff_minutes = 5 * (2 ** item.retry_count)
                item.next_retry_at = datetime.now(timezone.utc) + timedelta(minutes=backoff_minutes)
                self._save_items()

            return False

    def abandon_item(self, item_id: str):
        """Mark an item as abandoned (no more retries)"""
        with self._lock:
            item = self._items.get(item_id)
            if item:
                item.status = DLQItemStatus.ABANDONED
                self._save_items()

    def get_item(self, item_id: str) -> Optional[DLQItem]:
        """Get a specific item"""
        with self._lock:
            return self._items.get(item_id)

    def get_items(
        self,
        status: Optional[DLQItemStatus] = None,
        service: Optional[str] = None,
        limit: int = 100,
    ) -> List[DLQItem]:
        """Get items with optional filtering"""
        with self._lock:
            items = list(self._items.values())

        if status:
            items = [i for i in items if i.status == status]
        if service:
            items = [i for i in items if i.service == service]

        items.sort(key=lambda x: x.created_at, reverse=True)
        return items[:limit]

    def get_summary(self) -> Dict[str, Any]:
        """Get summary for health dashboard"""
        with self._lock:
            items = list(self._items.values())

        by_status = {}
        by_service = {}
        by_reason = {}

        for item in items:
            by_status[item.status.value] = by_status.get(item.status.value, 0) + 1
            by_service[item.service] = by_service.get(item.service, 0) + 1
            by_reason[item.failure_reason.value] = by_reason.get(item.failure_reason.value, 0) + 1

        pending_count = by_status.get("pending", 0)

        return {
            "total_items": len(items),
            "pending_items": pending_count,
            "status": "warning" if pending_count > 10 else "ok",
            "by_status": by_status,
            "by_service": by_service,
            "by_reason": by_reason,
            "auto_retry_enabled": self.auto_retry_enabled,
        }

    def cleanup_old_items(self):
        """Remove items past retention period"""
        cutoff = datetime.now(timezone.utc) - timedelta(days=self.retention_days)

        with self._lock:
            to_remove = [
                item_id for item_id, item in self._items.items()
                if item.created_at < cutoff
            ]

            for item_id in to_remove:
                del self._items[item_id]

            if to_remove:
                self._save_items()
                logger.info(f"Cleaned up {len(to_remove)} old DLQ items")


# =============================================================================
# SINGLETON
# =============================================================================

_dlq: Optional[DeadLetterQueue] = None


def get_dead_letter_queue() -> DeadLetterQueue:
    """Get or create the DLQ singleton"""
    global _dlq
    if _dlq is None:
        _dlq = DeadLetterQueue()
    return _dlq


def add_to_dlq(
    service: str,
    endpoint: str,
    method: str,
    request_data: Dict[str, Any],
    error: Exception,
    **kwargs,
) -> str:
    """Convenience function to add a failed request to DLQ"""
    dlq = get_dead_letter_queue()
    return dlq.add_item(
        service=service,
        endpoint=endpoint,
        method=method,
        request_data=request_data,
        error=error,
        **kwargs,
    )
