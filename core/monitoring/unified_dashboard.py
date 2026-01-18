"""
JARVIS Unified Monitoring Dashboard

Comprehensive monitoring system providing:
- Dashboard data collection (trading, bots, performance, logs)
- Alert rules engine with configurable JSON rules
- Alert routing to Telegram/email/logs
- Health check aggregation
- Historical metrics storage with retention
- WebSocket real-time updates
- HTTP endpoints for dashboard
- Sensitive data protection

Usage:
    from core.monitoring.unified_dashboard import create_dashboard_app

    app = create_dashboard_app()
    web.run_app(app, port=8080)
"""

import asyncio
import json
import logging
import os
import re
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set

logger = logging.getLogger("jarvis.monitoring.dashboard")

# =============================================================================
# SENSITIVE DATA PATTERNS - DO NOT EXPOSE
# =============================================================================

SENSITIVE_PATTERNS = [
    r"[0-9a-fA-F]{64}",  # Private keys
    r"sk-[a-zA-Z0-9]{48}",  # OpenAI keys
    r"xai-[a-zA-Z0-9-]+",  # XAI keys
    r"[A-Za-z0-9]{32,44}",  # Solana wallet addresses (approximate)
]

SENSITIVE_KEYS = {
    "private_key", "secret", "password", "api_key", "token", "wallet",
    "WALLET_PRIVATE_KEY", "ANTHROPIC_API_KEY", "XAI_API_KEY", "TELEGRAM_BOT_TOKEN",
}


def sanitize_data(data: Any) -> Any:
    """Remove or mask sensitive data from responses."""
    if isinstance(data, dict):
        result = {}
        for key, value in data.items():
            # Skip sensitive keys entirely
            key_lower = key.lower()
            if any(sensitive in key_lower for sensitive in SENSITIVE_KEYS):
                continue
            # Recursively sanitize
            result[key] = sanitize_data(value)
        return result
    elif isinstance(data, list):
        return [sanitize_data(item) for item in data]
    elif isinstance(data, str):
        # Mask potential sensitive patterns
        for pattern in SENSITIVE_PATTERNS:
            data = re.sub(pattern, "[REDACTED]", data)
        return data
    return data


# =============================================================================
# CONFIGURATION
# =============================================================================

@dataclass
class MonitoringConfig:
    """Monitoring system configuration."""
    enabled: bool = True
    port: int = 8080
    retention_days: int = 30
    metrics_interval_seconds: int = 5
    alert_rules_file: str = "lifeos/config/alert_rules.json"
    slack_webhook: Optional[str] = None
    email_recipients: List[str] = field(default_factory=list)

    @classmethod
    def from_file(cls, path: str) -> "MonitoringConfig":
        """Load config from JSON file."""
        with open(path) as f:
            data = json.load(f)
        return cls(**data)

    @classmethod
    def from_env(cls) -> "MonitoringConfig":
        """Load config from environment variables."""
        return cls(
            enabled=os.getenv("MONITORING_ENABLED", "true").lower() == "true",
            port=int(os.getenv("MONITORING_PORT", "8080")),
            retention_days=int(os.getenv("MONITORING_RETENTION_DAYS", "30")),
            metrics_interval_seconds=int(os.getenv("MONITORING_INTERVAL", "5")),
            alert_rules_file=os.getenv("ALERT_RULES_FILE", "lifeos/config/alert_rules.json"),
            slack_webhook=os.getenv("SLACK_WEBHOOK"),
            email_recipients=os.getenv("EMAIL_RECIPIENTS", "").split(",") if os.getenv("EMAIL_RECIPIENTS") else [],
        )


# =============================================================================
# HELPER FUNCTIONS - Lazy imports to avoid circular dependencies
# =============================================================================

def get_scorekeeper():
    """Get scorekeeper instance (lazy import)."""
    try:
        from bots.treasury.scorekeeper import get_scorekeeper as _get_scorekeeper
        return _get_scorekeeper()
    except ImportError:
        return None


def get_supervisor_status() -> Dict[str, Any]:
    """Get supervisor component status."""
    try:
        # Try to read from supervisor if available
        from bots.supervisor import BotSupervisor
        # This would need the supervisor instance - return empty for now
        return {}
    except ImportError:
        return {}


def get_metrics_collector():
    """Get metrics collector instance (lazy import)."""
    try:
        from core.monitoring.metrics_collector import get_metrics_collector as _get_metrics_collector
        return _get_metrics_collector()
    except ImportError:
        return None


def get_log_aggregator():
    """Get log aggregator instance (lazy import)."""
    try:
        from core.monitoring.log_aggregator import get_log_aggregator as _get_log_aggregator
        return _get_log_aggregator()
    except ImportError:
        return None


# =============================================================================
# DASHBOARD METRICS COLLECTOR
# =============================================================================

