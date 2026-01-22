"""
Inter-Bot Message Bus

Real-time communication system for bot components to share information.
Enables bots to:
- Broadcast insights to other bots
- Subscribe to specific message types
- Coordinate actions
- Share real-time data

Features:
- Async pub/sub pattern
- Message filtering by type/component
- Message history buffer
- Priority messaging
- Dead letter queue for failed deliveries
"""

import asyncio
import logging
from datetime import datetime
from typing import Dict, List, Optional, Callable, Any, Set
from dataclasses import dataclass, field
from enum import Enum
from collections import deque


logger = logging.getLogger("jarvis.message_bus")


class MessagePriority(Enum):
    """Message priority levels."""
    LOW = 0
    NORMAL = 1
    HIGH = 2
    CRITICAL = 3


class MessageType(Enum):
    """Types of messages that can be sent."""
    # Trading signals
    BUY_SIGNAL = "buy_signal"
    SELL_SIGNAL = "sell_signal"
    PRICE_ALERT = "price_alert"

    # Sentiment updates
    SENTIMENT_CHANGED = "sentiment_changed"
    MARKET_MOOD = "market_mood"

    # System events
    ERROR_DETECTED = "error_detected"
    PERFORMANCE_DEGRADED = "performance_degraded"
    HEALTH_CHECK = "health_check"

    # Learning/adaptation
    NEW_LEARNING = "new_learning"
    PARAMETER_ADJUSTED = "parameter_adjusted"
    STRATEGY_CHANGED = "strategy_changed"

    # Coordination
    REQUEST_PAUSE = "request_pause"
    REQUEST_RESUME = "request_resume"
    EMERGENCY_STOP = "emergency_stop"

    # User interactions
    USER_COMMAND = "user_command"
    USER_FEEDBACK = "user_feedback"


@dataclass
class Message:
    """A message in the bus."""
    id: str
    type: MessageType
    sender: str  # Component that sent the message
    data: Dict[str, Any]
    priority: MessagePriority = MessagePriority.NORMAL
    timestamp: datetime = field(default_factory=datetime.now)
    ttl: Optional[int] = None  # Time to live in seconds
    requires_ack: bool = False  # Requires acknowledgment

    def is_expired(self) -> bool:
        """Check if message has expired."""
        if self.ttl is None:
            return False
        age = (datetime.now() - self.timestamp).total_seconds()
        return age > self.ttl


@dataclass
class Subscription:
    """A subscription to message types."""
    subscriber: str  # Component name
    message_types: Set[MessageType]  # Types to listen for
    callback: Callable[[Message], None]  # Async callback function
    filter_func: Optional[Callable[[Message], bool]] = None  # Optional filter


