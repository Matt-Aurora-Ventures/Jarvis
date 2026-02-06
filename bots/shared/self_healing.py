"""
Self-Healing Configuration for ClawdBots on VPS.

Provides process health monitoring, automatic restart on crash,
memory/CPU threshold alerts, heartbeat mechanism, and log error detection.

Designed to run as a background thread in each Telegram bot.

Usage:
    from bots.shared.self_healing import ProcessWatchdog, SelfHealingConfig

    config = SelfHealingConfig(
        bot_name="clawdjarvis",
        memory_threshold_mb=256,
        heartbeat_interval=30,
    )

    watchdog = ProcessWatchdog(config)
    watchdog.on_alert(lambda t, d: send_telegram_alert(t, d))
    watchdog.start()

Dependencies:
    - psutil (for process monitoring)
    - Standard library only otherwise
"""

import json
import logging
import os
import re
import sys
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Match, Optional, Tuple

try:
    import psutil
except ImportError:
    psutil = None  # type: ignore

logger = logging.getLogger(__name__)


# ==============================================================================
# Configuration Classes
# ==============================================================================


@dataclass
class SelfHealingConfig:
    """Configuration for self-healing watchdog.

    Attributes:
        bot_name: Identifier for the bot (e.g., "clawdjarvis")
        heartbeat_interval: Seconds between heartbeat updates
        health_check_interval: Seconds between health checks
        max_restart_attempts: Maximum restart attempts before giving up
        restart_cooldown: Seconds to wait between restart attempts
        memory_threshold_mb: Memory usage threshold in MB
        cpu_threshold_percent: CPU usage threshold as percentage
        log_file: Path to log file for error detection
        heartbeat_dir: Directory for heartbeat files
    """
    bot_name: str = "unknown"
    heartbeat_interval: int = 30
    health_check_interval: int = 60
    max_restart_attempts: int = 3
    restart_cooldown: int = 300
    memory_threshold_mb: int = 512
    cpu_threshold_percent: int = 80
    log_file: Optional[Path] = None
    heartbeat_dir: Optional[Path] = None

    def __post_init__(self):
        """Set default paths after initialization."""
        if self.heartbeat_dir is None:
            # Default to /root/clawdbots/.heartbeats on VPS
            default_dir = Path("/root/clawdbots/.heartbeats")
            if default_dir.parent.exists():
                self.heartbeat_dir = default_dir
            else:
                # Fallback for local development
                self.heartbeat_dir = Path.home() / ".clawdbots" / ".heartbeats"


@dataclass
class ResourceThresholds:
    """Resource usage thresholds for alerts.

    Attributes:
        memory_mb: Memory threshold in megabytes
        cpu_percent: CPU usage threshold as percentage (0-100)
        disk_percent: Disk usage threshold as percentage (0-100)
    """
    memory_mb: int = 512
    cpu_percent: int = 80
    disk_percent: int = 90

    def is_memory_exceeded(self, current_mb: float) -> bool:
        """Check if memory usage exceeds threshold."""
        return current_mb > self.memory_mb

    def is_cpu_exceeded(self, current_percent: float) -> bool:
        """Check if CPU usage exceeds threshold."""
        return current_percent > self.cpu_percent

    def is_disk_exceeded(self, current_percent: float) -> bool:
        """Check if disk usage exceeds threshold."""
        return current_percent > self.disk_percent


