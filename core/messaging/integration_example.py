"""
Example integration of Dead Letter Queue with existing systems.

Shows how to:
1. Set up the DLQ with processors
2. Integrate with trading engine
3. Integrate with alert delivery
4. Monitor DLQ health
"""

import asyncio
import logging
from typing import Optional

from core.messaging import (
    DeadLetterQueue,
    MessageType,
    FailureReason,
    RetryStrategy,
    get_dlq,
    TradeExecutionProcessor,
    AlertDeliveryProcessor,
    APICallbackProcessor,
    WebhookProcessor
)

logger = logging.getLogger(__name__)


class DLQIntegration:
    """
    Integration layer for DLQ with Jarvis systems.

    Usage:
        integration = DLQIntegration(trading_engine, alert_manager)
        await integration.start()
        # ... later ...
        await integration.stop()
    """

    def __init__(
        self,
        trading_engine: Optional[Any] = None,
        alert_manager: Optional[Any] = None,
        max_queue_size: int = 10000,
        depth_alert_threshold: int = 1000
    ):
        """
        Initialize DLQ integration.

        Args:
            trading_engine: Reference to TreasuryTrader
            alert_manager: Reference to AlertDeliveryManager
            max_queue_size: Maximum messages in DLQ
            depth_alert_threshold: Queue depth that triggers alerts
        """
        self.trading_engine = trading_engine
        self.alert_manager = alert_manager

        # Create DLQ
        self.dlq = DeadLetterQueue(
            max_queue_size=max_queue_size,
            max_retention_hours=24,
            retry_interval_seconds=10.0,
            cleanup_interval_seconds=300.0,
            depth_alert_threshold=depth_alert_threshold
        )

        # Register processors
        self._register_processors()

        # Register alert callbacks
        self._register_alerts()

        # Monitoring task
        self._monitor_task: Optional[asyncio.Task] = None

    def _register_processors(self) -> None:
        """Register message processors"""
        # Trade execution processor
        if self.trading_engine:
            trade_processor = TradeExecutionProcessor(
                trading_engine=self.trading_engine
            )
            self.dlq.register_processor(
                trade_processor,
                [MessageType.TRADE_EXECUTION]
            )
            logger.info("Registered TradeExecutionProcessor")

        # Alert delivery processor
        if self.alert_manager:
            alert_processor = AlertDeliveryProcessor(
                alert_manager=self.alert_manager
            )
            self.dlq.register_processor(
                alert_processor,
                [MessageType.ALERT_DELIVERY]
            )
            logger.info("Registered AlertDeliveryProcessor")

        # API callback processor
        api_processor = APICallbackProcessor()
        self.dlq.register_processor(
            api_processor,
            [MessageType.API_CALLBACK]
        )
        logger.info("Registered APICallbackProcessor")

        # Webhook processor
        webhook_processor = WebhookProcessor()
        self.dlq.register_processor(
            webhook_processor,
            [MessageType.WEBHOOK]
        )
        logger.info("Registered WebhookProcessor")

    def _register_alerts(self) -> None:
        """Register alert callbacks for DLQ monitoring"""
        self.dlq.register_alert_callback(self._handle_dlq_alert)

    async def _handle_dlq_alert(self, alert_type: str, data: dict) -> None:
        """Handle DLQ alerts"""
        if alert_type == "high_queue_depth":
            logger.warning(
                f"DLQ queue depth alert: {data['current_depth']}/{data['max_size']} "
                f"(threshold: {data['threshold']})"
            )

            # Send alert via Telegram if available
            if self.alert_manager:
                try:
                    from core.alerts.delivery import AlertMessage

                    alert = AlertMessage(
                        alert_id=f"DLQ-DEPTH-{data['current_depth']}",
                        title="Dead Letter Queue Alert",
                        body=f"DLQ depth: {data['current_depth']} (threshold: {data['threshold']})",
                        severity="high",
                        data=data
                    )

                    await self.alert_manager.deliver_alert(
                        user_id="admin",
                        message=alert
                    )
                except Exception as e:
                    logger.error(f"Failed to send DLQ alert: {e}")

        elif alert_type == "permanent_failure":
            logger.error(
                f"Permanent failure for message {data['message_id']}: "
                f"{data['failure_reason']} - {data['error']}"
            )

    async def _monitor_worker(self) -> None:
        """Background worker that monitors DLQ metrics"""
        while True:
            try:
                await asyncio.sleep(60)  # Check every minute

                metrics = self.dlq.get_metrics()

                # Log metrics
                logger.info(
                    f"DLQ Metrics: queue={metrics.current_queue_depth}, "
                    f"failures={metrics.total_failures}, "
                    f"successes={metrics.total_successes}, "
                    f"permanent={metrics.total_permanent_failures}, "
                    f"avg_retries={metrics.avg_retry_count:.2f}"
                )

                # Alert on high permanent failure rate
                if metrics.total_failures > 0:
                    perm_rate = metrics.total_permanent_failures / metrics.total_failures
                    if perm_rate > 0.5:  # 50% permanent failure rate
                        logger.warning(
                            f"High permanent failure rate: {perm_rate:.1%} "
                            f"({metrics.total_permanent_failures}/{metrics.total_failures})"
                        )

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in DLQ monitor: {e}")

    async def start(self) -> None:
        """Start the DLQ integration"""
        logger.info("Starting DLQ integration")

        # Start DLQ
        await self.dlq.start()

        # Start monitoring
        self._monitor_task = asyncio.create_task(self._monitor_worker())

        logger.info("DLQ integration started")

    async def stop(self) -> None:
        """Stop the DLQ integration"""
        logger.info("Stopping DLQ integration")

        # Stop monitoring
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass

        # Stop DLQ
        await self.dlq.stop()

        logger.info("DLQ integration stopped")

    async def enqueue_failed_trade(
        self,
        token_mint: str,
        token_symbol: str,
        direction: str,
        amount_usd: float,
        sentiment_score: float,
        sentiment_grade: str,
        error: str
    ) -> str:
        """
        Enqueue a failed trade execution.

        Returns:
            Message ID
        """
        return await self.dlq.enqueue(
            message_type=MessageType.TRADE_EXECUTION,
            payload={
                "token_mint": token_mint,
                "token_symbol": token_symbol,
                "direction": direction,
                "amount_usd": amount_usd,
                "sentiment_score": sentiment_score,
                "sentiment_grade": sentiment_grade
            },
            failure_reason=FailureReason.NETWORK_ERROR,
            error_message=error,
            retry_strategy=RetryStrategy.EXPONENTIAL,
            max_retries=3
        )

    async def enqueue_failed_alert(
        self,
        user_id: str,
        alert_id: str,
        title: str,
        body: str,
        severity: str,
        data: dict,
        error: str
    ) -> str:
        """
        Enqueue a failed alert delivery.

        Returns:
            Message ID
        """
        return await self.dlq.enqueue(
            message_type=MessageType.ALERT_DELIVERY,
            payload={
                "user_id": user_id,
                "alert_id": alert_id,
                "title": title,
                "body": body,
                "severity": severity,
                "data": data
            },
            failure_reason=FailureReason.NETWORK_ERROR,
            error_message=error,
            retry_strategy=RetryStrategy.EXPONENTIAL,
            max_retries=5
        )

    async def enqueue_failed_webhook(
        self,
        url: str,
        payload: dict,
        error: str
    ) -> str:
        """
        Enqueue a failed webhook delivery.

        Returns:
            Message ID
        """
        return await self.dlq.enqueue(
            message_type=MessageType.WEBHOOK,
            payload={
                "url": url,
                "payload": payload,
                "headers": {"Content-Type": "application/json"}
            },
            failure_reason=FailureReason.TIMEOUT,
            error_message=error,
            retry_strategy=RetryStrategy.EXPONENTIAL,
            max_retries=3
        )

    def get_metrics(self) -> dict:
        """Get DLQ metrics"""
        return self.dlq.get_metrics().to_dict()

    def get_queue_snapshot(self) -> list:
        """Get current queue snapshot"""
        return self.dlq.get_queue_snapshot()

    def get_permanent_failures(self) -> list:
        """Get permanent failures"""
        return self.dlq.get_permanent_failures()


