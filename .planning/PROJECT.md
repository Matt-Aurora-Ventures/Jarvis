# Project Context

## Overview
Elevate and repair the complete trading ecosystem across multiple platforms (Jarvis, kr8tiv.web.app, jarvislife.cloud). The project focuses on overhauling the simulation/backtesting engine via PyTorch, restoring broken execution integrations (TradFi sniper, Jupiter perps, Alvara Protocol basket), and exposing a public algorithmic trading suite (OpenClaw) on Solana.

## Core Value
A hardened, battle-tested, AI-driven algorithmic trading engine capable of hyper-parameter tuning and reliable live execution on multiple chains/protocols.

## Constraints
- Must integrate heavily with existing data (CoinGecko API) for tuning.
- Must follow the existing decoupled Multi-Agent / Autonomous Mesh architecture.

## Scale
- **Milestone:** System Remediation and Advanced Architecture Overhaul
- **Timeframe:** Immediate

## Active Requirements
- [ ] Implement robust PyTorch-based backtesting and tuning algorithms using CoinGecko API history.
- [ ] Repair and deploy the Grok-managed basket for Alvara Protocol (ERC-7621).
- [ ] Implement and test the Jupiter perpetuals automated trader and signal system.
- [ ] Expose Open Claw algorithmic trading tools for Solana and Jupiter for public usage.
- [ ] Complete end-to-end rewrite/injection of the TradFi options sniper for Solana tooling.
- [ ] Ensure all working, tested code is pushed to GitHub and deployed live automatically.

## Out of Scope
- Throwing away the entire existing Autonomous Mesh framework (needs to run within the current modular environment).

## Key Decisions
| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Parallel Execution | Deep/Comprehensive scoping to rapidly fix and elevate the components | Pending |
| PyTorch Overhaul | Standard heuristic backtesting is insufficient for hyperparameter tuning required for production scale | Pending |

---
*Last updated: 2026-02-24 after initialization*
