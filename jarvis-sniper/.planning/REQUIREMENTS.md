# Jarvis Sniper — Requirements

**Created:** 2026-02-09
**Status:** Phase 1 Complete, Phase 2 Active
**Milestone:** v2.0 — Backtesting, Advanced Algorithms, Data Integration

---

## Phase 1 Requirements (COMPLETE)

### SCORE-01: Dynamic Scoring for All Asset Classes ✅
- `calcBlueChipScore()` for blue chip tokens (4 dimensions, 0-100)
- `calcEquityScore()` for xStocks/indexes/prestocks (4 dimensions, 0-100)
- Replaces hardcoded `score: 50` with real-time data

### SCORE-02: Blue Chip Token Registry ✅
- 17 curated tokens across 3 tiers (Core Ecosystem, DeFi, Established Memes)
- API route at `/api/bluechips` with scoring

### TRADE-01: Per-Asset SL/TP Calibration ✅
- `getRecommendedSlTp()` branches by source type
- Asset-specific volatility ranges

### TRADE-02: 16 Strategy Presets ✅
- 8 memecoin, 3 blue chip, 2 xstock, 2 index, 1 prestock

### TRADE-03: Strategy Switch Continuity ✅
- `autoSnipe` preserved during preset switch
- `activePreset` in auto-snipe dependency array

### TRADE-04: Asset-Type-Aware Filters ✅
- Memecoin filters (B/S ratio, age, momentum) only apply to memecoins
- xStocks/indexes/blue chips pass through without memecoin-specific gates

### UX-01: Session Export ✅
- Downloadable `.md` report with stats, positions, execution log

### UX-02: Disclaimer Modal ✅
- Shows on every page load, requires acknowledgment

---

## Phase 2 Requirements (ACTIVE)

### Backtesting

#### BACK-01: Historical Data Pipeline
**Priority:** P0 | **Category:** Backtesting
- Collect OHLCV data (1h candles, 6+ months) for all 17 blue chip tokens
- Collect memecoin graduation history (5000+ historical tokens)
- Store data in local JSON/CSV for fast iteration
- Data sources: DexScreener, Jupiter price history, Birdeye

#### BACK-02: Backtesting Engine
**Priority:** P0 | **Category:** Backtesting
- Simulate all 16 strategy presets against historical data
- Configurable: entry timing, slippage model, fee model
- Walk-forward optimization (train on 70%, test on 30%)
- Output: Win Rate, Profit Factor, Max Drawdown, Sharpe Ratio, Avg Trade Duration

#### BACK-03: Strategy Validation Report
**Priority:** P0 | **Category:** Backtesting
- Per-strategy performance table with confidence intervals
- Compare backtested vs claimed win rates
- Identify underperforming strategies to remove/tune
- Generate downloadable PDF/MD report

#### BACK-04: Continuous Backtesting Loop
**Priority:** P1 | **Category:** Backtesting
- Auto-run backtests on new data (daily)
- Track strategy drift over time
- Alert if win rate drops below threshold

### Data Integration

#### DATA-01: tvscreener Integration
**Priority:** P0 | **Category:** Data
- Integrate TradingView screener API for real stock data
- Map TradingView symbols to token registry (AAPL → AAPLx)
- Pull: price, volume, RSI, MACD, moving averages, market cap
- Feed into `calcEquityScore()` for richer scoring

#### DATA-02: Market Hours Awareness
**Priority:** P1 | **Category:** Data
- Detect pre-market, regular hours, after-hours for xStocks
- Adjust scoring: higher scores during regular hours (more liquidity)
- Display market status in UI

### Wallet Safety

#### WALLET-01: Ephemeral Wallet Persistence
**Priority:** P0 | **Category:** Safety
- Move session wallet from `sessionStorage` to `localStorage` (encrypted)
- Auto-sweep ALL funds back to main wallet on `beforeunload`
- User password for wallet recovery across sessions
- CRITICAL: User must never lose funds

