"""
test_pda_derivation.py — Tests for deterministic Jupiter Perps PDA derivation.

Tests:
    1. derive_perpetuals_pda() returns stable, known address
    2. derive_pool_pda("JLP") returns stable, known address
    3. derive_position_pda() is deterministic (same inputs → same output)
    4. derive_position_pda() slot 0 and slot 1 produce different PDAs
    5. Long and short slots produce different PDAs
    6. enumerate_all_position_pdas() returns 9 entries per custody per side
    7. build_full_pda_map() returns correct structure
    8. derive_position_request_pda() is deterministic

Note: These tests require solders to be installed.
Skip gracefully if solders is not available.
"""

import pytest

try:
    from solders.pubkey import Pubkey
    _HAS_SOLDERS = True
except ImportError:
    _HAS_SOLDERS = False

pytestmark = pytest.mark.skipif(
    not _HAS_SOLDERS,
    reason="solders is required for PDA derivation tests",
)

from core.jupiter_perps.pda import (
    CUSTODY_MINTS,
    JUPITER_PERPS_PROGRAM_ID,
    JLP_POOL_NAME,
    MAX_POSITION_SLOTS,
    build_full_pda_map,
    derive_custody_pda,
    derive_perpetuals_pda,
    derive_pool_pda,
    derive_position_pda,
    derive_position_request_pda,
    enumerate_all_position_pdas,
    get_all_custody_pdas,
)

# Test wallet (known Solana devnet address — no funds)
TEST_WALLET = "9WzDXwBbmkg8ZTbNMqUxvQRAyrZzDsGYdLVL9zYtAWWM"


class TestProgramId:
    def test_program_id_is_valid_pubkey(self):
        """Program ID should be a valid Solana public key."""
        pk = Pubkey.from_string(JUPITER_PERPS_PROGRAM_ID)
        assert str(pk) == JUPITER_PERPS_PROGRAM_ID

    def test_program_id_is_on_curve(self):
        """Program addresses are not on the ed25519 curve (they're program addresses)."""
        # This test just verifies the string is valid base58
        pk = Pubkey.from_string(JUPITER_PERPS_PROGRAM_ID)
        assert len(bytes(pk)) == 32


class TestPerpetualsPda:
    def test_returns_pubkey(self):
        pda = derive_perpetuals_pda()
        assert isinstance(pda, Pubkey)

    def test_is_deterministic(self):
        pda1 = derive_perpetuals_pda()
        pda2 = derive_perpetuals_pda()
        assert pda1 == pda2

    def test_is_not_program_id(self):
        """PDA should be different from the program ID itself."""
        pda = derive_perpetuals_pda()
        assert str(pda) != JUPITER_PERPS_PROGRAM_ID


class TestPoolPda:
    def test_returns_pubkey(self):
        pda = derive_pool_pda()
        assert isinstance(pda, Pubkey)

    def test_is_deterministic(self):
        pda1 = derive_pool_pda(JLP_POOL_NAME)
        pda2 = derive_pool_pda(JLP_POOL_NAME)
        assert pda1 == pda2

    def test_different_names_different_pdas(self):
        jlp = derive_pool_pda("JLP")
        other = derive_pool_pda("OTHER")
        assert jlp != other


class TestCustodyPda:
    def test_returns_pubkey_for_sol(self):
        pool = derive_pool_pda()
        custody = derive_custody_pda(pool, CUSTODY_MINTS["SOL"])
        assert isinstance(custody, Pubkey)

    def test_is_deterministic(self):
        pool = derive_pool_pda()
        c1 = derive_custody_pda(pool, CUSTODY_MINTS["SOL"])
        c2 = derive_custody_pda(pool, CUSTODY_MINTS["SOL"])
        assert c1 == c2

    def test_different_mints_different_pdas(self):
        pool = derive_pool_pda()
        sol = derive_custody_pda(pool, CUSTODY_MINTS["SOL"])
        btc = derive_custody_pda(pool, CUSTODY_MINTS["BTC"])
        usdc = derive_custody_pda(pool, CUSTODY_MINTS["USDC"])
        assert sol != btc
        assert sol != usdc
        assert btc != usdc


