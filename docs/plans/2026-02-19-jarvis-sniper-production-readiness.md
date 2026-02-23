# Jarvis Sniper Production Readiness Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Ship Jarvis Sniper to a production-ready baseline where local dev works immediately, CI gates are green (test/lint/build), autonomy endpoints are protected, and the backend is safe for gradual multi-user scale.

**Architecture:** Keep the existing Next.js App Router architecture, but harden high-risk API routes, remove release blockers, and add deterministic test coverage for the security gates. Preserve current trading behavior while adding auth, input validation, and path-safety guardrails.

**Tech Stack:** Next.js 16, TypeScript, Vitest, ESLint, Bags SDK, Solana web3.js

---

## Scope and Acceptance Criteria

- `npm -C jarvis-sniper run test` passes.
- `npm -C jarvis-sniper run lint` passes.
- `npm -C jarvis-sniper run build` passes.
- `/api/autonomy/trade-telemetry` requires a signed auth token and rate limiting.
- `/api/autonomy/status`, `/api/strategy-overrides`, `/api/autonomy/audit/*` are no longer publicly readable without auth.
- `/api/backtest/runs/[runId]/artifacts` rejects invalid `runId` and path traversal payloads.
- Docs and scripts agree on one local dev URL and port.

## Task 1: Fix Release Blockers (Build + Lint)

**Files:**
- Modify: `jarvis-sniper/src/app/api/backtest/route.ts`
- Modify: `jarvis-sniper/src/lib/strategy-selector.ts`
- Test: `jarvis-sniper/src/__tests__/backtest-route-execution-realism.test.ts`

**Step 1: Write/adjust failing type test for backtest route data source handling**

```ts
// add assertion path for client-candle runs to ensure non_real_source is still tagged
expect(summary.dataSourceBreakdown.client).toBeGreaterThanOrEqual(0)
```

**Step 2: Run target test to confirm current failure or missing coverage**

Run: `npm -C jarvis-sniper run test -- src/__tests__/backtest-route-execution-realism.test.ts`
Expected: either FAIL or insufficient coverage for client-source degradation path.

**Step 3: Minimal implementation for build fix**

- Replace impossible comparison on `dataset.source` with a value derived from run result/source context that supports `'client'`.
- Keep `non_real_source` labeling logic functionally intact for client candle mode.

**Step 4: Minimal implementation for lint fix**

- Change `let shape = clampShape(shapeRaw);` to `const shape = clampShape(shapeRaw);` in `jarvis-sniper/src/lib/strategy-selector.ts`.

**Step 5: Re-run release gates for this task**

Run:
- `npm -C jarvis-sniper run lint`
- `npm -C jarvis-sniper run build`

Expected: no lint errors and successful TypeScript build.

**Step 6: Commit**

```bash
git add jarvis-sniper/src/app/api/backtest/route.ts jarvis-sniper/src/lib/strategy-selector.ts jarvis-sniper/src/__tests__/backtest-route-execution-realism.test.ts
git commit -m "fix(sniper): unblock build and lint for backtest/source typing"
```

## Task 2: Stabilize Failing Test Suite

**Files:**
- Modify: `jarvis-sniper/src/lib/__tests__/autonomy-apply-gate.test.ts`
- Modify: `jarvis-sniper/src/__tests__/session-wallet-portfolio-route.test.ts`
- Modify: `jarvis-sniper/src/__tests__/bags-swap-route.test.ts`

**Step 1: Add deterministic module/reset boundaries**

- Use `vi.resetModules()` in each affected suite `beforeEach`.
- Ensure per-test mocks are recreated after reset.

**Step 2: Add explicit timeout where route imports are heavy**

- Set `it(..., { timeout: 15000 })` (or equivalent Vitest timeout config) for route-level tests that import Bags SDK route modules.

**Step 3: Run failing files only**

Run:
- `npm -C jarvis-sniper run test -- src/lib/__tests__/autonomy-apply-gate.test.ts`
- `npm -C jarvis-sniper run test -- src/__tests__/session-wallet-portfolio-route.test.ts`
- `npm -C jarvis-sniper run test -- src/__tests__/bags-swap-route.test.ts`

Expected: all three pass consistently.

**Step 4: Run full suite**

Run: `npm -C jarvis-sniper run test`
Expected: full pass.

**Step 5: Commit**

```bash
git add jarvis-sniper/src/lib/__tests__/autonomy-apply-gate.test.ts jarvis-sniper/src/__tests__/session-wallet-portfolio-route.test.ts jarvis-sniper/src/__tests__/bags-swap-route.test.ts
git commit -m "test(sniper): stabilize route-level suites and remove flakiness"
```

## Task 3: Protect Telemetry Ingestion Endpoint

