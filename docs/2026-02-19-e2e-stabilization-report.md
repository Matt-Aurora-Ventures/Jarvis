# End-to-End Stabilization Report (2026-02-19)

## Scope
- Canonical surface: `jarvis-sniper`
- Perps path: `web/perps_api.py` + `core/jupiter_perps/*` validation suites
- Environments tested:
1. Local (`http://127.0.0.1:3001`)
2. Live (`https://kr8tiv.web.app`)

## Executive Status
- Direction is correct and materially improved in this tranche.
- Local canonical stack is stable and test-green.
- Live API regression (`/api/*` returning HTML) is restored to JSON after redeploy under Node 20 toolchain.
- Remaining launch blockers are operational hardening, dependency risk remediation, and backtest runtime latency behavior.

## What Was Implemented
1. CI/CD determinism and gate hardening:
- Added lockfile policy support by tracking `jarvis-sniper/package-lock.json`.
- Updated workflows to use `npm ci` with lockfile cache path.
- Added environment diagnostics (node/npm/python versions + lockfile checks).
- Strengthened deploy smoke checks to assert JSON API contracts post-deploy.
- Added runtime-mode guard in deploy workflow to fail if static export config is detected.

2. Browser automation reliability:
- `smoke-nav-playwright.py` now fails on API wiring signatures (`Unexpected token '<'`, `useMacroData/useTVScreener fetch failed`).
- `smoke-mobile-playwright.py` now:
1. Fails on API wiring signatures.
2. Persists logs/steps even on early failures.
3. Handles "wallet already connected / session wallet on" state without false failure.

3. Test contract alignment (no behavior refactor):
- Updated tests for async shared rate-limiter checks.
- Updated autonomy route tests for auth-required route contract.
- Removed bags-swap test timeout by mocking `@bagsfm/bags-sdk` import path in the test.

4. Live deploy execution and verification:
- Deploy fails under local Node 24 with Firebase frameworks timeout.
- Deploy succeeds using Node 20 wrapper.
- Live APIs now return JSON content-type and parse cleanly.

## Severity-Ranked Findings (Current)

### P0
1. Firebase deployment toolchain fragility:
- Running deploy from Node 24 caused `User code failed to load... Timeout after 10000` in framework analysis.
- Node 20 deploy succeeds.
- Impact: high operational risk if local/manual deploys are run with unsupported runtime.
- Mitigation in place: workflow pinned to Node 20 + runtime-mode guard + post-deploy JSON smoke.

2. Dependency risk remains elevated in prod tree:
- `npm audit --omit=dev` current baseline: `0 critical, 19 high, 3 moderate, 1 low` (23 total).
- Primary chain remains `@bagsfm/bags-sdk` transitives.
- Impact: public rollout blocker until risk is reduced or formally accepted with compensating controls.

### P1
1. Backtest API runtime latency:
- Direct `/api/backtest` POST can exceed tight probe timeouts in dev flows.
- Impact: unstable smoke/gating if used as a direct readiness probe.
- Mitigation in place: smoke probe now uses deterministic JSON endpoints (`/api/backtest/runs/nonexistent`) instead of heavy computation path.

2. Mobile smoke false-negative risk (now corrected):
- Wallet modal check assumed one UI state only.
- Mitigation: supports both connect-modal and already-connected states.

### P2
1. Autonomy auth route expectations:
- Tests needed explicit auth token setup due protected endpoint contract.
- This is expected behavior but requires explicit test fixture hygiene.

## Evidence Snapshot
- `npm test` (jarvis-sniper): 48 files, 299 tests, all passing.
- `npm run build` (jarvis-sniper): passing; dynamic API routes emitted.
- Perps suite gate:
1. `tests/test_execution_intent.py`
2. `tests/test_execution_service_standalone.py`
3. `tests/test_runner_external_queue.py`
4. `tests/test_perps_api_ingress.py`
5. `tests/test_signer_loader.py`
- Result: 46 passed.
- Vanguard standalone smoke: passed (`python scripts/test_vanguard_standalone.py --runtime-seconds 30`).
- Browser smoke:
1. Local nav: pass.
2. Local mobile: pass.
3. Live nav: pass.
4. Live mobile: pass.
- Live API probes after deploy:
1. `/api/health` -> 200 JSON.
2. `/api/version` -> 200 JSON.
3. `/api/macro` -> 200 JSON.
4. `/api/tv-screener` -> 200 JSON.

## Utility-First Recommendations
1. Keep canonical surface enforcement strict:
- `jarvis-sniper` only for production claims and deploy defaults.

2. Treat Node runtime as a deploy gate:
- For local/manual deploy commands, enforce Node 20 (or supported version) explicitly.
- Avoid ad-hoc deploys with ambient Node 24.

3. Keep smoke assertions focused on user-visible truth:
- JSON parse warnings and HTML-in-API responses should remain hard-fail signatures.

4. Avoid heavy backtest endpoint in deployment health checks:
- Use lightweight deterministic API contract probes for release validation.

5. Maintain explicit prod-vs-dev vulnerability policy:
- Track prod-only baseline and fail CI on criticals or high-count regression.

## 14-Day Roadmap
1. P0.1: Deploy runtime pinning and operator runbook (Owner: Platform, Effort: S, Risk: Low)
- Add explicit Node runtime wrapper for all manual deploy scripts.
- Success metric: no deploy timeout incidents from runtime mismatch.

2. P0.2: Prod dependency chain reduction (`@bagsfm/bags-sdk` path) (Owner: Backend, Effort: M, Risk: Medium)
- Apply non-breaking updates/overrides where safe.
- Success metric: reduce prod high vulnerabilities below current baseline without runtime regressions.

3. P1.1: Backtest execution path SLA instrumentation (Owner: Backend, Effort: M, Risk: Medium)
- Add route latency budget telemetry for `/api/backtest` phases.
- Success metric: p95/p99 observability and actionable timeout root-cause breakdown.

4. P1.2: CI artifactization for test/smoke evidence (Owner: DevOps, Effort: S, Risk: Low)
- Persist smoke screenshots + console logs from pipeline runs.
- Success metric: one-click diagnosis for failures.

5. P1.3: Perps + canonical route matrix automation (Owner: QA/Platform, Effort: M, Risk: Low)
- Expand a deterministic matrix runner for local/live contract probes.
- Success metric: nightly pass/fail snapshot with drift detection.

## Files Changed in This Tranche
- `.gitignore`
- `.github/workflows/ci.yml`
- `.github/workflows/p0-readiness-gates.yml`
- `.github/workflows/jarvis-sniper-firebase-deploy.yml`
- `jarvis-sniper/scripts/smoke-nav-playwright.py`
- `jarvis-sniper/scripts/smoke-mobile-playwright.py`
- `jarvis-sniper/src/__tests__/production-hardening.test.ts`
- `jarvis-sniper/src/__tests__/bags-swap-route.test.ts`
- `jarvis-sniper/src/app/api/autonomy/status/__tests__/route.test.ts`
- `jarvis-sniper/src/app/api/autonomy/trade-telemetry/__tests__/route.test.ts`
- `jarvis-sniper/src/app/api/strategy-overrides/__tests__/route.test.ts`
- `jarvis-sniper/package-lock.json`
