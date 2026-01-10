# JARVIS

**Your Autonomous AI Trading Partner & Life Automation System**

<p align="center">
  <b>An AI that makes money while you sleep.</b><br>
  <i>Starting with crypto traders. Expanding to everyone.</i>
</p>

[![Status](https://img.shields.io/badge/Status-ONLINE-success)](https://github.com/Matt-Aurora-Ventures/Jarvis)
[![Version](https://img.shields.io/badge/Version-3.6.0-blue)](CHANGELOG.md)
[![Tests](https://img.shields.io/badge/Tests-1108%2B%20Passing-brightgreen)]()
[![Platform](https://img.shields.io/badge/Platform-macOS%20%7C%20Windows%20%7C%20Linux-lightgrey)]()
[![Solana](https://img.shields.io/badge/Solana-Mainnet-purple)](https://solana.com)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

---

## Table of Contents

- [Vision](#-vision)
- [Features](#-features)
- [Quick Start](#-quick-start)
- [Trading Engine](#-trading-engine)
- [Staking System](#-staking-system)
- [Credit System](#-credit-system)
- [Bags.fm Integration](#-bagsfm-integration)
- [Treasury Management](#-treasury-management)
- [Self-Improvement Engine](#-self-improvement-engine)
- [Voice Control](#-voice-control)
- [Cross-Platform Support](#-cross-platform-support)
- [Dashboard](#-dashboard)
- [Telegram Bot](#-telegram-bot)
- [API Reference](#-api-reference)
- [Configuration](#%EF%B8%8F-configuration)
- [Deployment](#-deployment)
- [Roadmap](#%EF%B8%8F-roadmap)
- [Contributing](#-contributing)
- [Security](#-security)

---

## 🎯 Vision

JARVIS is not just another chatbot. It's an **autonomous AI system** that:

### Phase 1: Autonomous Crypto Trader (Current)
> *"An edge for the little guy"* - Democratizing institutional-grade trading tools.

- **Makes Money Autonomously**: 81+ trading strategies running 24/7
- **Protects Your Capital**: Sophisticated risk management and circuit breakers
- **Shares Revenue**: Earn SOL through $KR8TIV staking
- **No Crypto Knowledge Required**: Pay with credit card, JARVIS handles the rest

### Phase 2: Personal Life Automation (In Development)
- **Learns Your Patterns**: Observes your habits, preferences, and goals
- **Creates Automations**: Builds workflows based on your behavior
- **Takes Proactive Action**: Handles tasks before you ask
- **Integrates Everything**: Calendar, email, tasks, notes, and more

### Phase 3: Universal Assistant (Future)
- **Multi-Domain Intelligence**: Financial, health, productivity, social
- **Predictive Actions**: Anticipates needs before you ask
- **Complete Ecosystem**: Your entire digital life, optimized

---

## ✨ Features

### 🤖 Autonomous Trading
| Feature | Description |
|---------|-------------|
| **81+ Strategies** | Momentum, mean reversion, arbitrage, sentiment, breakout, grid trading |
| **Multi-DEX** | Jupiter, Raydium, Orca, Meteora, Bags.fm with smart routing |
| **MEV Protection** | Jito bundle integration prevents frontrunning |
| **Real-Time Data** | BirdEye, DexScreener, GMGN, GeckoTerminal feeds |
| **Risk Controls** | Position limits, stop losses, circuit breakers, daily loss limits |

### 💰 Dual Revenue Model

**For Crypto Users (Staking)**:
- Stake $KR8TIV tokens → Earn SOL from trading fees
- Time-weighted multipliers: 1.0x → 2.5x over 90 days
- Early holder bonuses: First 1000 stakers get up to 3x multiplier

**For Everyone (Credits)**:
- Pay with credit card via Stripe
- No crypto knowledge required
- Tiered packages: Starter ($25) → Pro ($100) → Whale ($500)

### 🧠 Self-Improving AI
- **Mirror Test**: Nightly self-correction at 3am
- **Reflexion Engine**: Learns from past mistakes
- **Trust Ladder**: Builds confidence through success
- **Paper-Trading Coliseum**: Strategies battle-tested before going live

### 🎙️ Voice Control
- Wake word: "Hey JARVIS"
- Natural language understanding
- Computer control (apps, email, search)
- Offline voice synthesis with Piper TTS

### 📊 Real-Time Dashboard
- Portfolio tracking and P&L
- Live positions with TP/SL visualization
- Token scanner with rug detection
- Strategy performance metrics

---

## 🚀 Quick Start

### Prerequisites
- Python 3.11+
- Node.js 18+ (for dashboard)
- Git

### Installation

```bash
# Clone repository
git clone https://github.com/Matt-Aurora-Ventures/Jarvis.git
cd Jarvis

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure API keys
mkdir -p secrets
cat > secrets/keys.json << 'EOF'
{
  "groq_api_key": "YOUR_GROQ_KEY",
  "openrouter_api_key": "YOUR_OPENROUTER_KEY",
  "birdeye_api_key": "YOUR_BIRDEYE_KEY",
  "xai": {"api_key": "YOUR_XAI_KEY"},
  "helius": {"api_key": "YOUR_HELIUS_KEY"}
}
EOF

# Start JARVIS
./bin/lifeos on --apply

# Or use the unified CLI
lifeos start
```

### Launch Dashboard

```bash
# Terminal 1: Start API server
python api/server.py

# Terminal 2: Start frontend
cd frontend && npm install && npm run dev
# Open http://localhost:5173
```

### Core Commands

| Command | Description |
|---------|-------------|
| `lifeos on --apply` | Start JARVIS daemon |
| `lifeos off --apply` | Stop JARVIS |
| `lifeos status` | Check daemon status |
| `lifeos chat` | Voice conversation mode |
| `lifeos doctor` | System health check |
| `lifeos trading coliseum start` | Start paper-trading |

---

## 📈 Trading Engine

### Strategy Categories

JARVIS employs 81+ trading strategies across multiple categories:

| Category | Count | Examples |
|----------|-------|----------|
| Slow Trend Following | 9 | 200-Day MA, Dual MA Crossover |
| Fast Trend Following | 6 | 10/30 MA with ADX |
| Mean Reversion | 6 | RSI Bounce, Bollinger Mean Reversion |
| Breakout | 6 | Range Breakout, Volume Confirmation |
| Arbitrage | 9 | Triangular, CEX-DEX, Funding Rate |
| Market Making | 3 | Bid-Ask Spread, Inventory Management |
| ML-Powered | 10+ | Regime Detection, Sentiment Alpha |

### Advanced Trading Infrastructure

**Data Ingestion** (`core/data_ingestion.py`):
- WebSocket streaming from Binance, Kraken
- CCXT normalization across 100+ exchanges
- Tick buffer for sub-second candle aggregation

**ML Regime Detection** (`core/ml_regime_detector.py`):
- Volatility prediction with Random Forest/Gradient Boosting
- Regime classification: Low/Medium/High/Extreme
- Adaptive strategy switching based on market conditions

**MEV Execution** (`core/jito_executor.py`):
- Jito Block Engine bundle submission
- Smart Order Routing (SOR) across DEXs
- Sandwich protection for user trades

### Risk Management

```python
# Default risk parameters
RISK_CONFIG = {
    "max_position_size_pct": 5.0,      # Max 5% per position
    "max_portfolio_risk_pct": 20.0,    # Max 20% total risk
    "stop_loss_pct": 10.0,             # 10% stop loss
    "take_profit_pct": 25.0,           # 25% take profit
    "max_drawdown_pct": 15.0,          # Circuit breaker at 15%
    "max_daily_trades": 50,            # Rate limit
}
```

### Position Tracking & Analytics (NEW in v3.6.0)

**Comprehensive position history and performance statistics**:

```python
from core.position_tracker import PositionTracker

tracker = PositionTracker()

# Record trade
await tracker.record_position(
    symbol="SOL/USDC",
    entry_price=100.0,
    exit_price=110.0,
    quantity=10,
    pnl=100.0
)

# Get statistics
stats = await tracker.get_stats()
print(f"Win Rate: {stats['win_rate']:.2%}")
print(f"Total P&L: ${stats['total_pnl']:.2f}")
print(f"Best Streak: {stats['best_winning_streak']}")
```

**API Endpoints**:
```bash
GET /api/position/stats        # Aggregate statistics
GET /api/position/history      # Full trade history
GET /api/position/by-symbol    # Performance by token
```

**Frontend Component** (`frontend/src/components/trading/PositionStats.jsx`):
- Win rate visualization
- P&L charts
- Streak tracking
- Performance by symbol

### LUT Micro-Alpha Module

High-risk trending token trading for the **$20 → $1,000,000 Challenge**:

**Exit Intent System**:
| Type | Trigger | Default |
|------|---------|---------|
| TP1 | +8% | 60% position |
| TP2 | +18% | 25% position |
| TP3 | +40% | 15% runner |
| Stop Loss | -9% | 100% position |
| Time Stop | 90 minutes | If TP1 not hit |
| Trailing | 5% from high | After TP1 |

**Phase-Based Scaling**:
| Phase | Max Trade | Max Exposure | Promotion Criteria |
|-------|-----------|--------------|-------------------|
| Trial | 2% NAV | 10% NAV | Net PnL > 0, PF ≥ 1.25 |
| Validated | 2.5% NAV | 15% NAV | 25 trades, Max DD ≤ 10% |
| Scaled | 3% NAV | 20% NAV | Full autonomy earned |

### Jupiter Perps (SAVAGE MODE)

High-conviction leveraged perpetuals:

| Phase | Max Leverage | Min Conviction | Stop Loss |
|-------|--------------|----------------|-----------|
| Trial | 5x | - | 3.0% |
| Validated | 15x | - | 2.0% |
| **SAVAGE** | **30x** | **0.9** | **1.2%** |

---

## 🏦 Staking System

### $KR8TIV Token

The native utility token powering the JARVIS ecosystem:

**Time-Weighted Multipliers**:
| Duration | Multiplier | Tier |
|----------|------------|------|
| 0-6 days | 1.0x | Bronze |
| 7-29 days | 1.5x | Silver |
| 30-89 days | 2.0x | Gold |
| 90+ days | 2.5x | Diamond |

**Staking Contract** (`contracts/staking/`):
- Anchor-based Solana program
- Weekly SOL distributions from trading fees
- 3-day cooldown for unstaking
- Auto-compound option

### Early Holder Rewards

First 1000 stakers receive bonus multipliers:

| Tier | Position | Multiplier | Pool Share |
|------|----------|------------|------------|
| Diamond | 1-100 | 3.0x | 50% |
| Gold | 101-500 | 2.0x | 35% |
| Silver | 501-1000 | 1.5x | 15% |

### Frontend Components

```jsx
// Staking Dashboard
<StakingDashboard wallet={connectedWallet}>
  <StakeCard title="Your Stake" value={stakeAmount} />
  <StakeCard title="Pending Rewards" value={pendingRewards} />
  <MultiplierBadge multiplier={2.0} tier="Gold" />
  <CooldownTimer endTime={cooldownEnd} />
  <ActionButton onClick={claimRewards}>Claim SOL</ActionButton>
</StakingDashboard>
```

### Staking API

```bash
# Get stake info
GET /api/staking/stake/{wallet}

# Stake tokens
POST /api/staking/stake
{"wallet": "...", "amount": 1000000000}

# Request unstake (3-day cooldown)
POST /api/staking/request-unstake
{"wallet": "..."}

# Claim rewards
POST /api/staking/claim
{"wallet": "..."}

# Early holder status
GET /api/staking/early-rewards/holder/{wallet}
```

---

## 💳 Credit System

### Pay-as-You-Go API Access

No crypto required! Purchase credits with your credit card:

**Packages**:
| Package | Credits | Bonus | Price | Per Credit |
|---------|---------|-------|-------|------------|
| Starter | 100 | 0 | $25 | $0.25 |
| Pro | 500 | 50 | $100 | $0.18 |
| Whale | 3,000 | 500 | $500 | $0.14 |

**API Credit Costs**:
| Endpoint | Credits |
|----------|---------|
| `/api/trade/quote` | 1 |
| `/api/trade/execute` | 5 |
| `/api/analyze` | 10 |
| `/api/backtest` | 50 |

**Rate Limits by Tier**:
| Tier | Requests/Min |
|------|-------------|
| Free | 10 |
| Starter | 50 |
| Pro | 100 |
| Whale | 500 |

### Stripe Integration

```python
from core.credits import create_checkout_session

# Create Stripe checkout
session = await create_checkout_session(
    user_id="user_123",
    package_id="pro",
    success_url="https://app.jarvis.ai/credits?success=true"
)
# Redirect to session.checkout_url
```

### Rate Limiting

Redis-based sliding window rate limiting (`core/payments/rate_limiter.py`):

```python
from core.payments.rate_limiter import check_rate_limit

allowed, info = await check_rate_limit(user_id, tier="pro")
if not allowed:
    raise RateLimitExceeded(retry_after=info["retry_after"])
```

---

## 🤝 Bags.fm Integration

JARVIS is an official Bags.fm partner, earning **25% of trading fees** (0.25% of volume):

### Trade Router

```python
from integrations.bags import BagsTradeRouter

router = BagsTradeRouter(partner_id="jarvis")

# Execute trade through Bags.fm (falls back to Jupiter if unavailable)
result = await router.swap(
    wallet=wallet,
    token_in=SOL_MINT,
    token_out=BONK_MINT,
    amount=1_000_000_000,  # 1 SOL
    slippage_bps=100,
)
print(f"Partner fee earned: {result.partner_fee_lamports}")
```

### Fee Collection

```python
from integrations.bags import FeeCollector

collector = FeeCollector()

# Collect partner fees (runs hourly)
fees = await collector.collect_and_distribute()
# Distributes to: 60% staking pool, 25% operations, 15% development
```

### Benefits
- 25% of platform fee on every swap
- Automatic fallback to Jupiter
- Real-time fee tracking dashboard
- Weekly distribution to stakers

---

## 🏛️ Treasury Management

### Multi-Wallet Architecture

| Wallet | Allocation | Purpose |
|--------|------------|---------|
| Reserve | 60% | Emergency fund, never traded |
| Active | 30% | Trading capital |
| Profit | 10% | Buffer for distributions |

### Risk Controls

```python
# core/treasury/risk.py
RISK_CONTROLS = {
    "circuit_breaker": 3,           # Consecutive losses to halt
    "max_position_pct": 5.0,        # Max per trade
    "daily_loss_limit_pct": 5.0,    # Max daily loss
    "recovery_cooldown_hours": 24,  # Cooldown after trigger
}
```

### Weekly Profit Distribution

| Recipient | Share |
|-----------|-------|
| Staking Rewards Pool | 60% |
| Operations Wallet | 25% |
| Development Fund | 15% |

### Transparency Dashboard

```bash
GET /api/treasury/status
GET /api/treasury/balances
GET /api/treasury/distributions
GET /api/treasury/metrics
```

---

## 🧠 Self-Improvement Engine

### The Mirror Test

Every night at 3am, JARVIS:
1. **Replays** the last 24 hours using Minimax 2.1
2. **Scores** its own performance (latency, accuracy, satisfaction)
3. **Proposes** code refactors and prompt improvements
4. **Validates** changes against 100 historical scenarios
5. **Auto-applies** if improvement score > 85%

### Trust Ladder

JARVIS earns autonomy through successful actions:

| Level | Name | Permissions |
|-------|------|-------------|
| 0 | STRANGER | Only respond when asked |
| 1 | ACQUAINTANCE | Can suggest, needs approval |
| 2 | COLLEAGUE | Can draft content for review |
| 3 | PARTNER | Can act autonomously, reports after |
| 4 | OPERATOR | Full autonomy in domain |

### Reflexion Engine

Learning from past mistakes:

```python
from core.self_improving.reflexion import ReflexionEngine

reflexion = ReflexionEngine()

# Analyze past action
analysis = await reflexion.analyze(
    action="Bought BONK at $0.00001",
    outcome="Price dropped 50% in 1 hour",
    expected="Price increase based on momentum",
)

# Extract and apply lessons
lessons = analysis.lessons
await reflexion.apply_lessons(lessons)
```

### Hyperparameter Optimization (NEW in v3.6.0)

**Automated strategy optimization using Optuna**:

```python
from core.hyperparameter_tuning import optimize_strategy

# Optimize SMA crossover strategy
best_params = optimize_strategy(
    strategy_type="sma_cross",
    data=historical_data,
    n_trials=100,
    objectives=["sharpe_ratio", "profit_factor"]
)

print(f"Best fast period: {best_params['fast_period']}")
print(f"Best slow period: {best_params['slow_period']}")
print(f"Expected Sharpe: {best_params['sharpe_ratio']:.2f}")
```

**Supported Strategies**:
- SMA Crossover
- RSI Mean Reversion
- Bollinger Bands
- MACD
- Custom strategies (extensible)

**Optimization Objectives**:
- Sharpe Ratio
- Profit Factor
- ROI
- Max Drawdown
- Win Rate

**Features**:
- Multi-objective optimization
- Parallel trial execution
- Pruning of unpromising trials
- Visualization of optimization history
- Automatic parameter validation

### Enhanced Paper Trading (v3.6.0)

**Realistic simulation with fee/slippage modeling**:

```python
from core.paper_trading import PaperWallet

wallet = PaperWallet(initial_balance=10000.0)

# Configure realistic fees
wallet.set_fees(
    trading_fee_bps=30,      # 0.30% trading fee
    slippage_bps=10          # 0.10% slippage
)

# Execute paper trade
result = await wallet.buy(
    symbol="SOL/USDC",
    amount=1000.0,
    price=100.0
)

# View history
history = wallet.get_trade_history()
analytics = wallet.get_analytics()
```

**Features**:
- Realistic balance simulation
- Configurable fees and slippage
- Trade history logging
- Performance analytics
- Win rate, P&L, streaks

**Telegram Commands** (NEW):
```bash
/paper wallet    # View paper wallet balance
/paper buy       # Execute paper buy
/paper sell      # Execute paper sell
/paper history   # View trade history
/paper reset     # Reset paper wallet
```

### Paper-Trading Coliseum

All strategies are battle-tested before going live:

```
Each strategy → 10 random 30-day backtests
    ↓
Metrics: Sharpe, Drawdown, Win Rate, Profit Factor
    ↓
Auto-Prune: 5 failures → Deletion + Autopsy
    ↓
Auto-Promote: Sharpe >1.5 → live_candidates/
```

**Commands**:
```bash
lifeos trading coliseum start      # Start paper-trading
lifeos trading coliseum results    # View results
lifeos trading coliseum cemetery   # View deleted strategies
```

---

## 🎤 Voice Control

### Wake Word Detection (NEW in v3.6.0)

**Cross-platform "Hey JARVIS" wake word detection** - works on Windows, macOS, and Linux without model training!

```bash
# Start voice mode with wake word
./bin/lifeos chat --streaming

# Windows desktop launcher
Jarvis-Voice.bat

# With Minimax 2.1 streaming consciousness
./bin/lifeos chat --streaming --minimax
```

**Implementation** (`core/wake_word.py`):
- Lightweight keyword spotting
- No cloud dependencies
- Low CPU usage (~2-5%)
- Instant activation

### Features

| Feature | Description |
|---------|-------------|
| Wake Word | "Hey JARVIS" activates listening (cross-platform) |
| Barge-In | Interrupt mid-response naturally |
| Pre-Caching | Predicts your next 3 likely intents |
| Ring Buffer | Last 30 seconds always in context |
| Offline TTS | Piper synthesis works without internet |
| Desktop Launcher | One-click voice activation on Windows |

### Voice Commands

| Command | Action |
|---------|--------|
| "Buy some SOL" | Execute SOL purchase |
| "What's my portfolio worth?" | Report value |
| "How's BONK doing?" | Analyze token |
| "Set stop loss at 10%" | Configure risk |
| "Start autonomous trading" | Enable auto-trading |

### Voice Clone (Optional)

Coqui XTTS voice cloning with Python 3.11:

```bash
# Create dedicated venv
python3.11 -m venv venv311
source venv311/bin/activate
pip install TTS
```

---

## 🌐 Cross-Platform Support

JARVIS runs on macOS, Windows, and Linux:

### Platform Operations

| Operation | macOS | Windows | Linux |
|-----------|-------|---------|-------|
| Notifications | osascript | ToastNotifier | notify-send |
| Clipboard | pbcopy/paste | win32clipboard | xclip |
| TTS | say | pyttsx3 | espeak |
| Screenshots | screencapture | pyautogui | scrot |
| App Launch | open -a | start | xdg-open |

### Usage

```python
from core.platform import send_notification, get_clipboard, speak_text

# Works on any platform
send_notification("JARVIS", "Trade executed!")
text = get_clipboard()
speak_text("Hello from JARVIS")
```

---

## 🎨 Dashboard

### Real-Time WebSocket Price Streaming (NEW in v3.6.0)

**True real-time price updates** via WebSocket server on port 8766:

```javascript
// Frontend usage
import { useWebSocketPrice } from '@/hooks/useWebSocketPrice';

function TokenPrice({ mint }) {
  const price = useWebSocketPrice(mint);
  return <span>${price?.toFixed(6)}</span>;
}
```

**Server** (`core/websocket_server.py`):
- Multi-client support
- Per-token subscriptions
- Automatic reconnection
- Sub-second latency

**Start WebSocket Server**:
```bash
python core/websocket_server.py
# Listens on ws://localhost:8766
```

### Trading Dashboard V2

Premium trading command center at `http://localhost:5173/trading`:

**Features**:
- 📊 Live Position Card with P&L
- 🛠️ Token Scanner with rug detection
- 💬 Floating JARVIS Chat
- 📈 TradingView-style charts
- 🔄 Real-time WebSocket price updates
- 📈 Position tracking with statistics

### Routes

| Route | Page | Description |
|-------|------|-------------|
| `/` | Dashboard | Portfolio overview |
| `/chat` | Chat | JARVIS AI assistant |
| `/trading` | Trading | Charts, positions, scanner |
| `/voice` | Voice | Voice command interface |
| `/roadmap` | Roadmap | Interactive progress tracker |
| `/settings` | Settings | API keys, preferences |

### Tech Stack

- React 18 + Vite 5 + TailwindCSS
- Zustand for state management
- lightweight-charts for TradingView charts
- Modular CSS architecture

---

## 📱 Telegram Bot

**JARVIS Telegram Bot** delivers AI-powered trading signals with interactive controls:

### Quick Start

```bash
cd tg_bot
pip install -r requirements.txt

# Create .env
cat > .env << 'EOF'
TELEGRAM_BOT_TOKEN=your-bot-token
XAI_API_KEY=your-grok-key
TELEGRAM_ADMIN_IDS=your-telegram-id
BIRDEYE_API_KEY=your-birdeye-key
EOF

python bot.py
```

### Interactive Inline Keyboards (NEW in v3.6.0)

**Button-based navigation** replaces text commands for better UX:

- **Main Menu**: Quick access to all features
- **Paper Trading**: Interactive wallet management
- **Admin Panel**: Role-specific controls
- **Token Analysis**: One-tap token lookup

### Commands

| Command | Description | Access |
|---------|-------------|--------|
| `/start` | Welcome + interactive menu | Public |
| `/status` | Check API status | Public |
| `/trending` | Top 5 trending tokens | Public |
| `/signals` | Master Signal Report (Top 10) | Admin |
| `/analyze <token>` | Full analysis with Grok | Admin |
| `/digest` | Comprehensive digest | Admin |
| `/paper wallet` | View paper wallet balance | Public |
| `/paper buy` | Execute paper buy | Public |
| `/paper sell` | Execute paper sell | Public |
| `/paper history` | View trade history | Public |
| `/paper reset` | Reset paper wallet | Admin |

### Master Signal Report

Returns top 10 trending Solana tokens with:
- Clickable contract addresses
- Entry recommendations (scalp/day/long)
- Leverage suggestions (1x-5x)
- Grok AI sentiment analysis
- Risk scores (-100 to +100)
- Direct links (DexScreener, Birdeye, Solscan)

---

## 📡 API Reference

### Authentication

```bash
curl -H "Authorization: Bearer YOUR_API_KEY" \
  https://api.jarvis.ai/v1/portfolio
```

### Core Endpoints

#### Portfolio
```bash
GET /api/portfolio
# Returns: total_value_usd, sol_balance, positions[]
```

#### Trading
```bash
POST /api/trade/quote
{"token_in": "SOL", "token_out": "BONK", "amount": 1.0}

POST /api/trade/execute
{"quote_id": "...", "slippage_bps": 100}
```

#### Analysis
```bash
POST /api/analyze
{"token_address": "...", "analysis_type": "comprehensive"}
```

#### Staking
```bash
GET /api/staking/stake/{wallet}
POST /api/staking/stake
POST /api/staking/claim
GET /api/staking/early-rewards/status
```

#### Credits
```bash
GET /api/credits/balance
GET /api/credits/packages
POST /api/credits/checkout
GET /api/credits/transactions
```

#### Treasury
```bash
GET /api/treasury/status
GET /api/treasury/balances
GET /api/treasury/distributions
```

---

## ⚙️ Configuration

### Main Config: `lifeos/config/lifeos.config.json`

```json
{
  "voice": {
    "wake_word": "jarvis",
    "tts_engine": "piper",
    "speak_responses": true
  },
  "providers": {
    "groq": {"enabled": true, "priority": 1},
    "ollama": {"enabled": true, "priority": 4}
  },
  "trading": {
    "dex_only": true,
    "preferred_chains": ["Solana"],
    "risk_per_trade": 0.02,
    "stop_loss_pct": 0.03
  }
}
```

### Minimax 2.1: `lifeos/config/minimax.config.json`

```json
{
  "minimax": {
    "model": "minimax/minimax-01",
    "via": "openrouter",
    "streaming": true
  },
  "mirror_test": {
    "enabled": true,
    "schedule": "0 3 * * *",
    "auto_apply": true
  }
}
```

### Required API Keys

```json
// secrets/keys.json
{
  "groq_api_key": "...",
  "openrouter_api_key": "...",
  "birdeye_api_key": "...",
  "xai": {"api_key": "..."},
  "helius": {"api_key": "..."},
  "stripe_secret_key": "...",
  "bags_partner_key": "..."
}
```

---

## 🚢 Deployment

### Docker

```bash
docker build -t jarvis .
docker run -d --name jarvis -p 8000:8000 \
  -e DATABASE_URL=postgresql://... \
  -e REDIS_URL=redis://... \
  jarvis
```

### Docker Compose

```yaml
version: '3.8'
services:
  jarvis:
    build: .
    ports: ["8000:8000"]
    depends_on: [db, redis]
  db:
    image: postgres:14
  redis:
    image: redis:7-alpine
```

### Monitoring Stack

```bash
cd monitoring
docker-compose -f docker-compose.monitoring.yml up -d

# Access:
# Prometheus: http://localhost:9090
# Grafana: http://localhost:3000
# Alertmanager: http://localhost:9093
```

### Production Checklist

- [ ] Production RPC (Helius, Triton)
- [ ] PostgreSQL with replication
- [ ] Redis cluster for HA
- [ ] SSL/TLS on all endpoints
- [ ] WAF and DDoS protection
- [ ] Monitoring and alerting
- [ ] Log aggregation (Loki)
- [ ] Backup automation

---

## 🗺️ Roadmap

### Completed ✓

- [x] Core trading engine with 81+ strategies
- [x] Jupiter, Raydium, Orca DEX integration
- [x] BirdEye, DexScreener, GMGN data feeds
- [x] Bags.fm partner integration (25% fee share)
- [x] Anchor staking smart contract
- [x] Time-weighted multipliers (1.0x-2.5x)
- [x] Early holder rewards program
- [x] Credit system with Stripe
- [x] Rate limiting with Redis
- [x] PostgreSQL schema with idempotent transactions
- [x] Frontend staking dashboard
- [x] Credit purchase UI
- [x] Prometheus/Grafana monitoring
- [x] Load testing infrastructure (k6)
- [x] Cross-platform support (macOS/Windows/Linux)
- [x] Voice control with wake word
- [x] Mirror Test self-correction
- [x] Paper-Trading Coliseum
- [x] Trust Ladder (5 levels)
- [x] Reflexion Engine
- [x] Wallet infrastructure (ALTs, dual-fee, simulation)
- [x] **Cross-platform wake word detection** (v3.6.0)
- [x] **WebSocket real-time price streaming** (v3.6.0)
- [x] **Position tracking & analytics** (v3.6.0)
- [x] **Enhanced paper trading with fees/slippage** (v3.6.0)
- [x] **Hyperparameter optimization with Optuna** (v3.6.0)
- [x] **Telegram inline keyboard navigation** (v3.6.0)
- [x] **Paper trading via Telegram** (v3.6.0)
- [x] 1108+ tests passing

### In Progress 🚧

- [ ] Walk-forward validation
- [ ] Cross-chain MEV (Flashbots for Ethereum)
- [ ] ML model retraining pipeline
- [ ] Advanced sentiment analysis pipeline

### Q1 2026

| Task | Priority |
|------|----------|
| Strategy optimization loop | P0 |
| Multi-exchange arbitrage | P0 |
| Order book depth (L2/L3) | P0 |
| Execution quality metrics | P1 |
| Live paper trading (30 days) | P1 |

### Q2 2026

| Task | Priority |
|------|----------|
| Sentiment trading pipeline | P0 |
| News event detection (NLP) | P1 |
| Regime ensemble models | P1 |
| Mobile app (iOS/Android) | P1 |
| Push notifications | P2 |

### Q3-Q4 2026

| Task | Priority |
|------|----------|
| Life automation features | P0 |
| Calendar integration | P0 |
| Email automation | P1 |
| Multi-agent swarm | P1 |
| Strategy marketplace | P2 |
| Multi-chain (Base, Arbitrum) | P2 |

### 2027+

- [ ] Fully autonomous 24/7 trading
- [ ] Self-funding (profits cover costs)
- [ ] White-label solution
- [ ] Multi-domain life optimization
- [ ] Complete ecosystem integration

---

## 🤝 Contributing

PRs welcome! Please:

1. Read safety guidelines in `core/guardian.py`
2. Run tests: `pytest tests/ -v`
3. Never commit secrets or personal data
4. Follow existing code style

### Development Setup

```bash
git clone https://github.com/Matt-Aurora-Ventures/Jarvis.git
cd Jarvis
python -m venv venv && source venv/bin/activate
pip install -r requirements-dev.txt

# Run tests
pytest tests/ -v --cov=core

# Linting
ruff check core/ --fix
mypy core/ --ignore-missing-imports
```

---

## 🔐 Security

### Reporting Vulnerabilities

Report security issues to security@jarvis.ai. Do not open public issues.

### Safety Features

- **Wallet Isolation**: Private keys never leave secure enclave
- **Rate Limiting**: Protection against abuse
- **Input Validation**: All inputs sanitized
- **MEV Protection**: Jito bundles prevent frontrunning
- **Audit Trail**: Complete transaction logging
- **Guardian System**: Blocks dangerous operations

### Protected Paths

```
secrets/           # API keys
*.pem, *.key       # Certificates
.env               # Environment files
*.db               # Databases
```

### GDPR Compliance

3-tier data consent system:

| Tier | Data Collected | Benefit |
|------|----------------|---------|
| TIER_0 | None | Full privacy |
| TIER_1 | Anonymous usage | Helps improve platform |
| TIER_2 | Trading patterns | Earn from data marketplace |

---

## 📄 License

MIT License - Use freely, modify freely. See [LICENSE](LICENSE) for details.

---

<p align="center">
  <b>Built by <a href="https://github.com/Matt-Aurora-Ventures">Matt Aurora Ventures</a></b><br>
  <i>"The best AI is one that makes you money while you sleep."</i>
</p>
