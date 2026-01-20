"""
Emergency Stop Integration Example

Shows how to integrate emergency stop checks into:
1. Trading engine position opening
2. Position monitoring loop
3. Order management
4. Alert system
"""

import asyncio
import logging
from typing import Optional, List
from datetime import datetime

from core.trading.emergency_stop import (
    get_emergency_stop_manager,
    StopLevel,
    UnwindStrategy,
)

logger = logging.getLogger(__name__)


# =============================================================================
# Example 1: Trading Engine Integration
# =============================================================================

class TradingEngineExample:
    """Example showing emergency stop in trading engine."""

    def __init__(self):
        self.emergency_manager = get_emergency_stop_manager()

    async def open_position(
        self,
        token_mint: str,
        amount_usd: float,
        **kwargs
    ) -> tuple[bool, str, Optional[object]]:
        """
        Open a new position with emergency stop check.

        This check happens FIRST before any other validation.
        """
        # ===== EMERGENCY STOP CHECK (FIRST!) =====
        allowed, reason = self.emergency_manager.is_trading_allowed(token_mint)
        if not allowed:
            logger.warning(f"Position blocked by emergency stop: {reason}")
            return False, f"🚨 EMERGENCY STOP: {reason}", None

        # ===== NORMAL TRADING FLOW =====
        # ... rest of position opening logic ...
        logger.info(f"Opening position for {token_mint}")

        # Simulate position creation
        position = {"token": token_mint, "amount": amount_usd}

        return True, "Position opened", position


# =============================================================================
# Example 2: Position Monitor Integration
# =============================================================================

class PositionMonitorExample:
    """Example showing emergency stop in position monitoring."""

    def __init__(self):
        self.emergency_manager = get_emergency_stop_manager()
        self.positions = []  # Mock positions

    async def monitor_loop(self):
        """
        Position monitoring loop with emergency stop handling.

        Runs continuously, checking for emergency stops and unwinding if needed.
        """
        logger.info("Starting position monitor loop")

        while True:
            try:
                # ===== CHECK EMERGENCY STOP STATUS =====
                if self.emergency_manager.should_unwind_positions():
                    logger.critical("Emergency unwind triggered!")
                    await self._handle_emergency_unwind()
                    # After unwinding, continue monitoring (for new stops)

                # ===== NORMAL MONITORING =====
                await self._check_positions()

                # Sleep between checks
                await asyncio.sleep(10)

            except Exception as e:
                logger.error(f"Monitor loop error: {e}")
                await asyncio.sleep(5)

    async def _handle_emergency_unwind(self):
        """
        Handle emergency position unwinding.

        Strategy determined by emergency manager.
        """
        strategy = self.emergency_manager.get_unwind_strategy()
        status = self.emergency_manager.get_status()

        logger.critical(
            f"UNWINDING POSITIONS: Strategy={strategy.value}, "
            f"Reason={status['reason']}"
        )

        if strategy == UnwindStrategy.IMMEDIATE:
            # Market orders, close now
            await self._unwind_immediate()

        elif strategy == UnwindStrategy.GRACEFUL:
            # Limit orders with fallback
            await self._unwind_graceful()

        elif strategy == UnwindStrategy.SCHEDULED:
            # Close over time
            await self._unwind_scheduled()

        else:  # MANUAL
            # Log and wait for manual intervention
            logger.warning("Manual unwind required - awaiting admin action")

    async def _unwind_immediate(self):
        """
        Immediate unwinding with market orders.

        Used for kill switch - accept slippage, exit NOW.
        """
        logger.critical("IMMEDIATE UNWIND - Using market orders")

        for position in self.positions:
            try:
                # Close with market order
                logger.info(f"Closing {position} with market order")
                # await self.close_position_market(position)

            except Exception as e:
                logger.error(f"Failed to close {position}: {e}")
                # Continue with other positions

    async def _unwind_graceful(self):
        """
        Graceful unwinding with limit orders.

        Try to get better prices, fall back to market if timeout.
        """
        logger.warning("GRACEFUL UNWIND - Using limit orders")

        timeout_seconds = 1800  # 30 minutes
        start_time = datetime.utcnow()

        for position in self.positions:
            try:
                # Place limit order at better price
                logger.info(f"Placing limit exit for {position}")
                # order_id = await self.place_limit_exit(position)

                # Monitor order, fall back if not filled
                # await self.monitor_exit_order(order_id, timeout_seconds)

            except Exception as e:
                logger.error(f"Failed graceful exit for {position}: {e}")
                # Fall back to market order
                logger.warning(f"Falling back to market order for {position}")
                # await self.close_position_market(position)

    async def _unwind_scheduled(self):
        """
        Scheduled unwinding over extended period.

        Close positions gradually at optimal prices.
        """
        logger.info("SCHEDULED UNWIND - Closing over time")

        # Close 1/3 of positions every 10 minutes
        batch_size = len(self.positions) // 3
        batches = [
            self.positions[i:i+batch_size]
            for i in range(0, len(self.positions), batch_size)
        ]

        for i, batch in enumerate(batches):
            logger.info(f"Closing batch {i+1}/{len(batches)}")

            for position in batch:
                try:
                    # await self.close_position_limit(position)
                    pass
                except Exception as e:
                    logger.error(f"Failed to close {position}: {e}")

            # Wait between batches (except last)
            if i < len(batches) - 1:
                await asyncio.sleep(600)  # 10 minutes

    async def _check_positions(self):
        """Normal position checking."""
        # ... regular monitoring logic ...
        pass


