# Bots & Integrations

Jarvis operates as a **mesh of 6 specialized bots**, each handling a specific domain. This page explains what each bot does and how to interact with them.

---

## Bot Ecosystem

```
Supervisor (bots/supervisor.py)
├── Buy Bot (KR8TIV token tracking)
├── Sentiment Reporter (Grok AI analysis)
├── Twitter Bot (@Jarvis_lifeos)
├── Telegram Bot (@Jarviskr8tivbot)
├── Bags Intel (bags.fm monitoring)
└── Treasury Trading (autonomous execution)
```

---

## 1. Buy Bot

**Purpose**: Track $KR8TIV token transactions and monitor holder behavior

**File**: `bots/buy_tracker/bot.py`

### Features

- Real-time transaction monitoring on Solana
- Holder distribution analysis
- Large buy/sell alerts
- Whale tracking (wallets >$10K)
- Top holders leaderboard

### Data Sources

- **Helius API**: Transaction parsing
- **DexScreener**: Price data
- **Birdeye API**: Advanced analytics (optional)

### Alerts

Configured via `TELEGRAM_BUY_BOT_CHAT_ID`:

| Event | Alert Threshold |
|-------|----------------|
| Large buy | >1% of total supply |
| Large sell | >1% of total supply |
| Whale activity | Wallet >$10K |
| New holder | First-time buyer |
| Graduation | Token graduates on bags.fm |

### Usage

```python
from bots.buy_tracker.bot import BuyBot

bot = BuyBot(token_address="...")
await bot.start_monitoring()
```

---

## 2. Sentiment Reporter

**Purpose**: Hourly market sentiment analysis using Grok AI

**File**: `bots/buy_tracker/sentiment_report.py`

### Features

- **Multi-source data aggregation** (DexScreener, CoinGecko, Twitter)
- **AI-powered sentiment scoring** (0-100 scale)
- **Market regime detection** (bullish, bearish, neutral, choppy)
- **Trend identification** (tokens gaining momentum)
- **Traditional markets** (stocks, commodities, DXY)

### Update Schedule

- **Frequency**: Every 15 minutes
- **AI Analysis**: Hourly (Grok xAI model)
- **Output**: `sentiment_report_data.json`

### Data Structure

```json
{
  "timestamp": "2026-01-23T14:30:00Z",
  "market_regime": "bullish",
  "macro_analysis": {
    "DXY": "down",
    "STOCKS": "up",
    "CRYPTO_IMPACT": "positive"
  },
  "trending_tokens": [
    {
      "symbol": "BONK",
      "sentiment": 78,
      "confidence": "high",
      "reason": "Strong social volume + whale accumulation"
    }
  ],
  "stock_picks": [
    {
      "symbol": "TSLA",
      "direction": "bullish",
      "target": 250,
      "stop": 220
    }
  ]
}
```

### Integration

Used by:
- Telegram `/demo` command (Sentiment Hub)
- Twitter autonomous posting
- Trading strategies (sentiment-based)

---

## 3. Twitter Bot (@Jarvis_lifeos)

**Purpose**: Autonomous social media engagement

**File**: `bots/twitter/autonomous_engine.py`

### Features

- **Autonomous posting**: Sentiment updates, market commentary
- **Mention tracking**: Reply to @Jarvis_lifeos mentions
- **Engagement analytics**: Track likes, retweets, impressions
- **Voice tuning**: Context-aware personality (bullish/bearish tone)
- **Circuit breaker**: 60s min interval, 30min cooldown after 3 errors

### Post Types

| Type | Frequency | Example |
|------|-----------|---------|
| **Sentiment Update** | Hourly | "Market sentiment is bullish. $SOL +5.2%, $BTC +3.1%. Top picks: ..." |
| **Trade Alert** | On execution | "Jarvis just bought $BONK at $0.0000123. Conviction: HIGH 🎯" |
| **Market Commentary** | 2-4x daily | "Macro update: DXY down, stocks up. Crypto looking strong 📈" |
| **User Reply** | Real-time | "@user Great question! Here's my analysis..." |

### Safety Features

- **Kill switch**: `X_BOT_ENABLED=false` (emergency disable)
- **Rate limiting**: Max 60 tweets/hour
- **Content moderation**: No profanity, scam-like language
- **Human review**: Optional approval for high-impact posts

### Usage

```python
from bots.twitter.twitter_client import TwitterClient

client = TwitterClient()
await client.post_tweet("Your message here")
```

---

## 4. Telegram Bot (@Jarviskr8tivbot)

**Purpose**: Full-featured user interface

**File**: `tg_bot/bot_core.py`

### Commands

#### Admin Commands

| Command | Description | Permission |
|---------|-------------|------------|
| `/start` | Initialize bot, show welcome | All users |
| `/demo` | Open Sentiment Hub (market data) | All users |
| `/emergency_close` | Close all positions immediately | Admin only |
| `/pause_trading` | Pause new positions | Admin only |
| `/resume_trading` | Resume trading | Admin only |
| `/restart` | Restart supervisor | Admin only |
| `/logs` | View recent logs | Admin only |
| `/treasury_status` | Treasury wallet info | Admin only |

#### Trading Commands

| Command | Description |
|---------|-------------|
| `/buy <token>` | Buy a token |
| `/sell <token>` | Sell a token or position |
| `/portfolio` | View open positions |
| `/history` | Recent trades |
| `/wallet` | Wallet balance |

