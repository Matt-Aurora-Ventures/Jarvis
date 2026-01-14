# JARVIS Code Style Guide

## Overview

This guide establishes coding standards for the JARVIS project to ensure
consistency, readability, and maintainability across the codebase.

---

## Table of Contents

1. [Python Style](#python-style)
2. [Naming Conventions](#naming-conventions)
3. [Documentation](#documentation)
4. [Type Hints](#type-hints)
5. [Error Handling](#error-handling)
6. [Testing](#testing)
7. [Git Practices](#git-practices)

---

## Python Style

### Formatting

We use **Black** for code formatting with a line length of 88 characters.

```bash
# Format code
black core/ api/ bots/

# Check formatting
black --check core/ api/ bots/
```

### Linting

We use **Ruff** for linting.

```bash
# Run linter
ruff core/ api/ bots/

# Fix auto-fixable issues
ruff --fix core/ api/ bots/
```

### Import Organization

Imports should be organized in three groups:
1. Standard library
2. Third-party packages
3. Local modules

```python
# Standard library
import os
import sys
from datetime import datetime
from typing import Dict, List, Optional

# Third-party
import httpx
from fastapi import FastAPI
from pydantic import BaseModel

# Local
from core.config import settings
from core.providers import get_provider
```

Use `isort` or Ruff's import sorting:

```bash
ruff --select I --fix core/
```

---

## Naming Conventions

### Variables and Functions

Use `snake_case` for variables and functions:

```python
# Good
user_name = "Alice"
def get_user_by_id(user_id: str) -> User:
    ...

# Bad
userName = "Alice"
def GetUserById(userId):
    ...
```

### Classes

Use `PascalCase` for classes:

```python
# Good
class UserService:
    ...

class TradingSignal:
    ...

# Bad
class user_service:
    ...
```

### Constants

Use `SCREAMING_SNAKE_CASE` for constants:

```python
# Good
MAX_RETRIES = 3
DEFAULT_TIMEOUT = 30
API_VERSION = "v1"

# Bad
maxRetries = 3
default_timeout = 30
```

### Private Members

Prefix with single underscore for internal use:

```python
class Cache:
    def __init__(self):
        self._data = {}  # Internal
        self._lock = threading.Lock()  # Internal

    def get(self, key):  # Public
        ...
```

### Module Names

Use short, lowercase names:

```
core/
  providers.py
  trading.py
  cache.py
```

---

## Documentation

### Docstrings

Use Google-style docstrings:

```python
def execute_trade(
    symbol: str,
    amount: float,
    side: str,
    price: Optional[float] = None
) -> TradeResult:
    """
    Execute a trade on the configured exchange.

    Args:
        symbol: Trading pair symbol (e.g., "SOL/USDC")
        amount: Amount to trade
        side: Trade side ("buy" or "sell")
        price: Optional limit price (market order if None)

    Returns:
        TradeResult containing execution details

    Raises:
        InsufficientFundsError: If balance is too low
        InvalidSymbolError: If symbol is not supported

    Example:
        >>> result = execute_trade("SOL/USDC", 10.0, "buy")
        >>> print(result.executed_price)
        150.25
    """
    ...
```

### Module Docstrings

Every module should have a docstring:

```python
"""
JARVIS Trading Module

Provides trading functionality including order execution,
position management, and risk controls.

This module integrates with multiple DEX protocols
and implements safety checks for all operations.
"""

from typing import ...
```

### Class Docstrings

```python
class TradingPipeline:
    """
    Orchestrates the complete trading workflow.

    The pipeline handles signal generation, validation,
    risk assessment, and order execution in sequence.

    Attributes:
        max_position_size: Maximum position size in USD
        risk_manager: Risk management instance
        executor: Order execution instance

    Example:
        >>> pipeline = TradingPipeline(max_position_size=1000)
        >>> result = await pipeline.process_signal(signal)
    """
```

---

## Type Hints

### Always Use Type Hints

```python
# Good
def process_message(
    message: str,
    user_id: str,
    context: Optional[Dict[str, Any]] = None
) -> str:
    ...

# Bad
def process_message(message, user_id, context=None):
    ...
```

### Common Type Patterns

```python
from typing import (
    Dict, List, Optional, Union, Callable,
    TypeVar, Generic, Any, Awaitable
)

# Optional values
def get_user(user_id: str) -> Optional[User]:
    ...

# Union types
def parse_input(value: Union[str, int]) -> str:
    ...

# Callable types
Handler = Callable[[str], Awaitable[str]]

def register_handler(handler: Handler) -> None:
    ...

# Generic types
T = TypeVar('T')

class Cache(Generic[T]):
    def get(self, key: str) -> Optional[T]:
        ...
```

### Return Type Hints

Always specify return types:

```python
# Good
async def fetch_price(symbol: str) -> float:
    ...

def validate_input(data: dict) -> bool:
    ...

# For no return value
def log_event(event: str) -> None:
    ...
```

---

## Error Handling

### Custom Exceptions

Define custom exceptions for domain errors:

```python
class JarvisError(Exception):
    """Base exception for JARVIS."""
    pass

class TradingError(JarvisError):
    """Trading-related errors."""
    pass

class InsufficientFundsError(TradingError):
    """Raised when balance is insufficient."""
    pass
```

### Exception Handling

Be specific with exception handling:

```python
# Good
try:
    result = await execute_trade(order)
except InsufficientFundsError as e:
    logger.warning(f"Insufficient funds: {e}")
    return TradeFailed(reason="insufficient_funds")
except ConnectionError as e:
    logger.error(f"Connection failed: {e}")
    raise TradingError("Exchange connection failed") from e

# Bad
try:
    result = await execute_trade(order)
except Exception as e:
    logger.error(f"Error: {e}")
    return None
```

### Logging Errors

```python
import logging

logger = logging.getLogger(__name__)

# Use appropriate log levels
logger.debug("Processing order...")
logger.info(f"Order executed: {order_id}")
logger.warning(f"Retry attempt {attempt}/{max_attempts}")
logger.error(f"Failed to execute: {error}", exc_info=True)
logger.critical("System shutdown required")
```

---

## Testing

### Test File Naming

```
tests/
  test_trading.py          # Unit tests
  test_api_endpoints.py    # API tests
  integration/
    test_database.py       # Integration tests
```

### Test Function Naming

Use descriptive names:

```python
# Good
def test_execute_trade_with_valid_input_returns_success():
    ...

def test_execute_trade_with_insufficient_funds_raises_error():
    ...

# Bad
def test_trade():
    ...

def test_1():
    ...
```

### Test Structure

Follow Arrange-Act-Assert pattern:

```python
def test_user_creation():
    # Arrange
    user_data = {"name": "Alice", "email": "alice@example.com"}

    # Act
    user = create_user(user_data)

    # Assert
    assert user.name == "Alice"
    assert user.email == "alice@example.com"
```

### Fixtures

Use fixtures for common setup:

```python
@pytest.fixture
def mock_provider():
    """Create a mock LLM provider."""
    provider = AsyncMock()
    provider.generate.return_value = {"text": "response"}
    return provider

def test_chat_response(mock_provider):
    response = process_chat("Hello", provider=mock_provider)
    assert response is not None
```

---

## Git Practices

### Commit Messages

Use conventional commits format:

```
<type>(<scope>): <description>

[optional body]

[optional footer]
```

Types:
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation
- `style`: Formatting
- `refactor`: Code restructuring
- `test`: Adding tests
- `chore`: Maintenance

Examples:

```
feat(trading): add limit order support

- Implement limit order execution
- Add price validation
- Update trading tests

Closes #123
```

```
fix(api): handle rate limit errors correctly

The API was not respecting the retry-after header,
causing excessive retries.
```

### Branch Naming

```
feature/add-trading-signals
fix/rate-limit-handling
docs/update-api-docs
refactor/simplify-cache
```

### Pull Requests

- Keep PRs focused and small (<400 lines when possible)
- Include tests for new functionality
- Update documentation as needed
- Request review from at least one team member

---

## Configuration

### pyproject.toml Settings

```toml
[tool.black]
line-length = 88

[tool.ruff]
line-length = 88
select = ["E", "F", "I", "W"]

[tool.mypy]
python_version = "3.10"
warn_return_any = true
```

### Pre-commit Hooks

See `.pre-commit-config.yaml` for configured hooks.

---

## Quick Reference

| Item | Convention |
|------|------------|
| Variables | `snake_case` |
| Functions | `snake_case` |
| Classes | `PascalCase` |
| Constants | `SCREAMING_SNAKE_CASE` |
| Modules | `lowercase` |
| Private | `_underscore` |
| Line length | 88 characters |
| Indentation | 4 spaces |
| Quotes | Double quotes |
| Docstrings | Google style |
