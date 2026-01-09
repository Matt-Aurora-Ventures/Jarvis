"""
Tests for lifeos/memory sandboxing system.

SECURITY CRITICAL: These tests verify isolation boundaries.

Tests cover:
- Context permission enforcement
- Trading isolation (CRITICAL)
- Audit logging
- TTL expiration
- Cross-context access prevention
"""

import asyncio
import sys
from datetime import timedelta
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from lifeos.memory import (
    MemoryContext,
    MemoryStore,
    MemoryAccessError,
    can_read,
    can_write,
    requires_audit,
)


# =============================================================================
# Test Context Permissions
# =============================================================================

class TestContextPermissions:
    """Test context permission definitions."""

    # TRADING ISOLATION TESTS (SECURITY CRITICAL)

    def test_trading_cannot_be_read_by_public(self):
        """CRITICAL: Public cannot read trading data."""
        assert not can_read(MemoryContext.PUBLIC, MemoryContext.TRADING)

    def test_trading_cannot_be_read_by_personal(self):
        """CRITICAL: Personal cannot read trading data."""
        assert not can_read(MemoryContext.PERSONAL, MemoryContext.TRADING)

    def test_trading_cannot_be_read_by_system(self):
        """CRITICAL: Even system cannot read trading data."""
        assert not can_read(MemoryContext.SYSTEM, MemoryContext.TRADING)

    def test_trading_can_only_read_itself(self):
        """Trading can only read its own data."""
        assert can_read(MemoryContext.TRADING, MemoryContext.TRADING)

    def test_trading_cannot_be_written_by_others(self):
        """CRITICAL: Only trading can write to trading."""
        assert not can_write(MemoryContext.PUBLIC, MemoryContext.TRADING)
        assert not can_write(MemoryContext.PERSONAL, MemoryContext.TRADING)
        assert not can_write(MemoryContext.SYSTEM, MemoryContext.TRADING)
        assert can_write(MemoryContext.TRADING, MemoryContext.TRADING)

    # PERSONAL PROTECTION TESTS

    def test_personal_cannot_be_read_by_public(self):
        """Public cannot read personal data."""
        assert not can_read(MemoryContext.PUBLIC, MemoryContext.PERSONAL)

    def test_personal_cannot_be_read_by_trading(self):
        """Trading cannot read personal data."""
        assert not can_read(MemoryContext.TRADING, MemoryContext.PERSONAL)

    def test_personal_can_be_read_by_system(self):
        """System can read personal data (for backup, etc)."""
        assert can_read(MemoryContext.SYSTEM, MemoryContext.PERSONAL)

    def test_personal_can_only_write_to_itself(self):
        """Only personal can write to personal."""
        assert can_write(MemoryContext.PERSONAL, MemoryContext.PERSONAL)
        assert not can_write(MemoryContext.PUBLIC, MemoryContext.PERSONAL)
        assert not can_write(MemoryContext.TRADING, MemoryContext.PERSONAL)

    # SYSTEM PROTECTION TESTS

    def test_system_can_only_be_written_by_system(self):
        """Only system can write to system."""
        assert can_write(MemoryContext.SYSTEM, MemoryContext.SYSTEM)
        assert not can_write(MemoryContext.PUBLIC, MemoryContext.SYSTEM)
        assert not can_write(MemoryContext.PERSONAL, MemoryContext.SYSTEM)
        assert not can_write(MemoryContext.TRADING, MemoryContext.SYSTEM)

    def test_system_readable_by_all(self):
        """System is readable by all contexts."""
        assert can_read(MemoryContext.PUBLIC, MemoryContext.SYSTEM)
        assert can_read(MemoryContext.PERSONAL, MemoryContext.SYSTEM)
        assert can_read(MemoryContext.TRADING, MemoryContext.SYSTEM)

    # PUBLIC ACCESS TESTS

    def test_public_readable_by_all(self):
        """Public is readable by all."""
        assert can_read(MemoryContext.PUBLIC, MemoryContext.PUBLIC)
        assert can_read(MemoryContext.TRADING, MemoryContext.PUBLIC)
        assert can_read(MemoryContext.PERSONAL, MemoryContext.PUBLIC)
        assert can_read(MemoryContext.SYSTEM, MemoryContext.PUBLIC)

    def test_public_writable_by_all(self):
        """Public is writable by all."""
        assert can_write(MemoryContext.PUBLIC, MemoryContext.PUBLIC)
        assert can_write(MemoryContext.TRADING, MemoryContext.PUBLIC)
        assert can_write(MemoryContext.PERSONAL, MemoryContext.PUBLIC)
        assert can_write(MemoryContext.SYSTEM, MemoryContext.PUBLIC)

    # AUDIT REQUIREMENTS

    def test_trading_requires_audit(self):
        """Trading access must be audited."""
        assert requires_audit(MemoryContext.TRADING)

    def test_personal_requires_audit(self):
        """Personal access must be audited."""
        assert requires_audit(MemoryContext.PERSONAL)

    def test_system_requires_audit(self):
        """System access must be audited."""
        assert requires_audit(MemoryContext.SYSTEM)

    def test_public_no_audit(self):
        """Public access doesn't require audit."""
        assert not requires_audit(MemoryContext.PUBLIC)


