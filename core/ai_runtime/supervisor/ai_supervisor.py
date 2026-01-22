"""
AI Supervisor

Correlates insights from all agents and manages human-approval workflow.
This is the ONLY agent that can propose actions to be reviewed by humans.
"""
import asyncio
import logging
import json
from typing import Dict, Any, List, Optional
from datetime import datetime
from dataclasses import dataclass, field
from pathlib import Path
import uuid

from ..bus.socket_bus import SecureMessageBus, BusMessage
from ..memory.store import MemoryStore
from ..config import AIRuntimeConfig
from .correlator import InsightCorrelator

logger = logging.getLogger(__name__)


@dataclass
class PendingAction:
    """An action waiting for human approval."""

    action_id: str
    action_type: str
    description: str
    proposed_by: str
    evidence: List[Dict[str, Any]]
    confidence: float
    created_at: datetime
    status: str = "pending"  # pending, approved, rejected


@dataclass
class SupervisorState:
    """Current state of the supervisor."""

    active_agents: List[str] = field(default_factory=list)
    insight_count: int = 0
    pending_actions: List[PendingAction] = field(default_factory=list)
    last_report_time: Optional[datetime] = None


class AISupervisor:
    """
    Central coordinator for all AI agents.

    Responsibilities:
    1. Receive and correlate insights from agents
    2. Detect patterns across components
    3. Propose actions for human review
    4. NEVER take autonomous action

    All actions require human approval through:
    - CLI commands (now)
    - Admin dashboard (future)
    """

    def __init__(
        self,
        config: AIRuntimeConfig,
        bus: SecureMessageBus,
        memory: MemoryStore,
    ):
        self.config = config
        self.bus = bus
        self.memory = memory
        self.state = SupervisorState()
        self._running = False
        self.correlator = InsightCorrelator(correlation_window_minutes=5)
        self._correlation_task: Optional[asyncio.Task] = None

        # Register as message handler
        self.bus.register_handler("supervisor", self._handle_message)

    async def _handle_message(self, msg: BusMessage):
        """Handle incoming message from an agent."""
        logger.info(f"Supervisor received {msg.msg_type} from {msg.from_agent}")

        if msg.msg_type == "insight":
            await self._process_insight(msg.from_agent, msg.payload)
        elif msg.msg_type == "error":
            await self._process_error(msg.from_agent, msg.payload)

    async def _process_insight(self, agent: str, payload: Dict[str, Any]):
        """Process an insight from an agent."""
        self.state.insight_count += 1

        insight = {
            "agent": agent,
            "timestamp": datetime.utcnow().isoformat(),
            "payload": payload,
        }

        # Add to correlator
        self.correlator.add_insight(insight)

        # Store in memory
        await self.memory.store(
            namespace=f"supervisor.insights.{agent}",
            key=f"{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}",
            value=json.dumps(insight),
        )

        # Immediate action check for high-confidence errors
        if payload.get("insight", {}).get("insight_type") == "error":
            confidence = payload.get("insight", {}).get("confidence", 0)
            if confidence > 0.9:
                await self._propose_action(
                    action_type="investigate_error",
                    description=payload.get("insight", {}).get("summary", "Unknown error"),
                    proposed_by=agent,
                    evidence=[insight],
                    confidence=confidence,
                )

    async def _process_error(self, agent: str, payload: Dict[str, Any]):
        """Process an error report from an agent."""
        logger.error(f"Agent {agent} reported error: {payload}")

        # Log for human review
        await self.memory.store(
            namespace="supervisor.errors",
            key=f"{agent}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}",
            value=json.dumps(payload),
        )

    async def _propose_action(
        self,
        action_type: str,
        description: str,
        proposed_by: str,
        evidence: List[Dict[str, Any]],
        confidence: float,
    ):
        """
        Propose an action for human review.

        Actions are NEVER executed automatically.
        They go into a queue for human approval.
        """
        action = PendingAction(
            action_id=str(uuid.uuid4())[:8],
            action_type=action_type,
            description=description,
            proposed_by=proposed_by,
            evidence=evidence,
            confidence=confidence,
            created_at=datetime.utcnow(),
        )

        self.state.pending_actions.append(action)

        # Persist to disk
        actions_file = Path(self.config.log_path).parent / "pending_actions.json"
        actions_file.parent.mkdir(parents=True, exist_ok=True)

        pending = [
            {
                "id": a.action_id,
                "type": a.action_type,
                "description": a.description,
                "proposed_by": a.proposed_by,
                "confidence": a.confidence,
                "created_at": a.created_at.isoformat(),
                "status": a.status,
            }
            for a in self.state.pending_actions
            if a.status == "pending"
        ]

        actions_file.write_text(json.dumps(pending, indent=2))
        logger.info(f"Action proposed: [{action.action_id}] {description}")

    async def correlate_insights(self):
        """
        Periodically correlate insights to find patterns.

        This runs in the background and looks for:
        - Repeated errors across components
        - Performance degradation patterns
        - UX friction signals
        """
        correlation_interval = 300  # 5 minutes

        while self._running:
            await asyncio.sleep(correlation_interval)

            if self.correlator.get_buffer_size() < 3:
                continue

            # Check for error clusters
            error_clusters = self.correlator.find_error_clusters()
            for cluster in error_clusters:
                await self._propose_action(
                    action_type="error_cluster",
                    description=f"Detected {cluster['error_count']} related errors across {len(cluster['agents'])} agents",
                    proposed_by="supervisor",
                    evidence=cluster["evidence"],
                    confidence=0.8,
                )

            # Check for patterns
            patterns = self.correlator.find_patterns()
            for pattern in patterns:
                if pattern["pattern_type"] == "latency_spike":
                    await self._propose_action(
                        action_type="performance_issue",
                        description=f"Latency spike detected across {len(pattern['affected_agents'])} components",
                        proposed_by="supervisor",
                        evidence=pattern["evidence"],
                        confidence=0.7,
                    )

            # Update report time
            self.state.last_report_time = datetime.utcnow()

    async def start(self):
        """Start the supervisor."""
        self._running = True
        logger.info("AI Supervisor started")

        # Start correlation task
        self._correlation_task = asyncio.create_task(self.correlate_insights())

    async def stop(self):
        """Stop the supervisor."""
        self._running = False

        if self._correlation_task:
            self._correlation_task.cancel()
            try:
                await self._correlation_task
            except asyncio.CancelledError:
                pass

        logger.info("AI Supervisor stopped")

    def get_status(self) -> Dict[str, Any]:
        """Get current supervisor status."""
        return {
            "running": self._running,
            "active_agents": self.state.active_agents,
            "insight_count": self.state.insight_count,
            "pending_actions": len(
                [a for a in self.state.pending_actions if a.status == "pending"]
            ),
            "last_report": (
                self.state.last_report_time.isoformat()
                if self.state.last_report_time
                else None
            ),
            "buffer_size": self.correlator.get_buffer_size(),
        }

    # CLI Interface for human control

    async def list_pending_actions(self) -> List[Dict[str, Any]]:
        """List all pending actions for human review."""
        return [
            {
                "id": a.action_id,
                "type": a.action_type,
                "description": a.description,
                "confidence": f"{a.confidence:.0%}",
                "age": str(datetime.utcnow() - a.created_at),
            }
            for a in self.state.pending_actions
            if a.status == "pending"
        ]

    async def approve_action(self, action_id: str) -> bool:
        """Approve a pending action (marks for execution by human)."""
        for action in self.state.pending_actions:
            if action.action_id == action_id and action.status == "pending":
                action.status = "approved"
                logger.info(f"Action {action_id} approved")
                return True
        return False

    async def reject_action(self, action_id: str) -> bool:
        """Reject a pending action."""
        for action in self.state.pending_actions:
            if action.action_id == action_id and action.status == "pending":
                action.status = "rejected"
                logger.info(f"Action {action_id} rejected")
                return True
        return False

    def register_agent(self, agent_name: str):
        """Register an active agent."""
        if agent_name not in self.state.active_agents:
            self.state.active_agents.append(agent_name)
            logger.info(f"Agent {agent_name} registered with supervisor")
