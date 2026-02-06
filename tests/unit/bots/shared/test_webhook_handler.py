"""
Tests for ClawdBots webhook handler module.

Tests the inbound webhook handling functionality:
- Webhook registration
- Signature validation
- Request handling and routing
- Log management
"""

import asyncio
import hashlib
import hmac
import json
import os
import pytest
import tempfile
import time
from pathlib import Path
from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock, patch


# Import will fail until we implement the module
try:
    from bots.shared.webhook_handler import (
        register_webhook,
        unregister_webhook,
        handle_webhook_request,
        validate_signature,
        get_webhook_logs,
        get_registered_webhooks,
        WebhookResponse,
        WebhookRegistry,
        clear_webhooks,
    )
    IMPORTS_AVAILABLE = True
except ImportError:
    IMPORTS_AVAILABLE = False


@pytest.fixture
def temp_log_file():
    """Create a temporary log file for testing."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        f.write('[]')
        temp_path = f.name
    yield temp_path
    # Cleanup
    if os.path.exists(temp_path):
        os.unlink(temp_path)


@pytest.fixture
def webhook_registry(temp_log_file):
    """Create a fresh webhook registry for each test."""
    if not IMPORTS_AVAILABLE:
        pytest.skip("Module not yet implemented")

    # Clear any existing webhooks and set custom log path
    clear_webhooks()
    registry = WebhookRegistry.get_instance()
    registry._log_path = Path(temp_log_file)
    return registry


class TestWebhookRegistration:
    """Tests for webhook registration functionality."""

    def test_register_webhook_basic(self, webhook_registry):
        """Test registering a basic webhook without secret."""
        handler = AsyncMock(return_value={"status": "ok"})

        register_webhook("/test/hook", handler)

        webhooks = get_registered_webhooks()
        assert "/test/hook" in webhooks
        assert webhooks["/test/hook"]["secret"] is None

    def test_register_webhook_with_secret(self, webhook_registry):
        """Test registering a webhook with HMAC secret."""
        handler = AsyncMock(return_value={"status": "ok"})
        secret = "my-secret-key"

        register_webhook("/secure/hook", handler, secret=secret)

        webhooks = get_registered_webhooks()
        assert "/secure/hook" in webhooks
        assert webhooks["/secure/hook"]["secret"] == secret

    def test_register_webhook_overwrite(self, webhook_registry):
        """Test that re-registering overwrites previous handler."""
        handler1 = AsyncMock(return_value={"v": 1})
        handler2 = AsyncMock(return_value={"v": 2})

        register_webhook("/path", handler1)
        register_webhook("/path", handler2, secret="new-secret")

        webhooks = get_registered_webhooks()
        assert "/path" in webhooks
        assert webhooks["/path"]["secret"] == "new-secret"

    def test_unregister_webhook(self, webhook_registry):
        """Test unregistering a webhook."""
        handler = AsyncMock()
        register_webhook("/removable", handler)

        result = unregister_webhook("/removable")

        assert result is True
        assert "/removable" not in get_registered_webhooks()

    def test_unregister_nonexistent_webhook(self, webhook_registry):
        """Test unregistering a webhook that doesn't exist."""
        result = unregister_webhook("/does-not-exist")
        assert result is False


class TestSignatureValidation:
    """Tests for HMAC signature validation."""

    def test_validate_signature_sha256(self, webhook_registry):
        """Test validating SHA256 HMAC signature."""
        secret = "test-secret"
        body = b'{"event": "test"}'

        # Generate valid signature
        signature = hmac.new(
            secret.encode(),
            body,
            hashlib.sha256
        ).hexdigest()

        headers = {
            "X-Webhook-Signature": f"sha256={signature}",
        }

        result = validate_signature(headers, body, secret)
        assert result is True

    def test_validate_signature_invalid(self, webhook_registry):
        """Test rejecting invalid signature."""
        secret = "test-secret"
        body = b'{"event": "test"}'

        headers = {
            "X-Webhook-Signature": "sha256=invalid-signature",
        }

        result = validate_signature(headers, body, secret)
        assert result is False

    def test_validate_signature_missing_header(self, webhook_registry):
        """Test handling missing signature header."""
        secret = "test-secret"
        body = b'{"event": "test"}'

        headers = {}

        result = validate_signature(headers, body, secret)
        assert result is False

    def test_validate_signature_no_secret_required(self, webhook_registry):
        """Test that validation passes when no secret is required."""
        body = b'{"event": "test"}'
        headers = {}

        result = validate_signature(headers, body, secret=None)
        assert result is True

    def test_validate_signature_timestamp_replay_protection(self, webhook_registry):
        """Test timestamp validation for replay protection."""
        secret = "test-secret"
        body = b'{"event": "test"}'
        timestamp = str(int(time.time()))

        # Generate signature with timestamp
        message = f"{timestamp}.{body.decode()}"
        signature = hmac.new(
            secret.encode(),
            message.encode(),
            hashlib.sha256
        ).hexdigest()

        headers = {
            "X-Webhook-Signature": f"sha256={signature}",
            "X-Webhook-Timestamp": timestamp,
        }

        result = validate_signature(headers, body, secret)
        assert result is True

    def test_validate_signature_expired_timestamp(self, webhook_registry):
        """Test rejecting expired timestamps (replay protection)."""
        secret = "test-secret"
        body = b'{"event": "test"}'
        # Timestamp from 10 minutes ago
        old_timestamp = str(int(time.time()) - 600)

        message = f"{old_timestamp}.{body.decode()}"
        signature = hmac.new(
            secret.encode(),
            message.encode(),
            hashlib.sha256
        ).hexdigest()

        headers = {
            "X-Webhook-Signature": f"sha256={signature}",
            "X-Webhook-Timestamp": old_timestamp,
        }

        # Should fail due to expired timestamp (default tolerance is 300s)
        result = validate_signature(headers, body, secret, tolerance_seconds=300)
        assert result is False


