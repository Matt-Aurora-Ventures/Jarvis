# Phase 1-4 Live Rollout Signoff (2026-02-24)

## Decision
- **Status:** `CONDITIONAL FAIL`
- **Reason:** Preflight validation gates pass, but `deploy:hardened` fails in Firebase frameworks deploy phase (`User code failed to load. Cannot determine backend specification. Timeout after 10000.`).

## Branch/Sync State
- Working branch: `feat/phase14-validation-merge-live-clean`
- Rebase status: synced to `origin/main` (no branch drift after rebase/fetch)
- Remote push: `origin/feat/phase14-validation-merge-live-clean`

## Preflight Validation Evidence
- Python core suites: `PASS`
  - Command: `pytest core/open_claw/tests core/backtest/data_ingestion/tests bots/tradfi_sniper/tests core/intel/tests tests/backtesting -q`
  - Result: `56 passed`
- Web lint: `PASS (warnings only)`
  - Command: `npm -C jarvis-sniper run lint`
  - Result: no lint errors, warnings present
- Web tests: `PASS`
  - Command: `npm -C jarvis-sniper run test`
  - Result: `64 files passed, 344 tests passed`
- Web build: `PASS`
  - Command: `npm -C jarvis-sniper run build`
- Real-data-only backtest gate: `PASS`
  - Command: `npm -C jarvis-sniper run check:real-data-only`

## Deploy Attempt Evidence
- Command: `npm -C jarvis-sniper run deploy:hardened`
- Result: `FAIL`
- Error:
  - `Error: User code failed to load. Cannot determine backend specification. Timeout after 10000.`
  - Firebase frameworks warning indicates unsupported runtime path with local Node `v24.13.1` for this preview toolchain.
- Additional context:
  - Firebase auth/project access is valid (`kr8tiv` project access succeeded).
  - Build phase succeeds; failure occurs at backend spec/function analysis.

## Post-Deploy Health Smoke Evidence
- Artifact: `jarvis-sniper/debug/live-smoke-20260224-170046.json`
- Health endpoints:
  - `https://kr8tiv.web.app/api/health` -> `200`
  - `https://jarvislife.cloud/api/health` -> `200`
  - `https://www.jarvislife.cloud/api/health` -> `200`
- Observed from responses:
  - valid JSON
  - `backend.cloudRunTagUrl` populated (`https://fh-72449e75ed065b91---ssrkr8tiv-wrmji3msqa-uc.a.run.app`)
  - status currently reports `degraded` (not `down`)

## Functional Smoke
- API and contract-level coverage: `PASS` via automated tests (`backtest-route-execution-realism`, `useBacktest-transport`, `health route`, `backtest-cors`, disabled-surface UI contracts).
- Manual live UI run-through (single backtest from UI, detached monitor visual confirmation): **not executed in this terminal session**.

## Release Recommendation
- Do **not** mark rollout fully green until deploy pipeline issue is resolved.
- Next unblock:
  1. Re-run deploy with supported Node runtime (`20` or `22`) for Firebase frameworks path.
  2. Re-run `deploy:hardened`.
  3. Re-run health + UI smoke and update this signoff doc to `PASS`.
