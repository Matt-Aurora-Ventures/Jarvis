# 🚀 Jarvis Development - Quick Reference Card

## MCP Servers Status

| Server | Status | Purpose |
|--------|--------|---------|
| 🧠 Sequential Thinking | ✅ Active | Complex problem decomposition |
| 💾 Memory | ✅ Active | Persistent context across sessions |
| 📁 Filesystem | ✅ Active | File operations |
| 📚 Context7 | ✅ Active | Library documentation |
| 📓 NotebookLM | ✅ Active | Google NotebookLM research & docs |
| 🗄️ SQLite | ✅ Active | Database access |
| 🔍 Brave Search | ⚠️ Need key | Web search |
| 🐙 GitHub | 🔧 Optional | Repo access |

**Action**: Restart AI environment to activate servers

---

## Get Shit Done Commands

```bash
# Workflow
/gsd:init          # Start new project
/gsd:plan          # Create implementation plan
/gsd:execute       # Start building
/gsd:verify        # Run tests
/gsd:done          # Complete milestone

# Status
/gsd:status        # Current progress
/gsd:help          # All commands

# Quick mode (skip approvals)
/gsd:quick
```

**Launch**: `claude --dangerously-skip-permissions`

---

## Ralph Wiggum Loop

```
1. PLAN    → Review specs, define acceptance criteria
2. EXECUTE → Let AI work autonomously  
3. VERIFY  → Run tests, provide backpressure
4. REPEAT  → Next task
```

**Key**: Let Ralph Ralph (don't micromanage!)

---

## Solana Quick Reference

```python
# Program IDs (store in Memory!)
JUPITER_V6 = "JUP6LkbZbjS1jKKwapdHNy74zcZ3tLUZoi5QNyVTaV4"
RAYDIUM_AMM = "675kPX9MHTjS2zt1qfr1NYHuzeLXfQM9H24wFSUt1Mp8"
BAGS_PROGRAM = "BAGSGuhFcxRJMcZQj51Hn6zbFWRxiMQNZLwNLs49proo"
WSOL = "So11111111111111111111111111111111111111112"
USDC = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"

# Libraries
from solana.rpc.async_api import AsyncClient
from solders.keypair import Keypair
from aiogram import Bot, Dispatcher, Router
```

---

## Essential Documentation URLs

```
Solana RPC:     https://solana.com/docs/rpc
Jupiter V6:     https://hub.jup.ag/docs/apis/swap-api
Telegram API:   https://core.telegram.org/bots/api
aiogram:        https://docs.aiogram.dev/
BAGS.fm:        https://docs.bags.fm/
```

---

## Prompts to Use

### Store Context in Memory
```
"Remember for Jarvis project:
- Using aiogram 3.x for Telegram
- solana-py + solders for blockchain
- Helius RPC for low latency
- Jupiter V6 for swaps
- PostgreSQL for trade history"
```

### Use Sequential Thinking
```
"Use sequential thinking to design [complex feature].
Consider: [constraint 1], [constraint 2], [constraint 3]"
```

### Query Documentation
```
"Using Context7, show me how to [specific task] 
in [library name]"
```

### Reference Examples
```
"Search GitHub for [pattern] in [language] 
for [use case]"
```

### Query NotebookLM
```
"Search my NotebookLM notebooks for [topic]"
"Create a NotebookLM notebook from [these docs]"
"Generate an audio overview of [notebook name]"
```

---

## File Locations

```
.mcp.json                              # MCP configuration
.ralph-playbook/                       # Ralph methodology
.claude/                               # GSD system files
  ├── PROMPTS                          # System context
  ├── AGENTS.md                        # AI agent definitions
  └── IMPLEMENTATION_PLAN.md           # Build plan
docs/
  ├── AI_DEVELOPMENT_WORKFLOW_GUIDE.md # Full guide
  ├── MCP_SETUP_GUIDE.md               # MCP details
  └── SOLANA_TELEGRAM_LIBRARY_REFERENCE.md  # Code patterns
```

---

## Workflow for New Feature

```bash
# 1. Initialize (if not done)
/gsd:init

# 2. Describe feature
"Build [feature description]"

# 3. Review plan
cat .claude/IMPLEMENTATION_PLAN.md

# 4. Execute autonomously
/gsd:execute --quick

# 5. Verify
/gsd:verify
pytest
npm test

# 6. Complete
/gsd:done
git push
```

---

## Troubleshooting

**MCP not working?**
→ Restart AI environment completely

**GSD commands not found?**
→ Run: `npx get-shit-done-cc@latest --both --global`

**Brave search 422 error?**
→ Get free API key: https://brave.com/search/api/

**Memory not persisting?**
→ Check disk permissions in project dir

**Ralph getting stuck?**
→ Exit loop, update specs, restart

---

## Power Combo

```
1. Use Memory to store your stack
2. Use GSD to structure your work  
3. Use Ralph to execute autonomously
4. Use Sequential Thinking for hard problems
5. Use Context7 for accurate docs
```

**Result**: Ship 10x faster ⚡

---

## Next Actions

- [ ] Restart AI environment
- [ ] Verify: "Do you have sequential thinking?"
- [ ] Run: `/gsd:help` in Claude Code
- [ ] Read: `.ralph-playbook/README.md`
- [ ] Optional: Add Brave API key
- [ ] Start building! 🚀

---

**Need Help?**
- Full Guide: `docs/AI_DEVELOPMENT_WORKFLOW_GUIDE.md`
- GSD Discord: https://discord.gg/5JJgD5svVS
- Ralph Original: https://ghuntley.com/ralph/
