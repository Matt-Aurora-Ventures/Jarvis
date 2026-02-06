"""
Inter-Bot Coordination System for ClawdBots

Provides coordination between the three ClawdBots:
- Jarvis (CTO) - Technical orchestration and trading
- Matt (COO) - Operations and PR filtering
- Friday (CMO) - Marketing and communications

Features:
1. Task handoff mechanism between bots
2. Shared state via file-based system (/root/clawdbots/shared_state.json)
3. Bot-to-bot messaging via file queue
4. Task ownership/claiming to prevent duplicate work
5. Status reporting and aggregation

Usage:
    from bots.shared.coordination import BotCoordinator, BotRole

    # Initialize as Jarvis
    coord = BotCoordinator(BotRole.JARVIS)

    # Delegate research to Friday
    task_id = coord.delegate_task(
        to_bot=BotRole.FRIDAY,
        description="Research competitor marketing strategy",
        priority=TaskPriority.HIGH,
    )

    # Send message to Matt
    coord.send_message(BotRole.MATT, "Campaign ready for review")

    # Check status of all bots
    report = coord.generate_status_report()
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

try:
    import filelock
except ImportError:
    # Fallback for environments without filelock
    filelock = None

logger = logging.getLogger("clawdbots.coordination")


# Default state file path (VPS location)
DEFAULT_STATE_FILE = "/root/clawdbots/shared_state.json"


class BotRole(Enum):
    """
    ClawdBot roles with their titles.

    Each bot has a specific responsibility:
    - JARVIS (CTO): Technical lead, trading, orchestration
    - MATT (COO): Operations, PR filtering, coordination
    - FRIDAY (CMO): Marketing, communications, content
    """
    JARVIS = "jarvis"
    MATT = "matt"
    FRIDAY = "friday"

    @property
    def title(self) -> str:
        """Get the executive title for this role."""
        titles = {
            "jarvis": "CTO",
            "matt": "COO",
            "friday": "CMO",
        }
        return titles.get(self.value, "Unknown")


class TaskPriority(Enum):
    """Task priority levels (lower number = higher priority)."""
    CRITICAL = 1
    HIGH = 2
    MEDIUM = 3
    LOW = 4


class TaskStatus(Enum):
    """Task lifecycle status."""
    PENDING = "pending"
    CLAIMED = "claimed"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


class CoordinationError(Exception):
    """Raised when a coordination operation fails."""
    pass


@dataclass
class CoordinationTask:
    """
    A task delegated between bots.

    Tracks the full lifecycle from delegation through completion.
    """
    id: str
    description: str
    delegated_by: BotRole
    delegated_to: BotRole
    priority: TaskPriority = TaskPriority.MEDIUM
    status: TaskStatus = TaskStatus.PENDING
    context: Dict[str, Any] = field(default_factory=dict)
    created_at: Optional[str] = None
    claimed_at: Optional[str] = None
    completed_at: Optional[str] = None
    result: Optional[str] = None
    artifacts: List[str] = field(default_factory=list)
    failure_reason: Optional[str] = None

    def __post_init__(self):
        """Initialize timestamps."""
        if self.created_at is None:
            self.created_at = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "id": self.id,
            "description": self.description,
            "delegated_by": self.delegated_by.value,
            "delegated_to": self.delegated_to.value,
            "priority": self.priority.value,
            "status": self.status.value,
            "context": self.context,
            "created_at": self.created_at,
            "claimed_at": self.claimed_at,
            "completed_at": self.completed_at,
            "result": self.result,
            "artifacts": self.artifacts,
            "failure_reason": self.failure_reason,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CoordinationTask":
        """Deserialize from dictionary."""
        return cls(
            id=data["id"],
            description=data["description"],
            delegated_by=BotRole(data["delegated_by"]),
            delegated_to=BotRole(data["delegated_to"]),
            priority=TaskPriority(data.get("priority", 3)),
            status=TaskStatus(data.get("status", "pending")),
            context=data.get("context", {}),
            created_at=data.get("created_at"),
            claimed_at=data.get("claimed_at"),
            completed_at=data.get("completed_at"),
            result=data.get("result"),
            artifacts=data.get("artifacts", []),
            failure_reason=data.get("failure_reason"),
        )


@dataclass
class BotMessage:
    """
    A message between bots.

    Used for notifications, requests, and coordination communication.
    """
    id: str
    from_bot: BotRole
    to_bot: BotRole
    content: str
    related_task_id: Optional[str] = None
    read: bool = False
    created_at: Optional[str] = None

    def __post_init__(self):
        """Initialize timestamp."""
        if self.created_at is None:
            self.created_at = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "id": self.id,
            "from_bot": self.from_bot.value,
            "to_bot": self.to_bot.value,
            "content": self.content,
            "related_task_id": self.related_task_id,
            "read": self.read,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BotMessage":
        """Deserialize from dictionary."""
        return cls(
            id=data["id"],
            from_bot=BotRole(data["from_bot"]),
            to_bot=BotRole(data["to_bot"]),
            content=data["content"],
            related_task_id=data.get("related_task_id"),
            read=data.get("read", False),
            created_at=data.get("created_at"),
        )


@dataclass
class BotStatus:
    """
    Current status of a bot.

    Used for health monitoring and coordination.
    """
    bot: BotRole
    online: bool = True
    current_task: Optional[str] = None
    tasks_completed: int = 0
    tasks_pending: int = 0
    last_heartbeat: Optional[str] = None
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "bot": self.bot.value,
            "online": self.online,
            "current_task": self.current_task,
            "tasks_completed": self.tasks_completed,
            "tasks_pending": self.tasks_pending,
            "last_heartbeat": self.last_heartbeat,
            "error": self.error,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BotStatus":
        """Deserialize from dictionary."""
        return cls(
            bot=BotRole(data["bot"]),
            online=data.get("online", False),
            current_task=data.get("current_task"),
            tasks_completed=data.get("tasks_completed", 0),
            tasks_pending=data.get("tasks_pending", 0),
            last_heartbeat=data.get("last_heartbeat"),
            error=data.get("error"),
        )


class BotCoordinator:
    """
    Coordinates tasks and messages between ClawdBots.

    Each bot creates its own BotCoordinator instance, specifying its role.
    All coordinators share state via the same JSON file.

    Thread-safe via file locking (when filelock is available).
    """

    def __init__(
        self,
        bot_role: BotRole,
        state_file: Optional[str] = None,
    ):
        """
        Initialize the coordinator for a specific bot.

        Args:
            bot_role: The role of this bot (JARVIS, MATT, or FRIDAY)
            state_file: Path to shared state file (default: /root/clawdbots/shared_state.json)
        """
        self._role = bot_role
        self._state_file = state_file or DEFAULT_STATE_FILE

        # Create parent directory if needed
        state_path = Path(self._state_file)
        state_path.parent.mkdir(parents=True, exist_ok=True)

        # Setup file lock
        if filelock:
            self._lock = filelock.FileLock(self._state_file + ".lock")
        else:
            self._lock = None
            logger.warning("filelock not available, concurrent access may cause issues")

        # Initialize state file if needed
        if not state_path.exists():
            self._save_state(self._default_state())

        logger.info(f"BotCoordinator initialized for {bot_role.value} ({bot_role.title})")

    def _default_state(self) -> Dict[str, Any]:
        """Return default empty state."""
        return {
            "version": "1.0",
            "last_updated": datetime.now(timezone.utc).isoformat(),
            "tasks": [],
            "completed_tasks": [],
            "messages": [],
            "bot_statuses": {},
        }

    def _load_state(self) -> Dict[str, Any]:
        """Load state from disk."""
        try:
            with open(self._state_file, "r") as f:
                data = json.load(f)
                # Handle empty or invalid files
                if not data or not isinstance(data, dict):
                    return self._default_state()
                return data
        except (json.JSONDecodeError, FileNotFoundError) as e:
            logger.warning(f"Failed to load state: {e}, using default")
            return self._default_state()

    def _save_state(self, data: Dict[str, Any]) -> None:
        """Atomically save state to disk."""
        data["last_updated"] = datetime.now(timezone.utc).isoformat()

        # Write to temp file then rename (atomic on most filesystems)
        state_path = Path(self._state_file)
        temp_fd, temp_path = tempfile.mkstemp(
            dir=state_path.parent,
            suffix=".json.tmp",
        )
        try:
            with os.fdopen(temp_fd, "w") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            os.replace(temp_path, self._state_file)
        except Exception as e:
            if os.path.exists(temp_path):
                os.unlink(temp_path)
            raise e

    def _with_lock(self, func):
        """Execute function with file lock if available."""
        if self._lock:
            with self._lock:
                return func()
        else:
            return func()

    def _generate_task_id(self) -> str:
        """Generate unique task ID."""
        return f"task_{uuid.uuid4().hex[:8]}"

    def _generate_message_id(self) -> str:
        """Generate unique message ID."""
        return f"msg_{uuid.uuid4().hex[:8]}"

    # -------------------------
    # Task Delegation Methods
    # -------------------------

    def delegate_task(
        self,
        to_bot: BotRole,
        description: str,
        priority: TaskPriority = TaskPriority.MEDIUM,
        context: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Delegate a task to another bot.

        Args:
            to_bot: Bot to delegate the task to
            description: Task description
            priority: Task priority level
            context: Additional context/metadata

        Returns:
            The task ID

        Raises:
            CoordinationError: If delegating to self
        """
        if to_bot == self._role:
            raise CoordinationError(
                f"Cannot delegate task to self ({self._role.value})"
            )

        task_id = self._generate_task_id()

        task = CoordinationTask(
            id=task_id,
            description=description,
            delegated_by=self._role,
            delegated_to=to_bot,
            priority=priority,
            context=context or {},
        )

        def _do_delegate():
            state = self._load_state()
            state["tasks"].append(task.to_dict())
            self._save_state(state)
            return task_id

        result = self._with_lock(_do_delegate)

        logger.info(
            f"Task {task_id} delegated: {self._role.value} -> {to_bot.value}: "
            f"{description[:50]}..."
        )

        return result

    def claim_task(self, task_id: str) -> bool:
        """
        Claim a task delegated to this bot.

        Args:
            task_id: ID of the task to claim

        Returns:
            True if claimed successfully, False otherwise
        """
        def _do_claim():
            state = self._load_state()

            for i, t_data in enumerate(state["tasks"]):
                if t_data["id"] == task_id:
                    # Verify task is for this bot
                    if t_data["delegated_to"] != self._role.value:
                        logger.warning(
                            f"Cannot claim task {task_id} - delegated to "
                            f"{t_data['delegated_to']}, not {self._role.value}"
                        )
                        return False

                    # Verify task is pending
                    if t_data["status"] != TaskStatus.PENDING.value:
                        logger.warning(
                            f"Cannot claim task {task_id} - status is "
                            f"{t_data['status']}, not pending"
                        )
                        return False

                    # Claim the task
                    now = datetime.now(timezone.utc).isoformat()
                    t_data["status"] = TaskStatus.CLAIMED.value
                    t_data["claimed_at"] = now

                    state["tasks"][i] = t_data
                    self._save_state(state)

                    logger.info(f"Task {task_id} claimed by {self._role.value}")
                    return True

            logger.warning(f"Task {task_id} not found")
            return False

        return self._with_lock(_do_claim)

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
            True if completed successfully, False otherwise
        """
        def _do_complete():
            state = self._load_state()

            for i, t_data in enumerate(state["tasks"]):
                if t_data["id"] == task_id:
                    # Verify task belongs to this bot
                    if t_data["delegated_to"] != self._role.value:
                        logger.warning(
                            f"Cannot complete task {task_id} - "
                            f"delegated to {t_data['delegated_to']}"
                        )
                        return False

                    # Update task
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

                    logger.info(f"Task {task_id} completed by {self._role.value}")
                    return True

            logger.warning(f"Task {task_id} not found")
            return False

        return self._with_lock(_do_complete)

    def fail_task(self, task_id: str, reason: str) -> bool:
        """
        Mark a task as failed.

        Args:
            task_id: ID of the task
            reason: Reason for failure

        Returns:
            True if marked as failed, False otherwise
        """
        def _do_fail():
            state = self._load_state()

            for i, t_data in enumerate(state["tasks"]):
                if t_data["id"] == task_id:
                    # Verify task belongs to this bot
                    if t_data["delegated_to"] != self._role.value:
                        logger.warning(
                            f"Cannot fail task {task_id} - "
                            f"delegated to {t_data['delegated_to']}"
                        )
                        return False

                    # Update task
                    now = datetime.now(timezone.utc).isoformat()
                    t_data["status"] = TaskStatus.FAILED.value
                    t_data["completed_at"] = now
                    t_data["failure_reason"] = reason

                    # Move to completed (as failed)
                    state["tasks"].pop(i)
                    state["completed_tasks"].append(t_data)
                    self._save_state(state)

                    logger.info(f"Task {task_id} failed: {reason}")
                    return True

            logger.warning(f"Task {task_id} not found")
            return False

        return self._with_lock(_do_fail)

    def get_task(self, task_id: str) -> Optional[CoordinationTask]:
        """
        Get a task by ID.

        Args:
            task_id: ID of the task

        Returns:
            CoordinationTask or None if not found
        """
        def _do_get():
            state = self._load_state()

            # Check active tasks
            for t_data in state["tasks"]:
                if t_data["id"] == task_id:
                    return CoordinationTask.from_dict(t_data)

            # Check completed tasks
            for t_data in state.get("completed_tasks", []):
                if t_data["id"] == task_id:
                    return CoordinationTask.from_dict(t_data)

            return None

        return self._with_lock(_do_get)

    def get_pending_tasks(self) -> List[CoordinationTask]:
        """
        Get all pending tasks delegated to this bot.

        Returns:
            List of pending CoordinationTask objects
        """
        def _do_get():
            state = self._load_state()

            pending = []
            for t_data in state["tasks"]:
                if (t_data["delegated_to"] == self._role.value and
                    t_data["status"] == TaskStatus.PENDING.value):
                    pending.append(CoordinationTask.from_dict(t_data))

            return pending

        return self._with_lock(_do_get)

    def get_tasks_by_status(self, status: TaskStatus) -> List[CoordinationTask]:
        """
        Get tasks by status for this bot.

        Args:
            status: Status to filter by

        Returns:
            List of CoordinationTask objects matching status
        """
        def _do_get():
            state = self._load_state()

            tasks = []
            for t_data in state["tasks"]:
                if (t_data["delegated_to"] == self._role.value and
                    t_data["status"] == status.value):
                    tasks.append(CoordinationTask.from_dict(t_data))

            return tasks

        return self._with_lock(_do_get)

    # -------------------------
    # Messaging Methods
    # -------------------------

    def send_message(
        self,
        to_bot: BotRole,
        content: str,
        related_task_id: Optional[str] = None,
    ) -> str:
        """
        Send a message to another bot.

        Args:
            to_bot: Bot to send message to
            content: Message content
            related_task_id: Optional related task ID

        Returns:
            The message ID
        """
        msg_id = self._generate_message_id()

        message = BotMessage(
            id=msg_id,
            from_bot=self._role,
            to_bot=to_bot,
            content=content,
            related_task_id=related_task_id,
        )

        def _do_send():
            state = self._load_state()
            state["messages"].append(message.to_dict())
            self._save_state(state)
            return msg_id

        result = self._with_lock(_do_send)

        logger.info(
            f"Message {msg_id} sent: {self._role.value} -> {to_bot.value}"
        )

        return result

    def get_unread_messages(self) -> List[BotMessage]:
        """
        Get all unread messages for this bot.

        Returns:
            List of unread BotMessage objects
        """
        def _do_get():
            state = self._load_state()

            unread = []
            for m_data in state.get("messages", []):
                if (m_data["to_bot"] == self._role.value and
                    not m_data.get("read", False)):
                    unread.append(BotMessage.from_dict(m_data))

            return unread

        return self._with_lock(_do_get)

    def mark_message_read(self, message_id: str) -> bool:
        """
        Mark a message as read.

        Args:
            message_id: ID of the message

        Returns:
            True if marked, False if not found
        """
        def _do_mark():
            state = self._load_state()

            for i, m_data in enumerate(state.get("messages", [])):
                if m_data["id"] == message_id:
                    m_data["read"] = True
                    state["messages"][i] = m_data
                    self._save_state(state)
                    return True

            return False

        return self._with_lock(_do_mark)

    # -------------------------
    # Status Methods
    # -------------------------

    def update_status(
        self,
        current_task: Optional[str] = None,
        tasks_completed: int = 0,
        tasks_pending: int = 0,
        error: Optional[str] = None,
    ) -> None:
        """
        Update this bot's status.

        Args:
            current_task: Current task description
            tasks_completed: Number of completed tasks
            tasks_pending: Number of pending tasks
            error: Current error state (if any)
        """
        def _do_update():
            state = self._load_state()

            now = datetime.now(timezone.utc).isoformat()

            status = BotStatus(
                bot=self._role,
                online=True,
                current_task=current_task,
                tasks_completed=tasks_completed,
                tasks_pending=tasks_pending,
                last_heartbeat=now,
                error=error,
            )

            state["bot_statuses"][self._role.value] = status.to_dict()
            self._save_state(state)

        self._with_lock(_do_update)
        logger.debug(f"Status updated for {self._role.value}")

    def heartbeat(self) -> None:
        """
        Update heartbeat timestamp for this bot.

        Should be called periodically to indicate the bot is alive.
        """
        def _do_heartbeat():
            state = self._load_state()

            now = datetime.now(timezone.utc).isoformat()

            if self._role.value not in state.get("bot_statuses", {}):
                state["bot_statuses"][self._role.value] = BotStatus(
                    bot=self._role,
                    online=True,
                    last_heartbeat=now,
                ).to_dict()
            else:
                state["bot_statuses"][self._role.value]["last_heartbeat"] = now
                state["bot_statuses"][self._role.value]["online"] = True

            self._save_state(state)

        self._with_lock(_do_heartbeat)

    def get_my_status(self) -> BotStatus:
        """
        Get this bot's current status.

        Returns:
            BotStatus object
        """
        def _do_get():
            state = self._load_state()

            status_data = state.get("bot_statuses", {}).get(self._role.value)
            if status_data:
                return BotStatus.from_dict(status_data)

            return BotStatus(bot=self._role, online=False)

        return self._with_lock(_do_get)

    def get_all_bot_statuses(self) -> Dict[BotRole, BotStatus]:
        """
        Get status of all bots.

        Returns:
            Dictionary mapping BotRole to BotStatus
        """
        def _do_get():
            state = self._load_state()

            statuses = {}
            for role in BotRole:
                status_data = state.get("bot_statuses", {}).get(role.value)
                if status_data:
                    statuses[role] = BotStatus.from_dict(status_data)
                else:
                    statuses[role] = BotStatus(bot=role, online=False)

            return statuses

        return self._with_lock(_do_get)

    # -------------------------
    # Reporting Methods
    # -------------------------

    def generate_status_report(self) -> str:
        """
        Generate a human-readable status report for all bots.

        Returns:
            Formatted status report string
        """
        statuses = self.get_all_bot_statuses()

        def _count_tasks():
            state = self._load_state()
            return len(state.get("tasks", [])), len(state.get("completed_tasks", []))

        active_count, completed_count = self._with_lock(_count_tasks)

        lines = [
            "=" * 50,
            "CLAWDBOTS STATUS REPORT",
            f"Generated: {datetime.now(timezone.utc).isoformat()}",
            f"Generated by: {self._role.value} ({self._role.title})",
            "=" * 50,
            "",
            "BOT STATUS:",
            "-" * 30,
        ]

        for role in BotRole:
            status = statuses.get(role, BotStatus(bot=role, online=False))
            status_icon = "[OK]" if status.online else "[--]"
            task_info = f" - {status.current_task}" if status.current_task else ""
            lines.append(
                f"  {status_icon} {role.value.upper()} ({role.title})"
                f"{task_info}"
            )
            if status.error:
                lines.append(f"       ERROR: {status.error}")

        lines.extend([
            "",
            "TASK SUMMARY:",
            "-" * 30,
            f"  Active tasks: {active_count}",
            f"  Completed tasks: {completed_count}",
            "",
            "=" * 50,
        ])

        return "\n".join(lines)


# -------------------------
# Convenience Functions
# -------------------------

def get_coordinator(role: str) -> BotCoordinator:
    """
    Get a BotCoordinator for the specified role.

    Args:
        role: Role name ('jarvis', 'matt', or 'friday')

    Returns:
        BotCoordinator instance
    """
    role_map = {
        "jarvis": BotRole.JARVIS,
        "matt": BotRole.MATT,
        "friday": BotRole.FRIDAY,
    }
    if role.lower() not in role_map:
        raise ValueError(f"Invalid role: {role}. Must be jarvis, matt, or friday")

    return BotCoordinator(role_map[role.lower()])