# =============================================================================
# Example 3: Alert Integration
# =============================================================================

class AlertSystemExample:
    """Example showing emergency stop alert integration."""

    def __init__(self, telegram_bot, discord_webhook):
        self.telegram_bot = telegram_bot
        self.discord_webhook = discord_webhook
        self.emergency_manager = get_emergency_stop_manager()

        # Register alert callbacks
        self.emergency_manager.register_alert_callback(self._send_telegram_alert)
        self.emergency_manager.register_alert_callback(self._send_discord_alert)

    async def _send_telegram_alert(self, message: str):
        """Send alert to Telegram admin."""
        try:
            logger.info(f"Sending Telegram alert: {message[:50]}...")
            # await self.telegram_bot.send_message(admin_id, message)
        except Exception as e:
            logger.error(f"Failed to send Telegram alert: {e}")

    async def _send_discord_alert(self, message: str):
        """Send alert to Discord webhook."""
        try:
            logger.info(f"Sending Discord alert: {message[:50]}...")
            # await self.discord_webhook.send(message)
        except Exception as e:
            logger.error(f"Failed to send Discord alert: {e}")


# =============================================================================
# Example 4: Order Manager Integration
# =============================================================================

class OrderManagerExample:
    """Example showing emergency stop in order management."""

    def __init__(self):
        self.emergency_manager = get_emergency_stop_manager()
        self.pending_orders = []  # Mock orders

    async def process_orders(self):
        """
        Process pending orders with emergency stop handling.

        Cancel orders if emergency stop requires it.
        """
        status = self.emergency_manager.get_status()

        # Cancel all orders on KILL or HARD stop
        if status['level'] in ['KILL_SWITCH', 'HARD_STOP']:
            logger.warning(f"Cancelling all orders due to {status['level']}")
            await self._cancel_all_orders()
            return

        # Cancel token-specific orders if token paused
        if status['paused_tokens']:
            await self._cancel_token_orders(status['paused_tokens'])

        # Process remaining orders normally
        # ... normal order processing ...

    async def _cancel_all_orders(self):
        """Cancel all pending orders immediately."""
        logger.critical("CANCELLING ALL ORDERS")

        for order in self.pending_orders:
            try:
                logger.info(f"Cancelling order {order}")
                # await self.cancel_order(order)
            except Exception as e:
                logger.error(f"Failed to cancel {order}: {e}")

    async def _cancel_token_orders(self, paused_tokens: List[str]):
        """Cancel orders for paused tokens."""
        for token in paused_tokens:
            logger.warning(f"Cancelling orders for paused token: {token}")

            for order in self.pending_orders:
                if order.get('token') == token:
                    try:
                        # await self.cancel_order(order)
                        pass
                    except Exception as e:
                        logger.error(f"Failed to cancel order: {e}")


# =============================================================================
# Example 5: Background Task Integration
# =============================================================================

async def emergency_stop_background_task():
    """
    Background task that monitors emergency stop status.

    Useful for logging, metrics, or triggering actions on state changes.
    """
    emergency_manager = get_emergency_stop_manager()
    last_level = StopLevel.NONE

    while True:
        try:
            status = emergency_manager.get_status()
            current_level = StopLevel(status['level'])

            # Detect level change
            if current_level != last_level:
                logger.info(f"Emergency stop level changed: {last_level.value} -> {current_level.value}")

                # Take action based on new level
                if current_level == StopLevel.KILL_SWITCH:
                    logger.critical("🚨 KILL SWITCH ACTIVE 🚨")
                    # Trigger external alerting, paging, etc.

                elif current_level == StopLevel.NONE and last_level != StopLevel.NONE:
                    logger.info("✅ Trading resumed - emergency stop cleared")

                last_level = current_level

            # Check for auto-resume
            # (handled automatically by is_trading_allowed, but good to log)

            await asyncio.sleep(5)

        except Exception as e:
            logger.error(f"Emergency stop monitor error: {e}")
            await asyncio.sleep(5)


# =============================================================================
# Example 6: Complete Integration
# =============================================================================

async def main():
    """
    Example of complete integration in a trading bot.

    Shows all components working together.
    """
    # Initialize components
    trading_engine = TradingEngineExample()
    position_monitor = PositionMonitorExample()
    order_manager = OrderManagerExample()

    # Mock alert system
    alert_system = AlertSystemExample(None, None)

    # Start background tasks
    tasks = [
        asyncio.create_task(position_monitor.monitor_loop()),
        asyncio.create_task(emergency_stop_background_task()),
    ]

    # Simulate trading
    try:
        # Try to open position (will check emergency stop)
        success, msg, position = await trading_engine.open_position(
            token_mint="EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
            amount_usd=100.0
        )

        if success:
            logger.info(f"Position opened: {position}")
        else:
            logger.warning(f"Position blocked: {msg}")

        # Process orders (will respect emergency stop)
        await order_manager.process_orders()

        # Keep running
        await asyncio.gather(*tasks)

    except KeyboardInterrupt:
        logger.info("Shutting down...")
        for task in tasks:
            task.cancel()


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    asyncio.run(main())
