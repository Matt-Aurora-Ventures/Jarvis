"""
JARVIS Test Configuration

Central pytest configuration and shared fixtures for all tests.
Includes coverage configuration and factory fixtures.
"""

import os
import sys
from unittest.mock import MagicMock

# Add project root to path FIRST
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ==============================================================================
# CRITICAL: Mock sklearn/scipy BEFORE they get imported by coverage
# This prevents scipy/numpy/coverage interaction issue on Windows
# ==============================================================================
if 'sklearn' not in sys.modules:
    # Create mock sklearn module
    sklearn_mock = MagicMock()
    sklearn_mock.ensemble = MagicMock()
    sklearn_mock.preprocessing = MagicMock()
    sklearn_mock.model_selection = MagicMock()
    sys.modules['sklearn'] = sklearn_mock
    sys.modules['sklearn.ensemble'] = sklearn_mock.ensemble
    sys.modules['sklearn.preprocessing'] = sklearn_mock.preprocessing
    sys.modules['sklearn.model_selection'] = sklearn_mock.model_selection

if 'scipy' not in sys.modules:
    scipy_mock = MagicMock()
    scipy_mock.stats = MagicMock()
    sys.modules['scipy'] = scipy_mock
    sys.modules['scipy.stats'] = scipy_mock.stats

# Now import the rest
import pytest
import asyncio
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, patch
from datetime import datetime
from typing import Generator

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
    from httpx import AsyncClient, ASGITransport
    from api.fastapi_app import create_app
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
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


# ============================================================================
# Factory Fixtures
# ============================================================================

@pytest.fixture
def user_factory():
    """User factory fixture."""
    try:
        from tests.factories import UserFactory
        return UserFactory
    except ImportError:
        pytest.skip("UserFactory not available")


@pytest.fixture
def trade_factory():
    """Trade factory fixture."""
    try:
        from tests.factories import TradeFactory
        return TradeFactory
    except ImportError:
        pytest.skip("TradeFactory not available")


@pytest.fixture
def message_factory():
    """Message factory fixture."""
    try:
        from tests.factories import MessageFactory
        return MessageFactory
    except ImportError:
        pytest.skip("MessageFactory not available")


@pytest.fixture
def telegram_update_factory():
    """Telegram update factory fixture."""
    try:
        from tests.factories import TelegramUpdateFactory
        return TelegramUpdateFactory
    except ImportError:
        pytest.skip("TelegramUpdateFactory not available")


# ============================================================================
# Mock Helper Fixtures
# ============================================================================

@pytest.fixture
def mock_http_client():
    """Create a mock HTTP client."""
    try:
        from tests.utils.mock_helpers import MockHTTPClient
        return MockHTTPClient()
    except ImportError:
        pytest.skip("MockHTTPClient not available")


@pytest.fixture
def mock_cache():
    """Create a mock cache."""
    try:
        from tests.utils.mock_helpers import MockCache
        return MockCache()
    except ImportError:
        pytest.skip("MockCache not available")


@pytest.fixture
def mock_llm_provider():
    """Create a mock LLM provider."""
    try:
        from tests.utils.mock_helpers import MockProvider
        return MockProvider()
    except ImportError:
        pytest.skip("MockProvider not available")


# ============================================================================
# Async Utility Fixtures
# ============================================================================

@pytest.fixture
def async_event_recorder():
    """Create an async event recorder."""
    try:
        from tests.utils.async_utils import AsyncEventRecorder
        return AsyncEventRecorder()
    except ImportError:
        pytest.skip("AsyncEventRecorder not available")


# ============================================================================
# Sequence Reset
# ============================================================================

@pytest.fixture(autouse=True)
def reset_sequences():
    """Reset sequence generators between tests."""
    yield
    try:
        from tests.factories.base import SequenceGenerator
        SequenceGenerator.reset()
    except ImportError:
        pass


# ============================================================================
# Pytest Hooks and Markers
# ============================================================================

def pytest_configure(config):
    """Configure custom markers."""
    config.addinivalue_line(
        "markers", "slow: marks tests as slow running"
    )
    config.addinivalue_line(
        "markers", "integration: marks integration tests"
    )
    config.addinivalue_line(
        "markers", "security: marks security tests"
    )
    config.addinivalue_line(
        "markers", "unit: marks unit tests"
    )


def pytest_collection_modifyitems(config, items):
    """Modify test collection."""
    for item in items:
        # Add slow marker to integration tests
        if "integration" in item.nodeid:
            item.add_marker(pytest.mark.integration)
            item.add_marker(pytest.mark.slow)

        if "security" in item.nodeid:
            item.add_marker(pytest.mark.security)
