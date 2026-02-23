# Full Repo Readiness Evaluation (2026-02-20)

## Executive Summary
The repo is feature-rich and operationally ambitious, but currently has deployment-path drift and branch hygiene risk. The highest-leverage move is to consolidate production operations around a single canonical deployment path and enforce startup/provider/tool parity checks.

## A) Where Code Is Now
- Multi-surface architecture:
  - Python core/runtime and service modules
  - Next.js sniper app (`jarvis-sniper`)
  - OpenClaw/ClawdBot gateway and redundancy deploy surfaces
  - legacy/prototype surfaces still present
- Duplicate deployment/config surfaces for OpenClaw/Codex behavior:
  - `docker/clawdbot-gateway/`
  - `deploy/clawdbot-redundancy/`
- Worktree contains substantial in-flight changes across multiple domains, increasing release and debugging coupling.

## B) Where Code Needs To Be
- One canonical production deployment track with documented ownership.
- One source of truth for provider+tool startup contracts:
  - Anthropic path
  - xAI path
  - Codex CLI path
- Deterministic startup checks for required binaries and auth mode assumptions.
- Clear separation between production, preview, and prototype surfaces.

## C) What Is Left To Do (Priority Order)
1. Canonicalize production run path and tag secondary paths as dev-only.
2. Standardize Codex bootstrap and fallback verification across all startup surfaces.
3. Remove docs/runtime drift (provider/tool instructions must match real entrypoints).
4. Add smoke checks:
   - provider env/auth present
   - key CLI tools resolvable (`openclaw`, `clawdbot`, `codex`)
5. Clean branch hygiene:
   - isolate infra/runtime changes from unrelated feature work
   - reduce blast radius for deploys.

## D) What’s Good
- Clear role model by bot profile (Matt/Friday/Jarvis) and intentional provider targeting.
- Strong operational primitives already present:
  - watchdog behavior
  - health checks
  - redis/supermemory context strategy
- Documentation captures intended Codex CLI no-API-key mode.

## E) What’s Weak
- Deployment duplication causes configuration drift and inconsistent startup behavior.
- Runtime npm installs without strict command resolution made Codex availability brittle.
- Large mixed worktree raises confidence risk for production rollouts.

## Backlog (Execution-Ready)

### Now (0-2 days)
1. Finalize and deploy canonical Codex bootstrap in production path.
2. Run VPS acceptance checks:
   - `codex --version`
   - `codex --login`
   - restart persistence checks
3. Add a short operational runbook section for Codex CLI auth lifecycle.

### Next (3-7 days)
1. Add startup smoke script for bot containers:
   - provider-specific env checks
   - command availability checks
2. Label and document non-canonical deployment surfaces as dev-only.
3. Add CI lint/check job for compose and shell startup safety.

### Later (1-3 weeks)
1. Collapse duplicate deployment logic into reusable scripts/templates.
2. Introduce release gates for environment parity (prod/staging/dev).
3. Prune legacy/prototype surfaces from production documentation path.

## Single Recommended Next Step
Run the VPS in-container verification and restart persistence checks on `openclaw-ydy8-openclaw-1`, then promote `deploy/clawdbot-redundancy/` as the official production source of truth in runbooks.

## Acceptance Criteria
- Codex CLI is resolvable and login-capable after container restart.
- Anthropic workflows remain unchanged.
- Production docs point first to canonical deployment files.
- A short prioritized backlog exists and is owned.
