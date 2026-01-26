"""
Comprehensive unit tests for core/alerts.py - Alert System

Tests cover:
1. AlertType, AlertPriority, AlertStatus, NotificationChannel Enums
   - Value verification
   - Enum counts

2. AlertCondition Dataclass
   - Creation with required fields
   - Optional field defaults

3. Alert Dataclass
   - Full creation with all fields
   - Default values
   - Metadata handling

4. AlertTrigger Dataclass
   - Trigger event creation
   - Notification status tracking

5. AlertDB Class
   - Database initialization
   - Schema creation
   - Connection management

6. AlertManager Class
   - Alert creation
   - Alert checking against prices
   - Alert triggering and notifications
   - Alert cancellation
   - Alert retrieval
   - Trigger history
   - Webhook configuration
   - Custom notification handlers

7. Singleton Accessor
   - get_alert_manager returns singleton

Target: 80%+ coverage with 70+ comprehensive tests
"""

import pytest
import asyncio
import json
import sqlite3
import tempfile
import uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock, PropertyMock
import os
import sys
import importlib.util

# Import directly from core/alerts.py file (not the core/alerts/ package)
# This is needed because core/alerts/ directory shadows core/alerts.py
project_root = Path(__file__).parent.parent.parent
alerts_file = project_root / "core" / "alerts.py"
spec = importlib.util.spec_from_file_location("alerts_module", alerts_file)
alerts_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(alerts_module)

# Extract classes from the loaded module
AlertType = alerts_module.AlertType
AlertPriority = alerts_module.AlertPriority
AlertStatus = alerts_module.AlertStatus
NotificationChannel = alerts_module.NotificationChannel
AlertCondition = alerts_module.AlertCondition
Alert = alerts_module.Alert
AlertTrigger = alerts_module.AlertTrigger
AlertDB = alerts_module.AlertDB
AlertManager = alerts_module.AlertManager
get_alert_manager = alerts_module.get_alert_manager


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def temp_db(tmp_path):
    """Create temporary database path."""
    db_path = tmp_path / "test_alerts.db"
    return db_path


@pytest.fixture
def alert_db(temp_db):
    """Create AlertDB instance with temp database."""
    return AlertDB(temp_db)


@pytest.fixture
def alert_manager(temp_db):
    """Create AlertManager instance with temp database."""
    return AlertManager(db_path=temp_db)


@pytest.fixture
def sample_condition():
    """Create a sample alert condition."""
    return AlertCondition(
        alert_type=AlertType.PRICE_ABOVE,
        symbol="SOL",
        threshold=100.0
    )


@pytest.fixture
def sample_condition_below():
    """Create a sample price below condition."""
    return AlertCondition(
        alert_type=AlertType.PRICE_BELOW,
        symbol="BTC",
        threshold=50000.0
    )


@pytest.fixture
def sample_rsi_condition():
    """Create a sample RSI overbought condition."""
    return AlertCondition(
        alert_type=AlertType.RSI_OVERBOUGHT,
        symbol="ETH",
        threshold=70.0
    )


@pytest.fixture
def sample_rsi_oversold_condition():
    """Create a sample RSI oversold condition."""
    return AlertCondition(
        alert_type=AlertType.RSI_OVERSOLD,
        symbol="ETH",
        threshold=30.0
    )


@pytest.fixture
def sample_alert(sample_condition):
    """Create a sample alert object."""
    return Alert(
        id="test123",
        name="Test Alert",
        condition=sample_condition,
        priority=AlertPriority.MEDIUM,
        channels=[NotificationChannel.CONSOLE],
        status=AlertStatus.ACTIVE,
        created_at=datetime.now(timezone.utc).isoformat(),
        expires_at=None,
        cooldown_minutes=60,
        max_triggers=0,
        trigger_count=0,
        last_triggered=None,
        message_template="SOL price_above: {value} (threshold: {threshold})",
        webhook_url=None,
        metadata={}
    )


# =============================================================================
# AlertType Enum Tests
# =============================================================================

class TestAlertType:
    """Test AlertType enum values."""

    def test_alert_type_values(self):
        """Test all alert type values are defined."""
        assert AlertType.PRICE_ABOVE.value == "price_above"
        assert AlertType.PRICE_BELOW.value == "price_below"
        assert AlertType.PRICE_CHANGE_PCT.value == "price_change_pct"
        assert AlertType.VOLUME_SPIKE.value == "volume_spike"
        assert AlertType.RSI_OVERBOUGHT.value == "rsi_overbought"
        assert AlertType.RSI_OVERSOLD.value == "rsi_oversold"
        assert AlertType.MA_CROSS.value == "ma_cross"
        assert AlertType.WHALE_MOVEMENT.value == "whale_movement"
        assert AlertType.LIQUIDITY_CHANGE.value == "liquidity_change"
        assert AlertType.CUSTOM.value == "custom"

    def test_alert_type_count(self):
        """Test there are exactly 10 alert types."""
        assert len(AlertType) == 10

    def test_alert_type_from_value(self):
        """Test creating AlertType from string value."""
        assert AlertType("price_above") == AlertType.PRICE_ABOVE
        assert AlertType("rsi_oversold") == AlertType.RSI_OVERSOLD


# =============================================================================
# AlertPriority Enum Tests
# =============================================================================

class TestAlertPriority:
    """Test AlertPriority enum values."""

    def test_alert_priority_values(self):
        """Test all priority values are defined."""
        assert AlertPriority.LOW.value == "low"
        assert AlertPriority.MEDIUM.value == "medium"
        assert AlertPriority.HIGH.value == "high"
        assert AlertPriority.CRITICAL.value == "critical"

    def test_alert_priority_count(self):
        """Test there are exactly 4 priority levels."""
        assert len(AlertPriority) == 4


