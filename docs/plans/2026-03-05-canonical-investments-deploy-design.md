# Canonical Investments Deploy Design

## Goal

Deploy the investments experience to the active `jarvislife.cloud` surface using the canonical `jarvis-sniper` frontend and the standalone `services/investments` backend, while leaving legacy and unfinished surfaces out of production.

## Approved Direction

### Canonical Surfaces

- `jarvis-sniper` is the only public UI that should back `jarvislife.cloud`.
- `services/investments` is the only basket backend contract the live UI should consume.
- The older `frontend/` and `web/` surfaces are not part of the production path and should remain out of the rollout.

### Conflict Resolution

- If duplicate UI exists, keep the `jarvis-sniper` implementation.
- If duplicate API shaping exists, keep the `services/investments/api.py` contract that already matches the `jarvis-sniper` investment normalizers.
- If a feature is incomplete or partially wired, disable or hide it rather than shipping an ambiguous or degraded operator path.

### Runtime Topology

#### Frontend

- `jarvis-sniper` remains the production shell.
- The active investments page is `jarvis-sniper/src/components/investments/InvestmentsPageClient.tsx`.
- The page consumes `/api/investments/*` through the `jarvis-sniper` proxy routes and should not call the prototype frontend directly.

#### Backend

- `services/investments` runs as a standalone FastAPI service.
- It is deployed separately and exposed to the frontend via `INVESTMENTS_SERVICE_BASE_URL`.
- The backend must remain safe-by-default:
  - `DRY_RUN=true` for the first cloud cut unless basket creation and keys are fully ready.
  - `ENABLE_BRIDGE_AUTOMATION=false`
  - `ENABLE_STAKING_AUTOMATION=false`

### UX Principles

- Keep the current `jarvis-sniper` visual language and interaction model.
- Streamline the investments surface around one operator flow:
  - current basket state
  - recent decisions
  - cycle trigger
  - kill switch
  - runtime/version drift warning
- Remove or suppress dead-end, inactive, or unfinished controls instead of exposing “almost-live” states.
- Favor fewer, clearer actions over extra panels.

### Rollout Plan

1. Deploy `services/investments` first.
2. Verify backend health and contract compatibility.
3. Wire `jarvis-sniper` runtime env to the healthy investments upstream.
4. Deploy `jarvis-sniper` through the existing Firebase/Cloud Run flow.
5. Run production smoke tests against `jarvislife.cloud`.

### Smoke Test Contract

#### Backend

- `GET /health`
- `GET /api/investments/basket`
- `GET /api/investments/performance?hours=168`
- `GET /api/investments/version`

#### Frontend

- `GET /api/health` reports the investments upstream as configured and healthy.
- `/investments?tab=investments` renders without broken loading or dead panels.
- The operator can run a basket cycle.
- The operator can activate and deactivate the kill switch.

### Rollback

Fast rollback is frontend-only:

- set `NEXT_PUBLIC_ENABLE_INVESTMENTS=false`
- redeploy `jarvis-sniper`

This intentionally uses the existing staged-rollout overlay instead of leaving a broken UI exposed.

Secondary rollback:

- unset or revert `INVESTMENTS_SERVICE_BASE_URL`
- point the frontend back to the previous healthy upstream or disable the surface entirely

### Explicit Non-Goals For This Rollout

- Do not merge the legacy `frontend/` or `web/` investments surfaces into production.
- Do not enable bridge automation.
- Do not enable staking automation.
- Do not ship unfinished “live updates” features unless they are fully verified in the canonical runtime.
