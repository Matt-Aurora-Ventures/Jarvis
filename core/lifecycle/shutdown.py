"""
JARVIS Graceful Shutdown Handler

Provides coordinated shutdown for all system components:
- Signal handling (SIGTERM, SIGINT)
- Connection draining
- Task completion with timeout
- Cleanup callbacks
- Health status during shutdown

Usage:
    from core.lifecycle.shutdown import ShutdownManager, get_shutdown_manager

    manager = get_shutdown_manager()

    # Register cleanup handlers
    manager.register_callback("database", cleanup_database, priority=10)
    manager.register_callback("websockets", close_websockets, priority=5)

    # Start shutdown on signal
    manager.setup_signal_handlers()
"""

import asyncio
import logging
import os
import signal
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Coroutine, Dict, List, Optional

logger = logging.getLogger("jarvis.lifecycle.shutdown")


# =============================================================================
# MODELS
# =============================================================================

class ShutdownPhase(Enum):
    """Shutdown phases"""
    RUNNING = "running"
    DRAINING = "draining"      # Stop accepting new requests
    FINISHING = "finishing"     # Complete in-flight requests
    CLEANING = "cleaning"       # Run cleanup callbacks
    STOPPED = "stopped"


@dataclass
class ShutdownCallback:
    """A registered shutdown callback"""
    name: str
    callback: Callable
    priority: int = 0  # Higher = called first
    timeout: float = 30.0
    critical: bool = False  # If True, failure is logged but doesn't stop shutdown


@dataclass
class ShutdownResult:
    """Result of a shutdown callback"""
    name: str
    success: bool
    duration_ms: float
    error: Optional[str] = None


@dataclass
class ShutdownStatus:
    """Current shutdown status"""
    phase: ShutdownPhase
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    in_flight_requests: int
    completed_callbacks: List[str]
    failed_callbacks: List[str]
    timeout_seconds: float
    reason: str


# =============================================================================
# SHUTDOWN MANAGER
# =============================================================================

