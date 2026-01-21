"""
Tests for Dead Letter Queue system.

Covers:
- Message enqueueing
- Retry mechanisms
- Exponential backoff
- Permanent failures
- Queue depth monitoring
- Metrics tracking
"""

import asyncio
import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

from core.messaging.dead_letter_queue import (
    DeadLetterQueue,
    FailedMessage,
    MessageType,
    FailureReason,
    RetryStrategy,
    MessageProcessor,
    DLQMetrics
)


class MockProcessor(MessageProcessor):
    """Mock processor for testing"""

    def __init__(self, should_succeed: bool = True):
        self.should_succeed = should_succeed
        self.process_calls = []

    async def process(self, message: FailedMessage) -> bool:
        self.process_calls.append(message.id)
        await asyncio.sleep(0.01)  # Simulate work
        return self.should_succeed

    def can_process(self, message_type: MessageType) -> bool:
        return message_type == MessageType.TRADE_EXECUTION


class TestFailedMessage:
    """Test FailedMessage dataclass"""

    def test_message_creation(self):
        """Test creating a failed message"""
        message = FailedMessage(
            message_type=MessageType.TRADE_EXECUTION,
            payload={"token": "SOL"},
            failure_reason=FailureReason.TIMEOUT,
            error_message="Connection timeout",
            max_retries=3,
            retry_strategy=RetryStrategy.EXPONENTIAL
        )

        assert message.message_type == MessageType.TRADE_EXECUTION
        assert message.payload["token"] == "SOL"
        assert message.failure_reason == FailureReason.TIMEOUT
        assert message.retry_count == 0
        assert message.max_retries == 3

    def test_should_retry_logic(self):
        """Test retry logic"""
        # Should retry (under max retries)
        message = FailedMessage(
            message_type=MessageType.ALERT_DELIVERY,
            failure_reason=FailureReason.NETWORK_ERROR,
            retry_count=1,
            max_retries=3,
            retry_strategy=RetryStrategy.EXPONENTIAL
        )
        message.calculate_next_retry()
        assert message.should_retry()

        # Should not retry (max retries exhausted)
        message.retry_count = 3
        assert not message.should_retry()

        # Should not retry (NONE strategy)
        message.retry_count = 0
        message.retry_strategy = RetryStrategy.NONE
        assert not message.should_retry()

    def test_exponential_backoff(self):
        """Test exponential backoff calculation"""
        message = FailedMessage(
            message_type=MessageType.WEBHOOK,
            failure_reason=FailureReason.TIMEOUT,
            retry_strategy=RetryStrategy.EXPONENTIAL
        )

        # First retry: 2^0 = 1 second
        message.calculate_next_retry()
        assert message.next_retry_at is not None
        delay1 = (message.next_retry_at - datetime.utcnow()).total_seconds()
        assert 0.5 < delay1 < 2

        # Second retry: 2^1 = 2 seconds
        message.retry_count = 1
        message.calculate_next_retry()
        delay2 = (message.next_retry_at - datetime.utcnow()).total_seconds()
        assert 1.5 < delay2 < 3

        # Third retry: 2^2 = 4 seconds
        message.retry_count = 2
        message.calculate_next_retry()
        delay3 = (message.next_retry_at - datetime.utcnow()).total_seconds()
        assert 3.5 < delay3 < 5

    def test_linear_backoff(self):
        """Test linear backoff calculation"""
        message = FailedMessage(
            message_type=MessageType.API_CALLBACK,
            failure_reason=FailureReason.RATE_LIMIT,
            retry_strategy=RetryStrategy.LINEAR
        )

        # First retry: 5 * 1 = 5 seconds
        message.calculate_next_retry()
        delay1 = (message.next_retry_at - datetime.utcnow()).total_seconds()
        assert 4.5 < delay1 < 6

        # Second retry: 5 * 2 = 10 seconds
        message.retry_count = 1
        message.calculate_next_retry()
        delay2 = (message.next_retry_at - datetime.utcnow()).total_seconds()
        assert 9.5 < delay2 < 11

    def test_fixed_backoff(self):
        """Test fixed backoff calculation"""
        message = FailedMessage(
            message_type=MessageType.NOTIFICATION,
            failure_reason=FailureReason.SERVICE_UNAVAILABLE,
            retry_strategy=RetryStrategy.FIXED
        )

        # All retries: 30 seconds
        for i in range(3):
            message.retry_count = i
            message.calculate_next_retry()
            delay = (message.next_retry_at - datetime.utcnow()).total_seconds()
            assert 29 < delay < 31

    def test_to_dict(self):
        """Test serialization to dict"""
        message = FailedMessage(
            message_type=MessageType.TRADE_EXECUTION,
            payload={"amount": 100},
            failure_reason=FailureReason.VALIDATION_ERROR,
            error_message="Invalid amount",
            metadata={"user_id": "123"}
        )

        data = message.to_dict()
        assert data["message_type"] == "trade_execution"
        assert data["payload"]["amount"] == 100
        assert data["failure_reason"] == "validation_error"
        assert data["error_message"] == "Invalid amount"
        assert data["metadata"]["user_id"] == "123"


