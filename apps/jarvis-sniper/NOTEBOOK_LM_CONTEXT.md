# Jarvis Sniper — Complete Project Context for NotebookLM

## Project Overview

**Jarvis Sniper** is a standalone Solana token sniping web application. It monitors newly graduated/boosted tokens on Solana DEXes, scores them using multi-factor analysis, and executes real on-chain swap transactions through the user's Phantom wallet. The goal is a professional-grade trading terminal for sniping new Solana meme coins with automated risk management (stop-loss, take-profit, trailing stops).

### What We're Trying to Accomplish

1. **Token Discovery**: Continuously scan DexScreener's boosted token feed to find newly launched Solana tokens with strong fundamentals (liquidity, volume, social presence, buy pressure).

2. **Scoring & Filtering**: Score each token 0-100 using liquidity, volume, social links, boost amount, buy/sell ratio, and price momentum. Only tokens meeting the minimum score threshold are snipe candidates.

3. **Real On-Chain Execution**: When the user clicks "Snipe" (manual or auto-snipe):
   - Get a swap quote via waterfall strategy: Jupiter v6 (primary) -> Bags.fm (fallback) -> Direct Raydium/Meteora (for brand-new tokens)
   - Build a versioned Solana transaction
   - Send to Phantom wallet for user to sign
   - Submit signed transaction to Solana mainnet (with optional Jito MEV bundle)
   - Confirm on-chain and track the position with real tx hash and token amounts

4. **Real-Time P&L Tracking**: `usePnlTracker` hook polls DexScreener every 3 seconds to fetch current token prices and update all open positions with real-time P&L.

5. **Automated Risk Management**: `useAutomatedRiskManagement` hook continuously monitors open positions and automatically triggers sell transactions when SL/TP thresholds are hit.

6. **Budget Authorization System**: Users must set a SOL budget and sign an on-chain memo transaction via Phantom to prove wallet ownership before any sniping can occur. This prevents accidental trades and ensures real wallet control.

7. **Manual Quick Snipe**: Dedicated input field in SniperControls lets users paste any token mint address and snipe it with one click — no need to wait for scanner discovery.

8. **Chart Integration**: Multi-provider chart embeds (Birdeye TV widget default, DexScreener, GeckoTerminal fallbacks) with drag-to-resize and provider switching.

9. **Session Management**: "Reset Record" button clears all stats, positions, and execution history — only available when no open trades exist.

---

## Technology Stack

### Core Framework
| Technology | Version | Purpose |
|-----------|---------|---------|
| **Next.js** | 16.1.6 | React framework with App Router, API routes, Turbopack dev server |
| **React** | 19.2.3 | UI rendering (latest with concurrent features) |
| **TypeScript** | ^5 | Type safety across the entire codebase |
| **Tailwind CSS** | v4 | Utility-first styling with CSS-first configuration (`@theme` blocks, `@source` directives) |
| **Turbopack** | Built into Next.js 16 | Fast dev server bundler (replaces webpack in dev) |

### Solana / Blockchain
| Library | Version | Purpose |
|---------|---------|---------|
| **@solana/web3.js** | ^1.98.0 | Solana SDK — Connection, Transaction, VersionedTransaction, PublicKey, SystemProgram |
| **buffer** | ^6.0.3 | Node.js Buffer polyfill for browser (needed by @solana/web3.js for transaction serialization) |

**IMPORTANT**: We do NOT use `@solana/wallet-adapter-react`'s `ConnectionProvider` or `WalletProvider`. We have a custom `usePhantomWallet` hook that directly interfaces with `window.phantom.solana` (the Phantom browser extension's injected provider).

### State Management
| Library | Version | Purpose |
|---------|---------|---------|
| **Zustand** | ^5.0.11 | Lightweight state store for all app state (config, positions, executions, budget) |

### UI Libraries
| Library | Version | Purpose |
|---------|---------|---------|
| **lucide-react** | ^0.563.0 | Icon library (Crosshair, Shield, Target, Send, Loader2, etc.) |
| **framer-motion** | ^12.31.1 | Animations (installed, available for future use) |

---

## Architecture & File Structure

