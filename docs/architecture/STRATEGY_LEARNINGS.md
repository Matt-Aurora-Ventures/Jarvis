# JARVIS Strategic Learnings & Implementation Plan

**Generated:** 2026-01-12
**Source:** Video transcript analysis (5 trading tutorial videos)

---

## Executive Summary

Analysis of 5 trading tutorial videos revealed critical strategies, techniques, and architectural patterns that should be integrated into JARVIS's core trading capabilities. This document outlines:
1. Key trading strategies discovered
2. Technical implementations required
3. Decision matrix enhancements
4. Risk management improvements

---

## 1. LIQUIDATION-BASED TRADING STRATEGIES

### 1.1 Contrarian Liquidation Strategy (HIGH PRIORITY)

**Concept:** Trade opposite to large liquidation cascades, expecting mean reversion.

**Rules:**
- **Go LONG** when: `long_liquidation_volume > short_liquidation_volume * 1.5`
  - Rationale: Large long liquidations create oversold conditions, expect bounce
- **Go SHORT** when: `short_liquidation_volume > long_liquidation_volume * 1.5`
  - Rationale: Large short liquidations create overbought conditions, expect dump
- **Stay NEUTRAL** when: Neither side dominates by 1.5x

**Entry Conditions:**
- Minimum liquidation volume threshold: $500,000
- Time window for aggregation: 5 minutes
- Clear directional bias (1.5x imbalance)

**Implementation:**
```python
# Pseudo-code for liquidation strategy
def get_liquidation_signal(liquidations_5m):
    long_liq_volume = sum(liq.volume for liq in liquidations_5m if liq.side == 'SELL')
    short_liq_volume = sum(liq.volume for liq in liquidations_5m if liq.side == 'BUY')

    if long_liq_volume > short_liq_volume * 1.5 and long_liq_volume > 500_000:
        return 'LONG'  # Contrarian: buy after long liquidations
    elif short_liq_volume > long_liq_volume * 1.5 and short_liq_volume > 500_000:
        return 'SHORT'  # Contrarian: sell after short liquidations
    return 'NEUTRAL'
```

**Data Sources Required:**
- CoinGlass API for liquidation data
- Real-time liquidation feeds
- Historical liquidation data for backtesting

---

### 1.2 Large Liquidation Tracking ($5M+ Events)

**Concept:** Monitor for whale liquidations as potential market reversal signals.

**Rules:**
- Track liquidations > $5M as significant events
- Combine with other indicators (funding rate, OI changes)
- Use as confirmation for existing signals

---

## 2. DUAL MOVING AVERAGE REVERSAL STRATEGY

### 2.1 Core Strategy (VALIDATED)

**Parameters (Optimized through walk-forward testing):**
- Fast MA: 7-13 periods (sweet spot: 13)
- Slow MA: 30-45 periods (sweet spot: 33-42)
- Timeframe: Daily or 6-hour
- Take Profit: 1%
- Stop Loss: 3%

**Trend Filter:**
- Use 100 SMA (NOT 200 - too slow for crypto)
- Only take LONG positions when price > 100 SMA
- 100 SMA enters trends earlier, captures more upside

**Performance Metrics (from testing):**
- Sharpe Ratio: ~1.0-1.4 (out-of-sample)
- Sortino Ratio: 2.5-4.5
- Calmar Ratio: 1-6
- Max Drawdown: 20-52%

---

## 3. ROBUSTNESS TESTING FRAMEWORK

### 3.1 Testing Hierarchy (MUST IMPLEMENT)

1. **Hold-out Out-of-Sample Test**
   - Split: 70% train, 30% test
   - Strategy should retain 50%+ of train set performance
   - Drawdown profile should remain similar

2. **Parameter Heat Map Analysis**
   - Grid search around best parameters (+/- 10%)
   - Look for PLATEAUS not spikes
   - Thin spike = overfit, wide plateau = robust

