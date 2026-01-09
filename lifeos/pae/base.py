"""
PAE Base Classes

Defines abstract base classes for:
- Provider: Data sources
- Action: Executable commands
- Evaluator: Decision makers

All components support:
- Async operations
- Health checks
- Metadata
- Dependency injection
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Set, TypeVar, Generic


class PAEError(Exception):
    """Base error for PAE system."""

    def __init__(
        self,
        component_name: str,
        message: str,
        original_error: Optional[Exception] = None,
    ):
        self.component_name = component_name
        self.message = message
        self.original_error = original_error
        super().__init__(f"[{component_name}] {message}")


class ProviderError(PAEError):
    """Error from a Provider component."""
    pass


class ActionError(PAEError):
    """Error from an Action component."""
    pass


class EvaluatorError(PAEError):
    """Error from an Evaluator component."""
    pass


class ComponentStatus(Enum):
    """Status of a PAE component."""
    UNINITIALIZED = "uninitialized"
    READY = "ready"
    BUSY = "busy"
    ERROR = "error"
    DISABLED = "disabled"


@dataclass
class ComponentHealth:
    """Health status of a component."""
    status: ComponentStatus
    message: str = ""
    last_check: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ComponentMetadata:
    """Metadata for a PAE component."""
    name: str
    description: str = ""
    version: str = "1.0.0"
    author: str = ""
    tags: List[str] = field(default_factory=list)
    requires: List[str] = field(default_factory=list)
    provides: List[str] = field(default_factory=list)


T = TypeVar('T')


class PAEComponent(ABC):
    """
    Base class for all PAE components.

    Provides common functionality:
    - Lifecycle management (initialize, shutdown)
    - Health checking
    - Dependency access
    """

    def __init__(self, name: str, dependencies: Optional[Dict[str, Any]] = None):
        """
        Initialize component.

        Args:
            name: Component name
            dependencies: Injected dependencies
        """
        self._name = name
        self._dependencies = dependencies or {}
        self._status = ComponentStatus.UNINITIALIZED
        self._metadata = ComponentMetadata(name=name)
        self._initialized_at: Optional[datetime] = None
        self._last_used: Optional[datetime] = None
        self._use_count = 0
        self._error_count = 0

    @property
    def name(self) -> str:
        """Component name."""
        return self._name

    @property
    def status(self) -> ComponentStatus:
        """Current status."""
        return self._status

    @property
    def metadata(self) -> ComponentMetadata:
        """Component metadata."""
        return self._metadata

    @property
    def stats(self) -> Dict[str, Any]:
        """Usage statistics."""
        return {
            "name": self._name,
            "status": self._status.value,
            "initialized_at": self._initialized_at.isoformat() if self._initialized_at else None,
            "last_used": self._last_used.isoformat() if self._last_used else None,
            "use_count": self._use_count,
            "error_count": self._error_count,
        }

    def get_dependency(self, name: str) -> Any:
        """Get an injected dependency."""
        if name not in self._dependencies:
            raise KeyError(f"Dependency not found: {name}")
        return self._dependencies[name]

    def has_dependency(self, name: str) -> bool:
        """Check if dependency exists."""
        return name in self._dependencies

    async def initialize(self) -> None:
        """
        Initialize the component.

        Override to add custom initialization logic.
        """
        self._status = ComponentStatus.READY
        self._initialized_at = datetime.now(timezone.utc)

    async def shutdown(self) -> None:
        """
        Shutdown the component.

        Override to add custom cleanup logic.
        """
        self._status = ComponentStatus.DISABLED

    async def health_check(self) -> ComponentHealth:
        """
        Check component health.

        Override to add custom health checks.
        """
        return ComponentHealth(
            status=self._status,
            message="OK" if self._status == ComponentStatus.READY else str(self._status.value),
        )

    def _record_use(self) -> None:
        """Record a usage of this component."""
        self._last_used = datetime.now(timezone.utc)
        self._use_count += 1

    def _record_error(self) -> None:
        """Record an error from this component."""
        self._error_count += 1


class Provider(PAEComponent):
    """
    Base class for data providers.

    Providers fetch or generate data from various sources:
    - External APIs
    - Databases
    - Files
    - Computed values

    Example:
        class WeatherProvider(Provider):
            async def provide(self, query):
                return await fetch_weather(query["location"])
    """

    @abstractmethod
    async def provide(
        self,
        query: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
    ) -> Any:
        """
        Provide data based on query.

        Args:
            query: Query parameters
            context: Optional execution context

        Returns:
            Provided data

        Raises:
            ProviderError: If data cannot be provided
        """
        pass

    async def validate_query(self, query: Dict[str, Any]) -> List[str]:
        """
        Validate a query before execution.

        Override to add custom validation.

        Args:
            query: Query to validate

        Returns:
            List of validation errors (empty if valid)
        """
        return []

    async def __call__(
        self,
        query: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
    ) -> Any:
        """Allow calling provider directly."""
        self._record_use()
        try:
            errors = await self.validate_query(query)
            if errors:
                raise ProviderError(
                    self.name,
                    f"Query validation failed: {', '.join(errors)}"
                )
            return await self.provide(query, context)
        except ProviderError:
            self._record_error()
            raise
        except Exception as e:
            self._record_error()
            raise ProviderError(self.name, str(e), original_error=e)


class Action(PAEComponent):
    """
    Base class for executable actions.

    Actions perform operations with side effects:
    - Send notifications
    - Execute trades
    - Write to databases
    - Call external APIs

    Example:
        class SendEmailAction(Action):
            async def execute(self, params):
                await send_email(
                    to=params["to"],
                    subject=params["subject"],
                    body=params["body"]
                )
                return {"sent": True}
    """

    @abstractmethod
    async def execute(
        self,
        params: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Execute the action.

        Args:
            params: Action parameters
            context: Optional execution context

        Returns:
            Result of the action

        Raises:
            ActionError: If action fails
        """
        pass

    async def validate_params(self, params: Dict[str, Any]) -> List[str]:
        """
        Validate parameters before execution.

        Override to add custom validation.

        Args:
            params: Parameters to validate

        Returns:
            List of validation errors (empty if valid)
        """
        return []

    async def rollback(
        self,
        params: Dict[str, Any],
        result: Dict[str, Any],
    ) -> bool:
        """
        Attempt to rollback a failed action.

        Override to support rollback.

        Args:
            params: Original parameters
            result: Partial result before failure

        Returns:
            True if rollback succeeded
        """
        return False

    @property
    def is_reversible(self) -> bool:
        """Whether this action can be rolled back."""
        return False

    @property
    def requires_confirmation(self) -> bool:
        """Whether this action requires user confirmation."""
        return False

    async def __call__(
        self,
        params: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Allow calling action directly."""
        self._record_use()
        try:
            errors = await self.validate_params(params)
            if errors:
                raise ActionError(
                    self.name,
                    f"Parameter validation failed: {', '.join(errors)}"
                )
            return await self.execute(params, context)
        except ActionError:
            self._record_error()
            raise
        except Exception as e:
            self._record_error()
            raise ActionError(self.name, str(e), original_error=e)


class Evaluator(PAEComponent):
    """
    Base class for decision evaluators.

    Evaluators make decisions based on context:
    - Should we send an alert?
    - Is this trade profitable?
    - Does this match user intent?

    Example:
        class RiskEvaluator(Evaluator):
            async def evaluate(self, context):
                risk_score = calculate_risk(context["position"])
                return EvaluationResult(
                    decision=risk_score < 0.3,
                    confidence=0.85,
                    reasoning="Risk within acceptable limits"
                )
    """

    @abstractmethod
    async def evaluate(
        self,
        context: Dict[str, Any],
    ) -> "EvaluationResult":
        """
        Evaluate context and make a decision.

        Args:
            context: Context for evaluation

        Returns:
            Evaluation result with decision and reasoning

        Raises:
            EvaluatorError: If evaluation fails
        """
        pass

    async def validate_context(self, context: Dict[str, Any]) -> List[str]:
        """
        Validate context before evaluation.

        Override to add custom validation.

        Args:
            context: Context to validate

        Returns:
            List of validation errors (empty if valid)
        """
        return []

    async def __call__(
        self,
        context: Dict[str, Any],
    ) -> "EvaluationResult":
        """Allow calling evaluator directly."""
        self._record_use()
        try:
            errors = await self.validate_context(context)
            if errors:
                raise EvaluatorError(
                    self.name,
                    f"Context validation failed: {', '.join(errors)}"
                )
            return await self.evaluate(context)
        except EvaluatorError:
            self._record_error()
            raise
        except Exception as e:
            self._record_error()
            raise EvaluatorError(self.name, str(e), original_error=e)


@dataclass
class EvaluationResult:
    """Result of an evaluation."""
    decision: bool
    confidence: float = 1.0
    reasoning: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    alternatives: List[Dict[str, Any]] = field(default_factory=list)

    def __bool__(self) -> bool:
        """Allow using result directly in conditionals."""
        return self.decision
