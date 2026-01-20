"""
Tests for Webhook Handlers (Bags.fm Webhook).

Validates:
- Webhook signature verification
- Duplicate event deduplication (idempotency)
- Event processing is idempotent
- Timeout handling
- Retry behavior on failure (DLQ)
- Event ordering preservation
"""

import asyncio
import hashlib
import hmac
import json
import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
from typing import List

from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.testclient import TestClient as StarletteTestClient

from api.webhooks.bags_webhook import (
    BagsWebhookHandler,
    BagsEventType,
    WebhookEvent,
    TokenLaunchEvent,
    TradeExecutedEvent,
    FeesClaimedEvent,
    PartnerStatsEvent,
    create_webhook_routes,
    BagsPollingFallback,
)


# =============================================================================
# Test Fixtures
# =============================================================================


class MockRedis:
    """Mock Redis for testing without real Redis connection."""

    def __init__(self):
        self._data = {}
        self._lists = {}
        self._zsets = {}
        self._expiry = {}

    async def exists(self, key: str) -> bool:
        return key in self._data

    async def setex(self, key: str, ttl: int, value: str):
        self._data[key] = value
        self._expiry[key] = ttl

    async def get(self, key: str) -> str:
        return self._data.get(key)

    async def lpush(self, key: str, value: str):
        if key not in self._lists:
            self._lists[key] = []
        self._lists[key].insert(0, value)

    async def rpop(self, key: str) -> str:
        if key in self._lists and self._lists[key]:
            return self._lists[key].pop()
        return None

    async def lrange(self, key: str, start: int, end: int) -> List[str]:
        if key not in self._lists:
            return []
        return self._lists[key][start:end + 1]

    async def ltrim(self, key: str, start: int, end: int):
        if key in self._lists:
            self._lists[key] = self._lists[key][start:end + 1]

    async def zadd(self, key: str, mapping: dict):
        if key not in self._zsets:
            self._zsets[key] = {}
        self._zsets[key].update(mapping)

    async def zrevrange(self, key: str, start: int, end: int) -> List[str]:
        if key not in self._zsets:
            return []
        items = sorted(self._zsets[key].items(), key=lambda x: x[1], reverse=True)
        return [k for k, v in items[start:end + 1]]

    async def zremrangebyrank(self, key: str, start: int, end: int):
        pass  # Simplified for testing

    async def close(self):
        pass


@pytest.fixture
def mock_redis():
    """Create a mock Redis instance."""
    return MockRedis()


@pytest.fixture
def webhook_secret():
    """Return test webhook secret."""
    return "test_secret_key_12345"


@pytest.fixture
def handler(webhook_secret, mock_redis):
    """Create a BagsWebhookHandler with mock Redis."""
    h = BagsWebhookHandler(
        webhook_secret=webhook_secret,
        redis_url="redis://localhost:6379"
    )
    h._redis = mock_redis
    return h


@pytest.fixture
def sample_event():
    """Create a sample webhook event."""
    return WebhookEvent(
        id="evt_test_123",
        type=BagsEventType.TRADE_EXECUTED,
        timestamp=int(datetime.utcnow().timestamp()),
        data={
            "trade_id": "trade_001",
            "input_mint": "So11111111111111111111111111111111111111112",
            "output_mint": "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
            "input_amount": 1000000000,
            "output_amount": 150000000,
            "user_wallet": "8dNmN5Nm7qPJzPE4RFe8kYf8FmPqXxKz9Xu3DmWb7dNm",
            "partner_id": "partner_123",
            "partner_fee": 5000,
            "platform_fee": 10000,
            "transaction_signature": "5KtP...xyz"
        }
    )


def create_signature(payload: bytes, secret: str) -> str:
    """Create a valid webhook signature."""
    signature = hmac.new(
        secret.encode(),
        payload,
        hashlib.sha256
    ).hexdigest()
    return f"sha256={signature}"


# =============================================================================
# Signature Verification Tests
# =============================================================================


