# Sniper Full Analysis (Canonical + Preview)

Generated: 2026-02-23 (UTC)  
Scope: canonical `jarvis-sniper` integration, preview stabilization, security/runtime review, backtesting contract hardening.

## Architecture Summary

- Canonical UI surface is `jarvis-sniper` with route-level APIs in `jarvis-sniper/src/app/api/*`.
- Perps and investments are now integrated on canonical routes:
  - `/investments` (`jarvis-sniper/src/app/investments/page.tsx`)
  - `/trading` redirect compatibility (`jarvis-sniper/src/app/trading/page.tsx`)
- Canonical proxies now provide strict endpoint allowlists:
  - `/api/perps/*` (`jarvis-sniper/src/app/api/perps/*`)
  - `/api/investments/*` (`jarvis-sniper/src/app/api/investments/*`)
- Contract normalization layer is implemented in shared client modules:
  - `jarvis-sniper/src/lib/perps/normalizers.ts`
  - `jarvis-sniper/src/lib/investments/normalizers.ts`
- Preview surfaces remain runnable but non-canonical:
  - Legacy combined UI under `frontend/src/pages/Investments.jsx`
  - Perps prototype API in `web/perps_api.py`

## What Is Strong

- Canonical route recovery is complete locally: `/investments` now 200 and `/trading` redirects to `/investments?tab=perps`.
- Perps chart gap is closed in both preview and canonical surfaces:
  - Preview chart: `frontend/src/components/perps/PerpsPriceChart.tsx`
  - Canonical chart: `jarvis-sniper/src/components/perps/PerpsCandlesChart.tsx`
- Contract mismatch risk is substantially reduced by explicit normalizers and unit tests.
- Backtesting contract governance now has repeatable entrypoints and artifacts:
  - `scripts/backtesting/run_backtest_validation.ps1`
  - `scripts/backtesting/validate_backtest_contract.py`
- Security test blocker is fixed by implementing `core/security/skill_vetter.py`.

## Deficiencies By Severity

### Critical

- Deployed production still lacks canonical route exposure:
  - `https://kr8tiv.web.app/investments` returns `404` (verified 2026-02-23).
  - `https://kr8tiv.web.app/trading` returns `404` (verified 2026-02-23).
  - Impact: users cannot access new features until deployment.

### High

- Investments upstream service implementation is not present in this clean mainline snapshot; canonical proxies depend on an external service at `INVESTMENTS_SERVICE_BASE_URL`.

### Medium

- Preview and canonical surfaces still duplicate substantial UI logic:
  - `frontend/src/components/perps/*` and `jarvis-sniper/src/components/perps/*`
  - `frontend/src/components/investments/*` and `jarvis-sniper/src/components/investments/*`
- Operator write actions for investments depend on matching client/server token setup:
  - `NEXT_PUBLIC_INVESTMENTS_ADMIN_TOKEN` and `INVESTMENTS_ADMIN_TOKEN`.
  - If absent/mismatched, write APIs fail by design.

### Low

- Text encoding artifacts remain in some legacy comments/strings (non-functional, readability only).
- Backtest command output still contains known non-fatal warning noise (pytest asyncio deprecation, expected mocked error logs in tests).

## Security Findings And Remediation Status

- Fixed: missing security module that broke test collection.
  - Added `core/security/skill_vetter.py`.
  - Exported in `core/security/__init__.py`.
  - Verification: `tests/unit/security/test_skill_vetter.py` now passes.
- Fixed: autonomy polling error spam from unauthenticated protected reads.
  - `jarvis-sniper/src/components/SniperControls.tsx` now skips polling when read token is not configured and displays explicit unconfigured state.
- Implemented: investments write endpoint fail-closed behavior.
  - `jarvis-sniper/src/lib/investments/proxy.ts` enforces configured admin token and bearer verification.
- Added: investments container drift guard surface.
  - `jarvis-sniper/src/app/api/investments/version/route.ts`
  - UI warning path in `jarvis-sniper/src/components/investments/AlvaraBasketPanel.tsx`.

## Functionality E2E Results

- Canonical local route smoke:
  - `/` => `200`
  - `/investments` => `200`
  - `/trading` => redirects to `/investments?tab=perps` and resolves `200`.
- Canonical build:
  - `npm --prefix jarvis-sniper run build` => pass.
- Canonical test suite:
  - `npm --prefix jarvis-sniper run test` => pass (`315` passing tests).
- Preview build:
  - `npm --prefix frontend run build` => pass (after fixing `Waveform` import issue).
- Perps ingress:
  - `tests/test_perps_api_ingress.py` => pass.
  - `web/perps_api.py` now uses browser-like headers and preserves upstream error metadata (`status`, `reason`).

## Inefficient Bloat Inventory + Consolidation Plan

- Duplicate perps/investments components across `frontend` and `jarvis-sniper`.
  - Plan: extract shared headless hooks/normalizers into one package and keep surface-specific shells only.
- Multiple UX surfaces for overlapping functionality (prototype + canonical + legacy).
  - Plan: freeze legacy route changes; enforce canonical-only feature work after migration.
- Growing test/runtime matrix with mixed auth assumptions.
  - Plan: add explicit auth/no-auth test fixtures and split fast smoke pack from full secure pack.

## Local vs Deployed vs Origin/Main Matrix

- Canonical integration worktree (this execution):
  - Based on clean `origin/main`.
  - New canonical routes/proxies/components integrated.
  - Build and targeted test suites pass.
- Current user local branch (`C:\Users\lucid\Desktop\Jarvis`):
  - Divergence: `HEAD...origin/main = 3 ahead / 10 behind`.
  - Dirty state: `335` changed entries.
  - High merge risk until rebased/cherry-picked via controlled integration.
- Deployed `kr8tiv.web.app`:
  - Still old route behavior (`/investments` and `/trading` both 404 as of 2026-02-23).

## Readiness Scorecard (Internal Beta Bar)

- Jupiter perps feature readiness: **82%**
  - Gains: charting, price/history normalization, canonical route/panel integration, proxy layer.
  - Remaining: deployed rollout, upstream runtime telemetry hardening.
- Alvara investments feature readiness: **68%**
  - Gains: canonical panel/proxy/read flow, normalization, write-path gating, drift warning.
  - Remaining: production upstream service alignment and end-to-end write path validation.
- Combined canonical go-live readiness: **64%**
  - Gains: route exposure solved locally, testable contract layer.
  - Remaining: deployment + suite stabilization + operational env wiring.

## Immediate Priorities

### Next 24h

- Deploy canonical build exposing `/investments` + `/trading`.
- Set and verify envs:
  - `PERPS_SERVICE_BASE_URL`
  - `INVESTMENTS_SERVICE_BASE_URL`
  - `INVESTMENTS_ADMIN_TOKEN`
  - `NEXT_PUBLIC_ENABLE_INVESTMENTS`
  - `NEXT_PUBLIC_ENABLE_PERPS`
- Run smoke checks against deployed URL after rollout.

### Next 72h

- Run internal beta test pass on perps and investments operator flows.
- Confirm investments service contract parity in deployed environment.

### Next 7d

- De-duplicate preview/canonical component logic.
- Lock feature development to canonical-only surface.
- Execute staged dependency remediation from `jarvis-sniper/docs/dependency-risk-register.md` (P0/P1 first).
