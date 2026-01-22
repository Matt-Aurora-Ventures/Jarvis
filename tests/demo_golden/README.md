# Demo Golden Snapshots

These tests lock in the **canonical demo behavior**. They run the demo/telegram handlers with mocked dependencies and compare outputs against golden files in `tests/demo_golden/golden/`.

## Contract
- **Do not change output text or buttons** without updating golden files.
- Demo output is the source of truth; production behavior should match it.
- Snapshots normalize timestamps/IDs to avoid flaky diffs.

## Regenerating Golden Files (manual)
1. Run:
   - `set UPDATE_GOLDEN=1`
   - `python -m pytest tests/demo_golden/test_demo_golden.py -q`
2. Review diffs in `tests/demo_golden/golden/`
3. Unset the flag:
   - `set UPDATE_GOLDEN=`

## What’s Covered
- Command outputs: `/start`, `/help`, `/dashboard`, `/positions`, `/report`
- Trading callbacks: `trade_*`, `sell_pos:*`
- Demo flows: `/demo`, `demo:positions`, `demo:buy:*`, `demo:sell_all`, `demo:sell:*`, `demo:refresh`
