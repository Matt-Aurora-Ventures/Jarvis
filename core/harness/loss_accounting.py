"""Loss accounting for summarization/compression steps."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import List

from core.harness.action_schema import ActionEvent
from core.harness.journal import ActionJournal


def _now_iso() -> str:
    return datetime.utcnow().isoformat()


@dataclass
class LossRecord:
    what_removed: List[str]
    why_ok: str
    recovery_pointer: str
    source_ids: List[str] = field(default_factory=list)
    created_at: str = field(default_factory=_now_iso)

    def to_dict(self) -> dict:
        return {
            "what_removed": self.what_removed,
            "why_ok": self.why_ok,
            "recovery_pointer": self.recovery_pointer,
            "source_ids": self.source_ids,
            "created_at": self.created_at,
        }


def record_loss(record: LossRecord, journal: ActionJournal) -> None:
    event = ActionEvent.new(
        action_id="loss_record",
        event_type="loss_recorded",
        actor="memory",
        data={"loss_record": record.to_dict()},
    )
    journal.append(event)
