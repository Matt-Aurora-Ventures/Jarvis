# Trading Kill Switch Audit - 2026-01-20

## Finding
- `LIFEOS_KILL_SWITCH` was only referenced in `core/approval_gate.py` and `core/context_loader.py`.
- `bots/treasury/trading.py` did not enforce the kill switch for live trade execution.

## Change
- Added a kill switch guard at the start of `TradingEngine.open_position` so trade requests are rejected when `LIFEOS_KILL_SWITCH` is enabled.

## Notes
- This is a minimal safety gate; approval workflows still need a dedicated audit to ensure manual approval is required before live execution.
