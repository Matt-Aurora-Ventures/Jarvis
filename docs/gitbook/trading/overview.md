# Trading System Overview

Jarvis's autonomous trading engine is the most mature domain, designed to prove the concept of AI-driven capital management on Solana.

---

## Quick Stats

- **81+ strategies** across 6 categories
- **Max 50 concurrent positions**
- **4-tier risk classification**
- **60-second stop-loss monitoring**
- **Live on Jupiter DEX**
- **Transparent on-chain execution**

---

## Supported Exchanges

| Exchange | Integration | Status | Fee Sharing |
|----------|-------------|--------|-------------|
| **Jupiter** | Lite API + Quote API | ✅ Live | Yes (referral) |
| **Bags.fm** | Partner API | ✅ Live | Yes (partner fees) |
| **DexScreener** | Price Oracle | ✅ Live | N/A |
| **Raydium** | Direct (planned) | 🔜 Q2 2026 | Yes |
| **Orca** | Direct (planned) | 🔜 Q2 2026 | Yes |

---

## Strategy Categories

Jarvis employs **81+ trading strategies** organized into 6 categories:

### 1. Momentum (12 strategies)

**Philosophy**: Ride trends and breakouts

| Strategy | Description | Win Rate | Best For |
|----------|-------------|----------|----------|
| **RSI Divergence** | Buy when price makes lower low but RSI makes higher low | ~65% | Reversal catching |
| **MACD Crossover** | Enter on bullish cross, exit on bearish | ~60% | Trend confirmation |
| **Breakout** | Enter on volume-confirmed resistance break | ~58% | Strong moves |
| **Moving Average Cross** | Golden cross (50MA > 200MA) | ~55% | Long-term trends |

### 2. Mean Reversion (8 strategies)

**Philosophy**: Price returns to average over time

| Strategy | Description | Win Rate | Best For |
|----------|-------------|----------|----------|
| **Bollinger Bounce** | Buy at lower band, sell at upper band | ~62% | Ranging markets |
| **Oversold Bounce** | Buy RSI <30, sell RSI >70 | ~60% | Quick reversals |
| **Z-Score Reversion** | Enter when price deviates >2σ from mean | ~58% | Statistical edges |

### 3. Sentiment (15 strategies)

**Philosophy**: AI-powered social and news sentiment

| Strategy | Description | Win Rate | Best For |
|----------|-------------|----------|----------|
| **Grok Sentiment Score** | Buy high-conviction Grok picks | ~70% | AI alpha |
| **Social Volume Spike** | Enter on sudden Twitter/Reddit activity | ~55% | Hype plays |
| **News Event Trading** | Trade on major announcements | ~52% | Event-driven |
| **Influencer Mentions** | Track crypto influencer callouts | ~48% | High-risk/reward |

### 4. On-Chain (18 strategies)

**Philosophy**: Analyze blockchain data for edge

| Strategy | Description | Win Rate | Best For |
|----------|-------------|----------|----------|
| **Whale Tracking** | Follow large wallets (>$100K) | ~65% | Smart money |
| **Holder Distribution** | Buy when concentration decreases | ~60% | Distribution analysis |
| **Liquidity Inflows** | Enter when LP adds significantly | ~58% | Safety signals |
| **Dormant Wallet Activity** | Track old wallets waking up | ~55% | Long-term holders moving |

### 5. Liquidity (10 strategies)

**Philosophy**: Volume and liquidity are king

| Strategy | Description | Win Rate | Best For |
|----------|-------------|----------|----------|
| **Volume Breakout** | Enter on 3x+ average volume | ~62% | Strong momentum |
| **Bid/Ask Spread** | Only trade tight spreads (<0.5%) | ~58% | Efficient execution |
| **Liquidity Depth** | Require $10K+ in top 3 levels | ~56% | Large orders |

### 6. Arbitrage (6 strategies)

**Philosophy**: Exploit price inefficiencies

| Strategy | Description | Win Rate | Best For |
|----------|-------------|----------|----------|
| **Cross-DEX Arb** | Buy Raydium, sell Jupiter (or vice versa) | ~80% | Risk-free profit |
| **CEX-DEX Arb** | Exploit CEX/DEX price gaps | ~75% | Market inefficiencies |
| **Triangular Arb** | 3-way swaps for profit | ~70% | Complex trades |

---

## Risk Management

### Position Sizing by Risk Tier

Every token is classified into a risk tier based on:
- Market capitalization
- Daily trading volume
- Liquidity depth
- Holder distribution
- On-chain metrics

| Risk Level | Market Cap | Liquidity | Position Size | Max Positions |
|------------|------------|-----------|---------------|---------------|
| **ESTABLISHED** | >$500M | >$1M daily | 1.0x (full) | Unlimited |
| **MID** | >$50M | >$100K daily | 0.85x | Max 20 |
| **MICRO** | >$1M | >$20K daily | 0.7x | Max 10 |
| **SHITCOIN** | <$1M | <$20K daily | 0.5x (half) | Max 5 |

**Base Position Size**: 2% of treasury balance

**Example**:
- Treasury: 100 SOL
- Base position: 2 SOL
- ESTABLISHED token: 2 SOL (1.0x)
- MID token: 1.7 SOL (0.85x)
- MICRO token: 1.4 SOL (0.7x)
- SHITCOIN token: 1 SOL (0.5x)

### Stop Loss & Take Profit

| Risk Tier | Stop Loss | Take Profit | Trailing Stop |
|-----------|-----------|-------------|---------------|
| **ESTABLISHED** | -15% | +30% | Optional |
| **MID** | -12% | +25% | Optional |
| **MICRO** | -10% | +20% | Recommended |
| **SHITCOIN** | -7% | +15% | Required |

**Monitoring Frequency**: Every 60 seconds

