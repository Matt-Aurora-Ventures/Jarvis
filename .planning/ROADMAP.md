# Roadmap
*Phased execution plan*

## Phase 1: Core Backtesting Infrastructure [PyTorch]
- Target: Build the structural data pipeline and PyTorch modeling logic to accurately tune the algorithmic traders.
- Deliverables:
  - `CoinGeckoFetcher` ingestion wrapper for historical resolution.
  - PyTorch/ML model and tuning scaffolds for sniper capabilities (`base_sniper`, `sentiment_finetuner`, Optuna tuning modules).
  - Continuous algo-loop workflow for real-data backtest refresh and tuning artifact generation.

## Phase 2: Open Claw & Jupiter Perps Repair
- Target: Fix the broken Jupiter perpetuals trader, integrate signals, and decouple the open-claw algorithmic logic for Solana.
- Deliverables:
  - `JupiterPerpsAnchorClient` + runner execution path for perpetuals orchestration.
  - Signal intake and strategy mapping paths for external/macro intel integration.
  - Accessible `OpenClawSDK` entrypoint for decoupled algorithmic logic.

## Phase 3: Specialized Snipers (Alvara & TradFi)
- Target: Complete the Grok-managed basket integration (Alvara) and inject Traditional Finance options data triggers into the Solana trading pipeline.
- Deliverables:
  - `GrokAllocator` basket-weight validation and Alvara runner wiring for ERC-7621-oriented flows.
  - TradFi preset mapping + execution runner with guarded non-execution paths for neutral/invalid conditions.

## Phase 4: CI/CD & Production Push Automation
- Target: Implement strict push-to-live pipelines seamlessly to eliminate friction holding back the updated algorithms.
- Deliverables:
  - CI gates (`ci.yml`, `python-testing.yml`) aligned with Python and web validation surfaces.
  - Deploy pipelines for `kr8tiv.web.app` and `jarvislife.cloud`, with production release flow tied to validated test gates.

---
*Last Updated: 2026-02-24*
