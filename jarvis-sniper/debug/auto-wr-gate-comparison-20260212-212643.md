# Auto WR Gate Comparison (Real Data)

Generated: 2026-02-12 21:26:43 -06:00

## Run Context
- Source run: `npx tsx scripts/real-backtest.ts`
- Data source: GeckoTerminal OHLCV (real market candles)
- Scope requested: memecoin + bags auto mode
- Upstream constraints observed: GeckoTerminal `new_pools` returned HTTP 429; most tracked pools returned 0 candles.
- Effective universe recovered: 1 token (`W`, bluechip), 1000 candles.
- Memecoin/bags datasets recovered: 0 tokens.

## Cohort Results (Memecoin + Bags)

| Cohort | Net P&L | Trades | Win Rate | Max Drawdown | Profit Factor | Sharpe | No-eligible cycles |
|---|---:|---:|---:|---:|---:|---:|---:|
| Baseline (no WR gate) | N/A (no memecoin/bags fills) | 0 | N/A | N/A | N/A | N/A | 100% (proxy) |
| Strict 70 only | N/A | 0 | N/A | N/A | N/A | N/A | 100% (proxy) |
| Loose 50 only | N/A | 0 | N/A | N/A | N/A | N/A | 100% (proxy) |
| Adaptive 70→50 | N/A | 0 | N/A | N/A | N/A | N/A | 100% (proxy) |

## Findings
- This run does not provide enough memecoin/bags coverage to compare 70 vs 50 vs adaptive behavior.
- Because there were no memecoin/bags trades, all WR-gated cohorts collapse to the same outcome: no eligible strategy execution evidence.
- The limiting factor here is dataset availability/rate-limit quality, not WR-threshold logic.

## Recommendation
- Keep the product default as adaptive `70→50` (Wilson95 lower-bound, min 1000 trades) in code.
- Treat this specific experiment as **inconclusive** due to missing memecoin/bags data.
- Re-run comparison once upstream data collection is healthy (or use cached campaign artifacts with >=1000 trades/strategy).

## Notes
- I also attempted direct `/api/backtest` route execution from the current shell session; calls exceeded long timeouts and did not return usable summary payloads.
- This artifact documents the completed run and why the decision signal is currently unavailable from live data.