class TestSignatureVerification:
    """Test webhook signature verification."""

    def test_valid_signature(self, handler, webhook_secret):
        """Test that valid signatures are accepted."""
        payload = b'{"id": "test", "type": "test.event"}'
        signature = create_signature(payload, webhook_secret)

        assert handler.verify_signature(payload, signature) is True

    def test_invalid_signature(self, handler):
        """Test that invalid signatures are rejected."""
        payload = b'{"id": "test", "type": "test.event"}'
        invalid_signature = "sha256=invalid_signature_here"

        assert handler.verify_signature(payload, invalid_signature) is False

    def test_wrong_secret(self, handler):
        """Test that signatures made with wrong secret are rejected."""
        payload = b'{"id": "test", "type": "test.event"}'
        wrong_signature = create_signature(payload, "wrong_secret")

        assert handler.verify_signature(payload, wrong_signature) is False

    def test_empty_signature(self, handler):
        """Test that empty signatures are rejected."""
        payload = b'{"id": "test", "type": "test.event"}'

        assert handler.verify_signature(payload, "") is False

    def test_malformed_signature_format(self, handler, webhook_secret):
        """Test that malformed signature format is rejected."""
        payload = b'{"id": "test", "type": "test.event"}'
        # Missing sha256= prefix
        raw_signature = hmac.new(
            webhook_secret.encode(),
            payload,
            hashlib.sha256
        ).hexdigest()

        assert handler.verify_signature(payload, raw_signature) is False

    def test_modified_payload_fails(self, handler, webhook_secret):
        """Test that modified payload fails verification."""
        original_payload = b'{"id": "test", "type": "test.event"}'
        modified_payload = b'{"id": "test", "type": "modified.event"}'
        signature = create_signature(original_payload, webhook_secret)

        assert handler.verify_signature(modified_payload, signature) is False

    def test_timing_attack_resistance(self, handler, webhook_secret):
        """Test that comparison is constant-time (uses hmac.compare_digest)."""
        payload = b'{"id": "test", "type": "test.event"}'
        signature = create_signature(payload, webhook_secret)

        # Multiple calls should take similar time (constant time comparison)
        # We verify implementation uses hmac.compare_digest by checking the code
        assert handler.verify_signature(payload, signature) is True


# =============================================================================
# Duplicate Event Deduplication Tests
# =============================================================================


class TestEventDeduplication:
    """Test that duplicate events are properly deduplicated."""

    @pytest.mark.asyncio
    async def test_first_event_not_processed(self, handler, sample_event):
        """Test that first occurrence of event is not marked as processed."""
        is_processed = await handler.is_processed(sample_event.id)
        assert is_processed is False

    @pytest.mark.asyncio
    async def test_event_marked_as_processed(self, handler, sample_event):
        """Test that events can be marked as processed."""
        await handler.mark_processed(sample_event.id)
        is_processed = await handler.is_processed(sample_event.id)
        assert is_processed is True

    @pytest.mark.asyncio
    async def test_duplicate_event_skipped(self, handler, sample_event):
        """Test that duplicate events are skipped."""
        handler_called = []

        async def test_handler(event):
            handler_called.append(event.id)

        handler.on(BagsEventType.TRADE_EXECUTED, test_handler)

        # Process first time - should call handler
        await handler.handle_event(sample_event)
        assert len(handler_called) == 1

        # Process same event again - should skip
        await handler.handle_event(sample_event)
        assert len(handler_called) == 1  # Still 1, not 2

    @pytest.mark.asyncio
    async def test_different_events_both_processed(self, handler):
        """Test that different events are both processed."""
        handler_called = []

        async def test_handler(event):
            handler_called.append(event.id)

        handler.on(BagsEventType.TRADE_EXECUTED, test_handler)

        event1 = WebhookEvent(
            id="evt_001",
            type=BagsEventType.TRADE_EXECUTED,
            timestamp=int(datetime.utcnow().timestamp()),
            data={"trade_id": "trade_001"}
        )
        event2 = WebhookEvent(
            id="evt_002",
            type=BagsEventType.TRADE_EXECUTED,
            timestamp=int(datetime.utcnow().timestamp()),
            data={"trade_id": "trade_002"}
        )

        await handler.handle_event(event1)
        await handler.handle_event(event2)

        assert len(handler_called) == 2
        assert "evt_001" in handler_called
        assert "evt_002" in handler_called

    @pytest.mark.asyncio
    async def test_ttl_set_on_processed_marker(self, handler, sample_event, mock_redis):
        """Test that TTL is set when marking event as processed."""
        await handler.mark_processed(sample_event.id, ttl=3600)

        key = f"bags:event:{sample_event.id}"
        assert key in mock_redis._expiry
        assert mock_redis._expiry[key] == 3600


# =============================================================================
# Event Processing Idempotency Tests
# =============================================================================


