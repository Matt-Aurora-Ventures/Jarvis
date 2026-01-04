#!/usr/bin/env python3
"""Search Solana DEX pools for >= target one-day ROI using multiple strategies."""

from __future__ import annotations

import argparse
import json
import random
import sys
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core import trading_pipeline
from core import rugcheck
from core import dexscreener
from core import birdeye
from core.geckoterminal import (
    extract_included_tokens,
    fetch_pool_ohlcv,
    fetch_pools,
    normalize_ohlcv_list,
)


OUT_DIR = ROOT / "data" / "trader" / "solana_dex_one_day"
JUPITER_TOKEN_URL = "https://token.jup.ag/all"
SOLANA_TOKEN_LIST_URL = "https://cdn.jsdelivr.net/gh/solana-labs/token-list@main/src/tokens/solana.tokenlist.json"
PROGRESS_PATH = OUT_DIR / "progress.json"
JUPITER_CACHE = ROOT / "data" / "trader" / "jupiter_tokens_all.json"
PHANTOM_TOKEN_LIST_PATH = ROOT / "data" / "trader" / "phantom_terminal_tokens.json"

TIMEFRAME_SECONDS = {
    "hour": 3600,
}

DEFAULT_TOKEN_SCAN_LIMIT = 2000

EXCLUDED_ADDRESSES = {
    "So11111111111111111111111111111111111111112",  # SOL
    "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",  # USDC
    "Es9vMFrzaCER3EJmqvQC2Uo9qowWP1h1xFh3Le7YpR1V",  # USDT
}
EXCLUDED_SYMBOLS = {"SOL", "USDC", "USDT"}


