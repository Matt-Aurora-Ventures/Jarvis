"""
Graceful shutdown manager for services.

Provides coordinated shutdown handling for:
- Database connections
- Async tasks and background jobs
- External API clients
- File handles and state persistence
- Signal handling (SIGTERM, SIGINT)
"""

import asyncio
import logging
import signal
import sys
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Callable, Awaitable, Optional, List, Dict, Any

logger = logging.getLogger(__name__)


class ShutdownPhase(Enum):
    """Shutdown phase for prioritized cleanup."""
    IMMEDIATE = 1  # Stop accepting new work
    GRACEFUL = 2   # Complete in-flight work
    PERSIST = 3    # Save state
    CLEANUP = 4    # Close connections
    FINAL = 5      # Last-resort cleanup


@dataclass
class ShutdownHook:
    """A registered shutdown hook."""
    name: str
    callback: Callable[[], Awaitable[None]]
    phase: ShutdownPhase
    timeout: float = 5.0
    priority: int = 0  # Higher = runs first within phase


class ShutdownManager:
    """
    Manages graceful shutdown of services.

    Usage:
        manager = ShutdownManager()
        manager.register_hook("db", close_db, ShutdownPhase.CLEANUP)
        manager.install_signal_handlers()

        # Later, when shutting down
        await manager.shutdown()
    """

    def __init__(self, shutdown_timeout: float = 30.0):
        self.shutdown_timeout = shutdown_timeout
        self.hooks: List[ShutdownHook] = []
        self._shutdown_event = asyncio.Event()
        self._is_shutting_down = False
        self._shutdown_complete = False
        self._signal_handlers_installed = False

    def register_hook(
        self,
        name: str,
        callback: Callable[[], Awaitable[None]],
        phase: ShutdownPhase = ShutdownPhase.GRACEFUL,
        timeout: float = 5.0,
        priority: int = 0,
    ):
        """
        Register a shutdown hook.

        Args:
            name: Descriptive name for logging
            callback: Async function to call during shutdown
            phase: When to run this hook
            timeout: Max seconds to wait for this hook
            priority: Higher priority runs first (within phase)
        """
        hook = ShutdownHook(
            name=name,
            callback=callback,
            phase=phase,
            timeout=timeout,
            priority=priority,
        )
        self.hooks.append(hook)
        logger.debug(f"Registered shutdown hook: {name} (phase={phase.name}, priority={priority})")

    def install_signal_handlers(self):
        """Install signal handlers for graceful shutdown."""
        if self._signal_handlers_installed:
            logger.warning("Signal handlers already installed")
            return

        def signal_handler(sig, frame):
            sig_name = signal.Signals(sig).name
            logger.info(f"Received {sig_name}, initiating graceful shutdown...")
            self._shutdown_event.set()

        # SIGTERM - systemd sends this
        signal.signal(signal.SIGTERM, signal_handler)

        # SIGINT - Ctrl+C
        signal.signal(signal.SIGINT, signal_handler)

        # Windows doesn't have SIGQUIT
        if hasattr(signal, 'SIGQUIT'):
            signal.signal(signal.SIGQUIT, signal_handler)

        self._signal_handlers_installed = True
        logger.info("Signal handlers installed (SIGTERM, SIGINT)")

    async def wait_for_shutdown(self):
        """Wait for shutdown signal."""
        await self._shutdown_event.wait()

    def is_shutting_down(self) -> bool:
        """Check if shutdown has been initiated."""
        return self._is_shutting_down

    async def shutdown(self):
        """
        Execute graceful shutdown sequence.

        Runs all registered hooks in phase order, respecting timeouts.
        """
        if self._is_shutting_down:
            logger.warning("Shutdown already in progress")
            return

        self._is_shutting_down = True
        start_time = datetime.now()

        logger.info("=" * 60)
        logger.info("GRACEFUL SHUTDOWN INITIATED")
        logger.info("=" * 60)

        # Sort hooks by phase, then by priority (descending)
        sorted_hooks = sorted(
            self.hooks,
            key=lambda h: (h.phase.value, -h.priority)
        )

        # Group by phase
        by_phase: Dict[ShutdownPhase, List[ShutdownHook]] = {}
        for hook in sorted_hooks:
            if hook.phase not in by_phase:
                by_phase[hook.phase] = []
            by_phase[hook.phase].append(hook)

        # Execute each phase
        for phase in ShutdownPhase:
            if phase not in by_phase:
                continue

            phase_hooks = by_phase[phase]
            logger.info(f"[Shutdown Phase: {phase.name}] Running {len(phase_hooks)} hooks...")

            for hook in phase_hooks:
                try:
                    logger.info(f"  [{hook.name}] Starting...")
                    await asyncio.wait_for(
                        hook.callback(),
                        timeout=hook.timeout
                    )
                    logger.info(f"  [{hook.name}] Complete")
                except asyncio.TimeoutError:
                    logger.error(f"  [{hook.name}] Timeout after {hook.timeout}s")
                except Exception as e:
                    logger.error(f"  [{hook.name}] Failed: {e}", exc_info=True)

        self._shutdown_complete = True
        elapsed = (datetime.now() - start_time).total_seconds()

        logger.info("=" * 60)
        logger.info(f"SHUTDOWN COMPLETE ({elapsed:.1f}s)")
        logger.info("=" * 60)