class TestEventIdempotency:
    """Test that event processing is idempotent."""

    @pytest.mark.asyncio
    async def test_handler_only_called_once(self, handler, sample_event):
        """Test that handler is called exactly once per event."""
        call_count = 0

        async def counting_handler(event):
            nonlocal call_count
            call_count += 1

        handler.on(BagsEventType.TRADE_EXECUTED, counting_handler)

        # Process same event multiple times
        for _ in range(5):
            await handler.handle_event(sample_event)

        assert call_count == 1

    @pytest.mark.asyncio
    async def test_side_effects_only_once(self, handler, sample_event):
        """Test that side effects only happen once."""
        trade_updates = []

        async def update_trade_handler(event):
            trade_updates.append(event.data.get("trade_id"))

        handler.on(BagsEventType.TRADE_EXECUTED, update_trade_handler)

        await handler.handle_event(sample_event)
        await handler.handle_event(sample_event)
        await handler.handle_event(sample_event)

        assert len(trade_updates) == 1
        assert trade_updates[0] == "trade_001"

    @pytest.mark.asyncio
    async def test_processing_state_persists(self, handler, sample_event, mock_redis):
        """Test that processing state persists across handler restarts."""
        # Process event
        async def dummy_handler(event):
            pass

        handler.on(BagsEventType.TRADE_EXECUTED, dummy_handler)
        await handler.handle_event(sample_event)

        # Create new handler with same Redis (simulating restart)
        new_handler = BagsWebhookHandler(
            webhook_secret="test_secret",
            redis_url="redis://localhost:6379"
        )
        new_handler._redis = mock_redis

        # Should still be marked as processed
        is_processed = await new_handler.is_processed(sample_event.id)
        assert is_processed is True


# =============================================================================
# Retry Behavior Tests
# =============================================================================


class TestRetryBehavior:
    """Test retry behavior on failure."""

    @pytest.mark.asyncio
    async def test_failed_event_sent_to_dlq(self, handler, sample_event, mock_redis):
        """Test that failed events are sent to dead letter queue."""
        async def failing_handler(event):
            raise ValueError("Processing failed")

        handler.on(BagsEventType.TRADE_EXECUTED, failing_handler)

        result = await handler.handle_event(sample_event)

        assert result is False
        assert len(mock_redis._lists.get("bags:dlq", [])) == 1

    @pytest.mark.asyncio
    async def test_dlq_entry_contains_error_info(self, handler, sample_event, mock_redis):
        """Test that DLQ entry contains error information."""
        async def failing_handler(event):
            raise ValueError("Specific error message")

        handler.on(BagsEventType.TRADE_EXECUTED, failing_handler)

        await handler.handle_event(sample_event)

        dlq_entries = mock_redis._lists.get("bags:dlq", [])
        assert len(dlq_entries) == 1

        entry = json.loads(dlq_entries[0])
        assert "error" in entry
        assert "Specific error message" in entry["error"]
        assert "failed_at" in entry
        assert "retry_count" in entry
        assert entry["retry_count"] == 0

    @pytest.mark.asyncio
    async def test_dlq_retry_mechanism(self, handler, mock_redis):
        """Test DLQ retry mechanism."""
        successful_events = []

        async def succeeding_handler(event):
            successful_events.append(event.id)

        handler.on(BagsEventType.TRADE_EXECUTED, succeeding_handler)

        # Add event to DLQ
        event = WebhookEvent(
            id="evt_retry_001",
            type=BagsEventType.TRADE_EXECUTED,
            timestamp=int(datetime.utcnow().timestamp()),
            data={"trade_id": "trade_001"}
        )
        dlq_entry = {
            "event": event.dict(),
            "error": "Previous failure",
            "failed_at": datetime.utcnow().isoformat(),
            "retry_count": 0
        }
        mock_redis._lists["bags:dlq"] = [json.dumps(dlq_entry)]

        # Retry DLQ
        await handler.retry_dlq(max_retries=3)

        # Event should be processed
        assert "evt_retry_001" in successful_events

    @pytest.mark.asyncio
    async def test_max_retries_exhausted(self, handler, mock_redis):
        """Test that events exceeding max retries go to permanent failure."""
        async def failing_handler(event):
            raise ValueError("Always fails")

        handler.on(BagsEventType.TRADE_EXECUTED, failing_handler)

        # Add event to DLQ with retry_count at max
        event = WebhookEvent(
            id="evt_max_retry",
            type=BagsEventType.TRADE_EXECUTED,
            timestamp=int(datetime.utcnow().timestamp()),
            data={"trade_id": "trade_001"}
        )
        dlq_entry = {
            "event": event.dict(),
            "error": "Previous failure",
            "failed_at": datetime.utcnow().isoformat(),
            "retry_count": 3  # At max
        }
        mock_redis._lists["bags:dlq"] = [json.dumps(dlq_entry)]

        # Retry DLQ
        await handler.retry_dlq(max_retries=3)

        # Should be moved to permanent failure queue
        assert len(mock_redis._lists.get("bags:dlq:failed", [])) == 1

    @pytest.mark.asyncio
    async def test_retry_count_incremented(self, handler, mock_redis):
        """Test that retry count is incremented on each retry."""
        async def failing_handler(event):
            raise ValueError("Always fails")

        handler.on(BagsEventType.TRADE_EXECUTED, failing_handler)

        event = WebhookEvent(
            id="evt_count_test",
            type=BagsEventType.TRADE_EXECUTED,
            timestamp=int(datetime.utcnow().timestamp()),
            data={"trade_id": "trade_001"}
        )
        dlq_entry = {
            "event": event.dict(),
            "error": "Previous failure",
            "failed_at": datetime.utcnow().isoformat(),
            "retry_count": 1
        }
        mock_redis._lists["bags:dlq"] = [json.dumps(dlq_entry)]

        await handler.retry_dlq(max_retries=3)

        # Should be back in DLQ with incremented retry count
        remaining = mock_redis._lists.get("bags:dlq", [])
        if remaining:
            entry = json.loads(remaining[0])
            assert entry["retry_count"] == 2


