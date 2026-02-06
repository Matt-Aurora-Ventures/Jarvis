"""
Webhook Handler for ClawdBots.

Provides inbound webhook handling for ClawdBots to receive events from
external services (GitHub, payment processors, monitoring tools, etc.).

Features:
- Simple webhook registration with path routing
- HMAC signature validation (SHA256)
- Timestamp-based replay protection
- Activity logging to JSON file

Usage:
    from bots.shared.webhook_handler import (
        register_webhook,
        handle_webhook_request,
        validate_signature,
        get_webhook_logs,
    )

    # Register a webhook handler
    async def my_handler(data: dict) -> dict:
        # Process the webhook payload
        return {"status": "processed"}

    register_webhook("/github/push", my_handler, secret="my-secret")

    # In your HTTP server (aiohttp, Flask, FastAPI, etc.):
    response = await handle_webhook_request(
        path="/github/push",
        headers=request.headers,
        body=await request.read()
    )
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Awaitable, Callable, Dict, List, Optional, Union

logger = logging.getLogger(__name__)

# Default log path - can be overridden per instance
DEFAULT_LOG_PATH = Path("/root/clawdbots/webhook_logs.json")

# For Windows development, use a local path if /root doesn't exist
if not DEFAULT_LOG_PATH.parent.exists():
    DEFAULT_LOG_PATH = Path(__file__).parent.parent.parent / "data" / "webhook_logs.json"


# Type alias for webhook handlers
WebhookHandler = Callable[[Dict[str, Any]], Awaitable[Dict[str, Any]]]


@dataclass
class WebhookResponse:
    """Response from handling a webhook request."""

    status_code: int
    body: Dict[str, Any]
    headers: Dict[str, str] = field(default_factory=lambda: {
        "Content-Type": "application/json"
    })

    def to_json(self) -> str:
        """Serialize body to JSON string."""
        return json.dumps(self.body)


@dataclass
class WebhookConfig:
    """Configuration for a registered webhook."""

    path: str
    handler: WebhookHandler
    secret: Optional[str] = None
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        """Return serializable dict (excludes handler)."""
        return {
            "path": self.path,
            "secret": self.secret,
            "created_at": self.created_at,
        }


class WebhookRegistry:
    """
    Singleton registry for webhook handlers.

    Manages webhook registration, signature validation, and logging.
    """

    _instance: Optional[WebhookRegistry] = None

    def __init__(self):
        self._webhooks: Dict[str, WebhookConfig] = {}
        self._log_path: Path = DEFAULT_LOG_PATH
        self._logs: List[Dict[str, Any]] = []
        self._max_log_entries = 1000  # Keep last 1000 entries in memory

    @classmethod
    def get_instance(cls) -> WebhookRegistry:
        """Get the singleton instance."""
        if cls._instance is None:
            cls._instance = WebhookRegistry()
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """Reset singleton (for testing)."""
        cls._instance = None

    def register(
        self,
        path: str,
        handler: WebhookHandler,
        secret: Optional[str] = None,
    ) -> None:
        """
        Register a webhook handler for a path.

        Args:
            path: URL path to listen on (e.g., "/github/webhook")
            handler: Async function to call when webhook is received
            secret: Optional HMAC secret for signature validation
        """
        config = WebhookConfig(
            path=path,
            handler=handler,
            secret=secret,
        )
        self._webhooks[path] = config
        logger.info(f"Registered webhook: {path} (secret: {'yes' if secret else 'no'})")

    def unregister(self, path: str) -> bool:
        """
        Unregister a webhook handler.

        Args:
            path: URL path to unregister

        Returns:
            True if webhook was found and removed, False otherwise
        """
        if path in self._webhooks:
            del self._webhooks[path]
            logger.info(f"Unregistered webhook: {path}")
            return True
        return False

    def get_webhook(self, path: str) -> Optional[WebhookConfig]:
        """Get webhook config for a path."""
        return self._webhooks.get(path)

    def get_all_webhooks(self) -> Dict[str, Dict[str, Any]]:
        """Get all registered webhooks as serializable dict."""
        return {
            path: config.to_dict()
            for path, config in self._webhooks.items()
        }

    def clear(self) -> None:
        """Clear all registered webhooks."""
        self._webhooks.clear()
        self._logs.clear()

    async def handle_request(
        self,
        path: str,
        headers: Dict[str, str],
        body: bytes,
    ) -> WebhookResponse:
        """
        Handle an incoming webhook request.

        Args:
            path: Request path
            headers: Request headers
            body: Raw request body

        Returns:
            WebhookResponse with status code and response body
        """
        start_time = time.time()
        log_entry = {
            "path": path,
            "timestamp": datetime.utcnow().isoformat(),
            "success": False,
            "status_code": 0,
        }

        try:
            # Find handler
            config = self.get_webhook(path)
            if config is None:
                log_entry["status_code"] = 404
                log_entry["error"] = "Webhook not found"
                self._add_log(log_entry)
                return WebhookResponse(
                    status_code=404,
                    body={"success": False, "error": "Webhook not found"}
                )

            # Validate signature if secret is configured
            if config.secret:
                if not self._validate_signature(headers, body, config.secret):
                    log_entry["status_code"] = 401
                    log_entry["error"] = "Invalid signature"
                    self._add_log(log_entry)
                    return WebhookResponse(
                        status_code=401,
                        body={"success": False, "error": "Invalid signature"}
                    )

            # Parse body
            data = self._parse_body(body, headers)

            # Call handler
            try:
                result = await config.handler(data)
            except Exception as e:
                logger.exception(f"Webhook handler error for {path}")
                log_entry["status_code"] = 500
                log_entry["error"] = str(e)
                self._add_log(log_entry)
                return WebhookResponse(
                    status_code=500,
                    body={"success": False, "error": str(e)}
                )

            # Success
            log_entry["success"] = True
            log_entry["status_code"] = 200
            log_entry["duration_ms"] = round((time.time() - start_time) * 1000, 2)
            self._add_log(log_entry)

            return WebhookResponse(
                status_code=200,
                body={"success": True, "result": result}
            )

        except Exception as e:
            logger.exception(f"Unexpected error handling webhook {path}")
            log_entry["status_code"] = 500
            log_entry["error"] = str(e)
            self._add_log(log_entry)
            return WebhookResponse(
                status_code=500,
                body={"success": False, "error": str(e)}
            )

    def _validate_signature(
        self,
        headers: Dict[str, str],
        body: bytes,
        secret: str,
        tolerance_seconds: int = 300,
    ) -> bool:
        """
        Validate HMAC signature from headers.

        Supports two signature formats:
        1. Simple: X-Webhook-Signature: sha256=<hex>
        2. With timestamp: X-Webhook-Timestamp + signature over timestamp.body

        Args:
            headers: Request headers
            body: Raw request body
            secret: HMAC secret
            tolerance_seconds: Max age of timestamp (default 5 min)

        Returns:
            True if signature is valid, False otherwise
        """
        # Normalize header keys to lowercase for comparison
        headers_lower = {k.lower(): v for k, v in headers.items()}

        signature_header = headers_lower.get("x-webhook-signature")
        if not signature_header:
            return False

        # Parse signature (format: sha256=<hex>)
        if not signature_header.startswith("sha256="):
            return False
        provided_sig = signature_header[7:]  # Remove "sha256=" prefix

        # Check for timestamp (replay protection)
        timestamp = headers_lower.get("x-webhook-timestamp")
        if timestamp:
            # Validate timestamp is recent
            try:
                ts = int(timestamp)
                if abs(time.time() - ts) > tolerance_seconds:
                    logger.warning(f"Webhook timestamp expired: {timestamp}")
                    return False
            except ValueError:
                return False

            # Signature over timestamp.body
            message = f"{timestamp}.{body.decode()}"
            expected_sig = hmac.new(
                secret.encode(),
                message.encode(),
                hashlib.sha256
            ).hexdigest()
        else:
            # Simple signature over body only
            expected_sig = hmac.new(
                secret.encode(),
                body,
                hashlib.sha256
            ).hexdigest()

        return hmac.compare_digest(provided_sig, expected_sig)

    def _parse_body(
        self,
        body: bytes,
        headers: Dict[str, str],
    ) -> Dict[str, Any]:
        """
        Parse request body based on content type.

        Args:
            body: Raw request body
            headers: Request headers

        Returns:
            Parsed body as dict
        """
        headers_lower = {k.lower(): v for k, v in headers.items()}
        content_type = headers_lower.get("content-type", "")

        # Try JSON parsing if content-type is JSON or not specified
        if "application/json" in content_type or not content_type:
            try:
                return json.loads(body.decode())
            except json.JSONDecodeError:
                # If no content-type and not valid JSON, treat as raw
                if not content_type:
                    pass  # Fall through to raw handling
                else:
                    return {"raw_body": body.decode(), "parse_error": "Invalid JSON"}

        # Non-JSON body - wrap in dict
        return {"raw_body": body.decode()}

    def _add_log(self, entry: Dict[str, Any]) -> None:
        """Add log entry and persist to file."""
        self._logs.insert(0, entry)

        # Trim in-memory logs
        if len(self._logs) > self._max_log_entries:
            self._logs = self._logs[:self._max_log_entries]

        # Persist to file
        self._save_logs()

    def _save_logs(self) -> None:
        """Save logs to JSON file."""
        try:
            self._log_path.parent.mkdir(parents=True, exist_ok=True)
            # Only persist last 500 entries to file
            with open(self._log_path, "w") as f:
                json.dump(self._logs[:500], f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save webhook logs: {e}")

    def _load_logs(self) -> None:
        """Load logs from file."""
        try:
            if self._log_path.exists():
                with open(self._log_path, "r") as f:
                    self._logs = json.load(f)
        except Exception as e:
            logger.error(f"Failed to load webhook logs: {e}")
            self._logs = []

    def get_logs(self, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Get recent webhook activity logs.

        Args:
            limit: Maximum number of entries to return

        Returns:
            List of log entries, newest first
        """
        return self._logs[:limit]