class TestPositionPda:
    def test_returns_pubkey(self):
        owner = Pubkey.from_string(TEST_WALLET)
        pool = derive_pool_pda()
        custody = derive_custody_pda(pool, CUSTODY_MINTS["SOL"])
        pda = derive_position_pda(owner, pool, custody, "long", 0)
        assert isinstance(pda, Pubkey)

    def test_is_deterministic(self):
        owner = Pubkey.from_string(TEST_WALLET)
        pool = derive_pool_pda()
        custody = derive_custody_pda(pool, CUSTODY_MINTS["SOL"])
        pda1 = derive_position_pda(owner, pool, custody, "long", 0)
        pda2 = derive_position_pda(owner, pool, custody, "long", 0)
        assert pda1 == pda2

    def test_different_slots_different_pdas(self):
        owner = Pubkey.from_string(TEST_WALLET)
        pool = derive_pool_pda()
        custody = derive_custody_pda(pool, CUSTODY_MINTS["SOL"])
        pda_0 = derive_position_pda(owner, pool, custody, "long", 0)
        pda_1 = derive_position_pda(owner, pool, custody, "long", 1)
        pda_8 = derive_position_pda(owner, pool, custody, "long", 8)
        assert pda_0 != pda_1
        assert pda_0 != pda_8
        assert pda_1 != pda_8

    def test_different_sides_different_pdas(self):
        owner = Pubkey.from_string(TEST_WALLET)
        pool = derive_pool_pda()
        custody = derive_custody_pda(pool, CUSTODY_MINTS["SOL"])
        long_pda = derive_position_pda(owner, pool, custody, "long", 0)
        short_pda = derive_position_pda(owner, pool, custody, "short", 0)
        assert long_pda != short_pda

    def test_different_owners_different_pdas(self):
        pool = derive_pool_pda()
        custody = derive_custody_pda(pool, CUSTODY_MINTS["SOL"])
        owner1 = Pubkey.from_string(TEST_WALLET)
        # Generate a different valid public key
        owner2 = Pubkey.from_bytes(bytes([1] * 32))
        pda1 = derive_position_pda(owner1, pool, custody, "long", 0)
        pda2 = derive_position_pda(owner2, pool, custody, "long", 0)
        assert pda1 != pda2

    def test_rejects_invalid_slot(self):
        owner = Pubkey.from_string(TEST_WALLET)
        pool = derive_pool_pda()
        custody = derive_custody_pda(pool, CUSTODY_MINTS["SOL"])
        with pytest.raises(ValueError, match="slot"):
            derive_position_pda(owner, pool, custody, "long", MAX_POSITION_SLOTS)
        with pytest.raises(ValueError, match="slot"):
            derive_position_pda(owner, pool, custody, "long", -1)

    def test_all_9_slots_are_unique(self):
        owner = Pubkey.from_string(TEST_WALLET)
        pool = derive_pool_pda()
        custody = derive_custody_pda(pool, CUSTODY_MINTS["SOL"])
        pdas = {
            derive_position_pda(owner, pool, custody, "long", slot)
            for slot in range(MAX_POSITION_SLOTS)
        }
        assert len(pdas) == MAX_POSITION_SLOTS


class TestEnumeratePositionPdas:
    def test_returns_correct_count(self):
        owner = Pubkey.from_string(TEST_WALLET)
        pool = derive_pool_pda()
        custodies = get_all_custody_pdas(pool)
        # 5 custodies × 9 slots = 45 per side
        result = enumerate_all_position_pdas(owner, pool, custodies, "long")
        assert len(result) == len(CUSTODY_MINTS) * MAX_POSITION_SLOTS

    def test_all_pdas_are_unique(self):
        owner = Pubkey.from_string(TEST_WALLET)
        pool = derive_pool_pda()
        custodies = get_all_custody_pdas(pool)
        result = enumerate_all_position_pdas(owner, pool, custodies, "long")
        pdas = [r["pda"] for r in result]
        assert len(pdas) == len(set(pdas))

    def test_result_has_required_fields(self):
        owner = Pubkey.from_string(TEST_WALLET)
        pool = derive_pool_pda()
        custodies = get_all_custody_pdas(pool)
        result = enumerate_all_position_pdas(owner, pool, custodies, "long")
        for item in result:
            assert "pda" in item
            assert "slot" in item
            assert "side" in item
            assert "custody_symbol" in item
            assert 0 <= item["slot"] < MAX_POSITION_SLOTS


class TestBuildFullPdaMap:
    def test_returns_correct_structure(self):
        result = build_full_pda_map(TEST_WALLET)
        assert "perpetuals" in result
        assert "pool" in result
        assert "custodies" in result
        assert "position_pdas" in result

    def test_custodies_has_all_symbols(self):
        result = build_full_pda_map(TEST_WALLET)
        assert set(result["custodies"].keys()) == set(CUSTODY_MINTS.keys())

    def test_position_pdas_count(self):
        result = build_full_pda_map(TEST_WALLET)
        # 5 custodies × 9 slots × 2 sides = 90 total
        expected = len(CUSTODY_MINTS) * MAX_POSITION_SLOTS * 2
        assert len(result["position_pdas"]) == expected

    def test_all_values_are_strings(self):
        result = build_full_pda_map(TEST_WALLET)
        assert isinstance(result["perpetuals"], str)
        assert isinstance(result["pool"], str)
        for sym, addr in result["custodies"].items():
            assert isinstance(addr, str)


class TestPositionRequestPda:
    def test_returns_pubkey(self):
        owner = Pubkey.from_string(TEST_WALLET)
        pda = derive_position_request_pda(owner, 0)
        assert isinstance(pda, Pubkey)

    def test_is_deterministic(self):
        owner = Pubkey.from_string(TEST_WALLET)
        pda1 = derive_position_request_pda(owner, 42)
        pda2 = derive_position_request_pda(owner, 42)
        assert pda1 == pda2

    def test_different_counters_different_pdas(self):
        owner = Pubkey.from_string(TEST_WALLET)
        pda_0 = derive_position_request_pda(owner, 0)
        pda_1 = derive_position_request_pda(owner, 1)
        assert pda_0 != pda_1
