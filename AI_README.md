# Jarvis - AI Agent Entry Document

> This document is designed for AI agents, IDE assistants, and automated tools to quickly understand the Jarvis system architecture, capabilities, and constraints.

**Version**: 3.3.0
**Last Updated**: 2026-01-08
**Primary Language**: Python 3.11+
**Platforms**: macOS, Windows, Linux

---

## System Identity

Jarvis is an autonomous, self-improving AI assistant that:
- Runs continuously (daemon mode)
- Observes user activity and system state
- Controls the computer via voice, text, or hotkeys
- Executes Solana trading strategies with human approval gates
- Improves itself nightly through the Mirror Test self-correction cycle

**Philosophy**: "An edge for the little guy"—democratizing institutional-grade AI and trading tools at minimal cost.

---

## Capabilities Matrix

| Capability | Status | Module | Notes |
|------------|--------|--------|-------|
| Voice control | DONE | `core/voice.py` | Wake word "Hey Jarvis" |
| Computer control | DONE | `core/computer.py`, `core/platform/` | Cross-platform |
| LLM reasoning | DONE | `core/providers.py` | Minimax 2.1 + Groq + Ollama |
| Solana trading | DONE | `core/trading/` | Jupiter, Raydium, Orca |
| MEV protection | DONE | `core/jito_executor.py` | Jito Block Engine |
| Self-improvement | DONE | `core/evolution/` | Nightly Mirror Test |
| Activity monitoring | DONE | `core/observer.py` | Privacy-first (local only) |
| Frontend dashboard | PARTIAL | `frontend/` | Known 404 issues on wallet APIs |
| Ethereum MEV | PLANNED | - | Flashbots integration |
| iOS companion | PLANNED | - | Not started |

---

## Constraints (Non-Negotiable)

1. **Solana-only** for financial infrastructure (no ETH/other chains in trading)
2. **Local data only** - no cloud logging of user activity
3. **Cost-efficient** - default free/near-free operation (Groq, Ollama, Piper)
4. **Human approval required** for live trades (via `core/approval_gate.py`)
5. **Safety rules** enforced by `core/guardian.py` - cannot delete itself or critical files

---

## Architecture Map

```
Entry Points
├── bin/lifeos              → CLI entry (routes to core/cli.py)
├── api/server.py           → Flask API (port 8765)
└── scripts/                → Automation scripts

Core Modules (190 files)
├── core/daemon.py          → Subsystem orchestration
├── core/voice.py           → Voice control (STT/TTS)
├── core/conversation.py    → Response generation
├── core/providers.py       → LLM provider routing
├── core/guardian.py        → Safety rules (PROTECTED)
├── core/approval_gate.py   → Trade approval (PROTECTED)
├── core/trading/           → Trading subpackage (25+ modules)
├── core/voice/             → Voice subpackage (4 modules)
├── core/platform/          → Cross-platform adapters (3 adapters)
└── core/evolution/         → Self-improvement (Mirror Test)

Data Storage
├── lifeos/config/          → Configuration files (JSON)
├── lifeos/memory/          → Conversation history (JSONL)
├── lifeos/context/         → Goals, principles, projects (Markdown)
├── lifeos/logs/            → Runtime logs
├── data/trader/            → Trading data, backtests (SQLite, JSON)
├── data/notes/             → User notes archive (Markdown)
└── secrets/keys.json       → API keys (gitignored)

Frontend
├── frontend/src/           → React 18 + Vite + TailwindCSS
└── frontend/src/pages/     → Dashboard, Trading, Chat, Voice, etc.
```

---

## Strategy Catalog

**Location**: `data/notion_deep/strategy_catalog.json`
**Count**: 81 strategies extracted from Moon Dev's Algo Trading Roadmap

| Category | Count | Implementation Status |
|----------|-------|----------------------|
| Slow Trend Following | 9 | DONE |
| Fast Trend Following | 6 | DONE |
| Carry Trades | 9 | DONE |
| Mean Reversion | 6 | DONE |
| Cross-Sectional | 6 | PARTIAL |
| Breakout | 6 | DONE |
| Calendar Spreads | 6 | PARTIAL |
| Advanced (HMM, etc.) | 33 | PARTIAL |