3. **Walk-Forward Testing**
   - Rolling window: 3-year train, 6-month trade
   - Re-optimize parameters each window
   - Stitch together out-of-sample equity curves
   - Compound equity (each slice starts with previous ending capital)

4. **Permutation Tests**
   - Shuffle returns/signals 1000 times
   - Calculate p-value
   - Live Sharpe should be in extreme right tail (p < 0.05)

5. **Monte Carlo Resampling**
   - Bootstrap trades 10,000 times
   - 5th percentile CAGR should stay positive
   - Understand luck vs skill

6. **Fee/Slippage Shock**
   - Double commissions
   - Add 0.25% slippage
   - Edge should survive

### 3.2 Key Metrics to Track

| Metric | Description | Target |
|--------|-------------|--------|
| Sharpe Ratio | Return / Total Volatility | > 1.0 |
| Sortino Ratio | Return / Downside Volatility (better for crypto) | > 2.0 |
| Calmar Ratio | CAGR / Max Drawdown | > 1.0 |
| Expectancy | Average profit per trade | > 0 |
| Profit Factor | Gross profit / Gross loss | > 1.5 |
| Max Drawdown | Largest peak-to-trough decline | < 50% |

---

## 4. POSITION MANAGEMENT & RISK CONTROL

### 4.1 Cooldown System (IMPLEMENT IMMEDIATELY)

**Problem:** Overtrading, entering new positions too quickly after exits.

**Solution:**
```python
COOLDOWN_MINUTES = 30  # Configurable

def can_enter_trade():
    last_close_time = get_last_close_from_csv()
    if last_close_time and (now - last_close_time) < timedelta(minutes=COOLDOWN_MINUTES):
        return False  # Entry blocked
    return True

def on_position_close():
    log_to_csv('position_closures.csv', {
        'timestamp': now,
        'symbol': symbol,
        'pnl': pnl
    })
```

**Key Points:**
- Track CLOSURES not entries (handles unfilled orders)
- Allow closing during cooldown (for retry attempts)
- Log all closures to CSV for analysis

### 4.2 Position Sizing Rules

- **Never use 100% balance** - exchange bugs can trap you
- **Maximum position size:** 25% of portfolio per trade
- **ATR-based sizing:** Risk 1% of equity per trade
- **Notional cap:** Max $10M per position (liquidity constraint)

### 4.3 Negative Balance Protection

**Problem:** Some exchanges block ALL orders when available balance is negative.

**Solution:**
- Use smaller position sizes (never full balance)
- Implement emergency close with `reduce_only=True` parameter
- Monitor available balance before order placement

---

## 5. API EFFICIENCY OPTIMIZATIONS

### 5.1 Reduce Excessive API Calls

**Problem Identified:** Calling token overview API 20x more than needed.

**Solutions:**
1. **Cache with TTL** - But be careful with live trading data
2. **Batch requests** - Fetch multiple tokens in one call
3. **Single wallet fetch** - Don't loop through all wallets for one token
4. **Lazy loading** - Only fetch data when needed

### 5.2 API Call Tracking

- Log API usage by endpoint
- Set alerts for approaching rate limits
- Implement exponential backoff for failures

---

## 6. COPY TRADING ENHANCEMENTS

### 6.1 Wallet Ranking System

**Track for each followed wallet:**
- Win rate
- Average profit per trade
- Total PnL
- Number of trades
- Time in position

**Implementation:**
```python
# Store all trending tokens with owner info
all_trending_ever = pd.DataFrame()

def on_new_trending_token(token, owner_wallet):
    global all_trending_ever
    new_row = {
        'token': token,
        'owner': owner_wallet,
        'timestamp': now
    }
    all_trending_ever = pd.concat([all_trending_ever, pd.DataFrame([new_row])])
    all_trending_ever.to_csv('data/all_trending_ever.csv', index=False)

def on_position_close(token):
    # Look up who we followed for this token
    owner = get_owner_for_token(token)
    update_wallet_stats(owner, pnl)
```

