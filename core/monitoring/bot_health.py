"""
JARVIS Bot Health Monitoring

Comprehensive health monitoring for all JARVIS bots:
- Telegram bot
- Twitter/X bot
- Treasury bot
- Buy tracker bot

Provides:
- Real-time health status
- Activity metrics
- Error tracking
- Alert integration
"""

import asyncio
import logging
import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional
import json
import sqlite3
from pathlib import Path

from .health import HealthStatus, ComponentHealth, HealthMonitor, get_health_monitor

logger = logging.getLogger("jarvis.monitoring.bot_health")


# =============================================================================
# MODELS
# =============================================================================

class BotType(Enum):
    """Types of bots in the system"""
    TELEGRAM = "telegram"
    TWITTER = "twitter"
    TREASURY = "treasury"
    BUY_TRACKER = "buy_tracker"
    GROK_IMAGINE = "grok_imagine"


@dataclass
class BotMetrics:
    """Runtime metrics for a bot"""
    messages_processed: int = 0
    commands_executed: int = 0
    errors_count: int = 0
    last_activity: Optional[datetime] = None
    last_error: Optional[str] = None
    last_error_time: Optional[datetime] = None
    uptime_seconds: float = 0.0
    avg_response_time_ms: float = 0.0

    # Bot-specific metrics
    custom_metrics: Dict[str, Any] = field(default_factory=dict)


@dataclass
class BotHealth:
    """Health status for a single bot"""
    bot_type: BotType
    name: str
    status: HealthStatus
    is_running: bool
    metrics: BotMetrics
    last_check: datetime
    message: str

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "bot_type": self.bot_type.value,
            "name": self.name,
            "status": self.status.value,
            "is_running": self.is_running,
            "message": self.message,
            "last_check": self.last_check.isoformat(),
            "metrics": {
                "messages_processed": self.metrics.messages_processed,
                "commands_executed": self.metrics.commands_executed,
                "errors_count": self.metrics.errors_count,
                "last_activity": self.metrics.last_activity.isoformat() if self.metrics.last_activity else None,
                "uptime_seconds": self.metrics.uptime_seconds,
                "avg_response_time_ms": self.metrics.avg_response_time_ms,
                **self.metrics.custom_metrics,
            }
        }


# =============================================================================
# BOT HEALTH CHECKER
# =============================================================================

