"""
Alert Delivery System

Multi-channel alert delivery with retries and templating.
Supports Discord, Telegram, Email, Webhooks, and Push notifications.

Prompts #101-110: Signal & Alert Service
"""

import asyncio
import logging
import aiohttp
import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Dict, List, Any
from enum import Enum

logger = logging.getLogger(__name__)


class DeliveryChannel(str, Enum):
    """Supported delivery channels"""
    DISCORD = "discord"
    TELEGRAM = "telegram"
    EMAIL = "email"
    WEBHOOK = "webhook"
    PUSH = "push"
    SMS = "sms"


class DeliveryStatus(str, Enum):
    """Delivery status"""
    PENDING = "pending"
    SENT = "sent"
    DELIVERED = "delivered"
    FAILED = "failed"
    RETRYING = "retrying"


@dataclass
class DeliveryConfig:
    """Configuration for a delivery channel"""
    channel: DeliveryChannel
    enabled: bool = True
    endpoint: str = ""
    api_key: Optional[str] = None
    max_retries: int = 3
    retry_delay_seconds: int = 5
    timeout_seconds: int = 10
    rate_limit_per_minute: int = 60
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DeliveryResult:
    """Result of an alert delivery attempt"""
    success: bool
    channel: DeliveryChannel
    message_id: Optional[str] = None
    error: Optional[str] = None
    attempts: int = 1
    delivered_at: Optional[datetime] = None


@dataclass
class AlertMessage:
    """Formatted alert message for delivery"""
    alert_id: str
    title: str
    body: str
    severity: str  # low, medium, high, critical
    data: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)

    def to_discord_embed(self) -> Dict[str, Any]:
        """Format as Discord embed"""
        color_map = {
            "low": 0x3498db,      # Blue
            "medium": 0xf39c12,   # Orange
            "high": 0xe74c3c,     # Red
            "critical": 0x9b59b6  # Purple
        }

        return {
            "embeds": [{
                "title": self.title,
                "description": self.body,
                "color": color_map.get(self.severity, 0x3498db),
                "timestamp": self.timestamp.isoformat(),
                "footer": {"text": f"Alert ID: {self.alert_id}"},
                "fields": [
                    {"name": k, "value": str(v), "inline": True}
                    for k, v in list(self.data.items())[:6]
                ]
            }]
        }

    def to_telegram_message(self) -> str:
        """Format as Telegram message"""
        emoji_map = {
            "low": "ℹ️",
            "medium": "⚠️",
            "high": "🔴",
            "critical": "🚨"
        }

        emoji = emoji_map.get(self.severity, "📢")
        lines = [
            f"{emoji} *{self.title}*",
            "",
            self.body,
            ""
        ]

        for k, v in self.data.items():
            lines.append(f"• {k}: `{v}`")

        lines.append(f"\n_ID: {self.alert_id}_")
        return "\n".join(lines)

    def to_email_html(self) -> str:
        """Format as HTML email"""
        color_map = {
            "low": "#3498db",
            "medium": "#f39c12",
            "high": "#e74c3c",
            "critical": "#9b59b6"
        }
        color = color_map.get(self.severity, "#3498db")

        data_rows = "".join([
            f"<tr><td>{k}</td><td>{v}</td></tr>"
            for k, v in self.data.items()
        ])

        return f"""
        <html>
        <body style="font-family: Arial, sans-serif;">
            <div style="border-left: 4px solid {color}; padding: 16px; margin: 16px 0;">
                <h2 style="color: {color}; margin: 0;">{self.title}</h2>
                <p>{self.body}</p>
                <table style="width: 100%; border-collapse: collapse;">
                    {data_rows}
                </table>
                <p style="color: #666; font-size: 12px;">
                    Alert ID: {self.alert_id} | {self.timestamp.strftime('%Y-%m-%d %H:%M:%S')}
                </p>
            </div>
        </body>
        </html>
        """


