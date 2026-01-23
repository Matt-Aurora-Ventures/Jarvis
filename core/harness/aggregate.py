"""Aggregate pending actions across supervisor, approvals, and journal."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List

from core.ai_runtime.config import AIRuntimeConfig
from core.approval_gate import get_approval_gate
from core.harness.decision_gate import DecisionGate
from core.harness.journal import ActionJournal
from core.harness.validators import get_kill_switch_status


@dataclass
class UnifiedAction:
    action_id: str
    source: str
    intent: str
    scope: str
    summary: str
    status: str
    created_at: str
    raw: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "action_id": self.action_id,
            "source": self.source,
            "intent": self.intent,
            "scope": self.scope,
            "summary": self.summary,
            "status": self.status,
            "created_at": self.created_at,
            "raw": self.raw,
        }


def _supervisor_pending_path() -> Path:
    config = AIRuntimeConfig.from_env()
    return Path(config.log_path).parent / "pending_actions.json"


def read_supervisor_pending() -> List[UnifiedAction]:
    path = _supervisor_pending_path()
    if not path.exists():
        return []
    try:
        pending = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    actions: List[UnifiedAction] = []
    for item in pending:
        action_id = item.get("id", "")
        actions.append(
            UnifiedAction(
                action_id=action_id,
                source="ai_supervisor",
                intent=item.get("type", "supervisor_action"),
                scope="supervisor",
                summary=item.get("description", ""),
                status=item.get("status", "pending"),
                created_at=item.get("created_at", ""),
                raw=item,
            )
        )
    return actions


def read_trade_pending() -> List[UnifiedAction]:
    gate = get_approval_gate()
    pending = gate.get_pending()
    actions: List[UnifiedAction] = []
    for proposal in pending:
        summary = f"{proposal.side} {proposal.size} {proposal.symbol} @ {proposal.price}"
        actions.append(
            UnifiedAction(
                action_id=proposal.id,
                source="trade_gate",
                intent="trade_approval",
                scope="trading",
                summary=summary,
                status=proposal.status.value,
                created_at=str(proposal.timestamp),
                raw=proposal.to_dict(),
            )
        )
    return actions


def read_journal_pending() -> List[UnifiedAction]:
    gate = DecisionGate()
    pending = gate.list_pending()
    actions: List[UnifiedAction] = []
    for proposal in pending:
        actions.append(
            UnifiedAction(
                action_id=proposal.action_id,
                source=proposal.source,
                intent=proposal.intent,
                scope=proposal.scope,
                summary=proposal.payload.get("summary", proposal.intent),
                status=proposal.status,
                created_at=proposal.created_at,
                raw=proposal.to_dict(),
            )
        )
    return actions


def read_journal_tail(limit: int = 20) -> List[Dict[str, Any]]:
    journal = ActionJournal.from_env()
    return [event.to_dict() for event in journal.summarize_recent(limit)]


def aggregate_actions() -> Dict[str, Any]:
    supervisor = read_supervisor_pending()
    trades = read_trade_pending()
    journal = read_journal_pending()
    kill_switch, source = get_kill_switch_status()
    return {
        "kill_switch": {"active": kill_switch, "source": source},
        "pending": {
            "supervisor": [action.to_dict() for action in supervisor],
            "trading": [action.to_dict() for action in trades],
            "journal": [action.to_dict() for action in journal],
        },
        "timeline": read_journal_tail(),
    }
