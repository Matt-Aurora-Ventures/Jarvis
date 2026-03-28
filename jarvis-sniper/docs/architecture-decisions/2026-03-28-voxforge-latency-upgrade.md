# ADR: VoxForge Latency Upgrade — WebSocket Token Discovery

**Date:** 2026-03-28
**Status:** Implemented
**Author:** Matt Haynes

## Context

Jarvis Sniper (www.jarvislife.cloud) relied on 100% REST polling for token discovery, P&L tracking, and transaction confirmation. Token discovery via DexScreener polling had ~30s latency. A conversation with VoxForge (developer of roostar.vercel.app) revealed that competitive snipers use WebSocket-based real-time feeds for sub-second detection.

### Budget Constraint

Helius Developer tier at $49/mo. This EXCLUDES:
- LaserStream gRPC mainnet (Professional $999/mo only)
- Enhanced WebSockets (Professional $999/mo only)

The original design docs (`docs/plans/2026-03-28-jarvis-sniper-latency-upgrade-design.md` and `*-plan.md`) were built on these inaccessible features and were scrapped.

## Decision

Use **free and standard-tier WebSocket methods** that work within the $49/mo budget:

| Method | Cost | Latency | Purpose |
|--------|------|---------|---------|
| PumpPortal WSS (`wss://pumpportal.fun/api/data`) | Free | ~1-3s | Primary token discovery |
| Helius `logsSubscribe` (standard Solana WSS) | Included in $49/mo | ~50-150ms | Secondary token discovery |
| Solana `signatureSubscribe` (standard WSS) | Included in $49/mo | ~400ms | Transaction confirmation |

### What We Rejected

- **LaserStream gRPC / Enhanced WebSockets:** Requires $999/mo Professional tier.
- **Standalone data service + Redis + SSE + Docker:** Over-engineered for a browser-based Next.js app on Firebase.
- **UltraTrade SDK:** Closed-source, wallet-connected = supply chain risk. Deferred.
- **Vite migration:** Too large, mid-KIN/Brain work.

## Architecture

Everything stays client-side in the Next.js app deployed on Firebase. No new infrastructure.

```
Browser (Next.js on Firebase)
├── PumpPortal WSS ← subscribeNewToken (FREE, primary)
├── Helius WSS ← logsSubscribe + signatureSubscribe ($49/mo tier)
├── DexScreener REST ← 15s poll (fallback enrichment, reduced from 30s)
├── Jupiter lite API ← 1.5s price poll (unchanged)
└── Existing API routes ← /api/graduations, /api/bags/swap, etc.
```

Feature-flagged via `NEXT_PUBLIC_DATA_SOURCE`:
- `pumpportal` (default): PumpPortal WebSocket for token discovery
- `logs-subscribe`: Helius logsSubscribe for token discovery
- `poll-only`: Existing REST polling only

## Implementation

### New Files
- `src/hooks/usePumpPortalStream.ts` — PumpPortal WSS hook with auto-reconnect
- `src/hooks/useLogsSubscribe.ts` — Helius logsSubscribe hook with mint extraction
- `src/lib/data-source-config.ts` — Feature flag configuration
- `src/lib/simulate.ts` — Pre-flight transaction simulation
- `src/lib/jito-tip.ts` — Dynamic Jito tip floor (60s cached)

### Modified Files
- `src/components/providers/SniperAutomationOrchestrator.tsx` — Wire hooks, reduce poll interval
- `src/lib/tx-confirmation.ts` — Race signatureSubscribe against HTTP polling
- `src/lib/bags-trading.ts` — Add pre-flight simulation before signing
- `src/lib/jito-bundles.ts` — Re-export dynamic tip floor
- `.env.example` — New env vars

## Expected Impact

| Metric | Before | After |
|--------|--------|-------|
| Token discovery latency | ~30s (DexScreener poll) | ~1-3s (PumpPortal WSS) |
| Tx confirmation latency | ~2.5s (HTTP poll) | ~400ms (signatureSubscribe race) |
| Failed tx cost | Full gas | Caught by pre-flight simulation |
| Jito tips | Hardcoded 0.001 SOL | Dynamic from tip floor API |
| REST poll interval | 30s | 15s (fallback when WSS active) |

## Risks

- PumpPortal WebSocket is a free third-party service — could go down or change API.
  Mitigated by feature flag + REST polling fallback.
- Helius `logsSubscribe` mint extraction depends on PumpFun program data layout.
  If layout changes, the hook fails silently and REST polling continues.
- `signatureSubscribe` adds a WebSocket per transaction.
  Mitigated by timeout + cleanup on confirmation/failure.
