# Jarvis Sniper — Trading Terminal

**Created:** 2026-02-09
**Owner:** @lucid
**Status:** Phase 1 Complete, Phase 2 In Progress

---

## What This Is

A real-time Solana token trading terminal that scans, scores, and auto-trades tokens across 5 asset classes: memecoins, xStocks (tokenized equities), prestocks (pre-IPO), indexes, and blue chip Solana tokens. Built as a Next.js 15 web app with a trading-terminal UI.

## Why It Exists

Telegram-based trading (/demo bot) works but lacks:
- Visual token scanning across multiple asset classes
- Backtested strategy presets with performance data
- Real-time scoring with dynamic algorithms
- Multi-asset coverage (stocks, indexes, blue chips alongside memecoins)
- Session-level position tracking with budget controls

The Sniper fills this gap as a dedicated trading terminal for power users who want algorithm-driven execution with full transparency.

## Core Value

**One terminal, multiple asset classes, research-backed algorithms, automated execution with mandatory risk controls.**

The user picks a strategy preset (16 available), sets a budget, and the system auto-trades qualifying tokens with per-asset SL/TP calibration. Every trade has mandatory stop-loss and take-profit.

---

## Current State (Phase 1 Complete)

### What Works
- 16 strategy presets across 5 asset classes
- Dynamic scoring: `calcBlueChipScore()` and `calcEquityScore()`
- 17-token blue chip registry (SOL, JUP, RAY, etc.)
- Per-asset SL/TP calibration via `getRecommendedSlTp()`
- Session export (downloadable .md reports)
- Auto-snipe pipeline: scan → score → filter → execute
- Strategy switch continuity (preserves autoSnipe state)
- Asset-type-aware filters (memecoin filters don't block xStocks)
- 30s swap timeout (AbortController)
- Disclaimer modal on every load

### What Doesn't Work Yet
- Backtesting pipeline (no historical validation)
- Ephemeral wallet persistence (funds lost on tab close)
- tvscreener integration (no real stock data)
- Advanced algorithms (pairs trading, stat arb, regime switching)
- Per-asset circuit breakers
- On-chain SL/TP (Jupiter Trigger Orders)

---

## Technical Context

### Stack
- **Frontend:** Next.js 15 (App Router), React 19, TypeScript
- **State:** Zustand v5 with Persist (localStorage)
- **Styling:** Tailwind CSS 4, dark/light themes
- **Wallet:** Solana Wallet Adapter (Phantom) + Session Wallet (ephemeral)
- **Data:** DexScreener API, Bags.fm Graduation API, Jupiter Price API v3
- **Execution:** Bags Swaps (via server-side Bags SDK proxy). Optional Jito relay for landing.
- **Port:** 3001

### Key Files
| File | Purpose |
|------|---------|
| `src/stores/useSniperStore.ts` | Central state: config, positions, budget, 16 presets |
| `src/hooks/useSnipeExecutor.ts` | Swap execution with asset-type-aware filters |
| `src/components/GraduationFeed.tsx` | Token scanner + auto-snipe logic |
| `src/lib/bluechip-data.ts` | 17-token blue chip registry |
| `src/lib/xstocks-data.ts` | xStock/prestock/index token registry |
| `src/lib/bags-trading.ts` | Bags.fm/Jupiter swap execution |
| `src/lib/session-wallet.ts` | Ephemeral wallet (sessionStorage) |
| `src/app/api/bluechips/route.ts` | Blue chip scoring API |
| `src/app/api/xstocks/route.ts` | Equity scoring API |
| `docs/PRD_JARVIS_SNIPER.md` | Full product requirements document |

### Asset Classes
| Class | Count | Scoring | SL Range | TP Range |
|-------|-------|---------|----------|----------|
| Memecoin | Dynamic | V4 Safety Simulation | 15-45% | 50-250% |
| Blue Chip | 17 tokens | `calcBlueChipScore()` | 3-5% | 8-15% |
| xStock | ~20 tokens | `calcEquityScore()` | 1.5-3% | 3-8% |
| Index | ~5 tokens | `calcEquityScore()` | 0.8-3% | 1.5-8% |
| PreStock | ~8 tokens | `calcEquityScore()` | 5% | 15% |

---

## Constraints

1. **Must maintain existing functionality** — Phase 1 features must keep working
2. **Mandatory TP/SL** — Every trade MUST have stop-loss and take-profit
3. **User fund safety** — Ephemeral wallet must never lose user funds
4. **No server-side state** — All state lives in browser (Zustand + localStorage)
5. **DexScreener rate limits** — 30s cache, batch requests (30/chunk max)
6. **Next.js App Router** — All API routes in `src/app/api/`
7. **TypeScript strict** — Zero type errors in production build

---

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Zustand over Redux | Simpler API, built-in persist, works with React 19 | Working well |
| DexScreener as primary data | Free, comprehensive, covers all Solana tokens | Rate limits manageable |
| Per-asset SL/TP | Different asset classes have different volatility profiles | Prevents over-tight/loose stops |
| 16 strategy presets | Users pick proven configs rather than configuring from scratch | Good UX |
| Session wallet (ephemeral) | Quick trading without Phantom approval popups | Needs persistence fix |
| Client-side execution | No backend server needed, direct Jupiter swaps | Limits to browser-open monitoring |

---

## Requirements

### Validated

- ✓ Dynamic scoring for all asset classes — existing
- ✓ 16 strategy presets across 5 asset classes — existing
- ✓ Blue chip token registry (17 tokens) — existing
- ✓ Per-asset SL/TP calibration — existing
- ✓ Auto-snipe pipeline with budget controls — existing
- ✓ Session export (downloadable reports) — existing
- ✓ Asset-type-aware snipe filters — existing
- ✓ Strategy switch continuity — existing

### Active

- [ ] Backtesting pipeline (validate all 16 strategies, 5000+ trades)
- [ ] tvscreener integration (real stock data for xStocks/indexes)
- [ ] Ephemeral wallet persistence (auto-sweep + localStorage backup)
- [ ] Advanced blue chip algorithms (pairs, stat arb, regime switching)
- [ ] Per-asset circuit breakers (memecoin losses don't stop blue chips)
- [ ] On-chain SL/TP via Jupiter Trigger Orders

### Out of Scope

- Mobile app — web-only terminal
- Multi-chain — Solana only
- Social trading — single-user terminal
- Server-side state — browser-only architecture
- HFT — we operate on 30s scan intervals

---

*Last updated: 2026-02-09 after initialization*
