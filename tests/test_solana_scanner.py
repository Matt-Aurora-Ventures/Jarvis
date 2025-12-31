import core.solana_scanner as solana_scanner


def test_shortlist_ids_are_ordered():
    shortlist = solana_scanner.compile_strategy_shortlist()
    assert len(shortlist) >= 5
    ids = [item["id"] for item in shortlist]
    assert ids[0] == "sol_meme_trend_sma"
    assert "new_listing_sniper" in ids
    assert "whale_copy_trade" in ids


def test_dedupe_keeps_first():
    rows = [
        {"address": "A", "value": 1},
        {"address": "A", "value": 2},
        {"address": "B", "value": 3},
    ]
    deduped = solana_scanner._dedupe(rows, "address")
    assert len(deduped) == 2
    assert deduped[0]["value"] == 1


def test_max_int_handles_mixed_values():
    rows = [
        {"listingTime": "100"},
        {"listingTime": 150},
        {"listingTime": "bad"},
    ]
    assert solana_scanner._max_int(rows, "listingTime") == 150