---

## 7. META-LABELING / CORRECTIVE AI

### 7.1 Concept

Instead of predicting price directly, predict whether a trade SIGNAL will be profitable.

**Two-Stage Approach:**
1. **Base Model:** Generates trade signals (long/short/neutral)
2. **Meta-Labeler:** Classifies if the signal is worth taking

### 7.2 Features for Meta-Labeler

- Signal strength from base model
- Recent hit rate of similar signals
- Current market regime (trending/ranging)
- Funding rate skew
- Order flow imbalance (OFI)
- Liquidity conditions
- Time-based factors (hour, day of week)

### 7.3 Output

- Probability that the trade will be profitable
- Only take trades with probability > threshold (e.g., 60%)

---

## 8. IMPLEMENTATION PRIORITY MATRIX

| Priority | Item | Effort | Impact |
|----------|------|--------|--------|
| P0 | Liquidation signal integration | Medium | High |
| P0 | Cooldown system | Low | High |
| P0 | Position sizing limits | Low | High |
| P1 | Walk-forward testing framework | High | High |
| P1 | Dual MA strategy implementation | Medium | High |
| P1 | Robustness testing suite | High | High |
| P2 | Wallet ranking for copy trading | Medium | Medium |
| P2 | API efficiency optimizations | Medium | Medium |
| P2 | Meta-labeling classifier | High | High |
| P3 | 100 SMA trend filter | Low | Medium |
| P3 | Monte Carlo simulation | Medium | Medium |

---

## 9. DECISION MATRIX UPDATES

### 9.1 Entry Conditions (Add These)

```python
ENTRY_CONDITIONS = {
    'liquidation_imbalance': {
        'threshold': 1.5,
        'min_volume': 500_000,
        'window': '5m'
    },
    'trend_filter': {
        'enabled': True,
        'period': 100,  # SMA 100
        'type': 'above'  # Price must be above SMA
    },
    'cooldown': {
        'enabled': True,
        'minutes': 30
    },
    'max_position_size': 0.25,  # 25% of portfolio
    'max_notional': 10_000_000  # $10M cap
}
```

### 9.2 Exit Conditions (Add These)

```python
EXIT_CONDITIONS = {
    'take_profit': 0.01,  # 1%
    'stop_loss': 0.03,    # 3%
    'trailing_stop': {
        'enabled': False,
        'distance': 0.02
    },
    'time_stop': {
        'enabled': False,
        'hours': 24
    }
}
```

---

## 10. DATA SOURCES TO INTEGRATE

| Source | Data Type | Priority |
|--------|-----------|----------|
| CoinGlass | Liquidation data | P0 |
| Birdeye | Token analytics | P1 |
| Helius | Solana transaction data | P1 |
| Jupiter | DEX aggregation | P1 |
| ClickHouse | Historical data storage | P2 |

---

## 11. NEXT STEPS

1. [ ] Implement liquidation signal module in `core/trading/`
2. [ ] Add cooldown system to position manager
3. [ ] Create robustness testing framework in `tests/`
4. [ ] Integrate CoinGlass API for liquidation data
5. [ ] Update decision matrix with new entry/exit conditions
6. [ ] Implement walk-forward testing capability
7. [ ] Add Sharpe/Sortino/Calmar tracking to performance metrics
8. [ ] Create wallet ranking system for copy trading

---

## 12. KEY QUOTES & PHILOSOPHY

> "If it's too good to be true, it probably is. Never run anybody else's bot. You have to build your own edge."

> "The lower time frames are more competitive. Start with higher timeframes and go smaller over time."

> "You can't just work harder at trading and get better. You have to have patience, you cannot be greedy, and you can't be fearful."

> "Just keep making your systems better and better and better because that's what everyone else is trying to do." - Jim Simons philosophy

---

*Document generated by JARVIS knowledge extraction pipeline*