class DeliveryBot(ABC):
    """Abstract base class for delivery bots"""

    def __init__(self, config: DeliveryConfig):
        self.config = config
        self.last_delivery = datetime.min
        self.delivery_count = 0

    @abstractmethod
    async def deliver(self, message: AlertMessage) -> DeliveryResult:
        """Deliver an alert message"""
        pass

    async def deliver_with_retry(self, message: AlertMessage) -> DeliveryResult:
        """Deliver with automatic retries"""
        last_error = None

        for attempt in range(1, self.config.max_retries + 1):
            try:
                result = await self.deliver(message)
                result.attempts = attempt

                if result.success:
                    return result

                last_error = result.error

            except Exception as e:
                last_error = str(e)
                logger.warning(f"Delivery attempt {attempt} failed: {e}")

            if attempt < self.config.max_retries:
                await asyncio.sleep(self.config.retry_delay_seconds)

        return DeliveryResult(
            success=False,
            channel=self.config.channel,
            error=last_error,
            attempts=self.config.max_retries
        )


class DiscordBot(DeliveryBot):
    """Discord webhook delivery bot"""

    async def deliver(self, message: AlertMessage) -> DeliveryResult:
        """Send alert via Discord webhook"""
        if not self.config.endpoint:
            return DeliveryResult(
                success=False,
                channel=DeliveryChannel.DISCORD,
                error="No webhook URL configured"
            )

        try:
            payload = message.to_discord_embed()

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.config.endpoint,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=self.config.timeout_seconds)
                ) as response:
                    if response.status in [200, 204]:
                        return DeliveryResult(
                            success=True,
                            channel=DeliveryChannel.DISCORD,
                            delivered_at=datetime.now()
                        )
                    else:
                        text = await response.text()
                        return DeliveryResult(
                            success=False,
                            channel=DeliveryChannel.DISCORD,
                            error=f"HTTP {response.status}: {text}"
                        )

        except asyncio.TimeoutError:
            return DeliveryResult(
                success=False,
                channel=DeliveryChannel.DISCORD,
                error="Request timeout"
            )
        except Exception as e:
            return DeliveryResult(
                success=False,
                channel=DeliveryChannel.DISCORD,
                error=str(e)
            )


class TelegramBot(DeliveryBot):
    """Telegram bot delivery"""

    async def deliver(self, message: AlertMessage) -> DeliveryResult:
        """Send alert via Telegram bot"""
        bot_token = self.config.api_key
        chat_id = self.config.metadata.get("chat_id")

        if not bot_token or not chat_id:
            return DeliveryResult(
                success=False,
                channel=DeliveryChannel.TELEGRAM,
                error="Bot token or chat ID not configured"
            )

        try:
            url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
            payload = {
                "chat_id": chat_id,
                "text": message.to_telegram_message(),
                "parse_mode": "Markdown"
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    url,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=self.config.timeout_seconds)
                ) as response:
                    data = await response.json()

                    if data.get("ok"):
                        return DeliveryResult(
                            success=True,
                            channel=DeliveryChannel.TELEGRAM,
                            message_id=str(data["result"]["message_id"]),
                            delivered_at=datetime.now()
                        )
                    else:
                        return DeliveryResult(
                            success=False,
                            channel=DeliveryChannel.TELEGRAM,
                            error=data.get("description", "Unknown error")
                        )

        except Exception as e:
            return DeliveryResult(
                success=False,
                channel=DeliveryChannel.TELEGRAM,
                error=str(e)
            )


class WebhookBot(DeliveryBot):
    """Generic webhook delivery bot"""

    async def deliver(self, message: AlertMessage) -> DeliveryResult:
        """Send alert via webhook"""
        if not self.config.endpoint:
            return DeliveryResult(
                success=False,
                channel=DeliveryChannel.WEBHOOK,
                error="No webhook URL configured"
            )

        try:
            payload = {
                "alert_id": message.alert_id,
                "title": message.title,
                "body": message.body,
                "severity": message.severity,
                "data": message.data,
                "timestamp": message.timestamp.isoformat()
            }

            headers = {"Content-Type": "application/json"}
            if self.config.api_key:
                headers["Authorization"] = f"Bearer {self.config.api_key}"

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.config.endpoint,
                    json=payload,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=self.config.timeout_seconds)
                ) as response:
                    if response.status in [200, 201, 202, 204]:
                        return DeliveryResult(
                            success=True,
                            channel=DeliveryChannel.WEBHOOK,
                            delivered_at=datetime.now()
                        )
                    else:
                        text = await response.text()
                        return DeliveryResult(
                            success=False,
                            channel=DeliveryChannel.WEBHOOK,
                            error=f"HTTP {response.status}: {text}"
                        )

        except Exception as e:
            return DeliveryResult(
                success=False,
                channel=DeliveryChannel.WEBHOOK,
                error=str(e)
            )


