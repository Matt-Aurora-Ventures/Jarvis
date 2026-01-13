# Testing & Quality Improvements (56-70)

## 56. Unit Test Coverage Enhancement

```python
# tests/unit/test_trading_pipeline.py
import pytest
from core.trading_pipeline import run_backtest, StrategyConfig, _sma_series, _rsi_series

class TestIndicators:
    def test_sma_series_basic(self):
        closes = [10, 20, 30, 40, 50]
        result = _sma_series(closes, 3)
        assert result[2] == 20.0  # (10+20+30)/3
        assert result[4] == 40.0  # (30+40+50)/3
    
    def test_sma_series_empty(self):
        assert _sma_series([], 5) == []
    
    def test_rsi_series_bounds(self):
        closes = list(range(1, 50))
        result = _rsi_series(closes, 14)
        for val in result[14:]:
            assert 0 <= val <= 100

class TestBacktest:
    @pytest.fixture
    def sample_candles(self):
        return [{"close": 100 + i, "timestamp": i} for i in range(100)]
    
    def test_backtest_insufficient_data(self, sample_candles):
        result = run_backtest(sample_candles[:5], "BTC", "1h", StrategyConfig())
        assert result.error == "Not enough data for backtest"
    
    def test_backtest_returns_metrics(self, sample_candles):
        result = run_backtest(sample_candles, "BTC", "1h", StrategyConfig())
        assert result.total_trades >= 0
        assert 0 <= result.win_rate <= 1
```

## 57. Integration Tests

```python
# tests/integration/test_api_integration.py
import pytest
from fastapi.testclient import TestClient
from api.fastapi_app import create_app

@pytest.fixture
def client():
    app = create_app()
    return TestClient(app)

class TestAPIIntegration:
    def test_health_endpoint(self, client):
        response = client.get("/api/health")
        assert response.status_code == 200
        assert "status" in response.json()
    
    def test_websocket_connection(self, client):
        with client.websocket_connect("/ws/trading") as ws:
            ws.send_json({"action": "subscribe", "symbol": "SOL"})
            data = ws.receive_json()
            assert data["status"] == "subscribed"
    
    def test_rate_limiting(self, client):
        for _ in range(100):
            client.get("/api/health")
        response = client.get("/api/health")
        assert response.status_code in [200, 429]
```

## 58. E2E Tests with Playwright

```python
# tests/e2e/test_trading_flow.py
import pytest
from playwright.sync_api import Page, expect

@pytest.fixture
def authenticated_page(page: Page):
    page.goto("http://localhost:3000")
    page.fill('[data-testid="api-key-input"]', "test-api-key")
    page.click('[data-testid="connect-btn"]')
    page.wait_for_selector('[data-testid="dashboard"]')
    return page

class TestTradingFlow:
    def test_place_order(self, authenticated_page: Page):
        page = authenticated_page
        page.click('[data-testid="trading-tab"]')
        page.fill('[data-testid="amount-input"]', "10")
        page.click('[data-testid="buy-btn"]')
        expect(page.locator('[data-testid="order-success"]')).to_be_visible()
    
    def test_view_positions(self, authenticated_page: Page):
        page = authenticated_page
        page.click('[data-testid="positions-tab"]')
        expect(page.locator('[data-testid="positions-list"]')).to_be_visible()
```

## 59. API Contract Tests

```python
# tests/contract/test_api_contracts.py
from pydantic import ValidationError
from api.schemas.trading import CreateOrderRequest, OrderResponse

class TestAPIContracts:
    def test_create_order_request_valid(self):
        request = CreateOrderRequest(
            symbol="SOL/USDC", side="buy", order_type="market", amount=10.0
        )
        assert request.symbol == "SOL/USDC"
    
    def test_create_order_request_invalid_amount(self):
        with pytest.raises(ValidationError):
            CreateOrderRequest(symbol="SOL", side="buy", order_type="market", amount=-1)
    
    def test_order_response_schema(self):
        data = {"order_id": "123", "symbol": "SOL", "side": "buy", "status": "pending",
                "amount": 10.0, "filled_amount": 0, "price": None, "created_at": "2024-01-01T00:00:00"}
        response = OrderResponse(**data)
        assert response.order_id == "123"
```

## 60. Load Testing

```python
# tests/load/locustfile.py
from locust import HttpUser, task, between

class TradingUser(HttpUser):
    wait_time = between(1, 3)
    
    def on_start(self):
        self.client.headers = {"X-API-Key": "test-key"}
    
    @task(10)
    def get_health(self):
        self.client.get("/api/health")
    
    @task(5)
    def get_positions(self):
        self.client.get("/api/positions")
    
    @task(2)
    def place_order(self):
        self.client.post("/api/orders", json={
            "symbol": "SOL/USDC", "side": "buy", "order_type": "market", "amount": 1.0
        })
    
    @task(1)
    def run_backtest(self):
        self.client.post("/api/backtest", json={
            "symbol": "BTC", "interval": "1h", "strategy": "sma_cross"
        })

# Run: locust -f tests/load/locustfile.py --host=http://localhost:8000
```

## 61. Mutation Testing

