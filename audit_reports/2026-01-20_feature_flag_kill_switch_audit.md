# Feature Flags & Kill Switch Audit - 2026-01-20

Legend: [DONE] enforced, [PARTIAL] present but not consistent, [MISSING] not found.

## Feature Flag Systems (Inventory)
- [PARTIAL] `core/config/feature_flags.py` (config + FF_* env overrides) used by `core/feature_manager.py`.
- [PARTIAL] `core/feature_flags.py` (legacy flags, file-based, defaults).
- [PARTIAL] `core/users/features.py` (user-tier flags, separate store).

Observation: multiple flag systems exist with overlapping purpose; usage is inconsistent across modules.

## Kill Switch Coverage
- [DONE] `core/approval_gate.py` kill switch (proposal gating).
- [DONE] `core/security/emergency_shutdown.py` persistent shutdown state.
- [DONE] `bots/treasury/trading.py` `LIFEOS_KILL_SWITCH` gate in `open_position`.
- [DONE] `bots/twitter/autonomous_engine.py` + `bots/twitter/sentiment_poster.py` `X_BOT_ENABLED` gate.
- [DONE] `bots/twitter/x_claude_cli_handler.py` `X_BOT_ENABLED` gate.
- [DONE] `core/treasury/manager.py` now blocks on kill switch + emergency shutdown + `LIVE_TRADING_ENABLED`.
- [DONE] `core/trading/batch_processor.py` now blocks on kill switch + emergency shutdown + `LIVE_TRADING_ENABLED`.
- [DONE] `core/trading/bags_adapter.py` now blocks on kill switch + emergency shutdown + `LIVE_TRADING_ENABLED`.

## Remaining Gaps (Next Pass)
- [PARTIAL] `integrations/bags` trade router paths may bypass `core/trading/bags_adapter.py` gating.
- [PARTIAL] No single unified flag system; some features still check legacy flags while others use config flags.
- [MISSING] Global feature flag enforcement in non-trading bots (Telegram/X) beyond env toggles.

## Recommendations (Prioritized)
1) Consolidate on `core/feature_manager` for system-wide flags and map legacy flag names to config flags.
2) Add kill switch checks in any trade entrypoints that bypass the adapter (e.g., direct router calls).
3) Add a single shared helper for kill switch/flag checks to reduce drift.
