# JARVIS Test Suite

Comprehensive testing documentation for the JARVIS project.

---

## Table of Contents

1. [Quick Start](#quick-start)
2. [Test Structure](#test-structure)
3. [Running Tests](#running-tests)
4. [Writing Tests](#writing-tests)
5. [Fixtures & Factories](#fixtures--factories)
6. [Mocking](#mocking)
7. [Async Testing](#async-testing)
8. [Integration Tests](#integration-tests)
9. [Load Testing](#load-testing)
10. [Coverage](#coverage)

---

## Quick Start

```bash
# Run all tests
pytest

# Run with verbose output
pytest -v

# Run specific test file
pytest tests/test_trading.py

# Run specific test function
pytest tests/test_trading.py::test_execute_trade

# Run with coverage
pytest --cov=core --cov-report=html

# Run in parallel (faster)
pytest -n auto
```

---

## Test Structure

```
tests/
├── conftest.py              # Shared fixtures
├── README.md                # This file
├── factories/               # Test data factories
│   ├── __init__.py
│   ├── base.py              # Base factory classes
│   ├── user_factory.py      # User/auth factories
│   ├── trade_factory.py     # Trading factories
│   ├── message_factory.py   # Message factories
│   ├── bot_factory.py       # Bot update factories
│   └── api_factory.py       # API request factories
├── utils/                   # Test utilities
│   ├── __init__.py
│   ├── async_utils.py       # Async testing helpers
│   ├── mock_helpers.py      # Mock implementations
│   └── assertions.py        # Custom assertions
├── integration/             # Integration tests
│   ├── __init__.py
│   ├── test_api_integration.py
│   ├── test_llm_integration.py
│   └── test_monitoring_integration.py
├── load/                    # Load/performance tests
│   └── locustfile.py
├── contract/                # Contract tests
│   └── test_api_contracts.py
├── test_api_endpoints.py    # API endpoint tests
├── test_bot_commands.py     # Bot command tests
├── test_trading.py          # Trading logic tests
├── test_security.py         # Security tests
└── test_resilience.py       # Resilience tests
```

---

## Running Tests

### Basic Commands

| Command | Description |
|---------|-------------|
| `pytest` | Run all tests |
| `pytest -v` | Verbose output |
| `pytest -x` | Stop on first failure |
| `pytest -s` | Show print statements |
| `pytest --pdb` | Debug on failure |

### Filtering Tests

```bash
# By marker
pytest -m "not slow"
pytest -m "integration"
pytest -m "security"

# By keyword
pytest -k "trade"
pytest -k "not database"

# By file pattern
pytest tests/test_*.py
pytest tests/**/test_*.py
```

### Parallel Execution

```bash
# Auto-detect CPU cores
pytest -n auto

# Specific number of workers
pytest -n 4

# Distribute by file
pytest -n auto --dist loadfile
```

### Test Markers

| Marker | Description |
|--------|-------------|
| `@pytest.mark.slow` | Long-running tests |
| `@pytest.mark.integration` | Requires external services |
| `@pytest.mark.security` | Security-related tests |
| `@pytest.mark.asyncio` | Async tests |
| `@pytest.mark.skip` | Skip this test |
| `@pytest.mark.xfail` | Expected to fail |

---

## Writing Tests

### Basic Test Structure

```python
import pytest
from core.trading import execute_trade

class TestExecuteTrade:
    """Tests for the execute_trade function."""

    def test_successful_trade(self):
        """Trade executes successfully with valid params."""
        # Arrange
        params = {"symbol": "SOL", "amount": 100}

        # Act
        result = execute_trade(params)

        # Assert
        assert result.success is True
        assert result.symbol == "SOL"

    def test_invalid_amount_raises_error(self):
        """Negative amounts raise ValueError."""
        params = {"symbol": "SOL", "amount": -100}

        with pytest.raises(ValueError, match="Amount must be positive"):
            execute_trade(params)
```

### Async Test Structure

```python
import pytest
from core.trading import async_execute_trade

class TestAsyncTrade:
    """Tests for async trading functions."""

    @pytest.mark.asyncio
    async def test_async_trade(self):
        """Async trade executes correctly."""
        result = await async_execute_trade("SOL", 100)
        assert result.success is True

    @pytest.mark.asyncio
    async def test_concurrent_trades(self):
        """Multiple trades can execute concurrently."""
        import asyncio

        results = await asyncio.gather(
            async_execute_trade("SOL", 100),
            async_execute_trade("RAY", 50),
        )

        assert all(r.success for r in results)
```

### Parameterized Tests

```python
import pytest

@pytest.mark.parametrize("symbol,expected", [
    ("SOL", True),
    ("RAY", True),
    ("INVALID", False),
])
def test_validate_symbol(symbol, expected):
    """Validate different trading symbols."""
    result = validate_symbol(symbol)
    assert result == expected

@pytest.mark.parametrize("amount", [0, -1, -100])
def test_invalid_amounts(amount):
    """Invalid amounts are rejected."""
    with pytest.raises(ValueError):
        validate_amount(amount)
```

---

## Fixtures & Factories

### Using Fixtures

```python
# conftest.py
import pytest

@pytest.fixture
def sample_user():
    """Create a sample user for testing."""
    return {
        "id": "user_123",
        "name": "Test User",
        "role": "trader",
    }

@pytest.fixture
def authenticated_client(client, sample_user):
    """Client with authentication."""
    client.set_auth(sample_user)
    return client

# test_api.py
def test_protected_endpoint(authenticated_client):
    """Protected endpoint requires auth."""
    response = authenticated_client.get("/api/v1/protected")
    assert response.status_code == 200
```

### Using Factories

```python
from tests.factories import UserFactory, TradeFactory

def test_user_creation():
    """Create user with factory."""
    user = UserFactory.build()
    assert user.id is not None
    assert "@" in user.email

def test_custom_user():
    """Create user with custom attributes."""
    user = UserFactory.build(
        name="Custom Name",
        role="admin"
    )
    assert user.name == "Custom Name"
    assert user.role == "admin"

def test_multiple_trades():
    """Create multiple trades."""
    trades = TradeFactory.build_batch(5)
    assert len(trades) == 5
    assert all(t.id is not None for t in trades)
```

### Available Factories

| Factory | Creates |
|---------|---------|
| `UserFactory` | User objects |
| `AdminUserFactory` | Admin users |
| `APIKeyFactory` | API keys |
| `OrderFactory` | Trade orders |
| `TradeFactory` | Executed trades |
| `TradingSignalFactory` | Trading signals |
| `TelegramUpdateFactory` | Telegram updates |
| `TelegramMessageFactory` | Telegram messages |
| `TwitterMentionFactory` | Twitter mentions |

---

## Mocking

### Using Mock Helpers

```python
from tests.utils.mock_helpers import (
    MockDatabase,
    MockCache,
    MockHTTPClient,
    MockTelegramBot,
)

@pytest.fixture
def mock_db():
    """Mock database for testing."""
    db = MockDatabase()
    db.add_response("SELECT * FROM users", [{"id": 1, "name": "Test"}])
    return db

def test_with_mock_db(mock_db):
    """Test with mocked database."""
    result = get_users(db=mock_db)
    assert len(result) == 1
```

### Patching External Services

```python
from unittest.mock import patch, AsyncMock

@pytest.mark.asyncio
async def test_external_api():
    """Mock external API calls."""
    with patch("core.external.api_client.fetch") as mock_fetch:
        mock_fetch.return_value = {"status": "ok"}

        result = await call_external_api()

        assert result["status"] == "ok"
        mock_fetch.assert_called_once()

@pytest.mark.asyncio
async def test_async_external():
    """Mock async external calls."""
    with patch("core.external.client.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = {"data": "test"}

        result = await fetch_data()

        assert result == {"data": "test"}
```

---

## Async Testing

### Async Utilities

```python
from tests.utils.async_utils import (
    async_timeout,
    wait_for_condition,
    AsyncContextManager,
)

@pytest.mark.asyncio
@async_timeout(5.0)
async def test_with_timeout():
    """Test automatically times out after 5 seconds."""
    result = await long_running_operation()
    assert result is not None

@pytest.mark.asyncio
async def test_wait_for_condition():
    """Wait for async condition."""
    state = {"ready": False}

    async def become_ready():
        await asyncio.sleep(0.1)
        state["ready"] = True

    asyncio.create_task(become_ready())

    await wait_for_condition(lambda: state["ready"], timeout=1.0)
    assert state["ready"] is True
```

### Testing Event Loops

```python
import pytest
import asyncio

@pytest.fixture
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()

@pytest.mark.asyncio
async def test_concurrent_operations():
    """Test multiple concurrent operations."""
    results = await asyncio.gather(
        operation_1(),
        operation_2(),
        operation_3(),
    )
    assert len(results) == 3
```

---

## Integration Tests

### Running Integration Tests

```bash
# Run all integration tests
pytest tests/integration/ -v

# With external services
INTEGRATION_TESTS=1 pytest tests/integration/

# Skip slow integration tests
pytest tests/integration/ -m "not slow"
```

### Writing Integration Tests

```python
# tests/integration/test_api_integration.py
import pytest

@pytest.mark.integration
class TestAPIIntegration:
    """Integration tests for API endpoints."""

    @pytest.fixture(autouse=True)
    def setup(self, test_client, test_database):
        """Set up integration test environment."""
        self.client = test_client
        self.db = test_database

    def test_create_and_retrieve_user(self):
        """Full user lifecycle test."""
        # Create
        response = self.client.post("/api/v1/users", json={
            "name": "Test User",
            "email": "test@example.com"
        })
        assert response.status_code == 201
        user_id = response.json()["id"]

        # Retrieve
        response = self.client.get(f"/api/v1/users/{user_id}")
        assert response.status_code == 200
        assert response.json()["name"] == "Test User"

        # Verify in database
        db_user = self.db.get_user(user_id)
        assert db_user is not None
```

### External Service Mocks

```python
import pytest
from tests.utils.mock_helpers import MockHTTPClient

@pytest.fixture
def mock_external_services(monkeypatch):
    """Mock all external services for integration tests."""
    mock_http = MockHTTPClient()
    mock_http.add_response(
        "GET", "https://api.external.com/data",
        json={"result": "mocked"}
    )

    monkeypatch.setattr("httpx.AsyncClient", lambda: mock_http)
    return mock_http
```

---

## Load Testing

### Running Load Tests

```bash
# Start Locust web UI
cd tests/load
locust -f locustfile.py

# Headless mode
locust -f locustfile.py --headless -u 100 -r 10 --run-time 60s

# With specific host
locust -f locustfile.py --host http://localhost:8000
```

### Load Test Structure

```python
# tests/load/locustfile.py
from locust import HttpUser, task, between

class JarvisUser(HttpUser):
    """Simulated JARVIS API user."""

    wait_time = between(1, 3)

    @task(10)
    def get_health(self):
        """Frequent health checks."""
        self.client.get("/health")

    @task(5)
    def get_prices(self):
        """Get token prices."""
        self.client.get("/api/v1/prices/SOL")

    @task(1)
    def execute_trade(self):
        """Occasional trade execution."""
        self.client.post("/api/v1/trade", json={
            "symbol": "SOL",
            "amount": 100,
            "side": "buy"
        })
```

---

## Coverage

### Generating Coverage Reports

```bash
# HTML report
pytest --cov=core --cov-report=html

# Terminal report
pytest --cov=core --cov-report=term-missing

# XML for CI
pytest --cov=core --cov-report=xml

# Multiple formats
pytest --cov=core --cov-report=html --cov-report=xml
```

### Coverage Configuration

```toml
# pyproject.toml
[tool.coverage.run]
source = ["core", "api", "bots"]
omit = ["*/tests/*", "*/__pycache__/*"]

[tool.coverage.report]
exclude_lines = [
    "pragma: no cover",
    "if TYPE_CHECKING:",
    "raise NotImplementedError",
]
fail_under = 60
```

### Viewing Coverage

```bash
# Open HTML report
open htmlcov/index.html  # macOS
xdg-open htmlcov/index.html  # Linux
start htmlcov/index.html  # Windows
```

---

## Test Best Practices

### Do

- Write tests before or with code
- Test one thing per test
- Use descriptive test names
- Clean up test resources
- Use fixtures for shared setup
- Mock external dependencies

### Don't

- Test implementation details
- Have tests depend on each other
- Use real API keys in tests
- Leave flaky tests unfixed
- Skip writing tests for "simple" code

### Naming Convention

```python
def test_function_name_describes_expected_behavior():
    """Docstring explains what is being tested."""
    pass

# Examples:
def test_execute_trade_returns_confirmation():
    pass

def test_invalid_symbol_raises_value_error():
    pass

def test_rate_limiter_blocks_after_threshold():
    pass
```

---

## Troubleshooting

### Common Issues

**Tests hang indefinitely**
```bash
# Add timeout
pytest --timeout=10
```

**Import errors**
```bash
# Install in editable mode
pip install -e .
```

**Async warnings**
```python
# Use proper async marker
@pytest.mark.asyncio
async def test_async():
    pass
```

**Database conflicts**
```bash
# Use isolated test database
export TEST_DATABASE_URL=sqlite:///./test.db
```

---

## CI/CD Integration

### GitHub Actions

```yaml
# .github/workflows/test.yml
- name: Run tests
  run: |
    pytest --cov=core --cov-report=xml -v

- name: Upload coverage
  uses: codecov/codecov-action@v3
```

### Pre-commit

```yaml
# .pre-commit-config.yaml
- repo: local
  hooks:
    - id: pytest
      name: pytest
      entry: pytest tests/ -x
      language: system
      pass_filenames: false
```