```
jarvis-sniper/
├── src/
│   ├── app/
│   │   ├── layout.tsx              # Root layout — fonts, PhantomWalletProvider, dark terminal
│   │   ├── page.tsx                # Main dashboard — 3-column grid, P&L tracker, risk mgmt
│   │   ├── globals.css             # Tailwind v4 theme — dark terminal design system
│   │   └── api/
│   │       ├── graduations/route.ts  # Server-side: DexScreener → scored token feed
│   │       └── best-ever/route.ts    # Loads BEST_EVER.json backtester config
│   ├── components/
│   │   ├── StatusBar.tsx           # Top bar — wallet connect, SOL balance
│   │   ├── GraduationFeed.tsx      # LEFT — Token scanner with auto-snipe
│   │   ├── PerformanceSummary.tsx   # CENTER TOP — PnL, win rate, trade count
│   │   ├── TokenChart.tsx          # CENTER — Birdeye/DexScreener/Gecko + drag resize
│   │   ├── ExecutionLog.tsx        # CENTER BOTTOM — Event log
│   │   ├── SniperControls.tsx      # RIGHT TOP — Budget, Quick Snipe, config, auto-snipe
│   │   ├── PositionsPanel.tsx      # RIGHT BOTTOM — Positions + Reset Record button
│   │   └── providers/
│   │       └── WalletProvider.tsx   # Buffer polyfill + PhantomWalletProvider
│   ├── hooks/
│   │   ├── usePhantomWallet.tsx    # Phantom wallet — connect, sign, disconnect
│   │   ├── useSnipeExecutor.ts     # Swap execution — quote → sign → send → confirm
│   │   ├── usePnlTracker.ts       # Real-time P&L — polls DexScreener prices every 3s
│   │   └── useAutomatedRiskManagement.ts  # Auto SL/TP — monitors + sells positions
│   ├── stores/
│   │   └── useSniperStore.ts       # Zustand — state, config, positions, budget, actions
│   └── lib/
│       ├── bags-api.ts             # DexScreener scoring + BagsGraduation types
│       └── bags-trading.ts         # Swap execution — waterfall quotes, Jupiter/Bags/Direct DEX
├── architecture.isoflow.json       # Full architecture diagram (isoflow format)
├── NOTEBOOK_LM_CONTEXT.md          # This file
├── .env.local                      # RPC + Bags.fm API keys
├── package.json
└── tsconfig.json
```

---

## Data Flow

### Token Discovery Flow
```
DexScreener Boosts API ──→ /api/graduations (server route) ──→ Score calculation
   │                              │
   │ Fetch latest boosted         │ Merge boost data + pair data
   │ Solana tokens                │ Score: liquidity + volume + socials + boosts + momentum
   │                              │
   └──────────────────────────────┘
                                  │
                                  ▼
                        GraduationFeed component
                        (polls every 30 seconds)
                              │
                              ▼
                     Token cards with scores + Snipe buttons
                     Auto-snipe if enabled + wallet ready + budget authorized
```

### Swap Execution Flow (THE CRITICAL PATH)
```
User clicks "Snipe" or Quick Snipe or auto-snipe triggers
       │
       ▼
useSnipeExecutor.snipe(grad)
       │
       ├── Guard checks: wallet connected? budget authorized? not already sniped?
       │   not at capacity? sufficient budget? not in-flight?
       │
       ▼
bags-trading.ts → getQuote() [WATERFALL STRATEGY]
       │
       │  1. Jupiter v6: GET https://quote-api.jup.ag/v6/quote
       │     (Standard aggregator, covers Raydium/Orca/Meteora, no auth)
       │
       │  2. Bags.fm fallback: GET https://public-api-v2.bags.fm/api/v1/trade/quote
       │     (Their proxy, uses BAGS_API_KEY for auth)
       │
       │  3. Direct DEX fallback (if dexHint provided):
       │     - Raydium: GET https://transaction-v1.raydium.io/compute/swap-base-in
       │     - Meteora: Bags.fm with API key auth
       │
       ▼
bags-trading.ts → getSwapTransaction()
       │
       │  1. Jupiter: POST https://quote-api.jup.ag/v6/swap
       │     Body: { quoteResponse, userPublicKey, wrapAndUnwrapSol, dynamicComputeUnitLimit }
       │
       │  2. Bags.fm fallback: POST .../trade/swap
       │
       ▼
Deserialize VersionedTransaction from base64
       │
       ▼
Phantom wallet signTransaction(tx) ──→ User approves in Phantom popup
       │
       ▼
Send to Solana:
  ├── If Jito enabled: POST to Jito block engine (3 endpoints with failover)
  └── Else: connection.sendRawTransaction({ skipPreflight: true, maxRetries: 3 })
       │
       ▼
connection.confirmTransaction(txHash, 'confirmed')
       │
       ▼
Create Position in store with real txHash + token amounts
Update budget spent
```

