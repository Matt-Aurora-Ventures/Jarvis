# Perps Top Section + Local NotebookLM Go-Live Check Design

Date: 2026-02-27
Owner: Codex + lucid

## Goal
Ship a production-usable Perps operator surface in `jarvis-sniper` that exposes charting, entries, exits, and live-control actions (runner + arm/disarm), while keeping NotebookLM strictly outside runtime/build and using it only as a local final verification pass.

## Scope
- In scope:
  - Promote Perps as explicit top section in Investments UI.
  - Keep/validate existing chart + open/close + TP/SL workflow.
  - Add missing runtime control actions to UI: runner start/stop, arm prepare/confirm, disarm.
  - Add missing Next.js perps proxy routes for existing upstream endpoints.
  - Add tests for new API routes and panel interaction/state rendering.
  - Add local NotebookLM go-live verification script + question set + evidence artifact.
- Out of scope:
  - Embedding NotebookLM in application runtime.
  - New perps trading engine logic in upstream service.
  - Secret key hardcoding in repo files.

## Existing Architecture Constraints
- Canonical UI: `jarvis-sniper`.
- Perps frontend currently reads/writes via `/api/perps/*` proxy routes.
- Upstream perps runtime already exposes endpoints including `/arm`, `/disarm`, `/runner/start`, `/runner/stop`, `/limits` (via `web/perps_api.py`).
- Perps feature is env-gated (`NEXT_PUBLIC_ENABLE_PERPS`).

## Design Decisions
1. Extend, do not replace, the current `PerpsSniperPanel` + `usePerpsData` pattern.
2. Use existing `proxyPerpsPost` path for new routes to avoid duplicated proxy logic.
3. Keep the Grok/xAI key in environment configuration only (`XAI_API_KEY` / perps AI envs), never committed to source.
4. NotebookLM verification is an offline/operator workflow with saved artifact under `temp/` and ops summary under `docs/operations/`.

## Components and File Targets
- UI shell and sectioning:
  - `jarvis-sniper/src/components/investments/InvestmentsPageClient.tsx`
- Perps panel controls:
  - `jarvis-sniper/src/components/perps/PerpsSniperPanel.tsx`
  - `jarvis-sniper/src/components/perps/usePerpsData.ts`
- New API routes:
  - `jarvis-sniper/src/app/api/perps/arm/route.ts`
  - `jarvis-sniper/src/app/api/perps/disarm/route.ts`
  - `jarvis-sniper/src/app/api/perps/runner/start/route.ts`
  - `jarvis-sniper/src/app/api/perps/runner/stop/route.ts`
  - `jarvis-sniper/src/app/api/perps/limits/route.ts`
- Tests:
  - Route tests mirroring existing perps route pattern under `jarvis-sniper/src/app/api/perps/**/__tests__/`.
  - Perps panel or investments client test updates under `jarvis-sniper/src/components/**/__tests__/`.
- Local NotebookLM go-live check artifacts:
  - `temp/` script + JSON/MD outputs.
  - `docs/operations/` summary entry.

## Data Flow
1. User enters Perps tab and sees top Perps section + runtime control strip.
2. Control actions call Next.js proxy route (`/api/perps/*`).
3. Proxy forwards to `PERPS_SERVICE_BASE_URL/api/perps/*` with timeout/error normalization.
4. UI refreshes status and displays action feedback in-panel.

## Error Handling
- Preserve fail-safe behavior for disabled surfaces (`forceDisabledReason`, env gate).
- Show explicit per-action failures in panel state (no silent failures).
- Reuse existing proxy timeout/unavailable codes (`UPSTREAM_TIMEOUT`, `UPSTREAM_UNAVAILABLE`).

## Testing Strategy
- Route-level: verify each new endpoint forwards to expected upstream path and method.
- UI-level: verify Perps control buttons render and action state messaging appears.
- Build/lint/test subset run for `jarvis-sniper` before completion.

## Security
- Do not commit Grok key provided in chat.
- Configure xAI/Grok via deployment/local env variables only.
- If needed, update `.env.example` with variable names only (no secrets).

## Rollout Verification
- Local: run route tests + UI tests + `npm -C jarvis-sniper run build`.
- Runtime smoke: `/api/health` shows perps upstream configured/ok, then exercise runner + arm/disarm + open/close from UI.
- Local NotebookLM final check: run targeted question batch and attach artifact as pre-go-live evidence.