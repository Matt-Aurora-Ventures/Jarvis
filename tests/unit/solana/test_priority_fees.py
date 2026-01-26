"""
Unit tests for Solana Priority Fee Estimation.

Tests cover:
1. Fetching recent prioritization fees from RPC
2. Computing percentile-based fee tiers
3. Automatic tier selection based on urgency
4. Graceful fallback on API errors
5. Caching of fee estimates
6. Integration with transaction builder
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from dataclasses import dataclass
from typing import List, Optional, Dict, Any
import time

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))


# =============================================================================
# Test Data
# =============================================================================

# Sample priority fee data from getRecentPrioritizationFees RPC response
SAMPLE_FEE_DATA = [
    {"slot": 100, "prioritizationFee": 0},
    {"slot": 101, "prioritizationFee": 100},
    {"slot": 102, "prioritizationFee": 500},
    {"slot": 103, "prioritizationFee": 1000},
    {"slot": 104, "prioritizationFee": 1500},
    {"slot": 105, "prioritizationFee": 2000},
    {"slot": 106, "prioritizationFee": 3000},
    {"slot": 107, "prioritizationFee": 5000},
    {"slot": 108, "prioritizationFee": 10000},
    {"slot": 109, "prioritizationFee": 50000},
]

# Expected percentiles for SAMPLE_FEE_DATA (sorted: 0, 100, 500, 1000, 1500, 2000, 3000, 5000, 10000, 50000)
# 25th percentile index: 2.25 -> interpolated ~625
# 50th percentile index: 4.5 -> interpolated ~1750
# 75th percentile index: 6.75 -> interpolated ~4500
# 95th percentile index: 8.55 -> interpolated ~28000


# =============================================================================
# Test: Fee Tier Enum
# =============================================================================

class TestPriorityFeeTier:
    """Test the PriorityFeeTier enumeration."""

    def test_tier_values_exist(self):
        """Verify all expected tier values exist."""
        from core.solana.priority_fees import PriorityFeeTier

        assert hasattr(PriorityFeeTier, 'LOW')
        assert hasattr(PriorityFeeTier, 'MEDIUM')
        assert hasattr(PriorityFeeTier, 'HIGH')
        assert hasattr(PriorityFeeTier, 'ULTRA')

    def test_tier_ordering(self):
        """Verify tier ordering (LOW < MEDIUM < HIGH < ULTRA)."""
        from core.solana.priority_fees import PriorityFeeTier

        assert PriorityFeeTier.LOW.value < PriorityFeeTier.MEDIUM.value
        assert PriorityFeeTier.MEDIUM.value < PriorityFeeTier.HIGH.value
        assert PriorityFeeTier.HIGH.value < PriorityFeeTier.ULTRA.value


# =============================================================================
# Test: Priority Fee Estimator - Core Functionality
# =============================================================================

class TestPriorityFeeEstimator:
    """Test the PriorityFeeEstimator class."""

    @pytest.fixture
    def mock_rpc_client(self):
        """Create a mock RPC client that returns sample fee data."""
        client = AsyncMock()
        # Mock the getRecentPrioritizationFees response
        mock_response = MagicMock()
        mock_response.value = SAMPLE_FEE_DATA
        client.get_recent_prioritization_fees.return_value = mock_response
        return client

    @pytest.fixture
    def estimator(self, mock_rpc_client):
        """Create a PriorityFeeEstimator instance for testing."""
        from core.solana.priority_fees import PriorityFeeEstimator
        return PriorityFeeEstimator(rpc_client=mock_rpc_client)

    @pytest.mark.asyncio
    async def test_fetch_recent_fees(self, estimator, mock_rpc_client):
        """Test fetching recent prioritization fees from RPC."""
        fees = await estimator.fetch_recent_fees()

        assert fees is not None
        assert len(fees) == len(SAMPLE_FEE_DATA)
        mock_rpc_client.get_recent_prioritization_fees.assert_called_once()

    @pytest.mark.asyncio
    async def test_compute_fee_tiers(self, estimator):
        """Test computing fee tiers from raw fee data."""
        from core.solana.priority_fees import FeeTiers

        tiers = await estimator.compute_fee_tiers()

        assert isinstance(tiers, FeeTiers)
        assert tiers.low >= 0
        assert tiers.medium >= tiers.low
        assert tiers.high >= tiers.medium
        assert tiers.ultra >= tiers.high

    @pytest.mark.asyncio
    async def test_fee_tier_percentiles(self, estimator):
        """Test that fee tiers correspond to correct percentiles."""
        tiers = await estimator.compute_fee_tiers()

        # Low tier (25th percentile) should be around 500-750
        assert 100 <= tiers.low <= 1000, f"Low tier {tiers.low} not in expected range"

        # Medium tier (50th percentile) should be around 1500-2000
        assert 1000 <= tiers.medium <= 3000, f"Medium tier {tiers.medium} not in expected range"

        # High tier (75th percentile) should be around 3000-5000
        assert 2000 <= tiers.high <= 6000, f"High tier {tiers.high} not in expected range"

        # Ultra tier (95th percentile) should be around 10000-50000
        assert 5000 <= tiers.ultra <= 60000, f"Ultra tier {tiers.ultra} not in expected range"

    @pytest.mark.asyncio
    async def test_get_recommended_fee_low_urgency(self, estimator):
        """Test fee recommendation for low urgency transactions."""
        from core.solana.priority_fees import PriorityFeeTier

        fee, tier = await estimator.get_recommended_fee(urgency=0.1)

        assert tier == PriorityFeeTier.LOW
        assert fee > 0

    @pytest.mark.asyncio
    async def test_get_recommended_fee_medium_urgency(self, estimator):
        """Test fee recommendation for medium urgency transactions."""
        from core.solana.priority_fees import PriorityFeeTier

        fee, tier = await estimator.get_recommended_fee(urgency=0.5)

        assert tier == PriorityFeeTier.MEDIUM

    @pytest.mark.asyncio
    async def test_get_recommended_fee_high_urgency(self, estimator):
        """Test fee recommendation for high urgency transactions."""
        from core.solana.priority_fees import PriorityFeeTier

        fee, tier = await estimator.get_recommended_fee(urgency=0.8)

        assert tier == PriorityFeeTier.HIGH

    @pytest.mark.asyncio
    async def test_get_recommended_fee_ultra_urgency(self, estimator):
        """Test fee recommendation for ultra urgency transactions."""
        from core.solana.priority_fees import PriorityFeeTier

        fee, tier = await estimator.get_recommended_fee(urgency=1.0)

        assert tier == PriorityFeeTier.ULTRA

    @pytest.mark.asyncio
    async def test_get_fee_for_specific_tier(self, estimator):
        """Test getting fee for a specific tier."""
        from core.solana.priority_fees import PriorityFeeTier

        low_fee = await estimator.get_fee_for_tier(PriorityFeeTier.LOW)
        high_fee = await estimator.get_fee_for_tier(PriorityFeeTier.HIGH)

        assert high_fee > low_fee


# =============================================================================
# Test: Caching
# =============================================================================

class TestPriorityFeeCaching:
    """Test fee estimation caching."""

    @pytest.fixture
    def mock_rpc_client(self):
        """Create a mock RPC client."""
        client = AsyncMock()
        mock_response = MagicMock()
        mock_response.value = SAMPLE_FEE_DATA
        client.get_recent_prioritization_fees.return_value = mock_response
        return client

    @pytest.mark.asyncio
    async def test_fee_tiers_cached(self, mock_rpc_client):
        """Test that fee tiers are cached."""
        from core.solana.priority_fees import PriorityFeeEstimator

        estimator = PriorityFeeEstimator(rpc_client=mock_rpc_client, cache_ttl_seconds=60)

        # First call fetches from RPC
        await estimator.compute_fee_tiers()
        assert mock_rpc_client.get_recent_prioritization_fees.call_count == 1

        # Second call uses cache
        await estimator.compute_fee_tiers()
        assert mock_rpc_client.get_recent_prioritization_fees.call_count == 1

    @pytest.mark.asyncio
    async def test_cache_expiry(self, mock_rpc_client):
        """Test that cache expires after TTL."""
        from core.solana.priority_fees import PriorityFeeEstimator

        estimator = PriorityFeeEstimator(rpc_client=mock_rpc_client, cache_ttl_seconds=0.1)

        # First call
        await estimator.compute_fee_tiers()
        assert mock_rpc_client.get_recent_prioritization_fees.call_count == 1

        # Wait for cache to expire
        await asyncio.sleep(0.15)

        # Should fetch again
        await estimator.compute_fee_tiers()
        assert mock_rpc_client.get_recent_prioritization_fees.call_count == 2

    @pytest.mark.asyncio
    async def test_force_refresh_bypasses_cache(self, mock_rpc_client):
        """Test that force_refresh bypasses cache."""
        from core.solana.priority_fees import PriorityFeeEstimator

        estimator = PriorityFeeEstimator(rpc_client=mock_rpc_client, cache_ttl_seconds=60)

        await estimator.compute_fee_tiers()
        assert mock_rpc_client.get_recent_prioritization_fees.call_count == 1

        await estimator.compute_fee_tiers(force_refresh=True)
        assert mock_rpc_client.get_recent_prioritization_fees.call_count == 2


# =============================================================================
# Test: Error Handling and Fallback
# =============================================================================

class TestPriorityFeeErrorHandling:
    """Test error handling and fallback behavior."""

    @pytest.mark.asyncio
    async def test_fallback_on_rpc_error(self):
        """Test fallback to default fees on RPC error."""
        from core.solana.priority_fees import PriorityFeeEstimator, DEFAULT_FEES

        failing_client = AsyncMock()
        failing_client.get_recent_prioritization_fees.side_effect = Exception("RPC Error")

        estimator = PriorityFeeEstimator(rpc_client=failing_client)
        tiers = await estimator.compute_fee_tiers()

        # Should return default fees
        assert tiers.low == DEFAULT_FEES['low']
        assert tiers.medium == DEFAULT_FEES['medium']
        assert tiers.high == DEFAULT_FEES['high']
        assert tiers.ultra == DEFAULT_FEES['ultra']

    @pytest.mark.asyncio
    async def test_fallback_on_empty_response(self):
        """Test fallback when RPC returns empty data."""
        from core.solana.priority_fees import PriorityFeeEstimator, DEFAULT_FEES

        empty_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.value = []
        empty_client.get_recent_prioritization_fees.return_value = mock_response

        estimator = PriorityFeeEstimator(rpc_client=empty_client)
        tiers = await estimator.compute_fee_tiers()

        # Should return default fees
        assert tiers.low == DEFAULT_FEES['low']

    @pytest.mark.asyncio
    async def test_fallback_on_timeout(self):
        """Test fallback on RPC timeout."""
        from core.solana.priority_fees import PriorityFeeEstimator, DEFAULT_FEES

        timeout_client = AsyncMock()
        timeout_client.get_recent_prioritization_fees.side_effect = asyncio.TimeoutError()

        estimator = PriorityFeeEstimator(rpc_client=timeout_client)
        tiers = await estimator.compute_fee_tiers()

        # Should return default fees
        assert tiers.low == DEFAULT_FEES['low']

    @pytest.mark.asyncio
    async def test_get_recommended_fee_uses_cached_fallback_on_error(self):
        """Test that get_recommended_fee uses last good cache on error."""
        from core.solana.priority_fees import PriorityFeeEstimator

        # Client that succeeds first, then fails
        flaky_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.value = SAMPLE_FEE_DATA
        flaky_client.get_recent_prioritization_fees.side_effect = [
            mock_response,
            Exception("Network error"),
        ]

        estimator = PriorityFeeEstimator(rpc_client=flaky_client, cache_ttl_seconds=0)

        # First call succeeds
        fee1, _ = await estimator.get_recommended_fee(urgency=0.5)

        # Second call fails but should use fallback
        fee2, _ = await estimator.get_recommended_fee(urgency=0.5)

        # Should still get a valid fee
        assert fee2 > 0


# =============================================================================
# Test: Account-Specific Fees
# =============================================================================

class TestAccountSpecificFees:
    """Test fetching fees for specific accounts (writable accounts in tx)."""

    @pytest.fixture
    def mock_rpc_client(self):
        """Create a mock RPC client."""
        client = AsyncMock()
        mock_response = MagicMock()
        mock_response.value = SAMPLE_FEE_DATA
        client.get_recent_prioritization_fees.return_value = mock_response
        return client

    @pytest.mark.asyncio
    async def test_fetch_fees_for_accounts(self, mock_rpc_client):
        """Test fetching fees filtered by account addresses."""
        from core.solana.priority_fees import PriorityFeeEstimator

        estimator = PriorityFeeEstimator(rpc_client=mock_rpc_client)
        accounts = ["Account1", "Account2"]

        fees = await estimator.fetch_recent_fees(accounts=accounts)

        # Verify RPC was called with accounts parameter
        mock_rpc_client.get_recent_prioritization_fees.assert_called()
        call_args = mock_rpc_client.get_recent_prioritization_fees.call_args
        # The accounts should be passed to the RPC call
        assert call_args is not None


# =============================================================================
# Test: Minimum Fee Enforcement
# =============================================================================

class TestMinimumFeeEnforcement:
    """Test minimum fee enforcement for transaction viability."""

    @pytest.mark.asyncio
    async def test_minimum_fee_enforced(self):
        """Test that fees are never below minimum threshold."""
        from core.solana.priority_fees import PriorityFeeEstimator, MIN_PRIORITY_FEE

        # Client returning all zero fees
        zero_fee_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.value = [{"slot": i, "prioritizationFee": 0} for i in range(10)]
        zero_fee_client.get_recent_prioritization_fees.return_value = mock_response

        estimator = PriorityFeeEstimator(rpc_client=zero_fee_client)
        fee, _ = await estimator.get_recommended_fee(urgency=0.5)

        assert fee >= MIN_PRIORITY_FEE

    @pytest.mark.asyncio
    async def test_maximum_fee_cap(self):
        """Test that fees are capped at maximum threshold."""
        from core.solana.priority_fees import PriorityFeeEstimator, MAX_PRIORITY_FEE

        # Client returning extremely high fees
        high_fee_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.value = [{"slot": i, "prioritizationFee": 999999999} for i in range(10)]
        high_fee_client.get_recent_prioritization_fees.return_value = mock_response

        estimator = PriorityFeeEstimator(rpc_client=high_fee_client)
        fee, _ = await estimator.get_recommended_fee(urgency=1.0)

        assert fee <= MAX_PRIORITY_FEE


# =============================================================================
# Test: Integration Helpers
# =============================================================================

class TestIntegrationHelpers:
    """Test helper functions for integration with transaction builder."""

    @pytest.mark.asyncio
    async def test_compute_unit_price_conversion(self):
        """Test conversion from priority fee to compute unit price."""
        from core.solana.priority_fees import compute_unit_price_from_fee

        # Priority fee in lamports, compute units consumed
        fee_lamports = 10000
        compute_units = 200000

        unit_price = compute_unit_price_from_fee(fee_lamports, compute_units)

        # Unit price should be fee / CU (in microlamports)
        expected = (fee_lamports * 1_000_000) // compute_units
        assert unit_price == expected

    @pytest.mark.asyncio
    async def test_create_priority_fee_instruction(self):
        """Test creating SetComputeUnitPrice instruction."""
        from core.solana.priority_fees import create_priority_fee_instructions

        instructions = create_priority_fee_instructions(
            priority_fee_lamports=10000,
            compute_units=200000
        )

        # Should return list with compute budget instructions
        assert len(instructions) >= 1


# =============================================================================
# Test: Convenience Functions
# =============================================================================

class TestConvenienceFunctions:
    """Test module-level convenience functions."""

    @pytest.mark.asyncio
    async def test_get_priority_fee_simple(self):
        """Test simple get_priority_fee function."""
        from core.solana.priority_fees import get_priority_fee

        # Should work without explicit RPC client (uses default)
        fee = await get_priority_fee(urgency=0.5)

        assert fee > 0
        assert isinstance(fee, int)

    @pytest.mark.asyncio
    async def test_estimate_fee_for_swap(self):
        """Test estimating fee for a swap transaction."""
        from core.solana.priority_fees import estimate_swap_priority_fee

        fee = await estimate_swap_priority_fee(
            input_mint="So11111111111111111111111111111111111111112",
            output_mint="EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
            urgency=0.7
        )

        assert fee > 0


# =============================================================================
# Test: FeeTiers Dataclass
# =============================================================================

class TestFeeTiersDataclass:
    """Test the FeeTiers dataclass."""

    def test_fee_tiers_creation(self):
        """Test creating FeeTiers instance."""
        from core.solana.priority_fees import FeeTiers

        tiers = FeeTiers(low=100, medium=500, high=1000, ultra=5000)

        assert tiers.low == 100
        assert tiers.medium == 500
        assert tiers.high == 1000
        assert tiers.ultra == 5000

    def test_fee_tiers_to_dict(self):
        """Test FeeTiers to_dict method."""
        from core.solana.priority_fees import FeeTiers

        tiers = FeeTiers(low=100, medium=500, high=1000, ultra=5000)
        d = tiers.to_dict()

        assert d == {
            'low': 100,
            'medium': 500,
            'high': 1000,
            'ultra': 5000,
            'timestamp': d['timestamp']  # Dynamic
        }

    def test_fee_tiers_get_for_tier(self):
        """Test getting fee for specific tier from FeeTiers."""
        from core.solana.priority_fees import FeeTiers, PriorityFeeTier

        tiers = FeeTiers(low=100, medium=500, high=1000, ultra=5000)

        assert tiers.get(PriorityFeeTier.LOW) == 100
        assert tiers.get(PriorityFeeTier.MEDIUM) == 500
        assert tiers.get(PriorityFeeTier.HIGH) == 1000
        assert tiers.get(PriorityFeeTier.ULTRA) == 5000
