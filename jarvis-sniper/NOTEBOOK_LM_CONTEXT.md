# Jarvis Sniper — Complete Project Context for NotebookLM

## Project Overview

**Jarvis Sniper** is a standalone Solana token sniping web application. It monitors newly graduated/boosted tokens on Solana DEXes, scores them using multi-factor analysis, and executes real on-chain swap transactions through the user's Phantom wallet. The goal is a professional-grade trading terminal for sniping new Solana meme coins with automated risk management (stop-loss, take-profit, trailing stops).

### What We're Trying to Accomplish

1. **Token Discovery**: Continuously scan DexScreener's boosted token feed to find newly launched Solana tokens with strong fundamentals (liquidity, volume, social presence, buy pressure).

2. **Scoring & Filtering**: Score each token 0-100 using liquidity, volume, social links, boost amount, buy/sell ratio, and price momentum. Only tokens meeting the minimum score threshold are snipe candidates.

3. **Real On-Chain Execution**: When the user clicks "Snipe" or auto-snipe triggers:
   - Get a swap quote from the Bags.fm/Jupiter aggregator API
   - Build a versioned Solana transaction
   - Send to Phantom wallet for user to sign
   - Submit signed transaction to Solana mainnet (with optional Jito MEV bundle)
   - Confirm on-chain and track the position with real tx hash

4. **Position Management**: Track open positions with real-time P&L, per-token SL/TP recommendations, manual close buttons, and position age tracking.

5. **Budget Authorization System**: Users must explicitly set and authorize a SOL budget before any sniping can occur. This prevents accidental trades and ghost positions.

6. **Chart Integration**: Embedded charts (Birdeye TV widget, DexScreener, GeckoTerminal) for any selected token, with drag-to-resize.

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
| **@solana/web3.js** | ^1.98.0 | Solana SDK — Connection, Transaction, PublicKey, VersionedTransaction |
| **@solana/wallet-adapter-base** | ^0.9.23 | Base wallet adapter types (installed but NOT used for connection — we use native Phantom API) |
| **@solana/wallet-adapter-phantom** | ^0.9.24 | Phantom adapter types (installed but NOT used directly) |
| **@solana/wallet-adapter-react** | ^0.15.35 | React context for wallets (installed but ConnectionProvider REMOVED to avoid console errors) |
| **buffer** | ^6.0.3 | Node.js Buffer polyfill for browser (needed by @solana/web3.js for transaction serialization) |

**IMPORTANT**: We do NOT use `@solana/wallet-adapter-react`'s `ConnectionProvider` or `WalletProvider`. We have a custom `usePhantomWallet` hook that directly interfaces with `window.phantom.solana` (the Phantom browser extension's injected provider). This was done because wallet-adapter was causing `WalletContext` console errors.

### State Management
| Library | Version | Purpose |
|---------|---------|---------|
| **Zustand** | ^5.0.11 | Lightweight state store for all app state (config, positions, executions, budget) |

### UI Libraries
| Library | Version | Purpose |
|---------|---------|---------|
| **lucide-react** | ^0.563.0 | Icon library (Crosshair, Shield, Target, BarChart3, etc.) |
| **framer-motion** | ^12.31.1 | Animations (installed, available for future use) |
| **sonner** | ^2.0.7 | Toast notifications (installed, available for future use) |
| **clsx** | ^2.1.1 | Conditional className utility |
| **tailwind-merge** | ^3.4.0 | Merge Tailwind classes without conflicts |

---

## Architecture & File Structure