# =============================================================================
# AlertStatus Enum Tests
# =============================================================================

class TestAlertStatus:
    """Test AlertStatus enum values."""

    def test_alert_status_values(self):
        """Test all status values are defined."""
        assert AlertStatus.ACTIVE.value == "active"
        assert AlertStatus.TRIGGERED.value == "triggered"
        assert AlertStatus.EXPIRED.value == "expired"
        assert AlertStatus.CANCELLED.value == "cancelled"
        assert AlertStatus.SNOOZED.value == "snoozed"

    def test_alert_status_count(self):
        """Test there are exactly 5 status values."""
        assert len(AlertStatus) == 5


# =============================================================================
# NotificationChannel Enum Tests
# =============================================================================

class TestNotificationChannel:
    """Test NotificationChannel enum values."""

    def test_notification_channel_values(self):
        """Test all channel values are defined."""
        assert NotificationChannel.CONSOLE.value == "console"
        assert NotificationChannel.WEBHOOK.value == "webhook"
        assert NotificationChannel.TELEGRAM.value == "telegram"
        assert NotificationChannel.DISCORD.value == "discord"
        assert NotificationChannel.EMAIL.value == "email"
        assert NotificationChannel.PUSH.value == "push"

    def test_notification_channel_count(self):
        """Test there are exactly 6 notification channels."""
        assert len(NotificationChannel) == 6


# =============================================================================
# AlertCondition Dataclass Tests
# =============================================================================

class TestAlertCondition:
    """Test AlertCondition dataclass."""

    def test_create_basic_condition(self):
        """Test creating a basic alert condition."""
        condition = AlertCondition(
            alert_type=AlertType.PRICE_ABOVE,
            symbol="SOL",
            threshold=100.0
        )
        assert condition.alert_type == AlertType.PRICE_ABOVE
        assert condition.symbol == "SOL"
        assert condition.threshold == 100.0

    def test_condition_default_comparison(self):
        """Test default comparison is gte."""
        condition = AlertCondition(
            alert_type=AlertType.PRICE_ABOVE,
            symbol="SOL",
            threshold=100.0
        )
        assert condition.comparison == "gte"

    def test_condition_custom_comparison(self):
        """Test custom comparison value."""
        condition = AlertCondition(
            alert_type=AlertType.PRICE_ABOVE,
            symbol="SOL",
            threshold=100.0,
            comparison="gt"
        )
        assert condition.comparison == "gt"

    def test_condition_secondary_threshold(self):
        """Test secondary threshold for range alerts."""
        condition = AlertCondition(
            alert_type=AlertType.PRICE_CHANGE_PCT,
            symbol="SOL",
            threshold=5.0,
            secondary_threshold=10.0
        )
        assert condition.secondary_threshold == 10.0

    def test_condition_time_window(self):
        """Test time window setting."""
        condition = AlertCondition(
            alert_type=AlertType.VOLUME_SPIKE,
            symbol="SOL",
            threshold=1000000,
            time_window_minutes=15
        )
        assert condition.time_window_minutes == 15

    def test_condition_default_time_window(self):
        """Test default time window is 0."""
        condition = AlertCondition(
            alert_type=AlertType.PRICE_ABOVE,
            symbol="SOL",
            threshold=100.0
        )
        assert condition.time_window_minutes == 0


# =============================================================================
# Alert Dataclass Tests
# =============================================================================

class TestAlert:
    """Test Alert dataclass."""

    def test_create_alert(self, sample_condition):
        """Test creating an alert."""
        alert = Alert(
            id="abc123",
            name="Test Alert",
            condition=sample_condition,
            priority=AlertPriority.HIGH,
            channels=[NotificationChannel.CONSOLE, NotificationChannel.TELEGRAM],
            status=AlertStatus.ACTIVE,
            created_at="2025-01-25T00:00:00+00:00",
            expires_at=None
        )
        assert alert.id == "abc123"
        assert alert.name == "Test Alert"
        assert alert.priority == AlertPriority.HIGH
        assert len(alert.channels) == 2
        assert alert.status == AlertStatus.ACTIVE

    def test_alert_default_cooldown(self, sample_condition):
        """Test default cooldown is 60 minutes."""
        alert = Alert(
            id="abc123",
            name="Test Alert",
            condition=sample_condition,
            priority=AlertPriority.MEDIUM,
            channels=[NotificationChannel.CONSOLE],
            status=AlertStatus.ACTIVE,
            created_at="2025-01-25T00:00:00+00:00",
            expires_at=None
        )
        assert alert.cooldown_minutes == 60

    def test_alert_default_max_triggers(self, sample_condition):
        """Test default max_triggers is 0 (unlimited)."""
        alert = Alert(
            id="abc123",
            name="Test Alert",
            condition=sample_condition,
            priority=AlertPriority.MEDIUM,
            channels=[NotificationChannel.CONSOLE],
            status=AlertStatus.ACTIVE,
            created_at="2025-01-25T00:00:00+00:00",
            expires_at=None
        )
        assert alert.max_triggers == 0

    def test_alert_with_metadata(self, sample_condition):
        """Test alert with custom metadata."""
        alert = Alert(
            id="abc123",
            name="Test Alert",
            condition=sample_condition,
            priority=AlertPriority.MEDIUM,
            channels=[NotificationChannel.CONSOLE],
            status=AlertStatus.ACTIVE,
            created_at="2025-01-25T00:00:00+00:00",
            expires_at=None,
            metadata={"source": "test", "tags": ["trading"]}
        )
        assert alert.metadata["source"] == "test"
        assert "trading" in alert.metadata["tags"]


