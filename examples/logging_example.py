"""
Example: Using Structured Logging in Jarvis

This example demonstrates how to use the new structured logging system
in various scenarios common to the Jarvis codebase.
"""

import asyncio
from core.logging_config import (
    setup_logging,
    get_logger,
    CorrelationContext,
    set_correlation_id,
    set_user_context,
)


# Example 1: Application Setup
def setup_application():
    """Setup logging for the entire application."""
    setup_logging(
        log_dir="logs",
        log_file="jarvis.log",
        level="INFO",
        json_format=True,  # JSON for production
        console_output=True,  # Also show in console
        max_bytes=100 * 1024 * 1024,  # 100MB per file
        backup_count=10,  # Keep 10 backups
        extra_fields={
            "service": "jarvis",
            "environment": "production",
            "version": "1.0.0"
        }
    )


# Example 2: Module-level Logger
logger = get_logger(__name__)


# Example 3: Simple Logging
def simple_logging_example():
    """Basic logging without extra context."""
    logger.info("Application started")
    logger.debug("Debug message for troubleshooting")
    logger.warning("Something unusual happened")
    logger.error("An error occurred")


# Example 4: Structured Logging with Extra Data
def structured_logging_example():
    """Logging with additional structured data."""
    logger.info("User logged in",
        user_id="user_123",
        username="alice",
        ip_address="192.168.1.100"
    )

    logger.warning("Low disk space",
        available_gb=5.2,
        total_gb=100.0,
        usage_percent=94.8
    )


# Example 5: Correlation Context for Request Tracking
async def trade_execution_example():
    """Track a trade request across multiple operations."""

    # Auto-generate correlation ID
    with CorrelationContext(user_id="user_456"):
        logger.info("Trade request received",
            symbol="SOL",
            amount=100.5,
            side="buy"
        )

        # Simulate validation
        await asyncio.sleep(0.1)
        logger.debug("Validation passed",
            balance_check=True,
            risk_check=True
        )

        # Simulate execution
        await asyncio.sleep(0.2)
        logger.info("Trade executed successfully",
            symbol="SOL",
            amount=100.5,
            price=95.23,
            tx_id="0x1234567890abcdef",
            execution_time_ms=300
        )


# Example 6: Error Handling with Context
async def error_handling_example():
    """Proper error logging with exception details."""

    with CorrelationContext(
        correlation_id="trade-123",
        user_id="user_789",
        trade_id="trade_001"
    ):
        try:
            logger.info("Attempting risky operation",
                operation="swap",
                slippage_tolerance=0.05
            )

            # Simulate error
            raise ValueError("Insufficient liquidity")

        except ValueError as e:
            logger.exception("Trade failed",
                symbol="SOL",
                amount=100,
                error_type=type(e).__name__,
                retry_count=0
            )


# Example 7: Nested Correlation Contexts
async def nested_context_example():
    """Nested operations with their own context."""

    with CorrelationContext(correlation_id="batch-001"):
        logger.info("Batch processing started", batch_size=10)

        for i in range(3):
            # Each item gets its own context that inherits batch correlation
            with CorrelationContext(
                correlation_id=f"item-{i}",
                user_id=f"user_{i}"
            ):
                logger.info("Processing item",
                    item_index=i,
                    status="in_progress"
                )
                await asyncio.sleep(0.1)
                logger.info("Item completed",
                    item_index=i,
                    status="success"
                )


# Example 8: Background Task Logging
async def background_task_example():
    """Long-running background task with periodic logging."""

    task_id = "monitor_001"

    with CorrelationContext(session_id=task_id):
        logger.info("Background task started",
            task_type="price_monitor",
            interval_seconds=60
        )

        for iteration in range(3):
            logger.debug("Monitoring iteration",
                iteration=iteration,
                symbols_checked=["SOL", "BTC", "ETH"]
            )

            # Simulate price check
            await asyncio.sleep(1)

            logger.info("Price alert triggered",
                symbol="SOL",
                current_price=95.50,
                threshold_price=95.00,
                direction="above"
            )


# Example 9: API Request Handler Pattern
async def api_handler_example(request_id: str, user_id: str):
    """Pattern for API request handlers."""

    with CorrelationContext(
        correlation_id=request_id,
        user_id=user_id
    ):
        logger.info("API request started",
            endpoint="/api/trade",
            method="POST"
        )

        try:
            # Simulate processing
            await asyncio.sleep(0.1)

            logger.info("API request completed",
                status_code=200,
                response_time_ms=100
            )

        except Exception as e:
            logger.exception("API request failed",
                endpoint="/api/trade",
                status_code=500
            )
            raise


# Example 10: Performance Monitoring
async def performance_monitoring_example():
    """Track operation performance with timing data."""
    import time

    with CorrelationContext():
        start = time.time()

        logger.info("Heavy operation started",
            operation="data_sync",
            estimated_duration_s=5
        )

        # Simulate work
        await asyncio.sleep(0.5)

        duration_ms = (time.time() - start) * 1000

        logger.info("Heavy operation completed",
            operation="data_sync",
            duration_ms=duration_ms,
            success=True
        )

        # Alert on slow operations
        if duration_ms > 1000:
            logger.warning("Slow operation detected",
                operation="data_sync",
                duration_ms=duration_ms,
                threshold_ms=1000
            )


# Main demonstration
async def main():
    """Run all examples."""

    # Setup logging
    setup_logging(
        log_dir="logs/examples",
        log_file="structured_logging_demo.log",
        level="DEBUG",
        json_format=False,  # Use structured format for demo readability
        console_output=True
    )

    print("=" * 60)
    print("STRUCTURED LOGGING EXAMPLES")
    print("=" * 60)
    print()

    print("Example 1: Simple Logging")
    simple_logging_example()
    print()

    print("Example 2: Structured Data")
    structured_logging_example()
    print()

    print("Example 3: Trade Execution with Correlation")
    await trade_execution_example()
    print()

    print("Example 4: Error Handling")
    await error_handling_example()
    print()

    print("Example 5: Nested Contexts")
    await nested_context_example()
    print()

    print("Example 6: Background Task")
    await background_task_example()
    print()

    print("Example 7: API Handler")
    await api_handler_example("req_123", "user_999")
    print()

    print("Example 8: Performance Monitoring")
    await performance_monitoring_example()
    print()

    print("=" * 60)
    print("Check logs/examples/structured_logging_demo.log for output")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