**Execution**:
- Stops are **soft stops** (checked in background job)
- When triggered, automatic market sell via Jupiter
- Logs reason and outcome for learning

### Circuit Breakers

| Condition | Action |
|-----------|--------|
| **3 consecutive losses** | Pause all trading for 1 hour |
| **Daily loss limit (-10%)** | Halt trading until next day (UTC reset) |
| **Low balance (<0.01 SOL)** | Alert admin, no new positions |
| **API failure (3+ errors)** | Switch to fallback data source |
| **Emergency mode** | Close all positions immediately |

---

## Execution Engine

### Trade Flow

```
1. Signal Generated
   ├─► Strategy fires buy/sell signal
   └─► Consensus check (minimum 3 strategies agree)

2. Risk Check
   ├─► Verify position limits not exceeded
   ├─► Check risk tier classification
   ├─► Confirm liquidity meets minimum
   └─► Validate circuit breaker state

3. Quote Request
   ├─► Jupiter quote API for best price
   ├─► Slippage tolerance: 1% default
   ├─► Route optimization (multi-hop if better)
   └─► Priority fee calculation

4. Transaction Building
   ├─► Construct Solana transaction
   ├─► Add compute budget instruction
   ├─► Add priority fee instruction
   └─► Sign with encrypted wallet

5. Submission
   ├─► Send to Helius RPC (priority)
   ├─► Fallback to public RPC if needed
   ├─► Transaction simulation (pre-flight)
   └─► Confirmation polling (up to 30s)

6. Post-Trade
   ├─► Log to PostgreSQL audit table
   ├─► Update .positions.json
   ├─► Send Telegram notification
   └─► Record to memory for learning
```

### Example Trade

```json
{
  "token": "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
  "symbol": "USDC",
  "action": "BUY",
  "amount_sol": 2.0,
  "entry_price": 1.0001,
  "slippage_bps": 100,
  "stop_loss": 0.8501,
  "take_profit": 1.3001,
  "risk_tier": "ESTABLISHED",
  "strategies": ["grok_sentiment", "whale_tracking", "volume_breakout"],
  "confidence": 0.78,
  "timestamp": "2026-01-23T14:30:00Z"
}
```

---

## Performance Tracking

### Metrics

| Metric | Description | Target |
|--------|-------------|--------|
| **Win Rate** | Percentage of profitable trades | >60% |
| **Average P&L** | Profit per trade | >5% |
| **Max Drawdown** | Largest peak-to-trough decline | <20% |
| **Sharpe Ratio** | Risk-adjusted returns | >1.5 |
| **Recovery Time** | Time to recover from drawdown | <7 days |

### Position Lifecycle

```
Entry → Monitoring → Exit
  │         │          │
  │         ├─► TP hit? → Close with profit
  │         ├─► SL hit? → Close with loss
  │         └─► Manual? → User closes
  │
  └─► Logged to audit table
       └─► Performance updated
            └─► Strategy scores adjusted
```

---

## Safety Rails

### Hard Limits (Code-Enforced)

```python
MAX_POSITIONS = 50
MAX_POSITION_SIZE_PCT = 2.0  # 2% of treasury
MAX_CORRELATED_POSITIONS = 10  # Same sector
MAX_HIGH_RISK_PCT = 20.0  # MICRO + SHITCOIN combined
MIN_LIQUIDITY_USD = 1000  # $1K daily volume
DAILY_LOSS_LIMIT_PCT = 10.0  # -10% max loss per day
```

### Approval Requirements

| Trade Value | Approval Required |
|-------------|------------------|
| < $100 | Automatic |
| $100 - $1,000 | Telegram notification |
| $1,000 - $10,000 | Telegram approval required |
| > $10,000 | Multi-sig approval required |

### Emergency Controls

**Kill Switch**:
```bash
# Set in .env to immediately halt all trading
LIFEOS_KILL_SWITCH=true
```

**Telegram Commands**:
```
/emergency_close   # Close all positions immediately
/pause_trading     # Pause new positions, keep monitoring
/resume_trading    # Resume normal operations
/treasury_status   # Show current state
```

---

## Backtesting

Jarvis includes a comprehensive backtesting framework:

**Features**:
- Historical data from DexScreener, CoinGecko
- Strategy-by-strategy performance analysis
- Walk-forward optimization
- Monte Carlo simulation for risk assessment

**Usage**:
```bash
python scripts/backtest_strategy.py \
  --strategy grok_sentiment \
  --start-date 2025-01-01 \
  --end-date 2026-01-01 \
  --initial-balance 100
```

**Output**:
- Win rate, avg P&L, max drawdown
- Equity curve chart
- Trade-by-trade breakdown
- Optimal parameters

---

## Live Monitoring

### Web Dashboard

Visit `http://localhost:8080` to see:
- Real-time open positions
- Recent trades with outcomes
- Performance charts
- Strategy leaderboard
- Risk metrics

### Telegram Bot

Send `/demo` to [@Jarviskr8tivbot](https://t.me/Jarviskr8tivbot) for:
- **Sentiment Hub**: Live market sentiment
- **Treasury Signals**: What the treasury bot is trading
- **AI Picks**: High-conviction Grok recommendations
- **Charts**: Real-time price charts
- **Graduations**: Latest bags.fm token launches

---

## Next Steps

- **Configure Strategies** → Edit `bots/treasury/trading.py`
- **Adjust Risk Parameters** → Edit `.env` file
- **Enable Live Trading** → Set `TREASURY_LIVE_MODE=true`
- **View Performance** → Open web dashboard
- **Get Alerts** → Configure Telegram notifications

---

**Ready to start trading?** → [Installation Guide](../getting-started/installation.md)

**Want to understand the architecture?** → [Architecture Overview](../architecture/overview.md)