**Files:**
- Modify: `jarvis-sniper/src/app/api/autonomy/trade-telemetry/route.ts`
- Modify: `jarvis-sniper/src/lib/autonomy/trade-telemetry-store.ts`
- Create: `jarvis-sniper/src/app/api/autonomy/trade-telemetry/__tests__/route.auth.test.ts`

**Step 1: Write failing auth/rate-limit tests**

```ts
it('returns 401 without telemetry token', async () => {})
it('returns 429 when telemetry rate limit exceeded', async () => {})
it('accepts valid signed request', async () => {})
```

**Step 2: Implement auth + limiter + payload bounds**

- Require `Authorization: Bearer <AUTONOMY_JOB_TOKEN>` or dedicated `AUTONOMY_TELEMETRY_TOKEN`.
- Add `autonomyRateLimiter` check.
- Enforce strict payload caps (max lengths already clamped; reject oversized body early by content length when available).

**Step 3: Protect integrity of execution priors**

- Add source tagging or trust level field to telemetry writes.
- Exclude untrusted telemetry from priors used by backtests.

**Step 4: Run tests**

Run: `npm -C jarvis-sniper run test -- src/app/api/autonomy/trade-telemetry/__tests__/route.auth.test.ts`
Expected: PASS.

**Step 5: Commit**

```bash
git add jarvis-sniper/src/app/api/autonomy/trade-telemetry/route.ts jarvis-sniper/src/lib/autonomy/trade-telemetry-store.ts jarvis-sniper/src/app/api/autonomy/trade-telemetry/__tests__/route.auth.test.ts
git commit -m "feat(sniper): secure autonomy telemetry ingestion"
```

## Task 4: Lock Down Autonomy Read Endpoints

**Files:**
- Modify: `jarvis-sniper/src/app/api/autonomy/status/route.ts`
- Modify: `jarvis-sniper/src/app/api/strategy-overrides/route.ts`
- Modify: `jarvis-sniper/src/app/api/autonomy/audit/latest/route.ts`
- Modify: `jarvis-sniper/src/app/api/autonomy/audit/[cycleId]/route.ts`
- Create: `jarvis-sniper/src/app/api/autonomy/status/__tests__/route.auth.test.ts`
- Create: `jarvis-sniper/src/app/api/strategy-overrides/__tests__/route.auth.test.ts`

**Step 1: Write failing unauthorized-access tests**

```ts
it('returns 401 without token')
it('returns 200 with valid token')
```

**Step 2: Implement shared auth helper**

- Add a reusable `requireAutonomyAuth(request)` helper for these routes.
- Reuse existing hourly token model to keep operations simple.

**Step 3: Keep safe public surface minimal**

- If public observability is required, create a sanitized public status route exposing only uptime + basic health (no strategy patches, no cycle internals).

**Step 4: Run route tests**

Run:
- `npm -C jarvis-sniper run test -- src/app/api/autonomy/status/__tests__/route.auth.test.ts`
- `npm -C jarvis-sniper run test -- src/app/api/strategy-overrides/__tests__/route.auth.test.ts`

Expected: PASS.

**Step 5: Commit**

```bash
git add jarvis-sniper/src/app/api/autonomy/status/route.ts jarvis-sniper/src/app/api/strategy-overrides/route.ts jarvis-sniper/src/app/api/autonomy/audit/latest/route.ts jarvis-sniper/src/app/api/autonomy/audit/[cycleId]/route.ts jarvis-sniper/src/app/api/autonomy/status/__tests__/route.auth.test.ts jarvis-sniper/src/app/api/strategy-overrides/__tests__/route.auth.test.ts
git commit -m "feat(sniper): require auth for autonomy status and audit surfaces"
```

## Task 5: Prevent Path Traversal in Backtest Artifact Route

**Files:**
- Modify: `jarvis-sniper/src/app/api/backtest/runs/[runId]/artifacts/route.ts`
- Create: `jarvis-sniper/src/app/api/backtest/runs/[runId]/artifacts/__tests__/route.security.test.ts`

**Step 1: Write failing traversal tests**

```ts
it('rejects runId containing path separators')
it('rejects dot-dot traversal sequences')
it('accepts valid runId format')
```

**Step 2: Implement runId validation**

- Enforce regex allowlist (for example `^[a-zA-Z0-9_-]{8,64}$`).
- Reject invalid IDs with 400 before filesystem join.

**Step 3: Add canonical-path guard**

- Resolve candidate path and ensure it remains under `.jarvis-cache/backtest-runs` root before reads.

**Step 4: Run security tests**

Run: `npm -C jarvis-sniper run test -- src/app/api/backtest/runs/[runId]/artifacts/__tests__/route.security.test.ts`
Expected: PASS.

**Step 5: Commit**

