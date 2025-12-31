"""
Agent Registry - Routes tasks to the right specialized agent.

The registry:
- Maintains all available agents
- Routes objectives to the best-fit agent
- Tracks agent availability and performance
- Enables self-sufficient operation (can run with just Ollama)
"""

import json
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Type

from core.agents.base import (
    BaseAgent,
    AgentRole,
    AgentTask,
    AgentResult,
    ProviderPreference,
)


ROOT = Path(__file__).resolve().parents[2]
REGISTRY_STATE = ROOT / "data" / "agents" / "registry_state.json"


@dataclass
class AgentStatus:
    """Status of a registered agent."""
    role: AgentRole
    available: bool = True
    last_execution: float = 0
    total_tasks: int = 0
    success_rate: float = 1.0
    avg_duration_ms: float = 0
    provider_available: Dict[str, bool] = field(default_factory=dict)


class AgentRegistry:
    """
    Central registry for all specialized agents.

    Usage:
        registry = AgentRegistry()
        registry.register(ResearcherAgent())
        registry.register(OperatorAgent())

        # Route a task to the best agent
        result = registry.route_and_execute(task)

        # Or get agent for specific role
        researcher = registry.get(AgentRole.RESEARCHER)
    """

    def __init__(self):
        self._agents: Dict[AgentRole, BaseAgent] = {}
        self._status: Dict[AgentRole, AgentStatus] = {}
        self._load_state()

    def register(self, agent: BaseAgent) -> None:
        """Register an agent."""
        self._agents[agent.role] = agent
        if agent.role not in self._status:
            self._status[agent.role] = AgentStatus(
                role=agent.role,
                provider_available=agent.check_provider_availability(),
            )

    def get(self, role: AgentRole) -> Optional[BaseAgent]:
        """Get an agent by role."""
        return self._agents.get(role)

    def get_all(self) -> List[BaseAgent]:
        """Get all registered agents."""
        return list(self._agents.values())

    def route_task(self, task: AgentTask) -> Optional[BaseAgent]:
        """
        Route a task to the best-fit agent based on description matching.

        Returns the agent best suited to handle the task.
        """
        if not self._agents:
            return None

        # Score each agent's fit for the task
        scores = []
        for role, agent in self._agents.items():
            status = self._status.get(role)
            if status and not status.available:
                continue

            # Get agent's confidence it can handle this task
            fit_score = agent.can_handle(task.description)

            # Adjust by historical success rate
            if status:
                fit_score *= (0.5 + 0.5 * status.success_rate)

            scores.append((agent, fit_score))

        if not scores:
            return None

        # Return highest scoring agent
        scores.sort(key=lambda x: -x[1])
        return scores[0][0] if scores[0][1] > 0 else None

    def route_and_execute(self, task: AgentTask) -> AgentResult:
        """Route task to best agent and execute."""
        agent = self.route_task(task)

        if not agent:
            return AgentResult(
                task_id=task.id,
                success=False,
                output="",
                error="No suitable agent found for task",
            )

        # Execute
        start = time.time()
        result = agent.execute(task)
        result.duration_ms = int((time.time() - start) * 1000)

        # Update status
        self._update_status(agent.role, result)
        self._save_state()

        return result

    def execute_with_role(self, role: AgentRole, task: AgentTask) -> AgentResult:
        """Execute task with a specific agent role."""
        agent = self.get(role)

        if not agent:
            return AgentResult(
                task_id=task.id,
                success=False,
                output="",
                error=f"Agent {role.value} not registered",
            )

        start = time.time()
        result = agent.execute(task)
        result.duration_ms = int((time.time() - start) * 1000)

        self._update_status(role, result)
        self._save_state()

        return result

    def _update_status(self, role: AgentRole, result: AgentResult) -> None:
        """Update agent status after execution."""
        status = self._status.get(role)
        if not status:
            status = AgentStatus(role=role)
            self._status[role] = status

        status.last_execution = time.time()
        status.total_tasks += 1

        # Update success rate (exponential moving average)
        alpha = 0.2
        status.success_rate = (
            alpha * (1.0 if result.success else 0.0) +
            (1 - alpha) * status.success_rate
        )

        # Update average duration
        n = status.total_tasks
        status.avg_duration_ms = (
            (status.avg_duration_ms * (n - 1) + result.duration_ms) / n
        )

    def get_status(self, role: Optional[AgentRole] = None) -> Dict[str, Any]:
        """Get status of one or all agents."""
        if role:
            status = self._status.get(role)
            return asdict(status) if status else {}

        return {
            role.value: asdict(status)
            for role, status in self._status.items()
        }

    def check_all_availability(self) -> Dict[str, Dict[str, bool]]:
        """Check provider availability for all agents."""
        result = {}
        for role, agent in self._agents.items():
            availability = agent.check_provider_availability()
            result[role.value] = availability
            if role in self._status:
                self._status[role].provider_available = availability
        return result

    def get_self_sufficient_status(self) -> Dict[str, Any]:
        """Check if the system can run self-sufficiently (local only)."""
        availability = self.check_all_availability()

        # Check if Ollama is available for any agent
        ollama_available = any(
            avail.get("ollama", False)
            for avail in availability.values()
        )

        # Check which agents can run locally
        local_agents = [
            role for role, avail in availability.items()
            if avail.get("ollama", False)
        ]

        # Check cloud "transformers" available
        cloud_available = {}
        for role, avail in availability.items():
            cloud_available[role] = {
                "claude": avail.get("claude", False),
                "openai": avail.get("openai", False),
                "groq": avail.get("groq", False),
                "gemini": avail.get("gemini", False),
            }

        return {
            "self_sufficient": ollama_available,
            "local_provider": "ollama" if ollama_available else None,
            "local_agents": local_agents,
            "cloud_transformers": cloud_available,
            "recommendation": (
                "System is self-sufficient with local Ollama. "
                "Cloud APIs available as optional boosters."
                if ollama_available else
                "No local Ollama found. Install Ollama for self-sufficient operation."
            ),
        }

    def _load_state(self) -> None:
        """Load registry state from disk."""
        if REGISTRY_STATE.exists():
            try:
                with open(REGISTRY_STATE, "r") as f:
                    data = json.load(f)
                    for role_str, status_data in data.get("status", {}).items():
                        role = AgentRole(role_str)
                        self._status[role] = AgentStatus(
                            role=role,
                            available=status_data.get("available", True),
                            last_execution=status_data.get("last_execution", 0),
                            total_tasks=status_data.get("total_tasks", 0),
                            success_rate=status_data.get("success_rate", 1.0),
                            avg_duration_ms=status_data.get("avg_duration_ms", 0),
                        )
            except Exception:
                pass

    def _save_state(self) -> None:
        """Save registry state to disk."""
        REGISTRY_STATE.parent.mkdir(parents=True, exist_ok=True)
        with open(REGISTRY_STATE, "w") as f:
            json.dump({
                "status": {
                    role.value: asdict(status)
                    for role, status in self._status.items()
                },
                "updated_at": time.time(),
            }, f, indent=2, default=str)


# Global registry instance
_registry: Optional[AgentRegistry] = None


def get_registry() -> AgentRegistry:
    """Get the global agent registry."""
    global _registry
    if _registry is None:
        _registry = AgentRegistry()
    return _registry


def initialize_agents() -> AgentRegistry:
    """Initialize registry with all standard agents."""
    # Import here to avoid circular imports
    from core.agents.researcher import ResearcherAgent
    from core.agents.operator import OperatorAgent
    from core.agents.trader import TraderAgent
    from core.agents.architect import ArchitectAgent

    registry = get_registry()

    # Register all agents
    registry.register(ResearcherAgent())
    registry.register(OperatorAgent())
    registry.register(TraderAgent())
    registry.register(ArchitectAgent())

    return registry
