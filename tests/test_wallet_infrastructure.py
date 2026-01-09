"""
Tests for core/wallet_infrastructure.py

Tests cover:
- Address validation
- Priority fee configuration
- Transaction builder
- Token safety analysis
- ALT manager
"""

import asyncio
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.wallet_infrastructure import (
    is_valid_solana_address,
    TransactionPriority,
    PriorityFeeConfig,
    BlockhashInfo,
    TransactionSimulationResult,
    TokenSafetyReport,
    AddressLookupTableManager,
    TransactionBuilder,
    TokenSafetyAnalyzer,
    SOL_MINT,
    USDC_MINT,
    BASE58_ALPHABET,
    MIN_JITO_TIP_LAMPORTS,
)


class TestAddressValidation:
    """Test Solana address validation."""

    def test_valid_sol_mint(self):
        """SOL mint should be valid."""
        assert is_valid_solana_address(SOL_MINT)

    def test_valid_usdc_mint(self):
        """USDC mint should be valid."""
        assert is_valid_solana_address(USDC_MINT)

    def test_valid_addresses(self):
        """Various valid addresses."""
        valid = [
            "So11111111111111111111111111111111111111112",
            "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
            "Es9vMFrzaCER3EJmqvQC2Uo9qowWP1h1xFh3Le7YpR1V",
            "JUP6LkbZbjS1jKKwapdHNy74zcZ3tLUZoi5QNyVTaV4",
        ]
        for addr in valid:
            assert is_valid_solana_address(addr), f"{addr} should be valid"

    def test_invalid_empty(self):
        """Empty string should be invalid."""
        assert not is_valid_solana_address("")
        assert not is_valid_solana_address(None)

    def test_invalid_too_short(self):
        """Short strings should be invalid."""
        assert not is_valid_solana_address("abc")
        assert not is_valid_solana_address("a" * 31)

    def test_invalid_too_long(self):
        """Long strings should be invalid."""
        assert not is_valid_solana_address("a" * 50)

    def test_invalid_ethereum_address(self):
        """Ethereum addresses should be invalid."""
        assert not is_valid_solana_address("0x1234567890abcdef1234567890abcdef12345678")

    def test_invalid_characters(self):
        """Invalid base58 characters should fail."""
        # O, 0, I, l are not in base58
        assert not is_valid_solana_address("O" * 32)
        assert not is_valid_solana_address("0" * 32)
        assert not is_valid_solana_address("I" * 32)
        assert not is_valid_solana_address("l" * 32)


class TestPriorityFeeConfig:
    """Test priority fee configuration."""

    def test_low_priority(self):
        """Low priority should have minimal fees."""
        config = PriorityFeeConfig.for_priority(TransactionPriority.LOW)
        assert config.priority_fee_lamports == 1_000
        assert config.jito_tip_lamports == 0
        assert not config.use_jito

    def test_medium_priority(self):
        """Medium priority should have moderate fees."""
        config = PriorityFeeConfig.for_priority(TransactionPriority.MEDIUM)
        assert config.priority_fee_lamports == 10_000
        assert not config.use_jito

    def test_high_priority(self):
        """High priority should have higher fees."""
        config = PriorityFeeConfig.for_priority(TransactionPriority.HIGH)
        assert config.priority_fee_lamports == 100_000
        assert not config.use_jito

    def test_urgent_priority(self):
        """Urgent priority should use Jito."""
        config = PriorityFeeConfig.for_priority(TransactionPriority.URGENT)
        assert config.priority_fee_lamports >= 100_000
        assert config.jito_tip_lamports >= MIN_JITO_TIP_LAMPORTS
        assert config.use_jito

    def test_fee_ordering(self):
        """Fees should increase with priority."""
        low = PriorityFeeConfig.for_priority(TransactionPriority.LOW)
        medium = PriorityFeeConfig.for_priority(TransactionPriority.MEDIUM)
        high = PriorityFeeConfig.for_priority(TransactionPriority.HIGH)
        urgent = PriorityFeeConfig.for_priority(TransactionPriority.URGENT)

        assert low.priority_fee_lamports < medium.priority_fee_lamports
        assert medium.priority_fee_lamports < high.priority_fee_lamports
        assert high.priority_fee_lamports < urgent.priority_fee_lamports


class TestBlockhashInfo:
    """Test blockhash validity tracking."""

    def test_fresh_blockhash_valid(self):
        """Fresh blockhash should be valid."""
        import time
        info = BlockhashInfo(
            blockhash="test_blockhash",
            last_valid_block_height=100,
            fetched_at=time.time(),
        )
        assert info.is_likely_valid()

    def test_old_blockhash_invalid(self):
        """Old blockhash should be invalid."""
        import time
        info = BlockhashInfo(
            blockhash="test_blockhash",
            last_valid_block_height=100,
            fetched_at=time.time() - 120,  # 2 minutes ago
        )
        assert not info.is_likely_valid()

    def test_block_height_exceeded(self):
        """Exceeded block height should be invalid."""
        import time
        info = BlockhashInfo(
            blockhash="test_blockhash",
            last_valid_block_height=100,
            fetched_at=time.time(),
        )
        assert not info.is_likely_valid(current_block_height=150)


