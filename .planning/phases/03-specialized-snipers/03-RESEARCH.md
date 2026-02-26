# Phase 03: Specialized Snipers (Alvara & TradFi) - Research

## 1. Context & Constraints
Phase 3 expands the scope of Jarvis to specialized targets outside the standard meme/bluechip scope on Solana. We face two distinct objectives with unique execution environments:
1. **Alvara Protocol (ERC-7621) Integration:** An EVM-based operation managing baskets/index funds using Alvara's standard.
2. **"TradFi" Solana Sniper Integration:** Integrating with the user's existing `jarvis-sniper` application which features specific presets (`xstock_intraday`, `prestock_speculative`, `index_leveraged`) targeting tokenized equities and indices on Solana.

The NotebookLM instances provided detailed context on Phase 1 and 2 (Jupiter / Open Claw), but omitted Phase 3 specifics. Therefore, this research relies on extrapolating the architectural requirements necessary to fulfill the roadmap while integrating tightly with the existing `.planning/codebase/` constraints and the active `jarvis-sniper` frontend app.

## 2. TradFi Sniper (Solana SPL Equities)

### Current State in `jarvis-sniper`
The `jarvis-sniper` frontend (deployed at `jarvislife.cloud`) defines "TradFi" via several active strategy presets in `src/app/tradfi-sniper/page.tsx` and the backtest engine `route.ts`.
- **Presets:** `xstock_intraday`, `xstock_swing`, `prestock_speculative`, `index_intraday`, `index_leveraged`.
- **Target Assets:** These are explicitly tracked as "xStocks", "preStocks", and "Indexes". They are SPL variants representing TradFi assets (e.g. tokenized SPY, tokenized equities).

### Integration Requirements
The Phase 3 directive is to put the *execution* of these options data triggers into the python execution layer, synchronizing with the `jarvis-sniper` UI.
- **Data Triggers:** We need a python ingestion module that polls real TradFi data (e.g., Yahoo Finance, Alpaca, or Polygon.io) to capture momentum, options flow, or DXY movements.
- **Execution Link:** When the TradFi data dictates a macro shift, the Python bot must execute the specific SPL token equivalent on Jupiter (e.g., longing a tokenized TSLA derivative on Solana).
- **Decoupling:** As requested by the user, we must "integrate with our tradfi sniper that already exists in our sniper app". This means the Python bot must load the exact hyper-parameters defined in `route.ts` (e.g. `stopLossPct: 4`, `takeProfitPct: 10` for `xstock_intraday`).

## 3. Alvara Protocol (ERC-7621)

### The Challenge
The Jarvis ecosystem is overwhelmingly centered around Solana (Rust/Anchor). The Alvara Protocol, however, fundamentally relies on the EVM-based ERC-7621 Tokenized Investment Fund standard.
- The `CONCERNS.md` noted: "Alvara Protocol basket management requires full connection".
- Grok AI was noted in the roadmap to be the "manager" of this basket.

### Structural Requirements
- **Web3.py Client:** We need an EVM execution module parallel to our Solana modules, utilizing `web3.py`.
- **ABI Parsing:** We must acquire the standard ERC-7621 ABI to mint, rebalance, and manage baskets.
- **Grok Intel Loop:** The logic must poll the `Grok` LLM to determine sector rotation (e.g. "rotate 20% to AI coins, 30% to L1s") and execute the transaction payload to the Alvara factory contract.
- **Isolation:** Because this requires EVM keys, it must utilize the `core.security.key_manager` isolated wallet logic similarly updated in Phase 2.

## 4. Execution Plan Strategy
- `03-01-PLAN.md`: Will dictate the step-by-step to scaffold the EVM dependencies and the Grok-to-Alvara rebalancing loop.
- `03-02-PLAN.md`: Will dictate the step-by-step to scaffold the `TradFi Data Fetcher`, link it to the Solana execution module, and expressly match the exact config limits exposed in `jarvis-sniper/src/app/api/backtest/route.ts`.
