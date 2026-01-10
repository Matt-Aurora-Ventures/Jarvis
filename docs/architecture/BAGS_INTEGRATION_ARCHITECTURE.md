# JARVIS x Bags.fm Integration Architecture

> Technical architecture for the Bags.fm integration, staking system, and tokenomics infrastructure.

## Overview

This document covers the trading and tokenomics layer added on top of the core JARVIS platform.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           NORMIE LAYER (FIAT)                                │
├─────────────────────────────────────────────────────────────────────────────┤
│  ┌───────────────┐  ┌───────────────┐  ┌───────────────┐                    │
│  │ Stripe        │  │ Credit        │  │ API           │                    │
│  │ Payments      │──│ Manager       │──│ Metering      │                    │
│  │               │  │               │  │               │                    │
│  │ Checkout      │  │ Balance       │  │ Rate Limiting │                    │
│  │ Webhooks      │  │ Transactions  │  │ Usage Logs    │                    │
│  └───────────────┘  └───────────────┘  └───────────────┘                    │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           CRYPTO LAYER (SOL)                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│  ┌───────────────┐  ┌───────────────┐  ┌───────────────┐                    │
│  │ Bags.fm       │  │ Staking       │  │ Treasury      │                    │
│  │ Integration   │──│ Contract      │──│ Management    │                    │
│  │               │  │               │  │               │                    │
│  │ Trade Router  │  │ KR8TIV Token  │  │ Multi-Wallet  │                    │
│  │ Fee Collector │  │ SOL Rewards   │  │ Risk Control  │                    │
│  │ Partner API   │  │ Multipliers   │  │ Distribution  │                    │
│  └───────────────┘  └───────────────┘  └───────────────┘                    │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Component Details

### 1. Bags.fm Integration (`/integrations/bags`)

#### Trade Router
- Accepts trade requests from JARVIS trading modules
- Routes through Bags.fm for partner fee earning
- Falls back to Jupiter if Bags is unavailable

```python
# Trade flow
1. Quote request → Bags API /v1/quote
2. Transaction → Bags API /v1/swap
3. Sign → User wallet
4. Execute → Solana RPC
5. Track → Event system
```

#### Fee Collector
- Monitors partner fee accumulation
- Claims fees to designated wallet
- Triggers treasury distribution

```python
# Fee rate
Platform fee: 1% of volume
Partner share: 25% of platform fee = 0.25% of volume

# Example
$100,000 volume → $1,000 platform fee → $250 partner fee
```

### 2. Staking System (`/core/staking`, `/contracts`)

#### Smart Contract (Anchor)
- KR8TIV token staking
- Time-weighted multipliers
- SOL reward distribution

```rust
// Multiplier tiers
0-6 days:   1.0x
7-29 days:  1.5x
30-89 days: 2.0x
90+ days:   2.5x
```

#### Auto-Compound Service
- Opt-in automatic reinvestment
- Threshold-based triggers (default: 0.01 SOL)
- Claim → Swap → Stake cycle

```python
# Compound APY vs Simple APY
Simple APY:   15%
Compound APY: 16.18% (daily compounding)
Boost:        +7.9%
```

### 3. Treasury Management (`/core/treasury`)

#### Wallet Architecture
```
Treasury (100%)
├── Reserve Wallet (60%)
│   └── Cold storage, multisig 2-of-3
├── Active Wallet (30%)
│   └── Trading bot, limited daily cap
└── Profit Wallet (10%)
    └── Weekly distribution buffer
```

#### Trading Bot
- DCA strategies (SOL/USDC, KR8TIV)
- Mean reversion trading
- All trades via Bags (earn fees)
- Risk controls: 10% max position, 5% daily loss limit, 15% drawdown halt

#### Distribution System
```
Weekly Distribution:
├── 60% → Staking Rewards Pool
├── 25% → Operations Wallet
└── 15% → Development Reserve

Triggered: Sunday 00:00 UTC
Minimum: 0.1 SOL
```

### 4. Credit System (`/core/payments`)

#### Packages
| Package | Credits | Bonus | Price | Points |
|---------|---------|-------|-------|--------|
| Starter | 100     | 0     | $25   | 25     |
| Pro     | 500     | 50    | $100  | 150    |
| Whale   | 3000    | 500   | $500  | 1000   |

#### API Metering
```python
# Endpoint costs
/api/trade/quote:    1 credit
/api/trade/execute:  5 credits
/api/analyze:        10 credits
/api/backtest:       50 credits

# Rate limits by tier
Free:    10 req/min
Starter: 50 req/min
Pro:     100 req/min
Whale:   500 req/min
```

### 5. Analytics (`/core/analytics`)

#### Event Types
```python
# User events
user.registered, user.login

# Credit events
credits.purchased, credits.consumed

# Trading events
trade.quote, trade.executed, trade.failed

# Staking events
stake.created, stake.unstaked, rewards.claimed

# Fee events
fee.collected, fee.distributed
```

#### Metrics Aggregation
- Hourly and daily aggregates
- Per-user and global statistics
- Real-time WebSocket feed

## Data Flow Diagrams

### Credit Purchase Flow
```
User → Stripe Checkout → Webhook → Credit Manager → Balance Update
                              ↓
                         Event Tracker
```

### Trade Execution Flow
```
User → API → Credit Check → Bags Quote → Transaction → Wallet Sign
                              ↓
                         Bags Execute → Solana → Confirmation
                              ↓
                         Fee Tracking → Partner Fee Pool
```

### Staking Rewards Flow
```
Treasury → Weekly Distribution → Staking Pool
                                       ↓
User → Claim Rewards → Multiplier Calc → SOL Transfer
        ↓ (if auto-compound)
     Swap to KR8TIV → Stake
```

## Security Considerations

### API Security
- JWT tokens (1h expiry) + API keys
- Rate limiting per tier
- Credit-gated expensive endpoints
- Webhook signature verification

### Wallet Security
- Hot/cold wallet separation
- Multisig for large withdrawals
- Daily trading limits
- Key encryption at rest

### Circuit Breakers
```python
# Automatic halts
if daily_loss > 5%:    pause_trading()
if single_trade > 10%: reject_trade()
if drawdown > 15%:     halt_all()
```

## Deployment

### Docker Services
```yaml
api:        FastAPI main server
flask:      Legacy API
redis:      Caching, rate limiting
worker:     Background jobs (distribution, compound)
```

### CI/CD Pipeline
- PR checks: lint, test, type check, security scan
- Staging: auto-deploy on main push
- Production: manual approval, blue-green deployment
- Contracts: separate workflow, devnet first

## File Structure

```
/core
├── /analytics     - Event tracking, metrics
├── /payments      - Stripe, credit metering
├── /staking       - Auto-compound service
├── /trading       - Bags adapter, treasury bot
└── /treasury      - Wallet management, distribution

/integrations
└── /bags          - Bags.fm client, fee collector

/contracts
└── /staking       - Anchor staking program

/api
├── /routes        - FastAPI endpoints
└── fastapi_app.py - Main application

/frontend
└── /components
    ├── /staking   - Staking UI
    ├── /credits   - Credit purchase UI
    └── /admin     - Revenue dashboard
```

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 3.7.0   | 2026-01 | Bags.fm integration, complete staking system |
| 3.6.0   | 2024-01 | Treasury management, credit system foundation |
