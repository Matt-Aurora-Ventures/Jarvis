"""
Tests for core/approval_gate.py

Tests cover:
- Trade proposal creation and serialization
- Approval status enum values
- ApprovalGate initialization
- Proposal submission
- Approval and rejection workflows
- Kill switch functionality
- Expiration handling
"""

import json
import os
import sys
import tempfile
import time
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.approval_gate import (
    ApprovalStatus,
    TradeProposal,
    ApprovalGate,
)


class TestApprovalStatus:
    """Test ApprovalStatus enum."""

    def test_pending_value(self):
        """Should have pending status."""
        assert ApprovalStatus.PENDING.value == "pending"

    def test_approved_value(self):
        """Should have approved status."""
        assert ApprovalStatus.APPROVED.value == "approved"

    def test_rejected_value(self):
        """Should have rejected status."""
        assert ApprovalStatus.REJECTED.value == "rejected"

    def test_expired_value(self):
        """Should have expired status."""
        assert ApprovalStatus.EXPIRED.value == "expired"

    def test_killed_value(self):
        """Should have killed status."""
        assert ApprovalStatus.KILLED.value == "killed"


class TestTradeProposal:
    """Test TradeProposal dataclass."""

    def test_create_proposal(self):
        """Should create proposal with required fields."""
        proposal = TradeProposal(
            id="test-001",
            symbol="SOL",
            side="BUY",
            size=10.0,
            price=150.0,
            strategy="momentum",
            reason="Strong uptrend detected"
        )
        assert proposal.id == "test-001"
        assert proposal.symbol == "SOL"
        assert proposal.side == "BUY"
        assert proposal.size == 10.0
        assert proposal.price == 150.0
        assert proposal.strategy == "momentum"
        assert proposal.status == ApprovalStatus.PENDING

    def test_default_expiry(self):
        """Should have 5 minute default expiry."""
        proposal = TradeProposal(
            id="test-001",
            symbol="SOL",
            side="BUY",
            size=10.0,
            price=150.0,
            strategy="momentum",
            reason="Test"
        )
        assert proposal.expiry_seconds == 300

    def test_to_dict(self):
        """Should serialize to dict correctly."""
        proposal = TradeProposal(
            id="test-001",
            symbol="SOL",
            side="BUY",
            size=10.0,
            price=150.0,
            strategy="momentum",
            reason="Test reason"
        )
        data = proposal.to_dict()
        assert data["id"] == "test-001"
        assert data["symbol"] == "SOL"
        assert data["side"] == "BUY"
        assert data["size"] == 10.0
        assert data["price"] == 150.0
        assert data["status"] == "pending"

    def test_from_dict(self):
        """Should deserialize from dict correctly."""
        data = {
            "id": "test-002",
            "symbol": "BTC",
            "side": "SELL",
            "size": 0.5,
            "price": 45000.0,
            "strategy": "trend_follow",
            "reason": "Downtrend",
            "status": "approved",
        }
        proposal = TradeProposal.from_dict(data)
        assert proposal.id == "test-002"
        assert proposal.symbol == "BTC"
        assert proposal.side == "SELL"
        assert proposal.status == ApprovalStatus.APPROVED

    def test_from_dict_with_string_status(self):
        """Should handle string status values."""
        data = {
            "id": "test-003",
            "symbol": "ETH",
            "side": "BUY",
            "size": 5.0,
            "price": 3000.0,
            "strategy": "test",
            "reason": "test",
            "status": "rejected",
        }
        proposal = TradeProposal.from_dict(data)
        assert proposal.status == ApprovalStatus.REJECTED

    def test_is_expired_false(self):
        """Should not be expired when fresh."""
        proposal = TradeProposal(
            id="test",
            symbol="SOL",
            side="BUY",
            size=1.0,
            price=100.0,
            strategy="test",
            reason="test",
            timestamp=time.time()
        )
        assert not proposal.is_expired()

    def test_is_expired_true(self):
        """Should be expired when past expiry_seconds."""
        proposal = TradeProposal(
            id="test",
            symbol="SOL",
            side="BUY",
            size=1.0,
            price=100.0,
            strategy="test",
            reason="test",
            timestamp=time.time() - 400,  # 400 seconds ago
            expiry_seconds=300
        )
        assert proposal.is_expired()

    def test_roundtrip_serialization(self):
        """Should survive serialization roundtrip."""
        original = TradeProposal(
            id="roundtrip-test",
            symbol="SOL",
            side="BUY",
            size=25.5,
            price=148.75,
            strategy="dip_buy",
            reason="Oversold RSI",
            expiry_seconds=600,
        )
        data = original.to_dict()
        restored = TradeProposal.from_dict(data)

        assert restored.id == original.id
        assert restored.symbol == original.symbol
        assert restored.side == original.side
        assert restored.size == original.size
        assert restored.price == original.price
        assert restored.strategy == original.strategy
        assert restored.status == original.status


