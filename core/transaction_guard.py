"""Transaction guardrails for institutional hardening."""

from __future__ import annotations

import os
from typing import Optional, Tuple

from core import config

POLY_GNOSIS_SAFE_ID = 2
POLY_GNOSIS_SAFE_ENV = "POLY_GNOSIS_SAFE"


def _resolve_poly_gnosis_safe_id() -> Optional[int]:
    env_value = os.getenv(POLY_GNOSIS_SAFE_ENV)
    if env_value:
        try:
            return int(env_value)
        except ValueError:
            return None

    cfg = config.load_config()
    safe_cfg = cfg.get("gnosis_safe", {}) if isinstance(cfg, dict) else {}
    safe_id = safe_cfg.get("polygon_safe_id")
    if safe_id is None:
        return None
    try:
        return int(safe_id)
    except (TypeError, ValueError):
        return None


def require_poly_gnosis_safe(action: str) -> Tuple[bool, Optional[str]]:
    safe_id = _resolve_poly_gnosis_safe_id()
    if safe_id is None:
        return False, f"gnosis_safe_missing: {POLY_GNOSIS_SAFE_ENV} not set or config missing for {action}"
    if safe_id != POLY_GNOSIS_SAFE_ID:
        return False, f"gnosis_safe_mismatch: expected {POLY_GNOSIS_SAFE_ID}, got {safe_id} for {action}"
    return True, None
