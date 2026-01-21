"""
Recovery configuration types.

Defines the configuration and context types for the recovery engine.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple, Type


class RecoveryPolicy(Enum):
    """Recovery policy for handling failures."""
    RETRY = "retry"              # Retry with backoff
    CIRCUIT_BREAK = "circuit"    # Open circuit after threshold
    FALLBACK = "fallback"        # Use fallback function
    IGNORE = "ignore"            # Log and ignore
    ESCALATE = "escalate"        # Notify human
    ABORT = "abort"              # Stop immediately


class RecoveryOutcome(Enum):
    """Outcome of a recovery attempt."""
    SUCCESS = "success"
    RETRY_PENDING = "retry_pending"
    CIRCUIT_OPEN = "circuit_open"
    FALLBACK_USED = "fallback_used"
    ESCALATED = "escalated"
    ABORTED = "aborted"
    FAILED = "failed"


@dataclass
class ComponentConfig:
    """
    Configuration for a recoverable component.

    Attributes:
        max_retries: Maximum retry attempts before giving up
        retry_base_delay: Base delay between retries (seconds)
        retry_max_delay: Maximum delay between retries (seconds)
        retry_multiplier: Multiplier for exponential backoff
        circuit_threshold: Failures before circuit opens
        circuit_cooldown: Seconds to wait when circuit is open
        circuit_half_open_max: Max attempts in half-open state
        fallback: Optional fallback function
        retryable_errors: Error types that can be retried
        non_retryable_errors: Error types that should never be retried
        on_recovery: Callback when recovery succeeds
        on_failure: Callback when recovery fails
        policies: Ordered policies to apply
    """
    max_retries: int = 3
    retry_base_delay: float = 1.0
    retry_max_delay: float = 60.0
    retry_multiplier: float = 2.0
    retry_jitter: float = 0.1

    circuit_threshold: int = 5
    circuit_cooldown: float = 60.0
    circuit_half_open_max: int = 2
    circuit_success_threshold: int = 2

    fallback: Optional[Callable] = None
    retryable_errors: Tuple[Type[Exception], ...] = (
        ConnectionError,
        TimeoutError,
        OSError,
    )
    non_retryable_errors: Tuple[Type[Exception], ...] = (
        ValueError,
        TypeError,
        KeyError,
    )

    on_recovery: Optional[Callable] = None
    on_failure: Optional[Callable] = None

    policies: List[RecoveryPolicy] = field(default_factory=lambda: [
        RecoveryPolicy.RETRY,
        RecoveryPolicy.CIRCUIT_BREAK,
    ])


@dataclass
class RecoveryContext:
    """
    Context for a recovery operation.

    Captures all information about a recovery attempt for logging,
    debugging, and audit purposes.
    """
    component: str
    operation: str
    attempt: int
    max_attempts: int
    started_at: datetime
    ended_at: Optional[datetime] = None
    outcome: Optional[RecoveryOutcome] = None

    # Error tracking
    errors: List[Dict[str, Any]] = field(default_factory=list)
    last_error: Optional[str] = None
    last_error_type: Optional[str] = None

    # Timing
    total_delay: float = 0.0
    delays: List[float] = field(default_factory=list)

    # State
    circuit_state: str = "closed"
    used_fallback: bool = False
    escalated: bool = False

    # Result
    result: Any = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for logging."""
        return {
            "component": self.component,
            "operation": self.operation,
            "attempt": self.attempt,
            "max_attempts": self.max_attempts,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "ended_at": self.ended_at.isoformat() if self.ended_at else None,
            "outcome": self.outcome.value if self.outcome else None,
            "last_error": self.last_error,
            "last_error_type": self.last_error_type,
            "total_delay": self.total_delay,
            "circuit_state": self.circuit_state,
            "used_fallback": self.used_fallback,
            "escalated": self.escalated,
        }

    def add_error(self, error: Exception) -> None:
        """Add an error to the context."""
        self.errors.append({
            "type": type(error).__name__,
            "message": str(error),
            "attempt": self.attempt,
            "timestamp": datetime.utcnow().isoformat(),
        })
        self.last_error = str(error)
        self.last_error_type = type(error).__name__


# Predefined configurations for common components
TELEGRAM_CONFIG = ComponentConfig(
    max_retries=3,
    retry_base_delay=2.0,
    circuit_threshold=10,
    circuit_cooldown=300.0,  # 5 minutes
    retryable_errors=(
        ConnectionError,
        TimeoutError,
        OSError,
    ),
)

X_BOT_CONFIG = ComponentConfig(
    max_retries=3,
    retry_base_delay=5.0,
    retry_max_delay=120.0,
    circuit_threshold=3,
    circuit_cooldown=1800.0,  # 30 minutes
    retryable_errors=(
        ConnectionError,
        TimeoutError,
        OSError,
    ),
)

TRADING_CONFIG = ComponentConfig(
    max_retries=2,
    retry_base_delay=1.0,
    retry_max_delay=10.0,
    circuit_threshold=5,
    circuit_cooldown=60.0,
    policies=[
        RecoveryPolicy.RETRY,
        RecoveryPolicy.ESCALATE,  # Always escalate trading failures
    ],
)

TOOL_CONFIG = ComponentConfig(
    max_retries=2,
    retry_base_delay=0.5,
    circuit_threshold=10,
    circuit_cooldown=30.0,
)