class ShutdownManager:
    """
    Manages graceful shutdown of all JARVIS components.

    Features:
    - Signal handling (SIGTERM, SIGINT, SIGQUIT)
    - Callback registration with priority
    - Connection draining
    - Timeout enforcement
    - Structured shutdown phases
    """

    DEFAULT_TIMEOUT = 30.0  # seconds

    def __init__(
        self,
        timeout: float = DEFAULT_TIMEOUT,
        drain_timeout: float = 10.0,
    ):
        self.timeout = timeout
        self.drain_timeout = drain_timeout

        self._phase = ShutdownPhase.RUNNING
        self._callbacks: List[ShutdownCallback] = []
        self._results: List[ShutdownResult] = []
        self._shutdown_event = asyncio.Event()
        self._started_at: Optional[datetime] = None
        self._completed_at: Optional[datetime] = None
        self._reason = ""
        self._in_flight = 0

        # Coordination
        self._lock = asyncio.Lock()
        self._draining_complete = asyncio.Event()

    # =========================================================================
    # CALLBACK REGISTRATION
    # =========================================================================

    def register_callback(
        self,
        name: str,
        callback: Callable[[], Coroutine],
        priority: int = 0,
        timeout: float = 30.0,
        critical: bool = False,
    ):
        """
        Register a shutdown callback.

        Args:
            name: Unique name for the callback
            callback: Async function to call during shutdown
            priority: Higher priority = called first
            timeout: Maximum time to wait for callback
            critical: If True, errors are logged but don't stop shutdown
        """
        self._callbacks.append(ShutdownCallback(
            name=name,
            callback=callback,
            priority=priority,
            timeout=timeout,
            critical=critical,
        ))
        logger.debug(f"Registered shutdown callback: {name} (priority={priority})")

    def unregister_callback(self, name: str):
        """Unregister a callback by name"""
        self._callbacks = [c for c in self._callbacks if c.name != name]

    # =========================================================================
    # SIGNAL HANDLING
    # =========================================================================

    def setup_signal_handlers(self):
        """Set up signal handlers for graceful shutdown"""
        if sys.platform == "win32":
            # Windows only supports SIGINT
            signal.signal(signal.SIGINT, self._signal_handler)
        else:
            # Unix signals
            loop = asyncio.get_event_loop()

            for sig in (signal.SIGTERM, signal.SIGINT):
                loop.add_signal_handler(
                    sig,
                    lambda s=sig: asyncio.create_task(self._async_signal_handler(s))
                )

            # SIGQUIT for immediate shutdown
            loop.add_signal_handler(
                signal.SIGQUIT,
                lambda: asyncio.create_task(self.shutdown("SIGQUIT", immediate=True))
            )

        logger.info("Signal handlers configured for graceful shutdown")

    def _signal_handler(self, signum, frame):
        """Synchronous signal handler (Windows)"""
        logger.info(f"Received signal {signum}, initiating shutdown")
        asyncio.create_task(self.shutdown(f"signal_{signum}"))

    async def _async_signal_handler(self, sig):
        """Async signal handler (Unix)"""
        sig_name = signal.Signals(sig).name
        logger.info(f"Received {sig_name}, initiating shutdown")
        await self.shutdown(sig_name)

    # =========================================================================
    # SHUTDOWN EXECUTION
    # =========================================================================

    async def shutdown(
        self,
        reason: str = "manual",
        immediate: bool = False,
    ):
        """
        Initiate graceful shutdown.

        Args:
            reason: Reason for shutdown (for logging)
            immediate: If True, skip draining phase
        """
        async with self._lock:
            if self._phase != ShutdownPhase.RUNNING:
                logger.warning(f"Shutdown already in progress (phase={self._phase})")
                return

            self._phase = ShutdownPhase.DRAINING
            self._started_at = datetime.now(timezone.utc)
            self._reason = reason

        logger.info(f"Initiating shutdown: {reason}")

        try:
            # Phase 1: Draining
            if not immediate:
                await self._drain_connections()

            # Phase 2: Finishing
            self._phase = ShutdownPhase.FINISHING
            await self._wait_for_requests()

            # Phase 3: Cleanup
            self._phase = ShutdownPhase.CLEANING
            await self._run_callbacks()

            # Phase 4: Done
            self._phase = ShutdownPhase.STOPPED
            self._completed_at = datetime.now(timezone.utc)

            duration = (self._completed_at - self._started_at).total_seconds()
            logger.info(f"Shutdown complete in {duration:.2f}s")

        except Exception as e:
            logger.error(f"Shutdown error: {e}")
            self._phase = ShutdownPhase.STOPPED

        # Signal completion
        self._shutdown_event.set()

    async def _drain_connections(self):
        """Stop accepting new connections"""
        logger.info("Draining connections...")

        # Notify components to stop accepting new work
        self._draining_complete.clear()

        # Wait for drain timeout
        try:
            await asyncio.wait_for(
                self._draining_complete.wait(),
                timeout=self.drain_timeout
            )
        except asyncio.TimeoutError:
            logger.warning(f"Drain timeout ({self.drain_timeout}s)")

    async def _wait_for_requests(self):
        """Wait for in-flight requests to complete"""
        if self._in_flight <= 0:
            return

        logger.info(f"Waiting for {self._in_flight} in-flight requests...")

        start = time.time()
        while self._in_flight > 0:
            if time.time() - start > self.timeout / 2:
                logger.warning(f"Timeout waiting for requests, {self._in_flight} remaining")
                break
            await asyncio.sleep(0.1)

    async def _run_callbacks(self):
        """Run all shutdown callbacks in priority order"""
        # Sort by priority (highest first)
        sorted_callbacks = sorted(
            self._callbacks,
            key=lambda c: c.priority,
            reverse=True
        )

        logger.info(f"Running {len(sorted_callbacks)} shutdown callbacks")

        for callback in sorted_callbacks:
            result = await self._run_callback(callback)
            self._results.append(result)

            if not result.success and not callback.critical:
                logger.error(f"Critical callback failed: {callback.name}")

    async def _run_callback(self, callback: ShutdownCallback) -> ShutdownResult:
        """Run a single callback with timeout"""
        start = time.time()

        try:
            await asyncio.wait_for(
                callback.callback(),
                timeout=callback.timeout
            )

            duration = (time.time() - start) * 1000
            logger.info(f"Callback '{callback.name}' completed in {duration:.1f}ms")

            return ShutdownResult(
                name=callback.name,
                success=True,
                duration_ms=duration,
            )

        except asyncio.TimeoutError:
            duration = (time.time() - start) * 1000
            logger.error(f"Callback '{callback.name}' timed out after {callback.timeout}s")

            return ShutdownResult(
                name=callback.name,
                success=False,
                duration_ms=duration,
                error=f"Timeout after {callback.timeout}s",
            )

        except Exception as e:
            duration = (time.time() - start) * 1000
            logger.error(f"Callback '{callback.name}' failed: {e}")

            return ShutdownResult(
                name=callback.name,
                success=False,
                duration_ms=duration,
                error=str(e),
            )

    # =========================================================================
    # REQUEST TRACKING
    # =========================================================================

    def request_started(self):
        """Track a new in-flight request"""
        self._in_flight += 1

    def request_completed(self):
        """Track request completion"""
        self._in_flight = max(0, self._in_flight - 1)

        # Signal if draining and all requests done
        if self._phase == ShutdownPhase.DRAINING and self._in_flight == 0:
            self._draining_complete.set()

    def is_shutting_down(self) -> bool:
        """Check if shutdown is in progress"""
        return self._phase != ShutdownPhase.RUNNING

    def is_accepting_requests(self) -> bool:
        """Check if new requests should be accepted"""
        return self._phase == ShutdownPhase.RUNNING

    # =========================================================================
    # STATUS
    # =========================================================================

    def get_status(self) -> ShutdownStatus:
        """Get current shutdown status"""
        return ShutdownStatus(
            phase=self._phase,
            started_at=self._started_at,
            completed_at=self._completed_at,
            in_flight_requests=self._in_flight,
            completed_callbacks=[r.name for r in self._results if r.success],
            failed_callbacks=[r.name for r in self._results if not r.success],
            timeout_seconds=self.timeout,
            reason=self._reason,
        )

    async def wait_for_shutdown(self):
        """Wait for shutdown to complete"""
        await self._shutdown_event.wait()


