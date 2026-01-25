Claude Coordination Packet - Jarvis (Solana + Telegram + Bags)

Purpose
- Provide Claude with a canonical build corpus and a scoped task packet.
- Enforce correctness, security, production reliability, and DEX-only trading.

Ingest Order (use this order)
1) C:\Users\lucid\OneDrive\Desktop\prompts\development\Solana and telegram libraries.txt
2) docs/CLAUDE_OPUS_INGEST_GUIDE.md
3) prd-demo-bot-enhancement.md
4) bots/treasury/trading_legacy.py
5) bots/treasury/trading/ (all modules)

Hard Requirements
- Prefer canonical sources listed in the libraries document.
- Helius RPC is primary.
- bags.fm is primary execution; Jupiter is fallback.
- For any RPC calls: cite exact method docs in the response.
- For swaps: use Jupiter Swap API (OpenAPI) and Bags API docs.
- For price feeds: Pyth docs.
- For Telegram: Telegram Bot API + selected Python framework docs.

Task Packet (current)
A) Audit refactor status
- Verify that bots/treasury/trading_legacy.py behavior is preserved in bots/treasury/trading/.
- Identify any missing functions, classes, or behaviors in the refactor.
- Verify exports remain backward compatible: bots.treasury.trading.*

B) Module layout validation
Target 5 logical modules (plus types/constants/logging helpers):
- trading_core.py: public entry points, orchestrator surface
- trading_execution.py: bags + Jupiter execution + swap/signal logic
- trading_positions.py: position state and persistence
- trading_risk.py: risk limits + TP/SL calculations
- trading_analytics.py: PnL + reporting

C) Update imports/call sites
- Ensure all imports point to bots.treasury.trading package.
- Remove references to bots/treasury/trading_legacy.py except archival use.

Deliverable Format
1) Architecture (components + responsibilities + data flow)
2) Critical dependencies + exact references
3) Security model (keys, signing, permissions, rate limits, abuse protection)
4) Minimal repo scaffold (folders + key modules)
5) Implementation plan with milestones
6) Testing plan (unit + integration + devnet) and runbooks
7) Trading bots: latency plan + tx landing plan + recovery logic

Notes
- Keep changes minimal: refactor only, preserve behavior.
- Use ASCII-only output.
