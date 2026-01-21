"""
Progress Tracking for Long-Running Operations
Reliability Audit Item #23: Shared progress tracker

Provides:
- Operation progress tracking
- Status updates via callbacks
- Cancellation support
- API-queryable progress state
"""

import asyncio
import logging
import os
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional
import threading
import json
from pathlib import Path

logger = logging.getLogger("jarvis.progress")


class OperationStatus(Enum):
    """Status of a tracked operation"""
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class ProgressUpdate:
    """A single progress update"""
    timestamp: datetime
    progress_pct: float
    message: str
    step_current: Optional[int] = None
    step_total: Optional[int] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TrackedOperation:
    """A long-running operation being tracked"""
    operation_id: str
    operation_type: str
    description: str
    status: OperationStatus
    progress_pct: float
    started_at: datetime
    updated_at: datetime
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    current_step: Optional[str] = None
    step_current: int = 0
    step_total: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)
    updates: List[ProgressUpdate] = field(default_factory=list)
    cancellation_requested: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "operation_id": self.operation_id,
            "operation_type": self.operation_type,
            "description": self.description,
            "status": self.status.value,
            "progress_pct": self.progress_pct,
            "started_at": self.started_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "error_message": self.error_message,
            "current_step": self.current_step,
            "step_current": self.step_current,
            "step_total": self.step_total,
            "cancellation_requested": self.cancellation_requested,
            "elapsed_sec": (
                (self.completed_at or datetime.now(timezone.utc)) - self.started_at
            ).total_seconds(),
        }