```
jarvis-sniper/
├── src/
│   ├── app/
│   │   ├── layout.tsx              # Root layout — fonts, WalletProvider wrapper, dark terminal background
│   │   ├── page.tsx                # Main dashboard — 3-column grid layout
│   │   ├── globals.css             # Tailwind v4 theme — dark terminal design system
│   │   └── api/
│   │       ├── graduations/route.ts  # Server-side API: DexScreener → scored token feed
│   │       └── best-ever/route.ts    # Loads BEST_EVER.json backtester config
│   ├── components/
│   │   ├── StatusBar.tsx           # Top bar — wallet connect, SOL balance, system status
│   │   ├── GraduationFeed.tsx      # LEFT COLUMN — Token scanner, auto-snipe, token cards
│   │   ├── PerformanceSummary.tsx   # CENTER TOP — Win rate, total P&L, trade count
│   │   ├── TokenChart.tsx          # CENTER MIDDLE — Birdeye/DexScreener/Gecko chart embed with drag resize
│   │   ├── ExecutionLog.tsx        # CENTER BOTTOM — Snipe/error/exit event log
│   │   ├── SniperControls.tsx      # RIGHT TOP — Budget system, config sliders, auto-snipe toggle
│   │   ├── PositionsPanel.tsx      # RIGHT BOTTOM — Open/closed positions, click-to-chart
│   │   └── providers/
│   │       └── WalletProvider.tsx   # Client-side wrapper — Buffer polyfill + PhantomWalletProvider
│   ├── hooks/
│   │   ├── usePhantomWallet.tsx    # Custom Phantom wallet hook — connect, disconnect, signTransaction
│   │   └── useSnipeExecutor.ts     # Real swap execution hook — quote → sign → send → confirm
│   ├── stores/
│   │   └── useSniperStore.ts       # Zustand store — all state, config, positions, budget, actions
│   └── lib/
│       ├── bags-api.ts             # Bags.fm API client — fetchGraduations, fetchTokenInfo, scoring
│       └── bags-trading.ts         # Swap execution — getQuote, executeSwap, Jito bundle support
├── .env.local                      # NEXT_PUBLIC_SOLANA_RPC endpoint
├── package.json
├── tsconfig.json
└── tailwind.config.ts (Tailwind v4 — configured via globals.css @theme)
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
                     Token cards with scores
                     Auto-snipe if enabled
```

### Swap Execution Flow (THE CRITICAL PATH)
```
User clicks "Snipe" or auto-snipe triggers
       │
       ▼
useSnipeExecutor.snipe(grad)
       │
       ├── Guard checks: wallet connected? budget authorized? not already sniped?
       │
       ▼
bags-trading.ts → getQuote()
       │
       │  POST https://public-api-v2.bags.fm/api/v1/trade/quote
       │  Params: inputMint (SOL), outputMint (token), amount (lamports), slippageBps
       │
       ▼
bags-trading.ts → executeSwap()
       │
       │  POST https://public-api-v2.bags.fm/api/v1/trade/swap
       │  Body: { userPublicKey, quoteResponse }
       │  Returns: { swapTransaction (base64 encoded) }
       │
       ▼
Deserialize VersionedTransaction from base64
       │
       ▼
Phantom wallet signTransaction(tx) ──→ User approves in Phantom popup
       │
       ▼
Send to Solana:
  ├── If Jito enabled: POST to Jito block engine endpoints
  └── Else: connection.sendRawTransaction()
       │
       ▼
connection.confirmTransaction(txHash, 'confirmed')
       │
       ▼
Create Position in Zustand store with real txHash + token amounts
```

### Current Issue: "Swap failed: Quote failed"
The `getQuote()` call to `https://public-api-v2.bags.fm/api/v1/trade/quote` is returning a non-success response. This could be because:
1. The Bags.fm trade API endpoint URL may be wrong or deprecated
2. The API might require authentication (API key / partner key)
3. The token might not have a Jupiter-routable pair yet
4. The API response format might have changed
5. Jupiter v6 API could be used directly instead of going through Bags.fm

**Fallback option**: Use Jupiter's own quote API directly:
- Quote: `https://quote-api.jup.ag/v6/quote?inputMint=So11111111111111111111111111111111111111112&outputMint={TOKEN}&amount={LAMPORTS}&slippageBps={BPS}`
- Swap: `https://quote-api.jup.ag/v6/swap` (POST with quote + userPublicKey)

---

## API Integrations

### 1. DexScreener API (Token Discovery)
- **Boosts endpoint**: `https://api.dexscreener.com/token-boosts/latest/v1`
  - Returns recently boosted tokens across all chains
  - We filter to `chainId === 'solana'`
- **Token data endpoint**: `https://api.dexscreener.com/tokens/v1/solana/{addresses}`
  - Batch fetch pair data (price, liquidity, volume, txn counts)
  - Up to 30 comma-separated addresses per call
- **Embed chart**: `https://dexscreener.com/solana/{mint}?embed=1&theme=dark`
  - Embeddable iframe chart (sometimes shows "no data" for new tokens)