def main() -> None:
    args = parse_args()
    social_context = apply_social_overrides(args)
    if args.source == "multi" and args.token_scan_limit == DEFAULT_TOKEN_SCAN_LIMIT:
        cap = max(args.limit_tokens * 6, 300)
        cap = min(cap, 1000)
        if cap < args.token_scan_limit:
            print(f"[tokens] capping token_scan_limit from {args.token_scan_limit} to {cap} for multi-source")
            args.token_scan_limit = cap
    if social_context.get("applied"):
        print(f"[social] using relaxed safety filters for @{args.social_handle}")
    days = min(args.days, 30)
    safe_mode = bool(args.safe_mode)
    min_trades = args.min_trades
    if safe_mode and min_trades < 2:
        min_trades = 2

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    tokens = load_tokens(args)

    if not tokens:
        print("No tokens found. Check API or thresholds.")
        return

    token_path = OUT_DIR / "token_universe.json"
    if not token_path.exists():
        token_path.write_text(json.dumps(tokens, indent=2))

    strategies = build_strategies(
        max_strategies=args.max_strategies,
        capital_usd=args.capital_usd,
        fee_bps=args.fee_bps,
        slippage_bps=args.slippage_bps,
        risk_per_trade=args.risk_per_trade,
        stop_loss_pct=args.stop_loss_pct,
        take_profit_pct=args.take_profit_pct,
        max_position_pct=args.max_position_pct,
    )

    hits: List[Dict[str, Any]] = []
    best_overall: List[Dict[str, Any]] = []
    tokens_tested = 0
    windows_tested = 0
    start_index = 0

    if args.resume and PROGRESS_PATH.exists():
        try:
            progress = json.loads(PROGRESS_PATH.read_text())
            start_index = int(progress.get("last_index", 0))
            tokens_tested = int(progress.get("tokens_tested", 0))
            windows_tested = int(progress.get("windows_tested", 0))
            if progress.get("hits"):
                hits = progress.get("hits", [])
            if progress.get("best_overall"):
                best_overall = progress.get("best_overall", [])
        except (json.JSONDecodeError, ValueError, TypeError):
            start_index = 0

    for idx, token in enumerate(tokens[start_index:], start_index + 1):
        print(f"[{idx}/{len(tokens)}] Testing {token['symbol']} ({token['address'][:6]}...)")
        safety = None
        if safe_mode or args.require_locked_liquidity:
            report = rugcheck.fetch_report(token["address"])
            if safe_mode:
                safety = rugcheck.evaluate_safety(
                    report,
                    min_locked_pct=args.min_locked_pct,
                    min_locked_usd=args.min_locked_usd,
                    require_spl_program=True,
                    require_authorities_revoked=True,
                    max_transfer_fee_bps=args.max_transfer_fee_bps,
                    require_not_rugged=True,
                )
                if not safety.get("ok"):
                    continue
            elif args.require_locked_liquidity:
                if not rugcheck.has_locked_liquidity(
                    report,
                    min_locked_pct=args.min_locked_pct,
                    min_locked_usd=args.min_locked_usd,
                ):
                    continue
                safety = {"ok": True, "details": rugcheck.best_lock_stats(report)}

        if safety and safety.get("details"):
            token["safety"] = safety["details"]

        candles = fetch_candles_for_days(
            pool_address=token["pool_address"],
            token_address=token.get("address"),
            timeframe=args.timeframe,
            days=days,
            ohlcv_source=args.ohlcv_source,
            sleep_seconds=args.sleep_seconds,
        )
        if not candles:
            _save_progress(idx, tokens_tested, windows_tested, hits, best_overall)
            continue

        daily_windows = split_daily_windows(
            candles,
            min_candles=args.min_candles_per_day,
        )
        if not daily_windows:
            _save_progress(idx, tokens_tested, windows_tested, hits, best_overall)
            continue

        tokens_tested += 1
        token_best: Optional[Dict[str, Any]] = None

        for day_ts, day_candles in daily_windows:
            windows_tested += 1
            for strat in strategies:
                strat_id = strat["id"]
                strat_cfg = strat["config"]
                result = trading_pipeline.run_backtest(
                    day_candles,
                    symbol=token["symbol"],
                    interval=args.timeframe,
                    strategy=strat_cfg,
                )
                if result.error:
                    continue
                if result.total_trades < min_trades:
                    continue

                roi = result.roi
                if args.max_drawdown is not None and result.max_drawdown > args.max_drawdown:
                    continue
                if token_best is None or roi > token_best["roi"]:
                    token_best = {
                        "token": token,
                        "day_start": day_ts,
                        "roi": roi,
                        "net_pnl": result.net_pnl,
                        "total_trades": result.total_trades,
                        "max_drawdown": result.max_drawdown,
                        "strategy_id": strat_id,
                        "strategy": asdict(strat_cfg),
                    }

                if roi >= args.threshold:
                    lock_stats = {"best_lp_locked_pct": 0.0, "best_lp_locked_usd": 0.0}
                    locked_ok = True
                    if args.require_locked_liquidity:
                        report = rugcheck.fetch_report(token["address"])
                        locked_ok = rugcheck.has_locked_liquidity(
                            report,
                            min_locked_pct=args.min_locked_pct,
                            min_locked_usd=args.min_locked_usd,
                        )
                        lock_stats = rugcheck.best_lock_stats(report)

                    if not locked_ok:
                        continue

                    hit = {
                        "token": token,
                        "day_start": day_ts,
                        "roi": roi,
                        "net_pnl": result.net_pnl,
                        "total_trades": result.total_trades,
                        "max_drawdown": result.max_drawdown,
                        "strategy_id": strat_id,
                        "strategy": asdict(strat_cfg),
                        "lock_stats": lock_stats,
                        "locked": locked_ok,
                    }
                    if safety:
                        hit["safety"] = safety
                    hits.append(hit)
                    write_outputs(
                        hits=hits,
                        best_overall=best_overall,
                        tokens_tested=tokens_tested,
                        windows_tested=windows_tested,
                        threshold=args.threshold,
                        days=days,
                        strategies=strategies,
                        require_locked=args.require_locked_liquidity,
                        min_locked_pct=args.min_locked_pct,
                        min_locked_usd=args.min_locked_usd,
                        source=args.source,
                        ohlcv_source=args.ohlcv_source,
                        pair_sort=args.pair_sort,
                        token_scan_limit=args.token_scan_limit,
                        limit_tokens=args.limit_tokens,
                        safe_mode=safe_mode,
                        min_trades=min_trades,
                        max_drawdown=args.max_drawdown,
                        social_handle=args.social_handle,
                        social_overrides_applied=args.social_overrides_applied,
                    )
                    print("✅ Threshold hit found.")
                    if args.stop_on_hit:
                        _save_progress(idx, tokens_tested, windows_tested, hits, best_overall)
                        return

        if token_best:
            best_overall.append(token_best)

        if idx % args.progress_interval == 0:
            _save_progress(idx, tokens_tested, windows_tested, hits, best_overall)
            write_outputs(
                hits=hits,
                best_overall=best_overall,
                tokens_tested=tokens_tested,
                windows_tested=windows_tested,
                threshold=args.threshold,
                days=days,
                strategies=strategies,
                require_locked=args.require_locked_liquidity,
                min_locked_pct=args.min_locked_pct,
                min_locked_usd=args.min_locked_usd,
                source=args.source,
                ohlcv_source=args.ohlcv_source,
                pair_sort=args.pair_sort,
                token_scan_limit=args.token_scan_limit,
                limit_tokens=args.limit_tokens,
                safe_mode=safe_mode,
                min_trades=min_trades,
                max_drawdown=args.max_drawdown,
                social_handle=args.social_handle,
                social_overrides_applied=args.social_overrides_applied,
            )

    write_outputs(
        hits=hits,
        best_overall=best_overall,
        tokens_tested=tokens_tested,
        windows_tested=windows_tested,
        threshold=args.threshold,
        days=days,
        strategies=strategies,
        require_locked=args.require_locked_liquidity,
        min_locked_pct=args.min_locked_pct,
        min_locked_usd=args.min_locked_usd,
        source=args.source,
        ohlcv_source=args.ohlcv_source,
        pair_sort=args.pair_sort,
        token_scan_limit=args.token_scan_limit,
        limit_tokens=args.limit_tokens,
        safe_mode=safe_mode,
        min_trades=min_trades,
        max_drawdown=args.max_drawdown,
        social_handle=args.social_handle,
        social_overrides_applied=args.social_overrides_applied,
    )
    _save_progress(len(tokens), tokens_tested, windows_tested, hits, best_overall)
    print("Finished scanning tokens.")


def normalize_handle(handle: Optional[str]) -> Optional[str]:
    if not handle:
        return None
    normalized = handle.strip()
    if normalized.startswith("@"):
        normalized = normalized[1:]
    normalized = normalized.lower()
    return normalized or None


