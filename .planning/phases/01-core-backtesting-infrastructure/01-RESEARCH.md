# Phase 1: Core Backtesting Infrastructure [PyTorch] - Research

**Researched:** 2026-02-24
**Domain:** Algorithmic Trading Backtesting (PyTorch, CoinGecko, Python)
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

No user constraints - all decisions at Claude's discretion. The primary constraint is from the ROADMAP and REQUIREMENTS to integrate CoinGecko API and use PyTorch for auto-tuning.
</user_constraints>

<research_summary>
## Summary

Researched the existing Python ecosystem for deep-learning-based crypto backtesting. The standard approach utilizes `pandas`, `numpy`, and `PyTorch` for historical sequence modeling (LSTMs or Transformers).
To auto-tune hyperparameters efficiently, standard Bayesian optimization or libraries like `Optuna` or `Ray Tune` are heavily favored as compared to custom random search grids.

Key finding: Don't hand-roll a data pipeline; utilize `pandas` for efficient time-series alignment of CoinGecko OHLCV + Volume + Market Cap data. Build a structured PyTorch `Dataset` that standardizes inputs before tuning the sniper logic.

**Primary recommendation:** Use `pandas` for data structuring, `torch.utils.data.Dataset` for pipeline feeding, and `Optuna` or standard `PyTorch` gradient-based tuning for hyper-parameters.
</research_summary>

<standard_stack>
## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| torch | >=2.0.0 | Deep learning | The standard for ML modeling |
| pandas | >=2.0.0 | Time-series data | Efficient data alignment and OHLCV storage |
| optuna | >=3.0.0 | Hyperparam Auto-tune | Best-in-class, easy API for parameter search |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| requests | >=2.30.0 | API fetching | CoinGecko historical data |
| scikit-learn | >=1.3.0 | Data Scaling | Normalizing prices/volumes before PyTorch |
</standard_stack>

<architecture_patterns>
## Architecture Patterns

### Recommended Project Structure
```
core/backtest/
├── data_ingestion/       # CoinGecko API wrappers
├── dataset/              # PyTorch Dataset definitions
├── models/               # PyTorch sniper network architectures
└── tuner/                # Optuna automatic parameter search
```

### Pattern 1: CoinGecko Caching
**What:** Always cache CoinGecko historical data.
**When to use:** Whenever fetching >1 day of OHLCV to avoid rate limits.
**Example:** Save `/v3/coins/{id}/market_chart` responses to `data/cache/` as Parquet or CSV.

### Pattern 2: PyTorch Time-Series Dataset
**What:** Use sliding windows of `block_size` to predict the next `N` changes to feed into the bot signal emulation.
</architecture_patterns>

<dont_hand_roll>
## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Hyperparameter Search | Custom loops / grid search | Optuna | Better performance, pruning bad trials |
| Time-series alignment | Custom array parsing | Pandas DataFrames | `df.resample()` and `ffill()` handle missing data |
</dont_hand_roll>

<common_pitfalls>
## Common Pitfalls

### Pitfall 1: Look-ahead bias
**What goes wrong:** Model gets future data, achieves 100% accuracy in backtest.
**How to avoid:** Ensure that at timestep `T`, only data up to `T` is fed to the model and strategy.

### Pitfall 2: CoinGecko Rate Limits
**What goes wrong:** Free tier gets rate-limited instantly.
**How to avoid:** Implement strict retry headers and disk caching for all OHLCV fetch operations.
</common_pitfalls>

<code_examples>
## Code Examples

### Basic Coingecko Wrapper
```python
import requests
import pandas as pd
import time

def fetch_historical_data(coin_id, days):
    url = f"https://api.coingecko.com/api/v3/coins/{coin_id}/market_chart?vs_currency=usd&days={days}"
    resp = requests.get(url)
    if resp.status_code == 429:
        time.sleep(60)
    data = resp.json()
    # Process into Pandas...
    return pd.DataFrame(data['prices'], columns=['timestamp', 'price'])
```
</code_examples>

<sota_updates>
## State of the Art (2024-2025)
Standard continuous optimization uses ML models with reinforcement learning or Bayesian search rather than simple crossovers.
</sota_updates>

<sources>
## Sources
- PyTorch Official Docs
- CoinGecko API Docs
</sources>

<metadata>
## Metadata
**Research date:** 2026-02-24
**Valid until:** 2026-03-24
</metadata>
