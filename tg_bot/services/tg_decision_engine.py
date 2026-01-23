"""
Telegram Bot Decision Engine - Enforces decision framework for bot actions.

This module provides decision-making for:
1. Command execution (should we run this command?)
2. Response generation (should we respond to this message?)
3. Action confirmation (should we execute this trade/action?)

Key Principles:
- HOLD is a first-class decision (restraint is intelligence)
- Full audit trail for all decisions
- Permission + intent validation
- Rate limiting and cooldowns
"""

import logging
import time
from datetime import datetime
from typing import Dict, Any, Optional, List

from core.decisions import (
    DecisionEngine,
    DecisionContext,
    DecisionResult,
    Decision,
    RiskLevel,
    RateLimitRule,
    CostThresholdRule,
    ConfidenceThresholdRule,
    CircuitBreakerRule,
)

logger = logging.getLogger(__name__)

# Singleton instance
_tg_decision_engine: Optional["TelegramDecisionEngine"] = None


class IntentClassificationRule:
    """
    Classifies command intent and applies appropriate restrictions.

    Intent types:
    - INFO: Read-only, low risk (e.g., /balance, /status)
    - ACTION: State-changing, medium risk (e.g., /buy, /sell)
    - ADMIN: Administrative, high risk (e.g., /config, /restart)
    - BROADCAST: Public-facing, high risk (e.g., /announce)
    """

    name = "intent_classification"
    description = "Classifies and validates command intent"
    priority = 10

    # Intent classifications
    INFO_COMMANDS = {
        "balance", "status", "positions", "price", "market",
        "help", "start", "digest", "sentiment", "analyze",
    }
    ACTION_COMMANDS = {
        "buy", "sell", "swap", "trade", "close", "dca",
        "limit", "stop", "trail", "exit",
    }
    ADMIN_COMMANDS = {
        "config", "reload", "restart", "logs", "system",
        "kill", "enable", "disable", "broadcast",
    }

    def __init__(self, require_confirmation_for_actions: bool = True):
        self.require_confirmation = require_confirmation_for_actions

    async def evaluate(
        self,
        context: DecisionContext,
        current_decision: Decision = Decision.EXECUTE,
    ) -> tuple[Decision, str, List[str]]:
        # Non-command chat messages should not be blocked by command intent rules.
        # This keeps normal chat replies responsive while preserving command safety.
        if context.intent == "respond_message":
            return (Decision.EXECUTE, "Non-command message response allowed", [])

        command = context.data.get("command", "").lower().strip("/")
        what_would_change = []

        # Classify intent
        if command in self.INFO_COMMANDS:
            intent = "INFO"
        elif command in self.ACTION_COMMANDS:
            intent = "ACTION"
        elif command in self.ADMIN_COMMANDS:
            intent = "ADMIN"
        else:
            intent = "UNKNOWN"

        # INFO commands always pass
        if intent == "INFO":
            return (Decision.EXECUTE, f"Info command '{command}' allowed", [])

        # ACTION commands may need confirmation
        if intent == "ACTION":
            confirmed = context.data.get("confirmed", False)
            if self.require_confirmation and not confirmed:
                what_would_change.append("User confirms the action")
                return (
                    Decision.HOLD,
                    f"Action '{command}' requires confirmation",
                    what_would_change,
                )
            return (Decision.EXECUTE, f"Action command '{command}' confirmed", [])

        # ADMIN commands escalate for review
        if intent == "ADMIN":
            return (
                Decision.EXECUTE,  # Admin commands are already protected by @admin_only
                f"Admin command '{command}' - verified admin user",
                [],
            )

        # Unknown commands - be cautious
        what_would_change.append(f"Register command '{command}' as known")
        return (
            Decision.HOLD,
            f"Unknown command '{command}'",
            what_would_change,
        )