class MessageBus:
    """
    Central message bus for inter-component communication.

    Thread-safe async pub/sub system.
    """

    def __init__(self, max_history: int = 1000):
        self.max_history = max_history

        self.subscriptions: List[Subscription] = []
        self.message_history: deque = deque(maxlen=max_history)
        self.dead_letter_queue: deque = deque(maxlen=100)

        self._lock = asyncio.Lock()
        self._message_count = 0

        # Statistics
        self.stats = {
            "total_messages": 0,
            "messages_by_type": {},
            "messages_by_component": {},
            "failed_deliveries": 0
        }

        logger.info("MessageBus initialized")

    async def publish(
        self,
        sender: str,
        message_type: MessageType,
        data: Dict[str, Any],
        priority: MessagePriority = MessagePriority.NORMAL,
        ttl: Optional[int] = None,
        requires_ack: bool = False
    ) -> str:
        """
        Publish a message to the bus.

        Returns message ID.
        """
        async with self._lock:
            import uuid
            message_id = str(uuid.uuid4())

            message = Message(
                id=message_id,
                type=message_type,
                sender=sender,
                data=data,
                priority=priority,
                timestamp=datetime.now(),
                ttl=ttl,
                requires_ack=requires_ack
            )

            # Add to history
            self.message_history.append(message)

            # Update stats
            self.stats["total_messages"] += 1
            self.stats["messages_by_type"][message_type.value] = \
                self.stats["messages_by_type"].get(message_type.value, 0) + 1
            self.stats["messages_by_component"][sender] = \
                self.stats["messages_by_component"].get(sender, 0) + 1

            logger.debug(f"[{sender}] Published {message_type.value}: {message_id}")

        # Deliver to subscribers (outside lock to avoid deadlock)
        await self._deliver_message(message)

        return message_id

    async def _deliver_message(self, message: Message):
        """Deliver message to all matching subscribers."""
        if message.is_expired():
            logger.warning(f"Message {message.id} expired before delivery")
            return

        delivery_tasks = []

        for subscription in self.subscriptions:
            # Check if subscriber is interested in this message type
            if message.type not in subscription.message_types:
                continue

            # Apply custom filter if provided
            if subscription.filter_func and not subscription.filter_func(message):
                continue

            # Don't deliver to sender (unless they specifically subscribed)
            if message.sender == subscription.subscriber:
                continue

            # Create delivery task
            task = asyncio.create_task(
                self._safe_delivery(subscription, message)
            )
            delivery_tasks.append(task)

        # Wait for all deliveries (with timeout for priority messages)
        if delivery_tasks:
            timeout = 5.0 if message.priority == MessagePriority.CRITICAL else 10.0
            try:
                await asyncio.wait_for(
                    asyncio.gather(*delivery_tasks, return_exceptions=True),
                    timeout=timeout
                )
            except asyncio.TimeoutError:
                logger.warning(f"Message {message.id} delivery timed out")

    async def _safe_delivery(self, subscription: Subscription, message: Message):
        """Safely deliver message to subscriber with error handling."""
        try:
            # Call subscriber's callback
            if asyncio.iscoroutinefunction(subscription.callback):
                await subscription.callback(message)
            else:
                subscription.callback(message)

            logger.debug(
                f"Delivered {message.type.value} to {subscription.subscriber}"
            )

        except Exception as e:
            logger.error(
                f"Failed to deliver {message.type.value} to {subscription.subscriber}: {e}"
            )
            self.stats["failed_deliveries"] += 1

            # Add to dead letter queue
            async with self._lock:
                self.dead_letter_queue.append({
                    "message": message,
                    "subscriber": subscription.subscriber,
                    "error": str(e),
                    "timestamp": datetime.now()
                })

    def subscribe(
        self,
        subscriber: str,
        message_types: List[MessageType],
        callback: Callable[[Message], None],
        filter_func: Optional[Callable[[Message], bool]] = None
    ):
        """
        Subscribe to message types.

        Args:
            subscriber: Name of subscribing component
            message_types: List of MessageType to subscribe to
            callback: Async function to call when message arrives
            filter_func: Optional function to filter messages (returns True to receive)
        """
        subscription = Subscription(
            subscriber=subscriber,
            message_types=set(message_types),
            callback=callback,
            filter_func=filter_func
        )

        self.subscriptions.append(subscription)

        logger.info(
            f"[{subscriber}] Subscribed to {len(message_types)} message types"
        )

    def unsubscribe(self, subscriber: str):
        """Remove all subscriptions for a subscriber."""
        initial_count = len(self.subscriptions)
        self.subscriptions = [
            s for s in self.subscriptions if s.subscriber != subscriber
        ]
        removed = initial_count - len(self.subscriptions)

        if removed > 0:
            logger.info(f"[{subscriber}] Unsubscribed ({removed} subscriptions removed)")

    async def get_recent_messages(
        self,
        message_type: Optional[MessageType] = None,
        sender: Optional[str] = None,
        limit: int = 100
    ) -> List[Message]:
        """Get recent messages from history."""
        async with self._lock:
            messages = list(self.message_history)

            # Filter
            if message_type:
                messages = [m for m in messages if m.type == message_type]
            if sender:
                messages = [m for m in messages if m.sender == sender]

            # Return most recent
            return messages[-limit:]

    def get_stats(self) -> Dict[str, Any]:
        """Get message bus statistics."""
        return {
            **self.stats,
            "active_subscriptions": len(self.subscriptions),
            "history_size": len(self.message_history),
            "dead_letters": len(self.dead_letter_queue)
        }


# Global message bus instance
_message_bus: Optional[MessageBus] = None


def get_message_bus() -> MessageBus:
    """Get the global message bus instance."""
    global _message_bus
    if _message_bus is None:
        _message_bus = MessageBus()
    return _message_bus
