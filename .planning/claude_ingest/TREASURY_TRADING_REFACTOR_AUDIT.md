# Treasury Trading Refactor Parity Audit

Date: 2026-01-26
Scope:
- Compare `bots/treasury/trading_legacy.py` to `bots/treasury/trading/` modules.
- Validate module layout vs target.
- Identify missing functions/behaviors and call-site updates.

## Executive Summary
- Class/method parity is largely preserved. TradingEngine now delegates to TradingOperationsMixin + PositionManager.
- 1 compatibility break found: `core/tools/trading_contracts.py` imports `TreasuryEngine` and accesses `TreasuryEngine.BLOCKED_*` class attrs that no longer exist.
- Legacy private state helpers moved to PositionManager (not exposed on TradingEngine), but no external call sites found.

## Parity Findings
### Classes and methods
- TradeDirection, TradeStatus, RiskLevel: preserved.
- Position: preserved (5 methods). Legacy TP/SL remediation and peak_price behavior preserved.
- TradeReport: preserved (to_telegram_message).
- _SimpleWallet: preserved (6 methods).
- TreasuryTrader: preserved; plus new `get_tp_sl_levels` helper.
- TradingEngine:
  - open/close/update/monitor/reconcile methods preserved via TradingOperationsMixin.
  - Legacy state helpers `_configure_state_paths`, `_load_from_secondary`, `_load_history_from_legacy` moved to PositionManager (no call sites found).

### Top-level functions
- `_log_trading_error`, `_log_trading_event`, `_log_position_change` moved into `bots/treasury/trading/logging_utils.py`.

## Compatibility Checks
- `core/tools/trading_contracts.py` uses `RiskChecker.is_blocked_token(...)` and `RiskChecker.is_high_risk_token(...)`.
- No `TreasuryEngine` references remain.
- Backward-compat alias added: `TreasuryEngine = TradingEngine` in `bots/treasury/trading/__init__.py`.
- TradingEngine class-level constants now expose BLOCKED_* and risk thresholds for legacy access.

## Module Layout Validation (Target 5 modules + helpers)
Target:
- trading_core.py (public surface)
- trading_execution.py (execution + signals)
- trading_positions.py (state)
- trading_risk.py (risk)
- trading_analytics.py (PnL/reporting)
Helpers: types/constants/logging

Current:
- trading_core.py: public surface
- trading_engine.py: orchestrator (core)
- trading_operations.py: open/close/update/reconcile
- trading_execution.py: swaps + signals
- trading_positions.py: state + migration
- trading_risk.py: risk logic
- trading_analytics.py: PnL + learning
- types.py / constants.py / logging_utils.py / memory_hooks.py

Verdict: layout matches target with extra separation (engine + operations + memory hooks).

## Call-Site Checks
- No imports of `trading_legacy` found.
- No `TreasuryEngine` references found.

## Architecture (Current Refactor)
Components:
- TradingEngine: orchestrator, admin/risk delegation, audit logging, order manager.
- TradingOperationsMixin: open/close/update/monitor/reconcile operations.
- SwapExecutor: Bags/Jupiter execution with circuit breaker integration.
- SignalAnalyzer: sentiment/liquidation/MA combined signals.
- PositionManager: load/save/migrate positions, legacy fallback.
- RiskChecker: token safety + spending limits + sizing.
- TradingAnalytics: PnL and self-correcting AI learning.

Data Flow:
1) Signal -> TradingEngine.analyze_* -> TradingOperationsMixin.open_position
2) Risk checks -> quote -> execute swap -> position persisted
3) Monitoring -> close/reconcile -> analytics + learning

## Critical Dependencies (Primary References)
- Solana RPC (HTTP + WebSocket)
- Jupiter Swap API V6 (quote + swap)
- Bags.fm API (primary execution)
- Pyth price feeds (market data)
- Telegram Bot API + aiogram (bot integration)

## Security Model (Current)
- Admin-only trading (`is_admin` + user_id checks)
- Kill switch via env flag
- Circuit breaker via core.recovery.adapters
- Audit logging (local + centralized audit_trail)
- SafeState for atomic file access (if available)
- RiskManager alerts and circuit breaker

## Minimal Repo Scaffold (current)
- bots/treasury/trading/
  - trading_engine.py
  - trading_operations.py
  - trading_execution.py
  - trading_positions.py
  - trading_risk.py
  - trading_analytics.py
  - treasury_trader.py
  - types.py
  - constants.py
  - logging_utils.py

## Implementation Plan (Refactor Parity Fixes)
1) Optional: expose BLOCKED_TOKENS/BLOCKED_SYMBOLS on TradingEngine for legacy patterns.

## Testing Plan
- Unit:
  - test_trading_engine.py, test_trading_operations.py, test_trading_positions.py, test_trading_risk.py
- Integration:
  - test_trading_flow.py (swap + positions + TP/SL)
- Regression:
  - check_token_safety tool uses updated engine/risk helper

## Latency + Tx Landing Plan (current)
- Fast path: signal -> quote -> execute -> confirm
- Bags.fm primary, Jupiter fallback
- Circuit breaker guards against cascading failures
- (Future) gRPC streaming + priority fees + Jito bundles

