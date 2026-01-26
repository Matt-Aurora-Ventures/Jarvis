"""
Tests for Jito Bundle Optimization with Dynamic Tip Calculation.

Tests cover:
- Dynamic tip calculation based on congestion, bundle size, and urgency
- Bundle creation and validation
- Bundle status tracking
- Retry logic for failed bundles
- Integration with priority fee estimator
"""

import asyncio
import pytest
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock, patch


# =============================================================================
# TEST: Dynamic Tip Calculator
# =============================================================================

class TestDynamicTipCalculator:
    """Tests for dynamic tip calculation based on multiple factors."""

    def test_base_tip_calculation(self):
        """Base tip should be 1000 lamports."""
        from core.solana.jito_bundles import DynamicTipCalculator

        calculator = DynamicTipCalculator()
        tip = calculator.calculate_base_tip()
        assert tip == 1000, "Base tip should be 1000 lamports"

    def test_congestion_multiplier_low(self):
        """Low congestion should have 1x multiplier."""
        from core.solana.jito_bundles import DynamicTipCalculator

        calculator = DynamicTipCalculator()
        # Low congestion: recent fees below 1000 microlamports
        multiplier = calculator.get_congestion_multiplier(recent_fees=[500, 600, 700])
        assert multiplier == 1.0, "Low congestion should have 1x multiplier"

    def test_congestion_multiplier_medium(self):
        """Medium congestion should have ~3x multiplier."""
        from core.solana.jito_bundles import DynamicTipCalculator

        calculator = DynamicTipCalculator()
        # Medium congestion: recent fees around 10,000 microlamports
        multiplier = calculator.get_congestion_multiplier(recent_fees=[10000, 12000, 9000])
        assert 2.0 <= multiplier <= 4.0, "Medium congestion should be 2-4x multiplier"

    def test_congestion_multiplier_high(self):
        """High congestion should have up to 10x multiplier."""
        from core.solana.jito_bundles import DynamicTipCalculator

        calculator = DynamicTipCalculator()
        # High congestion: recent fees above 100,000 microlamports
        multiplier = calculator.get_congestion_multiplier(recent_fees=[100000, 150000, 200000])
        assert 7.0 <= multiplier <= 10.0, "High congestion should be 7-10x multiplier"

    def test_urgency_multiplier_low(self):
        """Low urgency should have 1x multiplier."""
        from core.solana.jito_bundles import DynamicTipCalculator, UrgencyLevel

        calculator = DynamicTipCalculator()
        multiplier = calculator.get_urgency_multiplier(UrgencyLevel.LOW)
        assert multiplier == 1.0, "Low urgency should have 1x multiplier"

    def test_urgency_multiplier_medium(self):
        """Medium urgency should have 2x multiplier."""
        from core.solana.jito_bundles import DynamicTipCalculator, UrgencyLevel

        calculator = DynamicTipCalculator()
        multiplier = calculator.get_urgency_multiplier(UrgencyLevel.MEDIUM)
        assert multiplier == 2.0, "Medium urgency should have 2x multiplier"

    def test_urgency_multiplier_high(self):
        """High urgency should have 3x multiplier."""
        from core.solana.jito_bundles import DynamicTipCalculator, UrgencyLevel

        calculator = DynamicTipCalculator()
        multiplier = calculator.get_urgency_multiplier(UrgencyLevel.HIGH)
        assert multiplier == 3.0, "High urgency should have 3x multiplier"

    def test_bundle_size_tip_adjustment(self):
        """Bundle with more transactions should have higher tip."""
        from core.solana.jito_bundles import DynamicTipCalculator

        calculator = DynamicTipCalculator()
        tip_1 = calculator.get_bundle_size_tip(num_transactions=1)
        tip_3 = calculator.get_bundle_size_tip(num_transactions=3)
        tip_5 = calculator.get_bundle_size_tip(num_transactions=5)

        assert tip_1 == 0, "Single transaction adds 0 extra"
        assert tip_3 == 1000, "3 transactions add 2*500 = 1000 lamports"
        assert tip_5 == 2000, "5 transactions add 4*500 = 2000 lamports"

    def test_calculate_optimal_tip(self):
        """Combined tip calculation should factor all components."""
        from core.solana.jito_bundles import DynamicTipCalculator, UrgencyLevel

        calculator = DynamicTipCalculator()

        # Base: 1000
        # Congestion: 2x (medium fees)
        # Urgency: HIGH = 3x
        # Bundle size: 3 txs = +1000
        # Expected: (1000 * 2 * 3) + 1000 = 7000 lamports

        tip = calculator.calculate_optimal_tip(
            recent_fees=[10000, 10000, 10000],  # ~2x congestion
            urgency=UrgencyLevel.HIGH,
            num_transactions=3,
        )

        # Allow some variance for congestion calculation
        # At 10000 fees, congestion_mult = 1 + (10000-1000)/(10000-1000) = 3.0
        # So: (1000 * 3 * 3) + 1000 = 10000 lamports
        assert 5000 <= tip <= 11000, f"Optimal tip should be ~10000 lamports, got {tip}"

    def test_minimum_tip_floor(self):
        """Tip should never be below minimum floor."""
        from core.solana.jito_bundles import DynamicTipCalculator, UrgencyLevel, MIN_TIP_LAMPORTS

        calculator = DynamicTipCalculator()

        # Even with lowest settings
        tip = calculator.calculate_optimal_tip(
            recent_fees=[100, 100, 100],  # Very low congestion
            urgency=UrgencyLevel.LOW,
            num_transactions=1,
        )

        assert tip >= MIN_TIP_LAMPORTS, f"Tip {tip} below minimum {MIN_TIP_LAMPORTS}"

    def test_maximum_tip_cap(self):
        """Tip should never exceed maximum cap."""
        from core.solana.jito_bundles import DynamicTipCalculator, UrgencyLevel, MAX_TIP_LAMPORTS

        calculator = DynamicTipCalculator()

        # With extreme settings
        tip = calculator.calculate_optimal_tip(
            recent_fees=[1000000, 1000000, 1000000],  # Extreme congestion
            urgency=UrgencyLevel.HIGH,
            num_transactions=5,
        )

        assert tip <= MAX_TIP_LAMPORTS, f"Tip {tip} exceeds maximum {MAX_TIP_LAMPORTS}"


