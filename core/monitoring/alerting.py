"""Alerting system for critical events."""
import asyncio
import time
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum
import logging
import json

logger = logging.getLogger(__name__)


class AlertSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class AlertStatus(str, Enum):
    FIRING = "firing"
    RESOLVED = "resolved"
    SILENCED = "silenced"


@dataclass
class Alert:
    """An alert instance."""
    id: str
    name: str
    severity: AlertSeverity
    message: str
    status: AlertStatus = AlertStatus.FIRING
    labels: Dict[str, str] = field(default_factory=dict)
    annotations: Dict[str, str] = field(default_factory=dict)
    fired_at: float = field(default_factory=time.time)
    resolved_at: Optional[float] = None
    
    def resolve(self):
        self.status = AlertStatus.RESOLVED
        self.resolved_at = time.time()
    
    def silence(self):
        self.status = AlertStatus.SILENCED


@dataclass
class AlertRule:
    """Definition of an alert rule."""
    name: str
    condition: Callable[[], bool]
    severity: AlertSeverity
    message_template: str
    labels: Dict[str, str] = field(default_factory=dict)
    for_duration: float = 0  # seconds to wait before firing
    cooldown: float = 300  # seconds between alerts
    
    _pending_since: Optional[float] = field(default=None, repr=False)
    _last_fired: float = field(default=0, repr=False)


class AlertManager:
    """Manage alert rules and notifications."""
    
    def __init__(self):
        self.rules: Dict[str, AlertRule] = {}
        self.active_alerts: Dict[str, Alert] = {}
        self.alert_history: List[Alert] = []
        self._notifiers: List[Callable[[Alert], None]] = []
        self._silences: Dict[str, float] = {}  # rule_name -> until timestamp
    
    def add_rule(self, rule: AlertRule):
        """Add an alert rule."""
        self.rules[rule.name] = rule
        logger.info(f"Added alert rule: {rule.name}")
    
    def remove_rule(self, name: str):
        """Remove an alert rule."""
        self.rules.pop(name, None)
    
    def add_notifier(self, notifier: Callable[[Alert], None]):
        """Add a notification handler."""
        self._notifiers.append(notifier)
    
    def silence(self, rule_name: str, duration: float):
        """Silence a rule for specified duration."""
        self._silences[rule_name] = time.time() + duration
        
        # Silence existing alert
        if rule_name in self.active_alerts:
            self.active_alerts[rule_name].silence()
    
    def evaluate(self) -> List[Alert]:
        """Evaluate all rules and return new alerts."""
        new_alerts = []
        now = time.time()
        
        for name, rule in self.rules.items():
            # Check silence
            if name in self._silences and self._silences[name] > now:
                continue
            
            # Check cooldown
            if now - rule._last_fired < rule.cooldown:
                continue
            
            try:
                condition_met = rule.condition()
            except Exception as e:
                logger.error(f"Error evaluating rule {name}: {e}")
                continue
            
            if condition_met:
                # Check for_duration
                if rule.for_duration > 0:
                    if rule._pending_since is None:
                        rule._pending_since = now
                        continue
                    elif now - rule._pending_since < rule.for_duration:
                        continue
                
                # Fire alert
                if name not in self.active_alerts:
                    alert = Alert(
                        id=f"{name}_{int(now)}",
                        name=name,
                        severity=rule.severity,
                        message=rule.message_template,
                        labels=rule.labels.copy()
                    )
                    
                    self.active_alerts[name] = alert
                    self.alert_history.append(alert)
                    rule._last_fired = now
                    rule._pending_since = None
                    
                    new_alerts.append(alert)
                    self._notify(alert)
            else:
                # Resolve if previously firing
                rule._pending_since = None
                if name in self.active_alerts:
                    alert = self.active_alerts.pop(name)
                    alert.resolve()
        
        return new_alerts
    
    def _notify(self, alert: Alert):
        """Send notifications for an alert."""
        for notifier in self._notifiers:
            try:
                notifier(alert)
            except Exception as e:
                logger.error(f"Notifier error: {e}")
    
    def get_active_alerts(self) -> List[Alert]:
        """Get all active alerts."""
        return list(self.active_alerts.values())
    
    def get_alert_history(self, limit: int = 100) -> List[Alert]:
        """Get recent alert history."""
        return self.alert_history[-limit:]


# Notifier implementations
def log_notifier(alert: Alert):
    """Log alerts to standard logger."""
    level = {
        AlertSeverity.INFO: logging.INFO,
        AlertSeverity.WARNING: logging.WARNING,
        AlertSeverity.ERROR: logging.ERROR,
        AlertSeverity.CRITICAL: logging.CRITICAL
    }.get(alert.severity, logging.WARNING)
    
    logger.log(level, f"ALERT [{alert.severity.value}] {alert.name}: {alert.message}")


def webhook_notifier(url: str):
    """Create a webhook notifier."""
    import aiohttp
    
    async def notify(alert: Alert):
        payload = {
            "id": alert.id,
            "name": alert.name,
            "severity": alert.severity.value,
            "message": alert.message,
            "status": alert.status.value,
            "labels": alert.labels,
            "fired_at": alert.fired_at
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                await session.post(url, json=payload, timeout=10)
        except Exception as e:
            logger.error(f"Webhook notification failed: {e}")
    
    def sync_notify(alert: Alert):
        asyncio.create_task(notify(alert))
    
    return sync_notify


def file_notifier(path: str = "logs/alerts.jsonl"):
    """Create a file notifier."""
    from pathlib import Path
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    
    def notify(alert: Alert):
        entry = {
            "timestamp": time.time(),
            "id": alert.id,
            "name": alert.name,
            "severity": alert.severity.value,
            "message": alert.message,
            "status": alert.status.value
        }
        with open(path, "a") as f:
            f.write(json.dumps(entry) + "\n")
    
    return notify


# Global alert manager
alert_manager = AlertManager()
alert_manager.add_notifier(log_notifier)


# Pre-defined alert rules
def create_default_rules():
    """Create default alert rules."""
    from core.monitoring.metrics import metrics
    
    # High error rate
    alert_manager.add_rule(AlertRule(
        name="high_error_rate",
        condition=lambda: False,  # Implement actual check
        severity=AlertSeverity.ERROR,
        message_template="Error rate exceeded threshold",
        for_duration=60,
        cooldown=300
    ))
    
    # High latency
    alert_manager.add_rule(AlertRule(
        name="high_latency",
        condition=lambda: False,
        severity=AlertSeverity.WARNING,
        message_template="API latency exceeded threshold",
        for_duration=120,
        cooldown=600
    ))
    
    # Provider failures
    alert_manager.add_rule(AlertRule(
        name="provider_down",
        condition=lambda: False,
        severity=AlertSeverity.CRITICAL,
        message_template="AI provider unavailable",
        for_duration=30,
        cooldown=300
    ))
