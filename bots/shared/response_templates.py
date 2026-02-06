"""
Response Templates for ClawdBots.

Shared message templates for consistent bot responses.
Supports variable interpolation and per-bot personality overrides.
"""

import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


# Default templates shared across all bots
TEMPLATES: Dict[str, str] = {
    # System
    "error": "Something went wrong: {error}\nTry again or contact the founder.",
    "unauthorized": "You don't have permission for that. Required level: {level}",
    "rate_limited": "Slow down. Try again in {seconds}s.",
    "maintenance": "System maintenance in progress. Back shortly.",

    # Health
    "health_ok": "All systems operational.\nUptime: {uptime}\nBots: {bot_count} active",
    "health_degraded": "Degraded performance detected.\n{details}",
    "health_down": "ALERT: {service} is down.\nLast seen: {last_seen}",

    # Trading
    "buy_confirm": "BUY {token}\nAmount: {amount} SOL\nTP: {tp}% | SL: {sl}%\nTx: {tx_hash}",
    "sell_confirm": "SOLD {pct}% of {token}\nP&L: {pnl}\nTx: {tx_hash}",
    "position_summary": "{token} | Entry: {entry} | Current: {current} | P&L: {pnl}%",

    # Kaizen
    "kaizen_report": "KAIZEN REPORT ({period})\nErrors: {errors}\nAvg Response: {avg_response}ms\nInsights: {insight_count}\n\n{top_insight}",

    # Handoff
    "handoff_sent": "Task routed to {target_bot}: {task_summary}",
    "handoff_received": "New task from {source_bot}: {task_summary}",

    # Morning brief
    "morning_brief_header": "MORNING BRIEF - {date}\n{'='*30}",

    # Generic
    "success": "Done. {details}",
    "not_found": "Nothing found for: {query}",
    "help": "Available commands:\n{command_list}",
}

# Per-bot personality wrappers
BOT_STYLES: Dict[str, Dict[str, str]] = {
    "matt": {
        "prefix": "",
        "error_tone": "Let me look into that. ",
        "success_tone": "All good. ",
    },
    "friday": {
        "prefix": "",
        "error_tone": "Hmm, hit a snag. ",
        "success_tone": "Nailed it. ",
    },
    "jarvis": {
        "prefix": "",
        "error_tone": "Error detected. ",
        "success_tone": "Executed. ",
    },
}


def render(template_name: str, bot_name: Optional[str] = None, **kwargs: Any) -> str:
    """Render a template with variables. Applies bot personality if specified."""
    tmpl = TEMPLATES.get(template_name)
    if not tmpl:
        logger.warning(f"Template not found: {template_name}")
        return f"[{template_name}] {kwargs}"

    try:
        text = tmpl.format(**kwargs)
    except KeyError as e:
        logger.warning(f"Missing template var {e} in {template_name}")
        text = tmpl  # Return raw template rather than crash

    # Apply bot personality prefix
    if bot_name and bot_name in BOT_STYLES:
        style = BOT_STYLES[bot_name]
        if "error" in template_name:
            text = style.get("error_tone", "") + text
        elif "success" in template_name or "confirm" in template_name:
            text = style.get("success_tone", "") + text
        prefix = style.get("prefix", "")
        if prefix:
            text = prefix + text

    return text


def add_template(name: str, template: str):
    """Register a custom template at runtime."""
    TEMPLATES[name] = template


def list_templates() -> list:
    """List all available template names."""
    return sorted(TEMPLATES.keys())
