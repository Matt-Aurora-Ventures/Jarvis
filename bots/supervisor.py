#!/usr/bin/env python3
"""
JARVIS Bot Supervisor - Robust process management with auto-restart.

This supervisor ensures all bot components keep running without supervision.
Features:
- Auto-restart on crash with exponential backoff
- Health monitoring
- Graceful shutdown
- Component isolation (one crash doesn't kill others)
- Detailed logging
- Anti-scam integration
"""

import asyncio
import logging
import os
import sys
import signal
import socket
import time
import tempfile
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass, field
from enum import Enum


# =============================================================================
# Single Instance Enforcement (Bug Fix US-033)
# =============================================================================

class SingleInstanceLock:
    """
    Cross-platform single instance enforcement using file locking.

    On Windows: Uses temp file with exclusive access
    On Unix: Uses fcntl.flock
    """

    def __init__(self, name: str):
        self.name = name
        self.lock_file = Path(tempfile.gettempdir()) / f"{name}.lock"
        self._lock_fd = None
        self._is_windows = sys.platform == "win32"

    def acquire(self) -> bool:
        """
        Acquire the single instance lock.

        Returns:
            True if lock acquired, False if another instance is running.

        Raises:
            RuntimeError: If another instance is already running.
        """
        try:
            if self._is_windows:
                # Windows: Use exclusive file creation
                import msvcrt
                self._lock_fd = open(self.lock_file, 'w')
                msvcrt.locking(self._lock_fd.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                # Unix: Use fcntl
                import fcntl
                self._lock_fd = open(self.lock_file, 'w')
                fcntl.flock(self._lock_fd.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)

            # Write PID to lock file for debugging
            self._lock_fd.write(str(os.getpid()))
            self._lock_fd.flush()
            return True

        except (IOError, OSError) as e:
            if self._lock_fd:
                self._lock_fd.close()
                self._lock_fd = None
            raise RuntimeError(
                f"Another instance of {self.name} is already running. "
                f"Lock file: {self.lock_file}"
            ) from e

    def release(self):
        """Release the lock and clean up."""
        if self._lock_fd:
            try:
                if self._is_windows:
                    import msvcrt
                    msvcrt.locking(self._lock_fd.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(self._lock_fd.fileno(), fcntl.LOCK_UN)
                self._lock_fd.close()
            except Exception:
                pass
            finally:
                self._lock_fd = None
                try:
                    self.lock_file.unlink()
                except Exception:
                    pass

    def __enter__(self):
        self.acquire()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.release()
        return False


def ensure_single_instance(name: str) -> SingleInstanceLock:
    """
    Ensure only one instance of a named process is running.

    Args:
        name: Unique name for the process (e.g., "telegram_demo_bot")

    Returns:
        SingleInstanceLock that must be kept alive while the process runs.

    Raises:
        RuntimeError: If another instance is already running.

    Usage:
        lock = ensure_single_instance("telegram_demo_bot")
        try:
            # ... run your bot ...
        finally:
            lock.release()
    """
    lock = SingleInstanceLock(name)
    lock.acquire()
    return lock

# Import safe task tracking
try:
    from core.async_utils import fire_and_forget, TaskTracker
    TASK_TRACKING_AVAILABLE = True
except ImportError:
    TASK_TRACKING_AVAILABLE = False
    fire_and_forget = None
    TaskTracker = None

# Import shutdown manager
try:
    from core.shutdown_manager import get_shutdown_manager, ShutdownPhase
    SHUTDOWN_MANAGER_AVAILABLE = True
except ImportError:
    SHUTDOWN_MANAGER_AVAILABLE = False
    get_shutdown_manager = None
    ShutdownPhase = None

# Import error tracker for centralized error logging
try:
    from core.logging.error_tracker import error_tracker
    ERROR_TRACKER_AVAILABLE = True
except ImportError:
    error_tracker = None
    ERROR_TRACKER_AVAILABLE = False

# Import self-correcting AI system
try:
    from core.self_correcting import (
        get_shared_memory,
        get_message_bus,
        get_ollama_router,
        get_self_adjuster,
    )
    SELF_CORRECTING_AVAILABLE = True
except ImportError:
    get_shared_memory = None
    get_message_bus = None
    get_ollama_router = None
    get_self_adjuster = None
    SELF_CORRECTING_AVAILABLE = False


def systemd_notify(state: str) -> bool:
    """
    Send notification to systemd watchdog.

    States:
        READY=1 - Service is ready
        WATCHDOG=1 - Ping the watchdog
        STOPPING=1 - Service is stopping

    Returns True if notification was sent, False otherwise.
    """
    notify_socket = os.environ.get("NOTIFY_SOCKET")
    if not notify_socket:
        return False  # Not running under systemd

    try:
        # Handle abstract sockets (start with @)
        if notify_socket.startswith("@"):
            notify_socket = "\0" + notify_socket[1:]

        sock = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
        sock.connect(notify_socket)
        sock.sendall(state.encode())
        sock.close()
        return True
    except Exception:
        return False

# Fix Windows encoding
if sys.platform == "win32":
    for stream in [sys.stdout, sys.stderr]:
        if hasattr(stream, 'reconfigure'):
            stream.reconfigure(encoding='utf-8', errors='replace')

# Add project root to path
project_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(project_root))

logger = logging.getLogger("jarvis.supervisor")


def track_supervisor_error(exc: Exception, component: str, context: str = "") -> None:
    """Track an error in the supervisor using the centralized error tracker."""
    if ERROR_TRACKER_AVAILABLE and error_tracker:
        error_tracker.track_error(
            exc,
            context=context or f"supervisor.{component}",
            component="supervisor",
            metadata={"component_name": component}
        )


class ComponentStatus(Enum):
    """Component status states."""
    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    FAILED = "failed"
    RESTARTING = "restarting"


@dataclass
class ComponentState:
    """Track state of a supervised component."""
    name: str
    status: ComponentStatus = ComponentStatus.STOPPED
    task: Optional[asyncio.Task] = None
    start_time: Optional[datetime] = None
    restart_count: int = 0
    last_error: Optional[str] = None
    last_error_time: Optional[datetime] = None
    consecutive_failures: int = 0
    # Backoff settings
    min_backoff: float = 1.0
    max_backoff: float = 300.0  # 5 minutes max
    current_backoff: float = 1.0


class BotSupervisor:
    """
    Supervisor that keeps bot components running.

    Usage:
        supervisor = BotSupervisor()
        supervisor.register("buy_bot", buy_bot.start)
        supervisor.register("sentiment", sentiment.start)
        await supervisor.run_forever()
    """

    def __init__(
        self,
        max_restarts: int = 100,  # Max restarts before giving up
        health_check_interval: int = 60,  # Seconds between health checks
        reset_failure_after: int = 300,  # Reset failure count after 5 min of success
    ):
        self.max_restarts = max_restarts
        self.health_check_interval = health_check_interval
        self.reset_failure_after = reset_failure_after

        self.components: Dict[str, ComponentState] = {}
        self.component_funcs: Dict[str, Callable] = {}
        self._running = False
        self._shutdown_event = asyncio.Event()

        # Register with shutdown manager
        if SHUTDOWN_MANAGER_AVAILABLE:
            self._shutdown_manager = get_shutdown_manager()
            self._shutdown_manager.register_hook(
                name="supervisor",
                callback=self._graceful_shutdown,
                phase=ShutdownPhase.IMMEDIATE,
                timeout=30.0,
                priority=100,  # High priority - stop supervisor first
            )

    def register(
        self,
        name: str,
        start_func: Callable,
        min_backoff: float = 1.0,
        max_backoff: float = 300.0,
    ):
        """Register a component to be supervised."""
        self.components[name] = ComponentState(
            name=name,
            min_backoff=min_backoff,
            max_backoff=max_backoff,
            current_backoff=min_backoff,
        )
        self.component_funcs[name] = start_func
        logger.info(f"Registered component: {name}")

    async def _run_component(self, name: str):
        """Run a single component with error handling."""
        state = self.components[name]
        func = self.component_funcs[name]

        while self._running and state.restart_count < self.max_restarts:
            try:
                state.status = ComponentStatus.STARTING
                state.start_time = datetime.now()
                logger.info(f"[{name}] Starting component...")

                state.status = ComponentStatus.RUNNING

                # Run the component
                if asyncio.iscoroutinefunction(func):
                    await func()
                else:
                    func()

                # If we get here, the component exited cleanly
                logger.info(f"[{name}] Component exited cleanly")
                break

            except asyncio.CancelledError:
                logger.info(f"[{name}] Component cancelled")
                state.status = ComponentStatus.STOPPED
                raise

            except Exception as e:
                state.consecutive_failures += 1
                state.restart_count += 1
                state.last_error = str(e)
                state.last_error_time = datetime.now()
                state.status = ComponentStatus.FAILED

                logger.error(
                    f"[{name}] Component crashed (attempt {state.restart_count}/{self.max_restarts}): {e}",
                    exc_info=True
                )

                # Alert on repeated failures (every 5 failures)
                if state.consecutive_failures % 5 == 0:
                    if TASK_TRACKING_AVAILABLE:
                        fire_and_forget(
                            self._send_error_alert(name, str(e), state.consecutive_failures, state.restart_count),
                            name=f"error_alert_{name}"
                        )
                    else:
                        asyncio.create_task(self._send_error_alert(
                            name, str(e), state.consecutive_failures, state.restart_count
                        ))

                if state.restart_count >= self.max_restarts:
                    logger.error(f"[{name}] Max restarts reached, giving up")
                    # Send critical alert
                    if TASK_TRACKING_AVAILABLE:
                        fire_and_forget(
                            self._send_critical_alert(name, str(e)),
                            name=f"critical_alert_{name}"
                        )
                    else:
                        asyncio.create_task(self._send_critical_alert(name, str(e)))
                    break

                # Exponential backoff
                wait_time = state.current_backoff
                state.current_backoff = min(state.current_backoff * 2, state.max_backoff)

                logger.info(f"[{name}] Restarting in {wait_time:.1f}s...")
                state.status = ComponentStatus.RESTARTING

                try:
                    await asyncio.sleep(wait_time)
                except asyncio.CancelledError:
                    break

        state.status = ComponentStatus.STOPPED

    async def _health_monitor(self):
        """Monitor component health and log status."""
        while self._running:
            try:
                await asyncio.sleep(self.health_check_interval)

                now = datetime.now()
                status_lines = ["=== COMPONENT HEALTH ==="]

                for name, state in self.components.items():
                    uptime = ""
                    if state.start_time and state.status == ComponentStatus.RUNNING:
                        delta = now - state.start_time
                        uptime = f" (uptime: {delta})"

                        # Reset failure count after successful run
                        if delta.total_seconds() > self.reset_failure_after:
                            if state.consecutive_failures > 0:
                                logger.info(f"[{name}] Resetting failure count after stable run")
                                state.consecutive_failures = 0
                                state.current_backoff = state.min_backoff

                    status_lines.append(
                        f"  {name}: {state.status.value}{uptime} "
                        f"(restarts: {state.restart_count})"
                    )

                logger.info("\n".join(status_lines))

                # Ping systemd watchdog (if running under systemd)
                systemd_notify("WATCHDOG=1")

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Health monitor error: {e}")

    async def run_forever(self):
        """Run all components forever with supervision."""
        self._running = True

        logger.info("=" * 60)
        logger.info("JARVIS BOT SUPERVISOR STARTING")
        logger.info(f"Components: {list(self.components.keys())}")
        logger.info("=" * 60)

        # Notify systemd that we're ready
        if systemd_notify("READY=1"):
            logger.info("Notified systemd: READY")

        # Create tasks for each component
        tasks = []
        for name in self.components:
            task = asyncio.create_task(self._run_component(name))
            self.components[name].task = task
            tasks.append(task)

        # Add health monitor
        health_task = asyncio.create_task(self._health_monitor())
        tasks.append(health_task)

        # Wait for shutdown signal or all tasks to complete
        try:
            await asyncio.gather(*tasks, return_exceptions=True)
        except asyncio.CancelledError:
            pass
        finally:
            self._running = False
            await self._cleanup()

    async def _graceful_shutdown(self):
        """Graceful shutdown hook for shutdown manager."""
        logger.info("Supervisor graceful shutdown initiated...")
        self._running = False

        # Signal all components to stop
        for name, state in self.components.items():
            logger.info(f"  [{name}] Requesting shutdown...")
            if state.task and not state.task.done():
                state.task.cancel()

        # Wait for components to finish (with timeout per component)
        for name, state in self.components.items():
            if state.task and not state.task.done():
                try:
                    await asyncio.wait_for(state.task, timeout=5.0)
                    logger.info(f"  [{name}] Stopped cleanly")
                except asyncio.TimeoutError:
                    logger.warning(f"  [{name}] Shutdown timeout (5s)")
                except asyncio.CancelledError:
                    logger.info(f"  [{name}] Cancelled")
                except Exception as e:
                    logger.error(f"  [{name}] Shutdown error: {e}")

    async def _cleanup(self):
        """Clean up all components."""
        logger.info("Supervisor shutting down...")
        systemd_notify("STOPPING=1")

        # If shutdown manager is available, it handles cleanup
        if SHUTDOWN_MANAGER_AVAILABLE:
            # Already handled by _graceful_shutdown
            pass
        else:
            # Fallback to old cleanup logic
            for name, state in self.components.items():
                if state.task and not state.task.done():
                    state.task.cancel()
                    try:
                        await asyncio.wait_for(state.task, timeout=5.0)
                    except (asyncio.CancelledError, asyncio.TimeoutError):
                        pass

        logger.info("Supervisor shutdown complete")

    def get_status(self) -> Dict[str, Any]:
        """Get current status of all components."""
        return {
            name: {
                "status": state.status.value,
                "restart_count": state.restart_count,
                "last_error": state.last_error,
                "uptime": str(datetime.now() - state.start_time) if state.start_time else None,
            }
            for name, state in self.components.items()
        }

    async def _send_error_alert(
        self, component: str, error: str, consecutive: int, total: int
    ):
        """Send error alert to Telegram admins."""
        try:
            import aiohttp
            token = os.environ.get("TELEGRAM_BOT_TOKEN")
            admin_ids = os.environ.get("TELEGRAM_ADMIN_IDS", "")

            if not token or not admin_ids:
                return

            admin_list = [x.strip() for x in admin_ids.split(",") if x.strip().isdigit()]
            if not admin_list:
                return

            message = (
                f"⚠️ <b>Component Error Alert</b>\n\n"
                f"<b>Component:</b> {component}\n"
                f"<b>Consecutive failures:</b> {consecutive}\n"
                f"<b>Total restarts:</b> {total}\n"
                f"<b>Error:</b> <code>{error[:200]}</code>"
            )

            async with aiohttp.ClientSession() as session:
                for admin_id in admin_list[:3]:  # Limit to first 3 admins
                    url = f"https://api.telegram.org/bot{token}/sendMessage"
                    await session.post(url, json={
                        "chat_id": admin_id,
                        "text": message,
                        "parse_mode": "HTML",
                    })
        except Exception as e:
            logger.debug(f"Failed to send error alert: {e}")

    async def _send_critical_alert(self, component: str, error: str):
        """Send critical alert when component gives up."""
        try:
            import aiohttp
            token = os.environ.get("TELEGRAM_BOT_TOKEN")
            admin_ids = os.environ.get("TELEGRAM_ADMIN_IDS", "")

            if not token or not admin_ids:
                return

            admin_list = [x.strip() for x in admin_ids.split(",") if x.strip().isdigit()]
            if not admin_list:
                return

            message = (
                f"🚨 <b>CRITICAL: Component Died</b>\n\n"
                f"<b>Component:</b> {component}\n"
                f"<b>Status:</b> Max restarts reached - STOPPED\n"
                f"<b>Last error:</b> <code>{error[:200]}</code>\n\n"
                f"Manual intervention required!"
            )

            async with aiohttp.ClientSession() as session:
                for admin_id in admin_list[:3]:
                    url = f"https://api.telegram.org/bot{token}/sendMessage"
                    await session.post(url, json={
                        "chat_id": admin_id,
                        "text": message,
                        "parse_mode": "HTML",
                    })
        except Exception as e:
            logger.debug(f"Failed to send critical alert: {e}")


def load_env():
    """Load environment variables from .env files."""
    env_files = [
        project_root / "tg_bot" / ".env",
        project_root / "bots" / "twitter" / ".env",
        project_root / ".env",
    ]
    for env_path in env_files:
        if env_path.exists():
            with open(env_path) as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        key, value = line.split("=", 1)
                        os.environ.setdefault(key.strip(), value.strip())


async def create_buy_bot():
    """Create and run the buy bot."""
    from bots.buy_tracker.bot import JarvisBuyBot
    bot = JarvisBuyBot()
    await bot.start()


async def create_sentiment_reporter():
    """Create and run the sentiment reporter (1 hour interval)."""
    from bots.buy_tracker.sentiment_report import SentimentReportGenerator

    reporter = SentimentReportGenerator(
        bot_token=os.environ.get("TELEGRAM_BOT_TOKEN", ""),
        chat_id=os.environ.get("TELEGRAM_BUY_BOT_CHAT_ID", ""),
        xai_api_key=os.environ.get("XAI_API_KEY", ""),
        interval_minutes=60,  # Changed to 1 hour as requested
    )
    await reporter.start()


async def create_twitter_poster():
    """Create and run the Twitter sentiment poster."""
    from bots.twitter.sentiment_poster import SentimentTwitterPoster
    from bots.twitter.twitter_client import TwitterClient, TwitterCredentials
    from bots.twitter.claude_content import ClaudeContentGenerator

    # Use TwitterCredentials.from_env() which correctly prefers JARVIS_ACCESS_TOKEN
    # for posting as @Jarvis_lifeos instead of @aurora_ventures
    twitter_client = TwitterClient()  # Uses from_env() internally
    try:
        from core.llm.anthropic_utils import get_anthropic_api_key
        claude_key = get_anthropic_api_key()
    except Exception:
        claude_key = os.environ.get("ANTHROPIC_API_KEY")
    claude_client = ClaudeContentGenerator(api_key=claude_key)

    poster = SentimentTwitterPoster(
        twitter_client=twitter_client,
        claude_client=claude_client,
        interval_minutes=60,  # Changed to 1 hour
    )
    await poster.start()


async def create_telegram_bot():
    """Create and run the main Telegram bot with anti-scam.

    Lock architecture (US-033 fix):
    - Supervisor acquires and HOLDS the polling lock for the bot's entire lifetime
    - Subprocess skips its own lock acquisition (SKIP_TELEGRAM_LOCK=1)
    - This eliminates the race condition from probe-release-spawn pattern
    """
    import subprocess

    tg_token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    if not tg_token:
        logger.warning("No TELEGRAM_BOT_TOKEN set, skipping Telegram bot")
        return

    # Import enhanced locking with PID validation
    try:
        from core.utils.instance_lock import acquire_instance_lock, cleanup_stale_lock
    except Exception as exc:
        logger.warning(f"Polling lock helper unavailable: {exc}")
        acquire_instance_lock = None
        cleanup_stale_lock = None

    lock_handle = None

    if acquire_instance_lock and cleanup_stale_lock:
        # Clean up any stale locks from crashed processes FIRST
        cleanup_stale_lock(tg_token, name="telegram_polling")

        # Acquire lock at supervisor level - hold for entire bot lifetime
        # This is the KEY FIX: supervisor holds lock, not just probes it
        lock_handle = acquire_instance_lock(
            tg_token,
            name="telegram_polling",
            max_wait_seconds=30,
            validate_pid=True,
        )
        if not lock_handle:
            logger.error("Cannot acquire Telegram polling lock - another instance is running")
            return

        logger.info("Acquired Telegram polling lock at supervisor level")

    # Run as subprocess to isolate it
    env = os.environ.copy()
    env["PYTHONPATH"] = str(project_root) + os.pathsep + env.get("PYTHONPATH", "")
    # Tell subprocess to skip its own lock acquisition - supervisor holds it
    env["SKIP_TELEGRAM_LOCK"] = "1"

    # Kill any lingering telegram bot processes from previous runs
    try:
        if sys.platform == "win32":
            # taskkill /FI doesn't support CMDLINE filter on Windows
            # Use PowerShell to find and kill processes with tg_bot in command line
            kill_cmd = (
                'powershell -Command "'
                "Get-CimInstance Win32_Process -Filter \\\"Name='python.exe'\\\" | "
                "Where-Object { $_.CommandLine -like '*tg_bot*' } | "
                'ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"'
            )
            os.system(kill_cmd)
        else:
            os.system("pkill -f 'python.*tg_bot' 2>/dev/null || true")
        await asyncio.sleep(2)  # Wait for process to fully terminate
    except Exception as e:
        logger.warning(f"Failed to clean up lingering processes: {e}")

    proc = subprocess.Popen(
        [sys.executable, str(project_root / "tg_bot" / "bot.py")],
        env=env,
    )

    try:
        # Wait for process to complete (it shouldn't unless it crashes)
        while True:
            ret = proc.poll()
            if ret is not None:
                logger.error(f"Telegram bot exited with code {ret}")
                # Wait longer before allowing restart to give Telegram time to clean up
                await asyncio.sleep(15)
                raise RuntimeError(f"Telegram bot exited with code {ret}")
            await asyncio.sleep(5)
    finally:
        # Terminate subprocess if still running
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()
                logger.warning("Telegram bot process killed (timeout on terminate)")

        # Release supervisor-level lock
        if lock_handle:
            try:
                lock_handle.close()
                logger.info("Released Telegram polling lock")
            except Exception as e:
                logger.warning(f"Error releasing lock: {e}")


async def create_autonomous_x_engine():
    """Create and run the autonomous X (Twitter) posting engine."""
    from bots.twitter.autonomous_engine import get_autonomous_engine
    from bots.twitter.x_claude_cli_handler import get_x_claude_cli_handler

    # Check for required credentials
    x_api_key = os.environ.get("X_API_KEY", "") or os.environ.get("TWITTER_API_KEY", "")
    if not x_api_key:
        logger.warning("No X_API_KEY/TWITTER_API_KEY set, skipping autonomous X engine")
        return

    engine = get_autonomous_engine()
    cli_handler = get_x_claude_cli_handler()

    # Run both the engine and CLI monitor concurrently
    await asyncio.gather(
        engine.run(),
        cli_handler.run(),
        return_exceptions=True
    )


async def create_public_trading_bot():
    """Create and run the public trading bot for mass-market users."""
    from bots.public_trading_bot_supervisor import PublicBotConfig, PublicTradingBotSupervisor

    try:
        # Get configuration from environment
        telegram_token = os.environ.get("PUBLIC_BOT_TELEGRAM_TOKEN", "")
        live_trading = os.environ.get("PUBLIC_BOT_LIVE_TRADING", "false").lower() == "true"
        require_confirmation = os.environ.get("PUBLIC_BOT_REQUIRE_CONFIRMATION", "true").lower() == "true"
        min_confidence = float(os.environ.get("PUBLIC_BOT_MIN_CONFIDENCE", "65.0"))
        max_daily_loss = float(os.environ.get("PUBLIC_BOT_MAX_DAILY_LOSS", "1000.0"))

        # Check if enabled
        if not telegram_token:
            logger.info("[public_bot] PUBLIC_BOT_TELEGRAM_TOKEN not set, skipping public trading bot")
            return

        # Create config
        config = PublicBotConfig(
            enabled=True,
            telegram_token=telegram_token,
            enable_live_trading=live_trading,
            require_confirmation=require_confirmation,
            min_confidence_threshold=min_confidence,
            max_daily_loss_per_user=max_daily_loss,
        )

        # Create and initialize supervisor
        supervisor = PublicTradingBotSupervisor(config)
        success = await supervisor.initialize()

        if not success:
            logger.error("[public_bot] Failed to initialize public trading bot")
            return

        # Start the bot
        logger.info("[public_bot] Public trading bot initialized, starting polling...")
        await supervisor.start()

    except Exception as e:
        logger.error(f"[public_bot] Public trading bot error: {e}", exc_info=True)
        raise


async def create_treasury_bot():
    """Create and run the Treasury bot on its own Telegram token."""
    import subprocess

    treasury_token = (
        os.environ.get("TREASURY_BOT_TOKEN", "")
        or os.environ.get("TREASURY_BOT_TELEGRAM_TOKEN", "")
    )
    if not treasury_token:
        logger.warning("No TREASURY_BOT_TOKEN set, skipping Treasury bot")
        return

    main_token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    public_token = os.environ.get("PUBLIC_BOT_TELEGRAM_TOKEN", "")
    if treasury_token in (main_token, public_token):
        logger.warning(
            "Treasury bot token matches another bot token; skipping to avoid polling conflict"
        )
        return

    env = os.environ.copy()
    env["PYTHONPATH"] = str(project_root) + os.pathsep + env.get("PYTHONPATH", "")
    env["TREASURY_BOT_TOKEN"] = treasury_token
    env["TREASURY_BOT_TELEGRAM_TOKEN"] = treasury_token

    # Kill any lingering treasury bot processes from previous runs
    try:
        if sys.platform == "win32":
            kill_cmd = (
                'powershell -Command "'
                "Get-CimInstance Win32_Process -Filter \\\"Name='python.exe'\\\" | "
                "Where-Object { $_.CommandLine -like '*run_treasury.py*' } | "
                'ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"'
            )
            os.system(kill_cmd)
        else:
            os.system("pkill -f 'python.*run_treasury.py' 2>/dev/null || true")
        await asyncio.sleep(2)
    except Exception as e:
        logger.warning(f"Failed to clean up treasury bot processes: {e}")

    proc = subprocess.Popen(
        [sys.executable, str(project_root / "bots" / "treasury" / "run_treasury.py")],
        env=env,
    )

    try:
        while True:
            ret = proc.poll()
            if ret is not None:
                logger.error(f"Treasury bot exited with code {ret}")
                await asyncio.sleep(15)
                raise RuntimeError(f"Treasury bot exited with code {ret}")
            await asyncio.sleep(5)
    finally:
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()
                logger.warning("Treasury bot process killed (timeout on terminate)")


async def create_autonomous_manager():
    """Create and run the autonomous manager (moderation, learning, vibe coding)."""
    from core.moderation.toxicity_detector import ToxicityDetector
    from core.moderation.auto_actions import AutoActions
    from core.learning.engagement_analyzer import EngagementAnalyzer
    from core.vibe_coding.sentiment_mapper import SentimentMapper
    from core.vibe_coding.regime_adapter import RegimeAdapter
    from core.autonomous_manager import get_autonomous_manager
    from bots.twitter.grok_client import get_grok_client
    from core.sentiment_aggregator import get_sentiment_aggregator

    try:
        # Initialize all components
        logger.info("[autonomous_manager] Initializing autonomous system components...")

        # Moderation
        toxicity_detector = ToxicityDetector()
        auto_actions = AutoActions()
        logger.info("[autonomous_manager] Moderation initialized")

        # Learning
        engagement_analyzer = EngagementAnalyzer(data_dir="data/learning")
        logger.info("[autonomous_manager] Learning analyzer initialized")

        # Vibe coding
        sentiment_mapper = SentimentMapper()
        regime_adapter = RegimeAdapter()
        logger.info("[autonomous_manager] Vibe coding initialized")

        # Get shared services
        grok_client = get_grok_client()
        sentiment_agg = get_sentiment_aggregator()

        # Get or create autonomous manager
        manager = await get_autonomous_manager(
            toxicity_detector=toxicity_detector,
            auto_actions=auto_actions,
            engagement_analyzer=engagement_analyzer,
            sentiment_mapper=sentiment_mapper,
            regime_adapter=regime_adapter,
            grok_client=grok_client,
            sentiment_agg=sentiment_agg,
        )

        logger.info("[autonomous_manager] All components initialized, starting loops...")

        # Run the autonomous manager (this runs all loops continuously)
        await manager.run()

    except Exception as e:
        logger.error(f"[autonomous_manager] Failed to start: {e}", exc_info=True)
        raise


async def create_bags_intel():
    """Create and run the Bags Intel service for bags.fm graduation monitoring."""
    # DISABLED: BitQuery API has 402 payment issues - needs alternative (Helius webhooks)
    # To re-enable: Set BAGS_INTEL_ENABLED=true in environment
    if not os.environ.get("BAGS_INTEL_ENABLED", "").lower() == "true":
        logger.info("[bags_intel] DISABLED - set BAGS_INTEL_ENABLED=true to enable (needs Helius alternative)")
        # Run forever but do nothing
        while True:
            await asyncio.sleep(3600)
        return

    from bots.bags_intel import create_bags_intel_service

    try:
        await create_bags_intel_service()
    except Exception as e:
        logger.error(f"[bags_intel] Failed to start: {e}", exc_info=True)
        raise


async def create_ai_supervisor():
    """Create and run optional AI runtime supervisor (Ollama-backed)."""
    try:
        from core.ai_runtime.integration import get_ai_runtime_manager
    except Exception as exc:
        logger.warning(f"AI runtime unavailable: {exc}", exc_info=True)
        # Run forever but idle to avoid restart churn
        while True:
            await asyncio.sleep(60)

    try:
        manager = get_ai_runtime_manager()
        started = await manager.start()
        if not started:
            logger.info("AI runtime disabled or unavailable; supervisor idle")
            # Keep running to prevent supervisor restart loop
            while True:
                await asyncio.sleep(60)
        else:
            logger.info("AI runtime started successfully, entering idle loop")
            # Keep the task alive while AI runtime runs
            while True:
                await asyncio.sleep(60)
    except Exception as exc:
        logger.error(f"AI supervisor error: {exc}", exc_info=True)
        # Don't crash - just idle
        while True:
            await asyncio.sleep(60)


async def register_memory_reflect_jobs():
    """
    Register daily/weekly memory reflection jobs with the global scheduler.

    Jobs:
    - Daily reflect: 3 AM UTC every day (PERF-002: <5min timeout)
    - Weekly summary: 4 AM UTC every Sunday

    Kill switch: Set MEMORY_REFLECT_ENABLED=false to disable.
    """
    from core.automation.scheduler import get_scheduler
    from core.memory.reflect import reflect_daily
    from core.memory.patterns import generate_weekly_summary

    # Check kill switch
    if os.environ.get("MEMORY_REFLECT_ENABLED", "true").lower() != "true":
        logger.info("[memory_reflect] Disabled via MEMORY_REFLECT_ENABLED=false")
        return

    scheduler = get_scheduler()

    # Daily reflection job - 3 AM UTC every day
    daily_job_id = scheduler.schedule_cron(
        name="memory_daily_reflect",
        action=reflect_daily,
        cron_expression="0 3 * * *",  # 3 AM UTC daily
        params={},
        enabled=True,
        retry_on_failure=True,
        timeout=300.0,  # 5 minutes max (PERF-002 requirement)
        tags=["memory", "reflect", "critical"]
    )
    logger.info(f"[memory_reflect] Registered daily reflect job (3 AM UTC) - ID: {daily_job_id}")

    # Weekly summary job - 4 AM UTC every Sunday
    weekly_job_id = scheduler.schedule_cron(
        name="memory_weekly_summary",
        action=generate_weekly_summary,
        cron_expression="0 4 * * 0",  # 4 AM UTC every Sunday
        params={},
        enabled=True,
        retry_on_failure=True,
        timeout=600.0,  # 10 minutes max
        tags=["memory", "summary", "weekly"]
    )
    logger.info(f"[memory_reflect] Registered weekly summary job (Sundays 4 AM UTC) - ID: {weekly_job_id}")

    # Start the scheduler if not already running
    await scheduler.start()
    logger.info("[memory_reflect] Scheduler started for memory reflection jobs")


def validate_startup() -> bool:
    """
    Validate critical configuration before starting.

    Returns True if all critical checks pass, False otherwise.
    Uses comprehensive config validator for thorough validation.
    """
    try:
        from core.config.validator import validate_config, get_validator, ValidationLevel

        # Run comprehensive validation
        validator = get_validator()
        is_valid, results = validator.validate(strict=False)

        # Separate by level
        errors = [r for r in results if r.level == ValidationLevel.ERROR]
        warnings = [r for r in results if r.level == ValidationLevel.WARNING]
        infos = [r for r in results if r.level == ValidationLevel.INFO]

        # Print results
        if errors:
            print("\n" + "=" * 60)
            print("  STARTUP VALIDATION: FAILED")
            print("=" * 60)
            for err in errors:
                print(f"  [CRITICAL] {err.key}: {err.message}")
            if warnings:
                for warn in warnings[:5]:  # Show first 5 warnings
                    print(f"  [WARNING] {warn.key}: {warn.message}")
                if len(warnings) > 5:
                    print(f"  ... and {len(warnings) - 5} more warnings")
            print("=" * 60)
            print(f"\nRun 'python scripts/validate_config.py --fix-hints' for help\n")
            return False

        if warnings:
            print("\n" + "-" * 60)
            print("  STARTUP WARNINGS:")
            print("-" * 60)
            for warn in warnings[:10]:  # Show first 10
                print(f"  [!] {warn.key}: {warn.message}")
            if len(warnings) > 10:
                print(f"  ... and {len(warnings) - 10} more warnings")
            print("-" * 60)
            print("  Some features may be disabled. Check logs for details.\n")

        # Show group summary
        print("Configuration Status by Group:")
        groups = validator.get_group_summary()
        for group, stats in sorted(groups.items()):
            configured_pct = (stats["configured"] / stats["total"] * 100) if stats["total"] > 0 else 0
            status = "✓" if configured_pct > 50 else "!" if configured_pct > 0 else "✗"
            print(f"  {status} {group:12s}: {stats['configured']:2d}/{stats['total']:2d} ({configured_pct:3.0f}%)")
        print()

        return True  # Allow startup even with warnings

    except ImportError:
        # Fallback to basic validation if validator not available
        logger.warning("Config validator not available, using basic validation")
        return _basic_validation()
    except Exception as e:
        logger.error(f"Config validation error: {e}")
        return _basic_validation()


def _basic_validation() -> bool:
    """Fallback basic validation if comprehensive validator unavailable."""
    issues = []
    warnings = []

    # Critical: Telegram bot token
    if not os.environ.get("TELEGRAM_BOT_TOKEN"):
        issues.append("TELEGRAM_BOT_TOKEN not set - Telegram bot will not start")

    # Critical: Admin IDs
    if not os.environ.get("TELEGRAM_ADMIN_IDS"):
        warnings.append("TELEGRAM_ADMIN_IDS not set - admin commands disabled")

    # Print results
    if issues:
        print("\n" + "=" * 60)
        print("  STARTUP VALIDATION: FAILED")
        print("=" * 60)
        for issue in issues:
            print(f"  [CRITICAL] {issue}")
        for warn in warnings:
            print(f"  [WARNING] {warn}")
        print("=" * 60 + "\n")
        return False

    if warnings:
        print("\n" + "-" * 60)
        print("  STARTUP WARNINGS:")
        print("-" * 60)
        for warn in warnings:
            print(f"  [!] {warn}")
        print("-" * 60 + "\n")

    return True


async def main():
    """Main entry point with robust supervision."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(project_root / "logs" / "supervisor.log", encoding='utf-8'),
        ]
    )

    # Ensure logs directory exists
    (project_root / "logs").mkdir(exist_ok=True)

    # ==========================================================
    # SINGLE INSTANCE ENFORCEMENT: Prevent dual supervisor race
    # ==========================================================
    try:
        lock = ensure_single_instance("jarvis-supervisor")
        logger.info("Single instance lock acquired")
    except RuntimeError as e:
        print("=" * 60)
        print("  ERROR: Another supervisor instance is already running!")
        print(f"  {e}")
        print("  Kill the other instance or wait for it to exit.")
        print("=" * 60)
        sys.exit(1)

    load_env()

    # ==========================================================
    # MCP SERVERS: Optional MCP toolchain for local agents
    # ==========================================================
    if os.getenv("MCP_AUTO_START", "").lower() in ("1", "true", "yes", "on"):
        try:
            os.environ.setdefault("JARVIS_ROOT", str(project_root))
            from core.mcp_loader import start_mcp_servers
            start_mcp_servers()
            logger.info("MCP auto-start enabled")
        except Exception as exc:
            logger.warning(f"MCP auto-start failed: {exc}")

    # ==========================================================
    # CONTEXT ENGINE: Track startups to prevent restart loops
    # ==========================================================
    try:
        from core.context_engine import context as context_engine
        context_engine.record_startup()
        if context_engine.is_restart_loop():
            print("=" * 60)
            print("  WARNING: Restart loop detected!")
            print(f"  {context_engine.state.get('startup_count_today', 0)} restarts today")
            print("  Waiting 60s before continuing...")
            print("=" * 60)
            await asyncio.sleep(60)  # Cool down period
        status = context_engine.get_status()
        logger.info(f"Context engine status: restarts_today={status['restarts_today']}, "
                    f"can_run_sentiment={status['can_run_sentiment']}")
    except ImportError:
        logger.warning("Context engine not available - startup tracking disabled")

    # ==========================================================
    # DURABLE RUNS: Check for incomplete runs from previous crash
    # ==========================================================
    try:
        from core.durability import get_run_ledger

        run_ledger = get_run_ledger()
        incomplete_runs = await run_ledger.get_incomplete_runs()

        if incomplete_runs:
            print(f"\n  Found {len(incomplete_runs)} incomplete runs from previous session:")
            for run in incomplete_runs:
                current_step = run.steps[run.current_step_index].name if run.steps else "unknown"
                print(f"    - {run.intent} (step: {current_step}, state: {run.state.value})")

                # Mark for recovery (increments recovery_count)
                await run_ledger.mark_for_recovery(run.id)

                # If too many recovery attempts, abort
                if run.recovery_count >= 3:
                    logger.warning(f"Run {run.id} exceeded recovery limit, aborting")
                    await run_ledger.abort_run(run.id, "Exceeded recovery limit")
                else:
                    logger.info(f"Run {run.id} marked for recovery (attempt #{run.recovery_count + 1})")

            print()

        # Log stats
        stats = await run_ledger.get_stats()
        logger.info(f"Run ledger stats: {stats.get('total_runs', 0)} total runs, "
                    f"by_state={stats.get('by_state', {})}")

    except ImportError:
        logger.debug("Durable runs not available - crash recovery disabled")
    except Exception as e:
        logger.warning(f"Durable runs check failed: {e}")

    # Validate configuration before starting
    if not validate_startup():
        print("Fix configuration issues and restart.")
        sys.exit(1)

    print("=" * 60)
    print("  JARVIS BOT SUPERVISOR")
    print("  Robust bot management with auto-restart")
    print("=" * 60)
    print()

    # ==========================================================
    # SELF-CORRECTING AI: Initialize shared learning system
    # ==========================================================
    ollama_router = None
    self_adjuster = None
    if SELF_CORRECTING_AVAILABLE:
        try:
            print("=" * 60)
            print("  INITIALIZING SELF-CORRECTING AI SYSTEM")
            print("=" * 60)

            # Get singleton instances
            shared_memory = get_shared_memory()
            message_bus = get_message_bus()
            ollama_router = get_ollama_router()
            self_adjuster = get_self_adjuster()

            # Start async services
            await ollama_router.start()
            await self_adjuster.start()

            # Get stats
            memory_stats = shared_memory.get_global_stats()
            router_stats = ollama_router.get_stats()

            print(f"  Shared Memory: {memory_stats.get('active_learnings', 0)} learnings")
            print(f"  Message Bus: Ready for inter-bot communication")
            print(f"  Ollama Router: {'AVAILABLE' if router_stats['ollama_available'] else 'Using Claude fallback'}")
            print(f"  Self Adjuster: Ready for parameter optimization")
            print("=" * 60)
            print()

            # Register shutdown hooks
            if SHUTDOWN_MANAGER_AVAILABLE:
                shutdown_mgr = get_shutdown_manager()
                shutdown_mgr.register_hook(
                    name="ollama_router",
                    callback=ollama_router.stop,
                    phase=ShutdownPhase.CLEANUP,
                    timeout=5.0,
                )
                shutdown_mgr.register_hook(
                    name="self_adjuster",
                    callback=self_adjuster.stop,
                    phase=ShutdownPhase.CLEANUP,
                    timeout=5.0,
                )

            logger.info("Self-correcting AI system: ENABLED")

        except Exception as e:
            logger.error(f"Failed to initialize self-correcting AI system: {e}", exc_info=True)
            print("=" * 60)
            print("  WARNING: Self-correcting AI system failed to initialize")
            print(f"  Error: {e}")
            print("  Bots will run without self-learning capabilities")
            print("=" * 60)
            print()
    else:
        logger.info("Self-correcting AI system: NOT AVAILABLE")

    # Start health endpoint (best-effort)
    health_runner = None
    try:
        from bots.health_endpoint import start_health_server
        health_port = int(os.environ.get("HEALTH_PORT", "8080"))
        health_runner = await start_health_server(health_port)
        print(f"Health endpoint: http://localhost:{health_port}/health")
    except Exception as exc:
        logger.warning(f"Health endpoint unavailable: {exc}")

    # Start external heartbeat monitoring (Healthchecks.io, etc.)
    heartbeat = None
    try:
        from core.monitoring.heartbeat import get_heartbeat
        heartbeat = get_heartbeat()
        if await heartbeat.start():
            print(f"External heartbeat: enabled (interval: {heartbeat.interval}s)")
        else:
            print("External heartbeat: not configured (set HEALTHCHECKS_URL)")
    except Exception as exc:
        logger.warning(f"Heartbeat monitoring unavailable: {exc}")

    # Create supervisor
    supervisor = BotSupervisor(
        max_restarts=100,
        health_check_interval=60,
        reset_failure_after=300,
    )

    # Initialize health bus for unified monitoring
    health_bus = None
    try:
        from core.monitoring.supervisor_health_bus import (
            initialize_health_bus,
            get_health_bus,
        )
        from core.monitoring.bot_health import get_bot_health_checker
        from core.monitoring.error_rate_tracker import get_error_rate_tracker

        health_bus = await initialize_health_bus(
            supervisor=supervisor,
            bot_checker=get_bot_health_checker(),
            error_tracker=get_error_rate_tracker(),
        )
        await health_bus.start()
        print("Health bus: ENABLED (unified monitoring)")

        # Register with shutdown manager
        if SHUTDOWN_MANAGER_AVAILABLE:
            shutdown_mgr = get_shutdown_manager()
            shutdown_mgr.register_hook(
                name="health_bus",
                callback=health_bus.stop,
                phase=ShutdownPhase.CLEANUP,
                timeout=5.0,
            )
    except Exception as exc:
        logger.warning(f"Health bus unavailable: {exc}")

    # ==========================================================
    # MEMORY REFLECTION: Register scheduled jobs
    # ==========================================================
    try:
        await register_memory_reflect_jobs()
        logger.info("Memory reflection jobs: ENABLED")
    except Exception as e:
        logger.warning(f"Memory reflection jobs failed to register: {e}")

    # Register components
    # Each component runs independently - if one crashes, others continue
    supervisor.register("buy_bot", create_buy_bot, min_backoff=5.0, max_backoff=60.0)
    supervisor.register("sentiment_reporter", create_sentiment_reporter, min_backoff=10.0, max_backoff=120.0)
    supervisor.register("twitter_poster", create_twitter_poster, min_backoff=30.0, max_backoff=300.0)
    supervisor.register("telegram_bot", create_telegram_bot, min_backoff=10.0, max_backoff=60.0)
    supervisor.register("autonomous_x", create_autonomous_x_engine, min_backoff=30.0, max_backoff=300.0)
    supervisor.register("public_trading_bot", create_public_trading_bot, min_backoff=20.0, max_backoff=180.0)
    supervisor.register("treasury_bot", create_treasury_bot, min_backoff=20.0, max_backoff=180.0)
    supervisor.register("autonomous_manager", create_autonomous_manager, min_backoff=15.0, max_backoff=120.0)
    supervisor.register("bags_intel", create_bags_intel, min_backoff=30.0, max_backoff=300.0)
    supervisor.register("ai_supervisor", create_ai_supervisor, min_backoff=30.0, max_backoff=300.0)

    print("Registered components:")
    for name in supervisor.components:
        print(f"  - {name}")
    print()
    print("Starting supervisor (Ctrl+C to stop)...")
    print("=" * 60)
    print()

    # Install signal handlers via shutdown manager
    if SHUTDOWN_MANAGER_AVAILABLE:
        shutdown_mgr = get_shutdown_manager()
        shutdown_mgr.install_signal_handlers()

        # Register cleanup hooks for health services
        if heartbeat:
            shutdown_mgr.register_hook(
                name="heartbeat",
                callback=heartbeat.stop,
                phase=ShutdownPhase.CLEANUP,
                timeout=5.0,
            )

        if health_runner:
            shutdown_mgr.register_hook(
                name="health_endpoint",
                callback=health_runner.cleanup,
                phase=ShutdownPhase.CLEANUP,
                timeout=5.0,
            )

        logger.info("Shutdown manager: ENABLED")
    else:
        # Fallback to manual signal handling
        loop = asyncio.get_event_loop()

        def signal_handler():
            logger.info("Received shutdown signal")
            supervisor._running = False
            for name, state in supervisor.components.items():
                if state.task:
                    state.task.cancel()

        if sys.platform != "win32":
            for sig in (signal.SIGTERM, signal.SIGINT):
                loop.add_signal_handler(sig, signal_handler)

        logger.info("Shutdown manager: NOT AVAILABLE (using fallback)")

    try:
        await supervisor.run_forever()
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received")
    finally:
        # ==========================================================
        # DURABLE RUNS: Mark incomplete runs as paused on shutdown
        # ==========================================================
        try:
            from core.durability import get_run_ledger, RunState

            run_ledger = get_run_ledger()
            incomplete_runs = await run_ledger.get_incomplete_runs()

            for run in incomplete_runs:
                # Don't abort - just log that we're shutting down cleanly
                logger.info(f"Clean shutdown: run {run.id} ({run.intent}) will resume on restart")

            # Cleanup old runs
            deleted = await run_ledger.cleanup_old_runs(days=30)
            if deleted > 0:
                logger.info(f"Cleaned up {deleted} old runs")

        except Exception as e:
            logger.debug(f"Durable runs cleanup skipped: {e}")

        # Trigger shutdown via manager if available
        if SHUTDOWN_MANAGER_AVAILABLE:
            shutdown_mgr = get_shutdown_manager()
            await shutdown_mgr.shutdown()
        else:
            # Fallback cleanup
            await supervisor._cleanup()
            if heartbeat:
                await heartbeat.stop()
            if health_runner:
                await health_runner.cleanup()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nShutdown complete.")
