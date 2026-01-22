# Jarvis audit packet (minimized)

Generated: 2026-01-22 10:35:54
Working directory: C:\Users\lucid\OneDrive\Desktop\Projects\Jarvis
Note: .env values are redacted.

## data/ top-level listing (names only)

### data/ entries
```text
abilities/
activity_logs/
alerts/
analysis/
analytics/
audit/
autonomous_actions.log
autonomous_agents/
autonomous_controller.log
autonomous_research/
backtests/
boot_reports/
bot_health.db
brain/
browser_automation/
budget/
cache/
calendar/
call_tracking.db
community/
console_requests.json
context/
context_docs/
context_state.json
cooldown_state.json
cross_system_state.json
crypto_trading/
custom.db
dexter/
discoveries.jsonl
distributions.db
dlq/
error_recovery.log
expansions/
feature_flags.json
google_cli/
google_data/
health/
health.db
intelligence/
iterative_improvements/
jarvis.db
jarvis.db-shm
jarvis.db-wal
jarvis_admin.db
jarvis_memory.db
jarvis_spam_protection.db
jarvis_state.json
jarvis_x_memory.db
jarvis_x_memory.db-shm
jarvis_x_memory.db-wal
key_rotation_metadata.json
learning/
limit_orders.json
llm_costs.db
locks/
logs/
memory/
metrics/
metrics.db
missions/
ml/
models/
moderation/
objectives/
onchain_cache/
paper_trading/
performance/
portfolio/
position_closures.csv
positions/
predictions/
proactive/
prompt_library.json
raid_bot.db
rate_limiter.db
recycle_test.db
research/
research.db
research_docs/
resource_monitor/
restarts/
revenue/
self_evaluation/
self_healing/
self_upgrade_queue.json
sentiment.db
tax.db
telegram_memory.db
telegram_sessions/
tests/
trader/
treasury_keypair.json
treasury_keypair.json.bak
treasury_orders.json
treasury_scorekeeper.json
treasury_trades.db
twitter/
validation_proof/
validations/
voices/
wallet/
whales.db
```

## Key file search results

### Search: positions.json
```text
C:\Users\lucid\OneDrive\Desktop\Projects\Jarvis\data\trader\positions.json
```

### Search: trade_history.json
```text
_Not found_
```

### Search: .trade_history.json
```text
C:\Users\lucid\OneDrive\Desktop\Projects\Jarvis\bots\treasury\.trade_history.json
```

### Search: context_state.json
```text
C:\Users\lucid\OneDrive\Desktop\Projects\Jarvis\data\context_state.json
```

### Search: .sentiment_poster_state.json
```text
_Not found_
```

## Key file contents

### data/context_state.json
Path: `data\context_state.json`
```json
{
  "last_sentiment_report": "2026-01-22T10:18:33.331225",
  "last_tweet": "2026-01-21T01:41:40.272854",
  "last_full_report": null,
  "startup_count_today": 4,
  "last_startup_date": "2026-01-22",
  "sentiment_cache_valid": true
}
```

### data/jarvis_state.json
Path: `data\jarvis_state.json`
```json
{
  "boot_count": 18,
  "last_boot": 1768879995.957705,
  "last_discovery_check": 1768795610.0811453,
  "discovered_resources": [],
  "self_improvements": [],
  "user_profile": {
    "name": "User",
    "linkedin": "yourprofile",
    "primary_goals": [
      "Make money through automation and smart decisions",
      "Help humanity through technology",
      "Build autonomous systems that work for me",
      "Achieve financial freedom"
    ],
    "businesses": [],
    "interests": [
      "AI and automation",
      "Crypto trading",
      "Algorithmic trading",
      "Self-improvement",
      "Creative agency workflows"
    ],
    "trading_focus": "crypto algorithmic trading",
    "mentor_channels": [
      "Moon Dev"
    ],
    "last_interview": 0
  }
}
```

### data/trader/positions.json
Path: `data\trader\positions.json`
```json
[
  {
    "id": "81d7b910",
    "token_mint": "So11111111111111111111111111111111111111112",
    "token_symbol": "SOL",
    "direction": "LONG",
    "entry_price": 100.0,
    "current_price": 100.0,
    "amount": 0.5,
    "amount_usd": 50.0,
    "take_profit_price": 130.0,
    "stop_loss_price": 92.0,
    "status": "OPEN",
    "opened_at": "2026-01-21T08:15:13.481565",
    "closed_at": null,
    "exit_price": null,
    "pnl_usd": 0.0,
    "pnl_pct": 0.0,
    "sentiment_grade": "A",
    "sentiment_score": 0.0,
    "tp_order_id": null,
    "sl_order_id": null
  }
]
```

### bots/treasury/.trade_history.json
Path: `bots\treasury\.trade_history.json`
```json
[
  {
    "id": "b4ebd181",
    "token_mint": "5zaGbQSZk2pSSugnKojH3NxpVkcvGFqQbYH6fuuofAAA",
    "token_symbol": "TEST",
    "direction": "LONG",
    "entry_price": 0.1666,
    "current_price": 0.1666,
    "amount": 0.00088365,
    "amount_usd": 0.00147058,
    "take_profit_price": 114.99999999999999,
    "stop_loss_price": 95.0,
    "status": "CLOSED",
    "opened_at": "2026-01-14T17:33:06.791670",
    "closed_at": "2026-01-14T17:41:49.595605",
    "exit_price": 0.1668,
    "pnl_usd": 1.7654021608643963e-06,
    "pnl_pct": 0.12004801920768651,
    "sentiment_grade": "B",
    "sentiment_score": 0.0,
    "tp_order_id": "0d01fdf9",
    "sl_order_id": "ec8725d0"
  },
  {
    "id": "7b408e14",
    "token_mint": "XsbEhLAtcf6HdfpFZ5xEMdqW8nfAvcsP5bdudRLJzJp",
    "token_symbol": "AAPLx",
    "direction": "LONG",
    "entry_price": 259.14,
    "current_price": 259.14,
    "amount": 5.69e-07,
    "amount_usd": 0.00147058,
    "take_profit_price": 110.0,
    "stop_loss_price": 96.0,
    "status": "CLOSED",
    "opened_at": "2026-01-14T17:33:08.486747",
    "closed_at": "2026-01-14T17:41:50.508807",
    "exit_price": 256.9,
    "pnl_usd": -1.2711658562939004e-05,
    "pnl_pct": -0.8643976229065405,
    "sentiment_grade": "B",
    "sentiment_score": 0.0,
    "tp_order_id": "5295d4ca",
    "sl_order_id": "9845197c"
  },
  {
    "id": "9a31c69e",
    "token_mint": "7TBD7QD9kyzwADErHusNtVWzSBdtG8j4aYJuXadNpump",
    "token_symbol": "MWHALE",
    "direction": "LONG",
    "entry_price": 3.152e-05,
    "current_price": 2.568e-05,
    "amount": 17.36091455,
    "amount_usd": 0.5605238457420001,
    "take_profit_price": 3.6248e-05,
    "stop_loss_price": 2.9944e-05,
    "status": "CLOSED",
    "opened_at": "2026-01-13T19:02:57.124806",
    "closed_at": "2026-01-14T02:06:51.400242",
    "exit_price": 2.898e-05,
    "pnl_usd": -0.045169117010935324,
    "pnl_pct": -8.058375634517773,
    "sentiment_grade": "B",
    "sentiment_score": 0.0,
    "tp_order_id": "e8f5a4dd",
    "sl_order_id": "5621c78f"
  },
  {
    "id": "bc43a63c",
    "token_mint": "Fp4fmsksrLAhcejVmCBrfAZfxbSaA1EWpK1A2Va5f147",
    "token_symbol": "USOR",
    "direction": "LONG",
    "entry_price": 0.001805,
    "current_price": 0.001805,
    "amount": 0.287141659,
    "amount_usd": 0.5189714881755,
    "take_profit_price": 0.0023465,
    "stop_loss_price": 0.0016245,
    "status": "CLOSED",
    "opened_at": "2026-01-13T19:43:56.023024",
    "closed_at": "2026-01-14T02:06:53.313472",
    "exit_price": 1.161e-07,
    "pnl_usd": -0.5189381072393353,
    "pnl_pct": -99.99356786703602,
    "sentiment_grade": "B",
    "sentiment_score": 0.0,
    "tp_order_id": "cb3213ac",
    "sl_order_id": "c3887cab"
  },
  {
    "id": "dfdc2e1f",
    "token_mint": "5sUsbK5kn1TyeWHiSox1e9AAgUDnZ8JqCMXXweP1pump",
    "token_symbol": "CLEPE",
    "direction": "LONG",
    "entry_price": 0.0009238,
    "current_price": 2.812e-06,
    "amount": 16.49215236,
    "amount_usd": 14.888302055025,
    "take_profit_price": 0.00120588,
    "stop_loss_price": 0.00083484,
    "status": "CLOSED",
    "opened_at": "2026-01-14T05:45:47.370849",
    "closed_at": "2026-01-14T07:06:22.872611",
    "exit_price": 3.538e-06,
    "pnl_usd": -14.831282340075141,
    "pnl_pct": -99.61701667027495,
    "sentiment_grade": "B",
    "sentiment_score": 0.0,
    "tp_order_id": "70b34389",
    "sl_order_id": "7f005c1c"
  },
  {
    "id": "515b841f",
    "token_mint": "G4nnWeNt2uBGg4LpkccxUTJhNqUhWsaEhigkVfWYpump",
    "token_symbol": "jeff",
    "direction": "LONG",
    "entry_price": 0.0003609,
    "current_price": 4.783e-06,
    "amount": 53.840732271,
    "amount_usd": 0.6066917756319999,
    "take_profit_price": 0.0005411999999999999,
    "stop_loss_price": 0.00030668,
    "status": "CLOSED",
    "opened_at": "2026-01-13T06:48:54.234584",
    "closed_at": "2026-01-15T02:00:00.000000",
    "exit_price": 4.783e-06,
    "pnl_usd": -0.5986,
    "pnl_pct": -98.67,
    "sentiment_grade": "B",
    "sentiment_score": 0.0,
    "tp_order_id": "63bdd216",
    "sl_order_id": "a7ec4ff1"
  },
  {
    "id": "3101cd8a",
    "token_mint": "2GL3PTYVE4J85HRuySaLsK1HK9cVkG34UQJDkQHbBAGS",
    "token_symbol": "SUPARALPH",
    "direction": "LONG",
    "entry_price": 5.778e-05,
    "current_price": 5.778e-05,
    "amount": 22159.860077337,
    "amount_usd": 1.3175871656088751,
    "take_profit_price": 6.6447e-05,
    "stop_loss_price": 5.489099999999999e-05,
    "status": "CLOSED",
    "opened_at": "2026-01-16T05:14:03.134527",
    "closed_at": "2026-01-16T05:15:10.976569",
    "exit_price": 7.077e-05,
    "pnl_usd": 0.29621767534197463,
    "pnl_pct": 22.481827622014546,
    "sentiment_grade": "B",
    "sentiment_score": 0.0,
    "tp_order_id": "7489ba81",
    "sl_order_id": "c9a3c703"
  },
  {
    "id": "3c7ae826",
    "token_mint": "5ceJY97nRc2GYzA6N51FpYCMMcWVxWfxTVFVzuX3BAGS",
    "token_symbol": "VIBECODOOR",
    "direction": "LONG",
    "entry_price": 5.118e-06,
    "current_price": 5.118e-06,
    "amount": 248601.253253172,
    "amount_usd": 1.2980397370612504,
    "take_profit_price": 5.885699999999999e-06,
    "stop_loss_price": 4.8621e-06,
    "status": "CLOSED",
    "opened_at": "2026-01-16T07:35:28.197361",
    "closed_at": "2026-01-16T13:27:47.794020",
    "exit_price": 4.609e-06,
    "pnl_usd": -0.1290938308253568,
    "pnl_pct": -9.945291129347396,
    "sentiment_grade": "B",
    "sentiment_score": 0.0,
    "tp_order_id": "f0b17f2f",
    "sl_order_id": "0d067d68"
  },
  {
    "id": "567743bd",
    "token_mint": "XsjQP3iMAaQ3kQScQKthQpx9ALRbjKAjQtHg6TFomoc",
    "token_symbol": "TQQQx",
    "direction": "LONG",
    "entry_price": 108.84155623078331,
    "current_price": 114.35,
    "amount": 0.019559161999999998,
    "amount_usd": 22.13239023151,
    "take_profit_price": 114.7716,
    "stop_loss_price": 103.08189999999999,
    "status": "CLOSED",
    "opened_at": "2026-01-15T01:33:35.411295",
    "closed_at": "2026-01-17T17:31:56.799721",
    "exit_price": 107.24,
    "pnl_usd": -0.3256685103090936,
    "pnl_pct": -1.4714565706754874,
    "sentiment_grade": "B",
    "sentiment_score": 0.0,
    "tp_order_id": "17b6faee",
    "sl_order_id": "dde9f4d8"
  },
  {
    "id": "6bea4d9b",
    "token_mint": "So11111111111111111111111111111111111111112",
    "token_symbol": "SOL",
    "direction": "LONG",
    "entry_price": 100.0,
    "current_price": 150.0,
    "amount": 1.0,
    "amount_usd": 100.0,
    "take_profit_price": 130.0,
    "stop_loss_price": 92.0,
    "status": "CLOSED",
    "opened_at": "2026-01-18T18:33:50.933746",
    "closed_at": "2026-01-18T18:33:50.959510",
    "exit_price": 100.0,
    "pnl_usd": 0.0,
    "pnl_pct": 0.0,
    "sentiment_grade": "A",
    "sentiment_score": 0.5,
    "tp_order_id": null,
    "sl_order_id": null
  },
  {
    "id": "42d33887",
    "token_mint": "So11111111111111111111111111111111111111112",
    "token_symbol": "SOL",
    "direction": "LONG",
    "entry_price": 100.0,
    "current_price": 150.0,
    "amount": 1.0,
    "amount_usd": 100.0,
    "take_profit_price": 130.0,
    "stop_loss_price": 92.0,
    "status": "CLOSED",
    "opened_at": "2026-01-18T18:36:14.831941",
    "closed_at": "2026-01-18T18:36:14.854994",
    "exit_price": 100.0,
    "pnl_usd": 0.0,
    "pnl_pct": 0.0,
    "sentiment_grade": "A",
    "sentiment_score": 0.5,
    "tp_order_id": null,
    "sl_order_id": null
  },
  {
    "id": "e8aed574",
    "token_mint": "So11111111111111111111111111111111111111112",
    "token_symbol": "SOL",
    "direction": "LONG",
    "entry_price": 100.0,
    "current_price": 150.0,
    "amount": 1.0,
    "amount_usd": 100.0,
    "take_profit_price": 130.0,
    "stop_loss_price": 92.0,
    "status": "CLOSED",
    "opened_at": "2026-01-18T18:36:29.687558",
    "closed_at": "2026-01-18T18:36:29.712643",
    "exit_price": 100.0,
    "pnl_usd": 0.0,
    "pnl_pct": 0.0,
    "sentiment_grade": "A",
    "sentiment_score": 0.5,
    "tp_order_id": null,
    "sl_order_id": null
  },
  {
    "id": "73f0670d",
    "token_mint": "So11111111111111111111111111111111111111112",
    "token_symbol": "SOL",
    "direction": "LONG",
    "entry_price": 100.0,
    "current_price": 150.0,
    "amount": 1.0,
    "amount_usd": 100.0,
    "take_profit_price": 130.0,
    "stop_loss_price": 92.0,
    "status": "CLOSED",
    "opened_at": "2026-01-18T18:37:12.738589",
    "closed_at": "2026-01-18T18:37:12.762102",
    "exit_price": 100.0,
    "pnl_usd": 0.0,
    "pnl_pct": 0.0,
    "sentiment_grade": "A",
    "sentiment_score": 0.5,
    "tp_order_id": null,
    "sl_order_id": null
  },
  {
    "id": "420b80b7",
    "token_mint": "So11111111111111111111111111111111111111112",
    "token_symbol": "SOL",
    "direction": "LONG",
    "entry_price": 100.0,
    "current_price": 150.0,
    "amount": 1.0,
    "amount_usd": 100.0,
    "take_profit_price": 130.0,
    "stop_loss_price": 92.0,
    "status": "CLOSED",
    "opened_at": "2026-01-18T18:38:38.345744",
    "closed_at": "2026-01-18T18:38:38.391653",
    "exit_price": 100.0,
    "pnl_usd": 0.0,
    "pnl_pct": 0.0,
    "sentiment_grade": "A",
    "sentiment_score": 0.5,
    "tp_order_id": null,
    "sl_order_id": null
  }
]
```

## Config and env (env values redacted)

### .env
Path: `.env`
```bash
# ============================================
# VPS DEPLOYMENT CREDENTIALS
# CRITICAL: Never commit this file to git
# ============================================

# Bags.fm API (trading/swaps)
BAGS_API_KEY=<REDACTED>
USE_BAGS_TRADING=<REDACTED>

# Bitquery API (bags_intel real-time monitoring)
BITQUERY_API_KEY=<REDACTED>

# Semantic memory database
DATABASE_URL=<REDACTED>

# Hostinger VPS Configuration
VPS_HOST=<REDACTED>
VPS_USERNAME=<REDACTED>
VPS_PASSWORD=<REDACTED>

# SSH Configuration
VPS_SSH_PORT_PRIMARY=<REDACTED>
VPS_SSH_PORT_ALTERNATE=<REDACTED>

# Deployment Configuration
JARVIS_LOCAL_PATH=<REDACTED>
DEPLOYMENT_TIMEOUT=<REDACTED>
RETRY_INTERVAL=<REDACTED>

# ============================================
# SECURITY REMINDERS
# ============================================
# 1. NEVER push this file to GitHub
# 2. Rotate VPS_PASSWORD in Hostinger hPanel after deployment
# 3. Use os.environ.get('VPS_PASSWORD') in scripts
# 4. Delete this file after first deployment
# ============================================

```

### env.example
Path: `env.example`
```bash
# ============================================================================
# JARVIS Configuration Template
# ============================================================================
# Copy this file to .env and fill in your values
# Never commit .env to version control!
# ============================================================================

# -----------------------------------------------------------------------------
# General Configuration
# -----------------------------------------------------------------------------

# Environment: development, staging, production
NODE_ENV=<REDACTED>

# Data directory for logs, databases, caches
DATA_DIR=<REDACTED>

# Logging level: DEBUG, INFO, WARNING, ERROR
LOG_LEVEL=<REDACTED>

# -----------------------------------------------------------------------------
# API Configuration
# -----------------------------------------------------------------------------

# FastAPI server settings
API_HOST=<REDACTED>
API_PORT=<REDACTED>
API_RELOAD=<REDACTED>

# CORS allowed origins (comma-separated)
CORS_ORIGINS=<REDACTED>

# Flask server (legacy API)
FLASK_HOST=<REDACTED>
FLASK_PORT=<REDACTED>

# -----------------------------------------------------------------------------
# Solana Configuration
# -----------------------------------------------------------------------------

# Network: mainnet-beta, devnet, testnet
SOLANA_NETWORK=<REDACTED>

# RPC endpoints
SOLANA_RPC_URL=<REDACTED>
SOLANA_WS_URL=<REDACTED>

# Premium RPC (Helius, QuickNode, etc)
HELIUS_API_KEY=
HELIUS_RPC_URL=

# Wallet paths (NEVER commit actual key files!)
TREASURY_WALLET_PATH=<REDACTED>
ACTIVE_WALLET_PATH=<REDACTED>
PROFIT_WALLET_PATH=<REDACTED>

# Program IDs
STAKING_PROGRAM_ID=<REDACTED>
KR8TIV_MINT=<REDACTED>

# -----------------------------------------------------------------------------
# Bags.fm Integration
# -----------------------------------------------------------------------------

# Enable Bags.fm fee collection
ENABLE_BAGS_INTEGRATION=<REDACTED>

# Bags.fm API settings
BAGS_API_URL=<REDACTED>
BAGS_PARTNER_CODE=
BAGS_PARTNER_SECRET=

# Fee collector settings
BAGS_REFERRAL_WALLET=
BAGS_FEE_COLLECTION_INTERVAL_HOURS=<REDACTED>

# -----------------------------------------------------------------------------
# Bags Intel (Token Launch Intelligence)
# -----------------------------------------------------------------------------

# Bitquery API for real-time WebSocket monitoring of graduations
# Get from: https://graphql.bitquery.io/
BITQUERY_API_KEY=

# Intel report thresholds
BAGS_INTEL_MIN_MCAP=<REDACTED>
BAGS_INTEL_MIN_SCORE=<REDACTED>

# -----------------------------------------------------------------------------
# Stripe Integration (Credits System)
# -----------------------------------------------------------------------------

STRIPE_SECRET_KEY=
STRIPE_PUBLISHABLE_KEY=
STRIPE_WEBHOOK_SECRET=

# Stripe price IDs for credit packages
STRIPE_PRICE_STARTER=
STRIPE_PRICE_PRO=
STRIPE_PRICE_WHALE=

# -----------------------------------------------------------------------------
# Treasury Configuration
# -----------------------------------------------------------------------------

# Allocation percentages (must sum to 100)
TREASURY_RESERVE_PCT=<REDACTED>
TREASURY_ACTIVE_PCT=<REDACTED>
TREASURY_PROFIT_PCT=<REDACTED>

# Treasury trading controls
TREASURY_LIVE_MODE=<REDACTED>
JARVIS_WALLET_PASSWORD=

# Risk management
CIRCUIT_BREAKER_THRESHOLD=<REDACTED>
MAX_SINGLE_TRADE_PCT=<REDACTED>
DAILY_LOSS_LIMIT_PCT=<REDACTED>

# Bags fee allocation (must sum to 100)
BAGS_STAKING_REWARDS_PCT=<REDACTED>
BAGS_OPERATIONS_PCT=<REDACTED>
BAGS_DEVELOPMENT_PCT=<REDACTED>

# -----------------------------------------------------------------------------
# Database Configuration
# -----------------------------------------------------------------------------

# SQLite (default)
DATABASE_URL=<REDACTED>

# PostgreSQL (production)
# DATABASE_URL=postgresql://user:password@localhost:5432/jarvis

# Redis (caching, sessions)
REDIS_URL=<REDACTED>

# -----------------------------------------------------------------------------
# External APIs
# -----------------------------------------------------------------------------

# OpenAI (for AI features)
OPENAI_API_KEY=

# Anthropic (for Claude)
ANTHROPIC_API_KEY=

# xAI Grok
XAI_API_KEY=
XAI_MODEL=<REDACTED>

# Groq (Free tier: 30 req/min)
# Get API key: https://console.groq.com
GROQ_API_KEY=
GROQ_MODEL=<REDACTED>

# Ollama (Local, free, private)
# Install: https://ollama.ai
OLLAMA_URL=<REDACTED>
OLLAMA_MODEL=<REDACTED>

# OpenRouter (Access to many models)
# Get API key: https://openrouter.ai
OPENROUTER_API_KEY=
OPENROUTER_MODEL=<REDACTED>

# DexScreener
DEXSCREENER_API_URL=<REDACTED>

# Birdeye (Solana token data)
BIRDEYE_API_KEY=

# Jupiter (DEX aggregator)
JUPITER_API_URL=<REDACTED>

# Commodity pricing (optional)
METALS_API_KEY=
GOLD_API_KEY=

# Telegram Bot
TELEGRAM_BOT_TOKEN=
TELEGRAM_ADMIN_CHAT_ID=
TELEGRAM_ADMIN_IDS=

# Telegram Broadcast - Main group for sentiment digests
# If not set, falls back to TELEGRAM_BUY_BOT_CHAT_ID
TELEGRAM_BROADCAST_CHAT_ID=

# Telegram Buy Bot (optional separate token/chat)
TELEGRAM_BUY_BOT_TOKEN=
TELEGRAM_BUY_BOT_CHAT_ID=
BUY_BOT_ENABLE_POLLING=<REDACTED>

# Telegram reply automation
TG_REPLY_MODE=<REDACTED>
TG_REPLY_COOLDOWN_SECONDS=<REDACTED>
TG_REPLY_MODEL=<REDACTED>
TG_CLAUDE_MODEL=<REDACTED>

# Treasury admin overrides (comma-separated Telegram user IDs)
TREASURY_ADMIN_IDS=

# X (Twitter) API
X_API_KEY=
X_API_SECRET=
X_ACCESS_TOKEN=
X_ACCESS_TOKEN_SECRET=
X_BEARER_TOKEN=
X_EXPECTED_USERNAME=<REDACTED>

# X OAuth 2.0 (recommended)
X_OAUTH2_CLIENT_ID=
X_OAUTH2_CLIENT_SECRET=
X_OAUTH2_ACCESS_TOKEN=
X_OAUTH2_REFRESH_TOKEN=
X_OAUTH2_REDIRECT_URI=<REDACTED>

# Optional video attachment (Grok Imagine)
X_VIDEO_PATH=
X_VIDEO_DIR=

# Discord Webhooks
DISCORD_WEBHOOK_ALERTS=
DISCORD_WEBHOOK_TRADES=

# -----------------------------------------------------------------------------
# Voice Configuration (TTS/STT)
# -----------------------------------------------------------------------------

VOICE_ENABLED=<REDACTED>
SPEAK_RESPONSES=<REDACTED>
BARGE_IN_ENABLED=<REDACTED>

# ElevenLabs TTS
ELEVENLABS_API_KEY=
ELEVENLABS_VOICE_ID=

# OpenAI Whisper (STT)
WHISPER_MODEL=<REDACTED>

# -----------------------------------------------------------------------------
# Frontend Configuration
# -----------------------------------------------------------------------------

# Vite dev server
VITE_API_URL=<REDACTED>
VITE_WS_URL=<REDACTED>

# Wallet adapter
VITE_SOLANA_NETWORK=<REDACTED>

# -----------------------------------------------------------------------------
# Security
# -----------------------------------------------------------------------------

# JWT secret for API authentication
JWT_SECRET=<REDACTED>

# API rate limiting
RATE_LIMIT_REQUESTS=<REDACTED>
RATE_LIMIT_WINDOW_SECONDS=<REDACTED>

# Allowed IP addresses (comma-separated, empty = all)
ALLOWED_IPS=

# -----------------------------------------------------------------------------
# Monitoring & Observability
# -----------------------------------------------------------------------------

# Sentry error tracking
SENTRY_DSN=

# Prometheus metrics
METRICS_ENABLED=<REDACTED>
METRICS_PORT=<REDACTED>

# Health check endpoint
HEALTH_CHECK_PATH=<REDACTED>

# -----------------------------------------------------------------------------
# Development Tools
# -----------------------------------------------------------------------------

# Hot reload
WATCH_FILES=<REDACTED>

# Debug mode (extra logging)
DEBUG=<REDACTED>

# Test mode (uses test databases/mocks)
TEST_MODE=<REDACTED>

```

### config.yaml
Path: `config.yaml`
```yaml
# ============================================================================
# JARVIS Master Configuration File
#
# This unified configuration file replaces all scattered config files.
# All secrets should be provided via environment variables.
#
# Environment Variable Expansion:
#   ${VAR_NAME}          - Replace with environment variable
#   ${VAR_NAME:default}  - Use default if not set
#
# Usage:
#   from core.config.unified_config import get_unified_config
#   config = get_unified_config()
#   api_key = config.get("twitter.api_key")
# ============================================================================

general:
  name: "Jarvis"
  version: "4.6.3"
  debug: ${DEBUG:false}
  log_level: ${LOG_LEVEL:INFO}
  data_dir: ${LIFEOS_HOME:~/.lifeos}

# ============================================================================
# Trading Configuration
# ============================================================================
trading:
  enabled: ${TRADING_ENABLED:false}
  live_mode: ${TREASURY_LIVE_MODE:false}
  paper_mode: true

  # Position management
  max_positions: 50
  max_position_pct: 0.25  # 25% of portfolio per position
  daily_loss_limit_pct: 0.10  # 10% daily loss limit

  # Execution parameters
  default_slippage_pct: 0.01  # 1% slippage tolerance
  slippage_bps: 50  # 50 basis points for Jupiter

  # Jupiter DEX integration
  rpc_url: ${RPC_URL:https://api.mainnet-beta.solana.com}
  jupiter_api_url: https://api.jup.ag

  # Dry run mode
  dry_run: ${DRY_RUN:true}

# ============================================================================
# Twitter / X Bot Configuration
# ============================================================================
twitter:
  enabled: ${X_BOT_ENABLED:false}

  # API Credentials (OAuth 1.0a)
  api_key: ${X_API_KEY}
  api_secret: ${X_API_SECRET}
  access_token: ${X_ACCESS_TOKEN}
  access_token_secret: ${X_ACCESS_TOKEN_SECRET}
  bearer_token: ${X_BEARER_TOKEN}

  # OAuth 2.0 (recommended for posting)
  oauth2_client_id: ${X_OAUTH2_CLIENT_ID}
  oauth2_client_secret: ${X_OAUTH2_CLIENT_SECRET}
  oauth2_access_token: ${X_OAUTH2_ACCESS_TOKEN}
  oauth2_refresh_token: ${X_OAUTH2_REFRESH_TOKEN}
  oauth2_redirect_uri: ${X_OAUTH2_REDIRECT_URI:http://localhost:8888/callback}

  # Account settings
  expected_username: ${X_EXPECTED_USERNAME:jarvis_lifeos}

  # Grok API (for sentiment analysis)
  grok_api_key: ${XAI_API_KEY}
  grok_model: grok-3
  grok_image_model: grok-2-image

  # Rate limiting & circuit breaker
  polling_interval: 60  # seconds
  min_tweet_interval: 1800  # 30 minutes between tweets
  circuit_breaker_cooldown: 1800  # 30 minutes cooldown after 3 errors
  circuit_breaker_error_threshold: 3

  # Engagement settings
  auto_reply: true
  reply_probability: 0.3  # Reply to 30% of mentions
  like_mentions: true
  max_replies_per_hour: 5
  mention_check_interval: 60  # seconds

  # Posting schedule (24-hour format, UTC)
  schedule:
    8: morning_report      # 8 AM - Morning market overview
    10: token_spotlight    # 10 AM - Trending token spotlight
    12: stock_picks        # 12 PM - Stock picks from Grok
    14: macro_update       # 2 PM - Macro/geopolitical update
    16: commodities        # 4 PM - Commodities & precious metals
    18: grok_insight       # 6 PM - Grok wisdom/insight
    20: evening_wrap       # 8 PM - Evening market wrap

# ============================================================================
# Telegram Bot Configuration
# ============================================================================
telegram:
  enabled: ${TELEGRAM_ENABLED:false}

  # Bot Token
  bot_token: ${TELEGRAM_BOT_TOKEN}

  # Admin security - only these users can run commands
  admin_ids: ${TELEGRAM_ADMIN_IDS}  # Format: "123456789,987654321"

  # Chat configuration
  broadcast_chat_id: ${TELEGRAM_BROADCAST_CHAT_ID}
  buy_bot_chat_id: ${TELEGRAM_BUY_BOT_CHAT_ID}

  # Polling
  polling_interval: 1.0  # seconds

  # Rate limiting & cost control
  sentiment_interval_seconds: 3600  # 1 hour minimum between checks
  max_sentiment_per_day: 24
  daily_cost_limit_usd: 10.00  # Stop if daily cost exceeds this

  # LLM settings
  grok_api_key: ${XAI_API_KEY}
  grok_model: grok-3-mini

  anthropic_api_key: ${ANTHROPIC_API_KEY}
  claude_model: claude-sonnet-4-20250514
  claude_max_tokens: 1024

  # Data APIs
  birdeye_api_key: ${BIRDEYE_API_KEY}  # For token data

  # Database
  db_path: ${HOME:~}/.lifeos/telegram/jarvis_secure.db

  # Digest schedule (UTC hours)
  digest_hours: [8, 14, 20]

  # Paper trading
  paper_starting_balance: 100.0  # SOL
  paper_max_position_pct: 0.20
  paper_slippage_pct: 0.003

  # Treasury integration
  low_balance_threshold: ${LOW_BALANCE_THRESHOLD:0.01}  # SOL

  # Security
  log_api_calls: false  # Never log actual API responses
  mask_addresses: true  # Truncate addresses in logs

# ============================================================================
# Buy Tracker Configuration
# ============================================================================
buy_tracker:
  enabled: ${BUY_TRACKER_ENABLED:false}

  # Telegram settings
  bot_token: ${TELEGRAM_BUY_BOT_TOKEN:${TELEGRAM_BOT_TOKEN}}
  chat_id: ${TELEGRAM_BUY_BOT_CHAT_ID}

  # Token tracking
  token_symbol: ${BUY_BOT_TOKEN_SYMBOL:KR8TIV}
  token_name: ${BUY_BOT_TOKEN_NAME:Kr8Tiv}
  token_address: ${BUY_BOT_TOKEN_ADDRESS}
  pair_address: ${BUY_BOT_PAIR_ADDRESS}

  # RPC settings
  rpc_url: ${RPC_URL:https://api.mainnet-beta.solana.com}
  helius_api_key: ${HELIUS_API_KEY}
  websocket_url: ${WEBSOCKET_URL}

  # Notification settings
  min_buy_usd: 5.0  # Minimum buy amount in USD to notify
  bot_name: "Jarvis Buy Bot Tracker"
  buy_emoji: "🤖"

# ============================================================================
# LLM / AI Configuration
# ============================================================================
llm:
  provider: ${LLM_PROVIDER:groq}
  model: ${LLM_MODEL:llama-3.3-70b-versatile}
  temperature: 0.7
  max_tokens: 500
  fallback_provider: ${LLM_FALLBACK:ollama}

# ============================================================================
# Persona Configuration
# ============================================================================
persona:
  default: jarvis
  voice_enabled: false
  voice_id: morgan_freeman

# ============================================================================
# Plugins Configuration
# ============================================================================
plugins:
  enabled: true
  auto_load: true
  directories:
    - plugins

# ============================================================================
# Memory Configuration
# ============================================================================
memory:
  # Memory store settings
  db_path: ${HOME:~}/.lifeos/memory.db
  max_history: 1000

  # TTL settings (hours)
  trading_ttl_hours: 24
  scratch_ttl_hours: 1
  duplicate_intent_hours: 1  # Issue #1: idempotency window

  # Backup settings (Issue #2)
  backup_dir: ${HOME:~}/.lifeos/trading/backups
  backup_interval_hours: 1
  backup_retention_hours: 24

# ============================================================================
# Event Bus Configuration
# ============================================================================
events:
  max_history: 1000
  max_dead_letters: 100

  # Queue settings
  max_queue_size: 1000
  handler_timeout: 30.0  # seconds (Issue #4 fix)

  # Dead letter queue retention
  dlq_retention: 100

# ============================================================================
# Notifications Configuration
# ============================================================================
notifications:
  desktop_enabled: true
  sound_enabled: true

# ============================================================================
# Monitoring Configuration
# ============================================================================
monitoring:
  health_check_interval: 30  # seconds
  metrics_enabled: true
  log_level: INFO

# ============================================================================
# API Configuration
# ============================================================================
api:
  rate_limit_per_minute: 60
  timeout_seconds: 30
  retry_attempts: 3

# ============================================================================
# Security Configuration
# ============================================================================
security:
  require_auth: true
  session_timeout_minutes: 60
  max_failed_logins: 5
  kill_switch: ${LIFEOS_KILL_SWITCH:false}

# ============================================================================
# Bot Configuration
# ============================================================================
bot:
  reply_cooldown_seconds: 12
  smart_filter_enabled: true
  admin_ids: ${BOT_ADMIN_IDS}

# ============================================================================
# State Backup Configuration (Issue #2)
# ============================================================================
state_backup:
  state_dir: ${HOME:~}/.lifeos/trading
  backup_dir: ${HOME:~}/.lifeos/trading/backups
  archive_dir: ${HOME:~}/.lifeos/trading/archive

  # Backup timing
  backup_interval_hours: 1
  backup_retention_hours: 24

  # Files to backup
  backup_files:
    - positions.json
    - exit_intents.json
    - audit_log.json
    - daily_volume.json

```

### config/settings.json
Path: `config\settings.json`
```json
{
  "voice": {
    "speech_voice": "Daniel",
    "speak_responses": true,
    "wake_word": "jarvis",
    "wake_word_sensitivity": 0.5,
    "wake_word_timeout": 3,
    "speech_rate": 180,
    "speech_pitch": 0.8,
    "volume": 1.0
  },
  "assistant": {
    "name": "Jarvis",
    "personality": "helpful, intelligent, and slightly witty",
    "max_response_length": 1000,
    "enable_learning": true
  },
  "audio": {
    "energy_threshold": 300,
    "pause_threshold": 0.8,
    "dynamic_energy_threshold": true,
    "ambient_noise_duration": 1.0,
    "timeout": 5,
    "phrase_time_limit": 10
  },
  "features": {
    "voice_commands": true,
    "wake_word": true,
    "speech_recognition": true,
    "text_to_speech": true,
    "conversation_history": true,
    "context_awareness": true
  },
  "advanced": {
    "debug_mode": false,
    "log_level": "INFO",
    "auto_update": true,
    "backup_settings": true,
    "privacy_mode": false
  }
}

```

### config/performance_baselines.json
Path: `config\performance_baselines.json`
```json
{
  "signal_detection": {
    "target_ms": 50,
    "description": "Complete signal detection including all sub-phases"
  },
  "signal_detection.liquidation": {
    "target_ms": 20,
    "description": "Liquidation analysis from CoinGlass data"
  },
  "signal_detection.ma_analysis": {
    "target_ms": 15,
    "description": "Dual moving average calculation"
  },
  "signal_detection.sentiment": {
    "target_ms": 25,
    "description": "Sentiment scoring and analysis"
  },
  "signal_detection.decision_matrix": {
    "target_ms": 5,
    "description": "Multi-signal decision matrix computation"
  },
  "position_sizing": {
    "target_ms": 10,
    "description": "Calculate position size based on risk parameters"
  },
  "risk_checks": {
    "target_ms": 5,
    "description": "Validate trade against risk limits"
  },
  "jupiter_quote": {
    "target_ms": 200,
    "description": "Get quote from Jupiter DEX (external API)",
    "external": true
  },
  "execution": {
    "target_ms": 100,
    "description": "Execute trade on Solana (external transaction)",
    "external": true
  },
  "full_trade": {
    "target_ms": 400,
    "description": "Complete trade lifecycle including external calls"
  },
  "api.jupiter.quote": {
    "target_ms": 200,
    "description": "Jupiter quote API latency"
  },
  "api.jupiter.swap": {
    "target_ms": 300,
    "description": "Jupiter swap API latency"
  },
  "api.birdeye.price": {
    "target_ms": 150,
    "description": "Birdeye price API latency"
  },
  "api.coinglass.liquidations": {
    "target_ms": 200,
    "description": "CoinGlass liquidation API latency"
  },
  "query.positions": {
    "target_ms": 20,
    "description": "Query open positions"
  },
  "query.trades": {
    "target_ms": 30,
    "description": "Query trade history"
  },
  "query.logs": {
    "target_ms": 50,
    "description": "Query log entries"
  }
}

```

### config/rpc_providers.json
Path: `config\rpc_providers.json`
```json
{
    "version": "1.0",
    "description": "RPC provider configurations for Life OS Trading Bot",
    "solana": {
        "primary": {
            "name": "publicnode_solana",
            "url": "https://solana.publicnode.com",
            "rate_limit": 20,
            "timeout_ms": 20000
        },
        "fallback": [
            {
                "name": "helius",
                "url": "https://mainnet.helius-rpc.com/?api-key=${HELIUS_API_KEY}",
                "websocket": "wss://mainnet.helius-rpc.com/?api-key=${HELIUS_API_KEY}",
                "features": [
                    "enhanced_transactions",
                    "token_metadata",
                    "priority_fees"
                ],
                "rate_limit": 100,
                "timeout_ms": 30000
            },
            {
                "name": "ankr_solana",
                "url": "https://rpc.ankr.com/solana",
                "rate_limit": 30,
                "timeout_ms": 20000
            },
            {
                "name": "alchemy_solana",
                "url": "https://solana-mainnet.g.alchemy.com/v2/${ALCHEMY_API_KEY}",
                "rate_limit": 50
            },
            {
                "name": "public_solana",
                "url": "https://api.mainnet-beta.solana.com",
                "rate_limit": 10,
                "note": "Rate limited, use only as last resort"
            }
        ]
    },
    "ethereum": {
        "primary": {
            "name": "alchemy_eth",
            "url": "https://eth-mainnet.g.alchemy.com/v2/${ALCHEMY_API_KEY}",
            "websocket": "wss://eth-mainnet.g.alchemy.com/v2/${ALCHEMY_API_KEY}",
            "chain_id": 1,
            "rate_limit": 100,
            "timeout_ms": 30000
        },
        "fallback": [
            {
                "name": "ankr_eth",
                "url": "https://rpc.ankr.com/eth/${ANKR_API_KEY}",
                "chain_id": 1
            },
            {
                "name": "public_eth",
                "url": "https://ethereum.publicnode.com",
                "chain_id": 1,
                "rate_limit": 5
            }
        ]
    },
    "polygon": {
        "primary": {
            "name": "alchemy_polygon",
            "url": "https://polygon-mainnet.g.alchemy.com/v2/${ALCHEMY_API_KEY}",
            "chain_id": 137,
            "rate_limit": 100
        },
        "fallback": [
            {
                "name": "public_polygon",
                "url": "https://polygon-rpc.com",
                "chain_id": 137,
                "rate_limit": 10
            }
        ]
    },
    "arbitrum": {
        "primary": {
            "name": "alchemy_arbitrum",
            "url": "https://arb-mainnet.g.alchemy.com/v2/${ALCHEMY_API_KEY}",
            "chain_id": 42161,
            "rate_limit": 100
        },
        "fallback": [
            {
                "name": "public_arbitrum",
                "url": "https://arb1.arbitrum.io/rpc",
                "chain_id": 42161,
                "rate_limit": 10
            }
        ]
    },
    "base": {
        "primary": {
            "name": "alchemy_base",
            "url": "https://base-mainnet.g.alchemy.com/v2/${ALCHEMY_API_KEY}",
            "chain_id": 8453,
            "rate_limit": 100
        }
    },
    "dex_aggregators": {
        "solana": {
            "jupiter": {
                "quote_api": "https://quote-api.jup.ag/v6",
                "swap_api": "https://quote-api.jup.ag/v6/swap",
                "price_api": "https://price.jup.ag/v6/price"
            }
        },
        "ethereum": {
            "1inch": {
                "api": "https://api.1inch.dev/swap/v6.0/1",
                "requires_key": true
            },
            "0x": {
                "api": "https://api.0x.org",
                "requires_key": true
            }
        }
    },
    "pricing": {
        "helius": {
            "free_tier": "Limited requests",
            "developer": "$49/month (500K credits)",
            "business": "$499/month (5M credits)"
        },
        "alchemy": {
            "free_tier": "30M compute units/month",
            "growth": "$49/month (400M CU)",
            "overage": "$0.40 per 1M CU"
        }
    }
}

```

### config/windsurf_settings.json
Path: `config\windsurf_settings.json`
```json
{
  "//": "MiniMax M2.1 Configuration for Windsurf IDE",
  "//": "Copy the relevant sections into your Windsurf settings.json",
  
  "ai.customModels": [
    {
      "id": "minimax-m2.1",
      "name": "MiniMax M2.1 (via OpenRouter)",
      "provider": "openai-compatible",
      "baseUrl": "https://openrouter.ai/api/v1",
      "model": "minimax/minimax-m2.1",
      "apiKeyEnvVar": "OPENROUTER_API_KEY",
      "contextWindow": 200000,
      "maxOutputTokens": 8192,
      "supportsStreaming": true
    },
    {
      "id": "minimax-text-01",
      "name": "MiniMax-Text-01 (via OpenRouter)",
      "provider": "openai-compatible",
      "baseUrl": "https://openrouter.ai/api/v1",
      "model": "minimax/minimax-text-01",
      "apiKeyEnvVar": "OPENROUTER_API_KEY",
      "contextWindow": 1000000,
      "maxOutputTokens": 16384,
      "supportsStreaming": true
    }
  ],
  
  "ai.defaultModel": "minimax-m2.1",
  
  "//": "=== ALTERNATIVE: Direct MiniMax API (if preferred over OpenRouter) ===",
  "ai.customModels.direct": [
    {
      "id": "minimax-m2.1-direct",
      "name": "MiniMax M2.1 (Direct API)",
      "provider": "openai-compatible",
      "baseUrl": "https://api.minimax.chat/v1",
      "model": "MiniMax-M2",
      "apiKeyEnvVar": "MINIMAX_API_KEY",
      "contextWindow": 200000,
      "maxOutputTokens": 8192,
      "supportsStreaming": true
    }
  ],
  
  "//": "=== ENVIRONMENT VARIABLES REQUIRED ===",
  "//": "export OPENROUTER_API_KEY='your-openrouter-api-key'",
  "//": "OR for direct API:",
  "//": "export MINIMAX_API_KEY='your-minimax-api-key'"
}

```

### config/environments/development.env
Path: `config\environments\development.env`
```bash
# JARVIS Development Environment Configuration

# Environment
ENVIRONMENT=<REDACTED>
DEBUG=<REDACTED>
LOG_LEVEL=<REDACTED>

# API Configuration
API_HOST=<REDACTED>
API_PORT=<REDACTED>
API_WORKERS=<REDACTED>
API_TIMEOUT=<REDACTED>

# Database (local)
DATABASE_URL=<REDACTED>
DB_POOL_SIZE=<REDACTED>
DB_MAX_OVERFLOW=<REDACTED>
DB_POOL_RECYCLE=<REDACTED>

# Redis (local)
REDIS_URL=<REDACTED>
REDIS_ENABLED=<REDACTED>

# LLM Configuration
LLM_PROVIDER=<REDACTED>
LLM_DEFAULT_MODEL=<REDACTED>
LLM_FALLBACK_PROVIDERS=
LLM_DAILY_BUDGET=<REDACTED>
LLM_MONTHLY_BUDGET=<REDACTED>
LLM_TIMEOUT=<REDACTED>

# Treasury (Paper trading only)
TREASURY_MODE=<REDACTED>
MAX_SINGLE_TRADE_USD=<REDACTED>
MAX_DAILY_VOLUME_USD=<REDACTED>
MAX_POSITION_SIZE_PERCENT=<REDACTED>

# Security (relaxed for dev)
SESSION_TIMEOUT=<REDACTED>
IDLE_TIMEOUT=<REDACTED>
RATE_LIMIT_ENABLED=<REDACTED>
RATE_LIMIT_REQUESTS=<REDACTED>
RATE_LIMIT_WINDOW=<REDACTED>

# Monitoring
METRICS_ENABLED=<REDACTED>
METRICS_PORT=<REDACTED>
TRACING_ENABLED=<REDACTED>
TRACING_SAMPLE_RATE=<REDACTED>

# Telegram Bot
TG_RATE_LIMIT_MESSAGES=<REDACTED>
TG_RATE_LIMIT_WINDOW=<REDACTED>

# Feature Flags
FEATURE_TWITTER_BOT=<REDACTED>
FEATURE_TRADING=<REDACTED>
FEATURE_ANALYTICS=<REDACTED>

```

### config/environments/staging.env
Path: `config\environments\staging.env`
```bash
# JARVIS Staging Environment Configuration

# Environment
ENVIRONMENT=<REDACTED>
DEBUG=<REDACTED>
LOG_LEVEL=<REDACTED>

# API Configuration
API_HOST=<REDACTED>
API_PORT=<REDACTED>
API_WORKERS=<REDACTED>
API_TIMEOUT=<REDACTED>

# Database
DATABASE_URL=<REDACTED>
DB_POOL_SIZE=<REDACTED>
DB_MAX_OVERFLOW=<REDACTED>
DB_POOL_RECYCLE=<REDACTED>

# Redis
REDIS_URL=<REDACTED>
REDIS_ENABLED=<REDACTED>

# LLM Configuration
LLM_PROVIDER=<REDACTED>
LLM_DEFAULT_MODEL=<REDACTED>
LLM_FALLBACK_PROVIDERS=<REDACTED>
LLM_DAILY_BUDGET=<REDACTED>
LLM_MONTHLY_BUDGET=<REDACTED>
LLM_TIMEOUT=<REDACTED>

# Treasury (Paper trading mode)
TREASURY_MODE=<REDACTED>
MAX_SINGLE_TRADE_USD=<REDACTED>
MAX_DAILY_VOLUME_USD=<REDACTED>
MAX_POSITION_SIZE_PERCENT=<REDACTED>

# Security
SESSION_TIMEOUT=<REDACTED>
IDLE_TIMEOUT=<REDACTED>
RATE_LIMIT_ENABLED=<REDACTED>
RATE_LIMIT_REQUESTS=<REDACTED>
RATE_LIMIT_WINDOW=<REDACTED>

# Monitoring
METRICS_ENABLED=<REDACTED>
METRICS_PORT=<REDACTED>
TRACING_ENABLED=<REDACTED>
TRACING_SAMPLE_RATE=<REDACTED>

# Telegram Bot
TG_RATE_LIMIT_MESSAGES=<REDACTED>
TG_RATE_LIMIT_WINDOW=<REDACTED>

# Feature Flags
FEATURE_TWITTER_BOT=<REDACTED>
FEATURE_TRADING=<REDACTED>
FEATURE_ANALYTICS=<REDACTED>

```

### config/environments/production.env
Path: `config\environments\production.env`
```bash
# JARVIS Production Environment Configuration
# DO NOT commit actual secrets to version control

# Environment
ENVIRONMENT=<REDACTED>
DEBUG=<REDACTED>
LOG_LEVEL=<REDACTED>

# API Configuration
API_HOST=<REDACTED>
API_PORT=<REDACTED>
API_WORKERS=<REDACTED>
API_TIMEOUT=<REDACTED>

# Database
# Use secrets manager for actual values
DATABASE_URL=<REDACTED>
DB_POOL_SIZE=<REDACTED>
DB_MAX_OVERFLOW=<REDACTED>
DB_POOL_RECYCLE=<REDACTED>

# Redis
REDIS_URL=<REDACTED>
REDIS_ENABLED=<REDACTED>

# LLM Configuration
LLM_PROVIDER=<REDACTED>
LLM_DEFAULT_MODEL=<REDACTED>
LLM_FALLBACK_PROVIDERS=<REDACTED>
LLM_DAILY_BUDGET=<REDACTED>
LLM_MONTHLY_BUDGET=<REDACTED>
LLM_TIMEOUT=<REDACTED>

# Treasury (CRITICAL - Use secrets manager)
TREASURY_MODE=<REDACTED>
MAX_SINGLE_TRADE_USD=<REDACTED>
MAX_DAILY_VOLUME_USD=<REDACTED>
MAX_POSITION_SIZE_PERCENT=<REDACTED>

# Security
SESSION_TIMEOUT=<REDACTED>
IDLE_TIMEOUT=<REDACTED>
RATE_LIMIT_ENABLED=<REDACTED>
RATE_LIMIT_REQUESTS=<REDACTED>
RATE_LIMIT_WINDOW=<REDACTED>

# Monitoring
METRICS_ENABLED=<REDACTED>
METRICS_PORT=<REDACTED>
TRACING_ENABLED=<REDACTED>
TRACING_SAMPLE_RATE=<REDACTED>

# Telegram Bot
# Token from secrets manager
TG_RATE_LIMIT_MESSAGES=<REDACTED>
TG_RATE_LIMIT_WINDOW=<REDACTED>

# Feature Flags
FEATURE_TWITTER_BOT=<REDACTED>
FEATURE_TRADING=<REDACTED>
FEATURE_ANALYTICS=<REDACTED>

```

## Log files listing (root + logs/)

### Log listing
```text

FullName                                                                                                    Length LastWriteTime        
--------                                                                                                    ------ -------------        
C:\Users\lucid\OneDrive\Desktop\Projects\Jarvis\deployment_retry.log                                          5371 1/17/2026 6:49:36 PM 
C:\Users\lucid\OneDrive\Desktop\Projects\Jarvis\logs\.9c270576d9ed2b97c08bad0646f8c0a7b0c8ca41-audit.json     1526 1/22/2026 12:01:49 AM
C:\Users\lucid\OneDrive\Desktop\Projects\Jarvis\logs\.c72d74d05bc6620c039e934e581ceade7092be56-audit.json     3062 1/22/2026 9:24:07 AM 
C:\Users\lucid\OneDrive\Desktop\Projects\Jarvis\logs\audit.jsonl                                            362993 1/21/2026 2:15:13 AM 
C:\Users\lucid\OneDrive\Desktop\Projects\Jarvis\logs\bots.log                                               255510 1/14/2026 12:38:27 PM
C:\Users\lucid\OneDrive\Desktop\Projects\Jarvis\logs\dashboard.log                                             920 1/18/2026 2:08:08 PM 
C:\Users\lucid\OneDrive\Desktop\Projects\Jarvis\logs\jarvis_20260113.log                                         0 1/13/2026 3:26:23 PM 
C:\Users\lucid\OneDrive\Desktop\Projects\Jarvis\logs\jarvis_errors.log                                        4775 1/22/2026 10:28:20 AM
C:\Users\lucid\OneDrive\Desktop\Projects\Jarvis\logs\key_rotation.log                                         2316 1/19/2026 6:32:26 PM 
C:\Users\lucid\OneDrive\Desktop\Projects\Jarvis\logs\mcp-puppeteer-2026-01-12.log.gz                          1078 1/13/2026 8:21:26 PM 
C:\Users\lucid\OneDrive\Desktop\Projects\Jarvis\logs\mcp-puppeteer-2026-01-13.log.gz                           267 1/14/2026 12:11:55 AM
C:\Users\lucid\OneDrive\Desktop\Projects\Jarvis\logs\mcp-puppeteer-2026-01-14.log                            16856 1/14/2026 11:47:14 PM
C:\Users\lucid\OneDrive\Desktop\Projects\Jarvis\logs\mcp-puppeteer-2026-01-15.log.gz                           837 1/16/2026 3:16:01 AM 
C:\Users\lucid\OneDrive\Desktop\Projects\Jarvis\logs\mcp-puppeteer-2026-01-16.log.gz                           231 1/17/2026 1:26:00 AM 
C:\Users\lucid\OneDrive\Desktop\Projects\Jarvis\logs\mcp-puppeteer-2026-01-17.log.gz                           291 1/18/2026 1:14:41 AM 
C:\Users\lucid\OneDrive\Desktop\Projects\Jarvis\logs\mcp-puppeteer-2026-01-18.log                              849 1/18/2026 10:26:36 PM
C:\Users\lucid\OneDrive\Desktop\Projects\Jarvis\logs\mcp-puppeteer-2026-01-19.log.gz                           330 1/20/2026 5:19:03 AM 
C:\Users\lucid\OneDrive\Desktop\Projects\Jarvis\logs\mcp-puppeteer-2026-01-20.log                            15486 1/20/2026 11:34:26 PM
C:\Users\lucid\OneDrive\Desktop\Projects\Jarvis\logs\mcp-puppeteer-2026-01-21.log                           194931 1/21/2026 11:59:48 PM
C:\Users\lucid\OneDrive\Desktop\Projects\Jarvis\logs\mcp-puppeteer-2026-01-22.log                            41592 1/22/2026 10:10:51 AM
C:\Users\lucid\OneDrive\Desktop\Projects\Jarvis\logs\sentiment_tuning.log                                     2085 1/17/2026 2:35:47 AM 
C:\Users\lucid\OneDrive\Desktop\Projects\Jarvis\logs\solana_dex_one_day_hunt_full.pid                            7 1/8/2026 2:29:15 PM  
C:\Users\lucid\OneDrive\Desktop\Projects\Jarvis\logs\startup.log                                              1068 1/17/2026 2:50:01 AM 
C:\Users\lucid\OneDrive\Desktop\Projects\Jarvis\logs\supervisor.log                                       12064800 1/22/2026 10:28:33 AM
C:\Users\lucid\OneDrive\Desktop\Projects\Jarvis\logs\supervisor_startup.log                                2530362 1/18/2026 10:26:57 PM
C:\Users\lucid\OneDrive\Desktop\Projects\Jarvis\logs\supervisor_test.log                                     22249 1/16/2026 6:10:03 PM 
C:\Users\lucid\OneDrive\Desktop\Projects\Jarvis\logs\telegram_bot.log                                        62915 1/22/2026 10:28:20 AM
C:\Users\lucid\OneDrive\Desktop\Projects\Jarvis\logs\telegram_bot_errors.log                                 35223 1/22/2026 10:28:20 AM
C:\Users\lucid\OneDrive\Desktop\Projects\Jarvis\logs\validation.log                                        5514069 1/18/2026 1:20:53 AM 
C:\Users\lucid\OneDrive\Desktop\Projects\Jarvis\supervisor.log                                             1215747 1/17/2026 1:04:57 PM 
C:\Users\lucid\OneDrive\Desktop\Projects\Jarvis\tg_bot.log                                                  977923 1/17/2026 1:26:26 PM 
C:\Users\lucid\OneDrive\Desktop\Projects\Jarvis\tg_bot_new.log                                             1032813 1/17/2026 1:26:30 PM 
C:\Users\lucid\OneDrive\Desktop\Projects\Jarvis\tg_bot_output.log                                               19 1/14/2026 10:39:52 AM
C:\Users\lucid\OneDrive\Desktop\Projects\Jarvis\vps-deploy.log                                                  71 1/17/2026 5:28:20 AM 



```

## Key log excerpts

### logs/jarvis_errors.log (tail 200 lines)
Path: `logs\jarvis_errors.log`
```text
2026-01-22 10:18:47,056 | ERROR | [c5d0b0347554] TelegramBot | Conflict: Conflict: terminated by other getUpdates request; make sure that only one bot instance is running | Count: 1
2026-01-22 10:18:52,764 | ERROR | [c5d0b0347554] TelegramBot | Conflict: Conflict: terminated by other getUpdates request; make sure that only one bot instance is running | Count: 2
2026-01-22 10:18:59,781 | ERROR | [c5d0b0347554] TelegramBot | Conflict: Conflict: terminated by other getUpdates request; make sure that only one bot instance is running | Count: 3
2026-01-22 10:19:05,636 | ERROR | [c5d0b0347554] TelegramBot | Conflict: Conflict: terminated by other getUpdates request; make sure that only one bot instance is running | Count: 4
2026-01-22 10:24:08,513 | ERROR | [c5d0b0347554] TelegramBot | Conflict: Conflict: terminated by other getUpdates request; make sure that only one bot instance is running | Count: 5
2026-01-22 10:24:14,274 | ERROR | [c5d0b0347554] TelegramBot | Conflict: Conflict: terminated by other getUpdates request; make sure that only one bot instance is running | Count: 6
2026-01-22 10:24:21,282 | ERROR | [c5d0b0347554] TelegramBot | Conflict: Conflict: terminated by other getUpdates request; make sure that only one bot instance is running | Count: 7
2026-01-22 10:24:45,330 | ERROR | [c5d0b0347554] TelegramBot | Conflict: Conflict: terminated by other getUpdates request; make sure that only one bot instance is running | Count: 8
2026-01-22 10:24:51,071 | ERROR | [c5d0b0347554] TelegramBot | Conflict: Conflict: terminated by other getUpdates request; make sure that only one bot instance is running | Count: 9
2026-01-22 10:24:58,099 | ERROR | [c5d0b0347554] TelegramBot | Conflict: Conflict: terminated by other getUpdates request; make sure that only one bot instance is running | Count: 10
2026-01-22 10:25:03,988 | ERROR | [c5d0b0347554] TelegramBot | Conflict: Conflict: terminated by other getUpdates request; make sure that only one bot instance is running | Count: 11
2026-01-22 10:25:41,533 | ERROR | [c5d0b0347554] TelegramBot | Conflict: Conflict: terminated by other getUpdates request; make sure that only one bot instance is running | Count: 12
2026-01-22 10:25:46,836 | ERROR | [c5d0b0347554] TelegramBot | Conflict: Conflict: terminated by other getUpdates request; make sure that only one bot instance is running | Count: 13
2026-01-22 10:25:53,118 | ERROR | [c5d0b0347554] TelegramBot | Conflict: Conflict: terminated by other getUpdates request; make sure that only one bot instance is running | Count: 14
2026-01-22 10:26:00,936 | ERROR | [c5d0b0347554] TelegramBot | Conflict: Conflict: terminated by other getUpdates request; make sure that only one bot instance is running | Count: 15
2026-01-22 10:26:08,561 | ERROR | [c5d0b0347554] TelegramBot | Conflict: Conflict: terminated by other getUpdates request; make sure that only one bot instance is running | Count: 16
2026-01-22 10:26:18,903 | ERROR | [c5d0b0347554] TelegramBot | Conflict: Conflict: terminated by other getUpdates request; make sure that only one bot instance is running | Count: 17
2026-01-22 10:26:53,616 | ERROR | [c5d0b0347554] TelegramBot | Conflict: Conflict: terminated by other getUpdates request; make sure that only one bot instance is running | Count: 18
2026-01-22 10:26:58,876 | ERROR | [c5d0b0347554] TelegramBot | Conflict: Conflict: terminated by other getUpdates request; make sure that only one bot instance is running | Count: 19
2026-01-22 10:27:05,111 | ERROR | [c5d0b0347554] TelegramBot | Conflict: Conflict: terminated by other getUpdates request; make sure that only one bot instance is running | Count: 20
2026-01-22 10:27:12,866 | ERROR | [c5d0b0347554] TelegramBot | Conflict: Conflict: terminated by other getUpdates request; make sure that only one bot instance is running | Count: 21
2026-01-22 10:27:19,866 | ERROR | [c5d0b0347554] TelegramBot | Conflict: Conflict: terminated by other getUpdates request; make sure that only one bot instance is running | Count: 22
2026-01-22 10:27:29,602 | ERROR | [c5d0b0347554] TelegramBot | Conflict: Conflict: terminated by other getUpdates request; make sure that only one bot instance is running | Count: 23
2026-01-22 10:27:42,386 | ERROR | [c5d0b0347554] TelegramBot | Conflict: Conflict: terminated by other getUpdates request; make sure that only one bot instance is running | Count: 24
2026-01-22 10:27:58,473 | ERROR | [c5d0b0347554] TelegramBot | Conflict: Conflict: terminated by other getUpdates request; make sure that only one bot instance is running | Count: 25
2026-01-22 10:28:20,223 | ERROR | [c5d0b0347554] TelegramBot | Conflict: Conflict: terminated by other getUpdates request; make sure that only one bot instance is running | Count: 26
2026-01-22 10:29:10,312 | ERROR | [c5d0b0347554] TelegramBot | Conflict: Conflict: terminated by other getUpdates request; make sure that only one bot instance is running | Count: 27
2026-01-22 10:29:16,073 | ERROR | [c5d0b0347554] TelegramBot | Conflict: Conflict: terminated by other getUpdates request; make sure that only one bot instance is running | Count: 28
2026-01-22 10:29:23,086 | ERROR | [c5d0b0347554] TelegramBot | Conflict: Conflict: terminated by other getUpdates request; make sure that only one bot instance is running | Count: 29
2026-01-22 10:29:27,735 | ERROR | [c5d0b0347554] TelegramBot | Conflict: Conflict: terminated by other getUpdates request; make sure that only one bot instance is running | Count: 30
2026-01-22 10:29:37,945 | ERROR | [c5d0b0347554] TelegramBot | Conflict: Conflict: terminated by other getUpdates request; make sure that only one bot instance is running | Count: 31
2026-01-22 10:30:19,450 | ERROR | [c5d0b0347554] TelegramBot | Conflict: Conflict: terminated by other getUpdates request; make sure that only one bot instance is running | Count: 32
2026-01-22 10:30:24,815 | ERROR | [c5d0b0347554] TelegramBot | Conflict: Conflict: terminated by other getUpdates request; make sure that only one bot instance is running | Count: 33
2026-01-22 10:30:31,077 | ERROR | [c5d0b0347554] TelegramBot | Conflict: Conflict: terminated by other getUpdates request; make sure that only one bot instance is running | Count: 34
2026-01-22 10:30:38,853 | ERROR | [c5d0b0347554] TelegramBot | Conflict: Conflict: terminated by other getUpdates request; make sure that only one bot instance is running | Count: 35
2026-01-22 10:30:45,894 | ERROR | [c5d0b0347554] TelegramBot | Conflict: Conflict: terminated by other getUpdates request; make sure that only one bot instance is running | Count: 36
2026-01-22 10:30:57,071 | ERROR | [c5d0b0347554] TelegramBot | Conflict: Conflict: terminated by other getUpdates request; make sure that only one bot instance is running | Count: 37
2026-01-22 10:31:13,019 | ERROR | [c5d0b0347554] TelegramBot | Conflict: Conflict: terminated by other getUpdates request; make sure that only one bot instance is running | Count: 38
2026-01-22 10:31:29,010 | ERROR | [c5d0b0347554] TelegramBot | Conflict: Conflict: terminated by other getUpdates request; make sure that only one bot instance is running | Count: 39
2026-01-22 10:31:51,507 | ERROR | [c5d0b0347554] TelegramBot | Conflict: Conflict: terminated by other getUpdates request; make sure that only one bot instance is running | Count: 40
2026-01-22 10:32:21,804 | ERROR | [c5d0b0347554] TelegramBot | Conflict: Conflict: terminated by other getUpdates request; make sure that only one bot instance is running | Count: 41
2026-01-22 10:32:56,406 | ERROR | [c5d0b0347554] TelegramBot | Conflict: Conflict: terminated by other getUpdates request; make sure that only one bot instance is running | Count: 42
2026-01-22 10:33:31,015 | ERROR | [c5d0b0347554] TelegramBot | Conflict: Conflict: terminated by other getUpdates request; make sure that only one bot instance is running | Count: 43
2026-01-22 10:34:05,605 | ERROR | [c5d0b0347554] TelegramBot | Conflict: Conflict: terminated by other getUpdates request; make sure that only one bot instance is running | Count: 44
2026-01-22 10:34:40,181 | ERROR | [c5d0b0347554] TelegramBot | Conflict: Conflict: terminated by other getUpdates request; make sure that only one bot instance is running | Count: 45
2026-01-22 10:35:14,720 | ERROR | [c5d0b0347554] TelegramBot | Conflict: Conflict: terminated by other getUpdates request; make sure that only one bot instance is running | Count: 46
2026-01-22 10:35:49,292 | ERROR | [c5d0b0347554] TelegramBot | Conflict: Conflict: terminated by other getUpdates request; make sure that only one bot instance is running | Count: 47
```

### logs/supervisor.log (tail 200 lines)
Path: `logs\supervisor.log`
```text
2026-01-22 10:29:00,259 - bots.buy_tracker.monitor - INFO -   - continuous/kr8tiv: s3KFNeaTFmkF...
2026-01-22 10:29:00,259 - bots.buy_tracker.monitor - INFO -   - ATH/kr8tiv: FsezrNYYXdTH...
2026-01-22 10:29:00,359 - core.autonomy.news_detector - INFO - News scan found 0 events
2026-01-22 10:29:00,513 - bots.buy_tracker.bot - INFO - Buy bot running - tracking KR8TIV
2026-01-22 10:29:01,293 - bots.twitter.x_claude_cli_handler - WARNING - Unauthorized X CLI attempt by @riveras_
2026-01-22 10:29:01,293 - bots.twitter.x_claude_cli_handler - WARNING - Unauthorized X CLI attempt by @riveras_
2026-01-22 10:29:01,768 - jarvis.grok - INFO - [EVENT] GROK_API_CALL
2026-01-22 10:29:01,769 - jarvis.twitter.sentiment_poster - INFO - Grok fallback generated: yo, just dropped a microcap sentiment scan! 3 bullish, 5 bearish tokens in the m...
2026-01-22 10:29:01,781 - bots.twitter.autonomous_engine - WARNING - Tweet too similar (63.2%) to: yo, just dropped a microcap sentiment scan! 3 bull...
2026-01-22 10:29:01,781 - jarvis.twitter.sentiment_poster - WARNING - SKIPPED DUPLICATE (sentiment): Too similar to recent tweet
2026-01-22 10:29:01,781 - jarvis.twitter.sentiment_poster - INFO - New: yo, just dropped a microcap sentiment scan! 3 bullish, 5 bea...
2026-01-22 10:29:01,781 - jarvis.twitter.sentiment_poster - INFO - Old: yo, just dropped a microcap sentiment scan! 3 bullish, 5 bea...
2026-01-22 10:29:02,669 - jarvis.grok - INFO - [EVENT] GROK_API_CALL
2026-01-22 10:29:02,669 - core.autonomy.alpha_detector - INFO - Alpha scan found 3 signals
2026-01-22 10:29:03,129 - jarvis.grok - INFO - [EVENT] GROK_API_CALL
2026-01-22 10:29:03,129 - core.autonomy.trending_detector - INFO - Detected 0 trending topics
2026-01-22 10:29:03,284 - bots.twitter.x_claude_cli_handler - WARNING - Unauthorized X CLI attempt by @bondingalerts
2026-01-22 10:29:03,284 - bots.twitter.x_claude_cli_handler - WARNING - Unauthorized X CLI attempt by @bondingalerts
2026-01-22 10:29:03,655 - jarvis.grok - INFO - [EVENT] GROK_API_CALL
2026-01-22 10:29:03,655 - core.autonomy.alpha_detector - INFO - Alpha scan found 3 signals
2026-01-22 10:29:04,372 - bots.buy_tracker.monitor - INFO - Initialized with 286 existing transactions across 11 pairs (skipped)
2026-01-22 10:29:05,303 - bots.twitter.x_claude_cli_handler - WARNING - Unauthorized X CLI attempt by @ctotokens
2026-01-22 10:29:05,303 - bots.twitter.x_claude_cli_handler - WARNING - Unauthorized X CLI attempt by @ctotokens
2026-01-22 10:29:07,193 - core.data.lunarcrush_api - WARNING - LunarCrush API disabled after repeated 404s
2026-01-22 10:29:07,193 - core.sentiment_trading - INFO - Pipeline scan found 3 signals
2026-01-22 10:29:07,193 - core.autonomy.orchestrator - INFO - Sentiment pipeline found 3 signals
2026-01-22 10:29:07,318 - bots.twitter.x_claude_cli_handler - WARNING - Unauthorized X CLI attempt by @moonmastor8
2026-01-22 10:29:07,318 - bots.twitter.x_claude_cli_handler - WARNING - Unauthorized X CLI attempt by @moonmastor8
2026-01-22 10:29:09,340 - bots.twitter.x_claude_cli_handler - WARNING - Unauthorized X CLI attempt by @blackhatfomo
2026-01-22 10:29:09,340 - bots.twitter.x_claude_cli_handler - WARNING - Unauthorized X CLI attempt by @blackhatfomo
2026-01-22 10:29:11,338 - bots.twitter.x_claude_cli_handler - WARNING - Unauthorized X CLI attempt by @pumpfunok
2026-01-22 10:29:11,338 - bots.twitter.x_claude_cli_handler - WARNING - Unauthorized X CLI attempt by @pumpfunok
2026-01-22 10:29:13,340 - bots.twitter.x_claude_cli_handler - WARNING - Unauthorized X CLI attempt by @cliftonlen83916
2026-01-22 10:29:13,340 - bots.twitter.x_claude_cli_handler - WARNING - Unauthorized X CLI attempt by @cliftonlen83916
2026-01-22 10:29:15,370 - bots.twitter.x_claude_cli_handler - WARNING - Unauthorized X CLI attempt by @kr8tivai
2026-01-22 10:29:15,370 - bots.twitter.x_claude_cli_handler - WARNING - Unauthorized X CLI attempt by @kr8tivai
2026-01-22 10:29:17,373 - bots.twitter.x_claude_cli_handler - WARNING - Unauthorized X CLI attempt by @kr8tivai
2026-01-22 10:29:17,373 - bots.twitter.x_claude_cli_handler - WARNING - Unauthorized X CLI attempt by @kr8tivai
2026-01-22 10:29:19,547 - jarvis.monitoring.health_bus - INFO - Health check: healthy - 7 healthy, 0 degraded, 0 critical
2026-01-22 10:29:33,988 - bots.buy_tracker.monitor - INFO - Found 1 new transaction(s) to process
2026-01-22 10:29:46,262 - bots.buy_tracker.monitor - INFO - Found 1 new transaction(s) to process
2026-01-22 10:29:49,567 - jarvis.monitoring.health_bus - INFO - Health check: healthy - 7 healthy, 0 degraded, 0 critical
2026-01-22 10:29:53,133 - bots.buy_tracker.monitor - INFO - Found 1 new transaction(s) to process
2026-01-22 10:29:57,455 - jarvis.supervisor - INFO - === COMPONENT HEALTH ===
  buy_bot: running (uptime: 0:01:07.919429) (restarts: 0)
  sentiment_reporter: running (uptime: 0:01:04.652456) (restarts: 0)
  twitter_poster: running (uptime: 0:01:04.630292) (restarts: 0)
  telegram_bot: running (uptime: 0:01:03.386296) (restarts: 0)
  autonomous_x: running (uptime: 0:01:02.627324) (restarts: 0)
  public_trading_bot: stopped (restarts: 0)
  autonomous_manager: running (uptime: 0:01:00.045455) (restarts: 0)
  bags_intel: running (uptime: 0:01:00.016269) (restarts: 0)
2026-01-22 10:29:59,719 - tweepy.client - WARNING - Rate limit exceeded. Sleeping for 180 seconds.
2026-01-22 10:30:06,007 - bots.buy_tracker.monitor - INFO - Found 2 new transaction(s) to process
2026-01-22 10:30:07,610 - bots.twitter.twitter_client - INFO - Connected to X as @Jarvis_lifeos (OAuth 1.0a via tweepy)
2026-01-22 10:30:07,690 - bots.twitter.twitter_client - WARNING - Disabling X read endpoints for 900s: search unauthorized (401)
2026-01-22 10:30:07,694 - core.autonomy.self_learning - INFO - Pattern analysis complete. Best hours: [23, 0, 2]
2026-01-22 10:30:07,696 - core.autonomy.self_learning - INFO - Pattern analysis complete. Best hours: [23, 0, 2]
2026-01-22 10:30:07,697 - core.autonomy.news_detector - INFO - News scan found 0 events
2026-01-22 10:30:07,697 - core.autonomy.news_detector - INFO - News scan found 0 events
2026-01-22 10:30:13,632 - jarvis.grok - INFO - [EVENT] GROK_API_CALL
2026-01-22 10:30:13,633 - core.autonomy.alpha_detector - INFO - Alpha scan found 3 signals
2026-01-22 10:30:13,633 - core.sentiment_trading - INFO - Pipeline scan found 3 signals
2026-01-22 10:30:13,633 - core.autonomy.orchestrator - INFO - Sentiment pipeline found 3 signals
2026-01-22 10:30:14,052 - jarvis.grok - INFO - [EVENT] GROK_API_CALL
2026-01-22 10:30:14,052 - core.autonomy.alpha_detector - INFO - Alpha scan found 3 signals
2026-01-22 10:30:19,566 - jarvis.monitoring.health_bus - INFO - Health check: healthy - 7 healthy, 0 degraded, 0 critical
2026-01-22 10:30:30,722 - bots.buy_tracker.monitor - INFO - Poll #15: 291 txns tracked across 11 pairs, min=$1.0
2026-01-22 10:30:49,291 - bots.buy_tracker.monitor - INFO - Found 2 new transaction(s) to process
2026-01-22 10:30:49,586 - jarvis.monitoring.health_bus - INFO - Health check: healthy - 7 healthy, 0 degraded, 0 critical
2026-01-22 10:30:55,716 - bots.buy_tracker.monitor - INFO - Found 1 new transaction(s) to process
2026-01-22 10:30:57,468 - jarvis.supervisor - INFO - === COMPONENT HEALTH ===
  buy_bot: running (uptime: 0:02:07.932409) (restarts: 0)
  sentiment_reporter: running (uptime: 0:02:04.665436) (restarts: 0)
  twitter_poster: running (uptime: 0:02:04.643272) (restarts: 0)
  telegram_bot: running (uptime: 0:02:03.399276) (restarts: 0)
  autonomous_x: running (uptime: 0:02:02.640304) (restarts: 0)
  public_trading_bot: stopped (restarts: 0)
  autonomous_manager: running (uptime: 0:02:00.058435) (restarts: 0)
  bags_intel: running (uptime: 0:02:00.029249) (restarts: 0)
2026-01-22 10:31:05,043 - bots.buy_tracker.monitor - INFO - Found 10 new transaction(s) to process
2026-01-22 10:31:14,063 - core.autonomy.self_learning - INFO - Pattern analysis complete. Best hours: [23, 0, 2]
2026-01-22 10:31:14,067 - core.autonomy.self_learning - INFO - Pattern analysis complete. Best hours: [23, 0, 2]
2026-01-22 10:31:14,068 - core.autonomy.news_detector - INFO - News scan found 0 events
2026-01-22 10:31:14,068 - core.autonomy.news_detector - INFO - News scan found 0 events
2026-01-22 10:31:19,585 - jarvis.monitoring.health_bus - INFO - Health check: healthy - 7 healthy, 0 degraded, 0 critical
2026-01-22 10:31:20,772 - bots.buy_tracker.monitor - INFO - Found 11 new transaction(s) to process
2026-01-22 10:31:26,443 - jarvis.grok - INFO - [EVENT] GROK_API_CALL
2026-01-22 10:31:26,444 - core.autonomy.alpha_detector - INFO - Alpha scan found 3 signals
2026-01-22 10:31:26,966 - jarvis.grok - INFO - [EVENT] GROK_API_CALL
2026-01-22 10:31:26,966 - core.autonomy.alpha_detector - INFO - Alpha scan found 3 signals
2026-01-22 10:31:26,966 - core.sentiment_trading - INFO - Pipeline scan found 3 signals
2026-01-22 10:31:26,966 - core.autonomy.orchestrator - INFO - Sentiment pipeline found 3 signals
2026-01-22 10:31:27,034 - bots.buy_tracker.monitor - INFO - Found 1 new transaction(s) to process
2026-01-22 10:31:49,604 - jarvis.monitoring.health_bus - INFO - Health check: healthy - 7 healthy, 0 degraded, 0 critical
2026-01-22 10:31:57,488 - jarvis.supervisor - INFO - === COMPONENT HEALTH ===
  buy_bot: running (uptime: 0:03:07.952517) (restarts: 0)
  sentiment_reporter: running (uptime: 0:03:04.685544) (restarts: 0)
  twitter_poster: running (uptime: 0:03:04.663380) (restarts: 0)
  telegram_bot: running (uptime: 0:03:03.419384) (restarts: 0)
  autonomous_x: running (uptime: 0:03:02.660412) (restarts: 0)
  public_trading_bot: stopped (restarts: 0)
  autonomous_manager: running (uptime: 0:03:00.078543) (restarts: 0)
  bags_intel: running (uptime: 0:03:00.049357) (restarts: 0)
2026-01-22 10:32:00,528 - bots.buy_tracker.monitor - INFO - Found 2 new transaction(s) to process
2026-01-22 10:32:12,855 - bots.buy_tracker.monitor - INFO - Poll #30: 318 txns tracked across 11 pairs, min=$1.0
2026-01-22 10:32:19,615 - jarvis.monitoring.health_bus - INFO - Health check: healthy - 7 healthy, 0 degraded, 0 critical
2026-01-22 10:32:25,993 - bots.buy_tracker.monitor - INFO - Found 3 new transaction(s) to process
2026-01-22 10:32:26,994 - core.autonomy.self_learning - INFO - Pattern analysis complete. Best hours: [23, 0, 2]
2026-01-22 10:32:26,998 - core.autonomy.self_learning - INFO - Pattern analysis complete. Best hours: [23, 0, 2]
2026-01-22 10:32:26,998 - core.autonomy.news_detector - INFO - News scan found 0 events
2026-01-22 10:32:26,998 - core.autonomy.news_detector - INFO - News scan found 0 events
2026-01-22 10:32:31,560 - jarvis.grok - INFO - [EVENT] GROK_API_CALL
2026-01-22 10:32:31,561 - core.autonomy.alpha_detector - INFO - Alpha scan found 3 signals
2026-01-22 10:32:31,561 - core.sentiment_trading - INFO - Pipeline scan found 3 signals
2026-01-22 10:32:31,561 - core.autonomy.orchestrator - INFO - Sentiment pipeline found 3 signals
2026-01-22 10:32:31,678 - jarvis.grok - INFO - [EVENT] GROK_API_CALL
2026-01-22 10:32:31,678 - core.autonomy.alpha_detector - INFO - Alpha scan found 3 signals
2026-01-22 10:32:32,237 - bots.buy_tracker.monitor - INFO - Found 1 new transaction(s) to process
2026-01-22 10:32:49,627 - jarvis.monitoring.health_bus - INFO - Health check: healthy - 7 healthy, 0 degraded, 0 critical
2026-01-22 10:32:56,353 - bots.buy_tracker.monitor - INFO - Found 1 new transaction(s) to process
2026-01-22 10:32:57,486 - jarvis.supervisor - INFO - === COMPONENT HEALTH ===
  buy_bot: running (uptime: 0:04:07.950315) (restarts: 0)
  sentiment_reporter: running (uptime: 0:04:04.683342) (restarts: 0)
  twitter_poster: running (uptime: 0:04:04.661178) (restarts: 0)
  telegram_bot: running (uptime: 0:04:03.417182) (restarts: 0)
  autonomous_x: running (uptime: 0:04:02.658210) (restarts: 0)
  public_trading_bot: stopped (restarts: 0)
  autonomous_manager: running (uptime: 0:04:00.076341) (restarts: 0)
  bags_intel: running (uptime: 0:04:00.047155) (restarts: 0)
2026-01-22 10:33:03,213 - bots.buy_tracker.monitor - INFO - Found 1 new transaction(s) to process
2026-01-22 10:33:15,767 - bots.buy_tracker.monitor - INFO - Found 1 new transaction(s) to process
2026-01-22 10:33:19,627 - jarvis.monitoring.health_bus - INFO - Health check: healthy - 7 healthy, 0 degraded, 0 critical
2026-01-22 10:33:31,666 - core.autonomy.self_learning - INFO - Pattern analysis complete. Best hours: [23, 0, 2]
2026-01-22 10:33:31,669 - core.autonomy.self_learning - INFO - Pattern analysis complete. Best hours: [23, 0, 2]
2026-01-22 10:33:31,669 - core.autonomy.news_detector - INFO - News scan found 0 events
2026-01-22 10:33:31,670 - core.autonomy.news_detector - INFO - News scan found 0 events
2026-01-22 10:33:35,786 - jarvis.grok - INFO - [EVENT] GROK_API_CALL
2026-01-22 10:33:35,787 - core.autonomy.alpha_detector - INFO - Alpha scan found 3 signals
2026-01-22 10:33:36,857 - jarvis.grok - INFO - [EVENT] GROK_API_CALL
2026-01-22 10:33:36,857 - core.autonomy.alpha_detector - INFO - Alpha scan found 3 signals
2026-01-22 10:33:36,857 - core.sentiment_trading - INFO - Pipeline scan found 3 signals
2026-01-22 10:33:36,857 - core.autonomy.orchestrator - INFO - Sentiment pipeline found 3 signals
2026-01-22 10:33:47,631 - bots.buy_tracker.monitor - INFO - Poll #45: 325 txns tracked across 11 pairs, min=$1.0
2026-01-22 10:33:49,649 - jarvis.monitoring.health_bus - INFO - Health check: healthy - 7 healthy, 0 degraded, 0 critical
2026-01-22 10:33:57,502 - jarvis.supervisor - INFO - === COMPONENT HEALTH ===
  buy_bot: running (uptime: 0:05:07.966029) (restarts: 0)
  sentiment_reporter: running (uptime: 0:05:04.699056) (restarts: 0)
  twitter_poster: running (uptime: 0:05:04.676892) (restarts: 0)
  telegram_bot: running (uptime: 0:05:03.432896) (restarts: 0)
  autonomous_x: running (uptime: 0:05:02.673924) (restarts: 0)
  public_trading_bot: stopped (restarts: 0)
  autonomous_manager: running (uptime: 0:05:00.092055) (restarts: 0)
  bags_intel: running (uptime: 0:05:00.062869) (restarts: 0)
2026-01-22 10:33:58,187 - core.autonomous_manager - INFO - 📚 Learning recommendations: ['Focus on market_analysis, trading_signals content - highest engagement', 'Post around 0:00 UTC for best engagement', 'Reduce sentiment content - lowest engagement', 'Engagement is strong - maintain current content strategy']
2026-01-22 10:34:19,662 - jarvis.monitoring.health_bus - INFO - Health check: healthy - 7 healthy, 0 degraded, 0 critical
2026-01-22 10:34:36,867 - core.autonomy.self_learning - INFO - Pattern analysis complete. Best hours: [23, 0, 2]
2026-01-22 10:34:36,871 - core.autonomy.self_learning - INFO - Pattern analysis complete. Best hours: [23, 0, 2]
2026-01-22 10:34:36,872 - core.autonomy.news_detector - INFO - News scan found 0 events
2026-01-22 10:34:36,872 - core.autonomy.news_detector - INFO - News scan found 0 events
2026-01-22 10:34:41,272 - jarvis.grok - INFO - [EVENT] GROK_API_CALL
2026-01-22 10:34:41,273 - core.autonomy.alpha_detector - INFO - Alpha scan found 3 signals
2026-01-22 10:34:41,273 - core.sentiment_trading - INFO - Pipeline scan found 3 signals
2026-01-22 10:34:41,273 - core.autonomy.orchestrator - INFO - Sentiment pipeline found 3 signals
2026-01-22 10:34:41,552 - jarvis.grok - INFO - [EVENT] GROK_API_CALL
2026-01-22 10:34:41,552 - core.autonomy.alpha_detector - INFO - Alpha scan found 3 signals
2026-01-22 10:34:49,669 - jarvis.monitoring.health_bus - INFO - Health check: healthy - 7 healthy, 0 degraded, 0 critical
2026-01-22 10:34:57,515 - jarvis.supervisor - INFO - === COMPONENT HEALTH ===
  buy_bot: running (uptime: 0:06:07.979239) (restarts: 0)
  sentiment_reporter: running (uptime: 0:06:04.712266) (restarts: 0)
  twitter_poster: running (uptime: 0:06:04.690102) (restarts: 0)
  telegram_bot: running (uptime: 0:06:03.446106) (restarts: 0)
  autonomous_x: running (uptime: 0:06:02.687134) (restarts: 0)
  public_trading_bot: stopped (restarts: 0)
  autonomous_manager: running (uptime: 0:06:00.105265) (restarts: 0)
  bags_intel: running (uptime: 0:06:00.076079) (restarts: 0)
2026-01-22 10:35:16,124 - bots.buy_tracker.monitor - INFO - Poll #60: 325 txns tracked across 11 pairs, min=$1.0
2026-01-22 10:35:19,680 - jarvis.monitoring.health_bus - INFO - Health check: healthy - 7 healthy, 0 degraded, 0 critical
2026-01-22 10:35:28,864 - bots.buy_tracker.monitor - INFO - Found 1 new transaction(s) to process
2026-01-22 10:35:40,924 - bots.buy_tracker.monitor - INFO - Found 1 new transaction(s) to process
2026-01-22 10:35:41,598 - core.autonomy.self_learning - INFO - Pattern analysis complete. Best hours: [23, 0, 2]
2026-01-22 10:35:41,604 - core.autonomy.self_learning - INFO - Pattern analysis complete. Best hours: [23, 0, 2]
2026-01-22 10:35:41,604 - core.autonomy.news_detector - INFO - News scan found 0 events
2026-01-22 10:35:41,604 - core.autonomy.news_detector - INFO - News scan found 0 events
2026-01-22 10:35:45,635 - jarvis.grok - INFO - [EVENT] GROK_API_CALL
2026-01-22 10:35:45,636 - core.autonomy.alpha_detector - INFO - Alpha scan found 3 signals
2026-01-22 10:35:45,636 - core.sentiment_trading - INFO - Pipeline scan found 3 signals
2026-01-22 10:35:45,636 - core.autonomy.orchestrator - INFO - Sentiment pipeline found 3 signals
2026-01-22 10:35:45,691 - jarvis.grok - INFO - [EVENT] GROK_API_CALL
2026-01-22 10:35:45,691 - core.autonomy.alpha_detector - INFO - Alpha scan found 3 signals
2026-01-22 10:35:49,661 - jarvis.monitoring.health_bus - INFO - Health check: healthy - 7 healthy, 0 degraded, 0 critical
2026-01-22 10:35:57,532 - jarvis.supervisor - INFO - === COMPONENT HEALTH ===
  buy_bot: running (uptime: 0:07:07.995910) (restarts: 0)
  sentiment_reporter: running (uptime: 0:07:04.728937) (restarts: 0)
  twitter_poster: running (uptime: 0:07:04.706773) (restarts: 0)
  telegram_bot: running (uptime: 0:07:03.462777) (restarts: 0)
  autonomous_x: running (uptime: 0:07:02.703805) (restarts: 0)
  public_trading_bot: stopped (restarts: 0)
  autonomous_manager: running (uptime: 0:07:00.121936) (restarts: 0)
  bags_intel: running (uptime: 0:07:00.092750) (restarts: 0)
```

### logs/validation.log (tail 200 lines)
Path: `logs\validation.log`
```text
2026-01-18 01:19:39,894 - [validation_loop] - INFO - [TEST 1] Position sync: treasury → scorekeeper
2026-01-18 01:19:39,894 - [validation_loop] - INFO -   Treasury has 12 open positions
2026-01-18 01:19:39,894 - [validation_loop] - INFO -   Synced 0 positions to scorekeeper
2026-01-18 01:19:39,894 - [validation_loop] - INFO -   Scorekeeper has 21 open positions
2026-01-18 01:19:39,894 - [validation_loop] - INFO - [PASS] Position Sync: treasury → scorekeeper → dashboard
2026-01-18 01:19:39,894 - [validation_loop] - INFO - [TEST 2] Moderation: toxicity detection + auto-actions
2026-01-18 01:19:39,896 - [validation_loop] - INFO -   Toxic scan result: 4 (confidence: 0.9%)
2026-01-18 01:19:39,896 - [validation_loop] - INFO -   Clean scan result: 0 (confidence: 1.0%)
2026-01-18 01:19:39,896 - [validation_loop] - INFO -   Moderation decision: False, Action: log
2026-01-18 01:19:39,897 - [validation_loop] - INFO -   Stats: messages_checked=0, actions_taken=0
2026-01-18 01:19:39,897 - [validation_loop] - INFO - [PASS] Moderation: toxicity detection + auto-actions
2026-01-18 01:19:39,897 - [validation_loop] - INFO - [TEST 3] Learning: engagement analyzer
2026-01-18 01:19:39,901 - [core.learning.engagement_analyzer] - INFO - Loaded 783 historical metrics
2026-01-18 01:19:39,901 - [core.learning.engagement_analyzer] - INFO - Recorded engagement: market_analysis - Score: 100.0
2026-01-18 01:19:39,901 - [validation_loop] - INFO -   Recorded engagement #1: quality_score=100.0
2026-01-18 01:19:39,901 - [core.learning.engagement_analyzer] - INFO - Recorded engagement: trading_signals - Score: 100.0
2026-01-18 01:19:39,901 - [validation_loop] - INFO -   Recorded engagement #2: quality_score=100.0
2026-01-18 01:19:39,901 - [core.learning.engagement_analyzer] - INFO - Recorded engagement: sentiment - Score: 100.0
2026-01-18 01:19:39,901 - [validation_loop] - INFO -   Recorded engagement #3: quality_score=100.0
2026-01-18 01:19:39,901 - [validation_loop] - INFO -   Generated 4 recommendations
2026-01-18 01:19:39,901 - [validation_loop] - INFO -     - Focus on market_analysis, trading_signals content - highest engagement
2026-01-18 01:19:39,901 - [validation_loop] - INFO -     - Post around 0:00 UTC for best engagement
2026-01-18 01:19:39,901 - [validation_loop] - INFO -     - Reduce sentiment content - lowest engagement
2026-01-18 01:19:39,901 - [validation_loop] - INFO -     - Engagement is strong - maintain current content strategy
2026-01-18 01:19:39,903 - [validation_loop] - INFO -   Summary: 3 top categories tracked
2026-01-18 01:19:39,903 - [validation_loop] - INFO -   Metrics recorded: 786
2026-01-18 01:19:39,931 - [validation_loop] - INFO -   State persisted to disk
2026-01-18 01:19:39,931 - [validation_loop] - INFO - [PASS] Learning: engagement analyzer recommendations
2026-01-18 01:19:39,931 - [validation_loop] - INFO - [TEST 4] Vibe coding: sentiment → regime adaptation
2026-01-18 01:19:39,931 - [core.vibe_coding.sentiment_mapper] - INFO - Sentiment: 15.0/100 → Regime: fear
2026-01-18 01:19:39,931 - [validation_loop] - INFO -   Sentiment  15 → fear       (position_size: 0.3x)
2026-01-18 01:19:39,931 - [core.vibe_coding.sentiment_mapper] - INFO - Sentiment: 25.0/100 → Regime: fear
2026-01-18 01:19:39,931 - [validation_loop] - INFO -   Sentiment  25 → fear       (position_size: 0.3x)
2026-01-18 01:19:39,931 - [core.vibe_coding.sentiment_mapper] - INFO - Sentiment: 50.0/100 → Regime: sideways
2026-01-18 01:19:39,931 - [validation_loop] - INFO -   Sentiment  50 → sideways   (position_size: 1.0x)
2026-01-18 01:19:39,931 - [core.vibe_coding.sentiment_mapper] - INFO - Sentiment: 50.0/100 → Regime: sideways
2026-01-18 01:19:39,931 - [core.vibe_coding.regime_adapter] - INFO - Adapted to sideways: 6 parameter(s) changed
2026-01-18 01:19:39,931 - [validation_loop] - INFO -     Adapted: 6 parameters changed
2026-01-18 01:19:39,931 - [core.vibe_coding.sentiment_mapper] - INFO - Sentiment: 70.0/100 → Regime: bullish
2026-01-18 01:19:39,931 - [validation_loop] - INFO -   Sentiment  70 → bullish    (position_size: 1.3x)
2026-01-18 01:19:39,931 - [core.vibe_coding.sentiment_mapper] - INFO - Sentiment: 70.0/100 → Regime: bullish
2026-01-18 01:19:39,931 - [core.vibe_coding.regime_adapter] - INFO - Adapted to bullish: 6 parameter(s) changed
2026-01-18 01:19:39,931 - [validation_loop] - INFO -     Adapted: 6 parameters changed
2026-01-18 01:19:39,931 - [core.vibe_coding.sentiment_mapper] - INFO - Sentiment: 85.0/100 → Regime: euphoria
2026-01-18 01:19:39,931 - [validation_loop] - INFO -   Sentiment  85 → euphoria   (position_size: 0.8x)
2026-01-18 01:19:39,931 - [core.vibe_coding.sentiment_mapper] - INFO - Sentiment: 85.0/100 → Regime: euphoria
2026-01-18 01:19:39,931 - [core.vibe_coding.regime_adapter] - INFO - Adapted to euphoria: 6 parameter(s) changed
2026-01-18 01:19:39,934 - [validation_loop] - INFO -     Adapted: 6 parameters changed
2026-01-18 01:19:39,934 - [validation_loop] - INFO - [PASS] Vibe Coding: sentiment → regime adaptation
2026-01-18 01:19:39,934 - [validation_loop] - INFO - [TEST 5] Autonomous manager loops
2026-01-18 01:19:39,941 - [core.learning.engagement_analyzer] - INFO - Loaded 786 historical metrics
2026-01-18 01:19:39,941 - [validation_loop] - INFO -   Manager status: running=False
2026-01-18 01:19:39,941 - [validation_loop] - INFO -   Stats: {'messages_checked': 0, 'content_moderated': 0, 'regimes_adapted': 0, 'improvements_made': 0}
2026-01-18 01:19:39,941 - [validation_loop] - INFO -   All components initialized successfully
2026-01-18 01:19:39,941 - [validation_loop] - INFO -   Autonomous loops configured and ready to start
2026-01-18 01:19:39,941 - [validation_loop] - INFO - [PASS] Autonomous Loops: manager initialization and status
2026-01-18 01:19:39,941 - [validation_loop] - INFO - [TEST 6] State persistence
2026-01-18 01:19:39,941 - [validation_loop] - INFO -   Found: engagement_metrics.json
2026-01-18 01:19:39,942 - [validation_loop] - INFO -   Missing: .positions.json (will be created on first use)
2026-01-18 01:19:39,942 - [validation_loop] - INFO - [PASS] State Persistence: state files exist and accessible
2026-01-18 01:19:44,017 - [validation_loop] - INFO - Saved proof to C:\Users\lucid\OneDrive\Desktop\Projects\Jarvis\data\validation_proof\proof_770.json
2026-01-18 01:19:44,017 - [validation_loop] - INFO - 
Iteration 770 Results: 6/6 tests passed
2026-01-18 01:19:44,017 - [validation_loop] - INFO - [ITERATION_STATUS] All tests passed!
2026-01-18 01:19:44,017 - [validation_loop] - INFO - 
Next iteration in 30 seconds (Ctrl+C to stop)...
2026-01-18 01:20:14,016 - [validation_loop] - INFO - 
============================================================
2026-01-18 01:20:14,016 - [validation_loop] - INFO - VALIDATION ITERATION 771
2026-01-18 01:20:14,016 - [validation_loop] - INFO - ============================================================
2026-01-18 01:20:14,016 - [validation_loop] - INFO - [TEST 1] Position sync: treasury → scorekeeper
2026-01-18 01:20:14,016 - [validation_loop] - INFO -   Treasury has 12 open positions
2026-01-18 01:20:14,016 - [validation_loop] - INFO -   Synced 0 positions to scorekeeper
2026-01-18 01:20:14,016 - [validation_loop] - INFO -   Scorekeeper has 21 open positions
2026-01-18 01:20:14,016 - [validation_loop] - INFO - [PASS] Position Sync: treasury → scorekeeper → dashboard
2026-01-18 01:20:14,016 - [validation_loop] - INFO - [TEST 2] Moderation: toxicity detection + auto-actions
2026-01-18 01:20:14,017 - [validation_loop] - INFO -   Toxic scan result: 4 (confidence: 0.9%)
2026-01-18 01:20:14,017 - [validation_loop] - INFO -   Clean scan result: 0 (confidence: 1.0%)
2026-01-18 01:20:14,017 - [validation_loop] - INFO -   Moderation decision: False, Action: log
2026-01-18 01:20:14,017 - [validation_loop] - INFO -   Stats: messages_checked=0, actions_taken=0
2026-01-18 01:20:14,017 - [validation_loop] - INFO - [PASS] Moderation: toxicity detection + auto-actions
2026-01-18 01:20:14,017 - [validation_loop] - INFO - [TEST 3] Learning: engagement analyzer
2026-01-18 01:20:14,022 - [core.learning.engagement_analyzer] - INFO - Loaded 786 historical metrics
2026-01-18 01:20:14,022 - [core.learning.engagement_analyzer] - INFO - Recorded engagement: market_analysis - Score: 100.0
2026-01-18 01:20:14,022 - [validation_loop] - INFO -   Recorded engagement #1: quality_score=100.0
2026-01-18 01:20:14,022 - [core.learning.engagement_analyzer] - INFO - Recorded engagement: trading_signals - Score: 100.0
2026-01-18 01:20:14,023 - [validation_loop] - INFO -   Recorded engagement #2: quality_score=100.0
2026-01-18 01:20:14,023 - [core.learning.engagement_analyzer] - INFO - Recorded engagement: sentiment - Score: 100.0
2026-01-18 01:20:14,023 - [validation_loop] - INFO -   Recorded engagement #3: quality_score=100.0
2026-01-18 01:20:14,023 - [validation_loop] - INFO -   Generated 4 recommendations
2026-01-18 01:20:14,023 - [validation_loop] - INFO -     - Focus on market_analysis, trading_signals content - highest engagement
2026-01-18 01:20:14,023 - [validation_loop] - INFO -     - Post around 0:00 UTC for best engagement
2026-01-18 01:20:14,023 - [validation_loop] - INFO -     - Reduce sentiment content - lowest engagement
2026-01-18 01:20:14,023 - [validation_loop] - INFO -     - Engagement is strong - maintain current content strategy
2026-01-18 01:20:14,024 - [validation_loop] - INFO -   Summary: 3 top categories tracked
2026-01-18 01:20:14,024 - [validation_loop] - INFO -   Metrics recorded: 789
2026-01-18 01:20:14,048 - [validation_loop] - INFO -   State persisted to disk
2026-01-18 01:20:14,048 - [validation_loop] - INFO - [PASS] Learning: engagement analyzer recommendations
2026-01-18 01:20:14,048 - [validation_loop] - INFO - [TEST 4] Vibe coding: sentiment → regime adaptation
2026-01-18 01:20:14,048 - [core.vibe_coding.sentiment_mapper] - INFO - Sentiment: 15.0/100 → Regime: fear
2026-01-18 01:20:14,048 - [validation_loop] - INFO -   Sentiment  15 → fear       (position_size: 0.3x)
2026-01-18 01:20:14,048 - [core.vibe_coding.sentiment_mapper] - INFO - Sentiment: 25.0/100 → Regime: fear
2026-01-18 01:20:14,048 - [validation_loop] - INFO -   Sentiment  25 → fear       (position_size: 0.3x)
2026-01-18 01:20:14,048 - [core.vibe_coding.sentiment_mapper] - INFO - Sentiment: 50.0/100 → Regime: sideways
2026-01-18 01:20:14,049 - [validation_loop] - INFO -   Sentiment  50 → sideways   (position_size: 1.0x)
2026-01-18 01:20:14,049 - [core.vibe_coding.sentiment_mapper] - INFO - Sentiment: 50.0/100 → Regime: sideways
2026-01-18 01:20:14,049 - [core.vibe_coding.regime_adapter] - INFO - Adapted to sideways: 6 parameter(s) changed
2026-01-18 01:20:14,049 - [validation_loop] - INFO -     Adapted: 6 parameters changed
2026-01-18 01:20:14,050 - [core.vibe_coding.sentiment_mapper] - INFO - Sentiment: 70.0/100 → Regime: bullish
2026-01-18 01:20:14,050 - [validation_loop] - INFO -   Sentiment  70 → bullish    (position_size: 1.3x)
2026-01-18 01:20:14,050 - [core.vibe_coding.sentiment_mapper] - INFO - Sentiment: 70.0/100 → Regime: bullish
2026-01-18 01:20:14,050 - [core.vibe_coding.regime_adapter] - INFO - Adapted to bullish: 6 parameter(s) changed
2026-01-18 01:20:14,050 - [validation_loop] - INFO -     Adapted: 6 parameters changed
2026-01-18 01:20:14,050 - [core.vibe_coding.sentiment_mapper] - INFO - Sentiment: 85.0/100 → Regime: euphoria
2026-01-18 01:20:14,050 - [validation_loop] - INFO -   Sentiment  85 → euphoria   (position_size: 0.8x)
2026-01-18 01:20:14,050 - [core.vibe_coding.sentiment_mapper] - INFO - Sentiment: 85.0/100 → Regime: euphoria
2026-01-18 01:20:14,051 - [core.vibe_coding.regime_adapter] - INFO - Adapted to euphoria: 6 parameter(s) changed
2026-01-18 01:20:14,051 - [validation_loop] - INFO -     Adapted: 6 parameters changed
2026-01-18 01:20:14,051 - [validation_loop] - INFO - [PASS] Vibe Coding: sentiment → regime adaptation
2026-01-18 01:20:14,051 - [validation_loop] - INFO - [TEST 5] Autonomous manager loops
2026-01-18 01:20:14,056 - [core.learning.engagement_analyzer] - INFO - Loaded 789 historical metrics
2026-01-18 01:20:14,056 - [validation_loop] - INFO -   Manager status: running=False
2026-01-18 01:20:14,057 - [validation_loop] - INFO -   Stats: {'messages_checked': 0, 'content_moderated': 0, 'regimes_adapted': 0, 'improvements_made': 0}
2026-01-18 01:20:14,057 - [validation_loop] - INFO -   All components initialized successfully
2026-01-18 01:20:14,057 - [validation_loop] - INFO -   Autonomous loops configured and ready to start
2026-01-18 01:20:14,057 - [validation_loop] - INFO - [PASS] Autonomous Loops: manager initialization and status
2026-01-18 01:20:14,057 - [validation_loop] - INFO - [TEST 6] State persistence
2026-01-18 01:20:14,058 - [validation_loop] - INFO -   Found: engagement_metrics.json
2026-01-18 01:20:14,058 - [validation_loop] - INFO -   Missing: .positions.json (will be created on first use)
2026-01-18 01:20:14,058 - [validation_loop] - INFO - [PASS] State Persistence: state files exist and accessible
2026-01-18 01:20:14,208 - [validation_loop] - INFO - Saved proof to C:\Users\lucid\OneDrive\Desktop\Projects\Jarvis\data\validation_proof\proof_771.json
2026-01-18 01:20:14,208 - [validation_loop] - INFO - 
Iteration 771 Results: 6/6 tests passed
2026-01-18 01:20:14,208 - [validation_loop] - INFO - [ITERATION_STATUS] All tests passed!
2026-01-18 01:20:14,208 - [validation_loop] - INFO - 
Next iteration in 30 seconds (Ctrl+C to stop)...
2026-01-18 01:20:44,217 - [validation_loop] - INFO - 
============================================================
2026-01-18 01:20:44,217 - [validation_loop] - INFO - VALIDATION ITERATION 772
2026-01-18 01:20:44,217 - [validation_loop] - INFO - ============================================================
2026-01-18 01:20:44,217 - [validation_loop] - INFO - [TEST 1] Position sync: treasury → scorekeeper
2026-01-18 01:20:44,217 - [validation_loop] - INFO -   Treasury has 12 open positions
2026-01-18 01:20:44,217 - [validation_loop] - INFO -   Synced 0 positions to scorekeeper
2026-01-18 01:20:44,217 - [validation_loop] - INFO -   Scorekeeper has 21 open positions
2026-01-18 01:20:44,217 - [validation_loop] - INFO - [PASS] Position Sync: treasury → scorekeeper → dashboard
2026-01-18 01:20:44,217 - [validation_loop] - INFO - [TEST 2] Moderation: toxicity detection + auto-actions
2026-01-18 01:20:44,217 - [validation_loop] - INFO -   Toxic scan result: 4 (confidence: 0.9%)
2026-01-18 01:20:44,218 - [validation_loop] - INFO -   Clean scan result: 0 (confidence: 1.0%)
2026-01-18 01:20:44,218 - [validation_loop] - INFO -   Moderation decision: False, Action: log
2026-01-18 01:20:44,218 - [validation_loop] - INFO -   Stats: messages_checked=0, actions_taken=0
2026-01-18 01:20:44,218 - [validation_loop] - INFO - [PASS] Moderation: toxicity detection + auto-actions
2026-01-18 01:20:44,218 - [validation_loop] - INFO - [TEST 3] Learning: engagement analyzer
2026-01-18 01:20:44,222 - [core.learning.engagement_analyzer] - INFO - Loaded 789 historical metrics
2026-01-18 01:20:44,222 - [core.learning.engagement_analyzer] - INFO - Recorded engagement: market_analysis - Score: 100.0
2026-01-18 01:20:44,222 - [validation_loop] - INFO -   Recorded engagement #1: quality_score=100.0
2026-01-18 01:20:44,222 - [core.learning.engagement_analyzer] - INFO - Recorded engagement: trading_signals - Score: 100.0
2026-01-18 01:20:44,222 - [validation_loop] - INFO -   Recorded engagement #2: quality_score=100.0
2026-01-18 01:20:44,222 - [core.learning.engagement_analyzer] - INFO - Recorded engagement: sentiment - Score: 100.0
2026-01-18 01:20:44,222 - [validation_loop] - INFO -   Recorded engagement #3: quality_score=100.0
2026-01-18 01:20:44,223 - [validation_loop] - INFO -   Generated 4 recommendations
2026-01-18 01:20:44,223 - [validation_loop] - INFO -     - Focus on market_analysis, trading_signals content - highest engagement
2026-01-18 01:20:44,223 - [validation_loop] - INFO -     - Post around 0:00 UTC for best engagement
2026-01-18 01:20:44,223 - [validation_loop] - INFO -     - Reduce sentiment content - lowest engagement
2026-01-18 01:20:44,223 - [validation_loop] - INFO -     - Engagement is strong - maintain current content strategy
2026-01-18 01:20:44,223 - [validation_loop] - INFO -   Summary: 3 top categories tracked
2026-01-18 01:20:44,223 - [validation_loop] - INFO -   Metrics recorded: 792
2026-01-18 01:20:50,362 - [validation_loop] - INFO -   State persisted to disk
2026-01-18 01:20:50,362 - [validation_loop] - INFO - [PASS] Learning: engagement analyzer recommendations
2026-01-18 01:20:50,362 - [validation_loop] - INFO - [TEST 4] Vibe coding: sentiment → regime adaptation
2026-01-18 01:20:50,362 - [core.vibe_coding.sentiment_mapper] - INFO - Sentiment: 15.0/100 → Regime: fear
2026-01-18 01:20:50,363 - [validation_loop] - INFO -   Sentiment  15 → fear       (position_size: 0.3x)
2026-01-18 01:20:50,363 - [core.vibe_coding.sentiment_mapper] - INFO - Sentiment: 25.0/100 → Regime: fear
2026-01-18 01:20:50,363 - [validation_loop] - INFO -   Sentiment  25 → fear       (position_size: 0.3x)
2026-01-18 01:20:50,363 - [core.vibe_coding.sentiment_mapper] - INFO - Sentiment: 50.0/100 → Regime: sideways
2026-01-18 01:20:50,363 - [validation_loop] - INFO -   Sentiment  50 → sideways   (position_size: 1.0x)
2026-01-18 01:20:50,363 - [core.vibe_coding.sentiment_mapper] - INFO - Sentiment: 50.0/100 → Regime: sideways
2026-01-18 01:20:50,363 - [core.vibe_coding.regime_adapter] - INFO - Adapted to sideways: 6 parameter(s) changed
2026-01-18 01:20:50,363 - [validation_loop] - INFO -     Adapted: 6 parameters changed
2026-01-18 01:20:50,363 - [core.vibe_coding.sentiment_mapper] - INFO - Sentiment: 70.0/100 → Regime: bullish
2026-01-18 01:20:50,363 - [validation_loop] - INFO -   Sentiment  70 → bullish    (position_size: 1.3x)
2026-01-18 01:20:50,363 - [core.vibe_coding.sentiment_mapper] - INFO - Sentiment: 70.0/100 → Regime: bullish
2026-01-18 01:20:50,363 - [core.vibe_coding.regime_adapter] - INFO - Adapted to bullish: 6 parameter(s) changed
2026-01-18 01:20:50,363 - [validation_loop] - INFO -     Adapted: 6 parameters changed
2026-01-18 01:20:50,363 - [core.vibe_coding.sentiment_mapper] - INFO - Sentiment: 85.0/100 → Regime: euphoria
2026-01-18 01:20:50,363 - [validation_loop] - INFO -   Sentiment  85 → euphoria   (position_size: 0.8x)
2026-01-18 01:20:50,363 - [core.vibe_coding.sentiment_mapper] - INFO - Sentiment: 85.0/100 → Regime: euphoria
2026-01-18 01:20:50,363 - [core.vibe_coding.regime_adapter] - INFO - Adapted to euphoria: 6 parameter(s) changed
2026-01-18 01:20:50,363 - [validation_loop] - INFO -     Adapted: 6 parameters changed
2026-01-18 01:20:50,363 - [validation_loop] - INFO - [PASS] Vibe Coding: sentiment → regime adaptation
2026-01-18 01:20:50,363 - [validation_loop] - INFO - [TEST 5] Autonomous manager loops
2026-01-18 01:20:53,704 - [core.learning.engagement_analyzer] - INFO - Loaded 792 historical metrics
2026-01-18 01:20:53,705 - [validation_loop] - INFO -   Manager status: running=False
2026-01-18 01:20:53,705 - [validation_loop] - INFO -   Stats: {'messages_checked': 0, 'content_moderated': 0, 'regimes_adapted': 0, 'improvements_made': 0}
2026-01-18 01:20:53,705 - [validation_loop] - INFO -   All components initialized successfully
2026-01-18 01:20:53,705 - [validation_loop] - INFO -   Autonomous loops configured and ready to start
2026-01-18 01:20:53,705 - [validation_loop] - INFO - [PASS] Autonomous Loops: manager initialization and status
2026-01-18 01:20:53,705 - [validation_loop] - INFO - [TEST 6] State persistence
2026-01-18 01:20:53,706 - [validation_loop] - INFO -   Found: engagement_metrics.json
2026-01-18 01:20:53,706 - [validation_loop] - INFO -   Missing: .positions.json (will be created on first use)
2026-01-18 01:20:53,706 - [validation_loop] - INFO - [PASS] State Persistence: state files exist and accessible
```

### logs/telegram_bot_errors.log (tail 200 lines)
Path: `logs\telegram_bot_errors.log`
```text

2026-01-22 10:27:58,473 CRITICAL tg_bot.bot_core CONFLICT ERROR: Another bot instance is polling. Kill other instances or wait for them to stop. Bot will continue retrying but may not receive updates.
2026-01-22 10:28:20,219 ERROR tg_bot.bot_core Bot error: Conflict: Conflict: terminated by other getUpdates request; make sure that only one bot instance is running
2026-01-22 10:28:20,221 ERROR tg_bot.bot_core Traceback: "C:\Users\lucid\AppData\Local\Programs\Python\Python312\Lib\site-packages\telegram\request\_baserequest.py", line 198, in post
    result = await self._request_wrapper(
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "C:\Users\lucid\AppData\Local\Programs\Python\Python312\Lib\site-packages\telegram\request\_baserequest.py", line 375, in _request_wrapper
    raise exception
telegram.error.Conflict: Conflict: terminated by other getUpdates request; make sure that only one bot instance is running

2026-01-22 10:28:20,223 CRITICAL tg_bot.bot_core CONFLICT ERROR: Another bot instance is polling. Kill other instances or wait for them to stop. Bot will continue retrying but may not receive updates.
2026-01-22 10:29:10,305 ERROR tg_bot.bot_core Bot error: Conflict: Conflict: terminated by other getUpdates request; make sure that only one bot instance is running
2026-01-22 10:29:10,311 ERROR tg_bot.bot_core Traceback: "C:\Users\lucid\AppData\Local\Programs\Python\Python312\Lib\site-packages\telegram\request\_baserequest.py", line 198, in post
    result = await self._request_wrapper(
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "C:\Users\lucid\AppData\Local\Programs\Python\Python312\Lib\site-packages\telegram\request\_baserequest.py", line 375, in _request_wrapper
    raise exception
telegram.error.Conflict: Conflict: terminated by other getUpdates request; make sure that only one bot instance is running

2026-01-22 10:29:10,312 CRITICAL tg_bot.bot_core CONFLICT ERROR: Another bot instance is polling. Kill other instances or wait for them to stop. Bot will continue retrying but may not receive updates.
2026-01-22 10:29:16,069 ERROR tg_bot.bot_core Bot error: Conflict: Conflict: terminated by other getUpdates request; make sure that only one bot instance is running
2026-01-22 10:29:16,071 ERROR tg_bot.bot_core Traceback: "C:\Users\lucid\AppData\Local\Programs\Python\Python312\Lib\site-packages\telegram\request\_baserequest.py", line 198, in post
    result = await self._request_wrapper(
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "C:\Users\lucid\AppData\Local\Programs\Python\Python312\Lib\site-packages\telegram\request\_baserequest.py", line 375, in _request_wrapper
    raise exception
telegram.error.Conflict: Conflict: terminated by other getUpdates request; make sure that only one bot instance is running

2026-01-22 10:29:16,073 CRITICAL tg_bot.bot_core CONFLICT ERROR: Another bot instance is polling. Kill other instances or wait for them to stop. Bot will continue retrying but may not receive updates.
2026-01-22 10:29:23,083 ERROR tg_bot.bot_core Bot error: Conflict: Conflict: terminated by other getUpdates request; make sure that only one bot instance is running
2026-01-22 10:29:23,084 ERROR tg_bot.bot_core Traceback: "C:\Users\lucid\AppData\Local\Programs\Python\Python312\Lib\site-packages\telegram\request\_baserequest.py", line 198, in post
    result = await self._request_wrapper(
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "C:\Users\lucid\AppData\Local\Programs\Python\Python312\Lib\site-packages\telegram\request\_baserequest.py", line 375, in _request_wrapper
    raise exception
telegram.error.Conflict: Conflict: terminated by other getUpdates request; make sure that only one bot instance is running

2026-01-22 10:29:23,087 CRITICAL tg_bot.bot_core CONFLICT ERROR: Another bot instance is polling. Kill other instances or wait for them to stop. Bot will continue retrying but may not receive updates.
2026-01-22 10:29:27,733 ERROR tg_bot.bot_core Bot error: Conflict: Conflict: terminated by other getUpdates request; make sure that only one bot instance is running
2026-01-22 10:29:27,734 ERROR tg_bot.bot_core Traceback: "C:\Users\lucid\AppData\Local\Programs\Python\Python312\Lib\site-packages\telegram\request\_baserequest.py", line 198, in post
    result = await self._request_wrapper(
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "C:\Users\lucid\AppData\Local\Programs\Python\Python312\Lib\site-packages\telegram\request\_baserequest.py", line 375, in _request_wrapper
    raise exception
telegram.error.Conflict: Conflict: terminated by other getUpdates request; make sure that only one bot instance is running

2026-01-22 10:29:27,735 CRITICAL tg_bot.bot_core CONFLICT ERROR: Another bot instance is polling. Kill other instances or wait for them to stop. Bot will continue retrying but may not receive updates.
2026-01-22 10:29:37,943 ERROR tg_bot.bot_core Bot error: Conflict: Conflict: terminated by other getUpdates request; make sure that only one bot instance is running
2026-01-22 10:29:37,944 ERROR tg_bot.bot_core Traceback: "C:\Users\lucid\AppData\Local\Programs\Python\Python312\Lib\site-packages\telegram\request\_baserequest.py", line 198, in post
    result = await self._request_wrapper(
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "C:\Users\lucid\AppData\Local\Programs\Python\Python312\Lib\site-packages\telegram\request\_baserequest.py", line 375, in _request_wrapper
    raise exception
telegram.error.Conflict: Conflict: terminated by other getUpdates request; make sure that only one bot instance is running

2026-01-22 10:29:37,945 CRITICAL tg_bot.bot_core CONFLICT ERROR: Another bot instance is polling. Kill other instances or wait for them to stop. Bot will continue retrying but may not receive updates.
2026-01-22 10:30:19,448 ERROR tg_bot.bot_core Bot error: Conflict: Conflict: terminated by other getUpdates request; make sure that only one bot instance is running
2026-01-22 10:30:19,448 ERROR tg_bot.bot_core Traceback: "C:\Users\lucid\AppData\Local\Programs\Python\Python312\Lib\site-packages\telegram\request\_baserequest.py", line 198, in post
    result = await self._request_wrapper(
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "C:\Users\lucid\AppData\Local\Programs\Python\Python312\Lib\site-packages\telegram\request\_baserequest.py", line 375, in _request_wrapper
    raise exception
telegram.error.Conflict: Conflict: terminated by other getUpdates request; make sure that only one bot instance is running

2026-01-22 10:30:19,450 CRITICAL tg_bot.bot_core CONFLICT ERROR: Another bot instance is polling. Kill other instances or wait for them to stop. Bot will continue retrying but may not receive updates.
2026-01-22 10:30:24,812 ERROR tg_bot.bot_core Bot error: Conflict: Conflict: terminated by other getUpdates request; make sure that only one bot instance is running
2026-01-22 10:30:24,813 ERROR tg_bot.bot_core Traceback: "C:\Users\lucid\AppData\Local\Programs\Python\Python312\Lib\site-packages\telegram\request\_baserequest.py", line 198, in post
    result = await self._request_wrapper(
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "C:\Users\lucid\AppData\Local\Programs\Python\Python312\Lib\site-packages\telegram\request\_baserequest.py", line 375, in _request_wrapper
    raise exception
telegram.error.Conflict: Conflict: terminated by other getUpdates request; make sure that only one bot instance is running

2026-01-22 10:30:24,815 CRITICAL tg_bot.bot_core CONFLICT ERROR: Another bot instance is polling. Kill other instances or wait for them to stop. Bot will continue retrying but may not receive updates.
2026-01-22 10:30:31,075 ERROR tg_bot.bot_core Bot error: Conflict: Conflict: terminated by other getUpdates request; make sure that only one bot instance is running
2026-01-22 10:30:31,076 ERROR tg_bot.bot_core Traceback: "C:\Users\lucid\AppData\Local\Programs\Python\Python312\Lib\site-packages\telegram\request\_baserequest.py", line 198, in post
    result = await self._request_wrapper(
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "C:\Users\lucid\AppData\Local\Programs\Python\Python312\Lib\site-packages\telegram\request\_baserequest.py", line 375, in _request_wrapper
    raise exception
telegram.error.Conflict: Conflict: terminated by other getUpdates request; make sure that only one bot instance is running

2026-01-22 10:30:31,077 CRITICAL tg_bot.bot_core CONFLICT ERROR: Another bot instance is polling. Kill other instances or wait for them to stop. Bot will continue retrying but may not receive updates.
2026-01-22 10:30:38,850 ERROR tg_bot.bot_core Bot error: Conflict: Conflict: terminated by other getUpdates request; make sure that only one bot instance is running
2026-01-22 10:30:38,850 ERROR tg_bot.bot_core Traceback: "C:\Users\lucid\AppData\Local\Programs\Python\Python312\Lib\site-packages\telegram\request\_baserequest.py", line 198, in post
    result = await self._request_wrapper(
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "C:\Users\lucid\AppData\Local\Programs\Python\Python312\Lib\site-packages\telegram\request\_baserequest.py", line 375, in _request_wrapper
    raise exception
telegram.error.Conflict: Conflict: terminated by other getUpdates request; make sure that only one bot instance is running

2026-01-22 10:30:38,853 CRITICAL tg_bot.bot_core CONFLICT ERROR: Another bot instance is polling. Kill other instances or wait for them to stop. Bot will continue retrying but may not receive updates.
2026-01-22 10:30:45,892 ERROR tg_bot.bot_core Bot error: Conflict: Conflict: terminated by other getUpdates request; make sure that only one bot instance is running
2026-01-22 10:30:45,892 ERROR tg_bot.bot_core Traceback: "C:\Users\lucid\AppData\Local\Programs\Python\Python312\Lib\site-packages\telegram\request\_baserequest.py", line 198, in post
    result = await self._request_wrapper(
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "C:\Users\lucid\AppData\Local\Programs\Python\Python312\Lib\site-packages\telegram\request\_baserequest.py", line 375, in _request_wrapper
    raise exception
telegram.error.Conflict: Conflict: terminated by other getUpdates request; make sure that only one bot instance is running

2026-01-22 10:30:45,894 CRITICAL tg_bot.bot_core CONFLICT ERROR: Another bot instance is polling. Kill other instances or wait for them to stop. Bot will continue retrying but may not receive updates.
2026-01-22 10:30:57,068 ERROR tg_bot.bot_core Bot error: Conflict: Conflict: terminated by other getUpdates request; make sure that only one bot instance is running
2026-01-22 10:30:57,068 ERROR tg_bot.bot_core Traceback: "C:\Users\lucid\AppData\Local\Programs\Python\Python312\Lib\site-packages\telegram\request\_baserequest.py", line 198, in post
    result = await self._request_wrapper(
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "C:\Users\lucid\AppData\Local\Programs\Python\Python312\Lib\site-packages\telegram\request\_baserequest.py", line 375, in _request_wrapper
    raise exception
telegram.error.Conflict: Conflict: terminated by other getUpdates request; make sure that only one bot instance is running

2026-01-22 10:30:57,071 CRITICAL tg_bot.bot_core CONFLICT ERROR: Another bot instance is polling. Kill other instances or wait for them to stop. Bot will continue retrying but may not receive updates.
2026-01-22 10:31:13,016 ERROR tg_bot.bot_core Bot error: Conflict: Conflict: terminated by other getUpdates request; make sure that only one bot instance is running
2026-01-22 10:31:13,017 ERROR tg_bot.bot_core Traceback: "C:\Users\lucid\AppData\Local\Programs\Python\Python312\Lib\site-packages\telegram\request\_baserequest.py", line 198, in post
    result = await self._request_wrapper(
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "C:\Users\lucid\AppData\Local\Programs\Python\Python312\Lib\site-packages\telegram\request\_baserequest.py", line 375, in _request_wrapper
    raise exception
telegram.error.Conflict: Conflict: terminated by other getUpdates request; make sure that only one bot instance is running

2026-01-22 10:31:13,019 CRITICAL tg_bot.bot_core CONFLICT ERROR: Another bot instance is polling. Kill other instances or wait for them to stop. Bot will continue retrying but may not receive updates.
2026-01-22 10:31:29,006 ERROR tg_bot.bot_core Bot error: Conflict: Conflict: terminated by other getUpdates request; make sure that only one bot instance is running
2026-01-22 10:31:29,008 ERROR tg_bot.bot_core Traceback: "C:\Users\lucid\AppData\Local\Programs\Python\Python312\Lib\site-packages\telegram\request\_baserequest.py", line 198, in post
    result = await self._request_wrapper(
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "C:\Users\lucid\AppData\Local\Programs\Python\Python312\Lib\site-packages\telegram\request\_baserequest.py", line 375, in _request_wrapper
    raise exception
telegram.error.Conflict: Conflict: terminated by other getUpdates request; make sure that only one bot instance is running

2026-01-22 10:31:29,010 CRITICAL tg_bot.bot_core CONFLICT ERROR: Another bot instance is polling. Kill other instances or wait for them to stop. Bot will continue retrying but may not receive updates.
2026-01-22 10:31:51,502 ERROR tg_bot.bot_core Bot error: Conflict: Conflict: terminated by other getUpdates request; make sure that only one bot instance is running
2026-01-22 10:31:51,503 ERROR tg_bot.bot_core Traceback: "C:\Users\lucid\AppData\Local\Programs\Python\Python312\Lib\site-packages\telegram\request\_baserequest.py", line 198, in post
    result = await self._request_wrapper(
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "C:\Users\lucid\AppData\Local\Programs\Python\Python312\Lib\site-packages\telegram\request\_baserequest.py", line 375, in _request_wrapper
    raise exception
telegram.error.Conflict: Conflict: terminated by other getUpdates request; make sure that only one bot instance is running

2026-01-22 10:31:51,507 CRITICAL tg_bot.bot_core CONFLICT ERROR: Another bot instance is polling. Kill other instances or wait for them to stop. Bot will continue retrying but may not receive updates.
2026-01-22 10:32:21,802 ERROR tg_bot.bot_core Bot error: Conflict: Conflict: terminated by other getUpdates request; make sure that only one bot instance is running
2026-01-22 10:32:21,803 ERROR tg_bot.bot_core Traceback: "C:\Users\lucid\AppData\Local\Programs\Python\Python312\Lib\site-packages\telegram\request\_baserequest.py", line 198, in post
    result = await self._request_wrapper(
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "C:\Users\lucid\AppData\Local\Programs\Python\Python312\Lib\site-packages\telegram\request\_baserequest.py", line 375, in _request_wrapper
    raise exception
telegram.error.Conflict: Conflict: terminated by other getUpdates request; make sure that only one bot instance is running

2026-01-22 10:32:21,804 CRITICAL tg_bot.bot_core CONFLICT ERROR: Another bot instance is polling. Kill other instances or wait for them to stop. Bot will continue retrying but may not receive updates.
2026-01-22 10:32:56,403 ERROR tg_bot.bot_core Bot error: Conflict: Conflict: terminated by other getUpdates request; make sure that only one bot instance is running
2026-01-22 10:32:56,404 ERROR tg_bot.bot_core Traceback: "C:\Users\lucid\AppData\Local\Programs\Python\Python312\Lib\site-packages\telegram\request\_baserequest.py", line 198, in post
    result = await self._request_wrapper(
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "C:\Users\lucid\AppData\Local\Programs\Python\Python312\Lib\site-packages\telegram\request\_baserequest.py", line 375, in _request_wrapper
    raise exception
telegram.error.Conflict: Conflict: terminated by other getUpdates request; make sure that only one bot instance is running

2026-01-22 10:32:56,406 CRITICAL tg_bot.bot_core CONFLICT ERROR: Another bot instance is polling. Kill other instances or wait for them to stop. Bot will continue retrying but may not receive updates.
2026-01-22 10:33:31,012 ERROR tg_bot.bot_core Bot error: Conflict: Conflict: terminated by other getUpdates request; make sure that only one bot instance is running
2026-01-22 10:33:31,013 ERROR tg_bot.bot_core Traceback: "C:\Users\lucid\AppData\Local\Programs\Python\Python312\Lib\site-packages\telegram\request\_baserequest.py", line 198, in post
    result = await self._request_wrapper(
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "C:\Users\lucid\AppData\Local\Programs\Python\Python312\Lib\site-packages\telegram\request\_baserequest.py", line 375, in _request_wrapper
    raise exception
telegram.error.Conflict: Conflict: terminated by other getUpdates request; make sure that only one bot instance is running

2026-01-22 10:33:31,016 CRITICAL tg_bot.bot_core CONFLICT ERROR: Another bot instance is polling. Kill other instances or wait for them to stop. Bot will continue retrying but may not receive updates.
2026-01-22 10:34:05,603 ERROR tg_bot.bot_core Bot error: Conflict: Conflict: terminated by other getUpdates request; make sure that only one bot instance is running
2026-01-22 10:34:05,604 ERROR tg_bot.bot_core Traceback: "C:\Users\lucid\AppData\Local\Programs\Python\Python312\Lib\site-packages\telegram\request\_baserequest.py", line 198, in post
    result = await self._request_wrapper(
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "C:\Users\lucid\AppData\Local\Programs\Python\Python312\Lib\site-packages\telegram\request\_baserequest.py", line 375, in _request_wrapper
    raise exception
telegram.error.Conflict: Conflict: terminated by other getUpdates request; make sure that only one bot instance is running

2026-01-22 10:34:05,605 CRITICAL tg_bot.bot_core CONFLICT ERROR: Another bot instance is polling. Kill other instances or wait for them to stop. Bot will continue retrying but may not receive updates.
2026-01-22 10:34:40,177 ERROR tg_bot.bot_core Bot error: Conflict: Conflict: terminated by other getUpdates request; make sure that only one bot instance is running
2026-01-22 10:34:40,178 ERROR tg_bot.bot_core Traceback: "C:\Users\lucid\AppData\Local\Programs\Python\Python312\Lib\site-packages\telegram\request\_baserequest.py", line 198, in post
    result = await self._request_wrapper(
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "C:\Users\lucid\AppData\Local\Programs\Python\Python312\Lib\site-packages\telegram\request\_baserequest.py", line 375, in _request_wrapper
    raise exception
telegram.error.Conflict: Conflict: terminated by other getUpdates request; make sure that only one bot instance is running

2026-01-22 10:34:40,181 CRITICAL tg_bot.bot_core CONFLICT ERROR: Another bot instance is polling. Kill other instances or wait for them to stop. Bot will continue retrying but may not receive updates.
2026-01-22 10:35:14,717 ERROR tg_bot.bot_core Bot error: Conflict: Conflict: terminated by other getUpdates request; make sure that only one bot instance is running
2026-01-22 10:35:14,718 ERROR tg_bot.bot_core Traceback: "C:\Users\lucid\AppData\Local\Programs\Python\Python312\Lib\site-packages\telegram\request\_baserequest.py", line 198, in post
    result = await self._request_wrapper(
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "C:\Users\lucid\AppData\Local\Programs\Python\Python312\Lib\site-packages\telegram\request\_baserequest.py", line 375, in _request_wrapper
    raise exception
telegram.error.Conflict: Conflict: terminated by other getUpdates request; make sure that only one bot instance is running

2026-01-22 10:35:14,721 CRITICAL tg_bot.bot_core CONFLICT ERROR: Another bot instance is polling. Kill other instances or wait for them to stop. Bot will continue retrying but may not receive updates.
2026-01-22 10:35:49,287 ERROR tg_bot.bot_core Bot error: Conflict: Conflict: terminated by other getUpdates request; make sure that only one bot instance is running
2026-01-22 10:35:49,289 ERROR tg_bot.bot_core Traceback: "C:\Users\lucid\AppData\Local\Programs\Python\Python312\Lib\site-packages\telegram\request\_baserequest.py", line 198, in post
    result = await self._request_wrapper(
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "C:\Users\lucid\AppData\Local\Programs\Python\Python312\Lib\site-packages\telegram\request\_baserequest.py", line 375, in _request_wrapper
    raise exception
telegram.error.Conflict: Conflict: terminated by other getUpdates request; make sure that only one bot instance is running

2026-01-22 10:35:49,292 CRITICAL tg_bot.bot_core CONFLICT ERROR: Another bot instance is polling. Kill other instances or wait for them to stop. Bot will continue retrying but may not receive updates.
```

### logs/bots.log (tail 200 lines)
Path: `logs\bots.log`
```text
[TG Bot]   File "C:\Users\lucid\OneDrive\Desktop\Projects\Jarvis\tg_bot\bot.py", line 3225, in _handle_expand_section
[Buy Tracker] 2026-01-14 11:48:24,032 - bots.buy_tracker.monitor - INFO - Poll #11115: 285 txns tracked, min=$1.0
[TG Bot]     if not data_file.exists():
[Buy Tracker] 2026-01-14 11:48:57,994 - bots.buy_tracker.monitor - INFO - Poll #11130: 285 txns tracked, min=$1.0
[TG Bot]   File "C:\Users\lucid\AppData\Local\Programs\Python\Python312\Lib\site-packages\telegram\_message.py", line 2060, in reply_text
[Buy Tracker] 2026-01-14 11:49:31,484 - bots.buy_tracker.monitor - INFO - Poll #11145: 285 txns tracked, min=$1.0
[TG Bot]     return await self.get_bot().send_message(
[Buy Tracker] 2026-01-14 11:50:04,523 - bots.buy_tracker.monitor - INFO - Poll #11160: 285 txns tracked, min=$1.0
[TG Bot]            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
[Buy Tracker] 2026-01-14 11:50:38,348 - bots.buy_tracker.monitor - INFO - Poll #11175: 285 txns tracked, min=$1.0
[TG Bot]   File "C:\Users\lucid\AppData\Local\Programs\Python\Python312\Lib\site-packages\telegram\ext\_extbot.py", line 3107, in send_message
[Buy Tracker] 2026-01-14 11:51:11,534 - bots.buy_tracker.monitor - INFO - Poll #11190: 285 txns tracked, min=$1.0
[TG Bot]     return await super().send_message(
[Buy Tracker] 2026-01-14 11:51:45,118 - bots.buy_tracker.monitor - INFO - Poll #11205: 285 txns tracked, min=$1.0
[TG Bot]            ^^^^^^^^^^^^^^^^^^^^^^^^^^^
[Buy Tracker] 2026-01-14 11:52:17,478 - bots.buy_tracker.monitor - INFO - Poll #11220: 285 txns tracked, min=$1.0
[TG Bot]   File "C:\Users\lucid\AppData\Local\Programs\Python\Python312\Lib\site-packages\telegram\_bot.py", line 1118, in send_message
[Buy Tracker] 2026-01-14 11:52:36,457 - bots.buy_tracker.monitor - INFO - Found 1 new transaction(s) to process
[RUNNER] TG Bot died (exit=4294967295). Restart #1
[RUNNER] Starting TG Bot...
[TG Bot]     return await self._send_message(
[Buy Tracker] 2026-01-14 11:52:51,987 - bots.buy_tracker.monitor - INFO - Poll #11235: 286 txns tracked, min=$1.0
[TG Bot] 2026-01-14 11:52:41,520 - apscheduler.scheduler - INFO - Adding job tentatively -- it will be properly scheduled when the scheduler starts
[Buy Tracker] 2026-01-14 11:53:24,642 - bots.buy_tracker.monitor - INFO - Poll #11250: 286 txns tracked, min=$1.0
[TG Bot] 2026-01-14 11:52:41,520 - apscheduler.scheduler - INFO - Adding job tentatively -- it will be properly scheduled when the scheduler starts
[Buy Tracker] 2026-01-14 11:53:57,837 - bots.buy_tracker.monitor - INFO - Poll #11265: 286 txns tracked, min=$1.0
[TG Bot] 2026-01-14 11:52:41,520 - apscheduler.scheduler - INFO - Adding job tentatively -- it will be properly scheduled when the scheduler starts
[Buy Tracker] 2026-01-14 11:54:30,599 - bots.buy_tracker.monitor - INFO - Poll #11280: 286 txns tracked, min=$1.0
[TG Bot] 2026-01-14 11:52:42,115 - core.health_monitor - INFO - HealthMonitor initialized
[Buy Tracker] 2026-01-14 11:55:03,457 - bots.buy_tracker.monitor - INFO - Poll #11295: 286 txns tracked, min=$1.0
[TG Bot] 2026-01-14 11:52:42,115 - core.health_monitor - INFO - Health monitoring started
[Buy Tracker] 2026-01-14 11:55:36,942 - bots.buy_tracker.monitor - INFO - Poll #11310: 286 txns tracked, min=$1.0
[TG Bot] 2026-01-14 11:52:42,270 - apscheduler.scheduler - INFO - Added job "digest_8" to job store "default"
[Buy Tracker] 2026-01-14 11:58:46,482 - bots.buy_tracker.monitor - INFO - Poll #11325: 286 txns tracked, min=$1.0
[TG Bot] 2026-01-14 11:52:42,270 - apscheduler.scheduler - INFO - Added job "digest_14" to job store "default"
[Buy Tracker] 2026-01-14 11:58:57,864 - bots.buy_tracker.monitor - ERROR - Failed to get signatures: [Errno 1] [SSL: SSLV3_ALERT_BAD_RECORD_MAC] sslv3 alert bad record mac (_ssl.c:2580)
[TG Bot] 2026-01-14 11:52:42,270 - apscheduler.scheduler - INFO - Added job "digest_20" to job store "default"
[Buy Tracker] 2026-01-14 11:59:08,613 - bots.buy_tracker.monitor - INFO - Buy below threshold: $0.30 < $1.0 by avg1...ZuME
[TG Bot] 2026-01-14 11:52:42,270 - apscheduler.scheduler - INFO - Scheduler started
[Buy Tracker] 2026-01-14 11:59:09,522 - bots.buy_tracker.monitor - INFO - Buy detected: $641.31 by Et6d...Mxjs (4.3847 SOL)
[TG Bot] 
[Buy Tracker] 2026-01-14 11:59:09,523 - __main__ - INFO - Processing buy: $641.31 from Et6d...Mxjs
[TG Bot] ==================================================
[Buy Tracker] 2026-01-14 11:59:16,285 - httpx - INFO - HTTP Request: POST https://api.telegram.org/bot***TELEGRAM_TOKEN_REDACTED***/sendVideo "HTTP/1.1 200 OK"
[TG Bot] JARVIS TELEGRAM BOT
[Buy Tracker] 2026-01-14 11:59:16,293 - __main__ - INFO - Buy notification sent: $641.31
[TG Bot] ==================================================
[Buy Tracker] 2026-01-14 11:59:16,293 - bots.buy_tracker.monitor - INFO - Found 5 new transaction(s) to process
[TG Bot] Admin IDs configured: 1
[Buy Tracker] 2026-01-14 11:59:30,002 - bots.buy_tracker.monitor - INFO - Poll #11340: 291 txns tracked, min=$1.0
[TG Bot] Grok API (XAI_API_KEY): Configured
[Buy Tracker] 2026-01-14 12:00:03,791 - bots.buy_tracker.monitor - INFO - Poll #11355: 291 txns tracked, min=$1.0
[TG Bot] Claude API: Configured
[Buy Tracker] 2026-01-14 12:00:37,276 - bots.buy_tracker.monitor - INFO - Poll #11370: 291 txns tracked, min=$1.0
[TG Bot] Birdeye API: Configured
[Buy Tracker] 2026-01-14 12:01:10,474 - bots.buy_tracker.monitor - INFO - Poll #11385: 291 txns tracked, min=$1.0
[TG Bot] Daily cost limit: $1.00
[Buy Tracker] 2026-01-14 12:01:44,208 - bots.buy_tracker.monitor - INFO - Poll #11400: 291 txns tracked, min=$1.0
[RUNNER] TG Bot died (exit=4294967295). Restart #2
[RUNNER] Starting TG Bot...
[TG Bot] Sentiment interval: 3600s (1 hour)
[Buy Tracker] 2026-01-14 12:02:17,228 - bots.buy_tracker.monitor - INFO - Poll #11415: 291 txns tracked, min=$1.0
[TG Bot] 2026-01-14 12:01:49,130 - apscheduler.scheduler - INFO - Adding job tentatively -- it will be properly scheduled when the scheduler starts
[Buy Tracker] 2026-01-14 12:02:38,417 - bots.buy_tracker.monitor - INFO - Found 1 new transaction(s) to process
[TG Bot] 2026-01-14 12:01:49,131 - apscheduler.scheduler - INFO - Adding job tentatively -- it will be properly scheduled when the scheduler starts
[Buy Tracker] 2026-01-14 12:02:51,485 - bots.buy_tracker.monitor - INFO - Poll #11430: 292 txns tracked, min=$1.0
[TG Bot] 2026-01-14 12:01:49,132 - apscheduler.scheduler - INFO - Adding job tentatively -- it will be properly scheduled when the scheduler starts
[Buy Tracker] 2026-01-14 12:03:24,400 - bots.buy_tracker.monitor - INFO - Poll #11445: 292 txns tracked, min=$1.0
[TG Bot] 2026-01-14 12:01:49,680 - core.health_monitor - INFO - HealthMonitor initialized
[Buy Tracker] 2026-01-14 12:03:57,467 - bots.buy_tracker.monitor - INFO - Poll #11460: 292 txns tracked, min=$1.0
[TG Bot] 2026-01-14 12:01:49,680 - core.health_monitor - INFO - Health monitoring started
[Buy Tracker] 2026-01-14 12:04:30,653 - bots.buy_tracker.monitor - INFO - Poll #11475: 292 txns tracked, min=$1.0
[TG Bot] 2026-01-14 12:01:49,882 - apscheduler.scheduler - INFO - Added job "digest_8" to job store "default"
[Buy Tracker] 2026-01-14 12:05:03,829 - bots.buy_tracker.monitor - INFO - Poll #11490: 292 txns tracked, min=$1.0
[TG Bot] 2026-01-14 12:01:49,882 - apscheduler.scheduler - INFO - Added job "digest_14" to job store "default"
[Buy Tracker] 2026-01-14 12:05:37,614 - bots.buy_tracker.monitor - INFO - Poll #11505: 292 txns tracked, min=$1.0
[TG Bot] 2026-01-14 12:01:49,882 - apscheduler.scheduler - INFO - Added job "digest_20" to job store "default"
[Buy Tracker] 2026-01-14 12:06:01,681 - bots.buy_tracker.monitor - INFO - Buy detected: $292.46 by 3bep...crRv (2.0021 SOL)
[TG Bot] 2026-01-14 12:01:49,882 - apscheduler.scheduler - INFO - Scheduler started
[Buy Tracker] 2026-01-14 12:06:01,681 - __main__ - INFO - Processing buy: $292.46 from 3bep...crRv
[TG Bot] 
[Buy Tracker] 2026-01-14 12:06:21,670 - httpx - INFO - HTTP Request: POST https://api.telegram.org/bot***TELEGRAM_TOKEN_REDACTED***/sendVideo "HTTP/1.1 200 OK"
[TG Bot] ==================================================
[Buy Tracker] 2026-01-14 12:06:21,674 - __main__ - INFO - Buy notification sent: $292.46
[TG Bot] JARVIS TELEGRAM BOT
[Buy Tracker] 2026-01-14 12:06:21,674 - bots.buy_tracker.monitor - INFO - Found 3 new transaction(s) to process
[TG Bot] ==================================================
[Buy Tracker] 2026-01-14 12:06:32,722 - bots.buy_tracker.monitor - INFO - Poll #11520: 295 txns tracked, min=$1.0
[TG Bot] Admin IDs configured: 1
[Buy Tracker] 2026-01-14 12:07:06,065 - bots.buy_tracker.monitor - INFO - Poll #11535: 295 txns tracked, min=$1.0
[TG Bot] Grok API (XAI_API_KEY): Configured
[Buy Tracker] 2026-01-14 12:07:39,571 - bots.buy_tracker.monitor - INFO - Poll #11550: 295 txns tracked, min=$1.0
[TG Bot] Claude API: Configured
[Buy Tracker] 2026-01-14 12:07:49,513 - bots.buy_tracker.monitor - INFO - Found 1 new transaction(s) to process
[TG Bot] Birdeye API: Configured
[Buy Tracker] 2026-01-14 12:08:13,783 - bots.buy_tracker.monitor - INFO - Poll #11565: 296 txns tracked, min=$1.0
[TG Bot] Daily cost limit: $1.00
[Buy Tracker] 2026-01-14 12:08:47,062 - bots.buy_tracker.monitor - INFO - Poll #11580: 296 txns tracked, min=$1.0
[TG Bot] Sentiment interval: 3600s (1 hour)
[Buy Tracker] 2026-01-14 12:09:20,126 - bots.buy_tracker.monitor - INFO - Poll #11595: 296 txns tracked, min=$1.0
[TG Bot] Digest hours (UTC): [8, 14, 20]
[Buy Tracker] 2026-01-14 12:12:13,109 - bots.buy_tracker.monitor - INFO - Poll #11610: 296 txns tracked, min=$1.0
[TG Bot] Data sources: dexscreener, birdeye, dextools, gmgn, grok, signal_aggregator, news_detector
[Buy Tracker] 2026-01-14 12:12:31,550 - bots.buy_tracker.monitor - INFO - Found 1 new transaction(s) to process
[TG Bot] Anti-scam protection: ENABLED
[Buy Tracker] 2026-01-14 12:12:47,215 - bots.buy_tracker.monitor - INFO - Poll #11625: 297 txns tracked, min=$1.0
[TG Bot] Scheduled digests: [8, 14, 20] UTC
[Buy Tracker] 2026-01-14 12:13:20,162 - bots.buy_tracker.monitor - INFO - Poll #11640: 297 txns tracked, min=$1.0
[RUNNER] TG Bot died (exit=15). Restart #3
[RUNNER] Starting TG Bot...
[TG Bot] ==================================================
[Buy Tracker] 2026-01-14 12:13:53,121 - bots.buy_tracker.monitor - INFO - Poll #11655: 297 txns tracked, min=$1.0
[TG Bot] 2026-01-14 12:13:25,678 - apscheduler.scheduler - INFO - Adding job tentatively -- it will be properly scheduled when the scheduler starts
[Buy Tracker] 2026-01-14 12:14:26,506 - bots.buy_tracker.monitor - INFO - Poll #11670: 297 txns tracked, min=$1.0
[TG Bot] 2026-01-14 12:13:25,678 - apscheduler.scheduler - INFO - Adding job tentatively -- it will be properly scheduled when the scheduler starts
[Buy Tracker] 2026-01-14 12:14:59,782 - bots.buy_tracker.monitor - INFO - Poll #11685: 297 txns tracked, min=$1.0
[TG Bot] 2026-01-14 12:13:25,678 - apscheduler.scheduler - INFO - Adding job tentatively -- it will be properly scheduled when the scheduler starts
[Buy Tracker] 2026-01-14 12:15:33,249 - bots.buy_tracker.monitor - INFO - Poll #11700: 297 txns tracked, min=$1.0
[TG Bot] 2026-01-14 12:13:26,251 - core.health_monitor - INFO - HealthMonitor initialized
[Buy Tracker] 2026-01-14 12:16:06,139 - bots.buy_tracker.monitor - INFO - Poll #11715: 297 txns tracked, min=$1.0
[TG Bot] 2026-01-14 12:13:26,251 - core.health_monitor - INFO - Health monitoring started
[Buy Tracker] 2026-01-14 12:16:39,432 - bots.buy_tracker.monitor - INFO - Poll #11730: 297 txns tracked, min=$1.0
[TG Bot] 2026-01-14 12:13:26,408 - apscheduler.scheduler - INFO - Added job "digest_8" to job store "default"
[Buy Tracker] 2026-01-14 12:17:12,904 - bots.buy_tracker.monitor - INFO - Poll #11745: 297 txns tracked, min=$1.0
[TG Bot] 2026-01-14 12:13:26,408 - apscheduler.scheduler - INFO - Added job "digest_14" to job store "default"
[Buy Tracker] 2026-01-14 12:17:45,716 - bots.buy_tracker.monitor - INFO - Poll #11760: 297 txns tracked, min=$1.0
[TG Bot] 2026-01-14 12:13:26,409 - apscheduler.scheduler - INFO - Added job "digest_20" to job store "default"
[Buy Tracker] 2026-01-14 12:18:19,380 - bots.buy_tracker.monitor - INFO - Poll #11775: 297 txns tracked, min=$1.0
[TG Bot] 2026-01-14 12:13:26,409 - apscheduler.scheduler - INFO - Scheduler started
[Buy Tracker] 2026-01-14 12:18:52,388 - bots.buy_tracker.monitor - INFO - Poll #11790: 297 txns tracked, min=$1.0
[TG Bot] 
[Buy Tracker] 2026-01-14 12:19:25,510 - bots.buy_tracker.monitor - INFO - Poll #11805: 297 txns tracked, min=$1.0
[TG Bot] ==================================================
[Buy Tracker] 2026-01-14 12:19:58,686 - bots.buy_tracker.monitor - INFO - Poll #11820: 297 txns tracked, min=$1.0
[TG Bot] JARVIS TELEGRAM BOT
[Buy Tracker] 2026-01-14 12:20:31,865 - bots.buy_tracker.monitor - INFO - Poll #11835: 297 txns tracked, min=$1.0
[TG Bot] ==================================================
[Buy Tracker] 2026-01-14 12:21:05,251 - bots.buy_tracker.monitor - INFO - Poll #11850: 297 txns tracked, min=$1.0
[TG Bot] Admin IDs configured: 1
[Buy Tracker] 2026-01-14 12:21:38,526 - bots.buy_tracker.monitor - INFO - Poll #11865: 297 txns tracked, min=$1.0
[TG Bot] Grok API (XAI_API_KEY): Configured
[Buy Tracker] 2026-01-14 12:22:11,926 - bots.buy_tracker.monitor - INFO - Poll #11880: 297 txns tracked, min=$1.0
[TG Bot] Claude API: Configured
[Buy Tracker] 2026-01-14 12:22:44,988 - bots.buy_tracker.monitor - INFO - Poll #11895: 297 txns tracked, min=$1.0
[TG Bot] Birdeye API: Configured
[Buy Tracker] 2026-01-14 12:23:19,550 - bots.buy_tracker.monitor - INFO - Poll #11910: 297 txns tracked, min=$1.0
[TG Bot] Daily cost limit: $1.00
[Buy Tracker] 2026-01-14 12:24:02,609 - bots.buy_tracker.monitor - INFO - Poll #11925: 297 txns tracked, min=$1.0
[TG Bot] Sentiment interval: 3600s (1 hour)
[Buy Tracker] 2026-01-14 12:25:07,128 - bots.buy_tracker.monitor - INFO - Buy detected: $45.84 by 2bZQ...9XNk (0.3130 SOL)
[TG Bot] Digest hours (UTC): [8, 14, 20]
[Buy Tracker] 2026-01-14 12:25:07,132 - __main__ - INFO - Processing buy: $45.84 from 2bZQ...9XNk
[TG Bot] Data sources: dexscreener, birdeye, dextools, gmgn, grok, signal_aggregator, news_detector
[Buy Tracker] 2026-01-14 12:25:30,655 - __main__ - ERROR - Failed to send buy notification: Timed out
[TG Bot] Anti-scam protection: ENABLED
[Buy Tracker] 2026-01-14 12:25:30,656 - bots.buy_tracker.monitor - INFO - Found 3 new transaction(s) to process
[TG Bot] Scheduled digests: [8, 14, 20] UTC
[Buy Tracker] 2026-01-14 12:25:52,393 - bots.buy_tracker.monitor - INFO - Poll #11940: 300 txns tracked, min=$1.0
[TG Bot] ==================================================
[Buy Tracker] 2026-01-14 12:26:25,860 - bots.buy_tracker.monitor - INFO - Poll #11955: 300 txns tracked, min=$1.0
[TG Bot] Bot started! Press Ctrl+C to stop.
[Buy Tracker] 2026-01-14 12:26:59,250 - bots.buy_tracker.monitor - INFO - Poll #11970: 300 txns tracked, min=$1.0
[TG Bot] ==================================================
[Buy Tracker] 2026-01-14 12:27:04,565 - bots.buy_tracker.monitor - INFO - Found 1 new transaction(s) to process
[TG Bot] 
[Buy Tracker] 2026-01-14 12:27:32,981 - bots.buy_tracker.monitor - INFO - Poll #11985: 301 txns tracked, min=$1.0
[TG Bot] Health monitoring: STARTED
[Buy Tracker] 2026-01-14 12:27:48,987 - bots.buy_tracker.monitor - INFO - Found 1 new transaction(s) to process
[TG Bot] [MSG] user_id=899543924 text=Could you do a deep dive into it? Obvious, the contracts are
[Buy Tracker] 2026-01-14 12:28:06,415 - bots.buy_tracker.monitor - INFO - Poll #12000: 302 txns tracked, min=$1.0
[TG Bot] 2026-01-14 12:13:27,015 - __main__ - INFO - Message from 899543924: Could you do a deep dive into it? Obvious, the contracts are
[Buy Tracker] 2026-01-14 12:28:39,498 - bots.buy_tracker.monitor - INFO - Poll #12015: 302 txns tracked, min=$1.0
[TG Bot] 2026-01-14 12:13:27,048 - __main__ - INFO - Generating reply for admin=False user=899543924
[Buy Tracker] 2026-01-14 12:29:12,727 - bots.buy_tracker.monitor - INFO - Poll #12030: 302 txns tracked, min=$1.0
[TG Bot] 2026-01-14 12:13:27,049 - tg_bot.services.chat_responder - INFO - Blocked command from non-admin 899543924: Could you do a deep dive into it? Obvious, the con
[Buy Tracker] 2026-01-14 12:29:46,115 - bots.buy_tracker.monitor - INFO - Poll #12045: 302 txns tracked, min=$1.0
[TG Bot] 2026-01-14 12:13:27,049 - __main__ - INFO - Reply generated: only matt can give me commands. happy to chat thou
[Buy Tracker] 2026-01-14 12:30:19,337 - bots.buy_tracker.monitor - INFO - Poll #12060: 302 txns tracked, min=$1.0
[TG Bot] [MSG] user_id=5320684004 text=Smart
[Buy Tracker] 2026-01-14 12:30:52,610 - bots.buy_tracker.monitor - INFO - Poll #12075: 302 txns tracked, min=$1.0
[TG Bot] 2026-01-14 12:13:27,394 - __main__ - INFO - Message from 5320684004: Smart
[Buy Tracker] 2026-01-14 12:31:25,170 - bots.buy_tracker.monitor - INFO - Poll #12090: 302 txns tracked, min=$1.0
[TG Bot] [MSG] user_id=756559674 text=Hello
[Buy Tracker] 2026-01-14 12:34:01,056 - bots.buy_tracker.monitor - INFO - Poll #12105: 302 txns tracked, min=$1.0
[TG Bot] 2026-01-14 12:13:27,717 - __main__ - INFO - Message from 756559674: Hello
[Buy Tracker] 2026-01-14 12:34:34,198 - bots.buy_tracker.monitor - INFO - Poll #12120: 302 txns tracked, min=$1.0
[TG Bot] 2026-01-14 12:13:27,734 - __main__ - INFO - Generating reply for admin=False user=756559674
[Buy Tracker] 2026-01-14 12:35:07,579 - bots.buy_tracker.monitor - INFO - Poll #12135: 302 txns tracked, min=$1.0
[TG Bot] 2026-01-14 12:13:32,135 - __main__ - INFO - Reply generated: Hey there! How's it going?
[Buy Tracker] 2026-01-14 12:35:40,450 - bots.buy_tracker.monitor - INFO - Poll #12150: 302 txns tracked, min=$1.0
[TG Bot] 2026-01-14 12:13:32,857 - __main__ - ERROR - Bot error: BadRequest
[Buy Tracker] 2026-01-14 12:36:13,486 - bots.buy_tracker.monitor - INFO - Poll #12165: 302 txns tracked, min=$1.0
[TG Bot] 2026-01-14 12:13:33,538 - __main__ - ERROR - Bot error: BadRequest
[Buy Tracker] 2026-01-14 12:36:46,702 - bots.buy_tracker.monitor - INFO - Poll #12180: 302 txns tracked, min=$1.0
[TG Bot] 2026-01-14 12:13:34,189 - __main__ - ERROR - Bot error: BadRequest
[Buy Tracker] 2026-01-14 12:37:19,777 - bots.buy_tracker.monitor - INFO - Poll #12195: 302 txns tracked, min=$1.0
[TG Bot] 2026-01-14 12:13:34,803 - __main__ - ERROR - Bot error: BadRequest
[Buy Tracker] 2026-01-14 12:37:53,617 - bots.buy_tracker.monitor - INFO - Poll #12210: 302 txns tracked, min=$1.0
[TG Bot] [MSG] user_id=756559674 text=Perfect
[Buy Tracker] 2026-01-14 12:38:26,998 - bots.buy_tracker.monitor - INFO - Poll #12225: 302 txns tracked, min=$1.0
```

### logs/audit.jsonl (tail 200 lines)
Path: `logs\audit.jsonl`
```text
{"timestamp": 1768869028.0292804, "event_type": "security_alert", "actor_id": "12345", "action": "OPEN_POSITION_REJECTED", "resource_type": "treasury_trade", "resource_id": "SOL", "ip_address": "", "user_agent": "", "details": {"token": "SOL", "reason": "spending_limit", "limit_reason": "Daily limit reached. Used $3720.00/500.0. Remaining: $-3220.00", "amount_usd": 100.0}, "success": false, "error_message": "", "timestamp_iso": "2026-01-19T18:30:28.029280"}
{"timestamp": 1768869028.050374, "event_type": "security_alert", "actor_id": "12345", "action": "OPEN_POSITION_REJECTED", "resource_type": "treasury_trade", "resource_id": "SOL", "ip_address": "", "user_agent": "", "details": {"token": "SOL", "reason": "amount_exceeds_max", "amount_usd": 100.0, "max_trade_usd": 50.0}, "success": false, "error_message": "", "timestamp_iso": "2026-01-19T18:30:28.050374"}
{"timestamp": 1768869028.1227021, "event_type": "trade_execute", "actor_id": "12345", "action": "OPEN_POSITION", "resource_type": "treasury_trade", "resource_id": "cdb4196b", "ip_address": "", "user_agent": "", "details": {"position_id": "cdb4196b", "token": "SOL", "token_mint": "So11111111111111111111111111111111111111112", "amount_usd": 50.0, "entry_price": 100.0, "tp_price": 130.0, "sl_price": 92.0, "sentiment_grade": "A", "dry_run": true}, "success": true, "error_message": "", "timestamp_iso": "2026-01-19T18:30:28.122702"}
{"timestamp": 1768869028.1613498, "event_type": "trade_execute", "actor_id": "12345", "action": "OPEN_POSITION", "resource_type": "treasury_trade", "resource_id": "64cd67a3", "ip_address": "", "user_agent": "", "details": {"position_id": "64cd67a3", "token": "SOL", "token_mint": "So11111111111111111111111111111111111111112", "amount_usd": 100.0, "entry_price": 100.0, "tp_price": 130.0, "sl_price": 92.0, "sentiment_grade": "A", "dry_run": true}, "success": true, "error_message": "", "timestamp_iso": "2026-01-19T18:30:28.161350"}
{"timestamp": 1768875374.1486592, "event_type": "security_alert", "actor_id": "12345", "action": "OPEN_POSITION_REJECTED", "resource_type": "treasury_trade", "resource_id": "TEST", "ip_address": "", "user_agent": "", "details": {"token": "TEST", "reason": "liquidity_check_failed", "risk_tier": "MICRO"}, "success": false, "error_message": "", "timestamp_iso": "2026-01-19T20:16:14.148659"}
{"timestamp": 1768875374.2503443, "event_type": "security_alert", "actor_id": "12345", "action": "OPEN_POSITION_REJECTED", "resource_type": "treasury_trade", "resource_id": "TEST", "ip_address": "", "user_agent": "", "details": {"token": "TEST", "reason": "liquidity_check_failed", "risk_tier": "MICRO"}, "success": false, "error_message": "", "timestamp_iso": "2026-01-19T20:16:14.250344"}
{"timestamp": 1768875376.081335, "event_type": "security_alert", "actor_id": "12345", "action": "OPEN_POSITION_REJECTED", "resource_type": "treasury_trade", "resource_id": "TEST", "ip_address": "", "user_agent": "", "details": {"token": "TEST", "reason": "liquidity_check_failed", "risk_tier": "MICRO"}, "success": false, "error_message": "", "timestamp_iso": "2026-01-19T20:16:16.081335"}
{"timestamp": 1768875376.1829574, "event_type": "security_alert", "actor_id": "12345", "action": "OPEN_POSITION_REJECTED", "resource_type": "treasury_trade", "resource_id": "TEST", "ip_address": "", "user_agent": "", "details": {"token": "TEST", "reason": "liquidity_check_failed", "risk_tier": "MICRO"}, "success": false, "error_message": "", "timestamp_iso": "2026-01-19T20:16:16.182957"}
{"timestamp": 1768875376.2505941, "event_type": "security_alert", "actor_id": "12345", "action": "OPEN_POSITION_REJECTED", "resource_type": "treasury_trade", "resource_id": "TEST", "ip_address": "", "user_agent": "", "details": {"token": "TEST", "reason": "liquidity_check_failed", "risk_tier": "MICRO"}, "success": false, "error_message": "", "timestamp_iso": "2026-01-19T20:16:16.250594"}
{"timestamp": 1768875376.3838458, "event_type": "security_alert", "actor_id": "12345", "action": "OPEN_POSITION_REJECTED", "resource_type": "treasury_trade", "resource_id": "TEST", "ip_address": "", "user_agent": "", "details": {"token": "TEST", "reason": "liquidity_check_failed", "risk_tier": "MICRO"}, "success": false, "error_message": "", "timestamp_iso": "2026-01-19T20:16:16.383846"}
{"timestamp": 1768875376.4320285, "event_type": "security_alert", "actor_id": "12345", "action": "OPEN_POSITION_REJECTED", "resource_type": "treasury_trade", "resource_id": "TEST", "ip_address": "", "user_agent": "", "details": {"token": "TEST", "reason": "liquidity_check_failed", "risk_tier": "MICRO"}, "success": false, "error_message": "", "timestamp_iso": "2026-01-19T20:16:16.432029"}
{"timestamp": 1768875376.702507, "event_type": "security_alert", "actor_id": "12345", "action": "OPEN_POSITION_REJECTED", "resource_type": "treasury_trade", "resource_id": "TEST", "ip_address": "", "user_agent": "", "details": {"token": "TEST", "reason": "liquidity_check_failed", "risk_tier": "MICRO"}, "success": false, "error_message": "", "timestamp_iso": "2026-01-19T20:16:16.702507"}
{"timestamp": 1768875376.7548409, "event_type": "trade_execute", "actor_id": "12345", "action": "CLOSE_POSITION", "resource_type": "treasury_trade", "resource_id": "test123", "ip_address": "", "user_agent": "", "details": {"position_id": "test123", "token": "TEST", "token_mint": "TestMint123", "entry_price": 100.0, "exit_price": 110.0, "pnl_usd": 100.0, "pnl_pct": 10.0, "reason": "Test close", "tx_signature": "close_tx", "dry_run": false}, "success": true, "error_message": "", "timestamp_iso": "2026-01-19T20:16:16.754841"}
{"timestamp": 1768875376.9268155, "event_type": "trade_execute", "actor_id": "12345", "action": "CLOSE_POSITION", "resource_type": "treasury_trade", "resource_id": "test123", "ip_address": "", "user_agent": "", "details": {"position_id": "test123", "token": "TEST", "token_mint": "TestMint123", "entry_price": 100.0, "exit_price": 110.0, "pnl_usd": 100.0, "pnl_pct": 10.0, "reason": "Test close", "tx_signature": "close_tx", "dry_run": false}, "success": true, "error_message": "", "timestamp_iso": "2026-01-19T20:16:16.926816"}
{"timestamp": 1768875376.9713492, "event_type": "security_alert", "actor_id": "12345", "action": "OPEN_POSITION_REJECTED", "resource_type": "treasury_trade", "resource_id": "xStockToken", "ip_address": "", "user_agent": "", "details": {"token": "xStockToken", "reason": "liquidity_check_failed", "risk_tier": "MICRO"}, "success": false, "error_message": "", "timestamp_iso": "2026-01-19T20:16:16.971349"}
{"timestamp": 1768875377.0362258, "event_type": "trade_execute", "actor_id": "12345", "action": "CLOSE_POSITION", "resource_type": "treasury_trade", "resource_id": "test123", "ip_address": "", "user_agent": "", "details": {"position_id": "test123", "token": "TEST", "token_mint": "TestMint123", "entry_price": 100.0, "exit_price": 110.0, "pnl_usd": 100.0, "pnl_pct": 10.0, "reason": "Test close", "tx_signature": "close_tx", "dry_run": false}, "success": true, "error_message": "", "timestamp_iso": "2026-01-19T20:16:17.036226"}
{"timestamp": 1768875377.4143016, "event_type": "security_alert", "actor_id": "12345", "action": "OPEN_POSITION_REJECTED", "resource_type": "treasury_trade", "resource_id": "TEST", "ip_address": "", "user_agent": "", "details": {"token": "TEST", "reason": "liquidity_check_failed", "risk_tier": "MICRO"}, "success": false, "error_message": "", "timestamp_iso": "2026-01-19T20:16:17.414302"}
{"timestamp": 1768875804.5142345, "event_type": "security_alert", "actor_id": "12345", "action": "OPEN_POSITION_REJECTED", "resource_type": "treasury_trade", "resource_id": "TEST", "ip_address": "", "user_agent": "", "details": {"token": "TEST", "reason": "liquidity_check_failed", "risk_tier": "MICRO"}, "success": false, "error_message": "", "timestamp_iso": "2026-01-19T20:23:24.514235"}
{"timestamp": 1768875804.7302196, "event_type": "security_alert", "actor_id": "12345", "action": "OPEN_POSITION_REJECTED", "resource_type": "treasury_trade", "resource_id": "SOL", "ip_address": "", "user_agent": "", "details": {"token": "SOL", "reason": "non_positive_amount", "amount_usd": 0.0}, "success": false, "error_message": "", "timestamp_iso": "2026-01-19T20:23:24.730220"}
{"timestamp": 1768875805.1877704, "event_type": "security_alert", "actor_id": "12345", "action": "OPEN_POSITION_REJECTED", "resource_type": "treasury_trade", "resource_id": "SOL", "ip_address": "", "user_agent": "", "details": {"token": "SOL", "reason": "amount_exceeds_max", "amount_usd": 150.0, "max_trade_usd": 100.0}, "success": false, "error_message": "", "timestamp_iso": "2026-01-19T20:23:25.187770"}
{"timestamp": 1768875805.5876875, "event_type": "security_alert", "actor_id": "12345", "action": "OPEN_POSITION_REJECTED", "resource_type": "treasury_trade", "resource_id": "BONK", "ip_address": "", "user_agent": "", "details": {"token": "BONK", "reason": "spending_limit", "limit_reason": "Daily limit reached. Used $3870.00/500.0. Remaining: $-3370.00", "amount_usd": 50.0}, "success": false, "error_message": "", "timestamp_iso": "2026-01-19T20:23:25.587687"}
{"timestamp": 1768875809.310903, "event_type": "security_alert", "actor_id": "12345", "action": "OPEN_POSITION_REJECTED", "resource_type": "treasury_trade", "resource_id": "BONK", "ip_address": "", "user_agent": "", "details": {"token": "BONK", "reason": "spending_limit", "limit_reason": "Daily limit reached. Used $3870.00/500.0. Remaining: $-3370.00", "amount_usd": 50.0}, "success": false, "error_message": "", "timestamp_iso": "2026-01-19T20:23:29.310903"}
{"timestamp": 1768875809.670831, "event_type": "security_alert", "actor_id": "12345", "action": "OPEN_POSITION_REJECTED", "resource_type": "treasury_trade", "resource_id": "BONK", "ip_address": "", "user_agent": "", "details": {"token": "BONK", "reason": "spending_limit", "limit_reason": "Daily limit reached. Used $3870.00/500.0. Remaining: $-3370.00", "amount_usd": 50.0}, "success": false, "error_message": "", "timestamp_iso": "2026-01-19T20:23:29.670831"}
{"timestamp": 1768875810.430911, "event_type": "security_alert", "actor_id": "12345", "action": "OPEN_POSITION_REJECTED", "resource_type": "treasury_trade", "resource_id": "BONK", "ip_address": "", "user_agent": "", "details": {"token": "BONK", "reason": "spending_limit", "limit_reason": "Daily limit reached. Used $3870.00/500.0. Remaining: $-3370.00", "amount_usd": 50.0}, "success": false, "error_message": "", "timestamp_iso": "2026-01-19T20:23:30.430911"}
{"timestamp": 1768875810.8378386, "event_type": "security_alert", "actor_id": "12345", "action": "OPEN_POSITION_REJECTED", "resource_type": "treasury_trade", "resource_id": "BONK", "ip_address": "", "user_agent": "", "details": {"token": "BONK", "reason": "spending_limit", "limit_reason": "Daily limit reached. Used $3870.00/500.0. Remaining: $-3370.00", "amount_usd": 50.0}, "success": false, "error_message": "", "timestamp_iso": "2026-01-19T20:23:30.837839"}
{"timestamp": 1768875811.0699885, "event_type": "security_alert", "actor_id": "12345", "action": "OPEN_POSITION_REJECTED", "resource_type": "treasury_trade", "resource_id": "BONK", "ip_address": "", "user_agent": "", "details": {"token": "BONK", "reason": "spending_limit", "limit_reason": "Daily limit reached. Used $3870.00/500.0. Remaining: $-3370.00", "amount_usd": 50.0}, "success": false, "error_message": "", "timestamp_iso": "2026-01-19T20:23:31.069988"}
{"timestamp": 1768875811.1920187, "event_type": "trade_execute", "actor_id": "12345", "action": "CLOSE_POSITION", "resource_type": "treasury_trade", "resource_id": "test123", "ip_address": "", "user_agent": "", "details": {"position_id": "test123", "token": "BONK", "token_mint": "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263", "entry_price": 100.0, "exit_price": 110.0, "pnl_usd": 100.0, "pnl_pct": 10.0, "reason": "Test close", "tx_signature": "close_tx", "dry_run": false}, "success": true, "error_message": "", "timestamp_iso": "2026-01-19T20:23:31.192019"}
{"timestamp": 1768875811.8275592, "event_type": "trade_execute", "actor_id": "12345", "action": "CLOSE_POSITION", "resource_type": "treasury_trade", "resource_id": "test123", "ip_address": "", "user_agent": "", "details": {"position_id": "test123", "token": "BONK", "token_mint": "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263", "entry_price": 100.0, "exit_price": 110.0, "pnl_usd": 100.0, "pnl_pct": 10.0, "reason": "Test close", "tx_signature": "close_tx", "dry_run": false}, "success": true, "error_message": "", "timestamp_iso": "2026-01-19T20:23:31.827559"}
{"timestamp": 1768875812.0421267, "event_type": "security_alert", "actor_id": "12345", "action": "OPEN_POSITION_REJECTED", "resource_type": "treasury_trade", "resource_id": "BONK", "ip_address": "", "user_agent": "", "details": {"token": "BONK", "reason": "spending_limit", "limit_reason": "Daily limit reached. Used $3870.00/500.0. Remaining: $-3370.00", "amount_usd": 50.0}, "success": false, "error_message": "", "timestamp_iso": "2026-01-19T20:23:32.042127"}
{"timestamp": 1768875812.311363, "event_type": "trade_execute", "actor_id": "12345", "action": "CLOSE_POSITION", "resource_type": "treasury_trade", "resource_id": "test123", "ip_address": "", "user_agent": "", "details": {"position_id": "test123", "token": "BONK", "token_mint": "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263", "entry_price": 100.0, "exit_price": 110.0, "pnl_usd": 100.0, "pnl_pct": 10.0, "reason": "Test close", "tx_signature": "close_tx", "dry_run": false}, "success": true, "error_message": "", "timestamp_iso": "2026-01-19T20:23:32.311363"}
{"timestamp": 1768875813.2675073, "event_type": "security_alert", "actor_id": "12345", "action": "OPEN_POSITION_REJECTED", "resource_type": "treasury_trade", "resource_id": "BONK", "ip_address": "", "user_agent": "", "details": {"token": "BONK", "reason": "spending_limit", "limit_reason": "Daily limit reached. Used $3870.00/500.0. Remaining: $-3370.00", "amount_usd": 50.0}, "success": false, "error_message": "", "timestamp_iso": "2026-01-19T20:23:33.267507"}
{"timestamp": 1768875813.5568254, "event_type": "security_alert", "actor_id": "12345", "action": "OPEN_POSITION_REJECTED", "resource_type": "treasury_trade", "resource_id": "BONK", "ip_address": "", "user_agent": "", "details": {"token": "BONK", "reason": "spending_limit", "limit_reason": "Daily limit reached. Used $3870.00/500.0. Remaining: $-3370.00", "amount_usd": 50.0}, "success": false, "error_message": "", "timestamp_iso": "2026-01-19T20:23:33.556825"}
{"timestamp": 1768875813.6073384, "event_type": "security_alert", "actor_id": "12345", "action": "OPEN_POSITION_REJECTED", "resource_type": "treasury_trade", "resource_id": "BONK", "ip_address": "", "user_agent": "", "details": {"token": "BONK", "reason": "spending_limit", "limit_reason": "Daily limit reached. Used $3870.00/500.0. Remaining: $-3370.00", "amount_usd": 50.0}, "success": false, "error_message": "", "timestamp_iso": "2026-01-19T20:23:33.607338"}
{"timestamp": 1768875813.649304, "event_type": "security_alert", "actor_id": "12345", "action": "OPEN_POSITION_REJECTED", "resource_type": "treasury_trade", "resource_id": "BONK", "ip_address": "", "user_agent": "", "details": {"token": "BONK", "reason": "spending_limit", "limit_reason": "Daily limit reached. Used $3870.00/500.0. Remaining: $-3370.00", "amount_usd": 50.0}, "success": false, "error_message": "", "timestamp_iso": "2026-01-19T20:23:33.649304"}
{"timestamp": 1768875813.8762486, "event_type": "security_alert", "actor_id": "12345", "action": "OPEN_POSITION_REJECTED", "resource_type": "treasury_trade", "resource_id": "UNKNOWN", "ip_address": "", "user_agent": "", "details": {"token": "UNKNOWN", "reason": "liquidity_check_failed", "risk_tier": "MICRO"}, "success": false, "error_message": "", "timestamp_iso": "2026-01-19T20:23:33.876249"}
{"timestamp": 1768875813.978167, "event_type": "security_alert", "actor_id": "12345", "action": "OPEN_POSITION_REJECTED", "resource_type": "treasury_trade", "resource_id": "SOL", "ip_address": "", "user_agent": "", "details": {"token": "SOL", "reason": "spending_limit", "limit_reason": "Daily limit reached. Used $3870.00/500.0. Remaining: $-3370.00", "amount_usd": 50.0}, "success": false, "error_message": "", "timestamp_iso": "2026-01-19T20:23:33.978167"}
{"timestamp": 1768876183.8473697, "event_type": "security_alert", "actor_id": "12345", "action": "OPEN_POSITION_REJECTED", "resource_type": "treasury_trade", "resource_id": "TEST", "ip_address": "", "user_agent": "", "details": {"token": "TEST", "reason": "liquidity_check_failed", "risk_tier": "MICRO"}, "success": false, "error_message": "", "timestamp_iso": "2026-01-19T20:29:43.847370"}
{"timestamp": 1768876183.924051, "event_type": "security_alert", "actor_id": "12345", "action": "OPEN_POSITION_REJECTED", "resource_type": "treasury_trade", "resource_id": "SOL", "ip_address": "", "user_agent": "", "details": {"token": "SOL", "reason": "non_positive_amount", "amount_usd": 0.0}, "success": false, "error_message": "", "timestamp_iso": "2026-01-19T20:29:43.924051"}
{"timestamp": 1768876183.9819365, "event_type": "security_alert", "actor_id": "12345", "action": "OPEN_POSITION_REJECTED", "resource_type": "treasury_trade", "resource_id": "SOL", "ip_address": "", "user_agent": "", "details": {"token": "SOL", "reason": "amount_exceeds_max", "amount_usd": 150.0, "max_trade_usd": 100.0}, "success": false, "error_message": "", "timestamp_iso": "2026-01-19T20:29:43.981936"}
{"timestamp": 1768876184.0827916, "event_type": "trade_execute", "actor_id": "12345", "action": "OPEN_POSITION", "resource_type": "treasury_trade", "resource_id": "8585738d", "ip_address": "", "user_agent": "", "details": {"position_id": "8585738d", "token": "BONK", "token_mint": "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263", "amount_usd": 50.0, "entry_price": 100.0, "tp_price": 118.0, "sl_price": 88.0, "sentiment_grade": "B", "dry_run": true}, "success": true, "error_message": "", "timestamp_iso": "2026-01-19T20:29:44.082792"}
{"timestamp": 1768876184.1468613, "event_type": "trade_execute", "actor_id": "12345", "action": "OPEN_POSITION", "resource_type": "treasury_trade", "resource_id": "c5783ab8", "ip_address": "", "user_agent": "", "details": {"position_id": "c5783ab8", "token": "BONK", "token_mint": "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263", "amount_usd": 50.0, "entry_price": 100.0, "tp_price": 118.0, "sl_price": 88.0, "sentiment_grade": "B", "tx_signature": "tx123", "dry_run": false}, "success": true, "error_message": "", "timestamp_iso": "2026-01-19T20:29:44.146861"}
{"timestamp": 1768876184.237362, "event_type": "trade_execute", "actor_id": "12345", "action": "OPEN_POSITION", "resource_type": "treasury_trade", "resource_id": "72ac0235", "ip_address": "", "user_agent": "", "details": {"position_id": "72ac0235", "token": "BONK", "token_mint": "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263", "amount_usd": 50.0, "entry_price": 100.0, "tp_price": 118.0, "sl_price": 88.0, "sentiment_grade": "B", "tx_signature": "tx123", "dry_run": false}, "success": true, "error_message": "", "timestamp_iso": "2026-01-19T20:29:44.237362"}
{"timestamp": 1768876184.29451, "event_type": "trade_execute", "actor_id": "12345", "action": "OPEN_POSITION", "resource_type": "treasury_trade", "resource_id": "422f312a", "ip_address": "", "user_agent": "", "details": {"position_id": "422f312a", "token": "BONK", "token_mint": "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263", "amount_usd": 50.0, "entry_price": 100.0, "tp_price": 118.0, "sl_price": 88.0, "sentiment_grade": "B", "dry_run": true}, "success": true, "error_message": "", "timestamp_iso": "2026-01-19T20:29:44.294510"}
{"timestamp": 1768876184.4155056, "event_type": "trade_execute", "actor_id": "12345", "action": "OPEN_POSITION", "resource_type": "treasury_trade", "resource_id": "6a595a3d", "ip_address": "", "user_agent": "", "details": {"position_id": "6a595a3d", "token": "BONK", "token_mint": "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263", "amount_usd": 50.0, "entry_price": 100.0, "tp_price": 118.0, "sl_price": 88.0, "sentiment_grade": "B", "tx_signature": "tx123", "dry_run": false}, "success": true, "error_message": "", "timestamp_iso": "2026-01-19T20:29:44.415506"}
{"timestamp": 1768876184.6081905, "event_type": "trade_execute", "actor_id": "12345", "action": "CLOSE_POSITION", "resource_type": "treasury_trade", "resource_id": "test123", "ip_address": "", "user_agent": "", "details": {"position_id": "test123", "token": "BONK", "token_mint": "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263", "entry_price": 100.0, "exit_price": 110.0, "pnl_usd": 100.0, "pnl_pct": 10.0, "reason": "Test close", "tx_signature": "close_tx", "dry_run": false}, "success": true, "error_message": "", "timestamp_iso": "2026-01-19T20:29:44.608191"}
{"timestamp": 1768876184.731945, "event_type": "trade_execute", "actor_id": "12345", "action": "CLOSE_POSITION", "resource_type": "treasury_trade", "resource_id": "test123", "ip_address": "", "user_agent": "", "details": {"position_id": "test123", "token": "BONK", "token_mint": "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263", "entry_price": 100.0, "exit_price": 110.0, "pnl_usd": 100.0, "pnl_pct": 10.0, "reason": "Test close", "tx_signature": "close_tx", "dry_run": false}, "success": true, "error_message": "", "timestamp_iso": "2026-01-19T20:29:44.731945"}
{"timestamp": 1768876184.796984, "event_type": "trade_execute", "actor_id": "12345", "action": "OPEN_POSITION", "resource_type": "treasury_trade", "resource_id": "6d9fe160", "ip_address": "", "user_agent": "", "details": {"position_id": "6d9fe160", "token": "BONK", "token_mint": "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263", "amount_usd": 50.0, "entry_price": 100.0, "tp_price": 118.0, "sl_price": 88.0, "sentiment_grade": "B", "tx_signature": "tx123", "dry_run": false}, "success": true, "error_message": "", "timestamp_iso": "2026-01-19T20:29:44.796984"}
{"timestamp": 1768876184.872728, "event_type": "trade_execute", "actor_id": "12345", "action": "CLOSE_POSITION", "resource_type": "treasury_trade", "resource_id": "test123", "ip_address": "", "user_agent": "", "details": {"position_id": "test123", "token": "BONK", "token_mint": "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263", "entry_price": 100.0, "exit_price": 110.0, "pnl_usd": 100.0, "pnl_pct": 10.0, "reason": "Test close", "tx_signature": "close_tx", "dry_run": false}, "success": true, "error_message": "", "timestamp_iso": "2026-01-19T20:29:44.872728"}
{"timestamp": 1768876185.1910522, "event_type": "trade_execute", "actor_id": "12345", "action": "OPEN_POSITION", "resource_type": "treasury_trade", "resource_id": "9bb91cdd", "ip_address": "", "user_agent": "", "details": {"position_id": "9bb91cdd", "token": "BONK", "token_mint": "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263", "amount_usd": 50.0, "entry_price": 100.0, "tp_price": 118.0, "sl_price": 88.0, "sentiment_grade": "B", "dry_run": true}, "success": true, "error_message": "", "timestamp_iso": "2026-01-19T20:29:45.191052"}
{"timestamp": 1768876185.2488766, "event_type": "trade_execute", "actor_id": "12345", "action": "OPEN_POSITION", "resource_type": "treasury_trade", "resource_id": "b03d204e", "ip_address": "", "user_agent": "", "details": {"position_id": "b03d204e", "token": "BONK", "token_mint": "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263", "amount_usd": 50.0, "entry_price": 100.0, "tp_price": 118.0, "sl_price": 88.0, "sentiment_grade": "B", "dry_run": true}, "success": true, "error_message": "", "timestamp_iso": "2026-01-19T20:29:45.248877"}
{"timestamp": 1768876185.2847633, "event_type": "trade_execute", "actor_id": "12345", "action": "OPEN_POSITION", "resource_type": "treasury_trade", "resource_id": "61987514", "ip_address": "", "user_agent": "", "details": {"position_id": "61987514", "token": "BONK", "token_mint": "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263", "amount_usd": 50.0, "entry_price": 100.0, "tp_price": 118.0, "sl_price": 88.0, "sentiment_grade": "B", "dry_run": true}, "success": true, "error_message": "", "timestamp_iso": "2026-01-19T20:29:45.284763"}
{"timestamp": 1768876185.3241122, "event_type": "trade_execute", "actor_id": "12345", "action": "OPEN_POSITION", "resource_type": "treasury_trade", "resource_id": "582d88c1", "ip_address": "", "user_agent": "", "details": {"position_id": "582d88c1", "token": "BONK", "token_mint": "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263", "amount_usd": 50.0, "entry_price": 100.0, "tp_price": 118.0, "sl_price": 88.0, "sentiment_grade": "B", "dry_run": true}, "success": true, "error_message": "", "timestamp_iso": "2026-01-19T20:29:45.324112"}
{"timestamp": 1768876185.3801315, "event_type": "security_alert", "actor_id": "12345", "action": "OPEN_POSITION_REJECTED", "resource_type": "treasury_trade", "resource_id": "UNKNOWN", "ip_address": "", "user_agent": "", "details": {"token": "UNKNOWN", "reason": "liquidity_check_failed", "risk_tier": "MICRO"}, "success": false, "error_message": "", "timestamp_iso": "2026-01-19T20:29:45.380131"}
{"timestamp": 1768876185.4414554, "event_type": "trade_execute", "actor_id": "12345", "action": "OPEN_POSITION", "resource_type": "treasury_trade", "resource_id": "ca27dbd4", "ip_address": "", "user_agent": "", "details": {"position_id": "ca27dbd4", "token": "SOL", "token_mint": "So11111111111111111111111111111111111111112", "amount_usd": 50.0, "entry_price": 100.0, "tp_price": 118.0, "sl_price": 88.0, "sentiment_grade": "B", "dry_run": true}, "success": true, "error_message": "", "timestamp_iso": "2026-01-19T20:29:45.441455"}
{"timestamp": 1768876593.5902271, "event_type": "security_alert", "actor_id": "12345", "action": "OPEN_POSITION_REJECTED", "resource_type": "treasury_trade", "resource_id": "TEST", "ip_address": "", "user_agent": "", "details": {"token": "TEST", "reason": "liquidity_check_failed", "risk_tier": "MICRO"}, "success": false, "error_message": "", "timestamp_iso": "2026-01-19T20:36:33.590227"}
{"timestamp": 1768876593.625487, "event_type": "security_alert", "actor_id": "12345", "action": "OPEN_POSITION_REJECTED", "resource_type": "treasury_trade", "resource_id": "SOL", "ip_address": "", "user_agent": "", "details": {"token": "SOL", "reason": "non_positive_amount", "amount_usd": 0.0}, "success": false, "error_message": "", "timestamp_iso": "2026-01-19T20:36:33.625487"}
{"timestamp": 1768876593.674007, "event_type": "security_alert", "actor_id": "12345", "action": "OPEN_POSITION_REJECTED", "resource_type": "treasury_trade", "resource_id": "SOL", "ip_address": "", "user_agent": "", "details": {"token": "SOL", "reason": "amount_exceeds_max", "amount_usd": 150.0, "max_trade_usd": 100.0}, "success": false, "error_message": "", "timestamp_iso": "2026-01-19T20:36:33.674007"}
{"timestamp": 1768876593.7600324, "event_type": "trade_execute", "actor_id": "12345", "action": "OPEN_POSITION", "resource_type": "treasury_trade", "resource_id": "1aef4dc1", "ip_address": "", "user_agent": "", "details": {"position_id": "1aef4dc1", "token": "BONK", "token_mint": "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263", "amount_usd": 50.0, "entry_price": 100.0, "tp_price": 118.0, "sl_price": 88.0, "sentiment_grade": "B", "dry_run": true}, "success": true, "error_message": "", "timestamp_iso": "2026-01-19T20:36:33.760032"}
{"timestamp": 1768876593.8023126, "event_type": "trade_execute", "actor_id": "12345", "action": "OPEN_POSITION", "resource_type": "treasury_trade", "resource_id": "7b803846", "ip_address": "", "user_agent": "", "details": {"position_id": "7b803846", "token": "BONK", "token_mint": "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263", "amount_usd": 50.0, "entry_price": 100.0, "tp_price": 118.0, "sl_price": 88.0, "sentiment_grade": "B", "tx_signature": "tx123", "dry_run": false}, "success": true, "error_message": "", "timestamp_iso": "2026-01-19T20:36:33.802313"}
{"timestamp": 1768876593.88221, "event_type": "trade_execute", "actor_id": "12345", "action": "OPEN_POSITION", "resource_type": "treasury_trade", "resource_id": "8ec8c1ec", "ip_address": "", "user_agent": "", "details": {"position_id": "8ec8c1ec", "token": "BONK", "token_mint": "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263", "amount_usd": 50.0, "entry_price": 100.0, "tp_price": 118.0, "sl_price": 88.0, "sentiment_grade": "B", "tx_signature": "tx123", "dry_run": false}, "success": true, "error_message": "", "timestamp_iso": "2026-01-19T20:36:33.882210"}
{"timestamp": 1768876593.9323833, "event_type": "trade_execute", "actor_id": "12345", "action": "OPEN_POSITION", "resource_type": "treasury_trade", "resource_id": "5d3f9c79", "ip_address": "", "user_agent": "", "details": {"position_id": "5d3f9c79", "token": "BONK", "token_mint": "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263", "amount_usd": 50.0, "entry_price": 100.0, "tp_price": 118.0, "sl_price": 88.0, "sentiment_grade": "B", "dry_run": true}, "success": true, "error_message": "", "timestamp_iso": "2026-01-19T20:36:33.932383"}
{"timestamp": 1768876594.0301702, "event_type": "trade_execute", "actor_id": "12345", "action": "OPEN_POSITION", "resource_type": "treasury_trade", "resource_id": "f283bece", "ip_address": "", "user_agent": "", "details": {"position_id": "f283bece", "token": "BONK", "token_mint": "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263", "amount_usd": 50.0, "entry_price": 100.0, "tp_price": 118.0, "sl_price": 88.0, "sentiment_grade": "B", "tx_signature": "tx123", "dry_run": false}, "success": true, "error_message": "", "timestamp_iso": "2026-01-19T20:36:34.030170"}
{"timestamp": 1768876594.0963995, "event_type": "trade_execute", "actor_id": "12345", "action": "CLOSE_POSITION", "resource_type": "treasury_trade", "resource_id": "test123", "ip_address": "", "user_agent": "", "details": {"position_id": "test123", "token": "BONK", "token_mint": "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263", "entry_price": 100.0, "exit_price": 110.0, "pnl_usd": 100.0, "pnl_pct": 10.0, "reason": "Test close", "tx_signature": "close_tx", "dry_run": false}, "success": true, "error_message": "", "timestamp_iso": "2026-01-19T20:36:34.096400"}
{"timestamp": 1768876594.210733, "event_type": "trade_execute", "actor_id": "12345", "action": "CLOSE_POSITION", "resource_type": "treasury_trade", "resource_id": "test123", "ip_address": "", "user_agent": "", "details": {"position_id": "test123", "token": "BONK", "token_mint": "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263", "entry_price": 100.0, "exit_price": 110.0, "pnl_usd": 100.0, "pnl_pct": 10.0, "reason": "Test close", "tx_signature": "close_tx", "dry_run": false}, "success": true, "error_message": "", "timestamp_iso": "2026-01-19T20:36:34.210733"}
{"timestamp": 1768876594.2631586, "event_type": "trade_execute", "actor_id": "12345", "action": "OPEN_POSITION", "resource_type": "treasury_trade", "resource_id": "b7660ce8", "ip_address": "", "user_agent": "", "details": {"position_id": "b7660ce8", "token": "BONK", "token_mint": "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263", "amount_usd": 50.0, "entry_price": 100.0, "tp_price": 118.0, "sl_price": 88.0, "sentiment_grade": "B", "tx_signature": "tx123", "dry_run": false}, "success": true, "error_message": "", "timestamp_iso": "2026-01-19T20:36:34.263159"}
{"timestamp": 1768876594.3342314, "event_type": "trade_execute", "actor_id": "12345", "action": "CLOSE_POSITION", "resource_type": "treasury_trade", "resource_id": "test123", "ip_address": "", "user_agent": "", "details": {"position_id": "test123", "token": "BONK", "token_mint": "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263", "entry_price": 100.0, "exit_price": 110.0, "pnl_usd": 100.0, "pnl_pct": 10.0, "reason": "Test close", "tx_signature": "close_tx", "dry_run": false}, "success": true, "error_message": "", "timestamp_iso": "2026-01-19T20:36:34.334231"}
{"timestamp": 1768876594.5749953, "event_type": "trade_execute", "actor_id": "12345", "action": "OPEN_POSITION", "resource_type": "treasury_trade", "resource_id": "c508593d", "ip_address": "", "user_agent": "", "details": {"position_id": "c508593d", "token": "BONK", "token_mint": "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263", "amount_usd": 50.0, "entry_price": 100.0, "tp_price": 118.0, "sl_price": 88.0, "sentiment_grade": "B", "dry_run": true}, "success": true, "error_message": "", "timestamp_iso": "2026-01-19T20:36:34.574995"}
{"timestamp": 1768876594.6241527, "event_type": "trade_execute", "actor_id": "12345", "action": "OPEN_POSITION", "resource_type": "treasury_trade", "resource_id": "226470f2", "ip_address": "", "user_agent": "", "details": {"position_id": "226470f2", "token": "BONK", "token_mint": "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263", "amount_usd": 50.0, "entry_price": 100.0, "tp_price": 118.0, "sl_price": 88.0, "sentiment_grade": "B", "dry_run": true}, "success": true, "error_message": "", "timestamp_iso": "2026-01-19T20:36:34.624153"}
{"timestamp": 1768876594.6609879, "event_type": "trade_execute", "actor_id": "12345", "action": "OPEN_POSITION", "resource_type": "treasury_trade", "resource_id": "8c838eca", "ip_address": "", "user_agent": "", "details": {"position_id": "8c838eca", "token": "BONK", "token_mint": "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263", "amount_usd": 50.0, "entry_price": 100.0, "tp_price": 118.0, "sl_price": 88.0, "sentiment_grade": "B", "dry_run": true}, "success": true, "error_message": "", "timestamp_iso": "2026-01-19T20:36:34.660988"}
{"timestamp": 1768876594.69026, "event_type": "trade_execute", "actor_id": "12345", "action": "OPEN_POSITION", "resource_type": "treasury_trade", "resource_id": "9f27bfef", "ip_address": "", "user_agent": "", "details": {"position_id": "9f27bfef", "token": "BONK", "token_mint": "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263", "amount_usd": 50.0, "entry_price": 100.0, "tp_price": 118.0, "sl_price": 88.0, "sentiment_grade": "B", "dry_run": true}, "success": true, "error_message": "", "timestamp_iso": "2026-01-19T20:36:34.690260"}
{"timestamp": 1768876594.733165, "event_type": "security_alert", "actor_id": "12345", "action": "OPEN_POSITION_REJECTED", "resource_type": "treasury_trade", "resource_id": "UNKNOWN", "ip_address": "", "user_agent": "", "details": {"token": "UNKNOWN", "reason": "liquidity_check_failed", "risk_tier": "MICRO"}, "success": false, "error_message": "", "timestamp_iso": "2026-01-19T20:36:34.733165"}
{"timestamp": 1768876594.7813807, "event_type": "trade_execute", "actor_id": "12345", "action": "OPEN_POSITION", "resource_type": "treasury_trade", "resource_id": "204a0ca5", "ip_address": "", "user_agent": "", "details": {"position_id": "204a0ca5", "token": "SOL", "token_mint": "So11111111111111111111111111111111111111112", "amount_usd": 50.0, "entry_price": 100.0, "tp_price": 118.0, "sl_price": 88.0, "sentiment_grade": "B", "dry_run": true}, "success": true, "error_message": "", "timestamp_iso": "2026-01-19T20:36:34.781381"}
{"timestamp": 1768877230.5903745, "event_type": "trade_execute", "actor_id": "12345", "action": "OPEN_POSITION", "resource_type": "treasury_trade", "resource_id": "63483c5a", "ip_address": "", "user_agent": "", "details": {"position_id": "63483c5a", "token": "SOL", "token_mint": "SOL_MINT", "amount_usd": 25.0, "entry_price": 100.0, "tp_price": 118.0, "sl_price": 88.0, "sentiment_grade": "B", "dry_run": true}, "success": true, "error_message": "", "timestamp_iso": "2026-01-19T20:47:10.590374"}
{"timestamp": 1768877230.6494122, "event_type": "trade_execute", "actor_id": "12345", "action": "OPEN_POSITION", "resource_type": "treasury_trade", "resource_id": "4a6f5e15", "ip_address": "", "user_agent": "", "details": {"position_id": "4a6f5e15", "token": "SOL", "token_mint": "SOL_MINT", "amount_usd": 25.0, "entry_price": 100.0, "tp_price": 118.0, "sl_price": 88.0, "sentiment_grade": "B", "dry_run": true}, "success": true, "error_message": "", "timestamp_iso": "2026-01-19T20:47:10.649412"}
{"timestamp": 1768877230.7320037, "event_type": "trade_execute", "actor_id": "12345", "action": "OPEN_POSITION", "resource_type": "treasury_trade", "resource_id": "b0fc2bd8", "ip_address": "", "user_agent": "", "details": {"position_id": "b0fc2bd8", "token": "SOL", "token_mint": "SOL_MINT", "amount_usd": 25.0, "entry_price": 100.0, "tp_price": 118.0, "sl_price": 88.0, "sentiment_grade": "B", "dry_run": true}, "success": true, "error_message": "", "timestamp_iso": "2026-01-19T20:47:10.732004"}
{"timestamp": 1768877230.761007, "event_type": "security_alert", "actor_id": "12345", "action": "OPEN_POSITION_REJECTED", "resource_type": "treasury_trade", "resource_id": "SOL", "ip_address": "", "user_agent": "", "details": {"token": "SOL", "reason": "duplicate", "existing_positions": 1}, "success": false, "error_message": "", "timestamp_iso": "2026-01-19T20:47:10.761007"}
{"timestamp": 1768877230.989509, "event_type": "trade_execute", "actor_id": "12345", "action": "OPEN_POSITION", "resource_type": "treasury_trade", "resource_id": "88ab97e7", "ip_address": "", "user_agent": "", "details": {"position_id": "88ab97e7", "token": "SOL", "token_mint": "SOL_MINT", "amount_usd": 25.0, "entry_price": 100.0, "tp_price": 118.0, "sl_price": 88.0, "sentiment_grade": "B", "dry_run": true}, "success": true, "error_message": "", "timestamp_iso": "2026-01-19T20:47:10.989509"}
{"timestamp": 1768877231.0934372, "event_type": "trade_execute", "actor_id": "12345", "action": "CLOSE_POSITION", "resource_type": "treasury_trade", "resource_id": "88ab97e7", "ip_address": "", "user_agent": "", "details": {"position_id": "88ab97e7", "token": "SOL", "entry_price": 100.0, "exit_price": 100.0, "pnl_usd": 0.0, "pnl_pct": 0.0, "reason": "Test close", "dry_run": true}, "success": true, "error_message": "", "timestamp_iso": "2026-01-19T20:47:11.093437"}
{"timestamp": 1768877231.2810826, "event_type": "trade_execute", "actor_id": "12345", "action": "OPEN_POSITION", "resource_type": "treasury_trade", "resource_id": "ffd09d86", "ip_address": "", "user_agent": "", "details": {"position_id": "ffd09d86", "token": "SOL", "token_mint": "SOL_MINT", "amount_usd": 50.0, "entry_price": 100.0, "tp_price": 118.0, "sl_price": 88.0, "sentiment_grade": "B", "dry_run": true}, "success": true, "error_message": "", "timestamp_iso": "2026-01-19T20:47:11.281083"}
{"timestamp": 1768877231.3481662, "event_type": "trade_execute", "actor_id": "12345", "action": "CLOSE_POSITION", "resource_type": "treasury_trade", "resource_id": "ffd09d86", "ip_address": "", "user_agent": "", "details": {"position_id": "ffd09d86", "token": "SOL", "entry_price": 100.0, "exit_price": 120.0, "pnl_usd": 10.0, "pnl_pct": 20.0, "reason": "Manual close", "dry_run": true}, "success": true, "error_message": "", "timestamp_iso": "2026-01-19T20:47:11.348166"}
{"timestamp": 1768877234.6287813, "event_type": "trade_execute", "actor_id": "12345", "action": "OPEN_POSITION", "resource_type": "treasury_trade", "resource_id": "39206e25", "ip_address": "", "user_agent": "", "details": {"position_id": "39206e25", "token": "SOL", "token_mint": "SOL_MINT", "amount_usd": 25.0, "entry_price": 100.0, "tp_price": 118.0, "sl_price": 88.0, "sentiment_grade": "B", "dry_run": true}, "success": true, "error_message": "", "timestamp_iso": "2026-01-19T20:47:14.628781"}
{"timestamp": 1768877234.6648839, "event_type": "security_alert", "actor_id": "99999", "action": "CLOSE_POSITION_REJECTED", "resource_type": "treasury_trade", "resource_id": "39206e25", "ip_address": "", "user_agent": "", "details": {"position_id": "39206e25", "reason": "unauthorized"}, "success": false, "error_message": "", "timestamp_iso": "2026-01-19T20:47:14.664884"}
{"timestamp": 1768877234.8193693, "event_type": "trade_execute", "actor_id": "12345", "action": "OPEN_POSITION", "resource_type": "treasury_trade", "resource_id": "cfe64164", "ip_address": "", "user_agent": "", "details": {"position_id": "cfe64164", "token": "TOK0", "token_mint": "TOKEN0_MINT", "amount_usd": 12.5, "entry_price": 100.0, "tp_price": 118.0, "sl_price": 88.0, "sentiment_grade": "B", "dry_run": true}, "success": true, "error_message": "", "timestamp_iso": "2026-01-19T20:47:14.819369"}
{"timestamp": 1768877235.0253353, "event_type": "trade_execute", "actor_id": "12345", "action": "OPEN_POSITION", "resource_type": "treasury_trade", "resource_id": "fb75b1ff", "ip_address": "", "user_agent": "", "details": {"position_id": "fb75b1ff", "token": "TOK1", "token_mint": "TOKEN1_MINT", "amount_usd": 12.5, "entry_price": 100.0, "tp_price": 118.0, "sl_price": 88.0, "sentiment_grade": "B", "dry_run": true}, "success": true, "error_message": "", "timestamp_iso": "2026-01-19T20:47:15.025335"}
{"timestamp": 1768877235.0830946, "event_type": "security_alert", "actor_id": "12345", "action": "OPEN_POSITION_REJECTED", "resource_type": "treasury_trade", "resource_id": "TOK2", "ip_address": "", "user_agent": "", "details": {"token": "TOK2", "reason": "max_positions"}, "success": false, "error_message": "", "timestamp_iso": "2026-01-19T20:47:15.083095"}
{"timestamp": 1768877236.2481105, "event_type": "trade_execute", "actor_id": "12345", "action": "OPEN_POSITION", "resource_type": "treasury_trade", "resource_id": "5c9adcae", "ip_address": "", "user_agent": "", "details": {"position_id": "5c9adcae", "token": "SOL", "token_mint": "SOL_MINT", "amount_usd": 25.0, "entry_price": 100.0, "tp_price": 118.0, "sl_price": 88.0, "sentiment_grade": "B", "dry_run": true}, "success": true, "error_message": "", "timestamp_iso": "2026-01-19T20:47:16.248111"}
{"timestamp": 1768877236.3049188, "event_type": "trade_execute", "actor_id": "12345", "action": "CLOSE_POSITION", "resource_type": "treasury_trade", "resource_id": "5c9adcae", "ip_address": "", "user_agent": "", "details": {"position_id": "5c9adcae", "token": "SOL", "entry_price": 100.0, "exit_price": 100.0, "pnl_usd": 0.0, "pnl_pct": 0.0, "reason": "Manual close", "dry_run": true}, "success": true, "error_message": "", "timestamp_iso": "2026-01-19T20:47:16.304919"}
{"timestamp": 1768877236.334368, "event_type": "security_alert", "actor_id": "12345", "action": "CLOSE_POSITION_REJECTED", "resource_type": "treasury_trade", "resource_id": "5c9adcae", "ip_address": "", "user_agent": "", "details": {"position_id": "5c9adcae", "reason": "not_found"}, "success": false, "error_message": "", "timestamp_iso": "2026-01-19T20:47:16.334368"}
{"timestamp": 1768877592.404217, "event_type": "trade_execute", "actor_id": "12345", "action": "OPEN_POSITION", "resource_type": "treasury_trade", "resource_id": "f024d143", "ip_address": "", "user_agent": "", "details": {"position_id": "f024d143", "token": "SOL", "token_mint": "SOL_MINT", "amount_usd": 25.0, "entry_price": 100.0, "tp_price": 118.0, "sl_price": 88.0, "sentiment_grade": "B", "dry_run": true}, "success": true, "error_message": "", "timestamp_iso": "2026-01-19T20:53:12.404217"}
{"timestamp": 1768877592.4503474, "event_type": "trade_execute", "actor_id": "12345", "action": "OPEN_POSITION", "resource_type": "treasury_trade", "resource_id": "910b694a", "ip_address": "", "user_agent": "", "details": {"position_id": "910b694a", "token": "SOL", "token_mint": "SOL_MINT", "amount_usd": 25.0, "entry_price": 100.0, "tp_price": 118.0, "sl_price": 88.0, "sentiment_grade": "B", "dry_run": true}, "success": true, "error_message": "", "timestamp_iso": "2026-01-19T20:53:12.450347"}
{"timestamp": 1768877592.5160513, "event_type": "trade_execute", "actor_id": "12345", "action": "OPEN_POSITION", "resource_type": "treasury_trade", "resource_id": "7f5e7a3a", "ip_address": "", "user_agent": "", "details": {"position_id": "7f5e7a3a", "token": "SOL", "token_mint": "SOL_MINT", "amount_usd": 25.0, "entry_price": 100.0, "tp_price": 118.0, "sl_price": 88.0, "sentiment_grade": "B", "dry_run": true}, "success": true, "error_message": "", "timestamp_iso": "2026-01-19T20:53:12.516051"}
{"timestamp": 1768877592.532505, "event_type": "security_alert", "actor_id": "12345", "action": "OPEN_POSITION_REJECTED", "resource_type": "treasury_trade", "resource_id": "SOL", "ip_address": "", "user_agent": "", "details": {"token": "SOL", "reason": "duplicate", "existing_positions": 1}, "success": false, "error_message": "", "timestamp_iso": "2026-01-19T20:53:12.532505"}
{"timestamp": 1768877592.6363032, "event_type": "trade_execute", "actor_id": "12345", "action": "OPEN_POSITION", "resource_type": "treasury_trade", "resource_id": "2d1d95dd", "ip_address": "", "user_agent": "", "details": {"position_id": "2d1d95dd", "token": "SOL", "token_mint": "SOL_MINT", "amount_usd": 25.0, "entry_price": 100.0, "tp_price": 118.0, "sl_price": 88.0, "sentiment_grade": "B", "dry_run": true}, "success": true, "error_message": "", "timestamp_iso": "2026-01-19T20:53:12.636303"}
{"timestamp": 1768877592.6714635, "event_type": "trade_execute", "actor_id": "12345", "action": "CLOSE_POSITION", "resource_type": "treasury_trade", "resource_id": "2d1d95dd", "ip_address": "", "user_agent": "", "details": {"position_id": "2d1d95dd", "token": "SOL", "entry_price": 100.0, "exit_price": 100.0, "pnl_usd": 0.0, "pnl_pct": 0.0, "reason": "Test close", "dry_run": true}, "success": true, "error_message": "", "timestamp_iso": "2026-01-19T20:53:12.671463"}
{"timestamp": 1768877592.7137127, "event_type": "security_alert", "actor_id": "12345", "action": "OPEN_POSITION_REJECTED", "resource_type": "treasury_trade", "resource_id": "SOL", "ip_address": "", "user_agent": "", "details": {"token": "SOL", "reason": "risk_limit", "alert": "POSITION_SIZE exceeded: 100.00 >= 100.00", "amount_usd": 100.0}, "success": false, "error_message": "", "timestamp_iso": "2026-01-19T20:53:12.713713"}
{"timestamp": 1768877594.1037626, "event_type": "trade_execute", "actor_id": "12345", "action": "OPEN_POSITION", "resource_type": "treasury_trade", "resource_id": "85693faa", "ip_address": "", "user_agent": "", "details": {"position_id": "85693faa", "token": "SOL", "token_mint": "SOL_MINT", "amount_usd": 25.0, "entry_price": 100.0, "tp_price": 118.0, "sl_price": 88.0, "sentiment_grade": "B", "dry_run": true}, "success": true, "error_message": "", "timestamp_iso": "2026-01-19T20:53:14.103763"}
{"timestamp": 1768877594.1237154, "event_type": "security_alert", "actor_id": "99999", "action": "CLOSE_POSITION_REJECTED", "resource_type": "treasury_trade", "resource_id": "85693faa", "ip_address": "", "user_agent": "", "details": {"position_id": "85693faa", "reason": "unauthorized"}, "success": false, "error_message": "", "timestamp_iso": "2026-01-19T20:53:14.123715"}
{"timestamp": 1768877594.1838481, "event_type": "trade_execute", "actor_id": "12345", "action": "OPEN_POSITION", "resource_type": "treasury_trade", "resource_id": "4158069c", "ip_address": "", "user_agent": "", "details": {"position_id": "4158069c", "token": "TOK0", "token_mint": "TOKEN0_MINT", "amount_usd": 12.5, "entry_price": 100.0, "tp_price": 118.0, "sl_price": 88.0, "sentiment_grade": "B", "dry_run": true}, "success": true, "error_message": "", "timestamp_iso": "2026-01-19T20:53:14.183848"}
{"timestamp": 1768877594.2296457, "event_type": "trade_execute", "actor_id": "12345", "action": "OPEN_POSITION", "resource_type": "treasury_trade", "resource_id": "aa92012a", "ip_address": "", "user_agent": "", "details": {"position_id": "aa92012a", "token": "TOK1", "token_mint": "TOKEN1_MINT", "amount_usd": 12.5, "entry_price": 100.0, "tp_price": 118.0, "sl_price": 88.0, "sentiment_grade": "B", "dry_run": true}, "success": true, "error_message": "", "timestamp_iso": "2026-01-19T20:53:14.229646"}
{"timestamp": 1768877594.2566593, "event_type": "security_alert", "actor_id": "12345", "action": "OPEN_POSITION_REJECTED", "resource_type": "treasury_trade", "resource_id": "TOK2", "ip_address": "", "user_agent": "", "details": {"token": "TOK2", "reason": "max_positions"}, "success": false, "error_message": "", "timestamp_iso": "2026-01-19T20:53:14.256659"}
{"timestamp": 1768877594.6300602, "event_type": "trade_execute", "actor_id": "12345", "action": "OPEN_POSITION", "resource_type": "treasury_trade", "resource_id": "d9aad989", "ip_address": "", "user_agent": "", "details": {"position_id": "d9aad989", "token": "SOL", "token_mint": "SOL_MINT", "amount_usd": 25.0, "entry_price": 100.0, "tp_price": 118.0, "sl_price": 88.0, "sentiment_grade": "B", "dry_run": true}, "success": true, "error_message": "", "timestamp_iso": "2026-01-19T20:53:14.630060"}
{"timestamp": 1768877594.6660826, "event_type": "trade_execute", "actor_id": "12345", "action": "CLOSE_POSITION", "resource_type": "treasury_trade", "resource_id": "d9aad989", "ip_address": "", "user_agent": "", "details": {"position_id": "d9aad989", "token": "SOL", "entry_price": 100.0, "exit_price": 100.0, "pnl_usd": 0.0, "pnl_pct": 0.0, "reason": "Manual close", "dry_run": true}, "success": true, "error_message": "", "timestamp_iso": "2026-01-19T20:53:14.666083"}
{"timestamp": 1768877594.6920903, "event_type": "security_alert", "actor_id": "12345", "action": "CLOSE_POSITION_REJECTED", "resource_type": "treasury_trade", "resource_id": "d9aad989", "ip_address": "", "user_agent": "", "details": {"position_id": "d9aad989", "reason": "not_found"}, "success": false, "error_message": "", "timestamp_iso": "2026-01-19T20:53:14.692090"}
{"timestamp": 1768878021.8446772, "event_type": "trade_execute", "actor_id": "12345", "action": "OPEN_POSITION", "resource_type": "treasury_trade", "resource_id": "1788ba55", "ip_address": "", "user_agent": "", "details": {"position_id": "1788ba55", "token": "SOL", "token_mint": "SOL_MINT", "amount_usd": 25.0, "entry_price": 100.0, "tp_price": 118.0, "sl_price": 88.0, "sentiment_grade": "B", "dry_run": true}, "success": true, "error_message": "", "timestamp_iso": "2026-01-19T21:00:21.844677"}
{"timestamp": 1768878022.1597002, "event_type": "trade_execute", "actor_id": "12345", "action": "OPEN_POSITION", "resource_type": "treasury_trade", "resource_id": "e20b7416", "ip_address": "", "user_agent": "", "details": {"position_id": "e20b7416", "token": "SOL", "token_mint": "SOL_MINT", "amount_usd": 25.0, "entry_price": 100.0, "tp_price": 118.0, "sl_price": 88.0, "sentiment_grade": "B", "dry_run": true}, "success": true, "error_message": "", "timestamp_iso": "2026-01-19T21:00:22.159700"}
{"timestamp": 1768878022.5001724, "event_type": "trade_execute", "actor_id": "12345", "action": "OPEN_POSITION", "resource_type": "treasury_trade", "resource_id": "8f1cddaf", "ip_address": "", "user_agent": "", "details": {"position_id": "8f1cddaf", "token": "SOL", "token_mint": "SOL_MINT", "amount_usd": 25.0, "entry_price": 100.0, "tp_price": 118.0, "sl_price": 88.0, "sentiment_grade": "B", "dry_run": true}, "success": true, "error_message": "", "timestamp_iso": "2026-01-19T21:00:22.500172"}
{"timestamp": 1768878022.6095068, "event_type": "security_alert", "actor_id": "12345", "action": "OPEN_POSITION_REJECTED", "resource_type": "treasury_trade", "resource_id": "SOL", "ip_address": "", "user_agent": "", "details": {"token": "SOL", "reason": "duplicate", "existing_positions": 1}, "success": false, "error_message": "", "timestamp_iso": "2026-01-19T21:00:22.609507"}
{"timestamp": 1768878023.0721047, "event_type": "trade_execute", "actor_id": "12345", "action": "OPEN_POSITION", "resource_type": "treasury_trade", "resource_id": "216bf314", "ip_address": "", "user_agent": "", "details": {"position_id": "216bf314", "token": "SOL", "token_mint": "SOL_MINT", "amount_usd": 25.0, "entry_price": 100.0, "tp_price": 118.0, "sl_price": 88.0, "sentiment_grade": "B", "dry_run": true}, "success": true, "error_message": "", "timestamp_iso": "2026-01-19T21:00:23.072105"}
{"timestamp": 1768878023.1790035, "event_type": "trade_execute", "actor_id": "12345", "action": "CLOSE_POSITION", "resource_type": "treasury_trade", "resource_id": "216bf314", "ip_address": "", "user_agent": "", "details": {"position_id": "216bf314", "token": "SOL", "entry_price": 100.0, "exit_price": 100.0, "pnl_usd": 0.0, "pnl_pct": 0.0, "reason": "Test close", "dry_run": true}, "success": true, "error_message": "", "timestamp_iso": "2026-01-19T21:00:23.179003"}
{"timestamp": 1768878023.3120823, "event_type": "trade_execute", "actor_id": "12345", "action": "OPEN_POSITION", "resource_type": "treasury_trade", "resource_id": "8bd1d81c", "ip_address": "", "user_agent": "", "details": {"position_id": "8bd1d81c", "token": "SOL", "token_mint": "So11111111111111111111111111111111111111112", "amount_usd": 75.0, "entry_price": 100.0, "tp_price": 118.0, "sl_price": 88.0, "sentiment_grade": "B", "dry_run": true}, "success": true, "error_message": "", "timestamp_iso": "2026-01-19T21:00:23.312082"}
{"timestamp": 1768878023.6374123, "event_type": "trade_execute", "actor_id": "12345", "action": "CLOSE_POSITION", "resource_type": "treasury_trade", "resource_id": "8bd1d81c", "ip_address": "", "user_agent": "", "details": {"position_id": "8bd1d81c", "token": "SOL", "entry_price": 100.0, "exit_price": 120.0, "pnl_usd": 15.0, "pnl_pct": 20.0, "reason": "Manual close", "dry_run": true}, "success": true, "error_message": "", "timestamp_iso": "2026-01-19T21:00:23.637412"}
{"timestamp": 1768878024.8790445, "event_type": "trade_execute", "actor_id": "12345", "action": "OPEN_POSITION", "resource_type": "treasury_trade", "resource_id": "3c570ff8", "ip_address": "", "user_agent": "", "details": {"position_id": "3c570ff8", "token": "SOL", "token_mint": "SOL_MINT", "amount_usd": 25.0, "entry_price": 100.0, "tp_price": 118.0, "sl_price": 88.0, "sentiment_grade": "B", "dry_run": true}, "success": true, "error_message": "", "timestamp_iso": "2026-01-19T21:00:24.879045"}
{"timestamp": 1768878024.908541, "event_type": "security_alert", "actor_id": "99999", "action": "CLOSE_POSITION_REJECTED", "resource_type": "treasury_trade", "resource_id": "3c570ff8", "ip_address": "", "user_agent": "", "details": {"position_id": "3c570ff8", "reason": "unauthorized"}, "success": false, "error_message": "", "timestamp_iso": "2026-01-19T21:00:24.908541"}
{"timestamp": 1768878025.3644626, "event_type": "trade_execute", "actor_id": "12345", "action": "OPEN_POSITION", "resource_type": "treasury_trade", "resource_id": "9e1cf1f2", "ip_address": "", "user_agent": "", "details": {"position_id": "9e1cf1f2", "token": "TOK0", "token_mint": "TOKEN0_MINT", "amount_usd": 12.5, "entry_price": 100.0, "tp_price": 118.0, "sl_price": 88.0, "sentiment_grade": "B", "dry_run": true}, "success": true, "error_message": "", "timestamp_iso": "2026-01-19T21:00:25.364463"}
{"timestamp": 1768878025.5330849, "event_type": "trade_execute", "actor_id": "12345", "action": "OPEN_POSITION", "resource_type": "treasury_trade", "resource_id": "44df2631", "ip_address": "", "user_agent": "", "details": {"position_id": "44df2631", "token": "TOK1", "token_mint": "TOKEN1_MINT", "amount_usd": 12.5, "entry_price": 100.0, "tp_price": 118.0, "sl_price": 88.0, "sentiment_grade": "B", "dry_run": true}, "success": true, "error_message": "", "timestamp_iso": "2026-01-19T21:00:25.533085"}
{"timestamp": 1768878025.5711443, "event_type": "security_alert", "actor_id": "12345", "action": "OPEN_POSITION_REJECTED", "resource_type": "treasury_trade", "resource_id": "TOK2", "ip_address": "", "user_agent": "", "details": {"token": "TOK2", "reason": "max_positions"}, "success": false, "error_message": "", "timestamp_iso": "2026-01-19T21:00:25.571144"}
{"timestamp": 1768878027.1694376, "event_type": "trade_execute", "actor_id": "12345", "action": "OPEN_POSITION", "resource_type": "treasury_trade", "resource_id": "847ac055", "ip_address": "", "user_agent": "", "details": {"position_id": "847ac055", "token": "SOL", "token_mint": "SOL_MINT", "amount_usd": 25.0, "entry_price": 100.0, "tp_price": 118.0, "sl_price": 88.0, "sentiment_grade": "B", "dry_run": true}, "success": true, "error_message": "", "timestamp_iso": "2026-01-19T21:00:27.169438"}
{"timestamp": 1768878027.3124902, "event_type": "trade_execute", "actor_id": "12345", "action": "CLOSE_POSITION", "resource_type": "treasury_trade", "resource_id": "847ac055", "ip_address": "", "user_agent": "", "details": {"position_id": "847ac055", "token": "SOL", "entry_price": 100.0, "exit_price": 100.0, "pnl_usd": 0.0, "pnl_pct": 0.0, "reason": "Manual close", "dry_run": true}, "success": true, "error_message": "", "timestamp_iso": "2026-01-19T21:00:27.312490"}
{"timestamp": 1768878027.3651307, "event_type": "security_alert", "actor_id": "12345", "action": "CLOSE_POSITION_REJECTED", "resource_type": "treasury_trade", "resource_id": "847ac055", "ip_address": "", "user_agent": "", "details": {"position_id": "847ac055", "reason": "not_found"}, "success": false, "error_message": "", "timestamp_iso": "2026-01-19T21:00:27.365131"}
{"timestamp": 1768979490.4867373, "event_type": "trade_execute", "actor_id": "123456", "action": "OPEN_POSITION", "resource_type": "treasury_trade", "resource_id": "6bc1872a", "ip_address": "", "user_agent": "", "details": {"position_id": "6bc1872a", "token": "SOL", "token_mint": "So11111111111111111111111111111111111111112", "amount_usd": 50.0, "entry_price": 128.16, "tp_price": 153.792, "sl_price": 115.344, "sentiment_grade": "B+", "dry_run": true}, "success": true, "error_message": "", "timestamp_iso": "2026-01-21T01:11:30.486737"}
{"timestamp": 1768980921.5915706, "event_type": "security_alert", "actor_id": "12345", "action": "OPEN_POSITION_REJECTED", "resource_type": "treasury_trade", "resource_id": "SOL", "ip_address": "", "user_agent": "", "details": {"token": "SOL", "reason": "risk_limit", "alert": "POSITION_SIZE exceeded: 100.00 >= 100.00", "amount_usd": 100.0}, "success": false, "error_message": "", "timestamp_iso": "2026-01-21T01:35:21.591571"}
{"timestamp": 1768980921.7174962, "event_type": "trade_execute", "actor_id": "12345", "action": "OPEN_POSITION", "resource_type": "treasury_trade", "resource_id": "d0548f47", "ip_address": "", "user_agent": "", "details": {"position_id": "d0548f47", "token": "SOL0", "token_mint": "UniqueEstablishedMint0", "amount_usd": 2.5, "entry_price": 100.0, "tp_price": 118.0, "sl_price": 88.0, "sentiment_grade": "B", "dry_run": true}, "success": true, "error_message": "", "timestamp_iso": "2026-01-21T01:35:21.717496"}
{"timestamp": 1768980921.7508848, "event_type": "trade_execute", "actor_id": "12345", "action": "OPEN_POSITION", "resource_type": "treasury_trade", "resource_id": "c9578e9b", "ip_address": "", "user_agent": "", "details": {"position_id": "c9578e9b", "token": "SOL1", "token_mint": "UniqueEstablishedMint1", "amount_usd": 2.5, "entry_price": 100.0, "tp_price": 118.0, "sl_price": 88.0, "sentiment_grade": "B", "dry_run": true}, "success": true, "error_message": "", "timestamp_iso": "2026-01-21T01:35:21.750885"}
{"timestamp": 1768980921.787843, "event_type": "trade_execute", "actor_id": "12345", "action": "OPEN_POSITION", "resource_type": "treasury_trade", "resource_id": "a2cb98c2", "ip_address": "", "user_agent": "", "details": {"position_id": "a2cb98c2", "token": "SOL2", "token_mint": "UniqueEstablishedMint2", "amount_usd": 2.5, "entry_price": 100.0, "tp_price": 118.0, "sl_price": 88.0, "sentiment_grade": "B", "dry_run": true}, "success": true, "error_message": "", "timestamp_iso": "2026-01-21T01:35:21.787843"}
{"timestamp": 1768980921.8327532, "event_type": "trade_execute", "actor_id": "12345", "action": "OPEN_POSITION", "resource_type": "treasury_trade", "resource_id": "113c1e2b", "ip_address": "", "user_agent": "", "details": {"position_id": "113c1e2b", "token": "SOL3", "token_mint": "UniqueEstablishedMint3", "amount_usd": 2.5, "entry_price": 100.0, "tp_price": 118.0, "sl_price": 88.0, "sentiment_grade": "B", "dry_run": true}, "success": true, "error_message": "", "timestamp_iso": "2026-01-21T01:35:21.832753"}
{"timestamp": 1768980921.8700805, "event_type": "trade_execute", "actor_id": "12345", "action": "OPEN_POSITION", "resource_type": "treasury_trade", "resource_id": "bdecbbcb", "ip_address": "", "user_agent": "", "details": {"position_id": "bdecbbcb", "token": "SOL4", "token_mint": "UniqueEstablishedMint4", "amount_usd": 2.5, "entry_price": 100.0, "tp_price": 118.0, "sl_price": 88.0, "sentiment_grade": "B", "dry_run": true}, "success": true, "error_message": "", "timestamp_iso": "2026-01-21T01:35:21.870080"}
{"timestamp": 1768980921.9076147, "event_type": "trade_execute", "actor_id": "12345", "action": "OPEN_POSITION", "resource_type": "treasury_trade", "resource_id": "6e04c0b9", "ip_address": "", "user_agent": "", "details": {"position_id": "6e04c0b9", "token": "SOL5", "token_mint": "UniqueEstablishedMint5", "amount_usd": 2.5, "entry_price": 100.0, "tp_price": 118.0, "sl_price": 88.0, "sentiment_grade": "B", "dry_run": true}, "success": true, "error_message": "", "timestamp_iso": "2026-01-21T01:35:21.907615"}
{"timestamp": 1768980921.945657, "event_type": "trade_execute", "actor_id": "12345", "action": "OPEN_POSITION", "resource_type": "treasury_trade", "resource_id": "839c47ff", "ip_address": "", "user_agent": "", "details": {"position_id": "839c47ff", "token": "SOL6", "token_mint": "UniqueEstablishedMint6", "amount_usd": 2.5, "entry_price": 100.0, "tp_price": 118.0, "sl_price": 88.0, "sentiment_grade": "B", "dry_run": true}, "success": true, "error_message": "", "timestamp_iso": "2026-01-21T01:35:21.945657"}
{"timestamp": 1768980921.995659, "event_type": "trade_execute", "actor_id": "12345", "action": "OPEN_POSITION", "resource_type": "treasury_trade", "resource_id": "c3b71983", "ip_address": "", "user_agent": "", "details": {"position_id": "c3b71983", "token": "SOL7", "token_mint": "UniqueEstablishedMint7", "amount_usd": 2.5, "entry_price": 100.0, "tp_price": 118.0, "sl_price": 88.0, "sentiment_grade": "B", "dry_run": true}, "success": true, "error_message": "", "timestamp_iso": "2026-01-21T01:35:21.995659"}
{"timestamp": 1768980922.0468996, "event_type": "trade_execute", "actor_id": "12345", "action": "OPEN_POSITION", "resource_type": "treasury_trade", "resource_id": "8a8678be", "ip_address": "", "user_agent": "", "details": {"position_id": "8a8678be", "token": "SOL8", "token_mint": "UniqueEstablishedMint8", "amount_usd": 2.5, "entry_price": 100.0, "tp_price": 118.0, "sl_price": 88.0, "sentiment_grade": "B", "dry_run": true}, "success": true, "error_message": "", "timestamp_iso": "2026-01-21T01:35:22.046900"}
{"timestamp": 1768980922.11655, "event_type": "trade_execute", "actor_id": "12345", "action": "OPEN_POSITION", "resource_type": "treasury_trade", "resource_id": "77fa2bd0", "ip_address": "", "user_agent": "", "details": {"position_id": "77fa2bd0", "token": "SOL9", "token_mint": "UniqueEstablishedMint9", "amount_usd": 2.5, "entry_price": 100.0, "tp_price": 118.0, "sl_price": 88.0, "sentiment_grade": "B", "dry_run": true}, "success": true, "error_message": "", "timestamp_iso": "2026-01-21T01:35:22.116550"}
{"timestamp": 1768980922.1466866, "event_type": "security_alert", "actor_id": "12345", "action": "OPEN_POSITION_REJECTED", "resource_type": "treasury_trade", "resource_id": "EXCESS", "ip_address": "", "user_agent": "", "details": {"token": "EXCESS", "reason": "max_positions"}, "success": false, "error_message": "", "timestamp_iso": "2026-01-21T01:35:22.146687"}
{"timestamp": 1768980922.232592, "event_type": "security_alert", "actor_id": "12345", "action": "OPEN_POSITION_REJECTED", "resource_type": "treasury_trade", "resource_id": "SOL", "ip_address": "", "user_agent": "", "details": {"token": "SOL", "reason": "risk_limit", "alert": "POSITION_SIZE exceeded: 100.00 >= 100.00", "amount_usd": 100.0}, "success": false, "error_message": "", "timestamp_iso": "2026-01-21T01:35:22.232592"}
{"timestamp": 1768980922.3812883, "event_type": "security_alert", "actor_id": "12345", "action": "OPEN_POSITION_REJECTED", "resource_type": "treasury_trade", "resource_id": "SOL", "ip_address": "", "user_agent": "", "details": {"token": "SOL", "reason": "risk_limit", "alert": "POSITION_SIZE exceeded: 100.00 >= 100.00", "amount_usd": 100.0}, "success": false, "error_message": "", "timestamp_iso": "2026-01-21T01:35:22.381288"}
{"timestamp": 1768980922.4498043, "event_type": "security_alert", "actor_id": "12345", "action": "OPEN_POSITION_REJECTED", "resource_type": "treasury_trade", "resource_id": "SOL", "ip_address": "", "user_agent": "", "details": {"token": "SOL", "reason": "risk_limit", "alert": "POSITION_SIZE exceeded: 100.00 >= 100.00", "amount_usd": 100.0}, "success": false, "error_message": "", "timestamp_iso": "2026-01-21T01:35:22.449804"}
{"timestamp": 1768980922.5283718, "event_type": "security_alert", "actor_id": "12345", "action": "OPEN_POSITION_REJECTED", "resource_type": "treasury_trade", "resource_id": "JUP", "ip_address": "", "user_agent": "", "details": {"token": "JUP", "reason": "risk_limit", "alert": "POSITION_SIZE exceeded: 100.00 >= 100.00", "amount_usd": 100.0}, "success": false, "error_message": "", "timestamp_iso": "2026-01-21T01:35:22.528372"}
{"timestamp": 1768980922.629675, "event_type": "security_alert", "actor_id": "12345", "action": "OPEN_POSITION_REJECTED", "resource_type": "treasury_trade", "resource_id": "SOL", "ip_address": "", "user_agent": "", "details": {"token": "SOL", "reason": "risk_limit", "alert": "POSITION_SIZE exceeded: 100.00 >= 100.00", "amount_usd": 100.0}, "success": false, "error_message": "", "timestamp_iso": "2026-01-21T01:35:22.629675"}
{"timestamp": 1768980922.7201724, "event_type": "security_alert", "actor_id": "12345", "action": "OPEN_POSITION_REJECTED", "resource_type": "treasury_trade", "resource_id": "SOL", "ip_address": "", "user_agent": "", "details": {"token": "SOL", "reason": "risk_limit", "alert": "POSITION_SIZE exceeded: 100.00 >= 100.00", "amount_usd": 100.0}, "success": false, "error_message": "", "timestamp_iso": "2026-01-21T01:35:22.720172"}
{"timestamp": 1768980922.803998, "event_type": "security_alert", "actor_id": "12345", "action": "OPEN_POSITION_REJECTED", "resource_type": "treasury_trade", "resource_id": "SOL", "ip_address": "", "user_agent": "", "details": {"token": "SOL", "reason": "risk_limit", "alert": "POSITION_SIZE exceeded: 100.00 >= 100.00", "amount_usd": 100.0}, "success": false, "error_message": "", "timestamp_iso": "2026-01-21T01:35:22.803998"}
{"timestamp": 1768980922.9045627, "event_type": "security_alert", "actor_id": "12345", "action": "OPEN_POSITION_REJECTED", "resource_type": "treasury_trade", "resource_id": "JUP", "ip_address": "", "user_agent": "", "details": {"token": "JUP", "reason": "risk_limit", "alert": "POSITION_SIZE exceeded: 100.00 >= 100.00", "amount_usd": 100.0}, "success": false, "error_message": "", "timestamp_iso": "2026-01-21T01:35:22.904563"}
{"timestamp": 1768980922.9769518, "event_type": "security_alert", "actor_id": "12345", "action": "OPEN_POSITION_REJECTED", "resource_type": "treasury_trade", "resource_id": "SOL", "ip_address": "", "user_agent": "", "details": {"token": "SOL", "reason": "risk_limit", "alert": "POSITION_SIZE exceeded: 100.00 >= 100.00", "amount_usd": 100.0}, "success": false, "error_message": "", "timestamp_iso": "2026-01-21T01:35:22.976952"}
{"timestamp": 1768980923.0737758, "event_type": "security_alert", "actor_id": "12345", "action": "OPEN_POSITION_REJECTED", "resource_type": "treasury_trade", "resource_id": "SOL", "ip_address": "", "user_agent": "", "details": {"token": "SOL", "reason": "risk_limit", "alert": "POSITION_SIZE exceeded: 100.00 >= 100.00", "amount_usd": 100.0}, "success": false, "error_message": "", "timestamp_iso": "2026-01-21T01:35:23.073776"}
{"timestamp": 1768980923.1262324, "event_type": "security_alert", "actor_id": "12345", "action": "OPEN_POSITION_REJECTED", "resource_type": "treasury_trade", "resource_id": "SOL", "ip_address": "", "user_agent": "", "details": {"token": "SOL", "reason": "amount_exceeds_max", "amount_usd": 100.0, "max_trade_usd": 50.0}, "success": false, "error_message": "", "timestamp_iso": "2026-01-21T01:35:23.126232"}
{"timestamp": 1768980923.23344, "event_type": "trade_execute", "actor_id": "12345", "action": "OPEN_POSITION", "resource_type": "treasury_trade", "resource_id": "35b3d475", "ip_address": "", "user_agent": "", "details": {"position_id": "35b3d475", "token": "SOL", "token_mint": "So11111111111111111111111111111111111111112", "amount_usd": 50.0, "entry_price": 100.0, "tp_price": 130.0, "sl_price": 92.0, "sentiment_grade": "A", "dry_run": true}, "success": true, "error_message": "", "timestamp_iso": "2026-01-21T01:35:23.233440"}
{"timestamp": 1768980923.2734156, "event_type": "security_alert", "actor_id": "12345", "action": "OPEN_POSITION_REJECTED", "resource_type": "treasury_trade", "resource_id": "SOL", "ip_address": "", "user_agent": "", "details": {"token": "SOL", "reason": "risk_limit", "alert": "POSITION_SIZE exceeded: 100.00 >= 100.00", "amount_usd": 100.0}, "success": false, "error_message": "", "timestamp_iso": "2026-01-21T01:35:23.273416"}
{"timestamp": 1768981187.869044, "event_type": "security_alert", "actor_id": "12345", "action": "OPEN_POSITION_REJECTED", "resource_type": "treasury_trade", "resource_id": "SOL", "ip_address": "", "user_agent": "", "details": {"token": "SOL", "reason": "risk_limit", "alert": "POSITION_SIZE exceeded: 100.00 >= 100.00", "amount_usd": 100.0}, "success": false, "error_message": "", "timestamp_iso": "2026-01-21T01:39:47.869044"}
{"timestamp": 1768981187.9879858, "event_type": "trade_execute", "actor_id": "12345", "action": "OPEN_POSITION", "resource_type": "treasury_trade", "resource_id": "e6551cf5", "ip_address": "", "user_agent": "", "details": {"position_id": "e6551cf5", "token": "SOL0", "token_mint": "UniqueEstablishedMint0", "amount_usd": 2.5, "entry_price": 100.0, "tp_price": 118.0, "sl_price": 88.0, "sentiment_grade": "B", "dry_run": true}, "success": true, "error_message": "", "timestamp_iso": "2026-01-21T01:39:47.987986"}
{"timestamp": 1768981188.0187936, "event_type": "trade_execute", "actor_id": "12345", "action": "OPEN_POSITION", "resource_type": "treasury_trade", "resource_id": "af2ea6ba", "ip_address": "", "user_agent": "", "details": {"position_id": "af2ea6ba", "token": "SOL1", "token_mint": "UniqueEstablishedMint1", "amount_usd": 2.5, "entry_price": 100.0, "tp_price": 118.0, "sl_price": 88.0, "sentiment_grade": "B", "dry_run": true}, "success": true, "error_message": "", "timestamp_iso": "2026-01-21T01:39:48.018794"}
{"timestamp": 1768981188.0534983, "event_type": "trade_execute", "actor_id": "12345", "action": "OPEN_POSITION", "resource_type": "treasury_trade", "resource_id": "c27482b3", "ip_address": "", "user_agent": "", "details": {"position_id": "c27482b3", "token": "SOL2", "token_mint": "UniqueEstablishedMint2", "amount_usd": 2.5, "entry_price": 100.0, "tp_price": 118.0, "sl_price": 88.0, "sentiment_grade": "B", "dry_run": true}, "success": true, "error_message": "", "timestamp_iso": "2026-01-21T01:39:48.053498"}
{"timestamp": 1768981188.086464, "event_type": "trade_execute", "actor_id": "12345", "action": "OPEN_POSITION", "resource_type": "treasury_trade", "resource_id": "37e49251", "ip_address": "", "user_agent": "", "details": {"position_id": "37e49251", "token": "SOL3", "token_mint": "UniqueEstablishedMint3", "amount_usd": 2.5, "entry_price": 100.0, "tp_price": 118.0, "sl_price": 88.0, "sentiment_grade": "B", "dry_run": true}, "success": true, "error_message": "", "timestamp_iso": "2026-01-21T01:39:48.086464"}
{"timestamp": 1768981188.1175094, "event_type": "trade_execute", "actor_id": "12345", "action": "OPEN_POSITION", "resource_type": "treasury_trade", "resource_id": "d654eb84", "ip_address": "", "user_agent": "", "details": {"position_id": "d654eb84", "token": "SOL4", "token_mint": "UniqueEstablishedMint4", "amount_usd": 2.5, "entry_price": 100.0, "tp_price": 118.0, "sl_price": 88.0, "sentiment_grade": "B", "dry_run": true}, "success": true, "error_message": "", "timestamp_iso": "2026-01-21T01:39:48.117509"}
{"timestamp": 1768981188.1494372, "event_type": "trade_execute", "actor_id": "12345", "action": "OPEN_POSITION", "resource_type": "treasury_trade", "resource_id": "30808be7", "ip_address": "", "user_agent": "", "details": {"position_id": "30808be7", "token": "SOL5", "token_mint": "UniqueEstablishedMint5", "amount_usd": 2.5, "entry_price": 100.0, "tp_price": 118.0, "sl_price": 88.0, "sentiment_grade": "B", "dry_run": true}, "success": true, "error_message": "", "timestamp_iso": "2026-01-21T01:39:48.149437"}
{"timestamp": 1768981188.179642, "event_type": "trade_execute", "actor_id": "12345", "action": "OPEN_POSITION", "resource_type": "treasury_trade", "resource_id": "2c230a28", "ip_address": "", "user_agent": "", "details": {"position_id": "2c230a28", "token": "SOL6", "token_mint": "UniqueEstablishedMint6", "amount_usd": 2.5, "entry_price": 100.0, "tp_price": 118.0, "sl_price": 88.0, "sentiment_grade": "B", "dry_run": true}, "success": true, "error_message": "", "timestamp_iso": "2026-01-21T01:39:48.179642"}
{"timestamp": 1768981188.210008, "event_type": "trade_execute", "actor_id": "12345", "action": "OPEN_POSITION", "resource_type": "treasury_trade", "resource_id": "08e41b8b", "ip_address": "", "user_agent": "", "details": {"position_id": "08e41b8b", "token": "SOL7", "token_mint": "UniqueEstablishedMint7", "amount_usd": 2.5, "entry_price": 100.0, "tp_price": 118.0, "sl_price": 88.0, "sentiment_grade": "B", "dry_run": true}, "success": true, "error_message": "", "timestamp_iso": "2026-01-21T01:39:48.210008"}
{"timestamp": 1768981188.2376556, "event_type": "trade_execute", "actor_id": "12345", "action": "OPEN_POSITION", "resource_type": "treasury_trade", "resource_id": "e37332a1", "ip_address": "", "user_agent": "", "details": {"position_id": "e37332a1", "token": "SOL8", "token_mint": "UniqueEstablishedMint8", "amount_usd": 2.5, "entry_price": 100.0, "tp_price": 118.0, "sl_price": 88.0, "sentiment_grade": "B", "dry_run": true}, "success": true, "error_message": "", "timestamp_iso": "2026-01-21T01:39:48.237656"}
{"timestamp": 1768981188.2650988, "event_type": "trade_execute", "actor_id": "12345", "action": "OPEN_POSITION", "resource_type": "treasury_trade", "resource_id": "33070fed", "ip_address": "", "user_agent": "", "details": {"position_id": "33070fed", "token": "SOL9", "token_mint": "UniqueEstablishedMint9", "amount_usd": 2.5, "entry_price": 100.0, "tp_price": 118.0, "sl_price": 88.0, "sentiment_grade": "B", "dry_run": true}, "success": true, "error_message": "", "timestamp_iso": "2026-01-21T01:39:48.265099"}
{"timestamp": 1768981188.2857578, "event_type": "security_alert", "actor_id": "12345", "action": "OPEN_POSITION_REJECTED", "resource_type": "treasury_trade", "resource_id": "EXCESS", "ip_address": "", "user_agent": "", "details": {"token": "EXCESS", "reason": "max_positions"}, "success": false, "error_message": "", "timestamp_iso": "2026-01-21T01:39:48.285758"}
{"timestamp": 1768981188.3192296, "event_type": "security_alert", "actor_id": "12345", "action": "OPEN_POSITION_REJECTED", "resource_type": "treasury_trade", "resource_id": "SOL", "ip_address": "", "user_agent": "", "details": {"token": "SOL", "reason": "risk_limit", "alert": "POSITION_SIZE exceeded: 100.00 >= 100.00", "amount_usd": 100.0}, "success": false, "error_message": "", "timestamp_iso": "2026-01-21T01:39:48.319230"}
{"timestamp": 1768981188.3680675, "event_type": "security_alert", "actor_id": "12345", "action": "OPEN_POSITION_REJECTED", "resource_type": "treasury_trade", "resource_id": "SOL", "ip_address": "", "user_agent": "", "details": {"token": "SOL", "reason": "risk_limit", "alert": "POSITION_SIZE exceeded: 100.00 >= 100.00", "amount_usd": 100.0}, "success": false, "error_message": "", "timestamp_iso": "2026-01-21T01:39:48.368068"}
{"timestamp": 1768981188.4074917, "event_type": "security_alert", "actor_id": "12345", "action": "OPEN_POSITION_REJECTED", "resource_type": "treasury_trade", "resource_id": "SOL", "ip_address": "", "user_agent": "", "details": {"token": "SOL", "reason": "risk_limit", "alert": "POSITION_SIZE exceeded: 100.00 >= 100.00", "amount_usd": 100.0}, "success": false, "error_message": "", "timestamp_iso": "2026-01-21T01:39:48.407492"}
{"timestamp": 1768981188.4485888, "event_type": "security_alert", "actor_id": "12345", "action": "OPEN_POSITION_REJECTED", "resource_type": "treasury_trade", "resource_id": "JUP", "ip_address": "", "user_agent": "", "details": {"token": "JUP", "reason": "risk_limit", "alert": "POSITION_SIZE exceeded: 100.00 >= 100.00", "amount_usd": 100.0}, "success": false, "error_message": "", "timestamp_iso": "2026-01-21T01:39:48.448589"}
{"timestamp": 1768981188.4824524, "event_type": "security_alert", "actor_id": "12345", "action": "OPEN_POSITION_REJECTED", "resource_type": "treasury_trade", "resource_id": "SOL", "ip_address": "", "user_agent": "", "details": {"token": "SOL", "reason": "risk_limit", "alert": "POSITION_SIZE exceeded: 100.00 >= 100.00", "amount_usd": 100.0}, "success": false, "error_message": "", "timestamp_iso": "2026-01-21T01:39:48.482452"}
{"timestamp": 1768981188.5134058, "event_type": "security_alert", "actor_id": "12345", "action": "OPEN_POSITION_REJECTED", "resource_type": "treasury_trade", "resource_id": "SOL", "ip_address": "", "user_agent": "", "details": {"token": "SOL", "reason": "risk_limit", "alert": "POSITION_SIZE exceeded: 100.00 >= 100.00", "amount_usd": 100.0}, "success": false, "error_message": "", "timestamp_iso": "2026-01-21T01:39:48.513406"}
{"timestamp": 1768981188.551677, "event_type": "security_alert", "actor_id": "12345", "action": "OPEN_POSITION_REJECTED", "resource_type": "treasury_trade", "resource_id": "SOL", "ip_address": "", "user_agent": "", "details": {"token": "SOL", "reason": "risk_limit", "alert": "POSITION_SIZE exceeded: 100.00 >= 100.00", "amount_usd": 100.0}, "success": false, "error_message": "", "timestamp_iso": "2026-01-21T01:39:48.551677"}
{"timestamp": 1768981188.5922356, "event_type": "security_alert", "actor_id": "12345", "action": "OPEN_POSITION_REJECTED", "resource_type": "treasury_trade", "resource_id": "JUP", "ip_address": "", "user_agent": "", "details": {"token": "JUP", "reason": "risk_limit", "alert": "POSITION_SIZE exceeded: 100.00 >= 100.00", "amount_usd": 100.0}, "success": false, "error_message": "", "timestamp_iso": "2026-01-21T01:39:48.592236"}
{"timestamp": 1768981188.6276777, "event_type": "security_alert", "actor_id": "12345", "action": "OPEN_POSITION_REJECTED", "resource_type": "treasury_trade", "resource_id": "SOL", "ip_address": "", "user_agent": "", "details": {"token": "SOL", "reason": "risk_limit", "alert": "POSITION_SIZE exceeded: 100.00 >= 100.00", "amount_usd": 100.0}, "success": false, "error_message": "", "timestamp_iso": "2026-01-21T01:39:48.627678"}
{"timestamp": 1768981188.6644385, "event_type": "security_alert", "actor_id": "12345", "action": "OPEN_POSITION_REJECTED", "resource_type": "treasury_trade", "resource_id": "SOL", "ip_address": "", "user_agent": "", "details": {"token": "SOL", "reason": "risk_limit", "alert": "POSITION_SIZE exceeded: 100.00 >= 100.00", "amount_usd": 100.0}, "success": false, "error_message": "", "timestamp_iso": "2026-01-21T01:39:48.664438"}
{"timestamp": 1768981188.6877563, "event_type": "security_alert", "actor_id": "12345", "action": "OPEN_POSITION_REJECTED", "resource_type": "treasury_trade", "resource_id": "SOL", "ip_address": "", "user_agent": "", "details": {"token": "SOL", "reason": "amount_exceeds_max", "amount_usd": 100.0, "max_trade_usd": 50.0}, "success": false, "error_message": "", "timestamp_iso": "2026-01-21T01:39:48.687756"}
{"timestamp": 1768981188.7560043, "event_type": "trade_execute", "actor_id": "12345", "action": "OPEN_POSITION", "resource_type": "treasury_trade", "resource_id": "0ba198fc", "ip_address": "", "user_agent": "", "details": {"position_id": "0ba198fc", "token": "SOL", "token_mint": "So11111111111111111111111111111111111111112", "amount_usd": 50.0, "entry_price": 100.0, "tp_price": 130.0, "sl_price": 92.0, "sentiment_grade": "A", "dry_run": true}, "success": true, "error_message": "", "timestamp_iso": "2026-01-21T01:39:48.756004"}
{"timestamp": 1768981188.7815557, "event_type": "security_alert", "actor_id": "12345", "action": "OPEN_POSITION_REJECTED", "resource_type": "treasury_trade", "resource_id": "SOL", "ip_address": "", "user_agent": "", "details": {"token": "SOL", "reason": "risk_limit", "alert": "POSITION_SIZE exceeded: 100.00 >= 100.00", "amount_usd": 100.0}, "success": false, "error_message": "", "timestamp_iso": "2026-01-21T01:39:48.781556"}
{"timestamp": 1768983241.2995484, "event_type": "trade_execute", "actor_id": "12345", "action": "OPEN_POSITION", "resource_type": "treasury_trade", "resource_id": "473c9c48", "ip_address": "", "user_agent": "", "details": {"position_id": "473c9c48", "token": "SOL", "token_mint": "SOL_MINT", "amount_usd": 25.0, "entry_price": 100.0, "tp_price": 118.0, "sl_price": 88.0, "sentiment_grade": "B", "dry_run": true}, "success": true, "error_message": "", "timestamp_iso": "2026-01-21T02:14:01.299548"}
{"timestamp": 1768983241.3395345, "event_type": "security_alert", "actor_id": "99999", "action": "CLOSE_POSITION_REJECTED", "resource_type": "treasury_trade", "resource_id": "473c9c48", "ip_address": "", "user_agent": "", "details": {"position_id": "473c9c48", "reason": "unauthorized"}, "success": false, "error_message": "", "timestamp_iso": "2026-01-21T02:14:01.339535"}
{"timestamp": 1768983241.4423995, "event_type": "trade_execute", "actor_id": "12345", "action": "OPEN_POSITION", "resource_type": "treasury_trade", "resource_id": "2c4064e0", "ip_address": "", "user_agent": "", "details": {"position_id": "2c4064e0", "token": "TOK0", "token_mint": "TOKEN0_MINT", "amount_usd": 12.5, "entry_price": 100.0, "tp_price": 118.0, "sl_price": 88.0, "sentiment_grade": "B", "dry_run": true}, "success": true, "error_message": "", "timestamp_iso": "2026-01-21T02:14:01.442400"}
{"timestamp": 1768983241.510594, "event_type": "trade_execute", "actor_id": "12345", "action": "OPEN_POSITION", "resource_type": "treasury_trade", "resource_id": "2fe8e3eb", "ip_address": "", "user_agent": "", "details": {"position_id": "2fe8e3eb", "token": "TOK1", "token_mint": "TOKEN1_MINT", "amount_usd": 12.5, "entry_price": 100.0, "tp_price": 118.0, "sl_price": 88.0, "sentiment_grade": "B", "dry_run": true}, "success": true, "error_message": "", "timestamp_iso": "2026-01-21T02:14:01.510594"}
{"timestamp": 1768983241.552217, "event_type": "security_alert", "actor_id": "12345", "action": "OPEN_POSITION_REJECTED", "resource_type": "treasury_trade", "resource_id": "TOK2", "ip_address": "", "user_agent": "", "details": {"token": "TOK2", "reason": "max_positions"}, "success": false, "error_message": "", "timestamp_iso": "2026-01-21T02:14:01.552217"}
{"timestamp": 1768983311.297924, "event_type": "security_alert", "actor_id": "12345", "action": "OPEN_POSITION_REJECTED", "resource_type": "treasury_trade", "resource_id": "SOL", "ip_address": "", "user_agent": "", "details": {"token": "SOL", "reason": "risk_limit", "alert": "POSITION_SIZE exceeded: 100.00 >= 100.00", "amount_usd": 100.0}, "success": false, "error_message": "", "timestamp_iso": "2026-01-21T02:15:11.297924"}
{"timestamp": 1768983311.6252656, "event_type": "trade_execute", "actor_id": "12345", "action": "OPEN_POSITION", "resource_type": "treasury_trade", "resource_id": "4e33f7d4", "ip_address": "", "user_agent": "", "details": {"position_id": "4e33f7d4", "token": "SOL0", "token_mint": "UniqueEstablishedMint0", "amount_usd": 2.5, "entry_price": 100.0, "tp_price": 118.0, "sl_price": 88.0, "sentiment_grade": "B", "dry_run": true}, "success": true, "error_message": "", "timestamp_iso": "2026-01-21T02:15:11.625266"}
{"timestamp": 1768983311.6850147, "event_type": "trade_execute", "actor_id": "12345", "action": "OPEN_POSITION", "resource_type": "treasury_trade", "resource_id": "81e2503a", "ip_address": "", "user_agent": "", "details": {"position_id": "81e2503a", "token": "SOL1", "token_mint": "UniqueEstablishedMint1", "amount_usd": 2.5, "entry_price": 100.0, "tp_price": 118.0, "sl_price": 88.0, "sentiment_grade": "B", "dry_run": true}, "success": true, "error_message": "", "timestamp_iso": "2026-01-21T02:15:11.685015"}
{"timestamp": 1768983311.739369, "event_type": "trade_execute", "actor_id": "12345", "action": "OPEN_POSITION", "resource_type": "treasury_trade", "resource_id": "e7e55bb5", "ip_address": "", "user_agent": "", "details": {"position_id": "e7e55bb5", "token": "SOL2", "token_mint": "UniqueEstablishedMint2", "amount_usd": 2.5, "entry_price": 100.0, "tp_price": 118.0, "sl_price": 88.0, "sentiment_grade": "B", "dry_run": true}, "success": true, "error_message": "", "timestamp_iso": "2026-01-21T02:15:11.739369"}
{"timestamp": 1768983311.7922497, "event_type": "trade_execute", "actor_id": "12345", "action": "OPEN_POSITION", "resource_type": "treasury_trade", "resource_id": "6c5f8356", "ip_address": "", "user_agent": "", "details": {"position_id": "6c5f8356", "token": "SOL3", "token_mint": "UniqueEstablishedMint3", "amount_usd": 2.5, "entry_price": 100.0, "tp_price": 118.0, "sl_price": 88.0, "sentiment_grade": "B", "dry_run": true}, "success": true, "error_message": "", "timestamp_iso": "2026-01-21T02:15:11.792250"}
{"timestamp": 1768983311.8661976, "event_type": "trade_execute", "actor_id": "12345", "action": "OPEN_POSITION", "resource_type": "treasury_trade", "resource_id": "3fd7fd2b", "ip_address": "", "user_agent": "", "details": {"position_id": "3fd7fd2b", "token": "SOL4", "token_mint": "UniqueEstablishedMint4", "amount_usd": 2.5, "entry_price": 100.0, "tp_price": 118.0, "sl_price": 88.0, "sentiment_grade": "B", "dry_run": true}, "success": true, "error_message": "", "timestamp_iso": "2026-01-21T02:15:11.866198"}
{"timestamp": 1768983311.9204707, "event_type": "trade_execute", "actor_id": "12345", "action": "OPEN_POSITION", "resource_type": "treasury_trade", "resource_id": "cd0176e4", "ip_address": "", "user_agent": "", "details": {"position_id": "cd0176e4", "token": "SOL5", "token_mint": "UniqueEstablishedMint5", "amount_usd": 2.5, "entry_price": 100.0, "tp_price": 118.0, "sl_price": 88.0, "sentiment_grade": "B", "dry_run": true}, "success": true, "error_message": "", "timestamp_iso": "2026-01-21T02:15:11.920471"}
{"timestamp": 1768983311.9744506, "event_type": "trade_execute", "actor_id": "12345", "action": "OPEN_POSITION", "resource_type": "treasury_trade", "resource_id": "6b4803f8", "ip_address": "", "user_agent": "", "details": {"position_id": "6b4803f8", "token": "SOL6", "token_mint": "UniqueEstablishedMint6", "amount_usd": 2.5, "entry_price": 100.0, "tp_price": 118.0, "sl_price": 88.0, "sentiment_grade": "B", "dry_run": true}, "success": true, "error_message": "", "timestamp_iso": "2026-01-21T02:15:11.974451"}
{"timestamp": 1768983312.0636525, "event_type": "trade_execute", "actor_id": "12345", "action": "OPEN_POSITION", "resource_type": "treasury_trade", "resource_id": "59460851", "ip_address": "", "user_agent": "", "details": {"position_id": "59460851", "token": "SOL7", "token_mint": "UniqueEstablishedMint7", "amount_usd": 2.5, "entry_price": 100.0, "tp_price": 118.0, "sl_price": 88.0, "sentiment_grade": "B", "dry_run": true}, "success": true, "error_message": "", "timestamp_iso": "2026-01-21T02:15:12.063653"}
{"timestamp": 1768983312.1409154, "event_type": "trade_execute", "actor_id": "12345", "action": "OPEN_POSITION", "resource_type": "treasury_trade", "resource_id": "b741b720", "ip_address": "", "user_agent": "", "details": {"position_id": "b741b720", "token": "SOL8", "token_mint": "UniqueEstablishedMint8", "amount_usd": 2.5, "entry_price": 100.0, "tp_price": 118.0, "sl_price": 88.0, "sentiment_grade": "B", "dry_run": true}, "success": true, "error_message": "", "timestamp_iso": "2026-01-21T02:15:12.140915"}
{"timestamp": 1768983312.204469, "event_type": "trade_execute", "actor_id": "12345", "action": "OPEN_POSITION", "resource_type": "treasury_trade", "resource_id": "97c21abe", "ip_address": "", "user_agent": "", "details": {"position_id": "97c21abe", "token": "SOL9", "token_mint": "UniqueEstablishedMint9", "amount_usd": 2.5, "entry_price": 100.0, "tp_price": 118.0, "sl_price": 88.0, "sentiment_grade": "B", "dry_run": true}, "success": true, "error_message": "", "timestamp_iso": "2026-01-21T02:15:12.204469"}
{"timestamp": 1768983312.2366736, "event_type": "security_alert", "actor_id": "12345", "action": "OPEN_POSITION_REJECTED", "resource_type": "treasury_trade", "resource_id": "EXCESS", "ip_address": "", "user_agent": "", "details": {"token": "EXCESS", "reason": "max_positions"}, "success": false, "error_message": "", "timestamp_iso": "2026-01-21T02:15:12.236674"}
{"timestamp": 1768983312.293354, "event_type": "security_alert", "actor_id": "12345", "action": "OPEN_POSITION_REJECTED", "resource_type": "treasury_trade", "resource_id": "SOL", "ip_address": "", "user_agent": "", "details": {"token": "SOL", "reason": "risk_limit", "alert": "POSITION_SIZE exceeded: 100.00 >= 100.00", "amount_usd": 100.0}, "success": false, "error_message": "", "timestamp_iso": "2026-01-21T02:15:12.293354"}
{"timestamp": 1768983312.45188, "event_type": "security_alert", "actor_id": "12345", "action": "OPEN_POSITION_REJECTED", "resource_type": "treasury_trade", "resource_id": "SOL", "ip_address": "", "user_agent": "", "details": {"token": "SOL", "reason": "risk_limit", "alert": "POSITION_SIZE exceeded: 100.00 >= 100.00", "amount_usd": 100.0}, "success": false, "error_message": "", "timestamp_iso": "2026-01-21T02:15:12.451880"}
{"timestamp": 1768983312.5234547, "event_type": "security_alert", "actor_id": "12345", "action": "OPEN_POSITION_REJECTED", "resource_type": "treasury_trade", "resource_id": "SOL", "ip_address": "", "user_agent": "", "details": {"token": "SOL", "reason": "risk_limit", "alert": "POSITION_SIZE exceeded: 100.00 >= 100.00", "amount_usd": 100.0}, "success": false, "error_message": "", "timestamp_iso": "2026-01-21T02:15:12.523455"}
{"timestamp": 1768983312.8058712, "event_type": "security_alert", "actor_id": "12345", "action": "OPEN_POSITION_REJECTED", "resource_type": "treasury_trade", "resource_id": "JUP", "ip_address": "", "user_agent": "", "details": {"token": "JUP", "reason": "risk_limit", "alert": "POSITION_SIZE exceeded: 100.00 >= 100.00", "amount_usd": 100.0}, "success": false, "error_message": "", "timestamp_iso": "2026-01-21T02:15:12.805871"}
{"timestamp": 1768983312.8931243, "event_type": "security_alert", "actor_id": "12345", "action": "OPEN_POSITION_REJECTED", "resource_type": "treasury_trade", "resource_id": "SOL", "ip_address": "", "user_agent": "", "details": {"token": "SOL", "reason": "risk_limit", "alert": "POSITION_SIZE exceeded: 100.00 >= 100.00", "amount_usd": 100.0}, "success": false, "error_message": "", "timestamp_iso": "2026-01-21T02:15:12.893124"}
{"timestamp": 1768983312.968933, "event_type": "security_alert", "actor_id": "12345", "action": "OPEN_POSITION_REJECTED", "resource_type": "treasury_trade", "resource_id": "SOL", "ip_address": "", "user_agent": "", "details": {"token": "SOL", "reason": "risk_limit", "alert": "POSITION_SIZE exceeded: 100.00 >= 100.00", "amount_usd": 100.0}, "success": false, "error_message": "", "timestamp_iso": "2026-01-21T02:15:12.968933"}
{"timestamp": 1768983313.0579004, "event_type": "security_alert", "actor_id": "12345", "action": "OPEN_POSITION_REJECTED", "resource_type": "treasury_trade", "resource_id": "SOL", "ip_address": "", "user_agent": "", "details": {"token": "SOL", "reason": "risk_limit", "alert": "POSITION_SIZE exceeded: 100.00 >= 100.00", "amount_usd": 100.0}, "success": false, "error_message": "", "timestamp_iso": "2026-01-21T02:15:13.057900"}
{"timestamp": 1768983313.1471927, "event_type": "security_alert", "actor_id": "12345", "action": "OPEN_POSITION_REJECTED", "resource_type": "treasury_trade", "resource_id": "JUP", "ip_address": "", "user_agent": "", "details": {"token": "JUP", "reason": "risk_limit", "alert": "POSITION_SIZE exceeded: 100.00 >= 100.00", "amount_usd": 100.0}, "success": false, "error_message": "", "timestamp_iso": "2026-01-21T02:15:13.147193"}
{"timestamp": 1768983313.2254558, "event_type": "security_alert", "actor_id": "12345", "action": "OPEN_POSITION_REJECTED", "resource_type": "treasury_trade", "resource_id": "SOL", "ip_address": "", "user_agent": "", "details": {"token": "SOL", "reason": "risk_limit", "alert": "POSITION_SIZE exceeded: 100.00 >= 100.00", "amount_usd": 100.0}, "success": false, "error_message": "", "timestamp_iso": "2026-01-21T02:15:13.225456"}
{"timestamp": 1768983313.3226478, "event_type": "security_alert", "actor_id": "12345", "action": "OPEN_POSITION_REJECTED", "resource_type": "treasury_trade", "resource_id": "SOL", "ip_address": "", "user_agent": "", "details": {"token": "SOL", "reason": "risk_limit", "alert": "POSITION_SIZE exceeded: 100.00 >= 100.00", "amount_usd": 100.0}, "success": false, "error_message": "", "timestamp_iso": "2026-01-21T02:15:13.322648"}
{"timestamp": 1768983313.3798358, "event_type": "security_alert", "actor_id": "12345", "action": "OPEN_POSITION_REJECTED", "resource_type": "treasury_trade", "resource_id": "SOL", "ip_address": "", "user_agent": "", "details": {"token": "SOL", "reason": "amount_exceeds_max", "amount_usd": 100.0, "max_trade_usd": 50.0}, "success": false, "error_message": "", "timestamp_iso": "2026-01-21T02:15:13.379836"}
{"timestamp": 1768983313.6994758, "event_type": "trade_execute", "actor_id": "12345", "action": "OPEN_POSITION", "resource_type": "treasury_trade", "resource_id": "81d7b910", "ip_address": "", "user_agent": "", "details": {"position_id": "81d7b910", "token": "SOL", "token_mint": "So11111111111111111111111111111111111111112", "amount_usd": 50.0, "entry_price": 100.0, "tp_price": 130.0, "sl_price": 92.0, "sentiment_grade": "A", "dry_run": true}, "success": true, "error_message": "", "timestamp_iso": "2026-01-21T02:15:13.699476"}
{"timestamp": 1768983313.7443056, "event_type": "security_alert", "actor_id": "12345", "action": "OPEN_POSITION_REJECTED", "resource_type": "treasury_trade", "resource_id": "SOL", "ip_address": "", "user_agent": "", "details": {"token": "SOL", "reason": "risk_limit", "alert": "POSITION_SIZE exceeded: 100.00 >= 100.00", "amount_usd": 100.0}, "success": false, "error_message": "", "timestamp_iso": "2026-01-21T02:15:13.744306"}
```

### root/supervisor.log (tail 200 lines)
Path: `supervisor.log`
```text
2026-01-17 13:19:48,959 - tg_bot.bot_core - ERROR - Traceback: "C:\Users\lucid\AppData\Local\Programs\Python\Python312\Lib\site-packages\telegram\request\_baserequest.py", line 198, in post
    result = await self._request_wrapper(
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "C:\Users\lucid\AppData\Local\Programs\Python\Python312\Lib\site-packages\telegram\request\_baserequest.py", line 375, in _request_wrapper
    raise exception
telegram.error.Conflict: Conflict: terminated by other getUpdates request; make sure that only one bot instance is running

2026-01-17 13:19:49,432 - bots.buy_tracker.monitor - INFO - Found 1 new transaction(s) to process
2026-01-17 13:19:58,698 - tg_bot.bot_core - ERROR - Bot error: Conflict: Conflict: terminated by other getUpdates request; make sure that only one bot instance is running
2026-01-17 13:19:58,700 - tg_bot.bot_core - ERROR - Traceback: "C:\Users\lucid\AppData\Local\Programs\Python\Python312\Lib\site-packages\telegram\request\_baserequest.py", line 198, in post
    result = await self._request_wrapper(
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "C:\Users\lucid\AppData\Local\Programs\Python\Python312\Lib\site-packages\telegram\request\_baserequest.py", line 375, in _request_wrapper
    raise exception
telegram.error.Conflict: Conflict: terminated by other getUpdates request; make sure that only one bot instance is running

2026-01-17 13:20:03,417 - tg_bot.bot_core - ERROR - Bot error: Conflict: Conflict: terminated by other getUpdates request; make sure that only one bot instance is running
2026-01-17 13:20:03,524 - tg_bot.bot_core - ERROR - Traceback: "C:\Users\lucid\AppData\Local\Programs\Python\Python312\Lib\site-packages\telegram\request\_baserequest.py", line 198, in post
    result = await self._request_wrapper(
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "C:\Users\lucid\AppData\Local\Programs\Python\Python312\Lib\site-packages\telegram\request\_baserequest.py", line 375, in _request_wrapper
    raise exception
telegram.error.Conflict: Conflict: terminated by other getUpdates request; make sure that only one bot instance is running

2026-01-17 13:20:09,501 - bots.buy_tracker.monitor - INFO - Poll #9180: 368 txns tracked, min=$1.0
2026-01-17 13:20:10,812 - tg_bot.bot_core - ERROR - Bot error: Conflict: Conflict: terminated by other getUpdates request; make sure that only one bot instance is running
2026-01-17 13:20:10,818 - tg_bot.bot_core - ERROR - Traceback: "C:\Users\lucid\AppData\Local\Programs\Python\Python312\Lib\site-packages\telegram\request\_baserequest.py", line 198, in post
    result = await self._request_wrapper(
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "C:\Users\lucid\AppData\Local\Programs\Python\Python312\Lib\site-packages\telegram\request\_baserequest.py", line 375, in _request_wrapper
    raise exception
telegram.error.Conflict: Conflict: terminated by other getUpdates request; make sure that only one bot instance is running

2026-01-17 13:20:17,728 - tg_bot.bot_core - ERROR - Bot error: Conflict: Conflict: terminated by other getUpdates request; make sure that only one bot instance is running
2026-01-17 13:20:17,730 - tg_bot.bot_core - ERROR - Traceback: "C:\Users\lucid\AppData\Local\Programs\Python\Python312\Lib\site-packages\telegram\request\_baserequest.py", line 198, in post
    result = await self._request_wrapper(
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "C:\Users\lucid\AppData\Local\Programs\Python\Python312\Lib\site-packages\telegram\request\_baserequest.py", line 375, in _request_wrapper
    raise exception
telegram.error.Conflict: Conflict: terminated by other getUpdates request; make sure that only one bot instance is running

2026-01-17 13:20:25,438 - jarvis.supervisor - INFO - === COMPONENT HEALTH ===
  buy_bot: running (uptime: 6:15:54.109779) (restarts: 0)
  sentiment_reporter: running (uptime: 6:15:50.942422) (restarts: 0)
  twitter_poster: running (uptime: 6:15:50.915818) (restarts: 0)
  telegram_bot: running (uptime: 6:15:46.222948) (restarts: 0)
  autonomous_x: running (uptime: 6:15:46.197094) (restarts: 0)
2026-01-17 13:20:29,498 - tg_bot.bot_core - ERROR - Bot error: Conflict: Conflict: terminated by other getUpdates request; make sure that only one bot instance is running
2026-01-17 13:20:29,499 - tg_bot.bot_core - ERROR - Traceback: "C:\Users\lucid\AppData\Local\Programs\Python\Python312\Lib\site-packages\telegram\request\_baserequest.py", line 198, in post
    result = await self._request_wrapper(
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "C:\Users\lucid\AppData\Local\Programs\Python\Python312\Lib\site-packages\telegram\request\_baserequest.py", line 375, in _request_wrapper
    raise exception
telegram.error.Conflict: Conflict: terminated by other getUpdates request; make sure that only one bot instance is running

2026-01-17 13:20:39,580 - tg_bot.bot_core - ERROR - Bot error: Conflict: Conflict: terminated by other getUpdates request; make sure that only one bot instance is running
2026-01-17 13:20:39,580 - tg_bot.bot_core - ERROR - Traceback: "C:\Users\lucid\AppData\Local\Programs\Python\Python312\Lib\site-packages\telegram\request\_baserequest.py", line 198, in post
    result = await self._request_wrapper(
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "C:\Users\lucid\AppData\Local\Programs\Python\Python312\Lib\site-packages\telegram\request\_baserequest.py", line 375, in _request_wrapper
    raise exception
telegram.error.Conflict: Conflict: terminated by other getUpdates request; make sure that only one bot instance is running

2026-01-17 13:20:41,546 - bots.buy_tracker.monitor - INFO - Poll #9195: 368 txns tracked, min=$1.0
2026-01-17 13:20:55,526 - tg_bot.bot_core - ERROR - Bot error: Conflict: Conflict: terminated by other getUpdates request; make sure that only one bot instance is running
2026-01-17 13:20:55,528 - tg_bot.bot_core - ERROR - Traceback: "C:\Users\lucid\AppData\Local\Programs\Python\Python312\Lib\site-packages\telegram\request\_baserequest.py", line 198, in post
    result = await self._request_wrapper(
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "C:\Users\lucid\AppData\Local\Programs\Python\Python312\Lib\site-packages\telegram\request\_baserequest.py", line 375, in _request_wrapper
    raise exception
telegram.error.Conflict: Conflict: terminated by other getUpdates request; make sure that only one bot instance is running

2026-01-17 13:21:13,713 - bots.buy_tracker.monitor - INFO - Poll #9210: 368 txns tracked, min=$1.0
2026-01-17 13:21:16,771 - tg_bot.bot_core - ERROR - Bot error: Conflict: Conflict: terminated by other getUpdates request; make sure that only one bot instance is running
2026-01-17 13:21:16,773 - tg_bot.bot_core - ERROR - Traceback: "C:\Users\lucid\AppData\Local\Programs\Python\Python312\Lib\site-packages\telegram\request\_baserequest.py", line 198, in post
    result = await self._request_wrapper(
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "C:\Users\lucid\AppData\Local\Programs\Python\Python312\Lib\site-packages\telegram\request\_baserequest.py", line 375, in _request_wrapper
    raise exception
telegram.error.Conflict: Conflict: terminated by other getUpdates request; make sure that only one bot instance is running

2026-01-17 13:21:25,436 - jarvis.supervisor - INFO - === COMPONENT HEALTH ===
  buy_bot: running (uptime: 6:16:54.107195) (restarts: 0)
  sentiment_reporter: running (uptime: 6:16:50.939838) (restarts: 0)
  twitter_poster: running (uptime: 6:16:50.913234) (restarts: 0)
  telegram_bot: running (uptime: 6:16:46.220364) (restarts: 0)
  autonomous_x: running (uptime: 6:16:46.194510) (restarts: 0)
2026-01-17 13:21:45,833 - bots.buy_tracker.monitor - INFO - Poll #9225: 368 txns tracked, min=$1.0
2026-01-17 13:21:47,023 - tg_bot.bot_core - ERROR - Bot error: Conflict: Conflict: terminated by other getUpdates request; make sure that only one bot instance is running
2026-01-17 13:21:47,023 - tg_bot.bot_core - ERROR - Traceback: "C:\Users\lucid\AppData\Local\Programs\Python\Python312\Lib\site-packages\telegram\request\_baserequest.py", line 198, in post
    result = await self._request_wrapper(
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "C:\Users\lucid\AppData\Local\Programs\Python\Python312\Lib\site-packages\telegram\request\_baserequest.py", line 375, in _request_wrapper
    raise exception
telegram.error.Conflict: Conflict: terminated by other getUpdates request; make sure that only one bot instance is running

2026-01-17 13:22:18,286 - bots.buy_tracker.monitor - INFO - Poll #9240: 368 txns tracked, min=$1.0
2026-01-17 13:22:21,844 - tg_bot.bot_core - ERROR - Bot error: Conflict: Conflict: terminated by other getUpdates request; make sure that only one bot instance is running
2026-01-17 13:22:21,844 - tg_bot.bot_core - ERROR - Traceback: "C:\Users\lucid\AppData\Local\Programs\Python\Python312\Lib\site-packages\telegram\request\_baserequest.py", line 198, in post
    result = await self._request_wrapper(
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "C:\Users\lucid\AppData\Local\Programs\Python\Python312\Lib\site-packages\telegram\request\_baserequest.py", line 375, in _request_wrapper
    raise exception
telegram.error.Conflict: Conflict: terminated by other getUpdates request; make sure that only one bot instance is running

2026-01-17 13:22:25,446 - jarvis.supervisor - INFO - === COMPONENT HEALTH ===
  buy_bot: running (uptime: 6:17:54.117026) (restarts: 0)
  sentiment_reporter: running (uptime: 6:17:50.949669) (restarts: 0)
  twitter_poster: running (uptime: 6:17:50.923065) (restarts: 0)
  telegram_bot: running (uptime: 6:17:46.230195) (restarts: 0)
  autonomous_x: running (uptime: 6:17:46.204341) (restarts: 0)
2026-01-17 13:22:26,832 - tweepy.client - WARNING - Rate limit exceeded. Sleeping for 753 seconds.
2026-01-17 13:22:50,532 - bots.buy_tracker.monitor - INFO - Poll #9255: 368 txns tracked, min=$1.0
2026-01-17 13:22:56,508 - tg_bot.bot_core - ERROR - Bot error: Conflict: Conflict: terminated by other getUpdates request; make sure that only one bot instance is running
2026-01-17 13:22:56,508 - tg_bot.bot_core - ERROR - Traceback: "C:\Users\lucid\AppData\Local\Programs\Python\Python312\Lib\site-packages\telegram\request\_baserequest.py", line 198, in post
    result = await self._request_wrapper(
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "C:\Users\lucid\AppData\Local\Programs\Python\Python312\Lib\site-packages\telegram\request\_baserequest.py", line 375, in _request_wrapper
    raise exception
telegram.error.Conflict: Conflict: terminated by other getUpdates request; make sure that only one bot instance is running

2026-01-17 13:23:22,674 - bots.buy_tracker.monitor - INFO - Poll #9270: 368 txns tracked, min=$1.0
2026-01-17 13:23:25,463 - jarvis.supervisor - INFO - === COMPONENT HEALTH ===
  buy_bot: running (uptime: 6:18:54.134328) (restarts: 0)
  sentiment_reporter: running (uptime: 6:18:50.966971) (restarts: 0)
  twitter_poster: running (uptime: 6:18:50.940367) (restarts: 0)
  telegram_bot: running (uptime: 6:18:46.247497) (restarts: 0)
  autonomous_x: running (uptime: 6:18:46.221643) (restarts: 0)
2026-01-17 13:23:32,377 - tg_bot.bot_core - ERROR - Bot error: Conflict: Conflict: terminated by other getUpdates request; make sure that only one bot instance is running
2026-01-17 13:23:32,377 - tg_bot.bot_core - ERROR - Traceback: "C:\Users\lucid\AppData\Local\Programs\Python\Python312\Lib\site-packages\telegram\request\_baserequest.py", line 198, in post
    result = await self._request_wrapper(
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "C:\Users\lucid\AppData\Local\Programs\Python\Python312\Lib\site-packages\telegram\request\_baserequest.py", line 375, in _request_wrapper
    raise exception
telegram.error.Conflict: Conflict: terminated by other getUpdates request; make sure that only one bot instance is running

2026-01-17 13:23:54,777 - bots.buy_tracker.monitor - INFO - Poll #9285: 368 txns tracked, min=$1.0
2026-01-17 13:24:07,029 - tg_bot.bot_core - ERROR - Bot error: Conflict: Conflict: terminated by other getUpdates request; make sure that only one bot instance is running
2026-01-17 13:24:07,030 - tg_bot.bot_core - ERROR - Traceback: "C:\Users\lucid\AppData\Local\Programs\Python\Python312\Lib\site-packages\telegram\request\_baserequest.py", line 198, in post
    result = await self._request_wrapper(
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "C:\Users\lucid\AppData\Local\Programs\Python\Python312\Lib\site-packages\telegram\request\_baserequest.py", line 375, in _request_wrapper
    raise exception
telegram.error.Conflict: Conflict: terminated by other getUpdates request; make sure that only one bot instance is running

2026-01-17 13:24:25,476 - jarvis.supervisor - INFO - === COMPONENT HEALTH ===
  buy_bot: running (uptime: 6:19:54.147157) (restarts: 0)
  sentiment_reporter: running (uptime: 6:19:50.979800) (restarts: 0)
  twitter_poster: running (uptime: 6:19:50.953196) (restarts: 0)
  telegram_bot: running (uptime: 6:19:46.260326) (restarts: 0)
  autonomous_x: running (uptime: 6:19:46.234472) (restarts: 0)
2026-01-17 13:24:26,889 - bots.buy_tracker.monitor - INFO - Poll #9300: 368 txns tracked, min=$1.0
2026-01-17 13:24:41,324 - tg_bot.bot_core - ERROR - Bot error: Conflict: Conflict: terminated by other getUpdates request; make sure that only one bot instance is running
2026-01-17 13:24:41,324 - tg_bot.bot_core - ERROR - Traceback: "C:\Users\lucid\AppData\Local\Programs\Python\Python312\Lib\site-packages\telegram\request\_baserequest.py", line 198, in post
    result = await self._request_wrapper(
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "C:\Users\lucid\AppData\Local\Programs\Python\Python312\Lib\site-packages\telegram\request\_baserequest.py", line 375, in _request_wrapper
    raise exception
telegram.error.Conflict: Conflict: terminated by other getUpdates request; make sure that only one bot instance is running

2026-01-17 13:24:59,256 - bots.buy_tracker.monitor - INFO - Poll #9315: 368 txns tracked, min=$1.0
2026-01-17 13:25:15,182 - tg_bot.bot_core - ERROR - Bot error: Conflict: Conflict: terminated by other getUpdates request; make sure that only one bot instance is running
2026-01-17 13:25:15,182 - tg_bot.bot_core - ERROR - Traceback: "C:\Users\lucid\AppData\Local\Programs\Python\Python312\Lib\site-packages\telegram\request\_baserequest.py", line 198, in post
    result = await self._request_wrapper(
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "C:\Users\lucid\AppData\Local\Programs\Python\Python312\Lib\site-packages\telegram\request\_baserequest.py", line 375, in _request_wrapper
    raise exception
telegram.error.Conflict: Conflict: terminated by other getUpdates request; make sure that only one bot instance is running

2026-01-17 13:25:25,493 - jarvis.supervisor - INFO - === COMPONENT HEALTH ===
  buy_bot: running (uptime: 6:20:54.164424) (restarts: 0)
  sentiment_reporter: running (uptime: 6:20:50.997067) (restarts: 0)
  twitter_poster: running (uptime: 6:20:50.970463) (restarts: 0)
  telegram_bot: running (uptime: 6:20:46.277593) (restarts: 0)
  autonomous_x: running (uptime: 6:20:46.251739) (restarts: 0)
2026-01-17 13:25:31,372 - bots.buy_tracker.monitor - INFO - Poll #9330: 368 txns tracked, min=$1.0
2026-01-17 13:25:50,646 - tg_bot.bot_core - ERROR - Bot error: Conflict: Conflict: terminated by other getUpdates request; make sure that only one bot instance is running
2026-01-17 13:25:50,651 - tg_bot.bot_core - ERROR - Traceback: "C:\Users\lucid\AppData\Local\Programs\Python\Python312\Lib\site-packages\telegram\request\_baserequest.py", line 198, in post
    result = await self._request_wrapper(
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "C:\Users\lucid\AppData\Local\Programs\Python\Python312\Lib\site-packages\telegram\request\_baserequest.py", line 375, in _request_wrapper
    raise exception
telegram.error.Conflict: Conflict: terminated by other getUpdates request; make sure that only one bot instance is running

2026-01-17 13:26:03,488 - bots.buy_tracker.monitor - INFO - Poll #9345: 368 txns tracked, min=$1.0
2026-01-17 13:26:24,373 - tg_bot.bot_core - ERROR - Bot error: Conflict: Conflict: terminated by other getUpdates request; make sure that only one bot instance is running
2026-01-17 13:26:24,373 - tg_bot.bot_core - ERROR - Traceback: "C:\Users\lucid\AppData\Local\Programs\Python\Python312\Lib\site-packages\telegram\request\_baserequest.py", line 198, in post
    result = await self._request_wrapper(
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "C:\Users\lucid\AppData\Local\Programs\Python\Python312\Lib\site-packages\telegram\request\_baserequest.py", line 375, in _request_wrapper
    raise exception
telegram.error.Conflict: Conflict: terminated by other getUpdates request; make sure that only one bot instance is running

2026-01-17 13:26:25,499 - jarvis.supervisor - INFO - === COMPONENT HEALTH ===
  buy_bot: running (uptime: 6:21:54.170948) (restarts: 0)
  sentiment_reporter: running (uptime: 6:21:51.003591) (restarts: 0)
  twitter_poster: running (uptime: 6:21:50.976987) (restarts: 0)
  telegram_bot: running (uptime: 6:21:46.284117) (restarts: 0)
  autonomous_x: running (uptime: 6:21:46.258263) (restarts: 0)
2026-01-17 13:26:35,556 - bots.buy_tracker.monitor - INFO - Poll #9360: 368 txns tracked, min=$1.0
```

## Database files (listing only)

### DB files
```text

FullName                                                                                                                   Length LastWriteTime        
--------                                                                                                                   ------ -------------        
C:\Users\lucid\OneDrive\Desktop\Projects\Jarvis\bots\grok_imagine\browser_profile\Default\heavy_ad_intervention_opt_out.db  16384 1/11/2026 11:34:47 PM
C:\Users\lucid\OneDrive\Desktop\Projects\Jarvis\bots\grok_imagine\browser_profile\first_party_sets.db                       49152 1/12/2026 12:32:18 AM
C:\Users\lucid\OneDrive\Desktop\Projects\Jarvis\bots\twitter\engagement.db                                                  45056 1/15/2026 7:27:47 PM 
C:\Users\lucid\OneDrive\Desktop\Projects\Jarvis\data\bot_health.db                                                          32768 1/17/2026 12:44:10 AM
C:\Users\lucid\OneDrive\Desktop\Projects\Jarvis\data\cache\file_cache.db                                                    20480 1/19/2026 7:41:45 PM 
C:\Users\lucid\OneDrive\Desktop\Projects\Jarvis\data\call_tracking.db                                                      192512 1/21/2026 7:56:54 AM 
C:\Users\lucid\OneDrive\Desktop\Projects\Jarvis\data\community\achievements.db                                              24576 1/18/2026 4:29:54 PM 
C:\Users\lucid\OneDrive\Desktop\Projects\Jarvis\data\custom.db                                                               8192 1/19/2026 7:46:41 PM 
C:\Users\lucid\OneDrive\Desktop\Projects\Jarvis\data\distributions.db                                                       20480 1/17/2026 4:22:40 AM 
C:\Users\lucid\OneDrive\Desktop\Projects\Jarvis\data\health.db                                                              24576 1/19/2026 5:47:23 PM 
C:\Users\lucid\OneDrive\Desktop\Projects\Jarvis\data\jarvis.db                                                             278528 1/22/2026 10:05:31 AM
C:\Users\lucid\OneDrive\Desktop\Projects\Jarvis\data\jarvis_admin.db                                                       139264 1/18/2026 7:30:46 PM 
C:\Users\lucid\OneDrive\Desktop\Projects\Jarvis\data\jarvis_memory.db                                                      143360 1/9/2026 1:51:38 PM  
C:\Users\lucid\OneDrive\Desktop\Projects\Jarvis\data\jarvis_spam_protection.db                                              36864 1/22/2026 10:34:41 AM
C:\Users\lucid\OneDrive\Desktop\Projects\Jarvis\data\jarvis_x_memory.db                                                    184320 1/22/2026 10:29:01 AM
C:\Users\lucid\OneDrive\Desktop\Projects\Jarvis\data\llm_costs.db                                                           36864 1/19/2026 6:22:27 PM 
C:\Users\lucid\OneDrive\Desktop\Projects\Jarvis\data\memory\long_term.db                                                    49152 1/11/2026 3:58:30 PM 
C:\Users\lucid\OneDrive\Desktop\Projects\Jarvis\data\metrics.db                                                             36864 1/18/2026 2:08:08 PM 
C:\Users\lucid\OneDrive\Desktop\Projects\Jarvis\data\raid_bot.db                                                            77824 1/21/2026 6:59:54 PM 
C:\Users\lucid\OneDrive\Desktop\Projects\Jarvis\data\rate_limiter.db                                                        36864 1/19/2026 8:36:27 PM 
C:\Users\lucid\OneDrive\Desktop\Projects\Jarvis\data\recycle_test.db                                                         4096 1/19/2026 7:46:41 PM 
C:\Users\lucid\OneDrive\Desktop\Projects\Jarvis\data\research.db                                                            20480 1/11/2026 3:58:27 PM 
C:\Users\lucid\OneDrive\Desktop\Projects\Jarvis\data\sentiment.db                                                           49152 1/17/2026 2:33:05 AM 
C:\Users\lucid\OneDrive\Desktop\Projects\Jarvis\data\tax.db                                                                 45056 1/20/2026 2:40:44 PM 
C:\Users\lucid\OneDrive\Desktop\Projects\Jarvis\data\telegram_memory.db                                                    274432 1/22/2026 10:29:49 AM
C:\Users\lucid\OneDrive\Desktop\Projects\Jarvis\data\treasury_trades.db                                                     28672 1/17/2026 4:32:22 AM 
C:\Users\lucid\OneDrive\Desktop\Projects\Jarvis\data\whales.db                                                              40960 1/14/2026 5:06:33 AM 
C:\Users\lucid\OneDrive\Desktop\Projects\Jarvis\database.db                                                                 45056 1/21/2026 6:52:01 PM 



```

## Database schemas (DDL only)

### Schema: bots\grok_imagine\browser_profile\Default\heavy_ad_intervention_opt_out.db
LastWriteTime: 2026-01-11 23:34:47.067452 | Size: 16384 bytes
```sql
-- table: enabled_previews_v1
CREATE TABLE enabled_previews_v1 (type INTEGER NOT NULL, version INTEGER NOT NULL, PRIMARY KEY(type));
-- table: previews_v1
CREATE TABLE previews_v1 (host_name VARCHAR NOT NULL, time INTEGER NOT NULL, opt_out INTEGER NOT NULL, type INTEGER NOT NULL, PRIMARY KEY(host_name, time DESC, opt_out, type));
```

### Schema: bots\grok_imagine\browser_profile\first_party_sets.db
LastWriteTime: 2026-01-12 00:32:18.490567 | Size: 49152 bytes
```sql
-- index: idx_cleared_at_run_browser_contexts
CREATE INDEX idx_cleared_at_run_browser_contexts ON browser_contexts_cleared(cleared_at_run);
-- index: idx_marked_at_run_sites
CREATE INDEX idx_marked_at_run_sites ON browser_context_sites_to_clear(marked_at_run);
-- index: idx_public_sets_version_browser_contexts
CREATE INDEX idx_public_sets_version_browser_contexts ON browser_context_sets_version(public_sets_version);
-- table: browser_context_sets_version
CREATE TABLE browser_context_sets_version(browser_context_id TEXT PRIMARY KEY NOT NULL,public_sets_version TEXT NOT NULL)WITHOUT ROWID;
-- table: browser_context_sites_to_clear
CREATE TABLE browser_context_sites_to_clear(browser_context_id TEXT NOT NULL,site TEXT NOT NULL,marked_at_run INTEGER NOT NULL,PRIMARY KEY(browser_context_id,site))WITHOUT ROWID;
-- table: browser_contexts_cleared
CREATE TABLE browser_contexts_cleared(browser_context_id TEXT PRIMARY KEY NOT NULL,cleared_at_run INTEGER NOT NULL)WITHOUT ROWID;
-- table: manual_configurations
CREATE TABLE manual_configurations(browser_context_id TEXT NOT NULL,site TEXT NOT NULL,primary_site TEXT,site_type INTEGER,PRIMARY KEY(browser_context_id,site))WITHOUT ROWID;
-- table: meta
CREATE TABLE meta(key LONGVARCHAR NOT NULL UNIQUE PRIMARY KEY, value LONGVARCHAR);
-- table: policy_configurations
CREATE TABLE policy_configurations(browser_context_id TEXT NOT NULL,site TEXT NOT NULL,primary_site TEXT,PRIMARY KEY(browser_context_id,site))WITHOUT ROWID;
-- table: public_sets
CREATE TABLE public_sets(version TEXT NOT NULL,site TEXT NOT NULL,primary_site TEXT NOT NULL,site_type INTEGER NOT NULL,PRIMARY KEY(version,site))WITHOUT ROWID;
```

### Schema: bots\twitter\engagement.db
LastWriteTime: 2026-01-15 19:27:47.584088 | Size: 45056 bytes
```sql
-- index: idx_history_tweet
CREATE INDEX idx_history_tweet ON metrics_history(tweet_id);
-- index: idx_metrics_created
CREATE INDEX idx_metrics_created ON tweet_metrics(created_at);
-- index: idx_metrics_thread
CREATE INDEX idx_metrics_thread ON tweet_metrics(thread_id);
-- table: audience_snapshots
CREATE TABLE audience_snapshots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT,
                    follower_count INTEGER,
                    following_count INTEGER,
                    data_json TEXT
                );
-- table: metrics_history
CREATE TABLE metrics_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    tweet_id TEXT,
                    timestamp TEXT,
                    likes INTEGER,
                    retweets INTEGER,
                    replies INTEGER,
                    impressions INTEGER,
                    FOREIGN KEY (tweet_id) REFERENCES tweet_metrics(tweet_id)
                );
-- table: sqlite_sequence
CREATE TABLE sqlite_sequence(name,seq);
-- table: threads
CREATE TABLE threads (
                    thread_id TEXT PRIMARY KEY,
                    tweet_count INTEGER,
                    created_at TEXT,
                    topic TEXT,
                    type TEXT
                );
-- table: tweet_metrics
CREATE TABLE tweet_metrics (
                    tweet_id TEXT PRIMARY KEY,
                    created_at TEXT,
                    text_preview TEXT,
                    likes INTEGER DEFAULT 0,
                    retweets INTEGER DEFAULT 0,
                    replies INTEGER DEFAULT 0,
                    quotes INTEGER DEFAULT 0,
                    impressions INTEGER DEFAULT 0,
                    profile_clicks INTEGER DEFAULT 0,
                    url_clicks INTEGER DEFAULT 0,
                    hashtag_clicks INTEGER DEFAULT 0,
                    detail_expands INTEGER DEFAULT 0,
                    engagement_rate REAL DEFAULT 0.0,
                    last_updated TEXT,
                    thread_id TEXT
                );
```

### Schema: data\bot_health.db
LastWriteTime: 2026-01-17 00:44:10.880817 | Size: 32768 bytes
```sql
-- index: idx_bot_errors_time
CREATE INDEX idx_bot_errors_time
            ON bot_errors(recorded_at);
-- index: idx_bot_health_name
CREATE INDEX idx_bot_health_name
            ON bot_health_history(bot_name);
-- index: idx_bot_health_time
CREATE INDEX idx_bot_health_time
            ON bot_health_history(recorded_at);
-- table: bot_activity
CREATE TABLE bot_activity (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                bot_name TEXT NOT NULL,
                activity_type TEXT NOT NULL,
                details TEXT,
                recorded_at TEXT NOT NULL
            );
-- table: bot_errors
CREATE TABLE bot_errors (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                bot_name TEXT NOT NULL,
                error_type TEXT,
                error_message TEXT,
                stack_trace TEXT,
                recorded_at TEXT NOT NULL
            );
-- table: bot_health_history
CREATE TABLE bot_health_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                bot_name TEXT NOT NULL,
                bot_type TEXT NOT NULL,
                status TEXT NOT NULL,
                is_running INTEGER,
                messages_processed INTEGER,
                commands_executed INTEGER,
                errors_count INTEGER,
                uptime_seconds REAL,
                avg_response_time_ms REAL,
                message TEXT,
                recorded_at TEXT NOT NULL
            );
-- table: sqlite_sequence
CREATE TABLE sqlite_sequence(name,seq);
```

### Schema: data\cache\file_cache.db
LastWriteTime: 2026-01-19 19:41:45.281168 | Size: 20480 bytes
```sql
-- index: idx_expires
CREATE INDEX idx_expires ON cache_entries(expires_at);
-- index: idx_namespace
CREATE INDEX idx_namespace ON cache_entries(namespace);
-- table: cache_entries
CREATE TABLE cache_entries (
                    key TEXT PRIMARY KEY,
                    value BLOB NOT NULL,
                    created_at REAL NOT NULL,
                    expires_at REAL NOT NULL,
                    namespace TEXT DEFAULT 'default',
                    tags TEXT
                );
```

### Schema: data\call_tracking.db
LastWriteTime: 2026-01-21 07:56:54.511015 | Size: 192512 bytes
```sql
-- table: calls
CREATE TABLE calls (
            id TEXT PRIMARY KEY,
            timestamp TEXT NOT NULL,
            source TEXT NOT NULL,
            symbol TEXT NOT NULL,
            contract TEXT,
            verdict TEXT NOT NULL,
            score REAL,
            price_at_call REAL,
            reasoning TEXT,
            change_24h_at_call REAL,
            buy_sell_ratio REAL,
            volume_24h REAL,
            market_cap REAL,
            liquidity REAL,
            holders INTEGER,
            market_regime TEXT
        );
-- table: factor_stats
CREATE TABLE factor_stats (
            id TEXT PRIMARY KEY,
            factor_name TEXT NOT NULL,
            factor_level TEXT NOT NULL,
            total_calls INTEGER DEFAULT 0,
            wins INTEGER DEFAULT 0,
            losses INTEGER DEFAULT 0,
            avg_pnl_pct REAL,
            win_rate REAL,
            last_updated TEXT
        );
-- table: outcomes
CREATE TABLE outcomes (
            id TEXT PRIMARY KEY,
            call_id TEXT NOT NULL,
            timeframe TEXT NOT NULL,
            price_after REAL,
            change_pct REAL,
            measured_at TEXT
        );
-- table: probability_model
CREATE TABLE probability_model (
            id TEXT PRIMARY KEY,
            pump_level TEXT,
            ratio_level TEXT,
            score_level TEXT,
            regime TEXT,
            sample_size INTEGER,
            win_probability REAL,
            avg_win_pct REAL,
            avg_loss_pct REAL,
            expected_value REAL,
            last_updated TEXT
        );
-- table: trades
CREATE TABLE trades (
            id TEXT PRIMARY KEY,
            call_id TEXT,
            symbol TEXT NOT NULL,
            contract TEXT,
            entry_time TEXT,
            exit_time TEXT,
            entry_price REAL,
            exit_price REAL,
            position_size REAL,
            pnl_pct REAL,
            pnl_usd REAL,
            status TEXT,
            exit_reason TEXT
        );
```

### Schema: data\community\achievements.db
LastWriteTime: 2026-01-18 16:29:54.881588 | Size: 24576 bytes
```sql
-- table: badge_progress
CREATE TABLE badge_progress (
            user_id TEXT PRIMARY KEY,
            trade_count INTEGER DEFAULT 0,
            win_streak INTEGER DEFAULT 0,
            best_win_streak INTEGER DEFAULT 0,
            total_pnl REAL DEFAULT 0,
            win_rate REAL DEFAULT 0,
            unique_tokens_analyzed INTEGER DEFAULT 0,
            referral_count INTEGER DEFAULT 0,
            vote_count INTEGER DEFAULT 0,
            has_10x_trade INTEGER DEFAULT 0,
            has_alpha_discovery INTEGER DEFAULT 0,
            updated_at TEXT
        );
-- table: sqlite_sequence
CREATE TABLE sqlite_sequence(name,seq);
-- table: user_badges
CREATE TABLE user_badges (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            badge_id TEXT,
            earned_at TEXT,
            notified INTEGER DEFAULT 0,
            UNIQUE(user_id, badge_id)
        );
```

### Schema: data\custom.db
LastWriteTime: 2026-01-19 19:46:41.408895 | Size: 8192 bytes
```sql
-- table: products
CREATE TABLE products (
                id INTEGER PRIMARY KEY,
                name TEXT,
                price REAL
            );
```

### Schema: data\distributions.db
LastWriteTime: 2026-01-17 04:22:40.772255 | Size: 20480 bytes
```sql
-- index: idx_distributions_status
CREATE INDEX idx_distributions_status
            ON distributions(status);
-- index: idx_distributions_timestamp
CREATE INDEX idx_distributions_timestamp
            ON distributions(timestamp);
-- table: distributions
CREATE TABLE distributions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                total_amount INTEGER NOT NULL,
                staking_amount INTEGER NOT NULL,
                operations_amount INTEGER NOT NULL,
                development_amount INTEGER NOT NULL,
                staking_signature TEXT,
                operations_signature TEXT,
                development_signature TEXT,
                status TEXT DEFAULT 'pending',
                error_message TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
-- table: sqlite_sequence
CREATE TABLE sqlite_sequence(name,seq);
```

### Schema: data\health.db
LastWriteTime: 2026-01-19 17:47:23.749177 | Size: 24576 bytes
```sql
-- index: idx_health_component
CREATE INDEX idx_health_component
            ON health_history(component);
-- index: idx_health_time
CREATE INDEX idx_health_time
            ON health_history(checked_at);
-- table: health_history
CREATE TABLE health_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                component TEXT NOT NULL,
                status TEXT NOT NULL,
                latency_ms REAL,
                message TEXT,
                checked_at TEXT NOT NULL
            );
-- table: sqlite_sequence
CREATE TABLE sqlite_sequence(name,seq);
-- table: system_snapshots
CREATE TABLE system_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                status TEXT NOT NULL,
                healthy_count INTEGER,
                degraded_count INTEGER,
                unhealthy_count INTEGER,
                uptime_seconds REAL,
                snapshot_json TEXT,
                recorded_at TEXT NOT NULL
            );
```

### Schema: data\jarvis.db
LastWriteTime: 2026-01-22 10:05:31.315541 | Size: 278528 bytes
```sql
-- index: idx_errors_component
CREATE INDEX idx_errors_component
                    ON error_logs(component);
-- index: idx_learnings_type
CREATE INDEX idx_learnings_type
                    ON trade_learnings(learning_type);
-- index: idx_positions_status
CREATE INDEX idx_positions_status
                ON positions(status);
-- table: daily_stats
CREATE TABLE daily_stats (
                    date TEXT PRIMARY KEY,
                    trades_opened INTEGER DEFAULT 0,
                    trades_closed INTEGER DEFAULT 0,
                    wins INTEGER DEFAULT 0,
                    losses INTEGER DEFAULT 0,
                    total_pnl_sol REAL DEFAULT 0,
                    total_pnl_percent REAL DEFAULT 0,
                    largest_win REAL DEFAULT 0,
                    largest_loss REAL DEFAULT 0,
                    win_rate REAL DEFAULT 0
                );
-- table: error_logs
CREATE TABLE error_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    error_type TEXT NOT NULL,
                    component TEXT NOT NULL,
                    message TEXT NOT NULL,
                    context TEXT,
                    stack_trace TEXT,
                    resolved INTEGER DEFAULT 0,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                );
-- table: items
CREATE TABLE items (
                id INTEGER PRIMARY KEY,
                value TEXT
            );
-- table: memory_entries
CREATE TABLE memory_entries (
            id TEXT PRIMARY KEY,
            type TEXT,
            content TEXT,
            context TEXT,
            tags TEXT,
            confidence TEXT,
            timestamp TEXT,
            session_id TEXT,
            imported_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
-- table: pick_performance
CREATE TABLE pick_performance (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    pick_date TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    asset_class TEXT NOT NULL,
                    contract TEXT,
                    conviction_score INTEGER DEFAULT 0,
                    entry_price REAL DEFAULT 0,
                    target_price REAL DEFAULT 0,
                    stop_loss REAL DEFAULT 0,
                    timeframe TEXT,
                    current_price REAL DEFAULT 0,
                    max_price REAL DEFAULT 0,
                    min_price REAL DEFAULT 0,
                    pnl_pct REAL DEFAULT 0,
                    max_gain_pct REAL DEFAULT 0,
                    hit_target INTEGER DEFAULT 0,
                    hit_stop INTEGER DEFAULT 0,
                    outcome TEXT DEFAULT 'PENDING',
                    reasoning TEXT,
                    days_held INTEGER DEFAULT 0,
                    last_updated TEXT DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(pick_date, symbol)
                );
-- table: positions
CREATE TABLE positions (
                    id TEXT PRIMARY KEY,
                    symbol TEXT NOT NULL,
                    token_mint TEXT NOT NULL,
                    entry_price REAL NOT NULL,
                    entry_amount_sol REAL NOT NULL,
                    entry_amount_tokens REAL NOT NULL,
                    take_profit_price REAL,
                    stop_loss_price REAL,
                    tp_order_id TEXT,
                    sl_order_id TEXT,
                    status TEXT,
                    exit_price REAL,
                    exit_amount_sol REAL,
                    pnl_sol REAL,
                    pnl_pct REAL,
                    opened_at TEXT,
                    closed_at TEXT,
                    tx_signature_entry TEXT,
                    tx_signature_exit TEXT,
                    user_id INTEGER DEFAULT 0
                );
-- table: scorecard
CREATE TABLE scorecard (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    total_trades INTEGER DEFAULT 0,
                    winning_trades INTEGER DEFAULT 0,
                    losing_trades INTEGER DEFAULT 0,
                    total_pnl_sol REAL DEFAULT 0,
                    total_pnl_usd REAL DEFAULT 0,
                    largest_win_sol REAL DEFAULT 0,
                    largest_loss_sol REAL DEFAULT 0,
                    current_streak INTEGER DEFAULT 0,
                    best_streak INTEGER DEFAULT 0,
                    worst_streak INTEGER DEFAULT 0,
                    avg_win_pct REAL DEFAULT 0,
                    avg_loss_pct REAL DEFAULT 0,
                    win_rate REAL DEFAULT 0,
                    last_updated TEXT DEFAULT ''
                );
-- table: sqlite_sequence
CREATE TABLE sqlite_sequence(name,seq);
-- table: test
CREATE TABLE test (id INTEGER PRIMARY KEY);
-- table: trade_learnings
CREATE TABLE trade_learnings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    trade_id TEXT,
                    token_symbol TEXT,
                    token_type TEXT,
                    learning_type TEXT,
                    insight TEXT NOT NULL,
                    confidence REAL DEFAULT 0.5,
                    applied_count INTEGER DEFAULT 0,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                );
-- table: trades
CREATE TABLE trades (
                    id TEXT PRIMARY KEY,
                    symbol TEXT NOT NULL,
                    token_mint TEXT NOT NULL,
                    side TEXT NOT NULL,
                    amount_sol REAL NOT NULL,
                    amount_tokens REAL NOT NULL,
                    price REAL NOT NULL,
                    timestamp TEXT NOT NULL,
                    tx_signature TEXT,
                    position_id TEXT,
                    user_id INTEGER DEFAULT 0
                );
-- table: treasury_orders
CREATE TABLE treasury_orders (
                    order_id TEXT PRIMARY KEY,
                    order_json TEXT NOT NULL
                );
-- table: treasury_stats
CREATE TABLE treasury_stats (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    total_trades INTEGER DEFAULT 0,
                    total_wins INTEGER DEFAULT 0,
                    total_losses INTEGER DEFAULT 0,
                    current_streak INTEGER DEFAULT 0,
                    best_win_streak INTEGER DEFAULT 0,
                    worst_loss_streak INTEGER DEFAULT 0,
                    all_time_pnl_sol REAL DEFAULT 0,
                    largest_win_sol REAL DEFAULT 0,
                    largest_win_token TEXT DEFAULT '',
                    largest_loss_sol REAL DEFAULT 0,
                    largest_loss_token TEXT DEFAULT '',
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                );
-- table: users
CREATE TABLE users (
                id INTEGER PRIMARY KEY,
                name TEXT,
                email TEXT
            );
```

### Schema: data\jarvis_admin.db
LastWriteTime: 2026-01-18 19:30:46.821153 | Size: 139264 bytes
```sql
-- index: idx_engagement_user
CREATE INDEX idx_engagement_user
                ON engagement(user_id, timestamp);
-- table: engagement
CREATE TABLE engagement (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    action_type TEXT,
                    timestamp TEXT,
                    chat_id INTEGER,
                    details TEXT
                );
-- table: messages
CREATE TABLE messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    message_id INTEGER,
                    user_id INTEGER,
                    username TEXT,
                    text TEXT,
                    timestamp TEXT,
                    chat_id INTEGER,
                    was_deleted INTEGER DEFAULT 0,
                    deletion_reason TEXT
                );
-- table: mod_actions
CREATE TABLE mod_actions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    action_type TEXT,
                    user_id INTEGER,
                    message_id INTEGER,
                    reason TEXT,
                    timestamp TEXT,
                    reversed INTEGER DEFAULT 0
                );
-- table: sqlite_sequence
CREATE TABLE sqlite_sequence(name,seq);
-- table: upgrade_ideas
CREATE TABLE upgrade_ideas (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    idea TEXT,
                    source_user_id INTEGER,
                    source_message TEXT,
                    detected_at TEXT,
                    status TEXT DEFAULT 'pending',
                    priority INTEGER DEFAULT 0
                );
-- table: users
CREATE TABLE users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    first_seen TEXT,
                    message_count INTEGER DEFAULT 0,
                    warning_count INTEGER DEFAULT 0,
                    is_banned INTEGER DEFAULT 0,
                    is_trusted INTEGER DEFAULT 0,
                    spam_score REAL DEFAULT 0.0,
                    last_message_at TEXT,
                    notes TEXT
                );
```

### Schema: data\jarvis_memory.db
LastWriteTime: 2026-01-09 13:51:38.984821 | Size: 143360 bytes
```sql
-- index: idx_entities_name
CREATE INDEX idx_entities_name ON entities(name);
-- index: idx_entities_type
CREATE INDEX idx_entities_type ON entities(entity_type);
-- index: idx_facts_entity
CREATE INDEX idx_facts_entity ON facts(entity);
-- index: idx_facts_entity_id
CREATE INDEX idx_facts_entity_id ON facts(entity_id);
-- index: idx_interactions_feedback
CREATE INDEX idx_interactions_feedback ON interactions(feedback);
-- index: idx_interactions_session
CREATE INDEX idx_interactions_session ON interactions(session_id);
-- index: idx_interactions_timestamp
CREATE INDEX idx_interactions_timestamp ON interactions(timestamp);
-- index: idx_predictions_domain
CREATE INDEX idx_predictions_domain ON predictions(domain);
-- index: idx_predictions_resolved
CREATE INDEX idx_predictions_resolved ON predictions(was_correct);
-- index: idx_reflections_applied
CREATE INDEX idx_reflections_applied ON reflections(applied);
-- index: idx_reflections_created
CREATE INDEX idx_reflections_created ON reflections(created_at);
-- table: entities
CREATE TABLE entities (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    entity_type TEXT NOT NULL,  -- person, project, company, concept
    attributes TEXT DEFAULT '{}',  -- JSON for flexibility
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(name, entity_type)
);
-- table: facts
CREATE TABLE facts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entity TEXT NOT NULL,
    entity_id INTEGER,
    fact TEXT NOT NULL,
    confidence REAL DEFAULT 0.8,
    source TEXT DEFAULT 'conversation',
    learned_at TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(entity, fact),
    FOREIGN KEY (entity_id) REFERENCES entities(id)
);
-- table: facts_fts
CREATE VIRTUAL TABLE facts_fts USING fts5(
    entity, fact, content='facts', content_rowid='id'
);
-- table: facts_fts_config
CREATE TABLE 'facts_fts_config'(k PRIMARY KEY, v) WITHOUT ROWID;
-- table: facts_fts_data
CREATE TABLE 'facts_fts_data'(id INTEGER PRIMARY KEY, block BLOB);
-- table: facts_fts_docsize
CREATE TABLE 'facts_fts_docsize'(id INTEGER PRIMARY KEY, sz BLOB);
-- table: facts_fts_idx
CREATE TABLE 'facts_fts_idx'(segid, term, pgno, PRIMARY KEY(segid, term)) WITHOUT ROWID;
-- table: interactions
CREATE TABLE interactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_input TEXT NOT NULL,
    jarvis_response TEXT,
    feedback TEXT,  -- positive, negative, confused, retry
    session_id TEXT,
    timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
    metadata TEXT DEFAULT '{}'
);
-- table: predictions
CREATE TABLE predictions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    prediction TEXT NOT NULL,
    confidence REAL NOT NULL,
    domain TEXT DEFAULT 'general',
    deadline TEXT,
    outcome TEXT,
    was_correct INTEGER,  -- NULL = unresolved, 0 = wrong, 1 = correct
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    resolved_at TEXT
);
-- table: reflections
CREATE TABLE reflections (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    trigger TEXT NOT NULL,
    what_happened TEXT,
    why_failed TEXT,
    lesson TEXT NOT NULL,
    new_approach TEXT,
    applied INTEGER DEFAULT 0,
    applied_count INTEGER DEFAULT 0,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
-- table: reflections_fts
CREATE VIRTUAL TABLE reflections_fts USING fts5(
    trigger, lesson, new_approach, content='reflections', content_rowid='id'
);
-- table: reflections_fts_config
CREATE TABLE 'reflections_fts_config'(k PRIMARY KEY, v) WITHOUT ROWID;
-- table: reflections_fts_data
CREATE TABLE 'reflections_fts_data'(id INTEGER PRIMARY KEY, block BLOB);
-- table: reflections_fts_docsize
CREATE TABLE 'reflections_fts_docsize'(id INTEGER PRIMARY KEY, sz BLOB);
-- table: reflections_fts_idx
CREATE TABLE 'reflections_fts_idx'(segid, term, pgno, PRIMARY KEY(segid, term)) WITHOUT ROWID;
-- table: schema_version
CREATE TABLE schema_version (
    version INTEGER PRIMARY KEY,
    applied_at TEXT DEFAULT CURRENT_TIMESTAMP
);
-- table: settings
CREATE TABLE settings (
    key TEXT PRIMARY KEY,
    value TEXT,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);
-- table: sqlite_sequence
CREATE TABLE sqlite_sequence(name,seq);
-- table: trust
CREATE TABLE trust (
    domain TEXT PRIMARY KEY,
    level INTEGER DEFAULT 0,
    successes INTEGER DEFAULT 0,
    failures INTEGER DEFAULT 0,
    last_success TEXT,
    last_failure TEXT,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);
-- trigger: facts_ad
CREATE TRIGGER facts_ad AFTER DELETE ON facts BEGIN
    INSERT INTO facts_fts(facts_fts, rowid, entity, fact) VALUES('delete', old.id, old.entity, old.fact);
END;
-- trigger: facts_ai
CREATE TRIGGER facts_ai AFTER INSERT ON facts BEGIN
    INSERT INTO facts_fts(rowid, entity, fact) VALUES (new.id, new.entity, new.fact);
END;
-- trigger: facts_au
CREATE TRIGGER facts_au AFTER UPDATE ON facts BEGIN
    INSERT INTO facts_fts(facts_fts, rowid, entity, fact) VALUES('delete', old.id, old.entity, old.fact);
    INSERT INTO facts_fts(rowid, entity, fact) VALUES (new.id, new.entity, new.fact);
END;
-- trigger: reflections_ad
CREATE TRIGGER reflections_ad AFTER DELETE ON reflections BEGIN
    INSERT INTO reflections_fts(reflections_fts, rowid, trigger, lesson, new_approach)
    VALUES('delete', old.id, old.trigger, old.lesson, old.new_approach);
END;
-- trigger: reflections_ai
CREATE TRIGGER reflections_ai AFTER INSERT ON reflections BEGIN
    INSERT INTO reflections_fts(rowid, trigger, lesson, new_approach)
    VALUES (new.id, new.trigger, new.lesson, new.new_approach);
END;
```

### Schema: data\jarvis_spam_protection.db
LastWriteTime: 2026-01-22 10:34:41.587632 | Size: 36864 bytes
```sql
-- table: blocked_users
CREATE TABLE blocked_users (
                user_id TEXT PRIMARY KEY,
                username TEXT,
                reason TEXT,
                spam_score REAL,
                blocked_at TEXT,
                quote_tweet_id TEXT
            );
-- table: jarvis_tweets
CREATE TABLE jarvis_tweets (
                tweet_id TEXT PRIMARY KEY,
                posted_at TEXT,
                last_scanned TEXT
            );
-- table: scanned_quotes
CREATE TABLE scanned_quotes (
                tweet_id TEXT PRIMARY KEY,
                author_id TEXT,
                is_spam INTEGER,
                scanned_at TEXT
            );
```

### Schema: data\jarvis_x_memory.db
LastWriteTime: 2026-01-22 10:29:01.780035 | Size: 184320 bytes
```sql
-- index: idx_external_reply_author
CREATE INDEX idx_external_reply_author ON external_replies(author_handle);
-- index: idx_fingerprint
CREATE INDEX idx_fingerprint ON content_fingerprints(fingerprint);
-- index: idx_semantic_hash
CREATE INDEX idx_semantic_hash
                ON content_fingerprints(semantic_hash, created_at);
-- index: idx_topic_hash
CREATE INDEX idx_topic_hash ON content_fingerprints(topic_hash);
-- index: idx_tweets_category
CREATE INDEX idx_tweets_category
                    ON tweets(category, posted_at);
-- table: content_fingerprints
CREATE TABLE content_fingerprints (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    fingerprint TEXT UNIQUE,
                    tokens TEXT,
                    prices TEXT,
                    topic_hash TEXT,
                    semantic_hash TEXT,
                    created_at TEXT,
                    tweet_id TEXT
                );
-- table: content_queue
CREATE TABLE content_queue (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    content TEXT,
                    category TEXT,
                    cashtags TEXT,
                    scheduled_for TEXT,
                    status TEXT DEFAULT 'pending',
                    created_at TEXT
                );
-- table: external_replies
CREATE TABLE external_replies (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    original_tweet_id TEXT UNIQUE,
                    author_handle TEXT,
                    original_content TEXT,
                    our_reply TEXT,
                    our_tweet_id TEXT,
                    reply_type TEXT,
                    sentiment TEXT,
                    replied_at TEXT
                );
-- table: interactions
CREATE TABLE interactions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    tweet_id TEXT,
                    user_handle TEXT,
                    user_id TEXT,
                    interaction_type TEXT,
                    our_response TEXT,
                    timestamp TEXT
                );
-- table: mention_replies
CREATE TABLE mention_replies (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    tweet_id TEXT UNIQUE,
                    author_handle TEXT,
                    our_reply TEXT,
                    replied_at TEXT
                );
-- table: sqlite_sequence
CREATE TABLE sqlite_sequence(name,seq);
-- table: token_mentions
CREATE TABLE token_mentions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT,
                    contract_address TEXT,
                    sentiment TEXT,
                    first_mentioned TEXT,
                    last_mentioned TEXT,
                    mention_count INTEGER DEFAULT 1,
                    avg_sentiment_score REAL DEFAULT 0.0
                );
-- table: tweets
CREATE TABLE tweets (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    tweet_id TEXT UNIQUE,
                    content TEXT,
                    category TEXT,
                    cashtags TEXT,
                    posted_at TEXT,
                    engagement_likes INTEGER DEFAULT 0,
                    engagement_retweets INTEGER DEFAULT 0,
                    engagement_replies INTEGER DEFAULT 0
                );
-- table: users
CREATE TABLE users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    handle TEXT UNIQUE,
                    user_id TEXT,
                    first_seen TEXT,
                    interaction_count INTEGER DEFAULT 0,
                    sentiment TEXT DEFAULT 'neutral',
                    notes TEXT
                );
```

### Schema: data\llm_costs.db
LastWriteTime: 2026-01-19 18:22:27.805079 | Size: 36864 bytes
```sql
-- index: idx_llm_daily_date
CREATE INDEX idx_llm_daily_date
            ON llm_daily_stats(date);
-- index: idx_llm_usage_provider
CREATE INDEX idx_llm_usage_provider
            ON llm_usage(provider);
-- index: idx_llm_usage_timestamp
CREATE INDEX idx_llm_usage_timestamp
            ON llm_usage(timestamp);
-- table: budget_alerts
CREATE TABLE budget_alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                alert_name TEXT NOT NULL,
                threshold_usd REAL NOT NULL,
                actual_usd REAL NOT NULL,
                period TEXT NOT NULL,
                triggered_at TEXT NOT NULL
            );
-- table: llm_daily_stats
CREATE TABLE llm_daily_stats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                provider TEXT NOT NULL,
                model TEXT NOT NULL,
                total_requests INTEGER NOT NULL,
                successful_requests INTEGER NOT NULL,
                total_input_tokens INTEGER NOT NULL,
                total_output_tokens INTEGER NOT NULL,
                total_cost_usd REAL NOT NULL,
                avg_latency_ms REAL,
                UNIQUE(date, provider, model)
            );
-- table: llm_usage
CREATE TABLE llm_usage (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                provider TEXT NOT NULL,
                model TEXT NOT NULL,
                input_tokens INTEGER NOT NULL,
                output_tokens INTEGER NOT NULL,
                cost_usd REAL NOT NULL,
                latency_ms REAL,
                success INTEGER NOT NULL,
                error TEXT,
                metadata TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
-- table: sqlite_sequence
CREATE TABLE sqlite_sequence(name,seq);
```

### Schema: data\memory\long_term.db
LastWriteTime: 2026-01-11 15:58:30.984561 | Size: 49152 bytes
```sql
-- index: idx_content_hash
CREATE INDEX idx_content_hash ON memories(content_hash);
-- index: idx_created_at
CREATE INDEX idx_created_at ON memories(created_at);
-- index: idx_is_archived
CREATE INDEX idx_is_archived ON memories(is_archived);
-- index: idx_memory_type
CREATE INDEX idx_memory_type ON memories(memory_type);
-- index: idx_priority
CREATE INDEX idx_priority ON memories(priority);
-- table: consolidation_log
CREATE TABLE consolidation_log (
                id TEXT PRIMARY KEY,
                timestamp TEXT NOT NULL,
                memories_processed INTEGER,
                memories_merged INTEGER,
                memories_archived INTEGER,
                memories_deleted INTEGER,
                summary_id TEXT
            );
-- table: memories
CREATE TABLE memories (
                id TEXT PRIMARY KEY,
                content TEXT NOT NULL,
                content_hash TEXT NOT NULL,
                memory_type TEXT NOT NULL,
                priority INTEGER NOT NULL,
                source TEXT,
                tags TEXT,
                metadata TEXT,
                embedding BLOB,
                related_ids TEXT,
                created_at TEXT NOT NULL,
                accessed_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                access_count INTEGER DEFAULT 0,
                importance_score REAL DEFAULT 0.5,
                confidence REAL DEFAULT 1.0,
                is_archived INTEGER DEFAULT 0
            );
-- table: memory_relations
CREATE TABLE memory_relations (
                source_id TEXT NOT NULL,
                target_id TEXT NOT NULL,
                relation_type TEXT NOT NULL,
                strength REAL DEFAULT 1.0,
                created_at TEXT NOT NULL,
                PRIMARY KEY (source_id, target_id, relation_type),
                FOREIGN KEY (source_id) REFERENCES memories(id),
                FOREIGN KEY (target_id) REFERENCES memories(id)
            );
```

### Schema: data\metrics.db
LastWriteTime: 2026-01-18 14:08:08.737720 | Size: 36864 bytes
```sql
-- index: idx_metrics_1h_time
CREATE INDEX idx_metrics_1h_time
            ON metrics_1h(timestamp);
-- index: idx_metrics_1m_time
CREATE INDEX idx_metrics_1m_time
            ON metrics_1m(timestamp);
-- table: alert_history
CREATE TABLE alert_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                threshold_name TEXT NOT NULL,
                component TEXT NOT NULL,
                metric TEXT NOT NULL,
                value REAL,
                threshold REAL,
                severity TEXT,
                resolved_at TEXT
            );
-- table: metrics_1h
CREATE TABLE metrics_1h (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                component TEXT NOT NULL,
                total_requests INTEGER,
                failed_requests INTEGER,
                error_rate REAL,
                latency_p50 REAL,
                latency_p95 REAL,
                latency_p99 REAL,
                latency_min REAL,
                latency_max REAL,
                latency_mean REAL,
                UNIQUE(timestamp, component)
            );
-- table: metrics_1m
CREATE TABLE metrics_1m (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                component TEXT NOT NULL,
                total_requests INTEGER,
                failed_requests INTEGER,
                error_rate REAL,
                latency_p50 REAL,
                latency_p95 REAL,
                latency_p99 REAL,
                latency_min REAL,
                latency_max REAL,
                latency_mean REAL,
                UNIQUE(timestamp, component)
            );
-- table: sqlite_sequence
CREATE TABLE sqlite_sequence(name,seq);
```

### Schema: data\raid_bot.db
LastWriteTime: 2026-01-21 18:59:54.351315 | Size: 77824 bytes
```sql
-- index: idx_participations_raid
CREATE INDEX idx_participations_raid ON raid_participations(raid_id);
-- index: idx_participations_user
CREATE INDEX idx_participations_user ON raid_participations(user_id);
-- index: idx_raids_status
CREATE INDEX idx_raids_status ON raids(status);
-- index: idx_raids_tweet
CREATE INDEX idx_raids_tweet ON raids(tweet_id);
-- index: idx_users_telegram
CREATE INDEX idx_users_telegram ON raid_users(telegram_id);
-- index: idx_users_total_points
CREATE INDEX idx_users_total_points ON raid_users(total_points DESC);
-- index: idx_users_twitter
CREATE INDEX idx_users_twitter ON raid_users(twitter_handle);
-- index: idx_users_weekly_points
CREATE INDEX idx_users_weekly_points ON raid_users(weekly_points DESC);
-- table: raid_config
CREATE TABLE raid_config (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                );
-- table: raid_participations
CREATE TABLE raid_participations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    raid_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    liked INTEGER DEFAULT 0,
                    retweeted INTEGER DEFAULT 0,
                    commented INTEGER DEFAULT 0,
                    points_earned INTEGER DEFAULT 0,
                    verified_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (raid_id) REFERENCES raids(id),
                    FOREIGN KEY (user_id) REFERENCES raid_users(id),
                    UNIQUE(raid_id, user_id)
                );
-- table: raid_users
CREATE TABLE raid_users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    telegram_id INTEGER UNIQUE NOT NULL,
                    telegram_username TEXT,
                    twitter_handle TEXT NOT NULL,
                    twitter_id TEXT,
                    is_verified INTEGER DEFAULT 0,
                    is_blue INTEGER DEFAULT 0,
                    weekly_points INTEGER DEFAULT 0,
                    total_points INTEGER DEFAULT 0,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                );
-- table: raids
CREATE TABLE raids (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    tweet_id TEXT UNIQUE NOT NULL,
                    tweet_url TEXT NOT NULL,
                    tweet_author TEXT,
                    tweet_text TEXT,
                    started_at TEXT NOT NULL,
                    ended_at TEXT,
                    status TEXT DEFAULT 'active',
                    announcement_message_id INTEGER,
                    announcement_chat_id INTEGER,
                    total_participants INTEGER DEFAULT 0,
                    total_points_awarded INTEGER DEFAULT 0
                );
-- table: sqlite_sequence
CREATE TABLE sqlite_sequence(name,seq);
-- table: weekly_winners
CREATE TABLE weekly_winners (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    week_start TEXT NOT NULL,
                    week_end TEXT NOT NULL,
                    user_id INTEGER NOT NULL,
                    rank INTEGER NOT NULL,
                    points INTEGER NOT NULL,
                    reward_amount REAL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES raid_users(id)
                );
```

### Schema: data\rate_limiter.db
LastWriteTime: 2026-01-19 20:36:27.336682 | Size: 36864 bytes
```sql
-- index: idx_requests_endpoint
CREATE INDEX idx_requests_endpoint ON request_log(endpoint);
-- index: idx_requests_time
CREATE INDEX idx_requests_time ON request_log(timestamp);
-- table: limit_stats
CREATE TABLE limit_stats (
                    name TEXT NOT NULL,
                    date TEXT NOT NULL,
                    total_requests INTEGER DEFAULT 0,
                    allowed_requests INTEGER DEFAULT 0,
                    limited_requests INTEGER DEFAULT 0,
                    avg_wait_time_ms REAL DEFAULT 0,
                    PRIMARY KEY (name, date)
                );
-- table: rate_configs
CREATE TABLE rate_configs (
                    name TEXT PRIMARY KEY,
                    requests_per_second REAL NOT NULL,
                    burst_size INTEGER NOT NULL,
                    strategy TEXT NOT NULL,
                    scope TEXT NOT NULL,
                    retry_after_seconds REAL NOT NULL,
                    enabled INTEGER DEFAULT 1,
                    priority INTEGER DEFAULT 0,
                    metadata TEXT
                );
-- table: request_log
CREATE TABLE request_log (
                    request_id TEXT PRIMARY KEY,
                    endpoint TEXT NOT NULL,
                    scope_key TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    allowed INTEGER NOT NULL,
                    wait_time_ms REAL NOT NULL,
                    limit_name TEXT
                );
```

### Schema: data\recycle_test.db
LastWriteTime: 2026-01-19 19:46:41.527404 | Size: 4096 bytes
```sql
-- (no schema rows found)
```

### Schema: data\research.db
LastWriteTime: 2026-01-11 15:58:27.712909 | Size: 20480 bytes
```sql
-- table: knowledge_graph
CREATE TABLE knowledge_graph (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    concept TEXT NOT NULL,
                    related_concepts TEXT,
                    summary TEXT,
                    examples TEXT,
                    applications TEXT,
                    confidence REAL DEFAULT 0.0,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                );
-- table: research_log
CREATE TABLE research_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    action TEXT,
                    details TEXT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                );
-- table: research_notes
CREATE TABLE research_notes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    topic TEXT NOT NULL,
                    url TEXT,
                    title TEXT,
                    content TEXT,
                    insights TEXT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    processed BOOLEAN DEFAULT FALSE
                );
-- table: sqlite_sequence
CREATE TABLE sqlite_sequence(name,seq);
```

### Schema: data\sentiment.db
LastWriteTime: 2026-01-17 02:33:05.232744 | Size: 49152 bytes
```sql
-- index: idx_agg_symbol
CREATE INDEX idx_agg_symbol ON aggregated_sentiment(symbol);
-- index: idx_readings_symbol
CREATE INDEX idx_readings_symbol ON sentiment_readings(symbol);
-- index: idx_readings_time
CREATE INDEX idx_readings_time ON sentiment_readings(timestamp);
-- table: aggregated_sentiment
CREATE TABLE aggregated_sentiment (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL,
                    overall_score REAL,
                    overall_label TEXT,
                    overall_confidence REAL,
                    source_scores_json TEXT,
                    trend TEXT,
                    trend_change REAL,
                    timestamp TEXT,
                    warning TEXT
                );
-- table: component_correlations
CREATE TABLE component_correlations (
                timestamp TEXT NOT NULL,
                component TEXT NOT NULL,
                correlation REAL NOT NULL,
                sample_size INTEGER NOT NULL
            );
-- table: predictions
CREATE TABLE predictions (
                id TEXT PRIMARY KEY,
                symbol TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                components TEXT NOT NULL,
                sentiment_score REAL NOT NULL,
                sentiment_grade TEXT NOT NULL,
                weights_used TEXT NOT NULL,
                predicted_direction TEXT NOT NULL,
                outcome_recorded_at TEXT,
                actual_price_change REAL,
                outcome_correct INTEGER
            );
-- table: sentiment_readings
CREATE TABLE sentiment_readings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    score REAL NOT NULL,
                    label TEXT,
                    confidence REAL,
                    timestamp TEXT,
                    data_points INTEGER,
                    metadata_json TEXT
                );
-- table: sqlite_sequence
CREATE TABLE sqlite_sequence(name,seq);
-- table: weight_history
CREATE TABLE weight_history (
                id TEXT PRIMARY KEY,
                timestamp TEXT NOT NULL,
                weights TEXT NOT NULL,
                trigger_type TEXT,
                performance_metric REAL
            );
```

### Schema: data\tax.db
LastWriteTime: 2026-01-20 14:40:44.549838 | Size: 45056 bytes
```sql
-- index: idx_lots_date
CREATE INDEX idx_lots_date ON tax_lots(purchase_date);
-- index: idx_lots_symbol
CREATE INDEX idx_lots_symbol ON tax_lots(symbol);
-- index: idx_sales_date
CREATE INDEX idx_sales_date ON sales(sale_date);
-- index: idx_sales_symbol
CREATE INDEX idx_sales_symbol ON sales(symbol);
-- table: sales
CREATE TABLE sales (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL,
                    quantity REAL NOT NULL,
                    sale_price REAL NOT NULL,
                    sale_date TEXT NOT NULL,
                    proceeds REAL NOT NULL,
                    cost_basis REAL NOT NULL,
                    gain_loss REAL NOT NULL,
                    fee REAL DEFAULT 0,
                    is_long_term INTEGER NOT NULL,
                    holding_period_days INTEGER NOT NULL,
                    long_term_gain_loss REAL,
                    short_term_gain_loss REAL,
                    lots_used_json TEXT,
                    tx_id TEXT UNIQUE
                );
-- table: sqlite_sequence
CREATE TABLE sqlite_sequence(name,seq);
-- table: tax_lots
CREATE TABLE tax_lots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL,
                    quantity REAL NOT NULL,
                    remaining_quantity REAL NOT NULL,
                    cost_per_unit REAL NOT NULL,
                    total_cost REAL NOT NULL,
                    fee REAL DEFAULT 0,
                    purchase_date TEXT NOT NULL,
                    tx_id TEXT UNIQUE,
                    adjusted_cost_basis REAL NOT NULL,
                    wash_sale_adjustment REAL DEFAULT 0
                );
-- table: wash_sales
CREATE TABLE wash_sales (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL,
                    sale_date TEXT NOT NULL,
                    sale_tx_id TEXT,
                    replacement_date TEXT NOT NULL,
                    replacement_tx_id TEXT,
                    disallowed_loss REAL NOT NULL,
                    replacement_lot_id INTEGER
                );
```

### Schema: data\telegram_memory.db
LastWriteTime: 2026-01-22 10:29:49.896039 | Size: 274432 bytes
```sql
-- index: idx_learnings_topic
CREATE INDEX idx_learnings_topic
                ON learnings(topic);
-- index: idx_messages_user_id
CREATE INDEX idx_messages_user_id
                ON messages(user_id);
-- table: instructions
CREATE TABLE instructions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    instruction TEXT,
                    created_by INTEGER,
                    created_at TEXT,
                    active INTEGER DEFAULT 1
                );
-- table: learnings
CREATE TABLE learnings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    topic TEXT,
                    content TEXT,
                    source_type TEXT,  -- 'conversation', 'coding_result', 'feedback'
                    source_id TEXT,
                    created_at TEXT,
                    confidence REAL DEFAULT 0.5
                );
-- table: memories
CREATE TABLE memories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    key TEXT,
                    value TEXT,
                    created_at TEXT,
                    updated_at TEXT,
                    UNIQUE(user_id, key)
                );
-- table: messages
CREATE TABLE messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    username TEXT,
                    role TEXT,  -- 'user' or 'assistant'
                    content TEXT,
                    timestamp TEXT,
                    chat_id INTEGER
                );
-- table: sqlite_sequence
CREATE TABLE sqlite_sequence(name,seq);
```

### Schema: data\treasury_trades.db
LastWriteTime: 2026-01-17 04:32:22.759448 | Size: 28672 bytes
```sql
-- index: idx_trades_timestamp
CREATE INDEX idx_trades_timestamp
            ON treasury_trades(timestamp);
-- index: idx_trades_token
CREATE INDEX idx_trades_token
            ON treasury_trades(token_mint);
-- table: daily_snapshots
CREATE TABLE daily_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT UNIQUE NOT NULL,
                starting_balance INTEGER NOT NULL,
                ending_balance INTEGER,
                total_pnl INTEGER DEFAULT 0,
                trade_count INTEGER DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
-- table: sqlite_sequence
CREATE TABLE sqlite_sequence(name,seq);
-- table: treasury_trades
CREATE TABLE treasury_trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                token_mint TEXT NOT NULL,
                side TEXT NOT NULL,
                amount_in INTEGER NOT NULL,
                amount_out INTEGER NOT NULL,
                pnl INTEGER DEFAULT 0,
                success INTEGER DEFAULT 1,
                signature TEXT,
                metadata_json TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
```

### Schema: data\whales.db
LastWriteTime: 2026-01-14 05:06:33.351983 | Size: 40960 bytes
```sql
-- index: idx_movements_time
CREATE INDEX idx_movements_time ON whale_movements(timestamp);
-- index: idx_movements_token
CREATE INDEX idx_movements_token ON whale_movements(token_mint);
-- index: idx_movements_wallet
CREATE INDEX idx_movements_wallet ON whale_movements(wallet_address);
-- table: sqlite_sequence
CREATE TABLE sqlite_sequence(name,seq);
-- table: whale_alerts
CREATE TABLE whale_alerts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    wallet_address TEXT,
                    wallet_label TEXT,
                    alert_type TEXT,
                    message TEXT,
                    value_usd REAL,
                    timestamp TEXT,
                    token_symbol TEXT,
                    tx_signature TEXT,
                    acknowledged INTEGER DEFAULT 0
                );
-- table: whale_movements
CREATE TABLE whale_movements (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    wallet_address TEXT,
                    wallet_label TEXT,
                    timestamp TEXT,
                    movement_type TEXT,
                    token_symbol TEXT,
                    token_mint TEXT,
                    amount REAL,
                    value_usd REAL,
                    direction TEXT,
                    tx_signature TEXT UNIQUE,
                    counterparty TEXT,
                    is_significant INTEGER DEFAULT 0,
                    FOREIGN KEY (wallet_address) REFERENCES whale_wallets(address)
                );
-- table: whale_wallets
CREATE TABLE whale_wallets (
                    address TEXT PRIMARY KEY,
                    label TEXT NOT NULL,
                    category TEXT DEFAULT 'unknown',
                    total_value_usd REAL DEFAULT 0,
                    sol_balance REAL DEFAULT 0,
                    is_active INTEGER DEFAULT 1,
                    first_seen TEXT,
                    last_activity TEXT,
                    win_rate REAL DEFAULT 0,
                    avg_trade_size REAL DEFAULT 0,
                    notes TEXT,
                    tags_json TEXT
                );
```

### Schema: database.db
LastWriteTime: 2026-01-21 18:52:01.619287 | Size: 45056 bytes
```sql
-- table: calls
CREATE TABLE calls (id TEXT PRIMARY KEY, timestamp TEXT NOT NULL, source TEXT NOT NULL, symbol TEXT NOT NULL, contract TEXT, verdict TEXT NOT NULL, score REAL, price_at_call REAL, reasoning TEXT, change_24h_at_call REAL, buy_sell_ratio REAL, volume_24h REAL, market_cap REAL, liquidity REAL, holders INTEGER, market_regime TEXT);
-- table: factor_stats
CREATE TABLE factor_stats (id TEXT PRIMARY KEY, factor_name TEXT NOT NULL, factor_level TEXT NOT NULL, total_calls INTEGER DEFAULT 0, wins INTEGER DEFAULT 0, losses INTEGER DEFAULT 0, avg_pnl_pct REAL, win_rate REAL, last_updated TEXT);
-- table: outcomes
CREATE TABLE outcomes (id TEXT PRIMARY KEY, call_id TEXT NOT NULL, timeframe TEXT NOT NULL, price_after REAL, change_pct REAL, measured_at TEXT);
-- table: probability_model
CREATE TABLE probability_model (id TEXT PRIMARY KEY, pump_level TEXT, ratio_level TEXT, score_level TEXT, regime TEXT, sample_size INTEGER, win_probability REAL, avg_win_pct REAL, avg_loss_pct REAL, expected_value REAL, last_updated TEXT);
-- table: trades
CREATE TABLE trades (id TEXT PRIMARY KEY, call_id TEXT, symbol TEXT NOT NULL, contract TEXT, entry_time TEXT, exit_time TEXT, entry_price REAL, exit_price REAL, position_size REAL, pnl_pct REAL, pnl_usd REAL, status TEXT, exit_reason TEXT);
```