# =============================================================================
# AlertTrigger Dataclass Tests
# =============================================================================

class TestAlertTrigger:
    """Test AlertTrigger dataclass."""

    def test_create_alert_trigger(self):
        """Test creating an alert trigger."""
        trigger = AlertTrigger(
            alert_id="abc123",
            alert_name="SOL Price Alert",
            symbol="SOL",
            alert_type=AlertType.PRICE_ABOVE,
            trigger_value=105.0,
            threshold=100.0,
            message="SOL reached $105",
            priority=AlertPriority.HIGH,
            timestamp="2025-01-25T12:00:00+00:00",
            channels_notified=["console", "telegram"],
            notification_status={"console": True, "telegram": False}
        )
        assert trigger.alert_id == "abc123"
        assert trigger.trigger_value == 105.0
        assert trigger.threshold == 100.0
        assert len(trigger.channels_notified) == 2
        assert trigger.notification_status["console"] is True

    def test_alert_trigger_tracks_failures(self):
        """Test trigger tracks notification failures."""
        trigger = AlertTrigger(
            alert_id="abc123",
            alert_name="Test",
            symbol="SOL",
            alert_type=AlertType.PRICE_ABOVE,
            trigger_value=105.0,
            threshold=100.0,
            message="Test",
            priority=AlertPriority.MEDIUM,
            timestamp="2025-01-25T12:00:00+00:00",
            channels_notified=["console", "telegram", "email"],
            notification_status={"console": True, "telegram": False, "email": False}
        )
        failures = [k for k, v in trigger.notification_status.items() if not v]
        assert len(failures) == 2
        assert "telegram" in failures
        assert "email" in failures


# =============================================================================
# AlertDB Tests
# =============================================================================

class TestAlertDB:
    """Test AlertDB database operations."""

    def test_database_created(self, temp_db):
        """Test database file is created."""
        AlertDB(temp_db)
        assert temp_db.exists()

    def test_database_directory_created(self, tmp_path):
        """Test database parent directory is created."""
        nested_path = tmp_path / "subdir" / "alerts.db"
        AlertDB(nested_path)
        assert nested_path.parent.exists()
        assert nested_path.exists()

    def test_alerts_table_created(self, alert_db):
        """Test alerts table is created."""
        with alert_db._get_connection() as conn:
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='alerts'"
            )
            assert cursor.fetchone() is not None

    def test_alert_triggers_table_created(self, alert_db):
        """Test alert_triggers table is created."""
        with alert_db._get_connection() as conn:
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='alert_triggers'"
            )
            assert cursor.fetchone() is not None

    def test_webhook_configs_table_created(self, alert_db):
        """Test webhook_configs table is created."""
        with alert_db._get_connection() as conn:
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='webhook_configs'"
            )
            assert cursor.fetchone() is not None

    def test_indexes_created(self, alert_db):
        """Test indexes are created."""
        with alert_db._get_connection() as conn:
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='index'"
            )
            indexes = {row[0] for row in cursor.fetchall()}
            assert "idx_alerts_symbol" in indexes
            assert "idx_alerts_status" in indexes

    def test_connection_context_manager(self, alert_db):
        """Test connection context manager closes connection."""
        conn_ref = None
        with alert_db._get_connection() as conn:
            conn_ref = conn
            # Connection should be open inside context
            cursor = conn.execute("SELECT 1")
            assert cursor.fetchone()[0] == 1
        # Connection should be closed after context
        # sqlite3 connection raises ProgrammingError when used after close
        with pytest.raises(sqlite3.ProgrammingError):
            conn_ref.execute("SELECT 1")


# =============================================================================
# AlertManager Creation Tests
# =============================================================================

class TestAlertManagerCreation:
    """Test AlertManager initialization."""

    def test_manager_initialization(self, alert_manager):
        """Test manager initializes correctly."""
        assert alert_manager._alerts == {}
        assert alert_manager._webhooks == {}
        assert alert_manager._price_history == {}

    def test_manager_creates_database(self, alert_manager, temp_db):
        """Test manager creates database."""
        assert temp_db.exists()

    def test_manager_default_handlers(self, alert_manager):
        """Test default notification handlers are set."""
        assert NotificationChannel.CONSOLE in alert_manager._notification_handlers

    def test_manager_loads_active_alerts(self, temp_db, sample_condition):
        """Test manager loads active alerts from database."""
        # First manager creates an alert
        manager1 = AlertManager(db_path=temp_db)
        asyncio.run(manager1.create_alert(
            name="Persistent Alert",
            condition=sample_condition,
            channels=[NotificationChannel.CONSOLE]
        ))

        # Second manager should load it
        manager2 = AlertManager(db_path=temp_db)
        assert len(manager2._alerts) == 1


# =============================================================================
# AlertManager.create_alert Tests
# =============================================================================

