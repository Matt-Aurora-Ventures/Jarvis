# Consensus + Context Degraded-Mode Runbook

## Purpose
Operate Jarvis safely when consensus arena, supermemory hooks, Nosana routes, or mesh sync are partially unavailable.

## Feature Flags (Safe Controls)
- `JARVIS_USE_ARENA=0`: disable consensus fan-out, force local route.
- `JARVIS_USE_NOSANA=0`: disable Nosana heavy-compute route.
- `JARVIS_SUPERMEMORY_HOOKS=0`: disable preRecall/postResponse memory hooks.
- `JARVIS_MODEL_UPGRADER_ENABLED=0`: disable scheduled model upgrader scans.
- `JARVIS_MESH_SYNC_ENABLED=0`: disable encrypted mesh sync listener/publisher.
- `JARVIS_MESH_ATTESTATION_ENABLED=0`: disable on-chain state hash attestation.
- `JARVIS_MESH_AUTO_REGISTER_NODE=1`: auto-register node PDA before retrying commits.

## Startup Capability Report
- Supervisor logs a runtime matrix at startup:
  - `arena` status/reason/fallback
  - `supermemory_hooks` status/reason/fallback
  - `nosana` status/reason/fallback
  - `mesh_sync` status/reason/fallback
  - `mesh_attestation` status/reason/fallback
  - `model_upgrader` status and last scan timestamp
- Health endpoint exposes the same report:
  - `GET /runtime-status`
  - `GET /health` includes `runtime` section

## Graceful Fallback Matrix
- `arena` unavailable: fallback `local_ollama`
- `supermemory_hooks` unavailable: fallback `no_context_injection`
- `nosana` unavailable: fallback `skip_heavy_compute_route`
- `mesh_sync` unavailable: fallback `mesh_sync_bypassed`
- `mesh_attestation` unavailable: fallback `attestation_bypassed`
- If on-chain commit fails due missing node account, enable auto-register and set:
  - `JARVIS_MESH_NODE_ENDPOINT`
  - `JARVIS_MESH_KEYPAIR_PATH`
  - `JARVIS_MESH_PROGRAM_ID`

## Rollback Procedure (Fast)
1. Disable advanced routes immediately:
   - `JARVIS_USE_ARENA=0`
   - `JARVIS_USE_NOSANA=0`
   - `JARVIS_SUPERMEMORY_HOOKS=0`
2. Restart supervisor.
3. If recent model swap caused instability:
   - restore `lifeos/config/jarvis.json` from last known good commit
   - run `jobs/model_upgrader.py` rollback path or set previous model explicitly
4. If container-level rollback needed:
   - retag previous stable image as `latest`
   - redeploy stack with stable tag

## Weekly Upgrader Schedule
- Registered in supervisor scheduler path as cron `0 3 * * *` (3 AM UTC trigger).
- True weekly cadence is enforced by `jobs/model_upgrader.py` internal 7-day guard.

## Post-Deploy Smoke Checks
1. `GET /runtime-status` returns component matrix without 5xx.
2. Run a simple query and confirm local response path when arena disabled.
3. Trigger one chat cycle and confirm no crash when supermemory key/package missing.
4. Run `python jobs/model_upgrader.py --weekly-scan --force` in staging with candidates.
5. Call Nosana route with `JARVIS_USE_NOSANA=0` and confirm graceful `disabled` response.
