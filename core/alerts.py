"""
Alert System - Price alerts, notifications, and scheduled messages.
"""

import asyncio
import logging
import json
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone, timedelta
from pathlib import Path
from enum import Enum

logger = logging.getLogger(__name__)


class AlertType(Enum):
    """Types of alerts."""
    PRICE_ABOVE = "price_above"
    PRICE_BELOW = "price_below"
    PRICE_CHANGE_PERCENT = "price_change_percent"
    VOLUME_SPIKE = "volume_spike"
    CUSTOM = "custom"


class AlertStatus(Enum):
    """Alert status."""
    ACTIVE = "active"
    TRIGGERED = "triggered"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


@dataclass
class Alert:
    """An alert definition."""
    id: str
    user_id: str
    alert_type: AlertType
    token_symbol: str
    token_mint: str
    condition_value: float
    message: str = ""
    status: AlertStatus = AlertStatus.ACTIVE
    created_at: str = ""
    triggered_at: Optional[str] = None
    expires_at: Optional[str] = None
    repeat: bool = False
    cooldown_minutes: int = 60
    last_trigger: Optional[str] = None


class AlertManager:
    """
    Manage price and custom alerts.

    Usage:
        manager = AlertManager()

        # Create alert
        alert_id = manager.create_alert(
            user_id="123",
            alert_type=AlertType.PRICE_ABOVE,
            token_symbol="$SOL",
            token_mint="So11...",
            condition_value=200.0,
            message="SOL hit $200!"
        )

        # Check alerts against current prices
        triggered = await manager.check_alerts({"So11...": 205.0})
    """

    def __init__(self, storage_path: Optional[Path] = None):
        self.storage_path = storage_path or Path(__file__).parent.parent / "data" / "alerts.json"
        self.alerts: Dict[str, Alert] = {}
        self._callbacks: List[Callable] = []
        self._load()

    def _load(self):
        """Load alerts from storage."""
        if self.storage_path.exists():
            try:
                with open(self.storage_path) as f:
                    data = json.load(f)
                    for alert_data in data.get("alerts", []):
                        alert_data["alert_type"] = AlertType(alert_data["alert_type"])
                        alert_data["status"] = AlertStatus(alert_data["status"])
                        alert = Alert(**alert_data)
                        self.alerts[alert.id] = alert
                logger.info(f"Loaded {len(self.alerts)} alerts")
            except Exception as e:
                logger.error(f"Failed to load alerts: {e}")

    def _save(self):
        """Save alerts to storage."""
        try:
            self.storage_path.parent.mkdir(parents=True, exist_ok=True)
            data = {
                "alerts": [
                    {**asdict(a), "alert_type": a.alert_type.value, "status": a.status.value}
                    for a in self.alerts.values()
                ],
                "last_updated": datetime.now(timezone.utc).isoformat()
            }
            with open(self.storage_path, "w") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save alerts: {e}")

    def on_alert_triggered(self, callback: Callable):
        """Register callback for when alerts are triggered."""
        self._callbacks.append(callback)

    def create_alert(
        self,
        user_id: str,
        alert_type: AlertType,
        token_symbol: str,
        token_mint: str,
        condition_value: float,
        message: str = "",
        expires_hours: Optional[int] = None,
        repeat: bool = False,
        cooldown_minutes: int = 60
    ) -> str:
        """Create a new alert. Returns alert ID."""
        import uuid

        alert_id = str(uuid.uuid4())[:8]
        now = datetime.now(timezone.utc)

        expires_at = None
        if expires_hours:
            expires_at = (now + timedelta(hours=expires_hours)).isoformat()

        alert = Alert(
            id=alert_id,
            user_id=user_id,
            alert_type=alert_type,
            token_symbol=token_symbol,
            token_mint=token_mint,
            condition_value=condition_value,
            message=message or f"{token_symbol} alert triggered!",
            created_at=now.isoformat(),
            expires_at=expires_at,
            repeat=repeat,
            cooldown_minutes=cooldown_minutes
        )

        self.alerts[alert_id] = alert
        self._save()

        logger.info(f"Created alert {alert_id}: {alert_type.value} for {token_symbol}")
        return alert_id

    def cancel_alert(self, alert_id: str) -> bool:
        """Cancel an alert."""
        if alert_id not in self.alerts:
            return False

        self.alerts[alert_id].status = AlertStatus.CANCELLED
        self._save()
        return True

    def get_user_alerts(self, user_id: str) -> List[Alert]:
        """Get all alerts for a user."""
        return [a for a in self.alerts.values() if a.user_id == user_id]

    def get_active_alerts(self) -> List[Alert]:
        """Get all active alerts."""
        return [a for a in self.alerts.values() if a.status == AlertStatus.ACTIVE]

    async def check_alerts(self, current_prices: Dict[str, float]) -> List[Alert]:
        """
        Check all alerts against current prices.
        Returns list of triggered alerts.
        """
        triggered = []
        now = datetime.now(timezone.utc)

        for alert in list(self.alerts.values()):
            if alert.status != AlertStatus.ACTIVE:
                continue

            # Check expiration
            if alert.expires_at:
                expires = datetime.fromisoformat(alert.expires_at.replace('Z', '+00:00'))
                if now > expires:
                    alert.status = AlertStatus.EXPIRED
                    continue

            # Check cooldown
            if alert.last_trigger:
                last = datetime.fromisoformat(alert.last_trigger.replace('Z', '+00:00'))
                if (now - last).total_seconds() < alert.cooldown_minutes * 60:
                    continue

            # Get current price
            price = current_prices.get(alert.token_mint)
            if price is None:
                continue

            # Check condition
            should_trigger = False

            if alert.alert_type == AlertType.PRICE_ABOVE:
                should_trigger = price >= alert.condition_value

            elif alert.alert_type == AlertType.PRICE_BELOW:
                should_trigger = price <= alert.condition_value

            elif alert.alert_type == AlertType.PRICE_CHANGE_PERCENT:
                # Would need baseline price - simplified here
                pass

            if should_trigger:
                alert.triggered_at = now.isoformat()
                alert.last_trigger = now.isoformat()

                if not alert.repeat:
                    alert.status = AlertStatus.TRIGGERED

                triggered.append(alert)

                # Call callbacks
                for callback in self._callbacks:
                    try:
                        if asyncio.iscoroutinefunction(callback):
                            await callback(alert, price)
                        else:
                            callback(alert, price)
                    except Exception as e:
                        logger.error(f"Alert callback error: {e}")

        self._save()
        return triggered


