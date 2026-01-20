# Changelog

All notable changes to Jarvis (LifeOS) will be documented in this file.

---

# [4.6.1] - 2026-01-20

### Added
- Multi-level cache manager with memory/file/redis tiers, TTLs, LRU eviction, invalidation, stats, and request deduplication (`core/caching/cache_manager.py`).
- Query optimization toolkit for batching, request coalescing, connection pooling, and deduplicated fetches (`core/data/query_optimizer.py`).
- Comprehensive audit logger with hash-chain integrity and automatic secret redaction (`core/security/comprehensive_audit_logger.py`).
- Enhanced rate limiter with IP/user scopes, DDoS detection, and auto-blacklisting (`core/security/enhanced_rate_limiter.py`).
- Enhanced secrets manager with encryption, versioned rotation, and access auditing (`core/security/enhanced_secrets_manager.py`).
- Scam detector for pump-and-dump, wash trading, and coordinated manipulation patterns (`core/security/scam_detector.py`).
- Transaction verifier for contract authenticity, liquidity checks, and risk flags (`core/security/transaction_verifier.py`).
- Social toolkit configs for visuals, viral hooks, and trending logic (`core/social/config.py`).
- Image generator for sentiment/price/portfolio charts for X posts (`core/social/image_generator.py`).
- Trending token tracker with cached exchange feeds and change detection (`core/social/trending_tracker.py`).
- Viral optimizer with hashtags, hooks, and timing recommendations (`core/social/viral_optimizer.py`).
- Telegram command framework with parsing, permissions, rate limits, and history (`tg_bot/ui/command_framework.py`).
- Interactive Telegram menus for portfolio/trading/settings navigation (`tg_bot/ui/interactive_menus.py`).
- Watchlist manager with persistence and price alerts (`tg_bot/ui/watchlist_manager.py`).
- Session manager for drill-down UI state + user preferences with persistence (`tg_bot/sessions/session_manager.py`).
- Matplotlib dependency for Telegram chart rendering (`tg_bot/requirements.txt`, `requirements.txt`).
- PyNaCl for encrypted treasury keypair support (`requirements.txt`).
- X duplicate tuning via `X_DUPLICATE_DETECTION_HOURS` + `X_DUPLICATE_SIMILARITY` (`bots/twitter/autonomous_engine.py`).
- Telegram JobQueue extras for scheduled digests (`tg_bot/requirements.txt`).
- Unit tests for caching/query optimizer and new security/social modules (`tests/unit`, `tests/performance`, `tests/unit/security`, `tests/unit/social`).
- Telegram UI test coverage for commands, menus, inline buttons, and watchlists (`tests/unit/test_tg_ui_*`).
- Reliability audit notes and incident writeups (`audit_reports/`).

### Changed
- X autonomous posting now respects `X_BOT_ENABLED` kill switch (`bots/twitter/autonomous_engine.py`).
- Sentiment poster honors `X_BOT_ENABLED` gate (`bots/twitter/sentiment_poster.py`).
- X read endpoints back off on 401/403 to reduce log noise and protect limits (`bots/twitter/twitter_client.py`).
- X posting length now honors `X_MAX_TWEET_LENGTH`/`TWITTER_MAX_TWEET_LENGTH` (default 280) (`bots/twitter/twitter_client.py`).
- Jarvis voice validation + Twitter compliance now respect `X_MAX_TWEET_LENGTH` (`core/jarvis_voice_bible.py`, `core/social/twitter_compliance.py`).
- Treasury trading now blocks `open_position` when kill switch is enabled (`bots/treasury/trading.py`).
- Treasury manager + trade adapters now honor kill switch, emergency shutdown, and `LIVE_TRADING_ENABLED` (`core/treasury/manager.py`, `core/trading/batch_processor.py`, `core/trading/bags_adapter.py`).
- `tg_bot/sessions` is now tracked to prevent missing-module deploys (`.gitignore`, `tg_bot/sessions`).
- Desktop-only audio/wakeword deps are now Windows-only to avoid Linux install failures (`requirements.txt`).

### Fixed
- Telegram analytics handler import error (missing `is_admin`) to prevent bot crash (`tg_bot/bot_core.py`).

---

# [4.6.0] - 2026-01-14

### 🚀 **MASSIVE RELEASE: Autonomous Intelligence & Full-Stack Expansion**

The largest single release in JARVIS history. 7,750+ lines of new code across 105 new files, transforming JARVIS from a trading assistant into a fully autonomous AI system with comprehensive frontend components.

---

## 🧠 Core Autonomy System

### Action Executor (`core/autonomy/action_executor.py`) - **NEW**
The crown jewel of this release. Bridges observation/learning to actual execution:
- **ExecutableAction dataclass** with priority queuing, retry logic, delayed execution
- **9 Action Types**: POST_TWEET, SEND_ALERT, UPDATE_CONFIG, RESEARCH_TOPIC, TRADE_SIGNAL, CREATE_CONTENT, ENGAGEMENT, SHELL_COMMAND, MEMORY_UPDATE
- **Hypothesis-to-Action conversion** from ObservationalDaemon
- **Goal-to-Action conversion** from MemoryDrivenBehaviorEngine
- **Persistent queue** with disk storage (`data/execution/`)
- **Execution logging** with JSONL audit trail
- **Cooldown management** (30s minimum between executions)
- **Pluggable handlers** for custom action types

### News Detection System (`core/autonomy/news_detector.py`) - **NEW**
Real-time crypto news analysis with AI-powered filtering:
- Aggregates from CryptoPanic, LunarCrush, and social feeds
- Sentiment scoring with bullish/bearish classification
- Breaking news alerts with priority routing
- Token mention extraction and trending detection

### Alpha Signal Analyzer - **ENHANCED**
- Improved signal confidence scoring
- Better false positive filtering
- Integration with enhanced market data

---

## 📊 Enhanced Market Intelligence

### Enhanced Market Data (`core/enhanced_market_data.py`) - **NEW** (708 lines)
Comprehensive multi-source market aggregation:
- **7+ data sources**: CoinGecko, DeFiLlama, CoinMarketCap fallbacks
- **Token metrics**: Price, volume, market cap, FDV, circulating supply
- **DeFi metrics**: TVL, protocol rankings, yield opportunities
- **Sentiment integration**: Fear & Greed Index, social metrics
- **Caching layer** with TTL-based invalidation
- **Rate limiting** per source with backoff

### Resilient Price Fetcher (`core/price/resilient_fetcher.py`) - **NEW** (296 lines)
Production-grade price fetching with fault tolerance:
- Multiple fallback APIs (Jupiter, Raydium, BirdEye, DexScreener)
- Circuit breaker pattern for failed sources
- Weighted price averaging across sources
- Health scoring per provider
- Auto-recovery for degraded sources

### Whale Tracker (`core/whale_tracker.py`) - **NEW** (91 lines)
Large transaction monitoring:
- Configurable whale threshold detection
- Real-time wallet movement alerts
- Integration with trading signals

### Price Alerts System (`core/price_alerts.py`) - **NEW**
User-configurable price notifications:
- Above/below threshold triggers
- Percentage change alerts
- Multi-channel delivery (Telegram, desktop, webhook)

### Webhook Manager (`core/webhook_manager.py`) - **NEW**
External integration hub:
- Inbound webhook receivers
- Outbound webhook dispatching
- Discord/Slack/custom endpoint support
- Retry logic with exponential backoff

---

## 🐦 X (Twitter) Bot - Major Expansion

### Autonomous Engine (`bots/twitter/autonomous_engine.py`) - **+1,200 lines**
Massive enhancement to the autonomous posting system:
- **Quote Tweet Generation**: Smart quote selection with engagement scoring
- **Thread Generation**: Multi-tweet narrative building
- **Trend Analysis Integration**: Posts aligned with trending topics
- **Content Categories**: market_update, trending_token, agentic_thought, hourly_update, quote_tweet, thread
- **Engagement Tracking**: Metrics collection for posted content
- **Dynamic Interval Adjustment**: Based on engagement performance
- **Media Attachment Support**: Charts, images with posts

### Trend Analyzer (`bots/twitter/trend_analyzer.py`) - **NEW**
Real-time trend detection:
- Twitter trending topics API integration
- Crypto-specific trend filtering
- Trend velocity scoring
- Best posting time recommendations

### X Claude CLI Handler (`bots/twitter/x_claude_cli_handler.py`) - **NEW**
Claude integration for tweet generation:
- Direct Claude API for content creation
- Personality-consistent tweet drafting
- Content safety filtering

### Jarvis Voice (`bots/twitter/jarvis_voice.py`) - **+215 lines**
Enhanced voice/personality system:
- Mood-based tweet variation
- Time-of-day personality shifts
- Market condition tone adaptation

### Grok Client (`bots/twitter/grok_client.py`) - **ENHANCED**
- **State persistence** for daily image count (`data/grok_state.json`)
- Improved rate limit handling
- Better error recovery

---

## 🤖 Bot Supervisor & Resilience

### Bot Supervisor (`bots/supervisor.py`) - **NEW** (441 lines)
Production-grade bot orchestration:
- **Process Management**: Start/stop/restart individual bots
- **Health Monitoring**: Per-bot health checks
- **Auto-Recovery**: Crashed bot restart with backoff
- **Resource Limits**: Memory/CPU caps per bot
- **Graceful Shutdown**: Clean termination handling
- **Status Dashboard**: Real-time bot status

### Health Endpoint (`bots/health_endpoint.py`) - **NEW** (154 lines)
HTTP health check server:
- `/health` - Overall system health
- `/ready` - Readiness probe (K8s compatible)
- `/live` - Liveness probe
- Per-component health breakdown

---

## 💰 Trading System Improvements

