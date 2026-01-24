from pathlib import Path

from core.harness.action_schema import ActionEvent
from core.harness.journal import ActionJournal


def test_action_journal_append_and_latest(tmp_path: Path) -> None:
    journal_path = tmp_path / "action_journal.jsonl"
    journal = ActionJournal(journal_path)

    event1 = ActionEvent.new("action-1", "proposed", "tester", {"proposal": {"intent": "test"}})
    event2 = ActionEvent.new("action-1", "approved", "tester", {"decision": {"decision": "approved"}})
    journal.append(event1)
    journal.append(event2)

    events = list(journal.iter_events(action_id="action-1"))
    assert len(events) == 2
    assert events[0].type == "proposed"
    assert events[1].type == "approved"

    latest = journal.latest("action-1")
    assert latest is not None
    assert latest.type == "approved"


def test_action_journal_list_actions(tmp_path: Path) -> None:
    journal = ActionJournal(tmp_path / "action_journal.jsonl")
    journal.append(ActionEvent.new("a1", "proposed", "tester", {}))
    journal.append(ActionEvent.new("a2", "proposed", "tester", {}))
    journal.append(ActionEvent.new("a2", "approved", "tester", {}))

    assert set(journal.list_actions()) == {"a1", "a2"}
    assert journal.list_actions(status="proposed") == ["a1"]
