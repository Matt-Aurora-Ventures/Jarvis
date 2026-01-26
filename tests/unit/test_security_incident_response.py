"""
Comprehensive tests for the security incident response system.

Tests:
- Incident severity, status, and type enums
- Incident and timeline dataclass models
- Alert rule management and condition checking
- Playbook management and execution
- Incident lifecycle: create, acknowledge, update, resolve
- Automated actions from playbooks
- Notification delivery
- Incident metrics and views
- API endpoints for incident management
"""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, Mock, patch
from datetime import datetime, timedelta
import uuid

from core.security.incident_response import (
    IncidentSeverity,
    IncidentStatus,
    IncidentType,
    IncidentTimeline,
    Incident,
    AlertRule,
    Playbook,
    IncidentResponseManager,
    create_incident_endpoints,
)


# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def mock_notification_callback():
    """Create a mock notification callback."""
    return AsyncMock()


@pytest.fixture
def mock_emergency_shutdown_callback():
    """Create a mock emergency shutdown callback."""
    return AsyncMock()


@pytest.fixture
def manager():
    """Create a basic incident response manager."""
    return IncidentResponseManager()


@pytest.fixture
def manager_with_callbacks(mock_notification_callback, mock_emergency_shutdown_callback):
    """Create manager with notification and shutdown callbacks."""
    return IncidentResponseManager(
        notification_callback=mock_notification_callback,
        emergency_shutdown_callback=mock_emergency_shutdown_callback,
    )


@pytest.fixture
def sample_incident():
    """Create a sample incident for testing."""
    return Incident(
        id="test-incident-001",
        type=IncidentType.SECURITY_BREACH,
        severity=IncidentSeverity.P1,
        title="Test Security Breach",
        description="A test security breach incident",
        affected_systems=["api", "database"],
        affected_users=100,
        financial_impact=1_000_000_000,  # 1 SOL in lamports
    )


@pytest.fixture
def sample_alert_rule():
    """Create a sample alert rule for testing."""
    return AlertRule(
        id="test-rule-001",
        name="Test Alert Rule",
        description="A test alert rule",
        incident_type=IncidentType.UNUSUAL_ACTIVITY,
        severity=IncidentSeverity.P2,
        condition=lambda d: d.get("test_value", 0) > 100,
        cooldown=timedelta(minutes=5),
    )


@pytest.fixture
def sample_playbook():
    """Create a sample playbook for testing."""
    return Playbook(
        id="test-playbook-001",
        name="Test Playbook",
        incident_type=IncidentType.FUND_DRAIN,
        severity=IncidentSeverity.P1,
        steps=[
            {"order": 1, "action": "Step 1", "automated": True},
            {"order": 2, "action": "Step 2", "automated": False},
        ],
        auto_actions=[
            {"type": "pause_withdrawals", "params": {}},
            {"type": "notify_team", "params": {"channel": "security"}},
        ],
        notification_channels=["slack-security", "pagerduty"],
    )


# =============================================================================
# ENUM TESTS
# =============================================================================


class TestIncidentSeverity:
    """Test IncidentSeverity enum."""

    def test_p1_value(self):
        """Test P1 critical severity."""
        assert IncidentSeverity.P1.value == "p1"

    def test_p2_value(self):
        """Test P2 high severity."""
        assert IncidentSeverity.P2.value == "p2"

    def test_p3_value(self):
        """Test P3 medium severity."""
        assert IncidentSeverity.P3.value == "p3"

    def test_p4_value(self):
        """Test P4 low severity."""
        assert IncidentSeverity.P4.value == "p4"

    def test_enum_member_count(self):
        """Test all severity levels are present."""
        assert len(IncidentSeverity) == 4

    def test_string_inheritance(self):
        """Test that severity values are strings."""
        for severity in IncidentSeverity:
            assert isinstance(severity.value, str)


class TestIncidentStatus:
    """Test IncidentStatus enum."""

    def test_detected_value(self):
        """Test detected status."""
        assert IncidentStatus.DETECTED.value == "detected"

    def test_acknowledged_value(self):
        """Test acknowledged status."""
        assert IncidentStatus.ACKNOWLEDGED.value == "acknowledged"

    def test_investigating_value(self):
        """Test investigating status."""
        assert IncidentStatus.INVESTIGATING.value == "investigating"

    def test_mitigating_value(self):
        """Test mitigating status."""
        assert IncidentStatus.MITIGATING.value == "mitigating"

    def test_resolved_value(self):
        """Test resolved status."""
        assert IncidentStatus.RESOLVED.value == "resolved"

    def test_post_mortem_value(self):
        """Test post_mortem status."""
        assert IncidentStatus.POST_MORTEM.value == "post_mortem"

    def test_closed_value(self):
        """Test closed status."""
        assert IncidentStatus.CLOSED.value == "closed"

    def test_enum_member_count(self):
        """Test all statuses are present."""
        assert len(IncidentStatus) == 7


class TestIncidentType:
    """Test IncidentType enum."""

    def test_security_breach(self):
        """Test security breach type."""
        assert IncidentType.SECURITY_BREACH.value == "security_breach"

    def test_smart_contract_exploit(self):
        """Test smart contract exploit type."""
        assert IncidentType.SMART_CONTRACT_EXPLOIT.value == "smart_contract_exploit"

    def test_service_outage(self):
        """Test service outage type."""
        assert IncidentType.SERVICE_OUTAGE.value == "service_outage"

    def test_data_leak(self):
        """Test data leak type."""
        assert IncidentType.DATA_LEAK.value == "data_leak"

    def test_ddos_attack(self):
        """Test DDoS attack type."""
        assert IncidentType.DDOS_ATTACK.value == "ddos_attack"

    def test_unusual_activity(self):
        """Test unusual activity type."""
        assert IncidentType.UNUSUAL_ACTIVITY.value == "unusual_activity"

    def test_fund_drain(self):
        """Test fund drain type."""
        assert IncidentType.FUND_DRAIN.value == "fund_drain"

    def test_api_abuse(self):
        """Test API abuse type."""
        assert IncidentType.API_ABUSE.value == "api_abuse"

    def test_enum_member_count(self):
        """Test all incident types are present."""
        assert len(IncidentType) == 8


