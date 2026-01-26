# AI Development Workflow Guide for Jarvis
## MCP Servers + Get Shit Done + Ralph Wiggum Technique

---

## 🎯 Overview

This guide integrates three powerful systems for AI-assisted development:

1. **MCP Servers** - Enhanced AI capabilities (memory, sequential thinking, documentation)
2. **Get Shit Done (GSD)** - Spec-driven development workflow for Claude Code
3. **Ralph Wiggum Technique** - Methodology for autonomous AI development loops

---

## ✅ Installation Status

### MCP Servers - ✅ CONFIGURED
- **Sequential Thinking** - ✅ Installed
- **Memory (Persistent Context)** - ✅ Installed  
- **Filesystem** - ✅ Installed
- **Context7 (Library Docs)** - ✅ Installed
- **SQLite** - ✅ Installed
- **Brave Search** - ⚠️ Needs API key
- **GitHub** - 🔧 Optional (recommended)

**Next Step**: Restart your AI coding environment to load MCP servers.

### Get Shit Done - ✅ INSTALLED
- Installed globally to `~\.claude` and `~\.config\opencode`
- Version: 1.9.13
- Available commands: `/gsd:help`

**Next Step**: Launch Claude Code and run `/gsd:help`

### Ralph Playbook - ✅ CLONED
- Location: `C:\Users\lucid\OneDrive\Desktop\Projects\Jarvis\.ralph-playbook`
- Contains methodology docs and reference implementations

---

## 🚀 Quick Start

### 1. Restart Your AI Environment
After MCP installation, completely restart Claude Desktop, Cursor, or your AI coding assistant.

### 2. Verify MCP Servers
Ask your AI assistant:
```
"Do you have access to sequential thinking and memory servers?"
```

### 3. Launch GSD Workflow (in Claude Code)
```
/gsd:help
```

Then initialize your project:
```
/gsd:init
```

---

## 📚 System Comparison

| Feature | MCP Servers | Get Shit Done | Ralph Wiggum |
|---------|-------------|---------------|--------------|
| **Purpose** | Enhance AI capabilities | Structure development workflow | Autonomous execution methodology |
| **Level** | Tool/Infrastructure | Workflow/Process | Philosophy/Approach |
| **Best For** | All AI interactions | Claude Code projects | Complex autonomous tasks |
| **Integration** | Always active | Command-based | Loop-based automation |

---

## 🎓 Get Shit Done (GSD) Workflow

### What It Is
A context engineering layer that makes Claude Code reliable through:
- **Meta-prompting** - Structured prompts that guide AI effectively
- **XML formatting** - Clear, parseable instructions
- **Spec-driven development** - Build from clear specifications
- **Atomic git commits** - Track progress granularly

### Core Workflow

#### Phase 1: Initialize
```
/gsd:init
```
Sets up project structure with `.claude/` directory containing:
- `AGENTS.md` - Specialized AI agent definitions
- `PROMPTS` - System prompts and context
- `IMPLEMENTATION_PLAN.md` - Your build plan

#### Phase 2: Discuss
Describe what you want to build. GSD extracts:
- User stories / Jobs To Be Done (JTBD)
- Core features
- Technical requirements
- Success criteria

#### Phase 3: Plan
GSD generates `IMPLEMENTATION_PLAN.md`:
- Architecture decisions
- Component breakdown
- File structure
- Verification criteria

Review and approve before proceeding.

#### Phase 4: Execute
Claude Code builds according to spec:
- Atomic git commits per feature
- Self-verification after each step
- Context maintained across sessions

#### Phase 5: Verify
Automated validation:
- Run tests
- Check build status
- Verify functionality
- Report issues

#### Phase 6: Iterate
Repeat for next milestone until complete.

### Key Commands

```bash
# Core workflow
/gsd:init          # Initialize project
/gsd:plan          # Generate implementation plan
/gsd:execute       # Start building
/gsd:verify        # Run verification
/gsd:done          # Mark milestone complete

# Navigation
/gsd:status        # Current progress
/gsd:context       # Show project context
/gsd:next          # Next task

# Utilities
/gsd:help          # Show all commands
/gsd:quick         # Skip approval steps (fast mode)
```