---

## Provider Stack

| Provider | Role | Cost | Priority |
|----------|------|------|----------|
| Minimax 2.1 | Primary reasoning | $0.30/1M tokens | 1 |
| Groq | Fast tool execution | FREE | 2 |
| Ollama | Offline fallback | FREE | 3 |
| Gemini | Backup reasoning | $5-20/mo | 4 |
| OpenAI | Emergency fallback | $15/1M tokens | 5 |

---

## How to Run

```bash
# Start daemon
./bin/lifeos on --apply

# Voice conversation
./bin/lifeos chat

# Single voice command
./bin/lifeos talk "open Safari"

# Health check
./bin/lifeos doctor

# Trading coliseum
./bin/lifeos trading coliseum start

# Mirror Test report
./bin/lifeos mirror report
```

---

## Testing

```bash
# All tests
pytest tests/ -v

# With coverage
pytest --cov=core --cov-report=html tests/

# Specific module
pytest tests/test_guardian.py -v

# Pattern matching
pytest -k "test_protected" -v
```

**Current Coverage**: ~25%
**Target Coverage**: 60%+
**Test Files**: 18
**Tests Passing**: 180+

---

## Critical Paths (DO NOT MODIFY WITHOUT TESTS)

These files enforce safety and correctness. Any modification requires:
1. Existing test suite passes
2. New test added for the change
3. Human review of diff

| File | Purpose | Risk Level |
|------|---------|------------|
| `core/guardian.py` | Safety rules, protected paths | CRITICAL |
| `core/approval_gate.py` | Trade approval, kill switch | CRITICAL |
| `core/daemon.py` | Subsystem orchestration | HIGH |
| `core/providers.py` | LLM routing, fallbacks | HIGH |
| `core/solana_execution.py` | Transaction execution | HIGH |
| `core/jito_executor.py` | MEV bundle submission | HIGH |

---

## Known Issues (TODO Items)

| Location | Issue | Priority |
|----------|-------|----------|
| `core/execution_fallback.py:397` | Raydium/Orca direct execution not implemented | P1 |
| `core/lut_daemon.py:142` | xAI sentiment integration pending | P1 |
| `core/lut_micro_alpha.py:330` | xAI sentiment integration pending | P1 |
| `core/trading_daemon.py:258` | xAI sentiment integration pending | P1 |
| `core/micro_cap_sniper.py:534` | Sophisticated entry signals needed | P2 |
| `core/browser_automation.py:607` | OCR element location needed | P2 |

---

## Self-Improvement Cycle

**Schedule**: Daily at 3am (configurable in `lifeos/config/minimax.config.json`)

```
[1] Log Ingestion     → Parse last 24h from lifeos/logs/
[2] Minimax Replay    → Re-evaluate decisions with current model
[3] Performance Score → Grade latency, accuracy, satisfaction
[4] Refactor Proposal → AI-generated code improvements
[5] Dry-Run Testing   → Validate against 100 historical scenarios
[6] Auto-Apply        → If confidence > 0.85, merge and commit
```

**Snapshot Location**: `core/evolution/snapshots/`
**Diff Location**: `core/evolution/diffs/`
**Retention**: 60 days

---

## Cost Profile

| Usage Level | Monthly Cost | Configuration |
|-------------|--------------|---------------|
| Free | $0 | Groq + Ollama + Piper + public RPC |
| Light | ~$50 | Minimax 2.1 + free data sources |
| Heavy | ~$150 | Minimax + Helius RPC + BirdEye Pro |

---

## Contact Points

- **Issue Tracker**: https://github.com/Matt-Aurora-Ventures/Jarvis/issues
- **Changelog**: `/CHANGELOG.md`
- **Full README**: `/README.md`
- **Architecture Docs**: `/docs/ARCHITECTURE.md`

---

*This document is auto-generated and should be updated when significant changes occur.*
