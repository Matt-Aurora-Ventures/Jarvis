# LifeOS Trading System - AI Context Document

**Purpose**: This document provides comprehensive context for any AI model (local Ollama, MiniMax 2.1, Claude, GPT, etc.) to understand the LifeOS trading system instantly.

---

## System Overview

LifeOS is an autonomous trading system for Solana with:
- 10+ trading strategies across 5 categories
- Paper trading + live execution (with human approval)
- Self-improvement and learning capabilities
- Voice control and computer automation

---

## Strategy Categories

### 1. Arbitrage (Lowest Latency)
| Strategy | Description | Regime Fit |
|----------|-------------|------------|
| TriangularArbitrage | Cross-rate exploitation (BTC→ETH→USDT→BTC) | All |
| ArbitrageScanner | Cross-DEX price discrepancy | Volatile |

### 2. Momentum (Trend Following)
| Strategy | Description | Regime Fit |
|----------|-------------|------------|
| TrendFollower | MA crossover (golden/death cross) | Trending |
| BreakoutTrader | S/R break with volume confirmation | Trending, Volatile |

### 3. Mean Reversion
| Strategy | Description | Regime Fit |
|----------|-------------|------------|
| MeanReversion | Bollinger Bands + RSI oversold/overbought | Chopping, Calm |

### 4. Market Neutral
| Strategy | Description | Regime Fit |
|----------|-------------|------------|
| GridTrader | Range-bound order grid | Chopping, Calm |
| DCABot | Dollar-cost averaging | All |
| MarketMaker | Bid-ask spread capture | Chopping, Calm |

### 5. AI Adaptive
| Strategy | Description | Regime Fit |
|----------|-------------|------------|
| RegimeDetector | ML-based market classification | All |
| SentimentAnalyzer | NLP sentiment from social/news | Volatile |

---

## Decision Flow (5 Phases)

```
1. SENTIMENT → Analyze volume, volatility, fear/greed
   Output: Bullish / Neutral / Bearish

2. REGIME → Linear regression on prices, R² threshold
   Output: trending / chopping

3. STRATEGY → Match regime to decision matrix
   Output: Strategy name

4. SIGNAL → Execute strategy on price data
   Output: BUY / SELL / HOLD + confidence

5. GATE → Validate risk, ROI velocity, confidence
   Output: EXECUTE or WAIT
```

---

## Key Files (Priority Reading Order)

1. **`core/trading_decision_matrix.py`** - ALL strategy definitions
2. **`core/logic_core.py`** - Decision engine
3. **`core/trading_strategies.py`** - Basic strategy implementations
4. **`core/trading_strategies_advanced.py`** - Advanced strategies
5. **`core/solana_execution.py`** - Swap execution
6. **`core/exit_intents.py`** - TP/SL management
7. **`core/risk_manager.py`** - Risk controls

---

## Solana Execution Stack

```
Jupiter API (quotes) → Transaction Build → Simulation
                                              ↓
                    Helius RPC ← RPC Failover System
                                              ↓
                              Jito Bundle (MEV protection)
                                              ↓
                              Confirmation + Logging
```

---

## Safety Rules (MANDATORY)

1. **PAPER MODE DEFAULT** - All tests use `is_paper=True`
2. **HUMAN APPROVAL** - Live trades require explicit approval
3. **CIRCUIT BREAKER** - Stops at 10% drawdown
4. **SIMULATION FIRST** - Always `simulate_transaction()` before execute
5. **CONFIDENCE THRESHOLD** - Minimum 0.55 required
6. **POSITION LIMIT** - Max 8% of capital per trade

---

## Common Commands

```python
# Get decision matrix
from core.trading_decision_matrix import get_decision_matrix
matrix = get_decision_matrix()

# Select strategy for regime
strategy = matrix.select_strategy_for_regime("trending")

# Run logic core cycle
from core.logic_core import LogicCore, MarketSnapshot
lc = LogicCore()
snapshot = MarketSnapshot(symbol="SOL", prices=[...])
decision = lc.run_cycle(snapshot)

# Export training data
matrix.save_training_data()
```

---

## For Model Training

To train a local model on this system:

1. Load `data/training_data/strategy_catalog.json`
2. Use system prompt from `matrix.get_system_prompt()`
3. Include example trades from each strategy
4. Test with dry-run execution flows

---

## Version History

- **v2.0.0** (2026-01-05): Unified decision matrix, 10 strategies
- **v1.5.0** (2026-01-03): Added walk-forward validation
- **v1.0.0** (2025-12-28): Initial trading pipeline
