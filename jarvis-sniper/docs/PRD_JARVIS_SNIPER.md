# Jarvis Sniper — Product Requirements Document

**Version:** 1.0
**Date:** 2026-02-09
**Status:** Phase 1 Complete, Phase 2 In Progress

---

## 1. Product Overview

Jarvis Sniper is a real-time Solana token trading terminal that scans, scores, and auto-trades tokens across 5 asset classes: memecoins, xStocks (tokenized equities), prestocks (pre-IPO), indexes, and blue chip Solana tokens. It runs as a Next.js web app with a trading-terminal UI (dark/light mode), connecting to Phantom wallet or ephemeral session wallets for execution.

### Core Value Proposition
- **Multi-asset coverage:** One terminal for memecoins, blue chips, tokenized stocks, and indexes
- **Dynamic scoring:** Real-time scoring based on liquidity, volume, momentum, and market structure
- **Automated execution:** Auto-snipe qualifying tokens with budget controls and circuit breakers
- **Per-asset-class algorithms:** Calibrated SL/TP/trailing-stop for each asset's volatility profile
- **Session export:** Downloadable trading reports for analysis

---

## 2. Asset Classes & Strategies

### 2.1 Memecoins (8 Strategies)

| Preset ID | Name | SL | TP | Trail | Win Rate | Notes |
|-----------|------|----|----|-------|----------|-------|
| `pump_fresh_tight` | PUMP FRESH TIGHT | 20% | 80% | 8% | 88.2% (134T) | V4 backtest champion |
| `insight_j` | INSIGHT-J | 20% | 60% | 8% | 78.6% (14T) | Insight-balanced |
| `hybrid_b` | HYBRID-B | 20% | 60% | 8% | — | Conservative hybrid |
| `momentum` | MOMENTUM | 20% | 60% | 8% | — | Momentum filter |
| `let_it_ride` | LET IT RIDE | 20% | 100% | 5% | 100% (10T) | Max gains |
| `micro_cap_surge` | MICRO CAP SURGE | 45% | 250% | 20% | 76.2% | High-risk, high-reward |
| `genetic_best` | GENETIC BEST | 35% | 200% | 12% | 83.3% (GA) | Genetic optimizer |
| `genetic_v2` | GENETIC V2 | 45% | 207% | 10% | 71.1% (45T) | GA v2 champion |

**Scoring:** V4 safety simulation — 8 factors (liquidity, B/S ratio, vol/liq, holders, momentum, mcap, volume, source). Min score threshold per preset (0-100).

**Data source:** Bags.fm graduation API → DexScreener pair data

### 2.2 Blue Chip Solana (3 Strategies) — NEW

Established tokens with 2+ years on Solana, consistent volume, $200K+ DEX liquidity, Jupiter Strict List verified, non-stablecoin, high enough volatility to trade.

#### Token Registry (17 tokens)

**Tier 1 — Core Ecosystem ($1B+ mcap):**
SOL, JUP, RAY, PYTH, JTO, RNDR, HNT, W

**Tier 2 — DeFi & Infrastructure ($100M-$1B):**
ORCA, MNDE, DRIFT, TENSOR, MOBILE, STEP

**Tier 3 — Established Memes (2yr+):**
BONK, WIF, SAMO

#### Blue Chip Strategies

| Preset ID | Name | SL | TP | Trail | Expected WR | R/R | Description |
|-----------|------|----|----|-------|-------------|-----|-------------|
| `bluechip_mean_revert` | MEAN REVERT | 3% | 8% | 2% | 55-65% | 1.8:1 | Buy oversold blue chips, tight SL |
| `bluechip_trend_follow` | TREND FOLLOW | 5% | 15% | 4% | 45-55% | 2.5:1 | Ride established momentum |
| `bluechip_breakout` | BREAKOUT | 4% | 12% | 3% | 50-60% | 2:1 | High-volume breakout entries |

**Scoring:** `calcBlueChipScore()` — 4 dimensions (each 0-25, total 0-100):
1. Liquidity Health: $50K → $2M+ tiers
2. Volume Activity: Vol/Liq ratio 0.2x → 3x+
3. Price Momentum: 1h magnitude + 24h trend alignment
4. Market Structure: B/S ratio + tier bonus + category bonus + years bonus

