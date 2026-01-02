# Comprehensive Guide to Automated Crypto Trading on DEXs

A complete reference for the Life OS Trading Bot covering infrastructure, strategies, and risk management.

---

## Table of Contents

1. [Infrastructure Requirements](#1-infrastructure-requirements)
2. [Trading Strategies](#2-trading-strategies)
3. [DEX-Specific Strategies](#3-dex-specific-strategies)
4. [Risk Management](#4-risk-management)
5. [Quick Reference Cards](#5-quick-reference-cards)

---

## 1. Infrastructure Requirements

### Blockchain Comparison

| Network | TPS | Data Rate | Best For |
|---------|-----|-----------|----------|
| Solana | 1,000+ | 1TB/day | HFT, arbitrage |
| Ethereum | ~20 | Moderate | DeFi, smart contracts |
| Polygon | ~65 | Moderate | Scaling, low fees |
| Avalanche | 4,500 | High | Custom subnets |

### RPC Providers

| Provider | Specialty | Free Tier |
|----------|-----------|-----------|
| **Helius** | Solana-native, enhanced APIs | Yes |
| **Alchemy** | Multi-chain, reliable | 30M CU/month |
| **Ankr** | Hummingbot compatible | Limited |

### Cost Structure

- **Platform fees**: $15-110/month (or free with open-source)
- **RPC costs**: ~$0.40 per 1M compute units after free tier
- **Gas fees**: Variable per network (critical for HFT profitability)

---

## 2. Trading Strategies

### Foundational Strategies

#### Trend Following
- **Signal**: Moving average crossover (SMA 9/21)
- **Best for**: Clear trending markets
- **Risk**: False signals in sideways markets

```python
# Pseudo-code
if sma_short > sma_long and not in_position:
    buy()
elif sma_short < sma_long and in_position:
    sell()
```

#### Mean Reversion
- **Signal**: Price deviation from Bollinger Bands + RSI
- **Best for**: Range-bound markets
- **Risk**: Prolonged trends cause losses

```python
# Pseudo-code
if price < lower_band and rsi < 30:
    buy()  # Oversold
elif price > upper_band and rsi > 70:
    sell()  # Overbought
```

#### Dollar-Cost Averaging (DCA)
- **Signal**: Time-based (weekly/daily)
- **Best for**: Long-term accumulation
- **Risk**: May underperform lump-sum in bull markets

### Advanced Strategies

#### Market Making
- Place simultaneous bid/ask orders
- Profit from bid-ask spread
- Requires significant capital

#### Arbitrage
- Cross-exchange price discrepancy
- Triangular arbitrage (same exchange)
- Flash loan amplification

#### Sentiment Analysis
- NLP on news/social media
- Gauge market mood
- Trigger trades on sentiment shifts

---

## 3. DEX-Specific Strategies

### Flash Loan Arbitrage

```
1. Borrow $1M via flash loan (no collateral)
2. Buy ETH on Uniswap at $2,000
3. Sell ETH on Sushiswap at $2,010
4. Repay flash loan + fee
5. Keep ~$5,000 profit
```

> **Note**: If arbitrage fails, entire transaction reverts. "Risk-free" with zero upfront capital.

### MEV (Maximal Extractable Value)

**Sandwich Attack Pattern:**
1. **Front-run**: Bot sees large pending buy, buys first
2. **Victim trade**: Executes at inflated price
3. **Back-run**: Bot sells at higher price

> **Warning**: Solana saw 521,903 sandwich attacks in early 2025, causing $7.7M in victim losses.

---

## 4. Risk Management

### Core Principles

| Rule | Implementation |
|------|----------------|
| **Stop-Loss** | Auto-exit at -2% to -5% |
| **Take-Profit** | Auto-exit at +5% to +15% |
| **Position Sizing** | Max 1-2% of capital per trade |
| **Max Drawdown** | Circuit breaker at 10% portfolio loss |
| **Diversification** | Spread across uncorrelated assets |

### Critical Safeguards

1. **Never enable API withdrawals** for trading bots
2. **Monitor for errant algorithms** (Knight Capital lost $440M in 45 minutes)
3. **Deploy on VPS** for 24/7 uptime
4. **Backtest extensively** before live trading

---

## 5. Quick Reference Cards

### Strategy Selection Matrix

| Market Condition | Best Strategy |
|------------------|---------------|
| Strong uptrend | Trend Following |
| Strong downtrend | Trend Following (short) |
| Sideways/ranging | Mean Reversion |
| High volatility | Reduce position size |
| Low volatility | Market Making |

### Key Metrics for Backtesting

- **Sharpe Ratio**: Risk-adjusted return (>1 is good, >2 is excellent)
- **Max Drawdown**: Largest peak-to-trough decline
- **Win Rate**: % of profitable trades
- **Profit Factor**: Gross profit / Gross loss (>1.5 ideal)

### Environment Variables

```bash
# Required for Life OS Trading Bot
export OPENROUTER_API_KEY="your-key"
export HELIUS_API_KEY="your-helius-key"
export ALCHEMY_API_KEY="your-alchemy-key"

# Optional
export DAILY_SPEND_LIMIT_USD="5.00"
export ROUTER_MODE="CLOUD"  # CLOUD | LOCAL | BEAST
```

---

## Further Reading

- [Freqtrade Documentation](https://freqtrade.io)
- [Hummingbot Gateway](https://hummingbot.org)
- [Jupiter Aggregator (Solana)](https://jup.ag)
- [Alchemy Docs](https://docs.alchemy.com)