class DashboardMetrics:
    """
    Collects and aggregates metrics for the dashboard.

    Metrics collected:
    - Trading: positions, P&L, win rate, drawdown
    - Bots: component status, restarts, errors
    - Performance: latency, CPU, memory
    - Logs: error counts, warnings, recent errors
    """

    def __init__(self, data_dir: str = "data"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)

    async def collect_trading_metrics(self) -> Dict[str, Any]:
        """Collect trading-related metrics."""
        try:
            scorekeeper = get_scorekeeper()
            if not scorekeeper:
                return self._empty_trading_metrics()

            positions = scorekeeper.get_open_positions()
            stats = scorekeeper.get_performance_stats()

            total_notional = sum(
                p.get("amount_usd", 0) for p in positions
            )

            return sanitize_data({
                "active_positions": len(positions),
                "total_notional_usd": total_notional,
                "win_rate": stats.get("win_rate", 0) * 100,
                "total_pnl_usd": stats.get("total_pnl", 0),
                "avg_trade_pnl": stats.get("avg_trade_pnl", 0),
                "sharpe_ratio": stats.get("sharpe_ratio", 0),
                "max_drawdown": stats.get("max_drawdown", 0) * 100,
                "liquidation_risk": self._calculate_liquidation_risk(positions),
            })
        except Exception as e:
            logger.error(f"Error collecting trading metrics: {e}")
            return self._empty_trading_metrics()

    def _empty_trading_metrics(self) -> Dict[str, Any]:
        """Return empty trading metrics."""
        return {
            "active_positions": 0,
            "total_notional_usd": 0,
            "win_rate": 0,
            "total_pnl_usd": 0,
            "avg_trade_pnl": 0,
            "sharpe_ratio": 0,
            "max_drawdown": 0,
            "liquidation_risk": "LOW",
        }

    def _calculate_liquidation_risk(self, positions: List[Dict]) -> str:
        """Calculate overall liquidation risk."""
        if not positions:
            return "LOW"

        high_risk_count = sum(
            1 for p in positions
            if p.get("unrealized_pnl_pct", 0) < -15
        )

        if high_risk_count >= 3:
            return "HIGH"
        elif high_risk_count >= 1:
            return "MEDIUM"
        return "LOW"

    async def collect_bot_metrics(self) -> Dict[str, Any]:
        """Collect bot component metrics."""
        try:
            status = get_supervisor_status()

            return {
                "components": {
                    name: sanitize_data({
                        "status": info.get("status", "unknown"),
                        "uptime": info.get("uptime"),
                        "restart_count": info.get("restart_count", 0),
                        "last_error": info.get("last_error"),
                    })
                    for name, info in status.items()
                }
            }
        except Exception as e:
            logger.error(f"Error collecting bot metrics: {e}")
            return {"components": {}}

    async def collect_performance_metrics(self) -> Dict[str, Any]:
        """Collect performance metrics."""
        try:
            import psutil

            collector = get_metrics_collector()
            latency = None
            if collector:
                latency = collector.get_latency_percentiles("api", window_seconds=300)

            process = psutil.Process()
            memory = psutil.virtual_memory()

            return {
                "api_latency_p50_ms": latency.p50_ms if latency else 0,
                "api_latency_p95_ms": latency.p95_ms if latency else 0,
                "api_latency_p99_ms": latency.p99_ms if latency else 0,
                "cpu_percent": round(psutil.cpu_percent(interval=0.1), 1),
                "memory_mb": round(process.memory_info().rss / 1024 / 1024, 1),
                "memory_total_mb": round(memory.total / 1024 / 1024, 1),
                "memory_percent": round(memory.percent, 1),
            }
        except ImportError:
            return {
                "api_latency_p50_ms": 0,
                "api_latency_p95_ms": 0,
                "api_latency_p99_ms": 0,
                "cpu_percent": 0,
                "memory_mb": 0,
                "memory_total_mb": 0,
                "memory_percent": 0,
            }
        except Exception as e:
            logger.error(f"Error collecting performance metrics: {e}")
            return {}

    async def collect_log_metrics(self) -> Dict[str, Any]:
        """Collect log-related metrics."""
        try:
            aggregator = get_log_aggregator()
            if not aggregator:
                return self._empty_log_metrics()

            stats = aggregator.get_stats(
                start_time=datetime.now(timezone.utc) - timedelta(hours=24)
            )

            by_level = stats.entries_by_level if hasattr(stats, 'entries_by_level') else {}
            top_errors = stats.top_errors if hasattr(stats, 'top_errors') else []

            return {
                "errors_24h": by_level.get("ERROR", 0) + by_level.get("CRITICAL", 0),
                "warnings_24h": by_level.get("WARNING", 0),
                "info_24h": by_level.get("INFO", 0),
                "error_rate_per_minute": getattr(stats, 'error_rate_per_minute', 0),
                "recent_error": top_errors[0]["pattern"] if top_errors else None,
                "top_errors": top_errors[:5],
            }
        except Exception as e:
            logger.error(f"Error collecting log metrics: {e}")
            return self._empty_log_metrics()

    def _empty_log_metrics(self) -> Dict[str, Any]:
        """Return empty log metrics."""
        return {
            "errors_24h": 0,
            "warnings_24h": 0,
            "info_24h": 0,
            "error_rate_per_minute": 0,
            "recent_error": None,
            "top_errors": [],
        }

    async def get_dashboard_data(self) -> Dict[str, Any]:
        """Get complete dashboard data."""
        trading, bots, perf, logs = await asyncio.gather(
            self.collect_trading_metrics(),
            self.collect_bot_metrics(),
            self.collect_performance_metrics(),
            self.collect_log_metrics(),
            return_exceptions=True,
        )

        # Handle exceptions
        if isinstance(trading, Exception):
            trading = self._empty_trading_metrics()
        if isinstance(bots, Exception):
            bots = {"components": {}}
        if isinstance(perf, Exception):
            perf = {}
        if isinstance(logs, Exception):
            logs = self._empty_log_metrics()

        return sanitize_data({
            "trading": trading,
            "bots": bots,
            "performance": perf,
            "logs": logs,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })


# =============================================================================
# ALERT RULE ENGINE
# =============================================================================

class AlertRuleEngine:
    """
    Evaluates alert rules against current metrics.

    Rules are loaded from JSON config and support conditions like:
    - errors_per_hour > 10
    - component.status == 'crashed'
    - portfolio.drawdown < -20
    """

    def __init__(self, rules_file: str = None, rules: List[Dict] = None):
        self.rules: List[Dict] = []
        self._cooldowns: Dict[str, datetime] = {}

        if rules:
            self.rules = rules
        elif rules_file and Path(rules_file).exists():
            self._load_rules(rules_file)

    def _load_rules(self, rules_file: str):
        """Load rules from JSON file."""
        try:
            with open(rules_file) as f:
                data = json.load(f)
            self.rules = data.get("rules", [])
            logger.info(f"Loaded {len(self.rules)} alert rules from {rules_file}")
        except Exception as e:
            logger.error(f"Failed to load alert rules: {e}")
            self.rules = []

    def evaluate_rules(self, context: Dict[str, Any]) -> List[Dict]:
        """
        Evaluate all rules against current context.

        Args:
            context: Dictionary with current metric values

        Returns:
            List of triggered rules
        """
        triggered = []

        for rule in self.rules:
            rule_id = rule.get("id", "unknown")

            # Check cooldown
            if rule_id in self._cooldowns:
                if datetime.now(timezone.utc) < self._cooldowns[rule_id]:
                    continue

            try:
                if self._evaluate_condition(rule.get("condition", ""), context):
                    triggered.append(rule)
                    # Set cooldown (default 15 minutes)
                    cooldown_minutes = rule.get("cooldown_minutes", 15)
                    self._cooldowns[rule_id] = datetime.now(timezone.utc) + timedelta(minutes=cooldown_minutes)
            except Exception as e:
                logger.debug(f"Rule evaluation error for {rule_id}: {e}")

        return triggered

    def _evaluate_condition(self, condition: str, context: Dict[str, Any]) -> bool:
        """
        Evaluate a condition string against context.

        Supports simple expressions like:
        - "errors_per_hour > 10"
        - "component.status == 'crashed'"
        - "portfolio.drawdown < -20"
        """
        if not condition:
            return False

        # Parse condition
        # Handle comparison operators
        for op in ["==", "!=", ">=", "<=", ">", "<"]:
            if op in condition:
                left, right = condition.split(op, 1)
                left = left.strip()
                right = right.strip()

                left_val = self._get_value(left, context)
                right_val = self._parse_value(right)

                if left_val is None:
                    return False

                if op == "==":
                    return left_val == right_val
                elif op == "!=":
                    return left_val != right_val
                elif op == ">=":
                    return left_val >= right_val
                elif op == "<=":
                    return left_val <= right_val
                elif op == ">":
                    return left_val > right_val
                elif op == "<":
                    return left_val < right_val

        return False

    def _get_value(self, path: str, context: Dict[str, Any]) -> Any:
        """Get value from context using dot notation path."""
        parts = path.split(".")
        value = context

        for part in parts:
            if isinstance(value, dict):
                value = value.get(part)
            else:
                return None

            if value is None:
                return None

        return value

    def _parse_value(self, value_str: str) -> Any:
        """Parse a value string into appropriate type."""
        value_str = value_str.strip()

        # String literal
        if value_str.startswith("'") and value_str.endswith("'"):
            return value_str[1:-1]
        if value_str.startswith('"') and value_str.endswith('"'):
            return value_str[1:-1]

        # Boolean
        if value_str.lower() == "true":
            return True
        if value_str.lower() == "false":
            return False

        # Number
        try:
            if "." in value_str:
                return float(value_str)
            return int(value_str)
        except ValueError:
            return value_str


# =============================================================================
# ALERT ROUTER
# =============================================================================

