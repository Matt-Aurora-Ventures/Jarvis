"""
Transaction Verifier Tests

Tests for the transaction verification system that:
- Verifies token authenticity (rugpull detection)
- Validates liquidity (not fake)
- Analyzes contract code
- Performs ownership checks
"""
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from datetime import datetime, timedelta


class TestTransactionVerifier:
    """Tests for the transaction verifier."""

    @pytest.fixture
    def verifier(self):
        """Create a transaction verifier instance."""
        from core.security.transaction_verifier import TransactionVerifier
        return TransactionVerifier()

    def test_initialization(self):
        """Test verifier initializes correctly."""
        from core.security.transaction_verifier import TransactionVerifier
        verifier = TransactionVerifier()
        assert verifier is not None

    def test_verify_token_authenticity_valid(self, verifier):
        """Test verifying a legitimate token."""
        # Mock valid token metadata
        with patch.object(verifier, '_fetch_token_metadata') as mock_fetch:
            mock_fetch.return_value = {
                "name": "Wrapped SOL",
                "symbol": "SOL",
                "decimals": 9,
                "supply": 500000000000000000,  # Normal supply
                "mint_authority": None,  # No mint authority
                "freeze_authority": None,  # No freeze authority
            }

            result = verifier.verify_token_authenticity(
                token_address="So11111111111111111111111111111111111111112"
            )

            assert result["verified"] is True
            assert "risk_score" in result
            assert result["risk_score"] < 0.5  # Low risk for known token

    def test_verify_token_authenticity_suspicious(self, verifier):
        """Test detecting suspicious token characteristics."""
        # Mock suspicious token data
        with patch.object(verifier, '_fetch_token_metadata') as mock_fetch:
            mock_fetch.return_value = {
                "name": "SAFE MOON INU",  # Suspicious name pattern
                "symbol": "SAFEMOONINU",
                "decimals": 9,
                "supply": 1000000000000000,  # Massive supply
                "freeze_authority": "SomeAddress123",  # Has freeze authority
                "mint_authority": "SomeAddress456",  # Has mint authority
            }

            result = verifier.verify_token_authenticity("FakeToken111111111111111111111111111111111")

            assert result["risk_score"] > 0.5  # High risk
            assert len(result["warnings"]) > 0

    def test_detect_rugpull_indicators(self, verifier):
        """Test rugpull indicator detection."""
        with patch.object(verifier, '_fetch_token_data') as mock_fetch:
            mock_fetch.return_value = {
                "creator_holdings_pct": 0.90,  # Creator holds 90%
                "liquidity_locked": False,
                "contract_verified": False,
                "age_hours": 2,  # Very new
                "holder_count": 5,  # Few holders
                "top_10_holdings_pct": 0.99,  # Concentrated holdings
            }

            result = verifier.detect_rugpull_indicators("SuspiciousToken111111111111111111111111")

            assert result["is_potential_rugpull"] is True
            assert "creator_concentration" in result["indicators"]
            assert result["confidence"] > 0.7

    def test_verify_liquidity_valid(self, verifier):
        """Test verifying valid liquidity."""
        with patch.object(verifier, '_fetch_liquidity_data') as mock_fetch:
            mock_fetch.return_value = {
                "total_liquidity_usd": 500000,
                "liquidity_locked": True,
                "lock_duration_days": 365,
                "pool_age_days": 180,
                "liquidity_providers": 150,
            }

            result = verifier.verify_liquidity(
                "TokenAddress123",
                min_liquidity_usd=10000
            )

            assert result["liquidity_valid"] is True
            assert result["liquidity_score"] > 0.7

    def test_verify_liquidity_fake(self, verifier):
        """Test detecting fake/manipulated liquidity."""
        with patch.object(verifier, '_fetch_liquidity_data') as mock_fetch:
            mock_fetch.return_value = {
                "total_liquidity_usd": 1000000,  # High liquidity
                "liquidity_locked": False,
                "lock_duration_days": 0,
                "pool_age_days": 0.5,  # Very new
                "liquidity_providers": 1,  # Single LP
                "wash_trading_score": 0.9,  # High wash trading
            }

            result = verifier.verify_liquidity("SuspiciousToken123")

            assert result["liquidity_valid"] is False
            assert "fake_liquidity" in result["warnings"] or result["liquidity_score"] < 0.5

    def test_analyze_contract_code_safe(self, verifier):
        """Test analyzing a safe contract."""
        with patch.object(verifier, '_fetch_contract_source') as mock_fetch:
            mock_fetch.return_value = {
                "verified": True,
                "source_available": True,
                "has_proxy": False,
                "functions": ["transfer", "approve", "balanceOf"],
            }

            result = verifier.analyze_contract("SafeToken123")

            assert result["is_safe"] is True
            assert result["risk_level"] in ["low", "medium"]

    def test_analyze_contract_code_dangerous(self, verifier):
        """Test detecting dangerous contract patterns."""
        with patch.object(verifier, '_fetch_contract_source') as mock_fetch:
            mock_fetch.return_value = {
                "verified": False,
                "source_available": False,
                "has_proxy": True,
                "functions": ["transfer", "approve", "mint", "burn", "blacklist", "setFee"],
                "suspicious_functions": ["blacklist", "setFee", "pause"],
            }

            result = verifier.analyze_contract("DangerousToken123")

            assert result["is_safe"] is False
            assert len(result["dangerous_patterns"]) > 0
            assert result["risk_level"] == "high"

    def test_ownership_check(self, verifier):
        """Test ownership verification."""
        with patch.object(verifier, '_fetch_ownership_data') as mock_fetch:
            mock_fetch.return_value = {
                "owner_address": "OwnerAddress123",
                "owner_is_contract": False,
                "owner_history": [
                    {"from": None, "to": "OwnerAddress123", "timestamp": "2024-01-01"}
                ],
                "renounced": False,
            }

            result = verifier.check_ownership("TokenAddress123")

            assert "owner_address" in result
            assert "is_renounced" in result
            assert "ownership_risk" in result

    def test_comprehensive_verification(self, verifier):
        """Test comprehensive token verification."""
        with patch.multiple(verifier,
                          _fetch_token_metadata=MagicMock(return_value={"name": "Test", "symbol": "TEST"}),
                          _fetch_token_data=MagicMock(return_value={"creator_holdings_pct": 0.1}),
                          _fetch_liquidity_data=MagicMock(return_value={"total_liquidity_usd": 100000}),
                          _fetch_contract_source=MagicMock(return_value={"verified": True}),
                          _fetch_ownership_data=MagicMock(return_value={"renounced": True})):

            result = verifier.comprehensive_verify("TokenAddress123")

            assert "overall_score" in result
            assert "token_authenticity" in result
            assert "liquidity_analysis" in result
            assert "contract_analysis" in result
            assert "ownership_analysis" in result
            assert "recommendation" in result


