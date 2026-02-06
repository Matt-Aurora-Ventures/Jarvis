"""
Multi-Agent Spawning for ClawdBots.

Enables Matt (COO) to dispatch parallel tasks to specialist agents
and synthesize results. Based on GRU multi-agent patterns.

Pattern:
  User: "Analyze trading performance and draft a Twitter thread"
  Matt:
    -> Jarvis (async): Pull crypto_ops metrics, analyze P&L
    -> Friday (async): Draft Twitter thread structure
    -> Wait for both -> Synthesize -> Return unified response
"""

import asyncio
import json
import logging
import os
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class TaskStatus(str, Enum):
    """Status of a dispatched agent task."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"


@dataclass
class AgentTask:
    """A task dispatched to a specialist agent."""
    id: str
    target_bot: str  # "jarvis", "friday", "matt"
    description: str
    context: str = ""
    status: TaskStatus = TaskStatus.PENDING
    result: Optional[str] = None
    error: Optional[str] = None
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    completed_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "id": self.id,
            "target_bot": self.target_bot,
            "description": self.description,
            "context": self.context,
            "status": self.status.value if isinstance(self.status, TaskStatus) else self.status,
            "result": self.result,
            "error": self.error,
            "created_at": self.created_at,
            "completed_at": self.completed_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AgentTask":
        """Deserialize from dictionary."""
        return cls(
            id=data["id"],
            target_bot=data["target_bot"],
            description=data["description"],
            context=data.get("context", ""),
            status=TaskStatus(data.get("status", "pending")),
            result=data.get("result"),
            error=data.get("error"),
            created_at=data.get("created_at", datetime.now(timezone.utc).isoformat()),
            completed_at=data.get("completed_at"),
        )


@dataclass
class TaskGroup:
    """A group of parallel tasks dispatched together."""
    group_id: str
    original_message: str
    tasks: List[AgentTask] = field(default_factory=list)
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    completed_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "group_id": self.group_id,
            "original_message": self.original_message,
            "tasks": [t.to_dict() for t in self.tasks],
            "created_at": self.created_at,
            "completed_at": self.completed_at,
        }


# Keywords that route to each agent
_JARVIS_KEYWORDS = [
    "trade", "trading", "sol", "token", "vps", "server", "deploy",
    "code", "bug", "fix", "api", "performance", "wallet", "solana",
    "treasury", "position", "swap", "dex", "jupiter", "health",
]

_FRIDAY_KEYWORDS = [
    "tweet", "twitter", "post", "content", "brand", "marketing",
    "campaign", "copy", "write", "draft", "social", "engagement",
    "thread", "announcement", "pr", "communications",
]


class MultiAgentDispatcher:
    """Dispatches parallel tasks to specialist agents and synthesizes results."""

    def __init__(
        self,
        coordinator,
        bot_name: str = "matt",
        state_dir: Optional[str] = None,
    ):
        """
        Initialize the dispatcher.

        Args:
            coordinator: BotCoordinator instance for single-agent delegation
            bot_name: Name of the dispatching bot (default: matt)
            state_dir: Base directory for file-based task communication
        """
        self.coordinator = coordinator
        self.bot_name = bot_name

        # IMPORTANT: this dispatcher relies on a shared volume between bots.
        # Default to the shared data mount used by docker-compose:
        #   host: /root/clawdbots/data  -> container: /root/clawdbots/data
        #
        # Override via:
        #   CLAWDBOTS_STATE_DIR=/root/clawdbots/data
        resolved_state_dir = (
            state_dir
            or os.environ.get("CLAWDBOTS_STATE_DIR")
            or "/root/clawdbots/data"
        )
        self.state_dir = Path(resolved_state_dir)
        self.tasks_dir = self.state_dir / "tasks"
        self.tasks_dir.mkdir(parents=True, exist_ok=True)
        self.groups_dir = self.state_dir / "task_groups"
        self.groups_dir.mkdir(parents=True, exist_ok=True)

    def classify_request(self, message: str) -> Dict[str, str]:
        """
        Detect which agents a request needs based on keyword matching.

        Returns:
            Dict mapping bot_name -> task_context string.
            Empty dict if no specialist agents are needed.
        """
        agents: Dict[str, str] = {}
        msg_lower = message.lower()

        if any(kw in msg_lower for kw in _JARVIS_KEYWORDS):
            agents["jarvis"] = f"Technical analysis needed: {message}"

        if any(kw in msg_lower for kw in _FRIDAY_KEYWORDS):
            agents["friday"] = f"Marketing/content needed: {message}"

        return agents

    def _write_task_file(self, task: AgentTask) -> Path:
        """Write a task to disk for the target bot to pick up."""
        task_path = self.tasks_dir / f"{task.id}.json"
        task_path.write_text(json.dumps(task.to_dict(), indent=2))
        logger.info(
            f"Wrote task {task.id} for {task.target_bot} to {task_path}"
        )
        return task_path

    def _read_task_file(self, task_id: str) -> Optional[AgentTask]:
        """Read a task file from disk, return updated AgentTask or None."""
        task_path = self.tasks_dir / f"{task_id}.json"
        if not task_path.exists():
            return None
        try:
            data = json.loads(task_path.read_text())
            return AgentTask.from_dict(data)
        except (json.JSONDecodeError, KeyError) as e:
            logger.error(f"Failed to read task {task_id}: {e}")
            return None

    async def _poll_task_completion(
        self, task: AgentTask, deadline: float
    ) -> None:
        """
        Poll a task file on disk until it is completed or the deadline passes.

        Target bots write their results back to the same task file.
        This method updates the task object in-place.
        """
        poll_interval = 1.0
        while asyncio.get_event_loop().time() < deadline:
            updated = self._read_task_file(task.id)
            if updated and updated.status in (
                TaskStatus.COMPLETED,
                TaskStatus.FAILED,
            ):
                task.status = updated.status
                task.result = updated.result
                task.error = updated.error
                task.completed_at = updated.completed_at
                return
            await asyncio.sleep(poll_interval)

    async def dispatch_parallel(
        self, tasks: List[AgentTask], timeout: float = 120
    ) -> List[AgentTask]:
        """
        Dispatch multiple tasks in parallel and wait for all to complete.

        Each task is written to disk as a JSON file. Target bots poll for
        pending tasks and write results back. This method polls until all
        tasks complete or the timeout expires.

        Args:
            tasks: List of AgentTask to dispatch
            timeout: Maximum seconds to wait for all tasks

        Returns:
            The same list of tasks, updated with results/status
        """
        # Write all task files
        for task in tasks:
            task.status = TaskStatus.RUNNING
            self._write_task_file(task)

        # Poll all tasks in parallel
        loop = asyncio.get_event_loop()
        deadline = loop.time() + timeout

        poll_coros = [
            self._poll_task_completion(task, deadline) for task in tasks
        ]

        try:
            await asyncio.wait_for(
                asyncio.gather(*poll_coros, return_exceptions=True),
                timeout=timeout,
            )
        except asyncio.TimeoutError:
            pass

        # Mark any still-running tasks as timed out
        for task in tasks:
            if task.status == TaskStatus.RUNNING:
                task.status = TaskStatus.TIMEOUT
                task.completed_at = datetime.now(timezone.utc).isoformat()
                # Update the file on disk too
                self._write_task_file(task)

        return tasks

    async def dispatch_and_synthesize(
        self, message: str, timeout: float = 120
    ) -> Optional[str]:
        """
        High-level: classify message, dispatch to agents, synthesize results.

        Args:
            message: User message to process
            timeout: Max seconds to wait

        Returns:
            Synthesized response string, or None if single/no agent needed
        """
        agents = self.classify_request(message)

        if len(agents) <= 1:
            return None  # Single-agent or no-agent, handle normally

        # Create task group
        group_id = uuid.uuid4().hex[:8]
        tasks = []
        for bot, context in agents.items():
            tasks.append(
                AgentTask(
                    id=f"{group_id}_{bot}",
                    target_bot=bot,
                    description=message,
                    context=context,
                )
            )

        group = TaskGroup(
            group_id=group_id,
            original_message=message,
            tasks=tasks,
        )

        logger.info(
            f"Dispatching {len(tasks)} parallel tasks (group {group_id}): "
            f"{[t.target_bot for t in tasks]}"
        )

        # Dispatch and wait
        completed = await self.dispatch_parallel(tasks, timeout)

        # Persist group for visibility
        group.completed_at = datetime.now(timezone.utc).isoformat()
        self._save_task_group(group)

        return self._synthesize_results(message, completed)

    def _synthesize_results(
        self, original_message: str, tasks: List[AgentTask]
    ) -> str:
        """
        Combine results from multiple agents into a unified response.

        Args:
            original_message: The original user request
            tasks: Completed (or failed/timed out) tasks

        Returns:
            Formatted synthesis string
        """
        sections = []
        has_failures = False

        for task in tasks:
            bot_label = task.target_bot.upper()

            if task.status == TaskStatus.COMPLETED:
                sections.append(
                    f"[{bot_label}] {task.result or 'No result provided'}"
                )
            elif task.status == TaskStatus.FAILED:
                has_failures = True
                sections.append(
                    f"[{bot_label}] FAILED - Error: {task.error or 'Unknown error'}"
                )
            elif task.status == TaskStatus.TIMEOUT:
                has_failures = True
                sections.append(
                    f"[{bot_label}] TIMEOUT - Did not respond in time"
                )
            else:
                has_failures = True
                sections.append(
                    f"[{bot_label}] Status: {task.status.value}"
                )

        header = "Multi-Agent Results"
        if has_failures:
            header += " (partial)"

        body = "\n\n".join(sections)
        return f"{header}\n{'=' * len(header)}\n\n{body}"

    def _save_task_group(self, group: TaskGroup) -> None:
        """Persist a task group to disk for visibility and debugging."""
        group_path = self.groups_dir / f"{group.group_id}.json"
        group_path.write_text(json.dumps(group.to_dict(), indent=2))
        logger.info(f"Saved task group {group.group_id} to {group_path}")