### Sentiment Report (`bots/buy_tracker/sentiment_report.py`) - **+769 lines**
Revolutionary sentiment-driven reporting:
- **JARVIS AI Analysis**: Claude-powered market interpretation
- **Multi-asset coverage**: Not just Solana, full crypto market
- **Direct buy buttons**: One-click trading from reports
- **Confidence scoring**: Per-signal reliability metrics
- **Historical tracking**: Sentiment trend analysis

### Ape Buttons (`bots/buy_tracker/ape_buttons.py`) - **+80 lines**
Quick-trade button system:
- Pre-configured trade sizes
- Risk-adjusted position sizing
- Confirmation dialogs

### Jupiter Integration (`bots/treasury/jupiter.py`) - **+100 lines**
Enhanced DEX aggregation:
- Better route optimization
- Slippage protection improvements
- Transaction retry logic

### Treasury Trading (`bots/treasury/trading.py`) - **+175 lines**
Core trading logic improvements:
- Position sizing refinements
- Risk management enhancements
- Order execution optimization

### Sentiment Trading (`core/sentiment_trading.py`) - **+434 lines**
AI-driven trading signals:
- Multi-source sentiment aggregation
- Signal confidence scoring
- Automated trade execution based on sentiment

---

## 📱 Telegram Bot - Major Upgrade

### Main Bot (`tg_bot/bot.py`) - **+674 lines**
Massive functionality expansion:
- **New commands**: 20+ new admin/user commands
- **Inline keyboards**: Interactive button menus everywhere
- **Claude integration**: AI-powered chat responses
- **Trading UI**: Buy/sell directly from Telegram
- **Alert management**: Configure alerts via chat
- **System monitoring**: Bot status dashboards

### Claude CLI Handler (`tg_bot/services/claude_cli_handler.py`) - **NEW**
Direct Claude integration for Telegram:
- Natural language processing for commands
- Context-aware responses
- Multi-turn conversation support

### Chat Responder (`tg_bot/services/chat_responder.py`) - **+262 lines**
Enhanced conversation handling:
- Better context retention
- Personality-consistent responses
- Error handling improvements

### Signal Service (`tg_bot/services/signal_service.py`) - **+89 lines**
Trading signal delivery:
- Signal formatting for Telegram
- Priority-based delivery
- Read receipt tracking

---

## 🎨 Frontend - 70+ New Components

### Trading Components
| Component | Description |
|-----------|-------------|
| `AISuggestions.jsx` | AI-powered trade recommendations |
| `BacktestDashboard.jsx` | Historical strategy testing UI |
| `LiveMarketFeed.jsx` | Real-time market data stream |
| `LiveTrades.jsx` | Recent trade activity |
| `MarketDepth.jsx` | Order book visualization |
| `OrderPanel.jsx` | Trade execution interface |
| `StrategyBuilder.jsx` | Visual strategy creation |
| `TokenWatchlist.jsx` | Tracked tokens dashboard |
| `TradingChart.jsx` | Advanced charting with indicators |

### Analytics Components
| Component | Description |
|-----------|-------------|
| `analytics/` | Performance dashboards, metrics |
| `portfolio/` | Holdings overview, allocation |
| `profit/` | P&L tracking, ROI calculations |
| `risk/` | Risk assessment, exposure |
| `roi/` | Return on investment analysis |

### DeFi Components
| Component | Description |
|-----------|-------------|
| `airdrop/` | Airdrop tracking and claiming |
| `bridge/` | Cross-chain bridging UI |
| `defi/` | DeFi protocol dashboards |
| `lending/` | Lending protocol interfaces |
| `liquidity/` | LP position management |
| `staking/` | Staking calculators, dashboards |
| `yield/` | Yield farming opportunities |

### Market Analysis
| Component | Description |
|-----------|-------------|
| `correlation/` | Asset correlation matrices |
| `heatmap/` | Market heatmaps |
| `orderbook/` | Order book analysis |
| `orderflow/` | Order flow analysis |
| `screener/` | Token screening tools |
| `sentiment/` | Sentiment dashboards |
| `volatility/` | Volatility analysis |

### On-Chain Intelligence
| Component | Description |
|-----------|-------------|
| `holders/` | Token holder analysis |
| `onchain/` | On-chain metrics |
| `smartmoney/` | Smart money tracking |
| `whale/` | Whale activity monitoring |

### Advanced Features
| Component | Description |
|-----------|-------------|
| `arbitrage/` | Arbitrage opportunity finder |
| `derivatives/` | Derivatives trading UI |
| `leverage/` | Leveraged trading interfaces |
| `liquidations/` | Liquidation tracking |
| `mev/` | MEV protection/analysis |
| `options/` | Options trading UI |
| `perpetuals/` | Perps trading interface |

### Utilities & UI
| Component | Description |
|-----------|-------------|
| `alerts/` | Alert configuration UI |
| `calculator/` | Trading calculators |
| `calendar/` | Crypto events calendar |
| `compare/` | Token comparison tools |
| `explorer/` | Blockchain explorer |
| `fees/` | Fee calculators |
| `gas/` | Gas price tracking |
| `journal/` | Trading journal |
| `news/` | News aggregation |
| `planner/` | Trade planning tools |
| `settings/` | User preferences |
| `tax/` | Tax calculation tools |
| `wallet/` | Wallet management |
| `watchlist/` | Custom watchlists |

### Responsive & Mobile
- `MobileNav.jsx` - Mobile navigation
- `ResponsiveLayout.jsx` - Adaptive layouts
- `ResponsiveCard.jsx` - Mobile-friendly cards
- `ResponsiveTable.jsx` - Scrollable tables
- `responsive.css` - Mobile breakpoints

### System Components
- `AutoUpdater.jsx` - Application updates
- `NotificationCenter.jsx` - Notification hub
- `StatusBar.jsx` - System status display

### New Hooks
| Hook | Description |
|------|-------------|
| `useElectron.js` | Electron IPC communication |
| `useMarketDataStream.js` | Real-time market data |
| `useMediaQuery.js` | Responsive breakpoints |
| `useVoiceCommands.js` | Voice control integration |

### New Pages
- `Alerts.jsx` - Alert management page

---

## 🔧 Infrastructure Improvements

### API Key Management (`core/secrets.py`) - **+69 lines**
Enhanced key handling:
- **14 API integrations** tracked
- `validate_required_keys()` - Startup validation
- `print_key_status()` - Debug key configuration
- `list_configured_keys()` - Enumerate all keys

### Rate Limiting - **System-wide**
Implemented across all API clients:
- **CryptoPanic**: 1 req/sec with caching
- **LunarCrush**: 1.5 req/sec with daily tracking
- **Grok**: Image generation limits persisted
- **BirdEye**: Tiered rate limiting

### Telegram Console Bridge (`core/telegram_console_bridge.py`) - **+234 lines**
- Enhanced message routing
- Better error handling
- Improved state management

### Electron Main Process (`frontend/electron/main.js`) - **+196 lines**
- IPC handlers for market data
- Window state persistence
- Auto-updater integration

---

## 📁 New File Summary

### Core (7 new files)
```
core/autonomy/action_executor.py
core/autonomy/news_detector.py
core/enhanced_market_data.py
core/price/resilient_fetcher.py
core/price_alerts.py
core/webhook_manager.py
core/whale_tracker.py
```

### Bots (4 new files)
```
bots/health_endpoint.py
bots/supervisor.py
bots/twitter/trend_analyzer.py
bots/twitter/x_claude_cli_handler.py
```

### Frontend (80+ new files)
```
70+ component directories with index.js exports
9 trading components
4 new hooks
1 new page
3 responsive utilities
```

### Services (1 new file)
```
tg_bot/services/claude_cli_handler.py
```

### Scripts (2 new files)
```
scripts/send_progress_report.py
scripts/send_vibe_code_v2.py
```

### Tests (2 new files)
```
tests/security_pentest.py
tests/test_vibe_coding.py
```

---

## 📊 Stats

| Metric | Value |
|--------|-------|
| Lines Added | 7,750+ |
| Lines Modified | 977 |
| New Files | 105 |
| Modified Files | 49 |
| New Components | 70+ |
| New Hooks | 4 |
| New API Integrations | 3 |
| New Bot Commands | 20+ |

---

## 🔄 Migration Notes

1. **New dependencies**: Run `npm install` in frontend/
2. **New data directories**: `data/execution/` created automatically
3. **API keys**: New optional keys: COINGLASS_API_KEY, FINNHUB_API_KEY
4. **Environment**: Check `validate_required_keys()` output on startup

---

## 🎯 What's Next (v4.7.0)

- Multi-agent coordination
- Advanced backtesting engine
- Mobile app (React Native)
- Plugin system for custom strategies

---

# [4.5.0] - 2026-01-14

### 🤖 **Bot Supervisor & Resilience System**

Production-ready bot orchestration with auto-recovery and health monitoring.

### 🆕 New Features
- **Bot Supervisor**: Manages all bot processes with auto-restart
- **Health Endpoints**: HTTP health checks for monitoring
- **Graceful Shutdown**: Clean process termination
- **Resource Limits**: Memory/CPU caps per bot

---

# [4.4.0] - 2026-01-14

### 📰 **Enhanced Sentiment Report with Direct Buy Buttons**

JARVIS-analyzed market reports with one-click trading.

### 🆕 New Features
- **JARVIS Analysis**: AI-powered market interpretation
- **Multi-Asset Coverage**: Full crypto market, not just Solana
- **Buy Buttons**: Direct trading from sentiment reports
- **Confidence Scoring**: Per-signal reliability metrics

---

# [4.3.0] - 2026-01-13

### 🏗️ **Infrastructure Improvements Release**

Major core infrastructure modules and admin command enhancements.

### 🆕 New Features

#### Core Infrastructure Modules
- **Audit Logger** (`core/audit_logger.py`): Comprehensive audit trail with hash chain support
- **Feature Flags** (`core/feature_flags.py`): Runtime toggles with percentage rollouts
- **Health Monitor** (`core/health_monitor.py`): System health checks with K8s probes
- **Config Hot Reload** (`core/config_hot_reload.py`): Runtime configuration updates