class TestTransactionVerifierAsync:
    """Async tests for transaction verifier."""

    @pytest.fixture
    def verifier(self):
        from core.security.transaction_verifier import TransactionVerifier
        return TransactionVerifier()

    @pytest.mark.asyncio
    async def test_async_verification(self, verifier):
        """Test async verification methods."""
        with patch.object(verifier, '_async_fetch_token_data', new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = {
                "name": "Test Token",
                "symbol": "TEST",
                "verified": True,
            }

            result = await verifier.async_verify_token("TokenAddress123")
            assert result is not None


class TestTransactionVerifierEdgeCases:
    """Edge case tests for transaction verifier."""

    @pytest.fixture
    def verifier(self):
        from core.security.transaction_verifier import TransactionVerifier
        return TransactionVerifier()

    def test_invalid_address_handling(self, verifier):
        """Test handling of invalid addresses."""
        result = verifier.verify_token_authenticity("invalid_address")
        assert result["verified"] is False
        assert "error" in result or "invalid" in str(result).lower()

    def test_network_timeout_handling(self, verifier):
        """Test handling of network timeouts."""
        with patch.object(verifier, '_fetch_token_metadata') as mock_fetch:
            mock_fetch.side_effect = TimeoutError("Network timeout")

            result = verifier.verify_token_authenticity("TokenAddress123")
            assert result["verified"] is False
            assert "error" in result

    def test_rate_limit_handling(self, verifier):
        """Test handling of rate limits."""
        with patch.object(verifier, '_fetch_token_metadata') as mock_fetch:
            mock_fetch.side_effect = Exception("Rate limit exceeded")

            result = verifier.verify_token_authenticity("TokenAddress123")
            assert result["verified"] is False