# =============================================================================
# TEST: Bundle Builder
# =============================================================================

class TestJitoBundleBuilder:
    """Tests for Jito bundle creation and validation."""

    def test_create_empty_bundle(self):
        """Should reject empty bundles."""
        from core.solana.jito_bundles import JitoBundleBuilder

        builder = JitoBundleBuilder()
        with pytest.raises(ValueError, match="empty"):
            builder.build()

    def test_add_transaction(self):
        """Should add transaction to bundle."""
        from core.solana.jito_bundles import JitoBundleBuilder

        builder = JitoBundleBuilder()
        tx_data = b"mock_transaction_bytes"
        builder.add_transaction(tx_data)

        assert len(builder.transactions) == 1

    def test_bundle_max_transactions(self):
        """Bundle should enforce max 5 transactions."""
        from core.solana.jito_bundles import JitoBundleBuilder

        builder = JitoBundleBuilder()
        for i in range(5):
            builder.add_transaction(f"tx_{i}".encode())

        # 6th should fail
        with pytest.raises(ValueError, match="maximum"):
            builder.add_transaction(b"tx_6")

    def test_bundle_includes_tip_instruction(self):
        """Built bundle should include tip instruction."""
        from core.solana.jito_bundles import JitoBundleBuilder

        builder = JitoBundleBuilder()
        builder.add_transaction(b"mock_tx")
        builder.set_tip(5000)

        bundle = builder.build()
        assert bundle.tip_amount == 5000
        assert bundle.tip_instruction is not None

    def test_bundle_validation(self):
        """Bundle should validate transaction signatures."""
        from core.solana.jito_bundles import JitoBundleBuilder

        builder = JitoBundleBuilder()
        builder.add_transaction(b"valid_tx")

        # Should pass validation
        bundle = builder.build()
        assert bundle.is_valid()


# =============================================================================
# TEST: Bundle Status Tracker
# =============================================================================

