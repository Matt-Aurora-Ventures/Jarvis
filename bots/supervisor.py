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
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass, field
from enum import Enum

# Import safe task tracking
try:
    from core.async_utils import fire_and_forget, TaskTracker
    TASK_TRACKING_AVAILABLE = True
except ImportError:
    TASK_TRACKING_AVAILABLE = False
    fire_and_forget = None
    TaskTracker = None


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

    async def _cleanup(self):
        """Clean up all components."""
        logger.info("Supervisor shutting down...")
        systemd_notify("STOPPING=1")

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
    claude_client = ClaudeContentGenerator(api_key=os.environ.get("ANTHROPIC_API_KEY"))

    poster = SentimentTwitterPoster(
        twitter_client=twitter_client,
        claude_client=claude_client,
        interval_minutes=60,  # Changed to 1 hour
    )
    await poster.start()


async def create_telegram_bot():
    """Create and run the main Telegram bot with anti-scam."""
    import subprocess

    tg_token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    if not tg_token:
        logger.warning("No TELEGRAM_BOT_TOKEN set, skipping Telegram bot")
        return

    # Run as subprocess to isolate it
    env = os.environ.copy()
    env["PYTHONPATH"] = str(project_root) + os.pathsep + env.get("PYTHONPATH", "")

    proc = subprocess.Popen(
        [sys.executable, str(project_root / "tg_bot" / "bot.py")],
        env=env,
    )

    try:
        # Wait for process to complete (it shouldn't unless it crashes)
        while True:
            ret = proc.poll()
            if ret is not None:
                raise RuntimeError(f"Telegram bot exited with code {ret}")
            await asyncio.sleep(5)
    finally:
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()


async def create_autonomous_x_engine():
    """Create and run the autonomous X (Twitter) posting engine."""
    from bots.twitter.autonomous_engine import get_autonomous_engine
    from bots.twitter.x_claude_cli_handler import get_x_claude_cli_handler

    # Check for required credentials
    x_api_key = os.environ.get("X_API_KEY", "")
    if not x_api_key:
        logger.warning("No X_API_KEY set, skipping autonomous X engine")
        return

    engine = get_autonomous_engine()
    cli_handler = get_x_claude_cli_handler()

    # Run both the engine and CLI monitor concurrently
    await asyncio.gather(
        engine.run(),
        cli_handler.run(),
        return_exceptions=True
    )


def validate_startup() -> bool:
    """
    Validate critical configuration before starting.

    Returns True if all critical checks pass, False otherwise.
    """
    issues = []
    warnings = []

    # Critical: Telegram bot token
    if not os.environ.get("TELEGRAM_BOT_TOKEN"):
        issues.append("TELEGRAM_BOT_TOKEN not set - Telegram bot will not start")

    # Critical: Admin IDs
    if not os.environ.get("TELEGRAM_ADMIN_IDS"):
        warnings.append("TELEGRAM_ADMIN_IDS not set - admin commands disabled")

    # Warning: Trading credentials
    if not os.environ.get("WALLET_PRIVATE_KEY"):
        warnings.append("WALLET_PRIVATE_KEY not set - trading disabled")

    if not os.environ.get("SOLANA_RPC_URL"):
        warnings.append("SOLANA_RPC_URL not set - using public RPC")

    # Warning: AI APIs
    if not os.environ.get("XAI_API_KEY") and not os.environ.get("GROK_API_KEY"):
        warnings.append("XAI_API_KEY/GROK_API_KEY not set - Grok features disabled")

    if not os.environ.get("ANTHROPIC_API_KEY"):
        warnings.append("ANTHROPIC_API_KEY not set - Claude features disabled")

    # Warning: X/Twitter
    if not os.environ.get("JARVIS_ACCESS_TOKEN"):
        warnings.append("JARVIS_ACCESS_TOKEN not set - X posting disabled")

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

    load_env()

    # Validate configuration before starting
    if not validate_startup():
        print("Fix configuration issues and restart.")
        sys.exit(1)

    print("=" * 60)
    print("  JARVIS BOT SUPERVISOR")
    print("  Robust bot management with auto-restart")
    print("=" * 60)
    print()

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

    # Register components
    # Each component runs independently - if one crashes, others continue
    supervisor.register("buy_bot", create_buy_bot, min_backoff=5.0, max_backoff=60.0)
    supervisor.register("sentiment_reporter", create_sentiment_reporter, min_backoff=10.0, max_backoff=120.0)
    supervisor.register("twitter_poster", create_twitter_poster, min_backoff=30.0, max_backoff=300.0)
    supervisor.register("telegram_bot", create_telegram_bot, min_backoff=10.0, max_backoff=60.0)
    supervisor.register("autonomous_x", create_autonomous_x_engine, min_backoff=30.0, max_backoff=300.0)

    print("Registered components:")
    for name in supervisor.components:
        print(f"  - {name}")
    print()
    print("Starting supervisor (Ctrl+C to stop)...")
    print("=" * 60)
    print()

    # Handle shutdown signals
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

    try:
        await supervisor.run_forever()
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received")
    finally:
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
