# Tutorial: Advanced Trading Strategies

Learn how to combine JARVIS signals for optimal trading decisions.

## Overview

This tutorial covers:
1. Multi-signal confirmation
2. Algorithm weighting
3. Custom strategy creation
4. Risk-adjusted position sizing
5. Portfolio management

## Part 1: Understanding JARVIS Signals

### Signal Sources

JARVIS uses 8 algorithm types:

| Algorithm | Description | Weight |
|-----------|-------------|--------|
| Sentiment | Grok AI analysis | 1.0 (Primary) |
| Liquidation | Support/resistance levels | 0.8 |
| Whale | Large transaction activity | 0.8 |
| Technical | MA, RSI, MACD | 0.7 |
| News | Catalyst detection | 0.6 |
| Momentum | Trend following | 0.6 |
| Reversal | Pattern detection | 0.5 |
| Volume | Surge detection | 0.5 |

### Signal Strength

Each signal provides:
- **Score**: 0-100 (higher = more bullish)
- **Confidence**: How reliable the signal is
- **Direction**: BUY, SELL, or HOLD

## Part 2: Multi-Signal Confirmation

### The Confirmation Principle

Never trade on a single signal. Require multiple confirmations:

```
Strong Buy: 3+ signals agree (BUY) with confidence >70%
Moderate Buy: 2 signals agree (BUY) with confidence >60%
Hold: Mixed signals or low confidence
Avoid: 2+ signals say SELL
```

### Example: Perfect Setup

```
TOKEN: SOL

Signals:
1. Sentiment: BUY (85% confidence) - Grok bullish
2. Whale: BUY (78% confidence) - Accumulation
3. Technical: BUY (72% confidence) - MACD crossover
4. Volume: BUY (68% confidence) - Surge detected

Result: STRONG BUY
Combined Confidence: 82%
```

### Example: Conflicting Signals

```
TOKEN: BONK

Signals:
1. Sentiment: BUY (75% confidence)
2. Whale: SELL (65% confidence) - Distribution
3. Technical: HOLD (55% confidence)
4. Volume: BUY (60% confidence)

Result: HOLD
Reason: Whale distribution conflicts with sentiment
```

## Part 3: The Decision Matrix

### How JARVIS Combines Signals

The Decision Matrix weighs and combines signals:

```python
def calculate_combined_signal(signals):
    weighted_sum = 0
    total_weight = 0

    for signal in signals:
        weight = ALGORITHM_WEIGHTS[signal.type]
        weighted_sum += signal.score * weight * signal.confidence
        total_weight += weight

    return weighted_sum / total_weight
```

### Weight Adjustment

Algorithms earn/lose weight based on performance:

```
If algorithm accuracy > 70%:
    weight += 0.1 (max 1.5)

If algorithm accuracy < 50%:
    weight -= 0.1 (min 0.3)
```

### Viewing Algorithm Performance

```
/performance algorithms
```

**Response:**

```
ALGORITHM PERFORMANCE

1. Sentiment
   Signals: 150 | Wins: 108 | Accuracy: 72%
   Weight: 1.0 (Primary)

2. Whale
   Signals: 85 | Wins: 60 | Accuracy: 71%
   Weight: 0.85

3. Technical
   Signals: 200 | Wins: 130 | Accuracy: 65%
   Weight: 0.7

4. Volume
   Signals: 120 | Wins: 66 | Accuracy: 55%
   Weight: 0.55 (Reduced)
```

## Part 4: Risk-Adjusted Position Sizing

### Position Size Formula

```
Position Size = Base Size * Risk Multiplier * Signal Confidence

Where:
- Base Size = Portfolio % (1-10% based on risk level)
- Risk Multiplier = Token Risk Factor (0.15 - 1.0)
- Signal Confidence = Combined confidence (0.5 - 1.0)
```

### Token Risk Multipliers

| Token Type | Multiplier | Example |
|------------|------------|---------|
| Established | 1.0 | SOL, ETH, BTC |
| Mid-cap | 0.5 | JUP, BONK, WIF |
| Micro-cap | 0.25 | New projects |
| High-risk | 0.15 | Pump.fun tokens |

### Example Calculation

```
Portfolio: $10,000
Risk Level: MODERATE (2% base)
Token: SOL (Established = 1.0)
Signal Confidence: 85%

Position Size = $10,000 * 0.02 * 1.0 * 0.85
             = $170
```