class HealthStatus(Enum):
    """Health status levels."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    CRITICAL = "critical"

    def is_operational(self) -> bool:
        """Check if status is operational (healthy or degraded)."""
        return self in (HealthStatus.HEALTHY, HealthStatus.DEGRADED)


@dataclass
class RestartPolicy:
    """Policy for restart decisions.

    Attributes:
        max_attempts: Maximum restart attempts
        cooldown_seconds: Base cooldown between restarts
        backoff_multiplier: Multiplier for exponential backoff
    """
    max_attempts: int = 3
    cooldown_seconds: int = 300
    backoff_multiplier: float = 2.0
    _attempt_count: int = field(default=0, init=False, repr=False)
    _last_restart: Optional[datetime] = field(default=None, init=False, repr=False)

    def should_restart(self, attempt_count: Optional[int] = None) -> bool:
        """Determine if restart should be attempted.

        Args:
            attempt_count: Override internal attempt count (for testing)

        Returns:
            True if restart should be attempted
        """
        count = attempt_count if attempt_count is not None else self._attempt_count
        return count < self.max_attempts

    def get_backoff_delay(self, attempt: Optional[int] = None) -> float:
        """Calculate delay before next restart attempt.

        Args:
            attempt: Override internal attempt count

        Returns:
            Delay in seconds with exponential backoff
        """
        count = attempt if attempt is not None else self._attempt_count
        return self.cooldown_seconds * (self.backoff_multiplier ** count)

    def record_restart(self) -> None:
        """Record a restart attempt."""
        self._attempt_count += 1
        self._last_restart = datetime.now()

    def reset(self) -> None:
        """Reset restart attempt counter."""
        self._attempt_count = 0
        self._last_restart = None


# ==============================================================================
# Error Pattern Detection
# ==============================================================================


@dataclass
class ErrorPattern:
    """Pattern for detecting errors in log lines.

    Attributes:
        name: Identifier for this pattern
        regex: Regular expression to match
        severity: Severity level (low, medium, high, critical)
        action: Optional callback when pattern matches
        description: Human-readable description
    """
    name: str
    regex: str
    severity: str = "medium"
    action: Optional[Callable[[Match], None]] = None
    description: str = ""

    def __post_init__(self):
        """Compile regex pattern."""
        self._compiled = re.compile(self.regex, re.IGNORECASE)

    def match(self, line: str) -> Optional[Match]:
        """Check if line matches this pattern."""
        return self._compiled.search(line)


@dataclass
class ErrorMatch:
    """Result of an error pattern match."""
    name: str
    severity: str
    line: str
    match: Match
    timestamp: datetime = field(default_factory=datetime.now)


class LogErrorDetector:
    """Detects error patterns in log lines.

    Monitors log output for known error patterns and triggers
    alerts or actions based on severity.
    """

    # Default error patterns
    DEFAULT_PATTERNS = [
        ErrorPattern(
            name="critical_error",
            regex=r"\bCRITICAL\b",
            severity="critical",
            description="Critical level log message",
        ),
        ErrorPattern(
            name="error_log",
            regex=r"\bERROR\b",
            severity="high",
            description="Error level log message",
        ),
        ErrorPattern(
            name="exception",
            regex=r"(?:Traceback|Exception|Error:)",
            severity="high",
            description="Python exception or traceback",
        ),
        ErrorPattern(
            name="memory_error",
            regex=r"MemoryError|OutOfMemory|Cannot allocate",
            severity="critical",
            description="Memory allocation failure",
        ),
        ErrorPattern(
            name="connection_error",
            regex=r"ConnectionError|ConnectionRefused|NetworkError",
            severity="high",
            description="Network connection failure",
        ),
        ErrorPattern(
            name="timeout_error",
            regex=r"TimeoutError|Timed out|timeout exceeded",
            severity="medium",
            description="Operation timeout",
        ),
        ErrorPattern(
            name="rate_limit",
            regex=r"rate.?limit|429|too many requests",
            severity="medium",
            description="API rate limiting",
        ),
        ErrorPattern(
            name="auth_error",
            regex=r"Unauthorized|403|401|authentication failed",
            severity="high",
            description="Authentication failure",
        ),
        ErrorPattern(
            name="telegram_conflict",
            regex=r"Conflict.*terminated.*other.*getUpdates",
            severity="critical",
            description="Telegram polling conflict (duplicate instance)",
        ),
    ]

    def __init__(
        self,
        bot_name: str,
        patterns: Optional[List[ErrorPattern]] = None,
    ):
        """Initialize error detector.

        Args:
            bot_name: Bot identifier for logging
            patterns: Custom patterns (defaults used if None)
        """
        self.bot_name = bot_name
        self.patterns: List[ErrorPattern] = patterns or self.DEFAULT_PATTERNS.copy()
        self._error_history: List[ErrorMatch] = []
        self._max_history = 1000

    def add_pattern(self, pattern: ErrorPattern) -> None:
        """Add a custom error pattern."""
        self.patterns.append(pattern)

    def check_line(self, line: str) -> List[ErrorMatch]:
        """Check a log line for error patterns.

        Args:
            line: Log line to check

        Returns:
            List of matching error patterns
        """
        matches = []
        for pattern in self.patterns:
            match = pattern.match(line)
            if match:
                error_match = ErrorMatch(
                    name=pattern.name,
                    severity=pattern.severity,
                    line=line,
                    match=match,
                )
                matches.append(error_match)
                self._error_history.append(error_match)

                # Execute action if defined
                if pattern.action:
                    try:
                        pattern.action(match)
                    except Exception as e:
                        logger.warning(f"Error pattern action failed: {e}")

        # Trim history if needed
        if len(self._error_history) > self._max_history:
            self._error_history = self._error_history[-self._max_history:]

        return matches

    def get_error_summary(
        self,
        since: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """Get summary of detected errors.

        Args:
            since: Only include errors after this time

        Returns:
            Dictionary with error statistics
        """
        if since:
            errors = [e for e in self._error_history if e.timestamp >= since]
        else:
            errors = self._error_history

        by_severity: Dict[str, int] = {}
        by_name: Dict[str, int] = {}

        for error in errors:
            by_severity[error.severity] = by_severity.get(error.severity, 0) + 1
            by_name[error.name] = by_name.get(error.name, 0) + 1

        return {
            "total_errors": len(errors),
            "by_severity": by_severity,
            "by_name": by_name,
            "most_recent": errors[-1] if errors else None,
        }

    def clear_history(self) -> None:
        """Clear error history."""
        self._error_history.clear()


# ==============================================================================
# Heartbeat Manager
# ==============================================================================


class HeartbeatManager:
    """Manages heartbeat signals for process liveness detection.

    Writes periodic heartbeat files that can be monitored by
    external systems (systemd, cron watchdog, etc.)
    """

    def __init__(
        self,
        bot_name: str,
        interval: int = 30,
        heartbeat_dir: Optional[Path] = None,
    ):
        """Initialize heartbeat manager.

        Args:
            bot_name: Bot identifier
            interval: Seconds between heartbeats
            heartbeat_dir: Directory for heartbeat files
        """
        self.bot_name = bot_name
        self.interval = interval
        self.heartbeat_dir = heartbeat_dir
        self.last_heartbeat: Optional[datetime] = None
        self._running = False
        self._thread: Optional[threading.Thread] = None

        # Create heartbeat directory if specified
        if self.heartbeat_dir:
            self.heartbeat_dir.mkdir(parents=True, exist_ok=True)

    def record_heartbeat(self) -> None:
        """Record a heartbeat timestamp."""
        self.last_heartbeat = datetime.now()

        # Write to file if directory specified
        if self.heartbeat_dir:
            self._write_heartbeat_file()

    def _write_heartbeat_file(self) -> None:
        """Write heartbeat to file."""
        if not self.heartbeat_dir:
            return

        heartbeat_file = self.heartbeat_dir / f"{self.bot_name}.heartbeat"
        try:
            data = {
                "bot_name": self.bot_name,
                "timestamp": self.last_heartbeat.isoformat() if self.last_heartbeat else None,
                "pid": os.getpid(),
            }
            heartbeat_file.write_text(json.dumps(data))
        except Exception as e:
            logger.warning(f"Failed to write heartbeat file: {e}")

    def is_alive(self, tolerance_multiplier: float = 2.0) -> bool:
        """Check if heartbeat is recent enough to be considered alive.

        Args:
            tolerance_multiplier: How many intervals before considered dead

        Returns:
            True if heartbeat is within tolerance
        """
        if self.last_heartbeat is None:
            return False

        threshold = timedelta(seconds=self.interval * tolerance_multiplier)
        return datetime.now() - self.last_heartbeat < threshold

    def get_seconds_since_heartbeat(self) -> float:
        """Get seconds since last heartbeat."""
        if self.last_heartbeat is None:
            return float("inf")
        return (datetime.now() - self.last_heartbeat).total_seconds()

    def start_background(self) -> None:
        """Start background heartbeat thread."""
        if self._running:
            return

        self._running = True
        self._thread = threading.Thread(
            target=self._heartbeat_loop,
            daemon=True,
            name=f"heartbeat-{self.bot_name}",
        )
        self._thread.start()
        logger.info(f"[{self.bot_name}] Heartbeat started (interval={self.interval}s)")

    def stop(self) -> None:
        """Stop background heartbeat thread."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
            self._thread = None
        logger.info(f"[{self.bot_name}] Heartbeat stopped")

    def _heartbeat_loop(self) -> None:
        """Background heartbeat loop."""
        while self._running:
            self.record_heartbeat()
            time.sleep(self.interval)


