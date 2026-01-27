"""
SubAgent Manager - Track and manage spawned sub-agents.

This module provides infrastructure for tracking sub-agent execution,
similar to Clawdbot's subagent tracking system.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional, Dict, Any, List
import uuid
import os


# Default agent logs directory
AGENT_LOGS_DIR = Path(os.getenv("AGENT_LOGS_DIR", "/tmp/agent_logs"))


class AgentStatus(Enum):
    """Status values for agent execution."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    STOPPED = "stopped"


@dataclass
class SubAgent:
    """Represents a spawned sub-agent with execution tracking."""

    id: str
    session_id: str
    subagent_type: str
    description: str
    prompt: str
    status: str = "pending"
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    tokens_used: int = 0
    output_file: Optional[str] = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "id": self.id,
            "session_id": self.session_id,
            "subagent_type": self.subagent_type,
            "description": self.description,
            "prompt": self.prompt,
            "status": self.status,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "tokens_used": self.tokens_used,
            "output_file": self.output_file,
            "error": self.error,
            "metadata": self.metadata,
        }


class SubAgentManager:
    """Manages registration and tracking of sub-agents."""

    def __init__(self, db=None):
        """
        Initialize the SubAgentManager.

        Args:
            db: Optional DatabaseManager instance for persistence
        """
        self._agents: Dict[str, SubAgent] = {}
        self._db = db

    def register_agent(
        self,
        subagent_type: str,
        description: str,
        prompt: str,
        session_id: str,
        agent_id: Optional[str] = None,
        **kwargs
    ) -> SubAgent:
        """
        Register a new sub-agent.

        Args:
            subagent_type: Type of agent (scout, kraken, architect, etc.)
            description: Human-readable description of the task
            prompt: Full prompt sent to the agent
            session_id: Session identifier (e.g., "tg:user123:main")
            agent_id: Optional agent ID (generated if not provided)
            **kwargs: Additional fields (status, metadata, etc.)

        Returns:
            Registered SubAgent instance
        """
        # Generate ID if not provided
        if agent_id is None:
            agent_id = str(uuid.uuid4())[:7]  # Short hash format

        # Create agent
        agent = SubAgent(
            id=agent_id,
            session_id=session_id,
            subagent_type=subagent_type,
            description=description,
            prompt=prompt,
            **kwargs
        )

        # Store in registry
        self._agents[agent_id] = agent

        return agent

    def update_status(
        self,
        agent_id: str,
        status: str,
        tokens: Optional[int] = None,
        error: Optional[str] = None,
        output_file: Optional[str] = None,
    ) -> SubAgent:
        """
        Update agent status and execution details.

        Args:
            agent_id: Agent ID to update
            status: New status (pending, running, completed, failed, stopped)
            tokens: Token usage (optional)
            error: Error message if failed (optional)
            output_file: Path to output file (optional)

        Returns:
            Updated SubAgent instance
        """
        if agent_id not in self._agents:
            raise KeyError(f"Agent {agent_id} not found")

        agent = self._agents[agent_id]

        # Update status
        agent.status = status

        # Update timestamps
        if status == "running" and agent.started_at is None:
            agent.started_at = datetime.now()
        elif status in ("completed", "failed", "stopped"):
            agent.completed_at = datetime.now()

        # Update optional fields
        if tokens is not None:
            agent.tokens_used = tokens
        if error is not None:
            agent.error = error
        if output_file is not None:
            agent.output_file = output_file

        return agent

    def get_agent(self, agent_id: str) -> Optional[SubAgent]:
        """
        Retrieve an agent by ID.

        Args:
            agent_id: Agent ID to retrieve

        Returns:
            SubAgent instance or None if not found
        """
        return self._agents.get(agent_id)

    def list_agents(
        self,
        session_id: Optional[str] = None,
        status: Optional[str] = None,
        subagent_type: Optional[str] = None,
    ) -> List[SubAgent]:
        """
        List agents with optional filtering.

        Args:
            session_id: Filter by session ID (optional)
            status: Filter by status (optional)
            subagent_type: Filter by agent type (optional)

        Returns:
            List of matching SubAgent instances
        """
        agents = list(self._agents.values())

        if session_id:
            agents = [a for a in agents if a.session_id == session_id]
        if status:
            agents = [a for a in agents if a.status == status]
        if subagent_type:
            agents = [a for a in agents if a.subagent_type == subagent_type]

        return agents

    def get_session_summary(self, session_id: str) -> Dict[str, Any]:
        """
        Get summary statistics for a session.

        Args:
            session_id: Session ID to summarize

        Returns:
            Dictionary with session statistics
        """
        agents = self.list_agents(session_id=session_id)

        if not agents:
            return {
                "total": 0,
                "running": 0,
                "completed": 0,
                "failed": 0,
                "pending": 0,
                "stopped": 0,
                "total_tokens": 0,
            }

        status_counts = {}
        for agent in agents:
            status_counts[agent.status] = status_counts.get(agent.status, 0) + 1

        total_tokens = sum(a.tokens_used for a in agents)

        return {
            "total": len(agents),
            "running": status_counts.get("running", 0),
            "completed": status_counts.get("completed", 0),
            "failed": status_counts.get("failed", 0),
            "pending": status_counts.get("pending", 0),
            "stopped": status_counts.get("stopped", 0),
            "total_tokens": total_tokens,
        }

    def get_agent_output(self, agent_id: str) -> Optional[str]:
        """
        Retrieve agent output from file.

        Args:
            agent_id: Agent ID to retrieve output for

        Returns:
            Output file contents or None if no output file
        """
        agent = self.get_agent(agent_id)
        if not agent or not agent.output_file:
            return None

        try:
            output_path = Path(agent.output_file)
            if output_path.exists():
                return output_path.read_text(encoding="utf-8")
        except Exception as e:
            # Log error but don't raise
            pass

        return None

    def stop_agent(self, agent_id: str) -> bool:
        """
        Stop a running agent.

        Args:
            agent_id: Agent ID to stop

        Returns:
            True if agent was stopped, False if not running
        """
        agent = self.get_agent(agent_id)
        if not agent or agent.status != "running":
            return False

        self.update_status(agent_id, "stopped")
        return True

    def get_agent_log(self, agent_id: str) -> Optional[str]:
        """
        Retrieve agent execution log.

        Args:
            agent_id: Agent ID to retrieve log for

        Returns:
            Log file contents or None if no log file
        """
        # Check for log file in AGENT_LOGS_DIR
        log_file = AGENT_LOGS_DIR / f"{agent_id}.log"

        if log_file.exists():
            try:
                return log_file.read_text(encoding="utf-8")
            except Exception:
                pass

        return None

    def format_agent_list(self, session_id: str) -> str:
        """
        Format agent list for display.

        Args:
            session_id: Session ID to format agents for

        Returns:
            Formatted string with agent list
        """
        agents = self.list_agents(session_id=session_id)

        if not agents:
            return f"No active subagents for session {session_id}"

        output = [f"Active Subagents for {session_id}:"]
        output.append("")

        # Group by status
        running = [a for a in agents if a.status == "running"]
        completed = [a for a in agents if a.status == "completed"]
        failed = [a for a in agents if a.status == "failed"]
        pending = [a for a in agents if a.status == "pending"]

        if running:
            output.append("RUNNING:")
            for agent in running:
                output.append(f"  {agent.id} - {agent.description}")
            output.append("")

        if completed:
            output.append("COMPLETED:")
            for agent in completed:
                tokens_str = f"{agent.tokens_used // 1000}K" if agent.tokens_used >= 1000 else str(agent.tokens_used)
                output.append(f"  {agent.id} - {agent.description} ({tokens_str} tokens)")
            output.append("")

        if failed:
            output.append("FAILED:")
            for agent in failed:
                error_str = f" - {agent.error}" if agent.error else ""
                output.append(f"  {agent.id} - {agent.description}{error_str}")
            output.append("")

        if pending:
            output.append("PENDING:")
            for agent in pending:
                output.append(f"  {agent.id} - {agent.description}")

        return "\n".join(output)

    def format_agent_info(self, agent_id: str) -> str:
        """
        Format detailed agent info.

        Args:
            agent_id: Agent ID to format info for

        Returns:
            Formatted string with agent details
        """
        agent = self.get_agent(agent_id)
        if not agent:
            return f"Agent {agent_id} not found"

        output = [f"Agent: {agent.id}"]
        output.append(f"Type: {agent.subagent_type}")
        output.append(f"Description: {agent.description}")
        output.append(f"Status: {agent.status}")
        output.append(f"Session: {agent.session_id}")

        if agent.started_at:
            output.append(f"Started: {agent.started_at.isoformat()}")
        if agent.completed_at:
            output.append(f"Completed: {agent.completed_at.isoformat()}")
        if agent.tokens_used:
            output.append(f"Tokens: {agent.tokens_used:,}")
        if agent.error:
            output.append(f"Error: {agent.error}")
        if agent.output_file:
            output.append(f"Output: {agent.output_file}")

        return "\n".join(output)


# Singleton instance for convenience
_manager: Optional[SubAgentManager] = None


def get_manager() -> SubAgentManager:
    """Get or create the singleton SubAgentManager instance."""
    global _manager
    if _manager is None:
        _manager = SubAgentManager()
    return _manager
