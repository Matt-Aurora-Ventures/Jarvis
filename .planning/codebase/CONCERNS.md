# Concerns and Technical Debt

## Current Issues & Pain Points
- **Backtesting Deficiencies**: The backtesting engine does not execute correctly for the trading logic (`kr8tiv.web.app` and `jarvislife.cloud` algorithmic logic). It lacks the proper PyTorch-enabled tuning required to backtest the sniper components on CoinGecko data.
- **Inoperative Bots/Code**:
  - The grok-managed basket for Alvara Protocol is currently non-functional.
  - The Jupiter perpetuals automated trader and signal system does not work yet.
- **TradFi Sniper Injections**: TradFi sniper execution is completely isolated and not executing correctly. It lacks injections to options trading mechanisms on Solana (none are currently available/liquid for standard trading in the bot's wiring).

## Areas Needing Improvement
- System-wide improvement to the sniper performance.
- Elevate backend to correctly push newly tuned algorithm code straight to GitHub and production environments.

## Security Considerations
- Managing multiple high-value wallets (Solana trading).
- Handling API keys across multiple decoupled agents.
