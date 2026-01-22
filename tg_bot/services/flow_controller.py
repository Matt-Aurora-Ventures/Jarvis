"""
Telegram Flow Controller - Explicit Command → Plan → Execute Flow.

Implements the pattern:
1. Parse command
2. Generate plan
3. Validate + risk-check
4. Execute OR HOLD
5. Respond with rationale

This avoids "do it immediately" handlers and makes decisions transparent.

Usage:
    from tg_bot.services.flow_controller import get_flow_controller

    controller = get_flow_controller()

    # Process a command
    result = await controller.process_command(
        command="buy",
        args=["SOL", "0.1"],
        user_id=123456,
        chat_id=-100123456,
    )

    if result.should_execute:
        await execute_trade(result.plan)
    else:
        await message.reply(result.hold_reason)
"""

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Singleton instance
_flow_controller: Optional["FlowController"] = None


class IntentType(Enum):
    """Classification of command intent."""
    INFO = "info"           # Read-only, safe
    ACTION = "action"       # State-changing, needs confirmation
    ADMIN = "admin"         # Administrative, high privilege
    BROADCAST = "broadcast" # Public-facing, highest risk


class FlowDecision(Enum):
    """Decision for a command flow."""
    EXECUTE = "execute"     # Proceed with action
    HOLD = "hold"           # Do not act
    CONFIRM = "confirm"     # Requires user confirmation
    ESCALATE = "escalate"   # Needs admin review


@dataclass
class CommandPlan:
    """
    Plan for executing a command.

    The plan describes what will happen if executed,
    allowing the user to understand before confirming.
    """
    command: str
    intent_type: IntentType
    description: str
    signals_to_check: List[str] = field(default_factory=list)
    actions: List[str] = field(default_factory=list)
    risks: List[str] = field(default_factory=list)
    estimated_cost: float = 0.0
    requires_confirmation: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)

    def summary(self) -> str:
        """Get a user-friendly summary of the plan."""
        lines = [f"*Plan: {self.command}*", "", self.description]

        if self.actions:
            lines.append("\n*Actions:*")
            for action in self.actions:
                lines.append(f"  • {action}")

        if self.risks:
            lines.append("\n*Risks:*")
            for risk in self.risks:
                lines.append(f"  ⚠️ {risk}")

        if self.estimated_cost > 0:
            lines.append(f"\n*Estimated cost:* ${self.estimated_cost:.4f}")

        return "\n".join(lines)


@dataclass
class FlowResult:
    """
    Result of processing a command through the flow.
    """
    decision: FlowDecision
    plan: Optional[CommandPlan] = None
    should_execute: bool = False
    hold_reason: Optional[str] = None
    confirmation_message: Optional[str] = None
    confirmation_id: Optional[str] = None
    response_message: str = ""

    # Audit
    processing_time_ms: float = 0.0
    checks_performed: List[str] = field(default_factory=list)


@dataclass
class ConversationContext:
    """
    Session context for a conversation.

    Tracks state across messages for follow-up handling.
    """
    user_id: int
    chat_id: int
    last_intent: Optional[str] = None
    last_command: Optional[str] = None
    last_message_time: float = 0.0
    pending_confirmation: Optional[str] = None
    pending_plan: Optional[CommandPlan] = None
    message_count: int = 0
    created_at: datetime = field(default_factory=datetime.utcnow)

    def is_expired(self, ttl_seconds: int = 300) -> bool:
        """Check if the context has expired."""
        return time.time() - self.last_message_time > ttl_seconds


