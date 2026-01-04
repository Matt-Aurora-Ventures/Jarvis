#!/usr/bin/env python3
"""Scan Solana DEX pools, backtest 90d candles in 30d windows, and build bots."""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core import trading_pipeline
from core.geckoterminal import (
    extract_included_tokens,
    fetch_pool_ohlcv,
    fetch_pools,
    normalize_ohlcv_list,
)


OUT_DIR = ROOT / "data" / "trader" / "solana_dex"
BOT_DIR = OUT_DIR / "bots"

TIMEFRAME_SECONDS = {
    "minute": 60,
    "hour": 3600,
    "day": 86400,
}

EXCLUDED_ADDRESSES = {
    "So11111111111111111111111111111111111111112",  # SOL
    "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",  # USDC
    "Es9vMFrzaCER3EJmqvQC2Uo9qowWP1h1xFh3Le7YpR1V",  # USDT
}
EXCLUDED_SYMBOLS = {"SOL", "USDC", "USDT"}


def main() -> None:
    args = parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    BOT_DIR.mkdir(parents=True, exist_ok=True)

    tokens = collect_token_universe(
        limit_tokens=args.limit_tokens,
        pages=args.pages,
        min_liquidity_usd=args.min_liquidity_usd,
        min_volume_usd=args.min_volume_usd,
        sleep_seconds=args.sleep_seconds,
    )

    if not tokens:
        print("No tokens found. Check API or thresholds.")
        return

    (OUT_DIR / "token_universe.json").write_text(json.dumps(tokens, indent=2))

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

    results: List[Dict[str, Any]] = []
    for idx, token in enumerate(tokens, 1):
        print(f"[{idx}/{len(tokens)}] Backtesting {token['symbol']} ({token['address'][:6]}...)")
        token_result = backtest_token(
            token,
            strategies,
            timeframe=args.timeframe,
            window_days=args.window_days,
            windows=args.windows,
            sleep_seconds=args.sleep_seconds,
            min_candles_ratio=args.min_candles_ratio,
            min_trades=args.min_trades,
        )
        if token_result:
            results.append(token_result)

    if not results:
        print("No backtest results produced.")
        return

    results.sort(key=lambda item: item["score"], reverse=True)
    top5 = results[:5]

    (OUT_DIR / "backtest_results.json").write_text(json.dumps(results, indent=2))
    (OUT_DIR / "top5.json").write_text(json.dumps(top5, indent=2))
    (OUT_DIR / "top5.md").write_text(render_top5_markdown(top5))

    for entry in top5:
        write_bot_config(entry)

    print("\nTop 5 tokens:")
    for rank, entry in enumerate(top5, 1):
        token = entry["token"]
        strategy = entry["best_strategy"]
        print(
            f"{rank}. {token['symbol']} "
            f"(ROI 90d {strategy['roi_90d']*100:.1f}%, "
            f"avg 30d {strategy['avg_window_roi']*100:.1f}%)"
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Solana DEX backtest pipeline")
    parser.add_argument("--limit-tokens", type=int, default=100)
    parser.add_argument("--pages", type=int, default=10)
    parser.add_argument("--min-liquidity-usd", type=float, default=50000)
    parser.add_argument("--min-volume-usd", type=float, default=50000)
    parser.add_argument("--timeframe", type=str, default="hour", choices=TIMEFRAME_SECONDS.keys())
    parser.add_argument("--window-days", type=int, default=30)
    parser.add_argument("--windows", type=int, default=3)
    parser.add_argument("--max-strategies", type=int, default=60)
    parser.add_argument("--capital-usd", type=float, default=10.0)
    parser.add_argument("--fee-bps", type=float, default=30.0)
    parser.add_argument("--slippage-bps", type=float, default=20.0)
    parser.add_argument("--risk-per-trade", type=float, default=0.02)
    parser.add_argument("--stop-loss-pct", type=float, default=0.03)
    parser.add_argument("--take-profit-pct", type=float, default=0.06)
    parser.add_argument("--max-position-pct", type=float, default=0.25)
    parser.add_argument("--sleep-seconds", type=float, default=0.25)
    parser.add_argument("--min-candles-ratio", type=float, default=0.3)
    parser.add_argument("--min-trades", type=int, default=1)
    return parser.parse_args()


def collect_token_universe(
    *,
    limit_tokens: int,
    pages: int,
    min_liquidity_usd: float,
    min_volume_usd: float,
    sleep_seconds: float,
) -> List[Dict[str, Any]]:
    tokens_by_address: Dict[str, Dict[str, Any]] = {}

    for page in range(1, pages + 1):
        payload = fetch_pools("solana", page=page, include_tokens=True)
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
            }

            existing = tokens_by_address.get(base_address)
            if not existing or volume_24h > existing["volume_24h"]:
                tokens_by_address[base_address] = token_entry

        time.sleep(sleep_seconds)

    tokens = sorted(tokens_by_address.values(), key=lambda item: item["volume_24h"], reverse=True)
    return tokens[:limit_tokens]


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