```bash
git add jarvis-sniper/src/app/api/backtest/runs/[runId]/artifacts/route.ts jarvis-sniper/src/app/api/backtest/runs/[runId]/artifacts/__tests__/route.security.test.ts
git commit -m "fix(sniper): validate runId and block path traversal in artifact downloads"
```

## Task 6: Align Local-Run and Deployment Docs

**Files:**
- Modify: `jarvis-sniper/README.md`
- Modify: `jarvis-sniper/DEPLOYMENT.md`
- Modify: `jarvis-sniper/package.json` (only if choosing port 3000 instead of 3001)

**Step 1: Decide canonical dev port**

- Option A: keep `3001` and update all docs.
- Option B: change scripts to `3000` and update deployment docs.

Default choice: **A (keep 3001)** to avoid breaking existing local habits.

**Step 2: Update docs and quickstart text**

- Ensure README and deployment guides match scripts exactly.

**Step 3: Verify docs-to-runtime alignment**

Run: `npm -C jarvis-sniper run dev` and confirm startup URL in logs.
Expected: documented URL matches runtime output.

**Step 4: Commit**

```bash
git add jarvis-sniper/README.md jarvis-sniper/DEPLOYMENT.md jarvis-sniper/package.json
git commit -m "docs(sniper): align local run instructions with actual dev port"
```

## Task 7: Dependency Risk Reduction Wave

**Files:**
- Modify: `jarvis-sniper/package.json`
- Modify: `jarvis-sniper/package-lock.json`
- Create: `jarvis-sniper/docs/dependency-risk-register.md`

**Step 1: Baseline current audit snapshot**

Run: `npm -C jarvis-sniper audit --json > jarvis-sniper/docs/dependency-risk-register.json`

**Step 2: Prioritize direct/runtime packages first**

- Evaluate upgrade path for `@bagsfm/bags-sdk` to patched lineage.
- Re-run integration tests for `/api/bags/quote` and `/api/bags/swap`.

**Step 3: Upgrade test/dev toolchain separately**

- Plan semver-major upgrades for `vitest`, `eslint`, related plugins.

**Step 4: Validate**

Run:
- `npm -C jarvis-sniper run test`
- `npm -C jarvis-sniper run lint`
- `npm -C jarvis-sniper run build`
- `npm -C jarvis-sniper audit`

Expected: reduced high-severity count with no regression in trading paths.

**Step 5: Commit**

```bash
git add jarvis-sniper/package.json jarvis-sniper/package-lock.json jarvis-sniper/docs/dependency-risk-register.md
git commit -m "chore(sniper): reduce dependency vulnerabilities in runtime and tooling"
```

## Task 8: Scale-Readiness Baseline (50 -> 500 users)

**Files:**
- Modify: `jarvis-sniper/src/lib/rate-limiter.ts`
- Modify: `jarvis-sniper/src/lib/server-cache.ts`
- Create: `jarvis-sniper/src/lib/cache-provider.ts`
- Create: `jarvis-sniper/src/lib/rate-limit-provider.ts`
- Create: `jarvis-sniper/docs/scaling-playbook.md`

**Step 1: Add provider interfaces**

- Abstract current in-memory implementations behind interfaces.
- Keep in-memory as default local adapter.

**Step 2: Add Redis-compatible adapters (optional by env)**

- If Redis URL present, use shared cache/limiter for multi-instance correctness.

**Step 3: Add smoke tests for provider fallback**

- Validate no Redis configured -> in-memory adapter.
- Validate Redis configured -> shared adapter path selected.

**Step 4: Operational playbook**

- Document SLOs, dashboard metrics, alert thresholds, and rollout checklist.

**Step 5: Commit**

```bash
git add jarvis-sniper/src/lib/rate-limiter.ts jarvis-sniper/src/lib/server-cache.ts jarvis-sniper/src/lib/cache-provider.ts jarvis-sniper/src/lib/rate-limit-provider.ts jarvis-sniper/docs/scaling-playbook.md
git commit -m "feat(sniper): add pluggable cache/rate-limit providers for scale"
```

## Final Verification Gate

Run in order:

```bash
npm -C jarvis-sniper run test
npm -C jarvis-sniper run lint
npm -C jarvis-sniper run build
npm -C jarvis-sniper audit
```

Expected: all quality gates pass and dependency risk is explicitly documented for remaining accepted findings.

## Assumptions and Defaults

- Canonical local dev URL is `http://localhost:3001` unless explicitly changed.
- Autonomy endpoints are treated as privileged operational surfaces, not public APIs.
- Telemetry used for execution priors must be trusted; unauthenticated writes are out of scope for production.
- Single-instance in-memory cache/limit is acceptable only for local/dev and very small beta; shared backing store is required for horizontal scale.
