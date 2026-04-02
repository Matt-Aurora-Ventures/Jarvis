# Jarvis Sniper — Project Status, Architecture & Testing Plan

**Last Updated:** 2026-02-08
**Branch:** `trading-terminal-redesign`
**Build Status:** Clean (`tsc --noEmit` + `next build` pass)

---

## 1. Product Intent

Jarvis Sniper is a **public-facing Solana token sniping terminal** that allows any user to:

1. Connect their Phantom wallet
2. Discover newly graduated/boosted tokens scored 0-100
3. Snipe tokens with one click (manual) or automatically (auto-snipe mode)
4. Have positions monitored 24/7 with automated stop-loss and take-profit execution
5. View real-time P&L, charts, and execution history

**Target audience:** Solana traders who want fast entry into new meme coins with professional risk management — similar to BullX, Photon, or GMGN but with Bags.fm partner integration for referral revenue.

---

## 2. Non-Negotiable Requirements ("The Musts")

### 2.1 Risk Management — MUST work

| Requirement | Status | Implementation |
|-------------|--------|----------------|
| Stop-loss MUST execute automatically | PARTIAL | Browser: `useAutomatedRiskManagement.ts` (2s loop). Server: `scripts/risk-worker.ts` (3s loop) |
| Take-profit MUST execute automatically | PARTIAL | Same as above |
| SL/TP MUST work when browser is closed | BUILT | `risk-worker.ts` reads `.positions.json`, fetches Jupiter prices, signs sells with `SNIPER_PRIVATE_KEY` |
| SL/TP MUST work when app is closed | BUILT | Risk worker runs as standalone Node.js process |
| Per-token adaptive SL/TP based on score/liq/volume | DONE | `getRecommendedSlTp()` in `useSniperStore.ts:69-113` |
| Trailing stops | NOT IMPLEMENTED | `trailingStopPct` exists in config but no execution logic |
| Users MUST NOT lose funds due to broken SL/TP | NEEDS TESTING | End-to-end SL/TP test with real positions required |

### 2.2 Bags.fm API — MUST use for buys

| Requirement | Status | Implementation |
|-------------|--------|----------------|
| All buys MUST route through Bags.fm SDK | DONE | `/api/bags/swap/route.ts` — server-side proxy using `@bagsfm/bags-sdk` |
| Partner key MUST be passed for referral revenue | DONE | `referralAccount: new PublicKey(PARTNER_KEY)` in swap route |
| CORS MUST be handled (Bags API blocks browser origins) | DONE | Server-side proxy at `/api/bags/swap` bypasses CORS |
| Priority fees MUST be injected to prevent timeouts | DONE | `injectPriorityFee()` decompiles tx, adds `ComputeBudgetProgram.setComputeUnitPrice` (200k microLamports default) |
| Jupiter v6 fallback for sells (no CORS issues) | DONE | `bags-trading.ts` — sells go direct to Jupiter from client |

### 2.3 Win/Loss Performance — MUST hit targets

| Requirement | Status | Implementation |
|-------------|--------|----------------|
| Algorithm MUST achieve 60%+ win rate | NOT VERIFIED | No backtest data from production yet |
| Scoring algorithm MUST be easy to adjust | DONE | All params in `useSniperStore.ts` config: `stopLossPct`, `takeProfitPct`, `minScore`, `maxPositionSol`, etc. |
| Best config MUST be loadable from file | DONE | `/api/best-ever/route.ts` loads `BEST_EVER.json`, `loadBestEver()` applies it |
| Per-token SL/TP MUST adapt to liquidity/volume/momentum | DONE | `getRecommendedSlTp()` — 4 tiers + 3 adjustment factors |
| Historical backtest MUST be runnable | PARTIAL | Backtest infrastructure exists but produces 0 trades (buy/sell ratio filter bug — see plan file) |
| Algorithm parameters MUST be tunable without code changes | DONE | SniperControls UI exposes all config fields |

### 2.4 Position Persistence — MUST survive

| Requirement | Status | Implementation |
|-------------|--------|----------------|
| Positions MUST survive page reload | DONE | Zustand `persist` middleware → `localStorage` |
| Positions MUST survive browser close | DONE | `savePositionToServer()` → `/api/positions` → `.positions.json` |
| Positions MUST be readable by risk worker | DONE | Risk worker reads same `.positions.json` file |
| Execution log MUST persist (last 50 entries) | DONE | Zustand persist `partialize` includes `executionLog.slice(0, 50)` |
| Stats (PnL, W/L, trades) MUST persist | DONE | `totalPnl`, `winCount`, `lossCount`, `totalTrades` in persist |

