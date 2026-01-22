"""
Memory Namespaces

Defines logical namespaces for agent memory isolation.
"""
from enum import Enum


class MemoryNamespace(str, Enum):
    """Predefined memory namespaces for agents."""

    TELEGRAM = "ai.telegram"
    API = "ai.api"
    WEB = "ai.web"
    SUPERVISOR = "ai.supervisor"
    SUPERVISOR_INSIGHTS = "ai.supervisor.insights"
    SUPERVISOR_ERRORS = "ai.supervisor.errors"
    SHARED = "ai.shared"


def validate_namespace(namespace: str) -> bool:
    """Validate that a namespace follows the correct pattern."""
    # Must start with 'ai.' and contain only alphanumeric, dots, and underscores
    import re

    pattern = r"^ai\.[a-z0-9_.]+$"
    return bool(re.match(pattern, namespace))
