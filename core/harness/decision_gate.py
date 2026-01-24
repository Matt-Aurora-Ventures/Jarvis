"""Proposal/approval decision gate backed by the action journal."""

from __future__ import annotations

from typing import List, Optional

from core.harness.action_schema import ActionDecision, ActionEvent, ActionProposal
from core.harness.journal import ActionJournal
from core.harness.validators import (
    ValidationResult,
    validate_budget,
    validate_kill_switch,
    validate_proposal_schema,
)


class DecisionGate:
    def __init__(self, journal: Optional[ActionJournal] = None):
        self.journal = journal or ActionJournal.from_env()

    def _ensure_ok(self, results: List[ValidationResult]) -> None:
        issues = [issue for result in results for issue in result.issues]
        if issues:
            raise ValueError("; ".join(issues))

    def propose(self, proposal: ActionProposal) -> str:
        self._ensure_ok(
            [
                validate_proposal_schema(proposal),
                validate_budget(proposal),
            ]
        )
        event = ActionEvent.new(
            action_id=proposal.action_id,
            event_type="proposed",
            actor=proposal.source,
            data={"proposal": proposal.to_dict()},
        )
        self.journal.append(event)
        return proposal.action_id

    def approve(self, action_id: str, actor: str, note: str = "") -> bool:
        if not validate_kill_switch().ok:
            return False
        decision = ActionDecision(action_id=action_id, decided_by=actor, decision="approved", note=note)
        event = ActionEvent.new(
            action_id=action_id,
            event_type="approved",
            actor=actor,
            data={"decision": decision.to_dict()},
        )
        self.journal.append(event)
        return True

    def reject(self, action_id: str, actor: str, reason: str = "") -> bool:
        decision = ActionDecision(action_id=action_id, decided_by=actor, decision="rejected", reason=reason)
        event = ActionEvent.new(
            action_id=action_id,
            event_type="rejected",
            actor=actor,
            data={"decision": decision.to_dict()},
        )
        self.journal.append(event)
        return True

    def list_pending(self) -> List[ActionProposal]:
        events = list(self.journal.iter_events())
        proposals: dict[str, ActionProposal] = {}
        statuses: dict[str, str] = {}
        for event in events:
            if event.type == "proposed":
                proposal_data = event.data.get("proposal", {})
                proposal = ActionProposal.from_dict(proposal_data)
                proposals[proposal.action_id] = proposal
                statuses[proposal.action_id] = "proposed"
            elif event.type in {"approved", "rejected", "executed", "failed"}:
                statuses[event.action_id] = event.type
        pending: List[ActionProposal] = []
        for action_id, proposal in proposals.items():
            status = statuses.get(action_id, proposal.status)
            if status == "proposed":
                pending.append(proposal)
        return pending
