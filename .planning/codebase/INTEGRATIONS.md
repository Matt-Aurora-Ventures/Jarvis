# Jarvis External Integrations

**Generated**: 2026-01-24

## AI/LLM Providers

### Anthropic (Claude)
- API Key: ANTHROPIC_API_KEY
- Models: claude-sonnet-4-20250514, Opus 4
- Files: core/llm/anthropic_utils.py, tg_bot/services/claude_client.py

### OpenAI
- **API Key**: OPENAI_API_KEY
- **Usage**: Alternative AI provider, Whisper STT
- **Models**: GPT-4, GPT-3.5

### xAI (Grok)
- **API Key**: XAI_API_KEY
- **Model**: grok-3-mini, grok-3
- **Usage**: Sentiment analysis, token scoring
- **Daily Limit**: $10 (configurable)
- **Files**: core/xai_twitter.py, bots/buy_tracker/sentiment_report.py

### Groq
- **API Key**: GROQ_API_KEY
- **Model**: llama-3.3-70b-versatile
- **Rate Limit**: 30 req/min
- **Docs**: https://console.groq.com

### Ollama (Local)
- **URL**: OLLAMA_BASE_URL
- **Models**: qwen2.5-coder:7b, llama3.2
- **Usage**: Private, offline AI inference

---

## Blockchain & DeFi

### Solana Network
- **Network**: SOLANA_NETWORK
- **RPC URL**: SOLANA_RPC_URL
- **WebSocket**: SOLANA_WS_URL
- **Helius RPC**: HELIUS_API_KEY, HELIUS_RPC_URL

### Jupiter Aggregator
- **API URL**: JUPITER_API_URL (https://quote-api.jup.ag/v6)
- **Purpose**: DEX aggregation for best swap routes
- **Files**: bots/treasury/jupiter.py, core/jupiter.py

### Bags.fm
- **API URL**: BAGS_API_URL (https://api.bags.fm)
- **Partner Code**: BAGS_PARTNER_CODE
- **Purpose**: Token launches, fee collection
- **Files**: core/treasury/bags_integration.py, api/webhooks/bags_webhook.py

### Bitquery (Bags Intel)
- **API Key**: BITQUERY_API_KEY
- **Purpose**: Real-time WebSocket monitoring of bags.fm graduations
- **Files**: bots/bags_intel/monitor.py, bots/bags_intel/intel_service.py

---

## Market Data APIs

### DexScreener
- **API URL**: https://api.dexscreener.com/latest
- **Files**: core/dexscreener.py
- **Auth**: Public API

### Birdeye
- **API Key**: BIRDEYE_API_KEY
- **Files**: core/birdeye.py

### GeckoTerminal
- **Files**: core/geckoterminal.py
- **Auth**: Public API

---

## Social Platforms

### Telegram Bot
- **Bot Token**: TELEGRAM_BOT_TOKEN
- **Admin Chat ID**: TELEGRAM_ADMIN_CHAT_ID
- **Admin User IDs**: TELEGRAM_ADMIN_IDS
- **Broadcast Chat**: TELEGRAM_BROADCAST_CHAT_ID
- **Entry Point**: tg_bot/bot.py
- **Framework**: python-telegram-bot

### X (Twitter)
- **API Key**: X_API_KEY, X_API_SECRET
- **Access Token**: X_ACCESS_TOKEN, X_ACCESS_TOKEN_SECRET
- **Bearer Token**: X_BEARER_TOKEN
- **Kill Switch**: X_BOT_ENABLED
- **SDKs**: xdk>=0.1.0, tweepy>=4.14.0
- **Files**: bots/twitter/twitter_client.py

### Discord
- **Webhooks**: DISCORD_WEBHOOK_ALERTS, DISCORD_WEBHOOK_TRADES

---

## Payment & Billing

### Stripe
- **Secret Key**: STRIPE_SECRET_KEY
- **Webhook Secret**: STRIPE_WEBHOOK_SECRET
- **Price IDs**: STRIPE_PRICE_STARTER, STRIPE_PRICE_PRO, STRIPE_PRICE_WHALE

---

## Database & Storage

### PostgreSQL (Production)
- **Connection String**: DATABASE_URL
- **Pooling**: core/db/pool.py

### SQLite (Default)
- **Path**: ./data/jarvis.db

### Redis (Optional)
- **URL**: REDIS_URL
- **Purpose**: Caching, sessions, distributed locks
- **Files**: core/cache/redis_cache.py, core/locks/distributed_lock.py

---

## Monitoring

### Sentry
- **DSN**: SENTRY_DSN
- **Purpose**: Error tracking

### Prometheus
- **Enabled**: METRICS_ENABLED
- **Port**: METRICS_PORT (default: 9090)
- **Endpoint**: /api/metrics

---

## WebSocket Channels

- /ws/trading - Trade execution updates
- /ws/staking - Staking rewards
- /ws/treasury - Treasury activity
- /ws/credits - Credit usage
- /ws/voice - Voice command responses

---

## Authentication

### JWT
- **Secret**: JWT_SECRET
- **Implementation**: api/auth/jwt_auth.py

### API Key
- **Implementation**: api/auth/key_auth.py
- **Header**: X-API-Key

---

## Security Settings

- **Rate Limiting**: RATE_LIMIT_REQUESTS, RATE_LIMIT_WINDOW_SECONDS
- **IP Allowlist**: ALLOWED_IPS
- **Kill Switches**: LIFEOS_KILL_SWITCH, JARVIS_KILL_SWITCH

---

## Integration Summary

| Provider | Env Var | Purpose |
|----------|---------|---------|
| Anthropic | ANTHROPIC_API_KEY | Primary AI (Claude) |
| OpenAI | OPENAI_API_KEY | GPT models, Whisper STT |
| xAI | XAI_API_KEY | Grok sentiment analysis |
| Solana | SOLANA_RPC_URL | Blockchain RPC |
| Jupiter | JUPITER_API_URL | DEX aggregation |
| Bags.fm | BAGS_PARTNER_CODE | Token launches |
| Bitquery | BITQUERY_API_KEY | Graduation monitoring |
| DexScreener | - | Token data (public) |
| Birdeye | BIRDEYE_API_KEY | Solana analytics |
| Telegram | TELEGRAM_BOT_TOKEN | Bot interface |
| Twitter/X | X_API_KEY | Social posting |
| Stripe | STRIPE_SECRET_KEY | Billing |
| PostgreSQL | DATABASE_URL | Primary storage |
| Redis | REDIS_URL | Distributed cache |