# ==============================================================================
# Health Monitor
# ==============================================================================


class HealthMonitor:
    """Monitors process health metrics (memory, CPU, etc.)."""

    def __init__(self, config: SelfHealingConfig):
        """Initialize health monitor.

        Args:
            config: Self-healing configuration
        """
        self.bot_name = config.bot_name
        self.config = config
        self.thresholds = ResourceThresholds(
            memory_mb=config.memory_threshold_mb,
            cpu_percent=config.cpu_threshold_percent,
        )
        self.is_running = False
        self._process: Optional["psutil.Process"] = None

    def _get_process(self) -> Optional["psutil.Process"]:
        """Get current process object."""
        if psutil is None:
            logger.warning("psutil not available - health monitoring limited")
            return None

        if self._process is None:
            self._process = psutil.Process()
        return self._process

    def get_memory_usage_mb(self) -> float:
        """Get current memory usage in MB."""
        process = self._get_process()
        if process is None:
            return 0.0

        try:
            memory_info = process.memory_info()
            return memory_info.rss / (1024 * 1024)  # Convert bytes to MB
        except Exception as e:
            logger.warning(f"Failed to get memory usage: {e}")
            return 0.0

    def get_cpu_usage_percent(self) -> float:
        """Get current CPU usage percentage."""
        process = self._get_process()
        if process is None:
            return 0.0

        try:
            return process.cpu_percent()
        except Exception as e:
            logger.warning(f"Failed to get CPU usage: {e}")
            return 0.0

    def check_health(self) -> HealthStatus:
        """Check overall process health.

        Returns:
            HealthStatus based on resource usage
        """
        memory_mb = self.get_memory_usage_mb()
        cpu_percent = self.get_cpu_usage_percent()

        memory_exceeded = self.thresholds.is_memory_exceeded(memory_mb)
        cpu_exceeded = self.thresholds.is_cpu_exceeded(cpu_percent)

        # Determine status based on thresholds
        if memory_exceeded and cpu_exceeded:
            return HealthStatus.CRITICAL
        elif memory_exceeded or cpu_exceeded:
            return HealthStatus.DEGRADED
        else:
            return HealthStatus.HEALTHY

    def get_health_report(self) -> Dict[str, Any]:
        """Get detailed health report.

        Returns:
            Dictionary with health metrics
        """
        memory_mb = self.get_memory_usage_mb()
        cpu_percent = self.get_cpu_usage_percent()
        status = self.check_health()

        return {
            "bot_name": self.bot_name,
            "status": status.value,
            "operational": status.is_operational(),
            "memory_mb": round(memory_mb, 2),
            "memory_threshold_mb": self.thresholds.memory_mb,
            "memory_exceeded": self.thresholds.is_memory_exceeded(memory_mb),
            "cpu_percent": round(cpu_percent, 2),
            "cpu_threshold_percent": self.thresholds.cpu_percent,
            "cpu_exceeded": self.thresholds.is_cpu_exceeded(cpu_percent),
            "timestamp": datetime.now().isoformat(),
        }


