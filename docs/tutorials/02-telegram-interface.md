# Tutorial: Telegram Interface Navigation

Master the JARVIS Telegram bot interface.

## Overview

JARVIS provides a comprehensive Telegram interface for:
- Trading operations
- Market analysis
- Portfolio management
- System administration (admin only)

## Command Categories

### General Commands

| Command | Description |
|---------|-------------|
| `/start` | Welcome message and registration |
| `/help` | List all available commands |
| `/status` | System health status |

### Market Analysis

| Command | Description |
|---------|-------------|
| `/sentiment` | Full market sentiment report |
| `/report` | Alias for `/sentiment` |
| `/trending` | Trending Solana tokens |
| `/analyze <token>` | Deep token analysis |
| `/price <token>` | Current price check |

### Trading

| Command | Description |
|---------|-------------|
| `/buy <token> <amount>` | Buy a token |
| `/sell <token>` | Sell/close position |
| `/portfolio` | View open positions |
| `/history` | Trade history |

### Account Management

| Command | Description |
|---------|-------------|
| `/wallets` | Manage wallets |
| `/balance` | Check wallet balance |
| `/settings` | User preferences |
| `/performance` | Trading statistics |

### Admin Commands (Admin Only)

| Command | Description |
|---------|-------------|
| `/admin` | Admin control panel |
| `/execute <code>` | Execute Python code |
| `/logs` | View recent logs |
| `/restart <component>` | Restart a bot component |

## Detailed Command Usage

### /sentiment - Market Sentiment Report

Get a comprehensive market overview:

```
/sentiment
```

**Response:**

```
MARKET SENTIMENT REPORT
Generated: 2026-01-18 10:30 UTC

MARKET OVERVIEW
Fear & Greed Index: 65 (Greed)
BTC: $98,500 (+1.2%)
ETH: $3,450 (+2.1%)
SOL: $105 (+3.5%)

TOP MOVERS (24h)
BONK: +15.2%
WIF: +12.4%
JUP: +8.7%

GROK ANALYSIS
Sentiment: Bullish
Key Signals:
- Strong institutional buying
- Positive social sentiment on X
- Technical breakout forming

RECOMMENDATION
Market conditions favor long positions.
Risk: Moderate
```

### /analyze - Token Deep Dive

Analyze any Solana token:

```
/analyze WIF
```

**Response:**

```
TOKEN ANALYSIS: WIF (Dogwifhat)

CURRENT DATA
Price: $2.15
24h Change: +8.7%
Volume (24h): $125M
Market Cap: $2.1B
Liquidity: $45M

RISK ASSESSMENT
Risk Level: MEDIUM
Liquidity Score: 8/10
Whale Concentration: 15% top 10 holders

TECHNICAL ANALYSIS
RSI: 58 (Neutral)
MACD: Bullish
Support: $1.95
Resistance: $2.45

SENTIMENT (Grok)
Score: 72/100
Trend: Bullish
Catalysts: Community growth, meme season

RECOMMENDATION
Action: CONSIDER BUY
Entry Zone: $2.10 - $2.20
Take Profit: $2.58 (+20%)
Stop Loss: $1.93 (-10%)
Confidence: 75%
```

### /buy - Execute Trade

Buy tokens with specific amount:

```
/buy SOL 100
```

This attempts to buy $100 worth of SOL.

**Confirmation Flow:**

1. Bot shows trade details
2. User confirms or cancels
3. Trade executes via Jupiter DEX
4. Confirmation with position details

**Parameters:**
- `<token>`: Token symbol (SOL, BONK, WIF)
- `<amount>`: USD amount to trade

### /portfolio - View Positions

See all open positions:

```
/portfolio
```

**Response:**

```
YOUR PORTFOLIO

Open Positions: 3
Total Value: $1,250.00
Unrealized PnL: +$45.50 (+3.6%)

POSITIONS:

1. SOL
   Entry: $100.00 | Current: $108.50
   PnL: +$8.50 (+8.5%)
   [Details] [Close]

2. BONK
   Entry: $50.00 | Current: $52.30
   PnL: +$2.30 (+4.6%)
   [Details] [Close]

3. WIF
   Entry: $75.00 | Current: $73.20
   PnL: -$1.80 (-2.4%)
   [Details] [Close]
```