**Parameter derivation:**
- SOL avg daily volatility: 4-6% → SL 3-5%
- JUP/RAY: 5-8% → SL 4-6%, TP 8-15%
- BONK/WIF: 8-12% → SL 5-8%, TP 10-20%
- Optimal trailing stop = ~1x ATR (daily volatility)

**Data source:** DexScreener token API → `calcBlueChipScore()` → auto-sort by score

### 2.3 xStocks — Tokenized Equities (2 Strategies)

Tokenized US stocks on Solana (AAPLx, MSFTx, GOOGLx, etc.) via xStocks protocol.

| Preset ID | Name | SL | TP | Trail | Description |
|-----------|------|----|----|-------|-------------|
| `xstock_intraday` | INTRADAY | 1.5% | 3% | 1% | Normal intraday swings |
| `xstock_swing` | SWING | 3% | 8% | 2% | Multi-day momentum |

**Scoring:** `calcEquityScore()` — 4 dimensions (total 0-100):
1. Trading Activity (0-30): Vol/Liq ratio + transaction count
2. Price Momentum (0-30): 1h magnitude + trend consistency + intraday bonus
3. Market Quality (0-20): Liquidity tier + B/S health + spread quality
4. Asset Class Bonus (0-20): INDEX +15, XSTOCK +8-12 (by sector), PRESTOCK +5, COMMODITY +12

**Key:** Mega-cap bonus (+5) for AAPL, MSFT, GOOGL, AMZN, NVDA, META

### 2.4 PreStocks (1 Strategy)

Pre-IPO tokenized equities — higher volatility than established stocks.

| Preset ID | Name | SL | TP | Trail | Description |
|-----------|------|----|----|-------|-------------|
| `prestock_speculative` | SPECULATIVE | 5% | 15% | 3% | Pre-IPO vol adjusted |

### 2.5 Indexes (2 Strategies)

Tokenized index funds (SPYx, QQQx, TQQQx).

| Preset ID | Name | SL | TP | Trail | Description |
|-----------|------|----|----|-------|-------------|
| `index_intraday` | INTRADAY | 0.8% | 1.5% | 0.5% | SPY/QQQ tight scalping |
| `index_leveraged` | TQQQ SWING | 3% | 8% | 2% | 3x leveraged index |

---

## 3. Architecture

### 3.1 Tech Stack
- **Frontend:** Next.js 15 (App Router), React 19, TypeScript
- **State Management:** Zustand v5 with Persist (localStorage)
- **Styling:** Tailwind CSS 4, CSS custom properties (dark/light themes)
- **Wallet:** Solana Wallet Adapter (Phantom) + Session Wallet (ephemeral)
- **Data:** DexScreener API, Bags.fm Graduation API, Jupiter Price API v3
- **Execution:** Bags Swaps (via server-side Bags SDK proxy). Optional Jito relay for landing.
- **Port:** 3001

### 3.2 Key Components

```
jarvis-sniper/
├── src/
│   ├── app/
│   │   ├── api/
│   │   │   ├── bluechips/route.ts    # Blue chip token data API
│   │   │   ├── xstocks/route.ts      # xStock/index/prestock data API
│   │   │   └── graduations/route.ts  # Memecoin graduation data API
│   │   ├── page.tsx                  # Main trading terminal page
│   │   └── layout.tsx                # Root layout with fonts & providers
│   ├── components/
│   │   ├── GraduationFeed.tsx        # Token scanner with auto-snipe
│   │   ├── SniperControls.tsx        # Strategy config, budget, controls
│   │   ├── StatusBar.tsx             # Top bar with links & session export
│   │   ├── EarlyBetaModal.tsx        # Disclaimer modal (every load)
│   │   └── strategy-categories.ts    # Category groupings for dropdown
│   ├── stores/
│   │   └── useSniperStore.ts         # Central state: config, positions, budget
│   ├── hooks/
│   │   ├── useSnipeExecutor.ts       # Swap execution logic (Bags Swaps via /api/bags/*)
│   │   └── useChartData.ts           # Price chart data fetching
│   └── lib/
│       ├── bluechip-data.ts          # Blue chip token registry (17 tokens)
│       ├── xstocks-data.ts           # xStock/prestock/index registry
│       ├── session-export.ts         # Session report download (.md)
│       ├── session-wallet.ts         # Ephemeral wallet (sessionStorage)
│       └── server-cache.ts           # In-memory API cache (30s TTL)
```

### 3.3 Data Flow

