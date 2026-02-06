# PRD: ClawdBot Fleet Stabilization ("Golden State")

**Date:** 2026-02-05  
**Owner:** @lucid  
**Scope:** OpenClaw/ClawdBot autonomous fleet (KVM4 hub + KVM8 muscle + Hetzner watchdog + Mac lab)  
**Hard Constraint:** No destructive actions. Do not wipe KVM8. Preserve all wallets/keys/data. Surgical fixes only.

---

## 1. Problem

The fleet has intermittently degraded into:

- Auth/model crash loops (`404` / unknown model IDs, expired OAuth refreshes).
- Provider cross-contamination (Jarvis accidentally using Anthropic tokens).
- Identity amnesia (SOUL/IDENTITY/HEARTBEAT wiped or not volume-mounted).
- Infra flapping (healthchecks/watchdogs restarting healthy containers, burning API credits).
- KVM8 instability + missing treasury key material (must be recovered without wiping the host).

---

## 2. Goals

### G0: "Golden State" always-on stability

- Friday/Matt/Jarvis run stable on **KVM4** with correct providers + model IDs.
- Redis shared memory online for KVM4 bots.
- Identity persistence survives restarts (no “day-one bot” resets).
- KVM8 bots run stable (no OOM loops) and preserve key material.

### G1: Autonomous operations loop

- Continuous “heartbeat” reporting (Telegram + infra + key errors + crash reasons).
- Recovery actions are safe + auditable (no silent destructive behaviors).

### G2: Grounded debugging

- MSW protocol / NotebookLM loop: inject errors → get grounded answers → compile into PRD/TODO updates.
- Agent TARS (Firefox) is the default automation path for OAuth-heavy web UIs.

---

## 3. Non-Goals

- Rebuilding KVM8 from scratch.
- Changing token strategy / trading logic beyond stability.
- Refactors that risk operational regression without test backpressure.

---

## 4. Current Intended Architecture (Baseline)

### Nodes

- **KVM4 (Hub):** Friday, Matt, Jarvis, Redis
- **KVM8 (Muscle):** all other GitHub bots (compute + autonomous loops)
- **Hetzner (Watchtower):** Yoda (watchdog + recovery)
- **Mac (Lab):** Squishy (research + multimodal)

### Providers / Models (must be pinned)

- Friday: Anthropic `claude-opus-4-20250514`
- Matt: Anthropic `claude-sonnet-4-20250514`
- Jarvis: xAI `grok-beta`
- Yoda: NVIDIA `nvidia/moonshotai/kimi-k2.5`
- Squishy: Google `gemini-2.5-pro-preview-05-06` (exact string)

### Wiring

- Provider decoupling: each bot uses only its own provider key(s).
- Redis shared state on KVM4: `jarvis-redis:6379`.
- Identity persistence: `/root/clawd` and bot config directories are volume-mounted.
- Tailscale mesh: Yoda can reach KVM4 over `100.x` and restart containers if needed.

---

## 5. Requirements

### P0 (Stop The Bleed)

- **REQ-FLEET-001:** All bots use verified model IDs only (no `claude-4.5-opus`, no `xai/grok-4.1`, no `anthropic/claude-opus-4-5-*`).
- **REQ-FLEET-002:** Provider keys are fully decoupled per bot (Jarvis never touches Anthropic).
- **REQ-FLEET-003:** No restart flapping (healthchecks/watchdogs tuned; graceful SIGTERM; no loop tax).
- **REQ-FLEET-004:** Identity persistence survives restarts (SOUL/IDENTITY/HEARTBEAT/USER present and non-empty).
- **REQ-FLEET-005:** KVM8 stabilized without wipes (OOM prevention; logs; safe restarts).
- **REQ-FLEET-006:** Treasury key recovery on KVM8 (locate → backup → verify) without deleting data.

### P1 (Autonomy + Grounded Ops)

- **REQ-FLEET-101:** MSW (NotebookLM bridge) operational and used during incident resolution.
- **REQ-FLEET-102:** Agent TARS CLI/UI operational with Firefox for web automation (Hostinger/Hetzner/NotebookLM).
- **REQ-FLEET-103:** Supermemory.ai is the shared long-term memory store (keep SQLite fallback).
- **REQ-FLEET-104:** Heartbeat loop runs every N minutes and posts structured status.

### P2 (Quality + Safety)

- **REQ-FLEET-201:** Golden image / one-command spawn documented and reproducible.
- **REQ-FLEET-202:** Audited recovery actions (every restart has reason + timestamp + initiator).
- **REQ-FLEET-203:** Tailscale mesh hardened (ACLs/tags, stable names, documented node map).

---

## 6. Acceptance Criteria (Done State)

- **AC-1:** `docker ps` on KVM4 shows Friday/Matt/Jarvis/Redis healthy for 60+ minutes with no restarts due to healthcheck flapping.
- **AC-2:** Jarvis answers market questions without consuming Anthropic auth/quota (xAI only).
- **AC-3:** Restart KVM4 host → bots come back with personality intact (no empty identity files).
- **AC-4:** KVM8 bots run stable under load; no OOM crashes in last 24h; treasury key material recovered + backed up.
- **AC-5:** Yoda can detect Friday down and restart it over Tailscale.
- **AC-6:** MSW can query NotebookLM and compile grounded answers into markdown artifacts.

---

## 7. Rollout Plan

1. **Phase A (KVM4):** stabilize core bots, persistence, healthcheck tuning, shared memory.
2. **Phase B (MSW/TARS):** make NotebookLM + Firefox automation the default ops lane.
3. **Phase C (KVM8):** stabilize muscle node, recover treasury key, add OOM + watchdog protections.
4. **Phase D (Mesh):** harden Tailscale + Yoda watchdog, add fleet heartbeat and incident logs.

---

## 8. References

- `reports/telegram_mega_fixit.md` (48h Telegram synthesis)
- `.ralph-playbook/` (Ralph loop mechanics)
- `C:\Users\lucid\OneDrive\Desktop\backup-matt-bot-2026-02-04.tar.gz` (golden backup reference)

