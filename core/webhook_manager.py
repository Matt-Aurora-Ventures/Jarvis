"""
Webhook Manager for JARVIS.

Handles outbound webhook notifications to external services:
- Discord (trading alerts, system status)
- Slack (team notifications)
- Custom HTTP endpoints
- Telegram (already integrated elsewhere)

Supports retry logic, rate limiting, and batching.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional
from enum import Enum
import aiohttp

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[1]
WEBHOOK_CONFIG_PATH = ROOT / "data" / "webhook_config.json"
WEBHOOK_LOG_PATH = ROOT / "data" / "webhook_log.jsonl"


class WebhookType(Enum):
    """Supported webhook types."""
    DISCORD = "discord"
    SLACK = "slack"
    TELEGRAM = "telegram"
    CUSTOM = "custom"


class EventType(Enum):
    """Types of events that can trigger webhooks."""
    TRADE_EXECUTED = "trade_executed"
    TRADE_ALERT = "trade_alert"
    PRICE_ALERT = "price_alert"
    SENTIMENT_REPORT = "sentiment_report"
    SYSTEM_STATUS = "system_status"
    ERROR = "error"
    MILESTONE = "milestone"
    DAILY_SUMMARY = "daily_summary"
    CUSTOM = "custom"


@dataclass
class WebhookConfig:
    """Configuration for a webhook endpoint."""
    id: str
    name: str
    webhook_type: WebhookType
    url: str
    enabled: bool = True
    events: List[EventType] = field(default_factory=list)
    rate_limit_per_minute: int = 30
    retry_count: int = 3
    retry_delay_seconds: float = 1.0
    custom_headers: Dict[str, str] = field(default_factory=dict)
    template: Optional[str] = None  # Custom message template

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "webhook_type": self.webhook_type.value,
            "url": self.url,
            "enabled": self.enabled,
            "events": [e.value for e in self.events],
            "rate_limit_per_minute": self.rate_limit_per_minute,
            "retry_count": self.retry_count,
            "retry_delay_seconds": self.retry_delay_seconds,
            "custom_headers": self.custom_headers,
            "template": self.template,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> WebhookConfig:
        return cls(
            id=data["id"],
            name=data["name"],
            webhook_type=WebhookType(data["webhook_type"]),
            url=data["url"],
            enabled=data.get("enabled", True),
            events=[EventType(e) for e in data.get("events", [])],
            rate_limit_per_minute=data.get("rate_limit_per_minute", 30),
            retry_count=data.get("retry_count", 3),
            retry_delay_seconds=data.get("retry_delay_seconds", 1.0),
            custom_headers=data.get("custom_headers", {}),
            template=data.get("template"),
        )


@dataclass
class WebhookPayload:
    """Payload for a webhook notification."""
    event_type: EventType
    title: str
    message: str
    data: Dict[str, Any] = field(default_factory=dict)
    color: Optional[int] = None  # For Discord embeds
    timestamp: float = field(default_factory=time.time)

    def to_discord_embed(self) -> Dict[str, Any]:
        """Format as Discord embed."""
        embed = {
            "title": self.title,
            "description": self.message,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(self.timestamp)),
        }

        if self.color:
            embed["color"] = self.color

        # Add fields from data
        if self.data:
            embed["fields"] = []
            for key, value in self.data.items():
                embed["fields"].append({
                    "name": key.replace("_", " ").title(),
                    "value": str(value),
                    "inline": True,
                })

        return {"embeds": [embed]}

    def to_slack_message(self) -> Dict[str, Any]:
        """Format as Slack message with blocks."""
        blocks = [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": self.title}
            },
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": self.message}
            }
        ]

        # Add fields from data
        if self.data:
            fields = []
            for key, value in self.data.items():
                fields.append({
                    "type": "mrkdwn",
                    "text": f"*{key.replace('_', ' ').title()}:* {value}"
                })
            if fields:
                blocks.append({
                    "type": "section",
                    "fields": fields[:10]  # Slack max 10 fields
                })

        return {"blocks": blocks}

    def to_custom_json(self) -> Dict[str, Any]:
        """Format as generic JSON."""
        return {
            "event": self.event_type.value,
            "title": self.title,
            "message": self.message,
            "data": self.data,
            "timestamp": self.timestamp,
        }


class WebhookManager:
    """
    Manages webhook notifications for JARVIS.

    Features:
    - Multiple webhook endpoints
    - Event-based routing
    - Rate limiting
    - Retry logic
    - Logging
    """

    def __init__(self):
        self.webhooks: Dict[str, WebhookConfig] = {}
        self._rate_limiters: Dict[str, List[float]] = {}
        self._session: Optional[aiohttp.ClientSession] = None
        self._load_config()

    def _load_config(self) -> None:
        """Load webhook configurations from file."""
        if not WEBHOOK_CONFIG_PATH.exists():
            return

        try:
            data = json.loads(WEBHOOK_CONFIG_PATH.read_text())
            for webhook_data in data.get("webhooks", []):
                webhook = WebhookConfig.from_dict(webhook_data)
                self.webhooks[webhook.id] = webhook
            logger.info(f"Loaded {len(self.webhooks)} webhook configurations")
        except Exception as e:
            logger.error(f"Failed to load webhook config: {e}")

    def _save_config(self) -> None:
        """Save webhook configurations to file."""
        try:
            WEBHOOK_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
            data = {
                "webhooks": [w.to_dict() for w in self.webhooks.values()],
                "updated_at": time.time(),
            }
            WEBHOOK_CONFIG_PATH.write_text(json.dumps(data, indent=2))
        except Exception as e:
            logger.error(f"Failed to save webhook config: {e}")

    def add_webhook(self, config: WebhookConfig) -> None:
        """Add or update a webhook configuration."""
        self.webhooks[config.id] = config
        self._save_config()
        logger.info(f"Added webhook: {config.name} ({config.id})")

    def remove_webhook(self, webhook_id: str) -> bool:
        """Remove a webhook configuration."""
        if webhook_id in self.webhooks:
            del self.webhooks[webhook_id]
            self._save_config()
            logger.info(f"Removed webhook: {webhook_id}")
            return True
        return False

    def get_webhook(self, webhook_id: str) -> Optional[WebhookConfig]:
        """Get a webhook configuration by ID."""
        return self.webhooks.get(webhook_id)

    def list_webhooks(self) -> List[WebhookConfig]:
        """List all webhook configurations."""
        return list(self.webhooks.values())

    def _is_rate_limited(self, webhook_id: str, limit: int) -> bool:
        """Check if webhook is rate limited."""
        now = time.time()
        if webhook_id not in self._rate_limiters:
            self._rate_limiters[webhook_id] = []

        # Remove timestamps older than 1 minute
        self._rate_limiters[webhook_id] = [
            t for t in self._rate_limiters[webhook_id]
            if now - t < 60
        ]

        return len(self._rate_limiters[webhook_id]) >= limit

    def _record_request(self, webhook_id: str) -> None:
        """Record a request for rate limiting."""
        if webhook_id not in self._rate_limiters:
            self._rate_limiters[webhook_id] = []
        self._rate_limiters[webhook_id].append(time.time())

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=30)
            )
        return self._session

    async def _send_webhook(
        self,
        webhook: WebhookConfig,
        payload: WebhookPayload,
    ) -> bool:
        """Send a single webhook notification."""
        if not webhook.enabled:
            return False

        if self._is_rate_limited(webhook.id, webhook.rate_limit_per_minute):
            logger.warning(f"Webhook {webhook.id} is rate limited")
            return False

        # Format payload based on webhook type
        if webhook.webhook_type == WebhookType.DISCORD:
            body = payload.to_discord_embed()
        elif webhook.webhook_type == WebhookType.SLACK:
            body = payload.to_slack_message()
        else:
            body = payload.to_custom_json()

        # Apply custom template if specified
        if webhook.template:
            try:
                body = {"content": webhook.template.format(**payload.__dict__, **payload.data)}
            except Exception:
                pass

        session = await self._get_session()
        headers = {"Content-Type": "application/json", **webhook.custom_headers}

        for attempt in range(webhook.retry_count):
            try:
                self._record_request(webhook.id)

                async with session.post(webhook.url, json=body, headers=headers) as resp:
                    if resp.status in (200, 201, 204):
                        self._log_webhook(webhook, payload, True)
                        return True
                    else:
                        text = await resp.text()
                        logger.warning(
                            f"Webhook {webhook.id} failed ({resp.status}): {text[:200]}"
                        )
            except Exception as e:
                logger.error(f"Webhook {webhook.id} error: {e}")

            if attempt < webhook.retry_count - 1:
                await asyncio.sleep(webhook.retry_delay_seconds * (attempt + 1))

        self._log_webhook(webhook, payload, False)
        return False

    def _log_webhook(
        self,
        webhook: WebhookConfig,
        payload: WebhookPayload,
        success: bool,
    ) -> None:
        """Log webhook delivery attempt."""
        try:
            WEBHOOK_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
            log_entry = {
                "timestamp": time.time(),
                "webhook_id": webhook.id,
                "webhook_name": webhook.name,
                "event_type": payload.event_type.value,
                "title": payload.title,
                "success": success,
            }
            with open(WEBHOOK_LOG_PATH, "a") as f:
                f.write(json.dumps(log_entry) + "\n")
        except Exception as e:
            logger.error(f"Failed to log webhook: {e}")

    async def notify(
        self,
        event_type: EventType,
        title: str,
        message: str,
        data: Optional[Dict[str, Any]] = None,
        color: Optional[int] = None,
        webhook_ids: Optional[List[str]] = None,
    ) -> Dict[str, bool]:
        """
        Send notification to all relevant webhooks.

        Args:
            event_type: Type of event
            title: Notification title
            message: Notification message
            data: Additional data fields
            color: Color for embeds (Discord)
            webhook_ids: Specific webhooks to notify (None = all matching)

        Returns:
            Dict of webhook_id -> success status
        """
        payload = WebhookPayload(
            event_type=event_type,
            title=title,
            message=message,
            data=data or {},
            color=color,
        )

        results = {}
        tasks = []

        for webhook in self.webhooks.values():
            # Skip if not in specific list
            if webhook_ids and webhook.id not in webhook_ids:
                continue

            # Skip if event type not configured for this webhook
            if webhook.events and event_type not in webhook.events:
                continue

            tasks.append((webhook.id, self._send_webhook(webhook, payload)))

        if tasks:
            done = await asyncio.gather(*[t[1] for t in tasks], return_exceptions=True)
            for i, (webhook_id, _) in enumerate(tasks):
                if isinstance(done[i], Exception):
                    results[webhook_id] = False
                else:
                    results[webhook_id] = done[i]

        return results

    async def notify_trade(
        self,
        symbol: str,
        side: str,
        amount: float,
        price: float,
        pnl_pct: Optional[float] = None,
        is_paper: bool = True,
    ) -> Dict[str, bool]:
        """Send trade notification to webhooks."""
        color = 0x00FF00 if side.lower() == "buy" else 0xFF0000  # Green/Red
        if pnl_pct is not None:
            color = 0x00FF00 if pnl_pct > 0 else 0xFF0000

        data = {
            "symbol": symbol,
            "side": side.upper(),
            "amount": f"${amount:.2f}",
            "price": f"${price:.8f}",
            "mode": "Paper" if is_paper else "Live",
        }

        if pnl_pct is not None:
            data["pnl"] = f"{pnl_pct:+.2f}%"

        return await self.notify(
            event_type=EventType.TRADE_EXECUTED,
            title=f"Trade Executed: {side.upper()} {symbol}",
            message=f"{'Paper' if is_paper else 'Live'} trade on {symbol}",
            data=data,
            color=color,
        )

    async def notify_alert(
        self,
        symbol: str,
        alert_type: str,
        message: str,
        price: Optional[float] = None,
    ) -> Dict[str, bool]:
        """Send price/trading alert to webhooks."""
        data = {"symbol": symbol, "alert": alert_type}
        if price:
            data["price"] = f"${price:.8f}"

        return await self.notify(
            event_type=EventType.PRICE_ALERT,
            title=f"Alert: {symbol}",
            message=message,
            data=data,
            color=0xFFAA00,  # Orange
        )

    async def notify_error(
        self,
        component: str,
        error: str,
        details: Optional[str] = None,
    ) -> Dict[str, bool]:
        """Send error notification to webhooks."""
        data = {"component": component}
        if details:
            data["details"] = details[:200]

        return await self.notify(
            event_type=EventType.ERROR,
            title=f"Error in {component}",
            message=error,
            data=data,
            color=0xFF0000,  # Red
        )

    async def notify_milestone(
        self,
        title: str,
        description: str,
        data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, bool]:
        """Send milestone notification to webhooks."""
        return await self.notify(
            event_type=EventType.MILESTONE,
            title=title,
            message=description,
            data=data or {},
            color=0x00AAFF,  # Blue
        )

    async def close(self) -> None:
        """Close the aiohttp session."""
        if self._session and not self._session.closed:
            await self._session.close()


# Singleton instance
_webhook_manager: Optional[WebhookManager] = None


def get_webhook_manager() -> WebhookManager:
    """Get the singleton WebhookManager instance."""
    global _webhook_manager
    if _webhook_manager is None:
        _webhook_manager = WebhookManager()
    return _webhook_manager


# Convenience functions for common notifications
async def notify_trade(
    symbol: str,
    side: str,
    amount: float,
    price: float,
    pnl_pct: Optional[float] = None,
    is_paper: bool = True,
) -> Dict[str, bool]:
    """Send trade notification to all configured webhooks."""
    return await get_webhook_manager().notify_trade(
        symbol, side, amount, price, pnl_pct, is_paper
    )


async def notify_alert(
    symbol: str,
    alert_type: str,
    message: str,
    price: Optional[float] = None,
) -> Dict[str, bool]:
    """Send alert notification to all configured webhooks."""
    return await get_webhook_manager().notify_alert(symbol, alert_type, message, price)


async def notify_error(
    component: str,
    error: str,
    details: Optional[str] = None,
) -> Dict[str, bool]:
    """Send error notification to all configured webhooks."""
    return await get_webhook_manager().notify_error(component, error, details)


async def notify_milestone(
    title: str,
    description: str,
    data: Optional[Dict[str, Any]] = None,
) -> Dict[str, bool]:
    """Send milestone notification to all configured webhooks."""
    return await get_webhook_manager().notify_milestone(title, description, data)


# Quick setup helpers
def add_discord_webhook(
    webhook_id: str,
    name: str,
    url: str,
    events: Optional[List[EventType]] = None,
) -> WebhookConfig:
    """Quick setup for Discord webhook."""
    config = WebhookConfig(
        id=webhook_id,
        name=name,
        webhook_type=WebhookType.DISCORD,
        url=url,
        events=events or list(EventType),
    )
    get_webhook_manager().add_webhook(config)
    return config


def add_slack_webhook(
    webhook_id: str,
    name: str,
    url: str,
    events: Optional[List[EventType]] = None,
) -> WebhookConfig:
    """Quick setup for Slack webhook."""
    config = WebhookConfig(
        id=webhook_id,
        name=name,
        webhook_type=WebhookType.SLACK,
        url=url,
        events=events or list(EventType),
    )
    get_webhook_manager().add_webhook(config)
    return config


def add_custom_webhook(
    webhook_id: str,
    name: str,
    url: str,
    events: Optional[List[EventType]] = None,
    headers: Optional[Dict[str, str]] = None,
) -> WebhookConfig:
    """Quick setup for custom HTTP webhook."""
    config = WebhookConfig(
        id=webhook_id,
        name=name,
        webhook_type=WebhookType.CUSTOM,
        url=url,
        events=events or list(EventType),
        custom_headers=headers or {},
    )
    get_webhook_manager().add_webhook(config)
    return config
