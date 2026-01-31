# JARVIS - Claude Code Context

## Project Overview
Jarvis is an autonomous LifeOS trading and AI assistant system running on Solana.

## Key Directories
- `core/` - Main Python modules (trading, bots, execution, risk management)
- `bots/` - Bot implementations (Telegram, Twitter/X, Treasury, Buy Tracker)
- `tg_bot/` - Telegram bot handlers and services
- `api/` - API server and handlers
- `web/` - Web interfaces (trading UI, system control deck)
- `lifeos/config/` - Configuration files
- `scripts/` - Automation and utility scripts
- `~/.lifeos/trading/` - Runtime state files

## Current State Access
- Position state: `bots/treasury/.positions.json`
- Exit intents: `~/.lifeos/trading/exit_intents.json`
- Grok state: `bots/twitter/.grok_state.json`
- Execution logs: Check supervisor output

## Critical Files
- `bots/supervisor.py` - Main supervisor that orchestrates all components
- `bots/treasury/trading.py` - Treasury trading engine (Jupiter DEX)
- `bots/twitter/x_claude_cli_handler.py` - X/Twitter CLI command handler
- `bots/twitter/autonomous_engine.py` - Autonomous posting engine
- `bots/buy_tracker/sentiment_report.py` - Sentiment analysis and reporting
- `tg_bot/services/chat_responder.py` - Telegram chat handler
- `core/context_loader.py` - Shared Jarvis context/capabilities

## Active Configurations
- Max positions: 50 (treasury/trading.py, position_manager.py)
- Grok daily cost limit: $10 (tg_bot/config.py)
- X Bot circuit breaker: 60s min interval, 30min cooldown after 3 errors

## How to Execute Actions
```python
# Example: Post to X
from bots.twitter.twitter_client import TwitterClient
client = TwitterClient()
await client.post_tweet("Message here")

# Example: Check positions
from bots.treasury.trading import TreasuryTrader
trader = TreasuryTrader()
positions = trader.get_open_positions()

# Example: Get Jarvis capabilities
from core.context_loader import JarvisContext
caps = JarvisContext.get_capabilities()
```

## Environment Variables
- `X_BOT_ENABLED` - Kill switch for X posting (true/false)
- `LIFEOS_KILL_SWITCH` - Emergency trade halt
- `TREASURY_LIVE_MODE` - Enable live trading (vs dry run)
- `TELEGRAM_BOT_TOKEN` - Telegram API token
- `JARVIS_ACCESS_TOKEN` - Twitter OAuth for @Jarvis_lifeos

## Running the System
```bash
# Start all bots via supervisor
python bots/supervisor.py

# Components managed:
# - buy_bot: KR8TIV token tracking
# - sentiment_reporter: Hourly market reports
# - twitter_poster: Grok sentiment tweets
# - telegram_bot: Telegram interface
# - autonomous_x: Autonomous X posting
# - bags_intel: Bags.fm graduation monitoring & intel reports
```

## Web Interfaces

### Trading Interface (Port 5001)
**Location**: `web/trading_web.py`
**URL**: http://127.0.0.1:5001

Web-based trading UI that mirrors the Telegram `/demo` interface:

**Features**:
- Portfolio overview (SOL balance, USD value, P&L)
- Buy tokens with mandatory TP/SL
- View all open positions with real-time P&L
- Sell positions (25%, 50%, 100%)
- AI sentiment analysis for tokens
- Market regime indicators
- Auto-refresh every 30 seconds

**To Run**:
```bash
cd web
python trading_web.py
```

### System Control Deck (Port 5000)
**Location**: `web/task_web.py`
**URL**: http://127.0.0.1:5000

System-wide operations and monitoring:
- System health (CPU, RAM, disk, network)
- Mission control (research, backtesting, diagnostics)
- Task management
- Config toggles
- Security logs
- Action approval gates

**To Run**:
```bash
cd web
python task_web.py
```

## Key Features
1. **Autonomous Trading**: Jupiter DEX integration for Solana tokens
2. **Sentiment Analysis**: Grok AI for token scoring
3. **X/Twitter Bot**: @Jarvis_lifeos posts market updates
4. **Telegram Integration**: Full admin interface via @Jarviskr8tivbot
5. **Web Interfaces**: Trading UI and system control deck
6. **CLI Commands**: Admin can execute code via X mentions

## Bags Intel (bags.fm Intelligence Reports)

Real-time monitoring of bags.fm token graduations with automated investment analysis.

**Location**: `bots/bags_intel/`

**New Environment Variable Required**:
- `BITQUERY_API_KEY` - Get from https://bitquery.io (for real-time WebSocket monitoring)

**Reuses Existing Keys**:
- `TELEGRAM_BOT_TOKEN` / `TELEGRAM_BUY_BOT_CHAT_ID` - For sending reports
- `XAI_API_KEY` - For Grok AI analysis
- `TWITTER_BEARER_TOKEN` - For social scanning (optional)
- `HELIUS_API_KEY` - For holder data (optional)

**Scoring Dimensions** (weighted 0-100):
- Bonding Curve (25%): Duration, volume, buyer count, buy/sell ratio
- Creator (20%): Twitter presence, account age, history
- Social (15%): Linked socials, website
- Market (25%): Liquidity, price stability
- Distribution (15%): Holder count, concentration

**Quality Tiers**:
- Exceptional (80+), Strong (65-79), Average (50-64), Weak (35-49), Poor (<35)

## Recent Fixes (2026-01-15)
1. X bot circuit breaker to prevent spam loops
2. Max positions increased to 50
3. Telegram bot context enhanced with capabilities
4. Grok daily cost limit increased to $10

## Recent Additions (2026-01-21)
1. Bags Intel service for bags.fm graduation monitoring
2. Intel reports sent to Telegram with scoring breakdown

## Master Task Tracking

**PRIMARY REFERENCE:** [docs/ULTIMATE_MASTER_GSD_JAN_31_2026.md](docs/ULTIMATE_MASTER_GSD_JAN_31_2026.md)

This document is the PERMANENT MASTER REFERENCE for all pending work:
- 120+ tasks consolidated from 9 source documents
- Eliminates duplicates, categorizes by priority
- Execution phases (Critical → Security → Infrastructure → Quality)
- Testing & verification matrix
- Survives context compaction
- ALWAYS read this document to understand pending tasks

**Quick Stats:**
- 20 tasks completed ✅
- 85 tasks pending ⏳
- 3 tasks blocked 🔒
- 11 tasks backlog 📋

**Priority Tasks:**
1. GitHub Dependabot: 49 security vulnerabilities (1 critical, 15 high, 25 moderate, 8 low)
2. Code-level security: 88+ SQL injection, pickle, eval fixes remaining
3. Bot stability: Telegram polling lock, ai_supervisor not running
4. GitHub PRs: 7 pull requests awaiting review

**Ralph Wiggum Loop Protocol:** ACTIVE - Continuous execution until told to stop

