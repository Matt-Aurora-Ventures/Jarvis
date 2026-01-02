# Jarvis - Autonomous LifeOS System
<p align="center">
  <b>The central command center for your digital life.</b><br>
  <i>Deep visibility, autonomous security, and algorithmic trading.</i>
</p>

![Status](https://img.shields.io/badge/Status-ONLINE-success)
![Dashboard](https://img.shields.io/badge/Dashboard-v2.0-blue)
![Security](https://img.shields.io/badge/Security-IDS_ACTIVE-red)

---

**Jarvis v2.0** brings complete observability to autonomous operations. It doesn't just run scripts; it visualizes its entire cognition process, monitors system security in real-time, and executes high-frequency trading strategies with full transparency.

## 🖥️ The Ecosystem Dashboard

At `http://localhost:5001`, Jarvis provides a SOC-style command center:

- **🛡️ Security Intelligence (IDS)**
  - Real-time Process Spawn Detection
  - Network Traffic Analysis (TX/RX Flow)
  - Suspicious Port Flagging & Connection Tracking
  - [Read Security Manual](SECURITY_MANUAL.md)

- **📈 Trading Pipeline**
  - Live Backtesting Progress (50 Tokens × 50 Strategies)
  - Solana Token Scanning (BirdEye Integration)
  - Strategy Performance Tracking

- **💬 Communication Link**
  - Chat Console with `/exec`, `/log`, `/scan` commands
  - System Log Streaming
  - Direct Instruction Interface

---

## 🧠 Core Capabilities

### 1. Autonomous Research (NotebookLM)
- **Deep Research**: Creates research notebooks automatically.
- **Source Truth**: Filters information via trusted sources.
- **Study Guides**: Generates summaries from complex topics.
- *Powered by `core/notebooklm_mcp.py`*

### 2. Algorithmic Trading
- **Scanner**: Monitors top 50 high-volume Solana tokens.
- **Backtester**: Validates 50 strategies against 3-month data.
- **Executor**: Paper-trading simulation environment.
- *Powered by `scripts/run_trading_pipeline.py`*

### 3. Voice Control
- **Interactive**: Barge-in capable voice interface.
- **Cost-Optimized**: Smart routing between Minimax and Whisper.
- **Frontend**: Dedicated Voice Dashboard at `/voice`.

---

## 🚀 Quick Start

### 1. Launch the Ecosystem Dashboard
```bash
# Monitor everything in one place
python3 scripts/progress_dashboard.py
# Open http://localhost:5001
```

### 2. Start Sub-Systems
```bash
# Terminal 2: Run Trading Pipeline
python3 scripts/run_trading_pipeline.py

# Terminal 3: Start Voice/Frontend API
python3 api/server.py
```

### 3. Frontend Development
```bash
cd frontend
npm run dev
# Open http://localhost:5173
```

---

## 📚 Documentation

- **[Visibility Guide](VISIBILITY_FIXES.md)**: How the dashboard works.
- **[Security Manual](SECURITY_MANUAL.md)**: Understanding the IDS alerts.
- **[Frontend Testing](FRONTEND_TESTING.md)**: React/Vite/Flask setup.

---

## 🔑 Configuration

Managed via `secrets/keys.json` (gitignored):
```json
{
  "groq_api_key": "...",
  "openrouter_api_key": "...",
  "birdeye_api_key": "..."
}
```

---

*System is self-evolving. Logs are analyzed nightly for self-correction.*