class EmailBot(DeliveryBot):
    """Email delivery bot (via SendGrid or similar)"""

    async def deliver(self, message: AlertMessage) -> DeliveryResult:
        """Send alert via email"""
        api_key = self.config.api_key
        to_email = self.config.metadata.get("to_email")
        from_email = self.config.metadata.get("from_email", "alerts@jarvis.kr8tiv.com")

        if not api_key or not to_email:
            return DeliveryResult(
                success=False,
                channel=DeliveryChannel.EMAIL,
                error="API key or recipient email not configured"
            )

        try:
            # SendGrid API
            url = "https://api.sendgrid.com/v3/mail/send"
            payload = {
                "personalizations": [{"to": [{"email": to_email}]}],
                "from": {"email": from_email},
                "subject": f"[{message.severity.upper()}] {message.title}",
                "content": [
                    {"type": "text/html", "value": message.to_email_html()}
                ]
            }

            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    url,
                    json=payload,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=self.config.timeout_seconds)
                ) as response:
                    if response.status in [200, 202]:
                        return DeliveryResult(
                            success=True,
                            channel=DeliveryChannel.EMAIL,
                            delivered_at=datetime.now()
                        )
                    else:
                        text = await response.text()
                        return DeliveryResult(
                            success=False,
                            channel=DeliveryChannel.EMAIL,
                            error=f"HTTP {response.status}: {text}"
                        )

        except Exception as e:
            return DeliveryResult(
                success=False,
                channel=DeliveryChannel.EMAIL,
                error=str(e)
            )


class PushBot(DeliveryBot):
    """Push notification delivery (via Firebase Cloud Messaging)"""

    async def deliver(self, message: AlertMessage) -> DeliveryResult:
        """Send push notification via FCM"""
        server_key = self.config.api_key
        device_token = self.config.metadata.get("device_token")

        if not server_key or not device_token:
            return DeliveryResult(
                success=False,
                channel=DeliveryChannel.PUSH,
                error="Server key or device token not configured"
            )

        try:
            url = "https://fcm.googleapis.com/fcm/send"
            payload = {
                "to": device_token,
                "notification": {
                    "title": message.title,
                    "body": message.body,
                },
                "data": {
                    "alert_id": message.alert_id,
                    "severity": message.severity,
                    **message.data
                }
            }

            headers = {
                "Authorization": f"key={server_key}",
                "Content-Type": "application/json"
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    url,
                    json=payload,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=self.config.timeout_seconds)
                ) as response:
                    data = await response.json()

                    if data.get("success", 0) > 0:
                        return DeliveryResult(
                            success=True,
                            channel=DeliveryChannel.PUSH,
                            message_id=str(data.get("results", [{}])[0].get("message_id")),
                            delivered_at=datetime.now()
                        )
                    else:
                        return DeliveryResult(
                            success=False,
                            channel=DeliveryChannel.PUSH,
                            error=data.get("results", [{}])[0].get("error", "Unknown error")
                        )

        except Exception as e:
            return DeliveryResult(
                success=False,
                channel=DeliveryChannel.PUSH,
                error=str(e)
            )