class TestApprovalGate:
    """Test ApprovalGate class."""

    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for tests."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def gate(self, temp_dir):
        """Create ApprovalGate with temp directory."""
        # Clear any existing env var
        if "LIFEOS_KILL_SWITCH" in os.environ:
            del os.environ["LIFEOS_KILL_SWITCH"]
        return ApprovalGate(data_dir=temp_dir)

    def test_init_creates_directory(self, temp_dir):
        """Should create data directory on init."""
        sub_dir = temp_dir / "approvals"
        gate = ApprovalGate(data_dir=sub_dir)
        assert sub_dir.exists()

    def test_submit_for_approval(self, gate):
        """Should accept trade proposal."""
        proposal = TradeProposal(
            id="",
            symbol="SOL",
            side="BUY",
            size=10.0,
            price=150.0,
            strategy="test",
            reason="test"
        )

        with patch('subprocess.run'):  # Mock notification
            proposal_id = gate.submit_for_approval(proposal)

        assert proposal_id is not None
        assert len(proposal_id) > 0

    def test_submit_generates_id(self, gate):
        """Should generate ID if not provided."""
        proposal = TradeProposal(
            id="",
            symbol="SOL",
            side="BUY",
            size=10.0,
            price=150.0,
            strategy="test",
            reason="test"
        )

        with patch('subprocess.run'):
            proposal_id = gate.submit_for_approval(proposal)

        assert proposal_id.startswith("trade_")

    def test_approve_pending(self, gate):
        """Should approve pending proposal."""
        proposal = TradeProposal(
            id="approve-test",
            symbol="SOL",
            side="BUY",
            size=10.0,
            price=150.0,
            strategy="test",
            reason="test"
        )

        with patch('subprocess.run'):
            gate.submit_for_approval(proposal)

        result = gate.approve("approve-test")
        assert result is True

    def test_approve_nonexistent(self, gate):
        """Should return False for nonexistent proposal."""
        result = gate.approve("nonexistent-id")
        assert result is False

    def test_reject_pending(self, gate):
        """Should reject pending proposal."""
        proposal = TradeProposal(
            id="reject-test",
            symbol="SOL",
            side="BUY",
            size=10.0,
            price=150.0,
            strategy="test",
            reason="test"
        )

        with patch('subprocess.run'):
            gate.submit_for_approval(proposal)

        result = gate.reject("reject-test", "Too risky")
        assert result is True

    def test_reject_nonexistent(self, gate):
        """Should return False for nonexistent proposal."""
        result = gate.reject("nonexistent-id", "Reason")
        assert result is False

    def test_get_pending_list(self, gate):
        """Should list pending proposals."""
        proposal1 = TradeProposal(
            id="pending-1",
            symbol="SOL",
            side="BUY",
            size=10.0,
            price=150.0,
            strategy="test",
            reason="test"
        )
        proposal2 = TradeProposal(
            id="pending-2",
            symbol="ETH",
            side="SELL",
            size=5.0,
            price=3000.0,
            strategy="test",
            reason="test"
        )

        with patch('subprocess.run'):
            gate.submit_for_approval(proposal1)
            gate.submit_for_approval(proposal2)

        pending = gate.get_pending()
        assert len(pending) == 2

    def test_kill_switch_blocks_submission(self, temp_dir):
        """Should block submissions when kill switch active."""
        os.environ["LIFEOS_KILL_SWITCH"] = "1"
        try:
            gate = ApprovalGate(data_dir=temp_dir)
            proposal = TradeProposal(
                id="blocked",
                symbol="SOL",
                side="BUY",
                size=10.0,
                price=150.0,
                strategy="test",
                reason="test"
            )

            with patch('subprocess.run'):
                gate.submit_for_approval(proposal)

            # Proposal should be killed, not pending
            assert proposal.status == ApprovalStatus.KILLED
        finally:
            del os.environ["LIFEOS_KILL_SWITCH"]

    def test_kill_switch_blocks_approval(self, temp_dir):
        """Should block approvals when kill switch active."""
        gate = ApprovalGate(data_dir=temp_dir)
        proposal = TradeProposal(
            id="to-block",
            symbol="SOL",
            side="BUY",
            size=10.0,
            price=150.0,
            strategy="test",
            reason="test"
        )

        with patch('subprocess.run'):
            gate.submit_for_approval(proposal)

        # Activate kill switch
        os.environ["LIFEOS_KILL_SWITCH"] = "1"
        try:
            result = gate.approve("to-block")
            assert result is False
        finally:
            del os.environ["LIFEOS_KILL_SWITCH"]

    def test_persistence(self, temp_dir):
        """Should persist and reload proposals."""
        gate1 = ApprovalGate(data_dir=temp_dir)
        proposal = TradeProposal(
            id="persist-test",
            symbol="SOL",
            side="BUY",
            size=10.0,
            price=150.0,
            strategy="test",
            reason="test"
        )

        with patch('subprocess.run'):
            gate1.submit_for_approval(proposal)

        # Create new gate (simulates restart)
        gate2 = ApprovalGate(data_dir=temp_dir)
        pending = gate2.get_pending()

        assert len(pending) == 1
        assert pending[0].id == "persist-test"


