# Real Data Backtest Results

**Generated**: 2026-02-13T03:26:21.893Z
**Runtime**: 11.4s
**Data Source**: GeckoTerminal OHLCV (1h candles) — REAL market data only
**Synthetic data**: NONE — zero synthetic or simulated price data used

## 1. Data Provenance

Every candle used in these backtests comes from GeckoTerminal's OHLCV API (CoinGecko DEX data).
Each trade can be verified by its entry/exit timestamps and the pool address on GeckoTerminal.

| Token | Pair Address | Candles | Date Range |
|-------|-------------|---------|------------|
| W_4gBdoc | `4gBdoceUxqqc...` | 1000 | 2026-01-02 04:00:00 → 2026-02-13 03:00:00 |

## 2. Strategy Performance Summary

| Strategy | Trades | Win Rate | Profit Factor | Expectancy | Avg Return | Max DD | Sharpe | Tokens |
|----------|--------|----------|---------------|------------|------------|--------|--------|--------|
| **Blue Chip Mean Revert** | 89 | 19.1% | 0.12 | -1.42 | -0.62% | 72.9% | -10.00 | 1 |
| **Blue Chip Trend Follow** | 19 | 0.0% | 0.00 | -3.90 | -3.10% | 53.1% | -10.00 | 1 |
| **Blue Chip Breakout** | 17 | 17.6% | 0.11 | -2.10 | -1.30% | 31.1% | -10.00 | 1 |

## 3. Strategy Ranking (by Expectancy)

1. **bluechip_mean_revert** — WR: 19.1%, Exp: -1.42, PF: 0.12 → **UNDERPERFORMER** (89 trades)
2. **bluechip_breakout** — WR: 17.6%, Exp: -2.10, PF: 0.11 → **UNDERPERFORMER** (17 trades)
3. **bluechip_trend_follow** — WR: 0.0%, Exp: -3.90, PF: 0.00 → **UNDERPERFORMER** (19 trades)

## 4. Parameter Optimization (Grid Search)

For each strategy, we tested parameter variations around the current config.
Only showing top 3 alternatives that improve on the current config.

### Blue Chip Mean Revert
Current: SL=3%, TP=8%, Trail=2% → Exp: -1.42

| Rank | SL% | TP% | Trail% | Win Rate | Expectancy | PF | Trades |
|------|-----|-----|--------|----------|------------|-----|--------|
| 1 | 4.5 | 5 | 1 | 11.3% | -1.13 | 0.07 | 124 |
| 2 | 4.5 | 6 | 1 | 11.3% | -1.13 | 0.07 | 124 |
| 3 | 4.5 | 8 | 1 | 11.3% | -1.13 | 0.07 | 124 |

### Blue Chip Trend Follow
Current: SL=5%, TP=15%, Trail=4% → Exp: -3.90

| Rank | SL% | TP% | Trail% | Win Rate | Expectancy | PF | Trades |
|------|-----|-----|--------|----------|------------|-----|--------|
| 1 | 7.5 | 7.5 | 2 | 0.0% | -1.80 | 0.00 | 19 |
| 2 | 7.5 | 11.3 | 2 | 0.0% | -1.80 | 0.00 | 19 |
| 3 | 7.5 | 15 | 2 | 0.0% | -1.80 | 0.00 | 19 |

### Blue Chip Breakout
Current: SL=4%, TP=12%, Trail=3% → Exp: -2.10

| Rank | SL% | TP% | Trail% | Win Rate | Expectancy | PF | Trades |
|------|-----|-----|--------|----------|------------|-----|--------|
| 1 | 2 | 6 | 4.5 | 18.8% | -1.48 | 0.31 | 16 |
| 2 | 2 | 6 | 3 | 16.7% | -1.55 | 0.19 | 18 |
| 3 | 4 | 6 | 1.5 | 9.1% | -1.59 | 0.11 | 22 |

## 5. Trade-Level Evidence (Sample — First 10 Trades Per Strategy)

Each trade is verifiable via the pair address + entry/exit timestamps on DexScreener.

### Blue Chip Mean Revert (89 total trades)