# ============================================
# PUBLIC API - CONVENIENCE FUNCTIONS
# ============================================

def register_webhook(
    path: str,
    handler: WebhookHandler,
    secret: Optional[str] = None,
) -> None:
    """
    Register a webhook handler for a URL path.

    Args:
        path: URL path to listen on (e.g., "/github/push")
        handler: Async function to call with parsed body
        secret: Optional HMAC secret for signature validation

    Example:
        async def on_github_push(data: dict) -> dict:
            print(f"Push to {data['repository']['name']}")
            return {"acknowledged": True}

        register_webhook("/github/push", on_github_push, secret="github-secret")
    """
    WebhookRegistry.get_instance().register(path, handler, secret)


def unregister_webhook(path: str) -> bool:
    """
    Unregister a webhook handler.

    Args:
        path: URL path to unregister

    Returns:
        True if webhook was found and removed
    """
    return WebhookRegistry.get_instance().unregister(path)


async def handle_webhook_request(
    path: str,
    headers: Dict[str, str],
    body: bytes,
) -> WebhookResponse:
    """
    Handle an incoming webhook request.

    Args:
        path: Request path (e.g., "/github/push")
        headers: Request headers dict
        body: Raw request body bytes

    Returns:
        WebhookResponse with status_code and body

    Example (with aiohttp):
        async def webhook_route(request):
            response = await handle_webhook_request(
                path=request.path,
                headers=dict(request.headers),
                body=await request.read()
            )
            return web.json_response(
                response.body,
                status=response.status_code
            )
    """
    return await WebhookRegistry.get_instance().handle_request(path, headers, body)


