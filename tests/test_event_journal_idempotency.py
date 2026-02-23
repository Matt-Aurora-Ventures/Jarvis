from __future__ import annotations

import pytest

from core.jupiter_perps.event_journal import EventJournal
from core.jupiter_perps.intent import Noop


@pytest.mark.asyncio
async def test_log_intent_returns_false_for_duplicate_key(tmp_path) -> None:
    sqlite_path = tmp_path / "events.sqlite3"
    journal = EventJournal(dsn="", sqlite_path=str(sqlite_path))
    await journal.connect()
    if not journal.has_local:
        pytest.skip("aiosqlite is not installed in this test environment")

    intent = Noop(idempotency_key="dedupe-key")
    first = await journal.log_intent(intent)
    second = await journal.log_intent(intent)

    assert first is True
    assert second is False

    await journal.close()