### Features

**Sentiment Hub** (`/demo` command):
- **Market Regime**: Real-time BTC/SOL changes
- **AI Picks**: Grok high-conviction recommendations
- **Treasury Signals**: What the treasury bot is trading
- **Trending Tokens**: Top gainers with sentiment
- **Charts**: Real-time OHLCV charts
- **Bags Graduations**: Latest token launches
- **Traditional Markets**: Stocks, commodities, DXY

**TP/SL Monitoring**:
- Background job runs every 5 minutes
- Auto-exits when take-profit or stop-loss triggers
- Telegram notification on execution

**Chart Generation**:
- Professional candlestick charts using mplfinance
- Dark theme matching Telegram
- 5-minute caching for performance

### Configuration

```env
TELEGRAM_BOT_TOKEN=your_telegram_token
TELEGRAM_BUY_BOT_CHAT_ID=your_chat_id
TELEGRAM_ADMIN_IDS=123456789,987654321  # Comma-separated
```

---

## 5. Bags Intel Bot

**Purpose**: Monitor bags.fm token graduations

**File**: `bots/bags_intel/bags_intel_bot.py`

### Features

- **Real-time WebSocket monitoring** (Bitquery API)
- **Multi-dimensional scoring**:
  - Bonding curve performance (25%)
  - Creator credibility (20%)
  - Social presence (15%)
  - Market metrics (25%)
  - Distribution (15%)
- **Investment recommendations** based on total score
- **Automated intel reports** to Telegram

### Scoring System

| Score | Quality | Recommendation |
|-------|---------|----------------|
| **80-100** | Exceptional 🌟 | Strong buy signal 💎 |
| **65-79** | Strong 💪 | Consider buying ✅ |
| **50-64** | Average 👍 | Proceed with caution ⚠️ |
| **35-49** | Weak ⚠️ | High risk ⚠️ |
| **0-34** | Poor ❌ | Avoid ❌ |

### Intel Report

```json
{
  "token_symbol": "NEWTOKEN",
  "graduation_time": "2026-01-23T14:30:00Z",
  "total_score": 78,
  "scores": {
    "bonding_curve": 85,
    "creator": 70,
    "social": 75,
    "market": 80,
    "distribution": 72
  },
  "recommendation": "Consider buying",
  "insights": [
    "Strong bonding curve performance",
    "Active creator with verified Twitter",
    "Good initial liquidity"
  ]
}
```

### Usage

Reports sent to `TELEGRAM_BUY_BOT_CHAT_ID` on each graduation.

---

## 6. Treasury Trading Bot

**Purpose**: Autonomous trading execution

**File**: `bots/treasury/trading.py`

### Features

- **81+ strategies** across 6 categories
- **Max 50 concurrent positions**
- **4-tier risk classification**
- **60-second stop-loss monitoring**
- **Circuit breakers** for safety
- **Transparent on-chain** execution

### Wallet

```
Address: 3Ht2dkyRT8NvBrHvUGcbhqMTbaeAtGcrm3n5AKHVn24r
Encryption: AES-256 (Fernet)
Password: Stored in .env (JARVIS_WALLET_PASSWORD)
```

### Configuration

```env
TREASURY_LIVE_MODE=false  # Set to true for live trading
MAX_POSITIONS=50
MAX_POSITION_SIZE_PCT=2.0  # 2% of treasury
DAILY_LOSS_LIMIT_PCT=10.0  # -10% max loss
```

Full details: [Trading System Overview](../trading/overview.md)

---

## Inter-Bot Communication

Bots communicate via **NATS JetStream** (sub-millisecond latency):

```
Trading Signal Generated (Treasury Bot)
   ↓
NATS Publish: "trading.buy_bot.execute.critical"
   ↓
All Bots Subscribe → React Accordingly:
   ├─► Twitter Bot → Posts about trade
   ├─► Telegram Bot → Notifies user
   ├─► Buy Bot → Logs transaction
   └─► Sentiment Reporter → Updates context
```

---

## Bot Management

### Start All Bots

```bash
python bots/supervisor.py
```

### Start Individual Bots

```bash
# Telegram only
python tg_bot/bot.py

# Twitter only
python bots/twitter/autonomous_engine.py

# Treasury only
python bots/treasury/trading.py

# Sentiment only
python bots/buy_tracker/sentiment_report.py

# Bags Intel only
python bots/bags_intel/bags_intel_bot.py
```

### View Logs

```bash
# All bots
tail -f logs/supervisor.log

# Specific bot
tail -f logs/telegram.log
tail -f logs/twitter.log
tail -f logs/treasury.log
```

### Restart Bots

```bash
# Via Telegram
/restart

# Via systemd
sudo systemctl restart jarvis-supervisor

# Manual
pkill -f "bots/supervisor.py" && python bots/supervisor.py
```

---

## Next Steps

- **Configure Bot Permissions** → Edit `.env` file
- **Set Up Telegram** → Create bot via @BotFather
- **Enable Twitter** → Configure OAuth tokens
- **Fund Treasury** → Send SOL to treasury wallet
- **Monitor Bots** → Check logs and dashboards

---

**Ready to start?** → [Installation Guide](../getting-started/installation.md)

**Want to understand the architecture?** → [Architecture Overview](../architecture/overview.md)
