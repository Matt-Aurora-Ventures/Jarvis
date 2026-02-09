"""Lightweight env-driven feature flags.

Keep this module dependency-free (stdlib only) so it can be imported from
anywhere without creating cycles.
"""

from __future__ import annotations

import os


def env_flag(name: str, default: bool = False) -> bool:
    """Parse a boolean-ish env var with a safe default.

    - Unset or empty: default
    - "1/true/yes/on": True
    - everything else: False
    """
    raw = os.getenv(name)
    if raw is None or raw == "":
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


def is_cooldown_mode() -> bool:
    """Master kill-switch for cost-heavy / risky behavior."""
    return env_flag("JARVIS_COOLDOWN_MODE", False)


def is_xai_enabled(*, default: bool = True) -> bool:
    """Return True if xAI/Grok calls are allowed.

    This is intentionally conservative: cooldown mode always disables xAI.
    """
    if is_cooldown_mode():
        return False
    return env_flag("XAI_ENABLED", default)

