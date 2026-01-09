"""
Action Framework for Jarvis Self-Improving Core.

Actions are things Jarvis can DO, not just SAY.

Action types:
- Draft: Create content for review (requires COLLEAGUE trust)
- Schedule: Propose calendar events (requires COLLEAGUE trust)
- Remind: Set notifications (requires ACQUAINTANCE trust)
- Send: Execute communication (requires PARTNER trust)
- Execute: Run automations (requires OPERATOR trust)

Key principles:
- Trust level enforcement is bulletproof
- All actions are logged with full audit trail
- Reversible actions can be undone
- Actions link to the conversation that triggered them
"""

import json
import logging
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional, List, Dict, Any, Callable, Type
from dataclasses import dataclass, field
from enum import Enum

from core.self_improving.memory.store import MemoryStore
from core.self_improving.trust.ladder import TrustManager, TrustLevel, Permission

logger = logging.getLogger("jarvis.actions")


class ActionType(Enum):
    """Types of actions Jarvis can take."""

    REMIND = "remind"  # Set reminders/notifications
    DRAFT = "draft"  # Create content for review
    SCHEDULE = "schedule"  # Propose calendar events
    SEND = "send"  # Execute communication
    EXECUTE = "execute"  # Run automations
    RESEARCH = "research"  # Gather information


# Map action types to required trust levels
ACTION_TRUST_REQUIREMENTS = {
    ActionType.REMIND: TrustLevel.ACQUAINTANCE,
    ActionType.DRAFT: TrustLevel.COLLEAGUE,
    ActionType.SCHEDULE: TrustLevel.COLLEAGUE,
    ActionType.SEND: TrustLevel.PARTNER,
    ActionType.EXECUTE: TrustLevel.OPERATOR,
    ActionType.RESEARCH: TrustLevel.STRANGER,  # Research is always allowed
}


@dataclass
class ActionResult:
    """Result of executing an action."""

    success: bool
    message: str
    action_id: str
    action_type: ActionType
    domain: str
    data: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    reversible: bool = False
    executed_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "message": self.message,
            "action_id": self.action_id,
            "action_type": self.action_type.value,
            "domain": self.domain,
            "data": self.data,
            "error": self.error,
            "reversible": self.reversible,
            "executed_at": self.executed_at.isoformat(),
        }


@dataclass
class ActionContext:
    """Context for action execution."""

    user_id: Optional[str] = None
    session_id: Optional[str] = None
    conversation_id: Optional[str] = None
    triggered_by: str = "user_request"  # user_request, proactive, automation
    metadata: Dict[str, Any] = field(default_factory=dict)


class Action(ABC):
    """
    Base class for all actions.

    Subclass this to implement specific actions.
    """

    # Override in subclass
    name: str = "base_action"
    description: str = "Base action"
    action_type: ActionType = ActionType.EXECUTE
    domain: str = "general"
    reversible: bool = False

    def __init__(
        self,
        memory: MemoryStore,
        trust: TrustManager,
    ):
        self.memory = memory
        self.trust = trust
        self._execution_log: List[ActionResult] = []

    @property
    def required_trust(self) -> TrustLevel:
        """Get required trust level for this action."""
        return ACTION_TRUST_REQUIREMENTS.get(self.action_type, TrustLevel.OPERATOR)

    def check_permission(self) -> Permission:
        """Check if action is allowed at current trust level."""
        return self.trust.check_permission(
            self.action_type.value,
            self.domain,
        )

    @abstractmethod
    def execute(
        self,
        params: Dict[str, Any],
        context: ActionContext,
    ) -> ActionResult:
        """
        Execute the action.

        Override in subclass with specific implementation.
        """
        pass

    def rollback(self, action_id: str) -> ActionResult:
        """
        Rollback/undo the action if reversible.

        Override in subclass if action supports rollback.
        """
        return ActionResult(
            success=False,
            message="This action does not support rollback",
            action_id=action_id,
            action_type=self.action_type,
            domain=self.domain,
        )

    def validate_params(self, params: Dict[str, Any]) -> tuple[bool, str]:
        """
        Validate action parameters.

        Override in subclass for specific validation.
        Returns (is_valid, error_message).
        """
        return True, ""

    def _log_execution(self, result: ActionResult):
        """Log action execution for audit trail."""
        self._execution_log.append(result)

        # Also store in memory for persistence
        from core.self_improving.memory.models import Interaction

        self.memory.store_interaction(
            Interaction(
                user_input=f"[ACTION] {self.name}",
                jarvis_response=f"{'Success' if result.success else 'Failed'}: {result.message}",
                feedback="positive" if result.success else "negative",
                metadata={
                    "action_id": result.action_id,
                    "action_type": result.action_type.value,
                    "domain": result.domain,
                    "data": result.data,
                },
            )
        )

    def run(
        self,
        params: Dict[str, Any],
        context: Optional[ActionContext] = None,
    ) -> ActionResult:
        """
        Run the action with permission checks and logging.

        This is the main entry point - it handles:
        1. Permission check
        2. Parameter validation
        3. Execution
        4. Logging
        5. Trust update
        """
        if context is None:
            context = ActionContext()

        action_id = f"act_{datetime.utcnow().timestamp()}"

        # Check permission
        permission = self.check_permission()
        if not permission:
            result = ActionResult(
                success=False,
                message=self.trust.explain_denial(permission),
                action_id=action_id,
                action_type=self.action_type,
                domain=self.domain,
                error="Permission denied",
            )
            self._log_execution(result)
            return result

        # Validate parameters
        is_valid, error = self.validate_params(params)
        if not is_valid:
            result = ActionResult(
                success=False,
                message=f"Invalid parameters: {error}",
                action_id=action_id,
                action_type=self.action_type,
                domain=self.domain,
                error=error,
            )
            self._log_execution(result)
            return result

        # Execute
        try:
            result = self.execute(params, context)
            result.action_id = action_id
            result.reversible = self.reversible

            # Update trust based on outcome
            if result.success:
                self.trust.record_success(self.domain)
            else:
                self.trust.record_failure(self.domain)

            self._log_execution(result)
            return result

        except Exception as e:
            logger.error(f"Action {self.name} failed: {e}")
            result = ActionResult(
                success=False,
                message=f"Action failed: {str(e)}",
                action_id=action_id,
                action_type=self.action_type,
                domain=self.domain,
                error=str(e),
            )
            self.trust.record_failure(self.domain, major=True)
            self._log_execution(result)
            return result