#### WALLET-02: Fund Recovery UI
**Priority:** P1 | **Category:** Safety
- Show warning if ephemeral wallet has balance on page load
- One-click sweep to main wallet
- Transaction history for sweep operations

### Advanced Algorithms

#### ALGO-01: Research-Backed Strategy Implementation
**Priority:** P0 | **Category:** Algorithms
- Implement strategies from awesome-systematic-trading research
- At minimum: Mean Reversion, Trend Following, Breakout, Momentum Factor
- Each strategy must be backtested (BACK-02) before enabling

#### ALGO-02: Volatility Regime Detection
**Priority:** P1 | **Category:** Algorithms
- Detect current market regime: trending, mean-reverting, volatile
- Auto-select best strategy for current regime
- Use ATR, Bollinger Band width, or realized vol as regime indicator

#### ALGO-03: Pairs Trading
**Priority:** P2 | **Category:** Algorithms
- Identify correlated token pairs (JUP/RAY, BONK/WIF)
- Z-score mean reversion on spread
- Entry at ±2 sigma, exit at 0

#### ALGO-04: Multi-Timeframe Confirmation
**Priority:** P1 | **Category:** Algorithms
- 5m + 1h + 24h trend alignment for entries
- Only enter when majority of timeframes agree on direction
- Reduces false signals from noise

### Circuit Breakers

#### CIRCUIT-01: Per-Asset Circuit Breakers
**Priority:** P0 | **Category:** Risk
- Separate loss counters for each asset class
- Memecoin losses don't disable blue chip trading
- Per-class daily loss limits and consecutive loss limits
- Configurable cooldown periods

#### CIRCUIT-02: Gradual Position Sizing
**Priority:** P2 | **Category:** Risk
- After N consecutive losses, reduce position size by X%
- Gradually restore after winning trades
- Kelly criterion for optimal sizing

### On-Chain Execution

#### EXEC-01: Jupiter Trigger Orders
**Priority:** P2 | **Category:** Execution
- Use Jupiter Trigger Orders for on-chain SL/TP
- Positions protected even if browser closes
- Fields already exist: `jupTpOrderKey`, `jupSlOrderKey`

---

## Requirement Traceability

| REQ ID | Phase | Status |
|--------|-------|--------|
| SCORE-01 | 1 | ✅ Complete |
| SCORE-02 | 1 | ✅ Complete |
| TRADE-01 | 1 | ✅ Complete |
| TRADE-02 | 1 | ✅ Complete |
| TRADE-03 | 1 | ✅ Complete |
| TRADE-04 | 1 | ✅ Complete |
| UX-01 | 1 | ✅ Complete |
| UX-02 | 1 | ✅ Complete |
| BACK-01 | 2.1 | Pending |
| BACK-02 | 2.1 | Pending |
| BACK-03 | 2.1 | Pending |
| BACK-04 | 2.2 | Pending |
| DATA-01 | 2.2 | Pending |
| DATA-02 | 2.2 | Pending |
| WALLET-01 | 2.3 | Pending |
| WALLET-02 | 2.3 | Pending |
| ALGO-01 | 2.4 | Pending |
| ALGO-02 | 2.4 | Pending |
| ALGO-03 | 2.5 | Pending |
| ALGO-04 | 2.4 | Pending |
| CIRCUIT-01 | 2.3 | Pending |
| CIRCUIT-02 | 2.5 | Pending |
| EXEC-01 | 2.5 | Pending |

---

## Success Criteria

| Metric | Target |
|--------|--------|
| Backtested strategies | All 16 validated against 5000+ trades |
| Blue chip win rate | >55% (backtested) |
| xStock win rate | >50% (backtested) |
| Memecoin win rate | >80% (backtested, current best: 88.2%) |
| Fund safety | Zero fund loss from wallet issues |
| tvscreener data | Real-time stock data enriching equity scores |
| Circuit breakers | Per-asset-class isolation working |
| Build clean | Zero TypeScript errors |

---

**Document Version:** 1.0
**Last Updated:** 2026-02-09
