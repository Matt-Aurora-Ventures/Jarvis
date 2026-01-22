"""
Telegram Bot Agent

Observes Telegram bot interactions and suggests improvements.
NEVER blocks message handling - all AI calls are fire-and-forget or optional.
"""
import logging
from typing import Optional, Dict, Any
from dataclasses import dataclass

from .base import BaseAgent
from ..security.injection_defense import TaggedInput, InputSource

logger = logging.getLogger(__name__)


@dataclass
class TelegramEvent:
    """Structured Telegram event for observation."""

    event_type: str  # "message", "command", "callback", "error"
    user_id: Optional[int]
    chat_id: int
    content: Optional[str]
    command: Optional[str]
    latency_ms: Optional[float]
    error: Optional[str]
    metadata: Dict[str, Any]


class TelegramAgent(BaseAgent):
    """
    AI agent for the Telegram bot component.

    Responsibilities:
    - Observe user interactions (not content, just patterns)
    - Detect error patterns and UX friction
    - Suggest command improvements
    - Track response latencies

    Privacy: Does NOT store user message content, only metadata and patterns.
    """

    async def process_component_event(
        self, event: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        Process a Telegram event.

        Called by the Telegram bot handler AFTER normal processing.
        This is non-blocking - bot continues regardless of result.
        """
        try:
            tg_event = TelegramEvent(**event)
        except Exception as e:
            logger.debug(f"Invalid event format: {e}")
            return None

        # Privacy: Create sanitized observation (no message content)
        observation = TaggedInput(
            content=f"""
Telegram Event:
- Type: {tg_event.event_type}
- Command: {tg_event.command or 'N/A'}
- Latency: {tg_event.latency_ms or 'N/A'}ms
- Error: {tg_event.error or 'None'}
- Metadata: {tg_event.metadata}
""",
            source=InputSource.LOG,
            component="telegram_bot",
            timestamp=__import__("time").time(),
        )

        insight = await self.observe(observation)

        if insight and insight.get("has_insight"):
            # Send to supervisor for correlation
            await self.send_to_supervisor(
                {
                    "agent": self.name,
                    "event_type": tg_event.event_type,
                    "insight": insight,
                }
            )

        return insight

    async def suggest_response(self, context: Dict[str, Any]) -> Optional[str]:
        """
        Optionally suggest a response enhancement.

        This is called AFTER the bot generates its normal response.
        The suggestion is merged only if appropriate.

        Args:
            context: Contains 'user_query', 'bot_response', 'command'

        Returns:
            Enhanced response or None to use original
        """
        if not self.capabilities.can_suggest:
            return None

        # Don't enhance sensitive commands
        if context.get("command") in ["balance", "wallet", "transfer"]:
            return None

        suggestion = await self.suggest(
            f"""
The user asked: {context.get('user_query', 'N/A')}
The bot responded: {context.get('bot_response', 'N/A')}

If the response could be clearer or more helpful, suggest an improvement.
If it's already good, respond with just "KEEP_ORIGINAL".
"""
        )

        if suggestion and "KEEP_ORIGINAL" not in suggestion:
            return suggestion
        return None