class FlowController:
    """
    Controls the flow of Telegram commands.

    Implements:
    1. Intent classification
    2. Plan generation
    3. Risk checking
    4. Confirmation flow
    5. Execution or hold
    """

    # Command classifications
    INFO_COMMANDS = {
        "start", "help", "balance", "positions", "price",
        "market", "status", "digest", "sentiment", "analyze",
        "portfolio", "history", "alerts",
    }
    ACTION_COMMANDS = {
        "buy", "sell", "swap", "trade", "close", "dca",
        "limit", "stop", "trail", "exit", "cancel",
    }
    ADMIN_COMMANDS = {
        "config", "reload", "restart", "logs", "system",
        "kill", "enable", "disable", "users", "stats",
    }
    BROADCAST_COMMANDS = {
        "broadcast", "announce", "alert_all",
    }

    def __init__(self, require_confirmation: bool = True):
        self.require_confirmation = require_confirmation
        self.contexts: Dict[Tuple[int, int], ConversationContext] = {}
        self._pending_confirmations: Dict[str, Tuple[int, CommandPlan]] = {}
        self._context_ttl = 300  # 5 minutes

    def classify_intent(self, command: str) -> IntentType:
        """Classify the intent of a command."""
        cmd = command.lower().strip("/")

        if cmd in self.INFO_COMMANDS:
            return IntentType.INFO
        elif cmd in self.ACTION_COMMANDS:
            return IntentType.ACTION
        elif cmd in self.ADMIN_COMMANDS:
            return IntentType.ADMIN
        elif cmd in self.BROADCAST_COMMANDS:
            return IntentType.BROADCAST
        else:
            # Default to INFO for unknown commands
            return IntentType.INFO

    def get_context(self, user_id: int, chat_id: int) -> ConversationContext:
        """Get or create a conversation context."""
        key = (user_id, chat_id)
        if key not in self.contexts:
            self.contexts[key] = ConversationContext(
                user_id=user_id,
                chat_id=chat_id,
                last_message_time=time.time(),
            )
        else:
            ctx = self.contexts[key]
            if ctx.is_expired(self._context_ttl):
                # Reset expired context
                self.contexts[key] = ConversationContext(
                    user_id=user_id,
                    chat_id=chat_id,
                    last_message_time=time.time(),
                )
        return self.contexts[key]

    def update_context(
        self,
        user_id: int,
        chat_id: int,
        command: Optional[str] = None,
        intent: Optional[str] = None,
    ) -> ConversationContext:
        """Update conversation context."""
        ctx = self.get_context(user_id, chat_id)
        ctx.last_message_time = time.time()
        ctx.message_count += 1
        if command:
            ctx.last_command = command
        if intent:
            ctx.last_intent = intent
        return ctx

    async def generate_plan(
        self,
        command: str,
        args: List[str],
        intent_type: IntentType,
    ) -> CommandPlan:
        """Generate an execution plan for a command."""
        cmd = command.lower().strip("/")

        plan = CommandPlan(
            command=cmd,
            intent_type=intent_type,
            description="",
        )

        # Generate plan based on command type
        if cmd == "buy":
            token = args[0] if args else "?"
            amount = args[1] if len(args) > 1 else "?"
            plan.description = f"Buy {amount} SOL worth of {token}"
            plan.actions = [
                f"Check {token} price and liquidity",
                f"Calculate swap with {amount} SOL",
                f"Execute swap via Jupiter",
                "Record position in portfolio",
            ]
            plan.signals_to_check = ["price", "liquidity", "slippage"]
            plan.risks = [
                "Token could drop in value",
                "Slippage may affect final amount",
            ]
            plan.estimated_cost = float(amount) * 0.003 if amount.replace(".", "").isdigit() else 0
            plan.requires_confirmation = True

        elif cmd == "sell":
            token = args[0] if args else "?"
            amount = args[1] if len(args) > 1 else "all"
            plan.description = f"Sell {amount} of {token}"
            plan.actions = [
                f"Check current {token} balance",
                f"Calculate swap for {amount}",
                "Execute swap via Jupiter",
                "Update position record",
            ]
            plan.risks = ["Market conditions may have changed"]
            plan.requires_confirmation = True

        elif cmd == "balance":
            plan.description = "Display wallet balances"
            plan.actions = ["Fetch SOL balance", "Fetch token balances"]
            plan.signals_to_check = []

        elif cmd == "positions":
            plan.description = "Display current positions"
            plan.actions = ["Load position data", "Calculate P&L"]

        elif cmd == "broadcast":
            message = " ".join(args) if args else "?"
            plan.description = f"Broadcast message to all users"
            plan.actions = [
                "Load user list",
                f"Send: {message[:50]}...",
                "Record delivery status",
            ]
            plan.risks = ["Message will be sent to ALL users", "Cannot be undone"]
            plan.requires_confirmation = True

        else:
            plan.description = f"Execute {cmd} command"

        return plan

    async def validate_plan(
        self,
        plan: CommandPlan,
        user_id: int,
        is_admin: bool = False,
    ) -> Tuple[bool, str]:
        """
        Validate a plan before execution.

        Returns (is_valid, reason)
        """
        # Check admin commands
        if plan.intent_type == IntentType.ADMIN and not is_admin:
            return False, "Admin permission required"

        if plan.intent_type == IntentType.BROADCAST and not is_admin:
            return False, "Admin permission required for broadcasts"

        # Check for high-risk actions
        if plan.estimated_cost > 100:
            return False, f"Estimated cost ${plan.estimated_cost:.2f} exceeds limit"

        return True, "Plan validated"

    async def process_command(
        self,
        command: str,
        args: List[str],
        user_id: int,
        chat_id: int,
        is_admin: bool = False,
        force_execute: bool = False,
    ) -> FlowResult:
        """
        Process a command through the full flow.

        Flow:
        1. Classify intent
        2. Generate plan
        3. Validate
        4. Decide (execute/confirm/hold)
        5. Return result
        """
        start_time = time.time()
        result = FlowResult(decision=FlowDecision.HOLD)

        # Get conversation context
        ctx = self.update_context(user_id, chat_id, command)

        # 1. Classify intent
        intent_type = self.classify_intent(command)
        ctx.last_intent = intent_type.value
        result.checks_performed.append(f"intent:{intent_type.value}")

        # 2. Generate plan
        plan = await self.generate_plan(command, args, intent_type)
        result.plan = plan
        result.checks_performed.append("plan_generated")

        # 3. Validate
        is_valid, reason = await self.validate_plan(plan, user_id, is_admin)
        result.checks_performed.append(f"validate:{is_valid}")

        if not is_valid:
            result.decision = FlowDecision.HOLD
            result.hold_reason = reason
            result.response_message = f"❌ {reason}"
            result.processing_time_ms = (time.time() - start_time) * 1000
            return result

        # 4. Decide
        if intent_type == IntentType.INFO:
            # Info commands always execute
            result.decision = FlowDecision.EXECUTE
            result.should_execute = True
            result.response_message = "ℹ️ Processing..."

        elif intent_type == IntentType.ACTION:
            if self.require_confirmation and plan.requires_confirmation and not force_execute:
                # Needs confirmation
                confirmation_id = f"{user_id}_{int(time.time())}"
                self._pending_confirmations[confirmation_id] = (user_id, plan)
                ctx.pending_confirmation = confirmation_id
                ctx.pending_plan = plan

                result.decision = FlowDecision.CONFIRM
                result.confirmation_id = confirmation_id
                result.confirmation_message = (
                    f"{plan.summary()}\n\n"
                    f"Reply with /confirm to proceed or /cancel to abort."
                )
                result.response_message = result.confirmation_message
            else:
                result.decision = FlowDecision.EXECUTE
                result.should_execute = True
                result.response_message = f"✅ Executing: {plan.description}"

        elif intent_type in (IntentType.ADMIN, IntentType.BROADCAST):
            if plan.requires_confirmation and not force_execute:
                confirmation_id = f"{user_id}_{int(time.time())}"
                self._pending_confirmations[confirmation_id] = (user_id, plan)

                result.decision = FlowDecision.CONFIRM
                result.confirmation_id = confirmation_id
                result.confirmation_message = (
                    f"⚠️ *Admin Action Required*\n\n"
                    f"{plan.summary()}\n\n"
                    f"Reply with /confirm to proceed or /cancel to abort."
                )
                result.response_message = result.confirmation_message
            else:
                result.decision = FlowDecision.EXECUTE
                result.should_execute = True

        result.processing_time_ms = (time.time() - start_time) * 1000
        return result

    async def confirm(
        self,
        user_id: int,
        confirmation_id: Optional[str] = None,
    ) -> FlowResult:
        """Confirm a pending action."""
        result = FlowResult(decision=FlowDecision.HOLD)

        # Find pending confirmation
        if confirmation_id and confirmation_id in self._pending_confirmations:
            pending_user_id, plan = self._pending_confirmations.pop(confirmation_id)
            if pending_user_id == user_id:
                result.decision = FlowDecision.EXECUTE
                result.should_execute = True
                result.plan = plan
                result.response_message = f"✅ Confirmed. Executing: {plan.description}"
                return result

        # Check context for pending confirmation
        for key, ctx in self.contexts.items():
            if ctx.user_id == user_id and ctx.pending_confirmation:
                if ctx.pending_confirmation in self._pending_confirmations:
                    _, plan = self._pending_confirmations.pop(ctx.pending_confirmation)
                    ctx.pending_confirmation = None
                    ctx.pending_plan = None

                    result.decision = FlowDecision.EXECUTE
                    result.should_execute = True
                    result.plan = plan
                    result.response_message = f"✅ Confirmed. Executing: {plan.description}"
                    return result

        result.hold_reason = "No pending action to confirm"
        result.response_message = "❓ No pending action to confirm"
        return result

    async def cancel(self, user_id: int) -> FlowResult:
        """Cancel a pending action."""
        result = FlowResult(decision=FlowDecision.HOLD)

        # Find and remove pending confirmation
        for key, ctx in list(self.contexts.items()):
            if ctx.user_id == user_id and ctx.pending_confirmation:
                if ctx.pending_confirmation in self._pending_confirmations:
                    self._pending_confirmations.pop(ctx.pending_confirmation)
                ctx.pending_confirmation = None
                ctx.pending_plan = None

                result.response_message = "❌ Action cancelled"
                return result

        result.response_message = "❓ No pending action to cancel"
        return result

    def cleanup_expired(self) -> int:
        """Clean up expired contexts and confirmations."""
        now = time.time()
        expired = 0

        # Clean contexts
        for key in list(self.contexts.keys()):
            if self.contexts[key].is_expired(self._context_ttl):
                del self.contexts[key]
                expired += 1

        # Clean old confirmations (5 minute timeout)
        for conf_id in list(self._pending_confirmations.keys()):
            try:
                timestamp = int(conf_id.split("_")[-1])
                if now - timestamp > 300:
                    del self._pending_confirmations[conf_id]
                    expired += 1
            except (ValueError, IndexError):
                pass

        return expired


def get_flow_controller() -> FlowController:
    """Get or create the singleton flow controller."""
    global _flow_controller
    if _flow_controller is None:
        _flow_controller = FlowController()
    return _flow_controller