### 2.5 Security — MUST be safe for public users

| Requirement | Status | Implementation |
|-------------|--------|----------------|
| Private keys MUST never touch the browser | PARTIAL | Buys: Phantom signs (no key exposure). Risk worker: uses `SNIPER_PRIVATE_KEY` server-side only |
| API keys MUST never be exposed to client | DONE | Bags API key is server-only (`BAGS_API_KEY`) and used only in `/api/bags/*` routes + risk worker |
| XSS protection | NOT TESTED | No sanitization audit done |
| CSRF protection | NOT TESTED | Next.js API routes have no CSRF tokens |
| Rate limiting on API routes | NOT IMPLEMENTED | `/api/bags/swap`, `/api/positions` have no rate limits |
| Input validation on API routes | PARTIAL | Basic null checks but no schema validation (zod) |
| Wallet authorization MUST be verified | DONE | On-chain memo transaction required before any trades |
| Position file MUST not be publicly accessible | DONE | `.positions.json` in project root, not in `/public` |
| Penetration testing | NOT DONE | No security audit performed |

### 2.6 User Experience — MUST work

| Requirement | Status | Implementation |
|-------------|--------|----------------|
| Positions MUST show on chart | PARTIAL | `TokenChart.tsx` shows chart for selected token but no position overlay (entry price line, SL/TP lines) |
| Real-time P&L MUST update | DONE | `usePnlTracker.ts` polls DexScreener every 3s |
| Failed transactions MUST not lock funds | DONE | Failed snipes un-mark `snipedMints` and refund budget |
| Error states MUST be visible | DONE | `ExecutionLog.tsx` shows all errors with timestamps |

---

## 3. System Architecture

### 3.1 File Map

```
jarvis-sniper/
├── .env.local                          # API keys, RPC endpoint
├── package.json                        # Dependencies + scripts
├── next.config.ts                      # Next.js 16 + Turbopack
├── tsconfig.json                       # TypeScript config
├── PROJECT_STATUS.md                   # THIS FILE
├── NOTEBOOK_LM_CONTEXT.md             # Detailed project context for NotebookLM
│
├── scripts/
│   └── risk-worker.ts                  # 24/7 SL/TP monitor (standalone Node.js)
│
└── src/
    ├── app/
    │   ├── layout.tsx                  # Root layout, fonts, WalletProvider
    │   ├── page.tsx                    # Main 3-column dashboard
    │   ├── globals.css                 # Tailwind v4 dark terminal theme
    │   └── api/
    │       ├── graduations/route.ts    # DexScreener scored token feed
    │       ├── best-ever/route.ts      # Load optimal config from file
    │       ├── bags/
    │       │   ├── quote/route.ts      # Bags.fm quote proxy (server-side)
    │       │   └── swap/route.ts       # Bags.fm swap proxy + priority fees + partner key
    │       └── positions/route.ts      # Position CRUD for risk worker
    │
    ├── components/
    │   ├── StatusBar.tsx               # Top nav: wallet, stats, mode badge
    │   ├── GraduationFeed.tsx          # LEFT: token scanner + auto-snipe
    │   ├── PerformanceSummary.tsx       # CENTER TOP: 6-stat grid
    │   ├── TokenChart.tsx              # CENTER: multi-provider chart embeds
    │   ├── ExecutionLog.tsx            # CENTER BOTTOM: event log
    │   ├── SniperControls.tsx          # RIGHT TOP: budget, quick snipe, config
    │   ├── PositionsPanel.tsx          # RIGHT BOTTOM: open positions + history
    │   └── providers/
    │       └── WalletProvider.tsx      # Buffer polyfill + Phantom provider
    │
    ├── hooks/
    │   ├── usePhantomWallet.tsx        # Direct Phantom wallet integration
    │   ├── useSnipeExecutor.ts         # Swap execution orchestrator
    │   ├── usePnlTracker.ts            # Real-time price polling (3s)
    │   └── useAutomatedRiskManagement.ts # Browser-side SL/TP monitor (2s)
    │
    ├── stores/
    │   └── useSniperStore.ts           # Zustand state + localStorage persist
    │
    └── lib/
        ├── bags-api.ts                 # DexScreener scoring (0-100)
        └── bags-trading.ts             # Swap execution: Bags proxy (buys) + Jupiter (sells)
```

