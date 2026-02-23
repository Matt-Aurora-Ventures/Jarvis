# Canonical Investments/Perps Baseline (2026-02-22)

## Scope
Baseline captured from clean branch `feature/canonical-investments-perps-integration-exec` (branched from `origin/main`) before integration and recovery changes.

## Environment
- Canonical dev server: `jarvis-sniper` on `http://127.0.0.1:3021`
- Prototype perps API: `http://127.0.0.1:5001`
- Investments service: `http://127.0.0.1:8770`

## Route Baseline
- `GET /` -> `200`
- `GET /bags-sniper` -> `200`
- `GET /tradfi-sniper` -> `200`
- `GET /investments` -> `404`
- `GET /trading` -> `404`

## Perps API Baseline
- `GET /api/perps/prices` returns market-object shape with `fetch_failed` and `price: 0.0` for `SOL-USD/BTC-USD/ETH-USD`.
- `GET /api/perps/history/SOL-USD` returns `{"candles": [], "error": "HTTP Error 403: Forbidden"}`.
- `GET /api/perps/history/BTC-USD` returns `{"candles": [], "error": "HTTP Error 403: Forbidden"}`.
- `GET /api/perps/status` returns health payload; runner down/disarmed in this baseline.

## Investments API Baseline
- `GET /api/investments/basket` returns basket with token-map `tokens` + `nav_usd`.
- `GET /api/investments/performance?hours=168` returns wrapper shape `{basket_id, hours, points, change_pct}`.
- `GET /api/investments/decisions?limit=5` returns list (empty in this baseline).
- `GET /api/investments/kill-switch` returns `{"active": false}`.

## Test Baseline
### Python backtesting
Command:
```bash
pytest tests/backtesting -q
```
Result: `41 passed`.

### Jarvis-sniper backtest cluster
Command:
```bash
npm --prefix jarvis-sniper run test -- \
  src/__tests__/bags-backtest.test.ts \
  src/__tests__/bags-backtest-api.test.ts \
  src/__tests__/backtest-route-execution-realism.test.ts \
  src/__tests__/backtest-campaign-orchestrator.test.ts \
  src/__tests__/backtest-artifact-integrity.test.ts \
  src/__tests__/rpc-and-backtest-regressions.test.ts \
  src/__tests__/backtest-cost-accounting.test.ts
```
Result: `6 files passed, 37 tests passed`.

### Security suite
Command:
```bash
pytest tests/unit/security -q
```
Result: fails during collection with:
- `ModuleNotFoundError: No module named 'core.security.skill_vetter'`

## Key Baseline Findings
1. Canonical surface lacks investments/perps routes (`/investments`, `/trading` both 404).
2. Perps upstream market/history fetches are failing (empty charts/prices).
3. Investments service contract differs from frontend expectations in shape/field names.
4. Backtesting baseline is green; security suite is red due missing `skill_vetter` module.
