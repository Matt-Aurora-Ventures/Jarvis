"""
Durability models - Types for the run ledger.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
import uuid


class RunState(Enum):
    """State of a run."""
    PENDING = "pending"       # Run created but not started
    RUNNING = "running"       # Run in progress
    PAUSED = "paused"         # Run paused (can resume)
    COMPLETED = "completed"   # Run finished successfully
    FAILED = "failed"         # Run failed
    ABORTED = "aborted"       # Run manually aborted
    RECOVERING = "recovering" # Run being recovered after crash


class StepState(Enum):
    """State of a step within a run."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    SKIPPED = "skipped"
    FAILED = "failed"


@dataclass
class RunStep:
    """A single step in a run."""
    name: str
    state: StepState = StepState.PENDING
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error: Optional[str] = None
    result: Any = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "state": self.state.value,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "error": self.error,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RunStep":
        return cls(
            name=data["name"],
            state=StepState(data["state"]),
            started_at=datetime.fromisoformat(data["started_at"]) if data.get("started_at") else None,
            completed_at=datetime.fromisoformat(data["completed_at"]) if data.get("completed_at") else None,
            error=data.get("error"),
            result=data.get("result"),
            metadata=data.get("metadata", {}),
        )


@dataclass
class Run:
    """
    A durable run that can survive crashes.

    The run tracks:
    - What platform/component is running
    - What the intent is
    - What steps are planned
    - What step we're currently on
    - State of each step
    """
    id: str
    platform: str
    intent: str
    state: RunState = RunState.PENDING
    steps: List[RunStep] = field(default_factory=list)
    current_step_index: int = 0

    # Timestamps
    created_at: datetime = field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None

    # Recovery info
    recovery_count: int = 0
    last_recovery_at: Optional[datetime] = None

    @classmethod
    def create(
        cls,
        platform: str,
        intent: str,
        steps: List[str],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> "Run":
        """Create a new run with the given steps."""
        run_id = f"{platform}_{intent}_{uuid.uuid4().hex[:8]}"
        return cls(
            id=run_id,
            platform=platform,
            intent=intent,
            steps=[RunStep(name=step) for step in steps],
            metadata=metadata or {},
        )

    @property
    def current_step(self) -> Optional[str]:
        """Get the name of the current step."""
        if 0 <= self.current_step_index < len(self.steps):
            return self.steps[self.current_step_index].name
        return None

    @property
    def current_step_obj(self) -> Optional[RunStep]:
        """Get the current step object."""
        if 0 <= self.current_step_index < len(self.steps):
            return self.steps[self.current_step_index]
        return None

    @property
    def is_complete(self) -> bool:
        """Check if all steps are complete."""
        return all(
            s.state in (StepState.COMPLETED, StepState.SKIPPED)
            for s in self.steps
        )

    @property
    def progress_pct(self) -> float:
        """Get completion percentage."""
        if not self.steps:
            return 0.0
        completed = sum(
            1 for s in self.steps
            if s.state in (StepState.COMPLETED, StepState.SKIPPED)
        )
        return completed / len(self.steps) * 100

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "platform": self.platform,
            "intent": self.intent,
            "state": self.state.value,
            "steps": [s.to_dict() for s in self.steps],
            "current_step_index": self.current_step_index,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "metadata": self.metadata,
            "error": self.error,
            "recovery_count": self.recovery_count,
            "last_recovery_at": self.last_recovery_at.isoformat() if self.last_recovery_at else None,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Run":
        run = cls(
            id=data["id"],
            platform=data["platform"],
            intent=data["intent"],
            state=RunState(data["state"]),
            steps=[RunStep.from_dict(s) for s in data.get("steps", [])],
            current_step_index=data.get("current_step_index", 0),
            created_at=datetime.fromisoformat(data["created_at"]),
            started_at=datetime.fromisoformat(data["started_at"]) if data.get("started_at") else None,
            completed_at=datetime.fromisoformat(data["completed_at"]) if data.get("completed_at") else None,
            metadata=data.get("metadata", {}),
            error=data.get("error"),
            recovery_count=data.get("recovery_count", 0),
            last_recovery_at=datetime.fromisoformat(data["last_recovery_at"]) if data.get("last_recovery_at") else None,
        )
        return run

    def summary(self) -> str:
        """Get a human-readable summary."""
        step_info = f"step {self.current_step_index + 1}/{len(self.steps)}"
        if self.current_step:
            step_info += f" ({self.current_step})"
        return f"[{self.platform}] {self.intent} - {self.state.value} @ {step_info}"