class TestAlertManagerCreateAlert:
    """Test AlertManager.create_alert method."""

    @pytest.mark.asyncio
    async def test_create_basic_alert(self, alert_manager, sample_condition):
        """Test creating a basic alert."""
        alert = await alert_manager.create_alert(
            name="SOL Above 100",
            condition=sample_condition,
            channels=[NotificationChannel.CONSOLE]
        )
        assert alert.id is not None
        assert alert.name == "SOL Above 100"
        assert alert.status == AlertStatus.ACTIVE
        assert alert.id in alert_manager._alerts

    @pytest.mark.asyncio
    async def test_create_alert_default_channel(self, alert_manager, sample_condition):
        """Test default channel is CONSOLE."""
        alert = await alert_manager.create_alert(
            name="Test Alert",
            condition=sample_condition
        )
        assert NotificationChannel.CONSOLE in alert.channels

    @pytest.mark.asyncio
    async def test_create_alert_multiple_channels(self, alert_manager, sample_condition):
        """Test creating alert with multiple channels."""
        alert = await alert_manager.create_alert(
            name="Multi-channel Alert",
            condition=sample_condition,
            channels=[NotificationChannel.CONSOLE, NotificationChannel.TELEGRAM]
        )
        assert len(alert.channels) == 2

    @pytest.mark.asyncio
    async def test_create_alert_with_expiration(self, alert_manager, sample_condition):
        """Test creating alert with expiration."""
        expires = datetime.now(timezone.utc) + timedelta(hours=24)
        alert = await alert_manager.create_alert(
            name="Expiring Alert",
            condition=sample_condition,
            expires_at=expires
        )
        assert alert.expires_at is not None

    @pytest.mark.asyncio
    async def test_create_alert_custom_cooldown(self, alert_manager, sample_condition):
        """Test creating alert with custom cooldown."""
        alert = await alert_manager.create_alert(
            name="Quick Cooldown",
            condition=sample_condition,
            cooldown_minutes=5
        )
        assert alert.cooldown_minutes == 5

    @pytest.mark.asyncio
    async def test_create_alert_max_triggers(self, alert_manager, sample_condition):
        """Test creating alert with max triggers limit."""
        alert = await alert_manager.create_alert(
            name="Limited Alert",
            condition=sample_condition,
            max_triggers=3
        )
        assert alert.max_triggers == 3

    @pytest.mark.asyncio
    async def test_create_alert_custom_message(self, alert_manager, sample_condition):
        """Test creating alert with custom message template."""
        alert = await alert_manager.create_alert(
            name="Custom Message",
            condition=sample_condition,
            message_template="ALERT: {symbol} hit {value}!"
        )
        assert "ALERT:" in alert.message_template

    @pytest.mark.asyncio
    async def test_create_alert_with_webhook(self, alert_manager, sample_condition):
        """Test creating alert with webhook URL."""
        alert = await alert_manager.create_alert(
            name="Webhook Alert",
            condition=sample_condition,
            webhook_url="https://example.com/webhook"
        )
        assert alert.webhook_url == "https://example.com/webhook"

    @pytest.mark.asyncio
    async def test_create_alert_with_metadata(self, alert_manager, sample_condition):
        """Test creating alert with metadata."""
        alert = await alert_manager.create_alert(
            name="Metadata Alert",
            condition=sample_condition,
            metadata={"source": "api", "user_id": "123"}
        )
        assert alert.metadata["source"] == "api"
        assert alert.metadata["user_id"] == "123"

    @pytest.mark.asyncio
    async def test_create_alert_generates_default_message(self, alert_manager, sample_condition):
        """Test default message template is generated."""
        alert = await alert_manager.create_alert(
            name="Auto Message",
            condition=sample_condition
        )
        assert "{value}" in alert.message_template
        assert "{threshold}" in alert.message_template

    @pytest.mark.asyncio
    async def test_create_alert_persisted_to_db(self, alert_manager, sample_condition):
        """Test alert is saved to database."""
        alert = await alert_manager.create_alert(
            name="Persisted Alert",
            condition=sample_condition
        )

        with alert_manager.db._get_connection() as conn:
            cursor = conn.execute(
                "SELECT name FROM alerts WHERE id = ?",
                (alert.id,)
            )
            row = cursor.fetchone()
            assert row is not None
            assert row[0] == "Persisted Alert"


# =============================================================================
# AlertManager.check_alerts Tests
# =============================================================================

