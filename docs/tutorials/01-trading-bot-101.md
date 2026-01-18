# Tutorial: Trading Bot 101

Learn how to set up and execute your first trade with JARVIS.

## Prerequisites

- JARVIS running (see [Quick Start](../QUICKSTART.md))
- Telegram bot responding to commands
- Understanding of cryptocurrency trading basics

## Overview

This tutorial covers:
1. Setting up a wallet
2. Analyzing tokens
3. Executing your first trade
4. Managing positions
5. Understanding risk levels

## Part 1: Setting Up Your Wallet

### Step 1.1: Generate a New Wallet

In Telegram, send:

```
/wallets
```

Select **"Generate New Wallet"** from the menu.

JARVIS will create a new Solana wallet with:
- Public address (safe to share)
- Encrypted private key (stored securely)

**Response:**

```
Wallet Generated

Address: 7xKr...9Zpm
Status: Active
Balance: 0 SOL

IMPORTANT: Fund this wallet to start trading.
```

### Step 1.2: Fund Your Wallet

Send SOL to your new wallet address:

1. Copy the address from the bot response
2. Send SOL from your existing wallet or exchange
3. Wait for confirmation (usually 1-2 minutes)

Check your balance:

```
/balance
```

### Step 1.3: Import Existing Wallet (Alternative)

If you have an existing wallet:

```
/wallets import
```

Enter your seed phrase when prompted (sent securely via DM).

**Security Notes:**
- Never share your seed phrase publicly
- JARVIS encrypts all private keys with PBKDF2 + Fernet
- Only the admin can access encrypted keys

## Part 2: Analyzing Tokens

### Step 2.1: Get Token Sentiment

Before trading, analyze the token:

```
/analyze SOL
```

**Response:**

```
TOKEN ANALYSIS: SOL (Solana)

SENTIMENT SCORE: 78/100 (Bullish)
RISK LEVEL: LOW

Price: $105.50 (+2.3% 24h)
Volume: $1.2B (24h)
Market Cap: $45B

Technical Indicators:
- RSI: 62 (Neutral)
- MACD: Bullish crossover
- MA: Above 50-day

Whale Activity:
- 3 large buys in last hour
- Net flow: +$2.5M

RECOMMENDATION: BUY
Confidence: 85%
Suggested Entry: $105.00
Take Profit: $126.00 (+20%)
Stop Loss: $94.95 (-10%)
```

### Step 2.2: Understanding Risk Levels

JARVIS classifies tokens into risk tiers:

| Level | Description | Example |
|-------|-------------|---------|
| `LOW` | Established tokens, high liquidity | SOL, ETH, BTC |
| `MEDIUM` | Known projects, good liquidity | JUP, BONK, WIF |
| `HIGH` | Newer tokens, moderate liquidity | New launches |
| `EXTREME` | Pump.fun tokens, low liquidity | Meme coins |

### Step 2.3: Get Trending Tokens

See what's moving:

```
/trending
```

**Response:**

```
TRENDING TOKENS (Solana)

1. SOL +5.2% - $105.50
2. BONK +12.3% - $0.000028
3. WIF +8.7% - $2.15
4. JUP +3.1% - $0.85
5. PYTH +6.4% - $0.45
```

## Part 3: Executing Your First Trade

### Step 3.1: Start with Paper Trading

Before risking real funds, use paper trading:

```
/settings
```

Select **"Trading Mode"** > **"Paper Trading"**

Paper trades simulate real trades without using actual funds.

### Step 3.2: Buy a Token

Execute a buy:

```
/buy SOL 50
```

This buys $50 worth of SOL.

**Confirmation Prompt:**

```
TRADE CONFIRMATION

Action: BUY
Token: SOL
Amount: $50 USD
Current Price: $105.50
Estimated SOL: 0.474

Take Profit: $126.60 (+20%)
Stop Loss: $94.95 (-10%)

Confirm trade? [Yes] [No]
```

Select **[Yes]** to execute.

### Step 3.3: Trade Execution

**Success Response:**

```
TRADE EXECUTED

Position Opened:
- Token: SOL
- Entry: $105.50
- Amount: 0.474 SOL ($50.00)
- TP: $126.60
- SL: $94.95

Status: ACTIVE
Position ID: pos_abc123
```