class BotHealthChecker:
    """
    Monitors health of all JARVIS bots.

    Features:
    - Real-time status monitoring
    - Metrics collection
    - Error tracking
    - Alerting on issues
    """

    def __init__(
        self,
        db_path: str = None,
        check_interval: float = 30.0,
    ):
        self.db_path = db_path or os.getenv(
            "BOT_HEALTH_DB",
            "data/bot_health.db"
        )
        self.check_interval = check_interval

        # Bot registrations
        self._bots: Dict[str, Dict[str, Any]] = {}
        self._metrics: Dict[str, BotMetrics] = {}
        self._start_times: Dict[str, datetime] = {}
        self._response_times: Dict[str, List[float]] = {}

        # Health status
        self._health: Dict[str, BotHealth] = {}
        self._running = False
        self._task: Optional[asyncio.Task] = None

        self._init_database()

    def _init_database(self):
        """Initialize bot health database"""
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Bot health history
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS bot_health_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                bot_name TEXT NOT NULL,
                bot_type TEXT NOT NULL,
                status TEXT NOT NULL,
                is_running INTEGER,
                messages_processed INTEGER,
                commands_executed INTEGER,
                errors_count INTEGER,
                uptime_seconds REAL,
                avg_response_time_ms REAL,
                message TEXT,
                recorded_at TEXT NOT NULL
            )
        """)

        # Bot errors log
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS bot_errors (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                bot_name TEXT NOT NULL,
                error_type TEXT,
                error_message TEXT,
                stack_trace TEXT,
                recorded_at TEXT NOT NULL
            )
        """)

        # Activity log
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS bot_activity (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                bot_name TEXT NOT NULL,
                activity_type TEXT NOT NULL,
                details TEXT,
                recorded_at TEXT NOT NULL
            )
        """)

        # Indexes
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_bot_health_name
            ON bot_health_history(bot_name)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_bot_health_time
            ON bot_health_history(recorded_at)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_bot_errors_time
            ON bot_errors(recorded_at)
        """)

        conn.commit()
        conn.close()

    # =========================================================================
    # BOT REGISTRATION
    # =========================================================================

    def register_bot(
        self,
        name: str,
        bot_type: BotType,
        check_func: Optional[Callable] = None,
        **kwargs,
    ):
        """
        Register a bot for health monitoring.

        Args:
            name: Unique name for the bot
            bot_type: Type of bot
            check_func: Optional async function to check bot health
            **kwargs: Additional bot metadata
        """
        self._bots[name] = {
            "type": bot_type,
            "check_func": check_func,
            **kwargs,
        }
        self._metrics[name] = BotMetrics()
        self._start_times[name] = datetime.now(timezone.utc)
        self._response_times[name] = []

        logger.info(f"Registered bot for health monitoring: {name} ({bot_type.value})")

    def unregister_bot(self, name: str):
        """Unregister a bot"""
        if name in self._bots:
            del self._bots[name]
            del self._metrics[name]
            del self._start_times[name]
            del self._response_times[name]
            if name in self._health:
                del self._health[name]
            logger.info(f"Unregistered bot: {name}")

    # =========================================================================
    # METRICS TRACKING
    # =========================================================================

    def record_message(self, bot_name: str):
        """Record a message processed by a bot"""
        if bot_name in self._metrics:
            self._metrics[bot_name].messages_processed += 1
            self._metrics[bot_name].last_activity = datetime.now(timezone.utc)

    def record_command(self, bot_name: str):
        """Record a command executed by a bot"""
        if bot_name in self._metrics:
            self._metrics[bot_name].commands_executed += 1
            self._metrics[bot_name].last_activity = datetime.now(timezone.utc)

    def record_error(self, bot_name: str, error: str, error_type: str = None):
        """Record an error from a bot"""
        if bot_name in self._metrics:
            self._metrics[bot_name].errors_count += 1
            self._metrics[bot_name].last_error = error
            self._metrics[bot_name].last_error_time = datetime.now(timezone.utc)

            # Log to database
            self._save_error(bot_name, error, error_type)

    def record_response_time(self, bot_name: str, response_time_ms: float):
        """Record a response time"""
        if bot_name in self._response_times:
            times = self._response_times[bot_name]
            times.append(response_time_ms)

            # Keep last 100 measurements
            if len(times) > 100:
                times.pop(0)

            # Update average
            if times:
                self._metrics[bot_name].avg_response_time_ms = sum(times) / len(times)

    def set_custom_metric(self, bot_name: str, key: str, value: Any):
        """Set a custom metric for a bot"""
        if bot_name in self._metrics:
            self._metrics[bot_name].custom_metrics[key] = value

    def record_activity(self, bot_name: str, activity_type: str, details: str = None):
        """Record bot activity"""
        if bot_name in self._metrics:
            self._metrics[bot_name].last_activity = datetime.now(timezone.utc)

            # Log to database
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO bot_activity (bot_name, activity_type, details, recorded_at)
                VALUES (?, ?, ?, ?)
            """, (
                bot_name,
                activity_type,
                details,
                datetime.now(timezone.utc).isoformat(),
            ))
            conn.commit()
            conn.close()

    def _save_error(self, bot_name: str, error: str, error_type: str = None):
        """Save error to database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO bot_errors (bot_name, error_type, error_message, recorded_at)
            VALUES (?, ?, ?, ?)
        """, (
            bot_name,
            error_type or "unknown",
            error,
            datetime.now(timezone.utc).isoformat(),
        ))
        conn.commit()
        conn.close()

    # =========================================================================
    # HEALTH CHECKS
    # =========================================================================

    async def check_bot_health(self, bot_name: str) -> BotHealth:
        """Check health of a specific bot"""
        if bot_name not in self._bots:
            return BotHealth(
                bot_type=BotType.TELEGRAM,
                name=bot_name,
                status=HealthStatus.UNKNOWN,
                is_running=False,
                metrics=BotMetrics(),
                last_check=datetime.now(timezone.utc),
                message="Bot not registered",
            )

        bot_info = self._bots[bot_name]
        metrics = self._metrics[bot_name]

        # Calculate uptime
        start_time = self._start_times.get(bot_name)
        if start_time:
            metrics.uptime_seconds = (datetime.now(timezone.utc) - start_time).total_seconds()

        # Run custom check if available
        is_running = True
        message = "Bot is healthy"
        status = HealthStatus.HEALTHY

        check_func = bot_info.get("check_func")
        if check_func:
            try:
                result = await check_func()
                if isinstance(result, dict):
                    is_running = result.get("running", True)
                    message = result.get("message", "OK")

                    if result.get("status") == "degraded":
                        status = HealthStatus.DEGRADED
                    elif result.get("status") == "unhealthy" or not is_running:
                        status = HealthStatus.UNHEALTHY
                elif isinstance(result, bool):
                    is_running = result
                    if not result:
                        status = HealthStatus.UNHEALTHY
                        message = "Bot is not running"
            except Exception as e:
                status = HealthStatus.UNHEALTHY
                message = f"Health check failed: {e}"
                is_running = False

        # Check for recent activity
        if metrics.last_activity:
            inactive_time = (datetime.now(timezone.utc) - metrics.last_activity).total_seconds()

            # Warn if inactive for more than 5 minutes
            if inactive_time > 300 and status == HealthStatus.HEALTHY:
                status = HealthStatus.DEGRADED
                message = f"No activity for {int(inactive_time)}s"

            # Unhealthy if inactive for more than 30 minutes
            if inactive_time > 1800:
                status = HealthStatus.UNHEALTHY
                message = f"Bot inactive for {int(inactive_time / 60)} minutes"

        # Check error rate
        if metrics.errors_count > 0 and metrics.messages_processed > 0:
            error_rate = metrics.errors_count / (metrics.messages_processed + metrics.commands_executed)

            if error_rate > 0.1:  # More than 10% errors
                status = HealthStatus.UNHEALTHY
                message = f"High error rate: {error_rate:.1%}"
            elif error_rate > 0.05:  # More than 5% errors
                if status == HealthStatus.HEALTHY:
                    status = HealthStatus.DEGRADED
                message = f"Elevated error rate: {error_rate:.1%}"

        health = BotHealth(
            bot_type=bot_info["type"],
            name=bot_name,
            status=status,
            is_running=is_running,
            metrics=metrics,
            last_check=datetime.now(timezone.utc),
            message=message,
        )

        self._health[bot_name] = health
        await self._save_health_snapshot(health)

        return health

    async def check_all_bots(self) -> Dict[str, BotHealth]:
        """Check health of all registered bots"""
        results = {}

        for bot_name in self._bots:
            results[bot_name] = await self.check_bot_health(bot_name)

        return results

    async def _save_health_snapshot(self, health: BotHealth):
        """Save health snapshot to database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO bot_health_history
            (bot_name, bot_type, status, is_running, messages_processed,
             commands_executed, errors_count, uptime_seconds,
             avg_response_time_ms, message, recorded_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            health.name,
            health.bot_type.value,
            health.status.value,
            1 if health.is_running else 0,
            health.metrics.messages_processed,
            health.metrics.commands_executed,
            health.metrics.errors_count,
            health.metrics.uptime_seconds,
            health.metrics.avg_response_time_ms,
            health.message,
            health.last_check.isoformat(),
        ))

        conn.commit()
        conn.close()

    # =========================================================================
    # BACKGROUND MONITORING
    # =========================================================================

    async def start(self):
        """Start background health monitoring"""
        if self._running:
            return

        self._running = True
        self._task = asyncio.create_task(self._monitor_loop())
        logger.info("Bot health monitoring started")

    async def stop(self):
        """Stop background health monitoring"""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Bot health monitoring stopped")

    async def _monitor_loop(self):
        """Background monitoring loop"""
        while self._running:
            try:
                await self.check_all_bots()

                # Check for alerts
                await self._check_alerts()

            except Exception as e:
                logger.error(f"Health check error: {e}")

            await asyncio.sleep(self.check_interval)

    async def _check_alerts(self):
        """Check for conditions requiring alerts"""
        for name, health in self._health.items():
            if health.status == HealthStatus.UNHEALTHY:
                try:
                    from .alerting import alert_manager
                    await alert_manager.trigger_alert(
                        name=f"bot_{name}_unhealthy",
                        message=f"Bot '{name}' is unhealthy: {health.message}",
                        severity="critical",
                        metadata=health.to_dict(),
                    )
                except ImportError:
                    logger.warning(f"Bot {name} is unhealthy: {health.message}")

    # =========================================================================
    # HISTORY & STATS
    # =========================================================================

    async def get_bot_history(
        self,
        bot_name: str,
        hours: int = 24,
    ) -> List[Dict[str, Any]]:
        """Get health history for a bot"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        since = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()

        cursor.execute("""
            SELECT * FROM bot_health_history
            WHERE bot_name = ? AND recorded_at >= ?
            ORDER BY recorded_at DESC
        """, (bot_name, since))

        columns = [d[0] for d in cursor.description]
        history = [dict(zip(columns, row)) for row in cursor.fetchall()]

        conn.close()
        return history

    async def get_error_log(
        self,
        bot_name: str = None,
        hours: int = 24,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Get error log for bots"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        since = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()

        query = """
            SELECT * FROM bot_errors
            WHERE recorded_at >= ?
        """
        params = [since]

        if bot_name:
            query += " AND bot_name = ?"
            params.append(bot_name)

        query += f" ORDER BY recorded_at DESC LIMIT {limit}"

        cursor.execute(query, params)

        columns = [d[0] for d in cursor.description]
        errors = [dict(zip(columns, row)) for row in cursor.fetchall()]

        conn.close()
        return errors

    async def get_activity_log(
        self,
        bot_name: str = None,
        hours: int = 24,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Get activity log for bots"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        since = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()

        query = """
            SELECT * FROM bot_activity
            WHERE recorded_at >= ?
        """
        params = [since]

        if bot_name:
            query += " AND bot_name = ?"
            params.append(bot_name)

        query += f" ORDER BY recorded_at DESC LIMIT {limit}"

        cursor.execute(query, params)

        columns = [d[0] for d in cursor.description]
        activities = [dict(zip(columns, row)) for row in cursor.fetchall()]

        conn.close()
        return activities

    async def get_uptime_stats(
        self,
        bot_name: str,
        days: int = 7,
    ) -> Dict[str, float]:
        """Get uptime statistics for a bot"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()

        cursor.execute("""
            SELECT status, COUNT(*) FROM bot_health_history
            WHERE bot_name = ? AND recorded_at >= ?
            GROUP BY status
        """, (bot_name, since))

        counts = {row[0]: row[1] for row in cursor.fetchall()}
        total = sum(counts.values())

        conn.close()

        if total == 0:
            return {"uptime_pct": 100.0}

        healthy = counts.get("healthy", 0) + counts.get("degraded", 0)

        return {
            "uptime_pct": (healthy / total) * 100,
            "healthy_pct": (counts.get("healthy", 0) / total) * 100,
            "degraded_pct": (counts.get("degraded", 0) / total) * 100,
            "unhealthy_pct": (counts.get("unhealthy", 0) / total) * 100,
            "total_checks": total,
        }

    def get_summary(self) -> Dict[str, Any]:
        """Get summary of all bot health"""
        summary = {
            "total_bots": len(self._bots),
            "healthy": 0,
            "degraded": 0,
            "unhealthy": 0,
            "bots": {},
        }

        for name, health in self._health.items():
            if health.status == HealthStatus.HEALTHY:
                summary["healthy"] += 1
            elif health.status == HealthStatus.DEGRADED:
                summary["degraded"] += 1
            else:
                summary["unhealthy"] += 1

            summary["bots"][name] = health.to_dict()

        return summary