def backtest_token(
    token: Dict[str, Any],
    strategies: List[Dict[str, Any]],
    *,
    timeframe: str,
    window_days: int,
    windows: int,
    sleep_seconds: float,
    min_candles_ratio: float,
    min_trades: int,
) -> Optional[Dict[str, Any]]:
    pool_address = token.get("pool_address")
    if not pool_address:
        return None

    window_candles = _candles_per_window(timeframe, window_days)
    all_windows = fetch_ohlcv_windows(
        pool_address=pool_address,
        timeframe=timeframe,
        window_candles=window_candles,
        windows=windows,
        sleep_seconds=sleep_seconds,
    )

    if not all_windows:
        return None

    merged = merge_ohlcv_windows(all_windows)
    if not merged:
        return None

    min_candles = int(window_candles * windows * min_candles_ratio)
    if len(merged) < min_candles:
        return None

    full_candles = normalize_ohlcv_list(merged)
    window_candles_list = [normalize_ohlcv_list(window) for window in all_windows]

    best = None
    best_score = None

    for strat in strategies:
        strat_id = strat["id"]
        strat_cfg = strat["config"]
        full_result = trading_pipeline.run_backtest(
            full_candles,
            symbol=token["symbol"],
            interval=timeframe,
            strategy=strat_cfg,
        )

        window_results = [
            trading_pipeline.run_backtest(
                window,
                symbol=token["symbol"],
                interval=timeframe,
                strategy=strat_cfg,
            )
            for window in window_candles_list
        ]

        score_payload = score_strategy(full_result, window_results, min_trades=min_trades)
        if not score_payload:
            continue

        score = score_payload["score"]
        if best_score is None or score > best_score:
            best_score = score
            best = {
                "strategy_id": strat_id,
                "strategy": asdict(strat_cfg),
                "roi_90d": full_result.roi,
                "net_pnl": full_result.net_pnl,
                "profit_factor": full_result.profit_factor,
                "total_trades": full_result.total_trades,
                "max_drawdown": full_result.max_drawdown,
                "avg_window_roi": score_payload["avg_window_roi"],
                "window_rois": score_payload["window_rois"],
                "score": score,
            }

    if not best:
        return None

    return {
        "token": token,
        "best_strategy": best,
        "score": best_score,
        "timeframe": timeframe,
        "window_days": window_days,
        "windows": windows,
    }


def score_strategy(
    full_result: trading_pipeline.BacktestResult,
    window_results: List[trading_pipeline.BacktestResult],
    *,
    min_trades: int = 5,
) -> Optional[Dict[str, Any]]:
    if full_result.error:
        return None
    if full_result.total_trades < min_trades:
        return None

    window_rois = [result.roi for result in window_results if not result.error]
    if not window_rois:
        return None

    avg_window_roi = sum(window_rois) / len(window_rois)
    score = avg_window_roi - (full_result.max_drawdown * 0.5)

    return {
        "avg_window_roi": avg_window_roi,
        "window_rois": window_rois,
        "score": score,
    }


def fetch_ohlcv_windows(
    *,
    pool_address: str,
    timeframe: str,
    window_candles: int,
    windows: int,
    sleep_seconds: float,
) -> List[List[List[Any]]]:
    all_windows: List[List[List[Any]]] = []
    before_timestamp: Optional[int] = None

    for _ in range(windows):
        payload = fetch_pool_ohlcv(
            "solana",
            pool_address,
            timeframe,
            limit=window_candles,
            before_timestamp=before_timestamp,
        )
        if not payload:
            break
        ohlcv_list = payload.get("data", {}).get("attributes", {}).get("ohlcv_list", []) or []
        if not ohlcv_list:
            break
        all_windows.append(ohlcv_list)
        oldest = min(row[0] for row in ohlcv_list)
        before_timestamp = oldest - 1
        time.sleep(sleep_seconds)

    return all_windows


