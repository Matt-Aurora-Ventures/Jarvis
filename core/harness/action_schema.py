"""Schema objects for action proposals, decisions, and journal events."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Optional
import uuid

from core.harness.budgets import Budget, budget_from_payload


def _now_iso() -> str:
    return datetime.utcnow().isoformat()


@dataclass
class ActionProposal:
    action_id: str
    source: str
    intent: str
    scope: str
    payload: Dict[str, Any]
    created_at: str = field(default_factory=_now_iso)
    status: str = "proposed"
    budget: Optional[Budget] = None

    @classmethod
    def new(
        cls,
        source: str,
        intent: str,
        scope: str,
        payload: Dict[str, Any],
        budget: Optional[Budget] = None,
    ) -> "ActionProposal":
        return cls(
            action_id=str(uuid.uuid4()),
            source=source,
            intent=intent,
            scope=scope,
            payload=payload,
            budget=budget,
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "action_id": self.action_id,
            "source": self.source,
            "intent": self.intent,
            "scope": self.scope,
            "payload": self.payload,
            "created_at": self.created_at,
            "status": self.status,
            "budget": self.budget.to_dict() if self.budget else None,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ActionProposal":
        return cls(
            action_id=data.get("action_id") or data.get("id") or str(uuid.uuid4()),
            source=data.get("source", ""),
            intent=data.get("intent", ""),
            scope=data.get("scope", ""),
            payload=data.get("payload", {}) or {},
            created_at=data.get("created_at", _now_iso()),
            status=data.get("status", "proposed"),
            budget=budget_from_payload(data.get("budget")),
        )


@dataclass
class ActionDecision:
    action_id: str
    decided_by: str
    decision: str
    decided_at: str = field(default_factory=_now_iso)
    note: Optional[str] = None
    reason: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "action_id": self.action_id,
            "decided_by": self.decided_by,
            "decision": self.decision,
            "decided_at": self.decided_at,
            "note": self.note,
            "reason": self.reason,
        }


@dataclass
class ActionEvent:
    event_id: str
    action_id: str
    type: str
    actor: str
    timestamp: str = field(default_factory=_now_iso)
    data: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def new(cls, action_id: str, event_type: str, actor: str, data: Dict[str, Any]) -> "ActionEvent":
        return cls(
            event_id=str(uuid.uuid4()),
            action_id=action_id,
            type=event_type,
            actor=actor,
            data=data,
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "action_id": self.action_id,
            "type": self.type,
            "actor": self.actor,
            "timestamp": self.timestamp,
            "data": self.data,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ActionEvent":
        return cls(
            event_id=data.get("event_id", str(uuid.uuid4())),
            action_id=data.get("action_id", ""),
            type=data.get("type", ""),
            actor=data.get("actor", ""),
            timestamp=data.get("timestamp", _now_iso()),
            data=data.get("data", {}) or {},
        )
