"""
Incident Response System
Prompt #53: Automated incident detection and response
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional
import json

logger = logging.getLogger(__name__)


# =============================================================================
# MODELS
# =============================================================================

class IncidentSeverity(str, Enum):
    P1 = "p1"  # Critical - immediate response
    P2 = "p2"  # High - response within 1 hour
    P3 = "p3"  # Medium - response within 4 hours
    P4 = "p4"  # Low - response within 24 hours


class IncidentStatus(str, Enum):
    DETECTED = "detected"
    ACKNOWLEDGED = "acknowledged"
    INVESTIGATING = "investigating"
    MITIGATING = "mitigating"
    RESOLVED = "resolved"
    POST_MORTEM = "post_mortem"
    CLOSED = "closed"


class IncidentType(str, Enum):
    SECURITY_BREACH = "security_breach"
    SMART_CONTRACT_EXPLOIT = "smart_contract_exploit"
    SERVICE_OUTAGE = "service_outage"
    DATA_LEAK = "data_leak"
    DDOS_ATTACK = "ddos_attack"
    UNUSUAL_ACTIVITY = "unusual_activity"
    FUND_DRAIN = "fund_drain"
    API_ABUSE = "api_abuse"


@dataclass
class IncidentTimeline:
    """Timeline entry for incident"""
    timestamp: datetime
    action: str
    actor: str
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Incident:
    """Security incident"""
    id: str
    type: IncidentType
    severity: IncidentSeverity
    title: str
    description: str
    status: IncidentStatus = IncidentStatus.DETECTED
    detected_at: datetime = field(default_factory=datetime.utcnow)
    acknowledged_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    assigned_to: Optional[str] = None
    affected_systems: List[str] = field(default_factory=list)
    affected_users: int = 0
    financial_impact: int = 0  # In lamports
    timeline: List[IncidentTimeline] = field(default_factory=list)
    evidence: List[Dict[str, Any]] = field(default_factory=list)
    actions_taken: List[str] = field(default_factory=list)
    root_cause: Optional[str] = None
    post_mortem_url: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def add_timeline(self, action: str, actor: str, details: Dict = None):
        self.timeline.append(IncidentTimeline(
            timestamp=datetime.utcnow(),
            action=action,
            actor=actor,
            details=details or {}
        ))


@dataclass
class AlertRule:
    """Rule for detecting incidents"""
    id: str
    name: str
    description: str
    incident_type: IncidentType
    severity: IncidentSeverity
    condition: Callable[[Dict], bool]
    cooldown: timedelta = field(default_factory=lambda: timedelta(minutes=5))
    last_triggered: Optional[datetime] = None
    is_active: bool = True


@dataclass
class Playbook:
    """Incident response playbook"""
    id: str
    name: str
    incident_type: IncidentType
    severity: IncidentSeverity
    steps: List[Dict[str, Any]]
    auto_actions: List[Dict[str, Any]] = field(default_factory=list)
    notification_channels: List[str] = field(default_factory=list)


# =============================================================================
# INCIDENT RESPONSE MANAGER
# =============================================================================

class IncidentResponseManager:
    """Manages incident detection, response, and resolution"""

    def __init__(
        self,
        notification_callback: Optional[Callable] = None,
        emergency_shutdown_callback: Optional[Callable] = None
    ):
        self.notify = notification_callback
        self.emergency_shutdown = emergency_shutdown_callback

        self.incidents: Dict[str, Incident] = {}
        self.alert_rules: Dict[str, AlertRule] = {}
        self.playbooks: Dict[str, Playbook] = {}
        self.on_call: List[str] = []

        # Initialize default rules and playbooks
        self._init_default_rules()
        self._init_default_playbooks()

    def _init_default_rules(self):
        """Initialize default alert rules"""
        self.add_alert_rule(AlertRule(
            id="large-withdrawal",
            name="Large Withdrawal Detected",
            description="Single withdrawal exceeds threshold",
            incident_type=IncidentType.UNUSUAL_ACTIVITY,
            severity=IncidentSeverity.P2,
            condition=lambda d: d.get("amount", 0) > 100_000 * 10**9,
            cooldown=timedelta(minutes=15)
        ))

        self.add_alert_rule(AlertRule(
            id="rapid-withdrawals",
            name="Rapid Withdrawals",
            description="Multiple large withdrawals in short period",
            incident_type=IncidentType.FUND_DRAIN,
            severity=IncidentSeverity.P1,
            condition=lambda d: d.get("withdrawal_count", 0) > 10 and d.get("period_minutes", 60) < 10
        ))

        self.add_alert_rule(AlertRule(
            id="api-abuse",
            name="API Abuse Detected",
            description="Unusual API usage patterns",
            incident_type=IncidentType.API_ABUSE,
            severity=IncidentSeverity.P3,
            condition=lambda d: d.get("requests_per_minute", 0) > 1000
        ))

        self.add_alert_rule(AlertRule(
            id="contract-anomaly",
            name="Smart Contract Anomaly",
            description="Unexpected contract behavior detected",
            incident_type=IncidentType.SMART_CONTRACT_EXPLOIT,
            severity=IncidentSeverity.P1,
            condition=lambda d: d.get("anomaly_score", 0) > 0.9
        ))

    def _init_default_playbooks(self):
        """Initialize default response playbooks"""
        self.add_playbook(Playbook(
            id="fund-drain-response",
            name="Fund Drain Response",
            incident_type=IncidentType.FUND_DRAIN,
            severity=IncidentSeverity.P1,
            steps=[
                {"order": 1, "action": "Pause all withdrawals", "automated": True},
                {"order": 2, "action": "Notify on-call security team", "automated": True},
                {"order": 3, "action": "Capture transaction logs", "automated": True},
                {"order": 4, "action": "Identify affected wallets", "automated": False},
                {"order": 5, "action": "Assess financial impact", "automated": False},
                {"order": 6, "action": "Notify affected users", "automated": False},
                {"order": 7, "action": "Coordinate with exchanges", "automated": False},
                {"order": 8, "action": "Prepare public statement", "automated": False}
            ],
            auto_actions=[
                {"type": "pause_withdrawals", "params": {}},
                {"type": "notify_team", "params": {"channel": "security"}},
                {"type": "capture_logs", "params": {"duration_hours": 24}}
            ],
            notification_channels=["slack-security", "pagerduty", "email-founders"]
        ))

        self.add_playbook(Playbook(
            id="ddos-response",
            name="DDoS Attack Response",
            incident_type=IncidentType.DDOS_ATTACK,
            severity=IncidentSeverity.P2,
            steps=[
                {"order": 1, "action": "Enable aggressive rate limiting", "automated": True},
                {"order": 2, "action": "Activate CDN protection", "automated": True},
                {"order": 3, "action": "Block suspicious IPs", "automated": True},
                {"order": 4, "action": "Monitor service health", "automated": True},
                {"order": 5, "action": "Scale infrastructure", "automated": False}
            ],
            auto_actions=[
                {"type": "enable_rate_limiting", "params": {"requests_per_second": 10}},
                {"type": "activate_ddos_protection", "params": {}}
            ],
            notification_channels=["slack-infra"]
        ))

    # =========================================================================
    # ALERT MANAGEMENT
    # =========================================================================

    def add_alert_rule(self, rule: AlertRule):
        """Add an alert rule"""
        self.alert_rules[rule.id] = rule

    def remove_alert_rule(self, rule_id: str):
        """Remove an alert rule"""
        if rule_id in self.alert_rules:
            del self.alert_rules[rule_id]

    async def check_alerts(self, event_data: Dict[str, Any]) -> List[Incident]:
        """Check all alert rules against event data"""
        triggered_incidents = []

        for rule in self.alert_rules.values():
            if not rule.is_active:
                continue

            # Check cooldown
            if rule.last_triggered:
                if datetime.utcnow() - rule.last_triggered < rule.cooldown:
                    continue

            # Check condition
            try:
                if rule.condition(event_data):
                    incident = await self.create_incident(
                        incident_type=rule.incident_type,
                        severity=rule.severity,
                        title=rule.name,
                        description=rule.description,
                        evidence=[{"rule_id": rule.id, "event_data": event_data}]
                    )
                    rule.last_triggered = datetime.utcnow()
                    triggered_incidents.append(incident)
            except Exception as e:
                logger.error(f"Error checking rule {rule.id}: {e}")

        return triggered_incidents

    # =========================================================================
    # PLAYBOOK MANAGEMENT
    # =========================================================================

    def add_playbook(self, playbook: Playbook):
        """Add a response playbook"""
        self.playbooks[playbook.id] = playbook

    def get_playbook_for_incident(self, incident: Incident) -> Optional[Playbook]:
        """Get the appropriate playbook for an incident"""
        for playbook in self.playbooks.values():
            if (playbook.incident_type == incident.type and
                playbook.severity == incident.severity):
                return playbook
        return None

    # =========================================================================
    # INCIDENT LIFECYCLE
    # =========================================================================

    async def create_incident(
        self,
        incident_type: IncidentType,
        severity: IncidentSeverity,
        title: str,
        description: str,
        evidence: List[Dict] = None
    ) -> Incident:
        """Create a new incident"""
        import uuid

        incident = Incident(
            id=str(uuid.uuid4()),
            type=incident_type,
            severity=severity,
            title=title,
            description=description,
            evidence=evidence or []
        )

        incident.add_timeline("Incident detected", "system")
        self.incidents[incident.id] = incident

        # Get and execute playbook
        playbook = self.get_playbook_for_incident(incident)
        if playbook:
            await self._execute_playbook(incident, playbook)

        # Send notifications
        await self._notify_incident(incident, "created")

        logger.warning(f"Incident created: {incident.id} - {title} [{severity.value}]")
        return incident

    async def acknowledge_incident(
        self,
        incident_id: str,
        responder: str
    ) -> Incident:
        """Acknowledge an incident"""
        incident = self.incidents.get(incident_id)
        if not incident:
            raise ValueError("Incident not found")

        incident.status = IncidentStatus.ACKNOWLEDGED
        incident.acknowledged_at = datetime.utcnow()
        incident.assigned_to = responder
        incident.add_timeline("Incident acknowledged", responder)

        await self._notify_incident(incident, "acknowledged")

        logger.info(f"Incident {incident_id} acknowledged by {responder}")
        return incident

    async def update_incident_status(
        self,
        incident_id: str,
        status: IncidentStatus,
        actor: str,
        notes: str = ""
    ) -> Incident:
        """Update incident status"""
        incident = self.incidents.get(incident_id)
        if not incident:
            raise ValueError("Incident not found")

        old_status = incident.status
        incident.status = status
        incident.add_timeline(
            f"Status changed: {old_status.value} -> {status.value}",
            actor,
            {"notes": notes}
        )

        if status == IncidentStatus.RESOLVED:
            incident.resolved_at = datetime.utcnow()

        await self._notify_incident(incident, "updated")

        logger.info(f"Incident {incident_id} status: {status.value}")
        return incident

    async def add_incident_action(
        self,
        incident_id: str,
        action: str,
        actor: str
    ) -> Incident:
        """Add an action taken for an incident"""
        incident = self.incidents.get(incident_id)
        if not incident:
            raise ValueError("Incident not found")

        incident.actions_taken.append(action)
        incident.add_timeline(f"Action taken: {action}", actor)

        return incident

    async def resolve_incident(
        self,
        incident_id: str,
        resolver: str,
        root_cause: str,
        resolution_notes: str
    ) -> Incident:
        """Resolve an incident"""
        incident = self.incidents.get(incident_id)
        if not incident:
            raise ValueError("Incident not found")

        incident.status = IncidentStatus.RESOLVED
        incident.resolved_at = datetime.utcnow()
        incident.root_cause = root_cause
        incident.add_timeline(
            "Incident resolved",
            resolver,
            {"root_cause": root_cause, "notes": resolution_notes}
        )

        await self._notify_incident(incident, "resolved")

        logger.info(f"Incident {incident_id} resolved by {resolver}")
        return incident

    # =========================================================================
    # AUTOMATED ACTIONS
    # =========================================================================

    async def _execute_playbook(
        self,
        incident: Incident,
        playbook: Playbook
    ):
        """Execute automated actions from playbook"""
        incident.add_timeline(
            f"Executing playbook: {playbook.name}",
            "system"
        )

        for action in playbook.auto_actions:
            try:
                await self._execute_action(incident, action)
                incident.actions_taken.append(f"[AUTO] {action['type']}")
            except Exception as e:
                logger.error(f"Auto action failed: {action['type']} - {e}")
                incident.add_timeline(
                    f"Auto action failed: {action['type']}",
                    "system",
                    {"error": str(e)}
                )

    async def _execute_action(
        self,
        incident: Incident,
        action: Dict[str, Any]
    ):
        """Execute a single automated action"""
        action_type = action["type"]
        params = action.get("params", {})

        if action_type == "pause_withdrawals":
            if self.emergency_shutdown:
                await self.emergency_shutdown("pause_withdrawals")
            incident.add_timeline("Withdrawals paused", "system")

        elif action_type == "notify_team":
            channel = params.get("channel", "security")
            if self.notify:
                await self.notify(
                    channel,
                    f"🚨 INCIDENT: {incident.title}",
                    {"incident_id": incident.id, "severity": incident.severity.value}
                )

        elif action_type == "capture_logs":
            # Would capture relevant logs
            incident.add_timeline("Logs captured", "system")

        elif action_type == "enable_rate_limiting":
            # Would enable aggressive rate limiting
            incident.add_timeline("Rate limiting enabled", "system")

        elif action_type == "activate_ddos_protection":
            # Would activate CDN DDoS protection
            incident.add_timeline("DDoS protection activated", "system")

    # =========================================================================
    # NOTIFICATIONS
    # =========================================================================

    async def _notify_incident(
        self,
        incident: Incident,
        event: str
    ):
        """Send incident notifications"""
        if not self.notify:
            return

        message = self._format_incident_message(incident, event)
        channels = self._get_notification_channels(incident)

        for channel in channels:
            try:
                await self.notify(channel, message, {
                    "incident_id": incident.id,
                    "severity": incident.severity.value,
                    "type": incident.type.value
                })
            except Exception as e:
                logger.error(f"Failed to notify {channel}: {e}")

    def _format_incident_message(self, incident: Incident, event: str) -> str:
        severity_emoji = {
            IncidentSeverity.P1: "🔴",
            IncidentSeverity.P2: "🟠",
            IncidentSeverity.P3: "🟡",
            IncidentSeverity.P4: "🟢"
        }

        return (
            f"{severity_emoji[incident.severity]} "
            f"**[{incident.severity.value.upper()}] {incident.title}**\n"
            f"Status: {incident.status.value}\n"
            f"Type: {incident.type.value}\n"
            f"ID: {incident.id}"
        )

    def _get_notification_channels(self, incident: Incident) -> List[str]:
        """Get notification channels based on severity"""
        channels = ["slack-security"]

        if incident.severity == IncidentSeverity.P1:
            channels.extend(["pagerduty", "sms-oncall", "email-founders"])
        elif incident.severity == IncidentSeverity.P2:
            channels.append("pagerduty")

        return channels

    # =========================================================================
    # VIEWS
    # =========================================================================

    async def get_incident(self, incident_id: str) -> Optional[Incident]:
        """Get incident by ID"""
        return self.incidents.get(incident_id)

    async def get_active_incidents(self) -> List[Incident]:
        """Get all active (unresolved) incidents"""
        return [
            i for i in self.incidents.values()
            if i.status not in [IncidentStatus.RESOLVED, IncidentStatus.CLOSED]
        ]

    async def get_incidents_by_severity(
        self,
        severity: IncidentSeverity
    ) -> List[Incident]:
        """Get incidents by severity"""
        return [i for i in self.incidents.values() if i.severity == severity]

    async def get_incident_metrics(self) -> Dict[str, Any]:
        """Get incident metrics"""
        now = datetime.utcnow()
        last_24h = now - timedelta(hours=24)
        last_7d = now - timedelta(days=7)

        all_incidents = list(self.incidents.values())
        recent_24h = [i for i in all_incidents if i.detected_at >= last_24h]
        recent_7d = [i for i in all_incidents if i.detected_at >= last_7d]

        # Calculate MTTR (Mean Time To Resolve)
        resolved = [
            i for i in all_incidents
            if i.resolved_at and i.acknowledged_at
        ]
        if resolved:
            total_time = sum(
                (i.resolved_at - i.acknowledged_at).total_seconds()
                for i in resolved
            )
            mttr = total_time / len(resolved) / 60  # In minutes
        else:
            mttr = 0

        return {
            "total_incidents": len(all_incidents),
            "active_incidents": len([i for i in all_incidents if i.status not in [IncidentStatus.RESOLVED, IncidentStatus.CLOSED]]),
            "last_24h": len(recent_24h),
            "last_7d": len(recent_7d),
            "by_severity": {
                s.value: len([i for i in all_incidents if i.severity == s])
                for s in IncidentSeverity
            },
            "by_type": {
                t.value: len([i for i in all_incidents if i.type == t])
                for t in IncidentType
            },
            "mttr_minutes": round(mttr, 2)
        }


# =============================================================================
# API ENDPOINTS
# =============================================================================

def create_incident_endpoints(manager: IncidentResponseManager):
    """Create API endpoints for incident management"""
    from fastapi import APIRouter, HTTPException
    from pydantic import BaseModel

    router = APIRouter(prefix="/api/incidents", tags=["Incident Response"])

    class CreateIncidentRequest(BaseModel):
        type: str
        severity: str
        title: str
        description: str

    class UpdateStatusRequest(BaseModel):
        status: str
        notes: str = ""

    class ResolveRequest(BaseModel):
        root_cause: str
        resolution_notes: str

    @router.get("")
    async def list_incidents(active_only: bool = True):
        """List incidents"""
        if active_only:
            incidents = await manager.get_active_incidents()
        else:
            incidents = list(manager.incidents.values())

        return [_format_incident(i) for i in incidents]

    @router.get("/metrics")
    async def get_metrics():
        """Get incident metrics"""
        return await manager.get_incident_metrics()

    @router.get("/{incident_id}")
    async def get_incident(incident_id: str):
        """Get incident details"""
        incident = await manager.get_incident(incident_id)
        if not incident:
            raise HTTPException(status_code=404, detail="Incident not found")
        return _format_incident(incident, include_timeline=True)

    @router.post("")
    async def create_incident(request: CreateIncidentRequest):
        """Create a new incident"""
        incident = await manager.create_incident(
            incident_type=IncidentType(request.type),
            severity=IncidentSeverity(request.severity),
            title=request.title,
            description=request.description
        )
        return {"incident_id": incident.id}

    @router.post("/{incident_id}/acknowledge")
    async def acknowledge(incident_id: str, responder: str):
        """Acknowledge an incident"""
        try:
            incident = await manager.acknowledge_incident(incident_id, responder)
            return {"status": incident.status.value}
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

    @router.put("/{incident_id}/status")
    async def update_status(incident_id: str, actor: str, request: UpdateStatusRequest):
        """Update incident status"""
        try:
            incident = await manager.update_incident_status(
                incident_id,
                IncidentStatus(request.status),
                actor,
                request.notes
            )
            return {"status": incident.status.value}
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

    @router.post("/{incident_id}/resolve")
    async def resolve(incident_id: str, resolver: str, request: ResolveRequest):
        """Resolve an incident"""
        try:
            incident = await manager.resolve_incident(
                incident_id,
                resolver,
                request.root_cause,
                request.resolution_notes
            )
            return {"status": incident.status.value}
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

    def _format_incident(incident: Incident, include_timeline: bool = False) -> Dict:
        result = {
            "id": incident.id,
            "type": incident.type.value,
            "severity": incident.severity.value,
            "title": incident.title,
            "description": incident.description,
            "status": incident.status.value,
            "detected_at": incident.detected_at.isoformat(),
            "acknowledged_at": incident.acknowledged_at.isoformat() if incident.acknowledged_at else None,
            "resolved_at": incident.resolved_at.isoformat() if incident.resolved_at else None,
            "assigned_to": incident.assigned_to,
            "actions_taken": incident.actions_taken
        }

        if include_timeline:
            result["timeline"] = [
                {
                    "timestamp": t.timestamp.isoformat(),
                    "action": t.action,
                    "actor": t.actor,
                    "details": t.details
                }
                for t in incident.timeline
            ]

        return result

    return router