### 2. Bags.fm Trade API (Swap Execution)
- **Base URL**: `https://public-api-v2.bags.fm/api/v1`
- **Quote**: `GET /trade/quote?inputMint=...&outputMint=...&amount=...&slippageBps=...`
- **Swap**: `POST /trade/swap` with `{ userPublicKey, quoteResponse }`
- **Status**: Currently returning failures — may need API key or may be deprecated

### 3. Jupiter v6 API (Alternative Swap Route)
- **Quote**: `https://quote-api.jup.ag/v6/quote?inputMint=...&outputMint=...&amount=...&slippageBps=...`
- **Swap**: `POST https://quote-api.jup.ag/v6/swap` with `{ quoteResponse, userPublicKey, wrapAndUnwrapSol: true }`
- Jupiter is the standard Solana swap aggregator — more reliable than going through Bags.fm

### 4. Birdeye TV Widget (Chart)
- **URL**: `https://birdeye.so/tv-widget/{mint}?chain=solana&viewMode=pair&chartInterval=15&chartType=CANDLE&chartLeftToolbar=show&theme=dark`
- Works reliably with Solana token mints
- Shows TradingView-style candlestick charts

### 5. GeckoTerminal (Chart Fallback)
- **URL**: `https://www.geckoterminal.com/solana/tokens/{mint}?embed=1&info=0&swaps=0`

### 6. Jito MEV Bundles (Optional Fast Execution)
- Endpoints: `https://mainnet.block-engine.jito.wtf/api/v1/transactions` (+ amsterdam, frankfurt)
- Sends signed transaction as base64 via JSON-RPC `sendTransaction`
- Faster block inclusion via MEV bundle

### 7. Solana RPC
- Configured via `NEXT_PUBLIC_SOLANA_RPC` in `.env.local`
- Currently: `https://api.mainnet-beta.solana.com` (public, rate-limited)
- Recommended upgrade: Helius, QuickNode, or Triton for production

---

## Key Components Deep Dive

### useSniperStore (Zustand)
Central state store containing:
- **config**: SL%, TP%, trailing stop, max position size, max concurrent positions, min score, auto-snipe toggle, Jito toggle, slippage BPS
- **budget**: { budgetSol, authorized, spent } — authorization gate for all trades
- **positions**: Array of Position objects (mint, symbol, entry price, current price, P&L, tx hash, status, per-token SL/TP)
- **executionLog**: Array of ExecutionEvent objects (snipe, error, exit events)
- **graduations**: Array of BagsGraduation objects from scanner
- **snipedMints**: Set of already-sniped token addresses (dedup)
- **selectedMint**: Currently selected token for chart display

### usePhantomWallet (Custom Hook)
- Detects Phantom extension via `window.phantom.solana`
- Eager reconnect via `connect({ onlyIfTrusted: true })`
- Exposes: `connected`, `address`, `publicKey`, `signTransaction`, `connect`, `disconnect`
- Listens for `accountChanged` events (Phantom account switching)

### useSnipeExecutor (Execution Hook)
- Lazy-initializes Solana `Connection` from env RPC URL
- Guards: wallet connected, budget authorized, not already sniped, not at capacity, sufficient budget
- Calls `executeSwap()` from bags-trading.ts
- On success: creates real Position with txHash
- On failure: logs error, un-marks token for retry
- Has in-flight dedup via `pendingRef`

### getRecommendedSlTp (Per-Token Risk)
Multi-factor SL/TP recommendation:
- Base from score tier: 80+ → SL 15% TP 60%; 65+ → SL 20% TP 40%; 50+ → SL 25% TP 30%; <50 → SL 30% TP 20%
- Adjusted for liquidity (high liq = tighter SL)
- Adjusted for momentum (strong up = wider TP)
- Adjusted for volume (high vol = more reliable)
- Clamped: SL 5-50%, TP 10-150%

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
│ (Graduation  │ TokenChart       │ (Budget + Config)  │
│  Feed)       │ ExecutionLog     │ Positions Panel    │
│              │                  │                    │
└──────────────┴──────────────────┴────────────────────┘
Grid: [340px] [1fr] [380px]
```

---

## Environment Variables

| Variable | Value | Notes |
|----------|-------|-------|
| `NEXT_PUBLIC_SOLANA_RPC` | `https://api.mainnet-beta.solana.com` | Public RPC, rate-limited. Upgrade to Helius/QuickNode for production. |
| `NEXT_PUBLIC_BAGS_API_KEY` | (not set) | May be needed for Bags.fm trade API |
| `NEXT_PUBLIC_BAGS_PARTNER_KEY` | (not set) | May be needed for Bags.fm trade API |

