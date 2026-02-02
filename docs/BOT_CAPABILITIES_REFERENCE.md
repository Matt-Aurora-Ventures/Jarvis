# Jarvis Bot Capabilities Reference

**Last Updated:** 2026-01-31
**Status:** Production
**Purpose:** Comprehensive guide to all Jarvis bot capabilities, integration points, and deployment procedures

---

## Table of Contents

1. [Bot Inventory](#bot-inventory)
2. [Main Telegram Bot](#main-telegram-bot)
3. [Treasury Bot](#treasury-bot)
4. [X/Twitter Bots](#xtwitter-bots)
5. [ClawdBot Suite](#clawdbot-suite)
6. [Supporting Services](#supporting-services)
7. [Integration Architecture](#integration-architecture)
8. [Deployment Procedures](#deployment-procedures)

---

## Bot Inventory

| Bot | Purpose | Status | Token Required | VPS Location |
|-----|---------|--------|---------------|--------------|
| @Jarviskr8tivbot | Main Telegram interface | RUNNING | TELEGRAM_BOT_TOKEN | 72.61.7.126 |
| @jarvis_treasury_bot | Trading commands (isolated) | PENDING | TREASURY_BOT_TOKEN | 72.61.7.126 |
| @X_TELEGRAM_KR8TIV_BOT | X bot sync to Telegram | PENDING | X_BOT_TELEGRAM_TOKEN | 72.61.7.126 |
| @Jarvis_lifeos | Autonomous Twitter posting | RUNNING | X OAuth2 | 72.61.7.126 |
| @ClawdMatt_bot | Marketing assistant (PR Matt) | READY | On VPS | 76.13.106.100 |
| @ClawdFriday_bot | Email AI assistant | READY | On VPS | 76.13.106.100 |
| @ClawdJarvis_87772_bot | Main orchestrator | READY | On VPS | 76.13.106.100 |
| @McSquishington_bot | Campee bot | READY | Created | Remote |

---

## Main Telegram Bot

**Handle:** @Jarviskr8tivbot
**Purpose:** Primary user interface for Jarvis system
**Status:** RUNNING
**Code:** `tg_bot/`, `bots/supervisor.py`

### Capabilities

#### Trading Commands
- `/demo` - Paper trading interface
- `/buy <token> <amount>` - Buy token with TP/SL
- `/sell <token> <percent>` - Sell position (25%, 50%, 100%)
- `/positions` - View all open positions
- `/portfolio` - Portfolio overview with P&L
- `/balance` - SOL balance and USD value

#### Sentiment Analysis
- `/sentiment <token>` - Get AI sentiment score (Grok)
- `/analyze <token>` - Deep token analysis
- `/market` - Current market regime

#### Information
- `/help` - Command reference
- `/status` - System health
- `/stats` - Trading statistics

### Security Features
- Admin whitelist (TELEGRAM_ADMIN_IDS)
- Username-based auth (TELEGRAM_ADMIN_USERNAMES)
- Rate limiting on expensive API calls
- Daily cost limits for Grok API ($10/day)
- Masked secrets in logs

### Configuration
```bash
# Required
TELEGRAM_BOT_TOKEN=<main_bot_token>
TELEGRAM_ADMIN_IDS=<comma_separated_user_ids>

# Optional
TELEGRAM_ADMIN_USERNAMES=matthaynes88
TELEGRAM_BROADCAST_CHAT_ID=<group_chat_id>
LOW_BALANCE_THRESHOLD=0.01
```

---

## Treasury Bot

**Handle:** @jarvis_treasury_bot
**Purpose:** Isolated trading commands to prevent token conflicts
**Status:** PENDING DEPLOYMENT
**Code:** `bots/treasury/`

### Why Separate Token?
Original issue: Treasury bot shared TELEGRAM_BOT_TOKEN with main bot, causing polling conflicts and 35+ crashes (exit code 4294967295).

### Capabilities
- Live trading on Jupiter DEX
- Position management (max 50 positions)
- Automatic TP/SL execution
- Risk management

### Deployment Checklist
1. User creates bot via @BotFather
2. Add TREASURY_BOT_TOKEN to VPS .env
3. Restart supervisor
4. Verify "Using unique treasury bot token" in logs
5. Monitor for 10+ minutes (no crashes = success)

### Configuration
```bash
TREASURY_BOT_TOKEN=<dedicated_token>
TREASURY_LIVE_MODE=true
MAX_POSITIONS=50
```

---

## X/Twitter Bots

### 1. Autonomous Engine (@Jarvis_lifeos)

**Purpose:** Fully autonomous Twitter presence
**Status:** RUNNING (4h 29m uptime, 0 restarts)
**Code:** `bots/twitter/autonomous_engine.py`

**Capabilities:**
- Hourly market updates
- Token deep dives
- Weekly outlook threads
- Reply to mentions
- Engagement with followers
- Image generation via Grok
- Persistent memory (dedup)
- Brand voice compliance

**Features:**
- Duplicate detection (48-hour window, 0.4 similarity)
- Circuit breaker (60s min interval, 30min cooldown after 3 errors)
- Cost tracking (input/output tokens, images)
- Thread scheduling (Monday 8am, Wednesday 2pm, Friday 6pm UTC)
- Telegram sync (posts mirrored to group)

**Configuration:**
```bash
# X API (developer.x.com)
X_API_KEY=<api_key>
X_API_SECRET=<api_secret>
X_BEARER_TOKEN=<bearer>
X_ACCESS_TOKEN=<access>
X_ACCESS_TOKEN_SECRET=<secret>

# OAuth 2.0 (@Jarvis_lifeos)
X_OAUTH2_CLIENT_ID=<client_id>
X_OAUTH2_CLIENT_SECRET=<client_secret>
X_OAUTH2_ACCESS_TOKEN=<access>
X_OAUTH2_REFRESH_TOKEN=<refresh>

# xAI Grok
XAI_API_KEY=<grok_key>

# Behavior
X_DUPLICATE_DETECTION_HOURS=48
X_DUPLICATE_SIMILARITY=0.4
X_BOT_ENABLED=true
```

**Known Issues:**
- OAuth 401 errors (tokens may need refresh at developer.x.com)
- Grok API key loading (see debug_grok_api_key.py)

### 2. Sentiment Reporter

**Purpose:** Hourly market sentiment tweets
**Status:** RUNNING (4h 30m uptime, 0 restarts)
**Code:** `bots/twitter/sentiment_poster.py`

**Capabilities:**
- Top gainers/losers analysis
- Market trend summaries
- Automated posting schedule

### 3. Telegram Sync

**Purpose:** Mirror X posts to Telegram group
**Status:** PENDING (needs X_BOT_TELEGRAM_TOKEN deployment)
**Code:** `bots/twitter/telegram_sync.py`

**Issue:** Currently shares TELEGRAM_BOT_TOKEN with main bot, causing conflicts.

**Fix:** Created X_BOT_TELEGRAM_TOKEN=7968869100:AAEanuTRjH4eHTOGvssn8BV71ChsuPrz6Hc

**Deployment:**
1. Add X_BOT_TELEGRAM_TOKEN to VPS .env
2. Restart supervisor
3. Verify "Using unique X bot token" in logs

---

## ClawdBot Suite

**VPS:** 76.13.106.100 (srv1302498.hstgr.cloud)
**Gateway:** ws://127.0.0.1:18789
**Browser Control:** http://127.0.0.1:18791/

### Architecture
- clawdbot-gateway: WebSocket coordinator
- Tokens: Centralized in `/root/clawdbots/tokens.env`
- Brand guides: `/root/clawdbots/marketing_guide.md`, `jarvis_voice.md`

### 1. ClawdMatt Bot

**Handle:** @ClawdMatt_bot
**Purpose:** Marketing assistant (PR Matt persona)
**Status:** READY (token on VPS, needs code location)
**Code:** `bots/pr_matt/pr_matt_bot.py` (MVP complete)

**Capabilities:**
- Marketing content generation
- Twitter integration
- Telegram notifications
- Brand voice filtering

**Blocker:** User must provide Python bot code location or clawdbot wrapper script.

### 2. ClawdFriday Bot

**Handle:** @ClawdFriday_bot
**Purpose:** Email AI assistant
**Status:** READY (token on VPS, needs code location)
**Code:** `bots/friday/friday_bot.py` (MVP complete)

**Capabilities:**
- Email processing
- Task extraction
- Calendar integration
- Brand voice compliance

**Blocker:** User must provide code location or clawdbot wrapper.

### 3. ClawdJarvis Bot

**Handle:** @ClawdJarvis_87772_bot
**Purpose:** Main orchestrator
**Status:** READY (token on VPS, needs functional spec)

**Blocker:** Needs functional specification and implementation.

---

## Supporting Services

### 1. Buy Tracker

**Purpose:** Monitor KR8TIV token buys
**Status:** STOPPED (100 restarts - hit limit)
**Code:** `bots/buy_tracker/`

**Issue:** Background task handling (fixed in commit 1a11518, needs verification)

### 2. Bags Intel

**Purpose:** Monitor bags.fm token graduations
**Status:** RUNNING (4h 29m uptime, 0 restarts)
**Code:** `bots/bags_intel/`

**Capabilities:**
- Real-time graduation monitoring (BitQuery WebSocket)
- Investment scoring (7 dimensions, 0-100)
- Telegram reports with analysis
- Grok AI integration

**Scoring Dimensions:**
- Bonding Curve (25%): Duration, volume, buyers
- Creator (20%): Twitter, account age
- Social (15%): Linked socials, website
- Market (25%): Liquidity, price stability
- Distribution (15%): Holder count, concentration

**Configuration:**
```bash
BITQUERY_API_KEY=<required>  # Get from bitquery.io
TELEGRAM_BOT_TOKEN=<for_reports>
TELEGRAM_BUY_BOT_CHAT_ID=<target_chat>
XAI_API_KEY=<for_grok>
```

### 3. Autonomous Manager

**Purpose:** Orchestrate autonomous behaviors
**Status:** RUNNING (4h 29m uptime, 0 restarts)
**Code:** `core/autonomous_manager.py`

---

## Integration Architecture

### Component Communication

```
┌─────────────────────┐
│  Telegram Users     │
└──────────┬──────────┘
           │
           v
┌─────────────────────┐
│  @Jarviskr8tivbot   │ (Main Bot)
│  - Admin commands   │
│  - Trading UI       │
│  - Sentiment checks │
└──────────┬──────────┘
           │
           v
┌─────────────────────────────────────────┐
│         Supervisor (bots/supervisor.py) │
│  - Component orchestration              │
│  - Restart handling                     │
│  - Health monitoring                    │
└──────────┬──────────────────────────────┘
           │
           ├───────> Treasury Bot (trading)
           ├───────> X Bot (autonomous posting)
           ├───────> Sentiment Reporter
           ├───────> Buy Tracker
           ├───────> Bags Intel
           └───────> Autonomous Manager
```

### Data Flow

```
User Command
    │
    v
Telegram Handler
    │
    v
Trading Engine (core/trading/)
    │
    ├──> Jupiter DEX (Solana)
    ├──> Grok AI (sentiment)
    └──> Database (positions)
    │
    v
Response to User
```

### External APIs

| Service | Purpose | Rate Limits |
|---------|---------|-------------|
| xAI Grok | Sentiment, content | $10/day limit |
| Anthropic Claude | Advanced reasoning | Pay-per-use |
| Birdeye API | Token data | Free tier |
| Helius RPC | Solana blockchain | Paid tier |
| Jupiter DEX | Token swaps | No limits |
| Bags.fm API | Token info | Free |
| BitQuery | WebSocket data | Paid API key |

---

## Deployment Procedures

### VPS 72.61.7.126 (Main Jarvis)

```bash
# 1. SSH to VPS
ssh root@72.61.7.126

# 2. Navigate to project
cd /home/jarvis/Jarvis

# 3. Pull latest code
git pull origin main

# 4. Update .env (if needed)
nano lifeos/config/.env

# 5. Restart supervisor
pkill -f supervisor.py
nohup python bots/supervisor.py > logs/supervisor.log 2>&1 &

# 6. Verify
tail -f logs/supervisor.log
```

### VPS 76.13.106.100 (ClawdBot Gateway)

```bash
# 1. SSH to VPS
ssh root@76.13.106.100

# 2. Check gateway status
curl http://127.0.0.1:18791/health

# 3. Check tokens
cat /root/clawdbots/tokens.env

# 4. Start bot process (TBD - needs code location)
# cd <bot_directory>
# python run_bot.py
```

### Systemd Services (Alternative to Supervisor)

```bash
# Install services
cd /home/jarvis/Jarvis
sudo ./scripts/deploy/install-services.sh

# Start all services
sudo systemctl start jarvis.target

# Check status
sudo systemctl status jarvis-*

# View logs
sudo journalctl -u jarvis-supervisor -f
```

### Automated Deployment Script

```bash
# Use comprehensive deployment script
./scripts/deploy_all_bots.sh

# Features:
# - Automatic backup
# - Git pull
# - Token verification
# - Supervisor restart
# - Health monitoring
# - Rollback on failure
```

---

## Troubleshooting

### Common Issues

#### 1. Telegram Polling Conflicts

**Symptoms:** "Conflict: terminated by other getUpdates request"

**Cause:** Multiple bots using same token

**Fix:**
1. Verify each bot has unique token
2. Check supervisor.py for token isolation
3. Restart all bots

#### 2. Treasury Bot Crashes (Exit Code 4294967295)

**Symptoms:** 35+ consecutive failures

**Cause:** Missing TREASURY_BOT_TOKEN

**Fix:**
1. Create token via @BotFather
2. Add to VPS .env
3. Restart supervisor

#### 3. X Bot Not Posting

**Symptoms:** "hasn't been posting consistently"

**Cause:** Shared TELEGRAM_BOT_TOKEN causing polling conflicts

**Fix:**
1. Deploy X_BOT_TELEGRAM_TOKEN to VPS
2. Restart supervisor
3. Verify dedicated token in logs

#### 4. Grok API Errors

**Symptoms:** "Incorrect API key provided: xa***pS"

**Cause:** Key loading truncation or invalid key

**Fix:**
1. Run `python scripts/debug_grok_api_key.py`
2. Verify XAI_API_KEY in bots/twitter/.env
3. Regenerate at console.x.ai if needed

---

## Security Considerations

### Secrets Management

1. **Never commit secrets** to git
2. **Use environment variables** for all credentials
3. **Encrypt VPS secrets** with age or similar
4. **Rotate tokens** regularly
5. **Mask keys in logs** (only show first 4 and last 4 chars)

### Token Isolation

Each bot MUST have its own Telegram token to prevent polling conflicts:
- Main: TELEGRAM_BOT_TOKEN
- Treasury: TREASURY_BOT_TOKEN
- X Sync: X_BOT_TELEGRAM_TOKEN
- ClawdMatt: CLAWDMATT_BOT_TOKEN
- ClawdFriday: CLAWDFRIDAY_BOT_TOKEN
- ClawdJarvis: CLAWDJARVIS_BOT_TOKEN

### Admin Controls

- Whitelist by user ID: TELEGRAM_ADMIN_IDS
- Whitelist by username: TELEGRAM_ADMIN_USERNAMES
- Rate limits on expensive operations
- Daily cost caps on AI APIs

---

## Performance & Monitoring

### Health Checks

```bash
# Supervisor status
curl http://127.0.0.1:5000/api/health

# Bot uptime
ps aux | grep supervisor

# Log monitoring
tail -f logs/supervisor.log

# Resource usage
htop
```

### Metrics

- Bot uptime
- Restart count
- API call costs
- Position count
- P&L tracking
- Error rates

### Alerts

- Bot crash (>3 consecutive failures)
- High API costs (>$10/day)
- Low SOL balance (<0.01)
- Trading errors
- Security events

---

## Future Enhancements

### Planned Features

1. **Dashboard** - Real-time monitoring UI
2. **Metrics** - Prometheus/Grafana integration
3. **Mobile App** - iOS/Android interface
4. **Voice Interface** - TTS for content
5. **Newsletter** - Email automation
6. **AI VC Fund** - Decentralized investment DAO

### Under Development

- Nightly builds (CI/CD)
- Unit test coverage (>80%)
- Integration tests
- Load testing
- Performance profiling

---

## References

- Main Documentation: `CLAUDE.md`
- Deployment Guide: `docs/BOT_TOKEN_DEPLOYMENT_COMPLETE_GUIDE.md`
- Security Audit: `docs/SECURITY_AUDIT_BRUTE_FORCE_JAN_31.md`
- Telegram Architecture: `docs/telegram-polling-architecture.md`
- Master Task List: `docs/MASTER_GSD_SINGLE_SOURCE_OF_TRUTH.md`

---

**Maintained By:** Jarvis Development Team
**Last Audit:** 2026-01-31
**Next Review:** After all 208 GSD tasks complete