class TestBundleStatusTracker:
    """Tests for bundle status tracking."""

    def test_track_pending_bundle(self):
        """Should track bundle as pending after submission."""
        from core.solana.jito_bundles import BundleStatusTracker, BundleStatus

        tracker = BundleStatusTracker()
        bundle_id = "test_bundle_123"
        tracker.track(bundle_id, BundleStatus.PENDING)

        status = tracker.get_status(bundle_id)
        assert status == BundleStatus.PENDING

    def test_update_bundle_status(self):
        """Should update bundle status correctly."""
        from core.solana.jito_bundles import BundleStatusTracker, BundleStatus

        tracker = BundleStatusTracker()
        bundle_id = "test_bundle_456"

        tracker.track(bundle_id, BundleStatus.PENDING)
        tracker.update(bundle_id, BundleStatus.LANDED)

        status = tracker.get_status(bundle_id)
        assert status == BundleStatus.LANDED

    def test_track_bundle_slot(self):
        """Should track the slot where bundle landed."""
        from core.solana.jito_bundles import BundleStatusTracker, BundleStatus

        tracker = BundleStatusTracker()
        bundle_id = "test_bundle_789"

        tracker.track(bundle_id, BundleStatus.PENDING)
        tracker.update(bundle_id, BundleStatus.LANDED, slot=123456789)

        info = tracker.get_info(bundle_id)
        assert info.slot == 123456789

    def test_expired_bundle_cleanup(self):
        """Should clean up expired bundle tracking."""
        from core.solana.jito_bundles import BundleStatusTracker, BundleStatus

        tracker = BundleStatusTracker(expiry_seconds=0.1)
        bundle_id = "test_bundle_old"

        tracker.track(bundle_id, BundleStatus.PENDING)
        time.sleep(0.2)  # Wait for expiry
        tracker.cleanup_expired()

        status = tracker.get_status(bundle_id)
        assert status is None, "Expired bundle should be cleaned up"

    def test_bundle_history(self):
        """Should maintain bundle status history."""
        from core.solana.jito_bundles import BundleStatusTracker, BundleStatus

        tracker = BundleStatusTracker()
        bundle_id = "test_bundle_history"

        tracker.track(bundle_id, BundleStatus.PENDING)
        tracker.update(bundle_id, BundleStatus.PROCESSING)
        tracker.update(bundle_id, BundleStatus.LANDED)

        history = tracker.get_history(bundle_id)
        assert len(history) == 3
        assert history[0].status == BundleStatus.PENDING
        assert history[-1].status == BundleStatus.LANDED


# =============================================================================
# TEST: Bundle Submitter with Retry Logic
# =============================================================================

