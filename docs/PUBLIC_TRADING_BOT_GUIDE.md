# Public Trading Bot - Complete System Guide

## Overview

The **Public Trading Bot** is a mass-market Telegram bot enabling anyone to analyze Solana tokens, trade with managed risk, and learn from AI-powered recommendations.

This is the next generation of Jarvis - designed for **scale and accessibility**.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│              PUBLIC TRADING BOT (USER-FACING)               │
│                                                             │
│  • /analyze <token> - Token analysis                       │
│  • /buy <token> <amount> - Trade execution                 │
│  • /portfolio - Holdings & P&L                             │
│  • /settings - Risk management                             │
│  • /performance - Stats & learning                         │
└─────────────────┬───────────────────────────────────────────┘
                  │
        ┌─────────┴─────────┐
        ↓                   ↓
┌──────────────────┐  ┌──────────────────┐
│ User Management  │  │ Token Analyzer   │
│                  │  │                  │
│ • Registration   │  │ • Price analysis │
│ • Wallets        │  │ • Risk rating    │
│ • Settings       │  │ • Sentiment      │
│ • Rate limits    │  │ • Technical      │
│ • Stats          │  │ • Recommendation │
└──────────────────┘  └──────────────────┘
        ↓                   ↓
┌──────────────────────────────────────────┐
│      ADAPTIVE LEARNING ALGORITHM          │
│                                          │
│  • Signal generation (8+ types)          │
│  • Outcome tracking                      │
│  • Confidence adjustment                 │
│  • Pattern extraction                    │
│  • Continuous improvement                │
└──────────────────────────────────────────┘
        ↓
┌──────────────────────────────────────────┐
│         TRADING ENGINE & WALLETS         │
│                                          │
│  • Solana wallet per user                │
│  • Jupiter DEX execution                 │
│  • Transaction logging                   │
│  • Position management                   │
└──────────────────────────────────────────┘
```

## Core Components

### 1. **PublicUserManager** (`core/public_user_manager.py`)

Manages users, wallets, and trading settings.

**Features:**
- User registration with profiles
- Multi-wallet support (create, import, export)
- Risk level management (Conservative to Degen)
- Trading statistics and performance tracking
- Rate limiting (daily trade/loss limits)
- Encrypted wallet storage

**Key Classes:**
```python
UserProfile
  - user_id, telegram_username
  - risk_level, max_position_size_pct
  - max_daily_trades, max_daily_loss_usd
  - Settings for alerts, anti-whale, auto-adjust

Wallet
  - wallet_id, public_key, encrypted_private_key
  - source (generated/imported/recovered)
  - balance_sol, total_traded_usd, is_primary

UserStats
  - total_trades, winning_trades, losing_trades
  - total_pnl_usd, win_rate
  - current_risk_level, win_streak, loss_streak
```

**Usage:**
```python
user_manager = PublicUserManager()

# Register new user
success, profile = user_manager.register_user(user_id, username)

# Create wallet
success, wallet = user_manager.create_wallet(user_id, public_key, encrypted_privkey, is_primary=True)

# Get user stats
stats = user_manager.get_user_stats(user_id)

# Check rate limits
allowed, reason = user_manager.check_rate_limits(user_id)

# Record a trade
user_manager.record_trade(user_id, wallet_id, "SOL", "BUY", 50.0, pnl_usd=0.0)
```

### 2. **AdaptiveAlgorithm** (`core/adaptive_algorithm.py`)

Learning system that continuously improves trading recommendations.

**Signal Types:**
- `SENTIMENT` - Grok sentiment analysis
- `LIQUIDATION` - Liquidation level detection
- `WHALE` - Whale activity signals
- `TECHNICAL` - Moving averages, crossovers
- `NEWS` - News catalyst detection
- `MOMENTUM` - Momentum trading
- `REVERSAL` - Reversal patterns
- `VOLUME` - Volume surge detection
- `COMPOSITE` - Combined signal strength

**How it learns:**
1. Generate signals based on different algorithms
2. Execute trades following signals
3. Record outcomes (win/loss, amount)
4. Update algorithm confidence based on results
5. Adjust parameters for better future signals

**Key Methods:**
```python
algorithm = AdaptiveAlgorithm()

# Generate signals
signal = algorithm.generate_sentiment_signal(symbol, sentiment_score, price_data)
signal = algorithm.generate_liquidation_signal(symbol, liquidation_data)
signal = algorithm.generate_whale_signal(symbol, whale_data)

# Record outcomes
outcome = TradeOutcome(
    algorithm_type=AlgorithmType.SENTIMENT,
    signal_strength=75,
    user_id=user_id,
    symbol="SOL",
    entry_price=100,
    exit_price=110,
    pnl_usd=50,
    hold_duration_hours=2
)
algorithm.record_outcome(outcome)