### Running Without Permission Prompts (Recommended)

Launch Claude Code with:
```bash
claude --dangerously-skip-permissions
```

Or add to `.claude/settings.json`:
```json
{
  "permissions": {
    "allow": [
      "Bash(date:*)",
      "Bash(git add:*)",
      "Bash(git commit:*)",
      "Bash(git status:*)",
      "Bash(npm:*)",
      "Bash(python:*)"
    ]
  }
}
```

---

## 🎯 Ralph Wiggum Technique

### What It Is
The "Ralph Wiggum Technique" is a methodology for letting AI autonomously execute complex development tasks through continuous feedback loops.

**Origin**: Named after the Simpsons character who says "I'm helping!" - the AI works autonomously while you supervise.

**Core Principle**: *Let Ralph Ralph* - Don't micromanage, let the AI work within defined guardrails.

### The Three-Phase Loop

```
┌─────────────────────────────────────┐
│  1. PLAN                            │
│  - Review IMPLEMENTATION_PLAN.md    │
│  - Identify next task               │
│  - Define acceptance criteria       │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│  2. EXECUTE (Let Ralph Ralph)       │
│  - AI builds autonomously           │
│  - Self-corrects errors             │
│  - Follows spec exactly             │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│  3. VERIFY                          │
│  - Run tests                        │
│  - Check against acceptance criteria│
│  - Provide backpressure if needed   │
└──────────────┬──────────────────────┘
               │
               ▼
        [Loop continues]
```

### Key Principles

#### 1. Context Is Everything
- Maintain comprehensive `PROMPTS` file with project context
- Use `AGENTS.md` to define specialized AI personas
- Store specs in structured `specs/` directory
- Let MCP Memory server remember key decisions

#### 2. Steering Ralph (Backpressure)
Don't interrupt the loop. Instead, provide feedback via:
- **Test failures** - Let failing tests guide corrections
- **Acceptance criteria** - Define clear "done" conditions
- **Spec updates** - Refine specs between loops, not during

#### 3. Let Ralph Ralph
Resist urge to micromanage:
- ✅ Set clear boundaries
- ✅ Define success criteria
- ✅ Review completed work
- ❌ Don't interrupt mid-task
- ❌ Don't hand-hold every decision
- ❌ Don't switch contexts rapidly

#### 4. Move Outside the Loop
For major changes:
- Stop the loop
- Update specs/plan
- Restart with new context

Don't try to steer mid-execution.

### File Structure for Ralph

```
.ralph-playbook/          # Reference methodology (installed)
├── PROMPTS               # System prompts
├── AGENTS.md            # AI agent definitions  
├── loop.sh              # Automation script
└── README.md            # Full methodology

your-project/
├── .claude/             # GSD system files
│   ├── AGENTS.md
│   ├── PROMPTS
│   └── IMPLEMENTATION_PLAN.md
├── specs/               # Feature specifications
│   ├── user-auth.md
│   ├── trading-bot.md
│   └── telegram-bot.md
├── src/                 # Source code
└── tests/               # Test suite
```

### Example Ralph Loop

```bash
# 1. Set context
cat IMPLEMENTATION_PLAN.md | head -n 50

# 2. Start autonomous loop
while true; do
  # AI reads next task from plan
  # AI executes task
  # AI commits code
  # AI runs tests
  
  # If tests pass, continue
  # If tests fail, AI debugs and retries
  # If stuck, exit loop for human intervention
done
```

---

## 🔄 Combining All Three Systems

### For Solana Trading Bot Development

#### 1. Use MCP Memory to Store Context
```
Store in Memory:
- Jupiter V6 API endpoint: https://quote-api.jup.ag/v6
- Helius RPC: wss://your-endpoint
- Program IDs: JUPITER_V6, RAYDIUM_AMM, etc.
- Trading strategy parameters
- Risk limits
```

