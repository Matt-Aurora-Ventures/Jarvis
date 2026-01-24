"""Validation helpers for proposals and approvals."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
import json
import os
from pathlib import Path
from typing import List, Optional, Tuple

from core.harness.action_schema import ActionProposal


ROOT = Path(__file__).resolve().parents[2]
KILL_SWITCH_ENV_VARS = ("LIFEOS_KILL_SWITCH", "KILL_SWITCH", "JARVIS_KILL_SWITCH")
KILL_SWITCH_FILE = ROOT / "logs" / "kill_switch.json"
RISKY_SCOPES = {"trading", "self-upgrade"}


@dataclass
class ValidationResult:
    ok: bool
    issues: List[str] = field(default_factory=list)


def _env_kill_switch_active() -> Tuple[bool, Optional[str]]:
    for key in KILL_SWITCH_ENV_VARS:
        value = os.getenv(key)
        if value and str(value).strip().lower() in {"1", "true", "yes", "on"}:
            return True, key
    return False, None


def _file_kill_switch_active() -> Tuple[bool, Optional[str]]:
    if not KILL_SWITCH_FILE.exists():
        return False, None
    try:
        payload = json.loads(KILL_SWITCH_FILE.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return False, None
    if bool(payload.get("enabled")):
        return True, str(KILL_SWITCH_FILE)
    return False, None


def get_kill_switch_status() -> Tuple[bool, Optional[str]]:
    active, source = _env_kill_switch_active()
    if active:
        return active, source
    return _file_kill_switch_active()


def set_kill_switch_status(enabled: bool) -> None:
    KILL_SWITCH_FILE.parent.mkdir(parents=True, exist_ok=True)
    payload = {"enabled": bool(enabled), "updated_at": datetime.utcnow().isoformat()}
    KILL_SWITCH_FILE.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def validate_kill_switch() -> ValidationResult:
    active, source = get_kill_switch_status()
    if active:
        return ValidationResult(False, [f"Kill switch active ({source})"])
    return ValidationResult(True, [])


def validate_proposal_schema(proposal: ActionProposal) -> ValidationResult:
    issues: List[str] = []
    if not proposal.action_id:
        issues.append("action_id missing")
    if not proposal.source:
        issues.append("source missing")
    if not proposal.intent:
        issues.append("intent missing")
    if not proposal.scope:
        issues.append("scope missing")
    if proposal.payload is None:
        issues.append("payload missing")
    return ValidationResult(len(issues) == 0, issues)


def validate_budget(proposal: ActionProposal) -> ValidationResult:
    issues: List[str] = []
    if proposal.scope in RISKY_SCOPES and proposal.budget is None:
        issues.append(f"budget required for scope '{proposal.scope}'")
        return ValidationResult(False, issues)
    if proposal.budget:
        if proposal.budget.timeout_s <= 0:
            issues.append("budget.timeout_s must be > 0")
        if proposal.budget.max_steps <= 0:
            issues.append("budget.max_steps must be > 0")
        if proposal.budget.max_cost_usd < 0:
            issues.append("budget.max_cost_usd must be >= 0")
    return ValidationResult(len(issues) == 0, issues)
