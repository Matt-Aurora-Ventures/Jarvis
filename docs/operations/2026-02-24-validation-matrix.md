# Phase 1-4 Validation Matrix (2026-02-24)

## Purpose
Define one deterministic validation contract for local runs and CI so push-to-main and PR checks enforce the same core gates.

## Matrix
| Gate | Command | Pass criteria |
|---|---|---|
| Python core suites | `pytest core/open_claw/tests core/backtest/data_ingestion/tests bots/tradfi_sniper/tests core/intel/tests tests/backtesting -q` | Exit code `0`; no failed tests. |
| Web lint | `npm -C jarvis-sniper run lint` | Exit code `0`; no lint errors. |
| Web unit/integration tests (phase core) | `npm -C jarvis-sniper run test -- src/lib/__tests__/cache-provider.test.ts src/lib/__tests__/rate-limit-provider.test.ts src/lib/__tests__/server-cache.test.ts src/stores/__tests__/useSniperStore.test.ts src/app/api/health/__tests__/route.test.ts src/hooks/__tests__/useBacktest-transport.test.ts src/lib/__tests__/backtest-cors.test.ts` | Exit code `0`; no failed Vitest suites in the phase core contract set. |
| Web production build | `npm -C jarvis-sniper run build` | Exit code `0`; Next.js build completes without fatal errors. |
| Backtest realism contracts | `npm -C jarvis-sniper run test -- src/__tests__/backtest-route-execution-realism.test.ts src/__tests__/rpc-and-backtest-regressions.test.ts` | Exit code `0`; strict-no-synthetic backtest contract tests pass. |

## CI Mapping
- `.github/workflows/python-testing.yml`
  - `python-validation`
  - `web-validation`
  - `backtest-validation`
- `.github/workflows/ci.yml`
  - `python-validation`
  - `web-validation`
  - `backtest-validation`
  - plus existing `prod-dependency-risk` gate.

## Notes
- `jarvis-sniper/package.json` currently does not expose `check:real-data-only`; the backtest realism contract gate above is used as the deterministic strict-no-synthetic check.
- Python validation depends on Parquet support (`pyarrow`) for CoinGecko cache tests.
- Deploy workflow gating is handled separately in Task 5 (`deploy.yml` dependency fix).