# =============================================================================
# SINGLETON
# =============================================================================

_manager: Optional[ShutdownManager] = None


def get_shutdown_manager() -> ShutdownManager:
    """Get or create the shutdown manager singleton"""
    global _manager
    if _manager is None:
        _manager = ShutdownManager()
    return _manager


# =============================================================================
# MIDDLEWARE
# =============================================================================

class ShutdownMiddleware:
    """
    ASGI middleware for graceful shutdown support.

    - Tracks in-flight requests
    - Returns 503 when shutting down
    """

    def __init__(self, app):
        self.app = app
        self.manager = get_shutdown_manager()

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # Check if accepting requests
        if not self.manager.is_accepting_requests():
            # Return 503 Service Unavailable
            await send({
                "type": "http.response.start",
                "status": 503,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"connection", b"close"),
                ],
            })
            await send({
                "type": "http.response.body",
                "body": b'{"error": "Service shutting down"}',
            })
            return

        # Track request
        self.manager.request_started()

        try:
            await self.app(scope, receive, send)
        finally:
            self.manager.request_completed()


# =============================================================================
# CONTEXT MANAGER
# =============================================================================

class LifecycleContext:
    """
    Context manager for graceful lifecycle management.

    Usage:
        async with LifecycleContext() as lifecycle:
            # Setup
            lifecycle.register("db", close_db)
            lifecycle.register("cache", close_cache)

            # Run application
            await run_app()

        # Cleanup runs automatically
    """

    def __init__(self, timeout: float = 30.0):
        self.manager = ShutdownManager(timeout=timeout)

    async def __aenter__(self):
        self.manager.setup_signal_handlers()
        return self.manager

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.manager._phase == ShutdownPhase.RUNNING:
            await self.manager.shutdown("context_exit")
        return False