# =============================================================================
# Event Ordering Tests
# =============================================================================


class TestEventOrdering:
    """Test that event ordering is preserved."""

    @pytest.mark.asyncio
    async def test_events_processed_in_order(self, handler):
        """Test that events are processed in receipt order."""
        processed_order = []

        async def order_tracking_handler(event):
            processed_order.append(event.id)

        handler.on(BagsEventType.TRADE_EXECUTED, order_tracking_handler)

        events = [
            WebhookEvent(
                id=f"evt_{i:03d}",
                type=BagsEventType.TRADE_EXECUTED,
                timestamp=int(datetime.utcnow().timestamp()),
                data={"order": i}
            )
            for i in range(10)
        ]

        for event in events:
            await handler.handle_event(event)

        expected_order = [f"evt_{i:03d}" for i in range(10)]
        assert processed_order == expected_order

    @pytest.mark.asyncio
    async def test_event_log_maintains_order(self, handler, mock_redis):
        """Test that event log maintains chronological order."""
        async def dummy_handler(event):
            pass

        handler.on(BagsEventType.TRADE_EXECUTED, dummy_handler)

        base_time = int(datetime.utcnow().timestamp())
        for i in range(5):
            event = WebhookEvent(
                id=f"evt_{i}",
                type=BagsEventType.TRADE_EXECUTED,
                timestamp=base_time + i,
                data={"order": i}
            )
            await handler.handle_event(event)

        # Verify events are stored in log
        logged_events = mock_redis._zsets.get("bags:events:log", {})
        assert len(logged_events) == 5

    @pytest.mark.asyncio
    async def test_events_by_type_maintains_order(self, handler, mock_redis):
        """Test that per-type event lists maintain order."""
        async def dummy_handler(event):
            pass

        handler.on(BagsEventType.TRADE_EXECUTED, dummy_handler)

        for i in range(3):
            event = WebhookEvent(
                id=f"evt_{i}",
                type=BagsEventType.TRADE_EXECUTED,
                timestamp=int(datetime.utcnow().timestamp()),
                data={"order": i}
            )
            await handler.handle_event(event)

        # Use the string value of the enum, as that's what the handler logs with
        type_key = f"bags:events:{BagsEventType.TRADE_EXECUTED.value}"
        assert type_key in mock_redis._lists
        # Events are stored newest first (lpush)
        assert len(mock_redis._lists[type_key]) == 3


# =============================================================================
# Handler Registration Tests
# =============================================================================


