"""
Tests for message processors.

Covers:
- TradeExecutionProcessor
- AlertDeliveryProcessor
- APICallbackProcessor
- IncomingMessageProcessor
- WebhookProcessor
- NotificationProcessor
"""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from core.messaging.dead_letter_queue import (
    FailedMessage,
    MessageType,
    FailureReason,
    RetryStrategy
)

from core.messaging.processors import (
    TradeExecutionProcessor,
    AlertDeliveryProcessor,
    APICallbackProcessor,
    IncomingMessageProcessor,
    WebhookProcessor,
    NotificationProcessor
)


class TestTradeExecutionProcessor:
    """Test TradeExecutionProcessor"""

    @pytest.mark.asyncio
    async def test_successful_trade_retry(self):
        """Test successful trade execution retry"""
        # Mock trading engine
        mock_engine = AsyncMock()
        mock_engine.execute_sentiment_trade = AsyncMock(
            return_value={"success": True, "position_id": "test-123"}
        )

        processor = TradeExecutionProcessor(trading_engine=mock_engine)

        message = FailedMessage(
            message_type=MessageType.TRADE_EXECUTION,
            payload={
                "token_mint": "So11111111111111111111111111111111111111112",
                "token_symbol": "SOL",
                "direction": "LONG",
                "amount_usd": 100.0,
                "sentiment_score": 0.8,
                "sentiment_grade": "A"
            },
            failure_reason=FailureReason.TIMEOUT,
            error_message="Timeout"
        )

        success = await processor.process(message)

        assert success
        mock_engine.execute_sentiment_trade.assert_called_once()

    @pytest.mark.asyncio
    async def test_failed_trade_retry(self):
        """Test failed trade execution retry"""
        mock_engine = AsyncMock()
        mock_engine.execute_sentiment_trade = AsyncMock(
            return_value={"success": False, "error": "Insufficient balance"}
        )

        processor = TradeExecutionProcessor(trading_engine=mock_engine)

        message = FailedMessage(
            message_type=MessageType.TRADE_EXECUTION,
            payload={
                "token_mint": "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
                "token_symbol": "USDC",
                "sentiment_score": 0.5
            },
            failure_reason=FailureReason.NETWORK_ERROR,
            error_message="Network error"
        )

        success = await processor.process(message)
        assert not success

    @pytest.mark.asyncio
    async def test_no_trading_engine(self):
        """Test processor without trading engine configured"""
        processor = TradeExecutionProcessor(trading_engine=None)

        message = FailedMessage(
            message_type=MessageType.TRADE_EXECUTION,
            payload={"token_mint": "test"},
            failure_reason=FailureReason.TIMEOUT,
            error_message="Timeout"
        )

        success = await processor.process(message)
        assert not success

    def test_can_process(self):
        """Test can_process method"""
        processor = TradeExecutionProcessor()
        assert processor.can_process(MessageType.TRADE_EXECUTION)
        assert not processor.can_process(MessageType.ALERT_DELIVERY)


class TestAlertDeliveryProcessor:
    """Test AlertDeliveryProcessor"""

    @pytest.mark.asyncio
    async def test_successful_alert_retry(self):
        """Test successful alert delivery retry"""
        # Mock alert manager
        mock_manager = AsyncMock()
        mock_result = MagicMock()
        mock_result.success = True
        mock_manager.deliver_alert = AsyncMock(
            return_value={"telegram": mock_result}
        )

        processor = AlertDeliveryProcessor(alert_manager=mock_manager)

        message = FailedMessage(
            message_type=MessageType.ALERT_DELIVERY,
            payload={
                "user_id": "user123",
                "alert_id": "ALERT-001",
                "title": "Price Alert",
                "body": "SOL reached $150",
                "severity": "high",
                "data": {"token": "SOL", "price": 150},
                "channels": ["telegram"]
            },
            failure_reason=FailureReason.NETWORK_ERROR,
            error_message="Network error"
        )

        success = await processor.process(message)
        assert success

    @pytest.mark.asyncio
    async def test_failed_alert_retry(self):
        """Test failed alert delivery retry"""
        mock_manager = AsyncMock()
        mock_result = MagicMock()
        mock_result.success = False
        mock_manager.deliver_alert = AsyncMock(
            return_value={"telegram": mock_result}
        )

        processor = AlertDeliveryProcessor(alert_manager=mock_manager)

        message = FailedMessage(
            message_type=MessageType.ALERT_DELIVERY,
            payload={
                "user_id": "user123",
                "alert_id": "ALERT-002",
                "title": "Test",
                "body": "Test"
            },
            failure_reason=FailureReason.TIMEOUT,
            error_message="Timeout"
        )

        success = await processor.process(message)
        assert not success

    def test_can_process(self):
        """Test can_process method"""
        processor = AlertDeliveryProcessor()
        assert processor.can_process(MessageType.ALERT_DELIVERY)
        assert not processor.can_process(MessageType.WEBHOOK)


