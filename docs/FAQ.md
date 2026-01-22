# JARVIS Frequently Asked Questions

Common questions and answers about developing, deploying, and using JARVIS.

---

## Table of Contents

1. [Getting Started](#getting-started)
2. [Configuration](#configuration)
3. [Bots (Telegram/Twitter)](#bots-telegramtwitter)
4. [Treasury & Trading](#treasury--trading)
5. [LLM Integration](#llm-integration)
6. [API](#api)
7. [Database](#database)
8. [Deployment](#deployment)
9. [Troubleshooting](#troubleshooting)
10. [Security](#security)

---

## Getting Started

### Q: What are the minimum requirements to run JARVIS?

**A:**
- Python 3.10 or higher
- 512MB RAM minimum (2GB recommended)
- PostgreSQL 13+ or SQLite for development
- Redis (optional, for caching)

### Q: How do I set up a development environment?

**A:** See the [Developer Setup Guide](DEVELOPER_SETUP.md) for detailed instructions. Quick start:

```bash
git clone <repo>
cd jarvis
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp env.example .env
# Edit .env with your API keys
python run_bots.py
```

### Q: What API keys do I need?

**A:** At minimum:
- `ANTHROPIC_API_KEY` or `OPENAI_API_KEY` - For LLM functionality
- `TELEGRAM_BOT_TOKEN` - If using Telegram bot

For full functionality:
- `TWITTER_BEARER_TOKEN` - Twitter integration
- `SOLANA_RPC_URL` - Solana blockchain access
- `SOLANA_PRIVATE_KEY` - Treasury operations (handle with care!)

---

## Configuration

### Q: Where is the configuration stored?

**A:** Configuration comes from multiple sources:

1. **Environment variables** - Primary source for secrets
2. **`.env` file** - Local development overrides
3. **`core/config/`** - Default values and schema

Priority: Environment > .env > defaults

### Q: How do I change logging levels?

**A:**

```bash
# Environment variable
export LOG_LEVEL=DEBUG

# Or in .env
LOG_LEVEL=DEBUG

# For specific modules
export LOG_LEVEL_CORE_LLM=DEBUG
```

### Q: Can I run without Redis?

**A:** Yes. Set:

```bash
REDIS_ENABLED=false
```

Caching will use in-memory fallback (not shared across instances).

---

## Bots (Telegram/Twitter)

### Q: How do I create a Telegram bot token?

**A:**

1. Message [@BotFather](https://t.me/BotFather) on Telegram
2. Send `/newbot`
3. Follow the prompts to name your bot
4. Copy the token to `TELEGRAM_BOT_TOKEN`

### Q: How do I add admin users?

**A:** Add Telegram user IDs to environment:

```bash
ADMIN_USER_IDS=123456789,987654321
```

Find your user ID by messaging [@userinfobot](https://t.me/userinfobot).

### Q: Why isn't my bot responding?

**A:** Check these common issues:

1. **Token correct?** - Verify `TELEGRAM_BOT_TOKEN`
2. **Bot started?** - Check logs for startup errors
3. **Privacy mode?** - Bot only sees messages starting with `/` unless disabled
4. **Rate limited?** - Check for rate limit warnings in logs

### Q: How do I handle bot rate limits?

**A:** JARVIS includes built-in rate limiting:

```python
# In core/bot/rate_limiter.py
DEFAULT_LIMITS = {
    "user_message": RateLimitConfig(requests=30, window_seconds=60),
    "user_command": RateLimitConfig(requests=10, window_seconds=60),
}
```

Adjust these values in your configuration if needed.

### Q: Can I run multiple bots?

**A:** Yes. Each bot needs its own token:

```bash
TELEGRAM_BOT_TOKEN=bot1_token
TELEGRAM_BOT_TOKEN_2=bot2_token
```

Then configure separate instances in `run_bots.py`.

---

## Treasury & Trading

### Q: Is the treasury using real funds?

**A:** It depends on configuration:

```bash
# Test mode (paper trading)
TREASURY_MODE=paper

# Real funds (use with caution!)
TREASURY_MODE=live
```

Always start with paper mode.

### Q: What are the trading limits?

**A:** Default safety limits:

| Limit | Value |
|-------|-------|
| Single trade | $1,000 |
| Daily volume | $10,000 |
| Position size | 10% of portfolio |

Adjust in `core/treasury/risk.py`.

### Q: How do I trigger emergency shutdown?

**A:**

```python
from core.security.emergency_shutdown import trigger_shutdown

# In code
await trigger_shutdown(reason="Manual intervention")

# Via bot command (admin only)
/emergency_shutdown

# Via API
POST /api/v1/admin/emergency-shutdown
```

### Q: What exchanges/DEXs are supported?

**A:** Currently:
- Jupiter (Solana DEX aggregator)
- Raydium (Solana AMM)

Future: Binance, Coinbase integration planned.

---

## LLM Integration

### Q: Which LLM providers are supported?

**A:**
- **Anthropic Claude** (recommended) - claude-3-opus, claude-3-sonnet, claude-3-haiku
- **OpenAI** - gpt-4, gpt-4-turbo, gpt-3.5-turbo
- **Groq** (fast inference)
- **Ollama** (local models)

### Q: How do I switch LLM providers?

**A:**

```bash
# Primary provider
LLM_PROVIDER=anthropic

# Fallback chain
LLM_FALLBACK_PROVIDERS=openai,groq
```

### Q: Can I run Claude Code locally with Ollama?

**A:** Yes. Ollama 0.14.0+ exposes an Anthropic-compatible Messages API, so Claude Code can run fully local (the API key can be a placeholder like `ollama`).

```bash
# Install a local coding model
ollama pull qwen3-coder

# Point Claude Code to Ollama
export ANTHROPIC_API_KEY=ollama
export ANTHROPIC_BASE_URL=http://localhost:11434/v1

# Run Claude Code locally
claude --model qwen3-coder
```

If you also want JARVIS to use the same local model, set `OLLAMA_URL=http://localhost:11434` and `OLLAMA_MODEL=qwen3-coder` in your `.env`. JARVIS also honors `ANTHROPIC_BASE_URL` to route Claude calls through Ollama.

### Q: How do I control LLM costs?

**A:** Use the cost tracker:

```python
from core.llm.cost_tracker import get_cost_tracker

tracker = get_cost_tracker()
stats = tracker.get_session_stats()
print(f"Total cost: ${stats['total_cost']:.4f}")
```

Set budget limits:

```bash
LLM_DAILY_BUDGET=10.00
LLM_MONTHLY_BUDGET=100.00
```

### Q: Why is the LLM response slow?

**A:** Common causes:

1. **Model choice** - Opus is slower than Haiku
2. **Token count** - Long prompts take longer
3. **Rate limits** - Provider throttling
4. **Network** - Check connectivity

Try:
```bash
# Use faster model for simple tasks
LLM_DEFAULT_MODEL=claude-3-haiku
```

---

## API

### Q: How do I authenticate API requests?

**A:** Use bearer token or API key:

```bash
# Header
Authorization: Bearer your-api-key

# Query param (not recommended)
GET /api/v1/data?api_key=your-key
```

### Q: What's the API rate limit?

**A:** Default limits:

| Endpoint Type | Limit |
|--------------|-------|
| Read endpoints | 100/minute |
| Write endpoints | 20/minute |
| Trade endpoints | 5/minute |

Headers show current usage:
```
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 95
X-RateLimit-Reset: 1704067200
```

### Q: How do I get API documentation?

**A:**
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`
- OpenAPI JSON: `http://localhost:8000/openapi.json`

Also see [API Documentation](API_DOCUMENTATION.md).

---

## Database

### Q: Which databases are supported?

**A:**
- **PostgreSQL** (recommended for production)
- **SQLite** (development only)

```bash
# PostgreSQL
DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/jarvis

# SQLite (dev)
DATABASE_URL=sqlite+aiosqlite:///./jarvis.db
```

### Q: How do I run migrations?

**A:**

```bash
# Create migration
alembic revision --autogenerate -m "description"

# Apply migrations
alembic upgrade head

# Or use the script
python scripts/db/migrate.py upgrade
```

### Q: How do I backup the database?

**A:**

```bash
# PostgreSQL
python scripts/db/backup.py

# Manual
pg_dump jarvis > backup.sql
```

### Q: Database is slow, what do I do?

**A:**
1. Check connection pool settings
2. Add indexes for frequent queries
3. Run `ANALYZE` on tables
4. Check slow query log

```bash
# Enable slow query logging
DB_SLOW_QUERY_THRESHOLD=0.5  # 500ms
```

---

## Deployment

### Q: How do I deploy to production?

**A:** See [Deployment Runbook](runbooks/DEPLOYMENT.md). Quick overview:

```bash
# Build image
docker build -t jarvis-api .

# Run with docker-compose
docker-compose -f docker-compose.prod.yml up -d
```

### Q: What ports does JARVIS use?

**A:**
| Service | Port |
|---------|------|
| API | 8000 |
| Metrics | 9090 |
| Health | 8000/health |

### Q: How do I scale horizontally?

**A:**
1. Use external Redis for sessions/cache
2. Use PostgreSQL (not SQLite)
3. Run multiple API instances behind load balancer
4. Run single bot instance per platform

### Q: How do I set up HTTPS?

**A:** Use a reverse proxy:

```nginx
# nginx.conf
server {
    listen 443 ssl;
    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;

    location / {
        proxy_pass http://localhost:8000;
    }
}
```

---

## Troubleshooting

### Q: "Connection refused" errors

**A:** Check:
1. Is the service running?
2. Correct host/port?
3. Firewall blocking?

```bash
# Check if port is listening
netstat -tlnp | grep 8000
```

### Q: "Rate limit exceeded"

**A:** You're sending too many requests. Options:
1. Wait for reset (check `X-RateLimit-Reset` header)
2. Implement request queuing
3. Request rate limit increase

### Q: Out of memory errors

**A:**
1. Check memory limits: `docker stats`
2. Reduce connection pool sizes
3. Enable garbage collection tuning:
   ```bash
   PYTHONMALLOC=malloc
   ```

### Q: "Invalid API key"

**A:** Verify:
1. Key is correctly copied (no extra spaces)
2. Key has correct permissions
3. Key hasn't expired

### Q: Bot commands not working

**A:** Debug steps:
1. Check bot is running: `ps aux | grep bot`
2. Check logs: `tail -f logs/bot.log`
3. Verify token with BotFather
4. Test with `/start` command

---

## Security

### Q: How are secrets stored?

**A:**
- Environment variables (primary)
- Encrypted storage for wallet keys
- Never in code or git

### Q: How do I rotate API keys?

**A:**
1. Generate new key
2. Update environment variable
3. Restart service
4. Revoke old key

### Q: What if I suspect a security breach?

**A:**
1. Trigger emergency shutdown
2. Rotate all credentials
3. Check audit logs
4. Contact security lead

See [Security Guidelines](SECURITY_GUIDELINES.md).

### Q: How do I report a vulnerability?

**A:**
- DO NOT create public GitHub issue
- Email security concerns privately
- Include: description, reproduction steps, impact

---

## Still Have Questions?

1. Check other docs in `docs/` folder
2. Search existing GitHub issues
3. Join community chat
4. Open a new issue with `question` label

---

## Quick Links

- [Developer Setup](DEVELOPER_SETUP.md)
- [API Documentation](API_DOCUMENTATION.md)
- [Troubleshooting Guide](TROUBLESHOOTING.md)
- [Architecture Overview](architecture/README.md)
- [Security Guidelines](SECURITY_GUIDELINES.md)
- [Performance Tuning](PERFORMANCE_TUNING.md)
