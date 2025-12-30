# 🤖 Jarvis - Your Autonomous AI Assistant

<p align="center">
  <b>A self-improving AI that watches, learns, acts, and evolves.</b><br>
  <i>Like having a brilliant friend who never sleeps and controls your Mac.</i>
</p>

---

**Jarvis** is an autonomous AI assistant that runs 24/7 on your Mac. It observes what you're doing, offers proactive suggestions every 15 minutes, controls your computer via voice or text, conducts research, creates documents, and continuously improves itself.

## ✨ What Makes Jarvis Different

| Feature | Jarvis | ChatGPT/Claude |
|---------|--------|----------------|
| Runs locally 24/7 | ✅ | ❌ |
| Watches your screen | ✅ | ❌ |
| Controls your Mac | ✅ | ❌ |
| Proactive suggestions | ✅ | ❌ |
| Self-improving | ✅ | ❌ |
| Voice activated | ✅ | Limited |
| Free to run | ✅ (with Ollama/Groq) | ❌ |

## 🚀 Key Features

### 🧠 Autonomous AI
- **Conversational** — Talks like a friend, not a robot
- **Proactive** — Offers solutions every 15 minutes based on what you're doing
- **Self-improving** — Learns from interactions and upgrades itself
- **Context-aware** — Remembers your goals, projects, and preferences

### 🎤 Voice Control
- **Wake word** — "Hey Jarvis" activates listening
- **Natural conversation** — Chat like you would with a person
- **Hotkey** — Ctrl+Shift+Up for instant access
- **60-second patience** — Won't cut you off mid-thought

### 🖥️ Computer Control
- **Open apps & windows** — "Open Safari", "Switch to VS Code"
- **Compose emails** — "Send an email to John about the meeting"
- **Google searches** — "Search for crypto trading strategies"
- **Create notes & reminders** — "Remind me to call mom at 5pm"
- **Keyboard shortcuts** — Copy, paste, save, undo, and more

### 📊 Research & Documents
- **Automated research** — "Research the best AI stocks for 2025"
- **Document creation** — "Create a business plan for my startup"
- **Free software discovery** — "Find open source alternatives to Photoshop"

### 📈 Trading + Market Research
- **DEX-first focus** — Low-fee chains (Solana/Base/BNB/Monad/Abstract)
- **Hyperliquid data** — 30-day snapshots with lightweight backtests
- **Strategy backlog** — Keeps experiments moving while you’re idle

### 📓 Local Knowledge Engine
- **Distilled note archive** — All notes/research saved as `.md/.txt/.py` in `data/notes/`
- **Auto-summary + prompts** — Every capture creates a concise summary + reusable prompt snippet
- **Command-line + voice parity** — `lifeos capture`, voice `log`, and missions share the same pipeline
- **Raw artifact storage** — curl outputs, transcripts, and CLI logs saved for full traceability

### 👁️ Activity Monitoring
- **App usage tracking** — Know where your time goes
- **Productivity insights** — Identify patterns and distractions
- **Screen context** — Jarvis sees what you see
- **Configurable depth** — Lite or deep logging, all stored locally

### 🛡️ Security + Resource Guard
- **Resource alerts** — CPU/RAM/Disk warnings with OS notifications
- **Network monitoring** — Throughput + packet rate logging
- **Process guard** — Flags heavy/abusive processes and can auto-terminate (opt-in)

### 🔄 Self-Evolution
- **Auto-upgrades on boot** — Applies pending improvements automatically
- **Skill learning** — Add new capabilities via simple Python modules
- **Error analysis** — Learns from failures and fixes itself
- **Continuous iteration** — Gets smarter every day

### 🧩 MCP Autonomy Stack
- **Filesystem + Git MCP** — Safe read/write access to `LifeOS` and Jarvis context with enforced branch discipline.
- **Dual Memory Layer** — JSONL knowledge graph (`server-memory`) plus Obsidian-native graph (`obsidian-memory`) stored in `$HOME/Documents/Obsidian/LifeOSVault`.
- **Knowledge Connectors** — Obsidian REST MCP enables Jarvis to search, edit, and append to vault notes with API-key protection.
- **Systems Insight** — `mcp-monitor` streams CPU/GPU/RAM/network metrics for optimization cycles.
- **Persistent Reasoning** — SQLite MCP hosts long-term structured data and queryable memories.
- **Action Surface** — Shell MCP (sandboxed to LifeOS) and Puppeteer MCP (browser automation) give Jarvis “hands” for executing plans.
- **Sequential Thinking MCP** — Provides scratchpad-style reasoning traces to enforce decomposition before acting.
- **YouTube Transcript MCP** — Fast transcript access for research and MoonDev ingestion.

> The entire MCP stack is declared in `lifeos/config/mcp.config.json`, autostarted by `core/mcp_loader.py`, and mirrored in Windsurf’s `~/.codeium/windsurf/mcp_config.json` for editor parity.

### 🌙 Idle Missions (Auto-Research)
- **MoonDev Watcher** — Tracks official MoonDevOnYT X feed for new HFT drops
- **AlgoTradeCamp Digest** — Snapshots algotradecamp.com for lessons and tactics
- **MoonDev YouTube Harvester** — Pulls transcripts via yt-dlp and summarizes key experiments
- **Hyperliquid Snapshot + Backtest** — 30-day data pulls with lightweight MA backtests
- **DEX API Scout** — Finds free/low-cost DEX endpoints for low-fee chains
- **Prompt Pack Builder** — Generates prompt packs for agency + website workflows
- **AI/Security News Scan** — Tracks new tools/releases to upgrade Jarvis
- **Business Suggestions Digest** — Summarizes opportunities tied to your work
- **Directive Digest** — Keeps operating directives tight and actionable
- **Self-Improvement Pulse** — Reviews provider errors + memory to prioritize upgrades