# =============================================================================
# INTEGRATION WITH HEALTH MONITOR
# =============================================================================

def register_bot_checks(health_monitor: HealthMonitor, bot_checker: "BotHealthChecker"):
    """Register bot health checks with the main health monitor"""
    from .health import HealthCheck

    async def check_bots() -> ComponentHealth:
        """Aggregate bot health check"""
        start = time.time()

        try:
            health_dict = await bot_checker.check_all_bots()
            latency = (time.time() - start) * 1000

            healthy = sum(1 for h in health_dict.values() if h.status == HealthStatus.HEALTHY)
            degraded = sum(1 for h in health_dict.values() if h.status == HealthStatus.DEGRADED)
            unhealthy = sum(1 for h in health_dict.values() if h.status == HealthStatus.UNHEALTHY)
            total = len(health_dict)

            if unhealthy > 0:
                status = HealthStatus.UNHEALTHY
                message = f"Bots: {healthy}/{total} healthy, {unhealthy} unhealthy"
            elif degraded > 0:
                status = HealthStatus.DEGRADED
                message = f"Bots: {healthy}/{total} healthy, {degraded} degraded"
            elif healthy > 0:
                status = HealthStatus.HEALTHY
                message = f"All {total} bots healthy"
            else:
                status = HealthStatus.UNKNOWN
                message = "No bots registered"

            return ComponentHealth(
                name="bots",
                status=status,
                latency_ms=latency,
                message=message,
                last_check=datetime.now(timezone.utc),
                metadata={"healthy": healthy, "degraded": degraded, "unhealthy": unhealthy},
            )

        except Exception as e:
            return ComponentHealth(
                name="bots",
                status=HealthStatus.UNHEALTHY,
                latency_ms=(time.time() - start) * 1000,
                message=f"Bot check failed: {e}",
                last_check=datetime.now(timezone.utc),
            )

    health_monitor.register_check(HealthCheck(
        name="bots",
        check_func=check_bots,
        timeout_seconds=30.0,
        critical=False,
    ))