class AlertRouter:
    """
    Routes alerts to appropriate notification channels.

    Supported channels:
    - telegram: Send to admin Telegram
    - email: Send email (if configured)
    - log: Log to system logger
    - dashboard: Store for dashboard display
    """

    def __init__(self):
        self._active_alerts: List[Dict] = []
        self._alert_history: deque = deque(maxlen=1000)

    async def route_alert(self, alert: Dict) -> bool:
        """Route alert to appropriate channels."""
        actions = alert.get("actions", ["log"])
        success = True

        for action in actions:
            try:
                if action == "telegram":
                    success = await self._send_telegram(alert) and success
                elif action == "email":
                    success = await self._send_email(alert) and success
                elif action == "log":
                    self._log_alert(alert)
                elif action == "dashboard":
                    self._add_to_dashboard(alert)
            except Exception as e:
                logger.error(f"Alert routing error for {action}: {e}")
                success = False

        # Always add to history
        self._alert_history.append({
            **alert,
            "routed_at": datetime.now(timezone.utc).isoformat(),
        })

        return success

    async def _send_telegram(self, alert: Dict) -> bool:
        """Send alert to Telegram."""
        try:
            import aiohttp

            token = os.environ.get("TELEGRAM_BOT_TOKEN")
            admin_ids = os.environ.get("TELEGRAM_ADMIN_IDS", "")

            if not token or not admin_ids:
                logger.debug("Telegram not configured for alerts")
                return True

            admin_list = [x.strip() for x in admin_ids.split(",") if x.strip().isdigit()]
            if not admin_list:
                return True

            severity = alert.get("severity", "info")
            emoji = {
                "info": "i",
                "warning": "(!)",
                "error": "[!]",
                "critical": "[!!!]",
            }.get(severity, "")

            message = (
                f"{emoji} <b>Alert: {alert.get('id', 'unknown')}</b>\n\n"
                f"<b>Severity:</b> {severity}\n"
                f"<b>Message:</b> {alert.get('message', 'No message')}\n"
                f"<b>Time:</b> {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}"
            )

            async with aiohttp.ClientSession() as session:
                for admin_id in admin_list[:3]:
                    url = f"https://api.telegram.org/bot{token}/sendMessage"
                    await session.post(url, json={
                        "chat_id": admin_id,
                        "text": message,
                        "parse_mode": "HTML",
                    })

            return True

        except Exception as e:
            logger.error(f"Telegram alert failed: {e}")
            return False

    async def _send_email(self, alert: Dict) -> bool:
        """Send alert via email."""
        # Placeholder for email integration
        logger.info(f"Email alert (not configured): {alert.get('id')}")
        return True

    def _log_alert(self, alert: Dict):
        """Log alert to system logger."""
        severity = alert.get("severity", "info")
        message = f"Alert [{alert.get('id')}]: {alert.get('message', 'No message')}"

        if severity == "critical":
            logger.critical(message)
        elif severity == "error":
            logger.error(message)
        elif severity == "warning":
            logger.warning(message)
        else:
            logger.info(message)

    def _add_to_dashboard(self, alert: Dict):
        """Add alert to dashboard display."""
        self._active_alerts.append({
            **alert,
            "created_at": datetime.now(timezone.utc).isoformat(),
        })

        # Keep only last 50 active alerts
        if len(self._active_alerts) > 50:
            self._active_alerts = self._active_alerts[-50:]

    def get_active_alerts(self) -> List[Dict]:
        """Get currently active alerts."""
        return self._active_alerts.copy()

    def get_alert_history(self, limit: int = 50) -> List[Dict]:
        """Get alert history."""
        return list(self._alert_history)[-limit:]


# =============================================================================
# HEALTH CHECK AGGREGATOR
# =============================================================================

class HealthCheckAggregator:
    """
    Aggregates health checks from all components.

    Components checked:
    - buy_bot: Process running + recent activity
    - sentiment_reporter: Scheduled jobs running
    - twitter_poster: Last tweet time
    - telegram_bot: Message count (24h)
    - trading_engine: Last trade time
    """

    def __init__(self):
        self._last_checks: Dict[str, Dict] = {}

    async def check_component(self, component: str) -> Dict[str, Any]:
        """Check health of a specific component."""
        try:
            status = get_supervisor_status()
            comp_status = status.get(component, {})

            if not comp_status:
                return {
                    "component": component,
                    "status": "unknown",
                    "message": "Component not found in supervisor",
                }

            status_val = comp_status.get("status", "unknown")
            restart_count = comp_status.get("restart_count", 0)

            # Determine health status
            if status_val == "running" and restart_count < 5:
                health = "healthy"
            elif status_val == "running":
                health = "degraded"
            else:
                health = "unhealthy"

            result = {
                "component": component,
                "status": health,
                "component_status": status_val,
                "restart_count": restart_count,
                "uptime": comp_status.get("uptime"),
                "message": comp_status.get("last_error"),
            }

            self._last_checks[component] = result
            return result

        except Exception as e:
            return {
                "component": component,
                "status": "unknown",
                "message": str(e),
            }

    async def get_overall_health(self) -> Dict[str, Any]:
        """Get aggregated health status."""
        status = get_supervisor_status()

        components = {}
        healthy_count = 0
        degraded_count = 0
        unhealthy_count = 0

        for name in status.keys():
            comp_health = await self.check_component(name)
            components[name] = comp_health

            if comp_health["status"] == "healthy":
                healthy_count += 1
            elif comp_health["status"] == "degraded":
                degraded_count += 1
            else:
                unhealthy_count += 1

        # Determine overall status
        if unhealthy_count > 0:
            overall = "unhealthy" if unhealthy_count > degraded_count + healthy_count else "degraded"
        elif degraded_count > 0:
            overall = "degraded"
        elif healthy_count > 0:
            overall = "healthy"
        else:
            overall = "unknown"

        return {
            "status": overall,
            "components": components,
            "summary": {
                "healthy": healthy_count,
                "degraded": degraded_count,
                "unhealthy": unhealthy_count,
            },
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }


# =============================================================================
# METRICS STORE
# =============================================================================

class MetricsStore:
    """
    Stores historical metrics for querying.

    Features:
    - In-memory buffer for recent data
    - Persistent JSONL files for history
    - Configurable retention period
    """

    def __init__(self, data_dir: str = "data", retention_days: int = 30):
        self.data_dir = Path(data_dir)
        self.metrics_dir = self.data_dir / "metrics"
        self.metrics_dir.mkdir(parents=True, exist_ok=True)
        self.retention_days = retention_days

        # In-memory buffer
        self._buffer: Dict[str, deque] = {}
        self._buffer_size = 1000

    def record(self, metric: str, value: float, metadata: Dict = None):
        """Record a metric value."""
        if metric not in self._buffer:
            self._buffer[metric] = deque(maxlen=self._buffer_size)

        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "metric": metric,
            "value": value,
            "metadata": metadata or {},
        }

        self._buffer[metric].append(entry)

    def get_recent(self, metric: str, minutes: int = 5) -> List[Dict]:
        """Get recent metric values."""
        if metric not in self._buffer:
            return []

        cutoff = datetime.now(timezone.utc) - timedelta(minutes=minutes)

        return [
            entry for entry in self._buffer[metric]
            if datetime.fromisoformat(entry["timestamp"]) > cutoff
        ]

    def get_history(self, metric: str, days: int = 1) -> List[Dict]:
        """Get historical metric values."""
        results = []

        # Get from buffer first
        if metric in self._buffer:
            results.extend(self._buffer[metric])

        # Load from files if needed
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)

        for file in sorted(self.metrics_dir.glob("*.jsonl")):
            try:
                with open(file) as f:
                    for line in f:
                        entry = json.loads(line)
                        if entry.get("metric") == metric:
                            ts = datetime.fromisoformat(entry["timestamp"])
                            if ts > cutoff:
                                results.append(entry)
            except Exception:
                continue

        # Sort by timestamp
        results.sort(key=lambda x: x["timestamp"])
        return results

    def flush(self):
        """Flush buffer to disk."""
        if not any(self._buffer.values()):
            return

        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        file_path = self.metrics_dir / f"metrics_{timestamp}.jsonl"

        with open(file_path, "w") as f:
            for metric_buffer in self._buffer.values():
                for entry in metric_buffer:
                    f.write(json.dumps(entry) + "\n")

        # Clear buffers
        for buffer in self._buffer.values():
            buffer.clear()

    def cleanup_old_data(self):
        """Remove data older than retention period."""
        cutoff = time.time() - (self.retention_days * 24 * 60 * 60)

        for file in self.metrics_dir.glob("*.jsonl"):
            try:
                if file.stat().st_mtime < cutoff:
                    file.unlink()
                    logger.debug(f"Deleted old metrics file: {file}")
            except Exception as e:
                logger.error(f"Error cleaning up {file}: {e}")


# =============================================================================
# WEBSOCKET MANAGER
# =============================================================================

class WebSocketManager:
    """Manages WebSocket connections for real-time updates."""

    def __init__(self):
        self.clients: Set = set()

    async def connect(self, websocket):
        """Register new client connection."""
        self.clients.add(websocket)
        logger.debug(f"WebSocket client connected. Total: {len(self.clients)}")

    async def disconnect(self, websocket):
        """Remove client connection."""
        self.clients.discard(websocket)
        logger.debug(f"WebSocket client disconnected. Total: {len(self.clients)}")

    async def broadcast(self, data: Dict):
        """Broadcast data to all connected clients."""
        if not self.clients:
            return

        # Sanitize before sending
        safe_data = sanitize_data(data)

        disconnected = set()
        for client in self.clients:
            try:
                await client.send_json(safe_data)
            except Exception:
                disconnected.add(client)

        # Remove disconnected clients
        self.clients -= disconnected


# =============================================================================
# HTTP SERVER
# =============================================================================

