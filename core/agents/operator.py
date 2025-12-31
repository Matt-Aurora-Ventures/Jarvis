"""
Operator Agent - Task execution, UI automation, integrations.

Capabilities:
- UI automation (browser, apps)
- File operations
- Email and calendar
- System integrations

Uses Groq for speed, falls back to Ollama for self-sufficient operation.
"""

import json
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.agents.base import (
    BaseAgent,
    AgentRole,
    AgentCapability,
    AgentTask,
    AgentResult,
    ProviderPreference,
)
from core import actions, config


ROOT = Path(__file__).resolve().parents[2]
OPERATOR_LOG = ROOT / "data" / "agents" / "operator" / "operations.jsonl"


class OperatorAgent(BaseAgent):
    """
    Operator Agent - Executes tasks and automates workflows.

    Optimized for speed and reliability. Handles:
    - UI automation (browser, apps)
    - File operations
    - Communication (email, messages)
    - Calendar and scheduling
    - System integrations

    Uses Groq for speed, with Ollama fallback for self-sufficient operation.
    """

    def __init__(self):
        super().__init__(
            role=AgentRole.OPERATOR,
            capabilities=[
                AgentCapability.UI_AUTOMATION,
                AgentCapability.FILE_OPS,
                AgentCapability.EMAIL,
                AgentCapability.CALENDAR,
            ],
            provider_preference=ProviderPreference.AUTO,
        )
        OPERATOR_LOG.parent.mkdir(parents=True, exist_ok=True)

    def get_system_prompt(self) -> str:
        return """You are the Operator Agent in the Jarvis multi-agent system.

Your role is to execute tasks efficiently and reliably.

CAPABILITIES:
- Browser automation (open URLs, search, navigate)
- App control (open, switch, interact)
- File operations (create, move, organize)
- Email and messaging
- Calendar management

OPERATING PRINCIPLES:
1. Execute precisely - no guessing, no assumptions
2. Verify before destructive actions
3. Report what was done and what failed
4. Handle errors gracefully
5. Log all operations

AVAILABLE ACTIONS:
- open_browser(url): Open browser to URL
- google(query): Search Google
- open_mail: Open mail app
- compose_email(to, subject, body): Create email
- open_calendar: Open calendar
- create_event(title, date, time): Create calendar event
- open_notes(topic): Open notes folder
- create_note(title, body): Create a note
- open_finder(path): Open Finder to path
- spotlight(query): Open Spotlight search

OUTPUT FORMAT:
1. PLAN: What you will do
2. EXECUTION: Step-by-step what happened
3. RESULT: Success/failure with details
4. SIDE EFFECTS: Any unintended changes"""

    def _get_keywords(self) -> List[str]:
        return [
            "open", "launch", "start", "run", "execute",
            "send", "email", "message", "notify",
            "create", "make", "new", "add",
            "schedule", "calendar", "event", "meeting",
            "browse", "search", "google", "navigate",
            "file", "folder", "save", "move", "copy",
            "automate", "do", "perform", "action",
        ]

    def execute(self, task: AgentTask) -> AgentResult:
        """Execute an operation task."""
        start_time = time.time()
        steps_taken = 0
        artifacts = {"actions_taken": []}

        try:
            # Step 1: Plan the execution
            steps_taken += 1
            plan = self._plan_execution(task)

            # Step 2: Execute each action
            results = []
            for action_spec in plan:
                steps_taken += 1
                action_result = self._execute_action(action_spec)
                results.append(action_result)
                artifacts["actions_taken"].append(action_result)

                # Stop on critical failure
                if not action_result.get("success") and action_spec.get("critical", True):
                    break

            # Step 3: Summarize results
            steps_taken += 1
            success = all(r.get("success", False) for r in results)
            output = self._summarize_execution(task.description, results)

            # Log operation
            self._log_operation(task, results, success)

            return AgentResult(
                task_id=task.id,
                success=success,
                output=output,
                steps_taken=steps_taken,
                duration_ms=int((time.time() - start_time) * 1000),
                artifacts=artifacts,
                learnings=[f"Executed: {task.description[:50]}"],
            )

        except Exception as e:
            return AgentResult(
                task_id=task.id,
                success=False,
                output="",
                error=str(e)[:500],
                steps_taken=steps_taken,
                duration_ms=int((time.time() - start_time) * 1000),
            )

    def _plan_execution(self, task: AgentTask) -> List[Dict[str, Any]]:
        """Plan the actions to execute."""
        # Get available actions
        available = actions.get_available_actions()

        prompt = f"""Plan execution for this task:
Task: {task.description}
Context: {json.dumps(task.context) if task.context else 'None'}
Constraints: {task.constraints}

Available actions: {available}

Output a JSON array of actions to execute:
[
  {{"action": "action_name", "params": {{"key": "value"}}, "critical": true}},
  ...
]

Only output the JSON array, no other text."""

        response, _ = self.generate(prompt, priority="speed")

        # Parse plan
        try:
            import re
            match = re.search(r'\[.*\]', response, re.DOTALL)
            if match:
                plan = json.loads(match.group())
                return plan if isinstance(plan, list) else []
        except Exception:
            pass

        # Fallback: try to infer action from description
        return self._infer_action(task.description)

    def _infer_action(self, description: str) -> List[Dict[str, Any]]:
        """Infer action from natural language description."""
        description_lower = description.lower()

        # Simple pattern matching for common operations
        if "open" in description_lower and "browser" in description_lower:
            return [{"action": "open_browser", "params": {}, "critical": True}]
        elif "google" in description_lower or "search" in description_lower:
            # Extract search query
            query = description.replace("google", "").replace("search", "").strip()
            return [{"action": "google", "params": {"query": query}, "critical": True}]
        elif "email" in description_lower or "mail" in description_lower:
            return [{"action": "open_mail", "params": {}, "critical": True}]
        elif "calendar" in description_lower:
            return [{"action": "open_calendar", "params": {}, "critical": True}]
        elif "note" in description_lower:
            return [{"action": "open_notes", "params": {}, "critical": False}]

        return []

    def _execute_action(self, action_spec: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a single action."""
        action_name = action_spec.get("action", "")
        params = action_spec.get("params", {})

        if not action_name:
            return {"success": False, "error": "No action specified"}

        # Use the disciplined action execution from actions module
        success, output, feedback = actions.execute_with_discipline(
            action_name=action_name,
            why=f"Operator agent executing: {action_name}",
            expected_outcome=f"{action_name} completes successfully",
            **params,
        )

        return {
            "action": action_name,
            "params": params,
            "success": success,
            "output": output,
            "feedback": feedback,
        }

    def _summarize_execution(self, description: str, results: List[Dict]) -> str:
        """Summarize what was executed."""
        successful = [r for r in results if r.get("success")]
        failed = [r for r in results if not r.get("success")]

        summary_parts = [f"Task: {description}"]

        if successful:
            summary_parts.append(f"\nCompleted ({len(successful)}):")
            for r in successful:
                summary_parts.append(f"  - {r['action']}: {r.get('output', 'done')[:100]}")

        if failed:
            summary_parts.append(f"\nFailed ({len(failed)}):")
            for r in failed:
                summary_parts.append(f"  - {r['action']}: {r.get('error', 'unknown error')[:100]}")

        return "\n".join(summary_parts)

    def _log_operation(self, task: AgentTask, results: List[Dict], success: bool) -> None:
        """Log operation for analysis."""
        entry = {
            "timestamp": time.time(),
            "task_id": task.id,
            "description": task.description[:200],
            "actions": len(results),
            "success": success,
            "results": results,
        }

        with open(OPERATOR_LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")

    # Convenience methods for direct use
    def quick_action(self, action_name: str, **params) -> bool:
        """Execute a single action quickly."""
        success, output, _ = actions.execute_with_discipline(
            action_name=action_name,
            why="Quick action via Operator agent",
            expected_outcome=f"{action_name} succeeds",
            **params,
        )
        return success

    def run_workflow(self, steps: List[Dict[str, Any]]) -> AgentResult:
        """Run a multi-step workflow."""
        task = AgentTask(
            id=str(uuid.uuid4())[:8],
            objective_id="workflow",
            description=f"Workflow with {len(steps)} steps",
            context={"steps": steps},
            max_steps=len(steps) + 2,
        )
        return self.execute(task)