# Global singleton
_manager: Optional[ShutdownManager] = None


def get_shutdown_manager() -> ShutdownManager:
    """Get or create the global shutdown manager."""
    global _manager
    if _manager is None:
        _manager = ShutdownManager()
    return _manager


@asynccontextmanager
async def managed_shutdown():
    """
    Context manager for automatic shutdown handling.

    Usage:
        async with managed_shutdown():
            # Your app code
            await run_server()
    """
    manager = get_shutdown_manager()
    manager.install_signal_handlers()

    try:
        yield manager
    finally:
        await manager.shutdown()


class ShutdownAwareService:
    """
    Base class for services that need graceful shutdown.

    Subclasses should implement:
    - _startup() - Initialize resources
    - _shutdown() - Clean up resources
    """

    def __init__(self, name: str):
        self.name = name
        self._running = False
        self._shutdown_manager = get_shutdown_manager()

    async def start(self):
        """Start the service and register shutdown hook."""
        if self._running:
            raise RuntimeError(f"{self.name} already running")

        logger.info(f"[{self.name}] Starting...")
        await self._startup()
        self._running = True

        # Register shutdown hook
        self._shutdown_manager.register_hook(
            name=self.name,
            callback=self._shutdown_hook,
            phase=ShutdownPhase.GRACEFUL,
        )

        logger.info(f"[{self.name}] Started")

    async def _startup(self):
        """Override this to initialize resources."""
        pass

    async def _shutdown(self):
        """Override this to clean up resources."""
        pass

    async def _shutdown_hook(self):
        """Internal shutdown hook."""
        if not self._running:
            return

        logger.info(f"[{self.name}] Shutting down...")
        try:
            await self._shutdown()
            self._running = False
            logger.info(f"[{self.name}] Shutdown complete")
        except Exception as e:
            logger.error(f"[{self.name}] Shutdown error: {e}", exc_info=True)
            raise


class DatabaseShutdownMixin:
    """Mixin for services with database connections."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._db_connections: List[Any] = []

    def register_db_connection(self, conn: Any):
        """Register a database connection for cleanup."""
        self._db_connections.append(conn)

    async def _close_db_connections(self):
        """Close all registered database connections."""
        logger.info(f"Closing {len(self._db_connections)} database connection(s)...")

        for i, conn in enumerate(self._db_connections):
            try:
                if hasattr(conn, 'close'):
                    if asyncio.iscoroutinefunction(conn.close):
                        await conn.close()
                    else:
                        conn.close()
                elif hasattr(conn, 'aclose'):
                    await conn.aclose()
                logger.debug(f"  Closed connection {i+1}/{len(self._db_connections)}")
            except Exception as e:
                logger.error(f"  Failed to close connection {i+1}: {e}")

        self._db_connections.clear()


class TaskManagerMixin:
    """Mixin for services with background tasks."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._background_tasks: List[asyncio.Task] = []

    def create_task(self, coro, name: Optional[str] = None) -> asyncio.Task:
        """Create and track a background task."""
        task = asyncio.create_task(coro, name=name)
        self._background_tasks.append(task)
        return task

    async def _cancel_background_tasks(self, timeout: float = 5.0):
        """Cancel all background tasks."""
        if not self._background_tasks:
            return

        logger.info(f"Cancelling {len(self._background_tasks)} background task(s)...")

        # Cancel all tasks
        for task in self._background_tasks:
            if not task.done():
                task.cancel()

        # Wait for them to finish
        try:
            await asyncio.wait_for(
                asyncio.gather(*self._background_tasks, return_exceptions=True),
                timeout=timeout
            )
            logger.debug(f"  All tasks cancelled")
        except asyncio.TimeoutError:
            logger.warning(f"  Some tasks did not cancel within {timeout}s")

        self._background_tasks.clear()