# =============================================================================
# DATACLASS TESTS
# =============================================================================


class TestIncidentTimeline:
    """Test IncidentTimeline dataclass."""

    def test_timeline_creation(self):
        """Test creating a timeline entry."""
        now = datetime.utcnow()
        timeline = IncidentTimeline(
            timestamp=now,
            action="Incident detected",
            actor="system",
            details={"source": "alert_rule"},
        )

        assert timeline.timestamp == now
        assert timeline.action == "Incident detected"
        assert timeline.actor == "system"
        assert timeline.details == {"source": "alert_rule"}

    def test_timeline_default_details(self):
        """Test timeline with default details."""
        timeline = IncidentTimeline(
            timestamp=datetime.utcnow(),
            action="Test action",
            actor="test_user",
        )

        assert timeline.details == {}

    def test_timeline_with_empty_details(self):
        """Test timeline with empty details dict."""
        timeline = IncidentTimeline(
            timestamp=datetime.utcnow(),
            action="Action",
            actor="Actor",
            details={},
        )

        assert timeline.details == {}


class TestIncident:
    """Test Incident dataclass."""

    def test_incident_creation(self, sample_incident):
        """Test creating an incident."""
        assert sample_incident.id == "test-incident-001"
        assert sample_incident.type == IncidentType.SECURITY_BREACH
        assert sample_incident.severity == IncidentSeverity.P1
        assert sample_incident.title == "Test Security Breach"

    def test_incident_defaults(self):
        """Test incident default values."""
        incident = Incident(
            id="test",
            type=IncidentType.API_ABUSE,
            severity=IncidentSeverity.P4,
            title="Test",
            description="Test description",
        )

        assert incident.status == IncidentStatus.DETECTED
        assert incident.acknowledged_at is None
        assert incident.resolved_at is None
        assert incident.assigned_to is None
        assert incident.affected_systems == []
        assert incident.affected_users == 0
        assert incident.financial_impact == 0
        assert incident.timeline == []
        assert incident.evidence == []
        assert incident.actions_taken == []
        assert incident.root_cause is None
        assert incident.post_mortem_url is None
        assert incident.metadata == {}

    def test_add_timeline(self, sample_incident):
        """Test adding a timeline entry to incident."""
        sample_incident.add_timeline(
            action="Action taken",
            actor="test_user",
            details={"note": "test note"},
        )

        assert len(sample_incident.timeline) == 1
        assert sample_incident.timeline[0].action == "Action taken"
        assert sample_incident.timeline[0].actor == "test_user"
        assert sample_incident.timeline[0].details == {"note": "test note"}

    def test_add_timeline_without_details(self, sample_incident):
        """Test adding timeline entry without details."""
        sample_incident.add_timeline(
            action="Simple action",
            actor="system",
        )

        assert len(sample_incident.timeline) == 1
        assert sample_incident.timeline[0].details == {}

    def test_multiple_timeline_entries(self, sample_incident):
        """Test adding multiple timeline entries."""
        sample_incident.add_timeline("Action 1", "user1")
        sample_incident.add_timeline("Action 2", "user2")
        sample_incident.add_timeline("Action 3", "system")

        assert len(sample_incident.timeline) == 3


class TestAlertRule:
    """Test AlertRule dataclass."""

    def test_alert_rule_creation(self, sample_alert_rule):
        """Test creating an alert rule."""
        assert sample_alert_rule.id == "test-rule-001"
        assert sample_alert_rule.name == "Test Alert Rule"
        assert sample_alert_rule.incident_type == IncidentType.UNUSUAL_ACTIVITY
        assert sample_alert_rule.severity == IncidentSeverity.P2

    def test_alert_rule_condition(self, sample_alert_rule):
        """Test alert rule condition function."""
        assert sample_alert_rule.condition({"test_value": 150}) is True
        assert sample_alert_rule.condition({"test_value": 50}) is False

    def test_alert_rule_defaults(self):
        """Test alert rule default values."""
        rule = AlertRule(
            id="test",
            name="Test",
            description="Test",
            incident_type=IncidentType.API_ABUSE,
            severity=IncidentSeverity.P3,
            condition=lambda d: True,
        )

        assert rule.cooldown == timedelta(minutes=5)
        assert rule.last_triggered is None
        assert rule.is_active is True


class TestPlaybook:
    """Test Playbook dataclass."""

    def test_playbook_creation(self, sample_playbook):
        """Test creating a playbook."""
        assert sample_playbook.id == "test-playbook-001"
        assert sample_playbook.name == "Test Playbook"
        assert sample_playbook.incident_type == IncidentType.FUND_DRAIN
        assert sample_playbook.severity == IncidentSeverity.P1

    def test_playbook_steps(self, sample_playbook):
        """Test playbook steps."""
        assert len(sample_playbook.steps) == 2
        assert sample_playbook.steps[0]["order"] == 1
        assert sample_playbook.steps[0]["automated"] is True

    def test_playbook_auto_actions(self, sample_playbook):
        """Test playbook auto actions."""
        assert len(sample_playbook.auto_actions) == 2
        assert sample_playbook.auto_actions[0]["type"] == "pause_withdrawals"

    def test_playbook_defaults(self):
        """Test playbook default values."""
        playbook = Playbook(
            id="test",
            name="Test",
            incident_type=IncidentType.API_ABUSE,
            severity=IncidentSeverity.P3,
            steps=[],
        )

        assert playbook.auto_actions == []
        assert playbook.notification_channels == []


