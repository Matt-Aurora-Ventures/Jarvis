# Roadmap
*Phased execution plan*

## Phase 1: Core Backtesting Infrastructure [PyTorch]
- Target: Build the structural data pipeline and PyTorch modeling logic to accurately tune the algorithmic traders.
- Deliverables:
  - CoinGecko ingestion wrappers for historical resolution.
  - PyTorch training scripts covering all current sniper capabilities.
  - Automated continuous backtesting action to auto-tune hyper-parameters in production configurations.

## Phase 2: Open Claw & Jupiter Perps Repair
- Target: Fix the broken Jupiter perpetuals trader, integrate signals, and decouple the open-claw algorithmic logic for Solana.
- Deliverables:
  - Repaired perpetuals logic / bot execution.
  - Signal integration from external systems (Bags.fm/X).
  - Open Claw endpoint/UI or accessible SDK.

## Phase 3: Specialized Snipers (Alvara & TradFi)
- Target: Complete the Grok-managed basket integration (Alvara) and inject Traditional Finance options data triggers into the Solana trading pipeline.
- Deliverables:
  - Working Alvara Protocol ERC-7621 test and dev setup.
  - Solana "TradFi Options" strategy execution code without error looping.

## Phase 4: CI/CD & Production Push Automation
- Target: Implement strict push-to-live pipelines seamlessly to eliminate friction holding back the updated algorithms.
- Deliverables:
  - Automated deployment triggers for newly tuned `kr8tiv.web.app` and `jarvislife.cloud` bot logic based on test outcomes.

---
*Last Updated: 2026-02-24*
