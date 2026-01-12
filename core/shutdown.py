"""
Graceful Shutdown Handler - Clean shutdown with resource cleanup.
"""

import asyncio
import signal
import logging
import sys
from typing import Callable, List, Optional, Any, Coroutine
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum, auto

logger = logging.getLogger(__name__)


class ShutdownPhase(Enum):
    """Phases of shutdown process."""
    RUNNING = auto()
    GRACEFUL_SHUTDOWN = auto()
    FORCE_SHUTDOWN = auto()
    TERMINATED = auto()


@dataclass
class ShutdownHandler:
    """A registered shutdown handler."""
    name: str
    callback: Callable
    priority: int = 50  # 0-100, lower = earlier
    timeout: float = 10.0  # seconds
    critical: bool = False  # If True, failure stops shutdown


@dataclass
class ShutdownState:
    """Current shutdown state."""
    phase: ShutdownPhase = ShutdownPhase.RUNNING
    started_at: Optional[datetime] = None
    reason: str = ""
    handlers_completed: List[str] = field(default_factory=list)
    handlers_failed: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)


class GracefulShutdown:
    """
    Manages graceful shutdown with cleanup handlers.

    Usage:
        shutdown = GracefulShutdown()

        # Register cleanup handlers
        shutdown.register("database", db.close, priority=90)
        shutdown.register("websockets", ws_manager.disconnect_all, priority=80)
        shutdown.register("telegram", tg_bot.stop, priority=70)

        # Install signal handlers
        shutdown.install_signal_handlers()

        # Or trigger manually
        await shutdown.initiate("Manual shutdown requested")
    """

    def __init__(
        self,
        graceful_timeout: float = 30.0,
        force_timeout: float = 10.0
    ):
        self.graceful_timeout = graceful_timeout
        self.force_timeout = force_timeout
        self._handlers: List[ShutdownHandler] = []
        self._state = ShutdownState()
        self._shutdown_event = asyncio.Event()
        self._lock = asyncio.Lock()

    @property
    def is_shutting_down(self) -> bool:
        """Check if shutdown is in progress."""
        return self._state.phase != ShutdownPhase.RUNNING

    @property
    def state(self) -> ShutdownState:
        """Get current shutdown state."""
        return self._state

    def register(
        self,
        name: str,
        callback: Callable,
        priority: int = 50,
        timeout: float = 10.0,
        critical: bool = False
    ):
        """
        Register a shutdown handler.

        Args:
            name: Handler name for logging
            callback: Async or sync callable to run
            priority: 0-100, lower runs first
            timeout: Max time to wait for handler
            critical: If True, failure raises exception
        """
        handler = ShutdownHandler(
            name=name,
            callback=callback,
            priority=priority,
            timeout=timeout,
            critical=critical
        )
        self._handlers.append(handler)
        self._handlers.sort(key=lambda h: h.priority)
        logger.debug(f"Registered shutdown handler: {name} (priority={priority})")

    def unregister(self, name: str):
        """Unregister a handler by name."""
        self._handlers = [h for h in self._handlers if h.name != name]

    def install_signal_handlers(self, loop: asyncio.AbstractEventLoop = None):
        """Install OS signal handlers for graceful shutdown."""
        if sys.platform == 'win32':
            # Windows doesn't support SIGTERM the same way
            signal.signal(signal.SIGINT, self._signal_handler)
            signal.signal(signal.SIGBREAK, self._signal_handler)
        else:
            loop = loop or asyncio.get_event_loop()
            for sig in (signal.SIGTERM, signal.SIGINT):
                loop.add_signal_handler(
                    sig,
                    lambda s=sig: asyncio.create_task(
                        self.initiate(f"Received signal {s.name}")
                    )
                )

        logger.info("Signal handlers installed for graceful shutdown")

    def _signal_handler(self, signum, frame):
        """Signal handler for Windows."""
        sig_name = signal.Signals(signum).name
        logger.info(f"Received signal: {sig_name}")

        # Schedule shutdown in the event loop
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self.initiate(f"Received signal {sig_name}"))
        except RuntimeError:
            # No running loop, force exit
            logger.warning("No running event loop, forcing exit")
            sys.exit(0)

    async def initiate(self, reason: str = "Shutdown requested"):
        """
        Initiate graceful shutdown.

        Args:
            reason: Reason for shutdown (for logging)
        """
        async with self._lock:
            if self.is_shutting_down:
                logger.warning("Shutdown already in progress")
                return

            self._state.phase = ShutdownPhase.GRACEFUL_SHUTDOWN
            self._state.started_at = datetime.now(timezone.utc)
            self._state.reason = reason

        logger.info(f"Initiating graceful shutdown: {reason}")

        try:
            await asyncio.wait_for(
                self._run_handlers(),
                timeout=self.graceful_timeout
            )
        except asyncio.TimeoutError:
            logger.warning(
                f"Graceful shutdown timed out after {self.graceful_timeout}s, "
                f"forcing shutdown"
            )
            await self._force_shutdown()

        self._state.phase = ShutdownPhase.TERMINATED
        self._shutdown_event.set()

        logger.info(
            f"Shutdown complete. "
            f"Completed: {len(self._state.handlers_completed)}, "
            f"Failed: {len(self._state.handlers_failed)}"
        )

    async def _run_handlers(self):
        """Run all shutdown handlers in priority order."""
        for handler in self._handlers:
            if self._state.phase == ShutdownPhase.FORCE_SHUTDOWN:
                break

            try:
                logger.info(f"Running shutdown handler: {handler.name}")

                result = handler.callback()
                if asyncio.iscoroutine(result):
                    await asyncio.wait_for(result, timeout=handler.timeout)

                self._state.handlers_completed.append(handler.name)
                logger.info(f"Shutdown handler completed: {handler.name}")

            except asyncio.TimeoutError:
                msg = f"Handler {handler.name} timed out after {handler.timeout}s"
                logger.error(msg)
                self._state.handlers_failed.append(handler.name)
                self._state.errors.append(msg)

                if handler.critical:
                    raise

            except Exception as e:
                msg = f"Handler {handler.name} failed: {e}"
                logger.error(msg)
                self._state.handlers_failed.append(handler.name)
                self._state.errors.append(msg)

                if handler.critical:
                    raise

    async def _force_shutdown(self):
        """Force shutdown - cancel remaining handlers."""
        self._state.phase = ShutdownPhase.FORCE_SHUTDOWN
        logger.warning("Force shutdown initiated")

        # Give a brief moment for cleanup
        await asyncio.sleep(0.5)

    async def wait_for_shutdown(self):
        """Wait until shutdown is complete."""
        await self._shutdown_event.wait()

    def get_status(self) -> dict:
        """Get current shutdown status."""
        return {
            'phase': self._state.phase.name,
            'reason': self._state.reason,
            'started_at': self._state.started_at.isoformat() if self._state.started_at else None,
            'handlers_completed': self._state.handlers_completed,
            'handlers_failed': self._state.handlers_failed,
            'errors': self._state.errors
        }


