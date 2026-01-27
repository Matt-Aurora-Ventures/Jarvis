"""
Webhook Management

Manage webhooks for real-time event delivery.

Prompts #61-64: Developer Webhooks
"""

import asyncio
import hashlib
import hmac
import logging
import os
import secrets
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional
import aiohttp
from aiohttp import ClientTimeout
import json

logger = logging.getLogger(__name__)


class WebhookEvent(str, Enum):
    """Webhook event types"""
    # Portfolio events
    POSITION_OPENED = "position.opened"
    POSITION_CLOSED = "position.closed"
    POSITION_UPDATED = "position.updated"

    # Trade events
    TRADE_EXECUTED = "trade.executed"
    TRADE_FAILED = "trade.failed"
    QUOTE_EXPIRED = "quote.expired"

    # Signal events
    SIGNAL_GENERATED = "signal.generated"
    SIGNAL_EXPIRED = "signal.expired"

    # Alert events
    ALERT_TRIGGERED = "alert.triggered"
    PRICE_ALERT = "alert.price"

    # Whale events
    WHALE_TRANSACTION = "whale.transaction"
    WHALE_PATTERN = "whale.pattern"

    # Staking events
    STAKE_DEPOSITED = "stake.deposited"
    STAKE_WITHDRAWN = "stake.withdrawn"
    REWARD_CLAIMED = "reward.claimed"

    # System events
    SYSTEM_STATUS = "system.status"


# Event categories for subscription
EVENT_CATEGORIES = {
    "portfolio": [
        WebhookEvent.POSITION_OPENED,
        WebhookEvent.POSITION_CLOSED,
        WebhookEvent.POSITION_UPDATED,
    ],
    "trades": [
        WebhookEvent.TRADE_EXECUTED,
        WebhookEvent.TRADE_FAILED,
        WebhookEvent.QUOTE_EXPIRED,
    ],
    "signals": [
        WebhookEvent.SIGNAL_GENERATED,
        WebhookEvent.SIGNAL_EXPIRED,
    ],
    "alerts": [
        WebhookEvent.ALERT_TRIGGERED,
        WebhookEvent.PRICE_ALERT,
    ],
    "whales": [
        WebhookEvent.WHALE_TRANSACTION,
        WebhookEvent.WHALE_PATTERN,
    ],
    "staking": [
        WebhookEvent.STAKE_DEPOSITED,
        WebhookEvent.STAKE_WITHDRAWN,
        WebhookEvent.REWARD_CLAIMED,
    ],
    "all": list(WebhookEvent),
}


@dataclass
class Webhook:
    """A webhook subscription"""
    webhook_id: str
    user_id: str
    url: str
    secret: str                 # For signing deliveries
    events: List[WebhookEvent]  # Subscribed events
    is_active: bool = True
    created_at: datetime = field(default_factory=datetime.utcnow)
    last_delivery: Optional[datetime] = None
    consecutive_failures: int = 0
    total_deliveries: int = 0
    total_failures: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def is_healthy(self) -> bool:
        return self.is_active and self.consecutive_failures < 5

    def to_dict(self) -> Dict[str, Any]:
        return {
            "webhook_id": self.webhook_id,
            "url": self.url,
            "events": [e.value for e in self.events],
            "is_active": self.is_active,
            "is_healthy": self.is_healthy,
            "created_at": self.created_at.isoformat(),
            "last_delivery": (
                self.last_delivery.isoformat() if self.last_delivery else None
            ),
            "consecutive_failures": self.consecutive_failures,
            "total_deliveries": self.total_deliveries,
            "total_failures": self.total_failures
        }


@dataclass
class WebhookDelivery:
    """A webhook delivery attempt"""
    delivery_id: str
    webhook_id: str
    event: WebhookEvent
    payload: Dict[str, Any]
    status_code: Optional[int] = None
    response_body: Optional[str] = None
    error: Optional[str] = None
    attempt: int = 1
    timestamp: datetime = field(default_factory=datetime.utcnow)
    duration_ms: float = 0.0

    @property
    def is_success(self) -> bool:
        return self.status_code is not None and 200 <= self.status_code < 300