### 3.2 Data Flow

```
Token Discovery:
  DexScreener Boosted API → /api/graduations → calculateScore() → GraduationFeed

Buy Execution:
  User clicks Snipe → useSnipeExecutor → /api/bags/swap (server) →
    BagsSDK.getQuote() → BagsSDK.createSwapTransaction() →
    injectPriorityFee() → base64 tx back to client →
    Phantom signs → sendRawTransaction → confirmTransaction →
    addPosition() + savePositionToServer()

Sell Execution (Browser SL/TP):
  useAutomatedRiskManagement (2s loop) → check pnlPercent vs SL/TP →
    getSellQuote() via Jupiter v6 → executeSwapFromQuote() →
    Phantom signs → send → confirm → closePosition()

Sell Execution (Server Risk Worker):
  risk-worker.ts (3s loop) → read .positions.json →
    fetchPrices() via Jupiter Price API → check SL/TP →
    Jupiter quote → Jupiter swap tx → sign with SNIPER_PRIVATE_KEY →
    sendRawTransaction → confirm → update .positions.json

Price Tracking:
  usePnlTracker (3s loop) → DexScreener tokens API → updatePrices() →
    recalculate pnlPercent + pnlSol for all open positions
```

### 3.3 Key Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| next | 16.1.6 | App framework + API routes |
| react | 19.2.3 | UI rendering |
| @solana/web3.js | ^1.98.0 | Solana transactions |
| @bagsfm/bags-sdk | ^1.2.7 | Bags.fm swap API |
| zustand | ^5.0.11 | State management + persist |
| tailwindcss | ^4 | Styling |
| framer-motion | ^12.31.1 | Animations |
| lucide-react | ^0.563.0 | Icons |

---

## 4. What Has Been Proven On-Chain

| Event | Token | Amount | TX Hash | Status |
|-------|-------|--------|---------|--------|
| BUY | TULSA | 5,794.99 tokens for 0.030 SOL | Confirmed via Helius | Success |
| BUY | $FU | 63,909.72 tokens for 0.030 SOL | Confirmed via Helius | Success |
| BUY | $MAD | 0.030 SOL attempted | Empty on Helius (never landed) | Failed — timeout, no SOL lost |

**Root cause of $MAD failure:** Insufficient priority fees during network congestion. **Fixed** with `injectPriorityFee()` (200k microLamports default).

---

## 5. What's Built vs What Needs Work

### DONE (Verified Working)

- [x] Token discovery via DexScreener boosted feed
- [x] Multi-factor scoring 0-100 (liquidity, volume, socials, momentum, age)
- [x] Real on-chain buys via Bags.fm SDK + partner key
- [x] Priority fee injection to prevent timeouts
- [x] Phantom wallet integration (connect/disconnect/sign)
- [x] Budget authorization via on-chain memo
- [x] Real-time P&L tracking (3s DexScreener polling)
- [x] Browser-side SL/TP monitoring (2s loop)
- [x] Per-token adaptive SL/TP recommendations
- [x] Position persistence (Zustand localStorage + server `.positions.json`)
- [x] Execution event log
- [x] Performance stats (W/L, PnL, win rate)
- [x] Multi-provider chart embeds (Birdeye, DexScreener, GeckoTerminal)
- [x] Quick snipe (paste any mint address)
- [x] Auto-snipe mode (auto-buy tokens above min score)
- [x] Jito MEV bundle submission (3-endpoint failover)
- [x] Server-side risk worker script (`scripts/risk-worker.ts`)
- [x] TypeScript compiles clean, Next.js builds clean

### NOT YET DONE

- [ ] **Position overlay on charts** — entry price line, SL/TP lines on chart
- [ ] **Trailing stop execution** — config field exists but no logic
- [ ] **Test suite** — ZERO test files exist
- [ ] **Security audit / pen test** — not done
- [ ] **Rate limiting** on API routes
- [ ] **Input validation** with zod schemas
- [ ] **Error boundaries** in React
- [ ] **Toast notifications** (sonner installed but unused)
- [ ] **Backtest fix** — buy/sell ratio filter rejects all tokens (0 trades)
- [ ] **Win rate verification** — no production data yet
- [ ] **SNIPER_PRIVATE_KEY setup** — user needs to add to `.env.local`
- [ ] **Transaction simulation** before signing (catch failures early)
- [ ] **Slippage warnings** when impact > 2%
- [ ] **Mobile responsive** layout
- [ ] **Multi-wallet support** (currently single Phantom only)