def create_dashboard_app(
    data_dir: str = "data",
    config_dir: str = "lifeos/config",
) -> "web.Application":
    """
    Create the dashboard web application.

    Endpoints:
    - GET / : Dashboard HTML page
    - GET /health : System health status
    - GET /metrics/trading : Trading metrics
    - GET /metrics/bots : Bot component status
    - GET /metrics/performance : Performance stats
    - GET /metrics/logs : Log statistics
    - GET /metrics/history : Historical metrics
    - GET /alerts : Active alerts and rules
    - WS /ws/metrics : Real-time metrics stream
    """
    try:
        from aiohttp import web
    except ImportError:
        raise ImportError("aiohttp is required for the dashboard server")

    app = web.Application()

    # Initialize components
    metrics = DashboardMetrics(data_dir=data_dir)
    rule_engine = AlertRuleEngine(rules_file=f"{config_dir}/alert_rules.json")
    alert_router = AlertRouter()
    health_aggregator = HealthCheckAggregator()
    metrics_store = MetricsStore(data_dir=data_dir)
    ws_manager = WebSocketManager()

    # Store in app state
    app["metrics"] = metrics
    app["rule_engine"] = rule_engine
    app["alert_router"] = alert_router
    app["health_aggregator"] = health_aggregator
    app["metrics_store"] = metrics_store
    app["ws_manager"] = ws_manager

    # Routes
    async def index_handler(request):
        """Serve dashboard HTML."""
        html = _get_dashboard_html()
        return web.Response(text=html, content_type="text/html")

    async def health_handler(request):
        """Health check endpoint."""
        health = await app["health_aggregator"].get_overall_health()
        status_code = 200 if health["status"] in ["healthy", "degraded"] else 503
        return web.json_response(health, status=status_code)

    async def trading_metrics_handler(request):
        """Trading metrics endpoint."""
        data = await app["metrics"].collect_trading_metrics()
        return web.json_response(data)

    async def bots_metrics_handler(request):
        """Bot metrics endpoint."""
        data = await app["metrics"].collect_bot_metrics()
        return web.json_response(data)

    async def performance_metrics_handler(request):
        """Performance metrics endpoint."""
        data = await app["metrics"].collect_performance_metrics()
        return web.json_response(data)

    async def logs_metrics_handler(request):
        """Log metrics endpoint."""
        data = await app["metrics"].collect_log_metrics()
        return web.json_response(data)

    async def history_handler(request):
        """Historical metrics endpoint."""
        metric = request.query.get("metric", "")
        days = int(request.query.get("days", "7"))

        data = app["metrics_store"].get_history(metric, days=days)
        return web.json_response({
            "metric": metric,
            "days": days,
            "data": data,
        })

    async def alerts_handler(request):
        """Alerts endpoint."""
        return web.json_response({
            "active_alerts": app["alert_router"].get_active_alerts(),
            "rules": app["rule_engine"].rules,
            "history": app["alert_router"].get_alert_history(),
        })

    async def websocket_handler(request):
        """WebSocket endpoint for real-time updates."""
        ws = web.WebSocketResponse()
        await ws.prepare(request)

        await app["ws_manager"].connect(ws)

        try:
            async for msg in ws:
                # Handle incoming messages if needed
                pass
        finally:
            await app["ws_manager"].disconnect(ws)

        return ws

    # Register routes
    app.router.add_get("/", index_handler)
    app.router.add_get("/health", health_handler)
    app.router.add_get("/metrics/trading", trading_metrics_handler)
    app.router.add_get("/metrics/bots", bots_metrics_handler)
    app.router.add_get("/metrics/performance", performance_metrics_handler)
    app.router.add_get("/metrics/logs", logs_metrics_handler)
    app.router.add_get("/metrics/history", history_handler)
    app.router.add_get("/alerts", alerts_handler)
    app.router.add_get("/ws/metrics", websocket_handler)

    return app