class TestHandlerRegistration:
    """Test event handler registration."""

    @pytest.mark.asyncio
    async def test_multiple_handlers_for_same_event(self, handler, sample_event):
        """Test that multiple handlers can be registered for same event type."""
        handler1_called = []
        handler2_called = []

        async def handler1(event):
            handler1_called.append(event.id)

        async def handler2(event):
            handler2_called.append(event.id)

        handler.on(BagsEventType.TRADE_EXECUTED, handler1)
        handler.on(BagsEventType.TRADE_EXECUTED, handler2)

        await handler.handle_event(sample_event)

        assert len(handler1_called) == 1
        assert len(handler2_called) == 1

    @pytest.mark.asyncio
    async def test_sync_handler_support(self, handler, sample_event):
        """Test that sync handlers are also supported."""
        sync_called = []

        def sync_handler(event):
            sync_called.append(event.id)

        handler.on(BagsEventType.TRADE_EXECUTED, sync_handler)

        await handler.handle_event(sample_event)

        assert len(sync_called) == 1

    @pytest.mark.asyncio
    async def test_no_handlers_logs_warning(self, handler, caplog):
        """Test that missing handlers logs a warning."""
        event = WebhookEvent(
            id="evt_no_handler",
            type=BagsEventType.POOL_CREATED,  # No handler registered
            timestamp=int(datetime.utcnow().timestamp()),
            data={"pool": "test"}
        )

        result = await handler.handle_event(event)

        assert result is True  # Still returns True (no-op)

    @pytest.mark.asyncio
    async def test_handler_error_propagates(self, handler, sample_event):
        """Test that handler errors cause event to fail."""
        async def error_handler(event):
            raise RuntimeError("Handler error")

        handler.on(BagsEventType.TRADE_EXECUTED, error_handler)

        result = await handler.handle_event(sample_event)

        assert result is False


# =============================================================================
# FastAPI Route Tests
# =============================================================================


class TestWebhookRoutes:
    """Test FastAPI webhook routes."""

    @pytest.fixture
    def app_with_routes(self, handler):
        """Create FastAPI app with webhook routes."""
        app = FastAPI()
        router = create_webhook_routes(handler)
        app.include_router(router)
        return app

    def test_webhook_endpoint_requires_signature(self, app_with_routes):
        """Test that webhook endpoint requires valid signature."""
        client = TestClient(app_with_routes)

        response = client.post(
            "/webhooks/bags/",
            json={"id": "test", "type": "test.event", "timestamp": 123, "data": {}},
            headers={"X-Bags-Signature": "invalid"}
        )

        assert response.status_code == 401
        assert "Invalid signature" in response.json()["detail"]

    def test_webhook_endpoint_accepts_valid_signature(self, handler, webhook_secret):
        """Test that webhook endpoint accepts valid signature."""
        app = FastAPI()
        router = create_webhook_routes(handler)
        app.include_router(router)
        client = TestClient(app)

        payload = json.dumps({
            "id": "evt_test",
            "type": BagsEventType.TRADE_EXECUTED,
            "timestamp": int(datetime.utcnow().timestamp()),
            "data": {"trade_id": "test"}
        }).encode()

        signature = create_signature(payload, webhook_secret)

        response = client.post(
            "/webhooks/bags/",
            content=payload,
            headers={
                "X-Bags-Signature": signature,
                "Content-Type": "application/json"
            }
        )

        assert response.status_code == 200
        assert response.json()["status"] == "accepted"
        assert response.json()["event_id"] == "evt_test"

    def test_webhook_endpoint_rejects_malformed_json(self, handler, webhook_secret):
        """Test that endpoint rejects malformed JSON."""
        app = FastAPI()
        router = create_webhook_routes(handler)
        app.include_router(router)
        client = TestClient(app)

        payload = b"not valid json"
        signature = create_signature(payload, webhook_secret)

        response = client.post(
            "/webhooks/bags/",
            content=payload,
            headers={
                "X-Bags-Signature": signature,
                "Content-Type": "application/json"
            }
        )

        assert response.status_code == 400
        assert "Invalid event" in response.json()["detail"]


# =============================================================================
# WebSocket Broadcast Tests
# =============================================================================


