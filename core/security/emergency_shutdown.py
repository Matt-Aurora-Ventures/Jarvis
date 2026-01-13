"""
JARVIS Emergency Shutdown - Circuit Breaker for Critical Operations

Provides kill switch for treasury and trading operations.
Can be triggered manually or automatically based on conditions.

Features:
- Immediate halt of all trading
- Wallet lock-out
- Notification broadcast
- Audit logging
- Recovery procedures

Usage:
    from core.security.emergency_shutdown import EmergencyShutdown, trigger_emergency

    # Quick shutdown
    trigger_emergency("Market crash detected")

    # With recovery
    shutdown = EmergencyShutdown()
    shutdown.trigger("Security breach suspected")
    # ... later ...
    shutdown.recover(admin_key="...")
"""

import asyncio
import json
import logging
import os
import threading
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[2]
SHUTDOWN_FILE = ROOT / "data" / ".emergency_shutdown"
SHUTDOWN_LOG = ROOT / "data" / "emergency_shutdown_log.json"


class ShutdownReason(Enum):
    """Categories of emergency shutdown reasons."""
    MANUAL = "manual"                    # Admin triggered
    SECURITY = "security"                # Security breach
    MARKET = "market"                    # Market conditions
    LOSS_LIMIT = "loss_limit"            # Daily loss exceeded
    ERROR = "error"                      # Critical error
    NETWORK = "network"                  # Network issues
    DEPENDENCY = "dependency"            # Dependency failure
    MAINTENANCE = "maintenance"          # Planned maintenance


@dataclass
class ShutdownEvent:
    """Record of a shutdown event."""
    timestamp: str
    reason: str
    category: ShutdownReason
    triggered_by: str
    details: Dict[str, Any] = field(default_factory=dict)
    recovered: bool = False
    recovered_at: Optional[str] = None
    recovered_by: Optional[str] = None


@dataclass
class ShutdownState:
    """Current shutdown state."""
    is_shutdown: bool = False
    event: Optional[ShutdownEvent] = None
    blocked_operations: List[str] = field(default_factory=list)


