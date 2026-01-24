# Jarvis Architecture

Generated: 2026-01-24

## Overview

Jarvis is a multi-bot autonomous trading and AI assistant system built on a supervisor-managed microservices architecture.

## Core Pattern: Supervisor-Managed Bot Constellation

- Central supervisor orchestrates independent bot processes
- Each bot runs in isolation with auto-restart
- Shared state coordination via JSON files
- Event-driven communication between components

## System Layers

### Layer 1: Infrastructure and Orchestration

Entry Point: bots/supervisor.py

The supervisor manages 10+ independent bot components with auto-restart, health monitoring, and graceful shutdown.

Key Files:
- bots/supervisor.py - Main supervisor
- core/shutdown_manager.py - Coordinated shutdown
- core/async_utils.py - Task tracking utilities
- core/context_engine.py - Startup tracking
- core/durability/run_ledger.py - Crash recovery

### Layer 2: Bot Layer (Autonomous Services)

#### Trading Bots

Treasury Bot (bots/treasury/)
- Entry: bots/treasury/run_treasury.py
- Engine: bots/treasury/trading.py
- Integration: Jupiter DEX for Solana swaps
- Risk: Position limits (max 50), scorekeeper
- State: .positions.json, exit_intents.json

Buy Tracker Bot (bots/buy_tracker/)
- Entry: bots/buy_tracker/bot.py
- Purpose: Track KR8TIV token buys
- Anti-scam monitoring

Public Trading Bot
- Entry: bots/public_trading_bot_supervisor.py
- Purpose: Mass-market trading
- Features: Paper trading, confirmations

#### Social Media Bots

Twitter/X Autonomous Engine (bots/twitter/autonomous_engine.py)
- Autonomous posting to @Jarvis_lifeos
- Hourly updates on finance/crypto/tokens
- Grok-generated content with images
- Admin code execution via X mentions
- State: .grok_state.json, jarvis_x_memory.db

Telegram Bot (tg_bot/bot.py)
- Main polling loop
- Handlers: tg_bot/handlers/
- Commands: /sentiment, /trending, /analyze
- Admin: /vibe for Claude coding

#### Intelligence Bots

Bags Intel (bots/bags_intel/)
- Monitor bags.fm token graduations
- Real-time scoring
- Automated reports to Telegram

Sentiment Reporter (bots/buy_tracker/sentiment_report.py)
- Hourly market sentiment reports
- Grok AI token scoring

### Layer 3: Core Services Layer

Trading Services (core/trading/)
- decision_matrix.py - Multi-signal decisions
- signals/liquidation.py - CoinGlass signals
- signals/dual_ma.py - Technical strategy
- cooldown.py - Trade cooldown
- emergency_stop.py - Emergency halt

AI Services (core/)
- dexter/agent.py - ReAct agent (Grok-3)
- llm/anthropic_utils.py - Claude integration
- self_correcting.py - Shared learning
- ai_runtime/ - Ollama-backed runtime

Market Data (integrations/)
- birdeye/ - Token data
- dexscreener/ - Trending tokens
- coinglass/ - Liquidations
- helius/ - Solana blockchain

State Management (core/)
- safe_state.py - Race-free state files
- context_loader.py - Shared capabilities
- state_paths.py - Centralized paths
- memory/dedup_store.py - Dedup memory

### Layer 4: API and External Interface

FastAPI Server (api/fastapi_app.py)
- Staking endpoints
- Credits/billing
- WebSocket updates
- Versioning support

Middleware (api/middleware/)
- Rate limiting, CORS
- Request tracing, logging
- Security headers

### Layer 5: Data and Storage

SQLite: Local state
PostgreSQL: Optional archival memory
JSON Files: Position state, config

State Files (~/.lifeos/trading/):
- exit_intents.json
- lut_module_state.json
- perps_state.json
- .positions.json

## Data Flow

### Trade Execution Flow

1. Market Data Ingestion
   - Birdeye, DexScreener, CoinGlass, Helius

2. Signal Generation
   - LiquidationAnalyzer
   - DualMAAnalyzer
   - Grok Sentiment

3. Decision Making
   - DecisionMatrix aggregates signals
   - MetaLabeler assesses quality
   - Dexter Agent reasoning loop

4. Risk Management
   - Position limits (max 50)
   - Cooldown enforcement
   - Emergency stop check

5. Trade Execution
   - Jupiter DEX swap
   - SecureWallet signing
   - Scorekeeper tracking

6. State Persistence
   - SafeState writes positions
   - AuditTrail logs events

### Social Media Posting Flow

1. Content Generation
   - Grok AI market analysis
   - Claude creative content
   - MemoryStore context

2. Validation
   - Deduplication check
   - Circuit breaker (60s min)
   - Rate limit check

3. Posting
   - TwitterClient posts
   - TelegramSync mirrors

4. Memory Update
   - MemoryStore records
   - State file update

## Key Abstractions

### Bot Component Interface

All bots implement:
async def start() -> None

Registered via:
supervisor.register(name, start_func, min_backoff, max_backoff)

### State Management

SafeState (atomic operations):
state = SafeState(path)
state.update(data)

StatePathsManager:
from core.state_paths import STATE_PATHS
path = STATE_PATHS.exit_intents

### Memory and Learning

MemoryStore (deduplication):
store.add(MemoryEntry(...))
is_dup = store.is_duplicate(text)

Self-Correcting System:
memory = get_shared_memory()
memory.record_learning(...)

### Trading Decision

DecisionMatrix (multi-signal):
matrix.add_signal(signal)
decision = matrix.decide()

Dexter Agent (ReAct):
agent = DexterAgent()
decision = await agent.decide(symbol)

## Entry Points

Production:
- python bots/supervisor.py (all bots)
- python tg_bot/bot.py (standalone Telegram)
- python bots/treasury/run_treasury.py (standalone Treasury)
- uvicorn api.fastapi_app:app (API server)

CLI Tools:
- python jarvis_daemon.py (systemd)
- python health_check_bot.py
- scripts/ (various utilities)

## Technology Stack

Languages: Python 3.10+, TypeScript
Frameworks: FastAPI, python-telegram-bot, Tweepy
Blockchain: Solana, Jupiter DEX
AI/LLM: Anthropic Claude, Grok/X.AI, Ollama
Data: Birdeye, DexScreener, CoinGlass, Helius
Storage: SQLite, PostgreSQL, JSON files

## Design Decisions

### Why Supervisor Architecture?

Isolation: One bot crash does not kill others
Restart: Auto-restart with exponential backoff
Monitoring: Centralized health checks
Flexibility: Easy to enable/disable components

### Why JSON State Files?

Simplicity: No database setup
Portability: Easy to inspect/backup
Atomicity: SafeState prevents race conditions
Performance: Fast for small state

### Why Grok + Claude Hybrid?

Grok: Real-time data access
Claude: Creative content generation
Cost: Distribute load
Resilience: Fallback options

## Security

Secrets: Environment variables, SecretManager
Auth: JWT, API keys, admin whitelist
Audit: All trades logged, security events tracked
Network: CORS, CSRF, rate limiting, IP allowlist

## Monitoring

Health: /health endpoint, systemd watchdog
Logging: Structured JSON, error tracking
Metrics: Trade performance, uptime, latency
Alerts: Telegram alerts on errors
