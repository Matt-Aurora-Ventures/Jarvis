# Jupiter Perps Migration Note

- Legacy monolith module moved to `core/legacy/jupiter_perps_legacy.py`.
- Canonical execution path is now `core/jupiter_perps/*`.
- Canonical runtime entrypoint is:

```bash
python -m core.jupiter_perps.runner --dry-run
```

If any legacy code imports `core.jupiter_perps` expecting the old monolith symbols, update those imports to explicit legacy path or migrate to package modules.

## AnchorPy Bindings

The canonical client bindings are generated from local IDL:

```bash
python scripts/generate_anchorpy_bindings.py
```

This updates `core/jupiter_perps/client/{instructions,accounts,types,program_id.py}`.

## Live Builder Notes

- Live transaction build path is Python-only and uses local AnchorPy generated instructions.
- Market custody mint mapping defaults to:
  - `SOL-USD` -> SOL custody mint
  - `BTC-USD` -> BTC custody mint
  - `ETH-USD` -> ETH custody mint
- Override/add markets with `PERPS_MARKET_CUSTODY_MINTS_JSON` (JSON object of `market -> mint`).