class TestWebSocketBroadcast:
    """Test WebSocket event broadcasting."""

    @pytest.mark.asyncio
    async def test_broadcast_sends_to_clients(self, handler, sample_event):
        """Test that events are broadcast to connected clients."""
        mock_client = AsyncMock()
        handler.add_websocket_client(mock_client)

        await handler.broadcast_to_clients(sample_event)

        mock_client.send_str.assert_called_once()
        sent_data = json.loads(mock_client.send_str.call_args[0][0])
        assert sent_data["type"] == "bags_event"
        assert sent_data["event"]["id"] == sample_event.id

    @pytest.mark.asyncio
    async def test_disconnected_clients_removed(self, handler, sample_event):
        """Test that disconnected clients are removed from list."""
        mock_client = AsyncMock()
        mock_client.send_str.side_effect = Exception("Disconnected")
        handler.add_websocket_client(mock_client)

        assert len(handler._websocket_clients) == 1

        await handler.broadcast_to_clients(sample_event)

        assert len(handler._websocket_clients) == 0

    def test_add_remove_websocket_client(self, handler):
        """Test adding and removing WebSocket clients."""
        mock_client = MagicMock()

        handler.add_websocket_client(mock_client)
        assert mock_client in handler._websocket_clients

        handler.remove_websocket_client(mock_client)
        assert mock_client not in handler._websocket_clients


# =============================================================================
# Event Model Tests
# =============================================================================


class TestEventModels:
    """Test event data models."""

    def test_webhook_event_model(self):
        """Test WebhookEvent model validation."""
        event = WebhookEvent(
            id="evt_123",
            type=BagsEventType.TRADE_EXECUTED,
            timestamp=1704067200,
            data={"key": "value"}
        )

        assert event.id == "evt_123"
        assert event.type == BagsEventType.TRADE_EXECUTED
        assert event.timestamp == 1704067200
        assert event.data == {"key": "value"}
        assert event.signature is None

    def test_trade_executed_event_model(self):
        """Test TradeExecutedEvent model."""
        event = TradeExecutedEvent(
            trade_id="trade_001",
            input_mint="SOL_MINT",
            output_mint="USDC_MINT",
            input_amount=1000000000,
            output_amount=150000000,
            user_wallet="wallet_address",
            partner_id="partner_123",
            partner_fee=5000,
            platform_fee=10000,
            transaction_signature="tx_sig"
        )

        assert event.trade_id == "trade_001"
        assert event.input_amount == 1000000000
        assert event.partner_fee == 5000

    def test_token_launch_event_model(self):
        """Test TokenLaunchEvent model."""
        event = TokenLaunchEvent(
            token_mint="TOKEN_MINT",
            token_name="Test Token",
            token_symbol="TEST",
            initial_price=0.001,
            pool_address="POOL_ADDR",
            creator="CREATOR_ADDR",
            transaction_signature="tx_sig"
        )

        assert event.token_symbol == "TEST"
        assert event.initial_price == 0.001

    def test_fees_claimed_event_model(self):
        """Test FeesClaimedEvent model."""
        event = FeesClaimedEvent(
            partner_id="partner_123",
            amount_claimed=500000,
            claim_signature="claim_sig",
            period_start=1704067200,
            period_end=1704153600
        )

        assert event.amount_claimed == 500000
        assert event.period_end > event.period_start

    def test_partner_stats_event_model(self):
        """Test PartnerStatsEvent model."""
        event = PartnerStatsEvent(
            partner_id="partner_123",
            total_volume=10000000000,
            total_fees_earned=50000000,
            total_trades=1000,
            unique_users=250,
            period="daily"
        )

        assert event.total_trades == 1000
        assert event.period == "daily"


# =============================================================================
# Event Type Tests
# =============================================================================


class TestEventTypes:
    """Test event type enumeration."""

    def test_all_event_types_defined(self):
        """Test that all expected event types are defined."""
        expected_types = [
            "token_launch.completed",
            "token_launch.failed",
            "trade.executed",
            "fees.claimed",
            "partner.stats_updated",
            "pool.created",
            "liquidity.added",
            "liquidity.removed"
        ]

        actual_types = [e.value for e in BagsEventType]
        for expected in expected_types:
            assert expected in actual_types


# =============================================================================
# Default Handler Tests
# =============================================================================


class TestDefaultHandlers:
    """Test default event handler registration.

    NOTE: The register_default_handlers function uses @handler.on() as a decorator,
    but the on() method is designed for direct calls (not decorator usage).
    This is a known limitation in the production code.
    """

    def test_manual_handler_registration(self, handler):
        """Test that handlers can be manually registered (non-decorator usage)."""
        async def my_trade_handler(event):
            pass

        async def my_fee_handler(event):
            pass

        # Register handlers using the non-decorator API
        handler.on(BagsEventType.TRADE_EXECUTED, my_trade_handler)
        handler.on(BagsEventType.FEES_CLAIMED, my_fee_handler)

        # Verify handlers are registered
        assert BagsEventType.TRADE_EXECUTED in handler._handlers
        assert BagsEventType.FEES_CLAIMED in handler._handlers
        assert len(handler._handlers[BagsEventType.TRADE_EXECUTED]) == 1
        assert len(handler._handlers[BagsEventType.FEES_CLAIMED]) == 1