class EmergencyShutdown:
    """
    Emergency shutdown controller.

    When triggered:
    1. Sets global shutdown flag
    2. Blocks all trading operations
    3. Locks wallet access
    4. Sends notifications
    5. Logs the event
    6. Optionally moves funds to cold wallet
    """

    # Operations blocked during shutdown
    BLOCKED_OPERATIONS = [
        "trading.execute",
        "trading.swap",
        "wallet.transfer",
        "wallet.sign",
        "treasury.trade",
        "treasury.distribute",
        "bot.buy",
        "bot.sell",
    ]

    def __init__(self):
        self._state = ShutdownState()
        self._callbacks: List[Callable[[ShutdownEvent], None]] = []
        self._recovery_callbacks: List[Callable[[], None]] = []
        self._lock = threading.Lock()

        # Load persisted state
        self._load_state()

    def _load_state(self):
        """Load shutdown state from disk."""
        if SHUTDOWN_FILE.exists():
            try:
                data = json.loads(SHUTDOWN_FILE.read_text())
                self._state.is_shutdown = data.get("is_shutdown", False)

                if event_data := data.get("event"):
                    event_data["category"] = ShutdownReason(event_data["category"])
                    self._state.event = ShutdownEvent(**event_data)

                self._state.blocked_operations = data.get(
                    "blocked_operations",
                    self.BLOCKED_OPERATIONS
                )

                if self._state.is_shutdown:
                    logger.warning("Emergency shutdown state persisted - system is locked")

            except Exception as e:
                logger.error(f"Failed to load shutdown state: {e}")

    def _save_state(self):
        """Persist shutdown state to disk."""
        try:
            data = {
                "is_shutdown": self._state.is_shutdown,
                "blocked_operations": self._state.blocked_operations,
            }

            if self._state.event:
                event_dict = asdict(self._state.event)
                event_dict["category"] = self._state.event.category.value
                data["event"] = event_dict

            SHUTDOWN_FILE.write_text(json.dumps(data, indent=2))

        except Exception as e:
            logger.error(f"Failed to save shutdown state: {e}")

    def _log_event(self, event: ShutdownEvent):
        """Log shutdown event to history."""
        try:
            history = []
            if SHUTDOWN_LOG.exists():
                history = json.loads(SHUTDOWN_LOG.read_text())

            event_dict = asdict(event)
            event_dict["category"] = event.category.value
            history.append(event_dict)

            # Keep last 100 events
            history = history[-100:]

            SHUTDOWN_LOG.write_text(json.dumps(history, indent=2))

        except Exception as e:
            logger.error(f"Failed to log shutdown event: {e}")

    def on_shutdown(self, callback: Callable[[ShutdownEvent], None]):
        """Register callback for shutdown events."""
        self._callbacks.append(callback)

    def on_recovery(self, callback: Callable[[], None]):
        """Register callback for recovery events."""
        self._recovery_callbacks.append(callback)

    def trigger(
        self,
        reason: str,
        category: ShutdownReason = ShutdownReason.MANUAL,
        triggered_by: str = "system",
        **details
    ) -> ShutdownEvent:
        """
        Trigger emergency shutdown.

        Args:
            reason: Human-readable reason
            category: Category of shutdown
            triggered_by: Who/what triggered it
            **details: Additional context

        Returns:
            The shutdown event
        """
        with self._lock:
            event = ShutdownEvent(
                timestamp=datetime.now().isoformat(),
                reason=reason,
                category=category,
                triggered_by=triggered_by,
                details=details,
            )

            self._state.is_shutdown = True
            self._state.event = event
            self._state.blocked_operations = self.BLOCKED_OPERATIONS.copy()

            # Persist immediately
            self._save_state()
            self._log_event(event)

            logger.critical(f"EMERGENCY SHUTDOWN: {reason} [{category.value}]")

            # Notify callbacks
            for callback in self._callbacks:
                try:
                    callback(event)
                except Exception as e:
                    logger.error(f"Shutdown callback failed: {e}")

            return event

    def recover(
        self,
        admin_key: Optional[str] = None,
        recovered_by: str = "admin"
    ) -> bool:
        """
        Recover from emergency shutdown.

        Args:
            admin_key: Admin authentication (optional)
            recovered_by: Who is performing recovery

        Returns:
            True if recovery successful
        """
        with self._lock:
            if not self._state.is_shutdown:
                logger.info("System is not in shutdown state")
                return True

            # Verify admin key if required
            expected_key = os.getenv("JARVIS_ADMIN_KEY")
            if expected_key and admin_key != expected_key:
                logger.warning(f"Recovery attempted with invalid admin key by {recovered_by}")
                return False

            # Update event
            if self._state.event:
                self._state.event.recovered = True
                self._state.event.recovered_at = datetime.now().isoformat()
                self._state.event.recovered_by = recovered_by
                self._log_event(self._state.event)

            # Clear shutdown state
            self._state.is_shutdown = False
            self._state.blocked_operations = []

            self._save_state()

            logger.info(f"Emergency shutdown recovered by {recovered_by}")

            # Notify callbacks
            for callback in self._recovery_callbacks:
                try:
                    callback()
                except Exception as e:
                    logger.error(f"Recovery callback failed: {e}")

            return True

    def is_shutdown(self) -> bool:
        """Check if system is in shutdown state."""
        return self._state.is_shutdown

    def is_operation_blocked(self, operation: str) -> bool:
        """
        Check if a specific operation is blocked.

        Args:
            operation: Operation name (e.g., "trading.execute")

        Returns:
            True if operation is blocked
        """
        if not self._state.is_shutdown:
            return False

        return operation in self._state.blocked_operations

    def get_state(self) -> ShutdownState:
        """Get current shutdown state."""
        return self._state

    def get_history(self, limit: int = 10) -> List[Dict]:
        """Get shutdown event history."""
        if not SHUTDOWN_LOG.exists():
            return []

        try:
            history = json.loads(SHUTDOWN_LOG.read_text())
            return history[-limit:]
        except Exception:
            return []


# Global instance
_shutdown: Optional[EmergencyShutdown] = None


def get_emergency_shutdown() -> EmergencyShutdown:
    """Get singleton emergency shutdown instance."""
    global _shutdown
    if _shutdown is None:
        _shutdown = EmergencyShutdown()
    return _shutdown


def trigger_emergency(
    reason: str,
    category: ShutdownReason = ShutdownReason.MANUAL,
    **details
) -> ShutdownEvent:
    """Quick trigger for emergency shutdown."""
    shutdown = get_emergency_shutdown()
    return shutdown.trigger(reason, category, **details)