### High-Risk Token Example

```
Portfolio: $10,000
Risk Level: MODERATE (2% base)
Token: PUMP (High-risk = 0.15)
Signal Confidence: 75%

Position Size = $10,000 * 0.02 * 0.15 * 0.75
             = $22.50
```

## Part 5: Strategy Templates

### Strategy 1: Conservative Accumulation

**Goal**: Steady portfolio growth with minimal risk.

**Rules:**
- Only trade established tokens (SOL, ETH, BTC)
- Require 3+ confirming signals
- Minimum 80% confidence
- 1% position size
- 10% TP, 5% SL

**Setup:**
```
/settings risk CONSERVATIVE
```

### Strategy 2: Momentum Trading

**Goal**: Catch trending tokens early.

**Rules:**
- Focus on trending tokens
- Require sentiment + volume signals
- Minimum 70% confidence
- 2% position size
- 20% TP, 10% SL

**Setup:**
```
/settings risk MODERATE
```

**Watchlist:**
```
/trending
```

### Strategy 3: Whale Following

**Goal**: Follow smart money movements.

**Rules:**
- Trade only when whale signal triggers
- Require whale + sentiment agreement
- Track large wallet accumulation
- 3% position size
- 25% TP, 12% SL

**Monitoring:**
```
/whales SOL
```

### Strategy 4: Degen Micro-Cap

**Goal**: High risk, high reward micro-caps.

**Rules:**
- Small positions only (0.5% max)
- New tokens with strong sentiment
- Quick in/out (24-48 hours)
- 50% TP, 25% SL

**Setup:**
```
/settings risk DEGEN
```

**WARNING**: High risk of total loss.

## Part 6: Portfolio Management

### Diversification Rules

JARVIS enforces:
- Max 20% in any single token
- Max 50 concurrent positions
- Sector diversification (don't all-in memes)

### Portfolio Rebalancing

Check portfolio allocation:

```
/portfolio allocation
```

**Response:**

```
PORTFOLIO ALLOCATION

By Token:
SOL: 35% ($875)
BONK: 15% ($375)
WIF: 12% ($300)
USDC: 38% ($950)

By Risk:
LOW: 35%
MEDIUM: 27%
HIGH: 0%
CASH: 38%

Recommendations:
- Consider reducing SOL (>30% in single token)
- Cash position is healthy (38%)
```

### Exit Strategy Management

Set portfolio-wide exit rules:

```
/settings exits
```

Options:
- **Trailing Stop**: Move SL up as price rises
- **Time-based**: Exit if no movement in X days
- **Portfolio Heat**: Exit positions if total drawdown >15%

## Part 7: Backtesting Strategies

### Run Backtest

Test a strategy on historical data:

```
/backtest momentum 30d
```

**Response:**

```
BACKTEST RESULTS: Momentum Strategy
Period: Last 30 days

Simulated Trades: 45
Win Rate: 62%
Total Return: +18.5%
Max Drawdown: -8.2%
Sharpe Ratio: 1.8

Best Performers:
1. SOL: +25%
2. BONK: +15%
3. WIF: +12%

Worst Performers:
1. TOKEN_X: -15%
2. TOKEN_Y: -8%

Recommendation: Strategy viable. Consider implementation.
```

## Part 8: Custom Alerts

### Price Alerts

```
/alert price SOL > 110
```

Get notified when SOL exceeds $110.

### Signal Alerts

```
/alert signal SOL whale buy
```

Get notified when whale buying detected for SOL.

### Volume Alerts

```
/alert volume BONK > 50m
```

Get notified when BONK 24h volume exceeds $50M.

### Sentiment Alerts

```
/alert sentiment WIF < 40
```

Get notified if WIF sentiment drops below 40.

## Summary

Key principles:
1. **Multi-signal confirmation** reduces false positives
2. **Risk-adjusted sizing** protects capital
3. **Algorithm weighting** improves over time
4. **Diversification** spreads risk
5. **Backtesting** validates strategies

## Next Steps

- [Dexter ReAct Agent](./04-dexter-react.md)
- [Security Best Practices](./05-security.md)
- [Fee Structure](./06-revenue.md)

---

**Last Updated**: 2026-01-18