| # | Token | Entry Time | Exit Time | Entry$ | Exit$ | P&L% | Net% | Exit Reason | Pair |
|---|-------|------------|-----------|--------|-------|------|------|-------------|------|
| 1 | W_4gBdoc | 2026-01-05 07:00:00 | 2026-01-05 17:00:00 | $0.037784 | $0.038581 | 2.11% | 1.31% | trail | `4gBdoceU...` |
| 2 | W_4gBdoc | 2026-01-06 18:00:00 | 2026-01-06 22:00:00 | $0.039219 | $0.039874 | 1.67% | 0.87% | trail | `4gBdoceU...` |
| 3 | W_4gBdoc | 2026-01-07 02:00:00 | 2026-01-07 09:00:00 | $0.038935 | $0.038431 | -1.29% | -2.09% | trail | `4gBdoceU...` |
| 4 | W_4gBdoc | 2026-01-07 10:00:00 | 2026-01-07 13:00:00 | $0.038708 | $0.038051 | -1.70% | -2.50% | trail | `4gBdoceU...` |
| 5 | W_4gBdoc | 2026-01-07 16:00:00 | 2026-01-07 22:00:00 | $0.037902 | $0.037624 | -0.74% | -1.54% | trail | `4gBdoceU...` |
| 6 | W_4gBdoc | 2026-01-08 01:00:00 | 2026-01-08 06:00:00 | $0.037728 | $0.037110 | -1.64% | -2.44% | trail | `4gBdoceU...` |
| 7 | W_4gBdoc | 2026-01-08 07:00:00 | 2026-01-08 10:00:00 | $0.037016 | $0.036391 | -1.69% | -2.49% | trail | `4gBdoceU...` |
| 8 | W_4gBdoc | 2026-01-08 14:00:00 | 2026-01-08 15:00:00 | $0.035949 | $0.036046 | 0.27% | -0.53% | trail | `4gBdoceU...` |
| 9 | W_4gBdoc | 2026-01-08 21:00:00 | 2026-01-09 08:00:00 | $0.036571 | $0.036256 | -0.86% | -1.66% | trail | `4gBdoceU...` |
| 10 | W_4gBdoc | 2026-01-10 07:00:00 | 2026-01-10 22:00:00 | $0.036216 | $0.037362 | 3.16% | 2.36% | trail | `4gBdoceU...` |

### Blue Chip Trend Follow (19 total trades)

| # | Token | Entry Time | Exit Time | Entry$ | Exit$ | P&L% | Net% | Exit Reason | Pair |
|---|-------|------------|-----------|--------|-------|------|------|-------------|------|
| 1 | W_4gBdoc | 2026-01-09 15:00:00 | 2026-01-10 06:00:00 | $0.036833 | $0.035971 | -2.34% | -3.14% | trail | `4gBdoceU...` |
| 2 | W_4gBdoc | 2026-01-12 02:00:00 | 2026-01-12 14:00:00 | $0.037285 | $0.035966 | -3.54% | -4.34% | trail | `4gBdoceU...` |
| 3 | W_4gBdoc | 2026-01-14 19:00:00 | 2026-01-15 03:00:00 | $0.039179 | $0.037970 | -3.09% | -3.89% | trail | `4gBdoceU...` |
| 4 | W_4gBdoc | 2026-01-16 21:00:00 | 2026-01-18 23:00:00 | $0.036675 | $0.034841 | -5.00% | -5.80% | sl | `4gBdoceU...` |
| 5 | W_4gBdoc | 2026-01-21 14:00:00 | 2026-01-21 16:00:00 | $0.031215 | $0.029654 | -5.00% | -5.80% | sl | `4gBdoceU...` |
| 6 | W_4gBdoc | 2026-01-21 19:00:00 | 2026-01-21 23:00:00 | $0.031632 | $0.030367 | -4.00% | -4.80% | trail | `4gBdoceU...` |
| 7 | W_4gBdoc | 2026-01-23 15:00:00 | 2026-01-23 20:00:00 | $0.030245 | $0.029327 | -3.04% | -3.84% | trail | `4gBdoceU...` |
| 8 | W_4gBdoc | 2026-01-24 03:00:00 | 2026-01-25 04:00:00 | $0.030141 | $0.029433 | -2.35% | -3.15% | trail | `4gBdoceU...` |
| 9 | W_4gBdoc | 2026-01-26 01:00:00 | 2026-01-27 13:00:00 | $0.029225 | $0.028462 | -2.61% | -3.41% | trail | `4gBdoceU...` |
| 10 | W_4gBdoc | 2026-01-27 15:00:00 | 2026-01-27 17:00:00 | $0.029232 | $0.028791 | -1.51% | -2.31% | trail | `4gBdoceU...` |

