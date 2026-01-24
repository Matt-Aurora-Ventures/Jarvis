"""Compression helpers with loss accounting hooks."""

from __future__ import annotations

from typing import List, Tuple

from core.harness.journal import ActionJournal
from core.harness.loss_accounting import LossRecord, record_loss


def compress_events(events: List[str], journal: ActionJournal | None = None) -> Tuple[str, LossRecord]:
    """Return a simple summary and record what was removed."""
    summary = "\n".join(events[:5])
    removed = events[5:]
    record = LossRecord(
        what_removed=removed,
        why_ok="Older events summarized for brevity; originals remain retrievable.",
        recovery_pointer="memory_store",
        source_ids=[],
    )
    if journal:
        record_loss(record, journal)
    return summary, record
