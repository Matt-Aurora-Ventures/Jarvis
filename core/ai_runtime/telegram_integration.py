"""
Telegram Bot Integration Helpers

Provides decorators and utilities for optionally observing Telegram bot behavior.
"""
import asyncio
import logging
import time
from functools import wraps
from typing import Optional, Dict, Any, Callable

logger = logging.getLogger("jarvis.ai_runtime.telegram")


def get_telegram_agent():
    """
    Get the Telegram AI agent if available.

    Returns None if AI runtime is not running or agent is unavailable.
    """
    try:
        from .integration import get_ai_runtime_manager

        manager = get_ai_runtime_manager()
        return manager.get_telegram_agent() if manager.is_running else None
    except Exception as e:
        logger.debug(f"Failed to get Telegram agent: {e}")
        return None


def with_ai_observation(handler: Callable):
    """
    Decorator that optionally observes handler execution.

    CRITICAL: This is fire-and-forget. Handler completes normally
    regardless of AI availability or response time.

    Usage:
        @with_ai_observation
        async def handle_start(update, context):
            # Your handler code
            pass
    """

    @wraps(handler)
    async def wrapper(update, context, *args, **kwargs):
        # Run handler first (AI never blocks)
        start_time = time.time()
        result = None
        error = None

        try:
            result = await handler(update, context, *args, **kwargs)
        except Exception as e:
            error = str(e)
            raise  # Re-raise so normal error handling works

        latency_ms = (time.time() - start_time) * 1000

        # Fire-and-forget AI observation
        agent = get_telegram_agent()
        if agent:
            asyncio.create_task(
                _observe_async(agent, update, context, latency_ms, result, error)
            )

        return result

    return wrapper


async def _observe_async(
    agent,
    update,
    context,
    latency_ms: float,
    result: Any,
    error: Optional[str],
):
    """
    Async observation - errors are logged but never propagate.

    This runs in the background and will not affect the bot's operation.
    """
    try:
        # Extract safe metadata (no message content for privacy)
        event = {
            "event_type": "message" if update.message else "callback",
            "user_id": update.effective_user.id if update.effective_user else None,
            "chat_id": update.effective_chat.id if update.effective_chat else 0,
            "content": None,  # Privacy: don't store content
            "command": (
                update.message.text.split()[0]
                if update.message and update.message.text
                else None
            ),
            "latency_ms": latency_ms,
            "error": error,
            "metadata": {"had_result": result is not None},
        }

        # Hard 500ms timeout for AI observation
        await asyncio.wait_for(agent.process_component_event(event), timeout=0.5)

    except asyncio.TimeoutError:
        pass  # Expected - AI too slow
    except Exception as e:
        logger.debug(f"AI observation error: {e}")
        # AI errors never affect bot


async def suggest_response_enhancement(
    agent_or_none,
    user_query: str,
    bot_response: str,
    command: Optional[str] = None,
) -> Optional[str]:
    """
    Optionally ask AI to suggest a response enhancement.

    This is called AFTER the bot generates its normal response.
    Returns None if AI unavailable or suggests keeping original.

    Args:
        agent_or_none: Telegram agent or None
        user_query: What the user asked
        bot_response: The bot's response
        command: The command if any

    Returns:
        Enhanced response or None to use original
    """
    if not agent_or_none:
        return None

    try:
        # Hard 800ms timeout
        suggestion = await asyncio.wait_for(
            agent_or_none.suggest_response(
                {
                    "user_query": user_query,
                    "bot_response": bot_response,
                    "command": command,
                }
            ),
            timeout=0.8,
        )
        return suggestion
    except asyncio.TimeoutError:
        return None
    except Exception as e:
        logger.debug(f"Response suggestion error: {e}")
        return None
