"""Structured logging utilities for Telegram bot.

Provides centralized structured JSON logging for all bot events:
- SPAM_DECISION: Spam detection decisions with reputation context
- AI_ROUTING: AI provider routing with fallback tier info
- MESSAGE_FLOW: Message routing decisions
- VIBE_REQUEST: Vibe coding execution details
- TERMINAL_CMD: Terminal command execution
"""

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class StructuredLogger:
    """Structured logger for bot events with JSON formatting.

    All methods are static - no instance state needed.
    Log format: EVENT_TYPE: {JSON payload with timestamp}

    Usage:
        StructuredLogger.log_spam_decision("ban", user_id, ...)
        StructuredLogger.log_ai_routing("dexter", user_id, ...)
    """

    @staticmethod
    def log_event(
        event_type: str,
        action: str,
        context: Dict[str, Any],
        level: str = "info"
    ) -> None:
        """
        Log a structured event in JSON format.

        Args:
            event_type: Type of event (SPAM_DECISION, AI_ROUTING, MESSAGE_FLOW, etc.)
            action: Action taken (allow, ban, route_to_ai, execute_command, etc.)
            context: Dictionary of contextual information
            level: Log level (info, warning, error, debug)
        """
        log_entry = {
            "event": event_type,
            "action": action,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            **context
        }

        log_message = f"{event_type}: {json.dumps(log_entry)}"

        log_func = getattr(logger, level.lower(), logger.info)
        log_func(log_message)

    @staticmethod
    def log_spam_decision(
        action: str,
        user_id: int,
        username: str,
        confidence: float,
        reason: str,
        message_preview: str,
        reputation: Optional[Dict] = None
    ) -> None:
        """Log spam detection decision with reputation context.

        Args:
            action: Action taken - "allow", "warn", "mute", "ban", "delete"
            user_id: Telegram user ID
            username: Telegram username
            confidence: Spam confidence score (0.0 - 1.0)
            reason: Reason for the decision
            message_preview: First 50 chars of message
            reputation: Optional user reputation dict with is_trusted, clean_messages, reputation_score
        """
        context = {
            "action": action,
            "user_id": user_id,
            "username": username,
            "confidence": round(confidence, 3),
            "reason": reason,
            "message_preview": message_preview[:50] if message_preview else ""
        }

        if reputation:
            context["reputation"] = {
                "is_trusted": reputation.get("is_trusted", False),
                "clean_messages": reputation.get("clean_messages", 0),
                "score": reputation.get("reputation_score", 0)
            }

        # Use warning level for non-allow actions
        level = "info" if action == "allow" else "warning"
        StructuredLogger.log_event("SPAM_DECISION", action, context, level=level)

    @staticmethod
    def log_ai_routing(
        provider: str,
        user_id: int,
        message_preview: str,
        success: bool,
        fallback_tier: Optional[int] = None
    ) -> None:
        """Log AI routing decision (Dexter, Grok, fallback).

        Args:
            provider: AI provider name - "dexter", "grok", "simple_fallback"
            user_id: Telegram user ID
            message_preview: First 50 chars of message
            success: Whether the AI call succeeded
            fallback_tier: Optional tier number (1=Dexter, 2=Grok, 3=Simple)
        """
        context = {
            "provider": provider,
            "user_id": user_id,
            "message_preview": message_preview[:50] if message_preview else "",
            "success": success
        }

        if fallback_tier is not None:
            context["fallback_tier"] = fallback_tier

        StructuredLogger.log_event("AI_ROUTING", f"route_to_{provider}", context)

    @staticmethod
    def log_vibe_request(
        user_id: int,
        username: str,
        prompt_preview: str,
        success: bool,
        tokens_used: int,
        duration_sec: float,
        sanitized: bool
    ) -> None:
        """Log vibe coding request execution.

        Args:
            user_id: Telegram user ID
            username: Telegram username
            prompt_preview: First 100 chars of prompt
            success: Whether execution succeeded
            tokens_used: Number of tokens used
            duration_sec: Execution duration in seconds
            sanitized: Whether output was sanitized
        """
        context = {
            "user_id": user_id,
            "username": username,
            "prompt_preview": prompt_preview[:100] if prompt_preview else "",
            "success": success,
            "tokens_used": tokens_used,
            "duration_sec": round(duration_sec, 2),
            "sanitized": sanitized
        }

        StructuredLogger.log_event("VIBE_REQUEST", "execute", context)

    @staticmethod
    def log_terminal_command(
        user_id: int,
        username: str,
        command_preview: str,
        success: bool,
        is_admin: bool
    ) -> None:
        """Log terminal command execution.

        Args:
            user_id: Telegram user ID
            username: Telegram username
            command_preview: First 100 chars of command
            success: Whether execution succeeded
            is_admin: Whether user is admin
        """
        context = {
            "user_id": user_id,
            "username": username,
            "command_preview": command_preview[:100] if command_preview else "",
            "success": success,
            "is_admin": is_admin
        }

        level = "info" if success else "warning"
        StructuredLogger.log_event("TERMINAL_CMD", "execute", context, level=level)

    @staticmethod
    def log_message_flow(
        user_id: int,
        message_preview: str,
        route: str,
        is_admin: bool,
        should_reply: bool
    ) -> None:
        """Log message routing flow decision.

        Args:
            user_id: Telegram user ID
            message_preview: First 50 chars of message
            route: Route taken - "spam_blocked", "terminal", "vibe_coding", "ai_response", "ignored"
            is_admin: Whether user is admin
            should_reply: Whether bot should reply
        """
        context = {
            "user_id": user_id,
            "message_preview": message_preview[:50] if message_preview else "",
            "route": route,
            "is_admin": is_admin,
            "should_reply": should_reply
        }

        StructuredLogger.log_event("MESSAGE_FLOW", f"route_{route}", context, level="debug")
