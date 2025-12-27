# DEX Trading Bots - Low Capital Playbook

## Focus
- Build DEX-only bots for low-fee chains with real volume.
- Start with tiny capital; prioritize research, backtests, and paper trading.
- Favor simple strategies that survive fees and slippage.

## Target Chains and DEXs
- Solana: Jupiter (aggregator), Raydium, Orca, Phoenix (CLOB).
- Base: Aerodrome, Uniswap V3.
- BNB Chain: PancakeSwap, Thena.
- Arbitrum/Optimism/Polygon: Uniswap V3, Camelot, Velodrome, QuickSwap.
- Monad: early ecosystem; monitor docs and DEX launches.
- Abstract: early ecosystem; monitor docs and DEX launches.

## Data + APIs to Start With
- Jupiter quote/price APIs for Solana routing (aggregator).
- DexScreener public API for live pairs and prices.
- GeckoTerminal API for pool data and candles.
- 0x / 1inch aggregator APIs for EVM quote routes (free tiers).
- Hyperliquid data snapshots for quick backtesting and signal tests.

## Architecture (Minimum Viable Bot)
1. Data ingestion (prices, pools, spread, volume).
2. Strategy module (signal generation).
3. Risk module (position sizing, max loss, daily stop).
4. Execution module (quotes -> tx build -> send).
5. Logging + metrics (PnL, win rate, slippage, fees).

## Low-Capital Strategy Starters
- Simple MA cross on liquid pairs with strict fee threshold.
- Mean reversion on stable pairs (avoid deep slippage).
- Quote-based scalps: only trade if spread > fees + slippage buffer.
- CLOB maker orders (Phoenix/limit orders) when rebates exist.
- Backtest on 30-day data; only go live with proven edge.

## How to Build (First Pass)
- Pick one chain + one DEX to avoid complexity.
- Use read-only APIs for data and simulate locally.
- Use a small wallet with a strict cap (e.g., $5-$50).
- Only send transactions when expected edge > 2x fees.
- Keep bot interval slow (minutes, not seconds) to reduce gas churn.

## Guardrails for Tiny Funding
- Max trade size 1-2% of capital.
- Daily loss limit 3-5% of capital.
- Hard stop after 3 losing trades in a row.
- Avoid illiquid pairs; stick to top volume tokens.

## Focused Research Questions
- Which DEX APIs are free and reliable per chain?
- What slippage thresholds keep trades profitable with low capital?
- Can Phoenix or CLOBs offer lower fees for micro orders?
- Which pairs have the best volume-to-slippage ratio?

## Sources to Track
- Solana Docs: https://docs.solana.com
- Jupiter Docs: https://station.jup.ag/docs/apis
- Raydium Docs: https://docs.raydium.io
- Orca Docs: https://docs.orca.so
- Base Docs: https://docs.base.org
- Aerodrome Docs: https://docs.aerodrome.finance
- BNB Chain Docs: https://docs.bnbchain.org
- PancakeSwap Docs: https://docs.pancakeswap.finance
- Uniswap Docs: https://docs.uniswap.org
- DexScreener API: https://docs.dexscreener.com
- GeckoTerminal: https://api.geckoterminal.com
- 0x API: https://0x.org/docs
- 1inch API: https://portal.1inch.dev/documentation
- Hyperliquid API: https://hyperliquid.xyz

## Next Actions for Jarvis
- Scout free API endpoints and log rate limits per chain.
- Pull 30-day Hyperliquid data and run a baseline backtest.
- Build a minimal Solana bot using Jupiter quotes + dry-run execution.
- Summarize DEX fees and slippage thresholds for each chain.