def apply_social_overrides(args: argparse.Namespace) -> Dict[str, Any]:
    handle = normalize_handle(args.social_handle)
    args.social_handle = handle
    args.social_overrides_applied = False

    if not handle:
        return {"handle": None, "applied": False}

    try:
        from core import sentiment_trading
    except Exception as exc:
        print(f"[social] sentiment_trading unavailable: {exc}")
        return {"handle": handle, "applied": False, "error": "missing_sentiment_module"}

    config = sentiment_trading.get_default_config()
    trusted = [normalize_handle(h) for h in (config.trusted_handles or [])]
    if handle not in trusted:
        print(f"[social] handle @{handle} not in trusted list; keeping default safety filters.")
        return {"handle": handle, "applied": False, "trusted": False}

    args.safe_mode = False
    args.require_locked_liquidity = bool(config.require_locked_lp)
    args.min_locked_pct = float(config.min_locked_pct)
    args.min_locked_usd = 0.0
    args.max_transfer_fee_bps = float(config.max_transfer_fee_bps)
    args.min_liquidity_usd = float(config.min_liquidity_usd)
    args.min_volume_usd = float(config.min_volume_24h_usd)

    args.fee_bps = float(config.fee_bps)
    args.slippage_bps = float(config.slippage_bps)
    args.risk_per_trade = float(config.risk_per_trade)
    args.stop_loss_pct = float(config.stop_loss_pct)
    args.take_profit_pct = float(config.take_profit_pct)
    args.max_position_pct = float(config.max_position_pct)
    args.capital_usd = float(config.capital_usd)

    args.social_overrides_applied = True
    return {"handle": handle, "applied": True, "trusted": True}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Search for >=100% one-day ROI on Solana pools.")
    parser.add_argument(
        "--source",
        type=str,
        default="dexscreener",
        choices=["dexscreener", "geckoterminal", "birdeye", "phantom", "multi"],
    )
    parser.add_argument(
        "--ohlcv-source",
        type=str,
        default="auto",
        choices=["auto", "geckoterminal", "birdeye"],
    )
    parser.add_argument("--phantom-token-list", type=str, default=str(PHANTOM_TOKEN_LIST_PATH))
    parser.add_argument("--phantom-token-url", type=str)
    parser.add_argument("--social-handle", type=str)
    parser.add_argument("--limit-tokens", type=int, default=500)
    parser.add_argument("--pages", type=int, default=25)
    parser.add_argument("--sort", type=str, default="h24_tx_count_desc")
    parser.add_argument("--pair-sort", type=str, default="volume", choices=["volume", "liquidity", "txns"])
    parser.add_argument("--token-scan-limit", type=int, default=DEFAULT_TOKEN_SCAN_LIMIT)
    parser.add_argument("--token-sample-seed", type=int, default=42)
    parser.add_argument("--token-cache-hours", type=int, default=24)
    parser.add_argument("--min-liquidity-usd", type=float, default=0.0)
    parser.add_argument("--min-volume-usd", type=float, default=0.0)
    parser.add_argument("--timeframe", type=str, default="hour", choices=TIMEFRAME_SECONDS.keys())
    parser.add_argument("--days", type=int, default=30)
    parser.add_argument("--threshold", type=float, default=1.0)
    parser.add_argument("--max-strategies", type=int, default=120)
    parser.add_argument("--capital-usd", type=float, default=10.0)
    parser.add_argument("--fee-bps", type=float, default=30.0)
    parser.add_argument("--slippage-bps", type=float, default=20.0)
    parser.add_argument("--risk-per-trade", type=float, default=0.02)
    parser.add_argument("--stop-loss-pct", type=float, default=0.03)
    parser.add_argument("--take-profit-pct", type=float, default=0.06)
    parser.add_argument("--max-position-pct", type=float, default=0.25)
    parser.add_argument("--min-candles-per-day", type=int, default=20)
    parser.add_argument("--max-drawdown", type=float)
    parser.add_argument("--safe-mode", action="store_true")
    parser.add_argument("--max-transfer-fee-bps", type=float, default=0.0)
    parser.add_argument("--min-trades", type=int, default=1)
    parser.add_argument("--progress-interval", type=int, default=5)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--sleep-seconds", type=float, default=0.2)
    parser.add_argument("--require-locked-liquidity", action="store_true")
    parser.add_argument("--min-locked-pct", type=float, default=50.0)
    parser.add_argument("--min-locked-usd", type=float, default=0.0)
    parser.add_argument("--stop-on-hit", action="store_true")
    return parser.parse_args()


def collect_token_universe_geckoterminal(
    *,
    limit_tokens: int,
    pages: int,
    sort: str,
    min_liquidity_usd: float,
    min_volume_usd: float,
    sleep_seconds: float,
) -> List[Dict[str, Any]]:
    tokens_by_address: Dict[str, Dict[str, Any]] = {}

    for page in range(1, pages + 1):
        print(f"[tokens:geckoterminal] fetching page {page}/{pages}")
        payload = fetch_pools("solana", page=page, sort=sort, include_tokens=True)
        if not payload:
            break
        included_tokens = extract_included_tokens(payload)
        pools = payload.get("data", []) or []
        if not pools:
            break

        for pool in pools:
            attrs = pool.get("attributes", {}) or {}
            volume_24h = _to_float(attrs.get("volume_usd", {}).get("h24"))
            reserve_usd = _to_float(attrs.get("reserve_in_usd"))
            if volume_24h < min_volume_usd or reserve_usd < min_liquidity_usd:
                continue

            base, quote = _resolve_tokens(pool, included_tokens)
            if not base or not quote:
                continue

            base_address = base.get("address")
            base_symbol = (base.get("symbol") or "").upper()
            if not base_address:
                continue
            if base_address in EXCLUDED_ADDRESSES or base_symbol in EXCLUDED_SYMBOLS:
                continue

            token_entry = {
                "symbol": base.get("symbol") or base_address[:6],
                "name": base.get("name") or base.get("symbol") or base_address,
                "address": base_address,
                "quote_symbol": quote.get("symbol"),
                "quote_address": quote.get("address"),
                "pool_address": attrs.get("address"),
                "pool_name": attrs.get("name"),
                "pool_id": pool.get("id"),
                "dex": _resolve_dex(pool),
                "volume_24h": volume_24h,
                "reserve_usd": reserve_usd,
                "sources": ["geckoterminal"],
            }

            existing = tokens_by_address.get(base_address)
            if not existing or volume_24h > existing["volume_24h"]:
                tokens_by_address[base_address] = token_entry

        time.sleep(sleep_seconds)

    tokens = sorted(tokens_by_address.values(), key=lambda item: item["volume_24h"], reverse=True)
    return tokens[:limit_tokens]


