# Agent Coordination - Jarvis (GSD + Ralph + MCP)

Purpose
- Provide a single coordination note for Claude/Codex agents working on Jarvis V1.
- Keep all agents aligned with GSD artifacts, canonical refs, and the Ralph loop.

Must-Read (ingest order)
1) .planning/claude_ingest/Solana_and_telegram_libraries.txt
2) docs/CLAUDE_OPUS_INGEST_GUIDE.md
3) prd-demo-bot-enhancement.md
4) bots/treasury/trading_legacy.py
5) bots/treasury/trading/ (all modules)
6) .planning/PROJECT.md
7) .planning/STATE.md
8) .planning/ROADMAP.md
9) .planning/REQUIREMENTS.md

Canonical Stack (Python)
- Telegram: aiogram (default). Alternative: python-telegram-bot.
- Solana: solana-py + solders. Optional: anchorpy for IDL programs.

Primary Reference Policy
- Use only the canonical sources in Solana_and_telegram_libraries.txt for primary citations.
- RPC method use must cite Solana RPC docs (HTTP/WS).
- Bags.fm is primary execution; Jupiter is fallback.

Ralph Wiggum Loop
- PLAN: confirm target task against .planning/STATE.md and phase plans.
- EXECUTE: implement minimal change set, preserve existing behavior.
- VERIFY: run tests or targeted checks; record outcomes.

Docker + MCP
- Docker MCP toolkit is available via `docker mcp`.
- System-wide client connections are active (codex + claude-code) via Docker MCP gateway.
- Use `docker mcp server ls` to list enabled MCP servers.
- If tools list hangs, proceed with local `.mcp.json` and project docs.

GSD Docs Index
- .gsd-spec.md
- docs/gsd-claude-combined.md (snapshot)
- gsd_tmp/GSD-STYLE.md
- gsd_tmp/agents/gsd-*.md

Notes
- Respect ongoing background agents listed in .planning/STATE.md.
- Keep output ASCII-only.