```
DexScreener API ──→ API Routes (30s cache) ──→ GraduationFeed
                                                    │
                                                    ├── Token Scanner UI
                                                    ├── Auto-Snipe Logic
                                                    │      │
                                                    │      ├── computeHybridB() filter
                                                    │      ├── Score threshold check
                                                    │      └── snipe() → Bags Swap
                                                    │
                                                    └── Price Chart (selected token)
```

### 3.4 Auto-Snipe Pipeline

1. `GraduationFeed` fetches tokens every 30s from API route
2. API route fetches DexScreener, applies `calcBlueChipScore()` / `calcEquityScore()`, caches 30s
3. Auto-snipe `useEffect` fires when graduations, config, or activePreset changes
4. For each token: `computeHybridB()` filter → score threshold → `snipe()`
5. `snipe()` gets latest config via `useSniperStore.getState()` → `getRecommendedSlTp()` → Bags swap
6. Position tracked with SL/TP/trailing stop, monitored in real-time

---

## 4. Features Implemented (Phase 1)

### 4.1 Dynamic Scoring ✅
- `calcEquityScore()` for xStocks/indexes/prestocks — replaces hardcoded `score: 50`
- `calcBlueChipScore()` for blue chip tokens — 4-dimension scoring
- Both use real-time DexScreener data (volume, liquidity, momentum, B/S ratio)

### 4.2 Blue Chip Token Registry ✅
- 17 curated tokens across 3 tiers
- `BlueChipToken` interface with category, volatility, mcap tier, years on Solana
- API route at `/api/bluechips` with tier/category filtering

### 4.3 Per-Asset SL/TP Calibration ✅
- `getRecommendedSlTp()` branches by source type (xstock, index, prestock, bluechip, memecoin)
- Each branch uses asset-specific volatility ranges
- Adaptive: stronger momentum → wider targets

### 4.4 Strategy Categories ✅
- 5 grouped categories: TOP PERFORMERS, BALANCED, AGGRESSIVE, BLUE CHIP SOLANA, XSTOCK & INDEX
- 16 total strategy presets across all asset classes

### 4.5 Session Export ✅
- `downloadSessionReport()` generates `.md` file with:
  - Summary stats (P&L, positions, wallet)
  - Strategy config (preset, SL/TP, filters)
  - Open & closed positions with P&L
  - Last 100 execution log entries

### 4.6 Strategy Switch Continuity ✅
- `autoSnipe` preserved during `loadPreset()` (spread merge)
- `activePreset` added to auto-snipe dependency array → immediate re-evaluation on switch
- `useSnipeExecutor.snipe()` reads latest config at call time via `getState()`

### 4.7 Disclaimer Modal ✅
- Shows on every page load (no storage persistence)
- Requires user to click "I UNDERSTAND" before trading

---

## 5. Remaining Work (Phase 2)

### 5.1 Ephemeral Wallet Persistence
**Current:** Session wallet uses `sessionStorage` — keypair dies when tab closes. Funds in ephemeral wallet are lost.

**Required:**
- Option A: Move to `localStorage` (persists across sessions, same device)
- Option B: Encrypted keystore backup with user password
- Option C: Auto-sweep ALL funds back to main wallet on page unload (not just excess)

**Recommendation:** Option C (auto-sweep on `beforeunload`) + Option A for convenience. User should never lose funds.

### 5.2 Backtesting Pipeline
**Goal:** Validate all 16 strategies against 5000+ historical trades.

**Requirements:**
- Historical price data for all 17 blue chip tokens (OHLCV, 1h candles, 6+ months)
- Memecoin graduation historical data (already partially available)
- Walk-forward optimization for parameter tuning
- Key metrics: Win Rate, Profit Factor, Max Drawdown, Sharpe Ratio

**Data Sources:**
- DexScreener historical (limited)
- TradingView Screener API (`tvscreener` — github.com/deepentropy/tvscreener) for traditional assets
- Jupiter price history
- Birdeye/Helius for historical on-chain data

### 5.3 tvscreener Integration
**Purpose:** Use TradingView screener data for xStock/index price analysis.

**Implementation:**
- Python backend service using `tvscreener` library
- Real-time stock screener data: volume, price change, RSI, MACD, etc.
- Cross-reference with DexScreener tokenized price for arbitrage signals
- Feed data into `calcEquityScore()` for richer scoring

### 5.4 Advanced Blue Chip Algorithms
**Research basis:** Awesome Systematic Trading repository.

