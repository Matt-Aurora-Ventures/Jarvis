# Quantitative Trading Guide

Comprehensive guide for Jarvis's algorithmic trading system covering strategy classification, infrastructure, and best practices.

## Table of Contents

1. [Strategy Categories](#strategy-categories)
2. [Static vs Adaptive Bots](#static-vs-adaptive-bots)
3. [Infrastructure: Flashbots vs Jito](#infrastructure-flashbots-vs-jito)
4. [Risk Assessment](#risk-assessment)
5. [Architecture Overview](#architecture-overview)
6. [Quick Start](#quick-start)

---

## Strategy Categories

### 1. Arbitrage Strategies

#### Triangular Arbitrage
Exploits price discrepancies between three trading pairs.

```
Example: BTC/USDT → ETH/BTC → ETH/USDT
If cross-rate product > 1.0 + fees, profit exists

Module: core/trading_strategies_advanced.py::TriangularArbitrage
```

**Key Features:**
- Scans all 3-pair combinations
- Accounts for fees and slippage
- Flash loan support for DeFi (risk-free capital)

#### Spatial Arbitrage (Cross-DEX)
Exploits price gaps between exchanges.

```
Module: core/trading_strategies.py::ArbitrageScanner
```

---

### 2. MEV (Maximal Extractable Value)

#### Sandwiching on Solana
Uses Jito validator client to bundle transactions:

```
1. Front-run: Buy before victim
2. Victim: Executes at worse price
3. Back-run: Sell at elevated price

Module: core/jito_executor.py::JitoExecutor
```

**Jito Benefits:**
- Private relay (mempool protection)
- Atomic execution (up to 5 txs)
- Bundle simulation before submission

---

### 3. Market Neutral & Yield

#### Grid Trading
Profits from price oscillations in sideways markets.

```
Upper: $105 ─── SELL orders
Current: $100
Lower: $95  ─── BUY orders

Module: core/trading_strategies_advanced.py::GridTrader
```

**Best for:** Ranging markets with <3% daily moves

#### Market Making
Captures bid-ask spread by providing liquidity.

```
Module: core/trading_strategies_advanced.py::MarketMaker
```

**Risk:** Inventory accumulation during trends

---

### 4. Momentum & Trend

#### Moving Average Crossover
```python
# Golden Cross (Bullish): Short MA > Long MA
# Death Cross (Bearish): Short MA < Long MA

Module: core/trading_strategies.py::TrendFollower
```

#### Breakout Trading
Trades support/resistance breaks with volume confirmation.

```
Module: core/trading_strategies_advanced.py::BreakoutTrader
```

---

### 5. AI & Sentiment

#### AI Agents vs Static Bots

| Aspect | Static Bot | AI Agent |
|--------|------------|----------|
| Rules | Fixed | Adaptive |
| Regime Detection | None | ML-based |
| Strategy Switching | Manual | Automatic |
| Learning | None | Continuous |

```
Module: core/ml_regime_detector.py::AdaptiveStrategySwitcher
```

#### Sentiment Analysis
```
Module: core/trading_strategies.py::SentimentAnalyzer
```

---

## Static vs Adaptive Bots

### Static Bots (Rule-Based)
- Execute predefined rules without adaptation
- Examples: Simple grid, DCA, fixed MA crossover
- **Weakness:** Fail in changing market conditions

### AI Agents (LLM-Enhanced)
- Use ML for regime detection
- Dynamically switch strategies
- Learn from execution results

```python
# Automatic strategy switching based on volatility
from core.ml_regime_detector import AdaptiveStrategySwitcher

switcher = AdaptiveStrategySwitcher()
result = switcher.update(prices)
# Returns: {"current_strategy": "GridTrader", "regime": "low_volatility"}
```

**Regime → Strategy Mapping:**
| Regime | Strategy | Why |
|--------|----------|-----|
| Low Volatility | Grid Trading | Range-bound profit |
| Medium Volatility | Mean Reversion | RSI/BB signals work |
| High Volatility | Trend Following | Strong directional moves |
| Extreme Volatility | Risk-Off | Preserve capital |

---

## Infrastructure: Flashbots vs Jito

### Ethereum: Flashbots
- **Protect:** Submit to private mempool
- **Builder API:** Propose blocks directly
- **MEV-Share:** Split MEV with users

### Solana: Jito Block Engine
- **Bundle submission:** Up to 5 atomic transactions
- **Tip accounts:** Pay validators for inclusion
- **Bundle simulation:** Test before sending

```python
# Jito bundle submission
from core.jito_executor import JitoExecutor

executor = JitoExecutor()
result = await executor.send_bundle(
    transactions=[tx1, tx2, tx3],
    estimated_profit=500_000_000,  # 0.5 SOL
    simulate_first=True,
)
```

**Key Differences:**

| Feature | Flashbots | Jito |
|---------|-----------|------|
| Chain | Ethereum | Solana |
| Max Bundle Size | Unlimited | 5 txs |
| Latency | ~12s blocks | ~400ms slots |
| Tip Model | Priority fee | Tip accounts |

---

## Risk Assessment

### Mean Reversion Limitations
**Risk:** Strong trending markets break mean reversion.

```
When trending:
- Price stays above/below Bollinger Bands
- RSI stays overbought/oversold for extended periods
- Entries become "catching falling knives"

Mitigation:
1. Use trend filter (ADX > 25 = don't mean revert)
2. Reduce position size in high volatility
3. Combine with regime detection
```

### Market Making Inventory Risk
**Risk:** Accumulated positions during crashes.

```
Example:
- Market crashes 20%
- Bot keeps buying dips
- Inventory grows (all underwater)
- Recovery may take months

Mitigation:
1. Max inventory limits
2. Inventory skew (quote away from position)
3. Volatility-based spread widening
4. Circuit breaker on % drawdown
```

### Slippage and Failed Transactions
```python
from core.security_hardening import SlippageChecker

checker = SlippageChecker(default_tolerance_bps=50)
result = checker.check(expected=100.0, executed=101.0)
# {"passed": False, "slippage_bps": 100, "message": "Exceeds tolerance"}
```

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│                    DATA LAYER ("Eyes")                  │
│  core/data_ingestion.py                                 │
│  - WebSocket streams (Binance, Kraken)                  │
│  - CCXT exchange normalization                          │
│  - Tick buffer & OHLCV aggregation                      │
└─────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────┐
│                  STRATEGY LAYER ("Brain")               │
│  core/trading_strategies.py                             │
│  core/trading_strategies_advanced.py                    │
│  core/ml_regime_detector.py                             │
│  - TrendFollower, MeanReversion, GridTrader, etc.       │
│  - ML regime detection & adaptive switching             │
└─────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────┐
│                 EXECUTION LAYER ("Hands")               │
│  core/jito_executor.py (Solana)                         │
│  core/trading_pipeline.py (General)                     │
│  - Smart Order Routing                                  │
│  - Bundle simulation & submission                       │
│  - Paper trading & backtesting                          │
└─────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────┐
│                   RISK LAYER ("Shield")                 │
│  core/risk_manager.py                                   │
│  core/security_hardening.py                             │
│  - Stop-loss / Take-profit                              │
│  - Position sizing (Kelly-inspired)                     │
│  - Slippage tolerance                                   │
│  - Encrypted API key storage                            │
└─────────────────────────────────────────────────────────┘
```

---

## Quick Start

### 1. Install Dependencies
```bash
pip install ccxt websockets scikit-learn numpy aiohttp
# For Solana: pip install solders
# For encryption: pip install cryptography
```

### 2. Strategy Usage
```python
from core.trading_strategies_advanced import TriangularArbitrage, GridTrader

# Triangular Arbitrage
arb = TriangularArbitrage(min_profit_pct=0.1)
opp = arb.scan_triangle("BTC", "ETH", "USDT", prices)

# Grid Trading
grid = GridTrader(upper_bound=105, lower_bound=95, num_grids=10)
signal = grid.analyze(prices, symbol="BTC/USDT")
```

### 3. ML Regime Detection
```python
from core.ml_regime_detector import VolatilityRegimeDetector

detector = VolatilityRegimeDetector()
detector.fit(historical_prices)  # Train on history
prediction = detector.predict(recent_prices)
# prediction.regime: "high_volatility"
# prediction.recommended_strategy: "TrendFollower"
```

### 4. Secure Key Storage
```python
from core.security_hardening import SecureKeyManager

manager = SecureKeyManager()
manager.store_key("binance", api_key, password="secret", ip_whitelist=["127.0.0.1"])
api_key = manager.get_key("binance", password="secret")
```

---

## Security Best Practices

### Lessons from 3Commas Breach (Dec 2022)
- **Problem:** API keys stored unencrypted
- **Loss:** $22M+ in user funds
- **Our Solution:** Fernet encryption + PBKDF2 key derivation

### Required Practices
1. ✅ Encrypt API keys at rest
2. ✅ IP whitelist all exchange API keys
3. ✅ Enable 2FA on exchange accounts
4. ✅ Use withdrawal whitelist on exchanges
5. ✅ Never commit secrets to git
6. ✅ Rotate keys regularly

### Audit Your Code
```bash
python3 -c "
from core.security_hardening import SecurityAuditor
auditor = SecurityAuditor()
issues = auditor.scan_directory('/path/to/code')
print(auditor.generate_report(issues))
"
```

---

*Built for Jarvis v2.0 - Autonomous Trading System*
