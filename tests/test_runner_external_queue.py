from __future__ import annotations

import json
from pathlib import Path

from core.jupiter_perps.intent import OpenPosition
from core.jupiter_perps.runner import _read_external_intents


def _append_jsonl(path: Path, payload: dict) -> None:
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload) + "\n")


def test_read_external_intents_normalizes_legacy_and_tracks_cursor(tmp_path: Path) -> None:
    queue_path = tmp_path / "intent_queue.jsonl"

    _append_jsonl(
        queue_path,
        {
            "type": "OpenPosition",
            "idempotency_key": "legacy-open-1",
            "market": "SOL-USD",
            "side": "long",
            "collateral_usd": 100.0,
            "leverage": 3.0,
        },
    )
    _append_jsonl(queue_path, {"intent_type": "open_position", "idempotency_key": "bad"})

    intents, cursor, rejections = _read_external_intents(queue_path, cursor=0)

    assert len(intents) == 1
    assert isinstance(intents[0], OpenPosition)
    assert intents[0].size_usd == 300.0
    assert cursor > 0
    assert len(rejections) == 1

    intents_again, cursor_again, rejections_again = _read_external_intents(queue_path, cursor=cursor)
    assert intents_again == []
    assert rejections_again == []
    assert cursor_again == cursor

    _append_jsonl(
        queue_path,
        {
            "intent_type": "open_position",
            "idempotency_key": "canonical-open-2",
            "market": "SOL-USD",
            "side": "short",
            "collateral_mint": "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
            "collateral_amount_usd": 50.0,
            "leverage": 2.0,
            "size_usd": 100.0,
        },
    )
    intents_after_append, final_cursor, final_rejections = _read_external_intents(
        queue_path, cursor=cursor_again,
    )
    assert len(intents_after_append) == 1
    assert final_rejections == []
    assert final_cursor > cursor_again
