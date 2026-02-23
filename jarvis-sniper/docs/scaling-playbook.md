# Jarvis Sniper Scaling Playbook

Last updated: 2026-02-19

## Purpose

This playbook defines how to take Jarvis Sniper from single-operator usage to controlled multi-user scale without breaking execution safety, observability, or fund protection.

## Current Baseline

- Next.js app + API routes, running as a single process by default.
- Shared in-process caches/rate limiters now abstracted behind provider interfaces:
  - `src/lib/cache-provider.ts`
  - `src/lib/rate-limit-provider.ts`
- Autonomy routes are token-gated and rate-limited.
- Telemetry ingestion is authenticated, size-limited, and tagged with trust level.
- Execution evidence and autonomy artifacts persist to local app storage paths.

## Scale Objectives

1. Keep fund safety controls strict under load.
2. Keep backtest/autonomy workloads from degrading user-facing APIs.
3. Support gradual tenant growth with reversible rollout gates.

## Required Architecture Steps

### Phase 0: Private Beta Hardening (now)

- Keep single instance deployment.
- Require auth tokens for autonomy and telemetry routes.
- Enforce production env policy for secrets and signer mode.
- Track API latency/error rates and autonomy cycle health.

Exit criteria:
- Full test/lint/build gates green.
- No critical security findings introduced.
- Manual operator runbook validated.

### Phase 1: Multi-Instance Readiness

- Set shared providers for cross-instance consistency:
  - `JARVIS_CACHE_PROVIDER=redis`
  - `JARVIS_RATE_LIMIT_PROVIDER=redis`
  - `REDIS_URL` or `UPSTASH_REDIS_REST_URL`
- Move artifact/evidence storage to durable shared backing (object store + metadata index).
- Ensure sticky-less operation (no correctness dependency on single pod memory).

Exit criteria:
- Two-instance soak test with stable rate-limits and cache behavior.
- Zero data-loss in artifact/evidence writes during rolling restarts.

### Phase 2: Workload Isolation

- Split services by concern:
  - Web/API service
  - Autonomy worker service (hourly cycle)
  - Backtest worker service (long-running jobs)
- Use queue-based dispatch for heavy jobs with idempotency keys.
- Keep API routes fast by returning job IDs for asynchronous execution.

Exit criteria:
- p95 API latency remains within target under concurrent autonomy/backtest load.
- Queue retries are bounded and observable.

### Phase 3: Controlled Public Rollout

- Introduce tenant-level controls (quotas, API keys, per-tenant rate classes).
- Add progressive rollout flags for high-risk execution features.
- Formalize incident response and security review cadence.

Exit criteria:
- Tenant isolation checks pass.
- On-call playbooks practiced.
- Dependency/security P0 items closed.

## Operational SLOs

- API availability: >= 99.9%
- Trade telemetry ingest success: >= 99.5%
- Autonomy cycle completion (hourly): >= 99%
- Error budget alerts:
  - 5xx rate > 1% for 5m
  - Autonomy cycle miss > 1 interval
  - Queue retry burst above baseline

## Observability Requirements

- Structured logs with request IDs and cycle IDs.
- Metrics:
  - route latency p50/p95/p99
  - rate-limit rejection counts per route
  - autonomy auth failures
  - telemetry ingest accepted/rejected counts
  - evidence write failures
- Dashboards:
  - API health
  - autonomy status
  - execution evidence quality

## Security and Compliance Controls

- Keep write/control routes token-authenticated.
- Separate read vs write tokens where possible.
- Rotate autonomy tokens regularly and on personnel change.
- Enforce payload size limits and input validation on all ingestion routes.
- Run regular dependency audits and track accepted risk explicitly.

## Release Checklist for Each Scale Stage

1. Tests: `npm -C jarvis-sniper run test`
2. Lint: `npm -C jarvis-sniper run lint`
3. Build: `npm -C jarvis-sniper run build` (or isolated build-check workspace if lock contention exists)
4. Security audit: `npm -C jarvis-sniper audit`
5. Smoke test live endpoints and autonomy status route with auth
6. Verify rollback path before promoting

## Rollback Policy

- Any spike in failed executions, missing telemetry, or sustained 5xx triggers immediate rollback to prior stable image.
- Keep database/storage schema changes backward-compatible for one release window.
- Feature flags default to fail-closed for autonomous execution paths.

## Ownership

- Trading safety owner: execution and wallet safety controls
- Platform owner: deployment, scaling, observability
- Security owner: auth, token rotation, dependency governance



