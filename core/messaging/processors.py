"""
Message Processors for Dead Letter Queue

Implements processors for:
- Failed trade executions
- Undeliverable alerts
- Failed API callbacks
- Malformed incoming messages
"""

import asyncio
import logging
from typing import Optional, Dict, Any

from .dead_letter_queue import MessageProcessor, FailedMessage, MessageType

logger = logging.getLogger(__name__)


class TradeExecutionProcessor(MessageProcessor):
    """
    Processes failed trade execution messages.

    Handles retries for:
    - Jupiter swap failures
    - Network timeouts
    - Insufficient balance errors
    """

    def __init__(self, trading_engine: Optional[Any] = None):
        """
        Initialize processor.

        Args:
            trading_engine: Reference to TreasuryTrader instance
        """
        self.trading_engine = trading_engine

    def can_process(self, message_type: MessageType) -> bool:
        """Check if this processor handles this message type"""
        return message_type == MessageType.TRADE_EXECUTION

    async def process(self, message: FailedMessage) -> bool:
        """
        Retry failed trade execution.

        Expected payload:
        {
            "token_mint": str,
            "token_symbol": str,
            "direction": "LONG" | "SHORT",
            "amount_usd": float,
            "sentiment_score": float,
            "sentiment_grade": str
        }
        """
        if not self.trading_engine:
            logger.error("No trading engine configured for trade retry")
            return False

        payload = message.payload

        try:
            logger.info(
                f"Retrying trade execution: {payload.get('token_symbol')} "
                f"{payload.get('direction')}"
            )

            # Check if we should still execute this trade
            # (market conditions may have changed)
            token_mint = payload.get("token_mint")
            if not token_mint:
                logger.error("Missing token_mint in payload")
                return False

            # Attempt to execute trade
            result = await self.trading_engine.execute_sentiment_trade(
                token_mint=token_mint,
                token_symbol=payload.get("token_symbol", "UNKNOWN"),
                sentiment_score=payload.get("sentiment_score", 0.0),
                sentiment_grade=payload.get("sentiment_grade", "F"),
                force_retry=True
            )

            if result and result.get("success"):
                logger.info(f"Successfully retried trade execution: {token_mint}")
                return True
            else:
                logger.warning(
                    f"Trade retry failed: {result.get('error', 'Unknown error')}"
                )
                return False

        except Exception as e:
            logger.error(f"Error retrying trade execution: {e}")
            return False


class AlertDeliveryProcessor(MessageProcessor):
    """
    Processes failed alert delivery messages.

    Handles retries for:
    - Discord webhook failures
    - Telegram API errors
    - Email delivery failures
    """

    def __init__(self, alert_manager: Optional[Any] = None):
        """
        Initialize processor.

        Args:
            alert_manager: Reference to AlertDeliveryManager instance
        """
        self.alert_manager = alert_manager

    def can_process(self, message_type: MessageType) -> bool:
        """Check if this processor handles this message type"""
        return message_type == MessageType.ALERT_DELIVERY

    async def process(self, message: FailedMessage) -> bool:
        """
        Retry failed alert delivery.

        Expected payload:
        {
            "user_id": str,
            "alert_id": str,
            "title": str,
            "body": str,
            "severity": str,
            "data": dict,
            "channels": list[str]
        }
        """
        if not self.alert_manager:
            logger.error("No alert manager configured for alert retry")
            return False

        payload = message.payload

        try:
            from core.alerts.delivery import AlertMessage, DeliveryChannel

            logger.info(f"Retrying alert delivery: {payload.get('alert_id')}")

            # Reconstruct alert message
            alert = AlertMessage(
                alert_id=payload.get("alert_id", "RETRY-UNKNOWN"),
                title=payload.get("title", "Alert"),
                body=payload.get("body", ""),
                severity=payload.get("severity", "medium"),
                data=payload.get("data", {})
            )

            # Determine channels
            channels = None
            if payload.get("channels"):
                channels = [
                    DeliveryChannel(ch) for ch in payload["channels"]
                ]

            # Attempt delivery
            results = await self.alert_manager.deliver_alert(
                user_id=payload.get("user_id", "admin"),
                message=alert,
                channels=channels
            )

            # Check if any channel succeeded
            success = any(result.success for result in results.values())

            if success:
                logger.info(f"Successfully retried alert delivery: {alert.alert_id}")
                return True
            else:
                logger.warning(f"Alert retry failed for all channels: {alert.alert_id}")
                return False

        except Exception as e:
            logger.error(f"Error retrying alert delivery: {e}")
            return False


class APICallbackProcessor(MessageProcessor):
    """
    Processes failed API callback messages.

    Handles retries for:
    - Webhook delivery failures
    - External API callback errors
    """

    def can_process(self, message_type: MessageType) -> bool:
        """Check if this processor handles this message type"""
        return message_type == MessageType.API_CALLBACK

    async def process(self, message: FailedMessage) -> bool:
        """
        Retry failed API callback.

        Expected payload:
        {
            "url": str,
            "method": str,
            "headers": dict,
            "body": dict
        }
        """
        import aiohttp

        payload = message.payload

        try:
            url = payload.get("url")
            method = payload.get("method", "POST").upper()
            headers = payload.get("headers", {})
            body = payload.get("body", {})

            if not url:
                logger.error("Missing URL in callback payload")
                return False

            logger.info(f"Retrying API callback: {method} {url}")

            async with aiohttp.ClientSession() as session:
                async with session.request(
                    method,
                    url,
                    json=body,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=10.0)
                ) as response:
                    if response.status in [200, 201, 202, 204]:
                        logger.info(f"Successfully retried API callback: {url}")
                        return True
                    else:
                        text = await response.text()
                        logger.warning(
                            f"API callback retry failed: {response.status} - {text}"
                        )
                        return False

        except asyncio.TimeoutError:
            logger.warning(f"API callback retry timeout: {payload.get('url')}")
            return False
        except Exception as e:
            logger.error(f"Error retrying API callback: {e}")
            return False