# === DCA SCHEDULER ===

@dataclass
class DCASchedule:
    """A DCA schedule definition."""
    id: str
    user_id: str
    token_mint: str
    token_symbol: str
    amount_usd: float
    frequency: str  # daily, weekly, monthly
    day_of_week: Optional[int] = None  # 0=Monday, 6=Sunday (for weekly)
    day_of_month: Optional[int] = None  # 1-28 (for monthly)
    hour: int = 12  # Hour to execute (UTC)
    enabled: bool = True
    created_at: str = ""
    last_executed: Optional[str] = None
    next_execution: Optional[str] = None
    total_invested: float = 0.0
    total_tokens: float = 0.0


class DCAScheduler:
    """
    Dollar Cost Averaging scheduler.

    Usage:
        scheduler = DCAScheduler()

        # Create weekly DCA for SOL
        schedule_id = scheduler.create_schedule(
            user_id="123",
            token_mint="So11...",
            token_symbol="$SOL",
            amount_usd=50.0,
            frequency="weekly",
            day_of_week=0  # Monday
        )

        # Check and execute due schedules
        executed = await scheduler.execute_due_schedules(execute_fn)
    """

    def __init__(self, storage_path: Optional[Path] = None):
        self.storage_path = storage_path or Path(__file__).parent.parent / "data" / "dca_schedules.json"
        self.schedules: Dict[str, DCASchedule] = {}
        self._load()

    def _load(self):
        """Load schedules from storage."""
        if self.storage_path.exists():
            try:
                with open(self.storage_path) as f:
                    data = json.load(f)
                    for sched_data in data.get("schedules", []):
                        sched = DCASchedule(**sched_data)
                        self.schedules[sched.id] = sched
                logger.info(f"Loaded {len(self.schedules)} DCA schedules")
            except Exception as e:
                logger.error(f"Failed to load schedules: {e}")

    def _save(self):
        """Save schedules to storage."""
        try:
            self.storage_path.parent.mkdir(parents=True, exist_ok=True)
            data = {
                "schedules": [asdict(s) for s in self.schedules.values()],
                "last_updated": datetime.now(timezone.utc).isoformat()
            }
            with open(self.storage_path, "w") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save schedules: {e}")

    def _calculate_next_execution(self, schedule: DCASchedule) -> str:
        """Calculate next execution time."""
        now = datetime.now(timezone.utc)

        if schedule.frequency == "daily":
            next_time = now.replace(hour=schedule.hour, minute=0, second=0, microsecond=0)
            if next_time <= now:
                next_time += timedelta(days=1)

        elif schedule.frequency == "weekly":
            days_ahead = schedule.day_of_week - now.weekday()
            if days_ahead <= 0:
                days_ahead += 7
            next_time = now + timedelta(days=days_ahead)
            next_time = next_time.replace(hour=schedule.hour, minute=0, second=0, microsecond=0)

        elif schedule.frequency == "monthly":
            next_time = now.replace(
                day=min(schedule.day_of_month or 1, 28),
                hour=schedule.hour, minute=0, second=0, microsecond=0
            )
            if next_time <= now:
                # Move to next month
                if now.month == 12:
                    next_time = next_time.replace(year=now.year + 1, month=1)
                else:
                    next_time = next_time.replace(month=now.month + 1)

        else:
            next_time = now + timedelta(days=1)

        return next_time.isoformat()

    def create_schedule(
        self,
        user_id: str,
        token_mint: str,
        token_symbol: str,
        amount_usd: float,
        frequency: str,
        day_of_week: Optional[int] = None,
        day_of_month: Optional[int] = None,
        hour: int = 12
    ) -> str:
        """Create a DCA schedule. Returns schedule ID."""
        import uuid

        schedule_id = str(uuid.uuid4())[:8]

        schedule = DCASchedule(
            id=schedule_id,
            user_id=user_id,
            token_mint=token_mint,
            token_symbol=token_symbol,
            amount_usd=amount_usd,
            frequency=frequency,
            day_of_week=day_of_week,
            day_of_month=day_of_month,
            hour=hour,
            created_at=datetime.now(timezone.utc).isoformat()
        )

        schedule.next_execution = self._calculate_next_execution(schedule)

        self.schedules[schedule_id] = schedule
        self._save()

        logger.info(f"Created DCA schedule {schedule_id}: {amount_usd} USD {frequency} for {token_symbol}")
        return schedule_id

    def get_due_schedules(self) -> List[DCASchedule]:
        """Get schedules that are due for execution."""
        now = datetime.now(timezone.utc)
        due = []

        for schedule in self.schedules.values():
            if not schedule.enabled:
                continue

            if schedule.next_execution:
                next_exec = datetime.fromisoformat(schedule.next_execution.replace('Z', '+00:00'))
                if next_exec <= now:
                    due.append(schedule)

        return due

    async def execute_due_schedules(
        self,
        execute_fn: Callable[[DCASchedule], Any]
    ) -> List[DCASchedule]:
        """
        Execute all due DCA schedules.

        Args:
            execute_fn: Async function that executes the buy. Should return tokens received.
        """
        due = self.get_due_schedules()
        executed = []

        for schedule in due:
            try:
                logger.info(f"Executing DCA {schedule.id}: {schedule.amount_usd} USD for {schedule.token_symbol}")

                tokens_received = await execute_fn(schedule)

                schedule.last_executed = datetime.now(timezone.utc).isoformat()
                schedule.total_invested += schedule.amount_usd
                schedule.total_tokens += tokens_received or 0
                schedule.next_execution = self._calculate_next_execution(schedule)

                executed.append(schedule)

            except Exception as e:
                logger.error(f"DCA execution failed for {schedule.id}: {e}")

        self._save()
        return executed

    def toggle_schedule(self, schedule_id: str, enabled: bool) -> bool:
        """Enable or disable a schedule."""
        if schedule_id not in self.schedules:
            return False

        self.schedules[schedule_id].enabled = enabled
        self._save()
        return True

    def delete_schedule(self, schedule_id: str) -> bool:
        """Delete a schedule."""
        if schedule_id not in self.schedules:
            return False

        del self.schedules[schedule_id]
        self._save()
        return True


