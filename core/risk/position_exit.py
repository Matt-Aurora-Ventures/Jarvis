"""
Position Exit Execution Module

Handles execution of position exits triggered by TP/SL/ladder conditions.

REQ-005: Exits must execute within 15 seconds of trigger.
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Protocol

logger = logging.getLogger(__name__)

# Exit must complete within 15 seconds (REQ-005)
EXIT_TIMEOUT_SECONDS = 15


# =============================================================================
# Protocol Definitions
# =============================================================================

class SwapServiceProtocol(Protocol):
    """Protocol for swap execution service."""

    async def execute_sell(
        self,
        token_mint: str,
        amount: float,
        wallet_address: str
    ) -> Dict[str, Any]:
        """Execute a sell swap."""
        ...


class NotifierProtocol(Protocol):
    """Protocol for notification service."""

    async def send_exit_notification(
        self,
        position_id: str,
        trigger: str,
        pnl_usd: float,
        pnl_pct: float,
        tx_hash: Optional[str] = None
    ) -> None:
        """Send notification about position exit."""
        ...


# =============================================================================
# Position Exit Executor
# =============================================================================

class PositionExitExecutor:
    """
    Executes position exits when triggered by TP/SL/ladder conditions.

    Features:
    - Full exits (TP/SL)
    - Partial exits (ladder tiers)
    - Notifications on exit
    - Timeout enforcement (15s max)

    Usage:
        executor = PositionExitExecutor(swap_service=swap, notifier=notifier)
        result = await executor.execute_exit(position, trigger="tp", exit_percent=100)
    """

    def __init__(
        self,
        swap_service: Optional[SwapServiceProtocol] = None,
        notifier: Optional[NotifierProtocol] = None,
    ):
        """
        Initialize exit executor.

        Args:
            swap_service: Service for executing swaps
            notifier: Service for sending notifications
        """
        self.swap_service = swap_service
        self.notifier = notifier

    async def execute_exit(
        self,
        position: Any,
        trigger: str,
        exit_percent: int,
        ladder_tier: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Execute a position exit.

        Args:
            position: Position to exit
            trigger: Exit trigger ("tp", "sl", "ladder")
            exit_percent: Percentage of position to sell (1-100)
            ladder_tier: Ladder tier index (if ladder trigger)

        Returns:
            Dict with execution result:
            - success: bool
            - exit_type: str (trigger type)
            - amount_sold: float
            - tx_hash: str (if successful)
            - pnl_usd: float (realized P&L)
            - pnl_pct: float (realized P&L %)
            - error: str (if failed)
        """
        result = {
            "success": False,
            "exit_type": trigger,
            "amount_sold": 0.0,
            "position_id": position.id,
            "ladder_tier": ladder_tier,
        }

        try:
            # Calculate amount to sell
            amount_to_sell = position.amount * (exit_percent / 100)
            result["amount_sold"] = amount_to_sell

            logger.info(
                f"Executing {trigger} exit for {position.token_symbol}: "
                f"{exit_percent}% = {amount_to_sell:.4f} tokens"
            )

            # Execute with timeout (REQ-005: 15s max)
            if self.swap_service:
                swap_result = await asyncio.wait_for(
                    self.swap_service.execute_sell(
                        token_mint=position.token_mint,
                        amount=amount_to_sell,
                        wallet_address=getattr(position, 'wallet_address', ''),
                    ),
                    timeout=EXIT_TIMEOUT_SECONDS
                )

                if swap_result.get("success"):
                    result["success"] = True
                    result["tx_hash"] = swap_result.get("tx_hash")
                    result["amount_out"] = swap_result.get("amount_out", 0)
                else:
                    result["error"] = swap_result.get("error", "Swap failed")
            else:
                # No swap service - simulate success for testing
                result["success"] = True
                result["tx_hash"] = "simulated_tx_hash"

            # Calculate P&L
            if result["success"]:
                entry_value = amount_to_sell * position.entry_price
                exit_value = amount_to_sell * position.current_price
                result["pnl_usd"] = exit_value - entry_value
                result["pnl_pct"] = (
                    ((position.current_price - position.entry_price) / position.entry_price) * 100
                    if position.entry_price > 0 else 0
                )

                # Send notification
                if self.notifier:
                    await self._send_notification(position, result, trigger)

                logger.info(
                    f"Exit executed for {position.token_symbol}: "
                    f"P&L ${result['pnl_usd']:.2f} ({result['pnl_pct']:+.1f}%)"
                )

        except asyncio.TimeoutError:
            result["error"] = f"Exit timed out after {EXIT_TIMEOUT_SECONDS}s"
            logger.error(
                f"Exit timeout for {position.token_symbol} ({trigger}): "
                f"exceeded {EXIT_TIMEOUT_SECONDS}s limit"
            )

        except Exception as e:
            result["error"] = str(e)
            logger.error(
                f"Exit failed for {position.token_symbol}: {e}",
                exc_info=True
            )

        return result

    async def _send_notification(
        self,
        position: Any,
        result: Dict[str, Any],
        trigger: str
    ) -> None:
        """Send exit notification."""
        try:
            await self.notifier.send_exit_notification(
                position_id=position.id,
                trigger=trigger,
                pnl_usd=result.get("pnl_usd", 0),
                pnl_pct=result.get("pnl_pct", 0),
                tx_hash=result.get("tx_hash"),
            )
        except Exception as e:
            logger.warning(f"Failed to send exit notification: {e}")


# =============================================================================
# Singleton Access
# =============================================================================

_EXECUTOR_INSTANCE: Optional[PositionExitExecutor] = None


def get_exit_executor(
    swap_service: Optional[SwapServiceProtocol] = None,
    notifier: Optional[NotifierProtocol] = None,
) -> PositionExitExecutor:
    """
    Get or create the PositionExitExecutor singleton.

    Args:
        swap_service: Service for executing swaps
        notifier: Service for sending notifications

    Returns:
        PositionExitExecutor instance
    """
    global _EXECUTOR_INSTANCE

    if _EXECUTOR_INSTANCE is None:
        _EXECUTOR_INSTANCE = PositionExitExecutor(
            swap_service=swap_service,
            notifier=notifier,
        )

    return _EXECUTOR_INSTANCE


# =============================================================================
# Notification Formatters
# =============================================================================

def format_exit_notification(
    position: Any,
    trigger: str,
    pnl_usd: float,
    pnl_pct: float,
    tx_hash: Optional[str] = None,
) -> str:
    """
    Format exit notification for Telegram.

    Args:
        position: Exited position
        trigger: Exit trigger type
        pnl_usd: Realized P&L in USD
        pnl_pct: Realized P&L percentage
        tx_hash: Transaction hash

    Returns:
        Formatted notification message
    """
    trigger_emoji = {
        "tp": "TARGET HIT",
        "sl": "STOP LOSS",
        "ladder": "LADDER EXIT",
    }.get(trigger, "EXIT")

    pnl_emoji = "+" if pnl_usd >= 0 else ""
    status_emoji = "WIN" if pnl_usd >= 0 else "LOSS"

    tx_link = ""
    if tx_hash:
        tx_link = f"\nTX: https://solscan.io/tx/{tx_hash}"

    return f"""
{trigger_emoji} - {position.token_symbol}

{status_emoji} P&L: {pnl_emoji}${abs(pnl_usd):.2f} ({pnl_pct:+.1f}%)

Entry: ${position.entry_price:.8f}
Exit: ${position.current_price:.8f}
{tx_link}
""".strip()
