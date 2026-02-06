# Contributing to Jarvis

Thank you for your interest in contributing to Jarvis, the persistent personal context engine. This document provides guidelines for contributing to the project.

## Table of Contents

- [Getting Started](#getting-started)
- [Development Environment Setup](#development-environment-setup)
- [Code Style Guidelines](#code-style-guidelines)
- [Testing](#testing)
- [Submitting Changes](#submitting-changes)
- [Commit Message Format](#commit-message-format)
- [Areas We Need Help](#areas-we-need-help)

## Getting Started

1. **Fork the repository** on GitHub
2. **Clone your fork** locally:
   ```bash
   git clone https://github.com/YOUR_USERNAME/Jarvis.git
   cd Jarvis
   ```
3. **Add upstream remote**:
   ```bash
   git remote add upstream https://github.com/Matt-Aurora-Ventures/Jarvis.git
   ```

## Development Environment Setup

### Prerequisites

- Python 3.11+
- PostgreSQL 14+ (for semantic memory)
- Node.js 18+ (for frontend development)
- Solana CLI (for trading features)
- Git

### Python Environment

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Install development dependencies
pip install pytest pytest-asyncio pytest-cov pytest-mock ruff mypy
```

### Environment Variables

```bash
# Copy example environment file
cp .env.example .env

# Edit .env with your configuration
# At minimum, set:
# - DATABASE_URL (PostgreSQL connection string)
# - TREASURY_LIVE_MODE=false (for testing)
```

### Database Setup

```bash
# Initialize the database
python scripts/init_db.py

# Verify setup
python scripts/verify_mcp_setup.py
```

### Verify Installation

```bash
# Run smoke tests to verify setup
pytest tests/test_smoke.py -v
```

## Code Style Guidelines

### Python

We follow **PEP 8** with some project-specific conventions:

```python
# Type hints required for all function signatures
def process_trade(
    token_address: str,
    amount: float,
    stop_loss: float | None = None
) -> dict[str, Any]:
    """Process a trade execution.

    Args:
        token_address: Solana token address
        amount: Trade amount in SOL
        stop_loss: Optional stop loss percentage

    Returns:
        Trade execution result with status and transaction ID

    Raises:
        ValueError: If amount is negative or zero
        InsufficientFundsError: If balance is too low
    """
    pass
```

**Guidelines**:
- Use type hints for all function parameters and return values
- Write docstrings for all public functions (Google style)
- Use meaningful variable names (no single-letter names except in loops)
- Keep functions under 50 lines (split if longer)
- Use `pathlib.Path` for file operations, not string concatenation
- Prefer f-strings over `.format()` or `%` formatting

**Imports**:
```python
# Standard library first
import sys
from pathlib import Path

# Third-party packages
import requests
from anthropic import Anthropic

# Local modules
from core import config
from core.memory import auto_import
```

### TypeScript/JavaScript

For frontend contributions:

```typescript
// Use TypeScript for type safety
interface TradeRequest {
  tokenAddress: string;
  amount: number;
  stopLoss?: number;
}

// Functional components with hooks
const TradingPanel: React.FC<Props> = ({ portfolio }) => {
  const [isLoading, setIsLoading] = useState(false);

  return (
    <div className="trading-panel">
      {/* component JSX */}
    </div>
  );
};
```

**Guidelines**:
- Use TypeScript, not plain JavaScript
- Functional components over class components
- ESLint + Prettier for formatting
- Use React hooks (useState, useEffect, etc.)

### Code Quality Tools

Run these before committing:

```bash
# Python linting and formatting
ruff check .
ruff format .

# Type checking
mypy core/ bots/ tg_bot/

# Frontend linting
cd frontend
npm run lint
npm run format
```

## Testing

### Running Tests

```bash
# All tests
pytest

# Specific test file
pytest tests/test_smoke.py

# With coverage report
pytest --cov=core --cov=bots --cov-report=html

# Verbose output
pytest -v

# Run only fast tests (skip integration)
pytest -m "not integration"
```

### Writing Tests

**Test Structure**:
```python
"""Module description.

Tests for XYZ functionality.
"""

import pytest
from core.module import function_to_test


class TestFeatureName:
    """Test suite for feature name."""

    def test_basic_functionality(self):
        """Test basic case."""
        result = function_to_test(input_data)
        assert result == expected_output

    def test_error_handling(self):
        """Test error cases."""
        with pytest.raises(ValueError):
            function_to_test(invalid_input)

    @pytest.mark.asyncio
    async def test_async_function(self):
        """Test async functionality."""
        result = await async_function()
        assert result is not None
```

**Coverage Requirements**:
- **80%+ coverage** for new code
- All public functions must have tests
- Edge cases and error conditions must be tested
- Integration tests for critical paths (trading, memory, bots)

**Testing Guidelines**:
- Use pytest fixtures for setup/teardown
- Mock external API calls (use `pytest-mock` or `responses`)
- Test files should mirror source structure: `core/module.py` → `tests/test_module.py`
- Use descriptive test names: `test_trade_execution_with_insufficient_balance`

## Submitting Changes

### Before You Submit

1. **Read the requirements**: Check [docs/ULTIMATE_MASTER_GSD_JAN_31_2026.md](docs/ULTIMATE_MASTER_GSD_JAN_31_2026.md) to see if your change is already planned
2. **Check existing issues**: Search for related issues or PRs
3. **Discuss major changes**: Open an issue first for architectural changes or new features

### Pull Request Process

1. **Create a feature branch**:
   ```bash
   git checkout -b feature/your-feature-name
   # or
   git checkout -b fix/bug-description
   ```

2. **Make your changes**:
   - Follow code style guidelines
   - Add/update tests
   - Update documentation if needed

3. **Test your changes**:
   ```bash
   pytest tests/
   ruff check .
   mypy core/
   ```

4. **Commit your changes** (see [Commit Message Format](#commit-message-format))

5. **Push to your fork**:
   ```bash
   git push origin feature/your-feature-name
   ```

6. **Open a Pull Request**:
   - Use the PR template (auto-populated)
   - Fill out all sections
   - Link related issues
   - Request review

### PR Requirements

- [ ] Code follows style guidelines
- [ ] Tests added/updated (80%+ coverage)
- [ ] All tests pass
- [ ] Documentation updated
- [ ] Commit messages follow format
- [ ] No merge conflicts
- [ ] For research-driven changes: citations and evaluation plan included

## Commit Message Format

We use **Conventional Commits** with some project-specific types:

```
<type>(<scope>): <subject>

<body>

<footer>
```

### Types

| Type | Use For |
|------|---------|
| `feat` | New feature |
| `fix` | Bug fix |
| `docs` | Documentation only |
| `style` | Code style (formatting, missing semicolons, etc.) |
| `refactor` | Code restructuring without changing behavior |
| `perf` | Performance improvement |
| `test` | Adding or updating tests |
| `chore` | Build process, dependencies, tooling |
| `security` | Security fixes or improvements |

### Scopes

Common scopes:
- `trading` - Trading engine
- `telegram` - Telegram bot
- `twitter` - Twitter/X bot
- `memory` - Memory/MCP system
- `api` - API server
- `frontend` - Web dashboard
- `core` - Core utilities
- `security` - Security features

### Examples

```
feat(trading): add multi-wallet support for position diversification

Implements support for managing multiple Solana wallets to distribute
trading positions and reduce single-wallet risk.

- Add wallet rotation logic in position_manager.py
- Create wallet pool configuration in treasury/config.py
- Add tests for wallet selection algorithm

Closes #123
```

```
fix(telegram): prevent duplicate lock acquisition on Windows

The bot was attempting to acquire the same file lock twice, causing
an infinite loop on Windows due to msvcrt.locking behavior.

Removed redundant acquire_instance_lock() call at line 330.

Fixes #456
```

```
docs(readme): update deployment instructions for systemd

Added missing steps for systemd service setup and clarified
deploy.sh usage for automated service file generation.
```

### Commit Message Rules

- Use present tense ("add feature" not "added feature")
- Use imperative mood ("move cursor to..." not "moves cursor to...")
- First line <= 72 characters
- Reference issues and PRs in footer
- For breaking changes, add `BREAKING CHANGE:` in footer

## Areas We Need Help

We welcome contributions in these areas:

### High Priority

| Area | Description | Difficulty |
|------|-------------|------------|
| **Security Fixes** | Address GitHub Dependabot alerts (49 vulnerabilities) | Medium |
| **Trading Strategies** | Implement new signal generation algorithms | Hard |
| **Test Coverage** | Increase test coverage to 80%+ | Easy-Medium |
| **Documentation** | Improve guides, add tutorials | Easy |

### Features

| Area | Description | Difficulty |
|------|-------------|------------|
| **iOS/Android Apps** | Mobile application development | Hard |
| **Discord Bot** | Bot integration for Discord | Medium |
| **Browser Extension** | Chrome/Firefox extension | Medium |
| **Strategy Builder** | No-code strategy creation UI | Hard |
| **Multi-Language Support** | Internationalization (i18n) | Medium |

### Infrastructure

| Area | Description | Difficulty |
|------|-------------|------------|
| **CI/CD Improvements** | GitHub Actions enhancements | Medium |
| **Monitoring** | Prometheus/Grafana dashboards | Medium |
| **Performance** | Query optimization, caching | Hard |
| **Docker Optimization** | Reduce image size, multi-stage builds | Medium |

### Good First Issues

Look for issues tagged with `good-first-issue`:
- Documentation improvements
- Small bug fixes
- Test additions
- Code style updates

## Questions?

- **General questions**: Open a discussion on GitHub
- **Bug reports**: Open an issue with the bug template
- **Feature requests**: Open an issue with the feature template
- **Security issues**: Email security@lifeos.ai (do NOT open public issues)

## Code of Conduct

Please read our [Code of Conduct](CODE_OF_CONDUCT.md) before contributing. We are committed to providing a welcoming and inclusive environment for all contributors.

## License

By contributing to Jarvis, you agree that your contributions will be licensed under the MIT License.

---

**Thank you for contributing to Jarvis!** 🚀

Your contributions help build the future of autonomous AI systems.