class TestAlertManagerCheckAlerts:
    """Test AlertManager.check_alerts method."""

    @pytest.mark.asyncio
    async def test_check_alerts_no_alerts(self, alert_manager):
        """Test checking with no alerts configured."""
        triggered = await alert_manager.check_alerts({"SOL": 100.0})
        assert triggered == []

    @pytest.mark.asyncio
    async def test_check_alerts_price_above_triggered(self, alert_manager, sample_condition):
        """Test price above alert triggers correctly."""
        await alert_manager.create_alert(
            name="SOL Above 100",
            condition=sample_condition
        )

        triggered = await alert_manager.check_alerts({"SOL": 105.0})
        assert len(triggered) == 1
        assert triggered[0].trigger_value == 105.0

    @pytest.mark.asyncio
    async def test_check_alerts_price_above_not_triggered(self, alert_manager, sample_condition):
        """Test price above alert doesn't trigger when below."""
        await alert_manager.create_alert(
            name="SOL Above 100",
            condition=sample_condition
        )

        triggered = await alert_manager.check_alerts({"SOL": 95.0})
        assert len(triggered) == 0

    @pytest.mark.asyncio
    async def test_check_alerts_price_below_triggered(self, alert_manager, sample_condition_below):
        """Test price below alert triggers correctly."""
        await alert_manager.create_alert(
            name="BTC Below 50000",
            condition=sample_condition_below
        )

        triggered = await alert_manager.check_alerts({"BTC": 48000.0})
        assert len(triggered) == 1

    @pytest.mark.asyncio
    async def test_check_alerts_price_below_not_triggered(self, alert_manager, sample_condition_below):
        """Test price below alert doesn't trigger when above."""
        await alert_manager.create_alert(
            name="BTC Below 50000",
            condition=sample_condition_below
        )

        triggered = await alert_manager.check_alerts({"BTC": 52000.0})
        assert len(triggered) == 0

    @pytest.mark.asyncio
    async def test_check_alerts_rsi_overbought_triggered(self, alert_manager, sample_rsi_condition):
        """Test RSI overbought alert triggers."""
        await alert_manager.create_alert(
            name="ETH RSI Overbought",
            condition=sample_rsi_condition
        )

        indicators = {"ETH": {"rsi": 75.0}}
        triggered = await alert_manager.check_alerts(
            prices={"ETH": 2000.0},
            indicators=indicators
        )
        assert len(triggered) == 1

    @pytest.mark.asyncio
    async def test_check_alerts_rsi_overbought_not_triggered(self, alert_manager, sample_rsi_condition):
        """Test RSI overbought doesn't trigger when RSI is low."""
        await alert_manager.create_alert(
            name="ETH RSI Overbought",
            condition=sample_rsi_condition
        )

        indicators = {"ETH": {"rsi": 50.0}}
        triggered = await alert_manager.check_alerts(
            prices={"ETH": 2000.0},
            indicators=indicators
        )
        assert len(triggered) == 0

    @pytest.mark.asyncio
    async def test_check_alerts_rsi_oversold_triggered(self, alert_manager, sample_rsi_oversold_condition):
        """Test RSI oversold alert triggers."""
        await alert_manager.create_alert(
            name="ETH RSI Oversold",
            condition=sample_rsi_oversold_condition
        )

        indicators = {"ETH": {"rsi": 25.0}}
        triggered = await alert_manager.check_alerts(
            prices={"ETH": 2000.0},
            indicators=indicators
        )
        assert len(triggered) == 1

    @pytest.mark.asyncio
    async def test_check_alerts_missing_symbol(self, alert_manager, sample_condition):
        """Test alert for missing symbol doesn't trigger."""
        await alert_manager.create_alert(
            name="SOL Above 100",
            condition=sample_condition
        )

        # ETH price but no SOL
        triggered = await alert_manager.check_alerts({"ETH": 2000.0})
        assert len(triggered) == 0

    @pytest.mark.asyncio
    async def test_check_alerts_expired_alert(self, alert_manager, sample_condition):
        """Test expired alert is skipped and marked expired."""
        # Create alert with past expiration
        alert = await alert_manager.create_alert(
            name="Expired Alert",
            condition=sample_condition,
            expires_at=datetime.now(timezone.utc) - timedelta(hours=1)
        )

        triggered = await alert_manager.check_alerts({"SOL": 105.0})
        assert len(triggered) == 0
        assert alert_manager._alerts[alert.id].status == AlertStatus.EXPIRED

    @pytest.mark.asyncio
    async def test_check_alerts_cooldown_respected(self, alert_manager, sample_condition):
        """Test alert cooldown prevents re-triggering."""
        await alert_manager.create_alert(
            name="Cooldown Alert",
            condition=sample_condition,
            cooldown_minutes=60
        )

        # First trigger
        triggered1 = await alert_manager.check_alerts({"SOL": 105.0})
        assert len(triggered1) == 1

        # Second check should be in cooldown
        triggered2 = await alert_manager.check_alerts({"SOL": 110.0})
        assert len(triggered2) == 0

    @pytest.mark.asyncio
    async def test_check_alerts_max_triggers_reached(self, alert_manager, sample_condition):
        """Test alert stops triggering after max_triggers."""
        alert = await alert_manager.create_alert(
            name="Limited Alert",
            condition=sample_condition,
            max_triggers=1,
            cooldown_minutes=0  # No cooldown for immediate re-trigger
        )

        # First trigger
        triggered1 = await alert_manager.check_alerts({"SOL": 105.0})
        assert len(triggered1) == 1

        # Should be marked as triggered (max reached)
        assert alert_manager._alerts[alert.id].trigger_count == 1

    @pytest.mark.asyncio
    async def test_check_alerts_inactive_alert_skipped(self, alert_manager, sample_condition):
        """Test inactive alerts are skipped."""
        alert = await alert_manager.create_alert(
            name="Inactive Alert",
            condition=sample_condition
        )
        # Manually set to cancelled
        alert_manager._alerts[alert.id].status = AlertStatus.CANCELLED

        triggered = await alert_manager.check_alerts({"SOL": 105.0})
        assert len(triggered) == 0


# =============================================================================
# AlertManager Threshold Checking Tests
# =============================================================================

class TestAlertManagerThresholdChecking:
    """Test AlertManager threshold checking logic."""

    def test_check_threshold_price_above_true(self, alert_manager):
        """Test price above threshold returns true when exceeded."""
        result = alert_manager._check_threshold(105.0, 100.0, AlertType.PRICE_ABOVE)
        assert result is True

    def test_check_threshold_price_above_exact(self, alert_manager):
        """Test price above at exact threshold returns true."""
        result = alert_manager._check_threshold(100.0, 100.0, AlertType.PRICE_ABOVE)
        assert result is True

    def test_check_threshold_price_above_false(self, alert_manager):
        """Test price above returns false when below."""
        result = alert_manager._check_threshold(95.0, 100.0, AlertType.PRICE_ABOVE)
        assert result is False

    def test_check_threshold_price_below_true(self, alert_manager):
        """Test price below threshold returns true when under."""
        result = alert_manager._check_threshold(95.0, 100.0, AlertType.PRICE_BELOW)
        assert result is True

    def test_check_threshold_price_below_exact(self, alert_manager):
        """Test price below at exact threshold returns true."""
        result = alert_manager._check_threshold(100.0, 100.0, AlertType.PRICE_BELOW)
        assert result is True

    def test_check_threshold_price_below_false(self, alert_manager):
        """Test price below returns false when above."""
        result = alert_manager._check_threshold(105.0, 100.0, AlertType.PRICE_BELOW)
        assert result is False

    def test_check_threshold_unknown_type(self, alert_manager):
        """Test unknown alert type returns false."""
        result = alert_manager._check_threshold(100.0, 100.0, AlertType.CUSTOM)
        assert result is False


