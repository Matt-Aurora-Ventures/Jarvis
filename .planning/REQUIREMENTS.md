# Requirements
*Feature specification and scope boundaries*

## Table Stakes (Must Have)
- **PyTorch Backtesting Suite**: CoinGecko API data integration, param tuning algorithms, complete coverage of current execution engine logic.
- **TradFi Sniper Infiltration**: Connect traditional options models/injections safely to Solana trading APIs.
- **Grok Basket Fixes**: Alvara Protocol ERC-7621 logic repaired, LEL implementations corrected for live usage.
- **Jupiter Perpetuals Fixes**: Integrate missing logic/connectors for the perpetuals automated trader and signal logic to correctly dispatch actions.

## Differentiators (Strategic Advantage)
- **Open Claw Autonomous Extension**: Allowing the algorithmic trader to be published for other users on Solana and Jupiter seamlessly.

## Anti-Features (Deliberately Not Building)
- **Centralized Brain System**: Remaining decentralized inside the mesh (Docker-composed decoupled bots), avoiding monolithic architectural rewrites.
- **Random Backtests**: Using only high-fidelity PyTorch model implementations instead of basic historical price sweeping.

## Dependencies & Risks
- **Dependency**: TradFi options on Solana suffer from low liquidity and fragmented APIs; these must be carefully verified.
- **Risk**: API rate limits from CoinGecko during extensive PyTorch multi-param batch backtesting runs.
- **Risk**: Alvara / Grok AI latency matching during live action trading.

---
*Last Updated: 2026-02-24*
