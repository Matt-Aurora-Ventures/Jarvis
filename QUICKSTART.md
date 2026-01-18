# Jarvis Public Trading Bot - Quick Start

**Get the trading platform running in 5 minutes.**

## 1. Clone & Setup (2 minutes)

```bash
# Get code
cd ~/Projects/Jarvis

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

## 2. Configure (2 minutes)

Create `.env` file:

```bash
cat > .env << 'EOF'
# Telegram Bot Token (Required)
PUBLIC_BOT_TELEGRAM_TOKEN=your_telegram_bot_token_here

# Optional: Trading Settings
PUBLIC_BOT_LIVE_TRADING=false              # Start in paper trading mode
PUBLIC_BOT_REQUIRE_CONFIRMATION=true       # Require /confirm before trades
PUBLIC_BOT_MIN_CONFIDENCE=65.0             # Min algorithm confidence (0-100)
PUBLIC_BOT_MAX_DAILY_LOSS=1000.0           # Max daily loss per user ($)
EOF
```

**Get Telegram Bot Token**:
1. Open Telegram, search for `@BotFather`
2. Send `/newbot`
3. Follow prompts, copy token to `.env`

## 3. Run (1 minute)

```bash
# Start all bots
python bots/supervisor.py
```

**Expected Output**:
```
============================================================
  JARVIS BOT SUPERVISOR
  Robust bot management with auto-restart
============================================================

Registered components:
  - buy_bot
  - sentiment_reporter
  - twitter_poster
  - telegram_bot
  - autonomous_x
  - public_trading_bot ← NEW
  - autonomous_manager

Starting supervisor (Ctrl+C to stop)...
```

## 4. Test (Optional, 1 minute)

```bash
# In another terminal
python -m pytest tests/test_api_integration.py -v

# Expected: 19/19 tests PASS
```

---

## Using the Bot

### Start Trading (In Telegram)

Send to bot:
```
/start
```

Response:
```
Welcome to Jarvis! You're now registered.
User ID: 12345
Risk Level: MODERATE
```

### Analyze Token

```
/analyze SOL
```

Response:
```
SOL Analysis:
- Price: $142.50
- 24h: +5.2%
- Liquidity: $500M
- Risk: LOW
- Recommendation: BUY (72% confidence)
```

### Execute Trade

```
/buy SOL 100
```

Response:
```
Confirm BUY 100 SOL at $142.50?
- Entry: $142.50
- Stop Loss: $121.13 (-15%)
- Take Profit: $213.75 (+50%)
[YES] [NO]
```

After confirmation:
```
Trade executed!
- Position: OPEN
- PnL: $0
- Unrealized: ...
```

### View Portfolio

```
/portfolio
```

Response:
```
Your Holdings:
- SOL: 100 @ $142.50
- BONK: 50 @ $0.001

Total: $14,250
Unrealized: +$350 (+2.5%)
```

### See Performance

```
/performance
```

Response:
```
Your Stats:
- Win Rate: 65% (26/40 trades)
- Avg PnL: +$125
- Total Profit: $3,250
- Fees Earned: $162.50
- Charity Donated: $10.81
```

### Manage Wallets

```
/wallets
```

Options:
- Create new wallet
- Import from seed
- Export wallet
- View balance

### Adjust Settings

```
/settings
```

Options:
- Risk level (Conservative, Moderate, Aggressive, Degen)
- Daily loss limit
- Trade confirmations
- Notifications

---

## Architecture Overview

```
Telegram Users
     ↓
Public Bot Handler (9 commands)
     ↓
┌────────────────────────────────┐
│  Market Data Service            │
│  (DexScreener, Jupiter,         │
│   Coingecko, On-chain)          │
└─────────────┬──────────────────┘
              ↓
┌────────────────────────────────┐
│  Token Analyzer                 │
│  (Price, Liquidity, Risk,       │
│   Recommendation)               │
└─────────────┬──────────────────┘
              ↓
┌────────────────────────────────┐
│  Adaptive Algorithm             │
│  (8 algorithms, Learning,       │
│   Signal generation)            │
└─────────────┬──────────────────┘
              ↓
┌────────────────────────────────┐
│  Trading Engine                 │
│  (Position Management,          │
│   Fee Distribution)             │
└────────────────────────────────┘
```

---

## Key Features

### ✅ Secure Wallets
- PBKDF2 encryption (100k iterations)
- Fernet symmetric encryption
- Per-user derived keys
- Private keys never logged

### ✅ Smart Trading
- 8 parallel algorithms
- Continuous learning
- Risk assessment (6 levels)
- Stop loss / Take profit

### ✅ Perfect Incentives
- Users earn 75% of fees
- Charity gets 5%
- Company keeps 20%
- Transparent tracking

### ✅ Rate Limiting
- Max 20 trades/day
- Max $1,000 daily loss
- Max 5% position size
- Confirmation required

---

## Monitoring

Check if bot is healthy:

```bash
curl http://localhost:8080/health | jq
```

View logs:

```bash
tail -f logs/supervisor.log
tail -f logs/public_bot.log
```

---

## API Integration

All APIs are pre-tested and working:

- ✅ DexScreener (Solana DEX data)
- ✅ Jupiter (Token pricing)
- ✅ Coingecko (Market data)
- ✅ On-chain (Holder distribution)

Run tests:

```bash
python -m pytest tests/test_api_integration.py -v
```

---

## Database

User data stored at:
```
~/.lifeos/public_users.db
```

Contains:
- User profiles
- Encrypted wallets
- Trading history
- Algorithm metrics
- Fee distribution

All encrypted with PBKDF2 + Fernet.

---

## Troubleshooting

### Bot won't start
```bash
# Check token
echo $PUBLIC_BOT_TELEGRAM_TOKEN

# Check logs
tail -f logs/supervisor.log | grep public_bot
```

### API errors
```bash
# Run API tests
python -m pytest tests/test_api_integration.py::TestDexScreenerAPI -v

# Check network
ping api.dexscreener.com
```

### Clear data
```bash
# Reset database (will recreate on startup)
rm ~/.lifeos/public_users.db
```

---

## Business Metrics

Once running, track:

```bash
# Active users
SELECT COUNT(*) FROM users;

# Total fees collected
SELECT SUM(total_fee) FROM success_fees;

# Average win rate
SELECT AVG(winning_signals) / AVG(total_signals) FROM algorithm_metrics;
```

---

## Next Steps

1. ✅ System is running
2. Run `/start` in Telegram to register
3. Run `/analyze SOL` to see token analysis
4. Run `/buy SOL 10` to execute a test trade (paper mode)
5. Check `/performance` to see results
6. Invite others to use the bot!

---

## Support

- **Docs**: See `docs/` folder
- **Architecture**: `SYSTEM_ARCHITECTURE.md`
- **Deployment**: `docs/DEPLOYMENT_GUIDE.md`
- **Production**: `docs/PRODUCTION_READINESS.md`
- **Issues**: Check logs or GitHub issues

---

**Status**: Production Ready
**Last Updated**: 2026-01-18
**Version**: 1.0