class WebhookManager:
    """
    Manages webhook subscriptions and deliveries.

    Features:
    - Event-based subscriptions
    - Signed payload delivery
    - Automatic retry with backoff
    - Health monitoring
    """

    MAX_RETRIES = 3
    RETRY_DELAYS = [1, 5, 30]  # seconds
    DELIVERY_TIMEOUT = 10  # seconds

    def __init__(self, storage_path: str = "data/webhooks.json"):
        self.storage_path = storage_path
        self._webhooks: Dict[str, Webhook] = {}
        self._deliveries: List[WebhookDelivery] = []
        self._session: Optional[aiohttp.ClientSession] = None
        self._load()

    def _load(self):
        """Load webhooks from storage"""
        try:
            if os.path.exists(self.storage_path):
                with open(self.storage_path, "r") as f:
                    data = json.load(f)
                for item in data.get("webhooks", []):
                    webhook = Webhook(
                        webhook_id=item["webhook_id"],
                        user_id=item["user_id"],
                        url=item["url"],
                        secret=item["secret"],
                        events=[WebhookEvent(e) for e in item.get("events", [])],
                        is_active=item.get("is_active", True),
                        created_at=datetime.fromisoformat(item["created_at"]),
                        consecutive_failures=item.get("consecutive_failures", 0),
                        total_deliveries=item.get("total_deliveries", 0),
                        total_failures=item.get("total_failures", 0)
                    )
                    self._webhooks[webhook.webhook_id] = webhook
        except Exception as e:
            logger.error(f"Failed to load webhooks: {e}")

    def _save(self):
        """Save webhooks to storage"""
        try:
            os.makedirs(os.path.dirname(self.storage_path), exist_ok=True)
            data = {
                "webhooks": [
                    {
                        "webhook_id": w.webhook_id,
                        "user_id": w.user_id,
                        "url": w.url,
                        "secret": w.secret,
                        "events": [e.value for e in w.events],
                        "is_active": w.is_active,
                        "created_at": w.created_at.isoformat(),
                        "consecutive_failures": w.consecutive_failures,
                        "total_deliveries": w.total_deliveries,
                        "total_failures": w.total_failures
                    }
                    for w in self._webhooks.values()
                ]
            }
            with open(self.storage_path, "w") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save webhooks: {e}")

    async def start(self):
        """Initialize the manager"""
        # Configure timeouts: 60s total, 30s connect (for webhook delivery)
        timeout = ClientTimeout(total=60, connect=30)
        self._session = aiohttp.ClientSession(timeout=timeout)
        logger.info("Webhook manager started")

    async def stop(self):
        """Shutdown the manager"""
        if self._session:
            await self._session.close()
        logger.info("Webhook manager stopped")

    # =========================================================================
    # WEBHOOK MANAGEMENT
    # =========================================================================

    async def create_webhook(
        self,
        user_id: str,
        url: str,
        events: List[WebhookEvent],
        metadata: Optional[Dict] = None
    ) -> Webhook:
        """Create a new webhook subscription"""
        webhook_id = f"wh_{secrets.token_hex(12)}"
        secret = secrets.token_urlsafe(32)

        webhook = Webhook(
            webhook_id=webhook_id,
            user_id=user_id,
            url=url,
            secret=secret,
            events=events,
            metadata=metadata or {}
        )

        self._webhooks[webhook_id] = webhook
        self._save()

        logger.info(f"Created webhook {webhook_id} for user {user_id}")
        return webhook

    async def update_webhook(
        self,
        webhook_id: str,
        url: Optional[str] = None,
        events: Optional[List[WebhookEvent]] = None,
        is_active: Optional[bool] = None
    ) -> Optional[Webhook]:
        """Update a webhook"""
        webhook = self._webhooks.get(webhook_id)
        if not webhook:
            return None

        if url:
            webhook.url = url
        if events:
            webhook.events = events
        if is_active is not None:
            webhook.is_active = is_active

        self._save()
        return webhook

    async def delete_webhook(self, webhook_id: str):
        """Delete a webhook"""
        if webhook_id in self._webhooks:
            del self._webhooks[webhook_id]
            self._save()
            logger.info(f"Deleted webhook {webhook_id}")

    async def get_webhook(self, webhook_id: str) -> Optional[Webhook]:
        """Get a webhook by ID"""
        return self._webhooks.get(webhook_id)

    async def get_user_webhooks(self, user_id: str) -> List[Webhook]:
        """Get all webhooks for a user"""
        return [w for w in self._webhooks.values() if w.user_id == user_id]

    async def rotate_secret(self, webhook_id: str) -> Optional[str]:
        """Rotate webhook secret"""
        webhook = self._webhooks.get(webhook_id)
        if not webhook:
            return None

        webhook.secret = secrets.token_urlsafe(32)
        self._save()
        return webhook.secret

    # =========================================================================
    # EVENT DELIVERY
    # =========================================================================

    async def dispatch_event(
        self,
        event: WebhookEvent,
        payload: Dict[str, Any],
        user_id: Optional[str] = None
    ):
        """Dispatch an event to all subscribed webhooks"""
        # Find matching webhooks
        webhooks = [
            w for w in self._webhooks.values()
            if event in w.events and w.is_healthy
            and (user_id is None or w.user_id == user_id)
        ]

        if not webhooks:
            return

        # Deliver to all webhooks
        tasks = [
            self._deliver_to_webhook(webhook, event, payload)
            for webhook in webhooks
        ]
        await asyncio.gather(*tasks, return_exceptions=True)

    async def _deliver_to_webhook(
        self,
        webhook: Webhook,
        event: WebhookEvent,
        payload: Dict[str, Any]
    ):
        """Deliver event to a single webhook with retry"""
        if not self._session:
            await self.start()

        delivery_id = f"del_{secrets.token_hex(8)}"

        full_payload = {
            "event": event.value,
            "timestamp": datetime.utcnow().isoformat(),
            "delivery_id": delivery_id,
            "data": payload
        }

        for attempt in range(1, self.MAX_RETRIES + 1):
            delivery = WebhookDelivery(
                delivery_id=delivery_id,
                webhook_id=webhook.webhook_id,
                event=event,
                payload=full_payload,
                attempt=attempt
            )

            try:
                # Sign payload
                payload_str = json.dumps(full_payload, sort_keys=True)
                timestamp = str(int(time.time()))
                signature = self._sign_payload(payload_str, timestamp, webhook.secret)

                # Make request
                start = time.time()
                async with self._session.post(
                    webhook.url,
                    json=full_payload,
                    headers={
                        "Content-Type": "application/json",
                        "X-Webhook-Signature": signature,
                        "X-Webhook-Timestamp": timestamp,
                        "X-Webhook-Event": event.value,
                        "X-Delivery-Id": delivery_id
                    },
                    timeout=aiohttp.ClientTimeout(total=self.DELIVERY_TIMEOUT)
                ) as response:
                    delivery.duration_ms = (time.time() - start) * 1000
                    delivery.status_code = response.status

                    try:
                        delivery.response_body = await response.text()
                    except Exception:
                        pass

                    if delivery.is_success:
                        await self._on_delivery_success(webhook, delivery)
                        return
                    else:
                        await self._on_delivery_failure(webhook, delivery)

            except Exception as e:
                delivery.error = str(e)
                delivery.duration_ms = (time.time() - start) * 1000
                await self._on_delivery_failure(webhook, delivery)

            # Retry with delay
            if attempt < self.MAX_RETRIES:
                delay = self.RETRY_DELAYS[attempt - 1]
                await asyncio.sleep(delay)

    def _sign_payload(self, payload: str, timestamp: str, secret: str) -> str:
        """Sign a webhook payload"""
        message = f"{timestamp}.{payload}"
        return hmac.new(
            secret.encode(),
            message.encode(),
            hashlib.sha256
        ).hexdigest()

    async def _on_delivery_success(
        self,
        webhook: Webhook,
        delivery: WebhookDelivery
    ):
        """Handle successful delivery"""
        webhook.consecutive_failures = 0
        webhook.total_deliveries += 1
        webhook.last_delivery = datetime.utcnow()
        self._deliveries.append(delivery)
        self._save()

        logger.debug(
            f"Webhook {webhook.webhook_id} delivery successful: "
            f"{delivery.event.value}"
        )

    async def _on_delivery_failure(
        self,
        webhook: Webhook,
        delivery: WebhookDelivery
    ):
        """Handle failed delivery"""
        webhook.consecutive_failures += 1
        webhook.total_failures += 1
        self._deliveries.append(delivery)
        self._save()

        logger.warning(
            f"Webhook {webhook.webhook_id} delivery failed "
            f"(attempt {delivery.attempt}): {delivery.error or delivery.status_code}"
        )

        # Disable after too many failures
        if webhook.consecutive_failures >= 10:
            webhook.is_active = False
            logger.error(
                f"Webhook {webhook.webhook_id} disabled due to repeated failures"
            )

    # =========================================================================
    # VERIFICATION
    # =========================================================================

    def verify_signature(
        self,
        payload: str,
        signature: str,
        timestamp: str,
        secret: str,
        tolerance_seconds: int = 300
    ) -> bool:
        """Verify a webhook signature (for receivers)"""
        # Check timestamp
        try:
            ts = int(timestamp)
            if abs(time.time() - ts) > tolerance_seconds:
                return False
        except ValueError:
            return False

        # Verify signature
        expected = self._sign_payload(payload, timestamp, secret)
        return hmac.compare_digest(signature, expected)

    # =========================================================================
    # DELIVERY HISTORY
    # =========================================================================

    async def get_deliveries(
        self,
        webhook_id: str,
        limit: int = 100
    ) -> List[WebhookDelivery]:
        """Get recent deliveries for a webhook"""
        deliveries = [
            d for d in self._deliveries
            if d.webhook_id == webhook_id
        ]
        return sorted(deliveries, key=lambda d: d.timestamp, reverse=True)[:limit]

    async def get_delivery_stats(self, webhook_id: str) -> Dict[str, Any]:
        """Get delivery statistics for a webhook"""
        webhook = self._webhooks.get(webhook_id)
        if not webhook:
            return {}

        recent_deliveries = await self.get_deliveries(webhook_id, limit=100)
        success_count = sum(1 for d in recent_deliveries if d.is_success)
        avg_duration = (
            sum(d.duration_ms for d in recent_deliveries) / len(recent_deliveries)
            if recent_deliveries else 0
        )

        return {
            "webhook_id": webhook_id,
            "total_deliveries": webhook.total_deliveries,
            "total_failures": webhook.total_failures,
            "success_rate": (
                success_count / len(recent_deliveries) * 100
                if recent_deliveries else 0
            ),
            "avg_duration_ms": round(avg_duration, 2),
            "is_healthy": webhook.is_healthy
        }


# Singleton
_webhook_manager: Optional[WebhookManager] = None


def get_webhook_manager() -> WebhookManager:
    """Get the webhook manager singleton"""
    global _webhook_manager
    if _webhook_manager is None:
        _webhook_manager = WebhookManager()
    return _webhook_manager


# Testing
if __name__ == "__main__":
    async def test():
        manager = WebhookManager("data/test_webhooks.json")
        await manager.start()

        # Create webhook
        webhook = await manager.create_webhook(
            user_id="test_user",
            url="https://example.com/webhook",
            events=[WebhookEvent.TRADE_EXECUTED, WebhookEvent.POSITION_OPENED]
        )
        print(f"Created webhook: {webhook.to_dict()}")

        # Dispatch event (will fail since URL is fake)
        await manager.dispatch_event(
            WebhookEvent.TRADE_EXECUTED,
            {"token": "SOL", "amount": 10, "price": 150}
        )

        # Get stats
        stats = await manager.get_delivery_stats(webhook.webhook_id)
        print(f"Delivery stats: {stats}")

        await manager.stop()

    asyncio.run(test())