def is_emergency_shutdown() -> bool:
    """Check if system is in emergency shutdown."""
    return get_emergency_shutdown().is_shutdown()


def check_operation(operation: str) -> bool:
    """
    Check if an operation is allowed.

    Use this decorator or direct check before critical operations.

    Args:
        operation: Operation name

    Returns:
        True if allowed, False if blocked

    Raises:
        EmergencyShutdownError if blocked
    """
    shutdown = get_emergency_shutdown()

    if shutdown.is_operation_blocked(operation):
        raise EmergencyShutdownError(
            f"Operation '{operation}' blocked due to emergency shutdown: "
            f"{shutdown.get_state().event.reason if shutdown.get_state().event else 'Unknown'}"
        )

    return True


class EmergencyShutdownError(Exception):
    """Raised when operation is blocked due to emergency shutdown."""
    pass


def require_operational(operation: str):
    """
    Decorator to require system is operational.

    Usage:
        @require_operational("trading.execute")
        async def execute_trade(...):
            ...
    """
    def decorator(func):
        async def async_wrapper(*args, **kwargs):
            check_operation(operation)
            return await func(*args, **kwargs)

        def sync_wrapper(*args, **kwargs):
            check_operation(operation)
            return func(*args, **kwargs)

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator


# Auto-trigger conditions
class AutoShutdownMonitor:
    """
    Monitor for automatic shutdown triggers.

    Watches for conditions that should trigger emergency shutdown:
    - Daily loss limit exceeded
    - Rapid consecutive losses
    - API errors exceeding threshold
    - Memory/CPU critical levels
    """

    def __init__(
        self,
        daily_loss_limit: float = 0.10,  # 10%
        consecutive_losses: int = 5,
        error_threshold: int = 10,
    ):
        self.daily_loss_limit = daily_loss_limit
        self.consecutive_losses = consecutive_losses
        self.error_threshold = error_threshold

        self._loss_count = 0
        self._error_count = 0
        self._daily_pnl = 0.0
        self._running = False

    def record_trade(self, pnl: float):
        """Record a trade result."""
        self._daily_pnl += pnl

        if pnl < 0:
            self._loss_count += 1
        else:
            self._loss_count = 0

        # Check triggers
        if self._loss_count >= self.consecutive_losses:
            trigger_emergency(
                f"Consecutive loss limit ({self.consecutive_losses}) exceeded",
                ShutdownReason.LOSS_LIMIT,
                consecutive_losses=self._loss_count,
            )

        if abs(self._daily_pnl) > self.daily_loss_limit:
            trigger_emergency(
                f"Daily loss limit ({self.daily_loss_limit:.1%}) exceeded",
                ShutdownReason.LOSS_LIMIT,
                daily_pnl=self._daily_pnl,
            )

    def record_error(self):
        """Record an error occurrence."""
        self._error_count += 1

        if self._error_count >= self.error_threshold:
            trigger_emergency(
                f"Error threshold ({self.error_threshold}) exceeded",
                ShutdownReason.ERROR,
                error_count=self._error_count,
            )

    def reset_daily(self):
        """Reset daily counters."""
        self._daily_pnl = 0.0
        self._loss_count = 0
        self._error_count = 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    print("Emergency Shutdown Test")
    print("=" * 40)

    shutdown = get_emergency_shutdown()

    print(f"Current state: {'SHUTDOWN' if shutdown.is_shutdown() else 'OPERATIONAL'}")

    if shutdown.is_shutdown():
        print(f"\nReason: {shutdown.get_state().event.reason if shutdown.get_state().event else 'Unknown'}")

        response = input("\nRecover system? [y/N]: ")
        if response.lower() == 'y':
            admin_key = input("Enter admin key (or press Enter to skip): ").strip()
            if shutdown.recover(admin_key=admin_key or None, recovered_by="cli"):
                print("[OK] System recovered")
            else:
                print("[FAIL] Recovery failed (check admin key)")
    else:
        response = input("\nTrigger test shutdown? [y/N]: ")
        if response.lower() == 'y':
            reason = input("Reason: ") or "CLI test"
            shutdown.trigger(reason, ShutdownReason.MANUAL, triggered_by="cli_test")
            print("[OK] Shutdown triggered")

    print("\nHistory:")
    for event in shutdown.get_history(5):
        print(f"  {event['timestamp']}: {event['reason']} [{event['category']}]")
