"""
Inter-Agent Task Handoff System

Enables Matt, Friday, and Jarvis agents to delegate tasks to each other
asynchronously via shared file-based state.

Part of the KR8TIV multi-agent coordination protocol.
"""

import json
import logging
import os
import tempfile
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

import filelock

logger = logging.getLogger("jarvis.coordination.handoff")

# Valid agent identifiers per protocol
VALID_AGENTS = {"matt", "friday", "jarvis"}


class HandoffStatus(Enum):
    """Status of a handoff in its lifecycle."""
    PENDING = "pending"
    ACCEPTED = "accepted"
    IN_PROGRESS = "in_progress"
    BLOCKED = "blocked"
    COMPLETED = "completed"
    REJECTED = "rejected"


class HandoffType(Enum):
    """Type of handoff/task."""
    IMPLEMENTATION = "implementation"
    REVIEW = "review"
    APPROVAL = "approval"
    ESCALATION = "escalation"
    COLLABORATION = "collaboration"


class HandoffPriority(Enum):
    """Priority level for handoffs."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class HandoffError(Exception):
    """Raised when a handoff operation fails."""
    pass


@dataclass
class Handoff:
    """
    A handoff from one agent to another.

    Represents a task being delegated between Matt, Friday, and Jarvis.
    """
    id: str
    from_agent: str
    to_agent: str
    task_id: str
    priority: HandoffPriority
    context: Dict[str, Any] = field(default_factory=dict)
    status: HandoffStatus = HandoffStatus.PENDING
    handoff_type: HandoffType = HandoffType.IMPLEMENTATION
    created_at: Optional[str] = None
    accepted_at: Optional[str] = None
    completed_at: Optional[str] = None
    result: Optional[Dict[str, Any]] = None
    status_history: List[Dict[str, Any]] = field(default_factory=list)

    def __post_init__(self):
        """Initialize defaults."""
        if self.created_at is None:
            self.created_at = datetime.now(timezone.utc).isoformat()
        if not self.status_history:
            self.status_history = [{
                "status": self.status.value,
                "timestamp": self.created_at,
                "note": f"Created by {self.from_agent}",
            }]

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "id": self.id,
            "from": self.from_agent,
            "to": self.to_agent,
            "task_id": self.task_id,
            "priority": self.priority.value,
            "type": self.handoff_type.value,
            "status": self.status.value,
            "context": self.context,
            "created_at": self.created_at,
            "accepted_at": self.accepted_at,
            "completed_at": self.completed_at,
            "result": self.result,
            "status_history": self.status_history,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Handoff":
        """Deserialize from dictionary."""
        return cls(
            id=data["id"],
            from_agent=data.get("from", data.get("from_agent", "")),
            to_agent=data.get("to", data.get("to_agent", "")),
            task_id=data["task_id"],
            priority=HandoffPriority(data.get("priority", "medium")),
            context=data.get("context", {}),
            status=HandoffStatus(data.get("status", "pending")),
            handoff_type=HandoffType(data.get("type", "implementation")),
            created_at=data.get("created_at"),
            accepted_at=data.get("accepted_at"),
            completed_at=data.get("completed_at"),
            result=data.get("result"),
            status_history=data.get("status_history", []),
        )


class TaskHandoff:
    """
    Manages inter-agent task handoffs.

    Provides methods for creating, accepting, rejecting, and completing
    handoffs between Matt, Friday, and Jarvis agents.

    Uses atomic file operations for safe concurrent access.
    """

    def __init__(
        self,
        data_dir: Optional[Path] = None,
        handoff_file: str = "handoffs.json",
    ):
        """
        Initialize the TaskHandoff manager.

        Args:
            data_dir: Directory for storing handoff state
            handoff_file: Name of the JSON file for handoffs
        """
        if data_dir is None:
            # Default to planning directory
            data_dir = Path(os.path.expanduser("~/.lifeos/coordination/handoffs"))

        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)

        self.handoff_file = self.data_dir / handoff_file
        self._lock = filelock.FileLock(self.data_dir / ".handoff.lock")

        # Initialize file if it doesn't exist
        if not self.handoff_file.exists():
            self._save_state({"handoffs": [], "archived": []})

        logger.info(f"TaskHandoff initialized at {self.data_dir}")

    def _load_state(self) -> Dict[str, Any]:
        """Load handoff state from disk."""
        try:
            with open(self.handoff_file, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError) as e:
            logger.error(f"Failed to load handoff state: {e}")
            return {"handoffs": [], "archived": []}

    def _save_state(self, data: Dict[str, Any]) -> None:
        """Atomically save handoff state to disk."""
        temp_fd, temp_path = tempfile.mkstemp(
            dir=self.data_dir,
            suffix=".json.tmp"
        )
        try:
            with os.fdopen(temp_fd, "w") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            os.replace(temp_path, self.handoff_file)
        except Exception as e:
            if os.path.exists(temp_path):
                os.unlink(temp_path)
            raise e

    def _generate_handoff_id(self) -> str:
        """Generate a unique handoff ID."""
        return f"handoff_{uuid.uuid4().hex[:8]}"

    def _generate_task_id(self) -> str:
        """Generate a unique task ID."""
        return f"task_{uuid.uuid4().hex[:8]}"

    def _validate_agent(self, agent: str) -> None:
        """Validate that agent is one of the valid agents."""
        if agent not in VALID_AGENTS:
            raise HandoffError(
                f"Invalid agent '{agent}'. Must be one of: {VALID_AGENTS}"
            )

    def create_handoff(
        self,
        from_agent: str,
        to_agent: str,
        task: str,
        context: Dict[str, Any],
        priority: HandoffPriority = HandoffPriority.MEDIUM,
        handoff_type: HandoffType = HandoffType.IMPLEMENTATION,
        deadline: Optional[str] = None,
    ) -> str:
        """
        Create a new handoff from one agent to another.

        Args:
            from_agent: Agent creating the handoff (matt/friday/jarvis)
            to_agent: Agent receiving the handoff (matt/friday/jarvis)
            task: Description of the task
            context: Additional context dictionary
            priority: Priority level
            handoff_type: Type of handoff
            deadline: Optional ISO8601 deadline

        Returns:
            The handoff ID

        Raises:
            HandoffError: If validation fails
        """
        # Validate agents
        self._validate_agent(from_agent)
        self._validate_agent(to_agent)

        # Cannot handoff to self
        if from_agent == to_agent:
            raise HandoffError("Cannot create handoff to self")

        # Task cannot be empty
        if not task or not task.strip():
            raise HandoffError("Task description cannot be empty")

        handoff_id = self._generate_handoff_id()
        task_id = self._generate_task_id()

        # Build context with task description
        full_context = {
            "summary": task,
            **context,
        }
        if deadline:
            full_context["deadline"] = deadline

        handoff = Handoff(
            id=handoff_id,
            from_agent=from_agent,
            to_agent=to_agent,
            task_id=task_id,
            priority=priority,
            context=full_context,
            handoff_type=handoff_type,
        )

        with self._lock:
            state = self._load_state()
            state["handoffs"].append(handoff.to_dict())
            self._save_state(state)

        logger.info(
            f"Created handoff {handoff_id}: {from_agent} -> {to_agent} "
            f"({priority.value})"
        )

        return handoff_id

    def accept_handoff(self, agent: str, handoff_id: str) -> bool:
        """
        Accept a pending handoff.

        Args:
            agent: Agent accepting the handoff
            handoff_id: ID of the handoff to accept

        Returns:
            True if accepted, False otherwise
        """
        with self._lock:
            state = self._load_state()

            for i, h_data in enumerate(state["handoffs"]):
                if h_data["id"] == handoff_id:
                    # Verify this agent is the recipient
                    if h_data.get("to") != agent:
                        logger.warning(
                            f"Agent {agent} cannot accept handoff "
                            f"assigned to {h_data.get('to')}"
                        )
                        return False

                    # Verify handoff is pending
                    if h_data["status"] != HandoffStatus.PENDING.value:
                        logger.warning(
                            f"Cannot accept handoff with status {h_data['status']}"
                        )
                        return False

                    # Update status
                    now = datetime.now(timezone.utc).isoformat()
                    h_data["status"] = HandoffStatus.ACCEPTED.value
                    h_data["accepted_at"] = now
                    h_data["status_history"].append({
                        "status": HandoffStatus.ACCEPTED.value,
                        "timestamp": now,
                        "note": f"Accepted by {agent}",
                    })

                    state["handoffs"][i] = h_data
                    self._save_state(state)

                    logger.info(f"Handoff {handoff_id} accepted by {agent}")
                    return True

            logger.warning(f"Handoff {handoff_id} not found")
            return False

    def reject_handoff(
        self,
        agent: str,
        handoff_id: str,
        reason: str,
    ) -> bool:
        """
        Reject a pending handoff.

        Args:
            agent: Agent rejecting the handoff
            handoff_id: ID of the handoff to reject
            reason: Reason for rejection

        Returns:
            True if rejected, False otherwise
        """
        with self._lock:
            state = self._load_state()

            for i, h_data in enumerate(state["handoffs"]):
                if h_data["id"] == handoff_id:
                    # Verify this agent is the recipient
                    if h_data.get("to") != agent:
                        logger.warning(
                            f"Agent {agent} cannot reject handoff "
                            f"assigned to {h_data.get('to')}"
                        )
                        return False

                    # Verify handoff is pending
                    if h_data["status"] != HandoffStatus.PENDING.value:
                        logger.warning(
                            f"Cannot reject handoff with status {h_data['status']}"
                        )
                        return False

                    # Update status
                    now = datetime.now(timezone.utc).isoformat()
                    h_data["status"] = HandoffStatus.REJECTED.value
                    h_data["status_history"].append({
                        "status": HandoffStatus.REJECTED.value,
                        "timestamp": now,
                        "note": f"Rejected by {agent}: {reason}",
                    })

                    state["handoffs"][i] = h_data
                    self._save_state(state)

                    logger.info(
                        f"Handoff {handoff_id} rejected by {agent}: {reason}"
                    )
                    return True

            logger.warning(f"Handoff {handoff_id} not found")
            return False

    def complete_handoff(
        self,
        agent: str,
        handoff_id: str,
        outcome: str = "success",
        artifacts: Optional[List[str]] = None,
        notes: Optional[str] = None,
    ) -> bool:
        """
        Mark a handoff as completed.

        Args:
            agent: Agent completing the handoff
            handoff_id: ID of the handoff
            outcome: Result outcome (success/failure/partial)
            artifacts: List of output file paths
            notes: Additional completion notes

        Returns:
            True if completed, False otherwise
        """
        with self._lock:
            state = self._load_state()

            for i, h_data in enumerate(state["handoffs"]):
                if h_data["id"] == handoff_id:
                    # Verify this agent is the recipient
                    if h_data.get("to") != agent:
                        logger.warning(
                            f"Agent {agent} cannot complete handoff "
                            f"assigned to {h_data.get('to')}"
                        )
                        return False

                    # Update status
                    now = datetime.now(timezone.utc).isoformat()
                    h_data["status"] = HandoffStatus.COMPLETED.value
                    h_data["completed_at"] = now
                    h_data["result"] = {
                        "outcome": outcome,
                        "artifacts": artifacts or [],
                        "notes": notes or "",
                    }
                    h_data["status_history"].append({
                        "status": HandoffStatus.COMPLETED.value,
                        "timestamp": now,
                        "note": f"Completed by {agent}: {outcome}",
                    })

                    state["handoffs"][i] = h_data
                    self._save_state(state)

                    logger.info(
                        f"Handoff {handoff_id} completed by {agent}: {outcome}"
                    )
                    return True

            logger.warning(f"Handoff {handoff_id} not found")
            return False

    def get_pending_handoffs(self, agent: str) -> List[Handoff]:
        """
        Get all pending handoffs for an agent.

        Args:
            agent: Agent to get handoffs for

        Returns:
            List of pending Handoff objects
        """
        with self._lock:
            state = self._load_state()

            pending = []
            for h_data in state["handoffs"]:
                if (h_data.get("to") == agent and
                    h_data["status"] == HandoffStatus.PENDING.value):
                    pending.append(Handoff.from_dict(h_data))

            return pending

    def get_handoff(self, handoff_id: str) -> Optional[Handoff]:
        """
        Get a specific handoff by ID.

        Args:
            handoff_id: ID of the handoff

        Returns:
            Handoff object or None if not found
        """
        with self._lock:
            state = self._load_state()

            for h_data in state["handoffs"]:
                if h_data["id"] == handoff_id:
                    return Handoff.from_dict(h_data)

            return None

    def get_all_handoffs(
        self,
        status: Optional[HandoffStatus] = None,
    ) -> List[Handoff]:
        """
        Get all handoffs, optionally filtered by status.

        Args:
            status: Optional status filter

        Returns:
            List of Handoff objects
        """
        with self._lock:
            state = self._load_state()

            handoffs = []
            for h_data in state["handoffs"]:
                if status is None or h_data["status"] == status.value:
                    handoffs.append(Handoff.from_dict(h_data))

            return handoffs

    def get_handoffs_from_agent(self, agent: str) -> List[Handoff]:
        """
        Get all handoffs created by an agent.

        Args:
            agent: Agent who created the handoffs

        Returns:
            List of Handoff objects
        """
        with self._lock:
            state = self._load_state()

            handoffs = []
            for h_data in state["handoffs"]:
                if h_data.get("from") == agent:
                    handoffs.append(Handoff.from_dict(h_data))

            return handoffs
