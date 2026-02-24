# Phase 2: Open Claw & Jupiter Perps Repair - Research

**Researched:** 2026-02-24
**Domain:** Solana Trading, Jupiter Perps API, Protocol Decoupling
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

No user constraints - all decisions at Claude's discretion. Working from ROADMAP and REQUIREMENTS to fix the Jupiter perpetuals bots, integrate Bags.fm/X signals, and expose Open Claw logic.
</user_constraints>

<research_summary>
## Summary

Researched the Jupiter Perpetuals API (`jup.ag`) and Solana trading bot patterns. The current bot is broken likely due to updates in the Jupiter v6 API or recent changes in their Perpetuals SDK, as well as common RPC rate limiting issues.

For decoupling the "Open Claw" algorithmic logic, the standard approach is to extract the Alpha-generation signal code into a functional, stateless SDK/package that takes market data and returns trade sizing/direction. Integrating external signals (e.g., Bags.fm, X/Twitter data) requires building robust, async event-listeners or scheduled pollers that feed into the Open Claw SDK.

**Primary recommendation:** Use the official Jupiter v6+ SDks (or verified Python ports like `solders`/`solana-py` coupled with REST/FlashAPI) for trade execution. Decouple the strategy logic into a discrete `open_claw` module serving as an SDK endpoint.
</research_summary>

<standard_stack>
## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| solana-py | >=0.30.0 | Solana RPC | Foundation for Solana interactions in Python |
| solders | >=0.18.0 | Solana serialization | Fast Rust-based core for Solana types |
| jupiter-python-sdk | - | Jupiter DEX | If available/maintained, or direct REST API requests |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| fastapi | >=0.100.0 | API Endpoint | To expose Open Claw as a local service |
| httpx | >=0.24.0 | Async HTTP | To poll/listen to Bags.fm or Twitter signals |
</standard_stack>

<architecture_patterns>
## Architecture Patterns

### Recommended Project Structure
```
bots/jupiter_perps/
├── client.py            # Jupiter API execution wrapper
├── state.py             # Wallet and position state management
└── runner.py            # The active bot loop connecting Open Claw to Jupiter

core/open_claw/
├── sdk.py               # The decoupled algo logic entrypoint
├── signal_ingestion.py  # Bags.fm / X integration listening
└── heuristics.py        # The actual trading math/logic
```

### Pattern 1: Async RPC Clients & Fallbacks
**What:** Solana RPCs are notoriously rate-limited or flaky.
**When to use:** Always when submitting transactions.
**Example:** Wrap `AsyncClient` calls with retries and multiple RPC fallback URIs.

### Pattern 2: Decoupled Strategy (Open Claw)
**What:** The `Open Claw` should be completely unaware of *how* the trade is executed. It just takes `(market_state, external_signals)` and outputs `(action, size, token)`.
</architecture_patterns>

<dont_hand_roll>
## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Jup routing | Custom pathfinding | Jupiter Quote API | Jupiter has the most liquidity and best paths |
| Tx Signing | Custom crypto | `solders.keypair` | Security and speed |
</dont_hand_roll>

<common_pitfalls>
## Common Pitfalls

### Pitfall 1: Nonce/Blockhash Expiration
**What goes wrong:** Transactions fail if the blockhash is too old before the network confirms it.
**How to avoid:** Always fetch the 'latest' blockhash right before signing the transaction and use `confirm_transaction` with appropriate commitment loops.

### Pitfall 2: API breaking changes
**What goes wrong:** Jupiter changes their margin or perpetuals API endpoints.
**How to avoid:** Heavily comment the endpoint URLs and maintain integration tests that ping the live API to ensure schemas match.
</common_pitfalls>

<code_examples>
## Code Examples

### Basic Jupiter API execution abstraction
```python
import httpx
from solana.rpc.async_api import AsyncClient

async def get_jup_quote(input_mint, output_mint, amount):
    url = f"https://quote-api.jup.ag/v6/quote?inputMint={input_mint}&outputMint={output_mint}&amount={amount}"
    async with httpx.AsyncClient() as client:
        resp = await client.get(url)
        return resp.json()
```
</code_examples>

<sota_updates>
## State of the Art (2024-2025)
Standard Solana DeFi wrappers heavily use the `solders` library for blazing-fast transaction building before broadcasting. Flashbots/Jito bundles are standard for avoiding MEV, but may be overkill for simple perpetual orders compared to direct priority fees.
</sota_updates>

<sources>
## Sources
- Solana Cookbook / solana-py docs
- Jupiter Station v6 API docs
</sources>

<metadata>
## Metadata
**Research date:** 2026-02-24
</metadata>
