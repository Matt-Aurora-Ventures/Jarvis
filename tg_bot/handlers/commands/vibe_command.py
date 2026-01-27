"""
/vibe command - Resilient AI chat using provider fallback chain

Uses the resilient provider system to ensure responses ALWAYS work,
even when primary APIs are down.

Examples:
    /vibe What's the market sentiment for BTC?
    /vibe Write a Python function to calculate RSI
    /vibe Explain how stop losses work
"""

import logging
from telegram import Update
from telegram.ext import ContextTypes

from core.resilient_provider import get_resilient_provider, initialize_providers
from tg_bot.middleware.resilient_errors import safe_reply

logger = logging.getLogger(__name__)

# Initialize providers on module load
_providers_initialized = False


async def _ensure_providers_initialized():
    """Ensure providers are initialized (idempotent)."""
    global _providers_initialized
    if not _providers_initialized:
        try:
            await initialize_providers()
            _providers_initialized = True
            logger.info("✅ Resilient providers initialized")
        except Exception as e:
            logger.error(f"Failed to initialize providers: {e}")


async def vibe_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    AI chat using resilient provider chain.

    Always returns a response, even if all cloud providers are down.
    Falls back through: XAI → Groq → OpenRouter → Ollama → Dexter

    Usage:
        /vibe <your question or request>

    Examples:
        /vibe What's BTC doing?
        /vibe Write a factorial function
        /vibe Explain circuit breakers
    """
    await _ensure_providers_initialized()

    # Get the prompt from command arguments
    if not context.args:
        help_text = (
            "🤖 **Vibe Command - Resilient AI Chat**\n\n"
            "Ask me anything! I'll use the best available AI provider.\n\n"
            "**Usage:**\n"
            "`/vibe <your question>`\n\n"
            "**Examples:**\n"
            "• `/vibe What's the market sentiment?`\n"
            "• `/vibe Write a Python sorting function`\n"
            "• `/vibe Explain how DeFi works`\n\n"
            "I automatically fallback between providers to ensure I always respond."
        )
        await safe_reply(update.effective_message, help_text, parse_mode="Markdown")
        return

    prompt = " ".join(context.args)

    # Send "thinking" message
    thinking_msg = await safe_reply(update.effective_message, "🤔 Thinking...", parse_mode=None)

    try:
        provider = get_resilient_provider()

        # Determine capability based on keywords
        capability = "chat"  # default
        if any(keyword in prompt.lower() for keyword in ["sentiment", "market", "price", "btc", "eth", "solana"]):
            capability = "sentiment"
        elif any(keyword in prompt.lower() for keyword in ["code", "function", "python", "javascript", "program"]):
            capability = "code"
        elif any(keyword in prompt.lower() for keyword in ["how", "what", "why", "explain", "research"]):
            capability = "knowledge"

        # Call resilient provider (ALWAYS returns a response)
        result = await provider.call(
            prompt=prompt,
            required_capability=capability,
            timeout=60.0
        )

        # Build response
        response_lines = []

        if result.degraded and result.fallback_count > 0:
            response_lines.append(f"⚠️ *Running in fallback mode* (primary provider unavailable)\n")

        if result.provider_used:
            response_lines.append(f"🤖 *Provider:* {result.provider_used.upper()}")
            response_lines.append(f"⏱️ *Latency:* {result.latency_ms:.0f}ms\n")

        response_lines.append(result.response)

        if not result.success:
            response_lines.append(f"\n_Note: Using fallback response due to provider issues_")

        response_text = "\n".join(response_lines)

        # Edit the thinking message with the result
        try:
            await thinking_msg.edit_text(response_text, parse_mode="Markdown")
        except Exception:
            # If edit fails, send a new message
            await safe_reply(update.effective_message, response_text, parse_mode="Markdown")

    except Exception as e:
        logger.error(f"Error in vibe_command: {e}")

        # CRITICAL: Even if there's an exception, provide a fallback response
        fallback_text = (
            "⚠️ I'm temporarily experiencing issues.\n\n"
            "This usually resolves quickly. Please try again in a moment, "
            "or use /status to check provider health."
        )

        try:
            await thinking_msg.edit_text(fallback_text, parse_mode=None)
        except Exception:
            await safe_reply(update.effective_message, fallback_text, parse_mode=None)