**Potential improvements:**
- **Pairs trading:** Long/short correlated blue chips (e.g., JUP vs RAY)
- **Statistical arbitrage:** Z-score mean reversion on SOL pairs
- **Momentum factor:** Rank blue chips by 1h/24h momentum, long top quartile
- **Volatility regime:** Switch between mean reversion (low vol) and trend following (high vol)
- **Multi-timeframe confirmation:** 5m + 1h + 24h alignment for entries

### 5.5 On-Chain SL/TP
**Current:** Client-side SL/TP monitoring (browser must stay open).

**Target:** Jupiter Trigger Orders for on-chain execution:
- SL/TP persist even if user closes browser
- Reduces missed exits due to network issues
- Already partially implemented (`jupTpOrderKey`, `jupSlOrderKey` fields exist)

### 5.6 Circuit Breaker Enhancements
**Current:**
- 3 consecutive losses → auto-disable auto-snipe
- Daily loss limit tracking

**Improvements:**
- Per-asset-class circuit breakers (memecoin losses shouldn't stop blue chip trading)
- Cooldown period before auto-resume
- Gradual position size reduction after losses

---

## 6. Success Criteria

| Metric | Target | Current |
|--------|--------|---------|
| Memecoin Win Rate | >80% | 88.2% (PUMP_FRESH_TIGHT) |
| Blue Chip Win Rate | >55% | Not yet backtested |
| xStock Win Rate | >50% | Not yet backtested |
| Scoring Accuracy | Dynamic, 10-100 range | ✅ Implemented |
| Auto-Snipe Reliability | No dropped trades on strategy switch | ✅ Fixed |
| Session Export | Download .md report | ✅ Implemented |
| Build Clean | Zero TypeScript errors | ✅ Verified |
| User Fund Safety | No fund loss from wallet issues | Partial (needs auto-sweep) |

---

## 7. Risk Register

| Risk | Impact | Mitigation |
|------|--------|------------|
| DexScreener API rate limit | Scoring stops | 30s cache, batch requests (30/chunk) |
| Jupiter swap failures | Missed entries/exits | Retry logic, on-chain trigger orders |
| Ephemeral wallet fund loss | User loses SOL | Auto-sweep on unload, localStorage backup |
| Blue chip low volatility periods | No qualifying trades | Mean reversion strategy handles flat markets |
| Front-running / MEV | Worse execution price | Jupiter anti-MEV routing, Jito bundles |

---

## 8. Appendix

### A. Dynamic Scoring Functions

**`calcBlueChipScore(token, pair)`** — [bluechips/route.ts](../src/app/api/bluechips/route.ts)
- Liquidity Health (0-25): $50K → $2M+
- Volume Activity (0-25): Vol/Liq 0.2x → 3x+
- Price Momentum (0-25): 1h + 24h trend alignment
- Market Structure (0-25): B/S ratio + tier + category + years

**`calcEquityScore(token, pair)`** — [xstocks/route.ts](../src/app/api/xstocks/route.ts)
- Trading Activity (0-30): Vol/Liq + transaction count
- Price Momentum (0-30): 1h magnitude + trend alignment
- Market Quality (0-20): Liquidity + B/S + spread proxy
- Asset Class Bonus (0-20): INDEX/XSTOCK/PRESTOCK/COMMODITY tiers

### B. Adaptive SL/TP Logic

**`getRecommendedSlTp(grad, mode)`** — [useSniperStore.ts](../src/stores/useSniperStore.ts)

Per-source branching:
- `xstock` → 1.5% SL / 3% TP (standard) or 2% / 5% (strong momentum)
- `index` → 0.8% SL / 1.5% TP (standard) or 3% / 8% (TQQQ leveraged)
- `prestock` → 5% SL / 15% TP
- `bluechip` → 3-5% SL / 8-15% TP (scales with momentum and volume)
- `memecoin` → 15-45% SL / 50-250% TP (strategy-dependent)

### C. Token Registry

**Blue Chips:** 17 tokens — [bluechip-data.ts](../src/lib/bluechip-data.ts)
**xStocks:** ~20 tokens — [xstocks-data.ts](../src/lib/xstocks-data.ts)
**PreStocks:** ~8 tokens — [xstocks-data.ts](../src/lib/xstocks-data.ts)
**Indexes:** ~5 tokens — [xstocks-data.ts](../src/lib/xstocks-data.ts)
