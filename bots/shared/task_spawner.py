"""
Multi-Agent Task Spawner (GRU Pattern) for ClawdBots.

Enables Matt (orchestrator) to dispatch tasks to Jarvis and Friday
in parallel, collect results, and synthesize responses.

Usage:
    spawner = TaskSpawner(bot_tokens)
    results = await spawner.spawn_parallel([
        Task("jarvis", "analyze trading performance"),
        Task("friday", "draft twitter thread about results"),
    ])
    synthesis = spawner.synthesize(results)
"""

import asyncio
import json
import logging
import os
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

DATA_DIR = Path(os.environ.get("CLAWDBOT_DATA_DIR", "/root/clawdbots/data"))
TASKS_FILE = DATA_DIR / "active_tasks.json"


class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"


@dataclass
class Task:
    target_bot: str
    instruction: str
    priority: int = 1  # 1=normal, 2=high, 3=critical
    timeout_seconds: int = 30
    task_id: str = ""
    status: TaskStatus = TaskStatus.PENDING
    result: Any = None
    error: str = ""
    started_at: float = 0
    completed_at: float = 0

    def __post_init__(self):
        if not self.task_id:
            self.task_id = f"{self.target_bot}_{int(time.time() * 1000)}"


@dataclass
class SpawnResult:
    task_id: str
    target_bot: str
    status: TaskStatus
    result: Any = None
    error: str = ""
    duration_ms: int = 0


class TaskSpawner:
    """Dispatches tasks to specialist bots and collects results."""

    def __init__(self, handlers: Optional[Dict[str, Callable]] = None):
        """
        Args:
            handlers: Dict mapping bot names to async handler functions.
                      e.g. {"jarvis": jarvis_handle, "friday": friday_handle}
        """
        self.handlers: Dict[str, Callable] = handlers or {}
        self._task_log: List[dict] = []

    def register_handler(self, bot_name: str, handler: Callable):
        """Register an async handler for a bot."""
        self.handlers[bot_name] = handler

    async def spawn_single(self, task: Task) -> SpawnResult:
        """Execute a single task against its target bot."""
        handler = self.handlers.get(task.target_bot)
        if not handler:
            return SpawnResult(
                task_id=task.task_id,
                target_bot=task.target_bot,
                status=TaskStatus.FAILED,
                error=f"No handler registered for {task.target_bot}",
            )

        task.status = TaskStatus.RUNNING
        task.started_at = time.time()

        try:
            result = await asyncio.wait_for(
                handler(task.instruction),
                timeout=task.timeout_seconds,
            )
            task.completed_at = time.time()
            task.status = TaskStatus.COMPLETED
            task.result = result
            duration = int((task.completed_at - task.started_at) * 1000)

            self._log_task(task, duration)
            return SpawnResult(
                task_id=task.task_id,
                target_bot=task.target_bot,
                status=TaskStatus.COMPLETED,
                result=result,
                duration_ms=duration,
            )
        except asyncio.TimeoutError:
            task.status = TaskStatus.TIMEOUT
            task.completed_at = time.time()
            duration = int((task.completed_at - task.started_at) * 1000)
            self._log_task(task, duration)
            return SpawnResult(
                task_id=task.task_id,
                target_bot=task.target_bot,
                status=TaskStatus.TIMEOUT,
                error=f"Timed out after {task.timeout_seconds}s",
                duration_ms=duration,
            )
        except Exception as e:
            task.status = TaskStatus.FAILED
            task.error = str(e)
            task.completed_at = time.time()
            duration = int((task.completed_at - task.started_at) * 1000)
            self._log_task(task, duration)
            return SpawnResult(
                task_id=task.task_id,
                target_bot=task.target_bot,
                status=TaskStatus.FAILED,
                error=str(e),
                duration_ms=duration,
            )

    async def spawn_parallel(self, tasks: List[Task]) -> List[SpawnResult]:
        """Execute multiple tasks in parallel across bots."""
        # Sort by priority (higher first)
        sorted_tasks = sorted(tasks, key=lambda t: -t.priority)
        coros = [self.spawn_single(t) for t in sorted_tasks]
        results = await asyncio.gather(*coros, return_exceptions=True)

        spawn_results = []
        for i, r in enumerate(results):
            if isinstance(r, Exception):
                spawn_results.append(SpawnResult(
                    task_id=sorted_tasks[i].task_id,
                    target_bot=sorted_tasks[i].target_bot,
                    status=TaskStatus.FAILED,
                    error=str(r),
                ))
            else:
                spawn_results.append(r)
        return spawn_results

    def synthesize(self, results: List[SpawnResult]) -> str:
        """Combine results from parallel tasks into a unified response."""
        sections = []
        for r in results:
            if r.status == TaskStatus.COMPLETED:
                sections.append(f"[{r.target_bot.upper()}] {r.result}")
            elif r.status == TaskStatus.TIMEOUT:
                sections.append(f"[{r.target_bot.upper()}] (timed out)")
            elif r.status == TaskStatus.FAILED:
                sections.append(f"[{r.target_bot.upper()}] (failed: {r.error})")
        return "\n\n".join(sections) if sections else "No results"

    def _log_task(self, task: Task, duration_ms: int):
        entry = {
            "id": task.task_id,
            "bot": task.target_bot,
            "instruction": task.instruction[:100],
            "status": task.status.value,
            "duration_ms": duration_ms,
            "ts": datetime.utcnow().isoformat(),
        }
        self._task_log.append(entry)
        self._persist_tasks()

    def _persist_tasks(self):
        try:
            DATA_DIR.mkdir(parents=True, exist_ok=True)
            existing = []
            if TASKS_FILE.exists():
                try:
                    existing = json.loads(TASKS_FILE.read_text())
                except (json.JSONDecodeError, OSError):
                    pass
            existing.extend(self._task_log)
            # Keep last 500
            if len(existing) > 500:
                existing = existing[-500:]
            TASKS_FILE.write_text(json.dumps(existing, indent=2))
            self._task_log.clear()
        except Exception as e:
            logger.error(f"Failed to persist tasks: {e}")

    def get_task_stats(self, hours: int = 24) -> Dict[str, Any]:
        """Get task execution statistics."""
        try:
            if not TASKS_FILE.exists():
                return {"total": 0}
            tasks = json.loads(TASKS_FILE.read_text())
        except (json.JSONDecodeError, OSError):
            return {"total": 0}

        total = len(tasks)
        completed = sum(1 for t in tasks if t.get("status") == "completed")
        failed = sum(1 for t in tasks if t.get("status") == "failed")
        avg_ms = 0
        durations = [t.get("duration_ms", 0) for t in tasks if t.get("duration_ms")]
        if durations:
            avg_ms = sum(durations) // len(durations)

        return {
            "total": total,
            "completed": completed,
            "failed": failed,
            "avg_duration_ms": avg_ms,
        }


def detect_parallel_needs(message: str) -> List[str]:
    """Detect which bots should handle parts of a complex request.

    Returns list of bot names that should be involved.
    """
    bots = []
    technical_keywords = [
        "trade", "trading", "deploy", "server", "api", "code", "debug",
        "performance", "metrics", "database", "infrastructure", "wallet",
    ]
    marketing_keywords = [
        "tweet", "twitter", "post", "content", "campaign", "brand",
        "social", "marketing", "thread", "announce", "blog",
    ]

    msg_lower = message.lower()
    if any(kw in msg_lower for kw in technical_keywords):
        bots.append("jarvis")
    if any(kw in msg_lower for kw in marketing_keywords):
        bots.append("friday")

    return bots
