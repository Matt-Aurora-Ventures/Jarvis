"""Fee and cost model for crypto and tokenized equities."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Dict

ROOT = Path(__file__).resolve().parents[1]
FEE_PROFILE_PATH = ROOT / "data" / "trader" / "knowledge" / "fee_profiles.json"


@dataclass
class FeeProfile:
    network_fee_usd: float
    amm_fee_bps: float
    aggregator_fee_bps: float
    slippage_bps: float
    spread_bps: float
    issuer_fee_bps: float
    conversion_bps: float
    notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


DEFAULT_CRYPTO = FeeProfile(
    network_fee_usd=0.0025,
    amm_fee_bps=30.0,
    aggregator_fee_bps=0.0,
    slippage_bps=30.0,
    spread_bps=15.0,
    issuer_fee_bps=0.0,
    conversion_bps=0.0,
    notes="default crypto",
)

DEFAULT_EQUITY = FeeProfile(
    network_fee_usd=0.0040,
    amm_fee_bps=40.0,
    aggregator_fee_bps=0.0,
    slippage_bps=80.0,
    spread_bps=80.0,
    issuer_fee_bps=10.0,
    conversion_bps=5.0,
    notes="default tokenized equity",
)


def _load_profiles() -> Dict[str, Any]:
    if not FEE_PROFILE_PATH.exists():
        return {}
    try:
        data = json.loads(FEE_PROFILE_PATH.read_text())
        return data if isinstance(data, dict) else {}
    except json.JSONDecodeError:
        return {}


def _write_profiles(payload: Dict[str, Any]) -> None:
    FEE_PROFILE_PATH.parent.mkdir(parents=True, exist_ok=True)
    FEE_PROFILE_PATH.write_text(json.dumps(payload, indent=2))


def get_fee_profile(asset_type: str, issuer: str = "") -> FeeProfile:
    profiles = _load_profiles()
    key = f"{asset_type}:{issuer}".lower().strip(":")
    if key in profiles:
        return FeeProfile(**profiles[key])
    if asset_type == "tokenized_equity":
        return DEFAULT_EQUITY
    return DEFAULT_CRYPTO


def save_fee_profile(asset_type: str, issuer: str, profile: FeeProfile) -> None:
    profiles = _load_profiles()
    key = f"{asset_type}:{issuer}".lower().strip(":")
    profiles[key] = profile.to_dict()
    profiles["_updated_at"] = time.time()
    _write_profiles(profiles)


def estimate_costs(
    *,
    notional_usd: float,
    asset_type: str,
    issuer: str = "",
) -> Dict[str, Any]:
    profile = get_fee_profile(asset_type, issuer)
    total_bps = (
        profile.amm_fee_bps
        + profile.aggregator_fee_bps
        + profile.slippage_bps
        + profile.spread_bps
        + profile.issuer_fee_bps
        + profile.conversion_bps
    )
    cost_pct = total_bps / 10000.0
    total_cost_usd = (notional_usd * cost_pct) + profile.network_fee_usd
    return {
        "profile": profile.to_dict(),
        "total_bps": total_bps,
        "total_pct": cost_pct,
        "total_cost_usd": total_cost_usd,
    }


def edge_to_cost_ratio(expected_edge_pct: float, cost_pct: float) -> float:
    if cost_pct <= 0:
        return 0.0
    return expected_edge_pct / cost_pct
