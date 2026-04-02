# Autonomy Runtime Runbook (Sniper)

## What Autonomy Can and Cannot Do
- Autonomy can apply bounded runtime parameter overrides through `strategy-overrides` snapshots.
- Autonomy cannot mutate source code, rewrite files, or deploy code behind the scenes.
- Override bounds are enforced in `src/lib/autonomy/override-policy.ts` against allowed fields and delta limits.

## Runtime Truth Endpoints
- `GET /api/autonomy/status`
  - `autonomyEnabled`
  - `applyOverridesEnabled`
  - `xaiConfigured`
  - `latestCycleId`
  - `latestReasonCode`
  - `overrideVersion`
  - `overrideUpdatedAt`
- `GET /api/strategy-overrides`
  - `version`
  - `updatedAt`
  - `cycleId`
  - `signature`
  - `patches`

## Operator Checks Before Trusting Autonomy
1. Verify `AUTONOMY_ENABLED=true`.
2. Verify `AUTONOMY_APPLY_OVERRIDES=true`.
3. Verify `XAI_API_KEY` is configured.
4. Confirm `latestCycleId` and `latestReasonCode` are recent and expected.
5. Confirm override snapshot `version` and `updatedAt` changed when a new cycle is expected.
6. Verify snapshot `signature` exists and is stable for the fetched snapshot payload.

## Practical Interpretation
- If `autonomyEnabled=false` or `applyOverridesEnabled=false`, no runtime strategy override should be applied.
- If `xaiConfigured=false`, autonomy may still run limited non-LLM logic, but no xAI-driven decision path should be assumed.
- If `latestCycleId` is stale, treat autonomy decisions as stale.
- If snapshot fields are unchanged and signature is unchanged, no new override has been applied.
