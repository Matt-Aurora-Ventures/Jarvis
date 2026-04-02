# Systematic Trading Strategies Research

**Source:** [paperswithbacktest/awesome-systematic-trading](https://github.com/paperswithbacktest/awesome-systematic-trading)
**Date:** 2026-02-09
**Analyst:** Jarvis Treasury / Sniper Module
**Target Assets:** Blue-chip Solana tokens, tokenized equities (xStocks), tokenized indexes

---

## Executive Summary

This document distills 40+ academic systematic trading strategies from the `awesome-systematic-trading` repository into the **top 10 most applicable** for Jarvis's trading universe. The repository catalogs strategies described by institutions and academics, each with QuantConnect implementations, Sharpe ratios, volatility profiles, and source papers.

**Key findings:**

1. **Mean reversion** strategies dominate on short timeframes (daily/weekly) with the highest Sharpe ratios, particularly short-term reversal (Sharpe 0.816) and overnight anomalies (Sharpe 0.892 for BTC).
2. **Trend following** strategies work well on medium timeframes (daily rebalancing) with ATR-based trailing stops, achieving Sharpe ~0.57 on equities.
3. **Crypto-specific** strategies show the highest absolute returns but also the highest volatility. Overnight seasonality (BTC Sharpe 0.892) and rebalancing premium (Sharpe 0.698) are directly applicable to Solana blue chips.
4. **Volatility-regime switching** is a cross-cutting filter that improves most strategies -- buy when price > SMA and VIX < SMA.
5. Most strategies are **implementable with OHLCV data** on 1h candles, with some adaptation from daily to hourly timeframes.

**Implementation priority:** Start with strategies 1-3 (highest Sharpe, lowest complexity, directly applicable to our asset classes).

---

## Target Asset Class Profiles

| Asset Class | Examples | Daily Volatility | Best Strategy Type |
|---|---|---|---|
| **Solana Blue Chips** | SOL, JUP, RAY, PYTH, BONK | 4-12% | Mean reversion, momentum, overnight seasonality |
| **Tokenized Equities** | AAPLx, MSFTx, TSLAx | 1-3% | Trend following, earnings reversal, pairs trading |
| **Tokenized Indexes** | SPYx, QQQx, TQQQx | 0.5-3% | Asset-class trend following, overnight anomaly, sentiment overlay |

---

## Top 10 Most Applicable Strategies (Ranked)

### 1. Overnight Seasonality (Crypto-Adapted)

| Attribute | Value |
|---|---|
| **Original Name** | Overnight Seasonality in Bitcoin |
| **Sharpe Ratio** | 0.892 |
| **Volatility** | 20.8% |
| **Rebalancing** | Intraday |
| **Best Regime** | All regimes (captures overnight drift) |
| **Complexity** | LOW |
| **Applicable To** | SOL, JUP, RAY, BONK, SPYx, QQQx |

**Core Logic:**
- Open a long position at 22:00 UTC, hold for 2 hours, close at 00:00 UTC
- Exploits the well-documented overnight return anomaly where assets drift upward during low-volume hours
- No indicators needed -- pure time-based entry/exit

**Entry Rules:**
1. At 22:00 UTC, buy 100% allocation of the target asset
2. At 00:00 UTC, close the position entirely

**Exit Rules:**
- Time-based exit at 00:00 UTC
- Optional: add stop-loss at -2% intraday

**Key Parameters to Optimize:**
| Parameter | Range | Default |
|---|---|---|
| Entry hour (UTC) | 20:00-23:00 | 22:00 |
| Holding period (hours) | 1-6 | 2 |
| Position size (%) | 50-100 | 100 |
| Stop-loss (%) | 1-5 | None |

**Adaptation for Solana Blue Chips:**
- Crypto markets are 24/7, so the overnight window needs calibration to Solana-specific volume patterns
- Test entry windows around Asian open (00:00 UTC) and US close (20:00 UTC)
- For SOL specifically, low-volume windows may shift vs. BTC due to different trader demographics

**Paper:** Dusak et al., "Intraday Seasonality in Bitcoin" (SSRN 4081000)

**Implementation Notes:**
```
Pseudocode:
  if current_hour == ENTRY_HOUR:
    buy(asset, portfolio_pct=1.0)
  if current_hour == EXIT_HOUR:
    sell(asset, all=True)
```

---

### 2. Short-Term Reversal Effect

| Attribute | Value |
|---|---|
| **Original Name** | Short Term Reversal Effect in Stocks |
| **Sharpe Ratio** | 0.816 |
| **Volatility** | 21.4% |
| **Rebalancing** | Weekly |
| **Best Regime** | Mean-reverting / choppy markets |
| **Complexity** | MEDIUM |
| **Applicable To** | Solana blue chips (high vol), tokenized equities |

**Core Logic:**
- From a universe of large-cap assets, identify the 10 worst performers over the past week
- Go long on these "losers" (expecting mean reversion)
- Go short on the 10 best performers of the past month (expecting reversal)
- Rebalance weekly

**Entry Rules:**
1. Calculate 7-day return for each asset in universe
2. Calculate 21-day return for each asset in universe
3. LONG: bottom 10% by weekly return (weekly losers)
4. SHORT: top 10% by monthly return (monthly winners)

**Exit Rules:**
- Rebalance weekly (close all, re-select)
- Equal weight across all positions

**Key Parameters to Optimize:**
| Parameter | Range | Default |
|---|---|---|
| Lookback period (short) | 3-10 days | 7 days (weekly) |
| Lookback period (long) | 14-30 days | 21 days (monthly) |
| Selection percentile | 10-25% | 10% |
| Rebalance frequency | 3-7 days | 7 days |
| Min universe size | 10-50 | 20 |

**Adaptation for Solana Blue Chips:**
- Universe: top 20-30 Solana tokens by market cap
- High crypto volatility amplifies mean-reversion opportunities
- Reduce lookback from 21 days to 7-14 days for faster crypto cycles
- Consider hourly candles with 24h/168h lookback instead of daily

**Paper:** Hameed & Mian, "Short-Term Reversal in Stocks" (SSRN 1605049)

**Implementation Notes:**
```
Pseudocode:
  weekly_returns = {token: pct_change(price, 7d) for token in universe}
  monthly_returns = {token: pct_change(price, 21d) for token in universe}
  longs = bottom_n(weekly_returns, n=selection_count)
  shorts = top_n(monthly_returns, n=selection_count)
  rebalance(longs, shorts, equal_weight=True)
```

---

### 3. Time-Series Momentum

| Attribute | Value |
|---|---|
| **Original Name** | Time Series Momentum Effect |
| **Sharpe Ratio** | 0.576 |
| **Volatility** | 20.5% |
| **Rebalancing** | Monthly |
| **Best Regime** | Trending markets |
| **Complexity** | LOW-MEDIUM |
| **Applicable To** | All three asset classes |

**Core Logic:**
- For each asset, check if the excess return over the past 12 months (or adapted lookback) is positive or negative
- Go long if positive, go short (or stay flat) if negative
- Position size inversely proportional to asset volatility (volatility targeting)
- Rebalance monthly (adapt to weekly for crypto)

**Entry Rules:**
1. Calculate trailing return over lookback period
2. If return > 0: go long
3. If return < 0: go short or stay flat
4. Size = target_vol / realized_vol (volatility parity)

**Exit Rules:**
- Rebalance at end of each period
- Reverse position if momentum signal flips

**Key Parameters to Optimize:**
| Parameter | Range | Default |
|---|---|---|
| Lookback period | 30-252 days | 252 days (12 months) |
| Target volatility | 5-20% | 10% |
| Vol estimation window | 20-60 days | 60 days |
| Leverage cap | 1x-4x | 4x |
| Rebalance frequency | Weekly-Monthly | Monthly |

**Adaptation for Solana Blue Chips:**
- Shorten lookback to 30-90 days (crypto trends are faster)
- Use 1h candle volatility estimation
- For tokenized equities: standard 252-day lookback is appropriate
- For tokenized indexes: consider 63-day (quarterly) lookback

**Paper:** Moskowitz, Ooi, Pedersen, "Time Series Momentum" (NYU Stern)

**Implementation Notes:**
```
Pseudocode:
  for asset in universe:
    ret = (price_now / price_lookback_days_ago) - 1
    vol = std(daily_returns, window=vol_window) * sqrt(252)
    position_size = target_vol / vol
    position_size = min(position_size, leverage_cap)
    if ret > 0:
      go_long(asset, size=position_size)
    else:
      go_flat(asset)  # or go_short for L/S version
```

---

### 4. Trend Following with ATR Trailing Stop

| Attribute | Value |
|---|---|
| **Original Name** | Trend-following Effect in Stocks |
| **Sharpe Ratio** | 0.569 |
| **Volatility** | 15.2% |
| **Rebalancing** | Daily |
| **Best Regime** | Strong trending markets |
| **Complexity** | MEDIUM |
| **Applicable To** | SOL, JUP, RAY, tokenized equities |

**Core Logic:**
- Entry: buy when today's close >= all-time high (or N-period high)
- Exit: ATR-based trailing stop-loss (10-period ATR below current price)
- Equal weight across all positions meeting criteria
- Daily rebalancing

**Entry Rules:**
1. Calculate all-time high (or rolling high over lookback)
2. If close >= all_time_high: enter long
3. Set initial stop-loss at: entry_price - ATR(10)

**Exit Rules:**
1. Trail stop-loss: new_sl = max(current_sl, price - ATR(10))
2. Exit when price hits stop-loss
3. Never lower the stop-loss, only raise it

**Key Parameters to Optimize:**
| Parameter | Range | Default |
|---|---|---|
| ATR period | 5-20 | 10 |
| ATR multiplier | 1.0-3.0 | 1.0 |
| Breakout lookback | 20-252 days | All-time |
| Max positions | 5-20 | 10 |
| Position sizing | Equal weight | Equal weight |

**Adaptation for Solana Blue Chips:**
- Use 50-day or 100-day high instead of all-time high (crypto ATH may be very distant)
- ATR on 1h candles with 24-period or 48-period window
- Wider ATR multiplier (2.0-3.0) for crypto volatility
- Consider adding volume confirmation (breakout on high volume)

**Paper:** "The Trend is Our Friend: Risk Parity, Momentum and Trend Following in Global Asset Allocation" (UPenn)

**Implementation Notes:**
```
Pseudocode:
  atr = ATR(high, low, close, period=10)
  highest_close = max(close, window=lookback)

  if close >= highest_close and not in_position:
    buy(asset)
    stop_loss = close - atr * multiplier

  if in_position:
    new_stop = close - atr * multiplier
    stop_loss = max(stop_loss, new_stop)  # only raise
    if close <= stop_loss:
      sell(asset)
```

---

### 5. Rebalancing Premium (Crypto Portfolio)

| Attribute | Value |
|---|---|
| **Original Name** | Rebalancing Premium in Cryptocurrencies |
| **Sharpe Ratio** | 0.698 |
| **Volatility** | 27.5% |
| **Rebalancing** | Daily |
| **Best Regime** | High volatility / sideways markets |
| **Complexity** | LOW |
| **Applicable To** | Solana blue-chip basket |

**Core Logic:**
- Construct an equally-weighted portfolio of N crypto assets
- Rebalance daily to maintain equal weights
- The "rebalancing premium" arises because daily rebalancing systematically buys low (assets that declined) and sells high (assets that appreciated)
- The strategy profits from mean reversion within the basket

**Entry Rules:**
1. Select universe of N cryptocurrencies
2. Allocate 1/N to each asset
3. Every day at fixed time, rebalance all positions to 1/N

**Exit Rules:**
- No explicit exit -- continuous rebalancing
- Remove asset from universe if it drops below minimum market cap threshold

**Key Parameters to Optimize:**
| Parameter | Range | Default |
|---|---|---|
| Number of assets | 5-30 | 20-27 |
| Rebalance frequency | 4h-7d | Daily |
| Rebalance threshold (%) | 1-10 | 0 (always rebalance) |
| Minimum market cap | $10M-$1B | $100M |

**Adaptation for Solana Blue Chips:**
- Universe: SOL, JUP, RAY, PYTH, BONK, WIF, JTO, ORCA, MNGO, DRIFT (10-15 tokens)
- Rebalance every 4-12 hours instead of daily (crypto moves faster)
- Add a rebalance threshold (only rebalance if weight drifts >5% from target)
- Transaction cost sensitivity: Jupiter DEX fees ~0.3% per swap

**Paper:** Makarov & Schoar, "Rebalancing Premium in Cryptocurrencies" (SSRN 3982120)

**Implementation Notes:**
```
Pseudocode:
  target_weight = 1.0 / len(universe)

  for asset in universe:
    current_weight = portfolio_value(asset) / total_portfolio_value
    drift = abs(current_weight - target_weight)
    if drift > rebalance_threshold:
      if current_weight > target_weight:
        sell(asset, amount=(current_weight - target_weight) * total_value)
      else:
        buy(asset, amount=(target_weight - current_weight) * total_value)
```

---

### 6. Momentum + Volatility Filter

| Attribute | Value |
|---|---|
| **Original Name** | Momentum and Reversal Combined with Volatility Effect in Stocks |
| **Sharpe Ratio** | 0.375 |
| **Volatility** | 17% |
| **Rebalancing** | Monthly |
| **Best Regime** | Trending + volatile markets |
| **Complexity** | MEDIUM-HIGH |
| **Applicable To** | Solana blue chips, tokenized equities |

**Core Logic:**
- Calculate 6-month return and 6-month annualized volatility for each asset
- Sort into quintiles by both return and volatility
- Go long on highest-return + highest-volatility assets (momentum confirmed by volatility)
- Go short on lowest-return + highest-volatility assets
- Equal-weighted, 1/6 rebalanced monthly (6-month tranching)

**Entry Rules:**
1. Calculate trailing 126-day return for each asset
2. Calculate trailing 126-day annualized volatility
3. LONG: top 20% by return AND top 20% by volatility
4. SHORT: bottom 20% by return AND top 20% by volatility

**Exit Rules:**
- Hold for 6 months (or adapted shorter period for crypto)
- Tranche: replace 1/6 of portfolio each month

**Key Parameters to Optimize:**
| Parameter | Range | Default |
|---|---|---|
| Return lookback | 30-180 days | 126 days |
| Volatility lookback | 30-180 days | 126 days |
| Quintile size | 10-30% | 20% |
| Holding period | 1-6 months | 6 months |
| Skip period (gap) | 0-7 days | 7 days |

**Adaptation for Solana Blue Chips:**
- Shorten lookback to 30-60 days for crypto
- Shorten holding period to 7-30 days
- High-vol tokens like BONK, WIF naturally cluster in the high-vol quintile
- For tokenized equities, standard 126-day parameters work

**Paper:** Asness, Liew, Stevens, "Momentum and Reversal Combined with Volatility" (SSRN 1679464)

---

### 7. Asset-Class Trend Following (SMA Filter)

| Attribute | Value |
|---|---|
| **Original Name** | Asset Class Trend-Following |
| **Sharpe Ratio** | 0.502 |
| **Volatility** | 10.4% |
| **Rebalancing** | Monthly |
| **Best Regime** | Trending / regime switching |
| **Complexity** | LOW |
| **Applicable To** | SPYx, QQQx, tokenized equities |

**Core Logic:**
- Hold an equal-weight portfolio of multiple asset classes (stocks, bonds, commodities, REITs)
- Only hold an asset when its price is ABOVE its 10-month (210-day) SMA
- When price < SMA, move that allocation to cash (or stablecoin)
- Rebalance monthly

**Entry Rules:**
1. Calculate 210-day SMA for each asset
2. If price > SMA: allocate 1/N to asset
3. If price <= SMA: hold cash/stablecoin for that slot

**Exit Rules:**
- Monthly recheck: exit if price drops below SMA
- Cash allocation earns stablecoin yield

**Key Parameters to Optimize:**
| Parameter | Range | Default |
|---|---|---|
| SMA period | 50-300 days | 210 days |
| Rebalance frequency | Weekly-Monthly | Monthly |
| Number of assets | 3-10 | 5 |
| Cash alternative | None/Stablecoin | Cash |

**Adaptation for Tokenized Assets:**
- Universe: SPYx, QQQx, SOL, BTC, ETH (or similar diversified basket)
- Shorten SMA to 50-100 days for crypto components
- Cash alternative = USDC earning yield on Solana (e.g., Drift, Kamino)
- Can be used as an overlay/filter on top of other strategies

**Paper:** Faber, "A Quantitative Approach to Tactical Asset Allocation" (SSRN 962461)

**Implementation Notes:**
```
Pseudocode:
  sma = SMA(close, period=210)
  for asset in universe:
    if close > sma:
      hold(asset, weight=1/n_assets)
    else:
      hold_cash(weight=1/n_assets)
```

---

### 8. Pairs Trading (Cointegration-Based)

| Attribute | Value |
|---|---|
| **Original Name** | Pairs Trading with Stocks / Country ETFs |
| **Sharpe Ratio** | 0.634 (stocks) / 0.257 (ETFs) |
| **Volatility** | 8.5% (stocks) / 5.7% (ETFs) |
| **Rebalancing** | Daily |
| **Best Regime** | Mean-reverting / range-bound |
| **Complexity** | HIGH |
| **Applicable To** | SOL/ETH, AAPLx/MSFTx, SPYx/QQQx |

**Core Logic:**
- Find cointegrated pairs of assets (statistically linked prices that revert to a mean spread)
- When the spread deviates beyond a threshold (e.g., 2 standard deviations), trade the convergence
- Go long the underperformer, short the outperformer
- Close when spread reverts to mean

**Entry Rules:**
1. Calculate spread = log(price_A) - beta * log(price_B)
2. Calculate z-score = (spread - mean(spread)) / std(spread)
3. If z-score > +2: short A, long B (spread too wide)
4. If z-score < -2: long A, short B (spread too narrow)

**Exit Rules:**
1. Close when z-score crosses 0 (mean reversion complete)
2. Stop-loss: close if z-score exceeds 3.5 (divergence, not convergence)
3. Time-based: close after max_holding_period days

**Key Parameters to Optimize:**
| Parameter | Range | Default |
|---|---|---|
| Formation period (lookback) | 60-252 days | 252 days |
| Entry z-score threshold | 1.5-2.5 | 2.0 |
| Exit z-score threshold | -0.5 to 0.5 | 0.0 |
| Stop-loss z-score | 3.0-4.0 | 3.5 |
| Max holding period | 10-60 days | 30 days |
| Hedge ratio estimation | OLS / Kalman | OLS |

**Candidate Pairs for Jarvis:**
| Pair | Rationale |
|---|---|
| SOL/ETH | Both L1 smart-contract platforms, correlated |
| JUP/RAY | Both Solana DEX tokens |
| AAPLx/MSFTx | Mega-cap tech, high correlation |
| SPYx/QQQx | Index correlation, small beta difference |
| SOL/JUP | Solana ecosystem tokens |
| BONK/WIF | Solana memecoins, high correlation |

**Paper:** Gatev, Goetzmann, Rouwenhorst, "Pairs Trading" (SSRN 141615)

**Implementation Notes:**
```
Pseudocode:
  # Formation phase (calculate hedge ratio)
  beta = OLS_regression(log_prices_A, log_prices_B).slope
  spread = log_prices_A - beta * log_prices_B
  mean_spread = mean(spread, window=lookback)
  std_spread = std(spread, window=lookback)

  # Trading phase
  z_score = (current_spread - mean_spread) / std_spread

  if z_score > entry_threshold:
    short(A), long(B, beta_weighted)
  elif z_score < -entry_threshold:
    long(A), short(B, beta_weighted)

  if abs(z_score) < exit_threshold:
    close_all()
  if abs(z_score) > stop_loss_threshold:
    close_all()  # relationship broke down
```

---

### 9. Volatility Regime Overlay (VIX / Realized Vol Filter)

| Attribute | Value |
|---|---|
| **Original Name** | Market Sentiment and an Overnight Anomaly |
| **Sharpe Ratio** | 0.369 |
| **Volatility** | 3.6% (very low -- it's an overlay) |
| **Rebalancing** | Daily |
| **Best Regime** | Regime switching (bull/bear detection) |
| **Complexity** | LOW |
| **Applicable To** | All asset classes (as overlay) |

**Core Logic:**
- Use as a filter/overlay on top of other strategies
- Three conditions must be met to take a trade:
  1. Price > 20-day SMA (uptrend)
  2. VIX < 20-day SMA (decreasing fear, use realized vol as crypto VIX substitute)
  3. Sentiment indicator > 20-day SMA (positive sentiment)
- Each condition contributes 1/3 weight
- Buy at close, sell at next open (overnight hold)

**Entry Rules:**
1. Calculate 20-day SMA of asset price
2. Calculate 20-day SMA of volatility proxy (realized 7d vol or fear index)
3. Calculate 20-day SMA of sentiment (from Grok/AI sentiment scorer)
4. Score = sum(conditions_met) / 3
5. Enter with position_size = Score (0, 1/3, 2/3, or 1)

**Exit Rules:**
- Sell at market open the next day
- Or: use as a regime filter for other strategies (only trade when score >= 2/3)

**Key Parameters to Optimize:**
| Parameter | Range | Default |
|---|---|---|
| SMA period | 10-50 | 20 |
| Sentiment source | AI/Social/On-chain | Combined |
| Minimum score to trade | 1/3, 2/3, 1 | 2/3 |
| Hold period | Overnight to 3 days | Overnight |

**Adaptation for Crypto:**
- Replace VIX with realized 7-day volatility of SOL or BTC
- When realized_vol < SMA(realized_vol): "low fear" regime
- Sentiment: use Jarvis's existing Grok AI sentiment scores
- Price > SMA filter: straightforward

**Paper:** "Market Sentiment and an Overnight Anomaly" (SSRN 3829582)

**Implementation Notes:**
```
Pseudocode:
  sma_price = SMA(close, 20)
  sma_vol = SMA(realized_vol_7d, 20)
  sma_sentiment = SMA(sentiment_score, 20)

  score = 0
  if close > sma_price: score += 1/3
  if realized_vol < sma_vol: score += 1/3
  if sentiment > sma_sentiment: score += 1/3

  if score >= min_score:
    allow_trade()  # Proceed with other strategy signals
  else:
    stay_cash()
```

---

### 10. Betting Against Beta

| Attribute | Value |
|---|---|
| **Original Name** | Betting Against Beta Factor in Stocks |
| **Sharpe Ratio** | 0.594 |
| **Volatility** | 18.9% |
| **Rebalancing** | Monthly |
| **Best Regime** | All regimes (factor-based) |
| **Complexity** | MEDIUM |
| **Applicable To** | Solana token universe, tokenized equities |

**Core Logic:**
- Calculate each asset's beta relative to a market benchmark (e.g., SOL for Solana tokens, SPYx for equities)
- Go long on low-beta assets (leveraged to target beta of 1)
- Go short on high-beta assets (de-leveraged to target beta of 1)
- Beta-neutral portfolio that profits from the empirical "low beta anomaly"

**Entry Rules:**
1. Calculate trailing 12-month beta for each asset vs. benchmark
2. Sort assets by beta
3. LONG: bottom quintile (lowest beta), leveraged up
4. SHORT: top quintile (highest beta), leveraged down
5. Target: each side has beta = 1 (net beta-neutral)

**Exit Rules:**
- Rebalance monthly
- Re-estimate betas and re-sort

**Key Parameters to Optimize:**
| Parameter | Range | Default |
|---|---|---|
| Beta estimation window | 60-252 days | 252 days |
| Quintile size | 10-30% | 20% |
| Rebalance frequency | Monthly-Quarterly | Monthly |
| Benchmark | SOL / BTC / SPYx | Market-dependent |

**Adaptation for Solana:**
- Benchmark: SOL price for Solana ecosystem tokens
- Low-beta tokens (PYTH, JTO, ORCA) vs high-beta tokens (BONK, WIF)
- Caution: leverage on low-beta side may be unnecessary in crypto
- Consider long-only variant: overweight low-beta, underweight high-beta

**Paper:** Frazzini & Pedersen, "Betting Against Beta" (NYU Stern)

---

## Honorable Mentions (Strategies 11-15)

### 11. Low Volatility Factor (Long-Only)
- **Sharpe:** 0.717 | **Vol:** 11.5% | **Rebalance:** Monthly
- Long stocks in lowest volatility quartile (3-year lookback)
- Adaptation: long the least volatile Solana blue chips
- Good for risk-managed portfolio construction

### 12. Sector Momentum / Rotational System
- **Sharpe:** 0.401 | **Vol:** 14.1% | **Rebalance:** Monthly
- Rotate into the strongest performing sector/asset class
- Adaptation: rotate between DeFi tokens, meme tokens, infra tokens, stables

### 13. Dispersion Trading
- **Sharpe:** 0.432 | **Vol:** 8.1% | **Rebalance:** Monthly
- Trade the spread between index volatility and component volatility
- Adaptation: SPYx vol vs. individual xStock vols

### 14. Paired Switching
- **Sharpe:** 0.691 | **Vol:** 9.5% | **Rebalance:** Quarterly
- Alternate between two asset classes based on relative performance
- Adaptation: switch between SOL ecosystem tokens and stablecoins

### 15. Reversal During Earnings Announcements
- **Sharpe:** 0.785 | **Vol:** 25.7% | **Rebalance:** Daily
- Short-term reversal around major announcements
- Adaptation: trade reversals around token unlock events, governance votes, or protocol upgrades

---

## Implementation Complexity Matrix

| Strategy | Data Needs | Code Complexity | Parameter Sensitivity | Time to Implement |
|---|---|---|---|---|
| 1. Overnight Seasonality | 1h OHLCV | Very Low | Low | 1-2 hours |
| 2. Short-Term Reversal | Daily OHLCV | Low | Medium | 2-4 hours |
| 3. Time-Series Momentum | Daily OHLCV | Low | Medium | 2-4 hours |
| 4. Trend Following + ATR | Daily OHLCV + ATR | Medium | Medium | 4-8 hours |
| 5. Rebalancing Premium | Daily prices | Very Low | Low | 2-3 hours |
| 6. Momentum + Vol Filter | Daily OHLCV | Medium | High | 4-8 hours |
| 7. Asset-Class SMA Filter | Daily OHLCV | Very Low | Low | 1-2 hours |
| 8. Pairs Trading | Hourly OHLCV | High | High | 8-16 hours |
| 9. Volatility Regime Overlay | Daily OHLCV + sentiment | Low | Medium | 2-4 hours |
| 10. Betting Against Beta | Daily OHLCV | Medium | Medium | 4-8 hours |

---

## Parameter Ranges for Backtesting

### Universal Parameters (apply to all strategies)
| Parameter | Conservative | Moderate | Aggressive |
|---|---|---|---|
| Position size cap | 10% portfolio | 20% portfolio | 50% portfolio |
| Max concurrent positions | 3-5 | 5-10 | 10-20 |
| Stop-loss (per trade) | 2-3% | 5-8% | 10-15% |
| Max portfolio drawdown | 10% | 20% | 30% |
| Transaction cost estimate | 0.3% (Jupiter) | 0.3% | 0.3% |

### Lookback Windows (crypto-adapted)
| Traditional | Crypto Equivalent | Rationale |
|---|---|---|
| 252 days (1 year) | 90 days | Crypto cycles ~4x faster |
| 126 days (6 months) | 30-45 days | Momentum decays faster |
| 63 days (quarter) | 14-21 days | Regime shifts are rapid |
| 21 days (month) | 7 days | Weekly cycles |
| 5 days (week) | 24-48 hours | Intraday mean reversion |

### Volatility Targets
| Asset Class | Target Ann. Vol | Position Sizing |
|---|---|---|
| Solana Blue Chips | 30-50% | Reduce size proportionally |
| Tokenized Equities | 15-25% | Standard sizing |
| Tokenized Indexes | 10-20% | Can increase leverage |

---

## Data Requirements

### Minimum Data for All Strategies
| Data Type | Source | Frequency | History Needed |
|---|---|---|---|
| OHLCV candles | DexScreener / Birdeye | 1h | 90 days minimum |
| Volume | DexScreener / Birdeye | 1h | 30 days minimum |
| Market cap | CoinGecko / Birdeye | Daily | 30 days |
| Total portfolio value | On-chain (Helius) | Real-time | N/A |

### Optional Data (improves signals)
| Data Type | Source | Strategy |
|---|---|---|
| Sentiment scores | Grok AI (existing) | Volatility Regime Overlay |
| On-chain volume | Helius / Flipside | Rebalancing Premium, Breakout |
| Token unlock schedule | Various | Reversal during events |
| Realized volatility | Computed from OHLCV | All strategies |
| Correlation matrix | Computed from OHLCV | Pairs Trading |

---

## Recommended Implementation Roadmap

### Phase 1: Quick Wins (Week 1)
1. **Overnight Seasonality** -- test on SOL, JUP with 1h candles
2. **Asset-Class SMA Filter** -- deploy on SPYx/QQQx as regime filter
3. **Rebalancing Premium** -- test on 5-token Solana basket

### Phase 2: Core Strategies (Week 2-3)
4. **Short-Term Reversal** -- implement on top-20 Solana tokens
5. **Time-Series Momentum** -- add momentum scoring to existing trade signals
6. **Trend Following + ATR** -- integrate ATR trailing stops into position management

### Phase 3: Advanced (Week 4+)
7. **Momentum + Volatility Filter** -- combine with existing sentiment
8. **Pairs Trading** -- start with SOL/ETH and AAPLx/MSFTx
9. **Volatility Regime Overlay** -- layer on top of all strategies
10. **Betting Against Beta** -- portfolio-level optimization

---

## Risk Considerations

1. **Overfitting:** Most reported Sharpe ratios are in-sample. Expect 30-50% degradation out-of-sample.
2. **Crypto adaptation:** Lookback windows, volatility parameters, and rebalance frequencies ALL need re-calibration for crypto. Traditional parameters will not work directly.
3. **Transaction costs:** Jupiter DEX fees (~0.3%), slippage on illiquid tokens, and MEV can significantly erode strategy returns. Factor in 0.5-1.0% round-trip costs.
4. **Regime dependence:** No single strategy works in all market conditions. The volatility regime overlay (Strategy 9) should be applied as a filter.
5. **Correlation risk:** Many Solana tokens are highly correlated (0.7-0.9 to SOL). Pairs trading may find few truly cointegrated pairs.
6. **Survivorship bias:** The repository's strategy list may overweight strategies that looked good historically. Always forward-test.

---

## Paper References

| # | Strategy | Paper |
|---|---|---|
| 1 | Overnight Seasonality | [SSRN 4081000](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=4081000) |
| 2 | Short-Term Reversal | [SSRN 1605049](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=1605049) |
| 3 | Time-Series Momentum | [NYU Stern - Moskowitz et al.](https://pages.stern.nyu.edu/~lpederse/papers/TimeSeriesMomentum.pdf) |
| 4 | Trend Following | [UPenn - Trend Following Effect](https://www.cis.upenn.edu/~mkearns/finread/trend.pdf) |
| 5 | Rebalancing Premium | [SSRN 3982120](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3982120) |
| 6 | Momentum + Volatility | [SSRN 1679464](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=1679464) |
| 7 | Asset-Class Trend | [SSRN 962461](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=962461) |
| 8 | Pairs Trading | [SSRN 141615](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=141615) |
| 9 | Volatility Regime | [SSRN 3829582](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3829582) |
| 10 | Betting Against Beta | [NYU Stern - Frazzini & Pedersen](https://pages.stern.nyu.edu/~lpederse/papers/BettingAgainstBeta.pdf) |
