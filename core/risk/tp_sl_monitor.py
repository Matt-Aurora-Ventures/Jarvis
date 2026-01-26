"""
TP/SL Order Monitoring Service

Continuously monitors open positions and executes exits when:
- Take-profit price is reached
- Stop-loss price is breached
- Ladder exit tiers are triggered

REQ-005: Stop-loss and take-profit enforcement
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Protocol

logger = logging.getLogger(__name__)

# Import shutdown manager for graceful cleanup
try:
    from core.shutdown_manager import get_shutdown_manager, ShutdownPhase
    SHUTDOWN_MANAGER_AVAILABLE = True
except ImportError:
    SHUTDOWN_MANAGER_AVAILABLE = False
    get_shutdown_manager = None
    ShutdownPhase = None


# =============================================================================
# Default Ladder Exit Configuration
# =============================================================================

DEFAULT_LADDER_EXITS: List[Dict[str, Any]] = [
    {"pnl_multiple": 2.0, "percent": 50},   # 50% at 2x
    {"pnl_multiple": 5.0, "percent": 30},   # 30% at 5x
    {"pnl_multiple": 10.0, "percent": 20},  # 20% at 10x
]


def create_ladder_exits(
    template: Optional[List[Dict[str, Any]]] = None
) -> List[Dict[str, Any]]:
    """
    Create ladder exit configuration from template.

    Each exit tier tracks:
    - pnl_multiple: Price multiple for trigger (e.g., 2.0 = 2x entry)
    - percent: Percentage of position to sell at this tier
    - executed: Whether this tier has been executed

    Args:
        template: Custom ladder config (defaults to DEFAULT_LADDER_EXITS)

    Returns:
        List of ladder exit configurations with executed=False
    """
    source = template if template else DEFAULT_LADDER_EXITS
    return [
        {
            "pnl_multiple": tier["pnl_multiple"],
            "percent": tier["percent"],
            "executed": False
        }
        for tier in source
    ]


# =============================================================================
# Protocol Definitions
# =============================================================================

class PriceService(Protocol):
    """Protocol for price fetching service."""

    async def get_token_price(self, token_mint: str) -> float:
        """Get current price for a token."""
        ...


class PositionManagerProtocol(Protocol):
    """Protocol for position management."""

    def get_open_positions(self) -> List[Any]:
        """Get all open positions."""
        ...

    def save_state(self) -> None:
        """Save position state."""
        ...


class ExitExecutorProtocol(Protocol):
    """Protocol for exit execution."""

    async def execute_exit(
        self,
        position: Any,
        trigger: str,
        exit_percent: int,
        ladder_tier: Optional[int] = None
    ) -> Dict[str, Any]:
        """Execute position exit."""
        ...


# =============================================================================
# TPSLMonitor Service
# =============================================================================

class TPSLMonitor:
    """
    Order monitoring service for TP/SL enforcement.

    Features:
    - Polls every 10 seconds (configurable)
    - Checks all open positions against current prices
    - Triggers exits when TP/SL conditions are met
    - Supports ladder exits (partial exits at price tiers)

    Usage:
        monitor = TPSLMonitor(position_manager=pm, price_service=ps)
        await monitor.start()  # Runs until stop() is called
    """

    def __init__(
        self,
        position_manager: Optional[PositionManagerProtocol] = None,
        price_service: Optional[PriceService] = None,
        exit_executor: Optional[ExitExecutorProtocol] = None,
        poll_interval: int = 10,
    ):
        """
        Initialize TP/SL monitor.

        Args:
            position_manager: Manager for position state
            price_service: Service for fetching token prices
            exit_executor: Service for executing exits
            poll_interval: Seconds between price checks (default 10)
        """
        self.position_manager = position_manager
        self.price_service = price_service
        self.exit_executor = exit_executor
        self.poll_interval = poll_interval
        self.running = False
        self._task: Optional[asyncio.Task] = None

        # Register with shutdown manager
        if SHUTDOWN_MANAGER_AVAILABLE:
            shutdown_mgr = get_shutdown_manager()
            shutdown_mgr.register_hook(
                name="tp_sl_monitor",
                callback=self.stop,
                phase=ShutdownPhase.IMMEDIATE,
                timeout=10.0,
                priority=80,
            )
            logger.debug("TP/SL monitor registered with shutdown manager")

    async def start(self) -> None:
        """Start the monitoring loop."""
        if self.running:
            logger.warning("TPSLMonitor already running")
            return

        self.running = True
        logger.info(f"TPSLMonitor started (poll_interval={self.poll_interval}s)")

        try:
            while self.running:
                try:
                    await self.check_all_positions()
                except Exception as e:
                    logger.error(f"Error in monitoring loop: {e}", exc_info=True)

                await asyncio.sleep(self.poll_interval)
        except asyncio.CancelledError:
            logger.info("TPSLMonitor cancelled")
        finally:
            self.running = False

    async def stop(self) -> None:
        """Stop the monitoring loop."""
        self.running = False
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("TPSLMonitor stopped")

    async def check_all_positions(self) -> List[Dict[str, Any]]:
        """
        Check all open positions against current prices.

        Returns:
            List of check results for each position
        """
        if not self.position_manager:
            return []

        positions = self.position_manager.get_open_positions()
        if not positions:
            return []

        results = []
        for pos in positions:
            try:
                # Get current price
                if self.price_service:
                    current_price = await self.price_service.get_token_price(
                        pos.token_mint
                    )
                else:
                    current_price = pos.current_price

                # Check for triggers
                result = await self.check_position(pos, current_price)
                results.append(result)

                # Execute exit if triggered
                if result["should_exit"] and self.exit_executor:
                    exit_result = await self.exit_executor.execute_exit(
                        position=pos,
                        trigger=result["trigger"],
                        exit_percent=result["exit_percent"],
                        ladder_tier=result.get("ladder_tier"),
                    )
                    result["exit_result"] = exit_result

            except Exception as e:
                logger.error(
                    f"Error checking position {pos.id}: {e}",
                    exc_info=True
                )
                results.append({
                    "position_id": pos.id,
                    "error": str(e),
                    "should_exit": False,
                    "trigger": None,
                })

        return results

    async def check_position(
        self,
        position: Any,
        current_price: float
    ) -> Dict[str, Any]:
        """
        Check if a position should trigger TP/SL/ladder exit.

        Args:
            position: Position to check
            current_price: Current token price

        Returns:
            Dict with trigger info:
            - trigger: "tp" | "sl" | "ladder" | None
            - should_exit: bool
            - exit_percent: int (100 for full, partial for ladder)
            - ladder_tier: int (if ladder trigger)
        """
        result = {
            "position_id": position.id,
            "current_price": current_price,
            "trigger": None,
            "should_exit": False,
            "exit_percent": 0,
        }

        entry_price = position.entry_price
        tp_price = position.take_profit_price
        sl_price = position.stop_loss_price

        # Check stop-loss first (priority)
        if current_price <= sl_price:
            logger.warning(
                f"SL triggered for {position.token_symbol}: "
                f"price={current_price} <= sl={sl_price}"
            )
            result["trigger"] = "sl"
            result["should_exit"] = True
            result["exit_percent"] = 100
            return result

        # Check take-profit
        if current_price >= tp_price:
            logger.info(
                f"TP triggered for {position.token_symbol}: "
                f"price={current_price} >= tp={tp_price}"
            )
            result["trigger"] = "tp"
            result["should_exit"] = True
            result["exit_percent"] = 100
            return result

        # Check ladder exits
        ladder_exits = position.ladder_exits
        if ladder_exits:
            pnl_multiple = current_price / entry_price if entry_price > 0 else 0

            for tier_idx, tier in enumerate(ladder_exits):
                if tier.get("executed"):
                    continue

                if pnl_multiple >= tier["pnl_multiple"]:
                    logger.info(
                        f"Ladder exit tier {tier_idx} triggered for {position.token_symbol}: "
                        f"{pnl_multiple:.2f}x >= {tier['pnl_multiple']}x"
                    )
                    result["trigger"] = "ladder"
                    result["should_exit"] = True
                    result["exit_percent"] = tier["percent"]
                    result["ladder_tier"] = tier_idx
                    return result

        return result


# =============================================================================
# Singleton Access
# =============================================================================

_MONITOR_INSTANCE: Optional[TPSLMonitor] = None


def get_tpsl_monitor(
    position_manager: Optional[PositionManagerProtocol] = None,
    price_service: Optional[PriceService] = None,
    exit_executor: Optional[ExitExecutorProtocol] = None,
    poll_interval: int = 10,
) -> TPSLMonitor:
    """
    Get or create the TPSLMonitor singleton.

    Args:
        position_manager: Manager for position state
        price_service: Service for fetching token prices
        exit_executor: Service for executing exits
        poll_interval: Seconds between price checks

    Returns:
        TPSLMonitor instance
    """
    global _MONITOR_INSTANCE

    if _MONITOR_INSTANCE is None:
        _MONITOR_INSTANCE = TPSLMonitor(
            position_manager=position_manager,
            price_service=price_service,
            exit_executor=exit_executor,
            poll_interval=poll_interval,
        )

    return _MONITOR_INSTANCE


async def start_tpsl_monitor(
    position_manager: PositionManagerProtocol,
    price_service: PriceService,
    exit_executor: ExitExecutorProtocol,
    poll_interval: int = 10,
) -> TPSLMonitor:
    """
    Create and start a TPSLMonitor instance.

    This is the main entry point for starting the monitor service.

    Args:
        position_manager: Manager for position state
        price_service: Service for fetching token prices
        exit_executor: Service for executing exits
        poll_interval: Seconds between price checks

    Returns:
        Running TPSLMonitor instance
    """
    monitor = get_tpsl_monitor(
        position_manager=position_manager,
        price_service=price_service,
        exit_executor=exit_executor,
        poll_interval=poll_interval,
    )

    # Start in background
    asyncio.create_task(monitor.start())

    return monitor