class TestWebhookRequestHandling:
    """Tests for handling incoming webhook requests."""

    @pytest.mark.asyncio
    async def test_handle_request_success(self, webhook_registry):
        """Test successful webhook request handling."""
        handler = AsyncMock(return_value={"processed": True})
        register_webhook("/api/webhook", handler)

        headers = {"Content-Type": "application/json"}
        body = b'{"event": "user.created", "data": {"id": 123}}'

        response = await handle_webhook_request("/api/webhook", headers, body)

        assert response.status_code == 200
        assert response.body["success"] is True
        handler.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_request_with_validation(self, webhook_registry):
        """Test webhook request with signature validation."""
        secret = "webhook-secret"
        handler = AsyncMock(return_value={"ok": True})
        register_webhook("/secure/webhook", handler, secret=secret)

        body = b'{"event": "payment.complete"}'
        signature = hmac.new(
            secret.encode(),
            body,
            hashlib.sha256
        ).hexdigest()

        headers = {
            "Content-Type": "application/json",
            "X-Webhook-Signature": f"sha256={signature}",
        }

        response = await handle_webhook_request("/secure/webhook", headers, body)

        assert response.status_code == 200
        handler.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_request_invalid_signature(self, webhook_registry):
        """Test rejection of request with invalid signature."""
        secret = "webhook-secret"
        handler = AsyncMock()
        register_webhook("/secure/webhook", handler, secret=secret)

        body = b'{"event": "payment.complete"}'
        headers = {
            "Content-Type": "application/json",
            "X-Webhook-Signature": "sha256=invalid",
        }

        response = await handle_webhook_request("/secure/webhook", headers, body)

        assert response.status_code == 401
        assert "signature" in response.body.get("error", "").lower()
        handler.assert_not_called()

    @pytest.mark.asyncio
    async def test_handle_request_not_found(self, webhook_registry):
        """Test 404 for unregistered webhook path."""
        headers = {"Content-Type": "application/json"}
        body = b'{}'

        response = await handle_webhook_request("/unknown/path", headers, body)

        assert response.status_code == 404
        assert "not found" in response.body.get("error", "").lower()

    @pytest.mark.asyncio
    async def test_handle_request_handler_error(self, webhook_registry):
        """Test handling when handler raises exception."""
        handler = AsyncMock(side_effect=ValueError("Processing failed"))
        register_webhook("/error/webhook", handler)

        headers = {"Content-Type": "application/json"}
        body = b'{}'

        response = await handle_webhook_request("/error/webhook", headers, body)

        assert response.status_code == 500
        assert "error" in response.body

    @pytest.mark.asyncio
    async def test_handle_request_parses_json_body(self, webhook_registry):
        """Test that JSON body is parsed and passed to handler."""
        received_data = {}

        async def capture_handler(data: Dict[str, Any]) -> Dict[str, Any]:
            received_data.update(data)
            return {"ok": True}

        register_webhook("/json/webhook", capture_handler)

        headers = {"Content-Type": "application/json"}
        body = b'{"key": "value", "number": 42}'

        await handle_webhook_request("/json/webhook", headers, body)

        assert received_data == {"key": "value", "number": 42}

    @pytest.mark.asyncio
    async def test_handle_request_raw_body_fallback(self, webhook_registry):
        """Test handling non-JSON body."""
        received_data = {}

        async def capture_handler(data: Dict[str, Any]) -> Dict[str, Any]:
            received_data.update(data)
            return {"ok": True}

        register_webhook("/raw/webhook", capture_handler)

        headers = {"Content-Type": "text/plain"}
        body = b'plain text body'

        await handle_webhook_request("/raw/webhook", headers, body)

        assert "raw_body" in received_data
        assert received_data["raw_body"] == "plain text body"