### Real-Time P&L Flow
```
usePnlTracker hook (mounted in page.tsx)
       │
       │ Every 3 seconds:
       │ 1. Collect all open position mints
       │ 2. Batch fetch from DexScreener tokens API
       │ 3. Extract current prices
       │ 4. Call store.updatePrices(priceMap)
       │    → Each position recalculates pnlPercent and pnlSol
       │
       ▼
UI reflects live P&L in PositionsPanel + PerformanceSummary
```

### Automated Risk Management Flow
```
useAutomatedRiskManagement hook (mounted in page.tsx)
       │
       │ Continuously monitors open positions:
       │ 1. Check pnlPercent vs position's recommendedSl / recommendedTp
       │ 2. If SL hit: get sell quote → build tx → sign → send → confirm
       │ 3. If TP hit: same sell flow
       │ 4. Uses setPositionClosing() to lock position during sell
       │ 5. Uses closePosition() to update status + stats + free budget
       │
       │ Uses bags-trading.ts:
       │   - getSellQuote(tokenMint, amountLamports) for Token→SOL quotes
       │   - executeSwapFromQuote() to skip re-quoting
       │
       ▼
Position closed with proper status (tp_hit / sl_hit)
Stats updated (winCount, lossCount, totalPnl)
Budget refunded (spent -= solInvested)
```

### Budget Authorization Flow
```
User sets budget (0.1/0.2/0.5/1.0 SOL presets or custom)
       │
       ▼
Clicks "Authorize X SOL"
       │
       ▼
Build on-chain memo transaction:
  - 0-lamport self-transfer (SystemProgram.transfer to self)
  - Memo instruction: "Jarvis Sniper | Authorize X SOL | timestamp"
  - Fetch recent blockhash
  - Set fee payer = user wallet
       │
       ▼
Phantom popup → User signs
       │
       ▼
Send + confirm on-chain
       │
       ▼
Store: budget.authorized = true, auto-calculate per-snipe SOL
```

---

## API Integrations

### 1. Jupiter v6 API (PRIMARY Swap Route)
- **Quote**: `https://quote-api.jup.ag/v6/quote?inputMint=...&outputMint=...&amount=...&slippageBps=...&swapMode=ExactIn`
- **Swap**: `POST https://quote-api.jup.ag/v6/swap` with `{ quoteResponse, userPublicKey, wrapAndUnwrapSol: true, dynamicComputeUnitLimit: true, prioritizationFeeLamports: 'auto' }`
- **Sell Quote**: Same endpoint with inputMint=token, outputMint=SOL
- No API key required. Routes across Raydium, Orca, Meteora.

### 2. Bags.fm Trade API (FALLBACK)
- **Base URL**: `https://public-api-v2.bags.fm/api/v1`
- **Quote**: `GET /trade/quote?inputMint=...&outputMint=...&amount=...&slippageBps=...`
- **Swap**: `POST /trade/swap` with `{ userPublicKey, quoteResponse }`
- **Auth**: `x-api-key` header with `BAGS_API_KEY`
- API key configured: `bags_prod_<redacted>...`

### 3. Direct DEX APIs (Last Resort)
- **Raydium V4**: `GET https://transaction-v1.raydium.io/compute/swap-base-in?inputMint=...&outputMint=...&amount=...&slippageBps=...&txVersion=V0`
  - Program ID: `675kPX9MHTjS2zt1qfr1NYHuzeLXfQM9H24wFSUt1Mp8`
- **Meteora DAMM v2**: Via Bags.fm authenticated endpoint
  - Program ID: `cpamdpZCGKUy5JxQXB4dcpGPiikHawvSWAd6mEn1sGG`
- **Meteora DBC**: `dbcij3LWUppWqq96dh6gJWwBifmcGfLSB5D4DuSMaqN`

### 4. DexScreener API (Token Discovery + P&L)
- **Boosts**: `https://api.dexscreener.com/token-boosts/latest/v1` (recently boosted tokens)
- **Tokens**: `https://api.dexscreener.com/tokens/v1/solana/{addresses}` (batch price data, up to 30)
- **Used for**: Token discovery scoring + real-time P&L price polling

### 5. Chart Providers
- **Birdeye TV Widget** (default): `https://birdeye.so/tv-widget/{mint}?chain=solana&viewMode=pair&chartInterval=15&chartType=CANDLE&chartLeftToolbar=show&theme=dark`
- **DexScreener embed**: `https://dexscreener.com/solana/{mint}?embed=1&theme=dark`
- **GeckoTerminal embed**: `https://www.geckoterminal.com/solana/tokens/{mint}?embed=1&info=0&swaps=0`