# Get confidence and recommendations
confidence = algorithm.get_algorithm_confidence(AlgorithmType.SENTIMENT)
composite_strength = algorithm.get_composite_signal_strength(signals)
recommendations = algorithm.recommend_algorithm_adjustments()
```

### 3. **TokenAnalyzer** (`core/token_analyzer.py`)

Comprehensive on-demand token analysis.

**Provides:**
- Price analysis (current, 24h, 7d, 30d changes)
- Liquidity scoring (0-100)
- Risk assessment (6 risk categories + overall rating)
- Sentiment integration
- Technical indicators
- Buy/Sell recommendations with confidence

**Risk Categories:**
- Holder concentration (whale dumps)
- Liquidity risk (ability to exit)
- Volatility risk (price swings)
- Regulatory risk
- Smart contract risk
- Team doxxing (rug pull risk)

**Recommendation Output:**
```python
TokenRecommendation
  - action: "BUY", "HOLD", "SELL", "WAIT"
  - confidence: 0-100
  - entry_price, target_price, stop_loss_price
  - time_horizon: "hours/days/weeks"
  - reasoning: [list of analysis points]
  - catalysts: [what could drive price]
```

**Usage:**
```python
analyzer = TokenAnalyzer()

# Analyze token
analysis = await analyzer.analyze_token("SOL", market_data)

# Get formatted message
telegram_msg = analyzer.format_analysis_for_telegram(analysis)

# Access components
price_data = analysis.price_data
liquidity = analysis.liquidity_data
risk = analysis.risk_assessment
recommendation = analysis.recommendation
```

### 4. **PublicBotHandler** (`tg_bot/public_bot_handler.py`)

User-facing Telegram commands and interactions.

**Main Commands:**

| Command | Purpose | Example |
|---------|---------|---------|
| `/start` | Register or welcome back | - |
| `/analyze <token>` | Deep token analysis | `/analyze SOL` |
| `/buy <token> <amount>` | Execute buy order | `/buy SOL 50` |
| `/sell` | List positions to close | - |
| `/portfolio` | View holdings & P&L | - |
| `/performance` | Detailed stats & analysis | - |
| `/wallets` | Manage wallets | - |
| `/settings` | User preferences | - |
| `/help` | Command reference | - |

## Database Schema

### Users Table
```sql
CREATE TABLE users (
    user_id INTEGER PRIMARY KEY,
    telegram_username TEXT UNIQUE,
    risk_level TEXT,  -- CONSERVATIVE, MODERATE, AGGRESSIVE, DEGEN
    max_position_size_pct REAL,
    max_daily_trades INTEGER,
    max_daily_loss_usd REAL,
    require_trade_confirmation BOOLEAN,
    enable_alerts BOOLEAN,
    anti_whale_threshold_usd REAL,
    auto_adjust_risk BOOLEAN,
    learn_from_losses BOOLEAN,
    created_at TEXT,
    last_active TEXT,
    is_active BOOLEAN
)
```

### Wallets Table
```sql
CREATE TABLE wallets (
    wallet_id TEXT PRIMARY KEY,
    user_id INTEGER,
    public_key TEXT UNIQUE,
    encrypted_private_key TEXT,  -- NEVER STORE PLAIN
    source TEXT,  -- generated, imported, recovered
    created_at TEXT,
    last_used TEXT,
    balance_sol REAL,
    total_traded_usd REAL,
    is_primary BOOLEAN,
    FOREIGN KEY (user_id) REFERENCES users(user_id)
)
```

### Transactions Table
```sql
CREATE TABLE transactions (
    tx_id TEXT PRIMARY KEY,
    user_id INTEGER,
    wallet_id TEXT,
    symbol TEXT,
    action TEXT,  -- BUY, SELL
    amount_usd REAL,
    executed_at TEXT,
    status TEXT,  -- pending, completed, failed
    pnl_usd REAL,
    FOREIGN KEY (user_id) REFERENCES users(user_id),
    FOREIGN KEY (wallet_id) REFERENCES wallets(wallet_id)
)
```

### Rate Limits Table
```sql
CREATE TABLE rate_limits (
    user_id INTEGER PRIMARY KEY,
    trades_today INTEGER,
    loss_today_usd REAL,
    last_reset TEXT,
    FOREIGN KEY (user_id) REFERENCES users(user_id)
)
```

## Integration Steps

### Step 1: Install Dependencies

```bash
pip install python-telegram-bot solders pynacl
```

### Step 2: Initialize Manager

```python
from core.public_user_manager import PublicUserManager
from core.adaptive_algorithm import AdaptiveAlgorithm
from core.token_analyzer import TokenAnalyzer
from tg_bot.public_bot_handler import PublicBotHandler

# Initialize systems
user_manager = PublicUserManager()
algorithm = AdaptiveAlgorithm()
token_analyzer = TokenAnalyzer()
bot_handler = PublicBotHandler(trading_engine)
```

### Step 3: Register with Telegram App

```python
from telegram.ext import Application, CommandHandler

app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