# =============================================================================
# INCIDENT RESPONSE MANAGER - INITIALIZATION TESTS
# =============================================================================


class TestIncidentResponseManagerInit:
    """Test IncidentResponseManager initialization."""

    def test_basic_initialization(self, manager):
        """Test basic manager initialization."""
        assert manager.notify is None
        assert manager.emergency_shutdown is None
        assert manager.incidents == {}
        assert manager.on_call == []

    def test_initialization_with_callbacks(self, manager_with_callbacks):
        """Test initialization with callbacks."""
        assert manager_with_callbacks.notify is not None
        assert manager_with_callbacks.emergency_shutdown is not None

    def test_default_rules_initialized(self, manager):
        """Test default alert rules are initialized."""
        assert "large-withdrawal" in manager.alert_rules
        assert "rapid-withdrawals" in manager.alert_rules
        assert "api-abuse" in manager.alert_rules
        assert "contract-anomaly" in manager.alert_rules

    def test_default_playbooks_initialized(self, manager):
        """Test default playbooks are initialized."""
        assert "fund-drain-response" in manager.playbooks
        assert "ddos-response" in manager.playbooks


# =============================================================================
# ALERT MANAGEMENT TESTS
# =============================================================================


class TestAlertManagement:
    """Test alert rule management."""

    def test_add_alert_rule(self, manager, sample_alert_rule):
        """Test adding an alert rule."""
        manager.add_alert_rule(sample_alert_rule)

        assert sample_alert_rule.id in manager.alert_rules
        assert manager.alert_rules[sample_alert_rule.id] == sample_alert_rule

    def test_remove_alert_rule(self, manager, sample_alert_rule):
        """Test removing an alert rule."""
        manager.add_alert_rule(sample_alert_rule)
        manager.remove_alert_rule(sample_alert_rule.id)

        assert sample_alert_rule.id not in manager.alert_rules

    def test_remove_nonexistent_rule(self, manager):
        """Test removing a nonexistent rule doesn't raise error."""
        # Should not raise
        manager.remove_alert_rule("nonexistent-rule-id")

    @pytest.mark.asyncio
    async def test_check_alerts_triggers_incident(self, manager_with_callbacks):
        """Test that check_alerts creates incidents when conditions match."""
        # Default rule: api-abuse triggers when requests_per_minute > 1000
        event_data = {"requests_per_minute": 1500}

        incidents = await manager_with_callbacks.check_alerts(event_data)

        assert len(incidents) == 1
        assert incidents[0].type == IncidentType.API_ABUSE

    @pytest.mark.asyncio
    async def test_check_alerts_no_match(self, manager):
        """Test check_alerts with no matching conditions."""
        event_data = {"requests_per_minute": 100}

        incidents = await manager.check_alerts(event_data)

        assert len(incidents) == 0

    @pytest.mark.asyncio
    async def test_check_alerts_respects_cooldown(self, manager):
        """Test that cooldown prevents repeated triggers."""
        rule = AlertRule(
            id="cooldown-test",
            name="Cooldown Test",
            description="Test cooldown",
            incident_type=IncidentType.UNUSUAL_ACTIVITY,
            severity=IncidentSeverity.P3,
            condition=lambda d: d.get("trigger", False),
            cooldown=timedelta(hours=1),
        )
        manager.add_alert_rule(rule)

        # First trigger
        incidents1 = await manager.check_alerts({"trigger": True})
        assert len(incidents1) == 1

        # Second trigger should be blocked by cooldown
        incidents2 = await manager.check_alerts({"trigger": True})
        assert len(incidents2) == 0

    @pytest.mark.asyncio
    async def test_check_alerts_inactive_rule_skipped(self, manager):
        """Test that inactive rules are skipped."""
        rule = AlertRule(
            id="inactive-rule",
            name="Inactive Rule",
            description="Should not trigger",
            incident_type=IncidentType.UNUSUAL_ACTIVITY,
            severity=IncidentSeverity.P4,
            condition=lambda d: True,  # Always match
            is_active=False,
        )
        manager.add_alert_rule(rule)

        incidents = await manager.check_alerts({"any": "data"})

        # No incidents from this rule
        assert not any(i.title == "Inactive Rule" for i in incidents)

    @pytest.mark.asyncio
    async def test_check_alerts_handles_condition_error(self, manager):
        """Test that errors in condition functions are handled."""
        rule = AlertRule(
            id="error-rule",
            name="Error Rule",
            description="Raises error",
            incident_type=IncidentType.UNUSUAL_ACTIVITY,
            severity=IncidentSeverity.P4,
            condition=lambda d: 1 / 0,  # Will raise ZeroDivisionError
        )
        manager.add_alert_rule(rule)

        # Should not raise, should log error
        incidents = await manager.check_alerts({})

        # No incident from the error rule
        assert not any(i.title == "Error Rule" for i in incidents)


# =============================================================================
# PLAYBOOK MANAGEMENT TESTS
# =============================================================================


