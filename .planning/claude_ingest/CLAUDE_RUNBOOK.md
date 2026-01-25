Claude Coordination Runbook (Docker)

Bundle
- .planning/claude_ingest/claude_ingest_bundle.tgz
- .planning/claude_ingest/CLAUDE_TASK_PACKET.md

Purpose
- Provide Claude with canonical references and the current treasury trading refactor state.
- Validate refactor parity vs trading_legacy.py and identify any missing behaviors.

Steps
1) Extract bundle (optional)
   - tar -xzf .planning/claude_ingest/claude_ingest_bundle.tgz -C .

2) Ingest order (in Claude)
   - .planning/claude_ingest/Solana_and_telegram_libraries.txt
   - docs/CLAUDE_OPUS_INGEST_GUIDE.md
   - prd-demo-bot-enhancement.md
   - bots/treasury/trading_legacy.py
   - bots/treasury/trading/ (all modules)

3) Task packet to give Claude
   - .planning/claude_ingest/CLAUDE_TASK_PACKET.md

Expected output from Claude
- Architecture + module responsibilities
- Missing functions/behaviors in refactor
- Exact call-site updates needed
- Testing plan (unit/integration/devnet)
- Latency + tx landing + recovery plan

Notes
- Helius is primary RPC.
- bags.fm primary execution; Jupiter fallback.
- Cite RPC methods and API references where required.
