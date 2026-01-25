"""
Usage Tracking Configuration.

Defines default quotas per tier and model pricing for cost estimation.
"""

from typing import Dict

# Default quotas by user tier (tokens per period)
# -1 means unlimited
DEFAULT_QUOTAS: Dict[str, Dict[str, int]] = {
    "free_tier": {
        "hour": 50_000,      # 50k tokens/hour
        "day": 1_000_000,    # 1M tokens/day
        "month": 10_000_000  # 10M tokens/month
    },
    "premium": {
        "hour": 200_000,     # 200k tokens/hour
        "day": 5_000_000,    # 5M tokens/day
        "month": 50_000_000  # 50M tokens/month
    },
    "admin": {
        "hour": -1,   # unlimited
        "day": -1,    # unlimited
        "month": -1   # unlimited
    }
}

# Model pricing in USD per 1M tokens
# Format: {"input": price_per_1M_input, "output": price_per_1M_output}
MODEL_PRICING: Dict[str, Dict[str, float]] = {
    # Grok models (xAI)
    "grok-3-mini": {
        "input": 0.30,   # $0.30 per 1M input tokens
        "output": 0.50,  # $0.50 per 1M output tokens
    },
    "grok-3": {
        "input": 3.00,
        "output": 15.00,
    },
    "grok-4": {
        "input": 5.00,
        "output": 25.00,
    },
    # Claude models (Anthropic)
    "claude-sonnet-4-20250514": {
        "input": 3.00,
        "output": 15.00,
    },
    "claude-3-5-sonnet-20241022": {
        "input": 3.00,
        "output": 15.00,
    },
    "claude-3-haiku-20240307": {
        "input": 0.25,
        "output": 1.25,
    },
    "claude-3-opus-20240229": {
        "input": 15.00,
        "output": 75.00,
    },
    # OpenAI models (if used)
    "gpt-4o": {
        "input": 2.50,
        "output": 10.00,
    },
    "gpt-4o-mini": {
        "input": 0.15,
        "output": 0.60,
    },
    # Default pricing for unknown models
    "default": {
        "input": 1.00,
        "output": 3.00,
    },
}

# Alert thresholds (percentage of quota used)
ALERT_THRESHOLDS = {
    "warning": 80,   # Warn at 80% usage
    "critical": 90,  # Critical alert at 90% usage
    "blocked": 100,  # Block at 100% usage
}

# Daily cost limit (USD) - can be overridden per user
DEFAULT_DAILY_COST_LIMIT = 10.00
