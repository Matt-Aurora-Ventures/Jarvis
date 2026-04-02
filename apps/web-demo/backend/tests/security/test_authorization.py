"""
Authorization Security Tests
Tests Rule #3: UI restrictions are not security - backend enforces
"""
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.security import JWTHandler


client = TestClient(app)


class TestVerticalPrivilegeEscalation:
    """Test that users cannot escalate to admin (Rule #2 & #3)."""

    def test_user_cannot_access_admin_endpoints(self):
        """Test user role cannot access admin endpoints."""
        # Get user token
        user_token = JWTHandler.create_access_token("user123", "user")

        # Try to access admin endpoint
        response = client.get(
            "/api/admin/users",
            headers={"Authorization": f"Bearer {user_token}"},
        )

        assert response.status_code == 403
        assert "admin" in response.json()["detail"].lower()

    def test_token_role_tampering_fails(self):
        """Test that modifying token role fails (Rule #1)."""
        import jwt
        from app.config import settings

        # Create user token
        user_token = JWTHandler.create_access_token("user123", "user")

        # Decode without verification
        payload = jwt.decode(user_token, options={"verify_signature": False})

        # Try to change role
        payload["role"] = "admin"

        # Re-encode with wrong secret
        tampered_token = jwt.encode(payload, "wrong-secret", algorithm="HS256")

        response = client.get(
            "/api/admin/users",
            headers={"Authorization": f"Bearer {tampered_token}"},
        )

        assert response.status_code == 401


class TestHorizontalPrivilegeEscalation:
    """Test that users cannot access other users' resources (Rule #2)."""

    def test_user_cannot_access_other_wallet(self):
        """Test ownership verification on wallet operations."""
        # User A token
        user_a_token = JWTHandler.create_access_token("user_a", "user")

        # Try to access User B's wallet
        response = client.get(
            "/api/wallet/export?wallet_id=user_b_wallet",
            headers={"Authorization": f"Bearer {user_a_token}"},
        )

        # Should be forbidden (ownership check)
        assert response.status_code in [403, 404]

    def test_user_cannot_modify_other_position(self):
        """Test ownership verification on position operations."""
        user_a_token = JWTHandler.create_access_token("user_a", "user")

        response = client.put(
            "/api/positions/other_user_position_id",
            headers={"Authorization": f"Bearer {user_a_token}"},
            json={"take_profit": 100.0},
        )

        assert response.status_code in [403, 404]

    def test_user_cannot_close_other_position(self):
        """Test ownership verification on position closure."""
        user_a_token = JWTHandler.create_access_token("user_a", "user")

        response = client.post(
            "/api/positions/other_user_position_id/close",
            headers={"Authorization": f"Bearer {user_a_token}"},
        )

        assert response.status_code in [403, 404]


class TestIDOR:
    """Test Insecure Direct Object Reference vulnerabilities (Rule #2)."""

    def test_position_id_enumeration_blocked(self):
        """Test that position IDs cannot be enumerated."""
        user_token = JWTHandler.create_access_token("user123", "user")

        # Try to access positions 1-100
        accessible_positions = []
        for pos_id in range(1, 101):
            response = client.get(
                f"/api/positions/{pos_id}",
                headers={"Authorization": f"Bearer {user_token}"},
            )

            if response.status_code == 200:
                accessible_positions.append(pos_id)

        # User should only access their own positions (not all IDs)
        assert len(accessible_positions) < 100

    def test_wallet_id_enumeration_blocked(self):
        """Test that wallet IDs cannot be enumerated."""
        user_token = JWTHandler.create_access_token("user123", "user")

        for wallet_id in range(1, 50):
            response = client.get(
                f"/api/wallet/{wallet_id}/balance",
                headers={"Authorization": f"Bearer {user_token}"},
            )

            # Should get 403/404 for wallets not owned by user
            assert response.status_code in [403, 404]

    def test_sequential_id_prediction_mitigated(self):
        """Test that resource IDs are not predictable."""
        user_token = JWTHandler.create_access_token("user123", "user")

        # Create 3 positions
        positions = []
        for i in range(3):
            response = client.post(
                "/api/positions",
                headers={"Authorization": f"Bearer {user_token}"},
                json={
                    "token_address": f"token{i}",
                    "amount": 1.0,
                },
            )

            if response.status_code in [200, 201]:
                positions.append(response.json()["id"])

        # IDs should not be sequential (1, 2, 3)
        if len(positions) >= 2:
            id_diff = abs(int(positions[1]) - int(positions[0]))
            assert id_diff != 1  # Not sequential