#### 9 New Admin Commands
| Command | Description |
|---------|-------------|
| `/health` | System health status |
| `/flags` | View/toggle feature flags |
| `/config` | View/set configuration |
| `/score` | Treasury scorecard (P&L) |
| `/orders` | Active TP/SL orders |
| `/system` | Full system overview |
| `/wallet` | Treasury wallet info |
| `/logs` | Recent log entries |
| `/audit` | Audit log entries |

#### Runtime Toggles
- `/flags enable <name>` - Enable feature flag
- `/flags disable <name>` - Disable feature flag
- `/config set <key> <value>` - Set config value

#### Trading Improvements
- **Order Persistence**: TP/SL orders saved to `data/limit_orders.json`
- **Background Health Monitoring**: Auto-starts on bot startup

#### Menu Buttons
- All admin commands accessible via inline keyboard buttons

### 🧪 Tests
- 16 new tests for core infrastructure modules (all passing)

---

# [3.6.0] - 2026-01-09

### 🚀 **Ralph Wiggum Loop Enhancements**

Major feature additions across trading, voice, and user experience.

### 🆕 New Features

#### Telegram Bot
- **Inline Keyboard Navigation**: Interactive button menus replace text commands
- **Paper Trading Commands**: `/paper wallet|buy|sell|history|reset`
- Admin/user role-specific button layouts

#### Voice Activation
- **"Hey Jarvis" Wake Word**: Cross-platform wake word detection
- Works on Windows, macOS, Linux without model training
- Desktop launcher (`Jarvis-Voice.bat`) for testing

#### Real-Time Data
- **WebSocket Price Server**: True real-time price streaming on port 8766
- Multi-client, per-token subscriptions
- Frontend hooks: `useWebSocketPrice`, `useSingleTokenPrice`

#### Position Tracking
- **Position Tracker**: Full history and aggregate statistics
- API endpoints: `/api/position/stats`, `/api/position/history`
- Win rate, P&L, streaks, performance by symbol
- Frontend `PositionStats` component

#### Paper Trading
- **Enhanced Paper Wallet**: Realistic balance simulation
- Fee/slippage modeling (configurable bps)
- Trade history logging with analytics

#### Strategy Optimization
- **Optuna Hyperparameter Tuning**: Automated strategy optimization
- Support for SMA cross, RSI, Bollinger strategies
- Multiple objectives: Sharpe ratio, profit factor, ROI

### 📁 New Files

| File | Description |
|------|-------------|
| `core/wake_word.py` | Cross-platform wake word detection |
| `core/websocket_server.py` | WebSocket price streaming server |
| `core/position_tracker.py` | Position history and statistics |
| `core/paper_trading.py` | Enhanced paper trading engine |
| `core/hyperparameter_tuning.py` | Optuna strategy optimization |
| `frontend/src/hooks/useWebSocketPrice.js` | WebSocket price hook |
| `frontend/src/hooks/usePositionStats.js` | Position stats hook |
| `frontend/src/components/trading/PositionStats.jsx` | Stats display |

### 🔧 Bug Fixes

- Windows compatibility for process alive check in `state.py`
- UTF-8 encoding for bot.py test reads

### 📊 Metrics

| Metric | Value |
|--------|-------|
| Tests passing | 1108 |
| New features | 7 |
| Files added | 8 |

---

# [3.5.2] - 2026-01-09

### 🔧 **Deprecation Fixes & Code Quality**

Comprehensive cleanup of Python 3.12+ deprecation warnings and code quality improvements.

### 🐛 Bug Fixes

- **datetime.utcnow() Deprecation**: Replaced 72 occurrences across 21 files with timezone-aware `datetime.now(timezone.utc)`
- **Test Fixes**: Fixed 3 failing telegram bot tests (config validation, defaults, function imports)
- **Warnings Eliminated**: Reduced pytest warnings from 336 to 0

### 📁 Files Updated

| Module | Files Changed | Changes |
|--------|---------------|---------|
| `core/self_improving/` | 8 files | All datetime calls modernized |
| `core/integrations/` | 4 files | Calendar, sentiment bots updated |
| `tg_bot/` | 3 files | Subscriber, scheduler, token_data |
| `core/` | 4 files | api_server, jarvis, google_manager, trading_decision_matrix |
| `tests/` | 1 file | test_self_improving.py |
| `scripts/` | 1 file | monitor_positions.py |

### 📊 Metrics

| Metric | Before | After |
|--------|--------|-------|
| Deprecation warnings | 336 | 0 |
| Tests passing | 1065 | 1065 |
| Test coverage | 20% | 20% |

---

# [3.5.1] - 2026-01-09

### 🔗 **Self-Improving Core Integration**

Integrates the Self-Improving Core (v3.5.0) with the main Jarvis daemon and API server.

### 🆕 New Features

- **Daemon Integration**: Self-improving scheduler runs nightly at 3am for reflection cycles
- **API Endpoints**: `/api/brain/stats`, `/api/brain/health`, `/api/brain/trust`
- **Conversation Enrichment**: Response context now includes learned patterns and reflections
- **Telegram `/reflect` Command**: Trigger reflection cycle from Telegram

### 📁 New Files

| File | Description |
|------|-------------|
| `core/self_improving/integration.py` | Singleton orchestrator and integration utilities |
| `tests/test_self_improving_integration.py` | 19 integration tests |

---

# [3.5.0] - 2026-01-09

### 🧠 **Self-Improving Core: Reflexion Pattern Implementation**

A complete self-improvement system based on the Reflexion paper (NeurIPS 2023). Jarvis can now learn from conversations, reflect on mistakes, and gradually earn autonomy.

### 🆕 New Features

**Memory System** (`core/self_improving/memory/`):
- **SQLite Memory Store**: Facts, reflections, predictions, interactions - no vector DB needed
- **Entity Management**: Track people, projects, companies, concepts
- **Full-Text Search**: Efficient querying without embedding costs

**Trust Ladder** (`core/self_improving/trust/`):
- **5 Trust Levels**: STRANGER → ACQUAINTANCE → COLLEAGUE → PARTNER → OPERATOR
- **Domain-Specific Trust**: Different autonomy levels per domain
- **Trust Earned**: Through accurate predictions and accepted suggestions

**Reflexion Engine** (`core/self_improving/reflexion/`):
- **Nightly Reflection**: Analyzes problematic interactions at 3am
- **Lesson Extraction**: "What went wrong and what to do differently"
- **Memory Pruning**: Old, unused reflections automatically cleaned

**Proactive Engine** (`core/self_improving/proactive/`):
- **Context-Aware Suggestions**: Only suggests when confidence > 70%
- **Rate Limiting**: Max 3 suggestions per day, cooldown between suggestions
- **Learning from Feedback**: Tracks which suggestions get accepted

**Action Framework** (`core/self_improving/actions/`):
- **Trust-Gated Actions**: Actions require minimum trust level
- **Action Types**: Draft, Schedule, Remind, Send, Execute
- **Full Audit Trail**: All actions logged with reversibility info

**Learning Extractor** (`core/self_improving/learning/`):
- **Fact Extraction**: Pulls new facts from conversations
- **Preference Detection**: Implicit preferences from behavior
- **Correction Handling**: Updates outdated facts

### 📁 New Files

| File | Description |
|------|-------------|
| `core/self_improving/__init__.py` | Package exports |
| `core/self_improving/orchestrator.py` | Main entry point, ties everything together |
| `core/self_improving/memory/store.py` | SQLite memory implementation |
| `core/self_improving/memory/models.py` | Data models (Entity, Fact, Reflection, etc.) |
| `core/self_improving/trust/ladder.py` | Trust management and progression |
| `core/self_improving/reflexion/engine.py` | Nightly reflection cycle |
| `core/self_improving/proactive/engine.py` | Suggestion generation |
| `core/self_improving/learning/extractor.py` | Conversation analysis |
| `core/self_improving/actions/framework.py` | Autonomous action execution |
| `tests/test_self_improving.py` | 29 comprehensive tests |

### 📊 Metrics

| Metric | Value |
|--------|-------|
| New tests | 29 |
| Trust levels | 5 |
| Action types | 5 |
| Memory tables | 7 (entities, facts, reflections, predictions, interactions, trust, settings) |

---

# [3.4.0] - 2026-01-09

### 🤖 **Telegram Bot v1.0: Production Signal Bot with Grok Sentiment**

This release delivers a fully functional Telegram trading signal bot with real-time Grok AI sentiment analysis, proper DexScreener integration, and comprehensive admin security controls.

### 🆕 New Features

**Telegram Signal Bot** (`tg_bot/`):
- **Master Signal Report**: `/signals` command returns top 10 trending Solana tokens with:
  - Clickable contract addresses
  - Entry recommendations (scalp/day trade/long term)
  - Leverage suggestions based on liquidity
  - Full Grok sentiment analysis on top 3 tokens
  - Risk assessment and signal scores (-100 to +100)
  - Direct links to DexScreener, Birdeye, Solscan
- **Admin-Only Commands**: Expensive API calls restricted to whitelisted Telegram IDs
- **Rate Limiting**: Configurable limits (1 sentiment/hour, 24/day, $1/day cost cap)
- **Cost Tracking**: SQLite-based API usage tracking with daily reports

**DexScreener Boosted Tokens API** (`core/dexscreener.py`):
- **`get_boosted_tokens()`**: Fetch trending tokens from `token-boosts/top/v1` endpoint
- **`get_boosted_tokens_with_data()`**: Enriched tokens with full price/volume/liquidity data
- **Updated `get_solana_trending()`**: Now uses boosted tokens (20+ real trending tokens)
- **Updated `get_momentum_tokens()`**: Momentum scoring with boosted tokens fallback

**Grok Sentiment Integration**:
- Enabled Grok provider in local config (`lifeos/config/lifeos.config.local.json`)
- Model: `grok-3-mini` for cost-effective sentiment analysis
- Budget controls: $1/day limit, 5 requests per cycle, 1-hour cache TTL
- Fallback: Heuristic keyword-based sentiment when API unavailable

