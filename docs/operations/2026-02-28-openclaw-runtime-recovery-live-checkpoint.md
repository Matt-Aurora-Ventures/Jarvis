# 2026-02-28 OpenClaw Runtime Recovery Live Checkpoint

## Scope
- Validate live Mission Control/API status.
- Restore unresponsive OpenClaw bot runtime.
- Remove known deploy blockers (`stable-20260220` image pull failures).
- Verify Friday/Arsenal runtime behavior after recovery actions.

## Live Environment
- Host: VPS `1302498`
- Mission Control: `http://76.13.106.100:8100`
- Bot projects:
  - `openclaw-arsenal`
  - `openclaw-edith`
  - `openclaw-jocasta`
  - `openclaw-ydy8`

## Actions Executed
1. Verified Mission Control health endpoints:
   - `/healthz` -> `200`
   - `/api/v1/health` -> `200`
2. Cleared Telegram webhooks for bot tokens and restarted OpenClaw projects.
3. Pulled live logs and confirmed recurring blockers:
   - `ghcr.io/hostinger/hvps-openclaw:stable-20260220` pull failures
   - repeated `getUpdates ... 409 conflict`
   - security warnings on control-ui flags
4. Canary-updated `openclaw-arsenal` to `ghcr.io/hostinger/hvps-openclaw:latest`.
5. First canary boot failed due legacy persisted config key incompatibility.
6. Recovered canary by rotating Arsenal data volume to a fresh path and redeploying:
   - service recovered to healthy state on `latest`.
7. Applied same clean-state migration to Friday runtime (`openclaw-ydy8`):
   - moved to `latest`
   - forced `OPENCLAW_GATEWAY_BIND=localhost`
   - fresh data path (`data_v2`)
   - confirmed active model is `anthropic/claude-opus-4-6`.

## Current State (post-canary)
- `openclaw-arsenal`: `running`, `healthy`, image `latest`
- `openclaw-edith`: `running`, `healthy`, image `stable-20260220`
- `openclaw-jocasta`: `running`, `healthy`, image `stable-20260220`
- `openclaw-ydy8`: `running`, `healthy`, image `latest`
- Mission Control stack: healthy

## Observed Gaps Still Open
1. Telegram long-poll conflict still appears intermittently (`409 conflict`) even with one healthy container per project.
2. OpenClaw runtime still emits control-ui security warnings for unsafe flags.
3. WhatsApp health-monitor churn remains active and noisy.
4. Arsenal canary on `latest` did not honor Codex as active runtime model in this environment.

## Immediate Next Steps
1. Align all bot projects to a single known-good image/version and migrate legacy config keys safely.
2. Force-disable WhatsApp plugin path where not used.
3. Enforce one-poller-per-token at runtime level and confirm no external duplicate pollers.
4. Reconcile model/provider credentials/runtime mapping so Arsenal can run `openai-codex/gpt-5.3-codex` deterministically.
5. Add a 30-minute soak gate with explicit pass/fail criteria before additional production changes.