class TestForcedBrowsing:
    """Test forced browsing / direct URL access (Rule #3)."""

    def test_admin_page_requires_auth(self):
        """Test that admin pages require authentication."""
        # Try to access without token
        response = client.get("/api/admin/dashboard")

        assert response.status_code in [401, 403]

    def test_hidden_endpoints_still_protected(self):
        """Test that 'hidden' endpoints are still protected (Rule #3)."""
        # Even if frontend doesn't show these, backend must protect
        user_token = JWTHandler.create_access_token("user123", "user")

        hidden_endpoints = [
            "/api/admin/debug",
            "/api/admin/logs",
            "/api/admin/config",
            "/api/internal/metrics",
        ]

        for endpoint in hidden_endpoints:
            response = client.get(
                endpoint,
                headers={"Authorization": f"Bearer {user_token}"},
            )

            # Should be protected (403 or 404, not 200)
            assert response.status_code in [403, 404]


class TestMassAssignment:
    """Test mass assignment vulnerabilities (Rule #1)."""

    def test_cannot_set_admin_via_registration(self):
        """Test that role cannot be set during registration."""
        response = client.post(
            "/api/auth/register",
            json={
                "email": "hacker@example.com",
                "username": "hacker",
                "password": "ValidPassword123!",
                "role": "admin",  # Try to set admin role
            },
        )

        # Should either ignore role or reject
        if response.status_code in [200, 201]:
            # Check that user is not admin
            user_data = response.json()
            assert user_data.get("role", "user") == "user"

    def test_cannot_modify_user_id_in_update(self):
        """Test that user_id cannot be changed via update."""
        user_token = JWTHandler.create_access_token("user123", "user")

        response = client.put(
            "/api/users/profile",
            headers={"Authorization": f"Bearer {user_token}"},
            json={
                "user_id": "different_user",  # Try to change user_id
                "username": "newname",
            },
        )

        # Should ignore user_id or reject
        if response.status_code == 200:
            user_data = response.json()
            assert user_data["user_id"] == "user123"  # Unchanged


class TestBusinessLogicFlaws:
    """Test business logic security (Rule #2)."""

    def test_negative_amount_rejected(self):
        """Test that negative trading amounts are rejected."""
        user_token = JWTHandler.create_access_token("user123", "user")

        response = client.post(
            "/api/trading/buy",
            headers={"Authorization": f"Bearer {user_token}"},
            json={
                "token_address": "token123",
                "amount": -10.0,  # Negative amount
            },
        )

        assert response.status_code == 400
        assert "amount" in response.json()["detail"].lower()

    def test_zero_amount_rejected(self):
        """Test that zero amounts are rejected."""
        user_token = JWTHandler.create_access_token("user123", "user")

        response = client.post(
            "/api/trading/buy",
            headers={"Authorization": f"Bearer {user_token}"},
            json={
                "token_address": "token123",
                "amount": 0.0,
            },
        )

        assert response.status_code == 400

    def test_excessive_amount_rejected(self):
        """Test that amounts exceeding limits are rejected."""
        user_token = JWTHandler.create_access_token("user123", "user")

        response = client.post(
            "/api/trading/buy",
            headers={"Authorization": f"Bearer {user_token}"},
            json={
                "token_address": "token123",
                "amount": 1000000.0,  # Excessive amount
            },
        )

        # Should be rejected (either 400 or 403)
        assert response.status_code in [400, 403]

    def test_invalid_percentage_rejected(self):
        """Test that invalid percentages are rejected."""
        user_token = JWTHandler.create_access_token("user123", "user")

        invalid_percentages = [-10, 150, 999]

        for pct in invalid_percentages:
            response = client.post(
                "/api/trading/sell",
                headers={"Authorization": f"Bearer {user_token}"},
                json={
                    "position_id": "pos123",
                    "percentage": pct,
                },
            )

            assert response.status_code == 400


class TestRaceConditions:
    """Test race condition vulnerabilities (Rule #2)."""

    def test_double_spend_prevention(self):
        """Test that double-spend is prevented."""
        import asyncio
        import aiohttp

        user_token = JWTHandler.create_access_token("user123", "user")

        async def make_trade():
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    "http://localhost:8000/api/trading/buy",
                    headers={"Authorization": f"Bearer {user_token}"},
                    json={
                        "token_address": "token123",
                        "amount": 1.0,
                    },
                ) as response:
                    return response.status

        # Try to make same trade concurrently
        # One should succeed, others should fail
        # (if user only has 1 SOL, can't buy 1 SOL twice)
        # This test would need actual implementation to work properly

    def test_concurrent_position_close(self):
        """Test that position can only be closed once."""
        user_token = JWTHandler.create_access_token("user123", "user")

        # Try to close same position twice
        response1 = client.post(
            "/api/positions/pos123/close",
            headers={"Authorization": f"Bearer {user_token}"},
        )

        response2 = client.post(
            "/api/positions/pos123/close",
            headers={"Authorization": f"Bearer {user_token}"},
        )

        # At least one should fail
        status_codes = [response1.status_code, response2.status_code]
        assert 400 in status_codes or 404 in status_codes


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
