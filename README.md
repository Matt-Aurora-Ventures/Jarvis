# 🤖 Jarvis - Autonomous LifeOS System

<p align="center">
  <b>The central command center for your digital life.</b><br>
  <i>A self-improving AI that watches, learns, acts, and evolves.</i><br>
  <i>Deep visibility, autonomous security, and algorithmic trading.</i>
</p>

![Status](https://img.shields.io/badge/Status-ONLINE-success)
![Dashboard](https://img.shields.io/badge/Dashboard-v3.0-blue)
![Security](https://img.shields.io/badge/Security-IDS_ACTIVE-red)

**[📋 View CHANGELOG](CHANGELOG.md)** | **[🛣️ Roadmap](#-ultimate-dashboard-roadmap)**

---

**Jarvis** is an autonomous AI assistant that runs 24/7 on your Mac. It observes what you're doing, offers proactive suggestions, controls your computer via voice or text, conducts research, executes trading strategies, and continuously improves itself. **Jarvis v2.0** brings complete observability to autonomous operations—visualizing its entire cognition process, monitoring system security in real-time, and executing high-frequency trading strategies with full transparency.

## ✨ What Makes Jarvis Different

| Feature | Jarvis | ChatGPT/Claude |
|---------|--------|----------------|
| Runs locally 24/7 | ✅ | ❌ |
| Watches your screen | ✅ | ❌ |
| Controls your Mac | ✅ | ❌ |
| Real-time IDS monitoring | ✅ | ❌ |
| Proactive suggestions | ✅ | ❌ |
| Self-improving | ✅ | ❌ |
| Voice activated | ✅ | Limited |
| Algorithmic trading | ✅ | ❌ |
| Free to run | ✅ (with Ollama/Groq) | ❌ |

---

## 🎨 Trading Dashboard V2 - Ultra-Clean UI

**NEW**: Premium trading command center at `http://localhost:5173/trading`

**Note**: The UI is a working baseline and we’re just getting started — expect ongoing UX/UI polish and refinements.

### Design Philosophy
- **Airbnb-Style Aesthetic**: Ultra-clean white knight design with generous spacing
- **Premium Typography**: Inter font family with perfect hierarchy
- **Soft Shadows**: No harsh borders, subtle depth with elevation
- **Intuitive Navigation**: Icon-based sidebar, persistent top bar
- **Real-Time Updates**: Live position monitoring (5s), wallet data (10s)

### Core Features
- **📊 Live Position Card**: Real-time P&L, visual TP/SL bars, one-click exit
- **🛠️ Token Scanner**: Instant lookup, rug check (0-100 risk score), liquidity analysis
- **💬 Floating Chat**: Jarvis AI assistant with expandable panel
- **📈 Stats Grid**: Portfolio value, win rate, total trades, P&L tracking
- **🔄 Auto-Refresh**: Background polling, skeleton loading states

### Tech Stack
- React 18 + Vite 5 + TailwindCSS 3.3
- Zustand 4.4 for state management
- lightweight-charts for TradingView-style charts
- 14 REST API endpoints (45 planned)
- Modular CSS architecture (8 files, ~800 lines)
- Mobile-responsive grid layout

### 📁 Frontend Architecture (V2 Refactor - 2025-01)

```
frontend/src/
├── main.jsx              # Entry point → imports styles.css
├── App.jsx               # Router with refactored pages
├── styles.css            # CSS entry (imports all modules)
├── styles/               # Modular CSS
│   ├── tokens.css        # Design tokens (colors, spacing, typography)
│   ├── base.css          # Reset and body styles
│   ├── layout.css        # Nav, sidebar, grid containers
│   ├── components.css    # Buttons, cards, inputs, badges
│   ├── trading.css       # Position cards, scanner, charts
│   ├── chat.css          # Message bubbles, floating chat
│   ├── animations.css    # Keyframes, transitions
│   └── utilities.css     # Helper classes
├── components/
│   ├── ui/               # Button, Card, Badge, Input, Skeleton
│   ├── common/           # LoadingSpinner, ErrorState, EmptyState, Toast
│   ├── layout/           # TopNav, Sidebar
│   ├── trading/          # StatsGrid, PositionCard, TokenScanner
│   └── chat/             # FloatingChat
├── hooks/                # useApi, useWallet, useSniper, useCapabilities
├── lib/                  # api.js, format.js, constants.js, utils.js
├── stores/               # Zustand stores (jarvisStore, tradingStore)
└── pages/
    ├── DashboardNew.jsx  # ✅ Wired - main dashboard
    ├── ChatNew.jsx       # ✅ Wired - AI chat interface
    ├── TradingNew.jsx    # ✅ Wired - trading command center
    ├── Roadmap.jsx       # ✅ Wired - interactive roadmap
    ├── Research.jsx      # ✅ Refactored to white theme
    ├── Settings.jsx      # ✅ Refactored to white theme
    └── VoiceControl.jsx  # ✅ Refactored to white theme
```

### 🎯 What's Live Now
| Route | Page | Description |
|-------|------|-------------|
| `/` | Dashboard | Portfolio overview, quick stats, activity feed |
| `/chat` | Chat | Jarvis AI assistant with context awareness |
| `/trading` | Trading | Charts, positions, token scanner, order panel |
| `/voice` | Voice | Voice command interface with orb visualization |
| `/research` | Research | Web research with source citations |
| `/roadmap` | Roadmap | Interactive progress tracker with phases |
| `/settings` | Settings | API keys, preferences, system config |

### 🔌 Capability Detection
The `useCapabilities` hook probes API endpoints on load:
```javascript
import { useCapabilities } from '@/hooks'
const { capabilities, loading, refresh } = useCapabilities()
// capabilities.chat: 'available' | 'unavailable' | 'timeout'
```

---

## 🛣️ Ultimate Dashboard Roadmap

> **"An edge for the little guy"** - Democratizing institutional-grade trading tools.

### 📊 Phase 1: Trading Core (Next)
| Feature | Description |
|---------|-------------|
| **Charts** | TradingView (lightweight-charts) with real-time candles |
| **Order Panel** | Buy/Sell with TP/SL, position sizing calculator |
| **Order Book** | Live depth, whale alerts, spread indicator |

### 🛡️ Phase 2: Sentinel Mode
| Feature | Description |
|---------|-------------|
| **Auto-Trading** | Master toggle, phase indicator (Trial→Savage) |
| **Coliseum** | 81 strategies grid with live backtest results |
| **Approval Gate** | Pending trades queue, one-click approve/reject |
| **Kill Switch** | Emergency cancel all trades |

### 📈 Phase 3: Intelligence Layer
| Feature | Description |
|---------|-------------|
| **Signal Aggregator** | Multi-source trending (Birdeye + Gecko + DexScreener) |
| **Smart Money** | GMGN insider tracking, whale patterns |
| **Sentiment** | Real-time X/Twitter via Grok |
| **ML Regime** | Volatility prediction, strategy switching |

### 🎙️ Phase 4: LifeOS Integration
| Feature | Description |
|---------|-------------|
| **Voice Trading** | "Buy $50 of SOL" natural language |
| **Mirror Test** | Self-correction dashboard, improvement history |
| **Knowledge** | Notes search, research viewer, trading journal |

### 🔬 Phase 5: Advanced Tools
| Feature | Description |
|---------|-------------|
| **MEV Dashboard** | Jito bundles, sandwich scanner, SOR visualizer |
| **Perps** | Jupiter perps, 30x leverage, funding rates |
| **Multi-DEX** | Quote comparison (Jupiter/Raydium/Orca) |
| **Analytics** | Equity curve, trade heatmap, drawdown analysis |

### 🎨 Phase 6: Polish & Scale
| Feature | Description |
|---------|-------------|
| **Performance** | WebSocket, code splitting, virtual scroll |
| **Mobile** | PWA, push notifications, touch charts |
| **Themes** | Dark/light toggle, accent colors |
| **Onboarding** | Interactive tutorial, tooltips |

**Timeline**: ~19 days for complete implementation
**API Endpoints**: 45 total (14 current + 31 new)

---

At `http://localhost:5001`, Jarvis provides a SOC-style command center:

- **🛡️ Security Intelligence (IDS)**
  - Real-time Process Spawn Detection
  - Network Traffic Analysis (TX/RX Flow)
  - Suspicious Port Flagging & Connection Tracking
  - [Read Security Manual](SECURITY_MANUAL.md)

- **📈 Trading Pipeline**
  - Live Backtesting Progress (50 Tokens × 50 Strategies)
  - Solana Token Scanning (BirdEye + Jupiter cache + DexScreener)
  - Strategy Performance Tracking

- **💬 Communication Link**
  - Chat Console with `/exec`, `/log`, `/scan` commands
  - System Log Streaming
  - Direct Instruction Interface

---

## 🧠 Core Capabilities

### 🔬 Autonomous Research (NotebookLM)
- **Deep Research**: Creates research notebooks automatically
- **Source Truth**: Filters information via trusted sources
- **Study Guides**: Generates summaries from complex topics
- *Powered by `core/notebooklm_mcp.py`*

### 📈 Algorithmic Trading
- **Scanner**: Monitors top 50 high-volume Solana tokens
- **Backtester**: Validates 50+ strategies against 3-month data
- **Executor**: Paper-trading simulation environment
- **81 Extracted Strategies**: From Moon Dev's Algo Trading Roadmap
- **Mutation Engine**: AI-generated strategy variations
- *Powered by `scripts/run_trading_pipeline.py`*

### 🧮 Quantitative Trading Infrastructure (v2.1)

**Advanced Strategies** (`core/trading_strategies_advanced.py`):
- **Triangular Arbitrage**: Cross-rate exploitation (BTC→ETH→USDT→BTC) with flash loan support
- **Grid Trading**: Range-bound strategy for sideways markets with auto-level configuration
- **Breakout Trading**: Support/resistance detection with volume confirmation
- **Market Making**: Bid-ask spread capture with inventory management and volatility scaling

**Data Ingestion Layer** (`core/data_ingestion.py`):
- **WebSocket Streaming**: Real-time data from Binance, Kraken
- **CCXT Normalization**: Unified interface across 100+ exchanges
- **Tick Buffer**: Ring buffer for sub-second candle aggregation
- **Multi-Exchange Prices**: Spatial arbitrage detection

**ML Regime Detection** (`core/ml_regime_detector.py`):
- **Volatility Prediction**: Random Forest/Gradient Boosting classifiers
- **Regime Classification**: Low/Medium/High/Extreme volatility detection
- **Adaptive Strategy Switching**: Auto-switch between Grid, Mean Reversion, Trend Following
- **Feature Extraction**: RSI, Bollinger position, volatility metrics, momentum indicators

**MEV Execution** (`core/jito_executor.py`):
- **Jito Block Engine**: Bundle submission with simulation (Solana)
- **Sandwich Execution**: Front-run + victim + back-run atomic bundles
- **Smart Order Routing (SOR)**: Split orders across DEXs to minimize impact
- **MEV Scanner**: Opportunity detection in pending transactions

**Security Hardening** (`core/security_hardening.py`):
- **Encrypted Key Storage**: Fernet encryption with PBKDF2 key derivation
- **IP Whitelisting**: Per-key access control (lessons from 3Commas breach)
- **Secrets Scanner**: Codebase audit for leaked credentials
- **Slippage Tolerance**: Order rejection on excessive slippage

**Human Approval Gate** (`core/approval_gate.py`) - **NEW v2.2**:
- **Pre-Trade Approval**: No live trade executes without explicit human approval
- **Pending Queue**: Trade proposals with 5-minute expiry
- **Kill Switch**: Emergency cancellation of all pending trades
- **macOS Notifications**: Real-time alerts for approval requests
- **Audit Trail**: Full history of approved/rejected/killed trades

**Walk-Forward Validation** (`core/trading_pipeline.py`) - **NEW v2.2**:
- **Time-Series Cross-Validation**: Industry-standard out-of-sample testing
- **Anchored Splits**: 5-fold validation with expanding training window
- **Overfitting Prevention**: Tests strategies on multiple unseen periods
- **Pass/Fail Metrics**: Sharpe > 1.0, Drawdown < 20%, Win Rate > 40%
- **Promotion Rules**: Requires 3/5 passing folds before live deployment

**DSPy Strategy Optimization** (`core/dspy_classifier.py`) - **NEW v2.2**:
- **Strategy Classification**: Auto-categorize strategies (arbitrage, momentum, mean reversion, etc.)
- **Risk Analysis**: Identify failure modes and recommend controls
- **Patch Proposals**: AI-generated code improvements with risk scoring
- **Local LLM Support**: Works with Ollama (qwen2.5:7b) for privacy
- **BootstrapFewShot**: Optimizes prompts using 8 hand-crafted training examples

- **Slippage Tolerance**: Order rejection when execution deviates beyond threshold

*Full documentation: `docs/QUANT_TRADING_GUIDE.md`*

### 🧬 Self-Evolving Intelligence (Minimax 2.1 Core)
- **Primary Routing**: Minimax 2.1 via OpenRouter with Groq + Ollama fallback
- **Self-Correction Loop**: Nightly evaluation and patch proposals (Mirror Test)
- **Action Verification**: Execute → verify → log, with audit trail
- **Cost-Aware Routing**: Provider chain with health checks and spend controls

### 🧾 Tokenized Equities (xStocks + PreStocks)
- **Unified Universe**: Tokenized equities ingested alongside crypto candidates
- **Solana Mints**: Verified SPL mint extraction from issuer sources
- **Compliance Flags**: Default unknown gating with explicit opt-in
- **Cost Controls**: Fee model + spread/slippage estimates with edge gating
- **Event Catalysts**: X/Twitter signals mapped to equity tokens and horizons

### 💸 Fee Model + Edge Gating
- **All-in Cost Modeling**: Network fee + AMM fee + slippage + spread + issuer fees
- **Edge-to-Cost Ratio**: Enforced minimums (>=2.0, >=3.0 thin liquidity)
- **Conservative Defaults**: Safe fallback when issuer fees are unknown
- **Persistent Profiles**: Stored in `data/trader/knowledge/fee_profiles.json`

### 🛰️ Solana Execution Reliability
- **RPC Failover**: Primary + fallback endpoints with health checks
- **Circuit Breaker**: Endpoints temporarily disabled after 3 failures (60s recovery)
- **Simulation First**: Pre-flight sim before send
- **Confirmation Loop**: Confirmed/finalized status checks
- **Reconciliation**: On-chain balances reconciled with local intents

### 📊 Multi-Source Data Aggregation (v2.4) - **NEW**

Unified token data from multiple sources with automatic failover:

**Data Sources** (`core/signal_aggregator.py`):
- **DexScreener**: Primary price/volume data, momentum detection
- **BirdEye**: Solana token data, OHLCV charts
- **GeckoTerminal**: Pool data, alternative charts
- **DexTools**: Hot pairs, audit scores, token security
- **GMGN.ai**: Smart money tracking, insider activity, honeypot detection
- **Lute.gg**: Momentum calls, social trading signals

**Grok Sentiment Integration**:
- Real-time X/Twitter sentiment analysis via Grok
- Sentiment-weighted signal scoring
- Automatic sentiment exit triggers
- Budget controls and caching

**Smart Money Tracking** (`core/gmgn_metrics.py`):
- Insider trader activity monitoring
- Sniper wallet detection
- First 70 buyers PnL analysis
- Whale accumulation patterns
- Token security scoring (honeypot, LP burned, mintable)

**Momentum Signals** (`core/lute_momentum.py`):
- Lute.gg call tracking from X/Twitter
- Conviction-based scoring (low/medium/high)
- Multi-caller aggregation
- Sentiment validation of calls

### 🎯 Jupiter Order Management (v2.4) - **NEW**

Stop loss and take profit execution via Jupiter swaps:

**Core Module** (`core/jupiter_orders.py`):
- **Stop Loss**: Automatic sell when price drops below trigger
- **Take Profit**: Automatic sell when price exceeds target
- **TP Ladder**: Multi-level exits (default: +8%/+18%/+40%)
- **Trailing Stop**: Dynamic SL that follows price up
- **Time Stop**: Auto-exit after configurable period

**Order Types**:
| Type | Trigger | Default |
|------|---------|---------|
| Stop Loss | Price ≤ trigger | -9% |
| Take Profit | Price ≥ trigger | +20% |
| Trailing Stop | Price ≤ highest - trail% | 5% trail |
| Time Stop | Time > expiry | 90 minutes |

**Features**:
- Persistent orders (survives restarts)
- Breakeven adjustment after TP1
- Order history logging
- Daemon integration for monitoring

### 🔄 Execution Fallback System (v2.4) - **NEW**

Redundant trade execution with automatic venue failover:

**Execution Priority** (`core/execution_fallback.py`):
1. **Jupiter** (primary) - Best aggregation, most routes
2. **Raydium** (backup) - Major Solana DEX
3. **Orca** (backup) - Concentrated liquidity pools

**Features**:
- Quote comparison across venues for best price
- Circuit breaker per venue (3 failures → 2min cooldown)
- Automatic failover on execution failure
- Unified result format across venues

### 🧪 Audit Suite (Run-All)
- **One Command**: `python3 -m core.audit run_all`
- **Coverage**: RPC health, Jupiter quote/sim, sentiment caching, equities ingestion, fee model, catalyst mapping
- **Reports**: JSON output in `data/trader/audit_reports/`

### 🎯 LUT Micro-Alpha Trading Module (v2.3) - **NEW**

High-risk trending token subsystem designed for the **$20 → $1,000,000 Challenge**.

**Core Architecture** (`core/lut_micro_alpha.py`):
- **Multi-Source Trending**: Aggregates from Birdeye + GeckoTerminal + DexScreener
- **Velocity Tracking**: Monitors rank velocity (rising/falling trends)
- **Phase-Based Scaling**: Conservative Phase 0 (2% trades) → Scaled Phase 2 (3% trades)
- **Immediate Exit Planning**: TP ladder + SL persisted to disk on entry

**Trending Aggregator** (`core/trending_aggregator.py`):
- **Source Weights**: Birdeye (45%), GeckoTerminal (35%), DexScreener (20%)
- **Composite Ranking**: Multi-source confirmation improves rank
- **Historical Velocity**: Tracks rank changes over 15m/1h/4h windows
- **Rising Filter**: Isolates tokens with positive velocity

**Exit Intent System** (`core/exit_intents.py`):
- **TP Ladder**: TP1 @ +8% (60%), TP2 @ +18% (25%), TP3 @ +40% (15% runner)
- **Stop Loss**: -9% with breakeven adjustment after TP1
- **Time Stop**: 90-minute invalidation if TP1 not hit
- **Trailing Stop**: Activates after TP1, 5% trail
- **Sentiment Exit**: Immediate exit on xAI sentiment reversal

**Phase Configuration**:
| Phase | Module Weight | Max Trade | Max Exposure | Edge/Cost Min |
|-------|---------------|-----------|--------------|---------------|
| 0 (Trial) | 0.33 | 2% NAV | 10% NAV | 2.0x |
| 1 (Validated) | 0.50 | 2.5% NAV | 15% NAV | 2.5x |
| 2 (Scaled) | 0.75 | 3% NAV | 20% NAV | 3.0x |

**Promotion Requirements** (Phase 0 → 1):
- NetPnL > 0
- ProfitFactor ≥ 1.25
- MaxDrawdown ≤ 40% of module budget
- Enforcement Reliability ≥ 95%
- ≤ 1 catastrophic event

**Redundant Daemon Enforcement**:
- `core/trading_daemon.py`: Primary intent enforcement
- `core/lut_daemon.py`: Backup enforcement (run in parallel)
- File locking for concurrent access safety

### ⚡ Jupiter Perps Acceleration Layer (v2.3.1) - **SAVAGE MODE** 🔥 

High-conviction leveraged perpetuals for accelerated capital growth.

**Core Module** (`core/jupiter_perps.py`):
- **Eligible Assets**: SOL, BTC, ETH (high liquidity only)
- **Max Leverage**: 5x Phase 0, 15x Phase 1, **30x Phase 2 (SAVAGE MODE)**
- **Conviction-Based Scaling**: 30x requires conviction > 0.9
- **Ultra-Tight Stop Loss**: 1.2% stop for 30x (liquidation safety)
- **Funding Awareness**: Rejects trades with adverse funding rates

**Phase Configuration - SAVAGE SCALING**:
| Phase | Name | Max Leverage | Max Trades/Day | Max Margin | Min Conviction |
|-------|------|--------------|----------------|------------|----------------|
| 0 | Trial | 5x | 2 | 35% | - |
| 1 | Validated | 15x | 5 | 55% | - |
| 2 | **SAVAGE** | **30x** | **10** | **75%** | **0.9** |

**Stop Loss Scaling (Liquidation Protection)**:
| Leverage | Stop Loss | Liquidation Distance |
|----------|-----------|---------------------|
| ≥25x | 1.2% | ~3.3% |
| ≥15x | 2.0% | ~6.7% |
| ≥10x | 2.5% | ~10% |
| ≥5x | 3.0% | ~20% |
| <5x | 4.0% | >20% |

**Perps TP Ladder**:
- TP1: 50% @ +4% (or +1.5R)
- TP2: 30% @ +8% (or +2.5R)
- Runner: 20% with trailing stop

---

## 🔁 Mirror Test + Self-Correction (README_v2 Highlights)

Every night Jarvis can:
1. Replay the last 24 hours using Minimax 2.1
2. Score its own performance (latency, accuracy, user satisfaction)
3. Propose refactors and patches
4. Dry-run changes on historical scenarios
5. Auto-apply if confidence threshold is met

## ⚔️ Paper-Trading Coliseum (README_v2 Highlights)
- 81 extracted strategies
- 10 randomized backtests per strategy
- Auto-prune after repeated failures
- Promotion only with strong Sharpe + drawdown metrics

## 🎙️ Streaming Consciousness Voice (README_v2 Highlights)
- Barge-in prediction and interruption handling
- Ring-buffered context for low-latency responses
- Pre-cached likely intents for instant replies

## 🔐 Action Verification Loop (README_v2 Highlights)
- Execute → verify → log
- Audit trail for actions and follow-up checks
- Time Stop: 60 minutes

**Promotion Requirements**:
- **Phase 0 → 1**: 10 trades, PF ≥ 1.25, MaxDD ≤ 15%, 0 liquidations
- **Phase 1 → 2**: 25 trades, PF ≥ 1.5, MaxDD ≤ 10%, 97%+ enforcement reliability

*State files: `~/.lifeos/trading/{lut_module_state,perps_state,exit_intents,execution_reliability}.json`*

### 🎤 Voice Control
- **Wake word**: "Hey Jarvis" activates listening
- **Natural conversation**: Chat like you would with a person
- **Hotkey**: Ctrl+Shift+Up for instant access
- **Barge-in capable**: Interrupt mid-response
- **Coqui XTTS voice clone (optional)**: Local voice cloning with 6–15s reference audio (Python 3.11 + ~2GB model download)
- **Streaming consciousness**: Ring buffer context with intent prediction
- **Cost-optimized**: Smart routing between Minimax and Whisper

### 🖥️ Computer Control
- **Open apps & windows**: "Open Safari", "Switch to VS Code"
- **Compose emails**: "Send an email to John about the meeting"
- **Google searches**: "Search for crypto trading strategies"
- **Create notes & reminders**: "Remind me to call mom at 5pm"
- **Keyboard shortcuts**: Copy, paste, save, undo, and more

### 📓 Local Knowledge Engine
- **Distilled note archive**: All notes/research saved as `.md/.txt/.py` in `data/notes/`
- **Auto-summary + prompts**: Every capture creates concise summary + reusable prompt snippet
- **Command-line + voice parity**: `lifeos capture`, voice `log`, and missions share same pipeline
- **Raw artifact storage**: curl outputs, transcripts, and CLI logs saved for full traceability

### 👁️ Activity Monitoring
- **App usage tracking**: Know where your time goes
- **Productivity insights**: Identify patterns and distractions
- **Screen context**: Jarvis sees what you see
- **Privacy-first**: All data stays local

### 🔄 Self-Evolution
- **Auto-upgrades on boot**: Applies pending improvements automatically
- **Mirror Test**: Nightly self-correction (3am) via Minimax 2.1 reflection
- **Skill learning**: Add new capabilities via simple Python modules
- **Error analysis**: Learns from failures and fixes itself
- **Continuous iteration**: Gets smarter every day

### 🌙 Idle Missions (Auto-Research)
- **MoonDev Watcher**: Tracks official MoonDevOnYT X feed for new HFT drops
- **AlgoTradeCamp Digest**: Snapshots algotradecamp.com for lessons and tactics
- **MoonDev YouTube Harvester**: Pulls transcripts via yt-dlp and summarizes key experiments
- **Self-Improvement Pulse**: Reviews provider errors + memory to prioritize upgrades

### 🔊 Offline Voice
- **Piper TTS**: Bundled model auto-downloads to `data/voices/`, works with no internet
- **Voice fallback**: Seamlessly drops to macOS `say` only if local synthesis fails
- **Voice clone**: Optional Coqui XTTS local cloning; enable via `lifeos/config/lifeos.config.local.json`
- **Voice doctor**: `./bin/lifeos doctor --voice` for full mic/STT/TTS diagnostics
- **Configurable**: Customize `voice.tts_engine`, `piper_model`, and `speech_voice` in config

---

## 🚀 Quick Start

### Installation & Setup

```bash
# Clone the repo
git clone https://github.com/Matt-Aurora-Ventures/Jarvis.git
cd Jarvis

# Set up environment
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Configure API keys
mkdir -p secrets
cat > secrets/keys.json <<'EOF'
{
  "groq_api_key": "YOUR_GROQ_KEY",
  "openrouter_api_key": "YOUR_OPENROUTER_KEY",
  "birdeye_api_key": "OPTIONAL_BIRDEYE_KEY",
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

### Optional: Coqui Voice Clone (Python 3.11)

Coqui XTTS voice cloning requires Python 3.11. If you want the local clone voice,
create a dedicated venv (`venv311`) and install the full macOS stack plus TTS.
`./bin/lifeos` auto-detects `venv311` when it exists.

```bash
# Install Python 3.11 (macOS)
brew install python@3.11

# Create a dedicated venv for voice cloning
/usr/local/bin/python3.11 -m venv venv311
source venv311/bin/activate

# Install macOS deps + Coqui TTS
pip install -r requirements-mac.txt
pip install TTS
```

If you hit `llvmlite` build errors on macOS, pin known-good versions first:

```bash
cat > constraints-voice.txt <<'EOF'
numpy==1.26.4
numba==0.60.0
llvmlite==0.43.0
EOF

pip install -r requirements-mac.txt -c constraints-voice.txt
pip install TTS -c constraints-voice.txt
```

### Launch the Ecosystem Dashboard

```bash
# Monitor everything in one place
python3 scripts/progress_dashboard.py
# Open http://localhost:5001
```

### Start Sub-Systems

```bash
# Terminal 2: Run Trading Pipeline
python3 scripts/run_trading_pipeline.py

# Terminal 3: Start Voice/Frontend API
python3 api/server.py
```

### Frontend Development

```bash
cd frontend
npm run dev
# Open http://localhost:5173
```

---

## 🎯 Commands Reference

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

### Trading Commands

| Command | Description |
|---------|-------------|
| `lifeos trading coliseum start` | Start paper-trading coliseum |
| `lifeos trading coliseum results` | View arena results |
| `lifeos trading coliseum cemetery` | Check deleted strategies + autopsy |

### Mirror Test Commands

| Command | Description |
|---------|-------------|
| `lifeos mirror report` | See last mirror test report |
| `lifeos mirror diff 2026-01-01 2026-01-02` | Compare snapshots |
| `lifeos mirror review` | Manually approve pending changes |

---

## 📈 Trading & Research

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

1. **P0 - Quick Wins**: 200-Day MA, Dual MA Crossover, ADX Enhanced
2. **P1 - Core**: Funding Rate Arbitrage, RSI Mean Reversion, Momentum
3. **P2 - Advanced**: HMM Regime, Dynamic Optimization, Triplets

### Paper-Trading Coliseum

Auto-backtest all strategies 24/7:

```
Each strategy → 10 random 30-day backtests
    ↓
Metrics: Sharpe, Drawdown, Win Rate, Profit Factor
    ↓
Auto-Prune: 5 failures → Deletion
    ↓
Auto-Promote: Sharpe >1.5 → live_candidates/
```

### Mutation Engine

Minimax 2.1 generates strategy variations:

```
Original: RSI(14) < 30 (oversold)
    ↓
Minimax Mutations:
    ├─ RSI(10) < 25 (more aggressive)
    ├─ RSI(20) < 35 (more conservative)
    └─ RSI(14) < 30 + Volume > 2x avg (volume filter)
    ↓
All variations → Coliseum → Best variant survives
```

### Data Sources

- **Hyperliquid**: Perp market data, funding rates
- **Moon Dev API**: Liquidation signals
- **Birdeye**: Solana token data
- **YouTube**: Trading content transcripts
- **Notion**: Strategy documentation

---

## 🤖 Provider Stack

### Minimax 2.1 Integration

Intelligent provider routing with context-aware selection:

```
User Input
    ↓
Intelligent Router (parallel health checks)
    ↓
┌────────────────────────────────────────┐
│ Minimax 2.1 (Primary)                  │ ← Conversational, nuanced
│   ├─ Streaming mode: Voice interaction │
│   ├─ Batch mode: Trading simulations   │
│   └─ Reflection mode: Mirror Test      │
└────────────────────────────────────────┘
    ↓ (fallback)
Groq Llama 3.3 70B (Tool Execution) ← Ultra-fast, FREE
    ↓ (offline fallback)
Ollama Qwen 2.5 (Local) ← Works without internet
```

**Context-aware selection**:
- Voice/Chat → Minimax (streaming)
- Tool execution → Groq (speed)
- Reflection → Minimax (quality)

### Mirror Test Workflow

Daily self-correction cycle (3am):

```
[1] Log Ingestion
    └─ Parse last 24h: actions, conversations, errors
    
[2] Minimax Replay
    └─ Re-run decisions with current model
    └─ Compare: What would I do differently now?
    
[3] Performance Scoring
    └─ Latency: Did responses take too long?
    └─ Accuracy: Did actions achieve intended result?
    └─ User Satisfaction: Follow-up questions? Corrections?
    
[4] Refactor Proposals
    └─ Generate Python code improvements
    └─ Update system_instructions.md
    └─ Optimize prompt templates
    
[5] Dry-Run Validation
    └─ Test changes against 100 historical scenarios
    └─ Ensure no regressions
    
[6] Auto-Apply (if score > 0.85)
    └─ Merge changes
    └─ Commit: "Mirror Test improvement: +3.2% accuracy"
```

---

## 🔌 MCP Autonomy Stack

The MCP (Model Context Protocol) stack gives Jarvis "hands" to interact with the system.

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

## ⚙️ Configuration

### Main Config: `lifeos/config/lifeos.config.json`

```json
{
  "voice": {
    "wake_word": "jarvis",
    "chat_silence_limit": 60,
    "speak_responses": true,
    "tts_engine": "piper",
    "piper_model": "en_US-amy-low.onnx",
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

### Minimax 2.1 Settings: `lifeos/config/minimax.config.json`

```json
{
  "minimax": {
    "model": "minimax/minimax-01",
    "via": "openrouter",
    "streaming": true,
    "context_window": 8000,
    "cost_per_1m_input": 0.30,
    "cost_per_1m_output": 1.20,
    "use_for": ["voice", "chat", "mirror_test", "trading_sims"]
  },
  "intelligent_routing": {
    "parallel_health_checks": true,
    "selection_latency_ms": 200,
    "context_rules": {
      "voice": "minimax",
      "tool_execution": "groq",
      "reflection": "minimax",
      "offline": "ollama"
    }
  },
  "mirror_test": {
    "enabled": true,
    "schedule": "0 3 * * *",
    "min_improvement_score": 0.85,
    "auto_apply": true,
    "snapshot_retention_days": 60,
    "metrics": ["latency", "accuracy", "user_satisfaction"]
  },
  "streaming_consciousness": {
    "enabled": true,
    "ring_buffer_tokens": 8000,
    "barge_in_detection": true,
    "pre_cache_responses": 3,
    "audio_cue_threshold": 0.7
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

## 🎤 Streaming Consciousness Voice

### Activate Continuous Mode

```bash
./bin/lifeos chat --streaming --minimax
```

**How It Works:**

1. **Ring Buffer Context**: Last 8,000 tokens (30s) always in memory
2. **Intent Prediction**: Minimax predicts your next 3 likely intents
3. **Pre-Cached Responses**: Generates all 3 responses in advance
4. **Barge-In Detection**:
   - Audio volume spike
   - Pitch change
   - Cadence break
   → Instant response delivery (<200ms)

**Example Session:**

```
[You speak, Jarvis buffers context in real-time]

You: "Hey Jarvis, what's the best—"
  [Minimax predicts: "crypto", "AI stock", "productivity app"]
  [Pre-caches 3 responses]

You: "—crypto arbitrage strategy right now?"
  [Delivers pre-cached "crypto" response instantly]

Jarvis: "Based on current vol spreads, CEX-DEX arb on SOL/USDC 
         via Jupiter is yielding 0.3-0.8% per cycle..."

You: [Interrupting] "Wait, what about Base chain?"
  [Audio spike detected, pauses mid-sentence]

Jarvis: "Good catch—Base has lower gas, making arb viable at 
         0.2% spreads vs 0.3% on Solana..."
```

---

## 🛡️ Security & OPSEC

### Secrets Management

- **Location**: `secrets/keys.json` (gitignored)
- **Never commit**: API keys, tokens, credentials
- **Environment variables**: Preferred for CI/CD
- **Rotation**: Rotate immediately if exposed

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
- **Code validation**: All generated code checked
- **Protected paths**: Core files locked from modification
- **Sandboxed shell**: MCP shell restricted to LifeOS directory
- **Action verification**: 3-step verification loop for all actions

### Action Verification (New)

Every action now has a 3-step verification loop:

```python
# Example: Send email
actions.execute_action("send_email", to="john@example.com", subject="Meeting")
    ↓
action_verifier.verify(action="send_email", expected_outcome="email in sent folder")
    ↓
action_verifier.learn(success=True, latency_ms=1200)
    ↓
Report: "Email sent and verified in Sent folder (1.2s)"
```

### Mirror Test Safety

- All refactor proposals run **dry-run validation** against 100 historical scenarios
- Requires 85% improvement score to auto-apply
- Manual review available: `./bin/lifeos mirror review`
- Git history preserves all changes with rollback

### Coliseum Sandboxing

- Paper-trading uses **simulated funds only**
- Live promotion requires human approval
- All strategy code executes in restricted environment (no file system access)

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

## 💰 Cost Comparison

| Provider | Cost | Speed | Quality |
|----------|------|-------|---------|
| **Groq** | FREE | ⚡ Ultra-fast | Great |
| **Ollama** | FREE | Medium | Good |
| **Minimax 2.1** | ~$50/mo | Fast | Excellent |
| **Gemini** | ~$5-20/mo | Fast | Excellent |
| **OpenAI** | ~$10-30/mo | Fast | Excellent |

### Detailed Minimax Cost Breakdown

| Task | Minimax 2.1 | GPT-4 Turbo | Claude Sonnet |
|------|-------------|-------------|---------------|
| 1M tokens voice chat | $1.50 | $15.00 | $15.00 |
| 100 trading backtests | $0.45 | $4.50 | $4.50 |
| Nightly mirror test | $0.30 | $3.00 | $3.00 |
| **Monthly (heavy use)** | **~$50** | **~$500** | **~$500** |

**Jarvis v1.0 with Minimax = 90% cost reduction vs GPT-4**

---

## 👨‍💻 Development

### Project Structure

```
core/           # Core modules (Python)
tests/          # Test suite
docs/           # Documentation
web/            # Flask control deck
frontend/       # React/Vite frontend
lifeos/config/  # Configuration files
skills/         # Skill modules (Python)
scripts/        # Automation scripts
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

## �️ Recent Fixes & Improvements (January 2026)

### Terminal Execution Reliability
- **Shell Executor Bypass**: Created `core/shell_executor.py` to bypass VS Code terminal hangs
- **Timeout Protection**: All subprocess calls now have aggressive 10-30s timeouts
- **Command Watchdog**: Background monitor kills stuck processes automatically (`core/command_watchdog.py`)
- **Git Lock Cleanup**: Auto-removes stale `.git/index.lock` files from hung operations
- **Command Validator**: Blocks dangerous command patterns that cause hangs (`core/command_validator.py`)

### Trading Infrastructure
- **Position Monitoring**: `scripts/monitor_positions.py` with async timeout protection
- **Exit Intent System**: Auto-tracking of TP ladders and stop losses
- **X/Twitter Sentiment**: Grok-4 integration for real-time sentiment analysis via xAI API
- **DexScreener Integration**: Live price feeds with buy/sell transaction analysis

### RPC & API Configuration
- **Multi-Provider Setup**: Helius (primary) + Alchemy + public fallback for Solana
- **Jupiter v6 API**: Quote and swap functionality with caching
- **BirdEye Scanner**: Top token and whale tracking

### MCP Server Status
| Server | Status | Notes |
|--------|--------|-------|
| Git Server | ✅ Working | Commit, status, log operations |
| System Monitor | ✅ Working | CPU, memory, network stats |
| Obsidian Memory | ✅ Working | Knowledge graph operations |
| Shell Server | ⚠️ Limited | Use shell_executor.py as bypass |

### Configuration Requirements
```bash
# Required API keys in secrets/keys.json:
{
  "xai": {"api_key": "..."}, # For X/Twitter sentiment
  "birdeye": {"api_key": "..."}, # For Solana token scanning
  "helius": {"api_key": "..."}, # For Solana RPC (recommended)
  "groq_api_key": "...", # For LLM calls
}
```

---

## �🗺️ Roadmap

### Completed ✓

- [x] Voice control & wake word
- [x] Computer control (apps, email, search)
- [x] Proactive 15-min suggestions
- [x] Self-evolution system
- [x] Research & document creation
- [x] Trading strategy extraction (81 strategies)
- [x] MCP autonomy stack
- [x] Claude + GPT hybrid collaboration
- [x] Minimax 2.1 integration
- [x] Intelligent provider routing
- [x] Mirror Test self-correction
- [x] Paper-Trading Coliseum
- [x] Streaming consciousness voice
- [x] Action verification loops
- [x] v2.0 Ecosystem Dashboard & Security IDS
- [x] **v2.1 Quantitative Trading Infrastructure** (Jan 2026)
  - [x] Triangular Arbitrage algorithm
  - [x] Grid Trading strategy
  - [x] Breakout Trading strategy
  - [x] Market Making with inventory management
  - [x] WebSocket data ingestion (Binance/Kraken)
  - [x] CCXT exchange normalization
  - [x] ML volatility regime detection
  - [x] Adaptive strategy switching
  - [x] Jito MEV executor (Solana)
  - [x] Smart Order Routing (SOR)
  - [x] Encrypted API key storage
  - [x] Slippage tolerance checks
- [x] **v2.3 LUT Micro-Alpha + Jupiter Perps** (Jan 2026)
  - [x] Multi-source trending aggregator (Birdeye + Gecko + DexScreener)
  - [x] Velocity-based token ranking
  - [x] Exit intent system with TP ladder + SL + time stops
  - [x] Phase-based scaling (Trial → Validated → Scaled)
  - [x] Jupiter Perps acceleration layer
  - [x] Redundant daemon enforcement (dual daemons)
  - [x] Execution reliability tracking
  - [x] Jupyter cell bundle generation for trade monitoring

### In Progress 🚧

- [ ] **Strategy optimization loop**: Hyperparameter tuning via Optuna
- [ ] **Multi-day mirror test trends**: 7-day rolling performance analysis
- [ ] **Cross-chain MEV**: Flashbots integration for Ethereum
- [ ] **ML model retraining**: Scheduled regime model updates

### Next Steps (Detailed Plan) 📋

#### Phase 1: Strategy Optimization (Q1 2026)
| Task | Description | Priority |
|------|-------------|----------|
| Hyperparameter Tuning | Integrate Optuna for Grid/Breakout parameter optimization | P0 |
| Walk-Forward Validation | Implement proper out-of-sample testing | P0 |
| Strategy Correlation | Detect and mitigate correlated strategies | P1 |
| Execution Quality | Track slippage, fill rates, latency metrics | P1 |
| Live Paper Trading | 30-day continuous paper trading with real spreads | P1 |

#### Phase 2: Infrastructure Hardening (Q1 2026)
| Task | Description | Priority |
|------|-------------|----------|
| Multi-Exchange Arbitrage | Extend triangular arb across Binance + Kraken + Coinbase | P0 |
| Order Book Depth | Add L2/L3 data ingestion for better execution | P0 |
| Flashbots Integration | Ethereum MEV via Flashbots Protect | P1 |
| Rate Limit Manager | Centralized exchange rate limit coordination | P1 |
| Disaster Recovery | Automated position unwinding on system failure | P1 |

#### Phase 3: ML Enhancement (Q2 2026)
| Task | Description | Priority |
|------|-------------|----------|
| Sentiment Pipeline | Twitter/Telegram sentiment → trading signals | P0 |
| News Event Detection | NLP for market-moving news classification | P1 |
| Regime Ensemble | Multiple ML models with voting for regime prediction | P1 |
| Feature Store | Centralized feature computation and caching | P2 |
| Online Learning | Incremental model updates on new data | P2 |

#### Phase 4: Autonomous Trading (Q2-Q3 2026)
| Task | Description | Priority |
|------|-------------|----------|
| 1000-Backtest Validation | Pass 1000 diverse market conditions before live | P0 |
| Capital Allocation | Kelly criterion + regime-aware sizing | P0 |
| Human Override | Telegram/Discord alerts with quick-kill commands | P0 |
| Profit Reinvestment | Automatic compounding with drawdown limits | P1 |
| Tax Tracking | Transaction logging for tax reporting | P2 |

#### Phase 5: Multi-Agent & Scaling (Q3-Q4 2026)
| Task | Description | Priority |
|------|-------------|----------|
| Multi-Agent Swarm | Specialized agents (scanner, executor, risk) | P1 |
| Strategy Marketplace | Community-contributed strategies with rev share | P2 |
| Multi-Chain Deployment | Solana + Base + Arbitrum + Polygon | P2 |
| iOS Companion App | Real-time P&L, alerts, manual overrides | P2 |
| Plugin System | Third-party data sources and strategy plugins | P3 |

### Long-Term Vision 🔮

- [ ] Fully autonomous 24/7 trading with human oversight
- [ ] Self-funding bot (profits cover infrastructure costs)
- [ ] Cross-strategy capital allocation optimization
- [ ] Institutional-grade risk management
- [ ] White-label solution for other traders

---

## 📚 Documentation

- **[Visibility Guide](VISIBILITY_FIXES.md)**: How the dashboard works
- **[Security Manual](SECURITY_MANUAL.md)**: Understanding IDS alerts
- **[Frontend Testing](FRONTEND_TESTING.md)**: React/Vite/Flask setup
- **[Architecture Blueprint](docs/)**: System design and architecture
- **[Changelog](CHANGELOG.md)**: Full version history

---

## 🤝 Contributing

PRs welcome! Please:

1. Read safety guidelines in `core/guardian.py`
2. Run tests before submitting
3. Never commit secrets or personal data
4. Follow existing code style

---

## 📄 License

MIT License - Use freely, modify freely, just don't blame us if Jarvis becomes too helpful.

---

<p align="center">
  <b>Built by <a href="https://github.com/Matt-Aurora-Ventures">Matt Aurora Ventures</a></b><br>
  <i>"The best AI is the one that makes you better."</i>
</p>

## Magnus 0x Audit Certification

Security Grade: Institutional / Production Ready

Improvements Made:
- Enforced `POLY_GNOSIS_SAFE=2` guardrails on transaction paths (swap execution + Jito bundles).
- Added WebSocket heartbeat timeout + exponential reconnect backoff for Binance/Kraken feeds.
- Fee-aware spread guardrails for MarketMaker to prevent post-fee leakage.
- Enabled JSON-structured logging for trading daemon via `LIFEOS_LOG_JSON=1`.
- Added env-driven kill switch (`LIFEOS_KILL_SWITCH`) for immediate trade suppression.

God Tier Feature Added:
- TWAP schedule builder in `SmartOrderRouter` (time-sliced + venue-split execution to reduce impact).

Death Scenarios Patched:
- 503/429 API failures now back off exponentially across core price/data clients.
- Silent WebSocket stalls force reconnect on heartbeat timeout.
- Blockhash drift recovery hook added for Solana swap execution (optional re-sign).

## README_v2 (Merged)

# Jarvis - Autonomous Self-Evolving AI

<p align="center">
  <b>Not a chatbot. A system that thinks, learns, and evolves.</b><br>
  <i>Powered by Minimax 2.1 - The fastest self-improving AI on your Mac.</i>
</p>

---

**Jarvis v1.0** is a **self-correcting autonomous AI** that runs 24/7, observes your work, controls your Mac, trades crypto strategies, and **rewrites its own code** to get smarter every night.

**🆕 Minimax 2.1 Integration** - 3x faster reasoning, 60% cost reduction, continuous consciousness mode.

---

## What Makes Jarvis Different

| Feature | Jarvis v1.0 | ChatGPT/Claude | Auto GPT |
|---------|-------------|----------------|----------|
| **Self-Correcting** | ✓ Nightly dream cycle | ✗ Static | ✗ Static |
| **Continuous Consciousness** | ✓ Streaming context | ✗ Isolated messages | ✗ Sequential |
| **Auto-Backtests Trading** | ✓ Paper-Trading Coliseum | ✗ No trading | ✗ No trading |
| **Verifies Own Actions** | ✓ 3-step feedback loops | ✗ Fire and forget | ✗ No verification |
| **Runs Locally 24/7** | ✓ | ✗ | Partial |
| **Cost per 1M tokens** | $0.30 (Minimax) | $15 (GPT-4) | $15 (GPT-4) |

---

## Key Features

### 🧠 Minimax 2.1 Core

- **Intelligent Routing** - Not a fallback chain, a **context-aware selector**
- **3-Provider Hybrid:**
  - **Minimax 2.1** - Conversational nuance, high-frequency reasoning (1M tokens = $0.30)
  - **Groq Llama 3.3 70B** - Ultra-fast tool use (FREE)
  - **Ollama** - Offline fallback (FREE)
- **Streaming Context** - Last 30 seconds buffered, not request/response loop
- **Parallel Health Checks** - Sub-200ms provider selection

### 🔁 The Mirror Test (Self-Correction Loop)

**Every night at 3am, Jarvis:**
1. **Replays** the last 24 hours using Minimax 2.1
2. **Scores** its own performance (latency, accuracy, user satisfaction)
3. **Refactors** `system_instructions.md` and Python modules
4. **Dry-Runs** changes against historical scenarios
5. **Auto-Applies** if improvement score > 85%

**Result:** Jarvis gets measurably smarter every day without human intervention.

### ⚔️ Paper-Trading Coliseum (Auto-Backtesting)

**81 Extracted Strategies** → **Minimax-Powered Simulation** → **Self-Pruning**

- Each strategy runs **10 randomized 30-day backtests** before touching live markets
- **Auto-Deletion:** If a strategy fails 5 simulations → deleted + autopsy logged
- **Mutation Engine:** Minimax generates strategy variations (e.g., RSI 30/70 → RSI 25/75)
- **Live Promotion:** Only strategies with Sharpe >1.5 across 10 tests go live

**Metrics Tracked:**
- Sharpe Ratio, Max Drawdown, Win Rate, Profit Factor
- Stored in `data/trading/coliseum/arena_results.db`

### 🎙️ Streaming Consciousness Voice

**Not Command/Response - Continuous Interaction**

- **Barge-In Prediction:** Audio cues (volume spike + pitch change) trigger instant response
- **Pre-Cached Responses:** Minimax predicts your next 3 likely intents
- **Ring Buffer Context:** Last 8,000 tokens (30 seconds) always in memory
- **Natural Interruption:** "Hold on..." recognized mid-sentence, response paused

**Example:**
```
You: "Hey Jarvis, research the best—"
Jarvis: (predicts "crypto" or "AI stocks" based on history, pre-buffers both)
You: "—crypto arbitrage strategies"
Jarvis: (instantly delivers pre-cached crypto response, <200ms latency)
```

### 🔐 Action Verification Loop

**Never Execute Without Feedback**

Old Flow:
```
User: "Send email" → Email sent → Done (no verification)
```

New Flow:
```
User: "Send email" 
  → Email sent 
  → Verify: Check Mail.app sent folder 
  → Learn: Log success/failure 
  → Report: "Email sent, confirmed in Sent folder"
```

Every action (`actions.py`) now has corresponding verification in `action_verifier.py`.

---

## Architecture Overview

```
jarvis/
├── core/
│   ├── intelligent_provider_router.py   # Minimax-first routing
│   ├── action_verifier.py               # 3-step verify loops
│   ├── streaming_consciousness.py       # Continuous context mode
│   ├── evolution/
│   │   ├── gym/
│   │   │   ├── mirror_test.py           # Nightly self-correction
│   │   │   ├── replay_sim.py            # Log replay engine
│   │   │   ├── performance_scorer.py    # Self-assessment
│   │   │   └── refactor_agent.py        # Auto-code improvement
│   │   ├── snapshots/                    # Daily system states
│   │   └── diffs/                        # Generated improvements
│   └── trading_coliseum.py               # Auto-backtest + pruning
├── data/
│   └── trading/
│       ├── coliseum/
│       │   ├── arena_results.db          # Backtest performance
│       │   ├── historical_snapshots/     # OHLCV cache
│       │   └── strategy_cemetery/        # Deleted strategies
│       └── live_candidates/              # Promoted strategies
└── lifeos/config/
    └── minimax.config.json               # Minimax 2.1 settings
```

### Minimax 2.1 Provider Stack

```
User Input
    ↓
Intelligent Router (parallel health checks)
    ↓
┌────────────────────────────────────────┐
│ Minimax 2.1 (Primary)                  │ ← Conversational, nuanced
│   ├─ Streaming mode: Voice interaction │
│   ├─ Batch mode: Trading simulations   │
│   └─ Reflection mode: Mirror Test      │
└────────────────────────────────────────┘
    ↓ (fallback)
Groq Llama 3.3 70B (Tool Execution) ← Ultra-fast, FREE
    ↓ (offline fallback)
Ollama Qwen 2.5 (Local) ← Works without internet
```

**Key Difference:** Not a waterfall, a **context-aware selection**:
- Voice/Chat → Minimax (streaming)
- Tool execution → Groq (speed)
- Reflection → Minimax (quality)

---

## Quick Start

```bash
# Clone and setup
git clone https://github.com/Matt-Aurora-Ventures/Jarvis.git
cd Jarvis
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Configure Minimax API key
mkdir -p secrets
cat > secrets/keys.json <<'EOF'
{
  "openrouter_api_key": "YOUR_OPENROUTER_KEY",
  "groq_api_key": "YOUR_GROQ_KEY"
}
EOF

# Start Jarvis with Minimax 2.1
./bin/lifeos on --apply --minimax

# Enable Mirror Test (nightly self-correction)
./bin/lifeos config set mirror_test.enabled true
./bin/lifeos config set mirror_test.schedule "0 3 * * *"  # 3am daily

# Activate Paper-Trading Coliseum
./bin/lifeos trading coliseum start --strategies all

# Streaming voice mode
./bin/lifeos chat --streaming
```

---

## Configuration

### Minimax 2.1 Settings: `lifeos/config/minimax.config.json`

```json
{
  "minimax": {
    "model": "minimax/minimax-01",
    "via": "openrouter",
    "streaming": true,
    "context_window": 8000,
    "cost_per_1m_input": 0.30,
    "cost_per_1m_output": 1.20,
    "use_for": ["voice", "chat", "mirror_test", "trading_sims"]
  },
  "intelligent_routing": {
    "parallel_health_checks": true,
    "selection_latency_ms": 200,
    "context_rules": {
      "voice": "minimax",
      "tool_execution": "groq",
      "reflection": "minimax",
      "offline": "ollama"
    }
  },
  "mirror_test": {
    "enabled": true,
    "schedule": "0 3 * * *",
    "min_improvement_score": 0.85,
    "auto_apply": true,
    "snapshot_retention_days": 60,
    "metrics": ["latency", "accuracy", "user_satisfaction"]
  },
  "streaming_consciousness": {
    "enabled": true,
    "ring_buffer_tokens": 8000,
    "barge_in_detection": true,
    "pre_cache_responses": 3,
    "audio_cue_threshold": 0.7
  }
}
```

---

## Mirror Test Workflow

### Daily Self-Correction Cycle (3am)

```
[1] Log Ingestion
    └─ Parse last 24h: actions, conversations, errors
    
[2] Minimax Replay
    └─ Re-run decisions with current model
    └─ Compare: What would I do differently now?
    
[3] Performance Scoring
    └─ Latency: Did responses take too long?
    └─ Accuracy: Did actions achieve intended result?
    └─ User Satisfaction: Follow-up questions? Corrections?
    
[4] Refactor Proposals
    └─ Generate Python code improvements
    └─ Update system_instructions.md
    └─ Optimize prompt templates
    
[5] Dry-Run Validation
    └─ Test changes against 100 historical scenarios
    └─ Ensure no regressions
    
[6] Auto-Apply (if score > 0.85)
    └─ Merge changes
    └─ Commit: "Mirror Test improvement: +3.2% accuracy"
```

**View Results:**
```bash
# See last mirror test report
./bin/lifeos mirror report

# Compare snapshots
./bin/lifeos mirror diff 2026-01-01 2026-01-02

# Manually approve pending changes
./bin/lifeos mirror review
```

---

## Paper-Trading Coliseum

### Auto-Backtest All Strategies

```bash
# Start coliseum (runs 24/7)
./bin/lifeos trading coliseum start

# View arena results
./bin/lifeos trading coliseum results

# Check strategy graveyard (deleted strategies + autopsy)
./bin/lifeos trading coliseum cemetery
```

### Strategy Lifecycle

**Phase 1: Extraction** (81 strategies from Moon Dev roadmap)
```
data/notion_deep/strategy_catalog.json
```

**Phase 2: Simulation** (Paper-Trading Coliseum)
```
Each strategy → 10 random 30-day backtests
    ↓
Metrics: Sharpe, Drawdown, Win Rate, Profit Factor
    ↓
Auto-Prune: 5 failures → Deletion
    ↓
Auto-Promote: Sharpe >1.5 → live_candidates/
```

**Phase 3: Live (Human-Approved Only)**
```
./bin/lifeos trading live promote STRAT-042
```

### Mutation Engine

Minimax 2.1 generates strategy variations:

```
Original: RSI(14) < 30 (oversold)
    ↓
Minimax Mutations:
    ├─ RSI(10) < 25 (more aggressive)
    ├─ RSI(20) < 35 (more conservative)
    └─ RSI(14) < 30 + Volume > 2x avg (volume filter)
    ↓
All variations → Coliseum → Best variant survives
```

---

## Streaming Consciousness Voice

### Activate Continuous Mode

```bash
./bin/lifeos chat --streaming --minimax
```

**How It Works:**

1. **Ring Buffer Context** - Last 8,000 tokens (30s) always in memory
2. **Intent Prediction** - Minimax predicts your next 3 likely intents
3. **Pre-Cached Responses** - Generates all 3 responses in advance
4. **Barge-In Detection:**
   - Audio volume spike
   - Pitch change
   - Cadence break
   → Instant response delivery (<200ms)

**Example Session:**
```
[You speak, Jarvis buffers context in real-time]

You: "Hey Jarvis, what's the best—"
  [Minimax predicts: "crypto", "AI stock", "productivity app"]
  [Pre-caches 3 responses]

You: "—crypto arbitrage strategy right now?"
  [Delivers pre-cached "crypto" response instantly]

Jarvis: "Based on current vol spreads, CEX-DEX arb on SOL/USDC 
         via Jupiter is yielding 0.3-0.8% per cycle..."

You: [Interrupting] "Wait, what about Base chain?"
  [Audio spike detected, pauses mid-sentence]

Jarvis: "Good catch—Base has lower gas, making arb viable at 
         0.2% spreads vs 0.3% on Solana..."
```

---

## Security & OPSEC

### Action Verification (New)

Every action now has a 3-step verification loop:

```python
# Example: Send email
actions.execute_action("send_email", to="john@example.com", subject="Meeting")
    ↓
action_verifier.verify(action="send_email", expected_outcome="email in sent folder")
    ↓
action_verifier.learn(success=True, latency_ms=1200)
    ↓
Report: "Email sent and verified in Sent folder (1.2s)"
```

### Mirror Test Safety

- All refactor proposals run **dry-run validation** against 100 historical scenarios
- Requires 85% improvement score to auto-apply
- Manual review available: `./bin/lifeos mirror review`
- Git history preserves all changes with rollback

### Coliseum Sandboxing

- Paper-trading uses **simulated funds only**
- Live promotion requires human approval
- All strategy code executes in restricted environment (no file system access)

---

## Cost Comparison

| Task | Minimax 2.1 | GPT-4 Turbo | Claude Sonnet |
|------|-------------|-------------|---------------|
| 1M tokens voice chat | $1.50 | $15.00 | $15.00 |
| 100 trading backtests | $0.45 | $4.50 | $4.50 |
| Nightly mirror test | $0.30 | $3.00 | $3.00 |
| **Monthly (heavy use)** | **~$50** | **~$500** | **~$500** |

**Jarvis v1.0 with Minimax = 90% cost reduction vs GPT-4**

---

## Roadmap

### Completed ✓
- [x] Minimax 2.1 integration
- [x] Intelligent provider routing
- [x] Mirror Test self-correction
- [x] Paper-Trading Coliseum
- [x] Streaming consciousness voice
- [x] Action verification loops

### In Progress 🚧
- [ ] Multi-day mirror test trends
- [ ] Strategy mutation optimization engine
- [ ] Cross-session memory semantic search

### Planned 🎯
- [ ] iOS companion app with streaming sync
- [ ] Multi-agent swarm orchestration
- [ ] Autonomous trading (post 1000-backtest validation)

---

## License

MIT - Use freely, modify freely. Built by [Matt Aurora Ventures](https://github.com/Matt-Aurora-Ventures).

<p align="center">
  <i>"The best AI is one that makes itself better."</i>
</p>