# =============================================================================
# Test Memory Store
# =============================================================================

class TestMemoryStore:
    """Test MemoryStore operations."""

    @pytest.fixture
    def store(self):
        """Create a fresh memory store."""
        return MemoryStore()

    # BASIC OPERATIONS

    @pytest.mark.asyncio
    async def test_set_and_get_public(self, store):
        """Should store and retrieve public data."""
        await store.set(
            key="test",
            value={"data": "value"},
            context=MemoryContext.PUBLIC,
            caller_context=MemoryContext.PUBLIC,
        )

        result = await store.get(
            key="test",
            context=MemoryContext.PUBLIC,
            caller_context=MemoryContext.PUBLIC,
        )

        assert result == {"data": "value"}

    @pytest.mark.asyncio
    async def test_get_nonexistent_returns_default(self, store):
        """Should return default for missing key."""
        result = await store.get(
            key="missing",
            context=MemoryContext.PUBLIC,
            caller_context=MemoryContext.PUBLIC,
            default="default_value",
        )

        assert result == "default_value"

    @pytest.mark.asyncio
    async def test_delete(self, store):
        """Should delete entries."""
        await store.set(
            key="to_delete",
            value="value",
            context=MemoryContext.PUBLIC,
            caller_context=MemoryContext.PUBLIC,
        )

        deleted = await store.delete(
            key="to_delete",
            context=MemoryContext.PUBLIC,
            caller_context=MemoryContext.PUBLIC,
        )

        assert deleted is True

        result = await store.get(
            key="to_delete",
            context=MemoryContext.PUBLIC,
            caller_context=MemoryContext.PUBLIC,
        )
        assert result is None

    @pytest.mark.asyncio
    async def test_exists(self, store):
        """Should check existence correctly."""
        await store.set(
            key="exists",
            value="yes",
            context=MemoryContext.PUBLIC,
            caller_context=MemoryContext.PUBLIC,
        )

        assert await store.exists(
            "exists",
            MemoryContext.PUBLIC,
            MemoryContext.PUBLIC,
        )
        assert not await store.exists(
            "not_exists",
            MemoryContext.PUBLIC,
            MemoryContext.PUBLIC,
        )

    @pytest.mark.asyncio
    async def test_keys(self, store):
        """Should list keys."""
        await store.set("key1", "v1", MemoryContext.PUBLIC, MemoryContext.PUBLIC)
        await store.set("key2", "v2", MemoryContext.PUBLIC, MemoryContext.PUBLIC)
        await store.set("other", "v3", MemoryContext.PUBLIC, MemoryContext.PUBLIC)

        all_keys = await store.keys(MemoryContext.PUBLIC, MemoryContext.PUBLIC)
        assert len(all_keys) == 3

        filtered = await store.keys(
            MemoryContext.PUBLIC,
            MemoryContext.PUBLIC,
            pattern="key",
        )
        assert len(filtered) == 2

    # SECURITY BOUNDARY TESTS (CRITICAL)

    @pytest.mark.asyncio
    async def test_trading_isolation_read(self, store):
        """CRITICAL: Public cannot read trading data."""
        # Store trading data
        await store.set(
            key="secret_position",
            value={"symbol": "SOL", "amount": 1000},
            context=MemoryContext.TRADING,
            caller_context=MemoryContext.TRADING,
        )

        # Attempt to read from public context
        with pytest.raises(MemoryAccessError) as exc_info:
            await store.get(
                key="secret_position",
                context=MemoryContext.TRADING,
                caller_context=MemoryContext.PUBLIC,
            )

        assert exc_info.value.context == MemoryContext.TRADING
        assert exc_info.value.caller_context == MemoryContext.PUBLIC

    @pytest.mark.asyncio
    async def test_trading_isolation_write(self, store):
        """CRITICAL: Public cannot write to trading."""
        with pytest.raises(MemoryAccessError):
            await store.set(
                key="malicious",
                value={"hack": "attempt"},
                context=MemoryContext.TRADING,
                caller_context=MemoryContext.PUBLIC,
            )

    @pytest.mark.asyncio
    async def test_personal_isolation_from_trading(self, store):
        """Trading cannot access personal data."""
        await store.set(
            key="personal_info",
            value={"name": "John"},
            context=MemoryContext.PERSONAL,
            caller_context=MemoryContext.PERSONAL,
        )

        with pytest.raises(MemoryAccessError):
            await store.get(
                key="personal_info",
                context=MemoryContext.PERSONAL,
                caller_context=MemoryContext.TRADING,
            )

    @pytest.mark.asyncio
    async def test_system_write_protection(self, store):
        """Non-system contexts cannot write to system."""
        with pytest.raises(MemoryAccessError):
            await store.set(
                key="config",
                value={"malicious": True},
                context=MemoryContext.SYSTEM,
                caller_context=MemoryContext.PUBLIC,
            )

    @pytest.mark.asyncio
    async def test_cross_context_audit_logging(self, store):
        """Failed access attempts should be logged."""
        # Attempt forbidden access
        try:
            await store.get(
                key="secret",
                context=MemoryContext.TRADING,
                caller_context=MemoryContext.PUBLIC,
            )
        except MemoryAccessError:
            pass

        # Check audit log
        audit = store.get_audit_log(context=MemoryContext.TRADING)
        assert len(audit) > 0
        assert audit[-1]["success"] is False
        assert audit[-1]["caller_context"] == "public"

    # TTL TESTS

    @pytest.mark.asyncio
    async def test_ttl_expiration(self, store):
        """Entries should expire after TTL."""
        await store.set(
            key="expires",
            value="soon",
            context=MemoryContext.SCRATCH,
            caller_context=MemoryContext.SCRATCH,
            ttl=timedelta(milliseconds=1),  # Expire immediately
        )

        await asyncio.sleep(0.01)  # Wait for expiration

        result = await store.get(
            key="expires",
            context=MemoryContext.SCRATCH,
            caller_context=MemoryContext.SCRATCH,
        )
        assert result is None

    @pytest.mark.asyncio
    async def test_ttl_capped_to_max(self, store):
        """TTL should be capped to context max."""
        # Trading max TTL is 1 day
        await store.set(
            key="test",
            value="data",
            context=MemoryContext.TRADING,
            caller_context=MemoryContext.TRADING,
            ttl=timedelta(days=365),  # Try to set 1 year
        )

        # Entry should exist (TTL was capped, not rejected)
        assert await store.exists(
            "test",
            MemoryContext.TRADING,
            MemoryContext.TRADING,
        )

    @pytest.mark.asyncio
    async def test_cleanup_expired(self, store):
        """Cleanup should remove expired entries."""
        await store.set(
            key="expired1",
            value="data",
            context=MemoryContext.PUBLIC,
            caller_context=MemoryContext.PUBLIC,
            ttl=timedelta(milliseconds=1),
        )

        await asyncio.sleep(0.01)

        removed = await store.cleanup_expired()
        assert removed >= 1

    # CLEAR CONTEXT TESTS

    @pytest.mark.asyncio
    async def test_clear_context(self, store):
        """Should clear all entries in a context."""
        await store.set("a", "1", MemoryContext.PUBLIC, MemoryContext.PUBLIC)
        await store.set("b", "2", MemoryContext.PUBLIC, MemoryContext.PUBLIC)

        count = await store.clear_context(
            MemoryContext.PUBLIC,
            MemoryContext.PUBLIC,
        )

        assert count == 2

        keys = await store.keys(MemoryContext.PUBLIC, MemoryContext.PUBLIC)
        assert len(keys) == 0

    @pytest.mark.asyncio
    async def test_clear_context_permission(self, store):
        """Should enforce permissions for clear."""
        with pytest.raises(MemoryAccessError):
            await store.clear_context(
                MemoryContext.TRADING,
                MemoryContext.PUBLIC,
            )

    # STATS TESTS

    def test_get_stats(self, store):
        """Should return store statistics."""
        stats = store.get_stats()

        assert "contexts" in stats
        assert "total_entries" in stats
        assert "audit_log_size" in stats
        assert MemoryContext.TRADING.value in stats["contexts"]