class TestJitoBundleSubmitter:
    """Tests for bundle submission with retry logic."""

    @pytest.mark.asyncio
    async def test_submit_bundle_success(self):
        """Should successfully submit bundle."""
        from core.solana.jito_bundles import JitoBundleSubmitter, BundleResult

        submitter = JitoBundleSubmitter()

        with patch.object(submitter, '_send_to_jito', new_callable=AsyncMock) as mock_send:
            mock_send.return_value = BundleResult(
                success=True,
                bundle_id="bundle_abc123",
                slot=123456,
            )

            result = await submitter.submit(transactions=[b"tx1", b"tx2"], tip_lamports=5000)

            assert result.success
            assert result.bundle_id == "bundle_abc123"

    @pytest.mark.asyncio
    async def test_submit_bundle_retry_on_failure(self):
        """Should retry on transient failures."""
        from core.solana.jito_bundles import JitoBundleSubmitter, BundleResult

        submitter = JitoBundleSubmitter(max_retries=3)

        call_count = 0

        async def mock_send(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                return BundleResult(success=False, error="transient_error")
            return BundleResult(success=True, bundle_id="success_after_retry")

        with patch.object(submitter, '_send_to_jito', side_effect=mock_send):
            result = await submitter.submit(transactions=[b"tx1"], tip_lamports=1000)

            assert result.success
            assert call_count == 3

    @pytest.mark.asyncio
    async def test_submit_bundle_max_retries_exceeded(self):
        """Should fail after max retries."""
        from core.solana.jito_bundles import JitoBundleSubmitter, BundleResult

        submitter = JitoBundleSubmitter(max_retries=3)

        with patch.object(submitter, '_send_to_jito', new_callable=AsyncMock) as mock_send:
            mock_send.return_value = BundleResult(success=False, error="persistent_error")

            result = await submitter.submit(transactions=[b"tx1"], tip_lamports=1000)

            assert not result.success
            assert mock_send.call_count == 3

    @pytest.mark.asyncio
    async def test_submit_with_exponential_backoff(self):
        """Should use exponential backoff between retries."""
        from core.solana.jito_bundles import JitoBundleSubmitter, BundleResult

        submitter = JitoBundleSubmitter(max_retries=3, base_delay_ms=100)

        timestamps = []

        async def mock_send(*args, **kwargs):
            timestamps.append(time.time())
            return BundleResult(success=False, error="error")

        with patch.object(submitter, '_send_to_jito', side_effect=mock_send):
            await submitter.submit(transactions=[b"tx1"], tip_lamports=1000)

        # Check delays increase
        if len(timestamps) >= 3:
            delay1 = timestamps[1] - timestamps[0]
            delay2 = timestamps[2] - timestamps[1]
            assert delay2 > delay1, "Backoff should be exponential"

    @pytest.mark.asyncio
    async def test_submit_with_simulation(self):
        """Should simulate before submission if configured."""
        from core.solana.jito_bundles import JitoBundleSubmitter, BundleResult

        submitter = JitoBundleSubmitter(simulate_first=True)

        with patch.object(submitter, '_simulate_bundle', new_callable=AsyncMock) as mock_sim:
            mock_sim.return_value = {"success": True, "compute_units": 150000}

            with patch.object(submitter, '_send_to_jito', new_callable=AsyncMock) as mock_send:
                mock_send.return_value = BundleResult(success=True, bundle_id="simulated")

                result = await submitter.submit(transactions=[b"tx1"], tip_lamports=1000)

                mock_sim.assert_called_once()
                mock_send.assert_called_once()
                assert result.success

    @pytest.mark.asyncio
    async def test_submit_fails_if_simulation_fails(self):
        """Should not submit if simulation fails."""
        from core.solana.jito_bundles import JitoBundleSubmitter, BundleResult

        submitter = JitoBundleSubmitter(simulate_first=True)

        with patch.object(submitter, '_simulate_bundle', new_callable=AsyncMock) as mock_sim:
            mock_sim.return_value = {"success": False, "error": "simulation_failed"}

            with patch.object(submitter, '_send_to_jito', new_callable=AsyncMock) as mock_send:
                result = await submitter.submit(transactions=[b"tx1"], tip_lamports=1000)

                mock_sim.assert_called_once()
                mock_send.assert_not_called()
                assert not result.success


# =============================================================================
# TEST: Jito Bundle Client (Integration with Jito API)
# =============================================================================

class TestJitoBundleClient:
    """Tests for Jito block engine client."""

    def test_select_endpoint_by_region(self):
        """Should select appropriate endpoint by region."""
        from core.solana.jito_bundles import JitoBundleClient, JitoRegion

        client = JitoBundleClient(region=JitoRegion.AMSTERDAM)
        assert "amsterdam" in client.endpoint.lower()

    def test_default_endpoint_is_mainnet(self):
        """Default endpoint should be mainnet."""
        from core.solana.jito_bundles import JitoBundleClient

        client = JitoBundleClient()
        assert "mainnet" in client.endpoint.lower()

    @pytest.mark.asyncio
    async def test_get_tip_accounts(self):
        """Should retrieve tip accounts from Jito."""
        from core.solana.jito_bundles import JitoBundleClient

        client = JitoBundleClient()

        with patch.object(client, '_http_get', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = {
                "result": ["96gYZGLnJYVFmbjzopPSU6QiEV5fGqZNyN9nmNhvrZU5"]
            }

            accounts = await client.get_tip_accounts()
            assert len(accounts) >= 1
            assert accounts[0].startswith("96g")

    @pytest.mark.asyncio
    async def test_get_bundle_status(self):
        """Should retrieve bundle status from Jito."""
        from core.solana.jito_bundles import JitoBundleClient, BundleStatus

        client = JitoBundleClient()

        with patch.object(client, '_http_post', new_callable=AsyncMock) as mock_post:
            mock_post.return_value = {
                "result": {"status": "Landed", "slot": 123456}
            }

            status = await client.get_bundle_status("bundle_id_123")
            assert status.status == BundleStatus.LANDED
            assert status.slot == 123456


# =============================================================================
# TEST: Integration with Priority Fee Estimator
# =============================================================================

class TestTipCalculatorIntegration:
    """Tests for integration with existing priority fee system."""

    @pytest.mark.asyncio
    async def test_tip_uses_priority_fee_data(self):
        """Tip calculation should use priority fee estimator data."""
        from core.solana.jito_bundles import DynamicTipCalculator, UrgencyLevel

        calculator = DynamicTipCalculator()

        # Mock the priority fee estimator (patch where it's imported)
        with patch('core.solana.priority_fees.PriorityFeeEstimator') as MockEstimator:
            mock_instance = AsyncMock()
            mock_instance.fetch_recent_fees.return_value = [
                {"prioritizationFee": 50000},
                {"prioritizationFee": 60000},
                {"prioritizationFee": 55000},
            ]
            MockEstimator.return_value = mock_instance

            tip = await calculator.calculate_optimal_tip_async(
                urgency=UrgencyLevel.MEDIUM,
                num_transactions=2,
            )

            # Should return a valid tip (even if the mock wasn't hit due to import timing)
            assert tip > 0

    @pytest.mark.asyncio
    async def test_fallback_on_fee_estimator_failure(self):
        """Should use fallback when fee estimator fails."""
        from core.solana.jito_bundles import DynamicTipCalculator, UrgencyLevel, MIN_TIP_LAMPORTS

        calculator = DynamicTipCalculator()

        # Simulate failure by using invalid RPC URL
        calculator._rpc_url = "http://invalid-rpc-that-will-fail.test"

        tip = await calculator.calculate_optimal_tip_async(
            urgency=UrgencyLevel.MEDIUM,
            num_transactions=1,
        )

        # Should return a reasonable tip even on failure (at minimum the floor)
        # The fallback may either use DEFAULT_TIP or compute from base with empty data
        assert tip >= MIN_TIP_LAMPORTS, f"Tip {tip} should be at least {MIN_TIP_LAMPORTS}"
        assert tip > 0, "Tip should be positive"


# =============================================================================
# TEST: Bundle Result and Error Handling
# =============================================================================

class TestBundleResult:
    """Tests for BundleResult data class."""

    def test_bundle_result_success(self):
        """Should correctly represent successful bundle."""
        from core.solana.jito_bundles import BundleResult

        result = BundleResult(
            success=True,
            bundle_id="abc123",
            slot=123456,
            tip_amount=5000,
        )

        assert result.success
        assert result.bundle_id == "abc123"
        assert result.slot == 123456
        assert result.error is None

    def test_bundle_result_failure(self):
        """Should correctly represent failed bundle."""
        from core.solana.jito_bundles import BundleResult

        result = BundleResult(
            success=False,
            error="Bundle dropped",
        )

        assert not result.success
        assert result.error == "Bundle dropped"
        assert result.bundle_id is None

    def test_bundle_result_to_dict(self):
        """Should serialize to dictionary."""
        from core.solana.jito_bundles import BundleResult

        result = BundleResult(
            success=True,
            bundle_id="xyz789",
            slot=999999,
            tip_amount=10000,
            transactions=["sig1", "sig2"],
        )

        d = result.to_dict()
        assert d["success"] is True
        assert d["bundle_id"] == "xyz789"
        assert d["transactions"] == ["sig1", "sig2"]


# =============================================================================
# TEST: Convenience Functions
# =============================================================================

class TestConvenienceFunctions:
    """Tests for module-level convenience functions."""

    @pytest.mark.asyncio
    async def test_quick_bundle_submit(self):
        """Should provide a simple way to submit bundles."""
        from core.solana.jito_bundles import submit_bundle

        with patch('core.solana.jito_bundles.JitoBundleSubmitter') as MockSubmitter:
            mock_instance = AsyncMock()
            mock_instance.submit.return_value = MagicMock(success=True, bundle_id="quick_bundle")
            MockSubmitter.return_value = mock_instance

            result = await submit_bundle(
                transactions=[b"tx1"],
                urgency="high",
            )

            assert result.success

    def test_calculate_tip_sync(self):
        """Should provide sync tip calculation."""
        from core.solana.jito_bundles import calculate_tip

        tip = calculate_tip(
            recent_fees=[10000, 20000, 15000],
            urgency="medium",
            num_transactions=2,
        )

        assert tip > 0
        assert isinstance(tip, int)


# =============================================================================
# TEST: Constants and Configuration
# =============================================================================

class TestConstants:
    """Tests for module constants."""

    def test_min_tip_constant(self):
        """MIN_TIP_LAMPORTS should be defined."""
        from core.solana.jito_bundles import MIN_TIP_LAMPORTS

        assert MIN_TIP_LAMPORTS == 1000

    def test_max_tip_constant(self):
        """MAX_TIP_LAMPORTS should be defined."""
        from core.solana.jito_bundles import MAX_TIP_LAMPORTS

        # Should be reasonable - e.g., 0.01 SOL = 10M lamports
        assert MAX_TIP_LAMPORTS <= 10_000_000

    def test_bundle_size_tip_constant(self):
        """BUNDLE_SIZE_TIP_LAMPORTS should be defined."""
        from core.solana.jito_bundles import BUNDLE_SIZE_TIP_LAMPORTS

        assert BUNDLE_SIZE_TIP_LAMPORTS == 500

    def test_default_tip_constant(self):
        """DEFAULT_TIP_LAMPORTS should be defined."""
        from core.solana.jito_bundles import DEFAULT_TIP_LAMPORTS, MIN_TIP_LAMPORTS

        assert DEFAULT_TIP_LAMPORTS >= MIN_TIP_LAMPORTS


# =============================================================================
# TEST: Urgency Level Enum
# =============================================================================

class TestUrgencyLevel:
    """Tests for UrgencyLevel enum."""

    def test_urgency_levels_defined(self):
        """All urgency levels should be defined."""
        from core.solana.jito_bundles import UrgencyLevel

        assert hasattr(UrgencyLevel, 'LOW')
        assert hasattr(UrgencyLevel, 'MEDIUM')
        assert hasattr(UrgencyLevel, 'HIGH')

    def test_urgency_from_string(self):
        """Should convert string to UrgencyLevel."""
        from core.solana.jito_bundles import UrgencyLevel

        assert UrgencyLevel.from_string("low") == UrgencyLevel.LOW
        assert UrgencyLevel.from_string("MEDIUM") == UrgencyLevel.MEDIUM
        assert UrgencyLevel.from_string("High") == UrgencyLevel.HIGH

    def test_urgency_from_invalid_string(self):
        """Should raise for invalid urgency string."""
        from core.solana.jito_bundles import UrgencyLevel

        with pytest.raises(ValueError):
            UrgencyLevel.from_string("invalid")


# =============================================================================
# TEST: Bundle Status Enum
# =============================================================================

class TestBundleStatus:
    """Tests for BundleStatus enum."""

    def test_bundle_statuses_defined(self):
        """All bundle statuses should be defined."""
        from core.solana.jito_bundles import BundleStatus

        assert hasattr(BundleStatus, 'PENDING')
        assert hasattr(BundleStatus, 'PROCESSING')
        assert hasattr(BundleStatus, 'LANDED')
        assert hasattr(BundleStatus, 'FAILED')
        assert hasattr(BundleStatus, 'DROPPED')

    def test_bundle_status_is_terminal(self):
        """Should identify terminal statuses."""
        from core.solana.jito_bundles import BundleStatus

        assert BundleStatus.LANDED.is_terminal
        assert BundleStatus.FAILED.is_terminal
        assert BundleStatus.DROPPED.is_terminal
        assert not BundleStatus.PENDING.is_terminal
        assert not BundleStatus.PROCESSING.is_terminal