def _get_dashboard_html() -> str:
    """Return the dashboard HTML template."""
    return """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>JARVIS Monitoring Dashboard</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #0a0a0f;
            color: #e0e0e0;
            padding: 20px;
        }
        .header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 30px;
            padding-bottom: 20px;
            border-bottom: 1px solid #333;
        }
        h1 { color: #00d4ff; font-size: 28px; }
        .status-badge {
            padding: 8px 16px;
            border-radius: 20px;
            font-weight: bold;
            text-transform: uppercase;
        }
        .status-healthy { background: #10b981; color: white; }
        .status-degraded { background: #f59e0b; color: black; }
        .status-unhealthy { background: #ef4444; color: white; }
        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
            gap: 20px;
        }
        .card {
            background: #1a1a2e;
            border-radius: 12px;
            padding: 20px;
            border: 1px solid #333;
        }
        .card h2 {
            color: #00d4ff;
            font-size: 18px;
            margin-bottom: 15px;
            display: flex;
            align-items: center;
            gap: 10px;
        }
        .metric-row {
            display: flex;
            justify-content: space-between;
            padding: 10px 0;
            border-bottom: 1px solid #222;
        }
        .metric-row:last-child { border-bottom: none; }
        .metric-label { color: #888; }
        .metric-value { font-weight: bold; font-family: monospace; }
        .metric-value.positive { color: #10b981; }
        .metric-value.negative { color: #ef4444; }
        .component-status {
            display: flex;
            align-items: center;
            gap: 10px;
            padding: 8px 0;
        }
        .status-dot {
            width: 10px;
            height: 10px;
            border-radius: 50%;
        }
        .status-dot.running { background: #10b981; }
        .status-dot.stopped { background: #ef4444; }
        .status-dot.warning { background: #f59e0b; }
        .alert-item {
            background: #2a2a3e;
            padding: 12px;
            border-radius: 8px;
            margin-bottom: 10px;
        }
        .alert-critical { border-left: 4px solid #ef4444; }
        .alert-warning { border-left: 4px solid #f59e0b; }
        .timestamp { color: #666; font-size: 12px; margin-top: 10px; }
        #last-update { color: #666; font-size: 14px; }
    </style>
</head>
<body>
    <div class="header">
        <h1>JARVIS Monitoring Dashboard</h1>
        <div>
            <span id="system-status" class="status-badge status-healthy">HEALTHY</span>
            <span id="last-update">Last update: --</span>
        </div>
    </div>

    <div class="grid">
        <!-- Trading Metrics -->
        <div class="card">
            <h2>Trading</h2>
            <div class="metric-row">
                <span class="metric-label">Active Positions</span>
                <span class="metric-value" id="active-positions">--</span>
            </div>
            <div class="metric-row">
                <span class="metric-label">Total Notional (USD)</span>
                <span class="metric-value" id="total-notional">--</span>
            </div>
            <div class="metric-row">
                <span class="metric-label">Win Rate</span>
                <span class="metric-value" id="win-rate">--</span>
            </div>
            <div class="metric-row">
                <span class="metric-label">Total P&L (USD)</span>
                <span class="metric-value" id="total-pnl">--</span>
            </div>
            <div class="metric-row">
                <span class="metric-label">Sharpe Ratio</span>
                <span class="metric-value" id="sharpe-ratio">--</span>
            </div>
            <div class="metric-row">
                <span class="metric-label">Max Drawdown</span>
                <span class="metric-value" id="max-drawdown">--</span>
            </div>
            <div class="metric-row">
                <span class="metric-label">Liquidation Risk</span>
                <span class="metric-value" id="liquidation-risk">--</span>
            </div>
        </div>

        <!-- Bot Status -->
        <div class="card">
            <h2>Bot Components</h2>
            <div id="bot-components">
                <div class="component-status">
                    <span class="status-dot running"></span>
                    <span>Loading...</span>
                </div>
            </div>
        </div>

        <!-- Performance -->
        <div class="card">
            <h2>Performance</h2>
            <div class="metric-row">
                <span class="metric-label">API Latency (P95)</span>
                <span class="metric-value" id="api-latency">--</span>
            </div>
            <div class="metric-row">
                <span class="metric-label">CPU Usage</span>
                <span class="metric-value" id="cpu-usage">--</span>
            </div>
            <div class="metric-row">
                <span class="metric-label">Memory Usage</span>
                <span class="metric-value" id="memory-usage">--</span>
            </div>
        </div>

        <!-- Logs -->
        <div class="card">
            <h2>Logging (24h)</h2>
            <div class="metric-row">
                <span class="metric-label">Errors</span>
                <span class="metric-value negative" id="error-count">--</span>
            </div>
            <div class="metric-row">
                <span class="metric-label">Warnings</span>
                <span class="metric-value" id="warning-count">--</span>
            </div>
            <div class="metric-row">
                <span class="metric-label">Recent Error</span>
                <span class="metric-value" id="recent-error">--</span>
            </div>
        </div>

        <!-- Alerts -->
        <div class="card">
            <h2>Active Alerts</h2>
            <div id="alerts-list">
                <p style="color: #666;">No active alerts</p>
            </div>
        </div>
    </div>

    <div class="timestamp">
        Dashboard refreshes every 5 seconds. WebSocket connection: <span id="ws-status">Connecting...</span>
    </div>

    <script>
        let ws;

        function connectWebSocket() {
            const wsUrl = `ws://${window.location.host}/ws/metrics`;
            ws = new WebSocket(wsUrl);

            ws.onopen = () => {
                document.getElementById('ws-status').textContent = 'Connected';
            };

            ws.onclose = () => {
                document.getElementById('ws-status').textContent = 'Disconnected - Reconnecting...';
                setTimeout(connectWebSocket, 3000);
            };

            ws.onmessage = (event) => {
                const data = JSON.parse(event.data);
                updateDashboard(data);
            };
        }

        function updateDashboard(data) {
            // Update timestamp
            document.getElementById('last-update').textContent =
                'Last update: ' + new Date().toLocaleTimeString();

            // Update trading metrics
            if (data.trading) {
                document.getElementById('active-positions').textContent = data.trading.active_positions || 0;
                document.getElementById('total-notional').textContent = '$' + (data.trading.total_notional_usd || 0).toLocaleString();
                document.getElementById('win-rate').textContent = (data.trading.win_rate || 0).toFixed(1) + '%';

                const pnl = data.trading.total_pnl_usd || 0;
                const pnlEl = document.getElementById('total-pnl');
                pnlEl.textContent = (pnl >= 0 ? '+' : '') + '$' + pnl.toFixed(2);
                pnlEl.className = 'metric-value ' + (pnl >= 0 ? 'positive' : 'negative');

                document.getElementById('sharpe-ratio').textContent = (data.trading.sharpe_ratio || 0).toFixed(2);
                document.getElementById('max-drawdown').textContent = (data.trading.max_drawdown || 0).toFixed(1) + '%';
                document.getElementById('liquidation-risk').textContent = data.trading.liquidation_risk || 'LOW';
            }

            // Update bot components
            if (data.bots && data.bots.components) {
                const container = document.getElementById('bot-components');
                container.innerHTML = '';

                for (const [name, info] of Object.entries(data.bots.components)) {
                    const status = info.status || 'unknown';
                    const dotClass = status === 'running' ? 'running' :
                                    status === 'stopped' ? 'stopped' : 'warning';

                    container.innerHTML += `
                        <div class="component-status">
                            <span class="status-dot ${dotClass}"></span>
                            <span>${name}: ${status}</span>
                            ${info.restart_count > 0 ? `<span style="color: #f59e0b">(${info.restart_count} restarts)</span>` : ''}
                        </div>
                    `;
                }
            }

            // Update performance
            if (data.performance) {
                document.getElementById('api-latency').textContent =
                    (data.performance.api_latency_p95_ms || 0).toFixed(0) + 'ms';
                document.getElementById('cpu-usage').textContent =
                    (data.performance.cpu_percent || 0).toFixed(1) + '%';
                document.getElementById('memory-usage').textContent =
                    (data.performance.memory_mb || 0).toFixed(0) + 'MB / ' +
                    (data.performance.memory_total_mb || 0).toFixed(0) + 'MB';
            }

            // Update logs
            if (data.logs) {
                document.getElementById('error-count').textContent = data.logs.errors_24h || 0;
                document.getElementById('warning-count').textContent = data.logs.warnings_24h || 0;
                document.getElementById('recent-error').textContent =
                    data.logs.recent_error || 'None';
            }
        }

        // Initial data fetch
        async function fetchData() {
            try {
                const [trading, bots, perf, logs, health] = await Promise.all([
                    fetch('/metrics/trading').then(r => r.json()),
                    fetch('/metrics/bots').then(r => r.json()),
                    fetch('/metrics/performance').then(r => r.json()),
                    fetch('/metrics/logs').then(r => r.json()),
                    fetch('/health').then(r => r.json()),
                ]);

                updateDashboard({ trading, bots, performance: perf, logs });

                // Update system status
                const statusEl = document.getElementById('system-status');
                statusEl.textContent = health.status.toUpperCase();
                statusEl.className = 'status-badge status-' + health.status;
            } catch (e) {
                console.error('Failed to fetch data:', e);
            }
        }

        // Initialize
        fetchData();
        setInterval(fetchData, 5000);
        connectWebSocket();
    </script>
</body>
</html>
"""