# =============================================================================
# Test Complete Isolation Scenarios
# =============================================================================

class TestIsolationScenarios:
    """Test complex isolation scenarios."""

    @pytest.fixture
    def store(self):
        return MemoryStore()

    @pytest.mark.asyncio
    async def test_trading_workflow_isolated(self, store):
        """
        CRITICAL: Full trading workflow should be isolated.

        Simulates a trading bot storing sensitive data.
        """
        # Trading bot stores position
        await store.set(
            key="position:SOL",
            value={"amount": 1000, "entry_price": 100.5},
            context=MemoryContext.TRADING,
            caller_context=MemoryContext.TRADING,
        )

        # Trading bot stores API keys (encrypted in real use)
        await store.set(
            key="api:binance",
            value={"key": "secret123"},
            context=MemoryContext.TRADING,
            caller_context=MemoryContext.TRADING,
        )

        # Trading can read its own data
        position = await store.get(
            "position:SOL",
            MemoryContext.TRADING,
            MemoryContext.TRADING,
        )
        assert position["amount"] == 1000

        # Public chatbot CANNOT access any trading data
        for key in ["position:SOL", "api:binance"]:
            with pytest.raises(MemoryAccessError):
                await store.get(
                    key,
                    MemoryContext.TRADING,
                    MemoryContext.PUBLIC,
                )

        # Personal context CANNOT access trading data
        with pytest.raises(MemoryAccessError):
            await store.get(
                "position:SOL",
                MemoryContext.TRADING,
                MemoryContext.PERSONAL,
            )

    @pytest.mark.asyncio
    async def test_contexts_share_public_data(self, store):
        """All contexts can share data via PUBLIC."""
        # Trading stores public info
        await store.set(
            key="market:SOL:price",
            value=100.5,
            context=MemoryContext.PUBLIC,
            caller_context=MemoryContext.TRADING,
        )

        # Personal can read it
        price = await store.get(
            "market:SOL:price",
            MemoryContext.PUBLIC,
            MemoryContext.PERSONAL,
        )
        assert price == 100.5

        # System can read it
        price = await store.get(
            "market:SOL:price",
            MemoryContext.PUBLIC,
            MemoryContext.SYSTEM,
        )
        assert price == 100.5