# =============================================================================
# SINGLETON
# =============================================================================

_bot_checker: Optional[BotHealthChecker] = None


def get_bot_health_checker() -> BotHealthChecker:
    """Get or create the bot health checker singleton"""
    global _bot_checker
    if _bot_checker is None:
        _bot_checker = BotHealthChecker()
    return _bot_checker


# =============================================================================
# CONVENIENCE DECORATORS
# =============================================================================

def track_bot_activity(bot_name: str):
    """
    Decorator to track bot function activity.

    Usage:
        @track_bot_activity("telegram")
        async def handle_message(message):
            ...
    """
    def decorator(func):
        async def wrapper(*args, **kwargs):
            checker = get_bot_health_checker()
            start = time.time()

            try:
                result = await func(*args, **kwargs)

                # Record success
                response_time = (time.time() - start) * 1000
                checker.record_response_time(bot_name, response_time)
                checker.record_message(bot_name)

                return result

            except Exception as e:
                # Record error
                checker.record_error(bot_name, str(e), type(e).__name__)
                raise

        return wrapper
    return decorator


def track_command(bot_name: str):
    """
    Decorator to track bot command execution.

    Usage:
        @track_command("telegram")
        async def handle_start_command(message):
            ...
    """
    def decorator(func):
        async def wrapper(*args, **kwargs):
            checker = get_bot_health_checker()
            start = time.time()

            try:
                result = await func(*args, **kwargs)

                # Record success
                response_time = (time.time() - start) * 1000
                checker.record_response_time(bot_name, response_time)
                checker.record_command(bot_name)

                return result

            except Exception as e:
                # Record error
                checker.record_error(bot_name, str(e), type(e).__name__)
                raise

        return wrapper
    return decorator
