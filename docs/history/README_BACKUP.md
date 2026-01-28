# JARVIS (Archived)

> **Historical note:** This README was archived from the repository root on 2026-02-01.
> The canonical README now lives at [`README.md`](../../README.md).

**Your Autonomous AI Trading Partner & Life Automation System**

<p align="center">
  <b>An AI that makes money while you sleep.</b><br>
  <i>Starting with crypto traders. Expanding to everyone.</i>
</p>

[![Status](https://img.shields.io/badge/Status-ONLINE-success)](https://github.com/Matt-Aurora-Ventures/Jarvis)
[![Version](https://img.shields.io/badge/Version-4.6.5-blue)](CHANGELOG.md)
[![Tests](https://img.shields.io/badge/Tests-1200%2B%20Passing-brightgreen)]()
[![Platform](https://img.shields.io/badge/Platform-macOS%20%7C%20Windows%20%7C%20Linux-lightgrey)]()
[![Solana](https://img.shields.io/badge/Solana-Mainnet-purple)](https://solana.com)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

---

## Table of Contents

- [Vision](#-vision)
- [What Makes JARVIS Different](#-what-makes-jarvis-different)
- [Core Capabilities](#-core-capabilities)
- [The Portable Brain](#-the-portable-brain)
- [Features](#-features)
- [Quick Start](#-quick-start)
- [Repository Map](#repository-map)
- [Trading Engine](#-trading-engine)
- [Staking System](#-staking-system)
- [Credit System](#-credit-system)
- [Bags.fm Integration](#-bagsfm-integration)
- [Treasury Management](#-treasury-management)
- [Self-Evolution System](#-self-evolution-system)
- [Intelligent Model Routing](#-intelligent-model-routing)
- [Conversation Engine](#-conversation-engine)
- [Cross-App Logic Loop](#-cross-app-logic-loop)
- [Voice Control](#-voice-control)
- [Cross-Platform Support](#-cross-platform-support)
- [Dashboard & Data Engine](#-dashboard--data-engine)
- [Telegram Bot](#-telegram-bot)
- [Standalone Wallet](#-standalone-wallet)
- [Current Integrations](#-current-integrations)
- [Future Platforms](#-future-platforms)
- [API Reference](#-api-reference)
- [Architecture Deep Dive](#-architecture-deep-dive)
- [MCP & Semantic Memory](#-mcp--semantic-memory-system)
- [Configuration](#%EF%B8%8F-configuration)
- [Deployment](#-deployment)
- [Change History & Traceability](#change-history--traceability)
- [Roadmap](#%EF%B8%8F-roadmap)
- [Community](#-community)
- [FAQ](#-faq)
- [Contributing](#-contributing)
- [Security](#-security)
- [License](#-license)

---

## 🚀 Recent Updates (v4.6.5 - January 21, 2026)

### 🔧 V1 Stabilization & Critical Bug Fixes

Major stability improvements addressing production issues:

#### Critical Telegram Bot Fix
| Issue | Root Cause | Fix |
|-------|------------|-----|
| Bot unresponsive | Duplicate lock acquisition caused infinite loop on Windows | Removed redundant `acquire_instance_lock()` call (was called twice) |
| Polling conflict | Multiple bot instances fighting for Telegram API | Single lock pattern with proper cleanup |

**Technical Detail**: Windows `msvcrt.locking` doesn't allow a process to lock the same file twice. The bot was attempting to acquire the same lock at lines 228 AND 330, causing the second attempt to loop forever.

#### Sentiment State Persistence
| Before | After |
|--------|-------|
| `record_sentiment_run()` called AFTER Telegram posting | Called BEFORE posting |
| If posting failed, sentiment would re-run on restart | State saved even if downstream fails |

#### Admin Check Fix
- Fixed forward reference bug in `bot_core.py`
- `DEFAULT_ADMIN_USER_ID` now defined at top of file (line 123)
- Previously referenced at line 372, defined at line 2623 → caused runtime errors

#### Error Tracking Integration
| Component | Status |
|-----------|--------|
| `tg_bot/handlers/__init__.py` | ✅ Integrated with `@error_handler` decorator |
| `bots/supervisor.py` | ✅ New `track_supervisor_error()` helper |
| Coverage | ~20% of handlers → growing |

#### New Features
- **Bags.fm Trade Adapter**: Partner fee earning on trades
- **Bags Intel Service**: bags.fm graduation monitoring
- **Dexter Sentiment**: CLI interface for sentiment queries

---

## 🚀 Previous Updates (v4.6.4 - January 17, 2026)

### 🧠 Enterprise Memory & MCP Enhancement

Complete semantic memory system for cross-session learning and context preservation.

#### 18 Model Context Protocols (MCPs) Configured
**New MCPs Added:**
- **ast-grep** - 20x faster code pattern search across 60+ modified files
- **nia** - Instant SDK/API documentation (Twitter, Telegram, Jupiter)
- **firecrawl** - Website scraping for market data extraction
- **postgres** - Direct queries to `continuous_claude` semantic memory database
- **perplexity** - Real-time web research for token analysis

**Total MCP Stack:** 18 servers (memory, filesystem, git, docker, solana, twitter, telegram, github, brave-search, etc.)

#### Automated Memory Import System
| Feature | Capability |
|---------|------------|
| **Source** | PostgreSQL `continuous_claude` database (100+ learnings) |
| **Storage** | Local SQLite with full-text search + JSONL for MCP server |
| **Access** | Python API + CLI commands + `/recall` skill in Claude Code |
| **Search** | Confidence-ranked, topic-filtered, semantic matching |

**New Files:**
- `MEMORY_QUERY_GUIDE.md` - 50+ query examples for all Jarvis tasks
- `MCP_SETUP_SUMMARY.md` - Complete system documentation
- `core/memory/auto_import.py` - Memory import engine (398 lines)
- `scripts/verify_mcp_setup.py` - Setup verification tool

#### Query Examples
```python
# Import and search
from core.memory.auto_import import MemoryImporter
importer = MemoryImporter()
results = importer.search_imported_memories("trading strategy", limit=10)

# View statistics
stats = importer.get_memory_stats()  # Total entries, by type, by confidence
```

#### What This Enables
✓ No knowledge loss between sessions
✓ Cross-session learning & pattern discovery
✓ 20x faster code search (ast-grep)
✓ Instant API documentation (nia)
✓ Real-time market research (perplexity + firecrawl)
✓ Semantic memory queries with 100+ learnings indexed

---

## 🚀 Previous Updates (v4.6.2 - January 2026)

### ⚡ Code Quality & Async Performance

Deep infrastructure improvements for reliability and performance.

#### Native Async Twitter Posting
| Change | Before | After |
|--------|--------|-------|
| HTTP Client | `requests` (blocking) | `aiohttp` (native async) |
| Event Loop | Blocked via `run_in_executor` | Non-blocking |
| Timeout | Basic | `aiohttp.ClientTimeout(total=30)` |
| Exceptions | Limited handling | Full aiohttp exception support |

#### SQLite Connection Management
- **Context Managers**: All database operations now use `with self._get_connection():`
- **Auto-Cleanup**: Connections properly closed after each operation
- **No More Locks**: Prevents SQLite database lock issues

#### Exception Handling Hardening
| File | Before | After |
|------|--------|-------|
| `buy_tracker/bot.py` | `except:` | `except Exception:` |
| `treasury/backtest.py` | `except:` | `except (ValueError, TypeError):` |
| `spam_protection.py` | `except:` | `except ValueError:` |

> **Why This Matters**: Bare `except:` catches SystemExit and KeyboardInterrupt, preventing graceful shutdown.

#### Additional Improvements
- OAuth token persistence across sessions
- Circuit breaker verification
- Engagement tracker metrics implementation
- Max positions increased to 50
- Grok API cost tracking

---

## 🚀 Previous: v4.6.1 - January 2026

### 🛡️ Treasury Risk Management & Active Stop Loss Monitoring

Critical risk management improvements for the trading system:

#### Active Stop Loss Monitoring
| Feature | Description |
|---------|-------------|
| `monitor_stop_losses()` | Background task checks positions every 60 seconds |
| Emergency Close | Auto-closes positions down >90% (even without SL breach) |
| TP Detection | Auto-closes when take profit price is hit |
| Admin Notifications | Telegram alerts sent when positions are auto-closed |

#### Position Health Dashboard
| Status | Condition | Action |
|--------|-----------|--------|
| `[SL BREACHED]` | Price <= stop loss | Immediate close |
| `[CRITICAL]` | Position down >50% | Alert displayed |
| `[WARNING]` | Position down >20% | Caution flag |
| `[TP HIT]` | Price >= take profit | Auto-close |

#### Token Risk Classification
| Risk Level | Market Cap | Liquidity | Position Modifier |
|------------|------------|-----------|-------------------|
| ESTABLISHED | >$500M | >$1M | 1.0x (full) |
| MID | >$50M | >$100K | 0.85x |
| MICRO | >$1M | >$20K | 0.7x |
| SHITCOIN | <$1M | <$20K | 0.5x (half) |

#### New Safeguards
- **Liquidity Check**: Blocks trades on tokens with <$1,000 daily volume
- **Tighter Stops for Shitcoins**: -7% SL vs -15% for established tokens
- **Cross-Module Dedup**: Shared `XMemory` prevents duplicate tweets across all posting modules
- **Content Relevance Filter**: Rejects generic/irrelevant AI-generated content

---

## 🚀 Previous: v4.6.0 - January 2026

### 🧠 MASSIVE RELEASE: Autonomous Intelligence & Full-Stack Expansion

**The largest single release in JARVIS history.** 7,750+ lines of new code across 105 new files.

#### Core Autonomy System - NEW
| Module | Description |
|--------|-------------|
| `action_executor.py` | **Crown jewel** - Bridges observation/learning to execution with priority queues |
| `news_detector.py` | Real-time crypto news analysis with AI-powered filtering |
| `enhanced_market_data.py` | 7+ data sources: CoinGecko, DeFiLlama, CoinMarketCap |
| `resilient_fetcher.py` | Circuit breaker pattern, multi-source price fetching |
| `whale_tracker.py` | Large transaction monitoring |
| `price_alerts.py` | User-configurable price notifications |
| `webhook_manager.py` | External integration hub with Discord/Slack support |

#### X (Twitter) Bot - Major Expansion
| Feature | Description |
|---------|-------------|
| Quote Tweets | Smart quote selection with engagement scoring |
| Thread Generation | Multi-tweet narrative building |
| Trend Analysis | Posts aligned with trending topics |
| Engagement Tracking | Metrics collection for posted content |
| Dynamic Intervals | Adjust posting based on engagement |

#### 70+ New Frontend Components
| Category | Components |
|----------|------------|
| **Trading** | AISuggestions, BacktestDashboard, LiveMarketFeed, TradingChart, StrategyBuilder |
| **DeFi** | airdrop/, bridge/, defi/, lending/, liquidity/, staking/, yield/ |
| **Analytics** | analytics/, portfolio/, profit/, risk/, roi/ |
| **Market** | correlation/, heatmap/, orderbook/, screener/, sentiment/, volatility/ |
| **On-Chain** | holders/, onchain/, smartmoney/, whale/ |
| **Advanced** | arbitrage/, derivatives/, leverage/, liquidations/, mev/, options/, perpetuals/ |

#### New Telegram Features
- **Claude CLI Handler**: Natural language processing for commands
- **20+ new commands**: Trading, alerts, system monitoring
- **Inline keyboards**: Interactive button menus everywhere

#### Stats
| Metric | Value |
|--------|-------|
| Lines Added | 7,750+ |
| New Files | 105 |
| Modified Files | 49 |
| New Components | 70+ |

**Full details**: See [CHANGELOG.md](CHANGELOG.md)

---

## 🚀 Previous Updates (v4.5.0 - January 2026)

### 🛡️ Bot Supervisor & Resilience System
**Robust process management with auto-restart and monitoring** (`bots/supervisor.py`):

| Feature | Description |
|---------|-------------|
| `BotSupervisor` | Central orchestrator managing all bot components |
| Auto-Restart | Exponential backoff (5s → 300s) on crashes |
| Health Monitoring | 60-second interval health checks for all components |
| Component States | Tracks uptime, restart counts, consecutive failures |
| Max Restart Protection | Stops after 100 restarts to prevent runaway loops |

**Components Managed:**
- `buy_bot` - Transaction tracking and monitoring
- `sentiment_reporter` - Hourly market sentiment reports
- `twitter_poster` - Automated Twitter/X posting
- `telegram_bot` - Main Telegram bot with anti-scam

### 🔒 Anti-Scam Protection - NEW
**Automatic spam/scam detection and removal** (integrated in `tg_bot/bot.py`):

| Feature | Description |
|---------|-------------|
| Pattern Detection | Regex-based scam phrase detection |
| Auto-Restrict | Automatically restricts detected scammers |
| Auto-Delete | Removes scam messages instantly |
| Admin Alerts | Notifies admins of detected threats |
| `/unban` Command | Admin command to restore false positives |

### 📊 Health Endpoint & Monitoring - NEW
**Kubernetes-style health probes** (`bots/health_endpoint.py`):

| Endpoint | Purpose |
|----------|---------|
| `/health` | Overall system health (JSON) |
| `/ready` | Readiness probe for load balancers |
| `/live` | Liveness probe for orchestrators |
| `/metrics` | Prometheus-compatible metrics |

### 💰 Resilient Price Fetching - NEW
**Multi-source price fetching with circuit breaker** (`core/price/resilient_fetcher.py`):

| Feature | Description |
|---------|-------------|
| DexScreener Primary | Most reliable source, used first |
| Jupiter Fallback | Secondary source when DexScreener fails |
| CoinGecko Tertiary | Final fallback for major tokens |
| 30-Second Cache | Reduces API spam, improves performance |
| Circuit Breaker | Tracks source health, avoids dead APIs |

### 🔧 Configuration Improvements - NEW
| Setting | Description | Default |
|---------|-------------|---------|
| `LOW_BALANCE_THRESHOLD` | Treasury low balance warning | 0.01 SOL |
| Sentiment Report Interval | Hourly reports | 60 minutes |

### 🐛 Bug Fixes
- Fixed Jupiter price.jup.ag DNS failures spamming logs
- Changed price fetching to use DexScreener as primary source
- Made low balance threshold configurable via environment
- Reduced log noise from expected API fallbacks

---

## 🚀 Previous Updates (v4.4.0 - January 2026)

### 🤖 Complete Autonomy System
**12 autonomous modules for full self-operation** (`core/autonomy/`):

| Module | Purpose |
|--------|---------|
| `self_learning.py` | Track tweet engagement, learn what works |
| `memory_system.py` | Remember users, conversations, sentiment |
| `reply_prioritizer.py` | Score mentions, prioritize influencers |
| `trending_detector.py` | Find trends before peak via Grok |
| `health_monitor.py` | Self-monitoring, API checks, auto-alerts |
| `content_calendar.py` | Event awareness, optimal posting times |
| `confidence_scorer.py` | Rate predictions 1-10, track accuracy |
| `alpha_detector.py` | Volume spikes, new pairs, on-chain alpha |
| `voice_tuner.py` | Context-aware personality adjustment |
| `thread_generator.py` | Auto-generate threads when needed |
| `quote_strategy.py` | Strategic quote tweeting |
| `analytics.py` | Performance dashboard, weekly insights |

**Orchestrator** (`core/autonomy/orchestrator.py`): Central controller coordinating all modules with `get_content_recommendations()`, smart reply decisions, and background learning tasks.

### 🐦 Twitter Bot - @Jarvis_lifeos
- **Centralized Voice Bible**: `core/jarvis_voice_bible.py` - single source of truth
- **Brand Personality**: "Smart kid who's actually cool" - calm, funny, helpful, edgy
- **Smart Reply Prioritization**: Score mentions by follower count, engagement, questions
- **Dynamic Voice Tuning**: Context-aware (reply vs thread vs market update)
- **Learning Loop**: Tracks engagement, learns optimal content types and timing
- **Grok Integration**: Primary sentiment analysis via xAI
- **Thread Generation**: Auto-generate threads for deep topics
- **Quote Strategy**: Strategic engagement with high-value tweets

### 🏗️ Core Infrastructure Upgrades
- **API Versioning**: `core/api/versioning.py` - semantic versioning, deprecation
- **Error Handling**: `core/api/errors.py` - structured error responses
- **Config Loader**: `core/config/loader.py` - multi-source config with validation
- **DB Connection Pool**: `core/db/pool.py` - async connection pooling
- **Cache Decorators**: `core/cache/decorators.py` - memoization, TTL cache
- **Task Queue**: `core/tasks/queue.py` - async background job processing
- **Validation**: `core/validation/validators.py` - input validation framework

### 🔒 Security & Resilience
- **Emergency Shutdown**: `core/security/emergency_shutdown.py` - graceful termination
- **Encrypted Storage**: `core/security/encrypted_storage.py` - at-rest encryption
- **Circuit Breakers**: Enhanced with half-open state, recovery probes
- **Retry Logic**: Exponential backoff with jitter, per-exception config
- **Startup Validator**: `core/startup_validator.py` - pre-flight checks

### 📊 Monitoring & Observability
- **Dashboard**: `core/monitoring/dashboard.py` - real-time metrics visualization
- **Request Logging**: `api/middleware/request_logging.py` - structured access logs
- **Compression**: `api/middleware/compression.py` - gzip/brotli responses
- **Profiler**: Enhanced CPU/memory profiling with flame graphs

### 📚 Documentation
- **Improvement Checklist**: `docs/IMPROVEMENT_CHECKLIST.md` - production readiness
- **Strategy Learnings**: Architecture decisions and rationale
- **DB Migrations**: `scripts/db/migrate.py` - schema versioning

---

## 🚀 Previous Updates (v4.2.0 - v4.3.0)

### Treasury Trading System - LIVE
- **Live Treasury Buys via Telegram**: Click-to-buy buttons with mandatory TP/SL
- **Jupiter Lite API Integration**: DNS-resilient trading (fallback when quote-api fails)
- **Hardwired Key Manager**: Centralized key persistence - keys never get lost
- **Transaction Signing Fix**: Proper `VersionedTransaction` signing with `solders`

### Telegram Bot Enhancements
- **Smart Response Filtering**: Jarvis only responds to messages directed at him
- **Sentiment Reports with Buy Buttons**: Real-time trading from reports
- **Admin-Only Trading**: Treasury trades restricted to authorized users
- **Unicode Error Fixes**: Clean response handling for all token names

### Security & Infrastructure
- **KeyManager Module**: `core/security/key_manager.py` - singleton key management
- **Credential Loader**: Unified bot credential management
- **RBAC System**: Role-based access control foundation
- **Pre-commit Hooks**: Automated code quality checks

### Trading Signals & Risk
- **Decision Matrix**: Multi-signal trade decision framework
- **Cooldown System**: Configurable cooldowns after trade closures
- **Risk Management**: Position sizing (max 25%), loss limits, circuit breakers
- **CoinGlass Integration**: Liquidation data for contrarian signals

### Observability
- **Metrics Module**: Prometheus-compatible metrics
- **Tracing Module**: Distributed tracing support
- **Alerting System**: Multi-channel alert routing
- **Grafana Dashboards**: Pre-built monitoring dashboards

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

## 🌟 What Makes JARVIS Different

### Not Just Another Chatbot

| Traditional AI | JARVIS |
|---------------|--------|
| Responds when asked | Proactively takes action |
| Forgets between sessions | Remembers everything about you |
| Single-purpose | Multi-domain intelligence |
| Needs constant supervision | Earns autonomy through success |
| Same for everyone | Learns your patterns and adapts |

### The Three Pillars

**1. Autonomy Through Trust**
JARVIS doesn't start with full autonomy. It earns trust through:
- Successful actions without errors
- Accurate predictions
- User satisfaction feedback
- Time-weighted reputation building

**2. Financial Intelligence First**
Starting with crypto trading creates:
- Measurable success metrics (P&L)
- Self-funding capability (trading profits)
- Clear value proposition ($$$)
- Foundation for life automation revenue

**3. Platform Agnostic**
JARVIS lives everywhere:
- Discord bot for community trading
- Telegram bot for mobile alerts
- Web dashboard for portfolio management
- Desktop app for voice control
- API for third-party integrations
- Future: iOS, Android, AR/VR

---

## 💪 Core Capabilities

### Real-Time Decision Engine

```
┌─────────────────────────────────────────────────────────────┐
│                    JARVIS DECISION LOOP                     │
├─────────────────────────────────────────────────────────────┤
│  Data Sources         │  Analysis Engine    │  Actions      │
│  ─────────────────    │  ─────────────────  │  ───────────  │
│  • Market feeds       │  • Signal fusion    │  • Execute    │
│  • Whale movements    │  • Pattern match    │  • Alert      │
│  • Social sentiment   │  • Risk assessment  │  • Learn      │
│  • News events        │  • ML prediction    │  • Report     │
│  • On-chain data      │  • Confidence score │  • Adapt      │
└─────────────────────────────────────────────────────────────┘
```

### Memory & Context System

| Memory Type | Duration | Purpose |
|-------------|----------|---------|
| **Working Memory** | Session | Current conversation context |
| **Short-Term** | 24 hours | Recent patterns and events |
| **Long-Term** | Permanent | User preferences, history |
| **Episodic** | Permanent | Specific memorable events |
| **Semantic** | Permanent | Learned facts and relationships |

### Multi-Modal Intelligence

- **Text**: Natural language understanding and generation
- **Voice**: Wake word activation, real-time conversation
- **Visual**: Chart analysis, screenshot understanding
- **Data**: Time-series analysis, pattern recognition
- **Code**: Self-modification, strategy generation

---

## 🧠 The Portable Brain

### Your AI That Follows You Everywhere

JARVIS maintains a **unified identity** across all platforms:

```
                        ┌─────────────────┐
                        │  JARVIS CORE    │
                        │  (Portable      │
                        │   Brain)        │
                        └────────┬────────┘
                                 │
        ┌────────────────────────┼────────────────────────┐
        │                        │                        │
   ┌────▼────┐            ┌──────▼──────┐          ┌──────▼──────┐
   │ Discord │            │  Telegram   │          │    Web      │
   │   Bot   │            │    Bot      │          │ Dashboard   │
   └────┬────┘            └──────┬──────┘          └──────┬──────┘
        │                        │                        │
        └────────────────────────┼────────────────────────┘
                                 │
                        ┌────────▼────────┐
                        │  Unified State  │
                        │  - Memory       │
                        │  - Preferences  │
                        │  - Trust Level  │
                        │  - Portfolio    │
                        └─────────────────┘
```

### State Synchronization

- **Real-time sync**: Actions on one platform reflect instantly on others
- **Context continuity**: Start a conversation on mobile, continue on desktop
- **Preference inheritance**: Settings apply everywhere automatically
- **Portfolio unified**: One wallet, visible from all interfaces

### Offline Mode

JARVIS works even without internet:
- Local LLM fallback (Ollama with Llama 3.2)
- Cached market data for basic analysis
- Voice synthesis with Piper TTS
- Journal and notes functionality
- Alert history review

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

### 📈 Data Platform (v3.8.0)
| Feature | Description |
|---------|-------------|
| **Anonymous Data Collection** | GDPR-compliant with k-anonymity enforcement |
| **Data Quality Scoring** | 6-dimension scoring (completeness, accuracy, freshness) |
| **Anomaly Detection** | Z-score outliers, spike detection, impossible values |
| **A/B Testing** | Deterministic hash-based user assignment, statistical analysis |
| **Strategy Optimization** | Optuna hyperparameter tuning with walk-forward validation |
| **Data Marketplace** | Packaging, dynamic pricing, contributor payouts |

### 🔍 Monitoring & Alerts (v3.8.0)
| Feature | Description |
|---------|-------------|
| **Health Monitoring** | Real-time component status (DB, RPC, Treasury, Trading) |
| **Alert Management** | Severity levels, cooldowns, suppression |
| **Notifications** | Slack and Discord webhook integration |
| **Treasury Reports** | Weekly/monthly performance with Markdown export |
| **Rewards Calculator** | Tiered APY projections with lock bonuses |

### 📢 Multi-Channel Alerts (v3.9.0)
| Feature | Description |
|---------|-------------|
| **Alert Delivery** | Discord, Telegram, Email, Push, Webhook channels |
| **Rich Formatting** | Discord embeds, Telegram Markdown, HTML email |
| **Retry Logic** | Configurable attempts with exponential backoff |
| **User Preferences** | Per-user channel and alert type settings |

### 🐋 Whale Tracking (v3.9.0)
| Feature | Description |
|---------|-------------|
| **Whale Tracker** | Monitor large transactions above threshold |
| **Pattern Analysis** | Detect accumulation, distribution, coordinated activity |
| **Trading Signals** | Generate signals from whale movements |
| **Risk Assessment** | Smart money flow direction analysis |

### 📊 Signal Fusion & Position Sizing (v3.9.0)
| Feature | Description |
|---------|-------------|
| **Signal Fusion** | Combine multiple sources with dynamic weighting |
| **Confidence Scoring** | Meta-signals with track-record-based weights |
| **Position Sizer** | Kelly Criterion, volatility-adjusted, risk-based sizing |
| **Risk Management** | Configurable max position, drawdown limits |

### 👥 Copy Trading (v3.9.0)
| Feature | Description |
|---------|-------------|
| **Leader System** | Tier-based rankings (Bronze → Diamond) |
| **Follower System** | Risk-adjusted copying with filters |
| **Copy Modes** | Exact, proportional, signal-only |
| **Safety Controls** | DISABLED until security audit complete |

### 💼 Portfolio Tracking (v3.9.0)
| Feature | Description |
|---------|-------------|
| **Position Manager** | Track buys, sells, transfers with cost basis |
| **P&L Analytics** | Realized/unrealized gains, total return |
| **Performance Metrics** | Sharpe ratio, max drawdown, volatility |
| **Benchmark Comparison** | Alpha, beta vs SOL/market indices |

### 👤 User Accounts & Subscriptions (v3.9.0)
| Feature | Description |
|---------|-------------|
| **Wallet Auth** | Wallet-based authentication (NO KYC) |
| **Subscription Tiers** | Free, Starter, Pro, Whale, Enterprise |
| **Feature Flags** | Percentage rollout, tier gating, overrides |
| **Usage Limits** | Per-tier alerts, API calls, positions |

### 🔄 DCA Automation (v3.9.0)
| Feature | Description |
|---------|-------------|
| **Scheduler** | Hourly, daily, weekly, monthly frequency |
| **Smart DCA** | Adjust size based on fear/greed, dips, volatility |
| **Multi-Token** | Configure different schedules per token |
| **Safety Controls** | DISABLED until security audit complete |

### 🏪 Strategy Marketplace (v3.9.0)
| Feature | Description |
|---------|-------------|
| **Strategy Listings** | Share and monetize trading strategies |
| **Subscription Model** | Monthly subscriptions with creator payouts |
| **Review System** | Ratings, helpfulness votes, moderation |
| **Performance Tracking** | Historical returns for all strategies |

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

## Repository Map

This section maps every major capability to its home in the repo so the README stays exhaustive.

### Top-Level Structure

| Path | Purpose |
| --- | --- |
| `api/` | API servers (Flask/FastAPI), routes, webhooks, websocket streaming. |
| `bin/` | CLI entry points (`lifeos`). |
| `config/` | Runtime settings and RPC provider configs. |
| `contracts/` | On-chain programs for staking and $KR8TIV. |
| `core/` | Core engine: trading, treasury, data platform, self-improvement, safety. |
| `data/` | Runtime state, memory DB, reports, positions, paper trading, wallets. |
| `database/` | Database schema and migrations. |
| `desktop/` | Desktop task manager UI (tkinter). |
| `docs/` | Architecture, trading, security, setup, handoffs. |
| `examples/` | Demos and small integration tests. |
| `frontend/` | React dashboard (Vite + Tailwind). |
| `integrations/` | External service integrations (Bags.fm, etc.). |
| `lifeos/` | LifeOS runtime, config, plugins, persistence. |
| `logs/` | Local runtime logs and PID files. |
| `monitoring/` | Prometheus/Grafana/Alertmanager config. |
| `playground/` | Experiments and simulations. |
| `plugins/` | Modular extensions (telegram, trading, voice, x_sentiment). |
| `scripts/` | Ops utilities, trading helpers, health checks. |
| `tests/` | Automated test suite. |
| `tg_bot/` | Telegram bot app, handlers, services. |
| `web/` | Flask control deck and web UI helpers. |
| `.github/` | CI, workflows, issue templates. |

### Capability-to-Module Index

| Capability | Primary modules |
| --- | --- |
| Trading and execution | `core/trading/`, `core/trading_*.py`, `scripts/*trader*`, `api/`, `frontend/` |
| Paper trading and coliseum | `core/paper_trading.py`, `core/trading_coliseum.py`, `tg_bot/`, `scripts/*paper*` |
| Treasury and rewards | `core/treasury/`, `core/economics/`, `core/monitoring/`, `api/` |
| Staking and credits | `contracts/`, `core/staking/`, `core/credits/`, `core/payments/` |
| Data platform and experiments | `core/data/`, `core/data_consent/`, `core/experiments/`, `core/metrics/` |
| Monitoring and alerts | `core/monitoring/`, `core/alerts/`, `monitoring/`, `api/` |
| Whale tracking | `core/whale_tracking/` (tracker, analyzer) |
| Signal fusion | `core/signals/` (fusion, position_sizer) |
| Copy trading | `core/copy_trading/` (leader, follower, copier) |
| Portfolio tracking | `core/portfolio/` (tracker, performance) |
| DCA automation | `core/dca/` (scheduler, smart_dca) |
| Strategy marketplace | `core/strategy_marketplace/` (strategies, reviews) |
| User accounts | `core/users/` (account, subscriptions, features) |
| Voice and wake word | `core/voice*.py`, `core/wake_word.py`, `plugins/voice/` |
| Self-improvement | `core/self_improving/`, `core/self_improvement_engine*.py`, `lifeos/` |
| Integrations and plugins | `integrations/`, `core/integrations/`, `plugins/` |
| Interfaces | `frontend/`, `tg_bot/`, `web/`, `desktop/` |

### Primary Entry Points

- CLI: `bin/lifeos` (calls `core/cli.py`)
- LifeOS runtime: `lifeos/jarvis.py`, `core/jarvis.py`
- API servers: `api/server.py` (Flask), `api/fastapi_app.py` (FastAPI)
- Dashboard: `frontend/` (Vite dev server)
- Telegram bot: `tg_bot/bot.py`
- Web control deck: `web/task_web.py`
- Desktop task GUI: `desktop/task_gui.py`
- Ops scripts: `scripts/run_dev.py`, `scripts/run_trading_pipeline.py`

### Data and Storage Locations

- `data/` for memory (`jarvis_memory.db`), state (`jarvis_state.json`), positions, paper trading, wallets.
- `database/migrations/` for schema evolution.
- `logs/` for runtime logs and PID files.
- `secrets/` for local keys (created during setup, git-ignored).
- Local caches (for example `.pytest_cache/`, `__pycache__/`) are ignored.

### Docs Index

- `docs/architecture/` for system architecture and audits.
- `docs/trading/` for trading system guidance.
- `docs/security/` for security and compliance notes.
- `docs/setup/`, `docs/development/`, `docs/sessions/` for environment, dev, and handoff notes.
- Key references: `docs/ARCHITECTURE_ANALYSIS_2026-01-01.md`, `docs/TRADING_AI_CONTEXT.md`, `docs/SENTIMENT_BOTS_GUIDE.md`.

### Testing and QA

- `tests/` holds unit and integration coverage across core, API, and integrations.
- Run with `pytest tests/ -v` (see Contributing for more).

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

### Active Position Monitoring (v4.6.1)

Background task runs every 60 seconds to protect against missed limit orders:

```python
# bots/treasury/trading.py
async def monitor_stop_losses() -> List[Dict]:
    """
    Active stop loss monitoring - catches positions that miss their limit orders.
    - Checks all open positions against current prices
    - Force-closes any position that breached SL
    - Emergency close for positions down >90%
    - Auto-takes profit when TP is hit
    """
```

**Position Health Statuses:**
| Status | Trigger | Action |
|--------|---------|--------|
| SL_BREACHED | Current price <= Stop loss | Auto-close |
| EMERGENCY_90PCT | Down >90% | Force close |
| TP_HIT | Current price >= Take profit | Take profit |

**Liquidity Guard:**
- Trades blocked if daily volume < $1,000
- Prevents entering positions with no exit liquidity

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

## 🔄 Self-Evolution System

JARVIS continuously improves itself through multiple feedback loops:

### The Mirror Test (Nightly Self-Correction)

Every night at 3am, JARVIS:
1. **Replays** the last 24 hours using Minimax 2.1
2. **Scores** its own performance (latency, accuracy, satisfaction)
3. **Proposes** code refactors and prompt improvements
4. **Validates** changes against 100 historical scenarios
5. **Auto-applies** if improvement score > 85%

```python
from core.self_improving.mirror_test import MirrorTest

mirror = MirrorTest()
report = await mirror.run_nightly_review()

print(f"Actions reviewed: {report.action_count}")
print(f"Issues found: {report.issues}")
print(f"Improvements applied: {report.improvements}")
```

### Trust Ladder

JARVIS earns autonomy through successful actions:

| Level | Name | Permissions | Promotion Criteria |
|-------|------|-------------|-------------------|
| 0 | STRANGER | Only respond when asked | Initial state |
| 1 | ACQUAINTANCE | Can suggest, needs approval | 10 successful interactions |
| 2 | COLLEAGUE | Can draft content for review | 50 successful, <5% rejection |
| 3 | PARTNER | Can act autonomously, reports after | 200 successful, <2% rejection |
| 4 | OPERATOR | Full autonomy in domain | 500 successful, <1% rejection |

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

### Strategy Evolution

JARVIS generates new strategies through:

| Method | Description | Success Rate |
|--------|-------------|--------------|
| **Mutation** | Modify existing strategy parameters | ~15% |
| **Crossover** | Combine two successful strategies | ~20% |
| **Generation** | LLM creates from market hypothesis | ~8% |
| **Adaptation** | Adjust for new market regime | ~25% |

---

## 🧭 Intelligent Model Routing

JARVIS automatically selects the best AI model for each task:

### Model Selection Matrix

| Task Type | Primary Model | Fallback | Latency | Cost |
|-----------|---------------|----------|---------|------|
| **Trading Analysis** | Grok (xAI) | Claude | 200ms | Medium |
| **Code Generation** | Claude | GPT-4 | 500ms | High |
| **Quick Q&A** | Groq (Llama 3.2) | Ollama | 50ms | Low |
| **Vision/Charts** | GPT-4V | Claude | 800ms | High |
| **Self-Reflection** | Minimax 2.1 | Claude | 300ms | Medium |
| **Offline** | Ollama Local | - | 100ms | Free |

### Routing Logic

```python
from core.model_router import ModelRouter

router = ModelRouter()

# Automatic routing based on task
response = await router.route(
    task="Analyze this chart for entry points",
    image=chart_bytes,
    priority="accuracy",  # or "speed" or "cost"
)

# Force specific provider
response = await router.route(
    task="Quick price check for SOL",
    provider="groq",  # Fast and cheap
)
```

### Fallback Chain

```
Primary Provider Failed?
    │
    ├─► Try Secondary Provider
    │       │
    │       └─► Try Tertiary Provider
    │               │
    │               └─► Use Ollama Local
    │                       │
    │                       └─► Graceful Error Response
```

### Cost Optimization

- **Priority Queue**: Urgent tasks use premium models
- **Batching**: Group similar requests for efficiency
- **Caching**: Repeated queries use cached responses
- **Off-peak**: Expensive analysis runs during low-cost hours

---

## 💬 Conversation Engine

JARVIS maintains natural, context-aware conversations across all platforms:

### Conversation Memory

| Type | Scope | TTL | Examples |
|------|-------|-----|----------|
| **Session Context** | Current chat | Session | "What we're discussing now" |
| **User Preferences** | User-level | Permanent | "Always show USD prices" |
| **Relationship History** | User-level | 90 days | "Last 100 conversations" |
| **Global Knowledge** | All users | Permanent | "BTC all-time high" |

### Personality Configuration

```python
from core.conversation import ConversationEngine

engine = ConversationEngine()

# Set personality traits
engine.configure(
    formality="casual",        # casual, neutral, formal
    verbosity="concise",       # verbose, balanced, concise
    humor="occasional",        # never, occasional, frequent
    proactivity="high",        # low, medium, high
)
```

### Context Management

```
User Message
    │
    ├─► Intent Classification
    │       │
    │       ├─► Trading Intent → Fetch portfolio context
    │       ├─► General Chat → Load relationship history
    │       └─► Technical Question → Load relevant docs
    │
    ├─► Context Window Optimization
    │       │
    │       └─► Summarize old context + Inject fresh context
    │
    └─► Response Generation
            │
            └─► Model Router → Appropriate LLM
```

### Multi-Turn Handling

- **Reference Resolution**: "Buy more of that token" → Resolves to previous token
- **Follow-up Detection**: "What about the other one?" → Tracks alternatives
- **Correction Handling**: "No, I meant SOL" → Updates understanding
- **Clarification Requests**: "Did you mean SOL or BONK?" → Asks when ambiguous

---

## 🔄 Cross-App Logic Loop

JARVIS operates as a unified system across all platforms and integrations:

### The Logic Loop

```
┌──────────────────────────────────────────────────────────────────┐
│                     CROSS-APP LOGIC LOOP                          │
├──────────────────────────────────────────────────────────────────┤
│                                                                   │
│    ┌─────────┐     ┌─────────┐     ┌─────────┐     ┌─────────┐  │
│    │ OBSERVE │ ──► │ ANALYZE │ ──► │ DECIDE  │ ──► │   ACT   │  │
│    └─────────┘     └─────────┘     └─────────┘     └─────────┘  │
│         │                                                  │      │
│         └──────────────────────────────────────────────────┘      │
│                         LEARN & ADAPT                             │
└──────────────────────────────────────────────────────────────────┘

OBSERVE: Market data, user activity, platform events
ANALYZE: Pattern recognition, signal fusion, risk assessment
DECIDE:  Strategy selection, confidence scoring, action planning
ACT:     Execute trades, send alerts, update state
LEARN:   Outcome tracking, reflexion, self-improvement
```

### Event Bus

All components communicate through a unified event system:

```python
from core.events import EventBus, Event

bus = EventBus()

# Subscribe to events
@bus.subscribe("whale.detected")
async def handle_whale(event: Event):
    # Trigger across all platforms
    await alert_discord(event.data)
    await alert_telegram(event.data)
    await update_dashboard(event.data)

# Publish events
await bus.publish(Event(
    type="trade.executed",
    data={"token": "SOL", "amount": 10, "price": 150}
))
```

### State Synchronization

| Component | Sync Frequency | Mechanism |
|-----------|---------------|-----------|
| Portfolio | Real-time | WebSocket |
| Positions | 5 seconds | Polling + Events |
| Alerts | Instant | Event Bus |
| User Preferences | On-change | Database Trigger |
| Trading State | Real-time | Memory + Persistence |

### Bot Online/Offline Modes

| Mode | Description | Capabilities |
|------|-------------|--------------|
| **ONLINE** | Full connectivity | All features available |
| **DEGRADED** | Limited connectivity | Cached data, local LLM |
| **OFFLINE** | No internet | Local-only features |
| **MAINTENANCE** | Scheduled downtime | Status page only |

```python
from core.bot_modes import BotMode, get_current_mode

mode = get_current_mode()

if mode == BotMode.ONLINE:
    result = await execute_trade(params)
elif mode == BotMode.DEGRADED:
    result = await queue_trade_for_later(params)
else:
    notify_user("Trading unavailable in offline mode")
```

---

## 🎤 Voice Control

### Wake Word Activation

```bash
# Start voice mode
./bin/lifeos chat --streaming

# With Minimax 2.1 streaming consciousness
./bin/lifeos chat --streaming --minimax
```

### Features

| Feature | Description |
|---------|-------------|
| Wake Word | "Hey JARVIS" activates listening |
| Barge-In | Interrupt mid-response naturally |
| Pre-Caching | Predicts your next 3 likely intents |
| Ring Buffer | Last 30 seconds always in context |
| Offline TTS | Piper synthesis works without internet |
| Morgan Freeman | Deep narrator voice preset via edge-tts |

### Voice Presets (Voice Bible)

```python
from core.voice_tts import speak

# Available presets
speak("Hello", preset="morgan")   # Morgan Freeman-style deep voice
speak("Hello", preset="jarvis")   # Default Jarvis voice
speak("Hello", preset="butler")   # British butler (en-GB-RyanNeural)
speak("Hello", preset="narrator") # Deep storyteller (en-US-RogerNeural)
speak("Hello", preset="tech")     # Fast technical voice
```

### TTS/STT Engine Support

| Engine | Type | Cost | Offline |
|--------|------|------|---------|
| Edge-TTS | TTS | FREE | No |
| Piper | TTS | FREE | Yes |
| Faster Whisper | STT | FREE | Yes |
| Gemini | STT | FREE tier | No |
| OpenAI Whisper | STT | $0.006/min | No |

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

## 🎨 Dashboard & Data Engine

### Trading Dashboard V2

Premium trading command center at `http://localhost:5173/trading`:

**Features**:
- 📊 Live Position Card with P&L
- 🛠️ Token Scanner with rug detection
- 💬 Floating JARVIS Chat
- 📈 TradingView-style charts
- 🔄 Auto-refresh (5s positions, 10s wallet)

### Routes

| Route | Page | Description |
|-------|------|-------------|
| `/` | Dashboard | Portfolio overview |
| `/chat` | Chat | JARVIS AI assistant |
| `/trading` | Trading | Charts, positions, scanner |
| `/voice` | Voice | Voice command interface |
| `/roadmap` | Roadmap | Interactive progress tracker |
| `/settings` | Settings | API keys, preferences |
| `/treasury` | Treasury | Treasury transparency dashboard |
| `/staking` | Staking | Staking and rewards |
| `/admin` | Admin | System health and metrics |

### The Giant Data Engine

JARVIS aggregates data from multiple sources into a unified intelligence layer:

```
┌──────────────────────────────────────────────────────────────────────┐
│                         DATA ENGINE ARCHITECTURE                      │
├──────────────────────────────────────────────────────────────────────┤
│                                                                       │
│   ┌─────────────┐   ┌─────────────┐   ┌─────────────┐               │
│   │   Market    │   │   Social    │   │  On-Chain   │               │
│   │    Data     │   │   Signals   │   │    Data     │               │
│   └──────┬──────┘   └──────┬──────┘   └──────┬──────┘               │
│          │                 │                  │                       │
│          └─────────────────┼──────────────────┘                       │
│                            │                                          │
│                   ┌────────▼────────┐                                 │
│                   │  FUSION ENGINE  │                                 │
│                   └────────┬────────┘                                 │
│                            │                                          │
│   ┌────────────────────────┼────────────────────────┐                │
│   │                        │                        │                │
│   ▼                        ▼                        ▼                │
│ ┌─────────┐          ┌─────────┐          ┌─────────────┐           │
│ │ Trading │          │ Alerts  │          │ Dashboard   │           │
│ │ Engine  │          │ System  │          │   Updates   │           │
│ └─────────┘          └─────────┘          └─────────────┘           │
└──────────────────────────────────────────────────────────────────────┘
```

### Data Sources

| Source | Data Type | Update Frequency | Use Case |
|--------|-----------|-----------------|----------|
| **BirdEye** | Token prices, liquidity | Real-time | Trading signals |
| **DexScreener** | DEX analytics | 5 seconds | Token discovery |
| **GMGN** | Trending tokens | 1 minute | Hot token alerts |
| **GeckoTerminal** | Pool data | Real-time | Liquidity analysis |
| **Helius** | On-chain events | Real-time | Whale tracking |
| **Twitter/X** | Social sentiment | 15 seconds | Sentiment analysis |
| **Discord** | Community chatter | Real-time | FOMO detection |

### Life Dashboard (Future)

Beyond crypto, the dashboard will track:

| Category | Data Points | Integration Status |
|----------|-------------|-------------------|
| **Finance** | Bank accounts, investments, expenses | Planned |
| **Health** | Steps, sleep, heart rate | Planned |
| **Productivity** | Tasks, calendar, goals | In Progress |
| **Social** | Messages, contacts, events | Planned |
| **Home** | IoT devices, energy, security | Future |

### Tech Stack

- React 18 + Vite 5 + TailwindCSS
- Zustand for state management
- lightweight-charts for TradingView charts
- Modular CSS architecture
- WebSocket for real-time updates
- D3.js for custom visualizations

---

## 📱 Telegram Bot

**JARVIS Telegram Bot** delivers AI-powered trading signals:

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

### Commands

| Command | Description | Access |
|---------|-------------|--------|
| `/start` | Welcome message | Public |
| `/status` | Check API status | Public |
| `/trending` | Top 5 trending tokens | Public |
| `/price <addr>` | Token price lookup | Public |
| `/solprice` | Quick SOL price | Public |
| `/mcap <addr>` | Market cap/liquidity | Public |
| `/volume <addr>` | 24h volume | Public |
| `/chart <addr>` | Chart links | Public |
| `/liquidity <addr>` | Liquidity info | Public |
| `/age <addr>` | Token age | Public |
| `/summary <addr>` | Full overview | Public |
| `/gainers` | Top 10 price gainers | Public |
| `/losers` | Top 10 biggest losers | Public |
| `/newpairs` | New trading pairs | Public |
| `/signals` | Master Signal Report (Top 10) | Admin |
| `/analyze <token>` | Full analysis with Grok | Admin |
| `/digest` | Comprehensive digest | Admin |
| `/health` | System health status | Admin |
| `/flags` | View/toggle feature flags | Admin |
| `/config` | View/set configuration | Admin |
| `/score` | Treasury scorecard (P&L) | Admin |
| `/orders` | Active TP/SL orders | Admin |
| `/system` | Full system overview | Admin |
| `/wallet` | Treasury wallet info | Admin |
| `/logs` | Recent log entries | Admin |
| `/audit` | Audit log entries | Admin |

### Master Signal Report

Returns top 10 trending Solana tokens with:
- Clickable contract addresses
- Entry recommendations (scalp/day/long)
- Leverage suggestions (1x-5x)
- Grok AI sentiment analysis
- Risk scores (-100 to +100)
- Direct links (DexScreener, Birdeye, Solscan)

---

## 👛 Standalone Wallet

The wallet experience is designed to be **standalone** so people can safely try Jarvis without adopting the full OS.

**What this includes today:**
- User wallet creation/import/export
- Funding/withdrawals and balances
- Safe trading flows with confirmations
- Demo mode with explicit risk warnings

**Where it lives:**
- Telegram public bot (`tg_bot/`)
- Wallet services (`core/public_user_manager.py`, `core/wallet_service.py`)

See **docs/BUILD_STREAMLINE.md** for how this stays decoupled while the OS evolves.

---

## 🔌 Current Integrations

JARVIS integrates with a comprehensive ecosystem of services:

### Trading & DEXs

| Integration | Type | Status | Purpose |
|------------|------|--------|---------|
| **Jupiter** | DEX Aggregator | ✅ Active | Best price routing |
| **Raydium** | AMM | ✅ Active | Concentrated liquidity |
| **Orca** | AMM | ✅ Active | Whirlpool positions |
| **Meteora** | DLMM | ✅ Active | Dynamic liquidity |
| **Bags.fm** | Partner DEX | ✅ Active | 25% fee share |
| **Jito** | MEV | ✅ Active | Bundle protection |
| **Jupiter Perps** | Perpetuals | ✅ Active | Leverage trading |

### Data Providers

| Integration | Type | Status | Data |
|------------|------|--------|------|
| **BirdEye** | Token Data | ✅ Active | Prices, liquidity, holder |
| **DexScreener** | DEX Analytics | ✅ Active | Pairs, volume, chart |
| **GMGN** | Trending | ✅ Active | Hot tokens |
| **GeckoTerminal** | Pool Data | ✅ Active | Liquidity pools |
| **Helius** | RPC + Data | ✅ Active | On-chain events |
| **QuickNode** | RPC | ✅ Active | Backup RPC |

### AI Providers

| Provider | Model | Use Case | Priority |
|----------|-------|----------|----------|
| **Grok (xAI)** | Grok-2 | Trading analysis | 1 |
| **Claude** | Claude 3 | Code, complex reasoning | 2 |
| **Groq** | Llama 3.2 | Fast Q&A | 3 |
| **OpenRouter** | Various | Routing, Minimax | 4 |
| **Ollama** | Llama 3.2 | Offline fallback | 5 |

### Communication

| Platform | Type | Status | Features |
|----------|------|--------|----------|
| **Telegram** | Bot | ✅ Active | Signals, alerts, commands |
| **Discord** | Bot | ✅ Active | Community, webhooks |
| **Email** | SMTP | ✅ Active | Alert delivery |
| **Push** | Web Push | ✅ Active | Browser notifications |

### Payments

| Service | Type | Status | Purpose |
|---------|------|--------|---------|
| **Stripe** | Fiat Payments | ✅ Active | Credit purchases |
| **Solana Pay** | Crypto | 🚧 Planned | Direct SOL payments |

---

## 🚀 Future Platforms

### Planned Integrations

| Platform | Type | Timeline | Description |
|----------|------|----------|-------------|
| **iOS App** | Mobile | Q2 2026 | Native app with push |
| **Android App** | Mobile | Q2 2026 | Native app with push |
| **Chrome Extension** | Browser | Q2 2026 | Quick access overlay |
| **Slack** | Workplace | Q2 2026 | Team alerts |
| **WhatsApp** | Messaging | Q3 2026 | Mobile alerts |
| **Apple Watch** | Wearable | Q3 2026 | Wrist notifications |
| **AR/VR** | Immersive | 2027+ | Spatial trading |

### Life Automation Integrations

| Integration | Type | Timeline | Purpose |
|-------------|------|----------|---------|
| **Google Calendar** | Productivity | Q2 2026 | Schedule management |
| **Notion** | Workspace | Q2 2026 | Notes and tasks |
| **Todoist** | Tasks | Q2 2026 | Task management |
| **Gmail** | Email | Q3 2026 | Email automation |
| **Spotify** | Music | Q3 2026 | Mood-based music |
| **Apple Health** | Health | Q3 2026 | Health tracking |
| **Home Assistant** | IoT | Q4 2026 | Smart home control |

### Multi-Chain Expansion

| Chain | Timeline | DEXs | Status |
|-------|----------|------|--------|
| **Base** | Q2 2026 | Uniswap, Aerodrome | Planned |
| **Arbitrum** | Q3 2026 | Uniswap, Camelot | Planned |
| **Ethereum** | Q3 2026 | Uniswap, 1inch | Planned |
| **Sui** | Q4 2026 | Cetus, Turbos | Research |
| **Aptos** | Q4 2026 | Liquidswap | Research |

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
GET /api/treasury/reports/weekly
GET /api/treasury/reports/monthly
```

#### Data Platform (v3.8.0)
```bash
# Consent management
GET /api/consent/{wallet}
POST /api/consent/update
DELETE /api/data/request-deletion

# Data quality
GET /api/data/quality/{dataset_id}
GET /api/data/anomalies

# Aggregation
GET /api/data/aggregated/strategy/{strategy_id}
GET /api/data/aggregated/token/{token_address}
```

#### Experiments (v3.8.0)
```bash
POST /api/experiments/create
GET /api/experiments/{experiment_id}
POST /api/experiments/{experiment_id}/variant/{user_id}
GET /api/experiments/{experiment_id}/analysis
```

#### Monitoring (v3.8.0)
```bash
GET /api/health
GET /api/health/components
GET /api/alerts/active
POST /api/alerts/{alert_id}/acknowledge
POST /api/alerts/{alert_id}/resolve
```

#### Rewards Calculator (v3.8.0)
```bash
GET /api/rewards/calculate/{wallet}
GET /api/rewards/project/{wallet}
GET /api/rewards/tiers
GET /api/rewards/apy-range
```

#### Whale Tracking (v3.9.0)
```bash
GET /api/whales/activity/{token}
GET /api/whales/patterns/{token}
GET /api/whales/signals
POST /api/whales/configure
```

#### Copy Trading (v3.9.0)
```bash
GET /api/copy/leaders
GET /api/copy/leaders/{wallet}
POST /api/copy/follow
DELETE /api/copy/unfollow/{leader}
GET /api/copy/portfolio
```

#### Portfolio (v3.9.0)
```bash
GET /api/portfolio/{wallet}
GET /api/portfolio/{wallet}/performance
GET /api/portfolio/{wallet}/positions
GET /api/portfolio/{wallet}/transactions
```

#### DCA (v3.9.0)
```bash
GET /api/dca/schedules
POST /api/dca/schedules
PUT /api/dca/schedules/{id}
DELETE /api/dca/schedules/{id}
POST /api/dca/execute/{id}
```

#### Strategy Marketplace (v3.9.0)
```bash
GET /api/marketplace/strategies
GET /api/marketplace/strategies/{id}
POST /api/marketplace/strategies
POST /api/marketplace/subscribe/{id}
GET /api/marketplace/reviews/{strategy_id}
POST /api/marketplace/reviews
```

#### Users & Subscriptions (v3.9.0)
```bash
GET /api/users/{wallet}
POST /api/users/register
GET /api/subscriptions/tiers
POST /api/subscriptions/upgrade
GET /api/features/{wallet}
```

#### Developer API (v4.0.0)
```bash
# SDK Access
GET /api/developer/sdk/config
POST /api/developer/authenticate

# API Keys
GET /api/developer/keys
POST /api/developer/keys
DELETE /api/developer/keys/{key_id}
POST /api/developer/keys/{key_id}/rotate

# Webhooks
GET /api/developer/webhooks
POST /api/developer/webhooks
PUT /api/developer/webhooks/{id}
DELETE /api/developer/webhooks/{id}
POST /api/developer/webhooks/{id}/test

# OAuth
GET /api/oauth/authorize
POST /api/oauth/token
POST /api/oauth/revoke
```

#### Tax Reporting (v4.0.0)
```bash
GET /api/tax/transactions/{wallet}
GET /api/tax/gains/{wallet}
GET /api/tax/report/{wallet}/{year}
GET /api/tax/export/csv/{wallet}/{year}
GET /api/tax/form8949/{wallet}/{year}
```

---

## 🏗️ Architecture Deep Dive

### System Overview

```
┌────────────────────────────────────────────────────────────────────────────┐
│                           JARVIS ARCHITECTURE                               │
├────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                        PRESENTATION LAYER                            │   │
│  │  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐  │   │
│  │  │   Web   │  │Telegram │  │ Discord │  │  Voice  │  │   API   │  │   │
│  │  │Dashboard│  │   Bot   │  │   Bot   │  │   CLI   │  │  REST   │  │   │
│  │  └────┬────┘  └────┬────┘  └────┬────┘  └────┬────┘  └────┬────┘  │   │
│  └───────┼────────────┼────────────┼────────────┼────────────┼───────┘   │
│          │            │            │            │            │            │
│  ┌───────▼────────────▼────────────▼────────────▼────────────▼───────┐   │
│  │                         API GATEWAY                                │   │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐          │   │
│  │  │  Auth    │  │  Rate    │  │  Cache   │  │  Circuit │          │   │
│  │  │  Layer   │  │  Limiter │  │  Layer   │  │  Breaker │          │   │
│  │  └──────────┘  └──────────┘  └──────────┘  └──────────┘          │   │
│  └────────────────────────────┬───────────────────────────────────────┘   │
│                               │                                           │
│  ┌────────────────────────────▼───────────────────────────────────────┐   │
│  │                          CORE ENGINE                                │   │
│  │                                                                     │   │
│  │  ┌───────────┐  ┌───────────┐  ┌───────────┐  ┌───────────┐      │   │
│  │  │  Trading  │  │  Signal   │  │  Portfolio│  │   User    │      │   │
│  │  │  Engine   │  │  Fusion   │  │  Manager  │  │  Manager  │      │   │
│  │  └───────────┘  └───────────┘  └───────────┘  └───────────┘      │   │
│  │                                                                     │   │
│  │  ┌───────────┐  ┌───────────┐  ┌───────────┐  ┌───────────┐      │   │
│  │  │  Whale    │  │  Treasury │  │  Staking  │  │  Credits  │      │   │
│  │  │  Tracker  │  │  Manager  │  │  System   │  │  System   │      │   │
│  │  └───────────┘  └───────────┘  └───────────┘  └───────────┘      │   │
│  └────────────────────────────┬───────────────────────────────────────┘   │
│                               │                                           │
│  ┌────────────────────────────▼───────────────────────────────────────┐   │
│  │                       INTELLIGENCE LAYER                            │   │
│  │  ┌───────────┐  ┌───────────┐  ┌───────────┐  ┌───────────┐      │   │
│  │  │   Model   │  │Conversation│ │  Self-    │  │  Memory   │      │   │
│  │  │   Router  │  │  Engine   │  │ Evolution │  │  System   │      │   │
│  │  └───────────┘  └───────────┘  └───────────┘  └───────────┘      │   │
│  └────────────────────────────┬───────────────────────────────────────┘   │
│                               │                                           │
│  ┌────────────────────────────▼───────────────────────────────────────┐   │
│  │                        DATA LAYER                                   │   │
│  │  ┌───────────┐  ┌───────────┐  ┌───────────┐  ┌───────────┐      │   │
│  │  │ PostgreSQL│  │   Redis   │  │  SQLite   │  │  File     │      │   │
│  │  │  (State)  │  │  (Cache)  │  │  (Memory) │  │  Storage  │      │   │
│  │  └───────────┘  └───────────┘  └───────────┘  └───────────┘      │   │
│  └────────────────────────────────────────────────────────────────────┘   │
│                                                                           │
│  ┌────────────────────────────────────────────────────────────────────┐   │
│  │                      EXTERNAL SERVICES                              │   │
│  │  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐     │   │
│  │  │  DEXs   │ │   AI    │ │  Data   │ │ Payment │ │  RPC    │     │   │
│  │  │ Jupiter │ │ Grok    │ │ BirdEye │ │ Stripe  │ │ Helius  │     │   │
│  │  │ Raydium │ │ Claude  │ │ GMGN    │ │         │ │QuickNode│     │   │
│  │  └─────────┘ └─────────┘ └─────────┘ └─────────┘ └─────────┘     │   │
│  └────────────────────────────────────────────────────────────────────┘   │
└────────────────────────────────────────────────────────────────────────────┘
```

### Module Dependency Graph

```
                    ┌──────────────────┐
                    │      CLI         │
                    │  bin/lifeos      │
                    └────────┬─────────┘
                             │
              ┌──────────────┼──────────────┐
              │              │              │
     ┌────────▼────┐  ┌──────▼─────┐  ┌─────▼──────┐
     │   Trading   │  │   Voice    │  │   Web      │
     │   Engine    │  │   Control  │  │   API      │
     └──────┬──────┘  └──────┬─────┘  └──────┬─────┘
            │                │               │
            └────────────────┼───────────────┘
                             │
                    ┌────────▼────────┐
                    │    Core JARVIS  │
                    │  core/jarvis.py │
                    └────────┬────────┘
                             │
     ┌─────────────┬─────────┼─────────┬─────────────┐
     │             │         │         │             │
┌────▼────┐ ┌──────▼──┐ ┌────▼────┐ ┌──▼────┐ ┌──────▼──────┐
│ Memory  │ │ Guardian│ │ Wallet  │ │ Model │ │ Self-Improve│
│ System  │ │ Safety  │ │ Manager │ │ Router│ │   Engine    │
└─────────┘ └─────────┘ └─────────┘ └───────┘ └─────────────┘
```

### Trading Flow

```
User Request → "Buy $100 of SOL"
       │
       ▼
┌──────────────────┐
│ Intent Detection │
│  (NLU Layer)     │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ Guardian Check   │  ◄─── Is user authorized?
│  (Safety Layer)  │  ◄─── Within risk limits?
└────────┬─────────┘  ◄─── Not blacklisted token?
         │
         ▼
┌──────────────────┐
│ Signal Fusion    │  ◄─── Combine signals from all sources
│  (Analysis)      │  ◄─── Generate confidence score
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ Position Sizer   │  ◄─── Calculate optimal size
│  (Risk Layer)    │  ◄─── Apply Kelly Criterion
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ DEX Router       │  ◄─── Find best route
│  (Execution)     │  ◄─── Jupiter → Raydium → Orca
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ Jito Bundle      │  ◄─── MEV protection
│  (Settlement)    │  ◄─── Transaction submission
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ Post-Trade       │  ◄─── Record in journal
│  (Analytics)     │  ◄─── Update portfolio
└──────────────────┘  ◄─── Notify user
```

## 🧠 MCP & Semantic Memory System

JARVIS leverages 18 Model Context Protocols (MCPs) for enterprise-grade memory, code analysis, and research capabilities.

### Memory Architecture

```
PostgreSQL (continuous_claude)
    ↓ [100+ semantic learnings with BGE embeddings]
    ↓
MemoryImporter (auto_import.py)
    ├─ Full-text search indexing
    ├─ Confidence-based ranking
    └─ Topic categorization
    ↓
Local Storage
    ├─ SQLite indexed database (zero-latency search)
    ├─ JSONL format (MCP memory server)
    └─ Session-level access via /recall
```

### Available MCPs

**Development & Code Analysis:**
| MCP | Purpose | Speed |
|-----|---------|-------|
| **ast-grep** | Pattern matching & refactoring | 20x faster than grep |
| **git** | Repository operations | Native |
| **github** | PR reviews & issue tracking | GitHub API |

**Knowledge & Documentation:**
| MCP | Purpose |
|-----|---------|
| **nia** | SDK/API docs (Twitter, Telegram, Jupiter) |
| **brave-search** | Web search |
| **youtube-transcript** | Video context extraction |

**Data Extraction & Research:**
| MCP | Purpose | Use Case |
|-----|---------|----------|
| **firecrawl** | Website scraping | Market data, token research |
| **perplexity** | Real-time web research | Current analysis |
| **postgres** | Database queries | Semantic memory + trading history |
| **sqlite** | Local queries | Session data |

**Infrastructure:**
| MCP | Purpose |
|-----|---------|
| **docker** | Container management |
| **puppeteer** | Browser automation |
| **fetch** | HTTP operations |
| **filesystem** | File navigation |
| **sequential-thinking** | Reasoning with chain-of-thought |

**Bot Integrations:**
| MCP | Purpose |
|-----|---------|
| **twitter** | X/Twitter API |
| **telegram** | Telegram bot framework |
| **solana** | Blockchain operations |
| **memory** | Session-level memory (JSONL) |

### Using the Memory System

**Quick Start:**
```bash
# Import all learnings from PostgreSQL
python core/memory/auto_import.py

# Query in Python
from core.memory.auto_import import MemoryImporter
importer = MemoryImporter()
results = importer.search_imported_memories("trading strategy", limit=10)

# Query in Claude Code
/recall "search terms for your task"
```

**Available Queries:**

Trading & Treasury:
```bash
# Past trading strategies
importer.search_imported_memories("trading strategy", limit=10)

# Bug fixes
importer.get_recent_by_type("ERROR_FIX", limit=20)
```

X Bot & Social:
```bash
# Circuit breaker patterns
importer.search_imported_memories("circuit breaker x twitter", limit=10)

# Sentiment scoring methods
importer.search_imported_memories("grok sentiment score", limit=10)
```

Configuration & Architecture:
```bash
# System decisions
importer.get_recent_by_type("ARCHITECTURAL_DECISION", limit=20)

# Config best practices
importer.search_imported_memories("config yaml environment", limit=10)
```

**Memory Statistics:**
```python
stats = importer.get_memory_stats()
# Returns: total_entries, by_type, by_confidence, topics, most_recent
```

### Learning Types

| Type | Purpose | Example |
|------|---------|---------|
| `WORKING_SOLUTION` | Fixes that work | "How we fixed the X bot spam loop" |
| `ERROR_FIX` | Bug solutions | "Bare except cleanup" |
| `FAILED_APPROACH` | What didn't work | "Approaches that failed for state backup" |
| `ARCHITECTURAL_DECISION` | System design choices | "Why PostgreSQL for memory" |
| `CODEBASE_PATTERN` | Reusable patterns | "Event bus handler patterns" |

### Configuration

**Database Connection:**
```bash
# .env
DATABASE_URL=postgresql://claude:claude_dev@localhost:5432/continuous_claude
SQLITE_DB_PATH=./data/jarvis.db
```

**Optional API Keys:**
```bash
# GitHub (for code review workflows)
GITHUB_TOKEN=ghp_...

# Firecrawl (for web scraping)
FIRECRAWL_API_KEY=...

# Perplexity (for real-time research)
PERPLEXITY_API_KEY=...
```

### Documentation

- **[MEMORY_QUERY_GUIDE.md](MEMORY_QUERY_GUIDE.md)** - 50+ query examples by task
- **[MCP_SETUP_SUMMARY.md](MCP_SETUP_SUMMARY.md)** - Complete MCP documentation
- **[core/memory/auto_import.py](core/memory/auto_import.py)** - Memory import system implementation

### Verification

```bash
# Verify all systems are configured
python scripts/verify_mcp_setup.py

# Expected output:
# [PASS] [MCP] Configuration - 18 MCPs configured
# [PASS] [ENV] Environment Variables - .env configured
# [PASS] [DB] PostgreSQL Connection - Connected to continuous_claude
# [PASS] [MEMORY] Memory System - MemoryImporter initialized
# [PASS] [DOCS] Documentation - All guides present
```

---

### Security Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                      SECURITY LAYERS                              │
├──────────────────────────────────────────────────────────────────┤
│                                                                   │
│  Layer 1: Network                                                 │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │  WAF  │  DDoS Protection  │  Rate Limiting  │  SSL/TLS    │  │
│  └────────────────────────────────────────────────────────────┘  │
│                                                                   │
│  Layer 2: Authentication                                          │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │  Wallet Signatures  │  API Keys  │  OAuth 2.0 + PKCE      │  │
│  └────────────────────────────────────────────────────────────┘  │
│                                                                   │
│  Layer 3: Authorization                                           │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │  Scopes  │  Feature Flags  │  Subscription Tiers          │  │
│  └────────────────────────────────────────────────────────────┘  │
│                                                                   │
│  Layer 4: Guardian (Runtime Safety)                               │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │  Action Validation  │  Risk Limits  │  Circuit Breakers   │  │
│  └────────────────────────────────────────────────────────────┘  │
│                                                                   │
│  Layer 5: Data Protection                                         │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │  Encryption at Rest  │  Anonymization  │  Audit Logging   │  │
│  └────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────┘
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

## Change History & Traceability

This README is the capability index; the authoritative release log lives in `CHANGELOG.md`.

- Release summaries: `CHANGELOG.md`
- Full commit ledger: `git log --oneline --decorate`
- File-level diffs between versions: `git diff tag1..tag2`
- Architecture decisions and audits: `docs/`

---

## 🗺️ Roadmap

### Completed ✓

**v4.1.3 - Enhanced UI Components & Context System (January 2026)**
- [x] Enhanced conversation context retention with key facts extraction
- [x] Automatic conversation summarization for long-term memory
- [x] Voice and trading WebSocket endpoints for real-time updates
- [x] useVoiceWebSocket React hook with auto-reconnect
- [x] Loading states for PositionCard, StatsGrid, and MarketIndicators
- [x] ErrorBoundary component with HOC and hook utilities
- [x] ConnectionStatus component with multiple variants
- [x] Notification/Toast system with provider and hook
- [x] Trade confirmation dialogs with countdown timer
- [x] Slippage control component with presets
- [x] Breadcrumb navigation with auto-generation
- [x] Collapsible sections for settings pages
- [x] Market indicators API endpoint (/api/market/indicators)

**v4.1.2 - Cross-Platform & UI/UX Improvements (January 2026)**
- [x] Full Windows/Linux cross-platform support for computer control module
- [x] Fixed WinError 2 spam from macOS-specific commands (osascript, pbpaste, etc.)
- [x] Cross-platform notifications using native APIs (Windows toast, macOS notification center)
- [x] Cross-platform dialogs using tkinter fallback on Windows/Linux
- [x] Enhanced health check API with voice system status and database checks
- [x] Standardized API error responses with error codes (VOICE_xxx, TRADE_xxx, etc.)
- [x] Global error handlers for Flask and FastAPI endpoints
- [x] Voice dependencies installed: faster-whisper, openwakeword
- [x] Frontend: ThemeToggle added to top navigation
- [x] Frontend: Keyboard shortcuts modal with full shortcut documentation
- [x] Frontend: Enhanced VoiceOrb with real-time audio visualization and animated rings
- [x] Frontend: Extended skeleton loading components (Position, Chart, Stats, Table, Message)

**v4.1.1 - Daemon Stability & Module Fixes (January 2026)**
- [x] Fixed `core/memory` module - Added `get_recent_entries()` and `summarize_entries()` functions
- [x] Fixed `core/guardian` module - Added `Guardian` class alias for backward compatibility
- [x] Fixed `core/context_manager` module - Added `ContextManager` class wrapper
- [x] Fixed `core/providers` module - Added `Providers` class wrapper
- [x] Fixed `core/evolution` module - Added `Evolution` class wrapper
- [x] Fixed `core/autonomous_restart` module - Added `AutonomousRestartManager` alias
- [x] Fixed `core/autonomous_controller` - Added missing `running` attribute
- [x] All 11 daemon components now start successfully
- [x] Installed missing dependencies: `pyautogui`, `groq`
- [x] Enhanced Telegram bot with sentiment reporting and ape trading buttons
- [x] Treasury trading improvements with position management
- [x] Buy tracker enhancements with sentiment analysis

**v4.1.0 - Full System Audit & Enhancement (NEW)**
- [x] Treasury Trading System with AES-256 encrypted wallets
- [x] Jupiter Aggregator integration for Solana swaps
- [x] Telegram trading dashboard with live buttons (/dashboard, /trade, /positions)
- [x] Take profit/stop loss by sentiment grade (A=30%/10%, B+=20%/8%)
- [x] Grok-3 AI integration (content, images, sentiment)
- [x] X.com sentiment analysis with budget controls ($3/day cap)
- [x] Whale tracking with alert thresholds ($10K/$50K/$100K)
- [x] Voice Bible with Morgan Freeman preset (edge-tts)
- [x] 6 TTS engines (Edge-TTS, Piper, macOS say, OpenAI, XTTS, Coqui)
- [x] 5 STT engines (Faster Whisper, Gemini, OpenAI, Google, Sphinx)
- [x] Wake word detection via openwakeword
- [x] Autonomous Agent with 7 tools and self-healing
- [x] Circular logic detection and prevention (CycleGovernor)
- [x] Autonomous Researcher for model discovery
- [x] Twitter/X OAuth 2.0 for @Jarvis_lifeos
- [x] Sentiment Engine at 84.6% accuracy
- [x] Security testing framework (22 unit tests, 9 penetration tests)

**v4.0.0 - Developer Platform & Vision**
- [x] Developer API SDK with auto-auth and retry
- [x] API key management with scopes and rate limits
- [x] Webhook system with signed payloads and retry logic
- [x] OAuth 2.0 provider with PKCE support
- [x] Tax reporting with FIFO/LIFO/HIFO cost basis
- [x] IRS Form 8949 generation
- [x] API Proxy with circuit breaker pattern
- [x] Request caching with LRU eviction
- [x] Load balancing (round-robin, weighted, failover, latency)
- [x] Trading journal with emotional state tracking
- [x] Comprehensive README overhaul with vision document
- [x] Architecture deep dive documentation
- [x] Cross-App Logic Loop documentation
- [x] Bot Online/Offline mode system
- [x] Conversation Engine framework
- [x] Intelligent Model Routing documentation

**v3.9.0 - Social Trading & Automation**
- [x] Multi-channel alert delivery (Discord, Telegram, Email, Push, Webhook)
- [x] Whale tracking with pattern analysis (accumulation, distribution)
- [x] Signal fusion system with dynamic weight adjustment
- [x] Position sizing (Kelly Criterion, volatility-adjusted, hybrid)
- [x] Copy trading infrastructure (DISABLED pending audit)
- [x] Leader/follower system with tier rankings
- [x] Portfolio tracker with P&L and performance metrics
- [x] User account system (wallet-based, NO KYC)
- [x] Subscription tiers (Free → Enterprise)
- [x] Feature flags with percentage rollout
- [x] DCA automation with smart adjustments (DISABLED pending audit)
- [x] Strategy marketplace with reviews

**v3.8.0 - Treasury & Data Platform**
- [x] Squads Protocol multisig integration for treasury
- [x] Strategy Manager framework with YAML configuration
- [x] Treasury transparency dashboard with WebSocket updates
- [x] GDPR-compliant data anonymization (k-anonymity, hashing)
- [x] Consent-based data collection system
- [x] Data deletion with audit trail (GDPR compliance)
- [x] Retention policies with automated cleanup
- [x] Data quality metrics (completeness, accuracy, freshness)
- [x] Statistical anomaly detection (z-score, spike detection)
- [x] Trade outcome aggregation by strategy/token/market
- [x] Optuna-based strategy parameter optimization
- [x] Walk-forward backtesting framework
- [x] A/B testing framework with statistical analysis
- [x] Wallet-based verification (NO KYC required)
- [x] On-chain reputation scoring system
- [x] Data marketplace packaging and dynamic pricing
- [x] Revenue distribution to data contributors
- [x] System health monitoring dashboard
- [x] Alert management (Slack/Discord notifications)
- [x] Treasury performance reports (weekly/monthly)
- [x] Tiered staking rewards calculator with projections

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
- [x] 1108+ tests passing

### In Progress 🚧

- [ ] Hyperparameter tuning via Optuna
- [ ] Walk-forward validation
- [ ] Cross-chain MEV (Flashbots for Ethereum)
- [ ] ML model retraining pipeline

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

## 👥 Community

### Join the Community

| Platform | Link | Description |
|----------|------|-------------|
| **Discord** | Coming Soon | Trading signals, support, dev chat |
| **Telegram** | Coming Soon | Alerts and announcements |
| **Twitter/X** | Coming Soon | Updates and alpha |
| **GitHub** | [Issues](https://github.com/Matt-Aurora-Ventures/Jarvis/issues) | Bug reports, feature requests |

### Community Guidelines

1. **Be Respectful**: Treat everyone with respect
2. **No Financial Advice**: JARVIS is a tool, not a financial advisor
3. **No Spam**: Avoid excessive self-promotion
4. **Report Bugs**: Help improve JARVIS by reporting issues
5. **Share Ideas**: Feature requests are welcome

### Contributor Recognition

Top contributors get:
- Early access to new features
- Recognition in release notes
- Exclusive Discord role
- Direct access to development team

---

## ❓ FAQ

### General Questions

**Q: What is JARVIS?**
A: JARVIS is an autonomous AI trading partner and life automation system. It starts with crypto trading on Solana and expands to general life automation.

**Q: Is JARVIS free to use?**
A: Yes! The core features are free. Premium features are available through credit purchases or $KR8TIV staking.

**Q: Do I need crypto knowledge?**
A: No. You can pay with credit card and JARVIS handles all the crypto complexity.

### Trading Questions

**Q: How does JARVIS make trading decisions?**
A: JARVIS uses 81+ trading strategies combining technical analysis, on-chain data, whale tracking, social sentiment, and ML predictions. All signals are fused into a confidence score.

**Q: Is my money safe?**
A: JARVIS uses multiple safety layers:
- Circuit breakers for automatic trading halt
- Position size limits
- Stop losses on all trades
- Guardian system that blocks dangerous operations
- Your private keys never leave your device

**Q: Can JARVIS lose money?**
A: Yes. Trading involves risk. JARVIS minimizes risk through sophisticated risk management, but no trading system is 100% profitable.

**Q: Does JARVIS trade with real money automatically?**
A: Only if you enable autonomous mode. By default, JARVIS suggests trades and waits for your approval. Copy Trading and DCA are DISABLED pending security audit.

### Technical Questions

**Q: What AI models does JARVIS use?**
A: JARVIS uses multiple AI providers:
- Grok (xAI) for trading analysis
- Claude for code and reasoning
- Groq (Llama 3.2) for fast responses
- Ollama for offline fallback

**Q: Can I run JARVIS offline?**
A: Yes! JARVIS has an offline mode with local LLM (Ollama) and cached market data for basic functionality.

**Q: What platforms does JARVIS support?**
A: Currently: Web Dashboard, Telegram Bot, Discord Bot, Voice CLI. Coming soon: iOS, Android, Chrome Extension.

### Staking Questions

**Q: What is $KR8TIV?**
A: $KR8TIV is the native utility token powering the JARVIS ecosystem. Stake it to earn SOL from trading fees.

**Q: How do I earn rewards?**
A: Stake $KR8TIV tokens and earn weekly SOL distributions. Longer staking = higher multipliers (up to 2.5x).

**Q: Is there a lock-up period?**
A: There's a 3-day cooldown after requesting unstake to prevent gaming the system.

### Privacy Questions

**Q: Does JARVIS collect my data?**
A: Only with your consent. We offer 3 tiers:
- TIER_0: No data collected
- TIER_1: Anonymous usage for platform improvement
- TIER_2: Trading patterns (earn from data marketplace)

**Q: Is my wallet address public?**
A: Your wallet address is never publicly associated with your trades. All data is anonymized.

**Q: Can I delete my data?**
A: Yes. You can request complete data deletion at any time (GDPR compliant).

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

### Local Claude Code with Ollama (Free + Offline)

JARVIS can be paired with Claude Code running against local Ollama models (no cloud API calls). This is ideal for coding workflows that must stay fully offline.

1. Install Ollama (0.14.0+) and pull a coding model:
   ```bash
   ollama pull qwen3-coder
   ```
2. Start Ollama:
   ```bash
   ollama serve
   ```
3. Install Claude Code, then point it at Ollama's Anthropic-compatible endpoint:
   ```bash
   export ANTHROPIC_API_KEY=ollama
   export ANTHROPIC_BASE_URL=http://localhost:11434/v1
   ```
4. Run Claude Code against the local model:
   ```bash
   claude --model qwen3-coder
   ```

**Tip:** If you also want JARVIS to use the same local model, set `OLLAMA_URL=http://localhost:11434` and `OLLAMA_MODEL=qwen3-coder` in your `.env`. JARVIS also honors `ANTHROPIC_BASE_URL` to route Claude calls (bots, tools, and codegen) through Ollama. Remove `ANTHROPIC_BASE_URL` to return Claude Code to the hosted Anthropic API.

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

## Third-Party Credits

This project integrates components inspired by and/or derived from:

- **AI-Researcher** by HKUDS (Data Intelligence Lab @ HKU)
  - Repository: https://github.com/HKUDS/AI-Researcher
  - Paper: https://arxiv.org/abs/2505.18705
  - License: MIT

We are grateful to the authors and contributors for open-sourcing their work.
Our integration adds a Jarvis-specific orchestration layer, artifact registry, and safety/compliance gates on top of the upstream research automation pipeline.

---

<p align="center">
  <b>Built by <a href="https://github.com/Matt-Aurora-Ventures">Matt Aurora Ventures</a></b><br>
  <i>"The best AI is one that makes you money while you sleep."</i>
</p>
