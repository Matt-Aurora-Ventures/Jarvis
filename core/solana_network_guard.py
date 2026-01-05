"""
Solana network health checks for high-frequency execution gating.
"""

from __future__ import annotations

import statistics
import time
from typing import Any, Dict, Optional

from core import config as config_module, solana_execution

try:
    import requests  # type: ignore
except Exception:
    requests = None

DEFAULT_CONFIG: Dict[str, Any] = {
    "enabled": True,
    "min_tps": 1500.0,
    "max_priority_fee_lamports": 8000,
    "performance_sample_limit": 2,
    "rpc_timeout_seconds": 8,
    "block_on_unknown": False,
}


def _merge_config(overrides: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    merged = dict(DEFAULT_CONFIG)
    if overrides:
        merged.update(overrides)
    return merged


def _rpc_call(url: str, method: str, params: Optional[list] = None, timeout: int = 8) -> Optional[Any]:
    if not requests:
        return None
    payload: Dict[str, Any] = {"jsonrpc": "2.0", "id": 1, "method": method}
    if params is not None:
        payload["params"] = params
    try:
        response = requests.post(url, json=payload, timeout=timeout)
        if response.status_code != 200:
            return None
        data = response.json()
    except Exception:
        return None
    if not isinstance(data, dict) or data.get("error"):
        return None
    return data.get("result")


def _get_tps(url: str, limit: int, timeout: int) -> Optional[float]:
    result = _rpc_call(url, "getRecentPerformanceSamples", [limit], timeout=timeout)
    if not isinstance(result, list) or not result:
        return None
    total_tx = 0
    total_secs = 0
    for item in result:
        if not isinstance(item, dict):
            continue
        total_tx += int(item.get("numTransactions", 0))
        total_secs += int(item.get("samplePeriodSecs", 0))
    if total_secs <= 0:
        return None
    return total_tx / total_secs


def _get_priority_fee(url: str, timeout: int) -> Optional[int]:
    result = _rpc_call(
        url,
        "getRecentPrioritizationFees",
        [{"accountKeys": []}],
        timeout=timeout,
    )
    if not isinstance(result, list) or not result:
        return None
    fees = [
        int(item.get("prioritizationFee", 0))
        for item in result
        if isinstance(item, dict) and item.get("prioritizationFee") is not None
    ]
    if not fees:
        return None
    return int(statistics.median(fees))


def assess_network_health() -> Dict[str, Any]:
    cfg = config_module.load_config()
    guard_cfg = _merge_config(cfg.get("solana_network_guard", {}))

    if not guard_cfg.get("enabled", True):
        return {"ok": True, "reason": "disabled", "checked_at": time.time()}

    if not requests:
        if guard_cfg.get("block_on_unknown", False):
            return {"ok": False, "reason": "requests_unavailable", "checked_at": time.time()}
        return {"ok": True, "reason": "requests_unavailable", "checked_at": time.time()}

    endpoints = solana_execution.load_solana_rpc_endpoints()
    timeout = int(guard_cfg.get("rpc_timeout_seconds", 8))
    min_tps = guard_cfg.get("min_tps")
    max_fee = guard_cfg.get("max_priority_fee_lamports")
    sample_limit = int(guard_cfg.get("performance_sample_limit", 2))
    block_on_unknown = bool(guard_cfg.get("block_on_unknown", False))

    chosen = None
    for endpoint in endpoints:
        health = _rpc_call(endpoint.url, "getHealth", timeout=timeout)
        if health == "ok":
            chosen = endpoint
            break

    if not chosen:
        return {"ok": False, "reason": "rpc_unhealthy", "checked_at": time.time()}

    tps = _get_tps(chosen.url, sample_limit, timeout=timeout)
    priority_fee = _get_priority_fee(chosen.url, timeout=timeout)

    reasons = []
    ok = True

    if min_tps is not None:
        if tps is None:
            reasons.append("tps_unknown")
            if block_on_unknown:
                ok = False
        elif tps < float(min_tps):
            reasons.append(f"tps_below_min:{tps:.1f}<{float(min_tps):.1f}")
            ok = False

    if max_fee is not None:
        if priority_fee is None:
            reasons.append("fee_unknown")
            if block_on_unknown:
                ok = False
        elif int(priority_fee) > int(max_fee):
            reasons.append(f"fee_above_max:{int(priority_fee)}>{int(max_fee)}")
            ok = False

    if not reasons:
        reasons.append("ok")

    return {
        "ok": ok,
        "reason": ";".join(reasons),
        "endpoint": chosen.url,
        "tps": tps,
        "priority_fee_lamports": priority_fee,
        "checked_at": time.time(),
    }
