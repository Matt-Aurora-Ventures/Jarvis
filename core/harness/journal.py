"""Append-only action journal for traceability."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable, List, Optional

from core.harness.action_schema import ActionEvent


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_JOURNAL_PATH = ROOT / "logs" / "action_journal.jsonl"


class ActionJournal:
    def __init__(self, path: Optional[Path] = None):
        self.path = path or DEFAULT_JOURNAL_PATH

    @classmethod
    def from_env(cls) -> "ActionJournal":
        from os import getenv

        value = getenv("ACTION_JOURNAL_PATH")
        return cls(Path(value) if value else DEFAULT_JOURNAL_PATH)

    def append(self, event: ActionEvent) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event.to_dict()) + "\n")

    def iter_events(
        self,
        action_id: Optional[str] = None,
        event_type: Optional[str] = None,
    ) -> Iterable[ActionEvent]:
        if not self.path.exists():
            return []
        events: List[ActionEvent] = []
        with self.path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    payload = json.loads(line)
                except json.JSONDecodeError:
                    continue
                event = ActionEvent.from_dict(payload)
                if action_id and event.action_id != action_id:
                    continue
                if event_type and event.type != event_type:
                    continue
                events.append(event)
        return events

    def latest(self, action_id: str) -> Optional[ActionEvent]:
        events = list(self.iter_events(action_id=action_id))
        return events[-1] if events else None

    def list_actions(self, status: Optional[str] = None) -> List[str]:
        actions: dict[str, str] = {}
        for event in self.iter_events():
            if event.type == "proposed":
                actions[event.action_id] = "proposed"
            elif event.type in {"approved", "rejected", "executed", "failed"}:
                actions[event.action_id] = event.type
        if status:
            return [action_id for action_id, state in actions.items() if state == status]
        return list(actions.keys())

    def summarize_recent(self, limit: int = 20) -> List[ActionEvent]:
        if not self.path.exists():
            return []
        lines = self.path.read_text(encoding="utf-8").splitlines()
        events: List[ActionEvent] = []
        for line in lines[-limit:]:
            if not line.strip():
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            events.append(ActionEvent.from_dict(payload))
        return events