class TestTransactionSimulationResult:
    """Test simulation result formatting."""

    def test_success_summary(self):
        """Successful simulation should produce readable summary."""
        result = TransactionSimulationResult(
            success=True,
            units_consumed=150000,
            estimated_fee_lamports=5000,
        )
        summary = result.get_human_readable_summary()
        assert "PASSED" in summary
        assert "150,000" in summary
        assert "SOL" in summary

    def test_failure_summary(self):
        """Failed simulation should show error details."""
        result = TransactionSimulationResult(
            success=False,
            error="Insufficient funds",
            error_hint="Add more SOL to your wallet",
        )
        summary = result.get_human_readable_summary()
        assert "FAILED" in summary
        assert "Insufficient funds" in summary
        assert "Add more SOL" in summary


class TestTokenSafetyReport:
    """Test token safety report."""

    def test_safe_token(self):
        """Safe token should have low risk score."""
        report = TokenSafetyReport(
            mint=SOL_MINT,
            symbol="SOL",
            safe=True,
            risk_score=10,
            mint_authority_revoked=True,
            freeze_authority_present=False,
            liquidity_amount_usd=1_000_000,
        )
        assert report.safe
        assert report.risk_score < 50

    def test_risky_token_warnings(self):
        """Risky token should have warnings."""
        report = TokenSafetyReport(
            mint="risky_mint",
            symbol="SCAM",
            safe=False,
            risk_score=85,
            warnings=[
                "Mint authority NOT revoked",
                "Freeze authority present",
            ],
        )
        summary = report.get_summary()
        assert "RISKY" in summary
        assert "Mint authority" in summary

    def test_report_summary_format(self):
        """Summary should be well-formatted."""
        report = TokenSafetyReport(
            mint="test_mint_123456789012345678901234",
            symbol="TEST",
            safe=True,
            risk_score=25,
        )
        summary = report.get_summary()
        assert "TEST" in summary
        assert "test_min" in summary  # Truncated to 8 chars
        assert "25" in summary


class TestAddressLookupTableManager:
    """Test ALT manager functionality."""

    def test_init(self):
        """Manager should initialize correctly."""
        manager = AddressLookupTableManager()
        assert manager is not None

    def test_get_address_index_found(self):
        """Should find address index in table."""
        manager = AddressLookupTableManager()
        table_data = {
            "address": "table_address",
            "addresses": ["addr1", "addr2", "addr3"],
        }
        assert manager.get_address_index(table_data, "addr1") == 0
        assert manager.get_address_index(table_data, "addr2") == 1
        assert manager.get_address_index(table_data, "addr3") == 2

    def test_get_address_index_not_found(self):
        """Should return None for missing address."""
        manager = AddressLookupTableManager()
        table_data = {
            "address": "table_address",
            "addresses": ["addr1", "addr2"],
        }
        assert manager.get_address_index(table_data, "addr3") is None

    def test_compress_accounts(self):
        """Should compress accounts using ALT."""
        manager = AddressLookupTableManager()
        table = {
            "address": "table1",
            "addresses": ["addr1", "addr2", "addr3"],
        }
        accounts = ["addr1", "addr4", "addr2"]
        remaining, compressed = manager.compress_accounts(accounts, [table])

        assert len(remaining) == 1
        assert "addr4" in remaining
        assert len(compressed) == 2

    def test_estimate_size_savings(self):
        """Should calculate size savings correctly."""
        manager = AddressLookupTableManager()
        result = manager.estimate_size_savings(
            num_accounts=10,
            num_compressed=8,
        )
        assert result["original_bytes"] == 320  # 10 * 32
        assert result["compressed_bytes"] == 72  # 2 * 32 + 8 * 1
        assert result["savings_bytes"] == 248
        assert result["savings_pct"] > 70


class TestTransactionBuilder:
    """Test transaction builder."""

    def test_set_priority(self):
        """Should update priority configuration."""
        builder = TransactionBuilder()
        builder.set_priority(TransactionPriority.URGENT)
        assert builder._priority_config.use_jito

    def test_compute_budget_instructions(self):
        """Should generate compute budget instructions."""
        builder = TransactionBuilder()
        builder.set_priority(TransactionPriority.HIGH)
        instructions = builder.build_compute_budget_instructions()

        assert len(instructions) == 2
        assert instructions[0]["type"] == "set_compute_unit_limit"
        assert instructions[1]["type"] == "set_compute_unit_price"

    def test_estimate_transaction_size(self):
        """Should estimate transaction size correctly."""
        builder = TransactionBuilder()
        result = builder.estimate_transaction_size(
            instructions=[{"data": "test"}],
            accounts=["addr" + str(i) for i in range(50)],
            use_alt=False,
        )
        assert result["account_count"] == 50
        assert result["needs_alt"]  # 50 accounts > 32 limit
        assert not result["fits_in_transaction"]


class TestTokenSafetyAnalyzer:
    """Test token safety analyzer."""

    def test_min_liquidity_constant(self):
        """Min liquidity should be set appropriately."""
        assert TokenSafetyAnalyzer.MIN_LIQUIDITY_USD >= 50_000

    def test_max_concentration_constant(self):
        """Max holder concentration should be reasonable."""
        assert TokenSafetyAnalyzer.MAX_HOLDER_CONCENTRATION <= 50

    @pytest.mark.asyncio
    async def test_analyze_token_returns_report(self):
        """Analysis should return a report."""
        analyzer = TokenSafetyAnalyzer()
        report = await analyzer.analyze_token(SOL_MINT)
        assert isinstance(report, TokenSafetyReport)
        assert report.mint == SOL_MINT


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
