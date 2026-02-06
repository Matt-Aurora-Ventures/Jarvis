"""
Whiteboard - Shared Task Coordination System

A whiteboard for Matt, Friday, and Jarvis agents to post, claim, and
complete tasks. Wraps active_tasks.json with atomic operations.

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

logger = logging.getLogger("jarvis.coordination.whiteboard")

# Valid agent identifiers per protocol
VALID_AGENTS = {"matt", "friday", "jarvis"}


class TaskStatus(Enum):
    """Status of a task on the whiteboard."""
    UNCLAIMED = "unclaimed"
    CLAIMED = "claimed"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


class AgentStatus(Enum):
    """Status of an agent."""
    ONLINE = "online"
    OFFLINE = "offline"
    BUSY = "busy"
    ERROR = "error"
    MAINTENANCE = "maintenance"


class WhiteboardError(Exception):
    """Raised when a whiteboard operation fails."""
    pass


@dataclass
class Task:
    """
    A task on the whiteboard.

    Tasks can be posted by any agent and claimed by others.
    """
    id: str
    description: str
    posted_by: str
    status: TaskStatus = TaskStatus.UNCLAIMED
    claimed_by: Optional[str] = None
    priority: str = "medium"
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: Optional[str] = None
    claimed_at: Optional[str] = None
    completed_at: Optional[str] = None
    result: Optional[str] = None
    artifacts: List[str] = field(default_factory=list)
    failure_reason: Optional[str] = None

    def __post_init__(self):
        """Initialize defaults."""
        if self.created_at is None:
            self.created_at = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "id": self.id,
            "description": self.description,
            "posted_by": self.posted_by,
            "status": self.status.value,
            "claimed_by": self.claimed_by,
            "priority": self.priority,
            "metadata": self.metadata,
            "created_at": self.created_at,
            "claimed_at": self.claimed_at,
            "completed_at": self.completed_at,
            "result": self.result,
            "artifacts": self.artifacts,
            "failure_reason": self.failure_reason,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Task":
        """Deserialize from dictionary."""
        return cls(
            id=data["id"],
            description=data["description"],
            posted_by=data["posted_by"],
            status=TaskStatus(data.get("status", "unclaimed")),
            claimed_by=data.get("claimed_by"),
            priority=data.get("priority", "medium"),
            metadata=data.get("metadata", {}),
            created_at=data.get("created_at"),
            claimed_at=data.get("claimed_at"),
            completed_at=data.get("completed_at"),
            result=data.get("result"),
            artifacts=data.get("artifacts", []),
            failure_reason=data.get("failure_reason"),
        )


@dataclass
class SystemFlags:
    """
    System-wide flags for coordination.

    Controls emergency stops, rate limits, and maintenance modes.
    """
    emergency_stop: bool = False
    rate_limit_active: bool = False
    maintenance_mode: bool = False

    def to_dict(self) -> Dict[str, bool]:
        """Serialize to dictionary."""
        return {
            "emergency_stop": self.emergency_stop,
            "rate_limit_active": self.rate_limit_active,
            "maintenance_mode": self.maintenance_mode,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SystemFlags":
        """Deserialize from dictionary."""
        return cls(
            emergency_stop=data.get("emergency_stop", False),
            rate_limit_active=data.get("rate_limit_active", False),
            maintenance_mode=data.get("maintenance_mode", False),
        )


class Whiteboard:
    """
    Shared whiteboard for task coordination.

    Wraps active_tasks.json with atomic file operations for safe
    concurrent access by Matt, Friday, and Jarvis agents.
    """

    def __init__(
        self,
        data_dir: Optional[Path] = None,
        tasks_file: str = "active_tasks.json",
    ):
        """
        Initialize the Whiteboard.

        Args:
            data_dir: Directory for storing whiteboard state
            tasks_file: Name of the JSON file for tasks
        """
        if data_dir is None:
            # Default to planning directory
            data_dir = Path(os.path.expanduser("~/.lifeos/coordination"))

        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)

        self.tasks_file = self.data_dir / tasks_file
        self._lock = filelock.FileLock(self.data_dir / ".whiteboard.lock")

        # Initialize file if it doesn't exist
        if not self.tasks_file.exists():
            self._save_state(self._default_state())

        logger.info(f"Whiteboard initialized at {self.data_dir}")

    def _default_state(self) -> Dict[str, Any]:
        """Return default whiteboard state."""
        return {
            "last_updated": datetime.now(timezone.utc).isoformat(),
            "active_agents": {},
            "tasks": [],
            "completed_tasks": [],
            "system_flags": SystemFlags().to_dict(),
        }

    def _load_state(self) -> Dict[str, Any]:
        """Load whiteboard state from disk."""
        try:
            with open(self.tasks_file, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError) as e:
            logger.error(f"Failed to load whiteboard state: {e}")
            return self._default_state()

    def _save_state(self, data: Dict[str, Any]) -> None:
        """Atomically save whiteboard state to disk."""
        data["last_updated"] = datetime.now(timezone.utc).isoformat()

        temp_fd, temp_path = tempfile.mkstemp(
            dir=self.data_dir,
            suffix=".json.tmp"
        )
        try:
            with os.fdopen(temp_fd, "w") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            os.replace(temp_path, self.tasks_file)
        except Exception as e:
            if os.path.exists(temp_path):
                os.unlink(temp_path)
            raise e

    def _generate_task_id(self) -> str:
        """Generate a unique task ID."""
        return f"task_{uuid.uuid4().hex[:8]}"

    def _validate_agent(self, agent: str) -> None:
        """Validate that agent is one of the valid agents."""
        if agent not in VALID_AGENTS:
            raise WhiteboardError(
                f"Invalid agent '{agent}'. Must be one of: {VALID_AGENTS}"
            )

    def post_task(
        self,
        agent: str,
        task: str,
        priority: str = "medium",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Post a new task to the whiteboard.

        Args:
            agent: Agent posting the task
            task: Task description
            priority: Priority level (critical/high/medium/low)
            metadata: Additional task metadata

        Returns:
            The task ID

        Raises:
            WhiteboardError: If validation fails
        """
        self._validate_agent(agent)

        if not task or not task.strip():
            raise WhiteboardError("Task description cannot be empty")

        task_id = self._generate_task_id()

        new_task = Task(
            id=task_id,
            description=task,
            posted_by=agent,
            priority=priority,
            metadata=metadata or {},
        )

        with self._lock:
            state = self._load_state()
            state["tasks"].append(new_task.to_dict())
            self._save_state(state)

        logger.info(f"Task {task_id} posted by {agent}: {task[:50]}...")

        return task_id

    def claim_task(self, agent: str, task_id: str) -> bool:
        """
        Claim a task from the whiteboard.

        Args:
            agent: Agent claiming the task
            task_id: ID of the task to claim

        Returns:
            True if claimed, False otherwise
        """
        with self._lock:
            state = self._load_state()

            # Check emergency stop
            flags = SystemFlags.from_dict(state.get("system_flags", {}))
            if flags.emergency_stop:
                logger.warning(
                    f"Cannot claim task during emergency stop"
                )
                return False

            for i, t_data in enumerate(state["tasks"]):
                if t_data["id"] == task_id:
                    # Check if already claimed
                    if t_data["status"] != TaskStatus.UNCLAIMED.value:
                        logger.warning(
                            f"Task {task_id} already claimed by "
                            f"{t_data.get('claimed_by')}"
                        )
                        return False

                    # Claim the task
                    now = datetime.now(timezone.utc).isoformat()
                    t_data["status"] = TaskStatus.CLAIMED.value
                    t_data["claimed_by"] = agent
                    t_data["claimed_at"] = now

                    state["tasks"][i] = t_data
                    self._save_state(state)

                    logger.info(f"Task {task_id} claimed by {agent}")
                    return True

            logger.warning(f"Task {task_id} not found")
            return False

    def complete_task(
        self,
        task_id: str,
        result: Optional[str] = None,
        artifacts: Optional[List[str]] = None,
    ) -> bool:
        """
        Mark a task as completed.

        Args:
            task_id: ID of the task
            result: Result description
            artifacts: List of output file paths

        Returns:
            True if completed, False otherwise
        """
        with self._lock:
            state = self._load_state()

            for i, t_data in enumerate(state["tasks"]):
                if t_data["id"] == task_id:
                    # Must be claimed first
                    if t_data["status"] not in (
                        TaskStatus.CLAIMED.value,
                        TaskStatus.IN_PROGRESS.value
                    ):
                        logger.warning(
                            f"Cannot complete unclaimed task {task_id}"
                        )
                        return False

                    # Complete the task
                    now = datetime.now(timezone.utc).isoformat()
                    t_data["status"] = TaskStatus.COMPLETED.value
                    t_data["completed_at"] = now
                    if result:
                        t_data["result"] = result
                    if artifacts:
                        t_data["artifacts"] = artifacts

                    # Move to completed
                    state["tasks"].pop(i)
                    state["completed_tasks"].append(t_data)
                    self._save_state(state)

                    logger.info(f"Task {task_id} completed")
                    return True

            logger.warning(f"Task {task_id} not found")
            return False

    def fail_task(self, task_id: str, reason: str) -> bool:
        """
        Mark a task as failed.

        Args:
            task_id: ID of the task
            reason: Reason for failure

        Returns:
            True if marked as failed, False otherwise
        """
        with self._lock:
            state = self._load_state()

            for i, t_data in enumerate(state["tasks"]):
                if t_data["id"] == task_id:
                    now = datetime.now(timezone.utc).isoformat()
                    t_data["status"] = TaskStatus.FAILED.value
                    t_data["completed_at"] = now
                    t_data["failure_reason"] = reason

                    # Move to completed (failed)
                    state["tasks"].pop(i)
                    state["completed_tasks"].append(t_data)
                    self._save_state(state)

                    logger.info(f"Task {task_id} failed: {reason}")
                    return True

            logger.warning(f"Task {task_id} not found")
            return False

    def get_task(self, task_id: str) -> Optional[Task]:
        """
        Get a specific task by ID.

        Args:
            task_id: ID of the task

        Returns:
            Task object or None if not found
        """
        with self._lock:
            state = self._load_state()

            # Check active tasks
            for t_data in state["tasks"]:
                if t_data["id"] == task_id:
                    return Task.from_dict(t_data)

            # Check completed tasks
            for t_data in state.get("completed_tasks", []):
                if t_data["id"] == task_id:
                    return Task.from_dict(t_data)

            return None

    def get_active_tasks(self) -> List[Task]:
        """
        Get all active (non-completed) tasks.

        Returns:
            List of Task objects
        """
        with self._lock:
            state = self._load_state()

            return [Task.from_dict(t) for t in state["tasks"]]

    def get_completed_tasks(self, limit: int = 100) -> List[Task]:
        """
        Get completed tasks.

        Args:
            limit: Maximum number of tasks to return

        Returns:
            List of Task objects
        """
        with self._lock:
            state = self._load_state()

            completed = state.get("completed_tasks", [])[-limit:]
            return [Task.from_dict(t) for t in completed]

    # Agent Status Methods

    def update_agent_status(
        self,
        agent: str,
        status: AgentStatus,
        current_task: Optional[str] = None,
        health: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Update an agent's status.

        Args:
            agent: Agent identifier
            status: New status
            current_task: Current task description
            health: Health metrics
        """
        with self._lock:
            state = self._load_state()

            if "active_agents" not in state:
                state["active_agents"] = {}

            now = datetime.now(timezone.utc).isoformat()

            agent_data = state["active_agents"].get(agent, {})
            agent_data.update({
                "status": status.value,
                "last_heartbeat": now,
            })

            if current_task is not None:
                agent_data["current_task"] = current_task
            if health is not None:
                agent_data["health"] = health

            state["active_agents"][agent] = agent_data
            self._save_state(state)

    def heartbeat(self, agent: str) -> None:
        """
        Update agent heartbeat timestamp.

        Args:
            agent: Agent identifier
        """
        with self._lock:
            state = self._load_state()

            if "active_agents" not in state:
                state["active_agents"] = {}

            now = datetime.now(timezone.utc).isoformat()

            if agent in state["active_agents"]:
                state["active_agents"][agent]["last_heartbeat"] = now
            else:
                state["active_agents"][agent] = {
                    "status": AgentStatus.ONLINE.value,
                    "last_heartbeat": now,
                }

            self._save_state(state)

    def get_agent_status(self, agent: str) -> Dict[str, Any]:
        """
        Get an agent's status.

        Args:
            agent: Agent identifier

        Returns:
            Agent status dictionary
        """
        with self._lock:
            state = self._load_state()

            return state.get("active_agents", {}).get(agent, {
                "status": AgentStatus.OFFLINE.value,
            })

    def get_all_agent_statuses(self) -> Dict[str, Dict[str, Any]]:
        """
        Get all agent statuses.

        Returns:
            Dictionary of agent -> status
        """
        with self._lock:
            state = self._load_state()

            return state.get("active_agents", {})

    # System Flags Methods

    def get_system_flags(self) -> SystemFlags:
        """
        Get current system flags.

        Returns:
            SystemFlags object
        """
        with self._lock:
            state = self._load_state()

            return SystemFlags.from_dict(state.get("system_flags", {}))

    def set_emergency_stop(self, active: bool) -> None:
        """
        Set or clear emergency stop flag.

        Args:
            active: Whether emergency stop is active
        """
        with self._lock:
            state = self._load_state()

            if "system_flags" not in state:
                state["system_flags"] = SystemFlags().to_dict()

            state["system_flags"]["emergency_stop"] = active
            self._save_state(state)

        if active:
            logger.warning("EMERGENCY STOP ACTIVATED")
        else:
            logger.info("Emergency stop cleared")

    def set_maintenance_mode(self, active: bool) -> None:
        """
        Set or clear maintenance mode.

        Args:
            active: Whether maintenance mode is active
        """
        with self._lock:
            state = self._load_state()

            if "system_flags" not in state:
                state["system_flags"] = SystemFlags().to_dict()

            state["system_flags"]["maintenance_mode"] = active
            self._save_state(state)

        logger.info(f"Maintenance mode: {'ON' if active else 'OFF'}")

    def set_rate_limit_active(self, active: bool) -> None:
        """
        Set or clear rate limit flag.

        Args:
            active: Whether rate limiting is active
        """
        with self._lock:
            state = self._load_state()

            if "system_flags" not in state:
                state["system_flags"] = SystemFlags().to_dict()

            state["system_flags"]["rate_limit_active"] = active
            self._save_state(state)

        logger.info(f"Rate limit: {'ACTIVE' if active else 'inactive'}")