class AlertDeliveryManager:
    """
    Manages multi-channel alert delivery

    Handles routing alerts to appropriate channels based on
    user preferences and subscription tier.
    """

    def __init__(self):
        self.bots: Dict[DeliveryChannel, DeliveryBot] = {}
        self.user_preferences: Dict[str, List[DeliveryConfig]] = {}
        self.delivery_history: List[Dict[str, Any]] = []

    def register_bot(self, channel: DeliveryChannel, config: DeliveryConfig):
        """Register a delivery bot for a channel"""
        bot_classes = {
            DeliveryChannel.DISCORD: DiscordBot,
            DeliveryChannel.TELEGRAM: TelegramBot,
            DeliveryChannel.WEBHOOK: WebhookBot,
            DeliveryChannel.EMAIL: EmailBot,
            DeliveryChannel.PUSH: PushBot,
        }

        bot_class = bot_classes.get(channel)
        if bot_class:
            self.bots[channel] = bot_class(config)
            logger.info(f"Registered {channel.value} delivery bot")

    def set_user_preferences(self, user_id: str, configs: List[DeliveryConfig]):
        """Set delivery preferences for a user"""
        self.user_preferences[user_id] = configs

    async def deliver_alert(
        self,
        user_id: str,
        message: AlertMessage,
        channels: Optional[List[DeliveryChannel]] = None
    ) -> Dict[DeliveryChannel, DeliveryResult]:
        """
        Deliver alert to user across configured channels

        Args:
            user_id: User to deliver to
            message: Alert message
            channels: Specific channels (or all user channels if None)
        """
        results = {}

        # Get user's configured channels
        user_configs = self.user_preferences.get(user_id, [])

        for config in user_configs:
            if not config.enabled:
                continue

            if channels and config.channel not in channels:
                continue

            bot = self.bots.get(config.channel)
            if not bot:
                # Create bot with user-specific config
                bot_classes = {
                    DeliveryChannel.DISCORD: DiscordBot,
                    DeliveryChannel.TELEGRAM: TelegramBot,
                    DeliveryChannel.WEBHOOK: WebhookBot,
                    DeliveryChannel.EMAIL: EmailBot,
                    DeliveryChannel.PUSH: PushBot,
                }
                bot_class = bot_classes.get(config.channel)
                if bot_class:
                    bot = bot_class(config)

            if bot:
                result = await bot.deliver_with_retry(message)
                results[config.channel] = result

                # Log delivery
                self.delivery_history.append({
                    "user_id": user_id,
                    "alert_id": message.alert_id,
                    "channel": config.channel.value,
                    "success": result.success,
                    "error": result.error,
                    "attempts": result.attempts,
                    "timestamp": datetime.now().isoformat()
                })

                # Limit history size (keep last 1000 entries)
                if len(self.delivery_history) > 1000:
                    self.delivery_history = self.delivery_history[-1000:]

        return results

    async def broadcast_alert(
        self,
        message: AlertMessage,
        user_ids: List[str]
    ) -> Dict[str, Dict[DeliveryChannel, DeliveryResult]]:
        """Broadcast alert to multiple users"""
        results = {}

        tasks = [
            self.deliver_alert(user_id, message)
            for user_id in user_ids
        ]

        delivery_results = await asyncio.gather(*tasks, return_exceptions=True)

        for user_id, result in zip(user_ids, delivery_results):
            if isinstance(result, Exception):
                results[user_id] = {
                    DeliveryChannel.WEBHOOK: DeliveryResult(
                        success=False,
                        channel=DeliveryChannel.WEBHOOK,
                        error=str(result)
                    )
                }
            else:
                results[user_id] = result

        return results

    def get_delivery_stats(self) -> Dict[str, Any]:
        """Get delivery statistics"""
        total = len(self.delivery_history)
        successful = sum(1 for d in self.delivery_history if d["success"])

        by_channel = {}
        for d in self.delivery_history:
            channel = d["channel"]
            if channel not in by_channel:
                by_channel[channel] = {"total": 0, "success": 0}
            by_channel[channel]["total"] += 1
            if d["success"]:
                by_channel[channel]["success"] += 1

        return {
            "total_deliveries": total,
            "successful_deliveries": successful,
            "success_rate": successful / total if total > 0 else 0,
            "by_channel": by_channel
        }


# Singleton instance
_delivery_manager: Optional[AlertDeliveryManager] = None


def get_delivery_manager() -> AlertDeliveryManager:
    """Get delivery manager singleton"""
    global _delivery_manager

    if _delivery_manager is None:
        _delivery_manager = AlertDeliveryManager()

    return _delivery_manager


# Testing
if __name__ == "__main__":
    async def test():
        manager = AlertDeliveryManager()

        # Configure a webhook
        manager.set_user_preferences("test_user", [
            DeliveryConfig(
                channel=DeliveryChannel.WEBHOOK,
                endpoint="https://webhook.site/test",
                enabled=True
            )
        ])

        # Create test message
        message = AlertMessage(
            alert_id="TEST-001",
            title="Price Alert Triggered",
            body="SOL has crossed your $150 threshold!",
            severity="high",
            data={
                "token": "SOL",
                "price": 152.50,
                "threshold": 150.00,
                "change_24h": "+5.2%"
            }
        )

        # Test formats
        print("Discord embed:", json.dumps(message.to_discord_embed(), indent=2))
        print("\nTelegram message:", message.to_telegram_message())
        print("\nDelivery stats:", manager.get_delivery_stats())

    asyncio.run(test())
