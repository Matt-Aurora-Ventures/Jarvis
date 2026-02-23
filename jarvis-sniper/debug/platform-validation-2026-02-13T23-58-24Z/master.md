# Platform Validation Report — kr8tiv.web.app

GeneratedAt: 2026-02-14T00:16:20.8750888-06:00
CloudRun service: ssrkr8tiv (us-central1)
LatestReadyRevision: ssrkr8tiv-00083-rb8

## Current Runtime Readiness (/api/health)

- status: ok
- rpc: configured=True source=helius_gatekeeper
- bagsApiKey: True
- autonomy: enabled=True applyOverrides=False
- xai: configured=True batchEnabled=True modelPolicy=grok-4-1-fast-reasoning

## Key Findings

1. **Grok/xAI is NOT producing decisions yet**: the xAI API key in Secret Manager currently returns "Incorrect API key provided" (xAI responds HTTP 400).
2. Autonomy is enabled but **audit-only apply is enforced** (`AUTONOMY_APPLY_OVERRIDES=false`). Even when xAI works, no runtime strategy overrides will be applied until you flip that flag.
3. **Portfolio endpoint reliability is the biggest live failure rate**: last 24h shows 123x HTTP 502 out of 1022 requests (~12%).
4. **Session exports do not include full tx signatures**, so strict UI-claim vs on-chain reconciliation is currently blocked.
5. Session wallet snapshot shows **non-zero token accounts persist**, matching the report that sells are not closing token accounts to reclaim rent.

## Evidence Artifacts

- `health.json`
- `autonomy-latest.json`
- `cloud-request-stats-24h.md`
- `cloud-request-stats-168h.md`
- `session-summaries.md`
- `chain-reconcile-2026-02-13T12-29-45.md`

## Immediate Fix Backlog (Ordered)

1. **Rotate xAI key**: update Secret Manager `jarvis-xai-runtime-key` to a valid key, then the next hourly cycle will submit a batch and produce decision artifacts.
2. **Tx signature observability**: update session export to emit full tx signatures (keep UI short-hash display, but export full hashes).
3. **Close token accounts after sells**: after any successful sell/exit, close emptied token accounts (reclaim rent) and log deterministic results.
4. **Reduce /api/session-wallet/portfolio 502s**: make holdings consensus fail-soft (partial results + diagnostics) rather than throwing 502 for transient provider errors.