### 6. Jito MEV Bundles (Optional Fast Execution)
- **Endpoints** (with failover):
  1. `https://mainnet.block-engine.jito.wtf/api/v1/transactions`
  2. `https://amsterdam.mainnet.block-engine.jito.wtf/api/v1/transactions`
  3. `https://frankfurt.mainnet.block-engine.jito.wtf/api/v1/transactions`
- JSON-RPC `sendTransaction` with base64-encoded signed tx
- Falls back to standard RPC if all Jito endpoints fail

### 7. Solana RPC
- Configured via `NEXT_PUBLIC_SOLANA_RPC` in `.env.local`
- Currently: `https://api.mainnet-beta.solana.com` (public, rate-limited)
- Used for: sendRawTransaction, confirmTransaction, getLatestBlockhash

---

## Key Components Deep Dive

### useSniperStore (Zustand)
Central state store containing:
- **config**: SL%, TP%, trailing stop%, max position size (SOL), max concurrent positions, min score, auto-snipe toggle, Jito toggle, slippage BPS
- **budget**: `{ budgetSol, authorized, spent }` — on-chain authorization gate for all trades
- **positions[]**: mint, symbol, entryPrice, currentPrice, amount, amountLamports, solInvested, pnlPercent, pnlSol, entryTime, txHash, status (open/tp_hit/sl_hit/closed), isClosing, score, recommendedSl, recommendedTp
- **executionLog[]**: type (snipe/tp_exit/sl_exit/manual_exit/error/skip), symbol, mint, amount, price, pnlPercent, reason, txHash, timestamp
- **graduations[]**: Scored tokens from DexScreener scanner
- **snipedMints**: Set of already-sniped token addresses (dedup)
- **selectedMint**: Currently selected token for chart display
- **stats**: totalPnl, winCount, lossCount, totalTrades
- **Key actions**: snipeToken (local fallback), updatePrices, setPositionClosing, closePosition, resetSession

### usePhantomWallet (Custom Hook)
- Detects Phantom extension via `window.phantom.solana`
- Eager reconnect via `connect({ onlyIfTrusted: true })`
- Exposes: `connected`, `address`, `publicKey`, `signTransaction`, `connect`, `disconnect`
- Listens for `connect`, `disconnect`, `accountChanged` events
- `signTransaction` shows Phantom popup for user approval

### useSnipeExecutor (Execution Hook)
- Lazy-initializes Solana `Connection` from env RPC URL
- Pre-flight guards: wallet connected, budget authorized, not already sniped, not at capacity, sufficient budget remaining, not in-flight (pendingRef)
- Marks `snipedMints` immediately to prevent duplicates
- Calls `executeSwap()` from bags-trading.ts (waterfall quote strategy)
- On success: creates real Position with txHash + token amounts, updates budget spent
- On failure: logs error execution event, un-marks sniped mint for retry

### usePnlTracker (Real-Time Pricing)
- Polls DexScreener tokens API every 3 seconds
- Batch fetches current prices for all open position mints
- Calls `store.updatePrices(priceMap)` to recalculate P&L

### useAutomatedRiskManagement (Auto SL/TP)
- Monitors all open positions against their per-token SL/TP thresholds
- When SL/TP hit: gets sell quote via `getSellQuote()`, executes via `executeSwapFromQuote()`
- Uses `isClosing` lock to prevent duplicate sell attempts
- Updates position status, stats, and frees budget on close

### getRecommendedSlTp (Per-Token Risk)
Multi-factor SL/TP recommendation:
- Base from score tier: 80+ → SL 15% TP 60%; 65+ → SL 20% TP 40%; 50+ → SL 25% TP 30%; <50 → SL 30% TP 20%
- Adjusted for liquidity (high liq = tighter SL)
- Adjusted for momentum (strong upward = wider TP)
- Adjusted for volume (high vol = more reliable moves)
- Clamped: SL 5-50%, TP 10-150%

### bags-trading.ts (Swap Execution Module)
- **getQuote()**: Waterfall — Jupiter v6 → Bags.fm → Direct DEX (Raydium/Meteora)
- **getSellQuote()**: Token→SOL via Jupiter (for risk management exits)
- **executeSwap()**: Full flow — quote → buildTx → sign → send → confirm
- **executeSwapFromQuote()**: Execute with pre-fetched quote (skip re-quoting for SL/TP)
- **getSwapTransaction()**: Jupiter swap endpoint → Bags.fm fallback
- **sendWithJito()**: MEV bundle submission with 3-endpoint failover