def validate_signature(
    headers: Dict[str, str],
    body: bytes,
    secret: Optional[str],
    tolerance_seconds: int = 300,
) -> bool:
    """
    Validate webhook signature from headers.

    Args:
        headers: Request headers
        body: Raw request body
        secret: HMAC secret (None = no validation required)
        tolerance_seconds: Max age for timestamp validation

    Returns:
        True if signature is valid (or no secret required)

    Signature format:
        X-Webhook-Signature: sha256=<hex-digest>
        X-Webhook-Timestamp: <unix-timestamp> (optional, for replay protection)
    """
    if secret is None:
        return True

    registry = WebhookRegistry.get_instance()
    return registry._validate_signature(headers, body, secret, tolerance_seconds)


def get_webhook_logs(limit: int = 50) -> List[Dict[str, Any]]:
    """
    Get recent webhook activity logs.

    Args:
        limit: Maximum entries to return (default 50)

    Returns:
        List of log entries with path, timestamp, success, etc.
    """
    return WebhookRegistry.get_instance().get_logs(limit)


def get_registered_webhooks() -> Dict[str, Dict[str, Any]]:
    """
    Get all registered webhooks.

    Returns:
        Dict mapping path to webhook config
    """
    return WebhookRegistry.get_instance().get_all_webhooks()