# Example usage in bots/supervisor.py
async def example_integration():
    """
    Example of integrating DLQ with Jarvis supervisor.
    """
    from bots.treasury.trading import TreasuryTrader
    from core.alerts.delivery import get_delivery_manager

    # Create components
    trading_engine = TreasuryTrader()
    alert_manager = get_delivery_manager()

    # Create DLQ integration
    dlq_integration = DLQIntegration(
        trading_engine=trading_engine,
        alert_manager=alert_manager,
        max_queue_size=10000,
        depth_alert_threshold=1000
    )

    # Start DLQ
    await dlq_integration.start()

    try:
        # Example: Failed trade execution
        await dlq_integration.enqueue_failed_trade(
            token_mint="So11111111111111111111111111111111111111112",
            token_symbol="SOL",
            direction="LONG",
            amount_usd=100.0,
            sentiment_score=0.8,
            sentiment_grade="A",
            error="Network timeout"
        )

        # Example: Failed alert delivery
        await dlq_integration.enqueue_failed_alert(
            user_id="admin",
            alert_id="ALERT-001",
            title="Price Alert",
            body="SOL reached $150",
            severity="high",
            data={"token": "SOL", "price": 150},
            error="Telegram API error"
        )

        # Run indefinitely
        while True:
            await asyncio.sleep(60)

            # Print metrics
            metrics = dlq_integration.get_metrics()
            print(f"DLQ Metrics: {metrics}")

    finally:
        await dlq_integration.stop()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(example_integration())