---

## Design System

### Theme
Dark terminal aesthetic with green accent (`#22c55e`). Glassmorphism cards with subtle green glow. Premium trading terminal feel.

### CSS Architecture (Tailwind v4)
- **No `tailwind.config.ts`** — theme defined in `globals.css` via `@theme` block
- CSS custom properties for all colors, shadows, borders
- Utility classes: `card-glass`, `badge-exceptional`, `skeleton`, `custom-scrollbar`, `sniper-dot`
- Responsive: 3-column grid on desktop, stacked on mobile

### Layout (page.tsx)
```
┌──────────────────────────────────────────────────────┐
│                     StatusBar                         │
├──────────────┬──────────────────┬────────────────────┤
│ Token Scanner│ Performance      │ Sniper Controls    │
│ (Graduation  │ TokenChart       │ Quick Snipe        │
│  Feed)       │ (drag resize)    │ Budget + Auth      │
│              │ ExecutionLog     │ Config + Toggles   │
│              │                  │ Positions Panel    │
│              │                  │ (Reset Record)     │
└──────────────┴──────────────────┴────────────────────┘
Grid: [340px] [1fr] [380px]
```

---

## Environment Variables

| Variable | Status | Notes |
|----------|--------|-------|
| `NEXT_PUBLIC_SOLANA_RPC` | Set | `https://api.mainnet-beta.solana.com` — upgrade to Helius/QuickNode for production |
| `BAGS_API_KEY` | Set | `bags_prod_<redacted>` |
| `BAGS_REFERRAL_ACCOUNT` | Set | `7jxnA3V5RbkuRpM1iP23i2eD37SqfrqNgoTU4UoB9Mdr` |

---

## Resolved Issues

### "Swap failed: Quote failed" — RESOLVED
- **Root cause**: Bags.fm trade API was failing as primary quote source
- **Fix**: Switched to Jupiter v6 API as primary, Bags.fm as fallback, Direct Raydium/Meteora as last resort
- **Status**: Waterfall quote strategy working

### DexScreener Chart "No Data" — RESOLVED
- **Fix**: Switched to Birdeye TV widget as default (works with token mints directly), DexScreener and GeckoTerminal as fallbacks with provider switching buttons

### Ghost Positions (Sniper says it worked but didn't) — RESOLVED
- **Root cause**: `snipeToken()` in store created local-only positions without blockchain transactions
- **Fix**: Created `useSnipeExecutor` hook that wires real swap execution (Jupiter/Bags) through Phantom wallet signing

### Budget Authorization — ENHANCED
- **Before**: Local state toggle only (`authorized: true`)
- **After**: On-chain memo transaction signed via Phantom — proves wallet ownership, creates auditable on-chain record

### No Manual Snipe Flow — RESOLVED
- **Before**: Could only snipe via hover overlay on scanner cards
- **After**: "Quick Snipe" input in SniperControls — paste any token mint and snipe with one click

---

## Future Improvements / Research Questions

1. **Interactive Chart with Position Lines**: Replace Birdeye iframe with `lightweight-charts` library to overlay Entry, SL, TP price lines on candlestick charts. Requires fetching OHLCV data from Birdeye/Bitquery API.

2. **Jito Tip Instructions**: Add dynamic Jito tip amounts to transactions for guaranteed block inclusion. Fetch tip floor from `bundles.jito.wtf/api/v1/bundles/tip_floor`.

3. **Direct Raydium SDK Integration**: Use `@raydium-io/raydium-sdk` for swapping tokens before Jupiter indexes them. Requires fetching pool keys on-chain.

4. **Jupiter Ultra API**: Migrate SL/TP exits to Jupiter Ultra (`/ultra/v1/`) for automated landing logic and real-time slippage estimation.

5. **Dedicated RPC Provider**: Switch from public Solana RPC to Helius/QuickNode/Triton for sub-second execution latency.

6. **Time-Based Exit**: Add `autoSellDelay` config — force-close positions older than X minutes that are still negative (slow rug protection).

7. **Split Slippage**: Separate `buySlippageBps` (tight, 0.3-0.5%) from `sellSlippageBps` (loose, 2-5%) for better entry/exit optimization.

8. **Trailing Stop Visualization**: Show dynamic trailing stop line on chart that moves up with price peaks.

9. **Dynamic Priority Fees**: Escalation ladder — normal trades use "high" priority, SL exits use "veryHigh" + Jito tips.