**Signal Service** (`tg_bot/services/signal_service.py`):
- Comprehensive token signals combining DexScreener + GMGN + Grok
- Signal scoring algorithm: momentum (25%), volume (15%), liquidity (10%), security (25%), smart money (15%), sentiment (15%)
- Signal levels: STRONG_BUY, BUY, NEUTRAL, SELL, STRONG_SELL, AVOID

**Beautiful Digest Formatter** (`tg_bot/services/digest_formatter.py`):
- Telegram-optimized markdown formatting
- Entry recommendations based on signal strength and liquidity
- Leverage suggestions (1x-5x) based on risk profile
- All links clickable in Telegram

### 🔧 Configuration

**New Environment Variables** (in `tg_bot/.env`):
```
TELEGRAM_BOT_TOKEN=your-bot-token
XAI_API_KEY=your-grok-key
TELEGRAM_ADMIN_IDS=your-telegram-id
BIRDEYE_API_KEY=your-birdeye-key
```

**Core Config Override** (`lifeos/config/lifeos.config.local.json`):
```json
{
  "providers": { "grok": { "enabled": true, "model": "grok-3-mini" } },
  "sentiment_spend_policy": { "daily_budget_usd": 1.0 }
}
```

### 📁 New Files

| File | Description |
|------|-------------|
| `tg_bot/bot.py` | Main bot with admin-only decorators and rate limiting |
| `tg_bot/config.py` | Secure config with .env loading and admin whitelist |
| `tg_bot/cli.py` | CLI for bot control (start, status, test, costs) |
| `tg_bot/services/signal_service.py` | Comprehensive signal aggregation |
| `tg_bot/services/cost_tracker.py` | API cost tracking with SQLite |
| `tg_bot/services/digest_formatter.py` | Beautiful Telegram formatting |

### 📊 Metrics

| Metric | Value |
|--------|-------|
| DexScreener tokens | 20+ Solana trending |
| Signal sources | 6 (DexScreener, Birdeye, DexTools, GMGN, Grok, Lute) |
| Bot commands | 8 (start, signals, trending, analyze, digest, costs, status, help) |
| Test coverage | Signal service fully tested |

---

# [3.3.0] - 2026-01-08

### 🏗️ **Architecture Refactor: Cross-Platform Support & Test Infrastructure**

This release introduces comprehensive cross-platform support, modular subpackages for better code organization, and significantly expanded test coverage.

### 🆕 New Features

**Cross-Platform Abstraction Layer** (`core/platform/`):
- **PlatformAdapter**: Abstract base class for OS-specific operations
- **MacOSAdapter**: osascript, pbcopy/pbpaste, say command integration
- **WindowsAdapter**: win32 APIs, PowerShell notifications, pyttsx3 TTS
- **LinuxAdapter**: notify-send, xdotool, xclip, espeak support
- **Auto-Detection**: Singleton pattern with `get_adapter()` for runtime platform detection
- **Unified API**: `send_notification()`, `get_clipboard_content()`, `speak_text()`, etc.

**Module Consolidation Subpackages**:
- **`core/trading/`**: Unified re-exports for all trading modules (jupiter, raydium, jito, strategies, signals, wallet)
- **`core/voice/`**: Unified re-exports for voice modules (voice.py, hotkeys.py, openai_tts.py)
- **Backwards Compatible**: All existing imports continue to work

**SPL Token Holdings API** (`core/api_server.py`):
- New `_fetch_spl_token_holdings()` method for wallet token display
- Fetches via `getTokenAccountsByOwner` RPC call
- Token metadata and pricing via BirdEye API
- Returns top 20 tokens sorted by USD value

**MCP Health Check Enhancement** (`core/mcp_loader.py`):
- `_check_mcp_protocol_health()` for protocol-level validation
- Checks process stdin writability for stdio-based servers
- Improved restart reliability

### 🧪 Test Suite Expansion

**New Test Files (5 added)**:
- `tests/test_guardian.py`: ~50 tests for safety rules, protected paths, dangerous commands
- `tests/test_providers.py`: ~40 tests for LLM provider abstraction
- `tests/test_daemon.py`: ~25 tests for daemon orchestration
- `tests/test_conversation.py`: ~35 tests for conversation logic
- `tests/test_platform.py`: ~30 tests for platform abstraction

**Test Infrastructure**:
- Added `pytest-cov>=4.1.0` for coverage reporting
- Added `pytest-asyncio>=0.23.0` for async tests
- Added `pytest-mock>=3.12.0` for mocking
- Added `responses>=0.25.0` for HTTP mocking
- Added `ruff>=0.1.0` for fast linting
- Added `mypy>=1.8.0` for type checking

**Coverage Improvement**:
- Test files: 13 → 18 (+5)
- Estimated coverage: ~15% → ~25%
- Critical modules now tested: guardian, providers, daemon, conversation, platform

### 🔐 Security Fixes

**osascript Injection Prevention** (`core/daemon.py`):
```python
# Before (vulnerable):
script = f'display notification "{message}" with title "{title}"'

# After (safe):
safe_title = title.replace('\\', '\\\\').replace('"', '\\"')
safe_message = message.replace('\\', '\\\\').replace('"', '\\"')
```

### 🧹 Code Cleanup

**Removed DEBUG Logging in Production**:
- `core/birdeye.py:549` - Changed to INFO level
- `core/dexscreener.py:486` - Changed to INFO level
- `core/geckoterminal.py:388` - Changed to INFO level

**Deleted Broken Files**:
- Removed `core/iterative_improver_broken.py` (duplicate of working version)

### 📝 Documentation

**Ralph Wiggum Loop** (`.windsurf/workflows/jarvis.md`):
- Comprehensive improvement tracking system
- 6 phases with prioritized tasks
- Metrics dashboard with before/after comparisons
- Quick commands for testing and linting

### 📊 Metrics

| Metric | Before | After | Change |
|--------|--------|-------|--------|
| Test Files | 13 | 18 | +5 |
| TODO Items | 19 | 16 | -3 |
| DEBUG in prod | 3 | 0 | -3 |
| Security Issues | 2 | 1 | -1 |
| Core Subpackages | 0 | 3 | +3 |

### 🔧 Dependencies

```bash
# New test dependencies
pytest-cov>=4.1.0
pytest-asyncio>=0.23.0
pytest-mock>=3.12.0
responses>=0.25.0

# New code quality tools
ruff>=0.1.0
mypy>=1.8.0
```

---

# [3.2.0] - 2026-01-08

### 🔐 **Wallet Infrastructure v2.5 - Institutional-Grade Solana Execution**

This release introduces comprehensive wallet infrastructure for production-ready Solana trading.

### 🆕 New Features

**Wallet Infrastructure** (`core/wallet_infrastructure.py` ~700 lines):
- **Address Lookup Tables (ALTs)**: Transaction compression reducing account size from 32 bytes to 1 byte
- **Dual-Fee System**: 4-tier priority system (LOW/MEDIUM/HIGH/URGENT) with Jito tip integration
- **Transaction Simulation**: Pre-sign validation with compute unit estimation and error classification
- **Blockhash Lifecycle**: Freshness tracking, auto-refresh, and stale detection
- **Token Safety Analyzer**: Mint authority, freeze authority, liquidity, and holder concentration checks

**Test Suite Expansion**:
- `tests/test_wallet_infrastructure.py`: 32 comprehensive tests for wallet module
- `tests/test_cli.py`: 11 CLI helper function tests
- **Total: 111 tests passing** (up from ~80)

### 🐛 Bug Fixes

**Cross-Platform Compatibility**:
- Fixed `fcntl` import error on Windows in `core/exit_intents.py`
- Added `msvcrt` fallback for file locking on Windows
- Helper functions `_lock_file()` and `_unlock_file()` for cross-platform support

**Test Corrections**:
- Updated `test_trading_integration.py` to match current implementation:
  - `classify_simulation_error("blockhash not found")` → "retryable" (not "blockhash_expired")
  - Position sizer returns `position_value` (not `position_size`)

### 📊 Backtest Results

Ran Solana DEX backtest on 15 tokens via GeckoTerminal:
- **Top Performer**: TRUMP token on Meteora DEX
  - Strategy: SMA 10/50 crossover
  - 90-day ROI: -8.2% | 30-day Avg: +0.5%
  - Max Drawdown: 13.8% | 26 trades
  - Bot config: `data/trader/solana_dex/bots/trump_6p6xgH.json`

### 📝 Documentation

- Updated README.md with Wallet Infrastructure section
- Added dual-fee system table with priority levels
- Added v2.5 to Completed roadmap section

---

# [3.1.0] - 2026-01-06

### 🔧 **Frontend Refactor: Modular Architecture & Premium Polish**

This release wires in the previously created modular components, ensuring the refactored architecture is actually used in production.

**Note**: The UI is a working baseline and we’re just getting started — expect ongoing UX/UI polish and refinements.

### ⚠️ Critical Fix: Wiring Refactored Files
- **main.jsx**: Startup wiring stabilized; CSS entry may be adjusted during ongoing frontend hardening
- **App.jsx**: Now imports refactored pages (`DashboardNew`, `ChatNew`, `TradingNew`) instead of legacy versions
- **Layout.jsx**: Added Roadmap navigation link

### 🆕 New Features
- **useCapabilities Hook**: Probes API endpoints on load to detect available features
  - Caches results in sessionStorage (5-minute TTL)
  - Returns `{ capabilities, loading, refresh }`
- **Roadmap Page**: Interactive 6-phase progress tracker
  - Accordion-style phase expansion
  - Feature status badges (✅ done, ⚠️ in-progress, ❌ not started)
  - Overall completion percentage

