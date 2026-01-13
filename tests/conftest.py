"""Pytest configuration and shared fixtures."""
import pytest
import asyncio
import tempfile
import os
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock

# Configure async tests
@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


# Temporary directory for test data
@pytest.fixture
def temp_dir():
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


# Mock database connection
@pytest.fixture
def mock_db():
    db = MagicMock()
    db.execute.return_value.fetchall.return_value = []
    db.execute.return_value.fetchone.return_value = None
    return db


# Mock Redis cache
@pytest.fixture
def mock_redis():
    redis = AsyncMock()
    redis.get.return_value = None
    redis.set.return_value = True
    redis.delete.return_value = True
    return redis


# Mock AI provider
@pytest.fixture
def mock_provider():
    provider = AsyncMock()
    provider.call.return_value = {"response": "mocked response", "tokens": 100}
    provider.health_check.return_value = True
    return provider


# Test client for FastAPI
@pytest.fixture
def client():
    from fastapi.testclient import TestClient
    from api.fastapi_app import create_app
    app = create_app()
    return TestClient(app)


# Async test client
@pytest.fixture
async def async_client():
    from httpx import AsyncClient
    from api.fastapi_app import create_app
    app = create_app()
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac


# Sample trade data
@pytest.fixture
def sample_trade():
    return {
        "id": "trade_001",
        "symbol": "SOL/USDC",
        "side": "buy",
        "amount": 10.0,
        "price": 100.0,
        "status": "filled",
        "created_at": "2024-01-01T00:00:00Z"
    }


# Sample candle data
@pytest.fixture
def sample_candles():
    return [
        {"timestamp": i, "open": 100+i, "high": 102+i, "low": 98+i, "close": 101+i, "volume": 1000}
        for i in range(200)
    ]


# Sample user data
@pytest.fixture
def sample_user():
    return {
        "id": "user_001",
        "email": "test@example.com",
        "api_key": "test_api_key_12345"
    }


# Environment setup
@pytest.fixture(autouse=True)
def setup_test_env(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "test")
    monkeypatch.setenv("RATE_LIMIT_ENABLED", "false")
    monkeypatch.setenv("JWT_SECRET_KEY", "test-secret-key")


# Clean up test artifacts
@pytest.fixture(autouse=True)
def cleanup():
    yield
    # Cleanup any test files created
    test_files = Path("data").glob("test_*")
    for f in test_files:
        try:
            f.unlink()
        except Exception:
            pass