class TestAPICallbackProcessor:
    """Test APICallbackProcessor"""

    @pytest.mark.asyncio
    async def test_successful_callback_retry(self):
        """Test successful API callback retry"""
        processor = APICallbackProcessor()

        # Mock aiohttp - session.request() returns an async context manager
        with patch("aiohttp.ClientSession") as mock_session:
            # Create mock response
            mock_response = MagicMock()
            mock_response.status = 200

            # Create async context manager for request()
            mock_request_cm = MagicMock()
            mock_request_cm.__aenter__ = AsyncMock(return_value=mock_response)
            mock_request_cm.__aexit__ = AsyncMock(return_value=None)

            # Session instance - request() returns the async context manager
            mock_session_instance = MagicMock()
            mock_session_instance.request.return_value = mock_request_cm
            mock_session_instance.__aenter__ = AsyncMock(return_value=mock_session_instance)
            mock_session_instance.__aexit__ = AsyncMock(return_value=None)

            mock_session.return_value = mock_session_instance

            message = FailedMessage(
                message_type=MessageType.API_CALLBACK,
                payload={
                    "url": "https://api.example.com/callback",
                    "method": "POST",
                    "headers": {"Authorization": "Bearer test"},
                    "body": {"event": "trade_executed"}
                },
                failure_reason=FailureReason.TIMEOUT,
                error_message="Timeout"
            )

            success = await processor.process(message)
            assert success

    @pytest.mark.asyncio
    async def test_failed_callback_retry(self):
        """Test failed API callback retry"""
        processor = APICallbackProcessor()

        # Mock aiohttp - session.request() returns an async context manager
        with patch("aiohttp.ClientSession") as mock_session:
            # Create mock response
            mock_response = MagicMock()
            mock_response.status = 500
            mock_response.text = AsyncMock(return_value="Internal Server Error")

            # Create async context manager for request()
            mock_request_cm = MagicMock()
            mock_request_cm.__aenter__ = AsyncMock(return_value=mock_response)
            mock_request_cm.__aexit__ = AsyncMock(return_value=None)

            # Session instance - request() returns the async context manager
            mock_session_instance = MagicMock()
            mock_session_instance.request.return_value = mock_request_cm
            mock_session_instance.__aenter__ = AsyncMock(return_value=mock_session_instance)
            mock_session_instance.__aexit__ = AsyncMock(return_value=None)

            mock_session.return_value = mock_session_instance

            message = FailedMessage(
                message_type=MessageType.API_CALLBACK,
                payload={
                    "url": "https://api.example.com/callback",
                    "method": "POST",
                    "body": {}
                },
                failure_reason=FailureReason.SERVICE_UNAVAILABLE,
                error_message="Service unavailable"
            )

            success = await processor.process(message)
            assert not success

    @pytest.mark.asyncio
    async def test_missing_url(self):
        """Test callback retry with missing URL"""
        processor = APICallbackProcessor()

        message = FailedMessage(
            message_type=MessageType.API_CALLBACK,
            payload={"method": "POST"},
            failure_reason=FailureReason.VALIDATION_ERROR,
            error_message="Missing URL"
        )

        success = await processor.process(message)
        assert not success

    def test_can_process(self):
        """Test can_process method"""
        processor = APICallbackProcessor()
        assert processor.can_process(MessageType.API_CALLBACK)
        assert not processor.can_process(MessageType.INCOMING_MESSAGE)


class TestIncomingMessageProcessor:
    """Test IncomingMessageProcessor"""

    @pytest.mark.asyncio
    async def test_telegram_message_retry(self):
        """Test retrying malformed Telegram message"""
        mock_handler = AsyncMock()
        mock_handler.handle_message = AsyncMock(return_value=True)

        processor = IncomingMessageProcessor(message_handler=mock_handler)

        message = FailedMessage(
            message_type=MessageType.INCOMING_MESSAGE,
            payload={
                "source": "telegram",
                "raw_message": {
                    "text": "/start",
                    "chat": {"id": 123}
                },
                "error": "Malformed message"
            },
            failure_reason=FailureReason.MALFORMED_DATA,
            error_message="Malformed message"
        )

        success = await processor.process(message)
        assert success
        mock_handler.handle_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_discord_message_retry(self):
        """Test retrying malformed Discord message"""
        mock_handler = AsyncMock()
        mock_handler.handle_message = AsyncMock(return_value=True)

        processor = IncomingMessageProcessor(message_handler=mock_handler)

        message = FailedMessage(
            message_type=MessageType.INCOMING_MESSAGE,
            payload={
                "source": "discord",
                "raw_message": {
                    "content": "!help",
                    "author": {"id": "456"}
                },
                "error": "Parse error"
            },
            failure_reason=FailureReason.MALFORMED_DATA,
            error_message="Parse error"
        )

        success = await processor.process(message)
        assert success

    @pytest.mark.asyncio
    async def test_no_message_handler(self):
        """Test processor without message handler"""
        processor = IncomingMessageProcessor(message_handler=None)

        message = FailedMessage(
            message_type=MessageType.INCOMING_MESSAGE,
            payload={"source": "telegram"},
            failure_reason=FailureReason.MALFORMED_DATA,
            error_message="Error"
        )

        success = await processor.process(message)
        assert not success

    def test_can_process(self):
        """Test can_process method"""
        processor = IncomingMessageProcessor()
        assert processor.can_process(MessageType.INCOMING_MESSAGE)
        assert not processor.can_process(MessageType.NOTIFICATION)