class TestPlaybookManagement:
    """Test playbook management."""

    def test_add_playbook(self, manager, sample_playbook):
        """Test adding a playbook."""
        manager.add_playbook(sample_playbook)

        assert sample_playbook.id in manager.playbooks
        assert manager.playbooks[sample_playbook.id] == sample_playbook

    def test_get_playbook_for_incident(self, manager, sample_incident):
        """Test getting matching playbook for an incident."""
        # Change sample_incident to match fund-drain-response playbook
        sample_incident.type = IncidentType.FUND_DRAIN
        sample_incident.severity = IncidentSeverity.P1

        playbook = manager.get_playbook_for_incident(sample_incident)

        assert playbook is not None
        assert playbook.id == "fund-drain-response"

    def test_get_playbook_no_match(self, manager, sample_incident):
        """Test getting playbook when no match exists."""
        # Use a type that doesn't have a matching playbook
        sample_incident.type = IncidentType.DATA_LEAK
        sample_incident.severity = IncidentSeverity.P4

        playbook = manager.get_playbook_for_incident(sample_incident)

        assert playbook is None

    def test_get_playbook_matches_type_and_severity(self, manager):
        """Test that playbook matching requires both type and severity match."""
        incident_p1 = Incident(
            id="test-1",
            type=IncidentType.DDOS_ATTACK,
            severity=IncidentSeverity.P1,  # Wrong severity for ddos-response
            title="Test",
            description="Test",
        )

        playbook = manager.get_playbook_for_incident(incident_p1)

        # ddos-response is for P2, so should not match
        assert playbook is None


# =============================================================================
# INCIDENT LIFECYCLE TESTS
# =============================================================================


class TestIncidentLifecycle:
    """Test incident lifecycle operations."""

    @pytest.mark.asyncio
    async def test_create_incident(self, manager):
        """Test creating an incident."""
        incident = await manager.create_incident(
            incident_type=IncidentType.SECURITY_BREACH,
            severity=IncidentSeverity.P1,
            title="Test Incident",
            description="Test description",
            evidence=[{"source": "test"}],
        )

        assert incident.id is not None
        assert incident.type == IncidentType.SECURITY_BREACH
        assert incident.severity == IncidentSeverity.P1
        assert incident.status == IncidentStatus.DETECTED
        assert incident.id in manager.incidents
        assert len(incident.timeline) >= 1

    @pytest.mark.asyncio
    async def test_create_incident_executes_playbook(self, manager_with_callbacks):
        """Test that creating an incident executes matching playbook."""
        incident = await manager_with_callbacks.create_incident(
            incident_type=IncidentType.FUND_DRAIN,
            severity=IncidentSeverity.P1,
            title="Fund Drain Test",
            description="Testing playbook execution",
        )

        # Playbook auto_actions should have been attempted
        assert len(incident.actions_taken) > 0

    @pytest.mark.asyncio
    async def test_acknowledge_incident(self, manager):
        """Test acknowledging an incident."""
        incident = await manager.create_incident(
            incident_type=IncidentType.API_ABUSE,
            severity=IncidentSeverity.P3,
            title="Test",
            description="Test",
        )

        acknowledged = await manager.acknowledge_incident(
            incident_id=incident.id,
            responder="test_user",
        )

        assert acknowledged.status == IncidentStatus.ACKNOWLEDGED
        assert acknowledged.acknowledged_at is not None
        assert acknowledged.assigned_to == "test_user"

    @pytest.mark.asyncio
    async def test_acknowledge_nonexistent_incident(self, manager):
        """Test acknowledging nonexistent incident raises error."""
        with pytest.raises(ValueError, match="Incident not found"):
            await manager.acknowledge_incident(
                incident_id="nonexistent",
                responder="test_user",
            )

    @pytest.mark.asyncio
    async def test_update_incident_status(self, manager):
        """Test updating incident status."""
        incident = await manager.create_incident(
            incident_type=IncidentType.SERVICE_OUTAGE,
            severity=IncidentSeverity.P2,
            title="Test",
            description="Test",
        )

        updated = await manager.update_incident_status(
            incident_id=incident.id,
            status=IncidentStatus.INVESTIGATING,
            actor="test_user",
            notes="Started investigation",
        )

        assert updated.status == IncidentStatus.INVESTIGATING

    @pytest.mark.asyncio
    async def test_update_status_to_resolved_sets_resolved_at(self, manager):
        """Test that updating to RESOLVED status sets resolved_at."""
        incident = await manager.create_incident(
            incident_type=IncidentType.SERVICE_OUTAGE,
            severity=IncidentSeverity.P3,
            title="Test",
            description="Test",
        )

        updated = await manager.update_incident_status(
            incident_id=incident.id,
            status=IncidentStatus.RESOLVED,
            actor="test_user",
        )

        assert updated.resolved_at is not None

    @pytest.mark.asyncio
    async def test_update_nonexistent_incident(self, manager):
        """Test updating nonexistent incident raises error."""
        with pytest.raises(ValueError, match="Incident not found"):
            await manager.update_incident_status(
                incident_id="nonexistent",
                status=IncidentStatus.INVESTIGATING,
                actor="test_user",
            )

    @pytest.mark.asyncio
    async def test_add_incident_action(self, manager):
        """Test adding an action to an incident."""
        incident = await manager.create_incident(
            incident_type=IncidentType.API_ABUSE,
            severity=IncidentSeverity.P3,
            title="Test",
            description="Test",
        )

        updated = await manager.add_incident_action(
            incident_id=incident.id,
            action="Blocked suspicious IP",
            actor="security_team",
        )

        assert "Blocked suspicious IP" in updated.actions_taken

    @pytest.mark.asyncio
    async def test_add_action_nonexistent_incident(self, manager):
        """Test adding action to nonexistent incident raises error."""
        with pytest.raises(ValueError, match="Incident not found"):
            await manager.add_incident_action(
                incident_id="nonexistent",
                action="Test action",
                actor="test_user",
            )

    @pytest.mark.asyncio
    async def test_resolve_incident(self, manager):
        """Test resolving an incident."""
        incident = await manager.create_incident(
            incident_type=IncidentType.UNUSUAL_ACTIVITY,
            severity=IncidentSeverity.P4,
            title="Test",
            description="Test",
        )

        resolved = await manager.resolve_incident(
            incident_id=incident.id,
            resolver="security_team",
            root_cause="Configuration error",
            resolution_notes="Fixed the configuration",
        )

        assert resolved.status == IncidentStatus.RESOLVED
        assert resolved.resolved_at is not None
        assert resolved.root_cause == "Configuration error"

    @pytest.mark.asyncio
    async def test_resolve_nonexistent_incident(self, manager):
        """Test resolving nonexistent incident raises error."""
        with pytest.raises(ValueError, match="Incident not found"):
            await manager.resolve_incident(
                incident_id="nonexistent",
                resolver="test_user",
                root_cause="Test",
                resolution_notes="Test",
            )