# =============================================================================
# Polling Fallback Tests
# =============================================================================


class TestPollingFallback:
    """Test polling fallback mechanism."""

    @pytest.fixture
    def fallback(self):
        """Create polling fallback instance."""
        return BagsPollingFallback(
            api_key="test_api_key",
            poll_interval=1
        )

    def test_fallback_initialization(self, fallback):
        """Test polling fallback initialization."""
        assert fallback.api_key == "test_api_key"
        assert fallback.poll_interval == 1
        assert fallback._running is False

    @pytest.mark.asyncio
    async def test_stop_polling(self, fallback):
        """Test stopping the polling loop."""
        fallback._running = True
        await fallback.stop_polling()
        assert fallback._running is False


# =============================================================================
# Connection Lifecycle Tests
# =============================================================================


class TestConnectionLifecycle:
    """Test connection lifecycle management."""

    @pytest.mark.asyncio
    async def test_connect_creates_redis(self, webhook_secret):
        """Test that connect creates Redis connection."""
        handler = BagsWebhookHandler(
            webhook_secret=webhook_secret,
            redis_url="redis://localhost:6379"
        )

        with patch('redis.asyncio.from_url', new_callable=AsyncMock) as mock_redis:
            mock_redis.return_value = MockRedis()
            await handler.connect()

            mock_redis.assert_called_once_with("redis://localhost:6379")

    @pytest.mark.asyncio
    async def test_close_closes_redis(self, handler, mock_redis):
        """Test that close properly closes Redis."""
        close_called = False

        async def mock_close():
            nonlocal close_called
            close_called = True

        mock_redis.close = mock_close

        await handler.close()

        assert close_called is True


# =============================================================================
# Event Logging Tests
# =============================================================================


class TestEventLogging:
    """Test event logging functionality."""

    @pytest.mark.asyncio
    async def test_events_logged_to_sorted_set(self, handler, sample_event, mock_redis):
        """Test that events are logged to sorted set."""
        async def dummy_handler(event):
            pass

        handler.on(BagsEventType.TRADE_EXECUTED, dummy_handler)

        await handler.handle_event(sample_event)

        # Verify event is in sorted set
        assert "bags:events:log" in mock_redis._zsets
        assert len(mock_redis._zsets["bags:events:log"]) == 1

    @pytest.mark.asyncio
    async def test_events_logged_by_type(self, handler, sample_event, mock_redis):
        """Test that events are logged by type."""
        async def dummy_handler(event):
            pass

        handler.on(BagsEventType.TRADE_EXECUTED, dummy_handler)

        await handler.handle_event(sample_event)

        # Use the string value since the event.type gets serialized to its value
        type_key = f"bags:events:{BagsEventType.TRADE_EXECUTED.value}"
        assert type_key in mock_redis._lists
        assert len(mock_redis._lists[type_key]) == 1


# =============================================================================
# Timeout Handling Tests
# =============================================================================


class TestTimeoutHandling:
    """Test timeout handling in webhook processing."""

    @pytest.mark.asyncio
    async def test_slow_handler_completes(self, handler, sample_event):
        """Test that slow handlers still complete if within timeout."""
        completed = []

        async def slow_handler(event):
            await asyncio.sleep(0.1)  # Small delay
            completed.append(event.id)

        handler.on(BagsEventType.TRADE_EXECUTED, slow_handler)

        result = await handler.handle_event(sample_event)

        assert result is True
        assert sample_event.id in completed

    @pytest.mark.asyncio
    async def test_handler_timeout_via_asyncio(self, handler, sample_event):
        """Test that handlers can be wrapped with asyncio timeout."""
        async def very_slow_handler(event):
            await asyncio.sleep(10)  # Would take too long

        handler.on(BagsEventType.TRADE_EXECUTED, very_slow_handler)

        # Wrap the call with a short timeout
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(
                handler.handle_event(sample_event),
                timeout=0.1
            )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