# ==============================================================================
# Process Watchdog
# ==============================================================================


AlertCallback = Callable[[str, Dict[str, Any]], None]
RestartCallback = Callable[[], None]


class ProcessWatchdog:
    """Main watchdog that orchestrates self-healing.

    Monitors process health, triggers alerts, and coordinates restarts.
    Runs as a background thread alongside the main bot.
    """

    def __init__(self, config: SelfHealingConfig):
        """Initialize process watchdog.

        Args:
            config: Self-healing configuration
        """
        self.config = config
        self.bot_name = config.bot_name

        # Components
        self.health_monitor = HealthMonitor(config)
        self.heartbeat_manager = HeartbeatManager(
            bot_name=config.bot_name,
            interval=config.heartbeat_interval,
            heartbeat_dir=config.heartbeat_dir,
        )
        self.error_detector = LogErrorDetector(bot_name=config.bot_name)
        self.restart_policy = RestartPolicy(
            max_attempts=config.max_restart_attempts,
            cooldown_seconds=config.restart_cooldown,
        )

        # State
        self.restart_count = 0
        self.is_running = False
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

        # Callbacks
        self._alert_callbacks: List[AlertCallback] = []
        self._restart_callbacks: List[RestartCallback] = []

        # Alert state (prevent spam)
        self._last_alerts: Dict[str, datetime] = {}
        self._alert_cooldown = 300  # 5 minutes between same alerts

    def on_alert(self, callback: AlertCallback) -> None:
        """Register callback for alerts.

        Args:
            callback: Function(alert_type, details) to call on alert
        """
        self._alert_callbacks.append(callback)

    def on_restart(self, callback: RestartCallback) -> None:
        """Register callback for restarts.

        Args:
            callback: Function() to call on restart
        """
        self._restart_callbacks.append(callback)

    def start(self) -> None:
        """Start the watchdog background thread."""
        if self.is_running:
            logger.warning(f"[{self.bot_name}] Watchdog already running")
            return

        self.is_running = True
        self._stop_event.clear()

        # Start heartbeat
        self.heartbeat_manager.start_background()

        # Start watchdog thread
        self._thread = threading.Thread(
            target=self._watchdog_loop,
            daemon=True,
            name=f"watchdog-{self.bot_name}",
        )
        self._thread.start()

        logger.info(f"[{self.bot_name}] Watchdog started")

    def stop(self) -> None:
        """Stop the watchdog."""
        if not self.is_running:
            return

        self.is_running = False
        self._stop_event.set()

        # Stop heartbeat
        self.heartbeat_manager.stop()

        # Wait for thread
        if self._thread:
            self._thread.join(timeout=10)
            self._thread = None

        logger.info(f"[{self.bot_name}] Watchdog stopped")

    def _watchdog_loop(self) -> None:
        """Main watchdog loop running in background thread."""
        while self.is_running and not self._stop_event.is_set():
            try:
                self._run_health_check()
            except Exception as e:
                logger.error(f"[{self.bot_name}] Health check error: {e}")

            # Sleep with interruptible wait
            self._stop_event.wait(timeout=self.config.health_check_interval)

    def _run_health_check(self) -> None:
        """Run a single health check cycle."""
        report = self.health_monitor.get_health_report()

        # Check for memory alert
        if report["memory_exceeded"]:
            self._trigger_alert("HIGH_MEMORY", {
                "memory_mb": report["memory_mb"],
                "threshold_mb": report["memory_threshold_mb"],
            })

        # Check for CPU alert
        if report["cpu_exceeded"]:
            self._trigger_alert("HIGH_CPU", {
                "cpu_percent": report["cpu_percent"],
                "threshold_percent": report["cpu_threshold_percent"],
            })

        # Check for critical status
        if report["status"] == "critical":
            self._trigger_alert("CRITICAL_STATUS", report)

        # Log health status periodically
        logger.debug(
            f"[{self.bot_name}] Health: {report['status']} "
            f"(mem={report['memory_mb']:.1f}MB, cpu={report['cpu_percent']:.1f}%)"
        )

    def _trigger_alert(
        self,
        alert_type: str,
        details: Dict[str, Any],
    ) -> None:
        """Trigger alert callbacks.

        Args:
            alert_type: Type of alert (e.g., "HIGH_MEMORY")
            details: Additional alert details
        """
        # Check cooldown
        now = datetime.now()
        last_alert = self._last_alerts.get(alert_type)
        if last_alert and (now - last_alert).total_seconds() < self._alert_cooldown:
            return  # Skip - still in cooldown

        self._last_alerts[alert_type] = now

        logger.warning(f"[{self.bot_name}] ALERT: {alert_type} - {details}")

        # Call callbacks
        for callback in self._alert_callbacks:
            try:
                callback(alert_type, details)
            except Exception as e:
                logger.error(f"Alert callback failed: {e}")

    def should_restart(self) -> Tuple[bool, str]:
        """Determine if bot should restart.

        Returns:
            Tuple of (should_restart, reason)
        """
        process = self.health_monitor._get_process()
        if process is None:
            return False, "Cannot check process status (psutil unavailable)"

        try:
            if not process.is_running():
                if self.restart_policy.should_restart():
                    return True, "Process is not running (crashed)"
                return False, "Max restart attempts exceeded"
        except Exception as e:
            logger.warning(f"Error checking process: {e}")

        return False, "Process is running normally"

    def check_log_line(self, line: str) -> List[ErrorMatch]:
        """Check a log line for errors.

        Args:
            line: Log line to check

        Returns:
            List of error matches
        """
        return self.error_detector.check_line(line)

    def get_status(self) -> Dict[str, Any]:
        """Get comprehensive watchdog status.

        Returns:
            Dictionary with full status information
        """
        health_report = self.health_monitor.get_health_report()
        error_summary = self.error_detector.get_error_summary()

        return {
            "bot_name": self.bot_name,
            "watchdog_running": self.is_running,
            "restart_count": self.restart_count,
            "health": health_report,
            "errors": error_summary,
            "heartbeat": {
                "last": self.heartbeat_manager.last_heartbeat.isoformat()
                if self.heartbeat_manager.last_heartbeat
                else None,
                "alive": self.heartbeat_manager.is_alive(),
                "seconds_since": self.heartbeat_manager.get_seconds_since_heartbeat(),
            },
        }