---

## Known Issues & Debugging

### 1. "Swap failed: Quote failed"
- **Where**: `useSnipeExecutor` → `executeSwap()` → `getQuote()`
- **API call**: `GET https://public-api-v2.bags.fm/api/v1/trade/quote?inputMint=So1111...&outputMint={token}&amount={lamports}&slippageBps=150`
- **Problem**: API returns non-200 or `success: false`
- **Fix options**:
  a. Switch to Jupiter v6 API directly (more reliable, no API key needed)
  b. Check if Bags.fm API requires authentication
  c. Verify the token has a Jupiter-routable pair

### 2. DexScreener Chart "No Data"
- DexScreener embeds need the pair address, not token mint. New tokens may not have indexed pairs yet.
- **Fixed**: Added Birdeye TV widget as default (works with token mints directly), DexScreener and GeckoTerminal as fallbacks.

### 3. Ghost Positions
- **Fixed**: Budget authorization system prevents trades without explicit user approval. `useSnipeExecutor` requires wallet connection + budget authorization before any swap executes.

### 4. Duplicate Execution Keys
- **Fixed**: Monotonic `execCounter` ensures unique IDs even when multiple events fire in same millisecond.

---

## Backtester Integration

The sniper has a companion backtester (in parent `jarvis-sniper/` directory) that:
- Runs continuous backtests on historical DexScreener data
- Saves best configuration to `winning/BEST_EVER.json`
- The web app loads this via `/api/best-ever` and applies config (SL%, TP%, position size, etc.)
- Genetic optimizer tunes parameters automatically

---

## Solana-Specific Technical Notes

### Transaction Types
- Solana uses **VersionedTransaction** (v0) for modern transactions with address lookup tables
- The swap API returns a base64-encoded serialized transaction
- We deserialize it, sign with Phantom, then send raw bytes to the network

### SOL Amounts
- Solana native unit: **lamports** (1 SOL = 1,000,000,000 lamports)
- UI shows SOL, API expects lamports: `Math.floor(amountSol * 1e9)`

### Phantom Wallet Integration
- Phantom injects `window.phantom.solana` as a provider object
- Key methods: `connect()`, `disconnect()`, `signTransaction(tx)`, `signAllTransactions(txs)`
- Events: `connect`, `disconnect`, `accountChanged`
- `signTransaction` shows a popup asking user to approve — this is the authorization gate

### RPC Considerations
- Public Solana RPC (`api.mainnet-beta.solana.com`) has rate limits
- For production sniping, need dedicated RPC (Helius, QuickNode, Triton)
- `confirmTransaction` waits for 'confirmed' commitment level

### Jito MEV Bundles
- Optional faster execution path
- Sends to Jito's block engine which includes tx in next block via MEV auction
- Falls back to standard `sendRawTransaction` if Jito fails

---

## Research Questions for Troubleshooting

1. **Is the Bags.fm trade API (`public-api-v2.bags.fm/api/v1/trade/quote`) still operational?** Does it require API keys? Has the endpoint changed?

2. **Should we switch to Jupiter v6 API directly?** `quote-api.jup.ag/v6/quote` is the standard and doesn't require API keys.

3. **How to handle tokens that don't have Jupiter-routable pairs yet?** Newly graduated tokens might only be on Raydium or Meteora. Jupiter aggregates across DEXes, but there may be a delay.

4. **What's the optimal RPC provider for sub-second snipe execution?** Helius, QuickNode, Triton — which has lowest latency for mainnet?

5. **How to implement real-time P&L tracking?** Need to poll token prices periodically and update position `currentPrice` / `pnlPercent`. Could use DexScreener WebSocket or Birdeye price API.

6. **How to implement actual SL/TP execution?** Currently SL/TP are display-only recommendations. Need a monitoring loop that checks price vs SL/TP levels and auto-sells when hit.
