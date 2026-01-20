"""
Dead Letter Queue (DLQ) for Failed Messages

In-memory implementation with:
- Retry mechanism with exponential backoff
- Monitoring for DLQ depth
- Failed message categorization
- Automatic replay
- Metrics tracking

Handles failures for:
- Failed trade executions
- Undeliverable alerts
- Failed API callbacks
- Malformed incoming messages
"""

import asyncio
import logging
import time
import uuid
from abc import ABC, abstractmethod
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Optional, Dict, List, Any, Callable, Awaitable, Deque

logger = logging.getLogger(__name__)


class MessageType(Enum):
    """Types of messages that can be queued"""
    TRADE_EXECUTION = "trade_execution"
    ALERT_DELIVERY = "alert_delivery"
    API_CALLBACK = "api_callback"
    INCOMING_MESSAGE = "incoming_message"
    WEBHOOK = "webhook"
    NOTIFICATION = "notification"
    OTHER = "other"


class FailureReason(Enum):
    """Categorized failure reasons"""
    TIMEOUT = "timeout"
    NETWORK_ERROR = "network_error"
    VALIDATION_ERROR = "validation_error"
    MALFORMED_DATA = "malformed_data"
    RATE_LIMIT = "rate_limit"
    SERVICE_UNAVAILABLE = "service_unavailable"
    AUTHENTICATION_ERROR = "authentication_error"
    UNKNOWN = "unknown"


class RetryStrategy(Enum):
    """Retry strategies"""
    EXPONENTIAL = "exponential"  # 1s, 2s, 4s, 8s...
    LINEAR = "linear"            # 5s, 10s, 15s, 20s...
    FIXED = "fixed"              # Same interval each time
    NONE = "none"                # No retries


