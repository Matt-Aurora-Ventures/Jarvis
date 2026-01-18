# Tutorial: Understanding the Fee Structure

Learn how JARVIS's fee distribution works.

## Overview

JARVIS uses a transparent, success-based fee model:
- Fees only on profitable trades
- Clear distribution breakdown
- User revenue sharing
- Charity contribution

## Fee Structure

### Success Fee

**Rate**: 0.5% of profit on winning trades only.

| Trade Outcome | Fee |
|---------------|-----|
| Profitable (+PnL) | 0.5% of profit |
| Break-even | No fee |
| Loss (-PnL) | No fee |

**Example:**
```
Trade: Buy $1,000 SOL
Result: Sell at $1,100
Profit: $100
Fee: $100 * 0.5% = $0.50
```

### No Fee on Losses

If you lose money, you pay nothing:

```
Trade: Buy $1,000 SOL
Result: Sell at $900
Loss: -$100
Fee: $0 (no fee on losses)
```

## Fee Distribution

### How Fees Are Split

| Recipient | Percentage | Purpose |
|-----------|------------|---------|
| User | 75% | Cashback/rewards |
| Charity | 5% | Automatic donations |
| Company | 20% | Operations |

### Distribution Example

```
Trade profit: $100
Success fee: $0.50

Distribution:
- User earns: $0.375 (75%)
- Charity: $0.025 (5%)
- Company: $0.10 (20%)
```

### User Rewards

The 75% user share accumulates as rewards:

```
/rewards
```

**Response:**

```
YOUR REWARDS

Total Earned: $12.50
Available to Claim: $12.50
Pending: $0.00

This Month: $3.75
Last Month: $5.00

[Claim Rewards] [History]
```

## Viewing Fees

### Fee Summary

```
/fees
```

**Response:**

```
FEE SUMMARY

Your Trading Activity (30 days):
- Total Trades: 25
- Winning Trades: 17
- Total Profit: $450

Fees Paid:
- Total Fees: $2.25 (0.5% of $450)

Your Share (75%):
- Earned: $1.69
- Claimed: $0.50
- Available: $1.19

Impact:
- Charity: $0.11 donated
- Operations: $0.45
```

### Fee History

```
/fees history
```

**Response:**

```
FEE HISTORY

1. 2026-01-18 - SOL trade
   Profit: $25.00 | Fee: $0.125
   Your share: $0.094

2. 2026-01-17 - BONK trade
   Profit: $15.00 | Fee: $0.075
   Your share: $0.056

3. 2026-01-17 - WIF trade
   Loss: -$8.00 | Fee: $0.00
   (No fee on losses)
```

## Transparency Dashboard

### Public Fee Tracking

JARVIS maintains transparent fee records:

```
/transparency
```

**Response:**

```
TRANSPARENCY REPORT

Platform Totals (All Time):
- Total Trading Volume: $2.5M
- Total Profits Generated: $180K
- Total Fees Collected: $900

Distribution Breakdown:
- Users Earned: $675 (75%)
- Charity Donated: $45 (5%)
- Operations: $180 (20%)

Charity Recipients:
- GiveDirectly: $25
- charity:water: $20
```

### Verifiable Records

All fee transactions are logged in JSONL format:

```json
{
  "timestamp": "2026-01-18T10:30:00Z",
  "event": "FEE_COLLECTED",
  "trade_id": "trade_abc123",
  "profit_usd": 100.00,
  "fee_usd": 0.50,
  "user_share": 0.375,
  "charity_share": 0.025,
  "company_share": 0.10
}
```

## Claiming Rewards

### How to Claim

1. Check available rewards: `/rewards`
2. Click [Claim Rewards]
3. Confirm the claim
4. Rewards sent to your wallet

### Minimum Claim

- Minimum claim: $1.00
- Claims processed instantly
- No claim fees

### Claim History

```
/rewards history
```

**Response:**

```
CLAIM HISTORY

1. 2026-01-15 - Claimed $5.00
   Sent to: 7xKr...9Zpm
   TX: https://solscan.io/tx/...

2. 2026-01-01 - Claimed $3.50
   Sent to: 7xKr...9Zpm
   TX: https://solscan.io/tx/...
```

## Why This Model?

### Benefits for Users

1. **Aligned Incentives**: We only profit when you profit
2. **Revenue Sharing**: 75% of fees go back to users
3. **No Hidden Fees**: Clear, transparent pricing
4. **Loss Protection**: No fees on losing trades

### Benefits for Platform

1. **Sustainable Growth**: Revenue tied to user success
2. **Quality Focus**: Incentivized to improve win rates
3. **Trust Building**: Transparency builds confidence
4. **Fair Model**: Success-based is ethical

## Comparison to Competitors

| Platform | Fee Model | Loss Fees |
|----------|-----------|-----------|
| **JARVIS** | 0.5% profit share | No |
| Typical Bot | 1-2% all trades | Yes |
| DEX | 0.25-0.3% swap | Yes |
| CEX | 0.1-0.5% maker/taker | Yes |

JARVIS only charges on success, making it more user-friendly.

## Charity Component

### How It Works

5% of all fees automatically go to verified charities:

1. **Selection**: Charities vetted for efficiency
2. **Distribution**: Monthly donations
3. **Transparency**: Public reporting
4. **Impact**: Real-world good

### Current Recipients

- **GiveDirectly**: Direct cash transfers
- **charity:water**: Clean water projects
- **Code.org**: Computer science education

### Impact Report

```
/charity
```

**Response:**

```
CHARITY IMPACT

Your Contribution: $0.25
Total Platform Donation: $45.00

Impact Estimate:
- 2 people received direct cash aid
- 1 person gained water access
- 5 students learning to code

Thank you for trading with purpose!
```

## Projections

### User Earnings Example

```
Monthly Trading:
- 20 trades
- 60% win rate (12 winners)
- $50 avg profit per winner
- Total profit: $600

Fee Calculation:
- Success fee: $600 * 0.5% = $3.00
- Your share: $3.00 * 75% = $2.25/month

Annual earnings: $27.00 (just from fee sharing)
```

### Scaling Potential

As you trade more profitably, rewards scale:

| Monthly Profit | Fee | Your Share |
|----------------|-----|------------|
| $600 | $3.00 | $2.25 |
| $2,000 | $10.00 | $7.50 |
| $10,000 | $50.00 | $37.50 |
| $50,000 | $250.00 | $187.50 |

## FAQ

### Q: Why only 0.5%?

A: We believe in fair pricing. 0.5% on profits (not volume) is sustainable for us while being friendly to users.

### Q: Can fees change?

A: Fee structure is locked for existing users. Any changes apply only to new users with advance notice.

### Q: How is charity chosen?

A: We select charities based on:
- Efficiency (>80% to programs)
- Transparency (public reporting)
- Impact (measurable outcomes)

### Q: What if I don't want charity?

A: The 5% charity allocation is built into the platform. Consider it a feature that makes crypto trading more meaningful.

## Summary

JARVIS fee model:
1. **0.5% success fee** - Only on profits
2. **75% to users** - Revenue sharing
3. **5% to charity** - Giving back
4. **20% operations** - Sustainability
5. **Transparent** - All transactions logged

## Next Steps

- [Quick Start Guide](../QUICKSTART.md)
- [Trading Bot 101](./01-trading-bot-101.md)
- [Fee Distribution Code](../../core/fee_distribution.py)

---

**Last Updated**: 2026-01-18