class ProgressTracker:
    """
    Centralized progress tracking for long-running operations.

    Features:
    - Register and track operations
    - Update progress with messages
    - Step-based progress
    - Cancellation support
    - Persistence for recovery
    - Callbacks for progress updates
    """

    def __init__(
        self,
        state_dir: str = None,
        max_history: int = 100,
        persist: bool = True,
    ):
        self.state_dir = Path(state_dir or os.path.expanduser("~/.lifeos/progress"))
        self.max_history = max_history
        self.persist = persist

        self._operations: Dict[str, TrackedOperation] = {}
        self._completed: List[TrackedOperation] = []
        self._callbacks: List[Callable[[TrackedOperation, ProgressUpdate], None]] = []
        self._lock = threading.Lock()

        if persist:
            self.state_dir.mkdir(parents=True, exist_ok=True)
            self._load_state()

    def _load_state(self):
        """Load persisted operation state"""
        state_file = self.state_dir / "operations.json"
        if not state_file.exists():
            return

        try:
            with open(state_file) as f:
                data = json.load(f)

            for op_data in data.get("active", []):
                # Mark interrupted operations as failed
                op = self._deserialize_operation(op_data)
                if op.status == OperationStatus.RUNNING:
                    op.status = OperationStatus.FAILED
                    op.error_message = "Operation interrupted (process restart)"
                    op.completed_at = datetime.now(timezone.utc)
                    self._completed.append(op)
                else:
                    self._operations[op.operation_id] = op

            for op_data in data.get("completed", [])[-self.max_history:]:
                self._completed.append(self._deserialize_operation(op_data))

        except Exception as e:
            logger.error(f"Failed to load progress state: {e}")

    def _save_state(self):
        """Persist operation state"""
        if not self.persist:
            return

        state_file = self.state_dir / "operations.json"
        data = {
            "active": [self._serialize_operation(op) for op in self._operations.values()],
            "completed": [self._serialize_operation(op) for op in self._completed[-self.max_history:]],
            "saved_at": datetime.now(timezone.utc).isoformat(),
        }

        with open(state_file, "w") as f:
            json.dump(data, f, indent=2)

    def _serialize_operation(self, op: TrackedOperation) -> Dict[str, Any]:
        """Serialize operation for storage"""
        return {
            "operation_id": op.operation_id,
            "operation_type": op.operation_type,
            "description": op.description,
            "status": op.status.value,
            "progress_pct": op.progress_pct,
            "started_at": op.started_at.isoformat(),
            "updated_at": op.updated_at.isoformat(),
            "completed_at": op.completed_at.isoformat() if op.completed_at else None,
            "error_message": op.error_message,
            "current_step": op.current_step,
            "step_current": op.step_current,
            "step_total": op.step_total,
            "metadata": op.metadata,
        }

    def _deserialize_operation(self, data: Dict[str, Any]) -> TrackedOperation:
        """Deserialize operation from storage"""
        return TrackedOperation(
            operation_id=data["operation_id"],
            operation_type=data["operation_type"],
            description=data["description"],
            status=OperationStatus(data["status"]),
            progress_pct=data["progress_pct"],
            started_at=datetime.fromisoformat(data["started_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"]),
            completed_at=datetime.fromisoformat(data["completed_at"]) if data.get("completed_at") else None,
            error_message=data.get("error_message"),
            current_step=data.get("current_step"),
            step_current=data.get("step_current", 0),
            step_total=data.get("step_total", 0),
            metadata=data.get("metadata", {}),
        )

    def start_operation(
        self,
        operation_type: str,
        description: str,
        total_steps: int = 0,
        metadata: Dict[str, Any] = None,
    ) -> str:
        """
        Start tracking a new operation.

        Args:
            operation_type: Type of operation (e.g., 'trade', 'sync', 'backup')
            description: Human-readable description
            total_steps: Total number of steps (0 for indeterminate)
            metadata: Additional metadata

        Returns:
            operation_id: Unique identifier for the operation
        """
        operation_id = str(uuid.uuid4())[:8]
        now = datetime.now(timezone.utc)

        op = TrackedOperation(
            operation_id=operation_id,
            operation_type=operation_type,
            description=description,
            status=OperationStatus.RUNNING,
            progress_pct=0.0,
            started_at=now,
            updated_at=now,
            step_total=total_steps,
            metadata=metadata or {},
        )

        with self._lock:
            self._operations[operation_id] = op
            self._save_state()

        logger.info(f"Started operation {operation_id}: {description}")
        return operation_id

    def update_progress(
        self,
        operation_id: str,
        progress_pct: float = None,
        message: str = None,
        step: int = None,
        step_name: str = None,
        metadata: Dict[str, Any] = None,
    ) -> bool:
        """
        Update operation progress.

        Args:
            operation_id: Operation to update
            progress_pct: Progress percentage (0-100)
            message: Status message
            step: Current step number
            step_name: Name of current step
            metadata: Additional update metadata

        Returns:
            True if update successful, False if operation not found
        """
        with self._lock:
            op = self._operations.get(operation_id)
            if op is None:
                return False

            if op.cancellation_requested:
                op.status = OperationStatus.CANCELLED
                op.completed_at = datetime.now(timezone.utc)
                self._move_to_completed(operation_id)
                return False

            now = datetime.now(timezone.utc)
            op.updated_at = now

            if progress_pct is not None:
                op.progress_pct = min(100.0, max(0.0, progress_pct))

            if step is not None:
                op.step_current = step
                if op.step_total > 0:
                    op.progress_pct = (step / op.step_total) * 100

            if step_name is not None:
                op.current_step = step_name

            if metadata:
                op.metadata.update(metadata)

            update = ProgressUpdate(
                timestamp=now,
                progress_pct=op.progress_pct,
                message=message or f"Progress: {op.progress_pct:.1f}%",
                step_current=op.step_current,
                step_total=op.step_total,
                metadata=metadata or {},
            )
            op.updates.append(update)

            # Keep only recent updates in memory
            if len(op.updates) > 50:
                op.updates = op.updates[-50:]

            self._save_state()

        # Notify callbacks
        for callback in self._callbacks:
            try:
                callback(op, update)
            except Exception as e:
                logger.error(f"Progress callback error: {e}")

        return True

    def complete_operation(
        self,
        operation_id: str,
        success: bool = True,
        message: str = None,
        result: Any = None,
    ):
        """
        Mark an operation as completed.

        Args:
            operation_id: Operation to complete
            success: Whether operation succeeded
            message: Completion message
            result: Operation result (stored in metadata)
        """
        with self._lock:
            op = self._operations.get(operation_id)
            if op is None:
                return

            now = datetime.now(timezone.utc)
            op.updated_at = now
            op.completed_at = now
            op.progress_pct = 100.0 if success else op.progress_pct

            if success:
                op.status = OperationStatus.COMPLETED
            else:
                op.status = OperationStatus.FAILED
                op.error_message = message

            if result is not None:
                op.metadata["result"] = result

            self._move_to_completed(operation_id)

        logger.info(f"Completed operation {operation_id}: {'success' if success else 'failed'}")

    def fail_operation(
        self,
        operation_id: str,
        error: str,
    ):
        """Mark operation as failed"""
        self.complete_operation(operation_id, success=False, message=error)

    def request_cancellation(self, operation_id: str) -> bool:
        """
        Request cancellation of an operation.

        The operation must check is_cancelled() and handle accordingly.
        """
        with self._lock:
            op = self._operations.get(operation_id)
            if op is None:
                return False

            op.cancellation_requested = True
            op.updated_at = datetime.now(timezone.utc)
            self._save_state()

        logger.info(f"Cancellation requested for operation {operation_id}")
        return True

    def is_cancelled(self, operation_id: str) -> bool:
        """Check if cancellation has been requested"""
        with self._lock:
            op = self._operations.get(operation_id)
            return op.cancellation_requested if op else True

    def get_operation(self, operation_id: str) -> Optional[TrackedOperation]:
        """Get operation status"""
        with self._lock:
            if operation_id in self._operations:
                return self._operations[operation_id]
            for op in self._completed:
                if op.operation_id == operation_id:
                    return op
        return None

    def get_active_operations(self) -> List[TrackedOperation]:
        """Get all active operations"""
        with self._lock:
            return list(self._operations.values())

    def get_completed_operations(self, limit: int = 20) -> List[TrackedOperation]:
        """Get recent completed operations"""
        with self._lock:
            return self._completed[-limit:]

    def get_operations_by_type(self, operation_type: str) -> List[TrackedOperation]:
        """Get operations by type"""
        with self._lock:
            active = [op for op in self._operations.values() if op.operation_type == operation_type]
            completed = [op for op in self._completed if op.operation_type == operation_type]
            return active + completed

    def on_progress(self, callback: Callable[[TrackedOperation, ProgressUpdate], None]):
        """Register progress update callback"""
        self._callbacks.append(callback)

    def _move_to_completed(self, operation_id: str):
        """Move operation from active to completed"""
        op = self._operations.pop(operation_id, None)
        if op:
            self._completed.append(op)
            if len(self._completed) > self.max_history:
                self._completed.pop(0)
            self._save_state()

    def get_summary(self) -> Dict[str, Any]:
        """Get tracker summary for health checks"""
        with self._lock:
            active_count = len(self._operations)
            completed_count = len(self._completed)

            by_status = {}
            for op in list(self._operations.values()) + self._completed[-50:]:
                status = op.status.value
                by_status[status] = by_status.get(status, 0) + 1

            return {
                "active_operations": active_count,
                "completed_operations": completed_count,
                "by_status": by_status,
                "active": [op.to_dict() for op in self._operations.values()],
            }