# =============================================================================
# AUTOMATED ACTIONS TESTS
# =============================================================================


class TestAutomatedActions:
    """Test automated actions from playbooks."""

    @pytest.mark.asyncio
    async def test_execute_pause_withdrawals_action(self, manager_with_callbacks):
        """Test pause_withdrawals action execution."""
        incident = Incident(
            id="test",
            type=IncidentType.FUND_DRAIN,
            severity=IncidentSeverity.P1,
            title="Test",
            description="Test",
        )

        action = {"type": "pause_withdrawals", "params": {}}

        await manager_with_callbacks._execute_action(incident, action)

        manager_with_callbacks.emergency_shutdown.assert_called_once_with(
            "pause_withdrawals"
        )

    @pytest.mark.asyncio
    async def test_execute_notify_team_action(self, manager_with_callbacks):
        """Test notify_team action execution."""
        incident = Incident(
            id="test",
            type=IncidentType.FUND_DRAIN,
            severity=IncidentSeverity.P1,
            title="Test Incident",
            description="Test",
        )

        action = {"type": "notify_team", "params": {"channel": "security"}}

        await manager_with_callbacks._execute_action(incident, action)

        manager_with_callbacks.notify.assert_called()

    @pytest.mark.asyncio
    async def test_execute_capture_logs_action(self, manager_with_callbacks):
        """Test capture_logs action execution."""
        incident = Incident(
            id="test",
            type=IncidentType.API_ABUSE,
            severity=IncidentSeverity.P3,
            title="Test",
            description="Test",
        )

        action = {"type": "capture_logs", "params": {"duration_hours": 24}}

        await manager_with_callbacks._execute_action(incident, action)

        # Should add timeline entry
        assert any("Logs captured" in t.action for t in incident.timeline)

    @pytest.mark.asyncio
    async def test_execute_rate_limiting_action(self, manager_with_callbacks):
        """Test enable_rate_limiting action execution."""
        incident = Incident(
            id="test",
            type=IncidentType.DDOS_ATTACK,
            severity=IncidentSeverity.P2,
            title="Test",
            description="Test",
        )

        action = {"type": "enable_rate_limiting", "params": {"requests_per_second": 10}}

        await manager_with_callbacks._execute_action(incident, action)

        assert any("Rate limiting enabled" in t.action for t in incident.timeline)

    @pytest.mark.asyncio
    async def test_execute_ddos_protection_action(self, manager_with_callbacks):
        """Test activate_ddos_protection action execution."""
        incident = Incident(
            id="test",
            type=IncidentType.DDOS_ATTACK,
            severity=IncidentSeverity.P2,
            title="Test",
            description="Test",
        )

        action = {"type": "activate_ddos_protection", "params": {}}

        await manager_with_callbacks._execute_action(incident, action)

        assert any("DDoS protection activated" in t.action for t in incident.timeline)

    @pytest.mark.asyncio
    async def test_playbook_execution_handles_action_errors(
        self, manager_with_callbacks
    ):
        """Test that playbook execution handles errors gracefully."""
        manager_with_callbacks.emergency_shutdown = AsyncMock(
            side_effect=Exception("Shutdown failed")
        )

        incident = Incident(
            id="test",
            type=IncidentType.FUND_DRAIN,
            severity=IncidentSeverity.P1,
            title="Test",
            description="Test",
        )

        playbook = manager_with_callbacks.playbooks["fund-drain-response"]

        # Should not raise, should log error
        await manager_with_callbacks._execute_playbook(incident, playbook)

        # Should have timeline entry about playbook execution
        assert any("Executing playbook" in t.action for t in incident.timeline)


# =============================================================================
# NOTIFICATION TESTS
# =============================================================================


