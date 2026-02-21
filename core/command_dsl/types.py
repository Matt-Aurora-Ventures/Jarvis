"""Types for the typed command DSL."""

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass(frozen=True)
class TypedCommand:
    """Validated representation of an executable command."""

    executor: str
    argv: List[str]
    timeout: Optional[int] = None
    cwd: Optional[str] = None
    env_overrides: Dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.executor:
            raise ValueError("executor is required")
        if not self.argv:
            raise ValueError("argv is required")


@dataclass(frozen=True)
class CommandValidationDecision:
    """Result from DSL command validation policy checks."""

    allowed: bool
    error: Optional[str] = None
    warnings: List[str] = field(default_factory=list)