# =============================================================================
# AlertManager Trigger and Notification Tests
# =============================================================================

class TestAlertManagerTriggerNotification:
    """Test AlertManager triggering and notification."""

    @pytest.mark.asyncio
    async def test_trigger_alert_updates_count(self, alert_manager, sample_condition):
        """Test triggering alert increments trigger count."""
        alert = await alert_manager.create_alert(
            name="Count Test",
            condition=sample_condition
        )

        await alert_manager.check_alerts({"SOL": 105.0})
        assert alert_manager._alerts[alert.id].trigger_count == 1

    @pytest.mark.asyncio
    async def test_trigger_alert_updates_last_triggered(self, alert_manager, sample_condition):
        """Test triggering alert updates last_triggered timestamp."""
        alert = await alert_manager.create_alert(
            name="Timestamp Test",
            condition=sample_condition
        )

        await alert_manager.check_alerts({"SOL": 105.0})
        assert alert_manager._alerts[alert.id].last_triggered is not None

    @pytest.mark.asyncio
    async def test_trigger_alert_calls_console_handler(self, alert_manager, sample_condition):
        """Test console notification handler is called."""
        # Set up mock before creating alert
        mock_handler = AsyncMock()
        alert_manager._notification_handlers[NotificationChannel.CONSOLE] = mock_handler

        await alert_manager.create_alert(
            name="Console Test",
            condition=sample_condition,
            channels=[NotificationChannel.CONSOLE]
        )

        await alert_manager.check_alerts({"SOL": 105.0})
        mock_handler.assert_called_once()

    @pytest.mark.asyncio
    async def test_trigger_alert_records_notification_status(self, alert_manager, sample_condition):
        """Test notification status is recorded in trigger."""
        await alert_manager.create_alert(
            name="Status Test",
            condition=sample_condition,
            channels=[NotificationChannel.CONSOLE]
        )

        triggered = await alert_manager.check_alerts({"SOL": 105.0})
        assert "console" in triggered[0].notification_status
        assert triggered[0].notification_status["console"] is True

    @pytest.mark.asyncio
    async def test_trigger_alert_handles_missing_handler(self, alert_manager, sample_condition):
        """Test missing notification handler doesn't crash."""
        await alert_manager.create_alert(
            name="Missing Handler",
            condition=sample_condition,
            channels=[NotificationChannel.TELEGRAM]  # No handler configured
        )

        triggered = await alert_manager.check_alerts({"SOL": 105.0})
        assert len(triggered) == 1
        assert triggered[0].notification_status["telegram"] is False

    @pytest.mark.asyncio
    async def test_trigger_alert_handles_handler_exception(self, alert_manager, sample_condition):
        """Test exception in notification handler is caught."""
        await alert_manager.create_alert(
            name="Exception Test",
            condition=sample_condition,
            channels=[NotificationChannel.CONSOLE]
        )

        # Mock handler to raise exception
        async def failing_handler(trigger):
            raise Exception("Handler failed")

        alert_manager._notification_handlers[NotificationChannel.CONSOLE] = failing_handler

        # Should not raise, but mark as failed
        triggered = await alert_manager.check_alerts({"SOL": 105.0})
        assert len(triggered) == 1
        assert triggered[0].notification_status["console"] is False

    @pytest.mark.asyncio
    async def test_trigger_saved_to_database(self, alert_manager, sample_condition):
        """Test trigger is saved to database."""
        alert = await alert_manager.create_alert(
            name="Persist Trigger",
            condition=sample_condition
        )

        await alert_manager.check_alerts({"SOL": 105.0})

        with alert_manager.db._get_connection() as conn:
            cursor = conn.execute(
                "SELECT alert_id FROM alert_triggers WHERE alert_id = ?",
                (alert.id,)
            )
            row = cursor.fetchone()
            assert row is not None


# =============================================================================
# AlertManager Console Notification Tests
# =============================================================================

class TestAlertManagerConsoleNotification:
    """Test console notification handler."""

    @pytest.mark.asyncio
    async def test_notify_console_prints_message(self, alert_manager, capsys):
        """Test console notification prints message."""
        trigger = AlertTrigger(
            alert_id="test123",
            alert_name="Test Alert",
            symbol="SOL",
            alert_type=AlertType.PRICE_ABOVE,
            trigger_value=105.0,
            threshold=100.0,
            message="SOL reached $105",
            priority=AlertPriority.MEDIUM,
            timestamp=datetime.now(timezone.utc).isoformat(),
            channels_notified=["console"],
            notification_status={}
        )

        await alert_manager._notify_console(trigger)
        captured = capsys.readouterr()
        assert "ALERT:" in captured.out
        assert "SOL reached $105" in captured.out

    @pytest.mark.asyncio
    async def test_notify_console_priority_emoji(self, alert_manager, capsys):
        """Test console notification shows priority indicator."""
        trigger = AlertTrigger(
            alert_id="test123",
            alert_name="Critical Alert",
            symbol="SOL",
            alert_type=AlertType.PRICE_ABOVE,
            trigger_value=105.0,
            threshold=100.0,
            message="Critical message",
            priority=AlertPriority.CRITICAL,
            timestamp=datetime.now(timezone.utc).isoformat(),
            channels_notified=["console"],
            notification_status={}
        )

        await alert_manager._notify_console(trigger)
        captured = capsys.readouterr()
        assert "!!!" in captured.out