# ==============================================================================
# Convenience Functions
# ==============================================================================


def create_watchdog(
    bot_name: str,
    memory_threshold_mb: int = 256,
    cpu_threshold_percent: int = 80,
    heartbeat_interval: int = 30,
    health_check_interval: int = 60,
    max_restart_attempts: int = 3,
    alert_callback: Optional[AlertCallback] = None,
) -> ProcessWatchdog:
    """Create a configured watchdog for a bot.

    Args:
        bot_name: Name of the bot
        memory_threshold_mb: Memory alert threshold
        cpu_threshold_percent: CPU alert threshold
        heartbeat_interval: Seconds between heartbeats
        health_check_interval: Seconds between health checks
        max_restart_attempts: Max restart attempts
        alert_callback: Optional callback for alerts

    Returns:
        Configured ProcessWatchdog instance
    """
    config = SelfHealingConfig(
        bot_name=bot_name,
        memory_threshold_mb=memory_threshold_mb,
        cpu_threshold_percent=cpu_threshold_percent,
        heartbeat_interval=heartbeat_interval,
        health_check_interval=health_check_interval,
        max_restart_attempts=max_restart_attempts,
    )

    watchdog = ProcessWatchdog(config)

    if alert_callback:
        watchdog.on_alert(alert_callback)

    return watchdog


