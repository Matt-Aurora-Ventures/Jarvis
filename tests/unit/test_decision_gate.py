from pathlib import Path

import pytest

from core.harness.action_schema import ActionProposal
from core.harness.decision_gate import DecisionGate
from core.harness.journal import ActionJournal


def test_decision_gate_pending_flow(tmp_path: Path) -> None:
    journal = ActionJournal(tmp_path / "action_journal.jsonl")
    gate = DecisionGate(journal)
    proposal = ActionProposal.new(
        source="tester",
        intent="do_thing",
        scope="general",
        payload={"summary": "Do the thing"},
    )
    gate.propose(proposal)

    pending = gate.list_pending()
    assert len(pending) == 1
    assert pending[0].action_id == proposal.action_id

    assert gate.approve(proposal.action_id, actor="tester")
    assert gate.list_pending() == []


def test_decision_gate_blocks_missing_budget_for_risky_scope(tmp_path: Path) -> None:
    journal = ActionJournal(tmp_path / "action_journal.jsonl")
    gate = DecisionGate(journal)
    proposal = ActionProposal.new(
        source="tester",
        intent="trade",
        scope="trading",
        payload={"summary": "Trade action"},
    )
    with pytest.raises(ValueError):
        gate.propose(proposal)