#### 2. Use GSD for Structure
```
/gsd:init

# Describe project
"Build a Solana trading bot that:
- Monitors Jupiter for arbitrage opportunities
- Executes trades via Telegram commands
- Uses aiogram for Telegram
- Uses solana-py for blockchain interaction"

# GSD generates IMPLEMENTATION_PLAN.md
# Review and approve

/gsd:execute
```

#### 3. Use Ralph for Autonomous Execution
```
# Let AI work autonomously on each component:
- Set up Solana RPC client
- Implement Jupiter swap integration  
- Build Telegram bot handlers
- Add trading strategy logic
- Write tests

# Provide backpressure via test failures
# Let Memory server remember patterns
# Let Sequential Thinking solve complex design decisions
```

### Example Workflow

```bash
# Day 1: Planning
/gsd:init
# Discuss requirements
# Review generated IMPLEMENTATION_PLAN.md

# Day 2-5: Execution (Ralph mode)
/gsd:execute --quick

# AI autonomously builds:
# - Telegram bot setup ✓
# - Solana client integration ✓  
# - Jupiter API wrapper ✓
# - Trade execution logic ✓
# - Error handling ✓

# You verify periodically:
/gsd:verify
git log --oneline  # Review atomic commits

# Day 6: Verification
/gsd:verify
# Manual testing
# Deploy to VPS
/gsd:done
```

---

## 🧠 MCP Server Usage in Workflow

### Sequential Thinking for Complex Decisions
When stuck on architecture:
```
"Use sequential thinking to design error recovery for failed Solana transactions.
Consider: RPC failures, transaction timeouts, insufficient funds, slippage limits."
```

The AI will break down the problem into steps:
1. Identify failure modes
2. Design retry logic per mode
3. Implement circuit breakers
4. Add monitoring
5. Verify edge cases

### Memory for Persistent Context
At project start:
```
"Remember:
- We use aiogram 3.x for Telegram bots
- Solana RPC via Helius for low latency
- Jupiter V6 for all DEX swaps
- PostgreSQL for trade history
- Redis for caching token metadata"
```

In future sessions:
```
"What telegram library are we using?"
→ "You're using aiogram 3.x"
```

### Context7 for Accurate Documentation
```
"Using Context7, show me how to implement FSM (Finite State Machine) 
in aiogram 3.x for multi-step /swap command"
```

Gets latest docs directly from aiogram, ensuring accuracy.

### GitHub Server for Reference Implementations
```
"Search GitHub for solana-py transaction retry patterns in production trading bots"
```

Finds real-world examples to learn from.

---

## 🎯 Best Practices

### DO ✅

1. **Start with Clear Specs**
   - Use GSD to generate IMPLEMENTATION_PLAN.md
   - Define acceptance criteria upfront
   - Review before execution

2. **Let Ralph Ralph**
   - Allow autonomous execution within specs
   - Trust the verification phase
   - Intervene only when stuck

3. **Use Memory Proactively**
   - Store common addresses/IDs
   - Save proven patterns
   - Remember past mistakes

4. **Leverage Sequential Thinking**
   - Complex architecture decisions
   - Trade-off analysis
   - Risk assessment

5. **Atomic Git Commits**
   - One feature per commit
   - Clear commit messages
   - Easy rollback if needed

### DON'T ❌

1. **Don't Micromanage**
   - Let execution phase complete
   - Don't interrupt mid-task
   - Review after, not during

2. **Don't Skip Planning**
   - IMPLEMENTATION_PLAN.md is critical
   - Prevents thrashing
   - Makes Ralph effective

3. **Don't Ignore Verification**
   - Always run /gsd:verify
   - Check tests
   - Manual QA critical features

4. **Don't Forget Context**
   - Keep PROMPTS file updated
   - Use Memory for key info
   - Maintain specs/ directory

---

## 🔧 Configuration Files

### MCP Configuration
**File**: `C:\Users\lucid\OneDrive\Desktop\Projects\Jarvis\.mcp.json`

Currently configured:
- ✅ Sequential Thinking
- ✅ Memory
- ✅ Filesystem
- ✅ Context7
- ✅ SQLite
- ⚠️ Brave Search (needs key)
- 🔧 GitHub (optional)

