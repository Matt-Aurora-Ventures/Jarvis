"""
Bags.fm Webhook Handler
Prompt #36: Handle webhook events from Bags API
"""

import asyncio
import hashlib
import hmac
import json
import logging
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional
from dataclasses import dataclass, field
from enum import Enum
import aiohttp
from fastapi import FastAPI, HTTPException, Request, BackgroundTasks
from pydantic import BaseModel
import redis.asyncio as redis

logger = logging.getLogger(__name__)


# =============================================================================
# EVENT TYPES
# =============================================================================

class BagsEventType(str, Enum):
    """Bags.fm webhook event types"""
    TOKEN_LAUNCH_COMPLETED = "token_launch.completed"
    TOKEN_LAUNCH_FAILED = "token_launch.failed"
    TRADE_EXECUTED = "trade.executed"
    FEES_CLAIMED = "fees.claimed"
    PARTNER_STATS_UPDATED = "partner.stats_updated"
    POOL_CREATED = "pool.created"
    LIQUIDITY_ADDED = "liquidity.added"
    LIQUIDITY_REMOVED = "liquidity.removed"


# =============================================================================
# EVENT MODELS
# =============================================================================

class WebhookEvent(BaseModel):
    """Base webhook event"""
    id: str
    type: str
    timestamp: int
    data: Dict[str, Any]
    signature: Optional[str] = None


class TokenLaunchEvent(BaseModel):
    """Token launch completed event"""
    token_mint: str
    token_name: str
    token_symbol: str
    initial_price: float
    pool_address: str
    creator: str
    transaction_signature: str


class TradeExecutedEvent(BaseModel):
    """Trade execution event"""
    trade_id: str
    input_mint: str
    output_mint: str
    input_amount: int
    output_amount: int
    user_wallet: str
    partner_id: Optional[str]
    partner_fee: int
    platform_fee: int
    transaction_signature: str


class FeesClaimedEvent(BaseModel):
    """Partner fees claimed event"""
    partner_id: str
    amount_claimed: int
    claim_signature: str
    period_start: int
    period_end: int


class PartnerStatsEvent(BaseModel):
    """Partner stats update event"""
    partner_id: str
    total_volume: int
    total_fees_earned: int
    total_trades: int
    unique_users: int
    period: str  # "daily", "weekly", "monthly"


# =============================================================================
# WEBHOOK HANDLER
# =============================================================================