def send_telegram_alert(
    chat_id: str,
    bot_token: str,
    alert_type: str,
    details: Dict[str, Any],
) -> bool:
    """Send alert via Telegram.

    Args:
        chat_id: Telegram chat ID
        bot_token: Bot API token
        alert_type: Type of alert
        details: Alert details

    Returns:
        True if sent successfully
    """
    try:
        import urllib.request
        import urllib.parse

        message = f"ALERT: {alert_type}\n\n"
        for key, value in details.items():
            message += f"- {key}: {value}\n"

        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        data = urllib.parse.urlencode({
            "chat_id": chat_id,
            "text": message,
            "parse_mode": "HTML",
        }).encode()

        req = urllib.request.Request(url, data=data)
        urllib.request.urlopen(req, timeout=10)
        return True

    except Exception as e:
        logger.error(f"Failed to send Telegram alert: {e}")
        return False


# ==============================================================================
# Module Exports
# ==============================================================================


__all__ = [
    # Config
    "SelfHealingConfig",
    "ResourceThresholds",
    "HealthStatus",
    "RestartPolicy",
    # Error Detection
    "ErrorPattern",
    "ErrorMatch",
    "LogErrorDetector",
    # Heartbeat
    "HeartbeatManager",
    # Health Monitor
    "HealthMonitor",
    # Watchdog
    "ProcessWatchdog",
    "AlertCallback",
    "RestartCallback",
    # Convenience
    "create_watchdog",
    "send_telegram_alert",
]
