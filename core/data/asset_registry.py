"""
Asset Universe Registry — Single source of truth for all tradeable assets.

Tracks every asset ever scanned, including dead, rugged, delisted, and graduated
tokens. This eliminates survivorship bias in backtests by enabling point-in-time
universe queries via ``get_universe_at_date()``.

Persistence:
    - JSON file at ``data/trader/asset_registry.json`` (portable, survives restarts)
    - Optional TimescaleDB mirror for queryable analytics

Usage::

    from core.data.asset_registry import AssetRegistry, AssetClass, AssetStatus

    registry = AssetRegistry()
    registry.register(AssetRecord(
        mint_address="So11111111111111111111111111111111111111112",
        symbol="SOL",
        asset_class=AssetClass.NATIVE_SOLANA,
        status=AssetStatus.ACTIVE,
        listing_date=datetime(2020, 4, 10, tzinfo=timezone.utc),
    ))

    # Point-in-time universe query (survivorship-bias-free)
    universe = registry.get_universe_at_date(datetime(2025, 6, 1, tzinfo=timezone.utc))
"""

from __future__ import annotations

import json
import logging
import os
import threading
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_REGISTRY_PATH = ROOT / "data" / "trader" / "asset_registry.json"


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class AssetClass(Enum):
    """Classification of tradeable assets on Solana."""

    NATIVE_SOLANA = "native_solana"
    BAGS_BONDING_CURVE = "bags_bonding_curve"       # Pre-graduation Bags.fm token
    BAGS_GRADUATED = "bags_graduated"                # Post-graduation Bags.fm token
    XSTOCK = "xstock"                                # Tokenized traditional equity
    MEMECOIN = "memecoin"                            # Other meme/micro-cap tokens
    STABLECOIN = "stablecoin"                        # USDC, USDT, etc.