def merge_ohlcv_windows(windows: List[List[List[Any]]]) -> List[List[Any]]:
    seen = set()
    merged: List[List[Any]] = []
    for window in windows:
        for row in window:
            if not row:
                continue
            ts = row[0]
            if ts in seen:
                continue
            seen.add(ts)
            merged.append(row)
    merged.sort(key=lambda row: row[0])
    return merged


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
    strategy_list: List[Dict[str, Any]] = []

    for fast in [4, 6, 8, 10, 12, 15]:
        for slow in [20, 30, 40, 50, 60]:
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
            strategy_list.append({"id": f"sma_{fast}_{slow}", "config": cfg})

    for period in [7, 10, 14, 21]:
        for lower, upper in [(25, 75), (30, 70), (35, 65), (40, 60)]:
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
            strategy_list.append({"id": f"rsi_{period}_{lower}_{upper}", "config": cfg})

    if max_strategies and len(strategy_list) > max_strategies:
        return strategy_list[:max_strategies]
    return strategy_list


def _candles_per_window(timeframe: str, window_days: int) -> int:
    seconds = TIMEFRAME_SECONDS.get(timeframe, 3600)
    return int((window_days * 86400) / seconds)


def _to_float(value: Any) -> float:
    if value is None:
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def write_bot_config(entry: Dict[str, Any]) -> None:
    token = entry["token"]
    strategy = entry["best_strategy"]

    bot_config = {
        "bot_id": f"solana_{token['symbol']}_{token['address'][:6]}",
        "token": token,
        "strategy": strategy,
        "timeframe": entry.get("timeframe", "hour"),
        "window_days": entry.get("window_days"),
        "windows": entry.get("windows"),
        "execution": {
            "mode": "paper",
            "dex": token.get("dex"),
            "router": "jupiter",
            "quote_api": "https://quote-api.jup.ag/v6/quote",
            "swap_api": "https://quote-api.jup.ag/v6/swap",
            "rpc_url": "https://api.mainnet-beta.solana.com",
        },
        "risk": {
            "capital_usd": strategy["strategy"]["capital_usd"],
            "max_position_pct": strategy["strategy"]["max_position_pct"],
            "risk_per_trade": strategy["strategy"]["risk_per_trade"],
            "stop_loss_pct": strategy["strategy"]["stop_loss_pct"],
            "take_profit_pct": strategy["strategy"]["take_profit_pct"],
        },
        "data_sources": {
            "ohlcv": "geckoterminal",
            "price": "jupiter",
        },
    }

    filename = f"{_slug(token['symbol'])}_{token['address'][:6]}.json"
    (BOT_DIR / filename).write_text(json.dumps(bot_config, indent=2))


def render_top5_markdown(entries: List[Dict[str, Any]]) -> str:
    lines = ["# Solana DEX Top 5 (90d backtest, 30d windows)", ""]
    for idx, entry in enumerate(entries, 1):
        token = entry["token"]
        strat = entry["best_strategy"]
        lines.extend(
            [
                f"## {idx}. {token['symbol']} ({token['name']})",
                f"- Address: {token['address']}",
                f"- Pool: {token['pool_name']} ({token['pool_address']})",
                f"- Dex: {token.get('dex')}",
                f"- 24h Volume: ${token['volume_24h']:.2f}",
                f"- Liquidity: ${token['reserve_usd']:.2f}",
                f"- Strategy: {strat['strategy_id']}",
                f"- ROI 90d: {strat['roi_90d']*100:.2f}%",
                f"- Avg 30d ROI: {strat['avg_window_roi']*100:.2f}%",
                f"- Max DD: {strat['max_drawdown']*100:.2f}%",
                f"- Trades: {strat['total_trades']}",
                "",
            ]
        )
    return "\n".join(lines).strip() + "\n"


def _slug(text: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9]+", "-", text or "").strip("-")
    return cleaned.lower() or "token"


if __name__ == "__main__":
    main()