```toml
# pyproject.toml - mutmut configuration
[tool.mutmut]
paths_to_mutate = "core/"
tests_dir = "tests/"
runner = "pytest"

# Run: mutmut run
# View: mutmut results
```

## 62. Snapshot Tests

```python
# tests/snapshot/test_responses.py
import pytest

class TestResponseSnapshots:
    def test_health_response_snapshot(self, client, snapshot):
        response = client.get("/api/health/detailed")
        # Remove dynamic fields
        data = response.json()
        data.pop("timestamp", None)
        assert data == snapshot
    
    def test_error_response_snapshot(self, client, snapshot):
        response = client.get("/api/nonexistent")
        assert response.json() == snapshot
```

## 63. Mocking Framework

```python
# tests/conftest.py
import pytest
from unittest.mock import AsyncMock, MagicMock

@pytest.fixture
def mock_provider():
    provider = AsyncMock()
    provider.call.return_value = {"response": "mocked"}
    return provider

@pytest.fixture
def mock_database():
    db = MagicMock()
    db.execute.return_value.fetchall.return_value = []
    return db

@pytest.fixture
def mock_redis():
    redis = MagicMock()
    redis.get.return_value = None
    return redis
```

## 64. Test Fixtures

```python
# tests/fixtures/trading.py
import pytest
from datetime import datetime

@pytest.fixture
def sample_trade():
    return {
        "id": "trade_001",
        "symbol": "SOL/USDC",
        "side": "buy",
        "amount": 10.0,
        "price": 100.0,
        "status": "filled",
        "created_at": datetime.now()
    }

@pytest.fixture
def sample_candles():
    return [
        {"timestamp": i, "open": 100+i, "high": 102+i, "low": 98+i, "close": 101+i, "volume": 1000}
        for i in range(200)
    ]

@pytest.fixture
def sample_strategy():
    from core.trading_pipeline import StrategyConfig
    return StrategyConfig(kind="sma_cross", params={"fast": 5, "slow": 20})
```

## 65. CI Test Pipeline

```yaml
# .github/workflows/test.yml
name: Tests
on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - name: Install dependencies
        run: pip install -r requirements.txt -r requirements-dev.txt
      - name: Run linting
        run: ruff check .
      - name: Run type checking
        run: mypy core/
      - name: Run tests
        run: pytest --cov=core --cov-report=xml
      - name: Upload coverage
        uses: codecov/codecov-action@v3
```

## 66. Coverage Reports

```ini
# .coveragerc
[run]
source = core
omit = tests/*, */__pycache__/*, */migrations/*

[report]
exclude_lines =
    pragma: no cover
    def __repr__
    raise NotImplementedError
    if TYPE_CHECKING:
fail_under = 80
show_missing = true

[html]
directory = coverage_html
```

## 67. Property-Based Tests

```python
# tests/property/test_trading.py
from hypothesis import given, strategies as st

class TestTradingProperties:
    @given(st.floats(min_value=0.001, max_value=1000000))
    def test_position_size_always_positive(self, amount):
        from core.trading_pipeline import _position_size, StrategyConfig
        config = StrategyConfig(risk_per_trade=0.02, stop_loss_pct=0.03)
        size = _position_size(config)
        assert 0 <= size <= config.max_position_pct
    
    @given(st.lists(st.floats(min_value=1, max_value=1000), min_size=20))
    def test_sma_length_matches_input(self, closes):
        from core.trading_pipeline import _sma_series
        result = _sma_series(closes, 5)
        assert len(result) == len(closes)
```

## 68. Fuzzing

```python
# tests/fuzz/test_input_fuzzing.py
import atheris
import sys

def fuzz_sanitizer(data):
    from core.security.sanitizer import sanitize_string
    fdp = atheris.FuzzedDataProvider(data)
    input_str = fdp.ConsumeString(1000)
    result = sanitize_string(input_str)
    assert len(result) <= 10000
    assert '\x00' not in result

if __name__ == "__main__":
    atheris.Setup(sys.argv, fuzz_sanitizer)
    atheris.Fuzz()
```

## 69. Visual Regression Tests

```javascript
// tests/visual/trading.spec.js
const { test, expect } = require('@playwright/test');

test('dashboard visual regression', async ({ page }) => {
  await page.goto('http://localhost:3000');
  await expect(page).toHaveScreenshot('dashboard.png', { maxDiffPixels: 100 });
});

test('trading panel visual regression', async ({ page }) => {
  await page.goto('http://localhost:3000/trading');
  await expect(page.locator('.trading-panel')).toHaveScreenshot('trading-panel.png');
});
```

## 70. Performance Benchmarks

```python
# tests/benchmark/test_performance.py
import pytest

class TestPerformance:
    @pytest.mark.benchmark(group="backtest")
    def test_backtest_performance(self, benchmark, sample_candles):
        from core.trading_pipeline import run_backtest, StrategyConfig
        result = benchmark(run_backtest, sample_candles, "BTC", "1h", StrategyConfig())
        assert result.total_trades >= 0
    
    @pytest.mark.benchmark(group="indicators")
    def test_sma_performance(self, benchmark):
        from core.trading_pipeline import _sma_series
        closes = list(range(10000))
        result = benchmark(_sma_series, closes, 20)
        assert len(result) == 10000
```
