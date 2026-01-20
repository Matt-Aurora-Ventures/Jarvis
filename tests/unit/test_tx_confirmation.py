"""
Unit tests for transaction confirmation system.
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from core.security.tx_confirmation import (
    TransactionConfirmationService,
    CommitmentLevel,
    TransactionStatus,
    TransactionResult,
    TransactionHistoryEntry
)


class TestTransactionConfirmationService:
    """Test transaction confirmation service."""

    @pytest.fixture
    def rpc_url(self):
        """Test RPC URL."""
        return "https://api.mainnet-beta.solana.com"

    @pytest.fixture
    def service(self, rpc_url):
        """Create confirmation service."""
        return TransactionConfirmationService(
            rpc_url=rpc_url,
            commitment=CommitmentLevel.CONFIRMED
        )

    @pytest.mark.asyncio
    async def test_verify_transaction_success(self, service):
        """Test successful transaction verification."""
        signature = "5KqH..." + "x" * 80

        # Mock RPC response for confirmed transaction
        mock_response = {
            'result': {
                'value': [{
                    'slot': 123456789,
                    'confirmationStatus': 'confirmed',
                    'confirmations': 10,
                    'err': None
                }]
            }
        }

        mock_block_time_response = {
            'result': {
                'blockTime': 1642000000
            }
        }

        with patch.object(service, '_get_session') as mock_session:
            mock_post = AsyncMock()
            mock_post.return_value.__aenter__.return_value.json = AsyncMock(
                side_effect=[mock_response, mock_block_time_response]
            )
            mock_session.return_value.post = mock_post

            result = await service.verify_transaction(signature)

            assert result.success is True
            assert result.signature == signature
            assert result.status == TransactionStatus.CONFIRMED
            assert result.slot == 123456789
            assert result.confirmations == 10
            assert result.error is None

    @pytest.mark.asyncio
    async def test_verify_transaction_failed(self, service):
        """Test failed transaction verification."""
        signature = "5KqH..." + "x" * 80

        # Mock RPC response for failed transaction
        mock_response = {
            'result': {
                'value': [{
                    'slot': 123456789,
                    'confirmationStatus': 'confirmed',
                    'confirmations': 0,
                    'err': {'InstructionError': [0, 'Custom error']}
                }]
            }
        }

        with patch.object(service, '_get_session') as mock_session:
            mock_post = AsyncMock()
            mock_post.return_value.__aenter__.return_value.json = AsyncMock(
                return_value=mock_response
            )
            mock_session.return_value.post = mock_post

            result = await service.verify_transaction(signature)

            assert result.success is False
            assert result.status == TransactionStatus.FAILED
            assert result.error is not None
            assert "failed on-chain" in result.error

    @pytest.mark.asyncio
    async def test_verify_transaction_timeout(self, service):
        """Test transaction verification timeout."""
        signature = "5KqH..." + "x" * 80

        # Mock RPC response that never finds transaction
        mock_response = {
            'result': {
                'value': [None]  # Transaction not found
            }
        }

        with patch.object(service, '_get_session') as mock_session:
            mock_post = AsyncMock()
            mock_post.return_value.__aenter__.return_value.json = AsyncMock(
                return_value=mock_response
            )
            mock_session.return_value.post = mock_post

            # Use short timeout for test
            result = await service.verify_transaction(signature, timeout=2)

            assert result.success is False
            assert result.status == TransactionStatus.TIMEOUT
            assert "timeout" in result.error.lower()

    @pytest.mark.asyncio
    async def test_verify_transaction_retry_logic(self, service):
        """Test retry logic on temporary failures."""
        signature = "5KqH..." + "x" * 80

        call_count = 0

        async def mock_check_status(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                # First two calls return temporary failure
                return TransactionResult(
                    success=False,
                    signature=signature,
                    status=TransactionStatus.PENDING,
                    error="Temporary network error"
                )
            else:
                # Third call succeeds
                return TransactionResult(
                    success=True,
                    signature=signature,
                    status=TransactionStatus.CONFIRMED,
                    slot=123456
                )

        with patch.object(service, '_check_transaction_status', side_effect=mock_check_status):
            result = await service.verify_transaction(signature)

            assert result.success is True
            assert call_count == 3
            assert result.retry_count > 0

    @pytest.mark.asyncio
    async def test_commitment_levels(self, service):
        """Test different commitment levels."""
        signature = "5KqH..." + "x" * 80

        # Test processed commitment
        mock_response_processed = {
            'result': {
                'value': [{
                    'slot': 123456789,
                    'confirmationStatus': 'processed',
                    'confirmations': 0,
                    'err': None
                }]
            }
        }

        with patch.object(service, '_get_session') as mock_session:
            mock_post = AsyncMock()
            mock_post.return_value.__aenter__.return_value.json = AsyncMock(
                return_value=mock_response_processed
            )
            mock_session.return_value.post = mock_post

            # Should succeed with processed commitment
            result = await service.verify_transaction(
                signature,
                commitment=CommitmentLevel.PROCESSED
            )
            assert result.success is True

        # Test finalized commitment (should fail with only 'confirmed')
        mock_response_confirmed = {
            'result': {
                'value': [{
                    'slot': 123456789,
                    'confirmationStatus': 'confirmed',
                    'confirmations': 10,
                    'err': None
                }]
            }
        }

        with patch.object(service, '_get_session') as mock_session:
            mock_post = AsyncMock()
            mock_post.return_value.__aenter__.return_value.json = AsyncMock(
                return_value=mock_response_confirmed
            )
            mock_session.return_value.post = mock_post

            # Should timeout waiting for finalized
            result = await service.verify_transaction(
                signature,
                commitment=CommitmentLevel.FINALIZED,
                timeout=2
            )
            assert result.success is False
            assert result.status == TransactionStatus.TIMEOUT

    @pytest.mark.asyncio
    async def test_log_transaction(self, service, tmp_path):
        """Test transaction logging."""
        # Override history file for test
        service.HISTORY_FILE = str(tmp_path / "tx_history.json")

        result = TransactionResult(
            success=True,
            signature="5KqH...xxx",
            status=TransactionStatus.CONFIRMED,
            slot=123456,
            block_time=1642000000,
            confirmations=10,
            retry_count=1,
            verification_time_ms=1500.0
        )

        await service.log_transaction(
            result=result,
            input_mint="So11111...",
            output_mint="EPjFWdd5...",
            input_amount=1.5,
            output_amount=150.0
        )

        # Verify log file was created and contains entry
        import json
        with open(service.HISTORY_FILE, 'r') as f:
            history = json.load(f)

        assert len(history) == 1
        assert history[0]['signature'] == "5KqH...xxx"
        assert history[0]['status'] == 'confirmed'
        assert history[0]['input_amount'] == 1.5
        assert history[0]['output_amount'] == 150.0

    @pytest.mark.asyncio
    async def test_get_transaction_history(self, service, tmp_path):
        """Test retrieving transaction history."""
        service.HISTORY_FILE = str(tmp_path / "tx_history.json")

        # Log multiple transactions
        for i in range(5):
            result = TransactionResult(
                success=i % 2 == 0,  # Alternate success/failure
                signature=f"sig{i}",
                status=TransactionStatus.CONFIRMED if i % 2 == 0 else TransactionStatus.FAILED,
                slot=123456 + i
            )

            await service.log_transaction(
                result=result,
                input_mint="So11111...",
                output_mint="EPjFWdd5...",
                input_amount=1.0,
                output_amount=100.0
            )

        # Get all history
        all_history = await service.get_transaction_history(limit=10)
        assert len(all_history) == 5

        # Get failed transactions only
        failed = await service.get_failed_transactions(limit=10)
        assert len(failed) == 2
        assert all(entry.status == TransactionStatus.FAILED for entry in failed)

    @pytest.mark.asyncio
    async def test_alert_callback(self, service):
        """Test alert callback on failed transaction."""
        signature = "5KqH..." + "x" * 80

        alert_called = False
        alert_result = None

        async def alert_callback(result):
            nonlocal alert_called, alert_result
            alert_called = True
            alert_result = result

        service.alert_callback = alert_callback

        # Mock failed transaction
        mock_response = {
            'result': {
                'value': [{
                    'slot': 123456789,
                    'confirmationStatus': 'confirmed',
                    'err': {'InstructionError': [0, 'Custom error']}
                }]
            }
        }

        with patch.object(service, '_get_session') as mock_session:
            mock_post = AsyncMock()
            mock_post.return_value.__aenter__.return_value.json = AsyncMock(
                return_value=mock_response
            )
            mock_session.return_value.post = mock_post

            result = await service.verify_transaction(signature)

            assert alert_called is True
            assert alert_result == result
            assert alert_result.success is False

    @pytest.mark.asyncio
    async def test_close_session(self, service):
        """Test session cleanup."""
        # Create a mock session
        mock_session = AsyncMock()
        mock_session.closed = False
        service._session = mock_session

        await service.close()

        mock_session.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_max_retries_exceeded(self, service):
        """Test behavior when max retries exceeded."""
        signature = "5KqH..." + "x" * 80

        async def mock_check_status(*args, **kwargs):
            # Always return temporary failure
            return TransactionResult(
                success=False,
                signature=signature,
                status=TransactionStatus.PENDING,
                error="Network error"
            )

        with patch.object(service, '_check_transaction_status', side_effect=mock_check_status):
            result = await service.verify_transaction(signature)

            assert result.success is False
            assert result.status == TransactionStatus.UNKNOWN
            assert "failed after" in result.error.lower()
            assert result.retry_count == service.MAX_RETRIES


class TestTransactionStatusEnum:
    """Test TransactionStatus enum."""

    def test_status_values(self):
        """Test all status values are defined."""
        assert TransactionStatus.PENDING.value == "pending"
        assert TransactionStatus.CONFIRMED.value == "confirmed"
        assert TransactionStatus.FINALIZED.value == "finalized"
        assert TransactionStatus.FAILED.value == "failed"
        assert TransactionStatus.TIMEOUT.value == "timeout"
        assert TransactionStatus.UNKNOWN.value == "unknown"


class TestCommitmentLevelEnum:
    """Test CommitmentLevel enum."""

    def test_commitment_values(self):
        """Test all commitment levels are defined."""
        assert CommitmentLevel.PROCESSED.value == "processed"
        assert CommitmentLevel.CONFIRMED.value == "confirmed"
        assert CommitmentLevel.FINALIZED.value == "finalized"


class TestTransactionResult:
    """Test TransactionResult dataclass."""

    def test_transaction_result_creation(self):
        """Test creating TransactionResult."""
        result = TransactionResult(
            success=True,
            signature="test_sig",
            status=TransactionStatus.CONFIRMED,
            slot=123456,
            block_time=1642000000,
            confirmations=10,
            retry_count=2,
            verification_time_ms=1500.5
        )

        assert result.success is True
        assert result.signature == "test_sig"
        assert result.status == TransactionStatus.CONFIRMED
        assert result.slot == 123456
        assert result.block_time == 1642000000
        assert result.confirmations == 10
        assert result.retry_count == 2
        assert result.verification_time_ms == 1500.5

    def test_transaction_result_defaults(self):
        """Test TransactionResult default values."""
        result = TransactionResult(
            success=False,
            signature="test_sig",
            status=TransactionStatus.FAILED
        )

        assert result.slot is None
        assert result.block_time is None
        assert result.error is None
        assert result.confirmations == 0
        assert result.retry_count == 0
        assert result.verification_time_ms == 0


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
