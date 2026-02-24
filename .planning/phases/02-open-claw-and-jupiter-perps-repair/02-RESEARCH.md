# Phase 2: Open Claw & Jupiter Perps Repair - Research

**Researched:** 2026-02-24
**Domain:** Solana Trading, Jupiter Perps Anchor API, Event-driven Agents, Bifurcated Processing
**Confidence:** HIGH

<user_constraints>
## User Constraints (from NotebookLM context)

**CRITICAL:**
- Open Claw must NEVER hold signing keys directly, it should act as an autonomous notification endpoint and SDK.
- Private Keys must be isolated using `core.security.key_manager` which interfaces securely without direct `.env` exposure if possible.
- Jupiter Perps MUST NOT use standard REST (as the v6 API is WIP for perps). It must interact natively with the on-chain contract via Anchor Python (`AnchorPy`) and `solders`.
</user_constraints>

<research_summary>
## Summary

Extensive research across the NotebookLM documentation reveals a highly complex system.
1. **Open Claw / Signals:** Signal generation uses a **Bifurcated Intelligence Model** where a slow macro loop (LangGraph) builds "Policy Envelopes" detailing bias and maximum leverage, while a micro-loop evaluates sub-800ms websocket ticks and uses a fast Grok API check for breaking invalidations prior to executing.
   - Signal selection utilizes Discounted Thompson Sampling (dTS) alongside a Wilson Confidence Interval threshold to route capital dynamically.
2. **Jupiter Perpetuals:** The Jupiter Perps system uses a "Two-Transaction Keeper Model". The user submits a `PositionRequest PDA`. An off-chain Jupiter Keeper fills the order. Because of this, the local database easily hallucinates broken positions. A **Reconciliation Loop** must actively scan all 9 possible PDAs (3 longs, 6 shorts) for the wallet to delete ghost/unfilled positions.

**Primary recommendation:** Build `bots/jupiter_perps/client.py` as an `AnchorPy` wrapper around `PERPHjGBqRHArX4DySjwM6UJHiR3sWAatqfdBS2qQJu`. Implement the bifurcated engine for Open Claw in `core/open_claw/signals/`.
</research_summary>

<standard_stack>
## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| anchorpy | >=0.20.0 | Solana Smart Contracts | Required to derive PDAs and decode Jupiter Perps IDL |
| solders | >=0.18.0 | Solana serialization | Fast Rust-based core for building transactions directly |
| scipy/numpy | >=1.11 | Statistical Math | For evaluating Wilson Confidence and dTS equations |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pydantic | >=2.0 | Schema Enforcement | Parsing Webhooks & Grok Outputs restrictively |
| tweepy | >=4.14 | Twitter X API | Async streaming of Twitter signals for the Micro Engine |
</standard_stack>

<architecture_patterns>
## Architecture Patterns

### Pattern 1: Event-Sourced Reconciliation Loop (Jupiter Perps)
**What:** The bot DB state diverges when a Jupiter Keeper fails to execute the request PDA.
**When to use:** Continuously running in the background as a polling task.
**Example:**
```python
async def reconciliation_loop():
    while True:
        # Enumerate 9 possible Position PDAs per wallet
        for custody, collateral in CUSTODY_PAIRS:
            position_pda = derive_position_pda(wallet, custody, collateral)
            chain_pos = await rpc.get_account_info(position_pda)
            local_pos = db.get_position_by_pda(position_pda)

            if local_pos and not chain_pos:
                mark_position_closed(local_pos, reason="chain_divergence")
```

### Pattern 2: Bifurcated Intelligence Model
**What:** Split slow API tasks (LangGraph/Context generation) from fast sub-second triggers.
**When to use:** Passing signals into the Open Claw heuristic engine.
**Structure:**
- `Macro Engine` -> Emits signed `PolicyEnvelope(bias, max_lev, validation_price)` every few hours.
- `Micro Engine` -> Checks immediate tick data + `Grok-4-1-fast-reasoning` News check before taking action.
</architecture_patterns>

<dont_hand_roll>
## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Jup Perps Tx | Direct buffer structs | AnchorPy `Program.fetch_idl` | Automatically derives the correct instruction formats |
| Signal Gating | Random thresholds | scipy `stats.proportion_confint` (Wilson Interval) | Statistically sound method for penalizing low-data samples |
</dont_hand_roll>

<common_pitfalls>
## Common Pitfalls

### Pitfall 1: Ghost Position PDA Leaks
**What goes wrong:** Open requests expire after 45 seconds, but the DB thinks it's open, locking capital constraints.
**How to avoid:** The reconciliation loop must be the ultimate source of truth, forcibly closing positions from the DB if `get_account_info` of the PDA is empty.

### Pitfall 2: RPC Bottlenecks
**What goes wrong:** Jupiter Perps reqs drop because of 200ms ping latency over normal REST.
**How to avoid:** Use Jito Bundles or high priority tips (`0.0002 SOL`) alongside an optimized co-located sender API if available.
</common_pitfalls>

<code_examples>
## Code Examples

### Deriving Jupiter Position PDA
```python
from anchorpy import Program, Provider, Wallet
from solders.pubkey import Pubkey

def derive_position_pda(trader_wallet, custody, collateral, program_id):
    pda, nonce = Pubkey.find_program_address(
        [bytes(trader_wallet), bytes(custody), bytes(collateral)],
        program_id
    )
    return pda
```

### Micro Engine Breaking News Gate
```python
async def breaking_news_check(market: str, xai_client) -> bool:
    response = await xai_client.responses.create(
        model="grok-4-1-fast",
        tools=[{"type": "x_search"}],
        input=f"Is there any major breaking news about {market} in the last 5 minutes that would cause a significant price move? Respond with SAFE or DANGER only."
    )
    return "SAFE" in response.output_text.upper()
```
</code_examples>