class UserRateLimitRule:
    """
    Per-user rate limiting to prevent abuse.
    """

    name = "user_rate_limit"
    description = "Per-user rate limiting"
    priority = 5

    def __init__(
        self,
        max_commands_per_minute: int = 10,
        max_actions_per_hour: int = 20,
    ):
        self.max_commands_per_minute = max_commands_per_minute
        self.max_actions_per_hour = max_actions_per_hour
        self._user_history: Dict[int, List[float]] = {}

    async def evaluate(
        self,
        context: DecisionContext,
        current_decision: Decision = Decision.EXECUTE,
    ) -> tuple[Decision, str, List[str]]:
        user_id = context.data.get("user_id")
        if not user_id:
            return (Decision.EXECUTE, "No user ID to rate limit", [])

        now = time.time()
        what_would_change = []

        # Get or create user history
        if user_id not in self._user_history:
            self._user_history[user_id] = []

        history = self._user_history[user_id]

        # Clean old entries
        one_hour_ago = now - 3600
        self._user_history[user_id] = [t for t in history if t > one_hour_ago]
        history = self._user_history[user_id]

        # Check per-minute limit
        one_minute_ago = now - 60
        commands_in_minute = sum(1 for t in history if t > one_minute_ago)
        if commands_in_minute >= self.max_commands_per_minute:
            what_would_change.append(f"Wait for rate limit ({self.max_commands_per_minute}/min)")
            return (
                Decision.HOLD,
                f"User rate limit: {commands_in_minute}/{self.max_commands_per_minute} per minute",
                what_would_change,
            )

        # Record this command
        history.append(now)

        return (Decision.EXECUTE, "User rate limit OK", [])


