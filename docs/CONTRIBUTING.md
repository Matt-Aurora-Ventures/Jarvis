# Contributing to JARVIS

Thank you for your interest in contributing to JARVIS! This guide will help you
get started with the contribution process.

---

## Table of Contents

1. [Code of Conduct](#code-of-conduct)
2. [Getting Started](#getting-started)
3. [Development Workflow](#development-workflow)
4. [Pull Request Process](#pull-request-process)
5. [Coding Standards](#coding-standards)
6. [Testing Requirements](#testing-requirements)
7. [Documentation](#documentation)
8. [Issue Guidelines](#issue-guidelines)

---

## Code of Conduct

We are committed to providing a welcoming and respectful environment. Please:

- Be respectful and inclusive
- Use welcoming and inclusive language
- Accept constructive criticism gracefully
- Focus on what is best for the community
- Show empathy towards other contributors

---

## Getting Started

### Prerequisites

- Python 3.10 or higher
- Git
- Basic understanding of async Python
- Familiarity with FastAPI and Telegram/Twitter APIs (helpful)

### Setting Up Your Development Environment

1. **Fork the repository**

   Click the "Fork" button on GitHub to create your own copy.

2. **Clone your fork**

   ```bash
   git clone https://github.com/YOUR_USERNAME/jarvis.git
   cd jarvis
   ```

3. **Set up upstream remote**

   ```bash
   git remote add upstream https://github.com/ORIGINAL_OWNER/jarvis.git
   ```

4. **Create a virtual environment**

   ```bash
   python -m venv venv
   source venv/bin/activate  # Linux/Mac
   # or
   venv\Scripts\activate  # Windows
   ```

5. **Install dependencies**

   ```bash
   pip install -r requirements.txt
   pip install -r requirements-dev.txt
   ```

6. **Set up pre-commit hooks**

   ```bash
   pre-commit install
   ```

7. **Configure environment**

   ```bash
   cp env.example .env
   # Edit .env with your API keys (for testing)
   ```

---

## Development Workflow

### 1. Create a Branch

Always create a new branch for your work:

```bash
git checkout main
git pull upstream main
git checkout -b feature/your-feature-name
```

Branch naming conventions:
- `feature/` - New features
- `fix/` - Bug fixes
- `docs/` - Documentation updates
- `refactor/` - Code refactoring
- `test/` - Test additions

### 2. Make Your Changes

- Write clean, readable code
- Follow the [code style guide](CODE_STYLE.md)
- Add tests for new functionality
- Update documentation as needed

### 3. Run Tests

```bash
# Run all tests
pytest tests/

# Run specific test file
pytest tests/test_trading.py

# Run with coverage
pytest --cov=core tests/
```

### 4. Run Linting

```bash
# Format code
black core/ api/ bots/

# Run linter
ruff core/ api/ bots/

# Type checking
mypy core/
```

### 5. Commit Your Changes

Follow our [commit message conventions](COMMIT_CONVENTIONS.md):

```bash
git add .
git commit -m "feat(api): add user preferences endpoint"
```

### 6. Push and Create PR

```bash
git push origin feature/your-feature-name
```

Then create a Pull Request on GitHub.

---

## Pull Request Process

### Before Submitting

- [ ] Tests pass locally
- [ ] Code is formatted with Black
- [ ] Linting passes with Ruff
- [ ] Documentation is updated
- [ ] Commit messages follow conventions
- [ ] PR description explains changes

### PR Template

When creating a PR, include:

```markdown
## Description
Brief description of changes

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Breaking change
- [ ] Documentation update

## Testing
How have you tested this?

## Checklist
- [ ] Tests added/updated
- [ ] Documentation updated
- [ ] No breaking changes (or documented)
```

### Review Process

1. A maintainer will review your PR
2. Address any feedback or requested changes
3. Once approved, a maintainer will merge your PR

---

## Coding Standards

### Python Style

- Use Black for formatting (line length 88)
- Use Ruff for linting
- Follow PEP 8 guidelines
- Use type hints

### Naming Conventions

```python
# Variables and functions: snake_case
user_name = "Alice"
def get_user_by_id(): ...

# Classes: PascalCase
class UserService: ...

# Constants: SCREAMING_SNAKE_CASE
MAX_RETRIES = 3
```

### Documentation

- Write docstrings for all public functions and classes
- Use Google-style docstrings
- Update README for significant changes

```python
def process_trade(symbol: str, amount: float) -> TradeResult:
    """
    Process a trade order.

    Args:
        symbol: Trading pair symbol
        amount: Amount to trade

    Returns:
        TradeResult with execution details

    Raises:
        InvalidSymbolError: If symbol is not supported
    """
```

---

## Testing Requirements

### Test Coverage

- Aim for 80%+ coverage on new code
- All bug fixes must include a regression test
- New features require unit and integration tests

### Test Structure

```python
def test_feature_does_expected_behavior():
    # Arrange
    input_data = {...}

    # Act
    result = feature(input_data)

    # Assert
    assert result.status == "success"
```

### Running Tests

```bash
# All tests
pytest tests/

# With coverage
pytest --cov=core --cov-report=html tests/

# Specific markers
pytest -m "not slow" tests/
```

---

## Documentation

### When to Update Docs

- New features or APIs
- Changed behavior
- Configuration changes
- New dependencies

### Documentation Locations

| Type | Location |
|------|----------|
| API docs | `docs/API_DOCUMENTATION.md` |
| Architecture | `docs/architecture/README.md` |
| Setup guide | `docs/DEVELOPER_SETUP.md` |
| Troubleshooting | `docs/TROUBLESHOOTING.md` |

---

## Issue Guidelines

### Reporting Bugs

Include:
- Clear description of the bug
- Steps to reproduce
- Expected vs actual behavior
- Environment details (OS, Python version)
- Error messages/logs

### Feature Requests

Include:
- Clear description of the feature
- Use case / problem it solves
- Proposed solution (if any)
- Willingness to implement

### Issue Labels

| Label | Description |
|-------|-------------|
| `bug` | Something isn't working |
| `enhancement` | New feature request |
| `documentation` | Documentation improvements |
| `good first issue` | Good for newcomers |
| `help wanted` | Extra attention needed |

---

## Questions?

- Check existing issues and documentation
- Join our community chat
- Open a discussion on GitHub

Thank you for contributing to JARVIS!