### 🎨 White Theme Applied
- **Research.jsx**: Refactored to white theme with proper CSS classes
- **Settings.jsx**: Refactored to white theme with card-based layout
- **VoiceControl.jsx**: Refactored to white theme with voice orb

### 📁 Barrel Exports Created
- **components/index.js**: Root-level export for all components
- **lib/index.js**: Root-level export for all utilities

### 🐛 CSS Fixes
- Added `appearance: button` for cross-browser compatibility
- Removed conflicting `vertical-align` on block elements

### 📝 Documentation
- **README.md**: Added "Frontend Architecture V2" section with file tree
- **README.md**: Added "What's Live Now" route table
- **README.md**: Added "Capability Detection" usage example

---

# [3.0.0] - 2026-01-05

### 🚀 **MAJOR RELEASE: Ultimate Trading Dashboard V3**

This release represents a complete UI/UX transformation with an ultra-clean Airbnb-style design, integrated TradingView charts, advanced order panel, and a comprehensive 6-phase roadmap for the ultimate trading command center.

### 🎨 Dashboard V3 - Pure White Aesthetic
- Switched to "White Knight" pure white design system (Airbnb inspired).
- Fixed invisible text issues in Dashboard.jsx.
- Backend port aligned to 8765.
- **KNOWN ISSUE**: Frontend API endpoints (`/api/wallet/status`, etc.) are currently glitching/returning 404s. Fix impending.

### 🎨 Trading Dashboard V2 - Ultra-Clean White Knight UI

- **Complete Design System Overhaul** (`frontend/src/index.css` +780 lines)
  - Inter font family with premium typography hierarchy
  - Soft shadow system (sm/md/lg/xl elevations)
  - White knight color palette (generous white space, soft grays, indigo accents)
  - Mobile-responsive grid layouts with touch-optimized controls
  - Skeleton loading states and smooth micro-animations

- **New Component Architecture**
  - **TopNav**: Clean navigation with SOL price ticker and wallet balance
  - **Sidebar**: Icon-based navigation (Overview/Trading/Tools/Analytics/Settings)
  - **StatsGrid**: Portfolio value, win rate, total trades, P&L tracking
  - **LivePositionCard**: Real-time P&L with visual TP/SL progress bars
  - **ToolsHub**: Token scanner with rug check (0-100 risk score)
  - **FloatingChat**: Expandable Jarvis AI assistant bubble

- **Enhanced API Endpoints** (`core/api_server.py` +1,353 lines)
  - Total: 17 API endpoints (14 existing + 3 new)
  - Wallet status, transactions, sniper status/config
  - Scan history, trending momentum, Jarvis chat/status
  - System info, position management, DeFi tools

### 📊 Phase 1: Trading Core (Charts + Order Panel)

- **TradingChart Component** (`frontend/src/components/TradingChart.jsx` +284 lines)
  - lightweight-charts integration with real-time OHLCV candlesticks
  - 6 timeframe options: 1m, 5m, 15m, 1H, 4H, 1D
  - Auto-refresh every 30 seconds
  - BirdEye API with DexScreener synthetic fallback
  - Volume histogram overlay
  - Real-time price updates with change tracking

- **OrderPanel Component** (`frontend/src/components/OrderPanel.jsx` +294 lines)
  - Buy/Sell toggle with visual feedback
  - TP/SL preset buttons (+10/20/50%, -5/10/20%)
  - Position sizing with preset amounts (0.01, 0.05, 0.1, 0.25 SOL)
  - Paper trading mode with simulated execution
  - Live trade result display with status

- **New API Endpoints**
  - `/api/chart/{mint}` - OHLCV candlestick data with timeframe selection
  - `/api/strategies/list` - All 81 trading strategies
  - `/api/trade` - Execute trades with TP/SL configuration

### 🛣️ Ultimate Dashboard Roadmap (6 Phases)

- **Comprehensive Master Plan** (`README.md` +54 lines)
  - Phase 1: Trading Core (TradingView charts, order panel, order book)
  - Phase 2: Sentinel Mode (autonomous trading, 81 strategy coliseum, approval gate)
  - Phase 3: Intelligence Layer (signal aggregator, smart money, sentiment, ML regime)
  - Phase 4: LifeOS Integration (voice trading, mirror test, knowledge engine)
  - Phase 5: Advanced Tools (MEV dashboard, 30x perps, multi-DEX execution)
  - Phase 6: Polish & Scale (WebSocket, PWA, themes, onboarding)
  - Timeline: ~19 days | API Endpoints: 45 total planned

### 📈 Build Stats

- **JavaScript**: 397.74 KB (121.86 KB gzipped)
- **CSS**: 44.43 KB (8.83 KB gzipped)
- **Modules**: 1,392 transformed
- **Total Changes**: 9,973 insertions across 18 files

### 🎯 Vision: "An Edge for the Little Guy"

Democratizing institutional-grade trading tools:
- $50,000+/year Bloomberg Terminal features → Free
- $100,000+ hedge fund infrastructure → Open source
- Hundreds of dev hours for institutional algos → Accessible to retail

---

# [2.4.0] - 2026-01-05

### 🚀 **MAJOR RELEASE: Multi-Source Data Aggregation & Execution Hardening**

This release adds comprehensive data source integration, Grok sentiment analysis, stop loss/take profit orders, and redundant execution fallbacks.

### 📊 Multi-Source Data Integration

- **Lute.gg Momentum Tracker** (`core/lute_momentum.py`) - NEW
  - Token call tracking from X/Twitter lute.gg links
  - Conviction-based scoring (low/medium/high)
  - Multi-caller aggregation for momentum signals
  - Sentiment validation of calls via Grok

- **GMGN.ai Token Metrics** (`core/gmgn_metrics.py`) - NEW
  - Smart money wallet tracking (insiders, snipers, whales)
  - Token security analysis (honeypot, LP burned, mintable)
  - First 70 buyers PnL analysis
  - Fallback to RugCheck when GMGN unavailable

- **DexTools Integration** (`core/dextools.py`) - NEW
  - Hot pairs tracking with DexTools hot level
  - Token audit scores and security data
  - Automatic DexScreener fallback
  - Rate limiting and caching

- **Unified Signal Aggregator** (`core/signal_aggregator.py`) - NEW
  - Combines all sources: DexScreener, BirdEye, GeckoTerminal, DexTools, GMGN, Lute
  - Grok sentiment integration for signal scoring
  - Aggregated signal strength (STRONG_BUY to AVOID)
  - Momentum opportunity discovery

### 🎯 Jupiter Order Management

- **Jupiter Orders** (`core/jupiter_orders.py`) - NEW
  - Stop Loss orders with automatic execution
  - Take Profit orders with trigger monitoring
  - TP Ladder support (default: +8%/+18%/+40%)
  - Trailing stops with dynamic trigger adjustment
  - Time stops for position expiry
  - Breakeven SL adjustment after TP1
  - Persistent order storage (survives restarts)
  - Order history logging

### 🔄 Execution Fallback System

- **Execution Fallback** (`core/execution_fallback.py`) - NEW
  - Multi-venue execution: Jupiter → Raydium → Orca
  - Quote comparison for best price
  - Circuit breaker per venue (3 failures → 2min cooldown)
  - Automatic failover on execution failure
  - Unified result format

### 🛠️ Solana Execution Improvements

- **Enhanced RPC Failover** (`core/solana_execution.py`)
  - Circuit breaker pattern (3 failures → 60s recovery)
  - Health caching (10s TTL) reduces redundant checks
  - Exponential backoff with jitter
  - Better error classification (retryable vs permanent)

- **Fortified DexScreener** (`core/dexscreener.py`)
  - TokenPair dataclass with 20+ fields
  - Momentum token detection
  - Rate limiting infrastructure (300 req/min)
  - Safe fetch functions with Result wrapper

- **Improved BirdEye/GeckoTerminal**
  - Rate limiting across all API clients
  - Unified Result dataclasses
  - Safe fetch functions with error handling
  - API status monitoring

### 📈 Grok Sentiment Integration

- **Signal-Weighted Sentiment**
  - Sentiment analysis integrated into signal scoring
  - Positive sentiment boosts signal (+8 to +15)
  - Negative sentiment reduces signal (-8 to -15)
  - Confidence-weighted scoring

---

# [1.1.0] - Institutional Hardening

### 🔒 Audit Hardening

- **Gnosis Safe Enforcement:** Added `core/transaction_guard.py` and enforced `POLY_GNOSIS_SAFE=2` in Solana swap + Jito bundle execution.
- **WebSocket Resilience:** Heartbeat timeouts + exponential reconnect backoff for Binance/Kraken streams (`core/data_ingestion.py`).
- **API 503/429 Backoff:** Exponential backoff across Birdeye, GeckoTerminal, DexScreener, Jupiter, RugCheck, and Jupiter swap endpoints.
- **Fee-Aware Market Making:** Spread guardrails after fees in `core/trading_strategies_advanced.py::MarketMaker`.
- **JSON Logging:** Structured logging toggle for trading daemon (`LIFEOS_LOG_JSON=1`).
- **Kill Switch Env:** `LIFEOS_KILL_SWITCH` activates emergency trade shutdown (`core/approval_gate.py`).
- **Blockhash Drift Hook:** Optional re-sign callback for Solana swaps to recover stale blockhash.
- **TWAP Schedule Builder:** Time-sliced, venue-split execution via `SmartOrderRouter.build_twap_schedule`.

# [2.3.0] - 2026-01-04

### ⚙️ Tokenized Equities + Execution Reliability

- **New Universe Ingestion:** `core/tokenized_equities_universe.py`
  - xStocks products ingestion via Next.js data endpoint
  - PreStocks products + sitemap scraping with Solana mint extraction
  - Cached universe stored in `data/trader/universe/tokenized_equities.json`

- **Fee Model:** `core/fee_model.py`
  - Network + AMM + slippage + spread + issuer fee modeling
  - Edge-to-cost ratio gating enforced in opportunity engine
  - Persisted profiles in `data/trader/knowledge/fee_profiles.json`

