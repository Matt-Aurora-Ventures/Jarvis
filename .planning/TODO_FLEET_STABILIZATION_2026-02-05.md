# TODO: Fleet Stabilization (Loop Backlog)

**Date:** 2026-02-05  
**PRD:** `.planning/PRD_FLEET_STABILIZATION_2026-02-05.md`  
**Source:** last 48h Telegram + current VPS state

---

## Phase A — KVM4 (Hub) Stabilization

1. Verify pinned model IDs + providers per bot (Friday/Matt Anthropic, Jarvis xAI). `DONE`
2. Stop health API container flapping (remove host `socat` conflict; run dockerized health API). `DONE`
3. Verify identity persistence (SOUL/IDENTITY/HEARTBEAT/USER non-empty, volume-mounted). `DONE`
4. Redis verification:
   - `jarvis-redis` running
   - bots set `REDIS_HOST=jarvis-redis` and use it. `PENDING`
5. Remove provider-key leakage:
   - ensure Jarvis container does not carry Anthropic OAuth or other provider fallbacks. `PENDING`
6. Tune Docker healthchecks to prevent false restarts under load (interval/timeout/retries/start_period). `PENDING`

## Phase B — NotebookLM (MSW) + Agent TARS (Firefox)

1. Install/repair Agent TARS CLI so `agent-tars` is runnable on Windows (PATH + launcher). `DONE`
2. Configure Agent TARS to use Firefox reliably (hybrid control, headful for OAuth). `PENDING`
3. Establish a working Hostinger automation path (avoid Cloudflare loop):
   - real desktop Firefox session, OR Agent TARS + stable profile, OR Chrome relay. `PENDING`
4. Install MSW protocol and wire it to Jarvis workspace (NotebookLM → markdown artifacts). `PENDING`
5. Establish a standard “query NotebookLM” loop:
   - inject error/log excerpt
   - capture grounded answer + follow-up questions
   - compile into `.planning/research/` and supermemory. `PENDING`

## Phase C — KVM8 (Muscle) Stabilization + Treasury Key Recovery (Non-Destructive)

1. Restore SSH access (public port 22 is timing out): **access recovered via SSH on port 443** (documented in Windows SSH config as `jarvis-vps`). `DONE`
2. SSH access validation + inventory (containers/services/log paths). `DONE` (basic inventory + log targets; expand if needed)
3. OOM prevention:
   - caps/swap/logging
   - watchdog that restarts *only* failed services with backoff. `PENDING`
4. Treasury key recovery (no deletes):
   - **FOUND** SecureWallet registry + key material under `bots/treasury/.wallets/` (registry + salt + `<pubkey>.key`). `DONE`
   - key-manager updated to discover/resolve treasury material without printing secrets. `DONE`
5. Stabilize “other GitHub bots” on KVM8:
   - ensure provider keys are isolated
   - ensure persistence mounts
   - ensure correct model allowlists. `PENDING`
6. Buy bot Telegram “Chat not found” (400) remediation:
   - validate chat access on startup
   - fallback alert to admin chat
   - confirm bot membership in `KR8TIV AI - Jarvis Life OS` group. `DONE` (bot invited + `getChat` now 200 OK)
7. Supervisor graceful stop/restart reliability:
   - fix SIGTERM handling (no `systemctl stop` timeouts)
   - stop warning spam from uptime parsing. `DONE`

## Phase D — Mesh Hardening (Tailscale + Watchtower)

1. Confirm all nodes on tailnet and document mapping. `PENDING`
2. Yoda watchdog:
   - can reach KVM4 over `100.x`
   - can restart Friday safely and log reason. `PENDING`
3. Squishy on Mac:
   - uses Google model string
   - can reach shared services as intended. `PENDING`

## Continuous Loop Outputs

1. Regenerate Telegram 48h fix-it synthesis on interval and diff changes. `PENDING`
2. Append key operational learnings into supermemory (shared tag). `PENDING`
3. Maintain incident log with timestamps + root cause + fix. `PENDING`
