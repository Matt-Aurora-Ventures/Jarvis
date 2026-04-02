# Credits & Attribution

## dexbotsdev — DeFi Trading Infrastructure

Several architectural patterns in the Jarvis sniper were inspired by the open-source
work of **dexbotsdev**, a Java Enterprise Architect with 21+ years of experience
building blockchain trading infrastructure.

**GitHub**: https://github.com/dexbotsdev

### Specific Patterns Borrowed

| Pattern | Source Repo | Where Used in Jarvis |
|---------|------------|---------------------|
| Multi-SWQoS provider failover (race transactions across Jito, NextBlock, etc.) | [sol-trade-sdk](https://github.com/dexbotsdev/sol-trade-sdk) (`src/swqos/mod.rs`, `SWQoSTrait`) | `src/lib/swqos-router.ts` |
| Fast 10s confirmation polling with 1s intervals | [sol-trade-sdk](https://github.com/dexbotsdev/sol-trade-sdk) (`src/swqos/default.rs`, `wait_for_confirm`) | `src/lib/transaction-confirm.ts` |

### Key Repos We Studied

- **[sol-trade-sdk](https://github.com/dexbotsdev/sol-trade-sdk)** (541 commits, Rust)
  High-performance Rust SDK for PumpFun, PumpSwap, Raydium, Meteora trading.
  Notable for: 9+ MEV providers, copy trading, middleware pipeline, durable nonces,
  Address Lookup Tables, QUIC support via Astralane.

- **[solana-trading-sdk](https://github.com/dexbotsdev/solana-trading-sdk)** (Rust)
  Universal Solana trading SDK with multi-DEX trait abstraction and 6 SWQoS providers.

- **[defi-auto-trading-bot](https://github.com/dexbotsdev/defi-auto-trading-bot)** (Python + Rust)
  EVM-focused sniper with concurrent task execution pattern (`asyncio.gather`)
  that informed our approach to parallel wallet + backtest operations.

Thank you to dexbotsdev for making these patterns available to the community.