class TestWebhookProcessor:
    """Test WebhookProcessor"""

    @pytest.mark.asyncio
    async def test_successful_webhook_retry(self):
        """Test successful webhook retry"""
        processor = WebhookProcessor()

        # Mock aiohttp - session.post() returns an async context manager
        with patch("aiohttp.ClientSession") as mock_session:
            # Create mock response
            mock_response = MagicMock()
            mock_response.status = 200

            # Create async context manager for post()
            mock_post_cm = MagicMock()
            mock_post_cm.__aenter__ = AsyncMock(return_value=mock_response)
            mock_post_cm.__aexit__ = AsyncMock(return_value=None)

            # Session instance - post() returns the async context manager
            mock_session_instance = MagicMock()
            mock_session_instance.post.return_value = mock_post_cm
            mock_session_instance.__aenter__ = AsyncMock(return_value=mock_session_instance)
            mock_session_instance.__aexit__ = AsyncMock(return_value=None)

            mock_session.return_value = mock_session_instance

            message = FailedMessage(
                message_type=MessageType.WEBHOOK,
                payload={
                    "url": "https://webhook.site/test",
                    "payload": {"event": "trade_executed", "amount": 100},
                    "headers": {"Content-Type": "application/json"}
                },
                failure_reason=FailureReason.TIMEOUT,
                error_message="Timeout"
            )

            success = await processor.process(message)
            assert success

    @pytest.mark.asyncio
    async def test_webhook_timeout(self):
        """Test webhook retry with timeout"""
        processor = WebhookProcessor()

        # Mock aiohttp - session.post() raises timeout on enter
        with patch("aiohttp.ClientSession") as mock_session:
            # Create async context manager that raises timeout on __aenter__
            mock_post_cm = MagicMock()
            mock_post_cm.__aenter__ = AsyncMock(side_effect=asyncio.TimeoutError())
            mock_post_cm.__aexit__ = AsyncMock(return_value=None)

            mock_session_instance = MagicMock()
            mock_session_instance.post.return_value = mock_post_cm
            mock_session_instance.__aenter__ = AsyncMock(return_value=mock_session_instance)
            mock_session_instance.__aexit__ = AsyncMock(return_value=None)

            mock_session.return_value = mock_session_instance

            message = FailedMessage(
                message_type=MessageType.WEBHOOK,
                payload={
                    "url": "https://webhook.site/timeout",
                    "payload": {}
                },
                failure_reason=FailureReason.TIMEOUT,
                error_message="Timeout"
            )

            success = await processor.process(message)
            assert not success

    def test_can_process(self):
        """Test can_process method"""
        processor = WebhookProcessor()
        assert processor.can_process(MessageType.WEBHOOK)
        assert not processor.can_process(MessageType.TRADE_EXECUTION)


class TestNotificationProcessor:
    """Test NotificationProcessor"""

    @pytest.mark.asyncio
    async def test_successful_notification_retry(self):
        """Test successful notification retry"""
        mock_service = AsyncMock()
        mock_service.send = AsyncMock(return_value=True)

        processor = NotificationProcessor(notification_service=mock_service)

        message = FailedMessage(
            message_type=MessageType.NOTIFICATION,
            payload={
                "channel": "push",
                "recipient": "user123",
                "title": "Trade Alert",
                "body": "Your trade executed successfully",
                "data": {"trade_id": "123"}
            },
            failure_reason=FailureReason.NETWORK_ERROR,
            error_message="Network error"
        )

        success = await processor.process(message)
        assert success
        mock_service.send.assert_called_once()

    @pytest.mark.asyncio
    async def test_failed_notification_retry(self):
        """Test failed notification retry"""
        mock_service = AsyncMock()
        mock_service.send = AsyncMock(return_value=False)

        processor = NotificationProcessor(notification_service=mock_service)

        message = FailedMessage(
            message_type=MessageType.NOTIFICATION,
            payload={
                "channel": "sms",
                "recipient": "+1234567890",
                "title": "Alert",
                "body": "Test"
            },
            failure_reason=FailureReason.SERVICE_UNAVAILABLE,
            error_message="Service unavailable"
        )

        success = await processor.process(message)
        assert not success

    @pytest.mark.asyncio
    async def test_missing_recipient(self):
        """Test notification retry with missing recipient"""
        mock_service = AsyncMock()
        processor = NotificationProcessor(notification_service=mock_service)

        message = FailedMessage(
            message_type=MessageType.NOTIFICATION,
            payload={
                "channel": "push",
                "title": "Test"
            },
            failure_reason=FailureReason.VALIDATION_ERROR,
            error_message="Missing recipient"
        )

        success = await processor.process(message)
        assert not success

    def test_can_process(self):
        """Test can_process method"""
        processor = NotificationProcessor()
        assert processor.can_process(MessageType.NOTIFICATION)
        assert not processor.can_process(MessageType.ALERT_DELIVERY)
