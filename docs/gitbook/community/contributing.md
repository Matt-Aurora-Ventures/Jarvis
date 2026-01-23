# Contributing to Jarvis

Thank you for your interest in contributing to Jarvis LifeOS! This project is open-source and community-driven.

---

## Ways to Contribute

### 1. Code Contributions

- **Bug fixes**: Found a bug? Submit a PR!
- **New features**: Implement features from the roadmap
- **Strategies**: Add new trading strategies
- **Integrations**: Connect new exchanges or data sources
- **Documentation**: Improve guides and tutorials

### 2. Testing & Feedback

- **Beta testing**: Try new features and report issues
- **Strategy backtesting**: Test trading strategies on historical data
- **UI/UX feedback**: Suggest improvements to interfaces

### 3. Community Support

- **Answer questions**: Help new users on Telegram/GitHub
- **Write tutorials**: Create guides and walkthroughs
- **Translate**: Help translate documentation

### 4. Strategic Input

- **Governance**: Vote on proposals (KR8TIV holders)
- **Feature requests**: Suggest new capabilities
- **Design input**: Shape the future of Jarvis

---

## Development Setup

### Prerequisites

- Python 3.11+
- PostgreSQL 16+
- Node.js 18+ (for frontend)
- Git
- Solana CLI

### Fork & Clone

```bash
# Fork the repository on GitHub
# Then clone your fork
git clone https://github.com/YOUR_USERNAME/Jarvis.git
cd Jarvis

# Add upstream remote
git remote add upstream https://github.com/Matt-Aurora-Ventures/Jarvis.git
```

### Install Dependencies

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt  # Development tools
```

### Set Up Pre-Commit Hooks

```bash
# Install pre-commit
pip install pre-commit

# Install hooks
pre-commit install
```

This runs code formatters and linters before each commit.

---

## Coding Standards

### Python Style

- **PEP 8** compliance (enforced by `ruff`)
- **Type hints** on all functions
- **Docstrings** (Google style) for public functions
- **100 character** line limit

### Example

```python
def calculate_position_size(
    balance: float,
    risk_tier: str,
    max_position_pct: float = 2.0
) -> float:
    """
    Calculate position size based on risk tier.

    Args:
        balance: Available balance in SOL
        risk_tier: Risk classification (ESTABLISHED, MID, MICRO, SHITCOIN)
        max_position_pct: Max position size as % of balance

    Returns:
        Position size in SOL

    Raises:
        ValueError: If risk_tier is invalid
    """
    multiplier = RISK_TIER_MULTIPLIERS.get(risk_tier)
    if not multiplier:
        raise ValueError(f"Invalid risk tier: {risk_tier}")

    return balance * (max_position_pct / 100) * multiplier
```

### Testing

- **Write tests** for all new features
- **100% coverage** for critical paths (trading, risk management)
- **Integration tests** for multi-component features

```bash
# Run tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=core --cov=bots --cov-report=html

# Run specific test file
pytest tests/test_trading.py -v
```

---

## Contribution Workflow

### 1. Pick an Issue

Browse [open issues](https://github.com/Matt-Aurora-Ventures/Jarvis/issues) and comment to claim one.

Or create a new issue to discuss your idea first.

### 2. Create a Branch

```bash
# Update your local main
git checkout main
git pull upstream main

# Create feature branch
git checkout -b feature/your-feature-name

# Or for bug fixes
git checkout -b fix/bug-description
```

### 3. Make Changes

- Write code following style guidelines
- Add tests
- Update documentation
- Keep commits focused and atomic

### 4. Commit

```bash
# Stage changes
git add .

# Commit with descriptive message
git commit -m "feat: add support for XYZ exchange

- Implement XYZ client
- Add integration tests
- Update documentation"
```

**Commit Message Format**:
```
<type>(<scope>): <subject>

<body>

<footer>
```

**Types**: `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`

### 5. Push & Create PR

```bash
# Push to your fork
git push origin feature/your-feature-name

# Create PR on GitHub
# Go to: https://github.com/Matt-Aurora-Ventures/Jarvis/compare
```

**PR Template**:
```markdown
## Description
Brief description of changes

## Related Issue
Fixes #123

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Breaking change
- [ ] Documentation update

## Testing
- [ ] All tests passing
- [ ] Added new tests
- [ ] Manual testing completed

## Checklist
- [ ] Code follows style guidelines
- [ ] Self-review completed
- [ ] Documentation updated
- [ ] No breaking changes (or documented)
```

### 6. Code Review

- Address reviewer feedback
- Make requested changes
- Push updates to your branch
- Once approved, your PR will be merged!

---

## Adding a Trading Strategy

### 1. Create Strategy File

```python
# bots/treasury/strategies/my_strategy.py

from typing import Dict, Optional

def evaluate_signal(
    token_data: Dict,
    market_data: Dict,
    portfolio: Dict
) -> Optional[str]:
    """
    Evaluate if token should be bought, sold, or held.

    Args:
        token_data: Token metrics (price, volume, liquidity)
        market_data: Overall market conditions
        portfolio: Current portfolio state

    Returns:
        "BUY", "SELL", or None
    """
    # Your strategy logic here
    rsi = token_data.get("rsi")
    volume = token_data.get("volume_24h")

    if rsi < 30 and volume > 1000000:
        return "BUY"
    elif rsi > 70:
        return "SELL"

    return None

# Strategy metadata
STRATEGY_NAME = "RSI Volume"
STRATEGY_CATEGORY = "MOMENTUM"
MIN_CONFIDENCE = 0.6
```

### 2. Register Strategy

```python
# bots/treasury/trading.py

from strategies.my_strategy import evaluate_signal as my_strategy

STRATEGIES = [
    # ... existing strategies
    {
        "name": "my_strategy",
        "fn": my_strategy,
        "weight": 1.0,
        "category": "MOMENTUM"
    }
]
```

### 3. Backtest

```bash
python scripts/backtest_strategy.py \
  --strategy my_strategy \
  --start-date 2025-01-01 \
  --end-date 2026-01-01
```

### 4. Submit PR

Include backtest results showing:
- Win rate
- Average P&L
- Max drawdown
- Sharpe ratio

---

## Community Guidelines

### Code of Conduct

We follow the [Contributor Covenant](https://www.contributor-covenant.org/).

**In short**:
- Be respectful and inclusive
- Constructive feedback, no personal attacks
- Focus on the code, not the person
- Help newcomers learn

### Communication Channels

- **GitHub Issues**: Bug reports, feature requests
- **GitHub Discussions**: Design discussions, questions
- **Telegram**: [@Jarviskr8tivbot](https://t.me/Jarviskr8tivbot) - Community chat
- **Twitter**: [@Jarvis_lifeos](https://twitter.com/Jarvis_lifeos) - Updates

---

## Recognition

### Contributor Leaderboard

Top contributors are recognized in:
- `CONTRIBUTORS.md` file
- Monthly Twitter shoutouts
- Potential KR8TIV rewards for significant contributions

### Swag

Contributors with 5+ merged PRs receive Jarvis swag (stickers, t-shirts).

---

## License

By contributing, you agree that your contributions will be licensed under the MIT License.

---

## Getting Help

Stuck or have questions?

- **GitHub Discussions**: [Ask a question](https://github.com/Matt-Aurora-Ventures/Jarvis/discussions)
- **Telegram**: Ping `@matthaynes88` or community mods
- **Email**: dev@jarvislife.io

---

**Thank you for helping build the future of AI context models!** 🚀
