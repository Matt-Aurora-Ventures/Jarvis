"""Solana meme coin scanner using BirdEye APIs."""

from __future__ import annotations

import csv
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from core import config, notes_manager

try:
    import requests  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    requests = None


ROOT = Path(__file__).resolve().parents[1]
SCAN_DIR = ROOT / "data" / "trader" / "solana_scanner"
STRATEGIES_FILE = ROOT / "data" / "trader" / "strategies.json"

TRENDING_CSV = SCAN_DIR / "birdeye_trending_tokens.csv"
NEW_TOKENS_CSV = SCAN_DIR / "birdeye_new_tokens.csv"
TOP_TRADERS_CSV = SCAN_DIR / "birdeye_top_traders.csv"

DEFAULT_SUPER_CYCLE_TOKENS = [
    "EKpQGSJtjMFqKZ9KQanSqYXRcF8fBopzLHYxdM65zcjm",
    "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263",
    "7GCihgDB8fe6KNjn2MYtkzZcRjQy3t9GHdC8uHYmW2hr",
]

STRATEGY_SHORTLIST = [
    {
        "rank": 1,
        "id": "sol_meme_trend_sma",
        "name": "Meme Trend SMA",
        "why": "Captures sustained meme coin momentum while avoiding chop.",
    },
    {
        "rank": 2,
        "id": "sol_meme_mean_reversion",
        "name": "Solana Meme Mean Reversion",
        "why": "Exploits blow-off tops and reversion after hype spikes.",
    },
    {
        "rank": 3,
        "id": "new_listing_sniper",
        "name": "New Listing Sniper",
        "why": "Fast edge in early listings before retail discovers them.",
    },
    {
        "rank": 4,
        "id": "whale_copy_trade",
        "name": "Whale Copy Trade",
        "why": "Follows proven wallets to reduce research time.",
    },
    {
        "rank": 5,
        "id": "open_interest_momentum",
        "name": "Open Interest Momentum",
        "why": "Uses OI shifts to confirm continuation or reversal.",
    },
]


def scan_all(
    *,
    trending_limit: int = 200,
    new_token_hours: int = 3,
    top_trader_limit: int = 100,
    sleep_seconds: float = 0.8,
) -> Dict[str, Any]:
    cfg = config.load_config()
    scanner_cfg = cfg.get("solana_scanner", {})
    api_key = _resolve_api_key(scanner_cfg)
    if not api_key:
        return {"error": "Missing BirdEye API key", "config": "solana_scanner.birdeye_api_key_env"}

    SCAN_DIR.mkdir(parents=True, exist_ok=True)

    trending = get_trending_tokens(api_key, limit=trending_limit, sleep_seconds=sleep_seconds)
    _write_csv(TRENDING_CSV, trending)

    new_tokens = get_new_tokens(api_key, hours=new_token_hours, sleep_seconds=sleep_seconds)
    _write_csv(NEW_TOKENS_CSV, new_tokens)

    top_traders = get_top_traders(
        api_key,
        token_addresses=scanner_cfg.get("super_cycle_tokens", DEFAULT_SUPER_CYCLE_TOKENS),
        limit=top_trader_limit,
        sleep_seconds=sleep_seconds,
    )
    _write_csv(TOP_TRADERS_CSV, top_traders)

    digest = _render_digest(trending, new_tokens, top_traders)
    note_path, summary_path, _ = notes_manager.save_note(
        topic="solana_scanner",
        content=digest,
        fmt="md",
        tags=["solana", "scanner", "trading"],
        source="solana_scanner",
        metadata={"trending": len(trending), "new_tokens": len(new_tokens), "top_traders": len(top_traders)},
    )

    return {
        "trending": len(trending),
        "new_tokens": len(new_tokens),
        "top_traders": len(top_traders),
        "trending_csv": str(TRENDING_CSV),
        "new_tokens_csv": str(NEW_TOKENS_CSV),
        "top_traders_csv": str(TOP_TRADERS_CSV),
        "note_path": str(note_path),
        "summary_path": str(summary_path),
    }


def get_trending_tokens(
    api_key: str,
    *,
    limit: int = 200,
    sleep_seconds: float = 0.8,
) -> List[Dict[str, Any]]:
    url = "https://public-api.birdeye.so/defi/token_trending"
    headers = {
        "accept": "application/json",
        "x-chain": "solana",
        "X-API-KEY": api_key,
    }

    all_tokens: List[Dict[str, Any]] = []
    for offset in range(0, limit, 20):
        params = {
            "sort_by": "rank",
            "sort_type": "asc",
            "offset": offset,
            "limit": min(20, limit - offset),
        }
        data = _http_get_json(url, headers, params=params)
        if not data:
            break
        tokens = data.get("data", {}).get("tokens", []) or []
        for token in tokens:
            all_tokens.append(_normalize_trending_token(token))
        if len(tokens) < 20:
            break
        time.sleep(sleep_seconds)

    return all_tokens