### GSD Configuration
**Global**: `~\.claude\` (for Claude Code)  
**Global**: `~\.config\opencode` (for OpenCode)

### Ralph Reference
**Location**: `.ralph-playbook/`

---

## 📖 Additional Resources

### Get Shit Done
- Repository: https://github.com/glittercowboy/get-shit-done
- Discord: https://discord.gg/5JJgD5svVS
- Update: `npx get-shit-done-cc@latest --both --global`

### Ralph Wiggum Technique  
- Original Post: https://ghuntley.com/ralph/
- Playbook: See `.ralph-playbook/README.md`
- Video: https://www.youtube.com/watch?v=O2bBWDoxO4s

### MCP Servers
- Official Docs: https://modelcontextprotocol.io/
- Server List: https://github.com/modelcontextprotocol/servers
- Community: https://github.com/wong2/awesome-mcp-servers

### Solana Development (from your corpus)
- Solana RPC: https://solana.com/docs/rpc
- Jupiter V6: https://hub.jup.ag/docs/apis/swap-api
- aiogram: https://docs.aiogram.dev/
- Telegram Bot API: https://core.telegram.org/bots/api

---

## 🎓 Learning Path

### Week 1: Setup & Basics
- ✅ Install MCP servers (done)
- ✅ Install GSD (done)
- ✅ Clone Ralph playbook (done)
- ⏭️ Restart AI environment
- ⏭️ Verify MCP access
- ⏭️ Run `/gsd:help` in Claude Code

### Week 2: Simple Projects
- Create test project with `/gsd:init`
- Build simple Telegram bot
- Practice Ralph loops
- Use Memory to store learnings

### Week 3: Jarvis Development
- Use GSD for Solana bot planning
- Implement trading logic autonomously
- Leverage Sequential Thinking for complex decisions
- Use Memory for program IDs and patterns

### Week 4: Optimization
- Refine PROMPTS for your style
- Create custom AGENTS.md definitions
- Optimize Ralph loop for your workflow
- Share learnings with Memory

---

## 🚦 Status Check

Run these to verify everything is working:

```bash
# 1. Check MCP servers (in your AI environment)
"List all available MCP servers and their status"

# 2. Check GSD installation
npx get-shit-done-cc --version

# 3. Check Ralph playbook
ls .ralph-playbook/

# 4. Verify git is working (for GSD)
git status

# 5. Test Sequential Thinking
"Use sequential thinking to plan a simple Telegram echo bot"

# 6. Test Memory
"Remember: Test memory is working"
# Later session:
"What did I ask you to remember about memory?"
```

---

## 💡 Pro Tips

### For Solana/Telegram Development

1. **Use Memory as Your Second Brain**
   ```
   Store all program IDs, RPC endpoints, API keys locations
   → Never re-explain your stack
   ```

2. **Let GSD Structure Your Bot**
   ```
   /gsd:init when starting new bot features
   → Clear specs prevent scope creep
   ```

3. **Ralph for Iteration**
   ```
   Define trading strategy in spec
   → Let Ralph implement and test
   → Backpressure via profitability tests
   ```

4. **Sequential Thinking for Architecture**
   ```
   "Design rate limiting for Telegram webhook that handles
   RPC requests, database writes, and Redis caching"
   → Breaks down complex decisions
   ```

5. **Context7 for Library Updates**
   ```
   "What's new in jupiter-swap-api V6?"
   → Always current docs
   ```

---

**Last Updated**: 2026-01-25  
**Version**: 1.0  
**For**: Jarvis Solana Trading Bot Project

---

**Quick Action Items:**
1. ⏭️ Restart your AI coding environment
2. ⏭️ Run `/gsd:help` in Claude Code
3. ⏭️ Ask AI: "Do you have sequential thinking and memory?"
4. ⏭️ Read `.ralph-playbook/README.md`
5. ⏭️ (Optional) Add Brave API key to `.mcp.json`
6. 🚀 Start building!