class BagsWebhookHandler:
    """Handler for Bags.fm webhook events"""

    def __init__(
        self,
        webhook_secret: str,
        redis_url: str = "redis://localhost:6379",
        dead_letter_queue: str = "bags:dlq",
    ):
        self.webhook_secret = webhook_secret
        self.redis_url = redis_url
        self.dead_letter_queue = dead_letter_queue
        self._redis: Optional[redis.Redis] = None
        self._handlers: Dict[str, List[Callable]] = {}
        self._websocket_clients: List[aiohttp.ClientWebSocketResponse] = []

    async def connect(self):
        """Initialize Redis connection"""
        self._redis = await redis.from_url(self.redis_url)

    async def close(self):
        """Close connections"""
        if self._redis:
            await self._redis.close()

    # =========================================================================
    # SIGNATURE VERIFICATION
    # =========================================================================

    def verify_signature(self, payload: bytes, signature: str) -> bool:
        """Verify webhook signature for authenticity"""
        expected = hmac.new(
            self.webhook_secret.encode(),
            payload,
            hashlib.sha256
        ).hexdigest()

        return hmac.compare_digest(f"sha256={expected}", signature)

    # =========================================================================
    # IDEMPOTENCY
    # =========================================================================

    async def is_processed(self, event_id: str) -> bool:
        """Check if event was already processed"""
        key = f"bags:event:{event_id}"
        return await self._redis.exists(key)

    async def mark_processed(self, event_id: str, ttl: int = 86400 * 7):
        """Mark event as processed (7 day TTL)"""
        key = f"bags:event:{event_id}"
        await self._redis.setex(key, ttl, "1")

    # =========================================================================
    # EVENT HANDLING
    # =========================================================================

    def on(self, event_type: str, handler: Callable):
        """Register an event handler"""
        if event_type not in self._handlers:
            self._handlers[event_type] = []
        self._handlers[event_type].append(handler)

    async def handle_event(self, event: WebhookEvent) -> bool:
        """Process a webhook event"""
        # Check idempotency
        if await self.is_processed(event.id):
            logger.info(f"Event {event.id} already processed, skipping")
            return True

        try:
            # Get handlers for this event type
            handlers = self._handlers.get(event.type, [])
            if not handlers:
                logger.warning(f"No handlers for event type: {event.type}")
                return True

            # Execute all handlers
            for handler in handlers:
                try:
                    if asyncio.iscoroutinefunction(handler):
                        await handler(event)
                    else:
                        handler(event)
                except Exception as e:
                    logger.error(f"Handler error for {event.type}: {e}")
                    raise

            # Mark as processed
            await self.mark_processed(event.id)

            # Broadcast to websocket clients
            await self.broadcast_to_clients(event)

            # Log to database
            await self.log_event(event)

            return True

        except Exception as e:
            logger.error(f"Failed to process event {event.id}: {e}")
            await self.send_to_dlq(event, str(e))
            return False

    # =========================================================================
    # DEAD LETTER QUEUE
    # =========================================================================

    async def send_to_dlq(self, event: WebhookEvent, error: str):
        """Send failed event to dead letter queue"""
        dlq_entry = {
            "event": event.dict(),
            "error": error,
            "failed_at": datetime.utcnow().isoformat(),
            "retry_count": 0
        }
        await self._redis.lpush(
            self.dead_letter_queue,
            json.dumps(dlq_entry)
        )
        logger.info(f"Sent event {event.id} to DLQ")

    async def retry_dlq(self, max_retries: int = 3):
        """Retry events from dead letter queue"""
        while True:
            entry_data = await self._redis.rpop(self.dead_letter_queue)
            if not entry_data:
                break

            entry = json.loads(entry_data)
            if entry["retry_count"] >= max_retries:
                logger.error(f"Event {entry['event']['id']} exceeded max retries")
                # Move to permanent failure log
                await self._redis.lpush("bags:dlq:failed", entry_data)
                continue

            entry["retry_count"] += 1
            event = WebhookEvent(**entry["event"])

            success = await self.handle_event(event)
            if not success:
                await self._redis.lpush(
                    self.dead_letter_queue,
                    json.dumps(entry)
                )

    # =========================================================================
    # WEBSOCKET BROADCAST
    # =========================================================================

    async def broadcast_to_clients(self, event: WebhookEvent):
        """Broadcast event to connected websocket clients"""
        message = json.dumps({
            "type": "bags_event",
            "event": event.dict()
        })

        disconnected = []
        for client in self._websocket_clients:
            try:
                await client.send_str(message)
            except Exception:
                disconnected.append(client)

        # Remove disconnected clients
        for client in disconnected:
            self._websocket_clients.remove(client)

    def add_websocket_client(self, client):
        """Add a websocket client for real-time updates"""
        self._websocket_clients.append(client)

    def remove_websocket_client(self, client):
        """Remove a websocket client"""
        if client in self._websocket_clients:
            self._websocket_clients.remove(client)

    # =========================================================================
    # DATABASE LOGGING
    # =========================================================================

    async def log_event(self, event: WebhookEvent):
        """Log event to database for auditing"""
        # Store in Redis sorted set by timestamp for quick access
        await self._redis.zadd(
            "bags:events:log",
            {json.dumps(event.dict()): event.timestamp}
        )

        # Trim to last 10000 events
        await self._redis.zremrangebyrank("bags:events:log", 0, -10001)

        # Also store by type for filtering
        await self._redis.lpush(
            f"bags:events:{event.type}",
            json.dumps(event.dict())
        )
        await self._redis.ltrim(f"bags:events:{event.type}", 0, 999)


# =============================================================================
# FASTAPI ROUTES
# =============================================================================

def create_webhook_routes(handler: BagsWebhookHandler) -> FastAPI:
    """Create FastAPI router for webhook endpoints"""
    from fastapi import APIRouter
    router = APIRouter(prefix="/webhooks/bags", tags=["Bags Webhooks"])

    @router.post("/")
    async def receive_webhook(
        request: Request,
        background_tasks: BackgroundTasks
    ):
        """Receive and process Bags.fm webhook"""
        # Get raw body and signature
        body = await request.body()
        signature = request.headers.get("X-Bags-Signature", "")

        # Verify signature
        if not handler.verify_signature(body, signature):
            raise HTTPException(status_code=401, detail="Invalid signature")

        # Parse event
        try:
            event_data = json.loads(body)
            event = WebhookEvent(**event_data)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Invalid event: {e}")

        # Process in background
        background_tasks.add_task(handler.handle_event, event)

        return {"status": "accepted", "event_id": event.id}

    @router.get("/events")
    async def get_recent_events(
        event_type: Optional[str] = None,
        limit: int = 50
    ):
        """Get recent webhook events"""
        if event_type:
            events = await handler._redis.lrange(
                f"bags:events:{event_type}", 0, limit - 1
            )
        else:
            events = await handler._redis.zrevrange(
                "bags:events:log", 0, limit - 1
            )

        return [json.loads(e) for e in events]

    @router.get("/dlq")
    async def get_dlq_events(limit: int = 50):
        """Get events in dead letter queue"""
        events = await handler._redis.lrange(
            handler.dead_letter_queue, 0, limit - 1
        )
        return [json.loads(e) for e in events]

    @router.post("/dlq/retry")
    async def retry_dlq_events():
        """Retry events in dead letter queue"""
        await handler.retry_dlq()
        return {"status": "ok"}

    return router


