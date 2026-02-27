# Surface Readiness Checklist (Basket, Perps, Clawbot)

Date: 2026-02-27  
Scope: `jarvis-sniper` top navigation and investments/clawbot runtime gating.

## 1. Basket (Alvara)

Current mode:
- Env-gated demo-safe by default.
- Controlled by `NEXT_PUBLIC_ENABLE_INVESTMENTS`.
- Defaults to disabled until explicitly set to `true`.

What stays visible when disabled:
- Panel shell, metrics cards, decision history, and staged-rollout overlay.

What is blocked when disabled:
- Trigger cycle.
- Kill switch activate/deactivate.

Production-ready checklist:
1. Set `INVESTMENTS_SERVICE_BASE_URL` to a healthy upstream.
2. Set `INVESTMENTS_ADMIN_TOKEN`.
3. Set `NEXT_PUBLIC_ENABLE_INVESTMENTS=true`.
4. Verify `GET /api/health` reports `upstreams.investments.configured=true` and `ok=true`.
5. Run smoke tests for basket reads + admin write endpoints.

## 2. Perps

Current mode:
- Env-gated demo-safe by default.
- Controlled by `NEXT_PUBLIC_ENABLE_PERPS`.
- Defaults to disabled until explicitly set to `true`.

What stays visible when disabled:
- Panel shell, price/status/history blocks, staged-rollout overlay.

What is blocked when disabled:
- Open position.
- Close position.

Production-ready checklist:
1. Set `PERPS_SERVICE_BASE_URL` to a healthy upstream.
2. Set `NEXT_PUBLIC_ENABLE_PERPS=true`.
3. Verify `GET /api/health` reports `upstreams.perps.configured=true` and `ok=true`.
4. Verify runner status is healthy and arm/mode policy is correct.
5. Run open/close lifecycle smoke tests from UI.

## 3. Clawbot (New Top Tab)

Current mode:
- Always demo-safe for this release.
- Surface key: `clawbot`.
- Route: `/clawbot`.

What stays visible:
- Dedicated top tab (desktop + mobile nav).
- Clawbot page shell with status cards and coming-soon banner.

What is blocked:
- All action controls are disabled.

Production-ready checklist:
1. Add Clawbot API routes for status + audit + controlled actions.
2. Add auth model and rate limits for mutating routes.
3. Add runtime health checks into `/api/health` upstream section.
4. Add end-to-end safety tests for halt/recovery behavior.
5. Switch `clawbot` surface from hard-disabled to explicit env-gated rollout.