class TestKillSwitch:
    """Test kill switch functionality."""

    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for tests."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    def test_activate_kill_switch(self, temp_dir):
        """Should activate kill switch."""
        # Clean env
        if "LIFEOS_KILL_SWITCH" in os.environ:
            del os.environ["LIFEOS_KILL_SWITCH"]

        gate = ApprovalGate(data_dir=temp_dir)
        gate.kill_switch()  # Actual method name

        assert gate._kill_switch_active is True

    def test_deactivate_kill_switch(self, temp_dir):
        """Should deactivate kill switch."""
        gate = ApprovalGate(data_dir=temp_dir)
        gate.kill_switch()
        gate.reset_kill_switch(confirm="I_UNDERSTAND_THE_RISK")  # Requires confirmation

        assert gate._kill_switch_active is False

    def test_is_kill_switch_active(self, temp_dir):
        """Should report kill switch status."""
        gate = ApprovalGate(data_dir=temp_dir)
        assert gate.is_kill_switch_active() is False

        gate.kill_switch()
        assert gate.is_kill_switch_active() is True


class TestEdgeCases:
    """Test edge cases and error handling."""

    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for tests."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    def test_empty_symbol(self, temp_dir):
        """Should handle empty symbol."""
        gate = ApprovalGate(data_dir=temp_dir)
        proposal = TradeProposal(
            id="empty-symbol",
            symbol="",
            side="BUY",
            size=10.0,
            price=150.0,
            strategy="test",
            reason="test"
        )

        with patch('subprocess.run'):
            proposal_id = gate.submit_for_approval(proposal)

        assert proposal_id is not None

    def test_zero_size(self, temp_dir):
        """Should handle zero size."""
        gate = ApprovalGate(data_dir=temp_dir)
        proposal = TradeProposal(
            id="zero-size",
            symbol="SOL",
            side="BUY",
            size=0.0,
            price=150.0,
            strategy="test",
            reason="test"
        )

        with patch('subprocess.run'):
            proposal_id = gate.submit_for_approval(proposal)

        # Should still accept (validation might be elsewhere)
        assert proposal_id is not None

    def test_negative_price(self, temp_dir):
        """Should handle negative price."""
        gate = ApprovalGate(data_dir=temp_dir)
        proposal = TradeProposal(
            id="neg-price",
            symbol="SOL",
            side="BUY",
            size=10.0,
            price=-1.0,
            strategy="test",
            reason="test"
        )

        with patch('subprocess.run'):
            proposal_id = gate.submit_for_approval(proposal)

        assert proposal_id is not None

    def test_special_chars_in_reason(self, temp_dir):
        """Should handle special characters in reason."""
        gate = ApprovalGate(data_dir=temp_dir)
        proposal = TradeProposal(
            id="special-chars",
            symbol="SOL",
            side="BUY",
            size=10.0,
            price=150.0,
            strategy="test",
            reason='Test with "quotes" and $pecial ch@rs!'
        )

        with patch('subprocess.run'):
            proposal_id = gate.submit_for_approval(proposal)

        assert proposal_id is not None

    def test_unicode_in_fields(self, temp_dir):
        """Should handle unicode in fields."""
        gate = ApprovalGate(data_dir=temp_dir)
        proposal = TradeProposal(
            id="unicode-test",
            symbol="SOL",
            side="BUY",
            size=10.0,
            price=150.0,
            strategy="日本語テスト",
            reason="Bullish 🚀 momentum"
        )

        with patch('subprocess.run'):
            proposal_id = gate.submit_for_approval(proposal)

        # Should persist and reload correctly
        gate2 = ApprovalGate(data_dir=temp_dir)
        pending = gate2.get_pending()
        assert len(pending) == 1
        assert "🚀" in pending[0].reason