def load_tokens(args: argparse.Namespace) -> List[Dict[str, Any]]:
    token_path = OUT_DIR / "token_universe.json"
    if args.resume and token_path.exists():
        try:
            data = json.loads(token_path.read_text())
            if isinstance(data, list):
                return data
        except json.JSONDecodeError:
            pass

    if args.source == "dexscreener":
        return collect_token_universe_dexscreener(
            limit_tokens=args.limit_tokens,
            token_scan_limit=args.token_scan_limit,
            min_liquidity_usd=args.min_liquidity_usd,
            min_volume_usd=args.min_volume_usd,
            pair_sort=args.pair_sort,
            sleep_seconds=args.sleep_seconds,
            cache_hours=args.token_cache_hours,
            sample_seed=args.token_sample_seed,
        )
    if args.source == "geckoterminal":
        return collect_token_universe_geckoterminal(
            limit_tokens=args.limit_tokens,
            pages=args.pages,
            sort=args.sort,
            min_liquidity_usd=args.min_liquidity_usd,
            min_volume_usd=args.min_volume_usd,
            sleep_seconds=args.sleep_seconds,
        )
    if args.source == "birdeye":
        return collect_token_universe_birdeye(
            limit_tokens=args.limit_tokens,
            token_scan_limit=args.token_scan_limit,
            min_liquidity_usd=args.min_liquidity_usd,
            min_volume_usd=args.min_volume_usd,
            pair_sort=args.pair_sort,
            sleep_seconds=args.sleep_seconds,
            cache_hours=args.token_cache_hours,
            sample_seed=args.token_sample_seed,
        )
    if args.source == "phantom":
        return collect_token_universe_phantom(
            limit_tokens=args.limit_tokens,
            token_scan_limit=args.token_scan_limit,
            min_liquidity_usd=args.min_liquidity_usd,
            min_volume_usd=args.min_volume_usd,
            pair_sort=args.pair_sort,
            sleep_seconds=args.sleep_seconds,
            sample_seed=args.token_sample_seed,
            token_list_path=Path(args.phantom_token_list),
            token_list_url=args.phantom_token_url,
        )
    return collect_token_universe_multi(
        limit_tokens=args.limit_tokens,
        pages=args.pages,
        sort=args.sort,
        token_scan_limit=args.token_scan_limit,
        min_liquidity_usd=args.min_liquidity_usd,
        min_volume_usd=args.min_volume_usd,
        pair_sort=args.pair_sort,
        sleep_seconds=args.sleep_seconds,
        cache_hours=args.token_cache_hours,
        sample_seed=args.token_sample_seed,
        phantom_token_list=Path(args.phantom_token_list),
        phantom_token_url=args.phantom_token_url,
    )


def _resolve_token_address(token: Dict[str, Any]) -> Optional[str]:
    for key in ("address", "mint", "tokenAddress", "token_address"):
        value = token.get(key)
        if value:
            return str(value)
    return None


def _resolve_token_symbol(token: Dict[str, Any]) -> Optional[str]:
    for key in ("symbol", "ticker"):
        value = token.get(key)
        if value:
            return str(value)
    return None


def _resolve_token_name(token: Dict[str, Any]) -> Optional[str]:
    for key in ("name", "tokenName"):
        value = token.get(key)
        if value:
            return str(value)
    return None