### Blue Chip Breakout (17 total trades)

| # | Token | Entry Time | Exit Time | Entry$ | Exit$ | P&L% | Net% | Exit Reason | Pair |
|---|-------|------------|-----------|--------|-------|------|------|-------------|------|
| 1 | W_4gBdoc | 2026-01-02 16:00:00 | 2026-01-03 07:00:00 | $0.035954 | $0.036552 | 1.66% | 0.86% | trail | `4gBdoceU...` |
| 2 | W_4gBdoc | 2026-01-03 16:00:00 | 2026-01-03 19:00:00 | $0.038298 | $0.038592 | 0.77% | -0.03% | trail | `4gBdoceU...` |
| 3 | W_4gBdoc | 2026-01-04 16:00:00 | 2026-01-05 04:00:00 | $0.039024 | $0.038050 | -2.50% | -3.30% | trail | `4gBdoceU...` |
| 4 | W_4gBdoc | 2026-01-05 16:00:00 | 2026-01-06 08:00:00 | $0.039007 | $0.039157 | 0.39% | -0.41% | trail | `4gBdoceU...` |
| 5 | W_4gBdoc | 2026-01-10 09:00:00 | 2026-01-10 23:00:00 | $0.037040 | $0.036981 | -0.16% | -0.96% | trail | `4gBdoceU...` |
| 6 | W_4gBdoc | 2026-01-11 12:00:00 | 2026-01-11 20:00:00 | $0.037684 | $0.036593 | -2.89% | -3.69% | trail | `4gBdoceU...` |
| 7 | W_4gBdoc | 2026-01-13 06:00:00 | 2026-01-13 22:00:00 | $0.037470 | $0.038959 | 3.97% | 3.17% | trail | `4gBdoceU...` |
| 8 | W_4gBdoc | 2026-01-14 15:00:00 | 2026-01-14 18:00:00 | $0.039675 | $0.038581 | -2.76% | -3.56% | trail | `4gBdoceU...` |
| 9 | W_4gBdoc | 2026-01-17 15:00:00 | 2026-01-18 07:00:00 | $0.037121 | $0.036008 | -3.00% | -3.80% | trail | `4gBdoceU...` |
| 10 | W_4gBdoc | 2026-01-24 08:00:00 | 2026-01-25 03:00:00 | $0.030421 | $0.029740 | -2.24% | -3.04% | trail | `4gBdoceU...` |

## 6. Methodology

### Data Collection
- Source: GeckoTerminal API (`api.geckoterminal.com/api/v2/networks/solana/pools/{pool}/ohlcv/hour`)
- Resolution: 1-hour candles, up to 1000 candles per token (~42 days)
- Token discovery: GeckoTerminal trending pools (memecoins), new pools (bags-like), hardcoded registry (bluechips)
- No synthetic data generation of any kind

### Simulation Model
- Entry: At candle close price + slippage (buy higher)
- Exit: SL/TP/Trailing Stop/Max Hold Expiry checked on each candle
- Slippage: Applied on both entry and exit (varies by strategy: 0.15%-1.5%)
- Fees: 0.25% per trade (entry + exit = 0.50% total)
- No compounding between trades (each trade uses fresh capital)

### Entry Signals
- **Momentum**: RSI(14) between 50-70 + green candle
- **Trend**: Price crosses above SMA(20) with 1.2x volume confirmation
- **Breakout**: Price breaks above 12-candle highest high with 1.5x volume
- **Mean Reversion**: Price below SMA(20)*0.99 + green recovery candle

### Verification
- Every trade has exact entry/exit timestamps (Unix ms)
- Every trade maps to a real GeckoTerminal pool address
- Anyone can verify by loading the pool on GeckoTerminal (`geckoterminal.com/solana/pools/{address}`) and checking the price at the given timestamps