class TestNotifications:
    """Test notification functionality."""

    @pytest.mark.asyncio
    async def test_notify_incident_created(self, manager_with_callbacks):
        """Test notification on incident creation."""
        await manager_with_callbacks.create_incident(
            incident_type=IncidentType.API_ABUSE,
            severity=IncidentSeverity.P3,
            title="Test API Abuse",
            description="Test",
        )

        manager_with_callbacks.notify.assert_called()

    @pytest.mark.asyncio
    async def test_notify_incident_acknowledged(self, manager_with_callbacks):
        """Test notification on incident acknowledgment."""
        incident = await manager_with_callbacks.create_incident(
            incident_type=IncidentType.API_ABUSE,
            severity=IncidentSeverity.P3,
            title="Test",
            description="Test",
        )

        call_count_before = manager_with_callbacks.notify.call_count

        await manager_with_callbacks.acknowledge_incident(
            incident_id=incident.id,
            responder="test_user",
        )

        assert manager_with_callbacks.notify.call_count > call_count_before

    @pytest.mark.asyncio
    async def test_notify_incident_resolved(self, manager_with_callbacks):
        """Test notification on incident resolution."""
        incident = await manager_with_callbacks.create_incident(
            incident_type=IncidentType.API_ABUSE,
            severity=IncidentSeverity.P3,
            title="Test",
            description="Test",
        )

        call_count_before = manager_with_callbacks.notify.call_count

        await manager_with_callbacks.resolve_incident(
            incident_id=incident.id,
            resolver="test_user",
            root_cause="Test",
            resolution_notes="Test",
        )

        assert manager_with_callbacks.notify.call_count > call_count_before

    @pytest.mark.asyncio
    async def test_no_notification_without_callback(self, manager):
        """Test that no notification is sent without callback."""
        # Should not raise when notify callback is None
        incident = await manager.create_incident(
            incident_type=IncidentType.API_ABUSE,
            severity=IncidentSeverity.P3,
            title="Test",
            description="Test",
        )

        assert incident is not None

    @pytest.mark.asyncio
    async def test_notification_handles_channel_error(self, manager_with_callbacks):
        """Test that notification errors are handled gracefully."""
        manager_with_callbacks.notify = AsyncMock(
            side_effect=Exception("Channel unavailable")
        )

        # Should not raise
        await manager_with_callbacks.create_incident(
            incident_type=IncidentType.API_ABUSE,
            severity=IncidentSeverity.P3,
            title="Test",
            description="Test",
        )

    def test_format_incident_message_p1(self, manager, sample_incident):
        """Test message formatting for P1 incident."""
        sample_incident.severity = IncidentSeverity.P1

        message = manager._format_incident_message(sample_incident, "created")

        assert "[P1]" in message.upper()
        assert sample_incident.title in message

    def test_format_incident_message_p2(self, manager, sample_incident):
        """Test message formatting for P2 incident."""
        sample_incident.severity = IncidentSeverity.P2

        message = manager._format_incident_message(sample_incident, "created")

        assert "[P2]" in message.upper()

    def test_format_incident_message_p3(self, manager, sample_incident):
        """Test message formatting for P3 incident."""
        sample_incident.severity = IncidentSeverity.P3

        message = manager._format_incident_message(sample_incident, "created")

        assert "[P3]" in message.upper()

    def test_format_incident_message_p4(self, manager, sample_incident):
        """Test message formatting for P4 incident."""
        sample_incident.severity = IncidentSeverity.P4

        message = manager._format_incident_message(sample_incident, "created")

        assert "[P4]" in message.upper()

    def test_get_notification_channels_p1(self, manager, sample_incident):
        """Test notification channels for P1 severity."""
        sample_incident.severity = IncidentSeverity.P1

        channels = manager._get_notification_channels(sample_incident)

        assert "slack-security" in channels
        assert "pagerduty" in channels
        assert "sms-oncall" in channels
        assert "email-founders" in channels

    def test_get_notification_channels_p2(self, manager, sample_incident):
        """Test notification channels for P2 severity."""
        sample_incident.severity = IncidentSeverity.P2

        channels = manager._get_notification_channels(sample_incident)

        assert "slack-security" in channels
        assert "pagerduty" in channels
        assert "sms-oncall" not in channels

    def test_get_notification_channels_p3(self, manager, sample_incident):
        """Test notification channels for P3 severity."""
        sample_incident.severity = IncidentSeverity.P3

        channels = manager._get_notification_channels(sample_incident)

        assert "slack-security" in channels
        assert "pagerduty" not in channels

    def test_get_notification_channels_p4(self, manager, sample_incident):
        """Test notification channels for P4 severity."""
        sample_incident.severity = IncidentSeverity.P4

        channels = manager._get_notification_channels(sample_incident)

        assert "slack-security" in channels
        assert len(channels) == 1


# =============================================================================
# VIEWS AND METRICS TESTS
# =============================================================================