def collect_token_universe_from_token_list(
    tokens: List[Dict[str, Any]],
    *,
    limit_tokens: int,
    token_scan_limit: int,
    min_liquidity_usd: float,
    min_volume_usd: float,
    pair_sort: str,
    sleep_seconds: float,
    sample_seed: int,
    source_name: str,
) -> List[Dict[str, Any]]:
    if not tokens:
        return []

    rng = random.Random(sample_seed)
    rng.shuffle(tokens)
    if token_scan_limit > 0:
        tokens = tokens[:token_scan_limit]

    tokens_by_address: Dict[str, Dict[str, Any]] = {}
    total_tokens = len(tokens)
    print(f"[tokens:{source_name}] scanning {total_tokens} tokens (limit {limit_tokens})")
    for idx, token in enumerate(tokens, 1):
        if len(tokens_by_address) >= limit_tokens:
            print(f"[tokens:{source_name}] reached limit {limit_tokens} after scanning {idx - 1} tokens")
            break

        address = _resolve_token_address(token)
        if not address or address in EXCLUDED_ADDRESSES:
            if idx % 50 == 0:
                print(
                    f"[tokens:{source_name}] scanned {idx}/{total_tokens} | "
                    f"candidates {len(tokens_by_address)}"
                )
            time.sleep(sleep_seconds)
            continue

        payload = dexscreener.fetch_token_pairs(address)
        if not payload:
            if idx % 50 == 0:
                print(
                    f"[tokens:{source_name}] scanned {idx}/{total_tokens} | "
                    f"candidates {len(tokens_by_address)}"
                )
            time.sleep(sleep_seconds)
            continue

        pairs = payload.get("pairs", []) or []
        sol_pairs = [p for p in pairs if p.get("chainId") == "solana"]
        if not sol_pairs:
            if idx % 50 == 0:
                print(
                    f"[tokens:{source_name}] scanned {idx}/{total_tokens} | "
                    f"candidates {len(tokens_by_address)}"
                )
            time.sleep(sleep_seconds)
            continue

        best_pair = select_best_pair(sol_pairs, sort_key=pair_sort)
        if not best_pair:
            if idx % 50 == 0:
                print(
                    f"[tokens:{source_name}] scanned {idx}/{total_tokens} | "
                    f"candidates {len(tokens_by_address)}"
                )
            time.sleep(sleep_seconds)
            continue

        entry = build_entry_from_pair(
            best_pair,
            token_address=address,
            token_symbol=_resolve_token_symbol(token),
            token_name=_resolve_token_name(token),
        )
        if not entry:
            if idx % 50 == 0:
                print(
                    f"[tokens:{source_name}] scanned {idx}/{total_tokens} | "
                    f"candidates {len(tokens_by_address)}"
                )
            time.sleep(sleep_seconds)
            continue

        if entry["volume_24h"] < min_volume_usd or entry["reserve_usd"] < min_liquidity_usd:
            if idx % 50 == 0:
                print(
                    f"[tokens:{source_name}] scanned {idx}/{total_tokens} | "
                    f"candidates {len(tokens_by_address)}"
                )
            time.sleep(sleep_seconds)
            continue

        entry["sources"] = [source_name]
        tokens_by_address[address] = entry
        if idx % 50 == 0:
            print(
                f"[tokens:{source_name}] scanned {idx}/{total_tokens} | "
                f"candidates {len(tokens_by_address)}"
            )
        time.sleep(sleep_seconds)

    sorted_tokens = sorted(tokens_by_address.values(), key=lambda item: item["volume_24h"], reverse=True)
    print(f"[tokens:{source_name}] selected {len(sorted_tokens)} candidates")
    return sorted_tokens


def load_birdeye_tokens(*, limit: int) -> List[Dict[str, Any]]:
    if not birdeye.has_api_key():
        print("[birdeye] API key missing in secrets/keys.json")
        return []

    if limit > 100:
        print(f"[birdeye] capping limit from {limit} to 100 (API constraint)")
        limit = 100

    payload = birdeye.fetch_trending_tokens(limit=limit)
    if not payload:
        return []

    tokens = payload.get("data", {}).get("tokens", []) or payload.get("data", {}).get("items", []) or []
    normalized: List[Dict[str, Any]] = []
    for token in tokens:
        address = token.get("address")
        if not address:
            continue
        normalized.append(
            {
                "address": address,
                "symbol": token.get("symbol"),
                "name": token.get("name"),
            }
        )
    print(f"[birdeye] loaded {len(normalized)} tokens")
    return normalized


def load_phantom_tokens(
    *,
    token_list_path: Path,
    token_list_url: Optional[str],
) -> List[Dict[str, Any]]:
    data = None
    if token_list_url:
        try:
            resp = requests.get(token_list_url, timeout=30)
            resp.raise_for_status()
            data = resp.json()
        except requests.RequestException as exc:
            print(f"[phantom] token list fetch failed: {exc}")
            return []
    elif token_list_path.exists():
        try:
            data = json.loads(token_list_path.read_text())
        except json.JSONDecodeError as exc:
            print(f"[phantom] token list parse failed: {exc}")
            return []
    else:
        print(f"[phantom] token list not found at {token_list_path}")
        return []

    if isinstance(data, dict):
        data = data.get("tokens") or data.get("data") or []

    if not isinstance(data, list):
        return []

    normalized: List[Dict[str, Any]] = []
    for token in data:
        if not isinstance(token, dict):
            continue
        address = _resolve_token_address(token)
        if not address:
            continue
        normalized.append(
            {
                "address": address,
                "symbol": _resolve_token_symbol(token),
                "name": _resolve_token_name(token),
            }
        )
    print(f"[phantom] loaded {len(normalized)} tokens")
    return normalized


def collect_token_universe_birdeye(
    *,
    limit_tokens: int,
    token_scan_limit: int,
    min_liquidity_usd: float,
    min_volume_usd: float,
    pair_sort: str,
    sleep_seconds: float,
    cache_hours: int,
    sample_seed: int,
) -> List[Dict[str, Any]]:
    source_limit = max(limit_tokens, token_scan_limit, 50)
    tokens = load_birdeye_tokens(limit=source_limit)
    if not tokens:
        print("[birdeye] falling back to dexscreener token list")
        return collect_token_universe_dexscreener(
            limit_tokens=limit_tokens,
            token_scan_limit=token_scan_limit,
            min_liquidity_usd=min_liquidity_usd,
            min_volume_usd=min_volume_usd,
            pair_sort=pair_sort,
            sleep_seconds=sleep_seconds,
            cache_hours=cache_hours,
            sample_seed=sample_seed,
        )
    return collect_token_universe_from_token_list(
        tokens,
        limit_tokens=limit_tokens,
        token_scan_limit=token_scan_limit,
        min_liquidity_usd=min_liquidity_usd,
        min_volume_usd=min_volume_usd,
        pair_sort=pair_sort,
        sleep_seconds=sleep_seconds,
        sample_seed=sample_seed,
        source_name="birdeye",
    )


