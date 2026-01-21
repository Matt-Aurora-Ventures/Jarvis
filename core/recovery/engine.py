"""
Unified Recovery Engine - One brain for all recovery decisions.

This engine centralizes:
- Retry logic with exponential backoff
- Circuit breakers
- Cooldown management
- Failure tracking
- Escalation

Bots are adapters, not decision-makers. All recovery logic lives here.
"""

import asyncio
import logging
import random
import threading
import time
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional, Tuple, Type, TypeVar

from .config import (
    ComponentConfig,
    RecoveryContext,
    RecoveryOutcome,
    RecoveryPolicy,
    TELEGRAM_CONFIG,
    X_BOT_CONFIG,
    TRADING_CONFIG,
    TOOL_CONFIG,
)

logger = logging.getLogger(__name__)

T = TypeVar("T")

# Singleton instance
_recovery_engine: Optional["RecoveryEngine"] = None


class CircuitState:
    """Circuit breaker state for a component."""

    def __init__(self, config: ComponentConfig):
        self.config = config
        self.state = "closed"  # closed, open, half_open
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time: Optional[float] = None
        self.opened_at: Optional[float] = None
        self.half_open_attempts = 0
        self._lock = threading.Lock()

    def can_execute(self) -> bool:
        """Check if execution is allowed."""
        with self._lock:
            if self.state == "closed":
                return True

            if self.state == "open":
                # Check if cooldown has passed
                if self.opened_at:
                    cooldown_end = self.opened_at + self.config.circuit_cooldown
                    if time.time() > cooldown_end:
                        self.state = "half_open"
                        self.half_open_attempts = 0
                        return True
                return False

            if self.state == "half_open":
                return self.half_open_attempts < self.config.circuit_half_open_max

            return False

    def record_success(self) -> None:
        """Record a successful execution."""
        with self._lock:
            if self.state == "half_open":
                self.success_count += 1
                if self.success_count >= self.config.circuit_success_threshold:
                    self._close()
            elif self.state == "closed":
                # Reset failure count on success
                self.failure_count = max(0, self.failure_count - 1)

    def record_failure(self) -> None:
        """Record a failed execution."""
        with self._lock:
            self.failure_count += 1
            self.last_failure_time = time.time()

            if self.state == "half_open":
                self._open()
            elif self.failure_count >= self.config.circuit_threshold:
                self._open()

    def _open(self) -> None:
        """Open the circuit."""
        self.state = "open"
        self.opened_at = time.time()
        self.success_count = 0
        self.half_open_attempts = 0
        logger.warning(f"Circuit breaker OPENED after {self.failure_count} failures")

    def _close(self) -> None:
        """Close the circuit."""
        self.state = "closed"
        self.failure_count = 0
        self.success_count = 0
        self.opened_at = None
        logger.info("Circuit breaker CLOSED after successful recovery")

    def get_status(self) -> Dict[str, Any]:
        """Get circuit status."""
        with self._lock:
            remaining_cooldown = 0
            if self.state == "open" and self.opened_at:
                cooldown_end = self.opened_at + self.config.circuit_cooldown
                remaining_cooldown = max(0, cooldown_end - time.time())

            return {
                "state": self.state,
                "failure_count": self.failure_count,
                "success_count": self.success_count,
                "remaining_cooldown": remaining_cooldown,
            }