class TestViewsAndMetrics:
    """Test incident views and metrics."""

    @pytest.mark.asyncio
    async def test_get_incident(self, manager):
        """Test getting an incident by ID."""
        incident = await manager.create_incident(
            incident_type=IncidentType.API_ABUSE,
            severity=IncidentSeverity.P3,
            title="Test",
            description="Test",
        )

        retrieved = await manager.get_incident(incident.id)

        assert retrieved == incident

    @pytest.mark.asyncio
    async def test_get_nonexistent_incident(self, manager):
        """Test getting nonexistent incident returns None."""
        retrieved = await manager.get_incident("nonexistent-id")

        assert retrieved is None

    @pytest.mark.asyncio
    async def test_get_active_incidents(self, manager):
        """Test getting all active incidents."""
        # Create active incident
        active = await manager.create_incident(
            incident_type=IncidentType.API_ABUSE,
            severity=IncidentSeverity.P3,
            title="Active",
            description="Test",
        )

        # Create and resolve an incident
        resolved = await manager.create_incident(
            incident_type=IncidentType.UNUSUAL_ACTIVITY,
            severity=IncidentSeverity.P4,
            title="Resolved",
            description="Test",
        )
        await manager.resolve_incident(
            resolved.id, "user", "cause", "notes"
        )

        active_incidents = await manager.get_active_incidents()

        assert active in active_incidents
        assert resolved not in active_incidents

    @pytest.mark.asyncio
    async def test_get_incidents_by_severity(self, manager):
        """Test filtering incidents by severity."""
        # Create incidents of different severities
        p1 = await manager.create_incident(
            incident_type=IncidentType.FUND_DRAIN,
            severity=IncidentSeverity.P1,
            title="P1",
            description="Test",
        )
        p3 = await manager.create_incident(
            incident_type=IncidentType.API_ABUSE,
            severity=IncidentSeverity.P3,
            title="P3",
            description="Test",
        )

        p1_incidents = await manager.get_incidents_by_severity(IncidentSeverity.P1)

        assert p1 in p1_incidents
        assert p3 not in p1_incidents

    @pytest.mark.asyncio
    async def test_get_incident_metrics_empty(self, manager):
        """Test metrics with no incidents."""
        metrics = await manager.get_incident_metrics()

        assert metrics["total_incidents"] == 0
        assert metrics["active_incidents"] == 0
        assert metrics["last_24h"] == 0
        assert metrics["last_7d"] == 0
        assert metrics["mttr_minutes"] == 0

    @pytest.mark.asyncio
    async def test_get_incident_metrics_with_incidents(self, manager):
        """Test metrics with incidents."""
        # Create some incidents
        await manager.create_incident(
            incident_type=IncidentType.API_ABUSE,
            severity=IncidentSeverity.P3,
            title="Test 1",
            description="Test",
        )
        await manager.create_incident(
            incident_type=IncidentType.UNUSUAL_ACTIVITY,
            severity=IncidentSeverity.P4,
            title="Test 2",
            description="Test",
        )

        metrics = await manager.get_incident_metrics()

        assert metrics["total_incidents"] == 2
        assert metrics["active_incidents"] == 2
        assert metrics["last_24h"] == 2
        assert metrics["by_severity"]["p3"] == 1
        assert metrics["by_severity"]["p4"] == 1

    @pytest.mark.asyncio
    async def test_get_incident_metrics_mttr(self, manager):
        """Test MTTR calculation in metrics."""
        # Create and resolve an incident
        incident = await manager.create_incident(
            incident_type=IncidentType.API_ABUSE,
            severity=IncidentSeverity.P3,
            title="Test",
            description="Test",
        )

        # Acknowledge
        await manager.acknowledge_incident(incident.id, "user")

        # Resolve
        await manager.resolve_incident(incident.id, "user", "cause", "notes")

        metrics = await manager.get_incident_metrics()

        # MTTR should be calculated (very small since done instantly)
        assert metrics["mttr_minutes"] >= 0


# =============================================================================
# API ENDPOINTS TESTS
# =============================================================================


class TestAPIEndpoints:
    """Test API endpoints creation."""

    def test_create_endpoints_returns_router(self, manager):
        """Test that create_incident_endpoints returns a FastAPI router."""
        router = create_incident_endpoints(manager)

        assert router is not None
        assert hasattr(router, "routes")

    def test_router_has_list_endpoint(self, manager):
        """Test router has list incidents endpoint."""
        router = create_incident_endpoints(manager)

        routes = [r.path for r in router.routes]
        # Router prefix is /api/incidents, so root path is /api/incidents
        assert "/api/incidents" in routes

    def test_router_has_metrics_endpoint(self, manager):
        """Test router has metrics endpoint."""
        router = create_incident_endpoints(manager)

        routes = [r.path for r in router.routes]
        assert "/api/incidents/metrics" in routes

    def test_router_has_get_incident_endpoint(self, manager):
        """Test router has get incident by ID endpoint."""
        router = create_incident_endpoints(manager)

        routes = [r.path for r in router.routes]
        assert "/api/incidents/{incident_id}" in routes

    def test_router_has_create_endpoint(self, manager):
        """Test router has create incident endpoint."""
        router = create_incident_endpoints(manager)

        # Check for POST method on root path
        post_routes = [r for r in router.routes if hasattr(r, "methods") and "POST" in r.methods]
        assert len(post_routes) > 0

    def test_router_has_acknowledge_endpoint(self, manager):
        """Test router has acknowledge endpoint."""
        router = create_incident_endpoints(manager)

        routes = [r.path for r in router.routes]
        assert "/api/incidents/{incident_id}/acknowledge" in routes

    def test_router_has_status_update_endpoint(self, manager):
        """Test router has status update endpoint."""
        router = create_incident_endpoints(manager)

        routes = [r.path for r in router.routes]
        assert "/api/incidents/{incident_id}/status" in routes

    def test_router_has_resolve_endpoint(self, manager):
        """Test router has resolve endpoint."""
        router = create_incident_endpoints(manager)

        routes = [r.path for r in router.routes]
        assert "/api/incidents/{incident_id}/resolve" in routes


# =============================================================================
# DEFAULT RULES TESTS
# =============================================================================


