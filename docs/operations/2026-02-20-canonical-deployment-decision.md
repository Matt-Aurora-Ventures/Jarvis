# Canonical Deployment Decision (2026-02-20)

## Decision
Use `deploy/clawdbot-redundancy/` as the canonical **production** deployment path.

## Rationale
- Contains production-focused entrypoint and lifecycle logic:
  - provider/env wiring
  - tailscale handling
  - redis hydration
  - supermemory bootstrap
  - watchdog/health integration
- Explicit multi-bot composition and operations scripts are colocated.
- Better fit for long-running VPS operations than ad hoc compose scripts.

## Role of `docker/clawdbot-gateway/`
Retain as **development/integration** surface for local or simplified setups.
Not the primary source of truth for production runbooks.

## Canonical Files
- `deploy/clawdbot-redundancy/docker-compose.clawdbots.yml`
- `deploy/clawdbot-redundancy/entrypoint.sh`
- `deploy/clawdbot-redundancy/openclaw-config-template.json`
- `deploy/clawdbot-redundancy/auth-profiles-template.json`

## Required Follow-up Alignment
1. Update runbooks/docs to reference canonical production files first.
2. Keep `docker/clawdbot-gateway/` in sync only for local/dev use cases.
3. Add explicit "production vs dev" labels in both directories.

## Guardrails
- No hardcoded secrets in repo configs.
- Provider auth mode must remain explicit per bot profile.
- Any new startup behavior must be added to canonical path first, then backported to dev path if needed.