### 🔊 Offline Voice
- **Piper TTS** — Bundled model auto-downloads to `data/voices/`, works with no internet
- **Voice fallback** — Seamlessly drops to macOS `say` only if local synthesis fails
- **Configurable** — Customize `voice.tts_engine`, `piper_model`, and `speech_voice` in config
- **Jarvis voice live** — macOS `say` is enabled by default for natural speech

## 📦 Quick Start

```bash
# Clone the repo
git clone https://github.com/Matt-Aurora-Ventures/Jarvis.git
cd Jarvis

# Set up environment
python3 -m venv venv
source venv/bin/activate
python -m pip install -r requirements.txt

# If you hit the macOS llvmlite/LLVM error, use the lite set:
python -m pip install -r requirements-mac-lite.txt

# Add your API key (stored locally; never commit or share)
cat > secrets/keys.json <<'JSON'
{"google_api_key": "YOUR_KEY", "groq_api_key": "YOUR_GROQ_KEY", "brave_api_key": "OPTIONAL_BRAVE_KEY"}
JSON

# Start Jarvis
./bin/lifeos on --apply

# Talk to Jarvis
./bin/lifeos chat
```

## 🎯 Commands

| Command | What it does |
|---------|--------------|
| `lifeos on --apply` | Start Jarvis daemon |
| `lifeos off --apply` | Stop Jarvis |
| `lifeos status` | Check if Jarvis is running |
| `lifeos chat` | Voice conversation mode |
| `lifeos talk` | Single voice command |
| `lifeos log "note"` | Quick note to memory |
| `lifeos activity` | View productivity stats |
| `lifeos jarvis research "topic"` | Run research project |
| `lifeos jarvis discover` | System discovery |

## 🖥️ Web Control Deck

Run the local Flask dashboard for status, resources, missions, and research:

```bash
python3 web/task_web.py
```

Open `http://127.0.0.1:5000` in your browser.

## ⚙️ Configuration

Edit `lifeos/config/lifeos.config.json`:

```json
{
  "voice": {
    "wake_word": "jarvis",
    "chat_silence_limit": 60,
    "speak_responses": true,
    "tts_engine": "say",
    "speech_voice": "Samantha"
  },
  "observer": {
    "mode": "lite",
    "flush_interval": 45
  },
  "actions": {
    "allow_ui": false,
    "require_confirm": true
  },
  "resource_monitor": {
    "enabled": true,
    "ram_free_gb_warn": 2.0,
    "cpu_load_warn": 4.0
  },
  "network_monitor": {
    "enabled": true
  },
  "process_guard": {
    "enabled": true,
    "auto_kill": false
  },
  "providers": {
    "gemini": { "enabled": true, "model": "gemini-2.5-pro" },
    "groq": { "enabled": true },
    "ollama": { "enabled": true, "model": "llama3.2:3b" }
  }
}
```

### 🧠 System Instructions

Jarvis follows the memory-first/decomposition/git-safety workflow defined in [`lifeos/config/system_instructions.md`](lifeos/config/system_instructions.md):

1. Query memory MCP servers before asking the user.
2. Break work into steps, logging reasoning and verification.
3. Create/switch feature branches before editing tracked files.
4. Limit filesystem actions to approved LifeOS/Jarvis-context paths and prefer MCP tooling.
5. Record discoveries, blockers, and fixes back into memory for future runs.

## 💰 Cost

| Provider | Cost | Speed | Quality |
|----------|------|-------|---------|
| **Groq** | FREE | ⚡ Ultra-fast | Great |
| **Ollama** | FREE | Medium | Good |
| **Gemini** | ~$5-20/mo | Fast | Excellent |
| **OpenAI** | ~$10-30/mo | Fast | Excellent |

## 🛡️ Safety

Jarvis has built-in safety constraints:
- **Cannot delete itself** or critical system files
- **Guardian module** validates all generated code
- **Protected paths** prevent dangerous operations
- **All data local** — nothing sent to external servers (except AI APIs)

## 🔐 Secrets Hygiene

- Keep API keys in `secrets/keys.json` or environment variables; `secrets/` is gitignored.
- Never paste keys into issues, logs, screenshots, or shared docs.
- Rotate keys immediately if they leak or are accidentally shared.

## 🗺️ Roadmap

- [x] Voice control & wake word
- [x] Computer control (apps, email, search)
- [x] Proactive 15-min suggestions
- [x] Self-evolution system
- [x] Research & document creation
- [ ] Real-time web search
- [ ] Trading automation
- [ ] iOS companion app
- [ ] Multi-device sync

## 📝 Changelog

See [CHANGELOG.md](CHANGELOG.md) for full version history.

## 🤝 Contributing

PRs welcome! Check `core/guardian.py` for safety guidelines before modifying system behavior.

## 📄 License

MIT License - Use freely, modify freely, just don't blame us if Jarvis becomes too helpful.

---

<p align="center">
  <b>Built by <a href="https://github.com/Matt-Aurora-Ventures">Matt Aurora Ventures</a></b><br>
  <i>"The best AI is the one that makes you better."</i>
</p>