class IncomingMessageProcessor(MessageProcessor):
    """
    Processes malformed incoming messages.

    Handles:
    - Message validation and sanitization
    - Retry with corrected format
    """

    def __init__(self, message_handler: Optional[Any] = None):
        """
        Initialize processor.

        Args:
            message_handler: Reference to message handler (e.g., Telegram bot)
        """
        self.message_handler = message_handler

    def can_process(self, message_type: MessageType) -> bool:
        """Check if this processor handles this message type"""
        return message_type == MessageType.INCOMING_MESSAGE

    async def process(self, message: FailedMessage) -> bool:
        """
        Retry processing malformed incoming message.

        Expected payload:
        {
            "source": str,  # "telegram", "discord", etc.
            "raw_message": dict,
            "error": str
        }
        """
        if not self.message_handler:
            logger.error("No message handler configured for incoming message retry")
            return False

        payload = message.payload

        try:
            source = payload.get("source", "unknown")
            raw_message = payload.get("raw_message", {})

            logger.info(f"Retrying incoming message from {source}")

            # Attempt to sanitize and process
            if source == "telegram":
                # Extract text safely
                text = raw_message.get("text", "")
                if not text:
                    logger.warning("No text in malformed Telegram message")
                    return False

                # Attempt to process with handler
                result = await self.message_handler.handle_message(raw_message)
                return result

            elif source == "discord":
                # Handle Discord message
                content = raw_message.get("content", "")
                if not content:
                    logger.warning("No content in malformed Discord message")
                    return False

                result = await self.message_handler.handle_message(raw_message)
                return result

            else:
                logger.warning(f"Unknown message source: {source}")
                return False

        except Exception as e:
            logger.error(f"Error retrying incoming message: {e}")
            return False


class WebhookProcessor(MessageProcessor):
    """
    Processes failed webhook deliveries.

    Handles retries for:
    - Webhook POST failures
    - Timeout errors
    """

    def can_process(self, message_type: MessageType) -> bool:
        """Check if this processor handles this message type"""
        return message_type == MessageType.WEBHOOK

    async def process(self, message: FailedMessage) -> bool:
        """
        Retry failed webhook delivery.

        Expected payload:
        {
            "url": str,
            "payload": dict,
            "headers": dict
        }
        """
        import aiohttp

        payload = message.payload

        try:
            url = payload.get("url")
            webhook_payload = payload.get("payload", {})
            headers = payload.get("headers", {"Content-Type": "application/json"})

            if not url:
                logger.error("Missing URL in webhook payload")
                return False

            logger.info(f"Retrying webhook: {url}")

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    url,
                    json=webhook_payload,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=15.0)
                ) as response:
                    if response.status in [200, 201, 202, 204]:
                        logger.info(f"Successfully retried webhook: {url}")
                        return True
                    else:
                        text = await response.text()
                        logger.warning(
                            f"Webhook retry failed: {response.status} - {text}"
                        )
                        return False

        except asyncio.TimeoutError:
            logger.warning(f"Webhook retry timeout: {payload.get('url')}")
            return False
        except Exception as e:
            logger.error(f"Error retrying webhook: {e}")
            return False


class NotificationProcessor(MessageProcessor):
    """
    Processes failed notification deliveries.

    Handles retries for:
    - Push notifications
    - SMS
    - Other notification channels
    """

    def __init__(self, notification_service: Optional[Any] = None):
        """
        Initialize processor.

        Args:
            notification_service: Reference to notification service
        """
        self.notification_service = notification_service

    def can_process(self, message_type: MessageType) -> bool:
        """Check if this processor handles this message type"""
        return message_type == MessageType.NOTIFICATION

    async def process(self, message: FailedMessage) -> bool:
        """
        Retry failed notification.

        Expected payload:
        {
            "channel": str,  # "push", "sms", etc.
            "recipient": str,
            "title": str,
            "body": str,
            "data": dict
        }
        """
        if not self.notification_service:
            logger.error("No notification service configured")
            return False

        payload = message.payload

        try:
            channel = payload.get("channel", "push")
            recipient = payload.get("recipient")

            if not recipient:
                logger.error("Missing recipient in notification payload")
                return False

            logger.info(f"Retrying {channel} notification to {recipient}")

            # Attempt to send notification
            result = await self.notification_service.send(
                channel=channel,
                recipient=recipient,
                title=payload.get("title", "Notification"),
                body=payload.get("body", ""),
                data=payload.get("data", {})
            )

            if result:
                logger.info(f"Successfully retried notification to {recipient}")
                return True
            else:
                logger.warning(f"Notification retry failed for {recipient}")
                return False

        except Exception as e:
            logger.error(f"Error retrying notification: {e}")
            return False