- **Event/Catalyst Mapping:** `core/event_catalyst.py`
  - Extracts catalysts from X/Twitter sentiment text
  - Maps company names/tickers to tokenized equities
  - Adjusts scoring horizon for catalyst windows

- **Execution Reliability:** `core/solana_execution.py`
  - RPC failover, simulation before send, confirmation loop
  - Shared wallet loader (`core/solana_wallet.py`) + token metadata (`core/solana_tokens.py`)

- **Exit Enforcement + Reconciliation:**
  - Live exit intents can execute swaps when enabled
  - On-chain reconciliation on daemon boot with optional auto intent creation

- **Audit Suite Expanded:** `python3 -m core.audit run_all`
  - Includes equities ingestion, fee model, catalysts, and Grok caching tests

- **Grok Spend Controls:** `core/x_sentiment.py`
  - TTL caching, batching, daily budget caps with warnings

---

# [2.2.0] - 2026-01-03

### 🛡️ **MAJOR RELEASE: Trading Safety & Optimization**

This release focuses on production-ready trading safety with human approval gates, walk-forward validation to prevent overfitting, and DSPy-based strategy optimization.

### 🚨 Human Approval Gate

- **New Module:** `core/approval_gate.py` (340 lines)
  - **Pre-Trade Approval**: No live trade executes without explicit human confirmation
  - **Pending Queue**: Trade proposals with configurable expiry (default 5 minutes)
  - **Kill Switch**: Emergency `kill_switch()` cancels all pending trades
  - **macOS Notifications**: Real-time approval alerts with trade details
  - **Audit Trail**: Complete history logged to `data/trading/approvals/history.jsonl`
  - **CLI Interface**: `python core/approval_gate.py [submit|list|approve|reject|kill|status]`

### 📊 Walk-Forward Validation

- **Enhanced:** `core/trading_pipeline.py` (+111 lines)
  - **`walk_forward_backtest()`**: Time-series cross-validation with anchored splits
  - **`summarize_walk_forward()`**: Aggregates metrics across 5 out-of-sample folds
  - **Overfitting Prevention**: Tests strategies on multiple unseen time periods
  - **Promotion Rules**: Requires avg Sharpe > 1.0, Max DD < 20%, 3/5 passing folds
  - **Industry Standard**: Prevents fantasy PnL from curve-fitting

### 🤖 DSPy Strategy Optimization

- **New Module:** `core/dspy_classifier.py` (440 lines)
  - **ClassifyStrategy Signature**: Auto-categorize trading strategies
  - **AnalyzeStrategyRisk Signature**: Identify failure modes and controls
  - **ProposePatch Signature**: AI-generated code improvements
  - **GenerateTestCase Signature**: Pytest test generation
  - **Local LLM Support**: Ollama integration (qwen2.5:7b) for privacy
  - **BootstrapFewShot Optimizer**: Prompt optimization with 8 training examples
  - **Graceful Fallback**: Works without DSPy installed, optional `pip install dspy-ai`

### 🔍 Comprehensive System Audit

- **New Document:** `COMPREHENSIVE_AUDIT_2026-01-03.md` (750+ lines)
  - **Repo Map**: Functional boundaries (Trading, Autonomy, Risk, Data, Memory)
  - **Risk Register**: 10 prioritized risks (R1-R10) with mitigation plans
  - **Architecture vNext**: Mermaid diagrams, interface contracts, 5-phase migration
  - **Strategy Classification**: Updated schema with 12 strategies mapped
  - **Backtesting Plan**: Walk-forward implementation, Coliseum promotion rules
  - **Security Hardening**: Key migration, pre-commit hooks, process isolation
  - **DSPy Integration**: Signatures for classification, risk, patches

### 🐛 Bug Fixes

- **Fixed:** `core/providers.py` - Missing `PROVIDER_RANKINGS = [` declaration
  - Was blocking all core module imports with "unmatched ]" syntax error
  - Added proper list initialization at line 454

### ✅ Verification & Testing

- **All patches tested end-to-end:**
  - Walk-forward: 5 folds, avg Sharpe 3.7, Total PnL $18.10
  - Approval gate: Submit → Approve → Kill switch ✓
  - Cycle governor: Cooldown enforcement (299s) ✓
  - Error recovery: max_attempts=5 verified ✓
  - Observer mode: Already set to "lite" ✓

### 🎯 Configuration Updates

- **Observer mode**: Confirmed `"mode": "lite"` for privacy (no keystroke logging)
- **Error recovery**: Circuit breaker enforces max 5 retry attempts
- **Circular logic**: CycleGovernor blocks detected loops

### 📦 Dependencies

```bash
# Optional for DSPy optimization
pip install dspy-ai
```

### 🔗 Related Work

- Builds on v2.1.0 Quantitative Trading Infrastructure
- Addresses top issues from AUDIT_REPORT.md and TOP_ISSUES.md
- Implements recommendations from SELF_IMPROVEMENT.md

---

# [2.1.0] - 2026-01-03

### 🚀 **MAJOR RELEASE: Quantitative Trading Infrastructure**

This release transforms Jarvis's trading capabilities with advanced algorithmic strategies, real-time data ingestion, ML-based regime detection, and MEV execution on Solana.

### 📊 Advanced Trading Strategies

- **New Module:** `core/trading_strategies_advanced.py` (~700 lines)
  - **TriangularArbitrage**: Cross-rate exploitation (BTC→ETH→USDT→BTC) with flash loan support
  - **GridTrader**: Range-bound strategy for sideways markets with auto-level configuration
  - **BreakoutTrader**: Support/resistance detection with volume confirmation
  - **MarketMaker**: Bid-ask spread capture with inventory management and volatility scaling

### 📡 Data Ingestion Layer

- **New Module:** `core/data_ingestion.py` (~650 lines)
  - **WebSocket Handlers**: Real-time streaming from Binance and Kraken
  - **CCXT Integration**: Unified interface across 100+ exchanges
  - **TickBuffer**: Ring buffer for tick-level data with OHLCV aggregation
  - **Multi-Exchange Prices**: Spatial arbitrage detection across venues

### 🧠 ML Volatility Regime Detection

- **New Module:** `core/ml_regime_detector.py` (~700 lines)
  - **VolatilityRegimeDetector**: Random Forest/Gradient Boosting classifiers
  - **Feature Extraction**: RSI, Bollinger position, volatility metrics, momentum indicators
  - **Regime Classification**: Low/Medium/High/Extreme volatility states
  - **AdaptiveStrategySwitcher**: Auto-switch between Grid, Mean Reversion, Trend Following

### ⚡ MEV Execution (Solana)

- **New Module:** `core/jito_executor.py` (~550 lines)
  - **JitoBundleClient**: Bundle submission with simulation via Jito Block Engine
  - **JitoExecutor**: High-level interface with tip calculation and retry logic
  - **MEVScanner**: Sandwich opportunity detection in pending transactions
  - **SmartOrderRouter (SOR)**: Order splitting across DEXs to minimize market impact

### 🔒 Security Hardening

- **New Module:** `core/security_hardening.py` (~600 lines)
  - **SecureKeyManager**: Fernet encryption with PBKDF2 key derivation
  - **IP Whitelisting**: Per-key access control (lessons from 3Commas breach)
  - **SecurityAuditor**: Codebase scanning for leaked credentials
  - **SlippageChecker**: Order rejection when execution deviates beyond tolerance

### 📚 Documentation

- **New:** `docs/QUANT_TRADING_GUIDE.md` - Comprehensive guide covering:
  - Strategy categories (Arbitrage, MEV, Grid, Momentum, AI/Sentiment)
  - Static vs Adaptive bots comparison
  - Flashbots vs Jito Block Engine infrastructure analysis
  - Risk assessment (Mean Reversion limitations, Market Making inventory risk)
  - Architecture overview and quick start examples

### 📈 README Enhancements

- Added Quantitative Trading Infrastructure (v2.1) section
- Expanded roadmap with 5-phase detailed next steps plan through Q4 2026
- Added long-term vision for autonomous trading

### 🔧 Dependencies (Optional)

```bash
pip install ccxt websockets scikit-learn numpy aiohttp cryptography
# For Solana MEV: pip install solders
```

### ✅ Verification

- All 5 new modules compile successfully
- Each module includes runnable demo code at bottom
- Graceful degradation when optional dependencies missing

---

# [1.0.0] - 2026-01-01

### 🚀 **MAJOR RELEASE: Minimax 2.1 Integration & Self-Evolving Architecture**

This release transforms Jarvis from a reactive script runner into a **self-correcting, autonomous AI system** powered by Minimax 2.1.

### 🧠 Minimax 2.1 Integration

- **New Module:** `core/life_os_router.py` - Intelligent provider routing with Minimax 2.1 via OpenRouter
- **Hybrid AI Stack:** Minimax (primary) + Groq (tool execution) + Ollama (offline fallback)
- **Cost Efficiency:** 95% cost reduction ($0.30/1M input tokens vs $15/1M for GPT-4)
- **3x Faster Reflection:** Minimax optimized for high-frequency reasoning tasks
- **Context-Aware Routing:** Parallel health checks select optimal provider based on task type

### 🔁 Mirror Test (Self-Correction Engine)

- **New Module:** `core/self_improvement_engine_v2.py` - Nightly dream cycle for autonomous code refinement
- **New Directory:** `core/evolution/gym/` - Self-training arena with replay simulation
- **Log Replay:** Re-runs last 24 hours of decisions using current Minimax model
- **Performance Scoring:** Grades latency, accuracy, and user satisfaction
- **Refactor Generation:** Minimax proposes Python/config improvements
- **Dry-Run Validation:** Tests changes against 100 historical scenarios
- **Auto-Apply:** Merges improvements at 85% confidence threshold
- **Snapshot System:** Daily system backups with 60-day retention

### ⚔️ Paper-Trading Coliseum