class ApplicationLifecycle:
    """
    Complete application lifecycle management.

    Usage:
        lifecycle = ApplicationLifecycle()

        @lifecycle.on_startup
        async def init_database():
            await db.connect()

        @lifecycle.on_shutdown
        async def close_database():
            await db.disconnect()

        # Run the application
        await lifecycle.run(main_coroutine())
    """

    def __init__(self):
        self.shutdown = GracefulShutdown()
        self._startup_handlers: List[Callable] = []
        self._running = False

    def on_startup(self, func: Callable = None, *, priority: int = 50):
        """Decorator to register startup handler."""
        def decorator(f):
            self._startup_handlers.append((f, priority))
            self._startup_handlers.sort(key=lambda x: x[1])
            return f

        if func is not None:
            return decorator(func)
        return decorator

    def on_shutdown(
        self,
        func: Callable = None,
        *,
        priority: int = 50,
        timeout: float = 10.0,
        critical: bool = False
    ):
        """Decorator to register shutdown handler."""
        def decorator(f):
            self.shutdown.register(
                name=f.__name__,
                callback=f,
                priority=priority,
                timeout=timeout,
                critical=critical
            )
            return f

        if func is not None:
            return decorator(func)
        return decorator

    async def startup(self):
        """Run all startup handlers."""
        logger.info("Running startup handlers...")

        for handler, priority in self._startup_handlers:
            try:
                logger.debug(f"Running startup: {handler.__name__}")
                result = handler()
                if asyncio.iscoroutine(result):
                    await result
            except Exception as e:
                logger.error(f"Startup handler {handler.__name__} failed: {e}")
                raise

        logger.info("Startup complete")
        self._running = True

    async def run(self, main_coro: Coroutine):
        """
        Run application with lifecycle management.

        Args:
            main_coro: Main application coroutine
        """
        self.shutdown.install_signal_handlers()

        try:
            await self.startup()
            await main_coro
        except KeyboardInterrupt:
            logger.info("Keyboard interrupt received")
        except Exception as e:
            logger.error(f"Application error: {e}")
        finally:
            if not self.shutdown.is_shutting_down:
                await self.shutdown.initiate("Application stopped")


# === CLEANUP UTILITIES ===

async def cleanup_async_generators():
    """Cleanup any lingering async generators."""
    try:
        loop = asyncio.get_running_loop()
        await loop.shutdown_asyncgens()
    except Exception as e:
        logger.warning(f"Error cleaning up async generators: {e}")


async def cancel_all_tasks():
    """Cancel all running tasks except current."""
    tasks = [
        t for t in asyncio.all_tasks()
        if t is not asyncio.current_task()
    ]

    if not tasks:
        return

    logger.info(f"Cancelling {len(tasks)} tasks...")

    for task in tasks:
        task.cancel()

    await asyncio.gather(*tasks, return_exceptions=True)


# === SINGLETON ===

_lifecycle: Optional[ApplicationLifecycle] = None

def get_lifecycle() -> ApplicationLifecycle:
    """Get singleton lifecycle manager."""
    global _lifecycle
    if _lifecycle is None:
        _lifecycle = ApplicationLifecycle()
    return _lifecycle


def get_shutdown_handler() -> GracefulShutdown:
    """Get shutdown handler from lifecycle."""
    return get_lifecycle().shutdown