class TestDeadLetterQueue:
    """Test DeadLetterQueue"""

    @pytest.fixture
    def dlq(self):
        """Create DLQ instance for testing"""
        return DeadLetterQueue(
            max_queue_size=100,
            max_retention_hours=1,
            retry_interval_seconds=0.1,  # Fast for testing
            cleanup_interval_seconds=0.5,
            depth_alert_threshold=10
        )

    @pytest.mark.asyncio
    async def test_enqueue_message(self, dlq):
        """Test enqueueing a failed message"""
        message_id = await dlq.enqueue(
            message_type=MessageType.TRADE_EXECUTION,
            payload={"token": "SOL", "amount": 100},
            failure_reason=FailureReason.TIMEOUT,
            error_message="Connection timeout"
        )

        assert message_id is not None
        assert len(dlq._queue) == 1

        metrics = dlq.get_metrics()
        assert metrics.total_failures == 1
        assert metrics.current_queue_depth == 1
        assert metrics.failures_by_type["trade_execution"] == 1
        assert metrics.failures_by_reason["timeout"] == 1

    @pytest.mark.asyncio
    async def test_register_and_retry_success(self, dlq):
        """Test successful retry with processor"""
        # Register processor
        processor = MockProcessor(should_succeed=True)
        dlq.register_processor(processor, [MessageType.TRADE_EXECUTION])

        # Start DLQ
        await dlq.start()

        # Enqueue message - use EXPONENTIAL strategy (1 sec delay) instead of FIXED (30 sec)
        message_id = await dlq.enqueue(
            message_type=MessageType.TRADE_EXECUTION,
            payload={"token": "SOL"},
            failure_reason=FailureReason.NETWORK_ERROR,
            error_message="Network error",
            retry_strategy=RetryStrategy.EXPONENTIAL,
            max_retries=3
        )

        # Wait for retry (EXPONENTIAL first retry is 2^0 = 1 second + processing time)
        await asyncio.sleep(1.5)

        # Check processor was called
        assert message_id in processor.process_calls

        # Message should be removed from queue
        assert len(dlq._queue) == 0

        # Metrics should reflect success
        metrics = dlq.get_metrics()
        assert metrics.total_successes == 1

        await dlq.stop()

    @pytest.mark.asyncio
    async def test_retry_failure_then_permanent(self, dlq):
        """Test retry failures leading to permanent failure"""
        # Register processor that always fails
        processor = MockProcessor(should_succeed=False)
        dlq.register_processor(processor, [MessageType.TRADE_EXECUTION])

        await dlq.start()

        # Enqueue message with max 2 retries - use EXPONENTIAL (1s, 2s delays)
        message_id = await dlq.enqueue(
            message_type=MessageType.TRADE_EXECUTION,
            payload={"token": "BTC"},
            failure_reason=FailureReason.TIMEOUT,
            error_message="Timeout",
            retry_strategy=RetryStrategy.EXPONENTIAL,
            max_retries=2
        )

        # Wait for retries to exhaust (1s + 2s delays + processing + buffer)
        await asyncio.sleep(5.0)

        # Should be in permanent failures
        assert len(dlq._permanent_failures) == 1
        assert dlq._permanent_failures[0].id == message_id

        # Should not be in main queue
        assert len(dlq._queue) == 0

        # Metrics should reflect permanent failure
        metrics = dlq.get_metrics()
        assert metrics.total_permanent_failures == 1
        assert metrics.total_retries >= 2

        await dlq.stop()

    @pytest.mark.asyncio
    async def test_queue_capacity_limit(self, dlq):
        """Test queue respects max capacity"""
        dlq.max_queue_size = 5

        # Enqueue 10 messages (exceeds capacity)
        for i in range(10):
            await dlq.enqueue(
                message_type=MessageType.ALERT_DELIVERY,
                payload={"id": i},
                failure_reason=FailureReason.NETWORK_ERROR,
                error_message="Error",
                retry_strategy=RetryStrategy.NONE  # Don't retry
            )

        # Queue should be at max capacity
        assert len(dlq._queue) == 5

        # Oldest messages should be dropped
        messages = list(dlq._queue)
        assert messages[0].payload["id"] == 5  # First message is #5 (0-4 dropped)

    @pytest.mark.asyncio
    async def test_depth_alerts(self, dlq):
        """Test queue depth alerts"""
        alert_calls = []

        async def alert_callback(alert_type: str, data: dict):
            alert_calls.append((alert_type, data))

        dlq.register_alert_callback(alert_callback)

        # Enqueue messages to exceed threshold (10)
        for i in range(15):
            await dlq.enqueue(
                message_type=MessageType.WEBHOOK,
                payload={"id": i},
                failure_reason=FailureReason.TIMEOUT,
                error_message="Timeout"
            )

        # Should have triggered depth alert
        assert any(alert_type == "high_queue_depth" for alert_type, _ in alert_calls)

    @pytest.mark.asyncio
    async def test_cleanup_old_messages(self, dlq):
        """Test cleanup of old messages"""
        dlq.max_retention_hours = 0  # Expire immediately for testing

        await dlq.start()

        # Enqueue message
        await dlq.enqueue(
            message_type=MessageType.NOTIFICATION,
            payload={"test": True},
            failure_reason=FailureReason.TIMEOUT,
            error_message="Timeout",
            retry_strategy=RetryStrategy.NONE
        )

        assert len(dlq._queue) == 1

        # Wait for cleanup
        await asyncio.sleep(1.0)

        # Message should be cleaned up
        assert len(dlq._queue) == 0

        await dlq.stop()

    @pytest.mark.asyncio
    async def test_replay_message(self, dlq):
        """Test manually replaying a message from permanent failures"""
        # Add message to permanent failures
        message = FailedMessage(
            message_type=MessageType.API_CALLBACK,
            payload={"url": "https://example.com"},
            failure_reason=FailureReason.TIMEOUT,
            error_message="Timeout",
            retry_count=3,
            max_retries=3
        )
        dlq._permanent_failures.append(message)

        # Replay message
        success = await dlq.replay_message(message.id)
        assert success

        # Should be back in main queue with reset retry count
        assert len(dlq._queue) == 1
        assert len(dlq._permanent_failures) == 0
        assert dlq._queue[0].retry_count == 0

    @pytest.mark.asyncio
    async def test_metrics_calculation(self, dlq):
        """Test metrics calculation"""
        processor = MockProcessor(should_succeed=True)
        dlq.register_processor(processor, [MessageType.TRADE_EXECUTION])

        await dlq.start()

        # Enqueue and process some messages - use EXPONENTIAL (1 sec delay)
        for i in range(5):
            await dlq.enqueue(
                message_type=MessageType.TRADE_EXECUTION,
                payload={"id": i},
                failure_reason=FailureReason.TIMEOUT,
                error_message="Timeout",
                retry_strategy=RetryStrategy.EXPONENTIAL,
                max_retries=2
            )

        # Wait for processing (EXPONENTIAL first retry is 1s + processing time)
        await asyncio.sleep(2.0)

        metrics = dlq.get_metrics()
        assert metrics.total_failures == 5
        assert metrics.total_successes > 0
        assert metrics.current_queue_depth >= 0

        await dlq.stop()

    @pytest.mark.asyncio
    async def test_get_queue_snapshot(self, dlq):
        """Test getting queue snapshot"""
        # Enqueue some messages
        for i in range(3):
            await dlq.enqueue(
                message_type=MessageType.ALERT_DELIVERY,
                payload={"id": i},
                failure_reason=FailureReason.NETWORK_ERROR,
                error_message="Error"
            )

        snapshot = dlq.get_queue_snapshot()
        assert len(snapshot) == 3
        assert all("message_type" in msg for msg in snapshot)
        assert all("payload" in msg for msg in snapshot)

    @pytest.mark.asyncio
    async def test_get_permanent_failures(self, dlq):
        """Test getting permanent failures snapshot"""
        # Add to permanent failures
        for i in range(2):
            message = FailedMessage(
                message_type=MessageType.WEBHOOK,
                payload={"id": i},
                failure_reason=FailureReason.TIMEOUT,
                error_message="Timeout"
            )
            dlq._permanent_failures.append(message)

        snapshot = dlq.get_permanent_failures()
        assert len(snapshot) == 2
        assert all("message_type" in msg for msg in snapshot)

    @pytest.mark.asyncio
    async def test_no_processor_registered(self, dlq):
        """Test behavior when no processor is registered"""
        await dlq.start()

        # Enqueue message without processor - use EXPONENTIAL (1s delay) for test speed
        await dlq.enqueue(
            message_type=MessageType.OTHER,
            payload={"test": True},
            failure_reason=FailureReason.UNKNOWN,
            error_message="Unknown error",
            retry_strategy=RetryStrategy.EXPONENTIAL,
            max_retries=1
        )

        # Wait for retry attempt (1s delay + 2s for next attempt + processing)
        await asyncio.sleep(4.0)

        # Should move to permanent failures
        assert len(dlq._permanent_failures) == 1

        await dlq.stop()


class TestDLQMetrics:
    """Test DLQMetrics dataclass"""

    def test_metrics_initialization(self):
        """Test metrics initialization"""
        metrics = DLQMetrics()
        assert metrics.total_failures == 0
        assert metrics.total_retries == 0
        assert metrics.total_successes == 0
        assert metrics.current_queue_depth == 0

    def test_metrics_to_dict(self):
        """Test metrics serialization"""
        metrics = DLQMetrics(
            total_failures=10,
            total_retries=5,
            total_successes=3,
            total_permanent_failures=2,
            avg_retry_count=1.67,
            current_queue_depth=5,
            max_queue_depth_seen=8
        )

        data = metrics.to_dict()
        assert data["total_failures"] == 10
        assert data["total_retries"] == 5
        assert data["total_successes"] == 3
        assert data["avg_retry_count"] == 1.67