# =============================================================================
# AlertManager Cancel and Retrieval Tests
# =============================================================================

class TestAlertManagerCancelAndRetrieval:
    """Test alert cancellation and retrieval methods."""

    @pytest.mark.asyncio
    async def test_cancel_alert_success(self, alert_manager, sample_condition):
        """Test cancelling an alert."""
        alert = await alert_manager.create_alert(
            name="Cancel Me",
            condition=sample_condition
        )

        result = await alert_manager.cancel_alert(alert.id)
        assert result is True
        assert alert.id not in alert_manager._alerts

    @pytest.mark.asyncio
    async def test_cancel_alert_nonexistent(self, alert_manager):
        """Test cancelling nonexistent alert returns False."""
        result = await alert_manager.cancel_alert("nonexistent")
        assert result is False

    @pytest.mark.asyncio
    async def test_cancel_alert_updates_database(self, alert_manager, sample_condition):
        """Test cancelled alert is updated in database."""
        alert = await alert_manager.create_alert(
            name="Cancel Me",
            condition=sample_condition
        )

        await alert_manager.cancel_alert(alert.id)

        with alert_manager.db._get_connection() as conn:
            cursor = conn.execute(
                "SELECT status FROM alerts WHERE id = ?",
                (alert.id,)
            )
            row = cursor.fetchone()
            assert row[0] == "cancelled"

    @pytest.mark.asyncio
    async def test_get_alert_exists(self, alert_manager, sample_condition):
        """Test getting existing alert."""
        alert = await alert_manager.create_alert(
            name="Find Me",
            condition=sample_condition
        )

        found = alert_manager.get_alert(alert.id)
        assert found is not None
        assert found.name == "Find Me"

    @pytest.mark.asyncio
    async def test_get_alert_nonexistent(self, alert_manager):
        """Test getting nonexistent alert returns None."""
        found = alert_manager.get_alert("nonexistent")
        assert found is None

    @pytest.mark.asyncio
    async def test_get_active_alerts_all(self, alert_manager, sample_condition):
        """Test getting all active alerts."""
        await alert_manager.create_alert(name="Alert 1", condition=sample_condition)
        await alert_manager.create_alert(name="Alert 2", condition=sample_condition)

        active = alert_manager.get_active_alerts()
        assert len(active) == 2

    @pytest.mark.asyncio
    async def test_get_active_alerts_by_symbol(self, alert_manager, sample_condition, sample_condition_below):
        """Test getting active alerts filtered by symbol."""
        await alert_manager.create_alert(name="SOL Alert", condition=sample_condition)
        await alert_manager.create_alert(name="BTC Alert", condition=sample_condition_below)

        sol_alerts = alert_manager.get_active_alerts(symbol="SOL")
        assert len(sol_alerts) == 1
        assert sol_alerts[0].condition.symbol == "SOL"

    @pytest.mark.asyncio
    async def test_get_active_alerts_excludes_cancelled(self, alert_manager, sample_condition):
        """Test cancelled alerts are excluded."""
        alert = await alert_manager.create_alert(name="Cancel Me", condition=sample_condition)
        await alert_manager.cancel_alert(alert.id)

        active = alert_manager.get_active_alerts()
        assert len(active) == 0


# =============================================================================
# AlertManager Trigger History Tests
# =============================================================================

class TestAlertManagerTriggerHistory:
    """Test trigger history retrieval."""

    @pytest.mark.asyncio
    async def test_get_trigger_history_empty(self, alert_manager):
        """Test empty trigger history."""
        history = alert_manager.get_trigger_history()
        assert history == []

    @pytest.mark.asyncio
    async def test_get_trigger_history_with_triggers(self, alert_manager, sample_condition):
        """Test getting trigger history."""
        await alert_manager.create_alert(
            name="History Test",
            condition=sample_condition
        )

        await alert_manager.check_alerts({"SOL": 105.0})

        history = alert_manager.get_trigger_history()
        assert len(history) == 1

    @pytest.mark.asyncio
    async def test_get_trigger_history_by_alert_id(self, alert_manager, sample_condition, sample_condition_below):
        """Test getting trigger history filtered by alert ID."""
        alert1 = await alert_manager.create_alert(
            name="Alert 1",
            condition=sample_condition,
            cooldown_minutes=0
        )
        alert2 = await alert_manager.create_alert(
            name="Alert 2",
            condition=sample_condition_below
        )

        await alert_manager.check_alerts({"SOL": 105.0, "BTC": 48000.0})

        history = alert_manager.get_trigger_history(alert_id=alert1.id)
        assert len(history) == 1
        assert history[0]["alert_id"] == alert1.id

    @pytest.mark.asyncio
    async def test_get_trigger_history_respects_limit(self, alert_manager, sample_condition):
        """Test trigger history respects limit parameter."""
        alert = await alert_manager.create_alert(
            name="Many Triggers",
            condition=sample_condition,
            cooldown_minutes=0
        )

        # Trigger multiple times (manually reset cooldown)
        for i in range(5):
            alert_manager._alerts[alert.id].last_triggered = None
            await alert_manager.check_alerts({"SOL": 105.0 + i})

        history = alert_manager.get_trigger_history(limit=3)
        assert len(history) == 3


# =============================================================================
# AlertManager Webhook Tests
# =============================================================================