class ProgressContext:
    """Context manager for progress tracking"""

    def __init__(
        self,
        tracker: ProgressTracker,
        operation_type: str,
        description: str,
        total_steps: int = 0,
    ):
        self.tracker = tracker
        self.operation_type = operation_type
        self.description = description
        self.total_steps = total_steps
        self.operation_id: Optional[str] = None

    def __enter__(self):
        self.operation_id = self.tracker.start_operation(
            operation_type=self.operation_type,
            description=self.description,
            total_steps=self.total_steps,
        )
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            self.tracker.fail_operation(self.operation_id, str(exc_val))
        else:
            self.tracker.complete_operation(self.operation_id)
        return False

    def update(
        self,
        progress_pct: float = None,
        message: str = None,
        step: int = None,
    ):
        """Update progress"""
        self.tracker.update_progress(
            self.operation_id,
            progress_pct=progress_pct,
            message=message,
            step=step,
        )

    def is_cancelled(self) -> bool:
        """Check if cancellation requested"""
        return self.tracker.is_cancelled(self.operation_id)


# =============================================================================
# SINGLETON
# =============================================================================

_tracker: Optional[ProgressTracker] = None


def get_progress_tracker() -> ProgressTracker:
    """Get or create the progress tracker singleton"""
    global _tracker
    if _tracker is None:
        _tracker = ProgressTracker()
    return _tracker


def track_operation(
    operation_type: str,
    description: str,
    total_steps: int = 0,
) -> ProgressContext:
    """
    Convenience function for tracking operations.

    Usage:
        with track_operation("backup", "Backing up data", total_steps=3) as progress:
            progress.update(step=1, message="Step 1")
            if progress.is_cancelled():
                return
            progress.update(step=2, message="Step 2")
            progress.update(step=3, message="Step 3")
    """
    return ProgressContext(
        tracker=get_progress_tracker(),
        operation_type=operation_type,
        description=description,
        total_steps=total_steps,
    )