---

## 6. Existing Documentation

| Document | Location | Content |
|----------|----------|---------|
| Project Context (NotebookLM) | `jarvis-sniper/NOTEBOOK_LM_CONTEXT.md` | 425 lines — complete architecture, data flows, API integrations, design system, resolved issues, future improvements |
| This Status Doc | `jarvis-sniper/PROJECT_STATUS.md` | Architecture, musts, testing plan, file map |
| Bags Integration Guide | `docs/bags-integration.md` | Python + JS bags.fm integration, partner fees, scoring |
| Sentiment ADR | `docs/adr/ADR-001-grok-sentiment-analysis.md` | Why Grok over Claude for sentiment ($10/day vs $300/day) |
| Dashboard Architecture | `docs/architecture/DASHBOARD_ARCHITECTURE.md` | Web terminal architecture |
| Master Task Tracking | `docs/ULTIMATE_MASTER_GSD_JAN_31_2026.md` | 120+ tasks, priorities, execution phases |
| Backtest Plan | `.claude/plans/dynamic-enchanting-leaf.md` | Fix zero-trade backtest, algorithm tuning, genetic optimizer |
| Main CLAUDE.md | `CLAUDE.md` | Repo-wide context, env vars, running instructions |

---

## 7. Testing Plan

### 7.1 Unit Tests (PRIORITY: HIGH — 0 exist today)

| Test File to Create | What It Tests | Critical? |
|---------------------|---------------|-----------|
| `src/lib/__tests__/bags-api.test.ts` | `calculateScore()` — scoring formula, tier boundaries, edge cases (0 liquidity, missing fields) | YES |
| `src/lib/__tests__/bags-trading.test.ts` | `getQuote()` waterfall, `executeSwap()` error handling, `getSellQuote()`, `savePositionToServer()` | YES |
| `src/stores/__tests__/useSniperStore.test.ts` | `getRecommendedSlTp()` — all 4 tiers, liquidity/momentum/volume adjustments, clamping. Position CRUD. Budget math. | YES |
| `src/hooks/__tests__/useSnipeExecutor.test.ts` | Pre-flight guards (wallet, budget, capacity, duplicates), snipe flow, error recovery | YES |
| `src/app/api/__tests__/positions.test.ts` | GET/POST/DELETE position CRUD, file I/O, concurrent writes | YES |
| `src/app/api/__tests__/swap.test.ts` | Priority fee injection, partner key, error responses | YES |
| `scripts/__tests__/risk-worker.test.ts` | SL/TP trigger logic, price fetch, position close | YES |

### 7.2 Integration Tests (PRIORITY: HIGH)

| Test | What It Validates |
|------|-------------------|
| **Buy flow E2E** | Quote → swap tx → sign → confirm → position created → saved to server |
| **Sell flow E2E** | SL/TP triggered → sell quote → sign → confirm → position closed → stats updated |
| **Risk worker E2E** | Position in file → price drop → SL triggered → sell executed → file updated |
| **Persistence roundtrip** | Create position → reload page → position still there with correct data |
| **Budget accounting** | Authorize → snipe → budget decremented → close → budget refunded |
| **Duplicate prevention** | Snipe token A → token A appears again → NOT sniped twice |

### 7.3 Security Tests (PRIORITY: CRITICAL)

| Test | What It Validates | Tool |
|------|-------------------|------|
| **API key exposure** | `BAGS_API_KEY` not in client bundle | `next build` + inspect `.next/static` |
| **XSS in token names** | Malicious `<script>` in token symbol/name doesn't execute | Manual + automated |
| **CSRF on /api/bags/swap** | POST endpoint can't be called from external origins | Check `Origin`/`Referer` headers |
| **Rate limiting** | `/api/bags/swap` can't be spammed (DDoS) | Load test |
| **Input validation** | Malformed mint addresses, negative amounts, huge slippage | Fuzz test |
| **Private key isolation** | `SNIPER_PRIVATE_KEY` never appears in logs, responses, or client code | Grep + audit |
| **Position file access** | `.positions.json` not accessible via HTTP | Request `/.positions.json` |
| **SQL/NoSQL injection** | N/A (no database) but validate all API body parsing | — |
| **Wallet impersonation** | Can user A close user B's positions? | Multi-wallet test |
| **Transaction replay** | Signed tx can't be replayed after SL/TP close | Solana nonce check |