def get_new_tokens(
    api_key: str,
    *,
    hours: int = 3,
    sleep_seconds: float = 0.8,
) -> List[Dict[str, Any]]:
    url = "https://public-api.birdeye.so/defi/v2/tokens/new_listing"
    headers = {
        "accept": "application/json",
        "x-chain": "solana",
        "X-API-KEY": api_key,
    }

    end_time = int(time.time())
    start_time = end_time - int(hours * 3600)

    existing = _read_csv(NEW_TOKENS_CSV)
    last_listing_time = _max_int(existing, "listingTime")
    if last_listing_time:
        start_time = max(start_time, last_listing_time + 1)

    all_tokens: List[Dict[str, Any]] = []
    params = {
        "time_from": start_time,
        "time_to": end_time,
        "limit": 10,
    }

    while start_time < end_time:
        params["time_from"] = start_time
        data = _http_get_json(url, headers, params=params)
        if not data:
            break
        tokens = data.get("data", {}).get("items", []) or []
        if not tokens:
            break
        for token in tokens:
            all_tokens.append(_normalize_new_token(token))
        last_time = tokens[-1].get("listingTime") or start_time
        start_time = int(last_time) + 1
        time.sleep(sleep_seconds)

    combined = _dedupe(existing + all_tokens, "address")
    return combined


def get_top_traders(
    api_key: str,
    *,
    token_addresses: List[str],
    limit: int = 100,
    sleep_seconds: float = 0.8,
) -> List[Dict[str, Any]]:
    url = "https://public-api.birdeye.so/defi/v2/tokens/top_traders"
    headers = {
        "accept": "application/json",
        "x-chain": "solana",
        "X-API-KEY": api_key,
    }
    all_traders: List[Dict[str, Any]] = []

    for token_address in token_addresses:
        offset = 0
        while offset < limit:
            params = {
                "address": token_address,
                "time_frame": "24h",
                "sort_type": "desc",
                "sort_by": "volume",
                "limit": min(10, limit - offset),
                "offset": offset,
            }
            data = _http_get_json(url, headers, params=params)
            if not data:
                break
            traders = data.get("data", {}).get("items", []) or []
            for trader in traders:
                all_traders.append(_normalize_trader(token_address, trader))
            if len(traders) < 10:
                break
            offset += 10
            time.sleep(sleep_seconds)

    return all_traders


def compile_strategy_shortlist() -> List[Dict[str, Any]]:
    return list(STRATEGY_SHORTLIST)


def seed_scanner_strategies() -> Dict[str, Any]:
    strategies = _scanner_strategies()
    _seed_trader_strategies(strategies)
    return {
        "strategies_added": len(strategies),
        "strategies": [s["id"] for s in strategies],
    }


def _scanner_strategies() -> List[Dict[str, Any]]:
    return [
        {
            "id": "sol_meme_trend_sma",
            "name": "Meme Trend SMA",
            "description": "Trend-following meme coin strategy using SMA gating.",
            "rules": {
                "strategy": "trend_sma",
                "params": {"fast": 9, "slow": 21},
                "signals": ["trend", "volume expansion"],
            },
        },
        {
            "id": "sol_meme_mean_reversion",
            "name": "Solana Meme Mean Reversion",
            "description": "Fade overextended meme coins after blow-off moves.",
            "rules": {
                "strategy": "mean_reversion",
                "signals": ["zscore >= 2", "reversal candle"],
            },
        },
        {
            "id": "new_listing_sniper",
            "name": "New Listing Sniper",
            "description": "Filter new Solana token listings for early entries.",
            "rules": {
                "strategy": "new_listing",
                "signals": ["new listing", "liquidity >= min"],
            },
        },
        {
            "id": "whale_copy_trade",
            "name": "Whale Copy Trade",
            "description": "Copy trade known profitable wallets with risk limits.",
            "rules": {
                "strategy": "copy_trade",
                "signals": ["top trader buy", "token trending"],
            },
        },
        {
            "id": "open_interest_momentum",
            "name": "Open Interest Momentum",
            "description": "Use open interest shifts to confirm trend continuation.",
            "rules": {
                "strategy": "open_interest",
                "signals": ["oi spike", "funding shift"],
            },
        },
    ]