def collect_token_universe_phantom(
    *,
    limit_tokens: int,
    token_scan_limit: int,
    min_liquidity_usd: float,
    min_volume_usd: float,
    pair_sort: str,
    sleep_seconds: float,
    sample_seed: int,
    token_list_path: Path,
    token_list_url: Optional[str],
) -> List[Dict[str, Any]]:
    source_limit = max(limit_tokens, token_scan_limit, 50)
    tokens = load_phantom_tokens(token_list_path=token_list_path, token_list_url=token_list_url)
    if len(tokens) > source_limit:
        tokens = tokens[:source_limit]
    return collect_token_universe_from_token_list(
        tokens,
        limit_tokens=limit_tokens,
        token_scan_limit=token_scan_limit,
        min_liquidity_usd=min_liquidity_usd,
        min_volume_usd=min_volume_usd,
        pair_sort=pair_sort,
        sleep_seconds=sleep_seconds,
        sample_seed=sample_seed,
        source_name="phantom_terminal",
    )


def collect_token_universe_multi(
    *,
    limit_tokens: int,
    pages: int,
    sort: str,
    token_scan_limit: int,
    min_liquidity_usd: float,
    min_volume_usd: float,
    pair_sort: str,
    sleep_seconds: float,
    cache_hours: int,
    sample_seed: int,
    phantom_token_list: Path,
    phantom_token_url: Optional[str],
) -> List[Dict[str, Any]]:
    sources: List[List[Dict[str, Any]]] = []

    print("[tokens] collecting from geckoterminal...")
    gecko = collect_token_universe_geckoterminal(
        limit_tokens=limit_tokens,
        pages=pages,
        sort=sort,
        min_liquidity_usd=min_liquidity_usd,
        min_volume_usd=min_volume_usd,
        sleep_seconds=sleep_seconds,
    )
    print(f"[tokens] geckoterminal candidates: {len(gecko)}")
    sources.append(gecko)

    print("[tokens] collecting from dexscreener (jupiter list)...")
    dex = collect_token_universe_dexscreener(
        limit_tokens=limit_tokens,
        token_scan_limit=token_scan_limit,
        min_liquidity_usd=min_liquidity_usd,
        min_volume_usd=min_volume_usd,
        pair_sort=pair_sort,
        sleep_seconds=sleep_seconds,
        cache_hours=cache_hours,
        sample_seed=sample_seed,
    )
    print(f"[tokens] dexscreener candidates: {len(dex)}")
    sources.append(dex)

    print("[tokens] collecting from birdeye...")
    bird = collect_token_universe_birdeye(
        limit_tokens=limit_tokens,
        token_scan_limit=token_scan_limit,
        min_liquidity_usd=min_liquidity_usd,
        min_volume_usd=min_volume_usd,
        pair_sort=pair_sort,
        sleep_seconds=sleep_seconds,
        sample_seed=sample_seed,
    )
    print(f"[tokens] birdeye candidates: {len(bird)}")
    sources.append(bird)

    print("[tokens] collecting from phantom list...")
    phantom = collect_token_universe_phantom(
        limit_tokens=limit_tokens,
        token_scan_limit=token_scan_limit,
        min_liquidity_usd=min_liquidity_usd,
        min_volume_usd=min_volume_usd,
        pair_sort=pair_sort,
        sleep_seconds=sleep_seconds,
        sample_seed=sample_seed,
        token_list_path=phantom_token_list,
        token_list_url=phantom_token_url,
    )
    print(f"[tokens] phantom candidates: {len(phantom)}")
    sources.append(phantom)

    combined = merge_token_entries([entry for source in sources for entry in source])
    combined_sorted = sorted(combined, key=lambda item: item["volume_24h"], reverse=True)
    print(f"[tokens] combined candidates: {len(combined_sorted)}")
    return combined_sorted[:limit_tokens]


