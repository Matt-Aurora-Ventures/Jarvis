# Jarvis - Autonomous AI Assistant

<p align="center">
  <b>A self-improving AI that watches, learns, acts, and evolves.</b><br>
  <i>Like having a brilliant friend who never sleeps and controls your Mac.</i>
</p>

---

**Jarvis** is an autonomous AI assistant that runs 24/7 on your Mac. It observes what you're doing, offers proactive suggestions, controls your computer via voice or text, conducts research, creates documents, trades crypto, and continuously improves itself.

**v0.9.0** introduces **Claude + GPT hybrid collaboration**, a comprehensive **trading research pipeline**, and **81 extracted trading strategies** ready for backtesting.

---

## Table of Contents

- [What Makes Jarvis Different](#-what-makes-jarvis-different)
- [Key Features](#-key-features)
- [Architecture Overview](#-architecture-overview)
- [Quick Start](#-quick-start)
- [Configuration](#-configuration)
- [Commands Reference](#-commands-reference)
- [Trading & Research](#-trading--research)
- [MCP Autonomy Stack](#-mcp-autonomy-stack)
- [Security & OPSEC](#-security--opsec)
- [Development](#-development)
- [Roadmap](#-roadmap)
- [Contributing](#-contributing)
- [License](#-license)

---

## What Makes Jarvis Different

| Feature | Jarvis | ChatGPT/Claude |
|---------|--------|----------------|
| Runs locally 24/7 | Yes | No |
| Watches your screen | Yes | No |
| Controls your Mac | Yes | No |
| Proactive suggestions | Yes | No |
| Self-improving | Yes | No |
| Voice activated | Yes | Limited |
| Trading research | Yes | No |
| Multi-provider fallback | Yes | Single |
| Free to run | Yes (Ollama/Groq) | Paid |

---

## Key Features

### Autonomous AI Core

- **Conversational** - Talks like a friend, not a robot
- **Proactive** - Offers solutions every 15 minutes based on what you're doing
- **Self-improving** - Learns from interactions and upgrades itself
- **Context-aware** - Remembers your goals, projects, and preferences
- **Multi-provider** - Groq, Gemini, OpenAI, Ollama with automatic fallback

### Voice Control

- **Wake word** - "Hey Jarvis" activates listening
- **Natural conversation** - Chat like you would with a person
- **Hotkey** - `Ctrl+Shift+Up` for instant access
- **60-second patience** - Won't cut you off mid-thought
- **Offline TTS** - Piper engine works without internet

### Computer Control

| Action | Example Command |
|--------|-----------------|
| Open apps | "Open Safari", "Switch to VS Code" |
| Compose emails | "Send an email to John about the meeting" |
| Google searches | "Search for crypto trading strategies" |
| Notes & reminders | "Remind me to call mom at 5pm" |
| Keyboard shortcuts | Copy, paste, save, undo, and more |
| Calendar | "Create a meeting for tomorrow at 2pm" |
| iMessage | "Send a message to Sarah" |

### Research & Documents

- **Automated research** - "Research the best AI stocks for 2025"
- **Document creation** - "Create a business plan for my startup"
- **Free software discovery** - "Find open source alternatives to Photoshop"
- **Multi-source aggregation** - DuckDuckGo, Brave, direct web scraping

### Trading & Market Research

- **81 extracted strategies** - From Moon Dev's Algo Trading Roadmap
- **Strategy categories:**
  - Trend Following (slow/fast, MA crossovers)
  - Carry Trades (funding rate arbitrage)
  - Mean Reversion (RSI, Bollinger, Z-score)
  - Cross-Sectional Momentum
  - Breakout Trading
  - Calendar Spreads
  - Hidden Markov Models (regime detection)
- **DEX-first focus** - Solana, Base, BNB Chain, Monad, Abstract
- **Hyperliquid integration** - 30-day snapshots with backtests
- **Liquidation signals** - Moon Dev API integration
- **Solana scanner** - Birdeye API for token discovery

### Local Knowledge Engine

- **Distilled note archive** - All notes saved as `.md/.txt/.py` in `data/notes/`
- **Auto-summary** - Every capture creates a concise summary
- **Prompt library** - Reusable prompt snippets
- **Full traceability** - Raw artifacts stored for reference

### Activity Monitoring

- **App usage tracking** - Know where your time goes
- **Productivity insights** - Identify patterns
- **Screen context** - Jarvis sees what you see
- **Configurable depth** - Lite or deep logging

### Resource & Security

- **Resource alerts** - CPU/RAM/Disk warnings
- **Network monitoring** - Throughput + packet rate
- **Process guard** - Flags heavy processes (optional auto-terminate)
- **Security scans** - Periodic vulnerability checks

### Self-Evolution

- **Auto-upgrades on boot** - Applies pending improvements
- **Skill learning** - Add capabilities via Python modules
- **Error analysis** - Learns from failures
- **Continuous iteration** - Gets smarter every day

---

## Architecture Overview

```
jarvis/
├── bin/                    # CLI entry points
│   └── lifeos              # Main executable
├── core/                   # Core modules
│   ├── actions.py          # Computer control actions
│   ├── agent_graph.py      # Multi-agent orchestration
│   ├── agent_router.py     # Intelligent agent routing
│   ├── cli.py              # Command-line interface
│   ├── conversation.py     # Conversation management
│   ├── daemon.py           # Background daemon
│   ├── guardian.py         # Safety constraints
│   ├── hyperliquid.py      # Hyperliquid data fetcher
│   ├── liquidation_bot.py  # Liquidation trading signals
│   ├── mcp_doctor.py       # MCP health diagnostics
│   ├── mcp_loader.py       # MCP process supervisor
│   ├── memory.py           # Memory management
│   ├── missions.py         # Idle mission scheduler
│   ├── notion_*.py         # Notion extraction modules
│   ├── orchestrator.py     # Task orchestration
│   ├── proactive.py        # 15-min suggestion system
│   ├── providers.py        # AI provider management
│   ├── research.py         # Research automation
│   ├── self_improvement_engine.py  # Auto-evolution
│   ├── semantic_memory.py  # Semantic search
│   ├── solana_scanner.py   # Solana token scanner
│   ├── trading_*.py        # Trading pipeline modules
│   ├── voice.py            # Voice control
│   └── youtube_ingest.py   # YouTube transcript extraction
├── lifeos/
│   └── config/
│       ├── lifeos.config.json   # Main configuration
│       ├── mcp.config.json      # MCP server config
│       └── system_instructions.md  # AI behavior rules
├── web/
│   └── task_web.py         # Flask control deck
├── data/                   # Runtime data (gitignored)
├── secrets/                # API keys (gitignored)
└── tests/                  # Test suite
```

### Provider Chain

```
Request → Groq (fast, free) → Gemini → OpenAI → Ollama (local)
              ↓                  ↓         ↓          ↓
          Primary           Fallback   Fallback   Offline
```

### MCP Server Stack

```
┌─────────────────────────────────────────────────────────────┐
│                     MCP Autonomy Stack                      │
├─────────────────────────────────────────────────────────────┤
│ filesystem      │ Safe read/write to LifeOS + Jarvis context│
│ memory          │ JSONL knowledge graph                     │
│ obsidian-memory │ Obsidian vault integration                │
│ sqlite          │ Structured data persistence               │
│ system-monitor  │ CPU/GPU/RAM/network metrics               │
│ shell           │ Sandboxed command execution               │
│ puppeteer       │ Browser automation                        │
│ youtube-transcript │ Fast transcript access                 │
│ sequential-thinking │ Scratchpad reasoning                  │
│ git             │ Version control operations                │
│ notebooklm      │ NotebookLM integration                    │
└─────────────────────────────────────────────────────────────┘
```

---

## Quick Start

```bash
# Clone the repo
git clone https://github.com/Matt-Aurora-Ventures/Jarvis.git
cd Jarvis

# Set up environment
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# If you hit the macOS llvmlite/LLVM error:
pip install -r requirements-mac-lite.txt

# Configure API keys (stored locally, never committed)
mkdir -p secrets
cat > secrets/keys.json << 'EOF'
{
  "groq_api_key": "YOUR_GROQ_KEY",
  "google_api_key": "YOUR_GEMINI_KEY",
  "openai_api_key": "YOUR_OPENAI_KEY",
  "brave_api_key": "OPTIONAL_BRAVE_KEY"
}
EOF

# Start Jarvis
./bin/lifeos on --apply

# Talk to Jarvis
./bin/lifeos chat

# Check system health
./bin/lifeos doctor
```

---

## Configuration

### Main Config: `lifeos/config/lifeos.config.json`

```json
{
  "voice": {
    "wake_word": "jarvis",
    "chat_silence_limit": 60,
    "speak_responses": true,
    "tts_engine": "say",
    "speech_voice": "Samantha"
  },
  "providers": {
    "groq": { "enabled": true, "priority": 1 },
    "gemini": { "enabled": false, "priority": 2 },
    "openai": { "enabled": "auto", "priority": 3 },
    "ollama": { "enabled": true, "model": "qwen2.5:1.5b", "priority": 4 }
  },
  "missions": {
    "enabled": true,
    "poll_seconds": 120,
    "idle_grace_seconds": 120
  },
  "trading": {
    "dex_only": true,
    "preferred_chains": ["Solana", "Base", "BNB Chain", "Monad", "Abstract"],
    "strategy": "sma_cross",
    "risk_per_trade": 0.02,
    "stop_loss_pct": 0.03
  }
}
```

### System Instructions

Jarvis follows the memory-first workflow defined in `lifeos/config/system_instructions.md`:

1. Query memory MCP servers before asking the user
2. Break work into steps with reasoning and verification
3. Create feature branches before editing tracked files
4. Limit filesystem actions to approved paths
5. Record discoveries back into memory

---

## Commands Reference

### Core Commands

| Command | Description |
|---------|-------------|
| `lifeos on --apply` | Start Jarvis daemon |
| `lifeos off --apply` | Stop Jarvis |
| `lifeos status` | Check daemon status |
| `lifeos chat` | Voice conversation mode |
| `lifeos talk` | Single voice command |
| `lifeos doctor` | System health check |
| `lifeos doctor --test` | Quick provider test |

### Memory & Notes

| Command | Description |
|---------|-------------|
| `lifeos log "note"` | Quick note to memory |
| `lifeos capture "content"` | Capture to notes archive |
| `lifeos activity` | View productivity stats |

### Research & Actions

| Command | Description |
|---------|-------------|
| `lifeos jarvis research "topic"` | Run research project |
| `lifeos jarvis discover` | System discovery |
| `lifeos providers check` | Check AI provider status |

### Web Control Deck

```bash
python3 web/task_web.py
# Open http://127.0.0.1:5000
```

---

## Trading & Research

### Extracted Strategies (81 total)

Jarvis has extracted and parsed 81 trading strategies from Moon Dev's Algo Trading Roadmap:

| Category | Count | Examples |
|----------|-------|----------|
| Slow Trend Following | 9 | 200-Day MA, Dual MA Crossover |
| Fast Trend Following | 6 | 10/30 MA with ADX |
| Carry Trades | 9 | Funding Rate Arbitrage, Basis Trading |
| Mean Reversion | 6 | RSI Bounce, Bollinger Mean Reversion |
| Cross-Sectional | 6 | Relative Strength, Momentum Rankings |
| Breakout | 6 | Range Breakout, Volume Confirmation |
| Calendar Spreads | 6 | Rollover Strategies |
| Advanced | 33 | HMM Regime, Dynamic Optimization |

### Strategy Catalog

Strategies are stored in `data/notion_deep/strategy_catalog.json`:

```json
{
  "strategy_id": "STRAT-001",
  "name": "200-Day MA Long",
  "category": "Slow Trend Following",
  "indicators": ["moving average"],
  "entry_conditions": ["Price closes above 200-day MA"],
  "exit_conditions": ["Price closes below 200-day MA or trailing stop"],
  "implementation_status": "pending"
}
```

### Implementation Priority

1. **P0 - Quick Wins:** 200-Day MA, Dual MA Crossover, ADX Enhanced
2. **P1 - Core:** Funding Rate Arbitrage, RSI Mean Reversion, Momentum
3. **P2 - Advanced:** HMM Regime, Dynamic Optimization, Triplets

### Data Sources

- **Hyperliquid** - Perp market data, funding rates
- **Moon Dev API** - Liquidation signals
- **Birdeye** - Solana token data
- **YouTube** - Trading content transcripts
- **Notion** - Strategy documentation

---

## MCP Autonomy Stack

The MCP (Model Context Protocol) stack gives Jarvis "hands" to interact with the system:

### Server Configuration

Located in `lifeos/config/mcp.config.json`:

```json
{
  "servers": [
    { "name": "filesystem", "enabled": true },
    { "name": "memory", "enabled": true },
    { "name": "obsidian-memory", "enabled": true },
    { "name": "sqlite", "enabled": true },
    { "name": "system-monitor", "enabled": true },
    { "name": "shell", "enabled": true },
    { "name": "puppeteer", "enabled": true },
    { "name": "youtube-transcript", "enabled": true },
    { "name": "sequential-thinking", "enabled": true },
    { "name": "git", "enabled": true },
    { "name": "notebooklm", "enabled": true }
  ]
}
```

### Health Check

```bash
lifeos doctor
```

Outputs provider health, MCP server status, and actionable fixes.

---

## Security & OPSEC

### Secrets Management

- **Location:** `secrets/keys.json` (gitignored)
- **Never commit:** API keys, tokens, credentials
- **Environment variables:** Preferred for CI/CD
- **Rotation:** Rotate immediately if exposed

### What's Protected

```
secrets/           # API keys and tokens
*.secret           # Any secret files
*.pem, *.key       # Certificates and keys
.env, .env.*       # Environment files
*.db, *.sqlite     # Databases
browser-data/      # Browser sessions
transcripts/       # Voice recordings
data/              # Runtime data
lifeos/logs/       # Log files
```

### Safety Constraints

Jarvis has built-in safety via `core/guardian.py`:

- **Cannot delete itself** or critical system files
- **Code validation** - All generated code checked
- **Protected paths** - Core files locked from modification
- **Sandboxed shell** - MCP shell restricted to LifeOS directory

### Audit Commands

```bash
# Scan for potential secrets in code
grep -r "sk-\|api_key\s*=" --include="*.py" core/

# Check gitignore coverage
git status --ignored

# Run secrets hygiene check
python3 -c "from core.secret_hygiene import scan_for_secrets; scan_for_secrets()"
```

---

## Development

### Project Structure

```
core/           # Core modules (Python)
tests/          # Test suite
docs/           # Documentation
web/            # Flask control deck
lifeos/config/  # Configuration files
skills/         # Skill modules (Python)
```

### Running Tests

```bash
# All tests
pytest tests/

# Specific module
pytest tests/test_trading_pipeline.py -v

# With coverage
pytest --cov=core tests/
```

### Adding a New Skill

1. Create `skills/my_skill.py`:

```python
def my_skill(param1: str) -> str:
    """Skill description."""
    return f"Result: {param1}"
```

2. Jarvis will auto-discover and load it.

### Contributing a Provider

1. Add to `core/providers.py`
2. Implement `call()` method with fallback support
3. Add to provider chain in config

---

## Roadmap

### Completed

- [x] Voice control & wake word
- [x] Computer control (apps, email, search)
- [x] Proactive 15-min suggestions
- [x] Self-evolution system
- [x] Research & document creation
- [x] Trading strategy extraction (81 strategies)
- [x] MCP autonomy stack
- [x] Claude + GPT hybrid collaboration

### In Progress

- [ ] Strategy backtesting engine
- [ ] Live paper trading
- [ ] Web search integration

### Planned

- [ ] Trading automation (live)
- [ ] iOS companion app
- [ ] Multi-device sync
- [ ] Plugin marketplace

---

## Cost

| Provider | Cost | Speed | Quality |
|----------|------|-------|---------|
| **Groq** | FREE | Ultra-fast | Great |
| **Ollama** | FREE | Medium | Good |
| **Gemini** | ~$5-20/mo | Fast | Excellent |
| **OpenAI** | ~$10-30/mo | Fast | Excellent |

---

## Contributing

PRs welcome! Please:

1. Read safety guidelines in `core/guardian.py`
2. Run tests before submitting
3. Never commit secrets or personal data
4. Follow existing code style

---

## Changelog

See [CHANGELOG.md](CHANGELOG.md) for full version history.

**Latest: v0.9.0** - Claude + GPT hybrid collaboration, 81 trading strategies, Notion deep extraction.

---

## License

MIT License - Use freely, modify freely, just don't blame us if Jarvis becomes too helpful.

---

<p align="center">
  <b>Built by <a href="https://github.com/Matt-Aurora-Ventures">Matt Aurora Ventures</a></b><br>
  <i>"The best AI is the one that makes you better."</i>
</p>