class RecoveryEngine:
    """
    Unified recovery engine for all components.

    This is the single source of truth for recovery decisions.
    Components register with the engine and delegate all retry/circuit
    logic to it.
    """

    def __init__(self):
        self.components: Dict[str, ComponentConfig] = {}
        self.circuits: Dict[str, CircuitState] = {}
        self.operation_stats: Dict[str, Dict[str, int]] = {}
        self._lock = threading.Lock()

        # Escalation callbacks
        self._escalation_callbacks: List[Callable] = []

        # Register default components
        self._register_defaults()

    def _register_defaults(self) -> None:
        """Register default component configurations."""
        self.register_component("telegram_bot", TELEGRAM_CONFIG)
        self.register_component("x_bot", X_BOT_CONFIG)
        self.register_component("trading", TRADING_CONFIG)
        self.register_component("tools", TOOL_CONFIG)

    def register_component(
        self,
        name: str,
        config: Optional[ComponentConfig] = None,
    ) -> None:
        """Register a component with its recovery configuration."""
        with self._lock:
            self.components[name] = config or ComponentConfig()
            self.circuits[name] = CircuitState(self.components[name])
            self.operation_stats[name] = {
                "total": 0,
                "successes": 0,
                "failures": 0,
                "retries": 0,
                "circuit_opens": 0,
            }
            logger.info(f"Registered recovery component: {name}")

    def on_escalation(self, callback: Callable) -> None:
        """Register a callback for escalation events."""
        self._escalation_callbacks.append(callback)

    def can_execute(self, component: str) -> bool:
        """Check if a component can execute."""
        circuit = self.circuits.get(component)
        if not circuit:
            return True  # Unknown components can always execute
        return circuit.can_execute()

    def get_circuit_status(self, component: str) -> Dict[str, Any]:
        """Get circuit breaker status for a component."""
        circuit = self.circuits.get(component)
        if not circuit:
            return {"state": "unknown", "failure_count": 0}
        return circuit.get_status()

    def record_success(self, component: str, operation: str = "") -> None:
        """Record a successful operation."""
        circuit = self.circuits.get(component)
        if circuit:
            circuit.record_success()

        with self._lock:
            stats = self.operation_stats.get(component, {})
            stats["total"] = stats.get("total", 0) + 1
            stats["successes"] = stats.get("successes", 0) + 1
            self.operation_stats[component] = stats

    def record_failure(
        self,
        component: str,
        operation: str = "",
        error: str = "",
    ) -> None:
        """Record a failed operation."""
        circuit = self.circuits.get(component)
        if circuit:
            circuit.record_failure()

        with self._lock:
            stats = self.operation_stats.get(component, {})
            stats["total"] = stats.get("total", 0) + 1
            stats["failures"] = stats.get("failures", 0) + 1
            self.operation_stats[component] = stats

        logger.warning(f"Recovery: {component}:{operation} failed - {error}")

    def calculate_delay(
        self,
        component: str,
        attempt: int,
    ) -> float:
        """Calculate the delay before the next retry."""
        config = self.components.get(component, ComponentConfig())

        # Exponential backoff with jitter
        delay = config.retry_base_delay * (config.retry_multiplier ** (attempt - 1))
        delay = min(delay, config.retry_max_delay)

        # Add jitter
        jitter = delay * config.retry_jitter * random.random()
        delay += jitter

        return delay

    def should_retry(
        self,
        component: str,
        attempt: int,
        error: Exception,
    ) -> bool:
        """Determine if an operation should be retried."""
        config = self.components.get(component, ComponentConfig())

        # Check attempt count
        if attempt >= config.max_retries:
            return False

        # Check non-retryable errors
        if isinstance(error, config.non_retryable_errors):
            return False

        # Check retryable errors (if specified)
        if config.retryable_errors and not isinstance(error, config.retryable_errors):
            # Check for common transient error patterns
            error_msg = str(error).lower()
            transient_patterns = [
                "connection", "timeout", "temporary", "busy",
                "unavailable", "rate limit", "reset by peer",
                "network", "dns", "socket", "429", "503",
            ]
            if not any(p in error_msg for p in transient_patterns):
                return False

        # Check circuit state
        if not self.can_execute(component):
            return False

        return True

    async def execute_with_recovery(
        self,
        component: str,
        operation: str,
        func: Callable[..., T],
        args: Tuple = (),
        kwargs: Optional[Dict[str, Any]] = None,
    ) -> Tuple[Optional[T], RecoveryContext]:
        """
        Execute a function with automatic recovery.

        This is the main entry point for recoverable operations.
        Returns (result, context) where context contains full recovery info.
        """
        kwargs = kwargs or {}
        config = self.components.get(component, ComponentConfig())

        context = RecoveryContext(
            component=component,
            operation=operation,
            attempt=0,
            max_attempts=config.max_retries,
            started_at=datetime.utcnow(),
        )

        # Check circuit breaker first
        if not self.can_execute(component):
            context.circuit_state = "open"
            context.outcome = RecoveryOutcome.CIRCUIT_OPEN
            context.ended_at = datetime.utcnow()
            return None, context

        # Attempt execution with retries
        last_error: Optional[Exception] = None

        for attempt in range(1, config.max_retries + 1):
            context.attempt = attempt

            try:
                # Execute the function
                if asyncio.iscoroutinefunction(func):
                    result = await func(*args, **kwargs)
                else:
                    result = func(*args, **kwargs)

                # Success
                context.result = result
                context.outcome = RecoveryOutcome.SUCCESS
                context.ended_at = datetime.utcnow()
                self.record_success(component, operation)

                # Fire success callback
                if config.on_recovery and attempt > 1:
                    try:
                        config.on_recovery(context)
                    except Exception:
                        pass

                return result, context

            except Exception as e:
                last_error = e
                context.add_error(e)

                # Check if we should retry
                if not self.should_retry(component, attempt, e):
                    break

                # Calculate delay
                delay = self.calculate_delay(component, attempt)
                context.delays.append(delay)
                context.total_delay += delay

                logger.info(
                    f"Recovery: {component}:{operation} attempt {attempt} failed, "
                    f"retrying in {delay:.1f}s - {e}"
                )

                # Wait before retry
                await asyncio.sleep(delay)

                # Update stats
                with self._lock:
                    stats = self.operation_stats.get(component, {})
                    stats["retries"] = stats.get("retries", 0) + 1
                    self.operation_stats[component] = stats

        # All retries exhausted
        self.record_failure(component, operation, str(last_error) if last_error else "")
        context.ended_at = datetime.utcnow()

        # Try fallback if available
        if config.fallback:
            try:
                if asyncio.iscoroutinefunction(config.fallback):
                    result = await config.fallback(*args, **kwargs)
                else:
                    result = config.fallback(*args, **kwargs)

                context.result = result
                context.outcome = RecoveryOutcome.FALLBACK_USED
                context.used_fallback = True
                return result, context
            except Exception as fallback_error:
                context.add_error(fallback_error)

        # Check if escalation is in policies
        if RecoveryPolicy.ESCALATE in config.policies:
            await self._escalate(context)
            context.outcome = RecoveryOutcome.ESCALATED
            context.escalated = True
        else:
            context.outcome = RecoveryOutcome.FAILED

        # Fire failure callback
        if config.on_failure:
            try:
                config.on_failure(context)
            except Exception:
                pass

        return None, context

    async def _escalate(self, context: RecoveryContext) -> None:
        """Escalate a failure to humans."""
        logger.error(
            f"ESCALATION: {context.component}:{context.operation} "
            f"failed after {context.attempt} attempts - {context.last_error}"
        )

        for callback in self._escalation_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(context)
                else:
                    callback(context)
            except Exception as e:
                logger.error(f"Escalation callback error: {e}")

        # Try to send Telegram notification
        try:
            await self._send_telegram_escalation(context)
        except Exception as e:
            logger.debug(f"Telegram escalation failed: {e}")

    async def _send_telegram_escalation(self, context: RecoveryContext) -> None:
        """Send escalation notification via Telegram."""
        import os
        import aiohttp

        token = os.environ.get("TELEGRAM_BOT_TOKEN")
        admin_ids = os.environ.get("TELEGRAM_ADMIN_IDS", "")

        if not token or not admin_ids:
            return

        admin_list = [x.strip() for x in admin_ids.split(",") if x.strip().isdigit()]
        if not admin_list:
            return

        message = (
            f"🚨 <b>Recovery Escalation</b>\n\n"
            f"<b>Component:</b> {context.component}\n"
            f"<b>Operation:</b> {context.operation}\n"
            f"<b>Attempts:</b> {context.attempt}/{context.max_attempts}\n"
            f"<b>Total delay:</b> {context.total_delay:.1f}s\n"
            f"<b>Error:</b> <code>{context.last_error[:200] if context.last_error else 'Unknown'}</code>\n"
            f"<b>Circuit:</b> {context.circuit_state}\n\n"
            f"Manual intervention may be required."
        )

        async with aiohttp.ClientSession() as session:
            for admin_id in admin_list[:2]:
                url = f"https://api.telegram.org/bot{token}/sendMessage"
                await session.post(url, json={
                    "chat_id": admin_id,
                    "text": message,
                    "parse_mode": "HTML",
                })

    def get_stats(self) -> Dict[str, Any]:
        """Get recovery statistics for all components."""
        with self._lock:
            stats = {}
            for component, op_stats in self.operation_stats.items():
                circuit = self.circuits.get(component)
                stats[component] = {
                    **op_stats,
                    "circuit": circuit.get_status() if circuit else None,
                    "success_rate": (
                        op_stats.get("successes", 0) / op_stats.get("total", 1)
                        if op_stats.get("total", 0) > 0
                        else 1.0
                    ),
                }
            return stats

    def reset_circuit(self, component: str) -> bool:
        """Manually reset a circuit breaker."""
        circuit = self.circuits.get(component)
        if not circuit:
            return False

        with circuit._lock:
            circuit.state = "closed"
            circuit.failure_count = 0
            circuit.success_count = 0
            circuit.opened_at = None

        logger.info(f"Circuit breaker manually reset: {component}")
        return True


def get_recovery_engine() -> RecoveryEngine:
    """Get or create the singleton recovery engine."""
    global _recovery_engine
    if _recovery_engine is None:
        _recovery_engine = RecoveryEngine()
    return _recovery_engine