def clear_webhooks() -> None:
    """Clear all registered webhooks and logs (for testing)."""
    WebhookRegistry.reset_instance()


# ============================================
# EXAMPLE HTTP SERVER INTEGRATION
# ============================================

def create_aiohttp_handler():
    """
    Create an aiohttp handler for webhooks.

    Usage:
        from aiohttp import web
        from bots.shared.webhook_handler import create_aiohttp_handler

        app = web.Application()
        app.router.add_post('/webhook/{path:.*}', create_aiohttp_handler())

    Returns:
        aiohttp request handler function
    """
    try:
        from aiohttp import web
    except ImportError:
        raise ImportError("aiohttp required: pip install aiohttp")

    async def webhook_handler(request):
        # Extract path after /webhook/
        path = "/" + request.match_info.get("path", "")
        headers = dict(request.headers)
        body = await request.read()

        response = await handle_webhook_request(path, headers, body)

        return web.json_response(
            response.body,
            status=response.status_code,
            headers=response.headers
        )

    return webhook_handler


# ============================================
# CLI FOR TESTING
# ============================================

if __name__ == "__main__":
    import asyncio

    async def test_handler(data: Dict[str, Any]) -> Dict[str, Any]:
        print(f"Received webhook: {data}")
        return {"processed": True, "received_keys": list(data.keys())}

    async def main():
        # Register test webhook
        register_webhook("/test", test_handler)
        register_webhook("/secure", test_handler, secret="test-secret")

        print("Registered webhooks:", get_registered_webhooks())

        # Test without auth
        response = await handle_webhook_request(
            "/test",
            {"Content-Type": "application/json"},
            b'{"event": "test", "value": 123}'
        )
        print(f"\nTest response: {response.status_code} - {response.body}")

        # Test with valid auth
        body = b'{"event": "secure"}'
        sig = hmac.new(b"test-secret", body, hashlib.sha256).hexdigest()
        response = await handle_webhook_request(
            "/secure",
            {
                "Content-Type": "application/json",
                "X-Webhook-Signature": f"sha256={sig}",
            },
            body
        )
        print(f"Secure response: {response.status_code} - {response.body}")

        # Test with invalid auth
        response = await handle_webhook_request(
            "/secure",
            {
                "Content-Type": "application/json",
                "X-Webhook-Signature": "sha256=invalid",
            },
            body
        )
        print(f"Invalid auth response: {response.status_code} - {response.body}")

        # Test 404
        response = await handle_webhook_request("/unknown", {}, b'{}')
        print(f"404 response: {response.status_code} - {response.body}")

        # Show logs
        print("\nWebhook logs:")
        for log in get_webhook_logs(limit=10):
            print(f"  {log['path']}: {log['status_code']} - {log.get('error', 'OK')}")

    asyncio.run(main())
