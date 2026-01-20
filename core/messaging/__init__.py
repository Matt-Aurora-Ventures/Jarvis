"""
Messaging module with Dead Letter Queue support.

Provides:
- Dead letter queue for failed messages
- Retry mechanisms with exponential backoff
- Message processors for different failure types
- Monitoring and metrics
"""

from .dead_letter_queue import (
    DeadLetterQueue,
    FailedMessage,
    MessageType,
    FailureReason,
    RetryStrategy,
    DLQMetrics,
    MessageProcessor,
    get_dlq,
    set_dlq
)

from .processors import (
    TradeExecutionProcessor,
    AlertDeliveryProcessor,
    APICallbackProcessor,
    IncomingMessageProcessor,
    WebhookProcessor,
    NotificationProcessor
)

__all__ = [
    # Core DLQ
    "DeadLetterQueue",
    "FailedMessage",
    "MessageType",
    "FailureReason",
    "RetryStrategy",
    "DLQMetrics",
    "MessageProcessor",
    "get_dlq",
    "set_dlq",
    # Processors
    "TradeExecutionProcessor",
    "AlertDeliveryProcessor",
    "APICallbackProcessor",
    "IncomingMessageProcessor",
    "WebhookProcessor",
    "NotificationProcessor",
]
