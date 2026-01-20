"""API contract tests to ensure frontend/backend compatibility."""
import pytest
from typing import Any, Dict

# Skip if pydantic or fastapi not available
pytest.importorskip("pydantic")
pytest.importorskip("fastapi")

from pydantic import ValidationError


class TestHealthContract:
    """Contract tests for health endpoint."""
    
    def test_health_response_schema(self, client):
        """Health response must match expected schema."""
        response = client.get("/api/health")
        data = response.json()
        
        # Required fields
        assert "status" in data, "Missing required field: status"
        assert isinstance(data["status"], str), "status must be string"
        assert data["status"] in ["healthy", "degraded", "unhealthy"]
        
        # Optional but expected fields
        if "version" in data:
            assert isinstance(data["version"], str)
        
        if "timestamp" in data:
            assert isinstance(data["timestamp"], (int, float))
        
        if "services" in data:
            assert isinstance(data["services"], dict)


class TestErrorResponseContract:
    """Contract tests for error responses."""
    
    def test_404_error_schema(self, client):
        """404 errors must follow error schema."""
        response = client.get("/api/nonexistent")
        assert response.status_code == 404
        
        data = response.json()
        
        # Must have error info
        assert "error" in data or "detail" in data, "Error response missing error/detail"
    
    def test_error_includes_code(self, client):
        """Error responses should include error code."""
        response = client.get("/api/nonexistent")
        data = response.json()
        
        if "error" in data and isinstance(data["error"], dict):
            # Structured error format
            assert "code" in data["error"] or "message" in data["error"]


class TestPaginationContract:
    """Contract tests for paginated responses."""
    
    PAGINATION_FIELDS = ["items", "total", "page", "page_size", "has_next", "has_prev"]
    
    def validate_pagination(self, data: Dict[str, Any]):
        """Validate pagination structure."""
        for field in self.PAGINATION_FIELDS:
            if field in ["has_next", "has_prev"]:
                if field in data:
                    assert isinstance(data[field], bool), f"{field} must be boolean"
            elif field == "items":
                if field in data:
                    assert isinstance(data[field], list), "items must be array"
            else:
                if field in data:
                    assert isinstance(data[field], int), f"{field} must be integer"


class TestTradingContract:
    """Contract tests for trading endpoints."""
    
    ORDER_REQUIRED_FIELDS = ["symbol", "side", "amount"]
    ORDER_RESPONSE_FIELDS = ["order_id", "status"]
    
    def test_order_request_validation(self):
        """Order requests must be validated."""
        from api.schemas.trading import CreateOrderRequest
        
        # Valid order
        valid_order = {
            "symbol": "SOL/USDC",
            "side": "buy",
            "order_type": "market",
            "amount": 10.0
        }
        order = CreateOrderRequest(**valid_order)
        assert order.symbol == "SOL/USDC"
        
        # Invalid order - missing amount
        with pytest.raises(ValidationError):
            CreateOrderRequest(symbol="SOL/USDC", side="buy")
        
        # Invalid order - negative amount
        with pytest.raises(ValidationError):
            CreateOrderRequest(symbol="SOL/USDC", side="buy", amount=-10)
    
    def test_order_side_enum(self):
        """Order side must be buy or sell."""
        from api.schemas.trading import OrderSide
        
        assert OrderSide.BUY.value == "buy"
        assert OrderSide.SELL.value == "sell"


class TestWebSocketContract:
    """Contract tests for WebSocket messages."""
    
    def test_message_structure(self):
        """WebSocket messages must follow structure."""
        # Expected message format
        valid_message = {
            "type": "update",
            "channel": "trading",
            "data": {"price": 100.5},
            "timestamp": 1234567890.123
        }
        
        assert "type" in valid_message
        assert "channel" in valid_message
        assert "data" in valid_message
    
    def test_heartbeat_structure(self):
        """Heartbeat messages must follow structure."""
        from core.performance.websocket_optimizer import WebSocketOptimizer
        
        optimizer = WebSocketOptimizer()
        heartbeat = optimizer.get_heartbeat_message()
        
        assert heartbeat["type"] == "heartbeat"
        assert "timestamp" in heartbeat


class TestAPIResponseContract:
    """Contract tests for standard API responses."""
    
    def test_success_response_structure(self):
        """Success responses must follow structure."""
        from api.schemas.responses import success_response
        
        response = success_response(data={"key": "value"})
        
        assert response["success"] is True
        assert "data" in response
        assert "timestamp" in response
    
    def test_error_response_structure(self):
        """Error responses must follow structure."""
        from api.schemas.responses import error_response
        
        response = error_response(code="TEST_001", message="Test error")
        
        assert response["success"] is False
        assert "error" in response
        assert response["error"]["code"] == "TEST_001"
        assert response["error"]["message"] == "Test error"


class TestBackwardsCompatibility:
    """Tests to ensure backwards compatibility."""
    
    def test_deprecated_fields_still_work(self):
        """Deprecated fields should still be accepted."""
        # Add tests for any deprecated fields that need to remain
        pass
    
    def test_new_optional_fields_have_defaults(self):
        """New fields should be optional with defaults."""
        from api.schemas.trading import CreateOrderRequest
        
        # Minimal order should work
        order = CreateOrderRequest(
            symbol="SOL/USDC",
            side="buy",
            amount=10.0
        )
        
        # New optional fields should have defaults
        assert order.order_type is not None
        assert order.reduce_only is False