@dataclass
class FailedMessage:
    """Represents a message that failed processing"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    message_type: MessageType = MessageType.OTHER
    payload: Dict[str, Any] = field(default_factory=dict)
    failure_reason: FailureReason = FailureReason.UNKNOWN
    error_message: str = ""
    failed_at: datetime = field(default_factory=datetime.utcnow)
    retry_count: int = 0
    max_retries: int = 3
    retry_strategy: RetryStrategy = RetryStrategy.EXPONENTIAL
    next_retry_at: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def should_retry(self) -> bool:
        """Check if message should be retried"""
        if self.retry_strategy == RetryStrategy.NONE:
            return False
        if self.retry_count >= self.max_retries:
            return False
        return True

    def is_ready_for_retry(self) -> bool:
        """Check if message is ready for retry (time-based)"""
        if not self.should_retry():
            return False
        if self.next_retry_at and datetime.utcnow() < self.next_retry_at:
            return False
        return True

    def calculate_next_retry(self) -> None:
        """Calculate next retry time based on strategy"""
        if self.retry_strategy == RetryStrategy.EXPONENTIAL:
            delay_seconds = min(2 ** self.retry_count, 300)  # Cap at 5 minutes
        elif self.retry_strategy == RetryStrategy.LINEAR:
            delay_seconds = 5 * (self.retry_count + 1)
        elif self.retry_strategy == RetryStrategy.FIXED:
            delay_seconds = 30
        else:
            delay_seconds = 0

        self.next_retry_at = datetime.utcnow() + timedelta(seconds=delay_seconds)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "id": self.id,
            "message_type": self.message_type.value,
            "payload": self.payload,
            "failure_reason": self.failure_reason.value,
            "error_message": self.error_message,
            "failed_at": self.failed_at.isoformat(),
            "retry_count": self.retry_count,
            "max_retries": self.max_retries,
            "retry_strategy": self.retry_strategy.value,
            "next_retry_at": self.next_retry_at.isoformat() if self.next_retry_at else None,
            "metadata": self.metadata
        }


@dataclass
class DLQMetrics:
    """Metrics for dead letter queue"""
    total_failures: int = 0
    total_retries: int = 0
    total_successes: int = 0
    total_permanent_failures: int = 0
    failures_by_type: Dict[str, int] = field(default_factory=lambda: defaultdict(int))
    failures_by_reason: Dict[str, int] = field(default_factory=lambda: defaultdict(int))
    avg_retry_count: float = 0.0
    current_queue_depth: int = 0
    max_queue_depth_seen: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "total_failures": self.total_failures,
            "total_retries": self.total_retries,
            "total_successes": self.total_successes,
            "total_permanent_failures": self.total_permanent_failures,
            "failures_by_type": dict(self.failures_by_type),
            "failures_by_reason": dict(self.failures_by_reason),
            "avg_retry_count": self.avg_retry_count,
            "current_queue_depth": self.current_queue_depth,
            "max_queue_depth_seen": self.max_queue_depth_seen
        }


class MessageProcessor(ABC):
    """Abstract base for message processors"""

    @abstractmethod
    async def process(self, message: FailedMessage) -> bool:
        """
        Process a failed message.

        Returns:
            True if successful, False if failed
        """
        pass

    @abstractmethod
    def can_process(self, message_type: MessageType) -> bool:
        """Check if this processor handles this message type"""
        pass


class DeadLetterQueue:
    """
    In-memory dead letter queue with retry and monitoring.

    Features:
    - Automatic retry with configurable strategies
    - Message categorization by type and failure reason
    - Depth monitoring with alerts
    - Metrics tracking
    - Periodic cleanup of old messages
    """

    def __init__(
        self,
        max_queue_size: int = 10000,
        max_retention_hours: int = 24,
        retry_interval_seconds: float = 10.0,
        cleanup_interval_seconds: float = 300.0,  # 5 minutes
        depth_alert_threshold: int = 1000,
    ):
        """
        Initialize DLQ.

        Args:
            max_queue_size: Maximum messages to keep in queue
            max_retention_hours: How long to keep messages before discarding
            retry_interval_seconds: How often to check for retryable messages
            cleanup_interval_seconds: How often to clean up old messages
            depth_alert_threshold: Queue depth that triggers alerts
        """
        self.max_queue_size = max_queue_size
        self.max_retention_hours = max_retention_hours
        self.retry_interval_seconds = retry_interval_seconds
        self.cleanup_interval_seconds = cleanup_interval_seconds
        self.depth_alert_threshold = depth_alert_threshold

        # Main queue - using deque for efficient FIFO operations
        self._queue: Deque[FailedMessage] = deque(maxlen=max_queue_size)

        # Permanent failures (exhausted retries)
        self._permanent_failures: Deque[FailedMessage] = deque(maxlen=1000)

        # Message processors by type
        self._processors: Dict[MessageType, List[MessageProcessor]] = defaultdict(list)

        # Metrics
        self._metrics = DLQMetrics()

        # Alert callbacks
        self._alert_callbacks: List[Callable[[str, Dict[str, Any]], Awaitable[None]]] = []

        # Running flag
        self._running = False
        self._retry_task: Optional[asyncio.Task] = None
        self._cleanup_task: Optional[asyncio.Task] = None

        # Lock for thread-safe operations
        self._lock = asyncio.Lock()

    def register_processor(self, processor: MessageProcessor, message_types: List[MessageType]) -> None:
        """Register a message processor for specific types"""
        for msg_type in message_types:
            self._processors[msg_type].append(processor)
            logger.debug(f"Registered processor for {msg_type.value}")

    def register_alert_callback(
        self,
        callback: Callable[[str, Dict[str, Any]], Awaitable[None]]
    ) -> None:
        """Register callback for queue depth alerts"""
        self._alert_callbacks.append(callback)

    async def enqueue(
        self,
        message_type: MessageType,
        payload: Dict[str, Any],
        failure_reason: FailureReason,
        error_message: str,
        retry_strategy: RetryStrategy = RetryStrategy.EXPONENTIAL,
        max_retries: int = 3,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Add a failed message to the DLQ.

        Returns:
            Message ID
        """
        async with self._lock:
            message = FailedMessage(
                message_type=message_type,
                payload=payload,
                failure_reason=failure_reason,
                error_message=error_message,
                retry_strategy=retry_strategy,
                max_retries=max_retries,
                metadata=metadata or {}
            )

            # Calculate initial retry time
            if retry_strategy != RetryStrategy.NONE:
                message.calculate_next_retry()

            # Check if queue is at capacity
            if len(self._queue) >= self.max_queue_size:
                # Remove oldest message
                removed = self._queue.popleft()
                logger.warning(
                    f"DLQ at capacity, dropped oldest message: "
                    f"{removed.message_type.value} (id: {removed.id})"
                )

            self._queue.append(message)

            # Update metrics
            self._metrics.total_failures += 1
            self._metrics.failures_by_type[message_type.value] += 1
            self._metrics.failures_by_reason[failure_reason.value] += 1
            self._metrics.current_queue_depth = len(self._queue)
            self._metrics.max_queue_depth_seen = max(
                self._metrics.max_queue_depth_seen,
                len(self._queue)
            )

            logger.info(
                f"Enqueued failed message: {message_type.value} "
                f"(reason: {failure_reason.value}, id: {message.id})"
            )

            # Check for depth alerts
            await self._check_depth_alerts()

            return message.id

    async def _retry_worker(self) -> None:
        """Background worker that retries failed messages"""
        logger.info("DLQ retry worker started")

        while self._running:
            try:
                await asyncio.sleep(self.retry_interval_seconds)

                async with self._lock:
                    # Find messages ready for retry
                    retryable = [
                        msg for msg in self._queue
                        if msg.is_ready_for_retry()
                    ]

                if not retryable:
                    continue

                logger.debug(f"Found {len(retryable)} messages to retry")

                # Process retries (without lock to avoid blocking)
                for message in retryable:
                    await self._retry_message(message)

            except Exception as e:
                logger.error(f"Error in retry worker: {e}")

    async def _retry_message(self, message: FailedMessage) -> None:
        """Attempt to retry a failed message"""
        processors = self._processors.get(message.message_type, [])

        if not processors:
            logger.warning(
                f"No processors registered for {message.message_type.value}, "
                f"moving to permanent failures"
            )
            await self._mark_permanent_failure(message)
            return

        # Try each processor
        success = False
        for processor in processors:
            if not processor.can_process(message.message_type):
                continue

            try:
                logger.debug(
                    f"Retrying message {message.id} (attempt {message.retry_count + 1})"
                )

                success = await processor.process(message)

                if success:
                    logger.info(f"Successfully retried message {message.id}")
                    break

            except Exception as e:
                logger.error(f"Error retrying message {message.id}: {e}")

        async with self._lock:
            if success:
                # Remove from queue
                try:
                    self._queue.remove(message)
                    self._metrics.total_successes += 1
                    self._metrics.total_retries += message.retry_count + 1
                    self._metrics.current_queue_depth = len(self._queue)
                except ValueError:
                    pass  # Already removed
            else:
                # Increment retry count
                message.retry_count += 1
                self._metrics.total_retries += 1

                if message.retry_count >= message.max_retries:
                    # Max retries exhausted
                    await self._mark_permanent_failure(message)
                else:
                    # Calculate next retry
                    message.calculate_next_retry()
                    logger.debug(
                        f"Message {message.id} will retry at {message.next_retry_at}"
                    )

    async def _mark_permanent_failure(self, message: FailedMessage) -> None:
        """Move message to permanent failures"""
        try:
            self._queue.remove(message)
        except ValueError:
            pass  # Already removed

        self._permanent_failures.append(message)
        self._metrics.total_permanent_failures += 1
        self._metrics.current_queue_depth = len(self._queue)

        logger.warning(
            f"Message {message.id} moved to permanent failures after "
            f"{message.retry_count} retries"
        )

        # Alert on permanent failure
        await self._send_alert(
            "permanent_failure",
            {
                "message_id": message.id,
                "message_type": message.message_type.value,
                "failure_reason": message.failure_reason.value,
                "retry_count": message.retry_count,
                "error": message.error_message
            }
        )

    async def _cleanup_worker(self) -> None:
        """Background worker that cleans up old messages"""
        logger.info("DLQ cleanup worker started")

        while self._running:
            try:
                await asyncio.sleep(self.cleanup_interval_seconds)

                cutoff = datetime.utcnow() - timedelta(hours=self.max_retention_hours)

                async with self._lock:
                    # Remove old messages from queue
                    initial_size = len(self._queue)
                    self._queue = deque(
                        (msg for msg in self._queue if msg.failed_at > cutoff),
                        maxlen=self.max_queue_size
                    )
                    removed_count = initial_size - len(self._queue)

                    if removed_count > 0:
                        logger.info(f"Cleaned up {removed_count} old messages from DLQ")
                        self._metrics.current_queue_depth = len(self._queue)

                    # Clean up old permanent failures
                    initial_perm_size = len(self._permanent_failures)
                    self._permanent_failures = deque(
                        (msg for msg in self._permanent_failures if msg.failed_at > cutoff),
                        maxlen=1000
                    )
                    removed_perm = initial_perm_size - len(self._permanent_failures)

                    if removed_perm > 0:
                        logger.info(
                            f"Cleaned up {removed_perm} old permanent failures"
                        )

            except Exception as e:
                logger.error(f"Error in cleanup worker: {e}")

    async def _check_depth_alerts(self) -> None:
        """Check if queue depth exceeds threshold and send alerts"""
        if len(self._queue) >= self.depth_alert_threshold:
            await self._send_alert(
                "high_queue_depth",
                {
                    "current_depth": len(self._queue),
                    "threshold": self.depth_alert_threshold,
                    "max_size": self.max_queue_size,
                    "permanent_failures": len(self._permanent_failures)
                }
            )

    async def _send_alert(self, alert_type: str, data: Dict[str, Any]) -> None:
        """Send alert via registered callbacks"""
        for callback in self._alert_callbacks:
            try:
                await callback(alert_type, data)
            except Exception as e:
                logger.error(f"Error in alert callback: {e}")

    async def start(self) -> None:
        """Start the DLQ background workers"""
        if self._running:
            logger.warning("DLQ already running")
            return

        self._running = True
        self._retry_task = asyncio.create_task(self._retry_worker())
        self._cleanup_task = asyncio.create_task(self._cleanup_worker())
        logger.info("DLQ started")

    async def stop(self) -> None:
        """Stop the DLQ background workers"""
        if not self._running:
            return

        logger.info("Stopping DLQ")
        self._running = False

        if self._retry_task:
            self._retry_task.cancel()
            try:
                await self._retry_task
            except asyncio.CancelledError:
                pass

        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass

        logger.info("DLQ stopped")

    def get_metrics(self) -> DLQMetrics:
        """Get current metrics"""
        # Update avg retry count
        if self._metrics.total_retries > 0:
            total_messages = (
                self._metrics.total_successes +
                self._metrics.total_permanent_failures
            )
            if total_messages > 0:
                self._metrics.avg_retry_count = (
                    self._metrics.total_retries / total_messages
                )

        return self._metrics

    def get_queue_snapshot(self) -> List[Dict[str, Any]]:
        """Get snapshot of current queue"""
        return [msg.to_dict() for msg in list(self._queue)]

    def get_permanent_failures(self) -> List[Dict[str, Any]]:
        """Get snapshot of permanent failures"""
        return [msg.to_dict() for msg in list(self._permanent_failures)]

    async def replay_message(self, message_id: str) -> bool:
        """
        Manually replay a message from permanent failures.

        Returns:
            True if replayed successfully
        """
        async with self._lock:
            # Find message in permanent failures
            message = None
            for msg in self._permanent_failures:
                if msg.id == message_id:
                    message = msg
                    break

            if not message:
                logger.warning(f"Message {message_id} not found in permanent failures")
                return False

            # Reset retry count and move back to queue
            message.retry_count = 0
            message.calculate_next_retry()

            try:
                self._permanent_failures.remove(message)
                self._queue.append(message)
                self._metrics.current_queue_depth = len(self._queue)
                logger.info(f"Replaying message {message_id}")
                return True
            except Exception as e:
                logger.error(f"Error replaying message {message_id}: {e}")
                return False


# Singleton instance
_dlq: Optional[DeadLetterQueue] = None


def get_dlq() -> DeadLetterQueue:
    """Get global DLQ instance"""
    global _dlq
    if not _dlq:
        _dlq = DeadLetterQueue()
    return _dlq


def set_dlq(dlq: DeadLetterQueue) -> None:
    """Set global DLQ instance (for testing)"""
    global _dlq
    _dlq = dlq