def _resolve_api_key(scanner_cfg: Dict[str, Any]) -> Optional[str]:
    key_env = scanner_cfg.get("birdeye_api_key_env", "BIRDEYE_API_KEY")
    return os.getenv(key_env)


def _normalize_trending_token(token: Dict[str, Any]) -> Dict[str, Any]:
    address = token.get("address")
    return {
        "address": address,
        "name": token.get("name"),
        "symbol": token.get("symbol"),
        "liquidity": token.get("liquidity"),
        "volume24hUSD": token.get("volume24hUSD"),
        "price": token.get("price"),
        "dexscreener_link": _dexscreener_link(address),
    }


def _normalize_new_token(token: Dict[str, Any]) -> Dict[str, Any]:
    address = token.get("address")
    return {
        "address": address,
        "name": token.get("name"),
        "symbol": token.get("symbol"),
        "listingTime": token.get("listingTime"),
        "liquidity": token.get("liquidity"),
        "price": token.get("price"),
        "dexscreener_link": _dexscreener_link(address),
    }


def _normalize_trader(token_address: str, trader: Dict[str, Any]) -> Dict[str, Any]:
    owner = trader.get("owner")
    return {
        "tokenAddress": token_address,
        "owner": owner,
        "volume": trader.get("volume"),
        "trades": trader.get("trade"),
        "gmgn_link": f"https://gmgn.ai/sol/address/{owner}" if owner else None,
    }


def _dexscreener_link(address: Optional[str]) -> Optional[str]:
    if not address:
        return None
    return f"https://dexscreener.com/solana/{address}"


def _http_get_json(
    url: str,
    headers: Dict[str, str],
    *,
    params: Optional[Dict[str, Any]] = None,
    timeout: int = 30,
) -> Dict[str, Any]:
    if params:
        url = f"{url}?{urlencode(params)}"
    if requests:
        resp = requests.get(url, headers=headers, timeout=timeout)
        resp.raise_for_status()
        return resp.json()
    request = Request(url, headers=headers)
    with urlopen(request, timeout=timeout) as resp:
        data = resp.read().decode("utf-8")
    return json.loads(data)


def _write_csv(path: Path, rows: List[Dict[str, Any]]) -> None:
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(rows[0].keys())
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _read_csv(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    with path.open("r", newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _dedupe(rows: List[Dict[str, Any]], key: str) -> List[Dict[str, Any]]:
    seen = set()
    output: List[Dict[str, Any]] = []
    for row in rows:
        value = row.get(key)
        if not value or value in seen:
            continue
        seen.add(value)
        output.append(row)
    return output


def _max_int(rows: List[Dict[str, Any]], key: str) -> Optional[int]:
    values = []
    for row in rows:
        try:
            values.append(int(float(row.get(key, 0))))
        except (TypeError, ValueError):
            continue
    return max(values) if values else None


def _render_digest(
    trending: List[Dict[str, Any]],
    new_tokens: List[Dict[str, Any]],
    top_traders: List[Dict[str, Any]],
) -> str:
    lines = [
        "# Solana Meme Coin Scanner",
        f"Generated: {datetime.now(timezone.utc).isoformat()}",
        "",
        f"Trending tokens: {len(trending)}",
        f"New listings: {len(new_tokens)}",
        f"Top traders: {len(top_traders)}",
        "",
        "## Strategy Shortlist",
    ]
    for item in STRATEGY_SHORTLIST:
        lines.append(f"- {item['rank']}. {item['name']} ({item['id']}): {item['why']}")
    return "\n".join(lines).strip() + "\n"


def _seed_trader_strategies(strategies: List[Dict[str, Any]]) -> None:
    if not strategies:
        return
    existing = []
    if STRATEGIES_FILE.exists():
        try:
            with open(STRATEGIES_FILE, "r", encoding="utf-8") as handle:
                data = json.load(handle)
                existing = data.get("strategies", [])
        except Exception:
            existing = []

    existing_ids = {item.get("id") for item in existing if isinstance(item, dict)}
    new_entries = []
    for strat in strategies:
        if strat.get("id") in existing_ids:
            continue
        new_entries.append({
            "id": strat.get("id"),
            "name": strat.get("name"),
            "description": strat.get("description", ""),
            "rules": strat.get("rules", {}),
            "created_at": time.time(),
            "backtest_results": None,
            "paper_results": None,
            "approved_for_live": False,
        })

    if not new_entries:
        return

    merged = existing + new_entries
    STRATEGIES_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(STRATEGIES_FILE, "w", encoding="utf-8") as handle:
        json.dump({"strategies": merged, "updated_at": time.time()}, handle, indent=2)