class TestDefaultAlertRules:
    """Test default alert rules."""

    @pytest.mark.asyncio
    async def test_large_withdrawal_rule(self, manager):
        """Test large withdrawal alert rule."""
        # Amount > 100,000 SOL in lamports
        large_amount = 150_000 * 10**9  # 150,000 SOL

        incidents = await manager.check_alerts({"amount": large_amount})

        assert any(i.type == IncidentType.UNUSUAL_ACTIVITY for i in incidents)

    @pytest.mark.asyncio
    async def test_large_withdrawal_rule_below_threshold(self, manager):
        """Test large withdrawal rule doesn't trigger below threshold."""
        small_amount = 50_000 * 10**9  # 50,000 SOL

        incidents = await manager.check_alerts({"amount": small_amount})

        # Should not trigger unusual activity for this specific rule
        unusual = [i for i in incidents if i.title == "Large Withdrawal Detected"]
        assert len(unusual) == 0

    @pytest.mark.asyncio
    async def test_rapid_withdrawals_rule(self, manager):
        """Test rapid withdrawals alert rule."""
        # More than 10 withdrawals in less than 10 minutes
        event_data = {
            "withdrawal_count": 15,
            "period_minutes": 5,
        }

        incidents = await manager.check_alerts(event_data)

        assert any(i.type == IncidentType.FUND_DRAIN for i in incidents)

    @pytest.mark.asyncio
    async def test_api_abuse_rule(self, manager):
        """Test API abuse alert rule."""
        # More than 1000 requests per minute
        event_data = {"requests_per_minute": 2000}

        incidents = await manager.check_alerts(event_data)

        assert any(i.type == IncidentType.API_ABUSE for i in incidents)

    @pytest.mark.asyncio
    async def test_contract_anomaly_rule(self, manager):
        """Test smart contract anomaly alert rule."""
        # Anomaly score > 0.9
        event_data = {"anomaly_score": 0.95}

        incidents = await manager.check_alerts(event_data)

        assert any(i.type == IncidentType.SMART_CONTRACT_EXPLOIT for i in incidents)


# =============================================================================
# DEFAULT PLAYBOOKS TESTS
# =============================================================================


class TestDefaultPlaybooks:
    """Test default playbooks."""

    def test_fund_drain_playbook_exists(self, manager):
        """Test fund drain response playbook exists."""
        assert "fund-drain-response" in manager.playbooks

    def test_fund_drain_playbook_has_steps(self, manager):
        """Test fund drain playbook has steps."""
        playbook = manager.playbooks["fund-drain-response"]

        assert len(playbook.steps) > 0
        assert playbook.steps[0]["order"] == 1

    def test_fund_drain_playbook_has_auto_actions(self, manager):
        """Test fund drain playbook has auto actions."""
        playbook = manager.playbooks["fund-drain-response"]

        assert len(playbook.auto_actions) > 0
        assert any(a["type"] == "pause_withdrawals" for a in playbook.auto_actions)

    def test_ddos_playbook_exists(self, manager):
        """Test DDoS response playbook exists."""
        assert "ddos-response" in manager.playbooks

    def test_ddos_playbook_has_steps(self, manager):
        """Test DDoS playbook has steps."""
        playbook = manager.playbooks["ddos-response"]

        assert len(playbook.steps) > 0

    def test_ddos_playbook_has_rate_limiting_action(self, manager):
        """Test DDoS playbook has rate limiting action."""
        playbook = manager.playbooks["ddos-response"]

        assert any(a["type"] == "enable_rate_limiting" for a in playbook.auto_actions)


# =============================================================================
# EDGE CASES AND CONCURRENCY TESTS
# =============================================================================


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    @pytest.mark.asyncio
    async def test_incident_with_empty_evidence(self, manager):
        """Test creating incident with empty evidence list."""
        incident = await manager.create_incident(
            incident_type=IncidentType.API_ABUSE,
            severity=IncidentSeverity.P4,
            title="Test",
            description="Test",
            evidence=[],
        )

        assert incident.evidence == []

    @pytest.mark.asyncio
    async def test_incident_with_none_evidence(self, manager):
        """Test creating incident with None evidence."""
        incident = await manager.create_incident(
            incident_type=IncidentType.API_ABUSE,
            severity=IncidentSeverity.P4,
            title="Test",
            description="Test",
            evidence=None,
        )

        assert incident.evidence == []

    @pytest.mark.asyncio
    async def test_multiple_incidents_same_type(self, manager):
        """Test creating multiple incidents of the same type."""
        incidents = []
        for i in range(5):
            incident = await manager.create_incident(
                incident_type=IncidentType.API_ABUSE,
                severity=IncidentSeverity.P3,
                title=f"Test {i}",
                description=f"Test {i}",
            )
            incidents.append(incident)

        # All should have unique IDs
        ids = [i.id for i in incidents]
        assert len(ids) == len(set(ids))

    @pytest.mark.asyncio
    async def test_status_update_adds_timeline(self, manager):
        """Test that status updates add timeline entries."""
        incident = await manager.create_incident(
            incident_type=IncidentType.API_ABUSE,
            severity=IncidentSeverity.P3,
            title="Test",
            description="Test",
        )

        initial_timeline_count = len(incident.timeline)

        await manager.update_incident_status(
            incident_id=incident.id,
            status=IncidentStatus.INVESTIGATING,
            actor="test_user",
            notes="Starting investigation",
        )

        assert len(incident.timeline) > initial_timeline_count

    @pytest.mark.asyncio
    async def test_action_without_emergency_shutdown_callback(self, manager):
        """Test pause_withdrawals action when no emergency shutdown callback."""
        incident = Incident(
            id="test",
            type=IncidentType.FUND_DRAIN,
            severity=IncidentSeverity.P1,
            title="Test",
            description="Test",
        )

        action = {"type": "pause_withdrawals", "params": {}}

        # Should not raise even without emergency_shutdown callback
        await manager._execute_action(incident, action)

    @pytest.mark.asyncio
    async def test_notify_team_without_callback(self, manager):
        """Test notify_team action when no notification callback."""
        incident = Incident(
            id="test",
            type=IncidentType.FUND_DRAIN,
            severity=IncidentSeverity.P1,
            title="Test",
            description="Test",
        )

        action = {"type": "notify_team", "params": {"channel": "security"}}

        # Should not raise even without notify callback
        await manager._execute_action(incident, action)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
