"""
Supervisor Health Bus - Unified health monitoring for JARVIS Supervisor

Integrates:
- Bot health monitoring (bot_health.py)
- Error rate tracking (error_rate_tracker.py)
- Component status from supervisor
- Structured logging (logging_config.py)
- Telegram alerts for critical issues

Provides:
- Single endpoint for all health data
- Aggregated status determination
- Alert routing based on severity
- Historical data for dashboards
"""

import asyncio
import logging
import os
import json
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple
import traceback

logger = logging.getLogger("jarvis.monitoring.health_bus")


class OverallHealth(Enum):
    """Overall system health status"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


@dataclass
class ComponentHealthSnapshot:
    """Health snapshot for a single component"""
    name: str
    status: str  # healthy, degraded, unhealthy, stopped
    uptime_seconds: float = 0.0
    restart_count: int = 0
    last_error: Optional[str] = None
    last_error_time: Optional[datetime] = None
    error_rate_1min: float = 0.0
    error_rate_1hr: float = 0.0
    messages_processed: int = 0
    last_activity: Optional[datetime] = None
    custom_metrics: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SystemHealthReport:
    """Complete system health report"""
    timestamp: datetime
    overall_status: OverallHealth
    components: Dict[str, ComponentHealthSnapshot]
    total_components: int
    healthy_count: int
    degraded_count: int
    critical_count: int
    stopped_count: int
    error_summary: Dict[str, int]
    alerts_active: List[str]
    uptime_seconds: float
    message: str


class SupervisorHealthBus:
    """
    Central health monitoring hub for the JARVIS Supervisor.

    Aggregates health data from all monitoring systems and provides
    a unified interface for health checks, alerts, and dashboards.
    """

    def __init__(
        self,
        alert_webhook: Optional[str] = None,
        health_file_path: Optional[str] = None,
        check_interval: float = 30.0,
    ):
        self.alert_webhook = alert_webhook
        self.health_file_path = health_file_path or os.path.expanduser(
            "~/.lifeos/monitoring/system_health.json"
        )
        self.check_interval = check_interval

        # Component references
        self._supervisor = None
        self._bot_checker = None
        self._error_tracker = None

        # State
        self._start_time = datetime.now(timezone.utc)
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._last_report: Optional[SystemHealthReport] = None
        self._active_alerts: List[str] = []

        # Callbacks
        self._on_health_change: List[Callable[[SystemHealthReport], None]] = []
        self._on_critical: List[Callable[[str, ComponentHealthSnapshot], None]] = []

        # Create directories
        Path(self.health_file_path).parent.mkdir(parents=True, exist_ok=True)

    # =========================================================================
    # REGISTRATION
    # =========================================================================

    def register_supervisor(self, supervisor):
        """Register the supervisor for component monitoring"""
        self._supervisor = supervisor
        logger.info("Supervisor registered with health bus")

    def register_bot_checker(self, bot_checker):
        """Register the bot health checker"""
        self._bot_checker = bot_checker
        logger.info("Bot health checker registered with health bus")

    def register_error_tracker(self, error_tracker):
        """Register the error rate tracker"""
        self._error_tracker = error_tracker
        logger.info("Error rate tracker registered with health bus")

    # =========================================================================
    # HEALTH AGGREGATION
    # =========================================================================

    async def get_health_report(self) -> SystemHealthReport:
        """Generate comprehensive health report"""
        now = datetime.now(timezone.utc)
        components: Dict[str, ComponentHealthSnapshot] = {}
        error_summary: Dict[str, int] = {}

        # Collect supervisor component status
        if self._supervisor:
            try:
                supervisor_status = self._supervisor.get_status()
                for name, data in supervisor_status.items():
                    snapshot = ComponentHealthSnapshot(
                        name=name,
                        status=data.get("status", "unknown"),
                        restart_count=data.get("restart_count", 0),
                        last_error=data.get("last_error"),
                        uptime_seconds=self._parse_uptime(data.get("uptime")),
                    )
                    components[f"supervisor.{name}"] = snapshot
            except Exception as e:
                logger.error(f"Failed to get supervisor status: {e}")

        # Collect bot health checker data
        if self._bot_checker:
            try:
                bot_summary = self._bot_checker.get_summary()
                for bot_name, bot_data in bot_summary.get("bots", {}).items():
                    metrics = bot_data.get("metrics", {})
                    snapshot = ComponentHealthSnapshot(
                        name=bot_name,
                        status=bot_data.get("status", "unknown"),
                        messages_processed=metrics.get("messages_processed", 0),
                        uptime_seconds=metrics.get("uptime_seconds", 0),
                        last_activity=self._parse_datetime(metrics.get("last_activity")),
                        custom_metrics={
                            "commands_executed": metrics.get("commands_executed", 0),
                            "avg_response_time_ms": metrics.get("avg_response_time_ms", 0),
                        },
                    )
                    components[f"bot.{bot_name}"] = snapshot
            except Exception as e:
                logger.error(f"Failed to get bot health: {e}")

        # Collect error rate tracker data
        if self._error_tracker:
            try:
                error_stats = self._error_tracker.get_summary()
                error_summary = {
                    "total_1min": error_stats.get("total_errors_1min", 0),
                    "total_1hr": error_stats.get("total_errors_1hr", 0),
                    "categories_exceeded": len(error_stats.get("categories_exceeded", [])),
                }

                # Add error rates to components
                by_category = error_stats.get("by_category", {})
                for cat, cat_stats in by_category.items():
                    key = f"errors.{cat}"
                    if key not in components:
                        components[key] = ComponentHealthSnapshot(
                            name=f"error_tracker.{cat}",
                            status="healthy" if not cat_stats.get("exceeded") else "degraded",
                            error_rate_1min=cat_stats.get("count_1min", 0),
                            error_rate_1hr=cat_stats.get("count_1hr", 0),
                        )
            except Exception as e:
                logger.error(f"Failed to get error stats: {e}")

        # Calculate aggregates
        healthy_count = 0
        degraded_count = 0
        critical_count = 0
        stopped_count = 0

        for comp in components.values():
            status = comp.status.lower()
            if status in ("healthy", "running"):
                healthy_count += 1
            elif status in ("degraded", "warning", "restarting"):
                degraded_count += 1
            elif status in ("unhealthy", "critical", "failed"):
                critical_count += 1
            else:
                stopped_count += 1

        # Determine overall status
        if critical_count > 0:
            overall_status = OverallHealth.CRITICAL
            message = f"{critical_count} component(s) in critical state"
        elif degraded_count > 0:
            overall_status = OverallHealth.DEGRADED
            message = f"{degraded_count} component(s) degraded"
        elif healthy_count > 0:
            overall_status = OverallHealth.HEALTHY
            message = f"All {healthy_count} component(s) healthy"
        else:
            overall_status = OverallHealth.UNKNOWN
            message = "No components reporting"

        uptime = (now - self._start_time).total_seconds()

        report = SystemHealthReport(
            timestamp=now,
            overall_status=overall_status,
            components=components,
            total_components=len(components),
            healthy_count=healthy_count,
            degraded_count=degraded_count,
            critical_count=critical_count,
            stopped_count=stopped_count,
            error_summary=error_summary,
            alerts_active=list(self._active_alerts),
            uptime_seconds=uptime,
            message=message,
        )

        self._last_report = report

        # Check for status changes and trigger callbacks
        await self._check_status_changes(report)

        # Save to file for external monitoring
        await self._save_health_file(report)

        return report

    async def _check_status_changes(self, report: SystemHealthReport):
        """Check for status changes and trigger callbacks"""
        # Notify on overall health change
        for callback in self._on_health_change:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(report)
                else:
                    callback(report)
            except Exception as e:
                logger.error(f"Health change callback error: {e}")

        # Check for critical components
        for name, comp in report.components.items():
            if comp.status.lower() in ("unhealthy", "critical", "failed"):
                for callback in self._on_critical:
                    try:
                        if asyncio.iscoroutinefunction(callback):
                            await callback(name, comp)
                        else:
                            callback(name, comp)
                    except Exception as e:
                        logger.error(f"Critical callback error: {e}")

    async def _save_health_file(self, report: SystemHealthReport):
        """Save health report to file for external monitoring"""
        try:
            data = {
                "timestamp": report.timestamp.isoformat(),
                "overall_status": report.overall_status.value,
                "message": report.message,
                "counts": {
                    "total": report.total_components,
                    "healthy": report.healthy_count,
                    "degraded": report.degraded_count,
                    "critical": report.critical_count,
                    "stopped": report.stopped_count,
                },
                "error_summary": report.error_summary,
                "uptime_seconds": report.uptime_seconds,
                "components": {
                    name: {
                        "status": comp.status,
                        "uptime_seconds": comp.uptime_seconds,
                        "restart_count": comp.restart_count,
                        "last_error": comp.last_error,
                        "error_rate_1min": comp.error_rate_1min,
                        "messages_processed": comp.messages_processed,
                    }
                    for name, comp in report.components.items()
                },
            }

            with open(self.health_file_path, 'w') as f:
                json.dump(data, f, indent=2, default=str)

        except Exception as e:
            logger.error(f"Failed to save health file: {e}")

    # =========================================================================
    # CALLBACKS
    # =========================================================================

    def on_health_change(self, callback: Callable[[SystemHealthReport], None]):
        """Register callback for health status changes"""
        self._on_health_change.append(callback)

    def on_critical(self, callback: Callable[[str, ComponentHealthSnapshot], None]):
        """Register callback for critical component status"""
        self._on_critical.append(callback)

    # =========================================================================
    # ALERTING
    # =========================================================================

    async def send_alert(
        self,
        title: str,
        message: str,
        severity: str = "warning",
        component: Optional[str] = None,
    ):
        """Send alert via configured channels"""
        alert_id = f"{severity}:{component or 'system'}:{int(time.time())}"

        # Add to active alerts
        if severity in ("critical", "error"):
            if alert_id not in self._active_alerts:
                self._active_alerts.append(alert_id)

        # Log the alert
        log_level = logging.CRITICAL if severity == "critical" else \
                   logging.ERROR if severity == "error" else \
                   logging.WARNING
        logger.log(log_level, f"ALERT [{severity}] {title}: {message}")

        # Send Telegram alert for critical issues
        if severity in ("critical", "error"):
            await self._send_telegram_alert(title, message, severity)

    async def _send_telegram_alert(self, title: str, message: str, severity: str):
        """Send alert to Telegram admins"""
        try:
            import aiohttp

            token = os.environ.get("TELEGRAM_BOT_TOKEN")
            admin_ids = os.environ.get("TELEGRAM_ADMIN_IDS", "")

            if not token or not admin_ids:
                return

            admin_list = [x.strip() for x in admin_ids.split(",") if x.strip().isdigit()]
            if not admin_list:
                return

            emoji = "" if severity == "critical" else "" if severity == "error" else ""

            text = (
                f"{emoji} <b>{title}</b>\n\n"
                f"{message}\n\n"
                f"<i>Severity: {severity}</i>"
            )

            async with aiohttp.ClientSession() as session:
                for admin_id in admin_list[:3]:
                    url = f"https://api.telegram.org/bot{token}/sendMessage"
                    await session.post(url, json={
                        "chat_id": admin_id,
                        "text": text,
                        "parse_mode": "HTML",
                    })

        except Exception as e:
            logger.debug(f"Failed to send Telegram alert: {e}")

    def clear_alert(self, alert_id: str):
        """Clear an active alert"""
        if alert_id in self._active_alerts:
            self._active_alerts.remove(alert_id)

    # =========================================================================
    # BACKGROUND MONITORING
    # =========================================================================

    async def start(self):
        """Start background health monitoring"""
        if self._running:
            return

        self._running = True
        self._task = asyncio.create_task(self._monitor_loop())
        logger.info("Health bus monitoring started")

    async def stop(self):
        """Stop background health monitoring"""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Health bus monitoring stopped")

    async def _monitor_loop(self):
        """Background monitoring loop"""
        while self._running:
            try:
                report = await self.get_health_report()

                # Log health status periodically
                logger.info(
                    f"Health check: {report.overall_status.value} - "
                    f"{report.healthy_count} healthy, "
                    f"{report.degraded_count} degraded, "
                    f"{report.critical_count} critical"
                )

            except Exception as e:
                logger.error(f"Health monitor error: {e}", exc_info=True)

            await asyncio.sleep(self.check_interval)

    # =========================================================================
    # UTILITIES
    # =========================================================================

    def _parse_uptime(self, uptime_str: Optional[str]) -> float:
        """Parse uptime string to seconds"""
        if not uptime_str:
            return 0.0
        try:
            # Format: "0:05:30" or timedelta string
            parts = str(uptime_str).split(":")
            if len(parts) == 3:
                hours = int(parts[0])
                minutes = int(parts[1])
                seconds = float(parts[2])
                return hours * 3600 + minutes * 60 + seconds
            return float(uptime_str)
        except (ValueError, TypeError, AttributeError) as e:
            logger.warning(f"Failed to parse uptime '{uptime_str}': {e}")
            return 0.0

    def _parse_datetime(self, dt_str: Optional[str]) -> Optional[datetime]:
        """Parse datetime string"""
        if not dt_str:
            return None
        try:
            return datetime.fromisoformat(dt_str.replace('Z', '+00:00'))
        except (ValueError, TypeError, AttributeError) as e:
            logger.warning(f"Failed to parse datetime '{dt_str}': {e}")
            return None

    # =========================================================================
    # PUBLIC API
    # =========================================================================

    def get_status_summary(self) -> Dict[str, Any]:
        """Get quick status summary (no async)"""
        if self._last_report:
            return {
                "status": self._last_report.overall_status.value,
                "message": self._last_report.message,
                "healthy": self._last_report.healthy_count,
                "degraded": self._last_report.degraded_count,
                "critical": self._last_report.critical_count,
                "uptime_seconds": self._last_report.uptime_seconds,
                "timestamp": self._last_report.timestamp.isoformat(),
            }
        return {
            "status": "unknown",
            "message": "No health report available",
        }

    def is_healthy(self) -> bool:
        """Quick check if system is healthy"""
        if self._last_report:
            return self._last_report.overall_status == OverallHealth.HEALTHY
        return True  # Assume healthy if no report yet


# =============================================================================
# SINGLETON
# =============================================================================

_health_bus: Optional[SupervisorHealthBus] = None


def get_health_bus() -> SupervisorHealthBus:
    """Get or create the health bus singleton"""
    global _health_bus
    if _health_bus is None:
        _health_bus = SupervisorHealthBus()
    return _health_bus


async def initialize_health_bus(
    supervisor=None,
    bot_checker=None,
    error_tracker=None,
) -> SupervisorHealthBus:
    """Initialize the health bus with all components"""
    bus = get_health_bus()

    if supervisor:
        bus.register_supervisor(supervisor)

    if bot_checker:
        bus.register_bot_checker(bot_checker)

    if error_tracker:
        bus.register_error_tracker(error_tracker)

    # Auto-discover components if not provided
    if not bot_checker:
        try:
            from .bot_health import get_bot_health_checker
            bus.register_bot_checker(get_bot_health_checker())
        except ImportError:
            pass

    if not error_tracker:
        try:
            from .error_rate_tracker import get_error_rate_tracker
            bus.register_error_tracker(get_error_rate_tracker())
        except ImportError:
            pass

    return bus


# =============================================================================
# STRUCTURED ERROR LOGGING
# =============================================================================

def log_component_error(
    component: str,
    error: Exception,
    context: Optional[Dict[str, Any]] = None,
    severity: str = "error",
):
    """
    Log a component error with structured data.

    This provides consistent error logging across all bots and integrates
    with the error rate tracker.

    Args:
        component: Component name (e.g., "telegram_bot", "treasury")
        error: The exception that occurred
        context: Additional context data
        severity: Severity level (error, warning, critical)
    """
    from core.logging_config import get_logger, CorrelationContext

    comp_logger = get_logger(f"jarvis.{component}")

    error_data = {
        "component": component,
        "error_type": type(error).__name__,
        "error_message": str(error),
        "severity": severity,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    if context:
        error_data["context"] = context

    # Log with structured data
    if severity == "critical":
        comp_logger.critical(
            f"[{component}] Critical error: {error}",
            exc_info=True,
            **error_data
        )
    else:
        comp_logger.error(
            f"[{component}] Error: {error}",
            exc_info=True,
            **error_data
        )

    # Record in error tracker
    try:
        from .error_rate_tracker import record_error, ErrorCategory

        # Map component to category
        category_map = {
            "telegram": ErrorCategory.EXTERNAL,
            "twitter": ErrorCategory.EXTERNAL,
            "treasury": ErrorCategory.TRADING,
            "buy_tracker": ErrorCategory.TRADING,
            "api": ErrorCategory.API,
            "database": ErrorCategory.DATABASE,
        }

        category = ErrorCategory.INTERNAL
        for key, cat in category_map.items():
            if key in component.lower():
                category = cat
                break

        record_error(
            category=category,
            message=str(error),
            source=component,
            error_code=type(error).__name__,
            metadata=context,
        )
    except Exception as e:
        logger.debug(f"Failed to record error in tracker: {e}")


def log_bot_event(
    bot_name: str,
    event_type: str,
    message: str,
    data: Optional[Dict[str, Any]] = None,
):
    """
    Log a bot event with structured data.

    Args:
        bot_name: Name of the bot
        event_type: Type of event (startup, message, command, etc.)
        message: Event description
        data: Additional event data
    """
    from core.logging_config import get_logger

    bot_logger = get_logger(f"jarvis.bot.{bot_name}")

    event_data = {
        "bot": bot_name,
        "event_type": event_type,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    if data:
        event_data.update(data)

    bot_logger.info(f"[{bot_name}] {event_type}: {message}", **event_data)

    # Record in bot health checker
    try:
        from .bot_health import get_bot_health_checker
        checker = get_bot_health_checker()
        checker.record_activity(bot_name, event_type, message)
    except Exception:
        pass