### Step 3.4: Understanding Trade Parameters

| Parameter | Description | Default |
|-----------|-------------|---------|
| Amount | USD value to trade | Required |
| Take Profit | Exit price for profit | Based on grade |
| Stop Loss | Exit price for loss | Based on grade |
| Slippage | Price tolerance | 1% |

## Part 4: Managing Positions

### Step 4.1: View Open Positions

```
/portfolio
```

**Response:**

```
OPEN POSITIONS (1)

1. SOL
   Entry: $105.50
   Current: $107.20
   PnL: +$0.81 (+1.6%)
   TP: $126.60 | SL: $94.95

Total Unrealized PnL: +$0.81
```

### Step 4.2: Monitor Position

Get detailed position info:

```
/position SOL
```

**Response:**

```
POSITION DETAILS: SOL

Entry: $105.50
Current: $107.20
Change: +$1.70 (+1.6%)

Amount: 0.474 SOL
Value: $50.81

Take Profit: $126.60 (+20%)
Stop Loss: $94.95 (-10%)

Status: ACTIVE
Opened: 2 hours ago

Actions:
[Close Position] [Update TP/SL]
```

### Step 4.3: Close Position Manually

```
/sell SOL
```

**Confirmation:**

```
CLOSE POSITION

Token: SOL
Entry: $105.50
Exit: $107.20
PnL: +$0.81 (+1.6%)

Confirm close? [Yes] [No]
```

### Step 4.4: Automatic Exit

Positions auto-close when:
- Price hits Take Profit target
- Price hits Stop Loss target
- You manually close

**TP Hit Notification:**

```
TAKE PROFIT HIT

SOL position closed!
Entry: $105.50
Exit: $126.60
PnL: +$10.00 (+20.0%)

Congrats!
```

## Part 5: Risk Management

### Step 5.1: Configure Risk Level

```
/settings
```

Select **"Risk Level"**:

| Level | Position Size | TP | SL |
|-------|--------------|-----|-----|
| CONSERVATIVE | 1% of capital | 10% | 5% |
| MODERATE | 2% of capital | 20% | 10% |
| AGGRESSIVE | 5% of capital | 30% | 15% |
| DEGEN | 10% of capital | 50% | 25% |

### Step 5.2: Set Daily Loss Limit

Protect yourself from large losses:

```
/settings
```

Select **"Risk Limits"** > **"Daily Loss Limit"**

Enter maximum daily loss (e.g., $100).

Trading pauses if limit is hit.

### Step 5.3: Position Size Limits

JARVIS enforces:
- **Max single trade**: $100 default
- **Max daily volume**: $500 default
- **Max concurrent positions**: 50

### Step 5.4: Grade-Based TP/SL

JARVIS adjusts TP/SL based on sentiment grade:

| Grade | Take Profit | Stop Loss |
|-------|-------------|-----------|
| A+ | 30% | 8% |
| A | 30% | 8% |
| B+ | 20% | 10% |
| B | 18% | 12% |
| C | 10% | 15% |
| D | 5% | 20% |

Higher conviction = wider TP, tighter SL.

## Part 6: Performance Tracking

### View Trading Performance

```
/performance
```

**Response:**

```
TRADING PERFORMANCE

Period: Last 30 days

Total Trades: 25
Win Rate: 68%
Winning: 17 | Losing: 8

Total PnL: +$125.50
Best Trade: +$45.00 (SOL)
Worst Trade: -$12.50 (BONK)

Algorithm Accuracy:
- Sentiment: 72%
- Technical: 65%
- Whale: 70%
```

## Summary

You've learned:
- How to set up and fund a wallet
- How to analyze tokens before trading
- How to execute and manage trades
- How to configure risk parameters
- How to track performance

## Next Steps

- [Telegram Interface Guide](./02-telegram-interface.md)
- [Advanced Strategies](./03-advanced-strategies.md)
- [Dexter ReAct Agent](./04-dexter-react.md)

## Tips

1. **Start with paper trading** until you're comfortable
2. **Always analyze** before trading
3. **Never risk more** than you can afford to lose
4. **Use stop losses** on every trade
5. **Review performance** regularly

---

**Last Updated**: 2026-01-18
