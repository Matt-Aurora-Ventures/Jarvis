# Solana Trading Expansion Roadmap

**Generated**: 2026-01-05
**Status**: Ready for Implementation

---

## 1. Immediate Improvements (This Sprint)

### 1.1 Decision Matrix Enhancements
- [x] Unified strategy registry (10 strategies)
- [x] Logic Core integration
- [x] Training data export for AI models
- [ ] Add real-time regime detection using ML
- [ ] Connect opportunity_engine.py to decision matrix

### 1.2 Loop Closing Opportunities
| Loop | Current State | Fix |
|------|--------------|-----|
| Strategy → Execution | Manual bridge | Add auto-routing to Jupiter |
| Signal → Exit Intent | Separate systems | Unify in decision matrix |
| Backtest → Live | Manual promotion | Add approval gate flow |
| Error → Learning | Logs only | Feed to self-improvement engine |

---

## 2. Solana-Specific Enhancements

### 2.1 Execution Improvements
- **Jito Bundle Optimization**: Dynamic tip calculation based on network congestion
- **RPC Health Scoring**: Track latency/success rates per endpoint
- **Transaction Retry Logic**: Smarter blockhash refresh timing
- **Priority Fee Estimation**: Use getRecentPrioritizationFees

### 2.2 Data Sources to Add
| Source | Purpose | Priority |
|--------|---------|----------|
| Helius Webhooks | Real-time token events | P0 |
| Jupiter Price API v2 | Better price feeds | P1 |
| Birdeye Pro API | Volume/liquidity data | P1 |
| Tensor NFT API | NFT floor prices | P2 |

### 2.3 MEV Opportunities
- **Sandwich Detection**: Monitor mempool for front-run protection
- **Arbitrage Routes**: Multi-hop DEX paths via Jupiter
- **Liquidation Monitoring**: Track lending protocols (Marginfi, Kamino)

---

## 3. Decision Making Improvements

### 3.1 ML Model Enhancements
```
Current: Linear regression for regime detection
Upgrade: 
  → Random Forest ensemble for regime
  → LSTM for price prediction
  → Transformer for sentiment analysis
```

### 3.2 Risk Management Additions
- **Correlation Matrix**: Block correlated positions
- **Drawdown Prediction**: Early warning system
- **Position Aging**: Force exits on stale positions
- **Volatility Scaling**: Reduce size in high VIX

### 3.3 Self-Learning Loop
```
Trade Outcome → Performance Analysis → Strategy Score Update
                                              ↓
                                    DSPy Prompt Optimization
                                              ↓
                                    Model Fine-tuning Data
```

---

## 4. Model Training Unification

### 4.1 Current Problem
> "Each time I boot this up with a different model in a different IDE it acts totally different"

### 4.2 Solution: Unified Context Files
| File | Purpose | For Models |
|------|---------|------------|
| `docs/TRADING_AI_CONTEXT.md` | System overview | All |
| `core/trading_decision_matrix.py` | Strategy definitions | Code-aware |
| `data/training_data/strategy_catalog.json` | Structured data | Fine-tuning |

### 4.3 Model-Specific Adaptations
```python
# For MiniMax 2.1 / Local Ollama
context = get_decision_matrix().get_system_prompt()

# Include in every prompt:
system_message = f"""
{context}

Current Mode: Paper Trading
Safety: All trades require simulation before execution
"""
```

### 4.4 Training Data Pipeline
```bash
# Export training data
python -c "from core.trading_decision_matrix import export_training_data_to_file; export_training_data_to_file()"

# Use in fine-tuning
# 1. Load strategy_catalog.json
# 2. Generate Q&A pairs for each strategy
# 3. Include example trades as demonstrations
```

---

## 5. Future Chain Expansion

### 5.1 Architecture for Multi-Chain
```
┌─────────────────────────────────────────────┐
│           Decision Matrix (Unified)          │
└─────────────────────────────────────────────┘
                      │
    ┌─────────────────┼─────────────────┐
    ↓                 ↓                 ↓
┌─────────┐     ┌─────────┐     ┌─────────┐
│ Solana  │     │Ethereum │     │  Base   │
│Executor │     │Executor │     │Executor │
└─────────┘     └─────────┘     └─────────┘
    │                 │                 │
    ↓                 ↓                 ↓
Jupiter          Uniswap           Aerodrome
Jito            Flashbots          (future)
```

### 5.2 Chain Priority Order
1. **Solana** (Current) - Fast, cheap, Jupiter/Jito integrated
2. **Base** (Next) - Low fees, growing DeFi
3. **Ethereum L2s** - Arbitrum, Optimism for larger liquidity
4. **Monad** (Future) - When mainnet launches

---

## 6. Action Items

### This Week
1. [ ] Run full integration test suite with pytest
2. [ ] Export training data and test with local Ollama
3. [ ] Connect opportunity_engine to decision matrix
4. [ ] Fix remaining error handlers (add logging)

### Next Week
1. [ ] Implement Helius webhooks for token events
2. [ ] Add correlation limits to risk manager
3. [ ] Create approval gate UI for live trades
4. [ ] Test MiniMax 2.1 with unified context

### This Month
1. [ ] ML regime detector upgrade
2. [ ] Self-learning feedback loop
3. [ ] Base chain executor (prototype)
