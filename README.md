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

### 👁️ Activity Monitoring
- **App usage tracking** — Know where your time goes
- **Productivity insights** — Identify patterns and distractions
- **Screen context** — Jarvis sees what you see
- **Privacy-first** — All data stays local

### 🔄 Self-Evolution
- **Auto-upgrades on boot** — Applies pending improvements automatically
- **Skill learning** — Add new capabilities via simple Python modules
- **Error analysis** — Learns from failures and fixes itself
- **Continuous iteration** — Gets smarter every day

## 📦 Quick Start

```bash
# Clone the repo
git clone https://github.com/Matt-Aurora-Ventures/Jarvis.git
cd Jarvis

# Set up environment
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Add your API key (Gemini, Groq, or OpenAI)
echo '{"google_api_key": "YOUR_KEY", "groq_api_key": "YOUR_GROQ_KEY"}' > secrets/keys.json

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

## ⚙️ Configuration

Edit `lifeos/config/lifeos.config.json`:

```json
{
  "voice": {
    "wake_word": "jarvis",
    "chat_silence_limit": 60,
    "speak_responses": true
  },
  "providers": {
    "gemini": { "enabled": true, "model": "gemini-2.5-pro" },
    "groq": { "enabled": true },
    "ollama": { "enabled": true, "model": "llama3.2:3b" }
  }
}
```

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