class TestAlertManagerWebhook:
    """Test webhook configuration."""

    def test_add_webhook(self, alert_manager):
        """Test adding a webhook."""
        alert_manager.add_webhook(
            channel="telegram",
            url="https://api.telegram.org/bot123/sendMessage",
            name="Telegram Bot"
        )

        assert "telegram" in alert_manager._webhooks
        assert alert_manager._webhooks["telegram"]["url"] == "https://api.telegram.org/bot123/sendMessage"

    def test_add_webhook_persisted(self, alert_manager):
        """Test webhook is persisted to database."""
        alert_manager.add_webhook(
            channel="discord",
            url="https://discord.com/api/webhooks/123"
        )

        with alert_manager.db._get_connection() as conn:
            cursor = conn.execute(
                "SELECT url FROM webhook_configs WHERE channel = ?",
                ("discord",)
            )
            row = cursor.fetchone()
            assert row is not None
            assert row[0] == "https://discord.com/api/webhooks/123"


# =============================================================================
# AlertManager Custom Handler Tests
# =============================================================================

class TestAlertManagerCustomHandler:
    """Test custom notification handlers."""

    def test_set_notification_handler(self, alert_manager):
        """Test setting a custom notification handler."""
        async def custom_handler(trigger):
            pass

        alert_manager.set_notification_handler(
            NotificationChannel.TELEGRAM,
            custom_handler
        )

        assert NotificationChannel.TELEGRAM in alert_manager._notification_handlers
        assert alert_manager._notification_handlers[NotificationChannel.TELEGRAM] == custom_handler

    @pytest.mark.asyncio
    async def test_custom_handler_called(self, alert_manager, sample_condition):
        """Test custom handler is called on trigger."""
        handler_called = []

        async def custom_handler(trigger):
            handler_called.append(trigger)

        alert_manager.set_notification_handler(
            NotificationChannel.TELEGRAM,
            custom_handler
        )

        await alert_manager.create_alert(
            name="Custom Handler Test",
            condition=sample_condition,
            channels=[NotificationChannel.TELEGRAM]
        )

        await alert_manager.check_alerts({"SOL": 105.0})
        assert len(handler_called) == 1


# =============================================================================
# Singleton Tests
# =============================================================================

class TestSingleton:
    """Test singleton accessor."""

    def test_get_alert_manager_returns_singleton(self):
        """Test get_alert_manager returns same instance."""
        # Reset the singleton
        alerts_module._manager = None

        manager1 = get_alert_manager()
        manager2 = get_alert_manager()

        assert manager1 is manager2

    def test_get_alert_manager_creates_manager(self):
        """Test get_alert_manager creates AlertManager."""
        # Reset the singleton
        alerts_module._manager = None

        manager = get_alert_manager()
        assert isinstance(manager, AlertManager)


# =============================================================================
# Edge Cases Tests
# =============================================================================

class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    @pytest.mark.asyncio
    async def test_alert_with_zero_threshold(self, alert_manager):
        """Test alert with zero threshold."""
        condition = AlertCondition(
            alert_type=AlertType.PRICE_ABOVE,
            symbol="TOKEN",
            threshold=0.0
        )
        alert = await alert_manager.create_alert(
            name="Zero Threshold",
            condition=condition
        )
        assert alert.condition.threshold == 0.0

    @pytest.mark.asyncio
    async def test_alert_with_negative_threshold(self, alert_manager):
        """Test alert with negative threshold (for short positions)."""
        condition = AlertCondition(
            alert_type=AlertType.PRICE_CHANGE_PCT,
            symbol="TOKEN",
            threshold=-10.0  # 10% down
        )
        alert = await alert_manager.create_alert(
            name="Negative Threshold",
            condition=condition
        )
        assert alert.condition.threshold == -10.0

    @pytest.mark.asyncio
    async def test_very_long_alert_name(self, alert_manager, sample_condition):
        """Test alert with very long name."""
        long_name = "A" * 500
        alert = await alert_manager.create_alert(
            name=long_name,
            condition=sample_condition
        )
        assert len(alert.name) == 500

    @pytest.mark.asyncio
    async def test_unicode_alert_name(self, alert_manager, sample_condition):
        """Test alert with unicode characters in name."""
        alert = await alert_manager.create_alert(
            name="Alert",
            condition=sample_condition
        )
        assert alert.name == "Alert"

    @pytest.mark.asyncio
    async def test_check_alerts_with_empty_prices(self, alert_manager, sample_condition):
        """Test checking alerts with empty price dict."""
        await alert_manager.create_alert(
            name="Empty Price Test",
            condition=sample_condition
        )

        triggered = await alert_manager.check_alerts({})
        assert len(triggered) == 0

    @pytest.mark.asyncio
    async def test_check_alerts_with_none_indicators(self, alert_manager, sample_rsi_condition):
        """Test RSI alert with None indicators."""
        await alert_manager.create_alert(
            name="RSI None Test",
            condition=sample_rsi_condition
        )

        triggered = await alert_manager.check_alerts(
            prices={"ETH": 2000.0},
            indicators=None
        )
        assert len(triggered) == 0

    @pytest.mark.asyncio
    async def test_check_alerts_with_missing_rsi(self, alert_manager, sample_rsi_condition):
        """Test RSI alert when RSI value is missing."""
        await alert_manager.create_alert(
            name="RSI Missing Test",
            condition=sample_rsi_condition
        )

        triggered = await alert_manager.check_alerts(
            prices={"ETH": 2000.0},
            indicators={"ETH": {"macd": 0.5}}  # No RSI
        )
        assert len(triggered) == 0


# =============================================================================
# RUN CONFIGURATION
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