class ActionRegistry:
    """
    Registry for available actions.

    Usage:
        registry = ActionRegistry(memory, trust)
        registry.register(ReminderAction)

        # Get available actions for current trust
        actions = registry.get_available_actions("calendar")

        # Execute an action
        result = registry.execute("set_reminder", params, context)
    """

    def __init__(self, memory: MemoryStore, trust: TrustManager):
        self.memory = memory
        self.trust = trust
        self._actions: Dict[str, Type[Action]] = {}
        self._instances: Dict[str, Action] = {}

    def register(self, action_class: Type[Action]):
        """Register an action class."""
        name = action_class.name
        self._actions[name] = action_class
        logger.debug(f"Registered action: {name}")

    def get_action(self, name: str) -> Optional[Action]:
        """Get an action instance by name."""
        if name not in self._instances:
            action_class = self._actions.get(name)
            if action_class:
                self._instances[name] = action_class(self.memory, self.trust)
        return self._instances.get(name)

    def get_available_actions(
        self,
        domain: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Get actions available at current trust level."""
        available = []

        for name, action_class in self._actions.items():
            # Create temp instance to check
            action = self.get_action(name)
            if not action:
                continue

            # Filter by domain if specified
            if domain and action.domain != domain and action.domain != "general":
                continue

            # Check permission
            permission = action.check_permission()

            available.append({
                "name": name,
                "description": action.description,
                "type": action.action_type.value,
                "domain": action.domain,
                "required_trust": action.required_trust.name,
                "allowed": permission.allowed,
            })

        return available

    def execute(
        self,
        action_name: str,
        params: Dict[str, Any],
        context: Optional[ActionContext] = None,
    ) -> ActionResult:
        """Execute an action by name."""
        action = self.get_action(action_name)

        if not action:
            return ActionResult(
                success=False,
                message=f"Unknown action: {action_name}",
                action_id=f"err_{datetime.utcnow().timestamp()}",
                action_type=ActionType.EXECUTE,
                domain="general",
                error="Action not found",
            )

        return action.run(params, context)

    def rollback(self, action_name: str, action_id: str) -> ActionResult:
        """Rollback an action."""
        action = self.get_action(action_name)

        if not action:
            return ActionResult(
                success=False,
                message=f"Unknown action: {action_name}",
                action_id=action_id,
                action_type=ActionType.EXECUTE,
                domain="general",
                error="Action not found",
            )

        return action.rollback(action_id)

    def list_all(self) -> List[str]:
        """List all registered action names."""
        return list(self._actions.keys())


# =============================================================================
# BUILT-IN ACTIONS
# =============================================================================


class ReminderAction(Action):
    """Action to set a reminder."""

    name = "set_reminder"
    description = "Set a reminder for a future time"
    action_type = ActionType.REMIND
    domain = "tasks"
    reversible = True

    def __init__(self, memory: MemoryStore, trust: TrustManager):
        super().__init__(memory, trust)
        self._reminders: Dict[str, Dict[str, Any]] = {}

    def validate_params(self, params: Dict[str, Any]) -> tuple[bool, str]:
        if "message" not in params:
            return False, "Missing 'message' parameter"
        if "when" not in params:
            return False, "Missing 'when' parameter"
        return True, ""

    def execute(
        self,
        params: Dict[str, Any],
        context: ActionContext,
    ) -> ActionResult:
        message = params["message"]
        when = params["when"]

        reminder_id = f"rem_{datetime.utcnow().timestamp()}"
        self._reminders[reminder_id] = {
            "message": message,
            "when": when,
            "created_at": datetime.utcnow().isoformat(),
            "context": context.metadata,
        }

        return ActionResult(
            success=True,
            message=f"Reminder set: {message}",
            action_id=reminder_id,
            action_type=self.action_type,
            domain=self.domain,
            data={"reminder_id": reminder_id, "when": when},
            reversible=True,
        )

    def rollback(self, action_id: str) -> ActionResult:
        if action_id in self._reminders:
            del self._reminders[action_id]
            return ActionResult(
                success=True,
                message="Reminder cancelled",
                action_id=action_id,
                action_type=self.action_type,
                domain=self.domain,
            )
        return ActionResult(
            success=False,
            message="Reminder not found",
            action_id=action_id,
            action_type=self.action_type,
            domain=self.domain,
        )


class DraftAction(Action):
    """Action to draft content for review."""

    name = "draft_content"
    description = "Create draft content (email, document, message) for review"
    action_type = ActionType.DRAFT
    domain = "general"
    reversible = True

    def __init__(self, memory: MemoryStore, trust: TrustManager):
        super().__init__(memory, trust)
        self._drafts: Dict[str, Dict[str, Any]] = {}

    def validate_params(self, params: Dict[str, Any]) -> tuple[bool, str]:
        if "content_type" not in params:
            return False, "Missing 'content_type' (email, document, message)"
        if "content" not in params:
            return False, "Missing 'content' parameter"
        return True, ""

    def execute(
        self,
        params: Dict[str, Any],
        context: ActionContext,
    ) -> ActionResult:
        content_type = params["content_type"]
        content = params["content"]
        recipient = params.get("recipient")

        draft_id = f"draft_{datetime.utcnow().timestamp()}"
        self._drafts[draft_id] = {
            "type": content_type,
            "content": content,
            "recipient": recipient,
            "created_at": datetime.utcnow().isoformat(),
            "status": "pending_review",
        }

        return ActionResult(
            success=True,
            message=f"Draft {content_type} created for review",
            action_id=draft_id,
            action_type=self.action_type,
            domain=self.domain,
            data={"draft_id": draft_id, "content_type": content_type},
            reversible=True,
        )

    def rollback(self, action_id: str) -> ActionResult:
        if action_id in self._drafts:
            del self._drafts[action_id]
            return ActionResult(
                success=True,
                message="Draft deleted",
                action_id=action_id,
                action_type=self.action_type,
                domain=self.domain,
            )
        return ActionResult(
            success=False,
            message="Draft not found",
            action_id=action_id,
            action_type=self.action_type,
            domain=self.domain,
        )


class ResearchAction(Action):
    """Action to gather information."""

    name = "research"
    description = "Gather information on a topic"
    action_type = ActionType.RESEARCH
    domain = "research"
    reversible = False

    def validate_params(self, params: Dict[str, Any]) -> tuple[bool, str]:
        if "query" not in params:
            return False, "Missing 'query' parameter"
        return True, ""

    def execute(
        self,
        params: Dict[str, Any],
        context: ActionContext,
    ) -> ActionResult:
        query = params["query"]

        # In real implementation, this would call search APIs
        # For now, just acknowledge the request

        return ActionResult(
            success=True,
            message=f"Research initiated for: {query}",
            action_id=f"res_{datetime.utcnow().timestamp()}",
            action_type=self.action_type,
            domain=self.domain,
            data={"query": query, "status": "in_progress"},
        )


def create_default_registry(
    memory: MemoryStore,
    trust: TrustManager,
) -> ActionRegistry:
    """Create a registry with default actions."""
    registry = ActionRegistry(memory, trust)
    registry.register(ReminderAction)
    registry.register(DraftAction)
    registry.register(ResearchAction)
    return registry