# Register public bot commands
app.add_handler(CommandHandler("start", bot_handler.cmd_start))
app.add_handler(CommandHandler("analyze", bot_handler.cmd_analyze))
app.add_handler(CommandHandler("buy", bot_handler.cmd_buy))
app.add_handler(CommandHandler("sell", bot_handler.cmd_sell))
app.add_handler(CommandHandler("portfolio", bot_handler.cmd_portfolio))
app.add_handler(CommandHandler("performance", bot_handler.cmd_performance))
app.add_handler(CommandHandler("wallets", bot_handler.cmd_wallets))
app.add_handler(CommandHandler("settings", bot_handler.cmd_settings))
app.add_handler(CommandHandler("help", bot_handler.cmd_help))
```

### Step 4: Wire into Supervisor

```python
# In supervisor.py
public_bot = PublicBotHandler(trading_engine)

components = {
    'public_bot': {
        'handler': public_bot,
        'enabled': True,
    }
}
```

## Security Considerations

### Wallet Security
- ✅ Private keys encrypted before storage
- ✅ Never logged or transmitted unencrypted
- ✅ Per-user wallet isolation
- ✅ Rate limiting to prevent abuse

### Trade Safety
- ✅ Position size limits per user
- ✅ Daily loss limits
- ✅ Trade confirmation requirement
- ✅ Max trade size limits

### Rate Limiting
- ✅ Max daily trades per user
- ✅ Max daily loss limit
- ✅ Position size as % of wallet
- ✅ Per-symbol max trade size based on liquidity

## User Experience Flow

### New User
1. User sends `/start`
2. Bot registers user and shows welcome
3. User creates wallet with `/wallets`
4. User analyzes token with `/analyze SOL`
5. User buys with `/buy SOL 50`
6. Bot executes trade and sends confirmation
7. User tracks P&L with `/portfolio`

### Experienced User
1. User quickly analyzes tokens
2. Uses learned recommendation confidence
3. Executes trades without confirmation
4. Tracks winning/losing patterns
5. Adjusts risk level based on performance
6. Bot automatically adjusts recommendation weight based on algorithm confidence

## Performance Metrics

Track and improve:
- **Win Rate**: % of winning trades (target: >55%)
- **Average Win**: $ profit per winning trade
- **Profit Factor**: Total wins / Total losses (target: >1.5)
- **Sharpe Ratio**: Risk-adjusted returns
- **Algorithm Accuracy**: Per algorithm type

## Future Enhancements

### Phase 2: Advanced Features
- [ ] Options trading strategies
- [ ] Yield farming integration
- [ ] Staking recommendations
- [ ] Multi-chain support
- [ ] Copy trading (follow top traders)

### Phase 3: Intelligence
- [ ] ML model fine-tuning on user data
- [ ] Sentiment from social media APIs
- [ ] Whale tracking integration
- [ ] Macro indicator integration
- [ ] GRO (Grok learning) - learn from Grok's trades

### Phase 4: Scaling
- [ ] Horizontal scaling (multi-instance)
- [ ] Load balancing
- [ ] High-availability database
- [ ] Real-time analytics dashboard
- [ ] Mobile app

## Troubleshooting

### User Can't Register
```python
# Check database
user_manager.get_user_profile(user_id)  # Should return None initially

# Manual registration
success, profile = user_manager.register_user(user_id, username)
```

### Wallet Issues
```python
# Verify wallet exists
wallets = user_manager.get_user_wallets(user_id)
primary = user_manager.get_primary_wallet(user_id)

# Check balance
from solders.rpc.async_client import AsyncClient
client = AsyncClient("https://api.mainnet-beta.solana.com")
balance = await client.get_balance(PublicKey(wallet.public_key))
```

### Algorithm Not Learning
```python
# Check metrics
stats = algorithm.get_all_stats()
for algo_type, metrics in stats.items():
    print(f"{algo_type}: Confidence {metrics['confidence']}, "
          f"Win Rate {metrics['win_rate']:.1f}%")

# Verify outcomes recorded
recent = algorithm.get_recent_outcomes(limit=10)
```

## Deployment Checklist

- [ ] Database initialized at `~/.lifeos/public_users.db`
- [ ] Encryption keys configured for wallet storage
- [ ] Jupiter DEX API keys configured
- [ ] Telegram bot token configured
- [ ] Rate limits configured appropriately
- [ ] Safety checks enabled (confirm trades, limits)
- [ ] Monitoring/alerts configured
- [ ] User documentation created
- [ ] Onboarding flow tested
- [ ] Cold start test (first user)

## Success Criteria

**Must Have** (MVP):
- ✅ Users can register and create wallets
- ✅ Token analysis working with real data
- ✅ Buy/sell execution with safety checks
- ✅ Portfolio tracking and P&L calculation
- ✅ Rate limiting preventing abuse

**Should Have** (v1.0):
- Adaptive algorithm improving win rate
- User performance dashboard
- Risk adjustment based on performance
- Community features (leaderboard, tips)

**Nice to Have** (v2.0):
- Copy trading / strategy following
- Advanced risk management tools
- Mobile app integration
- Staking/yield farming

## Contact & Support

For questions or issues:
- Check `/help` command
- Review this guide
- Check algorithm stats with `/performance`
- Monitor transaction logs