class AssetStatus(Enum):
    """Lifecycle status of a tracked asset."""

    ACTIVE = "active"
    DELISTED = "delisted"
    RUGGED = "rugged"                                # Rug pull confirmed
    GRADUATED = "graduated"                          # Bonding curve → AMM migration
    DEAD = "dead"                                    # Zero liquidity, abandoned
    SUSPENDED = "suspended"                          # Temporarily untradeable


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class AssetRecord:
    """Represents a single asset in the universe registry."""

    mint_address: str
    symbol: str
    asset_class: AssetClass
    status: AssetStatus
    listing_date: datetime

    # Lifecycle dates (None until event occurs)
    delisted_date: Optional[datetime] = None
    rugged_date: Optional[datetime] = None
    graduation_date: Optional[datetime] = None

    # Pool / market info
    pool_address: Optional[str] = None
    pool_liquidity_usd: Optional[float] = None

    # xStock specific
    underlying_ticker: Optional[str] = None          # "TSLA", "NVDA", etc.

    # Bags.fm specific
    creator_address: Optional[str] = None
    bags_creator_fee_pct: float = 0.0                # Perpetual creator fee (usually 1%)

    # Metadata
    name: Optional[str] = None
    notes: str = ""
    last_updated: Optional[datetime] = None

    # Data quality
    has_reliable_ohlcv: bool = False
    ohlcv_start_date: Optional[datetime] = None
    min_candles_available: int = 0

    def __post_init__(self) -> None:
        if isinstance(self.asset_class, str):
            self.asset_class = AssetClass(self.asset_class)
        if isinstance(self.status, str):
            self.status = AssetStatus(self.status)
        if isinstance(self.listing_date, str):
            self.listing_date = datetime.fromisoformat(self.listing_date)
        for date_field in (
            "delisted_date", "rugged_date", "graduation_date",
            "last_updated", "ohlcv_start_date",
        ):
            val = getattr(self, date_field)
            if isinstance(val, str):
                setattr(self, date_field, datetime.fromisoformat(val))

    # -- Helpers ----------------------------------------------------------------

    def is_tradeable_at(self, dt: datetime) -> bool:
        """Return True if this asset was tradeable (active) at *dt*."""
        if dt < self.listing_date:
            return False
        end_date = self.delisted_date or self.rugged_date
        if end_date and dt >= end_date:
            return False
        if self.status in (AssetStatus.DEAD, AssetStatus.RUGGED, AssetStatus.DELISTED):
            if end_date is None:
                return False
        return True

    def is_bags_token(self) -> bool:
        return self.asset_class in (AssetClass.BAGS_BONDING_CURVE, AssetClass.BAGS_GRADUATED)

    def is_xstock(self) -> bool:
        return self.asset_class == AssetClass.XSTOCK

    def round_trip_creator_fee_pct(self) -> float:
        """Total creator fee for a full buy+sell round trip."""
        return self.bags_creator_fee_pct * 2.0

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to JSON-safe dict."""
        d: Dict[str, Any] = {}
        for k, v in asdict(self).items():
            if isinstance(v, Enum):
                d[k] = v.value
            elif isinstance(v, datetime):
                d[k] = v.isoformat()
            else:
                d[k] = v
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AssetRecord":
        """Deserialize from a dict (e.g. loaded from JSON)."""
        return cls(**data)


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

class AssetRegistry:
    """
    In-memory registry backed by a JSON file on disk.

    Thread-safe for reads and writes via an internal lock.
    """

    def __init__(self, path: Optional[Path] = None) -> None:
        self._path = Path(path) if path else DEFAULT_REGISTRY_PATH
        self._lock = threading.Lock()
        self._assets: Dict[str, AssetRecord] = {}
        self._load()

    # -- Persistence ------------------------------------------------------------

    def _load(self) -> None:
        if not self._path.exists():
            logger.info("Asset registry not found at %s — starting fresh", self._path)
            return
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
            records = raw if isinstance(raw, list) else raw.get("assets", [])
            for entry in records:
                try:
                    rec = AssetRecord.from_dict(entry)
                    self._assets[rec.mint_address] = rec
                except Exception as exc:  # noqa: BLE001
                    logger.warning("Skipping malformed registry entry: %s", exc)
            logger.info("Loaded %d assets from registry", len(self._assets))
        except (json.JSONDecodeError, OSError) as exc:
            logger.error("Failed to load asset registry: %s", exc)

    def save(self) -> None:
        """Persist the registry to disk."""
        with self._lock:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            payload = {
                "version": 1,
                "updated_at": datetime.now(timezone.utc).isoformat(),
                "count": len(self._assets),
                "assets": [r.to_dict() for r in self._assets.values()],
            }
            tmp = self._path.with_suffix(".tmp")
            tmp.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
            tmp.replace(self._path)
        logger.info("Saved %d assets to %s", len(self._assets), self._path)

    # -- CRUD -------------------------------------------------------------------

    def register(self, record: AssetRecord, *, persist: bool = True) -> None:
        """Add or update an asset in the registry."""
        record.last_updated = datetime.now(timezone.utc)
        with self._lock:
            self._assets[record.mint_address] = record
        if persist:
            self.save()

    def bulk_register(self, records: Sequence[AssetRecord]) -> None:
        """Add multiple assets in a single write."""
        now = datetime.now(timezone.utc)
        with self._lock:
            for rec in records:
                rec.last_updated = now
                self._assets[rec.mint_address] = rec
        self.save()

    def get(self, mint_address: str) -> Optional[AssetRecord]:
        """Retrieve an asset by mint address."""
        return self._assets.get(mint_address)

    def update_status(
        self,
        mint_address: str,
        new_status: AssetStatus,
        *,
        event_date: Optional[datetime] = None,
        notes: str = "",
    ) -> bool:
        """Update an asset's status and record the transition date."""
        rec = self._assets.get(mint_address)
        if rec is None:
            logger.warning("Cannot update status — mint %s not in registry", mint_address)
            return False

        event_dt = event_date or datetime.now(timezone.utc)
        rec.status = new_status
        rec.last_updated = datetime.now(timezone.utc)

        if new_status == AssetStatus.DELISTED:
            rec.delisted_date = event_dt
        elif new_status == AssetStatus.RUGGED:
            rec.rugged_date = event_dt
        elif new_status == AssetStatus.GRADUATED:
            rec.graduation_date = event_dt
            if rec.asset_class == AssetClass.BAGS_BONDING_CURVE:
                rec.asset_class = AssetClass.BAGS_GRADUATED

        if notes:
            rec.notes = f"{rec.notes}; {notes}".lstrip("; ")

        self.save()
        logger.info(
            "Asset %s (%s) status → %s at %s",
            rec.symbol, mint_address, new_status.value, event_dt.isoformat(),
        )
        return True

    def remove(self, mint_address: str) -> bool:
        """Remove an asset entirely (use sparingly — prefer status updates)."""
        removed = False
        with self._lock:
            if mint_address in self._assets:
                del self._assets[mint_address]
                removed = True

        if removed:
            self.save()
            return True
        return False

    # -- Queries ----------------------------------------------------------------

    @property
    def all_assets(self) -> List[AssetRecord]:
        """Return all registered assets."""
        return list(self._assets.values())

    @property
    def count(self) -> int:
        return len(self._assets)

    def get_active(self) -> List[AssetRecord]:
        """Return only currently active/tradeable assets."""
        return [r for r in self._assets.values() if r.status == AssetStatus.ACTIVE]

    def get_by_class(self, asset_class: AssetClass) -> List[AssetRecord]:
        """Filter by asset class."""
        return [r for r in self._assets.values() if r.asset_class == asset_class]

    def get_by_status(self, status: AssetStatus) -> List[AssetRecord]:
        """Filter by lifecycle status."""
        return [r for r in self._assets.values() if r.status == status]

    def get_universe_at_date(self, target_date: datetime) -> List[AssetRecord]:
        """
        Return only assets that were listed and tradeable at *target_date*.

        This is the critical function for survivorship-bias-free backtesting.
        Assets that were rugged, delisted, or dead by *target_date* are excluded.
        Assets not yet listed by *target_date* are excluded.
        """
        return [r for r in self._assets.values() if r.is_tradeable_at(target_date)]

    def get_backtest_eligible(
        self,
        start_date: datetime,
        end_date: datetime,
        min_candles: int = 1000,
    ) -> List[AssetRecord]:
        """
        Return assets eligible for backtesting over [start_date, end_date].

        An asset is eligible if:
        - It was listed before or at *start_date*
        - It has at least *min_candles* of OHLCV data
        - It has reliable OHLCV data flagged
        """
        results: List[AssetRecord] = []
        for rec in self._assets.values():
            if rec.listing_date > start_date:
                continue
            if not rec.has_reliable_ohlcv:
                continue
            if rec.min_candles_available < min_candles:
                continue
            results.append(rec)
        return results

    def search(
        self,
        symbol: Optional[str] = None,
        asset_class: Optional[AssetClass] = None,
        status: Optional[AssetStatus] = None,
        predicate: Optional[Callable[[AssetRecord], bool]] = None,
    ) -> List[AssetRecord]:
        """Flexible search with optional filters."""
        results: List[AssetRecord] = []
        for rec in self._assets.values():
            if symbol and rec.symbol.upper() != symbol.upper():
                continue
            if asset_class and rec.asset_class != asset_class:
                continue
            if status and rec.status != status:
                continue
            if predicate and not predicate(rec):
                continue
            results.append(rec)
        return results

    def get_bags_tokens(self, include_graduated: bool = True) -> List[AssetRecord]:
        """Return all Bags.fm tokens (pre-grad, post-grad, or both)."""
        classes = {AssetClass.BAGS_BONDING_CURVE}
        if include_graduated:
            classes.add(AssetClass.BAGS_GRADUATED)
        return [r for r in self._assets.values() if r.asset_class in classes]

    def get_xstocks(self) -> List[AssetRecord]:
        """Return all tokenized equity assets."""
        return self.get_by_class(AssetClass.XSTOCK)

    # -- Statistics -------------------------------------------------------------

    def summary(self) -> Dict[str, Any]:
        """Return a summary of the registry for dashboards and logging."""
        by_class: Dict[str, int] = {}
        by_status: Dict[str, int] = {}
        for rec in self._assets.values():
            by_class[rec.asset_class.value] = by_class.get(rec.asset_class.value, 0) + 1
            by_status[rec.status.value] = by_status.get(rec.status.value, 0) + 1
        return {
            "total": len(self._assets),
            "by_class": by_class,
            "by_status": by_status,
            "backtest_eligible": len([
                r for r in self._assets.values()
                if r.has_reliable_ohlcv and r.min_candles_available >= 1000
            ]),
        }


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_registry: Optional[AssetRegistry] = None


def get_asset_registry(path: Optional[Path] = None) -> AssetRegistry:
    """Return the global AssetRegistry singleton (lazy-initialized)."""
    global _registry
    if _registry is None:
        _registry = AssetRegistry(path)
    return _registry