# =============================================================================
# STARTUP SCRIPT
# =============================================================================

async def start_dashboard(
    port: int = 8080,
    data_dir: str = "data",
    config_dir: str = "lifeos/config",
):
    """Start the dashboard server."""
    try:
        from aiohttp import web
    except ImportError:
        logger.error("aiohttp is required: pip install aiohttp")
        return

    app = create_dashboard_app(data_dir=data_dir, config_dir=config_dir)

    runner = web.AppRunner(app)
    await runner.setup()

    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()

    logger.info(f"Dashboard started on http://localhost:{port}")

    # Start metrics broadcast loop
    async def broadcast_loop():
        while True:
            try:
                data = await app["metrics"].get_dashboard_data()
                await app["ws_manager"].broadcast(data)

                # Store metrics for history
                if "trading" in data:
                    app["metrics_store"].record("win_rate", data["trading"].get("win_rate", 0))
                    app["metrics_store"].record("total_pnl", data["trading"].get("total_pnl_usd", 0))

                # Check alert rules
                context = {
                    "errors_per_hour": data.get("logs", {}).get("errors_24h", 0) / 24,
                    "portfolio": {"drawdown": data.get("trading", {}).get("max_drawdown", 0)},
                    "api_latency_p95": data.get("performance", {}).get("api_latency_p95_ms", 0),
                }

                for comp_name, comp_data in data.get("bots", {}).get("components", {}).items():
                    context["component"] = comp_data
                    triggered = app["rule_engine"].evaluate_rules(context)
                    for rule in triggered:
                        await app["alert_router"].route_alert(rule)

            except Exception as e:
                logger.error(f"Broadcast loop error: {e}")

            await asyncio.sleep(5)

    asyncio.create_task(broadcast_loop())

    return runner


# =============================================================================
# SINGLETON
# =============================================================================

_dashboard_metrics: Optional[DashboardMetrics] = None


def get_dashboard_metrics() -> DashboardMetrics:
    """Get or create dashboard metrics singleton."""
    global _dashboard_metrics
    if _dashboard_metrics is None:
        _dashboard_metrics = DashboardMetrics()
    return _dashboard_metrics
