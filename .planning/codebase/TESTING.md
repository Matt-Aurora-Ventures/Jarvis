# Jarvis Testing Guide

**Generated:** 2026-01-24  
**Framework:** pytest  
**Purpose:** Testing patterns, fixtures, and execution guide

---

## Testing Framework

**Primary:** pytest  
**Location:** `tests/` directory  
**Configuration:** `tests/conftest.py`

---

## Test Organization

### File Naming

- Test files: `test_*.py`
- Location mirrors source structure

### Test Structure

**Class-based organization:**

```python
class TestUIPermissions:
    """Test _ui_allowed and permission checks."""
    
    def test_ui_allowed_default_true(self):
        """UI actions should be allowed by default."""
        assert result is True
```

---

## Test Markers

Defined in `conftest.py`:

- `@pytest.mark.unit` - Unit tests
- `@pytest.mark.integration` - Integration tests  
- `@pytest.mark.slow` - Slow-running tests
- `@pytest.mark.security` - Security tests

---

## Fixtures

### Core Fixtures (`tests/conftest.py`)

**Environment:**
```python
@pytest.fixture(autouse=True)
def setup_test_env(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "test")
```

**Async:**
```python
@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()
```

**Mocks:**
```python
@pytest.fixture
def mock_db():
    db = MagicMock()
    return db

@pytest.fixture
def mock_redis():
    redis = AsyncMock()
    return redis
```

**Sample Data:**
```python
@pytest.fixture
def sample_trade():
    return {"id": "trade_001", "symbol": "SOL/USDC"}
```

---

## Mocking Patterns

### unittest.mock

```python
from unittest.mock import MagicMock, AsyncMock, patch

def test_example(self):
    with patch("core.config.load_config") as mock_config:
        mock_config.return_value = {"test": True}
        result = function_under_test()
        assert result
```

---

## Running Tests

```bash
# All tests
pytest

# Specific file
pytest tests/test_actions.py

# With coverage
pytest --cov=core --cov=bots
```

---

## Key Patterns

1. Use `conftest.py` for shared fixtures
2. Mock external services (DB, APIs)
3. Class-based organization
4. AAA pattern (Arrange-Act-Assert)
5. Descriptive test names