class TestWebhookLogging:
    """Tests for webhook activity logging."""

    @pytest.mark.asyncio
    async def test_logs_successful_webhook(self, webhook_registry):
        """Test that successful webhooks are logged."""
        handler = AsyncMock(return_value={"ok": True})
        register_webhook("/logged", handler)

        await handle_webhook_request(
            "/logged",
            {"Content-Type": "application/json"},
            b'{"test": true}'
        )

        logs = get_webhook_logs(limit=10)

        assert len(logs) >= 1
        latest = logs[0]
        assert latest["path"] == "/logged"
        assert latest["success"] is True
        assert "timestamp" in latest

    @pytest.mark.asyncio
    async def test_logs_failed_webhook(self, webhook_registry):
        """Test that failed webhooks are logged."""
        handler = AsyncMock(side_effect=Exception("Boom"))
        register_webhook("/failing", handler)

        await handle_webhook_request(
            "/failing",
            {"Content-Type": "application/json"},
            b'{}'
        )

        logs = get_webhook_logs(limit=10)

        assert len(logs) >= 1
        latest = logs[0]
        assert latest["path"] == "/failing"
        assert latest["success"] is False
        assert "error" in latest

    @pytest.mark.asyncio
    async def test_log_limit(self, webhook_registry):
        """Test that log limit is respected."""
        handler = AsyncMock(return_value={})
        register_webhook("/multi", handler)

        # Generate multiple log entries
        for i in range(10):
            await handle_webhook_request(
                "/multi",
                {},
                b'{}'
            )

        logs = get_webhook_logs(limit=5)
        assert len(logs) == 5

    @pytest.mark.asyncio
    async def test_logs_include_metadata(self, webhook_registry):
        """Test that logs include useful metadata."""
        handler = AsyncMock(return_value={"result": "data"})
        register_webhook("/meta", handler)

        await handle_webhook_request(
            "/meta",
            {
                "Content-Type": "application/json",
                "User-Agent": "TestAgent/1.0",
            },
            b'{"event_type": "test.event"}'
        )

        logs = get_webhook_logs(limit=1)
        assert len(logs) == 1
        log = logs[0]

        assert "path" in log
        assert "timestamp" in log
        assert "status_code" in log


class TestWebhookResponse:
    """Tests for WebhookResponse data class."""

    def test_response_creation(self):
        """Test creating a webhook response."""
        if not IMPORTS_AVAILABLE:
            pytest.skip("Module not yet implemented")

        response = WebhookResponse(
            status_code=200,
            body={"success": True, "message": "Processed"}
        )

        assert response.status_code == 200
        assert response.body["success"] is True

    def test_response_error(self):
        """Test creating an error response."""
        if not IMPORTS_AVAILABLE:
            pytest.skip("Module not yet implemented")

        response = WebhookResponse(
            status_code=400,
            body={"success": False, "error": "Bad request"}
        )

        assert response.status_code == 400
        assert response.body["success"] is False


class TestIntegration:
    """Integration tests for the webhook handler."""

    @pytest.mark.asyncio
    async def test_full_webhook_flow(self, webhook_registry):
        """Test complete webhook flow from registration to handling."""
        events_received = []

        async def event_handler(data: Dict[str, Any]) -> Dict[str, Any]:
            events_received.append(data)
            return {"received": True, "event_id": data.get("id")}

        # Register webhook
        secret = "integration-test-secret"
        register_webhook("/events", event_handler, secret=secret)

        # Create valid signed request
        body = b'{"id": "evt_123", "type": "order.created"}'
        signature = hmac.new(
            secret.encode(),
            body,
            hashlib.sha256
        ).hexdigest()

        headers = {
            "Content-Type": "application/json",
            "X-Webhook-Signature": f"sha256={signature}",
        }

        # Handle request
        response = await handle_webhook_request("/events", headers, body)

        # Verify
        assert response.status_code == 200
        assert len(events_received) == 1
        assert events_received[0]["id"] == "evt_123"

        # Check logs
        logs = get_webhook_logs(limit=1)
        assert logs[0]["path"] == "/events"
        assert logs[0]["success"] is True

    @pytest.mark.asyncio
    async def test_multiple_webhooks(self, webhook_registry):
        """Test handling multiple different webhooks."""
        orders = []
        users = []

        async def order_handler(data):
            orders.append(data)
            return {"type": "order"}

        async def user_handler(data):
            users.append(data)
            return {"type": "user"}

        register_webhook("/orders", order_handler)
        register_webhook("/users", user_handler)

        await handle_webhook_request("/orders", {}, b'{"order_id": 1}')
        await handle_webhook_request("/users", {}, b'{"user_id": 2}')
        await handle_webhook_request("/orders", {}, b'{"order_id": 3}')

        assert len(orders) == 2
        assert len(users) == 1
        assert orders[0]["order_id"] == 1
        assert orders[1]["order_id"] == 3
        assert users[0]["user_id"] == 2