- **New Module:** `core/trading_coliseum.py` - Automated strategy backtesting arena
- **Auto-Backtest:** 10 randomized 30-day simulations per strategy
- **Auto-Prune:** Deletes strategies after 5 consecutive failures
- **Auto-Promote:** Strategies with Sharpe >1.5 promoted to live candidates
- **Mutation Engine:** Minimax generates strategy variations for optimization
- **Strategy Autopsies:** Minimax-powered failure analysis for deleted strategies
- **SQLite Database:** `data/trading/coliseum/arena_results.db` for performance tracking
- **Strategy Cemetery:** Archives deleted strategies with comprehensive failure reports

### 📊 Trading Infrastructure

- **New Module:** `core/trading_strategies.py` - 5 implemented strategies (Trend, Mean Reversion, DCA, Arbitrage, Sentiment)
- **New Module:** `core/risk_manager.py` - Position sizing, stop-loss, circuit breakers, trade journaling
- **New Config:** `config/rpc_providers.json` - RPC endpoints for Solana, Ethereum, Base, Arbitrage, Polygon
- **New Doc:** `docs/trading_guide.md` - Comprehensive 540-line trading guide
- **Strategy Ensemble:** Weighted voting system for combining multiple strategies

### 🎙️ Streaming Consciousness (Voice Enhancement)

- **Enhanced Input Synthesis:** Entity extraction, intent classification, context linking
- **Ring Buffer Context:** Last 8,000 tokens (~30s) continuously buffered
- **Barge-In Prediction:** Audio cue detection (volume spike + pitch change)
- **Pre-Cached Responses:** Minimax predicts 3 likely user intents, pre-generates responses
- **Follow-Up Detection:** Identifies continuation of previous conversation topics

### 🔍 Action Verification Loops

- **Enhanced** `core/conversation.py` with `_extract_entities()`, `_classify_intent()`, `_synthesize_input()`
- **3-Step Verification:** Execute → Verify → Learn pattern for all actions
- **Satisfaction Tracking:** Monitors follow-up questions as proxy for response quality
- **Feedback Integration:** Action results feed back into learning system

### 🐛 Syntax Fixes

- **Fixed:** `core/actions.py` - f-string backslash errors in `compose_email()`, `create_calendar_event()`, `send_imessage()`, `set_reminder()`
- **Fixed:** `core/computer.py` - f-string backslash error in `type_text()`
- **Fixed:** `core/self_evaluator.py` - Mismatched if/else structure in `integrate_expansions()`
- **Note:** `core/iterative_improver_broken.py` intentionally broken (legacy code)

### 📚 Documentation

- **New:** `README_v2.md` - Complete rewrite showcasing Minimax 2.1, Mirror Test, Coliseum
- **New:** `docs/ARCHITECTURE_ANALYSIS_2026-01-01.md` - Senior Systems Architect analysis
- **Enhanced:** Architecture diagrams for intelligent routing vs waterfall fallback
- **Enhanced:** Cost comparison tables (Minimax vs GPT-4 vs Claude)

### ⚙️ Configuration

- **New:** `config/windsurf_settings.json` - Minimax 2.1 + MiniMax-Text-01 configuration
- **New:** `.idx/dev.nix` - Google IDX/Antigravity environment with Python 3.11 + trading deps
- **Enhanced:** Provider configuration with Minimax routing modes (CLOUD, LOCAL, BEAST)

### 📊 Cost & Performance Metrics

- **Cost Reduction:** 95% cheaper ($1.40/month vs $29/month for equivalent workload)
- **Latency:** Sub-200ms provider selection with parallel health checks
- **Context Window:** 200k tokens (Minimax 2.1) for complex reasoning tasks
- **Daily Spend Limit:** Configurable cost tracking with automatic fallback

### 🔧 Implementation Details

- **Mirror Test Cycle:** Runs at 3am daily (configurable via cron)
- **Coliseum Metrics:** Sharpe Ratio, Max Drawdown, Win Rate, Profit Factor
- **Backtest Windows:** 10 randomized 30-day periods from last 2 years
- **Deletion Threshold:** 5 consecutive failures OR Sharpe <0.5 OR Max Drawdown >25%
- **Promotion Threshold:** Sharpe >1.5, Win Rate >45%, Max Drawdown <25% across ALL tests

### 🎯 Roadmap Completion

- [x] Minimax 2.1 integration
- [x] Intelligent provider routing
- [x] Mirror Test self-correction
- [x] Paper-Trading Coliseum
- [x] Streaming consciousness voice
- [x] Action verification loops
- [x] Syntax error audit (105 modules)

---

# [0.9.1] - 2025-12-31

### 🔊 Voice + TTS
- Added barge-in support so Jarvis keeps listening while speaking and can be interrupted mid-response.
- Added self-echo suppression to stop the mic from re-feeding Jarvis's own TTS.
- Added local voice-clone engine (XTTS-v2) with optional Morgan Freeman reference support.
- Expanded Morgan Freeman voice handling with candidate selection and rate overrides.

### 🧠 Conversation Behavior
- Tightened execution bias and removed redundant follow-up prompts.
- Updated default conversation prompt guidance to avoid repeated questions.

### ⚙️ Providers + Config
- Removed deprecated Groq models and added `llama-3.3-70b-specdec` fallback.
- Updated local model ordering to match installed availability.
- Added barge-in and voice-clone settings to the main config.

### 📚 Docs
- Updated README with barge-in controls and local voice-cloning setup.

# [0.9.0] - 2025-12-30

### 🤖 Claude + GPT Hybrid Collaboration

This release represents a major milestone: **Claude Opus and GPT collaborated** to architect, implement, and refine Jarvis's trading research and autonomous capabilities. The hybrid approach combined Claude's deep reasoning with GPT's rapid iteration.

### 📊 Notion Deep Extraction System

- **New Module:** `core/notion_ingest.py` - API-based Notion page extraction with recursive block fetching
- **New Module:** `core/notion_scraper.py` - Playwright-based headless scraper for full content expansion
- **New Module:** `core/notion_tab_crawler.py` - Enhanced tab/toggle/database state-crawl for comprehensive extraction
- **New Module:** `core/notion_deep_extractor.py` - Deep recursive block fetcher using Notion's public API
- **Extracted 1,913 blocks** from Moon Dev's Algo Trading Roadmap
- **Parsed 81 trading strategies** into structured JSON catalog
- **Generated implementation plan** with architecture mapping and backtest checklist

### 📈 Trading Pipeline Enhancements

- **New Module:** `core/trading_pipeline.py` - End-to-end trading research pipeline
- **New Module:** `core/trading_youtube.py` - YouTube channel monitoring for trading content
- **New Module:** `core/trading_notion.py` - Notion-to-strategy extraction integration
- **New Module:** `core/liquidation_bot.py` - Liquidation-based trading signals (Hyperliquid/Moon Dev API)
- **New Module:** `core/solana_scanner.py` - Solana token scanner with Birdeye API integration
- **Strategy categories:** Trend following, carry trades, mean reversion, momentum, breakout, HMM regime detection

### 🧠 Agent Architecture

- **New Module:** `core/agent_graph.py` - Multi-agent graph orchestration
- **New Module:** `core/agent_router.py` - Intelligent routing between specialized agents
- **New Module:** `core/agents/` - Directory for specialized agent implementations
- **New Module:** `core/orchestrator.py` - High-level task orchestration
- **New Module:** `core/input_broker.py` - Unified input handling across voice/CLI/API
- **New Module:** `core/action_feedback.py` - Action result feedback loop

### 🔬 Self-Improvement Engine

- **New Module:** `core/self_improvement_engine.py` - Autonomous capability expansion
- **New Module:** `core/memory_driven_behavior.py` - Memory-first decision making
- **New Module:** `core/semantic_memory.py` - Semantic search over memory store
- **New Module:** `core/conversation_backtest.py` - Conversation replay for testing
- **New Module:** `core/enhanced_search_pipeline.py` - Multi-source research aggregation

### 🏥 Diagnostics & Reliability

- **New Module:** `core/mcp_doctor.py` - MCP server health diagnostics
- **New Module:** `core/mcp_doctor_simple.py` - Lightweight MCP health check
- **New Module:** `core/secret_hygiene.py` - Automated secrets scanning
- **New Module:** `core/objectives.py` - Goal tracking and progress measurement
- **New Module:** `core/vision_client.py` - Vision API integration for screen understanding
- **Added `lifeos doctor`** command for provider and MCP health checks

### 📚 Documentation

- **New:** `docs/handoff_claude_opus.md` - Handoff brief for Claude Opus collaboration
- **New:** `docs/HANDOFF_GPT5.md` - Future handoff template for GPT-5
- **New:** `docs/notion_extraction_guide.md` - Notion extraction methodology
- **Generated:** `data/notion_deep/strategy_catalog.json` - 81 strategies in structured format
- **Generated:** `data/notion_deep/implementation_plan.md` - Architecture and backtest plan
- **Generated:** `data/notion_deep/knowledge_base.md` - Master knowledge base

### 🧪 Testing Infrastructure

- **New:** `tests/test_trading_pipeline.py` - Trading pipeline tests
- **New:** `tests/test_trading_youtube.py` - YouTube ingestion tests
- **New:** `tests/test_liquidation_bot.py` - Liquidation bot tests
- **New:** `tests/test_solana_scanner.py` - Solana scanner tests
- **New:** `tests/test_conversation_backtest.py` - Conversation replay tests
- **New:** `test_*.py` - Various integration and unit tests

### 🔧 Fixes & Improvements

- Improved UI actions to accept keyword arguments (voice chat compatibility)
- Added Groq throttling and backoff to avoid rate limit storms
- Ollama fallback now gated by health check
- Readability extractor fixed for HTML decoding
- Enhanced error recovery with circuit breaker pattern

---

# [0.8.1] - 2025-12-30

### 📄 Docs
- Clarified secrets handling in the README with local-only key storage and do-not-share guidance.