# =============================================================================
# POLLING FALLBACK
# =============================================================================

class BagsPollingFallback:
    """Fallback polling for when webhooks aren't available"""

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://public-api-v2.bags.fm",
        poll_interval: int = 60
    ):
        self.api_key = api_key
        self.base_url = base_url
        self.poll_interval = poll_interval
        self._last_poll: Dict[str, int] = {}
        self._running = False

    async def start_polling(self, handler: BagsWebhookHandler):
        """Start polling loop"""
        self._running = True

        async with aiohttp.ClientSession() as session:
            while self._running:
                try:
                    await self._poll_partner_stats(session, handler)
                    await self._poll_recent_trades(session, handler)
                except Exception as e:
                    logger.error(f"Polling error: {e}")

                await asyncio.sleep(self.poll_interval)

    async def stop_polling(self):
        """Stop polling loop"""
        self._running = False

    async def _poll_partner_stats(
        self,
        session: aiohttp.ClientSession,
        handler: BagsWebhookHandler
    ):
        """Poll for partner stats updates"""
        async with session.get(
            f"{self.base_url}/api/v1/partner/stats",
            headers={"x-api-key": self.api_key}
        ) as response:
            if response.status == 200:
                data = await response.json()
                event = WebhookEvent(
                    id=f"poll-stats-{datetime.utcnow().timestamp()}",
                    type=BagsEventType.PARTNER_STATS_UPDATED,
                    timestamp=int(datetime.utcnow().timestamp()),
                    data=data
                )
                await handler.handle_event(event)

    async def _poll_recent_trades(
        self,
        session: aiohttp.ClientSession,
        handler: BagsWebhookHandler
    ):
        """Poll for recent trades"""
        since = self._last_poll.get("trades", 0)
        async with session.get(
            f"{self.base_url}/api/v1/partner/trades",
            headers={"x-api-key": self.api_key},
            params={"since": since}
        ) as response:
            if response.status == 200:
                data = await response.json()
                for trade in data.get("trades", []):
                    event = WebhookEvent(
                        id=f"poll-trade-{trade.get('signature')}",
                        type=BagsEventType.TRADE_EXECUTED,
                        timestamp=trade.get("timestamp", 0),
                        data=trade
                    )
                    await handler.handle_event(event)

                if data.get("trades"):
                    self._last_poll["trades"] = max(
                        t.get("timestamp", 0) for t in data["trades"]
                    )


# =============================================================================
# DEFAULT EVENT HANDLERS
# =============================================================================

def register_default_handlers(handler: BagsWebhookHandler):
    """Register default event handlers"""

    @handler.on(BagsEventType.TRADE_EXECUTED)
    async def on_trade_executed(event: WebhookEvent):
        """Handle trade execution"""
        data = TradeExecutedEvent(**event.data)
        logger.info(
            f"Trade executed: {data.input_amount} -> {data.output_amount}, "
            f"partner fee: {data.partner_fee}"
        )
        # Update metrics, notify user, etc.

    @handler.on(BagsEventType.FEES_CLAIMED)
    async def on_fees_claimed(event: WebhookEvent):
        """Handle fee claim"""
        data = FeesClaimedEvent(**event.data)
        logger.info(
            f"Fees claimed: {data.amount_claimed} lamports, "
            f"signature: {data.claim_signature}"
        )
        # Trigger distribution to stakers

    @handler.on(BagsEventType.PARTNER_STATS_UPDATED)
    async def on_stats_updated(event: WebhookEvent):
        """Handle stats update"""
        data = PartnerStatsEvent(**event.data)
        logger.info(
            f"Partner stats updated: {data.total_volume} volume, "
            f"{data.total_fees_earned} fees earned"
        )
        # Update dashboard

    @handler.on(BagsEventType.TOKEN_LAUNCH_COMPLETED)
    async def on_token_launch(event: WebhookEvent):
        """Handle token launch"""
        data = TokenLaunchEvent(**event.data)
        logger.info(
            f"Token launched: {data.token_symbol} at {data.initial_price}, "
            f"pool: {data.pool_address}"
        )
        # Add to watchlist, notify users