# === NOTIFICATION PREFERENCES ===

@dataclass
class NotificationPrefs:
    """User notification preferences."""
    user_id: str
    telegram_enabled: bool = True
    twitter_enabled: bool = False
    email_enabled: bool = False
    email_address: str = ""
    alert_types: List[str] = field(default_factory=lambda: ["price", "trade", "sentiment"])
    quiet_hours_start: Optional[int] = None  # UTC hour
    quiet_hours_end: Optional[int] = None
    min_alert_interval_minutes: int = 5


class NotificationManager:
    """Manage notification preferences and delivery."""

    def __init__(self, storage_path: Optional[Path] = None):
        self.storage_path = storage_path or Path(__file__).parent.parent / "data" / "notification_prefs.json"
        self.prefs: Dict[str, NotificationPrefs] = {}
        self._load()

    def _load(self):
        """Load preferences from storage."""
        if self.storage_path.exists():
            try:
                with open(self.storage_path) as f:
                    data = json.load(f)
                    for prefs_data in data.get("preferences", []):
                        prefs = NotificationPrefs(**prefs_data)
                        self.prefs[prefs.user_id] = prefs
            except Exception as e:
                logger.error(f"Failed to load notification prefs: {e}")

    def _save(self):
        """Save preferences to storage."""
        try:
            self.storage_path.parent.mkdir(parents=True, exist_ok=True)
            data = {
                "preferences": [asdict(p) for p in self.prefs.values()],
                "last_updated": datetime.now(timezone.utc).isoformat()
            }
            with open(self.storage_path, "w") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save notification prefs: {e}")

    def get_prefs(self, user_id: str) -> NotificationPrefs:
        """Get or create preferences for a user."""
        if user_id not in self.prefs:
            self.prefs[user_id] = NotificationPrefs(user_id=user_id)
            self._save()
        return self.prefs[user_id]

    def update_prefs(self, user_id: str, **kwargs) -> NotificationPrefs:
        """Update preferences for a user."""
        prefs = self.get_prefs(user_id)
        for key, value in kwargs.items():
            if hasattr(prefs, key):
                setattr(prefs, key, value)
        self._save()
        return prefs

    def should_notify(self, user_id: str, alert_type: str) -> bool:
        """Check if user should receive notification."""
        prefs = self.get_prefs(user_id)

        # Check alert type
        if alert_type not in prefs.alert_types:
            return False

        # Check quiet hours
        if prefs.quiet_hours_start is not None and prefs.quiet_hours_end is not None:
            now_hour = datetime.now(timezone.utc).hour
            if prefs.quiet_hours_start <= now_hour < prefs.quiet_hours_end:
                return False

        return True


# === SINGLETON INSTANCES ===

_alert_manager: Optional[AlertManager] = None
_dca_scheduler: Optional[DCAScheduler] = None
_notification_manager: Optional[NotificationManager] = None


def get_alert_manager() -> AlertManager:
    global _alert_manager
    if _alert_manager is None:
        _alert_manager = AlertManager()
    return _alert_manager


def get_dca_scheduler() -> DCAScheduler:
    global _dca_scheduler
    if _dca_scheduler is None:
        _dca_scheduler = DCAScheduler()
    return _dca_scheduler


def get_notification_manager() -> NotificationManager:
    global _notification_manager
    if _notification_manager is None:
        _notification_manager = NotificationManager()
    return _notification_manager