# [0.8.0] - 2025-12-27

### 🧠 Behavior + Context
- Tightened conversational focus to avoid circular logic, added clearer research summaries with sources, and improved cross-session memory capture.
- Added Jarvis superintelligence context directives and prompt pack support for agency + website workflows.

### 🔊 Voice
- New Jarvis voice is live (macOS `say` fallback configured).

### 📈 Trading + Research
- Added Hyperliquid data ingestion (30-day snapshots) plus lightweight MA backtests and research notes.
- Switched trading research to DEX-first, low-fee chains (Solana/Base/BNB/Monad/Abstract), with DEX API scouting missions.
- Expanded autonomous research topics for security, network monitoring, and lightweight AI tools.

### 🛡️ Resource + Security Monitoring
- Always-on resource monitor with memory/CPU/disk alerts and periodic security scans.
- Network throughput + packet rate monitoring with logs.
- Process guard to flag heavy/abusive processes and optionally auto-terminate (opt-in).

### 🧩 Missions + MCP
- Added new idle missions: AI/security news scan, business suggestions, directive digest, and Hyperliquid backtest.
- Added YouTube transcript MCP server and a local transcript API fallback for faster ingestion.

### 🌐 Control Deck
- Rebuilt the local web UI as a control deck with system status, resource telemetry, mission triggers, research runs, and config toggles.
- Added Flask to requirements and expanded server endpoints for status, security logs, and actions.

### 🔧 Fixes
- Fixed boot self-tests for memory pipeline and added lightweight guardrails to reduce UI automation spam.
- Added DuckDuckGo Lite fallback for research search and fixed API server chat invocation.

### ✅ Testing
- Preliminary testing on this build looks good so far.

# [0.7.0] - 2025-12-26

### 🧩 MCP Autonomy Stack
- Added a dedicated MCP configuration (`lifeos/config/mcp.config.json`) declared in priority order, covering filesystem, dual memory layers, Obsidian REST, SQLite, system monitor, shell, Puppeteer, sequential thinking, and git servers.
- Mirrored the same stack inside Windsurf's `~/.codeium/windsurf/mcp_config.json` so the editor and LifeOS share the exact capabilities and storage paths.

### ⚙️ MCP Process Loader
- Introduced `core/mcp_loader.py`, a process supervisor that reads the MCP config, launches enabled servers with per-tool log files, and shuts them down cleanly.
- Wired the loader into `core/daemon.py` so MCP services start before the Jarvis boot sequence and are automatically stopped during shutdown.

### 🧠 System Instructions
- Authored `lifeos/config/system_instructions.md`, enforcing memory-first queries, structured decomposition, git safety rules, filesystem boundaries, and tool usage guidelines for Jarvis.

### ✅ Testing
- Verified the loader by launching every autostart server (filesystem, memory, obsidian-memory, mcp-obsidian, sqlite, system-monitor, shell, puppeteer, sequential-thinking, git) and confirmed clean shutdown.

## [0.6.0] - 2025-12-25

### 🚀 Major Features

#### Local Knowledge Base & Prompt Distillation
- All notes, research dumps, and scratchpads now save to `data/notes/` as `.md/.txt/.py`.
- Each capture auto-generates a distilled summary plus prompt-library snippet for reuse.
- CLI capture, voice `log`, and automation actions share the same pipeline for consistency.

#### Targeted Idle Missions
- Background scheduler now runs when the system is idle for 10+ minutes.
- Missions include:
  - **MoonDev Watcher** – curls the official MoonDevOnYT X feed.
  - **AlgoTradeCamp Digest** – snapshots algotradecamp.com for new strategies.
  - **MoonDev YouTube Harvester** – pulls transcripts via yt-dlp and summarizes key ideas.
  - **Self-Improvement Pulse** – inspects recent provider failures & memory to queue upgrades.
- Mission output lands in context docs *and* the local notes archive.

#### Offline Piper Voice
- Bundled Piper TTS support with automatic model download to `data/voices/`.
- `_speak` now prefers the local Piper engine, falling back to macOS `say` only if needed.
- Works without an internet connection while keeping the familiar voice preferences.

### 🔧 Improvements

- Added `core/youtube_ingest.py` helper for consistent transcript extraction.
- Guardian now whitelists key repo subdirectories so Jarvis can open/save local resources safely.
- Requirements updated with `yt-dlp` and `piper-tts` to support the new pipelines.

### 🐛 Fixes

- Stopped Jarvis from launching macOS Notes; local folder access no longer trips safety checks.
- Voice logging and CLI capture now report saved file locations for easy reference.

## [0.5.0] - 2024-12-24

### 🚀 Major Features

#### Proactive Monitoring System
- **15-minute suggestion cycle** - Jarvis now watches what you're doing and offers helpful suggestions every 15 minutes
- **Context-aware recommendations** - Suggestions based on current screen, recent activity, and your goals
- **macOS notifications** - Non-intrusive alerts when Jarvis has an idea for you
- **Suggestion logging** - All suggestions saved to `data/suggestions.jsonl` for review

#### Research & Document Creation
- **`research_topic(topic, depth)`** - Automated research with quick/medium/deep modes
- **`create_document(title, request)`** - AI-generated documents saved to `data/research/`
- **`search_free_software(category)`** - Find latest open-source tools in any category

#### Computer Control (Actions System)
- **Email composition** - `compose_email()`, `send_email()` via Mail.app or mailto:
- **Browser control** - `open_browser()`, `google()` for quick searches
- **App management** - `open_app()`, `switch_app()`, `close_window()`, `minimize()`
- **Keyboard shortcuts** - `copy()`, `paste()`, `cut()`, `undo()`, `select_all()`, `save()`
- **Notes & Reminders** - `create_note()`, `set_reminder()` integration
- **Calendar** - `create_calendar_event()` with date/time support
- **iMessage** - `send_imessage()` for quick messaging
- **Spotlight** - `spotlight_search()` for system-wide search

#### Conversational AI Upgrade
- **Natural conversation style** - No more robotic responses
- **Personality and warmth** - Jarvis now speaks like a brilliant friend
- **Proactive suggestions** - Points out opportunities without being asked
- **Action execution in chat** - Use `[ACTION: command()]` syntax to control Mac

### 🔧 Improvements

#### Provider System Overhaul
- **Smart provider ranking** - Free providers prioritized, ordered by intelligence
- **Groq integration** - Ultra-fast inference with Groq API (free tier)
- **Gemini CLI support** - Direct CLI integration for Gemini
- **Fixed Gemini 404 errors** - Updated all model names to valid 2.5 versions
- **Anthropic placeholder** - Ready for Claude API key

#### Self-Evolution System
- **Auto-evolve on boot** - Automatically applies pending safe improvements
- **Continuous improvement** - Analyzes errors and proposes fixes
- **Skill auto-installation** - New skills added without manual intervention
- **Safety validation** - Guardian checks all code before execution

#### Voice Chat
- **60-second silence timeout** - Chat no longer ends prematurely (was 10s)
- **Better command parsing** - More natural voice command recognition
- **Shutdown commands** - "Jarvis shut down", "goodbye Jarvis" etc.

#### Safety & Guardian System
- **Self-preservation rules** - Cannot delete own code or critical files
- **Code validation** - All generated code checked for dangerous patterns
- **Safety prompts** - Injected into all AI interactions
- **Protected paths** - Core system files locked from modification

### 🐛 Bug Fixes
- Fixed Gemini model 404 errors (gemini-1.5-flash → gemini-2.5-flash)
- Fixed chat ending due to silence after 10 seconds
- Fixed provider fallback not trying all available options
- Fixed evolution module import errors
- Fixed Ollama timeout issues (now 180s for model loading)

### 📁 New Files
- `core/actions.py` - Computer control action registry
- `core/proactive.py` - 15-minute monitoring and research system
- `core/guardian.py` - Safety constraints and code validation
- `core/jarvis.py` - Boot sequence, user profile, mission context
- `core/observer.py` - Deep activity observation
- `core/computer.py` - AppleScript computer control
- `lifeos/context/user_profile.md` - User goals and preferences

---

## [0.4.0] - 2024-12-23

### Added
- **Intelligent provider ranking** - Automatic selection of best available AI
- **Groq provider** - Fast, free inference option
- **Gemini CLI** - Alternative Gemini access method
- **Deep observer** - Full keyboard/mouse/screen logging (optional)
- **Guardian module** - Safety constraints for AI operations
- **Jarvis boot sequence** - System discovery and initialization

### Changed
- Provider order now prioritizes free options
- Ollama timeout increased for large model loading
- Config updated for better defaults

---

## [0.3.0] - 2024-12-22

### Added
- **Self-evolution system** - AI can propose and apply improvements
- **Skill system** - Modular capabilities in `skills/` directory
- **Memory routing** - Automatic categorization of notes
- **Activity summaries** - Injected into conversations

### Changed
- Conversation prompt includes more context
- Better error handling in providers

---

## [0.2.0] - 2024-12-20

### Added
- **Voice control** - Wake word detection with openwakeword
- **Chat mode** - Continuous conversation with context
- **Hotkey activation** - Ctrl+Shift+Up for quick access
- **Check-in system** - Scheduled prompts and interviews
- **Report generation** - Morning/afternoon summaries

### Changed
- Improved TTS with multiple voice options
- Better activity tracking resolution

---

## [0.1.0] - 2024-12-15

### Added
- Initial release
- **Passive observation** - Keyboard/mouse activity tracking
- **App tracking** - Monitor which apps are used
- **Context system** - Memory buffer and storage
- **CLI interface** - Basic commands (on, off, status, log)
- **Gemini integration** - Primary AI provider
- **Ollama support** - Local LLM option

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
- [ ] Plugin marketplace

---

## Contributing

Contributions welcome! Please read the safety guidelines in `core/guardian.py` before submitting code that modifies system behavior.

## License

MIT License - See LICENSE file for details.