### 7.4 Performance Tests (PRIORITY: MEDIUM)

| Test | What It Validates |
|------|-------------------|
| **Price polling under load** | 10+ open positions, 3s DexScreener polling doesn't lag UI |
| **SL/TP reaction time** | Time from price crossing threshold to sell tx submitted (target: <5s) |
| **Concurrent snipes** | 3 tokens graduate simultaneously, all sniped without race conditions |
| **Risk worker memory** | Long-running worker doesn't leak memory over 24h+ |
| **Large position file** | 100+ positions in `.positions.json` doesn't slow reads |

### 7.5 Algorithm Validation (PRIORITY: HIGH)

| Test | What It Validates |
|------|-------------------|
| **Backtest produces trades** | Fix buy/sell ratio filter (plan file step 1) → >0 trades |
| **Score distribution** | Run against 1000 tokens → healthy bell curve, not all 0 or all 100 |
| **SL/TP adaptation** | High-score tokens get tighter SL, wider TP. Low-score get wider SL, shorter TP |
| **Win rate tracking** | After 50+ trades, verify win rate calculation matches manual count |
| **Genetic optimizer** | Self-improver produces configs that beat default on historical data |
| **Edge cases** | 0 liquidity, $0 price, missing socials, expired boost — no crashes |

---

## 8. Environment Variables

```env
# Required — currently set
NEXT_PUBLIC_SOLANA_RPC=https://mainnet.helius-rpc.com/?api-key=<key>
BAGS_API_KEY=bags_prod_<key>
# Optional referral / fee-share account (public key)
BAGS_REFERRAL_ACCOUNT=7jxnA3V5RbkuRpM1iP23i2eD37SqfrqNgoTU4UoB9Mdr

# Required for risk worker — NOT YET SET
SNIPER_PRIVATE_KEY=<base58 private key from dedicated trading wallet>

# Optional
JITO_TIP_LAMPORTS=10000  # Jito tip amount (not yet configurable)
```

---

## 9. How to Run

```bash
# Development server (port 3001)
cd jarvis-sniper && npm run dev

# Production build
npm run build && npm start

# 24/7 Risk Worker (separate terminal)
npm run risk-worker

# TypeScript check
npx tsc --noEmit
```

---

## 10. Related Systems

| System | Location | Relationship |
|--------|----------|-------------|
| **jarvis-web-terminal** | `jarvis-web-terminal/` | Separate multi-page trading terminal with sentiment dashboard, broader feature set |
| **Python trading bots** | `bots/treasury/` | Treasury trader using Jupiter DEX, separate position management |
| **Telegram bot** | `tg_bot/` | `/demo` command mirrors trading UI, separate position system |
| **Bags Intel** | `bots/bags_intel/` | Python-based bags.fm graduation monitoring with Telegram reports |
| **Sentiment Engine** | `core/x_sentiment.py` | Grok-powered sentiment scoring used across all systems |
| **Web Trading UI** | `web/trading_web.py` | Flask-based trading UI on port 5001 |

---

## 11. Next Steps (Priority Order)

1. **Fix backtest** — buy/sell ratio filter producing 0 trades (see plan file)
2. **Write core unit tests** — `bags-api.test.ts`, `useSniperStore.test.ts`, `risk-worker.test.ts`
3. **Position overlay on charts** — show entry price, SL line, TP line on TokenChart
4. **Security hardening** — move API key to server-only env, add rate limiting, input validation
5. **Trailing stop implementation** — config field exists, needs execution logic
6. **Pen test** — XSS, CSRF, API abuse, wallet impersonation
7. **Production backtest** — 50+ real trades to verify win rate
8. **Risk worker deployment** — systemd service or PM2 for always-on monitoring
9. **Add SNIPER_PRIVATE_KEY** — dedicated trading wallet for risk worker auto-sells
10. **Mobile responsive** — current layout is desktop-only 3-column grid
