"""Tests for core.data.asset_registry — Asset Universe Registry."""

import json
import tempfile
from datetime import datetime, timezone, timedelta
from pathlib import Path

import pytest

from core.data.asset_registry import (
    AssetClass,
    AssetRecord,
    AssetRegistry,
    AssetStatus,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def tmp_registry(tmp_path: Path) -> AssetRegistry:
    """Return a registry backed by a temp file."""
    return AssetRegistry(path=tmp_path / "registry.json")


def _sol_record(**overrides) -> AssetRecord:
    defaults = dict(
        mint_address="So11111111111111111111111111111111111111112",
        symbol="SOL",
        asset_class=AssetClass.NATIVE_SOLANA,
        status=AssetStatus.ACTIVE,
        listing_date=datetime(2020, 4, 10, tzinfo=timezone.utc),
    )
    defaults.update(overrides)
    return AssetRecord(**defaults)


def _bags_record(**overrides) -> AssetRecord:
    defaults = dict(
        mint_address="BAGS_TOKEN_MINT_123",
        symbol="BAGTEST",
        asset_class=AssetClass.BAGS_BONDING_CURVE,
        status=AssetStatus.ACTIVE,
        listing_date=datetime(2025, 12, 1, tzinfo=timezone.utc),
        creator_address="CREATOR_WALLET_XYZ",
        bags_creator_fee_pct=1.0,
    )
    defaults.update(overrides)
    return AssetRecord(**defaults)


def _xstock_record(**overrides) -> AssetRecord:
    defaults = dict(
        mint_address="TSLA_XSTOCK_MINT_456",
        symbol="TSLAx",
        asset_class=AssetClass.XSTOCK,
        status=AssetStatus.ACTIVE,
        listing_date=datetime(2025, 6, 30, tzinfo=timezone.utc),
        underlying_ticker="TSLA",
    )
    defaults.update(overrides)
    return AssetRecord(**defaults)


# ---------------------------------------------------------------------------
# AssetRecord unit tests
# ---------------------------------------------------------------------------

class TestAssetRecord:

    def test_is_tradeable_at_active(self):
        rec = _sol_record()
        assert rec.is_tradeable_at(datetime(2025, 1, 1, tzinfo=timezone.utc))

    def test_is_tradeable_at_before_listing(self):
        rec = _sol_record()
        assert not rec.is_tradeable_at(datetime(2019, 1, 1, tzinfo=timezone.utc))

    def test_is_tradeable_at_after_delist(self):
        rec = _sol_record(
            status=AssetStatus.DELISTED,
            delisted_date=datetime(2025, 6, 1, tzinfo=timezone.utc),
        )
        assert rec.is_tradeable_at(datetime(2025, 5, 1, tzinfo=timezone.utc))
        assert not rec.is_tradeable_at(datetime(2025, 7, 1, tzinfo=timezone.utc))

    def test_is_tradeable_at_rugged(self):
        rec = _sol_record(
            status=AssetStatus.RUGGED,
            rugged_date=datetime(2025, 3, 15, tzinfo=timezone.utc),
        )
        assert not rec.is_tradeable_at(datetime(2025, 4, 1, tzinfo=timezone.utc))
        assert rec.is_tradeable_at(datetime(2025, 3, 1, tzinfo=timezone.utc))

    def test_dead_without_date_never_tradeable(self):
        rec = _sol_record(status=AssetStatus.DEAD)
        assert not rec.is_tradeable_at(datetime(2025, 1, 1, tzinfo=timezone.utc))

    def test_is_bags_token(self):
        assert _bags_record().is_bags_token()
        assert not _sol_record().is_bags_token()

    def test_is_xstock(self):
        assert _xstock_record().is_xstock()
        assert not _sol_record().is_xstock()

    def test_round_trip_creator_fee(self):
        rec = _bags_record(bags_creator_fee_pct=1.0)
        assert rec.round_trip_creator_fee_pct() == 2.0

    def test_serialization_round_trip(self):
        rec = _bags_record()
        d = rec.to_dict()
        restored = AssetRecord.from_dict(d)
        assert restored.mint_address == rec.mint_address
        assert restored.asset_class == rec.asset_class
        assert restored.status == rec.status
        assert restored.bags_creator_fee_pct == 1.0

    def test_enum_from_string(self):
        """AssetRecord.__post_init__ coerces string values to enums."""
        rec = AssetRecord(
            mint_address="TEST",
            symbol="T",
            asset_class="native_solana",
            status="active",
            listing_date="2025-01-01T00:00:00+00:00",
        )
        assert rec.asset_class == AssetClass.NATIVE_SOLANA
        assert rec.status == AssetStatus.ACTIVE
        assert isinstance(rec.listing_date, datetime)


# ---------------------------------------------------------------------------
# AssetRegistry tests
# ---------------------------------------------------------------------------

class TestAssetRegistry:

    def test_register_and_get(self, tmp_registry: AssetRegistry):
        rec = _sol_record()
        tmp_registry.register(rec)
        assert tmp_registry.get(rec.mint_address) is rec
        assert tmp_registry.count == 1

    def test_persistence(self, tmp_path: Path):
        path = tmp_path / "reg.json"
        reg1 = AssetRegistry(path=path)
        reg1.register(_sol_record())
        reg1.register(_bags_record())

        # Load into a new instance
        reg2 = AssetRegistry(path=path)
        assert reg2.count == 2
        assert reg2.get("So11111111111111111111111111111111111111112") is not None
        assert reg2.get("BAGS_TOKEN_MINT_123") is not None

    def test_get_active(self, tmp_registry: AssetRegistry):
        tmp_registry.register(_sol_record(), persist=False)
        tmp_registry.register(
            _bags_record(status=AssetStatus.RUGGED, rugged_date=datetime(2025, 12, 5, tzinfo=timezone.utc)),
            persist=False,
        )
        active = tmp_registry.get_active()
        assert len(active) == 1
        assert active[0].symbol == "SOL"

    def test_get_universe_at_date(self, tmp_registry: AssetRegistry):
        """Core survivorship-bias-free query."""
        sol = _sol_record()
        bags = _bags_record()
        rugged = _bags_record(
            mint_address="RUGGED_MINT",
            symbol="RUGTOKEN",
            status=AssetStatus.RUGGED,
            listing_date=datetime(2025, 10, 1, tzinfo=timezone.utc),
            rugged_date=datetime(2025, 11, 1, tzinfo=timezone.utc),
        )
        future = _xstock_record(
            listing_date=datetime(2026, 6, 1, tzinfo=timezone.utc),
        )

        for rec in [sol, bags, rugged, future]:
            tmp_registry.register(rec, persist=False)

        # Query at a date where SOL, BAGS, and RUGGED were all tradeable
        dt = datetime(2025, 10, 15, tzinfo=timezone.utc)
        universe = tmp_registry.get_universe_at_date(dt)
        symbols = {r.symbol for r in universe}
        assert "SOL" in symbols
        assert "RUGTOKEN" in symbols       # Was still alive on Oct 15
        assert "BAGTEST" not in symbols    # Not listed until Dec 1
        assert "TSLAx" not in symbols      # Not listed until Jun 2026

        # Query after rug date
        dt2 = datetime(2025, 12, 15, tzinfo=timezone.utc)
        universe2 = tmp_registry.get_universe_at_date(dt2)
        symbols2 = {r.symbol for r in universe2}
        assert "RUGTOKEN" not in symbols2  # Rugged by now
        assert "BAGTEST" in symbols2       # Listed Dec 1

    def test_update_status_graduation(self, tmp_registry: AssetRegistry):
        bags = _bags_record()
        tmp_registry.register(bags, persist=False)

        success = tmp_registry.update_status(
            bags.mint_address,
            AssetStatus.GRADUATED,
            event_date=datetime(2026, 1, 15, tzinfo=timezone.utc),
            notes="graduated to Raydium",
        )
        assert success

        updated = tmp_registry.get(bags.mint_address)
        assert updated is not None
        assert updated.status == AssetStatus.GRADUATED
        assert updated.asset_class == AssetClass.BAGS_GRADUATED
        assert updated.graduation_date == datetime(2026, 1, 15, tzinfo=timezone.utc)
        assert "graduated to Raydium" in updated.notes

    def test_update_status_unknown_mint(self, tmp_registry: AssetRegistry):
        assert not tmp_registry.update_status("NONEXISTENT", AssetStatus.DEAD)

    def test_bulk_register(self, tmp_registry: AssetRegistry):
        records = [_sol_record(), _bags_record(), _xstock_record()]
        tmp_registry.bulk_register(records)
        assert tmp_registry.count == 3

    def test_search(self, tmp_registry: AssetRegistry):
        tmp_registry.bulk_register([_sol_record(), _bags_record(), _xstock_record()])

        assert len(tmp_registry.search(symbol="SOL")) == 1
        assert len(tmp_registry.search(asset_class=AssetClass.XSTOCK)) == 1
        assert len(tmp_registry.search(status=AssetStatus.ACTIVE)) == 3
        assert len(tmp_registry.search(predicate=lambda r: r.is_bags_token())) == 1

    def test_get_bags_tokens(self, tmp_registry: AssetRegistry):
        tmp_registry.bulk_register([_sol_record(), _bags_record(), _xstock_record()])
        bags = tmp_registry.get_bags_tokens()
        assert len(bags) == 1
        assert bags[0].symbol == "BAGTEST"

    def test_get_xstocks(self, tmp_registry: AssetRegistry):
        tmp_registry.bulk_register([_sol_record(), _bags_record(), _xstock_record()])
        xstocks = tmp_registry.get_xstocks()
        assert len(xstocks) == 1
        assert xstocks[0].underlying_ticker == "TSLA"

    def test_get_backtest_eligible(self, tmp_registry: AssetRegistry):
        eligible = _sol_record(has_reliable_ohlcv=True, min_candles_available=2000)
        ineligible = _bags_record(has_reliable_ohlcv=False, min_candles_available=50)
        tmp_registry.bulk_register([eligible, ineligible])

        results = tmp_registry.get_backtest_eligible(
            start_date=datetime(2021, 1, 1, tzinfo=timezone.utc),
            end_date=datetime(2025, 12, 1, tzinfo=timezone.utc),
        )
        assert len(results) == 1
        assert results[0].symbol == "SOL"

    def test_summary(self, tmp_registry: AssetRegistry):
        tmp_registry.bulk_register([_sol_record(), _bags_record(), _xstock_record()])
        s = tmp_registry.summary()
        assert s["total"] == 3
        assert s["by_class"]["native_solana"] == 1
        assert s["by_status"]["active"] == 3

    def test_remove(self, tmp_registry: AssetRegistry):
        tmp_registry.register(_sol_record(), persist=False)
        assert tmp_registry.count == 1
        assert tmp_registry.remove("So11111111111111111111111111111111111111112")
        assert tmp_registry.count == 0
        assert not tmp_registry.remove("NONEXISTENT")

    def test_json_file_structure(self, tmp_path: Path):
        path = tmp_path / "reg.json"
        reg = AssetRegistry(path=path)
        reg.register(_sol_record())

        raw = json.loads(path.read_text())
        assert raw["version"] == 1
        assert "updated_at" in raw
        assert raw["count"] == 1
        assert len(raw["assets"]) == 1
        assert raw["assets"][0]["symbol"] == "SOL"