### /wallets - Wallet Management

Manage your trading wallets:

```
/wallets
```

**Menu Options:**

```
WALLET MANAGEMENT

Your Wallets: 1
Active: 7xKr...9Zpm

Actions:
[Generate New] [Import Wallet]
[Export Seed] [Set Default]
[View Balances]
```

#### Generate New Wallet

Select "Generate New" to create a new wallet:

```
NEW WALLET CREATED

Address: 8yLm...3Qnp
Status: Active

Your seed phrase (SAVE THIS!):
[View Seed Phrase]

This wallet is now ready to receive SOL.
```

#### Import Wallet

Select "Import Wallet" to import existing:

1. Bot asks for seed phrase via DM
2. Enter your 12/24 word phrase
3. Wallet is encrypted and stored

### /settings - User Preferences

Configure your preferences:

```
/settings
```

**Menu:**

```
SETTINGS

Trading:
- Risk Level: MODERATE [Change]
- Trading Mode: PAPER [Change]
- Confirmations: ON [Toggle]

Notifications:
- Trade Alerts: ON [Toggle]
- Price Alerts: ON [Toggle]
- Reports: DAILY [Change]

Limits:
- Daily Loss: $100 [Change]
- Max Position: $50 [Change]
```

## Interactive Buttons

JARVIS uses inline keyboards for easy navigation:

### Confirmation Buttons

```
Confirm this trade?

[Yes] [No]
```

### Navigation Buttons

```
[< Back] [Home] [Help]
```

### Action Buttons

```
[Buy] [Sell] [Analyze]
```

## Conversation Context

JARVIS remembers context within a conversation:

```
User: analyze SOL
JARVIS: [Shows SOL analysis]

User: buy 50
JARVIS: [Understands you mean buy $50 of SOL]
```

## Group Chat Behavior

In group chats, JARVIS:
- Responds when mentioned (@YourBot)
- Responds to crypto-related topics
- Responds to greetings
- Does NOT execute trades (DM only)

**Group Commands:**
```
@JarvisBot price SOL
```

## Error Handling

### Invalid Command

```
User: /buuy SOL
JARVIS: Unknown command. Did you mean /buy?
```

### Missing Parameters

```
User: /buy
JARVIS: Usage: /buy <token> <amount>
Example: /buy SOL 50
```

### Insufficient Balance

```
JARVIS: Insufficient balance.
Available: $25.00
Required: $50.00
```

### Rate Limit

```
JARVIS: Too many requests. Please wait 30 seconds.
```

## Admin Features

For users with admin privileges:

### /admin - Control Panel

```
ADMIN CONTROL PANEL

System Status: HEALTHY
Uptime: 3d 12h 45m

Quick Actions:
[View Logs] [Restart Bots]
[Feature Flags] [Kill Switch]
```

### /execute - Run Code

```
/execute print(1 + 1)
```

**Response:**
```
Code Executed:
Output: 2
```

**Security Notes:**
- Only admin can execute
- Sandboxed execution
- Logged for audit

## Tips

1. **Use short commands**: `/s` works for `/sentiment`
2. **Inline buttons**: Tap buttons instead of typing
3. **Context is remembered**: Follow-up messages understood
4. **DM for trades**: Trading only works in private messages
5. **Check status**: Use `/status` if bot seems slow

## Troubleshooting

### Bot Not Responding

1. Check if bot is running: `/status`
2. Try `/help` to test basic response
3. Check internet connection
4. Contact admin

### Commands Not Working

1. Ensure correct syntax
2. Check command permissions
3. Try typing command fully (no aliases)

### Slow Responses

1. Market data APIs may be slow
2. Heavy analysis takes longer
3. Rate limits may apply

## Next Steps

- [Trading Bot 101](./01-trading-bot-101.md)
- [Advanced Strategies](./03-advanced-strategies.md)
- [Command Reference](../API_DOCUMENTATION.md)

---

**Last Updated**: 2026-01-18
