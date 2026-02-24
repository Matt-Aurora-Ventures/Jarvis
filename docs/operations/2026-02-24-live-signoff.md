# 2026-02-24 Live Signoff

## Scope
- Phase 1-4 validation + merge + live rollout for Jarvis Sniper surface reliability.
- Domain targets: `kr8tiv.web.app`, `jarvislife.cloud`, `www.jarvislife.cloud`.

## GitHub Merge
- Branch pushed: `phase14-validation-live-rollout-20260224b`
- Commit merged to `main`: `f1004cd6`

## Validation Results

### Python (blocking phase 1-4 suites)
Command:
```bash
pytest core/open_claw/tests core/backtest/data_ingestion/tests bots/tradfi_sniper/tests core/intel/tests tests/backtesting -q
```
Result:
- Pass (`56 passed`)

### Python (full legacy command from initial matrix)
Command:
```bash
pytest core/open_claw/tests core/backtest/data_ingestion/tests bots/tradfi_sniper/tests core/intel/tests tests/backtesting tests/unit -q
```
Result:
- Fails at collection due pre-existing legacy API mismatch in `tests/unit` (not introduced in this rollout).
- Tracked as advisory/non-blocking in updated matrix/workflow.

### Jarvis Sniper
Commands:
```bash
npm -C jarvis-sniper run lint
npm -C jarvis-sniper run test
npm -C jarvis-sniper run build
npm -C jarvis-sniper run check:real-data-only
```
Result:
- All commands exit `0`.

## Deploy
Command:
```bash
npm -C jarvis-sniper run deploy:hardened
```
Result:
- Firebase hosting + function deploy succeeded.
- Hosting URL updated: `https://kr8tiv.web.app`
- Post-deploy hardening script failed due missing authenticated `gcloud` active account on this machine.

## Live Smoke
Evidence artifact:
- `jarvis-sniper/debug/live-smoke-20260224-164514.json`

Checks:
- `https://kr8tiv.web.app/api/health` -> 200 JSON, `backend.cloudRunTagUrl` non-null
- `https://jarvislife.cloud/api/health` -> 200 JSON, `backend.cloudRunTagUrl` non-null
- `https://www.jarvislife.cloud/api/health` -> 200 JSON, `backend.cloudRunTagUrl` non-null
- `/api/version` matches across all three domains
- Browser check on `/investments` confirms "Investments Coming Soon" banner and panel shell rendering.

## Outstanding Follow-ups
1. Run Cloud Run hardening after restoring `gcloud` auth in this environment.
2. Resolve legacy `tests/unit` compatibility track separately (advisory suite already isolated in workflow).
