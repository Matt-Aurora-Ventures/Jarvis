# Build Streamlining Plan

This document captures how the Jarvis build is being streamlined while keeping the **wallet** experience standalone and safe for public use.

## Goals

- Keep the wallet experience decoupled from the OS core.
- Ensure research automation produces **proposals**, not direct changes.
- Make each subsystem replaceable without breaking the stack.

## System Boundaries

### 1) Wallet (Standalone)
- **Scope:** user wallets, balances, funding/withdrawals, trading confirmations, demo mode.
- **Runtime:** Telegram public bot (`tg_bot/`) + wallet services (`core/public_user_manager.py`, `core/wallet_service.py`).
- **Rule:** wallet flows must remain functional even if the OS stack evolves.

### 2) OS Core (Jarvis Runtime)
- **Scope:** orchestration, memory, automation, and prompt/control layers.
- **Rule:** OS core can evolve independently as long as wallet API contracts remain stable.

### 3) Research Subsystem
- **Scope:** AI-Researcher jobs → versioned artifacts → change proposals.
- **Rule:** research outputs are **gated**; no auto-merge.

## Streamlining Checklist

1) **Separate runtime boundaries**
   - wallet services and bot flows stay in `tg_bot/` + `core/` wallet modules
   - OS orchestration stays in `core/` + `prism/` + `workflow_engine/`

2) **One-way integration**
   - wallet can consume research artifacts, but research never calls wallet execution directly

3) **Deterministic changes**
   - research outputs produce proposals + diffs + tests → require approval

4) **Versioned artifacts**
   - each research job persists a report, claim set, and proposal (if any)

## Immediate Actions (Next Pass)

- Add stable wallet API contracts (documented interfaces)
- Add minimal integration tests for wallet-only flows
- Add CI job to validate research artifact schema

## Principle

**Public wallet experience remains a safe, standalone sandbox** while the OS builds out behind it.
