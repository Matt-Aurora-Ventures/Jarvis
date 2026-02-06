"""
Subagent Orchestration
======================

Lightweight parallel execution layer over the internal multi-agent system.

Why this exists
---------------
The fleet repeatedly needs to fan out a single objective into multiple
independent "subagent" tasks (triage, audits, drafting, validation).

This module provides:
- A small API to spawn tasks in parallel (thread pool).
- Tracking via `core.agents.manager.SubAgentManager`.
- Durable artifacts written to `data/subagents/<session>/...` (no stdout-only).

This is intentionally non-destructive: it only writes artifacts and updates the
in-memory manager state. It does *not* apply code changes or perform deploys.
"""

from __future__ import annotations

import json
import logging
import re
import time
import uuid
from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from core.agents.base import AgentRole, AgentTask, AgentResult
from core.agents.manager import get_manager as get_subagent_manager
from core.agents.registry import initialize_agents

logger = logging.getLogger(__name__)


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUT_DIR = ROOT / "data" / "subagents"


def _safe_slug(value: str) -> str:
    value = value.strip() or "session"
    value = re.sub(r"[^a-zA-Z0-9._-]+", "_", value)
    return value[:120]


@dataclass(frozen=True)
class SpawnedSubagent:
    """A tracked, running subagent task."""

    agent_id: str
    role: Optional[AgentRole]
    task: AgentTask
    future: Future
    output_path: Path


class SubagentOrchestrator:
    """
    Spawn and track multiple agent tasks concurrently.

    Notes:
    - Uses a ThreadPoolExecutor because most agent work is I/O bound
      (LLM calls, filesystem, network) and threads keep integration simple.
    - Designed to be used by a higher-level scheduler (Orchestrator, Telegram bot,
      or ops scripts) to "fan out" and then synthesize.
    """

    def __init__(
        self,
        session_id: str,
        max_workers: int = 4,
        out_dir: Optional[Path] = None,
    ) -> None:
        self.session_id = session_id
        self.max_workers = max_workers
        self.out_dir = out_dir or (DEFAULT_OUT_DIR / _safe_slug(session_id))
        self.out_dir.mkdir(parents=True, exist_ok=True)

        # Ensure standard agents are registered once.
        self._registry = initialize_agents()
        self._mgr = get_subagent_manager()

        self._executor = ThreadPoolExecutor(max_workers=max_workers)
        self._spawned: List[SpawnedSubagent] = []

    def spawn(
        self,
        description: str,
        role: Optional[AgentRole] = None,
        context: Optional[Dict[str, Any]] = None,
        constraints: Optional[List[str]] = None,
        expected_output: str = "",
        timeout_seconds: int = 300,
        max_steps: int = 10,
    ) -> SpawnedSubagent:
        """Spawn one subagent task."""
        agent_id = str(uuid.uuid4())[:7]
        task = AgentTask(
            id=agent_id,
            objective_id=self.session_id,
            description=description,
            context=context or {},
            constraints=constraints or [],
            expected_output=expected_output,
            max_steps=max_steps,
            timeout_seconds=timeout_seconds,
        )

        out_path = self.out_dir / f"{agent_id}.json"

        # Register with manager for visibility.
        self._mgr.register_agent(
            subagent_type=(role.value if role else "auto"),
            description=description,
            prompt=description,
            session_id=self.session_id,
            agent_id=agent_id,
            status="running",
            metadata={
                "role": (role.value if role else "auto"),
                "created_at": datetime.now(timezone.utc).isoformat(),
            },
        )

        def _run_task() -> AgentResult:
            start = time.time()
            try:
                if role is not None:
                    result = self._registry.execute_with_role(role, task)
                else:
                    result = self._registry.route_and_execute(task)
                result.duration_ms = result.duration_ms or int((time.time() - start) * 1000)
                return result
            except Exception as e:
                return AgentResult(
                    task_id=task.id,
                    success=False,
                    output="",
                    error=str(e)[:500],
                    duration_ms=int((time.time() - start) * 1000),
                )

        future: Future = self._executor.submit(_run_task)

        def _on_done(fut: Future) -> None:
            try:
                res: AgentResult = fut.result()
            except Exception as e:
                res = AgentResult(task_id=task.id, success=False, output="", error=str(e)[:500])

            payload = {
                "agent_id": agent_id,
                "session_id": self.session_id,
                "role": role.value if role else "auto",
                "task": {
                    "id": task.id,
                    "objective_id": task.objective_id,
                    "description": task.description,
                    "context": task.context,
                    "constraints": task.constraints,
                    "expected_output": task.expected_output,
                    "max_steps": task.max_steps,
                    "timeout_seconds": task.timeout_seconds,
                },
                "result": {
                    "success": res.success,
                    "output": res.output,
                    "error": res.error,
                    "duration_ms": res.duration_ms,
                    "steps_taken": res.steps_taken,
                    "tokens_used": res.tokens_used,
                    "cost_estimate": res.cost_estimate,
                    "artifacts": res.artifacts,
                    "learnings": res.learnings,
                },
                "completed_at": datetime.now(timezone.utc).isoformat(),
            }

            try:
                out_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
            except Exception as e:
                logger.warning("Failed to write subagent artifact %s: %s", out_path, e)

            try:
                self._mgr.update_status(
                    agent_id=agent_id,
                    status=("completed" if res.success else "failed"),
                    tokens=res.tokens_used or None,
                    error=(res.error or None),
                    output_file=str(out_path),
                )
            except Exception:
                pass

        future.add_done_callback(_on_done)

        spawned = SpawnedSubagent(
            agent_id=agent_id,
            role=role,
            task=task,
            future=future,
            output_path=out_path,
        )
        self._spawned.append(spawned)
        return spawned

    def spawn_many(self, specs: Iterable[Dict[str, Any]]) -> List[SpawnedSubagent]:
        """
        Spawn many tasks from a list of dict specs.

        Spec keys:
        - description (required)
        - role (optional, AgentRole or str)
        - context, constraints, expected_output, timeout_seconds, max_steps
        """
        out: List[SpawnedSubagent] = []
        for spec in specs:
            desc = str(spec.get("description") or "").strip()
            if not desc:
                continue
            role_val = spec.get("role")
            role: Optional[AgentRole] = None
            if isinstance(role_val, AgentRole):
                role = role_val
            elif isinstance(role_val, str) and role_val.strip():
                try:
                    role = AgentRole(role_val.strip())
                except Exception:
                    role = None

            out.append(
                self.spawn(
                    description=desc,
                    role=role,
                    context=spec.get("context") or None,
                    constraints=spec.get("constraints") or None,
                    expected_output=str(spec.get("expected_output") or ""),
                    timeout_seconds=int(spec.get("timeout_seconds") or 300),
                    max_steps=int(spec.get("max_steps") or 10),
                )
            )
        return out

    def gather(self, timeout_seconds: Optional[int] = None) -> List[AgentResult]:
        """
        Wait for all spawned tasks and return results.

        If timeout_seconds is provided, this will return whatever finished
        within the deadline.
        """
        deadline = time.time() + timeout_seconds if timeout_seconds else None
        results: List[AgentResult] = []

        futures = [s.future for s in self._spawned]
        for fut in as_completed(futures, timeout=timeout_seconds):
            if deadline and time.time() > deadline:
                break
            try:
                results.append(fut.result())
            except Exception as e:
                results.append(AgentResult(task_id="unknown", success=False, output="", error=str(e)[:500]))
        return results

    def shutdown(self) -> None:
        """Shutdown the executor (no more spawns)."""
        try:
            self._executor.shutdown(wait=False, cancel_futures=False)
        except Exception:
            pass

