"""Webhook delivery with retry and signing."""
import hmac
import hashlib
import json
import time
import asyncio
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

try:
    import aiohttp
    HAS_AIOHTTP = True
except ImportError:
    HAS_AIOHTTP = False


class DeliveryStatus(str, Enum):
    PENDING = "pending"
    DELIVERED = "delivered"
    FAILED = "failed"
    RETRYING = "retrying"


@dataclass
class WebhookDelivery:
    id: str
    url: str
    event: str
    payload: Dict[str, Any]
    secret: str = ""
    status: DeliveryStatus = DeliveryStatus.PENDING
    attempts: int = 0
    max_attempts: int = 5
    created_at: float = field(default_factory=time.time)
    last_attempt: float = 0
    response_code: int = 0
    error_message: str = ""


class WebhookManager:
    """Manage webhook subscriptions and delivery."""
    
    def __init__(self, max_concurrent: int = 10):
        self.subscriptions: Dict[str, List[Dict]] = {}
        self.pending: List[WebhookDelivery] = []
        self.max_concurrent = max_concurrent
        self._delivery_log_path = Path("logs/webhooks.jsonl")
    
    def subscribe(self, event: str, url: str, secret: str = ""):
        if event not in self.subscriptions:
            self.subscriptions[event] = []
        self.subscriptions[event].append({"url": url, "secret": secret})
        logger.info(f"Webhook subscribed: {event} -> {url}")
    
    def unsubscribe(self, event: str, url: str):
        if event in self.subscriptions:
            self.subscriptions[event] = [s for s in self.subscriptions[event] if s["url"] != url]
    
    async def trigger(self, event: str, payload: Dict[str, Any]):
        if event not in self.subscriptions:
            return
        
        for sub in self.subscriptions[event]:
            delivery = WebhookDelivery(
                id=f"{event}_{int(time.time()*1000)}",
                url=sub["url"],
                event=event,
                payload=payload,
                secret=sub.get("secret", "")
            )
            await self._deliver(delivery)
    
    async def _deliver(self, delivery: WebhookDelivery):
        if not HAS_AIOHTTP:
            logger.error("aiohttp not installed, cannot deliver webhook")
            return
        
        body = json.dumps({"event": delivery.event, "data": delivery.payload, "timestamp": time.time()})
        headers = {"Content-Type": "application/json"}
        
        if delivery.secret:
            signature = hmac.new(delivery.secret.encode(), body.encode(), hashlib.sha256).hexdigest()
            headers["X-Webhook-Signature"] = f"sha256={signature}"
        
        delivery.attempts += 1
        delivery.last_attempt = time.time()
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(delivery.url, data=body, headers=headers, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                    delivery.response_code = resp.status
                    if 200 <= resp.status < 300:
                        delivery.status = DeliveryStatus.DELIVERED
                        logger.info(f"Webhook delivered: {delivery.event} -> {delivery.url}")
                    else:
                        raise Exception(f"HTTP {resp.status}")
        except Exception as e:
            delivery.error_message = str(e)
            if delivery.attempts < delivery.max_attempts:
                delivery.status = DeliveryStatus.RETRYING
                self.pending.append(delivery)
                delay = min(300, 2 ** delivery.attempts)
                asyncio.create_task(self._retry_later(delivery, delay))
            else:
                delivery.status = DeliveryStatus.FAILED
                logger.error(f"Webhook failed permanently: {delivery.event} -> {delivery.url}: {e}")
        
        self._log_delivery(delivery)
    
    async def _retry_later(self, delivery: WebhookDelivery, delay: float):
        await asyncio.sleep(delay)
        if delivery in self.pending:
            self.pending.remove(delivery)
            await self._deliver(delivery)
    
    def _log_delivery(self, delivery: WebhookDelivery):
        self._delivery_log_path.parent.mkdir(parents=True, exist_ok=True)
        log_entry = {
            "id": delivery.id, "event": delivery.event, "url": delivery.url,
            "status": delivery.status.value, "attempts": delivery.attempts,
            "response_code": delivery.response_code, "timestamp": time.time()
        }
        with open(self._delivery_log_path, "a") as f:
            f.write(json.dumps(log_entry) + "\n")


webhook_manager = WebhookManager()
