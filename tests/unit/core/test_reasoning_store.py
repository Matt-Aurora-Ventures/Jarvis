"""
Tests for Reasoning Chain Storage

These tests verify:
1. Storage of debate reasoning chains for compliance
2. Retrieval and querying of past debates
3. Reasoning chain serialization
4. Performance tracking from stored decisions
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime, timedelta
import json
import tempfile
from pathlib import Path


class TestReasoningStore:
    """Test reasoning chain storage."""

    def test_store_reasoning_chain(self):
        """Should store a complete reasoning chain."""
        from core.reasoning_store import ReasoningStore

        with tempfile.TemporaryDirectory() as tmpdir:
            store = ReasoningStore(data_dir=tmpdir)

            chain = {
                "debate_id": "debate_123",
                "symbol": "BONK",
                "timestamp": datetime.utcnow().isoformat(),
                "bull_case": "Strong momentum",
                "bear_case": "Risk of reversal",
                "synthesis": "Proceed with caution",
                "recommendation": "BUY",
                "confidence": 72.0,
                "signal_context": {"direction": "BUY", "rsi": 35},
            }

            result = store.store(chain)

            assert result.success is True
            assert result.chain_id is not None

    def test_retrieve_reasoning_chain(self):
        """Should retrieve a stored reasoning chain by ID."""
        from core.reasoning_store import ReasoningStore

        with tempfile.TemporaryDirectory() as tmpdir:
            store = ReasoningStore(data_dir=tmpdir)

            chain = {
                "debate_id": "debate_456",
                "symbol": "WIF",
                "recommendation": "SELL",
                "confidence": 65.0,
            }

            result = store.store(chain)
            chain_id = result.chain_id

            retrieved = store.get(chain_id)

            assert retrieved is not None
            assert retrieved["symbol"] == "WIF"
            assert retrieved["recommendation"] == "SELL"

    def test_query_by_symbol(self):
        """Should query reasoning chains by token symbol."""
        from core.reasoning_store import ReasoningStore

        with tempfile.TemporaryDirectory() as tmpdir:
            store = ReasoningStore(data_dir=tmpdir)

            # Store multiple chains
            store.store({"debate_id": "d1", "symbol": "BONK", "recommendation": "BUY"})
            store.store({"debate_id": "d2", "symbol": "WIF", "recommendation": "SELL"})
            store.store({"debate_id": "d3", "symbol": "BONK", "recommendation": "HOLD"})

            bonk_chains = store.query(symbol="BONK")

            assert len(bonk_chains) == 2
            assert all(c["symbol"] == "BONK" for c in bonk_chains)

    def test_query_by_date_range(self):
        """Should query reasoning chains by date range."""
        from core.reasoning_store import ReasoningStore

        with tempfile.TemporaryDirectory() as tmpdir:
            store = ReasoningStore(data_dir=tmpdir)

            now = datetime.utcnow()
            yesterday = now - timedelta(days=1)
            last_week = now - timedelta(days=7)

            store.store({
                "debate_id": "d1",
                "symbol": "BONK",
                "timestamp": now.isoformat(),
            })
            store.store({
                "debate_id": "d2",
                "symbol": "WIF",
                "timestamp": yesterday.isoformat(),
            })
            store.store({
                "debate_id": "d3",
                "symbol": "JUP",
                "timestamp": last_week.isoformat(),
            })

            # Query last 2 days
            recent = store.query(
                start_date=yesterday - timedelta(hours=1),
                end_date=now + timedelta(hours=1),
            )

            assert len(recent) == 2

    def test_query_by_recommendation(self):
        """Should query reasoning chains by recommendation type."""
        from core.reasoning_store import ReasoningStore

        with tempfile.TemporaryDirectory() as tmpdir:
            store = ReasoningStore(data_dir=tmpdir)

            store.store({"debate_id": "d1", "symbol": "A", "recommendation": "BUY"})
            store.store({"debate_id": "d2", "symbol": "B", "recommendation": "SELL"})
            store.store({"debate_id": "d3", "symbol": "C", "recommendation": "BUY"})

            buy_chains = store.query(recommendation="BUY")

            assert len(buy_chains) == 2


class TestReasoningChainFormat:
    """Test reasoning chain data format."""

    def test_reasoning_chain_schema(self):
        """Reasoning chain should follow expected schema."""
        from core.reasoning_store import ReasoningChain

        chain = ReasoningChain(
            debate_id="test_123",
            symbol="BONK",
            timestamp=datetime.utcnow(),
            market_data={"price": 0.00001234, "volume": 1500000},
            signal={"direction": "BUY", "confidence": 70},
            bull_case="Strong momentum and volume",
            bear_case="Overbought RSI",
            synthesis="Proceed with tight stop",
            recommendation="BUY",
            confidence=72.0,
            tokens_used=450,
            outcome=None,  # Filled in later
        )

        assert chain.debate_id == "test_123"
        assert chain.symbol == "BONK"
        assert chain.recommendation in ["BUY", "SELL", "HOLD"]

    def test_reasoning_chain_to_dict(self):
        """Reasoning chain should serialize to dict."""
        from core.reasoning_store import ReasoningChain

        chain = ReasoningChain(
            debate_id="test_456",
            symbol="WIF",
            timestamp=datetime.utcnow(),
            recommendation="HOLD",
            confidence=55.0,
        )

        data = chain.to_dict()

        assert data["debate_id"] == "test_456"
        assert data["symbol"] == "WIF"
        assert "timestamp" in data

    def test_reasoning_chain_from_dict(self):
        """Reasoning chain should deserialize from dict."""
        from core.reasoning_store import ReasoningChain

        data = {
            "debate_id": "test_789",
            "symbol": "JUP",
            "timestamp": datetime.utcnow().isoformat(),
            "recommendation": "SELL",
            "confidence": 68.0,
            "bull_case": "Some upside",
            "bear_case": "More downside",
        }

        chain = ReasoningChain.from_dict(data)

        assert chain.debate_id == "test_789"
        assert chain.recommendation == "SELL"


class TestOutcomeTracking:
    """Test decision outcome tracking."""

    def test_update_outcome(self):
        """Should update reasoning chain with actual outcome."""
        from core.reasoning_store import ReasoningStore

        with tempfile.TemporaryDirectory() as tmpdir:
            store = ReasoningStore(data_dir=tmpdir)

            result = store.store({
                "debate_id": "outcome_test",
                "symbol": "BONK",
                "recommendation": "BUY",
                "confidence": 75.0,
            })

            # Later, update with actual outcome
            updated = store.update_outcome(
                chain_id=result.chain_id,
                outcome={
                    "executed": True,
                    "entry_price": 0.00001234,
                    "exit_price": 0.00001500,
                    "pnl_pct": 21.5,
                    "was_correct": True,
                }
            )

            assert updated.success is True

            # Retrieve and verify outcome
            chain = store.get(result.chain_id)
            assert chain["outcome"]["pnl_pct"] == 21.5
            assert chain["outcome"]["was_correct"] is True

    def test_calculate_accuracy_stats(self):
        """Should calculate accuracy statistics from stored outcomes."""
        from core.reasoning_store import ReasoningStore

        with tempfile.TemporaryDirectory() as tmpdir:
            store = ReasoningStore(data_dir=tmpdir)

            # Store chains with outcomes
            for i, (rec, correct) in enumerate([
                ("BUY", True),
                ("BUY", True),
                ("BUY", False),
                ("SELL", True),
                ("HOLD", True),
            ]):
                result = store.store({
                    "debate_id": f"stats_{i}",
                    "symbol": "TEST",
                    "recommendation": rec,
                    "confidence": 70.0,
                })
                store.update_outcome(
                    result.chain_id,
                    {"was_correct": correct, "executed": rec != "HOLD"}
                )

            stats = store.get_accuracy_stats()

            assert stats["total_decisions"] == 5
            assert stats["buy_accuracy"] == 2/3  # 2 correct out of 3 BUY
            assert stats["overall_accuracy"] == 4/5  # 4 correct out of 5


class TestReasoningStorePersistence:
    """Test reasoning store persistence."""

    def test_persists_across_restarts(self):
        """Stored chains should persist across store restarts."""
        from core.reasoning_store import ReasoningStore

        with tempfile.TemporaryDirectory() as tmpdir:
            # First instance
            store1 = ReasoningStore(data_dir=tmpdir)
            result = store1.store({
                "debate_id": "persist_test",
                "symbol": "PERSIST",
                "recommendation": "BUY",
            })
            chain_id = result.chain_id

            # New instance (simulating restart)
            store2 = ReasoningStore(data_dir=tmpdir)
            chain = store2.get(chain_id)

            assert chain is not None
            assert chain["symbol"] == "PERSIST"

    def test_handles_corrupted_data(self):
        """Should handle corrupted data gracefully."""
        from core.reasoning_store import ReasoningStore

        with tempfile.TemporaryDirectory() as tmpdir:
            # Write corrupted data
            data_file = Path(tmpdir) / "reasoning_chains.jsonl"
            data_file.write_text("not valid json\n{also broken")

            # Should not crash, should log warning
            store = ReasoningStore(data_dir=tmpdir)
            chains = store.query()

            assert chains == []  # Empty due to corruption


class TestReasoningStoreExport:
    """Test reasoning store export functionality."""

    def test_export_to_json(self):
        """Should export all chains to JSON file."""
        from core.reasoning_store import ReasoningStore

        with tempfile.TemporaryDirectory() as tmpdir:
            store = ReasoningStore(data_dir=tmpdir)

            store.store({"debate_id": "e1", "symbol": "A", "recommendation": "BUY"})
            store.store({"debate_id": "e2", "symbol": "B", "recommendation": "SELL"})

            export_path = Path(tmpdir) / "export.json"
            store.export_json(str(export_path))

            assert export_path.exists()

            with open(export_path) as f:
                exported = json.load(f)

            assert len(exported) == 2

    def test_export_filtered_to_csv(self):
        """Should export filtered chains to CSV for analysis."""
        from core.reasoning_store import ReasoningStore

        with tempfile.TemporaryDirectory() as tmpdir:
            store = ReasoningStore(data_dir=tmpdir)

            store.store({"debate_id": "c1", "symbol": "BONK", "recommendation": "BUY", "confidence": 75})
            store.store({"debate_id": "c2", "symbol": "WIF", "recommendation": "SELL", "confidence": 65})

            export_path = Path(tmpdir) / "export.csv"
            store.export_csv(str(export_path), columns=["symbol", "recommendation", "confidence"])

            assert export_path.exists()

            content = export_path.read_text()
            assert "BONK" in content
            assert "BUY" in content


class TestReasoningStoreCleanup:
    """Test reasoning store cleanup."""

    def test_cleanup_old_chains(self):
        """Should clean up chains older than retention period."""
        from core.reasoning_store import ReasoningStore

        with tempfile.TemporaryDirectory() as tmpdir:
            store = ReasoningStore(data_dir=tmpdir, retention_days=30)

            now = datetime.utcnow()
            old_date = now - timedelta(days=60)

            store.store({
                "debate_id": "old",
                "symbol": "OLD",
                "timestamp": old_date.isoformat(),
            })
            store.store({
                "debate_id": "new",
                "symbol": "NEW",
                "timestamp": now.isoformat(),
            })

            cleaned = store.cleanup_old()

            assert cleaned == 1  # One old chain removed

            remaining = store.query()
            assert len(remaining) == 1
            assert remaining[0]["symbol"] == "NEW"