class TelegramDecisionEngine:
    """
    Decision engine specialized for Telegram bot commands.
    """

    def __init__(self):
        self.engine = DecisionEngine(
            component="telegram_bot",
            default_confidence_threshold=0.5,
            default_cost_threshold=10.0,
            enable_logging=True,
            enable_audit=True,
        )

        # Configure rules
        self._setup_rules()

        # Track decision history
        self._hold_reasons: Dict[str, int] = {}
        self._action_confirmations_pending: Dict[str, Dict] = {}

    def _setup_rules(self):
        """Configure decision rules for Telegram bot."""
        # Circuit breaker
        self.engine.add_rule(
            CircuitBreakerRule(
                failure_threshold=10,
                recovery_timeout=300,
                half_open_max=2,
            )
        )

        # User rate limiting
        self.engine.add_rule(
            UserRateLimitRule(
                max_commands_per_minute=10,
                max_actions_per_hour=30,
            )
        )

        # Intent classification
        self.engine.add_rule(
            IntentClassificationRule(require_confirmation_for_actions=True)
        )

        # Confidence threshold
        self.engine.add_rule(
            ConfidenceThresholdRule(
                min_confidence=0.3,
                escalate_below=0.1,
            )
        )

    async def should_execute_command(
        self,
        command: str,
        user_id: int,
        is_admin: bool = False,
        confirmed: bool = False,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> DecisionResult:
        """
        Decide whether to execute a Telegram command.
        """
        risk = RiskLevel.LOW
        if command.lower() in {"buy", "sell", "trade", "swap"}:
            risk = RiskLevel.MEDIUM
        elif command.lower() in {"config", "restart", "kill", "broadcast"}:
            risk = RiskLevel.HIGH

        context = DecisionContext(
            intent=f"command_{command}",
            data={
                "command": command,
                "user_id": user_id,
                "is_admin": is_admin,
                "confirmed": confirmed,
                **(metadata or {}),
            },
            cost_estimate=0.0,  # Commands are free
            risk_level=risk,
        )

        result = await self.engine.decide(context)

        # Track hold reasons
        if result.decision == Decision.HOLD:
            for rule in result.rules_failed:
                self._hold_reasons[rule] = self._hold_reasons.get(rule, 0) + 1

        return result

    async def should_respond_to_message(
        self,
        message_text: str,
        user_id: int,
        chat_type: str = "private",
        is_reply_to_bot: bool = False,
    ) -> DecisionResult:
        """
        Decide whether to respond to a non-command message.
        """
        context = DecisionContext(
            intent="respond_message",
            data={
                "message": message_text[:500],
                "user_id": user_id,
                "chat_type": chat_type,
                "is_reply_to_bot": is_reply_to_bot,
                "confidence": 0.7 if is_reply_to_bot else 0.4,
            },
            risk_level=RiskLevel.LOW,
        )

        return await self.engine.decide(context)

    async def should_respond(
        self,
        message: str,
        user_id: str,
        chat_type: str = "group",
        is_admin: bool = False,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> DecisionResult:
        """Backwards-compatible alias for should_respond_to_message."""
        is_reply_to_bot = False
        if metadata and isinstance(metadata, dict):
            is_reply_to_bot = bool(metadata.get("is_reply_to_bot", False))
        return await self.should_respond_to_message(
            message_text=message,
            user_id=int(user_id) if str(user_id).isdigit() else 0,
            chat_type=chat_type or "group",
            is_reply_to_bot=is_reply_to_bot,
        )

    async def should_execute_trade(
        self,
        action: str,
        token: str,
        amount: float,
        user_id: int,
        confidence: float = 0.7,
    ) -> DecisionResult:
        """
        Decide whether to execute a trading action.

        This is a high-risk decision that should typically require
        confirmation unless confidence is very high.
        """
        context = DecisionContext(
            intent=f"trade_{action}",
            data={
                "action": action,
                "token": token,
                "amount": amount,
                "user_id": user_id,
                "confidence": confidence,
            },
            cost_estimate=amount * 0.01,  # Estimate 1% fee
            risk_level=RiskLevel.HIGH,
        )

        result = await self.engine.decide(context)

        # Trading actions with low confidence should escalate
        if confidence < 0.6 and result.decision == Decision.EXECUTE:
            return DecisionResult(
                decision=Decision.ESCALATE,
                confidence=confidence,
                rationale=f"Trade confidence {confidence:.0%} requires confirmation",
                intent=f"trade_{action}",
                what_would_change_my_mind=["Higher confidence score", "Explicit user confirmation"],
                component="telegram_bot",
            )

        return result

    def request_confirmation(
        self,
        action: str,
        user_id: int,
        details: Dict[str, Any],
    ) -> str:
        """
        Generate a confirmation request ID for an action.

        Returns a unique ID that can be used to confirm/cancel the action.
        """
        confirmation_id = f"{user_id}_{action}_{int(time.time())}"
        self._action_confirmations_pending[confirmation_id] = {
            "action": action,
            "user_id": user_id,
            "details": details,
            "created_at": datetime.utcnow(),
        }
        return confirmation_id

    def confirm_action(self, confirmation_id: str) -> Optional[Dict]:
        """
        Confirm a pending action and return its details.

        Returns None if confirmation ID is invalid or expired.
        """
        pending = self._action_confirmations_pending.pop(confirmation_id, None)
        if not pending:
            return None

        # Check expiration (5 minutes)
        created = pending.get("created_at", datetime.utcnow())
        if (datetime.utcnow() - created).total_seconds() > 300:
            return None

        return pending

    def cancel_action(self, confirmation_id: str) -> bool:
        """Cancel a pending action."""
        return self._action_confirmations_pending.pop(confirmation_id, None) is not None

    def get_stats(self) -> Dict[str, Any]:
        """Get decision statistics."""
        stats = self.engine.get_stats()
        stats["hold_reasons"] = dict(self._hold_reasons)
        stats["pending_confirmations"] = len(self._action_confirmations_pending)
        return stats

    def record_success(self):
        """Record a successful action."""
        for rule in self.engine.rules:
            if hasattr(rule, "record_success"):
                rule.record_success()

    def record_failure(self, error: str = ""):
        """Record a failed action."""
        for rule in self.engine.rules:
            if hasattr(rule, "record_failure"):
                rule.record_failure()


def get_tg_decision_engine() -> TelegramDecisionEngine:
    """Get or create the singleton Telegram decision engine."""
    global _tg_decision_engine
    if _tg_decision_engine is None:
        _tg_decision_engine = TelegramDecisionEngine()
    return _tg_decision_engine