def merge_token_entries(entries: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    tokens_by_address: Dict[str, Dict[str, Any]] = {}
    for entry in entries:
        address = entry.get("address")
        if not address:
            continue
        existing = tokens_by_address.get(address)
        if not existing:
            tokens_by_address[address] = entry
            continue

        sources = sorted(set((existing.get("sources") or []) + (entry.get("sources") or [])))
        candidate = entry
        existing_volume = _to_float(existing.get("volume_24h"))
        candidate_volume = _to_float(entry.get("volume_24h"))
        if candidate_volume < existing_volume:
            candidate = existing
        elif candidate_volume == existing_volume:
            existing_liquidity = _to_float(existing.get("reserve_usd"))
            candidate_liquidity = _to_float(entry.get("reserve_usd"))
            if candidate_liquidity < existing_liquidity:
                candidate = existing

        candidate["sources"] = sources
        tokens_by_address[address] = candidate

    return list(tokens_by_address.values())


def collect_token_universe_dexscreener(
    *,
    limit_tokens: int,
    token_scan_limit: int,
    min_liquidity_usd: float,
    min_volume_usd: float,
    pair_sort: str,
    sleep_seconds: float,
    cache_hours: int,
    sample_seed: int,
) -> List[Dict[str, Any]]:
    tokens = load_jupiter_tokens(cache_hours=cache_hours)
    return collect_token_universe_from_token_list(
        tokens,
        limit_tokens=limit_tokens,
        token_scan_limit=token_scan_limit,
        min_liquidity_usd=min_liquidity_usd,
        min_volume_usd=min_volume_usd,
        pair_sort=pair_sort,
        sleep_seconds=sleep_seconds,
        sample_seed=sample_seed,
        source_name="jupiter",
    )


def load_jupiter_tokens(*, cache_hours: int) -> List[Dict[str, Any]]:
    cache_hours = max(cache_hours, 1)
    if JUPITER_CACHE.exists():
        try:
            payload = json.loads(JUPITER_CACHE.read_text())
            cached_at = payload.get("cached_at", 0)
            if time.time() - cached_at < cache_hours * 3600:
                data = payload.get("data", [])
                if isinstance(data, list):
                    return data
        except json.JSONDecodeError:
            pass

    data = None
    try:
        resp = requests.get(JUPITER_TOKEN_URL, timeout=30)
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as exc:
        print(f"[jupiter] token list fetch failed: {exc}")

    if not isinstance(data, list):
        try:
            resp = requests.get(SOLANA_TOKEN_LIST_URL, timeout=30)
            resp.raise_for_status()
            payload = resp.json()
            data = payload.get("tokens", [])
        except requests.RequestException as exc:
            print(f"[solana-token-list] fetch failed: {exc}")
            return []

    if isinstance(data, list):
        JUPITER_CACHE.parent.mkdir(parents=True, exist_ok=True)
        JUPITER_CACHE.write_text(json.dumps({"cached_at": time.time(), "data": data}))
        return data
    return []


def select_best_pair(pairs: List[Dict[str, Any]], *, sort_key: str) -> Optional[Dict[str, Any]]:
    if not pairs:
        return None

    def score(pair: Dict[str, Any]) -> Tuple[float, float, float]:
        liquidity = _to_float((pair.get("liquidity") or {}).get("usd"))
        volume = _to_float((pair.get("volume") or {}).get("h24"))
        txns = _to_float(_pair_tx_count(pair))
        if sort_key == "liquidity":
            return (liquidity, volume, txns)
        if sort_key == "txns":
            return (txns, volume, liquidity)
        return (volume, liquidity, txns)

    return max(pairs, key=score)


def build_entry_from_pair(
    pair: Dict[str, Any],
    *,
    token_address: str,
    token_symbol: Optional[str],
    token_name: Optional[str],
) -> Optional[Dict[str, Any]]:
    base = pair.get("baseToken") or {}
    quote = pair.get("quoteToken") or {}
    base_address = base.get("address")
    quote_address = quote.get("address")
    if not base_address or not quote_address:
        return None

    if base_address == token_address:
        token_meta = base
        quote_meta = quote
    elif quote_address == token_address:
        token_meta = quote
        quote_meta = base
    else:
        return None

    symbol = token_symbol or token_meta.get("symbol") or token_address[:6]
    if str(symbol).upper() in EXCLUDED_SYMBOLS:
        return None

    pool_address = pair.get("pairAddress")
    if not pool_address:
        return None

    volume_24h = _to_float((pair.get("volume") or {}).get("h24"))
    reserve_usd = _to_float((pair.get("liquidity") or {}).get("usd"))
    base_symbol = base.get("symbol") or "BASE"
    quote_symbol = quote.get("symbol") or "QUOTE"
    pool_name = f"{base_symbol} / {quote_symbol}"

    return {
        "symbol": symbol,
        "name": token_name or token_meta.get("name") or symbol,
        "address": token_address,
        "quote_symbol": quote_meta.get("symbol"),
        "quote_address": quote_meta.get("address"),
        "pool_address": pool_address,
        "pool_name": pool_name,
        "pool_id": f"{pair.get('dexId', 'dex')}:{pool_address}",
        "dex": pair.get("dexId"),
        "volume_24h": volume_24h,
        "reserve_usd": reserve_usd,
    }


def _pair_tx_count(pair: Dict[str, Any]) -> float:
    txns = pair.get("txns") or {}
    h24 = txns.get("h24") or {}
    return _to_float(h24.get("buys")) + _to_float(h24.get("sells"))


def _resolve_tokens(
    pool: Dict[str, Any],
    included_tokens: Dict[str, Dict[str, Any]],
) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
    relationships = pool.get("relationships", {}) or {}
    base_id = relationships.get("base_token", {}).get("data", {}).get("id")
    quote_id = relationships.get("quote_token", {}).get("data", {}).get("id")
    if not base_id or not quote_id:
        return None, None

    base = included_tokens.get(base_id, {}).copy()
    quote = included_tokens.get(quote_id, {}).copy()
    if "address" not in base:
        base["address"] = _strip_token_prefix(base_id)
    if "address" not in quote:
        quote["address"] = _strip_token_prefix(quote_id)
    return base, quote


def _resolve_dex(pool: Dict[str, Any]) -> Optional[str]:
    dex_id = pool.get("relationships", {}).get("dex", {}).get("data", {}).get("id")
    return dex_id


def _strip_token_prefix(token_id: str) -> str:
    if "_" in token_id:
        return token_id.split("_", 1)[1]
    return token_id


def fetch_candles_for_days(
    *,
    pool_address: Optional[str],
    token_address: Optional[str],
    timeframe: str,
    days: int,
    ohlcv_source: str,
    sleep_seconds: float,
) -> List[Dict[str, Any]]:
    limit = min(days * 24, 720)
    if sleep_seconds > 0:
        time.sleep(sleep_seconds)

    if ohlcv_source in ("geckoterminal", "auto") and pool_address:
        payload = fetch_pool_ohlcv("solana", pool_address, timeframe, limit=limit)
        if payload:
            ohlcv_list = payload.get("data", {}).get("attributes", {}).get("ohlcv_list", []) or []
            if ohlcv_list:
                merged = sorted(ohlcv_list, key=lambda row: row[0])
                return normalize_ohlcv_list(merged)

    if ohlcv_source in ("birdeye", "auto") and token_address and birdeye.has_api_key():
        timeframe_map = {"hour": "1H"}
        birdeye_timeframe = timeframe_map.get(timeframe, "1H")
        payload = birdeye.fetch_ohlcv(
            token_address,
            timeframe=birdeye_timeframe,
            limit=limit,
        )
        if payload:
            candles = birdeye.normalize_ohlcv(payload)
            if candles:
                return candles

    return []


def split_daily_windows(
    candles: List[Dict[str, Any]],
    *,
    min_candles: int,
) -> List[Tuple[int, List[Dict[str, Any]]]]:
    buckets: Dict[int, List[Dict[str, Any]]] = {}
    for candle in candles:
        ts = candle.get("timestamp")
        if ts is None:
            continue
        day_ts = int(ts // 86400) * 86400
        buckets.setdefault(day_ts, []).append(candle)

    windows: List[Tuple[int, List[Dict[str, Any]]]] = []
    for day_ts in sorted(buckets):
        day_candles = sorted(buckets[day_ts], key=lambda c: c.get("timestamp") or 0)
        if len(day_candles) < min_candles:
            continue
        windows.append((day_ts, day_candles))
    return windows


def build_strategies(
    *,
    max_strategies: int,
    capital_usd: float,
    fee_bps: float,
    slippage_bps: float,
    risk_per_trade: float,
    stop_loss_pct: float,
    take_profit_pct: float,
    max_position_pct: float,
) -> List[Dict[str, Any]]:
    strategies: List[Dict[str, Any]] = []

    for fast in [2, 3, 4, 5, 6, 7, 8, 9, 10]:
        for slow in [11, 12, 13, 14, 15, 16, 18, 20, 21, 22, 23]:
            if fast >= slow:
                continue
            cfg = trading_pipeline.StrategyConfig(
                kind="sma_cross",
                params={"fast": fast, "slow": slow},
                fee_bps=fee_bps,
                slippage_bps=slippage_bps,
                risk_per_trade=risk_per_trade,
                stop_loss_pct=stop_loss_pct,
                take_profit_pct=take_profit_pct,
                max_position_pct=max_position_pct,
                capital_usd=capital_usd,
            )
            strategies.append({"id": f"sma_{fast}_{slow}", "config": cfg})

    for period in [5, 7, 9, 12, 14, 18]:
        for lower, upper in [
            (20, 80),
            (25, 75),
            (30, 70),
            (35, 65),
            (40, 60),
            (45, 55),
        ]:
            cfg = trading_pipeline.StrategyConfig(
                kind="rsi",
                params={"period": period, "lower": lower, "upper": upper},
                fee_bps=fee_bps,
                slippage_bps=slippage_bps,
                risk_per_trade=risk_per_trade,
                stop_loss_pct=stop_loss_pct,
                take_profit_pct=take_profit_pct,
                max_position_pct=max_position_pct,
                capital_usd=capital_usd,
            )
            strategies.append({"id": f"rsi_{period}_{lower}_{upper}", "config": cfg})

    if max_strategies and len(strategies) > max_strategies:
        return strategies[:max_strategies]
    return strategies


def write_outputs(
    *,
    hits: List[Dict[str, Any]],
    best_overall: List[Dict[str, Any]],
    tokens_tested: int,
    windows_tested: int,
    threshold: float,
    days: int,
    strategies: List[Dict[str, Any]],
    require_locked: bool,
    min_locked_pct: float,
    min_locked_usd: float,
    source: str,
    ohlcv_source: str,
    pair_sort: str,
    token_scan_limit: int,
    limit_tokens: int,
    safe_mode: bool,
    min_trades: int,
    max_drawdown: Optional[float],
    social_handle: Optional[str],
    social_overrides_applied: bool,
) -> None:
    best_sorted = sorted(best_overall, key=lambda item: item["roi"], reverse=True)
    top20 = best_sorted[:20]

    if require_locked:
        for entry in top20:
            report = rugcheck.fetch_report(entry["token"]["address"])
            entry["lock_stats"] = rugcheck.best_lock_stats(report)
            entry["locked"] = rugcheck.has_locked_liquidity(
                report,
                min_locked_pct=min_locked_pct,
                min_locked_usd=min_locked_usd,
            )

    summary = {
        "threshold": threshold,
        "days": days,
        "tokens_tested": tokens_tested,
        "windows_tested": windows_tested,
        "strategies_tested": len(strategies),
        "hits_found": len(hits),
        "require_locked_liquidity": require_locked,
        "min_locked_pct": min_locked_pct,
        "min_locked_usd": min_locked_usd,
        "source": source,
        "ohlcv_source": ohlcv_source,
        "pair_sort": pair_sort,
        "token_scan_limit": token_scan_limit,
        "limit_tokens": limit_tokens,
        "safe_mode": safe_mode,
        "min_trades": min_trades,
        "max_drawdown": max_drawdown,
        "social_handle": social_handle,
        "social_overrides_applied": social_overrides_applied,
    }

    (OUT_DIR / "hits.json").write_text(json.dumps(hits, indent=2))
    (OUT_DIR / "top20.json").write_text(json.dumps(top20, indent=2))
    (OUT_DIR / "summary.json").write_text(json.dumps(summary, indent=2))


def _save_progress(
    index: int,
    tokens_tested: int,
    windows_tested: int,
    hits: List[Dict[str, Any]],
    best_overall: List[Dict[str, Any]],
) -> None:
    payload = {
        "last_index": index,
        "tokens_tested": tokens_tested,
        "windows_tested": windows_tested,
        "hits": hits,
        "best_overall": best_overall,
    }
    PROGRESS_PATH.write_text(json.dumps(payload, indent=2))


def _to_float(value: Any) -> float:
    if value is None:
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


if __name__ == "__main__":
    main()
